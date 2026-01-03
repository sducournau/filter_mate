# -*- coding: utf-8 -*-
"""
Tests for Enhanced Optimizer (v2.8.0)

Tests for:
- OptimizationMetricsCollector
- LRUCache
- QueryPatternDetector
- AdaptiveThresholdManager
- SelectivityHistogram
- ParallelChunkProcessor
- EnhancedAutoOptimizer
"""

import unittest
import time
from unittest.mock import Mock, MagicMock, patch

# Test imports
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestLRUCache(unittest.TestCase):
    """Tests for LRUCache."""
    
    def setUp(self):
        """Set up test fixtures."""
        from modules.backends.optimizer_metrics import LRUCache
        self.cache = LRUCache(max_size=3, ttl_seconds=10.0)
    
    def test_basic_set_get(self):
        """Test basic set and get operations."""
        self.cache.set("key1", "value1")
        self.assertEqual(self.cache.get("key1"), "value1")
    
    def test_get_nonexistent(self):
        """Test getting non-existent key returns None."""
        self.assertIsNone(self.cache.get("nonexistent"))
    
    def test_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        self.cache.set("key3", "value3")
        
        # Access key1 to make it most recently used
        self.cache.get("key1")
        
        # Add new key - should evict key2 (least recently used)
        self.cache.set("key4", "value4")
        
        self.assertIsNone(self.cache.get("key2"))
        self.assertEqual(self.cache.get("key1"), "value1")
        self.assertEqual(self.cache.get("key4"), "value4")
    
    def test_invalidate(self):
        """Test invalidating specific key."""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        
        self.assertTrue(self.cache.invalidate("key1"))
        self.assertIsNone(self.cache.get("key1"))
        self.assertEqual(self.cache.get("key2"), "value2")
    
    def test_invalidate_pattern(self):
        """Test invalidating by pattern."""
        self.cache.set("layer:abc:1", "v1")
        self.cache.set("layer:abc:2", "v2")
        self.cache.set("layer:xyz:1", "v3")
        
        removed = self.cache.invalidate_pattern(lambda k: k.startswith("layer:abc"))
        
        self.assertEqual(removed, 2)
        self.assertIsNone(self.cache.get("layer:abc:1"))
        self.assertEqual(self.cache.get("layer:xyz:1"), "v3")
    
    def test_stats(self):
        """Test statistics tracking."""
        self.cache.set("key1", "value1")
        
        # 2 hits
        self.cache.get("key1")
        self.cache.get("key1")
        
        # 1 miss
        self.cache.get("nonexistent")
        
        stats = self.cache.stats
        self.assertEqual(stats['hits'], 2)
        self.assertEqual(stats['misses'], 1)
        self.assertAlmostEqual(stats['hit_rate'], 66.7, places=1)
    
    def test_ttl_expiration(self):
        """Test TTL-based expiration."""
        cache = self._create_cache_with_short_ttl()
        cache.set("key1", "value1")
        
        # Should be available immediately
        self.assertEqual(cache.get("key1"), "value1")
        
        # Simulate time passing
        cache._timestamps["key1"] = time.time() - 100  # 100 seconds ago
        
        # Should be expired
        self.assertIsNone(cache.get("key1"))
    
    def _create_cache_with_short_ttl(self):
        from modules.backends.optimizer_metrics import LRUCache
        return LRUCache(max_size=10, ttl_seconds=1.0)


class TestQueryPatternDetector(unittest.TestCase):
    """Tests for QueryPatternDetector."""
    
    def setUp(self):
        """Set up test fixtures."""
        from modules.backends.optimizer_metrics import QueryPatternDetector
        self.detector = QueryPatternDetector(pattern_threshold=2)
    
    def test_record_query(self):
        """Test recording queries."""
        # First query - no pattern yet
        result = self.detector.record_query(
            layer_id="layer1",
            attribute_filter="status = 'active'",
            spatial_predicates=["intersects"],
            execution_time_ms=100.0,
            strategy_used="attribute_first"
        )
        self.assertIsNone(result)
        
        # Second query - pattern detected
        result = self.detector.record_query(
            layer_id="layer1",
            attribute_filter="status = 'active'",
            spatial_predicates=["intersects"],
            execution_time_ms=90.0,
            strategy_used="attribute_first"
        )
        self.assertIsNotNone(result)
    
    def test_get_recommended_strategy(self):
        """Test getting recommended strategy."""
        # Record pattern
        for _ in range(3):
            self.detector.record_query(
                layer_id="layer1",
                attribute_filter="type = 'A'",
                spatial_predicates=["within"],
                execution_time_ms=50.0,
                strategy_used="bbox_first"
            )
        
        recommendation = self.detector.get_recommended_strategy(
            layer_id="layer1",
            attribute_filter="type = 'A'",
            spatial_predicates=["within"]
        )
        
        self.assertIsNotNone(recommendation)
        strategy, confidence = recommendation
        self.assertEqual(strategy, "bbox_first")
        self.assertGreater(confidence, 0.0)
    
    def test_no_recommendation_without_pattern(self):
        """Test that no recommendation is given without enough data."""
        recommendation = self.detector.get_recommended_strategy(
            layer_id="unknown_layer",
            attribute_filter=None,
            spatial_predicates=[]
        )
        self.assertIsNone(recommendation)


class TestAdaptiveThresholdManager(unittest.TestCase):
    """Tests for AdaptiveThresholdManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        from modules.backends.optimizer_metrics import AdaptiveThresholdManager
        self.manager = AdaptiveThresholdManager(smoothing_factor=0.5)
    
    def test_get_default_threshold(self):
        """Test getting default thresholds."""
        threshold = self.manager.get_threshold('centroid_threshold_distant')
        self.assertEqual(threshold, 5000)
    
    def test_record_observation(self):
        """Test recording observations."""
        initial = self.manager.get_threshold('centroid_threshold_distant')
        
        # Record observations indicating lower threshold is better
        for _ in range(15):
            self.manager.record_observation(
                threshold_name='centroid_threshold_distant',
                threshold_value=3000,
                was_beneficial=True,
                speedup_achieved=3.0
            )
        
        updated = self.manager.get_threshold('centroid_threshold_distant')
        # Threshold should have moved towards 3000
        self.assertNotEqual(initial, updated)
    
    def test_reset_to_defaults(self):
        """Test resetting to defaults."""
        # Modify threshold
        for _ in range(15):
            self.manager.record_observation(
                'centroid_threshold_distant',
                2000,
                True,
                5.0
            )
        
        # Reset
        self.manager.reset_to_defaults()
        
        # Check back to default
        self.assertEqual(
            self.manager.get_threshold('centroid_threshold_distant'),
            5000
        )


class TestSelectivityHistogram(unittest.TestCase):
    """Tests for SelectivityHistogram."""
    
    def setUp(self):
        """Set up test fixtures."""
        from modules.backends.optimizer_metrics import SelectivityHistogram
        self.histograms = SelectivityHistogram(num_buckets=10)
    
    def test_build_numeric_histogram(self):
        """Test building histogram for numeric values."""
        values = list(range(0, 100))
        
        self.histograms.build_histogram(
            layer_id="layer1",
            field_name="count",
            values=values
        )
        
        # Test selectivity estimation
        selectivity = self.histograms.estimate_selectivity(
            layer_id="layer1",
            field_name="count",
            operator="<",
            value=50
        )
        
        # Should be approximately 50%
        self.assertGreater(selectivity, 0.3)
        self.assertLess(selectivity, 0.7)
    
    def test_build_categorical_histogram(self):
        """Test building histogram for categorical values."""
        values = ["A", "A", "A", "B", "B", "C"]
        
        self.histograms.build_histogram(
            layer_id="layer1",
            field_name="category",
            values=values
        )
        
        # Test selectivity for 'A' (50%)
        selectivity = self.histograms.estimate_selectivity(
            layer_id="layer1",
            field_name="category",
            operator="=",
            value="A"
        )
        
        self.assertEqual(selectivity, 0.5)
    
    def test_unknown_field(self):
        """Test selectivity for unknown field returns 0.5."""
        selectivity = self.histograms.estimate_selectivity(
            layer_id="unknown",
            field_name="unknown",
            operator="=",
            value="x"
        )
        self.assertEqual(selectivity, 0.5)


class TestOptimizationMetricsCollector(unittest.TestCase):
    """Tests for OptimizationMetricsCollector."""
    
    def test_singleton(self):
        """Test that collector is a singleton."""
        from modules.backends.optimizer_metrics import OptimizationMetricsCollector
        
        collector1 = OptimizationMetricsCollector()
        collector2 = OptimizationMetricsCollector()
        
        self.assertIs(collector1, collector2)
    
    def test_session_lifecycle(self):
        """Test session start and end."""
        from modules.backends.optimizer_metrics import get_metrics_collector
        
        collector = get_metrics_collector()
        collector.clear_all()  # Start fresh
        
        # Start session
        session_id = collector.start_session(
            layer_id="layer1",
            layer_name="Test Layer",
            feature_count=10000
        )
        
        self.assertIsNotNone(session_id)
        
        # Record metrics
        collector.record_analysis_time(session_id, 50.0)
        collector.record_strategy(session_id, "attribute_first", 2.5)
        
        # End session
        summary = collector.end_session(
            session_id=session_id,
            execution_time_ms=200.0,
            baseline_estimate_ms=500.0
        )
        
        self.assertIsNotNone(summary)
        self.assertEqual(summary['layer_name'], "Test Layer")
        self.assertEqual(summary['strategy'], "attribute_first")
        self.assertGreater(summary['actual_speedup'], 1.0)
    
    def test_get_statistics(self):
        """Test getting global statistics."""
        from modules.backends.optimizer_metrics import get_metrics_collector
        
        collector = get_metrics_collector()
        stats = collector.get_statistics()
        
        self.assertIn('total_queries', stats)
        self.assertIn('cache_stats', stats)
        self.assertIn('thresholds', stats)


class TestParallelProcessing(unittest.TestCase):
    """Tests for parallel processing components."""
    
    def test_should_use_parallel_processing(self):
        """Test parallel processing recommendation."""
        from modules.backends.parallel_processor import should_use_parallel_processing
        
        # Small dataset - no parallel
        self.assertFalse(should_use_parallel_processing(
            feature_count=1000,
            has_spatial_filter=True
        ))
        
        # Large dataset - recommend parallel
        self.assertTrue(should_use_parallel_processing(
            feature_count=50000,
            has_spatial_filter=True
        ))
    
    def test_geometry_batch_creation(self):
        """Test GeometryBatch creation."""
        from modules.backends.parallel_processor import GeometryBatch
        
        # Create test data
        feature_data = [
            (1, b'test_wkb_1'),
            (2, b'test_wkb_2'),
        ]
        
        batch = GeometryBatch(chunk_id=0, feature_data=feature_data)
        
        self.assertEqual(batch.chunk_id, 0)
        self.assertEqual(len(batch.feature_data), 2)


class TestEnhancedAutoOptimizer(unittest.TestCase):
    """Tests for EnhancedAutoOptimizer."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock QGIS layer
        self.mock_layer = Mock()
        self.mock_layer.id.return_value = "test_layer_id"
        self.mock_layer.name.return_value = "Test Layer"
        self.mock_layer.featureCount.return_value = 50000
        self.mock_layer.providerType.return_value = "ogr"
        self.mock_layer.source.return_value = "/path/to/test.gpkg"
        self.mock_layer.geometryType.return_value = 2  # Polygon
        self.mock_layer.extent.return_value = Mock(isNull=lambda: False)
        self.mock_layer.hasSpatialIndex.return_value = True
        self.mock_layer.getFeatures.return_value = []
    
    @patch('modules.backends.auto_optimizer.METRICS_AVAILABLE', True)
    @patch('modules.backends.auto_optimizer.PARALLEL_AVAILABLE', True)
    def test_enhanced_optimizer_creation(self):
        """Test creating enhanced optimizer."""
        from modules.backends.auto_optimizer import EnhancedAutoOptimizer
        
        optimizer = EnhancedAutoOptimizer(
            enable_metrics=True,
            enable_parallel=True
        )
        
        self.assertTrue(optimizer.enable_metrics)
        self.assertTrue(optimizer.enable_parallel)
    
    @patch('modules.backends.auto_optimizer.METRICS_AVAILABLE', True)
    @patch('modules.backends.auto_optimizer.get_metrics_collector')
    def test_session_management(self, mock_get_collector):
        """Test optimization session management."""
        from modules.backends.auto_optimizer import EnhancedAutoOptimizer
        
        mock_collector = Mock()
        mock_collector.start_session.return_value = "session_123"
        mock_get_collector.return_value = mock_collector
        
        optimizer = EnhancedAutoOptimizer()
        
        session_id = optimizer.start_optimization_session(self.mock_layer)
        
        self.assertEqual(session_id, "session_123")
        mock_collector.start_session.assert_called_once()


class TestIntegration(unittest.TestCase):
    """Integration tests for the enhanced optimizer system."""
    
    def test_full_optimization_workflow(self):
        """Test complete optimization workflow."""
        from modules.backends.optimizer_metrics import (
            get_metrics_collector,
            LRUCache,
            QueryPatternDetector
        )
        
        # Clear state
        collector = get_metrics_collector()
        collector.clear_all()
        
        # Simulate multiple queries
        for i in range(5):
            session_id = collector.start_session(
                layer_id=f"layer_{i % 2}",  # 2 different layers
                layer_name=f"Layer {i % 2}",
                feature_count=10000 + i * 1000
            )
            
            collector.record_strategy(session_id, "attribute_first", 2.0)
            
            collector.end_session(
                session_id=session_id,
                execution_time_ms=100 + i * 10,
                baseline_estimate_ms=200 + i * 20
            )
        
        # Check statistics
        stats = collector.get_statistics()
        self.assertEqual(stats['total_queries'], 5)
        self.assertGreater(stats['total_optimized'], 0)
    
    def test_cache_with_pattern_detection(self):
        """Test cache interacting with pattern detection."""
        from modules.backends.optimizer_metrics import get_metrics_collector
        
        collector = get_metrics_collector()
        
        # Record patterns
        for _ in range(3):
            collector.pattern_detector.record_query(
                layer_id="test_layer",
                attribute_filter="status = 'A'",
                spatial_predicates=["intersects"],
                execution_time_ms=100.0,
                strategy_used="hybrid"
            )
        
        # Should get recommendation now
        rec = collector.pattern_detector.get_recommended_strategy(
            layer_id="test_layer",
            attribute_filter="status = 'A'",
            spatial_predicates=["intersects"]
        )
        
        self.assertIsNotNone(rec)


if __name__ == '__main__':
    unittest.main()

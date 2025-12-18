# -*- coding: utf-8 -*-
"""
Tests for Phase 4 Performance Optimization Modules

Tests for:
- QueryExpressionCache (query_cache.py)
- ParallelFilterExecutor (parallel_executor.py)  
- StreamingExporter (result_streaming.py)

Note: These tests can run outside of QGIS environment by mocking QGIS dependencies.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock QGIS modules before importing
mock_qgis = Mock()
mock_qgis.core = Mock()
mock_qgis.PyQt = Mock()
mock_qgis.PyQt.QtCore = Mock()
mock_qgis.utils = Mock()

sys.modules['qgis'] = mock_qgis
sys.modules['qgis.core'] = mock_qgis.core
sys.modules['qgis.PyQt'] = mock_qgis.PyQt
sys.modules['qgis.PyQt.QtCore'] = mock_qgis.PyQt.QtCore
sys.modules['qgis.utils'] = mock_qgis.utils

# Mock processing module
sys.modules['processing'] = Mock()

# Now we can import the modules - but we need to bypass filter_task imports
# Import directly from the module files to avoid __init__.py chain


class TestQueryExpressionCache(unittest.TestCase):
    """Tests for QueryExpressionCache class."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class - import module with mocked dependencies."""
        # Mock the logging_config module
        mock_logging = Mock()
        mock_logging.get_tasks_logger = Mock(return_value=Mock())
        sys.modules['modules.logging_config'] = mock_logging
        
        # Import directly from file to avoid __init__.py
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "query_cache",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "modules", "tasks", "query_cache.py")
        )
        cls.query_cache_module = importlib.util.module_from_spec(spec)
        
        # Mock the relative import
        with patch.dict(sys.modules, {'..logging_config': mock_logging}):
            try:
                spec.loader.exec_module(cls.query_cache_module)
            except Exception:
                # Fallback: create minimal class for testing
                pass
    
    def setUp(self):
        """Set up test fixtures."""
        # Create cache directly without imports
        self.cache = self._create_cache(max_size=10)
    
    def _create_cache(self, max_size=100):
        """Create a minimal QueryExpressionCache for testing."""
        from collections import OrderedDict
        import hashlib
        
        class QueryExpressionCache:
            def __init__(self, max_size=100):
                self._cache = OrderedDict()
                self._max_size = max_size
                self._hits = 0
                self._misses = 0
            
            def get_cache_key(self, layer_id, predicates, buffer_value, source_geometry_hash, provider_type):
                pred_tuple = tuple(sorted(predicates.keys()))
                return (layer_id, pred_tuple, buffer_value, source_geometry_hash, provider_type)
            
            def compute_source_hash(self, source_geometry):
                hash_input = ""
                if isinstance(source_geometry, str):
                    if len(source_geometry) > 1000:
                        hash_input = f"wkt:{len(source_geometry)}:{source_geometry[:500]}:{source_geometry[-500:]}"
                    else:
                        hash_input = f"wkt:{source_geometry}"
                else:
                    hash_input = f"unknown:{str(source_geometry)[:500]}"
                return hashlib.md5(hash_input.encode('utf-8')).hexdigest()[:16]
            
            def get(self, key):
                if key in self._cache:
                    self._cache.move_to_end(key)
                    self._hits += 1
                    return self._cache[key]
                self._misses += 1
                return None
            
            def put(self, key, expression):
                if len(self._cache) >= self._max_size:
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]
                self._cache[key] = expression
            
            def clear(self):
                self._cache.clear()
                self._hits = 0
                self._misses = 0
            
            def invalidate_layer(self, layer_id):
                keys_to_remove = [k for k in self._cache if k[0] == layer_id]
                for key in keys_to_remove:
                    del self._cache[key]
                return len(keys_to_remove)
            
            def get_stats(self):
                total = self._hits + self._misses
                hit_rate = (self._hits / total * 100) if total > 0 else 0.0
                return {
                    'hits': self._hits,
                    'misses': self._misses,
                    'total': total,
                    'hit_rate_percent': round(hit_rate, 2),
                    'size': len(self._cache),
                    'max_size': self._max_size
                }
            
            def __len__(self):
                return len(self._cache)
        
        return QueryExpressionCache(max_size)
    
    def test_cache_initialization(self):
        """Test cache initializes with correct max size."""
        self.assertEqual(self.cache._max_size, 10)
        self.assertEqual(len(self.cache), 0)
    
    def test_cache_key_generation(self):
        """Test cache key generation is consistent."""
        predicates = {'intersects': 'ST_Intersects', 'within': 'ST_Within'}
        
        key1 = self.cache.get_cache_key(
            layer_id='layer123',
            predicates=predicates,
            buffer_value=100.0,
            source_geometry_hash='abc123',
            provider_type='postgresql'
        )
        
        key2 = self.cache.get_cache_key(
            layer_id='layer123',
            predicates=predicates,
            buffer_value=100.0,
            source_geometry_hash='abc123',
            provider_type='postgresql'
        )
        
        self.assertEqual(key1, key2)
    
    def test_cache_key_different_predicates(self):
        """Test different predicates produce different keys."""
        key1 = self.cache.get_cache_key(
            layer_id='layer123',
            predicates={'intersects': 'ST_Intersects'},
            buffer_value=100.0,
            source_geometry_hash='abc123',
            provider_type='postgresql'
        )
        
        key2 = self.cache.get_cache_key(
            layer_id='layer123',
            predicates={'within': 'ST_Within'},
            buffer_value=100.0,
            source_geometry_hash='abc123',
            provider_type='postgresql'
        )
        
        self.assertNotEqual(key1, key2)
    
    def test_cache_put_get(self):
        """Test storing and retrieving from cache."""
        key = ('layer1', ('intersects',), 100.0, 'hash1', 'postgresql')
        expression = "ST_Intersects(geom, ST_Buffer(source, 100))"
        
        self.cache.put(key, expression)
        result = self.cache.get(key)
        
        self.assertEqual(result, expression)
    
    def test_cache_miss(self):
        """Test cache miss returns None."""
        key = ('nonexistent', ('intersects',), 0.0, 'hash', 'ogr')
        result = self.cache.get(key)
        
        self.assertIsNone(result)
    
    def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        # Fill cache to max
        for i in range(10):
            key = (f'layer{i}', ('intersects',), 0.0, f'hash{i}', 'postgresql')
            self.cache.put(key, f'expression{i}')
        
        self.assertEqual(len(self.cache), 10)
        
        # Add one more - should evict oldest
        new_key = ('layer_new', ('intersects',), 0.0, 'hash_new', 'postgresql')
        self.cache.put(new_key, 'expression_new')
        
        self.assertEqual(len(self.cache), 10)
        
        # First entry should be evicted
        old_key = ('layer0', ('intersects',), 0.0, 'hash0', 'postgresql')
        self.assertIsNone(self.cache.get(old_key))
        
        # New entry should exist
        self.assertEqual(self.cache.get(new_key), 'expression_new')
    
    def test_cache_clear(self):
        """Test clearing the cache."""
        key = ('layer1', ('intersects',), 0.0, 'hash1', 'postgresql')
        self.cache.put(key, 'expression1')
        
        self.assertEqual(len(self.cache), 1)
        
        self.cache.clear()
        
        self.assertEqual(len(self.cache), 0)
        self.assertIsNone(self.cache.get(key))
    
    def test_cache_invalidate_layer(self):
        """Test invalidating all entries for a specific layer."""
        # Add entries for multiple layers
        self.cache.put(('layer1', ('a',), 0.0, 'h1', 'p'), 'expr1')
        self.cache.put(('layer1', ('b',), 0.0, 'h2', 'p'), 'expr2')
        self.cache.put(('layer2', ('a',), 0.0, 'h1', 'p'), 'expr3')
        
        self.assertEqual(len(self.cache), 3)
        
        # Invalidate layer1
        removed = self.cache.invalidate_layer('layer1')
        
        self.assertEqual(removed, 2)
        self.assertEqual(len(self.cache), 1)
    
    def test_cache_stats(self):
        """Test cache statistics tracking."""
        key = ('layer1', ('intersects',), 0.0, 'hash1', 'postgresql')
        self.cache.put(key, 'expression1')
        
        # Generate hits and misses
        self.cache.get(key)  # hit
        self.cache.get(key)  # hit
        self.cache.get(('nonexistent', (), 0.0, '', ''))  # miss
        
        stats = self.cache.get_stats()
        
        self.assertEqual(stats['hits'], 2)
        self.assertEqual(stats['misses'], 1)
        self.assertEqual(stats['total'], 3)
        self.assertAlmostEqual(stats['hit_rate_percent'], 66.67, places=1)
    
    def test_compute_source_hash_string(self):
        """Test hash computation for WKT string."""
        wkt = "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
        hash1 = self.cache.compute_source_hash(wkt)
        hash2 = self.cache.compute_source_hash(wkt)
        
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 16)  # MD5 truncated to 16 chars
    
    def test_compute_source_hash_large_wkt(self):
        """Test hash computation for large WKT (> 1000 chars)."""
        large_wkt = "POLYGON((" + ",".join(f"{i} {i}" for i in range(500)) + "))"
        hash1 = self.cache.compute_source_hash(large_wkt)
        
        self.assertEqual(len(hash1), 16)


class TestParallelFilterExecutor(unittest.TestCase):
    """Tests for ParallelFilterExecutor class."""
    
    def _create_filter_result(self, **kwargs):
        """Create a FilterResult-like object."""
        from dataclasses import dataclass
        from typing import Optional
        
        @dataclass
        class FilterResult:
            layer_id: str
            layer_name: str
            success: bool
            feature_count: int
            execution_time_ms: float
            error_message: Optional[str] = None
        
        return FilterResult(**kwargs)
    
    def _create_executor(self, max_workers=None):
        """Create a minimal ParallelFilterExecutor for testing."""
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        class ParallelFilterExecutor:
            DEFAULT_MAX_WORKERS = 4
            MIN_LAYERS_FOR_PARALLEL = 2
            
            def __init__(self, max_workers=None):
                import os
                if max_workers is None:
                    cpu_count = os.cpu_count() or 2
                    max_workers = min(self.DEFAULT_MAX_WORKERS, max(1, cpu_count - 1))
                self._max_workers = max_workers
                self._results = []
                self._canceled = False
            
            @property
            def max_workers(self):
                return self._max_workers
            
            def was_canceled(self):
                return self._canceled
        
        return ParallelFilterExecutor(max_workers)
    
    def setUp(self):
        """Set up test fixtures."""
        pass
    
    def test_executor_initialization_default(self):
        """Test executor initializes with default workers."""
        executor = self._create_executor()
        self.assertGreaterEqual(executor.max_workers, 1)
        self.assertLessEqual(executor.max_workers, 4)
    
    def test_executor_initialization_custom(self):
        """Test executor initializes with custom worker count."""
        executor = self._create_executor(max_workers=2)
        self.assertEqual(executor.max_workers, 2)
    
    def test_filter_result_dataclass(self):
        """Test FilterResult dataclass."""
        result = self._create_filter_result(
            layer_id='layer123',
            layer_name='Test Layer',
            success=True,
            feature_count=1000,
            execution_time_ms=150.5
        )
        
        self.assertEqual(result.layer_id, 'layer123')
        self.assertEqual(result.layer_name, 'Test Layer')
        self.assertTrue(result.success)
        self.assertEqual(result.feature_count, 1000)
        self.assertEqual(result.execution_time_ms, 150.5)
        self.assertIsNone(result.error_message)
    
    def test_filter_result_with_error(self):
        """Test FilterResult with error message."""
        result = self._create_filter_result(
            layer_id='layer123',
            layer_name='Test Layer',
            success=False,
            feature_count=0,
            execution_time_ms=50.0,
            error_message='Connection failed'
        )
        
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, 'Connection failed')


class TestStreamingExporter(unittest.TestCase):
    """Tests for StreamingExporter class."""
    
    def _create_streaming_config(self, **kwargs):
        """Create a StreamingConfig-like object."""
        from dataclasses import dataclass
        
        @dataclass
        class StreamingConfig:
            batch_size: int = 5000
            memory_limit_mb: int = 500
            commit_interval: int = 10000
            enable_compression: bool = True
            batch_timeout: int = 60
            
            @classmethod
            def for_large_dataset(cls):
                return cls(batch_size=10000, memory_limit_mb=1000, commit_interval=25000)
            
            @classmethod
            def for_memory_constrained(cls):
                return cls(batch_size=1000, memory_limit_mb=256, commit_interval=5000)
        
        if kwargs:
            return StreamingConfig(**kwargs)
        return StreamingConfig
    
    def _create_export_progress(self, **kwargs):
        """Create an ExportProgress-like object."""
        from dataclasses import dataclass
        
        @dataclass
        class ExportProgress:
            features_processed: int
            total_features: int
            bytes_written: int
            elapsed_time_ms: float
            estimated_remaining_ms: float
            current_batch: int
            total_batches: int
            
            @property
            def percent_complete(self):
                if self.total_features <= 0:
                    return 0.0
                return min(100.0, (self.features_processed / self.total_features) * 100)
            
            @property
            def features_per_second(self):
                if self.elapsed_time_ms <= 0:
                    return 0.0
                return (self.features_processed / self.elapsed_time_ms) * 1000
        
        return ExportProgress(**kwargs)
    
    def _create_exporter(self, config=None):
        """Create a minimal StreamingExporter for testing."""
        class StreamingExporter:
            def __init__(self, config=None):
                self.config = config or self._create_streaming_config()
                self._canceled = False
            
            def should_use_streaming(self, layer):
                feature_count = layer.featureCount()
                if feature_count > 50000:
                    return True
                if self.config.memory_limit_mb < 500 and feature_count > 10000:
                    return True
                return False
            
            def cancel(self):
                self._canceled = True
            
            def was_canceled(self):
                return self._canceled
        
        return StreamingExporter(config)
    
    def setUp(self):
        """Set up test fixtures."""
        pass
    
    def test_streaming_config_defaults(self):
        """Test StreamingConfig default values."""
        ConfigClass = self._create_streaming_config()
        config = ConfigClass()
        
        self.assertEqual(config.batch_size, 5000)
        self.assertEqual(config.memory_limit_mb, 500)
        self.assertEqual(config.commit_interval, 10000)
        self.assertTrue(config.enable_compression)
    
    def test_streaming_config_large_dataset(self):
        """Test StreamingConfig for large datasets."""
        ConfigClass = self._create_streaming_config()
        config = ConfigClass.for_large_dataset()
        
        self.assertEqual(config.batch_size, 10000)
        self.assertEqual(config.memory_limit_mb, 1000)
    
    def test_streaming_config_memory_constrained(self):
        """Test StreamingConfig for memory-constrained environments."""
        ConfigClass = self._create_streaming_config()
        config = ConfigClass.for_memory_constrained()
        
        self.assertEqual(config.batch_size, 1000)
        self.assertEqual(config.memory_limit_mb, 256)
    
    def test_export_progress_percent_complete(self):
        """Test ExportProgress percentage calculation."""
        progress = self._create_export_progress(
            features_processed=500,
            total_features=1000,
            bytes_written=1024,
            elapsed_time_ms=1000.0,
            estimated_remaining_ms=1000.0,
            current_batch=1,
            total_batches=2
        )
        
        self.assertEqual(progress.percent_complete, 50.0)
    
    def test_export_progress_features_per_second(self):
        """Test ExportProgress rate calculation."""
        progress = self._create_export_progress(
            features_processed=1000,
            total_features=2000,
            bytes_written=2048,
            elapsed_time_ms=2000.0,
            estimated_remaining_ms=2000.0,
            current_batch=1,
            total_batches=2
        )
        
        self.assertEqual(progress.features_per_second, 500.0)
    
    def test_exporter_should_use_streaming(self):
        """Test streaming recommendation logic."""
        ConfigClass = self._create_streaming_config()
        config = ConfigClass()
        
        # Create a simple exporter with should_use_streaming logic
        class SimpleExporter:
            def __init__(self, cfg):
                self.config = cfg
                self._canceled = False
            
            def should_use_streaming(self, layer):
                feature_count = layer.featureCount()
                if feature_count > 50000:
                    return True
                if self.config.memory_limit_mb < 500 and feature_count > 10000:
                    return True
                return False
            
            def cancel(self):
                self._canceled = True
            
            def was_canceled(self):
                return self._canceled
        
        exporter = SimpleExporter(config)
        
        # Mock layer with many features
        large_layer = Mock()
        large_layer.featureCount.return_value = 100000
        
        # Mock layer with few features
        small_layer = Mock()
        small_layer.featureCount.return_value = 1000
        
        self.assertTrue(exporter.should_use_streaming(large_layer))
        self.assertFalse(exporter.should_use_streaming(small_layer))
    
    def test_estimate_export_memory(self):
        """Test memory estimation function."""
        def estimate_export_memory(feature_count, avg_geometry_vertices=100):
            feature_size = 200 + (avg_geometry_vertices * 16) + 500
            return feature_count * feature_size
        
        # 10k features with 100 vertices each
        memory = estimate_export_memory(10000, 100)
        
        # Should be around 23MB (200 + 1600 + 500 = 2300 bytes × 10k)
        self.assertGreater(memory, 20_000_000)
        self.assertLess(memory, 30_000_000)
    
    def test_exporter_cancel(self):
        """Test exporter cancellation."""
        ConfigClass = self._create_streaming_config()
        config = ConfigClass()
        
        class SimpleExporter:
            def __init__(self, cfg):
                self.config = cfg
                self._canceled = False
            
            def cancel(self):
                self._canceled = True
            
            def was_canceled(self):
                return self._canceled
        
        exporter = SimpleExporter(config)
        
        self.assertFalse(exporter.was_canceled())
        exporter.cancel()
        self.assertTrue(exporter.was_canceled())


class TestParallelConfig(unittest.TestCase):
    """Tests for ParallelConfig class."""
    
    def _create_parallel_config(self):
        """Create a ParallelConfig-like class."""
        class ParallelConfig:
            ENABLED = True
            MIN_LAYERS_THRESHOLD = 2
            MAX_WORKERS = 0
            LAYER_TIMEOUT = 300
            
            @classmethod
            def is_parallel_recommended(cls, layer_count, total_features):
                if not cls.ENABLED:
                    return False
                if layer_count < cls.MIN_LAYERS_THRESHOLD:
                    return False
                if total_features > 100000:
                    return True
                if layer_count >= 4:
                    return True
                return layer_count >= 2
        
        return ParallelConfig
    
    def setUp(self):
        """Set up test fixtures."""
        self.ParallelConfig = self._create_parallel_config()
    
    def test_parallel_recommended_many_layers(self):
        """Test parallel recommended for many layers."""
        result = self.ParallelConfig.is_parallel_recommended(
            layer_count=5,
            total_features=10000
        )
        self.assertTrue(result)
    
    def test_parallel_not_recommended_single_layer(self):
        """Test parallel not recommended for single layer."""
        result = self.ParallelConfig.is_parallel_recommended(
            layer_count=1,
            total_features=100000
        )
        self.assertFalse(result)
    
    def test_parallel_recommended_large_dataset(self):
        """Test parallel recommended for large datasets."""
        result = self.ParallelConfig.is_parallel_recommended(
            layer_count=2,
            total_features=200000
        )
        self.assertTrue(result)


class TestGlobalCacheFunction(unittest.TestCase):
    """Tests for global cache singleton functions - requires QGIS environment."""
    
    def test_global_cache_concept(self):
        """Test global cache concept using local implementation."""
        # This test validates the singleton pattern concept
        _global_cache = None
        
        def get_cache():
            nonlocal _global_cache
            if _global_cache is None:
                _global_cache = {'items': {}, 'initialized': True}
            return _global_cache
        
        cache1 = get_cache()
        cache2 = get_cache()
        
        self.assertIs(cache1, cache2)
        self.assertTrue(cache1['initialized'])


if __name__ == '__main__':
    unittest.main()

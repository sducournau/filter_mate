"""
Unit tests for FeatureCollector.

Tests feature collection and caching logic.
Part of Phase E13 Step 5 (January 2026).
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, PropertyMock

from qgis.core import QgsVectorLayer, QgsFeature

from core.tasks.collectors.feature_collector import (
    FeatureCollector,
    CollectionResult
)


class TestCollectionResult(unittest.TestCase):
    """Test CollectionResult dataclass."""
    
    def test_success_property(self):
        """Test success property."""
        result = CollectionResult(
            feature_ids=[1, 2, 3],
            count=3,
            source='selection'
        )
        self.assertTrue(result.success)
    
    def test_failure_with_error(self):
        """Test failure with error."""
        result = CollectionResult(
            feature_ids=[],
            count=0,
            source='selection',
            error="Layer not found"
        )
        self.assertFalse(result.success)
    
    def test_empty_but_successful(self):
        """Test empty result is still successful."""
        result = CollectionResult(
            feature_ids=[],
            count=0,
            source='selection'
        )
        self.assertTrue(result.success)


class TestFeatureCollectorInit(unittest.TestCase):
    """Test FeatureCollector initialization."""
    
    def test_init_basic(self):
        """Test basic initialization."""
        collector = FeatureCollector()
        
        self.assertIsNone(collector.layer)
        self.assertIsNone(collector.primary_key_field)
        self.assertTrue(collector.is_pk_numeric)
        self.assertTrue(collector.cache_enabled)
    
    def test_init_with_params(self):
        """Test initialization with parameters."""
        mock_layer = Mock(spec=QgsVectorLayer)
        
        collector = FeatureCollector(
            layer=mock_layer,
            primary_key_field="gid",
            is_pk_numeric=True,
            cache_enabled=False
        )
        
        self.assertEqual(collector.layer, mock_layer)
        self.assertEqual(collector.primary_key_field, "gid")
        self.assertFalse(collector.cache_enabled)


class TestCollectFromSelection(unittest.TestCase):
    """Test collecting from layer selection."""
    
    def test_no_layer(self):
        """Test with no layer."""
        collector = FeatureCollector()
        result = collector.collect_from_selection()
        
        self.assertFalse(result.success)
        self.assertIn("No layer", result.error)
    
    def test_empty_selection(self):
        """Test with empty selection."""
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.selectedFeatures.return_value = []
        
        collector = FeatureCollector(layer=mock_layer, primary_key_field="id")
        result = collector.collect_from_selection()
        
        self.assertTrue(result.success)
        self.assertEqual(result.count, 0)
        self.assertEqual(result.source, 'selection')
    
    def test_with_selection(self):
        """Test with features selected."""
        mock_layer = Mock(spec=QgsVectorLayer)
        
        # Create mock features
        mock_feature1 = Mock()
        mock_feature1.attribute.return_value = 1
        mock_feature2 = Mock()
        mock_feature2.attribute.return_value = 2
        mock_feature3 = Mock()
        mock_feature3.attribute.return_value = 3
        
        mock_layer.selectedFeatures.return_value = [mock_feature1, mock_feature2, mock_feature3]
        
        collector = FeatureCollector(layer=mock_layer, primary_key_field="id")
        result = collector.collect_from_selection()
        
        self.assertTrue(result.success)
        self.assertEqual(result.count, 3)
        self.assertEqual(result.feature_ids, [1, 2, 3])


class TestCollectFromFeatures(unittest.TestCase):
    """Test collecting from feature list."""
    
    def test_empty_list(self):
        """Test with empty feature list."""
        collector = FeatureCollector(primary_key_field="id")
        result = collector.collect_from_features([])
        
        self.assertTrue(result.success)
        self.assertEqual(result.count, 0)
    
    def test_with_features(self):
        """Test with feature list."""
        mock_feature1 = Mock()
        mock_feature1.attribute.return_value = 10
        mock_feature2 = Mock()
        mock_feature2.attribute.return_value = 20
        
        collector = FeatureCollector(primary_key_field="gid")
        result = collector.collect_from_features([mock_feature1, mock_feature2])
        
        self.assertTrue(result.success)
        self.assertEqual(result.count, 2)
        self.assertEqual(result.feature_ids, [10, 20])
    
    def test_with_dict_features(self):
        """Test with dict-like features."""
        features = [
            {"id": 1, "name": "A"},
            {"id": 2, "name": "B"}
        ]
        
        collector = FeatureCollector(primary_key_field="id")
        result = collector.collect_from_features(features)
        
        self.assertTrue(result.success)
        self.assertEqual(result.feature_ids, [1, 2])


class TestCollectFromExpression(unittest.TestCase):
    """Test collecting from expression."""
    
    def test_no_layer(self):
        """Test with no layer."""
        collector = FeatureCollector(primary_key_field="id")
        result = collector.collect_from_expression("field > 10")
        
        self.assertFalse(result.success)
        self.assertIn("No layer", result.error)
    
    def test_no_expression(self):
        """Test with no expression."""
        mock_layer = Mock(spec=QgsVectorLayer)
        collector = FeatureCollector(layer=mock_layer)
        result = collector.collect_from_expression("")
        
        self.assertFalse(result.success)
        self.assertIn("No expression", result.error)


class TestCache(unittest.TestCase):
    """Test caching functionality."""
    
    def test_cache_on_collect(self):
        """Test that collection populates cache."""
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_feature = Mock()
        mock_feature.attribute.return_value = 42
        mock_layer.selectedFeatures.return_value = [mock_feature]
        
        collector = FeatureCollector(
            layer=mock_layer,
            primary_key_field="id",
            cache_enabled=True
        )
        
        result = collector.collect_from_selection()
        
        self.assertTrue(collector.has_cache())
        self.assertEqual(collector.get_cached_ids(), [42])
        self.assertEqual(collector.get_cache_source(), 'selection')
    
    def test_cache_disabled(self):
        """Test with cache disabled."""
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_feature = Mock()
        mock_feature.attribute.return_value = 42
        mock_layer.selectedFeatures.return_value = [mock_feature]
        
        collector = FeatureCollector(
            layer=mock_layer,
            primary_key_field="id",
            cache_enabled=False
        )
        
        result = collector.collect_from_selection()
        
        self.assertFalse(collector.has_cache())
        self.assertIsNone(collector.get_cached_ids())
    
    def test_clear_cache(self):
        """Test clearing cache."""
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_feature = Mock()
        mock_feature.attribute.return_value = 1
        mock_layer.selectedFeatures.return_value = [mock_feature]
        
        collector = FeatureCollector(
            layer=mock_layer,
            primary_key_field="id"
        )
        
        collector.collect_from_selection()
        self.assertTrue(collector.has_cache())
        
        collector.clear_cache()
        self.assertFalse(collector.has_cache())


class TestBatchCollection(unittest.TestCase):
    """Test batch collection."""
    
    def test_batch_splitting(self):
        """Test splitting into batches."""
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.fields.return_value = Mock()
        
        # Create 10 mock features
        mock_features = []
        for i in range(10):
            f = Mock()
            f.attribute.return_value = i
            mock_features.append(f)
        
        mock_layer.getFeatures.return_value = mock_features
        
        collector = FeatureCollector(
            layer=mock_layer,
            primary_key_field="id"
        )
        
        batches, total = collector.collect_in_batches(batch_size=3)
        
        self.assertEqual(total, 10)
        self.assertEqual(len(batches), 4)  # 3, 3, 3, 1
        self.assertEqual(len(batches[0]), 3)
        self.assertEqual(len(batches[3]), 1)


class TestFormatIds(unittest.TestCase):
    """Test ID formatting for SQL."""
    
    def test_format_numeric(self):
        """Test formatting numeric IDs."""
        result = FeatureCollector.format_ids_for_sql([1, 2, 3], is_numeric=True)
        self.assertEqual(result, "1, 2, 3")
    
    def test_format_text(self):
        """Test formatting text IDs."""
        result = FeatureCollector.format_ids_for_sql(["a", "b", "c"], is_numeric=False)
        self.assertEqual(result, "'a', 'b', 'c'")
    
    def test_format_empty(self):
        """Test formatting empty list."""
        result = FeatureCollector.format_ids_for_sql([], is_numeric=True)
        self.assertEqual(result, "")


class TestRestoreSelection(unittest.TestCase):
    """Test selection restoration."""
    
    def test_restore_selection(self):
        """Test restoring layer selection."""
        mock_layer = Mock(spec=QgsVectorLayer)
        
        success = FeatureCollector.restore_layer_selection(
            layer=mock_layer,
            feature_ids=[1, 2, 3]
        )
        
        self.assertTrue(success)
        mock_layer.selectByIds.assert_called_once_with([1, 2, 3])
    
    def test_restore_no_layer(self):
        """Test with no layer."""
        success = FeatureCollector.restore_layer_selection(
            layer=None,
            feature_ids=[1, 2, 3]
        )
        
        self.assertFalse(success)
    
    def test_restore_empty_ids(self):
        """Test with empty IDs."""
        mock_layer = Mock(spec=QgsVectorLayer)
        
        success = FeatureCollector.restore_layer_selection(
            layer=mock_layer,
            feature_ids=[]
        )
        
        self.assertFalse(success)


if __name__ == '__main__':
    unittest.main()

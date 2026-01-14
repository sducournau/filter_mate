"""
Unit tests for AttributeFilterExecutor.

Tests extracted attribute filtering logic from FilterEngineTask.
Part of Phase E13 refactoring (January 2026).
"""

import unittest
from unittest.mock import Mock, MagicMock, patch

from qgis.core import QgsVectorLayer, QgsFeature, QgsField, QgsFields
from qgis.PyQt.QtCore import QVariant

from core.tasks.executors.attribute_filter_executor import AttributeFilterExecutor


class TestAttributeFilterExecutor(unittest.TestCase):
    """Test AttributeFilterExecutor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock layer
        self.layer = Mock(spec=QgsVectorLayer)
        self.layer.name.return_value = "test_layer"
        
        # Mock fields
        fields = QgsFields()
        fields.append(QgsField("id", QVariant.Int))
        fields.append(QgsField("name", QVariant.String))
        fields.append(QgsField("population", QVariant.Int))
        self.layer.fields.return_value = fields
        
        # Create executor
        self.executor = AttributeFilterExecutor(
            layer=self.layer,
            provider_type='postgresql',
            primary_key='id',
            table_name='test_table',
            old_subset=None,
            combine_operator='AND'
        )
    
    def test_initialization(self):
        """Test executor initialization."""
        self.assertEqual(self.executor.layer, self.layer)
        self.assertEqual(self.executor.provider_type, 'postgresql')
        self.assertEqual(self.executor.primary_key, 'id')
        self.assertEqual(self.executor.table_name, 'test_table')
        self.assertEqual(len(self.executor.field_names), 3)
    
    def test_process_qgis_expression_valid(self):
        """Test processing valid QGIS expression."""
        expression = "population > 1000"
        
        with patch.object(self.executor, '_qualify_field_names', return_value=" " + expression):
            with patch.object(self.executor, '_convert_to_postgis', return_value=expression):
                result, is_field = self.executor.process_qgis_expression(expression)
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)
    
    def test_process_qgis_expression_invalid_field_only(self):
        """Test rejection of field-only expression."""
        expression = "population"
        
        result, is_field = self.executor.process_qgis_expression(expression)
        
        self.assertIsNone(result)
        self.assertIsNone(is_field)
    
    def test_process_qgis_expression_no_comparison(self):
        """Test rejection of display expression without comparison."""
        expression = "coalesce(name, 'Unknown')"
        
        result, is_field = self.executor.process_qgis_expression(expression)
        
        self.assertIsNone(result)
        self.assertIsNone(is_field)
    
    def test_build_feature_id_expression_numeric(self):
        """Test building feature ID expression with numeric primary key."""
        # Create mock features
        features = []
        for i in range(1, 4):
            feature = Mock(spec=QgsFeature)
            feature.id.return_value = i
            feature.__getitem__ = Mock(return_value=i)
            features.append(feature)
        
        with patch('core.tasks.executors.attribute_filter_executor.build_feature_id_expression') as mock_build:
            mock_build.return_value = '"id" IN (1, 2, 3)'
            
            result = self.executor.build_feature_id_expression(features, is_numeric=True)
        
        self.assertIsNotNone(result)
        mock_build.assert_called_once()
    
    def test_build_feature_id_expression_with_ctid(self):
        """Test building expression with PostgreSQL ctid."""
        executor = AttributeFilterExecutor(
            layer=self.layer,
            provider_type='postgresql',
            primary_key='ctid',
            table_name='test_table'
        )
        
        features = []
        for i in range(1, 3):
            feature = Mock(spec=QgsFeature)
            feature.id.return_value = i
            features.append(feature)
        
        with patch('core.tasks.executors.attribute_filter_executor.build_feature_id_expression') as mock_build:
            mock_build.return_value = '"ctid" IN (1, 2)'
            
            result = executor.build_feature_id_expression(features, is_numeric=False)
        
        self.assertIsNotNone(result)
    
    def test_combine_with_old_subset_no_existing(self):
        """Test combination with no existing subset."""
        expression = "population > 1000"
        
        with patch('core.tasks.executors.attribute_filter_executor.combine_with_old_subset') as mock_combine:
            result = self.executor.combine_with_old_subset(expression)
        
        # Should return expression unchanged when no old_subset
        self.assertEqual(result, expression)
        mock_combine.assert_not_called()
    
    def test_combine_with_old_subset_existing(self):
        """Test combination with existing subset."""
        executor = AttributeFilterExecutor(
            layer=self.layer,
            provider_type='postgresql',
            primary_key='id',
            old_subset='status = "active"',
            combine_operator='AND'
        )
        
        expression = "population > 1000"
        
        with patch('core.tasks.executors.attribute_filter_executor.combine_with_old_subset') as mock_combine:
            mock_combine.return_value = '(status = "active") AND (population > 1000)'
            
            result = executor.combine_with_old_subset(expression)
        
        self.assertIsNotNone(result)
        mock_combine.assert_called_once()
    
    def test_try_v3_attribute_filter_no_bridge(self):
        """Test v3 filter attempt without TaskBridge."""
        result = self.executor.try_v3_attribute_filter("population > 1000")
        
        # Should return None (fallback) when no task_bridge
        self.assertIsNone(result)
    
    def test_try_v3_attribute_filter_field_only(self):
        """Test v3 filter skips field-only expressions."""
        executor = AttributeFilterExecutor(
            layer=self.layer,
            provider_type='postgresql',
            primary_key='id',
            task_bridge=Mock()
        )
        
        result = executor.try_v3_attribute_filter("population")
        
        # Should return None (fallback) for field-only expression
        self.assertIsNone(result)
    
    def test_try_v3_attribute_filter_success(self):
        """Test successful v3 filter execution."""
        # Create mock TaskBridge
        task_bridge = Mock()
        bridge_result = Mock()
        bridge_result.status = 'SUCCESS'
        bridge_result.success = True
        bridge_result.backend_used = 'postgresql'
        bridge_result.feature_count = 42
        bridge_result.execution_time_ms = 123.4
        bridge_result.feature_ids = [1, 2, 3]
        task_bridge.execute_attribute_filter.return_value = bridge_result
        
        executor = AttributeFilterExecutor(
            layer=self.layer,
            provider_type='postgresql',
            primary_key='id',
            task_bridge=task_bridge
        )
        
        with patch('core.tasks.executors.attribute_filter_executor.safe_set_subset_string') as mock_safe:
            mock_safe.return_value = True
            
            result = executor.try_v3_attribute_filter("population > 1000")
        
        self.assertTrue(result)
        task_bridge.execute_attribute_filter.assert_called_once()
        mock_safe.assert_called_once()
    
    def test_try_v3_attribute_filter_fallback(self):
        """Test v3 filter requesting fallback."""
        task_bridge = Mock()
        bridge_result = Mock()
        bridge_result.status = 'FALLBACK'
        bridge_result.error_message = 'Complex expression not supported'
        task_bridge.execute_attribute_filter.return_value = bridge_result
        
        executor = AttributeFilterExecutor(
            layer=self.layer,
            provider_type='postgresql',
            primary_key='id',
            task_bridge=task_bridge
        )
        
        result = executor.try_v3_attribute_filter("population > 1000")
        
        # Should return None (fallback to legacy)
        self.assertIsNone(result)
    
    def test_apply_filter(self):
        """Test applying filter to layer."""
        expression = '"id" IN (1, 2, 3)'
        
        with patch('core.tasks.executors.attribute_filter_executor.safe_set_subset_string') as mock_safe:
            mock_safe.return_value = True
            
            result = self.executor.apply_filter(expression)
        
        self.assertTrue(result)
        mock_safe.assert_called_once_with(self.layer, expression)


if __name__ == '__main__':
    unittest.main()

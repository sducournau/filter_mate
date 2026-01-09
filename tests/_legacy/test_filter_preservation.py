"""
Test filter preservation on layer switch and filter combination.

Tests that existing filters are automatically preserved when applying new filters,
preventing data loss during layer switching and multi-step filtering workflows.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestFilterPreservation(unittest.TestCase):
    """Test automatic filter preservation functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock QGIS dependencies
        self.mock_qgs_task = Mock()
        self.mock_qgs_vector_layer = Mock()
        self.mock_qgs_project = Mock()
        
        # Create mock layer with existing filter
        self.layer_with_filter = Mock()
        self.layer_with_filter.id.return_value = 'test_layer_1'
        self.layer_with_filter.name.return_value = 'Test Layer'
        self.layer_with_filter.subsetString.return_value = 'population > 5000'
        self.layer_with_filter.fields.return_value = []
        
        # Create mock layer without filter
        self.layer_no_filter = Mock()
        self.layer_no_filter.id.return_value = 'test_layer_2'
        self.layer_no_filter.name.return_value = 'Clean Layer'
        self.layer_no_filter.subsetString.return_value = ''
        self.layer_no_filter.fields.return_value = []
    
    @patch('modules.tasks.filter_task.logger')
    def test_combine_with_old_subset_default_and(self, mock_logger):
        """Test that AND operator is used by default when no operator specified"""
        from modules.tasks.filter_task import FilterEngineTask
        
        # Create task with minimal parameters
        task_parameters = {
            'infos': {
                'layer_provider_type': 'postgresql',
                'layer_schema': 'public',
                'layer_name': 'test_table',
                'layer_id': 'test_layer_1',
                'layer_geometry_field': 'geom',
                'primary_key_name': 'id'
            },
            'filtering': {
                'has_combine_operator': False,  # No operator specified
                'source_layer_combine_operator': None,
                'other_layers_combine_operator': None
            },
            'task': {}
        }
        
        # Mock task
        task = Mock(spec=FilterEngineTask)
        task.task_parameters = task_parameters
        task.source_layer = self.layer_with_filter
        task.param_source_old_subset = 'population > 5000'
        task.has_combine_operator = False
        
        # Call the actual method
        task._combine_with_old_subset = FilterEngineTask._combine_with_old_subset.__get__(task)
        task._get_source_combine_operator = FilterEngineTask._get_source_combine_operator.__get__(task)
        
        new_expression = 'area > 100'
        result = task._combine_with_old_subset(new_expression)
        
        # Verify AND operator used by default
        self.assertIn('population > 5000', result)
        self.assertIn('area > 100', result)
        self.assertIn('AND', result.upper())
        
        # Verify log message about default operator
        mock_logger.info.assert_called()
        log_message = str(mock_logger.info.call_args_list[-1])
        self.assertIn('AND par défaut', log_message)
    
    def test_combine_with_old_subset_explicit_or(self):
        """Test that explicit OR operator is respected"""
        from modules.tasks.filter_task import FilterEngineTask
        
        task_parameters = {
            'infos': {
                'layer_provider_type': 'postgresql',
                'layer_schema': 'public',
                'layer_name': 'test_table',
                'layer_id': 'test_layer_1',
                'layer_geometry_field': 'geom',
                'primary_key_name': 'id'
            },
            'filtering': {
                'has_combine_operator': True,
                'source_layer_combine_operator': 'OR',
                'other_layers_combine_operator': 'OR'
            },
            'task': {}
        }
        
        task = Mock(spec=FilterEngineTask)
        task.task_parameters = task_parameters
        task.source_layer = self.layer_with_filter
        task.param_source_old_subset = 'population > 5000'
        task.has_combine_operator = True
        task.param_source_layer_combine_operator = 'OR'
        
        task._combine_with_old_subset = FilterEngineTask._combine_with_old_subset.__get__(task)
        task._get_source_combine_operator = FilterEngineTask._get_source_combine_operator.__get__(task)
        
        new_expression = 'area > 100'
        result = task._combine_with_old_subset(new_expression)
        
        # Verify OR operator used
        self.assertIn('population > 5000', result)
        self.assertIn('area > 100', result)
        self.assertIn('OR', result.upper())
    
    def test_combine_with_old_subset_and_not(self):
        """Test AND NOT operator for exclusion filtering"""
        from modules.tasks.filter_task import FilterEngineTask
        
        task_parameters = {
            'infos': {
                'layer_provider_type': 'postgresql',
                'layer_schema': 'public',
                'layer_name': 'test_table',
                'layer_id': 'test_layer_1',
                'layer_geometry_field': 'geom',
                'primary_key_name': 'id'
            },
            'filtering': {
                'has_combine_operator': True,
                'source_layer_combine_operator': 'AND NOT',
                'other_layers_combine_operator': 'AND NOT'
            },
            'task': {}
        }
        
        task = Mock(spec=FilterEngineTask)
        task.task_parameters = task_parameters
        task.source_layer = self.layer_with_filter
        task.param_source_old_subset = 'population > 5000'
        task.has_combine_operator = True
        task.param_source_layer_combine_operator = 'AND NOT'
        
        task._combine_with_old_subset = FilterEngineTask._combine_with_old_subset.__get__(task)
        task._get_source_combine_operator = FilterEngineTask._get_source_combine_operator.__get__(task)
        
        new_expression = 'area > 100'
        result = task._combine_with_old_subset(new_expression)
        
        # Verify AND NOT operator used
        self.assertIn('population > 5000', result)
        self.assertIn('area > 100', result)
        self.assertIn('AND NOT', result.upper())
    
    def test_combine_with_old_subset_no_existing_filter(self):
        """Test that new expression is returned unchanged when no existing filter"""
        from modules.tasks.filter_task import FilterEngineTask
        
        task = Mock(spec=FilterEngineTask)
        task.param_source_old_subset = ''  # No existing filter
        task.has_combine_operator = False
        
        task._combine_with_old_subset = FilterEngineTask._combine_with_old_subset.__get__(task)
        task._get_source_combine_operator = FilterEngineTask._get_source_combine_operator.__get__(task)
        
        new_expression = 'area > 100'
        result = task._combine_with_old_subset(new_expression)
        
        # Verify expression unchanged
        self.assertEqual(result, new_expression)
        self.assertNotIn('AND', result)
    
    @patch('modules.tasks.filter_task.logger')
    def test_combine_with_old_filter_default_and(self, mock_logger):
        """Test distant layer filter combination with default AND"""
        from modules.tasks.filter_task import FilterEngineTask
        
        task = Mock(spec=FilterEngineTask)
        task.has_combine_operator = False
        task.param_other_layers_combine_operator = None
        
        task._combine_with_old_filter = FilterEngineTask._combine_with_old_filter.__get__(task)
        task._get_combine_operator = FilterEngineTask._get_combine_operator.__get__(task)
        
        new_expression = 'type = "commercial"'
        result = task._combine_with_old_filter(new_expression, self.layer_with_filter)
        
        # Verify AND used by default
        self.assertIn('population > 5000', result)
        self.assertIn('type = "commercial"', result)
        self.assertIn('AND', result.upper())
        
        # Verify log about preservation
        mock_logger.info.assert_called()
    
    def test_combine_with_old_filter_no_existing(self):
        """Test distant layer without existing filter"""
        from modules.tasks.filter_task import FilterEngineTask
        
        task = Mock(spec=FilterEngineTask)
        task.has_combine_operator = False
        
        task._combine_with_old_filter = FilterEngineTask._combine_with_old_filter.__get__(task)
        task._get_combine_operator = FilterEngineTask._get_combine_operator.__get__(task)
        
        new_expression = 'type = "commercial"'
        result = task._combine_with_old_filter(new_expression, self.layer_no_filter)
        
        # Verify expression unchanged
        self.assertEqual(result, new_expression)
    
    def test_filter_preservation_workflow(self):
        """Test complete workflow: geometric filter -> layer switch -> attribute filter"""
        from modules.tasks.filter_task import FilterEngineTask
        
        # Step 1: Layer has geometric filter (from polygon selection)
        layer = Mock()
        layer.id.return_value = 'parcelles_layer'
        layer.name.return_value = 'Parcelles'
        layer.subsetString.return_value = 'id IN (1, 5, 12, 45, 78)'
        layer.fields.return_value = []
        
        task_parameters = {
            'infos': {
                'layer_provider_type': 'spatialite',
                'layer_schema': '',
                'layer_name': 'parcelles',
                'layer_id': 'parcelles_layer',
                'layer_geometry_field': 'geom',
                'primary_key_name': 'id'
            },
            'filtering': {
                'has_combine_operator': False,
                'source_layer_combine_operator': None,
                'other_layers_combine_operator': None
            },
            'task': {}
        }
        
        task = Mock(spec=FilterEngineTask)
        task.task_parameters = task_parameters
        task.source_layer = layer
        task.param_source_old_subset = 'id IN (1, 5, 12, 45, 78)'
        task.has_combine_operator = False
        
        task._combine_with_old_subset = FilterEngineTask._combine_with_old_subset.__get__(task)
        task._get_source_combine_operator = FilterEngineTask._get_source_combine_operator.__get__(task)
        
        # Step 2: User switches layer (context preserved in param_source_old_subset)
        # Step 3: Apply attribute filter
        attribute_filter = 'population > 10000'
        result = task._combine_with_old_subset(attribute_filter)
        
        # Verify both filters present (intersection)
        self.assertIn('id IN (1, 5, 12, 45, 78)', result)
        self.assertIn('population > 10000', result)
        self.assertIn('AND', result.upper())
        
        # This would result in features that are:
        # - Inside the polygon selection (id IN ...)
        # - AND have population > 10000
        print(f"\n✓ Combined filter: {result}")
    
    def test_complex_where_clause_preservation(self):
        """Test preservation of complex WHERE clauses"""
        from modules.tasks.filter_task import FilterEngineTask
        
        # Complex existing filter
        complex_filter = "WHERE (field1 > 10) AND (field2 IN ('A', 'B'))"
        
        layer = Mock()
        layer.subsetString.return_value = complex_filter
        layer.fields.return_value = []
        
        task = Mock(spec=FilterEngineTask)
        task.param_source_old_subset = complex_filter
        task.has_combine_operator = False
        
        task._combine_with_old_subset = FilterEngineTask._combine_with_old_subset.__get__(task)
        task._get_source_combine_operator = FilterEngineTask._get_source_combine_operator.__get__(task)
        
        new_expression = 'field3 = "value"'
        result = task._combine_with_old_subset(new_expression)
        
        # Verify complex WHERE preserved
        self.assertIn('field1 > 10', result)
        self.assertIn('field2 IN', result)
        self.assertIn('field3 = "value"', result)
        self.assertIn('AND', result.upper())


class TestFilterPreservationIntegration(unittest.TestCase):
    """Integration tests for filter preservation across workflow"""
    
    def test_multi_layer_filter_preservation(self):
        """Test that all layers preserve filters in multi-layer operation"""
        # This would test the complete workflow from UI to backend
        # Requires more extensive mocking of QGIS environment
        pass
    
    def test_undo_redo_with_preserved_filters(self):
        """Test undo/redo works correctly with filter preservation"""
        # Test interaction between undo/redo system and filter preservation
        pass


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)

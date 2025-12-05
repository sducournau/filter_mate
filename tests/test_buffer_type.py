"""
Tests for buffer_type functionality in FilterMate
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestBufferTypeConfiguration(unittest.TestCase):
    """Test buffer_type configuration and mapping"""
    
    @patch('modules.appTasks.QgsTask')
    def test_param_buffer_type_initialization(self, mock_qgstask):
        """Test that param_buffer_type is initialized with default value"""
        from modules.appTasks import FilterTask
        
        task_params = {
            "filtering": {
                "has_buffer_value": False,
                "has_buffer_type": False,
                "buffer_type": "Round"
            }
        }
        
        task = FilterTask('test_task', task_params)
        
        # Verify default initialization
        self.assertEqual(task.param_buffer_type, 0, "Default buffer type should be 0 (Round)")
    
    @patch('modules.appTasks.QgsTask')
    @patch('modules.appTasks.logger')
    def test_buffer_type_mapping_round(self, mock_logger, mock_qgstask):
        """Test buffer_type mapping for Round"""
        from modules.appTasks import FilterTask
        
        task_params = {
            "filtering": {
                "has_buffer_value": True,
                "buffer_value": 10.0,
                "buffer_value_property": False,
                "buffer_value_expression": "",
                "has_buffer_type": True,
                "buffer_type": "Round"
            }
        }
        
        task = FilterTask('test_task', task_params)
        
        # Mock the expression check
        with patch('modules.appTasks.QgsExpression') as mock_expr:
            mock_expr.return_value.isField.return_value = False
            task.expression = "test_expression"
            task.param_source_old_subset = ""
            
            # Call the initialization method
            task._initialize_source_subset_and_buffer()
        
        # Verify Round maps to 0
        self.assertEqual(task.param_buffer_type, 0, "Round should map to END_CAP_STYLE=0")
    
    @patch('modules.appTasks.QgsTask')
    @patch('modules.appTasks.logger')
    def test_buffer_type_mapping_flat(self, mock_logger, mock_qgstask):
        """Test buffer_type mapping for Flat"""
        from modules.appTasks import FilterTask
        
        task_params = {
            "filtering": {
                "has_buffer_value": True,
                "buffer_value": 10.0,
                "buffer_value_property": False,
                "buffer_value_expression": "",
                "has_buffer_type": True,
                "buffer_type": "Flat"
            }
        }
        
        task = FilterTask('test_task', task_params)
        
        with patch('modules.appTasks.QgsExpression') as mock_expr:
            mock_expr.return_value.isField.return_value = False
            task.expression = "test_expression"
            task.param_source_old_subset = ""
            
            task._initialize_source_subset_and_buffer()
        
        # Verify Flat maps to 1
        self.assertEqual(task.param_buffer_type, 1, "Flat should map to END_CAP_STYLE=1")
    
    @patch('modules.appTasks.QgsTask')
    @patch('modules.appTasks.logger')
    def test_buffer_type_mapping_square(self, mock_logger, mock_qgstask):
        """Test buffer_type mapping for Square"""
        from modules.appTasks import FilterTask
        
        task_params = {
            "filtering": {
                "has_buffer_value": True,
                "buffer_value": 10.0,
                "buffer_value_property": False,
                "buffer_value_expression": "",
                "has_buffer_type": True,
                "buffer_type": "Square"
            }
        }
        
        task = FilterTask('test_task', task_params)
        
        with patch('modules.appTasks.QgsExpression') as mock_expr:
            mock_expr.return_value.isField.return_value = False
            task.expression = "test_expression"
            task.param_source_old_subset = ""
            
            task._initialize_source_subset_and_buffer()
        
        # Verify Square maps to 2
        self.assertEqual(task.param_buffer_type, 2, "Square should map to END_CAP_STYLE=2")
    
    @patch('modules.appTasks.QgsTask')
    @patch('modules.appTasks.logger')
    def test_buffer_type_default_when_not_configured(self, mock_logger, mock_qgstask):
        """Test buffer_type defaults to Round when has_buffer_type is False"""
        from modules.appTasks import FilterTask
        
        task_params = {
            "filtering": {
                "has_buffer_value": True,
                "buffer_value": 10.0,
                "buffer_value_property": False,
                "buffer_value_expression": "",
                "has_buffer_type": False,
                "buffer_type": "Square"  # Should be ignored when has_buffer_type=False
            }
        }
        
        task = FilterTask('test_task', task_params)
        
        with patch('modules.appTasks.QgsExpression') as mock_expr:
            mock_expr.return_value.isField.return_value = False
            task.expression = "test_expression"
            task.param_source_old_subset = ""
            
            task._initialize_source_subset_and_buffer()
        
        # Verify defaults to Round (0) when not configured
        self.assertEqual(task.param_buffer_type, 0, "Should default to Round (0) when has_buffer_type=False")
    
    @patch('modules.appTasks.QgsTask')
    @patch('modules.appTasks.logger')
    def test_buffer_type_invalid_value_defaults_to_round(self, mock_logger, mock_qgstask):
        """Test buffer_type defaults to Round for invalid values"""
        from modules.appTasks import FilterTask
        
        task_params = {
            "filtering": {
                "has_buffer_value": True,
                "buffer_value": 10.0,
                "buffer_value_property": False,
                "buffer_value_expression": "",
                "has_buffer_type": True,
                "buffer_type": "InvalidType"  # Invalid type
            }
        }
        
        task = FilterTask('test_task', task_params)
        
        with patch('modules.appTasks.QgsExpression') as mock_expr:
            mock_expr.return_value.isField.return_value = False
            task.expression = "test_expression"
            task.param_source_old_subset = ""
            
            task._initialize_source_subset_and_buffer()
        
        # Verify defaults to Round (0) for invalid value
        self.assertEqual(task.param_buffer_type, 0, "Should default to Round (0) for invalid buffer_type")
    
    @patch('modules.appTasks.QgsTask')
    @patch('modules.appTasks.processing')
    @patch('modules.appTasks.QgsProcessingContext')
    @patch('modules.appTasks.QgsProcessingFeedback')
    @patch('modules.appTasks.logger')
    def test_apply_qgis_buffer_uses_param_buffer_type(self, mock_logger, mock_feedback, 
                                                       mock_context, mock_processing, mock_qgstask):
        """Test that _apply_qgis_buffer uses self.param_buffer_type"""
        from modules.appTasks import FilterTask
        
        task_params = {
            "filtering": {
                "has_buffer_value": True,
                "buffer_value": 10.0,
                "buffer_value_property": False,
                "buffer_value_expression": "",
                "has_buffer_type": True,
                "buffer_type": "Square"
            }
        }
        
        task = FilterTask('test_task', task_params)
        task.param_buffer_type = 2  # Square
        
        # Mock layer
        mock_layer = Mock()
        mock_crs = Mock()
        mock_crs.isGeographic.return_value = False
        mock_crs.authid.return_value = "EPSG:3857"
        mock_crs.mapUnits.return_value = 0
        mock_layer.crs.return_value = mock_crs
        mock_layer.featureCount.return_value = 100
        mock_layer.geometryType.return_value = 0
        mock_layer.wkbType.return_value = 1
        
        # Mock processing.run
        mock_processing.run.return_value = {'OUTPUT': mock_layer}
        task.outputs = {}
        
        # Call the buffer method
        task._apply_qgis_buffer(mock_layer, 10.0)
        
        # Verify processing.run was called with correct END_CAP_STYLE
        mock_processing.run.assert_called()
        call_args = mock_processing.run.call_args
        
        # Check that alg_params contains END_CAP_STYLE=2 (Square)
        alg_params = call_args[0][1]
        self.assertEqual(alg_params['END_CAP_STYLE'], 2, 
                        "_apply_qgis_buffer should use param_buffer_type (Square=2)")


if __name__ == '__main__':
    unittest.main()

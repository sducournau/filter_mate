"""
Tests for VariablesPersistenceManager

Unit tests for the extracted variables management module.
Part of MIG-024 (God Class reduction).
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import json


class TestVariablesPersistenceManager(unittest.TestCase):
    """Tests for VariablesPersistenceManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock callbacks
        self.mock_connection = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_connection.cursor.return_value = self.mock_cursor
        self.mock_connection.__enter__ = Mock(return_value=self.mock_connection)
        self.mock_connection.__exit__ = Mock(return_value=False)
        
        self.mock_get_connection = Mock(return_value=self.mock_connection)
        self.mock_get_project_uuid = Mock(return_value="test-uuid-12345")
        self.mock_project_layers = {
            "layer_123": {
                "infos": {"is_already_subset": False},
                "exploring": {"explore_expression": ""},
                "filtering": {"layer_filter_expression": "population > 1000"}
            }
        }
        self.mock_get_project_layers = Mock(return_value=self.mock_project_layers)
        self.mock_return_typped_value = Mock(return_value=("test_value", str))
        
    def test_init_creates_manager(self):
        """Test manager initialization with callbacks."""
        from adapters.variables_manager import VariablesPersistenceManager
        
        manager = VariablesPersistenceManager(
            get_spatialite_connection=self.mock_get_connection,
            get_project_uuid=self.mock_get_project_uuid,
            get_project_layers=self.mock_get_project_layers,
            return_typped_value=self.mock_return_typped_value
        )
        
        self.assertIsNotNone(manager)
        self.assertEqual(manager._get_connection, self.mock_get_connection)
        self.assertEqual(manager._get_project_uuid, self.mock_get_project_uuid)
        
    def test_init_with_optional_callbacks(self):
        """Test manager initialization with optional callbacks."""
        from adapters.variables_manager import VariablesPersistenceManager
        
        mock_cancel = Mock()
        mock_layer_change = Mock(return_value=False)
        
        manager = VariablesPersistenceManager(
            get_spatialite_connection=self.mock_get_connection,
            get_project_uuid=self.mock_get_project_uuid,
            get_project_layers=self.mock_get_project_layers,
            return_typped_value=self.mock_return_typped_value,
            cancel_layer_tasks=mock_cancel,
            is_layer_change_in_progress=mock_layer_change
        )
        
        self.assertEqual(manager._cancel_layer_tasks, mock_cancel)
        self.assertEqual(manager._is_layer_change_in_progress, mock_layer_change)
        
    @patch('adapters.variables_manager.is_qgis_alive', return_value=False)
    def test_save_single_property_qgis_shutdown(self, mock_alive):
        """Test save_single_property returns False when QGIS is shutting down."""
        from adapters.variables_manager import VariablesPersistenceManager
        
        manager = VariablesPersistenceManager(
            get_spatialite_connection=self.mock_get_connection,
            get_project_uuid=self.mock_get_project_uuid,
            get_project_layers=self.mock_get_project_layers,
            return_typped_value=self.mock_return_typped_value
        )
        
        mock_layer = Mock()
        result = manager.save_single_property(
            layer=mock_layer,
            cursor=self.mock_cursor,
            key_group="filtering",
            key="test_key",
            value="test_value"
        )
        
        self.assertFalse(result)
        
    @patch('adapters.variables_manager.is_qgis_alive', return_value=True)
    @patch('adapters.variables_manager.is_valid_layer', return_value=False)
    def test_save_single_property_invalid_layer(self, mock_valid, mock_alive):
        """Test save_single_property returns False for invalid layer."""
        from adapters.variables_manager import VariablesPersistenceManager
        
        manager = VariablesPersistenceManager(
            get_spatialite_connection=self.mock_get_connection,
            get_project_uuid=self.mock_get_project_uuid,
            get_project_layers=self.mock_get_project_layers,
            return_typped_value=self.mock_return_typped_value
        )
        
        mock_layer = Mock()
        result = manager.save_single_property(
            layer=mock_layer,
            cursor=self.mock_cursor,
            key_group="filtering",
            key="test_key",
            value="test_value"
        )
        
        self.assertFalse(result)
        
    @patch('adapters.variables_manager.is_valid_layer', return_value=False)
    def test_save_variables_from_layer_invalid_layer(self, mock_valid):
        """Test save_variables_from_layer returns False for invalid layer."""
        from adapters.variables_manager import VariablesPersistenceManager
        
        manager = VariablesPersistenceManager(
            get_spatialite_connection=self.mock_get_connection,
            get_project_uuid=self.mock_get_project_uuid,
            get_project_layers=self.mock_get_project_layers,
            return_typped_value=self.mock_return_typped_value
        )
        
        mock_layer = Mock()
        result = manager.save_variables_from_layer(layer=mock_layer)
        
        self.assertFalse(result)
        
    @patch('adapters.variables_manager.is_valid_layer', return_value=True)
    def test_save_variables_layer_not_in_project_layers(self, mock_valid):
        """Test save_variables_from_layer returns False when layer not in PROJECT_LAYERS."""
        from adapters.variables_manager import VariablesPersistenceManager
        
        manager = VariablesPersistenceManager(
            get_spatialite_connection=self.mock_get_connection,
            get_project_uuid=self.mock_get_project_uuid,
            get_project_layers=Mock(return_value={}),  # Empty PROJECT_LAYERS
            return_typped_value=self.mock_return_typped_value
        )
        
        mock_layer = Mock()
        mock_layer.id.return_value = "unknown_layer"
        mock_layer.name.return_value = "Unknown"
        
        result = manager.save_variables_from_layer(layer=mock_layer)
        
        self.assertFalse(result)
        
    def test_save_variables_no_connection(self):
        """Test save_variables_from_layer returns False when no DB connection."""
        from adapters.variables_manager import VariablesPersistenceManager
        
        # Create patches
        with patch('adapters.variables_manager.is_valid_layer', return_value=True):
            manager = VariablesPersistenceManager(
                get_spatialite_connection=Mock(return_value=None),  # No connection
                get_project_uuid=self.mock_get_project_uuid,
                get_project_layers=self.mock_get_project_layers,
                return_typped_value=self.mock_return_typped_value
            )
            
            mock_layer = Mock()
            mock_layer.id.return_value = "layer_123"
            mock_layer.name.return_value = "Test Layer"
            
            result = manager.save_variables_from_layer(layer=mock_layer)
            
            self.assertFalse(result)
            
    @patch('adapters.variables_manager.is_valid_layer', return_value=False)
    def test_remove_variables_invalid_layer(self, mock_valid):
        """Test remove_variables_from_layer returns False for invalid layer."""
        from adapters.variables_manager import VariablesPersistenceManager
        
        manager = VariablesPersistenceManager(
            get_spatialite_connection=self.mock_get_connection,
            get_project_uuid=self.mock_get_project_uuid,
            get_project_layers=self.mock_get_project_layers,
            return_typped_value=self.mock_return_typped_value
        )
        
        mock_layer = Mock()
        result = manager.remove_variables_from_layer(layer=mock_layer)
        
        self.assertFalse(result)


class TestProjectSettingsSaver(unittest.TestCase):
    """Tests for ProjectSettingsSaver class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_connection = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_connection.cursor.return_value = self.mock_cursor
        
        self.mock_get_connection = Mock(return_value=self.mock_connection)
        self.mock_get_project_uuid = Mock(return_value="project-uuid-123")
        self.mock_config_data = {
            "CURRENT_PROJECT": {
                "filtering_mode": "single"
            }
        }
        self.mock_get_config_data = Mock(return_value=self.mock_config_data)
        
    def test_init_creates_saver(self):
        """Test ProjectSettingsSaver initialization."""
        from adapters.variables_manager import ProjectSettingsSaver
        
        saver = ProjectSettingsSaver(
            get_spatialite_connection=self.mock_get_connection,
            get_project_uuid=self.mock_get_project_uuid,
            get_config_data=self.mock_get_config_data,
            config_json_path="/path/to/config.json"
        )
        
        self.assertIsNotNone(saver)
        self.assertEqual(saver._config_json_path, "/path/to/config.json")
        self.assertIsNone(saver.project_file_name)
        self.assertIsNone(saver.project_file_path)
        
    def test_save_project_variables_no_config(self):
        """Test save_project_variables returns False when no config data."""
        from adapters.variables_manager import ProjectSettingsSaver
        
        saver = ProjectSettingsSaver(
            get_spatialite_connection=self.mock_get_connection,
            get_project_uuid=self.mock_get_project_uuid,
            get_config_data=Mock(return_value=None),
            config_json_path="/path/to/config.json"
        )
        
        result = saver.save_project_variables()
        
        self.assertFalse(result)
        
    def test_save_project_variables_no_connection(self):
        """Test save_project_variables returns False when no DB connection."""
        from adapters.variables_manager import ProjectSettingsSaver
        
        saver = ProjectSettingsSaver(
            get_spatialite_connection=Mock(return_value=None),
            get_project_uuid=self.mock_get_project_uuid,
            get_config_data=self.mock_get_config_data,
            config_json_path="/path/to/config.json"
        )
        
        result = saver.save_project_variables()
        
        self.assertFalse(result)
        
    def test_save_project_variables_updates_name(self):
        """Test save_project_variables updates project name."""
        from adapters.variables_manager import ProjectSettingsSaver
        
        saver = ProjectSettingsSaver(
            get_spatialite_connection=self.mock_get_connection,
            get_project_uuid=self.mock_get_project_uuid,
            get_config_data=self.mock_get_config_data,
            config_json_path="/tmp/test_config.json"
        )
        
        # Write mock config file first
        import os
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(self.mock_config_data, f)
            temp_path = f.name
        
        try:
            saver._config_json_path = temp_path
            saver.save_project_variables(name="test_project", project_absolute_path="/test/path")
            
            self.assertEqual(saver.project_file_name, "test_project")
            self.assertEqual(saver.project_file_path, "/test/path")
        finally:
            os.unlink(temp_path)


class TestVariablesManagerIntegration(unittest.TestCase):
    """Integration tests for variables manager module."""
    
    def test_module_imports(self):
        """Test that module can be imported."""
        try:
            from adapters.variables_manager import (
                VariablesPersistenceManager,
                ProjectSettingsSaver
            )
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import variables_manager module: {e}")
            
    def test_manager_interface_complete(self):
        """Test that VariablesPersistenceManager has all required methods."""
        from adapters.variables_manager import VariablesPersistenceManager
        
        required_methods = [
            'save_single_property',
            'save_variables_from_layer',
            'remove_variables_from_layer'
        ]
        
        for method in required_methods:
            self.assertTrue(
                hasattr(VariablesPersistenceManager, method),
                f"Missing method: {method}"
            )
            
    def test_saver_interface_complete(self):
        """Test that ProjectSettingsSaver has all required methods."""
        from adapters.variables_manager import ProjectSettingsSaver
        
        required_methods = ['save_project_variables']
        
        for method in required_methods:
            self.assertTrue(
                hasattr(ProjectSettingsSaver, method),
                f"Missing method: {method}"
            )


if __name__ == '__main__':
    unittest.main()

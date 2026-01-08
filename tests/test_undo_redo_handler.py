"""
Tests for UndoRedoHandler

Unit tests for the extracted undo/redo management module.
Part of MIG-024 (God Class reduction).
"""

import unittest
from unittest.mock import Mock, MagicMock, patch


class TestUndoRedoHandler(unittest.TestCase):
    """Tests for UndoRedoHandler class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock history manager
        self.mock_history_manager = MagicMock()
        self.mock_history = MagicMock()
        self.mock_history.can_undo.return_value = True
        self.mock_history.can_redo.return_value = True
        self.mock_history_manager.get_history.return_value = self.mock_history
        self.mock_history_manager.can_undo_global.return_value = True
        self.mock_history_manager.can_redo_global.return_value = True
        
        # Mock project layers
        self.mock_project_layers = {
            "layer_123": {
                "infos": {"is_already_subset": False},
                "filtering": {"layers_to_filter": []}
            }
        }
        self.mock_get_project_layers = Mock(return_value=self.mock_project_layers)
        
        # Mock project
        self.mock_project = MagicMock()
        self.mock_get_project = Mock(return_value=self.mock_project)
        
        # Mock iface
        self.mock_iface = MagicMock()
        self.mock_get_iface = Mock(return_value=self.mock_iface)
        
        # Mock refresh callback
        self.mock_refresh = Mock()
        
    def _create_handler(self):
        """Create handler with mocked dependencies."""
        from adapters.undo_redo_handler import UndoRedoHandler
        
        return UndoRedoHandler(
            history_manager=self.mock_history_manager,
            get_project_layers=self.mock_get_project_layers,
            get_project=self.mock_get_project,
            get_iface=self.mock_get_iface,
            refresh_layers_callback=self.mock_refresh
        )
        
    def test_init_creates_handler(self):
        """Test handler initialization."""
        handler = self._create_handler()
        self.assertIsNotNone(handler)
        
    def test_update_button_states_no_layer(self):
        """Test update_button_states with no current layer."""
        handler = self._create_handler()
        
        undo_btn = MagicMock()
        redo_btn = MagicMock()
        
        handler.update_button_states(
            current_layer=None,
            layers_to_filter=[],
            undo_button=undo_btn,
            redo_button=redo_btn
        )
        
        undo_btn.setEnabled.assert_called_with(False)
        redo_btn.setEnabled.assert_called_with(False)
        
    def test_update_button_states_layer_not_in_project(self):
        """Test update_button_states when layer not in PROJECT_LAYERS."""
        handler = self._create_handler()
        
        mock_layer = MagicMock()
        mock_layer.id.return_value = "unknown_layer"
        mock_layer.name.return_value = "Unknown"
        
        undo_btn = MagicMock()
        redo_btn = MagicMock()
        
        handler.update_button_states(
            current_layer=mock_layer,
            layers_to_filter=[],
            undo_button=undo_btn,
            redo_button=redo_btn
        )
        
        undo_btn.setEnabled.assert_called_with(False)
        redo_btn.setEnabled.assert_called_with(False)
        
    def test_update_button_states_with_history(self):
        """Test update_button_states enables buttons when history available."""
        handler = self._create_handler()
        
        mock_layer = MagicMock()
        mock_layer.id.return_value = "layer_123"
        mock_layer.name.return_value = "Test Layer"
        
        undo_btn = MagicMock()
        redo_btn = MagicMock()
        
        handler.update_button_states(
            current_layer=mock_layer,
            layers_to_filter=[],
            undo_button=undo_btn,
            redo_button=redo_btn
        )
        
        undo_btn.setEnabled.assert_called_with(True)
        redo_btn.setEnabled.assert_called_with(True)
        
    @patch('adapters.undo_redo_handler.is_layer_source_available', return_value=False)
    def test_handle_undo_invalid_layer(self, mock_available):
        """Test handle_undo returns False for invalid layer."""
        handler = self._create_handler()
        
        mock_layer = MagicMock()
        
        result = handler.handle_undo(
            source_layer=mock_layer,
            layers_to_filter=[],
            use_global=False
        )
        
        self.assertFalse(result)
        
    @patch('adapters.undo_redo_handler.is_layer_source_available', return_value=True)
    @patch('adapters.undo_redo_handler.safe_set_subset_string')
    def test_handle_undo_layer_only(self, mock_set_subset, mock_available):
        """Test handle_undo for single layer."""
        handler = self._create_handler()
        
        mock_layer = MagicMock()
        mock_layer.id.return_value = "layer_123"
        mock_layer.name.return_value = "Test Layer"
        
        # Mock previous state
        mock_state = MagicMock()
        mock_state.expression = "old_expression"
        mock_state.description = "Previous filter"
        self.mock_history.undo.return_value = mock_state
        
        result = handler.handle_undo(
            source_layer=mock_layer,
            layers_to_filter=[],
            use_global=False
        )
        
        self.assertTrue(result)
        mock_set_subset.assert_called_once()
        self.mock_refresh.assert_called_once_with(mock_layer)
        
    @patch('adapters.undo_redo_handler.is_layer_source_available', return_value=False)
    def test_handle_redo_invalid_layer(self, mock_available):
        """Test handle_redo returns False for invalid layer."""
        handler = self._create_handler()
        
        mock_layer = MagicMock()
        
        result = handler.handle_redo(
            source_layer=mock_layer,
            layers_to_filter=[],
            use_global=False
        )
        
        self.assertFalse(result)
        
    @patch('adapters.undo_redo_handler.is_layer_source_available', return_value=True)
    @patch('adapters.undo_redo_handler.safe_set_subset_string')
    def test_handle_redo_layer_only(self, mock_set_subset, mock_available):
        """Test handle_redo for single layer."""
        handler = self._create_handler()
        
        mock_layer = MagicMock()
        mock_layer.id.return_value = "layer_123"
        mock_layer.name.return_value = "Test Layer"
        
        # Mock next state
        mock_state = MagicMock()
        mock_state.expression = "next_expression"
        mock_state.description = "Next filter"
        self.mock_history.redo.return_value = mock_state
        
        result = handler.handle_redo(
            source_layer=mock_layer,
            layers_to_filter=[],
            use_global=False
        )
        
        self.assertTrue(result)
        mock_set_subset.assert_called_once()
        self.mock_refresh.assert_called_once_with(mock_layer)
        
    def test_handle_undo_no_layer(self):
        """Test handle_undo returns False when no layer provided."""
        handler = self._create_handler()
        
        result = handler.handle_undo(
            source_layer=None,
            layers_to_filter=[],
            use_global=False
        )
        
        self.assertFalse(result)
        
    def test_handle_redo_no_layer(self):
        """Test handle_redo returns False when no layer provided."""
        handler = self._create_handler()
        
        result = handler.handle_redo(
            source_layer=None,
            layers_to_filter=[],
            use_global=False
        )
        
        self.assertFalse(result)
        
    def test_clear_filter_history(self):
        """Test clear_filter_history clears history correctly."""
        handler = self._create_handler()
        
        mock_layer = MagicMock()
        mock_layer.id.return_value = "layer_123"
        
        handler.clear_filter_history(mock_layer)
        
        self.mock_history.clear.assert_called_once()
        self.mock_history_manager.clear_global_history.assert_called_once()
        
    def test_push_filter_to_history(self):
        """Test push_filter_to_history pushes state correctly."""
        handler = self._create_handler()
        
        mock_layer = MagicMock()
        mock_layer.id.return_value = "layer_123"
        mock_layer.subsetString.return_value = "population > 1000"
        
        # Mock get_or_create_history
        mock_new_history = MagicMock()
        mock_new_history._current_index = 0
        mock_new_history._states = [MagicMock()]
        self.mock_history_manager.get_or_create_history.return_value = mock_new_history
        
        task_parameters = {
            "task": {"layers": []}
        }
        
        handler.push_filter_to_history(
            source_layer=mock_layer,
            task_parameters=task_parameters,
            feature_count=100,
            provider_type="spatialite",
            layer_count=1
        )
        
        mock_new_history.push_state.assert_called_once()
        
    def test_push_filter_with_remote_layers(self):
        """Test push_filter_to_history with remote layers."""
        # Update PROJECT_LAYERS to include remote layer
        self.mock_project_layers["remote_layer_1"] = {
            "infos": {"is_already_subset": False},
            "filtering": {}
        }
        
        handler = self._create_handler()
        
        mock_layer = MagicMock()
        mock_layer.id.return_value = "layer_123"
        mock_layer.subsetString.return_value = "population > 1000"
        
        # Mock remote layer in project
        mock_remote = MagicMock()
        mock_remote.subsetString.return_value = "related_filter"
        mock_remote.featureCount.return_value = 50
        self.mock_project.mapLayer.return_value = mock_remote
        
        # Mock history
        mock_new_history = MagicMock()
        mock_new_history._current_index = 0
        mock_new_history._states = [MagicMock()]
        self.mock_history_manager.get_or_create_history.return_value = mock_new_history
        
        task_parameters = {
            "task": {
                "layers": [
                    {"layer_id": "remote_layer_1", "layer_name": "Remote1"}
                ]
            }
        }
        
        handler.push_filter_to_history(
            source_layer=mock_layer,
            task_parameters=task_parameters,
            feature_count=100,
            provider_type="spatialite",
            layer_count=2
        )
        
        # Should push global state
        self.mock_history_manager.push_global_state.assert_called_once()


class TestUndoRedoHandlerGlobal(unittest.TestCase):
    """Tests for global undo/redo operations."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock history manager with global state
        self.mock_history_manager = MagicMock()
        
        self.mock_global_state = MagicMock()
        self.mock_global_state.source_expression = "source_filter"
        self.mock_global_state.remote_layers = {
            "remote_layer_1": ("remote_filter_1", None),
            "remote_layer_2": ("remote_filter_2", None)
        }
        
        self.mock_history_manager.undo_global.return_value = self.mock_global_state
        self.mock_history_manager.redo_global.return_value = self.mock_global_state
        self.mock_history_manager.can_undo_global.return_value = True
        self.mock_history_manager.can_redo_global.return_value = True
        
        # Mock project layers
        self.mock_project_layers = {
            "layer_123": {
                "infos": {"is_already_subset": False},
                "filtering": {"layers_to_filter": ["remote_layer_1"]}
            },
            "remote_layer_1": {
                "infos": {"is_already_subset": False},
                "filtering": {}
            },
            "remote_layer_2": {
                "infos": {"is_already_subset": False},
                "filtering": {}
            }
        }
        self.mock_get_project_layers = Mock(return_value=self.mock_project_layers)
        
        # Mock project with layers
        self.mock_project = MagicMock()
        self.mock_remote_layer1 = MagicMock()
        self.mock_remote_layer2 = MagicMock()
        
        def mock_map_layer(layer_id):
            if layer_id == "remote_layer_1":
                return self.mock_remote_layer1
            elif layer_id == "remote_layer_2":
                return self.mock_remote_layer2
            return None
        
        self.mock_project.mapLayer = mock_map_layer
        self.mock_get_project = Mock(return_value=self.mock_project)
        
        # Mock iface
        self.mock_iface = MagicMock()
        self.mock_get_iface = Mock(return_value=self.mock_iface)
        
        # Mock refresh callback
        self.mock_refresh = Mock()
        
    def _create_handler(self):
        """Create handler with mocked dependencies."""
        from adapters.undo_redo_handler import UndoRedoHandler
        
        return UndoRedoHandler(
            history_manager=self.mock_history_manager,
            get_project_layers=self.mock_get_project_layers,
            get_project=self.mock_get_project,
            get_iface=self.mock_get_iface,
            refresh_layers_callback=self.mock_refresh
        )
        
    @patch('adapters.undo_redo_handler.is_layer_source_available', return_value=True)
    @patch('adapters.undo_redo_handler.safe_set_subset_string')
    def test_handle_global_undo(self, mock_set_subset, mock_available):
        """Test handle_undo with global undo."""
        handler = self._create_handler()
        
        mock_source_layer = MagicMock()
        mock_source_layer.id.return_value = "layer_123"
        mock_source_layer.name.return_value = "Source Layer"
        
        result = handler.handle_undo(
            source_layer=mock_source_layer,
            layers_to_filter=["remote_layer_1"],
            use_global=True
        )
        
        self.assertTrue(result)
        self.mock_history_manager.undo_global.assert_called_once()
        
    @patch('adapters.undo_redo_handler.is_layer_source_available', return_value=True)
    @patch('adapters.undo_redo_handler.safe_set_subset_string')
    def test_handle_global_redo(self, mock_set_subset, mock_available):
        """Test handle_redo with global redo."""
        handler = self._create_handler()
        
        mock_source_layer = MagicMock()
        mock_source_layer.id.return_value = "layer_123"
        mock_source_layer.name.return_value = "Source Layer"
        
        result = handler.handle_redo(
            source_layer=mock_source_layer,
            layers_to_filter=["remote_layer_1"],
            use_global=True
        )
        
        self.assertTrue(result)
        self.mock_history_manager.redo_global.assert_called_once()


class TestUndoRedoHandlerIntegration(unittest.TestCase):
    """Integration tests for undo/redo handler module."""
    
    def test_module_imports(self):
        """Test that module can be imported."""
        try:
            from adapters.undo_redo_handler import UndoRedoHandler
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import undo_redo_handler module: {e}")
            
    def test_handler_interface_complete(self):
        """Test that UndoRedoHandler has all required methods."""
        from adapters.undo_redo_handler import UndoRedoHandler
        
        required_methods = [
            'update_button_states',
            'handle_undo',
            'handle_redo',
            'clear_filter_history'
        ]
        
        for method in required_methods:
            self.assertTrue(
                hasattr(UndoRedoHandler, method),
                f"Missing method: {method}"
            )


if __name__ == '__main__':
    unittest.main()

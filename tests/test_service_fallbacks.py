"""
Unit tests for service fallbacks in FilterMateApp.

E7-S1: Test that FilterMate works without hexagonal architecture services.
Tests cover scenarios where HEXAGONAL_AVAILABLE = False or services fail to initialize.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from qgis.core import QgsVectorLayer, QgsProject
from qgis.PyQt.QtCore import Qt


class TestFilterUsableLayersFallback(unittest.TestCase):
    """Test _filter_usable_layers() fallback when LayerLifecycleService unavailable."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.plugin_dir = "/tmp/test_plugin"
    
    def test_fallback_returns_valid_layers(self):
        """Test fallback filters out invalid layers correctly."""
        # Import after mocking HEXAGONAL_AVAILABLE
        with patch('filter_mate_app.HEXAGONAL_AVAILABLE', False):
            from filter_mate_app import FilterMateApp
            
            app = FilterMateApp(self.plugin_dir)
            
            # Create mock layers
            valid_layer = Mock(spec=QgsVectorLayer)
            valid_layer.isValid.return_value = True
            
            invalid_layer = Mock(spec=QgsVectorLayer)
            invalid_layer.isValid.return_value = False
            
            missing_source_layer = Mock(spec=QgsVectorLayer)
            missing_source_layer.isValid.return_value = True
            
            # Mock is_layer_source_available
            with patch('filter_mate_app.is_layer_source_available') as mock_available:
                mock_available.side_effect = lambda layer: layer == valid_layer
                
                # Test filtering
                result = app._filter_usable_layers([valid_layer, invalid_layer, missing_source_layer])
                
                # Assertions
                self.assertEqual(len(result), 1, "Should return only valid layer")
                self.assertEqual(result[0], valid_layer)
    
    def test_fallback_shows_degraded_mode_warning(self):
        """Test fallback shows degraded mode warning once."""
        with patch('filter_mate_app.HEXAGONAL_AVAILABLE', False):
            from filter_mate_app import FilterMateApp
            
            app = FilterMateApp(self.plugin_dir)
            app._degraded_mode_warning_shown = False
            
            with patch('filter_mate_app.iface') as mock_iface:
                mock_iface.messageBar.return_value.pushWarning = Mock()
                
                # First call should show warning
                app._filter_usable_layers([])
                
                self.assertTrue(app._degraded_mode_warning_shown)
                mock_iface.messageBar().pushWarning.assert_called_once()
                
                # Second call should NOT show warning again
                mock_iface.messageBar().pushWarning.reset_mock()
                app._filter_usable_layers([])
                mock_iface.messageBar().pushWarning.assert_not_called()
    
    def test_fallback_handles_exceptions_gracefully(self):
        """Test fallback handles layer exceptions without crashing."""
        with patch('filter_mate_app.HEXAGONAL_AVAILABLE', False):
            from filter_mate_app import FilterMateApp
            
            app = FilterMateApp(self.plugin_dir)
            
            # Create layer that raises exception
            broken_layer = Mock(spec=QgsVectorLayer)
            broken_layer.isValid.side_effect = RuntimeError("SIP deleted")
            
            valid_layer = Mock(spec=QgsVectorLayer)
            valid_layer.isValid.return_value = True
            
            with patch('filter_mate_app.is_layer_source_available', return_value=True):
                # Should not raise exception
                result = app._filter_usable_layers([broken_layer, valid_layer])
                
                # Should skip broken layer and return valid one
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0], valid_layer)


class TestManageTaskFallback(unittest.TestCase):
    """Test manage_task() fallback when TaskOrchestrator fails."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.plugin_dir = "/tmp/test_plugin"
    
    def test_fallback_executes_on_orchestrator_exception(self):
        """Test fallback is called when TaskOrchestrator raises exception."""
        from filter_mate_app import FilterMateApp
        
        app = FilterMateApp(self.plugin_dir)
        
        # Mock orchestrator to raise exception
        app._task_orchestrator = Mock()
        app._task_orchestrator.dispatch_task.side_effect = Exception("Service failed")
        
        # Mock legacy dispatch
        app._legacy_dispatch_task = Mock()
        
        with patch('filter_mate_app.iface'):
            # Execute task
            app.manage_task('filter', None)
            
            # Verify fallback was called
            app._legacy_dispatch_task.assert_called_once_with('filter', None)
    
    def test_fallback_executes_when_orchestrator_unavailable(self):
        """Test fallback is used when TaskOrchestrator is None."""
        from filter_mate_app import FilterMateApp
        
        app = FilterMateApp(self.plugin_dir)
        app._task_orchestrator = None
        
        # Mock legacy dispatch
        app._legacy_dispatch_task = Mock()
        
        with patch('filter_mate_app.iface'):
            # Execute task
            app.manage_task('filter', None)
            
            # Verify fallback was called
            app._legacy_dispatch_task.assert_called_once_with('filter', None)
    
    def test_legacy_dispatch_task_handles_filter_operations(self):
        """Test _legacy_dispatch_task properly dispatches filter tasks."""
        from filter_mate_app import FilterMateApp
        
        app = FilterMateApp(self.plugin_dir)
        app._task_orchestrator = None
        
        # Mock methods
        app.get_task_parameters = Mock(return_value={'task': 'params'})
        app._execute_filter_task = Mock()
        
        with patch('filter_mate_app.iface'):
            # Execute filter task
            app._legacy_dispatch_task('filter', None)
            
            # Verify _execute_filter_task was called
            app._execute_filter_task.assert_called_once_with('filter', {'task': 'params'})
    
    def test_legacy_dispatch_task_handles_undo_redo(self):
        """Test _legacy_dispatch_task properly dispatches undo/redo."""
        from filter_mate_app import FilterMateApp
        
        app = FilterMateApp(self.plugin_dir)
        app.handle_undo = Mock()
        app.handle_redo = Mock()
        
        with patch('filter_mate_app.iface'):
            # Test undo
            app._legacy_dispatch_task('undo', None)
            app.handle_undo.assert_called_once()
            
            # Test redo
            app._legacy_dispatch_task('redo', None)
            app.handle_redo.assert_called_once()


class TestFilterCompletionFallback(unittest.TestCase):
    """Test filter_engine_task_completed() fallback when FilterResultHandler fails."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.plugin_dir = "/tmp/test_plugin"
    
    def test_fallback_executes_on_handler_exception(self):
        """Test fallback applies filter results when handler raises exception."""
        from filter_mate_app import FilterMateApp
        
        app = FilterMateApp(self.plugin_dir)
        
        # Mock handler to raise exception
        app._filter_result_handler = Mock()
        app._filter_result_handler.handle_task_completion.side_effect = Exception("Handler failed")
        
        # Mock required methods
        app.apply_subset_filter = Mock()
        app._refresh_layers_and_canvas = Mock()
        app.PROJECT = Mock()
        app.PROJECT.mapLayers.return_value.values.return_value = []
        
        # Mock source layer
        source_layer = Mock(spec=QgsVectorLayer)
        source_layer.featureCount.return_value = 100
        
        task_parameters = {
            'infos': {'layer_provider_type': 'spatialite'},
            'task': {'layers': []}
        }
        
        with patch('filter_mate_app.iface'):
            with patch('filter_mate_app.show_success_with_backend'):
                with patch('filter_mate_app.show_info'):
                    # Execute completion
                    app.filter_engine_task_completed('filter', source_layer, task_parameters)
                    
                    # Verify fallback methods were called
                    app.apply_subset_filter.assert_called_once_with('filter', source_layer)
                    app._refresh_layers_and_canvas.assert_called_once_with(source_layer)


class TestUndoRedoFallback(unittest.TestCase):
    """Test handle_undo() and handle_redo() fallbacks when UndoRedoHandler unavailable."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.plugin_dir = "/tmp/test_plugin"
    
    def test_undo_fallback_uses_history_manager(self):
        """Test undo fallback uses HistoryManager directly."""
        from filter_mate_app import FilterMateApp
        from core.services.history_service import FilterState
        
        app = FilterMateApp(self.plugin_dir)
        app._undo_redo_handler = None
        
        # Mock dockwidget and layer
        app.dockwidget = Mock()
        current_layer = Mock(spec=QgsVectorLayer)
        current_layer.id.return_value = "layer_1"
        app.dockwidget.current_layer = current_layer
        app.dockwidget._filtering_in_progress = False
        
        # Mock history manager
        mock_history = Mock()
        previous_state = FilterState(
            expression="old_filter",
            feature_count=50,
            description="Previous filter"
        )
        mock_history.can_undo.return_value = True
        mock_history.undo.return_value = previous_state
        
        app.history_manager.get_history = Mock(return_value=mock_history)
        app._refresh_layers_and_canvas = Mock()
        app.update_undo_redo_buttons = Mock()
        
        with patch('filter_mate_app.iface'):
            with patch('filter_mate_app.safe_set_subset_string') as mock_set:
                with patch('filter_mate_app.show_info'):
                    # Execute undo
                    app.handle_undo()
                    
                    # Verify fallback executed correctly
                    mock_history.undo.assert_called_once()
                    mock_set.assert_called_once_with(current_layer, "old_filter")
                    app._refresh_layers_and_canvas.assert_called_once_with(current_layer)
                    app.update_undo_redo_buttons.assert_called_once()
    
    def test_redo_fallback_uses_history_manager(self):
        """Test redo fallback uses HistoryManager directly."""
        from filter_mate_app import FilterMateApp
        from core.services.history_service import FilterState
        
        app = FilterMateApp(self.plugin_dir)
        app._undo_redo_handler = None
        
        # Mock dockwidget and layer
        app.dockwidget = Mock()
        current_layer = Mock(spec=QgsVectorLayer)
        current_layer.id.return_value = "layer_1"
        app.dockwidget.current_layer = current_layer
        app.dockwidget._filtering_in_progress = False
        
        # Mock history manager
        mock_history = Mock()
        next_state = FilterState(
            expression="new_filter",
            feature_count=75,
            description="Next filter"
        )
        mock_history.can_redo.return_value = True
        mock_history.redo.return_value = next_state
        
        app.history_manager.get_history = Mock(return_value=mock_history)
        app._refresh_layers_and_canvas = Mock()
        app.update_undo_redo_buttons = Mock()
        
        with patch('filter_mate_app.iface'):
            with patch('filter_mate_app.safe_set_subset_string') as mock_set:
                with patch('filter_mate_app.show_info'):
                    # Execute redo
                    app.handle_redo()
                    
                    # Verify fallback executed correctly
                    mock_history.redo.assert_called_once()
                    mock_set.assert_called_once_with(current_layer, "new_filter")
                    app._refresh_layers_and_canvas.assert_called_once_with(current_layer)
                    app.update_undo_redo_buttons.assert_called_once()


class TestSpatialiteConnectionFallback(unittest.TestCase):
    """Test get_spatialite_connection() fallback when DatasourceManager fails."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.plugin_dir = "/tmp/test_plugin"
    
    def test_fallback_creates_connection(self):
        """Test fallback uses spatialite_connect() directly."""
        from filter_mate_app import FilterMateApp
        
        app = FilterMateApp(self.plugin_dir)
        app._datasource_manager = None
        app.db_file_path = "/tmp/test.db"
        
        # Mock spatialite_connect
        with patch('filter_mate_app.spatialite_connect') as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn
            
            with patch('filter_mate_app.iface'):
                # Get connection
                result = app.get_spatialite_connection()
                
                # Verify fallback was used
                mock_connect.assert_called_once_with(app.db_file_path)
                self.assertEqual(result, mock_conn)
    
    def test_fallback_handles_connection_failure(self):
        """Test fallback returns None when connection fails."""
        from filter_mate_app import FilterMateApp
        
        app = FilterMateApp(self.plugin_dir)
        app._datasource_manager = None
        
        # Mock spatialite_connect to raise exception
        with patch('filter_mate_app.spatialite_connect') as mock_connect:
            mock_connect.side_effect = Exception("DB not found")
            
            with patch('filter_mate_app.iface'):
                # Get connection
                result = app.get_spatialite_connection()
                
                # Verify None returned
                self.assertIsNone(result)


class TestDegradedModeWarning(unittest.TestCase):
    """Test _show_degraded_mode_warning() displays warning once per session."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.plugin_dir = "/tmp/test_plugin"
    
    def test_warning_shown_only_once(self):
        """Test degraded mode warning is shown only once."""
        from filter_mate_app import FilterMateApp
        
        app = FilterMateApp(self.plugin_dir)
        
        with patch('filter_mate_app.iface') as mock_iface:
            mock_iface.messageBar.return_value.pushWarning = Mock()
            
            # First call should show warning
            app._show_degraded_mode_warning()
            self.assertTrue(app._degraded_mode_warning_shown)
            mock_iface.messageBar().pushWarning.assert_called_once()
            
            # Second call should NOT show warning
            mock_iface.messageBar().pushWarning.reset_mock()
            app._show_degraded_mode_warning()
            mock_iface.messageBar().pushWarning.assert_not_called()


if __name__ == '__main__':
    unittest.main()

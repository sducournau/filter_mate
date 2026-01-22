"""
Unit tests for TaskOrchestrator._is_filter_task() fix

FIX 2026-01-22: Export action not working due to incorrect task classification
"""

import pytest
from unittest.mock import Mock, MagicMock
from core.services.task_orchestrator import TaskOrchestrator


class TestTaskOrchestrator:
    """Test suite for TaskOrchestrator task classification."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create minimal TaskOrchestrator for testing."""
        # Create mock dependencies
        get_dockwidget = Mock(return_value=None)
        get_project_layers = Mock(return_value={})
        get_config_data = Mock(return_value={})
        get_project = Mock()
        check_reset_stale_flags = Mock()
        set_loading_flag = Mock()
        set_initializing_flag = Mock()
        get_task_parameters = Mock()
        handle_filter_task = Mock()
        handle_layer_task = Mock()
        handle_undo = Mock()
        handle_redo = Mock()
        force_reload_layers = Mock()
        handle_remove_all_layers = Mock()
        handle_project_initialization = Mock()
        
        return TaskOrchestrator(
            get_dockwidget=get_dockwidget,
            get_project_layers=get_project_layers,
            get_config_data=get_config_data,
            get_project=get_project,
            check_reset_stale_flags=check_reset_stale_flags,
            set_loading_flag=set_loading_flag,
            set_initializing_flag=set_initializing_flag,
            get_task_parameters=get_task_parameters,
            handle_filter_task=handle_filter_task,
            handle_layer_task=handle_layer_task,
            handle_undo=handle_undo,
            handle_redo=handle_redo,
            force_reload_layers=force_reload_layers,
            handle_remove_all_layers=handle_remove_all_layers,
            handle_project_initialization=handle_project_initialization
        )
    
    def test_filter_tasks_are_classified_correctly(self, orchestrator):
        """Test that filter tasks are correctly identified."""
        # Arrange & Act & Assert
        assert orchestrator._is_filter_task('filter') is True
        assert orchestrator._is_filter_task('unfilter') is True
        assert orchestrator._is_filter_task('reset') is True
    
    def test_export_is_not_a_filter_task(self, orchestrator):
        """
        CRITICAL TEST: Export must NOT be classified as a filter task.
        
        BUG FIXED: Previously, export was incorrectly classified as a filter task
        due to negative logic in _is_filter_task():
            return "layer" not in task_name and task_name not in (...)
        
        This caused export to be routed to _handle_filter_task() instead of
        having its own dedicated handler, breaking all export functionality.
        """
        # Arrange & Act
        result = orchestrator._is_filter_task('export')
        
        # Assert - THIS IS THE CRITICAL FIX
        assert result is False, (
            "REGRESSION: Export is being classified as a filter task again! "
            "This breaks all export functionality. "
            "Check _is_filter_task() implementation."
        )
    
    def test_layer_tasks_are_not_filter_tasks(self, orchestrator):
        """Test that layer management tasks are not filter tasks."""
        # Arrange & Act & Assert
        assert orchestrator._is_filter_task('add_layers') is False
        assert orchestrator._is_filter_task('remove_layers') is False
        assert orchestrator._is_filter_task('remove_all_layers') is False
    
    def test_undo_redo_are_not_filter_tasks(self, orchestrator):
        """Test that undo/redo are not filter tasks."""
        # Arrange & Act & Assert
        assert orchestrator._is_filter_task('undo') is False
        assert orchestrator._is_filter_task('redo') is False
    
    def test_project_tasks_are_not_filter_tasks(self, orchestrator):
        """Test that project tasks are not filter tasks."""
        # Arrange & Act & Assert
        assert orchestrator._is_filter_task('new_project') is False
        assert orchestrator._is_filter_task('project_read') is False
        assert orchestrator._is_filter_task('reload_layers') is False
    
    def test_whitelist_approach_is_explicit(self, orchestrator):
        """
        Test that _is_filter_task uses explicit whitelist (best practice).
        
        This test ensures we don't regress to negative logic like:
            "layer" not in task_name and task_name not in (...)
        
        Explicit whitelist is:
        - ✅ Easier to understand
        - ✅ Robust to new task additions
        - ✅ Self-documenting (you know EXACTLY what is a filter task)
        """
        # Arrange - All known filter tasks
        known_filter_tasks = {'filter', 'unfilter', 'reset'}
        
        # Arrange - All known non-filter tasks
        known_non_filter_tasks = {
            'export', 'undo', 'redo', 'reload_layers',
            'add_layers', 'remove_layers', 'remove_all_layers',
            'new_project', 'project_read'
        }
        
        # Act & Assert - Filter tasks
        for task in known_filter_tasks:
            assert orchestrator._is_filter_task(task) is True, (
                f"Filter task '{task}' should be classified as filter task"
            )
        
        # Act & Assert - Non-filter tasks
        for task in known_non_filter_tasks:
            assert orchestrator._is_filter_task(task) is False, (
                f"Non-filter task '{task}' should NOT be classified as filter task"
            )


class TestTaskOrchestratorExportDispatching:
    """Test export task routing in dispatch_task()."""
    
    @pytest.fixture
    def orchestrator_with_mocks(self):
        """Create orchestrator with mocked handlers."""
        get_dockwidget = Mock(return_value=None)
        get_project_layers = Mock(return_value={})
        get_config_data = Mock(return_value={})
        get_project = Mock()
        check_reset_stale_flags = Mock()
        set_loading_flag = Mock()
        set_initializing_flag = Mock()
        
        # Mock task parameter builder
        mock_params = {'task': {'layers': []}}
        get_task_parameters = Mock(return_value=mock_params)
        
        # Mock handlers
        handle_filter_task = Mock()
        handle_layer_task = Mock()
        handle_undo = Mock()
        handle_redo = Mock()
        force_reload_layers = Mock()
        handle_remove_all_layers = Mock()
        handle_project_initialization = Mock()
        
        orchestrator = TaskOrchestrator(
            get_dockwidget=get_dockwidget,
            get_project_layers=get_project_layers,
            get_config_data=get_config_data,
            get_project=get_project,
            check_reset_stale_flags=check_reset_stale_flags,
            set_loading_flag=set_loading_flag,
            set_initializing_flag=set_initializing_flag,
            get_task_parameters=get_task_parameters,
            handle_filter_task=handle_filter_task,
            handle_layer_task=handle_layer_task,
            handle_undo=handle_undo,
            handle_redo=handle_redo,
            force_reload_layers=force_reload_layers,
            handle_remove_all_layers=handle_remove_all_layers,
            handle_project_initialization=handle_project_initialization
        )
        
        return orchestrator, {
            'get_task_parameters': get_task_parameters,
            'handle_filter_task': handle_filter_task,
            'handle_layer_task': handle_layer_task
        }
    
    def test_export_task_calls_filter_task_handler(self, orchestrator_with_mocks):
        """
        Test that export task is routed to filter task handler.
        
        Export uses FilterEngineTask (like filter/unfilter/reset) so it must
        be routed to _handle_filter_task(), NOT _handle_layer_task().
        """
        # Arrange
        orchestrator, mocks = orchestrator_with_mocks
        
        # Act
        result = orchestrator.dispatch_task('export', data=None)
        
        # Assert
        assert result is True, "Export task should be dispatched successfully"
        
        # Verify correct handler was called
        mocks['handle_filter_task'].assert_called_once()
        mocks['handle_layer_task'].assert_not_called()
        
        # Verify task parameters were built
        mocks['get_task_parameters'].assert_called_once_with('export', None)
    
    def test_export_with_no_parameters_fails_gracefully(self, orchestrator_with_mocks):
        """Test that export fails gracefully when parameters are invalid."""
        # Arrange
        orchestrator, mocks = orchestrator_with_mocks
        mocks['get_task_parameters'].return_value = None  # Simulate failure
        
        # Act
        result = orchestrator.dispatch_task('export', data=None)
        
        # Assert
        assert result is False, "Export should fail when parameters are invalid"
        mocks['handle_filter_task'].assert_not_called()
        mocks['handle_layer_task'].assert_not_called()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

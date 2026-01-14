# -*- coding: utf-8 -*-
"""
Unit Tests for ActionDispatcher

Phase E13 Step 6: Tests for action dispatching and coordination.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass

# Import the module under test
import sys
import os

# Add parent path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

from core.tasks.dispatchers.action_dispatcher import (
    ActionDispatcher,
    ActionResult,
    ActionContext,
    TaskAction,
    BaseActionHandler,
    CallbackActionHandler,
    ExportActionHandler,
    create_dispatcher_for_task,
    create_action_context_from_task
)


class TestTaskAction(unittest.TestCase):
    """Tests for TaskAction enum."""
    
    def test_from_string_valid_lowercase(self):
        """Test converting lowercase action string."""
        self.assertEqual(TaskAction.from_string('filter'), TaskAction.FILTER)
        self.assertEqual(TaskAction.from_string('unfilter'), TaskAction.UNFILTER)
        self.assertEqual(TaskAction.from_string('reset'), TaskAction.RESET)
        self.assertEqual(TaskAction.from_string('export'), TaskAction.EXPORT)
    
    def test_from_string_valid_uppercase(self):
        """Test converting uppercase action string."""
        self.assertEqual(TaskAction.from_string('FILTER'), TaskAction.FILTER)
        self.assertEqual(TaskAction.from_string('UNFILTER'), TaskAction.UNFILTER)
    
    def test_from_string_invalid(self):
        """Test converting invalid action string."""
        self.assertIsNone(TaskAction.from_string('invalid'))
        self.assertIsNone(TaskAction.from_string(''))
        self.assertIsNone(TaskAction.from_string('delete'))


class TestActionResult(unittest.TestCase):
    """Tests for ActionResult dataclass."""
    
    def test_default_values(self):
        """Test default values are set correctly."""
        result = ActionResult(success=True, action='filter')
        
        self.assertTrue(result.success)
        self.assertEqual(result.action, 'filter')
        self.assertEqual(result.message, "")
        self.assertEqual(result.feature_count, 0)
        self.assertEqual(result.layers_processed, 0)
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.errors, [])
        self.assertEqual(result.elapsed_time, 0.0)
        self.assertEqual(result.metadata, {})
    
    def test_custom_values(self):
        """Test custom values are preserved."""
        result = ActionResult(
            success=True,
            action='filter',
            message="Filtered successfully",
            feature_count=100,
            layers_processed=5,
            warnings=["Warning 1"],
            errors=[],
            elapsed_time=1.5,
            metadata={"key": "value"}
        )
        
        self.assertEqual(result.message, "Filtered successfully")
        self.assertEqual(result.feature_count, 100)
        self.assertEqual(result.layers_processed, 5)
        self.assertEqual(result.warnings, ["Warning 1"])
        self.assertEqual(result.elapsed_time, 1.5)


class TestActionContext(unittest.TestCase):
    """Tests for ActionContext dataclass."""
    
    def test_minimal_context(self):
        """Test creating context with minimal parameters."""
        mock_layer = Mock()
        mock_layer.isValid.return_value = True
        
        context = ActionContext(
            task_parameters={},
            source_layer=mock_layer,
            layers={},
            layers_count=0
        )
        
        self.assertEqual(context.task_parameters, {})
        self.assertEqual(context.source_layer, mock_layer)
        self.assertEqual(context.layers_count, 0)
        self.assertIsNone(context.is_canceled)
        self.assertIsNone(context.set_progress)
    
    def test_full_context(self):
        """Test creating context with all parameters."""
        mock_layer = Mock()
        is_canceled_cb = Mock(return_value=False)
        set_progress_cb = Mock()
        queue_subset_cb = Mock()
        
        context = ActionContext(
            task_parameters={"task": {"key": "value"}},
            source_layer=mock_layer,
            layers={"postgresql": [], "ogr": []},
            layers_count=5,
            is_canceled=is_canceled_cb,
            set_progress=set_progress_cb,
            queue_subset_string=queue_subset_cb,
            current_predicates={"intersects": "ST_Intersects"},
            db_file_path="/path/to/db.sqlite",
            project_uuid="uuid-123",
            session_id="session-456"
        )
        
        self.assertEqual(context.layers_count, 5)
        self.assertEqual(context.db_file_path, "/path/to/db.sqlite")
        self.assertEqual(context.session_id, "session-456")


class TestActionDispatcher(unittest.TestCase):
    """Tests for ActionDispatcher class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.dispatcher = ActionDispatcher()
        
        # Create mock layer
        self.mock_layer = Mock()
        self.mock_layer.isValid.return_value = True
        self.mock_layer.name.return_value = "test_layer"
        
        # Create context
        self.context = ActionContext(
            task_parameters={"task": {}},
            source_layer=self.mock_layer,
            layers={},
            layers_count=1,
            is_canceled=Mock(return_value=False)
        )
    
    def test_register_handler(self):
        """Test registering a handler."""
        mock_handler = Mock()
        mock_handler.can_handle.return_value = True
        
        # Register for FILTER action
        self.dispatcher.register_for_action(TaskAction.FILTER, mock_handler)
        
        self.assertTrue(self.dispatcher.has_handler('filter'))
    
    def test_dispatch_unknown_action(self):
        """Test dispatching unknown action returns error."""
        result = self.dispatcher.dispatch('unknown_action', self.context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.action, 'unknown_action')
        self.assertIn('Unknown action', result.message)
    
    def test_dispatch_no_handler(self):
        """Test dispatching without registered handler."""
        result = self.dispatcher.dispatch('filter', self.context)
        
        self.assertFalse(result.success)
        self.assertIn('No handler', result.message)
    
    def test_dispatch_with_callback_handler(self):
        """Test dispatching with callback handler."""
        callback = Mock(return_value=True)
        handler = CallbackActionHandler(TaskAction.FILTER, callback)
        
        self.dispatcher.register_for_action(TaskAction.FILTER, handler)
        result = self.dispatcher.dispatch('filter', self.context)
        
        self.assertTrue(result.success)
        callback.assert_called_once()
    
    def test_dispatch_with_failing_callback(self):
        """Test dispatching with failing callback."""
        callback = Mock(return_value=False)
        handler = CallbackActionHandler(TaskAction.FILTER, callback)
        
        self.dispatcher.register_for_action(TaskAction.FILTER, handler)
        result = self.dispatcher.dispatch('filter', self.context)
        
        self.assertFalse(result.success)
    
    def test_dispatch_with_exception(self):
        """Test dispatching with callback that raises exception."""
        callback = Mock(side_effect=Exception("Test error"))
        handler = CallbackActionHandler(TaskAction.FILTER, callback)
        
        self.dispatcher.register_for_action(TaskAction.FILTER, handler)
        result = self.dispatcher.dispatch('filter', self.context)
        
        self.assertFalse(result.success)
        self.assertIn("Test error", str(result.errors))
    
    def test_dispatch_sets_elapsed_time(self):
        """Test that dispatch sets elapsed time."""
        callback = Mock(return_value=True)
        handler = CallbackActionHandler(TaskAction.FILTER, callback)
        
        self.dispatcher.register_for_action(TaskAction.FILTER, handler)
        result = self.dispatcher.dispatch('filter', self.context)
        
        self.assertGreaterEqual(result.elapsed_time, 0)
    
    def test_get_supported_actions(self):
        """Test getting list of supported actions."""
        callback = Mock(return_value=True)
        
        self.dispatcher.register_for_action(
            TaskAction.FILTER,
            CallbackActionHandler(TaskAction.FILTER, callback)
        )
        self.dispatcher.register_for_action(
            TaskAction.RESET,
            CallbackActionHandler(TaskAction.RESET, callback)
        )
        
        supported = self.dispatcher.get_supported_actions()
        
        self.assertIn('filter', supported)
        self.assertIn('reset', supported)
        self.assertNotIn('export', supported)
    
    def test_fallback_handler(self):
        """Test fallback handler for unregistered actions."""
        fallback_callback = Mock(return_value=True)
        fallback = CallbackActionHandler(TaskAction.FILTER, fallback_callback)
        fallback.can_handle = Mock(return_value=True)
        
        self.dispatcher.set_fallback(fallback)
        
        # Unfilter is not registered, should use fallback
        self.assertTrue(self.dispatcher.has_handler('unfilter'))
    
    def test_pre_dispatch_hook_abort(self):
        """Test pre-dispatch hook can abort execution."""
        callback = Mock(return_value=True)
        handler = CallbackActionHandler(TaskAction.FILTER, callback)
        self.dispatcher.register_for_action(TaskAction.FILTER, handler)
        
        # Add hook that aborts
        abort_hook = Mock(return_value=False)
        self.dispatcher.add_pre_dispatch_hook(abort_hook)
        
        result = self.dispatcher.dispatch('filter', self.context)
        
        self.assertFalse(result.success)
        self.assertIn("aborted", result.message)
        callback.assert_not_called()
    
    def test_post_dispatch_hook_called(self):
        """Test post-dispatch hook is called."""
        callback = Mock(return_value=True)
        handler = CallbackActionHandler(TaskAction.FILTER, callback)
        self.dispatcher.register_for_action(TaskAction.FILTER, handler)
        
        post_hook = Mock()
        self.dispatcher.add_post_dispatch_hook(post_hook)
        
        self.dispatcher.dispatch('filter', self.context)
        
        post_hook.assert_called_once()


class TestCallbackActionHandler(unittest.TestCase):
    """Tests for CallbackActionHandler class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_layer = Mock()
        self.mock_layer.isValid.return_value = True
        
        self.context = ActionContext(
            task_parameters={},
            source_layer=self.mock_layer,
            layers={},
            layers_count=1
        )
    
    def test_can_handle_correct_action(self):
        """Test handler responds to correct action."""
        handler = CallbackActionHandler(TaskAction.FILTER, Mock())
        
        self.assertTrue(handler.can_handle(TaskAction.FILTER))
        self.assertFalse(handler.can_handle(TaskAction.EXPORT))
    
    def test_execute_success(self):
        """Test successful execution."""
        callback = Mock(return_value=True)
        handler = CallbackActionHandler(TaskAction.FILTER, callback)
        
        result = handler.execute(self.context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.action, 'filter')
    
    def test_execute_failure(self):
        """Test failed execution."""
        callback = Mock(return_value=False)
        handler = CallbackActionHandler(TaskAction.UNFILTER, callback)
        
        result = handler.execute(self.context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.action, 'unfilter')
    
    def test_validate_with_custom_callback(self):
        """Test validation with custom callback."""
        validate_cb = Mock(return_value=(True, ""))
        handler = CallbackActionHandler(
            TaskAction.FILTER,
            Mock(),
            validate_callback=validate_cb
        )
        
        is_valid, msg = handler.validate(self.context)
        
        self.assertTrue(is_valid)
        validate_cb.assert_called_once()
    
    def test_default_validation_no_layer(self):
        """Test default validation fails without layer."""
        handler = CallbackActionHandler(TaskAction.FILTER, Mock())
        context = ActionContext(
            task_parameters={},
            source_layer=None,
            layers={},
            layers_count=0
        )
        
        is_valid, msg = handler.validate(context)
        
        self.assertFalse(is_valid)
        self.assertIn("No source layer", msg)


class TestExportActionHandler(unittest.TestCase):
    """Tests for ExportActionHandler class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_layer = Mock()
        self.mock_layer.isValid.return_value = True
    
    def test_validate_no_layers_to_export(self):
        """Test validation fails when no layers to export."""
        handler = ExportActionHandler(Mock())
        context = ActionContext(
            task_parameters={"task": {"EXPORTING": {"HAS_LAYERS_TO_EXPORT": False}}},
            source_layer=self.mock_layer,
            layers={},
            layers_count=0
        )
        
        is_valid, msg = handler.validate(context)
        
        self.assertFalse(is_valid)
        self.assertIn("No layers selected", msg)
    
    def test_validate_with_layers_to_export(self):
        """Test validation succeeds with layers to export."""
        handler = ExportActionHandler(Mock())
        context = ActionContext(
            task_parameters={"task": {"EXPORTING": {"HAS_LAYERS_TO_EXPORT": True}}},
            source_layer=self.mock_layer,
            layers={},
            layers_count=1
        )
        
        is_valid, msg = handler.validate(context)
        
        self.assertTrue(is_valid)
    
    def test_execute_success(self):
        """Test successful export execution."""
        callback = Mock(return_value=True)
        handler = ExportActionHandler(callback)
        context = ActionContext(
            task_parameters={"task": {"EXPORTING": {"HAS_LAYERS_TO_EXPORT": True}}},
            source_layer=self.mock_layer,
            layers={},
            layers_count=3
        )
        
        result = handler.execute(context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.action, 'export')


class TestFactoryFunctions(unittest.TestCase):
    """Tests for factory functions."""
    
    def test_create_dispatcher_for_task(self):
        """Test creating dispatcher from task."""
        mock_task = Mock()
        mock_task.execute_filtering = Mock(return_value=True)
        mock_task.execute_unfiltering = Mock(return_value=True)
        mock_task.execute_reseting = Mock(return_value=True)
        mock_task.execute_exporting = Mock(return_value=True)
        
        dispatcher = create_dispatcher_for_task(mock_task)
        
        self.assertTrue(dispatcher.has_handler('filter'))
        self.assertTrue(dispatcher.has_handler('unfilter'))
        self.assertTrue(dispatcher.has_handler('reset'))
        self.assertTrue(dispatcher.has_handler('export'))
    
    def test_create_action_context_from_task(self):
        """Test creating context from task."""
        mock_layer = Mock()
        mock_layer.isValid.return_value = True
        
        mock_task = Mock()
        mock_task.task_parameters = {"task": {"key": "value"}}
        mock_task.source_layer = mock_layer
        mock_task.layers = {"ogr": []}
        mock_task.layers_count = 2
        mock_task.isCanceled = Mock(return_value=False)
        mock_task.setProgress = Mock()
        mock_task._queue_subset_string = Mock()
        mock_task.current_predicates = {"intersects": "ST_Intersects"}
        mock_task.db_file_path = "/path/db.sqlite"
        mock_task.project_uuid = "uuid"
        mock_task.session_id = "session"
        
        context = create_action_context_from_task(mock_task)
        
        self.assertEqual(context.source_layer, mock_layer)
        self.assertEqual(context.layers_count, 2)
        self.assertEqual(context.db_file_path, "/path/db.sqlite")


if __name__ == '__main__':
    unittest.main()

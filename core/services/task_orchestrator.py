"""
Task Orchestrator Service

v4.1: Extracted from FilterMateApp.manage_task() as part of God Class decomposition.

This service orchestrates all FilterMate task execution, handling:
- Task dispatching and routing
- Task queuing for concurrent operations
- Task state management and cancellation
- Controller delegation (Strangler Fig pattern)

The orchestrator acts as a central dispatcher, routing tasks to appropriate
handlers while maintaining backward compatibility with legacy code paths.
"""

from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass
from enum import Enum
import weakref
import logging

from qgis.PyQt.QtCore import QTimer, Qt
from qgis.core import QgsApplication, QgsProject, QgsVectorLayer, QgsTask
import sip

logger = logging.getLogger('FilterMate')


class TaskStatus(Enum):
    """Status of a task in the orchestrator."""
    NOT_STARTED = "not_started"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskContext:
    """Context for task execution."""
    task_name: str
    data: Any = None
    retry_count: int = 0
    max_retries: int = 10
    deferred: bool = False


class StabilityConstants:
    """Constants for stability-related behavior."""
    MAX_ADD_LAYERS_QUEUE = 10
    LAYER_RETRY_DELAY_MS = 500
    WIDGET_INIT_DELAY_MS = 500
    STALE_FLAG_TIMEOUT_SECONDS = 60


class TaskOrchestrator:
    """
    Central task orchestration service for FilterMate.
    
    Manages task lifecycle from dispatch to completion, including:
    - Task routing to appropriate handlers
    - Concurrent task management and queuing
    - State flag management for stability
    - Controller delegation for hexagonal architecture migration
    
    This class replaces the monolithic manage_task() method in FilterMateApp.
    """
    
    # Task descriptions for user-facing messages
    TASK_DESCRIPTIONS = {
        'filter': 'Filtering data',
        'unfilter': 'Unfiltering data',
        'reset': 'Reseting data',
        'export': 'Exporting data',
        'undo': 'Undo filter',
        'redo': 'Redo filter',
        'add_layers': 'Adding layers',
        'remove_layers': 'Removing layers',
        'remove_all_layers': 'Removing all layers',
        'new_project': 'New project',
        'project_read': 'Existing project loaded',
        'reload_layers': 'Reloading layers'
    }
    
    def __init__(
        self,
        get_dockwidget: Callable,
        get_project_layers: Callable[[], Dict],
        get_config_data: Callable[[], Dict],
        get_project: Callable[[], QgsProject],
        check_reset_stale_flags: Callable,
        set_loading_flag: Callable[[bool], None],
        set_initializing_flag: Callable[[bool], None],
        get_task_parameters: Callable[[str, Any], Optional[Dict]],
        handle_filter_task: Callable[[str, Dict], None],
        handle_layer_task: Callable[[str, Dict], None],
        handle_undo: Callable,
        handle_redo: Callable,
        force_reload_layers: Callable,
        handle_remove_all_layers: Callable,
        handle_project_initialization: Callable[[str], None],
    ):
        """
        Initialize TaskOrchestrator with dependency injection.
        
        Args:
            get_dockwidget: Callback to get current dockwidget instance
            get_project_layers: Callback to get PROJECT_LAYERS dict
            get_config_data: Callback to get CONFIG_DATA dict
            get_project: Callback to get QgsProject instance
            check_reset_stale_flags: Callback to check and reset stale flags
            set_loading_flag: Callback to set loading flag
            set_initializing_flag: Callback to set initializing flag
            get_task_parameters: Callback to build task parameters
            handle_filter_task: Callback to execute filter/unfilter/reset tasks
            handle_layer_task: Callback to execute layer management tasks
            handle_undo: Callback for undo operation
            handle_redo: Callback for redo operation
            force_reload_layers: Callback for reload_layers task
            handle_remove_all_layers: Callback for remove_all_layers task
            handle_project_initialization: Callback for project_read/new_project
        """
        self._get_dockwidget = get_dockwidget
        self._get_project_layers = get_project_layers
        self._get_config_data = get_config_data
        self._get_project = get_project
        self._check_reset_stale_flags = check_reset_stale_flags
        self._set_loading_flag = set_loading_flag
        self._set_initializing_flag = set_initializing_flag
        self._get_task_parameters = get_task_parameters
        self._handle_filter_task = handle_filter_task
        self._handle_layer_task = handle_layer_task
        self._handle_undo = handle_undo
        self._handle_redo = handle_redo
        self._force_reload_layers = force_reload_layers
        self._handle_remove_all_layers = handle_remove_all_layers
        self._handle_project_initialization = handle_project_initialization
        
        # State management
        self._pending_add_layers_tasks = 0
        self._add_layers_queue: List[Any] = []
        self._processing_queue = False
        self._widgets_ready = False
        self._filter_retry_count: Dict[str, int] = {}
        self._initializing_project = False
        self._loading_new_project = False
        
        # Controller integration for hexagonal migration
        self._controller_integration = None
        
        logger.info("TaskOrchestrator initialized")
    
    @property
    def dockwidget(self):
        """Get current dockwidget instance."""
        return self._get_dockwidget()
    
    @property
    def widgets_ready(self) -> bool:
        """Check if widgets are ready for operations."""
        return self._widgets_ready
    
    @widgets_ready.setter
    def widgets_ready(self, value: bool):
        """Set widgets ready state."""
        self._widgets_ready = value
    
    def dispatch_task(self, task_name: str, data: Any = None) -> bool:
        """
        Dispatch a task for execution.
        
        Central entry point for all task execution. Routes tasks to appropriate
        handlers based on task type.
        
        Args:
            task_name: Name of the task to execute (must be in TASK_DESCRIPTIONS)
            data: Task-specific data (layers, parameters, etc.)
            
        Returns:
            True if task was dispatched successfully, False otherwise
            
        Raises:
            AssertionError: If task_name is not recognized
        """
        assert task_name in self.TASK_DESCRIPTIONS, f"Unknown task: {task_name}"
        
        logger.info("=" * 60)
        logger.info(f"TaskOrchestrator.dispatch_task: RECEIVED task_name='{task_name}'")
        self._log_current_state()
        logger.info("=" * 60)
        
        # Check and reset stale flags before processing
        self._check_reset_stale_flags()
        
        # Handle task based on type
        if task_name == 'remove_all_layers':
            self._handle_remove_all_layers()
            return True
        
        if task_name in ('project_read', 'new_project'):
            self._handle_project_initialization(task_name)
            return True
        
        if task_name == 'undo':
            self._handle_undo()
            return True
        
        if task_name == 'redo':
            self._handle_redo()
            return True
        
        if task_name == 'reload_layers':
            self._force_reload_layers()
            return True
        
        # FIX 2026-01-22: Handle export task explicitly
        if task_name == 'export':
            logger.info("TaskOrchestrator: Dispatching export task")
            # Get task parameters
            task_parameters = self._get_task_parameters(task_name, data)
            if task_parameters is None:
                logger.warning("Export task aborted - no valid parameters")
                return False
            # Export is a filter-type task (uses FilterEngineTask)
            self._handle_filter_task(task_name, task_parameters)
            return True
        
        # Check for project initialization skip
        if task_name == 'add_layers' and self._initializing_project:
            logger.debug("Skipping add_layers - project initialization in progress")
            return False
        
        # Handle add_layers queuing
        if task_name == 'add_layers':
            return self._dispatch_add_layers(data)
        
        # Check dockwidget readiness for non-layer tasks
        if not self._check_dockwidget_ready(task_name, data):
            return False
        
        # Sync state from dockwidget if available
        self._sync_from_dockwidget()
        
        # Try controller delegation for filter tasks (Strangler Fig pattern)
        if task_name in ('filter', 'unfilter', 'reset'):
            if self._try_delegate_to_controller(task_name, data):
                logger.info(f"v4.1: Task '{task_name}' delegated to controller")
                return True
        
        # Get task parameters
        task_parameters = self._get_task_parameters(task_name, data)
        if task_parameters is None:
            logger.warning(f"Task '{task_name}' aborted - no valid task parameters")
            return False
        
        # Route to appropriate handler
        if self._is_filter_task(task_name):
            self._handle_filter_task(task_name, task_parameters)
        else:
            self._handle_layer_task(task_name, task_parameters)
        
        return True
    
    def _dispatch_add_layers(self, data: Any) -> bool:
        """
        Handle add_layers task with queuing support.
        
        Args:
            data: Layers to add
            
        Returns:
            True if task was dispatched or queued, False otherwise
        """
        max_queue = StabilityConstants.MAX_ADD_LAYERS_QUEUE
        
        if self._pending_add_layers_tasks > 0:
            if len(self._add_layers_queue) >= max_queue:
                logger.warning(f"⚠️ STABILITY: add_layers queue full ({max_queue}), dropping oldest")
                self._add_layers_queue.pop(0)
            
            logger.info(f"Queueing add_layers - {self._pending_add_layers_tasks} task(s) in progress")
            self._add_layers_queue.append(data)
            return True
        
        self._pending_add_layers_tasks += 1
        logger.debug(f"Starting add_layers task (pending: {self._pending_add_layers_tasks})")
        
        # Continue with task parameter building and execution
        task_parameters = self._get_task_parameters('add_layers', data)
        if task_parameters:
            self._handle_layer_task('add_layers', task_parameters)
            return True
        return False
    
    def _check_dockwidget_ready(self, task_name: str, data: Any) -> bool:
        """
        Check if dockwidget is ready for task execution.
        
        Args:
            task_name: Task being executed
            data: Task data
            
        Returns:
            True if ready, False if deferred
        """
        # Some tasks can run without full initialization
        if task_name in ('remove_all_layers', 'project_read', 'new_project', 'add_layers'):
            return True
        
        dockwidget = self.dockwidget
        if dockwidget is None or not getattr(dockwidget, 'widgets_initialized', False):
            logger.warning(f"Task '{task_name}' called before dockwidget init, deferring...")
            self._defer_task(task_name, data, delay_ms=StabilityConstants.WIDGET_INIT_DELAY_MS)
            return False
        
        # For filter tasks, additional readiness check
        if task_name in ('filter', 'unfilter', 'reset'):
            if not self._is_dockwidget_ready_for_filtering():
                retry_key = f"{task_name}_{id(data)}"
                retry_count = self._filter_retry_count.get(retry_key, 0)
                
                if retry_count >= 10:
                    logger.error(f"❌ GIVING UP: Task '{task_name}' after {retry_count} retries")
                    self._filter_retry_count[retry_key] = 0
                    return self._try_emergency_fallback(task_name, data)
                
                self._filter_retry_count[retry_key] = retry_count + 1
                logger.warning(f"Task '{task_name}' waiting for widgets (attempt {retry_count + 1}/10)")
                self._defer_task(task_name, data, delay_ms=500)
                return False
            
            # Success - reset counter
            retry_key = f"{task_name}_{id(data)}"
            self._filter_retry_count[retry_key] = 0
        
        return True
    
    def _is_dockwidget_ready_for_filtering(self) -> bool:
        """
        Check if dockwidget is fully ready for filtering operations.
        
        Returns:
            True if ready, False otherwise
        """
        dockwidget = self.dockwidget
        if dockwidget is None:
            return False
        
        # Check signal-based flag with fallback
        if not self._widgets_ready:
            if getattr(dockwidget, 'widgets_initialized', False):
                logger.warning("⚠️ FALLBACK: Syncing widgets_ready from dockwidget")
                self._widgets_ready = True
            else:
                return False
        
        # Check layer combobox
        if hasattr(dockwidget, 'cbb_layers') and dockwidget.cbb_layers:
            if dockwidget.cbb_layers.count() == 0:
                return False
        
        # Check current layer
        if dockwidget.current_layer is None:
            return False
        
        return True
    
    def _try_emergency_fallback(self, task_name: str, data: Any) -> bool:
        """
        Try emergency fallback when widgets won't initialize.
        
        Args:
            task_name: Task name
            data: Task data
            
        Returns:
            True if fallback worked
        """
        dockwidget = self.dockwidget
        if dockwidget and getattr(dockwidget, 'widgets_initialized', False):
            logger.warning("⚠️ EMERGENCY: Forcing _widgets_ready = True")
            self._widgets_ready = True
            self._defer_task(task_name, data, delay_ms=100)
            return True
        return False
    
    def _defer_task(self, task_name: str, data: Any, delay_ms: int = 500):
        """
        Defer task execution with a timer.
        
        Args:
            task_name: Task to defer
            data: Task data
            delay_ms: Delay in milliseconds
        """
        weak_self = weakref.ref(self)
        captured_name = task_name
        captured_data = data
        
        def safe_retry():
            strong_self = weak_self()
            if strong_self is not None:
                strong_self.dispatch_task(captured_name, captured_data)
        
        QTimer.singleShot(delay_ms, safe_retry)
    
    def _sync_from_dockwidget(self):
        """Sync state from dockwidget."""
        dockwidget = self.dockwidget
        if dockwidget is not None:
            # Update project layers and config from dockwidget
            # This is handled by callbacks in the actual implementation
            pass
    
    def _log_current_state(self):
        """Log current state for debugging."""
        dockwidget = self.dockwidget
        if dockwidget and hasattr(dockwidget, 'current_layer'):
            try:
                current_layer = dockwidget.current_layer
                if current_layer:
                    import sip
                    if not sip.isdeleted(current_layer):
                        logger.info(f"  current_layer: {current_layer.name()}")
                        logger.info(f"  current_exploring_groupbox: {getattr(dockwidget, 'current_exploring_groupbox', 'unknown')}")
            except RuntimeError:
                logger.debug("  current_layer: <deleted>")
    
    def _is_filter_task(self, task_name: str) -> bool:
        """
        Check if task is a filter-type task.
        
        FIX 2026-01-22: Use explicit whitelist instead of negative logic.
        Previous implementation incorrectly classified 'export' as a filter task.
        """
        filter_tasks = ('filter', 'unfilter', 'reset')
        return task_name in filter_tasks
    
    def _try_delegate_to_controller(self, task_name: str, data: Any = None) -> bool:
        """
        Try to delegate filter task to hexagonal architecture controllers.
        
        Implements the Strangler Fig pattern: new code path via controllers
        with automatic fallback to legacy if delegation fails.
        
        Args:
            task_name: Name of the task ('filter', 'unfilter', 'reset')
            data: Optional task data
            
        Returns:
            True if delegation succeeded, False to use legacy path
        """
        dockwidget = self.dockwidget
        if dockwidget is None:
            return False
        
        integration = getattr(dockwidget, '_controller_integration', None)
        if integration is None or not integration.enabled:
            return False
        
        try:
            if task_name == 'filter':
                integration.sync_from_dockwidget()
                success = integration.delegate_execute_filter()
                if success:
                    logger.info("v4.1: Filter executed via FilteringController")
                    return True
            elif task_name == 'unfilter':
                # v4.0: Delegate to controller's execute_unfilter()
                integration.sync_from_dockwidget()
                success = integration.delegate_execute_unfilter()
                if success:
                    logger.info("v4.0: Unfilter executed via FilteringController")
                    return True
                logger.debug("v4.0: Controller delegation for 'unfilter' returned False, using legacy")
            elif task_name == 'reset':
                # v4.0: Delegate to controller's execute_reset_filters()
                integration.sync_from_dockwidget()
                success = integration.delegate_execute_reset()
                if success:
                    logger.info("v4.0: Reset executed via FilteringController")
                    return True
                logger.debug("v4.0: Controller delegation for 'reset' returned False, using legacy")
            
            return False
            
        except Exception as e:
            logger.warning(f"v4.1: Controller delegation failed: {e}")
            return False
    
    # ========================================
    # QUEUE MANAGEMENT
    # ========================================
    
    def process_add_layers_queue(self):
        """
        Process queued add_layers operations.
        
        Called after a previous add_layers task completes.
        """
        if self._processing_queue:
            return
        
        if not self._add_layers_queue:
            return
        
        if self._pending_add_layers_tasks > 0:
            return
        
        self._processing_queue = True
        try:
            data = self._add_layers_queue.pop(0)
            logger.info(f"Processing queued add_layers ({len(self._add_layers_queue)} remaining)")
            self.dispatch_task('add_layers', data)
        finally:
            self._processing_queue = False
    
    def decrement_pending_tasks(self, task_name: str):
        """
        Decrement pending task counter after completion.
        
        Args:
            task_name: Completed task name
        """
        if task_name == 'add_layers' and self._pending_add_layers_tasks > 0:
            self._pending_add_layers_tasks -= 1
            logger.debug(f"add_layers pending count: {self._pending_add_layers_tasks}")
    
    def reset_flags_on_termination(self, task_name: str):
        """
        Reset flags when a task is terminated unexpectedly.
        
        Args:
            task_name: Terminated task name
        """
        if task_name == 'add_layers':
            if self._pending_add_layers_tasks > 0:
                self._pending_add_layers_tasks -= 1
            logger.debug(f"Reset flags after {task_name} termination")

    def safe_cancel_all_tasks(self) -> None:
        """
        Safely cancel all tasks in the QGIS task manager.

        Cancels tasks individually instead of using cancelAll() to avoid
        Windows access violations during project transitions.
        """
        try:
            task_manager = QgsApplication.taskManager()
            if not task_manager:
                return

            count = task_manager.count()
            for i in range(count - 1, -1, -1):  # Iterate backwards
                task = task_manager.task(i)
                if task and task.canCancel():
                    task.cancel()

        except Exception as e:
            logger.warning(f"Could not cancel tasks: {e}")

    def cancel_layer_tasks(self, layer_id: str) -> None:
        """
        Cancel all running tasks for a specific layer.

        CRASH FIX: Must be called before modifying layer variables to prevent
        race conditions where background tasks iterate features while main
        thread modifies layer state.

        Args:
            layer_id: The ID of the layer whose tasks should be cancelled
        """
        try:
            dockwidget = self._get_dockwidget()
            if not dockwidget:
                return

            exploring_widget = dockwidget.widgets.get("EXPLORING", {})
            for widget_key in ["SINGLE_SELECTION_FEATURES", "MULTIPLE_SELECTION_FEATURES"]:
                widget_data = exploring_widget.get(widget_key, {})
                widget = widget_data.get("WIDGET")
                if widget and hasattr(widget, 'tasks'):
                    for task_type in widget.tasks:
                        if layer_id in widget.tasks[task_type]:
                            task = widget.tasks[task_type][layer_id]
                            if isinstance(task, QgsTask) and not sip.isdeleted(task):
                                if task.status() in [QgsTask.Running, QgsTask.Queued]:
                                    logger.debug(f"Cancelling {task_type} task for layer {layer_id}")
                                    task.cancel()
        except Exception as e:
            logger.debug(f"cancel_layer_tasks: Error cancelling tasks: {e}")

    def get_pending_tasks_count(self) -> int:
        """Get number of pending add_layers tasks."""
        return self._pending_add_layers_tasks

    def get_queue_size(self) -> int:
        """Get current size of add_layers queue."""
        return len(self._add_layers_queue)

    def clear_queue(self) -> None:
        """Clear all queued add_layers operations."""
        size = len(self._add_layers_queue)
        self._add_layers_queue.clear()
        self._processing_queue = False
        if size > 0:
            logger.info(f"Cleared {size} queued add_layers operations")

    def reset_counters(self) -> None:
        """Reset all task counters."""
        self._pending_add_layers_tasks = 0
        logger.debug("Reset task counters")

    def enqueue_add_layers(self, layers: List[Any]) -> bool:
        """
        Add layers to the processing queue.

        Args:
            layers: List of layers to add

        Returns:
            True if enqueued successfully, False if queue full
        """
        max_queue = StabilityConstants.MAX_ADD_LAYERS_QUEUE
        if len(self._add_layers_queue) >= max_queue:
            logger.warning(f"Add layers queue is full ({max_queue}), dropping request")
            return False

        self._add_layers_queue.append(layers)
        logger.info(f"Enqueued add_layers operation (queue size: {len(self._add_layers_queue)})")
        return True

    def increment_pending_tasks(self) -> None:
        """Increment counter for pending add_layers tasks."""
        self._pending_add_layers_tasks += 1
        logger.debug(f"Pending add_layers tasks: {self._pending_add_layers_tasks}")
    
    # ========================================
    # WIDGETS INITIALIZED CALLBACK
    # ========================================
    
    def on_widgets_initialized(self):
        """
        Callback when dockwidget widgets are fully initialized.
        
        Called via widgetsInitialized signal when the dockwidget
        has finished creating and connecting all its widgets.
        """
        logger.info("✓ TaskOrchestrator received widgetsInitialized signal")
        self._widgets_ready = True
        
        # Process queued operations
        if self._add_layers_queue and self._pending_add_layers_tasks == 0:
            logger.info(f"Widgets ready - processing {len(self._add_layers_queue)} queued operations")
            weak_self = weakref.ref(self)
            def safe_process():
                strong_self = weak_self()
                if strong_self:
                    strong_self.process_add_layers_queue()
            QTimer.singleShot(100, safe_process)

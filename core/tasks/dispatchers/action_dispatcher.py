# -*- coding: utf-8 -*-
"""
ActionDispatcher - Task Action Routing and Coordination

Phase E13 Step 6: Extract action dispatching logic from FilterEngineTask.

This module provides a clean abstraction for routing task actions to their
appropriate handlers, replacing the if/elif chain in _execute_task_action().

Hexagonal Architecture:
- Port: ActionHandler protocol
- Adapters: FilterActionHandler, UnfilterActionHandler, ResetActionHandler, ExportActionHandler

Author: FilterMate Team
Created: January 2026 (Phase E13 Step 6)
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, Callable, List, Protocol, Tuple

logger = logging.getLogger('FilterMate.Core.Tasks.Dispatchers.ActionDispatcher')


# =============================================================================
# Enums
# =============================================================================

class TaskAction(Enum):
    """Enumeration of supported task actions."""
    FILTER = 'filter'
    UNFILTER = 'unfilter'
    RESET = 'reset'
    EXPORT = 'export'
    
    @classmethod
    def from_string(cls, action: str) -> Optional['TaskAction']:
        """Convert string to TaskAction enum."""
        try:
            return cls(action.lower())
        except ValueError:
            return None


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ActionResult:
    """Result of an action execution."""
    success: bool
    action: str
    message: str = ""
    feature_count: int = 0
    layers_processed: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    elapsed_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionContext:
    """Context for action execution."""
    task_parameters: Dict[str, Any]
    source_layer: Any  # QgsVectorLayer
    layers: Dict[str, List]  # Organized layers by provider
    layers_count: int
    
    # Callbacks
    is_canceled: Callable[[], bool] = None
    set_progress: Callable[[float], None] = None
    queue_subset_string: Callable[[Any, str], None] = None
    
    # Optional context
    current_predicates: Dict[str, str] = field(default_factory=dict)
    db_file_path: Optional[str] = None
    project_uuid: Optional[str] = None
    session_id: Optional[str] = None


# =============================================================================
# Protocols / Interfaces
# =============================================================================

class ActionHandler(Protocol):
    """Protocol for action handlers (Port in hexagonal architecture)."""
    
    def can_handle(self, action: TaskAction) -> bool:
        """Check if this handler can process the given action."""
        ...
    
    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the action with the given context."""
        ...
    
    def validate(self, context: ActionContext) -> Tuple[bool, str]:
        """Validate that the action can be executed."""
        ...


# =============================================================================
# Base Handler
# =============================================================================

class BaseActionHandler(ABC):
    """
    Base class for action handlers.
    
    Provides common functionality like cancellation checking and progress tracking.
    """
    
    def __init__(self, action_type: TaskAction):
        """
        Initialize the handler.
        
        Args:
            action_type: The action type this handler processes
        """
        self.action_type = action_type
        self._current_context: Optional[ActionContext] = None
    
    def can_handle(self, action: TaskAction) -> bool:
        """Check if this handler can process the given action."""
        return action == self.action_type
    
    def validate(self, context: ActionContext) -> tuple:
        """
        Validate that the action can be executed.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if context.source_layer is None:
            return False, "No source layer available"
        
        # Check layer validity
        try:
            if not context.source_layer.isValid():
                return False, f"Source layer '{context.source_layer.name()}' is not valid"
        except Exception as e:
            return False, f"Error validating source layer: {e}"
        
        return True, ""
    
    @abstractmethod
    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the action with the given context."""
        pass
    
    def _check_canceled(self, context: ActionContext) -> bool:
        """Check if the task has been canceled."""
        if context.is_canceled and context.is_canceled():
            logger.warning(f"{self.action_type.value} action canceled by user")
            return True
        return False
    
    def _update_progress(self, context: ActionContext, progress: float):
        """Update task progress."""
        if context.set_progress:
            context.set_progress(progress)


# =============================================================================
# Action Dispatcher
# =============================================================================

class ActionDispatcher:
    """
    Dispatches task actions to appropriate handlers.
    
    Phase E13 Step 6: Replaces the if/elif chain in _execute_task_action()
    with a registry-based dispatch system.
    
    Example:
        dispatcher = ActionDispatcher()
        
        # Register handlers
        dispatcher.register(FilterActionHandler())
        dispatcher.register(UnfilterActionHandler())
        
        # Dispatch action
        result = dispatcher.dispatch('filter', context)
        if result.success:
          
    """
    
    def __init__(self):
        """Initialize the dispatcher with empty handler registry."""
        self._handlers: Dict[TaskAction, ActionHandler] = {}
        self._fallback_handler: Optional[ActionHandler] = None
        self._pre_dispatch_hooks: List[Callable[[TaskAction, ActionContext], bool]] = []
        self._post_dispatch_hooks: List[Callable[[TaskAction, ActionResult], None]] = []
    
    def register(self, handler: ActionHandler) -> 'ActionDispatcher':
        """
        Register an action handler.
        
        Args:
            handler: Handler to register
            
        Returns:
            Self for method chaining
        """
        for action in TaskAction:
            if handler.can_handle(action):
                self._handlers[action] = handler
                logger.debug(f"Registered handler for action: {action.value}")
        return self
    
    def register_for_action(self, action: TaskAction, handler: ActionHandler) -> 'ActionDispatcher':
        """
        Register a handler for a specific action.
        
        Args:
            action: Action type
            handler: Handler to register
            
        Returns:
            Self for method chaining
        """
        self._handlers[action] = handler
        logger.debug(f"Registered handler for action: {action.value}")
        return self
    
    def set_fallback(self, handler: ActionHandler) -> 'ActionDispatcher':
        """
        Set fallback handler for unknown actions.
        
        Args:
            handler: Fallback handler
            
        Returns:
            Self for method chaining
        """
        self._fallback_handler = handler
        return self
    
    def add_pre_dispatch_hook(self, hook: Callable[[TaskAction, ActionContext], bool]) -> 'ActionDispatcher':
        """
        Add a hook to run before dispatching.
        
        Hook returns False to abort dispatch.
        
        Args:
            hook: Pre-dispatch hook function
            
        Returns:
            Self for method chaining
        """
        self._pre_dispatch_hooks.append(hook)
        return self
    
    def add_post_dispatch_hook(self, hook: Callable[[TaskAction, ActionResult], None]) -> 'ActionDispatcher':
        """
        Add a hook to run after dispatching.
        
        Args:
            hook: Post-dispatch hook function
            
        Returns:
            Self for method chaining
        """
        self._post_dispatch_hooks.append(hook)
        return self
    
    def dispatch(self, action: str, context: ActionContext) -> ActionResult:
        """
        Dispatch an action to the appropriate handler.
        
        Args:
            action: Action name ('filter', 'unfilter', 'reset', 'export')
            context: Execution context
            
        Returns:
            ActionResult with execution outcome
        """
        import time
        start_time = time.time()
        
        # Convert to enum
        task_action = TaskAction.from_string(action)
        if task_action is None:
            logger.error(f"Unknown action type: {action}")
            return ActionResult(
                success=False,
                action=action,
                message=f"Unknown action type: {action}",
                errors=[f"Unknown action: {action}"]
            )
        
        # Run pre-dispatch hooks
        for hook in self._pre_dispatch_hooks:
            try:
                if not hook(task_action, context):
                    logger.info(f"Pre-dispatch hook aborted action: {action}")
                    return ActionResult(
                        success=False,
                        action=action,
                        message="Action aborted by pre-dispatch hook"
                    )
            except Exception as e:
                logger.warning(f"Pre-dispatch hook failed: {e}")
        
        # Find handler
        handler = self._handlers.get(task_action, self._fallback_handler)
        if handler is None:
            logger.error(f"No handler registered for action: {action}")
            return ActionResult(
                success=False,
                action=action,
                message=f"No handler registered for action: {action}",
                errors=[f"No handler for: {action}"]
            )
        
        # Validate
        try:
            is_valid, error_msg = handler.validate(context)
            if not is_valid:
                logger.error(f"Validation failed for {action}: {error_msg}")
                return ActionResult(
                    success=False,
                    action=action,
                    message=error_msg,
                    errors=[error_msg]
                )
        except Exception as e:
            logger.error(f"Validation exception for {action}: {e}")
            return ActionResult(
                success=False,
                action=action,
                message=f"Validation error: {e}",
                errors=[str(e)]
            )
        
        # Execute
        try:
            logger.info(f"Dispatching action: {action}")
            result = handler.execute(context)
            result.elapsed_time = time.time() - start_time
            
        except Exception as e:
            logger.error(f"Action {action} failed with exception: {e}", exc_info=True)
            result = ActionResult(
                success=False,
                action=action,
                message=f"Action failed: {e}",
                errors=[str(e)],
                elapsed_time=time.time() - start_time
            )
        
        # Run post-dispatch hooks
        for hook in self._post_dispatch_hooks:
            try:
                hook(task_action, result)
            except Exception as e:
                logger.warning(f"Post-dispatch hook failed: {e}")
        
        logger.debug(f"Action {action} completed: success={result.success}, time={result.elapsed_time:.2f}s")
        return result
    
    def get_supported_actions(self) -> List[str]:
        """Get list of supported action names."""
        return [action.value for action in self._handlers.keys()]
    
    def has_handler(self, action: str) -> bool:
        """Check if a handler exists for the given action."""
        task_action = TaskAction.from_string(action)
        return task_action in self._handlers or self._fallback_handler is not None


# =============================================================================
# Callback-Based Action Handlers (for integration with FilterEngineTask)
# =============================================================================

class CallbackActionHandler(BaseActionHandler):
    """
    Action handler that delegates to a callback function.
    
    This enables integration with existing FilterEngineTask methods
    during the migration period.
    
    Example:
        handler = CallbackActionHandler(
            TaskAction.FILTER,
            execute_callback=task.execute_filtering
        )
    """
    
    def __init__(
        self,
        action_type: TaskAction,
        execute_callback: Callable[[], bool],
        validate_callback: Optional[Callable[[], tuple]] = None
    ):
        """
        Initialize callback handler.
        
        Args:
            action_type: Action type to handle
            execute_callback: Callback for execution (returns bool)
            validate_callback: Optional validation callback (returns tuple of bool, str)
        """
        super().__init__(action_type)
        self._execute_callback = execute_callback
        self._validate_callback = validate_callback
    
    def validate(self, context: ActionContext) -> tuple:
        """Validate using callback or default validation."""
        if self._validate_callback:
            return self._validate_callback()
        return super().validate(context)
    
    def execute(self, context: ActionContext) -> ActionResult:
        """Execute via callback."""
        self._current_context = context
        
        try:
            success = self._execute_callback()
            
            return ActionResult(
                success=success if success is not None else False,
                action=self.action_type.value,
                message="Action completed" if success else "Action failed",
                layers_processed=context.layers_count
            )
        except Exception as e:
            logger.error(f"Callback execution failed: {e}", exc_info=True)
            return ActionResult(
                success=False,
                action=self.action_type.value,
                message=f"Execution failed: {e}",
                errors=[str(e)]
            )


# =============================================================================
# Export Validation Handler
# =============================================================================

class ExportActionHandler(BaseActionHandler):
    """
    Handler for export actions with additional validation.
    
    Checks that export parameters are properly configured before execution.
    """
    
    def __init__(self, execute_callback: Callable[[], bool]):
        """
        Initialize export handler.
        
        Args:
            execute_callback: Callback to execute_exporting()
        """
        super().__init__(TaskAction.EXPORT)
        self._execute_callback = execute_callback
    
    def validate(self, context: ActionContext) -> tuple:
        """Validate export-specific parameters."""
        # Base validation
        base_valid, base_msg = super().validate(context)
        if not base_valid:
            return base_valid, base_msg
        
        # Check export parameters
        task_params = context.task_parameters.get("task", {})
        exporting = task_params.get("EXPORTING", {})
        
        if not exporting.get("HAS_LAYERS_TO_EXPORT", False):
            logger.debug("Export validation: HAS_LAYERS_TO_EXPORT is False or missing")
            return False, "No layers selected for export"
        
        logger.debug(f"Export validation passed: {len(exporting.get('LAYERS_TO_EXPORT', []))} layers")
        return True, ""
    
    def execute(self, context: ActionContext) -> ActionResult:
        """Execute export action."""
        self._current_context = context
        
        try:
            success = self._execute_callback()
            
            return ActionResult(
                success=success if success is not None else False,
                action=TaskAction.EXPORT.value,
                message="Export completed" if success else "Export failed",
                layers_processed=context.layers_count
            )
        except Exception as e:
            logger.error(f"Export failed: {e}", exc_info=True)
            return ActionResult(
                success=False,
                action=TaskAction.EXPORT.value,
                message=f"Export failed: {e}",
                errors=[str(e)]
            )


# =============================================================================
# Factory Functions
# =============================================================================

def create_dispatcher_for_task(task) -> ActionDispatcher:
    """
    Create an ActionDispatcher configured for a FilterEngineTask.
    
    Phase E13 Step 6: Factory function to create a dispatcher with all
    handlers registered and connected to the task's execution methods.
    
    Args:
        task: FilterEngineTask instance
        
    Returns:
        Configured ActionDispatcher
    """
    dispatcher = ActionDispatcher()
    
    # Register callback handlers for each action
    dispatcher.register_for_action(
        TaskAction.FILTER,
        CallbackActionHandler(TaskAction.FILTER, task.execute_filtering)
    )
    
    dispatcher.register_for_action(
        TaskAction.UNFILTER,
        CallbackActionHandler(TaskAction.UNFILTER, task.execute_unfiltering)
    )
    
    dispatcher.register_for_action(
        TaskAction.RESET,
        CallbackActionHandler(TaskAction.RESET, task.execute_reseting)
    )
    
    dispatcher.register_for_action(
        TaskAction.EXPORT,
        ExportActionHandler(task.execute_exporting)
    )
    
    logger.debug("Created ActionDispatcher for FilterEngineTask")
    return dispatcher


def create_action_context_from_task(task) -> ActionContext:
    """
    Create an ActionContext from a FilterEngineTask.
    
    Args:
        task: FilterEngineTask instance
        
    Returns:
        ActionContext populated from task
    """
    return ActionContext(
        task_parameters=task.task_parameters,
        source_layer=task.source_layer,
        layers=task.layers,
        layers_count=task.layers_count,
        is_canceled=task.isCanceled,
        set_progress=task.setProgress,
        queue_subset_string=getattr(task, '_queue_subset_string', None),
        current_predicates=getattr(task, 'current_predicates', {}),
        db_file_path=getattr(task, 'db_file_path', None),
        project_uuid=getattr(task, 'project_uuid', None),
        session_id=getattr(task, 'session_id', None)
    )

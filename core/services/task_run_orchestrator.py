# -*- coding: utf-8 -*-
"""
TaskRunOrchestrator Service

EPIC-1 Phase 14.7: Extracted from FilterTask.run()

This service orchestrates the main task execution flow:
- Layer initialization and CRS configuration
- Backend orchestration modules setup
- Database/project/session configuration
- Progress tracking and logging
- Performance warning detection

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase 14.7)
"""

import logging
import time
import hashlib
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger('FilterMate.Core.Services.TaskRunOrchestrator')


# =============================================================================
# Constants
# =============================================================================

LONG_QUERY_WARNING_THRESHOLD = 10.0  # seconds
VERY_LONG_QUERY_WARNING_THRESHOLD = 30.0  # seconds


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class TaskRunContext:
    """Context for task run orchestration."""
    task_action: str
    task_parameters: Dict[str, Any]
    layers_count: int
    source_layer: Any  # QgsVectorLayer
    
    # Callbacks to parent task
    initialize_source_layer_callback: Optional[Callable] = None
    configure_metric_crs_callback: Optional[Callable] = None
    organize_layers_to_filter_callback: Optional[Callable] = None
    log_backend_info_callback: Optional[Callable] = None
    execute_task_action_callback: Optional[Callable] = None
    get_contextual_performance_warning_callback: Optional[Callable] = None
    is_canceled_callback: Optional[Callable] = None
    set_progress_callback: Optional[Callable] = None
    
    # Orchestration modules (will be set by orchestrator)
    result_processor: Optional[Any] = None
    expression_builder: Optional[Any] = None
    filter_orchestrator: Optional[Any] = None
    
    # v4.0.1 FIX: Configuration values extracted from task_parameters
    # These MUST be returned to FilterEngineTask for Spatialite/history operations
    db_file_path: Optional[str] = None
    project_uuid: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class TaskRunResult:
    """Result of task run orchestration."""
    success: bool
    elapsed_time: float
    warning_messages: list
    exception: Optional[Exception] = None
    # v4.0.1 FIX: Include context to pass extracted configuration back to parent
    context: Optional['TaskRunContext'] = None


# =============================================================================
# TaskRunOrchestrator Service
# =============================================================================

class TaskRunOrchestrator:
    """
    Service for orchestrating main task execution flow.
    
    This service extracts the complex orchestration logic from FilterTask.run(),
    making it testable and following hexagonal architecture principles.
    
    Example:
        orchestrator = TaskRunOrchestrator()
        result = orchestrator.run(context)
        if result.success:
            # print(f"Task completed in {result.elapsed_time:.2f}s")  # DEBUG REMOVED
    """
    
    def run(self, context: TaskRunContext) -> TaskRunResult:
        """
        Execute main task orchestration.
        
        Args:
            context: Run context with task parameters and callbacks
            
        Returns:
            TaskRunResult with success status and metrics
        """
        run_start_time = time.time()
        warning_messages = []
        
        logger.info(f"🎬 TaskRunOrchestrator.run() STARTED: action={context.task_action}, layers={context.layers_count}")
        
        try:
            # Step 1: Clear Spatialite support cache for fresh detection
            logger.info("  Step 1: Clearing Spatialite cache...")
            self._clear_spatialite_cache(context)
            
            # Step 2: Initialize source layer
            logger.info("  Step 2: Initializing source layer...")
            if not self._initialize_source_layer(context):
                logger.error("  ❌ Step 2 FAILED: Source layer initialization failed")
                return TaskRunResult(
                    success=False,
                    elapsed_time=time.time() - run_start_time,
                    warning_messages=warning_messages,
                    context=context  # v4.0.1 FIX: Pass context back
                )
            logger.info("  ✓ Step 2 completed: Source layer initialized")
            
            # Step 3: Configure metric CRS if needed
            logger.info("  Step 3: Configuring metric CRS...")
            self._configure_metric_crs(context)
            logger.info("  ✓ Step 3 completed: CRS configured")
            
            # Step 4: Organize layers to filter by provider
            logger.info("  Step 4: Organizing layers by provider...")
            self._organize_layers(context)
            logger.info("  ✓ Step 4 completed: Layers organized")
            
            # Step 5: Initialize orchestration modules (EPIC-1 Phase E12)
            logger.info("  Step 5: Initializing orchestration modules...")
            self._initialize_orchestration_modules(context)
            logger.info("  ✓ Step 5 completed: Modules initialized")
            
            # Step 6: Extract database and project configuration
            logger.info("  Step 6: Extracting db_file_path, project_uuid, session_id...")
            self._extract_configuration(context)
            logger.info(f"  ✓ Step 6 completed: db={context.db_file_path is not None}, uuid={context.project_uuid is not None}")
            
            # Step 7: Initialize progress and logging
            logger.info("  Step 7: Initializing progress...")
            self._initialize_progress(context)
            logger.info("  ✓ Step 7 completed: Progress set to 0%")
            
            # Step 8: Log backend info
            logger.info("  Step 8: Logging backend info...")
            self._log_backend_info(context)
            logger.info("  ✓ Step 8 completed")
            
            # Step 9: Execute the appropriate action
            logger.info(f"  Step 9: Executing action '{context.task_action}'...")
            result = self._execute_action(context)
            if self._is_canceled(context):
                logger.warning("  ⚠️ Step 9: Task was canceled by user")
                return TaskRunResult(
                    success=False,
                    elapsed_time=time.time() - run_start_time,
                    warning_messages=warning_messages,
                    context=context  # v4.0.1 FIX: Pass context back
                )
            if result is False:
                elapsed = time.time() - run_start_time
                logger.error(f"  ❌ Step 9 FAILED: Action '{context.task_action}' returned False after {elapsed:.1f}s")
                logger.error(f"     Check Python console for detailed error messages.")
                logger.error(f"     Common causes: no features selected, empty filter expression, database connection issue.")
                return TaskRunResult(
                    success=False,
                    elapsed_time=elapsed,
                    warning_messages=warning_messages,
                    context=context  # v4.0.1 FIX: Pass context back
                )
            logger.info(f"  ✓ Step 9 completed: Action '{context.task_action}' succeeded")
            
            # Step 10: Task completed successfully
            self._set_progress(context, 100)
            
            # Step 11: Check for long query duration
            run_elapsed = time.time() - run_start_time
            warning_messages = self._check_performance_warnings(context, run_elapsed)
            
            logger.info(f"{context.task_action.capitalize()} task completed successfully in {run_elapsed:.2f}s")
            
            return TaskRunResult(
                success=True,
                elapsed_time=run_elapsed,
                warning_messages=warning_messages,
                context=context  # v4.0.1 FIX: Pass context back with extracted config
            )
        
        except Exception as e:
            logger.error(f'TaskRunOrchestrator run() failed: {e}', exc_info=True)
            return TaskRunResult(
                success=False,
                elapsed_time=time.time() - run_start_time,
                warning_messages=warning_messages,
                exception=e,
                context=context  # v4.0.1 FIX: Pass context back even on exception
            )
    
    def _clear_spatialite_cache(self, context: TaskRunContext):
        """Clear Spatialite support cache for fresh detection."""
        if context.task_action == 'filter':
            try:
                # Import is done here to avoid circular dependencies
                from ..ports import get_backend_services
                SpatialiteGeometricFilter = get_backend_services().get_spatialite_geometric_filter()
                if SpatialiteGeometricFilter and hasattr(SpatialiteGeometricFilter, 'clear_support_cache'):
                    SpatialiteGeometricFilter.clear_support_cache()
                    logger.debug("Spatialite support cache cleared for fresh detection")
            except Exception as e:
                logger.debug(f"Could not clear Spatialite cache: {e}")
    
    def _initialize_source_layer(self, context: TaskRunContext) -> bool:
        """Initialize source layer."""
        if context.initialize_source_layer_callback:
            return context.initialize_source_layer_callback()
        return True
    
    def _configure_metric_crs(self, context: TaskRunContext):
        """Configure metric CRS if needed."""
        if context.configure_metric_crs_callback:
            context.configure_metric_crs_callback()
    
    def _organize_layers(self, context: TaskRunContext):
        """Organize layers to filter by provider."""
        if context.organize_layers_to_filter_callback:
            context.organize_layers_to_filter_callback()
    
    def _initialize_orchestration_modules(self, context: TaskRunContext):
        """
        Initialize EPIC-1 Phase E12 orchestration modules.
        
        These modules extract 1,663 lines from the God Class:
        - ResultProcessor: Handles results and subset requests
        - ExpressionBuilder: Builds filter expressions
        - FilterOrchestrator: Orchestrates filtering operations
        
        CRITICAL NOTE 2026-01-16: These modules are created with current_predicates=[]
        BEFORE execute_filtering() calls _initialize_current_predicates(). This is OK
        because FilterEngineTask._get_filter_orchestrator() and _get_expression_builder()
        ALWAYS propagate fresh predicates from self.current_predicates on every access.
        This ensures the race condition doesn't cause empty predicates during filtering.
        """
        # Import modules (avoiding circular imports)
        from ..filter.result_processor import ResultProcessor
        from ..filter.expression_builder import ExpressionBuilder
        from ..filter.filter_orchestrator import FilterOrchestrator
        
        # Create ResultProcessor
        context.result_processor = ResultProcessor(
            task_action=context.task_action,
            task_parameters=context.task_parameters
        )
        
        # Create ExpressionBuilder
        # Note: source_wkt, source_srid, etc. will be set later after source geometry preparation
        # The lazy initialization in FilterEngineTask._get_expression_builder() will handle this
        context.expression_builder = ExpressionBuilder(
            task_parameters=context.task_parameters,
            source_layer=context.source_layer,
            current_predicates=[]  # Will be set by parent task
            # Other PostgreSQL parameters will be set via lazy init or updated later
        )
        
        # ARCHITECTURE FIX 2026-01-16 (Winston): DO NOT create FilterOrchestrator here!
        # FilterOrchestrator now requires a callback to fetch predicates dynamically.
        # Since parent_task doesn't exist yet at this point, we CANNOT create it here.
        # Instead, FilterEngineTask._get_filter_orchestrator() handles lazy initialization
        # with proper callback: lambda: self.current_predicates
        #
        # This eliminates the race condition where FilterOrchestrator was created with
        # empty predicates BEFORE _initialize_current_predicates() ran.
        context.filter_orchestrator = None  # Will be lazy-initialized by FilterEngineTask
        
        logger.debug("Phase E12 orchestration modules initialized (FilterOrchestrator lazy-init)")
    
    def _extract_configuration(self, context: TaskRunContext):
        """
        Extract database, project, and session configuration.
        
        v4.0.1 FIX: Store extracted values in context so they can be
        returned to FilterEngineTask. These are CRITICAL for:
        - db_file_path: Spatialite database connection
        - project_uuid: Filter history tracking
        - session_id: Materialized view isolation
        """
        task_params = context.task_parameters["task"]
        
        # Extract database path and STORE in context
        db_path = task_params.get('db_file_path')
        if db_path not in (None, ''):
            context.db_file_path = db_path
            logger.debug(f"Database path: {db_path}")
        
        # Extract project UUID and STORE in context
        proj_uuid = task_params.get('project_uuid')
        if proj_uuid not in (None, ''):
            context.project_uuid = proj_uuid
            logger.debug(f"Project UUID: {proj_uuid}")
        
        # Extract or generate session_id and STORE in context
        context.session_id = self._get_or_generate_session_id(task_params)
        logger.debug(f"Session ID: {context.session_id}")
    
    def _get_or_generate_session_id(self, task_params: Dict[str, Any]) -> str:
        """Get or generate session_id for multi-client MV isolation."""
        # Try direct key
        if 'session_id' in task_params:
            return task_params['session_id']
        
        # Try options dict
        if 'options' in task_params and 'session_id' in task_params['options']:
            return task_params['options']['session_id']
        
        # Fallback: generate a short session id
        session_id = hashlib.md5(f"{time.time()}".encode()).hexdigest()[:8]
        logger.debug(f"Generated fallback session_id: {session_id}")
        return session_id
    
    def _initialize_progress(self, context: TaskRunContext):
        """Initialize progress and logging."""
        self._set_progress(context, 0)
        logger.info(f"Starting {context.task_action} task for {context.layers_count} layer(s)")
    
    def _log_backend_info(self, context: TaskRunContext):
        """Log backend info and performance warnings."""
        if context.log_backend_info_callback:
            context.log_backend_info_callback()
    
    def _execute_action(self, context: TaskRunContext) -> bool:
        """Execute the appropriate task action."""
        if context.execute_task_action_callback:
            return context.execute_task_action_callback()
        return False
    
    def _is_canceled(self, context: TaskRunContext) -> bool:
        """Check if task was canceled."""
        if context.is_canceled_callback:
            return context.is_canceled_callback()
        return False
    
    def _set_progress(self, context: TaskRunContext, progress: int):
        """Set task progress."""
        if context.set_progress_callback:
            context.set_progress_callback(progress)
    
    def _check_performance_warnings(
        self,
        context: TaskRunContext,
        elapsed_time: float
    ) -> list:
        """
        Check for long query duration and generate warnings.
        
        Returns:
            List of warning messages
        """
        warnings = []
        
        if elapsed_time >= VERY_LONG_QUERY_WARNING_THRESHOLD:
            # Very long query (>30s): Critical warning
            if context.get_contextual_performance_warning_callback:
                warning_msg = context.get_contextual_performance_warning_callback(
                    elapsed_time,
                    'critical'
                )
                if warning_msg:
                    warnings.append(warning_msg)
            logger.warning(f"⚠️ Very long query: {elapsed_time:.1f}s")
        
        elif elapsed_time >= LONG_QUERY_WARNING_THRESHOLD:
            # Long query (>10s): Standard warning
            if context.get_contextual_performance_warning_callback:
                warning_msg = context.get_contextual_performance_warning_callback(
                    elapsed_time,
                    'warning'
                )
                if warning_msg:
                    warnings.append(warning_msg)
            logger.warning(f"⚠️ Long query: {elapsed_time:.1f}s")
        
        return warnings


# =============================================================================
# Factory Function
# =============================================================================

def create_task_run_orchestrator() -> TaskRunOrchestrator:
    """
    Factory function to create a TaskRunOrchestrator.
    
    Returns:
        TaskRunOrchestrator instance
    """
    return TaskRunOrchestrator()


# =============================================================================
# Convenience Function for Direct Use
# =============================================================================

def execute_task_run(
    task_action: str,
    task_parameters: Dict[str, Any],
    layers_count: int,
    source_layer: Any,
    initialize_source_layer_callback: Optional[Callable] = None,
    configure_metric_crs_callback: Optional[Callable] = None,
    organize_layers_to_filter_callback: Optional[Callable] = None,
    log_backend_info_callback: Optional[Callable] = None,
    execute_task_action_callback: Optional[Callable] = None,
    get_contextual_performance_warning_callback: Optional[Callable] = None,
    is_canceled_callback: Optional[Callable] = None,
    set_progress_callback: Optional[Callable] = None
) -> TaskRunResult:
    """
    Execute main task orchestration.
    
    Convenience function that creates an orchestrator and executes task.
    
    Args:
        task_action: Action to execute ('filter', 'unfilter', 'reset', 'export')
        task_parameters: Task parameters dict
        layers_count: Number of layers to process
        source_layer: Source QgsVectorLayer
        initialize_source_layer_callback: Callback to initialize source layer
        configure_metric_crs_callback: Callback to configure metric CRS
        organize_layers_to_filter_callback: Callback to organize layers
        log_backend_info_callback: Callback to log backend info
        execute_task_action_callback: Callback to execute action
        get_contextual_performance_warning_callback: Callback for performance warnings
        is_canceled_callback: Callback to check if task canceled
        set_progress_callback: Callback to set progress
        
    Returns:
        TaskRunResult with success status and metrics
    """
    context = TaskRunContext(
        task_action=task_action,
        task_parameters=task_parameters,
        layers_count=layers_count,
        source_layer=source_layer,
        initialize_source_layer_callback=initialize_source_layer_callback,
        configure_metric_crs_callback=configure_metric_crs_callback,
        organize_layers_to_filter_callback=organize_layers_to_filter_callback,
        log_backend_info_callback=log_backend_info_callback,
        execute_task_action_callback=execute_task_action_callback,
        get_contextual_performance_warning_callback=get_contextual_performance_warning_callback,
        is_canceled_callback=is_canceled_callback,
        set_progress_callback=set_progress_callback
    )
    
    orchestrator = create_task_run_orchestrator()
    return orchestrator.run(context)

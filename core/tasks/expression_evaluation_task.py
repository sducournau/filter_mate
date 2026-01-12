"""
ExpressionEvaluationTask - Asynchronous expression evaluation for large layers.

This module provides a QgsTask-based implementation for evaluating complex
QGIS expressions on large layers without freezing the UI.

Created: January 2026
Version: 2.5.10

PROBLEM SOLVED:
- When users apply complex custom expressions on large layers (100k+ features),
  the synchronous iteration in get_exploring_features() freezes QGIS
- This task moves expression evaluation to a background thread

USAGE:
    from modules.tasks.expression_evaluation_task import ExpressionEvaluationTask
    
    task = ExpressionEvaluationTask(
        description="Evaluating expression",
        layer=my_layer,
        expression="complex_expression",
        callback=my_callback_function,
        error_callback=my_error_callback
    )
    QgsApplication.taskManager().addTask(task)
"""

import time
import logging
from typing import List, Optional, Callable, Any, Tuple

from qgis.core import (
    QgsTask,
    QgsApplication,
    QgsVectorLayer,
    QgsFeature,
    QgsFeatureRequest,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsProject
)
from qgis.PyQt.QtCore import pyqtSignal, QObject

from ...infrastructure.logging import get_logger

logger = get_logger(__name__)


class ExpressionEvaluationSignals(QObject):
    """
    Signals for ExpressionEvaluationTask communication.
    
    Using QObject-based signals instead of task signals for thread safety.
    """
    # Emitted when evaluation completes successfully
    # Args: (features: List[QgsFeature], expression: str, layer_id: str)
    finished = pyqtSignal(list, str, str)
    
    # Emitted on error
    # Args: (error_message: str, layer_id: str)
    error = pyqtSignal(str, str)
    
    # Emitted during progress (for UI feedback)
    # Args: (current: int, total: int, layer_id: str)
    progress = pyqtSignal(int, int, str)
    
    # Emitted when task is cancelled
    # Args: (layer_id: str)
    cancelled = pyqtSignal(str)


class ExpressionEvaluationTask(QgsTask):
    """
    QgsTask for evaluating complex expressions on large layers asynchronously.
    
    This task prevents UI freezes when:
    - Evaluating complex expressions on 100k+ feature layers
    - Using custom filter expressions with spatial operations
    - Loading pre-filtered data with expensive expressions
    
    Thread Safety:
    - Uses layer.dataProvider().featureSource() for thread-safe iteration
    - Does NOT modify layer (no setSubsetString in background thread)
    - Results are passed via signals for main thread processing
    
    Example:
        def on_evaluation_complete(features, expression, layer_id):
            # Handle results in main thread
            layer.select([f.id() for f in features])
        
        task = ExpressionEvaluationTask(
            description="Filtering features",
            layer=my_layer,
            expression='"population" > 10000 AND intersects(@buffer_geometry)',
            limit=1000
        )
        task.signals.finished.connect(on_evaluation_complete)
        QgsApplication.taskManager().addTask(task)
    """
    
    # Progress update batch size (reduce UI overhead)
    PROGRESS_BATCH_SIZE = 100
    
    def __init__(
        self,
        description: str,
        layer: QgsVectorLayer,
        expression: str,
        limit: int = 0,
        request_fields: Optional[List[str]] = None,
        include_geometry: bool = True,
        context_variables: Optional[dict] = None
    ):
        """
        Initialize the expression evaluation task.
        
        Args:
            description: Task description shown in task manager
            layer: The vector layer to evaluate expression on
            expression: QGIS expression string to evaluate
            limit: Maximum number of features to return (0 = no limit)
            request_fields: Optional list of field names to include (None = all)
            include_geometry: Whether to include geometry in results
            context_variables: Additional variables for expression context
        """
        super().__init__(description, QgsTask.CanCancel)
        
        # Store parameters
        self.layer = layer
        self.layer_id = layer.id() if layer else None
        self.layer_name = layer.name() if layer else "Unknown"
        self.expression_string = expression
        self.limit = limit
        self.request_fields = request_fields
        self.include_geometry = include_geometry
        self.context_variables = context_variables or {}
        
        # Thread-safe feature source (must be created before run())
        self._feature_source = None
        self._total_count = 0
        
        # Results
        self.result_features: List[QgsFeature] = []
        self.result_expression: str = expression
        self.exception: Optional[Exception] = None
        
        # Signals for thread-safe communication
        self.signals = ExpressionEvaluationSignals()
        
        # Performance metrics
        self._start_time: float = 0
        self._processed_count: int = 0
        
        # Prepare feature source in main thread before task starts
        self._prepare_feature_source()
    
    def _prepare_feature_source(self):
        """
        Prepare thread-safe feature source from layer.
        
        CRITICAL: This must be called in the main thread before run() is called.
        dataProvider().featureSource() returns a thread-safe snapshot.
        """
        if self.layer and self.layer.isValid():
            try:
                provider = self.layer.dataProvider()
                if provider:
                    self._feature_source = provider.featureSource()
                    self._total_count = provider.featureCount()
            except Exception as e:
                logger.warning(f"Could not prepare feature source for {self.layer_name}: {e}")
                self._feature_source = None
    
    def run(self) -> bool:
        """
        Execute expression evaluation in background thread.
        
        Returns:
            True if evaluation completed successfully, False otherwise
        """
        self._start_time = time.time()
        
        try:
            # v2.6.7: Refresh feature source at run() time to get current layer state
            # This fixes stale data when filter was applied between task creation and execution
            self._refresh_feature_source()
            
            # Validate inputs
            if not self._validate_inputs():
                return False
            
            # Build feature request
            request = self._build_feature_request()
            if request is None:
                return False
            
            # Iterate features and collect results
            success = self._iterate_features(request)
            
            if success:
                elapsed = time.time() - self._start_time
                logger.info(
                    f"Expression evaluation completed for '{self.layer_name}': "
                    f"{len(self.result_features)} features in {elapsed:.2f}s"
                )
            
            return success
            
        except Exception as e:
            self.exception = e
            logger.error(f"Expression evaluation failed for '{self.layer_name}': {e}")
            return False
    
    def _refresh_feature_source(self):
        """
        Refresh the feature source from the layer's data provider.
        
        v2.6.7: Called at the start of run() to ensure we have the current layer state,
        not a stale snapshot from when the task was created.
        """
        if self.layer and self.layer.isValid():
            try:
                provider = self.layer.dataProvider()
                if provider:
                    self._feature_source = provider.featureSource()
                    self._total_count = provider.featureCount()
                    logger.debug(f"Refreshed feature source for {self.layer_name}: {self._total_count} features")
            except Exception as e:
                logger.warning(f"Could not refresh feature source for {self.layer_name}: {e}")
                # Keep the existing feature source if refresh fails
    
    def _validate_inputs(self) -> bool:
        """Validate task inputs before execution."""
        if self._feature_source is None:
            self.exception = ValueError("No feature source available (layer may have been removed)")
            return False
        
        if not self.expression_string:
            self.exception = ValueError("Expression string is empty")
            return False
        
        # Validate expression syntax
        qgs_expr = QgsExpression(self.expression_string)
        if qgs_expr.hasParserError():
            self.exception = ValueError(f"Invalid expression: {qgs_expr.parserErrorString()}")
            return False
        
        return True
    
    def _build_feature_request(self) -> Optional[QgsFeatureRequest]:
        """
        Build the QgsFeatureRequest with expression and optimizations.
        
        Returns:
            Configured QgsFeatureRequest or None on error
        """
        try:
            qgs_expr = QgsExpression(self.expression_string)
            request = QgsFeatureRequest(qgs_expr)
            
            # Set limit if specified
            if self.limit > 0:
                request.setLimit(self.limit)
            
            # Optimize field loading if specific fields requested
            if self.request_fields:
                request.setSubsetOfAttributes(
                    self.request_fields,
                    self.layer.fields()
                )
            
            # Geometry flag (can save memory/time if not needed)
            if not self.include_geometry:
                request.setFlags(QgsFeatureRequest.NoGeometry)
            
            return request
            
        except Exception as e:
            self.exception = e
            logger.error(f"Failed to build feature request: {e}")
            return None
    
    def _iterate_features(self, request: QgsFeatureRequest) -> bool:
        """
        Iterate through features matching the expression.
        
        Uses batched progress updates to minimize UI overhead.
        
        Args:
            request: Configured QgsFeatureRequest
            
        Returns:
            True if iteration completed (or was cancelled), False on error
        """
        try:
            # Use estimated count for progress
            estimated_total = self._total_count if self._total_count > 0 else 1000
            if self.limit > 0:
                estimated_total = min(estimated_total, self.limit)
            
            # ROBUSTNESS: Check feature source is still valid before iteration
            if self._feature_source is None:
                self.exception = ValueError("Feature source became invalid")
                return False
            
            # Get feature iterator - this can fail for invalid expressions
            try:
                feature_iterator = self._feature_source.getFeatures(request)
            except Exception as e:
                self.exception = ValueError(f"Failed to create feature iterator: {e}")
                logger.error(f"Failed to create feature iterator for '{self.layer_name}': {e}")
                return False
            
            # Iterate with cancellation checks
            for index, feature in enumerate(feature_iterator):
                # Check for cancellation
                if self.isCanceled():
                    logger.debug(f"Expression evaluation cancelled for '{self.layer_name}'")
                    return True  # Cancelled is not an error
                
                # Store feature
                self.result_features.append(feature)
                self._processed_count = index + 1
                
                # Batched progress update
                if index % self.PROGRESS_BATCH_SIZE == 0:
                    progress_pct = min(100, (index / estimated_total) * 100)
                    self.setProgress(progress_pct)
                    
                    # Emit progress signal for UI
                    self.signals.progress.emit(index, estimated_total, self.layer_id)
            
            # Final progress
            self.setProgress(100)
            return True
            
        except Exception as e:
            self.exception = e
            logger.error(f"Feature iteration failed: {e}")
            return False
    
    def finished(self, result: bool):
        """
        Called in main thread when task completes.
        
        Emits appropriate signals based on result.
        
        Args:
            result: True if run() returned True
        """
        try:
            if self.isCanceled():
                self.signals.cancelled.emit(self.layer_id)
                logger.debug(f"Expression evaluation was cancelled for '{self.layer_name}'")
                
            elif result:
                # Success - emit results
                self.signals.finished.emit(
                    self.result_features,
                    self.result_expression,
                    self.layer_id
                )
                
            else:
                # Error
                error_msg = str(self.exception) if self.exception else "Unknown error"
                self.signals.error.emit(error_msg, self.layer_id)
                logger.error(f"Expression evaluation error: {error_msg}")
        except Exception as e:
            # ROBUSTNESS: Catch any exception in finished() to prevent crashes
            logger.error(f"Error in finished() callback for '{self.layer_name}': {e}")
    
    def cancel(self):
        """Cancel the task."""
        logger.debug(f"Cancelling expression evaluation for '{self.layer_name}'")
        super().cancel()


class ExpressionEvaluationManager:
    """
    Manager for running expression evaluation tasks.
    
    Provides a simple interface for launching async expression evaluations
    and handles task lifecycle management.
    
    Example:
        manager = ExpressionEvaluationManager()
        
        def on_complete(features, expression, layer_id):
            print(f"Got {len(features)} features")
        
        manager.evaluate(
            layer=my_layer,
            expression='"field" > 100',
            on_complete=on_complete
        )
    """
    
    def __init__(self):
        """Initialize the manager."""
        self._active_tasks: dict[str, ExpressionEvaluationTask] = {}
    
    def evaluate(
        self,
        layer: QgsVectorLayer,
        expression: str,
        on_complete: Optional[Callable[[List[QgsFeature], str, str], None]] = None,
        on_error: Optional[Callable[[str, str], None]] = None,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
        on_cancelled: Optional[Callable[[str], None]] = None,
        limit: int = 0,
        description: Optional[str] = None,
        cancel_existing: bool = True
    ) -> Optional[ExpressionEvaluationTask]:
        """
        Start an async expression evaluation.
        
        Args:
            layer: Layer to evaluate expression on
            expression: QGIS expression string
            on_complete: Callback(features, expression, layer_id) on success
            on_error: Callback(error_msg, layer_id) on error
            on_progress: Callback(current, total, layer_id) for progress updates
            on_cancelled: Callback(layer_id) when cancelled
            limit: Max features to return (0 = no limit)
            description: Task description (auto-generated if None)
            cancel_existing: Cancel any existing task for this layer
            
        Returns:
            The created task, or None if creation failed
        """
        if not layer or not layer.isValid():
            logger.warning("Cannot evaluate expression on invalid layer")
            if on_error:
                on_error("Invalid layer", "")
            return None
        
        if not expression:
            logger.warning("Cannot evaluate empty expression")
            if on_error:
                on_error("Empty expression", layer.id())
            return None
        
        layer_id = layer.id()
        
        # Cancel existing task for this layer if requested
        if cancel_existing and layer_id in self._active_tasks:
            old_task = self._active_tasks[layer_id]
            if old_task and not old_task.isCanceled():
                logger.debug(f"Cancelling previous expression task for {layer.name()}")
                old_task.cancel()
        
        # Create task description
        if description is None:
            description = f"FilterMate: Evaluating expression on {layer.name()}"
        
        # Create task
        task = ExpressionEvaluationTask(
            description=description,
            layer=layer,
            expression=expression,
            limit=limit
        )
        
        # Connect signals
        if on_complete:
            task.signals.finished.connect(on_complete)
        if on_error:
            task.signals.error.connect(on_error)
        if on_progress:
            task.signals.progress.connect(on_progress)
        if on_cancelled:
            task.signals.cancelled.connect(on_cancelled)
        
        # Track and cleanup
        def _on_task_done(*args):
            if layer_id in self._active_tasks:
                del self._active_tasks[layer_id]
        
        task.signals.finished.connect(_on_task_done)
        task.signals.error.connect(_on_task_done)
        task.signals.cancelled.connect(_on_task_done)
        
        # Store and run
        self._active_tasks[layer_id] = task
        QgsApplication.taskManager().addTask(task)
        
        logger.debug(f"Started expression evaluation task for '{layer.name()}'")
        return task
    
    def cancel(self, layer_id: str) -> bool:
        """
        Cancel any active expression evaluation for a layer.
        
        Args:
            layer_id: ID of the layer
            
        Returns:
            True if a task was cancelled
        """
        if layer_id in self._active_tasks:
            task = self._active_tasks[layer_id]
            if task and not task.isCanceled():
                task.cancel()
                return True
        return False
    
    def cancel_all(self):
        """Cancel all active expression evaluations."""
        for layer_id in list(self._active_tasks.keys()):
            self.cancel(layer_id)
    
    def is_evaluating(self, layer_id: str) -> bool:
        """Check if expression evaluation is in progress for a layer."""
        return layer_id in self._active_tasks


# Global manager instance for convenience
_expression_manager: Optional[ExpressionEvaluationManager] = None


def get_expression_manager() -> ExpressionEvaluationManager:
    """
    Get the global ExpressionEvaluationManager instance.
    
    Creates one if it doesn't exist.
    """
    global _expression_manager
    if _expression_manager is None:
        _expression_manager = ExpressionEvaluationManager()
    return _expression_manager

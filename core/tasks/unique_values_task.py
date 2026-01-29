# -*- coding: utf-8 -*-
"""
UniqueValuesTask - QgsTask for async unique values loading.

v4.1.1 - January 2026

PERFORMANCE:
- Prevents UI freeze when loading unique values for fields with 10k+ distinct values
- Uses dataProvider().featureSource() for thread-safe access
- Supports pagination/batching for very large value sets
- Integrates with cache for repeated queries

Thread Safety:
- Uses QgsVectorDataProvider.featureSource() snapshot in main thread
- All value extraction happens in background thread
- Results emitted via Qt signals to main thread
"""

import time
import logging
from typing import List, Optional, Set, Any

try:
    from qgis.core import (
        QgsTask,
        QgsVectorLayer,
        QgsFeatureRequest,
        QgsFeature,
        QgsVectorDataProvider,
    )
    from qgis.PyQt.QtCore import QObject, pyqtSignal
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False
    QgsTask = object

logger = logging.getLogger('FilterMate.UniqueValuesTask')


class UniqueValuesSignals(QObject):
    """
    Signals for thread-safe communication from UniqueValuesTask.
    
    Signals:
        finished(values, field_name, layer_id): Emitted on successful completion
        progress(count, estimated_total, layer_id): Emitted during iteration
        error(error_message, layer_id): Emitted on error
        cancelled(layer_id): Emitted if task was cancelled
    """
    finished = pyqtSignal(list, str, str)       # values, field_name, layer_id
    progress = pyqtSignal(int, int, str)        # count, estimated_total, layer_id
    error = pyqtSignal(str, str)                # error_message, layer_id
    cancelled = pyqtSignal(str)                 # layer_id


class UniqueValuesTask(QgsTask):
    """
    QgsTask for asynchronously extracting unique values from a layer field.
    
    PERFORMANCE OPTIMIZATION:
    - For small layers (<10k features): Uses uniqueValues() directly
    - For large layers: Iterates features with progress updates
    - Always returns sorted, deduplicated string values
    
    LAZY LOADING:
    - max_values parameter limits results (e.g., first 1000 for autocomplete)
    - Pagination support via offset parameter
    - Early termination when max_values reached
    
    Thread Safety:
    - _feature_source prepared in main thread before run()
    - Only primitive data (strings) emitted via signals
    
    Example:
        task = UniqueValuesTask(
            description="Loading field values",
            layer=my_layer,
            field_name="category",
            max_values=500,  # Limit for UI performance
        )
        task.signals.finished.connect(on_values_loaded)
        QgsApplication.taskManager().addTask(task)
    """
    
    # Threshold for switching to iteration mode (vs uniqueValues)
    ITERATE_THRESHOLD = 10000
    
    # Progress batch size
    PROGRESS_BATCH_SIZE = 500
    
    def __init__(
        self,
        description: str,
        layer: QgsVectorLayer,
        field_name: str,
        max_values: int = 0,
        offset: int = 0,
        sort_values: bool = True,
        include_null: bool = False,
    ):
        """
        Initialize the unique values extraction task.
        
        Args:
            description: Task description for task manager
            layer: Source vector layer
            field_name: Name of field to extract values from
            max_values: Maximum values to return (0 = no limit)
            offset: Skip first N values (for pagination)
            sort_values: Whether to sort results alphabetically
            include_null: Whether to include NULL values
        """
        super().__init__(description, QgsTask.CanCancel)
        
        # Store parameters
        self.layer = layer
        self.layer_id = layer.id() if layer else None
        self.layer_name = layer.name() if layer else "Unknown"
        self.field_name = field_name
        self.max_values = max_values
        self.offset = offset
        self.sort_values = sort_values
        self.include_null = include_null
        
        # Thread-safe data source
        self._feature_source: Optional[QgsVectorDataProvider] = None
        self._total_count: int = 0
        self._field_index: int = -1
        
        # Results
        self.result_values: List[str] = []
        self.exception: Optional[Exception] = None
        
        # Signals
        self.signals = UniqueValuesSignals()
        
        # Performance metrics
        self._start_time: float = 0
        self._processed_count: int = 0
        
        # Prepare in main thread
        self._prepare_feature_source()
    
    def _prepare_feature_source(self) -> None:
        """
        Prepare thread-safe feature source in main thread.
        
        CRITICAL: Must be called before run() starts.
        """
        if not self.layer or not self.layer.isValid():
            return
        
        try:
            # Get field index
            fields = self.layer.fields()
            self._field_index = fields.indexFromName(self.field_name)
            
            if self._field_index < 0:
                logger.warning(f"Field '{self.field_name}' not found in {self.layer_name}")
                return
            
            # Get thread-safe snapshot
            provider = self.layer.dataProvider()
            if provider:
                self._feature_source = provider.featureSource()
                self._total_count = provider.featureCount()
                
        except Exception as e:
            logger.warning(f"Could not prepare feature source: {e}")
            self._feature_source = None
    
    def run(self) -> bool:
        """
        Execute unique values extraction in background thread.
        
        Returns:
            True on success, False on error
        """
        self._start_time = time.time()
        
        try:
            # Validate inputs
            if not self._validate_inputs():
                return False
            
            # Choose extraction method based on layer size
            if self._total_count < self.ITERATE_THRESHOLD:
                success = self._extract_via_unique_values()
            else:
                success = self._extract_via_iteration()
            
            if success:
                # Apply sorting if requested
                if self.sort_values:
                    self.result_values.sort(key=lambda x: (x is None, x or ''))
                
                # Apply offset/limit
                if self.offset > 0:
                    self.result_values = self.result_values[self.offset:]
                if self.max_values > 0:
                    self.result_values = self.result_values[:self.max_values]
                
                elapsed = time.time() - self._start_time
                logger.info(
                    f"Unique values extraction for '{self.field_name}' on '{self.layer_name}': "
                    f"{len(self.result_values)} values in {elapsed:.2f}s"
                )
            
            return success
            
        except Exception as e:
            self.exception = e
            logger.error(f"Unique values extraction failed: {e}")
            return False
    
    def _validate_inputs(self) -> bool:
        """Validate task inputs."""
        if self._feature_source is None:
            self.exception = ValueError("No feature source available")
            return False
        
        if self._field_index < 0:
            self.exception = ValueError(f"Field '{self.field_name}' not found")
            return False
        
        return True
    
    def _extract_via_unique_values(self) -> bool:
        """
        Fast extraction using provider's uniqueValues() for small layers.
        
        NOTE: uniqueValues() loads all values in memory, not suitable for huge layers.
        """
        try:
            if not self.layer or not self.layer.isValid():
                self.exception = ValueError("Layer no longer valid")
                return False
            
            # Use layer.uniqueValues() - faster for small datasets
            raw_values = self.layer.uniqueValues(self._field_index)
            
            # Convert to string list
            for val in raw_values:
                if self.isCanceled():
                    return True
                
                if val is None:
                    if self.include_null:
                        self.result_values.append(None)
                else:
                    self.result_values.append(str(val))
            
            self.setProgress(100)
            return True
            
        except Exception as e:
            self.exception = e
            logger.error(f"uniqueValues extraction failed: {e}")
            return False
    
    def _extract_via_iteration(self) -> bool:
        """
        Memory-efficient extraction via feature iteration for large layers.
        
        Uses a Set for deduplication, emits progress updates.
        """
        try:
            unique_set: Set[Any] = set()
            
            # Build optimized request - only load the target field
            request = QgsFeatureRequest()
            request.setSubsetOfAttributes([self._field_index])
            request.setFlags(QgsFeatureRequest.NoGeometry)
            
            # Get iterator
            feature_iter = self._feature_source.getFeatures(request)
            
            for index, feature in enumerate(feature_iter):
                # Check cancellation
                if self.isCanceled():
                    logger.debug(f"Unique values extraction cancelled at {index}")
                    return True
                
                # Get field value
                try:
                    value = feature.attributes()[self._field_index]
                    
                    if value is None:
                        if self.include_null:
                            unique_set.add(None)
                    else:
                        unique_set.add(str(value))
                except (IndexError, AttributeError):
                    continue
                
                # Progress update
                self._processed_count = index + 1
                if index % self.PROGRESS_BATCH_SIZE == 0:
                    progress_pct = min(100, (index / self._total_count) * 100)
                    self.setProgress(progress_pct)
                    self.signals.progress.emit(
                        len(unique_set), 
                        self._total_count, 
                        self.layer_id
                    )
                
                # Early termination if we have enough values (with buffer for offset)
                if self.max_values > 0:
                    needed = self.max_values + self.offset
                    if len(unique_set) >= needed * 2:  # 2x buffer for safety
                        logger.debug(f"Early termination: collected {len(unique_set)} values")
                        break
            
            # Convert set to list
            self.result_values = list(unique_set)
            self.setProgress(100)
            return True
            
        except Exception as e:
            self.exception = e
            logger.error(f"Iteration extraction failed: {e}")
            return False
    
    def finished(self, result: bool) -> None:
        """
        Called in main thread when task completes.
        
        Emits appropriate signals based on result.
        """
        try:
            if self.isCanceled():
                self.signals.cancelled.emit(self.layer_id)
                logger.debug(f"Unique values task cancelled for '{self.layer_name}'")
                
            elif result:
                self.signals.finished.emit(
                    self.result_values,
                    self.field_name,
                    self.layer_id
                )
                
            else:
                error_msg = str(self.exception) if self.exception else "Unknown error"
                self.signals.error.emit(error_msg, self.layer_id)
                logger.error(f"Unique values error: {error_msg}")
                
        except Exception as e:
            logger.error(f"Error in UniqueValuesTask.finished(): {e}")
    
    def cancel(self) -> None:
        """Cancel the task."""
        logger.debug(f"Cancelling unique values task for '{self.layer_name}'")
        super().cancel()


class UniqueValuesManager:
    """
    Manager for UniqueValuesTask instances.
    
    Provides:
    - Task lifecycle management
    - Concurrent request handling
    - Cancellation of pending tasks
    """
    
    _instance: Optional['UniqueValuesManager'] = None
    
    @classmethod
    def instance(cls) -> 'UniqueValuesManager':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        self._active_tasks: dict = {}  # layer_id:field_name -> task
    
    def fetch_async(
        self,
        layer: QgsVectorLayer,
        field_name: str,
        on_complete: callable,
        on_error: callable = None,
        max_values: int = 0,
    ) -> None:
        """
        Fetch unique values asynchronously.
        
        Args:
            layer: Source layer
            field_name: Field to extract values from
            on_complete: Callback(values: List[str]) on success
            on_error: Callback(error: str) on failure
            max_values: Max values to return (0 = all)
        """
        if not QGIS_AVAILABLE:
            if on_error:
                on_error("QGIS not available")
            return
        
        from qgis.core import QgsApplication
        
        # Cancel existing task for same layer/field
        task_key = f"{layer.id()}:{field_name}"
        if task_key in self._active_tasks:
            self._active_tasks[task_key].cancel()
        
        # Create new task
        task = UniqueValuesTask(
            description=f"Loading values for {field_name}",
            layer=layer,
            field_name=field_name,
            max_values=max_values,
        )
        
        # Store reference
        self._active_tasks[task_key] = task
        
        # Connect callbacks
        def _on_complete(values, field, layer_id):
            if task_key in self._active_tasks:
                del self._active_tasks[task_key]
            on_complete(values)
        
        def _on_error(error, layer_id):
            if task_key in self._active_tasks:
                del self._active_tasks[task_key]
            if on_error:
                on_error(error)
        
        task.signals.finished.connect(_on_complete)
        task.signals.error.connect(_on_error)
        
        # Submit to task manager
        QgsApplication.taskManager().addTask(task)
    
    def cancel_all(self, layer_id: str = None) -> int:
        """
        Cancel active tasks.
        
        Args:
            layer_id: Cancel only tasks for this layer (None = all)
            
        Returns:
            Number of tasks cancelled
        """
        cancelled = 0
        keys_to_remove = []
        
        for key, task in self._active_tasks.items():
            if layer_id is None or key.startswith(layer_id):
                task.cancel()
                keys_to_remove.append(key)
                cancelled += 1
        
        for key in keys_to_remove:
            del self._active_tasks[key]
        
        return cancelled


def get_unique_values_manager() -> UniqueValuesManager:
    """Get the global UniqueValuesManager instance."""
    return UniqueValuesManager.instance()

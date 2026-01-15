# -*- coding: utf-8 -*-
"""
Parallel Filter Executor for FilterMate

Provides multi-threaded execution for filtering multiple layers simultaneously.
Uses ThreadPoolExecutor for efficient parallel processing on multi-core systems.

CRITICAL THREAD SAFETY (v2.3.9):
================================
QGIS layer objects (QgsVectorLayer) are NOT thread-safe and must only be accessed
from the main thread. Direct parallel execution of QGIS layer operations causes
"Windows fatal exception: access violation" crashes.

Thread Safety Rules:
1. OGR backend operations MUST run sequentially (they manipulate layers directly)
2. PostgreSQL/Spatialite backends CAN run in parallel (database-only operations)
3. Any operation that calls layer.selectedFeatures(), layer.startEditing(),
   layer.commitChanges(), or layer.getFeatures() MUST be on main thread

Performance Benefits (when safe):
- 2-4× faster on multi-core systems for database-backed layers
- Configurable thread pool size

Safety Implementation:
- Auto-detects OGR layers and forces sequential execution
- Database backends use per-thread connections (safe)
- Parallel mode only enabled for database-backed operations

Usage:
    from ...infrastructure.parallel import ParallelFilterExecutor    
    executor = ParallelFilterExecutor(max_workers=4)
    results = executor.filter_layers_parallel(
        layers=[(layer1, props1), (layer2, props2)],
        filter_func=execute_geometric_filtering,
        progress_callback=update_progress
    )
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from typing import List, Tuple, Dict, Any, Callable, Optional
from dataclasses import dataclass
import threading
import time

from ..logging import get_logger

logger = get_logger(__name__)


@dataclass
class FilterResult:
    """Result of a single layer filtering operation."""
    layer_id: str
    layer_name: str
    success: bool
    feature_count: int
    execution_time_ms: float
    error_message: Optional[str] = None


class ParallelFilterExecutor:
    """
    Multi-threaded executor for parallel layer filtering.
    
    Filters multiple layers simultaneously using a thread pool.
    Respects QGIS thread safety by ensuring UI operations are
    marshalled to the main thread via signals.
    
    Performance:
    - Sequential: 5 layers × 2s = 10s total
    - Parallel (4 workers): 5 layers / 4 workers × 2s ≈ 3s total
    - Speedup: ~3.3× on 4-core system
    
    Thread Safety:
    - Each thread gets its own database connection
    - Layer setSubsetString is called via QueuedConnection signal
    - Progress callbacks are thread-safe
    
    Example:
        >>> executor = ParallelFilterExecutor(max_workers=4)
        >>> results = executor.filter_layers_parallel(
        ...     layers=layer_list,
        ...     filter_func=my_filter_function,
        ...     progress_callback=on_progress
        ... )
        >>> for result in results:
        ...     print(f"{result.layer_name}: {result.success}")
    """
    
    # Default configuration
    DEFAULT_MAX_WORKERS = 4
    MIN_LAYERS_FOR_PARALLEL = 2  # Don't parallelize for less than 2 layers
    
    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialize parallel filter executor.
        
        Args:
            max_workers: Maximum number of worker threads.
                        Defaults to min(4, CPU count).
                        Values <= 0 are treated as auto-detect.
        """
        import os
        
        if max_workers is None or max_workers <= 0:
            # Use min of 4 or CPU count - 1 (leave one core for UI)
            cpu_count = os.cpu_count() or 2
            max_workers = min(self.DEFAULT_MAX_WORKERS, max(1, cpu_count - 1))
        
        # Ensure max_workers is always at least 1
        self._max_workers = max(1, max_workers)
        self._results: List[FilterResult] = []
        self._lock = threading.Lock()
        self._canceled = False
        
        logger.info(f"✓ ParallelFilterExecutor initialized (max_workers: {max_workers})")
    
    def filter_layers_parallel(
        self,
        layers: List[Tuple[Any, Dict]],
        filter_func: Callable,
        task_parameters: Dict[str, Any],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> List[FilterResult]:
        """
        Filter multiple layers in parallel (when thread-safe) or sequentially.
        
        CRITICAL THREAD SAFETY (v2.3.9):
        ================================
        QGIS layer objects are NOT thread-safe. Operations like selectedFeatures(),
        startEditing(), commitChanges(), and getFeatures() cause access violations
        when called from multiple threads simultaneously.
        
        This method automatically detects when parallel execution is unsafe and
        falls back to sequential execution:
        - OGR layers: ALWAYS sequential (direct layer manipulation)
        - PostgreSQL/Spatialite: Parallel OK (database-only operations)
        - Mixed providers: Sequential (safest approach)
        
        Args:
            layers: List of (layer, layer_props) tuples to filter
            filter_func: Function to call for each layer: filter_func(provider_type, layer, layer_props)
            task_parameters: Shared task parameters
            progress_callback: Optional callback(current, total, layer_name) for progress updates
            cancel_check: Optional callback() -> bool to check if canceled
        
        Returns:
            List[FilterResult]: Results for each layer
        """
        self._canceled = False
        self._results = []
        
        layer_count = len(layers)
        
        # Don't parallelize for small layer counts
        if layer_count < self.MIN_LAYERS_FOR_PARALLEL:
            logger.info(f"Only {layer_count} layer(s) - using sequential execution")
            return self._filter_sequential(layers, filter_func, progress_callback, cancel_check)
        
        # CRITICAL THREAD SAFETY FIX (v2.3.9):
        # Check if ANY layer uses OGR provider - if so, MUST use sequential execution
        # OGR operations manipulate QGIS layer objects directly which is NOT thread-safe
        has_ogr_layers = False
        provider_types = set()
        
        # CRITICAL SQLITE LOCKING FIX (v2.4.2):
        # Track layers by their source database file. Layers sharing the same SQLite/GeoPackage
        # file MUST be filtered sequentially to prevent "unable to open database file" errors.
        # SQLite has single-writer limitation - parallel writes to same DB cause locking issues.
        database_file_counts = {}  # file_path -> count of layers using it
        
        for layer, layer_props in layers:
            provider_type = layer_props.get('_effective_provider_type', 'ogr')
            if hasattr(layer, 'providerType'):
                if layer.providerType() == 'postgres':
                    provider_type = 'postgresql'
                elif layer.providerType() == 'spatialite':
                    provider_type = 'spatialite'
                elif layer.providerType() == 'ogr':
                    provider_type = 'ogr'
            
            provider_types.add(provider_type)
            if provider_type == 'ogr':
                has_ogr_layers = True
            
            # Track database files for Spatialite/OGR layers
            if provider_type in ('spatialite', 'ogr') and hasattr(layer, 'source'):
                try:
                    source = layer.source()
                    if source:
                        # Extract file path from source (format: /path/to/file.gpkg|layername=...)
                        file_path = source.split('|')[0].lower()
                        if file_path.endswith(('.gpkg', '.sqlite', '.db', '.spatialite')):
                            database_file_counts[file_path] = database_file_counts.get(file_path, 0) + 1
                except Exception:
                    pass
        
        # Check if any database file has multiple layers - force sequential for shared databases
        shared_database_files = [f for f, count in database_file_counts.items() if count > 1]
        if shared_database_files:
            max_layers = max(database_file_counts.values())
            logger.warning(
                f"⚠️ Multiple layers share the same SQLite database - using SEQUENTIAL execution. "
                f"SQLite has single-writer limitation. "
                f"{len(shared_database_files)} shared database(s), max {max_layers} layers/db. "
                f"Providers: {provider_types}"
            )
            return self._filter_sequential(layers, filter_func, progress_callback, cancel_check)
        
        # Force sequential execution for OGR layers to prevent access violations
        if has_ogr_layers:
            logger.warning(
                f"⚠️ OGR layers detected - using SEQUENTIAL execution for thread safety. "
                f"Parallel execution of OGR operations causes access violations because "
                f"QGIS layer objects are not thread-safe. "
                f"Providers: {provider_types}"
            )
            return self._filter_sequential(layers, filter_func, progress_callback, cancel_check)
        
        # Also force sequential if geometric filtering is enabled (uses layer operations)
        filtering_params = task_parameters.get("filtering", {})
        is_geometric = filtering_params.get("filter_type") == "geometric"
        
        if is_geometric:
            logger.warning(
                f"⚠️ Geometric filtering detected - using SEQUENTIAL execution for thread safety. "
                f"Geometric operations use selectByLocation which is not thread-safe."
            )
            return self._filter_sequential(layers, filter_func, progress_callback, cancel_check)
        
        logger.info(f"🚀 Starting parallel filtering of {layer_count} layers with {self._max_workers} workers")
        logger.info(f"   Providers: {provider_types} (all database-backed, parallel OK)")
        start_time = time.time()
        
        # Track completion
        completed_count = 0
        
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            # Submit all layer filtering jobs
            future_to_layer: Dict[Future, Tuple[Any, Dict, str]] = {}
            
            for layer, layer_props in layers:
                # Determine provider type from layer or props
                provider_type = layer_props.get('_effective_provider_type', 'ogr')
                if hasattr(layer, 'providerType'):
                    if layer.providerType() == 'postgres':
                        provider_type = 'postgresql'
                    elif layer.providerType() == 'spatialite':
                        provider_type = 'spatialite'
                    elif layer.providerType() == 'ogr':
                        provider_type = 'ogr'
                
                # Submit job
                future = executor.submit(
                    self._filter_single_layer,
                    filter_func,
                    provider_type,
                    layer,
                    layer_props
                )
                future_to_layer[future] = (layer, layer_props, provider_type)
            
            # Collect results as they complete
            for future in as_completed(future_to_layer):
                if cancel_check and cancel_check():
                    self._canceled = True
                    logger.warning("⚠️ Parallel filtering canceled")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                
                layer, layer_props, provider_type = future_to_layer[future]
                layer_name = layer.name() if hasattr(layer, 'name') else str(layer)
                
                try:
                    result = future.result(timeout=300)  # 5 minute timeout per layer
                    
                    with self._lock:
                        self._results.append(result)
                        completed_count += 1
                    
                    if progress_callback:
                        progress_callback(completed_count, layer_count, layer_name)
                    
                    status = "✓" if result.success else "✗"
                    logger.info(f"{status} {layer_name}: {result.feature_count} features ({result.execution_time_ms:.0f}ms)")
                    
                except Exception as e:
                    error_result = FilterResult(
                        layer_id=layer.id() if hasattr(layer, 'id') else str(id(layer)),
                        layer_name=layer_name,
                        success=False,
                        feature_count=0,
                        execution_time_ms=0.0,
                        error_message=str(e)
                    )
                    
                    with self._lock:
                        self._results.append(error_result)
                        completed_count += 1
                    
                    logger.error(f"✗ {layer_name}: {e}")
        
        total_time = (time.time() - start_time) * 1000
        success_count = sum(1 for r in self._results if r.success)
        
        logger.info(f"📊 Parallel filtering complete: {success_count}/{layer_count} succeeded in {total_time:.0f}ms")
        
        return self._results
    
    def _filter_single_layer(
        self,
        filter_func: Callable,
        provider_type: str,
        layer: Any,
        layer_props: Dict
    ) -> FilterResult:
        """
        Filter a single layer (called in worker thread).
        
        STABILITY FIX v2.3.9: Added layer validation to prevent access violations
        when layer becomes invalid during parallel filtering.
        
        Args:
            filter_func: Filtering function to call
            provider_type: Provider type string
            layer: QgsVectorLayer to filter
            layer_props: Layer properties dict
        
        Returns:
            FilterResult: Result of the operation
        """
        # STABILITY FIX v2.3.9: Validate layer before any operations
        # This prevents crashes when layer is deleted/invalidated during parallel execution
        try:
            if layer is None:
                return FilterResult(
                    layer_id="unknown",
                    layer_name="unknown",
                    success=False,
                    feature_count=0,
                    execution_time_ms=0.0,
                    error_message="Layer is None"
                )
            
            # Check if layer is still valid (C++ object not deleted)
            try:
                layer_name = layer.name()
                layer_id = layer.id()
                if not layer.isValid():
                    return FilterResult(
                        layer_id=layer_id,
                        layer_name=layer_name,
                        success=False,
                        feature_count=0,
                        execution_time_ms=0.0,
                        error_message="Layer is not valid"
                    )
            except (RuntimeError, AttributeError) as access_error:
                return FilterResult(
                    layer_id=str(id(layer)),
                    layer_name="deleted_layer",
                    success=False,
                    feature_count=0,
                    execution_time_ms=0.0,
                    error_message=f"Layer C++ object deleted: {access_error}"
                )
        except Exception as validation_error:
            return FilterResult(
                layer_id=str(id(layer)) if layer else "unknown",
                layer_name="unknown",
                success=False,
                feature_count=0,
                execution_time_ms=0.0,
                error_message=f"Layer validation failed: {validation_error}"
            )
        
        start_time = time.time()
        
        # FIX v3.0.8: Log each layer being filtered
        logger.info(f"🔄 _filter_single_layer: Filtering '{layer_name}' (provider={provider_type})")
        from qgis.core import QgsMessageLog, Qgis
        QgsMessageLog.logMessage(
            f"🔄 Filtering: {layer_name} ({provider_type})",
            "FilterMate", Qgis.Info
        )
        
        try:
            # Call the actual filter function
            success = filter_func(provider_type, layer, layer_props)
            
            # FIX v3.0.8: Log result
            logger.info(f"  → {layer_name}: filter_func returned {success}")
            
            # Get feature count after filtering
            feature_count = 0
            if hasattr(layer, 'featureCount'):
                try:
                    feature_count = layer.featureCount()
                except Exception:
                    pass
            
            execution_time = (time.time() - start_time) * 1000
            
            return FilterResult(
                layer_id=layer_id,
                layer_name=layer_name,
                success=bool(success),
                feature_count=feature_count,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            # FIX v3.0.8: Log exceptions
            logger.error(f"  → {layer_name}: Exception in filter_func: {e}")
            execution_time = (time.time() - start_time) * 1000
            
            return FilterResult(
                layer_id=layer_id,
                layer_name=layer_name,
                success=False,
                feature_count=0,
                execution_time_ms=execution_time,
                error_message=str(e)
            )
    
    def _filter_sequential(
        self,
        layers: List[Tuple[Any, Dict]],
        filter_func: Callable,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> List[FilterResult]:
        """
        Filter layers sequentially (fallback for small layer counts).
        
        STABILITY FIX v2.3.13: Adds inter-layer delay for GeoPackage layers
        to allow SQLite file locks to release between operations.
        
        STABILITY FIX v2.4.2: Extended to handle Spatialite and all SQLite-based
        databases (.gpkg, .sqlite, .db, .spatialite). Increased delay and added
        retry logic for persistent locking issues.
        
        Args:
            layers: List of (layer, layer_props) tuples
            filter_func: Filter function to call
            progress_callback: Progress callback
            cancel_check: Cancellation check callback
        
        Returns:
            List[FilterResult]: Results
        """
        import time
        
        results = []
        layer_count = len(layers)
        
        # FIX v3.0.8: Log entry to sequential filter
        logger.info(f"🔄 _filter_sequential: Starting with {layer_count} layers")
        from qgis.core import QgsMessageLog, Qgis
        QgsMessageLog.logMessage(
            f"🔄 Using SEQUENTIAL filtering for {layer_count} layers",
            "FilterMate", Qgis.Info
        )
        
        # FIX v3.0.8: Log layer names to be processed
        layer_names = []
        for l, lp in layers:
            try:
                layer_names.append(l.name() if hasattr(l, 'name') else 'unknown')
            except Exception:  # FIX v3.0.20: Avoid bare except clause
                layer_names.append('invalid')
        logger.info(f"🔄 Layers to process: {layer_names}")
        QgsMessageLog.logMessage(
            f"📋 Layers queue: {', '.join(layer_names)}",
            "FilterMate", Qgis.Info
        )
        
        # FIX v3.0.8: Check cancel_check status at start
        if cancel_check:
            initial_cancel_state = cancel_check()
            logger.info(f"🔄 cancel_check at start = {initial_cancel_state}")
            if initial_cancel_state:
                logger.warning(f"⚠️ cancel_check() is already True at start - this will skip all layers!")
                QgsMessageLog.logMessage(
                    f"⚠️ Task already cancelled before filtering started!",
                    "FilterMate", Qgis.Warning
                )
        
        # STABILITY FIX v2.4.2: Track SQLite database file paths for inter-layer delay
        # When multiple layers from the same SQLite database are processed sequentially,
        # add a delay between operations to allow SQLite locks to release.
        # This applies to: GeoPackage (.gpkg), Spatialite (.sqlite, .spatialite, .db)
        last_db_path = None
        
        # Count layers per database for adaptive delay calculation
        db_layer_counts = {}
        for layer, layer_props in layers:
            db_path = self._get_layer_database_path(layer)
            if db_path:
                db_layer_counts[db_path] = db_layer_counts.get(db_path, 0) + 1
        
        for i, (layer, layer_props) in enumerate(layers):
            # FIX v3.0.9: DISABLED cancel_check during distant layer filtering
            # RATIONALE: Once distant layer filtering has started, we MUST complete all layers.
            # The cancel_check (which calls QgsTask.isCanceled()) can return True spuriously when:
            # 1. processing.run("native:selectbylocation") modifies layer selection state
            # 2. This triggers Qt events that QGIS TaskManager interprets as layer modification
            # 3. TaskManager then auto-cancels tasks with "dependent" layers (even if we didn't set any)
            # 
            # SOLUTION: Ignore cancel_check during sequential filtering. The user can still cancel
            # the overall filter task, but the distant layers will all be processed.
            # This matches the expected behavior: filter is applied to ALL distant layers atomically.
            #
            # Previous code that was causing premature stops:
            # if cancel_check and cancel_check():
            #     layer_name = layer.name() if hasattr(layer, 'name') else f"layer_{i}"
            #     logger.warning(f"⚠️ _filter_sequential: cancel_check() returned True at layer {i+1}/{len(layers)} ({layer_name}) - breaking loop")
            #     break
            #
            # If truly needed, we can check ONLY at the very beginning (already done above)
            
            provider_type = layer_props.get('_effective_provider_type', 'ogr')
            
            # Get current layer's database path
            current_db_path = self._get_layer_database_path(layer)
            
            # STABILITY FIX v2.4.2: Add inter-layer delay for same SQLite database
            # Delay is adaptive based on number of layers sharing the database
            if current_db_path and current_db_path == last_db_path:
                # Calculate adaptive delay: more layers = longer delay
                layer_count_in_db = db_layer_counts.get(current_db_path, 1)
                if layer_count_in_db > 10:
                    delay = 0.5  # 500ms for large number of layers
                elif layer_count_in_db > 5:
                    delay = 0.3  # 300ms for medium number of layers
                else:
                    delay = 0.2  # 200ms for small number of layers
                
                time.sleep(delay)
            
            result = self._filter_single_layer(filter_func, provider_type, layer, layer_props)
            results.append(result)
            
            # Track last database path for next iteration
            if current_db_path:
                last_db_path = current_db_path
            
            if progress_callback:
                layer_name = layer.name() if hasattr(layer, 'name') else str(layer)
                progress_callback(i + 1, layer_count, layer_name)
        
        # FIX v3.0.8: Log completion summary
        logger.info(f"✓ _filter_sequential completed: {len(results)}/{len(layers)} layers processed")
        from qgis.core import QgsMessageLog, Qgis
        QgsMessageLog.logMessage(
            f"✓ Sequential filtering completed: {len(results)}/{len(layers)} layers",
            "FilterMate", Qgis.Info
        )
        
        return results
    
    def _get_layer_database_path(self, layer) -> Optional[str]:
        """
        Extract the database file path from a layer's source.
        
        Works with:
        - GeoPackage (.gpkg)
        - Spatialite (.sqlite, .spatialite, .db)
        - Native spatialite provider layers
        - OGR provider layers
        
        Args:
            layer: QgsVectorLayer to check
            
        Returns:
            Lowercase database file path or None if not SQLite-based
        """
        try:
            if not hasattr(layer, 'source'):
                return None
            
            source = layer.source()
            if not source:
                return None
            
            # Extract file path (format: /path/to/file.gpkg|layername=... or dbname='/path/...')
            file_path = None
            
            if '|' in source:
                # OGR format: /path/to/file.gpkg|layername=xxx
                file_path = source.split('|')[0]
            elif "dbname='" in source:
                # Spatialite format: dbname='/path/to/file.sqlite' ...
                import re
                match = re.search(r"dbname='([^']+)'", source)
                if match:
                    file_path = match.group(1)
            elif "dbname=\"" in source:
                import re
                match = re.search(r'dbname="([^"]+)"', source)
                if match:
                    file_path = match.group(1)
            else:
                file_path = source
            
            if file_path:
                file_path_lower = file_path.lower()
                if file_path_lower.endswith(('.gpkg', '.sqlite', '.db', '.spatialite')):
                    return file_path_lower
            
            return None
        except Exception:
            return None
    
    def get_results(self) -> List[FilterResult]:
        """Get results from last parallel operation."""
        return self._results
    
    def was_canceled(self) -> bool:
        """Check if last operation was canceled."""
        return self._canceled
    
    @property
    def max_workers(self) -> int:
        """Get maximum worker count."""
        return self._max_workers


# Configuration for parallel execution
class ParallelConfig:
    """
    Configuration for parallel filter execution.
    
    Allows tuning parallel execution behavior based on
    system capabilities and user preferences.
    """
    
    # Enable/disable parallel execution globally
    ENABLED = True
    
    # Minimum layers to trigger parallel execution
    MIN_LAYERS_THRESHOLD = 2
    
    # Maximum workers (0 = auto-detect based on CPU count)
    MAX_WORKERS = 0
    
    # Timeout per layer in seconds
    LAYER_TIMEOUT = 300
    
    def __init__(self, max_workers: Optional[int] = None, 
                 min_layers_for_parallel: int = 2,
                 enabled: bool = True,
                 layer_timeout: int = 300):
        """
        Initialize ParallelConfig with optional custom values.
        
        Args:
            max_workers: Maximum number of worker threads (None or 0 = auto-detect)
            min_layers_for_parallel: Minimum layers to trigger parallel execution
            enabled: Enable/disable parallel execution
            layer_timeout: Timeout per layer in seconds
        """
        # Treat 0 as auto-detect (None)
        if max_workers is not None and max_workers <= 0:
            max_workers = None
        self.max_workers = max_workers
        self.min_layers_for_parallel = min_layers_for_parallel
        self.enabled = enabled
        self.layer_timeout = layer_timeout
    
    @classmethod
    def is_parallel_recommended(cls, layer_count: int, total_features: int) -> bool:
        """
        Determine if parallel execution is recommended.
        
        Args:
            layer_count: Number of layers to filter
            total_features: Total features across all layers
        
        Returns:
            bool: True if parallel execution recommended
        """
        if not cls.ENABLED:
            return False
        
        if layer_count < cls.MIN_LAYERS_THRESHOLD:
            return False
        
        # For very large datasets, parallel execution helps
        if total_features > 100000:
            return True
        
        # For many layers, parallel execution helps
        if layer_count >= 4:
            return True
        
        return layer_count >= 2

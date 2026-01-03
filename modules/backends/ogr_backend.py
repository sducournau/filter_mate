# -*- coding: utf-8 -*-
"""
OGR Backend for FilterMate

Fallback backend for OGR-based providers (Shapefiles, GeoPackage, etc.).
Uses QGIS processing algorithms for filtering since OGR providers don't support
complex SQL expressions like PostgreSQL/Spatialite.

CRITICAL THREAD SAFETY (v2.3.9, v2.3.12):
=========================================
This backend manipulates QGIS layer objects directly (selectedFeatures, etc.)
which are NOT thread-safe when used with signals.

v2.3.12 FIX: Replaced startEditing/commitChanges with direct data provider calls.
- startEditing/commitChanges trigger layer modification signals
- Main thread UI (QgsLayerTreeModel) receives these signals
- This causes "Windows fatal exception: access violation"
- Using dataProvider().changeAttributeValues() bypasses signals

OGR backend operations still run sequentially for safety, but the direct
provider approach is more robust and avoids signal-related crashes.

The ParallelFilterExecutor automatically detects OGR layers and forces 
sequential execution for additional safety.

GDAL ERROR HANDLING (v2.3.11):
==============================
GeoPackage layers may generate transient SQLite warnings during concurrent
operations. These are handled via GdalErrorHandler which suppresses known
harmless warnings like "unable to open database file".

v2.4.0 Improvements:
====================
- Automatic spatial index creation for file-based formats
- Improved index detection and management

v2.6.2 Improvements:
====================
- CRITICAL FIX: Interruptible processing with cancellation support
- CancellableFeedback class for immediate query termination
- Task cancellation checks before and during processing operations
"""

import threading
from typing import Dict, Optional
from qgis.core import (
    QgsVectorLayer, 
    QgsProcessingFeedback, 
    QgsWkbTypes,
    QgsGeometry,
    QgsFeature,
    QgsMemoryProviderUtils
)
from qgis import processing
from .base_backend import GeometricFilterBackend
from ..logging_config import get_tasks_logger
from ..appUtils import safe_set_subset_string

# Import geometry safety module (v2.3.9 - stability fix)
from ..geometry_safety import (
    validate_geometry,
    validate_geometry_for_geos,
    safe_as_geometry_collection,
    safe_as_polygon,
    safe_collect_geometry,
    safe_convert_to_multi_polygon,
    extract_polygons_from_collection,
    get_geometry_type_name,
    create_geos_safe_layer
)

# Import GDAL error handler for suppressing transient SQLite warnings (v2.3.11)
from ..object_safety import GdalErrorHandler

# Import Spatial Index Manager for automatic index creation (v2.4.0)
try:
    from .spatial_index_manager import get_spatial_index_manager, SpatialIndexManager
    SPATIAL_INDEX_MANAGER_AVAILABLE = True
except ImportError:
    SPATIAL_INDEX_MANAGER_AVAILABLE = False
    get_spatial_index_manager = None
    SpatialIndexManager = None

# v2.5.10: Import Multi-Step Optimizer for attribute-first filtering
try:
    from .multi_step_optimizer import (
        MultiStepFilterOptimizer,
        MultiStepPlanBuilder,
        BackendFilterStrategy,
        AttributePreFilter,
        OGROptimizer,
        BackendSelectivityEstimator
    )
    MULTI_STEP_OPTIMIZER_AVAILABLE = True
except ImportError:
    MULTI_STEP_OPTIMIZER_AVAILABLE = False
    MultiStepFilterOptimizer = None
    MultiStepPlanBuilder = None
    BackendFilterStrategy = None
    AttributePreFilter = None
    OGROptimizer = None
    BackendSelectivityEstimator = None

logger = get_tasks_logger()

# Thread safety tracking (v2.3.9)
_ogr_operations_lock = threading.Lock()
_last_operation_thread = None


class CancellableFeedback(QgsProcessingFeedback):
    """
    v2.6.2: QgsProcessingFeedback subclass that checks for task cancellation.
    
    This allows processing algorithms to be interrupted when the parent task
    is cancelled, preventing QGIS from freezing on long operations.
    
    Usage:
        feedback = CancellableFeedback(cancel_check=lambda: task.isCanceled())
        processing.run("native:selectbylocation", {...}, feedback=feedback)
    """
    
    def __init__(self, cancel_check=None):
        """
        Initialize cancellable feedback.
        
        Args:
            cancel_check: Callable that returns True if operation should be cancelled
        """
        super().__init__()
        self._cancel_check = cancel_check
        self._is_canceled = False
    
    def isCanceled(self) -> bool:
        """Check if operation is cancelled."""
        if self._is_canceled:
            return True
        if self._cancel_check and self._cancel_check():
            self._is_canceled = True
            return True
        return super().isCanceled()
    
    def cancel(self):
        """Cancel the operation."""
        self._is_canceled = True
        super().cancel()


def escape_ogr_identifier(identifier: str) -> str:
    """
    Escape identifier for OGR SQL expressions.
    
    OGR uses double quotes for identifiers but has limited support.
    Some formats (Shapefile) have restrictions on field names.
    
    Args:
        identifier: Field or table name
        
    Returns:
        Escaped identifier
    """
    # Remove problematic characters and truncate if needed
    # Note: This is a basic implementation. Different OGR drivers have different rules.
    if ' ' in identifier:
        logger.warning(f"OGR identifier '{identifier}' contains spaces - may cause issues with some formats")
    
    # Always use double quotes for OGR
    return f'"{identifier}"'


class OGRGeometricFilter(GeometricFilterBackend):
    """
    OGR backend for geometric filtering.
    
    This backend provides filtering for OGR-based layers (Shapefiles, GeoPackage, etc.) using:
    - QGIS processing algorithms (selectbylocation)
    - Memory-based filtering
    - Compatible with all OGR-supported formats
    """
    
    def __init__(self, task_params: Dict):
        """
        Initialize OGR backend.
        
        Args:
            task_params: Task parameters dictionary
        """
        super().__init__(task_params)
        self.logger = logger
    
    def _is_task_canceled(self) -> bool:
        """
        v2.6.2: Check if the parent task was canceled.
        
        Returns:
            True if task was canceled, False otherwise
        """
        if hasattr(self, 'task_params') and self.task_params:
            task = self.task_params.get('_parent_task')
            if task and hasattr(task, 'isCanceled'):
                return task.isCanceled()
        return False
    
    def _create_cancellable_feedback(self) -> CancellableFeedback:
        """
        v2.6.2: Create a CancellableFeedback instance linked to parent task.
        
        Returns:
            CancellableFeedback instance
        """
        return CancellableFeedback(cancel_check=self._is_task_canceled)
    
    def supports_layer(self, layer: QgsVectorLayer) -> bool:
        """
        Check if this backend supports the given layer.
        
        Args:
            layer: QGIS vector layer to check
        
        Returns:
            True if layer is from OGR provider or any other provider
        """
        # This is the fallback backend, supports everything
        return True
    
    def _ensure_spatial_index(self, layer: QgsVectorLayer) -> bool:
        """
        Ensure spatial index exists for the layer.
        
        Creates spatial index if not present. For shapefiles, this creates a .qix file.
        For other formats, may create internal index.
        
        v2.4.0: Uses SpatialIndexManager for improved index handling.
        
        Performance: O(n log n) creation time, but O(log n) queries afterward.
        Gain: 4-100× faster spatial queries depending on dataset size.
        
        Args:
            layer: Layer to check/create index for
        
        Returns:
            True if index exists or was created successfully
        """
        # v2.4.0: Use SpatialIndexManager if available
        if SPATIAL_INDEX_MANAGER_AVAILABLE:
            try:
                manager = get_spatial_index_manager()
                return manager.ensure_index(layer)
            except Exception as e:
                self.log_warning(f"SpatialIndexManager error: {e}, falling back to legacy method")
        
        # Legacy fallback
        try:
            # Check if spatial index already exists
            if layer.hasSpatialIndex():
                self.log_debug(f"✓ Spatial index already exists for {layer.name()}")
                return True
            
            # Try to create spatial index
            self.log_info(f"Creating spatial index for {layer.name()}...")
            
            # For OGR layers, use QGIS processing to create index
            try:
                result = processing.run("native:createspatialindex", {
                    'INPUT': layer
                })
                
                if layer.hasSpatialIndex():
                    self.log_info(f"✓ Spatial index created successfully for {layer.name()}")
                    return True
                else:
                    self.log_warning(
                        f"Spatial index creation completed but layer.hasSpatialIndex() returns False. "
                        f"This may be normal for some formats."
                    )
                    return True  # Consider it success anyway
                    
            except Exception as create_error:
                self.log_warning(
                    f"Could not create spatial index for {layer.name()}: {str(create_error)}. "
                    f"Continuing without index (performance may be reduced)."
                )
                return False
                
        except Exception as e:
            self.log_warning(f"Error checking spatial index: {str(e)}. Continuing anyway.")
            return False
    
    def _should_clear_old_subset(self, old_subset: Optional[str]) -> bool:
        """
        Check if old_subset contains patterns that indicate it should be cleared.
        
        This prevents combining with corrupted or incompatible previous filters.
        
        Invalid patterns:
        1. __source alias (PostgreSQL EXISTS subquery internal alias)
        2. EXISTS subquery (would create nested subqueries)
        3. Spatial predicates (likely from previous geometric filter)
        
        Args:
            old_subset: The existing subset string to check
            
        Returns:
            True if old_subset should be cleared (not combined with)
        """
        if not old_subset:
            return False
        
        old_subset_upper = old_subset.upper()
        
        # Pattern 1: __source alias (only valid inside PostgreSQL EXISTS subqueries)
        has_source_alias = '__source' in old_subset.lower()
        
        # Pattern 2: EXISTS subquery (avoid nested EXISTS)
        has_exists = 'EXISTS (' in old_subset_upper or 'EXISTS(' in old_subset_upper
        
        # Pattern 3: Spatial predicates from various backends
        # These indicate a previous geometric filter that should be replaced
        spatial_predicates = [
            # PostGIS/Spatialite predicates
            'ST_INTERSECTS', 'ST_CONTAINS', 'ST_WITHIN', 'ST_TOUCHES',
            'ST_OVERLAPS', 'ST_CROSSES', 'ST_DISJOINT', 'ST_EQUALS',
            'ST_DWITHIN', 'ST_COVERS', 'ST_COVEREDBY',
            # Spatialite-specific
            'INTERSECTS', 'CONTAINS', 'WITHIN'
        ]
        has_spatial_predicate = any(pred in old_subset_upper for pred in spatial_predicates)
        
        should_clear = has_source_alias or has_exists or has_spatial_predicate
        
        if should_clear:
            reason = []
            if has_source_alias:
                reason.append("contains __source alias")
            if has_exists:
                reason.append("contains EXISTS subquery")
            if has_spatial_predicate:
                reason.append("contains spatial predicate")
            
            self.log_warning(f"⚠️ Invalid old_subset detected - {', '.join(reason)}")
            self.log_warning(f"  → Subset: '{old_subset[:100]}...'")
            self.log_info(f"  → Will replace instead of combine")
        
        return should_clear

    def _try_multi_step_filter(
        self,
        layer: QgsVectorLayer,
        attribute_filter: Optional[str],
        source_layer: QgsVectorLayer,
        predicates: Dict,
        buffer_value: Optional[float],
        old_subset: Optional[str],
        combine_operator: Optional[str]
    ) -> Optional[bool]:
        """
        Try multi-step filter optimization for large datasets.
        
        v2.5.10: Uses attribute-first strategy when beneficial.
        
        This method analyzes the filter operation and determines if a multi-step
        approach would be more efficient than direct spatial filtering:
        
        1. If attribute filter is very selective (<30%), apply it first to reduce
           the number of features that need expensive spatial calculations.
        2. For very large datasets, use chunked processing.
        
        Args:
            layer: Target layer to filter
            attribute_filter: Optional attribute expression
            source_layer: Source layer for spatial filter
            predicates: Spatial predicates to apply
            buffer_value: Optional buffer value
            old_subset: Existing subset string
            combine_operator: Operator to combine with existing filter
            
        Returns:
            True if filter succeeded, False if failed, None if should fall back to standard
        """
        if not MULTI_STEP_OPTIMIZER_AVAILABLE:
            return None  # Fall back to standard
        
        try:
            feature_count = layer.featureCount()
            
            # Only use multi-step for medium-large datasets
            if feature_count < 5000:
                return None  # Standard method is fine
            
            # Get source extent for selectivity estimation
            source_extent = source_layer.extent() if source_layer else None
            
            # Create optimizer and build plan
            optimizer = MultiStepFilterOptimizer(layer, self.task_params)
            plan = optimizer.analyze_and_plan(
                attribute_filter=attribute_filter,
                spatial_filter_extent=source_extent,
                has_spatial_filter=True
            )
            
            # Check if multi-step is beneficial
            if plan.strategy == BackendFilterStrategy.DIRECT:
                return None  # Use standard method
            
            if plan.strategy == BackendFilterStrategy.ATTRIBUTE_FIRST:
                self.log_info(
                    f"🚀 Using ATTRIBUTE-FIRST strategy for {layer.name()} "
                    f"(selectivity: {plan.estimated_selectivity:.1%})"
                )
                
                # Step 1: Get FIDs matching attribute filter
                prefiltered_fids = optimizer.execute_attribute_prefilter(attribute_filter)
                
                if not prefiltered_fids:
                    # No matches - apply empty filter
                    # v2.6.9: FIX - Use unquoted 'fid = -1' for OGR/GeoPackage compatibility
                    self.log_info("Attribute pre-filter returned 0 matches")
                    empty_filter = 'fid = -1'  # No valid FID is -1
                    queue_callback = self.task_params.get('_subset_queue_callback')
                    if queue_callback:
                        queue_callback(layer, empty_filter)
                    else:
                        from ..appUtils import safe_set_subset_string
                        safe_set_subset_string(layer, empty_filter)
                    return True
                
                self.log_info(
                    f"  → Attribute pre-filter: {len(prefiltered_fids)}/{feature_count} features "
                    f"({len(prefiltered_fids)/feature_count*100:.1f}%)"
                )
                
                # Step 2: Create a temporary layer with only pre-filtered features
                # and run spatial filter on that reduced set
                from qgis.core import QgsFeatureRequest, QgsVectorLayer, QgsMemoryProviderUtils
                
                # Build a temporary layer with pre-filtered features
                request = QgsFeatureRequest()
                if len(prefiltered_fids) <= 1000:
                    request.setFilterFids(list(prefiltered_fids))
                else:
                    fid_list = ','.join(str(f) for f in sorted(prefiltered_fids))
                    request.setFilterExpression(f'$id IN ({fid_list})')
                
                # Create memory layer copy
                fields = layer.fields()
                geom_type = layer.wkbType()
                crs = layer.crs()
                
                temp_layer = QgsMemoryProviderUtils.createMemoryLayer(
                    f"{layer.name()}_prefiltered",
                    fields,
                    geom_type,
                    crs
                )
                
                if not temp_layer or not temp_layer.isValid():
                    self.log_warning("Failed to create temp layer, falling back to standard")
                    return None
                
                # Copy features
                provider = temp_layer.dataProvider()
                features = [f for f in layer.getFeatures(request)]
                provider.addFeatures(features)
                temp_layer.updateExtents()
                
                self.log_info(f"  → Created temp layer with {temp_layer.featureCount()} features")
                
                # Step 3: Apply spatial filter on reduced set
                # Apply buffer if needed
                intersect_layer = self._apply_buffer(source_layer, buffer_value)
                if intersect_layer is None:
                    return False
                
                # Map predicates
                predicate_codes = self._map_predicates(predicates)
                
                # Run selectbylocation on temp layer
                if not self._safe_select_by_location(temp_layer, intersect_layer, predicate_codes):
                    self.log_warning("Spatial selection on temp layer failed")
                    return None
                
                # Get final matching IDs
                final_matching = set()
                for feat in temp_layer.selectedFeatures():
                    # Need to map back to original layer FIDs
                    # Features in temp layer have same attribute values
                    final_matching.add(feat.id())
                
                # The FIDs in temp_layer match the original because we copied them
                # But we need to use the attribute values to find original FIDs
                from ..appUtils import get_primary_key_name
                pk_field = get_primary_key_name(layer)
                
                if pk_field:
                    # Get PK values from selected temp features
                    pk_values = []
                    for feat in temp_layer.selectedFeatures():
                        pk_val = feat.attribute(pk_field)
                        if pk_val is not None:
                            pk_values.append(pk_val)
                    
                    if pk_values:
                        # Build subset expression
                        from qgis.PyQt.QtCore import QMetaType
                        field_idx = layer.fields().indexFromName(pk_field)
                        field_type = layer.fields()[field_idx].type()
                        
                        if field_type == QMetaType.Type.QString:
                            pk_list = ','.join(f"'{str(v).replace(chr(39), chr(39)+chr(39))}'" for v in pk_values)
                        else:
                            pk_list = ','.join(str(v) for v in pk_values)
                        
                        new_expression = f'"{pk_field}" IN ({pk_list})'
                    else:
                        # v2.6.9: FIX - Use unquoted 'fid = -1' for OGR/GeoPackage compatibility
                        new_expression = 'fid = -1'  # No valid FID is -1
                else:
                    # Fall back to $id
                    selected_ids = [f.id() for f in temp_layer.selectedFeatures()]
                    if selected_ids:
                        id_list = ','.join(str(fid) for fid in selected_ids)
                        new_expression = f'$id IN ({id_list})'
                    else:
                        # v2.6.9: FIX - Use unquoted 'fid = -1' for OGR/GeoPackage compatibility
                        new_expression = 'fid = -1'  # No valid FID is -1
                
                # Combine with old subset if needed
                if old_subset and not self._should_clear_old_subset(old_subset):
                    if not combine_operator:
                        combine_operator = 'AND'
                    final_expression = f"({old_subset}) {combine_operator} ({new_expression})"
                else:
                    final_expression = new_expression
                
                # Apply filter
                queue_callback = self.task_params.get('_subset_queue_callback')
                if queue_callback:
                    queue_callback(layer, final_expression)
                    self.log_info(f"✓ Multi-step filter queued for {layer.name()}")
                else:
                    from ..appUtils import safe_set_subset_string
                    safe_set_subset_string(layer, final_expression)
                    self.log_info(f"✓ Multi-step filter applied to {layer.name()}")
                
                return True
            
            elif plan.strategy == BackendFilterStrategy.PROGRESSIVE_CHUNKS:
                self.log_info(
                    f"🔄 Using PROGRESSIVE_CHUNKS strategy for {layer.name()} "
                    f"(chunk_size: {plan.chunk_size})"
                )
                # For now, fall back to standard for chunked processing
                # TODO: Implement chunked spatial filtering
                return None
            
            # Other strategies: fall back to standard
            return None
            
        except Exception as e:
            self.log_warning(f"Multi-step filter failed: {e}, falling back to standard")
            import traceback
            self.log_debug(traceback.format_exc())
            return None

    def build_expression(
        self,
        layer_props: Dict,
        predicates: Dict,
        source_geom: Optional[str] = None,
        buffer_value: Optional[float] = None,
        buffer_expression: Optional[str] = None,
        source_filter: Optional[str] = None,
        use_centroids: bool = False,
        **kwargs
    ) -> str:
        """
        Build expression for OGR backend.
        
        Note: OGR backend uses QGIS processing algorithms, so we don't build
        SQL expressions. This method returns a serialized dict of parameters.
        
        Args:
            layer_props: Layer properties
            predicates: Spatial predicates to apply
            source_geom: Source geometry (layer reference)
            buffer_value: Buffer distance
            buffer_expression: Expression for dynamic buffer
            source_filter: Source layer filter (not used in OGR)
            use_centroids: If True, source layer centroids are used (already applied in prepare_ogr_source_geom)
            **kwargs: Additional backend-specific parameters (ignored)
        
        Returns:
            JSON string with processing parameters
        """
        self.log_debug(f"Preparing OGR processing for {layer_props.get('layer_name', 'unknown')}")
        
        # Log buffer parameters for debugging
        self.log_info(f"📐 OGR build_expression - Buffer parameters:")
        self.log_info(f"  - buffer_value: {buffer_value}")
        self.log_info(f"  - buffer_expression: {buffer_expression}")
        if buffer_value is not None and buffer_value < 0:
            self.log_info(f"  ⚠️ NEGATIVE BUFFER (erosion) requested: {buffer_value}m")
        
        # Store source_geom for later use in apply_filter
        self.source_geom = source_geom
        
        # For OGR, we'll use QGIS processing, so we return predicate names and buffer params
        # The actual filtering will be done in apply_filter()
        # CRITICAL FIX: Pass buffer_value to apply_filter for application there
        import json
        params = {
            'predicates': list(predicates.keys()),
            'buffer_value': buffer_value,
            'buffer_expression': buffer_expression
        }
        return json.dumps(params)
    
    def apply_filter(
        self,
        layer: QgsVectorLayer,
        expression: str,
        old_subset: Optional[str] = None,
        combine_operator: Optional[str] = None
    ) -> bool:
        """
        Apply filter using QGIS processing selectbylocation algorithm.
        
        CRITICAL THREAD SAFETY (v2.3.9, v2.3.12):
        This method manipulates QGIS layer objects (selectedFeatures, etc.)
        which require careful handling for thread safety.
        
        v2.3.12: Uses data provider directly instead of edit mode to avoid
        layer signals that cause access violations when received by the main thread.
        The ParallelFilterExecutor still forces sequential mode for OGR layers.
        
        Uses optimized method for large datasets (≥10k features):
        - Ensures spatial index exists
        - Uses attribute-based filtering after spatial selection
        
        For PostgreSQL memory optimization (small datasets):
        - Uses memory layer copy for spatial calculations
        - Applies resulting filter to original PostgreSQL layer
        
        Args:
            layer: Layer to filter
            expression: JSON parameters for processing
            old_subset: Existing subset (not used for OGR - uses selection instead)
            combine_operator: Combine operator (not used for OGR)
        
        Returns:
            True if filter applied successfully
        """
        global _last_operation_thread, _ogr_operations_lock
        
        # THREAD SAFETY CHECK (v2.3.9): Detect concurrent access
        current_thread = threading.current_thread().ident
        with _ogr_operations_lock:
            if _last_operation_thread is not None and _last_operation_thread != current_thread:
                self.log_warning(
                    f"⚠️ OGR apply_filter called from different thread! "
                    f"Previous: {_last_operation_thread}, Current: {current_thread}. "
                    f"This may cause access violations. OGR operations are NOT thread-safe."
                )
            _last_operation_thread = current_thread
        
        # GDAL ERROR HANDLING (v2.3.11): Suppress transient SQLite warnings
        # These warnings occur during concurrent GeoPackage access but are handled
        # internally by GDAL/OGR and don't affect operation success.
        with GdalErrorHandler():
            try:
                import json
                from qgis import processing
                
                params = json.loads(expression) if expression else {}
                predicates = params.get('predicates', [])
                buffer_value = params.get('buffer_value')
                
                # Check if using memory optimization for PostgreSQL
                use_memory_opt = getattr(self, '_use_memory_optimization', False)
                memory_layer = getattr(self, '_memory_layer', None)
                original_layer = getattr(self, '_original_layer', None)
                
                if use_memory_opt and memory_layer and original_layer:
                    self.log_info(f"⚡ Using memory optimization for {layer.name()}")
                    return self._apply_filter_with_memory_optimization(
                        original_layer, memory_layer, predicates, buffer_value,
                        old_subset, combine_operator
                    )
                
                self.log_debug(f"Applying OGR filter to {layer.name()} using QGIS processing")
                
                # Get source layer - should be set by build_expression
                source_layer = getattr(self, 'source_geom', None)
                
                # DIAGNOSTIC: Log source layer state
                self.log_info(f"📍 OGR source_geom state for {layer.name()}:")
                if source_layer is None:
                    self.log_error("  → source_geom is None!")
                elif not isinstance(source_layer, QgsVectorLayer):
                    self.log_error(f"  → source_geom is not a QgsVectorLayer: {type(source_layer).__name__}")
                else:
                    self.log_info(f"  → Name: {source_layer.name()}")
                    self.log_info(f"  → Valid: {source_layer.isValid()}")
                    self.log_info(f"  → Feature count: {source_layer.featureCount()}")
                    if source_layer.featureCount() > 0:
                        # Check first geometry
                        for feat in source_layer.getFeatures():
                            geom = feat.geometry()
                            self.log_info(f"  → First geometry valid: {geom is not None and not geom.isEmpty()}")
                            if geom and not geom.isEmpty():
                                self.log_info(f"  → First geometry type: {geom.wkbType()}")
                            break
                
                if not source_layer:
                    self.log_error("No source layer/geometry provided for geometric filtering")
                    return False
                
                # Check feature count and decide on strategy
                feature_count = layer.featureCount()
                
                # Ensure spatial index exists (performance boost)
                self._ensure_spatial_index(layer)
                
                # Only log for large datasets
                if feature_count >= 100000:
                    self.log_info(f"Large dataset ({feature_count:,} features)")
                
                # v2.5.10: Try multi-step filter optimization for large datasets
                # with combined attribute+spatial filters
                if MULTI_STEP_OPTIMIZER_AVAILABLE and feature_count >= 5000:
                    # Check if there's an attribute filter we can use for pre-filtering
                    attribute_filter = old_subset if old_subset and not self._should_clear_old_subset(old_subset) else None
                    
                    if attribute_filter or feature_count >= 50000:
                        multi_result = self._try_multi_step_filter(
                            layer, attribute_filter, source_layer, predicates,
                            buffer_value, old_subset, combine_operator
                        )
                        
                        if multi_result is not None:
                            return multi_result  # True or False
                        # else: fall through to standard method
                
                # FIX v2.4.6: Use standard method for OGR layers
                # The large dataset optimization (using _fm_match_ temp field) causes
                # SQLite "unable to open database file" errors when:
                # - Multiple layers from the same GeoPackage are filtered simultaneously
                # - The database file is on a network drive or has access issues
                # - The database is opened read-only by another process
                # The standard method is reliable and performs well with spatial indexes.
                return self._apply_filter_standard(
                    layer, source_layer, predicates, buffer_value,
                    old_subset, combine_operator
                )
                
            except Exception as e:
                self.log_error(f"Error applying OGR filter: {str(e)}")
                import traceback
                self.log_debug(f"Traceback: {traceback.format_exc()}")
                return False
    
    def _apply_buffer(self, source_layer, buffer_value):
        """Apply buffer to source layer if specified.
        
        Supports both positive buffers (expansion) and negative buffers (erosion/shrinking).
        Negative buffers only work on polygon geometries - they shrink the polygon inward.
        
        CRITICAL FIX: Handles GeometryCollection results from native:buffer.
        When buffering multiple non-overlapping geometries, QGIS Processing can
        produce GeometryCollection which is incompatible with typed layers (MultiPolygon).
        This method converts GeometryCollection to MultiPolygon for compatibility.
        
        STABILITY FIX v2.3.9: Added source layer validation to prevent access violations.
        
        Uses buffer_type from task_params for END_CAP_STYLE:
        - 0: Round (default)
        - 1: Flat
        - 2: Square
        
        Note on negative buffers:
        - Negative buffer on a polygon shrinks it inward (erosion)
        - Negative buffer on a point or line produces empty geometry
        - Very large negative buffers may collapse the polygon entirely
        """
        # STABILITY FIX v2.3.9: Validate source layer before any operations
        if source_layer is None:
            self.log_error("Source layer is None - cannot apply buffer")
            return None
        
        if not isinstance(source_layer, QgsVectorLayer):
            self.log_error(f"Source layer is not a QgsVectorLayer: {type(source_layer).__name__}")
            return None
        
        if not source_layer.isValid():
            self.log_error(f"Source layer is not valid: {source_layer.name()}")
            return None
        
        # CRITICAL FIX v2.5.4: For memory layers, featureCount() can return 0 immediately after creation
        # even if features were added. We need to force a refresh/recount.
        # Try to get actual feature count by iterating (more reliable for memory layers)
        actual_feature_count = 0
        if source_layer.providerType() == 'memory':
            # For memory layers, force extent update and iterate to get real count
            source_layer.updateExtents()
            
            # DIAGNOSTIC: Log both featureCount() and actual iteration count
            reported_count = source_layer.featureCount()
            try:
                actual_feature_count = sum(1 for _ in source_layer.getFeatures())
            except Exception as e:
                self.log_warning(f"Failed to iterate features: {e}, using featureCount()")
                actual_feature_count = reported_count
            
            if reported_count != actual_feature_count:
                self.log_warning(f"⚠️ Memory layer count mismatch: featureCount()={reported_count}, actual={actual_feature_count}")
        else:
            actual_feature_count = source_layer.featureCount()
        
        self.log_debug(f"Source layer '{source_layer.name()}': provider={source_layer.providerType()}, features={actual_feature_count}")
        
        if actual_feature_count == 0:
            self.log_error(f"⚠️ Source layer has no features: {source_layer.name()}")
            self.log_error(f"  → This is the INTERSECT layer for spatial filtering")
            self.log_error(f"  → Common causes:")
            self.log_error(f"     1. No features selected in source layer")
            self.log_error(f"     2. Source layer subset string filters out all features")
            self.log_error(f"     3. Field-based filtering returned no matches")
            return None
        
        # Support both positive and negative buffer values
        if buffer_value and buffer_value != 0:
            buffer_type_str = "expansion" if buffer_value > 0 else "erosion (shrink)"
            self.log_debug(f"Applying {buffer_type_str} buffer of {buffer_value} to source layer")
            
            # Warn for negative buffer on non-polygon layers
            if buffer_value < 0:
                geom_type = source_layer.geometryType()
                # 0 = Point, 1 = Line, 2 = Polygon
                if geom_type != 2:  # Not polygon
                    self.log_warning(f"⚠️ Negative buffer applied to non-polygon geometry type ({geom_type})")
                    self.log_warning(f"  → This may produce empty or invalid geometries")
            
            try:
                # Ensure buffer_value is numeric
                buffer_dist = float(buffer_value)
                
                # Get buffer_type from task_params (default: 0 = Round)
                buffer_type = 0  # Default: Round
                buffer_segments = 5  # Default: 5 segments
                if self.task_params:
                    filtering_params = self.task_params.get("filtering", {})
                    if filtering_params.get("has_buffer_type", False):
                        buffer_type_str = filtering_params.get("buffer_type", "Round")
                        buffer_type_mapping = {"Round": 0, "Flat": 1, "Square": 2}
                        buffer_type = buffer_type_mapping.get(buffer_type_str, 0)
                        buffer_segments = filtering_params.get("buffer_segments", 5)
                        self.log_debug(f"Using buffer type: {buffer_type_str} (END_CAP_STYLE={buffer_type}, segments={buffer_segments})")
                
                # Log layer details for debugging
                self.log_debug(f"Buffer source layer: {source_layer.name()}, "
                              f"CRS: {source_layer.crs().authid()}, "
                              f"Features: {source_layer.featureCount()}")
                
                # v2.6.2: Use cancellable feedback for interruptible processing
                from qgis.core import QgsProcessingContext, QgsFeatureRequest
                context = QgsProcessingContext()
                context.setInvalidGeometryCheck(QgsFeatureRequest.GeometrySkipInvalid)
                feedback = self._create_cancellable_feedback()
                
                # v2.6.2: Check cancellation before buffer
                if self._is_task_canceled():
                    self.log_info("Filter cancelled before buffer processing")
                    return None
                
                try:
                    # First run fixgeometries to repair any invalid geometries
                    fix_result = processing.run("native:fixgeometries", {
                        'INPUT': source_layer,
                        'OUTPUT': 'memory:'
                    }, context=context, feedback=feedback)
                    fixed_layer = fix_result['OUTPUT']
                    self.log_debug(f"Fixed geometries: {fixed_layer.featureCount()} features")
                except Exception as fix_error:
                    self.log_warning(f"fixgeometries failed: {fix_error}, using original layer")
                    fixed_layer = source_layer
                
                # Now apply buffer on the fixed layer
                # native:buffer supports negative distances for polygon erosion
                buffer_result = processing.run("native:buffer", {
                    'INPUT': fixed_layer,
                    'DISTANCE': buffer_dist,
                    'SEGMENTS': int(buffer_segments),  # Use configured buffer segments
                    'END_CAP_STYLE': int(buffer_type),  # Use configured buffer type
                    'JOIN_STYLE': int(0),  # Round
                    'MITER_LIMIT': float(2.0),
                    'DISSOLVE': False,
                    'OUTPUT': 'memory:'
                }, context=context, feedback=feedback)
                
                buffered_layer = buffer_result['OUTPUT']
                
                # CRITICAL FIX v2.4.23: For negative buffers, REMOVE empty/invalid geometries
                # Negative buffers can collapse polygons to empty geometries if the erosion
                # is too large. These must be removed or selectbylocation will fail.
                if buffer_dist < 0:
                    from qgis.core import QgsVectorLayer, QgsFeature
                    
                    # Count and collect valid features
                    valid_features = []
                    empty_count = 0
                    
                    for feature in buffered_layer.getFeatures():
                        geom = feature.geometry()
                        if geom.isNull() or geom.isEmpty():
                            empty_count += 1
                        else:
                            # Keep only valid, non-empty geometries
                            valid_features.append(feature)
                    
                    if empty_count > 0:
                        self.log_info(f"📐 Negative buffer: {empty_count} features collapsed to empty (removing)")
                        
                        # Create new layer with only valid geometries
                        if valid_features:
                            # Create new memory layer with same CRS and geometry type
                            crs_authid = buffered_layer.crs().authid()
                            geom_type = buffered_layer.wkbType()
                            from qgis.core import QgsWkbTypes
                            geom_type_str = QgsWkbTypes.displayString(geom_type)
                            
                            new_layer = QgsVectorLayer(
                                f"{geom_type_str}?crs={crs_authid}",
                                "filtered_buffer",
                                "memory"
                            )
                            
                            # Copy valid features to new layer
                            provider = new_layer.dataProvider()
                            provider.addFeatures(valid_features)
                            new_layer.updateExtents()
                            
                            self.log_info(f"  ✓ Created new layer with {len(valid_features)} valid features (removed {empty_count} empty)")
                            buffered_layer = new_layer
                        else:
                            self.log_error(f"  ⚠️ All features collapsed to empty after negative buffer!")
                            self.log_error(f"  → Buffer value {buffer_dist}m is too large for the polygons")
                            return None
                
                # CRITICAL FIX: Check for and convert GeometryCollection to MultiPolygon
                # native:buffer can produce GeometryCollection when features don't overlap
                buffered_layer = self._convert_geometry_collection_to_multipolygon(buffered_layer)
                
                self.log_debug("Buffer applied successfully")
                return buffered_layer
            except Exception as buffer_error:
                self.log_error(f"Buffer operation failed: {str(buffer_error)}")
                self.log_error(f"  - Buffer value: {buffer_value} (type: {type(buffer_value).__name__})")
                self.log_error(f"  - Source layer: {source_layer.name()}")
                self.log_error(f"  - CRS: {source_layer.crs().authid()} (Geographic: {source_layer.crs().isGeographic()})")
                
                # Check for common error causes
                if source_layer.crs().isGeographic() and abs(float(buffer_value)) > 1:
                    self.log_error(
                        f"ERROR: Geographic CRS detected with large buffer value!\n"
                        f"  A buffer of {buffer_value}° in a geographic CRS (lat/lon) is equivalent to\n"
                        f"  approximately {abs(float(buffer_value)) * 111}km at the equator.\n"
                        f"  → Solution: Reproject your layer to a projected CRS (e.g., EPSG:3857, EPSG:2154)"
                    )
                
                import traceback
                self.log_debug(f"Buffer traceback: {traceback.format_exc()}")
                return None
        return source_layer
    
    def _convert_geometry_collection_to_multipolygon(self, layer):
        """
        Convert GeometryCollection geometries in a layer to MultiPolygon.
        
        CRITICAL FIX for GeoPackage/OGR layers:
        When native:buffer processes features that don't overlap, the result
        can contain GeometryCollection type instead of MultiPolygon.
        This causes errors when the buffer layer is used for spatial operations
        on typed layers (e.g., GeoPackage MultiPolygon layers).
        
        Error fixed: "Impossible d'ajouter l'objet avec une géométrie de type 
        GeometryCollection à une couche de type MultiPolygon"
        
        Args:
            layer: QgsVectorLayer from buffer operation
            
        Returns:
            QgsVectorLayer: Layer with geometries converted to MultiPolygon
        """
        from qgis.core import (
            QgsWkbTypes, QgsFeature, QgsGeometry, 
            QgsMemoryProviderUtils, QgsVectorLayer
        )
        
        try:
            # Check if any features have GeometryCollection type
            has_geometry_collection = False
            for feature in layer.getFeatures():
                geom = feature.geometry()
                if validate_geometry(geom):
                    geom_type = get_geometry_type_name(geom)
                    if 'GeometryCollection' in geom_type:
                        has_geometry_collection = True
                        break
            
            if not has_geometry_collection:
                self.log_debug("No GeometryCollection found in buffer result - no conversion needed")
                return layer
            
            self.log_info("🔄 GeometryCollection detected in buffer result - converting to MultiPolygon")
            
            # Create new memory layer with MultiPolygon type
            crs = layer.crs()
            fields = layer.fields()
            
            # Create MultiPolygon memory layer
            converted_layer = QgsMemoryProviderUtils.createMemoryLayer(
                f"{layer.name()}_converted",
                fields,
                QgsWkbTypes.MultiPolygon,
                crs
            )
            
            if not converted_layer or not converted_layer.isValid():
                self.log_error("Failed to create converted memory layer")
                return layer
            
            converted_dp = converted_layer.dataProvider()
            converted_features = []
            conversion_count = 0
            
            for feature in layer.getFeatures():
                geom = feature.geometry()
                if not validate_geometry(geom):
                    continue
                
                geom_type = get_geometry_type_name(geom)
                new_geom = geom
                
                if 'GeometryCollection' in geom_type:
                    # STABILITY FIX v2.3.9: Use safe wrapper for conversion
                    converted = safe_convert_to_multi_polygon(geom)
                    if converted:
                        new_geom = converted
                        conversion_count += 1
                        self.log_debug(f"Converted GeometryCollection to {get_geometry_type_name(new_geom)}")
                    else:
                        # Fallback: try extracting polygons using safe wrapper
                        polygon_parts = extract_polygons_from_collection(geom)
                        if polygon_parts:
                            # Create MultiPolygon from extracted parts
                            if len(polygon_parts) == 1:
                                poly_data = safe_as_polygon(polygon_parts[0])
                                if poly_data:
                                    new_geom = QgsGeometry.fromMultiPolygonXY([poly_data])
                            else:
                                multi_poly_parts = [safe_as_polygon(p) for p in polygon_parts]
                                multi_poly_parts = [p for p in multi_poly_parts if p]
                                if multi_poly_parts:
                                    new_geom = QgsGeometry.fromMultiPolygonXY(multi_poly_parts)
                            conversion_count += 1
                        else:
                            self.log_warning("GeometryCollection contained no polygon parts - skipping feature")
                            continue
                
                elif 'Polygon' in geom_type and 'Multi' not in geom_type:
                    # Convert single Polygon to MultiPolygon for consistency
                    poly_data = safe_as_polygon(geom)
                    if poly_data:
                        new_geom = QgsGeometry.fromMultiPolygonXY([poly_data])
                
                # Create new feature with converted geometry
                new_feature = QgsFeature(fields)
                new_feature.setGeometry(new_geom)
                new_feature.setAttributes(feature.attributes())
                converted_features.append(new_feature)
            
            # Add converted features
            if converted_features:
                success, _ = converted_dp.addFeatures(converted_features)
                if success:
                    converted_layer.updateExtents()
                    self.log_info(f"✓ Converted {conversion_count} GeometryCollection(s) to MultiPolygon")
                    return converted_layer
                else:
                    self.log_error("Failed to add converted features to layer")
                    return layer
            else:
                self.log_warning("No features to convert")
                return layer
                
        except Exception as e:
            self.log_error(f"Error converting GeometryCollection: {str(e)}")
            import traceback
            self.log_debug(f"Conversion traceback: {traceback.format_exc()}")
            return layer

    def _map_predicates(self, predicates):
        """Map predicate names to QGIS processing codes.
        
        Handles multiple input formats:
        - Lowercase names: 'intersects', 'disjoint', etc.
        - UI names with capital: 'Intersect', 'Disjoint', etc.
        - Numeric string indices: '0', '2', etc. (from filter_task.py execute_filtering mapping)
        - SQL function names: 'ST_Intersects', 'ST_Disjoint', etc.
        
        Note: The numeric indices correspond to positions in filter_task.py's self.predicates dict:
        0/1: Intersect/intersects, 2/3: Contain/contains, 4/5: Disjoint/disjoint, 
        6/7: Equal/equals, 8/9: Touch/touches, 10/11: Overlap/overlaps,
        12/13: Are within/within, 14/15: Cross/crosses, 16/17: covers/coveredby
        """
        # QGIS selectbylocation predicate codes:
        # 0: intersect, 1: contain, 2: disjoint, 3: equal, 4: touch, 5: overlap, 6: within, 7: cross
        predicate_map = {
            # Lowercase names (standard)
            'intersects': [0],
            'contains': [1],
            'disjoint': [2],
            'equal': [3],
            'equals': [3],
            'touches': [4],
            'overlaps': [5],
            'within': [6],
            'crosses': [7],
            'covers': [1],  # Similar to contains
            'coveredby': [6],  # Similar to within
            # UI names (capitalized)
            'Intersect': [0],
            'Contain': [1],
            'Disjoint': [2],
            'Equal': [3],
            'Touch': [4],
            'Overlap': [5],
            'Within': [6],
            'Are within': [6],
            'Cross': [7],
            # Numeric string indices from filter_task.py execute_filtering
            # Based on self.predicates dict order in filter_task.py:
            # "Intersect": 0, "intersects": 1, "Contain": 2, "contains": 3,
            # "Disjoint": 4, "disjoint": 5, "Equal": 6, "equals": 7,
            # "Touch": 8, "touches": 9, "Overlap": 10, "overlaps": 11,
            # "Are within": 12, "within": 13, "Cross": 14, "crosses": 15,
            # "covers": 16, "coveredby": 17
            '0': [0],   # Intersect -> QGIS intersect (0)
            '1': [0],   # intersects -> QGIS intersect (0)
            '2': [1],   # Contain -> QGIS contain (1)
            '3': [1],   # contains -> QGIS contain (1)
            '4': [2],   # Disjoint -> QGIS disjoint (2)
            '5': [2],   # disjoint -> QGIS disjoint (2)
            '6': [3],   # Equal -> QGIS equal (3)
            '7': [3],   # equals -> QGIS equal (3)
            '8': [4],   # Touch -> QGIS touch (4)
            '9': [4],   # touches -> QGIS touch (4)
            '10': [5],  # Overlap -> QGIS overlap (5)
            '11': [5],  # overlaps -> QGIS overlap (5)
            '12': [6],  # Are within -> QGIS within (6)
            '13': [6],  # within -> QGIS within (6)
            '14': [7],  # Cross -> QGIS cross (7)
            '15': [7],  # crosses -> QGIS cross (7)
            '16': [1],  # covers -> QGIS contain (1)
            '17': [6],  # coveredby -> QGIS within (6)
            # SQL function names (PostGIS style)
            'ST_Intersects': [0],
            'ST_Contains': [1],
            'ST_Disjoint': [2],
            'ST_Equals': [3],
            'ST_Touches': [4],
            'ST_Overlaps': [5],
            'ST_Within': [6],
            'ST_Crosses': [7],
            'ST_Covers': [1],
            'ST_CoveredBy': [6],
        }
        
        predicate_codes = []
        for pred in predicates:
            if pred in predicate_map:
                predicate_codes.extend(predicate_map[pred])
            else:
                self.log_debug(f"Unknown predicate '{pred}', attempting lookup by index")
        
        if not predicate_codes:
            predicate_codes = [0]  # Default to intersects
            self.log_info("No predicates specified, defaulting to 'intersects'")
        else:
            self.log_debug(f"Mapped predicates {predicates} to QGIS codes {predicate_codes}")
        
        return predicate_codes
    
    def _preflight_layer_check(self, layer: QgsVectorLayer, param_name: str) -> bool:
        """
        Pre-flight check before passing layer to processing.run().
        
        CRITICAL STABILITY FIX v2.3.9.3:
        This method tests the exact operations that QGIS Processing performs
        during checkParameterValues(). If any of these fail, we abort before
        calling processing.run() to prevent C++ level crashes.
        
        Args:
            layer: Layer to validate
            param_name: Parameter name for logging (e.g., "INPUT", "INTERSECT")
            
        Returns:
            True if layer passes all pre-flight checks, False otherwise
        """
        if layer is None:
            self.log_error(f"Pre-flight check: {param_name} layer is None")
            return False
        
        try:
            # These are the operations that checkParameterValues performs:
            
            # 1. Check layer validity
            if not layer.isValid():
                self.log_error(f"Pre-flight check: {param_name} layer.isValid() = False")
                return False
            
            # 2. Get layer source (used by Processing to identify the layer)
            source = layer.source()
            if not source:
                self.log_warning(f"Pre-flight check: {param_name} layer has empty source (memory layer)")
            
            # 3. Access data provider
            provider = layer.dataProvider()
            if provider is None:
                self.log_error(f"Pre-flight check: {param_name} layer has no data provider")
                return False
            
            # 4. Check provider can be accessed (this is where crashes often occur)
            try:
                uri = provider.dataSourceUri()
                caps = provider.capabilities()
            except Exception as provider_error:
                self.log_error(f"Pre-flight check: {param_name} provider access failed: {provider_error}")
                return False
            
            # 5. Verify extent can be computed (required for spatial operations)
            try:
                extent = layer.extent()
                if extent.isNull() or extent.isEmpty():
                    # Empty extent is OK for layers with no features
                    if layer.featureCount() > 0:
                        self.log_warning(f"Pre-flight check: {param_name} layer has null/empty extent despite having features")
            except Exception as extent_error:
                self.log_error(f"Pre-flight check: {param_name} extent access failed: {extent_error}")
                return False
            
            # 6. Test that we can start feature iteration (but don't iterate all)
            try:
                request = layer.getFeatures()
                # Just test that we can get the iterator, don't consume it
                del request
            except Exception as iter_error:
                self.log_error(f"Pre-flight check: {param_name} cannot create feature iterator: {iter_error}")
                return False
            
            self.log_debug(f"✓ Pre-flight check passed for {param_name}: {layer.name()}")
            return True
            
        except (RuntimeError, OSError) as access_error:
            self.log_error(f"Pre-flight check: {param_name} layer access error: {access_error}")
            return False
        except Exception as unexpected:
            self.log_error(f"Pre-flight check: {param_name} unexpected error: {unexpected}")
            return False
    
    def _validate_intersect_layer(self, intersect_layer: QgsVectorLayer) -> bool:
        """
        Validate that the intersect layer is safe to use for spatial operations.
        
        CRITICAL STABILITY FIX v2.3.9.3:
        Prevents access violations when passing invalid layers to native:selectbylocation.
        Tests the same layer properties that checkParameterValues accesses.
        
        Checks:
        1. Layer is not None and is a QgsVectorLayer
        2. Layer is valid
        3. Layer has at least one feature
        4. Features have valid geometries
        5. Layer properties can be safely accessed
        
        Args:
            intersect_layer: The layer to validate
            
        Returns:
            True if layer is safe to use, False otherwise
        """
        # Check layer exists and is valid
        if intersect_layer is None:
            self.log_error("Intersect layer is None")
            return False
        
        if not isinstance(intersect_layer, QgsVectorLayer):
            self.log_error(f"Intersect layer is not a QgsVectorLayer: {type(intersect_layer).__name__}")
            return False
        
        if not intersect_layer.isValid():
            self.log_error(f"Intersect layer is not valid: {intersect_layer.name()}")
            return False
        
        # STABILITY FIX v2.3.9.3: Deep layer access validation
        # Test the same properties that checkParameterValues accesses
        try:
            # Test basic properties that Processing accesses
            _ = intersect_layer.id()
            _ = intersect_layer.name()
            _ = intersect_layer.crs().isValid()
            _ = intersect_layer.wkbType()
            _ = intersect_layer.geometryType()
            
            # Test data provider access (critical)
            provider = intersect_layer.dataProvider()
            if provider is None:
                self.log_error(f"Intersect layer data provider is None")
                return False
            
            # Test provider properties
            _ = provider.wkbType()
            _ = provider.featureCount()
            _ = provider.extent()
            
        except (RuntimeError, OSError, AttributeError) as access_error:
            self.log_error(f"Intersect layer access failed: {access_error}")
            return False
        except Exception as unexpected_error:
            self.log_error(f"Unexpected error accessing intersect layer: {unexpected_error}")
            return False
        
        # Check feature count
        feature_count = intersect_layer.featureCount()
        if feature_count == 0:
            self.log_warning(f"Intersect layer has no features: {intersect_layer.name()}")
            return False
        
        # Check that at least one feature has a valid geometry
        has_valid_geometry = False
        invalid_geom_count = 0
        try:
            for feature in intersect_layer.getFeatures():
                geom = feature.geometry()
                if validate_geometry(geom):
                    has_valid_geometry = True
                    break
                else:
                    invalid_geom_count += 1
                    if invalid_geom_count >= 10:  # Check first 10 only for performance
                        break
        except (RuntimeError, OSError) as iter_error:
            self.log_error(f"Failed to iterate intersect layer features: {iter_error}")
            return False
        
        if not has_valid_geometry:
            self.log_error(f"Intersect layer has no valid geometries (checked {invalid_geom_count} features)")
            return False
        
        self.log_info(f"✓ Intersect layer validated: {intersect_layer.name()} ({feature_count} features)")
        return True
    
    def _validate_input_layer(self, layer: QgsVectorLayer) -> bool:
        """
        Validate that the input layer (to be filtered) is safe for spatial operations.
        
        CRITICAL STABILITY FIX v2.3.9.3:
        Prevents access violations when passing invalid layers to native:selectbylocation.
        Tests the same layer properties that checkParameterValues accesses to catch
        crashes before calling processing.run().
        
        Args:
            layer: The layer to validate
            
        Returns:
            True if layer is safe to use, False otherwise
        """
        if layer is None:
            self.log_error("Input layer is None")
            return False
        
        if not isinstance(layer, QgsVectorLayer):
            self.log_error(f"Input layer is not a QgsVectorLayer: {type(layer).__name__}")
            return False
        
        if not layer.isValid():
            self.log_error(f"Input layer is not valid: {layer.name()}")
            return False
        
        # STABILITY FIX v2.3.9.3: Deep layer access validation
        # Test the same properties that checkParameterValues accesses
        # This catches crashes before calling processing.run()
        try:
            # Test basic properties that Processing accesses
            _ = layer.id()
            _ = layer.name()
            _ = layer.crs().isValid()
            _ = layer.wkbType()
            _ = layer.geometryType()
            
            # Test data provider access (critical - this is where many crashes occur)
            provider = layer.dataProvider()
            if provider is None:
                self.log_error(f"Input layer data provider is None: {layer.name()}")
                return False
            
            # Test provider properties
            _ = provider.wkbType()
            _ = provider.featureCount()
            _ = provider.extent()
            
        except (RuntimeError, OSError, AttributeError) as access_error:
            self.log_error(f"Input layer access failed (layer may be corrupted or deleted): {access_error}")
            return False
        except Exception as unexpected_error:
            self.log_error(f"Unexpected error accessing input layer: {unexpected_error}")
            return False
        
        # Check feature count - empty layers are OK (will just return no results)
        feature_count = layer.featureCount()
        if feature_count == 0:
            self.log_debug(f"Input layer is empty: {layer.name()}")
            return True  # OK to proceed, just won't match anything
        
        self.log_debug(f"✓ Input layer validated: {layer.name()} ({feature_count} features)")
        return True
    
    def _safe_select_by_location(
        self,
        input_layer: QgsVectorLayer,
        intersect_layer: QgsVectorLayer,
        predicate_codes: list
    ) -> bool:
        """
        Safely execute selectbylocation with comprehensive error handling.
        
        CRITICAL STABILITY FIX v2.3.9.1:
        Wraps native:selectbylocation with validation and error recovery.
        Uses create_geos_safe_layer() to filter out geometries that would crash GEOS
        at the C++ level (cannot be caught by Python try/except).
        
        Args:
            input_layer: Layer to select features from
            intersect_layer: Layer containing geometries to intersect with
            predicate_codes: List of QGIS predicate codes
            
        Returns:
            True if selection completed successfully, False on error
        """
        from qgis.core import QgsMessageLog, Qgis
        
        try:
            # Validate both layers before processing
            QgsMessageLog.logMessage(
                f"_safe_select_by_location: input={input_layer.name() if input_layer else 'None'} ({input_layer.featureCount() if input_layer else 0}), "
                f"intersect={intersect_layer.name() if intersect_layer else 'None'} ({intersect_layer.featureCount() if intersect_layer else 0})",
                "FilterMate", Qgis.Info
            )
            
            self.log_info(f"🔍 Validating layers for selectbylocation...")
            self.log_info(f"  → Input layer: {input_layer.name() if input_layer else 'None'}")
            if input_layer:
                self.log_info(f"    - Valid: {input_layer.isValid()}")
                self.log_info(f"    - Feature count: {input_layer.featureCount()}")
            self.log_info(f"  → Intersect layer: {intersect_layer.name() if intersect_layer else 'None'}")
            if intersect_layer:
                self.log_info(f"    - Valid: {intersect_layer.isValid()}")
                self.log_info(f"    - Feature count: {intersect_layer.featureCount()}")
            
            if not self._validate_input_layer(input_layer):
                self.log_error("Input layer validation failed - see details above")
                return False
            
            if not self._validate_intersect_layer(intersect_layer):
                self.log_error("Intersect layer validation failed - see details above")
                return False
            
            # Configure processing context to handle invalid geometries gracefully
            from qgis.core import QgsProcessingContext, QgsFeatureRequest
            context = QgsProcessingContext()
            context.setInvalidGeometryCheck(QgsFeatureRequest.GeometrySkipInvalid)
            
            # v2.6.2: Use cancellable feedback for interruptible processing
            feedback = self._create_cancellable_feedback()
            
            # v2.6.2: Check cancellation before starting
            if self._is_task_canceled():
                self.log_info("Filter cancelled before selectbylocation")
                return False
            
            self.log_info(f"🔍 Preparing selectbylocation: input={input_layer.name()} ({input_layer.featureCount()} features), "
                         f"intersect={intersect_layer.name()} ({intersect_layer.featureCount()} features), "
                         f"predicates={predicate_codes}")
            
            # STABILITY FIX v2.3.9.2: Use create_geos_safe_layer() for geometry validation
            # The function now handles fallbacks gracefully and returns original layer as last resort
            self.log_info("🛡️ Creating GEOS-safe intersect layer (geometry validation)...")
            safe_intersect = create_geos_safe_layer(intersect_layer, "_safe_intersect")
            
            # create_geos_safe_layer now returns the original layer as fallback, never None for valid input
            if safe_intersect is None:
                self.log_warning("create_geos_safe_layer returned None, using original layer")
                safe_intersect = intersect_layer
            
            if not safe_intersect.isValid() or safe_intersect.featureCount() == 0:
                self.log_error("No valid geometries in intersect layer")
                return False
            
            self.log_info(f"✓ Safe intersect layer: {safe_intersect.featureCount()} features")
            
            # Also process input layer if not too large
            safe_input = input_layer
            use_safe_input = False
            if input_layer.featureCount() <= 50000:  # Only process smaller layers for performance
                self.log_debug("🛡️ Creating GEOS-safe input layer...")
                temp_safe_input = create_geos_safe_layer(input_layer, "_safe_input")
                if temp_safe_input and temp_safe_input.isValid() and temp_safe_input.featureCount() > 0:
                    safe_input = temp_safe_input
                    use_safe_input = True
                    self.log_debug(f"✓ Safe input layer: {safe_input.featureCount()} features")
            
            self.log_info(f"🔍 Executing selectbylocation with GEOS-safe geometries")
            
            # STABILITY FIX v2.3.9.3: Pre-flight validation of layers before processing.run()
            # This catches issues that would cause checkParameterValues to crash at C++ level
            actual_input = input_layer if not use_safe_input else safe_input
            if not self._preflight_layer_check(actual_input, "INPUT"):
                self.log_error("Pre-flight check failed for INPUT layer")
                return False
            if not self._preflight_layer_check(safe_intersect, "INTERSECT"):
                self.log_error("Pre-flight check failed for INTERSECT layer")
                return False
            
            # Execute with error handling - use safe layers
            if not use_safe_input:
                # Direct selection on original layer
                select_result = processing.run("native:selectbylocation", {
                    'INPUT': input_layer,
                    'PREDICATE': predicate_codes,
                    'INTERSECT': safe_intersect,
                    'METHOD': 0  # creating new selection
                }, context=context, feedback=feedback)
            else:
                # Select on safe layer, then map back to original
                select_result = processing.run("native:selectbylocation", {
                    'INPUT': safe_input,
                    'PREDICATE': predicate_codes,
                    'INTERSECT': safe_intersect,
                    'METHOD': 0
                }, context=context, feedback=feedback)
                
                # FIX v2.4.18: Map selection back using primary key values, not feature IDs
                # The safe layer is a memory copy where feature IDs don't match the original
                # We must use the primary key field values to map back to the original layer
                try:
                    from ..appUtils import get_primary_key_name
                    pk_field = get_primary_key_name(input_layer)
                    
                    if pk_field:
                        # Get primary key values from selected features in safe layer
                        pk_values = []
                        for f in safe_input.selectedFeatures():
                            pk_val = f.attribute(pk_field)
                            if pk_val is not None:
                                pk_values.append(pk_val)
                        
                        if pk_values:
                            # Select features in original layer by matching primary key values
                            # Build an expression to select matching features
                            from qgis.PyQt.QtCore import QMetaType
                            field_idx = input_layer.fields().indexFromName(pk_field)
                            field_type = input_layer.fields()[field_idx].type()
                            
                            # Quote string values, keep numeric values unquoted
                            if field_type == QMetaType.Type.QString:
                                pk_list = ','.join(f"'{str(v).replace(chr(39), chr(39)+chr(39))}'" for v in pk_values)
                            else:
                                pk_list = ','.join(str(v) for v in pk_values)
                            
                            from qgis.core import QgsExpression, QgsFeatureRequest
                            expr_str = f'"{pk_field}" IN ({pk_list})'
                            expr = QgsExpression(expr_str)
                            request = QgsFeatureRequest(expr)
                            
                            # Get matching feature IDs from original layer
                            matching_ids = [f.id() for f in input_layer.getFeatures(request)]
                            input_layer.selectByIds(matching_ids)
                            self.log_debug(f"Mapped {len(matching_ids)} features back to original layer using '{pk_field}'")
                        else:
                            self.log_warning("No primary key values found in selected features")
                            input_layer.removeSelection()
                    else:
                        # Fallback: try using feature IDs directly (may not work for all cases)
                        self.log_warning(f"No primary key found for {input_layer.name()}, trying direct ID mapping (may fail)")
                        selected_fids = [f.id() for f in safe_input.selectedFeatures()]
                        if selected_fids:
                            input_layer.selectByIds(selected_fids)
                except (RuntimeError, AttributeError) as e:
                    self.log_error(f"Failed to map selection back to original layer: {e}")
                    return False
            
            try:
                selected_count = input_layer.selectedFeatureCount()
            except (RuntimeError, AttributeError) as e:
                self.log_error(f"Failed to get selected feature count: {e}")
                return False
            
            QgsMessageLog.logMessage(
                f"selectbylocation result: {selected_count} features selected on {input_layer.name()}",
                "FilterMate", Qgis.Info
            )
            
            # DIAGNOSTIC v2.4.17: Log intersect layer geometry extent
            if intersect_layer and intersect_layer.isValid():
                extent = intersect_layer.extent()
                QgsMessageLog.logMessage(
                    f"  Intersect layer '{intersect_layer.name()}' extent: ({extent.xMinimum():.1f},{extent.yMinimum():.1f})-({extent.xMaximum():.1f},{extent.yMaximum():.1f})",
                    "FilterMate", Qgis.Info
                )
                # Log first geometry WKT preview
                for feat in intersect_layer.getFeatures():
                    geom = feat.geometry()
                    if geom and not geom.isEmpty():
                        wkt_preview = geom.asWkt()[:200] if geom.asWkt() else "EMPTY"
                        QgsMessageLog.logMessage(
                            f"  First intersect geom: {wkt_preview}...",
                            "FilterMate", Qgis.Info
                        )
                    break
            
            self.log_info(f"✓ Selection complete: {selected_count} features selected")
            return True
            
        except Exception as e:
            self.log_error(f"selectbylocation failed: {str(e)}")
            import traceback
            self.log_debug(f"Traceback: {traceback.format_exc()}")
            
            QgsMessageLog.logMessage(
                f"selectbylocation FAILED on {input_layer.name() if input_layer else 'Unknown'}: {str(e)}",
                "FilterMate", Qgis.Critical
            )
            
            # Clear any partial selection to avoid inconsistent state
            try:
                input_layer.removeSelection()
            except:
                pass
            
            return False
    
    def _apply_filter_standard(
        self, layer, source_layer, predicates, buffer_value,
        old_subset, combine_operator
    ):
        """
        Standard filtering method for small-medium datasets (<10k features).
        
        Uses direct selectbylocation and subset string with feature IDs.
        
        STABILITY FIX v2.3.9: Added layer validation to prevent access violations.
        FIX v2.4.18: Clear existing subset before selectbylocation to prevent GDAL errors.
        """
        # Initialize existing_subset early for exception handling
        existing_subset = None
        
        # STABILITY FIX v2.3.9: Validate layers before any operations
        if layer is None or not layer.isValid():
            self.log_error("Target layer is None or invalid - cannot proceed with standard filtering")
            if layer is None:
                self.log_error("  → layer is None")
            else:
                self.log_error(f"  → layer.isValid() = {layer.isValid()}")
            return False
        
        if source_layer is None or not source_layer.isValid():
            self.log_error("Source layer is None or invalid - cannot proceed with standard filtering")
            if source_layer is None:
                self.log_error("  → source_layer is None")
            else:
                self.log_error(f"  → source_layer.isValid() = {source_layer.isValid()}")
                self.log_error(f"  → source_layer.featureCount() = {source_layer.featureCount()}")
            return False
        
        # FIX v2.4.18: Save and temporarily clear existing subset string
        # This prevents GDAL "feature id out of available range" errors when
        # selectbylocation tries to access features that are filtered out by the existing subset.
        # The existing subset is saved and will be combined with the new filter later if needed.
        existing_subset = layer.subsetString()
        if existing_subset:
            self.log_info(f"🔄 Temporarily clearing existing subset on {layer.name()} for selectbylocation")
            self.log_debug(f"  → Existing subset: '{existing_subset[:100]}...'")
            safe_set_subset_string(layer, "")
            # Update old_subset to use the existing subset for combination later
            if old_subset is None:
                old_subset = existing_subset
        
        self.log_debug(f"OGR standard filter: target={layer.name()} ({layer.featureCount()} features), source={source_layer.name()} ({source_layer.featureCount()} features)")
        
        # DIAGNOSTIC v2.4.17: Log source layer geometry details before buffer
        logger.debug(f"_apply_filter_standard: source_layer={source_layer.name()}, features={source_layer.featureCount()}")
        # Log first 3 source features at DEBUG level only
        if source_layer.featureCount() > 0 and logger.isEnabledFor(logging.DEBUG):
            for idx, feat in enumerate(source_layer.getFeatures()):
                geom = feat.geometry()
                if geom and not geom.isEmpty():
                    bbox = geom.boundingBox()
                    logger.debug(
                        f"  Source feature[{idx}]: id={feat.id()}, bbox=({bbox.xMinimum():.1f},{bbox.yMinimum():.1f})-({bbox.xMaximum():.1f},{bbox.yMaximum():.1f})"
                    )
                if idx >= 2:  # Only log first 3 features
                    break
        
        # Apply buffer
        intersect_layer = self._apply_buffer(source_layer, buffer_value)
        if intersect_layer is None:
            # FIX v2.4.18: Restore original subset if buffer failed
            if existing_subset:
                self.log_warning(f"Restoring original subset after buffer failure")
                safe_set_subset_string(layer, existing_subset)
            return False
        
        # Map predicates
        predicate_codes = self._map_predicates(predicates)
        
        # STABILITY FIX v2.3.9: Use safe wrapper for selectbylocation
        if not self._safe_select_by_location(layer, intersect_layer, predicate_codes):
            self.log_error("Safe select by location failed - cannot proceed")
            # FIX v2.4.18: Restore original subset if selectbylocation failed
            if existing_subset:
                self.log_warning(f"Restoring original subset after selectbylocation failure")
                safe_set_subset_string(layer, existing_subset)
            return False
        
        selected_count = layer.selectedFeatureCount()
        
        # Convert selection to subset filter
        try:
            if selected_count > 0:
                # Get primary key field name for proper subset string
                # Note: $id is not always supported by all OGR providers
                # Use actual primary key field name instead
                from ..appUtils import get_primary_key_name
                
                pk_field = get_primary_key_name(layer)
                if not pk_field:
                    # Fallback to $id if no primary key found
                    pk_field = "$id"
                    self.log_warning(f"No primary key found for {layer.name()}, using $id (may not work for all formats)")
                
                # Get actual field values from selected features
                if pk_field == "$id":
                    # Use QGIS feature IDs
                    # STABILITY FIX v2.3.9: Wrap in try-except to catch access violations
                    try:
                        selected_ids = [f.id() for f in layer.selectedFeatures()]
                    except (RuntimeError, AttributeError) as e:
                        self.log_error(f"Failed to get selected features: {e}")
                        return False
                    id_list = ','.join(str(fid) for fid in selected_ids)
                    new_subset_expression = f"$id IN ({id_list})"
                else:
                    # Get actual field values and check field type
                    from qgis.PyQt.QtCore import QMetaType
                    field_idx = layer.fields().indexFromName(pk_field)
                    
                    if field_idx < 0:
                        self.log_error(f"Primary key field '{pk_field}' not found in layer")
                        return False
                    
                    field_type = layer.fields()[field_idx].type()
                    
                    # Extract values from the primary key field
                    # STABILITY FIX v2.3.9: Wrap in try-except to catch access violations
                    try:
                        selected_values = [f.attribute(pk_field) for f in layer.selectedFeatures()]
                    except (RuntimeError, AttributeError) as e:
                        self.log_error(f"Failed to get selected features for PK extraction: {e}")
                        return False
                    
                    # Quote string values, keep numeric values unquoted
                    if field_type == QMetaType.Type.QString:
                        id_list = ','.join(f"'{str(val).replace(chr(39), chr(39)+chr(39))}'" for val in selected_values)
                    else:
                        id_list = ','.join(str(val) for val in selected_values)
                    
                    escaped_pk = escape_ogr_identifier(pk_field)
                    new_subset_expression = f'{escaped_pk} IN ({id_list})'
                
                self.log_debug(f"Generated subset expression using key '{pk_field}'")
                
                # Combine with old subset if needed (but not if it contains invalid patterns)
                if old_subset and not self._should_clear_old_subset(old_subset):
                    if not combine_operator:
                        combine_operator = 'AND'
                        self.log_info(f"🔗 Préservation du filtre existant avec {combine_operator}")
                    self.log_info(f"  → Ancien subset: '{old_subset[:80]}...' (longueur: {len(old_subset)})")
                    self.log_info(f"  → Nouveau filtre: '{new_subset_expression[:80]}...'")
                    final_expression = f"({old_subset}) {combine_operator} ({new_subset_expression})"
                    self.log_info(f"  → Expression combinée: longueur {len(final_expression)} chars")
                else:
                    final_expression = new_subset_expression
                
                # Apply subset filter
                # THREAD SAFETY FIX: Use queue callback if available (called from background thread)
                queue_callback = self.task_params.get('_subset_queue_callback')
                
                # DIAGNOSTIC
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"Applying subset on {layer.name()}: queue_callback={'Yes' if queue_callback else 'No'}, expr_len={len(final_expression)}",
                    "FilterMate", Qgis.Info
                )
                
                if queue_callback:
                    queue_callback(layer, final_expression)
                    self.log_debug(f"OGR filter queued for main thread application")
                    result = True
                else:
                    self.log_warning(f"No queue callback - applying directly (may cause thread issues)")
                    result = safe_set_subset_string(layer, final_expression)
                    
                if result:
                    try:
                        final_count = layer.featureCount()
                    except (RuntimeError, AttributeError):
                        final_count = -1  # Unknown
                    
                    QgsMessageLog.logMessage(
                        f"✓ Subset applied on {layer.name()}: {final_count} features",
                        "FilterMate", Qgis.Info
                    )
                    
                    self.log_info(f"✓ {layer.name()}: {final_count if not queue_callback else '(pending)'} features")
                    
                    # Clear selection safely
                    try:
                        layer.removeSelection()
                    except (RuntimeError, AttributeError):
                        pass
                    
                    if final_count == 0 and selected_count > 0 and not queue_callback:
                        self.log_warning(f"Filter returned 0 features - check primary key '{pk_field}'")
                    
                    return True
                else:
                    QgsMessageLog.logMessage(
                        f"✗ Subset FAILED on {layer.name()}",
                        "FilterMate", Qgis.Critical
                    )
                    self.log_error(f"✗ Filter failed for {layer.name()}")
                    try:
                        layer.removeSelection()
                    except (RuntimeError, AttributeError):
                        pass
                    # FIX v2.4.18: Restore original subset if filter application failed
                    if existing_subset:
                        self.log_warning(f"Restoring original subset after filter failure")
                        safe_set_subset_string(layer, existing_subset)
                    return False
            else:
                self.log_debug("No features selected by geometric filter")
                # THREAD SAFETY FIX for empty result
                # v2.6.9: FIX - Use unquoted 'fid = -1' for OGR/GeoPackage compatibility
                empty_filter = 'fid = -1'  # No valid FID is -1
                queue_callback = self.task_params.get('_subset_queue_callback')
                if queue_callback:
                    queue_callback(layer, empty_filter)
                else:
                    safe_set_subset_string(layer, empty_filter)
                return True
                
        except Exception as select_error:
            self.log_error(f"Select by location failed: {str(select_error)}")
            # FIX v2.4.18: Restore original subset on exception
            if existing_subset:
                self.log_warning(f"Restoring original subset after exception")
                try:
                    safe_set_subset_string(layer, existing_subset)
                except Exception:
                    pass
            return False
    
    def _apply_filter_large(
        self, layer, source_layer, predicates, buffer_value,
        old_subset, combine_operator
    ):
        """
        Optimized filtering for large datasets (≥10k features).
        
        Strategy:
        1. Use spatial index for fast pre-filtering
        2. Store match result in temporary attribute
        3. Use attribute-based subset string (faster than ID list)
        
        Performance: O(log n) with spatial index vs O(n) without.
        
        STABILITY FIX v2.3.9: Falls back to standard method if layer cannot be edited
        (e.g., read-only GeoPackage, locked database, etc.)
        FIX v2.4.18: Clear existing subset before selectbylocation to prevent GDAL errors.
        """
        # Initialize existing_subset early for exception handling
        existing_subset = None
        
        try:
            # STABILITY FIX v2.3.9: Validate layer before any operations
            if layer is None or not layer.isValid():
                self.log_error("Layer is None or invalid - cannot proceed with large dataset filtering")
                return False
            
            # Check if layer supports editing (some formats are read-only)
            try:
                caps = layer.dataProvider().capabilities()
                from qgis.core import QgsVectorDataProvider
                can_edit = bool(caps & QgsVectorDataProvider.AddAttributes) and bool(caps & QgsVectorDataProvider.ChangeAttributeValues)
                if not can_edit:
                    self.log_info(f"Layer {layer.name()} does not support attribute editing - using standard method")
                    return self._apply_filter_standard(
                        layer, source_layer, predicates, buffer_value,
                        old_subset, combine_operator
                    )
            except Exception as caps_error:
                self.log_warning(f"Could not check layer capabilities: {caps_error} - trying standard method")
                return self._apply_filter_standard(
                    layer, source_layer, predicates, buffer_value,
                    old_subset, combine_operator
                )
            
            # FIX v2.4.18: Save and temporarily clear existing subset string
            # This prevents GDAL "feature id out of available range" errors
            existing_subset = layer.subsetString()
            if existing_subset:
                self.log_info(f"🔄 Temporarily clearing existing subset on {layer.name()} for large dataset filtering")
                self.log_debug(f"  → Existing subset: '{existing_subset[:100]}...'")
                safe_set_subset_string(layer, "")
                if old_subset is None:
                    old_subset = existing_subset
            
            # Apply buffer
            intersect_layer = self._apply_buffer(source_layer, buffer_value)
            if intersect_layer is None:
                # Restore original subset if buffer failed
                if existing_subset:
                    safe_set_subset_string(layer, existing_subset)
                return False
            
            # Map predicates
            predicate_codes = self._map_predicates(predicates)
            
            # Add temporary field for marking matches
            temp_field = "_fm_match_"
            self.log_info(f"Using optimized large-dataset method with temp field '{temp_field}'")
            
            # Check if temp field already exists
            field_names = [field.name() for field in layer.fields()]
            if temp_field in field_names:
                self.log_debug(f"Temp field '{temp_field}' already exists")
            else:
                from qgis.core import QgsField
                from qgis.PyQt.QtCore import QMetaType
                import time
                
                # STABILITY FIX v2.4.2: Enhanced retry logic for SQLite concurrent access
                # When multiple layers from the same GeoPackage/Spatialite are filtered,
                # SQLite can throw "unable to open database file" errors due to file locking.
                # Use longer delays and more retries for reliable operation.
                max_retries = 8  # Increased from 5
                retry_delay = 1.0  # Increased from 0.5s - SQLite needs more time to release locks
                add_field_success = False
                
                for attempt in range(max_retries):
                    try:
                        # Use GDAL error handler to suppress transient SQLite warnings
                        with GdalErrorHandler():
                            result = layer.dataProvider().addAttributes([QgsField(temp_field, QMetaType.Type.Int)])
                            if result:
                                layer.updateFields()
                                add_field_success = True
                                self.log_debug(f"Added temp field '{temp_field}' to '{layer.name()}' on attempt {attempt + 1}")
                                break
                            else:
                                # addAttributes returned False - likely database lock
                                if attempt < max_retries - 1:
                                    self.log_info(
                                        f"⏳ SQLite lock on '{layer.name()}' (attempt {attempt + 1}/{max_retries}). "
                                        f"Waiting {retry_delay:.1f}s for lock release..."
                                    )
                                    time.sleep(retry_delay)
                                    retry_delay = min(retry_delay * 1.5, 8.0)  # Gentler backoff, max 8s
                    except Exception as add_attr_error:
                        error_str = str(add_attr_error).lower()
                        is_recoverable = any(x in error_str for x in [
                            'unable to open database file',
                            'database is locked',
                            'disk i/o error',
                            'sqlite3_exec',
                            'busy',
                        ])
                        
                        if is_recoverable and attempt < max_retries - 1:
                            self.log_info(
                                f"⏳ SQLite error for '{layer.name()}' (attempt {attempt + 1}/{max_retries}): "
                                f"{add_attr_error}. Waiting {retry_delay:.1f}s..."
                            )
                            time.sleep(retry_delay)
                            retry_delay = min(retry_delay * 1.5, 8.0)  # Same backoff as above
                        else:
                            self.log_error(f"Failed to add temp field to '{layer.name()}' after {max_retries} attempts: {add_attr_error}")
                            # Fall back to standard method which doesn't need attribute editing
                            return self._apply_filter_standard(
                                layer, source_layer, predicates, buffer_value,
                                old_subset, combine_operator
                            )
                
                if not add_field_success:
                    self.log_warning(f"Could not add temp field to '{layer.name()}' - falling back to standard method")
                    return self._apply_filter_standard(
                        layer, source_layer, predicates, buffer_value,
                        old_subset, combine_operator
                    )
            
            # Initialize all to 0 (no match)
            field_idx = layer.fields().indexFromName(temp_field)
            if field_idx < 0:
                self.log_error(f"Temp field '{temp_field}' not found after creation")
                return False
            
            # STABILITY FIX v2.3.12: Use data provider directly instead of edit mode
            # startEditing/commitChanges trigger layer signals that cause access violations
            # when called from background threads (the main thread's UI reacts to these signals)
            # Using data provider bypasses the signal mechanism and is thread-safe.
            data_provider = layer.dataProvider()
            if data_provider is None:
                self.log_error(f"Layer {layer.name()} has no data provider")
                return False
            
            # STABILITY FIX v2.3.9: Use feature IDs list to avoid iterator issues
            # Materializing the feature list first prevents concurrent modification issues
            try:
                with GdalErrorHandler():
                    feature_ids = [f.id() for f in layer.getFeatures()]
            except (RuntimeError, AttributeError) as e:
                self.log_error(f"Failed to get features for initialization: {e}")
                return False
            
            # Initialize all values to 0 using data provider (no edit mode)
            # STABILITY FIX v2.4.2: Enhanced retry logic for concurrent SQLite access
            import time
            max_retries = 8  # Increased from 5
            retry_delay = 1.0  # Increased from 0.5s
            init_success = False
            
            for attempt in range(max_retries):
                try:
                    # Build attribute changes dict: {fid: {field_idx: value}}
                    attr_changes = {fid: {field_idx: 0} for fid in feature_ids}
                    with GdalErrorHandler():
                        if data_provider.changeAttributeValues(attr_changes):
                            init_success = True
                            break
                        else:
                            if attempt < max_retries - 1:
                                self.log_info(f"⏳ SQLite lock during init for '{layer.name()}' (attempt {attempt + 1}/{max_retries}). Waiting {retry_delay:.1f}s...")
                                time.sleep(retry_delay)
                                retry_delay = min(retry_delay * 1.5, 8.0)
                except (RuntimeError, AttributeError) as e:
                    error_str = str(e).lower()
                    is_recoverable = any(x in error_str for x in [
                        'unable to open database file', 'database is locked', 'sqlite3_exec', 'busy',
                    ])
                    if is_recoverable and attempt < max_retries - 1:
                        self.log_info(f"⏳ SQLite error during init for '{layer.name()}' (attempt {attempt + 1}/{max_retries}): {e}. Waiting {retry_delay:.1f}s...")
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 1.5, 8.0)
                    else:
                        self.log_error(f"Error during initialization: {e}")
                        return self._apply_filter_standard(
                            layer, source_layer, predicates, buffer_value,
                            old_subset, combine_operator
                        )
            
            if not init_success:
                self.log_warning(f"Could not initialize temp field values - falling back to standard method")
                return self._apply_filter_standard(
                    layer, source_layer, predicates, buffer_value,
                    old_subset, combine_operator
                )
            
            # STABILITY FIX v2.3.9: Use safe wrapper for selectbylocation
            if not self._safe_select_by_location(layer, intersect_layer, predicate_codes):
                self.log_error("Safe select by location failed in large dataset method")
                return False
            
            selected_count = layer.selectedFeatureCount()

            
            if selected_count > 0:
                # Mark selected features in temp field
                # STABILITY FIX v2.3.12: Use data provider directly instead of edit mode
                # This prevents access violations caused by layer signals from background threads
                try:
                    with GdalErrorHandler():
                        selected_features = list(layer.selectedFeatures())
                except (RuntimeError, AttributeError) as e:
                    self.log_error(f"Failed to get selected features: {e}")
                    return False
                
                # Use data provider to update attribute values (thread-safe, no signals)
                # STABILITY FIX v2.4.2: Enhanced retry logic for concurrent SQLite access
                mark_success = False
                retry_delay = 1.0  # Increased from 0.5s
                
                for attempt in range(max_retries):
                    try:
                        # Build attribute changes dict: {fid: {field_idx: value}}
                        attr_changes = {f.id(): {field_idx: 1} for f in selected_features}
                        with GdalErrorHandler():
                            if data_provider.changeAttributeValues(attr_changes):
                                mark_success = True
                                break
                            else:
                                if attempt < max_retries - 1:
                                    self.log_info(f"⏳ SQLite lock during mark for '{layer.name()}' (attempt {attempt + 1}/{max_retries}). Waiting {retry_delay:.1f}s...")
                                    time.sleep(retry_delay)
                                    retry_delay = min(retry_delay * 1.5, 8.0)
                    except (RuntimeError, AttributeError) as e:
                        error_str = str(e).lower()
                        is_recoverable = any(x in error_str for x in [
                            'unable to open database file', 'database is locked', 'sqlite3_exec', 'busy',
                        ])
                        if is_recoverable and attempt < max_retries - 1:
                            self.log_info(f"⏳ SQLite error during mark for '{layer.name()}' (attempt {attempt + 1}/{max_retries}): {e}. Waiting {retry_delay:.1f}s...")
                            time.sleep(retry_delay)
                            retry_delay = min(retry_delay * 1.5, 8.0)
                        else:
                            self.log_error(f"Error during attribute update: {e}")
                            return False
                
                if not mark_success:
                    self.log_error(f"Failed to mark selected features after {max_retries} attempts")
                    return False
                
                # Clear selection - wrapped in try-except for safety
                try:
                    layer.removeSelection()
                except (RuntimeError, AttributeError):
                    self.log_warning("Could not clear selection (layer may be invalid)")
                
                # Use attribute-based filter (much faster than ID list for large datasets)
                escaped_temp = escape_ogr_identifier(temp_field)
                new_subset_expression = f'{escaped_temp} = 1'
                
                # Combine with old subset if needed (but not if it contains invalid patterns)
                if old_subset and not self._should_clear_old_subset(old_subset):
                    if not combine_operator:
                        combine_operator = 'AND'
                        self.log_info(f"🔗 Préservation du filtre existant avec {combine_operator}")
                    self.log_info(f"  → Ancien subset: '{old_subset[:80]}...' (longueur: {len(old_subset)})")
                    final_expression = f"({old_subset}) {combine_operator} ({new_subset_expression})"
                    self.log_info(f"  → Expression combinée: longueur {len(final_expression)} chars")
                else:
                    final_expression = new_subset_expression
                
                # Apply subset filter
                # THREAD SAFETY FIX: Use queue callback if available (called from background thread)
                queue_callback = self.task_params.get('_subset_queue_callback')
                
                if queue_callback:
                    queue_callback(layer, final_expression)
                    self.log_debug(f"OGR large filter queued for main thread application")
                    result = True
                else:
                    self.log_warning(f"No queue callback - applying directly (may cause thread issues)")
                    result = safe_set_subset_string(layer, final_expression)
                    
                if result:
                    if not queue_callback:
                        final_count = layer.featureCount()
                        self.log_info(f"✓ {layer.name()}: {final_count} features")
                    else:
                        self.log_info(f"✓ {layer.name()}: filter queued")
                    return True
                else:
                    self.log_error(f"✗ Filter failed for {layer.name()}")
                    return False
            else:
                self.log_debug("No features selected by geometric filter")
                # THREAD SAFETY FIX for empty result
                # v2.6.9: FIX - Use unquoted 'fid = -1' for OGR/GeoPackage compatibility
                empty_filter = 'fid = -1'  # No valid FID is -1
                queue_callback = self.task_params.get('_subset_queue_callback')
                if queue_callback:
                    queue_callback(layer, empty_filter)
                else:
                    safe_set_subset_string(layer, empty_filter)
                return True
                
        except Exception as e:
            self.log_error(f"Large dataset filtering failed: {str(e)}")
            # Fallback to standard method
            return self._apply_filter_standard(
                layer, source_layer, predicates, buffer_value,
                old_subset, combine_operator
            )
    
    def _apply_filter_with_memory_optimization(
        self, original_layer, memory_layer, predicates, buffer_value,
        old_subset, combine_operator
    ):
        """
        Apply filter using memory layer for spatial calculations.
        
        This method is used for small PostgreSQL datasets optimization:
        1. Perform spatial selection on the memory layer (fast, no network)
        2. Get the IDs of selected features
        3. Apply the resulting subset filter to the original PostgreSQL layer
        
        Performance: Avoids network overhead for spatial queries on small datasets.
        Typically 2-10× faster than direct PostgreSQL queries for < 5000 features.
        
        Args:
            original_layer: The original PostgreSQL layer to apply filter to
            memory_layer: In-memory copy of the layer for spatial calculations
            predicates: Spatial predicates to apply
            buffer_value: Optional buffer distance
            old_subset: Existing subset string on original layer
            combine_operator: Operator for combining with existing filter
            
        Returns:
            True if filter applied successfully
        """
        try:
            from qgis import processing
            from ..appUtils import get_primary_key_name
            from qgis.PyQt.QtCore import QMetaType
            
            # Apply buffer to source geometry if needed
            source_layer = getattr(self, 'source_geom', None)
            if not source_layer:
                self.log_error("No source layer/geometry provided for geometric filtering")
                return False
            
            intersect_layer = self._apply_buffer(source_layer, buffer_value)
            if intersect_layer is None:
                return False
            
            # Map predicates
            predicate_codes = self._map_predicates(predicates)
            
            self.log_info(f"⚡ Memory optimization: Selecting features from memory layer")
            self.log_info(f"  → Memory layer: {memory_layer.name()} ({memory_layer.featureCount()} features)")
            self.log_info(f"  → Predicates: {predicate_codes}")
            
            # STABILITY FIX v2.3.9: Use safe wrapper for selectbylocation
            if not self._safe_select_by_location(memory_layer, intersect_layer, predicate_codes):
                self.log_error("Safe select by location failed in memory optimization")
                return False
            
            selected_count = memory_layer.selectedFeatureCount()
            self.log_info(f"  → Selected {selected_count} features in memory layer")
            
            if selected_count > 0:
                # Get primary key from original PostgreSQL layer
                pk_field = get_primary_key_name(original_layer)
                if not pk_field:
                    pk_field = get_primary_key_name(memory_layer)
                
                if not pk_field:
                    self.log_error("No primary key found for PostgreSQL layer - cannot transfer selection")
                    memory_layer.removeSelection()
                    return False
                
                # Get primary key values from selected features in memory layer
                field_idx = memory_layer.fields().indexFromName(pk_field)
                if field_idx < 0:
                    self.log_error(f"Primary key field '{pk_field}' not found in memory layer")
                    memory_layer.removeSelection()
                    return False
                
                field_type = memory_layer.fields()[field_idx].type()
                
                # Extract primary key values from selected features
                # STABILITY FIX v2.3.9: Wrap in try-except to catch access violations
                try:
                    selected_values = [f.attribute(pk_field) for f in memory_layer.selectedFeatures()]
                except (RuntimeError, AttributeError) as e:
                    self.log_error(f"Failed to get selected features from memory layer: {e}")
                    try:
                        memory_layer.removeSelection()
                    except:
                        pass
                    return False
                
                # Build subset expression for PostgreSQL layer
                if field_type == QMetaType.Type.QString:
                    id_list = ','.join(f"'{str(val).replace(chr(39), chr(39)+chr(39))}'" for val in selected_values)
                else:
                    id_list = ','.join(str(val) for val in selected_values)
                
                # PostgreSQL uses double quotes for identifiers
                escaped_pk = f'"{pk_field}"'
                new_subset_expression = f'{escaped_pk} IN ({id_list})'
                
                self.log_debug(f"  → Generated PostgreSQL subset using key '{pk_field}'")
                
                # Clear memory layer selection
                memory_layer.removeSelection()
                
                # Combine with old subset if needed (but not if it contains invalid patterns)
                if old_subset and not self._should_clear_old_subset(old_subset):
                    if not combine_operator:
                        combine_operator = 'AND'
                        self.log_info(f"🔗 Préservation du filtre existant avec {combine_operator}")
                    self.log_info(f"  → Ancien subset: '{old_subset[:80]}...'")
                    final_expression = f"({old_subset}) {combine_operator} ({new_subset_expression})"
                else:
                    final_expression = new_subset_expression
                
                # Apply subset filter to ORIGINAL PostgreSQL layer
                # THREAD SAFETY FIX: Use queue callback if available (called from background thread)
                queue_callback = self.task_params.get('_subset_queue_callback')
                
                if queue_callback:
                    queue_callback(original_layer, final_expression)
                    self.log_debug(f"OGR PostgreSQL filter queued for main thread application")
                    result = True
                else:
                    self.log_warning(f"No queue callback - applying directly (may cause thread issues)")
                    result = safe_set_subset_string(original_layer, final_expression)
                    
                if result:
                    if not queue_callback:
                        final_count = original_layer.featureCount()
                        self.log_info(f"✓ {original_layer.name()}: {final_count} features (via memory optimization)")
                    else:
                        self.log_info(f"✓ {original_layer.name()}: filter queued (via memory optimization)")
                    return True
                else:
                    self.log_error(f"✗ Filter failed for {original_layer.name()}")
                    return False
            else:
                self.log_debug("No features selected by geometric filter (memory optimization)")
                memory_layer.removeSelection()
                # THREAD SAFETY FIX for empty result
                # v2.6.9: FIX - Use unquoted 'fid = -1' for OGR/GeoPackage compatibility
                empty_filter = 'fid = -1'  # No valid FID is -1
                queue_callback = self.task_params.get('_subset_queue_callback')
                if queue_callback:
                    queue_callback(original_layer, empty_filter)
                else:
                    safe_set_subset_string(original_layer, empty_filter)
                return True
                
        except Exception as e:
            self.log_error(f"Memory optimization filtering failed: {str(e)}")
            import traceback
            self.log_debug(f"Traceback: {traceback.format_exc()}")
            # Clear memory layer selection if exists
            if memory_layer:
                try:
                    memory_layer.removeSelection()
                except (RuntimeError, AttributeError):
                    pass  # Layer may have been deleted or is invalid
            return False
    
    def get_backend_name(self) -> str:
        """Get backend name"""
        return "OGR"

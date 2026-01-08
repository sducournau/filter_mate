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

import logging
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
from ..appUtils import safe_set_subset_string, clean_buffer_value

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

# v2.8.11: Import Spatialite Cache for multi-step filtering
# OGR backend uses the same cache as Spatialite for FID persistence
try:
    from .spatialite_cache import (
        get_cache as get_spatialite_cache,
        store_filter_fids,
        get_previous_filter_fids,
        intersect_filter_fids,
        SpatialiteCacheDB
    )
    SPATIALITE_CACHE_AVAILABLE = True
except ImportError:
    SPATIALITE_CACHE_AVAILABLE = False
    get_spatialite_cache = None
    store_filter_fids = None
    get_previous_filter_fids = None
    intersect_filter_fids = None
    SpatialiteCacheDB = None

logger = get_tasks_logger()

# Thread safety tracking (v2.3.9)
_ogr_operations_lock = threading.Lock()
_last_operation_thread = None


def cleanup_ogr_temp_layers(backend_instance):
    """
    v2.9.24: Clean up temporary GEOS-safe layers for an OGR backend instance.
    
    CRITICAL: This should only be called when ALL target layers have been filtered,
    not between individual layers. Premature cleanup causes garbage collection of
    safe_intersect layers that are still needed for subsequent target layers.
    
    Args:
        backend_instance: Instance of OGRGeometricFilter
    """
    if hasattr(backend_instance, '_temp_layers_keep_alive') and backend_instance._temp_layers_keep_alive:
        layer_count = len(backend_instance._temp_layers_keep_alive)
        backend_instance._temp_layers_keep_alive = []
        if hasattr(backend_instance, 'log_debug'):
            backend_instance.log_debug(f"🧹 Cleaned up {layer_count} temporary GEOS-safe layers after filter operation")
    if hasattr(backend_instance, '_source_layer_keep_alive') and backend_instance._source_layer_keep_alive:
        backend_instance._source_layer_keep_alive = []
        if hasattr(backend_instance, 'log_debug'):
            backend_instance.log_debug("🧹 Cleaned up source layer references")


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
    
    # NOTE: _should_clear_old_subset() and _is_fid_only_filter() are inherited from
    # GeometricFilterBackend (base_backend.py) - v2.8.6 harmonization

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
                # NOTE: QgsVectorLayer is already imported at module level (line 48)
                # Using local import here would shadow the global and cause:
                # "cannot access local variable 'QgsVectorLayer'" errors in Python 3.11+
                from qgis.core import QgsFeatureRequest
                
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
                # FIX v3.0.10: Check if buffer is already applied from previous step
                if hasattr(self, 'task_params') and self.task_params:
                    infos = self.task_params.get('infos', {})
                    buffer_state = infos.get('buffer_state', {})
                    is_pre_buffered = buffer_state.get('is_pre_buffered', False)

                    if is_pre_buffered and buffer_value != 0:
                        # Buffer already applied - use source layer directly
                        self.log_info(f"  ✓ Multi-step filter: Using pre-buffered source ({buffer_value}m)")
                        intersect_layer = source_layer
                    else:
                        # Apply buffer fresh
                        intersect_layer = self._apply_buffer(source_layer, buffer_value)
                        if intersect_layer is None:
                            return False

                        # Store buffered layer for potential reuse in next step
                        if buffer_value != 0:
                            self._buffered_source_layer = intersect_layer
                            # Also update infos to mark buffer as pre-applied for next step
                            if 'buffer_state' in infos:
                                infos['buffer_state']['is_pre_buffered'] = True
                                self.log_info(f"  ✓ Stored buffered layer for potential reuse in multi-step filter")
                else:
                    # No task_params - apply buffer normally
                    intersect_layer = self._apply_buffer(source_layer, buffer_value)
                    if intersect_layer is None:
                        return False
                
                # Map predicates
                predicate_codes = self._map_predicates(predicates)
                
                # Run selectbylocation on temp layer
                if not self._safe_select_by_location(temp_layer, intersect_layer, predicate_codes):
                    self.log_warning("Spatial selection on temp layer failed")
                    return None
                
                # Get final matching IDs - collect both QGIS FIDs and PK values
                final_matching = set()
                matching_fids = []  # For cache (QGIS FIDs)
                for feat in temp_layer.selectedFeatures():
                    # Need to map back to original layer FIDs
                    # Features in temp layer have same attribute values
                    final_matching.add(feat.id())
                    matching_fids.append(feat.id())
                
                # v2.8.11: MULTI-STEP FILTERING - Intersect with previous cache if exists
                # v2.9.30: FIX - Also pass buffer_val and predicates_list to avoid wrong intersection
                step_number = 1
                source_wkt = ""
                predicates_list = []
                buffer_val = 0.0
                if hasattr(self, 'task_params') and self.task_params:
                    infos = self.task_params.get('infos', {})
                    source_wkt = infos.get('source_geom_wkt', '')
                    # v2.8.12: FIX - geometric_predicates can be list or dict
                    geom_preds = self.task_params.get('filtering', {}).get('geometric_predicates', [])
                    if isinstance(geom_preds, dict):
                        predicates_list = list(geom_preds.keys())
                    elif isinstance(geom_preds, list):
                        predicates_list = geom_preds
                    else:
                        predicates_list = []
                    # FIX v3.0.12: Clean buffer value from float precision errors
                    buffer_val = clean_buffer_value(self.task_params.get('filtering', {}).get('buffer_value', 0.0))
                
                if SPATIALITE_CACHE_AVAILABLE and intersect_filter_fids and old_subset:
                    # v2.9.43: CRITICAL - Cache multi-step only supports AND operator
                    cache_operator = None
                    if hasattr(self, 'task_params') and self.task_params:
                        cache_operator = self.task_params.get('_current_combine_operator')
                    
                    if cache_operator in ('OR', 'NOT AND'):
                        self.log_warning(
                            f"⚠️ OGR Multi-step filtering with {cache_operator} - "
                            f"cache intersection not supported (only AND), performing full filter"
                        )
                        # Skip cache intersection for OR/NOT AND
                    else:
                        # AND or None → use cache intersection
                        previous_fids = get_previous_filter_fids(layer, source_wkt, buffer_val, predicates_list)
                        if previous_fids is not None:
                            original_count = len(matching_fids)
                            matching_fids_set, step_number = intersect_filter_fids(
                                layer, set(matching_fids), source_wkt, buffer_val, predicates_list
                            )
                            matching_fids = list(matching_fids_set)
                            final_matching = matching_fids_set
                            self.log_info(f"  🔄 Multi-step intersection: {original_count} ∩ {len(previous_fids)} = {len(matching_fids)}")
                            from qgis.core import QgsMessageLog, Qgis
                            QgsMessageLog.logMessage(
                                f"  → OGR ATTRIBUTE_FIRST Multi-step step {step_number}: {original_count} ∩ {len(previous_fids)} = {len(matching_fids)} FIDs",
                                "FilterMate", Qgis.Info  # DEBUG
                            )
                
                # v2.8.11: Store result in cache for future multi-step filtering
                if SPATIALITE_CACHE_AVAILABLE and store_filter_fids and matching_fids:
                    try:
                        
                        cache_key = store_filter_fids(
                            layer=layer,
                            fids=matching_fids,
                            source_geom_wkt=source_wkt,
                            predicates=predicates_list,
                            buffer_value=buffer_val,
                            step_number=step_number
                        )
                        self.log_info(f"  💾 OGR ATTRIBUTE_FIRST Cached {len(matching_fids)} FIDs (key={cache_key[:8] if cache_key else 'N/A'}, step={step_number})")
                    except Exception as cache_err:
                        self.log_debug(f"Cache storage failed (non-fatal): {cache_err}")
                
                # The FIDs in temp_layer match the original because we copied them
                # But we need to use the attribute values to find original FIDs
                from ..appUtils import get_primary_key_name
                pk_field = get_primary_key_name(layer)
                
                if pk_field:
                    # Get PK values from selected temp features
                    # v2.8.11: Only get PK values for FIDs that passed cache intersection
                    pk_values = []
                    for feat in temp_layer.selectedFeatures():
                        if feat.id() in final_matching:  # Only include if in intersected set
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
                    # Fall back to $id - use final_matching (already intersected with cache)
                    if final_matching:
                        id_list = ','.join(str(fid) for fid in final_matching)
                        new_expression = f'$id IN ({id_list})'
                    else:
                        # v2.6.9: FIX - Use unquoted 'fid = -1' for OGR/GeoPackage compatibility
                        new_expression = 'fid = -1'  # No valid FID is -1
                
                # Combine with old subset if needed
                # v3.0.7: FID filters from previous step MUST be combined (not replaced)
                # v2.8.6: Use shared _is_fid_only_filter() from base_backend
                if old_subset and not self._should_clear_old_subset(old_subset):
                    is_fid_only = self._is_fid_only_filter(old_subset)
                    
                    if is_fid_only:
                        # FID filter from previous step - ALWAYS combine
                        final_expression = f"({old_subset}) AND ({new_expression})"
                    elif combine_operator is None:
                        # v3.0.7: Use default AND instead of REPLACE
                        final_expression = f"({old_subset}) AND ({new_expression})"
                    else:
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

        # FIX v3.0.10: Check for pre-buffered layer from previous multi-step operation
        # If buffer is already applied, store the buffered layer reference instead
        if hasattr(self, 'task_params') and self.task_params:
            infos = self.task_params.get('infos', {})
            buffer_state = infos.get('buffer_state', {})
            is_pre_buffered = buffer_state.get('is_pre_buffered', False)

            if is_pre_buffered and buffer_value != 0:
                # Check if we have a stored buffered layer from previous step
                buffered_layer = getattr(self, '_buffered_source_layer', None)
                if buffered_layer and isinstance(buffered_layer, QgsVectorLayer) and buffered_layer.isValid():
                    self.log_info(f"  ✓ Multi-step filter: Reusing buffered layer from previous step ({buffer_value}m buffer)")
                    # Use buffered layer as source
                    self.source_geom = buffered_layer
                else:
                    self.log_warning(f"  ⚠️  Multi-step filter: Buffered layer not found or invalid - will recompute")

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
                # FIX v3.0.12: Clean buffer value from float precision errors
                buffer_value = clean_buffer_value(params.get('buffer_value'))
                
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
                
                # FIX v2.9.13: CRITICAL - Keep source_geom alive across ALL target layers
                # PROBLEM: source_geom (e.g., 'source_from_task') is a memory layer created ONCE in FilterTask
                # and REUSED for filtering ALL target layers (Ducts, End Cable, Home Count, etc.).
                # Qt's C++ GC may delete it after 5-6 iterations if no persistent Python reference exists.
                #
                # SOLUTION: Maintain TWO separate reference lists:
                # 1. _source_layer_keep_alive: PERSISTENT - retains source_geom across all iterations
                # 2. _temp_layers_keep_alive: CLEARED each iteration - holds GEOS-safe layers for current target
                #
                # This prevents "wrapped C/C++ object has been deleted" errors when processing layer 6+
                
                # Get source layer - should be set by build_expression
                source_layer = getattr(self, 'source_geom', None)
                
                # Initialize persistent source layer reference (ONCE per filter operation)
                if not hasattr(self, '_source_layer_keep_alive') or self._source_layer_keep_alive is None:
                    self._source_layer_keep_alive = []
                    if source_layer is not None and isinstance(source_layer, QgsVectorLayer):
                        self._source_layer_keep_alive.append(source_layer)
                        self.log_debug(f"🔒 PERSISTENT reference created for source_geom '{source_layer.name()}'")
                
                # FIX v2.9.24: DO NOT clear _temp_layers_keep_alive between target layers!
                # CRITICAL BUG: safe_intersect layers created for layer N are garbage-collected
                # before layer N+1 can use them, causing "wrapped C/C++ object has been deleted".
                # The same source_geom (e.g., 'output') is REUSED across multiple target layers,
                # but the GEOS-safe wrapper (safe_intersect) was being deleted after each layer.
                # SOLUTION: Accumulate temp layers throughout the ENTIRE filter operation,
                # only clear when the full task completes (in finished() or cancel()).
                if not hasattr(self, '_temp_layers_keep_alive'):
                    self._temp_layers_keep_alive = []
                    self.log_debug("🆕 Initialized _temp_layers_keep_alive list")
                # DO NOT CLEAR - let them accumulate for the entire filter operation
                # self.log_debug(f"🔒 Retaining {len(self._temp_layers_keep_alive)} temp layers from previous iterations")
                
                # DIAGNOSTIC: Log source layer state
                # FIX v2.6.13: Also log to QGIS MessagePanel for visibility
                from qgis.core import QgsMessageLog, Qgis
                
                self.log_info(f"📍 OGR source_geom state for {layer.name()}:")
                if source_layer is None:
                    self.log_error("  → source_geom is None!")
                    QgsMessageLog.logMessage(
                        f"OGR apply_filter: source_geom is None for '{layer.name()}'",
                        "FilterMate", Qgis.Critical
                    )
                    return False  # FIX v2.9.9: Return False immediately if source is None
                elif not isinstance(source_layer, QgsVectorLayer):
                    self.log_error(f"  → source_geom is not a QgsVectorLayer: {type(source_layer).__name__}")
                    QgsMessageLog.logMessage(
                        f"OGR apply_filter: source_geom is not a QgsVectorLayer for '{layer.name()}': {type(source_layer).__name__}",
                        "FilterMate", Qgis.Critical
                    )
                    return False  # FIX v2.9.9: Return False immediately if source type is wrong
                elif not source_layer.isValid():
                    # FIX v2.9.9: Check if source layer is still valid (might have been GC'd)
                    self.log_error(f"  → source_geom is INVALID (layer: {source_layer.name()})")
                    QgsMessageLog.logMessage(
                        f"OGR apply_filter: source_geom is INVALID for '{layer.name()}' - layer may have been garbage collected",
                        "FilterMate", Qgis.Critical
                    )
                    return False  # FIX v2.9.9: Return False if source layer is invalid
                elif source_layer.featureCount() == 0:
                    # FIX v2.9.9: Check if source layer has features
                    self.log_error(f"  → source_geom has 0 features (layer: {source_layer.name()})")
                    QgsMessageLog.logMessage(
                        f"OGR apply_filter: source_geom has 0 features for '{layer.name()}'",
                        "FilterMate", Qgis.Critical
                    )
                    return False  # FIX v2.9.9: Return False if source has no features
                else:
                    self.log_info(f"  → Name: {source_layer.name()}")
                    self.log_info(f"  → Valid: {source_layer.isValid()}")
                    self.log_info(f"  → Feature count: {source_layer.featureCount()}")
                    # Log summary to MessagePanel
                    QgsMessageLog.logMessage(
                        f"OGR apply_filter: source_geom for '{layer.name()}' = '{source_layer.name()}' "
                        f"(valid={source_layer.isValid()}, features={source_layer.featureCount()})",
                        "FilterMate", Qgis.Info  # DEBUG
                    )
                    if source_layer.featureCount() > 0:
                        # Check first geometry
                        for feat in source_layer.getFeatures():
                            geom = feat.geometry()
                            self.log_info(f"  → First geometry valid: {geom is not None and not geom.isEmpty()}")
                            if geom and not geom.isEmpty():
                                self.log_info(f"  → First geometry type: {geom.wkbType()}")
                                # FIX v2.8.13: Log detailed geometry info to QGIS MessagePanel
                                QgsMessageLog.logMessage(
                                    f"OGR apply_filter: first geometry for '{layer.name()}' - "
                                    f"type={geom.wkbType()}, isNull={geom.isNull()}, isEmpty={geom.isEmpty()}, "
                                    f"area={geom.area():.2f}",
                                    "FilterMate", Qgis.Info  # DEBUG
                                )
                            else:
                                # FIX v2.8.13: Log if geometry is invalid
                                QgsMessageLog.logMessage(
                                    f"OGR apply_filter: first geometry for '{layer.name()}' is INVALID - "
                                    f"geom is None: {geom is None}, isEmpty: {geom.isEmpty() if geom else 'N/A'}",
                                    "FilterMate", Qgis.Warning
                                )
                            break
                
                if not source_layer:
                    # FIX v2.9.9: This should never be reached due to earlier checks, but keep for safety
                    self.log_error("No source layer/geometry provided for geometric filtering (should have been caught earlier)")
                    return False
                
                # Check feature count and decide on strategy
                feature_count = layer.featureCount()
                
                # FIX v2.8.13: Log target layer details
                QgsMessageLog.logMessage(
                    f"OGR apply_filter: target layer '{layer.name()}' has {feature_count} features",
                    "FilterMate", Qgis.Info  # DEBUG
                )
                
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
                        # FIX v2.8.13: Log multi-step path for debugging
                        QgsMessageLog.logMessage(
                            f"OGR apply_filter: trying MULTI-STEP optimizer for '{layer.name()}' "
                            f"(features={feature_count}, attr_filter={attribute_filter is not None})",
                            "FilterMate", Qgis.Info  # DEBUG
                        )
                        multi_result = self._try_multi_step_filter(
                            layer, attribute_filter, source_layer, predicates,
                            buffer_value, old_subset, combine_operator
                        )
                        
                        if multi_result is not None:
                            # FIX v2.8.13: Log multi-step result
                            QgsMessageLog.logMessage(
                                f"OGR apply_filter: MULTI-STEP returned {multi_result} for '{layer.name()}'",
                                "FilterMate", Qgis.Info if multi_result else Qgis.Warning  # DEBUG si succès
                            )
                            return multi_result  # True or False
                        # else: fall through to standard method
                        QgsMessageLog.logMessage(
                            f"OGR apply_filter: MULTI-STEP returned None, falling through to STANDARD for '{layer.name()}'",
                            "FilterMate", Qgis.Info  # DEBUG
                        )
                
                # FIX v2.8.13: Log standard path for debugging
                QgsMessageLog.logMessage(
                    f"OGR apply_filter: using STANDARD method for '{layer.name()}' (features={feature_count})",
                    "FilterMate", Qgis.Info  # DEBUG
                )
                
                # FIX v2.4.6: Use standard method for OGR layers
                # The large dataset optimization (using _fm_match_ temp field) causes
                # SQLite "unable to open database file" errors when:
                # - Multiple layers from the same GeoPackage are filtered simultaneously
                # - The database file is on a network drive or has access issues
                # - The database is opened read-only by another process
                # The standard method is reliable and performs well with spatial indexes.
                result = self._apply_filter_standard(
                    layer, source_layer, predicates, buffer_value,
                    old_subset, combine_operator
                )
                
                # FIX v2.8.13: Log result for debugging
                QgsMessageLog.logMessage(
                    f"OGR apply_filter: _apply_filter_standard returned {result} for '{layer.name()}'",
                    "FilterMate", Qgis.Info if result else Qgis.Warning  # DEBUG si succès, WARNING si échec
                )
                return result
                
            except Exception as e:
                self.log_error(f"Error applying OGR filter: {str(e)}")
                import traceback
                tb = traceback.format_exc()
                self.log_debug(f"Traceback: {tb}")
                # FIX v2.8.13: Log exception to QGIS MessagePanel for visibility
                QgsMessageLog.logMessage(
                    f"OGR apply_filter EXCEPTION for '{layer.name()}': {str(e)}\n"
                    f"Traceback: {tb[:500]}",
                    "FilterMate", Qgis.Critical
                )
                return False
    
    # Note: _get_buffer_endcap_style(), _get_buffer_segments(), _get_simplify_tolerance()
    # are inherited from GeometricFilterBackend (v2.8.6 refactoring)

    def _apply_simplify(self, source_layer, simplify_tolerance):
        """Apply geometry simplification to source layer.
        
        Uses QGIS native:simplifygeometries algorithm with Douglas-Peucker method.
        This reduces vertex count for complex geometries before buffer application.
        
        Args:
            source_layer: QgsVectorLayer to simplify
            simplify_tolerance: Tolerance value in layer units (meters for projected CRS)
            
        Returns:
            QgsVectorLayer: Simplified layer or original layer if simplification fails/skipped
        """
        if not source_layer or simplify_tolerance <= 0:
            return source_layer
        
        from qgis.core import QgsProcessingContext, QgsFeatureRequest, QgsProcessingFeedback
        
        try:
            context = QgsProcessingContext()
            context.setInvalidGeometryCheck(QgsFeatureRequest.GeometrySkipInvalid)
            # FIX v3.0.12: Use standard feedback to avoid cancellation issues during OGR fallback
            feedback = QgsProcessingFeedback()
            
            # Check cancellation before simplification
            if self._is_task_canceled():
                self.log_info("Filter cancelled before simplification")
                return source_layer
            
            self.log_info(f"📐 Applying geometry simplification (tolerance={simplify_tolerance}m)")
            
            # Use Douglas-Peucker algorithm (METHOD=0)
            simplify_result = processing.run("native:simplifygeometries", {
                'INPUT': source_layer,
                'METHOD': 0,  # Douglas-Peucker
                'TOLERANCE': float(simplify_tolerance),
                'OUTPUT': 'memory:'
            }, context=context, feedback=feedback)
            
            simplified_layer = simplify_result['OUTPUT']
            
            if simplified_layer and simplified_layer.isValid():
                original_vertices = sum(f.geometry().constGet().nCoordinates() 
                                       for f in source_layer.getFeatures() 
                                       if f.geometry() and not f.geometry().isNull())
                simplified_vertices = sum(f.geometry().constGet().nCoordinates() 
                                         for f in simplified_layer.getFeatures() 
                                         if f.geometry() and not f.geometry().isNull())
                
                reduction_pct = ((original_vertices - simplified_vertices) / original_vertices * 100) if original_vertices > 0 else 0
                self.log_info(f"  ✓ Simplified: {original_vertices:,} → {simplified_vertices:,} vertices ({reduction_pct:.1f}% reduction)")
                
                return simplified_layer
            else:
                self.log_warning("Simplification returned invalid layer, using original")
                return source_layer
                
        except Exception as e:
            self.log_warning(f"Geometry simplification failed: {e}, using original layer")
            return source_layer

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
        # FIX v2.6.13: Add QGIS MessagePanel logging for visibility
        from qgis.core import QgsMessageLog, Qgis
        
        if source_layer is None:
            self.log_error("Source layer is None - cannot apply buffer")
            QgsMessageLog.logMessage(
                "OGR _apply_buffer: source layer is None",
                "FilterMate", Qgis.Critical
            )
            return None
        
        if not isinstance(source_layer, QgsVectorLayer):
            self.log_error(f"Source layer is not a QgsVectorLayer: {type(source_layer).__name__}")
            QgsMessageLog.logMessage(
                f"OGR _apply_buffer: source layer is not a QgsVectorLayer: {type(source_layer).__name__}",
                "FilterMate", Qgis.Critical
            )
            return None
        
        if not source_layer.isValid():
            self.log_error(f"Source layer is not valid: {source_layer.name()}")
            QgsMessageLog.logMessage(
                f"OGR _apply_buffer: source layer '{source_layer.name()}' is not valid",
                "FilterMate", Qgis.Critical
            )
            return None
        
        # CRITICAL FIX v2.5.4: For memory layers, featureCount() can return 0 immediately after creation
        # even if features were added. We need to force a refresh/recount.
        # Try to get actual feature count by iterating (more reliable for memory layers)
        actual_feature_count = 0
        provider_type = source_layer.providerType()
        
        # FIX v3.0.11: DIAGNOSTIC - Log detailed feature counting info to QGIS MessagePanel
        QgsMessageLog.logMessage(
            f"OGR _apply_buffer: source layer '{source_layer.name()}' - "
            f"provider={provider_type}, featureCount()={source_layer.featureCount()}, "
            f"subsetString='{source_layer.subsetString()[:50] if source_layer.subsetString() else '(none)'}'",
            "FilterMate", Qgis.Info
        )
        
        if provider_type == 'memory':
            # For memory layers, force extent update and iterate to get real count
            source_layer.updateExtents()
            
            # DIAGNOSTIC: Log both featureCount() and actual iteration count
            reported_count = source_layer.featureCount()
            try:
                actual_feature_count = sum(1 for _ in source_layer.getFeatures())
            except Exception as e:
                self.log_warning(f"Failed to iterate features: {e}, using featureCount()")
                QgsMessageLog.logMessage(
                    f"OGR _apply_buffer: getFeatures() iteration FAILED: {e}",
                    "FilterMate", Qgis.Warning
                )
                actual_feature_count = reported_count
            
            if reported_count != actual_feature_count:
                self.log_warning(f"⚠️ Memory layer count mismatch: featureCount()={reported_count}, actual={actual_feature_count}")
                QgsMessageLog.logMessage(
                    f"OGR _apply_buffer: Memory layer count MISMATCH - featureCount()={reported_count}, actual={actual_feature_count}",
                    "FilterMate", Qgis.Warning
                )
        else:
            actual_feature_count = source_layer.featureCount()
        
        self.log_debug(f"Source layer '{source_layer.name()}': provider={provider_type}, features={actual_feature_count}")
        
        if actual_feature_count == 0:
            self.log_error(f"⚠️ Source layer has no features: {source_layer.name()}")
            self.log_error(f"  → This is the INTERSECT layer for spatial filtering")
            self.log_error(f"  → Common causes:")
            self.log_error(f"     1. No features selected in source layer")
            self.log_error(f"     2. Source layer subset string filters out all features")
            self.log_error(f"     3. Field-based filtering returned no matches")
            # FIX v2.6.13: Add QGIS MessagePanel logging for visibility
            from qgis.core import QgsMessageLog, Qgis
            QgsMessageLog.logMessage(
                f"OGR _apply_buffer: source layer '{source_layer.name()}' has 0 features - "
                f"cannot perform spatial filtering. Check source layer selection/filter.",
                "FilterMate", Qgis.Critical
            )
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
                # FIX v3.0.12: Use standard feedback for OGR fallback to avoid cancellation issues
                # The CancellableFeedback can cause processing to fail if parent task state is inconsistent
                from qgis.core import QgsProcessingContext, QgsFeatureRequest, QgsProcessingFeedback
                context = QgsProcessingContext()
                context.setInvalidGeometryCheck(QgsFeatureRequest.GeometrySkipInvalid)
                
                # Use standard feedback instead of cancellable for more reliable processing
                # The parent task cancellation is checked separately before each operation
                feedback = QgsProcessingFeedback()
                
                # v2.6.2: Check cancellation before buffer
                if self._is_task_canceled():
                    self.log_info("Filter cancelled before buffer processing")
                    return None
                
                # FIX v3.0.12: DIAGNOSTIC - Log detailed state before processing
                QgsMessageLog.logMessage(
                    f"OGR _apply_buffer: BEFORE processing - layer={source_layer.name()}, "
                    f"valid={source_layer.isValid()}, features={source_layer.featureCount()}, "
                    f"feedback_canceled={feedback.isCanceled()}",
                    "FilterMate", Qgis.Info
                )
                
                try:
                    # First run fixgeometries to repair any invalid geometries
                    fix_result = processing.run("native:fixgeometries", {
                        'INPUT': source_layer,
                        'OUTPUT': 'memory:'
                    }, context=context, feedback=feedback)
                    fixed_layer = fix_result['OUTPUT']
                    self.log_debug(f"Fixed geometries: {fixed_layer.featureCount()} features")
                    
                    # FIX v3.0.12: DIAGNOSTIC - Check feedback state after fixgeometries
                    if feedback.isCanceled():
                        QgsMessageLog.logMessage(
                            f"OGR _apply_buffer: fixgeometries completed but feedback is CANCELED",
                            "FilterMate", Qgis.Warning
                        )
                    
                    # v2.6.x: Apply geometry simplification before buffer if tolerance is set
                    simplify_tolerance = self._get_simplify_tolerance()
                    if simplify_tolerance > 0:
                        fixed_layer = self._apply_simplify(fixed_layer, simplify_tolerance)
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
                    # Note: QgsVectorLayer and QgsFeature are already imported at module level
                    
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
                
                # FIX v2.9.11: Ensure the layer reference is kept alive
                # The buffered_layer is a temporary memory layer that must persist
                # until it's used in _safe_select_by_location
                if not hasattr(self, '_temp_layers_keep_alive') or self._temp_layers_keep_alive is None:
                    self._temp_layers_keep_alive = []
                self._temp_layers_keep_alive.append(buffered_layer)
                
                self.log_debug("Buffer applied successfully")
                return buffered_layer
            except Exception as buffer_error:
                # FIX v3.0.12: Enhanced error logging to QGIS MessagePanel
                self.log_error(f"Buffer operation failed: {str(buffer_error)}")
                self.log_error(f"  - Buffer value: {buffer_value} (type: {type(buffer_value).__name__})")
                self.log_error(f"  - Source layer: {source_layer.name()}")
                self.log_error(f"  - CRS: {source_layer.crs().authid()} (Geographic: {source_layer.crs().isGeographic()})")
                
                # Log to QGIS MessagePanel for visibility
                QgsMessageLog.logMessage(
                    f"OGR _apply_buffer: EXCEPTION - {str(buffer_error)[:200]}",
                    "FilterMate", Qgis.Critical
                )
                
                # Check for common error causes
                if source_layer.crs().isGeographic() and abs(float(buffer_value)) > 1:
                    self.log_error(
                        f"ERROR: Geographic CRS detected with large buffer value!\n"
                        f"  A buffer of {buffer_value}° in a geographic CRS (lat/lon) is equivalent to\n"
                        f"  approximately {abs(float(buffer_value)) * 111}km at the equator.\n"
                        f"  → Solution: Reproject your layer to a projected CRS (e.g., EPSG:3857, EPSG:2154)"
                    )
                
                import traceback
                error_traceback = traceback.format_exc()
                self.log_debug(f"Buffer traceback: {error_traceback}")
                QgsMessageLog.logMessage(
                    f"OGR _apply_buffer: Traceback - {error_traceback[:500]}",
                    "FilterMate", Qgis.Warning
                )
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
        # NOTE: QgsVectorLayer, QgsFeature, QgsGeometry, QgsMemoryProviderUtils, QgsWkbTypes
        # are already imported at module level (lines 47-54)
        # Avoid local imports that shadow global names (Python 3.11+ issue)
        
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
        from qgis.core import QgsMessageLog, Qgis
        
        if layer is None:
            self.log_error(f"Pre-flight check: {param_name} layer is None")
            QgsMessageLog.logMessage(
                f"_preflight_layer_check: FAILED at step 0 (None check) for {param_name}",
                "FilterMate", Qgis.Critical
            )
            return False
        
        try:
            # These are the operations that checkParameterValues performs:
            
            # 1. Check layer validity
            if not layer.isValid():
                self.log_error(f"Pre-flight check: {param_name} layer.isValid() = False")
                QgsMessageLog.logMessage(
                    f"_preflight_layer_check: FAILED at step 1 (isValid) for {param_name} - layer is not valid",
                    "FilterMate", Qgis.Critical
                )
                return False
            
            # 2. Get layer source (used by Processing to identify the layer)
            try:
                source = layer.source()
                if not source:
                    self.log_warning(f"Pre-flight check: {param_name} layer has empty source (memory layer)")
            except Exception as source_error:
                self.log_error(f"Pre-flight check: {param_name} source() failed: {source_error}")
                QgsMessageLog.logMessage(
                    f"_preflight_layer_check: FAILED at step 2 (source) for {param_name} - {source_error}",
                    "FilterMate", Qgis.Critical
                )
                return False
            
            # 3. Access data provider
            try:
                provider = layer.dataProvider()
                if provider is None:
                    self.log_error(f"Pre-flight check: {param_name} layer has no data provider")
                    QgsMessageLog.logMessage(
                        f"_preflight_layer_check: FAILED at step 3 (dataProvider) for {param_name} - provider is None",
                        "FilterMate", Qgis.Critical
                    )
                    return False
            except Exception as provider_get_error:
                self.log_error(f"Pre-flight check: {param_name} dataProvider() failed: {provider_get_error}")
                QgsMessageLog.logMessage(
                    f"_preflight_layer_check: FAILED at step 3 (dataProvider) for {param_name} - {provider_get_error}",
                    "FilterMate", Qgis.Critical
                )
                return False
            
            # 4. Check provider can be accessed (this is where crashes often occur)
            try:
                uri = provider.dataSourceUri()
                caps = provider.capabilities()
            except Exception as provider_error:
                self.log_error(f"Pre-flight check: {param_name} provider access failed: {provider_error}")
                QgsMessageLog.logMessage(
                    f"_preflight_layer_check: FAILED at step 4 (provider access) for {param_name} - {provider_error}",
                    "FilterMate", Qgis.Critical
                )
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
                QgsMessageLog.logMessage(
                    f"_preflight_layer_check: FAILED at step 5 (extent) for {param_name} - {extent_error}",
                    "FilterMate", Qgis.Critical
                )
                return False
            
            # 6. Test that we can start feature iteration (but don't iterate all)
            try:
                request = layer.getFeatures()
                # Just test that we can get the iterator, don't consume it
                del request
            except Exception as iter_error:
                self.log_error(f"Pre-flight check: {param_name} cannot create feature iterator: {iter_error}")
                QgsMessageLog.logMessage(
                    f"_preflight_layer_check: FAILED at step 6 (getFeatures) for {param_name} - {iter_error}",
                    "FilterMate", Qgis.Critical
                )
                return False
            
            self.log_debug(f"✓ Pre-flight check passed for {param_name}: {layer.name()}")
            return True
            
        except (RuntimeError, OSError) as access_error:
            self.log_error(f"Pre-flight check: {param_name} layer access error: {access_error}")
            QgsMessageLog.logMessage(
                f"_preflight_layer_check: FAILED with RuntimeError/OSError for {param_name} - {access_error}",
                "FilterMate", Qgis.Critical
            )
            return False
        except Exception as unexpected:
            self.log_error(f"Pre-flight check: {param_name} unexpected error: {unexpected}")
            QgsMessageLog.logMessage(
                f"_preflight_layer_check: FAILED with unexpected exception for {param_name} - {unexpected}",
                "FilterMate", Qgis.Critical
            )
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
        # FIX v2.8.13: Enhanced diagnostic logging
        has_valid_geometry = False
        invalid_geom_count = 0
        try:
            for feature in intersect_layer.getFeatures():
                geom = feature.geometry()
                if validate_geometry(geom):
                    has_valid_geometry = True
                    self.log_debug(f"Found valid geometry in feature {feature.id()}")
                    break
                else:
                    invalid_geom_count += 1
                    # FIX v2.8.13: Log WHY the geometry is invalid
                    if geom is None:
                        self.log_debug(f"Feature {feature.id()}: geometry is None")
                    elif geom.isNull():
                        self.log_debug(f"Feature {feature.id()}: geometry is Null")
                    elif geom.isEmpty():
                        self.log_debug(f"Feature {feature.id()}: geometry is Empty")
                    else:
                        self.log_debug(f"Feature {feature.id()}: wkbType={geom.wkbType()}")
                    if invalid_geom_count >= 10:  # Check first 10 only for performance
                        break
        except (RuntimeError, OSError) as iter_error:
            self.log_error(f"Failed to iterate intersect layer features: {iter_error}")
            return False
        
        if not has_valid_geometry:
            self.log_error(f"Intersect layer has no valid geometries (checked {invalid_geom_count} features)")
            # FIX v2.8.13: Log to QGIS MessagePanel for visibility
            from qgis.core import QgsMessageLog, Qgis
            QgsMessageLog.logMessage(
                f"OGR _validate_intersect_layer: NO VALID GEOMETRIES in '{intersect_layer.name()}' "
                f"(checked {invalid_geom_count} features)",
                "FilterMate", Qgis.Critical
            )
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
        from qgis.core import QgsMessageLog, Qgis, QgsProject
        
        # FIX v2.9.43: Track safe_intersect layer for cleanup
        safe_intersect_to_cleanup = None
        
        try:
            # Validate both layers before processing
            QgsMessageLog.logMessage(
                f"_safe_select_by_location: input={input_layer.name() if input_layer else 'None'} ({input_layer.featureCount() if input_layer else 0}), "
                f"intersect={intersect_layer.name() if intersect_layer else 'None'} ({intersect_layer.featureCount() if intersect_layer else 0})",
                "FilterMate", Qgis.Info  # DEBUG
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
            
            # FIX v2.8.14: Log validation steps to QGIS MessageLog for visibility
            QgsMessageLog.logMessage(
                f"_safe_select_by_location: validating input layer '{input_layer.name() if input_layer else 'None'}'...",
                "FilterMate", Qgis.Info  # DEBUG
            )
            
            if not self._validate_input_layer(input_layer):
                self.log_error("Input layer validation failed - see details above")
                # FIX v2.8.13: Log to QGIS MessagePanel for visibility
                QgsMessageLog.logMessage(
                    f"OGR _safe_select_by_location: INPUT layer validation FAILED for '{input_layer.name() if input_layer else 'None'}'",
                    "FilterMate", Qgis.Critical
                )
                return False
            
            # FIX v2.8.14: Log validation steps to QGIS MessageLog for visibility
            QgsMessageLog.logMessage(
                f"_safe_select_by_location: input layer OK, validating intersect layer '{intersect_layer.name() if intersect_layer else 'None'}'...",
                "FilterMate", Qgis.Info  # DEBUG
            )
            
            if not self._validate_intersect_layer(intersect_layer):
                self.log_error("Intersect layer validation failed - see details above")
                # FIX v2.8.13: Log to QGIS MessagePanel for visibility
                QgsMessageLog.logMessage(
                    f"OGR _safe_select_by_location: INTERSECT layer validation FAILED for '{intersect_layer.name() if intersect_layer else 'None'}'",
                    "FilterMate", Qgis.Critical
                )
                return False
            
            # FIX v2.8.14: Log progress to QGIS MessageLog
            QgsMessageLog.logMessage(
                f"_safe_select_by_location: both layers validated, configuring processing context...",
                "FilterMate", Qgis.Info  # DEBUG
            )
            
            # Configure processing context to handle invalid geometries gracefully
            from qgis.core import QgsProcessingContext, QgsFeatureRequest
            context = QgsProcessingContext()
            context.setInvalidGeometryCheck(QgsFeatureRequest.GeometrySkipInvalid)
            
            # v2.6.2: Use cancellable feedback for interruptible processing
            # FIX v3.0.12: Use standard feedback to avoid cancellation issues during OGR fallback
            # The CancellableFeedback can cause processing to fail if parent task state is inconsistent
            from qgis.core import QgsProcessingFeedback
            feedback = QgsProcessingFeedback()
            
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
            
            # FIX v2.9.13: Keep references to temporary GEOS-safe layers to prevent garbage collection
            # The memory layers created by create_geos_safe_layer() are created FRESH for each target
            # layer and can be deleted by Python GC before processing completes.
            # 
            # STRATEGY (v2.9.24 UPDATE): 
            # - _temp_layers_keep_alive: ACCUMULATE across ALL target layers during filter operation
            #   Cleared ONLY when entire task completes (via cleanup_temp_layers())
            # - _source_layer_keep_alive: PERSISTENT across ALL target layers (never cleared mid-operation)
            #   to retain source_geom for the entire filter operation
            # 
            # CRITICAL: DO NOT clear _temp_layers_keep_alive between layers - causes GC of safe_intersect
            if not hasattr(self, '_temp_layers_keep_alive') or self._temp_layers_keep_alive is None:
                self._temp_layers_keep_alive = []
            # NOTE: _temp_layers_keep_alive is NO LONGER cleared between layers (v2.9.24 fix)
            # NOTE: _source_layer_keep_alive is initialized ONCE in apply_filter() and NEVER cleared
            
            # FIX v2.8.14: Log to QGIS MessageLog before create_geos_safe_layer
            QgsMessageLog.logMessage(
                f"_safe_select_by_location: creating GEOS-safe intersect layer for '{intersect_layer.name()}'...",
                "FilterMate", Qgis.Info  # DEBUG
            )
            
            # FIX v2.9.15: Add unique ID to layer name to prevent conflicts when creating multiple GEOS-safe layers
            # Each target layer creates a new safe_intersect, but they all have the same base name
            # This can cause issues after 7-8 iterations when QGIS memory layer registry gets confused
            import time
            unique_id = int(time.time() * 1000) % 1000000  # Last 6 digits of timestamp in ms
            
            try:
                safe_intersect = create_geos_safe_layer(intersect_layer, f"_safe_intersect_{unique_id}")
                # FIX v2.9.14: CRITICAL - Retain reference IMMEDIATELY to prevent GC before first access
                # The C++ object can be deleted between creation and first use if not retained immediately.
                # This layer is created fresh for each target layer and is stored in _temp_layers_keep_alive
                # (which is cleared between target layers). The source_geom is stored separately in
                # _source_layer_keep_alive (persistent across all target layers).
                if safe_intersect is not None:
                    # Add to retention list BEFORE any other operation (including .name() access)
                    self._temp_layers_keep_alive.append(safe_intersect)
                    # FIX v2.8.15: CRITICAL - Force full object materialization immediately after adding to keep-alive list
                    # Test ALL properties that will be accessed later to ensure C++ object is fully initialized
                    # This prevents race condition where GC intervenes between creation and first real use
                    try:
                        layer_name = safe_intersect.name()
                        _ = safe_intersect.isValid()  # Force validity check
                        _ = safe_intersect.featureCount()  # Force feature count
                        _ = safe_intersect.source()  # Force source access
                        provider = safe_intersect.dataProvider()  # Force provider access
                        if provider:
                            _ = provider.name()  # Force provider property access
                        self.log_debug(f"🔒 TEMP reference for GEOS-safe intersect: '{layer_name}' (fully materialized)")
                        # FIX v2.9.19: CRITICAL - Process Qt events and add delay to prevent GC race condition
                        # The C++ object can be deleted by Qt's GC between creation and processing.run()
                        # This happens intermittently after 5-7 target layer iterations.
                        # Process events BEFORE any further operations to ensure the layer is stable.
                        from qgis.PyQt.QtCore import QCoreApplication
                        QCoreApplication.processEvents()
                        time.sleep(0.005)  # 5ms delay - still imperceptible but more reliable
                        # Re-validate after event processing to catch late GC
                        _ = safe_intersect.isValid()
                        _ = safe_intersect.featureCount()
                        
                        # FIX v2.9.43: ULTIMATE PROTECTION - Add to QGIS project temporarily
                        # Even with all the above protections, Qt can still GC the layer after the delay
                        # but BEFORE processing.run(). Adding to project gives it a C++ reference in the
                        # QgsProject registry, which Qt respects and won't GC.
                        # We'll remove it after processing.run() completes.
                        QgsProject.instance().addMapLayer(safe_intersect, False)  # addToLegend=False
                        safe_intersect_to_cleanup = safe_intersect  # Track for cleanup
                        self.log_debug(f"🔒 Added '{layer_name}' to project registry for GC protection")
                    except RuntimeError as name_err:
                        # If even basic access fails after adding to list, the layer is already dead
                        QgsMessageLog.logMessage(
                            f"_safe_select_by_location: safe_intersect materialization FAILED immediately after creation: {name_err}",
                            "FilterMate", Qgis.Critical
                        )
                        self.log_error(f"GEOS-safe intersect layer wrapper destroyed immediately: {name_err}")
                        return False
                # NO NEED to retain intersect_layer here - it's the source_geom which is already
                # retained in _source_layer_keep_alive (persistent)
            except Exception as geos_err:
                QgsMessageLog.logMessage(
                    f"_safe_select_by_location: create_geos_safe_layer FAILED for intersect: {geos_err}",
                    "FilterMate", Qgis.Critical
                )
                return False
            
            # create_geos_safe_layer now returns the original layer as fallback, never None for valid input
            if safe_intersect is None:
                self.log_warning("create_geos_safe_layer returned None, using original layer")
                safe_intersect = intersect_layer
            
            if not safe_intersect.isValid() or safe_intersect.featureCount() == 0:
                self.log_error("No valid geometries in intersect layer")
                # FIX v2.8.13: Log to QGIS MessagePanel for visibility
                QgsMessageLog.logMessage(
                    f"OGR _safe_select_by_location: GEOS-safe intersect layer is invalid or empty "
                    f"(valid={safe_intersect.isValid() if safe_intersect else False}, "
                    f"features={safe_intersect.featureCount() if safe_intersect else 0})",
                    "FilterMate", Qgis.Critical
                )
                return False
            
            self.log_info(f"✓ Safe intersect layer: {safe_intersect.featureCount()} features")
            
            # FIX v2.8.14: Log to QGIS MessageLog
            QgsMessageLog.logMessage(
                f"_safe_select_by_location: GEOS-safe intersect layer OK ({safe_intersect.featureCount()} features)",
                "FilterMate", Qgis.Info  # DEBUG
            )
            
            # Also process input layer if not too large
            # FIX v2.9.14: DISABLED - GEOS-safe input layer causes false negatives in spatial selection
            # Keeping only GEOS-safe intersect layer which is essential for crash prevention
            # The input layer (target from project) is usually already valid and doesn't need filtering
            safe_input = input_layer
            use_safe_input = False
            # DISABLED: Creating GEOS-safe input layer
            # if input_layer.featureCount() <= 50000:  # Only process smaller layers for performance
            #     self.log_debug("🛡️ Creating GEOS-safe input layer...")
            #     ...
            
            self.log_info(f"🔍 Executing selectbylocation with GEOS-safe geometries")
            
            # STABILITY FIX v2.3.9.3: Pre-flight validation of layers before processing.run()
            # This catches issues that would cause checkParameterValues to crash at C++ level
            actual_input = input_layer if not use_safe_input else safe_input
            # FIX v2.9.14: CRITICAL - Validate C++ wrapper BEFORE any property access
            # The C++ object can be deleted even if we have a Python reference
            # This must be done BEFORE accessing .name() in log messages
            try:
                # Test if C++ objects are still valid by accessing their properties
                # This will raise RuntimeError if the C++ object has been deleted
                actual_input_name = actual_input.name()  # Force access to C++ object
                safe_intersect_name = safe_intersect.name()  # Force access to C++ object
                _ = actual_input.dataProvider().name()  # Test provider
                _ = safe_intersect.dataProvider().name()  # Test provider
            except RuntimeError as wrapper_error:
                self.log_error(f"C++ wrapper validation failed - object has been deleted: {wrapper_error}")
                QgsMessageLog.logMessage(
                    f"_safe_select_by_location: C++ WRAPPER VALIDATION FAILED - {wrapper_error}",
                    "FilterMate", Qgis.Critical
                )
                return False
            except AttributeError as attr_error:
                self.log_error(f"C++ wrapper attribute error: {attr_error}")
                QgsMessageLog.logMessage(
                    f"_safe_select_by_location: C++ WRAPPER ATTRIBUTE ERROR - {attr_error}",
                    "FilterMate", Qgis.Critical
                )
                return False
            
            # Now safe to use layer names in log messages (already validated above)
            # FIX v2.8.14: Log pre-flight checks to QGIS MessageLog
            QgsMessageLog.logMessage(
                f"_safe_select_by_location: running pre-flight check for INPUT layer '{actual_input_name}'...",
                "FilterMate", Qgis.Info  # DEBUG
            )
            
            if not self._preflight_layer_check(actual_input, "INPUT"):
                self.log_error("Pre-flight check failed for INPUT layer")
                QgsMessageLog.logMessage(
                    f"_safe_select_by_location: PRE-FLIGHT CHECK FAILED for INPUT layer '{actual_input_name}'",
                    "FilterMate", Qgis.Critical
                )
                return False
            
            # FIX v2.8.14: Log pre-flight checks to QGIS MessageLog
            QgsMessageLog.logMessage(
                f"_safe_select_by_location: running pre-flight check for INTERSECT layer '{safe_intersect_name}'...",
                "FilterMate", Qgis.Info  # DEBUG
            )
                
            if not self._preflight_layer_check(safe_intersect, "INTERSECT"):
                self.log_error("Pre-flight check failed for INTERSECT layer")
                QgsMessageLog.logMessage(
                    f"_safe_select_by_location: PRE-FLIGHT CHECK FAILED for INTERSECT layer '{safe_intersect_name}'",
                    "FilterMate", Qgis.Critical
                )
                return False
            
            # FIX v2.8.14: Log before executing selectbylocation
            QgsMessageLog.logMessage(
                f"_safe_select_by_location: executing processing.run('native:selectbylocation') for '{input_layer.name()}'...",
                "FilterMate", Qgis.Info  # DEBUG
            )
            
            # Execute with error handling - use safe layers
            # FIX v2.9.11: Wrap processing.run in try-except to catch C++ level errors
            # FIX v2.9.43: Use finally block to ensure safe_intersect is removed from project
            try:
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
            except RuntimeError as cpp_error:
                # C++ level error (access violation, memory error, etc.)
                self.log_error(f"C++ error in processing.run: {cpp_error}")
                QgsMessageLog.logMessage(
                    f"_safe_select_by_location: C++ ERROR in processing.run - {cpp_error}",
                    "FilterMate", Qgis.Critical
                )
                # Try to clear selection safely before returning
                try:
                    input_layer.removeSelection()
                except (RuntimeError, AttributeError):
                    pass
                return False
            except Exception as proc_error:
                # Other processing errors
                self.log_error(f"Processing error: {proc_error}")
                QgsMessageLog.logMessage(
                    f"_safe_select_by_location: PROCESSING ERROR - {proc_error}",
                    "FilterMate", Qgis.Critical
                )
                try:
                    input_layer.removeSelection()
                except (RuntimeError, AttributeError):
                    pass
                return False
                
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
                "FilterMate", Qgis.Info  # DEBUG
            )
            
            # DIAGNOSTIC v2.4.17: Log intersect layer geometry extent
            if intersect_layer and intersect_layer.isValid():
                extent = intersect_layer.extent()
                QgsMessageLog.logMessage(
                    f"  Intersect layer '{intersect_layer.name()}' extent: ({extent.xMinimum():.1f},{extent.yMinimum():.1f})-({extent.xMaximum():.1f},{extent.yMaximum():.1f})",
                    "FilterMate", Qgis.Info  # DEBUG
                )
                # Log first geometry WKT preview
                for feat in intersect_layer.getFeatures():
                    geom = feat.geometry()
                    if geom and not geom.isEmpty():
                        wkt_preview = geom.asWkt()[:200] if geom.asWkt() else "EMPTY"
                        QgsMessageLog.logMessage(
                            f"  First intersect geom: {wkt_preview}...",
                            "FilterMate", Qgis.Info  # DEBUG
                        )
                    break
            
            self.log_info(f"✓ Selection complete: {selected_count} features selected")
            return True
            
        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            self.log_error(f"selectbylocation failed: {str(e)}")
            self.log_debug(f"Traceback: {tb_str}")
            
            # FIX v2.8.14: Enhanced error logging to QGIS MessagePanel for visibility
            QgsMessageLog.logMessage(
                f"selectbylocation FAILED on {input_layer.name() if input_layer else 'Unknown'}: {str(e)}",
                "FilterMate", Qgis.Critical
            )
            # Log full traceback to MessageLog for debugging
            QgsMessageLog.logMessage(
                f"selectbylocation traceback:\n{tb_str}",
                "FilterMate", Qgis.Warning
            )
            
            # Clear any partial selection to avoid inconsistent state
            try:
                input_layer.removeSelection()
            except (RuntimeError, AttributeError):
                pass  # Layer may be invalid or destroyed
            
            return False
        
        finally:
            # FIX v2.9.43: CRITICAL - Remove safe_intersect from project registry
            # This cleanup MUST happen whether the operation succeeded or failed
            # to prevent accumulating temporary layers in the project
            if safe_intersect_to_cleanup is not None:
                try:
                    # Check if layer still exists in project before trying to remove
                    if QgsProject.instance().mapLayer(safe_intersect_to_cleanup.id()):
                        QgsProject.instance().removeMapLayer(safe_intersect_to_cleanup.id())
                        self.log_debug(f"🧹 Removed safe_intersect from project registry")
                except (RuntimeError, AttributeError) as cleanup_err:
                    # Layer may have been destroyed or removed already - not critical
                    self.log_debug(f"Safe intersect cleanup note: {cleanup_err}")
                except Exception as cleanup_err:
                    # Unexpected error - log but don't fail the operation
                    self.log_debug(f"Safe intersect cleanup error: {cleanup_err}")
    
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
        # FIX v2.8.13: Log entry to this method for debugging
        from qgis.core import QgsMessageLog, Qgis
        QgsMessageLog.logMessage(
            f"OGR _apply_filter_standard: ENTERING for '{layer.name() if layer else 'None'}' "
            f"with source '{source_layer.name() if source_layer else 'None'}' "
            f"(predicates={predicates}, buffer={buffer_value})",
            "FilterMate", Qgis.Info  # DEBUG
        )
        
        # Initialize existing_subset early for exception handling
        existing_subset = None
        
        # STABILITY FIX v2.3.9: Validate layers before any operations
        # FIX v2.6.13: Add QGIS MessagePanel logging for visibility
        
        if layer is None or not layer.isValid():
            self.log_error("Target layer is None or invalid - cannot proceed with standard filtering")
            if layer is None:
                self.log_error("  → layer is None")
                QgsMessageLog.logMessage(
                    "OGR _apply_filter_standard: target layer is None",
                    "FilterMate", Qgis.Critical
                )
            else:
                self.log_error(f"  → layer.isValid() = {layer.isValid()}")
                QgsMessageLog.logMessage(
                    f"OGR _apply_filter_standard: target layer '{layer.name()}' is invalid",
                    "FilterMate", Qgis.Critical
                )
            return False
        
        if source_layer is None or not source_layer.isValid():
            self.log_error("Source layer is None or invalid - cannot proceed with standard filtering")
            if source_layer is None:
                self.log_error("  → source_layer is None")
                QgsMessageLog.logMessage(
                    f"OGR _apply_filter_standard: source layer is None for target '{layer.name()}'",
                    "FilterMate", Qgis.Critical
                )
            else:
                self.log_error(f"  → source_layer.isValid() = {source_layer.isValid()}")
                self.log_error(f"  → source_layer.featureCount() = {source_layer.featureCount()}")
                QgsMessageLog.logMessage(
                    f"OGR _apply_filter_standard: source layer '{source_layer.name()}' is invalid (valid={source_layer.isValid()}, features={source_layer.featureCount()})",
                    "FilterMate", Qgis.Critical
                )
            return False
        
        # FIX v2.4.18: Save and temporarily clear existing subset string
        # This prevents GDAL "feature id out of available range" errors when
        # selectbylocation tries to access features that are filtered out by the existing subset.
        # The existing subset is saved and will be combined with the new filter later if needed.
        # 
        # FIX v2.9.40: CRITICAL - In multi-step filtering, old_subset already contains the FID filter
        # from the previous step, so we must ALWAYS use existing_subset (from layer.subsetString())
        # instead of old_subset. This ensures that we filter within the already-filtered features.
        existing_subset = layer.subsetString()
        if existing_subset:
            self.log_info(f"🔄 Temporarily clearing existing subset on {layer.name()} for selectbylocation")
            self.log_debug(f"  → Existing subset: '{existing_subset[:100]}...'")
            safe_set_subset_string(layer, "")
            # v2.9.40: ALWAYS use existing_subset for combination (even if old_subset is not None)
            # This is critical for multi-step filtering where we need to filter within filtered features
            old_subset = existing_subset
            self.log_debug(f"  → old_subset updated to existing_subset for multi-step filtering compatibility")
        
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
        # FIX v3.0.10: Check if buffer is already applied from previous step
        if hasattr(self, 'task_params') and self.task_params:
            infos = self.task_params.get('infos', {})
            buffer_state = infos.get('buffer_state', {})
            is_pre_buffered = buffer_state.get('is_pre_buffered', False)

            if is_pre_buffered and buffer_value != 0:
                # Buffer already applied - use source layer directly
                self.log_info(f"  ✓ Multi-step filter: Using pre-buffered source ({buffer_value}m)")
                intersect_layer = source_layer
            else:
                # Apply buffer fresh
                intersect_layer = self._apply_buffer(source_layer, buffer_value)
                # Store buffered layer for potential reuse in next step
                if intersect_layer and buffer_value != 0:
                    self._buffered_source_layer = intersect_layer
                    if 'buffer_state' in infos:
                        infos['buffer_state']['is_pre_buffered'] = True
        else:
            # No task_params - apply buffer normally
            intersect_layer = self._apply_buffer(source_layer, buffer_value)

        if intersect_layer is None:
            # FIX v2.4.18: Restore original subset if buffer failed
            # FIX v2.6.13: Add QGIS MessagePanel logging for visibility
            QgsMessageLog.logMessage(
                f"OGR _apply_filter_standard: _apply_buffer returned None for '{layer.name()}' - "
                f"source layer '{source_layer.name()}' may have no features or invalid geometries",
                "FilterMate", Qgis.Critical
            )
            if existing_subset:
                self.log_warning(f"Restoring original subset after buffer failure")
                safe_set_subset_string(layer, existing_subset)
            return False
        
        # FIX v2.9.11: Keep reference to buffered layer to prevent premature garbage collection
        # The intersect_layer may be a temporary memory layer that can be GC'd before processing.run
        if not hasattr(self, '_temp_layers_keep_alive') or self._temp_layers_keep_alive is None:
            self._temp_layers_keep_alive = []
        self._temp_layers_keep_alive.append(intersect_layer)
        
        # Map predicates
        predicate_codes = self._map_predicates(predicates)
        
        # STABILITY FIX v2.3.9: Use safe wrapper for selectbylocation
        # FIX v2.8.13: Add detailed logging before selectbylocation for debugging
        QgsMessageLog.logMessage(
            f"OGR selectbylocation: target={layer.name()} ({layer.featureCount()} features), "
            f"intersect={intersect_layer.name()} ({intersect_layer.featureCount()} features), "
            f"predicates={predicate_codes}",
            "FilterMate", Qgis.Info  # DEBUG
        )
        
        if not self._safe_select_by_location(layer, intersect_layer, predicate_codes):
            self.log_error("Safe select by location failed - cannot proceed")
            # FIX v2.8.13: Add QGIS MessageLog for visibility
            QgsMessageLog.logMessage(
                f"OGR _apply_filter_standard: selectbylocation FAILED for '{layer.name()}' - "
                f"intersect layer '{intersect_layer.name()}' ({intersect_layer.featureCount()} features)",
                "FilterMate", Qgis.Critical
            )
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
                # We'll collect both QGIS FIDs (for cache) and PK values (for filter expression)
                matching_fids = []  # QGIS feature IDs for cache
                
                if pk_field == "$id":
                    # Use QGIS feature IDs
                    # STABILITY FIX v2.3.9: Wrap in try-except to catch access violations
                    try:
                        selected_ids = [f.id() for f in layer.selectedFeatures()]
                        matching_fids = selected_ids  # FIDs are the same
                    except (RuntimeError, AttributeError) as e:
                        self.log_error(f"Failed to get selected features: {e}")
                        return False
                    
                    # v2.8.11: MULTI-STEP FILTERING - Intersect with previous cache if exists
                    # v2.9.30: FIX - Also pass buffer_val and predicates_list to avoid wrong intersection
                    step_number = 1
                    source_wkt = ""
                    predicates_list = []
                    buffer_val = 0.0
                    if hasattr(self, 'task_params') and self.task_params:
                        infos = self.task_params.get('infos', {})
                        source_wkt = infos.get('source_geom_wkt', '')
                        # v2.8.12: FIX - geometric_predicates can be list or dict
                        geom_preds = self.task_params.get('filtering', {}).get('geometric_predicates', [])
                        if isinstance(geom_preds, dict):
                            predicates_list = list(geom_preds.keys())
                        elif isinstance(geom_preds, list):
                            predicates_list = geom_preds
                        else:
                            predicates_list = []
                        # FIX v3.0.12: Clean buffer value from float precision errors
                        buffer_val = clean_buffer_value(self.task_params.get('filtering', {}).get('buffer_value', 0.0))
                    
                    if SPATIALITE_CACHE_AVAILABLE and intersect_filter_fids and old_subset:
                        # v2.9.43: CRITICAL - Cache multi-step only supports AND operator
                        cache_operator = None
                        if hasattr(self, 'task_params') and self.task_params:
                            cache_operator = self.task_params.get('_current_combine_operator')
                        
                        if cache_operator in ('OR', 'NOT AND'):
                            self.log_warning(
                                f"⚠️ OGR Multi-step with {cache_operator} - "
                                f"cache intersection not supported, performing full filter"
                            )
                            # Skip cache intersection for OR/NOT AND
                        else:
                            # AND or None → use cache intersection
                            previous_fids = get_previous_filter_fids(layer, source_wkt, buffer_val, predicates_list)
                            if previous_fids is not None:
                                original_count = len(matching_fids)
                                matching_fids_set, step_number = intersect_filter_fids(
                                    layer, set(matching_fids), source_wkt, buffer_val, predicates_list
                                )
                                matching_fids = list(matching_fids_set)
                                selected_ids = matching_fids  # Update for expression building
                                self.log_info(f"  🔄 Multi-step intersection: {original_count} ∩ {len(previous_fids)} = {len(matching_fids)}")
                                from qgis.core import QgsMessageLog, Qgis
                                QgsMessageLog.logMessage(
                                    f"  → OGR Multi-step step {step_number}: {original_count} ∩ {len(previous_fids)} = {len(matching_fids)} FIDs",
                                    "FilterMate", Qgis.Info  # DEBUG
                                )
                    
                    # v2.8.11: Store result in cache for future multi-step filtering
                    if SPATIALITE_CACHE_AVAILABLE and store_filter_fids and matching_fids:
                        try:
                            
                            cache_key = store_filter_fids(
                                layer=layer,
                                fids=matching_fids,
                                source_geom_wkt=source_wkt,
                                predicates=predicates_list,
                                buffer_value=buffer_val,
                                step_number=step_number if 'step_number' in dir() else 1
                            )
                            self.log_info(f"  💾 OGR Cached {len(matching_fids)} FIDs (key={cache_key[:8] if cache_key else 'N/A'}, step={step_number if 'step_number' in dir() else 1})")
                        except Exception as cache_err:
                            self.log_debug(f"Cache storage failed (non-fatal): {cache_err}")
                    
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
                    
                    # Extract values from the primary key field AND collect QGIS FIDs for cache
                    # STABILITY FIX v2.3.9: Wrap in try-except to catch access violations
                    try:
                        selected_values = []
                        matching_fids = []  # QGIS feature IDs for cache
                        for f in layer.selectedFeatures():
                            selected_values.append(f.attribute(pk_field))
                            matching_fids.append(f.id())  # Collect QGIS FID for cache
                    except (RuntimeError, AttributeError) as e:
                        self.log_error(f"Failed to get selected features for PK extraction: {e}")
                        return False
                    
                    # v2.8.11: MULTI-STEP FILTERING - Intersect with previous cache if exists
                    # v2.9.30: FIX - Also pass buffer_val and predicates_list to avoid wrong intersection
                    step_number = 1
                    source_wkt = ""
                    predicates_list = []
                    buffer_val = 0.0
                    if hasattr(self, 'task_params') and self.task_params:
                        infos = self.task_params.get('infos', {})
                        source_wkt = infos.get('source_geom_wkt', '')
                        # v2.8.12: FIX - geometric_predicates can be list or dict
                        geom_preds = self.task_params.get('filtering', {}).get('geometric_predicates', [])
                        if isinstance(geom_preds, dict):
                            predicates_list = list(geom_preds.keys())
                        elif isinstance(geom_preds, list):
                            predicates_list = geom_preds
                        else:
                            predicates_list = []
                        # FIX v3.0.12: Clean buffer value from float precision errors
                        buffer_val = clean_buffer_value(self.task_params.get('filtering', {}).get('buffer_value', 0.0))
                    
                    if SPATIALITE_CACHE_AVAILABLE and intersect_filter_fids and old_subset:
                        # v2.9.43: CRITICAL - Cache multi-step only supports AND operator
                        cache_operator = None
                        if hasattr(self, 'task_params') and self.task_params:
                            cache_operator = self.task_params.get('_current_combine_operator')
                        
                        if cache_operator in ('OR', 'NOT AND'):
                            self.log_warning(
                                f"⚠️ OGR Multi-step with {cache_operator} - "
                                f"cache intersection not supported, performing full filter"
                            )
                            # Skip cache intersection for OR/NOT AND
                        else:
                            # AND or None → use cache intersection
                            previous_fids = get_previous_filter_fids(layer, source_wkt, buffer_val, predicates_list)
                            if previous_fids is not None:
                                original_count = len(matching_fids)
                                matching_fids_set, step_number = intersect_filter_fids(
                                    layer, set(matching_fids), source_wkt, buffer_val, predicates_list
                                )
                                matching_fids = list(matching_fids_set)
                                
                                # We need to re-map FIDs to PK values after intersection
                                # Get the PK values for the intersected FIDs
                                if len(matching_fids) < original_count:
                                    # Need to filter selected_values to match intersected FIDs
                                    fid_to_value = dict(zip([f.id() for f in layer.selectedFeatures()], selected_values))
                                    selected_values = [fid_to_value[fid] for fid in matching_fids if fid in fid_to_value]
                            
                                self.log_info(f"  🔄 Multi-step intersection: {original_count} ∩ {len(previous_fids)} = {len(matching_fids)}")
                                from qgis.core import QgsMessageLog, Qgis
                                QgsMessageLog.logMessage(
                                    f"  → OGR Multi-step step {step_number}: {original_count} ∩ {len(previous_fids)} = {len(matching_fids)} FIDs",
                                    "FilterMate", Qgis.Info  # DEBUG
                                )
                    
                    # v2.8.11: Store result in cache for future multi-step filtering
                    if SPATIALITE_CACHE_AVAILABLE and store_filter_fids and matching_fids:
                        try:
                            
                            cache_key = store_filter_fids(
                                layer=layer,
                                fids=matching_fids,
                                source_geom_wkt=source_wkt,
                                predicates=predicates_list,
                                buffer_value=buffer_val,
                                step_number=step_number
                            )
                            self.log_info(f"  💾 OGR Cached {len(matching_fids)} FIDs (key={cache_key[:8] if cache_key else 'N/A'}, step={step_number})")
                        except Exception as cache_err:
                            self.log_debug(f"Cache storage failed (non-fatal): {cache_err}")
                    
                    # Quote string values, keep numeric values unquoted
                    if field_type == QMetaType.Type.QString:
                        id_list = ','.join(f"'{str(val).replace(chr(39), chr(39)+chr(39))}'" for val in selected_values)
                    else:
                        id_list = ','.join(str(val) for val in selected_values)
                    
                    escaped_pk = escape_ogr_identifier(pk_field)
                    new_subset_expression = f'{escaped_pk} IN ({id_list})'
                
                self.log_debug(f"Generated subset expression using key '{pk_field}'")
                
                # Combine with old subset if needed (but not if it contains invalid patterns)
                # v3.0.7/v2.8.6: Use shared methods from base_backend for harmonization
                if old_subset and not self._should_clear_old_subset(old_subset):
                    is_fid_only = self._is_fid_only_filter(old_subset)
                    
                    if is_fid_only:
                        # FID filter from previous step - ALWAYS combine (ignore combine_operator=None)
                        self.log_info(f"✅ Combining FID filter from step 1 with new filter (MULTI-STEP)")
                        self.log_info(f"  → FID filter: {old_subset[:80]}...")
                        final_expression = f"({old_subset}) AND ({new_subset_expression})"
                    elif combine_operator is None:
                        # v3.0.7: combine_operator=None → use default AND
                        self.log_info(f"🔗 combine_operator=None → using default AND (preserving filter)")
                        final_expression = f"({old_subset}) AND ({new_subset_expression})"
                    else:
                        if not combine_operator:
                            combine_operator = 'AND'
                        self.log_info(f"🔗 Préservation du filtre existant avec {combine_operator}")
                        final_expression = f"({old_subset}) {combine_operator} ({new_subset_expression})"
                else:
                    final_expression = new_subset_expression
                
                # Apply subset filter
                # THREAD SAFETY FIX: Use queue callback if available (called from background thread)
                queue_callback = self.task_params.get('_subset_queue_callback')
                
                # DIAGNOSTIC
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"Applying subset on {layer.name()}: queue_callback={'Yes' if queue_callback else 'No'}, expr_len={len(final_expression)}",
                    "FilterMate", Qgis.Info  # DEBUG
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
                    
                    # FIX v3.0.7: Show correct message based on queue_callback
                    # When queue_callback is used, subset is QUEUED, not applied yet
                    # So featureCount() still returns the pre-filter count
                    if queue_callback:
                        QgsMessageLog.logMessage(
                            f"✓ Subset QUEUED for {layer.name()}: {selected_count} features selected (will be applied on main thread)",
                            "FilterMate", Qgis.Info
                        )
                    else:
                        QgsMessageLog.logMessage(
                            f"✓ Subset applied on {layer.name()}: {final_count} features",
                            "FilterMate", Qgis.Info
                        )
                    
                    self.log_info(f"✓ {layer.name()}: {selected_count if queue_callback else final_count} features{' (pending)' if queue_callback else ''}")
                    
                    # Clear selection safely
                    try:
                        layer.removeSelection()
                    except (RuntimeError, AttributeError):
                        pass
                    
                    # FIX v2.8.15: Force immediate layer refresh for OGR backend
                    # Without this, the canvas may not update correctly after filtering
                    # even though subset string is correctly applied
                    if not queue_callback:
                        try:
                            layer.triggerRepaint()
                            logger.debug(f"  → Triggered immediate repaint for {layer.name()}")
                        except Exception as repaint_err:
                            logger.debug(f"  → Could not trigger repaint: {repaint_err}")
                    
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
                    # FIX v2.8.15: Force immediate layer refresh for OGR backend
                    try:
                        layer.triggerRepaint()
                        logger.debug(f"  → Triggered immediate repaint for {layer.name()} (empty filter)")
                    except Exception as repaint_err:
                        logger.debug(f"  → Could not trigger repaint: {repaint_err}")
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
            # FIX v3.0.10: Check if buffer is already applied from previous step
            if hasattr(self, 'task_params') and self.task_params:
                infos = self.task_params.get('infos', {})
                buffer_state = infos.get('buffer_state', {})
                is_pre_buffered = buffer_state.get('is_pre_buffered', False)

                if is_pre_buffered and buffer_value != 0:
                    # Buffer already applied - use source layer directly
                    self.log_info(f"  ✓ Multi-step filter: Using pre-buffered source ({buffer_value}m)")
                    intersect_layer = source_layer
                else:
                    # Apply buffer fresh
                    intersect_layer = self._apply_buffer(source_layer, buffer_value)
                    # Store buffered layer for potential reuse in next step
                    if intersect_layer and buffer_value != 0:
                        self._buffered_source_layer = intersect_layer
                        if 'buffer_state' in infos:
                            infos['buffer_state']['is_pre_buffered'] = True
            else:
                # No task_params - apply buffer normally
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
                # v3.0.7/v2.8.6: Use shared methods from base_backend for harmonization
                if old_subset and not self._should_clear_old_subset(old_subset):
                    is_fid_only = self._is_fid_only_filter(old_subset)
                    
                    if is_fid_only:
                        # FID filter from previous step - ALWAYS combine
                        self.log_info(f"✅ Combining FID filter from step 1 with new filter (MULTI-STEP)")
                        final_expression = f"({old_subset}) AND ({new_subset_expression})"
                    elif combine_operator is None:
                        # v3.0.7: Use default AND instead of REPLACE
                        self.log_info(f"🔗 combine_operator=None → using default AND (preserving filter)")
                        final_expression = f"({old_subset}) AND ({new_subset_expression})"
                    else:
                        if not combine_operator:
                            combine_operator = 'AND'
                        self.log_info(f"🔗 Préservation du filtre existant avec {combine_operator}")
                        final_expression = f"({old_subset}) {combine_operator} ({new_subset_expression})"
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
                        # FIX v2.8.15: Force immediate layer refresh for OGR backend
                        try:
                            layer.triggerRepaint()
                            logger.debug(f"  → Triggered immediate repaint for {layer.name()} (large dataset)")
                        except Exception as repaint_err:
                            logger.debug(f"  → Could not trigger repaint: {repaint_err}")
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
                    # FIX v2.8.15: Force immediate layer refresh for OGR backend
                    try:
                        layer.triggerRepaint()
                        logger.debug(f"  → Triggered immediate repaint for {layer.name()} (large dataset, empty filter)")
                    except Exception as repaint_err:
                        logger.debug(f"  → Could not trigger repaint: {repaint_err}")
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
            
            # FIX v3.0.10: Check if buffer is already applied from previous step
            if hasattr(self, 'task_params') and self.task_params:
                infos = self.task_params.get('infos', {})
                buffer_state = infos.get('buffer_state', {})
                is_pre_buffered = buffer_state.get('is_pre_buffered', False)

                if is_pre_buffered and buffer_value != 0:
                    # Buffer already applied - use source layer directly
                    self.log_info(f"  ✓ Multi-step filter: Using pre-buffered source ({buffer_value}m)")
                    intersect_layer = source_layer
                else:
                    # Apply buffer fresh
                    intersect_layer = self._apply_buffer(source_layer, buffer_value)
                    # Store buffered layer for potential reuse in next step
                    if intersect_layer and buffer_value != 0:
                        self._buffered_source_layer = intersect_layer
                        if 'buffer_state' in infos:
                            infos['buffer_state']['is_pre_buffered'] = True
            else:
                # No task_params - apply buffer normally
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
                    except (RuntimeError, AttributeError):
                        pass  # Layer may be invalid or destroyed
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
                # v3.0.7/v2.8.6: Use shared methods from base_backend for harmonization
                if old_subset and not self._should_clear_old_subset(old_subset):
                    is_fid_only = self._is_fid_only_filter(old_subset)
                    
                    if is_fid_only:
                        # FID filter from previous step - ALWAYS combine
                        self.log_info(f"✅ Combining FID filter from step 1 with new filter (MULTI-STEP)")
                        final_expression = f"({old_subset}) AND ({new_subset_expression})"
                    elif combine_operator is None:
                        # v3.0.7: Use default AND instead of REPLACE
                        self.log_info(f"🔗 combine_operator=None → using default AND (preserving filter)")
                        final_expression = f"({old_subset}) AND ({new_subset_expression})"
                    else:
                        if not combine_operator:
                            combine_operator = 'AND'
                        self.log_info(f"🔗 Préservation du filtre existant avec {combine_operator}")
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

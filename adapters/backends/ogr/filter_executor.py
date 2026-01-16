"""
OGR Filter Executor

EPIC-1 Phase E4: Backend-specific filter execution for OGR (Shapefile, GeoPackage, etc.).

This module contains OGR-specific methods extracted from filter_task.py:
- build_ogr_filter_from_selection() - Build filter from selection (57 lines)
- execute_ogr_spatial_selection() - Execute spatial selection (159 lines) - DEFERRED
- prepare_ogr_source_geom() - Prepare source geometry for OGR (382 lines) - DEFERRED

Note: execute_ogr_spatial_selection and prepare_ogr_source_geom are deferred because
they have heavy dependencies on self.* instance variables and QGIS processing context.
They need significant refactoring before extraction.

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase E4)
"""

import logging
import re
import threading

logger = logging.getLogger('FilterMate.Adapters.Backends.OGR.FilterExecutor')

# =============================================================================
# TEMPORARY LAYER REGISTRY
# Tracks temporary layers created for garbage collection prevention.
# These layers are added to QgsProject with addToLegend=False and must be
# explicitly removed when filtering is complete.
# =============================================================================

_temp_layer_registry_lock = threading.Lock()
_temp_layer_registry = []  # List of layer IDs to clean up


def register_temp_layer(layer_id: str) -> None:
    """
    Register a temporary layer for later cleanup.
    
    Args:
        layer_id: The QgsMapLayer.id() of the temp layer
    """
    with _temp_layer_registry_lock:
        if layer_id not in _temp_layer_registry:
            _temp_layer_registry.append(layer_id)
            logger.debug(f"Registered temp layer for cleanup: {layer_id}")


def cleanup_ogr_temp_layers() -> int:
    """
    Clean up all registered temporary OGR layers.
    
    This removes layers from the QgsProject that were added with
    addToLegend=False for garbage collection prevention.
    
    Returns:
        int: Number of layers removed
    """
    from qgis.core import QgsProject
    
    with _temp_layer_registry_lock:
        if not _temp_layer_registry:
            return 0
        
        layer_ids = _temp_layer_registry.copy()
        _temp_layer_registry.clear()
    
    removed_count = 0
    project = QgsProject.instance()
    
    for layer_id in layer_ids:
        try:
            if project.mapLayer(layer_id) is not None:
                project.removeMapLayer(layer_id)
                removed_count += 1
                logger.debug(f"Cleaned up temp layer: {layer_id}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp layer {layer_id}: {e}")
    
    if removed_count > 0:
        logger.info(f"Cleaned up {removed_count} temporary OGR layers")
    
    return removed_count


def build_ogr_filter_from_selection(
    layer,
    layer_props: dict,
    selected_fids: list = None,
    distant_geom_expression: str = None
) -> tuple:
    """
    Build filter expression from selected features for OGR layers.
    
    EPIC-1 Phase E4-S4: Extracted from filter_task.py line 6949 (57 lines)
    
    Args:
        layer: Layer with selected features
        layer_props: Layer properties dict with keys:
            - primary_key_name: Primary key field name
            - primary_key_is_numeric: Whether PK is numeric
            - layer_schema: Schema name
            - layer_name: Table/layer name
            - layer_geometry_field: Geometry field name
        selected_fids: List of selected feature IDs (optional, reads from layer if None)
        distant_geom_expression: Geometry field expression
        
    Returns:
        tuple: (filter_expression, full_sql_expression) or (None, None) if no selection
    """
    param_distant_primary_key_name = layer_props["primary_key_name"]
    param_distant_primary_key_is_numeric = layer_props.get(
        "primary_key_is_numeric", True
    )
    param_distant_schema = layer_props.get("layer_schema", "")
    param_distant_table = layer_props["layer_name"]
    param_distant_geometry_field = layer_props.get(
        "layer_geometry_field", "geometry"
    )
    
    # Get selected feature IDs if not provided
    if selected_fids is None:
        try:
            from qgis.core import QgsFeatureRequest
            selected_fids = list(layer.selectedFeatureIds())
        except Exception:
            selected_fids = []
    
    if not selected_fids:
        return None, None
    
    # Extract feature IDs from selection
    # CRITICAL FIX: Handle ctid (PostgreSQL internal identifier)
    # ctid is not accessible via feature[field_name], use feature.id() instead
    features_ids = []
    try:
        from qgis.core import QgsFeatureRequest
        request = QgsFeatureRequest().setFilterFids(selected_fids)
        for feature in layer.getFeatures(request):
            if param_distant_primary_key_name == 'ctid':
                features_ids.append(str(feature.id()))
            else:
                pk_value = feature[param_distant_primary_key_name]
                features_ids.append(str(pk_value))
    except Exception as e:
        logger.warning(f"Error extracting feature IDs: {e}")
        # Fallback to fids directly
        features_ids = [str(fid) for fid in selected_fids]
    
    if len(features_ids) == 0:
        return None, None
    
    # Build IN clause based on key type
    if param_distant_primary_key_is_numeric:
        param_expression = '"{pk}" IN ({ids})'.format(
            pk=param_distant_primary_key_name,
            ids=", ".join(features_ids)
        )
    else:
        # Quote string values
        param_expression = '"{pk}" IN ({ids})'.format(
            pk=param_distant_primary_key_name,
            ids="'" + "', '".join(features_ids) + "'"
        )
    
    # Build full SELECT expression for manage_layer_subset_strings
    geom_expr = distant_geom_expression or f'"{param_distant_geometry_field}"'
    
    if param_distant_schema:
        full_expression = (
            f'SELECT "{param_distant_table}"."{param_distant_primary_key_name}", '
            f'{geom_expr} FROM "{param_distant_schema}"."{param_distant_table}" '
            f'WHERE {param_expression}'
        )
    else:
        # OGR doesn't use schemas
        full_expression = (
            f'SELECT "{param_distant_primary_key_name}", '
            f'{geom_expr} FROM "{param_distant_table}" '
            f'WHERE {param_expression}'
        )
    
    return param_expression, full_expression


def format_ogr_pk_values(
    values: list,
    is_numeric: bool = True
) -> str:
    """
    Format primary key values for OGR IN clause.
    
    EPIC-1 Phase E4-S4: OGR equivalent of PostgreSQL format_pk_values_for_sql
    
    Args:
        values: List of primary key values
        is_numeric: Whether PK is numeric
        
    Returns:
        str: Comma-separated values formatted for SQL IN clause
    """
    if not values:
        return ''
    
    if is_numeric:
        return ', '.join(str(v) for v in values)
    else:
        # Quote string values and escape internal quotes
        formatted = []
        for v in values:
            str_val = str(v).replace("'", "''")
            formatted.append(f"'{str_val}'")
        return ', '.join(formatted)


def normalize_column_names_for_ogr(
    expression: str,
    field_names: list
) -> str:
    """
    Normalize column names in expression for OGR layers.
    
    EPIC-1 Phase E4-S4: OGR equivalent of PostgreSQL function
    
    OGR/Shapefile field names are case-insensitive but often stored
    in uppercase. This ensures proper matching.
    
    Args:
        expression: SQL expression string
        field_names: List of actual field names from the layer
        
    Returns:
        str: Expression with corrected column names
    """
    if not expression or not field_names:
        return expression
    
    result_expression = expression
    
    # Build case-insensitive lookup map: uppercase → actual name
    field_lookup = {name.upper(): name for name in field_names}
    
    # Find all quoted column names in expression
    quoted_cols = re.findall(r'"([^"]+)"', result_expression)
    
    for col_name in quoted_cols:
        # Skip if column exists with exact case
        if col_name in field_names:
            continue
        
        # Check for case-insensitive match
        col_upper = col_name.upper()
        if col_upper in field_lookup:
            correct_name = field_lookup[col_upper]
            result_expression = result_expression.replace(
                f'"{col_name}"',
                f'"{correct_name}"'
            )
            logger.debug(f"OGR column case fix: \"{col_name}\" → \"{correct_name}\"")
    
    return result_expression


def build_ogr_simple_filter(
    primary_key_name: str,
    feature_ids: list,
    is_numeric: bool = True
) -> str:
    """
    Build simple OGR filter for primary key IN clause.
    
    EPIC-1 Phase E4-S4: Utility for OGR subset strings
    
    Args:
        primary_key_name: Primary key field name
        feature_ids: List of feature IDs to include
        is_numeric: Whether PK is numeric
        
    Returns:
        str: OGR filter expression
    """
    if not feature_ids:
        return ""
    
    formatted_ids = format_ogr_pk_values(feature_ids, is_numeric)
    return f'"{primary_key_name}" IN ({formatted_ids})'


def apply_ogr_subset(
    layer,
    subset_string: str,
    queue_subset_func=None
) -> bool:
    """
    Apply subset string to OGR layer with thread safety.
    
    EPIC-1 Phase E4-S4: Thread-safe OGR subset application
    
    Args:
        layer: QGIS vector layer
        subset_string: SQL subset string
        queue_subset_func: Function to queue subset for main thread
        
    Returns:
        bool: True if successful
    """
    if queue_subset_func:
        # Thread-safe: queue for main thread application
        queue_subset_func(layer, subset_string)
        return True
    else:
        # Direct application (only safe from main thread)
        try:
            return layer.setSubsetString(subset_string)
        except Exception as e:
            logger.error(f"Failed to apply OGR subset: {e}")
            return False


def combine_ogr_filters(
    existing_filter: str,
    new_filter: str,
    combine_operator: str = "AND"
) -> str:
    """
    Combine two OGR filters with a logical operator.
    
    EPIC-1 Phase E4-S4: Utility for combining OGR filters
    
    Args:
        existing_filter: Existing filter expression
        new_filter: New filter to combine
        combine_operator: "AND", "OR", or "NOT"
        
    Returns:
        str: Combined filter expression
    """
    if not existing_filter:
        return new_filter
    if not new_filter:
        return existing_filter
    
    if combine_operator.upper() == "NOT":
        return f"({existing_filter}) AND NOT ({new_filter})"
    else:
        return f"({existing_filter}) {combine_operator.upper()} ({new_filter})"


# =============================================================================
# EPIC-1 Phase E4-S7: OGR Source Geometry Preparation
# =============================================================================

from dataclasses import dataclass, field
from typing import Optional, List, Any, Callable


@dataclass
class OGRSourceContext:
    """
    Context object for OGR source geometry preparation.
    
    EPIC-1 Phase E4-S7: Encapsulates all parameters needed for prepare_ogr_source_geom()
    to enable extraction from filter_task.py with minimal coupling.
    
    This replaces the many self.* references with a clean data structure.
    """
    # Source layer reference
    source_layer: Any = None  # QgsVectorLayer
    
    # Task parameters
    task_parameters: dict = field(default_factory=dict)
    
    # Field expression info: tuple (is_field_expr, field_name) or None
    is_field_expression: Optional[tuple] = None
    
    # Filter expression (from execute_source_layer_filtering)
    expression: Optional[str] = None
    
    # New subset string
    param_source_new_subset: Optional[str] = None
    
    # Reprojection settings
    has_to_reproject_source_layer: bool = False
    source_layer_crs_authid: Optional[str] = None
    
    # Centroid optimization
    param_use_centroids_source_layer: bool = False
    
    # Spatialite fallback mode (for buffer handling)
    spatialite_fallback_mode: bool = False
    
    # Buffer parameter (None = no buffer, float/QgsProperty = buffer distance)
    buffer_distance: Any = None
    
    # Helper method callbacks (dependency injection)
    copy_filtered_layer_to_memory: Optional[Callable] = None
    copy_selected_features_to_memory: Optional[Callable] = None
    create_memory_layer_from_features: Optional[Callable] = None
    reproject_layer: Optional[Callable] = None
    convert_layer_to_centroids: Optional[Callable] = None
    get_buffer_distance_parameter: Optional[Callable] = None


def validate_task_features(task_features: list, layer: Any = None) -> tuple:
    """
    Validate QgsFeature objects from task parameters.
    
    EPIC-1 Phase E4-S7: Extracted validation logic from prepare_ogr_source_geom().
    Handles thread-safety issues where QgsFeature objects become invalid.
    
    Args:
        task_features: List of QgsFeature objects or feature-like objects
        layer: Source layer for FID recovery fallback
        
    Returns:
        tuple: (valid_features: list, invalid_count: int, recovered_via_fids: bool)
    """
    valid_features = []
    invalid_count = 0
    recovered_via_fids = False
    
    for f in task_features:
        if f is None or f == "":
            continue
        try:
            if hasattr(f, 'hasGeometry') and hasattr(f, 'geometry'):
                if f.hasGeometry():
                    geom = f.geometry()
                    if geom is not None and not geom.isEmpty():
                        valid_features.append(f)
                    else:
                        invalid_count += 1
                        logger.debug(f"  Skipping feature with empty geometry")
                else:
                    invalid_count += 1
                    logger.debug(f"  Skipping feature without geometry")
            elif f:
                # Non-QgsFeature truthy value (e.g., feature ID)
                valid_features.append(f)
        except (RuntimeError, AttributeError) as e:
            invalid_count += 1
            logger.warning(f"  ⚠️ Feature access error (thread-safety issue?): {e}")
    
    return valid_features, invalid_count, recovered_via_fids


def recover_features_from_fids(
    layer: Any, 
    feature_fids: list
) -> list:
    """
    Recover features using FIDs when QgsFeature objects are invalid.
    
    EPIC-1 Phase E4-S7: FID recovery logic for thread-safety issues.
    
    Args:
        layer: Source layer to fetch features from
        feature_fids: List of feature IDs
        
    Returns:
        list: Recovered features or empty list
    """
    if not feature_fids or not layer:
        return []
    
    try:
        from qgis.core import QgsFeatureRequest
        request = QgsFeatureRequest().setFilterFids(feature_fids)
        recovered_features = list(layer.getFeatures(request))
        if recovered_features:
            logger.info(f"  ✓ Recovered {len(recovered_features)} features using FIDs")
        return recovered_features
    except Exception as e:
        logger.error(f"  ❌ FID recovery failed: {e}")
        return []


def determine_source_mode(
    context: OGRSourceContext
) -> tuple:
    """
    Determine which mode to use for OGR source geometry preparation.
    
    EPIC-1 Phase E4-S7: Mode detection logic extracted for clarity.
    
    Args:
        context: OGRSourceContext with all parameters
        
    Returns:
        tuple: (mode: str, features_or_none)
        Modes: "TASK_PARAMS", "SUBSET", "SELECTION", "FIELD_BASED", "EXPRESSION_FALLBACK", "DIRECT"
    """
    layer = context.source_layer
    if not layer:
        return "INVALID", None
    
    has_subset = bool(layer.subsetString())
    has_selection = layer.selectedFeatureCount() > 0
    
    # Check field-based mode
    is_field_based = (
        context.is_field_expression is not None and
        isinstance(context.is_field_expression, tuple) and
        len(context.is_field_expression) >= 2 and
        context.is_field_expression[0] is True
    )
    
    # Check task features
    task_features_raw = context.task_parameters.get("task", {}).get("features", [])
    valid_features, invalid_count, _ = validate_task_features(task_features_raw, layer)
    
    # FID recovery if all features invalid
    if len(valid_features) == 0 and len(task_features_raw) > 0 and invalid_count > 0:
        feature_fids = context.task_parameters.get("task", {}).get("feature_fids", [])
        if not feature_fids:
            feature_fids = context.task_parameters.get("feature_fids", [])
        valid_features = recover_features_from_fids(layer, feature_fids)
    
    # Determine mode
    if valid_features and len(valid_features) > 0:
        return "TASK_PARAMS", valid_features
    elif has_subset or has_selection:
        if has_selection and not has_subset:
            return "SELECTION", None
        return "SUBSET", None
    elif is_field_based:
        return "FIELD_BASED", None
    elif context.expression and context.expression.strip():
        return "EXPRESSION_FALLBACK", context.expression
    elif context.param_source_new_subset and context.param_source_new_subset.strip():
        return "EXPRESSION_FALLBACK", context.param_source_new_subset
    else:
        return "DIRECT", None


def validate_ogr_result_layer(layer: Any) -> tuple:
    """
    Validate the final OGR source layer before storing.
    
    EPIC-1 Phase E4-S7: Result validation logic extracted.
    
    Args:
        layer: Processed layer to validate
        
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    if layer is None:
        return False, "Final layer is None"
    
    if not layer.isValid():
        return False, "Final layer is not valid"
    
    feature_count = layer.featureCount()
    if feature_count is None or feature_count == 0:
        return False, "Final layer has no features"
    
    # Check for at least one valid geometry
    has_valid_geom = False
    invalid_reason = "unknown"
    
    try:
        from ....core.geometry.geometry_safety import validate_geometry
    except ImportError:
        # Fallback validation
        def validate_geometry(geom):
            return geom is not None and not geom.isNull() and not geom.isEmpty()
    
    for feature in layer.getFeatures():
        geom = feature.geometry()
        if validate_geometry(geom):
            has_valid_geom = True
            break
        else:
            if geom is None:
                invalid_reason = "geometry is None"
            elif geom.isNull():
                invalid_reason = "geometry is Null"
            elif geom.isEmpty():
                invalid_reason = "geometry is Empty"
            else:
                wkb_type = geom.wkbType()
                invalid_reason = f"wkbType={wkb_type} (Unknown or NoGeometry)"
    
    if not has_valid_geom:
        return False, f"No valid geometries (reason: {invalid_reason})"
    
    return True, None


def prepare_ogr_source_geom(
    context: OGRSourceContext
) -> Any:
    """
    Prepare OGR source geometry with optional reprojection and buffering.
    
    EPIC-1 Phase E4-S7: Extracted from filter_task.py (382 lines → callable function)
    
    Uses OGRSourceContext to decouple from FilterEngineTask instance.
    Helper methods are injected via context callbacks.
    
    Process:
    1. Determine source mode (task_params, subset, selection, field-based, direct)
    2. Copy layer to memory if needed
    3. Reproject if needed
    4. Apply centroid optimization if enabled
    5. Validate result
    
    Args:
        context: OGRSourceContext with all required parameters and callbacks
        
    Returns:
        QgsVectorLayer or None: Prepared source geometry layer
    """
    from qgis.core import QgsMessageLog, Qgis, QgsProject, QgsExpressionContext
    try:
        from qgis.core import QgsProperty
    except ImportError:
        QgsProperty = None
    
    layer = context.source_layer
    
    if not layer:
        logger.error("prepare_ogr_source_geom: source_layer is None")
        return None
    
    # Step 0: Determine mode and prepare layer
    mode, mode_data = determine_source_mode(context)
    
    logger.info(f"=== prepare_ogr_source_geom ({mode} MODE) ===")
    logger.info(f"  Source layer: {layer.name()}")
    logger.info(f"  Feature count: {layer.featureCount()}")
    
    if mode == "INVALID":
        logger.error("  Mode is INVALID, returning None")
        return None
    
    elif mode == "TASK_PARAMS":
        valid_features = mode_data
        logger.info(f"  Using {len(valid_features)} features from task_parameters")
        
        if context.create_memory_layer_from_features:
            layer = context.create_memory_layer_from_features(
                valid_features, layer.crs(), "source_from_task"
            )
            if layer:
                logger.info(f"  ✓ Memory layer created with {layer.featureCount()} features")
            else:
                logger.error("  ✗ Failed to create memory layer")
                layer = context.source_layer
    
    elif mode == "SELECTION":
        logger.info(f"  Copying selected features to memory")
        if context.copy_selected_features_to_memory:
            layer = context.copy_selected_features_to_memory(layer, "source_selection")
    
    elif mode == "SUBSET":
        logger.info(f"  Copying filtered layer to memory")
        if context.copy_filtered_layer_to_memory:
            layer = context.copy_filtered_layer_to_memory(layer, "source_filtered")
    
    elif mode == "FIELD_BASED":
        logger.info(f"  Field-based mode: using all filtered features")
        if context.copy_filtered_layer_to_memory:
            layer = context.copy_filtered_layer_to_memory(layer, "source_field_based")
    
    elif mode == "EXPRESSION_FALLBACK":
        filter_to_use = mode_data
        logger.info(f"  Expression fallback: '{filter_to_use[:80]}...'")
        
        try:
            from qgis.core import QgsFeatureRequest, QgsExpression
            expr = QgsExpression(filter_to_use)
            if expr.hasParserError():
                logger.warning(f"  Expression parse error: {expr.parserErrorString()}")
            else:
                request = QgsFeatureRequest(expr)
                filtered_features = list(layer.getFeatures(request))
                
                if filtered_features and context.create_memory_layer_from_features:
                    layer = context.create_memory_layer_from_features(
                        filtered_features, layer.crs(), "source_expr_filtered"
                    )
                    if layer:
                        logger.info(f"  ✓ Filtered to {layer.featureCount()} features")
        except Exception as e:
            logger.error(f"  Expression filtering failed: {e}")
    
    elif mode == "DIRECT":
        logger.info(f"  Direct mode: using source layer as-is")
        QgsMessageLog.logMessage(
            f"OGR DIRECT MODE: Using {layer.featureCount()} features",
            "FilterMate", Qgis.Warning
        )
    
    # Step 1: Handle buffer CRS check
    buffer_distance = context.buffer_distance
    if context.get_buffer_distance_parameter:
        buffer_distance = context.get_buffer_distance_parameter()
    
    if buffer_distance is not None and layer:
        crs = layer.crs()
        is_geographic = crs.isGeographic()
        
        eval_distance = buffer_distance
        if QgsProperty and isinstance(buffer_distance, QgsProperty):
            features = list(layer.getFeatures())
            if features:
                ctx = QgsExpressionContext()
                ctx.setFeature(features[0])
                eval_distance = buffer_distance.value(ctx, 0)
        
        if is_geographic and eval_distance and float(eval_distance) > 1:
            logger.warning(
                f"⚠️ Geographic CRS ({crs.authid()}) with buffer {eval_distance}. "
                f"Auto-reprojecting to EPSG:3857."
            )
            context.has_to_reproject_source_layer = True
            context.source_layer_crs_authid = 'EPSG:3857'
    
    # Step 2: Reproject if needed
    if context.has_to_reproject_source_layer and context.reproject_layer:
        layer = context.reproject_layer(layer, context.source_layer_crs_authid)
    
    # Step 3: Validate result
    is_valid, error_msg = validate_ogr_result_layer(layer)
    if not is_valid:
        logger.error(f"prepare_ogr_source_geom: {error_msg}")
        QgsMessageLog.logMessage(
            f"OGR source preparation FAILED: {error_msg}",
            "FilterMate", Qgis.Critical
        )
        return None
    
    # Step 4: Centroid optimization
    if context.param_use_centroids_source_layer and context.convert_layer_to_centroids:
        logger.info("  Applying centroid optimization")
        centroid_layer = context.convert_layer_to_centroids(layer)
        if centroid_layer and centroid_layer.isValid() and centroid_layer.featureCount() > 0:
            layer = centroid_layer
            logger.info(f"  ✓ Converted to centroids: {layer.featureCount()} points")
    
    # Step 5: Prevent garbage collection for memory layers
    # FIX v4.1.1: Register layer for cleanup after filtering completes
    if layer and layer.isValid() and layer.providerType() == 'memory':
        logger.debug("  Adding memory layer to project (prevent GC)")
        QgsProject.instance().addMapLayer(layer, addToLegend=False)
        register_temp_layer(layer.id())  # Register for cleanup
    
    return layer


# =============================================================================
# EPIC-1 Phase E4-S7b: OGR Spatial Selection Execution
# =============================================================================

@dataclass
class OGRSpatialSelectionContext:
    """
    Context object for OGR spatial selection execution.
    
    EPIC-1 Phase E4-S7b: Encapsulates parameters for _execute_ogr_spatial_selection()
    """
    # Source geometry layer (prepared by prepare_ogr_source_geom)
    ogr_source_geom: Any = None
    
    # Predicates dict: {predicate_enum: True, ...}
    current_predicates: dict = field(default_factory=dict)
    
    # Combine operator settings
    has_combine_operator: bool = False
    param_other_layers_combine_operator: str = "AND"
    
    # Callback for spatial index verification
    verify_and_create_spatial_index: Optional[Callable] = None


def execute_ogr_spatial_selection(
    layer: Any,
    current_layer: Any,
    param_old_subset: str,
    context: OGRSpatialSelectionContext
) -> None:
    """
    Execute spatial selection using QGIS processing for OGR/non-PostgreSQL layers.
    
    EPIC-1 Phase E4-S7b: Extracted from filter_task.py _execute_ogr_spatial_selection()
    
    STABILITY FIX v2.3.9: Added comprehensive validation before calling selectbylocation
    to prevent access violations from invalid geometries.
    
    Args:
        layer: Original layer
        current_layer: Potentially reprojected working layer
        param_old_subset: Existing subset string
        context: OGRSpatialSelectionContext with source geom and callbacks
        
    Returns:
        None (modifies current_layer selection)
        
    Raises:
        Exception: If source geometry is invalid or unavailable
    """
    from qgis.core import (
        QgsVectorLayer, QgsWkbTypes, QgsProcessingContext, 
        QgsProcessingFeedback, QgsFeatureRequest
    )
    from qgis import processing
    
    # Import geometry validation from geometry_safety module
    try:
        from ....core.geometry.geometry_safety import validate_geometry, create_geos_safe_layer
    except ImportError:
        def validate_geometry(geom):
            return geom is not None and not geom.isNull() and not geom.isEmpty()
        create_geos_safe_layer = None
    
    # Import safe subset setter
    try:
        from ....infrastructure.database.sql_utils import safe_set_subset_string
    except ImportError:
        def safe_set_subset_string(lyr, subset):
            return lyr.setSubsetString(subset)
    
    ogr_source_geom = context.ogr_source_geom
    
    # Validate source geometry
    if not ogr_source_geom:
        logger.error("ogr_source_geom is None - cannot execute spatial selection")
        raise Exception("Source geometry layer is not available for spatial selection")
    
    if not isinstance(ogr_source_geom, QgsVectorLayer):
        logger.error(f"ogr_source_geom is not a QgsVectorLayer: {type(ogr_source_geom)}")
        raise Exception(f"Source geometry must be a QgsVectorLayer, got {type(ogr_source_geom)}")
    
    if not ogr_source_geom.isValid():
        logger.error(f"ogr_source_geom is not valid: {ogr_source_geom.name()}")
        raise Exception("Source geometry layer is not valid")
    
    feature_count = ogr_source_geom.featureCount()
    if feature_count is None or feature_count == 0:
        logger.warning("ogr_source_geom has no features - spatial selection will return no results")
        return
    
    # Validate at least one geometry
    has_valid_geom = False
    for feature in ogr_source_geom.getFeatures():
        geom = feature.geometry()
        if validate_geometry(geom):
            has_valid_geom = True
            break
    
    if not has_valid_geom:
        logger.error("ogr_source_geom has no valid geometries")
        raise Exception("Source geometry layer has no valid geometries")
    
    logger.info(f"Using ogr_source_geom: {ogr_source_geom.name()}, "
               f"features={feature_count}, "
               f"geomType={QgsWkbTypes.displayString(ogr_source_geom.wkbType())}")
    
    # Configure processing context
    proc_context = QgsProcessingContext()
    proc_context.setInvalidGeometryCheck(QgsFeatureRequest.GeometrySkipInvalid)
    feedback = QgsProcessingFeedback()
    
    # Create GEOS-safe source layer
    logger.info("🛡️ Creating GEOS-safe source layer...")
    if create_geos_safe_layer:
        safe_source_geom = create_geos_safe_layer(ogr_source_geom, "_safe_source")
    else:
        safe_source_geom = ogr_source_geom
    
    if safe_source_geom is None:
        logger.warning("create_geos_safe_layer returned None, using original")
        safe_source_geom = ogr_source_geom
    
    if not safe_source_geom.isValid() or safe_source_geom.featureCount() == 0:
        logger.error("No valid source geometries available")
        raise Exception("Source geometry layer has no valid geometries")
    
    logger.info(f"✓ Safe source layer: {safe_source_geom.featureCount()} features")
    
    # Process target layer for smaller datasets
    safe_current_layer = current_layer
    use_safe_current = False
    target_count = current_layer.featureCount()
    if target_count and target_count <= 50000 and create_geos_safe_layer:
        logger.debug("🛡️ Creating GEOS-safe target layer...")
        temp_safe = create_geos_safe_layer(current_layer, "_safe_target")
        if temp_safe and temp_safe.isValid() and temp_safe.featureCount() > 0:
            safe_current_layer = temp_safe
            use_safe_current = True
            logger.info(f"✓ Safe target layer: {safe_current_layer.featureCount()} features")
    
    # FIX 2026-01-15: Extract numeric QGIS predicate codes from current_predicates
    # current_predicates peut contenir:
    #   - Des noms SQL comme clés: {'ST_Intersects': 'ST_Intersects'}
    #   - Des codes numériques comme clés: {0: 'ST_Intersects'}
    # Pour processing.run("qgis:selectbylocation"), on a besoin des codes numériques
    
    predicate_list = []
    for key in context.current_predicates.keys():
        if isinstance(key, int):
            # C'est déjà un code numérique QGIS
            predicate_list.append(key)
        elif isinstance(key, str) and key.isdigit():
            # C'est un string numérique
            predicate_list.append(int(key))
    
    # Si aucun code numérique trouvé, default à intersects (0)
    if not predicate_list:
        logger.warning(f"No numeric QGIS predicate codes found in current_predicates: {context.current_predicates}")
        logger.warning("Defaulting to 'intersects' (code 0)")
        predicate_list = [0]
    
    # DIAGNOSTIC LOGS 2026-01-15: Trace OGR spatial selection execution
    logger.info("=" * 70)
    logger.info(f"🚀 execute_ogr_spatial_selection STARTING")
    logger.info(f"   Layer: {current_layer.name() if hasattr(current_layer, 'name') else 'unknown'}")
    logger.info(f"   Source geom: {ogr_source_geom.name() if hasattr(ogr_source_geom, 'name') else 'unknown'}")
    logger.info(f"   Source features: {ogr_source_geom.featureCount() if hasattr(ogr_source_geom, 'featureCount') else 'unknown'}")
    logger.info(f"   Predicate list (numeric): {predicate_list}")
    logger.info(f"   Predicate names: {list(context.current_predicates.keys())}")
    logger.info(f"   Has combine operator: {context.has_combine_operator}")
    logger.info(f"   Combine operator: {context.param_other_layers_combine_operator}")
    logger.info(f"   Old subset: {param_old_subset[:100] if param_old_subset else 'None'}...")
    logger.info("=" * 70)
    
    def map_selection_to_original():
        """Map selection back to original layer if we used safe layer."""
        if use_safe_current and safe_current_layer is not current_layer:
            selected_fids = list(safe_current_layer.selectedFeatureIds())
            if selected_fids:
                current_layer.selectByIds(selected_fids)
                logger.debug(f"Mapped {len(selected_fids)} features to original layer")
    
    work_layer = safe_current_layer if use_safe_current else current_layer
    verify_index = context.verify_and_create_spatial_index
    
    # Execute selection based on combine operator
    if context.has_combine_operator:
        work_layer.selectAll()
        
        op = context.param_other_layers_combine_operator
        
        if op == 'OR':
            if verify_index:
                verify_index(work_layer)
            safe_set_subset_string(work_layer, param_old_subset)
            work_layer.selectAll()
            safe_set_subset_string(work_layer, '')
            method = 1
        elif op == 'AND':
            if verify_index:
                verify_index(work_layer)
            method = 2
        elif op == 'NOT AND':
            if verify_index:
                verify_index(work_layer)
            method = 3
        else:
            if verify_index:
                verify_index(work_layer)
            method = 0
        
        alg_params = {
            'INPUT': work_layer,
            'INTERSECT': safe_source_geom,
            'METHOD': method,
            'PREDICATE': predicate_list
        }
        processing.run("qgis:selectbylocation", alg_params, context=proc_context, feedback=feedback)
        map_selection_to_original()
    else:
        if verify_index:
            verify_index(work_layer)
        alg_params = {
            'INPUT': work_layer,
            'INTERSECT': safe_source_geom,
            'METHOD': 0,
            'PREDICATE': predicate_list
        }
        processing.run("qgis:selectbylocation", alg_params, context=proc_context, feedback=feedback)
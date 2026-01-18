"""
Spatialite Filter Executor

EPIC-1 Phase E4: Backend-specific filter execution for Spatialite.

This module contains Spatialite-specific methods extracted from filter_task.py:
- prepare_spatialite_source_geom() - Prepare source geometry (629 lines - EXTRACTED!)
- qgis_expression_to_spatialite() - Convert QGIS expression to Spatialite SQL
- _build_spatialite_query() - Build complete Spatialite query
- _apply_spatialite_subset() - Apply subset to Spatialite layer
- _manage_spatialite_subset() - Manage Spatialite subset strings

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase E4)
Updated: EPIC-1 Phase E4-S8 - Extracted prepare_spatialite_source_geom()
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, List, Any, Callable, Dict, Tuple

# EPIC-1 E4-S9: Import centralized HistoryRepository
from ...repositories.history_repository import HistoryRepository

logger = logging.getLogger('FilterMate.Adapters.Backends.Spatialite.FilterExecutor')


# =============================================================================
# EPIC-1 Phase E4-S8: Spatialite Source Geometry Preparation
# =============================================================================

@dataclass
class SpatialiteSourceContext:
    """
    Context object for Spatialite source geometry preparation.
    
    EPIC-1 Phase E4-S8: Encapsulates all parameters needed for prepare_spatialite_source_geom()
    to enable extraction from filter_task.py with minimal coupling.
    
    This replaces the many self.* references with a clean data structure.
    """
    # Source layer reference
    source_layer: Any = None  # QgsVectorLayer
    
    # Task parameters dict
    task_parameters: Dict = field(default_factory=dict)
    
    # Field expression info: tuple (is_field_expr, field_name) or None
    is_field_expression: Optional[Tuple] = None
    
    # Expression for filtering
    expression: Optional[str] = None
    
    # New subset string
    param_source_new_subset: Optional[str] = None
    
    # Buffer value (None = no buffer, float = buffer distance in meters)
    param_buffer_value: Optional[float] = None
    
    # Reprojection settings
    has_to_reproject_source_layer: bool = False
    source_layer_crs_authid: Optional[str] = None
    source_crs: Any = None  # QgsCoordinateReferenceSystem
    
    # Centroid optimization
    param_use_centroids_source_layer: bool = False
    
    # QGIS Project reference (for transforms)
    PROJECT: Any = None
    
    # Geometry cache reference (for caching computed geometries)
    geom_cache: Any = None
    
    # Helper method callbacks (dependency injection)
    geometry_to_wkt: Optional[Callable] = None  # _geometry_to_wkt
    simplify_geometry_adaptive: Optional[Callable] = None  # _simplify_geometry_adaptive  
    get_optimization_thresholds: Optional[Callable] = None  # _get_optimization_thresholds


@dataclass
class SpatialiteSourceResult:
    """
    Result from prepare_spatialite_source_geom().
    
    EPIC-1 Phase E4-S8: Clean return type instead of modifying self.spatialite_source_geom.
    """
    wkt: Optional[str] = None
    success: bool = False
    error_message: Optional[str] = None
    feature_count: int = 0
    geometry_type: Optional[str] = None
    from_cache: bool = False
    buffer_state: Dict = field(default_factory=dict)


class SourceMode:
    """Source mode constants for feature acquisition."""
    TASK_PARAMS = "TASK_PARAMS"
    SUBSET = "SUBSET"
    SELECTION = "SELECTION"
    FIELD_BASED = "FIELD_BASED"
    FALLBACK = "FALLBACK"


def determine_spatialite_source_mode(context: SpatialiteSourceContext) -> Tuple[str, Dict]:
    """
    Determine the source mode for feature acquisition.
    
    EPIC-1 Phase E4-S8: Extracted from prepare_spatialite_source_geom() mode detection logic.
    
    Priority order:
    1. TASK_PARAMS - task_features from task_parameters (most reliable, thread-safe)
    2. SUBSET - getFeatures() with subset string
    3. SELECTION - selectedFeatures()
    4. FIELD_BASED - all features with field expression
    5. FALLBACK - all features (should be rare)
    
    Args:
        context: SpatialiteSourceContext with layer and parameters
        
    Returns:
        tuple: (mode: str, metadata: dict)
    """
    source_layer = context.source_layer
    task_parameters = context.task_parameters
    is_field_expression = context.is_field_expression
    
    has_subset = bool(source_layer.subsetString())
    has_selection = source_layer.selectedFeatureCount() > 0
    
    # Check if we're in field-based mode
    is_field_based_mode = (
        is_field_expression is not None and
        isinstance(is_field_expression, tuple) and
        len(is_field_expression) >= 2 and
        is_field_expression[0] is True
    )
    
    # Check task_features
    task_features = task_parameters.get("task", {}).get("features", [])
    has_task_features = task_features and len(task_features) > 0
    
    logger.info(f"[Spatialite] === determine_spatialite_source_mode DEBUG ===")
    logger.info(f"[Spatialite]   has_task_features: {has_task_features} ({len(task_features) if task_features else 0} features)")
    logger.info(f"[Spatialite]   has_subset: {has_subset}")
    logger.info(f"[Spatialite]   has_selection: {has_selection}")
    logger.info(f"[Spatialite]   is_field_based_mode: {is_field_based_mode}")
    
    metadata = {
        "has_task_features": has_task_features,
        "has_subset": has_subset,
        "has_selection": has_selection,
        "is_field_based_mode": is_field_based_mode,
        "task_features": task_features,
        "feature_fids": task_parameters.get("task", {}).get("feature_fids", []),
    }
    
    if has_task_features and not is_field_based_mode:
        return SourceMode.TASK_PARAMS, metadata
    elif has_subset and not has_task_features:
        return SourceMode.SUBSET, metadata
    elif has_selection:
        return SourceMode.SELECTION, metadata
    elif is_field_based_mode:
        return SourceMode.FIELD_BASED, metadata
    else:
        return SourceMode.FALLBACK, metadata


def validate_spatialite_features(task_features: List, layer: Any = None) -> Tuple[List, int, int]:
    """
    Validate QgsFeature objects from task parameters.
    
    EPIC-1 Phase E4-S8: Extracted validation logic.
    Handles thread-safety issues where QgsFeature objects become invalid.
    
    Args:
        task_features: List of QgsFeature objects
        layer: Source layer for fallback info
        
    Returns:
        tuple: (valid_features: list, validation_errors: int, skipped_no_geometry: int)
    """
    valid_features = []
    validation_errors = 0
    skipped_no_geometry = 0
    
    for i, f in enumerate(task_features):
        try:
            if f is None or f == "":
                continue
            if hasattr(f, 'hasGeometry') and hasattr(f, 'geometry'):
                if f.hasGeometry() and not f.geometry().isEmpty():
                    valid_features.append(f)
                    if i < 3:
                        geom = f.geometry()
                        bbox = geom.boundingBox()
                        logger.debug(f"  Feature[{i}]: type={geom.wkbType()}, "
                                   f"bbox=({bbox.xMinimum():.1f},{bbox.yMinimum():.1f})-"
                                   f"({bbox.xMaximum():.1f},{bbox.yMaximum():.1f})")
                else:
                    skipped_no_geometry += 1
                    logger.debug(f"[Spatialite]   Skipping feature[{i}] without valid geometry")
            elif f:
                valid_features.append(f)
        except Exception as e:
            validation_errors += 1
            logger.warning(f"[Spatialite]   Feature[{i}] validation error (thread-safety): {e}")
            continue
    
    return valid_features, validation_errors, skipped_no_geometry


def recover_spatialite_features_from_fids(
    layer: Any,
    feature_fids: List
) -> List:
    """
    Recover features using FIDs when QgsFeature objects are invalid.
    
    EPIC-1 Phase E4-S8: FID recovery logic for thread-safety issues.
    
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
        recovered = list(layer.getFeatures(request))
        if recovered:
            logger.info(f"[Spatialite]   ✓ Recovered {len(recovered)} features using FIDs")
        return recovered
    except Exception as e:
        logger.error(f"[Spatialite]   ❌ FID recovery failed: {e}")
        return []


def resolve_spatialite_features(
    context: SpatialiteSourceContext,
    mode: str,
    metadata: Dict
) -> Tuple[List, bool]:
    """
    Resolve features based on the determined source mode.
    
    EPIC-1 Phase E4-S8: Extracted feature resolution logic.
    
    Args:
        context: SpatialiteSourceContext
        mode: Source mode from determine_spatialite_source_mode()
        metadata: Metadata dict from mode detection
        
    Returns:
        tuple: (features: list, recovery_attempted: bool)
    """
    source_layer = context.source_layer
    recovery_attempted = False
    features = []
    
    if mode == SourceMode.TASK_PARAMS:
        logger.info(f"[Spatialite] === resolve_spatialite_features (TASK PARAMS PRIORITY MODE) ===")
        task_features = metadata["task_features"]
        logger.info(f"[Spatialite]   Using {len(task_features)} features from task_parameters (thread-safe)")
        
        # Validate features
        valid_features, validation_errors, skipped_no_geometry = validate_spatialite_features(
            task_features, source_layer
        )
        
        total_failures = validation_errors + skipped_no_geometry
        features = valid_features
        logger.info(f"[Spatialite]   Valid features after filtering: {len(features)}")
        
        if skipped_no_geometry > 0:
            logger.warning(f"[Spatialite]   Skipped {skipped_no_geometry} features with no/empty geometry")
        
        # Recovery logic if all features failed
        if len(features) == 0 and len(task_features) > 0 and total_failures > 0:
            recovery_attempted = True
            logger.error(f"[Spatialite]   ❌ ALL {len(task_features)} task_features failed validation")
            
            # Try FID recovery
            feature_fids = metadata.get("feature_fids", [])
            if not feature_fids:
                feature_fids = context.task_parameters.get("feature_fids", [])
            
            if feature_fids:
                logger.info(f"[Spatialite]   → Attempting recovery using {len(feature_fids)} feature_fids")
                features = recover_spatialite_features_from_fids(source_layer, feature_fids)
            
            # Try selection recovery
            if len(features) == 0 and source_layer.selectedFeatureCount() > 0:
                logger.info(f"[Spatialite]   → Attempting recovery from source layer selection")
                try:
                    from qgis.core import QgsFeatureRequest
                    selected_fids = list(source_layer.selectedFeatureIds())
                    if selected_fids:
                        request = QgsFeatureRequest().setFilterFids(selected_fids)
                        features = list(source_layer.getFeatures(request))
                        logger.info(f"[Spatialite]   ✓ Recovered {len(features)} from selection")
                except Exception as e:
                    logger.error(f"[Spatialite]   ❌ Selection recovery failed: {e}")
                    
    elif mode == SourceMode.SUBSET:
        logger.info(f"[Spatialite] === resolve_spatialite_features (FILTERED MODE) ===")
        logger.info(f"[Spatialite]   Source layer has filter: {source_layer.subsetString()[:100]}")
        features = list(source_layer.getFeatures())
        logger.debug(f"[Spatialite]   Retrieved {len(features)} features")
        
    elif mode == SourceMode.SELECTION:
        logger.info(f"[Spatialite] === resolve_spatialite_features (MULTI-SELECTION MODE) ===")
        try:
            from qgis.core import QgsFeatureRequest
            selected_fids = list(source_layer.selectedFeatureIds())
            if selected_fids:
                request = QgsFeatureRequest().setFilterFids(selected_fids)
                features = list(source_layer.getFeatures(request))
        except Exception as e:
            logger.error(f"[Spatialite] Failed to get selected features: {e}")
            
    elif mode == SourceMode.FIELD_BASED:
        logger.info(f"[Spatialite] === resolve_spatialite_features (FIELD-BASED MODE) ===")
        logger.info(f"[Spatialite]   Field name: '{context.is_field_expression[1] if context.is_field_expression else 'unknown'}'")
        features = list(source_layer.getFeatures())
        
    else:  # FALLBACK
        logger.info(f"[Spatialite] === resolve_spatialite_features (FALLBACK MODE) ===")
        from qgis.core import QgsMessageLog, Qgis
        QgsMessageLog.logMessage(
            f"⚠️ FALLBACK MODE: Using ALL {source_layer.featureCount()} features",
            "FilterMate", Qgis.Warning
        )
        features = list(source_layer.getFeatures())
    
    return features, recovery_attempted


def process_spatialite_geometries(
    features: List,
    context: SpatialiteSourceContext
) -> Optional[str]:
    """
    Process geometries from features into WKT for Spatialite.
    
    EPIC-1 Phase E4-S8: Extracted geometry processing logic.
    Handles reprojection, centroid conversion, union, simplification.
    
    Args:
        features: List of QgsFeature objects
        context: SpatialiteSourceContext with processing parameters
        
    Returns:
        str: WKT string or None if processing failed
    """
    from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsGeometry, QgsWkbTypes
    
    # Import geometry safety functions (migrated from modules.geometry_safety)
    from ....core.geometry import (
        validate_geometry,
        safe_unary_union,
        safe_collect_geometry,
        safe_as_geometry_collection,
        extract_polygons_from_collection,
        get_geometry_type_name
    )
    
    raw_geometries = [f.geometry() for f in features if f.hasGeometry()]
    logger.debug(f"[Spatialite] process_spatialite_geometries: {len(raw_geometries)} geometries")
    
    if len(raw_geometries) == 0:
        logger.error(f"[Spatialite] No geometries found in features")
        return None
    
    geometries = []
    target_crs = QgsCoordinateReferenceSystem(context.source_layer_crs_authid)
    
    # Setup reprojection
    transform = None
    if context.has_to_reproject_source_layer and context.source_crs:
        source_crs_obj = QgsCoordinateReferenceSystem(context.source_crs.authid())
        transform = QgsCoordinateTransform(source_crs_obj, target_crs, context.PROJECT)
        logger.debug(f"[Spatialite] Will reproject from {context.source_crs.authid()} to {context.source_layer_crs_authid}")
    
    for geometry in raw_geometries:
        if geometry.isEmpty():
            continue
            
        geom_copy = QgsGeometry(geometry)
        
        # Centroid optimization
        # ORDER OF APPLICATION: Centroid first, then multipart conversion, then reprojection
        # This creates points from source geometries before union to WKT
        if context.param_use_centroids_source_layer:
            centroid = geom_copy.centroid()
            if centroid and not centroid.isEmpty():
                geom_copy = centroid
                logger.debug(f"[Spatialite] Converted to centroid")
        
        if geom_copy.isMultipart():
            geom_copy.convertToSingleType()
        
        if transform:
            geom_copy.transform(transform)
        
        # Log buffer info (buffer applied via SQL, not here)
        if context.param_buffer_value and context.param_buffer_value != 0:
            buffer_type = "expansion" if context.param_buffer_value > 0 else "erosion"
            logger.debug(f"[Spatialite] Buffer of {context.param_buffer_value}m ({buffer_type}) via ST_Buffer() in SQL")
        
        geometries.append(geom_copy)
    
    if len(geometries) == 0:
        logger.error(f"[Spatialite] No valid geometries after processing")
        return None
    
    # Dissolve using unaryUnion
    logger.info(f"[Spatialite] Applying dissolve (unaryUnion) on {len(geometries)} geometries")
    collected_geometry = safe_unary_union(geometries)
    
    if collected_geometry is None:
        logger.warning(f"[Spatialite] unaryUnion failed, falling back to safe_collect_geometry")
        collected_geometry = safe_collect_geometry(geometries)
    
    if collected_geometry is None:
        logger.error(f"[Spatialite] Both unaryUnion and collect failed")
        return None
    
    collected_type = get_geometry_type_name(collected_geometry)
    logger.info(f"[Spatialite] Dissolved geometry type: {collected_type}")
    
    # Handle GeometryCollection conversion
    if 'GeometryCollection' in collected_type:
        logger.warning(f"[Spatialite] Dissolve produced {collected_type} - converting to homogeneous type")
        
        has_polygons = any('Polygon' in get_geometry_type_name(g) for g in geometries if validate_geometry(g))
        has_lines = any('Line' in get_geometry_type_name(g) for g in geometries if validate_geometry(g))
        has_points = any('Point' in get_geometry_type_name(g) for g in geometries if validate_geometry(g))
        
        if has_polygons:
            polygon_parts = extract_polygons_from_collection(collected_geometry)
            if polygon_parts:
                collected_geometry = safe_collect_geometry(polygon_parts)
                if collected_geometry and 'GeometryCollection' in get_geometry_type_name(collected_geometry):
                    converted = collected_geometry.convertToType(QgsWkbTypes.PolygonGeometry, True)
                    if converted and not converted.isEmpty():
                        collected_geometry = converted
        elif has_lines:
            line_parts = []
            for part in safe_as_geometry_collection(collected_geometry):
                part_type = get_geometry_type_name(part)
                if 'Line' in part_type:
                    if 'Multi' in part_type:
                        for sub_part in safe_as_geometry_collection(part):
                            line_parts.append(sub_part)
                    else:
                        line_parts.append(part)
            if line_parts:
                collected_geometry = safe_collect_geometry(line_parts)
        elif has_points:
            point_parts = []
            for part in safe_as_geometry_collection(collected_geometry):
                part_type = get_geometry_type_name(part)
                if 'Point' in part_type:
                    if 'Multi' in part_type:
                        for sub_part in safe_as_geometry_collection(part):
                            point_parts.append(sub_part)
                    else:
                        point_parts.append(part)
            if point_parts:
                collected_geometry = safe_collect_geometry(point_parts)
    
    # Drop Z/M values for Spatialite compatibility
    if QgsWkbTypes.hasZ(collected_geometry.wkbType()) or QgsWkbTypes.hasM(collected_geometry.wkbType()):
        original_type = get_geometry_type_name(collected_geometry)
        abstract_geom = collected_geometry.constGet()
        if abstract_geom:
            cloned = abstract_geom.clone()
            cloned.dropZValue()
            cloned.dropMValue()
            collected_geometry = QgsGeometry(cloned)
            logger.info(f"[Spatialite]   ✓ Dropped Z/M: {original_type} → {get_geometry_type_name(collected_geometry)}")
    
    # Generate WKT with optimized precision
    crs_authid = context.source_layer_crs_authid
    if context.geometry_to_wkt:
        wkt = context.geometry_to_wkt(collected_geometry, crs_authid)
    else:
        wkt = collected_geometry.asWkt()
    
    geom_type = wkt.split('(')[0].strip() if '(' in wkt else 'Unknown'
    logger.info(f"[Spatialite]   Final geometry type: {geom_type}")
    logger.info(f"[Spatialite]   📏 WKT length: {len(wkt):,} chars")
    
    # Apply adaptive simplification for large geometries
    if context.get_optimization_thresholds:
        thresholds = context.get_optimization_thresholds()
        max_wkt_length = thresholds.get('exists_subquery_threshold', 100000)
        
        if len(wkt) > max_wkt_length and context.simplify_geometry_adaptive:
            logger.warning(f"[Spatialite]   ⚠️ WKT too long ({len(wkt)} > {max_wkt_length})")
            
            simplified = context.simplify_geometry_adaptive(
                collected_geometry,
                max_wkt_length=max_wkt_length,
                crs_authid=crs_authid
            )
            
            if simplified and not simplified.isEmpty():
                if context.geometry_to_wkt:
                    simplified_wkt = context.geometry_to_wkt(simplified, crs_authid)
                else:
                    simplified_wkt = simplified.asWkt()
                
                reduction_pct = (1 - len(simplified_wkt) / len(wkt)) * 100
                logger.info(f"[Spatialite]   ✓ Simplified: {len(wkt)} → {len(simplified_wkt)} chars ({reduction_pct:.1f}% reduction)")
                wkt = simplified_wkt
    
    # Escape single quotes for SQL
    return wkt.replace("'", "''")


def prepare_spatialite_source_geom(context: SpatialiteSourceContext) -> SpatialiteSourceResult:
    """
    Prepare source geometry for Spatialite filtering.
    
    EPIC-1 Phase E4-S8: Main orchestration function extracted from filter_task.py.
    Converts selected features to WKT format for use in Spatialite spatial queries.
    Handles reprojection, buffering, caching, and geometry optimization.
    
    Supports all geometry types including non-linear geometries:
    - CIRCULARSTRING, COMPOUNDCURVE, CURVEPOLYGON, MULTICURVE, MULTISURFACE
    
    Performance: Uses cache to avoid recalculating for multiple layers.
    
    Args:
        context: SpatialiteSourceContext with all required parameters
        
    Returns:
        SpatialiteSourceResult with WKT and metadata
    """
    source_layer = context.source_layer
    
    if not source_layer:
        return SpatialiteSourceResult(
            success=False,
            error_message="No source layer provided"
        )
    
    # Step 1: Determine source mode
    mode, metadata = determine_spatialite_source_mode(context)
    logger.info(f"[Spatialite] Source mode: {mode}")
    
    # Step 2: Check cache first
    current_subset = source_layer.subsetString() or ''
    layer_id = source_layer.id()
    
    if context.geom_cache:
        # Get features for cache key (we need to resolve first for proper cache lookup)
        # For now, check if we have cached data
        pass  # Cache lookup moved after feature resolution for proper key
    
    # Step 3: Resolve features
    features, recovery_attempted = resolve_spatialite_features(context, mode, metadata)
    
    if not features:
        # Handle expression fallback
        filter_expression = context.expression
        new_subset = context.param_source_new_subset
        
        if recovery_attempted:
            logger.error(f"[Spatialite] BLOCKING fallback - recovery was attempted")
            return SpatialiteSourceResult(
                success=False,
                error_message="Cannot recover source features. Verify selection before filtering."
            )
        
        filter_to_use = filter_expression or new_subset
        if filter_to_use and filter_to_use.strip():
            try:
                from qgis.core import QgsFeatureRequest, QgsExpression
                expr = QgsExpression(filter_to_use)
                if not expr.hasParserError():
                    request = QgsFeatureRequest(expr)
                    features = list(source_layer.getFeatures(request))
                    logger.info(f"[Spatialite] Expression fallback: {len(features)} features")
            except Exception as e:
                logger.warning(f"[Spatialite] Expression fallback failed: {e}")
        
        if not features:
            features = list(source_layer.getFeatures())
            logger.info(f"[Spatialite] Final fallback: Using all {len(features)} features")
    
    if not features:
        return SpatialiteSourceResult(
            success=False,
            error_message="No features found for geometry preparation"
        )
    
    logger.info(f"[Spatialite] Processing {len(features)} features")
    logger.debug(f"[Spatialite] Buffer value: {context.param_buffer_value}")
    logger.debug(f"[Spatialite] Target CRS: {context.source_layer_crs_authid}")
    
    # Step 4: Check cache with proper key
    if context.geom_cache:
        cached_geom = context.geom_cache.get(
            features,
            context.param_buffer_value,
            context.source_layer_crs_authid,
            layer_id=layer_id,
            subset_string=current_subset
        )
        
        if cached_geom is not None:
            cached_wkt = cached_geom.get('wkt')
            wkt_type = cached_wkt.split('(')[0].strip() if cached_wkt else 'Unknown'
            
            # Validate cache - check if buffer expected but cached is LineString
            cache_is_valid = True
            if context.param_buffer_value and context.param_buffer_value != 0:
                if 'LineString' in wkt_type or 'Line' in wkt_type:
                    logger.error(f"[Spatialite] ❌ CACHE BUG DETECTED - stale geometry without buffer")
                    context.geom_cache.clear()
                    cache_is_valid = False
            
            if cache_is_valid:
                logger.info(f"[Spatialite] ✓ Using CACHED source geometry for Spatialite")
                return SpatialiteSourceResult(
                    wkt=cached_wkt,
                    success=True,
                    feature_count=len(features),
                    geometry_type=wkt_type,
                    from_cache=True
                )
    
    # Step 5: Process geometries
    wkt = process_spatialite_geometries(features, context)
    
    if not wkt:
        return SpatialiteSourceResult(
            success=False,
            error_message="Geometry processing failed"
        )
    
    geom_type = wkt.split('(')[0].strip() if '(' in wkt else 'Unknown'
    logger.info(f"[Spatialite]   WKT length: {len(wkt)} chars")
    logger.info(f"[Spatialite] === prepare_spatialite_source_geom END ===")
    
    # Step 6: Build buffer state for multi-step filters
    buffer_value = context.param_buffer_value or 0
    existing_buffer_state = {}
    if context.task_parameters and 'infos' in context.task_parameters:
        existing_buffer_state = context.task_parameters['infos'].get('buffer_state', {})
    
    is_multi_step = existing_buffer_state.get('is_pre_buffered', False)
    previous_buffer_value = existing_buffer_state.get('buffer_value', 0)
    
    buffer_state = {
        'has_buffer': buffer_value != 0,
        'buffer_value': buffer_value,
        'is_pre_buffered': is_multi_step and previous_buffer_value == buffer_value,
        'buffer_column': 'geom_buffered' if (is_multi_step and previous_buffer_value == buffer_value) else 'geom',
        'previous_buffer_value': previous_buffer_value if is_multi_step else None
    }
    
    if is_multi_step and previous_buffer_value == buffer_value and buffer_value != 0:
        logger.info(f"[Spatialite]   ✓ Multi-step: Reusing existing {buffer_value}m buffer")
    
    # Step 7: Store in cache
    if context.geom_cache:
        context.geom_cache.put(
            features,
            context.param_buffer_value,
            context.source_layer_crs_authid,
            {'wkt': wkt},
            layer_id=layer_id,
            subset_string=current_subset
        )
        logger.info(f"[Spatialite] ✓ Source geometry computed and CACHED")
    
    return SpatialiteSourceResult(
        wkt=wkt,
        success=True,
        feature_count=len(features),
        geometry_type=geom_type,
        from_cache=False,
        buffer_state=buffer_state
    )


def qgis_expression_to_spatialite(expression: str, geom_col: str = 'geometry') -> str:
    """
    Convert QGIS expression to Spatialite SQL.
    
    EPIC-1 Phase E4-S1: Extracted from filter_task.py line 3526 (58 lines)
    
    Spatialite spatial functions are ~90% compatible with PostGIS, but differences:
    - Type casting: PostgreSQL uses :: operator, Spatialite uses CAST() function
    - String comparison is case-sensitive by default
    - No ILIKE operator (use LOWER() + LIKE instead)
    
    Args:
        expression: QGIS expression string
        geom_col: Geometry column name (default: 'geometry')
        
    Returns:
        str: Spatialite SQL expression
    """
    import re
    import logging
    
    logger = logging.getLogger('FilterMate.Adapters.Backends.Spatialite.FilterExecutor')
    
    if not expression:
        return expression
    
    # Handle CASE expressions
    expression = re.sub('case', ' CASE ', expression, flags=re.IGNORECASE)
    expression = re.sub('when', ' WHEN ', expression, flags=re.IGNORECASE)
    expression = re.sub(' is ', ' IS ', expression, flags=re.IGNORECASE)
    expression = re.sub('then', ' THEN ', expression, flags=re.IGNORECASE)
    expression = re.sub('else', ' ELSE ', expression, flags=re.IGNORECASE)
    
    # Handle LIKE/ILIKE - Spatialite doesn't have ILIKE, use LIKE with LOWER()
    # IMPORTANT: Process ILIKE first, before processing LIKE, to avoid double-replacement
    expression = re.sub(
        r'(\w+)\s+ILIKE\s+',
        r'LOWER(\1) LIKE LOWER(',
        expression,
        flags=re.IGNORECASE
    )
    expression = re.sub(r'\bNOT\b', ' NOT ', expression, flags=re.IGNORECASE)
    expression = re.sub(r'\bLIKE\b', ' LIKE ', expression, flags=re.IGNORECASE)
    
    # Convert PostgreSQL :: type casting to Spatialite CAST() function
    expression = re.sub(r'(["\w]+)::numeric', r'CAST(\1 AS REAL)', expression)
    expression = re.sub(r'(["\w]+)::integer', r'CAST(\1 AS INTEGER)', expression)
    expression = re.sub(r'(["\w]+)::text', r'CAST(\1 AS TEXT)', expression)
    expression = re.sub(r'(["\w]+)::double', r'CAST(\1 AS REAL)', expression)
    
    return expression


def build_spatialite_query(
    sql_subset_string: str,
    table_name: str,
    geom_key_name: str,
    primary_key_name: str,
    custom: bool,
    buffer_expression: str = None,
    buffer_value: float = None,
    buffer_segments: int = 5,
    buffer_type: str = "Round",
    task_parameters: dict = None
) -> str:
    """
    Build Spatialite query for simple or complex (buffered) subsets.
    
    EPIC-1 Phase E4-S2: Extracted from filter_task.py line 10616 (64 lines)
    
    Args:
        sql_subset_string: SQL query for subset
        table_name: Source table name
        geom_key_name: Geometry field name
        primary_key_name: Primary key field name
        custom: Whether custom buffer expression is used
        buffer_expression: QGIS expression for dynamic buffer
        buffer_value: Static buffer value in meters
        buffer_segments: Number of segments for round buffers
        buffer_type: Buffer type ('Round', 'Flat', 'Square')
        task_parameters: Task parameters dict
        
    Returns:
        str: Spatialite SELECT query
    """
    if custom is False:
        # Simple subset - use query as-is
        return sql_subset_string
    
    # Complex subset with buffer (adapt from PostgreSQL logic)
    buffer_expr = (
        qgis_expression_to_spatialite(buffer_expression)
        if buffer_expression
        else str(buffer_value)
    )
    
    # Build ST_Buffer style parameters (quad_segs for segments, endcap for type)
    buffer_type_mapping = {
        "Round": "round",
        "Flat": "flat",
        "Square": "square"
    }
    buffer_type_str = (
        task_parameters.get("filtering", {}).get("buffer_type", "Round")
        if task_parameters
        else buffer_type
    )
    endcap_style = buffer_type_mapping.get(buffer_type_str, "round")
    quad_segs = buffer_segments
    
    # Build style string for Spatialite ST_Buffer
    style_params = f"quad_segs={quad_segs}"
    if endcap_style != 'round':
        style_params += f" endcap={endcap_style}"
    
    # Build Spatialite SELECT (similar to PostgreSQL CREATE MATERIALIZED VIEW)
    # Note: Spatialite uses same ST_Buffer syntax as PostGIS
    query = f"""
        SELECT 
            ST_Buffer({geom_key_name}, {buffer_expr}, '{style_params}') as {geom_key_name},
            {primary_key_name},
            {buffer_expr} as buffer_value
        FROM {table_name}
        WHERE {primary_key_name} IN ({sql_subset_string})
    """
    
    return query


def apply_spatialite_subset(
    layer,
    name: str,
    primary_key_name: str,
    sql_subset_string: str,
    cur=None,
    conn=None,
    current_seq_order: int = 0,
    session_id: str = None,
    project_uuid: str = None,
    source_layer_id: str = None,
    queue_subset_func=None
) -> bool:
    """
    Apply subset string to layer and update history.
    
    EPIC-1 Phase E4-S4: Extracted from filter_task.py line 10591 (44 lines)
    
    Args:
        layer: QGIS vector layer
        name: Temp table name
        primary_key_name: Primary key field name
        sql_subset_string: Original SQL subset string for history
        cur: Spatialite cursor for history
        conn: Spatialite connection for history
        current_seq_order: Sequence order for history
        session_id: Session ID for multi-client isolation
        project_uuid: Project UUID for history
        source_layer_id: Source layer ID for history
        queue_subset_func: Function to queue subset string for main thread
        
    Returns:
        bool: True if successful
    """
    # Build session-prefixed name for multi-client isolation
    session_name = f"{session_id}_{name}" if session_id else name
    
    # Apply subset string to layer (reference temp table)
    layer_subsetString = (
        f'"{primary_key_name}" IN '
        f'(SELECT "{primary_key_name}" FROM mv_{session_name})'
    )
    logger.debug(f"[Spatialite] Applying Spatialite subset string: {layer_subsetString}")
    
    # THREAD SAFETY: Queue subset string for application in finished()
    if queue_subset_func:
        queue_subset_func(layer, layer_subsetString)
    
    # EPIC-1 E4-S9: Use centralized HistoryRepository instead of direct SQL
    if cur and conn and project_uuid:
        history_repo = HistoryRepository(conn, cur)
        try:
            history_repo.insert(
                project_uuid=project_uuid,
                layer_id=layer.id(),
                subset_string=sql_subset_string,
                seq_order=current_seq_order,
                source_layer_id=source_layer_id or ''
            )
        except Exception as e:
            logger.warning(f"[Spatialite] Failed to update Spatialite history: {e}")
        finally:
            history_repo.close()
    
    return True


def manage_spatialite_subset(
    layer,
    sql_subset_string: str,
    primary_key_name: str,
    geom_key_name: str,
    name: str,
    custom: bool = False,
    cur=None,
    conn=None,
    current_seq_order: int = 0,
    session_id: str = None,
    project_uuid: str = None,
    source_layer_id: str = None,
    queue_subset_func=None,
    get_spatialite_datasource_func=None,
    task_parameters: dict = None
) -> bool:
    """
    Handle Spatialite temporary tables for filtering.
    
    EPIC-1 Phase E4-S4: Extracted from filter_task.py line 10635 (66 lines)
    
    Alternative to PostgreSQL materialized views using create_temp_spatialite_table().
    
    Args:
        layer: QGIS vector layer
        sql_subset_string: SQL query for subset
        primary_key_name: Primary key field name
        geom_key_name: Geometry field name
        name: Unique name for temp table
        custom: Whether custom buffer expression is used
        cur: Spatialite cursor for history
        conn: Spatialite connection for history
        current_seq_order: Sequence order for history
        session_id: Session ID for multi-client isolation
        project_uuid: Project UUID for history
        source_layer_id: Source layer ID for history
        queue_subset_func: Function to queue subset string for main thread
        get_spatialite_datasource_func: Function to get datasource info
        task_parameters: Task parameters dict for buffer options
        
    Returns:
        bool: True if successful
    """
    try:
        from ....infrastructure.database.sql_utils import create_temp_spatialite_table
    except ImportError:
        logger.error(f"[Spatialite] create_temp_spatialite_table not available")
        return False
    
    # Get datasource information
    if get_spatialite_datasource_func:
        db_path, table_name, layer_srid, is_native_spatialite = (
            get_spatialite_datasource_func(layer)
        )
    else:
        # Fallback: assume it's a native Spatialite layer
        db_path = layer.source().split('|')[0]
        table_name = layer.source().split('table=')[1].split(' ')[0] if 'table=' in layer.source() else layer.name()
        layer_srid = layer.crs().authid().split(':')[1] if layer.crs().authid() else '4326'
        is_native_spatialite = True
    
    # For non-Spatialite layers, use QGIS subset string directly
    if not is_native_spatialite:
        if queue_subset_func:
            queue_subset_func(layer, sql_subset_string)
        return True
    
    # Build Spatialite query (simple or buffered)
    spatialite_query = build_spatialite_query(
        sql_subset_string=sql_subset_string,
        table_name=table_name,
        geom_key_name=geom_key_name,
        primary_key_name=primary_key_name,
        custom=custom,
        task_parameters=task_parameters
    )
    
    # Create temporary table with session-prefixed name
    session_name = f"{session_id}_{name}" if session_id else name
    logger.info(
        f"Creating Spatialite temp table 'mv_{session_name}' "
        f"(session: {session_id})"
    )
    
    success = create_temp_spatialite_table(
        db_path=db_path,
        table_name=session_name,
        sql_query=spatialite_query,
        geom_field=geom_key_name,
        srid=layer_srid
    )
    
    if not success:
        logger.error(f"[Spatialite] Failed to create Spatialite temp table")
        return False
    
    # Apply subset and update history
    return apply_spatialite_subset(
        layer=layer,
        name=name,
        primary_key_name=primary_key_name,
        sql_subset_string=sql_subset_string,
        cur=cur,
        conn=conn,
        current_seq_order=current_seq_order,
        session_id=session_id,
        project_uuid=project_uuid,
        source_layer_id=source_layer_id,
        queue_subset_func=queue_subset_func
    )


def get_last_subset_info(cur, layer, project_uuid: str, conn=None) -> tuple:
    """
    Get the last subset information for a layer from history.
    
    EPIC-1 Phase E4-S4: Extracted from filter_task.py line 10703 (28 lines)
    
    Args:
        cur: Database cursor
        layer: QgsVectorLayer
        project_uuid: Project UUID
        conn: Database connection (optional, for HistoryRepository)
        
    Returns:
        tuple: (last_subset_id, last_seq_order, layer_name, sanitized_name)
    """
    from ....infrastructure.database.sql_utils import sanitize_sql_identifier
    
    layer_name = layer.name()
    # Use sanitize_sql_identifier to handle all special chars (em-dash, etc.)
    name = sanitize_sql_identifier(layer.id().replace(layer_name, ''))
    
    # EPIC-1 E4-S9: Use centralized HistoryRepository if connection available
    if conn:
        history_repo = HistoryRepository(conn, cur)
        try:
            last_entry = history_repo.get_last_entry(project_uuid, layer.id())
            if last_entry:
                return last_entry.id, last_entry.seq_order, layer_name, name
            else:
                return None, 0, layer_name, name
        except Exception as e:
            logger.warning(f"[Spatialite] Failed to get last subset info via repository: {e}")
            return None, 0, layer_name, name
        finally:
            history_repo.close()
    
    # Fallback to direct SQL if no connection provided
    try:
        cur.execute(
            """SELECT * FROM fm_subset_history 
               WHERE fk_project = '{fk_project}' AND layer_id = '{layer_id}' 
               ORDER BY seq_order DESC LIMIT 1;""".format(
                fk_project=project_uuid,
                layer_id=layer.id()
            )
        )
        
        results = cur.fetchall()
        if len(results) == 1:
            result = results[0]
            return result[0], result[5], layer_name, name
        else:
            return None, 0, layer_name, name
    except Exception as e:
        logger.warning(f"[Spatialite] Failed to get last subset info: {e}")
        return None, 0, layer_name, name


def cleanup_session_temp_tables(
    db_path: str,
    session_id: str
) -> int:
    """
    Clean up all temporary tables for a specific session.
    
    EPIC-1 Phase E4-S4: New function for session cleanup
    
    Drops all temporary tables and indexes prefixed with the session_id.
    Should be called when closing the plugin or resetting.
    
    Args:
        db_path: Path to Spatialite database
        session_id: Session identifier prefix
        
    Returns:
        int: Number of tables cleaned up
    """
    import sqlite3
    
    if not session_id or not db_path:
        return 0
    
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Find all temp tables for this session
        cur.execute(
            """SELECT name FROM sqlite_master 
               WHERE type='table' AND name LIKE ?""",
            (f"mv_{session_id}_%",)
        )
        tables = cur.fetchall()
        
        count = 0
        for (table_name,) in tables:
            try:
                # Drop the table
                cur.execute(f'DROP TABLE IF EXISTS "{table_name}";')
                # Drop associated R-tree index
                cur.execute(f'DROP TABLE IF EXISTS "idx_{table_name}_geometry";')
                count += 1
            except Exception as e:
                logger.warning(f"[Spatialite] Error dropping temp table {table_name}: {e}")
        
        conn.commit()
        conn.close()
        
        if count > 0:
            logger.info(
                f"Cleaned up {count} Spatialite temp table(s) "
                f"for session {session_id}"
            )
        return count
        
    except Exception as e:
        logger.error(f"[Spatialite] Error cleaning up session tables: {e}")
        return 0


def normalize_column_names_for_spatialite(
    expression: str,
    field_names: list
) -> str:
    """
    Normalize column names in expression for Spatialite.
    
    EPIC-1 Phase E4-S4: Spatialite equivalent of PostgreSQL function
    
    Spatialite is case-insensitive for column names by default,
    but we still need to ensure proper quoting.
    
    Args:
        expression: SQL expression string
        field_names: List of actual field names from the layer
        
    Returns:
        str: Expression with properly quoted column names
    """
    import re
    
    if not expression or not field_names:
        return expression
    
    result_expression = expression
    
    # Find all unquoted column references that match field names
    for field_name in field_names:
        # Pattern: word boundary + field name + word boundary (not already quoted)
        pattern = r'(?<!")\b' + re.escape(field_name) + r'\b(?!")'
        replacement = f'"{field_name}"'
        result_expression = re.sub(pattern, replacement, result_expression)
    
    return result_expression


def build_spatial_filter_expression(
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
    Build Spatialite SQL filter expression for geometric predicates.
    
    v4.2.1 (2026-01-18): Implemented proper spatial filtering for Spatialite.
    
    Spatialite uses similar spatial functions to PostGIS but with some differences:
    - Same predicate names: ST_Intersects, ST_Contains, ST_Within, etc.
    - GeomFromText for WKT instead of ST_GeomFromText
    - Subset strings apply directly via setSubsetString() - no EXISTS needed
    
    Args:
        layer_props: Layer properties dict with table_name, geom_field, pk_field, etc.
        predicates: Dict of predicates (within_distance, intersects, etc.)
        source_geom: Source geometry WKT string
        buffer_value: Buffer distance in meters
        buffer_expression: QGIS expression for dynamic buffer
        source_filter: Optional WHERE clause for source layer (unused for Spatialite)
        use_centroids: Use layer centroids instead of full geometries
        **kwargs: Additional parameters (source_wkt, source_srid, source_feature_count)
        
    Returns:
        str: Spatialite SQL WHERE clause expression or "" if geometry missing
    """
    logger.info(f"[Spatialite] build_spatial_filter_expression() CALLED")
    logger.info(f"  predicates: {predicates}")
    logger.info(f"  source_geom (WKT) available: {source_geom is not None}")
    logger.info(f"  buffer_value: {buffer_value}")
    logger.info(f"  use_centroids: {use_centroids}")
    
    # Validate we have source geometry
    if not source_geom or not isinstance(source_geom, str):
        logger.warning(f"[Spatialite] No source geometry WKT provided - cannot build spatial expression")
        return ""
    
    # Get geometry field and SRID
    geom_field = layer_props.get('layer_geometry_field', 'geometry')
    source_srid = kwargs.get('source_srid', 4326)  # Default to WGS84
    
    logger.info(f"  geom_field: {geom_field}")
    logger.info(f"  source_srid: {source_srid}")
    
    # Build GeomFromText expression
    # Spatialite: GeomFromText(wkt, srid)
    source_geom_expr = f"GeomFromText('{source_geom}', {source_srid})"
    
    # Apply buffer if needed
    if buffer_value and buffer_value != 0:
        logger.info(f"  Applying buffer: {buffer_value}m")
        # Spatialite ST_Buffer syntax: ST_Buffer(geom, distance)
        source_geom_expr = f"ST_Buffer({source_geom_expr}, {buffer_value})"
    
    # Build target geometry expression
    target_geom_expr = f'"{geom_field}"'
    if use_centroids:
        target_geom_expr = f'ST_Centroid({target_geom_expr})'
    
    # Map QGIS predicates to Spatialite functions
    predicate_mapping = {
        'intersects': 'ST_Intersects',
        'contains': 'ST_Contains',
        'within': 'ST_Within',
        'crosses': 'ST_Crosses',
        'touches': 'ST_Touches',
        'overlaps': 'ST_Overlaps',
        'disjoint': 'ST_Disjoint',
        'equals': 'ST_Equals',
    }
    
    # Build predicate expressions
    predicate_clauses = []
    for predicate_name in (predicates if isinstance(predicates, list) else [predicates]):
        predicate_func = predicate_mapping.get(predicate_name.lower())
        if predicate_func:
            # Build predicate: ST_Intersects("geometry", GeomFromText(...))
            clause = f"{predicate_func}({target_geom_expr}, {source_geom_expr})"
            predicate_clauses.append(clause)
            logger.debug(f"  Added predicate: {clause[:100]}...")
        else:
            logger.warning(f"  Unknown predicate '{predicate_name}' - skipping")
    
    if not predicate_clauses:
        logger.warning(f"[Spatialite] No valid predicates - cannot build expression")
        return ""
    
    # Combine multiple predicates with OR (standard spatial logic)
    expression = " OR ".join(predicate_clauses)
    
    logger.info(f"[Spatialite] ✓ Built spatial expression: {len(expression)} chars")
    logger.debug(f"  Expression: {expression[:200]}...")
    
    return expression


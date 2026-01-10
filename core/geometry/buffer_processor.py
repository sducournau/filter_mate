"""
Buffer Processing Module

EPIC-1 Phase E2: Extracted from modules/tasks/filter_task.py

Provides buffer operations for vector layers:
- Positive buffers (expansion)
- Negative buffers (erosion/shrink)
- Expression-based buffer distances
- Geometry repair and dissolve operations

Supports:
- QGIS processing algorithm (qgis:buffer)
- Manual buffering (fallback)
- Geographic CRS validation

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase E2)
"""

import logging
from dataclasses import dataclass
from typing import Optional, Tuple, List

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsExpression,
    QgsExpressionContext,
    QgsFeature,
    QgsGeometry,
    QgsProcessing,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProperty,
    QgsVectorLayer,
    QgsWkbTypes
)
from qgis import processing

# Import geometry safety utilities
from modules.geometry_safety import (
    validate_geometry,
    safe_buffer,
    safe_unary_union,
    safe_convert_to_multi_polygon,
    safe_as_polygon,
    safe_collect_geometry,
    extract_polygons_from_collection,
    get_geometry_type_name
)

logger = logging.getLogger('FilterMate.Core.Geometry.Buffer')


@dataclass
class BufferConfig:
    """Configuration for buffer operations."""
    
    buffer_type: int = 0  # 0=Round, 1=Flat, 2=Square
    buffer_segments: int = 5  # Number of segments for round caps
    dissolve: bool = True  # Dissolve overlapping buffers
    
    def __post_init__(self):
        """Validate configuration."""
        if self.buffer_segments < 1:
            raise ValueError("buffer_segments must be >= 1")
        if self.buffer_type not in (0, 1, 2):
            raise ValueError("buffer_type must be 0 (Round), 1 (Flat), or 2 (Square)")


def evaluate_buffer_distance(
    layer: QgsVectorLayer,
    buffer_param: 'QgsProperty | float'
) -> float:
    """
    Evaluate buffer distance from parameter (handles expressions).
    
    Args:
        layer: Layer to use for expression evaluation
        buffer_param: QgsProperty (expression) or float value
        
    Returns:
        float: Evaluated buffer distance (0 if cannot be evaluated)
    """
    if isinstance(buffer_param, QgsProperty):
        # Expression-based buffer: use first feature to evaluate
        features = list(layer.getFeatures())
        if features:
            context = QgsExpressionContext()
            context.setFeature(features[0])
            return buffer_param.value(context, 0)
        return 0
    return float(buffer_param)


def create_memory_layer_for_buffer(layer: QgsVectorLayer) -> QgsVectorLayer:
    """
    Create empty memory layer for buffered features.
    
    Buffers ALWAYS produce polygon geometries regardless of source type
    (Point/Line/Polygon). Uses MultiPolygon to handle both single and
    multi-part results.
    
    Args:
        layer: Source layer for CRS
        
    Returns:
        QgsVectorLayer: Empty memory layer configured for MultiPolygon
    """
    geom_type = "MultiPolygon"
    buffered_layer = QgsVectorLayer(
        f"{geom_type}?crs={layer.crs().authid()}",
        "buffered_temp",
        "memory"
    )
    return buffered_layer


def buffer_all_features(
    layer: QgsVectorLayer,
    buffer_dist: float,
    buffer_segments: int = 5
) -> Tuple[List[QgsGeometry], int, int, int]:
    """
    Buffer all features from layer.
    
    STABILITY FIX v2.3.9: Uses safe_buffer wrapper to prevent
    access violations on certain machines.
    
    NOTE: Negative buffers (erosion) may produce empty geometries if the buffer
    distance is larger than the feature width. This is expected behavior.
    
    Args:
        layer: Source layer
        buffer_dist: Buffer distance (can be negative for erosion)
        buffer_segments: Number of segments for round caps (default: 5)
        
    Returns:
        tuple: (geometries, valid_count, invalid_count, eroded_count)
            - geometries: List of buffered QgsGeometry objects
            - valid_count: Number of successfully buffered features
            - invalid_count: Number of features that failed buffering
            - eroded_count: Number of features completely eroded (negative buffer)
    """
    geometries = []
    valid_features = 0
    invalid_features = 0
    eroded_features = 0  # Count features that eroded completely
    
    is_negative_buffer = buffer_dist < 0
    logger.debug(
        f"Buffering features: layer type={layer.geometryType()}, "
        f"wkb type={layer.wkbType()}, buffer_dist={buffer_dist}"
    )
    
    if is_negative_buffer:
        logger.info(
            f"⚠️ Applying NEGATIVE BUFFER (erosion) of {buffer_dist}m - "
            f"some features may disappear completely"
        )
    
    for idx, feature in enumerate(layer.getFeatures()):
        geom = feature.geometry()
        
        # STABILITY FIX: Use validate_geometry for proper checking
        if not validate_geometry(geom):
            logger.debug(f"Feature {idx}: Invalid or empty geometry, skipping")
            invalid_features += 1
            continue
        
        try:
            # STABILITY FIX: Use safe_buffer wrapper instead of direct buffer()
            # This handles invalid geometries gracefully and prevents GEOS crashes
            buffered_geom = safe_buffer(geom, buffer_dist, buffer_segments)
            
            if buffered_geom is not None:
                geometries.append(buffered_geom)
                valid_features += 1
                logger.debug(f"Feature {idx}: Buffered geometry accepted")
            else:
                # Check if this is complete erosion (expected for negative buffers)
                if is_negative_buffer:
                    logger.debug(f"Feature {idx}: Completely eroded (negative buffer)")
                    eroded_features += 1
                else:
                    logger.warning(f"Feature {idx}: safe_buffer returned None")
                    invalid_features += 1
                
        except Exception as buffer_error:
            logger.warning(f"Feature {idx}: Buffer operation failed: {buffer_error}")
            invalid_features += 1
    
    # Enhanced logging for negative buffers
    if is_negative_buffer and eroded_features > 0:
        logger.info(
            f"📊 Buffer négatif résultats: {valid_features} features conservées, "
            f"{eroded_features} complètement érodées, {invalid_features} invalides"
        )
        if valid_features == 0:
            logger.warning(
                f"⚠️ TOUTES les features ont été érodées par le buffer de {buffer_dist}m! "
                f"Réduisez la distance du buffer."
            )
    else:
        logger.debug(
            f"Manual buffer results: {valid_features} valid, {invalid_features} invalid features"
        )
    
    return geometries, valid_features, invalid_features, eroded_features


def dissolve_and_add_to_layer(
    geometries: List[QgsGeometry],
    buffered_layer: QgsVectorLayer,
    verify_spatial_index_fn: Optional[callable] = None
) -> QgsVectorLayer:
    """
    Dissolve geometries and add to memory layer.
    
    STABILITY FIX v2.3.9: Uses geometry_safety module to prevent
    access violations when handling GeometryCollections.
    
    Args:
        geometries: List of buffered geometries
        buffered_layer: Target memory layer
        verify_spatial_index_fn: Optional callback to create spatial index
            Signature: verify_spatial_index_fn(layer, layer_name)
            
    Returns:
        QgsVectorLayer: Layer with dissolved geometry added
    """
    # Filter out invalid geometries first (STABILITY FIX)
    valid_geometries = [g for g in geometries if validate_geometry(g)]
    
    if not valid_geometries:
        logger.warning("dissolve_and_add_to_layer: No valid geometries to dissolve")
        return buffered_layer
    
    # Dissolve all geometries into one using safe wrapper
    dissolved_geom = safe_unary_union(valid_geometries)
    
    if dissolved_geom is None:
        logger.error("dissolve_and_add_to_layer: safe_unary_union returned None")
        return buffered_layer
    
    # STABILITY FIX: Use safe conversion to MultiPolygon
    final_type = get_geometry_type_name(dissolved_geom)
    logger.debug(f"Dissolved geometry type: {final_type}")
    
    if 'GeometryCollection' in final_type or 'Polygon' not in final_type:
        logger.info(f"Converting {final_type} to MultiPolygon using safe wrapper")
        converted = safe_convert_to_multi_polygon(dissolved_geom)
        if converted:
            dissolved_geom = converted
            logger.info(f"Converted to {get_geometry_type_name(dissolved_geom)}")
        else:
            # Last resort: extract polygons manually using safe function
            logger.warning("safe_convert_to_multi_polygon failed, extracting polygons")
            polygon_parts = extract_polygons_from_collection(dissolved_geom)
            if polygon_parts:
                collected = safe_collect_geometry(polygon_parts)
                if collected:
                    dissolved_geom = collected
                    # Force conversion if still not polygon
                    if 'Polygon' not in get_geometry_type_name(dissolved_geom):
                        converted = dissolved_geom.convertToType(QgsWkbTypes.PolygonGeometry, True)
                        if converted and not converted.isEmpty():
                            dissolved_geom = converted
            else:
                logger.error("Could not extract any polygons from geometry")
                return buffered_layer
    
    # FINAL SAFETY CHECK: Ensure geometry is MultiPolygon before adding to layer
    if validate_geometry(dissolved_geom):
        final_type = get_geometry_type_name(dissolved_geom)
        logger.info(f"Final geometry type before adding: {final_type}")
        
        # Ensure it's MultiPolygon (not single Polygon)
        if dissolved_geom.wkbType() == QgsWkbTypes.Polygon:
            # Convert single Polygon to MultiPolygon using safe wrapper
            poly_data = safe_as_polygon(dissolved_geom)
            if poly_data:
                dissolved_geom = QgsGeometry.fromMultiPolygonXY([poly_data])
                logger.debug("Converted single Polygon to MultiPolygon")
    else:
        logger.error("Final dissolved geometry is invalid")
        return buffered_layer
    
    # Create feature with dissolved geometry
    feat = QgsFeature()
    feat.setGeometry(dissolved_geom)
    
    provider = buffered_layer.dataProvider()
    success, _ = provider.addFeatures([feat])
    if not success:
        logger.error(
            f"Failed to add feature to buffer layer. "
            f"Geometry type: {get_geometry_type_name(dissolved_geom)}"
        )
    buffered_layer.updateExtents()
    
    # Create spatial index for improved performance (if callback provided)
    if verify_spatial_index_fn:
        verify_spatial_index_fn(buffered_layer, "buffered_temp")
    
    return buffered_layer


def create_buffered_memory_layer(
    layer: QgsVectorLayer,
    buffer_distance: 'QgsProperty | float',
    buffer_segments: int = 5,
    verify_spatial_index_fn: Optional[callable] = None,
    warning_callback: Optional[callable] = None
) -> QgsVectorLayer:
    """
    Manually buffer layer features and create memory layer (fallback method).
    
    This is a fallback when qgis:buffer processing fails. It:
    1. Validates CRS (warns about geographic CRS)
    2. Evaluates buffer distance (handles expressions)
    3. Buffers all features individually
    4. Dissolves results into single geometry
    5. Returns memory layer with buffered geometry
    
    Args:
        layer: Input layer
        buffer_distance: QgsProperty (expression) or float value
        buffer_segments: Number of segments for round caps (default: 5)
        verify_spatial_index_fn: Optional callback to create spatial index
        warning_callback: Optional callback for user warnings (erosion, etc.)
            Signature: warning_callback(message: str)
            
    Returns:
        QgsVectorLayer: Memory layer with buffered geometries
        
    Raises:
        Exception: If source layer has no features
    """
    feature_count = layer.featureCount()
    logger.info(
        f"Manual buffer: Layer has {feature_count} features, "
        f"geomType={layer.geometryType()}, wkbType={layer.wkbType()}"
    )
    
    # CRS diagnostic
    crs = layer.crs()
    is_geographic = crs.isGeographic()
    logger.info(f"Manual buffer CRS: {crs.authid()}, isGeographic={is_geographic}")
    
    if feature_count == 0:
        raise Exception("Cannot buffer layer: source layer has no features")
    
    # Evaluate buffer distance
    buffer_dist = evaluate_buffer_distance(layer, buffer_distance)
    logger.debug(f"Manual buffer distance: {buffer_dist}")
    
    # Warn about geographic CRS
    if is_geographic and buffer_dist > 1:
        logger.warning(
            f"⚠️ Manual buffer with geographic CRS ({crs.authid()}) and distance {buffer_dist}°\n"
            f"   This is {buffer_dist * 111:.1f}km at equator - likely too large!"
        )
    
    # Create memory layer
    buffered_layer = create_memory_layer_for_buffer(layer)
    
    # Buffer all features
    geometries, valid_features, invalid_features, eroded_features = buffer_all_features(
        layer, buffer_dist, buffer_segments
    )
    
    # MODIFIED: Accept result even with 0 valid geometries (return empty layer instead of error)
    if not geometries:
        # Enhanced warning message for negative buffers
        if buffer_dist < 0:
            msg = (
                f"Le buffer négatif de {buffer_dist}m a complètement érodé toutes les géométries. "
                f"Réduisez la distance du buffer."
            )
            logger.warning(
                f"⚠️ Buffer négatif ({buffer_dist}m) a complètement érodé toutes les géométries. "
                f"Total: {feature_count}, Valides: {valid_features}, "
                f"Érodées: {eroded_features}, Invalides: {invalid_features}"
            )
            # Store warning for display in UI thread (thread safety)
            if warning_callback:
                warning_callback(msg)
        else:
            logger.warning(
                f"⚠️ Manual buffer produced no geometries. "
                f"Total: {feature_count}, Valid: {valid_features}, Invalid: {invalid_features}"
            )
        # Return empty layer instead of raising exception
        return buffered_layer
    
    # Dissolve and add to layer if we have geometries
    return dissolve_and_add_to_layer(geometries, buffered_layer, verify_spatial_index_fn)


def apply_qgis_buffer(
    layer: QgsVectorLayer,
    buffer_distance: 'QgsProperty | float',
    config: BufferConfig,
    convert_geometry_collection_fn: Optional[callable] = None
) -> QgsVectorLayer:
    """
    Apply buffer using QGIS processing algorithm.
    
    This is the preferred buffer method. Uses qgis:buffer algorithm with:
    - Automatic dissolve
    - Configurable buffer type (round/flat/square)
    - GeometryCollection to MultiPolygon conversion
    - Geographic CRS validation
    
    Args:
        layer: Input layer
        buffer_distance: QgsProperty (expression) or float value
        config: BufferConfig with buffer_type, buffer_segments, dissolve
        convert_geometry_collection_fn: Optional callback to convert result
            Signature: convert_geometry_collection_fn(layer) -> layer
            
    Returns:
        QgsVectorLayer: Buffered layer (temporary)
        
    Raises:
        Exception: If buffer operation fails or geographic CRS detected with large value
    """
    # CRITICAL DIAGNOSTIC: Check CRS type
    crs = layer.crs()
    is_geographic = crs.isGeographic()
    crs_units = crs.mapUnits()
    
    # Log layer info with enhanced CRS diagnostics
    logger.info(
        f"QGIS buffer: {layer.featureCount()} features, "
        f"CRS: {crs.authid()}, "
        f"Geometry type: {layer.geometryType()}, "
        f"wkbType: {layer.wkbType()}, "
        f"buffer_distance: {buffer_distance}"
    )
    logger.info(f"CRS diagnostics: isGeographic={is_geographic}, mapUnits={crs_units}")
    
    # CRITICAL: Check if CRS is geographic with large buffer value
    if is_geographic:
        # Evaluate buffer distance to get actual value
        eval_distance = buffer_distance
        if isinstance(buffer_distance, QgsProperty):
            features = list(layer.getFeatures())
            if features:
                context = QgsExpressionContext()
                context.setFeature(features[0])
                eval_distance = buffer_distance.value(context, 0)
        
        if eval_distance and float(eval_distance) > 1:
            logger.warning(
                f"⚠️ GEOGRAPHIC CRS DETECTED with large buffer value!\n"
                f"  CRS: {crs.authid()} (units: degrees)\n"
                f"  Buffer: {eval_distance} DEGREES (this is likely wrong!)\n"
                f"  → A buffer of {eval_distance}° = ~{float(eval_distance) * 111}km at equator\n"
                f"  → This will likely fail or create invalid geometries\n"
                f"  SOLUTION: Reproject layer to a projected CRS (e.g., EPSG:3857, EPSG:2154) first"
            )
            raise Exception(
                f"Cannot apply buffer: Geographic CRS detected ({crs.authid()}) with buffer value {eval_distance}. "
                f"Buffer units would be DEGREES, not meters. "
                f"Please reproject your layer to a projected coordinate system (e.g., EPSG:3857 Web Mercator, "
                f"or EPSG:2154 Lambert 93 for France) before applying buffer."
            )
    
    # Apply buffer with dissolve
    # CRITICAL: Configure to skip invalid geometries instead of failing
    alg_params = {
        'DISSOLVE': config.dissolve,
        'DISTANCE': buffer_distance,
        'END_CAP_STYLE': int(config.buffer_type),
        'INPUT': layer,
        'JOIN_STYLE': int(0),
        'MITER_LIMIT': float(2),
        'SEGMENTS': int(config.buffer_segments),
        'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
    }
    
    logger.debug(f"Calling processing.run('qgis:buffer') with params: {alg_params}")
    
    # CRITICAL: Configure processing context to skip invalid geometries
    context = QgsProcessingContext()
    context.setInvalidGeometryCheck(QgsFeatureRequest.GeometryNoCheck)
    feedback = QgsProcessingFeedback()
    
    result = processing.run(
        'qgis:buffer', 
        alg_params, 
        context=context, 
        feedback=feedback
    )
    buffered_layer = result['OUTPUT']
    
    # CRITICAL FIX: Convert GeometryCollection to MultiPolygon
    # This prevents "Impossible d'ajouter l'objet avec une géométrie de type 
    # GeometryCollection à une couche de type MultiPolygon" errors when using
    # the buffer result for spatial operations on typed GPKG layers
    if convert_geometry_collection_fn:
        buffered_layer = convert_geometry_collection_fn(buffered_layer)
    
    # Create spatial index
    processing.run('qgis:createspatialindex', {"INPUT": buffered_layer})
    
    return buffered_layer

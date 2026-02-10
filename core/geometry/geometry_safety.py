# -*- coding: utf-8 -*-
"""
Geometry Safety Module - Centralized GEOS-safe operations

EPIC-1 Migration: Created from orphan modules/geometry_safety.pyc
Date: January 2026

Provides GEOS-safe geometry operations to prevent crashes from:
- Invalid geometries
- Self-intersecting polygons
- Empty or null geometries
- Type mismatches

All functions validate input and provide safe fallbacks.

Usage:
    from ...core.geometry.geometry_safety import (        validate_geometry,
        safe_buffer,
        safe_unary_union,
        safe_collect_geometry
    )
"""

import logging
from typing import Optional, List

from qgis.core import (
    QgsGeometry,
    QgsWkbTypes,
    QgsVectorLayer,
    QgsFeature,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject
)

logger = logging.getLogger('FilterMate.Core.Geometry.Safety')


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_geometry(geom: Optional[QgsGeometry]) -> bool:
    """
    Validate that a geometry is usable for GEOS operations.

    Args:
        geom: QgsGeometry to validate

    Returns:
        bool: True if geometry is valid for use
    """
    if geom is None:
        return False
    if geom.isNull():
        return False
    if geom.isEmpty():
        return False
    return True


def validate_geometry_for_geos(geom: Optional[QgsGeometry]) -> bool:
    """
    Validate that a geometry is safe for GEOS operations (stricter).

    Args:
        geom: QgsGeometry to validate

    Returns:
        bool: True if geometry is GEOS-safe
    """
    if not validate_geometry(geom):
        return False
    try:
        return geom.isGeosValid()
    except Exception as e:
        logger.debug(f"Ignored in GEOS validity check: {e}")
        return False


def get_geometry_type_name(geom: Optional[QgsGeometry]) -> str:
    """
    Get a human-readable geometry type name.

    Args:
        geom: QgsGeometry to inspect

    Returns:
        str: Geometry type name or 'Unknown'
    """
    if not validate_geometry(geom):
        return 'Unknown'
    try:
        return QgsWkbTypes.displayString(geom.wkbType())
    except Exception as e:
        logger.debug(f"Ignored in geometry type name detection: {e}")
        return 'Unknown'


# =============================================================================
# SAFE CONVERSION FUNCTIONS
# =============================================================================

def safe_as_polygon(geom: Optional[QgsGeometry]) -> Optional[QgsGeometry]:
    """
    Safely convert geometry to polygon type.

    Args:
        geom: Geometry to convert

    Returns:
        QgsGeometry or None if conversion fails
    """
    if not validate_geometry(geom):
        return None

    try:
        # Already a polygon type
        if QgsWkbTypes.geometryType(geom.wkbType()) == QgsWkbTypes.PolygonGeometry:
            return geom

        # Try to convert
        converted = geom.buffer(0, 5)  # Small buffer often converts to polygon
        if validate_geometry(converted):
            return converted
        return None
    except Exception as e:
        logger.debug(f"safe_as_polygon failed: {e}")
        return None


def safe_as_geometry_collection(geom: Optional[QgsGeometry]) -> Optional[QgsGeometry]:
    """
    Safely wrap geometry in a GeometryCollection.

    Args:
        geom: Geometry to wrap

    Returns:
        QgsGeometry collection or None
    """
    if not validate_geometry(geom):
        return None

    try:
        # If already a collection, return as-is
        if QgsWkbTypes.isMultiType(geom.wkbType()):
            return geom
        # Create collection
        return QgsGeometry.collectGeometry([geom])
    except Exception as e:
        logger.debug(f"safe_as_geometry_collection failed: {e}")
        return geom


def safe_convert_to_multi_polygon(geom: Optional[QgsGeometry]) -> Optional[QgsGeometry]:
    """
    Safely convert geometry to MultiPolygon.

    Args:
        geom: Geometry to convert

    Returns:
        QgsGeometry MultiPolygon or None
    """
    if not validate_geometry(geom):
        return None

    try:
        geom_type = geom.wkbType()

        # Already MultiPolygon
        if geom_type in (QgsWkbTypes.MultiPolygon, QgsWkbTypes.MultiPolygonZ,
                         QgsWkbTypes.MultiPolygonM, QgsWkbTypes.MultiPolygonZM):
            return geom

        # Single Polygon -> MultiPolygon
        if QgsWkbTypes.geometryType(geom_type) == QgsWkbTypes.PolygonGeometry:
            return QgsGeometry.collectGeometry([geom])

        # GeometryCollection -> extract polygons
        if geom_type in (QgsWkbTypes.GeometryCollection, QgsWkbTypes.GeometryCollectionZ):
            polygons = extract_polygons_from_collection(geom)
            if polygons:
                return QgsGeometry.collectGeometry(polygons)

        return None
    except Exception as e:
        logger.debug(f"safe_convert_to_multi_polygon failed: {e}")
        return None


def extract_polygons_from_collection(geom: Optional[QgsGeometry]) -> List[QgsGeometry]:
    """
    Extract all polygon geometries from a GeometryCollection.

    Args:
        geom: GeometryCollection to extract from

    Returns:
        List of polygon geometries
    """
    if not validate_geometry(geom):
        return []

    polygons = []
    try:
        for part in geom.asGeometryCollection():
            if validate_geometry(part):
                part_type = QgsWkbTypes.geometryType(part.wkbType())
                if part_type == QgsWkbTypes.PolygonGeometry:
                    polygons.append(part)
    except Exception as e:
        logger.debug(f"extract_polygons_from_collection failed: {e}")

    return polygons


# =============================================================================
# SAFE GEOMETRIC OPERATIONS
# =============================================================================

def safe_buffer(
    geom: Optional[QgsGeometry],
    distance: float,
    segments: int = 5
) -> Optional[QgsGeometry]:
    """
    Safely create a buffer around geometry.

    Args:
        geom: Geometry to buffer
        distance: Buffer distance (can be negative)
        segments: Number of segments for round corners

    Returns:
        QgsGeometry buffer or None
    """
    if not validate_geometry(geom):
        logger.warning("safe_buffer: Invalid input geometry")
        return None

    if distance == 0:
        return geom

    try:
        result = geom.buffer(distance, segments)
        if validate_geometry(result):
            return result
        logger.warning("safe_buffer: Buffer produced invalid result")
        return None
    except Exception as e:
        logger.error(f"safe_buffer failed: {e}")
        return None


def safe_buffer_metric(
    geom: Optional[QgsGeometry],
    distance_meters: float,
    source_crs: QgsCoordinateReferenceSystem,
    segments: int = 5
) -> Optional[QgsGeometry]:
    """
    Create buffer with metric distance, handling CRS conversion.

    Args:
        geom: Geometry to buffer
        distance_meters: Buffer distance in meters
        source_crs: Source CRS of geometry
        segments: Number of segments for round corners

    Returns:
        QgsGeometry buffer or None
    """
    if not validate_geometry(geom):
        return None

    try:
        # Check if CRS is metric
        if source_crs.mapUnits() in (0, 1):  # Meters or kilometers
            return safe_buffer(geom, distance_meters, segments)

        # Need to project to metric CRS
        # Use Web Mercator as default metric CRS
        metric_crs = QgsCoordinateReferenceSystem("EPSG:3857")
        transform = QgsCoordinateTransform(source_crs, metric_crs, QgsProject.instance())

        # Transform, buffer, transform back
        projected_geom = QgsGeometry(geom)
        projected_geom.transform(transform)

        buffered = safe_buffer(projected_geom, distance_meters, segments)
        if buffered is None:
            return None

        # Transform back
        reverse_transform = QgsCoordinateTransform(metric_crs, source_crs, QgsProject.instance())
        buffered.transform(reverse_transform)

        return buffered
    except Exception as e:
        logger.error(f"safe_buffer_metric failed: {e}")
        return None


def safe_buffer_with_crs_check(
    geom: Optional[QgsGeometry],
    distance: float,
    crs: Optional[QgsCoordinateReferenceSystem] = None,
    segments: int = 5
) -> Optional[QgsGeometry]:
    """
    Create buffer with automatic CRS handling.

    If CRS is geographic (degrees), uses metric conversion.

    Args:
        geom: Geometry to buffer
        distance: Buffer distance (meters if geographic, else CRS units)
        crs: Coordinate reference system
        segments: Number of segments

    Returns:
        QgsGeometry buffer or None
    """
    if crs is not None and crs.isGeographic():
        return safe_buffer_metric(geom, distance, crs, segments)
    return safe_buffer(geom, distance, segments)


def safe_unary_union(geometries: List[QgsGeometry]) -> Optional[QgsGeometry]:
    """
    Safely union multiple geometries.

    Args:
        geometries: List of geometries to union

    Returns:
        QgsGeometry union or None
    """
    if not geometries:
        return None

    valid_geoms = [g for g in geometries if validate_geometry(g)]
    if not valid_geoms:
        return None

    try:
        if len(valid_geoms) == 1:
            return valid_geoms[0]

        result = valid_geoms[0]
        for geom in valid_geoms[1:]:
            result = result.combine(geom)
            if not validate_geometry(result):
                logger.warning("safe_unary_union: Intermediate result invalid")
                return None

        return result
    except Exception as e:
        logger.error(f"safe_unary_union failed: {e}")
        return None


def safe_collect_geometry(geometries: List[QgsGeometry]) -> Optional[QgsGeometry]:
    """
    Safely collect geometries into a GeometryCollection.

    Args:
        geometries: List of geometries to collect

    Returns:
        QgsGeometry collection or None
    """
    if not geometries:
        return None

    valid_geoms = [g for g in geometries if validate_geometry(g)]
    if not valid_geoms:
        return None

    try:
        return QgsGeometry.collectGeometry(valid_geoms)
    except Exception as e:
        logger.error(f"safe_collect_geometry failed: {e}")
        return None


def repair_geometry(geom: Optional[QgsGeometry]) -> Optional[QgsGeometry]:
    """
    Attempt to repair an invalid geometry.

    Tries multiple repair strategies:
    1. makeValid()
    2. buffer(0)
    3. simplify + makeValid

    Args:
        geom: Geometry to repair

    Returns:
        QgsGeometry repaired or None
    """
    if geom is None:
        return None

    # Already valid?
    if validate_geometry_for_geos(geom):
        return geom

    # Strategy 1: makeValid
    try:
        repaired = geom.makeValid()
        if validate_geometry_for_geos(repaired):
            return repaired
    except Exception as e:
        logger.debug(f"Ignored in repair_geometry makeValid: {e}")

    # Strategy 2: buffer(0)
    try:
        buffered = geom.buffer(0, 5)
        if validate_geometry_for_geos(buffered):
            return buffered
    except Exception as e:
        logger.debug(f"Ignored in repair_geometry buffer(0): {e}")

    # Strategy 3: simplify + makeValid
    try:
        simplified = geom.simplify(0.0001)
        if simplified:
            repaired = simplified.makeValid()
            if validate_geometry_for_geos(repaired):
                return repaired
    except Exception as e:
        logger.debug(f"Ignored in repair_geometry simplify+makeValid: {e}")

    return None


def create_geos_safe_layer(
    layer: QgsVectorLayer,
    name_suffix: str = "_safe"
) -> Optional[QgsVectorLayer]:
    """
    Create a memory layer with repaired geometries.

    Args:
        layer: Source layer with potentially invalid geometries
        name_suffix: Suffix for the new layer name

    Returns:
        QgsVectorLayer with repaired geometries or None
    """
    if layer is None or not layer.isValid():
        return None

    try:
        # Create memory layer
        geom_type = QgsWkbTypes.displayString(layer.wkbType())
        crs = layer.crs().authid()
        uri = f"{geom_type}?crs={crs}"

        safe_layer = QgsVectorLayer(uri, f"{layer.name()}{name_suffix}", "memory")
        if not safe_layer.isValid():
            return None

        # Copy fields
        safe_layer.startEditing()
        safe_layer.dataProvider().addAttributes(layer.fields().toList())
        safe_layer.updateFields()

        # Copy features with repaired geometries
        for feature in layer.getFeatures():
            new_feat = QgsFeature(safe_layer.fields())
            new_feat.setAttributes(feature.attributes())

            geom = feature.geometry()
            if validate_geometry(geom):
                repaired = repair_geometry(geom) if not validate_geometry_for_geos(geom) else geom
                if repaired:
                    new_feat.setGeometry(repaired)
                    safe_layer.addFeature(new_feat)

        safe_layer.commitChanges()

        # FIX v2.9.44: CRITICAL - Add layer to project registry BEFORE returning
        # The layer can be garbage collected by Qt's C++ GC during the return from this function.
        # Adding it to the project registry (with addToLegend=False) creates a strong C++ reference
        # that survives the return. The caller is responsible for removing it when done.
        # FIX v4.1.1: Register layer for cleanup after filtering completes
        try:
            from qgis.core import QgsProject
            QgsProject.instance().addMapLayer(safe_layer, False)  # addToLegend=False
            logger.debug(f"create_geos_safe_layer: Added '{safe_layer.name()}' to project registry for GC protection")

            # Register for cleanup after filtering completes
            try:
                from ..ports import get_backend_services
                _backend_services = get_backend_services()
                _backend_services.register_ogr_temp_layer(safe_layer.id())
            except ImportError:
                logger.debug("Could not import register_temp_layer - cleanup must be manual")
        except Exception as add_err:
            logger.warning(f"create_geos_safe_layer: Failed to add layer to project: {add_err}")

        return safe_layer

    except Exception as e:
        logger.error(f"create_geos_safe_layer failed: {e}")
        return None


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Validation
    'validate_geometry',
    'validate_geometry_for_geos',
    'get_geometry_type_name',
    # Conversion
    'safe_as_polygon',
    'safe_as_geometry_collection',
    'safe_convert_to_multi_polygon',
    'extract_polygons_from_collection',
    # Operations
    'safe_buffer',
    'safe_buffer_metric',
    'safe_buffer_with_crs_check',
    'safe_unary_union',
    'safe_collect_geometry',
    'repair_geometry',
    'create_geos_safe_layer',
]

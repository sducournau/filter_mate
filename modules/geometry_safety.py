# -*- coding: utf-8 -*-
"""
Geometry Safety Module - FilterMate v2.3.9

Provides safe wrappers for QGIS geometry operations to prevent
access violations and crashes on certain machines.

CRITICAL: These functions handle edge cases where GEOS/QGIS can crash:
- Invalid geometries
- Null/empty geometries  
- Type mismatches (calling asPolygon on a Point, etc.)
- Corrupted geometry data

Usage:
    from modules.geometry_safety import (
        safe_as_geometry_collection,
        safe_as_polygon,
        safe_buffer,
        safe_unary_union,
        safe_collect_geometry,
        validate_geometry
    )

Author: FilterMate Team
Date: December 2025
"""

import logging
from typing import List, Optional, Any

from qgis.core import (
    QgsGeometry,
    QgsWkbTypes,
    QgsFeature
)

logger = logging.getLogger(__name__)


# =============================================================================
# Geometry Validation
# =============================================================================

def validate_geometry(geom: Optional[QgsGeometry]) -> bool:
    """
    Check if a geometry is safe to use for operations.
    
    Args:
        geom: QgsGeometry to validate
        
    Returns:
        bool: True if geometry is safe to use, False otherwise
    """
    if geom is None:
        return False
    
    try:
        if geom.isNull():
            return False
        if geom.isEmpty():
            return False
        # Check that wkbType is valid
        wkb_type = geom.wkbType()
        if wkb_type == QgsWkbTypes.Unknown or wkb_type == QgsWkbTypes.NoGeometry:
            return False
        return True
    except Exception as e:
        logger.debug(f"validate_geometry exception: {e}")
        return False


def validate_geometry_for_geos(geom: Optional[QgsGeometry], strict: bool = False) -> bool:
    """
    Deep validation to check if geometry is safe for GEOS operations.
    
    This is more thorough than validate_geometry() and optionally tests if 
    the geometry can survive a buffer(0) operation without crashing GEOS.
    
    CRITICAL: This function catches geometries that can crash GEOS at C++ level.
    
    Args:
        geom: QgsGeometry to validate
        strict: If True, also tests buffer(0) (more thorough but may reject valid geometries)
        
    Returns:
        bool: True if geometry is safe for GEOS operations, False otherwise
    """
    if not validate_geometry(geom):
        return False
    
    try:
        # Test 1: Check for NaN/Inf in coordinates (can crash GEOS)
        try:
            import math
            bbox = geom.boundingBox()
            coords = [bbox.xMinimum(), bbox.xMaximum(), bbox.yMinimum(), bbox.yMaximum()]
            for coord in coords:
                if math.isnan(coord) or math.isinf(coord):
                    logger.debug("validate_geometry_for_geos: NaN/Inf detected in bounding box")
                    return False
        except Exception:
            # If bounding box fails, geometry is likely invalid
            return False
        
        # Test 2: isGeosValid() - basic GEOS validation
        # Note: Some geometries fail isGeosValid() but still work in selectbylocation
        try:
            if not geom.isGeosValid():
                # Try makeValid() as a repair attempt
                repaired = geom.makeValid()
                if repaired and not repaired.isNull() and repaired.isGeosValid():
                    # Geometry can be repaired, so it's usable
                    return True
                # If strict mode, reject; otherwise allow (selectbylocation might handle it)
                if strict:
                    logger.debug("validate_geometry_for_geos: isGeosValid() returned False")
                    return False
        except Exception:
            pass  # isGeosValid() failed, but geometry might still work
        
        # Test 3 (strict only): Try buffer(0) - catches subtle corruptions
        # This test is too aggressive for normal use as it rejects many valid geometries
        if strict:
            try:
                buffered = geom.buffer(0, 1)  # Use minimal segments for speed
                if buffered is None or buffered.isNull() or buffered.isEmpty():
                    logger.debug("validate_geometry_for_geos: buffer(0) returned empty/null")
                    return False
            except Exception as buffer_error:
                logger.debug(f"validate_geometry_for_geos: buffer(0) failed: {buffer_error}")
                return False
        
        return True
        
    except Exception as e:
        logger.debug(f"validate_geometry_for_geos exception: {e}")
        return False


def is_geometry_collection_type(geom: QgsGeometry) -> bool:
    """
    Check if geometry is a collection type (GeometryCollection or Multi*).
    
    Args:
        geom: QgsGeometry to check
        
    Returns:
        bool: True if geometry is a collection type
    """
    if not validate_geometry(geom):
        return False
    
    try:
        wkb_type = geom.wkbType()
        type_name = QgsWkbTypes.displayString(wkb_type)
        return 'GeometryCollection' in type_name or 'Multi' in type_name
    except Exception:
        return False


def get_geometry_type_name(geom: Optional[QgsGeometry]) -> str:
    """
    Safely get geometry type name.
    
    Args:
        geom: QgsGeometry
        
    Returns:
        str: Type name or "Unknown"
    """
    if not validate_geometry(geom):
        return "Unknown"
    
    try:
        return QgsWkbTypes.displayString(geom.wkbType())
    except Exception:
        return "Unknown"


# =============================================================================
# Safe Geometry Collection Operations
# =============================================================================

def safe_as_geometry_collection(geom: Optional[QgsGeometry]) -> List[QgsGeometry]:
    """
    Safely extract geometry collection parts.
    
    CRITICAL: Prevents access violations when calling asGeometryCollection()
    on invalid or non-collection geometries.
    
    Args:
        geom: QgsGeometry (potentially a collection)
        
    Returns:
        list: List of QgsGeometry parts, or empty list on failure
    """
    if not validate_geometry(geom):
        return []
    
    try:
        wkb_type = geom.wkbType()
        type_name = QgsWkbTypes.displayString(wkb_type)
        
        # Only call asGeometryCollection on actual collections
        if 'GeometryCollection' in type_name or 'Multi' in type_name:
            parts = geom.asGeometryCollection()
            if parts:
                # Filter out invalid parts
                valid_parts = []
                for p in parts:
                    if p is not None:
                        # Wrap in QgsGeometry if needed
                        if isinstance(p, QgsGeometry):
                            if not p.isEmpty() and not p.isNull():
                                valid_parts.append(p)
                        else:
                            # May be a QgsAbstractGeometry
                            wrapped = QgsGeometry(p)
                            if not wrapped.isEmpty() and not wrapped.isNull():
                                valid_parts.append(wrapped)
                return valid_parts
            return []
        else:
            # Single geometry - return as list with a copy
            geom_copy = QgsGeometry(geom)
            return [geom_copy] if not geom_copy.isEmpty() else []
            
    except Exception as e:
        logger.error(f"safe_as_geometry_collection failed: {e}")
        return []


# =============================================================================
# Safe Polygon Operations
# =============================================================================

def safe_as_polygon(geom: Optional[QgsGeometry]) -> Optional[List]:
    """
    Safely convert geometry to polygon data (list of rings).
    
    CRITICAL: Prevents access violations when calling asPolygon()
    on non-polygon geometries.
    
    Args:
        geom: QgsGeometry (should be a Polygon type)
        
    Returns:
        list or None: Polygon ring data, or None if not a polygon
    """
    if not validate_geometry(geom):
        return None
    
    try:
        wkb_type = geom.wkbType()
        
        # Check for exact polygon types (including Z, M, ZM variants)
        polygon_types = (
            QgsWkbTypes.Polygon,
            QgsWkbTypes.Polygon25D,
            QgsWkbTypes.PolygonZ,
            QgsWkbTypes.PolygonM,
            QgsWkbTypes.PolygonZM
        )
        
        if wkb_type in polygon_types:
            result = geom.asPolygon()
            if result and len(result) > 0:
                return result
        
        # Also check by type name as fallback
        type_name = QgsWkbTypes.displayString(wkb_type)
        if 'Polygon' in type_name and 'Multi' not in type_name:
            result = geom.asPolygon()
            if result and len(result) > 0:
                return result
                
    except Exception as e:
        logger.debug(f"safe_as_polygon failed: {e}")
    
    return None


def safe_as_multi_polygon(geom: Optional[QgsGeometry]) -> Optional[List]:
    """
    Safely convert geometry to multi-polygon data.
    
    Args:
        geom: QgsGeometry (should be a MultiPolygon type)
        
    Returns:
        list or None: MultiPolygon data, or None if not a MultiPolygon
    """
    if not validate_geometry(geom):
        return None
    
    try:
        wkb_type = geom.wkbType()
        
        # Check for MultiPolygon types
        multi_polygon_types = (
            QgsWkbTypes.MultiPolygon,
            QgsWkbTypes.MultiPolygon25D,
            QgsWkbTypes.MultiPolygonZ,
            QgsWkbTypes.MultiPolygonM,
            QgsWkbTypes.MultiPolygonZM
        )
        
        if wkb_type in multi_polygon_types:
            result = geom.asMultiPolygon()
            if result and len(result) > 0:
                return result
                
        # Also check by type name
        type_name = QgsWkbTypes.displayString(wkb_type)
        if 'MultiPolygon' in type_name:
            result = geom.asMultiPolygon()
            if result and len(result) > 0:
                return result
                
    except Exception as e:
        logger.debug(f"safe_as_multi_polygon failed: {e}")
    
    return None


# =============================================================================
# Safe Geometry Operations
# =============================================================================

def safe_buffer(
    geom: Optional[QgsGeometry], 
    distance: float, 
    segments: int = 5
) -> Optional[QgsGeometry]:
    """
    Safe buffer operation with validation and repair attempts.
    
    CRITICAL: Prevents GEOS crashes when buffering invalid geometries.
    
    NOTE: Negative buffers (erosion) can produce empty geometries if the buffer 
    distance is larger than the feature width. This is expected behavior - the 
    feature completely erodes away.
    
    Args:
        geom: QgsGeometry to buffer
        distance: Buffer distance (can be negative for erosion)
        segments: Number of segments for curves (default 5)
        
    Returns:
        QgsGeometry or None: Buffered geometry, or None on failure or complete erosion
    """
    if not validate_geometry(geom):
        logger.debug("safe_buffer: Invalid input geometry")
        return None
    
    try:
        distance = float(distance)
    except (ValueError, TypeError):
        logger.error(f"safe_buffer: Invalid distance value: {distance}")
        return None
    
    # Log negative buffer (erosion) operations
    if distance < 0:
        logger.debug(f"safe_buffer: Applying negative buffer (erosion) of {distance}m")
    
    working_geom = geom
    
    # Try to repair if invalid
    try:
        if not geom.isGeosValid():
            logger.debug("safe_buffer: Input geometry invalid, attempting repair")
            repaired = geom.makeValid()
            if repaired and not repaired.isEmpty() and not repaired.isNull():
                working_geom = repaired
            else:
                # Try buffer(0) trick
                fixed = geom.buffer(0, segments)
                if fixed and not fixed.isEmpty() and fixed.isGeosValid():
                    working_geom = fixed
                else:
                    logger.warning("safe_buffer: Could not repair invalid geometry")
                    return None
    except Exception as e:
        logger.debug(f"safe_buffer: Repair attempt failed: {e}")
        # Continue with original geometry
    
    # Apply buffer
    try:
        result = working_geom.buffer(distance, segments)
        if result and not result.isEmpty() and not result.isNull():
            return result
        else:
            # Empty geometry can be normal for negative buffers (complete erosion)
            if distance < 0:
                logger.debug(f"safe_buffer: Negative buffer ({distance}m) produced empty geometry (complete erosion)")
            else:
                logger.debug("safe_buffer: Buffer produced empty/null geometry")
            return None
    except Exception as e:
        logger.error(f"safe_buffer: Buffer operation failed: {e}")
        return None


def safe_unary_union(geometries: List[QgsGeometry]) -> Optional[QgsGeometry]:
    """
    Safe unaryUnion operation with validation.
    
    CRITICAL: Prevents crashes when unifying invalid or mixed geometries.
    
    Args:
        geometries: List of QgsGeometry to unify
        
    Returns:
        QgsGeometry or None: Unified geometry, or None on failure
    """
    if not geometries:
        return None
    
    # Filter and validate geometries
    valid_geoms = []
    for g in geometries:
        if not validate_geometry(g):
            continue
        
        try:
            # Try to repair if invalid
            if not g.isGeosValid():
                repaired = g.makeValid()
                if repaired and not repaired.isEmpty() and not repaired.isNull():
                    valid_geoms.append(repaired)
                    continue
                # Try buffer(0) trick
                fixed = g.buffer(0, 5)
                if fixed and not fixed.isEmpty() and fixed.isGeosValid():
                    valid_geoms.append(fixed)
                    continue
                # Skip this geometry
                logger.debug("safe_unary_union: Skipping unrepairable geometry")
            else:
                valid_geoms.append(g)
        except Exception as e:
            logger.debug(f"safe_unary_union: Error processing geometry: {e}")
            continue
    
    if not valid_geoms:
        logger.warning("safe_unary_union: No valid geometries after filtering")
        return None
    
    # Perform unaryUnion
    try:
        result = QgsGeometry.unaryUnion(valid_geoms)
        if result and not result.isEmpty() and not result.isNull():
            return result
        else:
            logger.debug("safe_unary_union: unaryUnion produced empty result")
            return None
    except Exception as e:
        logger.error(f"safe_unary_union: unaryUnion failed: {e}")
        
        # Fallback: try combining one by one
        try:
            if len(valid_geoms) == 1:
                return valid_geoms[0]
            
            combined = valid_geoms[0]
            for g in valid_geoms[1:]:
                try:
                    combined = combined.combine(g)
                except Exception:
                    continue
            
            if combined and not combined.isEmpty():
                return combined
        except Exception as e2:
            logger.error(f"safe_unary_union: Fallback combine failed: {e2}")
        
        return None


def safe_collect_geometry(geometries: List[QgsGeometry]) -> Optional[QgsGeometry]:
    """
    Safe collectGeometry operation with validation.
    
    CRITICAL: Prevents crashes when collecting invalid geometries.
    
    Args:
        geometries: List of QgsGeometry to collect
        
    Returns:
        QgsGeometry or None: Collected geometry, or None on failure
    """
    if not geometries:
        return None
    
    # Filter valid geometries
    valid_geoms = [g for g in geometries if validate_geometry(g)]
    
    if not valid_geoms:
        logger.warning("safe_collect_geometry: No valid geometries to collect")
        return None
    
    try:
        result = QgsGeometry.collectGeometry(valid_geoms)
        if result and not result.isEmpty() and not result.isNull():
            return result
        else:
            logger.debug("safe_collect_geometry: collectGeometry produced empty result")
            return None
    except Exception as e:
        logger.error(f"safe_collect_geometry: collectGeometry failed: {e}")
        return None


# =============================================================================
# Geometry Type Conversion
# =============================================================================

def safe_convert_to_multi_polygon(geom: Optional[QgsGeometry]) -> Optional[QgsGeometry]:
    """
    Safely convert a geometry to MultiPolygon.
    
    Handles:
    - Polygon -> MultiPolygon
    - MultiPolygon -> MultiPolygon (no-op)
    - GeometryCollection -> Extract polygons -> MultiPolygon
    
    Args:
        geom: QgsGeometry to convert
        
    Returns:
        QgsGeometry or None: MultiPolygon geometry, or None on failure
    """
    if not validate_geometry(geom):
        return None
    
    try:
        type_name = get_geometry_type_name(geom)
        
        # Already MultiPolygon
        if 'MultiPolygon' in type_name:
            return geom
        
        # Single Polygon -> MultiPolygon
        if 'Polygon' in type_name and 'Multi' not in type_name:
            poly_data = safe_as_polygon(geom)
            if poly_data:
                return QgsGeometry.fromMultiPolygonXY([poly_data])
            return None
        
        # GeometryCollection -> Extract polygons
        if 'GeometryCollection' in type_name:
            polygon_parts = []
            parts = safe_as_geometry_collection(geom)
            
            for part in parts:
                part_type = get_geometry_type_name(part)
                if 'Polygon' in part_type and 'Multi' not in part_type:
                    poly_data = safe_as_polygon(part)
                    if poly_data:
                        polygon_parts.append(poly_data)
                elif 'MultiPolygon' in part_type:
                    # Extract each polygon from MultiPolygon
                    multi_data = safe_as_multi_polygon(part)
                    if multi_data:
                        polygon_parts.extend(multi_data)
            
            if polygon_parts:
                return QgsGeometry.fromMultiPolygonXY(polygon_parts)
            return None
        
        # Try convertToType as last resort
        converted = geom.convertToType(QgsWkbTypes.PolygonGeometry, True)
        if converted and not converted.isEmpty():
            return converted
            
    except Exception as e:
        logger.error(f"safe_convert_to_multi_polygon failed: {e}")
    
    return None


def extract_polygons_from_collection(geom: Optional[QgsGeometry]) -> List[QgsGeometry]:
    """
    Extract all polygon geometries from a GeometryCollection.
    
    Args:
        geom: QgsGeometry (potentially a collection)
        
    Returns:
        list: List of polygon QgsGeometry objects
    """
    if not validate_geometry(geom):
        return []
    
    polygons = []
    
    try:
        type_name = get_geometry_type_name(geom)
        
        # If already a simple polygon
        if 'Polygon' in type_name and 'Multi' not in type_name and 'Collection' not in type_name:
            return [geom]
        
        # Extract from collection
        parts = safe_as_geometry_collection(geom)
        for part in parts:
            part_type = get_geometry_type_name(part)
            
            if 'Polygon' in part_type and 'Multi' not in part_type:
                polygons.append(part)
            elif 'MultiPolygon' in part_type or 'GeometryCollection' in part_type:
                # Recursively extract
                polygons.extend(extract_polygons_from_collection(part))
                
    except Exception as e:
        logger.error(f"extract_polygons_from_collection failed: {e}")
    
    return polygons


# =============================================================================
# Geometry Repair
# =============================================================================

def repair_geometry(geom: Optional[QgsGeometry]) -> Optional[QgsGeometry]:
    """
    Attempt to repair an invalid geometry using multiple strategies.
    
    Strategies tried in order:
    1. makeValid() - Standard OGC repair
    2. buffer(0) - Often fixes self-intersections
    3. simplify() - Removes problematic vertices
    
    Args:
        geom: QgsGeometry to repair
        
    Returns:
        QgsGeometry or None: Repaired geometry, or None if repair failed
    """
    if geom is None:
        return None
    
    # Check if already valid
    try:
        if geom.isGeosValid() and not geom.isEmpty() and not geom.isNull():
            return geom
    except Exception:
        pass
    
    # Strategy 1: makeValid
    try:
        repaired = geom.makeValid()
        if repaired and not repaired.isNull() and not repaired.isEmpty() and repaired.isGeosValid():
            logger.debug("repair_geometry: Success with makeValid()")
            return repaired
    except Exception as e:
        logger.debug(f"repair_geometry: makeValid failed: {e}")
    
    # Strategy 2: buffer(0)
    try:
        buffered = geom.buffer(0, 5)
        if buffered and not buffered.isNull() and not buffered.isEmpty() and buffered.isGeosValid():
            logger.debug("repair_geometry: Success with buffer(0)")
            return buffered
    except Exception as e:
        logger.debug(f"repair_geometry: buffer(0) failed: {e}")
    
    # Strategy 3: simplify with small tolerance
    try:
        simplified = geom.simplify(0.0001)
        if simplified and not simplified.isNull() and not simplified.isEmpty() and simplified.isGeosValid():
            logger.debug("repair_geometry: Success with simplify()")
            return simplified
    except Exception as e:
        logger.debug(f"repair_geometry: simplify failed: {e}")
    
    logger.warning("repair_geometry: All repair strategies failed")
    return None


# =============================================================================
# Safe Layer Creation for GEOS Operations
# =============================================================================

def create_geos_safe_layer(layer, layer_name_suffix: str = "_geos_safe") -> Optional[any]:
    """
    Create a memory layer containing only GEOS-safe geometries.
    
    CRITICAL FIX for crashes during selectbylocation:
    This function filters out geometries that would cause GEOS to crash
    at the C++ level (which cannot be caught by Python try/except).
    
    Process:
    1. Validate each geometry with validate_geometry_for_geos()
    2. Try to repair geometries that fail validation with makeValid()
    3. Use multi-level fallback: strict -> normal -> repaired -> original
    4. Create new memory layer with safe geometries
    
    Args:
        layer: QgsVectorLayer to filter
        layer_name_suffix: Suffix for the new layer name
        
    Returns:
        QgsVectorLayer: Memory layer with GEOS-safe geometries, or original layer as last resort
    """
    from qgis.core import (
        QgsVectorLayer, QgsMemoryProviderUtils, QgsFeature
    )
    
    if layer is None:
        logger.error("create_geos_safe_layer: Input layer is None")
        return None
    
    if not isinstance(layer, QgsVectorLayer):
        logger.error(f"create_geos_safe_layer: Input is not a QgsVectorLayer: {type(layer)}")
        return None
    
    if not layer.isValid():
        logger.error(f"create_geos_safe_layer: Input layer is not valid")
        return None
    
    feature_count = layer.featureCount()
    if feature_count == 0:
        logger.warning("create_geos_safe_layer: Input layer has no features")
        return None
    
    try:
        # Create output memory layer
        safe_layer = QgsMemoryProviderUtils.createMemoryLayer(
            f"{layer.name()}{layer_name_suffix}",
            layer.fields(),
            layer.wkbType(),
            layer.crs()
        )
        
        if not safe_layer or not safe_layer.isValid():
            logger.error("create_geos_safe_layer: Failed to create memory layer")
            # Fallback: return original layer
            logger.warning("create_geos_safe_layer: Falling back to original layer")
            return layer
        
        data_provider = safe_layer.dataProvider()
        safe_features = []
        repaired_features = []  # Features that needed makeValid()
        skipped_count = 0
        repaired_count = 0
        
        for feature in layer.getFeatures():
            geom = feature.geometry()
            
            # Test 1: Basic validation - skip truly invalid geometries
            if not validate_geometry(geom):
                skipped_count += 1
                continue
            
            # Test 2: Normal GEOS validation (not strict)
            if validate_geometry_for_geos(geom, strict=False):
                # Geometry passes normal validation
                new_feature = QgsFeature(layer.fields())
                new_feature.setGeometry(geom)
                new_feature.setAttributes(feature.attributes())
                safe_features.append(new_feature)
            else:
                # Try makeValid() repair
                try:
                    repaired = geom.makeValid()
                    if repaired and not repaired.isNull() and not repaired.isEmpty():
                        new_feature = QgsFeature(layer.fields())
                        new_feature.setGeometry(repaired)
                        new_feature.setAttributes(feature.attributes())
                        repaired_features.append(new_feature)
                        repaired_count += 1
                    else:
                        # makeValid failed, but include original geometry as fallback
                        # selectbylocation might handle it
                        new_feature = QgsFeature(layer.fields())
                        new_feature.setGeometry(geom)
                        new_feature.setAttributes(feature.attributes())
                        repaired_features.append(new_feature)
                        logger.debug(f"create_geos_safe_layer: Including geometry despite validation failure (fid={feature.id()})")
                except Exception as repair_error:
                    # Include original geometry as last resort
                    new_feature = QgsFeature(layer.fields())
                    new_feature.setGeometry(geom)
                    new_feature.setAttributes(feature.attributes())
                    repaired_features.append(new_feature)
                    logger.debug(f"create_geos_safe_layer: Repair failed, including original (fid={feature.id()}): {repair_error}")
        
        # Combine safe and repaired features
        all_features = safe_features + repaired_features
        
        if not all_features:
            # No features at all - this shouldn't happen but handle gracefully
            logger.warning(f"create_geos_safe_layer: No features could be processed (all {feature_count} skipped)")
            logger.warning("create_geos_safe_layer: Falling back to original layer")
            return layer
        
        # Add features to layer
        success, _ = data_provider.addFeatures(all_features)
        if not success:
            logger.error("create_geos_safe_layer: Failed to add features to memory layer")
            logger.warning("create_geos_safe_layer: Falling back to original layer")
            return layer
        
        safe_layer.updateExtents()
        
        # Create spatial index to improve performance
        try:
            from qgis.core import QgsSpatialIndex
            data_provider.createSpatialIndex()
            logger.debug("create_geos_safe_layer: Spatial index created successfully")
        except Exception as index_error:
            logger.debug(f"create_geos_safe_layer: Could not create spatial index: {index_error}")
        
        if repaired_count > 0 or skipped_count > 0:
            logger.info(f"create_geos_safe_layer: Created layer with {len(all_features)}/{feature_count} features "
                       f"({skipped_count} skipped, {repaired_count} repaired)")
        else:
            logger.debug(f"create_geos_safe_layer: All {feature_count} geometries passed validation")
        
        return safe_layer
        
    except Exception as e:
        logger.error(f"create_geos_safe_layer: Exception: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        # Ultimate fallback: return original layer
        logger.warning("create_geos_safe_layer: Exception occurred, falling back to original layer")
        return layer

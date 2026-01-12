"""
Geometry Repair Module

EPIC-1 Phase E2: Extracted from modules/tasks/filter_task.py

Provides geometry validation and repair operations:
- Multiple repair strategies (makeValid, buffer(0), simplify, etc.)
- Layer-wide geometry validation
- Invalid geometry reporting

Repair strategies (in order):
1. makeValid() - GEOS standard repair
2. buffer(0) - Fixes self-intersections
3. simplify + makeValid - For complex geometries
4. convexHull - Preserves area, simplifies shape
5. boundingBox - Last resort for filtering

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase E2)
"""

import logging
from typing import Optional

from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsVectorLayer,
    QgsWkbTypes
)

# Import geometry safety utilities (migrated from modules.geometry_safety)
from .geometry_safety import (
    validate_geometry,
    get_geometry_type_name
)

logger = logging.getLogger('FilterMate.Core.Geometry.Repair')


def aggressive_geometry_repair(geom: QgsGeometry) -> Optional[QgsGeometry]:
    """
    Try multiple repair strategies for a geometry.
    
    Attempts 5 different repair strategies in order of preference:
    1. makeValid() - Standard GEOS repair
    2. buffer(0) - Often fixes self-intersections
    3. simplify + makeValid - For complex geometries
    4. convexHull - Preserves area but simplifies shape
    5. boundingBox - Last resort for filtering purposes
    
    Args:
        geom: QgsGeometry to repair
        
    Returns:
        QgsGeometry or None: Repaired geometry if successful, None otherwise
    """
    # Log initial state
    logger.debug(
        f"🔧 Attempting geometry repair: wkbType={geom.wkbType()}, "
        f"isEmpty={geom.isEmpty()}, isValid={geom.isGeosValid()}"
    )
    
    # Strategy 1: Standard makeValid()
    try:
        repaired = geom.makeValid()
        if repaired and not repaired.isNull() and not repaired.isEmpty() and repaired.isGeosValid():
            logger.info("✓ Repaired with makeValid()")
            return repaired
        else:
            status = (
                f"null={repaired.isNull() if repaired else 'None'}, "
                f"empty={repaired.isEmpty() if repaired and not repaired.isNull() else 'N/A'}, "
                f"valid={repaired.isGeosValid() if repaired and not repaired.isNull() else 'N/A'}"
            )
            logger.debug(f"makeValid() produced unusable geometry: {status}")
    except Exception as e:
        logger.debug(f"makeValid() failed with exception: {e}")
    
    # Strategy 2: Buffer(0) trick - often fixes self-intersections
    try:
        buffered = geom.buffer(0, 5)
        if buffered and not buffered.isNull() and not buffered.isEmpty() and buffered.isGeosValid():
            logger.info("✓ Repaired with buffer(0) trick")
            return buffered
        else:
            status = (
                f"null={buffered.isNull() if buffered else 'None'}, "
                f"empty={buffered.isEmpty() if buffered and not buffered.isNull() else 'N/A'}"
            )
            logger.debug(f"buffer(0) produced unusable geometry: {status}")
    except Exception as e:
        logger.debug(f"buffer(0) failed with exception: {e}")
    
    # Strategy 3: Simplify then makeValid
    try:
        simplified = geom.simplify(0.0001)  # Very small tolerance
        if simplified and not simplified.isNull():
            repaired = simplified.makeValid()
            if repaired and not repaired.isNull() and not repaired.isEmpty() and repaired.isGeosValid():
                logger.info("✓ Repaired with simplify + makeValid")
                return repaired
    except Exception as e:
        logger.debug(f"simplify + makeValid failed: {e}")
    
    # Strategy 4: ConvexHull as last resort (preserves area but simplifies shape)
    try:
        hull = geom.convexHull()
        if hull and not hull.isNull() and not hull.isEmpty() and hull.isGeosValid():
            logger.info("✓ Using convex hull as last resort")
            return hull
    except Exception as e:
        logger.debug(f"convexHull failed: {e}")
    
    # Strategy 5: Bounding box (very last resort for filtering purposes)
    try:
        bbox = geom.boundingBox()
        if bbox and not bbox.isEmpty():
            bbox_geom = QgsGeometry.fromRect(bbox)
            if bbox_geom and not bbox_geom.isNull() and bbox_geom.isGeosValid():
                logger.warning(
                    "⚠️ Using bounding box as absolute last resort - geometry severely corrupted"
                )
                return bbox_geom
    except Exception as e:
        logger.debug(f"boundingBox failed: {e}")
    
    logger.error("✗ All repair strategies failed - geometry is irreparably corrupted")
    return None


def repair_invalid_geometries(
    layer: QgsVectorLayer,
    verify_spatial_index_fn: Optional[callable] = None
) -> QgsVectorLayer:
    """
    Validate and repair invalid geometries in a layer.
    Creates a new memory layer with repaired geometries if needed.
    
    Process:
    1. First pass: count invalid geometries
    2. If all valid: return original layer
    3. If invalid found: create memory layer and repair
    4. Use aggressive_geometry_repair for each invalid geometry
    5. Return repaired layer with spatial index
    
    Args:
        layer: Input layer to check and repair
        verify_spatial_index_fn: Optional callback to create spatial index
            Signature: verify_spatial_index_fn(layer, layer_name)
        
    Returns:
        QgsVectorLayer: Original layer if all valid, or new layer with repaired geometries
        
    Raises:
        Exception: If all geometries are invalid and cannot be repaired
    """
    total_features = layer.featureCount()
    invalid_count = 0
    repaired_count = 0
    
    # First pass: check for invalid geometries
    for feature in layer.getFeatures():
        geom = feature.geometry()
        if geom and not geom.isNull():
            if not geom.isGeosValid():
                invalid_count += 1
    
    if invalid_count == 0:
        logger.debug(f"✓ All {total_features} geometries are valid")
        return layer
    
    logger.warning(
        f"⚠️ Found {invalid_count}/{total_features} invalid geometries, attempting repair..."
    )
    
    # Create memory layer for repaired geometries
    geom_type = QgsWkbTypes.displayString(layer.wkbType())
    crs = layer.crs().authid()
    repaired_layer = QgsVectorLayer(f"{geom_type}?crs={crs}", "repaired_geometries", "memory")
    
    # Copy fields
    repaired_layer.dataProvider().addAttributes(layer.fields())
    repaired_layer.updateFields()
    
    # Repair and copy features
    features_to_add = []
    for feature in layer.getFeatures():
        new_feature = QgsFeature(feature)
        geom = feature.geometry()
        
        if geom and not geom.isNull():
            # Log geometry details for diagnosis
            logger.debug(
                f"Feature {feature.id()}: wkbType={geom.wkbType()}, "
                f"isEmpty={geom.isEmpty()}, isValid={geom.isGeosValid()}"
            )
            
            if not geom.isGeosValid():
                # Get validation error details
                try:
                    errors = geom.validateGeometry()
                    if errors:
                        # First 3 errors
                        logger.debug(f"  Validation errors: {[str(e.what()) for e in errors[:3]]}")
                except (AttributeError, RuntimeError):
                    pass
                
                # Try aggressive repair with multiple strategies
                repaired_geom = aggressive_geometry_repair(geom)
                
                if repaired_geom and not repaired_geom.isEmpty():
                    new_feature.setGeometry(repaired_geom)
                    repaired_count += 1
                    logger.debug(f"  ✓ Repaired geometry for feature {feature.id()}")
                else:
                    logger.warning(
                        f"  ✗ Could not repair geometry for feature {feature.id()} - "
                        f"all strategies failed"
                    )
                    continue
        
        features_to_add.append(new_feature)
    
    # Add repaired features
    repaired_layer.dataProvider().addFeatures(features_to_add)
    repaired_layer.updateExtents()
    
    # Check if we have at least some valid features
    if len(features_to_add) == 0:
        logger.error(
            f"✗ Geometry repair failed: No valid features remaining after repair (0/{total_features})"
        )
        raise Exception(
            f"All geometries are invalid and cannot be repaired. "
            f"Total: {total_features}, Invalid: {invalid_count}"
        )
    
    # Create spatial index for improved performance (if callback provided)
    if verify_spatial_index_fn:
        verify_spatial_index_fn(repaired_layer, "repaired_geometries")
    
    logger.info(
        f"✓ Geometry repair complete: {repaired_count}/{invalid_count} successfully repaired, "
        f"{len(features_to_add)}/{total_features} features kept"
    )
    return repaired_layer

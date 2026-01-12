"""
Geometry Converter Module

EPIC-1 Phase E2: Extracted from modules/tasks/filter_task.py

Provides geometry type conversion operations:
- GeometryCollection to MultiPolygon conversion
- Polygon to MultiPolygon conversion
- Safe extraction of polygon parts from collections

Used primarily for buffer operations that can produce GeometryCollections
when dissolving features, which causes errors when adding to typed layers
(e.g., GeoPackage MultiPolygon layers).

Error fixed: "Impossible d'ajouter l'objet avec une géométrie de type 
GeometryCollection à une couche de type MultiPolygon"

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase E2)
"""

import logging
from typing import Optional

from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsMemoryProviderUtils,
    QgsVectorLayer,
    QgsWkbTypes
)

# Import geometry safety utilities (migrated from modules.geometry_safety)
from .geometry_safety import (
    validate_geometry,
    safe_convert_to_multi_polygon,
    safe_as_polygon,
    extract_polygons_from_collection,
    get_geometry_type_name
)

logger = logging.getLogger('FilterMate.Core.Geometry.Converter')


def convert_geometry_collection_to_multipolygon(layer: QgsVectorLayer) -> QgsVectorLayer:
    """
    Convert GeometryCollection geometries in a layer to MultiPolygon.
    
    STABILITY FIX v2.3.9: Uses geometry_safety module to prevent
    access violations when handling GeometryCollections.
    
    CRITICAL FIX for GeoPackage/OGR layers:
    When qgis:buffer processes features with DISSOLVE=True, the result
    can contain GeometryCollection type instead of MultiPolygon.
    This causes errors when the buffer layer is used for spatial operations
    on typed layers (e.g., GeoPackage MultiPolygon layers).
    
    Process:
    1. Check if layer contains GeometryCollection features
    2. If not found: return original layer unchanged
    3. If found: create new MultiPolygon memory layer
    4. Convert each GeometryCollection to MultiPolygon
    5. Extract polygon parts if direct conversion fails
    6. Return layer with all geometries as MultiPolygon
    
    Args:
        layer: QgsVectorLayer from buffer operation (may contain GeometryCollections)
        
    Returns:
        QgsVectorLayer: Layer with geometries converted to MultiPolygon
            Returns original layer if no conversion needed or on error
    """
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
            logger.debug("No GeometryCollection found in buffer result - no conversion needed")
            return layer
        
        logger.info(
            "🔄 GeometryCollection detected in buffer result - converting to MultiPolygon"
        )
        
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
            logger.error("Failed to create converted memory layer")
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
                # STABILITY FIX: Use safe wrapper for conversion
                converted = safe_convert_to_multi_polygon(geom)
                if converted:
                    new_geom = converted
                    conversion_count += 1
                    logger.debug(
                        f"Converted GeometryCollection to {get_geometry_type_name(new_geom)}"
                    )
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
                        logger.warning(
                            "GeometryCollection contained no polygon parts - skipping feature"
                        )
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
                logger.info(
                    f"✓ Converted {conversion_count} GeometryCollection(s) to MultiPolygon"
                )
                return converted_layer
            else:
                logger.error("Failed to add converted features to layer")
                return layer
        else:
            logger.warning("No features to convert")
            return layer
            
    except Exception as e:
        logger.error(f"Error converting GeometryCollection: {str(e)}")
        import traceback
        logger.debug(f"Conversion traceback: {traceback.format_exc()}")
        return layer

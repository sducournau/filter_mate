"""
OGR Geometry Optimizer.

v4.7 E6-S2: Extracted from filter_task.py for better modularity.

Provides geometry simplification and optimization specifically for
OGR fallback mode when PostgreSQL/Spatialite fail with complex geometries.
"""
import traceback

from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsGeometry, 
    QgsWkbTypes, QgsMessageLog
)


def simplify_source_for_ogr_fallback(source_layer, logger=None):
    """
    Simplify complex source geometries for OGR fallback.
    
    v2.9.7: When Spatialite/PostgreSQL fails with complex geometries (like large
    GeometryCollections), OGR fallback may also struggle. This function:
    1. Converts GeometryCollections to MultiPolygon (extract polygons only)
    2. Simplifies complex geometries to reduce vertex count
    3. Applies makeValid() to ensure geometry validity
    
    Args:
        source_layer: QgsVectorLayer containing source geometry
        logger: Optional logger for diagnostics
        
    Returns:
        QgsVectorLayer: Simplified source layer (may be new memory layer)
    """
    def log_info(msg):
        if logger:
            logger.info(msg)
        else:
            QgsMessageLog.logMessage(msg, "FilterMate", level=QgsMessageLog.INFO)
    
    def log_warning(msg):
        if logger:
            logger.warning(msg)
        else:
            QgsMessageLog.logMessage(msg, "FilterMate", level=QgsMessageLog.WARNING)
    
    def log_debug(msg):
        if logger:
            logger.debug(msg)
    
    if not source_layer or not source_layer.isValid():
        return source_layer
    
    try:
        # Check if simplification is needed
        needs_simplification = False
        total_vertices = 0
        has_geometry_collection = False
        
        for feat in source_layer.getFeatures():
            geom = feat.geometry()
            if geom and not geom.isEmpty():
                # Count vertices
                for part in geom.parts():
                    total_vertices += part.vertexCount()
                
                # Check for GeometryCollection
                wkt = geom.asWkt()
                if wkt and wkt.strip().upper().startswith('GEOMETRYCOLLECTION'):
                    has_geometry_collection = True
        
        # Thresholds for simplification
        MAX_VERTICES = 5000
        
        if total_vertices > MAX_VERTICES or has_geometry_collection:
            needs_simplification = True
            log_info(f"  🔧 OGR fallback: simplifying source ({total_vertices:,} vertices, GeomCollection={has_geometry_collection})")
        
        if not needs_simplification:
            return source_layer
        
        # Create new memory layer with simplified geometries
        crs_authid = source_layer.crs().authid()
        simplified_layer = QgsVectorLayer(
            f"MultiPolygon?crs={crs_authid}",
            "ogr_fallback_simplified",
            "memory"
        )
        
        if not simplified_layer.isValid():
            log_warning("  Failed to create simplified layer, using original")
            return source_layer
        
        simplified_features = []
        
        for feat in source_layer.getFeatures():
            geom = feat.geometry()
            if not geom or geom.isEmpty():
                continue
            
            # Step 1: Extract polygons from GeometryCollection
            wkt = geom.asWkt()
            if wkt and wkt.strip().upper().startswith('GEOMETRYCOLLECTION'):
                # Extract polygon parts
                polygons = []
                for part in geom.parts():
                    part_geom = QgsGeometry(part.clone())
                    geom_type = QgsWkbTypes.geometryType(part_geom.wkbType())
                    if geom_type == QgsWkbTypes.PolygonGeometry:
                        if part_geom.isMultipart():
                            for sub in part_geom.parts():
                                polygons.append(QgsGeometry(sub.clone()))
                        else:
                            polygons.append(part_geom)
                
                if polygons:
                    geom = QgsGeometry.collectGeometry(polygons)
                    log_debug(f"    Extracted {len(polygons)} polygons from GeometryCollection")
                else:
                    log_warning(f"    No polygons found in GeometryCollection, skipping")
                    continue
            
            # Step 2: Apply makeValid
            if not geom.isGeosValid():
                geom = geom.makeValid()
                if geom.isNull() or geom.isEmpty():
                    continue
            
            # Step 3: Simplify if still too complex
            vertex_count = sum(p.vertexCount() for p in geom.parts())
            if vertex_count > 1000:
                # Calculate tolerance based on extent
                bbox = geom.boundingBox()
                extent = max(bbox.width(), bbox.height())
                tolerance = extent / 1000  # 0.1% of extent
                
                simplified = geom.simplify(tolerance)
                if simplified and not simplified.isEmpty():
                    new_vertex_count = sum(p.vertexCount() for p in simplified.parts())
                    log_debug(f"    Simplified: {vertex_count:,} → {new_vertex_count:,} vertices")
                    geom = simplified
            
            # Create new feature
            new_feat = QgsFeature()
            new_feat.setGeometry(geom)
            simplified_features.append(new_feat)
        
        if simplified_features:
            simplified_layer.dataProvider().addFeatures(simplified_features)
            simplified_layer.updateExtents()
            log_info(f"  ✓ Simplified source: {len(simplified_features)} features, ready for OGR")
            return simplified_layer
        else:
            log_warning("  No features after simplification, using original")
            return source_layer
            
    except Exception as e:
        log_warning(f"  OGR simplification error: {e}, using original")
        log_debug(f"  Traceback: {traceback.format_exc()}")
        return source_layer

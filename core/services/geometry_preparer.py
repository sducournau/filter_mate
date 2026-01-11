"""
Geometry Preparation Service for Multi-Backend Filtering

This module handles geometry preparation logic for different provider backends
(PostgreSQL, Spatialite, OGR) during spatial filtering operations.

Extracted from FilterTask as part of God Class refactoring (Phase E6-S3).
"""

from qgis.core import (
    QgsMessageLog, Qgis, QgsVectorLayer, QgsGeometry, QgsWkbTypes
)

# Provider constants
PROVIDER_POSTGRES = 'postgresql'


def prepare_geometries_by_provider(
    provider_list,
    task_parameters,
    source_layer,
    param_source_provider_type,
    param_buffer_expression,
    layers_dict,
    prepare_postgresql_geom_callback,
    prepare_spatialite_geom_callback,
    prepare_ogr_geom_callback,
    logger=None,
    postgresql_available=True
):
    """
    Prepare source geometries for each provider type.
    
    This function determines which geometry representations are needed based on
    the target provider backends and prepares them accordingly. It handles:
    - PostgreSQL: EXISTS subquery vs WKT mode decision
    - Spatialite: WKT string preparation with OGR fallback
    - OGR: Layer-based geometry preparation
    
    Args:
        provider_list: List of unique provider types to prepare (modified in-place)
        task_parameters: Task configuration dictionary
        source_layer: Source QgsVectorLayer
        param_source_provider_type: Source layer provider type string
        param_buffer_expression: Buffer expression string
        layers_dict: Dictionary of target layers by provider type
        prepare_postgresql_geom_callback: Callback to prepare PostgreSQL geometry
        prepare_spatialite_geom_callback: Callback to prepare Spatialite WKT geometry
        prepare_ogr_geom_callback: Callback to prepare OGR layer geometry
        logger: Optional logger instance for output
        postgresql_available: Whether psycopg2 is available
        
    Returns:
        dict: Prepared geometries with keys:
            - 'success': bool
            - 'postgresql_source_geom': SQL fragment or None
            - 'spatialite_source_geom': WKT string or None
            - 'ogr_source_geom': QgsVectorLayer or None
            - 'spatialite_fallback_mode': bool flag
    """
    result = {
        'success': True,
        'postgresql_source_geom': None,
        'spatialite_source_geom': None,
        'ogr_source_geom': None,
        'spatialite_fallback_mode': False
    }
    
    # CRITICAL FIX v2.7.3: Use SELECTED/FILTERED feature count, not total table count!
    task_features = task_parameters.get("task", {}).get("features", [])
    if task_features and len(task_features) > 0:
        source_feature_count = len(task_features)
        if logger:
            logger.info(f"Using task_features count for WKT decision: {source_feature_count} selected features")
            logger.debug(
                f"v2.7.3 FIX: Using {source_feature_count} SELECTED features for WKT decision (not {source_layer.featureCount()} total)"
            )
    else:
        source_feature_count = source_layer.featureCount()
        if logger:
            logger.info(f"Using source_layer featureCount for WKT decision: {source_feature_count} total features")
    
    # CRITICAL FIX v2.7.15: Check if source is PostgreSQL with connection
    source_is_postgresql = (
        param_source_provider_type == PROVIDER_POSTGRES and
        task_parameters.get("infos", {}).get("postgresql_connection_available", True)
    )
    
    postgresql_needs_wkt = (
        'postgresql' in provider_list and 
        postgresql_available and
        source_feature_count <= 50 and  # SIMPLE_WKT_THRESHOLD
        not source_is_postgresql
    )
    
    # DIAGNOSTIC: Log WKT decision
    if logger:
        logger.debug(
            f"v2.7.15: postgresql_needs_wkt={postgresql_needs_wkt} (count={source_feature_count}, source_is_pg={source_is_postgresql})"
        )
        if postgresql_needs_wkt:
            logger.info(f"PostgreSQL simplified mode: {source_feature_count} features ≤ 50, source is NOT PostgreSQL")
            logger.info("  → Will prepare WKT geometry for direct ST_GeomFromText()")
        elif source_is_postgresql and 'postgresql' in provider_list:
            logger.info(f"PostgreSQL EXISTS mode: source IS PostgreSQL with {source_feature_count} features")
            logger.info("  → Will use EXISTS subquery with table reference (no WKT simplification)")
    
    # Check if any OGR layer needs Spatialite geometry
    ogr_needs_spatialite_geom = False
    if 'ogr' in provider_list and layers_dict and 'ogr' in layers_dict:
        from adapters.backends.spatialite_backend import SpatialiteGeometricFilter
        spatialite_backend = SpatialiteGeometricFilter(task_parameters)
        for layer, layer_props in layers_dict['ogr']:
            if spatialite_backend.supports_layer(layer):
                ogr_needs_spatialite_geom = True
                if logger:
                    logger.info(f"  OGR layer '{layer.name()}' will use Spatialite backend - need WKT geometry")
                break
    
    # Prepare PostgreSQL source geometry
    has_postgresql_fallback_layers = False
    
    if 'postgresql' in provider_list and postgresql_available:
        source_is_postgresql_with_connection = (
            param_source_provider_type == PROVIDER_POSTGRES and
            task_parameters.get("infos", {}).get("postgresql_connection_available", True)
        )
        
        has_distant_postgresql_with_connection = False
        if layers_dict and 'postgresql' in layers_dict:
            for layer, layer_props in layers_dict['postgresql']:
                if layer_props.get('postgresql_connection_available', True):
                    has_distant_postgresql_with_connection = True
                if layer_props.get('_postgresql_fallback', False):
                    has_postgresql_fallback_layers = True
                    if logger:
                        logger.info(f"  → Layer '{layer.name()}' is PostgreSQL with OGR fallback")
        
        # CRITICAL FIX v2.7.2: ONLY prepare postgresql_source_geom if SOURCE is PostgreSQL
        if source_is_postgresql_with_connection:
            if logger:
                logger.info("Preparing PostgreSQL source geometry...")
                logger.info("  → Source layer is PostgreSQL with connection")
            result['postgresql_source_geom'] = prepare_postgresql_geom_callback()
        elif has_distant_postgresql_with_connection:
            if logger:
                logger.info("PostgreSQL distant layers detected but source is NOT PostgreSQL")
                logger.info("  → Source layer provider: %s", param_source_provider_type)
                logger.info("  → Will use WKT mode (ST_GeomFromText) for PostgreSQL filtering")
                logger.info("  → Skipping prepare_postgresql_source_geom() to avoid invalid table references")
        else:
            if logger:
                logger.warning("PostgreSQL in provider list but no layers have connection - will use OGR fallback")
            if 'ogr' not in provider_list:
                if logger:
                    logger.info("Adding OGR to provider list for PostgreSQL fallback...")
                provider_list.append('ogr')
    
    # CRITICAL FIX: If any PostgreSQL layer uses OGR fallback, we MUST prepare ogr_source_geom
    if has_postgresql_fallback_layers and 'ogr' not in provider_list:
        if logger:
            logger.info("PostgreSQL fallback layers detected - adding OGR to provider list")
        provider_list.append('ogr')
    
    # Prepare Spatialite source geometry (WKT string) with fallback to OGR
    if 'spatialite' in provider_list or postgresql_needs_wkt or ogr_needs_spatialite_geom:
        if logger:
            logger.debug(f"v2.7.3: Preparing Spatialite/WKT geometry (postgresql_wkt={postgresql_needs_wkt})")
            logger.info("Preparing Spatialite source geometry...")
            logger.info(f"  → Reason: spatialite={'spatialite' in provider_list}, "
                       f"postgresql_wkt={postgresql_needs_wkt}, ogr_spatialite={ogr_needs_spatialite_geom}")
            logger.info(f"  → Features in task: {len(task_parameters['task'].get('features', []))}")
        
        spatialite_success = False
        try:
            spatialite_geom = prepare_spatialite_geom_callback()
            if spatialite_geom is not None:
                spatialite_success = True
                result['spatialite_source_geom'] = spatialite_geom
                wkt_preview = spatialite_geom[:150] if len(spatialite_geom) > 150 else spatialite_geom
                if logger:
                    logger.info(f"✓ Spatialite source geometry prepared: {len(spatialite_geom)} chars")
                    logger.debug(f"v2.7.3: WKT prepared OK ({len(spatialite_geom)} chars)")
                    logger.info(f"  → WKT preview: {wkt_preview}...")
            else:
                if logger:
                    logger.warning("Spatialite geometry preparation returned None")
                QgsMessageLog.logMessage(
                    "v2.7.3: WARNING - Spatialite geometry preparation returned None!",
                    "FilterMate", Qgis.Warning
                )
        except Exception as e:
            if logger:
                logger.warning(f"Spatialite geometry preparation failed: {e}")
            QgsMessageLog.logMessage(
                f"v2.7.3: ERROR - Spatialite geometry preparation failed: {e}",
                "FilterMate", Qgis.Critical
            )
            if logger:
                import traceback
                logger.debug(f"Traceback: {traceback.format_exc()}")
        
        # Fallback to OGR if Spatialite failed
        if not spatialite_success:
            if logger:
                logger.info("Falling back to OGR geometry preparation...")
            result['spatialite_fallback_mode'] = True
            try:
                ogr_geom = prepare_ogr_geom_callback()
                if ogr_geom is not None:
                    # CRITICAL FIX: Convert OGR layer geometry to WKT for Spatialite
                    if isinstance(ogr_geom, QgsVectorLayer):
                        all_geoms = []
                        for feature in ogr_geom.getFeatures():
                            geom = feature.geometry()
                            if geom and not geom.isEmpty():
                                all_geoms.append(geom)
                        
                        if all_geoms:
                            combined = QgsGeometry.collectGeometry(all_geoms)
                            
                            # CRITICAL FIX: Prevent GeometryCollection from causing issues
                            combined_type = QgsWkbTypes.displayString(combined.wkbType())
                            if 'GeometryCollection' in combined_type:
                                if logger:
                                    logger.warning(f"OGR fallback: collectGeometry produced {combined_type} - converting")
                                
                                has_polygons = any('Polygon' in QgsWkbTypes.displayString(g.wkbType()) for g in all_geoms)
                                has_lines = any('Line' in QgsWkbTypes.displayString(g.wkbType()) for g in all_geoms)
                                has_points = any('Point' in QgsWkbTypes.displayString(g.wkbType()) for g in all_geoms)
                                
                                if has_polygons:
                                    converted = combined.convertToType(QgsWkbTypes.PolygonGeometry, True)
                                elif has_lines:
                                    converted = combined.convertToType(QgsWkbTypes.LineGeometry, True)
                                elif has_points:
                                    converted = combined.convertToType(QgsWkbTypes.PointGeometry, True)
                                else:
                                    converted = None
                                
                                if converted and not converted.isEmpty():
                                    combined = converted
                                    if logger:
                                        logger.info(f"OGR fallback: Converted to {QgsWkbTypes.displayString(combined.wkbType())}")
                                else:
                                    if logger:
                                        logger.warning("OGR fallback: Conversion failed, keeping GeometryCollection")
                            
                            wkt = combined.asWkt()
                            result['spatialite_source_geom'] = wkt.replace("'", "''")
                            if logger:
                                logger.info(f"✓ Converted OGR layer to WKT ({len(result['spatialite_source_geom'])} chars)")
                        else:
                            if logger:
                                logger.warning("OGR layer has no valid geometries for Spatialite fallback")
                            result['spatialite_source_geom'] = None
                    else:
                        result['spatialite_source_geom'] = ogr_geom
                        if logger:
                            logger.info("✓ Successfully used OGR geometry as fallback")
                else:
                    if logger:
                        logger.error("OGR fallback also failed - no geometry available")
                    result['success'] = False
                    return result
            except Exception as e2:
                if logger:
                    logger.error(f"OGR fallback failed: {e2}")
                result['success'] = False
                return result
            finally:
                result['spatialite_fallback_mode'] = False

    # Prepare OGR geometry if needed
    needs_ogr_geom = (
        'ogr' in provider_list or 
        'spatialite' in provider_list or
        param_buffer_expression != '' or
        'postgresql' in provider_list
    )
    if needs_ogr_geom:
        if logger:
            logger.info("Preparing OGR/Spatialite source geometry...")
        result['ogr_source_geom'] = prepare_ogr_geom_callback()
        
        # DIAGNOSTIC v2.4.11: Log status of all source geometries after preparation
        if logger:
            logger.info("=" * 60)
            logger.info("📊 SOURCE GEOMETRY STATUS AFTER PREPARATION")
            logger.info("=" * 60)
            
            spatialite_status = "✓ READY" if result['spatialite_source_geom'] else "✗ NOT AVAILABLE"
            spatialite_len = len(result['spatialite_source_geom']) if result['spatialite_source_geom'] else 0
            logger.info(f"  Spatialite (WKT): {spatialite_status} ({spatialite_len} chars)")
            
            ogr_status = "✓ READY" if result['ogr_source_geom'] else "✗ NOT AVAILABLE"
            ogr_features = result['ogr_source_geom'].featureCount() if (result['ogr_source_geom'] and isinstance(result['ogr_source_geom'], QgsVectorLayer)) else 0
            logger.info(f"  OGR (Layer):      {ogr_status} ({ogr_features} features)")
            
            postgresql_status = "✓ READY" if result['postgresql_source_geom'] else "✗ NOT AVAILABLE"
            logger.info(f"  PostgreSQL (SQL): {postgresql_status}")
            
            # CRITICAL: If both Spatialite and OGR are not available, filtering will fail
            if not result['spatialite_source_geom'] and not result['ogr_source_geom']:
                logger.error("=" * 60)
                logger.error("❌ CRITICAL: NO SOURCE GEOMETRY AVAILABLE!")
                logger.error("=" * 60)
                logger.error("  → Both Spatialite (WKT) and OGR (Layer) geometries are None")
                logger.error("  → This will cause ALL layer filtering to FAIL")
                logger.error("  → Possible causes:")
                logger.error("    1. Source layer has no features")
                logger.error("    2. Source layer has no valid geometries")
                logger.error("    3. No features selected/filtered in source layer")
                logger.error("    4. Geometry preparation failed")
                logger.error("=" * 60)
                
                # v2.8.6: Try to use source_layer directly as emergency fallback
                if source_layer and source_layer.isValid() and source_layer.featureCount() > 0:
                    logger.warning("  → EMERGENCY FALLBACK: Using source_layer directly as ogr_source_geom")
                    result['ogr_source_geom'] = source_layer
                    logger.info(f"  → ogr_source_geom set to source_layer ({source_layer.featureCount()} features)")
            
            logger.info("=" * 60)

    return result

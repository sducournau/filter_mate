"""
Geometry Preparation Service for Multi-Backend Filtering

This module handles geometry preparation logic for different provider backends
(PostgreSQL, Spatialite, OGR) during spatial filtering operations.

Extracted from FilterTask as part of God Class refactoring (Phase E6-S3).

Enhanced January 2026 (BMAD Optimization Priority 1):
- Added geometry simplification and validation methods
- Added WKT conversion utilities
- Added buffer-aware tolerance calculations
- Extracted from filter_task.py to reduce complexity
"""

import logging
from typing import Optional, Union, List, Tuple

from qgis.core import (
    QgsMessageLog, Qgis, QgsVectorLayer, QgsGeometry, QgsWkbTypes,
    QgsCoordinateReferenceSystem, QgsFeature, QgsRectangle
)

logger = logging.getLogger('FilterMate.Services.GeometryPreparer')

# Provider constants
PROVIDER_POSTGRES = 'postgresql'


# ==============================================================================
# GEOMETRY CONVERSION UTILITIES (Extracted from filter_task.py)
# ==============================================================================

def geometry_to_wkt(geometry: QgsGeometry, crs_authid: Optional[str] = None) -> str:
    """
    Convert geometry to WKT with optimized precision based on CRS.
    
    Args:
        geometry: QGIS geometry to convert
        crs_authid: CRS authority ID (e.g., 'EPSG:4326')
        
    Returns:
        WKT string representation
    """
    if geometry is None or geometry.isEmpty():
        return ""
    
    precision = get_wkt_precision(crs_authid)
    wkt = geometry.asWkt(precision)
    logger.debug(f"WKT precision: {precision} decimals (CRS: {crs_authid})")
    return wkt


def get_wkt_precision(crs_authid: Optional[str]) -> int:
    """
    Get optimal WKT precision based on CRS type.
    
    Args:
        crs_authid: CRS authority ID
        
    Returns:
        Number of decimal places for WKT coordinates
    """
    if not crs_authid:
        return 6  # Default precision
    
    # Geographic CRS: 8 decimal places (~1.1mm precision)
    if 'EPSG:4326' in crs_authid or 'EPSG:4269' in crs_authid:
        return 8
    
    # Projected CRS: 2 decimal places (cm precision)
    return 2


def get_buffer_aware_tolerance(
    buffer_value: Optional[float],
    buffer_segments: int,
    buffer_type: int,
    extent_size: float,
    is_geographic: bool = False
) -> float:
    """
    Calculate optimal simplification tolerance considering buffer parameters.
    
    Args:
        buffer_value: Buffer distance
        buffer_segments: Number of buffer segments
        buffer_type: Buffer end cap style (0=round, 1=flat, 2=square)
        extent_size: Size of geometry extent
        is_geographic: Whether CRS is geographic
        
    Returns:
        Tolerance value for simplification
    """
    try:
        from .buffer_service import BufferService, BufferConfig, BufferEndCapStyle
        config = BufferConfig(
            distance=buffer_value or 0,
            segments=buffer_segments,
            end_cap_style=BufferEndCapStyle(buffer_type)
        )
        return BufferService().calculate_buffer_aware_tolerance(config, extent_size, is_geographic)
    except ImportError:
        logger.warning("BufferService not available, using basic tolerance calculation")
        # Fallback: 0.1% of extent or 1/1000 of buffer distance
        if buffer_value:
            return buffer_value / 1000
        return extent_size / 1000 if extent_size > 0 else 0.001


def simplify_geometry_adaptive(
    geometry: QgsGeometry,
    max_wkt_length: Optional[int] = None,
    crs_authid: Optional[str] = None,
    buffer_value: Optional[float] = None,
    buffer_segments: int = 5,
    buffer_type: int = 0
) -> QgsGeometry:
    """
    Simplify geometry adaptively to reduce WKT size while preserving shape.
    
    Args:
        geometry: Geometry to simplify
        max_wkt_length: Maximum acceptable WKT length
        crs_authid: CRS authority ID
        buffer_value: Buffer distance (if applicable)
        buffer_segments: Number of buffer segments
        buffer_type: Buffer end cap style
        
    Returns:
        Simplified geometry
    """
    if not geometry or geometry.isEmpty():
        return geometry
    
    try:
        from ..ports import get_backend_services
        adapter = get_backend_services().get_geometry_preparation_adapter()
        if not adapter:
            logger.warning("GeometryPreparationAdapter not available")
            return geometry
        
        result = adapter.simplify_geometry_adaptive(
            geometry=geometry,
            max_wkt_length=max_wkt_length,
            crs_authid=crs_authid,
            buffer_value=buffer_value,
            buffer_segments=buffer_segments,
            buffer_type=buffer_type
        )
        
        if result.success and result.geometry:
            return result.geometry
        
        logger.warning(f"Adaptive simplification failed: {result.message}")
        return geometry
        
    except ImportError as e:
        logger.error(f"GeometryPreparationAdapter not available: {e}")
        return geometry
    except Exception as e:
        logger.error(f"Adaptive simplification error: {e}")
        return geometry


# ==============================================================================
# GEOMETRY VALIDATION & REPAIR (Extracted from filter_task.py)
# ==============================================================================

def aggressive_geometry_repair(geometry: QgsGeometry) -> QgsGeometry:
    """
    Aggressively repair invalid geometry using multiple strategies.
    
    Args:
        geometry: Geometry to repair
        
    Returns:
        Repaired geometry
    """
    try:
        from ..geometry import aggressive_geometry_repair as core_repair
        return core_repair(geometry)
    except ImportError:
        logger.warning("core.geometry.aggressive_geometry_repair not available, using basic repair")
        # Fallback: basic buffer(0) repair
        if geometry and not geometry.isEmpty():
            if not geometry.isGeosValid():
                repaired = geometry.buffer(0, 5)
                if repaired and not repaired.isEmpty():
                    return repaired
        return geometry


def repair_invalid_geometries(
    layer: QgsVectorLayer,
    verify_spatial_index_fn=None
) -> QgsVectorLayer:
    """
    Validate and repair all invalid geometries in layer.
    
    Args:
        layer: Layer to repair
        verify_spatial_index_fn: Optional function to verify spatial index
        
    Returns:
        Layer with repaired geometries
    """
    try:
        from ..geometry import repair_invalid_geometries as core_repair
        return core_repair(
            layer=layer,
            verify_spatial_index_fn=verify_spatial_index_fn
        )
    except ImportError:
        logger.warning("core.geometry.repair_invalid_geometries not available")
        return layer


# ==============================================================================
# LAYER CONVERSION UTILITIES (Extracted from filter_task.py)
# ==============================================================================

def copy_filtered_layer_to_memory(
    layer: QgsVectorLayer,
    layer_name: str = "filtered_copy"
) -> QgsVectorLayer:
    """
    Copy filtered layer to memory layer.
    
    Args:
        layer: Source layer (with possible subset filter)
        layer_name: Name for memory layer
        
    Returns:
        Memory layer with filtered features
    """
    try:
        from ..ports import get_backend_services
        adapter = get_backend_services().get_geometry_preparation_adapter()
        if not adapter:
            raise ImportError("GeometryPreparationAdapter not available")
        result = adapter.copy_filtered_to_memory(layer, layer_name)
        if result.success and result.layer:
            return result.layer
        raise Exception(f"Failed to copy filtered layer: {result.error_message or 'Unknown'}")
    except ImportError as e:
        logger.error(f"GeometryPreparationAdapter not available: {e}")
        raise


def copy_selected_features_to_memory(
    layer: QgsVectorLayer,
    layer_name: str = "selected_copy"
) -> QgsVectorLayer:
    """
    Copy selected features to memory layer.
    
    Args:
        layer: Source layer with selection
        layer_name: Name for memory layer
        
    Returns:
        Memory layer with selected features
    """
    try:
        from ..ports import get_backend_services
        adapter = get_backend_services().get_geometry_preparation_adapter()
        if not adapter:
            raise ImportError("GeometryPreparationAdapter not available")
        result = adapter.copy_selected_to_memory(layer, layer_name)
        if result.success and result.layer:
            return result.layer
        raise Exception(f"Failed to copy selected features: {result.error_message or 'Unknown'}")
    except ImportError as e:
        logger.error(f"GeometryPreparationAdapter not available: {e}")
        raise


def create_memory_layer_from_features(
    features: List[QgsFeature],
    crs: QgsCoordinateReferenceSystem,
    layer_name: str = "from_features"
) -> Optional[QgsVectorLayer]:
    """
    Create memory layer from feature list.
    
    Args:
        features: List of QgsFeature objects
        crs: Coordinate reference system
        layer_name: Name for memory layer
        
    Returns:
        Memory layer or None on failure
    """
    try:
        from ..ports import get_backend_services
        adapter = get_backend_services().get_geometry_preparation_adapter()
        if not adapter:
            logger.error("GeometryPreparationAdapter not available")
            return None
        result = adapter.create_memory_from_features(features, crs, layer_name)
        if result.success and result.layer:
            return result.layer
        logger.error(f"Failed to create memory layer: {result.error_message or 'Unknown'}")
        return None
    except ImportError as e:
        logger.error(f"GeometryPreparationAdapter not available: {e}")
        return None


def convert_layer_to_centroids(layer: QgsVectorLayer) -> Optional[QgsVectorLayer]:
    """
    Convert layer geometries to centroids.
    
    Args:
        layer: Source layer
        
    Returns:
        Layer with centroid geometries or None on failure
    """
    try:
        from ..ports import get_backend_services
        adapter = get_backend_services().get_geometry_preparation_adapter()
        if not adapter:
            logger.error("GeometryPreparationAdapter not available")
            return None
        result = adapter.convert_to_centroids(layer)
        if result.success and result.layer:
            return result.layer
        logger.error(f"Failed to convert to centroids: {result.error_message or 'Unknown'}")
        return None
    except ImportError as e:
        logger.error(f"GeometryPreparationAdapter not available: {e}")
        return None


# ==============================================================================
# MAIN PREPARATION FUNCTION (Original from filter_task.py)
# ==============================================================================



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
    # FIX 2026-01-16: CRITICAL - Use print() to force console output
    print("=" * 80)
    print("🚀 prepare_geometries_by_provider CALLED")
    print(f"   provider_list: {provider_list}")
    print(f"   param_source_provider_type: {param_source_provider_type}")
    print(f"   postgresql_available: {postgresql_available}")
    print(f"   layers_dict keys: {list(layers_dict.keys()) if layers_dict else 'None'}")
    print("=" * 80)
    
    # Also log normally
    if logger:
        logger.info(f"🚀 prepare_geometries_by_provider CALLED")
        logger.info(f"  → provider_list: {provider_list}")
        logger.info(f"  → param_source_provider_type: {param_source_provider_type}")
        logger.info(f"  → postgresql_available: {postgresql_available}")
        logger.info(f"  → layers_dict keys: {list(layers_dict.keys()) if layers_dict else 'None'}")
    
    from qgis.core import QgsMessageLog, Qgis
    
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
    
    # CRITICAL FIX v2.7.15 + v4.0.3 (2026-01-16): Check if source is PostgreSQL with connection
    # CRITICAL: IGNORE the stored postgresql_connection_available flag - it may be stale from old config
    # Instead, trust the module-level postgresql_available flag which reflects actual psycopg2 availability
    source_is_postgresql = (
        param_source_provider_type == PROVIDER_POSTGRES and
        postgresql_available  # Use module-level flag, NOT stored config value
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
    # FIX 2026-01-15: Use new backend architecture instead of legacy SpatialiteGeometricFilter
    ogr_needs_spatialite_geom = False
    if 'ogr' in provider_list and layers_dict and 'ogr' in layers_dict:
        try:
            from ..ports import get_backend_services
            SpatialiteBackend = get_backend_services().get_spatialite_backend()
            if not SpatialiteBackend:
                # Backend not available, skip Spatialite geometry preparation
                pass  # Fixed: was 'continue' outside loop
            # Check if any OGR layer could benefit from Spatialite backend
            # by checking if it's a GeoPackage or SQLite file
            for layer, layer_props in layers_dict['ogr']:
                layer_source = layer.source() if hasattr(layer, 'source') else ''
                # GeoPackage and SQLite files can use Spatialite backend
                if any(ext in layer_source.lower() for ext in ['.gpkg', '.sqlite', '.db']):
                    ogr_needs_spatialite_geom = True
                    if logger:
                        logger.info(f"  OGR layer '{layer.name()}' is GeoPackage/SQLite - will prepare WKT geometry")
                    break
        except ImportError as e:
            if logger:
                logger.warning(f"Spatialite backend not available: {e}")
            # Continue without Spatialite optimization
    
    # Prepare PostgreSQL source geometry
    has_postgresql_fallback_layers = False
    
    # FIX 2026-01-16: Log diagnostic for PostgreSQL geometry preparation
    print(f"🔍 PostgreSQL geometry preparation check:")
    print(f"  - 'postgresql' in provider_list: {'postgresql' in provider_list}")
    print(f"  - postgresql_available (module-level): {postgresql_available}")
    
    if 'postgresql' in provider_list and postgresql_available:
        print(f"  ✓ PostgreSQL block ENTERED")
        
        # CRITICAL FIX v4.0.3 (2026-01-16): IGNORE stored postgresql_connection_available - may be stale!
        # The module-level postgresql_available flag is the source of truth (psycopg2 actually importable)
        stored_pg_conn = task_parameters.get('infos', {}).get('postgresql_connection_available', 'NOT_SET')
        print(f"  - stored postgresql_connection_available: {stored_pg_conn} (IGNORED - may be stale)")
        
        # Trust module-level flag, not stored config
        source_is_postgresql_with_connection = (
            param_source_provider_type == PROVIDER_POSTGRES and
            postgresql_available  # Module-level flag, NOT stored config
        )
        print(f"  - source_is_postgresql_with_connection: {source_is_postgresql_with_connection}")
        print(f"  - param_source_provider_type: {param_source_provider_type}")
        print(f"  - PROVIDER_POSTGRES constant: {PROVIDER_POSTGRES}")
        
        has_distant_postgresql_with_connection = False
        if layers_dict and 'postgresql' in layers_dict:
            for layer, layer_props in layers_dict['postgresql']:
                # ALSO ignore stored flag for distant layers
                if postgresql_available:
                    has_distant_postgresql_with_connection = True
                if layer_props.get('_postgresql_fallback', False):
                    has_postgresql_fallback_layers = True
                    print(f"  → Layer '{layer.name()}' is PostgreSQL with OGR fallback")
        
        print(f"  - has_distant_postgresql_with_connection: {has_distant_postgresql_with_connection}")
        
        # CRITICAL FIX v2.7.2: ONLY prepare postgresql_source_geom if SOURCE is PostgreSQL
        if source_is_postgresql_with_connection:
            print(f"  ✓ PREPARING PostgreSQL source geometry...")
            result['postgresql_source_geom'] = prepare_postgresql_geom_callback()
            print(f"  ✓ PostgreSQL source geometry result: {result['postgresql_source_geom'] is not None}")
        elif has_distant_postgresql_with_connection:
            print(f"  ⚠️ PostgreSQL distant layers detected but source is NOT PostgreSQL")
            print(f"  → Will use WKT mode (ST_GeomFromText) for PostgreSQL filtering")
        else:
            print(f"  ❌ PostgreSQL in provider list but no layers have connection - will use OGR fallback")
            if 'ogr' not in provider_list:
                provider_list.append('ogr')
    else:
        print(f"  ❌ PostgreSQL block NOT entered")
    
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

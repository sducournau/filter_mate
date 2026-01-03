import math
import logging
import os

# Import logging configuration
from .logging_config import setup_logger
from ..config.config import ENV_VARS

# Setup logger with rotation
logger = setup_logger(
    'FilterMate.Utils',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_utils.log'),
    level=logging.INFO
)

# QGIS PostgreSQL backend always available via native provider
# psycopg2 is only needed for advanced features (materialized views, etc.)
POSTGRESQL_AVAILABLE = True  # QGIS native PostgreSQL support always available

# Import conditionnel de psycopg2 pour fonctionnalités avancées PostgreSQL
try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None
    logger.info(
        "psycopg2 not found - PostgreSQL layers will use QGIS native API (setSubsetString). "
        "Advanced features (materialized views, spatial indexes) disabled. "
        "For better performance with large datasets (>10k features), consider installing psycopg2."
    )

from qgis.core import (
    QgsApplication,
    QgsAuthMethodConfig,
    QgsDataSourceUri,
    QgsFeatureRequest,
    QgsTask,
    QgsVectorLayer,
    QgsWkbTypes
)
from qgis.PyQt.QtCore import QMetaType
from qgis.PyQt.QtCore import QThread

# Import constants
from .constants import (
    PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR, PROVIDER_MEMORY,
    REMOTE_PROVIDERS, get_provider_name
)


def get_primary_key_name(layer):
    """
    Get the primary key field name for a layer.
    
    For OGR layers, tries to find a suitable unique identifier field.
    Uses multiple detection strategies:
    1. Exact match with common ID field names
    2. Pattern matching for fields ending with _ID, _id, etc.
    3. First integer/string field as fallback
    
    Args:
        layer: QgsVectorLayer
    
    Returns:
        str: Primary key field name or None if not found
    """
    if not layer or not layer.isValid():
        return None
    
    # Get all field names
    fields = layer.fields()
    field_names = [field.name() for field in fields]
    
    if not field_names:
        return None
    
    # Strategy 1: Exact match with common primary key names (case-insensitive)
    common_pk_names = ['fid', 'id', 'objectid', 'ogc_fid', 'gid', 'uid']
    
    for field_name in field_names:
        if field_name.lower() in common_pk_names:
            logger.debug(f"Found primary key field (exact match): {field_name}")
            return field_name
    
    # Strategy 2: Pattern matching for fields ending with ID/id
    # Matches: AGG_ID, agg_id, node_id, FEATURE_ID, etc.
    import re
    id_pattern = re.compile(r'.*[_-]?id$', re.IGNORECASE)
    
    for field_name in field_names:
        if id_pattern.match(field_name):
            logger.debug(f"Found primary key field (pattern match): {field_name}")
            return field_name
    
    # Strategy 3: First integer field (often the primary key)
    for field in fields:
        if field.type() in [QMetaType.Type.Int, QMetaType.Type.LongLong]:
            logger.debug(f"Using first integer field as primary key: {field.name()}")
            return field.name()
    
    # Strategy 4: First string field that might be an ID
    for field in fields:
        if field.type() == QMetaType.Type.QString:
            # Check if field name suggests it's an ID
            field_lower = field.name().lower()
            if any(keyword in field_lower for keyword in ['id', 'key', 'code', 'num']):
                logger.debug(f"Using string field as primary key: {field.name()}")
                return field.name()
    
    # Last resort: use first field
    logger.warning(f"No standard primary key found, using first field: {field_names[0]}")
    return field_names[0]


def cleanup_corrupted_layer_filters(project):
    """
    Scan all layers in a project and clear any corrupted filter expressions.
    
    This function detects and clears filters that contain known corruption patterns
    that would cause SQL errors. Should be called at plugin startup to clean up
    any filters that were incorrectly saved in the project file.
    
    Corruption patterns detected:
    1. __source alias without EXISTS wrapper (missing FROM-clause entry error)
    2. Unbalanced parentheses (syntax error)
    
    Args:
        project: QgsProject instance to scan
    
    Returns:
        list: List of layer names that had corrupted filters cleared
    
    Added in v2.3.13 as part of filter integrity protection.
    """
    cleared_layers = []
    
    if project is None:
        logger.warning("cleanup_corrupted_layer_filters: project is None")
        return cleared_layers
    
    try:
        for layer_id, layer in project.mapLayers().items():
            # Only check vector layers
            if not isinstance(layer, QgsVectorLayer):
                continue
            
            # Skip invalid layers
            if not layer.isValid():
                continue
            
            # Get current filter expression
            current_filter = layer.subsetString()
            
            # Skip if no filter
            if not current_filter:
                continue
            
            is_corrupted = False
            corruption_reason = ""
            
            # Check for __source without EXISTS
            if '__source' in current_filter.lower() and 'EXISTS' not in current_filter.upper():
                is_corrupted = True
                corruption_reason = "__source alias without EXISTS wrapper"
            
            # Check for unbalanced parentheses
            elif current_filter.count('(') != current_filter.count(')'):
                is_corrupted = True
                open_count = current_filter.count('(')
                close_count = current_filter.count(')')
                corruption_reason = f"unbalanced parentheses ({open_count} '(' vs {close_count} ')')"
            
            if is_corrupted:
                layer_name = layer.name()
                logger.warning(f"CORRUPTED FILTER CLEARED on startup for layer '{layer_name}'")
                logger.warning(f"  → Reason: {corruption_reason}")
                logger.warning(f"  → Original filter: {current_filter[:200]}...")
                
                # Clear the corrupted filter
                try:
                    layer.setSubsetString("")
                    cleared_layers.append(layer_name)
                    logger.info(f"  → Filter cleared successfully for '{layer_name}'")
                except Exception as e:
                    logger.error(f"  → Failed to clear filter for '{layer_name}': {e}")
    
    except Exception as e:
        logger.error(f"cleanup_corrupted_layer_filters failed: {e}")
    
    if cleared_layers:
        logger.info(f"Startup cleanup: cleared corrupted filters from {len(cleared_layers)} layer(s): {cleared_layers}")
    
    return cleared_layers


def apply_postgresql_type_casting(expression):
    """
    Apply PostgreSQL type casting to handle varchar/text columns in numeric comparisons.
    
    PostgreSQL is strict about types: comparing a varchar column to an integer
    will fail with "operator does not exist: character varying < integer".
    
    This function adds ::numeric casts to column references in comparison operations.
    
    Args:
        expression: SQL expression string
    
    Returns:
        Expression with type casting applied
        
    Example:
        Input:  ("importance" < 4)
        Output: ("importance"::numeric < 4)
    """
    if not expression:
        return expression
    
    # Add type casting for numeric comparison operations
    # Handle both quoted and unquoted column names followed by comparison operators
    expression = expression.replace('" >', '"::numeric >').replace('">', '"::numeric >')
    expression = expression.replace('" <', '"::numeric <').replace('"<', '"::numeric <')
    expression = expression.replace('" +', '"::numeric +').replace('"+', '"::numeric +')
    expression = expression.replace('" -', '"::numeric -').replace('"-', '"::numeric -')
    expression = expression.replace('" >=', '"::numeric >=').replace('">=', '"::numeric >=')
    expression = expression.replace('" <=', '"::numeric <=').replace('"<=', '"::numeric <=')
    
    # Also handle LIKE/ILIKE operations with text casting
    expression = expression.replace('" NOT ILIKE', '"::text NOT ILIKE').replace('" ILIKE', '"::text ILIKE')
    expression = expression.replace('" NOT LIKE', '"::text NOT LIKE').replace('" LIKE', '"::text LIKE')
    
    return expression


def safe_set_subset_string(layer, expression):
    """
    Apply a subset filter to a layer.
    
    CRITICAL THREAD SAFETY WARNING (v2.3.12):
    ==========================================
    layer.setSubsetString() is NOT thread-safe and MUST be called from the main Qt thread.
    
    DO NOT call this function from QgsTask.run() or any background thread!
    Doing so causes "Windows fatal exception: access violation" crashes when multiple
    threads access the same layer simultaneously.
    
    For background tasks that need to work with layer features:
    - Use layer.dataProvider().featureSource() to get a thread-safe snapshot
    - The featureSource contains ALL features and can be safely iterated from any thread
    
    This function should only be called from:
    - QgsTask.finished() callback (runs on main thread)
    - UI event handlers (main thread)
    - Direct main thread code
    
    Args:
        layer: QgsVectorLayer to filter
        expression: Filter expression string
    
    Returns:
        bool: True if filter applied successfully
    """
    try:
        # Guard: invalid or missing layer/source
        if layer is None or not isinstance(layer, QgsVectorLayer) or not layer.isValid():
            logger.warning("safe_set_subset_string called on invalid or None layer; skipping.")
            return False

        # CRITICAL FIX v2.3.13: Validate expression for common corruption patterns
        # Prevent applying invalid expressions that would cause SQL errors
        if expression:
            expression_upper = expression.upper()
            expression_lower = expression.lower()
            
            # Pattern 1: __source alias without EXISTS wrapper
            # __source is only valid inside EXISTS subqueries
            if '__source' in expression_lower and 'EXISTS' not in expression_upper:
                logger.error(f"INVALID EXPRESSION BLOCKED for {layer.name()}")
                logger.error(f"  → Expression contains '__source' alias without EXISTS wrapper")
                logger.error(f"  → This would cause 'missing FROM-clause entry' error")
                logger.error(f"  → Expression: {expression[:200]}...")
                logger.warning(f"  → Applying empty filter to clear corrupted state")
                # Apply empty filter to reset layer to unfiltered state
                layer.setSubsetString("")
                return False
            
            # Pattern 2: Unbalanced parentheses
            open_parens = expression.count('(')
            close_parens = expression.count(')')
            if open_parens != close_parens:
                logger.error(f"INVALID EXPRESSION BLOCKED for {layer.name()}")
                logger.error(f"  → Unbalanced parentheses: {open_parens} '(' vs {close_parens} ')'")
                logger.error(f"  → Expression: {expression[:200]}...")
                logger.warning(f"  → Applying empty filter to clear corrupted state")
                layer.setSubsetString("")
                return False
            
            # Apply PostgreSQL type casting for postgres provider
            # This fixes "operator does not exist: character varying < integer" errors
            if layer.providerType() == 'postgres':
                expression = apply_postgresql_type_casting(expression)
                logger.debug(f"Applied PostgreSQL type casting: {expression[:100]}...")

        result = layer.setSubsetString(expression)

        if not result:
            # Get detailed error information
            error_msg = 'Unknown error'
            if layer.error():
                error_msg = layer.error().message()
            
            # Log comprehensive error information
            logger.warning(f"setSubsetString() returned False for {layer.name()}")
            logger.warning(f"  → Error: {error_msg}")
            logger.warning(f"  → Provider: {layer.providerType()}")
            logger.warning(f"  → Expression length: {len(expression) if expression else 0} chars")
            if expression:
                logger.warning(f"  → Expression preview: {expression[:200]}...")
            
            # Check for common PostgreSQL errors
            if 'syntax error' in error_msg.lower():
                logger.error("  → SQL SYNTAX ERROR detected. Check expression formatting.")
            elif 'column' in error_msg.lower() and 'does not exist' in error_msg.lower():
                logger.error("  → COLUMN NOT FOUND. Check field names and case sensitivity.")
            elif 'permission' in error_msg.lower():
                logger.error("  → PERMISSION ERROR. Check database user permissions.")

        return result

    except Exception as e:
        try:
            lname = layer.name() if layer else 'None'
        except (AttributeError, RuntimeError):
            lname = 'Unknown'
        logger.error(f"Failed to apply subset string to {lname}: {e}")
        return False

def is_layer_source_available(layer, require_psycopg2: bool = True) -> bool:
    """
    Check if a layer is usable: valid and its underlying data source is accessible.

    This guards against broken layers or moved/removed sources (e.g., deleted files).

    Args:
        layer (QgsVectorLayer): Layer to check
        require_psycopg2 (bool): If True, PostgreSQL layers require psycopg2 to be available.
                                 Set to False for operations like export that use QGIS API
                                 and don't need direct PostgreSQL connections.
                                 Default is True for backward compatibility.

    Returns:
        bool: True if the layer is valid and its source seems available
    """
    try:
        if layer is None or not isinstance(layer, QgsVectorLayer):
            logger.debug(f"is_layer_source_available: layer is None or not QgsVectorLayer")
            return False

        if not layer.isValid():
            logger.debug(f"is_layer_source_available: layer '{layer.name()}' isValid=False (provider={layer.providerType()})")
            return False

        # Get raw QGIS provider type (not normalized)
        raw_provider = layer.providerType()
        
        # REMOTE PROVIDERS: WFS, ArcGIS Feature Service, OGC API Features, etc.
        # If QGIS reports the layer as valid, trust it for remote providers
        if raw_provider in REMOTE_PROVIDERS:
            logger.debug(f"is_layer_source_available: remote provider '{raw_provider}' layer '{layer.name()}' - trusting QGIS validity")
            return True

        provider = detect_layer_provider_type(layer)

        # Memory layers are always available while project is open
        if provider == 'memory':
            return True

        source = layer.source() or ''
        # GeoPackage/Spatialite sources can have format: /path/to/file.gpkg|layername=xxx
        # or /path/to/file.gpkg|layerid=0, so we need to extract just the file path
        base = source.split('|')[0] if '|' in source else source
        
        # Clean up the path (remove any trailing whitespace, quotes, etc.)
        base = base.strip().strip('"').strip("'")

        # Spatialite/OGR: typically filesystem-backed
        if provider in ('spatialite', 'ogr'):
            # Quick heuristics for non-file based OGR sources (e.g., WFS/WMS/HTTP)
            lower = (base or '').lower()
            if lower.startswith(('http://', 'https://', 'wfs:', 'wms:', 'wcs:', 'ftp://')):
                # Remote source - can't synchronously verify availability, trust QGIS validity
                logger.debug(f"is_layer_source_available: remote URL detected for layer '{layer.name()}'")
                return True
            
            # Check for service URLs in source that may not start with protocol
            # Some OGR sources use 'url=' or contain service identifiers
            if any(marker in lower for marker in ['url=', 'service=', 'srsname=', 'typename=']):
                logger.debug(f"is_layer_source_available: service URL markers detected for layer '{layer.name()}'")
                return True

            # If we have a filesystem path, verify it exists
            if base:
                # For GeoPackage files - check if file exists (skip deep validation for performance)
                # Deep validation can cause issues with multiple layers from same GPKG
                if lower.endswith('.gpkg'):
                    if os.path.isfile(base):
                        # Skip is_valid_geopackage() to avoid SQLite locking issues
                        # QGIS already validated the layer when loading it
                        logger.debug(f"is_layer_source_available: GeoPackage file exists for layer '{layer.name()}'")
                        return True
                    else:
                        logger.debug(f"is_layer_source_available: GeoPackage file not found: {base}, trusting layer.isValid()={layer.isValid()}")
                        # Trust QGIS validity - file might be accessible through different path
                        return layer.isValid()
                
                if os.path.isfile(base):
                    return True
                # Shapefile main file check (.shp)
                if lower.endswith('.shp') and os.path.isfile(base):
                    return True
                # SQLite databases (often Spatialite)
                if lower.endswith('.sqlite') and os.path.isfile(base):
                    return True
                # CSV and other delimited text files
                if lower.endswith(('.csv', '.txt', '.tsv')):
                    return os.path.isfile(base)
                # GeoJSON files
                if lower.endswith(('.geojson', '.json')):
                    return os.path.isfile(base)
                    
            # If base is empty but layer is valid, it might be a virtual or computed layer
            # Trust QGIS validity in this case
            if not base and layer.isValid():
                logger.debug(f"is_layer_source_available: empty source but valid layer '{layer.name()}' - trusting QGIS")
                return True
                
            # If base is not empty but doesn't match known file types, 
            # it might be a remote source or special format - trust QGIS validity
            if base and not os.path.exists(base) and layer.isValid():
                # Could be a virtual path, memory layer, or remote source
                logger.debug(f"is_layer_source_available: source '{base}' not a local file but layer is valid - trusting QGIS for '{layer.name()}'")
                return True
            
            return False

        # PostgreSQL: verify connectivity
        if provider == 'postgresql':
            # v2.5.x: PostgreSQL layers always available via QGIS native API
            # psycopg2 is only needed for advanced features (materialized views)
            if require_psycopg2 and not PSYCOPG2_AVAILABLE:
                logger.debug(
                    f"PostgreSQL layer '{layer.name() if layer else 'Unknown'}' - psycopg2 not available, "
                    f"will use QGIS native API (setSubsetString)"
                )
            
            # For PostgreSQL, we rely on QGIS validity as connection test is expensive
            # The actual connection test will happen in get_datasource_connexion_from_layer()
            # when the layer is actually used for filtering
            # PostgreSQL layers are always considered available - QGIS handles the connection
            return True

        # Fallback: trust QGIS validity for unknown provider types
        logger.debug(f"is_layer_source_available: unknown provider '{provider}' for layer '{layer.name()}' - trusting QGIS validity")
        return True

    except Exception as e:
        logger.debug(f"Error while checking layer source availability: {e}")
        return False


def is_valid_geopackage(file_path: str) -> bool:
    """
    Validate that a file is a valid GeoPackage according to GDAL/OGR specifications.
    
    According to GeoPackage standard, a valid GPKG must:
    - Be a SQLite database file
    - Contain required metadata tables:
      * gpkg_contents (mandatory)
      * gpkg_spatial_ref_sys (mandatory)
      * gpkg_geometry_columns (mandatory for vector layers)
    
    Args:
        file_path: Path to the file to validate
    
    Returns:
        True if file is a valid GeoPackage, False otherwise
    
    Note:
        This function only checks for required metadata tables.
        It does NOT validate the full OGC GeoPackage specification.
    """
    import sqlite3
    import os
    
    # Check file exists and has .gpkg extension
    if not os.path.isfile(file_path):
        return False
    
    if not file_path.lower().endswith('.gpkg'):
        return False
    
    # Check file permissions (GDAL requires read/write access)
    if not os.access(file_path, os.R_OK):
        logger.warning(f"GeoPackage file not readable: {file_path}")
        return False
    
    try:
        # Try to connect as SQLite database
        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()
        
        # Get list of all tables
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}
        
        # Check for required GeoPackage metadata tables
        required_tables = {
            'gpkg_contents',
            'gpkg_spatial_ref_sys',
            'gpkg_geometry_columns'
        }
        
        has_required_tables = required_tables.issubset(tables)
        
        conn.close()
        
        if has_required_tables:
            logger.debug(f"✓ Valid GeoPackage detected: {file_path}")
        else:
            missing = required_tables - tables
            logger.debug(f"✗ Not a valid GeoPackage (missing tables: {missing}): {file_path}")
        
        return has_required_tables
        
    except sqlite3.Error as e:
        logger.debug(f"SQLite error checking GeoPackage: {e}")
        return False
    except Exception as e:
        logger.debug(f"Error validating GeoPackage: {e}")
        return False


def truncate(number, digits) -> float:
    """
    Truncate a number to a specified number of decimal places.
    
    Uses improved accuracy with floating point operations to avoid
    common truncation errors like truncate(16.4, 2) = 16.39 or 
    truncate(-1.13, 2) = -1.12.
    
    Args:
        number: The number to truncate
        digits: Number of decimal places to keep
        
    Returns:
        float: The truncated number
        
    Example:
        >>> truncate(16.456, 2)
        16.45
    """
    nbDecimals = len(str(number).split('.')[1]) 
    if nbDecimals <= digits:
        return number
    stepper = 10.0 ** digits
    return math.trunc(stepper * number) / stepper


def detect_layer_provider_type(layer):
    """
    Detect the provider type of a QGIS vector layer.
    
    For filtering purposes, this function returns the logical backend type:
    - 'postgresql': PostgreSQL/PostGIS layers (and similar SQL databases like MSSQL, Oracle, HANA)
    - 'spatialite': Native Spatialite AND GeoPackage/SQLite via OGR
    - 'ogr': Shapefiles, GeoJSON, and other OGR formats (not GPKG/SQLite)
    - 'memory': Memory layers
    
    Remote providers (WFS, ArcGIS Feature Service, etc.) return 'ogr' as they use
    QGIS expressions for filtering rather than SQL.
    
    GeoPackage and SQLite files return 'spatialite' because they support
    Spatialite SQL functions in setSubsetString (ST_Intersects, GeomFromText, etc.)
    
    Args:
        layer (QgsVectorLayer): QGIS vector layer
    
    Returns:
        str: One of 'postgresql', 'spatialite', 'ogr', 'memory', or 'unknown'
    """
    if not isinstance(layer, QgsVectorLayer):
        return 'unknown'
    
    provider_type = layer.providerType()
    
    # Remote providers (WFS, ArcGIS, etc.) use OGR-style filtering
    if provider_type in REMOTE_PROVIDERS:
        return 'ogr'
    
    # Use helper to convert QGIS provider type to FilterMate constant
    normalized_type = get_provider_name(provider_type)
    
    if normalized_type == 'postgresql':
        return 'postgresql'
    elif normalized_type == PROVIDER_SPATIALITE:
        return 'spatialite'
    elif normalized_type == PROVIDER_MEMORY:
        return 'memory'
    elif provider_type == PROVIDER_OGR or normalized_type == PROVIDER_OGR:
        # Check if it's a GeoPackage or SQLite file - these support Spatialite SQL
        source = layer.source()
        source_path = source.split('|')[0] if '|' in source else source
        lower_path = source_path.lower()
        
        if lower_path.endswith('.gpkg'):
            return 'spatialite'
        if lower_path.endswith('.sqlite'):
            return 'spatialite'
        
        # Check for remote URLs - these use OGR filtering
        if any(lower_path.startswith(proto) for proto in ('http://', 'https://', 'ftp://')):
            return 'ogr'
        
        # Other OGR formats (Shapefile, GeoJSON, etc.)
        return 'ogr'
    else:
        # Unknown provider - default to OGR for safety
        return 'ogr'


def get_geopackage_path(layer):
    """
    Extract GeoPackage file path from a layer.
    
    Args:
        layer (QgsVectorLayer): QGIS vector layer
    
    Returns:
        str or None: Absolute path to GeoPackage file, or None if not a GeoPackage layer
    
    Examples:
        >>> gpkg_path = get_geopackage_path(layer)
        >>> if gpkg_path:
        ...     print(f"Layer is from: {gpkg_path}")
    """
    import os
    
    if not isinstance(layer, QgsVectorLayer):
        return None
    
    # Get provider type first
    provider_type = detect_layer_provider_type(layer)
    
    # Only process spatialite/ogr layers
    if provider_type not in ('spatialite', 'ogr'):
        return None
    
    # Extract source path
    source = layer.source()
    source_path = source.split('|')[0] if '|' in source else source
    
    # Check if it's a GeoPackage file
    if source_path.lower().endswith('.gpkg'):
        # Normalize and return absolute path
        if os.path.isfile(source_path):
            return os.path.abspath(source_path)
    
    return None


def get_geopackage_related_layers(source_layer, project_layers_dict):
    """
    Get all layers from the same GeoPackage as the source layer.
    
    This function identifies all layers in the project that share the same GeoPackage
    file as the source layer. Useful for automatically including related layers in
    geometric filtering operations.
    
    Args:
        source_layer (QgsVectorLayer): Source layer to find related layers for
        project_layers_dict (dict): PROJECT_LAYERS dictionary containing layer info
    
    Returns:
        list: List of layer IDs from the same GeoPackage (excluding source layer itself)
    
    Examples:
        >>> related_ids = get_geopackage_related_layers(source_layer, PROJECT_LAYERS)
        >>> logger.info(f"Found {len(related_ids)} related layers in same GeoPackage")
    """
    # Get GeoPackage path of source layer
    source_gpkg_path = get_geopackage_path(source_layer)
    
    if not source_gpkg_path:
        logger.debug(f"Source layer '{source_layer.name()}' is not from a GeoPackage")
        return []
    
    logger.info(f"🔍 Looking for layers from same GeoPackage: {source_gpkg_path}")
    
    related_layer_ids = []
    from qgis.core import QgsProject
    project = QgsProject.instance()
    
    # Iterate through all layers in project
    for layer_id, layer_obj in project.mapLayers().items():
        # Skip the source layer itself
        if layer_id == source_layer.id():
            continue
        
        # Skip non-vector layers
        if not isinstance(layer_obj, QgsVectorLayer):
            continue
        
        # Check if this layer is from the same GeoPackage
        layer_gpkg_path = get_geopackage_path(layer_obj)
        if layer_gpkg_path and layer_gpkg_path == source_gpkg_path:
            # Verify layer is in PROJECT_LAYERS (properly initialized)
            if layer_id in project_layers_dict:
                related_layer_ids.append(layer_id)
                logger.info(f"  ✓ Found related layer: {layer_obj.name()} (id={layer_id[:8]}...)")
            else:
                logger.warning(
                    f"  ⚠️ Layer '{layer_obj.name()}' from same GeoPackage but not in PROJECT_LAYERS - skipping"
                )
    
    logger.info(f"  📊 Total related layers found: {len(related_layer_ids)}")
    return related_layer_ids


def geometry_type_to_string(layer):
    """
    Convert QGIS geometry type enum to string format expected by FilterMate UI.
    
    Args:
        layer (QgsVectorLayer): QGIS vector layer
    
    Returns:
        str: Geometry type string like 'GeometryType.Point', 'GeometryType.Line', etc.
    
    Examples:
        >>> geom_str = geometry_type_to_string(layer)
        >>> icon = icon_per_geometry_type(geom_str)
    """
    if not isinstance(layer, QgsVectorLayer):
        return 'GeometryType.UnknownGeometry'
    
    geometry_type = layer.geometryType()
    
    if geometry_type == QgsWkbTypes.PointGeometry:
        return 'GeometryType.Point'
    elif geometry_type == QgsWkbTypes.LineGeometry:
        return 'GeometryType.Line'
    elif geometry_type == QgsWkbTypes.PolygonGeometry:
        return 'GeometryType.Polygon'
    elif geometry_type == QgsWkbTypes.UnknownGeometry:
        return 'GeometryType.UnknownGeometry'
    elif geometry_type == QgsWkbTypes.NullGeometry:
        return 'GeometryType.UnknownGeometry'
    else:
        return 'GeometryType.UnknownGeometry'


def get_datasource_connexion_from_layer(layer):        
    """
    Get PostgreSQL connection from layer using psycopg2 (for advanced features).
    
    Returns (None, None) if:
    - psycopg2 is not available (basic filtering still works via QGIS API)
    - Layer is not PostgreSQL
    - Connection fails
    
    Note: This is only needed for advanced features like materialized views.
    Basic filtering via setSubsetString() works without psycopg2.
    """
    # Vérifier si psycopg2 est disponible (needed for direct DB operations)
    if not PSYCOPG2_AVAILABLE:
        logger.debug("psycopg2 not available - cannot create direct PostgreSQL connection")
        return None, None
    
    # Vérifier que c'est bien une source PostgreSQL
    if layer.providerType() != 'postgres':
        return None, None

    connexion = None
    source_uri, authcfg_id = get_data_source_uri(layer)

    host = source_uri.host()
    port = source_uri.port()
    dbname = source_uri.database()
    username = source_uri.username()
    password = source_uri.password()
    ssl_mode = source_uri.sslMode()

    if authcfg_id is not None:
        authConfig = QgsAuthMethodConfig()
        if authcfg_id in QgsApplication.authManager().configIds():
            QgsApplication.authManager().loadAuthenticationConfig(authcfg_id, authConfig, True)
            username = authConfig.config("username")
            password = authConfig.config("password")

    # Attempt connection using available credentials from authcfg or URI
    # Note: username/password may be empty if the connection relies on other auth methods
    try:
        connect_kwargs = {
            'user': username,
            'password': password,
            'host': host,
            'port': port,
            'database': dbname
        }
        # Remove None values to avoid psycopg2 complaints
        connect_kwargs = {k: v for k, v in connect_kwargs.items() if v is not None and v != ''}

        if ssl_mode is not None:
            connect_kwargs['sslmode'] = source_uri.encodeSslMode(ssl_mode)

        connexion = psycopg2.connect(**connect_kwargs)
        
        # CRITICAL FIX v2.5.18: Set statement_timeout to prevent blocking queries
        # This prevents complex spatial queries (EXISTS with ST_Intersects on large
        # datasets) from blocking indefinitely and making QGIS appear unresponsive.
        # Default timeout: 120 seconds (2 minutes)
        try:
            with connexion.cursor() as cursor:
                cursor.execute("SET statement_timeout = 120000")  # 120 seconds in milliseconds
                connexion.commit()
        except Exception as timeout_err:
            logger.warning(f"Could not set statement_timeout: {timeout_err}")
            
    except Exception as e:
        logger.error(f"PostgreSQL connection failed for layer '{layer.name()}' on {host}:{port}/{dbname}: {e}")
        connexion = None

    return connexion, source_uri

def get_data_source_uri(layer):
    """
    Extract data source URI and authentication config ID from a layer.
    
    Args:
        layer: QgsVectorLayer or None
    
    Returns:
        tuple: (source_uri, authcfg_id) or (None, None) if layer is None
    """
    if layer is None:
        return None, None
    
    source_uri = QgsDataSourceUri(layer.source()) if str(QgsDataSourceUri(layer.source())) != '' else None
    authcfg_id = source_uri.param('authcfg') if source_uri and str(source_uri.param('authcfg')) != '' else None
    return source_uri, authcfg_id


def create_temp_spatialite_table(db_path, table_name, sql_query, geom_field='geometry', srid=4326):
    """
    Create temporary table in Spatialite as alternative to PostgreSQL materialized views.
    
    This function provides a Spatialite backend for FilterMate when PostgreSQL is not available.
    It creates a temporary table populated by a SELECT query, similar to CREATE MATERIALIZED VIEW.
    
    Args:
        db_path (str): Path to Spatialite database
        table_name (str): Name for temporary table (without 'mv_' prefix)
        sql_query (str): SELECT query to populate table (Spatialite SQL syntax)
        geom_field (str): Geometry column name (default: 'geometry')
        srid (int): Spatial Reference System ID (default: 4326)
    
    Returns:
        bool: True if successful, False otherwise
    
    Raises:
        Exception: If Spatialite operations fail
    
    Example:
        >>> sql = "SELECT geometry, id, name FROM mytable WHERE condition = 1"
        >>> create_temp_spatialite_table('/path/to/db.sqlite', 'temp_view', sql, 'geom', 3857)
        True
    """
    import sqlite3
    
    try:
        # Connect to Spatialite database using context manager (ensures cleanup)
        with sqlite3.connect(db_path) as conn:
            conn.enable_load_extension(True)
            
            # Load Spatialite extension (try multiple paths for compatibility)
            try:
                conn.load_extension('mod_spatialite')
            except (OSError, sqlite3.OperationalError):
                try:
                    conn.load_extension('mod_spatialite.dll')  # Windows
                except (OSError, sqlite3.OperationalError):
                    try:
                        conn.load_extension('libspatialite')  # Linux/Mac alternative
                    except (OSError, sqlite3.OperationalError) as e:
                        raise RuntimeError(
                            "FilterMate: Spatialite extension not available. "
                            "Install spatialite or use PostgreSQL for spatial operations."
                        ) from e
            
            cursor = conn.cursor()
            
            try:
                # Full table name with mv_ prefix for compatibility with existing code
                full_table_name = f"mv_{table_name}"
                
                # Drop existing table and its spatial index if exists
                cursor.execute(f"DROP TABLE IF EXISTS {full_table_name}")
                conn.commit()
                
                # Create temp table from query
                # Note: We don't use "CREATE TEMP TABLE" because we need persistence across connections
                create_sql = f"CREATE TABLE {full_table_name} AS {sql_query}"
                cursor.execute(create_sql)
                conn.commit()
                
                # Register geometry column in Spatialite metadata
                # This is essential for spatial operations
                cursor.execute(f"""
                    SELECT RecoverGeometryColumn('{full_table_name}', '{geom_field}', {srid}, 
                                                (SELECT GeometryType({geom_field}) FROM {full_table_name} LIMIT 1),
                                                (SELECT CoordDimension({geom_field}) FROM {full_table_name} LIMIT 1))
                """)
                conn.commit()
                
                # Create spatial index (R-tree) for performance
                cursor.execute(f"SELECT CreateSpatialIndex('{full_table_name}', '{geom_field}')")
                conn.commit()
                
                # Optimize table (similar to PostgreSQL ANALYZE)
                cursor.execute(f"ANALYZE {full_table_name}")
                conn.commit()
                
                return True
                
            finally:
                cursor.close()
                # conn.close() is automatic with context manager
        
    except RuntimeError as e:
        # Re-raise spatialite extension errors with clear message
        logger.error(str(e))
        return False
        
    except Exception as e:
        error_msg = f"Error creating Spatialite temp table '{table_name}': {str(e)}"
        logger.error(error_msg)
        return False


def get_spatialite_datasource_from_layer(layer):
    """
    Get Spatialite database path from layer.
    
    Args:
        layer (QgsVectorLayer): QGIS vector layer
    
    Returns:
        tuple: (db_path, table_name) or (None, None) if not Spatialite
    """
    if layer.providerType() != 'spatialite':
        return None, None
    
    source_uri = QgsDataSourceUri(layer.source())
    db_path = source_uri.database()
    table_name = source_uri.table()
    
    return db_path, table_name


def get_source_table_name(layer):
    """
    Extract the actual source table name from a layer's data source.
    
    This function retrieves the real table name in the database/file, which may
    differ from the layer's display name in QGIS (layer.name()).
    
    For example, a GeoPackage layer might be displayed as "Distribution Cluster"
    in QGIS but the actual table name is "mro_woluwe_03_pop_033".
    
    Args:
        layer (QgsVectorLayer): QGIS vector layer
    
    Returns:
        str: The source table name, or layer.name() as fallback if extraction fails
    
    Examples:
        >>> layer = QgsVectorLayer("postgres://...")
        >>> get_source_table_name(layer)
        'my_table'
        
        >>> layer = QgsVectorLayer("/path/to/file.gpkg|layername=actual_table")
        >>> get_source_table_name(layer)
        'actual_table'
    """
    if layer is None:
        return None
    
    provider_type = layer.providerType()
    source = layer.source()
    
    try:
        # For PostgreSQL layers
        if provider_type == 'postgres':
            source_uri = QgsDataSourceUri(source)
            table_name = source_uri.table()
            if table_name:
                return table_name
            
            # Fallback: regex extraction from connection string
            # Format: table="schema"."table_name" or table="table_name"
            import re
            match = re.search(r'table="(?:[^"]+"\.")?([^"]+)"', source)
            if match:
                return match.group(1)
        
        # For Spatialite layers
        elif provider_type == 'spatialite':
            source_uri = QgsDataSourceUri(source)
            table_name = source_uri.table()
            if table_name:
                return table_name
        
        # For OGR layers (including GeoPackage)
        elif provider_type == 'ogr':
            # OGR source format: /path/to/file.gpkg|layername=table_name
            # or just /path/to/file.shp
            if '|layername=' in source:
                # Extract layername parameter
                parts = source.split('|layername=')
                if len(parts) > 1:
                    table_name = parts[1].split('|')[0]  # Handle additional parameters
                    return table_name
            
            # Try QgsDataSourceUri
            source_uri = QgsDataSourceUri(source)
            table_name = source_uri.table()
            if table_name:
                return table_name
            
            # For shapefile, use filename without extension
            if source.lower().endswith('.shp'):
                import os
                return os.path.splitext(os.path.basename(source))[0]
    
    except Exception as e:
        logger.debug(f"Could not extract source table name from layer {layer.id()}: {e}")
    
    # Fallback: use layer display name
    return layer.name()


def sanitize_sql_identifier(name: str) -> str:
    """
    Sanitize a string to be used as a SQL identifier (table name, view name, etc.).
    
    Replaces all non-alphanumeric characters (except underscore) with underscores.
    Handles special characters like em-dash (—), en-dash (–), and other Unicode characters.
    
    Args:
        name: The name to sanitize
        
    Returns:
        str: A sanitized string safe for use as a SQL identifier
        
    Examples:
        >>> sanitize_sql_identifier("mro_woluwe — Home Count")
        'mro_woluwe___Home_Count'
        >>> sanitize_sql_identifier("layer-name with spaces")
        'layer_name_with_spaces'
    """
    if not name:
        return ""
    
    import re
    # Replace any non-alphanumeric character (except underscore) with underscore
    # This handles em-dash (—), en-dash (–), spaces, and other special characters
    sanitized = re.sub(r'[^\w]', '_', name, flags=re.UNICODE)
    
    # Collapse multiple underscores into one
    sanitized = re.sub(r'_+', '_', sanitized)
    
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    
    return sanitized


def sanitize_filename(name: str, replacement: str = '_') -> str:
    """
    Sanitize a string to be used as a filename.
    
    Replaces characters that are invalid or problematic in filenames across
    different operating systems (Windows, Linux, macOS).
    
    Args:
        name: The filename to sanitize
        replacement: Character to use for replacement (default: '_')
        
    Returns:
        str: A sanitized string safe for use as a filename
        
    Examples:
        >>> sanitize_filename("mro_woluwe — Home Count")
        'mro_woluwe_-_Home_Count'
        >>> sanitize_filename("file:with*invalid<chars>")
        'file_with_invalid_chars_'
    """
    if not name:
        return ""
    
    import re
    
    # Characters forbidden in Windows filenames: \ / : * ? " < > |
    # Also handle em-dash (—) and en-dash (–) which can cause encoding issues
    forbidden_chars = r'[\\/:*?"<>|]'
    
    # Replace forbidden characters
    sanitized = re.sub(forbidden_chars, replacement, name)
    
    # Replace em-dash (—) and en-dash (–) with regular dash for readability
    sanitized = sanitized.replace('—', '-').replace('–', '-')
    
    # Replace other problematic Unicode characters with underscore
    # Keep basic alphanumeric, dash, underscore, dot, and space
    sanitized = re.sub(r'[^\w\s.\-]', replacement, sanitized, flags=re.UNICODE)
    
    # Collapse multiple replacement characters
    if replacement:
        sanitized = re.sub(f'{re.escape(replacement)}+', replacement, sanitized)
    
    # Remove leading/trailing spaces and dots (problematic on Windows)
    sanitized = sanitized.strip(' .')
    
    # Ensure the filename is not empty
    if not sanitized:
        sanitized = "unnamed"
    
    return sanitized


def escape_json_string(s: str) -> str:
    """
    Escape a string for safe inclusion in a JSON string value.
    
    This properly escapes backslashes, double quotes, and control characters
    that would break JSON parsing.
    
    Args:
        s: The string to escape
        
    Returns:
        str: A JSON-safe escaped string
        
    Examples:
        >>> escape_json_string('layer "name" with quotes')
        'layer \\"name\\" with quotes'
        >>> escape_json_string('path\\to\\file')
        'path\\\\to\\\\file'
    """
    if not s:
        return ""
    
    # Escape backslashes first (must be done first!)
    escaped = s.replace('\\', '\\\\')
    
    # Escape double quotes
    escaped = escaped.replace('"', '\\"')
    
    # Escape control characters
    escaped = escaped.replace('\n', '\\n')
    escaped = escaped.replace('\r', '\\r')
    escaped = escaped.replace('\t', '\\t')
    
    return escaped


def is_value_relation_layer_available(layer_id, layer_name=None):
    """
    Check if a ValueRelation referenced layer is available in the project.
    
    This provides a fallback mechanism when layers with ValueRelation widgets
    reference other layers that are not loaded in the current project.
    
    Args:
        layer_id (str): The ID of the referenced layer
        layer_name (str, optional): The name of the referenced layer (fallback lookup)
        
    Returns:
        bool: True if the referenced layer exists and is valid, False otherwise
        
    Example:
        >>> if is_value_relation_layer_available(vr_info['layer_id']):
        ...     # Use ValueRelation expression
        ... else:
        ...     # Fallback to raw field value
    """
    from qgis.core import QgsProject
    
    if not layer_id and not layer_name:
        return False
    
    project = QgsProject.instance()
    
    # Try to find by ID first (most reliable)
    if layer_id:
        ref_layer = project.mapLayer(layer_id)
        if ref_layer and ref_layer.isValid():
            return True
    
    # Fallback: try to find by name
    if layer_name:
        layers_by_name = project.mapLayersByName(layer_name)
        for layer in layers_by_name:
            if layer and layer.isValid():
                return True
    
    return False


def get_value_relation_info(layer, field_name, check_layer_availability=False):
    """
    Extract ValueRelation configuration from a field's editor widget setup.
    
    ValueRelation is a QGIS widget type that displays values from a related layer.
    This function extracts the configuration to determine:
    - The referenced layer
    - The key field (stored value)
    - The value field (displayed value)
    - Any filter expression
    
    Args:
        layer (QgsVectorLayer): The layer containing the field
        field_name (str): The name of the field to check
        check_layer_availability (bool): If True, returns None if the referenced
            layer is not available in the project. This prevents QGIS warnings
            about missing layer form dependencies. Default: False
        
    Returns:
        dict or None: Dictionary with keys:
            - 'layer_id': ID of the referenced layer
            - 'layer_name': Name of the referenced layer  
            - 'key_field': Field name used as key (stored value)
            - 'value_field': Field name used for display
            - 'filter_expression': Optional filter expression
            - 'allow_null': Whether null values are allowed
            - 'order_by_value': Whether to order by display value
            - 'layer_available': Boolean indicating if referenced layer exists
        Returns None if field is not a ValueRelation or config is invalid
        
    Example:
        >>> info = get_value_relation_info(layer, 'category_id')
        >>> if info:
        ...     print(f"Display field: {info['value_field']}")
    """
    if layer is None or not layer.isValid():
        return None
    
    try:
        field_idx = layer.fields().indexOf(field_name)
        if field_idx < 0:
            return None
        
        widget_setup = layer.editorWidgetSetup(field_idx)
        
        # Check if it's a ValueRelation widget
        if widget_setup.type() != 'ValueRelation':
            return None
        
        config = widget_setup.config()
        if not config:
            return None
        
        # Extract ValueRelation configuration
        layer_id = config.get('Layer', config.get('LayerId', ''))
        layer_name = config.get('LayerName', '')
        
        result = {
            'layer_id': layer_id,
            'layer_name': layer_name,
            'key_field': config.get('Key', ''),
            'value_field': config.get('Value', ''),
            'filter_expression': config.get('FilterExpression', ''),
            'allow_null': config.get('AllowNull', False),
            'order_by_value': config.get('OrderByValue', False),
            'layer_available': is_value_relation_layer_available(layer_id, layer_name)
        }
        
        # Validate required fields
        if not result['key_field'] or not result['value_field']:
            logger.debug(f"ValueRelation config incomplete for {field_name}: {config}")
            return None
        
        # If checking availability and layer is missing, return None to trigger fallback
        if check_layer_availability and not result['layer_available']:
            logger.debug(
                f"ValueRelation for '{field_name}' references missing layer "
                f"'{layer_name}' (id={layer_id[:8] if layer_id else 'N/A'}...). "
                f"Fallback to raw field value."
            )
            return None
        
        return result
        
    except Exception as e:
        logger.debug(f"Error extracting ValueRelation info for {field_name}: {e}")
        return None


def get_field_display_expression(layer, field_name, check_layer_availability=True):
    """
    Get the display expression for a field based on its widget configuration.
    
    For ValueRelation fields, this returns an expression that displays the 
    human-readable value from the referenced layer instead of the key.
    
    The expression uses QGIS's represent_value() function which automatically
    resolves ValueRelation, ValueMap, and other widget types to their display values.
    
    Args:
        layer (QgsVectorLayer): The layer containing the field
        field_name (str): The name of the field
        check_layer_availability (bool): If True, returns None for ValueRelation
            fields where the referenced layer is not available. This prevents
            QGIS warnings about missing layer form dependencies. Default: True
        
    Returns:
        str or None: A QGIS expression string for display, or None if no special
                     display is configured or if the referenced layer is missing
                     
    Example:
        >>> expr = get_field_display_expression(layer, 'category_id')
        >>> if expr:
        ...     # expr might be: represent_value("category_id")
        ...     # or: attribute(get_feature('categories_layer_id', 'id', "category_id"), 'name')
    """
    if layer is None or not layer.isValid():
        return None
    
    try:
        field_idx = layer.fields().indexOf(field_name)
        if field_idx < 0:
            return None
        
        widget_setup = layer.editorWidgetSetup(field_idx)
        widget_type = widget_setup.type()
        
        # For ValueRelation, check if referenced layer is available
        if widget_type == 'ValueRelation':
            if check_layer_availability:
                vr_info = get_value_relation_info(layer, field_name, check_layer_availability=True)
                if vr_info is None:
                    # Referenced layer is missing - fallback to raw field value
                    logger.debug(
                        f"Skipping represent_value() for '{field_name}' - "
                        f"referenced layer not available"
                    )
                    return None
            # represent_value() is the QGIS built-in function that resolves
            # widget values to their display representation
            return f'represent_value("{field_name}")'
        
        # For ValueMap widgets (dropdown with predefined values)
        elif widget_type == 'ValueMap':
            return f'represent_value("{field_name}")'
        
        # For RelationReference widgets  
        elif widget_type == 'RelationReference':
            # Check if the relation's referenced layer is available
            if check_layer_availability:
                config = widget_setup.config()
                relation_id = config.get('Relation', '') if config else ''
                if relation_id:
                    from qgis.core import QgsProject
                    relation = QgsProject.instance().relationManager().relation(relation_id)
                    if not relation.isValid():
                        logger.debug(
                            f"Skipping represent_value() for '{field_name}' - "
                            f"relation '{relation_id}' not valid"
                        )
                        return None
            return f'represent_value("{field_name}")'
        
        return None
        
    except Exception as e:
        logger.debug(f"Error getting display expression for {field_name}: {e}")
        return None


def get_layer_display_expression(layer):
    """
    Get the layer's configured display expression if it has one.
    
    Layers can have a display expression set in Layer Properties > Display
    which is used for feature identification, map tips, etc.
    
    Args:
        layer (QgsVectorLayer): The layer to check
        
    Returns:
        str or None: The display expression, or None if not set
        
    Example:
        >>> expr = get_layer_display_expression(layer)
        >>> if expr:
        ...     print(f"Layer uses: {expr}")  # e.g., "name" or "concat(id, ' - ', name)"
    """
    if layer is None or not layer.isValid():
        return None
    
    try:
        display_expr = layer.displayExpression()
        if display_expr and display_expr.strip():
            return display_expr.strip()
        return None
    except Exception as e:
        logger.debug(f"Error getting layer display expression: {e}")
        return None


def get_fields_with_value_relations(layer, only_available=True):
    """
    Get all fields in a layer that have ValueRelation widget configuration.
    
    This is useful for understanding data relationships and for building
    display expressions that show human-readable values.
    
    Args:
        layer (QgsVectorLayer): The layer to analyze
        only_available (bool): If True (default), only returns ValueRelation
            fields where the referenced layer is available in the project.
            This provides a fallback mechanism for missing layer dependencies.
        
    Returns:
        list: List of tuples (field_name, value_relation_info) for each 
              ValueRelation field. If only_available=True, excludes fields
              where referenced layers are missing.
              
    Example:
        >>> relations = get_fields_with_value_relations(layer)
        >>> for field_name, info in relations:
        ...     print(f"{field_name} -> {info['value_field']} from {info['layer_name']}")
    """
    if layer is None or not layer.isValid():
        return []
    
    result = []
    
    for field in layer.fields():
        field_name = field.name()
        vr_info = get_value_relation_info(layer, field_name, check_layer_availability=False)
        if vr_info:
            # Filter out unavailable layers if requested
            if only_available and not vr_info.get('layer_available', False):
                logger.debug(
                    f"Skipping ValueRelation field '{field_name}' - "
                    f"referenced layer '{vr_info.get('layer_name', 'unknown')}' not available"
                )
                continue
            result.append((field_name, vr_info))
    
    return result


def get_best_display_field(layer, sample_size=10, use_value_relations=True):
    """
    Determine the best field or expression to use for display in a layer.
    
    This function analyzes layer fields and selects the most suitable one
    for display purposes. It now supports:
    - Layer's configured display expression (from Layer Properties > Display)
    - ValueRelation fields with represent_value() expressions
    - Descriptive text fields (name, label, etc.)
    - Fallback to primary key
    
    Priority order:
    1. Layer's configured display expression (if set in QGIS)
    2. ValueRelation fields using represent_value() for human-readable display
    3. Fields matching common name patterns (name, nom, label, titre, etc.)
    4. First text/string field that's not an ID/key field
    5. Any field with values (fallback)
    6. Primary key if no better option
    
    Args:
        layer (QgsVectorLayer): The layer to analyze
        sample_size (int): Number of features to sample for value checking (default: 10)
        use_value_relations (bool): Whether to detect and use ValueRelation expressions
                                    (default: True)
        
    Returns:
        str: The field name or expression to use for display, or empty string if no fields
        
    Examples:
        >>> layer = QgsVectorLayer("Point?field=id:integer&field=name:string", "test", "memory")
        >>> get_best_display_field(layer)
        'name'
        >>> # For a layer with ValueRelation on category_id:
        >>> get_best_display_field(layer_with_vr)
        'represent_value("category_id")'  # Shows category name, not ID
    """
    if layer is None or not layer.isValid():
        return ""
    
    fields = layer.fields()
    if fields.count() == 0:
        return ""
    
    # Priority 1: Check if layer has a configured display expression
    layer_display_expr = get_layer_display_expression(layer)
    if layer_display_expr:
        logger.debug(f"Using layer display expression for {layer.name()}: {layer_display_expr}")
        return layer_display_expr
    
    # Priority 2: Check for ValueRelation fields that could provide better display
    if use_value_relations:
        vr_fields = get_fields_with_value_relations(layer)
        if vr_fields:
            # Prefer ValueRelation fields with common name patterns in their value_field
            name_patterns_vr = ['name', 'nom', 'label', 'titre', 'title', 'description', 
                                'libelle', 'libellé', 'display', 'text']
            
            for field_name, vr_info in vr_fields:
                value_field = vr_info.get('value_field', '').lower()
                if any(pattern in value_field for pattern in name_patterns_vr):
                    expr = get_field_display_expression(layer, field_name)
                    if expr:
                        logger.debug(f"Using ValueRelation display for {layer.name()}: {expr}")
                        return expr
            
            # If no name-pattern match, use first ValueRelation anyway
            # (any ValueRelation is likely better than raw IDs)
            first_vr_field = vr_fields[0][0]
            expr = get_field_display_expression(layer, first_vr_field)
            if expr:
                logger.debug(f"Using first ValueRelation for {layer.name()}: {expr}")
                # Don't return here - only use if no better text field found
                # Store for later comparison
                first_vr_expression = expr
            else:
                first_vr_expression = None
        else:
            first_vr_expression = None
    else:
        first_vr_expression = None
    
    # Common name patterns for descriptive fields (case-insensitive)
    name_patterns = [
        'name', 'nom', 'label', 'titre', 'title', 'description', 'desc',
        'libelle', 'libellé', 'bezeichnung', 'nombre', 'nome', 'naam',
        'display_name', 'displayname', 'full_name', 'fullname'
    ]
    
    # Patterns to exclude (ID/key fields)
    exclude_patterns = [
        'id', 'pk', 'fid', 'ogc_fid', 'gid', 'uid', 'uuid', 'oid',
        'objectid', 'object_id', '_id', 'rowid', 'row_id'
    ]
    
    # Get field type from QVariant
    from qgis.PyQt.QtCore import QVariant
    
    string_types = [QVariant.String, QVariant.Char]
    
    best_field = None
    first_text_field = None
    first_field_with_values = None
    primary_key = None
    
    # Try to get primary key from layer
    primary_key = get_primary_key_name(layer)
    
    # Helper function to check if a field has non-null/non-empty values
    def field_has_values(field_name):
        """Check if a field has at least one non-null, non-empty value."""
        try:
            # Get a sample of features to check values
            request = QgsFeatureRequest().setLimit(sample_size)
            request.setFlags(QgsFeatureRequest.NoGeometry)  # Faster without geometry
            request.setSubsetOfAttributes([field_name], layer.fields())
            
            for feature in layer.getFeatures(request):
                value = feature.attribute(field_name)
                # Check if value is not NULL and not empty string
                if value is not None and value != QVariant() and str(value).strip() != '':
                    return True
            return False
        except Exception:
            # If we can't check, assume it has values to avoid false negatives
            return True
    
    for field in fields:
        field_name = field.name()
        field_name_lower = field_name.lower()
        field_type = field.type()
        
        # Skip geometry fields
        if field_name_lower in ('geometry', 'geom', 'the_geom', 'shape'):
            continue
        
        # Check if it's a text field
        is_text_field = field_type in string_types
        
        # Check for exact match with name patterns
        for pattern in name_patterns:
            if field_name_lower == pattern or field_name_lower.endswith('_' + pattern):
                # Found a name pattern match - verify it has values
                if field_has_values(field_name):
                    return field_name
                # If no values, continue searching for another match
                break
        
        # Track first text field that's not an ID and has values
        if is_text_field and first_text_field is None:
            is_excluded = any(
                field_name_lower == ex or 
                field_name_lower.startswith(ex + '_') or
                field_name_lower.endswith('_' + ex)
                for ex in exclude_patterns
            )
            if not is_excluded:
                if field_has_values(field_name):
                    first_text_field = field_name
        
        # Track first field with values (any type)
        if first_field_with_values is None and field_has_values(field_name):
            is_excluded = any(
                field_name_lower == ex or 
                field_name_lower.startswith(ex + '_') or
                field_name_lower.endswith('_' + ex)
                for ex in exclude_patterns
            )
            if not is_excluded:
                first_field_with_values = field_name
    
    # Return first text field with values if found
    if first_text_field:
        return first_text_field
    
    # If no text field but we have a ValueRelation expression, use it
    # ValueRelation provides human-readable values from related tables
    if first_vr_expression:
        return first_vr_expression
    
    # Return first field with values if found
    if first_field_with_values:
        return first_field_with_values
    
    # Return primary key if exists and has values
    if primary_key and field_has_values(primary_key):
        return primary_key
    elif primary_key:
        return primary_key
    
    # Fall back to first field
    return fields[0].name()


# ============================================================================
# Orphaned Materialized View Detection and Cleanup (v2.8.1)
# ============================================================================

def detect_filtermate_mv_reference(subset_string: str) -> str:
    """
    Detect if a subset string references a FilterMate materialized view.
    
    FilterMate creates materialized views with the prefix 'filtermate_mv_' for
    optimized PostgreSQL filtering. When QGIS closes or the MV is cleaned up,
    the layer's subset string may still reference the now-deleted MV.
    
    Args:
        subset_string: The layer's current subset string
    
    Returns:
        The MV name if found, empty string otherwise
    
    Example subset strings that reference MVs:
        - "fid" IN (SELECT "pk" FROM "public"."filtermate_mv_abc123")
        - "id" IN (SELECT "id" FROM "schema"."filtermate_mv_xyz789")
    """
    import re
    
    if not subset_string:
        return ""
    
    # Pattern to match FilterMate MV references in subset strings
    # Matches: SELECT ... FROM "schema"."filtermate_mv_xxxxx"
    # or: SELECT ... FROM schema.filtermate_mv_xxxxx
    patterns = [
        # Quoted schema and table: "schema"."filtermate_mv_xxx"
        r'FROM\s+["\']?(\w+)["\']?\s*\.\s*["\']?(filtermate_mv_[a-f0-9]+)["\']?',
        # Just table name: filtermate_mv_xxx
        r'FROM\s+["\']?(filtermate_mv_[a-f0-9]+)["\']?',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, subset_string, re.IGNORECASE)
        if match:
            # Return the full MV name (last capturing group)
            return match.group(match.lastindex)
    
    return ""


def validate_mv_exists(layer, mv_name: str, schema: str = None) -> bool:
    """
    Validate if a FilterMate materialized view exists in the database.
    
    Args:
        layer: PostgreSQL QgsVectorLayer to get connection from
        mv_name: Name of the materialized view to check
        schema: Schema name (defaults to layer's schema or 'public')
    
    Returns:
        True if the MV exists, False otherwise
    """
    if not PSYCOPG2_AVAILABLE:
        # Cannot verify MV existence without psycopg2
        # Assume it doesn't exist to be safe
        logger.debug(f"Cannot verify MV '{mv_name}' - psycopg2 not available")
        return False
    
    if not layer or layer.providerType() != 'postgres':
        return False
    
    try:
        conn, source_uri = get_datasource_connexion_from_layer(layer)
        if not conn:
            logger.debug(f"Cannot verify MV '{mv_name}' - no database connection")
            return False
        
        # Get schema from source URI if not provided
        if schema is None:
            schema = source_uri.schema() or "public"
        
        cursor = conn.cursor()
        
        # Query pg_matviews to check if MV exists
        cursor.execute("""
            SELECT 1 FROM pg_matviews 
            WHERE schemaname = %s AND matviewname = %s
            LIMIT 1
        """, (schema, mv_name))
        
        exists = cursor.fetchone() is not None
        
        cursor.close()
        conn.close()
        
        logger.debug(f"MV '{schema}.{mv_name}' exists: {exists}")
        return exists
        
    except Exception as e:
        logger.debug(f"Error checking MV existence for '{mv_name}': {e}")
        return False


def clear_orphaned_mv_subset(layer) -> bool:
    """
    Clear a layer's subset string if it references a missing FilterMate MV.
    
    This fixes the "relation does not exist" error that occurs when:
    1. FilterMate creates a materialized view for filtering
    2. QGIS closes or the MV is cleaned up
    3. Project is reopened - subset string still references the deleted MV
    
    Args:
        layer: PostgreSQL QgsVectorLayer to check and fix
    
    Returns:
        True if the subset was cleared (MV was orphaned), False otherwise
    """
    if not layer or not isinstance(layer, QgsVectorLayer):
        return False
    
    if layer.providerType() != 'postgres':
        return False
    
    subset_string = layer.subsetString()
    if not subset_string:
        return False
    
    # Check if subset references a FilterMate MV
    mv_name = detect_filtermate_mv_reference(subset_string)
    if not mv_name:
        return False  # Not a FilterMate MV reference
    
    # Get schema from layer's source URI
    source_uri, _ = get_data_source_uri(layer)
    schema = source_uri.schema() if source_uri else "public"
    
    # Validate if the MV exists
    if validate_mv_exists(layer, mv_name, schema):
        logger.debug(f"Layer '{layer.name()}' has valid MV reference: {mv_name}")
        return False  # MV exists, no cleanup needed
    
    # MV doesn't exist - clear the orphaned subset string
    logger.warning(
        f"Layer '{layer.name()}' references missing MV '{schema}.{mv_name}'. "
        f"Clearing orphaned filter to restore layer functionality."
    )
    
    try:
        # Clear the subset string to restore layer to unfiltered state
        layer.setSubsetString("")
        logger.info(f"Cleared orphaned MV reference from layer '{layer.name()}'")
        return True
    except Exception as e:
        logger.error(f"Failed to clear subset string for layer '{layer.name()}': {e}")
        return False


def validate_and_cleanup_postgres_layers(layers: list) -> list:
    """
    Validate PostgreSQL layers and clean up orphaned MV references.
    
    Should be called on project load to detect and fix layers that reference
    FilterMate materialized views that no longer exist.
    
    Args:
        layers: List of QgsVectorLayer instances to check
    
    Returns:
        List of layer names that had orphaned MVs cleared
    """
    cleaned_layers = []
    
    for layer in layers:
        if not isinstance(layer, QgsVectorLayer):
            continue
        
        if layer.providerType() != 'postgres':
            continue
        
        try:
            if clear_orphaned_mv_subset(layer):
                cleaned_layers.append(layer.name())
        except Exception as e:
            logger.debug(f"Error validating layer '{layer.name()}': {e}")
    
    if cleaned_layers:
        logger.warning(
            f"Cleaned up {len(cleaned_layers)} layer(s) with orphaned MV references: "
            f"{', '.join(cleaned_layers)}"
        )
    
    return cleaned_layers

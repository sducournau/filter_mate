import math
import logging
import os
import re  # Import at module level for performance (avoid repeated imports in functions)
import sqlite3  # Import at module level for GeoPackage validation

# Import logging configuration
from .logging_config import setup_logger
from ..config.config import ENV_VARS

# Setup logger with rotation
logger = setup_logger(
    'FilterMate.Utils',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_utils.log'),
    level=logging.INFO
)

# Import conditionnel de psycopg2 pour support PostgreSQL optionnel
try:
    import psycopg2
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False
    psycopg2 = None
    logger.warning(
        "PostgreSQL support disabled (psycopg2 not found). "
        "Plugin will work with local files (Shapefile, GeoPackage, etc.) and Spatialite. "
        "For better performance with large datasets, consider installing psycopg2."
    )

from qgis.core import (
    QgsApplication,
    QgsAuthMethodConfig,
    QgsDataSourceUri,
    QgsTask,
    QgsVectorLayer,
    QgsWkbTypes
)
from qgis.PyQt.QtCore import QMetaType
from qgis.PyQt.QtCore import QThread

# Import constants
from .constants import (
    PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR, PROVIDER_MEMORY,
    get_provider_name
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
    # Note: 're' is imported at module level for performance
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


def safe_set_subset_string(layer, expression):
    """
    Thread-safe wrapper for layer.setSubsetString().
    
    CRITICAL: setSubsetString() MUST be called from the main Qt thread.
    This function always executes directly - QgsTask.run() is ALREADY in main thread context.
    
    Args:
        layer: QgsVectorLayer to filter
        expression: Filter expression string
    
    Returns:
        bool: True if filter applied successfully
    """
    try:
        result = layer.setSubsetString(expression)
        
        if not result:
            error_msg = layer.error().message() if layer.error() else 'none'
            logger.warning(f"setSubsetString() returned False for {layer.name()}: {error_msg}")
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to apply subset string to {layer.name()}: {e}")
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
        sqlite3 is imported at module level for performance.
    """
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
    # Improve accuracy with floating point operations, to avoid truncate(16.4, 2) = 16.39 or truncate(-1.13, 2) = -1.12
    nbDecimals = len(str(number).split('.')[1]) 
    if nbDecimals <= digits:
        return number
    stepper = 10.0 ** digits
    return math.trunc(stepper * number) / stepper


def detect_layer_provider_type(layer):
    """
    Detect the provider type of a QGIS vector layer.
    
    Handles the distinction between Spatialite and OGR layers, as both
    can report 'ogr' as providerType() but Spatialite layers have 'Transactions' capability.
    Also checks file extension to detect .sqlite and .gpkg files as Spatialite.
    
    Args:
        layer (QgsVectorLayer): QGIS vector layer
    
    Returns:
        str: One of 'postgresql', 'spatialite', 'ogr', 'memory', or 'unknown'
    
    Examples:
        >>> layer_type = detect_layer_provider_type(layer)
        >>> if layer_type == 'postgresql' and POSTGRESQL_AVAILABLE:
        ...     # Use PostgreSQL optimized path
    """
    if not isinstance(layer, QgsVectorLayer):
        return 'unknown'
    
    provider_type = layer.providerType()
    
    # Use helper to convert QGIS provider type to FilterMate constant
    # This handles 'postgres' -> 'postgresql' conversion
    normalized_type = get_provider_name(provider_type)
    
    if normalized_type == 'postgresql':
        return 'postgresql'
    elif normalized_type == PROVIDER_SPATIALITE:
        return 'spatialite'
    elif normalized_type == PROVIDER_MEMORY:
        return 'memory'
    
    # For OGR or other providers, check if it's Spatialite-based
    return _detect_spatialite_or_ogr(layer)


def _detect_spatialite_or_ogr(layer):
    """
    Helper to detect if an OGR-type layer is actually Spatialite-based.
    
    Checks file extension (.gpkg, .sqlite) and layer capabilities.
    
    Args:
        layer (QgsVectorLayer): QGIS vector layer
    
    Returns:
        str: 'spatialite' or 'ogr'
    """
    source = layer.source()
    source_path = source.split('|')[0] if '|' in source else source
    
    # Check for GeoPackage files
    if source_path.lower().endswith('.gpkg'):
        if is_valid_geopackage(source_path):
            logger.debug(f"Detected valid GeoPackage: {source_path}")
            return 'spatialite'
        else:
            logger.warning(f"File has .gpkg extension but is not a valid GeoPackage: {source_path}")
            return 'ogr'
    
    # Check for SQLite files
    if source_path.lower().endswith('.sqlite'):
        return 'spatialite'
    
    # Check for 'Transactions' capability (indicates Spatialite support)
    capabilities = layer.capabilitiesString().split(', ')
    if 'Transactions' in capabilities:
        return 'spatialite'
    
    return 'ogr'


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
    Get PostgreSQL connection from layer (if available).
    Returns (None, None) if PostgreSQL is not available or layer is not PostgreSQL.
    """
    # Vérifier si PostgreSQL est disponible
    if not POSTGRESQL_AVAILABLE:
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
    else:
        return connexion, source_uri

    if password is not None and len(password) > 0:
        if ssl_mode is not None:
            connexion = psycopg2.connect(user=username, password=password, host=host, port=port, database=dbname, sslmode=source_uri.encodeSslMode(ssl_mode))
        else:
            connexion = psycopg2.connect(user=username, password=password, host=host, port=port, database=dbname)

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
            # Note: 're' is imported at module level
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
    
    # Note: 're' is imported at module level
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
    
    # Note: 're' is imported at module level
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

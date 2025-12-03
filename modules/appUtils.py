import math
import logging
import os

# Import logging configuration
from modules.logging_config import setup_logger
from config.config import ENV_VARS

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

from qgis.core import *
from qgis.utils import *

# Provider type constants (QGIS providerType() returns these values)
PROVIDER_POSTGRES = 'postgres'      # PostgreSQL/PostGIS
PROVIDER_SPATIALITE = 'spatialite'  # Spatialite
PROVIDER_OGR = 'ogr'                # OGR (Shapefile, GeoPackage, etc.)
PROVIDER_MEMORY = 'memory'          # In-memory layers

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
    
    if provider_type == PROVIDER_POSTGRES:
        return 'postgresql'
    elif provider_type == PROVIDER_SPATIALITE:
        return 'spatialite'
    elif provider_type == PROVIDER_MEMORY:
        return 'memory'
    elif provider_type == PROVIDER_OGR:
        # Check if it's actually Spatialite masquerading as OGR
        capabilities = layer.capabilitiesString().split(', ')
        if 'Transactions' in capabilities:
            return 'spatialite'
        else:
            return 'ogr'
    else:
        # Fallback for OGR-like providers
        capabilities = layer.capabilitiesString().split(', ')
        if 'Transactions' in capabilities:
            return 'spatialite'
        else:
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

    if password != None and len(password) > 0:
        if ssl_mode != None:
            connexion = psycopg2.connect(user=username, password=password, host=host, port=port, database=dbname, sslmode=source_uri.encodeSslMode(ssl_mode))
        else:
            connexion = psycopg2.connect(user=username, password=password, host=host, port=port, database=dbname)

    return connexion, source_uri

def get_data_source_uri(layer):

    source_uri = QgsDataSourceUri(layer.source()) if str(QgsDataSourceUri(layer.source())) != '' else None
    authcfg_id = source_uri.param('authcfg') if str(source_uri.param('authcfg')) != '' else None
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
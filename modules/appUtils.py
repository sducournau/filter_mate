import math

# Import conditionnel de psycopg2 pour support PostgreSQL optionnel
try:
    import psycopg2
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False
    psycopg2 = None
    import warnings
    warnings.warn(
        "FilterMate: PostgreSQL support disabled (psycopg2 not found). "
        "Plugin will work with local files (Shapefile, GeoPackage, etc.) and Spatialite. "
        "For better performance with large datasets, consider installing psycopg2."
    )

from qgis.core import *
from qgis.utils import *

def truncate(number, digits) -> float:
    # Improve accuracy with floating point operations, to avoid truncate(16.4, 2) = 16.39 or truncate(-1.13, 2) = -1.12
    nbDecimals = len(str(number).split('.')[1]) 
    if nbDecimals <= digits:
        return number
    stepper = 10.0 ** digits
    return math.trunc(stepper * number) / stepper


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
        # Connect to Spatialite database
        conn = sqlite3.connect(db_path)
        conn.enable_load_extension(True)
        
        # Load Spatialite extension (try multiple paths for compatibility)
        try:
            conn.load_extension('mod_spatialite')
        except:
            try:
                conn.load_extension('mod_spatialite.dll')  # Windows
            except:
                conn.load_extension('libspatialite')  # Linux/Mac alternative
        
        cursor = conn.cursor()
        
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
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"FilterMate: Error creating Spatialite temp table '{table_name}': {str(e)}")
        if 'conn' in locals():
            conn.close()
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
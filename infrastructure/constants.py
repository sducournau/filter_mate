# -*- coding: utf-8 -*-
"""
FilterMate Constants Module

Provides global constants used throughout FilterMate.
Includes provider types, spatial predicates, and performance thresholds.

Migrated from modules/constants.py to infrastructure/constants.py
v4.0 Regression Fix: Restored missing constants from before_migration/modules/constants.py
"""

# =============================================================================
# Provider Types - FilterMate backend identifiers
# =============================================================================
PROVIDER_POSTGRES = 'postgresql'  # FilterMate backend name for PostgreSQL
PROVIDER_SPATIALITE = 'spatialite'
PROVIDER_OGR = 'ogr'
PROVIDER_MEMORY = 'memory'
PROVIDER_VIRTUAL = 'virtual'
PROVIDER_WFS = 'WFS'
PROVIDER_ARCGIS = 'arcgisfeatureserver'
PROVIDER_DELIMITEDTEXT = 'delimitedtext'
PROVIDER_GPKG = 'gpkg'
PROVIDER_MSSQL = 'mssql'
PROVIDER_HANA = 'hana'
PROVIDER_ORACLE = 'oracle'

# =============================================================================
# QGIS Internal Provider Names - returned by layer.providerType()
# Use these when comparing against QgsVectorLayer.providerType()
# =============================================================================
QGIS_PROVIDER_POSTGRES = 'postgres'      # layer.providerType() for PostgreSQL layers
QGIS_PROVIDER_SPATIALITE = 'spatialite'   # layer.providerType() for SpatiaLite layers
QGIS_PROVIDER_OGR = 'ogr'                # layer.providerType() for OGR/file layers
QGIS_PROVIDER_MEMORY = 'memory'           # layer.providerType() for memory layers

# Remote/distant providers that should be treated as available if layer is valid
REMOTE_PROVIDERS = {
    'WFS',                    # OGC Web Feature Service
    'wfs',                    # Lowercase variant
    'arcgisfeatureserver',    # ArcGIS Feature Service
    'arcgismapserver',        # ArcGIS Map Service
    'oapif',                  # OGC API Features
    'wcs',                    # Web Coverage Service (raster, but listed for completeness)
    'vectortile',             # Vector tiles
}

# Provider type mapping from QGIS internal names (v4.0 Regression Fix)
PROVIDER_TYPE_MAPPING = {
    QGIS_PROVIDER_POSTGRES: PROVIDER_POSTGRES,
    QGIS_PROVIDER_SPATIALITE: PROVIDER_SPATIALITE,
    QGIS_PROVIDER_OGR: PROVIDER_OGR,
    QGIS_PROVIDER_MEMORY: PROVIDER_MEMORY,
    'virtual': PROVIDER_OGR,  # Virtual layers use OGR backend (fallback)
    'WFS': PROVIDER_OGR,      # WFS uses OGR backend for filtering
    'wfs': PROVIDER_OGR,      # Lowercase variant
    'arcgisfeatureserver': PROVIDER_OGR,  # ArcGIS uses OGR backend
    'arcgismapserver': PROVIDER_OGR,      # ArcGIS Map Server
    'delimitedtext': PROVIDER_OGR,        # CSV/delimited text
    'gpkg': PROVIDER_SPATIALITE,          # GeoPackage (direct)
    'mssql': PROVIDER_POSTGRES,           # MSSQL uses similar SQL syntax
    'hana': PROVIDER_POSTGRES,            # SAP HANA
    'oracle': PROVIDER_POSTGRES,          # Oracle uses similar SQL syntax
    'oapif': PROVIDER_OGR,                # OGC API Features
}

# =============================================================================
# Spatial Predicates (v4.0 Fix: Restored capitalized format for UI compatibility)
# =============================================================================
PREDICATE_INTERSECTS = 'Intersects'
PREDICATE_WITHIN = 'Within'
PREDICATE_CONTAINS = 'Contains'
PREDICATE_OVERLAPS = 'Overlaps'
PREDICATE_CROSSES = 'Crosses'
PREDICATE_TOUCHES = 'Touches'
PREDICATE_DISJOINT = 'Disjoint'
PREDICATE_EQUALS = 'Equals'

# All supported predicates
ALL_PREDICATES = [
    PREDICATE_INTERSECTS,
    PREDICATE_WITHIN,
    PREDICATE_CONTAINS,
    PREDICATE_OVERLAPS,
    PREDICATE_CROSSES,
    PREDICATE_TOUCHES,
    PREDICATE_DISJOINT,
    PREDICATE_EQUALS,
]

# Predicate mapping to SQL functions (v4.0 Regression Fix)
PREDICATE_SQL_MAPPING = {
    # Capitalized variants
    PREDICATE_INTERSECTS: 'ST_Intersects',
    PREDICATE_WITHIN: 'ST_Within',
    PREDICATE_CONTAINS: 'ST_Contains',
    PREDICATE_OVERLAPS: 'ST_Overlaps',
    PREDICATE_CROSSES: 'ST_Crosses',
    PREDICATE_TOUCHES: 'ST_Touches',
    PREDICATE_DISJOINT: 'ST_Disjoint',
    PREDICATE_EQUALS: 'ST_Equals',
    # Lowercase variants (for case-insensitive lookups)
    'intersects': 'ST_Intersects',
    'within': 'ST_Within',
    'contains': 'ST_Contains',
    'overlaps': 'ST_Overlaps',
    'crosses': 'ST_Crosses',
    'touches': 'ST_Touches',
    'disjoint': 'ST_Disjoint',
    'equals': 'ST_Equals',
}

# =============================================================================
# Task Types
# =============================================================================
TASK_FILTER = 'filter'
TASK_UNFILTER = 'unfilter'
TASK_RESET = 'reset'
TASK_EXPORT = 'export'
TASK_ADD_LAYERS = 'add_layers'
TASK_REMOVE_LAYERS = 'remove_layers'

# =============================================================================
# Buffer Types
# =============================================================================
BUFFER_TYPE_FIXED = 'fixed'
BUFFER_TYPE_EXPRESSION = 'expression'
BUFFER_TYPE_NONE = None

# =============================================================================
# Combine Operators
# =============================================================================
COMBINE_AND = 'AND'
COMBINE_OR = 'OR'

# =============================================================================
# Export Formats
# =============================================================================
EXPORT_FORMAT_SHAPEFILE = 'ESRI Shapefile'
EXPORT_FORMAT_GEOPACKAGE = 'GPKG'
EXPORT_FORMAT_GEOJSON = 'GeoJSON'
EXPORT_FORMAT_KML = 'KML'
EXPORT_FORMAT_CSV = 'CSV'

# =============================================================================
# Performance Thresholds (v4.0 Regression Fix: Restored full set)
# =============================================================================
# Feature count thresholds for performance warnings
PERFORMANCE_THRESHOLD_SMALL = 10000      # < 10k: All backends fine
PERFORMANCE_THRESHOLD_MEDIUM = 50000     # 10k-50k: Warn if not PostgreSQL
PERFORMANCE_THRESHOLD_LARGE = 100000     # 50k-100k: Strong warning
PERFORMANCE_THRESHOLD_XLARGE = 500000    # > 500k: Critical warning

# Query duration thresholds for performance warnings (in seconds)
LONG_QUERY_WARNING_THRESHOLD = 10.0      # > 10s: Show warning to user
VERY_LONG_QUERY_WARNING_THRESHOLD = 30.0  # > 30s: Show critical warning

# Small dataset optimization threshold
SMALL_DATASET_THRESHOLD = 5000           # < 5k: Use OGR memory instead of PostgreSQL
DEFAULT_SMALL_DATASET_OPTIMIZATION = True  # Enable small dataset optimization by default

# Backward compatibility aliases
LARGE_DATASET_THRESHOLD = PERFORMANCE_THRESHOLD_MEDIUM
VERY_LARGE_DATASET_THRESHOLD = PERFORMANCE_THRESHOLD_XLARGE

# =============================================================================
# Backend Optimization Constants (v4.0 Regression Fix)
# =============================================================================
# PostgreSQL Materialized View settings
MV_MAX_AGE_SECONDS = 3600               # Max age before auto-cleanup (1 hour)
MV_CLEANUP_INTERVAL = 600               # Check for old MVs every 10 minutes
MV_PREFIX = 'fm_temp_mv_'               # Prefix for MV names (unified fm_temp_* prefix)

# Advanced MV Optimization settings
MV_ENABLE_INDEX_INCLUDE = True          # Use INCLUDE in GIST index (PostgreSQL 11+)
MV_ENABLE_EXTENDED_STATS = True         # Create extended statistics
MV_ENABLE_ASYNC_CLUSTER = True          # Async CLUSTER for medium datasets
MV_ASYNC_CLUSTER_THRESHOLD = 50000      # Features threshold for async CLUSTER
MV_ENABLE_BBOX_COLUMN = True            # Add bbox column for fast pre-filtering
MV_INDEX_FILLFACTOR = 90                # Index fill factor (90=read-heavy, 70=updates)

# Centroid optimization mode
CENTROID_MODE_DEFAULT = 'point_on_surface'
CENTROID_MODE_OPTIONS = ('centroid', 'point_on_surface', 'auto')

# Simplification optimization constants
SIMPLIFY_BEFORE_BUFFER_ENABLED = True   # Enable simplify before buffer in SQL
SIMPLIFY_TOLERANCE_FACTOR = 0.1         # Tolerance = buffer_distance * factor
SIMPLIFY_MIN_TOLERANCE = 0.5            # Minimum tolerance in meters
SIMPLIFY_MAX_TOLERANCE = 10.0           # Maximum tolerance in meters
SIMPLIFY_VERTEX_THRESHOLD = 100         # Only simplify if avg vertices > threshold
SIMPLIFY_FEATURE_THRESHOLD = 500        # Only simplify if features > threshold
SIMPLIFY_PRESERVE_TOPOLOGY = True       # Use ST_SimplifyPreserveTopology

# Spatialite WKT Cache settings
WKT_CACHE_MAX_SIZE = 10                 # Max number of WKT geometries to cache
WKT_CACHE_MAX_LENGTH = 500000           # Max WKT length to cache (500KB)
WKT_CACHE_TTL_SECONDS = 300             # Cache TTL (5 minutes)

# OGR Spatial Index settings
SPATIAL_INDEX_AUTO_CREATE = True        # Auto-create spatial indexes
SPATIAL_INDEX_MIN_FEATURES = 1000       # Min features to trigger auto-index

# Factory Cache settings
FACTORY_CACHE_MAX_AGE = 300             # Max cache age (5 minutes)
FACTORY_CACHE_CHECK_INTERVAL = 60       # Check cache validity every minute

# =============================================================================
# Auto-Optimization Constants
# =============================================================================
# Centroid optimization thresholds
CENTROID_AUTO_THRESHOLD_DISTANT = 5000      # Auto-enable for distant layers > 5k features
CENTROID_AUTO_THRESHOLD_LOCAL = 50000       # Auto-enable for local layers > 50k features

# Geometry simplification thresholds
SIMPLIFY_AUTO_THRESHOLD = 100000            # Auto-simplify for layers > 100k features

# Large WKT thresholds (chars)
LARGE_WKT_THRESHOLD = 100000                # Use R-tree optimization above this
VERY_LARGE_WKT_THRESHOLD = 500000           # Force aggressive optimization

# Vertex complexity thresholds
HIGH_COMPLEXITY_VERTICES = 50               # Average vertices per feature for "complex"
VERY_HIGH_COMPLEXITY_VERTICES = 200         # Average vertices for "very complex"

# Auto-optimization feature flags (can be overridden in config)
AUTO_OPTIMIZE_CENTROID_ENABLED = True       # Enable automatic centroid for distant layers
AUTO_OPTIMIZE_SIMPLIFY_ENABLED = False      # Enable automatic simplification (lossy, disabled)
AUTO_OPTIMIZE_STRATEGY_ENABLED = True       # Enable automatic strategy selection

# =============================================================================
# Connection Pool Constants
# =============================================================================
CONNECTION_POOL_MIN = 2                 # Minimum connections to keep open
CONNECTION_POOL_MAX = 15                # Maximum connections allowed
CONNECTION_POOL_TIMEOUT = 30            # Seconds to wait for available connection
CONNECTION_POOL_IDLE_TIMEOUT = 180      # Seconds before closing idle connections
CONNECTION_POOL_HEALTH_CHECK_INTERVAL = 60  # Seconds between health checks
CONNECTION_POOL_VALIDATION_QUERY = "SELECT 1"  # Query to validate connection

# Circuit Breaker settings
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5   # Failures before opening circuit
CIRCUIT_BREAKER_SUCCESS_THRESHOLD = 2   # Successes to close circuit
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 30.0  # Seconds before testing recovery

# =============================================================================
# SQLite/Spatialite Retry Constants
# =============================================================================
SQLITE_MAX_RETRIES = 5                  # Maximum retry attempts
SQLITE_BASE_DELAY = 0.1                 # Base delay in seconds (100ms)
SQLITE_MAX_DELAY = 5.0                  # Maximum delay in seconds
SQLITE_JITTER_FACTOR = 0.1              # Random jitter factor (0.1 = 10%)
SQLITE_TIMEOUT = 30.0                   # Default timeout in seconds

# =============================================================================
# Flag Manager Constants
# =============================================================================
FLAG_TIMEOUT_LOADING_PROJECT = 30000    # 30 seconds
FLAG_TIMEOUT_INITIALIZING = 30000       # 30 seconds
FLAG_TIMEOUT_PROCESSING_QUEUE = 60000   # 60 seconds
FLAG_TIMEOUT_UPDATING_LAYERS = 15000    # 15 seconds
FLAG_TIMEOUT_PLUGIN_BUSY = 60000        # 60 seconds

# Maximum queue sizes
MAX_ADD_LAYERS_QUEUE = 50               # Maximum queued add_layers operations
MAX_PENDING_TASKS = 10                  # Maximum pending async tasks

# =============================================================================
# Database Defaults
# =============================================================================
DEFAULT_POSTGRES_SCHEMA = 'public'
DEFAULT_TEMP_SCHEMA = 'filtermate_temp'

# Unified naming: all FilterMate objects use fm_temp_* prefix for easy cleanup
TABLE_PREFIX = 'fm_temp_'               # Base prefix for all FilterMate temp objects
TABLE_PREFIX_TEMP = 'fm_temp_tbl_'      # Temporary tables
TABLE_PREFIX_MATERIALIZED = 'fm_temp_mv_'  # Materialized views
TABLE_PREFIX_BUFFER = 'fm_temp_buf_'    # Buffer geometry tables
TABLE_PREFIX_SOURCE = 'fm_temp_src_'    # Source selection tables/MVs

# =============================================================================
# UI Constants
# =============================================================================
TAB_EXPLORING = 0
TAB_FILTERING = 1
TAB_EXPORTING = 2
TAB_CONFIGURATION = 3

WIDGET_STATE_ENABLED = True
WIDGET_STATE_DISABLED = False

MESSAGE_DURATION_SHORT = 3
MESSAGE_DURATION_MEDIUM = 5
MESSAGE_DURATION_LONG = 10

# =============================================================================
# Logging
# =============================================================================
LOG_LEVEL_DEBUG = 'DEBUG'
LOG_LEVEL_INFO = 'INFO'
LOG_LEVEL_WARNING = 'WARNING'
LOG_LEVEL_ERROR = 'ERROR'
LOG_LEVEL_CRITICAL = 'CRITICAL'

# =============================================================================
# File Extensions
# =============================================================================
EXTENSION_SHAPEFILE = '.shp'
EXTENSION_GEOPACKAGE = '.gpkg'
EXTENSION_GEOJSON = '.geojson'
EXTENSION_KML = '.kml'
EXTENSION_SQLITE = '.sqlite'
EXTENSION_QSS = '.qss'

# =============================================================================
# Geometry Type Constants (v4.0 Migration Fix)
# =============================================================================
GEOMETRY_TYPE_POINT = 0
GEOMETRY_TYPE_LINE = 1
GEOMETRY_TYPE_POLYGON = 2
GEOMETRY_TYPE_UNKNOWN = 3
GEOMETRY_TYPE_NULL = 4

# Geometry type string representations
GEOMETRY_TYPE_STRINGS = {
    GEOMETRY_TYPE_POINT: 'Point',
    GEOMETRY_TYPE_LINE: 'Line',
    GEOMETRY_TYPE_POLYGON: 'Polygon',
    GEOMETRY_TYPE_UNKNOWN: 'Unknown',
    GEOMETRY_TYPE_NULL: 'Null',
}

# Legacy format (for backward compatibility with icon_per_geometry_type)
GEOMETRY_TYPE_LEGACY_STRINGS = {
    GEOMETRY_TYPE_POINT: 'GeometryType.Point',
    GEOMETRY_TYPE_LINE: 'GeometryType.Line',
    GEOMETRY_TYPE_POLYGON: 'GeometryType.Polygon',
    GEOMETRY_TYPE_UNKNOWN: 'GeometryType.UnknownGeometry',
    GEOMETRY_TYPE_NULL: 'GeometryType.Null',
}


# =============================================================================
# Utility Functions
# =============================================================================
def get_geometry_type_string(geom_type, legacy_format: bool = False):
    """Get geometry type as string.

    Args:
        geom_type: QGIS geometry type (QgsWkbTypes.GeometryType)
        legacy_format: If True, return 'GeometryType.X' format for icon_per_geometry_type()

    Returns:
        str: Geometry type name

    Examples:
        >>> get_geometry_type_string(0)
        'Point'
        >>> get_geometry_type_string(0, legacy_format=True)
        'GeometryType.Point'
    """
    if legacy_format:
        return GEOMETRY_TYPE_LEGACY_STRINGS.get(geom_type, 'GeometryType.Unknown')
    return GEOMETRY_TYPE_STRINGS.get(geom_type, 'Unknown')


def get_provider_name(qgis_provider_type: str) -> str:
    """
    Convert QGIS provider type to FilterMate provider constant.

    Args:
        qgis_provider_type: Provider type from layer.providerType()

    Returns:
        FilterMate provider constant (PROVIDER_POSTGRES, etc.)

    Example:
        >>> get_provider_name('postgres')
        'postgresql'
    """
    return PROVIDER_TYPE_MAPPING.get(qgis_provider_type, qgis_provider_type)


def get_provider_display_name(provider_type: str) -> str:
    """Get human-readable provider display name."""
    provider_names = {
        PROVIDER_POSTGRES: 'PostgreSQL',
        'postgres': 'PostgreSQL',
        'postgresql': 'PostgreSQL',
        PROVIDER_SPATIALITE: 'SpatiaLite',
        PROVIDER_OGR: 'OGR/File',
        PROVIDER_MEMORY: 'Memory',
    }
    return provider_names.get(provider_type, provider_type)


def get_sql_predicate(predicate_name: str) -> str:
    """
    Get SQL function name for a geometric predicate.

    Args:
        predicate_name: Name of predicate (case-insensitive)

    Returns:
        SQL function name (e.g., 'ST_Intersects')

    Example:
        >>> get_sql_predicate('intersects')
        'ST_Intersects'
        >>> get_sql_predicate('Intersects')
        'ST_Intersects'
    """
    return PREDICATE_SQL_MAPPING.get(predicate_name, f'ST_{predicate_name}')


def should_warn_performance(feature_count: int, has_postgresql: bool = False) -> tuple:
    """
    Determine if performance warning should be shown.

    Args:
        feature_count: Number of features in layer
        has_postgresql: Whether PostgreSQL backend is available

    Returns:
        Tuple of (should_warn: bool, severity: str, message: str)

    Example:
        >>> should_warn_performance(60000, has_postgresql=False)
        (True, 'warning', 'Large dataset without PostgreSQL...')
    """
    if feature_count < PERFORMANCE_THRESHOLD_SMALL:
        return (False, 'info', '')

    if feature_count < PERFORMANCE_THRESHOLD_MEDIUM:
        if not has_postgresql:
            return (True, 'info',
                   f'Dataset has {feature_count} features. Consider PostgreSQL for better performance.')
        return (False, 'info', '')

    if feature_count < PERFORMANCE_THRESHOLD_LARGE:
        if not has_postgresql:
            return (True, 'warning',
                   f'Large dataset ({feature_count} features) without PostgreSQL. Performance may be reduced.')
        return (False, 'info', '')

    if feature_count < PERFORMANCE_THRESHOLD_XLARGE:
        if not has_postgresql:
            return (True, 'warning',
                   f'Very large dataset ({feature_count} features). PostgreSQL strongly recommended.')
        return (True, 'info',
               f'Large dataset ({feature_count} features). Operations may take time.')

    # XLarge datasets
    if not has_postgresql:
        return (True, 'critical',
               f'Extremely large dataset ({feature_count} features). PostgreSQL required for acceptable performance.')
    return (True, 'warning',
           f'Extremely large dataset ({feature_count} features). Operations will take significant time.')


# =============================================================================
# Exports (v4.0 Regression Fix: Complete export list)
# =============================================================================
__all__ = [
    # Provider types (FilterMate backend names)
    'PROVIDER_POSTGRES',
    'PROVIDER_SPATIALITE',
    'PROVIDER_OGR',
    'PROVIDER_MEMORY',
    'PROVIDER_VIRTUAL',
    'PROVIDER_WFS',
    'PROVIDER_ARCGIS',
    'PROVIDER_DELIMITEDTEXT',
    'PROVIDER_GPKG',
    'PROVIDER_MSSQL',
    'PROVIDER_HANA',
    'PROVIDER_ORACLE',
    # QGIS internal provider names (from layer.providerType())
    'QGIS_PROVIDER_POSTGRES',
    'QGIS_PROVIDER_SPATIALITE',
    'QGIS_PROVIDER_OGR',
    'QGIS_PROVIDER_MEMORY',
    'REMOTE_PROVIDERS',
    'PROVIDER_TYPE_MAPPING',
    # Spatial predicates
    'PREDICATE_INTERSECTS',
    'PREDICATE_CONTAINS',
    'PREDICATE_WITHIN',
    'PREDICATE_CROSSES',
    'PREDICATE_TOUCHES',
    'PREDICATE_DISJOINT',
    'PREDICATE_OVERLAPS',
    'PREDICATE_EQUALS',
    'ALL_PREDICATES',
    'PREDICATE_SQL_MAPPING',
    # Task types
    'TASK_FILTER',
    'TASK_UNFILTER',
    'TASK_RESET',
    'TASK_EXPORT',
    'TASK_ADD_LAYERS',
    'TASK_REMOVE_LAYERS',
    # Buffer types
    'BUFFER_TYPE_FIXED',
    'BUFFER_TYPE_EXPRESSION',
    'BUFFER_TYPE_NONE',
    # Combine operators
    'COMBINE_AND',
    'COMBINE_OR',
    # Export formats
    'EXPORT_FORMAT_SHAPEFILE',
    'EXPORT_FORMAT_GEOPACKAGE',
    'EXPORT_FORMAT_GEOJSON',
    'EXPORT_FORMAT_KML',
    'EXPORT_FORMAT_CSV',
    # Performance thresholds
    'PERFORMANCE_THRESHOLD_SMALL',
    'PERFORMANCE_THRESHOLD_MEDIUM',
    'PERFORMANCE_THRESHOLD_LARGE',
    'PERFORMANCE_THRESHOLD_XLARGE',
    'LONG_QUERY_WARNING_THRESHOLD',
    'VERY_LONG_QUERY_WARNING_THRESHOLD',
    'LARGE_DATASET_THRESHOLD',
    'VERY_LARGE_DATASET_THRESHOLD',
    'SMALL_DATASET_THRESHOLD',
    'DEFAULT_SMALL_DATASET_OPTIMIZATION',
    # Backend optimization
    'MV_MAX_AGE_SECONDS',
    'MV_CLEANUP_INTERVAL',
    'MV_PREFIX',
    'MV_ENABLE_INDEX_INCLUDE',
    'MV_ENABLE_EXTENDED_STATS',
    'MV_ENABLE_ASYNC_CLUSTER',
    'MV_ASYNC_CLUSTER_THRESHOLD',
    'MV_ENABLE_BBOX_COLUMN',
    'MV_INDEX_FILLFACTOR',
    'CENTROID_MODE_DEFAULT',
    'CENTROID_MODE_OPTIONS',
    'SIMPLIFY_BEFORE_BUFFER_ENABLED',
    'SIMPLIFY_TOLERANCE_FACTOR',
    'SIMPLIFY_MIN_TOLERANCE',
    'SIMPLIFY_MAX_TOLERANCE',
    'SIMPLIFY_VERTEX_THRESHOLD',
    'SIMPLIFY_FEATURE_THRESHOLD',
    'SIMPLIFY_PRESERVE_TOPOLOGY',
    'WKT_CACHE_MAX_SIZE',
    'WKT_CACHE_MAX_LENGTH',
    'WKT_CACHE_TTL_SECONDS',
    'SPATIAL_INDEX_AUTO_CREATE',
    'SPATIAL_INDEX_MIN_FEATURES',
    'FACTORY_CACHE_MAX_AGE',
    'FACTORY_CACHE_CHECK_INTERVAL',
    # Auto-optimization
    'CENTROID_AUTO_THRESHOLD_DISTANT',
    'CENTROID_AUTO_THRESHOLD_LOCAL',
    'SIMPLIFY_AUTO_THRESHOLD',
    'LARGE_WKT_THRESHOLD',
    'VERY_LARGE_WKT_THRESHOLD',
    'HIGH_COMPLEXITY_VERTICES',
    'VERY_HIGH_COMPLEXITY_VERTICES',
    'AUTO_OPTIMIZE_CENTROID_ENABLED',
    'AUTO_OPTIMIZE_SIMPLIFY_ENABLED',
    'AUTO_OPTIMIZE_STRATEGY_ENABLED',
    # Connection pool
    'CONNECTION_POOL_MIN',
    'CONNECTION_POOL_MAX',
    'CONNECTION_POOL_TIMEOUT',
    'CONNECTION_POOL_IDLE_TIMEOUT',
    'CONNECTION_POOL_HEALTH_CHECK_INTERVAL',
    'CONNECTION_POOL_VALIDATION_QUERY',
    'CIRCUIT_BREAKER_FAILURE_THRESHOLD',
    'CIRCUIT_BREAKER_SUCCESS_THRESHOLD',
    'CIRCUIT_BREAKER_RECOVERY_TIMEOUT',
    # SQLite/Spatialite
    'SQLITE_MAX_RETRIES',
    'SQLITE_BASE_DELAY',
    'SQLITE_MAX_DELAY',
    'SQLITE_JITTER_FACTOR',
    'SQLITE_TIMEOUT',
    # Flag manager
    'FLAG_TIMEOUT_LOADING_PROJECT',
    'FLAG_TIMEOUT_INITIALIZING',
    'FLAG_TIMEOUT_PROCESSING_QUEUE',
    'FLAG_TIMEOUT_UPDATING_LAYERS',
    'FLAG_TIMEOUT_PLUGIN_BUSY',
    'MAX_ADD_LAYERS_QUEUE',
    'MAX_PENDING_TASKS',
    # Database defaults
    'DEFAULT_POSTGRES_SCHEMA',
    'DEFAULT_TEMP_SCHEMA',
    'TABLE_PREFIX_TEMP',
    'TABLE_PREFIX_MATERIALIZED',
    # UI constants
    'TAB_EXPLORING',
    'TAB_FILTERING',
    'TAB_EXPORTING',
    'TAB_CONFIGURATION',
    'WIDGET_STATE_ENABLED',
    'WIDGET_STATE_DISABLED',
    'MESSAGE_DURATION_SHORT',
    'MESSAGE_DURATION_MEDIUM',
    'MESSAGE_DURATION_LONG',
    # Logging
    'LOG_LEVEL_DEBUG',
    'LOG_LEVEL_INFO',
    'LOG_LEVEL_WARNING',
    'LOG_LEVEL_ERROR',
    'LOG_LEVEL_CRITICAL',
    # File extensions
    'EXTENSION_SHAPEFILE',
    'EXTENSION_GEOPACKAGE',
    'EXTENSION_GEOJSON',
    'EXTENSION_KML',
    'EXTENSION_SQLITE',
    'EXTENSION_QSS',
    # Geometry types
    'GEOMETRY_TYPE_POINT',
    'GEOMETRY_TYPE_LINE',
    'GEOMETRY_TYPE_POLYGON',
    'GEOMETRY_TYPE_UNKNOWN',
    'GEOMETRY_TYPE_NULL',
    'GEOMETRY_TYPE_STRINGS',
    'GEOMETRY_TYPE_LEGACY_STRINGS',
    # Functions
    'get_geometry_type_string',
    'get_provider_name',
    'get_provider_display_name',
    'get_sql_predicate',
    'should_warn_performance',
]

"""
FilterMate Constants Module

Centralized constants for provider types, geometry types, and other shared values.
This module eliminates magic strings and numbers throughout the codebase.

Usage:
    from modules.constants import PROVIDER_POSTGRES, GEOMETRY_TYPE_POINT
"""

# ============================================================================
# Provider Types
# ============================================================================

PROVIDER_POSTGRES = 'postgresql'
PROVIDER_SPATIALITE = 'spatialite'
PROVIDER_OGR = 'ogr'
PROVIDER_MEMORY = 'memory'

# Provider type mapping from QGIS internal names
PROVIDER_TYPE_MAPPING = {
    'postgres': PROVIDER_POSTGRES,
    'spatialite': PROVIDER_SPATIALITE,
    'ogr': PROVIDER_OGR,
    'memory': PROVIDER_MEMORY,
}

# ============================================================================
# Geometry Types
# ============================================================================

# QGIS QgsWkbTypes enum values
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

# Alternative string formats (for backward compatibility)
GEOMETRY_TYPE_LEGACY_STRINGS = {
    GEOMETRY_TYPE_POINT: 'GeometryType.Point',
    GEOMETRY_TYPE_LINE: 'GeometryType.Line',
    GEOMETRY_TYPE_POLYGON: 'GeometryType.Polygon',
    GEOMETRY_TYPE_UNKNOWN: 'GeometryType.Unknown',
    GEOMETRY_TYPE_NULL: 'GeometryType.Null',
}

# ============================================================================
# Spatial Predicates
# ============================================================================

# Geometric predicates for spatial filtering
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

# Predicate mapping to SQL functions (lowercase variants)
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
    # Lowercase variants
    'intersects': 'ST_Intersects',
    'within': 'ST_Within',
    'contains': 'ST_Contains',
    'overlaps': 'ST_Overlaps',
    'crosses': 'ST_Crosses',
    'touches': 'ST_Touches',
    'disjoint': 'ST_Disjoint',
    'equals': 'ST_Equals',
}

# ============================================================================
# Task Types
# ============================================================================

TASK_FILTER = 'filter'
TASK_UNFILTER = 'unfilter'
TASK_RESET = 'reset'
TASK_EXPORT = 'export'
TASK_ADD_LAYERS = 'add_layers'
TASK_REMOVE_LAYERS = 'remove_layers'

# ============================================================================
# Buffer Types
# ============================================================================

BUFFER_TYPE_FIXED = 'fixed'
BUFFER_TYPE_EXPRESSION = 'expression'
BUFFER_TYPE_NONE = None

# ============================================================================
# Combine Operators
# ============================================================================

COMBINE_AND = 'AND'
COMBINE_OR = 'OR'

# ============================================================================
# Export Formats
# ============================================================================

EXPORT_FORMAT_SHAPEFILE = 'ESRI Shapefile'
EXPORT_FORMAT_GEOPACKAGE = 'GPKG'
EXPORT_FORMAT_GEOJSON = 'GeoJSON'
EXPORT_FORMAT_KML = 'KML'
EXPORT_FORMAT_CSV = 'CSV'

# ============================================================================
# Performance Thresholds
# ============================================================================

# Feature count thresholds for performance warnings
PERFORMANCE_THRESHOLD_SMALL = 10000      # < 10k: All backends fine
PERFORMANCE_THRESHOLD_MEDIUM = 50000     # 10k-50k: Warn if not PostgreSQL
PERFORMANCE_THRESHOLD_LARGE = 100000     # 50k-100k: Strong warning
PERFORMANCE_THRESHOLD_XLARGE = 500000    # > 500k: Critical warning

# Small dataset optimization threshold
# PostgreSQL layers below this threshold will use OGR memory backend for faster filtering
SMALL_DATASET_THRESHOLD = 5000           # < 5k: Use OGR memory instead of PostgreSQL
DEFAULT_SMALL_DATASET_OPTIMIZATION = True  # Enable small dataset optimization by default

# ============================================================================
# Database Defaults
# ============================================================================

# Default schema names
DEFAULT_POSTGRES_SCHEMA = 'public'
DEFAULT_TEMP_SCHEMA = 'filtermate_temp'

# Default table prefixes
TABLE_PREFIX_TEMP = 'fm_temp_'
TABLE_PREFIX_MATERIALIZED = 'fm_mv_'

# ============================================================================
# UI Constants
# ============================================================================

# Tab indices
TAB_EXPLORING = 0
TAB_FILTERING = 1
TAB_EXPORTING = 2
TAB_CONFIGURATION = 3

# Widget state flags
WIDGET_STATE_ENABLED = True
WIDGET_STATE_DISABLED = False

# Message bar durations (seconds)
MESSAGE_DURATION_SHORT = 3
MESSAGE_DURATION_MEDIUM = 5
MESSAGE_DURATION_LONG = 10

# ============================================================================
# Logging
# ============================================================================

LOG_LEVEL_DEBUG = 'DEBUG'
LOG_LEVEL_INFO = 'INFO'
LOG_LEVEL_WARNING = 'WARNING'
LOG_LEVEL_ERROR = 'ERROR'
LOG_LEVEL_CRITICAL = 'CRITICAL'

# ============================================================================
# File Extensions
# ============================================================================

EXTENSION_SHAPEFILE = '.shp'
EXTENSION_GEOPACKAGE = '.gpkg'
EXTENSION_GEOJSON = '.geojson'
EXTENSION_KML = '.kml'
EXTENSION_SQLITE = '.sqlite'
EXTENSION_QSS = '.qss'

# ============================================================================
# Helper Functions
# ============================================================================

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


def get_geometry_type_string(geometry_type: int, legacy_format: bool = False) -> str:
    """
    Convert geometry type integer to string representation.
    
    Args:
        geometry_type: Integer from QgsWkbTypes
        legacy_format: If True, returns 'GeometryType.Point' format
        
    Returns:
        String representation of geometry type
        
    Example:
        >>> get_geometry_type_string(0)
        'Point'
        >>> get_geometry_type_string(0, legacy_format=True)
        'GeometryType.Point'
    """
    if legacy_format:
        return GEOMETRY_TYPE_LEGACY_STRINGS.get(geometry_type, 'GeometryType.Unknown')
    return GEOMETRY_TYPE_STRINGS.get(geometry_type, 'Unknown')


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

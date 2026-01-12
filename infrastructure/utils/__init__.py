"""
FilterMate Infrastructure Utilities.

Common utility functions and helper classes:
- provider_utils: Provider type detection and utilities
- validation_utils: Layer and expression validation
- layer_utils: Layer data source connection and metadata
- task_utils: Database connection and CRS utilities for tasks
- complexity_estimator: Query complexity estimation and strategy recommendation
- sql_utils: SQL sanitization and safety functions
- field_utils: Field and value utilities

Migrated from modules/ (EPIC-1 v3.0).
"""
from .provider_utils import (
    ProviderType,
    detect_provider_type,
    is_postgresql,
    is_spatialite,
    is_ogr,
    is_memory,
    get_provider_display_name,
)
from .validation_utils import (
    is_sip_deleted,
    is_layer_valid,
    is_layer_source_available,
    validate_expression,
    validate_expression_syntax,
    validate_layers,
    get_layer_validation_info,
    safe_layer_access,
    safe_get_layer_name,
    safe_get_layer_id,
    safe_get_layer_source,
)
from .layer_utils import (
    detect_layer_provider_type,
    get_datasource_connexion_from_layer,
    get_data_source_uri,
    get_primary_key_name,
    get_best_display_field,
    validate_and_cleanup_postgres_layers,
    POSTGRESQL_AVAILABLE,
    PSYCOPG2_AVAILABLE,
    CRS_UTILS_AVAILABLE,
    DEFAULT_METRIC_CRS,
    PROVIDER_POSTGRES,
    PROVIDER_SPATIALITE,
    PROVIDER_OGR,
    PROVIDER_MEMORY,
)
from .task_utils import (
    spatialite_connect,
    safe_spatialite_connect,
    sqlite_execute_with_retry,
    ensure_db_directory_exists,
    get_best_metric_crs,
    should_reproject_layer,
    needs_metric_conversion,
    SQLITE_TIMEOUT,
    SQLITE_MAX_RETRIES,
    SQLITE_RETRY_DELAY,
    SQLITE_MAX_RETRY_TIME,
    MESSAGE_TASKS_CATEGORIES,
)
from .complexity_estimator import (
    QueryComplexity,
    ComplexityBreakdown,
    OperationCosts,
    QueryComplexityEstimator,
    get_complexity_estimator,
    estimate_query_complexity,
)

# Import SQL utilities (from infrastructure.database)
from ..database.sql_utils import (
    safe_set_subset_string,
    sanitize_sql_identifier,
)

# Import field utilities (from infrastructure)
from ..field_utils import clean_buffer_value

# Import source filter builder utilities (from core.filter)
try:
    from ...core.filter.source_filter_builder import get_source_table_name
except ImportError:
    def get_source_table_name(layer, param_source_table=None):
        """Fallback for get_source_table_name."""
        if param_source_table:
            return param_source_table
        if not layer:
            return None
        try:
            from qgis.core import QgsDataSourceUri
            uri = QgsDataSourceUri(layer.source())
            return uri.table()
        except Exception:
            return layer.name() if hasattr(layer, 'name') else None

# Import batch exporter utilities (from core.export)
try:
    from ...core.export.batch_exporter import sanitize_filename
except ImportError:
    import re as _re
    def sanitize_filename(filename):
        """Fallback for sanitize_filename."""
        if not filename:
            return "unnamed"
        sanitized = _re.sub(r'[<>:"/\\|?*]', '_', str(filename))
        return sanitized.strip('.')[:255] or "unnamed"

# Utility functions for geometry and signals
def geometry_type_to_string(geom_type):
    """
    Convert QgsWkbTypes geometry type to string representation.
    
    Args:
        geom_type: QgsWkbTypes geometry type enum
        
    Returns:
        str: Human-readable geometry type string
    """
    try:
        from qgis.core import QgsWkbTypes
        type_map = {
            QgsWkbTypes.PointGeometry: "Point",
            QgsWkbTypes.LineGeometry: "LineString",
            QgsWkbTypes.PolygonGeometry: "Polygon",
            QgsWkbTypes.NullGeometry: "NoGeometry",
            QgsWkbTypes.UnknownGeometry: "Unknown",
        }
        return type_map.get(geom_type, str(geom_type))
    except Exception:
        return str(geom_type)


def is_qgis_alive():
    """
    Check if QGIS application is still running and accessible.
    
    Returns:
        bool: True if QGIS is alive, False otherwise
    """
    try:
        from qgis.core import QgsApplication
        return QgsApplication.instance() is not None
    except Exception:
        return False


class GdalErrorHandler:
    """
    Context manager to suppress GDAL errors during operations.
    
    Use this when performing operations that may trigger non-critical
    GDAL errors that would otherwise pollute the console.
    
    Example:
        with GdalErrorHandler():
            layer.reload()
    """
    def __init__(self):
        self.previous_handler = None
        
    def __enter__(self):
        try:
            from osgeo import gdal
            self.previous_handler = gdal.GetErrorHandler()
            gdal.PushErrorHandler('CPLQuietErrorHandler')
        except Exception:
            pass
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            from osgeo import gdal
            gdal.PopErrorHandler()
        except Exception:
            pass
        return False


def safe_disconnect(signal, slot):
    """
    Safely disconnect a signal from a slot.
    
    Handles cases where the signal is not connected or objects are deleted.
    
    Args:
        signal: Qt signal to disconnect
        slot: Slot to disconnect from the signal
    """
    try:
        signal.disconnect(slot)
    except (RuntimeError, TypeError):
        pass  # Signal was not connected or objects deleted

__all__ = [
    # Provider utils
    'ProviderType',
    'detect_provider_type',
    'is_postgresql',
    'is_spatialite',
    'is_ogr',
    'is_memory',
    'get_provider_display_name',
    # Validation utils
    'is_sip_deleted',
    'is_layer_valid',
    'is_layer_source_available',
    'validate_expression',
    'validate_expression_syntax',
    'validate_layers',
    'get_layer_validation_info',
    'safe_layer_access',
    'safe_get_layer_name',
    'safe_get_layer_id',
    'safe_get_layer_source',
    # Layer utils (EPIC-1 migration)
    'detect_layer_provider_type',
    'get_datasource_connexion_from_layer',
    'get_data_source_uri',
    'get_primary_key_name',
    'get_best_display_field',
    'validate_and_cleanup_postgres_layers',
    'POSTGRESQL_AVAILABLE',
    'PSYCOPG2_AVAILABLE',
    'CRS_UTILS_AVAILABLE',
    'DEFAULT_METRIC_CRS',
    'PROVIDER_POSTGRES',
    'PROVIDER_SPATIALITE',
    'PROVIDER_OGR',
    'PROVIDER_MEMORY',
    # Task utils (EPIC-1 migration)
    'spatialite_connect',
    'safe_spatialite_connect',
    'sqlite_execute_with_retry',
    'ensure_db_directory_exists',
    'get_best_metric_crs',
    'should_reproject_layer',
    'needs_metric_conversion',
    'SQLITE_TIMEOUT',
    'SQLITE_MAX_RETRIES',
    'SQLITE_RETRY_DELAY',
    'SQLITE_MAX_RETRY_TIME',
    'MESSAGE_TASKS_CATEGORIES',
    # Complexity estimator (EPIC-1 migration)
    'QueryComplexity',
    'ComplexityBreakdown',
    'OperationCosts',
    'QueryComplexityEstimator',
    'get_complexity_estimator',
    'estimate_query_complexity',
    # SQL utilities (from infrastructure.database)
    'safe_set_subset_string',
    'sanitize_sql_identifier',
    # Field utilities
    'clean_buffer_value',
    # Source filter utilities
    'get_source_table_name',
    # Export utilities
    'sanitize_filename',
    # Geometry and signal utilities
    'geometry_type_to_string',
    'safe_disconnect',
    # QGIS safety utilities
    'is_qgis_alive',
    'GdalErrorHandler',
]

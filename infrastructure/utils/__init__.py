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
from .provider_utils import (  # noqa: F401
    ProviderType,
    detect_provider_type,
    is_postgresql,
    is_spatialite,
    is_ogr,
    is_memory,
    get_provider_display_name,
)
from .validation_utils import (  # noqa: F401
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
    # v4.1.0: Expression type detection for filtering
    is_filter_expression,
    is_display_expression,
    should_skip_expression_for_filtering,
)
from .layer_utils import (  # noqa: F401
    detect_layer_provider_type,
    get_datasource_connexion_from_layer,
    get_data_source_uri,
    get_spatialite_datasource_from_layer,
    get_primary_key_name,
    get_best_display_field,
    validate_and_cleanup_postgres_layers,
    POSTGRESQL_AVAILABLE,
    PSYCOPG2_AVAILABLE,
    DEFAULT_METRIC_CRS,
    PROVIDER_POSTGRES,
    PROVIDER_SPATIALITE,
    PROVIDER_OGR,
    PROVIDER_MEMORY,
    # ValueRelation utilities (EPIC-1 migration)
    is_value_relation_layer_available,
    get_value_relation_info,
    get_field_display_expression,
    get_layer_display_expression,
    get_fields_with_value_relations,
    # GeoPackage utilities
    is_valid_geopackage,
    get_geopackage_path,
    get_geopackage_related_layers,
    # MV utilities
    detect_filtermate_mv_reference,
    validate_mv_exists,
    clear_orphaned_mv_subset,
    # Filter cleanup
    cleanup_corrupted_layer_filters,
    # Utility functions
    truncate,
    escape_json_string,
)
from .task_utils import (  # noqa: F401
    spatialite_connect,
    sqlite_connect,
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
from .complexity_estimator import (  # noqa: F401
    QueryComplexity,
    ComplexityBreakdown,
    OperationCosts,
    QueryComplexityEstimator,
    get_complexity_estimator,
    estimate_query_complexity,
)
from .signal_utils import (  # noqa: F401
    is_layer_in_project,
    safe_disconnect,
    safe_emit,
    safe_set_layer_variable,
    safe_set_layer_variables,
)

# Import SQL utilities (from infrastructure.database)
from ..database.sql_utils import (  # noqa: F401
    safe_set_subset_string,
    sanitize_sql_identifier,
)

# Import field utilities (from infrastructure)
from ..field_utils import clean_buffer_value  # noqa: F401

# Import source filter builder utilities (from core.filter)
try:
    from ...core.filter.source_filter_builder import get_source_table_name  # noqa: F401
except ImportError:
    def get_source_table_name(layer, param_source_table=None):
        """Fallback for get_source_table_name."""
        if param_source_table:
            return param_source_table
        if not layer:
            return None
        try:
            from qgis.core import QgsDataSourceUri  # noqa: F401
            uri = QgsDataSourceUri(layer.source())
            return uri.table()
        except Exception:
            return layer.name() if hasattr(layer, 'name') else None

# Import batch exporter utilities (from core.export)
try:
    from ...core.export.batch_exporter import sanitize_filename  # noqa: F401
except ImportError:
    import re as _re  # noqa: F401

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

    v4.0.1: REGRESSION FIX - Returns legacy format ('GeometryType.Point')
    for compatibility with icon_per_geometry_type() and PROJECT_LAYERS.

    Args:
        geom_type: QgsWkbTypes geometry type enum OR QgsVectorLayer

    Returns:
        str: Geometry type string in legacy format ('GeometryType.Point', etc.)
    """
    try:
        from qgis.core import QgsWkbTypes, QgsVectorLayer  # noqa: F401

        # Handle if a layer is passed instead of geometry type
        if isinstance(geom_type, QgsVectorLayer):
            geom_type = geom_type.geometryType()

        # Return LEGACY format for compatibility with v2.3.8
        type_map = {
            QgsWkbTypes.PointGeometry: "GeometryType.Point",
            QgsWkbTypes.LineGeometry: "GeometryType.Line",
            QgsWkbTypes.PolygonGeometry: "GeometryType.Polygon",
            QgsWkbTypes.NullGeometry: "GeometryType.UnknownGeometry",
            QgsWkbTypes.UnknownGeometry: "GeometryType.UnknownGeometry",
        }
        return type_map.get(geom_type, "GeometryType.UnknownGeometry")
    except Exception:
        return "GeometryType.UnknownGeometry"


def is_qgis_alive():
    """
    Check if QGIS application is still running and accessible.

    Returns:
        bool: True if QGIS is alive, False otherwise
    """
    try:
        from qgis.core import QgsApplication  # noqa: F401
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
            from osgeo import gdal  # noqa: F401
            self.previous_handler = gdal.GetErrorHandler()
            gdal.PushErrorHandler('CPLQuietErrorHandler')
        except Exception:
            pass
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            from osgeo import gdal  # noqa: F401
            gdal.PopErrorHandler()
        except Exception:
            pass
        return False


def safe_iterate_features(layer_or_source, request=None, max_retries=5, retry_delay=0.3):
    """
    Safely iterate over features from a layer or feature source.

    Handles OGR/GeoPackage errors like "unable to open database file" with retry logic.
    Suppresses transient GDAL/OGR warnings that are handled internally.

    IMPORTANT: For multi-layer filtering with Spatialite/GeoPackage, concurrent database
    access can cause transient "unable to open database file" errors. This function uses
    exponential backoff to wait for database locks to clear.

    Args:
        layer_or_source: QgsVectorLayer, QgsVectorDataProvider, or QgsAbstractFeatureSource
        request: Optional QgsFeatureRequest
        max_retries: Number of retry attempts (default 5, increased for concurrent access)
        retry_delay: Initial delay between retries in seconds (default 0.3)

    Yields:
        Features from the layer/source

    Example:
        for feature in safe_iterate_features(layer):
            process_feature(feature)
    """
    import time  # noqa: F401
    import logging  # noqa: F401

    logger = logging.getLogger('FilterMate')

    # Use GDAL error handler to suppress transient SQLite warnings during iteration
    with GdalErrorHandler():
        for attempt in range(max_retries):
            try:
                if request:
                    iterator = layer_or_source.getFeatures(request)
                else:
                    iterator = layer_or_source.getFeatures()

                for feature in iterator:
                    yield feature
                return  # Successfully completed iteration

            except Exception as e:
                error_str = str(e).lower()

                # Check for known recoverable OGR/SQLite errors
                is_recoverable = any(x in error_str for x in [
                    'unable to open database file',
                    'database is locked',
                    'disk i/o error',
                    'sqlite3_step',
                    'busy',
                ])

                if is_recoverable and attempt < max_retries - 1:
                    layer_name = getattr(layer_or_source, 'name', lambda: 'unknown')()
                    logger.debug(
                        f"OGR access retry on '{layer_name}' (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Waiting {retry_delay:.2f}s..."
                    )
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 5.0)  # Exponential backoff, max 5 seconds
                else:
                    layer_name = getattr(layer_or_source, 'name', lambda: 'unknown')()
                    logger.error(f"Failed to iterate features from '{layer_name}' after {max_retries} attempts: {e}")
                    return  # Stop iteration on unrecoverable error


def get_feature_attribute(feature, field_name):
    """
    Safely get an attribute value from a feature.

    Handles special cases like 'fid' which may be a pseudo-field
    representing the feature ID rather than an actual attribute.

    Args:
        feature: QgsFeature object
        field_name: Name of the field to retrieve

    Returns:
        The attribute value, or None if not found

    Example:
        value = get_feature_attribute(feature, 'name')
        fid = get_feature_attribute(feature, 'fid')  # Gets feature.id() as fallback
    """
    import logging  # noqa: F401

    logger = logging.getLogger('FilterMate')

    if field_name is None:
        return None

    # Handle special case for 'fid' (feature ID)
    # In QGIS, 'fid' is often a pseudo-column representing feature.id()
    if field_name.lower() == 'fid':
        try:
            # First try to get it as a regular attribute
            return feature[field_name]
        except (KeyError, IndexError):
            # Fall back to feature.id() if 'fid' is not a real field
            return feature.id()

    # For regular fields, try to access by name
    try:
        return feature[field_name]
    except (KeyError, IndexError):
        # If field access fails, try to get by index
        try:
            fields = feature.fields()
            idx = fields.lookupField(field_name)
            if idx >= 0:
                return feature.attributes()[idx]
        except (KeyError, IndexError, AttributeError) as e:
            logger.debug(f"Could not get feature attribute '{field_name}': {e}")
        return None


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
    'get_spatialite_datasource_from_layer',
    'get_primary_key_name',
    'get_best_display_field',
    'validate_and_cleanup_postgres_layers',
    'POSTGRESQL_AVAILABLE',
    'PSYCOPG2_AVAILABLE',
    'DEFAULT_METRIC_CRS',
    'PROVIDER_POSTGRES',
    'PROVIDER_SPATIALITE',
    'PROVIDER_OGR',
    'PROVIDER_MEMORY',
    # ValueRelation utilities (EPIC-1 migration)
    'is_value_relation_layer_available',
    'get_value_relation_info',
    'get_field_display_expression',
    'get_layer_display_expression',
    'get_fields_with_value_relations',
    # GeoPackage utilities
    'is_valid_geopackage',
    'get_geopackage_path',
    'get_geopackage_related_layers',
    # MV utilities
    'detect_filtermate_mv_reference',
    'validate_mv_exists',
    'clear_orphaned_mv_subset',
    # Filter cleanup
    'cleanup_corrupted_layer_filters',
    # Utility functions
    'truncate',
    'escape_json_string',
    # Task utils (EPIC-1 migration)
    'spatialite_connect',
    'sqlite_connect',
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
    # QGIS safety utilities
    'is_qgis_alive',
    'GdalErrorHandler',
    # Signal and layer variable utilities (EPIC-1 migration)
    'is_layer_in_project',
    'safe_disconnect',
    'safe_emit',
    'safe_set_layer_variable',
    'safe_set_layer_variables',
    # Feature iteration utilities (EPIC-1 migration from widgets.py)
    'safe_iterate_features',
    'get_feature_attribute',
]

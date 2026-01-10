"""
FilterMate Infrastructure Utilities.

Common utility functions and helper classes:
- provider_utils: Provider type detection and utilities
- validation_utils: Layer and expression validation
- layer_utils: Layer data source connection and metadata
- task_utils: Database connection and CRS utilities for tasks

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
]

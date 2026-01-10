"""
FilterMate Infrastructure Utilities.

Common utility functions and helper classes.
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
]

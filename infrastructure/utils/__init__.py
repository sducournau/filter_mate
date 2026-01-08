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
]

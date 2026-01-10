# -*- coding: utf-8 -*-
"""
DEPRECATED: Legacy compatibility shim for modules/appUtils

Migrated to infrastructure/utils/layer_utils.py (EPIC-1)
This file provides backward compatibility only.

Migration Guide:
    OLD: from modules.appUtils import get_datasource_connexion_from_layer
    NEW: from infrastructure.utils import get_datasource_connexion_from_layer
"""
import warnings

warnings.warn(
    "modules.appUtils is deprecated. Use infrastructure.utils instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export ALL functions from new location (infrastructure/utils/layer_utils.py)
try:
    from ..infrastructure.utils import (
        # Provider detection
        detect_layer_provider_type,
        PROVIDER_POSTGRES,
        PROVIDER_SPATIALITE,
        PROVIDER_OGR,
        PROVIDER_MEMORY,
        
        # PostgreSQL connection
        get_datasource_connexion_from_layer,
        get_data_source_uri,
        POSTGRESQL_AVAILABLE,
        PSYCOPG2_AVAILABLE,
        
        # Field utilities
        get_primary_key_name,
        get_best_display_field,
        
        # Validation
        validate_and_cleanup_postgres_layers,
        is_layer_source_available,
        is_layer_valid as is_valid_layer,  # Alias for backward compatibility
        
        # CRS constants
        CRS_UTILS_AVAILABLE,
        DEFAULT_METRIC_CRS,
    )
except ImportError as e:
    # Fallback imports if infrastructure not available
    import logging
    logging.getLogger(__name__).warning(f"Failed to import from infrastructure.utils: {e}")
    
    POSTGRESQL_AVAILABLE = True
    PSYCOPG2_AVAILABLE = False
    CRS_UTILS_AVAILABLE = False
    DEFAULT_METRIC_CRS = "EPSG:3857"
    PROVIDER_POSTGRES = 'postgresql'
    PROVIDER_SPATIALITE = 'spatialite'
    PROVIDER_OGR = 'ogr'
    PROVIDER_MEMORY = 'memory'
    
    def get_datasource_connexion_from_layer(layer):
        return None, None
    
    def get_best_display_field(layer, sample_size=10, use_value_relations=True):
        try:
            fields = layer.fields()
            if fields.count() > 0:
                return fields[0].name()
        except:
            pass
        return ""
    
    def is_layer_source_available(layer):
        try:
            return layer is not None and layer.isValid()
        except:
            return False
    
    def is_valid_layer(layer):
        return is_layer_source_available(layer)
    
    def detect_layer_provider_type(layer):
        try:
            return layer.providerType()
        except:
            return 'unknown'
    
    def get_data_source_uri(layer):
        return None, None
    
    def get_primary_key_name(layer):
        return None
    
    def validate_and_cleanup_postgres_layers(layers):
        return []

__all__ = [
    'detect_layer_provider_type',
    'get_datasource_connexion_from_layer',
    'get_data_source_uri',
    'get_primary_key_name',
    'get_best_display_field',
    'validate_and_cleanup_postgres_layers',
    'is_layer_source_available',
    'is_valid_layer',
    'POSTGRESQL_AVAILABLE',
    'PSYCOPG2_AVAILABLE',
    'CRS_UTILS_AVAILABLE',
    'DEFAULT_METRIC_CRS',
    'PROVIDER_POSTGRES',
    'PROVIDER_SPATIALITE',
    'PROVIDER_OGR',
    'PROVIDER_MEMORY',
]

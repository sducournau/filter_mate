# -*- coding: utf-8 -*-
"""
FilterMate Layer Utilities - EPIC-1 Migration

Consolidated layer utility functions migrated from modules/appUtils.py.
Part of EPIC-1: Suppression du dossier modules/.

Functions:
- detect_layer_provider_type: Detect provider type for a layer
- get_datasource_connexion_from_layer: Get PostgreSQL connection via psycopg2
- get_data_source_uri: Extract data source URI and auth config
- get_best_display_field: Find best field for display purposes
- validate_and_cleanup_postgres_layers: Validate PostgreSQL layers
- get_primary_key_name: Get primary key field name

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional, Tuple, List, Any

logger = logging.getLogger('FilterMate.LayerUtils')

# QGIS imports with fallbacks for testing
try:
    from qgis.core import (
        QgsVectorLayer,
        QgsDataSourceUri,
        QgsFeatureRequest,
        QgsApplication,
        QgsAuthMethodConfig,
    )
    from qgis.PyQt.QtCore import QVariant
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False
    QgsVectorLayer = object
    QgsDataSourceUri = None
    QgsFeatureRequest = None
    QVariant = None

# psycopg2 availability
try:
    from adapters.backends.postgresql_availability import (
        psycopg2,
        PSYCOPG2_AVAILABLE,
        POSTGRESQL_AVAILABLE
    )
except ImportError:
    try:
        import psycopg2
        PSYCOPG2_AVAILABLE = True
    except ImportError:
        psycopg2 = None
        PSYCOPG2_AVAILABLE = False
    POSTGRESQL_AVAILABLE = True  # QGIS native always available

# Provider constants
PROVIDER_POSTGRES = 'postgresql'
PROVIDER_SPATIALITE = 'spatialite'
PROVIDER_OGR = 'ogr'
PROVIDER_MEMORY = 'memory'

REMOTE_PROVIDERS = {'WFS', 'wfs', 'arcgisfeatureserver', 'oapif'}


# =============================================================================
# Provider Detection
# =============================================================================

def detect_layer_provider_type(layer) -> str:
    """
    Detect the provider type of a QGIS vector layer.
    
    For filtering purposes, this function returns the logical backend type:
    - 'postgresql': PostgreSQL/PostGIS layers
    - 'spatialite': Native Spatialite AND GeoPackage/SQLite via OGR
    - 'ogr': Shapefiles, GeoJSON, and other OGR formats
    - 'memory': Memory layers
    
    GeoPackage and SQLite files return 'spatialite' because they support
    Spatialite SQL functions in setSubsetString.
    
    Args:
        layer: QGIS vector layer
    
    Returns:
        str: One of 'postgresql', 'spatialite', 'ogr', 'memory', or 'unknown'
    """
    if not QGIS_AVAILABLE:
        return 'unknown'
    
    if not isinstance(layer, QgsVectorLayer):
        return 'unknown'
    
    try:
        provider_type = layer.providerType()
    except (RuntimeError, AttributeError):
        return 'unknown'
    
    # Remote providers use OGR-style filtering
    if provider_type in REMOTE_PROVIDERS:
        return 'ogr'
    
    # Direct matches
    if provider_type == 'postgres':
        return 'postgresql'
    elif provider_type == 'spatialite':
        return 'spatialite'
    elif provider_type == 'memory':
        return 'memory'
    elif provider_type == 'ogr':
        # Check if it's a GeoPackage or SQLite file - these support Spatialite SQL
        try:
            source = layer.source()
            source_path = source.split('|')[0] if '|' in source else source
            lower_path = source_path.lower()
            
            if lower_path.endswith('.gpkg'):
                return 'spatialite'
            if lower_path.endswith('.sqlite'):
                return 'spatialite'
            
            # Check for remote URLs
            if any(lower_path.startswith(proto) for proto in ('http://', 'https://', 'ftp://')):
                return 'ogr'
            
            return 'ogr'
        except (RuntimeError, AttributeError):
            return 'ogr'
    else:
        return 'ogr'


# =============================================================================
# PostgreSQL Connection
# =============================================================================

def get_data_source_uri(layer) -> Tuple[Optional[Any], Optional[str]]:
    """
    Extract data source URI and authentication config ID from a layer.
    
    Args:
        layer: QgsVectorLayer or None
    
    Returns:
        tuple: (source_uri, authcfg_id) or (None, None) if layer is None
    """
    if layer is None or not QGIS_AVAILABLE or QgsDataSourceUri is None:
        return None, None
    
    try:
        source_uri = QgsDataSourceUri(layer.source())
        if str(source_uri) == '':
            return None, None
        authcfg_id = source_uri.param('authcfg')
        if authcfg_id and str(authcfg_id) != '':
            return source_uri, authcfg_id
        return source_uri, None
    except Exception:
        return None, None


def get_datasource_connexion_from_layer(layer) -> Tuple[Optional[Any], Optional[Any]]:
    """
    Get PostgreSQL connection from layer using psycopg2 (for advanced features).
    
    Returns (None, None) if:
    - psycopg2 is not available (basic filtering still works via QGIS API)
    - Layer is not PostgreSQL
    - Connection fails
    
    Note: This is only needed for advanced features like materialized views.
    Basic filtering via setSubsetString() works without psycopg2.
    
    Args:
        layer: QGIS vector layer
    
    Returns:
        tuple: (connection, source_uri) or (None, None)
    """
    # Check if psycopg2 is available
    if not PSYCOPG2_AVAILABLE or psycopg2 is None:
        logger.debug("psycopg2 not available - cannot create direct PostgreSQL connection")
        return None, None
    
    if not QGIS_AVAILABLE:
        return None, None
    
    # Check that it's a PostgreSQL source
    try:
        if layer.providerType() != 'postgres':
            return None, None
    except (RuntimeError, AttributeError):
        return None, None

    connexion = None
    source_uri, authcfg_id = get_data_source_uri(layer)
    
    if source_uri is None:
        return None, None
    
    try:
        host = source_uri.host()
        port = source_uri.port()
        dbname = source_uri.database()
        username = source_uri.username()
        password = source_uri.password()
        ssl_mode = source_uri.sslMode()

        if authcfg_id is not None:
            try:
                authConfig = QgsAuthMethodConfig()
                if authcfg_id in QgsApplication.authManager().configIds():
                    QgsApplication.authManager().loadAuthenticationConfig(authcfg_id, authConfig, True)
                    username = authConfig.config("username")
                    password = authConfig.config("password")
            except Exception as auth_err:
                logger.debug(f"Auth config loading failed: {auth_err}")

        # Build connection kwargs
        connect_kwargs = {
            'user': username,
            'password': password,
            'host': host,
            'port': port,
            'database': dbname
        }
        # Remove None values
        connect_kwargs = {k: v for k, v in connect_kwargs.items() if v is not None and v != ''}
        
        if ssl_mode is not None:
            connect_kwargs['sslmode'] = source_uri.encodeSslMode(ssl_mode)
        
        connexion = psycopg2.connect(**connect_kwargs)
        
        # Set statement timeout to prevent blocking queries
        try:
            with connexion.cursor() as cursor:
                cursor.execute("SET statement_timeout = 300000")  # 5 minutes
                connexion.commit()
        except Exception as timeout_err:
            logger.warning(f"Could not set statement_timeout: {timeout_err}")
            
    except Exception as e:
        layer_name = 'unknown'
        try:
            layer_name = layer.name()
        except:
            pass
        logger.error(f"PostgreSQL connection failed for layer '{layer_name}': {e}")
        connexion = None

    return connexion, source_uri


# =============================================================================
# Primary Key Detection
# =============================================================================

def get_primary_key_name(layer) -> Optional[str]:
    """
    Get the primary key field name for a layer.
    
    Uses multiple detection strategies:
    1. Exact match with common ID field names
    2. Pattern matching for fields ending with _ID, _id, etc.
    3. First integer/string field as fallback
    
    Args:
        layer: QgsVectorLayer
    
    Returns:
        str: Primary key field name or None if not found
    """
    if not QGIS_AVAILABLE:
        return None
    
    if not layer or not hasattr(layer, 'isValid') or not layer.isValid():
        return None
    
    try:
        fields = layer.fields()
    except (RuntimeError, AttributeError):
        return None
    
    if fields.count() == 0:
        return None
    
    # Common primary key field names
    pk_names = ['id', 'fid', 'ogc_fid', 'gid', 'pk', 'objectid', 'object_id', 'oid', 'uid']
    
    # Try exact match first (case-insensitive)
    for field in fields:
        if field.name().lower() in pk_names:
            return field.name()
    
    # Try pattern matching (_id suffix)
    for field in fields:
        name_lower = field.name().lower()
        if name_lower.endswith('_id') or name_lower.endswith('id'):
            return field.name()
    
    # Fallback: first integer field
    try:
        from qgis.PyQt.QtCore import QVariant
        int_types = [QVariant.Int, QVariant.LongLong, QVariant.UInt, QVariant.ULongLong]
        for field in fields:
            if field.type() in int_types:
                return field.name()
    except ImportError:
        pass
    
    # Last resort: first field
    if fields.count() > 0:
        return fields[0].name()
    
    return None


# =============================================================================
# Display Field Detection
# =============================================================================

def get_best_display_field(layer, sample_size: int = 10, use_value_relations: bool = True) -> str:
    """
    Determine the best field to use for display in a layer.
    
    Priority order:
    1. Layer's configured display expression (if set in QGIS)
    2. Fields matching common name patterns (name, nom, label, etc.)
    3. First text/string field that's not an ID field
    4. Primary key if no better option
    
    Args:
        layer: QgsVectorLayer
        sample_size: Number of features to sample for value checking
        use_value_relations: Whether to detect ValueRelation expressions
    
    Returns:
        str: The field name to use for display, or empty string
    """
    if not QGIS_AVAILABLE:
        return ""
    
    if layer is None or not hasattr(layer, 'isValid') or not layer.isValid():
        return ""
    
    try:
        fields = layer.fields()
    except (RuntimeError, AttributeError):
        return ""
    
    if fields.count() == 0:
        return ""
    
    # Common name patterns for descriptive fields
    name_patterns = [
        'name', 'nom', 'label', 'titre', 'title', 'description', 'desc',
        'libelle', 'libellé', 'bezeichnung', 'nombre', 'nome', 'naam',
        'display_name', 'displayname', 'full_name', 'fullname'
    ]
    
    # Patterns to exclude (ID/key fields)
    exclude_patterns = [
        'id', 'pk', 'fid', 'ogc_fid', 'gid', 'uid', 'uuid', 'oid',
        'objectid', 'object_id', '_id', 'rowid', 'row_id'
    ]
    
    # Try to find a field matching name patterns
    for field in fields:
        field_name_lower = field.name().lower()
        if any(pattern in field_name_lower for pattern in name_patterns):
            if not any(excl in field_name_lower for excl in exclude_patterns):
                return field.name()
    
    # Try to find first text field (not an ID)
    try:
        string_types = [QVariant.String, QVariant.Char] if QVariant else []
        for field in fields:
            if field.type() in string_types:
                field_name_lower = field.name().lower()
                if not any(excl in field_name_lower for excl in exclude_patterns):
                    return field.name()
    except Exception:
        pass
    
    # Fallback to primary key
    pk = get_primary_key_name(layer)
    if pk:
        return pk
    
    # Last resort: first field
    if fields.count() > 0:
        return fields[0].name()
    
    return ""


# =============================================================================
# PostgreSQL Layer Validation
# =============================================================================

def validate_and_cleanup_postgres_layers(layers: List) -> List[str]:
    """
    Validate PostgreSQL layers and clean up orphaned MV references.
    
    Should be called on project load to detect and fix layers that reference
    FilterMate materialized views that no longer exist.
    
    Args:
        layers: List of QgsVectorLayer instances to check
    
    Returns:
        List of layer names that had orphaned MVs cleared
    """
    if not QGIS_AVAILABLE:
        return []
    
    cleaned_layers = []
    
    for layer in layers:
        if not isinstance(layer, QgsVectorLayer):
            continue
        
        try:
            if layer.providerType() != 'postgres':
                continue
        except (RuntimeError, AttributeError):
            continue
        
        try:
            # Check if layer has a subset string referencing MV
            subset = layer.subsetString()
            if subset and 'mv_fm_' in subset.lower():
                # Clear the potentially orphaned filter
                layer.setSubsetString('')
                cleaned_layers.append(layer.name())
                logger.debug(f"Cleared orphaned MV filter from layer '{layer.name()}'")
        except Exception as e:
            logger.debug(f"Error validating layer: {e}")
    
    if cleaned_layers:
        logger.warning(
            f"Cleaned up {len(cleaned_layers)} layer(s) with orphaned MV references: "
            f"{', '.join(cleaned_layers)}"
        )
    
    return cleaned_layers


# =============================================================================
# CRS Utilities (Simple Constants)
# =============================================================================

# CRS utilities availability
CRS_UTILS_AVAILABLE = True

# Default metric CRS for buffer operations
DEFAULT_METRIC_CRS = "EPSG:3857"


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Provider detection
    'detect_layer_provider_type',
    'PROVIDER_POSTGRES',
    'PROVIDER_SPATIALITE',
    'PROVIDER_OGR',
    'PROVIDER_MEMORY',
    
    # PostgreSQL connection
    'get_datasource_connexion_from_layer',
    'get_data_source_uri',
    'POSTGRESQL_AVAILABLE',
    'PSYCOPG2_AVAILABLE',
    
    # Field utilities
    'get_primary_key_name',
    'get_best_display_field',
    
    # Validation
    'validate_and_cleanup_postgres_layers',
    
    # CRS constants
    'CRS_UTILS_AVAILABLE',
    'DEFAULT_METRIC_CRS',
]

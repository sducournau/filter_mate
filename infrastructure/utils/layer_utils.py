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
    from ...adapters.backends.postgresql_availability import (
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
        except (RuntimeError, AttributeError):
            pass  # Layer may have been deleted
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

def _field_has_values(layer, field_name: str, sample_size: int = 5) -> bool:
    """
    Check if a field has at least one non-null, non-empty value.

    FIX 2026-01-18: Added to prevent selecting fields with no values as default display field.
    This fixes the issue where the multiple selection picker shows an empty list because
    the default field has no values in the database.

    Args:
        layer: QgsVectorLayer to check
        field_name: Name of the field to check
        sample_size: Maximum number of features to sample (for performance)

    Returns:
        bool: True if field has at least one non-null value, False otherwise
    """
    if not QGIS_AVAILABLE:
        return True  # Assume has values if we can't check

    try:
        from qgis.core import QgsFeatureRequest

        # Create a request to fetch only the specified field (performance optimization)
        request = QgsFeatureRequest()
        request.setFlags(QgsFeatureRequest.NoGeometry)
        request.setSubsetOfAttributes([field_name], layer.fields())
        request.setLimit(sample_size)

        for feature in layer.getFeatures(request):
            try:
                value = feature[field_name]
                # Check if value is not NULL and not empty string
                if value is not None and value != '' and str(value).strip() != '':
                    return True
            except (KeyError, IndexError):
                continue

        return False
    except Exception as e:
        logger.debug(f"_field_has_values check failed for {field_name}: {e}")
        return True  # Assume has values on error to avoid breaking existing behavior


def get_best_display_field(layer, sample_size: int = 10, use_value_relations: bool = True) -> str:
    """
    Determine the best field or expression to use for display in a layer.

    Priority order:
    1. Layer's configured display expression (if set in QGIS)
    2. ValueRelation fields using represent_value() for human-readable display
    3. Fields matching common name patterns (name, nom, label, etc.) WITH VALUES
    4. First text/string field that's not an ID field AND HAS VALUES
    5. Primary key if no better option (always has values)
    6. First field with values

    FIX 2026-01-18: Now validates that candidate fields have non-null values
    before returning them. This prevents the multiple selection picker from
    showing an empty list when the default field has no values.

    Args:
        layer: QgsVectorLayer
        sample_size: Number of features to sample for value checking
        use_value_relations: Whether to detect and use ValueRelation expressions

    Returns:
        str: The field name or expression to use for display, or empty string
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

    # Priority 1: Check if layer has a configured display expression
    layer_display_expr = get_layer_display_expression(layer)
    if layer_display_expr:
        logger.debug(f"Using layer display expression for {layer.name()}: {layer_display_expr}")
        return layer_display_expr

    # Priority 2: Check for ValueRelation fields that could provide better display
    first_vr_expression = None
    if use_value_relations:
        vr_fields = get_fields_with_value_relations(layer)
        if vr_fields:
            # Common name patterns for descriptive fields in ValueRelations
            name_patterns_vr = ['name', 'nom', 'label', 'titre', 'title', 'description',
                                'libelle', 'libellé', 'display', 'text']

            # Prefer ValueRelation fields with common name patterns in their value_field
            for field_name, vr_info in vr_fields:
                value_field = vr_info.get('value_field', '').lower()
                if any(pattern in value_field for pattern in name_patterns_vr):
                    expr = get_field_display_expression(layer, field_name)
                    if expr:
                        logger.debug(f"Using ValueRelation display for {layer.name()}: {expr}")
                        return expr

            # Store first VR expression for later fallback
            if vr_fields:
                first_vr_field = vr_fields[0][0]
                first_vr_expression = get_field_display_expression(layer, first_vr_field)

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

    # Priority 3: Try to find a field matching name patterns WITH VALUES
    for field in fields:
        field_name_lower = field.name().lower()
        if any(pattern in field_name_lower for pattern in name_patterns):
            if not any(excl in field_name_lower for excl in exclude_patterns):
                # FIX 2026-01-18: Check if field has values before returning
                if _field_has_values(layer, field.name(), sample_size):
                    return field.name()
                else:
                    logger.debug(f"Skipping field '{field.name()}' - no values found")

    # Priority 4: Try to find first text field (not an ID) WITH VALUES
    try:
        string_types = [QVariant.String, QVariant.Char] if QVariant else []
        for field in fields:
            if field.type() in string_types:
                field_name_lower = field.name().lower()
                if not any(excl in field_name_lower for excl in exclude_patterns):
                    # FIX 2026-01-18: Check if field has values before returning
                    if _field_has_values(layer, field.name(), sample_size):
                        return field.name()
                    else:
                        logger.debug(f"Skipping text field '{field.name()}' - no values found")
    except Exception:
        pass

    # If no text field but we have a ValueRelation expression, use it
    if first_vr_expression:
        logger.debug(f"Using fallback ValueRelation for {layer.name()}: {first_vr_expression}")
        return first_vr_expression

    # Priority 5: Fallback to primary key (always has values by definition)
    pk = get_primary_key_name(layer)
    if pk:
        logger.debug(f"Using primary key '{pk}' as fallback for {layer.name()}")
        return pk

    # Priority 6: Last resort - find first field WITH VALUES
    for field in fields:
        if _field_has_values(layer, field.name(), sample_size):
            logger.debug(f"Using first field with values '{field.name()}' for {layer.name()}")
            return field.name()

    # Absolute fallback: first field (even if empty - better than nothing)
    if fields.count() > 0:
        logger.warning(f"No field with values found for {layer.name()}, using first field '{fields[0].name()}'")
        return fields[0].name()

    return ""


# =============================================================================
# PostgreSQL Layer Validation (uses MV utilities below)
# =============================================================================

# Note: validate_and_cleanup_postgres_layers is defined after MV utilities
# to use clear_orphaned_mv_subset function


# =============================================================================
# CRS Utilities (Simple Constants)
# =============================================================================

# Default metric CRS for buffer operations
DEFAULT_METRIC_CRS = "EPSG:3857"


# =============================================================================
# ValueRelation Utilities (EPIC-1 Migration from modules/appUtils.py)
# =============================================================================

def is_value_relation_layer_available(layer_id: str, layer_name: str = None) -> bool:
    """
    Check if a ValueRelation referenced layer is available in the project.

    This provides a fallback mechanism when layers with ValueRelation widgets
    reference other layers that are not loaded in the current project.

    Args:
        layer_id: The ID of the referenced layer
        layer_name: The name of the referenced layer (fallback lookup)

    Returns:
        bool: True if the referenced layer exists and is valid, False otherwise
    """
    if not QGIS_AVAILABLE:
        return False

    if not layer_id and not layer_name:
        return False

    try:
        from qgis.core import QgsProject
        project = QgsProject.instance()

        # Try to find by ID first (most reliable)
        if layer_id:
            ref_layer = project.mapLayer(layer_id)
            if ref_layer and ref_layer.isValid():
                return True

        # Fallback: try to find by name
        if layer_name:
            layers_by_name = project.mapLayersByName(layer_name)
            for layer in layers_by_name:
                if layer and layer.isValid():
                    return True
    except Exception:
        pass

    return False


def get_value_relation_info(layer, field_name: str, check_layer_availability: bool = False) -> Optional[dict]:
    """
    Extract ValueRelation configuration from a field's editor widget setup.

    ValueRelation is a QGIS widget type that displays values from a related layer.
    This function extracts the configuration to determine:
    - The referenced layer
    - The key field (stored value)
    - The value field (displayed value)
    - Any filter expression

    Args:
        layer: The layer containing the field
        field_name: The name of the field to check
        check_layer_availability: If True, returns None if the referenced
            layer is not available in the project.

    Returns:
        dict or None: Dictionary with keys:
            - 'layer_id': ID of the referenced layer
            - 'layer_name': Name of the referenced layer
            - 'key_field': Field name used as key (stored value)
            - 'value_field': Field name used for display
            - 'filter_expression': Optional filter expression
            - 'allow_null': Whether null values are allowed
            - 'order_by_value': Whether to order by display value
            - 'layer_available': Boolean indicating if referenced layer exists
        Returns None if field is not a ValueRelation or config is invalid
    """
    if not QGIS_AVAILABLE:
        return None

    if layer is None or not hasattr(layer, 'isValid') or not layer.isValid():
        return None

    try:
        field_idx = layer.fields().indexOf(field_name)
        if field_idx < 0:
            return None

        widget_setup = layer.editorWidgetSetup(field_idx)

        # Check if it's a ValueRelation widget
        if widget_setup.type() != 'ValueRelation':
            return None

        config = widget_setup.config()
        if not config:
            return None

        # Extract ValueRelation configuration
        layer_id = config.get('Layer', config.get('LayerId', ''))
        layer_name = config.get('LayerName', '')

        result = {
            'layer_id': layer_id,
            'layer_name': layer_name,
            'key_field': config.get('Key', ''),
            'value_field': config.get('Value', ''),
            'filter_expression': config.get('FilterExpression', ''),
            'allow_null': config.get('AllowNull', False),
            'order_by_value': config.get('OrderByValue', False),
            'layer_available': is_value_relation_layer_available(layer_id, layer_name)
        }

        # Validate required fields
        if not result['key_field'] or not result['value_field']:
            logger.debug(f"ValueRelation config incomplete for {field_name}: {config}")
            return None

        # If checking availability and layer is missing, return None to trigger fallback
        if check_layer_availability and not result['layer_available']:
            logger.debug(
                f"ValueRelation for '{field_name}' references missing layer "
                f"'{layer_name}' (id={layer_id[:8] if layer_id else 'N/A'}...). "
                "Fallback to raw field value."
            )
            return None

        return result

    except Exception as e:
        logger.debug(f"Error extracting ValueRelation info for {field_name}: {e}")
        return None


def get_field_display_expression(layer, field_name: str, check_layer_availability: bool = True) -> Optional[str]:
    """
    Get the display expression for a field based on its widget configuration.

    For ValueRelation fields, this returns an expression that displays the
    human-readable value from the referenced layer instead of the key.

    Args:
        layer: The layer containing the field
        field_name: The name of the field
        check_layer_availability: If True, returns None for ValueRelation
            fields where the referenced layer is not available.

    Returns:
        str or None: A QGIS expression string for display, or None if no special
                     display is configured
    """
    if not QGIS_AVAILABLE:
        return None

    if layer is None or not hasattr(layer, 'isValid') or not layer.isValid():
        return None

    try:
        field_idx = layer.fields().indexOf(field_name)
        if field_idx < 0:
            return None

        widget_setup = layer.editorWidgetSetup(field_idx)
        widget_type = widget_setup.type()

        # For ValueRelation, check if referenced layer is available
        if widget_type == 'ValueRelation':
            if check_layer_availability:
                vr_info = get_value_relation_info(layer, field_name, check_layer_availability=True)
                if vr_info is None:
                    logger.debug(f"Skipping represent_value() for '{field_name}' - referenced layer not available")
                    return None
            return f'represent_value("{field_name}")'

        # For ValueMap widgets (dropdown with predefined values)
        elif widget_type == 'ValueMap':
            return f'represent_value("{field_name}")'

        # For RelationReference widgets
        elif widget_type == 'RelationReference':
            if check_layer_availability:
                config = widget_setup.config()
                relation_id = config.get('Relation', '') if config else ''
                if relation_id:
                    try:
                        from qgis.core import QgsProject
                        relation = QgsProject.instance().relationManager().relation(relation_id)
                        if not relation.isValid():
                            logger.debug(f"Skipping represent_value() for '{field_name}' - relation not valid")
                            return None
                    except Exception:
                        return None
            return f'represent_value("{field_name}")'

        return None

    except Exception as e:
        logger.debug(f"Error getting display expression for {field_name}: {e}")
        return None


def get_layer_display_expression(layer) -> Optional[str]:
    """
    Get the layer's configured display expression if it has one.

    Layers can have a display expression set in Layer Properties > Display
    which is used for feature identification, map tips, etc.

    Args:
        layer: The layer to check

    Returns:
        str or None: The display expression, or None if not set
    """
    if not QGIS_AVAILABLE:
        return None

    if layer is None or not hasattr(layer, 'isValid') or not layer.isValid():
        return None

    try:
        display_expr = layer.displayExpression()
        if display_expr and display_expr.strip():
            return display_expr.strip()
        return None
    except Exception as e:
        logger.debug(f"Error getting layer display expression: {e}")
        return None


def get_fields_with_value_relations(layer, only_available: bool = True) -> List[Tuple[str, dict]]:
    """
    Get all fields in a layer that have ValueRelation widget configuration.

    Args:
        layer: The layer to analyze
        only_available: If True (default), only returns ValueRelation
            fields where the referenced layer is available in the project.

    Returns:
        list: List of tuples (field_name, value_relation_info) for each
              ValueRelation field.
    """
    if not QGIS_AVAILABLE:
        return []

    if layer is None or not hasattr(layer, 'isValid') or not layer.isValid():
        return []

    result = []

    try:
        for field in layer.fields():
            field_name = field.name()
            vr_info = get_value_relation_info(layer, field_name, check_layer_availability=False)
            if vr_info:
                # Filter out unavailable layers if requested
                if only_available and not vr_info.get('layer_available', False):
                    logger.debug(
                        f"Skipping ValueRelation field '{field_name}' - "
                        f"referenced layer '{vr_info.get('layer_name', 'unknown')}' not available"
                    )
                    continue
                result.append((field_name, vr_info))
    except Exception as e:
        logger.debug(f"Error getting fields with value relations: {e}")

    return result


# =============================================================================
# GeoPackage Utilities
# =============================================================================

def is_valid_geopackage(file_path: str) -> bool:
    """
    Check if a file is a valid GeoPackage database.

    Args:
        file_path: Path to the file to check

    Returns:
        bool: True if the file is a valid GeoPackage
    """
    if not file_path:
        return False

    import os
    if not os.path.exists(file_path):
        return False

    try:
        import sqlite3
        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()
        # Check for gpkg_contents table (required by GeoPackage spec)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gpkg_contents'")
        result = cursor.fetchone() is not None
        conn.close()
        return result
    except Exception:
        return False


def get_geopackage_path(layer) -> Optional[str]:
    """
    Extract the GeoPackage file path from a layer's source.

    Args:
        layer: QGIS vector layer

    Returns:
        str or None: Path to the GeoPackage file, or None
    """
    if not QGIS_AVAILABLE:
        return None

    if layer is None or not hasattr(layer, 'source'):
        return None

    try:
        source = layer.source()
        # GeoPackage sources can be like: "/path/to/file.gpkg|layername=tablename"
        source_path = source.split('|')[0] if '|' in source else source

        if source_path.lower().endswith('.gpkg'):
            return source_path
        return None
    except Exception:
        return None


def get_geopackage_related_layers(source_layer, project_layers_dict: dict) -> List:
    """
    Get all layers in the project that share the same GeoPackage database.

    Args:
        source_layer: The source layer to find related layers for
        project_layers_dict: Dictionary of project layers {layer_id: layer}

    Returns:
        list: List of related QgsVectorLayer instances
    """
    if not QGIS_AVAILABLE:
        return []

    gpkg_path = get_geopackage_path(source_layer)
    if not gpkg_path:
        return []

    related = []
    for layer_id, layer in project_layers_dict.items():
        if layer == source_layer:
            continue
        layer_gpkg = get_geopackage_path(layer)
        if layer_gpkg and layer_gpkg.lower() == gpkg_path.lower():
            related.append(layer)

    return related


# =============================================================================
# Materialized View Utilities
# =============================================================================

def detect_filtermate_mv_reference(subset_string: str) -> str:
    """
    Detect if a subset string references a FilterMate materialized view.

    Args:
        subset_string: The layer's current subset string

    Returns:
        str: The MV name if found, empty string otherwise
    """
    import re

    if not subset_string:
        return ""

    # Unified fm_temp_* prefix patterns (v4.4.3+)
    patterns = [
        r'FROM\s+["\']?(\w+)["\']?\s*\.\s*["\']?(fm_temp_\w+)["\']?',
        r'FROM\s+["\']?(fm_temp_\w+)["\']?',
        # Legacy patterns for backward compatibility
        r'FROM\s+["\']?(\w+)["\']?\s*\.\s*["\']?(filtermate_mv_[a-f0-9]+)["\']?',
        r'FROM\s+["\']?(filtermate_mv_[a-f0-9]+)["\']?',
        r'FROM\s+["\']?(\w+)["\']?\s*\.\s*["\']?(mv_fm_[a-f0-9]+)["\']?',
        r'FROM\s+["\']?(mv_fm_[a-f0-9]+)["\']?',
        r'FROM\s+["\']?(\w+)["\']?\s*\.\s*["\']?(fm_mv_[a-f0-9_]+)["\']?',
        r'FROM\s+["\']?(fm_mv_[a-f0-9_]+)["\']?',
    ]

    for pattern in patterns:
        match = re.search(pattern, subset_string, re.IGNORECASE)
        if match:
            return match.group(match.lastindex)

    return ""


def validate_mv_exists(layer, mv_name: str, schema: str = None) -> bool:
    """
    Validate if a FilterMate materialized view exists in the database.

    Args:
        layer: PostgreSQL QgsVectorLayer to get connection from
        mv_name: Name of the materialized view to check
        schema: Schema name (defaults to layer's schema or 'public')

    Returns:
        bool: True if the MV exists, False otherwise
    """
    if not PSYCOPG2_AVAILABLE or psycopg2 is None:
        logger.debug(f"Cannot verify MV '{mv_name}' - psycopg2 not available")
        return False

    if not QGIS_AVAILABLE:
        return False

    try:
        if not layer or layer.providerType() != 'postgres':
            return False
    except (RuntimeError, AttributeError):
        return False

    try:
        conn, source_uri = get_datasource_connexion_from_layer(layer)
        if not conn:
            return False

        if schema is None:
            schema = source_uri.schema() if source_uri else "public"
            if not schema:
                schema = "public"

        cursor = conn.cursor()
        cursor.execute("""
            SELECT 1 FROM pg_matviews
            WHERE schemaname = %s AND matviewname = %s
            LIMIT 1
        """, (schema, mv_name))

        exists = cursor.fetchone() is not None
        cursor.close()
        conn.close()

        return exists

    except Exception as e:
        logger.debug(f"Error checking MV existence for '{mv_name}': {e}")
        return False


def clear_orphaned_mv_subset(layer) -> bool:
    """
    Clear a layer's subset string if it references a missing FilterMate MV.

    Args:
        layer: PostgreSQL QgsVectorLayer to check and fix

    Returns:
        bool: True if the subset was cleared, False otherwise
    """
    if not QGIS_AVAILABLE:
        return False

    if not layer or not isinstance(layer, QgsVectorLayer):
        return False

    try:
        if layer.providerType() != 'postgres':
            return False
    except (RuntimeError, AttributeError):
        return False

    try:
        subset_string = layer.subsetString()
        if not subset_string:
            return False

        mv_name = detect_filtermate_mv_reference(subset_string)
        if not mv_name:
            return False

        source_uri, _ = get_data_source_uri(layer)
        schema = source_uri.schema() if source_uri else "public"
        if not schema:
            schema = "public"

        if validate_mv_exists(layer, mv_name, schema):
            return False

        logger.warning(
            f"Layer '{layer.name()}' references missing MV '{schema}.{mv_name}'. "
            "Clearing orphaned filter."
        )

        layer.setSubsetString("")
        logger.info(f"Cleared orphaned MV reference from layer '{layer.name()}'")
        return True

    except Exception as e:
        logger.debug(f"Error clearing orphaned MV: {e}")
        return False


# =============================================================================
# Filter Cleanup Utilities
# =============================================================================

def cleanup_corrupted_layer_filters(project) -> List[str]:
    """
    Scan all layers in a project and clear any corrupted filter expressions.

    Detects and clears filters with known corruption patterns:
    1. __source alias without EXISTS wrapper
    2. Unbalanced parentheses

    Args:
        project: QgsProject instance to scan

    Returns:
        list: List of layer names that had corrupted filters cleared
    """
    cleared_layers = []

    if project is None:
        logger.warning("cleanup_corrupted_layer_filters: project is None")
        return cleared_layers

    if not QGIS_AVAILABLE:
        return cleared_layers

    try:
        for layer_id, layer in project.mapLayers().items():
            if not isinstance(layer, QgsVectorLayer):
                continue

            if not layer.isValid():
                continue

            current_filter = layer.subsetString()
            if not current_filter:
                continue

            is_corrupted = False
            corruption_reason = ""

            # Check for __source without EXISTS
            if '__source' in current_filter.lower() and 'EXISTS' not in current_filter.upper():
                is_corrupted = True
                corruption_reason = "__source alias without EXISTS wrapper"

            # Check for unbalanced parentheses
            elif current_filter.count('(') != current_filter.count(')'):
                is_corrupted = True
                open_count = current_filter.count('(')
                close_count = current_filter.count(')')
                corruption_reason = f"unbalanced parentheses ({open_count} '(' vs {close_count} ')')"

            if is_corrupted:
                layer_name = layer.name()
                logger.warning(f"CORRUPTED FILTER CLEARED for layer '{layer_name}': {corruption_reason}")

                try:
                    layer.setSubsetString("")
                    cleared_layers.append(layer_name)
                except Exception as e:
                    logger.error(f"Failed to clear filter for '{layer_name}': {e}")

    except Exception as e:
        logger.error(f"cleanup_corrupted_layer_filters failed: {e}")

    return cleared_layers


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
            # Use the proper MV cleanup function
            if clear_orphaned_mv_subset(layer):
                cleaned_layers.append(layer.name())
        except Exception as e:
            logger.debug(f"Error validating layer '{layer.name()}': {e}")

    if cleaned_layers:
        logger.warning(
            f"Cleaned up {len(cleaned_layers)} layer(s) with orphaned MV references: "
            f"{', '.join(cleaned_layers)}"
        )

    return cleaned_layers


# =============================================================================
# Utility Functions
# =============================================================================

def truncate(number: float, digits: int) -> float:
    """
    Truncate a floating point number to a specified number of decimal places.

    Args:
        number: The number to truncate
        digits: Number of decimal places

    Returns:
        float: Truncated number
    """
    import math
    if digits < 0:
        return float(number)
    multiplier = 10 ** digits
    return math.trunc(number * multiplier) / multiplier


def escape_json_string(s: str) -> str:
    """
    Escape a string for safe inclusion in a JSON string value.

    Args:
        s: The string to escape

    Returns:
        str: A JSON-safe escaped string
    """
    if not s:
        return ""

    escaped = s.replace('\\', '\\\\')
    escaped = escaped.replace('"', '\\"')
    escaped = escaped.replace('\n', '\\n')
    escaped = escaped.replace('\r', '\\r')
    escaped = escaped.replace('\t', '\\t')

    return escaped


def get_spatialite_datasource_from_layer(layer) -> Tuple[Optional[str], Optional[str]]:
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
    'get_spatialite_datasource_from_layer',
    'POSTGRESQL_AVAILABLE',
    'PSYCOPG2_AVAILABLE',

    # Field utilities
    'get_primary_key_name',
    'get_best_display_field',

    # ValueRelation utilities (migrated from modules/appUtils.py)
    'is_value_relation_layer_available',
    'get_value_relation_info',
    'get_field_display_expression',
    'get_layer_display_expression',
    'get_fields_with_value_relations',

    # GeoPackage utilities
    'is_valid_geopackage',
    'get_geopackage_path',
    'get_geopackage_related_layers',

    # Materialized View utilities
    'detect_filtermate_mv_reference',
    'validate_mv_exists',
    'clear_orphaned_mv_subset',

    # Filter cleanup
    'cleanup_corrupted_layer_filters',

    # Validation
    'validate_and_cleanup_postgres_layers',

    # Utility functions
    'truncate',
    'escape_json_string',

    # CRS constants
    'DEFAULT_METRIC_CRS',
]

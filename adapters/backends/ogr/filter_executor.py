"""
OGR Filter Executor

EPIC-1 Phase E4: Backend-specific filter execution for OGR (Shapefile, GeoPackage, etc.).

This module contains OGR-specific methods extracted from filter_task.py:
- build_ogr_filter_from_selection() - Build filter from selection (57 lines)
- execute_ogr_spatial_selection() - Execute spatial selection (159 lines) - DEFERRED
- prepare_ogr_source_geom() - Prepare source geometry for OGR (382 lines) - DEFERRED

Note: execute_ogr_spatial_selection and prepare_ogr_source_geom are deferred because
they have heavy dependencies on self.* instance variables and QGIS processing context.
They need significant refactoring before extraction.

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase E4)
"""

import logging
import re

logger = logging.getLogger('FilterMate.Adapters.Backends.OGR.FilterExecutor')


def build_ogr_filter_from_selection(
    layer,
    layer_props: dict,
    selected_fids: list = None,
    distant_geom_expression: str = None
) -> tuple:
    """
    Build filter expression from selected features for OGR layers.
    
    EPIC-1 Phase E4-S4: Extracted from filter_task.py line 6949 (57 lines)
    
    Args:
        layer: Layer with selected features
        layer_props: Layer properties dict with keys:
            - primary_key_name: Primary key field name
            - primary_key_is_numeric: Whether PK is numeric
            - layer_schema: Schema name
            - layer_name: Table/layer name
            - layer_geometry_field: Geometry field name
        selected_fids: List of selected feature IDs (optional, reads from layer if None)
        distant_geom_expression: Geometry field expression
        
    Returns:
        tuple: (filter_expression, full_sql_expression) or (None, None) if no selection
    """
    param_distant_primary_key_name = layer_props["primary_key_name"]
    param_distant_primary_key_is_numeric = layer_props.get(
        "primary_key_is_numeric", True
    )
    param_distant_schema = layer_props.get("layer_schema", "")
    param_distant_table = layer_props["layer_name"]
    param_distant_geometry_field = layer_props.get(
        "layer_geometry_field", "geometry"
    )
    
    # Get selected feature IDs if not provided
    if selected_fids is None:
        try:
            from qgis.core import QgsFeatureRequest
            selected_fids = list(layer.selectedFeatureIds())
        except Exception:
            selected_fids = []
    
    if not selected_fids:
        return None, None
    
    # Extract feature IDs from selection
    # CRITICAL FIX: Handle ctid (PostgreSQL internal identifier)
    # ctid is not accessible via feature[field_name], use feature.id() instead
    features_ids = []
    try:
        from qgis.core import QgsFeatureRequest
        request = QgsFeatureRequest().setFilterFids(selected_fids)
        for feature in layer.getFeatures(request):
            if param_distant_primary_key_name == 'ctid':
                features_ids.append(str(feature.id()))
            else:
                pk_value = feature[param_distant_primary_key_name]
                features_ids.append(str(pk_value))
    except Exception as e:
        logger.warning(f"Error extracting feature IDs: {e}")
        # Fallback to fids directly
        features_ids = [str(fid) for fid in selected_fids]
    
    if len(features_ids) == 0:
        return None, None
    
    # Build IN clause based on key type
    if param_distant_primary_key_is_numeric:
        param_expression = '"{pk}" IN ({ids})'.format(
            pk=param_distant_primary_key_name,
            ids=", ".join(features_ids)
        )
    else:
        # Quote string values
        param_expression = '"{pk}" IN ({ids})'.format(
            pk=param_distant_primary_key_name,
            ids="'" + "', '".join(features_ids) + "'"
        )
    
    # Build full SELECT expression for manage_layer_subset_strings
    geom_expr = distant_geom_expression or f'"{param_distant_geometry_field}"'
    
    if param_distant_schema:
        full_expression = (
            f'SELECT "{param_distant_table}"."{param_distant_primary_key_name}", '
            f'{geom_expr} FROM "{param_distant_schema}"."{param_distant_table}" '
            f'WHERE {param_expression}'
        )
    else:
        # OGR doesn't use schemas
        full_expression = (
            f'SELECT "{param_distant_primary_key_name}", '
            f'{geom_expr} FROM "{param_distant_table}" '
            f'WHERE {param_expression}'
        )
    
    return param_expression, full_expression


def format_ogr_pk_values(
    values: list,
    is_numeric: bool = True
) -> str:
    """
    Format primary key values for OGR IN clause.
    
    EPIC-1 Phase E4-S4: OGR equivalent of PostgreSQL format_pk_values_for_sql
    
    Args:
        values: List of primary key values
        is_numeric: Whether PK is numeric
        
    Returns:
        str: Comma-separated values formatted for SQL IN clause
    """
    if not values:
        return ''
    
    if is_numeric:
        return ', '.join(str(v) for v in values)
    else:
        # Quote string values and escape internal quotes
        formatted = []
        for v in values:
            str_val = str(v).replace("'", "''")
            formatted.append(f"'{str_val}'")
        return ', '.join(formatted)


def normalize_column_names_for_ogr(
    expression: str,
    field_names: list
) -> str:
    """
    Normalize column names in expression for OGR layers.
    
    EPIC-1 Phase E4-S4: OGR equivalent of PostgreSQL function
    
    OGR/Shapefile field names are case-insensitive but often stored
    in uppercase. This ensures proper matching.
    
    Args:
        expression: SQL expression string
        field_names: List of actual field names from the layer
        
    Returns:
        str: Expression with corrected column names
    """
    if not expression or not field_names:
        return expression
    
    result_expression = expression
    
    # Build case-insensitive lookup map: uppercase → actual name
    field_lookup = {name.upper(): name for name in field_names}
    
    # Find all quoted column names in expression
    quoted_cols = re.findall(r'"([^"]+)"', result_expression)
    
    for col_name in quoted_cols:
        # Skip if column exists with exact case
        if col_name in field_names:
            continue
        
        # Check for case-insensitive match
        col_upper = col_name.upper()
        if col_upper in field_lookup:
            correct_name = field_lookup[col_upper]
            result_expression = result_expression.replace(
                f'"{col_name}"',
                f'"{correct_name}"'
            )
            logger.debug(f"OGR column case fix: \"{col_name}\" → \"{correct_name}\"")
    
    return result_expression


def build_ogr_simple_filter(
    primary_key_name: str,
    feature_ids: list,
    is_numeric: bool = True
) -> str:
    """
    Build simple OGR filter for primary key IN clause.
    
    EPIC-1 Phase E4-S4: Utility for OGR subset strings
    
    Args:
        primary_key_name: Primary key field name
        feature_ids: List of feature IDs to include
        is_numeric: Whether PK is numeric
        
    Returns:
        str: OGR filter expression
    """
    if not feature_ids:
        return ""
    
    formatted_ids = format_ogr_pk_values(feature_ids, is_numeric)
    return f'"{primary_key_name}" IN ({formatted_ids})'


def apply_ogr_subset(
    layer,
    subset_string: str,
    queue_subset_func=None
) -> bool:
    """
    Apply subset string to OGR layer with thread safety.
    
    EPIC-1 Phase E4-S4: Thread-safe OGR subset application
    
    Args:
        layer: QGIS vector layer
        subset_string: SQL subset string
        queue_subset_func: Function to queue subset for main thread
        
    Returns:
        bool: True if successful
    """
    if queue_subset_func:
        # Thread-safe: queue for main thread application
        queue_subset_func(layer, subset_string)
        return True
    else:
        # Direct application (only safe from main thread)
        try:
            return layer.setSubsetString(subset_string)
        except Exception as e:
            logger.error(f"Failed to apply OGR subset: {e}")
            return False


def combine_ogr_filters(
    existing_filter: str,
    new_filter: str,
    combine_operator: str = "AND"
) -> str:
    """
    Combine two OGR filters with a logical operator.
    
    EPIC-1 Phase E4-S4: Utility for combining OGR filters
    
    Args:
        existing_filter: Existing filter expression
        new_filter: New filter to combine
        combine_operator: "AND", "OR", or "NOT"
        
    Returns:
        str: Combined filter expression
    """
    if not existing_filter:
        return new_filter
    if not new_filter:
        return existing_filter
    
    if combine_operator.upper() == "NOT":
        return f"({existing_filter}) AND NOT ({new_filter})"
    else:
        return f"({existing_filter}) {combine_operator.upper()} ({new_filter})"

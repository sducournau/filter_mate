"""
PostgreSQL Filter Executor

EPIC-1 Phase E4: Backend-specific filter execution for PostgreSQL/PostGIS.

This module will contain PostgreSQL-specific methods extracted from filter_task.py:
- prepare_postgresql_source_geom() - Prepare source geometry with buffer/centroid
- qgis_expression_to_postgis() - Convert QGIS expression to PostGIS SQL
- _build_postgis_predicates() - Build spatial predicates
- _build_postgis_filter_expression() - Build complete filter expression
- _apply_postgresql_type_casting() - Apply type casting for PostgreSQL

TODO (EPIC-1 Phase E4): Extract methods from filter_task.py
This is a stub module for Phase E4 planning. Methods will be extracted
in a follow-up session due to complexity and dependencies.

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase E4 - stub)
"""

import logging

logger = logging.getLogger('FilterMate.Adapters.Backends.PostgreSQL.FilterExecutor')


def prepare_postgresql_source_geom(
    source_table: str,
    source_schema: str,
    source_geom: str,
    buffer_value: float = None,
    buffer_expression: str = None,
    use_centroids: bool = False,
    buffer_segments: int = 5,
    buffer_type: str = "Round",
    primary_key_name: str = None
) -> tuple:
    """
    Prepare PostgreSQL source geometry with buffer/centroid transformations.
    
    EPIC-1 Phase E4-S1: Extracted from filter_task.py line 3583 (122 lines)
    
    Handles:
    - Geometry buffer (static value or expression)
    - Centroid optimization (simplify complex polygons to points)
    - Materialized view creation (for buffer expressions)
    - Negative buffer handling (erosion with ST_MakeValid)
    
    Args:
        source_table: Table name
        source_schema: Schema name
        source_geom: Geometry column name
        buffer_expression: Dynamic buffer expression (creates materialized view)
        buffer_value: Static buffer value in meters
        buffer_segments: Number of segments for buffer (quad_segs)
        buffer_type: "Round", "Flat", or "Square"
        use_centroids: Apply ST_Centroid to source geometry
        primary_key_name: Primary key column (for materialized views)
        
    Returns:
        tuple: (postgresql_source_geom_expr, materialized_view_name or None)
    """
    import re
    from modules.appUtils import sanitize_sql_identifier
    
    logger = logging.getLogger('FilterMate.Adapters.Backends.PostgreSQL.FilterExecutor')
    
    # CRITICAL FIX: Include schema in geometry reference for PostgreSQL
    # Format: "schema"."table"."geom" to avoid "missing FROM-clause entry" errors
    base_geom = '"{source_schema}"."{source_table}"."{source_geom}"'.format(
        source_schema=source_schema,
        source_table=source_table,
        source_geom=source_geom
    )
    
    # Initialize return values
    postgresql_source_geom = base_geom
    materialized_view_name = None
    
    # CENTROID OPTIMIZATION: Wrap geometry in ST_Centroid if enabled for source layer
    # This significantly speeds up queries for complex polygons (e.g., buildings)
    # CENTROID + BUFFER OPTIMIZATION v2.5.13: Combine centroid and buffer when both are enabled
    # Order: ST_Buffer(ST_Centroid(geom)) - buffer is applied to the centroid point
    
    if buffer_expression is not None and buffer_expression != '':
        # Buffer expression mode (dynamic buffer from field/expression)
        
        # Adjust field references to include table name
        if buffer_expression.find('"') == 0 and buffer_expression.find(source_table) != 1:
            buffer_expression = '"{source_table}".'.format(source_table=source_table) + buffer_expression
        
        buffer_expression = re.sub(' "', ' "mv_{source_table}"."'.format(source_table=source_table), buffer_expression)
        
        buffer_expression = qgis_expression_to_postgis(buffer_expression)
        
        # NOTE: Materialized view creation is handled by the caller
        # This function only prepares the geometry expression
        
        # Use sanitize_sql_identifier to handle all special chars (em-dash, etc.)
        materialized_view_name = sanitize_sql_identifier(source_table + '_buffer_expr')
        
        postgresql_source_geom = '"mv_{materialized_view_name}_dump"."{source_geom}"'.format(
            source_geom=source_geom,
            materialized_view_name=materialized_view_name
        )
        
        # NOTE: Centroids are not supported with buffer expressions (materialized views)
        # because the view already contains buffered geometries
        if use_centroids:
            logger.warning("⚠️ PostgreSQL: Centroid option ignored when using buffer expression (materialized view)")
    
    elif buffer_value is not None and buffer_value != 0:
        # Static buffer value mode
        
        # CRITICAL FIX: For simple numeric buffer values, apply buffer directly in SQL
        # Don't create materialized views - just wrap geometry in ST_Buffer()
        
        # Build ST_Buffer style parameters (quad_segs for segments, endcap for buffer type)
        buffer_type_mapping = {"Round": "round", "Flat": "flat", "Square": "square"}
        endcap_style = buffer_type_mapping.get(buffer_type, "round")
        
        # Build style string for PostGIS ST_Buffer
        style_params = f"quad_segs={buffer_segments}"
        if endcap_style != 'round':
            style_params += f" endcap={endcap_style}"
        
        # CENTROID + BUFFER: Determine the geometry to buffer
        # If centroid is enabled, buffer the centroid point instead of the full geometry
        if use_centroids:
            geom_to_buffer = (
                f'ST_Centroid("{source_schema}"."{source_table}".'
                f'"{source_geom}")'
            )
            logger.info(
                "✓ PostgreSQL: Using ST_Centroid + ST_Buffer "
                "for source layer"
            )
        else:
            geom_to_buffer = '"{source_schema}"."{source_table}"."{source_geom}"'.format(
                source_schema=source_schema,
                source_table=source_table,
                source_geom=source_geom
            )
        
        # Build base ST_Buffer expression with style parameters
        base_buffer_expr = f"ST_Buffer({geom_to_buffer}, {buffer_value}, '{style_params}')"
        
        # CRITICAL FIX v2.5.6: Handle negative buffers (erosion) properly
        # Negative buffers can produce empty geometries which must be handled
        # with ST_MakeValid() and ST_IsEmpty() to prevent matching issues
        if buffer_value < 0:
            logger.info(f"📐 Applying NEGATIVE buffer (erosion): {buffer_value}m")
            logger.info(f"  🛡️ Wrapping in ST_MakeValid() + ST_IsEmpty check for empty geometry handling")
            validated_expr = f"ST_MakeValid({base_buffer_expr})"
            postgresql_source_geom = f"CASE WHEN ST_IsEmpty({validated_expr}) THEN NULL ELSE {validated_expr} END"
            logger.info(f"  📝 Generated expression: {postgresql_source_geom[:150]}...")
        else:
            postgresql_source_geom = base_buffer_expr
        
        buffer_type_desc = "expansion" if buffer_value > 0 else "erosion"
        centroid_desc = " (on centroids)" if use_centroids else ""
        logger.info(f"✓ PostgreSQL source geom prepared with {buffer_value}m buffer ({buffer_type_desc}, endcap={endcap_style}, segments={buffer_segments}){centroid_desc}")
        logger.debug(f"Using simple buffer: ST_Buffer with {buffer_value}m ({buffer_type_desc}){centroid_desc}")
    
    else:
        # No buffer - just apply centroid if enabled
        if use_centroids:
            postgresql_source_geom = f"ST_Centroid({base_geom})"
            logger.info(f"✓ PostgreSQL: Using ST_Centroid for source layer geometry simplification")
        else:
            postgresql_source_geom = base_geom
    
    logger.debug(f"prepare_postgresql_source_geom: {postgresql_source_geom}")
    
    return postgresql_source_geom, materialized_view_name


def qgis_expression_to_postgis(expression: str, geom_col: str = 'geometry') -> str:
    """
    Convert QGIS expression to PostGIS SQL.
    
    EPIC-1 Phase E4-S1: Extracted from filter_task.py line 3451 (68 lines)
    
    Converts QGIS expression syntax to PostgreSQL/PostGIS SQL:
    - Spatial functions ($area, $length, etc.) → ST_Area, ST_Length
    - IF statements → CASE WHEN
    - Type casting for numeric/text operations
    
    Args:
        expression: QGIS expression string
        geom_col: Geometry column name (default: 'geometry')
        
    Returns:
        str: PostGIS SQL expression
    """
    import re
    import logging
    
    logger = logging.getLogger('FilterMate.Adapters.Backends.PostgreSQL.FilterExecutor')
    
    if not expression:
        return expression
    
    # 1. Convert QGIS spatial functions to PostGIS
    spatial_conversions = {
        '$area': f'ST_Area("{geom_col}")',
        '$length': f'ST_Length("{geom_col}")',
        '$perimeter': f'ST_Perimeter("{geom_col}")',
        '$x': f'ST_X("{geom_col}")',
        '$y': f'ST_Y("{geom_col}")',
        '$geometry': f'"{geom_col}"',
        'buffer': 'ST_Buffer',
        'area': 'ST_Area',
        'length': 'ST_Length',
        'perimeter': 'ST_Perimeter',
    }
    
    for qgis_func, postgis_func in spatial_conversions.items():
        expression = expression.replace(qgis_func, postgis_func)
    
    # 2. Convert IF statements to CASE WHEN
    if expression.find('if') >= 0:
        expression = re.sub(
            r'if\s*\(\s*([^,]+),\s*([^,]+),\s*([^)]+)\)',
            r'CASE WHEN \1 THEN \2 ELSE \3 END',
            expression,
            flags=re.IGNORECASE
        )
        logger.debug(f"Expression after IF conversion: {expression}")

    # 3. Add type casting for numeric operations
    expression = expression.replace('" >', '"::numeric >').replace('">', '"::numeric >')
    expression = expression.replace('" <', '"::numeric <').replace('"<', '"::numeric <')
    expression = expression.replace('" +', '"::numeric +').replace('"+', '"::numeric +')
    expression = expression.replace('" -', '"::numeric -').replace('"-', '"::numeric -')

    # 4. Normalize SQL keywords (case-insensitive replacements)
    expression = re.sub(r'\bcase\b', ' CASE ', expression, flags=re.IGNORECASE)
    expression = re.sub(r'\bwhen\b', ' WHEN ', expression, flags=re.IGNORECASE)
    expression = re.sub(r'\bis\b', ' IS ', expression, flags=re.IGNORECASE)
    expression = re.sub(r'\bthen\b', ' THEN ', expression, flags=re.IGNORECASE)
    expression = re.sub(r'\belse\b', ' ELSE ', expression, flags=re.IGNORECASE)
    expression = re.sub(r'\bilike\b', ' ILIKE ', expression, flags=re.IGNORECASE)
    expression = re.sub(r'\blike\b', ' LIKE ', expression, flags=re.IGNORECASE)
    expression = re.sub(r'\bnot\b', ' NOT ', expression, flags=re.IGNORECASE)

    # 5. Add type casting for text operations
    expression = expression.replace('" NOT ILIKE', '"::text NOT ILIKE').replace('" ILIKE', '"::text ILIKE')
    expression = expression.replace('" NOT LIKE', '"::text NOT LIKE').replace('" LIKE', '"::text LIKE')

    return expression


def build_postgis_predicates(
    postgis_predicates: list,
    layer_props: dict,
    has_to_reproject: bool,
    source_layer_crs_authid: str,
    source_schema: str,
    source_table: str,
    source_geom: str
) -> tuple:
    """
    Build PostGIS spatial predicates array for geometric filtering.
    
    EPIC-1 Phase E4-S2: Extracted from filter_task.py line 6676 (59 lines)
    
    DEPRECATED: Not currently used. Expression building is now handled by
    postgresql_backend.build_expression() which properly wraps table references
    in EXISTS subqueries.
    
    Args:
        postgis_predicates: List of PostGIS predicate functions (ST_Intersects, etc.)
        layer_props: Layer properties dict with schema, table, geometry field
        has_to_reproject: Whether layer needs reprojection
        source_layer_crs_authid: Source layer CRS authority ID
        source_schema: Source schema name
        source_table: Source table name
        source_geom: Source geometry field name
        
    Returns:
        tuple: (postgis_sub_expression_array, param_distant_geom_expression)
    """
    import logging
    
    logger = logging.getLogger('FilterMate.Adapters.Backends.PostgreSQL.FilterExecutor')
    
    param_distant_table = layer_props["layer_name"]
    param_distant_geometry_field = layer_props["layer_geometry_field"]
    
    postgis_sub_expression_array = []
    param_distant_geom_expression = (
        '"{distant_table}"."{distant_geometry_field}"'.format(
            distant_table=param_distant_table,
            distant_geometry_field=param_distant_geometry_field
        )
    )
    
    # Use metric CRS from source layer for all calculations
    target_crs_srid = (
        source_layer_crs_authid.split(':')[1] 
        if source_layer_crs_authid else '3857'
    )
    
    for postgis_predicate in postgis_predicates:
        current_geom_expr = param_distant_geom_expression
        
        if has_to_reproject:
            # Reproject distant layer to same metric CRS as source
            current_geom_expr = (
                'ST_Transform({param_distant_geom_expression}, '
                '{target_crs_srid})'.format(
                    param_distant_geom_expression=param_distant_geom_expression,
                    target_crs_srid=target_crs_srid
                )
            )
            logger.debug(
                f"Layer will be reprojected to {source_layer_crs_authid} "
                "for comparison"
            )
        
        # CRITICAL FIX: Use subquery with EXISTS to avoid "missing FROM-clause"
        # setSubsetString cannot reference other tables directly, need subquery
        postgis_sub_expression_array.append(
            'EXISTS (SELECT 1 FROM "{source_schema}"."{source_table}" '
            'AS __source WHERE {predicate}({distant_geom},{source_geom}))'.format(
                source_schema=source_schema,
                source_table=source_table,
                predicate=postgis_predicate,
                distant_geom=current_geom_expr,
                source_geom='__source."{}"'.format(source_geom)
            )
        )
    
    return postgis_sub_expression_array, param_distant_geom_expression


# TODO: Extract from filter_task.py line 1812
def apply_postgresql_type_casting(expression: str, layer=None) -> str:
    """
    Apply PostgreSQL-specific type casting to expression.
    
    TODO: Extract implementation from filter_task.py (40 lines)
    
    Args:
        expression: SQL expression
        layer: Optional QGIS layer for context
        
    Returns:
        str: Expression with type casting applied
    """
    raise NotImplementedError("EPIC-1 Phase E4: To be extracted from filter_task.py")

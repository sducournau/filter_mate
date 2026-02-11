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


# Threshold for using inline buffer expression vs MV (in feature count)
# Below this threshold, buffer expression is used inline in SQL
# Above this threshold, a materialized view is created for better performance
BUFFER_EXPR_MV_THRESHOLD = 10000


def prepare_postgresql_source_geom(
    source_table: str,
    source_schema: str,
    source_geom: str,
    buffer_value: float = None,
    buffer_expression: str = None,
    use_centroids: bool = False,
    buffer_segments: int = 5,
    buffer_type: str = "Round",
    primary_key_name: str = None,
    session_id: str = None,
    mv_schema: str = "filter_mate_temp",
    source_feature_count: int = None
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
        session_id: Session identifier for MV name prefix (multi-client isolation)
        mv_schema: Schema for materialized views (default: filter_mate_temp)
        source_feature_count: Number of features in source layer (for MV threshold decision)

    Returns:
        tuple: (postgresql_source_geom_expr, materialized_view_name or None)

    Note:
        For buffer_expression with few features (< BUFFER_EXPR_MV_THRESHOLD), the buffer
        is applied inline in SQL without creating a materialized view. This is faster
        for small datasets and avoids the overhead of MV creation.
    """
    import re
    from ....infrastructure.database.sql_utils import sanitize_sql_identifier

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

        # Convert QGIS expression to PostGIS FIRST (before any modifications)
        buffer_expr_postgis = qgis_expression_to_postgis(buffer_expression)

        # FIX v4.2.7: Use inline buffer expression for small datasets (no MV)
        # This avoids the overhead of creating a materialized view for few features
        logger.info(f"[PostgreSQL] 🔍 THRESHOLD CHECK: source_feature_count={source_feature_count}, threshold={BUFFER_EXPR_MV_THRESHOLD}")
        use_inline_buffer = (
            source_feature_count is not None and
            source_feature_count <= BUFFER_EXPR_MV_THRESHOLD
        )
        logger.info(f"[PostgreSQL] 🔍 use_inline_buffer={use_inline_buffer}")

        if use_inline_buffer:
            # INLINE MODE: Apply buffer expression directly in SQL
            logger.info(f"[PostgreSQL] 📝 Using INLINE buffer expression ({source_feature_count} features <= {BUFFER_EXPR_MV_THRESHOLD} threshold)")

            # Adjust field references to include schema.table
            adjusted_buffer_expr = buffer_expr_postgis
            if adjusted_buffer_expr.find('"') == 0 and source_table not in adjusted_buffer_expr[:50]:
                adjusted_buffer_expr = f'"{source_table}".' + adjusted_buffer_expr

            # Build ST_Buffer style parameters
            buffer_type_mapping = {"Round": "round", "Flat": "flat", "Square": "square"}
            endcap_style = buffer_type_mapping.get(buffer_type, "round")
            style_params = f"quad_segs={buffer_segments}"
            if endcap_style != 'round':
                style_params += f" endcap={endcap_style}"

            # Build inline buffer expression
            postgresql_source_geom = f'ST_Buffer({base_geom}, {adjusted_buffer_expr}, \'{style_params}\')'

            # Centroids can be applied with inline buffer
            if use_centroids:
                # Apply centroid BEFORE buffer for efficiency
                postgresql_source_geom = f'ST_Buffer(ST_Centroid({base_geom}), {adjusted_buffer_expr}, \'{style_params}\')'
                logger.info("[PostgreSQL] ✓ Using ST_Centroid + inline ST_Buffer")

            logger.info(f"[PostgreSQL] ✓ Inline buffer expression: {postgresql_source_geom[:100]}...")
            # No MV created in inline mode
            materialized_view_name = None

        else:
            # MV MODE: Create materialized view for large datasets
            logger.info(f"[PostgreSQL] 📦 Using MV for buffer expression ({source_feature_count or 'unknown'} features > {BUFFER_EXPR_MV_THRESHOLD} threshold)")

            # Adjust field references to include table name for MV
            if buffer_expression.find('"') == 0 and buffer_expression.find(source_table) != 1:
                buffer_expression = '"{source_table}".'.format(source_table=source_table) + buffer_expression

            buffer_expression = re.sub(' "', ' "mv_{source_table}"."'.format(source_table=source_table), buffer_expression)

            buffer_expression = qgis_expression_to_postgis(buffer_expression)

            # NOTE: Materialized view creation is handled by the caller
            # This function only prepares the geometry expression

            # Use sanitize_sql_identifier to handle all special chars (em-dash, etc.)
            # FIX v4.2.0: Apply session_id prefix to MV name for multi-client isolation
            # The MV is created with session prefix in filter_actions.py, so we must use the same name here
            base_mv_name = sanitize_sql_identifier(source_table + '_buffer_expr')
            if session_id:
                materialized_view_name = f"{session_id}_{base_mv_name}"
                logger.debug(f"[PostgreSQL] Using session-prefixed MV name: {materialized_view_name}")
            else:
                materialized_view_name = base_mv_name
                logger.warning(f"[PostgreSQL] No session_id provided, using base MV name: {materialized_view_name}")

            # FIX v4.2.0: Include schema in MV reference to avoid PostgreSQL using default 'public' schema
            postgresql_source_geom = '"{mv_schema}"."mv_{materialized_view_name}_dump"."{source_geom}"'.format(
                mv_schema=mv_schema,
                source_geom=source_geom,
                materialized_view_name=materialized_view_name
            )

            # NOTE: Centroids are not supported with buffer expressions (materialized views)
            # because the view already contains buffered geometries
            # ORDER OF APPLICATION: Buffer expression creates MV first, centroid cannot be applied after
            if use_centroids:
                logger.warning("[PostgreSQL] ⚠️ PostgreSQL: Centroid option ignored when using buffer expression (materialized view)")
                # v4.1.3: Notify user via QGIS message log for visibility
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    "⚠️ Centroid optimization was requested but is incompatible with buffer expressions. "
                    "The centroid option has been ignored. Consider using a static buffer value instead.",
                    "FilterMate", Qgis.Warning
                )

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
        # ORDER OF APPLICATION: ST_Buffer(ST_Centroid(geom)) - centroid first, then buffer
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
            logger.info(f"[PostgreSQL] 📐 Applying NEGATIVE buffer (erosion): {buffer_value}m")
            logger.info("[PostgreSQL]   🛡️ Wrapping in ST_MakeValid() + ST_IsEmpty check for empty geometry handling")
            validated_expr = f"ST_MakeValid({base_buffer_expr})"
            postgresql_source_geom = f"CASE WHEN ST_IsEmpty({validated_expr}) THEN NULL ELSE {validated_expr} END"
            logger.info(f"[PostgreSQL]   📝 Generated expression: {postgresql_source_geom[:150]}...")
        else:
            postgresql_source_geom = base_buffer_expr

        buffer_type_desc = "expansion" if buffer_value > 0 else "erosion"
        centroid_desc = " (on centroids)" if use_centroids else ""
        logger.info(f"[PostgreSQL] ✓ PostgreSQL source geom prepared with {buffer_value}m buffer ({buffer_type_desc}, endcap={endcap_style}, segments={buffer_segments}){centroid_desc}")
        logger.debug(f"[PostgreSQL] Using simple buffer: ST_Buffer with {buffer_value}m ({buffer_type_desc}){centroid_desc}")

    else:
        # No buffer - just apply centroid if enabled
        if use_centroids:
            postgresql_source_geom = f"ST_Centroid({base_geom})"
            logger.info("[PostgreSQL] ✓ PostgreSQL: Using ST_Centroid for source layer geometry simplification")
        else:
            postgresql_source_geom = base_geom

    logger.debug(f"[PostgreSQL] prepare_postgresql_source_geom: {postgresql_source_geom}")

    return postgresql_source_geom, materialized_view_name


def qgis_expression_to_postgis(expression: str, geom_col: str = 'geometry') -> str:
    """
    Convert QGIS expression to PostGIS SQL.

    EPIC-1 Phase E4-S1: Extracted from filter_task.py line 3451 (68 lines)
    FIX v4.2.12: Added END keyword, * and / operators, multiple spaces cleanup

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
        logger.debug(f"[PostgreSQL] Expression after IF conversion: {expression}")

    # 3. Add type casting for numeric operations
    # FIX v4.2.12: Added * and / operators
    expression = expression.replace('" >', '"::numeric >').replace('">', '"::numeric >')
    expression = expression.replace('" <', '"::numeric <').replace('"<', '"::numeric <')
    expression = expression.replace('" +', '"::numeric +').replace('"+', '"::numeric +')
    expression = expression.replace('" -', '"::numeric -').replace('"-', '"::numeric -')
    expression = expression.replace('" *', '"::numeric *').replace('"*', '"::numeric *')
    expression = expression.replace('" /', '"::numeric /').replace('"/', '"::numeric /')

    # 4. Normalize SQL keywords (case-insensitive replacements)
    expression = re.sub(r'\bcase\b', ' CASE ', expression, flags=re.IGNORECASE)
    expression = re.sub(r'\bwhen\b', ' WHEN ', expression, flags=re.IGNORECASE)
    expression = re.sub(r'\bis\b', ' IS ', expression, flags=re.IGNORECASE)
    expression = re.sub(r'\bthen\b', ' THEN ', expression, flags=re.IGNORECASE)
    expression = re.sub(r'\belse\b', ' ELSE ', expression, flags=re.IGNORECASE)
    expression = re.sub(r'\bend\b', ' END ', expression, flags=re.IGNORECASE)  # FIX v4.2.12: Added END
    expression = re.sub(r'\bilike\b', ' ILIKE ', expression, flags=re.IGNORECASE)
    expression = re.sub(r'\blike\b', ' LIKE ', expression, flags=re.IGNORECASE)
    expression = re.sub(r'\bnot\b', ' NOT ', expression, flags=re.IGNORECASE)

    # 5. Add type casting for text operations
    expression = expression.replace('" NOT ILIKE', '"::text NOT ILIKE').replace('" ILIKE', '"::text ILIKE')
    expression = expression.replace('" NOT LIKE', '"::text NOT LIKE').replace('" LIKE', '"::text LIKE')

    # 6. Clean up multiple spaces (FIX v4.2.12)
    expression = re.sub(r'\s+', ' ', expression).strip()

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
    param_distant_geometry_field = layer_props.get("layer_geometry_field")

    # FIX v4.0.7 (2026-01-16): Auto-detect geometry column if stored value is invalid
    # The stored value may be "NULL" (string literal) from stale config
    # Use QgsDataSourceUri directly (more reliable than dataProvider().geometryColumn())
    if not param_distant_geometry_field or param_distant_geometry_field in ('NULL', 'None', ''):
        layer = layer_props.get("layer")
        if layer:
            # FIX v4.0.8 (2026-01-16): Check if this is a memory layer
            is_memory_layer = layer.providerType() == 'memory'

            if is_memory_layer:
                # Memory layers don't have URI-based geometry columns
                # Use layer.geometryColumn() directly
                try:
                    geom_col = layer.geometryColumn()
                    if geom_col and geom_col.strip():
                        param_distant_geometry_field = geom_col
                        logger.debug(f"[PostgreSQL] Memory layer geometry column: '{geom_col}'")
                    else:
                        param_distant_geometry_field = 'geometry'
                        logger.debug(f"[PostgreSQL] Memory layer {param_distant_table}: using default 'geometry'")
                except Exception:
                    param_distant_geometry_field = 'geometry'
            else:
                try:
                    # Directly use QgsDataSourceUri (more reliable for file-based layers)
                    from qgis.core import QgsDataSourceUri
                    uri = QgsDataSourceUri(layer.source())
                    detected_geom = uri.geometryColumn()
                    if detected_geom:
                        param_distant_geometry_field = detected_geom
                        logger.info(f"[PostgreSQL] ✓ Auto-detected geometry column for {param_distant_table}: '{detected_geom}'")
                except Exception as e:
                    logger.warning(f"[PostgreSQL] Could not auto-detect geometry column: {e}")

        # Final fallback to 'geom' (PostgreSQL default)
        if not param_distant_geometry_field or param_distant_geometry_field in ('NULL', 'None', ''):
            param_distant_geometry_field = 'geom'
            logger.warning(f"[PostgreSQL] ⚠️ Using fallback geometry column 'geom' for {param_distant_table}")

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


def apply_postgresql_type_casting(expression: str, layer=None) -> str:
    """
    Apply PostgreSQL type casting to fix common type mismatch errors.

    EPIC-1 Phase E4-S3: Extracted from filter_task.py line 1812 (40 lines)

    Handles cases like "importance" < 4 where importance is varchar.
    Adds ::numeric type casting for numeric comparisons.

    FIX v4.8.1 (2026-01-25): Apply cast INDIVIDUALLY to each comparison,
    not globally. This fixes combined expressions where some parts already
    have ::numeric but others don't. Uses negative lookahead to skip
    already-casted fields.

    Args:
        expression: SQL expression
        layer: Optional layer to get field type information

    Returns:
        str: Expression with type casting applied
    """
    import re

    if not expression:
        return expression

    # Add ::numeric type casting for numeric comparisons if not already present
    # This handles cases like "importance" < 4 → "importance"::numeric < 4
    # Pattern: "field" followed by comparison operator and number
    #
    # FIX v4.8.1: Use negative lookahead (?!::) AFTER the closing quote to ONLY
    # match fields that are NOT already casted. This allows the regex to apply
    # casting individually to each comparison in a combined expression.
    #
    # Before: "field"::numeric < 5 AND "field" < 5  → no change (global check failed)
    # After:  "field"::numeric < 5 AND "field" < 5  → "field"::numeric < 5 AND "field"::numeric < 5

    # Pattern explanation:
    # - "([^"]+)" : quoted field name
    # - (?!::) : negative lookahead - NOT followed by :: (skip already casted fields)
    # - (\s*) : optional whitespace
    # - (<|>|<=|>=|=) : comparison operator (including = for "field" = 5)
    # - (\s*) : optional whitespace
    # - (\d+(?:\.\d+)?) : integer or decimal number
    numeric_comparison_pattern = r'"([^"]+)"(?!::)(\s*)(<|>|<=|>=|=)(\s*)(\d+(?:\.\d+)?)'

    def add_numeric_cast(match):
        field = match.group(1)
        space1 = match.group(2)
        operator = match.group(3)
        space2 = match.group(4)
        number = match.group(5)
        return f'"{field}"::numeric{space1}{operator}{space2}{number}'

    # Apply to ALL numeric comparisons that don't have ::
    expression = re.sub(numeric_comparison_pattern, add_numeric_cast, expression)

    return expression


def build_spatial_join_query(
    layer_props: dict,
    param_postgis_sub_expression: str,
    sub_expression: str,
    current_materialized_view_name: str = None,
    current_materialized_view_schema: str = None,
    source_schema: str = None,
    source_table: str = None,
    expression: str = None,
    has_combine_operator: bool = False
) -> str:
    """
    Build SELECT query with spatial JOIN for filtering.

    EPIC-1 Phase E4-S3b: Extracted from filter_task.py line 6676 (56 lines)

    Constructs a PostgreSQL subquery using INNER JOIN for spatial filtering.
    The subquery returns primary key values that match the spatial predicate.

    Args:
        layer_props: Layer properties dict with schema, table, primary key
        param_postgis_sub_expression: PostGIS spatial predicate (e.g., ST_Intersects)
        sub_expression: Source layer subset expression or table reference
        current_materialized_view_name: MV name if using cached buffer (optional)
        current_materialized_view_schema: MV schema (optional)
        source_schema: Source table schema for direct table join
        source_table: Source table name for direct table join
        expression: Original filter expression for complexity check
        has_combine_operator: Whether combine operator is active

    Returns:
        str: SELECT query with INNER JOIN for use in IN clause
    """
    from qgis.core import QgsExpression

    logger = logging.getLogger('FilterMate.Adapters.Backends.PostgreSQL.FilterExecutor')

    param_distant_primary_key_name = layer_props["primary_key_name"]
    param_distant_schema = layer_props["layer_schema"]
    param_distant_table = layer_props["layer_name"]

    # Determine source reference (materialized view or direct table)
    if current_materialized_view_name:
        source_ref = f'"{current_materialized_view_schema}"."mv_{current_materialized_view_name}_dump"'
    else:
        source_ref = sub_expression

    # Check if expression is a simple field reference
    is_field = False
    if expression:
        try:
            is_field = QgsExpression(expression).isField()
        except Exception:
            pass

    # Build query based on combine operator and expression type
    if has_combine_operator:
        # With combine operator - no WHERE clause needed
        query = (
            f'(SELECT "{param_distant_table}"."{param_distant_primary_key_name}" '  # nosec B608
            f'FROM "{param_distant_schema}"."{param_distant_table}" '
            f'INNER JOIN {source_ref} ON {param_postgis_sub_expression})'
        )
    else:
        # Without combine operator - add WHERE clause if not a field
        if is_field:
            # For field expressions, use simple JOIN
            query = (
                f'(SELECT "{param_distant_table}"."{param_distant_primary_key_name}" '  # nosec B608
                f'FROM "{param_distant_schema}"."{param_distant_table}" '
                f'INNER JOIN {source_ref} ON {param_postgis_sub_expression})'
            )
        else:
            # For complex expressions, add WHERE clause
            if current_materialized_view_name:
                # Materialized view has WHERE embedded
                query = (
                    f'(SELECT "{param_distant_table}"."{param_distant_primary_key_name}" '  # nosec B608
                    f'FROM "{param_distant_schema}"."{param_distant_table}" '
                    f'INNER JOIN {source_ref} ON {param_postgis_sub_expression} '
                    f'WHERE {sub_expression})'
                )
            else:
                # Direct table JOIN with WHERE
                query = (
                    f'(SELECT "{param_distant_table}"."{param_distant_primary_key_name}" '  # nosec B608
                    f'FROM "{param_distant_schema}"."{param_distant_table}" '
                    f'INNER JOIN "{source_schema}"."{source_table}" '
                    f'ON {param_postgis_sub_expression} WHERE {sub_expression})'
                )

    logger.debug(f"[PostgreSQL] Built spatial join query: {query[:150]}...")
    return query


def apply_combine_operator(
    primary_key_name: str,
    param_expression: str,
    param_old_subset: str = None,
    param_combine_operator: str = None
) -> str:
    """
    Apply SQL set operator to combine with existing subset.

    CONSOLIDATED v4.1: Delegates to core.filter.expression_combiner.apply_combine_operator

    Wraps the subquery in an IN clause and optionally combines with
    existing subset using UNION, INTERSECT, or EXCEPT.

    Args:
        primary_key_name: Primary key field name
        param_expression: The subquery expression (from build_spatial_join_query)
        param_old_subset: Existing subset to combine with (optional)
        param_combine_operator: SQL set operator (UNION, INTERSECT, EXCEPT)

    Returns:
        str: Complete IN expression with optional combine operator
    """
    from ....core.filter.expression_combiner import apply_combine_operator as core_apply
    return core_apply(
        primary_key_name=primary_key_name,
        param_expression=param_expression,
        param_old_subset=param_old_subset,
        param_combine_operator=param_combine_operator
    )


def cleanup_session_materialized_views(
    connexion,
    schema_name: str,
    session_id: str
) -> int:
    """
    Clean up all materialized views for a specific session.

    CONSOLIDATED v4.1: Delegates to schema_manager.cleanup_session_materialized_views
    Wrapper maintained for backward compatibility.

    Args:
        connexion: psycopg2 connection
        schema_name: Schema containing the materialized views
        session_id: Session identifier prefix

    Returns:
        int: Number of views cleaned up
    """
    from .schema_manager import cleanup_session_materialized_views as schema_cleanup
    return schema_cleanup(connexion, schema_name, session_id)


def execute_postgresql_commands(
    connexion,
    commands: list,
    source_layer=None,
    reconnect_func=None
) -> bool:
    """
    Execute PostgreSQL commands with automatic reconnection on failure.

    EPIC-1 Phase E4-S4: Extracted from filter_task.py line 11101 (~27 lines)

    Args:
        connexion: psycopg2 connection
        commands: List of SQL commands to execute
        source_layer: Optional layer for reconnection
        reconnect_func: Optional function to reconnect (e.g., get_datasource_connexion_from_layer)

    Returns:
        bool: True if all commands succeeded
    """
    import psycopg2

    # Test connection
    try:
        with connexion.cursor() as cursor:
            cursor.execute("SELECT 1")
    except (psycopg2.OperationalError, psycopg2.InterfaceError, AttributeError) as e:
        logger.debug(f"[PostgreSQL] PostgreSQL connection test failed, reconnecting: {e}")
        if reconnect_func and source_layer:
            connexion, _ = reconnect_func(source_layer)

    # Execute commands
    with connexion.cursor() as cursor:
        for command in commands:
            cursor.execute(command)
            connexion.commit()

    return True


def ensure_source_table_stats(
    connexion,
    schema: str,
    table: str,
    geom_field: str
) -> bool:
    """
    Ensure PostgreSQL statistics exist for source table geometry column.

    EPIC-1 Phase E4-S4: Extracted from filter_task.py line 11128 (~40 lines)

    Checks pg_stats for geometry column statistics and runs ANALYZE if missing.
    This prevents "stats for X.geom do not exist" warnings from PostgreSQL
    query planner.

    Args:
        connexion: psycopg2 connection
        schema: Table schema name
        table: Table name
        geom_field: Geometry column name

    Returns:
        bool: True if stats exist or were created, False on error
    """
    try:
        with connexion.cursor() as cursor:
            # Check if stats exist for geometry column
            cursor.execute("""
                SELECT COUNT(*) FROM pg_stats
                WHERE schemaname = %s
                AND tablename = %s
                AND attname = %s;
            """, (schema, table, geom_field))

            result = cursor.fetchone()
            has_stats = result[0] > 0 if result else False

            if not has_stats:
                safe_schema = sanitize_sql_identifier(schema)
                safe_table = sanitize_sql_identifier(table)
                logger.info(f"Running ANALYZE on source table \"{safe_schema}\".\"{safe_table}\" (missing stats for {geom_field})")
                cursor.execute(f'ANALYZE "{safe_schema}"."{safe_table}";')
                connexion.commit()
                logger.debug(f"ANALYZE completed for \"{safe_schema}\".\"{safe_table}\"")

            return True

    except Exception as e:
        logger.warning(f"Could not check/create stats for \"{schema}\".\"{table}\": {e}")
        return False


def normalize_column_names_for_postgresql(expression: str, field_names: list) -> str:
    """
    Normalize column names in expression to match actual PostgreSQL column names.

    EPIC-1 Phase E4-S4: Extracted from filter_task.py line 7006 (49 lines)

    PostgreSQL is case-sensitive for quoted identifiers. If columns were created
    without quotes, they are stored in lowercase. This function corrects column
    names in filter expressions to match the actual column names.

    For example: "SUB_TYPE" → "sub_type" if the column exists as "sub_type"

    Args:
        expression: SQL expression string
        field_names: List of actual field names from the layer

    Returns:
        str: Expression with corrected column names
    """
    import re

    if not expression or not field_names:
        return expression

    result_expression = expression

    # Build case-insensitive lookup map: lowercase → actual name
    field_lookup = {name.lower(): name for name in field_names}

    # Find all quoted column names in expression (e.g., "SUB_TYPE")
    quoted_cols = re.findall(r'"([^"]+)"', result_expression)

    corrections_made = []
    for col_name in quoted_cols:
        # Skip if column exists with exact case (no correction needed)
        if col_name in field_names:
            continue

        # Check for case-insensitive match
        col_lower = col_name.lower()
        if col_lower in field_lookup:
            correct_name = field_lookup[col_lower]
            # Replace the incorrectly cased column name with correct one
            result_expression = result_expression.replace(
                f'"{col_name}"',
                f'"{correct_name}"'
            )
            corrections_made.append(f'"{col_name}" → "{correct_name}"')

    if corrections_made:
        logger.info(f"[PostgreSQL] PostgreSQL column case normalization: {', '.join(corrections_made)}")

    return result_expression


def qualify_field_names_in_expression(
    expression: str,
    field_names: list,
    primary_key_name: str,
    table_name: str,
    is_postgresql: bool = True,
    provider_type: str = None
) -> str:
    """
    Qualify field names with table prefix for PostgreSQL/Spatialite expressions.

    EPIC-1 Phase E4-S4: Extracted from filter_task.py line 7056 (90 lines)

    This helper adds table qualifiers to field names in QGIS expressions to make them
    compatible with PostgreSQL/Spatialite queries (e.g., "field" becomes "table"."field").

    For OGR providers, field names are NOT qualified (just wrapped in quotes if needed).

    Args:
        expression: Raw QGIS expression string
        field_names: List of field names to qualify
        primary_key_name: Primary key field name
        table_name: Source table name
        is_postgresql: Whether target is PostgreSQL (True) or other provider (False)
        provider_type: Provider type string (optional, for OGR/Spatialite detection)

    Returns:
        str: Expression with qualified field names (PostgreSQL/Spatialite) or simple quoted names (OGR)
    """
    result_expression = expression

    # CRITICAL FIX: For PostgreSQL, first normalize column names to match actual database column case
    if is_postgresql:
        all_fields = list(field_names) + ([primary_key_name] if primary_key_name else [])
        result_expression = normalize_column_names_for_postgresql(result_expression, all_fields)

    # For OGR and Spatialite, just ensure field names are quoted, no table qualification
    if provider_type in ('ogr', 'spatialite'):
        # Handle primary key
        if primary_key_name in result_expression and f'"{primary_key_name}"' not in result_expression:
            result_expression = result_expression.replace(
                f' {primary_key_name} ',
                f' "{primary_key_name}" '
            )

        # Handle other fields
        for field_name in field_names:
            if field_name in result_expression and f'"{field_name}"' not in result_expression:
                result_expression = result_expression.replace(
                    f' {field_name} ',
                    f' "{field_name}" '
                )

        return result_expression

    # PostgreSQL: Add table qualification
    # Handle primary key
    if primary_key_name in result_expression:
        if table_name not in result_expression:
            if f' "{primary_key_name}" ' in result_expression:
                if is_postgresql:
                    result_expression = result_expression.replace(
                        f'"{primary_key_name}"',
                        f'"{table_name}"."{primary_key_name}"'
                    )
            elif f" {primary_key_name} " in result_expression:
                if is_postgresql:
                    result_expression = result_expression.replace(
                        primary_key_name,
                        f'"{table_name}"."{primary_key_name}"'
                    )
                else:
                    result_expression = result_expression.replace(
                        primary_key_name,
                        f'"{primary_key_name}"'
                    )

    # Handle other fields
    existing_fields = [x for x in field_names if x in result_expression]
    if existing_fields and table_name not in result_expression:
        for field_name in existing_fields:
            if f' "{field_name}" ' in result_expression:
                if is_postgresql:
                    result_expression = result_expression.replace(
                        f'"{field_name}"',
                        f'"{table_name}"."{field_name}"'
                    )
            elif f" {field_name} " in result_expression:
                if is_postgresql:
                    result_expression = result_expression.replace(
                        field_name,
                        f'"{table_name}"."{field_name}"'
                    )
                else:
                    result_expression = result_expression.replace(
                        field_name,
                        f'"{field_name}"'
                    )

    return result_expression


def format_pk_values_for_sql(
    values: list,
    is_numeric: bool = None,
    layer=None,
    pk_field: str = None
) -> str:
    """
    Format primary key values for SQL IN clause.

    CONSOLIDATED v4.1: Delegates to core.filter.pk_formatter for DRY compliance.
    Wrapper maintained for backward compatibility.

    Args:
        values: List of primary key values
        is_numeric: Whether PK is numeric (optional, auto-detected if None)
        layer: QgsVectorLayer to check PK type (optional)
        pk_field: Primary key field name (optional)

    Returns:
        str: Comma-separated values formatted for SQL IN clause
    """
    # Delegate to the canonical implementation
    from ....core.filter.pk_formatter import format_pk_values_for_sql as core_format
    return core_format(
        values=values,
        is_numeric=is_numeric,
        layer=layer,
        pk_field=pk_field
    )


def _is_pk_numeric(layer, pk_field: str) -> bool:
    """
    Check if primary key field is numeric.

    Args:
        layer: QgsVectorLayer
        pk_field: Primary key field name

    Returns:
        bool: True if numeric, False otherwise (defaults to True if unknown)
    """
    if not layer or not pk_field:
        return True  # Default to numeric assumption

    try:
        from qgis.PyQt.QtCore import QVariant
        field_idx = layer.fields().indexOf(pk_field)
        if field_idx >= 0:
            field_type = layer.fields().at(field_idx).type()
            # Check for numeric types
            numeric_types = [
                QVariant.Int, QVariant.UInt, QVariant.LongLong,
                QVariant.ULongLong, QVariant.Double
            ]
            return field_type in numeric_types
    except Exception:
        pass

    return True  # Default to numeric


def build_postgis_filter_expression(
    layer_props: dict,
    param_postgis_sub_expression: str,
    sub_expression: str,
    param_old_subset: str = None,
    param_combine_operator: str = None,
    current_materialized_view_name: str = None,
    current_materialized_view_schema: str = None,
    source_schema: str = None,
    source_table: str = None,
    expression: str = None,
    has_combine_operator: bool = False
) -> tuple:
    """
    Build complete PostGIS filter expression for subset string.

    EPIC-1 Phase E4-S4b: Extracted from filter_task.py line 2748 (30 lines)

    Combines build_spatial_join_query and apply_combine_operator to create
    the final expression suitable for layer.setSubsetString().

    Args:
        layer_props: Layer properties dict with schema, table, primary key
        param_postgis_sub_expression: PostGIS spatial predicate (e.g., ST_Intersects)
        sub_expression: Source layer subset expression or table reference
        param_old_subset: Existing subset string from layer (optional)
        param_combine_operator: SQL set operator (UNION, INTERSECT, EXCEPT) (optional)
        current_materialized_view_name: MV name if using cached buffer (optional)
        current_materialized_view_schema: MV schema (optional)
        source_schema: Source table schema for direct table join
        source_table: Source table name for direct table join
        expression: Original filter expression for complexity check
        has_combine_operator: Whether combine operator is active

    Returns:
        tuple: (expression, param_expression) - Complete filter and subquery
    """
    param_distant_primary_key_name = layer_props["primary_key_name"]

    # Build spatial join subquery
    param_expression = build_spatial_join_query(
        layer_props=layer_props,
        param_postgis_sub_expression=param_postgis_sub_expression,
        sub_expression=sub_expression,
        current_materialized_view_name=current_materialized_view_name,
        current_materialized_view_schema=current_materialized_view_schema,
        source_schema=source_schema,
        source_table=source_table,
        expression=expression,
        has_combine_operator=has_combine_operator
    )

    # Apply combine operator if specified
    final_expression = apply_combine_operator(
        primary_key_name=param_distant_primary_key_name,
        param_expression=param_expression,
        param_old_subset=param_old_subset,
        param_combine_operator=param_combine_operator
    )

    return final_expression, param_expression

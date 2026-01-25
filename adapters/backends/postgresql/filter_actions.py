"""
PostgreSQL Filter Actions

EPIC-1 Phase E5/E6: PostgreSQL-specific filter action execution.

This module contains the PostgreSQL filter action methods extracted from 
FilterTask._filter_action_postgresql*, providing:
- Direct filtering (for small datasets using setSubsetString)
- Materialized view filtering (for large datasets with spatial indexes)

The functions are pure utilities that receive all dependencies as parameters,
making them testable and reusable outside of FilterTask context.

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase E5/E6)
"""

import logging
import re
import time
from typing import Optional, Tuple, Callable, Any

# EPIC-1 E4-S9: Import centralized HistoryRepository
from ...repositories.history_repository import HistoryRepository

logger = logging.getLogger('FilterMate.Adapters.Backends.PostgreSQL.FilterActions')


# =============================================================================
# Constants
# =============================================================================

# v4.2.12: Increased threshold - MV only for very large datasets
# MV adds overhead, prefer direct setSubsetString for most cases
MATERIALIZED_VIEW_THRESHOLD = 100000  # Features threshold for using materialized views

# v4.2.12: Secondary threshold for complex chaining scenarios
# When filter involves multiple spatial joins (chaining), use lower threshold
CHAINED_FILTER_MV_THRESHOLD = 50000

# Spatial predicates that indicate expensive expressions requiring materialization
SPATIAL_PREDICATES = [
    'ST_INTERSECTS', 'ST_CONTAINS', 'ST_WITHIN', 'ST_TOUCHES',
    'ST_OVERLAPS', 'ST_CROSSES', 'ST_DISJOINT', 'ST_EQUALS',
    'ST_DWITHIN', 'ST_COVERS', 'ST_COVEREDBY'
]

# Patterns indicating QGIS style/symbology expressions (should not be combined)
STYLE_PATTERNS = [
    r'AND\s+TRUE\s*\)',           # Pattern: AND TRUE) - common in rule-based styles
    r'THEN\s+true',               # CASE WHEN ... THEN true - style expression
    r'THEN\s+false',              # CASE WHEN ... THEN false
    r'SELECT\s+CASE',             # SELECT CASE in subquery
    r'\)\s*AND\s+TRUE\s*\)',      # (...) AND TRUE) pattern
]


# =============================================================================
# Helper Functions
# =============================================================================

def has_expensive_spatial_expression(sql_string: str) -> bool:
    """
    Check if SQL contains complex spatial predicates that are expensive to re-execute.
    
    DELEGATION: This function delegates to core.optimization.query_analyzer.
    
    Args:
        sql_string: SQL expression to check
        
    Returns:
        bool: True if expression contains expensive spatial operations
    """
    from ....core.optimization.query_analyzer import has_expensive_spatial_expression as canonical_check
    return canonical_check(sql_string)


def _is_chained_spatial_filter(sql_string: str) -> bool:
    """
    Check if SQL contains chained spatial filters (multiple EXISTS with spatial predicates).
    
    v4.2.12: Detects filter chaining scenarios where MV optimization is beneficial.
    
    Patterns detected:
    - Multiple EXISTS clauses with spatial predicates
    - JOIN between multiple spatial tables
    - Nested spatial subqueries
    
    Args:
        sql_string: SQL expression to check
        
    Returns:
        bool: True if filter involves chaining multiple spatial operations
    """
    if not sql_string:
        return False
    
    sql_upper = sql_string.upper()
    
    # Count EXISTS clauses with spatial predicates
    exists_count = sql_upper.count('EXISTS (') + sql_upper.count('EXISTS(')
    
    # Multiple EXISTS = chaining
    if exists_count >= 2:
        logger.debug(f"Detected chained filter: {exists_count} EXISTS clauses")
        return True
    
    # Multiple spatial predicates in different subqueries
    spatial_predicates = ['ST_INTERSECTS', 'ST_CONTAINS', 'ST_WITHIN', 'ST_DWITHIN']
    spatial_count = sum(sql_upper.count(pred) for pred in spatial_predicates)
    
    if spatial_count >= 2 and exists_count >= 1:
        logger.debug(f"Detected chained filter: {spatial_count} spatial predicates")
        return True
    
    return False


def _is_very_complex_expression(sql_string: str) -> bool:
    """
    Check if SQL is very complex, warranting MV even for smaller datasets.
    
    v4.2.12: Only returns True for truly expensive patterns that would
    cause significant slowdown during map rendering.
    
    Very complex patterns:
    - EXISTS + ST_Buffer (buffer computed per row in subquery)
    - Multiple nested EXISTS
    - EXISTS with IN clause containing many IDs
    
    Args:
        sql_string: SQL expression to check
        
    Returns:
        bool: True if expression is very complex
    """
    if not sql_string:
        return False
    
    sql_upper = sql_string.upper()
    
    # Pattern 1: EXISTS + ST_Buffer - very expensive (buffer per row)
    has_exists = 'EXISTS' in sql_upper
    has_buffer = 'ST_BUFFER' in sql_upper
    
    if has_exists and has_buffer:
        logger.debug("Very complex: EXISTS + ST_Buffer")
        return True
    
    # Pattern 2: Multiple nested EXISTS (3+)
    exists_count = sql_upper.count('EXISTS (') + sql_upper.count('EXISTS(')
    if exists_count >= 3:
        logger.debug(f"Very complex: {exists_count} nested EXISTS")
        return True
    
    # Pattern 3: EXISTS combined with large IN clause (>500 IDs)
    if has_exists and ' IN (' in sql_upper:
        # Rough estimate of IN clause size
        in_pos = sql_upper.find(' IN (')
        if in_pos > 0:
            # Count commas in IN clause (rough approximation)
            remaining = sql_upper[in_pos:in_pos + 5000]  # Check first 5000 chars
            comma_count = remaining.count(',')
            if comma_count > 500:
                logger.debug(f"Very complex: EXISTS + large IN clause ({comma_count}+ items)")
                return True
    
    return False


def should_combine_filters(old_subset: str) -> Tuple[bool, str]:
    """
    Determine if a new filter should be combined with an existing subset.
    
    Analyzes the old subset for patterns that indicate it should be replaced
    rather than combined (e.g., geometric filters, style expressions).
    
    Args:
        old_subset: Existing layer subset string
        
    Returns:
        Tuple[bool, str]: (should_combine, reason_if_not_combining)
    """
    if not old_subset:
        return False, "no existing filter"
    
    old_subset_upper = old_subset.upper()
    reasons = []
    
    # Pattern 1: __source alias (only valid inside EXISTS subqueries)
    if '__source' in old_subset.lower():
        reasons.append("__source alias")
    
    # Pattern 2: EXISTS subquery (avoid nested EXISTS)
    if 'EXISTS (' in old_subset_upper or 'EXISTS(' in old_subset_upper:
        reasons.append("EXISTS subquery")
    
    # Pattern 3: Spatial predicates (likely from previous geometric filter)
    if any(pred in old_subset_upper for pred in SPATIAL_PREDICATES):
        reasons.append("spatial predicate")
    
    # Pattern 4: FilterMate materialized view reference
    if re.search(
        r'IN\s*\(\s*SELECT.*FROM\s+["\']?filter_mate_temp["\']?\s*\.\s*["\']?mv_',
        old_subset,
        re.IGNORECASE | re.DOTALL
    ):
        reasons.append("FilterMate materialized view (mv_)")
    
    # Pattern 5: QGIS style/symbology expressions
    if any(re.search(pattern, old_subset, re.IGNORECASE) for pattern in STYLE_PATTERNS):
        reasons.append("QGIS style patterns")
    
    if reasons:
        return False, ", ".join(reasons)
    
    return True, ""


def build_combined_expression(
    old_subset: str,
    new_where_clause: str
) -> str:
    """
    Build the final filter expression, optionally combining with existing subset.
    
    Args:
        old_subset: Existing layer subset string (can be empty)
        new_where_clause: New WHERE clause to apply
        
    Returns:
        str: Final filter expression
    """
    if not old_subset:
        return new_where_clause
    
    should_combine, reason = should_combine_filters(old_subset)
    
    if not should_combine:
        logger.info(f"[PostgreSQL] Old subset contains {reason} - replacing instead of combining")
        return new_where_clause
    
    # Check if filters are identical (avoid duplication)
    normalized_old = old_subset.strip().strip('()')
    normalized_new = new_where_clause.strip().strip('()')
    
    if normalized_old == normalized_new:
        logger.debug(f"[PostgreSQL] New filter identical to existing - replacing instead of combining")
        return new_where_clause
    
    # Different filters - combine with AND
    logger.debug(f"[PostgreSQL] Combining with existing filter: {old_subset[:50]}...")
    return f"({old_subset}) AND ({new_where_clause})"


# =============================================================================
# Main Filter Action Functions
# =============================================================================

def execute_filter_action_postgresql(
    layer,
    sql_subset_string: str,
    primary_key_name: str,
    geom_key_name: str,
    name: str,
    custom: bool,
    cur,
    conn,
    seq_order: int,
    # Callback functions for delegation
    queue_subset_fn: Callable,
    get_connection_fn: Callable,
    ensure_stats_fn: Callable,
    extract_where_fn: Callable,
    insert_history_fn: Callable,
    get_session_name_fn: Callable,
    ensure_schema_fn: Callable,
    execute_commands_fn: Callable,
    create_simple_mv_fn: Callable,
    create_custom_mv_fn: Callable,
    parse_where_clauses_fn: Callable = None,
    # Context parameters
    source_schema: str = None,
    source_table: str = None,
    source_geom: str = None,
    current_mv_schema: str = "filter_mate_temp",
    project_uuid: str = None,
    session_id: str = None,
    param_buffer_expression: str = None
) -> bool:
    """
    Execute filter action using PostgreSQL backend.
    
    v4.2.12: Conservative MV usage - direct setSubsetString is preferred.
    
    Adapts filtering strategy based on dataset size and expression complexity:
    - Most cases: Uses direct setSubsetString (fast, no overhead)
    - Very large datasets (≥100k features): Uses materialized views
    - Chained filters (≥50k features): Uses materialized views
    - Very complex expressions (EXISTS+Buffer, ≥10k): Uses materialized views
    
    Args:
        layer: QgsVectorLayer to filter
        sql_subset_string: SQL SELECT statement
        primary_key_name: Primary key field name
        geom_key_name: Geometry field name
        name: Layer identifier
        custom: Whether this is a custom buffer filter
        cur: Database cursor
        conn: Database connection
        seq_order: Sequence order number
        queue_subset_fn: Function to queue subset string for main thread
        get_connection_fn: Function to get PostgreSQL connection
        ensure_stats_fn: Function to ensure table statistics
        extract_where_fn: Function to extract WHERE clause from SELECT
        insert_history_fn: Function to insert subset history
        get_session_name_fn: Function to get session-prefixed name
        ensure_schema_fn: Function to ensure temp schema exists
        execute_commands_fn: Function to execute PostgreSQL commands
        create_simple_mv_fn: Function to create simple materialized view SQL
        create_custom_mv_fn: Function to create custom buffer view SQL
        parse_where_clauses_fn: Function to parse WHERE clauses for custom buffer
        source_schema: Source table schema
        source_table: Source table name
        source_geom: Source geometry column
        current_mv_schema: Current materialized view schema
        project_uuid: Project UUID for history
        session_id: Session ID for view naming
        param_buffer_expression: Buffer expression for custom mode
            
    Returns:
        bool: True if successful
    """
    # Get feature count to determine strategy
    feature_count = layer.featureCount()
    
    # v4.2.12: More conservative MV usage - only for truly complex cases
    # MV adds overhead (creation time, cleanup), prefer direct setSubsetString
    
    # Check complexity indicators
    has_complex_expression = has_expensive_spatial_expression(sql_subset_string)
    is_chained_filter = _is_chained_spatial_filter(sql_subset_string)
    is_very_complex = _is_very_complex_expression(sql_subset_string)
    
    # v4.2.12: Decision matrix for MV usage
    # MV only when: (1) very large dataset, (2) complex chaining, (3) very complex expression
    use_materialized_view = False
    mv_reason = ""
    
    # Case 1: Very large dataset (>100k) - always use MV
    if feature_count >= MATERIALIZED_VIEW_THRESHOLD:
        use_materialized_view = True
        mv_reason = f"very large dataset ({feature_count:,} features ≥ {MATERIALIZED_VIEW_THRESHOLD:,})"
    
    # Case 2: Chained spatial filter with large-ish dataset (>50k)
    elif is_chained_filter and feature_count >= CHAINED_FILTER_MV_THRESHOLD:
        use_materialized_view = True
        mv_reason = f"chained filter with {feature_count:,} features"
    
    # Case 3: Very complex expression (multiple EXISTS + buffer + spatial)
    # Only if dataset is not tiny (>10k) to justify MV overhead
    elif is_very_complex and feature_count >= 10000:
        use_materialized_view = True
        mv_reason = "very complex expression with spatial predicates"
    
    # Case 4: Custom buffer expression - evaluate based on complexity
    # v4.2.12: Don't automatically use MV for custom, only if dataset large enough
    elif custom and feature_count >= CHAINED_FILTER_MV_THRESHOLD:
        use_materialized_view = True
        mv_reason = f"custom buffer expression with {feature_count:,} features"
    
    if use_materialized_view:
        # Log strategy decision
        logger.info(
            f"[PostgreSQL] Using materialized view: {mv_reason}"
        )
        
        return execute_filter_action_postgresql_materialized(
            layer=layer,
            sql_subset_string=sql_subset_string,
            primary_key_name=primary_key_name,
            geom_key_name=geom_key_name,
            name=name,
            custom=custom,
            cur=cur,
            conn=conn,
            seq_order=seq_order,
            queue_subset_fn=queue_subset_fn,
            get_connection_fn=get_connection_fn,
            ensure_stats_fn=ensure_stats_fn,
            insert_history_fn=insert_history_fn,
            get_session_name_fn=get_session_name_fn,
            ensure_schema_fn=ensure_schema_fn,
            execute_commands_fn=execute_commands_fn,
            create_simple_mv_fn=create_simple_mv_fn,
            create_custom_mv_fn=create_custom_mv_fn,
            parse_where_clauses_fn=parse_where_clauses_fn,
            source_schema=source_schema,
            source_table=source_table,
            source_geom=source_geom,
            current_mv_schema=current_mv_schema,
            project_uuid=project_uuid,
            session_id=session_id,
            param_buffer_expression=param_buffer_expression
        )
    else:
        # Small dataset - use direct setSubsetString
        logger.info(
            f"PostgreSQL: Small dataset ({feature_count:,} features < {MATERIALIZED_VIEW_THRESHOLD:,}). "
            "Using direct setSubsetString for simplicity."
        )
        
        return execute_filter_action_postgresql_direct(
            layer=layer,
            sql_subset_string=sql_subset_string,
            primary_key_name=primary_key_name,
            cur=cur,
            conn=conn,
            seq_order=seq_order,
            queue_subset_fn=queue_subset_fn,
            get_connection_fn=get_connection_fn,
            ensure_stats_fn=ensure_stats_fn,
            extract_where_fn=extract_where_fn,
            insert_history_fn=insert_history_fn,
            source_schema=source_schema,
            source_table=source_table,
            source_geom=source_geom,
            # Fallback to materialized if direct fails
            fallback_to_materialized_fn=lambda: execute_filter_action_postgresql_materialized(
                layer=layer,
                sql_subset_string=sql_subset_string,
                primary_key_name=primary_key_name,
                geom_key_name=geom_key_name,
                name=name,
                custom=False,
                cur=cur,
                conn=conn,
                seq_order=seq_order,
                queue_subset_fn=queue_subset_fn,
                get_connection_fn=get_connection_fn,
                ensure_stats_fn=ensure_stats_fn,
                insert_history_fn=insert_history_fn,
                get_session_name_fn=get_session_name_fn,
                ensure_schema_fn=ensure_schema_fn,
                execute_commands_fn=execute_commands_fn,
                create_simple_mv_fn=create_simple_mv_fn,
                create_custom_mv_fn=create_custom_mv_fn,
                parse_where_clauses_fn=parse_where_clauses_fn,
                source_schema=source_schema,
                source_table=source_table,
                source_geom=source_geom,
                current_mv_schema=current_mv_schema,
                project_uuid=project_uuid,
                session_id=session_id,
                param_buffer_expression=param_buffer_expression
            )
        )


def execute_filter_action_postgresql_direct(
    layer,
    sql_subset_string: str,
    primary_key_name: str,
    cur,
    conn,
    seq_order: int,
    # Callback functions
    queue_subset_fn: Callable,
    get_connection_fn: Callable,
    ensure_stats_fn: Callable,
    extract_where_fn: Callable,
    insert_history_fn: Callable,
    # Context parameters
    source_schema: str = None,
    source_table: str = None,
    source_geom: str = None,
    fallback_to_materialized_fn: Callable = None
) -> bool:
    """
    Execute PostgreSQL filter using direct setSubsetString (for small datasets).
    
    This method is simpler and faster for small datasets because it:
    - Avoids creating/dropping materialized views
    - Avoids creating spatial indexes
    - Uses PostgreSQL's query optimizer directly
    
    Args:
        layer: QgsVectorLayer to filter
        sql_subset_string: SQL SELECT statement
        primary_key_name: Primary key field name
        cur: Database cursor
        conn: Database connection
        seq_order: Sequence order number
        queue_subset_fn: Function to queue subset string
        get_connection_fn: Function to get PostgreSQL connection
        ensure_stats_fn: Function to ensure table statistics
        extract_where_fn: Function to extract WHERE clause
        insert_history_fn: Function to insert history
        source_schema: Source table schema
        source_table: Source table name
        source_geom: Source geometry column
        fallback_to_materialized_fn: Fallback function if direct fails
            
    Returns:
        bool: True if successful
    """
    start_time = time.time()
    
    # Ensure source table has statistics for query optimization
    connexion = get_connection_fn()
    ensure_stats_fn(connexion, source_schema, source_table, source_geom)
    
    try:
        # Extract WHERE clause from SELECT statement
        where_clause = extract_where_fn(sql_subset_string)
        
        if where_clause:
            # FIX 2026-01-16: Strip leading "WHERE " from where_clause
            # extract_where_fn returns "WHERE expression" but setSubsetString
            # expects just the expression without "WHERE" keyword
            # QGIS internally builds "SELECT * FROM table WHERE <subset_string>"
            clean_where_clause = where_clause.lstrip()
            if clean_where_clause.upper().startswith('WHERE '):
                clean_where_clause = clean_where_clause[6:].lstrip()
            
            # Get existing subset to preserve filter chain
            old_subset = layer.subsetString()
            
            # Build final expression (combine or replace)
            final_expression = build_combined_expression(old_subset, clean_where_clause)
            
            logger.debug(f"[PostgreSQL] Direct filter expression: {final_expression[:200]}...")
            
            # THREAD SAFETY: Queue filter for application in finished()
            queue_subset_fn(layer, final_expression)
            
            # Log intent (actual application happens in finished())
            elapsed = time.time() - start_time
            logger.info(
                f"Direct PostgreSQL filter queued in {elapsed:.3f}s. "
                "Will be applied on main thread."
            )
            
            # Insert history
            insert_history_fn(cur, conn, layer, sql_subset_string, seq_order)
            return True
        else:
            logger.warning(f"[PostgreSQL] Could not extract WHERE clause from: {sql_subset_string[:100]}...")
            # Fallback to materialized view approach
            if fallback_to_materialized_fn:
                logger.info(f"[PostgreSQL] Falling back to materialized view approach")
                return fallback_to_materialized_fn()
            return False
            
    except Exception as e:
        logger.error(f"[PostgreSQL] Error applying direct PostgreSQL filter: {str(e)}")
        import traceback
        logger.debug(f"[PostgreSQL] Traceback: {traceback.format_exc()}")
        return False


def execute_filter_action_postgresql_materialized(
    layer,
    sql_subset_string: str,
    primary_key_name: str,
    geom_key_name: str,
    name: str,
    custom: bool,
    cur,
    conn,
    seq_order: int,
    # Callback functions
    queue_subset_fn: Callable,
    get_connection_fn: Callable,
    ensure_stats_fn: Callable,
    insert_history_fn: Callable,
    get_session_name_fn: Callable,
    ensure_schema_fn: Callable,
    execute_commands_fn: Callable,
    create_simple_mv_fn: Callable,
    create_custom_mv_fn: Callable,
    parse_where_clauses_fn: Callable = None,
    # Context parameters
    source_schema: str = None,
    source_table: str = None,
    source_geom: str = None,
    current_mv_schema: str = "filter_mate_temp",
    project_uuid: str = None,
    session_id: str = None,
    param_buffer_expression: str = None
) -> bool:
    """
    Execute PostgreSQL filter using materialized views (for large datasets).
    
    This method provides optimal performance for large datasets by:
    - Creating indexed materialized views on the server
    - Using GIST spatial indexes for fast spatial queries
    - Clustering data for sequential read optimization
    
    Args:
        layer: QgsVectorLayer to filter
        sql_subset_string: SQL SELECT statement
        primary_key_name: Primary key field name
        geom_key_name: Geometry field name
        name: Layer identifier
        custom: Whether this is a custom buffer filter
        cur: Database cursor
        conn: Database connection
        seq_order: Sequence order number
        queue_subset_fn: Function to queue subset string
        get_connection_fn: Function to get PostgreSQL connection
        ensure_stats_fn: Function to ensure table statistics
        insert_history_fn: Function to insert history
        get_session_name_fn: Function to get session-prefixed name
        ensure_schema_fn: Function to ensure temp schema exists
        execute_commands_fn: Function to execute SQL commands
        create_simple_mv_fn: Function to create simple MV SQL
        create_custom_mv_fn: Function to create custom buffer MV SQL
        parse_where_clauses_fn: Function to parse WHERE clauses
        source_schema: Source table schema
        source_table: Source table name
        source_geom: Source geometry column
        current_mv_schema: Schema for materialized views
        project_uuid: Project UUID for history
        session_id: Session ID for view naming
        param_buffer_expression: Buffer expression for custom mode
            
    Returns:
        bool: True if successful
    """
    from ....infrastructure.database.sql_utils import sanitize_sql_identifier
    
    start_time = time.time()
    
    # Generate session-unique view name for multi-client isolation
    # FIX v4.2.0: For custom buffer expressions, use source_table + '_buffer_expr' as base name
    # This must match the name generated in filter_executor.prepare_postgresql_source_geom()
    if custom and param_buffer_expression:
        base_name = sanitize_sql_identifier(source_table + '_buffer_expr')
        session_name = get_session_name_fn(base_name)
        logger.debug(f"[PostgreSQL] Using session-prefixed MV name for buffer expr: {session_name}")
    else:
        session_name = get_session_name_fn(name)
    logger.debug(f"[PostgreSQL] Using session-prefixed view name: {session_name} (session_id: {session_id})")
    
    # Ensure temp schema exists before creating materialized views
    connexion = get_connection_fn()
    schema = ensure_schema_fn(connexion, current_mv_schema)
    
    # Ensure source table has statistics for query optimization
    ensure_stats_fn(connexion, source_schema, source_table, geom_key_name)
    
    # Build SQL commands using session-prefixed name (v4.4.4: fm_temp_mv_ prefix)
    sql_drop = (
        f'DROP INDEX IF EXISTS {schema}_{session_name}_cluster CASCADE; '
        f'DROP MATERIALIZED VIEW IF EXISTS \"{schema}\".\"fm_temp_mv_{session_name}\" CASCADE;'
    )
    
    if custom:
        # Parse custom buffer expression
        sql_drop += f' DROP MATERIALIZED VIEW IF EXISTS \"{schema}\".\"fm_temp_mv_{session_name}_dump\" CASCADE;'
        
        # EPIC-1 E4-S9: Use centralized HistoryRepository instead of direct SQL
        history_repo = HistoryRepository(conn, cur)
        try:
            last_entry = history_repo.get_last_entry(project_uuid, layer.id())
            last_subset_id = last_entry.id if last_entry else None
        finally:
            history_repo.close()
        
        # Parse WHERE clauses
        if param_buffer_expression and parse_where_clauses_fn:
            where_clause = param_buffer_expression.replace('CASE', '').replace('END', '').replace('IF', '').replace('ELSE', '').replace('\r', ' ').replace('\n', ' ')
            where_clauses = parse_where_clauses_fn()
            where_clause_fields_arr = [clause.split(' ')[0] for clause in where_clauses]
        else:
            logger.warning(f"[PostgreSQL] Custom buffer requested but param_buffer_expression is None, using simple view")
            where_clause_fields_arr = []
        
        sql_create = create_custom_mv_fn(
            schema, session_name, geom_key_name, 
            where_clause_fields_arr, last_subset_id, sql_subset_string
        )
    else:
        sql_create = create_simple_mv_fn(schema, session_name, sql_subset_string)
    
    sql_create_index = (
        f'CREATE INDEX IF NOT EXISTS {schema}_{session_name}_cluster '
        f'ON \"{schema}\".\"fm_temp_mv_{session_name}\" USING GIST ({geom_key_name});'
    )
    sql_cluster = (
        f'ALTER MATERIALIZED VIEW IF EXISTS \"{schema}\".\"fm_temp_mv_{session_name}\" '
        f'CLUSTER ON {schema}_{session_name}_cluster;'
    )
    sql_analyze = f'ANALYZE VERBOSE \"{schema}\".\"fm_temp_mv_{session_name}\";'
    
    sql_create = sql_create.replace('\n', '').replace('\t', '').replace('  ', ' ').strip()
    logger.debug(f"[PostgreSQL] SQL drop request: {sql_drop}")
    logger.debug(f"[PostgreSQL] SQL create request: {sql_create}")
    
    # Execute PostgreSQL commands
    connexion = get_connection_fn()
    commands = [sql_drop, sql_create, sql_create_index, sql_cluster, sql_analyze]
    
    if custom:
        sql_dump = (
            f'CREATE MATERIALIZED VIEW IF NOT EXISTS \"{schema}\".\"fm_temp_mv_{session_name}_dump\" '
            f'as SELECT ST_Union(\"{geom_key_name}\") as {geom_key_name} '
            f'from \"{schema}\".\"fm_temp_mv_{session_name}\";'
        )
        commands.append(sql_dump)
    
    execute_commands_fn(connexion, commands)
    
    # Insert history
    insert_history_fn(cur, conn, layer, sql_subset_string, seq_order)
    
    # Set subset string on layer using session-prefixed view name
    # THREAD SAFETY: Queue for application in finished()
    layer_subset_string = (
        f'"{primary_key_name}" IN '
        f'(SELECT "mv_{session_name}"."{primary_key_name}" FROM "{schema}"."mv_{session_name}")'
    )
    logger.debug(f"[PostgreSQL] Layer subset string: {layer_subset_string}")
    queue_subset_fn(layer, layer_subset_string)
    
    elapsed = time.time() - start_time
    logger.info(
        f"Materialized view created in {elapsed:.2f}s. "
        "Filter queued for application on main thread."
    )
    
    return True


# =============================================================================
# Reset and Unfilter Actions
# =============================================================================

def execute_reset_action_postgresql(
    layer,
    name: str,
    cur,
    conn,
    # Callback functions
    queue_subset_fn: Callable,
    get_connection_fn: Callable,
    execute_commands_fn: Callable,
    get_session_name_fn: Callable,
    delete_history_fn: Callable = None,
    # Context parameters
    project_uuid: str = None,
    current_mv_schema: str = "filter_mate_temp"
) -> bool:
    """
    Execute reset action using PostgreSQL backend.
    
    Clears the filter on a layer and drops associated materialized views.
    
    Args:
        layer: QgsVectorLayer to reset
        name: Layer identifier
        cur: Database cursor
        conn: Database connection
        queue_subset_fn: Function to queue subset string
        get_connection_fn: Function to get PostgreSQL connection
        execute_commands_fn: Function to execute SQL commands
        get_session_name_fn: Function to get session-prefixed name
        delete_history_fn: Function to delete subset history
        project_uuid: Project UUID for history
        current_mv_schema: Schema for materialized views
            
    Returns:
        bool: True if successful
    """
    logger.info(f"[PostgreSQL] Reset Action - Layer: {layer.name()} ({layer.featureCount()} features) - Dropping materialized views")
    
    # Delete history using prepared statements if available, otherwise use repository
    if delete_history_fn:
        try:
            delete_history_fn(project_uuid, layer.id())
        except Exception as e:
            logger.warning(f"[PostgreSQL] History Delete Fallback - Layer: {layer.name()} - {type(e).__name__}: {str(e)}")
            # EPIC-1 E4-S9: Use centralized HistoryRepository
            history_repo = HistoryRepository(conn, cur)
            try:
                history_repo.delete_for_layer(project_uuid, layer.id())
            finally:
                history_repo.close()
    else:
        # EPIC-1 E4-S9: Use centralized HistoryRepository instead of direct SQL
        history_repo = HistoryRepository(conn, cur)
        try:
            history_repo.delete_for_layer(project_uuid, layer.id())
        finally:
            history_repo.close()
    
    # Drop materialized view
    schema = current_mv_schema
    session_name = get_session_name_fn(name)
    
    sql_drop = f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."mv_{session_name}" CASCADE;'
    sql_drop += f' DROP MATERIALIZED VIEW IF EXISTS "{schema}"."mv_{session_name}_dump" CASCADE;'
    sql_drop += f' DROP INDEX IF EXISTS {schema}_{session_name}_cluster CASCADE;'
    
    connexion = get_connection_fn()
    execute_commands_fn(connexion, [sql_drop])
    logger.debug(f"[PostgreSQL] Materialized View Dropped - Schema: {schema} - Session: {session_name}")
    
    # THREAD SAFETY: Queue subset clear for application in finished()
    queue_subset_fn(layer, '')
    logger.info(f"[PostgreSQL] Reset Complete - Layer: {layer.name()} - Filter cleared")
    return True


def execute_unfilter_action_postgresql(
    layer,
    primary_key_name: str,
    geom_key_name: str,
    name: str,
    cur,
    conn,
    last_subset_id: Optional[str],
    # Callback functions
    queue_subset_fn: Callable,
    get_connection_fn: Callable,
    execute_commands_fn: Callable,
    get_session_name_fn: Callable,
    create_simple_mv_fn: Callable,
    # Context parameters
    project_uuid: str = None,
    current_mv_schema: str = "filter_mate_temp"
) -> bool:
    """
    Execute unfilter action for PostgreSQL (restore previous filter state).
    
    Removes the most recent filter and restores the previous one from history.
    
    Args:
        layer: QgsVectorLayer to unfilter
        primary_key_name: Primary key field name
        geom_key_name: Geometry field name
        name: Layer identifier
        cur: Database cursor
        conn: Database connection
        last_subset_id: Last subset ID to remove
        queue_subset_fn: Function to queue subset string
        get_connection_fn: Function to get PostgreSQL connection
        execute_commands_fn: Function to execute SQL commands
        get_session_name_fn: Function to get session-prefixed name
        create_simple_mv_fn: Function to create simple MV SQL
        project_uuid: Project UUID for history
        current_mv_schema: Schema for materialized views
            
    Returns:
        bool: True if successful
    """
    logger.info(f"[PostgreSQL] Unfilter Action - Layer: {layer.name()} ({layer.featureCount()} features) - Restoring previous filter")
    
    # EPIC-1 E4-S9: Use centralized HistoryRepository instead of direct SQL
    history_repo = HistoryRepository(conn, cur)
    try:
        # Delete last subset from history
        if last_subset_id:
            history_repo.delete_entry(project_uuid, layer.id(), last_subset_id)
        
        # Get previous subset
        last_entry = history_repo.get_last_entry(project_uuid, layer.id())
    finally:
        history_repo.close()
    
    if last_entry:
        sql_subset_string = last_entry.subset_string
        
        # Validate sql_subset_string from history
        if not sql_subset_string or not sql_subset_string.strip():
            logger.warning(
                f"[PostgreSQL] Empty Previous Subset - Layer: {layer.name()} - "
                "History entry exists but subset string is empty. Clearing filter."
            )
            queue_subset_fn(layer, '')
            return True
        
        schema = current_mv_schema
        session_name = get_session_name_fn(name)
        
        sql_drop = (
            f'DROP INDEX IF EXISTS {schema}_{session_name}_cluster CASCADE; '
            f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."mv_{session_name}" CASCADE;'
        )
        sql_create = create_simple_mv_fn(schema, session_name, sql_subset_string)
        sql_create_index = (
            f'CREATE INDEX IF NOT EXISTS {schema}_{session_name}_cluster '
            f'ON "{schema}"."mv_{session_name}" USING GIST ({geom_key_name});'
        )
        sql_cluster = (
            f'ALTER MATERIALIZED VIEW IF EXISTS "{schema}"."mv_{session_name}" '
            f'CLUSTER ON {schema}_{session_name}_cluster;'
        )
        sql_analyze = f'ANALYZE VERBOSE "{schema}"."mv_{session_name}";'
        
        sql_create = sql_create.replace('\n', '').replace('\t', '').replace('  ', ' ').strip()
        
        connexion = get_connection_fn()
        execute_commands_fn(connexion, [sql_drop, sql_create, sql_create_index, sql_cluster, sql_analyze])
        logger.debug(f"[PostgreSQL] Materialized View Recreated - Schema: {schema} - Session: {session_name} - Previous filter restored")
        
        layer_subset_string = (
            f'"{primary_key_name}" IN '
            f'(SELECT "mv_{session_name}"."{primary_key_name}" FROM "{schema}"."mv_{session_name}")'
        )
        queue_subset_fn(layer, layer_subset_string)
        logger.info(f"[PostgreSQL] Unfilter Complete - Layer: {layer.name()} - Previous state restored")
    else:
        # No previous filter - clear
        queue_subset_fn(layer, '')
        logger.info(f"[PostgreSQL] No Previous Filter - Layer: {layer.name()} - Filter cleared")
    
    return True

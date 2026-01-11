"""
Spatialite Filter Executor

EPIC-1 Phase E4: Backend-specific filter execution for Spatialite.

This module will contain Spatialite-specific methods extracted from filter_task.py:
- prepare_spatialite_source_geom() - Prepare source geometry (629 lines - LARGEST METHOD!)
- qgis_expression_to_spatialite() - Convert QGIS expression to Spatialite SQL
- _build_spatialite_query() - Build complete Spatialite query
- _apply_spatialite_subset() - Apply subset to Spatialite layer
- _manage_spatialite_subset() - Manage Spatialite subset strings

TODO (EPIC-1 Phase E4): Extract methods from filter_task.py
This is a stub module for Phase E4 planning. Methods will be extracted
in a follow-up session due to complexity and dependencies.

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase E4 - stub)
"""

import logging

logger = logging.getLogger('FilterMate.Adapters.Backends.Spatialite.FilterExecutor')


# TODO: Extract from filter_task.py line 4178
def prepare_spatialite_source_geom(
    source_layer,
    buffer_value: float = None,
    buffer_expression: str = None,
    use_centroids: bool = False,
    **kwargs
) -> str:
    """
    Prepare Spatialite source geometry expression with optional buffer and centroid.
    
    TODO: Extract implementation from filter_task.py (629 lines - LARGEST METHOD!)
    
    This is the most complex method in filter_task.py. Handles:
    - Temporary table creation
    - R-tree spatial index management
    - Dynamic buffer expressions
    - Centroid calculations
    - Error handling and cleanup
    
    Args:
        source_layer: QGIS vector layer
        buffer_value: Static buffer value in meters (optional)
        buffer_expression: Dynamic buffer expression (optional)
        use_centroids: Whether to use Centroid()
        **kwargs: Additional parameters (table_name, geom_name, etc.)
        
    Returns:
        str: Spatialite geometry expression or table reference
    """
    raise NotImplementedError("EPIC-1 Phase E4: To be extracted from filter_task.py")


def qgis_expression_to_spatialite(expression: str, geom_col: str = 'geometry') -> str:
    """
    Convert QGIS expression to Spatialite SQL.
    
    EPIC-1 Phase E4-S1: Extracted from filter_task.py line 3526 (58 lines)
    
    Spatialite spatial functions are ~90% compatible with PostGIS, but differences:
    - Type casting: PostgreSQL uses :: operator, Spatialite uses CAST() function
    - String comparison is case-sensitive by default
    - No ILIKE operator (use LOWER() + LIKE instead)
    
    Args:
        expression: QGIS expression string
        geom_col: Geometry column name (default: 'geometry')
        
    Returns:
        str: Spatialite SQL expression
    """
    import re
    import logging
    
    logger = logging.getLogger('FilterMate.Adapters.Backends.Spatialite.FilterExecutor')
    
    if not expression:
        return expression
    
    # Handle CASE expressions
    expression = re.sub('case', ' CASE ', expression, flags=re.IGNORECASE)
    expression = re.sub('when', ' WHEN ', expression, flags=re.IGNORECASE)
    expression = re.sub(' is ', ' IS ', expression, flags=re.IGNORECASE)
    expression = re.sub('then', ' THEN ', expression, flags=re.IGNORECASE)
    expression = re.sub('else', ' ELSE ', expression, flags=re.IGNORECASE)
    
    # Handle LIKE/ILIKE - Spatialite doesn't have ILIKE, use LIKE with LOWER()
    # IMPORTANT: Process ILIKE first, before processing LIKE, to avoid double-replacement
    expression = re.sub(
        r'(\w+)\s+ILIKE\s+',
        r'LOWER(\1) LIKE LOWER(',
        expression,
        flags=re.IGNORECASE
    )
    expression = re.sub(r'\bNOT\b', ' NOT ', expression, flags=re.IGNORECASE)
    expression = re.sub(r'\bLIKE\b', ' LIKE ', expression, flags=re.IGNORECASE)
    
    # Convert PostgreSQL :: type casting to Spatialite CAST() function
    expression = re.sub(r'(["\w]+)::numeric', r'CAST(\1 AS REAL)', expression)
    expression = re.sub(r'(["\w]+)::integer', r'CAST(\1 AS INTEGER)', expression)
    expression = re.sub(r'(["\w]+)::text', r'CAST(\1 AS TEXT)', expression)
    expression = re.sub(r'(["\w]+)::double', r'CAST(\1 AS REAL)', expression)
    
    return expression


def build_spatialite_query(
    sql_subset_string: str,
    table_name: str,
    geom_key_name: str,
    primary_key_name: str,
    custom: bool,
    buffer_expression: str = None,
    buffer_value: float = None,
    buffer_segments: int = 5,
    buffer_type: str = "Round",
    task_parameters: dict = None
) -> str:
    """
    Build Spatialite query for simple or complex (buffered) subsets.
    
    EPIC-1 Phase E4-S2: Extracted from filter_task.py line 10616 (64 lines)
    
    Args:
        sql_subset_string: SQL query for subset
        table_name: Source table name
        geom_key_name: Geometry field name
        primary_key_name: Primary key field name
        custom: Whether custom buffer expression is used
        buffer_expression: QGIS expression for dynamic buffer
        buffer_value: Static buffer value in meters
        buffer_segments: Number of segments for round buffers
        buffer_type: Buffer type ('Round', 'Flat', 'Square')
        task_parameters: Task parameters dict
        
    Returns:
        str: Spatialite SELECT query
    """
    if custom is False:
        # Simple subset - use query as-is
        return sql_subset_string
    
    # Complex subset with buffer (adapt from PostgreSQL logic)
    buffer_expr = (
        qgis_expression_to_spatialite(buffer_expression)
        if buffer_expression
        else str(buffer_value)
    )
    
    # Build ST_Buffer style parameters (quad_segs for segments, endcap for type)
    buffer_type_mapping = {
        "Round": "round",
        "Flat": "flat",
        "Square": "square"
    }
    buffer_type_str = (
        task_parameters.get("filtering", {}).get("buffer_type", "Round")
        if task_parameters
        else buffer_type
    )
    endcap_style = buffer_type_mapping.get(buffer_type_str, "round")
    quad_segs = buffer_segments
    
    # Build style string for Spatialite ST_Buffer
    style_params = f"quad_segs={quad_segs}"
    if endcap_style != 'round':
        style_params += f" endcap={endcap_style}"
    
    # Build Spatialite SELECT (similar to PostgreSQL CREATE MATERIALIZED VIEW)
    # Note: Spatialite uses same ST_Buffer syntax as PostGIS
    query = f"""
        SELECT 
            ST_Buffer({geom_key_name}, {buffer_expr}, '{style_params}') as {geom_key_name},
            {primary_key_name},
            {buffer_expr} as buffer_value
        FROM {table_name}
        WHERE {primary_key_name} IN ({sql_subset_string})
    """
    
    return query


def apply_spatialite_subset(
    layer,
    name: str,
    primary_key_name: str,
    sql_subset_string: str,
    cur=None,
    conn=None,
    current_seq_order: int = 0,
    session_id: str = None,
    project_uuid: str = None,
    source_layer_id: str = None,
    queue_subset_func=None
) -> bool:
    """
    Apply subset string to layer and update history.
    
    EPIC-1 Phase E4-S4: Extracted from filter_task.py line 10591 (44 lines)
    
    Args:
        layer: QGIS vector layer
        name: Temp table name
        primary_key_name: Primary key field name
        sql_subset_string: Original SQL subset string for history
        cur: Spatialite cursor for history
        conn: Spatialite connection for history
        current_seq_order: Sequence order for history
        session_id: Session ID for multi-client isolation
        project_uuid: Project UUID for history
        source_layer_id: Source layer ID for history
        queue_subset_func: Function to queue subset string for main thread
        
    Returns:
        bool: True if successful
    """
    import uuid
    
    # Build session-prefixed name for multi-client isolation
    session_name = f"{session_id}_{name}" if session_id else name
    
    # Apply subset string to layer (reference temp table)
    layer_subsetString = (
        f'"{primary_key_name}" IN '
        f'(SELECT "{primary_key_name}" FROM mv_{session_name})'
    )
    logger.debug(f"Applying Spatialite subset string: {layer_subsetString}")
    
    # THREAD SAFETY: Queue subset string for application in finished()
    if queue_subset_func:
        queue_subset_func(layer, layer_subsetString)
    
    # Update history
    if cur and conn and project_uuid:
        try:
            cur.execute(
                """INSERT INTO fm_subset_history 
                   VALUES('{id}', datetime(), '{fk_project}', '{layer_id}', 
                          '{layer_source_id}', {seq_order}, '{subset_string}');""".format(
                    id=uuid.uuid4(),
                    fk_project=project_uuid,
                    layer_id=layer.id(),
                    layer_source_id=source_layer_id or '',
                    seq_order=current_seq_order,
                    subset_string=sql_subset_string.replace("'", "''")
                )
            )
            conn.commit()
        except Exception as e:
            logger.warning(f"Failed to update Spatialite history: {e}")
    
    return True


def manage_spatialite_subset(
    layer,
    sql_subset_string: str,
    primary_key_name: str,
    geom_key_name: str,
    name: str,
    custom: bool = False,
    cur=None,
    conn=None,
    current_seq_order: int = 0,
    session_id: str = None,
    project_uuid: str = None,
    source_layer_id: str = None,
    queue_subset_func=None,
    get_spatialite_datasource_func=None,
    task_parameters: dict = None
) -> bool:
    """
    Handle Spatialite temporary tables for filtering.
    
    EPIC-1 Phase E4-S4: Extracted from filter_task.py line 10635 (66 lines)
    
    Alternative to PostgreSQL materialized views using create_temp_spatialite_table().
    
    Args:
        layer: QGIS vector layer
        sql_subset_string: SQL query for subset
        primary_key_name: Primary key field name
        geom_key_name: Geometry field name
        name: Unique name for temp table
        custom: Whether custom buffer expression is used
        cur: Spatialite cursor for history
        conn: Spatialite connection for history
        current_seq_order: Sequence order for history
        session_id: Session ID for multi-client isolation
        project_uuid: Project UUID for history
        source_layer_id: Source layer ID for history
        queue_subset_func: Function to queue subset string for main thread
        get_spatialite_datasource_func: Function to get datasource info
        task_parameters: Task parameters dict for buffer options
        
    Returns:
        bool: True if successful
    """
    try:
        from modules.appUtils import create_temp_spatialite_table
    except ImportError:
        logger.error("create_temp_spatialite_table not available")
        return False
    
    # Get datasource information
    if get_spatialite_datasource_func:
        db_path, table_name, layer_srid, is_native_spatialite = (
            get_spatialite_datasource_func(layer)
        )
    else:
        # Fallback: assume it's a native Spatialite layer
        db_path = layer.source().split('|')[0]
        table_name = layer.source().split('table=')[1].split(' ')[0] if 'table=' in layer.source() else layer.name()
        layer_srid = layer.crs().authid().split(':')[1] if layer.crs().authid() else '4326'
        is_native_spatialite = True
    
    # For non-Spatialite layers, use QGIS subset string directly
    if not is_native_spatialite:
        if queue_subset_func:
            queue_subset_func(layer, sql_subset_string)
        return True
    
    # Build Spatialite query (simple or buffered)
    spatialite_query = build_spatialite_query(
        sql_subset_string=sql_subset_string,
        table_name=table_name,
        geom_key_name=geom_key_name,
        primary_key_name=primary_key_name,
        custom=custom,
        task_parameters=task_parameters
    )
    
    # Create temporary table with session-prefixed name
    session_name = f"{session_id}_{name}" if session_id else name
    logger.info(
        f"Creating Spatialite temp table 'mv_{session_name}' "
        f"(session: {session_id})"
    )
    
    success = create_temp_spatialite_table(
        db_path=db_path,
        table_name=session_name,
        sql_query=spatialite_query,
        geom_field=geom_key_name,
        srid=layer_srid
    )
    
    if not success:
        logger.error("Failed to create Spatialite temp table")
        return False
    
    # Apply subset and update history
    return apply_spatialite_subset(
        layer=layer,
        name=name,
        primary_key_name=primary_key_name,
        sql_subset_string=sql_subset_string,
        cur=cur,
        conn=conn,
        current_seq_order=current_seq_order,
        session_id=session_id,
        project_uuid=project_uuid,
        source_layer_id=source_layer_id,
        queue_subset_func=queue_subset_func
    )


def get_last_subset_info(cur, layer, project_uuid: str) -> tuple:
    """
    Get the last subset information for a layer from history.
    
    EPIC-1 Phase E4-S4: Extracted from filter_task.py line 10703 (28 lines)
    
    Args:
        cur: Database cursor
        layer: QgsVectorLayer
        project_uuid: Project UUID
        
    Returns:
        tuple: (last_subset_id, last_seq_order, layer_name, sanitized_name)
    """
    from modules.appUtils import sanitize_sql_identifier
    
    layer_name = layer.name()
    # Use sanitize_sql_identifier to handle all special chars (em-dash, etc.)
    name = sanitize_sql_identifier(layer.id().replace(layer_name, ''))
    
    try:
        cur.execute(
            """SELECT * FROM fm_subset_history 
               WHERE fk_project = '{fk_project}' AND layer_id = '{layer_id}' 
               ORDER BY seq_order DESC LIMIT 1;""".format(
                fk_project=project_uuid,
                layer_id=layer.id()
            )
        )
        
        results = cur.fetchall()
        if len(results) == 1:
            result = results[0]
            return result[0], result[5], layer_name, name
        else:
            return None, 0, layer_name, name
    except Exception as e:
        logger.warning(f"Failed to get last subset info: {e}")
        return None, 0, layer_name, name


def cleanup_session_temp_tables(
    db_path: str,
    session_id: str
) -> int:
    """
    Clean up all temporary tables for a specific session.
    
    EPIC-1 Phase E4-S4: New function for session cleanup
    
    Drops all temporary tables and indexes prefixed with the session_id.
    Should be called when closing the plugin or resetting.
    
    Args:
        db_path: Path to Spatialite database
        session_id: Session identifier prefix
        
    Returns:
        int: Number of tables cleaned up
    """
    import sqlite3
    
    if not session_id or not db_path:
        return 0
    
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Find all temp tables for this session
        cur.execute(
            """SELECT name FROM sqlite_master 
               WHERE type='table' AND name LIKE ?""",
            (f"mv_{session_id}_%",)
        )
        tables = cur.fetchall()
        
        count = 0
        for (table_name,) in tables:
            try:
                # Drop the table
                cur.execute(f'DROP TABLE IF EXISTS "{table_name}";')
                # Drop associated R-tree index
                cur.execute(f'DROP TABLE IF EXISTS "idx_{table_name}_geometry";')
                count += 1
            except Exception as e:
                logger.warning(f"Error dropping temp table {table_name}: {e}")
        
        conn.commit()
        conn.close()
        
        if count > 0:
            logger.info(
                f"Cleaned up {count} Spatialite temp table(s) "
                f"for session {session_id}"
            )
        return count
        
    except Exception as e:
        logger.error(f"Error cleaning up session tables: {e}")
        return 0


def normalize_column_names_for_spatialite(
    expression: str,
    field_names: list
) -> str:
    """
    Normalize column names in expression for Spatialite.
    
    EPIC-1 Phase E4-S4: Spatialite equivalent of PostgreSQL function
    
    Spatialite is case-insensitive for column names by default,
    but we still need to ensure proper quoting.
    
    Args:
        expression: SQL expression string
        field_names: List of actual field names from the layer
        
    Returns:
        str: Expression with properly quoted column names
    """
    import re
    
    if not expression or not field_names:
        return expression
    
    result_expression = expression
    
    # Find all unquoted column references that match field names
    for field_name in field_names:
        # Pattern: word boundary + field name + word boundary (not already quoted)
        pattern = r'(?<!")\b' + re.escape(field_name) + r'\b(?!")'
        replacement = f'"{field_name}"'
        result_expression = re.sub(pattern, replacement, result_expression)
    
    return result_expression

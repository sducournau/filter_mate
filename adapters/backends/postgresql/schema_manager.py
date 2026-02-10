# -*- coding: utf-8 -*-
"""
FilterMate PostgreSQL Schema Manager

Manages PostgreSQL schema operations with robust fallback strategies.
Extracted from filter_task.py as part of Phase E7.5.

Features:
- Schema creation with multiple authorization fallbacks
- Schema existence validation
- Connection validation before operations
- Graceful degradation to 'public' schema

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional, Tuple

logger = logging.getLogger('FilterMate.PostgreSQL.SchemaManager')


def ensure_temp_schema_exists(connexion, schema_name: str) -> str:
    """
    Ensure the temporary schema exists in PostgreSQL database.

    Creates the schema if it doesn't exist. This is required before
    creating materialized views in the schema.

    v2.8.8: Now returns the actual schema to use. If the requested schema cannot be
    created (permission issues), falls back to 'public' schema.

    Args:
        connexion: psycopg2 connection object
        schema_name: Name of the schema to create

    Returns:
        str: Name of the schema to use (schema_name if created, 'public' as fallback)

    Raises:
        Exception: If connection is invalid (None, string, or closed)
    """
    # Validate connection before use
    if connexion is None:
        logger.error("[PostgreSQL] Cannot ensure temp schema: connection is None")
        raise Exception(f"Cannot create schema '{schema_name}': PostgreSQL connection is None")

    # Check if connexion is a string (connection string) instead of a connection object
    if isinstance(connexion, str):
        logger.error(f"[PostgreSQL] Cannot ensure temp schema: connexion is a string ('{connexion[:50]}...'), not a connection object")
        raise Exception(f"Cannot create schema '{schema_name}': PostgreSQL connexion is a string, not a connection object. This indicates ACTIVE_POSTGRESQL was not properly initialized.")

    # Check if connection has cursor method (duck typing validation)
    if not hasattr(connexion, 'cursor') or not callable(getattr(connexion, 'cursor', None)):
        logger.error(f"[PostgreSQL] Cannot ensure temp schema: connexion object has no cursor() method (type: {type(connexion).__name__})")
        raise Exception(f"Cannot create schema '{schema_name}': PostgreSQL connexion is not a valid connection object (type: {type(connexion).__name__})")

    # Check if connection is closed
    try:
        if connexion.closed:
            logger.error("[PostgreSQL] Cannot ensure temp schema: connection is closed")
            raise Exception(f"Cannot create schema '{schema_name}': PostgreSQL connection is closed")
    except AttributeError:
        # Connection object doesn't have 'closed' attribute - proceed anyway
        pass

    # First check if schema already exists
    try:
        with connexion.cursor() as cursor:
            cursor.execute("""
                SELECT schema_name FROM information_schema.schemata
                WHERE schema_name = %s
            """, (schema_name,))
            result = cursor.fetchone()
            if result:
                logger.debug(f"[PostgreSQL] Schema '{schema_name}' already exists")
                return schema_name
    except Exception as check_e:
        logger.debug(f"[PostgreSQL] Could not check if schema exists: {check_e}")
        # Continue to try creating it

    # Try creating schema without explicit authorization (uses current user)
    try:
        with connexion.cursor() as cursor:
            cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}";')
            connexion.commit()
        logger.debug(f"[PostgreSQL] Ensured schema '{schema_name}' exists")
        return schema_name
    except Exception as e:
        logger.warning(f"[PostgreSQL] Error creating schema '{schema_name}' (no auth): {e}")
        # Rollback failed transaction
        try:
            connexion.rollback()
        except Exception:
            pass  # Connection may be in bad state

        # Try with explicit AUTHORIZATION CURRENT_USER as fallback
        try:
            with connexion.cursor() as cursor:
                cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}" AUTHORIZATION CURRENT_USER;')
                connexion.commit()
            logger.debug(f"[PostgreSQL] Created schema '{schema_name}' with CURRENT_USER authorization")
            return schema_name
        except Exception as e2:
            logger.warning(f"[PostgreSQL] Error creating schema with CURRENT_USER: {e2}")
            try:
                connexion.rollback()
            except Exception:
                pass  # Connection may be in bad state

            # Final fallback: try with postgres authorization
            try:
                with connexion.cursor() as cursor:
                    cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}" AUTHORIZATION postgres;')
                    connexion.commit()
                logger.debug(f"[PostgreSQL] Created schema '{schema_name}' with postgres authorization")
                return schema_name
            except Exception as e3:
                try:
                    connexion.rollback()
                except Exception:
                    pass  # Connection may be in bad state

                # v2.8.8: Fallback to 'public' schema if temp schema cannot be created
                logger.warning(f"Cannot create schema '{schema_name}', falling back to 'public'. "
                               f"Errors: no auth: {e}, CURRENT_USER: {e2}, postgres: {e3}")
                return 'public'


def validate_connection(connexion) -> Tuple[bool, Optional[str]]:
    """
    Validate a PostgreSQL connection object.

    Args:
        connexion: Object to validate as a psycopg2 connection

    Returns:
        Tuple of (is_valid, error_message)
    """
    if connexion is None:
        return False, "Connection is None"

    if isinstance(connexion, str):
        return False, "Connection is a string, not a connection object"

    if not hasattr(connexion, 'cursor') or not callable(getattr(connexion, 'cursor', None)):
        return False, f"Object has no cursor() method (type: {type(connexion).__name__})"

    try:
        if connexion.closed:
            return False, "Connection is closed"
    except AttributeError:
        pass  # No 'closed' attribute, proceed

    return True, None


def schema_exists(connexion, schema_name: str) -> bool:
    """
    Check if a schema exists in the database.

    Args:
        connexion: psycopg2 connection
        schema_name: Name of the schema to check

    Returns:
        bool: True if schema exists, False otherwise
    """
    try:
        with connexion.cursor() as cursor:
            cursor.execute("""
                SELECT schema_name FROM information_schema.schemata
                WHERE schema_name = %s
            """, (schema_name,))
            result = cursor.fetchone()
            return result is not None
    except Exception as e:
        logger.debug(f"[PostgreSQL] Could not check if schema '{schema_name}' exists: {e}")
        return False


def ensure_table_stats(connexion, schema: str, table: str, geom_field: str) -> bool:
    """
    Ensure PostgreSQL statistics exist for source table geometry column.

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
                logger.info(f"Running ANALYZE on source table \"{schema}\".\"{table}\" (missing stats for {geom_field})")
                cursor.execute(f'ANALYZE "{schema}"."{table}";')
                connexion.commit()
                logger.debug(f"ANALYZE completed for \"{schema}\".\"{table}\"")

            return True

    except Exception as e:
        logger.warning(f"Could not check/create stats for \"{schema}\".\"{table}\": {e}")
        return False


def execute_commands(connexion, commands: list) -> bool:
    """
    Execute PostgreSQL commands with transaction handling.

    Args:
        connexion: psycopg2 connection
        commands: List of SQL commands to execute

    Returns:
        bool: True if all commands succeeded
    """
    try:
        with connexion.cursor() as cursor:
            for command in commands:
                cursor.execute(command)
                connexion.commit()
        return True
    except Exception as e:
        logger.error(f"[PostgreSQL] Error executing PostgreSQL commands: {e}")
        try:
            connexion.rollback()
        except Exception:
            pass
        return False


def cleanup_orphaned_materialized_views(connexion, schema_name: str, current_session_id: str = None, max_age_hours: int = 24) -> int:
    """
    Clean up orphaned materialized views older than max_age_hours.

    v4.4.4: Handles both fm_temp_mv_ (new) and mv_ (legacy) prefixes.

    This is a maintenance function to clean up views from crashed sessions
    or sessions that didn't clean up properly.

    Args:
        connexion: psycopg2 connection
        schema_name: Schema containing the materialized views
        current_session_id: Current session ID to skip (don't clean own views)
        max_age_hours: Maximum age in hours before a view is considered orphaned

    Returns:
        int: Number of views cleaned up
    """
    try:
        with connexion.cursor() as cursor:
            # Find all FilterMate materialized views (both new and legacy prefixes)
            cursor.execute("""
                SELECT matviewname FROM pg_matviews
                WHERE schemaname = %s
                AND (matviewname LIKE 'fm\\_temp\\_mv\\_%' OR matviewname LIKE 'mv\\_%')
            """, (schema_name,))
            views = cursor.fetchall()

            count = 0
            for (view_name,) in views:
                try:
                    # Extract session ID based on prefix
                    # New format: fm_temp_mv_<session_id>_<layer_id>
                    # Legacy format: mv_<session_id>_<layer_id>
                    if view_name.startswith('fm_temp_mv_'):
                        parts = view_name[11:].split('_', 1)  # Remove 'fm_temp_mv_' prefix
                    else:
                        parts = view_name[3:].split('_', 1)  # Remove 'mv_' prefix (legacy)

                    if len(parts) >= 2 and len(parts[0]) == 8:
                        # This looks like a session-prefixed view
                        if current_session_id and parts[0] == current_session_id:
                            continue  # Skip our own session's views

                    # For non-session views or very old ones, we could drop them
                    # But to be safe, we only log here
                    logger.debug(f"[PostgreSQL] Found potentially orphaned view: {view_name}")
                except Exception as e:
                    logger.debug(f"[PostgreSQL] Error processing view {view_name}: {e}")

            return count
    except Exception as e:
        logger.error(f"[PostgreSQL] Error checking orphaned views: {e}")
        return 0


def cleanup_session_materialized_views(connexion, schema_name: str, session_id: str) -> int:
    """
    Clean up all materialized views for a specific session.

    v4.4.4: Uses unified fm_temp_mv_ prefix with legacy mv_ fallback.

    Args:
        connexion: psycopg2 connection
        schema_name: Schema containing the materialized views
        session_id: Session ID prefix for views to clean up

    Returns:
        int: Number of views cleaned up
    """
    if not session_id:
        return 0

    try:
        with connexion.cursor() as cursor:
            # Find views with both new (fm_temp_mv_) and legacy (mv_) prefixes
            cursor.execute("""
                SELECT matviewname FROM pg_matviews
                WHERE schemaname = %s
                AND (matviewname LIKE %s OR matviewname LIKE %s)
            """, (schema_name, f"fm_temp_mv_{session_id}_%", f"mv_{session_id}_%"))
            views = cursor.fetchall()

            count = 0
            for (view_name,) in views:
                try:
                    cursor.execute(f'DROP MATERIALIZED VIEW IF EXISTS "{schema_name}"."{view_name}" CASCADE;')
                    count += 1
                except Exception as e:
                    logger.warning(f"[PostgreSQL] Error dropping view {view_name}: {e}")

            connexion.commit()
            return count
    except Exception as e:
        logger.error(f"[PostgreSQL] Error cleaning up session views: {e}")
        return 0


def get_session_prefixed_name(base_name: str, session_id: str = None) -> str:
    """
    Generate a session-unique materialized view name.

    Prefixes the base name with the session_id to ensure different
    QGIS clients don't conflict when using the same PostgreSQL database.

    Args:
        base_name: Original layer-based name
        session_id: Session identifier (8-char hex string)

    Returns:
        str: Session-prefixed name (e.g., "a1b2c3d4_layername")
    """
    if session_id:
        return f"{session_id}_{base_name}"
    return base_name


def create_simple_materialized_view_sql(schema: str, name: str, sql_subset_string: str) -> str:
    """
    Create SQL for simple materialized view (non-custom buffer).

    v4.4.4: Uses unified fm_temp_mv_ prefix.

    Args:
        schema: PostgreSQL schema name
        name: Layer identifier
        sql_subset_string: SQL SELECT statement

    Returns:
        str: SQL CREATE MATERIALIZED VIEW statement

    Raises:
        ValueError: If sql_subset_string is empty or None
    """
    # CRITICAL FIX: Validate sql_subset_string is not empty
    # Empty sql_subset_string causes SQL syntax error: "AS WITH DATA;" without SELECT
    if not sql_subset_string or not sql_subset_string.strip():
        raise ValueError(
            f"Cannot create materialized view 'fm_temp_mv_{name}': sql_subset_string is empty. "
            "This usually means the filter expression was not properly built."
        )

    return 'CREATE MATERIALIZED VIEW IF NOT EXISTS "{schema}"."fm_temp_mv_{name}" TABLESPACE pg_default AS {sql_subset_string} WITH DATA;'.format(
        schema=schema,
        name=name,
        sql_subset_string=sql_subset_string
    )


def parse_case_to_where_clauses(case_expression: str) -> list:
    """
    Parse CASE statement into WHERE clause array.

    Args:
        case_expression: CASE statement string

    Returns:
        list: List of WHERE clause strings extracted from WHEN clauses
    """
    where_clause = case_expression.replace('CASE', '').replace('END', '').replace('IF', '').replace('ELSE', '').replace('\r', ' ').replace('\n', ' ')
    where_clauses_in_arr = where_clause.split('WHEN')

    where_clause_out_arr = []
    for where_then_clause in where_clauses_in_arr:
        if len(where_then_clause.split('THEN')) >= 1:
            clause = where_then_clause.split('THEN')[0].replace('WHEN', ' ').strip()
            if clause:
                where_clause_out_arr.append(clause)

    return where_clause_out_arr

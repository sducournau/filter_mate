"""
PostgreSQL Materialized View Cleanup Handler

Handles all cleanup operations for PostgreSQL materialized views (MVs) and
temporary schema management. Extracted from FilterEngineTask as part of the
C1 God Object decomposition (Phase 3).

This handler manages:
- Session-based MV cleanup
- Orphaned MV cleanup
- Schema creation and management
- MV SQL generation (simple and custom buffer views)
- PostgreSQL command execution with reconnection

Location: core/tasks/cleanup_handler.py (Hexagonal Architecture - Application Layer)

Thread Safety:
    All methods are safe to call from worker threads as they only interact
    with PostgreSQL connections (not QGIS layer objects directly).
"""

import logging
import os
from typing import Any, Dict, List, Optional, Set

from ...infrastructure.logging import setup_logger
from ...config.config import ENV_VARS

# Setup logger
logger = setup_logger(
    'FilterMate.Tasks.Cleanup',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_tasks.log'),
    level=logging.INFO
)

# Lazy-load backend services
from ..ports.backend_services import get_backend_services


class CleanupHandler:
    """Handles PostgreSQL materialized view cleanup and schema management.

    This class encapsulates all MV lifecycle operations previously embedded
    in FilterEngineTask. It receives dependencies explicitly via method
    parameters rather than accessing task state directly.

    Attributes:
        _backend_services: Backend services facade for PostgreSQL operations.

    Example:
        >>> handler = CleanupHandler()
        >>> handler.cleanup_session_mvs(connexion, 'filtermate_temp', session_id)
    """

    def __init__(self):
        """Initialize CleanupHandler with backend services facade."""
        self._backend_services = get_backend_services()

    def cleanup_postgresql_materialized_views(
        self,
        postgresql_available: bool,
        source_provider_type: str,
        source_layer: Any,
        task_parameters: Dict[str, Any],
        param_all_layers: Optional[List[Any]],
        get_connection_fn,
        current_mv_schema: str = 'filtermate_temp',
    ) -> None:
        """Cleanup PostgreSQL materialized views created during filtering.

        Uses the MV reference tracker to prevent premature cleanup when
        MVs are shared across multiple layers.

        Args:
            postgresql_available: Whether PostgreSQL is available
            source_provider_type: Provider type of source layer ('postgresql', etc.)
            source_layer: Source QgsVectorLayer (or None)
            task_parameters: Task configuration dict
            param_all_layers: List of all layers being filtered
            get_connection_fn: Callable returning a valid psycopg2 connection
            current_mv_schema: Schema name for temporary MVs
        """
        if not postgresql_available:
            return

        try:
            if source_provider_type != 'postgresql':
                return

            # Import reference tracker
            from ...adapters.backends.postgresql.mv_reference_tracker import get_mv_reference_tracker

            # Collect layer IDs
            layer_ids = []

            if source_layer:
                layer_ids.append(source_layer.id())
            elif 'source_layer' in task_parameters:
                sl = task_parameters['source_layer']
                if sl:
                    layer_ids.append(sl.id())

            if param_all_layers:
                for layer in param_all_layers:
                    if layer and hasattr(layer, 'id'):
                        layer_ids.append(layer.id())

            if not layer_ids:
                logger.debug("No layer IDs available for PostgreSQL MV cleanup")
                return

            # Remove references and find droppable MVs
            tracker = get_mv_reference_tracker()
            mvs_to_drop: Set[str] = set()

            for layer_id in layer_ids:
                can_drop = tracker.remove_all_references_for_layer(layer_id)
                mvs_to_drop.update(can_drop)

            if not mvs_to_drop:
                logger.debug(
                    "PostgreSQL MV cleanup: All MVs still referenced by other layers "
                    f"(removed references for {len(layer_ids)} layer(s))"
                )
                return

            logger.info(
                f"PostgreSQL MV cleanup: Dropping {len(mvs_to_drop)} MV(s) "
                "with no remaining references"
            )

            connexion = get_connection_fn()
            if not connexion:
                logger.warning("No PostgreSQL connection for MV cleanup")
                return

            cursor = connexion.cursor()
            schema = current_mv_schema

            for mv_name in mvs_to_drop:
                try:
                    if '.' in mv_name:
                        mv_name = mv_name.split('.')[-1].strip('"')
                    drop_sql = f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."{mv_name}" CASCADE;'
                    cursor.execute(drop_sql)
                    logger.debug(f"Dropped MV: {schema}.{mv_name}")
                except (RuntimeError, OSError, AttributeError) as e:
                    logger.warning(f"Failed to drop MV {mv_name}: {e}")

            connexion.commit()
            logger.debug(f"PostgreSQL MV cleanup completed: dropped {len(mvs_to_drop)} MV(s)")

        except Exception as e:  # catch-all safety net: MV cleanup must not crash the task
            logger.debug(f"Error during PostgreSQL MV cleanup: {e}")

    def cleanup_session_materialized_views(
        self,
        connexion: Any,
        schema_name: str,
        session_id: str,
        pg_executor: Any = None,
        pg_executor_available: bool = False,
    ) -> Any:
        """Clean up all materialized views for the current session.

        Args:
            connexion: psycopg2 connection
            schema_name: PostgreSQL schema name
            session_id: Unique session identifier
            pg_executor: PostgreSQL executor instance (optional)
            pg_executor_available: Whether pg_executor is available

        Returns:
            Result from the cleanup operation
        """
        if pg_executor_available and pg_executor:
            return pg_executor.cleanup_session_materialized_views(
                connexion, schema_name, session_id
            )
        return self._backend_services.cleanup_session_materialized_views(
            connexion, schema_name, session_id
        )

    def cleanup_orphaned_materialized_views(
        self,
        connexion: Any,
        schema_name: str,
        session_id: str,
        max_age_hours: int = 24,
    ) -> Any:
        """Clean up orphaned materialized views older than max_age_hours.

        Args:
            connexion: psycopg2 connection
            schema_name: PostgreSQL schema name
            session_id: Unique session identifier
            max_age_hours: Maximum age in hours before cleanup

        Returns:
            Result from the cleanup operation
        """
        return self._backend_services.cleanup_orphaned_materialized_views(
            connexion, schema_name, session_id, max_age_hours
        )

    def ensure_temp_schema_exists(
        self,
        connexion: Any,
        schema_name: str,
    ) -> str:
        """Ensure the temporary schema exists in PostgreSQL database.

        Args:
            connexion: psycopg2 connection
            schema_name: Name of the schema to create

        Returns:
            str: Name of the schema to use (schema_name if created, 'public' as fallback)
        """
        return self._backend_services.ensure_temp_schema_exists(connexion, schema_name)

    def get_session_prefixed_name(self, base_name: str, session_id: str) -> str:
        """Generate a session-unique materialized view name.

        Args:
            base_name: Base name for the MV
            session_id: Unique session identifier

        Returns:
            str: Session-prefixed name
        """
        return self._backend_services.get_session_prefixed_name(base_name, session_id)

    def execute_postgresql_commands(
        self,
        connexion: Any,
        commands: List[str],
        source_layer: Any = None,
        psycopg2_module: Any = None,
        get_datasource_connexion_fn: Any = None,
    ) -> bool:
        """Execute PostgreSQL commands with automatic reconnection on failure.

        Args:
            connexion: psycopg2 connection
            commands: List of SQL commands to execute
            source_layer: Source layer for reconnection (optional)
            psycopg2_module: psycopg2 module for exception types
            get_datasource_connexion_fn: Function to get new connection from layer

        Returns:
            bool: True if all commands succeeded
        """
        # Test connection and reconnect if needed
        if psycopg2_module and source_layer and get_datasource_connexion_fn:
            try:
                with connexion.cursor() as cursor:
                    cursor.execute("SELECT 1")
            except (psycopg2_module.OperationalError, psycopg2_module.InterfaceError, AttributeError) as e:
                logger.debug(f"PostgreSQL connection test failed, reconnecting: {e}")
                connexion, _ = get_datasource_connexion_fn(source_layer)

        return self._backend_services.execute_commands(connexion, commands)

    def ensure_source_table_stats(
        self,
        connexion: Any,
        schema: str,
        table: str,
        geom_field: str,
    ) -> bool:
        """Ensure PostgreSQL statistics exist for source table geometry column.

        Args:
            connexion: psycopg2 connection
            schema: Schema name
            table: Table name
            geom_field: Geometry column name

        Returns:
            bool: True if stats were verified/created
        """
        return self._backend_services.ensure_table_stats(connexion, schema, table, geom_field)

    def create_simple_materialized_view_sql(
        self,
        schema: str,
        name: str,
        sql_subset_string: str,
    ) -> str:
        """Create SQL for a simple materialized view.

        Args:
            schema: PostgreSQL schema name
            name: MV identifier
            sql_subset_string: SQL SELECT statement

        Returns:
            str: SQL CREATE MATERIALIZED VIEW statement
        """
        return self._backend_services.create_simple_materialized_view_sql(
            schema, name, sql_subset_string
        )

    def parse_where_clauses(self, where_clause: Any) -> Any:
        """Parse CASE expression into WHERE clauses.

        Args:
            where_clause: WHERE clause to parse

        Returns:
            Parsed WHERE clauses
        """
        return self._backend_services.parse_case_to_where_clauses(where_clause)

    def create_custom_buffer_view_sql(
        self,
        schema: str,
        name: str,
        geom_key_name: str,
        where_clause_fields_arr: List[str],
        last_subset_id: Optional[str],
        sql_subset_string: str,
        postgresql_source_geom: str,
        has_to_reproject_source_layer: bool,
        source_layer_crs_authid: str,
        task_parameters: Dict[str, Any],
        param_buffer_segments: int,
        param_source_schema: str,
        param_source_table: str,
        primary_key_name: str,
        source_layer: Any,
        param_buffer: str,
        where_clause: Any,
    ) -> str:
        """Create SQL for custom buffer materialized view.

        Args:
            schema: PostgreSQL schema name
            name: Layer identifier
            geom_key_name: Geometry field name
            where_clause_fields_arr: List of WHERE clause fields
            last_subset_id: Previous subset ID (None if first)
            sql_subset_string: SQL SELECT statement for source
            postgresql_source_geom: PostGIS source geometry expression
            has_to_reproject_source_layer: Whether reprojection is needed
            source_layer_crs_authid: Source layer CRS auth ID
            task_parameters: Task configuration parameters
            param_buffer_segments: Number of buffer segments
            param_source_schema: Source schema name
            param_source_table: Source table name
            primary_key_name: Primary key field name
            source_layer: Source QgsVectorLayer
            param_buffer: Buffer expression string
            where_clause: WHERE clause for parsing

        Returns:
            str: SQL CREATE MATERIALIZED VIEW statement
        """
        # Apply reprojection if needed
        pg_source_geom = postgresql_source_geom
        if has_to_reproject_source_layer:
            pg_source_geom = f'ST_Transform({pg_source_geom}, {source_layer_crs_authid.split(":")[1]})'

        # Build ST_Buffer style parameters
        buffer_type_mapping = {"Round": "round", "Flat": "flat", "Square": "square"}
        buffer_type_str = task_parameters["filtering"].get("buffer_type", "Round")
        endcap_style = buffer_type_mapping.get(buffer_type_str, "round")
        quad_segs = param_buffer_segments

        style_params = f"quad_segs={quad_segs}"
        if endcap_style != 'round':
            style_params += f" endcap={endcap_style}"

        # Determine source filter for MV
        source_filter_for_mv = sql_subset_string
        if source_layer and source_layer.subsetString():
            source_subset = source_layer.subsetString()
            logger.info("Buffer MV: Using source layer subset for filtering")
            logger.info(f"   Source subset preview: {source_subset[:200]}...")

            if 'SELECT' in source_subset.upper():
                source_filter_for_mv = source_subset
                logger.info("   Using source layer SELECT statement for buffer MV")
            else:
                source_filter_for_mv = (
                    f'(SELECT "{param_source_table}"."{primary_key_name}" '  # nosec B608
                    f'FROM "{param_source_schema}"."{param_source_table}" '
                    f'WHERE {source_subset})'
                )
                logger.info("   Wrapped source WHERE clause in SELECT for buffer MV")
        else:
            logger.debug("   Buffer MV: No source layer subset, using sql_subset_string")

        # Parse where clauses
        parsed_where_clauses = self._backend_services.parse_case_to_where_clauses(where_clause)

        template = '''CREATE MATERIALIZED VIEW IF NOT EXISTS "{schema}"."fm_temp_mv_{name}" TABLESPACE pg_default AS
            SELECT ST_Buffer({postgresql_source_geom}, {param_buffer_expression}, '{style_params}') as {geometry_field},
                   "{table_source}"."{primary_key_name}",
                   {where_clause_fields},
                   {param_buffer_expression} as buffer_value
            FROM "{schema_source}"."{table_source}"
            WHERE "{table_source}"."{primary_key_name}" IN (SELECT sub."{primary_key_name}" FROM {source_new_subset} sub)
              AND {where_expression}
            WITH DATA;'''

        return template.format(
            schema=schema,
            name=name,
            postgresql_source_geom=pg_source_geom,
            geometry_field=geom_key_name,
            schema_source=param_source_schema,
            primary_key_name=primary_key_name,
            table_source=param_source_table,
            where_clause_fields=','.join(where_clause_fields_arr).replace('mv_', ''),
            param_buffer_expression=param_buffer.replace('mv_', ''),
            source_new_subset=source_filter_for_mv,
            where_expression=' OR '.join(parsed_where_clauses).replace('mv_', ''),
            style_params=style_params
        )

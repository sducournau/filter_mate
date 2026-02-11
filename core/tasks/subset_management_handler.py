"""
Subset Management Handler

Handles all layer subset string operations for FilterEngineTask:
- Subset string application via materialized views or temp tables
- Filter/reset/unfilter actions for PostgreSQL, Spatialite, and OGR backends
- Subset history management (insert, delete, query)
- Backend determination and performance warnings

Extracted from FilterEngineTask as part of the C1 God Object decomposition (Phase 3).

Location: core/tasks/subset_management_handler.py (Hexagonal Architecture - Application Layer)

Thread Safety:
    All setSubsetString operations are queued via _queue_subset_string callback
    and applied in finished() on the main Qt thread. Database operations
    (history insert/delete) are safe to call from worker threads.
"""

import logging
import os
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from ...infrastructure.logging import setup_logger
from ...config.config import ENV_VARS
from ...infrastructure.constants import (
    PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR
)
from ...infrastructure.utils import detect_layer_provider_type
from ...adapters.repositories.history_repository import HistoryRepository

# Setup logger
logger = setup_logger(
    'FilterMate.Tasks.Subset',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_tasks.log'),
    level=logging.INFO
)

# Lazy-load backend services
from ..ports.backend_services import get_backend_services


class SubsetManagementHandler:
    """Handles layer subset string management for all backends.

    This class encapsulates all subset string operations previously embedded
    in FilterEngineTask. Dependencies (connections, callbacks, state) are
    passed explicitly via method parameters.

    Example:
        >>> handler = SubsetManagementHandler()
        >>> handler.manage_layer_subset_strings(
        ...     layer=layer, task_action='filter',
        ...     safe_connect_fn=task._safe_spatialite_connect, ...
        ... )
    """

    def __init__(self):
        """Initialize SubsetManagementHandler with backend services facade."""
        self._backend_services = get_backend_services()

    def get_spatialite_datasource(self, layer, db_file_path):
        """Get Spatialite datasource information from layer.

        Falls back to filterMate database for non-Spatialite layers.

        Args:
            layer: QGIS vector layer.
            db_file_path: Path to filterMate database file.

        Returns:
            tuple: (db_path, table_name, layer_srid, is_native_spatialite)
        """
        from ...infrastructure.utils import get_spatialite_datasource_from_layer

        db_path, table_name = get_spatialite_datasource_from_layer(layer)
        layer_srid = layer.crs().postgisSrid()

        is_native_spatialite = db_path is not None

        if not is_native_spatialite:
            db_path = db_file_path
            logger.info("Non-Spatialite layer detected, will use QGIS subset string")

        return db_path, table_name, layer_srid, is_native_spatialite

    def build_spatialite_query(self, sql_subset_string, table_name, geom_key_name,
                                primary_key_name, custom, param_buffer_expression,
                                param_buffer_value, param_buffer_segments,
                                task_parameters, sl_executor, sl_executor_available):
        """Build Spatialite query for simple or complex (buffered) subsets.

        Args:
            sql_subset_string: SQL query for subset.
            table_name: Table name.
            geom_key_name: Geometry field name.
            primary_key_name: Primary key field name.
            custom: Whether custom buffer expression is used.
            param_buffer_expression: Buffer expression.
            param_buffer_value: Buffer value.
            param_buffer_segments: Buffer segments.
            task_parameters: Dict with task configuration.
            sl_executor: Spatialite executor module.
            sl_executor_available: Whether Spatialite executor is available.

        Returns:
            str: Built SQL query.
        """
        if sl_executor_available:
            return sl_executor.build_spatialite_query(
                sql_subset_string=sql_subset_string,
                table_name=table_name,
                geom_key_name=geom_key_name,
                primary_key_name=primary_key_name,
                custom=custom,
                buffer_expression=param_buffer_expression,
                buffer_value=param_buffer_value,
                buffer_segments=param_buffer_segments,
                task_parameters=task_parameters
            )
        # Minimal fallback: return unmodified if not custom
        return sql_subset_string

    def apply_spatialite_subset(self, layer, name, primary_key_name, sql_subset_string,
                                 cur, conn, current_seq_order, session_id, project_uuid,
                                 source_layer_id, queue_subset_fn):
        """Apply subset string to layer and update history.

        Args:
            layer: QGIS vector layer.
            name: Temp table name.
            primary_key_name: Primary key field name.
            sql_subset_string: Original SQL subset string for history.
            cur: Spatialite cursor for history.
            conn: Spatialite connection for history.
            current_seq_order: Sequence order for history.
            session_id: Session ID.
            project_uuid: Project UUID.
            source_layer_id: Source layer ID.
            queue_subset_fn: Callback to queue subset string.

        Returns:
            bool: True if successful.
        """
        return self._backend_services.apply_spatialite_subset(
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
            queue_subset_func=queue_subset_fn
        )

    def manage_spatialite_subset(self, layer, sql_subset_string, primary_key_name,
                                   geom_key_name, name, custom, cur, conn,
                                   current_seq_order, session_id, project_uuid,
                                   source_layer_id, queue_subset_fn,
                                   get_spatialite_datasource_fn, task_parameters):
        """Handle Spatialite temporary tables for filtering.

        Args:
            layer: QGIS vector layer.
            sql_subset_string: SQL query for subset.
            primary_key_name: Primary key field name.
            geom_key_name: Geometry field name.
            name: Unique name for temp table.
            custom: Whether custom buffer expression is used.
            cur: Spatialite cursor for history.
            conn: Spatialite connection for history.
            current_seq_order: Sequence order for history.
            session_id: Session ID.
            project_uuid: Project UUID.
            source_layer_id: Source layer ID.
            queue_subset_fn: Callback to queue subset string.
            get_spatialite_datasource_fn: Callback for Spatialite datasource.
            task_parameters: Dict with task configuration.

        Returns:
            bool: True if successful.
        """
        return self._backend_services.manage_spatialite_subset(
            layer=layer,
            sql_subset_string=sql_subset_string,
            primary_key_name=primary_key_name,
            geom_key_name=geom_key_name,
            name=name,
            custom=custom,
            cur=cur,
            conn=conn,
            current_seq_order=current_seq_order,
            session_id=session_id,
            project_uuid=project_uuid,
            source_layer_id=source_layer_id,
            queue_subset_func=queue_subset_fn,
            get_spatialite_datasource_func=get_spatialite_datasource_fn,
            task_parameters=task_parameters
        )

    def get_last_subset_info(self, cur, layer, project_uuid):
        """Get the last subset information for a layer from history.

        Args:
            cur: Database cursor.
            layer: QgsVectorLayer.
            project_uuid: Project UUID.

        Returns:
            tuple: (last_subset_id, last_seq_order, layer_name, name)
        """
        return self._backend_services.get_last_subset_info(cur, layer, project_uuid)

    def determine_backend(self, layer, postgresql_available):
        """Determine which backend to use for layer operations.

        Args:
            layer: QgsVectorLayer.
            postgresql_available: Whether PostgreSQL is available.

        Returns:
            tuple: (provider_type, use_postgresql, use_spatialite)
        """
        provider_type = detect_layer_provider_type(layer)
        use_postgresql = (provider_type == PROVIDER_POSTGRES and postgresql_available)
        use_spatialite = (provider_type in [PROVIDER_SPATIALITE, PROVIDER_OGR] or not use_postgresql)

        logger.debug(f"Provider={provider_type}, PostgreSQL={use_postgresql}, Spatialite={use_spatialite}")
        return provider_type, use_postgresql, use_spatialite

    def log_performance_warning_if_needed(self, use_spatialite, layer):
        """Log performance warning for large Spatialite datasets.

        Args:
            use_spatialite: Whether Spatialite backend is used.
            layer: QgsVectorLayer.
        """
        if use_spatialite and layer.featureCount() > 50000:
            logger.warning(
                f"Large dataset ({layer.featureCount():,} features) using Spatialite backend. "
                "Filtering may take longer. For optimal performance with large datasets, consider using PostgreSQL."
            )

    def insert_subset_history(self, cur, conn, layer, sql_subset_string, seq_order,
                               project_uuid, source_layer, ps_manager=None):
        """Insert subset history record into database.

        Args:
            cur: Database cursor.
            conn: Database connection.
            layer: QgsVectorLayer.
            sql_subset_string: SQL subset string.
            seq_order: Sequence order number.
            project_uuid: Project UUID.
            source_layer: Source QgsVectorLayer.
            ps_manager: Optional prepared statements manager.

        Returns:
            bool: True if successful.
        """
        from ...infrastructure.database.prepared_statements import create_prepared_statements

        # Initialize prepared statements manager if needed
        if not ps_manager:
            # Detect provider type from connection
            provider_type = 'spatialite'  # Default to spatialite for filtermate_db
            if hasattr(conn, 'get_backend_pid'):  # psycopg2 connection
                provider_type = 'postgresql'
            ps_manager = create_prepared_statements(conn, provider_type)

        # Use prepared statement if available (best performance)
        if ps_manager:
            try:
                return ps_manager.insert_subset_history(
                    history_id=str(uuid.uuid4()),
                    project_uuid=project_uuid,
                    layer_id=layer.id(),
                    source_layer_id=source_layer.id(),
                    seq_order=seq_order,
                    subset_string=sql_subset_string
                )
            except (RuntimeError, OSError, AttributeError) as e:
                logger.warning(f"Prepared statement failed, falling back to repository: {e}")

        # Fallback: Use centralized HistoryRepository
        history_repo = HistoryRepository(conn, cur)
        try:
            source_layer_id = source_layer.id() if source_layer else ''
            return history_repo.insert(
                project_uuid=project_uuid,
                layer_id=layer.id(),
                subset_string=sql_subset_string,
                seq_order=seq_order,
                source_layer_id=source_layer_id
            )
        finally:
            history_repo.close()

    def extract_where_clause_from_select(self, sql_select):
        """Extract WHERE clause from a SQL SELECT statement.

        Args:
            sql_select: Full SQL SELECT statement.

        Returns:
            str: The WHERE clause portion.
        """
        from .builders.subset_string_builder import SubsetStringBuilder
        _, where_clause = SubsetStringBuilder.extract_where_clause(sql_select)
        return where_clause

    def filter_action_postgresql(self, layer, sql_subset_string, primary_key_name,
                                   geom_key_name, name, custom, cur, conn, seq_order,
                                   queue_subset_fn, get_connection_fn, ensure_stats_fn,
                                   extract_where_fn, insert_history_fn,
                                   get_session_name_fn, ensure_schema_fn,
                                   execute_commands_fn, create_simple_mv_fn,
                                   create_custom_mv_fn, parse_where_clauses_fn,
                                   source_schema, source_table, source_geom,
                                   current_mv_schema, project_uuid, session_id,
                                   param_buffer_expression,
                                   pg_execute_filter_fn, pg_executor_available):
        """Execute filter action using PostgreSQL backend.

        Args:
            layer: QgsVectorLayer to filter.
            sql_subset_string: SQL SELECT statement.
            primary_key_name: Primary key field name.
            geom_key_name: Geometry field name.
            name: Layer identifier.
            custom: Whether this is a custom buffer filter.
            cur: Database cursor.
            conn: Database connection.
            seq_order: Sequence order number.
            queue_subset_fn: Callback to queue subset string.
            get_connection_fn: Callback for PostgreSQL connection.
            ensure_stats_fn: Callback for ensuring table stats.
            extract_where_fn: Callback for WHERE clause extraction.
            insert_history_fn: Callback for history insertion.
            get_session_name_fn: Callback for session name generation.
            ensure_schema_fn: Callback for schema creation.
            execute_commands_fn: Callback for PostgreSQL command execution.
            create_simple_mv_fn: Callback for simple MV SQL.
            create_custom_mv_fn: Callback for custom buffer MV SQL.
            parse_where_clauses_fn: Callback for WHERE clause parsing.
            source_schema: Source schema name.
            source_table: Source table name.
            source_geom: Source geometry field.
            current_mv_schema: MV schema name.
            project_uuid: Project UUID.
            session_id: Session ID.
            param_buffer_expression: Buffer expression if any.
            pg_execute_filter_fn: PostgreSQL execute filter function.
            pg_executor_available: Whether PG executor is available.

        Returns:
            bool: True if successful.
        """
        if pg_executor_available and pg_execute_filter_fn:
            return pg_execute_filter_fn(
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
                extract_where_fn=extract_where_fn,
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

        error_msg = (
            "PostgreSQL filter_actions module not available. "
            "This indicates a critical installation issue."
        )
        logger.error(error_msg)
        raise ImportError(error_msg)

    def reset_action_postgresql(self, layer, name, cur, conn,
                                  queue_subset_fn, get_connection_fn,
                                  execute_commands_fn, get_session_name_fn,
                                  project_uuid, current_mv_schema,
                                  ps_manager, pg_execute_reset_fn, pg_executor_available):
        """Execute reset action using PostgreSQL backend.

        Args:
            layer: QgsVectorLayer to reset.
            name: Layer identifier.
            cur: Database cursor.
            conn: Database connection.
            queue_subset_fn: Callback to queue subset string.
            get_connection_fn: Callback for PostgreSQL connection.
            execute_commands_fn: Callback for command execution.
            get_session_name_fn: Callback for session name.
            project_uuid: Project UUID.
            current_mv_schema: MV schema name.
            ps_manager: Prepared statements manager.
            pg_execute_reset_fn: PostgreSQL reset function.
            pg_executor_available: Whether PG executor is available.

        Returns:
            bool: True if successful.
        """
        if pg_executor_available and pg_execute_reset_fn:
            delete_history_fn = None
            if ps_manager:
                delete_history_fn = ps_manager.delete_subset_history

            return pg_execute_reset_fn(
                layer=layer,
                name=name,
                cur=cur,
                conn=conn,
                queue_subset_fn=queue_subset_fn,
                get_connection_fn=get_connection_fn,
                execute_commands_fn=execute_commands_fn,
                get_session_name_fn=get_session_name_fn,
                delete_history_fn=delete_history_fn,
                project_uuid=project_uuid,
                current_mv_schema=current_mv_schema
            )

        error_msg = "PostgreSQL filter_actions module not available"
        logger.error(error_msg)
        raise ImportError(error_msg)

    def reset_action_spatialite(self, layer, name, cur, conn,
                                  project_uuid, ps_manager,
                                  get_session_name_fn, db_file_path,
                                  queue_subset_fn):
        """Execute reset action using Spatialite backend.

        Args:
            layer: QgsVectorLayer to reset.
            name: Layer identifier.
            cur: Database cursor.
            conn: Database connection.
            project_uuid: Project UUID.
            ps_manager: Prepared statements manager.
            get_session_name_fn: Callback for session name.
            db_file_path: Path to filterMate database.
            queue_subset_fn: Callback to queue subset string.

        Returns:
            bool: True if successful.
        """
        logger.info("Reset - Spatialite backend - dropping temp table")

        history_repo = HistoryRepository(conn, cur)
        try:
            if ps_manager:
                try:
                    ps_manager.delete_subset_history(project_uuid, layer.id())
                except (RuntimeError, OSError, AttributeError) as e:
                    logger.warning(f"Prepared statement failed, falling back to repository: {e}")
                    history_repo.delete_for_layer(project_uuid, layer.id())
            else:
                history_repo.delete_for_layer(project_uuid, layer.id())
        finally:
            history_repo.close()

        # Drop temp table from filterMate_db using session-prefixed name
        import sqlite3
        session_name = get_session_name_fn(name)
        try:
            temp_conn = sqlite3.connect(db_file_path)
            temp_cur = temp_conn.cursor()
            temp_cur.execute(f"DROP TABLE IF EXISTS fm_temp_{session_name}")  # nosec B608
            temp_cur.execute(f"DROP TABLE IF EXISTS mv_{session_name}")  # nosec B608
            temp_conn.commit()
            temp_cur.close()
            temp_conn.close()
        except sqlite3.Error as e:
            logger.error(f"Error dropping Spatialite temp table: {e}")

        queue_subset_fn(layer, '')
        return True

    def reset_action_ogr(self, layer, name, cur, conn,
                           project_uuid, ps_manager, queue_subset_fn,
                           ogr_execute_reset_fn):
        """Execute reset action using OGR backend.

        Args:
            layer: QgsVectorLayer to reset.
            name: Layer identifier.
            cur: Database cursor.
            conn: Database connection.
            project_uuid: Project UUID.
            ps_manager: Prepared statements manager.
            queue_subset_fn: Callback to queue subset string.
            ogr_execute_reset_fn: OGR reset function.

        Returns:
            bool: True if successful.
        """
        logger.info("Reset - OGR backend")

        history_repo = HistoryRepository(conn, cur)
        try:
            if ps_manager:
                try:
                    ps_manager.delete_subset_history(project_uuid, layer.id())
                except (RuntimeError, OSError, AttributeError) as e:
                    logger.warning(f"Prepared statement failed, falling back to repository: {e}")
                    history_repo.delete_for_layer(project_uuid, layer.id())
            else:
                history_repo.delete_for_layer(project_uuid, layer.id())
        finally:
            history_repo.close()

        if ogr_execute_reset_fn:
            return ogr_execute_reset_fn(
                layer=layer,
                queue_subset_func=queue_subset_fn,
                cleanup_temp_layers=True
            )

        # Fallback: simple subset clear
        queue_subset_fn(layer, '')
        return True

    def unfilter_action(self, layer, primary_key_name, geom_key_name, name, custom,
                          cur, conn, last_subset_id, use_postgresql, use_spatialite,
                          queue_subset_fn, get_connection_fn, execute_commands_fn,
                          get_session_name_fn, create_simple_mv_fn,
                          project_uuid, current_mv_schema,
                          pg_execute_unfilter_fn, pg_executor_available,
                          ogr_execute_unfilter_fn, manage_spatialite_subset_fn):
        """Execute unfilter action (restore previous filter state).

        Args:
            layer: QgsVectorLayer to unfilter.
            primary_key_name: Primary key field name.
            geom_key_name: Geometry field name.
            name: Layer identifier.
            custom: Whether this is a custom buffer filter.
            cur: Database cursor.
            conn: Database connection.
            last_subset_id: Last subset ID to remove.
            use_postgresql: Whether to use PostgreSQL backend.
            use_spatialite: Whether to use Spatialite backend.
            queue_subset_fn: Callback to queue subset string.
            get_connection_fn: Callback for PostgreSQL connection.
            execute_commands_fn: Callback for command execution.
            get_session_name_fn: Callback for session name.
            create_simple_mv_fn: Callback for simple MV SQL.
            project_uuid: Project UUID.
            current_mv_schema: MV schema name.
            pg_execute_unfilter_fn: PostgreSQL unfilter function.
            pg_executor_available: Whether PG executor is available.
            ogr_execute_unfilter_fn: OGR unfilter function.
            manage_spatialite_subset_fn: Callback for Spatialite subset management.

        Returns:
            bool: True if successful.
        """
        if use_postgresql and pg_executor_available and pg_execute_unfilter_fn:
            return pg_execute_unfilter_fn(
                layer=layer,
                primary_key_name=primary_key_name,
                geom_key_name=geom_key_name,
                name=name,
                cur=cur,
                conn=conn,
                last_subset_id=last_subset_id,
                queue_subset_fn=queue_subset_fn,
                get_connection_fn=get_connection_fn,
                execute_commands_fn=execute_commands_fn,
                get_session_name_fn=get_session_name_fn,
                create_simple_mv_fn=create_simple_mv_fn,
                project_uuid=project_uuid,
                current_mv_schema=current_mv_schema
            )
        elif use_postgresql:
            error_msg = "PostgreSQL filter_actions module not available"
            logger.error(error_msg)
            raise ImportError(error_msg)

        # Determine if this is OGR or Spatialite
        provider_type = detect_layer_provider_type(layer)
        if provider_type == PROVIDER_OGR and ogr_execute_unfilter_fn:
            return self._unfilter_action_ogr(
                layer, cur, conn, last_subset_id,
                project_uuid, queue_subset_fn, ogr_execute_unfilter_fn
            )

        # Spatialite path (also used as fallback for OGR without ogr_execute_unfilter)
        return self._unfilter_action_spatialite(
            layer, primary_key_name, geom_key_name, name, custom,
            cur, conn, last_subset_id,
            project_uuid, queue_subset_fn, manage_spatialite_subset_fn
        )

    def _unfilter_action_ogr(self, layer, cur, conn, last_subset_id,
                               project_uuid, queue_subset_fn, ogr_execute_unfilter_fn):
        """Unfilter implementation for OGR backend.

        Args:
            layer: QgsVectorLayer to unfilter.
            cur: Database cursor.
            conn: Database connection.
            last_subset_id: Last subset ID to remove.
            project_uuid: Project UUID.
            queue_subset_fn: Callback to queue subset string.
            ogr_execute_unfilter_fn: OGR unfilter function.

        Returns:
            bool: True if successful.
        """
        history_repo = HistoryRepository(conn, cur)
        try:
            if last_subset_id:
                history_repo.delete_entry(project_uuid, layer.id(), last_subset_id)
            last_entry = history_repo.get_last_entry(project_uuid, layer.id())
        finally:
            history_repo.close()

        previous_subset = None

        if last_entry:
            previous_subset = last_entry.subset_string

            if not previous_subset or not previous_subset.strip():
                logger.warning(
                    f"Unfilter OGR: Previous subset from history is empty for {layer.name()}. "
                    "Clearing layer filter."
                )
                previous_subset = None

        if ogr_execute_unfilter_fn:
            return ogr_execute_unfilter_fn(
                layer=layer,
                previous_subset=previous_subset,
                queue_subset_func=queue_subset_fn
            )

        queue_subset_fn(layer, previous_subset or '')
        return True

    def _unfilter_action_spatialite(self, layer, primary_key_name, geom_key_name,
                                      name, custom, cur, conn, last_subset_id,
                                      project_uuid, queue_subset_fn,
                                      manage_spatialite_subset_fn):
        """Unfilter implementation for Spatialite backend.

        Args:
            layer: QgsVectorLayer to unfilter.
            primary_key_name: Primary key field name.
            geom_key_name: Geometry field name.
            name: Layer identifier.
            custom: Whether this is a custom buffer filter.
            cur: Database cursor.
            conn: Database connection.
            last_subset_id: Last subset ID to remove.
            project_uuid: Project UUID.
            queue_subset_fn: Callback to queue subset string.
            manage_spatialite_subset_fn: Callback for Spatialite subset management.

        Returns:
            bool: True if successful.
        """
        history_repo = HistoryRepository(conn, cur)
        try:
            if last_subset_id:
                history_repo.delete_entry(project_uuid, layer.id(), last_subset_id)
            last_entry = history_repo.get_last_entry(project_uuid, layer.id())
        finally:
            history_repo.close()

        if last_entry:
            sql_subset_string = last_entry.subset_string

            if not sql_subset_string or not sql_subset_string.strip():
                logger.warning(
                    f"Unfilter: Previous subset string from history is empty for {layer.name()}. "
                    "Clearing layer filter."
                )
                queue_subset_fn(layer, '')
                return True

            logger.info("Unfilter - Spatialite backend - recreating previous subset")
            success = manage_spatialite_subset_fn(
                layer, sql_subset_string, primary_key_name, geom_key_name,
                name, False, None, None, 0
            )
            if not success:
                queue_subset_fn(layer, '')
        else:
            queue_subset_fn(layer, '')

        return True

    def manage_layer_subset_strings(
        self,
        layer,
        task_action,
        safe_connect_fn,
        active_connections,
        project_uuid,
        session_id,
        source_layer,
        db_file_path,
        ps_manager,
        postgresql_available,
        queue_subset_fn,
        get_session_name_fn,
        get_connection_fn,
        ensure_stats_fn,
        extract_where_fn,
        insert_history_fn,
        ensure_schema_fn,
        execute_commands_fn,
        create_simple_mv_fn,
        create_custom_mv_fn,
        parse_where_clauses_fn,
        manage_spatialite_subset_fn,
        get_spatialite_datasource_fn,
        pg_execute_filter_fn,
        pg_execute_reset_fn,
        pg_execute_unfilter_fn,
        pg_executor_available,
        ogr_execute_reset_fn,
        ogr_execute_unfilter_fn,
        current_mv_schema,
        param_source_schema=None,
        param_source_table=None,
        param_source_geom=None,
        param_buffer_expression=None,
        task_parameters=None,
        sql_subset_string=None,
        primary_key_name=None,
        geom_key_name=None,
        custom=False,
    ):
        """Manage layer subset strings using materialized views or temp tables.

        This is the main orchestrator method. It determines the backend, executes
        the appropriate action (filter/reset/unfilter), and handles cleanup.

        Args:
            layer: QgsVectorLayer to manage.
            task_action: Action to perform ('filter', 'reset', 'unfilter').
            safe_connect_fn: Context manager for safe Spatialite connection.
            active_connections: List to track active connections.
            project_uuid: Project UUID.
            session_id: Session ID.
            source_layer: Source QgsVectorLayer.
            db_file_path: Path to filterMate database.
            ps_manager: Prepared statements manager.
            postgresql_available: Whether PostgreSQL is available.
            queue_subset_fn: Callback to queue subset string.
            get_session_name_fn: Callback for session name.
            get_connection_fn: Callback for PostgreSQL connection.
            ensure_stats_fn: Callback for ensuring table stats.
            extract_where_fn: Callback for WHERE clause extraction.
            insert_history_fn: Callback for history insertion.
            ensure_schema_fn: Callback for schema creation.
            execute_commands_fn: Callback for command execution.
            create_simple_mv_fn: Callback for simple MV SQL.
            create_custom_mv_fn: Callback for custom buffer MV SQL.
            parse_where_clauses_fn: Callback for WHERE clause parsing.
            manage_spatialite_subset_fn: Callback for Spatialite subset management.
            get_spatialite_datasource_fn: Callback for Spatialite datasource.
            pg_execute_filter_fn: PostgreSQL filter function.
            pg_execute_reset_fn: PostgreSQL reset function.
            pg_execute_unfilter_fn: PostgreSQL unfilter function.
            pg_executor_available: Whether PG executor is available.
            ogr_execute_reset_fn: OGR reset function.
            ogr_execute_unfilter_fn: OGR unfilter function.
            current_mv_schema: MV schema name.
            param_source_schema: Source schema name.
            param_source_table: Source table name.
            param_source_geom: Source geometry field.
            param_buffer_expression: Buffer expression.
            task_parameters: Dict with task configuration.
            sql_subset_string: SQL SELECT statement for filtering.
            primary_key_name: Primary key field name.
            geom_key_name: Geometry field name.
            custom: Whether this is a custom buffer filter.

        Returns:
            bool: True if successful.
        """
        with safe_connect_fn() as conn:
            active_connections.append(conn)
            cur = conn.cursor()

            try:
                # Get layer info and history
                last_subset_id, last_seq_order, layer_name, name = self.get_last_subset_info(
                    cur, layer, project_uuid
                )

                # Determine backend to use
                provider_type, use_postgresql, use_spatialite = self.determine_backend(
                    layer, postgresql_available
                )

                # Log performance warning if needed
                self.log_performance_warning_if_needed(use_spatialite, layer)

                # Execute appropriate action based on task_action
                if task_action == 'filter':
                    current_seq_order = last_seq_order + 1

                    if not sql_subset_string or not sql_subset_string.strip():
                        logger.warning(
                            f"Skipping subset management for {layer.name()}: "
                            "sql_subset_string is empty. Filter was applied via setSubsetString but "
                            "history/materialized view creation is skipped."
                        )
                        return True

                    if use_spatialite:
                        backend_name = "Spatialite" if provider_type == PROVIDER_SPATIALITE else "Local (OGR)"
                        logger.debug(f"Using {backend_name} backend")
                        success = manage_spatialite_subset_fn(
                            layer, sql_subset_string, primary_key_name, geom_key_name,
                            name, custom, cur, conn, current_seq_order
                        )
                        return success

                    return self.filter_action_postgresql(
                        layer=layer,
                        sql_subset_string=sql_subset_string,
                        primary_key_name=primary_key_name,
                        geom_key_name=geom_key_name,
                        name=name,
                        custom=custom,
                        cur=cur,
                        conn=conn,
                        seq_order=current_seq_order,
                        queue_subset_fn=queue_subset_fn,
                        get_connection_fn=get_connection_fn,
                        ensure_stats_fn=ensure_stats_fn,
                        extract_where_fn=extract_where_fn,
                        insert_history_fn=insert_history_fn,
                        get_session_name_fn=get_session_name_fn,
                        ensure_schema_fn=ensure_schema_fn,
                        execute_commands_fn=execute_commands_fn,
                        create_simple_mv_fn=create_simple_mv_fn,
                        create_custom_mv_fn=create_custom_mv_fn,
                        parse_where_clauses_fn=parse_where_clauses_fn,
                        source_schema=param_source_schema,
                        source_table=param_source_table,
                        source_geom=param_source_geom,
                        current_mv_schema=current_mv_schema,
                        project_uuid=project_uuid,
                        session_id=session_id,
                        param_buffer_expression=param_buffer_expression,
                        pg_execute_filter_fn=pg_execute_filter_fn,
                        pg_executor_available=pg_executor_available,
                    )

                elif task_action == 'reset':
                    if use_postgresql:
                        return self.reset_action_postgresql(
                            layer=layer, name=name, cur=cur, conn=conn,
                            queue_subset_fn=queue_subset_fn,
                            get_connection_fn=get_connection_fn,
                            execute_commands_fn=execute_commands_fn,
                            get_session_name_fn=get_session_name_fn,
                            project_uuid=project_uuid,
                            current_mv_schema=current_mv_schema,
                            ps_manager=ps_manager,
                            pg_execute_reset_fn=pg_execute_reset_fn,
                            pg_executor_available=pg_executor_available,
                        )
                    elif provider_type == PROVIDER_OGR:
                        return self.reset_action_ogr(
                            layer=layer, name=name, cur=cur, conn=conn,
                            project_uuid=project_uuid,
                            ps_manager=ps_manager,
                            queue_subset_fn=queue_subset_fn,
                            ogr_execute_reset_fn=ogr_execute_reset_fn,
                        )
                    elif use_spatialite:
                        return self.reset_action_spatialite(
                            layer=layer, name=name, cur=cur, conn=conn,
                            project_uuid=project_uuid,
                            ps_manager=ps_manager,
                            get_session_name_fn=get_session_name_fn,
                            db_file_path=db_file_path,
                            queue_subset_fn=queue_subset_fn,
                        )

                elif task_action == 'unfilter':
                    return self.unfilter_action(
                        layer=layer,
                        primary_key_name=primary_key_name,
                        geom_key_name=geom_key_name,
                        name=name,
                        custom=custom,
                        cur=cur,
                        conn=conn,
                        last_subset_id=last_subset_id,
                        use_postgresql=use_postgresql,
                        use_spatialite=use_spatialite,
                        queue_subset_fn=queue_subset_fn,
                        get_connection_fn=get_connection_fn,
                        execute_commands_fn=execute_commands_fn,
                        get_session_name_fn=get_session_name_fn,
                        create_simple_mv_fn=create_simple_mv_fn,
                        project_uuid=project_uuid,
                        current_mv_schema=current_mv_schema,
                        pg_execute_unfilter_fn=pg_execute_unfilter_fn,
                        pg_executor_available=pg_executor_available,
                        ogr_execute_unfilter_fn=ogr_execute_unfilter_fn,
                        manage_spatialite_subset_fn=manage_spatialite_subset_fn,
                    )

                return True

            finally:
                try:
                    cur.close()
                except (RuntimeError, OSError, AttributeError) as e:
                    logger.debug(f"Could not close database cursor: {e}")
                if conn in active_connections:
                    active_connections.remove(conn)

# -*- coding: utf-8 -*-
"""
PostgreSQL Backend Handler for FilterEngineTask.

Phase 4 (v6.0): Extracted from core/tasks/filter_task.py to reduce God class.
Contains all PostgreSQL-specific operations:
- Connection management and validation
- Materialized view lifecycle (create, cleanup, reference tracking)
- Filter/reset/unfilter actions
- Expression building and spatial query construction
- Subset history management

Location: core/tasks/handlers/postgresql_handler.py (Hexagonal Architecture - Application Layer)
"""

import logging
import os
import uuid
import time
from typing import Any, Dict, List, Optional

from ....infrastructure.logging import setup_logger
from ....config.config import ENV_VARS
from ....infrastructure.utils import get_datasource_connexion_from_layer
from ....infrastructure.database.prepared_statements import create_prepared_statements
from ....adapters.repositories.history_repository import HistoryRepository

# Core imports
from ...ports.backend_services import get_backend_services

# Setup logger
logger = setup_logger(
    'FilterMate.Tasks.PostgreSQLHandler',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_tasks.log'),
    level=logging.INFO
)

# PostgreSQL availability via facade
_backend_services = get_backend_services()
_pg_availability = _backend_services.get_postgresql_availability()
psycopg2 = _pg_availability.psycopg2
POSTGRESQL_AVAILABLE = _pg_availability.postgresql_available

# PostgreSQL executor
pg_executor = _backend_services.get_postgresql_executor()
PG_EXECUTOR_AVAILABLE = pg_executor is not None

# Filter actions
_pg_actions = _backend_services.get_postgresql_filter_actions()
if _pg_actions:
    pg_execute_filter = _pg_actions.get('filter')
    pg_execute_reset = _pg_actions.get('reset')
else:
    pg_execute_filter = None
    pg_execute_reset = None


class PostgreSQLHandler:
    """Handler for PostgreSQL-specific operations in FilterEngineTask.

    Phase 4 (v6.0): Extracted 24 methods from FilterEngineTask.
    Access task state via self.task.* (e.g., self.task.source_layer, self.task.param_source_schema).
    """

    def __init__(self, task):
        """Initialize with reference to the parent FilterEngineTask.

        Args:
            task: FilterEngineTask instance
        """
        self.task = task

    # ── Connection & Setup ──────────────────────────────────────────────

    def get_valid_connection(self):
        """
        Get a valid PostgreSQL connection for the current task.

        Checks if ACTIVE_POSTGRESQL in task_parameters contains a valid psycopg2
        connection object. If not, attempts to obtain a fresh connection from the source layer.

        Returns:
            psycopg2.connection: Valid PostgreSQL connection object

        Raises:
            Exception: If no valid connection can be established
        """
        # Try to get connection from task parameters
        connexion = self.task.task_parameters.get("task", {}).get("options", {}).get("ACTIVE_POSTGRESQL")

        # FIX v4.0.8: Explicitly reject dict objects
        if isinstance(connexion, dict):
            logger.warning("ACTIVE_POSTGRESQL is a dict (connection params), not a connection object - obtaining fresh connection")
            connexion = None

        # Validate that it's actually a connection object
        if connexion is not None and not isinstance(connexion, str):
            try:
                if hasattr(connexion, 'cursor') and callable(getattr(connexion, 'cursor')):
                    if not getattr(connexion, 'closed', True):
                        return connexion
                    else:
                        logger.warning("ACTIVE_POSTGRESQL connection is closed, will obtain new connection")
            except Exception as e:
                logger.warning(f"Error checking ACTIVE_POSTGRESQL connection: {e}")

        # Connection is invalid - try to get fresh connection from source layer
        logger.info("ACTIVE_POSTGRESQL is not a valid connection object, obtaining fresh connection from source layer")

        if hasattr(self.task, 'source_layer') and self.task.source_layer is not None:
            try:
                connexion, source_uri = get_datasource_connexion_from_layer(self.task.source_layer)
                if connexion is not None:
                    self.task.active_connections.append(connexion)
                    return connexion
            except Exception as e:
                logger.error(f"Failed to get connection from source layer: {e}")

        # Last resort: try from infos layer_id
        try:
            layer_id = self.task.task_parameters.get("infos", {}).get("layer_id")
            if layer_id:
                layer = self.task.PROJECT.mapLayer(layer_id)
                if layer and layer.providerType() == 'postgres':
                    connexion, source_uri = get_datasource_connexion_from_layer(layer)
                    if connexion is not None:
                        self.task.active_connections.append(connexion)
                        return connexion
        except Exception as e:
            logger.error(f"Failed to get connection from layer by ID: {e}")

        raise Exception(
            "No valid PostgreSQL connection available. "
            "ACTIVE_POSTGRESQL was not a valid connection object and could not obtain fresh connection from layer."
        )

    def ensure_temp_schema_exists(self, connexion, schema_name):
        """
        Ensure the temporary schema exists in PostgreSQL database.

        Args:
            connexion: psycopg2 connection
            schema_name: Name of the schema to create

        Returns:
            str: Name of the schema to use (schema_name if created, 'public' as fallback)
        """
        result = _backend_services.ensure_temp_schema_exists(connexion, schema_name)

        # Track schema error for instance state if fallback occurred
        if result == 'public' and schema_name != 'public':
            self.task._last_schema_error = f"Using 'public' schema as fallback (could not create '{schema_name}')"

        return result

    def execute_commands(self, connexion, commands):
        """
        Execute PostgreSQL commands with automatic reconnection on failure.

        Args:
            connexion: psycopg2 connection
            commands: List of SQL commands to execute

        Returns:
            bool: True if all commands succeeded
        """
        # Test connection and reconnect if needed
        try:
            with connexion.cursor() as cursor:
                cursor.execute("SELECT 1")
        except (psycopg2.OperationalError, psycopg2.InterfaceError, AttributeError) as e:
            logger.debug(f"PostgreSQL connection test failed, reconnecting: {e}")
            connexion, _ = get_datasource_connexion_from_layer(self.task.source_layer)

        return _backend_services.execute_commands(connexion, commands)

    def ensure_source_table_stats(self, connexion, schema, table, geom_field):
        """
        Ensure PostgreSQL statistics exist for source table geometry column.

        Args:
            connexion: psycopg2 connection
            schema: Schema name
            table: Table name
            geom_field: Geometry column name

        Returns:
            bool: True if stats were verified/created
        """
        return _backend_services.ensure_table_stats(connexion, schema, table, geom_field)

    # ── Expression Conversion ───────────────────────────────────────────

    def qgis_expression_to_postgis(self, expression):
        """Convert a QGIS expression to PostGIS-compatible SQL.

        Args:
            expression: QGIS expression string to convert.

        Returns:
            PostGIS-compatible SQL expression, or original if empty.
        """
        if not expression:
            return expression
        geom_col = getattr(self.task, 'param_source_geom', None) or 'geometry'
        from ...services.expression_service import ExpressionService
        from ...domain.filter_expression import ProviderType
        return ExpressionService().to_sql(expression, ProviderType.POSTGRESQL, geom_col)

    def extract_spatial_clauses_for_exists(self, filter_expr, source_table=None):
        """Delegates to core.filter.expression_sanitizer.extract_spatial_clauses_for_exists()."""
        from ...filter.expression_sanitizer import extract_spatial_clauses_for_exists
        return extract_spatial_clauses_for_exists(filter_expr, source_table)

    def apply_type_casting(self, expression, layer=None):
        """Delegates to pg_executor.apply_postgresql_type_casting()."""
        if PG_EXECUTOR_AVAILABLE:
            return pg_executor.apply_postgresql_type_casting(expression, layer)
        return expression

    def normalize_column_names(self, expression, field_names):
        """
        Normalize column names in expression to match actual PostgreSQL column names.
        """
        if not PG_EXECUTOR_AVAILABLE:
            raise ImportError("pg_executor module not available - cannot normalize column names for PostgreSQL")
        return pg_executor.normalize_column_names_for_postgresql(expression, field_names)

    # ── Geometry Preparation ────────────────────────────────────────────

    def prepare_source_geom(self):
        """Prepare PostgreSQL source geometry with buffer/centroid. Delegated to BackendServices facade.

        Returns:
            str: PostgreSQL geometry expression
        """
        logger.info("=" * 60)
        logger.info("PREPARING PostgreSQL SOURCE GEOMETRY")
        logger.info("=" * 60)
        logger.info(f"   source_schema: {self.task.param_source_schema}")
        logger.info(f"   source_table: {self.task.param_source_table}")
        logger.info(f"   source_geom: {self.task.param_source_geom}")
        logger.info(f"   buffer_value: {getattr(self.task, 'param_buffer_value', None)}")
        logger.info(f"   buffer_expression: {getattr(self.task, 'param_buffer_expression', None)}")
        logger.info(f"   use_centroids: {getattr(self.task, 'param_use_centroids_source_layer', False)}")
        logger.info(f"   session_id: {getattr(self.task, 'session_id', None)}")
        logger.info(f"   mv_schema: {getattr(self.task, 'current_materialized_view_schema', 'filter_mate_temp')}")

        # FIX v4.2.7: Use cached feature count for consistent threshold decisions
        source_fc = getattr(self.task, '_cached_source_feature_count', None)
        if source_fc is None:
            source_fc = self.task.source_layer.featureCount() if self.task.source_layer else None
            logger.warning(f"   Using fresh featureCount (not cached): {source_fc}")
        logger.info(f"   source_feature_count: {source_fc} (threshold=10000)")

        result_geom, mv_name = _backend_services.prepare_postgresql_source_geom(
            source_table=self.task.param_source_table, source_schema=self.task.param_source_schema,
            source_geom=self.task.param_source_geom, buffer_value=getattr(self.task, 'param_buffer_value', None),
            buffer_expression=getattr(self.task, 'param_buffer_expression', None),
            use_centroids=getattr(self.task, 'param_use_centroids_source_layer', False),
            buffer_segments=getattr(self.task, 'param_buffer_segments', 5),
            buffer_type=self.task.task_parameters.get("filtering", {}).get("buffer_type", "Round"),
            primary_key_name=getattr(self.task, 'primary_key_name', None),
            session_id=getattr(self.task, 'session_id', None),
            mv_schema=getattr(self.task, 'current_materialized_view_schema', 'filter_mate_temp'),
            source_feature_count=source_fc
        )
        self.task.postgresql_source_geom = result_geom
        if mv_name:
            self.task.current_materialized_view_name = mv_name

        logger.info(f"   postgresql_source_geom = '{str(result_geom)[:100]}...'")
        logger.info("=" * 60)

        return result_geom

    # ── Expression Building ─────────────────────────────────────────────

    def build_spatial_join_query(self, layer_props, param_postgis_sub_expression, sub_expression):
        """Build SELECT query with spatial JOIN for filtering. Delegates to pg_executor."""
        if PG_EXECUTOR_AVAILABLE:
            return pg_executor.build_spatial_join_query(
                layer_props=layer_props,
                param_postgis_sub_expression=param_postgis_sub_expression,
                sub_expression=sub_expression,
                current_materialized_view_name=self.task.current_materialized_view_name,
                current_materialized_view_schema=self.task.current_materialized_view_schema,
                source_schema=self.task.param_source_schema,
                source_table=self.task.param_source_table,
                expression=self.task.expression,
                has_combine_operator=self.task.has_combine_operator
            )
        # Minimal fallback for non-PG environments
        param_distant_primary_key_name = layer_props["primary_key_name"]
        param_distant_schema = layer_props["layer_schema"]
        param_distant_table = layer_props["layer_name"]
        source_ref = self.task._get_source_reference(sub_expression)
        return (
            f'(SELECT "{param_distant_table}"."{param_distant_primary_key_name}" '
            f'FROM "{param_distant_schema}"."{param_distant_table}" '
            f'INNER JOIN {source_ref} ON {param_postgis_sub_expression})'
        )

    def build_postgis_filter_expression(self, layer_props, param_postgis_sub_expression, sub_expression, param_old_subset, param_combine_operator):
        """
        Build complete PostGIS filter expression for subset string.

        Args:
            layer_props: Layer properties dict
            param_postgis_sub_expression: PostGIS spatial predicate expression
            sub_expression: Source layer subset expression
            param_old_subset: Existing subset string from layer
            param_combine_operator: SQL set operator (UNION, INTERSECT, EXCEPT)

        Returns:
            tuple: (expression, param_expression) - Complete filter and subquery
        """
        if PG_EXECUTOR_AVAILABLE:
            return pg_executor.build_postgis_filter_expression(
                layer_props=layer_props,
                param_postgis_sub_expression=param_postgis_sub_expression,
                sub_expression=sub_expression,
                param_old_subset=param_old_subset,
                param_combine_operator=param_combine_operator,
                current_materialized_view_name=self.task.current_materialized_view_name,
                current_materialized_view_schema=self.task.current_materialized_view_schema,
                source_schema=self.task.param_source_schema,
                source_table=self.task.param_source_table,
                expression=self.task.expression,
                has_combine_operator=self.task.has_combine_operator
            )
        # Minimal fallback
        param_expression = self.build_spatial_join_query(
            layer_props, param_postgis_sub_expression, sub_expression
        )
        expression = self.task._apply_combine_operator(
            layer_props["primary_key_name"], param_expression, param_old_subset, param_combine_operator
        )
        return expression, param_expression

    # ── Materialized View Lifecycle ─────────────────────────────────────

    def create_source_mv_if_needed(self, source_mv_info):
        """Create source materialized view with pre-computed buffer (v2.9.0 optimization)."""
        if not source_mv_info or not source_mv_info.create_sql:
            return False

        try:
            start_time = time.time()

            connexion = self.get_valid_connection()
            if not connexion:
                logger.warning("No PostgreSQL connection available for source MV creation")
                return False

            schema = source_mv_info.schema
            view_name = source_mv_info.view_name

            commands = [
                f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."{view_name}" CASCADE;',
                source_mv_info.create_sql,
                f'CREATE INDEX IF NOT EXISTS idx_{view_name}_geom ON "{schema}"."{view_name}" USING GIST (geom);',
                f'CREATE INDEX IF NOT EXISTS idx_{view_name}_buff ON "{schema}"."{view_name}" USING GIST (geom_buffered);',
                f'ANALYZE "{schema}"."{view_name}";'
            ]

            self.execute_commands(connexion, commands)

            # FIX v4.2.8: Register MV references to prevent premature cleanup
            from ....adapters.backends.postgresql.mv_reference_tracker import get_mv_reference_tracker
            tracker = get_mv_reference_tracker()

            if hasattr(self.task, 'source_layer') and self.task.source_layer:
                tracker.add_reference(view_name, self.task.source_layer.id())

            if hasattr(self.task, 'param_all_layers'):
                for layer in self.task.param_all_layers:
                    if layer and hasattr(layer, 'id'):
                        if not self.task.source_layer or layer.id() != self.task.source_layer.id():
                            tracker.add_reference(view_name, layer.id())

            elapsed = time.time() - start_time
            fid_count = len(source_mv_info.fid_list)
            logger.info(
                f"v2.9.0: Source MV '{view_name}' created in {elapsed:.2f}s "
                f"({fid_count} FIDs with pre-computed buffer)"
            )
            logger.info(f"   FIX v4.2.8: Registered references for multiple layers")
            return True

        except Exception as e:
            logger.warning(f"Failed to create source MV '{source_mv_info.view_name}': {e}")
            return False

    def ensure_buffer_expression_mv_exists(self):
        """
        FIX v4.2.1/v4.2.7: Ensure buffer expression MVs exist BEFORE distant layer filtering.
        Only create MVs if feature count exceeds threshold.
        """
        from ....infrastructure.database.sql_utils import sanitize_sql_identifier
        from ....adapters.backends.postgresql.filter_executor import BUFFER_EXPR_MV_THRESHOLD

        logger.info("=" * 60)
        logger.info("FIX v4.2.1/v4.2.7: Checking buffer expression MV requirements...")
        logger.info(f"   param_buffer_expression: {self.task.param_buffer_expression}")
        logger.info(f"   session_id: {self.task.session_id}")
        logger.info(f"   source_table: {self.task.param_source_table}")

        source_feature_count = getattr(self.task, '_cached_source_feature_count', None)
        if source_feature_count is None:
            source_feature_count = self.task.source_layer.featureCount() if self.task.source_layer else 0
            logger.warning(f"   Using fresh featureCount (not cached): {source_feature_count}")
        logger.info(f"   source_feature_count: {source_feature_count}")
        logger.info(f"   BUFFER_EXPR_MV_THRESHOLD: {BUFFER_EXPR_MV_THRESHOLD}")

        if source_feature_count is not None and source_feature_count <= BUFFER_EXPR_MV_THRESHOLD:
            logger.info(f"   SKIP MV creation: {source_feature_count} features <= {BUFFER_EXPR_MV_THRESHOLD} threshold")
            logger.info(f"   prepare_postgresql_source_geom() will use INLINE ST_Buffer() instead")
            logger.info("=" * 60)
            return True

        logger.info(f"   Creating MV: {source_feature_count} features > {BUFFER_EXPR_MV_THRESHOLD} threshold")
        logger.info("=" * 60)

        start_time = time.time()

        try:
            connexion = self.get_valid_connection()
            if not connexion:
                logger.warning("No PostgreSQL connection available for buffer expression MV creation")
                return False

            base_mv_name = sanitize_sql_identifier(self.task.param_source_table + '_buffer_expr')
            if self.task.session_id:
                mv_name = f"{self.task.session_id}_{base_mv_name}"
            else:
                mv_name = base_mv_name
                logger.warning("No session_id - using base MV name (may conflict with other sessions)")

            schema = self.task.current_materialized_view_schema
            geom_field = self.task.param_source_geom

            source_subset = self.task.source_layer.subsetString() if self.task.source_layer else ""

            buffer_expr = self.task.param_buffer_expression
            if buffer_expr:
                buffer_expr = self.qgis_expression_to_postgis(buffer_expr)
                if buffer_expr.find('"') == 0 and self.task.param_source_table not in buffer_expr[:50]:
                    buffer_expr = f'"{self.task.param_source_table}".' + buffer_expr

            buffer_type_mapping = {"Round": "round", "Flat": "flat", "Square": "square"}
            buffer_type_str = self.task.task_parameters.get("filtering", {}).get("buffer_type", "Round")
            endcap_style = buffer_type_mapping.get(buffer_type_str, "round")
            quad_segs = getattr(self.task, 'param_buffer_segments', 5)
            style_params = f"quad_segs={quad_segs}"
            if endcap_style != 'round':
                style_params += f" endcap={endcap_style}"

            source_geom_ref = f'"{self.task.param_source_schema}"."{self.task.param_source_table}"."{geom_field}"'

            where_clause = ""
            if source_subset:
                where_clause = f" WHERE {source_subset}"

            sql_drop = f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."fm_temp_mv_{mv_name}_dump" CASCADE;'
            sql_drop_main = f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."fm_temp_mv_{mv_name}" CASCADE;'

            sql_create_main = f'''
                CREATE MATERIALIZED VIEW IF NOT EXISTS "{schema}"."fm_temp_mv_{mv_name}" AS
                SELECT
                    "{self.task.param_source_table}"."{self.task.primary_key_name}",
                    ST_Buffer({source_geom_ref}, {buffer_expr}, '{style_params}') as {geom_field}
                FROM "{self.task.param_source_schema}"."{self.task.param_source_table}"
                {where_clause}
                WITH DATA;
            '''

            sql_create_dump = f'''
                CREATE MATERIALIZED VIEW IF NOT EXISTS "{schema}"."fm_temp_mv_{mv_name}_dump" AS
                SELECT ST_Union("{geom_field}") as {geom_field}
                FROM "{schema}"."fm_temp_mv_{mv_name}"
                WITH DATA;
            '''

            sql_index = f'CREATE INDEX IF NOT EXISTS idx_{mv_name}_geom ON "{schema}"."fm_temp_mv_{mv_name}" USING GIST ({geom_field});'

            schema = self.ensure_temp_schema_exists(connexion, schema)

            commands = [sql_drop, sql_drop_main, sql_create_main, sql_index, sql_create_dump]
            self.execute_commands(connexion, commands)

            # FIX v4.2.8: Register MV references
            from ....adapters.backends.postgresql.mv_reference_tracker import get_mv_reference_tracker
            tracker = get_mv_reference_tracker()

            if self.task.source_layer:
                tracker.add_reference(f"fm_temp_mv_{mv_name}", self.task.source_layer.id())
                tracker.add_reference(f"fm_temp_mv_{mv_name}_dump", self.task.source_layer.id())

            if hasattr(self.task, 'param_all_layers'):
                for layer in self.task.param_all_layers:
                    if layer and hasattr(layer, 'id') and layer.id() != (self.task.source_layer.id() if self.task.source_layer else None):
                        tracker.add_reference(f"fm_temp_mv_{mv_name}", layer.id())
                        tracker.add_reference(f"fm_temp_mv_{mv_name}_dump", layer.id())

            elapsed = time.time() - start_time
            logger.info(f"FIX v4.2.1: Buffer expression MVs created in {elapsed:.2f}s")
            logger.info(f"   fm_temp_mv_{mv_name} and fm_temp_mv_{mv_name}_dump ready for distant layer filtering")

            return True

        except Exception as e:
            logger.error(f"Failed to create buffer expression MV: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return False

    def try_create_filter_chain_mv(self):
        """
        v4.2.10b: DISABLED - Filter chain MV optimization.
        Feature temporarily disabled to prevent blocking on large datasets.
        """
        logger.info("=" * 60)
        logger.info("v4.2.10b: Filter chain MV optimization DISABLED")
        logger.info("   Feature temporarily disabled to prevent blocking")
        logger.info("   Will be re-enabled with timeout protection")
        logger.info("=" * 60)
        return False

    def create_simple_mv_sql(self, schema, name, sql_subset_string):
        """Delegated to BackendServices facade."""
        return _backend_services.create_simple_materialized_view_sql(schema, name, sql_subset_string)

    def create_custom_buffer_view_sql(self, schema, name, geom_key_name, where_clause_fields_arr, last_subset_id, sql_subset_string):
        """
        Create SQL for custom buffer materialized view.

        Args:
            schema: PostgreSQL schema name
            name: Layer identifier
            geom_key_name: Geometry field name
            where_clause_fields_arr: List of WHERE clause fields
            last_subset_id: Previous subset ID (None if first)
            sql_subset_string: SQL SELECT statement for source

        Returns:
            str: SQL CREATE MATERIALIZED VIEW statement
        """
        postgresql_source_geom = self.task.postgresql_source_geom
        if self.task.has_to_reproject_source_layer:
            postgresql_source_geom = f'ST_Transform({postgresql_source_geom}, {self.task.source_layer_crs_authid.split(":")[1]})'

        buffer_type_mapping = {"Round": "round", "Flat": "flat", "Square": "square"}
        buffer_type_str = self.task.task_parameters["filtering"].get("buffer_type", "Round")
        endcap_style = buffer_type_mapping.get(buffer_type_str, "round")
        quad_segs = self.task.param_buffer_segments

        style_params = f"quad_segs={quad_segs}"
        if endcap_style != 'round':
            style_params += f" endcap={endcap_style}"

        # FIX v4.2.8: Use source layer subset for buffer MV filtering
        source_filter_for_mv = sql_subset_string
        if self.task.source_layer and self.task.source_layer.subsetString():
            source_subset = self.task.source_layer.subsetString()
            logger.info(f"Buffer MV: Using source layer subset for filtering")
            logger.info(f"   Source subset preview: {source_subset[:200]}...")

            if 'SELECT' in source_subset.upper():
                source_filter_for_mv = source_subset
                logger.info(f"   Using source layer SELECT statement for buffer MV")
            else:
                source_filter_for_mv = (
                    f'(SELECT "{self.task.param_source_table}"."{self.task.primary_key_name}" '
                    f'FROM "{self.task.param_source_schema}"."{self.task.param_source_table}" '
                    f'WHERE {source_subset})'
                )
                logger.info(f"   Wrapped source WHERE clause in SELECT for buffer MV")
        else:
            logger.debug(f"   Buffer MV: No source layer subset, using sql_subset_string")

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
            postgresql_source_geom=postgresql_source_geom,
            geometry_field=geom_key_name,
            schema_source=self.task.param_source_schema,
            primary_key_name=self.task.primary_key_name,
            table_source=self.task.param_source_table,
            where_clause_fields=','.join(where_clause_fields_arr).replace('mv_', ''),
            param_buffer_expression=self.task.param_buffer.replace('mv_', ''),
            source_new_subset=source_filter_for_mv,
            where_expression=' OR '.join(self.task._parse_where_clauses()).replace('mv_', ''),
            style_params=style_params
        )

    # ── Filter/Reset Actions ────────────────────────────────────────────

    def filter_action(self, layer, sql_subset_string, primary_key_name, geom_key_name, name, custom, cur, conn, seq_order):
        """
        Execute filter action using PostgreSQL backend.

        EPIC-1 Phase E5/E6: Delegates to adapters.backends.postgresql.filter_actions.

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

        Returns:
            bool: True if successful
        """
        if PG_EXECUTOR_AVAILABLE and pg_execute_filter:
            return pg_execute_filter(
                layer=layer,
                sql_subset_string=sql_subset_string,
                primary_key_name=primary_key_name,
                geom_key_name=geom_key_name,
                name=name,
                custom=custom,
                cur=cur,
                conn=conn,
                seq_order=seq_order,
                # Callback functions - handler methods
                queue_subset_fn=self.task._queue_subset_string,
                get_connection_fn=self.get_valid_connection,
                ensure_stats_fn=self.ensure_source_table_stats,
                extract_where_fn=self.extract_where_clause,
                insert_history_fn=self.insert_subset_history,
                get_session_name_fn=self.task._get_session_prefixed_name,
                ensure_schema_fn=self.ensure_temp_schema_exists,
                execute_commands_fn=self.execute_commands,
                create_simple_mv_fn=self.create_simple_mv_sql,
                create_custom_mv_fn=self.create_custom_buffer_view_sql,
                parse_where_clauses_fn=self.task._parse_where_clauses,
                # Context parameters
                source_schema=self.task.param_source_schema,
                source_table=self.task.param_source_table,
                source_geom=self.task.param_source_geom,
                current_mv_schema=self.task.current_materialized_view_schema,
                project_uuid=self.task.project_uuid,
                session_id=self.task.session_id,
                param_buffer_expression=getattr(self.task, 'param_buffer_expression', None)
            )

        error_msg = (
            "PostgreSQL filter_actions module not available. "
            "This indicates a critical installation issue."
        )
        logger.error(error_msg)
        raise ImportError(error_msg)

    def reset_action(self, layer, name, cur, conn):
        """
        Execute reset action using PostgreSQL backend.

        Args:
            layer: QgsVectorLayer to reset
            name: Layer identifier
            cur: Database cursor
            conn: Database connection

        Returns:
            bool: True if successful
        """
        if PG_EXECUTOR_AVAILABLE and pg_execute_reset:
            delete_history_fn = None
            if self.task._ps_manager:
                delete_history_fn = self.task._ps_manager.delete_subset_history

            return pg_execute_reset(
                layer=layer,
                name=name,
                cur=cur,
                conn=conn,
                queue_subset_fn=self.task._queue_subset_string,
                get_connection_fn=self.get_valid_connection,
                execute_commands_fn=self.execute_commands,
                get_session_name_fn=self.task._get_session_prefixed_name,
                delete_history_fn=delete_history_fn,
                project_uuid=self.task.project_uuid,
                current_mv_schema=self.task.current_materialized_view_schema
            )

        error_msg = "PostgreSQL filter_actions module not available"
        logger.error(error_msg)
        raise ImportError(error_msg)

    def extract_where_clause(self, sql_select):
        """
        Extract WHERE clause from a SQL SELECT statement.
        """
        from ..builders.subset_string_builder import SubsetStringBuilder
        _, where_clause = SubsetStringBuilder.extract_where_clause(sql_select)
        return where_clause

    def insert_subset_history(self, cur, conn, layer, sql_subset_string, seq_order):
        """
        Insert subset history record into database.

        Args:
            cur: Database cursor
            conn: Database connection
            layer: QgsVectorLayer
            sql_subset_string: SQL subset string
            seq_order: Sequence order number
        """
        # Initialize prepared statements manager if needed
        if not self.task._ps_manager:
            provider_type = 'spatialite'
            if hasattr(conn, 'get_backend_pid'):
                provider_type = 'postgresql'
            self.task._ps_manager = create_prepared_statements(conn, provider_type)

        # Use prepared statement if available
        if self.task._ps_manager:
            try:
                return self.task._ps_manager.insert_subset_history(
                    history_id=str(uuid.uuid4()),
                    project_uuid=self.task.project_uuid,
                    layer_id=layer.id(),
                    source_layer_id=self.task.source_layer.id(),
                    seq_order=seq_order,
                    subset_string=sql_subset_string
                )
            except Exception as e:
                logger.warning(f"Prepared statement failed, falling back to repository: {e}")

        # Fallback: Use centralized HistoryRepository
        history_repo = HistoryRepository(conn, cur)
        try:
            source_layer_id = self.task.source_layer.id() if self.task.source_layer else ''
            return history_repo.insert(
                project_uuid=self.task.project_uuid,
                layer_id=layer.id(),
                subset_string=sql_subset_string,
                seq_order=seq_order,
                source_layer_id=source_layer_id
            )
        finally:
            history_repo.close()

    # ── Cleanup ─────────────────────────────────────────────────────────

    def cleanup_session_mvs(self, connexion, schema_name):
        """
        Clean up all materialized views for the current session.
        """
        if PG_EXECUTOR_AVAILABLE and pg_executor:
            return pg_executor.cleanup_session_materialized_views(
                connexion, schema_name, self.task.session_id
            )
        return _backend_services.cleanup_session_materialized_views(connexion, schema_name, self.task.session_id)

    def cleanup_orphaned_mvs(self, connexion, schema_name, max_age_hours=24):
        """
        Clean up orphaned materialized views older than max_age_hours.
        """
        return _backend_services.cleanup_orphaned_materialized_views(connexion, schema_name, self.task.session_id, max_age_hours)

    def cleanup_materialized_views(self):
        """
        Cleanup PostgreSQL materialized views created during filtering.
        Uses reference tracker to prevent premature MV cleanup.
        """
        if not POSTGRESQL_AVAILABLE:
            return

        try:
            if self.task.param_source_provider_type != 'postgresql':
                return

            from ....adapters.backends.postgresql.mv_reference_tracker import get_mv_reference_tracker

            layer_ids = []

            if hasattr(self.task, 'source_layer') and self.task.source_layer:
                layer_ids.append(self.task.source_layer.id())
            elif 'source_layer' in self.task.task_parameters:
                source_layer = self.task.task_parameters['source_layer']
                if source_layer:
                    layer_ids.append(source_layer.id())

            if hasattr(self.task, 'param_all_layers'):
                for layer in self.task.param_all_layers:
                    if layer and hasattr(layer, 'id'):
                        layer_ids.append(layer.id())

            if not layer_ids:
                logger.debug("No layer IDs available for PostgreSQL MV cleanup")
                return

            tracker = get_mv_reference_tracker()
            mvs_to_drop = set()

            for layer_id in layer_ids:
                can_drop = tracker.remove_all_references_for_layer(layer_id)
                mvs_to_drop.update(can_drop)

            if not mvs_to_drop:
                logger.debug(
                    f"PostgreSQL MV cleanup: All MVs still referenced by other layers "
                    f"(removed references for {len(layer_ids)} layer(s))"
                )
                return

            logger.info(
                f"PostgreSQL MV cleanup: Dropping {len(mvs_to_drop)} MV(s) "
                f"with no remaining references"
            )

            connexion = self.get_valid_connection()
            if not connexion:
                logger.warning("No PostgreSQL connection for MV cleanup")
                return

            cursor = connexion.cursor()
            schema = getattr(self.task, 'current_materialized_view_schema', 'filtermate_temp')

            for mv_name in mvs_to_drop:
                try:
                    if '.' in mv_name:
                        mv_name = mv_name.split('.')[-1].strip('"')

                    drop_sql = f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."{mv_name}" CASCADE;'
                    cursor.execute(drop_sql)
                    logger.debug(f"Dropped MV: {schema}.{mv_name}")
                except Exception as e:
                    logger.warning(f"Failed to drop MV {mv_name}: {e}")

            connexion.commit()
            logger.debug(f"PostgreSQL MV cleanup completed: dropped {len(mvs_to_drop)} MV(s)")

        except Exception as e:
            logger.debug(f"Error during PostgreSQL MV cleanup: {e}")

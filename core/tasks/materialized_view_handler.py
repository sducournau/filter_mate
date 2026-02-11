"""
Materialized View Handler for FilterEngineTask

Manages PostgreSQL materialized view lifecycle during filtering operations:
- Source MV creation with pre-computed buffer (v2.9.0 optimization)
- Buffer expression MV creation (v4.2.1 fix)
- Filter chain MV optimization (v4.2.10, currently disabled)
- Thin delegation to CleanupHandler for schema/command utilities

Extracted from FilterEngineTask as part of Pass 3 god-class decomposition.

Location: core/tasks/materialized_view_handler.py (Hexagonal Architecture - Application Layer)

Thread Safety:
    All methods interact only with PostgreSQL connections (not QGIS layer objects
    directly), so they are safe to call from worker threads.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from ...infrastructure.logging import setup_logger
from ...config.config import ENV_VARS

# Setup logger
logger = setup_logger(
    'FilterMate.Tasks.MaterializedView',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_tasks.log'),
    level=logging.INFO
)


class MaterializedViewHandler:
    """Handles PostgreSQL materialized view creation and lifecycle.

    This class encapsulates all MV creation operations previously embedded
    in FilterEngineTask. It receives the task reference for accessing state
    and delegates utility operations to CleanupHandler.

    Attributes:
        task: Reference to the parent FilterEngineTask for state access.
        cleanup_handler: CleanupHandler for schema/command utilities.

    Example:
        >>> handler = MaterializedViewHandler(task)
        >>> handler.create_source_mv_if_needed(source_mv_info)
    """

    def __init__(self, task):
        """Initialize MaterializedViewHandler.

        Args:
            task: FilterEngineTask instance providing access to task state
                  (source_layer, session_id, task_parameters, etc.)
        """
        self.task = task

    # =========================================================================
    # Source MV Creation (v2.9.0 optimization)
    # =========================================================================

    def create_source_mv_if_needed(self, source_mv_info):
        """Create source materialized view with pre-computed buffer (v2.9.0 optimization).

        Args:
            source_mv_info: Object with create_sql, schema, view_name, fid_list attributes.

        Returns:
            bool: True if MV was created successfully, False otherwise.
        """
        if not source_mv_info or not source_mv_info.create_sql:
            return False

        try:
            import time
            start_time = time.time()

            connexion = self.task._get_valid_postgresql_connection()
            if not connexion:
                logger.warning("No PostgreSQL connection available for source MV creation")
                return False

            # Build commands: drop if exists, create, add spatial index
            schema = source_mv_info.schema
            view_name = source_mv_info.view_name

            commands = [
                f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."{view_name}" CASCADE;',
                source_mv_info.create_sql,
                f'CREATE INDEX IF NOT EXISTS idx_{view_name}_geom ON "{schema}"."{view_name}" USING GIST (geom);',
                f'CREATE INDEX IF NOT EXISTS idx_{view_name}_buff ON "{schema}"."{view_name}" USING GIST (geom_buffered);',
                f'ANALYZE "{schema}"."{view_name}";'
            ]

            self.task._cleanup_handler.execute_postgresql_commands(
                connexion, commands,
                source_layer=self.task.source_layer,
                psycopg2_module=self._get_psycopg2(),
                get_datasource_connexion_fn=self._get_datasource_connexion_fn(),
            )

            # Register MV references to prevent premature cleanup
            from ...adapters.backends.postgresql.mv_reference_tracker import get_mv_reference_tracker
            tracker = get_mv_reference_tracker()

            # Register references for source layer and all distant layers
            if hasattr(self.task, 'source_layer') and self.task.source_layer:
                tracker.add_reference(view_name, self.task.source_layer.id())

            # Register for all distant layers that will use this source MV
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
            logger.info("   FIX v4.2.8: Registered references for multiple layers")
            return True

        except (RuntimeError, OSError, AttributeError, ImportError) as e:
            logger.warning(f"Failed to create source MV '{source_mv_info.view_name}': {e}")
            # Don't raise - the optimization can still work with inline subquery
            return False

    # =========================================================================
    # Buffer Expression MV (v4.2.1 fix)
    # =========================================================================

    def ensure_buffer_expression_mv_exists(self):
        """Ensure buffer expression MVs exist BEFORE distant layer filtering.

        FIX v4.2.1 (2026-01-21): Create MVs upfront in manage_distant_layers_geometric_filtering().
        FIX v4.2.7 (2026-01-22): Only create MVs if feature count exceeds threshold.

        When using custom buffer expression (set to field), this creates the
        materialized views (mv_<session>_<table>_buffer_expr and mv_<session>_<table>_buffer_expr_dump)
        BEFORE prepare_postgresql_source_geom() generates references to them.

        Returns:
            bool: True if MVs created or not needed, False on error.
        """
        import time
        from ...infrastructure.database.sql_utils import sanitize_sql_identifier
        from ...adapters.backends.postgresql.filter_executor import BUFFER_EXPR_MV_THRESHOLD

        logger.info("=" * 60)
        logger.info("FIX v4.2.1/v4.2.7: Checking buffer expression MV requirements...")
        logger.info(f"   param_buffer_expression: {self.task.param_buffer_expression}")
        logger.info(f"   session_id: {self.task.session_id}")
        logger.info(f"   source_table: {self.task.param_source_table}")

        # Use cached feature count for consistent threshold decisions
        source_feature_count = getattr(self.task, '_cached_source_feature_count', None)
        if source_feature_count is None:
            # Fallback if not cached (should not happen in normal flow)
            source_feature_count = self.task.source_layer.featureCount() if self.task.source_layer else 0
            logger.warning(f"   Using fresh featureCount (not cached): {source_feature_count}")
        logger.info(f"   source_feature_count: {source_feature_count}")
        logger.info(f"   BUFFER_EXPR_MV_THRESHOLD: {BUFFER_EXPR_MV_THRESHOLD}")

        if source_feature_count is not None and source_feature_count <= BUFFER_EXPR_MV_THRESHOLD:
            logger.info(f"   SKIP MV creation: {source_feature_count} features <= {BUFFER_EXPR_MV_THRESHOLD} threshold")
            logger.info("   -> prepare_postgresql_source_geom() will use INLINE ST_Buffer() instead")
            logger.info("=" * 60)
            return True  # Success - no MV needed

        logger.info(f"   -> Creating MV: {source_feature_count} features > {BUFFER_EXPR_MV_THRESHOLD} threshold")
        logger.info("=" * 60)

        start_time = time.time()

        try:
            # Get PostgreSQL connection
            connexion = self.task._get_valid_postgresql_connection()
            if not connexion:
                logger.warning("No PostgreSQL connection available for buffer expression MV creation")
                return False

            # Generate MV name (must match prepare_postgresql_source_geom logic)
            base_mv_name = sanitize_sql_identifier(self.task.param_source_table + '_buffer_expr')
            if self.task.session_id:
                mv_name = f"{self.task.session_id}_{base_mv_name}"
            else:
                mv_name = base_mv_name
                logger.warning("No session_id - using base MV name (may conflict with other sessions)")

            schema = self.task.current_materialized_view_schema
            geom_field = self.task.param_source_geom

            # Get source layer's current subset (the features to include in MV)
            source_subset = self.task.source_layer.subsetString() if self.task.source_layer else ""

            # Build the buffer expression for PostGIS
            buffer_expr = self.task.param_buffer_expression
            if buffer_expr:
                # Convert QGIS expression to PostGIS
                buffer_expr = self.task.qgis_expression_to_postgis(buffer_expr)
                # Adjust field references to include table name
                if buffer_expr.find('"') == 0 and self.task.param_source_table not in buffer_expr[:50]:
                    buffer_expr = f'"{self.task.param_source_table}".' + buffer_expr

            # Build ST_Buffer style parameters
            buffer_type_mapping = {"Round": "round", "Flat": "flat", "Square": "square"}
            buffer_type_str = self.task.task_parameters.get("filtering", {}).get("buffer_type", "Round")
            endcap_style = buffer_type_mapping.get(buffer_type_str, "round")
            quad_segs = getattr(self.task, 'param_buffer_segments', 5)
            style_params = f"quad_segs={quad_segs}"
            if endcap_style != 'round':
                style_params += f" endcap={endcap_style}"

            # Build source geometry reference
            source_geom_ref = f'"{self.task.param_source_schema}"."{self.task.param_source_table}"."{geom_field}"'

            # Build WHERE clause for source features
            where_clause = f" WHERE {source_subset}" if source_subset else ""

            # SQL commands (fm_temp_mv_ prefix)
            sql_drop = f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."fm_temp_mv_{mv_name}_dump" CASCADE;'
            sql_drop_main = f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."fm_temp_mv_{mv_name}" CASCADE;'

            # Create main MV with buffered geometries
            # DDL: mv_name is sanitized via sanitize_sql_identifier, other identifiers from QGIS layer metadata
            sql_create_main = (
                f'CREATE MATERIALIZED VIEW IF NOT EXISTS "{schema}"."fm_temp_mv_{mv_name}" AS '  # nosec B608
                f'SELECT "{self.task.param_source_table}"."{self.task.primary_key_name}", '
                f'ST_Buffer({source_geom_ref}, {buffer_expr}, \'{style_params}\') as {geom_field} '
                f'FROM "{self.task.param_source_schema}"."{self.task.param_source_table}" '
                f'{where_clause} WITH DATA;'
            )

            # Create dump MV (union of all buffered geometries)
            sql_create_dump = (
                f'CREATE MATERIALIZED VIEW IF NOT EXISTS "{schema}"."fm_temp_mv_{mv_name}_dump" AS '  # nosec B608
                f'SELECT ST_Union("{geom_field}") as {geom_field} '
                f'FROM "{schema}"."fm_temp_mv_{mv_name}" WITH DATA;'
            )

            # Index for main MV
            sql_index = f'CREATE INDEX IF NOT EXISTS idx_{mv_name}_geom ON "{schema}"."fm_temp_mv_{mv_name}" USING GIST ({geom_field});'

            # Ensure temp schema exists
            schema = self._ensure_temp_schema_exists(connexion, schema)

            # Execute commands
            commands = [sql_drop, sql_drop_main, sql_create_main, sql_index, sql_create_dump]
            self._execute_postgresql_commands(connexion, commands)

            # Register MV references to prevent premature cleanup
            from ...adapters.backends.postgresql.mv_reference_tracker import get_mv_reference_tracker
            tracker = get_mv_reference_tracker()

            # Register references for source layer and all distant layers (fm_temp_mv_ prefix)
            if self.task.source_layer:
                tracker.add_reference(f"fm_temp_mv_{mv_name}", self.task.source_layer.id())
                tracker.add_reference(f"fm_temp_mv_{mv_name}_dump", self.task.source_layer.id())

            # Register for all distant layers that will use this MV
            if hasattr(self.task, 'param_all_layers'):
                for layer in self.task.param_all_layers:
                    if layer and hasattr(layer, 'id') and layer.id() != (self.task.source_layer.id() if self.task.source_layer else None):
                        tracker.add_reference(f"fm_temp_mv_{mv_name}", layer.id())
                        tracker.add_reference(f"fm_temp_mv_{mv_name}_dump", layer.id())

            elapsed = time.time() - start_time
            logger.info(f"FIX v4.2.1: Buffer expression MVs created in {elapsed:.2f}s")
            logger.info(f"   fm_temp_mv_{mv_name} and fm_temp_mv_{mv_name}_dump ready for distant layer filtering")
            logger.info(f"   FIX v4.2.8: Registered references for {len(self.task.param_all_layers) if hasattr(self.task, 'param_all_layers') else 1} layer(s)")

            return True

        except (RuntimeError, OSError, AttributeError, ImportError, ValueError) as e:
            logger.error(f"Failed to create buffer expression MV: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            # Don't raise - let the original code path try
            return False

    # =========================================================================
    # Filter Chain MV (v4.2.10 - DISABLED)
    # =========================================================================

    def try_create_filter_chain_mv(self):
        """Try to create optimized MV for filter chaining.

        v4.2.10b: DISABLED - Feature causes blocking on large datasets.
        Will be re-enabled after adding:
        - Query timeout protection
        - Feature count threshold for spatial_filters tables
        - Configuration option to enable/disable

        Returns:
            bool: Always False (feature disabled).
        """
        # DISABLED - Causes task blocking at 14%
        # The MV creation with complex EXISTS subqueries can take very long on large tables
        # without proper indexes. Need to add timeout and better threshold checks.
        logger.info("=" * 60)
        logger.info("v4.2.10b: Filter chain MV optimization DISABLED")
        logger.info("   -> Feature temporarily disabled to prevent blocking")
        logger.info("   -> Will be re-enabled with timeout protection")
        logger.info("=" * 60)
        return False

        # Original code below - keep for reference
        """
        import time

        logger.info("=" * 60)
        logger.info("v4.2.10: Checking filter chain MV optimization...")

        # Check prerequisites
        source_subset = self.task.source_layer.subsetString() if self.task.source_layer else ""
        if not source_subset:
            logger.info("   No source subset - skipping filter chain optimization")
            logger.info("=" * 60)
            return False

        # Check if source_subset contains EXISTS clauses
        if 'EXISTS' not in source_subset.upper():
            logger.info("   No EXISTS in source subset - skipping filter chain optimization")
            logger.info("=" * 60)
            return False

        # Check if we're adding another spatial filter
        has_buffer = bool(self.task.param_buffer_expression or self.task.param_buffer_value)
        if not has_buffer:
            logger.info("   No buffer expression - filter chain MV not needed")
            logger.info("=" * 60)
            return False

        logger.info("   Prerequisites met for filter chain optimization:")
        logger.info("      - source_subset contains EXISTS")
        logger.info(f"      - buffer_expression/value: {self.task.param_buffer_expression or self.task.param_buffer_value}")

        start_time = time.time()

        try:
            # Import filter chain optimizer
            from ...adapters.backends.postgresql.filter_chain_optimizer import (
                FilterChainOptimizer,
                FilterChainContext,
                OptimizationStrategy
            )
            from ..filter.expression_combiner import extract_exists_clauses

            # Extract spatial filters from source_subset
            exists_clauses = extract_exists_clauses(source_subset)
            if len(exists_clauses) < 1:
                logger.info("   Could not extract EXISTS clauses from source subset")
                logger.info("=" * 60)
                return False

            # Build spatial_filters list from extracted EXISTS
            spatial_filters = []
            for clause in exists_clauses:
                spatial_filters.append({
                    'table': clause.get('table', 'unknown'),
                    'schema': clause.get('schema', 'public'),
                    'geom_column': 'geom',  # Default
                    'predicate': 'ST_Intersects',
                    'sql': clause.get('sql')  # Original SQL for reference
                })

            # Add current source layer as another filter (with buffer)
            buffer_val = self.task.param_buffer_value
            if self.task.param_buffer_expression:
                # For expression buffers, use average estimate
                buffer_val = 10.0  # Placeholder, actual value from expression

            spatial_filters.append({
                'table': self.task.param_source_table,
                'schema': self.task.param_source_schema,
                'geom_column': self.task.param_source_geom,
                'predicate': 'ST_Intersects',
                'buffer': buffer_val
            })

            logger.info(f"   -> Detected {len(spatial_filters)} spatial filters to chain:")
            for i, f in enumerate(spatial_filters):
                buf_str = f" (buffer={f.get('buffer')})" if f.get('buffer') else ""
                logger.info(f"      {i+1}. {f.get('schema')}.{f.get('table')}{buf_str}")

            # Get PostgreSQL connection
            connexion = self.task._get_valid_postgresql_connection()
            if not connexion:
                logger.warning("   No PostgreSQL connection for filter chain MV")
                logger.info("=" * 60)
                return False

            # Create filter chain context
            context = FilterChainContext(
                source_schema=self.task.param_source_schema,
                source_table=self.task.param_source_table,
                source_geom_column=self.task.param_source_geom,
                spatial_filters=spatial_filters,
                buffer_value=self.task.param_buffer_value,
                buffer_expression=self.task.param_buffer_expression,
                feature_count_estimate=getattr(self.task, '_cached_source_feature_count', 0),
                session_id=self.task.session_id
            )

            # Create optimizer and analyze
            optimizer = FilterChainOptimizer(connexion, self.task.session_id)
            strategy = optimizer.analyze_chain(context)

            if strategy == OptimizationStrategy.NONE:
                logger.info("   Optimizer recommends no MV (strategy=NONE)")
                logger.info("=" * 60)
                return False

            # Create chain MV
            mv_name = optimizer.create_chain_mv(context, strategy)

            if mv_name:
                elapsed = time.time() - start_time
                logger.info(f"   Filter chain MV created: {mv_name}")
                logger.info(f"   Strategy: {strategy.value}")
                logger.info(f"   Time: {elapsed:.2f}s")

                # Store for use by expression builders
                self.task._filter_chain_mv_name = mv_name
                self.task._filter_chain_optimizer = optimizer
                self.task._filter_chain_context = context

                # Inject MV name into task_parameters for ExpressionBuilder access
                self.task.task_parameters['_filter_chain_mv_name'] = mv_name
                logger.info("   Injected _filter_chain_mv_name into task_parameters")

                logger.info("=" * 60)
                return True
            else:
                logger.warning("   MV creation failed")
                logger.info("=" * 60)
                return False

        except ImportError as e:
            logger.debug(f"   Filter chain optimizer not available: {e}")
            logger.info("=" * 60)
            return False
        except Exception as e:
            logger.warning(f"   Filter chain optimization failed: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            logger.info("=" * 60)
            return False
        """  # End of disabled code block

    # =========================================================================
    # Delegation to CleanupHandler (thin wrappers for backward compat)
    # =========================================================================

    def create_simple_materialized_view_sql(self, schema: str, name: str, sql_subset_string: str) -> str:
        """Create simple MV SQL. Delegates to CleanupHandler."""
        return self.task._cleanup_handler.create_simple_materialized_view_sql(schema, name, sql_subset_string)

    def parse_where_clauses(self) -> Any:
        """Parse WHERE clauses. Delegates to CleanupHandler."""
        return self.task._cleanup_handler.parse_where_clauses(self.task.where_clause)

    def create_custom_buffer_view_sql(self, schema, name, geom_key_name, where_clause_fields_arr, last_subset_id, sql_subset_string):
        """Create SQL for custom buffer MV. Delegates to CleanupHandler."""
        return self.task._cleanup_handler.create_custom_buffer_view_sql(
            schema=schema, name=name, geom_key_name=geom_key_name,
            where_clause_fields_arr=where_clause_fields_arr,
            last_subset_id=last_subset_id, sql_subset_string=sql_subset_string,
            postgresql_source_geom=self.task.postgresql_source_geom,
            has_to_reproject_source_layer=self.task.has_to_reproject_source_layer,
            source_layer_crs_authid=self.task.source_layer_crs_authid,
            task_parameters=self.task.task_parameters,
            param_buffer_segments=self.task.param_buffer_segments,
            param_source_schema=self.task.param_source_schema,
            param_source_table=self.task.param_source_table,
            primary_key_name=self.task.primary_key_name,
            source_layer=self.task.source_layer,
            param_buffer=self.task.param_buffer,
            where_clause=self.task.where_clause,
        )

    def ensure_temp_schema_exists(self, connexion, schema_name):
        """Ensure temp schema exists in PostgreSQL. Delegates to CleanupHandler."""
        result = self.task._cleanup_handler.ensure_temp_schema_exists(connexion, schema_name)
        if result == 'public' and schema_name != 'public':
            self.task._last_schema_error = f"Using 'public' schema as fallback (could not create '{schema_name}')"
        return result

    def get_session_prefixed_name(self, base_name: str) -> str:
        """Generate a session-unique MV name. Delegates to CleanupHandler."""
        return self.task._cleanup_handler.get_session_prefixed_name(base_name, self.task.session_id)

    def cleanup_session_materialized_views(self, connexion: Any, schema_name: str) -> Any:
        """Clean up session MVs. Delegates to CleanupHandler."""
        from ..ports.backend_services import get_backend_services
        _backend_services = get_backend_services()
        _pg_executor = _backend_services.get_postgresql_executor()
        _pg_executor_available = _pg_executor is not None
        return self.task._cleanup_handler.cleanup_session_materialized_views(
            connexion, schema_name, self.task.session_id,
            pg_executor=_pg_executor, pg_executor_available=_pg_executor_available,
        )

    def cleanup_orphaned_materialized_views(self, connexion: Any, schema_name: str, max_age_hours: int = 24) -> Any:
        """Clean up orphaned MVs. Delegates to CleanupHandler."""
        return self.task._cleanup_handler.cleanup_orphaned_materialized_views(
            connexion, schema_name, self.task.session_id, max_age_hours
        )

    def execute_postgresql_commands(self, connexion: Any, commands: List[str]) -> bool:
        """Execute PostgreSQL commands with reconnection. Delegates to CleanupHandler."""
        return self.task._cleanup_handler.execute_postgresql_commands(
            connexion, commands,
            source_layer=self.task.source_layer,
            psycopg2_module=self._get_psycopg2(),
            get_datasource_connexion_fn=self._get_datasource_connexion_fn(),
        )

    def ensure_source_table_stats(self, connexion: Any, schema: str, table: str, geom_field: str) -> bool:
        """Ensure PostgreSQL statistics exist. Delegates to CleanupHandler."""
        return self.task._cleanup_handler.ensure_source_table_stats(connexion, schema, table, geom_field)

    def cleanup_postgresql_materialized_views(self):
        """Cleanup PostgreSQL materialized views. Delegates to CleanupHandler."""
        from ...infrastructure.constants import PROVIDER_POSTGRES
        from ..ports.backend_services import get_backend_services
        _backend_services = get_backend_services()
        _pg_availability = _backend_services.get_postgresql_availability()
        _postgresql_available = _pg_availability.postgresql_available

        self.task._cleanup_handler.cleanup_postgresql_materialized_views(
            postgresql_available=_postgresql_available,
            source_provider_type=self.task.param_source_provider_type,
            source_layer=getattr(self.task, 'source_layer', None),
            task_parameters=self.task.task_parameters,
            param_all_layers=getattr(self.task, 'param_all_layers', None),
            get_connection_fn=self.task._get_valid_postgresql_connection,
            current_mv_schema=getattr(self.task, 'current_materialized_view_schema', 'filtermate_temp'),
        )

    # =========================================================================
    # Internal helpers
    # =========================================================================

    def _get_psycopg2(self):
        """Get psycopg2 module via backend services facade."""
        from ..ports.backend_services import get_backend_services
        _backend_services = get_backend_services()
        return _backend_services.get_postgresql_availability().psycopg2

    def _get_datasource_connexion_fn(self):
        """Get the datasource connection function."""
        from ...infrastructure.utils import get_datasource_connexion_from_layer
        return get_datasource_connexion_from_layer

    def _ensure_temp_schema_exists(self, connexion, schema_name):
        """Internal: ensure temp schema exists (used by ensure_buffer_expression_mv_exists)."""
        return self.ensure_temp_schema_exists(connexion, schema_name)

    def _execute_postgresql_commands(self, connexion, commands):
        """Internal: execute postgresql commands (used by ensure_buffer_expression_mv_exists)."""
        return self.execute_postgresql_commands(connexion, commands)

"""
Spatial Query Handler for FilterEngineTask

Centralizes spatial query building methods that construct SQL queries for
geometric filtering operations across PostgreSQL and OGR backends.

Methods in this handler:
- Build spatial JOIN queries for PostGIS
- Apply SQL set operators (UNION, INTERSECT, EXCEPT)
- Build complete PostGIS filter expressions
- Execute OGR spatial selection (via ogr_executor)
- Build OGR filter from spatial selection results
- Determine source reference (MV vs direct table)

Extracted from FilterEngineTask as part of Pass 3 god-class decomposition.

Location: core/tasks/spatial_query_handler.py (Hexagonal Architecture - Application Layer)

Thread Safety:
    All methods are safe for worker threads. PostgreSQL methods use SQL string
    construction only (no direct layer access). OGR methods delegate to
    ogr_executor which handles its own safety.
"""

import logging
import os

from ...infrastructure.logging import setup_logger
from ...config.config import ENV_VARS

# Setup logger
logger = setup_logger(
    'FilterMate.Tasks.SpatialQuery',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_tasks.log'),
    level=logging.INFO
)

# Lazy load backend executors
from ..ports.backend_services import get_backend_services
_backend_services = get_backend_services()
pg_executor = _backend_services.get_postgresql_executor()
PG_EXECUTOR_AVAILABLE = pg_executor is not None
ogr_executor = _backend_services.get_ogr_executor()
OGR_EXECUTOR_AVAILABLE = ogr_executor is not None


class SpatialQueryHandler:
    """Handles spatial query construction for geometric filtering.

    This class encapsulates all spatial query building methods previously
    embedded in FilterEngineTask. Each method either delegates to a backend
    executor (pg_executor, ogr_executor) or provides a minimal fallback.

    Attributes:
        task: Reference to the parent FilterEngineTask for state access.

    Example:
        >>> handler = SpatialQueryHandler(task)
        >>> expr, sub = handler.build_postgis_filter_expression(
        ...     layer_props, spatial_predicate, sub_expr, old_subset, 'INTERSECT'
        ... )
    """

    def __init__(self, task):
        """Initialize SpatialQueryHandler.

        Args:
            task: FilterEngineTask instance providing access to task state
                  (current_materialized_view_name, param_source_schema, etc.)
        """
        self.task = task

    # =========================================================================
    # Source reference resolution
    # =========================================================================

    def get_source_reference(self, sub_expression):
        """Determine the source reference for spatial joins (MV or direct table).

        When a materialized view exists for the source layer, uses the MV dump
        view (pre-computed union of geometries). Otherwise, uses the original
        sub_expression (typically a direct table reference or subquery).

        Args:
            sub_expression: Default source expression (table reference or subquery).

        Returns:
            str: SQL reference to use as source in spatial joins.
        """
        if self.task.current_materialized_view_name:
            return (
                f'"{self.task.current_materialized_view_schema}".'
                f'"fm_temp_mv_{self.task.current_materialized_view_name}_dump"'
            )
        return sub_expression

    # =========================================================================
    # PostGIS query building
    # =========================================================================

    def build_spatial_join_query(self, layer_props, param_postgis_sub_expression, sub_expression):
        """Build SELECT query with spatial JOIN for filtering.

        Delegates to pg_executor when available, with minimal fallback.

        Args:
            layer_props: Layer properties dict with primary_key_name, layer_schema, layer_name.
            param_postgis_sub_expression: PostGIS spatial predicate (e.g., ST_Intersects(...)).
            sub_expression: Source layer subset expression or table reference.

        Returns:
            str: SQL SELECT query with spatial JOIN.
        """
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
        source_ref = self.get_source_reference(sub_expression)
        return (
            f'(SELECT "{param_distant_table}"."{param_distant_primary_key_name}" '  # nosec B608
            f'FROM "{param_distant_schema}"."{param_distant_table}" '
            f'INNER JOIN {source_ref} ON {param_postgis_sub_expression})'
        )

    def apply_combine_operator(self, primary_key_name, param_expression, param_old_subset, param_combine_operator):
        """Apply SQL set operator to combine with existing subset.

        Delegates to pg_executor when available, with minimal fallback.

        Args:
            primary_key_name: Primary key field name.
            param_expression: New filter subquery expression.
            param_old_subset: Existing subset string from layer.
            param_combine_operator: SQL set operator (UNION, INTERSECT, EXCEPT).

        Returns:
            str: Combined SQL expression.
        """
        if PG_EXECUTOR_AVAILABLE:
            return pg_executor.apply_combine_operator(
                primary_key_name, param_expression, param_old_subset, param_combine_operator
            )
        # Minimal fallback
        if param_old_subset and param_combine_operator:
            return f'"{primary_key_name}" IN ( {param_old_subset} {param_combine_operator} {param_expression} )'
        return f'"{primary_key_name}" IN {param_expression}'

    def build_postgis_filter_expression(self, layer_props, param_postgis_sub_expression,
                                        sub_expression, param_old_subset, param_combine_operator):
        """Build complete PostGIS filter expression for subset string.

        Delegates to pg_executor.build_postgis_filter_expression() when available.

        Args:
            layer_props: Layer properties dict.
            param_postgis_sub_expression: PostGIS spatial predicate expression.
            sub_expression: Source layer subset expression.
            param_old_subset: Existing subset string from layer.
            param_combine_operator: SQL set operator (UNION, INTERSECT, EXCEPT).

        Returns:
            tuple: (expression, param_expression) - Complete filter and subquery.
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
        expression = self.apply_combine_operator(
            layer_props["primary_key_name"], param_expression, param_old_subset, param_combine_operator
        )
        return expression, param_expression

    # =========================================================================
    # OGR spatial operations
    # =========================================================================

    def execute_ogr_spatial_selection(self, layer, current_layer, param_old_subset):
        """Execute OGR spatial selection using in-memory geometry operations.

        Delegates to ogr_executor.execute_ogr_spatial_selection().

        Args:
            layer: Source QgsVectorLayer.
            current_layer: Target QgsVectorLayer to filter.
            param_old_subset: Existing subset string.

        Raises:
            ImportError: If ogr_executor is not available.
        """
        if not OGR_EXECUTOR_AVAILABLE:
            raise ImportError("ogr_executor module not available - cannot execute OGR spatial selection")

        if not hasattr(ogr_executor, 'OGRSpatialSelectionContext'):
            raise ImportError("ogr_executor.OGRSpatialSelectionContext not available")

        context = ogr_executor.OGRSpatialSelectionContext(
            ogr_source_geom=self.task.ogr_source_geom,
            current_predicates=self.task.current_predicates,
            has_combine_operator=self.task.has_combine_operator,
            param_other_layers_combine_operator=self.task.param_other_layers_combine_operator,
            verify_and_create_spatial_index=self.task._verify_and_create_spatial_index,
        )
        ogr_executor.execute_ogr_spatial_selection(
            layer, current_layer, param_old_subset, context
        )
        logger.debug("execute_ogr_spatial_selection: delegated to ogr_executor")

    def build_ogr_filter_from_selection(self, current_layer, layer_props, param_distant_geom_expression):
        """Build OGR filter expression from spatial selection results.

        Delegates to ogr_executor.build_ogr_filter_from_selection().

        Args:
            current_layer: QgsVectorLayer with selected features.
            layer_props: Layer properties dict.
            param_distant_geom_expression: Distant geometry expression.

        Returns:
            str: OGR-compatible filter expression.

        Raises:
            ImportError: If ogr_executor is not available.
        """
        if not OGR_EXECUTOR_AVAILABLE:
            raise ImportError("ogr_executor module not available - cannot build OGR filter from selection")

        return ogr_executor.build_ogr_filter_from_selection(
            layer=current_layer,
            layer_props=layer_props,
            distant_geom_expression=param_distant_geom_expression
        )

"""
Expression Facade Handler for FilterEngineTask

Centralizes all expression building and manipulation facade methods that
delegate to specialized services (ExpressionBuilder, AttributeFilterExecutor,
ExpressionSanitizer, pg_executor).

Methods in this handler are thin facades that:
- Sanitize subset strings
- Process QGIS expressions to SQL
- Build feature ID expressions
- Qualify field names
- Combine filter expressions with existing subsets
- Apply filter and queue subset updates

Extracted from FilterEngineTask as part of Pass 3 god-class decomposition.

Location: core/tasks/expression_facade_handler.py (Hexagonal Architecture - Application Layer)

Thread Safety:
    Most methods are safe for worker threads. The _apply_filter_and_update_subset
    method queues subset requests for main thread application (does NOT call
    setSubsetString directly).
"""

import logging
import os
from typing import Any, Optional

from ...infrastructure.logging import setup_logger
from ...config.config import ENV_VARS
from ...infrastructure.constants import PROVIDER_POSTGRES

# Setup logger
logger = setup_logger(
    'FilterMate.Tasks.ExpressionFacade',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_tasks.log'),
    level=logging.INFO
)

# Lazy load pg_executor
from ..ports.backend_services import get_backend_services
_backend_services = get_backend_services()
pg_executor = _backend_services.get_postgresql_executor()
PG_EXECUTOR_AVAILABLE = pg_executor is not None


class ExpressionFacadeHandler:
    """Centralizes expression building and manipulation facades.

    This class encapsulates all expression-related facade methods previously
    embedded in FilterEngineTask. Each method delegates to a specialized
    service (ExpressionBuilder, AttributeFilterExecutor, pg_executor, etc.)

    Attributes:
        task: Reference to the parent FilterEngineTask for state access.

    Example:
        >>> handler = ExpressionFacadeHandler(task)
        >>> sanitized = handler.sanitize_subset_string(raw_subset)
        >>> combined = handler.build_combined_filter_expression(new_expr, old_sub, 'AND')
    """

    def __init__(self, task):
        """Initialize ExpressionFacadeHandler.

        Args:
            task: FilterEngineTask instance providing access to task state
                  (source_layer, task_parameters, executor getters, etc.)
        """
        self.task = task

    # =========================================================================
    # Sanitization and extraction
    # =========================================================================

    def sanitize_subset_string(self, subset_string):
        """Remove non-boolean display expressions and fix type casting issues.

        v4.7 E6-S2: Pure delegation to core.services.expression_service.

        Args:
            subset_string: The original subset string.

        Returns:
            str: Sanitized subset string with non-boolean expressions removed.
        """
        from ..services.expression_service import sanitize_subset_string
        return sanitize_subset_string(subset_string, logger=logger)

    def extract_spatial_clauses_for_exists(self, filter_expr, source_table=None):
        """Extract spatial clauses for EXISTS subqueries.

        Delegates to core.filter.expression_sanitizer.

        Args:
            filter_expr: Filter expression to analyze.
            source_table: Optional source table name.

        Returns:
            Extracted spatial clauses.
        """
        from ..filter.expression_sanitizer import extract_spatial_clauses_for_exists
        return extract_spatial_clauses_for_exists(filter_expr, source_table)

    # =========================================================================
    # PostgreSQL type casting and normalization
    # =========================================================================

    def apply_postgresql_type_casting(self, expression, layer=None):
        """Apply PostgreSQL type casting to fix varchar/numeric comparison issues.

        Delegates to pg_executor.apply_postgresql_type_casting().

        Args:
            expression: SQL expression to cast.
            layer: Optional QgsVectorLayer for field type inference.

        Returns:
            str: Expression with type casting applied, or unchanged if pg_executor unavailable.
        """
        if PG_EXECUTOR_AVAILABLE:
            return pg_executor.apply_postgresql_type_casting(expression, layer)
        return expression

    def normalize_column_names_for_postgresql(self, expression, field_names):
        """Normalize column names to match actual PostgreSQL column names.

        v4.7 E6-S1: Pure delegation to pg_executor.

        Args:
            expression: SQL expression with column references.
            field_names: List of actual field names.

        Returns:
            str: Expression with normalized column names.

        Raises:
            ImportError: If pg_executor is not available.
        """
        if not PG_EXECUTOR_AVAILABLE:
            raise ImportError("pg_executor module not available - cannot normalize column names for PostgreSQL")
        return pg_executor.normalize_column_names_for_postgresql(expression, field_names)

    # =========================================================================
    # QGIS expression processing
    # =========================================================================

    def process_qgis_expression(self, expression):
        """Process and validate a QGIS expression, converting it to SQL.

        Phase E13: Delegates to AttributeFilterExecutor.

        Args:
            expression: QGIS expression string.

        Returns:
            tuple: (processed_expression, is_field_expression) or (None, None) if invalid.
        """
        executor = self.task._get_attribute_executor()

        # FIX 2026-01-18: AttributeFilterExecutor.process_qgis_expression only accepts expression
        result = executor.process_qgis_expression(expression=expression)

        # Update task state if field expression detected
        if result[1] and isinstance(result[1], tuple) and result[1][0]:
            self.task.is_field_expression = result[1]
        elif result[1]:
            self.task.is_field_expression = result[1]

        return result

    def combine_with_old_subset(self, expression):
        """Combine new expression with old subset.

        Phase E13: Delegates to AttributeFilterExecutor.
        The executor already has old_subset, combine_operator, and provider_type
        set during initialization.

        Args:
            expression: New expression to combine.

        Returns:
            str: Combined expression.
        """
        executor = self.task._get_attribute_executor()
        # FIX 2026-01-18: only takes the expression parameter
        return executor.combine_with_old_subset(expression)

    # =========================================================================
    # Feature ID expression building
    # =========================================================================

    def build_feature_id_expression(self, features_list):
        """Build expression from feature IDs.

        Phase E13: Delegates to AttributeFilterExecutor.

        Args:
            features_list: List of feature objects with IDs.

        Returns:
            str: SQL expression filtering by feature IDs.
        """
        executor = self.task._get_attribute_executor()

        result = executor.build_feature_id_expression(
            features_list=features_list,
            is_numeric=self.task.task_parameters["infos"]["primary_key_is_numeric"]
        )

        # FIX 2026-01-16: Log expression to diagnose WHERE prefix
        logger.info(f"_build_feature_id_expression result: '{result[:100] if result else None}...'")
        if result and result.strip().startswith('WHERE'):
            logger.error("BUG: Expression starts with WHERE! Should NOT have WHERE prefix for setSubsetString")

        return result

    def is_pk_numeric(self, layer=None, pk_field=None):
        """Check if the primary key field is numeric.

        Args:
            layer: Optional QgsVectorLayer (defaults to source_layer).
            pk_field: Optional primary key field name.

        Returns:
            bool: True if primary key is numeric.
        """
        check_layer = layer or self.task.source_layer
        check_pk = pk_field or getattr(self.task, 'primary_key_name', None)
        if PG_EXECUTOR_AVAILABLE:
            return pg_executor._is_pk_numeric(check_layer, check_pk)
        return True  # Default assumption

    def format_pk_values_for_sql(self, values, is_numeric=None, layer=None, pk_field=None):
        """Format primary key values for SQL IN clause.

        Args:
            values: List of primary key values.
            is_numeric: Optional bool override.
            layer: Optional QgsVectorLayer.
            pk_field: Optional primary key field name.

        Returns:
            str: Formatted values for SQL IN clause.
        """
        if PG_EXECUTOR_AVAILABLE:
            return pg_executor.format_pk_values_for_sql(values, is_numeric, layer, pk_field)
        # Minimal fallback for non-PostgreSQL
        if not values:
            return ''
        return ', '.join(str(v) for v in values)

    def optimize_duplicate_in_clauses(self, expression):
        """Optimize duplicate IN clauses in expression.

        Delegates to core.filter.expression_sanitizer.

        Args:
            expression: SQL expression to optimize.

        Returns:
            str: Optimized expression.
        """
        from ..filter.expression_sanitizer import optimize_duplicate_in_clauses
        return optimize_duplicate_in_clauses(expression)

    # =========================================================================
    # Field name qualification
    # =========================================================================

    def qualify_field_names_in_expression(self, expression, field_names, primary_key_name, table_name, is_postgresql):
        """Qualify field names with table prefix for PostgreSQL/Spatialite expressions.

        EPIC-1 Phase E7.5: Delegates to core.filter.expression_builder.

        Args:
            expression: Raw QGIS expression string.
            field_names: List of field names to qualify.
            primary_key_name: Primary key field name.
            table_name: Source table name.
            is_postgresql: Whether target is PostgreSQL.

        Returns:
            str: Expression with qualified field names.
        """
        from ..filter.expression_builder import qualify_field_names_in_expression

        return qualify_field_names_in_expression(
            expression=expression,
            field_names=field_names,
            primary_key_name=primary_key_name,
            table_name=table_name,
            is_postgresql=is_postgresql,
            provider_type=self.task.param_source_provider_type,
            normalize_columns_fn=self.normalize_column_names_for_postgresql if is_postgresql else None
        )

    # =========================================================================
    # Combined filter expression building
    # =========================================================================

    def build_combined_filter_expression(self, new_expression, old_subset, combine_operator, layer_props=None):
        """Combine new filter expression with existing subset using specified operator.

        Phase E13 Step 4: Delegates to SubsetStringBuilder.combine_expressions().

        OPTIMIZATION v2.8.0: Uses CombinedQueryOptimizer to detect and reuse
        materialized views from previous filter operations.

        v2.9.0: Creates source MV with pre-computed buffer when FID count exceeds
        SOURCE_FID_MV_THRESHOLD (50).

        Args:
            new_expression: New filter expression to apply.
            old_subset: Existing subset string from layer.
            combine_operator: SQL operator ('AND', 'OR', 'NOT').
            layer_props: Optional layer properties for optimization context.

        Returns:
            str: Combined filter expression (optimized when possible).
        """
        from ..optimization import get_combined_query_optimizer

        builder = self.task._get_subset_builder()
        result = builder.combine_expressions(
            new_expression=new_expression,
            old_subset=old_subset,
            combine_operator=combine_operator,
            layer_props=layer_props
        )

        # Handle source MV creation (kept here as it's task-specific)
        # The builder returns optimization info but doesn't create MVs
        if result.optimization_applied:
            try:
                optimizer = get_combined_query_optimizer()
                opt_result = optimizer.optimize_combined_expression(
                    old_subset=self.sanitize_subset_string(old_subset) if old_subset else "",
                    new_expression=new_expression,
                    combine_operator=combine_operator,
                    layer_props=layer_props
                )
                if opt_result.success and hasattr(opt_result, 'source_mv_info') and opt_result.source_mv_info is not None:
                    self.task._create_source_mv_if_needed(opt_result.source_mv_info)
            except (AttributeError, ValueError, RuntimeError) as e:
                logger.debug(f"MV creation skipped: {e}")

        return result.expression

    # =========================================================================
    # Filter application and subset queuing
    # =========================================================================

    def apply_filter_and_update_subset(self, expression):
        """Queue filter expression for application on main thread.

        CRITICAL: setSubsetString must be called from main thread to avoid
        access violation crashes. This method only queues the expression
        for application in finished() which runs on the main thread.

        Args:
            expression: SQL filter expression to apply.

        Returns:
            bool: True if expression was queued successfully.
        """
        # Apply type casting for PostgreSQL to fix varchar/numeric comparison issues
        if self.task.param_source_provider_type == PROVIDER_POSTGRES:
            expression = self.apply_postgresql_type_casting(expression, self.task.source_layer)

        # Queue source layer for filter application in finished()
        if hasattr(self.task, '_pending_subset_requests'):
            self.task._pending_subset_requests.append((self.task.source_layer, expression))
            logger.info(f"Queued source layer {self.task.source_layer.name()} for filter application in finished()")

        # Only build PostgreSQL SELECT for PostgreSQL providers
        if self.task.param_source_provider_type == PROVIDER_POSTGRES:
            # FIX 2026-01-16: Strip leading "WHERE " to prevent "WHERE WHERE" syntax error
            clean_expression = expression.lstrip()
            if clean_expression.upper().startswith('WHERE '):
                clean_expression = clean_expression[6:].lstrip()
                logger.debug("Stripped WHERE prefix from expression in apply_filter_and_update_subset")

            # Build full SELECT expression for subset management (PostgreSQL only)
            full_expression = (
                f'SELECT "{self.task.param_source_table}"."{self.task.primary_key_name}", '  # nosec B608 - identifiers from QGIS layer metadata
                f'"{self.task.param_source_table}"."{self.task.param_source_geom}" '
                f'FROM "{self.task.param_source_schema}"."{self.task.param_source_table}" '
                f'WHERE {clean_expression}'
            )
            self.task.manage_layer_subset_strings(
                self.task.source_layer,
                full_expression,
                self.task.primary_key_name,
                self.task.param_source_geom,
                False
            )

        # Return True to indicate expression was queued successfully
        return True

    # =========================================================================
    # QGIS expression to SQL conversion
    # =========================================================================

    def qgis_expression_to_postgis(self, expression: str) -> str:
        """Convert a QGIS expression to PostGIS-compatible SQL.

        Transforms QGIS expression syntax to PostgreSQL/PostGIS SQL, handling
        function name mapping, operator conversions, and geometry column references.

        Args:
            expression: QGIS expression string to convert.

        Returns:
            PostGIS-compatible SQL expression, or original if empty.
        """
        if not expression:
            return expression
        geom_col = getattr(self.task, 'param_source_geom', None) or 'geometry'
        from ..services.expression_service import ExpressionService
        from ..domain.filter_expression import ProviderType
        return ExpressionService().to_sql(expression, ProviderType.POSTGRESQL, geom_col)

    def qgis_expression_to_spatialite(self, expression: str) -> str:
        """Convert a QGIS expression to Spatialite-compatible SQL.

        Transforms QGIS expression syntax to Spatialite SQL, handling
        function name mapping, operator conversions, and geometry column references.

        Args:
            expression: QGIS expression string to convert.

        Returns:
            Spatialite-compatible SQL expression, or original if empty.
        """
        if not expression:
            return expression
        geom_col = getattr(self.task, 'param_source_geom', None) or 'geometry'
        from ..services.expression_service import ExpressionService
        from ..domain.filter_expression import ProviderType
        return ExpressionService().to_sql(expression, ProviderType.SPATIALITE, geom_col)

    # =========================================================================
    # SQL operator normalization and combine operators
    # =========================================================================

    def normalize_sql_operator(self, operator):
        """Normalize translated SQL operators to English SQL keywords.

        FIX v2.5.12: Handle cases where translated operator values (ET, OU, NON)
        are stored in layer properties or project files from older versions.

        Args:
            operator: The operator string (possibly translated: ET, OU, UND, Y, etc.)

        Returns:
            str: Normalized SQL operator ('AND', 'OR', 'AND NOT', 'NOT') or None.
        """
        if not operator:
            return None

        op_upper = operator.upper().strip()

        # Mapping of translated operators to SQL keywords
        translations = {
            # French
            'ET': 'AND',
            'OU': 'OR',
            'ET NON': 'AND NOT',
            'NON': 'NOT',
            # German
            'UND': 'AND',
            'ODER': 'OR',
            'UND NICHT': 'AND NOT',
            'NICHT': 'NOT',
            # Spanish
            'Y': 'AND',
            'O': 'OR',
            'Y NO': 'AND NOT',
            'NO': 'NOT',
            # Italian
            'E': 'AND',
            'E NON': 'AND NOT',
            # Portuguese
            'E NÃO': 'AND NOT',
            'NÃO': 'NOT',
            # Already English - just return as-is
            'AND': 'AND',
            'OR': 'OR',
            'AND NOT': 'AND NOT',
            'NOT': 'NOT',
        }

        normalized = translations.get(op_upper, operator)

        if normalized != operator:
            logger.debug(f"Normalized operator '{operator}' to '{normalized}'")

        return normalized

    def get_source_combine_operator(self):
        """Get logical operator for combining with source layer's existing filter.

        Returns logical operators (AND, AND NOT, OR) from task parameters,
        normalized to English SQL keywords.

        Returns:
            str: 'AND', 'AND NOT', 'OR', or None.
        """
        if not hasattr(self.task, 'has_combine_operator') or not self.task.has_combine_operator:
            return None

        source_op = getattr(self.task, 'param_source_layer_combine_operator', None)
        return self.normalize_sql_operator(source_op)

    def get_combine_operator(self):
        """Get operator for combining with distant layers' existing filters.

        Returns the operator from task parameters, normalized to English SQL keywords,
        for use in SQL WHERE clauses across all backends.

        Returns:
            str: 'AND', 'OR', 'AND NOT', or None.
        """
        if not hasattr(self.task, 'has_combine_operator') or not self.task.has_combine_operator:
            return None

        other_op = getattr(self.task, 'param_other_layers_combine_operator', None)
        return self.normalize_sql_operator(other_op)

    def combine_with_old_filter(self, expression, layer):
        """Combine expression with layer's existing filter.

        Delegates to core.filter.expression_combiner.combine_with_old_filter().

        Args:
            expression: New filter expression.
            layer: QgsVectorLayer with potential existing subsetString.

        Returns:
            str: Combined filter expression.
        """
        from ..filter.expression_combiner import combine_with_old_filter

        old_subset = layer.subsetString() if layer.subsetString() != '' else None

        return combine_with_old_filter(
            new_expression=expression,
            old_subset=old_subset,
            combine_operator=self.get_combine_operator(),
            sanitize_fn=self.sanitize_subset_string
        )

    # =========================================================================
    # Query complexity analysis
    # =========================================================================

    def has_expensive_spatial_expression(self, sql_string: str) -> bool:
        """Detect if a SQL expression contains expensive spatial predicates.

        Delegates to core.optimization.query_analyzer.

        Args:
            sql_string: SQL expression to analyze.

        Returns:
            bool: True if expression contains expensive spatial predicates.
        """
        from ..optimization.query_analyzer import has_expensive_spatial_expression
        return has_expensive_spatial_expression(sql_string)

    def is_complex_filter(self, subset: str, provider_type: str) -> bool:
        """Check if a filter expression is complex (requires longer refresh delay).

        Delegates to core.optimization.query_analyzer.

        Args:
            subset: Filter expression to check.
            provider_type: Backend type ('postgresql', 'spatialite', 'ogr').

        Returns:
            bool: True if filter is considered complex.
        """
        from ..optimization.query_analyzer import is_complex_filter
        return is_complex_filter(subset, provider_type)

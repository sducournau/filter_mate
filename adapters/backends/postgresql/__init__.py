"""
FilterMate PostgreSQL Backend Package.

PostgreSQL/PostGIS specific implementations including:
- Main backend with BackendPort interface
- Materialized view management
- Query optimization
- Session cleanup
- Source geometry preparation (EPIC-1 Phase E4-S9)

Part of Phase 4 Backend Refactoring (ARCH-035 through ARCH-039).
"""
from .backend import PostgreSQLBackend, create_postgresql_backend
from .mv_manager import MaterializedViewManager, MVConfig, MVInfo, create_mv_manager
from .optimizer import QueryOptimizer, QueryAnalysis, OptimizationResult, create_optimizer
from .cleanup import PostgreSQLCleanupService, create_cleanup_service
from .filter_executor import (
    # EPIC-1 Phase E4-S9: Source geometry preparation
    prepare_postgresql_source_geom,
    qgis_expression_to_postgis,
    build_postgis_predicates,
    apply_postgresql_type_casting,
    build_spatial_join_query,
    # EPIC-1 Phase E4-S4b: Filter expression building
    build_postgis_filter_expression,
    apply_combine_operator,
)
from .executor_wrapper import PostgreSQLFilterExecutor
from .filter_actions import (
    # EPIC-1 Phase E5/E6: Filter action execution
    execute_filter_action_postgresql,
    execute_filter_action_postgresql_direct,
    execute_filter_action_postgresql_materialized,
    has_expensive_spatial_expression,
    should_combine_filters,
    build_combined_expression,
    MATERIALIZED_VIEW_THRESHOLD,
    # Reset and unfilter actions
    execute_reset_action_postgresql,
    execute_unfilter_action_postgresql,
)

# v4.1.0: Expression Builder (migrated from before_migration)
from .expression_builder import PostgreSQLExpressionBuilder

__all__ = [
    # Main backend
    'PostgreSQLBackend',
    'create_postgresql_backend',
    # MV Manager
    'MaterializedViewManager',
    'MVConfig',
    'MVInfo',
    'create_mv_manager',
    # Optimizer
    'QueryOptimizer',
    'QueryAnalysis',
    'OptimizationResult',
    'create_optimizer',
    # Cleanup
    'PostgreSQLCleanupService',
    'create_cleanup_service',
    # EPIC-1 Phase E4-S9: Filter executor
    'prepare_postgresql_source_geom',
    'qgis_expression_to_postgis',
    'build_postgis_predicates',
    'apply_postgresql_type_casting',
    'build_spatial_join_query',
    # EPIC-1 Phase E4-S4b: Filter expression building
    'build_postgis_filter_expression',
    'apply_combine_operator',
    # EPIC-1 Phase E5/E6: Filter action execution
    'execute_filter_action_postgresql',
    'execute_filter_action_postgresql_direct',
    'execute_filter_action_postgresql_materialized',
    'has_expensive_spatial_expression',
    'should_combine_filters',
    'build_combined_expression',
    'MATERIALIZED_VIEW_THRESHOLD',
    # Reset and unfilter actions
    'execute_reset_action_postgresql',
    'execute_unfilter_action_postgresql',
    # v4.1.0: Expression Builder
    'PostgreSQLExpressionBuilder',
]

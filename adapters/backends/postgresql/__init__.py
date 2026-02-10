"""
FilterMate PostgreSQL Backend Package.

PostgreSQL/PostGIS specific implementations including:
- Main backend with BackendPort interface
- Materialized view management
- Query optimization
- Filter chain optimization (v4.2.10)
- Session cleanup
- Source geometry preparation (EPIC-1 Phase E4-S9)

Part of Phase 4 Backend Refactoring (ARCH-035 through ARCH-039).
"""
from .backend import PostgreSQLBackend, create_postgresql_backend  # noqa: F401
from .mv_manager import MaterializedViewManager, MVConfig, MVInfo, create_mv_manager  # noqa: F401
from .optimizer import QueryOptimizer, QueryAnalysis, OptimizationResult, create_optimizer  # noqa: F401
from .cleanup import PostgreSQLCleanupService, create_cleanup_service  # noqa: F401
from .filter_executor import (  # noqa: F401
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
from .executor_wrapper import PostgreSQLFilterExecutor  # noqa: F401
from .filter_actions import (  # noqa: F401
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

# Expression Builder (migrated from before_migration)
from .expression_builder import PostgreSQLExpressionBuilder  # noqa: F401

# Filter Chain Optimizer (MV-based optimization)
from .filter_chain_optimizer import (  # noqa: F401
    FilterChainOptimizer,
    FilterChainContext,
    OptimizationStrategy,
    OptimizedChain,
    create_filter_chain_optimizer,
    optimize_filter_chain,
)

# Backward compatibility alias (legacy name from modules/)
# This alias allows code that imports PostgreSQLGeometricFilter to work
# with the renamed PostgreSQLBackend class
PostgreSQLGeometricFilter = PostgreSQLBackend

__all__ = [
    # Main backend
    'PostgreSQLBackend',
    'PostgreSQLGeometricFilter',  # Legacy alias for backward compatibility
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
    # Filter Chain Optimizer
    'FilterChainOptimizer',
    'FilterChainContext',
    'OptimizationStrategy',
    'OptimizedChain',
    'create_filter_chain_optimizer',
    'optimize_filter_chain',
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
    # Expression Builder
    'PostgreSQLExpressionBuilder',
]

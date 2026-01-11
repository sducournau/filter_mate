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
)

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
]

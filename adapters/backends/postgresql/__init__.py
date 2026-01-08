"""
FilterMate PostgreSQL Backend Package.

PostgreSQL/PostGIS specific implementations including:
- Main backend with BackendPort interface
- Materialized view management
- Query optimization
- Session cleanup

Part of Phase 4 Backend Refactoring (ARCH-035 through ARCH-039).
"""
from .backend import PostgreSQLBackend, create_postgresql_backend
from .mv_manager import MaterializedViewManager, MVConfig, MVInfo, create_mv_manager
from .optimizer import QueryOptimizer, QueryAnalysis, OptimizationResult, create_optimizer
from .cleanup import PostgreSQLCleanupService, create_cleanup_service

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
]

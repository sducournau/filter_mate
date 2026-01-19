"""
FilterMate Spatialite Backend Package.

Spatialite/GeoPackage specific implementations including:
- Main backend with BackendPort interface
- R-tree spatial index management
- Result caching
- Temporary table support
- Source geometry preparation (EPIC-1 Phase E4-S8)
- Filter actions (reset/unfilter) - Phase 1 v4.1

Part of Phase 4 Backend Refactoring (ARCH-040 through ARCH-043).
"""
from .backend import SpatialiteBackend, create_spatialite_backend, spatialite_connect
from .cache import SpatialiteCache, CacheStats, create_cache
from .index_manager import RTreeIndexManager, IndexInfo, create_index_manager
from .executor_wrapper import SpatialiteFilterExecutor
from .filter_executor import (
    # EPIC-1 Phase E4-S8: Source geometry preparation
    SpatialiteSourceContext,
    SpatialiteSourceResult,
    SourceMode,
    determine_spatialite_source_mode,
    validate_spatialite_features,
    recover_spatialite_features_from_fids,
    resolve_spatialite_features,
    process_spatialite_geometries,
    prepare_spatialite_source_geom,
    # Expression conversion
    qgis_expression_to_spatialite,
    # EPIC-1 Phase E4-S9: Subset management
    build_spatialite_query,
    apply_spatialite_subset,
    manage_spatialite_subset,
    get_last_subset_info,
    cleanup_session_temp_tables,
    normalize_column_names_for_spatialite,
)
from .filter_actions import (
    # Phase 1 v4.1: Backend actions (reset/unfilter)
    execute_reset_action_spatialite,
    execute_unfilter_action_spatialite,
    cleanup_spatialite_session_tables,
)
from .interruptible_query import (
    # v4.1.0: Interruptible SQLite queries (migrated from before_migration)
    InterruptibleSQLiteQuery,
    BatchedSQLiteQuery,
    create_interruptible_connection,
    SPATIALITE_QUERY_TIMEOUT,
    SPATIALITE_BATCH_SIZE,
    USE_OGR_FALLBACK,
)

# v4.1.0: Expression Builder (migrated from before_migration)
from .expression_builder import SpatialiteExpressionBuilder

__all__ = [
    # Main backend
    'SpatialiteBackend',
    'create_spatialite_backend',
    'spatialite_connect',
    # Cache
    'SpatialiteCache',
    'CacheStats',
    'create_cache',
    # Index Manager
    'RTreeIndexManager',
    'IndexInfo',
    'create_index_manager',
    # EPIC-1 Phase E4-S8: Source geometry preparation
    'SpatialiteSourceContext',
    'SpatialiteSourceResult',
    'SourceMode',
    'determine_spatialite_source_mode',
    'validate_spatialite_features',
    'recover_spatialite_features_from_fids',
    'resolve_spatialite_features',
    'process_spatialite_geometries',
    'prepare_spatialite_source_geom',
    'qgis_expression_to_spatialite',
    # EPIC-1 Phase E4-S9: Subset management
    'build_spatialite_query',
    'apply_spatialite_subset',
    'manage_spatialite_subset',
    'get_last_subset_info',
    'cleanup_session_temp_tables',
    'normalize_column_names_for_spatialite',
    # Phase 1 v4.1: Backend actions
    'execute_reset_action_spatialite',
    'execute_unfilter_action_spatialite',
    'cleanup_spatialite_session_tables',
    # v4.1.0: Interruptible SQLite queries
    'InterruptibleSQLiteQuery',
    'BatchedSQLiteQuery',
    'create_interruptible_connection',
    'SPATIALITE_QUERY_TIMEOUT',
    'SPATIALITE_BATCH_SIZE',
    'USE_OGR_FALLBACK',
    # v4.1.0: Expression Builder
    'SpatialiteExpressionBuilder',
]

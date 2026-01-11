"""
FilterMate Spatialite Backend Package.

Spatialite/GeoPackage specific implementations including:
- Main backend with BackendPort interface
- R-tree spatial index management
- Result caching
- Temporary table support
- Source geometry preparation (EPIC-1 Phase E4-S8)

Part of Phase 4 Backend Refactoring (ARCH-040 through ARCH-043).
"""
from .backend import SpatialiteBackend, create_spatialite_backend, spatialite_connect
from .cache import SpatialiteCache, CacheStats, create_cache
from .index_manager import RTreeIndexManager, IndexInfo, create_index_manager
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
]

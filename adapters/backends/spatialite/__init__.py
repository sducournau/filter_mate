"""
FilterMate Spatialite Backend Package.

Spatialite/GeoPackage specific implementations including:
- Main backend with BackendPort interface
- R-tree spatial index management
- Result caching
- Temporary table support

Part of Phase 4 Backend Refactoring (ARCH-040 through ARCH-043).
"""
from .backend import SpatialiteBackend, create_spatialite_backend, spatialite_connect
from .cache import SpatialiteCache, CacheStats, create_cache
from .index_manager import RTreeIndexManager, IndexInfo, create_index_manager

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
]

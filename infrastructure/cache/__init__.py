"""
FilterMate Infrastructure Cache.

Caching utilities for performance optimization:
- QueryExpressionCache: LRU cache for spatial query expressions
- CacheEntry: Cache entry with TTL and access tracking
- SourceGeometryCache: Cache for pre-calculated source geometries

Migrated from modules/tasks/ (EPIC-1 v3.0).
"""

# Re-export query cache utilities (migrated from modules/tasks/)
from .query_cache import (  # noqa: F401
    QueryExpressionCache,
    CacheEntry,
    get_query_cache,
    clear_query_cache,
    warm_cache_for_layer,
    warm_cache_for_project
)

# Re-export geometry cache (migrated from modules/tasks/)
from .geometry_cache import SourceGeometryCache  # noqa: F401

# Re-export exploring features cache (v4.0 Sprint 18)
from .exploring_cache import ExploringFeaturesCache  # noqa: F401

# WKT Cache (migrated from before_migration v4.1.0)
from .wkt_cache import WKTCache, WKTCacheEntry, get_wkt_cache  # noqa: F401

# Spatialite Persistent Cache (migrated from before_migration v4.1.0)
from .spatialite_persistent_cache import (  # noqa: F401
    SpatialitePersistentCache,
    get_persistent_cache,
    store_filter_fids,
    get_previous_filter_fids,
    intersect_filter_fids,
)

__all__ = [
    'QueryExpressionCache',
    'CacheEntry',
    'get_query_cache',
    'clear_query_cache',
    'warm_cache_for_layer',
    'warm_cache_for_project',
    'SourceGeometryCache',
    'ExploringFeaturesCache',
    # WKT Cache (v4.1.0)
    'WKTCache',
    'WKTCacheEntry',
    'get_wkt_cache',
    # Spatialite Persistent Cache (v4.1.0)
    'SpatialitePersistentCache',
    'get_persistent_cache',
    'store_filter_fids',
    'get_previous_filter_fids',
    'intersect_filter_fids',
]

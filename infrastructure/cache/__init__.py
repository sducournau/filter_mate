"""
FilterMate Infrastructure Cache.

Caching utilities for performance optimization:
- QueryExpressionCache: LRU cache for spatial query expressions
- CacheEntry: Cache entry with TTL and access tracking
- SourceGeometryCache: Cache for pre-calculated source geometries
- ExploringFeaturesCache: Cache for exploring features

Migrated from modules/tasks/ (EPIC-1 v3.0).
"""

# Re-export query cache utilities (migrated from modules/tasks/)
from .query_cache import (
    QueryExpressionCache,
    CacheEntry,
    get_query_cache,
    clear_query_cache,
    warm_cache_for_layer,
    warm_cache_for_project
)

# Re-export geometry cache (migrated from modules/tasks/)
from .geometry_cache import SourceGeometryCache

# Re-export exploring features cache
from .exploring_cache import ExploringFeaturesCache

__all__ = [
    'QueryExpressionCache',
    'CacheEntry',
    'get_query_cache',
    'clear_query_cache',
    'warm_cache_for_layer',
    'warm_cache_for_project',
    'SourceGeometryCache',
    'ExploringFeaturesCache'
]

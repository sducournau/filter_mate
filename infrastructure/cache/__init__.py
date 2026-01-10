"""
FilterMate Infrastructure Cache.

Caching utilities for performance optimization:
- ExploringFeaturesCache: Feature list caching for exploring tab
- QueryExpressionCache: LRU cache for spatial query expressions
- CacheEntry: Cache entry with TTL and access tracking
- SourceGeometryCache: Cache for pre-calculated source geometries

Migrated from modules/tasks/ (EPIC-1 v3.0).
"""

# Re-export legacy cache classes for backward compatibility
from ...infrastructure.cache import ExploringFeaturesCache

# Re-export query cache utilities (migrated from modules/tasks/)
from infrastructure.cache.query_cache import (
    QueryExpressionCache,
    CacheEntry,
    get_query_cache,
    clear_query_cache,
    warm_cache_for_layer,
    warm_cache_for_project
)

# Re-export geometry cache (migrated from modules/tasks/)
from infrastructure.cache.geometry_cache import SourceGeometryCache

__all__ = [
    'ExploringFeaturesCache',
    'QueryExpressionCache',
    'CacheEntry',
    'get_query_cache',
    'clear_query_cache',
    'warm_cache_for_layer',
    'warm_cache_for_project',
    'SourceGeometryCache'
]

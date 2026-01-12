# -*- coding: utf-8 -*-
"""
Query Cache - LEGACY SHIM

⚠️ DEPRECATED: This module has been migrated to infrastructure/cache/query_cache.py (EPIC-1)

MIGRATION GUIDE:
- OLD: from modules.tasks.query_cache import QueryExpressionCache
- NEW: from infrastructure.cache import QueryExpressionCache

All functionality is now available from:
    from infrastructure.cache import (
        QueryExpressionCache,
        CacheEntry,
        get_query_cache,
        clear_query_cache,
        warm_cache_for_layer,
        warm_cache_for_project
    )

This shim provides backward compatibility but will be removed in v3.1.
"""

import warnings

warnings.warn(
    "modules.tasks.query_cache is deprecated. "
    "Use 'from infrastructure.cache import ...' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from infrastructure
from ...infrastructure.cache import (
    QueryExpressionCache,
    CacheEntry,
    get_query_cache,
    clear_query_cache,
    warm_cache_for_layer,
    warm_cache_for_project
)

__all__ = [
    'QueryExpressionCache',
    'CacheEntry',
    'get_query_cache',
    'clear_query_cache',
    'warm_cache_for_layer',
    'warm_cache_for_project'
]

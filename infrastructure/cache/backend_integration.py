# -*- coding: utf-8 -*-
"""
Backend Cache Integration for FilterMate.

v4.1.1 - January 2026 - EPIC-3 Sprint 2

PURPOSE:
Integrates caching with FilterMate's multi-backend system:
1. Backend-aware cache keys
2. Backend-specific cache strategies
3. Integration with PostgreSQL, Spatialite, OGR backends
4. Cache warming for frequently used queries

USAGE:
    from infrastructure.cache import BackendCacheIntegration
    
    cache_integration = BackendCacheIntegration()
    
    # Get cached or execute query
    result = cache_integration.cached_query(
        layer=my_layer,
        expression="status = 1",
        backend_type="postgresql"
    )
"""

import logging
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum

from .interface import CacheKey, CacheEntry, CacheManager, get_cache_manager
from .query_cache import QueryCache, FilterResultCache, FilterCacheConfig
from .invalidation import CacheInvalidator, get_cache_invalidator

logger = logging.getLogger('FilterMate.Cache.Backend')


class BackendType(Enum):
    """Supported backend types."""
    POSTGRESQL = "postgresql"
    SPATIALITE = "spatialite"
    OGR = "ogr"
    MEMORY = "memory"


@dataclass
class BackendCacheConfig:
    """
    Backend-specific cache configuration.
    
    Different backends may benefit from different cache settings.
    """
    backend_type: BackendType
    enabled: bool = True
    max_entries: int = 500
    ttl_seconds: int = 300
    cache_queries: bool = True
    cache_unique_values: bool = True
    cache_counts: bool = True
    
    # PostgreSQL-specific
    cache_prepared_statements: bool = True
    
    # Spatialite-specific
    cache_spatial_index: bool = True
    
    # OGR-specific (more aggressive caching for slow backends)
    eager_caching: bool = False


# Default configurations per backend
DEFAULT_BACKEND_CONFIGS = {
    BackendType.POSTGRESQL: BackendCacheConfig(
        backend_type=BackendType.POSTGRESQL,
        max_entries=1000,
        ttl_seconds=600,  # PostgreSQL is fast, longer cache OK
        cache_prepared_statements=True,
    ),
    BackendType.SPATIALITE: BackendCacheConfig(
        backend_type=BackendType.SPATIALITE,
        max_entries=500,
        ttl_seconds=300,
        cache_spatial_index=True,
    ),
    BackendType.OGR: BackendCacheConfig(
        backend_type=BackendType.OGR,
        max_entries=2000,  # More entries for slow backend
        ttl_seconds=900,   # Longer TTL
        eager_caching=True,  # Pre-cache common queries
    ),
    BackendType.MEMORY: BackendCacheConfig(
        backend_type=BackendType.MEMORY,
        max_entries=100,   # Memory layers are fast
        ttl_seconds=60,    # Short TTL
    ),
}


class BackendCacheIntegration:
    """
    Integrates caching with backend system.
    
    Provides backend-aware caching with appropriate strategies
    for each backend type.
    
    Example:
        integration = BackendCacheIntegration()
        
        # Cache a query result
        integration.cache_query_result(
            layer_id="layer_123",
            backend_type=BackendType.POSTGRESQL,
            expression="status = 1",
            result_ids=[1, 2, 3, 4, 5]
        )
        
        # Get cached result
        result = integration.get_cached_query(
            layer_id="layer_123",
            backend_type=BackendType.POSTGRESQL,
            expression="status = 1"
        )
    """
    
    def __init__(
        self,
        cache_manager: CacheManager = None,
        configs: Dict[BackendType, BackendCacheConfig] = None,
    ):
        """
        Initialize backend cache integration.
        
        Args:
            cache_manager: Cache manager instance
            configs: Backend-specific configurations
        """
        self._cache_manager = cache_manager or get_cache_manager()
        self._configs = configs or DEFAULT_BACKEND_CONFIGS.copy()
        self._invalidator = get_cache_invalidator()
        
        # Create backend-specific caches
        self._backend_caches: Dict[BackendType, FilterResultCache] = {}
        self._initialize_caches()
    
    def _initialize_caches(self) -> None:
        """Initialize caches for each backend."""
        for backend_type, config in self._configs.items():
            if config.enabled:
                cache_config = FilterCacheConfig(
                    enabled=config.enabled,
                    max_entries=config.max_entries,
                    ttl_seconds=config.ttl_seconds,
                    cache_feature_ids=config.cache_queries,
                    cache_counts=config.cache_counts,
                    cache_unique_values=config.cache_unique_values,
                )
                
                cache = FilterResultCache(cache_config)
                self._backend_caches[backend_type] = cache
                
                # Register with manager
                self._cache_manager.register(
                    f"backend_{backend_type.value}",
                    cache._cache,
                )
    
    def get_backend_type(self, layer) -> BackendType:
        """
        Determine backend type from layer.
        
        Args:
            layer: QgsVectorLayer
            
        Returns:
            BackendType enum value
        """
        try:
            provider = layer.providerType()
            
            if provider == 'postgres':
                return BackendType.POSTGRESQL
            elif provider == 'spatialite':
                return BackendType.SPATIALITE
            elif provider == 'ogr':
                return BackendType.OGR
            elif provider == 'memory':
                return BackendType.MEMORY
            else:
                return BackendType.OGR  # Default fallback
        except Exception:
            return BackendType.OGR
    
    def _get_cache(self, backend_type: BackendType) -> Optional[FilterResultCache]:
        """Get cache for backend type."""
        return self._backend_caches.get(backend_type)
    
    def _make_backend_key(
        self,
        layer_id: str,
        backend_type: BackendType,
        expression: str,
    ) -> CacheKey:
        """Create backend-specific cache key."""
        return CacheKey(
            namespace=f"backend_{backend_type.value}",
            layer_id=layer_id,
            expression=expression,
        )
    
    # Query caching
    
    def cache_query_result(
        self,
        layer_id: str,
        backend_type: BackendType,
        expression: str,
        result_ids: List[int],
        ttl: int = None,
    ) -> bool:
        """
        Cache query result.
        
        Args:
            layer_id: Layer identifier
            backend_type: Backend type
            expression: Filter expression
            result_ids: Matching feature IDs
            ttl: Optional TTL override
        """
        cache = self._get_cache(backend_type)
        if not cache:
            return False
        
        return cache.cache_feature_ids(layer_id, expression, result_ids, ttl)
    
    def get_cached_query(
        self,
        layer_id: str,
        backend_type: BackendType,
        expression: str,
    ) -> Optional[List[int]]:
        """
        Get cached query result.
        
        Args:
            layer_id: Layer identifier
            backend_type: Backend type
            expression: Filter expression
            
        Returns:
            List of feature IDs or None
        """
        cache = self._get_cache(backend_type)
        if not cache:
            return None
        
        return cache.get_feature_ids(layer_id, expression)
    
    def cached_query(
        self,
        layer_id: str,
        backend_type: BackendType,
        expression: str,
        executor: Callable[[], List[int]],
        ttl: int = None,
    ) -> List[int]:
        """
        Get cached query result or execute and cache.
        
        Args:
            layer_id: Layer identifier
            backend_type: Backend type
            expression: Filter expression
            executor: Function to execute if not cached
            ttl: Optional TTL override
            
        Returns:
            List of feature IDs
        """
        # Try cache first
        cached = self.get_cached_query(layer_id, backend_type, expression)
        if cached is not None:
            logger.debug(f"Cache hit for {backend_type.value}:{layer_id}")
            return cached
        
        # Execute query
        result = executor()
        
        # Cache result
        self.cache_query_result(layer_id, backend_type, expression, result, ttl)
        
        return result
    
    # Unique values caching
    
    def cache_unique_values(
        self,
        layer_id: str,
        backend_type: BackendType,
        field_name: str,
        values: List[Any],
        filter_expr: str = "",
        ttl: int = None,
    ) -> bool:
        """Cache unique values for a field."""
        cache = self._get_cache(backend_type)
        if not cache:
            return False
        
        return cache.cache_unique_values(
            layer_id, field_name, values, filter_expr, ttl
        )
    
    def get_cached_unique_values(
        self,
        layer_id: str,
        backend_type: BackendType,
        field_name: str,
        filter_expr: str = "",
    ) -> Optional[List[Any]]:
        """Get cached unique values."""
        cache = self._get_cache(backend_type)
        if not cache:
            return None
        
        return cache.get_unique_values(layer_id, field_name, filter_expr)
    
    def cached_unique_values(
        self,
        layer_id: str,
        backend_type: BackendType,
        field_name: str,
        executor: Callable[[], List[Any]],
        filter_expr: str = "",
        ttl: int = None,
    ) -> List[Any]:
        """Get cached unique values or execute and cache."""
        cached = self.get_cached_unique_values(
            layer_id, backend_type, field_name, filter_expr
        )
        if cached is not None:
            return cached
        
        result = executor()
        self.cache_unique_values(
            layer_id, backend_type, field_name, result, filter_expr, ttl
        )
        
        return result
    
    # Count caching
    
    def cache_count(
        self,
        layer_id: str,
        backend_type: BackendType,
        expression: str,
        count: int,
        ttl: int = None,
    ) -> bool:
        """Cache feature count."""
        cache = self._get_cache(backend_type)
        if not cache:
            return False
        
        return cache.cache_count(layer_id, expression, count, ttl)
    
    def get_cached_count(
        self,
        layer_id: str,
        backend_type: BackendType,
        expression: str,
    ) -> Optional[int]:
        """Get cached feature count."""
        cache = self._get_cache(backend_type)
        if not cache:
            return None
        
        return cache.get_count(layer_id, expression)
    
    # Invalidation
    
    def invalidate_layer(self, layer_id: str) -> int:
        """Invalidate all cached data for a layer across all backends."""
        total = 0
        for cache in self._backend_caches.values():
            total += cache.invalidate_layer(layer_id)
        return total
    
    def invalidate_backend(self, backend_type: BackendType) -> int:
        """Invalidate all cached data for a backend."""
        cache = self._get_cache(backend_type)
        if cache:
            return cache.clear()
        return 0
    
    # Statistics
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all backend caches."""
        stats = {}
        for backend_type, cache in self._backend_caches.items():
            stats[backend_type.value] = cache.get_stats().to_dict()
        return stats
    
    def get_backend_stats(self, backend_type: BackendType) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific backend cache."""
        cache = self._get_cache(backend_type)
        if cache:
            return cache.get_stats().to_dict()
        return None


class CacheWarmer:
    """
    Warms cache with frequently used queries.
    
    Pre-populates cache for better initial performance.
    """
    
    def __init__(
        self,
        cache_integration: BackendCacheIntegration,
        max_queries: int = 100,
    ):
        """
        Initialize cache warmer.
        
        Args:
            cache_integration: Backend cache integration
            max_queries: Maximum queries to warm
        """
        self._integration = cache_integration
        self._max_queries = max_queries
        self._warm_queries: List[Tuple[str, BackendType, str]] = []
    
    def register_warm_query(
        self,
        layer_id: str,
        backend_type: BackendType,
        expression: str,
    ) -> None:
        """Register a query for warming."""
        query = (layer_id, backend_type, expression)
        if query not in self._warm_queries:
            self._warm_queries.append(query)
            if len(self._warm_queries) > self._max_queries:
                self._warm_queries.pop(0)
    
    def warm(
        self,
        executor: Callable[[str, str], List[int]],
    ) -> int:
        """
        Warm cache with registered queries.
        
        Args:
            executor: Function that executes query (layer_id, expression) -> ids
            
        Returns:
            Number of queries warmed
        """
        warmed = 0
        
        for layer_id, backend_type, expression in self._warm_queries:
            try:
                # Check if already cached
                if self._integration.get_cached_query(
                    layer_id, backend_type, expression
                ) is not None:
                    continue
                
                # Execute and cache
                result = executor(layer_id, expression)
                self._integration.cache_query_result(
                    layer_id, backend_type, expression, result
                )
                warmed += 1
                
            except Exception as e:
                logger.warning(f"Failed to warm cache for {layer_id}: {e}")
        
        logger.info(f"Cache warming complete: {warmed} queries warmed")
        return warmed


# Convenience function for layer-based caching
def get_layer_cache(layer) -> Optional[FilterResultCache]:
    """
    Get cache instance appropriate for a layer.
    
    Args:
        layer: QgsVectorLayer
        
    Returns:
        FilterResultCache or None
    """
    integration = BackendCacheIntegration()
    backend_type = integration.get_backend_type(layer)
    return integration._get_cache(backend_type)

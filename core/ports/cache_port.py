"""
Cache Port Interface.

Abstract interface for caching services.

This is a PURE PYTHON module with NO QGIS dependencies,
enabling true unit testing and clear separation of concerns.
"""
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, Callable, List
from dataclasses import dataclass
from datetime import datetime

K = TypeVar('K')  # Key type
V = TypeVar('V')  # Value type


@dataclass(frozen=True)
class CacheStats:
    """
    Statistics about cache usage.
    
    Attributes:
        hits: Number of cache hits
        misses: Number of cache misses
        size: Current number of entries
        max_size: Maximum allowed entries
        evictions: Number of evicted entries
        memory_bytes: Approximate memory usage in bytes
    """
    hits: int
    misses: int
    size: int
    max_size: int
    evictions: int = 0
    memory_bytes: int = 0

    @property
    def hit_rate(self) -> float:
        """
        Calculate cache hit rate.
        
        Returns:
            Hit rate as float between 0.0 and 1.0
        """
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total

    @property
    def miss_rate(self) -> float:
        """
        Calculate cache miss rate.
        
        Returns:
            Miss rate as float between 0.0 and 1.0
        """
        return 1.0 - self.hit_rate

    @property
    def is_full(self) -> bool:
        """Check if cache is at capacity."""
        return self.size >= self.max_size

    @property
    def utilization(self) -> float:
        """
        Calculate cache utilization.
        
        Returns:
            Utilization as float between 0.0 and 1.0
        """
        if self.max_size == 0:
            return 0.0
        return self.size / self.max_size

    def __str__(self) -> str:
        """Human-readable representation."""
        return (
            f"CacheStats(size={self.size}/{self.max_size}, "
            f"hit_rate={self.hit_rate:.1%}, "
            f"evictions={self.evictions})"
        )


@dataclass(frozen=True)
class CacheEntry(Generic[V]):
    """
    Wrapper for cached values with metadata.
    
    Attributes:
        value: The cached value
        created_at: When the entry was created
        expires_at: When the entry expires (None = never)
        access_count: Number of times accessed
        last_accessed: When last accessed
    """
    value: V
    created_at: datetime
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: Optional[datetime] = None

    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    @property
    def age_seconds(self) -> float:
        """Get age of entry in seconds."""
        return (datetime.now() - self.created_at).total_seconds()

    @property
    def ttl_remaining(self) -> Optional[float]:
        """Get remaining TTL in seconds, None if no expiry."""
        if self.expires_at is None:
            return None
        remaining = (self.expires_at - datetime.now()).total_seconds()
        return max(0.0, remaining)


class CachePort(ABC, Generic[K, V]):
    """
    Abstract interface for caching services.

    Generic cache that can be used for:
    - Expression results (FilterResult)
    - Layer metadata (LayerInfo)
    - Geometry objects
    - SQL query results
    
    Implementations should be thread-safe.

    Example:
        class LRUCache(CachePort[str, FilterResult]):
            def get(self, key: str) -> Optional[FilterResult]:
                # LRU cache implementation
                pass
    """

    @abstractmethod
    def get(self, key: K) -> Optional[V]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        pass

    @abstractmethod
    def set(
        self, 
        key: K, 
        value: V, 
        ttl_seconds: Optional[float] = None
    ) -> None:
        """
        Store value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Optional TTL override (None = use default)
        """
        pass

    @abstractmethod
    def delete(self, key: K) -> bool:
        """
        Remove value from cache.

        Args:
            key: Cache key

        Returns:
            True if key was found and removed
        """
        pass

    @abstractmethod
    def clear(self) -> int:
        """
        Clear all cached values.

        Returns:
            Number of entries cleared
        """
        pass

    @abstractmethod
    def has(self, key: K) -> bool:
        """
        Check if key exists in cache (and is not expired).

        Args:
            key: Cache key

        Returns:
            True if key exists and is not expired
        """
        pass

    @abstractmethod
    def get_stats(self) -> CacheStats:
        """
        Get cache statistics.

        Returns:
            CacheStats with hits, misses, size, etc.
        """
        pass

    def get_or_compute(
        self,
        key: K,
        compute_fn: Callable[[], V],
        ttl_seconds: Optional[float] = None
    ) -> V:
        """
        Get from cache or compute and cache.

        This is the primary method for cache usage, implementing
        the compute-if-absent pattern.

        Args:
            key: Cache key
            compute_fn: Function to compute value if not cached
            ttl_seconds: Optional TTL for computed value

        Returns:
            Cached or newly computed value
            
        Example:
            result = cache.get_or_compute(
                key="filter_123",
                compute_fn=lambda: expensive_filter_operation(),
                ttl_seconds=300.0
            )
        """
        value = self.get(key)
        if value is not None:
            return value

        value = compute_fn()
        self.set(key, value, ttl_seconds)
        return value

    def get_many(self, keys: List[K]) -> dict[K, V]:
        """
        Get multiple values from cache.
        
        Args:
            keys: List of cache keys
            
        Returns:
            Dictionary of found key-value pairs
        """
        result = {}
        for key in keys:
            value = self.get(key)
            if value is not None:
                result[key] = value
        return result

    def set_many(
        self, 
        items: dict[K, V], 
        ttl_seconds: Optional[float] = None
    ) -> None:
        """
        Store multiple values in cache.
        
        Args:
            items: Dictionary of key-value pairs
            ttl_seconds: Optional TTL for all items
        """
        for key, value in items.items():
            self.set(key, value, ttl_seconds)

    def delete_many(self, keys: List[K]) -> int:
        """
        Delete multiple values from cache.
        
        Args:
            keys: List of cache keys
            
        Returns:
            Number of keys deleted
        """
        count = 0
        for key in keys:
            if self.delete(key):
                count += 1
        return count

    def touch(self, key: K) -> bool:
        """
        Update access time for key without retrieving value.
        
        Useful for LRU caches to mark key as recently used.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists
        """
        # Default implementation - just check existence
        return self.has(key)

    def get_keys(self) -> List[K]:
        """
        Get all keys in cache.
        
        Returns:
            List of all cache keys
        """
        # Default implementation - subclasses should override
        return []

    def reset_stats(self) -> None:
        """Reset cache statistics to zero."""
        # Default implementation - subclasses should override
        pass


class ResultCachePort(CachePort[str, 'FilterResult']):
    """
    Specialized cache for filter results.
    
    Extends CachePort with filter-specific functionality.
    """

    def get_by_expression(
        self,
        expression_raw: str,
        layer_id: str
    ) -> Optional['FilterResult']:
        """
        Get cached result by expression and layer.
        
        Args:
            expression_raw: Filter expression string
            layer_id: Layer ID
            
        Returns:
            Cached FilterResult if found
        """
        key = self._make_key(expression_raw, layer_id)
        return self.get(key)

    def cache_result(
        self,
        result: 'FilterResult',
        ttl_seconds: Optional[float] = None
    ) -> None:
        """
        Cache a filter result.
        
        Args:
            result: FilterResult to cache
            ttl_seconds: Optional TTL
        """
        key = self._make_key(result.expression_raw, result.layer_id)
        self.set(key, result, ttl_seconds)

    def invalidate_layer(self, layer_id: str) -> int:
        """
        Invalidate all cached results for a layer.
        
        Called when layer data changes.
        
        Args:
            layer_id: Layer ID to invalidate
            
        Returns:
            Number of entries invalidated
        """
        # Default implementation - clear all
        # Subclasses should implement more efficiently
        return self.clear()

    def _make_key(self, expression_raw: str, layer_id: str) -> str:
        """Generate cache key from expression and layer."""
        return f"{layer_id}:{hash(expression_raw)}"


class GeometryCachePort(CachePort[str, 'GeometryData']):
    """
    Specialized cache for geometry data.
    
    Extends CachePort with geometry-specific functionality.
    """

    def get_layer_geometries(
        self,
        layer_id: str
    ) -> Optional['GeometryData']:
        """
        Get cached geometries for a layer.
        
        Args:
            layer_id: Layer ID
            
        Returns:
            Cached geometry data if found
        """
        return self.get(layer_id)

    def cache_geometries(
        self,
        layer_id: str,
        geometry_data: 'GeometryData',
        ttl_seconds: Optional[float] = None
    ) -> None:
        """
        Cache geometry data for a layer.
        
        Args:
            layer_id: Layer ID
            geometry_data: Geometry data to cache
            ttl_seconds: Optional TTL
        """
        self.set(layer_id, geometry_data, ttl_seconds)

    def get_memory_usage(self) -> int:
        """
        Get approximate memory usage in bytes.
        
        Returns:
            Memory usage estimate
        """
        return self.get_stats().memory_bytes


# Type hints for forward references
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.domain import FilterResult
    
    @dataclass
    class GeometryData:
        """Placeholder for geometry cache data."""
        pass

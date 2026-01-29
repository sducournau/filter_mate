# -*- coding: utf-8 -*-
"""
Unified Cache Interface for FilterMate.

v4.1.1 - January 2026 - EPIC-3 Sprint 2

PURPOSE:
Defines abstract cache interfaces for pluggable caching strategies:
1. CacheInterface - Base protocol for all cache implementations
2. CacheKey - Standardized cache key generation
3. CacheEntry - Cached value with metadata
4. CacheStats - Statistics tracking

USAGE:
    from infrastructure.cache import CacheInterface, CacheKey
    
    class MyCache(CacheInterface):
        def get(self, key: CacheKey) -> Optional[CacheEntry]:
            ...
        def set(self, key: CacheKey, value: Any, ttl: int = None) -> bool:
            ...
"""

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, List, Generic, TypeVar, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger('FilterMate.Cache')

T = TypeVar('T')


class CacheStrategy(Enum):
    """Cache eviction strategy."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In First Out
    TTL = "ttl"  # Time To Live only


@dataclass(frozen=True)
class CacheKey:
    """
    Immutable cache key with structured components.
    
    Provides consistent hashing for cache lookups.
    
    Example:
        key = CacheKey(
            namespace="filter",
            layer_id="layer_123",
            expression="status = 1",
        )
        hash_value = key.hash()
    """
    namespace: str
    layer_id: str = ""
    expression: str = ""
    params: tuple = ()  # Use tuple for hashability
    
    def hash(self) -> str:
        """Generate SHA256 hash of key components."""
        components = [
            self.namespace,
            self.layer_id,
            self.expression,
            str(self.params),
        ]
        key_string = "|".join(components)
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]
    
    def __str__(self) -> str:
        return f"{self.namespace}:{self.layer_id}:{self.hash()}"
    
    @classmethod
    def from_filter(
        cls,
        layer_id: str,
        expression: str,
        params: Dict[str, Any] = None,
    ) -> 'CacheKey':
        """Create cache key from filter parameters."""
        param_tuple = tuple(sorted(params.items())) if params else ()
        return cls(
            namespace="filter",
            layer_id=layer_id,
            expression=expression,
            params=param_tuple,
        )
    
    @classmethod
    def from_unique_values(
        cls,
        layer_id: str,
        field_name: str,
        filter_expr: str = "",
    ) -> 'CacheKey':
        """Create cache key for unique values query."""
        return cls(
            namespace="unique_values",
            layer_id=layer_id,
            expression=filter_expr,
            params=(field_name,),
        )
    
    @classmethod
    def from_spatial(
        cls,
        layer_id: str,
        operation: str,
        bbox: tuple = None,
    ) -> 'CacheKey':
        """Create cache key for spatial query."""
        return cls(
            namespace="spatial",
            layer_id=layer_id,
            expression=operation,
            params=bbox or (),
        )


@dataclass
class CacheEntry(Generic[T]):
    """
    Cached value with metadata.
    
    Tracks creation time, access patterns, and TTL.
    """
    value: T
    key: CacheKey
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    size_bytes: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
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
    
    def touch(self) -> None:
        """Update access time and count."""
        self.access_count += 1
        self.last_accessed = datetime.now()
    
    def set_ttl(self, seconds: int) -> None:
        """Set time-to-live in seconds."""
        self.expires_at = datetime.now() + timedelta(seconds=seconds)


@dataclass
class CacheStats:
    """
    Cache statistics for monitoring and tuning.
    """
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    insertions: int = 0
    current_size: int = 0
    max_size: int = 0
    total_size_bytes: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate."""
        return 1.0 - self.hit_rate
    
    def record_hit(self) -> None:
        """Record a cache hit."""
        self.hits += 1
    
    def record_miss(self) -> None:
        """Record a cache miss."""
        self.misses += 1
    
    def record_eviction(self) -> None:
        """Record an eviction."""
        self.evictions += 1
    
    def record_insertion(self, size_bytes: int = 0) -> None:
        """Record an insertion."""
        self.insertions += 1
        self.current_size += 1
        self.total_size_bytes += size_bytes
        self.max_size = max(self.max_size, self.current_size)
    
    def record_removal(self, size_bytes: int = 0) -> None:
        """Record a removal."""
        self.current_size = max(0, self.current_size - 1)
        self.total_size_bytes = max(0, self.total_size_bytes - size_bytes)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'hits': self.hits,
            'misses': self.misses,
            'evictions': self.evictions,
            'insertions': self.insertions,
            'current_size': self.current_size,
            'max_size': self.max_size,
            'total_size_bytes': self.total_size_bytes,
            'hit_rate': self.hit_rate,
        }
    
    def __str__(self) -> str:
        return (
            f"CacheStats(hits={self.hits}, misses={self.misses}, "
            f"hit_rate={self.hit_rate:.2%}, size={self.current_size})"
        )


class CacheInterface(ABC, Generic[T]):
    """
    Abstract base class for cache implementations.
    
    Defines the contract that all cache implementations must follow.
    
    Example implementation:
        class InMemoryCache(CacheInterface):
            def get(self, key):
                return self._storage.get(key.hash())
            
            def set(self, key, value, ttl=None):
                self._storage[key.hash()] = value
                return True
    """
    
    @abstractmethod
    def get(self, key: CacheKey) -> Optional[CacheEntry[T]]:
        """
        Retrieve cached value.
        
        Args:
            key: Cache key
            
        Returns:
            CacheEntry if found and not expired, None otherwise
        """
        pass
    
    @abstractmethod
    def set(
        self,
        key: CacheKey,
        value: T,
        ttl: int = None,
        metadata: Dict[str, Any] = None,
    ) -> bool:
        """
        Store value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (None for no expiration)
            metadata: Optional metadata to store with entry
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def delete(self, key: CacheKey) -> bool:
        """
        Delete cached value.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted, False if not found
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
    def exists(self, key: CacheKey) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists and not expired
        """
        pass
    
    @abstractmethod
    def get_stats(self) -> CacheStats:
        """
        Get cache statistics.
        
        Returns:
            CacheStats object
        """
        pass
    
    def get_or_set(
        self,
        key: CacheKey,
        factory: Callable[[], T],
        ttl: int = None,
    ) -> T:
        """
        Get cached value or compute and cache it.
        
        Args:
            key: Cache key
            factory: Function to compute value if not cached
            ttl: Time-to-live in seconds
            
        Returns:
            Cached or computed value
        """
        entry = self.get(key)
        if entry is not None:
            return entry.value
        
        value = factory()
        self.set(key, value, ttl)
        return value
    
    def invalidate_by_prefix(self, prefix: str) -> int:
        """
        Invalidate all keys with given prefix.
        
        Args:
            prefix: Key prefix to match
            
        Returns:
            Number of entries invalidated
        """
        # Default implementation - subclasses may override for efficiency
        return 0
    
    def invalidate_by_layer(self, layer_id: str) -> int:
        """
        Invalidate all cache entries for a layer.
        
        Args:
            layer_id: Layer ID
            
        Returns:
            Number of entries invalidated
        """
        # Default implementation - subclasses may override for efficiency
        return 0


@dataclass
class CacheConfig:
    """Configuration for cache instances."""
    max_size: int = 1000
    default_ttl: int = 300  # 5 minutes
    strategy: CacheStrategy = CacheStrategy.LRU
    enable_stats: bool = True
    max_memory_mb: float = 100.0
    cleanup_interval: int = 60  # seconds
    
    def validate(self) -> bool:
        """Validate configuration."""
        if self.max_size <= 0:
            raise ValueError("max_size must be positive")
        if self.default_ttl < 0:
            raise ValueError("default_ttl cannot be negative")
        if self.max_memory_mb <= 0:
            raise ValueError("max_memory_mb must be positive")
        return True


class CacheManager:
    """
    Manages multiple cache instances.
    
    Provides centralized access to different cache types
    (filter cache, spatial cache, etc.).
    """
    
    def __init__(self):
        self._caches: Dict[str, CacheInterface] = {}
        self._configs: Dict[str, CacheConfig] = {}
    
    def register(
        self,
        name: str,
        cache: CacheInterface,
        config: CacheConfig = None,
    ) -> None:
        """
        Register a cache instance.
        
        Args:
            name: Cache name
            cache: Cache instance
            config: Optional configuration
        """
        self._caches[name] = cache
        self._configs[name] = config or CacheConfig()
        logger.info(f"Registered cache: {name}")
    
    def get_cache(self, name: str) -> Optional[CacheInterface]:
        """
        Get a cache instance by name.
        
        Args:
            name: Cache name
            
        Returns:
            Cache instance or None
        """
        return self._caches.get(name)
    
    def get_all_stats(self) -> Dict[str, CacheStats]:
        """
        Get statistics for all caches.
        
        Returns:
            Dict mapping cache name to stats
        """
        return {
            name: cache.get_stats()
            for name, cache in self._caches.items()
        }
    
    def clear_all(self) -> Dict[str, int]:
        """
        Clear all caches.
        
        Returns:
            Dict mapping cache name to entries cleared
        """
        results = {}
        for name, cache in self._caches.items():
            results[name] = cache.clear()
        return results
    
    def invalidate_layer(self, layer_id: str) -> Dict[str, int]:
        """
        Invalidate all cache entries for a layer across all caches.
        
        Args:
            layer_id: Layer ID
            
        Returns:
            Dict mapping cache name to entries invalidated
        """
        results = {}
        for name, cache in self._caches.items():
            results[name] = cache.invalidate_by_layer(layer_id)
        return results


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


def reset_cache_manager() -> None:
    """Reset global cache manager (for testing)."""
    global _cache_manager
    _cache_manager = None

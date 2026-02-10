"""
Unified Cache Manager for FilterMate

Centralizes all caching operations with a common interface (CachePort).
Implements the plan from ANALYSE-EXHAUSTIVE-MIGRATION-20260114.md (Priority 2).

This manager provides:
- Unified cache policy (LRU, TTL)
- Centralized statistics
- Single configuration point
- Consistent eviction strategies

Architecture:
    infrastructure/cache/
    ├── cache_manager.py          ← This file (singleton)
    ├── geometry_cache.py          ← Implements CachePort[str, Geometry]
    ├── expression_cache.py        ← Implements CachePort[str, Expression]
    └── result_cache.py            ← Implements CachePort[str, FilterResult]

Author: FilterMate Team (BMAD optimization)
Date: January 14, 2026
"""

import logging
from typing import Dict, Optional, TypeVar, Any, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger('FilterMate.Infrastructure.CacheManager')

K = TypeVar('K')  # Key type
V = TypeVar('V')  # Value type


class CachePolicy(Enum):
    """Cache eviction policies."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In First Out
    TTL = "ttl"  # Time To Live


@dataclass
class CacheConfig:
    """
    Configuration for cache instances.

    Attributes:
        max_size: Maximum number of entries (0 = unlimited)
        policy: Eviction policy
        ttl_seconds: Time to live in seconds (for TTL policy)
        enable_stats: Whether to track statistics
        name: Cache name for logging
    """
    max_size: int = 100
    policy: CachePolicy = CachePolicy.LRU
    ttl_seconds: int = 3600  # 1 hour default
    enable_stats: bool = True
    name: str = "cache"


@dataclass
class CacheStats:
    """
    Cache statistics for monitoring and debugging.

    Attributes:
        hits: Number of successful cache retrievals
        misses: Number of cache misses
        evictions: Number of entries evicted
        total_size: Current cache size
        max_size: Maximum cache size
        hit_rate: Cache hit rate (hits / total requests)
    """
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_size: int = 0
    max_size: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def requests(self) -> int:
        """Total number of requests."""
        return self.hits + self.misses

    def __str__(self) -> str:
        """String representation."""
        return (
            f"CacheStats(hits={self.hits}, misses={self.misses}, "
            f"evictions={self.evictions}, size={self.total_size}/{self.max_size}, "
            f"hit_rate={self.hit_rate:.2%})"
        )


class CacheManager:
    """
    Singleton cache manager for unified cache operations.

    Provides centralized access to all cache instances with consistent
    configuration and statistics.

    Usage:
        # Get singleton instance
        manager = CacheManager.get_instance()

        # Register caches
        manager.register_cache('geometry', geometry_cache)
        manager.register_cache('expression', expression_cache)

        # Get cache
        geom_cache = manager.get_cache('geometry')

        # Global operations
        manager.clear_all()
        stats = manager.get_global_stats()
    """

    _instance: Optional['CacheManager'] = None

    def __init__(self):
        """
        Initialize cache manager.

        Note: Use get_instance() instead of direct instantiation.
        """
        self._caches: Dict[str, Any] = {}
        self._configs: Dict[str, CacheConfig] = {}
        self._stats: Dict[str, CacheStats] = {}
        logger.info("CacheManager initialized")

    @classmethod
    def get_instance(cls) -> 'CacheManager':
        """
        Get singleton instance of CacheManager.

        Returns:
            CacheManager singleton instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset singleton (useful for testing)."""
        cls._instance = None

    def register_cache(
        self,
        name: str,
        cache_instance: Any,
        config: Optional[CacheConfig] = None
    ):
        """
        Register a cache instance.

        Args:
            name: Unique cache name
            cache_instance: Cache instance implementing CachePort
            config: Optional cache configuration
        """
        if name in self._caches:
            logger.warning(f"Cache '{name}' already registered, replacing")

        self._caches[name] = cache_instance
        self._configs[name] = config or CacheConfig(name=name)
        self._stats[name] = CacheStats()

        logger.info(f"Registered cache: {name} with policy {config.policy if config else 'default'}")

    def get_cache(self, name: str) -> Optional[Any]:
        """
        Get registered cache by name.

        Args:
            name: Cache name

        Returns:
            Cache instance or None if not found
        """
        return self._caches.get(name)

    def get_config(self, name: str) -> Optional[CacheConfig]:
        """
        Get cache configuration.

        Args:
            name: Cache name

        Returns:
            Cache configuration or None
        """
        return self._configs.get(name)

    def get_stats(self, name: str) -> Optional[CacheStats]:
        """
        Get cache statistics.

        Args:
            name: Cache name

        Returns:
            Cache statistics or None
        """
        return self._stats.get(name)

    def get_global_stats(self) -> Dict[str, CacheStats]:
        """
        Get statistics for all caches.

        Returns:
            Dictionary of cache name -> statistics
        """
        return self._stats.copy()

    def clear_cache(self, name: str):
        """
        Clear specific cache.

        Args:
            name: Cache name
        """
        cache = self._caches.get(name)
        if cache and hasattr(cache, 'clear'):
            cache.clear()
            logger.info(f"Cleared cache: {name}")
        else:
            logger.warning(f"Cache '{name}' not found or doesn't support clear()")

    def clear_all(self):
        """Clear all registered caches."""
        for name in list(self._caches.keys()):
            self.clear_cache(name)
        logger.info("Cleared all caches")

    def update_stats(self, name: str, hit: bool = False, miss: bool = False, eviction: bool = False):
        """
        Update cache statistics.

        Args:
            name: Cache name
            hit: Increment hit counter
            miss: Increment miss counter
            eviction: Increment eviction counter
        """
        if name not in self._stats:
            self._stats[name] = CacheStats()

        stats = self._stats[name]
        if hit:
            stats.hits += 1
        if miss:
            stats.misses += 1
        if eviction:
            stats.evictions += 1

        # Update size
        cache = self._caches.get(name)
        if cache and hasattr(cache, 'size'):
            stats.total_size = cache.size()

        config = self._configs.get(name)
        if config:
            stats.max_size = config.max_size

    def get_summary(self) -> str:
        """
        Get summary of all caches.

        Returns:
            Formatted string with cache statistics
        """
        lines = ["Cache Manager Summary", "=" * 50]

        for name, stats in self._stats.items():
            config = self._configs.get(name)
            lines.append(f"\n{name}:")
            lines.append(f"  Policy: {config.policy.value if config else 'unknown'}")
            lines.append(f"  {stats}")

        return "\n".join(lines)

    def list_caches(self) -> List[str]:
        """
        Get list of registered cache names.

        Returns:
            List of cache names
        """
        return list(self._caches.keys())


# Global convenience functions

def get_cache_manager() -> CacheManager:
    """
    Get global cache manager instance.

    Returns:
        CacheManager singleton
    """
    return CacheManager.get_instance()


def clear_all_caches():
    """Clear all registered caches."""
    get_cache_manager().clear_all()


def get_cache_summary() -> str:
    """
    Get summary of all caches.

    Returns:
        Formatted summary string
    """
    return get_cache_manager().get_summary()

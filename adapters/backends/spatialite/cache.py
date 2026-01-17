# -*- coding: utf-8 -*-
"""
FilterMate Spatialite Cache - ARCH-041

Cache for Spatialite filter results and geometries.
Provides memory-efficient caching with TTL support.

Part of Phase 4 Backend Refactoring.

Features:
- LRU eviction policy
- TTL-based expiration
- Thread-safe operations
- Memory-aware sizing

Author: FilterMate Team
Date: January 2026
"""

import logging
import hashlib
import threading
from typing import Optional, Any, Dict, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import OrderedDict

logger = logging.getLogger('FilterMate.Spatialite.Cache')


@dataclass
class CacheEntry:
    """Entry in the cache with TTL support."""
    value: Any
    created_at: datetime
    expires_at: Optional[datetime]
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    size_bytes: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def touch(self) -> None:
        """Update access statistics."""
        self.access_count += 1
        self.last_accessed = datetime.now()


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int
    misses: int
    evictions: int
    current_size: int
    max_size: int
    memory_bytes: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def miss_rate(self) -> float:
        """Calculate miss rate."""
        return 1.0 - self.hit_rate

    @property
    def utilization(self) -> float:
        """Calculate utilization percentage."""
        return self.current_size / self.max_size if self.max_size > 0 else 0.0


class SpatialiteCache:
    """
    Cache for Spatialite filter results and geometries.

    Features:
    - LRU eviction policy
    - TTL-based expiration
    - Separate caches for results and geometries
    - Thread-safe operations
    - Memory-aware sizing

    Example:
        cache = SpatialiteCache(max_entries=100, ttl_seconds=300)

        # Cache filter result
        cache.set_result(layer_id, expression, feature_ids)

        # Retrieve cached result
        result = cache.get_result(layer_id, expression)
    """

    def __init__(
        self,
        max_entries: int = 100,
        ttl_seconds: float = 300.0,
        max_geometry_cache_mb: float = 50.0
    ):
        """
        Initialize cache.

        Args:
            max_entries: Maximum cache entries
            ttl_seconds: Default TTL for entries
            max_geometry_cache_mb: Max memory for geometry cache
        """
        self._max_entries = max_entries
        self._default_ttl = timedelta(seconds=ttl_seconds)
        self._max_geom_bytes = int(max_geometry_cache_mb * 1024 * 1024)

        # Separate caches
        self._result_cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._geometry_cache: OrderedDict[str, CacheEntry] = OrderedDict()

        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._current_geom_bytes = 0

        # Thread safety
        self._lock = threading.RLock()

        logger.debug(
            f"SpatialiteCache initialized: max_entries={max_entries}, "
            f"ttl={ttl_seconds}s, max_geom={max_geometry_cache_mb}MB"
        )

    # === Result Cache ===

    def get_result(
        self,
        layer_id: str,
        expression: str
    ) -> Optional[Tuple[int, ...]]:
        """
        Get cached filter result.

        Args:
            layer_id: Layer identifier
            expression: Filter expression

        Returns:
            Tuple of feature IDs or None if not cached
        """
        key = self._make_result_key(layer_id, expression)

        with self._lock:
            entry = self._result_cache.get(key)

            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired:
                del self._result_cache[key]
                self._misses += 1
                return None

            # Move to end (LRU)
            self._result_cache.move_to_end(key)
            entry.touch()
            self._hits += 1

            return entry.value

    def set_result(
        self,
        layer_id: str,
        expression: str,
        feature_ids: Tuple[int, ...],
        ttl_seconds: Optional[float] = None
    ) -> None:
        """
        Cache filter result.

        Args:
            layer_id: Layer identifier
            expression: Filter expression
            feature_ids: Feature IDs to cache
            ttl_seconds: Optional TTL override
        """
        key = self._make_result_key(layer_id, expression)
        ttl = timedelta(seconds=ttl_seconds) if ttl_seconds else self._default_ttl

        with self._lock:
            # Evict if at capacity
            while len(self._result_cache) >= self._max_entries:
                self._evict_oldest_result()

            self._result_cache[key] = CacheEntry(
                value=feature_ids,
                created_at=datetime.now(),
                expires_at=datetime.now() + ttl
            )

    def has_result(
        self,
        layer_id: str,
        expression: str
    ) -> bool:
        """Check if result is in cache (without touching)."""
        key = self._make_result_key(layer_id, expression)

        with self._lock:
            entry = self._result_cache.get(key)
            return entry is not None and not entry.is_expired

    # === Geometry Cache ===

    def get_geometry(
        self,
        layer_id: str,
        feature_id: int
    ) -> Optional[bytes]:
        """
        Get cached geometry WKB.

        Args:
            layer_id: Layer identifier
            feature_id: Feature ID

        Returns:
            Geometry WKB bytes or None if not cached
        """
        key = f"{layer_id}:geom:{feature_id}"

        with self._lock:
            entry = self._geometry_cache.get(key)

            if entry is None:
                return None

            if entry.is_expired:
                self._current_geom_bytes -= entry.size_bytes
                del self._geometry_cache[key]
                return None

            self._geometry_cache.move_to_end(key)
            entry.touch()
            return entry.value

    def set_geometry(
        self,
        layer_id: str,
        feature_id: int,
        geometry_wkb: bytes,
        ttl_seconds: Optional[float] = None
    ) -> None:
        """
        Cache geometry WKB.

        Args:
            layer_id: Layer identifier
            feature_id: Feature ID
            geometry_wkb: WKB bytes
            ttl_seconds: Optional TTL override
        """
        key = f"{layer_id}:geom:{feature_id}"
        size = len(geometry_wkb)
        ttl = timedelta(seconds=ttl_seconds) if ttl_seconds else self._default_ttl

        with self._lock:
            # Evict if over memory limit
            while self._current_geom_bytes + size > self._max_geom_bytes:
                if not self._evict_oldest_geometry():
                    break

            self._geometry_cache[key] = CacheEntry(
                value=geometry_wkb,
                created_at=datetime.now(),
                expires_at=datetime.now() + ttl,
                size_bytes=size
            )
            self._current_geom_bytes += size

    def get_geometries_batch(
        self,
        layer_id: str,
        feature_ids: Tuple[int, ...]
    ) -> Dict[int, bytes]:
        """
        Get multiple cached geometries.

        Args:
            layer_id: Layer identifier
            feature_ids: Feature IDs to retrieve

        Returns:
            Dict mapping feature_id to WKB bytes (only cached ones)
        """
        result = {}
        for fid in feature_ids:
            geom = self.get_geometry(layer_id, fid)
            if geom is not None:
                result[fid] = geom
        return result

    # === Layer Operations ===

    def invalidate_layer(self, layer_id: str) -> int:
        """
        Invalidate all cache entries for a layer.

        Args:
            layer_id: Layer to invalidate

        Returns:
            Number of entries invalidated
        """
        count = 0
        prefix = f"{layer_id}:"

        with self._lock:
            # Result cache
            keys_to_remove = [k for k in self._result_cache.keys() if k.startswith(prefix)]
            for key in keys_to_remove:
                del self._result_cache[key]
                count += 1

            # Geometry cache
            keys_to_remove = [k for k in self._geometry_cache.keys() if k.startswith(prefix)]
            for key in keys_to_remove:
                entry = self._geometry_cache[key]
                self._current_geom_bytes -= entry.size_bytes
                del self._geometry_cache[key]
                count += 1

        logger.debug(f"[Spatialite] Invalidated {count} cache entries for layer {layer_id}")
        return count

    # === Statistics ===

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        with self._lock:
            return CacheStats(
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
                current_size=len(self._result_cache) + len(self._geometry_cache),
                max_size=self._max_entries,
                memory_bytes=self._current_geom_bytes
            )

    def clear(self) -> int:
        """
        Clear all caches.

        Returns:
            Number of entries cleared
        """
        with self._lock:
            count = len(self._result_cache) + len(self._geometry_cache)
            self._result_cache.clear()
            self._geometry_cache.clear()
            self._current_geom_bytes = 0
            self._hits = 0
            self._misses = 0
            self._evictions = 0
            return count

    def cleanup_expired(self) -> int:
        """
        Remove expired entries.

        Returns:
            Number of entries removed
        """
        count = 0

        with self._lock:
            # Result cache
            expired_keys = [
                k for k, v in self._result_cache.items() if v.is_expired
            ]
            for key in expired_keys:
                del self._result_cache[key]
                count += 1

            # Geometry cache
            expired_keys = [
                k for k, v in self._geometry_cache.items() if v.is_expired
            ]
            for key in expired_keys:
                entry = self._geometry_cache[key]
                self._current_geom_bytes -= entry.size_bytes
                del self._geometry_cache[key]
                count += 1

        if count > 0:
            logger.debug(f"[Spatialite] Cleaned up {count} expired cache entries")
        return count

    # === Private Methods ===

    def _make_result_key(self, layer_id: str, expression: str) -> str:
        """Create cache key for result."""
        expr_hash = hashlib.md5(expression.encode()).hexdigest()[:12]
        return f"{layer_id}:{expr_hash}"

    def _evict_oldest_result(self) -> bool:
        """Evict oldest result cache entry."""
        if self._result_cache:
            self._result_cache.popitem(last=False)
            self._evictions += 1
            return True
        return False

    def _evict_oldest_geometry(self) -> bool:
        """Evict oldest geometry cache entry."""
        if self._geometry_cache:
            _, entry = self._geometry_cache.popitem(last=False)
            self._current_geom_bytes -= entry.size_bytes
            self._evictions += 1
            return True
        return False


def create_cache(
    max_entries: int = 100,
    ttl_seconds: float = 300.0,
    max_geometry_cache_mb: float = 50.0
) -> SpatialiteCache:
    """
    Factory function for SpatialiteCache.

    Args:
        max_entries: Maximum cache entries
        ttl_seconds: Default TTL for entries
        max_geometry_cache_mb: Max memory for geometry cache

    Returns:
        Configured SpatialiteCache instance
    """
    return SpatialiteCache(
        max_entries=max_entries,
        ttl_seconds=ttl_seconds,
        max_geometry_cache_mb=max_geometry_cache_mb
    )

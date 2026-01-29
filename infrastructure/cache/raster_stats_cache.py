# -*- coding: utf-8 -*-
"""
Raster Statistics Cache.

EPIC-2: Raster Integration
US-10: Statistics Caching

Provides efficient caching for raster statistics computation results,
reducing repeated calculations for large raster files.

Features:
- LRU eviction with configurable size limit
- TTL-based expiration for stale data
- Layer-specific cache invalidation
- Memory-efficient storage
- Thread-safe operations

Author: FilterMate Team
Date: January 2026
"""
import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import (
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    TypeVar,
)

logger = logging.getLogger('FilterMate.Infrastructure.RasterStatsCache')

# Type variables for generic cache
K = TypeVar('K')  # Key type
V = TypeVar('V')  # Value type


# =============================================================================
# Cache Entry
# =============================================================================

@dataclass
class CacheEntry(Generic[V]):
    """
    Individual cache entry with metadata.

    Attributes:
        value: Cached value
        created_at: When the entry was created
        last_accessed: When the entry was last accessed
        access_count: Number of times accessed
        size_bytes: Approximate memory size in bytes
    """
    value: V
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    size_bytes: int = 0

    def touch(self) -> None:
        """Update last accessed time and increment count."""
        self.last_accessed = datetime.now()
        self.access_count += 1

    @property
    def age_seconds(self) -> float:
        """Get age of entry in seconds."""
        return (datetime.now() - self.created_at).total_seconds()

    def is_expired(self, ttl_seconds: int) -> bool:
        """Check if entry has expired based on TTL."""
        return self.age_seconds > ttl_seconds


# =============================================================================
# Raster Stats Cache
# =============================================================================

@dataclass
class RasterStatsCacheConfig:
    """
    Configuration for raster statistics cache.

    Attributes:
        max_entries: Maximum number of cached layers
        max_memory_mb: Maximum memory usage in MB
        ttl_seconds: Time to live in seconds (0 = no expiration)
        enable_histograms: Whether to cache histogram data
        histogram_memory_limit_mb: Max memory for histograms
    """
    max_entries: int = 50
    max_memory_mb: float = 100.0
    ttl_seconds: int = 3600  # 1 hour default
    enable_histograms: bool = True
    histogram_memory_limit_mb: float = 50.0


@dataclass
class RasterStatsCacheStats:
    """
    Statistics for monitoring cache performance.

    Attributes:
        hits: Successful cache retrievals
        misses: Cache misses
        evictions: Number of evicted entries
        memory_bytes: Current memory usage
        histogram_hits: Histogram-specific hits
        histogram_misses: Histogram-specific misses
    """
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    memory_bytes: int = 0
    histogram_hits: int = 0
    histogram_misses: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate overall hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def histogram_hit_rate(self) -> float:
        """Calculate histogram hit rate."""
        total = self.histogram_hits + self.histogram_misses
        return self.histogram_hits / total if total > 0 else 0.0

    @property
    def memory_mb(self) -> float:
        """Memory usage in megabytes."""
        return self.memory_bytes / (1024 * 1024)


class RasterStatsCache:
    """
    LRU cache for raster layer statistics.

    Stores computed statistics for raster layers to avoid
    repeated calculations. Supports TTL-based expiration
    and memory-based eviction.

    Thread Safety:
        This cache is thread-safe. All operations are protected
        by a lock for concurrent access.

    Example:
        >>> cache = RasterStatsCache(config)
        >>> cache.put("layer_123", stats_response)
        >>> if cache.has("layer_123"):
        ...     response = cache.get("layer_123")
    """

    def __init__(
        self,
        config: Optional[RasterStatsCacheConfig] = None
    ) -> None:
        """
        Initialize the raster stats cache.

        Args:
            config: Cache configuration (uses defaults if None)
        """
        self._config = config or RasterStatsCacheConfig()
        self._lock = threading.RLock()

        # Main cache storage (OrderedDict for LRU)
        self._stats_cache: OrderedDict[str, CacheEntry] = OrderedDict()

        # Histogram cache (separate for memory management)
        self._histogram_cache: OrderedDict[str, CacheEntry] = OrderedDict()

        # Statistics
        self._stats = RasterStatsCacheStats()

        logger.debug(
            f"[RasterStatsCache] Initialized with max_entries="
            f"{self._config.max_entries}, ttl={self._config.ttl_seconds}s"
        )

    # =========================================================================
    # Public API - Statistics
    # =========================================================================

    def get_stats(
        self,
        layer_id: str,
        band: Optional[int] = None
    ) -> Optional[object]:
        """
        Get cached statistics for a layer.

        Args:
            layer_id: Layer identifier
            band: Optional band number (for band-specific stats)

        Returns:
            Cached statistics or None if not found/expired
        """
        cache_key = self._make_stats_key(layer_id, band)

        with self._lock:
            entry = self._stats_cache.get(cache_key)

            if entry is None:
                self._stats.misses += 1
                return None

            # Check expiration
            if self._config.ttl_seconds > 0:
                if entry.is_expired(self._config.ttl_seconds):
                    self._evict_stats_entry(cache_key)
                    self._stats.misses += 1
                    return None

            # Update LRU order
            self._stats_cache.move_to_end(cache_key)
            entry.touch()
            self._stats.hits += 1

            logger.debug(f"[RasterStatsCache] Hit for {cache_key}")
            return entry.value

    def put_stats(
        self,
        layer_id: str,
        stats: object,
        band: Optional[int] = None,
        size_bytes: int = 0
    ) -> None:
        """
        Cache statistics for a layer.

        Args:
            layer_id: Layer identifier
            stats: Statistics object to cache
            band: Optional band number
            size_bytes: Approximate size in bytes
        """
        cache_key = self._make_stats_key(layer_id, band)

        with self._lock:
            # Evict if at capacity
            while len(self._stats_cache) >= self._config.max_entries:
                self._evict_oldest_stats()

            # Create entry
            entry = CacheEntry(
                value=stats,
                size_bytes=size_bytes
            )

            self._stats_cache[cache_key] = entry
            self._stats.memory_bytes += size_bytes

            logger.debug(
                f"[RasterStatsCache] Cached stats for {cache_key} "
                f"({size_bytes} bytes)"
            )

    def has_stats(
        self,
        layer_id: str,
        band: Optional[int] = None
    ) -> bool:
        """
        Check if statistics are cached (and not expired).

        Args:
            layer_id: Layer identifier
            band: Optional band number

        Returns:
            True if valid cache entry exists
        """
        cache_key = self._make_stats_key(layer_id, band)

        with self._lock:
            entry = self._stats_cache.get(cache_key)
            if entry is None:
                return False

            if self._config.ttl_seconds > 0:
                if entry.is_expired(self._config.ttl_seconds):
                    return False

            return True

    # =========================================================================
    # Public API - Histograms
    # =========================================================================

    def get_histogram(
        self,
        layer_id: str,
        band: int
    ) -> Optional[object]:
        """
        Get cached histogram for a layer band.

        Args:
            layer_id: Layer identifier
            band: Band number

        Returns:
            Cached histogram data or None
        """
        if not self._config.enable_histograms:
            return None

        cache_key = self._make_histogram_key(layer_id, band)

        with self._lock:
            entry = self._histogram_cache.get(cache_key)

            if entry is None:
                self._stats.histogram_misses += 1
                return None

            # Check expiration
            if self._config.ttl_seconds > 0:
                if entry.is_expired(self._config.ttl_seconds):
                    self._evict_histogram_entry(cache_key)
                    self._stats.histogram_misses += 1
                    return None

            # Update LRU
            self._histogram_cache.move_to_end(cache_key)
            entry.touch()
            self._stats.histogram_hits += 1

            logger.debug(f"[RasterStatsCache] Histogram hit for {cache_key}")
            return entry.value

    def put_histogram(
        self,
        layer_id: str,
        band: int,
        histogram: object,
        size_bytes: int = 0
    ) -> None:
        """
        Cache histogram data for a layer band.

        Args:
            layer_id: Layer identifier
            band: Band number
            histogram: Histogram data to cache
            size_bytes: Approximate size in bytes
        """
        if not self._config.enable_histograms:
            return

        cache_key = self._make_histogram_key(layer_id, band)

        with self._lock:
            # Check memory limit
            hist_memory_limit = int(
                self._config.histogram_memory_limit_mb * 1024 * 1024
            )
            current_hist_memory = sum(
                e.size_bytes for e in self._histogram_cache.values()
            )

            # Evict if over limit
            while (
                current_hist_memory + size_bytes > hist_memory_limit
                and self._histogram_cache
            ):
                self._evict_oldest_histogram()
                current_hist_memory = sum(
                    e.size_bytes for e in self._histogram_cache.values()
                )

            # Create entry
            entry = CacheEntry(
                value=histogram,
                size_bytes=size_bytes
            )

            self._histogram_cache[cache_key] = entry
            self._stats.memory_bytes += size_bytes

            logger.debug(
                f"[RasterStatsCache] Cached histogram for {cache_key} "
                f"({size_bytes} bytes)"
            )

    def has_histogram(
        self,
        layer_id: str,
        band: int
    ) -> bool:
        """Check if histogram is cached."""
        if not self._config.enable_histograms:
            return False

        cache_key = self._make_histogram_key(layer_id, band)

        with self._lock:
            entry = self._histogram_cache.get(cache_key)
            if entry is None:
                return False

            if self._config.ttl_seconds > 0:
                if entry.is_expired(self._config.ttl_seconds):
                    return False

            return True

    # =========================================================================
    # Cache Management
    # =========================================================================

    def invalidate_layer(self, layer_id: str) -> int:
        """
        Invalidate all cached data for a layer.

        Args:
            layer_id: Layer to invalidate

        Returns:
            Number of entries removed
        """
        removed = 0

        with self._lock:
            # Remove stats entries
            keys_to_remove = [
                k for k in self._stats_cache.keys()
                if k.startswith(f"{layer_id}:")
            ]
            for key in keys_to_remove:
                self._evict_stats_entry(key)
                removed += 1

            # Remove histogram entries
            keys_to_remove = [
                k for k in self._histogram_cache.keys()
                if k.startswith(f"{layer_id}:")
            ]
            for key in keys_to_remove:
                self._evict_histogram_entry(key)
                removed += 1

        logger.debug(
            f"[RasterStatsCache] Invalidated {removed} entries for {layer_id}"
        )
        return removed

    def clear(self) -> None:
        """Clear all cached data."""
        with self._lock:
            self._stats_cache.clear()
            self._histogram_cache.clear()
            self._stats.memory_bytes = 0
            logger.debug("[RasterStatsCache] Cache cleared")

    def get_cache_stats(self) -> RasterStatsCacheStats:
        """Get cache statistics."""
        with self._lock:
            return RasterStatsCacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                evictions=self._stats.evictions,
                memory_bytes=self._stats.memory_bytes,
                histogram_hits=self._stats.histogram_hits,
                histogram_misses=self._stats.histogram_misses
            )

    @property
    def size(self) -> int:
        """Get total number of cached entries."""
        with self._lock:
            return len(self._stats_cache) + len(self._histogram_cache)

    @property
    def stats_count(self) -> int:
        """Get number of cached stats entries."""
        with self._lock:
            return len(self._stats_cache)

    @property
    def histogram_count(self) -> int:
        """Get number of cached histogram entries."""
        with self._lock:
            return len(self._histogram_cache)

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _make_stats_key(
        self,
        layer_id: str,
        band: Optional[int]
    ) -> str:
        """Create cache key for stats."""
        if band is None:
            return f"{layer_id}:stats:all"
        return f"{layer_id}:stats:band{band}"

    def _make_histogram_key(self, layer_id: str, band: int) -> str:
        """Create cache key for histogram."""
        return f"{layer_id}:histogram:band{band}"

    def _evict_oldest_stats(self) -> None:
        """Evict oldest (LRU) stats entry."""
        if not self._stats_cache:
            return

        oldest_key = next(iter(self._stats_cache))
        self._evict_stats_entry(oldest_key)

    def _evict_stats_entry(self, key: str) -> None:
        """Remove a specific stats entry."""
        if key in self._stats_cache:
            entry = self._stats_cache.pop(key)
            self._stats.memory_bytes -= entry.size_bytes
            self._stats.evictions += 1
            logger.debug(f"[RasterStatsCache] Evicted stats: {key}")

    def _evict_oldest_histogram(self) -> None:
        """Evict oldest histogram entry."""
        if not self._histogram_cache:
            return

        oldest_key = next(iter(self._histogram_cache))
        self._evict_histogram_entry(oldest_key)

    def _evict_histogram_entry(self, key: str) -> None:
        """Remove a specific histogram entry."""
        if key in self._histogram_cache:
            entry = self._histogram_cache.pop(key)
            self._stats.memory_bytes -= entry.size_bytes
            self._stats.evictions += 1
            logger.debug(f"[RasterStatsCache] Evicted histogram: {key}")


# =============================================================================
# Global Cache Instance
# =============================================================================

_global_raster_cache: Optional[RasterStatsCache] = None


def get_raster_stats_cache(
    config: Optional[RasterStatsCacheConfig] = None
) -> RasterStatsCache:
    """
    Get the global raster stats cache instance.

    Creates the instance on first call with provided or default config.

    Args:
        config: Optional configuration (only used on first call)

    Returns:
        Global RasterStatsCache instance
    """
    global _global_raster_cache

    if _global_raster_cache is None:
        _global_raster_cache = RasterStatsCache(config)

    return _global_raster_cache


def reset_raster_stats_cache() -> None:
    """Reset the global cache (for testing)."""
    global _global_raster_cache

    if _global_raster_cache:
        _global_raster_cache.clear()

    _global_raster_cache = None

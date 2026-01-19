# -*- coding: utf-8 -*-
"""
WKT Geometry Cache for FilterMate

Provides efficient caching of WKT geometries to avoid repeated parsing
and improve performance for successive filter operations.

Migrated from: before_migration/modules/backends/wkt_cache.py (402 lines)
Target: infrastructure/cache/wkt_cache.py

v4.1.0 - Hexagonal Architecture Migration (January 2026)

Features:
- Thread-safe LRU cache with TTL support
- Automatic expiration and eviction
- Layer-based invalidation
- Statistics tracking for monitoring
"""

import threading
import time
import hashlib
import logging
from typing import Dict, Optional, Tuple, Callable, Set
from dataclasses import dataclass, field
from collections import OrderedDict

from ..constants import (
    WKT_CACHE_MAX_SIZE,
    WKT_CACHE_MAX_LENGTH,
    WKT_CACHE_TTL_SECONDS
)

logger = logging.getLogger('FilterMate.Cache.WKT')


@dataclass
class WKTCacheEntry:
    """Entry for a cached WKT geometry."""
    key: str
    wkt: str
    srid: int
    source_layer_id: str
    creation_time: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 1
    
    @property
    def age_seconds(self) -> float:
        """Age of the entry in seconds."""
        return time.time() - self.creation_time
    
    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return self.age_seconds > WKT_CACHE_TTL_SECONDS
    
    @property
    def wkt_length(self) -> int:
        """Length of the WKT string."""
        return len(self.wkt)
    
    def touch(self):
        """Update last accessed time and increment counter."""
        self.last_accessed = time.time()
        self.access_count += 1


class WKTCache:
    """
    LRU cache for WKT geometries with TTL support.
    
    Features:
    - Thread-safe operations
    - LRU eviction when cache is full
    - TTL-based expiration
    - Size limits to prevent memory issues
    - Statistics tracking
    
    Usage:
        cache = WKTCache.get_instance()
        
        # Get or compute WKT
        wkt = cache.get_or_compute(
            key="layer_xyz_selection",
            compute_func=lambda: compute_wkt_from_layer(layer),
            srid=4326,
            source_layer_id="layer_xyz"
        )
        
        # Manual operations
        cache.put("my_key", "POLYGON(...)", 4326, "layer_id")
        wkt = cache.get("my_key")
        
        # Invalidate when layer changes
        cache.invalidate_for_layer("layer_xyz")
    """
    
    _instance: Optional['WKTCache'] = None
    _lock = threading.Lock()
    
    def __init__(
        self,
        max_size: Optional[int] = None,
        max_wkt_length: Optional[int] = None,
        ttl_seconds: Optional[int] = None
    ):
        """
        Initialize WKT cache.
        
        Args:
            max_size: Maximum number of entries (default: WKT_CACHE_MAX_SIZE)
            max_wkt_length: Maximum WKT length to cache (default: WKT_CACHE_MAX_LENGTH)
            ttl_seconds: Time-to-live in seconds (default: WKT_CACHE_TTL_SECONDS)
        """
        self.max_size = max_size or WKT_CACHE_MAX_SIZE
        self.max_wkt_length = max_wkt_length or WKT_CACHE_MAX_LENGTH
        self.ttl_seconds = ttl_seconds or WKT_CACHE_TTL_SECONDS
        
        self._cache: OrderedDict[str, WKTCacheEntry] = OrderedDict()
        self._layer_keys: Dict[str, Set[str]] = {}  # layer_id -> set of cache keys
        self._cache_lock = threading.RLock()
        
        # Statistics
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0
        self._expirations: int = 0
    
    @classmethod
    def get_instance(cls) -> 'WKTCache':
        """Get singleton instance of WKTCache."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = WKTCache()
                    logger.info("✓ WKTCache initialized")
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (for testing)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.clear()
                cls._instance = None
    
    @staticmethod
    def _compute_key(
        source_layer_id: str,
        feature_ids: Optional[Tuple[int, ...]] = None,
        filter_expression: Optional[str] = None,
        buffer_value: Optional[float] = None
    ) -> str:
        """
        Compute a cache key from parameters.
        
        Args:
            source_layer_id: Source layer ID
            feature_ids: Tuple of feature IDs (for selection-based)
            filter_expression: Filter expression (for expression-based)
            buffer_value: Buffer value
            
        Returns:
            Cache key string
        """
        parts = [source_layer_id]
        
        if feature_ids:
            # Hash feature IDs for consistent key
            ids_str = ",".join(str(fid) for fid in sorted(feature_ids))
            ids_hash = hashlib.md5(ids_str.encode()).hexdigest()[:12]
            parts.append(f"fids:{ids_hash}")
        
        if filter_expression:
            expr_hash = hashlib.md5(filter_expression.encode()).hexdigest()[:12]
            parts.append(f"expr:{expr_hash}")
        
        if buffer_value:
            parts.append(f"buf:{buffer_value}")
        
        return "|".join(parts)
    
    def get(self, key: str) -> Optional[Tuple[str, int]]:
        """
        Get WKT from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Tuple of (wkt, srid) or None if not found/expired
        """
        with self._cache_lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._misses += 1
                return None
            
            if entry.is_expired:
                self._remove(key)
                self._expirations += 1
                self._misses += 1
                logger.debug(f"WKT cache expired: {key}")
                return None
            
            # Move to end (LRU)
            self._cache.move_to_end(key)
            entry.touch()
            self._hits += 1
            
            logger.debug(f"WKT cache hit: {key} (access #{entry.access_count})")
            return (entry.wkt, entry.srid)
    
    def put(
        self,
        key: str,
        wkt: str,
        srid: int,
        source_layer_id: str
    ) -> bool:
        """
        Put WKT into cache.
        
        Args:
            key: Cache key
            wkt: WKT geometry string
            srid: SRID
            source_layer_id: Source layer ID for invalidation
            
        Returns:
            True if cached, False if too large
        """
        # Check WKT length
        if len(wkt) > self.max_wkt_length:
            logger.debug(f"WKT too large to cache: {len(wkt)} > {self.max_wkt_length}")
            return False
        
        with self._cache_lock:
            # Evict if at capacity
            while len(self._cache) >= self.max_size:
                self._evict_oldest()
            
            # Create entry
            entry = WKTCacheEntry(
                key=key,
                wkt=wkt,
                srid=srid,
                source_layer_id=source_layer_id
            )
            
            self._cache[key] = entry
            
            # Track by layer
            if source_layer_id not in self._layer_keys:
                self._layer_keys[source_layer_id] = set()
            self._layer_keys[source_layer_id].add(key)
            
            logger.debug(f"WKT cached: {key} ({len(wkt)} chars, SRID={srid})")
            return True
    
    def get_or_compute(
        self,
        key: str,
        compute_func: Callable[[], Tuple[str, int]],
        source_layer_id: str
    ) -> Tuple[str, int]:
        """
        Get WKT from cache or compute and cache it.
        
        Args:
            key: Cache key
            compute_func: Function that returns (wkt, srid)
            source_layer_id: Source layer ID
            
        Returns:
            Tuple of (wkt, srid)
        """
        # Try cache first
        cached = self.get(key)
        if cached:
            return cached
        
        # Compute
        wkt, srid = compute_func()
        
        # Cache if possible
        self.put(key, wkt, srid, source_layer_id)
        
        return (wkt, srid)
    
    def _remove(self, key: str):
        """Remove entry from cache."""
        entry = self._cache.pop(key, None)
        if entry:
            if entry.source_layer_id in self._layer_keys:
                self._layer_keys[entry.source_layer_id].discard(key)
    
    def _evict_oldest(self):
        """Evict the oldest (least recently used) entry."""
        if self._cache:
            key, entry = self._cache.popitem(last=False)
            
            if entry.source_layer_id in self._layer_keys:
                self._layer_keys[entry.source_layer_id].discard(key)
            
            self._evictions += 1
            logger.debug(f"WKT cache evicted: {key}")
    
    def invalidate(self, key: str) -> bool:
        """
        Invalidate a specific cache entry.
        
        Args:
            key: Cache key to invalidate
            
        Returns:
            True if entry was found and removed
        """
        with self._cache_lock:
            if key in self._cache:
                self._remove(key)
                logger.debug(f"WKT cache invalidated: {key}")
                return True
            return False
    
    def invalidate_for_layer(self, layer_id: str) -> int:
        """
        Invalidate all cache entries for a layer.
        
        Args:
            layer_id: Layer ID to invalidate
            
        Returns:
            Number of entries invalidated
        """
        with self._cache_lock:
            keys = self._layer_keys.get(layer_id, set()).copy()
            
            for key in keys:
                self._remove(key)
            
            if layer_id in self._layer_keys:
                del self._layer_keys[layer_id]
            
            if keys:
                logger.info(f"WKT cache: invalidated {len(keys)} entries for layer {layer_id}")
            
            return len(keys)
    
    def clear(self):
        """Clear all cache entries."""
        with self._cache_lock:
            count = len(self._cache)
            self._cache.clear()
            self._layer_keys.clear()
            logger.info(f"WKT cache cleared ({count} entries)")
    
    def cleanup_expired(self) -> int:
        """
        Remove expired entries.
        
        Returns:
            Number of entries removed
        """
        with self._cache_lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired
            ]
            
            for key in expired_keys:
                self._remove(key)
                self._expirations += 1
            
            if expired_keys:
                logger.debug(f"WKT cache: removed {len(expired_keys)} expired entries")
            
            return len(expired_keys)
    
    @property
    def hit_rate(self) -> float:
        """Cache hit rate (0.0 to 1.0)."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        with self._cache_lock:
            total_wkt_size = sum(len(e.wkt) for e in self._cache.values())
            return {
                'entries': len(self._cache),
                'layers': len(self._layer_keys),
                'total_wkt_size': total_wkt_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': self.hit_rate,
                'evictions': self._evictions,
                'expirations': self._expirations
            }
    
    def __len__(self) -> int:
        """Number of cached entries."""
        return len(self._cache)
    
    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"WKTCache(entries={stats['entries']}, "
            f"hit_rate={stats['hit_rate']:.1%})"
        )


# Convenience function
def get_wkt_cache() -> WKTCache:
    """Get the global WKT cache instance."""
    return WKTCache.get_instance()


# Export symbols
__all__ = [
    'WKTCache',
    'WKTCacheEntry',
    'get_wkt_cache',
]

# -*- coding: utf-8 -*-
"""
LRU Query Result Cache for FilterMate (EPIC-3 Sprint 2).

v4.1.1 - January 2026 - EPIC-3 Sprint 2

PURPOSE:
In-memory LRU cache for query results:
1. Filter expression results caching
2. Unique values caching
3. Feature count caching
4. Configurable size limits and TTL

This module provides the Sprint 2 cache implementation.
"""

import logging
import threading
import sys
from typing import Any, Optional, Dict, List, Set
from collections import OrderedDict as OD
from datetime import datetime
from dataclasses import dataclass

from .interface import (
    CacheInterface,
    CacheKey,
    CacheEntry,
    CacheStats,
    CacheConfig,
    CacheStrategy,
)

logger = logging.getLogger('FilterMate.Cache.LRU')


class LRUQueryCache(CacheInterface):
    """
    LRU cache for query results (EPIC-3 Sprint 2).
    
    Thread-safe in-memory cache with configurable size limits,
    TTL support, and layer-based invalidation.
    
    Features:
    - LRU eviction strategy
    - Per-entry TTL
    - Memory usage tracking
    - Layer-based invalidation
    - Thread-safe operations
    
    Example:
        cache = LRUQueryCache(max_size=500, default_ttl=120)
        
        # Cache unique values
        key = CacheKey.from_unique_values("layer_123", "status")
        cache.set(key, ["Active", "Inactive", "Pending"])
        
        # Get with default factory
        result = cache.get_or_set(
            key,
            factory=lambda: compute_unique_values(),
            ttl=60
        )
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 300,
        max_memory_mb: float = 50.0,
        enable_stats: bool = True,
    ):
        """
        Initialize query cache.
        
        Args:
            max_size: Maximum number of entries
            default_ttl: Default TTL in seconds (0 for no expiration)
            max_memory_mb: Maximum memory usage in MB
            enable_stats: Whether to track statistics
        """
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._max_memory_bytes = int(max_memory_mb * 1024 * 1024)
        self._enable_stats = enable_stats
        
        # LRU storage: OrderedDict maintains insertion order
        self._storage: OD[str, CacheEntry] = OD()
        
        # Index by layer_id for fast invalidation
        self._layer_index: Dict[str, Set[str]] = {}
        
        # Statistics
        self._stats = CacheStats()
        
        # Thread safety
        self._lock = threading.RLock()
    
    def get(self, key: CacheKey) -> Optional[CacheEntry]:
        """
        Retrieve cached value.
        
        Moves entry to end of LRU order on access.
        """
        hash_key = key.hash()
        
        with self._lock:
            entry = self._storage.get(hash_key)
            
            if entry is None:
                if self._enable_stats:
                    self._stats.record_miss()
                return None
            
            # Check expiration
            if entry.is_expired:
                self._remove_entry(hash_key, entry)
                if self._enable_stats:
                    self._stats.record_miss()
                return None
            
            # Move to end (most recently used)
            self._storage.move_to_end(hash_key)
            entry.touch()
            
            if self._enable_stats:
                self._stats.record_hit()
            
            return entry
    
    def set(
        self,
        key: CacheKey,
        value: Any,
        ttl: int = None,
        metadata: Dict[str, Any] = None,
    ) -> bool:
        """
        Store value in cache.
        
        Evicts LRU entries if size limit exceeded.
        """
        hash_key = key.hash()
        ttl = ttl if ttl is not None else self._default_ttl
        
        # Estimate size
        size_bytes = self._estimate_size(value)
        
        with self._lock:
            # Remove existing entry if present
            if hash_key in self._storage:
                self._remove_entry(hash_key, self._storage[hash_key])
            
            # Create entry
            entry = CacheEntry(
                value=value,
                key=key,
                size_bytes=size_bytes,
                metadata=metadata or {},
            )
            
            if ttl > 0:
                entry.set_ttl(ttl)
            
            # Evict if necessary
            self._evict_if_needed(size_bytes)
            
            # Store entry
            self._storage[hash_key] = entry
            
            # Update layer index
            if key.layer_id:
                if key.layer_id not in self._layer_index:
                    self._layer_index[key.layer_id] = set()
                self._layer_index[key.layer_id].add(hash_key)
            
            if self._enable_stats:
                self._stats.record_insertion(size_bytes)
            
            return True
    
    def delete(self, key: CacheKey) -> bool:
        """Delete cached value."""
        hash_key = key.hash()
        
        with self._lock:
            entry = self._storage.get(hash_key)
            if entry is None:
                return False
            
            self._remove_entry(hash_key, entry)
            return True
    
    def clear(self) -> int:
        """Clear all cached values."""
        with self._lock:
            count = len(self._storage)
            self._storage.clear()
            self._layer_index.clear()
            self._stats = CacheStats()
            return count
    
    def exists(self, key: CacheKey) -> bool:
        """Check if key exists in cache."""
        hash_key = key.hash()
        
        with self._lock:
            entry = self._storage.get(hash_key)
            if entry is None:
                return False
            if entry.is_expired:
                self._remove_entry(hash_key, entry)
                return False
            return True
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats
    
    def invalidate_by_layer(self, layer_id: str) -> int:
        """
        Invalidate all cache entries for a layer.
        
        Uses layer index for O(1) lookup of affected keys.
        """
        with self._lock:
            keys_to_remove = self._layer_index.get(layer_id, set()).copy()
            
            for hash_key in keys_to_remove:
                entry = self._storage.get(hash_key)
                if entry:
                    self._remove_entry(hash_key, entry)
            
            if layer_id in self._layer_index:
                del self._layer_index[layer_id]
            
            logger.debug(f"Invalidated {len(keys_to_remove)} entries for layer {layer_id}")
            return len(keys_to_remove)
    
    def invalidate_by_namespace(self, namespace: str) -> int:
        """Invalidate all entries in a namespace."""
        with self._lock:
            keys_to_remove = []
            
            for hash_key, entry in self._storage.items():
                if entry.key.namespace == namespace:
                    keys_to_remove.append((hash_key, entry))
            
            for hash_key, entry in keys_to_remove:
                self._remove_entry(hash_key, entry)
            
            return len(keys_to_remove)
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries."""
        with self._lock:
            keys_to_remove = []
            
            for hash_key, entry in self._storage.items():
                if entry.is_expired:
                    keys_to_remove.append((hash_key, entry))
            
            for hash_key, entry in keys_to_remove:
                self._remove_entry(hash_key, entry)
            
            return len(keys_to_remove)
    
    def get_keys(self, namespace: str = None) -> List[CacheKey]:
        """
        Get all cache keys.
        
        Args:
            namespace: Optional namespace filter
        """
        with self._lock:
            keys = []
            for entry in self._storage.values():
                if namespace is None or entry.key.namespace == namespace:
                    keys.append(entry.key)
            return keys
    
    def _remove_entry(self, hash_key: str, entry: CacheEntry) -> None:
        """Remove entry from storage and indices."""
        if hash_key in self._storage:
            del self._storage[hash_key]
            
            # Update layer index
            if entry.key.layer_id and entry.key.layer_id in self._layer_index:
                self._layer_index[entry.key.layer_id].discard(hash_key)
            
            if self._enable_stats:
                self._stats.record_removal(entry.size_bytes)
    
    def _evict_if_needed(self, new_size: int) -> int:
        """
        Evict entries if size limits exceeded.
        
        Returns:
            Number of entries evicted
        """
        evicted = 0
        
        # Evict if count limit exceeded
        while len(self._storage) >= self._max_size:
            # Remove least recently used (first item)
            hash_key, entry = self._storage.popitem(last=False)
            
            if entry.key.layer_id and entry.key.layer_id in self._layer_index:
                self._layer_index[entry.key.layer_id].discard(hash_key)
            
            if self._enable_stats:
                self._stats.record_eviction()
                self._stats.record_removal(entry.size_bytes)
            
            evicted += 1
        
        # Evict if memory limit exceeded
        while self._stats.total_size_bytes + new_size > self._max_memory_bytes:
            if not self._storage:
                break
            
            hash_key, entry = self._storage.popitem(last=False)
            
            if entry.key.layer_id and entry.key.layer_id in self._layer_index:
                self._layer_index[entry.key.layer_id].discard(hash_key)
            
            if self._enable_stats:
                self._stats.record_eviction()
                self._stats.record_removal(entry.size_bytes)
            
            evicted += 1
        
        return evicted
    
    def _estimate_size(self, value: Any) -> int:
        """Estimate memory size of value."""
        try:
            return sys.getsizeof(value)
        except TypeError:
            # Fallback for complex objects
            return 1024  # Assume 1KB


@dataclass
class FilterCacheConfig:
    """Configuration for filter result caching."""
    enabled: bool = True
    max_entries: int = 500
    ttl_seconds: int = 300
    max_memory_mb: float = 25.0
    cache_feature_ids: bool = True
    cache_counts: bool = True
    cache_unique_values: bool = True


class FilterResultCache:
    """
    Specialized cache for filter results.
    
    Provides type-safe caching for:
    - Feature IDs from filter expressions
    - Feature counts
    - Unique values
    
    Example:
        cache = FilterResultCache()
        
        # Cache feature IDs
        cache.cache_feature_ids("layer_123", "status = 1", [1, 2, 3, 4])
        
        # Get cached IDs
        ids = cache.get_feature_ids("layer_123", "status = 1")
    """
    
    def __init__(self, config: FilterCacheConfig = None):
        """
        Initialize filter result cache.
        
        Args:
            config: Cache configuration
        """
        self.config = config or FilterCacheConfig()
        self._cache = LRUQueryCache(
            max_size=self.config.max_entries,
            default_ttl=self.config.ttl_seconds,
            max_memory_mb=self.config.max_memory_mb,
        )
    
    def cache_feature_ids(
        self,
        layer_id: str,
        expression: str,
        feature_ids: List[int],
        ttl: int = None,
    ) -> bool:
        """
        Cache feature IDs for a filter expression.
        
        Args:
            layer_id: Layer identifier
            expression: Filter expression
            feature_ids: List of matching feature IDs
            ttl: Optional TTL override
        """
        if not self.config.enabled or not self.config.cache_feature_ids:
            return False
        
        key = CacheKey.from_filter(layer_id, expression)
        return self._cache.set(key, feature_ids, ttl)
    
    def get_feature_ids(
        self,
        layer_id: str,
        expression: str,
    ) -> Optional[List[int]]:
        """
        Get cached feature IDs.
        
        Args:
            layer_id: Layer identifier
            expression: Filter expression
            
        Returns:
            List of feature IDs or None if not cached
        """
        if not self.config.enabled or not self.config.cache_feature_ids:
            return None
        
        key = CacheKey.from_filter(layer_id, expression)
        entry = self._cache.get(key)
        return entry.value if entry else None
    
    def cache_count(
        self,
        layer_id: str,
        expression: str,
        count: int,
        ttl: int = None,
    ) -> bool:
        """Cache feature count for expression."""
        if not self.config.enabled or not self.config.cache_counts:
            return False
        
        key = CacheKey(
            namespace="count",
            layer_id=layer_id,
            expression=expression,
        )
        return self._cache.set(key, count, ttl)
    
    def get_count(
        self,
        layer_id: str,
        expression: str,
    ) -> Optional[int]:
        """Get cached feature count."""
        if not self.config.enabled or not self.config.cache_counts:
            return None
        
        key = CacheKey(
            namespace="count",
            layer_id=layer_id,
            expression=expression,
        )
        entry = self._cache.get(key)
        return entry.value if entry else None
    
    def cache_unique_values(
        self,
        layer_id: str,
        field_name: str,
        values: List[Any],
        filter_expr: str = "",
        ttl: int = None,
    ) -> bool:
        """Cache unique values for a field."""
        if not self.config.enabled or not self.config.cache_unique_values:
            return False
        
        key = CacheKey.from_unique_values(layer_id, field_name, filter_expr)
        return self._cache.set(key, values, ttl)
    
    def get_unique_values(
        self,
        layer_id: str,
        field_name: str,
        filter_expr: str = "",
    ) -> Optional[List[Any]]:
        """Get cached unique values."""
        if not self.config.enabled or not self.config.cache_unique_values:
            return None
        
        key = CacheKey.from_unique_values(layer_id, field_name, filter_expr)
        entry = self._cache.get(key)
        return entry.value if entry else None
    
    def invalidate_layer(self, layer_id: str) -> int:
        """Invalidate all cached data for a layer."""
        return self._cache.invalidate_by_layer(layer_id)
    
    def clear(self) -> int:
        """Clear all cached data."""
        return self._cache.clear()
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._cache.get_stats()

"""
ExploringFeaturesCache - Cache for exploring features in FilterMate.

Provides caching for feature exploration to improve performance when
switching between layers and groupbox types.
"""

import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class ExploringCacheEntry:
    """Cache entry for exploring features."""
    features: List[Any]
    expression: Optional[str]
    timestamp: float = field(default_factory=time.time)
    hits: int = 0


class ExploringFeaturesCache:
    """
    LRU cache for exploring features with TTL support.
    
    Caches feature lists by layer_id and groupbox_type to avoid
    repeated database queries when exploring layers.
    
    Args:
        max_layers: Maximum number of layers to cache
        max_age_seconds: Time-to-live for cache entries in seconds
    """
    
    def __init__(self, max_layers: int = 50, max_age_seconds: float = 300.0):
        self._max_layers = max_layers
        self._max_age_seconds = max_age_seconds
        self._cache: Dict[str, Dict[str, ExploringCacheEntry]] = {}
        self._access_order: List[str] = []  # LRU tracking by layer_id
        self._stats = {
            'hits': 0,
            'misses': 0,
            'invalidations': 0,
            'expirations': 0
        }
    
    def _make_key(self, layer_id: str, groupbox_type: str) -> Tuple[str, str]:
        """Create cache key from layer_id and groupbox_type."""
        return (layer_id, groupbox_type)
    
    def _is_expired(self, entry: ExploringCacheEntry) -> bool:
        """Check if cache entry has expired."""
        return (time.time() - entry.timestamp) > self._max_age_seconds
    
    def _update_access_order(self, layer_id: str) -> None:
        """Update LRU access order for layer."""
        if layer_id in self._access_order:
            self._access_order.remove(layer_id)
        self._access_order.append(layer_id)
    
    def _evict_if_needed(self) -> None:
        """Evict oldest layers if cache is full."""
        while len(self._cache) > self._max_layers and self._access_order:
            oldest_layer = self._access_order.pop(0)
            if oldest_layer in self._cache:
                del self._cache[oldest_layer]
    
    def get(self, layer_id: str, groupbox_type: str) -> Optional[List[Any]]:
        """
        Get cached features for layer and groupbox type.
        
        Args:
            layer_id: Layer ID
            groupbox_type: Type of groupbox (e.g., 'custom_selection')
            
        Returns:
            Cached features list or None if not cached/expired
        """
        if layer_id not in self._cache:
            self._stats['misses'] += 1
            return None
        
        layer_cache = self._cache[layer_id]
        if groupbox_type not in layer_cache:
            self._stats['misses'] += 1
            return None
        
        entry = layer_cache[groupbox_type]
        
        # Check expiration
        if self._is_expired(entry):
            del layer_cache[groupbox_type]
            if not layer_cache:
                del self._cache[layer_id]
                if layer_id in self._access_order:
                    self._access_order.remove(layer_id)
            self._stats['expirations'] += 1
            self._stats['misses'] += 1
            return None
        
        # Cache hit
        entry.hits += 1
        self._stats['hits'] += 1
        self._update_access_order(layer_id)
        return entry.features
    
    def put(
        self,
        layer_id: str,
        groupbox_type: str,
        features: List[Any],
        expression: Optional[str] = None
    ) -> None:
        """
        Store features in cache.
        
        Args:
            layer_id: Layer ID
            groupbox_type: Type of groupbox
            features: List of features to cache
            expression: Optional filter expression used
        """
        self._evict_if_needed()
        
        if layer_id not in self._cache:
            self._cache[layer_id] = {}
        
        self._cache[layer_id][groupbox_type] = ExploringCacheEntry(
            features=features,
            expression=expression
        )
        self._update_access_order(layer_id)
    
    def invalidate(self, layer_id: str, groupbox_type: Optional[str] = None) -> None:
        """
        Invalidate cache entries.
        
        Args:
            layer_id: Layer ID to invalidate
            groupbox_type: Optional specific groupbox type, or all if None
        """
        if layer_id not in self._cache:
            return
        
        if groupbox_type is None:
            # Invalidate all entries for layer
            del self._cache[layer_id]
            if layer_id in self._access_order:
                self._access_order.remove(layer_id)
        else:
            # Invalidate specific groupbox type
            if groupbox_type in self._cache[layer_id]:
                del self._cache[layer_id][groupbox_type]
                if not self._cache[layer_id]:
                    del self._cache[layer_id]
                    if layer_id in self._access_order:
                        self._access_order.remove(layer_id)
        
        self._stats['invalidations'] += 1
    
    def invalidate_all(self) -> None:
        """Clear all cache entries."""
        count = len(self._cache)
        self._cache.clear()
        self._access_order.clear()
        self._stats['invalidations'] += count
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_entries = sum(len(v) for v in self._cache.values())
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = (self._stats['hits'] / total_requests * 100) if total_requests > 0 else 0.0
        
        return {
            'layers_cached': len(self._cache),
            'total_entries': total_entries,
            'max_layers': self._max_layers,
            'max_age_seconds': self._max_age_seconds,
            'hits': self._stats['hits'],
            'misses': self._stats['misses'],
            'hit_rate': round(hit_rate, 1),
            'invalidations': self._stats['invalidations'],
            'expirations': self._stats['expirations']
        }
    
    def __len__(self) -> int:
        """Return total number of cached entries."""
        return sum(len(v) for v in self._cache.values())
    
    def __repr__(self) -> str:
        stats = self.get_stats()
        return f"ExploringFeaturesCache(entries={stats['total_entries']}, hit_rate={stats['hit_rate']}%)"

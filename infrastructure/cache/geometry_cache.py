# -*- coding: utf-8 -*-
"""
Source Geometry Cache for FilterMate

Cache for pre-calculated source geometries during spatial filtering operations.

This cache avoids recalculating source geometries when filtering multiple layers
with the same source selection, providing significant performance improvements.

Performance: 5× speedup when filtering 5+ layers with the same source.

Example:
    User selects 2000 features and filters 5 layers:
    - Without cache: 5 × 2s calculation = 10s wasted
    - With cache: 1 × 2s + 4 × 0.01s = 2.04s total

Usage:
    from ...infrastructure.cache import SourceGeometryCache
    cache = SourceGeometryCache()

    # Try to get from cache
    cached = cache.get(features, buffer_value, target_crs, layer_id, subset_string)
    if cached:
        geometry_data = cached
    else:
        geometry_data = calculate_geometry(...)
        cache.put(features, buffer_value, target_crs, geometry_data, layer_id, subset_string)

Migrated from modules/tasks/geometry_cache.py (EPIC-1 v3.0).
"""

from ..logging import get_logger

logger = get_logger(__name__)


class SourceGeometryCache:
    """
    Cache for pre-calculated source geometries.

    Avoids recalculating source geometries when filtering multiple layers
    with the same source selection.

    Performance: 5× gain when filtering 5+ layers with same source.

    Example:
        User selects 2000 features and filters 5 layers:
        - Without cache: 5 × 2s calculation = 10s wasted
        - With cache: 1 × 2s + 4 × 0.01s = 2.04s total

    Attributes:
        _cache: Dictionary mapping cache keys to geometry data
        _max_cache_size: Maximum number of cached entries (default: 10)
        _access_order: FIFO list for cache eviction
    """

    def __init__(self, max_size: int = 10):
        """
        Initialize source geometry cache.

        Args:
            max_size: Maximum number of cached entries (default: 10)
        """
        self._cache = {}
        self._max_cache_size = max_size
        self._access_order = []  # FIFO: First In, First Out
        logger.info(f"✓ SourceGeometryCache initialized (max size: {max_size})")

    def get_cache_key(self, features, buffer_value, target_crs_authid, layer_id=None, subset_string=None):
        """
        Generate unique cache key for a geometry.

        Args:
            features: List of features or IDs
            buffer_value: Buffer distance (or None)
            target_crs_authid: Target CRS authid (e.g., 'EPSG:3857')
            layer_id: Source layer ID (optional, avoids collisions)
            subset_string: Active subset string on layer (optional, invalidates cache on filter change)

        Returns:
            tuple: Unique cache key
        """
        # Convert features to sorted tuple of IDs (order-independent)
        if isinstance(features, (list, tuple)) and features:
            if hasattr(features[0], 'id'):
                feature_ids = tuple(sorted([f.id() for f in features]))
            else:
                feature_ids = tuple(sorted(features))
        else:
            feature_ids = ()

        # Include layer_id and subset_string in key to avoid collisions
        # subset_string is critical: if filter changes, geometry must be recalculated
        return (feature_ids, buffer_value, target_crs_authid, layer_id, subset_string)

    def get(self, features, buffer_value, target_crs_authid, layer_id=None, subset_string=None):
        """
        Retrieve geometry from cache if it exists.

        Args:
            features: List of features or IDs
            buffer_value: Buffer distance
            target_crs_authid: Target CRS authid
            layer_id: Source layer ID (optional)
            subset_string: Active subset string (optional)

        Returns:
            dict or None: Cached geometry data (wkt, bbox, etc.) or None if not found
        """
        key = self.get_cache_key(features, buffer_value, target_crs_authid, layer_id, subset_string)

        if key in self._cache:
            # Update access order (move to end)
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

            logger.info("✓ Cache HIT: Geometry retrieved from cache")
            return self._cache[key]

        logger.debug("Cache MISS: Geometry not in cache")
        return None

    def put(self, features, buffer_value, target_crs_authid, geometry_data, layer_id=None, subset_string=None):
        """
        Store geometry in cache.

        Args:
            features: List of features or IDs
            buffer_value: Buffer distance
            target_crs_authid: Target CRS authid
            geometry_data: Data to cache (dict with wkt, bbox, etc.)
            layer_id: Source layer ID (optional)
            subset_string: Active subset string (optional)
        """
        key = self.get_cache_key(features, buffer_value, target_crs_authid, layer_id, subset_string)

        # Check cache limit
        if len(self._cache) >= self._max_cache_size:
            # Remove oldest entry (FIFO)
            if self._access_order:
                oldest_key = self._access_order.pop(0)
                if oldest_key in self._cache:
                    del self._cache[oldest_key]
                    logger.debug(f"Cache full: Removed oldest entry (size: {self._max_cache_size})")

        # Store in cache
        self._cache[key] = geometry_data
        self._access_order.append(key)

        logger.info(f"✓ Cached geometry (cache size: {len(self._cache)}/{self._max_cache_size})")

    def clear(self):
        """Clear the cache."""
        count = len(self._cache)
        self._cache.clear()
        self._access_order.clear()
        logger.info(f"Cache cleared ({count} entries removed)")

    def invalidate_layer(self, layer_id):
        """
        Invalidate all cached geometries for a specific layer.

        Call this when a layer is modified or its filter changes.

        Args:
            layer_id: Layer ID to invalidate

        Returns:
            int: Number of entries removed
        """
        keys_to_remove = [k for k in self._cache if k[3] == layer_id]
        for key in keys_to_remove:
            del self._cache[key]
            if key in self._access_order:
                self._access_order.remove(key)

        if keys_to_remove:
            logger.debug(f"Cache invalidated {len(keys_to_remove)} entries for layer {layer_id}")

        return len(keys_to_remove)

    def get_stats(self):
        """
        Get cache statistics.

        Returns:
            dict: Statistics including size, max_size
        """
        return {
            'size': len(self._cache),
            'max_size': self._max_cache_size,
            'access_order_length': len(self._access_order)
        }

    def __len__(self):
        """Return current cache size."""
        return len(self._cache)

    def __contains__(self, key):
        """Check if key is in cache."""
        return key in self._cache

"""
Geometry Cache Wrapper

Task-level wrapper for geometry caching operations.
Extracted from FilterEngineTask as part of Phase E13 refactoring (January 2026).

Provides simplified interface to infrastructure.cache.SourceGeometryCache
with task-specific conveniences.

Location: core/tasks/cache/geometry_cache.py
"""

import logging
from typing import Optional, List, Any

# HEXAGONAL MIGRATION v4.1: Removed unused QgsGeometry import
# Use adapters from core.ports.qgis_port when needed

# Import infrastructure cache
from ....infrastructure.cache import SourceGeometryCache
from ....infrastructure.cache.cache_manager import (
    CacheManager,
    CacheConfig,
    CachePolicy
)

logger = logging.getLogger('FilterMate.Tasks.GeometryCache')


class GeometryCache:
    """
    Task-level wrapper for geometry caching.

    Provides simplified interface for caching prepared geometries during
    filtering operations. Delegates to infrastructure.cache.SourceGeometryCache.

    Responsibilities:
    - Cache prepared geometries with context
    - Invalidation on layer changes
    - Memory management (FIFO eviction)
    - Statistics tracking

    Extracted from FilterEngineTask (lines 257-267, 296) in Phase E13.

    Example:
        cache = GeometryCache(max_size=100)

        # Try to get from cache
        cached = cache.get(layer_id="layer_123", feature_ids=[1, 2, 3])
        if cached:
            geometry = cached
        else:
            geometry = compute_geometry(...)
            cache.put(layer_id="layer_123", geometry=geometry, feature_ids=[1, 2, 3])

        # Invalidate when layer changes
        cache.invalidate_layer("layer_123")
    """

    def __init__(self, max_size: int = 100):
        """
        Initialize geometry cache.

        Args:
            max_size: Maximum number of cached geometries (default: 100)
        """
        self._underlying_cache = SourceGeometryCache(max_size=max_size)
        self._max_size = max_size

        # Register in global CacheManager (only if not already registered)
        cache_manager = CacheManager.get_instance()
        if cache_manager.get_cache("geometry_task") is None:
            cache_config = CacheConfig(
                policy=CachePolicy.FIFO,  # FIFO policy for geometries
                max_size=max_size,
                ttl_seconds=None  # No TTL for geometries
            )
            cache_manager.register_cache("geometry_task", cache_config)
            logger.debug(
                f"GeometryCache initialized (max_size={max_size}) "
                "and registered in CacheManager"
            )
        else:
            logger.debug(
                f"GeometryCache initialized (max_size={max_size}), "
                "using existing CacheManager registration"
            )

    def get(
        self,
        layer_id: str,
        feature_ids: Optional[List[int]] = None,
        buffer_value: Optional[float] = None,
        target_crs_authid: Optional[str] = None,
        subset_string: Optional[str] = None
    ) -> Optional[Any]:
        """
        Get cached geometry for layer and context.

        Args:
            layer_id: Layer ID
            feature_ids: Optional list of feature IDs
            buffer_value: Optional buffer distance
            target_crs_authid: Optional target CRS
            subset_string: Optional active subset string

        Returns:
            Cached geometry data or None if not found
        """
        # Convert feature_ids to mock features for SourceGeometryCache compatibility
        # SourceGeometryCache.get() expects features, but we can pass IDs as key
        features = feature_ids if feature_ids else []
        buffer = buffer_value if buffer_value is not None else 0.0
        crs = target_crs_authid or "EPSG:4326"

        cached_data = self._underlying_cache.get(
            features=features,
            buffer_value=buffer,
            target_crs_authid=crs,
            layer_id=layer_id,
            subset_string=subset_string
        )

        if cached_data:
            logger.debug(f"Cache HIT for layer {layer_id}")
        else:
            logger.debug(f"Cache MISS for layer {layer_id}")

        return cached_data

    def put(
        self,
        layer_id: str,
        geometry: Any,
        feature_ids: Optional[List[int]] = None,
        buffer_value: Optional[float] = None,
        target_crs_authid: Optional[str] = None,
        subset_string: Optional[str] = None
    ):
        """
        Store geometry in cache with context.

        Args:
            layer_id: Layer ID
            geometry: Geometry data to cache
            feature_ids: Optional list of feature IDs
            buffer_value: Optional buffer distance
            target_crs_authid: Optional target CRS
            subset_string: Optional active subset string
        """
        features = feature_ids if feature_ids else []
        buffer = buffer_value if buffer_value is not None else 0.0
        crs = target_crs_authid or "EPSG:4326"

        self._underlying_cache.put(
            features=features,
            buffer_value=buffer,
            target_crs_authid=crs,
            geometry_data=geometry,
            layer_id=layer_id,
            subset_string=subset_string
        )

        logger.debug(f"Cached geometry for layer {layer_id}")

    def invalidate_layer(self, layer_id: str) -> int:
        """
        Invalidate all cached geometries for a specific layer.

        Call this when a layer is modified or its filter changes.

        Args:
            layer_id: Layer ID to invalidate

        Returns:
            Number of entries removed
        """
        count = self._underlying_cache.invalidate_layer(layer_id)

        if count > 0:
            logger.info(f"Invalidated {count} cache entries for layer {layer_id}")

        return count

    def clear(self):
        """Clear entire cache."""
        self._underlying_cache.clear()
        logger.info("Cache cleared")

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dict with statistics (size, max_size, etc.)
        """
        return self._underlying_cache.get_stats()

    def __len__(self) -> int:
        """Return current cache size."""
        return len(self._underlying_cache)

    @classmethod
    def get_shared_instance(cls) -> 'GeometryCache':
        """
        Get shared geometry cache instance (singleton pattern).

        Replaces FilterEngineTask.get_geometry_cache() class method.

        Returns:
            Shared GeometryCache instance
        """
        if not hasattr(cls, '_shared_instance'):
            cls._shared_instance = cls(max_size=100)
            logger.debug("Created shared GeometryCache instance")

        return cls._shared_instance

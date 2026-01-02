# -*- coding: utf-8 -*-
"""
Backend Factory for FilterMate

Factory pattern implementation for selecting the appropriate backend
based on layer provider type.

Includes optimization for small PostgreSQL datasets: when a PostgreSQL layer
has fewer features than SMALL_DATASET_THRESHOLD, use OGR memory backend
to avoid network overhead and achieve faster filtering.

v2.4.0 Improvements:
- Cache invalidation for modified layers
- Cache age tracking with TTL
- Improved memory management
"""

import time
from typing import Dict, Optional, Tuple
from qgis.core import QgsVectorLayer, QgsFeature, QgsFields, QgsWkbTypes, QgsMemoryProviderUtils
from .base_backend import GeometricFilterBackend
from .postgresql_backend import PostgreSQLGeometricFilter, POSTGRESQL_AVAILABLE, PSYCOPG2_AVAILABLE
from .spatialite_backend import SpatialiteGeometricFilter
from .ogr_backend import OGRGeometricFilter
from .memory_backend import MemoryGeometricFilter
from ..logging_config import get_tasks_logger
from ..constants import (
    PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR, PROVIDER_MEMORY,
    SMALL_DATASET_THRESHOLD, DEFAULT_SMALL_DATASET_OPTIMIZATION,
    FACTORY_CACHE_MAX_AGE
)

logger = get_tasks_logger()


def get_small_dataset_config() -> Tuple[bool, int]:
    """
    Get small dataset optimization configuration from ENV_VARS.
    
    Returns:
        Tuple of (enabled: bool, threshold: int)
    """
    try:
        from ...config.config import ENV_VARS
        
        config_data = ENV_VARS.get('CONFIG_DATA', {})
        config = config_data.get('APP', {}).get('OPTIONS', {}).get('SMALL_DATASET_OPTIMIZATION', {})
        
        # Handle nested config objects with 'value' key (v2.0 config format)
        enabled_config = config.get('enabled', DEFAULT_SMALL_DATASET_OPTIMIZATION)
        threshold_config = config.get('threshold', SMALL_DATASET_THRESHOLD)
        
        # Extract 'value' if it's a dict, otherwise use directly
        if isinstance(enabled_config, dict):
            enabled = enabled_config.get('value', DEFAULT_SMALL_DATASET_OPTIMIZATION)
        else:
            enabled = enabled_config
            
        if isinstance(threshold_config, dict):
            threshold = threshold_config.get('value', SMALL_DATASET_THRESHOLD)
        else:
            threshold = threshold_config
        
        return (bool(enabled), int(threshold))
    except Exception:
        # Fallback to defaults
        return (DEFAULT_SMALL_DATASET_OPTIMIZATION, SMALL_DATASET_THRESHOLD)


def should_use_memory_optimization(layer: QgsVectorLayer, layer_provider_type: str) -> bool:
    """
    Determine if a PostgreSQL layer should use OGR memory optimization.
    
    For small PostgreSQL datasets, loading data into a memory layer and using
    OGR backend is faster than making network requests to PostgreSQL server.
    
    Args:
        layer: QgsVectorLayer to check
        layer_provider_type: Provider type string
        
    Returns:
        True if memory optimization should be used
    """
    # Only applies to PostgreSQL layers
    if layer_provider_type != PROVIDER_POSTGRES:
        return False
    
    # Check if optimization is enabled
    enabled, threshold = get_small_dataset_config()
    if not enabled:
        return False
    
    # Check feature count
    try:
        feature_count = layer.featureCount()
        if feature_count < 0:
            # Unknown feature count, don't optimize
            return False
        
        if feature_count <= threshold:
            logger.debug(
                f"Layer {layer.name()} has {feature_count} features "
                f"(≤ {threshold}), eligible for memory optimization"
            )
            return True
        else:
            logger.debug(
                f"Layer {layer.name()} has {feature_count} features "
                f"(> {threshold}), using PostgreSQL backend"
            )
            return False
            
    except Exception as e:
        logger.warning(f"Could not determine feature count for {layer.name()}: {e}")
        return False


def load_postgresql_to_memory(layer: QgsVectorLayer) -> Optional[QgsVectorLayer]:
    """
    Load a PostgreSQL layer into a memory layer for faster local processing.
    
    This function copies all features from a PostgreSQL layer into a QGIS
    memory layer, which is much faster for filtering operations on small
    datasets because it avoids network overhead.
    
    Args:
        layer: PostgreSQL QgsVectorLayer to load
        
    Returns:
        QgsVectorLayer: Memory layer with all features, or None if failed
    """
    try:
        # Get layer properties
        geom_type = layer.wkbType()
        crs = layer.crs()
        fields = layer.fields()
        layer_name = f"{layer.name()}_memory"
        
        # Create memory layer with same structure
        geom_type_str = QgsWkbTypes.displayString(geom_type)
        memory_layer = QgsMemoryProviderUtils.createMemoryLayer(
            layer_name,
            fields,
            geom_type,
            crs
        )
        
        if not memory_layer or not memory_layer.isValid():
            logger.error(f"Failed to create memory layer for {layer.name()}")
            return None
        
        # Copy all features
        memory_dp = memory_layer.dataProvider()
        features = []
        
        for feature in layer.getFeatures():
            new_feature = QgsFeature(fields)
            new_feature.setGeometry(feature.geometry())
            new_feature.setAttributes(feature.attributes())
            features.append(new_feature)
        
        # Add features to memory layer
        success, _ = memory_dp.addFeatures(features)
        if not success:
            logger.error(f"Failed to add features to memory layer for {layer.name()}")
            return None
        
        memory_layer.updateExtents()
        
        logger.info(
            f"✓ Loaded {len(features)} features from PostgreSQL layer "
            f"'{layer.name()}' into memory layer for optimized filtering"
        )
        
        return memory_layer
        
    except Exception as e:
        logger.error(f"Error loading PostgreSQL layer to memory: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return None


class BackendFactory:
    """
    Factory for creating appropriate backend instances.
    
    The factory selects the best backend based on:
    1. Layer provider type (postgres, spatialite, ogr)
    2. Availability of required libraries (psycopg2 for PostgreSQL)
    3. Dataset size (small PostgreSQL datasets use OGR memory for speed)
    4. Fallback to OGR for unknown providers
    
    Small Dataset Optimization:
        For PostgreSQL layers with ≤ SMALL_DATASET_THRESHOLD features,
        the factory returns OGR backend with a pre-loaded memory layer.
        This avoids network overhead and is typically 2-10× faster for
        small datasets.
    
    v2.4.0 Cache Improvements:
        - Cache entries now track creation time and feature count
        - Automatic invalidation for stale entries (> FACTORY_CACHE_MAX_AGE)
        - Invalidation when layer feature count changes
    """
    
    # Cache for memory layers (layer_id -> (memory_layer, creation_time, feature_count))
    _memory_layer_cache: Dict[str, Tuple[QgsVectorLayer, float, int]] = {}
    
    @classmethod
    def clear_memory_cache(cls):
        """Clear the memory layer cache."""
        cls._memory_layer_cache.clear()
        logger.debug("Memory layer cache cleared")
    
    @classmethod
    def invalidate_layer_cache(cls, layer_id: str) -> bool:
        """
        Invalidate cache for a specific layer.
        
        Args:
            layer_id: ID of the layer to invalidate
            
        Returns:
            True if entry was found and removed
        """
        if layer_id in cls._memory_layer_cache:
            del cls._memory_layer_cache[layer_id]
            logger.debug(f"Cache invalidated for layer {layer_id}")
            return True
        return False
    
    @classmethod
    def _is_cache_valid(cls, layer: QgsVectorLayer) -> bool:
        """
        Check if cached memory layer is still valid.
        
        Validates:
        - Cache entry exists
        - Memory layer is valid
        - Cache age is within TTL
        - Feature count hasn't changed
        
        Args:
            layer: Source layer to check
            
        Returns:
            True if cache is valid
        """
        layer_id = layer.id()
        
        if layer_id not in cls._memory_layer_cache:
            return False
        
        cached_layer, creation_time, cached_count = cls._memory_layer_cache[layer_id]
        
        # Check if memory layer is still valid
        if not cached_layer or not cached_layer.isValid():
            logger.debug(f"Cache invalid: memory layer not valid for {layer.name()}")
            del cls._memory_layer_cache[layer_id]
            return False
        
        # Check cache age
        age = time.time() - creation_time
        if age > FACTORY_CACHE_MAX_AGE:
            logger.debug(f"Cache expired: {age:.0f}s > {FACTORY_CACHE_MAX_AGE}s for {layer.name()}")
            del cls._memory_layer_cache[layer_id]
            return False
        
        # Check if feature count changed (layer was modified)
        current_count = layer.featureCount()
        if current_count != cached_count:
            logger.debug(
                f"Cache invalid: feature count changed {cached_count} → {current_count} "
                f"for {layer.name()}"
            )
            del cls._memory_layer_cache[layer_id]
            return False
        
        return True
    
    @classmethod
    def get_memory_layer(cls, layer: QgsVectorLayer) -> Optional[QgsVectorLayer]:
        """
        Get or create a memory layer for the given layer.
        
        Args:
            layer: Source layer
            
        Returns:
            Cached or newly created memory layer
        """
        layer_id = layer.id()
        
        # Check cache with validation
        if cls._is_cache_valid(layer):
            cached_layer, _, _ = cls._memory_layer_cache[layer_id]
            logger.debug(f"Using cached memory layer for {layer.name()}")
            return cached_layer
        
        # Create new memory layer
        memory_layer = load_postgresql_to_memory(layer)
        if memory_layer:
            # Store with creation time and feature count for validation
            cls._memory_layer_cache[layer_id] = (
                memory_layer,
                time.time(),
                layer.featureCount()
            )
        
        return memory_layer
    
    @staticmethod
    def get_backend(
        layer_provider_type: str,
        layer: QgsVectorLayer,
        task_params: Dict,
        return_memory_info: bool = False
    ) -> GeometricFilterBackend:
        """
        Get the appropriate backend for the given layer.
        
        For small PostgreSQL datasets, this method returns an OGR backend
        that will use a memory layer copy for faster spatial calculations,
        but the final filter will be applied to the original PostgreSQL layer.
        
        Args:
            layer_provider_type: Provider type string ('postgresql', 'spatialite', 'ogr')
            layer: QgsVectorLayer instance
            task_params: Task parameters dictionary
            return_memory_info: If True, return tuple (backend, memory_layer, use_optimization)
        
        Returns:
            GeometricFilterBackend instance (or tuple if return_memory_info=True)
        """
        # v2.4.13: Enhanced logging at INFO level for backend selection debugging
        logger.info(f"🔧 BackendFactory.get_backend() called for '{layer.name()}'")
        logger.info(f"   → layer_provider_type (requested): '{layer_provider_type}'")
        logger.info(f"   → layer.providerType() (QGIS native): '{layer.providerType()}'")
        
        memory_layer = None
        use_optimization = False
        
        # PRIORITY 1: Check if backend is forced by user
        forced_backends = task_params.get('forced_backends', {})
        forced_backend = forced_backends.get(layer.id()) if forced_backends else None
        
        if forced_backend:
            logger.info(f"🔒 Using forced backend '{forced_backend.upper()}' for layer '{layer.name()}'")
            
            # Create the forced backend - RESPECT USER CHOICE strictly
            if forced_backend == 'postgresql':
                if not PSYCOPG2_AVAILABLE:
                    logger.info(
                        f"ℹ️ PostgreSQL backend forced for '{layer.name()}' - psycopg2 not available. "
                        f"Using QGIS native API (setSubsetString). MVs disabled."
                    )
                backend = PostgreSQLGeometricFilter(task_params)
                if not backend.supports_layer(layer):
                    logger.warning(
                        f"⚠️ PostgreSQL backend forced for '{layer.name()}' but layer type may not be fully supported. "
                        f"Proceeding with forced backend as requested."
                    )
                if return_memory_info:
                    return (backend, None, False)
                return backend
            
            elif forced_backend == 'spatialite':
                backend = SpatialiteGeometricFilter(task_params)
                if not backend.supports_layer(layer):
                    # FIX v2.4.19: Auto-fallback to OGR when forced Spatialite doesn't work
                    # Spatialite SQL functions may not be available in GDAL/OGR driver
                    # Using OGR backend (QGIS processing) ensures spatial filtering works
                    logger.warning(
                        f"⚠️ Spatialite backend forced for '{layer.name()}' but Spatialite functions NOT available. "
                        f"Falling back to OGR backend (QGIS processing) for reliable spatial filtering."
                    )
                    from qgis.core import QgsMessageLog, Qgis
                    QgsMessageLog.logMessage(
                        f"⚠️ Spatialite unavailable for '{layer.name()}' - using OGR fallback",
                        "FilterMate", Qgis.Warning
                    )
                    backend = OGRGeometricFilter(task_params)
                    if return_memory_info:
                        return (backend, None, False)
                    return backend
                if return_memory_info:
                    return (backend, None, False)
                return backend
            
            elif forced_backend == 'ogr':
                backend = OGRGeometricFilter(task_params)
                logger.info(f"✓ Using OGR backend as forced for '{layer.name()}'")
                if return_memory_info:
                    return (backend, None, False)
                return backend
            
            elif forced_backend == 'memory':
                backend = MemoryGeometricFilter(task_params)
                logger.info(f"✓ Using Memory backend as forced for '{layer.name()}'")
                if return_memory_info:
                    return (backend, None, False)
                return backend
            
            else:
                logger.warning(
                    f"⚠️ Unknown forced backend '{forced_backend}' for '{layer.name()}', "
                    f"falling back to auto-selection"
                )
        
        # PRIORITY 2: Auto-selection logic
        # Check for small PostgreSQL dataset optimization
        # PRIORITY 2.1: Native memory layers - use optimized Memory backend
        if layer_provider_type == PROVIDER_MEMORY or layer.providerType() == 'memory':
            logger.info(f"🧠 Using Memory backend for native memory layer '{layer.name()}'")
            backend = MemoryGeometricFilter(task_params)
            if return_memory_info:
                return (backend, None, False)
            return backend
        
        # PRIORITY 2.2: Small PostgreSQL dataset optimization
        if should_use_memory_optimization(layer, layer_provider_type):
            memory_layer = BackendFactory.get_memory_layer(layer)
            if memory_layer:
                use_optimization = True
                logger.info(
                    f"⚡ Using Memory backend optimization for small PostgreSQL layer "
                    f"'{layer.name()}' ({layer.featureCount()} features)"
                )
                # Use MemoryBackend instead of OGR for better performance
                backend = MemoryGeometricFilter(task_params)
                # Store memory layer reference in backend for spatial operations
                backend._memory_layer = memory_layer
                backend._original_layer = layer
                backend._use_memory_optimization = True
                
                if return_memory_info:
                    return (backend, memory_layer, True)
                return backend
            else:
                logger.warning(
                    f"Could not create memory layer for {layer.name()}, "
                    f"falling back to PostgreSQL backend"
                )
        
        # v2.5.x: PostgreSQL backend - always available via QGIS native API
        # psycopg2 is only required for advanced features (materialized views)
        if layer_provider_type == PROVIDER_POSTGRES:
            backend = PostgreSQLGeometricFilter(task_params)
            if backend.supports_layer(layer):
                if PSYCOPG2_AVAILABLE:
                    logger.info(f"✓ Using PostgreSQL backend for {layer.name()} (full features with psycopg2)")
                else:
                    logger.info(f"✓ Using PostgreSQL backend for {layer.name()} (QGIS native API, MVs disabled)")
                if return_memory_info:
                    return (backend, None, False)
                return backend
            else:
                # PostgreSQL layer but validation failed - fallback to OGR
                # OGR backend uses QGIS processing which works with all layer types
                logger.warning(f"PostgreSQL backend validation failed for {layer.name()}, falling back to OGR backend")
                backend = OGRGeometricFilter(task_params)
                if return_memory_info:
                    return (backend, None, False)
                return backend
        
        # Try Spatialite backend for Spatialite and GeoPackage/SQLite layers
        if layer_provider_type == PROVIDER_SPATIALITE:
            logger.info(f"   → Matched SPATIALITE branch (layer_provider_type='spatialite')")
            backend = SpatialiteGeometricFilter(task_params)
            logger.info(f"   → Testing Spatialite support via supports_layer()...")
            if backend.supports_layer(layer):
                logger.info(f"✓ Using Spatialite backend for {layer.name()}")
                if return_memory_info:
                    return (backend, None, False)
                return backend
            else:
                # Spatialite functions not available (e.g., GDAL without Spatialite support)
                # Fall back to OGR backend which uses QGIS processing
                logger.warning(
                    f"⚠️ Spatialite supports_layer() returned False for {layer.name()}, "
                    f"falling back to OGR backend"
                )
                backend = OGRGeometricFilter(task_params)
                if return_memory_info:
                    return (backend, None, False)
                return backend
        
        # For OGR layers, try Spatialite backend first (handles GeoPackage/SQLite)
        if layer_provider_type == PROVIDER_OGR:
            logger.info(f"   → Matched OGR branch (layer_provider_type='ogr')")
            backend = SpatialiteGeometricFilter(task_params)
            logger.info(f"   → Testing Spatialite support for OGR layer...")
            spatialite_supports = backend.supports_layer(layer)
            if spatialite_supports:
                logger.info(f"🚀 Using Spatialite backend for OGR layer {layer.name()} (GeoPackage/SQLite)")
                if return_memory_info:
                    return (backend, None, False)
                return backend
            else:
                # Log why Spatialite is not supported
                source = layer.source()
                source_path = source.split('|')[0] if '|' in source else source
                logger.info(
                    f"ℹ️ Spatialite backend not supported for {layer.name()} - "
                    f"source: {source_path[-80:] if len(source_path) > 80 else source_path}"
                )
        
        # Fallback to OGR backend (Shapefiles, GeoJSON, etc.)
        logger.info(f"→ Fallback: Using OGR backend for {layer.name()}")
        backend = OGRGeometricFilter(task_params)
        if return_memory_info:
            return (backend, None, False)
        return backend
    
    @staticmethod
    def get_backend_for_provider(
        provider_type: str,
        task_params: Dict
    ) -> GeometricFilterBackend:
        """
        Get backend instance for a provider type without checking layer.
        
        Note: This method does not apply small dataset optimization
        as it doesn't have access to the actual layer.
        
        Args:
            provider_type: Provider type string
            task_params: Task parameters
        
        Returns:
            Backend instance
        """
        if provider_type == PROVIDER_MEMORY:
            return MemoryGeometricFilter(task_params)
        elif provider_type == PROVIDER_POSTGRES and POSTGRESQL_AVAILABLE:
            return PostgreSQLGeometricFilter(task_params)
        elif provider_type == PROVIDER_SPATIALITE:
            return SpatialiteGeometricFilter(task_params)
        else:
            return OGRGeometricFilter(task_params)

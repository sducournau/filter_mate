# -*- coding: utf-8 -*-
"""
Backend Factory for FilterMate - Hexagonal Architecture.

Factory pattern implementation for selecting the appropriate backend
based on layer provider type.

Part of the Phase 4 architecture refactoring.

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Dict, Optional, Tuple, TYPE_CHECKING

from core.ports.backend_port import BackendPort
from core.domain.filter_expression import ProviderType
from core.domain.layer_info import LayerInfo

if TYPE_CHECKING:
    from infrastructure.di.container import Container

logger = logging.getLogger('FilterMate.Backend.Factory')


# Default thresholds
DEFAULT_SMALL_DATASET_THRESHOLD = 5000
DEFAULT_CACHE_MAX_AGE = 300  # 5 minutes


class BackendSelector:
    """
    Strategy for selecting the best backend for a layer.
    
    Implements intelligent backend selection based on:
    - Layer provider type
    - Dataset size
    - Available backends
    - User preferences (forced backend)
    - Optimization heuristics
    """
    
    # Priority order for fallback
    FALLBACK_PRIORITY = [
        ProviderType.OGR,
        ProviderType.MEMORY,
    ]
    
    def __init__(
        self,
        postgresql_available: bool = False,
        small_dataset_optimization: bool = False,
        small_dataset_threshold: int = DEFAULT_SMALL_DATASET_THRESHOLD
    ):
        """
        Initialize backend selector.
        
        Args:
            postgresql_available: Whether psycopg2 is installed
            small_dataset_optimization: Enable memory optimization for small PG datasets
            small_dataset_threshold: Threshold for small dataset optimization
        """
        self._postgresql_available = postgresql_available
        self._small_dataset_optimization = small_dataset_optimization
        self._small_dataset_threshold = small_dataset_threshold
    
    def select_provider_type(
        self,
        layer_info: LayerInfo,
        forced_backend: Optional[str] = None
    ) -> ProviderType:
        """
        Select the best provider type for a layer.
        
        Args:
            layer_info: Layer information
            forced_backend: User-forced backend (overrides auto-selection)
            
        Returns:
            Selected ProviderType
        """
        # Priority 1: User forced backend
        if forced_backend:
            return self._parse_forced_backend(forced_backend)
        
        # Priority 2: Native memory layers
        if layer_info.provider_type == ProviderType.MEMORY:
            return ProviderType.MEMORY
        
        # Priority 3: Small PostgreSQL dataset optimization
        if (
            layer_info.provider_type == ProviderType.POSTGRESQL
            and self._should_use_memory_optimization(layer_info)
        ):
            logger.info(
                f"Small dataset optimization: {layer_info.name} has "
                f"{layer_info.feature_count} features, using MEMORY backend"
            )
            return ProviderType.MEMORY
        
        # Priority 4: PostgreSQL with psycopg2
        if (
            layer_info.provider_type == ProviderType.POSTGRESQL
            and self._postgresql_available
        ):
            return ProviderType.POSTGRESQL
        
        # Priority 5: PostgreSQL without psycopg2 - fallback to OGR
        if (
            layer_info.provider_type == ProviderType.POSTGRESQL
            and not self._postgresql_available
        ):
            logger.info(
                f"PostgreSQL layer {layer_info.name} but psycopg2 not available, "
                f"using OGR backend"
            )
            return ProviderType.OGR
        
        # Priority 6: Spatialite
        if layer_info.provider_type == ProviderType.SPATIALITE:
            return ProviderType.SPATIALITE
        
        # Priority 7: OGR for file-based layers
        if layer_info.provider_type == ProviderType.OGR:
            return ProviderType.OGR
        
        # Default fallback
        logger.warning(
            f"Unknown provider type for {layer_info.name}, using OGR fallback"
        )
        return ProviderType.OGR
    
    def _parse_forced_backend(self, forced_backend: str) -> ProviderType:
        """Parse forced backend string to ProviderType."""
        mapping = {
            'postgresql': ProviderType.POSTGRESQL,
            'postgres': ProviderType.POSTGRESQL,
            'spatialite': ProviderType.SPATIALITE,
            'ogr': ProviderType.OGR,
            'memory': ProviderType.MEMORY,
        }
        provider = mapping.get(forced_backend.lower())
        if provider is None:
            logger.warning(f"Unknown forced backend: {forced_backend}")
            return ProviderType.OGR
        return provider
    
    def _should_use_memory_optimization(self, layer_info: LayerInfo) -> bool:
        """Check if memory optimization should be used for PostgreSQL layer."""
        if not self._small_dataset_optimization:
            return False
        
        if layer_info.feature_count is None:
            return False
        
        return layer_info.feature_count <= self._small_dataset_threshold


class BackendFactory:
    """
    Factory for creating and managing backend instances.
    
    Features:
    - Lazy initialization of backends
    - Backend caching for singleton pattern
    - Fallback chain when preferred backend fails
    - Configuration-driven behavior
    
    Example:
        factory = BackendFactory(container)
        backend = factory.get_backend(layer_info)
        result = backend.execute(expression, layer_info)
    """
    
    def __init__(
        self,
        container: Optional['Container'] = None,
        config: Optional[Dict] = None
    ):
        """
        Initialize backend factory.
        
        Args:
            container: DI container for resolving backends
            config: Configuration dictionary
        """
        self._container = container
        self._config = config or {}
        self._backends: Dict[ProviderType, BackendPort] = {}
        
        # Check PostgreSQL availability
        self._postgresql_available = self._check_postgresql_available()
        
        # Initialize selector
        opt_config = self._config.get('small_dataset_optimization', {})
        self._selector = BackendSelector(
            postgresql_available=self._postgresql_available,
            small_dataset_optimization=opt_config.get('enabled', False),
            small_dataset_threshold=opt_config.get(
                'threshold',
                DEFAULT_SMALL_DATASET_THRESHOLD
            )
        )
        
        logger.debug(f"BackendFactory initialized: postgresql={self._postgresql_available}")
    
    def _check_postgresql_available(self) -> bool:
        """Check if PostgreSQL backend is available."""
        try:
            from adapters.backends import POSTGRESQL_AVAILABLE
            return POSTGRESQL_AVAILABLE
        except ImportError:
            try:
                return True
            except ImportError:
                return False
    
    def get_backend(
        self,
        layer_info: LayerInfo,
        forced_backend: Optional[str] = None
    ) -> BackendPort:
        """
        Get appropriate backend for a layer.
        
        Args:
            layer_info: Layer information
            forced_backend: User-forced backend name
            
        Returns:
            Backend instance
            
        Raises:
            RuntimeError: If no backend is available
        """
        # Select provider type
        provider_type = self._selector.select_provider_type(
            layer_info,
            forced_backend
        )
        
        logger.info(
            f"Selected backend {provider_type.value} for layer {layer_info.name}"
        )
        
        # Get or create backend
        backend = self._get_or_create_backend(provider_type)
        
        if backend is not None:
            return backend
        
        # Fallback chain
        return self._get_fallback_backend(provider_type)
    
    def get_backend_for_provider(
        self,
        provider_type: ProviderType
    ) -> Optional[BackendPort]:
        """
        Get backend for a specific provider type.
        
        Args:
            provider_type: The provider type
            
        Returns:
            Backend instance or None
        """
        return self._get_or_create_backend(provider_type)
    
    def _get_or_create_backend(
        self,
        provider_type: ProviderType
    ) -> Optional[BackendPort]:
        """Get cached backend or create new one."""
        # Check cache first
        if provider_type in self._backends:
            return self._backends[provider_type]
        
        # Try to create backend
        backend = self._create_backend(provider_type)
        
        if backend is not None:
            self._backends[provider_type] = backend
        
        return backend
    
    def _create_backend(
        self,
        provider_type: ProviderType
    ) -> Optional[BackendPort]:
        """Create a new backend instance."""
        try:
            if provider_type == ProviderType.MEMORY:
                from adapters.backends.memory.backend import MemoryBackend
                return MemoryBackend()
            
            elif provider_type == ProviderType.OGR:
                from adapters.backends.ogr.backend import OGRBackend
                return OGRBackend()
            
            elif provider_type == ProviderType.SPATIALITE:
                from adapters.backends.spatialite.backend import SpatialiteBackend
                return SpatialiteBackend()
            
            elif provider_type == ProviderType.POSTGRESQL:
                if not self._postgresql_available:
                    logger.warning("PostgreSQL backend requested but not available")
                    return None
                from adapters.backends.postgresql.backend import PostgreSQLBackend
                return PostgreSQLBackend()
            
            else:
                logger.warning(f"Unknown provider type: {provider_type}")
                return None
                
        except ImportError as e:
            logger.warning(f"Failed to import backend for {provider_type}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to create backend for {provider_type}: {e}")
            return None
    
    def _get_fallback_backend(
        self,
        original_type: ProviderType
    ) -> BackendPort:
        """Get a fallback backend when preferred is not available."""
        for fallback_type in BackendSelector.FALLBACK_PRIORITY:
            if fallback_type != original_type:
                backend = self._get_or_create_backend(fallback_type)
                if backend is not None:
                    logger.info(
                        f"Using {fallback_type.value} as fallback for "
                        f"{original_type.value}"
                    )
                    return backend
        
        raise RuntimeError(
            f"No backend available for {original_type.value} and no fallback found"
        )
    
    def get_all_backends(self) -> Dict[ProviderType, BackendPort]:
        """
        Get all initialized backends.
        
        Returns:
            Dictionary of provider type to backend
        """
        return dict(self._backends)
    
    def cleanup(self) -> None:
        """Clean up all backends."""
        for provider_type, backend in self._backends.items():
            try:
                backend.cleanup()
                logger.debug(f"Cleaned up {provider_type.value} backend")
            except Exception as e:
                logger.warning(f"Error cleaning up {provider_type.value}: {e}")
        
        self._backends.clear()
    
    @property
    def postgresql_available(self) -> bool:
        """Check if PostgreSQL backend is available."""
        return self._postgresql_available
    
    @property
    def available_backends(self) -> Tuple[ProviderType, ...]:
        """Get list of available backend types."""
        available = [ProviderType.OGR, ProviderType.MEMORY, ProviderType.SPATIALITE]
        if self._postgresql_available:
            available.insert(0, ProviderType.POSTGRESQL)
        return tuple(available)


def create_backend_factory(
    container: Optional['Container'] = None,
    config: Optional[Dict] = None
) -> BackendFactory:
    """
    Create a configured BackendFactory instance.
    
    Args:
        container: Optional DI container
        config: Optional configuration
        
    Returns:
        Configured BackendFactory
    """
    return BackendFactory(container=container, config=config)

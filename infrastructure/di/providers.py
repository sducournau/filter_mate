# -*- coding: utf-8 -*-
"""
Service Providers for Dependency Injection.

Provides configuration for the DI container,
registering all services needed by FilterMate.

Author: FilterMate Team
Date: January 2026
"""

from typing import Dict, Optional
import logging

from .container import Container

# Ports
from core.ports.backend_port import BackendPort
from core.ports.cache_port import CachePort
from core.ports.repository_port import LayerRepositoryPort

# Domain
from core.domain.filter_expression import ProviderType

# Services
from core.services.filter_service import FilterService
from core.services.expression_service import ExpressionService

logger = logging.getLogger('FilterMate.DI.Providers')


class BackendProvider:
    """
    Provides backend registration for the DI container.
    
    Registers all available backends based on configuration
    and runtime availability.
    """
    
    @staticmethod
    def register_backends(
        container: Container,
        config: Optional[Dict] = None
    ) -> None:
        """
        Register all available backends.
        
        Args:
            container: DI container
            config: Optional configuration dictionary
        """
        config = config or {}
        
        # Import backends conditionally to avoid import errors
        # when dependencies are not available
        
        # Memory backend (always available)
        from adapters.backends.memory.backend import MemoryBackend
        container.register_singleton(
            MemoryBackend,
            lambda c: MemoryBackend()
        )
        logger.debug("Registered MemoryBackend")
        
        # OGR backend (always available)
        from adapters.backends.ogr.backend import OGRBackend
        container.register_singleton(
            OGRBackend,
            lambda c: OGRBackend()
        )
        logger.debug("Registered OGRBackend")
        
        # Spatialite backend (always available)
        from adapters.backends.spatialite.backend import SpatialiteBackend
        container.register_singleton(
            SpatialiteBackend,
            lambda c: SpatialiteBackend(
                cache=c.try_resolve(CachePort)
            )
        )
        logger.debug("Registered SpatialiteBackend")
        
        # PostgreSQL backend (conditional on psycopg2)
        try:
            from adapters.backends import POSTGRESQL_AVAILABLE
            if POSTGRESQL_AVAILABLE:
                from adapters.backends.postgresql.backend import PostgreSQLBackend
                container.register_singleton(
                    PostgreSQLBackend,
                    lambda c: PostgreSQLBackend(
                        use_mv_optimization=config.get('use_mv_optimization', True)
                    )
                )
                logger.debug("Registered PostgreSQLBackend")
            else:
                logger.info("PostgreSQL backend not available (psycopg2 not installed)")
        except ImportError as e:
            logger.info(f"PostgreSQL backend not available: {e}")
        
        # Register the backend factory
        container.register_singleton(
            'BackendFactory',
            lambda c: BackendFactory(c)
        )


class BackendFactory:
    """
    Factory for selecting appropriate backend for a layer.
    
    Implements the Strategy pattern to select the best
    backend based on layer type and configuration.
    """
    
    def __init__(self, container: Container):
        """
        Initialize factory with DI container.
        
        Args:
            container: DI container with registered backends
        """
        self._container = container
        self._backend_priority = [
            ProviderType.POSTGRESQL,
            ProviderType.SPATIALITE,
            ProviderType.OGR,
            ProviderType.MEMORY,
        ]
    
    def get_backend_for_provider(self, provider_type: ProviderType) -> Optional[BackendPort]:
        """
        Get appropriate backend for a provider type.
        
        Args:
            provider_type: The data provider type
            
        Returns:
            Backend instance or None if not available
        """
        backend_map = {
            ProviderType.POSTGRESQL: 'PostgreSQLBackend',
            ProviderType.SPATIALITE: 'SpatialiteBackend',
            ProviderType.OGR: 'OGRBackend',
            ProviderType.MEMORY: 'MemoryBackend',
        }
        
        backend_name = backend_map.get(provider_type)
        if backend_name:
            # Try to resolve from container
            try:
                # Get the class from the name
                if provider_type == ProviderType.POSTGRESQL:
                    from adapters.backends.postgresql.backend import PostgreSQLBackend
                    return self._container.try_resolve(PostgreSQLBackend)
                elif provider_type == ProviderType.SPATIALITE:
                    from adapters.backends.spatialite.backend import SpatialiteBackend
                    return self._container.try_resolve(SpatialiteBackend)
                elif provider_type == ProviderType.OGR:
                    from adapters.backends.ogr.backend import OGRBackend
                    return self._container.try_resolve(OGRBackend)
                elif provider_type == ProviderType.MEMORY:
                    from adapters.backends.memory.backend import MemoryBackend
                    return self._container.try_resolve(MemoryBackend)
            except Exception as e:
                logger.warning(f"Failed to resolve backend for {provider_type}: {e}")
        
        return None
    
    def get_best_backend(self, provider_type: ProviderType) -> BackendPort:
        """
        Get the best available backend for a provider type.
        
        Falls back to OGR if preferred backend not available.
        
        Args:
            provider_type: The data provider type
            
        Returns:
            Backend instance
            
        Raises:
            RuntimeError: If no backend is available
        """
        # Try preferred backend
        backend = self.get_backend_for_provider(provider_type)
        if backend is not None:
            return backend
        
        # Fall back through priority list
        for fallback_type in [ProviderType.OGR, ProviderType.MEMORY]:
            if fallback_type != provider_type:
                backend = self.get_backend_for_provider(fallback_type)
                if backend is not None:
                    logger.info(
                        f"Using {fallback_type.value} as fallback for {provider_type.value}"
                    )
                    return backend
        
        raise RuntimeError("No backend available")


class ServiceProvider:
    """
    Provides core service registration for the DI container.
    
    Registers domain services, repositories, and infrastructure.
    """
    
    @staticmethod
    def register_services(
        container: Container,
        config: Optional[Dict] = None
    ) -> None:
        """
        Register all core services.
        
        Args:
            container: DI container
            config: Optional configuration dictionary
        """
        config = config or {}
        
        # Register expression service
        container.register_singleton(
            ExpressionService,
            lambda c: ExpressionService()
        )
        logger.debug("Registered ExpressionService")
        
        # Register cache (infrastructure)
        try:
            from infrastructure.cache.filter_cache import FilterCache
            cache_config = config.get('cache', {})
            container.register_singleton(
                CachePort,
                lambda c: FilterCache(
                    max_size=cache_config.get('max_size', 1000),
                    ttl_seconds=cache_config.get('ttl_seconds', 3600)
                )
            )
            logger.debug("Registered FilterCache as CachePort")
        except ImportError:
            logger.warning("FilterCache not available, cache disabled")
        
        # Register layer repository
        try:
            from adapters.repositories.layer_repository import QGISLayerRepository
            container.register_singleton(
                LayerRepositoryPort,
                lambda c: QGISLayerRepository()
            )
            logger.debug("Registered QGISLayerRepository")
        except ImportError:
            logger.warning("QGISLayerRepository not available")
        
        # Register filter service
        container.register_singleton(
            FilterService,
            lambda c: FilterService(
                backend_factory=c.resolve('BackendFactory'),
                cache=c.try_resolve(CachePort),
                layer_repository=c.try_resolve(LayerRepositoryPort),
                expression_service=c.resolve(ExpressionService)
            )
        )
        logger.debug("Registered FilterService")


def configure_container(config: Optional[Dict] = None) -> Container:
    """
    Configure and return a fully initialized container.
    
    This is the Composition Root for the application.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Configured Container instance
    """
    from .container import get_container
    
    container = get_container()
    config = config or {}
    
    # Register in order of dependencies
    BackendProvider.register_backends(container, config)
    ServiceProvider.register_services(container, config)
    
    logger.info("DI Container configured successfully")
    return container

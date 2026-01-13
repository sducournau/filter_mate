# -*- coding: utf-8 -*-
"""
Backend Registry Implementation.

v4.0.1: Implements BackendRegistryPort to provide dependency injection
for filter executors. This is the bridge between core/ and adapters/.

The registry is instantiated in filter_mate_app.py and injected into
FilterEngineTask, eliminating direct imports from core/ to adapters/.
"""
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..core.ports.filter_executor_port import (
    FilterExecutorPort,
    FilterExecutionResult,
    FilterStatus,
    BackendRegistryPort,
)

if TYPE_CHECKING:
    from qgis.core import QgsVectorLayer

logger = logging.getLogger('FilterMate')


class BackendRegistry(BackendRegistryPort):
    """
    Central registry for filter backends.
    
    Provides backend selection based on layer type without requiring
    core/ to know about concrete backend implementations.
    
    Usage:
        # In filter_mate_app.py (initialization)
        registry = BackendRegistry()
        
        # In FilterEngineTask (usage)
        executor = self.backend_registry.get_executor(layer_info)
        result = executor.execute_filter(...)
    """
    
    def __init__(self):
        """Initialize the backend registry with available backends."""
        self._executors: Dict[str, FilterExecutorPort] = {}
        self._postgresql_available = False
        self._initialize_backends()
    
    def _initialize_backends(self):
        """Initialize available backends lazily."""
        # Check PostgreSQL availability
        try:
            from .backends.postgresql_availability import POSTGRESQL_AVAILABLE
            self._postgresql_available = POSTGRESQL_AVAILABLE
        except ImportError:
            self._postgresql_available = False
            logger.debug("PostgreSQL backend not available (psycopg2 not installed)")
    
    def get_executor(self, layer_info: Dict[str, Any]) -> FilterExecutorPort:
        """
        Get appropriate filter executor for a layer.
        
        Args:
            layer_info: Layer metadata including 'layer_provider_type'
            
        Returns:
            FilterExecutorPort implementation suitable for the layer
        """
        provider_type = layer_info.get('layer_provider_type', 'unknown')
        
        # Map provider types to backends
        if provider_type == 'postgresql' and self._postgresql_available:
            return self._get_postgresql_executor()
        elif provider_type == 'spatialite':
            return self._get_spatialite_executor()
        elif provider_type == 'ogr':
            return self._get_ogr_executor()
        else:
            # Default to OGR (universal fallback)
            return self._get_ogr_executor()
    
    def get_executor_by_name(self, backend_name: str) -> Optional[FilterExecutorPort]:
        """Get a specific backend by name."""
        if backend_name == 'postgresql':
            if self._postgresql_available:
                return self._get_postgresql_executor()
            return None
        elif backend_name == 'spatialite':
            return self._get_spatialite_executor()
        elif backend_name == 'ogr':
            return self._get_ogr_executor()
        elif backend_name == 'memory':
            return self._get_memory_executor()
        return None
    
    def is_available(self, backend_name: str) -> bool:
        """Check if a specific backend is available."""
        if backend_name == 'postgresql':
            return self._postgresql_available
        elif backend_name in ('spatialite', 'ogr', 'memory'):
            return True
        return False
    
    @property
    def postgresql_available(self) -> bool:
        """Return True if PostgreSQL backend is available."""
        return self._postgresql_available
    
    # Lazy loading of backend executors
    def _get_postgresql_executor(self) -> FilterExecutorPort:
        """Get or create PostgreSQL executor."""
        if 'postgresql' not in self._executors:
            from .backends.postgresql import PostgreSQLFilterExecutor
            self._executors['postgresql'] = PostgreSQLFilterExecutor()
        return self._executors['postgresql']
    
    def _get_spatialite_executor(self) -> FilterExecutorPort:
        """Get or create Spatialite executor."""
        if 'spatialite' not in self._executors:
            from .backends.spatialite import SpatialiteFilterExecutor
            self._executors['spatialite'] = SpatialiteFilterExecutor()
        return self._executors['spatialite']
    
    def _get_ogr_executor(self) -> FilterExecutorPort:
        """Get or create OGR executor."""
        if 'ogr' not in self._executors:
            from .backends.ogr import OGRFilterExecutor
            self._executors['ogr'] = OGRFilterExecutor()
        return self._executors['ogr']
    
    def _get_memory_executor(self) -> FilterExecutorPort:
        """Get or create Memory executor."""
        if 'memory' not in self._executors:
            # Memory backend uses OGR executor as fallback
            from .backends.ogr import OGRFilterExecutor
            self._executors['memory'] = OGRFilterExecutor()
        return self._executors['memory']
    
    def cleanup_all(self) -> None:
        """Clean up all backend resources."""
        for name, executor in self._executors.items():
            try:
                executor.cleanup_resources()
                logger.debug(f"Cleaned up {name} backend")
            except Exception as e:
                logger.warning(f"Error cleaning up {name} backend: {e}")


# Global singleton instance (optional, for backward compatibility)
_registry_instance: Optional[BackendRegistry] = None


def get_backend_registry() -> BackendRegistry:
    """
    Get the global backend registry instance.
    
    This is a convenience function for code that cannot use DI.
    Prefer injecting BackendRegistry directly when possible.
    """
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = BackendRegistry()
    return _registry_instance


def reset_backend_registry() -> None:
    """Reset the global registry instance (for testing)."""
    global _registry_instance
    if _registry_instance:
        _registry_instance.cleanup_all()
    _registry_instance = None

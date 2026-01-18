# -*- coding: utf-8 -*-
"""
Legacy Backend Adapters.

v4.1.0: Wrappers that expose the new BackendPort interface using the legacy
GeometricFilterBackend API (build_expression + apply_filter).

This enables progressive migration from before_migration backends to new
hexagonal architecture backends without breaking FilterEngineTask.

Migration Strategy:
1. Legacy code calls: backend = BackendFactory.get_backend(provider_type, layer, task_params)
2. BackendFactory returns: LegacyPostgreSQLAdapter / LegacySpatialiteAdapter / LegacyOGRAdapter
3. These adapters implement: build_expression() + apply_filter() (legacy interface)
4. Internally delegate to: new BackendPort.execute() when available

Author: FilterMate Team
Date: January 2026
"""

import logging
from abc import abstractmethod
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger('FilterMate.Backend.LegacyAdapter')


# v4.2.0: Define base interface (no more before_migration imports!)
class GeometricFilterBackend:
    """Base interface for legacy geometric filter backends."""
    def __init__(self, task_params: Dict):
        self.task_params = task_params
        self.logger = logger
    
    def build_expression(self, layer_props, predicates, source_geom=None, 
                       buffer_value=None, buffer_expression=None, 
                       source_filter=None, use_centroids=False, **kwargs) -> str:
        raise NotImplementedError()
    
    def apply_filter(self, layer, expression, old_subset=None, combine_operator=None) -> bool:
        raise NotImplementedError()
    
    def supports_layer(self, layer) -> bool:
        raise NotImplementedError()

# No more before_migration dependency
LEGACY_BASE_AVAILABLE = False


class BaseLegacyAdapter(GeometricFilterBackend):
    """
    Base adapter for wrapping new backends with legacy interface.
    
    Subclasses must implement:
    - _get_new_backend() -> BackendPort
    - _get_legacy_backend() -> GeometricFilterBackend (fallback)
    - provider_type property
    """
    
    def __init__(self, task_params: Dict):
        """Initialize adapter with task parameters."""
        super().__init__(task_params)
        self._new_backend = None
        self._legacy_backend = None
        self._use_new_backend = True  # v4.2.0: FORCE NEW BACKENDS (before_migration removed)
        
        # Try to initialize new backend
        try:
            self._new_backend = self._create_new_backend()
            if self._new_backend:
                # v4.2.0: Always use new backend now
                self._use_new_backend = True
                logger.debug(f"{self.provider_type}: New backend loaded (forced)")
        except Exception as e:
            logger.error(f"{self.provider_type}: New backend FAILED to load: {e}")
            raise RuntimeError(f"Cannot load {self.provider_type} backend - before_migration removed!")
        
        # v4.2.0: Legacy backends no longer available (before_migration removed)
        # The new backends must handle everything now
        logger.debug(f"{self.provider_type}: Using new hexagonal backend (no legacy fallback)")
    
    @property
    @abstractmethod
    def provider_type(self) -> str:
        """Return provider type string ('postgresql', 'spatialite', 'ogr')."""
        pass
    
    @abstractmethod
    def _create_new_backend(self):
        """Create new BackendPort implementation."""
        pass
    
    def _create_legacy_backend(self) -> GeometricFilterBackend:
        """
        v4.2.0: Legacy backends removed (before_migration gone).
        This method is now a no-op stub for backward compatibility.
        """
        return None
    
    def _should_use_new_backend(self) -> bool:
        """
        v4.2.0: ALWAYS use new backend (before_migration removed).
        """
        return True  # Force new backend since legacy is no longer available
    
    def build_expression(
        self, 
        layer_props: Dict, 
        predicates: Dict,
        source_geom: Optional[str] = None,
        buffer_value: Optional[float] = None,
        buffer_expression: Optional[str] = None,
        source_filter: Optional[str] = None,
        use_centroids: bool = False,
        **kwargs
    ) -> str:
        """Build filter expression, delegating to appropriate backend."""
        if self._use_new_backend and self._new_backend:
            return self._build_expression_new(
                layer_props, predicates, source_geom, buffer_value,
                buffer_expression, source_filter, use_centroids, **kwargs
            )
        elif self._legacy_backend:
            # FIX v4.0.3 (2026-01-16): Pass ALL arguments as KEYWORD arguments
            # to avoid positional mismatch between adapter and legacy backend signatures.
            # PostgreSQLGeometricFilter.build_expression() has source_wkt/source_srid/source_feature_count
            # BEFORE use_centroids, but this adapter had use_centroids in different position.
            return self._legacy_backend.build_expression(
                layer_props=layer_props,
                predicates=predicates,
                source_geom=source_geom,
                buffer_value=buffer_value,
                buffer_expression=buffer_expression,
                source_filter=source_filter,
                use_centroids=use_centroids,
                **kwargs
            )
        else:
            raise RuntimeError(f"No backend available for {self.provider_type}")
    
    def _build_expression_new(
        self,
        layer_props: Dict,
        predicates: Dict,
        source_geom: Optional[str],
        buffer_value: Optional[float],
        buffer_expression: Optional[str],
        source_filter: Optional[str],
        use_centroids: bool,
        **kwargs
    ) -> str:
        """
        Build expression using new backend wrapper.
        
        v4.2.0: Now uses executor wrappers which implement GeometricFilterBackend interface.
        The wrappers (OGRFilterExecutor, SpatialiteFilterExecutor, etc.) have build_expression().
        """
        # v4.2.0: Use new backend (wrapper) which has build_expression()
        if self._new_backend:
            return self._new_backend.build_expression(
                layer_props=layer_props,
                predicates=predicates,
                source_geom=source_geom,
                buffer_value=buffer_value,
                buffer_expression=buffer_expression,
                source_filter=source_filter,
                use_centroids=use_centroids,
                **kwargs
            )
        raise RuntimeError(f"No backend available for {self.provider_type}")
    
    def _get_provider_type_enum(self):
        """Get ProviderType enum for this backend."""
        from ...core.domain.filter_expression import ProviderType
        mapping = {
            'postgresql': ProviderType.POSTGRESQL,
            'spatialite': ProviderType.SPATIALITE,
            'ogr': ProviderType.OGR,
            'memory': ProviderType.MEMORY,
        }
        return mapping.get(self.provider_type, ProviderType.OGR)
    
    def apply_filter(
        self, 
        layer,
        expression: str,
        old_subset: Optional[str] = None,
        combine_operator: Optional[str] = None
    ) -> bool:
        """Apply filter expression to layer."""
        if self._use_new_backend and self._new_backend:
            return self._apply_filter_new(layer, expression, old_subset, combine_operator)
        elif self._legacy_backend:
            return self._legacy_backend.apply_filter(layer, expression, old_subset, combine_operator)
        else:
            raise RuntimeError(f"No backend available for {self.provider_type}")
    
    def _apply_filter_new(
        self,
        layer,
        expression: str,
        old_subset: Optional[str],
        combine_operator: Optional[str]
    ) -> bool:
        """Apply filter using new backend."""
        try:
            # Combine with old subset if needed
            final_expr = expression
            if old_subset and combine_operator:
                final_expr = f"({old_subset}) {combine_operator} ({expression})"
            elif old_subset:
                final_expr = f"({old_subset}) AND ({expression})"
            
            # v4.2.0: Use QGIS API directly (no more before_migration dependency)
            layer.setSubsetString(final_expr)
            return True
            
        except Exception as e:
            logger.error(f"New backend apply_filter failed: {e}")
            if self._legacy_backend:
                return self._legacy_backend.apply_filter(layer, expression, old_subset, combine_operator)
            return False
    
    def supports_layer(self, layer) -> bool:
        """Check if backend supports the given layer."""
        if self._use_new_backend and self._new_backend:
            try:
                from ...core.domain.layer_info import LayerInfo
                layer_info = LayerInfo.from_qgis_layer(layer)
                return self._new_backend.supports_layer(layer_info)
            except Exception:
                pass
        
        if self._legacy_backend:
            return self._legacy_backend.supports_layer(layer)
        
        return False
    
    def get_backend_name(self) -> str:
        """Get backend display name for logging (internal name must be plain 'PostgreSQL')."""
        suffix = "(v4)" if self._use_new_backend else "(Legacy)"
        # Return plain provider name for TaskBridge compatibility
        # Display suffix is added only in user messages via infrastructure/feedback
        return self.provider_type.capitalize()


class LegacyPostgreSQLAdapter(BaseLegacyAdapter):
    """
    Legacy adapter for PostgreSQL backend.
    
    Wraps new PostgreSQLBackend with GeometricFilterBackend interface.
    """
    
    @property
    def provider_type(self) -> str:
        return 'postgresql'
    
    def _create_new_backend(self):
        """Create new PostgreSQL backend wrapper."""
        try:
            from .postgresql.executor_wrapper import PostgreSQLFilterExecutor
            return PostgreSQLFilterExecutor()
        except ImportError:
            # PostgreSQL wrapper not yet implemented, return basic stub
            logger.warning("PostgreSQL executor wrapper not available yet")
            return None
    
    def _create_legacy_backend(self) -> GeometricFilterBackend:
        """Create legacy PostgreSQL backend - no longer available."""
        # v4.2.0: before_migration removed, only new backend available
        logger.warning("PostgreSQL legacy backend unavailable (before_migration removed)")
        return None
    
    # v4.2.0: Removed _should_use_new_backend() - always uses new backend


class LegacySpatialiteAdapter(BaseLegacyAdapter):
    """
    Legacy adapter for Spatialite backend.
    
    Wraps new SpatialiteBackend with GeometricFilterBackend interface.
    """
    
    @property
    def provider_type(self) -> str:
        return 'spatialite'
    
    def _create_new_backend(self):
        """Create new Spatialite backend wrapper with build_expression() support."""
        from .spatialite.executor_wrapper import SpatialiteFilterExecutor
        return SpatialiteFilterExecutor()
    
    def _create_legacy_backend(self) -> GeometricFilterBackend:
        """Create legacy Spatialite backend - no longer available."""
        # v4.2.0: before_migration removed, only new backend available
        logger.warning("Spatialite legacy backend unavailable (before_migration removed)")
        return None
    
    # v4.2.0: Removed _should_use_new_backend() - always uses new backend


class LegacyOGRAdapter(BaseLegacyAdapter):
    """
    Legacy adapter for OGR backend.
    
    Wraps new OGRBackend with GeometricFilterBackend interface.
    v4.1.0: First backend to test new architecture.
    """
    
    @property
    def provider_type(self) -> str:
        return 'ogr'
    
    def _create_new_backend(self):
        """Create new OGR backend wrapper with build_expression() support."""
        from .ogr.executor_wrapper import OGRFilterExecutor
        return OGRFilterExecutor()
    
    def _create_legacy_backend(self) -> GeometricFilterBackend:
        """Create legacy OGR backend - no longer available."""
        # v4.2.0: before_migration removed, only new backend available
        logger.warning("OGR legacy backend unavailable (before_migration removed)")
        return None
    
    # v4.2.0: Removed _should_use_new_backend() - always uses new backend


class LegacyMemoryAdapter(BaseLegacyAdapter):
    """
    Legacy adapter for Memory backend.
    
    Wraps new MemoryBackend with GeometricFilterBackend interface.
    v4.1.0: Second backend to test new architecture.
    """
    
    @property
    def provider_type(self) -> str:
        return 'memory'
    
    def _create_new_backend(self):
        """Create new Memory backend wrapper with build_expression() support."""
        try:
            from .memory.executor_wrapper import MemoryFilterExecutor
            return MemoryFilterExecutor()
        except ImportError:
            logger.warning("Memory executor wrapper not available yet")
            return None
    
    def _create_legacy_backend(self) -> GeometricFilterBackend:
        """Create legacy Memory backend - no longer available."""
        # v4.2.0: before_migration removed, only new backend available
        logger.warning("Memory legacy backend unavailable (before_migration removed)")
        return None
    
    # v4.2.0: Removed _should_use_new_backend() - always uses new backend


def get_legacy_adapter(provider_type: str, task_params: Dict) -> GeometricFilterBackend:
    """
    Factory function to get appropriate legacy adapter.
    
    Args:
        provider_type: Provider type string ('postgresql', 'spatialite', 'ogr', 'memory')
        task_params: Task parameters dictionary
        
    Returns:
        GeometricFilterBackend implementation (adapter or legacy backend)
    """
    adapters = {
        'postgresql': LegacyPostgreSQLAdapter,
        'postgres': LegacyPostgreSQLAdapter,
        'spatialite': LegacySpatialiteAdapter,
        'ogr': LegacyOGRAdapter,
        'memory': LegacyMemoryAdapter,
    }
    
    adapter_class = adapters.get(provider_type.lower(), LegacyOGRAdapter)
    
    try:
        adapter = adapter_class(task_params)
        logger.info(f"🔧 Created {adapter.get_backend_name()} for provider '{provider_type}'")
        return adapter
    except Exception as e:
        logger.warning(f"Could not create adapter for {provider_type}: {e}, falling back to OGR")
        return LegacyOGRAdapter(task_params)


# Feature flag to enable new backends progressively
# v4.1.0: Set to False by default, enable via set_new_backend_enabled() or config
ENABLE_NEW_BACKENDS = {
    'postgresql': False,  # Keep legacy (MV support, well-tested)
    'spatialite': False,  # Keep legacy (multi-step optimizer)
    'ogr': False,         # v4.1.0: First candidate for new backend testing
    'memory': False,      # v4.1.0: Second candidate for new backend testing
}


def set_new_backend_enabled(provider_type: str, enabled: bool):
    """
    Enable/disable new backend for a provider type.
    
    For progressive migration testing.
    
    Args:
        provider_type: Provider type to configure
        enabled: True to use new backend, False for legacy
        
    Example:
        >>> set_new_backend_enabled('ogr', True)
        >>> set_new_backend_enabled('memory', True)
    """
    if provider_type.lower() in ENABLE_NEW_BACKENDS:
        old_value = ENABLE_NEW_BACKENDS[provider_type.lower()]
        ENABLE_NEW_BACKENDS[provider_type.lower()] = enabled
        logger.info(f"🔄 Backend {provider_type.upper()}: {'LEGACY → NEW' if enabled else 'NEW → LEGACY'}")
    else:
        logger.warning(f"Unknown provider type: {provider_type}")


def is_new_backend_enabled(provider_type: str) -> bool:
    """Check if new backend is enabled for a provider type."""
    return ENABLE_NEW_BACKENDS.get(provider_type.lower(), False)


def get_backend_status() -> Dict[str, str]:
    """
    Get current backend status for all providers.
    
    Returns:
        Dict mapping provider type to 'new' or 'legacy'
        
    Example:
        >>> get_backend_status()
        {'postgresql': 'legacy', 'spatialite': 'legacy', 'ogr': 'new', 'memory': 'legacy'}
    """
    return {
        provider: 'new' if enabled else 'legacy'
        for provider, enabled in ENABLE_NEW_BACKENDS.items()
    }


def enable_experimental_backends():
    """
    Enable new backends for OGR and Memory (safest to test first).
    
    Call this to start progressive migration testing.
    """
    set_new_backend_enabled('ogr', True)
    set_new_backend_enabled('memory', True)
    logger.info("🧪 Experimental backends enabled: OGR, Memory")


def disable_all_new_backends():
    """Disable all new backends, revert to legacy."""
    for provider in ENABLE_NEW_BACKENDS:
        ENABLE_NEW_BACKENDS[provider] = False
    logger.info("🔙 All new backends disabled, using legacy")

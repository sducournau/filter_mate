# -*- coding: utf-8 -*-
"""
Legacy Backend Adapters.

v4.1.0: Wrappers that expose the new BackendPort interface using the legacy
GeometricFilterBackend API (build_expression + apply_filter).

This enables progressive migration from before_migration backends to new
hexagonal architecture backends without breaking FilterEngineTask.

v4.1.0 UPDATE: Now uses new ExpressionBuilders instead of before_migration backends.
The ExpressionBuilders implement the GeometricFilterPort interface with build_expression()
and apply_filter() methods migrated from the legacy code.

Migration Strategy:
1. Legacy code calls: backend = BackendFactory.get_backend(provider_type, layer, task_params)
2. BackendFactory returns: LegacyPostgreSQLAdapter / LegacySpatialiteAdapter / LegacyOGRAdapter
3. These adapters implement: build_expression() + apply_filter() (legacy interface)
4. Internally delegate to: new ExpressionBuilders (v4.1.0)

Author: FilterMate Team
Date: January 2026
"""

import logging
from abc import abstractmethod
from typing import Dict, Optional

logger = logging.getLogger('FilterMate.Backend.LegacyAdapter')


# v4.1.0: Import GeometricFilterPort from new location
try:
    from ...core.ports.geometric_filter_port import GeometricFilterPort
    GEOMETRIC_FILTER_PORT_AVAILABLE = True
except ImportError:
    GEOMETRIC_FILTER_PORT_AVAILABLE = False
    GeometricFilterPort = None

# v4.1.0: Define base class - prefer new port, fallback to minimal implementation
if GEOMETRIC_FILTER_PORT_AVAILABLE and GeometricFilterPort is not None:
    GeometricFilterBackend = GeometricFilterPort
    LEGACY_BASE_AVAILABLE = True
else:
    # Fallback: define minimal interface
    LEGACY_BASE_AVAILABLE = False

    class GeometricFilterBackend:
        """Minimal fallback if GeometricFilterPort is unavailable."""

        def __init__(self, task_params: Dict):
            self.task_params = task_params
            self._logger = logger

        def build_expression(self, layer_props, predicates, source_geom=None,
                           buffer_value=None, buffer_expression=None,
                           source_filter=None, use_centroids=False, **kwargs) -> str:
            raise NotImplementedError()

        def apply_filter(self, layer, expression, old_subset=None, combine_operator=None) -> bool:
            raise NotImplementedError()

        def supports_layer(self, layer) -> bool:
            raise NotImplementedError()

        def log_info(self, msg): logger.info(msg)
        def log_warning(self, msg): logger.warning(msg)
        def log_error(self, msg): logger.error(msg)
        def log_debug(self, msg): logger.debug(msg)


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
        self._use_new_backend = False  # Flag to switch to new implementation

        # Try to initialize new backend
        try:
            self._new_backend = self._create_new_backend()
            if self._new_backend:
                self._use_new_backend = self._should_use_new_backend()
                logger.debug(f"{self.provider_type}: New backend available, use_new={self._use_new_backend}")
        except Exception as e:
            logger.debug(f"{self.provider_type}: New backend unavailable: {e}")

        # FIX v4.0.4 (2026-01-16): ALWAYS initialize legacy backend as fallback
        # The _build_expression_new() method delegates to legacy backend for SQL generation
        # so we need it available regardless of _use_new_backend flag
        try:
            self._legacy_backend = self._create_legacy_backend()
            logger.debug(f"{self.provider_type}: Legacy backend initialized as fallback")
        except Exception as e:
            logger.warning(f"{self.provider_type}: Legacy backend unavailable: {e}")

    @property
    @abstractmethod
    def provider_type(self) -> str:
        """Return provider type string ('postgresql', 'spatialite', 'ogr')."""

    @abstractmethod
    def _create_new_backend(self):
        """Create new BackendPort implementation."""

    @abstractmethod
    def _create_legacy_backend(self) -> GeometricFilterBackend:
        """Create legacy GeometricFilterBackend fallback."""

    def _should_use_new_backend(self) -> bool:
        """
        Determine if new backend should be used.

        Override in subclasses for custom logic.
        Default: False (use legacy for stability during migration).
        """
        return False  # Conservative: use legacy by default

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
        Build expression using new backend.

        Translates legacy parameters to new FilterExpression domain model.
        Override in subclasses for backend-specific logic.

        FIX v4.0.3 (2026-01-16): Don't use FilterExpression.from_spatial_filter()
        as it no longer generates SQL (returns empty string). Instead, always
        use the legacy backend's build_expression() method.

        FIX v4.0.4 (2026-01-16): Pass ALL arguments as KEYWORD arguments
        to avoid "got multiple values for argument 'source_wkt'" error.
        The kwargs may contain source_wkt/source_srid/source_feature_count
        which must not conflict with positional arguments.
        """
        # ALWAYS use legacy backend for spatial filter expression building
        # The new FilterExpression domain model is not yet fully integrated
        if self._legacy_backend:
            # FIX v4.0.4: Use keyword arguments to avoid positional conflicts
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

            # v4.1.0: Use safe_set_subset_string from new location
            from ...infrastructure.database.sql_utils import safe_set_subset_string
            return safe_set_subset_string(layer, final_expr)

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
        "(v4)" if self._use_new_backend else "(Legacy)"
        # Return plain provider name for TaskBridge compatibility
        # Display suffix is added only in user messages via infrastructure/feedback
        return self.provider_type.capitalize()


class LegacyPostgreSQLAdapter(BaseLegacyAdapter):
    """
    Legacy adapter for PostgreSQL backend.

    Wraps new PostgreSQLBackend with GeometricFilterBackend interface.
    v4.1.0: Uses PostgreSQLExpressionBuilder instead of before_migration backend.
    """

    @property
    def provider_type(self) -> str:
        return 'postgresql'

    def _create_new_backend(self):
        """Create new PostgreSQL backend."""
        from .postgresql.backend import PostgreSQLBackend
        return PostgreSQLBackend()

    def _create_legacy_backend(self) -> GeometricFilterBackend:
        """Create PostgreSQL expression builder (v4.1.0 - migrated from before_migration)."""
        from .postgresql.expression_builder import PostgreSQLExpressionBuilder
        return PostgreSQLExpressionBuilder(self.task_params)

    def _should_use_new_backend(self) -> bool:
        """Use modern PostgreSQL backend v4.0 (hexagonal architecture)."""
        return True  # v4.0: Modern backend with improved MV management


class LegacySpatialiteAdapter(BaseLegacyAdapter):
    """
    Legacy adapter for Spatialite backend.

    Wraps new SpatialiteBackend with GeometricFilterBackend interface.
    v4.1.0: Uses SpatialiteExpressionBuilder instead of before_migration backend.
    """

    @property
    def provider_type(self) -> str:
        return 'spatialite'

    def _create_new_backend(self):
        """Create new Spatialite backend."""
        from .spatialite.backend import SpatialiteBackend
        return SpatialiteBackend()

    def _create_legacy_backend(self) -> GeometricFilterBackend:
        """Create Spatialite expression builder (v4.1.0 - migrated from before_migration)."""
        from .spatialite.expression_builder import SpatialiteExpressionBuilder
        return SpatialiteExpressionBuilder(self.task_params)

    def _should_use_new_backend(self) -> bool:
        """Use legacy for Spatialite (multi-step optimizer)."""
        return False  # Spatialite legacy has better optimization


class LegacyOGRAdapter(BaseLegacyAdapter):
    """
    Legacy adapter for OGR backend.

    Wraps new OGRBackend with GeometricFilterBackend interface.
    v4.1.0: Uses OGRExpressionBuilder instead of before_migration backend.
    """

    @property
    def provider_type(self) -> str:
        return 'ogr'

    def _create_new_backend(self):
        """Create new OGR backend."""
        from .ogr.backend import OGRBackend
        return OGRBackend()

    def _create_legacy_backend(self) -> GeometricFilterBackend:
        """Create OGR expression builder (v4.1.0 - migrated from before_migration)."""
        from .ogr.expression_builder import OGRExpressionBuilder
        return OGRExpressionBuilder(self.task_params)

    def _should_use_new_backend(self) -> bool:
        """Check feature flag for OGR backend."""
        # v4.1.0: Use feature flag system for progressive migration
        return is_new_backend_enabled('ogr')


class LegacyMemoryAdapter(BaseLegacyAdapter):
    """
    Legacy adapter for Memory backend.

    Wraps new MemoryBackend with GeometricFilterBackend interface.
    v4.1.0: Uses OGRExpressionBuilder as fallback (memory layers use OGR-like filtering).
    """

    @property
    def provider_type(self) -> str:
        return 'memory'

    def _create_new_backend(self):
        """Create new Memory backend."""
        from .memory.backend import MemoryBackend
        return MemoryBackend()

    def _create_legacy_backend(self) -> GeometricFilterBackend:
        """Create Memory expression builder (v4.1.0 - uses OGR builder for memory layers)."""
        from .ogr.expression_builder import OGRExpressionBuilder
        return OGRExpressionBuilder(self.task_params)

    def _should_use_new_backend(self) -> bool:
        """Check feature flag for Memory backend."""
        # v4.1.0: Use feature flag system for progressive migration
        return is_new_backend_enabled('memory')


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
        logger.debug(f"🔧 Created {adapter.get_backend_name()} for provider '{provider_type}'")
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
        ENABLE_NEW_BACKENDS[provider_type.lower()]
        ENABLE_NEW_BACKENDS[provider_type.lower()] = enabled
        logger.debug(f"🔄 Backend {provider_type.upper()}: {'LEGACY → NEW' if enabled else 'NEW → LEGACY'}")
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
    logger.debug("🧪 Experimental backends enabled: OGR, Memory")


def disable_all_new_backends():
    """Disable all new backends, revert to legacy."""
    for provider in ENABLE_NEW_BACKENDS:
        ENABLE_NEW_BACKENDS[provider] = False
    logger.debug("🔙 All new backends disabled, using legacy")

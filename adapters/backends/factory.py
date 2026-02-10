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

from ...core.ports.backend_port import BackendPort
from ...core.domain.filter_expression import ProviderType
from ...core.domain.layer_info import LayerInfo

if TYPE_CHECKING:
    from ...infrastructure.di.container import Container

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
    # MEMORY first (faster for small datasets), then OGR (universal compatibility)
    FALLBACK_PRIORITY = [
        ProviderType.MEMORY,
        ProviderType.OGR,
    ]

    def __init__(
        self,
        postgresql_available: bool = False,
        small_dataset_optimization: bool = False,
        small_dataset_threshold: int = DEFAULT_SMALL_DATASET_THRESHOLD,
        prefer_native_backend: bool = False
    ):
        """
        Initialize backend selector.

        Args:
            postgresql_available: Whether psycopg2 is installed
            small_dataset_optimization: Enable memory optimization for small PG datasets
            small_dataset_threshold: Threshold for small dataset optimization
            prefer_native_backend: If True, always use the native backend (e.g., PostgreSQL)
                                   even for small datasets. Useful when all project layers
                                   are PostgreSQL and we want consistent backend usage.
        """
        self._postgresql_available = postgresql_available
        self._small_dataset_optimization = small_dataset_optimization
        self._small_dataset_threshold = small_dataset_threshold
        self._prefer_native_backend = prefer_native_backend

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

        # Priority 3: PostgreSQL layers - ALWAYS use PostgreSQL backend (v4.0.8)
        # FIX v4.1.4 (2026-01-21): PostgreSQL layers ALWAYS use PostgreSQL backend
        # QGIS native API (setSubsetString) works without psycopg2.
        # psycopg2 is only needed for advanced features (materialized views, connection pooling)
        # but basic filtering always works via QGIS native provider.
        if layer_info.provider_type == ProviderType.POSTGRESQL:
            if not self._postgresql_available:
                logger.info(
                    f"PostgreSQL layer {layer_info.name}: using QGIS native API "
                    "(psycopg2 not available for advanced features)"
                )
            return ProviderType.POSTGRESQL

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
        """Check if memory optimization should be used for PostgreSQL layer.

        Returns False if:
        - small_dataset_optimization is disabled
        - prefer_native_backend is enabled (e.g., all project layers are PostgreSQL)
        - feature_count is unknown
        - feature_count exceeds the threshold
        """
        if not self._small_dataset_optimization:
            return False

        # NEW: Respect prefer_native_backend setting
        # When all project layers are PostgreSQL, we want to use PostgreSQL backend
        # consistently, even for small datasets (avoids backend switching overhead)
        if self._prefer_native_backend:
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

    # Singleton instance for static method compatibility
    _instance = None

    @staticmethod
    def get_backend(provider_type_or_layer_info, layer=None, task_params=None, force_ogr=False):
        """
        Static method for backward compatibility with legacy code.

        Supports both old signature (provider_type, layer, task_params) and
        new signature (layer_info, forced_backend).

        Args (old signature):
            provider_type_or_layer_info: Provider type string ('postgresql', 'spatialite', 'ogr')
            layer: QgsVectorLayer instance
            task_params: Task parameters dictionary
            force_ogr: If True, return OGR backend directly

        Args (new signature):
            provider_type_or_layer_info: LayerInfo instance
            layer: Optional forced_backend string

        Returns:
            Backend instance with apply_filter() and build_expression() methods
        """
        # v4.1.0: Try to use legacy adapters with feature flag for progressive migration
        try:
            from .legacy_adapter import get_legacy_adapter, is_new_backend_enabled
            USE_LEGACY_ADAPTERS = True
        except ImportError:
            USE_LEGACY_ADAPTERS = False

        # v4.1.0: Import expression builders from new locations (no more before_migration!)
        from .ogr.expression_builder import OGRExpressionBuilder
        from .spatialite.expression_builder import SpatialiteExpressionBuilder

        # Detect signature type
        if isinstance(provider_type_or_layer_info, str):
            # OLD SIGNATURE: (provider_type, layer, task_params)
            provider_type = provider_type_or_layer_info

            if force_ogr:
                logger.debug(f"🔄 Force OGR mode: Returning OGR backend for '{layer.name() if layer else 'unknown'}' (bypassing auto-selection)")
                return OGRExpressionBuilder(task_params or {})

            # Check for forced backend in task_params
            forced_backends = (task_params or {}).get('forced_backends', {})
            forced_backend = forced_backends.get(layer.id()) if layer and forced_backends else None

            if forced_backend:
                logger.debug(f"🔒 Using forced backend '{forced_backend.upper()}' for layer '{layer.name() if layer else 'unknown'}'")
                provider_type = forced_backend

            logger.debug(f"🔧 BackendFactory.get_backend() called for '{layer.name() if layer else 'unknown'}'")
            logger.debug(f"   → provider_type (effective): '{provider_type}'")

            # v4.2.0: ALWAYS use LegacyAdapters for hexagonal architecture support
            # The adapters delegate to new ExpressionBuilders (v4.1.0)
            # This enables progressive migration via set_new_backend_enabled()
            if USE_LEGACY_ADAPTERS:
                new_backend_active = is_new_backend_enabled(provider_type)
                logger.debug(f"   → Using LegacyAdapter (hexagonal: {'enabled' if new_backend_active else 'delegating to expression builder'})")
                try:
                    return get_legacy_adapter(provider_type, task_params or {})
                except (ImportError, AttributeError, RuntimeError) as e:
                    logger.warning(f"LegacyAdapter failed: {e}, falling back to direct expression builder")

            # Fallback: Return expression builders directly (v4.1.0)
            if provider_type in ('postgresql', 'postgres'):
                try:
                    from .postgresql.expression_builder import PostgreSQLExpressionBuilder
                    return PostgreSQLExpressionBuilder(task_params or {})
                except ImportError:
                    logger.warning("PostgreSQL backend not available, falling back to OGR")
                    return OGRExpressionBuilder(task_params or {})

            elif provider_type == 'spatialite':
                return SpatialiteExpressionBuilder(task_params or {})

            else:  # 'ogr' or unknown
                return OGRExpressionBuilder(task_params or {})

        else:
            # NEW SIGNATURE: (layer_info, forced_backend)
            # Delegate to instance method via singleton
            if BackendFactory._instance is None:
                BackendFactory._instance = BackendFactory()

            return BackendFactory._instance.get_backend_instance(
                provider_type_or_layer_info,
                forced_backend=layer
            )

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
        self._prefer_native_for_pg_project = False

        # Set singleton instance
        if BackendFactory._instance is None:
            BackendFactory._instance = self

        # Check PostgreSQL availability
        self._postgresql_available = self._check_postgresql_available()

        # Initialize selector with config
        opt_config = self._config.get('small_dataset_optimization', {})
        self._prefer_native_for_pg_project = opt_config.get(
            'prefer_native_for_postgresql_project', True
        )

        # OPTION C (Hybrid): Smart initialization - detect if project is PostgreSQL-only
        # This enables immediate PostgreSQL backend selection without waiting for
        # update_project_context() to be called by filter tasks
        initial_prefer_native = False
        if self._prefer_native_for_pg_project and self._postgresql_available:
            is_pg_only_project = self._detect_project_is_postgresql_only()
            if is_pg_only_project:
                initial_prefer_native = True
                logger.info(
                    "🐘 Smart Init: Detected PostgreSQL-only project - "
                    "forcing PostgreSQL backend for all layers"
                )

        self._selector = BackendSelector(
            postgresql_available=self._postgresql_available,
            small_dataset_optimization=opt_config.get('enabled', False),
            small_dataset_threshold=opt_config.get(
                'threshold',
                DEFAULT_SMALL_DATASET_THRESHOLD
            ),
            # Smart initialization based on project context
            prefer_native_backend=initial_prefer_native
        )

        logger.debug(
            f"BackendFactory initialized: postgresql={self._postgresql_available}, "
            f"prefer_native={initial_prefer_native}"
        )

    def _check_postgresql_available(self) -> bool:
        """Check if PostgreSQL backend with psycopg2 is available."""
        try:
            # CRITICAL: Use PSYCOPG2_AVAILABLE not POSTGRESQL_AVAILABLE!
            # POSTGRESQL_AVAILABLE is always True (QGIS native support)
            # But we need psycopg2 for advanced backend features (MV, pooling)
            from .postgresql_availability import PSYCOPG2_AVAILABLE
            return PSYCOPG2_AVAILABLE
        except ImportError:
            return False

    def update_project_context(self, all_layers_postgresql: bool) -> None:
        """
        Update backend selector based on project context.

        When all project layers are PostgreSQL and prefer_native_for_postgresql_project
        is enabled, this ensures PostgreSQL backend is used even for small datasets
        (avoids switching to MEMORY backend which would be inconsistent).

        This is called dynamically when project layers change (Option C - Hybrid approach).

        Args:
            all_layers_postgresql: True if all vector layers in the project are PostgreSQL
        """
        should_prefer_native = (
            all_layers_postgresql and
            self._prefer_native_for_pg_project and
            self._postgresql_available
        )

        # Log state change
        previous_state = self._selector._prefer_native_backend
        if should_prefer_native != previous_state:
            if should_prefer_native:
                logger.info(
                    "🔄 Dynamic Update: All project layers are PostgreSQL - "
                    "forcing PostgreSQL backend even for small datasets"
                )
            else:
                logger.info(
                    "🔄 Dynamic Update: Project has mixed backends - "
                    "allowing backend optimization"
                )

        # Update selector's prefer_native_backend flag
        self._selector._prefer_native_backend = should_prefer_native

    def is_all_layers_postgresql(self, layers: list) -> bool:
        """
        Check if all provided layers are PostgreSQL.

        Args:
            layers: List of QgsVectorLayer objects

        Returns:
            True if all layers are PostgreSQL provider type
        """
        if not layers:
            return False

        for layer in layers:
            if layer is None:
                continue
            provider_type = layer.providerType() if hasattr(layer, 'providerType') else None
            if provider_type != 'postgres':
                return False

        return True

    def _detect_project_is_postgresql_only(self) -> bool:
        """
        Detect if the current QGIS project contains ONLY PostgreSQL vector layers.

        This is called during BackendFactory initialization to enable smart
        backend selection at startup.

        Returns:
            True if all project vector layers are PostgreSQL, False otherwise
        """
        try:
            from qgis.core import QgsProject

            project = QgsProject.instance()
            if not project:
                return False

            # Get all map layers
            all_layers = project.mapLayers().values()

            # Filter to vector layers only
            vector_layers = [
                layer for layer in all_layers
                if hasattr(layer, 'providerType') and layer.type() == 0  # QgsMapLayer.VectorLayer
            ]

            if not vector_layers:
                return False

            # Check if ALL vector layers are PostgreSQL
            return self.is_all_layers_postgresql(vector_layers)

        except ImportError:
            logger.debug("QgsProject not available during initialization")
            return False
        except (RuntimeError, AttributeError) as e:
            logger.debug(f"Could not detect project layers: {e}")
            return False

    def get_backend_instance(
        self,
        layer_info: LayerInfo,
        forced_backend: Optional[str] = None
    ) -> BackendPort:
        """
        Get appropriate backend for a layer (instance method).

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
                from .memory.backend import MemoryBackend
                return MemoryBackend()

            elif provider_type == ProviderType.OGR:
                from .ogr.backend import OGRBackend
                return OGRBackend()

            elif provider_type == ProviderType.SPATIALITE:
                from .spatialite.backend import SpatialiteBackend
                return SpatialiteBackend()

            elif provider_type == ProviderType.POSTGRESQL:
                if not self._postgresql_available:
                    logger.warning(
                        "PostgreSQL backend requested but psycopg2 not available. "
                        "Install psycopg2 for advanced PostgreSQL features. "
                        "Falling back to OGR backend."
                    )
                    return None
                from .postgresql.backend import PostgreSQLBackend
                return PostgreSQLBackend()

            else:
                logger.warning(f"Unknown provider type: {provider_type}")
                return None

        except ImportError as e:
            logger.warning(f"Failed to import backend for {provider_type}: {e}")
            return None
        except (RuntimeError, AttributeError) as e:
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
            except (RuntimeError, AttributeError) as e:
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

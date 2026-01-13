"""
FilterMate Core Ports Module.

Abstract interfaces (ports) for dependency inversion.
Defines contracts that adapters must implement.

This module follows the Hexagonal Architecture pattern:
- Ports define interfaces that the core depends on
- Adapters implement these interfaces with concrete code
- The core remains decoupled from external dependencies

Ports:
- BackendPort: Interface for filter execution backends
- LayerRepositoryPort: Interface for layer data access
- FavoritesRepositoryPort: Interface for favorites persistence
- ConfigRepositoryPort: Interface for configuration storage
- HistoryRepositoryPort: Interface for history persistence
- CachePort: Interface for caching services
"""
from .backend_port import (
    BackendPort,
    BackendInfo,
    BackendCapability,
)
from .repository_port import (
    RepositoryPort,
    LayerRepositoryPort,
    FavoritesRepositoryPort,
    ConfigRepositoryPort,
    HistoryRepositoryPort,
)
from .cache_port import (
    CachePort,
    CacheStats,
    CacheEntry,
    ResultCachePort,
    GeometryCachePort,
)
from .filter_executor_port import (
    FilterExecutorPort,
    FilterExecutionResult,
    FilterStatus,
    BackendRegistryPort,
    CancellationCallback,
    ProgressCallback,
)

__all__ = [
    # Backend
    'BackendPort',
    'BackendInfo',
    'BackendCapability',
    # Repositories
    'RepositoryPort',
    'LayerRepositoryPort',
    'FavoritesRepositoryPort',
    'ConfigRepositoryPort',
    'HistoryRepositoryPort',
    # Cache
    'CachePort',
    'CacheStats',
    'CacheEntry',
    'ResultCachePort',
    'GeometryCachePort',
    # Filter Executor (v4.0.1)
    'FilterExecutorPort',
    'FilterExecutionResult',
    'FilterStatus',
    'BackendRegistryPort',
    'CancellationCallback',
    'ProgressCallback',
]

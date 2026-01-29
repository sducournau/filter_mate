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

# Geometric Filter Port (v4.1.0 - legacy API compatibility)
from .geometric_filter_port import (
    GeometricFilterPort,
)

# Backend Services Facade (EPIC-1 Phase E13)
from .backend_services import (
    BackendServices,
    get_backend_services,
    get_postgresql_available,
    PostgreSQLAvailability,
)

# Materialized View Port (v4.2 - unified MV/temp table interface)
from .materialized_view_port import (
    MaterializedViewPort,
    ViewType,
    ViewInfo,
    ViewConfig,
)

# Raster Port (EPIC-2 - Raster Integration)
from .raster_port import (
    RasterPort,
    RasterStats,
    BandStatistics,
    HistogramData,
    PixelIdentifyResult,
    TransparencySettings,
    RasterDataType,
    RasterRendererType,
    HistogramBinMethod,
)

# Raster Filter Port (EPIC-3 - Raster-Vector Integration)
from .raster_filter_port import (
    RasterFilterPort,
    RasterValuePredicate,
    SamplingMethod,
    RasterOperation,
    RasterSampleResult,
    RasterFilterResult,
    RasterMaskResult,
    ZonalStatisticsResult,
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
    # Geometric Filter (v4.1.0 - legacy API)
    'GeometricFilterPort',
    # Backend Services Facade (EPIC-1 E13)
    'BackendServices',
    'get_backend_services',
    'get_postgresql_available',
    'PostgreSQLAvailability',
    # Materialized View Port (v4.2)
    'MaterializedViewPort',
    'ViewType',
    'ViewInfo',
    'ViewConfig',
    # Raster Port (EPIC-2)
    'RasterPort',
    'RasterStats',
    'BandStatistics',
    'HistogramData',
    'PixelIdentifyResult',
    'TransparencySettings',
    'RasterDataType',
    'RasterRendererType',
    'HistogramBinMethod',
    # Raster Filter Port (EPIC-3)
    'RasterFilterPort',
    'RasterValuePredicate',
    'SamplingMethod',
    'RasterOperation',
    'RasterSampleResult',
    'RasterFilterResult',
    'RasterMaskResult',
    'ZonalStatisticsResult',
]

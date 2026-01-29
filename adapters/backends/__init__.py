"""
FilterMate Backend Adapters.

Multi-backend support for different data providers.
Part of the Hexagonal Architecture refactoring.

v4.1.0: Added legacy adapters for progressive migration.
EPIC-2: Added QGIS raster backend for raster integration.
EPIC-3: Added QGIS raster filter backend for raster-vector filtering.
"""

from .factory import BackendFactory, BackendSelector, create_backend_factory

# Re-export POSTGRESQL_AVAILABLE for compatibility
try:
    from .postgresql_availability import POSTGRESQL_AVAILABLE
except ImportError:
    # Default to True (QGIS native PostgreSQL always available)
    POSTGRESQL_AVAILABLE = True

# EPIC-2: QGIS Raster Backend
try:
    from .qgis_raster_backend import (
        QGISRasterBackend,
        get_qgis_raster_backend,
    )
    QGIS_RASTER_BACKEND_AVAILABLE = True
except ImportError:
    QGISRasterBackend = None
    get_qgis_raster_backend = None
    QGIS_RASTER_BACKEND_AVAILABLE = False

# EPIC-3: QGIS Raster Filter Backend (Raster-Vector integration)
try:
    from .qgis_raster_filter_backend import QGISRasterFilterBackend
    QGIS_RASTER_FILTER_BACKEND_AVAILABLE = True
except ImportError:
    QGISRasterFilterBackend = None
    QGIS_RASTER_FILTER_BACKEND_AVAILABLE = False

# v4.1.0: Legacy adapters for progressive migration
try:
    from .legacy_adapter import (
        get_legacy_adapter,
        LegacyPostgreSQLAdapter,
        LegacySpatialiteAdapter,
        LegacyOGRAdapter,
        LegacyMemoryAdapter,
        set_new_backend_enabled,
        is_new_backend_enabled,
        ENABLE_NEW_BACKENDS,
    )
    LEGACY_ADAPTERS_AVAILABLE = True
except ImportError:
    LEGACY_ADAPTERS_AVAILABLE = False
    get_legacy_adapter = None
    LegacyPostgreSQLAdapter = None
    LegacySpatialiteAdapter = None
    LegacyOGRAdapter = None
    LegacyMemoryAdapter = None
    set_new_backend_enabled = None
    is_new_backend_enabled = None
    ENABLE_NEW_BACKENDS = {}

__all__ = [
    'BackendFactory',
    'BackendSelector', 
    'create_backend_factory',
    'POSTGRESQL_AVAILABLE',
    # EPIC-2: Raster backend
    'QGISRasterBackend',
    'get_qgis_raster_backend',
    'QGIS_RASTER_BACKEND_AVAILABLE',
    # EPIC-3: Raster filter backend
    'QGISRasterFilterBackend',
    'QGIS_RASTER_FILTER_BACKEND_AVAILABLE',
    # v4.1.0: Legacy adapters
    'get_legacy_adapter',
    'LegacyPostgreSQLAdapter',
    'LegacySpatialiteAdapter',
    'LegacyOGRAdapter',
    'LegacyMemoryAdapter',
    'set_new_backend_enabled',
    'is_new_backend_enabled',
    'ENABLE_NEW_BACKENDS',
    'LEGACY_ADAPTERS_AVAILABLE',
]
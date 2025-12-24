# -*- coding: utf-8 -*-
"""
FilterMate Backend Architecture

This package contains the backend implementations for different data providers:
- PostgreSQL (optimized for performance with large datasets)
- Spatialite (good performance for small to medium datasets)
- OGR (fallback for various file formats)

Each backend implements the GeometricFilterBackend interface.

v2.4.0 Optimization Modules:
- MVRegistry: Automatic cleanup of PostgreSQL materialized views
- WKTCache: LRU cache for WKT geometries in Spatialite
- SpatialIndexManager: Automatic spatial index creation for OGR layers
"""

from .base_backend import GeometricFilterBackend
from .postgresql_backend import PostgreSQLGeometricFilter
from .spatialite_backend import SpatialiteGeometricFilter
from .ogr_backend import OGRGeometricFilter
from .factory import BackendFactory

# v2.4.0 Optimization modules
try:
    from .mv_registry import MVRegistry, get_mv_registry
except ImportError:
    MVRegistry = None
    get_mv_registry = None

try:
    from .wkt_cache import WKTCache, get_wkt_cache
except ImportError:
    WKTCache = None
    get_wkt_cache = None

try:
    from .spatial_index_manager import SpatialIndexManager, get_spatial_index_manager
except ImportError:
    SpatialIndexManager = None
    get_spatial_index_manager = None

__all__ = [
    # Core backends
    'GeometricFilterBackend',
    'PostgreSQLGeometricFilter',
    'SpatialiteGeometricFilter',
    'OGRGeometricFilter',
    'BackendFactory',
    # v2.4.0 Optimization modules
    'MVRegistry',
    'get_mv_registry',
    'WKTCache',
    'get_wkt_cache',
    'SpatialIndexManager',
    'get_spatial_index_manager',
]

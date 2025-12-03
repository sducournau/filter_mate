# -*- coding: utf-8 -*-
"""
FilterMate Backend Architecture

This package contains the backend implementations for different data providers:
- PostgreSQL (optimized for performance with large datasets)
- Spatialite (good performance for small to medium datasets)
- OGR (fallback for various file formats)

Each backend implements the GeometricFilterBackend interface.
"""

from .base_backend import GeometricFilterBackend
from .postgresql_backend import PostgreSQLGeometricFilter
from .spatialite_backend import SpatialiteGeometricFilter
from .ogr_backend import OGRGeometricFilter
from .factory import BackendFactory

__all__ = [
    'GeometricFilterBackend',
    'PostgreSQLGeometricFilter',
    'SpatialiteGeometricFilter',
    'OGRGeometricFilter',
    'BackendFactory'
]

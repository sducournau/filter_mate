# -*- coding: utf-8 -*-
"""
Backend Handlers Package

Phase 4 (v6.0): Extracted from FilterEngineTask to reduce God class.
Each handler encapsulates backend-specific logic (PostgreSQL, Spatialite, OGR).
"""

from .postgresql_handler import PostgreSQLHandler
from .spatialite_handler import SpatialiteHandler
from .ogr_handler import OGRHandler

__all__ = ['PostgreSQLHandler', 'SpatialiteHandler', 'OGRHandler']

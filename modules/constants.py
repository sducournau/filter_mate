# -*- coding: utf-8 -*-
"""
DEPRECATED: Legacy compatibility shim for modules/constants

Migrated to core/domain/constants.py
This file provides backward compatibility only.
"""
import warnings

warnings.warn(
    "modules.constants is deprecated. Use core.domain.constants instead.",
    DeprecationWarning,
    stacklevel=2
)

# Constants (basic values for compatibility)
PROVIDER_POSTGRES = 'postgres'
PROVIDER_SPATIALITE = 'spatialite'
PROVIDER_OGR = 'ogr'
PROVIDER_MEMORY = 'memory'

def get_geometry_type_string(geom_type):
    """Get geometry type as string."""
    geom_types = {
        0: 'Point',
        1: 'LineString',
        2: 'Polygon',
        3: 'MultiPoint',
        4: 'MultiLineString',
        5: 'MultiPolygon',
    }
    return geom_types.get(geom_type, 'Unknown')

__all__ = [
    'PROVIDER_POSTGRES',
    'PROVIDER_SPATIALITE', 
    'PROVIDER_OGR',
    'PROVIDER_MEMORY',
    'get_geometry_type_string',
]

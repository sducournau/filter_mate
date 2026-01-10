# -*- coding: utf-8 -*-
"""
FilterMate Constants Module

Provides global constants used throughout FilterMate.
Includes provider types, spatial predicates, and performance thresholds.

This file provides backward compatibility for modules.constants imports.
"""
import warnings

# Deprecation warning for tracking usage
warnings.warn(
    "modules.constants: Consider using specific imports from infrastructure/adapters.",
    DeprecationWarning,
    stacklevel=2
)

# =============================================================================
# Provider Types
# =============================================================================
PROVIDER_POSTGRES = 'postgres'
PROVIDER_SPATIALITE = 'spatialite'
PROVIDER_OGR = 'ogr'
PROVIDER_MEMORY = 'memory'

# =============================================================================
# Spatial Predicates
# =============================================================================
PREDICATE_INTERSECTS = "intersects"
PREDICATE_CONTAINS = "contains"
PREDICATE_WITHIN = "within"
PREDICATE_CROSSES = "crosses"
PREDICATE_TOUCHES = "touches"
PREDICATE_DISJOINT = "disjoint"
PREDICATE_OVERLAPS = "overlaps"
PREDICATE_EQUALS = "equals"

# =============================================================================
# Performance Thresholds
# =============================================================================
LONG_QUERY_WARNING_THRESHOLD = 5.0  # seconds
VERY_LONG_QUERY_WARNING_THRESHOLD = 30.0  # seconds

LARGE_DATASET_THRESHOLD = 50000  # features
VERY_LARGE_DATASET_THRESHOLD = 500000  # features


# =============================================================================
# Utility Functions
# =============================================================================
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


def get_provider_name(provider_type: str) -> str:
    """Get human-readable provider name."""
    provider_names = {
        PROVIDER_POSTGRES: 'PostgreSQL',
        PROVIDER_SPATIALITE: 'SpatiaLite',
        PROVIDER_OGR: 'OGR/File',
        PROVIDER_MEMORY: 'Memory',
    }
    return provider_names.get(provider_type, provider_type)


def should_warn_performance(feature_count: int, provider: str) -> bool:
    """Check if performance warning should be shown."""
    if provider == PROVIDER_POSTGRES:
        return feature_count > VERY_LARGE_DATASET_THRESHOLD
    return feature_count > LARGE_DATASET_THRESHOLD


# =============================================================================
# Exports
# =============================================================================
__all__ = [
    # Provider types
    'PROVIDER_POSTGRES',
    'PROVIDER_SPATIALITE', 
    'PROVIDER_OGR',
    'PROVIDER_MEMORY',
    # Spatial predicates
    'PREDICATE_INTERSECTS',
    'PREDICATE_CONTAINS',
    'PREDICATE_WITHIN',
    'PREDICATE_CROSSES',
    'PREDICATE_TOUCHES',
    'PREDICATE_DISJOINT',
    'PREDICATE_OVERLAPS',
    'PREDICATE_EQUALS',
    # Performance thresholds
    'LONG_QUERY_WARNING_THRESHOLD',
    'VERY_LONG_QUERY_WARNING_THRESHOLD',
    'LARGE_DATASET_THRESHOLD',
    'VERY_LARGE_DATASET_THRESHOLD',
    # Functions
    'get_geometry_type_string',
    'get_provider_name',
    'should_warn_performance',
]

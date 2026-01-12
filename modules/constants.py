# -*- coding: utf-8 -*-
"""
DEPRECATED: Legacy compatibility shim for modules/constants

This module has been migrated to infrastructure/constants.py
This shim provides backward compatibility for imports from modules.constants

Migration:
    OLD: from modules.constants import PROVIDER_POSTGRES
    NEW: from infrastructure.constants import PROVIDER_POSTGRES

Date: January 2026
EPIC: EPIC-1 (Suppression du dossier modules/)
"""
import warnings

warnings.warn(
    "modules.constants is deprecated. Use infrastructure.constants instead. "
    "This shim will be removed in FilterMate v5.0.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from ..infrastructure.constants import (
    # Provider Types
    PROVIDER_POSTGRES,
    PROVIDER_SPATIALITE,
    PROVIDER_OGR,
    PROVIDER_MEMORY,
    # Spatial Predicates
    PREDICATE_INTERSECTS,
    PREDICATE_CONTAINS,
    PREDICATE_WITHIN,
    PREDICATE_CROSSES,
    PREDICATE_TOUCHES,
    PREDICATE_DISJOINT,
    PREDICATE_OVERLAPS,
    PREDICATE_EQUALS,
    # Performance Thresholds
    LONG_QUERY_WARNING_THRESHOLD,
    VERY_LONG_QUERY_WARNING_THRESHOLD,
    LARGE_DATASET_THRESHOLD,
    VERY_LARGE_DATASET_THRESHOLD,
    # Utility Functions
    get_geometry_type_string,
    get_provider_name,
    should_warn_performance,
)

__all__ = [
    # Provider Types
    'PROVIDER_POSTGRES',
    'PROVIDER_SPATIALITE',
    'PROVIDER_OGR',
    'PROVIDER_MEMORY',
    # Spatial Predicates
    'PREDICATE_INTERSECTS',
    'PREDICATE_CONTAINS',
    'PREDICATE_WITHIN',
    'PREDICATE_CROSSES',
    'PREDICATE_TOUCHES',
    'PREDICATE_DISJOINT',
    'PREDICATE_OVERLAPS',
    'PREDICATE_EQUALS',
    # Performance Thresholds
    'LONG_QUERY_WARNING_THRESHOLD',
    'VERY_LONG_QUERY_WARNING_THRESHOLD',
    'LARGE_DATASET_THRESHOLD',
    'VERY_LARGE_DATASET_THRESHOLD',
    # Utility Functions
    'get_geometry_type_string',
    'get_provider_name',
    'should_warn_performance',
]

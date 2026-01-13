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
v4.0 Fix: Restored full re-exports for backward compatibility
"""
import warnings

warnings.warn(
    "modules.constants is deprecated. Use infrastructure.constants instead. "
    "This shim will be removed in FilterMate v5.0.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export ALL from new location (v4.0 Regression Fix)
from ..infrastructure.constants import *

# Explicit exports for IDE support
from ..infrastructure.constants import (
    # Provider Types
    PROVIDER_POSTGRES,
    PROVIDER_SPATIALITE,
    PROVIDER_OGR,
    PROVIDER_MEMORY,
    PROVIDER_VIRTUAL,
    PROVIDER_WFS,
    PROVIDER_ARCGIS,
    PROVIDER_DELIMITEDTEXT,
    PROVIDER_GPKG,
    PROVIDER_MSSQL,
    PROVIDER_HANA,
    PROVIDER_ORACLE,
    REMOTE_PROVIDERS,
    PROVIDER_TYPE_MAPPING,
    # Spatial Predicates
    PREDICATE_INTERSECTS,
    PREDICATE_CONTAINS,
    PREDICATE_WITHIN,
    PREDICATE_CROSSES,
    PREDICATE_TOUCHES,
    PREDICATE_DISJOINT,
    PREDICATE_OVERLAPS,
    PREDICATE_EQUALS,
    ALL_PREDICATES,
    PREDICATE_SQL_MAPPING,
    # Task types
    TASK_FILTER,
    TASK_UNFILTER,
    TASK_RESET,
    TASK_EXPORT,
    TASK_ADD_LAYERS,
    TASK_REMOVE_LAYERS,
    # Buffer types
    BUFFER_TYPE_FIXED,
    BUFFER_TYPE_EXPRESSION,
    BUFFER_TYPE_NONE,
    # Combine operators
    COMBINE_AND,
    COMBINE_OR,
    # Performance Thresholds
    PERFORMANCE_THRESHOLD_SMALL,
    PERFORMANCE_THRESHOLD_MEDIUM,
    PERFORMANCE_THRESHOLD_LARGE,
    PERFORMANCE_THRESHOLD_XLARGE,
    LONG_QUERY_WARNING_THRESHOLD,
    VERY_LONG_QUERY_WARNING_THRESHOLD,
    LARGE_DATASET_THRESHOLD,
    VERY_LARGE_DATASET_THRESHOLD,
    SMALL_DATASET_THRESHOLD,
    DEFAULT_SMALL_DATASET_OPTIMIZATION,
    # Backend optimization
    MV_MAX_AGE_SECONDS,
    MV_CLEANUP_INTERVAL,
    MV_PREFIX,
    CENTROID_MODE_DEFAULT,
    CENTROID_MODE_OPTIONS,
    # SQLite/Spatialite
    SQLITE_MAX_RETRIES,
    SQLITE_BASE_DELAY,
    SQLITE_MAX_DELAY,
    SQLITE_JITTER_FACTOR,
    SQLITE_TIMEOUT,
    # Geometry types
    GEOMETRY_TYPE_POINT,
    GEOMETRY_TYPE_LINE,
    GEOMETRY_TYPE_POLYGON,
    GEOMETRY_TYPE_UNKNOWN,
    GEOMETRY_TYPE_NULL,
    GEOMETRY_TYPE_STRINGS,
    GEOMETRY_TYPE_LEGACY_STRINGS,
    # Utility Functions
    get_geometry_type_string,
    get_provider_name,
    get_provider_display_name,
    get_sql_predicate,
    should_warn_performance,
)

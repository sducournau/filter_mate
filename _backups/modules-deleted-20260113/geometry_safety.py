# -*- coding: utf-8 -*-
"""
DEPRECATED: Legacy compatibility shim for modules/geometry_safety

This module has been migrated to core/geometry/geometry_safety.py
This shim provides backward compatibility for imports from modules.geometry_safety

Migration:
    OLD: from modules.geometry_safety import validate_geometry
    NEW: from core.geometry import validate_geometry

Date: January 2026
EPIC: EPIC-1 (Suppression du dossier modules/)
"""
import warnings

warnings.warn(
    "modules.geometry_safety is deprecated. Use core.geometry instead. "
    "This shim will be removed in FilterMate v4.0.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from ..core.geometry.geometry_safety import (
    # Validation
    validate_geometry,
    validate_geometry_for_geos,
    get_geometry_type_name,
    # Conversion
    safe_as_polygon,
    safe_as_geometry_collection,
    safe_convert_to_multi_polygon,
    extract_polygons_from_collection,
    # Operations
    safe_buffer,
    safe_buffer_metric,
    safe_buffer_with_crs_check,
    safe_unary_union,
    safe_collect_geometry,
    repair_geometry,
    create_geos_safe_layer,
)

__all__ = [
    'validate_geometry',
    'validate_geometry_for_geos',
    'get_geometry_type_name',
    'safe_as_polygon',
    'safe_as_geometry_collection',
    'safe_convert_to_multi_polygon',
    'extract_polygons_from_collection',
    'safe_buffer',
    'safe_buffer_metric',
    'safe_buffer_with_crs_check',
    'safe_unary_union',
    'safe_collect_geometry',
    'repair_geometry',
    'create_geos_safe_layer',
]

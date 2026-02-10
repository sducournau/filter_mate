"""
Geometry Operations Module

EPIC-1 Phase E2: Extracted from filter_task.py god class.
EPIC-1 Phase E7.5: Added simplify_buffer_result.
EPIC-1 Phase E13: Added geometry_safety module.

This module provides geometry processing functionality:
- Buffer operations (positive/negative)
- Geometry repair and validation
- Geometry type conversions
- Geometry simplification
- GEOS-safe operations

Used by FilterEngineTask for spatial operations.
"""

# Buffer operations
from .buffer_processor import (  # noqa: F401
    apply_qgis_buffer,
    create_buffered_memory_layer,
    simplify_buffer_result,
    BufferConfig
)

# Geometry repair
from .geometry_repair import (  # noqa: F401
    aggressive_geometry_repair,
    repair_invalid_geometries
)

# Geometry converters
from .geometry_converter import (  # noqa: F401
    convert_geometry_collection_to_multipolygon
)

# Geometry safety (GEOS-safe operations)
from .geometry_safety import (  # noqa: F401
    validate_geometry,
    validate_geometry_for_geos,
    get_geometry_type_name,
    safe_as_polygon,
    safe_as_geometry_collection,
    safe_convert_to_multi_polygon,
    extract_polygons_from_collection,
    safe_buffer,
    safe_buffer_metric,
    safe_buffer_with_crs_check,
    safe_unary_union,
    safe_collect_geometry,
    repair_geometry,
    create_geos_safe_layer,
)

__all__ = [
    # Buffer
    'apply_qgis_buffer',
    'create_buffered_memory_layer',
    'simplify_buffer_result',
    'BufferConfig',

    # Repair
    'aggressive_geometry_repair',
    'repair_invalid_geometries',

    # Convert
    'convert_geometry_collection_to_multipolygon',

    # Safety
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

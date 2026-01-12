"""
Geometry Operations Module

EPIC-1 Phase E2: Extracted from filter_task.py god class.
EPIC-1 Phase E7.5: Added simplify_buffer_result.

This module provides geometry processing functionality:
- Buffer operations (positive/negative)
- Geometry repair and validation  
- Geometry type conversions
- Geometry simplification

Used by FilterEngineTask for spatial operations.
"""

# Buffer operations
from .buffer_processor import (
    apply_qgis_buffer,
    create_buffered_memory_layer,
    simplify_buffer_result,
    BufferConfig
)

# Geometry repair
from .geometry_repair import (
    aggressive_geometry_repair,
    repair_invalid_geometries
)

# Geometry converters
from .geometry_converter import (
    convert_geometry_collection_to_multipolygon
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
]

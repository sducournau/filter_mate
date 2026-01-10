"""
Geometry Operations Module

EPIC-1 Phase E2: Extracted from filter_task.py god class.

This module provides geometry processing functionality:
- Buffer operations (positive/negative)
- Geometry repair and validation  
- Geometry type conversions
- Geometry simplification

Used by FilterEngineTask for spatial operations.
"""

# Buffer operations
from core.geometry.buffer_processor import (
    apply_qgis_buffer,
    create_buffered_memory_layer,
    BufferConfig
)

# Geometry repair
from core.geometry.geometry_repair import (
    aggressive_geometry_repair,
    repair_invalid_geometries
)

# Geometry converters
from core.geometry.geometry_converter import (
    convert_geometry_collection_to_multipolygon
)

__all__ = [
    # Buffer
    'apply_qgis_buffer',
    'create_buffered_memory_layer',
    'BufferConfig',
    
    # Repair
    'aggressive_geometry_repair',
    'repair_invalid_geometries',
    
    # Convert
    'convert_geometry_collection_to_multipolygon',
]

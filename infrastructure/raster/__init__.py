"""
FilterMate Raster Infrastructure.

Low-level raster operations: sampling, zonal stats, histogram, masking, export.
Each sub-module wraps QGIS/GDAL APIs with thread-safety and CRS handling.

Phase 1: sampling.py (point-based raster value extraction)
Phase 2+: histogram.py, zonal_stats.py, masking.py, export.py
"""
from .sampling import (  # noqa: F401
    sample_raster_at_point,
    sample_raster_for_features,
    get_raster_info,
)

__all__ = [
    'sample_raster_at_point',
    'sample_raster_for_features',
    'get_raster_info',
]

"""
FilterMate Raster Infrastructure.

Low-level raster operations: sampling, zonal stats, histogram, masking, export.
Each sub-module wraps QGIS/GDAL APIs with thread-safety and CRS handling.

Phase 1: sampling.py (point-based raster value extraction)
Phase 2: histogram.py (band histogram + statistics), band_utils.py (band info + compositions)
Phase 3+: zonal_stats.py, masking.py, export.py
"""
from .sampling import (  # noqa: F401
    sample_raster_at_point,
    sample_raster_for_features,
    get_raster_info,
)
from .histogram import (  # noqa: F401
    compute_band_histogram,
    compute_band_statistics,
    VALID_BIN_COUNTS,
)
from .band_utils import (  # noqa: F401
    get_band_info,
    apply_band_composition,
    apply_single_band,
    apply_preset_composition,
    get_preset_names,
    get_preset_label,
    PRESET_COMPOSITIONS,
)

__all__ = [
    # Phase 1: Sampling
    'sample_raster_at_point',
    'sample_raster_for_features',
    'get_raster_info',
    # Phase 2: Histogram
    'compute_band_histogram',
    'compute_band_statistics',
    'VALID_BIN_COUNTS',
    # Phase 2: Band Utils
    'get_band_info',
    'apply_band_composition',
    'apply_single_band',
    'apply_preset_composition',
    'get_preset_names',
    'get_preset_label',
    'PRESET_COMPOSITIONS',
]

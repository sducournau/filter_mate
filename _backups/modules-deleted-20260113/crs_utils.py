# -*- coding: utf-8 -*-
"""
DEPRECATED: Legacy compatibility shim for modules/crs_utils

This module has been migrated to core/geometry/crs_utils.py
This shim provides backward compatibility for imports from modules.crs_utils

Migration:
    OLD: from modules.crs_utils import is_geographic_crs
    NEW: from core.geometry.crs_utils import is_geographic_crs

Date: January 2026
EPIC: EPIC-1 (Suppression du dossier modules/)
"""
import warnings

warnings.warn(
    "modules.crs_utils is deprecated. Use core.geometry.crs_utils instead. "
    "This shim will be removed in FilterMate v4.0.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from ..core.geometry.crs_utils import (
    DEFAULT_METRIC_CRS,
    is_geographic_crs,
    is_metric_crs,
    get_crs_units,
    get_optimal_metric_crs,
    get_layer_crs_info,
    CRSTransformer,
    create_metric_buffer,
)

__all__ = [
    'DEFAULT_METRIC_CRS',
    'is_geographic_crs',
    'is_metric_crs',
    'get_crs_units',
    'get_optimal_metric_crs',
    'get_layer_crs_info',
    'CRSTransformer',
    'create_metric_buffer',
]

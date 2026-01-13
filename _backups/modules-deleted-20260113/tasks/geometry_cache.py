# -*- coding: utf-8 -*-
"""
Source Geometry Cache - LEGACY SHIM

⚠️ DEPRECATED: This module has been migrated to infrastructure/cache/geometry_cache.py (EPIC-1)

MIGRATION GUIDE:
- OLD: from modules.tasks.geometry_cache import SourceGeometryCache
- NEW: from infrastructure.cache import SourceGeometryCache

All functionality is now available from:
    from infrastructure.cache import SourceGeometryCache

This shim provides backward compatibility but will be removed in v3.1.
"""

import warnings

warnings.warn(
    "modules.tasks.geometry_cache is deprecated. "
    "Use 'from infrastructure.cache import SourceGeometryCache' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from infrastructure
from ...infrastructure.cache import SourceGeometryCache

__all__ = ['SourceGeometryCache']

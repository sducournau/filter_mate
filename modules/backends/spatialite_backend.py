# -*- coding: utf-8 -*-
"""
FilterMate Modules Spatialite Backend - Compatibility Shim

Re-exports SpatialiteBackend as SpatialiteGeometricFilter for backward compatibility.

Usage:
    from modules.backends.spatialite_backend import SpatialiteGeometricFilter
"""

import warnings
import logging

warnings.warn(
    "modules.backends.spatialite_backend: Importing from modules.backends is deprecated. "
    "Use 'from adapters.backends.spatialite import SpatialiteBackend' instead.",
    DeprecationWarning,
    stacklevel=2
)

logger = logging.getLogger(__name__)

# Re-export from adapters.backends.spatialite
try:
    from ...adapters.backends.spatialite import (
        SpatialiteBackend,
        spatialite_connect,
        SpatialiteCache,
        RTreeIndexManager,
        create_spatialite_backend,
    )
    
    # Alias for backward compatibility
    SpatialiteGeometricFilter = SpatialiteBackend
    
except ImportError as e:
    logger.warning(f"Failed to import from adapters.backends.spatialite: {e}")
    
    # Provide a stub class for compatibility
    class SpatialiteGeometricFilter:
        """Stub class when adapters.backends.spatialite is not available."""
        
        _support_cache = {}
        
        def __init__(self, task_params=None):
            self.task_params = task_params or {}
            logger.warning("SpatialiteGeometricFilter stub - backend not available")
        
        @classmethod
        def clear_support_cache(cls):
            """Clear support detection cache."""
            cls._support_cache.clear()
        
        def execute(self, *args, **kwargs):
            """Execute stub - returns empty result."""
            return {'success': False, 'error': 'Backend not available'}
    
    SpatialiteBackend = SpatialiteGeometricFilter
    spatialite_connect = None
    SpatialiteCache = None
    RTreeIndexManager = None
    create_spatialite_backend = None


__all__ = [
    'SpatialiteGeometricFilter',  # Legacy name
    'SpatialiteBackend',
    'spatialite_connect',
    'SpatialiteCache',
    'RTreeIndexManager',
    'create_spatialite_backend',
]

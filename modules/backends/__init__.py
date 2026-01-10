# -*- coding: utf-8 -*-
"""
FilterMate Modules Backends Package - Compatibility Shim

Re-exports backend classes from adapters.backends for backward compatibility.

Usage:
    from modules.backends import BackendFactory
    from modules.backends.spatialite_backend import SpatialiteGeometricFilter
"""

import warnings

warnings.warn(
    "modules.backends: Importing from modules.backends is deprecated. "
    "Use 'from adapters.backends import ...' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from adapters.backends
try:
    from adapters.backends import (
        BackendFactory,
        BackendSelector,
        create_backend_factory,
        POSTGRESQL_AVAILABLE,
    )
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Failed to import from adapters.backends: {e}")
    
    BackendFactory = None
    BackendSelector = None
    create_backend_factory = None
    POSTGRESQL_AVAILABLE = True


__all__ = [
    'BackendFactory',
    'BackendSelector',
    'create_backend_factory',
    'POSTGRESQL_AVAILABLE',
]

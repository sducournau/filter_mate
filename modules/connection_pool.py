# -*- coding: utf-8 -*-
"""
Shim module for connection pool.

DEPRECATED: This module is a compatibility shim.
Use infrastructure.database.connection_pool instead.

Migration: EPIC-1 Phase E6 - Strangler Fig Pattern
"""
import warnings
import logging

logger = logging.getLogger(__name__)

# Emit deprecation warning
warnings.warn(
    "modules.connection_pool is deprecated. "
    "Use infrastructure.database.connection_pool instead.",
    DeprecationWarning,
    stacklevel=2
)

logger.info(
    "SHIM: modules.connection_pool redirecting to infrastructure.database.connection_pool"
)

# Re-export from new location
try:
    from infrastructure.database.connection_pool import (
        cleanup_pools,
        get_pool,
        register_pool,
        unregister_pool,
    )
except ImportError:
    try:
        from ..infrastructure.database.connection_pool import (
            cleanup_pools,
            get_pool,
            register_pool,
            unregister_pool,
        )
    except ImportError as e:
        logger.warning(f"Could not import connection_pool: {e}")
        cleanup_pools = lambda: None
        get_pool = lambda name: None
        register_pool = lambda name, pool: None
        unregister_pool = lambda name: None

__all__ = [
    'cleanup_pools',
    'get_pool',
    'register_pool',
    'unregister_pool',
]

# -*- coding: utf-8 -*-
"""
Shim module for configuration migration.

DEPRECATED: This module is a compatibility shim.
Use infrastructure.config.config_migration instead.

Migration: EPIC-1 Phase E6 - Strangler Fig Pattern
"""
import warnings
import logging

logger = logging.getLogger(__name__)

# Emit deprecation warning
warnings.warn(
    "modules.config_migration is deprecated. "
    "Use infrastructure.config.config_migration instead.",
    DeprecationWarning,
    stacklevel=2
)

logger.info(
    "SHIM: modules.config_migration redirecting to infrastructure.config.config_migration"
)

# Re-export from new location
try:
    from infrastructure.config.config_migration import ConfigMigration
except ImportError:
    try:
        from ..infrastructure.config.config_migration import ConfigMigration
    except ImportError as e:
        logger.warning(f"Could not import ConfigMigration: {e}")
        ConfigMigration = None

__all__ = ['ConfigMigration']

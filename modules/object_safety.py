# -*- coding: utf-8 -*-
"""
DEPRECATED: Legacy compatibility shim for modules/object_safety

Migrated to infrastructure/utils/safety.py
This file provides backward compatibility only.

Migration: from infrastructure.utils.safety import is_valid_layer
"""
import warnings

warnings.warn(
    "modules.object_safety is deprecated. Use infrastructure.utils.safety instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from modules (still exists temporarily)
try:
    from ..infrastructure.utils import is_valid_layer
except ImportError:
    # Fallback if not yet in infrastructure
    def is_valid_layer(layer):
        """Basic fallback implementation."""
        try:
            return layer is not None and not layer.isNull()
        except:
            return False

__all__ = ['is_valid_layer']

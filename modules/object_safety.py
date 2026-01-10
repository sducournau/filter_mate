# -*- coding: utf-8 -*-
"""
DEPRECATED: Legacy compatibility shim for modules/object_safety

Migrated to infrastructure/utils/validation_utils.py (EPIC-1)
This file provides backward compatibility only.

Migration Guide:
    OLD: from modules.object_safety import is_valid_layer, is_sip_deleted
    NEW: from infrastructure.utils import is_layer_valid, is_sip_deleted
"""
import warnings

warnings.warn(
    "modules.object_safety is deprecated. Use infrastructure.utils instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
try:
    from ..infrastructure.utils import (
        is_sip_deleted,
        is_layer_valid as is_valid_layer,  # Alias for backward compatibility
        is_layer_source_available,
        safe_layer_access,
    )
except ImportError:
    # Fallback if infrastructure not available
    def is_sip_deleted(obj):
        """Basic fallback."""
        return obj is None
    
    def is_valid_layer(layer):
        """Basic fallback implementation."""
        try:
            return layer is not None and not layer.isNull() and layer.isValid()
        except:
            return False
    
    def is_layer_source_available(layer):
        """Basic fallback."""
        return is_valid_layer(layer)
    
    def safe_layer_access(layer):
        """Basic fallback - no context manager."""
        class DummyContext:
            def __enter__(self):
                return layer
            def __exit__(self, *args):
                pass
        return DummyContext()

__all__ = [
    'is_sip_deleted',
    'is_valid_layer',
    'is_layer_source_available',
    'safe_layer_access',
]

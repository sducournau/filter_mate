# -*- coding: utf-8 -*-
"""
DEPRECATED: Legacy compatibility shim for modules/appUtils

Migrated to adapters/database_manager.py and infrastructure/utils/
This file provides backward compatibility only.
"""
import warnings

warnings.warn(
    "modules.appUtils is deprecated. Use adapters.database_manager or infrastructure.utils instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new locations
try:
    from ..adapters.database_manager import get_datasource_connexion_from_layer
    from ..infrastructure.utils import get_best_display_field, is_layer_source_available
except ImportError:
    # Basic fallbacks
    def get_best_display_field(layer):
        """Fallback implementation."""
        fields = layer.fields()
        if fields:
            return fields[0].name()
        return None
    
    def is_layer_source_available(layer):
        """Fallback implementation."""
        try:
            return layer is not None and layer.isValid()
        except:
            return False

__all__ = [
    'get_best_display_field',
    'is_layer_source_available',
]

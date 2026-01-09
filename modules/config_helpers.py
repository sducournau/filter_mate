# -*- coding: utf-8 -*-
"""
DEPRECATED: Legacy compatibility shim for modules/config_helpers

Migrated to config/config.py
This file provides backward compatibility only.
"""
import warnings

warnings.warn(
    "modules.config_helpers is deprecated. Use config.config instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
try:
    from ..config.config import ENV_VARS
    
    def set_config_value(config_data, *keys, value):
        """Set config value (basic implementation)."""
        current = config_data
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value
    
    def get_optimization_thresholds(config_data):
        """Get optimization thresholds."""
        return config_data.get('optimization', {}).get('thresholds', {})
        
except ImportError:
    def set_config_value(*args, **kwargs):
        pass
    
    def get_optimization_thresholds(config_data):
        return {}

__all__ = [
    'set_config_value',
    'get_optimization_thresholds',
]

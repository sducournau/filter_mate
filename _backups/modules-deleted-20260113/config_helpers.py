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
    
    def get_config_value(config_data, *keys):
        """Get config value by nested keys."""
        current = config_data
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return None
            current = current[key]
        return current
    
    def get_optimization_thresholds(config_data):
        """Get optimization thresholds."""
        return config_data.get('optimization', {}).get('thresholds', {})
    
    def get_active_theme(config_data):
        """Get active theme from config."""
        # Try new structure
        theme = get_config_value(config_data, "app", "active_theme")
        if theme:
            return theme
        # Try old structure
        theme = get_config_value(config_data, "APP", "DOCKWIDGET", "COLORS", "ACTIVE_THEME")
        return theme or "default"
    
    def get_theme_colors(config_data, theme_name):
        """Get colors for a specific theme."""
        # Try new structure
        themes = get_config_value(config_data, "app", "themes")
        if themes and theme_name in themes:
            return themes[theme_name]
        # Try old structure
        themes = get_config_value(config_data, "APP", "DOCKWIDGET", "COLORS", "THEMES")
        if themes and theme_name in themes:
            return themes[theme_name]
        return {}
    
    def get_background_colors(config_data):
        """Get background colors from config."""
        active_theme = get_active_theme(config_data)
        colors = get_theme_colors(config_data, active_theme)
        return colors.get("background", {"primary": "#ffffff", "secondary": "#f5f5f5"})
    
    def get_font_colors(config_data):
        """Get font colors from config."""
        active_theme = get_active_theme(config_data)
        colors = get_theme_colors(config_data, active_theme)
        return colors.get("font", {"primary": "#000000", "secondary": "#666666"})
    
    def get_accent_colors(config_data):
        """Get accent colors from config."""
        active_theme = get_active_theme(config_data)
        colors = get_theme_colors(config_data, active_theme)
        return colors.get("accent", {"primary": "#0078d7", "secondary": "#005a9e"})
        
except ImportError:
    def set_config_value(*args, **kwargs):
        pass
    
    def get_config_value(*args, **kwargs):
        return None
    
    def get_optimization_thresholds(config_data):
        return {}
    
    def get_active_theme(config_data):
        return "default"
    
    def get_theme_colors(config_data, theme_name):
        return {}
    
    def get_background_colors(config_data):
        return {"primary": "#ffffff", "secondary": "#f5f5f5"}
    
    def get_font_colors(config_data):
        return {"primary": "#000000", "secondary": "#666666"}
    
    def get_accent_colors(config_data):
        return {"primary": "#0078d7", "secondary": "#005a9e"}

__all__ = [
    'set_config_value',
    'get_config_value',
    'get_optimization_thresholds',
    'get_active_theme',
    'get_theme_colors',
    'get_background_colors',
    'get_font_colors',
    'get_accent_colors',
]

# -*- coding: utf-8 -*-
"""
Theme Configuration Helpers for FilterMate.

Provides utility functions for accessing theme-related configuration values.
Extracted from modules/config_helpers.py during EPIC-1 migration.

Author: FilterMate Team
Date: January 2026
"""
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger('FilterMate.ThemeHelpers')


def get_config_value(config_data: Dict[str, Any], *keys) -> Optional[Any]:
    """
    Get config value by nested keys.
    
    Args:
        config_data: Configuration dictionary
        *keys: Nested keys to traverse
    
    Returns:
        Value at the nested path, or None if not found
    """
    current = config_data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def get_active_theme(config_data: Dict[str, Any]) -> str:
    """
    Get active theme from config.
    
    Args:
        config_data: Configuration dictionary
    
    Returns:
        Active theme name, defaults to 'default'
    """
    # Try new structure
    theme = get_config_value(config_data, "app", "active_theme")
    if theme is None:
        # Try old structure
        theme = get_config_value(config_data, "APP", "DOCKWIDGET", "COLORS", "ACTIVE_THEME")
    
    # FIX 2026-02-02: Config values can be dict with 'value' key or plain string
    if isinstance(theme, dict):
        theme = theme.get('value', 'default')
    
    return theme or "default"


def get_theme_colors(config_data: Dict[str, Any], theme_name: str) -> Dict[str, Any]:
    """
    Get colors for a specific theme.
    
    Args:
        config_data: Configuration dictionary
        theme_name: Name of the theme
    
    Returns:
        Dictionary of theme colors
    """
    # Try new structure
    themes = get_config_value(config_data, "app", "themes")
    if themes and theme_name in themes:
        return themes[theme_name]
    # Try old structure
    themes = get_config_value(config_data, "APP", "DOCKWIDGET", "COLORS", "THEMES")
    if themes and theme_name in themes:
        return themes[theme_name]
    return {}


def get_background_colors(config_data: Dict[str, Any]) -> List[str]:
    """
    Get background colors from config.
    
    Args:
        config_data: Configuration dictionary
    
    Returns:
        List of background colors [bg0, bg1, bg2, bg3]
    """
    active_theme = get_active_theme(config_data)
    colors = get_theme_colors(config_data, active_theme)
    # Try both cases: "BACKGROUND" (old) and "background" (new)
    bg = colors.get("BACKGROUND") or colors.get("background")
    if bg:
        return bg
    # Fallback to root BACKGROUND in COLORS section
    bg = get_config_value(config_data, "APP", "DOCKWIDGET", "COLORS", "BACKGROUND")
    if bg:
        return bg
    # Default fallback (light theme colors)
    return ["#F5F5F5", "#FFFFFF", "#E0E0E0", "#2196F3"]


def get_font_colors(config_data: Dict[str, Any]) -> List[str]:
    """
    Get font colors from config.
    
    Args:
        config_data: Configuration dictionary
    
    Returns:
        List of font colors [font0, font1, font2]
    """
    active_theme = get_active_theme(config_data)
    colors = get_theme_colors(config_data, active_theme)
    # Try both cases: "FONT" (old) and "font" (new)
    font = colors.get("FONT") or colors.get("font")
    if font:
        return font
    # Fallback to root FONT in COLORS section
    font = get_config_value(config_data, "APP", "DOCKWIDGET", "COLORS", "FONT")
    if font:
        return font
    # Default fallback (dark text for light theme)
    return ["#212121", "#616161", "#BDBDBD"]


def get_accent_colors(config_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Get accent colors from config.
    
    Args:
        config_data: Configuration dictionary
    
    Returns:
        Dictionary with accent colors (PRIMARY, HOVER, PRESSED, LIGHT_BG, DARK)
    """
    active_theme = get_active_theme(config_data)
    colors = get_theme_colors(config_data, active_theme)
    # Try both cases: "ACCENT" (old) and "accent" (new)
    accent = colors.get("ACCENT") or colors.get("accent")
    if accent:
        return accent
    # Fallback to root ACCENT in COLORS section
    accent = get_config_value(config_data, "APP", "DOCKWIDGET", "COLORS", "ACCENT")
    if accent:
        return accent
    # Default fallback
    return {
        "PRIMARY": "#1976D2",
        "HOVER": "#2196F3",
        "PRESSED": "#0D47A1",
        "LIGHT_BG": "#E3F2FD",
        "DARK": "#01579B"
    }


def get_available_themes(config_data: Dict[str, Any]) -> List[str]:
    """
    Get list of available theme names.
    
    Args:
        config_data: Configuration dictionary
    
    Returns:
        List of available theme names
    """
    # Try new structure
    themes = get_config_value(config_data, "app", "themes")
    if themes:
        return list(themes.keys())
    # Try old structure
    themes = get_config_value(config_data, "APP", "DOCKWIDGET", "COLORS", "THEMES")
    if themes:
        return list(themes.keys())
    return ["default", "dark"]


__all__ = [
    'get_config_value',
    'get_active_theme',
    'get_theme_colors',
    'get_background_colors',
    'get_font_colors',
    'get_accent_colors',
    'get_available_themes',
]

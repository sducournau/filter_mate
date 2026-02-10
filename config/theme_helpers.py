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
    if theme:
        return theme
    # Try old structure
    theme = get_config_value(config_data, "APP", "DOCKWIDGET", "COLORS", "ACTIVE_THEME")
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


def get_background_colors(config_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Get background colors from config.

    Args:
        config_data: Configuration dictionary

    Returns:
        Dictionary with primary and secondary background colors
    """
    active_theme = get_active_theme(config_data)
    colors = get_theme_colors(config_data, active_theme)
    return colors.get("background", {"primary": "#ffffff", "secondary": "#f5f5f5"})


def get_font_colors(config_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Get font colors from config.

    Args:
        config_data: Configuration dictionary

    Returns:
        Dictionary with primary and secondary font colors
    """
    active_theme = get_active_theme(config_data)
    colors = get_theme_colors(config_data, active_theme)
    return colors.get("font", {"primary": "#000000", "secondary": "#666666"})


def get_accent_colors(config_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Get accent colors from config.

    Args:
        config_data: Configuration dictionary

    Returns:
        Dictionary with primary and secondary accent colors
    """
    active_theme = get_active_theme(config_data)
    colors = get_theme_colors(config_data, active_theme)
    return colors.get("accent", {"primary": "#0078d7", "secondary": "#005a9e"})


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

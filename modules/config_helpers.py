# -*- coding: utf-8 -*-
"""
Configuration Helpers for FilterMate

Utility functions to read and write configuration values,
with support for ChoicesType format.

ChoicesType format:
{
    "value": "current_value",
    "choices": ["option1", "option2", "option3"]
}
"""

from typing import Any, Optional, List, Union
from qgis.core import QgsMessageLog, Qgis


def reload_config_from_file():
    """
    Reload configuration from config.json file.
    This is a wrapper around config.reload_config() for convenience.
    
    Returns:
        dict: Reloaded configuration data, or None if failed
    """
    try:
        from ..config.config import reload_config
        return reload_config()
    except Exception as e:
        QgsMessageLog.logMessage(
            f"Error reloading config: {e}",
            "FilterMate",
            Qgis.Critical
        )
        return None


def reset_config_to_defaults(backup=True, preserve_app_settings=True):
    """
    Reset configuration to default values.
    This is a wrapper around config.reset_config_to_default() for convenience.
    
    Args:
        backup (bool): If True, create a backup of current config before resetting
        preserve_app_settings (bool): If True, preserve APP_SQLITE_PATH and other app settings
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from ..config.config import reset_config_to_default
        return reset_config_to_default(backup=backup, preserve_app_settings=preserve_app_settings)
    except Exception as e:
        QgsMessageLog.logMessage(
            f"Error resetting config: {e}",
            "FilterMate",
            Qgis.Critical
        )
        return False


def save_config_to_file(config_data):
    """
    Save configuration data to config.json file.
    This is a wrapper around config.save_config() for convenience.
    
    Args:
        config_data (dict): Configuration data to save
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from ..config.config import save_config
        return save_config(config_data)
    except Exception as e:
        QgsMessageLog.logMessage(
            f"Error saving config: {e}",
            "FilterMate",
            Qgis.Critical
        )
        return False


def get_config_value(config_data: dict, *path_keys, default=None) -> Any:
    """
    Get a configuration value, handling ChoicesType format automatically.
    
    Args:
        config_data: Root configuration dictionary
        *path_keys: Path to the configuration value (e.g., "APP", "UI", "profile")
        default: Default value if path not found
    
    Returns:
        The configuration value (extracted from ChoicesType if applicable)
    
    Examples:
        >>> config = {"APP": {"UI": {"profile": {"value": "auto", "choices": [...]}}}}
        >>> get_config_value(config, "APP", "UI", "profile")
        'auto'
        
        >>> config = {"APP": {"name": "FilterMate"}}
        >>> get_config_value(config, "APP", "name")
        'FilterMate'
    """
    try:
        value = config_data
        for key in path_keys:
            value = value[key]
        
        # If value is a ChoicesType dict, extract the 'value' key
        if isinstance(value, dict) and 'value' in value and 'choices' in value:
            return value['value']
        
        return value
    except (KeyError, TypeError):
        return default


def set_config_value(config_data: dict, value: Any, *path_keys) -> None:
    """
    Set a configuration value, handling ChoicesType format automatically.
    
    Args:
        config_data: Root configuration dictionary
        value: New value to set
        *path_keys: Path to the configuration value
    
    Raises:
        KeyError: If path doesn't exist
        ValueError: If value not in choices (for ChoicesType)
    
    Examples:
        >>> config = {"APP": {"UI": {"profile": {"value": "auto", "choices": ["auto", "compact"]}}}}
        >>> set_config_value(config, "compact", "APP", "UI", "profile")
        >>> config["APP"]["UI"]["profile"]["value"]
        'compact'
    """
    # Navigate to parent
    current = config_data
    for key in path_keys[:-1]:
        current = current[key]
    
    # Get target
    final_key = path_keys[-1]
    target = current[final_key]
    
    # If target is ChoicesType, update the 'value' key
    if isinstance(target, dict) and 'value' in target and 'choices' in target:
        if value not in target['choices']:
            raise ValueError(
                f"Value '{value}' not in choices {target['choices']}"
            )
        target['value'] = value
    else:
        # Direct assignment
        current[final_key] = value


def get_config_choices(config_data: dict, *path_keys) -> Optional[List[Any]]:
    """
    Get available choices for a ChoicesType configuration value.
    
    Args:
        config_data: Root configuration dictionary
        *path_keys: Path to the configuration value
    
    Returns:
        List of available choices, or None if not a ChoicesType
    
    Examples:
        >>> config = {"APP": {"UI": {"profile": {"value": "auto", "choices": ["auto", "compact", "normal"]}}}}
        >>> get_config_choices(config, "APP", "UI", "profile")
        ['auto', 'compact', 'normal']
    """
    try:
        value = config_data
        for key in path_keys:
            value = value[key]
        
        if isinstance(value, dict) and 'choices' in value:
            return value['choices']
        
        return None
    except (KeyError, TypeError):
        return None


def is_choices_type(config_data: dict, *path_keys) -> bool:
    """
    Check if a configuration value uses ChoicesType format.
    
    Args:
        config_data: Root configuration dictionary
        *path_keys: Path to the configuration value
    
    Returns:
        True if value is a ChoicesType, False otherwise
    
    Examples:
        >>> config = {"APP": {"UI": {"profile": {"value": "auto", "choices": [...]}}}}
        >>> is_choices_type(config, "APP", "UI", "profile")
        True
        
        >>> is_choices_type(config, "APP", "name")
        False
    """
    try:
        value = config_data
        for key in path_keys:
            value = value[key]
        
        return isinstance(value, dict) and 'value' in value and 'choices' in value
    except (KeyError, TypeError):
        return False


def validate_config_value(config_data: dict, value: Any, *path_keys) -> bool:
    """
    Validate a value against configuration constraints (e.g., choices).
    
    Args:
        config_data: Root configuration dictionary
        value: Value to validate
        *path_keys: Path to the configuration value
    
    Returns:
        True if value is valid, False otherwise
    
    Examples:
        >>> config = {"APP": {"UI": {"profile": {"value": "auto", "choices": ["auto", "compact", "normal"]}}}}
        >>> validate_config_value(config, "compact", "APP", "UI", "profile")
        True
        
        >>> validate_config_value(config, "invalid", "APP", "UI", "profile")
        False
    """
    if is_choices_type(config_data, *path_keys):
        choices = get_config_choices(config_data, *path_keys)
        return value in choices if choices else False
    
    # For non-ChoicesType, any value is valid (type checking could be added)
    return True


def get_config_with_fallback(
    config_data: dict,
    path_keys: tuple,
    fallback_path_keys: tuple,
    default=None
) -> Any:
    """
    Get a configuration value with fallback path (for backward compatibility).
    
    Args:
        config_data: Root configuration dictionary
        path_keys: Primary path to try first
        fallback_path_keys: Fallback path if primary not found
        default: Default value if both paths fail
    
    Returns:
        Configuration value from primary or fallback path
    
    Examples:
        >>> config = {"OLD": {"PATH": "value"}}
        >>> get_config_with_fallback(config, ("NEW", "PATH"), ("OLD", "PATH"))
        'value'
    """
    value = get_config_value(config_data, *path_keys, default=None)
    if value is not None:
        return value
    
    return get_config_value(config_data, *fallback_path_keys, default=default)


# Convenience functions for common config paths


def get_ui_profile(config_data: dict) -> str:
    """Get current UI profile (auto/compact/normal)."""
    return get_config_with_fallback(
        config_data,
        ("APP", "UI", "profile"),
        ("APP", "DOCKWIDGET", "UI_PROFILE"),
        default="auto"
    )


def set_ui_profile(config_data: dict, value: str) -> None:
    """Set UI profile value."""
    try:
        set_config_value(config_data, value, "APP", "UI", "profile")
    except KeyError:
        # Fallback to old structure
        set_config_value(config_data, value, "APP", "DOCKWIDGET", "UI_PROFILE")


def get_active_theme(config_data: dict) -> str:
    """Get active theme (auto/default/dark/light)."""
    return get_config_with_fallback(
        config_data,
        ("APP", "UI", "theme", "active"),
        ("APP", "DOCKWIDGET", "COLORS", "ACTIVE_THEME"),
        default="auto"
    )


def get_theme_source(config_data: dict) -> str:
    """Get theme source (config/qgis/system)."""
    return get_config_with_fallback(
        config_data,
        ("APP", "UI", "theme", "source"),
        ("APP", "DOCKWIDGET", "COLORS", "THEME_SOURCE"),
        default="config"
    )


def get_export_style_format(config_data: dict, section: str = "EXPORTING") -> str:
    """Get export style format (QML/SLD/None)."""
    return get_config_value(
        config_data,
        "CURRENT_PROJECT",
        section,
        "STYLES_TO_EXPORT",
        default="QML"
    )


def get_export_data_format(config_data: dict, section: str = "EXPORTING") -> str:
    """Get export data format (GPKG/SHP/GEOJSON/etc)."""
    return get_config_value(
        config_data,
        "CURRENT_PROJECT",
        section,
        "DATATYPE_TO_EXPORT",
        default="GPKG"
    )

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

Enhanced with metadata support - use config_metadata module for:
- Widget type detection (checkbox, combobox, etc.)
- User-friendly labels and descriptions
- Validation rules
"""

from typing import Any, Optional, List, Union, Dict, Tuple

# Import metadata utilities
try:
    from .config_metadata import get_config_metadata
    METADATA_AVAILABLE = True
except ImportError:
    METADATA_AVAILABLE = False


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


# ============================================================================
# Extended Helpers for Configuration Harmonization
# ============================================================================

# === UI Configuration ===

def get_feedback_level(config_data: dict) -> str:
    """Get feedback level (minimal/normal/verbose)."""
    return get_config_with_fallback(
        config_data,
        ("app", "ui", "feedback", "level"),  # New structure
        ("APP", "DOCKWIDGET", "FEEDBACK_LEVEL"),  # Old structure
        default="normal"
    )


def get_ui_action_bar_position(config_data: dict) -> str:
    """Get action bar position (top/bottom/left/right)."""
    return get_config_with_fallback(
        config_data,
        ("app", "ui", "action_bar", "position"),
        ("APP", "DOCKWIDGET", "ACTION_BAR_POSITION"),
        default="left"
    )


def get_ui_action_bar_alignment(config_data: dict) -> str:
    """Get action bar vertical alignment (top/bottom)."""
    return get_config_with_fallback(
        config_data,
        ("app", "ui", "action_bar", "vertical_alignment"),
        ("APP", "DOCKWIDGET", "ACTION_BAR_VERTICAL_ALIGNMENT"),
        default="top"
    )


# === Button Configuration ===

def get_button_icon(config_data: dict, category: str, name: str) -> str:
    """
    Get button icon filename.
    
    Args:
        config_data: Configuration dictionary
        category: Icon category (action/exploring/filtering/exporting)
        name: Icon name (filter/undo/zoom/etc)
    
    Returns:
        Icon filename (e.g., "filter.png")
    """
    # Try new structure
    try:
        return config_data["app"]["buttons"]["icons"][category.lower()][name.lower()]
    except (KeyError, TypeError):
        pass
    
    # Fallback to old structure
    category_map = {
        "action": "ACTION",
        "exploring": "EXPLORING",
        "filtering": "FILTERING",
        "exporting": "EXPORTING"
    }
    old_category = category_map.get(category.lower(), category.upper())
    
    return get_config_value(
        config_data,
        "APP", "DOCKWIDGET", "PushButton", "ICONS", old_category, name.upper(),
        default="icon.png"
    )


def get_button_icon_size(config_data: dict, button_type: str = "action") -> int:
    """Get button icon size."""
    return get_config_with_fallback(
        config_data,
        ("app", "buttons", "icon_sizes", button_type.lower()),
        ("APP", "DOCKWIDGET", "PushButton", "ICONS_SIZES", button_type.upper()),
        default=25 if button_type.lower() == "action" else 20
    )


# === Theme/Color Configuration ===

def get_theme_colors(config_data: dict, theme_name: str = None) -> dict:
    """Get color palette for a theme."""
    if theme_name is None:
        theme_name = get_active_theme(config_data)
    
    # Try new structure
    try:
        return config_data["app"]["themes"][theme_name]
    except (KeyError, TypeError):
        pass
    
    # Fallback to old structure
    return get_config_value(
        config_data,
        "APP", "DOCKWIDGET", "COLORS", "THEMES", theme_name,
        default={}
    )


def get_font_colors(config_data: dict) -> list:
    """Get font colors array [primary, secondary, disabled]."""
    theme_name = get_active_theme(config_data)
    colors = get_theme_colors(config_data, theme_name)
    
    # Try new structure key
    font_colors = colors.get("font")
    if font_colors:
        return font_colors
    
    # Fallback to old structure key
    font_colors = colors.get("FONT")
    if font_colors:
        return font_colors
    
    # Default fallback
    return ["#212121", "#616161", "#BDBDBD"]


def get_background_colors(config_data: dict) -> list:
    """Get background colors array."""
    theme_name = get_active_theme(config_data)
    colors = get_theme_colors(config_data, theme_name)
    
    # Try new structure key
    bg_colors = colors.get("background")
    if bg_colors:
        return bg_colors
    
    # Fallback to old structure key
    bg_colors = colors.get("BACKGROUND")
    if bg_colors:
        return bg_colors
    
    # Default fallback
    return ["#F5F5F5", "#FFFFFF", "#E0E0E0", "#2196F3"]


def get_accent_colors(config_data: dict) -> dict:
    """Get accent colors dict."""
    theme_name = get_active_theme(config_data)
    colors = get_theme_colors(config_data, theme_name)
    
    # Try new structure key
    accent = colors.get("accent")
    if accent:
        return accent
    
    # Fallback to old structure key
    accent = colors.get("ACCENT")
    if accent:
        return accent
    
    # Default fallback
    return {
        "primary": "#1976D2",
        "hover": "#2196F3",
        "pressed": "#0D47A1",
        "light_bg": "#E3F2FD",
        "dark": "#01579B"
    }


# === Project Configuration ===

def get_layer_properties_count(config_data: dict) -> int:
    """Get expected layer properties count."""
    return get_config_with_fallback(
        config_data,
        ("project", "layers", "properties_count"),
        ("CURRENT_PROJECT", "OPTIONS", "LAYERS", "LAYER_PROPERTIES_COUNT"),
        default=35
    )


def set_layer_properties_count(config_data: dict, count: int) -> None:
    """Set layer properties count."""
    try:
        # Try new structure
        if "project" in config_data:
            config_data["project"]["layers"]["properties_count"] = count
            return
    except (KeyError, TypeError):
        pass
    
    # Fallback to old structure
    if "CURRENT_PROJECT" in config_data:
        config_data["CURRENT_PROJECT"]["OPTIONS"]["LAYERS"]["LAYER_PROPERTIES_COUNT"] = count


def get_postgresql_active_connection(config_data: dict) -> str:
    """Get active PostgreSQL connection string."""
    return get_config_with_fallback(
        config_data,
        ("project", "postgresql", "active_connection"),
        ("CURRENT_PROJECT", "OPTIONS", "ACTIVE_POSTGRESQL"),
        default=""
    )


def is_postgresql_active(config_data: dict) -> bool:
    """Check if PostgreSQL is active."""
    return get_config_with_fallback(
        config_data,
        ("project", "postgresql", "is_active"),
        ("CURRENT_PROJECT", "OPTIONS", "IS_ACTIVE_POSTGRESQL"),
        default=False
    )


def set_postgresql_connection(config_data: dict, connection_string: str, is_active: bool) -> None:
    """Set PostgreSQL connection."""
    try:
        # Try new structure
        if "project" in config_data:
            if "postgresql" not in config_data["project"]:
                config_data["project"]["postgresql"] = {}
            config_data["project"]["postgresql"]["active_connection"] = connection_string
            config_data["project"]["postgresql"]["is_active"] = is_active
            return
    except (KeyError, TypeError):
        pass
    
    # Fallback to old structure
    if "CURRENT_PROJECT" in config_data:
        if "OPTIONS" not in config_data["CURRENT_PROJECT"]:
            config_data["CURRENT_PROJECT"]["OPTIONS"] = {}
        config_data["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"] = connection_string
        config_data["CURRENT_PROJECT"]["OPTIONS"]["IS_ACTIVE_POSTGRESQL"] = is_active


# === Export Configuration ===

def get_export_layers_enabled(config_data: dict) -> bool:
    """Check if layers export is enabled."""
    return get_config_with_fallback(
        config_data,
        ("project", "export", "layers", "enabled"),
        ("CURRENT_PROJECT", "EXPORTING", "HAS_LAYERS_TO_EXPORT"),
        default=False
    )


def get_export_layers_list(config_data: dict) -> list:
    """Get list of layers to export."""
    return get_config_with_fallback(
        config_data,
        ("project", "export", "layers", "selected"),
        ("CURRENT_PROJECT", "EXPORTING", "LAYERS_TO_EXPORT"),
        default=[]
    )


def get_export_projection_epsg(config_data: dict) -> str:
    """Get export projection EPSG code."""
    return get_config_with_fallback(
        config_data,
        ("project", "export", "projection", "epsg"),
        ("CURRENT_PROJECT", "EXPORTING", "PROJECTION_TO_EXPORT"),
        default="EPSG:3857"
    )


def get_export_projection_enabled(config_data: dict) -> bool:
    """Check if projection export is enabled."""
    return get_config_with_fallback(
        config_data,
        ("project", "export", "projection", "enabled"),
        ("CURRENT_PROJECT", "EXPORTING", "HAS_PROJECTION_TO_EXPORT"),
        default=False
    )


def get_export_output_folder(config_data: dict) -> str:
    """Get export output folder path."""
    return get_config_with_fallback(
        config_data,
        ("project", "export", "output", "folder", "path"),
        ("CURRENT_PROJECT", "EXPORTING", "OUTPUT_FOLDER_TO_EXPORT"),
        default=""
    )


def get_export_zip_path(config_data: dict) -> str:
    """Get export ZIP file path."""
    return get_config_with_fallback(
        config_data,
        ("project", "export", "output", "zip", "path"),
        ("CURRENT_PROJECT", "EXPORTING", "ZIP_TO_EXPORT"),
        default=""
    )


# === App Paths and Flags ===

def get_github_page_url(config_data: dict) -> str:
    """Get GitHub documentation page URL."""
    return get_config_with_fallback(
        config_data,
        ("app", "paths", "github_page"),
        ("APP", "OPTIONS", "GITHUB_PAGE"),
        default="https://sducournau.github.io/filter_mate/"
    )


def get_github_repo_url(config_data: dict) -> str:
    """Get GitHub repository URL."""
    return get_config_with_fallback(
        config_data,
        ("app", "paths", "github_repo"),
        ("APP", "OPTIONS", "GITHUB_REPOSITORY"),
        default="https://github.com/sducournau/filter_mate/"
    )


def get_plugin_repo_url(config_data: dict) -> str:
    """Get QGIS plugin repository URL."""
    return get_config_with_fallback(
        config_data,
        ("app", "paths", "plugin_repo"),
        ("APP", "OPTIONS", "QGIS_PLUGIN_REPOSITORY"),
        default="https://plugins.qgis.org/plugins/filter_mate/"
    )


def get_sqlite_storage_path(config_data: dict) -> str:
    """Get SQLite storage path."""
    return get_config_with_fallback(
        config_data,
        ("app", "paths", "sqlite_storage"),
        ("APP", "OPTIONS", "APP_SQLITE_PATH"),
        default=""
    )


def get_fresh_reload_flag(config_data: dict) -> bool:
    """Get fresh reload flag."""
    return get_config_with_fallback(
        config_data,
        ("app", "flags", "fresh_reload"),
        ("APP", "OPTIONS", "FRESH_RELOAD_FLAG"),
        default=False
    )


def set_fresh_reload_flag(config_data: dict, value: bool) -> None:
    """Set fresh reload flag."""
    try:
        # Try new structure
        if "app" in config_data:
            if "flags" not in config_data["app"]:
                config_data["app"]["flags"] = {}
            config_data["app"]["flags"]["fresh_reload"] = value
            return
    except (KeyError, TypeError):
        pass
    
    # Fallback to old structure
    if "APP" in config_data:
        if "OPTIONS" not in config_data["APP"]:
            config_data["APP"]["OPTIONS"] = {}
        config_data["APP"]["OPTIONS"]["FRESH_RELOAD_FLAG"] = value


# === Project Meta ===

def get_project_id(config_data: dict) -> str:
    """Get current project ID."""
    return get_config_with_fallback(
        config_data,
        ("project", "meta", "id"),
        ("CURRENT_PROJECT", "OPTIONS", "PROJECT_ID"),
        default=""
    )


def get_project_path(config_data: dict) -> str:
    """Get current project path."""
    return get_config_with_fallback(
        config_data,
        ("project", "meta", "path"),
        ("CURRENT_PROJECT", "OPTIONS", "PROJECT_PATH"),
        default=""
    )


def get_project_sqlite_path(config_data: dict) -> str:
    """Get project SQLite database path."""
    return get_config_with_fallback(
        config_data,
        ("project", "postgresql", "sqlite_path"),
        ("CURRENT_PROJECT", "OPTIONS", "PROJECT_SQLITE_PATH"),
        default=""
    )


# === Layer Configuration ===

def get_link_legend_layers_flag(config_data: dict) -> bool:
    """Get flag for linking legend layers with current layer."""
    return get_config_with_fallback(
        config_data,
        ("project", "layers", "link_legend"),
        ("CURRENT_PROJECT", "OPTIONS", "LAYERS", "LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"),
        default=True
    )


# ============================================================================
# Metadata-Enhanced Functions
# ============================================================================

def get_config_metadata_for_path(config_path: str) -> Optional[Dict[str, Any]]:
    """
    Get metadata for a configuration path.
    
    Args:
        config_path: Dot-separated path (e.g., 'app.ui.profile')
    
    Returns:
        Metadata dictionary or None
    
    Example:
        >>> meta = get_config_metadata_for_path('app.ui.profile')
        >>> print(meta['description'])
        'UI layout profile - auto detects screen size...'
    """
    if not METADATA_AVAILABLE:
        return None
    
    try:
        metadata = get_config_metadata()
        return metadata.get_metadata(config_path)
    except Exception:
        return None


def get_widget_type_for_config(config_path: str) -> str:
    """
    Get recommended widget type for a configuration parameter.
    
    Args:
        config_path: Dot-separated path (e.g., 'app.auto_activate')
    
    Returns:
        Widget type: 'checkbox', 'combobox', 'textbox', 'spinbox', 'colorpicker'
    
    Example:
        >>> widget = get_widget_type_for_config('app.auto_activate')
        >>> print(widget)  # 'checkbox'
    """
    if not METADATA_AVAILABLE:
        return 'textbox'
    
    try:
        metadata = get_config_metadata()
        return metadata.get_widget_type(config_path)
    except Exception:
        return 'textbox'


def get_config_description(config_path: str) -> str:
    """
    Get user-friendly description for a configuration parameter.
    
    Args:
        config_path: Dot-separated path
    
    Returns:
        Description string
    """
    if not METADATA_AVAILABLE:
        return ""
    
    try:
        metadata = get_config_metadata()
        return metadata.get_description(config_path)
    except Exception:
        return ""


def get_config_label(config_path: str) -> str:
    """
    Get user-friendly label for UI display.
    
    Args:
        config_path: Dot-separated path
    
    Returns:
        User-friendly label
    """
    if not METADATA_AVAILABLE:
        return config_path.split('.')[-1].replace('_', ' ').title()
    
    try:
        metadata = get_config_metadata()
        return metadata.get_user_friendly_label(config_path)
    except Exception:
        return config_path.split('.')[-1].replace('_', ' ').title()


def get_config_allowed_values(config_path: str) -> Optional[List[Any]]:
    """
    Get list of allowed values for a configuration parameter.
    
    Args:
        config_path: Dot-separated path
    
    Returns:
        List of allowed values or None
    """
    if not METADATA_AVAILABLE:
        return None
    
    try:
        metadata = get_config_metadata()
        return metadata.get_allowed_values(config_path)
    except Exception:
        return None


def validate_config_value_with_metadata(config_path: str, value: Any) -> Tuple[bool, str]:
    """
    Validate a configuration value using metadata rules.
    
    Args:
        config_path: Dot-separated path
        value: Value to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    
    Example:
        >>> valid, error = validate_config_value_with_metadata('app.ui.profile', 'invalid')
        >>> print(valid, error)
        False, 'Value must be one of: auto, compact, normal'
    """
    if not METADATA_AVAILABLE:
        return True, ""
    
    try:
        metadata = get_config_metadata()
        return metadata.validate_value(config_path, value)
    except Exception as e:
        return False, str(e)


def get_all_configurable_paths() -> List[str]:
    """
    Get list of all configuration paths that have metadata.
    
    Returns:
        List of dot-separated configuration paths
    """
    if not METADATA_AVAILABLE:
        return []
    
    try:
        metadata = get_config_metadata()
        return metadata.get_all_config_paths()
    except Exception:
        return []


def get_config_groups() -> Dict[str, List[str]]:
    """
    Get configuration parameters grouped by category.
    
    Returns:
        Dictionary mapping category names to lists of config paths
    
    Example:
        >>> groups = get_config_groups()
        >>> print(groups['UI'])
        ['app.ui.profile', 'app.ui.theme.active', ...]
    """
    if not METADATA_AVAILABLE:
        return {}
    
    try:
        metadata = get_config_metadata()
        return metadata.get_config_groups()
    except Exception:
        return {}


def get_feature_count_limit(config_data: dict) -> int:
    """Get feature count limit."""
    return get_config_with_fallback(
        config_data,
        ("project", "layers", "feature_limit"),
        ("CURRENT_PROJECT", "OPTIONS", "LAYERS", "FEATURE_COUNT_LIMIT"),
        default=10000
    )

"""
Configuration Schema for FilterMate

This module defines the configuration schema with:
- Clear hierarchical structure
- Type validation
- Default values
- Metadata for UI rendering (choices, descriptions)
- Feature toggles

The schema is organized into logical sections:
- GENERAL: Language, feedback level, paths
- FEATURES: Enable/disable plugin features
- UI: Visual customization (themes, sizes, positions)
- JSON_VIEW: Qt JSON View specific settings
- EXPORT: Export functionality settings
- PROJECT: Project-specific runtime settings
"""

from typing import Any, Dict, List, Optional, Union


# =============================================================================
# Configuration Schema Definition
# =============================================================================

CONFIG_SCHEMA = {
    # -------------------------------------------------------------------------
    # GENERAL SETTINGS
    # -------------------------------------------------------------------------
    "GENERAL": {
        "_section_meta": {
            "title": "General Settings",
            "description": "Core plugin settings including language and feedback level",
            "icon": "settings.png"
        },
        "LANGUAGE": {
            "type": "choices",
            "choices": ["auto", "en", "fr", "pt", "es", "it", "de", "nl"],
            "default": "auto",
            "description": "Plugin language: 'auto' uses QGIS locale",
            "requires_restart": True
        },
        "FEEDBACK_LEVEL": {
            "type": "choices",
            "choices": ["minimal", "normal", "verbose"],
            "default": "normal",
            "description": "User feedback verbosity level"
        },
        "APP_SQLITE_PATH": {
            "type": "filepath",
            "default": "",
            "description": "Custom path for FilterMate data storage (leave empty for default)",
            "file_mode": "directory"
        }
    },
    
    # -------------------------------------------------------------------------
    # FEATURE TOGGLES
    # -------------------------------------------------------------------------
    "FEATURES": {
        "_section_meta": {
            "title": "Feature Toggles",
            "description": "Enable or disable specific plugin features",
            "icon": "features.png"
        },
        "ENABLE_UNDO_REDO": {
            "type": "boolean",
            "default": True,
            "description": "Enable undo/redo functionality for filters"
        },
        "ENABLE_FILTER_HISTORY": {
            "type": "boolean",
            "default": True,
            "description": "Track and display filter history"
        },
        "ENABLE_EXPORT": {
            "type": "boolean",
            "default": True,
            "description": "Enable data export functionality"
        },
        "ENABLE_LAYER_LINKING": {
            "type": "boolean",
            "default": True,
            "description": "Enable layer linking/tracking feature"
        },
        "ENABLE_GEOMETRIC_PREDICATES": {
            "type": "boolean",
            "default": True,
            "description": "Enable geometric predicate filters (intersects, within, etc.)"
        },
        "ENABLE_BUFFER_FILTER": {
            "type": "boolean",
            "default": True,
            "description": "Enable buffer-based filtering"
        },
        "ENABLE_ADVANCED_CONFIG": {
            "type": "boolean",
            "default": True,
            "description": "Show advanced configuration panel"
        },
        "AUTO_CURRENT_LAYER": {
            "type": "boolean",
            "default": False,
            "description": "Automatically use current layer for filtering"
        }
    },
    
    # -------------------------------------------------------------------------
    # UI SETTINGS
    # -------------------------------------------------------------------------
    "UI": {
        "_section_meta": {
            "title": "User Interface",
            "description": "Visual customization options",
            "icon": "ui.png"
        },
        "PROFILE": {
            "type": "choices",
            "choices": ["auto", "compact", "normal"],
            "default": "auto",
            "description": "UI display profile: 'auto' detects from screen size"
        },
        "ACTION_BAR": {
            "POSITION": {
                "type": "choices",
                "choices": ["top", "bottom", "left", "right"],
                "default": "left",
                "description": "Position of the action bar",
                "requires_restart": True
            },
            "VERTICAL_ALIGNMENT": {
                "type": "choices",
                "choices": ["top", "bottom"],
                "default": "top",
                "description": "Vertical alignment when action bar is on left/right"
            }
        },
        "ICONS": {
            "SIZE_ACTION": {
                "type": "range",
                "min": 16,
                "max": 48,
                "default": 25,
                "description": "Size of action buttons in pixels"
            },
            "SIZE_OTHERS": {
                "type": "range",
                "min": 12,
                "max": 32,
                "default": 20,
                "description": "Size of other icons in pixels"
            }
        },
        "THEME": {
            "MODE": {
                "type": "choices",
                "choices": ["auto", "config", "qgis", "system"],
                "default": "auto",
                "description": "Theme detection mode"
            },
            "ACTIVE": {
                "type": "choices",
                "choices": ["auto", "default", "dark", "light"],
                "default": "auto",
                "description": "Active color theme when mode is 'config'"
            }
        }
    },
    
    # -------------------------------------------------------------------------
    # JSON VIEW SETTINGS (qt_json_view integration)
    # -------------------------------------------------------------------------
    "JSON_VIEW": {
        "_section_meta": {
            "title": "Configuration Viewer",
            "description": "Settings for the JSON tree configuration viewer",
            "icon": "json.png"
        },
        "THEME": {
            "type": "choices",
            "choices": ["default", "monokai", "solarized_light", "solarized_dark", 
                       "nord", "dracula", "one_dark", "gruvbox", "auto"],
            "default": "auto",
            "description": "Color theme for JSON tree view. 'auto' matches UI theme."
        },
        "FONT_SIZE": {
            "type": "range",
            "min": 8,
            "max": 16,
            "default": 9,
            "description": "Font size for configuration tree"
        },
        "SHOW_ALTERNATING_ROWS": {
            "type": "boolean",
            "default": True,
            "description": "Show alternating row colors for better readability"
        },
        "EDITABLE_KEYS": {
            "type": "boolean",
            "default": True,
            "description": "Allow editing configuration keys (advanced users)"
        },
        "EDITABLE_VALUES": {
            "type": "boolean",
            "default": True,
            "description": "Allow editing configuration values"
        },
        "COLUMN_WIDTH_KEY": {
            "type": "range",
            "min": 100,
            "max": 300,
            "default": 180,
            "description": "Width of the property column"
        },
        "COLUMN_WIDTH_VALUE": {
            "type": "range",
            "min": 150,
            "max": 400,
            "default": 240,
            "description": "Width of the value column"
        }
    },
    
    # -------------------------------------------------------------------------
    # LAYER SETTINGS
    # -------------------------------------------------------------------------
    "LAYERS": {
        "_section_meta": {
            "title": "Layer Settings",
            "description": "Layer handling and performance options",
            "icon": "layers.png"
        },
        "LINK_LEGEND_LAYERS": {
            "type": "boolean",
            "default": True,
            "description": "Link legend layers selection with current layer"
        },
        "LAYER_PROPERTIES_COUNT": {
            "type": "range",
            "min": 10,
            "max": 100,
            "default": 35,
            "description": "Maximum layer properties to display"
        },
        "FEATURE_COUNT_LIMIT": {
            "type": "range",
            "min": 1000,
            "max": 100000,
            "default": 10000,
            "description": "Feature count threshold for performance warnings"
        },
        "FEATURE_COUNT_WARNING_THRESHOLD": {
            "type": "range",
            "min": 10000,
            "max": 500000,
            "default": 50000,
            "description": "Show warning when layer exceeds this feature count"
        }
    },
    
    # -------------------------------------------------------------------------
    # EXPORT SETTINGS
    # -------------------------------------------------------------------------
    "EXPORT": {
        "_section_meta": {
            "title": "Export Settings",
            "description": "Default export configuration",
            "icon": "export.png"
        },
        "DEFAULT_FORMAT": {
            "type": "choices",
            "choices": ["GPKG", "SHP", "GeoJSON", "CSV", "KML"],
            "default": "GPKG",
            "description": "Default export format"
        },
        "DEFAULT_CRS": {
            "type": "string",
            "default": "EPSG:4326",
            "description": "Default coordinate reference system for export"
        },
        "STYLE_FORMAT": {
            "type": "choices",
            "choices": ["QML", "SLD", "None"],
            "default": "QML",
            "description": "Style format to include with exports"
        },
        "REMEMBER_LAST_FOLDER": {
            "type": "boolean",
            "default": True,
            "description": "Remember last export folder location"
        },
        "LAST_FOLDER": {
            "type": "filepath",
            "default": "",
            "description": "Last used export folder (auto-saved)",
            "file_mode": "directory",
            "hidden": True
        }
    },
    
    # -------------------------------------------------------------------------
    # BACKEND SETTINGS
    # -------------------------------------------------------------------------
    "BACKEND": {
        "_section_meta": {
            "title": "Backend Settings",
            "description": "Database and processing backend preferences",
            "icon": "database.png"
        },
        "PREFERRED_BACKEND": {
            "type": "choices",
            "choices": ["auto", "postgresql", "spatialite", "ogr"],
            "default": "auto",
            "description": "Preferred processing backend. 'auto' selects based on layer type."
        },
        "USE_MATERIALIZED_VIEWS": {
            "type": "boolean",
            "default": True,
            "description": "Use materialized views for PostgreSQL (better performance)"
        },
        "SPATIALITE_TEMP_TABLES": {
            "type": "boolean",
            "default": True,
            "description": "Use temporary tables for Spatialite operations"
        },
        "CONNECTION_TIMEOUT": {
            "type": "range",
            "min": 5,
            "max": 120,
            "default": 30,
            "description": "Database connection timeout in seconds"
        }
    },
    
    # -------------------------------------------------------------------------
    # ADVANCED SETTINGS
    # -------------------------------------------------------------------------
    "ADVANCED": {
        "_section_meta": {
            "title": "Advanced Settings",
            "description": "Advanced options for power users",
            "icon": "advanced.png",
            "collapsed": True
        },
        "DEBUG_MODE": {
            "type": "boolean",
            "default": False,
            "description": "Enable debug logging (verbose output to console)"
        },
        "FRESH_RELOAD_FLAG": {
            "type": "boolean",
            "default": False,
            "description": "Force fresh reload on next plugin start",
            "hidden": True
        },
        "MAX_HISTORY_SIZE": {
            "type": "range",
            "min": 10,
            "max": 100,
            "default": 50,
            "description": "Maximum number of filter operations to keep in history"
        },
        "AUTO_SAVE_CONFIG": {
            "type": "boolean",
            "default": True,
            "description": "Automatically save configuration changes"
        }
    }
}


# =============================================================================
# UI Theme Definitions (for APP.DOCKWIDGET.COLORS)
# =============================================================================

UI_THEMES = {
    "default": {
        "name": "Default",
        "BACKGROUND": ["#F5F5F5", "#FFFFFF", "#E0E0E0", "#2196F3"],
        "FONT": ["#212121", "#616161", "#BDBDBD"],
        "ACCENT": {
            "PRIMARY": "#1976D2",
            "HOVER": "#2196F3",
            "PRESSED": "#0D47A1",
            "LIGHT_BG": "#E3F2FD",
            "DARK": "#01579B"
        }
    },
    "dark": {
        "name": "Dark",
        "BACKGROUND": ["#1E1E1E", "#2D2D30", "#3E3E42", "#007ACC"],
        "FONT": ["#EFF0F1", "#D0D0D0", "#808080"],
        "ACCENT": {
            "PRIMARY": "#007ACC",
            "HOVER": "#1E90FF",
            "PRESSED": "#005A9E",
            "LIGHT_BG": "#1E3A5F",
            "DARK": "#003D66"
        }
    },
    "light": {
        "name": "Light",
        "BACKGROUND": ["#FFFFFF", "#F5F5F5", "#E0E0E0", "#2196F3"],
        "FONT": ["#000000", "#424242", "#9E9E9E"],
        "ACCENT": {
            "PRIMARY": "#2196F3",
            "HOVER": "#64B5F6",
            "PRESSED": "#1976D2",
            "LIGHT_BG": "#E3F2FD",
            "DARK": "#0D47A1"
        }
    }
}


# =============================================================================
# JSON View Theme Mapping
# =============================================================================

JSON_VIEW_THEME_MAPPING = {
    # Maps UI theme to recommended JSON View theme
    "auto": "auto",
    "default": "default",
    "dark": "dracula",  # or 'monokai', 'one_dark'
    "light": "solarized_light"
}


# =============================================================================
# Helper Functions
# =============================================================================

def get_default_config() -> Dict[str, Any]:
    """
    Generate a default configuration dictionary from the schema.
    
    Returns:
        dict: Configuration with all default values
    """
    config = {}
    
    def extract_defaults(schema: Dict, target: Dict):
        for key, value in schema.items():
            if key.startswith('_'):
                continue
            if isinstance(value, dict):
                if 'type' in value and 'default' in value:
                    # This is a leaf setting
                    target[key] = value['default']
                else:
                    # This is a nested section
                    target[key] = {}
                    extract_defaults(value, target[key])
    
    extract_defaults(CONFIG_SCHEMA, config)
    return config


def validate_config_value(schema_entry: Dict, value: Any) -> tuple[bool, str]:
    """
    Validate a configuration value against its schema.
    
    Args:
        schema_entry: Schema definition for the setting
        value: Value to validate
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if 'type' not in schema_entry:
        return True, ""
    
    value_type = schema_entry['type']
    
    if value_type == 'boolean':
        if not isinstance(value, bool):
            return False, f"Expected boolean, got {type(value).__name__}"
    
    elif value_type == 'string':
        if not isinstance(value, str):
            return False, f"Expected string, got {type(value).__name__}"
    
    elif value_type == 'choices':
        choices = schema_entry.get('choices', [])
        if value not in choices:
            return False, f"Value must be one of: {choices}"
    
    elif value_type == 'range':
        if not isinstance(value, (int, float)):
            return False, f"Expected number, got {type(value).__name__}"
        min_val = schema_entry.get('min', float('-inf'))
        max_val = schema_entry.get('max', float('inf'))
        if value < min_val or value > max_val:
            return False, f"Value must be between {min_val} and {max_val}"
    
    elif value_type == 'filepath':
        if not isinstance(value, str):
            return False, f"Expected string path, got {type(value).__name__}"
    
    return True, ""


def get_json_view_theme_for_ui_theme(ui_theme: str) -> str:
    """
    Get the appropriate JSON View theme for a given UI theme.
    
    Args:
        ui_theme: The current UI theme name
    
    Returns:
        str: Recommended JSON View theme name
    """
    return JSON_VIEW_THEME_MAPPING.get(ui_theme, 'default')


def is_setting_hidden(schema_entry: Dict) -> bool:
    """Check if a setting should be hidden from the UI."""
    return schema_entry.get('hidden', False)


def requires_restart(schema_entry: Dict) -> bool:
    """Check if changing a setting requires plugin restart."""
    return schema_entry.get('requires_restart', False)


def get_setting_description(schema_entry: Dict) -> str:
    """Get the description for a setting."""
    return schema_entry.get('description', '')

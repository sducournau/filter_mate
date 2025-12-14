"""
FilterMate Configuration Package

This package provides configuration management for the FilterMate plugin.

Modules:
    - config: Original configuration loading (ENV_VARS)
    - config_schema: Schema definitions and validation
    - config_manager: Unified configuration manager (v2)
    - feedback_config: Feedback level configuration

Usage:
    # Original method (compatibility)
    from config.config import ENV_VARS, init_env_vars
    
    # New method (recommended)
    from config.config_manager import ConfigManager
    config = ConfigManager(plugin_dir)
    
    # Get settings
    language = config.get('GENERAL', 'LANGUAGE')
    
    # Check features
    if config.is_feature_enabled('ENABLE_UNDO_REDO'):
        ...
    
    # Get JSON View settings
    json_settings = config.get_json_view_settings()
"""

# Import for easy access
from .config import ENV_VARS, init_env_vars

# Try to import new modules (may not exist in older installations)
try:
    from .config_manager import ConfigManager, create_config_manager
    from .config_schema import (
        CONFIG_SCHEMA,
        UI_THEMES,
        JSON_VIEW_THEME_MAPPING,
        get_default_config,
        validate_config_value,
        get_json_view_theme_for_ui_theme,
    )
except ImportError:
    # Graceful degradation for older installations
    ConfigManager = None
    CONFIG_SCHEMA = None

__all__ = [
    # Original
    'ENV_VARS',
    'init_env_vars',
    
    # New (v2)
    'ConfigManager',
    'create_config_manager',
    'CONFIG_SCHEMA',
    'UI_THEMES',
    'JSON_VIEW_THEME_MAPPING',
    'get_default_config',
    'validate_config_value',
    'get_json_view_theme_for_ui_theme',
]

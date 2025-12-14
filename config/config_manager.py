"""
Configuration Manager for FilterMate

This module provides a unified configuration management layer that:
1. Bridges config.json with qt_json_view settings
2. Provides type-safe access to configuration values
3. Handles migration from old config format to new
4. Synchronizes JSON View theme with UI theme
5. Manages feature toggles

Usage:
    from config.config_manager import ConfigManager
    
    # Initialize
    config = ConfigManager(plugin_dir)
    
    # Get values with type safety
    language = config.get('GENERAL', 'LANGUAGE')
    
    # Check feature toggles
    if config.is_feature_enabled('ENABLE_UNDO_REDO'):
        ...
    
    # Get JSON View settings
    json_view_settings = config.get_json_view_settings()
"""

import json
import os
from typing import Any, Dict, List, Optional, Union
from qgis.core import QgsMessageLog, Qgis

try:
    from .config_schema import (
        CONFIG_SCHEMA,
        UI_THEMES,
        JSON_VIEW_THEME_MAPPING,
        get_default_config,
        validate_config_value,
        get_json_view_theme_for_ui_theme,
        is_setting_hidden,
        requires_restart,
    )
except ImportError:
    from config_schema import (
        CONFIG_SCHEMA,
        UI_THEMES,
        JSON_VIEW_THEME_MAPPING,
        get_default_config,
        validate_config_value,
        get_json_view_theme_for_ui_theme,
        is_setting_hidden,
        requires_restart,
    )


class ConfigManager:
    """
    Unified configuration manager for FilterMate.
    
    Provides type-safe access to configuration values with validation,
    automatic migration from old format, and qt_json_view integration.
    """
    
    # Config file names
    CONFIG_FILE = 'config.json'
    CONFIG_V2_FILE = 'config.v2.json'
    CONFIG_DEFAULT_FILE = 'config.default.json'
    
    # Settings to preserve from old config during reset
    PRESERVED_SETTINGS = [
        ('GENERAL', 'LANGUAGE'),
        ('GENERAL', 'APP_SQLITE_PATH'),
        ('LINKS', 'GITHUB_PAGE'),
        ('LINKS', 'GITHUB_REPOSITORY'),
    ]
    
    def __init__(self, plugin_dir: str, auto_load: bool = True):
        """
        Initialize the configuration manager.
        
        Args:
            plugin_dir: Path to the plugin directory
            auto_load: Whether to automatically load configuration
        """
        self.plugin_dir = plugin_dir
        self.config_dir = os.path.join(plugin_dir, 'config')
        self._data: Dict[str, Any] = {}
        self._schema = CONFIG_SCHEMA
        self._is_v2_format = False
        self._migrated_from_v1 = False
        
        if auto_load:
            self.load()
    
    # =========================================================================
    # Loading and Saving
    # =========================================================================
    
    def load(self) -> bool:
        """
        Load configuration from file.
        
        When old v1 config is detected, resets to defaults while preserving
        essential user settings (language, paths).
        
        Returns:
            bool: True if loaded successfully
        """
        try:
            # Try v2 format first
            v2_path = os.path.join(self.config_dir, self.CONFIG_V2_FILE)
            if os.path.exists(v2_path):
                with open(v2_path, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
                self._is_v2_format = True
                QgsMessageLog.logMessage(
                    "Loaded configuration (v2 format)",
                    "FilterMate",
                    Qgis.Info
                )
                return True
            
            # Fall back to v1 format - RESET to defaults with preserved settings
            v1_path = os.path.join(self.config_dir, self.CONFIG_FILE)
            if os.path.exists(v1_path):
                with open(v1_path, 'r', encoding='utf-8') as f:
                    v1_data = json.load(f)
                
                # Extract settings to preserve from old config
                preserved_values = self._extract_preserved_settings(v1_data)
                
                # Start fresh with default configuration
                self._data = get_default_config()
                
                # Restore preserved settings
                self._restore_preserved_settings(preserved_values)
                
                self._is_v2_format = True
                self._migrated_from_v1 = True
                
                # Save new config
                self.save()
                
                # Backup old config
                self._backup_old_config(v1_path)
                
                QgsMessageLog.logMessage(
                    "Old configuration detected. Reset to defaults with preserved settings (language, paths).",
                    "FilterMate",
                    Qgis.Info
                )
                return True
            
            # No config found, create default
            self._data = get_default_config()
            self._is_v2_format = True
            self.save()
            
            QgsMessageLog.logMessage(
                "Created default configuration",
                "FilterMate",
                Qgis.Info
            )
            return True
            
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error loading configuration: {e}",
                "FilterMate",
                Qgis.Critical
            )
            self._data = get_default_config()
            return False
    
    def _extract_preserved_settings(self, v1_data: Dict) -> Dict[str, Any]:
        """
        Extract settings to preserve from old v1 configuration.
        
        Args:
            v1_data: Old configuration data
        
        Returns:
            dict: Preserved settings with their values
        """
        preserved = {}
        
        try:
            app = v1_data.get('APP', {})
            dockwidget = app.get('DOCKWIDGET', {})
            options = app.get('OPTIONS', {})
            
            # Language
            if 'LANGUAGE' in dockwidget:
                lang = dockwidget['LANGUAGE']
                if isinstance(lang, dict) and 'value' in lang:
                    preserved[('GENERAL', 'LANGUAGE')] = lang['value']
                elif isinstance(lang, str):
                    preserved[('GENERAL', 'LANGUAGE')] = lang
            
            # SQLite path
            if 'APP_SQLITE_PATH' in options and options['APP_SQLITE_PATH']:
                preserved[('GENERAL', 'APP_SQLITE_PATH')] = options['APP_SQLITE_PATH']
            
            QgsMessageLog.logMessage(
                f"Preserved {len(preserved)} settings from old configuration",
                "FilterMate",
                Qgis.Info
            )
            
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error extracting preserved settings: {e}",
                "FilterMate",
                Qgis.Warning
            )
        
        return preserved
    
    def _restore_preserved_settings(self, preserved: Dict) -> None:
        """
        Restore preserved settings into the new configuration.
        
        Args:
            preserved: Dictionary of preserved settings
        """
        for keys, value in preserved.items():
            try:
                self.set(*keys, value)
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Error restoring setting {keys}: {e}",
                    "FilterMate",
                    Qgis.Warning
                )
    
    def _backup_old_config(self, v1_path: str) -> None:
        """
        Backup old v1 configuration file.
        
        Args:
            v1_path: Path to the old config file
        """
        try:
            import shutil
            from datetime import datetime
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = v1_path.replace('.json', f'.v1_backup_{timestamp}.json')
            shutil.copy2(v1_path, backup_path)
            
            QgsMessageLog.logMessage(
                f"Old configuration backed up to: {backup_path}",
                "FilterMate",
                Qgis.Info
            )
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Could not backup old configuration: {e}",
                "FilterMate",
                Qgis.Warning
            )
    
    def was_migrated_from_v1(self) -> bool:
        """
        Check if configuration was migrated from v1 during this session.
        
        Returns:
            bool: True if migration occurred
        """
        return self._migrated_from_v1
    
    def reset_to_defaults(self, preserve_user_settings: bool = True) -> bool:
        """
        Reset configuration to defaults.
        
        Args:
            preserve_user_settings: If True, preserve language and paths
        
        Returns:
            bool: True if reset successfully
        """
        try:
            preserved = {}
            
            if preserve_user_settings:
                # Extract current preserved settings
                for keys in self.PRESERVED_SETTINGS:
                    value = self.get(*keys)
                    if value is not None:
                        preserved[keys] = value
            
            # Reset to defaults
            self._data = get_default_config()
            
            # Restore preserved settings
            if preserved:
                self._restore_preserved_settings(preserved)
            
            self.save()
            
            QgsMessageLog.logMessage(
                f"Configuration reset to defaults (preserved {len(preserved)} settings)",
                "FilterMate",
                Qgis.Info
            )
            return True
            
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error resetting configuration: {e}",
                "FilterMate",
                Qgis.Critical
            )
            return False
    
    def save(self) -> bool:
        """
        Save configuration to file.
        
        Returns:
            bool: True if saved successfully
        """
        try:
            # Add schema version
            save_data = {"_schema_version": "2.0.0", **self._data}
            
            v2_path = os.path.join(self.config_dir, self.CONFIG_V2_FILE)
            with open(v2_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=4)
            
            return True
            
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error saving configuration: {e}",
                "FilterMate",
                Qgis.Critical
            )
            return False
    
    # =========================================================================
    # Value Access
    # =========================================================================
    
    def get(self, *keys: str, default: Any = None) -> Any:
        """
        Get a configuration value by path.
        
        Args:
            *keys: Path to the value (e.g., 'GENERAL', 'LANGUAGE')
            default: Default value if not found
        
        Returns:
            The configuration value or default
        
        Example:
            language = config.get('GENERAL', 'LANGUAGE')
            icon_size = config.get('UI', 'ICONS', 'SIZE_ACTION')
        """
        data = self._data
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key)
                if data is None:
                    return default
            else:
                return default
        
        # Handle both old format (direct value) and new format (value in dict)
        if isinstance(data, dict) and 'value' in data:
            return data['value']
        return data if data is not None else default
    
    def get_value(self, *keys: str, default: Any = None) -> Any:
        """Alias for get() for clarity."""
        return self.get(*keys, default=default)
    
    def set(self, *keys_and_value) -> bool:
        """
        Set a configuration value by path.
        
        Args:
            *keys_and_value: Path keys followed by the value
        
        Returns:
            bool: True if set successfully
        
        Example:
            config.set('GENERAL', 'LANGUAGE', 'fr')
            config.set('UI', 'ICONS', 'SIZE_ACTION', 30)
        """
        if len(keys_and_value) < 2:
            return False
        
        keys = keys_and_value[:-1]
        value = keys_and_value[-1]
        
        # Navigate to parent
        data = self._data
        for key in keys[:-1]:
            if key not in data:
                data[key] = {}
            data = data[key]
        
        final_key = keys[-1]
        
        # Handle new format with 'value' key
        if isinstance(data.get(final_key), dict) and 'type' in data.get(final_key, {}):
            data[final_key]['value'] = value
        else:
            data[final_key] = value
        
        return True
    
    def get_choices(self, *keys: str) -> List[str]:
        """
        Get available choices for a setting.
        
        Args:
            *keys: Path to the setting
        
        Returns:
            List of choices or empty list
        """
        data = self._data
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key)
            else:
                return []
        
        if isinstance(data, dict) and 'choices' in data:
            return data['choices']
        return []
    
    # =========================================================================
    # Feature Toggles
    # =========================================================================
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """
        Check if a feature is enabled.
        
        Args:
            feature_name: Name of the feature (e.g., 'ENABLE_UNDO_REDO')
        
        Returns:
            bool: True if feature is enabled
        """
        return self.get('FEATURES', feature_name, default=True)
    
    def get_enabled_features(self) -> Dict[str, bool]:
        """
        Get dictionary of all feature toggle states.
        
        Returns:
            dict: Feature name to enabled state mapping
        """
        features = {}
        features_section = self._data.get('FEATURES', {})
        
        for key, value in features_section.items():
            if key.startswith('_'):
                continue
            if isinstance(value, dict) and 'value' in value:
                features[key] = value['value']
            elif isinstance(value, bool):
                features[key] = value
        
        return features
    
    # =========================================================================
    # JSON View Integration
    # =========================================================================
    
    def get_json_view_settings(self) -> Dict[str, Any]:
        """
        Get settings for qt_json_view.
        
        Returns:
            dict: Settings for JsonView initialization
        """
        json_view = self._data.get('JSON_VIEW', {})
        
        def get_val(key, default):
            val = json_view.get(key, {})
            if isinstance(val, dict) and 'value' in val:
                return val['value']
            return default
        
        # Determine theme
        theme = get_val('THEME', 'auto')
        if theme == 'auto':
            ui_theme = self.get('UI', 'THEME', 'ACTIVE', default='default')
            theme = get_json_view_theme_for_ui_theme(ui_theme)
        
        return {
            'theme': theme,
            'font_size': get_val('FONT_SIZE', 9),
            'alternating_rows': get_val('SHOW_ALTERNATING_ROWS', True),
            'editable_keys': get_val('EDITABLE_KEYS', True),
            'editable_values': get_val('EDITABLE_VALUES', True),
            'column_width_key': get_val('COLUMN_WIDTH_KEY', 180),
            'column_width_value': get_val('COLUMN_WIDTH_VALUE', 240),
        }
    
    def get_json_view_theme(self) -> str:
        """
        Get the appropriate JSON View theme.
        
        Handles 'auto' mode by checking UI theme.
        
        Returns:
            str: Theme name for qt_json_view
        """
        settings = self.get_json_view_settings()
        return settings['theme']
    
    def sync_json_view_with_ui_theme(self) -> str:
        """
        Synchronize JSON View theme with current UI theme.
        
        Call this when UI theme changes.
        
        Returns:
            str: The new JSON View theme name
        """
        json_view_theme = self.get('JSON_VIEW', 'THEME', default='auto')
        
        if json_view_theme == 'auto':
            ui_theme = self.get('UI', 'THEME', 'ACTIVE', default='default')
            return get_json_view_theme_for_ui_theme(ui_theme)
        
        return json_view_theme
    
    # =========================================================================
    # UI Theme
    # =========================================================================
    
    def get_ui_theme(self) -> Dict[str, Any]:
        """
        Get the current UI theme colors.
        
        Returns:
            dict: Theme definition with BACKGROUND, FONT, ACCENT
        """
        theme_name = self.get('UI', 'THEME', 'ACTIVE', default='default')
        
        if theme_name == 'auto':
            # Detect from QGIS/system
            theme_name = self._detect_system_theme()
        
        themes = self._data.get('THEMES', UI_THEMES)
        return themes.get(theme_name, themes.get('default', UI_THEMES['default']))
    
    def _detect_system_theme(self) -> str:
        """
        Detect system theme (dark/light).
        
        Returns:
            str: 'dark' or 'light'
        """
        try:
            from qgis.core import QgsApplication
            from qgis.PyQt.QtGui import QPalette
            
            palette = QgsApplication.palette()
            bg_color = palette.color(QPalette.Window)
            
            # Dark theme if background is dark
            if bg_color.lightness() < 128:
                return 'dark'
            return 'light'
        except Exception:
            return 'default'
    
    # =========================================================================
    # Export Settings
    # =========================================================================
    
    def get_export_defaults(self) -> Dict[str, Any]:
        """
        Get default export settings.
        
        Returns:
            dict: Export configuration defaults
        """
        return {
            'format': self.get('EXPORT', 'DEFAULT_FORMAT', default='GPKG'),
            'crs': self.get('EXPORT', 'DEFAULT_CRS', default='EPSG:4326'),
            'style_format': self.get('EXPORT', 'STYLE_FORMAT', default='QML'),
            'last_folder': self.get('EXPORT', 'LAST_FOLDER', default=''),
            'remember_folder': self.get('EXPORT', 'REMEMBER_LAST_FOLDER', default=True),
        }
    
    def set_last_export_folder(self, folder: str) -> None:
        """
        Save the last export folder.
        
        Args:
            folder: Path to the export folder
        """
        if self.get('EXPORT', 'REMEMBER_LAST_FOLDER', default=True):
            self.set('EXPORT', 'LAST_FOLDER', folder)
            self.save()
    
    # =========================================================================
    # Backend Settings
    # =========================================================================
    
    def get_backend_settings(self) -> Dict[str, Any]:
        """
        Get backend configuration.
        
        Returns:
            dict: Backend settings
        """
        return {
            'preferred': self.get('BACKEND', 'PREFERRED_BACKEND', default='auto'),
            'use_materialized_views': self.get('BACKEND', 'USE_MATERIALIZED_VIEWS', default=True),
            'spatialite_temp_tables': self.get('BACKEND', 'SPATIALITE_TEMP_TABLES', default=True),
            'connection_timeout': self.get('BACKEND', 'CONNECTION_TIMEOUT', default=30),
        }
    
    # =========================================================================
    # Layer Settings
    # =========================================================================
    
    def get_layer_settings(self) -> Dict[str, Any]:
        """
        Get layer handling settings.
        
        Returns:
            dict: Layer settings
        """
        return {
            'link_legend': self.get('LAYERS', 'LINK_LEGEND_LAYERS', default=True),
            'properties_count': self.get('LAYERS', 'LAYER_PROPERTIES_COUNT', default=35),
            'feature_limit': self.get('LAYERS', 'FEATURE_COUNT_LIMIT', default=10000),
            'warning_threshold': self.get('LAYERS', 'FEATURE_COUNT_WARNING_THRESHOLD', default=50000),
        }
    
    # =========================================================================
    # Migration from V1
    # =========================================================================
    
    def _migrate_v1_to_v2(self, v1_data: Dict) -> Dict:
        """
        Migrate v1 configuration format to v2.
        
        Args:
            v1_data: Configuration in v1 format
        
        Returns:
            dict: Configuration in v2 format
        """
        v2_data = get_default_config()
        
        try:
            app = v1_data.get('APP', {})
            dockwidget = app.get('DOCKWIDGET', {})
            options = app.get('OPTIONS', {})
            current_project = v1_data.get('CURRENT_PROJECT', {})
            
            # GENERAL
            if 'LANGUAGE' in dockwidget:
                lang = dockwidget['LANGUAGE']
                v2_data['GENERAL']['LANGUAGE'] = {
                    'type': 'choices',
                    'choices': lang.get('choices', ['auto', 'en', 'fr']),
                    'value': lang.get('value', 'auto')
                }
            
            if 'FEEDBACK_LEVEL' in dockwidget:
                fb = dockwidget['FEEDBACK_LEVEL']
                v2_data['GENERAL']['FEEDBACK_LEVEL'] = {
                    'type': 'choices',
                    'choices': fb.get('choices', ['minimal', 'normal', 'verbose']),
                    'value': fb.get('value', 'normal')
                }
            
            if 'APP_SQLITE_PATH' in options:
                v2_data['GENERAL']['APP_SQLITE_PATH'] = {
                    'type': 'filepath',
                    'value': options['APP_SQLITE_PATH']
                }
            
            # UI
            if 'UI_PROFILE' in dockwidget:
                prof = dockwidget['UI_PROFILE']
                v2_data['UI']['PROFILE'] = {
                    'type': 'choices',
                    'choices': prof.get('choices', ['auto', 'compact', 'normal']),
                    'value': prof.get('value', 'auto')
                }
            
            if 'ACTION_BAR_POSITION' in dockwidget:
                pos = dockwidget['ACTION_BAR_POSITION']
                v2_data['UI']['ACTION_BAR'] = {
                    'POSITION': {
                        'type': 'choices',
                        'choices': pos.get('choices', ['top', 'bottom', 'left', 'right']),
                        'value': pos.get('value', 'left')
                    }
                }
            
            if 'ACTION_BAR_VERTICAL_ALIGNMENT' in dockwidget:
                align = dockwidget['ACTION_BAR_VERTICAL_ALIGNMENT']
                if 'ACTION_BAR' not in v2_data['UI']:
                    v2_data['UI']['ACTION_BAR'] = {}
                v2_data['UI']['ACTION_BAR']['VERTICAL_ALIGNMENT'] = {
                    'type': 'choices',
                    'choices': align.get('choices', ['top', 'bottom']),
                    'value': align.get('value', 'top')
                }
            
            # Icons sizes
            if 'PushButton' in dockwidget:
                pb = dockwidget['PushButton']
                if 'ICONS_SIZES' in pb:
                    sizes = pb['ICONS_SIZES']
                    v2_data['UI']['ICONS'] = {
                        'SIZE_ACTION': {
                            'type': 'range',
                            'min': 16,
                            'max': 48,
                            'value': sizes.get('ACTION', 25)
                        },
                        'SIZE_OTHERS': {
                            'type': 'range',
                            'min': 12,
                            'max': 32,
                            'value': sizes.get('OTHERS', 20)
                        }
                    }
            
            # COLORS/THEMES
            if 'COLORS' in dockwidget:
                colors = dockwidget['COLORS']
                if 'ACTIVE_THEME' in colors:
                    theme = colors['ACTIVE_THEME']
                    v2_data['UI']['THEME'] = {
                        'MODE': {
                            'type': 'choices',
                            'choices': ['auto', 'config', 'qgis', 'system'],
                            'value': colors.get('THEME_SOURCE', {}).get('value', 'auto')
                        },
                        'ACTIVE': {
                            'type': 'choices',
                            'choices': theme.get('choices', ['auto', 'default', 'dark', 'light']),
                            'value': theme.get('value', 'auto')
                        }
                    }
                
                if 'THEMES' in colors:
                    v2_data['THEMES'] = colors['THEMES']
            
            # LAYERS
            if 'OPTIONS' in current_project:
                proj_opts = current_project['OPTIONS']
                if 'LAYERS' in proj_opts:
                    layers = proj_opts['LAYERS']
                    v2_data['LAYERS'] = {
                        'LINK_LEGEND_LAYERS': {
                            'type': 'boolean',
                            'value': layers.get('LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG', True)
                        },
                        'LAYER_PROPERTIES_COUNT': {
                            'type': 'range',
                            'min': 10,
                            'max': 100,
                            'value': layers.get('LAYER_PROPERTIES_COUNT', 35)
                        },
                        'FEATURE_COUNT_LIMIT': {
                            'type': 'range',
                            'min': 1000,
                            'max': 100000,
                            'value': layers.get('FEATURE_COUNT_LIMIT', 10000)
                        }
                    }
            
            # EXPORT
            if 'EXPORTING' in current_project:
                exp = current_project['EXPORTING']
                v2_data['EXPORT'] = {
                    'DEFAULT_FORMAT': {
                        'type': 'choices',
                        'choices': ['GPKG', 'SHP', 'GeoJSON', 'CSV', 'KML'],
                        'value': exp.get('DATATYPE_TO_EXPORT', 'GPKG')
                    },
                    'DEFAULT_CRS': {
                        'type': 'string',
                        'value': exp.get('PROJECTION_TO_EXPORT', 'EPSG:4326')
                    },
                    'STYLE_FORMAT': {
                        'type': 'choices',
                        'choices': ['QML', 'SLD', 'None'],
                        'value': exp.get('STYLES_TO_EXPORT', 'QML')
                    },
                    'LAST_FOLDER': {
                        'type': 'filepath',
                        'value': exp.get('OUTPUT_FOLDER_TO_EXPORT', ''),
                        'hidden': True
                    }
                }
            
            # LINKS
            v2_data['LINKS'] = {
                'GITHUB_PAGE': {
                    'type': 'url',
                    'value': options.get('GITHUB_PAGE', 'https://sducournau.github.io/filter_mate/')
                },
                'GITHUB_REPOSITORY': {
                    'type': 'url',
                    'value': options.get('GITHUB_REPOSITORY', 'https://github.com/sducournau/filter_mate/')
                },
                'QGIS_PLUGIN_REPOSITORY': {
                    'type': 'url',
                    'value': options.get('QGIS_PLUGIN_REPOSITORY', 'https://plugins.qgis.org/plugins/filter_mate/')
                }
            }
            
            # ADVANCED
            if 'FRESH_RELOAD_FLAG' in options:
                v2_data['ADVANCED']['FRESH_RELOAD_FLAG'] = {
                    'type': 'boolean',
                    'value': options['FRESH_RELOAD_FLAG'],
                    'hidden': True
                }
            
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error during config migration: {e}",
                "FilterMate",
                Qgis.Warning
            )
        
        return v2_data
    
    # =========================================================================
    # Raw Access (for compatibility)
    # =========================================================================
    
    @property
    def data(self) -> Dict[str, Any]:
        """Get raw configuration data (for compatibility)."""
        return self._data
    
    def get_raw(self) -> Dict[str, Any]:
        """Get raw configuration data."""
        return self._data
    
    def set_raw(self, data: Dict[str, Any]) -> None:
        """Set raw configuration data."""
        self._data = data


# =============================================================================
# Utility Functions
# =============================================================================

def create_config_manager(plugin_dir: str) -> ConfigManager:
    """
    Factory function to create a ConfigManager instance.
    
    Args:
        plugin_dir: Path to the plugin directory
    
    Returns:
        ConfigManager instance
    """
    return ConfigManager(plugin_dir)

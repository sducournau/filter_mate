"""
Configuration Migration Module for FilterMate

Handles automatic migration of configuration files from older versions
to the latest structure.

Features:
- Automatic version detection
- Step-by-step migration path
- Backup of old configuration
- Validation of migrated data
- Rollback capability

Author: FilterMate Team
Date: December 2025
"""

import json
import os
import shutil
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path


class ConfigMigration:
    """
    Manages configuration migrations between versions.
    """
    
    # Version definitions
    VERSION_UNKNOWN = "unknown"
    VERSION_1_0 = "1.0"  # Original structure with APP.DOCKWIDGET
    VERSION_2_0 = "2.0"  # New structure with app.ui
    
    # Current target version
    CURRENT_VERSION = VERSION_2_0
    MINIMUM_SUPPORTED_VERSION = VERSION_1_0  # Versions older than this will be reset
    
    def __init__(self, config_path: Optional[str] = None, default_config_path: Optional[str] = None):
        """
        Initialize configuration migration.
        
        Args:
            config_path: Path to config.json. If None, uses default location.
            default_config_path: Path to config.default.json. If None, looks in same directory as config_path.
        """
        if config_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, "..", "config", "config.json")
        
        self.config_path = os.path.abspath(config_path)
        self.config_dir = os.path.dirname(self.config_path)
        self.backup_dir = os.path.join(self.config_dir, "backups")
        
        # Store path to default config (may be in different directory than config.json)
        if default_config_path is None:
            self.default_config_path = os.path.join(self.config_dir, "config.default.json")
        else:
            self.default_config_path = os.path.abspath(default_config_path)
        
        # Ensure backup directory exists
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def detect_version(self, config_data: Dict[str, Any]) -> str:
        """
        Detect the version of a configuration dictionary.
        
        Args:
            config_data: Configuration dictionary
        
        Returns:
            Version string (e.g., "1.0", "2.0")
        """
        # Check for explicit version markers (new format)
        if "_CONFIG_VERSION" in config_data:
            return config_data["_CONFIG_VERSION"]
        
        if "_schema_version" in config_data:
            return config_data["_schema_version"]
        
        # Detect by structure
        if "APP" in config_data and isinstance(config_data.get("APP"), dict):
            if "DOCKWIDGET" in config_data["APP"]:
                return self.VERSION_1_0
        
        if "app" in config_data and isinstance(config_data.get("app"), dict):
            if "ui" in config_data["app"]:
                return self.VERSION_2_0
        
        return self.VERSION_UNKNOWN
    
    def is_obsolete(self, config_data: Dict[str, Any]) -> bool:
        """
        Check if configuration is too old and should be reset.
        
        Args:
            config_data: Configuration dictionary
        
        Returns:
            True if configuration should be reset to default
        """
        version = self.detect_version(config_data)
        
        # Unknown or corrupted configs should be reset
        if version == self.VERSION_UNKNOWN:
            return True
        
        # Check if version is older than minimum supported
        # For now, only VERSION_1_0 and VERSION_2_0 are supported
        # If we detect something else or a malformed config, reset
        if version not in [self.VERSION_1_0, self.VERSION_2_0]:
            return True
        
        return False
    
    def needs_migration(self, config_data: Dict[str, Any]) -> bool:
        """
        Check if configuration needs migration.
        
        Args:
            config_data: Configuration dictionary
        
        Returns:
            True if migration is needed
        """
        current_version = self.detect_version(config_data)
        return current_version != self.CURRENT_VERSION
    
    def create_backup(self, config_data: Dict[str, Any]) -> str:
        """
        Create a backup of the current configuration.
        
        Args:
            config_data: Configuration to backup
        
        Returns:
            Path to backup file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        version = self.detect_version(config_data)
        backup_filename = f"config_backup_v{version}_{timestamp}.json"
        backup_path = os.path.join(self.backup_dir, backup_filename)
        
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Backup created: {backup_path}")
        return backup_path

    def reset_to_default(self, reason: str = "obsolete", config_data: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        Reset configuration to default, creating a backup first.
        
        Args:
            reason: Reason for reset (for backup naming)
            config_data: Optional current config to backup (if None, will load from file)
        
        Returns:
            Tuple of (success, message)
        """
        # Create backup of current config
        if config_data is not None:
            backup_path = self.create_backup(config_data)
        elif os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    current_config = json.load(f)
                backup_path = self.create_backup(current_config)
            except (json.JSONDecodeError, OSError, IOError) as e:
                # Config file is corrupted or unreadable, continue without backup
                backup_path = None
        else:
            backup_path = None
        
        # Path to default config (stored during __init__)
        default_config_path = self.default_config_path
        
        if not os.path.exists(default_config_path):
            return False, f"Default configuration not found: {default_config_path}"
        
        try:
            # Copy default config to config.json
            shutil.copy2(default_config_path, self.config_path)
            msg = f"Configuration reset to default (reason: {reason})"
            if backup_path:
                msg += f". Backup created: {backup_path}"
            return True, msg
        except Exception as e:
            return False, f"Failed to reset configuration: {e}"
    
    def migrate_1_0_to_2_0(self, config_v1: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migrate configuration from version 1.0 to 2.0.
        
        Args:
            config_v1: Configuration in v1 format
        
        Returns:
            Configuration in v2 format
        """
        config_v2 = {
            "_schema_version": self.VERSION_2_0,
            "_migrated_from": self.VERSION_1_0,
            "_migration_date": datetime.now().isoformat(),
            "app": {}
        }
        
        # Migrate APP.AUTO_ACTIVATE -> app.auto_activate
        if "APP" in config_v1 and "AUTO_ACTIVATE" in config_v1["APP"]:
            auto_activate = config_v1["APP"]["AUTO_ACTIVATE"]
            if isinstance(auto_activate, dict) and "value" in auto_activate:
                config_v2["app"]["auto_activate"] = {
                    "value": auto_activate["value"],
                    "choices": [True, False]
                }
            else:
                config_v2["app"]["auto_activate"] = {
                    "value": auto_activate,
                    "choices": [True, False]
                }
        
        # Migrate UI settings
        config_v2["app"]["ui"] = {}
        
        # APP.DOCKWIDGET.FEEDBACK_LEVEL -> app.ui.feedback.level
        if "APP" in config_v1 and "DOCKWIDGET" in config_v1["APP"]:
            dockwidget = config_v1["APP"]["DOCKWIDGET"]
            
            if "FEEDBACK_LEVEL" in dockwidget:
                config_v2["app"]["ui"]["feedback"] = {
                    "level": self._extract_value(dockwidget["FEEDBACK_LEVEL"])
                }
            
            # APP.DOCKWIDGET.LANGUAGE -> app.ui.language
            if "LANGUAGE" in dockwidget:
                config_v2["app"]["ui"]["language"] = self._extract_value(dockwidget["LANGUAGE"])
            
            # APP.DOCKWIDGET.UI_PROFILE -> app.ui.profile
            if "UI_PROFILE" in dockwidget:
                config_v2["app"]["ui"]["profile"] = self._extract_value(dockwidget["UI_PROFILE"])
            
            # APP.DOCKWIDGET.ACTION_BAR -> app.ui.action_bar
            if "ACTION_BAR" in dockwidget:
                action_bar = dockwidget["ACTION_BAR"]
                config_v2["app"]["ui"]["action_bar"] = {}
                
                if "POSITION" in action_bar:
                    config_v2["app"]["ui"]["action_bar"]["position"] = self._extract_value(action_bar["POSITION"])
                
                if "VERTICAL_ALIGNMENT" in action_bar:
                    config_v2["app"]["ui"]["action_bar"]["vertical_alignment"] = self._extract_value(action_bar["VERTICAL_ALIGNMENT"])
            
            # APP.DOCKWIDGET.COLORS -> app.ui.theme and app.themes
            if "COLORS" in dockwidget:
                colors = dockwidget["COLORS"]
                
                config_v2["app"]["ui"]["theme"] = {}
                
                if "ACTIVE_THEME" in colors:
                    config_v2["app"]["ui"]["theme"]["active"] = self._extract_value(colors["ACTIVE_THEME"])
                
                if "THEME_SOURCE" in colors:
                    config_v2["app"]["ui"]["theme"]["source"] = self._extract_value(colors["THEME_SOURCE"])
                
                # Migrate theme definitions
                if "THEMES" in colors:
                    config_v2["app"]["themes"] = colors["THEMES"]
        
        # Migrate button configuration
        if "APP" in config_v1 and "DOCKWIDGET" in config_v1["APP"]:
            dockwidget = config_v1["APP"]["DOCKWIDGET"]
            
            if "BUTTONS" in dockwidget:
                buttons = dockwidget["BUTTONS"]
                config_v2["app"]["buttons"] = {}
                
                # Button style
                if "STYLE" in buttons:
                    config_v2["app"]["buttons"]["style"] = buttons["STYLE"]
                
                # Icon sizes
                if "ICON_SIZE" in buttons:
                    icon_sizes = buttons["ICON_SIZE"]
                    config_v2["app"]["buttons"]["icon_sizes"] = {}
                    
                    if "ACTION_BUTTONS" in icon_sizes:
                        config_v2["app"]["buttons"]["icon_sizes"]["action"] = icon_sizes["ACTION_BUTTONS"]
                    
                    if "OTHERS" in icon_sizes:
                        config_v2["app"]["buttons"]["icon_sizes"]["others"] = icon_sizes["OTHERS"]
                
                # Icons
                if "ICONS" in buttons:
                    config_v2["app"]["buttons"]["icons"] = buttons["ICONS"]
        
        # Migrate export configuration
        config_v2["app"]["export"] = {}
        
        if "APP" in config_v1 and "DOCKWIDGET" in config_v1["APP"]:
            dockwidget = config_v1["APP"]["DOCKWIDGET"]
            
            if "EXPORT" in dockwidget:
                export = dockwidget["EXPORT"]
                
                # Style format
                if "STYLE" in export:
                    config_v2["app"]["export"]["style"] = {
                        "format": self._extract_value(export["STYLE"])
                    }
                
                # Data format
                if "DATA_FORMAT" in export:
                    config_v2["app"]["export"]["data"] = {
                        "format": self._extract_value(export["DATA_FORMAT"])
                    }
                
                # Layers enabled
                if "LAYERS_ENABLED" in export:
                    config_v2["app"]["export"]["layers_enabled"] = self._extract_value(export["LAYERS_ENABLED"])
                
                # Projection
                if "PROJECTION_ENABLED" in export:
                    config_v2["app"]["export"]["projection_enabled"] = self._extract_value(export["PROJECTION_ENABLED"])
                
                if "PROJECTION_EPSG" in export:
                    config_v2["app"]["export"]["projection_epsg"] = self._extract_value(export["PROJECTION_EPSG"])
        
        # Migrate project configuration
        config_v2["app"]["project"] = {}
        
        if "CURRENT_PROJECT" in config_v1:
            current_project = config_v1["CURRENT_PROJECT"]
            
            if "OPTIONS" in current_project:
                options = current_project["OPTIONS"]
                
                # Feature count limit
                if "FEATURE_COUNT_LIMIT" in options:
                    config_v2["app"]["project"]["feature_count_limit"] = options["FEATURE_COUNT_LIMIT"]
                
                # Layer properties count
                if "LAYER_PROPERTIES_COUNT" in options:
                    config_v2["app"]["project"]["layer_properties_count"] = options["LAYER_PROPERTIES_COUNT"]
                
                # Link legend layers
                if "LAYERS" in options and "LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG" in options["LAYERS"]:
                    config_v2["app"]["project"]["link_legend_layers"] = options["LAYERS"]["LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"]
        
        return config_v2
    
    def _extract_value(self, data: Any) -> Any:
        """
        Extract value from ChoicesType format or return as-is.
        
        Args:
            data: Data that might be in ChoicesType format
        
        Returns:
            Extracted value
        """
        if isinstance(data, dict):
            if "value" in data and "choices" in data:
                return {
                    "value": data["value"],
                    "choices": data["choices"]
                }
            elif "value" in data:
                return data["value"]
        
        return data
    
    def migrate(self, config_data: Dict[str, Any], 
                create_backup: bool = True,
                validate: bool = True) -> Tuple[Dict[str, Any], List[str]]:
        """
        Migrate configuration to the latest version.
        
        Args:
            config_data: Configuration to migrate
            create_backup: Whether to create a backup before migration
            validate: Whether to validate after migration
        
        Returns:
            Tuple of (migrated_config, list_of_warnings)
        """
        warnings = []
        current_version = self.detect_version(config_data)
        
        if current_version == self.CURRENT_VERSION:
            warnings.append(f"Configuration is already at version {self.CURRENT_VERSION}")
            return config_data, warnings
        
        if current_version == self.VERSION_UNKNOWN:
            warnings.append("Cannot detect configuration version - migration may fail")
        
        # Create backup
        if create_backup:
            try:
                self.create_backup(config_data)
            except Exception as e:
                warnings.append(f"Failed to create backup: {e}")
        
        # Perform migration
        migrated = config_data
        
        if current_version == self.VERSION_1_0:
            print(f"Migrating from v{self.VERSION_1_0} to v{self.CURRENT_VERSION}...")
            migrated = self.migrate_1_0_to_2_0(config_data)
            print("✓ Migration completed")
        else:
            warnings.append(f"No migration path from version {current_version} to {self.CURRENT_VERSION}")
            return config_data, warnings
        
        # Validate
        if validate:
            validation_warnings = self.validate_migrated_config(migrated)
            warnings.extend(validation_warnings)
        
        return migrated, warnings
    
    def validate_migrated_config(self, config_data: Dict[str, Any]) -> List[str]:
        """
        Validate a migrated configuration.
        
        Args:
            config_data: Configuration to validate
        
        Returns:
            List of validation warnings
        """
        warnings = []
        
        # Check required structure
        if "app" not in config_data:
            warnings.append("Missing 'app' root key in migrated config")
            return warnings
        
        # Check for essential sections
        essential_sections = ["ui", "buttons", "export", "project"]
        for section in essential_sections:
            if section not in config_data["app"]:
                warnings.append(f"Missing 'app.{section}' section in migrated config")
        
        # Validate using metadata if available
        try:
            from .config_metadata import get_config_metadata
            from .config_helpers import validate_config_value_with_metadata, get_all_configurable_paths
            
            metadata = get_config_metadata()
            all_paths = get_all_configurable_paths()
            
            # Check each configured value
            def validate_recursive(data, path="app"):
                if isinstance(data, dict):
                    for key, value in data.items():
                        if key.startswith("_"):
                            continue  # Skip metadata keys
                        
                        current_path = f"{path}.{key}"
                        
                        # If this is a leaf value (has 'value' key or is a final value)
                        if isinstance(value, dict) and "value" in value:
                            actual_value = value["value"]
                            valid, error = validate_config_value_with_metadata(current_path, actual_value)
                            if not valid:
                                warnings.append(f"Invalid value at {current_path}: {error}")
                        else:
                            validate_recursive(value, current_path)
            
            validate_recursive(config_data["app"])
            
        except ImportError:
            warnings.append("Metadata module not available - skipping detailed validation")
        except Exception as e:
            warnings.append(f"Validation error: {e}")
        
        return warnings
    
    def save_migrated_config(self, config_data: Dict[str, Any]) -> bool:
        """
        Save migrated configuration to file.
        
        Args:
            config_data: Configuration to save
        
        Returns:
            True if successful
        """
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            print(f"✓ Configuration saved to {self.config_path}")
            return True
        except Exception as e:
            print(f"✗ Failed to save configuration: {e}")
            return False
    
    def rollback_to_backup(self, backup_path: str) -> bool:
        """
        Rollback configuration to a backup file.
        
        Args:
            backup_path: Path to backup file
        
        Returns:
            True if successful
        """
        try:
            shutil.copy2(backup_path, self.config_path)
            print(f"✓ Configuration rolled back from {backup_path}")
            return True
        except Exception as e:
            print(f"✗ Failed to rollback: {e}")
            return False
    
    def list_backups(self) -> List[Dict[str, str]]:
        """
        List all available backup files.
        
        Returns:
            List of backup info dictionaries with 'path', 'date', 'version'
        """
        backups = []
        
        if not os.path.exists(self.backup_dir):
            return backups
        
        for filename in os.listdir(self.backup_dir):
            if filename.startswith("config_backup_") and filename.endswith(".json"):
                backup_path = os.path.join(self.backup_dir, filename)
                stat = os.stat(backup_path)
                
                # Parse version from filename
                version = "unknown"
                if "_v" in filename:
                    version_part = filename.split("_v")[1].split("_")[0]
                    version = version_part
                
                backups.append({
                    "path": backup_path,
                    "filename": filename,
                    "date": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "version": version,
                    "size": stat.st_size
                })
        
        # Sort by date (newest first)
        backups.sort(key=lambda x: x["date"], reverse=True)
        
        return backups
    
    def check_config_status(self) -> Tuple[str, Optional[str], Optional[Dict[str, Any]]]:
        """
        Check the current configuration status without performing any changes.
        
        Returns:
            Tuple of (status, version, config_data)
            status: 'ok', 'missing', 'corrupted', 'obsolete', 'needs_migration'
            version: detected version (or None if corrupted/missing)
            config_data: loaded config (or None if corrupted/missing)
        """
        if not os.path.exists(self.config_path):
            return 'missing', None, None
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        except Exception:
            return 'corrupted', None, None
        
        version = self.detect_version(config_data)
        
        if self.is_obsolete(config_data):
            return 'obsolete', version, config_data
        
        if self.needs_migration(config_data):
            return 'needs_migration', version, config_data
        
        return 'ok', version, config_data
    
    def update_ui_profile_options(self) -> Tuple[bool, str]:
        """
        Update UI_PROFILE choices and auto_detection_thresholds in config.json
        to include the 'hidpi' option if missing.
        
        This ensures user configs are automatically updated when new profile
        options are added without requiring a full migration.
        
        Returns:
            Tuple of (updated, message)
        """
        if not os.path.exists(self.config_path):
            return False, "Config file not found"
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        except Exception as e:
            return False, f"Failed to load config: {e}"
        
        updated = False
        
        # Navigate to UI_PROFILE in APP.DOCKWIDGET structure
        ui_profile = None
        if "APP" in config_data and "DOCKWIDGET" in config_data["APP"]:
            ui_profile = config_data["APP"]["DOCKWIDGET"].get("UI_PROFILE")
        
        if ui_profile is None:
            return False, "UI_PROFILE not found in config"
        
        # Update choices if 'hidpi' is missing
        if "choices" in ui_profile:
            if "hidpi" not in ui_profile["choices"]:
                ui_profile["choices"] = ["auto", "compact", "normal", "hidpi"]
                updated = True
        
        # Update description
        expected_description = "UI display profile: 'auto' (detect from screen/DPI), 'compact' for small screens, 'normal' for standard displays, 'hidpi' for high resolution displays (4K, Retina)"
        if ui_profile.get("description") != expected_description:
            ui_profile["description"] = expected_description
            updated = True
        
        # Update auto_detection_thresholds
        if "auto_detection_thresholds" in ui_profile:
            thresholds = ui_profile["auto_detection_thresholds"]
            if "hidpi_if_device_pixel_ratio_above" not in thresholds:
                thresholds["hidpi_if_device_pixel_ratio_above"] = 1.5
                updated = True
            if "hidpi_if_physical_width_above" not in thresholds:
                thresholds["hidpi_if_physical_width_above"] = 3840
                updated = True
        else:
            # Add complete thresholds if missing
            ui_profile["auto_detection_thresholds"] = {
                "compact_if_width_less_than": 1920,
                "compact_if_height_less_than": 1080,
                "hidpi_if_device_pixel_ratio_above": 1.5,
                "hidpi_if_physical_width_above": 3840
            }
            updated = True
        
        if updated:
            try:
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, indent=2, ensure_ascii=False)
                return True, "UI_PROFILE options updated successfully"
            except Exception as e:
                return False, f"Failed to save config: {e}"
        
        return False, "No updates needed"

    def update_settings_sections(self) -> Tuple[bool, str, List[str]]:
        """
        Update SETTINGS sections in config.json to add new configurable parameters
        like GEOMETRY_SIMPLIFICATION and OPTIMIZATION_THRESHOLDS if missing.
        
        This ensures user configs are automatically updated when new settings
        sections are added without requiring a full migration.
        
        Returns:
            Tuple of (updated, message, list_of_added_sections)
        """
        if not os.path.exists(self.config_path):
            return False, "Config file not found", []
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        except Exception as e:
            return False, f"Failed to load config: {e}", []
        
        updated = False
        added_sections = []
        
        # Ensure APP.SETTINGS exists
        if "APP" not in config_data:
            config_data["APP"] = {}
        if "SETTINGS" not in config_data["APP"]:
            config_data["APP"]["SETTINGS"] = {}
        
        settings = config_data["APP"]["SETTINGS"]
        
        # Add GEOMETRY_SIMPLIFICATION if missing
        if "GEOMETRY_SIMPLIFICATION" not in settings:
            settings["GEOMETRY_SIMPLIFICATION"] = {
                "description": "Geometry simplification settings for large WKT expressions",
                "enabled": {
                    "value": True,
                    "choices": [True, False],
                    "description": "Enable automatic geometry simplification for large WKT expressions"
                },
                "max_wkt_length": {
                    "value": 100000,
                    "min": 10000,
                    "max": 1000000,
                    "description": "Maximum WKT string length (chars) before simplification is applied"
                },
                "preserve_topology": {
                    "value": True,
                    "choices": [True, False],
                    "description": "Preserve geometry topology during simplification (prevents self-intersections)"
                },
                "min_tolerance_meters": {
                    "value": 1.0,
                    "min": 0.1,
                    "max": 100.0,
                    "description": "Minimum simplification tolerance in meters"
                },
                "max_tolerance_meters": {
                    "value": 100.0,
                    "min": 10.0,
                    "max": 1000.0,
                    "description": "Maximum simplification tolerance in meters (prevents excessive distortion)"
                },
                "show_simplification_warnings": {
                    "value": True,
                    "choices": [True, False],
                    "description": "Show warning messages when geometry is simplified"
                }
            }
            updated = True
            added_sections.append("GEOMETRY_SIMPLIFICATION")
        
        # Add OPTIMIZATION_THRESHOLDS if missing
        if "OPTIMIZATION_THRESHOLDS" not in settings:
            settings["OPTIMIZATION_THRESHOLDS"] = {
                "description": "Thresholds for automatic optimizations (feature counts and sizes)",
                "large_dataset_warning": {
                    "value": 50000,
                    "min": 0,
                    "max": 1000000,
                    "description": "Feature count above which performance warnings are displayed (0 to disable)"
                },
                "async_expression_threshold": {
                    "value": 10000,
                    "min": 1000,
                    "max": 500000,
                    "description": "Feature count above which expression evaluation runs in background thread"
                },
                "update_extents_threshold": {
                    "value": 50000,
                    "min": 1000,
                    "max": 500000,
                    "description": "Feature count below which layer extents are automatically updated after filtering"
                },
                "centroid_optimization_threshold": {
                    "value": 5000,
                    "min": 1000,
                    "max": 100000,
                    "description": "Feature count above which centroid optimization is applied for distant layers"
                },
                "exists_subquery_threshold": {
                    "value": 100000,
                    "min": 10000,
                    "max": 1000000,
                    "description": "WKT length (chars) above which EXISTS subquery mode is used instead of inline WKT"
                },
                "parallel_processing_threshold": {
                    "value": 100000,
                    "min": 10000,
                    "max": 1000000,
                    "description": "Feature count above which parallel processing is enabled"
                },
                "progress_update_batch_size": {
                    "value": 100,
                    "min": 10,
                    "max": 1000,
                    "description": "Number of features between progress bar updates (higher = faster but less responsive)"
                }
            }
            updated = True
            added_sections.append("OPTIMIZATION_THRESHOLDS")
        
        if updated:
            try:
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, indent=2, ensure_ascii=False)
                return True, "Settings sections updated successfully", added_sections
            except Exception as e:
                return False, f"Failed to save config: {e}", []
        
        return False, "No updates needed", []

    def auto_migrate_if_needed(self, confirm_reset_callback: Optional[callable] = None) -> Tuple[bool, List[str]]:
        """
        Automatically detect and migrate configuration if needed.
        Resets to default if configuration is obsolete or corrupted.
        
        Args:
            confirm_reset_callback: Optional callback function that takes (reason, version) 
                and returns True if user confirms reset, False otherwise.
                If None, reset is performed automatically.
        
        Returns:
            Tuple of (migration_performed_or_reset, list_of_warnings)
        """
        warnings = []
        
        # Load current config
        if not os.path.exists(self.config_path):
            warnings.append(f"Configuration file not found: {self.config_path}")
            # Try to copy default
            success, msg = self.reset_to_default(reason="missing")
            if success:
                print(f"✓ {msg}")
                return True, warnings
            else:
                warnings.append(msg)
                return False, warnings
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        except Exception as e:
            warnings.append(f"Failed to load configuration: {e}")
            # Config is corrupted - ask user for confirmation if callback provided
            if confirm_reset_callback is not None:
                if not confirm_reset_callback("corrupted", None):
                    warnings.append("User declined reset of corrupted configuration")
                    return False, warnings
            
            success, msg = self.reset_to_default(reason="corrupted")
            if success:
                print(f"✓ Configuration was corrupted. {msg}")
                return True, warnings
            else:
                warnings.append(msg)
                return False, warnings
        
        # Check if config is obsolete
        if self.is_obsolete(config_data):
            current_version = self.detect_version(config_data)
            print(f"⚠ Configuration version {current_version} is obsolete or unknown")
            
            # Ask user for confirmation if callback provided
            if confirm_reset_callback is not None:
                if not confirm_reset_callback("obsolete", current_version):
                    warnings.append("User declined reset of obsolete configuration")
                    return False, warnings
            
            success, msg = self.reset_to_default(reason="obsolete", config_data=config_data)
            if success:
                print(f"✓ {msg}")
                return True, warnings
            else:
                warnings.append(msg)
                return False, warnings
        
        # Check if migration is needed
        if not self.needs_migration(config_data):
            print(f"✓ Configuration is up to date (v{self.CURRENT_VERSION})")
            any_updated = False
            
            # Still check for UI_PROFILE updates (new options like hidpi)
            updated, update_msg = self.update_ui_profile_options()
            if updated:
                print(f"✓ {update_msg}")
                any_updated = True
            
            # Check for new SETTINGS sections (v2.7.6+)
            settings_updated, settings_msg, added_sections = self.update_settings_sections()
            if settings_updated:
                print(f"✓ {settings_msg}: {', '.join(added_sections)}")
                warnings.append(f"config_updated:{','.join(added_sections)}")
                any_updated = True
            
            return any_updated, warnings
        
        current_version = self.detect_version(config_data)
        print(f"⚠ Configuration needs migration from v{current_version} to v{self.CURRENT_VERSION}")
        
        # Perform migration
        migrated, migration_warnings = self.migrate(config_data)
        warnings.extend(migration_warnings)
        
        if migration_warnings:
            print("\nMigration warnings:")
            for warning in migration_warnings:
                print(f"  ⚠ {warning}")
        
        # Save migrated config
        if self.save_migrated_config(migrated):
            print("\n✓ Configuration successfully migrated!")
            return True, warnings
        else:
            warnings.append("Failed to save migrated configuration")
            return False, warnings


def migrate_config_file(config_path: Optional[str] = None) -> bool:
    """
    Convenience function to migrate a configuration file.
    
    Args:
        config_path: Path to config file, or None for default
    
    Returns:
        True if migration was successful or not needed
    """
    migrator = ConfigMigration(config_path)
    performed, warnings = migrator.auto_migrate_if_needed()
    
    if warnings:
        print("\nWarnings encountered:")
        for warning in warnings:
            print(f"  ⚠ {warning}")
    
    return performed or len([w for w in warnings if "up to date" in w]) > 0


def main():
    """Command-line interface for configuration migration."""
    import sys
    
    print("FilterMate Configuration Migration Tool")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        config_path = None
    
    migrator = ConfigMigration(config_path)
    
    # Show current status
    if os.path.exists(migrator.config_path):
        with open(migrator.config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        version = migrator.detect_version(config_data)
        print(f"\nCurrent configuration version: {version}")
        print(f"Target version: {migrator.CURRENT_VERSION}")
        
        if migrator.needs_migration(config_data):
            print("\n⚠ Migration required")
            response = input("\nProceed with migration? (y/n): ")
            
            if response.lower() == 'y':
                performed, warnings = migrator.auto_migrate_if_needed()
                
                if performed:
                    print("\n✓ Migration completed successfully!")
                    
                    # Show backup info
                    backups = migrator.list_backups()
                    if backups:
                        print(f"\nBackup created: {backups[0]['filename']}")
                else:
                    print("\n✗ Migration failed")
                    sys.exit(1)
            else:
                print("\nMigration cancelled")
        else:
            print("\n✓ No migration needed")
    else:
        print(f"\n✗ Configuration file not found: {migrator.config_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()

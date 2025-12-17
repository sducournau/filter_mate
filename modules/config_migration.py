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
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration migration.
        
        Args:
            config_path: Path to config.json. If None, uses default location.
        """
        if config_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, "..", "config", "config.json")
        
        self.config_path = os.path.abspath(config_path)
        self.config_dir = os.path.dirname(self.config_path)
        self.backup_dir = os.path.join(self.config_dir, "backups")
        
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
        # Check for explicit version marker
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
    
    def auto_migrate_if_needed(self) -> Tuple[bool, List[str]]:
        """
        Automatically detect and migrate configuration if needed.
        
        Returns:
            Tuple of (migration_performed, list_of_warnings)
        """
        warnings = []
        
        # Load current config
        if not os.path.exists(self.config_path):
            warnings.append(f"Configuration file not found: {self.config_path}")
            return False, warnings
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        except Exception as e:
            warnings.append(f"Failed to load configuration: {e}")
            return False, warnings
        
        # Check if migration is needed
        if not self.needs_migration(config_data):
            print(f"✓ Configuration is up to date (v{self.CURRENT_VERSION})")
            return False, warnings
        
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

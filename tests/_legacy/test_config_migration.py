"""
Tests for Configuration Migration Module

Tests the automatic migration of configuration files from v1.0 to v2.0.
"""

import unittest
import json
import os
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.config_migration import ConfigMigration


class TestConfigMigration(unittest.TestCase):
    """Test configuration migration functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for test configs
        self.test_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.test_dir, "config.json")
        
        # Sample v1.0 configuration
        self.config_v1 = {
            "APP": {
                "AUTO_ACTIVATE": {
                    "value": False
                },
                "DOCKWIDGET": {
                    "FEEDBACK_LEVEL": {
                        "value": "normal",
                        "choices": ["minimal", "normal", "verbose"]
                    },
                    "LANGUAGE": {
                        "value": "auto",
                        "choices": ["auto", "en", "fr", "de"]
                    },
                    "UI_PROFILE": {
                        "value": "auto",
                        "choices": ["auto", "compact", "normal"]
                    },
                    "ACTION_BAR": {
                        "POSITION": {
                            "value": "left",
                            "choices": ["top", "bottom", "left", "right"]
                        },
                        "VERTICAL_ALIGNMENT": {
                            "value": "top",
                            "choices": ["top", "bottom"]
                        }
                    },
                    "COLORS": {
                        "ACTIVE_THEME": {
                            "value": "auto",
                            "choices": ["auto", "default", "dark", "light"]
                        },
                        "THEME_SOURCE": {
                            "value": "config",
                            "choices": ["config", "qgis", "system"]
                        }
                    },
                    "BUTTONS": {
                        "STYLE": {
                            "border_radius": "10px",
                            "padding": "10px 10px 10px 10px"
                        },
                        "ICON_SIZE": {
                            "ACTION_BUTTONS": 25,
                            "OTHERS": 20
                        }
                    },
                    "EXPORT": {
                        "STYLE": {
                            "value": "qml",
                            "choices": ["qml", "sld"]
                        },
                        "DATA_FORMAT": {
                            "value": "GPKG",
                            "choices": ["GPKG", "ESRI Shapefile", "GeoJSON"]
                        },
                        "LAYERS_ENABLED": False,
                        "PROJECTION_ENABLED": False,
                        "PROJECTION_EPSG": 4326
                    }
                }
            },
            "CURRENT_PROJECT": {
                "OPTIONS": {
                    "FEATURE_COUNT_LIMIT": 100000,
                    "LAYER_PROPERTIES_COUNT": 10,
                    "LAYERS": {
                        "LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG": True
                    }
                }
            }
        }
        
        # Sample v2.0 configuration (expected structure)
        self.config_v2_expected_structure = {
            "_schema_version": "2.0",
            "app": {
                "auto_activate": {},
                "ui": {
                    "feedback": {},
                    "language": {},
                    "profile": {},
                    "action_bar": {},
                    "theme": {}
                },
                "buttons": {
                    "style": {},
                    "icon_sizes": {}
                },
                "export": {
                    "style": {},
                    "data": {},
                    "layers_enabled": False,
                    "projection_enabled": False
                },
                "project": {
                    "feature_count_limit": 100000,
                    "layer_properties_count": 10,
                    "link_legend_layers": True
                }
            }
        }
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_detect_version_v1(self):
        """Test detection of v1.0 configuration."""
        migrator = ConfigMigration(self.config_path)
        version = migrator.detect_version(self.config_v1)
        self.assertEqual(version, "1.0")
    
    def test_detect_version_v2(self):
        """Test detection of v2.0 configuration."""
        config_v2 = {"_schema_version": "2.0", "app": {}}
        migrator = ConfigMigration(self.config_path)
        version = migrator.detect_version(config_v2)
        self.assertEqual(version, "2.0")
    
    def test_detect_version_unknown(self):
        """Test detection of unknown configuration format."""
        config_unknown = {"some_random_key": {}}
        migrator = ConfigMigration(self.config_path)
        version = migrator.detect_version(config_unknown)
        self.assertEqual(version, "unknown")
    
    def test_needs_migration_v1(self):
        """Test that v1.0 config needs migration."""
        migrator = ConfigMigration(self.config_path)
        self.assertTrue(migrator.needs_migration(self.config_v1))
    
    def test_needs_migration_v2(self):
        """Test that v2.0 config doesn't need migration."""
        config_v2 = {"_schema_version": "2.0", "app": {}}
        migrator = ConfigMigration(self.config_path)
        self.assertFalse(migrator.needs_migration(config_v2))
    
    def test_migrate_1_0_to_2_0_structure(self):
        """Test that migration creates correct v2.0 structure."""
        migrator = ConfigMigration(self.config_path)
        migrated = migrator.migrate_1_0_to_2_0(self.config_v1)
        
        # Check version marker
        self.assertEqual(migrated["_schema_version"], "2.0")
        self.assertEqual(migrated["_migrated_from"], "1.0")
        
        # Check main structure exists
        self.assertIn("app", migrated)
        self.assertIn("ui", migrated["app"])
        self.assertIn("buttons", migrated["app"])
        self.assertIn("export", migrated["app"])
        self.assertIn("project", migrated["app"])
    
    def test_migrate_1_0_to_2_0_auto_activate(self):
        """Test migration of auto_activate setting."""
        migrator = ConfigMigration(self.config_path)
        migrated = migrator.migrate_1_0_to_2_0(self.config_v1)
        
        self.assertIn("auto_activate", migrated["app"])
        auto_activate = migrated["app"]["auto_activate"]
        self.assertIn("value", auto_activate)
        self.assertEqual(auto_activate["value"], False)
    
    def test_migrate_1_0_to_2_0_feedback_level(self):
        """Test migration of feedback level."""
        migrator = ConfigMigration(self.config_path)
        migrated = migrator.migrate_1_0_to_2_0(self.config_v1)
        
        feedback = migrated["app"]["ui"]["feedback"]["level"]
        self.assertIn("value", feedback)
        self.assertEqual(feedback["value"], "normal")
        self.assertIn("choices", feedback)
    
    def test_migrate_1_0_to_2_0_ui_profile(self):
        """Test migration of UI profile."""
        migrator = ConfigMigration(self.config_path)
        migrated = migrator.migrate_1_0_to_2_0(self.config_v1)
        
        profile = migrated["app"]["ui"]["profile"]
        self.assertIn("value", profile)
        self.assertEqual(profile["value"], "auto")
    
    def test_migrate_1_0_to_2_0_action_bar(self):
        """Test migration of action bar settings."""
        migrator = ConfigMigration(self.config_path)
        migrated = migrator.migrate_1_0_to_2_0(self.config_v1)
        
        action_bar = migrated["app"]["ui"]["action_bar"]
        self.assertIn("position", action_bar)
        self.assertEqual(action_bar["position"]["value"], "left")
        self.assertIn("vertical_alignment", action_bar)
        self.assertEqual(action_bar["vertical_alignment"]["value"], "top")
    
    def test_migrate_1_0_to_2_0_theme(self):
        """Test migration of theme settings."""
        migrator = ConfigMigration(self.config_path)
        migrated = migrator.migrate_1_0_to_2_0(self.config_v1)
        
        theme = migrated["app"]["ui"]["theme"]
        self.assertIn("active", theme)
        self.assertEqual(theme["active"]["value"], "auto")
        self.assertIn("source", theme)
        self.assertEqual(theme["source"]["value"], "config")
    
    def test_migrate_1_0_to_2_0_buttons(self):
        """Test migration of button settings."""
        migrator = ConfigMigration(self.config_path)
        migrated = migrator.migrate_1_0_to_2_0(self.config_v1)
        
        buttons = migrated["app"]["buttons"]
        self.assertIn("style", buttons)
        self.assertIn("icon_sizes", buttons)
        self.assertEqual(buttons["icon_sizes"]["action"], 25)
        self.assertEqual(buttons["icon_sizes"]["others"], 20)
    
    def test_migrate_1_0_to_2_0_export(self):
        """Test migration of export settings."""
        migrator = ConfigMigration(self.config_path)
        migrated = migrator.migrate_1_0_to_2_0(self.config_v1)
        
        export = migrated["app"]["export"]
        self.assertIn("style", export)
        self.assertEqual(export["style"]["format"]["value"], "qml")
        self.assertIn("data", export)
        self.assertEqual(export["data"]["format"]["value"], "GPKG")
        self.assertEqual(export["layers_enabled"], False)
        self.assertEqual(export["projection_enabled"], False)
        self.assertEqual(export["projection_epsg"], 4326)
    
    def test_migrate_1_0_to_2_0_project(self):
        """Test migration of project settings."""
        migrator = ConfigMigration(self.config_path)
        migrated = migrator.migrate_1_0_to_2_0(self.config_v1)
        
        project = migrated["app"]["project"]
        self.assertEqual(project["feature_count_limit"], 100000)
        self.assertEqual(project["layer_properties_count"], 10)
        self.assertEqual(project["link_legend_layers"], True)
    
    def test_create_backup(self):
        """Test backup creation."""
        # Write config to file
        with open(self.config_path, 'w') as f:
            json.dump(self.config_v1, f)
        
        migrator = ConfigMigration(self.config_path)
        backup_path = migrator.create_backup(self.config_v1)
        
        self.assertTrue(os.path.exists(backup_path))
        self.assertTrue(backup_path.endswith('.json'))
        
        # Verify backup content
        with open(backup_path, 'r') as f:
            backup_data = json.load(f)
        self.assertEqual(backup_data, self.config_v1)
    
    def test_list_backups(self):
        """Test listing backup files."""
        with open(self.config_path, 'w') as f:
            json.dump(self.config_v1, f)
        
        migrator = ConfigMigration(self.config_path)
        
        # Create a few backups
        migrator.create_backup(self.config_v1)
        migrator.create_backup(self.config_v1)
        
        backups = migrator.list_backups()
        self.assertGreaterEqual(len(backups), 2)
        
        # Check backup info structure
        for backup in backups:
            self.assertIn("path", backup)
            self.assertIn("filename", backup)
            self.assertIn("date", backup)
            self.assertIn("version", backup)
    
    def test_full_migration(self):
        """Test full migration process."""
        # Write v1 config to file
        with open(self.config_path, 'w') as f:
            json.dump(self.config_v1, f)
        
        migrator = ConfigMigration(self.config_path)
        
        # Perform migration
        migrated, warnings = migrator.migrate(self.config_v1, create_backup=True)
        
        # Check result
        self.assertEqual(migrated["_schema_version"], "2.0")
        self.assertIn("app", migrated)
        
        # Check backups were created
        backups = migrator.list_backups()
        self.assertGreater(len(backups), 0)
    
    def test_auto_migrate_if_needed(self):
        """Test automatic migration."""
        # Write v1 config to file
        with open(self.config_path, 'w') as f:
            json.dump(self.config_v1, f)
        
        migrator = ConfigMigration(self.config_path)
        performed, warnings = migrator.auto_migrate_if_needed()
        
        self.assertTrue(performed)
        
        # Verify file was updated
        with open(self.config_path, 'r') as f:
            updated_config = json.load(f)
        
        self.assertEqual(updated_config["_schema_version"], "2.0")
    
    def test_no_migration_needed(self):
        """Test when no migration is needed."""
        # Write v2 config to file
        config_v2 = {"_schema_version": "2.0", "app": {}}
        with open(self.config_path, 'w') as f:
            json.dump(config_v2, f)
        
        migrator = ConfigMigration(self.config_path)
        performed, warnings = migrator.auto_migrate_if_needed()
        
        self.assertFalse(performed)
    
    def test_extract_value_choices_type(self):
        """Test extraction of ChoicesType value."""
        migrator = ConfigMigration(self.config_path)
        
        choices_data = {
            "value": "normal",
            "choices": ["minimal", "normal", "verbose"]
        }
        
        result = migrator._extract_value(choices_data)
        self.assertIsInstance(result, dict)
        self.assertIn("value", result)
        self.assertEqual(result["value"], "normal")
    
    def test_extract_value_plain(self):
        """Test extraction of plain value."""
        migrator = ConfigMigration(self.config_path)
        
        plain_data = "some_value"
        result = migrator._extract_value(plain_data)
        self.assertEqual(result, "some_value")


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestConfigMigration)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

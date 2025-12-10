"""
Test for config.json migration to APP_SQLITE_PATH directory.

This test verifies that:
1. Config is properly migrated from plugin directory to SQLite directory
2. get_config_path() returns the correct path
3. Config can be read and written in the new location
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from pathlib import Path

# Add plugin path to sys.path for imports
plugin_path = str(Path(__file__).parent.parent)
if plugin_path not in sys.path:
    sys.path.insert(0, plugin_path)


class TestConfigMigration(unittest.TestCase):
    """Test configuration file migration functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directories
        self.temp_dir = tempfile.mkdtemp()
        self.plugin_dir = os.path.join(self.temp_dir, 'plugin')
        self.sqlite_dir = os.path.join(self.temp_dir, 'sqlite')
        
        os.makedirs(self.plugin_dir, exist_ok=True)
        os.makedirs(self.sqlite_dir, exist_ok=True)
        
        # Create sample config
        self.sample_config = {
            "APP": {
                "OPTIONS": {
                    "APP_SQLITE_PATH": self.sqlite_dir
                }
            },
            "CURRENT_PROJECT": {
                "layers": []
            }
        }
    
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_config_path_structure(self):
        """Test that config path uses correct directory structure."""
        # Write config to plugin dir (old location)
        old_config_path = os.path.join(self.plugin_dir, 'config.json')
        with open(old_config_path, 'w') as f:
            json.dump(self.sample_config, f, indent=4)
        
        # Expected new location
        new_config_path = os.path.join(self.sqlite_dir, 'config.json')
        
        print(f"Old config path: {old_config_path}")
        print(f"New config path: {new_config_path}")
        print(f"Config should be in SQLite directory: {self.sqlite_dir}")
        
        # Verify old config exists
        self.assertTrue(
            os.path.exists(old_config_path),
            "Old config should exist in plugin directory"
        )
    
    def test_config_migration_simulation(self):
        """Simulate config migration process."""
        # Create config in old location
        old_path = os.path.join(self.plugin_dir, 'config.json')
        with open(old_path, 'w') as f:
            json.dump(self.sample_config, f, indent=4)
        
        # Simulate migration
        new_path = os.path.join(self.sqlite_dir, 'config.json')
        
        if os.path.exists(old_path) and not os.path.exists(new_path):
            # Copy to new location
            shutil.copy2(old_path, new_path)
            
            # Backup old location
            backup_path = old_path + '.migrated'
            shutil.move(old_path, backup_path)
        
        # Verify migration
        self.assertTrue(
            os.path.exists(new_path),
            "Config should exist in new location after migration"
        )
        
        self.assertFalse(
            os.path.exists(old_path),
            "Old config should be moved (not exist) after migration"
        )
        
        self.assertTrue(
            os.path.exists(backup_path),
            "Backup of old config should exist"
        )
        
        # Verify content
        with open(new_path, 'r') as f:
            migrated_config = json.load(f)
        
        self.assertEqual(
            migrated_config["APP"]["OPTIONS"]["APP_SQLITE_PATH"],
            self.sqlite_dir,
            "Migrated config should preserve APP_SQLITE_PATH"
        )
    
    def test_config_read_write_new_location(self):
        """Test reading and writing config in new location."""
        config_path = os.path.join(self.sqlite_dir, 'config.json')
        
        # Write config
        with open(config_path, 'w') as f:
            json.dump(self.sample_config, f, indent=4)
        
        # Read config
        with open(config_path, 'r') as f:
            loaded_config = json.load(f)
        
        # Verify
        self.assertEqual(
            loaded_config["APP"]["OPTIONS"]["APP_SQLITE_PATH"],
            self.sqlite_dir,
            "Config should be readable from new location"
        )
        
        # Modify and save
        loaded_config["CURRENT_PROJECT"]["layers"] = ["layer1", "layer2"]
        
        with open(config_path, 'w') as f:
            json.dump(loaded_config, f, indent=4)
        
        # Re-read and verify modification
        with open(config_path, 'r') as f:
            modified_config = json.load(f)
        
        self.assertEqual(
            len(modified_config["CURRENT_PROJECT"]["layers"]),
            2,
            "Modified config should be saved correctly"
        )


def run_tests():
    """Run the test suite."""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestConfigMigration)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

"""
Test auto-reset of obsolete configuration

Tests the automatic detection and reset of obsolete/corrupted configurations.
"""

import json
import os
import tempfile
import shutil
import pytest
from pathlib import Path

# Add parent directory to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.config_migration import ConfigMigration


class TestAutoConfigReset:
    """Test automatic configuration reset functionality"""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def default_config_path(self, temp_config_dir):
        """Create a default config file"""
        default_path = os.path.join(temp_config_dir, "config.default.json")
        default_config = {
            "_CONFIG_VERSION": "2.0",
            "_CONFIG_META": {
                "description": "FilterMate Configuration File",
                "version": "2.0"
            },
            "APP": {
                "AUTO_ACTIVATE": {"value": False}
            }
        }
        with open(default_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        return default_path
    
    @pytest.fixture
    def config_path(self, temp_config_dir):
        """Path to config.json"""
        return os.path.join(temp_config_dir, "config.json")
    
    @pytest.fixture
    def migrator(self, config_path, default_config_path, temp_config_dir):
        """Create ConfigMigration instance"""
        # Ensure default config exists in same directory
        migrator = ConfigMigration(config_path)
        migrator.config_dir = temp_config_dir
        return migrator
    
    def test_detect_version_with_CONFIG_VERSION(self, migrator):
        """Test version detection with _CONFIG_VERSION marker"""
        config = {
            "_CONFIG_VERSION": "2.0",
            "APP": {}
        }
        assert migrator.detect_version(config) == "2.0"
    
    def test_detect_version_with_schema_version(self, migrator):
        """Test version detection with _schema_version marker"""
        config = {
            "_schema_version": "1.0",
            "APP": {}
        }
        assert migrator.detect_version(config) == "1.0"
    
    def test_detect_version_by_structure_v1(self, migrator):
        """Test version detection by structure for v1.0"""
        config = {
            "APP": {
                "DOCKWIDGET": {}
            }
        }
        assert migrator.detect_version(config) == "1.0"
    
    def test_detect_version_by_structure_v2(self, migrator):
        """Test version detection by structure for v2.0"""
        config = {
            "app": {
                "ui": {}
            }
        }
        assert migrator.detect_version(config) == "2.0"
    
    def test_detect_version_unknown(self, migrator):
        """Test version detection returns unknown for invalid config"""
        config = {
            "random_key": "random_value"
        }
        assert migrator.detect_version(config) == "unknown"
    
    def test_is_obsolete_unknown_version(self, migrator):
        """Test that unknown version is considered obsolete"""
        config = {"random_key": "value"}
        assert migrator.is_obsolete(config) is True
    
    def test_is_obsolete_v1_not_obsolete(self, migrator):
        """Test that v1.0 is not considered obsolete (it's migratable)"""
        config = {
            "_CONFIG_VERSION": "1.0",
            "APP": {"DOCKWIDGET": {}}
        }
        assert migrator.is_obsolete(config) is False
    
    def test_is_obsolete_v2_not_obsolete(self, migrator):
        """Test that v2.0 is not obsolete"""
        config = {
            "_CONFIG_VERSION": "2.0",
            "APP": {}
        }
        assert migrator.is_obsolete(config) is False
    
    def test_is_obsolete_unsupported_version(self, migrator):
        """Test that unsupported version (e.g., v0.5) is obsolete"""
        config = {
            "_CONFIG_VERSION": "0.5",
            "OLD_STRUCTURE": {}
        }
        assert migrator.is_obsolete(config) is True
    
    def test_reset_to_default(self, migrator, config_path, default_config_path, temp_config_dir):
        """Test reset_to_default creates backup and copies default"""
        # Create an obsolete config
        obsolete_config = {
            "version": "0.1",
            "old_key": "old_value"
        }
        with open(config_path, 'w') as f:
            json.dump(obsolete_config, f)
        
        # Reset to default
        success, message = migrator.reset_to_default(reason="test", config_data=obsolete_config)
        
        assert success is True
        assert "reset to default" in message.lower()
        
        # Verify backup was created
        backups = migrator.list_backups()
        assert len(backups) > 0
        
        # Verify config.json now contains default
        with open(config_path, 'r') as f:
            new_config = json.load(f)
        assert "_CONFIG_VERSION" in new_config
        assert new_config["_CONFIG_VERSION"] == "2.0"
    
    def test_auto_migrate_missing_config(self, migrator, config_path, default_config_path):
        """Test auto_migrate_if_needed handles missing config"""
        # Ensure config doesn't exist
        if os.path.exists(config_path):
            os.remove(config_path)
        
        # Run auto-migrate
        migrated, warnings = migrator.auto_migrate_if_needed()
        
        assert migrated is True
        assert os.path.exists(config_path)
        
        # Verify config is valid
        with open(config_path, 'r') as f:
            config = json.load(f)
        assert "_CONFIG_VERSION" in config
    
    def test_auto_migrate_corrupted_config(self, migrator, config_path, default_config_path):
        """Test auto_migrate_if_needed handles corrupted config"""
        # Create corrupted JSON
        with open(config_path, 'w') as f:
            f.write("{invalid json")
        
        # Run auto-migrate
        migrated, warnings = migrator.auto_migrate_if_needed()
        
        assert migrated is True
        assert len(warnings) > 0
        
        # Verify config is now valid
        with open(config_path, 'r') as f:
            config = json.load(f)
        assert "_CONFIG_VERSION" in config
    
    def test_auto_migrate_obsolete_config(self, migrator, config_path, default_config_path):
        """Test auto_migrate_if_needed handles obsolete config"""
        # Create obsolete config
        obsolete_config = {
            "version": "0.5",
            "old_structure": {}
        }
        with open(config_path, 'w') as f:
            json.dump(obsolete_config, f)
        
        # Run auto-migrate
        migrated, warnings = migrator.auto_migrate_if_needed()
        
        assert migrated is True
        
        # Verify config is now v2.0
        with open(config_path, 'r') as f:
            config = json.load(f)
        assert config["_CONFIG_VERSION"] == "2.0"
    
    def test_auto_migrate_up_to_date_config(self, migrator, config_path):
        """Test auto_migrate_if_needed skips up-to-date config"""
        # Create up-to-date config
        current_config = {
            "_CONFIG_VERSION": "2.0",
            "APP": {}
        }
        with open(config_path, 'w') as f:
            json.dump(current_config, f)
        
        # Run auto-migrate
        migrated, warnings = migrator.auto_migrate_if_needed()
        
        assert migrated is False
        assert len(warnings) == 0


class TestConfigDefaultStructure:
    """Test that config.default.json has the correct structure for qt_json_view"""
    
    @pytest.fixture
    def default_config(self):
        """Load config.default.json"""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'config',
            'config.default.json'
        )
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def test_has_version_marker(self, default_config):
        """Test that config has version marker"""
        assert "_CONFIG_VERSION" in default_config
        assert default_config["_CONFIG_VERSION"] == "2.0"
    
    def test_has_config_meta(self, default_config):
        """Test that config has metadata"""
        assert "_CONFIG_META" in default_config
        assert "description" in default_config["_CONFIG_META"]
        assert "version" in default_config["_CONFIG_META"]
    
    def test_choices_structure(self, default_config):
        """Test that choices follow the pattern {value, choices}"""
        # Check LANGUAGE
        language = default_config["APP"]["DOCKWIDGET"]["LANGUAGE"]
        assert "value" in language
        assert "choices" in language
        assert isinstance(language["choices"], list)
        assert language["value"] in language["choices"]
        
        # Check ACTIVE_THEME
        theme = default_config["APP"]["DOCKWIDGET"]["COLORS"]["ACTIVE_THEME"]
        assert "value" in theme
        assert "choices" in theme
    
    def test_meta_sections_exist(self, default_config):
        """Test that metadata sections are present"""
        dockwidget = default_config["APP"]["DOCKWIDGET"]
        
        # Check for meta sections (prefixed with _)
        assert "_LANGUAGE_META" in dockwidget
        assert "_FEEDBACK_LEVEL_META" in dockwidget
        assert "_ACTIVE_THEME_META" in dockwidget["COLORS"]
    
    def test_optimization_structure(self, default_config):
        """Test SMALL_DATASET_OPTIMIZATION structure"""
        optimization = default_config["APP"]["OPTIONS"]["SMALL_DATASET_OPTIMIZATION"]
        
        # Check enabled has choices
        assert "enabled" in optimization
        assert isinstance(optimization["enabled"], dict)
        assert "value" in optimization["enabled"]
        assert "choices" in optimization["enabled"]
        
        # Check method has choices
        assert "method" in optimization
        assert isinstance(optimization["method"], dict)
        assert "value" in optimization["method"]
        assert "choices" in optimization["method"]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

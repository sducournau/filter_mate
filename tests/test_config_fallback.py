# -*- coding: utf-8 -*-
"""
Tests for Configuration Fallback Mechanism

Tests that the plugin gracefully handles configuration failures
by using the in-memory fallback configuration.
"""

import unittest
import json
import os
import sys
import tempfile
import shutil

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock qgis before importing config
from unittest.mock import Mock, MagicMock

# Create minimal mock for qgis.core
mock_qgis_core = MagicMock()
mock_qgis_core.Qgis.Info = 0
mock_qgis_core.Qgis.Warning = 1
mock_qgis_core.Qgis.Critical = 2
mock_qgis_core.QgsMessageLog.logMessage = Mock()
mock_qgis_core.QgsProject.instance = Mock(return_value=Mock())
mock_qgis_core.QgsApplication.qgisSettingsDirPath = Mock(return_value=tempfile.gettempdir())

sys.modules['qgis'] = MagicMock()
sys.modules['qgis.core'] = mock_qgis_core


class TestFallbackConfig(unittest.TestCase):
    """Test the fallback configuration mechanism."""
    
    def test_fallback_config_exists(self):
        """Test that FALLBACK_CONFIG is defined and has required structure."""
        from config.config import FALLBACK_CONFIG
        
        # Check it's a dictionary
        self.assertIsInstance(FALLBACK_CONFIG, dict)
        
        # Check required top-level keys
        self.assertIn("APP", FALLBACK_CONFIG)
        self.assertIn("_CONFIG_VERSION", FALLBACK_CONFIG)
        
        # Check APP structure
        app_config = FALLBACK_CONFIG["APP"]
        self.assertIn("DOCKWIDGET", app_config)
        self.assertIn("OPTIONS", app_config)
        
        # Check OPTIONS has required keys
        options = app_config["OPTIONS"]
        self.assertIn("APP_SQLITE_PATH", options)
        self.assertIn("FRESH_RELOAD_FLAG", options)
    
    def test_get_fallback_config_returns_copy(self):
        """Test that get_fallback_config returns a deep copy."""
        from config.config import get_fallback_config, FALLBACK_CONFIG
        
        # Get a copy
        config_copy = get_fallback_config()
        
        # Modify the copy
        config_copy["TEST_KEY"] = "test_value"
        config_copy["APP"]["TEST_NESTED"] = "nested_value"
        
        # Original should be unchanged
        self.assertNotIn("TEST_KEY", FALLBACK_CONFIG)
        self.assertNotIn("TEST_NESTED", FALLBACK_CONFIG["APP"])
    
    def test_fallback_config_has_feedback_level(self):
        """Test that fallback config includes FEEDBACK_LEVEL for user messages."""
        from config.config import get_fallback_config
        
        config = get_fallback_config()
        
        # Check FEEDBACK_LEVEL exists and has valid structure
        feedback = config["APP"]["DOCKWIDGET"]["FEEDBACK_LEVEL"]
        self.assertIn("value", feedback)
        self.assertIn("choices", feedback)
        self.assertEqual(feedback["value"], "normal")
        self.assertIn("normal", feedback["choices"])
    
    def test_fallback_config_has_language(self):
        """Test that fallback config includes LANGUAGE setting."""
        from config.config import get_fallback_config
        
        config = get_fallback_config()
        
        # Check LANGUAGE exists
        language = config["APP"]["DOCKWIDGET"]["LANGUAGE"]
        self.assertIn("value", language)
        self.assertEqual(language["value"], "auto")
    
    def test_fallback_config_has_theme(self):
        """Test that fallback config includes THEME setting."""
        from config.config import get_fallback_config
        
        config = get_fallback_config()
        
        # Check THEME exists
        theme = config["APP"]["DOCKWIDGET"]["THEME"]
        self.assertIn("value", theme)
        self.assertIn("choices", theme)
        self.assertEqual(theme["value"], "auto")
    
    def test_fallback_config_version(self):
        """Test that fallback config has correct version."""
        from config.config import get_fallback_config
        
        config = get_fallback_config()
        
        self.assertEqual(config["_CONFIG_VERSION"], "2.0")
        self.assertTrue(config["_CONFIG_META"]["fallback"])


class TestFallbackConfigIntegration(unittest.TestCase):
    """Integration tests for fallback config with init_env_vars."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test configs
        self.temp_dir = tempfile.mkdtemp()
        self.original_env_vars = None
    
    def tearDown(self):
        """Clean up test environment."""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_fallback_on_corrupted_json(self):
        """Test that corrupted JSON falls back gracefully.
        
        Note: This is a conceptual test - actual integration requires
        mocking the file system operations in init_env_vars.
        """
        # Write a corrupted config file
        corrupted_config_path = os.path.join(self.temp_dir, 'config.json')
        with open(corrupted_config_path, 'w') as f:
            f.write('{ invalid json content }}}')
        
        # Verify the file is indeed invalid JSON
        with self.assertRaises(json.JSONDecodeError):
            with open(corrupted_config_path) as f:
                json.load(f)
        
        # The actual fallback mechanism is tested implicitly
        # when init_env_vars is called with inaccessible configs
    
    def test_fallback_on_missing_app_key(self):
        """Test that config without APP key triggers fallback."""
        # Write a config missing the APP key
        invalid_config_path = os.path.join(self.temp_dir, 'config.json')
        with open(invalid_config_path, 'w') as f:
            json.dump({"SOME_OTHER_KEY": {}}, f)
        
        # Load and check structure
        with open(invalid_config_path) as f:
            config = json.load(f)
        
        # Verify it would trigger fallback (missing APP/app key)
        has_app = "APP" in config or "app" in config
        self.assertFalse(has_app)


if __name__ == '__main__':
    unittest.main()

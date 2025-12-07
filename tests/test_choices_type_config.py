# -*- coding: utf-8 -*-
"""
Test ChoicesType Configuration Format

Tests that configuration fields that should be ChoicesType are properly formatted
and that the helper functions work correctly.
"""

import unittest
import json
import os
import sys

# Add plugin path
plugin_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if plugin_path not in sys.path:
    sys.path.insert(0, plugin_path)

from modules.config_helpers import (
    get_config_value,
    set_config_value,
    get_config_choices,
    is_choices_type,
    validate_config_value,
    get_ui_profile,
    set_ui_profile,
    get_active_theme,
    get_theme_source,
    get_export_style_format,
    get_export_data_format
)


class TestConfigChoicesTypeFormat(unittest.TestCase):
    """Test that config.json uses ChoicesType for appropriate fields"""
    
    def setUp(self):
        """Load config.json"""
        config_path = os.path.join(plugin_path, 'config', 'config.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
    
    def test_ui_profile_is_choices_type(self):
        """Test UI_PROFILE uses ChoicesType format"""
        ui_profile = self.config['APP']['DOCKWIDGET']['UI_PROFILE']
        
        self.assertIsInstance(ui_profile, dict, "UI_PROFILE should be a dict")
        self.assertIn('value', ui_profile, "UI_PROFILE should have 'value' key")
        self.assertIn('choices', ui_profile, "UI_PROFILE should have 'choices' key")
        
        # Check value is in choices
        self.assertIn(ui_profile['value'], ui_profile['choices'],
                     f"UI_PROFILE value '{ui_profile['value']}' should be in choices")
        
        # Check expected choices are present
        expected_choices = ['auto', 'compact', 'normal']
        for choice in expected_choices:
            self.assertIn(choice, ui_profile['choices'],
                         f"UI_PROFILE should have '{choice}' in choices")
    
    def test_active_theme_is_choices_type(self):
        """Test ACTIVE_THEME uses ChoicesType format"""
        active_theme = self.config['APP']['DOCKWIDGET']['COLORS']['ACTIVE_THEME']
        
        self.assertIsInstance(active_theme, dict)
        self.assertIn('value', active_theme)
        self.assertIn('choices', active_theme)
        self.assertIn(active_theme['value'], active_theme['choices'])
        
        # Check expected choices
        expected_choices = ['auto', 'default', 'dark', 'light']
        for choice in expected_choices:
            self.assertIn(choice, active_theme['choices'])
    
    def test_theme_source_is_choices_type(self):
        """Test THEME_SOURCE uses ChoicesType format"""
        theme_source = self.config['APP']['DOCKWIDGET']['COLORS']['THEME_SOURCE']
        
        self.assertIsInstance(theme_source, dict)
        self.assertIn('value', theme_source)
        self.assertIn('choices', theme_source)
        self.assertIn(theme_source['value'], theme_source['choices'])
        
        # Check expected choices
        expected_choices = ['config', 'qgis', 'system']
        for choice in expected_choices:
            self.assertIn(choice, theme_source['choices'])
    
    def test_styles_to_export_is_choices_type(self):
        """Test STYLES_TO_EXPORT uses ChoicesType format"""
        # Test in EXPORTING section
        styles = self.config['CURRENT_PROJECT']['EXPORTING']['STYLES_TO_EXPORT']
        
        self.assertIsInstance(styles, dict)
        self.assertIn('value', styles)
        self.assertIn('choices', styles)
        self.assertIn(styles['value'], styles['choices'])
        
        # Check expected choices
        expected_choices = ['QML', 'SLD', 'None']
        for choice in expected_choices:
            self.assertIn(choice, styles['choices'])
        
        # Test in EXPORT section (duplicate)
        if 'EXPORT' in self.config['CURRENT_PROJECT']:
            styles_export = self.config['CURRENT_PROJECT']['EXPORT']['STYLES_TO_EXPORT']
            self.assertIsInstance(styles_export, dict)
            self.assertIn('value', styles_export)
            self.assertIn('choices', styles_export)
    
    def test_datatype_to_export_is_choices_type(self):
        """Test DATATYPE_TO_EXPORT uses ChoicesType format"""
        # Test in EXPORTING section
        datatype = self.config['CURRENT_PROJECT']['EXPORTING']['DATATYPE_TO_EXPORT']
        
        self.assertIsInstance(datatype, dict)
        self.assertIn('value', datatype)
        self.assertIn('choices', datatype)
        self.assertIn(datatype['value'], datatype['choices'])
        
        # Check expected choices
        expected_choices = ['GPKG', 'SHP', 'GEOJSON', 'KML', 'DXF', 'CSV']
        for choice in expected_choices:
            self.assertIn(choice, datatype['choices'])
    
    def test_old_ui_profile_options_renamed(self):
        """Test that UI_PROFILE_OPTIONS has been renamed"""
        # Should now be _UI_PROFILE_META (with underscore prefix for metadata)
        self.assertIn('_UI_PROFILE_META', self.config['APP']['DOCKWIDGET'],
                     "Metadata should be in _UI_PROFILE_META")
        
        # Old name should not exist
        self.assertNotIn('UI_PROFILE_OPTIONS', self.config['APP']['DOCKWIDGET'],
                        "Old UI_PROFILE_OPTIONS should be renamed")


class TestConfigHelperFunctions(unittest.TestCase):
    """Test configuration helper functions"""
    
    def setUp(self):
        """Create test configuration"""
        self.config = {
            "APP": {
                "DOCKWIDGET": {
                    "UI_PROFILE": {
                        "value": "auto",
                        "choices": ["auto", "compact", "normal"]
                    },
                    "SIMPLE_VALUE": "test"
                }
            }
        }
    
    def test_get_config_value_choices_type(self):
        """Test getting value from ChoicesType"""
        value = get_config_value(self.config, "APP", "DOCKWIDGET", "UI_PROFILE")
        self.assertEqual(value, "auto")
    
    def test_get_config_value_simple(self):
        """Test getting simple value"""
        value = get_config_value(self.config, "APP", "DOCKWIDGET", "SIMPLE_VALUE")
        self.assertEqual(value, "test")
    
    def test_get_config_value_default(self):
        """Test default value for missing key"""
        value = get_config_value(self.config, "MISSING", "KEY", default="default")
        self.assertEqual(value, "default")
    
    def test_set_config_value_choices_type(self):
        """Test setting value in ChoicesType"""
        set_config_value(self.config, "compact", "APP", "DOCKWIDGET", "UI_PROFILE")
        
        # Should update the 'value' key
        self.assertEqual(
            self.config["APP"]["DOCKWIDGET"]["UI_PROFILE"]["value"],
            "compact"
        )
    
    def test_set_config_value_invalid_choice(self):
        """Test setting invalid choice raises ValueError"""
        with self.assertRaises(ValueError):
            set_config_value(self.config, "invalid", "APP", "DOCKWIDGET", "UI_PROFILE")
    
    def test_get_config_choices(self):
        """Test getting choices list"""
        choices = get_config_choices(self.config, "APP", "DOCKWIDGET", "UI_PROFILE")
        self.assertEqual(choices, ["auto", "compact", "normal"])
    
    def test_is_choices_type(self):
        """Test detecting ChoicesType"""
        self.assertTrue(
            is_choices_type(self.config, "APP", "DOCKWIDGET", "UI_PROFILE")
        )
        self.assertFalse(
            is_choices_type(self.config, "APP", "DOCKWIDGET", "SIMPLE_VALUE")
        )
    
    def test_validate_config_value(self):
        """Test value validation"""
        # Valid choice
        self.assertTrue(
            validate_config_value(self.config, "compact", "APP", "DOCKWIDGET", "UI_PROFILE")
        )
        
        # Invalid choice
        self.assertFalse(
            validate_config_value(self.config, "invalid", "APP", "DOCKWIDGET", "UI_PROFILE")
        )
        
        # Non-ChoicesType (any value valid)
        self.assertTrue(
            validate_config_value(self.config, "anything", "APP", "DOCKWIDGET", "SIMPLE_VALUE")
        )


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions for common config access"""
    
    def setUp(self):
        """Load actual config"""
        config_path = os.path.join(plugin_path, 'config', 'config.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
    
    def test_get_ui_profile(self):
        """Test get_ui_profile convenience function"""
        profile = get_ui_profile(self.config)
        self.assertIn(profile, ['auto', 'compact', 'normal'])
    
    def test_set_ui_profile(self):
        """Test set_ui_profile convenience function"""
        config_copy = json.loads(json.dumps(self.config))  # Deep copy
        set_ui_profile(config_copy, 'compact')
        
        profile = get_ui_profile(config_copy)
        self.assertEqual(profile, 'compact')
    
    def test_get_active_theme(self):
        """Test get_active_theme convenience function"""
        theme = get_active_theme(self.config)
        self.assertIn(theme, ['auto', 'default', 'dark', 'light'])
    
    def test_get_theme_source(self):
        """Test get_theme_source convenience function"""
        source = get_theme_source(self.config)
        self.assertIn(source, ['config', 'qgis', 'system'])
    
    def test_get_export_formats(self):
        """Test export format convenience functions"""
        style_format = get_export_style_format(self.config)
        self.assertIn(style_format, ['QML', 'SLD', 'None'])
        
        data_format = get_export_data_format(self.config)
        self.assertIn(data_format, ['GPKG', 'SHP', 'GEOJSON', 'KML', 'DXF', 'CSV'])


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestConfigChoicesTypeFormat))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigHelperFunctions))
    suite.addTests(loader.loadTestsFromTestCase(TestConvenienceFunctions))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

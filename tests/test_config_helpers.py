# -*- coding: utf-8 -*-
"""
Tests for Configuration Helpers

Tests that config_helpers.py functions work correctly with both
current (v1) and future (v2) configuration structures.
"""

import unittest
import json
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.config_helpers import (
    # Basic helpers
    get_config_value,
    set_config_value,
    get_config_choices,
    is_choices_type,
    validate_config_value,
    get_config_with_fallback,
    # UI helpers
    get_feedback_level,
    get_ui_action_bar_position,
    get_ui_action_bar_alignment,
    get_ui_profile,
    get_active_theme,
    get_theme_source,
    # Button helpers
    get_button_icon,
    get_button_icon_size,
    # Color helpers
    get_theme_colors,
    get_font_colors,
    get_background_colors,
    get_accent_colors,
    # Project helpers
    get_layer_properties_count,
    set_layer_properties_count,
    get_postgresql_active_connection,
    is_postgresql_active,
    set_postgresql_connection,
    # Export helpers
    get_export_layers_enabled,
    get_export_layers_list,
    get_export_projection_epsg,
    # Paths and flags
    get_github_page_url,
    get_sqlite_storage_path,
    get_fresh_reload_flag,
    set_fresh_reload_flag,
)


class TestConfigHelpersWithV1Structure(unittest.TestCase):
    """Test helpers with current (v1) configuration structure."""
    
    def setUp(self):
        """Load current config structure for testing."""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'config',
            'config.json'
        )
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                self.config_v1 = json.load(f)
        else:
            # Fallback minimal config if file doesn't exist
            self.config_v1 = {
                "APP": {
                    "DOCKWIDGET": {
                        "FEEDBACK_LEVEL": {"value": "normal", "choices": ["minimal", "normal", "verbose"]},
                        "ACTION_BAR_POSITION": {"value": "left", "choices": ["top", "bottom", "left", "right"]},
                        "COLORS": {
                            "ACTIVE_THEME": {"value": "default", "choices": ["auto", "default", "dark", "light"]},
                            "THEMES": {
                                "default": {
                                    "FONT": ["#212121", "#616161", "#BDBDBD"],
                                    "BACKGROUND": ["#F5F5F5", "#FFFFFF", "#E0E0E0", "#2196F3"]
                                }
                            }
                        },
                        "PushButton": {
                            "ICONS_SIZES": {"ACTION": 25, "OTHERS": 20},
                            "ICONS": {
                                "ACTION": {"FILTER": "filter.png"}
                            }
                        }
                    },
                    "OPTIONS": {
                        "GITHUB_PAGE": "https://sducournau.github.io/filter_mate/",
                        "APP_SQLITE_PATH": "",
                        "FRESH_RELOAD_FLAG": False
                    }
                },
                "CURRENT_PROJECT": {
                    "OPTIONS": {
                        "LAYERS": {
                            "LAYER_PROPERTIES_COUNT": 35,
                            "FEATURE_COUNT_LIMIT": 10000
                        },
                        "ACTIVE_POSTGRESQL": "",
                        "IS_ACTIVE_POSTGRESQL": False
                    },
                    "EXPORTING": {
                        "HAS_LAYERS_TO_EXPORT": False,
                        "LAYERS_TO_EXPORT": [],
                        "PROJECTION_TO_EXPORT": "EPSG:3857"
                    }
                }
            }
    
    def test_get_feedback_level(self):
        """Test feedback level retrieval."""
        level = get_feedback_level(self.config_v1)
        self.assertIn(level, ["minimal", "normal", "verbose"])
    
    def test_get_ui_action_bar_position(self):
        """Test action bar position retrieval."""
        position = get_ui_action_bar_position(self.config_v1)
        self.assertIn(position, ["top", "bottom", "left", "right"])
    
    def test_get_button_icon(self):
        """Test button icon retrieval."""
        icon = get_button_icon(self.config_v1, "action", "filter")
        self.assertTrue(icon.endswith(".png"))
    
    def test_get_button_icon_size(self):
        """Test button icon size retrieval."""
        size = get_button_icon_size(self.config_v1, "action")
        self.assertIsInstance(size, int)
        self.assertGreater(size, 0)
    
    def test_get_font_colors(self):
        """Test font colors retrieval."""
        colors = get_font_colors(self.config_v1)
        self.assertIsInstance(colors, list)
        self.assertEqual(len(colors), 3)
        # Check they're valid color codes
        for color in colors:
            self.assertTrue(color.startswith("#"))
    
    def test_get_background_colors(self):
        """Test background colors retrieval."""
        colors = get_background_colors(self.config_v1)
        self.assertIsInstance(colors, list)
        self.assertGreaterEqual(len(colors), 3)
    
    def test_get_accent_colors(self):
        """Test accent colors retrieval."""
        colors = get_accent_colors(self.config_v1)
        self.assertIsInstance(colors, dict)
        self.assertIn("primary", colors)
    
    def test_get_layer_properties_count(self):
        """Test layer properties count retrieval."""
        count = get_layer_properties_count(self.config_v1)
        self.assertIsInstance(count, int)
        self.assertGreater(count, 0)
    
    def test_set_layer_properties_count(self):
        """Test layer properties count setting."""
        test_config = json.loads(json.dumps(self.config_v1))  # Deep copy
        set_layer_properties_count(test_config, 50)
        new_count = get_layer_properties_count(test_config)
        self.assertEqual(new_count, 50)
    
    def test_get_postgresql_connection(self):
        """Test PostgreSQL connection retrieval."""
        connection = get_postgresql_active_connection(self.config_v1)
        self.assertIsInstance(connection, str)
        is_active = is_postgresql_active(self.config_v1)
        self.assertIsInstance(is_active, bool)
    
    def test_set_postgresql_connection(self):
        """Test PostgreSQL connection setting."""
        test_config = json.loads(json.dumps(self.config_v1))  # Deep copy
        set_postgresql_connection(test_config, "test_connection", True)
        connection = get_postgresql_active_connection(test_config)
        is_active = is_postgresql_active(test_config)
        self.assertEqual(connection, "test_connection")
        self.assertTrue(is_active)
    
    def test_get_export_settings(self):
        """Test export settings retrieval."""
        enabled = get_export_layers_enabled(self.config_v1)
        self.assertIsInstance(enabled, bool)
        
        layers = get_export_layers_list(self.config_v1)
        self.assertIsInstance(layers, list)
        
        epsg = get_export_projection_epsg(self.config_v1)
        self.assertTrue(epsg.startswith("EPSG:"))
    
    def test_get_paths(self):
        """Test paths retrieval."""
        url = get_github_page_url(self.config_v1)
        self.assertTrue(url.startswith("http"))
        
        path = get_sqlite_storage_path(self.config_v1)
        self.assertIsInstance(path, str)
    
    def test_get_fresh_reload_flag(self):
        """Test fresh reload flag."""
        flag = get_fresh_reload_flag(self.config_v1)
        self.assertIsInstance(flag, bool)
    
    def test_set_fresh_reload_flag(self):
        """Test setting fresh reload flag."""
        test_config = json.loads(json.dumps(self.config_v1))  # Deep copy
        set_fresh_reload_flag(test_config, True)
        flag = get_fresh_reload_flag(test_config)
        self.assertTrue(flag)


class TestConfigHelpersWithV2Structure(unittest.TestCase):
    """Test helpers with future (v2) configuration structure."""
    
    def setUp(self):
        """Create v2 config structure for testing."""
        self.config_v2 = {
            "app": {
                "ui": {
                    "feedback": {
                        "level": {"value": "normal", "choices": ["minimal", "normal", "verbose"]}
                    },
                    "action_bar": {
                        "position": {"value": "left", "choices": ["top", "bottom", "left", "right"]},
                        "vertical_alignment": {"value": "top", "choices": ["top", "bottom"]}
                    },
                    "theme": {
                        "active": {"value": "default", "choices": ["auto", "default", "dark", "light"]}
                    }
                },
                "buttons": {
                    "icon_sizes": {"action": 25, "others": 20},
                    "icons": {
                        "action": {"filter": "filter.png"}
                    }
                },
                "themes": {
                    "default": {
                        "font": ["#212121", "#616161", "#BDBDBD"],
                        "background": ["#F5F5F5", "#FFFFFF", "#E0E0E0", "#2196F3"],
                        "accent": {
                            "primary": "#1976D2",
                            "hover": "#2196F3"
                        }
                    }
                },
                "paths": {
                    "github_page": "https://sducournau.github.io/filter_mate/",
                    "sqlite_storage": ""
                },
                "flags": {
                    "fresh_reload": False
                }
            },
            "project": {
                "layers": {
                    "properties_count": 35,
                    "feature_limit": 10000
                },
                "postgresql": {
                    "active_connection": "",
                    "is_active": False
                },
                "export": {
                    "layers": {
                        "enabled": False,
                        "selected": []
                    },
                    "projection": {
                        "epsg": "EPSG:3857"
                    }
                }
            }
        }
    
    def test_get_feedback_level_v2(self):
        """Test feedback level retrieval with v2 structure."""
        level = get_feedback_level(self.config_v2)
        self.assertEqual(level, "normal")
    
    def test_get_ui_action_bar_position_v2(self):
        """Test action bar position with v2 structure."""
        position = get_ui_action_bar_position(self.config_v2)
        self.assertEqual(position, "left")
    
    def test_get_button_icon_v2(self):
        """Test button icon with v2 structure."""
        icon = get_button_icon(self.config_v2, "action", "filter")
        self.assertEqual(icon, "filter.png")
    
    def test_get_font_colors_v2(self):
        """Test font colors with v2 structure."""
        colors = get_font_colors(self.config_v2)
        self.assertEqual(len(colors), 3)
        self.assertEqual(colors[0], "#212121")
    
    def test_get_layer_properties_count_v2(self):
        """Test layer properties count with v2 structure."""
        count = get_layer_properties_count(self.config_v2)
        self.assertEqual(count, 35)
    
    def test_postgresql_connection_v2(self):
        """Test PostgreSQL connection with v2 structure."""
        connection = get_postgresql_active_connection(self.config_v2)
        self.assertEqual(connection, "")
        
        is_active = is_postgresql_active(self.config_v2)
        self.assertFalse(is_active)


class TestConfigHelpersMigrationCompatibility(unittest.TestCase):
    """Test that helpers work correctly during migration (mixed structures)."""
    
    def test_fallback_mechanism(self):
        """Test that get_config_with_fallback works correctly."""
        # Config with only old structure
        config_old = {
            "APP": {
                "OPTIONS": {
                    "GITHUB_PAGE": "https://old-url.com"
                }
            }
        }
        url = get_github_page_url(config_old)
        self.assertEqual(url, "https://old-url.com")
        
        # Config with only new structure
        config_new = {
            "app": {
                "paths": {
                    "github_page": "https://new-url.com"
                }
            }
        }
        url = get_github_page_url(config_new)
        self.assertEqual(url, "https://new-url.com")
        
        # Config with both (new should take precedence)
        config_both = {
            "app": {
                "paths": {
                    "github_page": "https://new-url.com"
                }
            },
            "APP": {
                "OPTIONS": {
                    "GITHUB_PAGE": "https://old-url.com"
                }
            }
        }
        url = get_github_page_url(config_both)
        self.assertEqual(url, "https://new-url.com")


def run_tests():
    """Run all tests and print results."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestConfigHelpersWithV1Structure))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigHelpersWithV2Structure))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigHelpersMigrationCompatibility))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

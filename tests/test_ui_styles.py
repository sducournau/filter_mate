"""
Unit tests for modules/ui_styles.py
Tests the StyleLoader class functionality
"""

import unittest
import os
import sys
from unittest.mock import Mock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.ui_styles import StyleLoader


class TestStyleLoader(unittest.TestCase):
    """Test StyleLoader class methods"""
    
    def setUp(self):
        """Clear cache before each test"""
        StyleLoader.clear_cache()
    
    def test_color_schemes_exist(self):
        """Test that default color schemes are defined"""
        self.assertIn('default', StyleLoader.COLOR_SCHEMES)
        self.assertIn('dark', StyleLoader.COLOR_SCHEMES)
        self.assertIn('light', StyleLoader.COLOR_SCHEMES)
    
    def test_color_scheme_structure(self):
        """Test that color schemes have required keys"""
        required_keys = ['color_bg_0', 'color_1', 'color_2', 'color_bg_3', 'color_3']
        
        for scheme_name, scheme in StyleLoader.COLOR_SCHEMES.items():
            for key in required_keys:
                self.assertIn(key, scheme, 
                    f"Color scheme '{scheme_name}' missing key '{key}'")
    
    def test_load_stylesheet_returns_string(self):
        """Test that load_stylesheet returns a string"""
        result = StyleLoader.load_stylesheet('default')
        self.assertIsInstance(result, str)
    
    def test_load_stylesheet_from_config(self):
        """Test loading stylesheet with config colors"""
        config_data = {
            "APP": {
                "DOCKWIDGET": {
                    "COLORS": {
                        "BACKGROUND": ["white", "#CCCCCC", "#F0F0F0", "#757575"],
                        "FONT": ["black", "black", "#a3a3a3"]
                    }
                }
            }
        }
        
        result = StyleLoader.load_stylesheet_from_config(config_data, 'default')
        self.assertIsInstance(result, str)
        
        # Check that color placeholders were replaced
        self.assertNotIn('{color_1}', result)
        self.assertNotIn('{color_2}', result)
        self.assertNotIn('{color_3}', result)
        self.assertNotIn('{color_bg_0}', result)
        self.assertNotIn('{color_bg_3}', result)
        
        # Check that actual colors are present
        self.assertIn('#CCCCCC', result)
        self.assertIn('#F0F0F0', result)
        self.assertIn('white', result)
    
    def test_load_stylesheet_from_config_handles_bad_config(self):
        """Test graceful fallback with invalid config"""
        bad_config = {"APP": {}}  # Missing required keys
        
        # Should not raise exception, should fallback to default
        result = StyleLoader.load_stylesheet_from_config(bad_config, 'default')
        self.assertIsInstance(result, str)
    
    def test_set_theme_from_config(self):
        """Test applying theme to a widget"""
        mock_widget = Mock()
        mock_widget.setStyleSheet = Mock()
        
        config_data = {
            "APP": {
                "DOCKWIDGET": {
                    "COLORS": {
                        "BACKGROUND": ["white", "#CCCCCC", "#F0F0F0", "#757575"],
                        "FONT": ["black", "black", "#a3a3a3"]
                    }
                }
            }
        }
        
        StyleLoader.set_theme_from_config(mock_widget, config_data, 'default')
        
        # Should have called setStyleSheet on the widget
        mock_widget.setStyleSheet.assert_called_once()
        
        # Check that a stylesheet string was passed
        call_args = mock_widget.setStyleSheet.call_args[0]
        self.assertEqual(len(call_args), 1)
        self.assertIsInstance(call_args[0], str)
    
    def test_cache_functionality(self):
        """Test that stylesheets are cached"""
        # First call
        result1 = StyleLoader.load_stylesheet('default')
        
        # Second call should use cache
        result2 = StyleLoader.load_stylesheet('default')
        
        self.assertEqual(result1, result2)
        self.assertIn('default', StyleLoader._styles_cache)
    
    def test_clear_cache(self):
        """Test cache clearing"""
        # Load a stylesheet
        StyleLoader.load_stylesheet('default')
        self.assertTrue(len(StyleLoader._styles_cache) > 0)
        
        # Clear cache
        StyleLoader.clear_cache()
        self.assertEqual(len(StyleLoader._styles_cache), 0)
    
    def test_get_current_theme(self):
        """Test getting current theme"""
        # Default should be 'default'
        theme = StyleLoader.get_current_theme()
        self.assertIsInstance(theme, str)


if __name__ == '__main__':
    unittest.main()

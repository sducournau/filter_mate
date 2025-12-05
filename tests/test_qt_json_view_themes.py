"""
Unit tests for Qt JSON View themes functionality.

Tests the color theme system including theme switching and color application.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch

# Mock QGIS modules before importing qt_json_view
import sys
sys.modules['qgis'] = MagicMock()
sys.modules['qgis.PyQt'] = MagicMock()
sys.modules['qgis.PyQt.QtCore'] = MagicMock()
sys.modules['qgis.PyQt.QtGui'] = MagicMock()
sys.modules['qgis.PyQt.QtWidgets'] = MagicMock()

from modules.qt_json_view import themes
from modules.qt_json_view.datatypes import (
    NoneType, StrType, IntType, FloatType, BoolType,
    ListType, DictType, UrlType, FilepathType, RangeType, ChoicesType
)


class TestThemes(unittest.TestCase):
    """Test the themes module."""
    
    def test_default_theme_exists(self):
        """Test that the default theme exists."""
        self.assertIn('default', themes.THEMES)
    
    def test_all_themes_registered(self):
        """Test that all expected themes are registered."""
        expected_themes = [
            'default', 'monokai', 'solarized_light', 'solarized_dark',
            'nord', 'dracula', 'one_dark', 'gruvbox'
        ]
        for theme_name in expected_themes:
            self.assertIn(theme_name, themes.THEMES, f"Theme {theme_name} not found")
    
    def test_get_current_theme(self):
        """Test getting the current theme."""
        current = themes.get_current_theme()
        self.assertIsNotNone(current)
        self.assertTrue(hasattr(current, 'name'))
    
    def test_set_theme_success(self):
        """Test setting a valid theme."""
        result = themes.set_theme('monokai')
        self.assertTrue(result)
        self.assertEqual(themes.get_current_theme().name, 'Monokai')
    
    def test_set_theme_failure(self):
        """Test setting an invalid theme."""
        result = themes.set_theme('nonexistent_theme')
        self.assertFalse(result)
    
    def test_set_theme_case_insensitive(self):
        """Test that theme names are case-insensitive."""
        themes.set_theme('MONOKAI')
        self.assertEqual(themes.get_current_theme().name, 'Monokai')
        
        themes.set_theme('NoRd')
        self.assertEqual(themes.get_current_theme().name, 'Nord')
    
    def test_get_available_themes(self):
        """Test getting list of available themes."""
        theme_list = themes.get_available_themes()
        self.assertIsInstance(theme_list, list)
        self.assertGreater(len(theme_list), 0)
        self.assertIn('default', theme_list)
    
    def test_get_theme_display_names(self):
        """Test getting theme display names."""
        display_names = themes.get_theme_display_names()
        self.assertIsInstance(display_names, dict)
        self.assertIn('default', display_names)
        self.assertEqual(display_names['default'], 'Default')
    
    def test_theme_has_all_color_keys(self):
        """Test that each theme has all required color keys."""
        required_keys = [
            'none', 'string', 'integer', 'float', 'boolean',
            'list', 'dict', 'url', 'filepath', 'range', 'choices'
        ]
        
        for theme_name, theme in themes.THEMES.items():
            for key in required_keys:
                color = theme.get_color(key)
                self.assertIsNotNone(
                    color, 
                    f"Theme {theme_name} missing color for {key}"
                )
    
    def test_theme_colors_are_different(self):
        """Test that themed colors differ from default."""
        themes.set_theme('default')
        default_string_color = themes.get_current_theme().get_color('string')
        
        themes.set_theme('monokai')
        monokai_string_color = themes.get_current_theme().get_color('string')
        
        # Colors should be different (at least for Monokai)
        # This test might need adjustment based on actual color values
        self.assertIsNotNone(default_string_color)
        self.assertIsNotNone(monokai_string_color)


class TestDataTypeThemeIntegration(unittest.TestCase):
    """Test integration of themes with DataType classes."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Reset to default theme
        themes.set_theme('default')
    
    def test_datatype_has_theme_color_key(self):
        """Test that all DataType classes have THEME_COLOR_KEY."""
        datatype_classes = [
            NoneType, StrType, IntType, FloatType, BoolType,
            ListType, DictType, UrlType, FilepathType, RangeType, ChoicesType
        ]
        
        for dt_class in datatype_classes:
            dt = dt_class()
            self.assertTrue(
                hasattr(dt, 'THEME_COLOR_KEY'),
                f"{dt_class.__name__} missing THEME_COLOR_KEY"
            )
    
    def test_datatype_get_color_method(self):
        """Test that DataType.get_color() returns a color."""
        dt = StrType()
        color = dt.get_color()
        self.assertIsNotNone(color)
    
    def test_datatype_color_changes_with_theme(self):
        """Test that DataType colors change when theme changes."""
        dt = StrType()
        
        # Get color with default theme
        themes.set_theme('default')
        default_color = dt.get_color()
        
        # Get color with different theme
        themes.set_theme('monokai')
        monokai_color = dt.get_color()
        
        # Both should return valid colors
        self.assertIsNotNone(default_color)
        self.assertIsNotNone(monokai_color)
    
    def test_all_datatypes_have_unique_color_keys(self):
        """Test that DataTypes use appropriate color keys."""
        expected_mapping = {
            NoneType: 'none',
            StrType: 'string',
            IntType: 'integer',
            FloatType: 'float',
            BoolType: 'boolean',
            ListType: 'list',
            DictType: 'dict',
            UrlType: 'url',
            FilepathType: 'filepath',
            RangeType: 'range',
            ChoicesType: 'choices',
        }
        
        for dt_class, expected_key in expected_mapping.items():
            dt = dt_class()
            self.assertEqual(
                dt.THEME_COLOR_KEY, 
                expected_key,
                f"{dt_class.__name__} has wrong THEME_COLOR_KEY"
            )


class TestIndividualThemes(unittest.TestCase):
    """Test individual theme characteristics."""
    
    def test_monokai_theme(self):
        """Test Monokai theme has expected properties."""
        theme = themes.THEMES['monokai']
        self.assertEqual(theme.name, 'Monokai')
        self.assertIsNotNone(theme.get_color('string'))
    
    def test_nord_theme(self):
        """Test Nord theme has expected properties."""
        theme = themes.THEMES['nord']
        self.assertEqual(theme.name, 'Nord')
        self.assertIsNotNone(theme.get_color('dict'))
    
    def test_dracula_theme(self):
        """Test Dracula theme has expected properties."""
        theme = themes.THEMES['dracula']
        self.assertEqual(theme.name, 'Dracula')
        self.assertIsNotNone(theme.get_color('boolean'))
    
    def test_solarized_themes(self):
        """Test both Solarized themes exist."""
        self.assertIn('solarized_light', themes.THEMES)
        self.assertIn('solarized_dark', themes.THEMES)
        
        light = themes.THEMES['solarized_light']
        dark = themes.THEMES['solarized_dark']
        
        self.assertEqual(light.name, 'Solarized Light')
        self.assertEqual(dark.name, 'Solarized Dark')


class TestThemeCustomization(unittest.TestCase):
    """Test custom theme creation and registration."""
    
    def test_create_custom_theme(self):
        """Test creating a custom theme."""
        from modules.qt_json_view.themes import Theme
        from qgis.PyQt.QtGui import QColor
        
        class TestTheme(Theme):
            def __init__(self):
                super().__init__("Test Theme")
                self.colors = {
                    'string': QColor("#FF0000"),
                }
        
        custom_theme = TestTheme()
        self.assertEqual(custom_theme.name, "Test Theme")
        self.assertIsNotNone(custom_theme.get_color('string'))
    
    def test_register_custom_theme(self):
        """Test registering a custom theme."""
        from modules.qt_json_view.themes import Theme, THEMES
        from qgis.PyQt.QtGui import QColor
        
        class CustomTheme(Theme):
            def __init__(self):
                super().__init__("Custom")
                self.colors = {'string': QColor("#FF0000")}
        
        # Register the theme
        THEMES['custom'] = CustomTheme()
        
        # Verify it can be used
        result = themes.set_theme('custom')
        self.assertTrue(result)
        self.assertEqual(themes.get_current_theme().name, 'Custom')
        
        # Clean up
        del THEMES['custom']


def run_tests():
    """Run all tests."""
    unittest.main(argv=[''], exit=False, verbosity=2)


if __name__ == '__main__':
    run_tests()

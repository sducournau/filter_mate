# -*- coding: utf-8 -*-
"""
Tests for UI Configuration System

Tests the dynamic UI configuration system including:
- Profile loading and switching
- Dimension retrieval
- Configuration validation
- Widget utilities
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.ui_config import UIConfig, DisplayProfile


class TestUIConfig(unittest.TestCase):
    """Test UIConfig class and profile management."""
    
    def setUp(self):
        """Reset to normal profile before each test."""
        UIConfig.set_profile(DisplayProfile.NORMAL)
    
    def test_default_profile(self):
        """Test that default profile is NORMAL."""
        self.assertEqual(UIConfig.get_profile(), DisplayProfile.NORMAL)
        self.assertEqual(UIConfig.get_profile_name(), "normal")
    
    def test_profile_switching(self):
        """Test switching between profiles."""
        # Switch to compact
        UIConfig.set_profile(DisplayProfile.COMPACT)
        self.assertEqual(UIConfig.get_profile(), DisplayProfile.COMPACT)
        self.assertEqual(UIConfig.get_profile_name(), "compact")
        
        # Switch back to normal
        UIConfig.set_profile(DisplayProfile.NORMAL)
        self.assertEqual(UIConfig.get_profile(), DisplayProfile.NORMAL)
    
    def test_button_dimensions_normal(self):
        """Test button dimensions for normal profile."""
        UIConfig.set_profile(DisplayProfile.NORMAL)
        
        # Standard button
        self.assertEqual(UIConfig.get_button_height("button"), 40)
        self.assertEqual(UIConfig.get_icon_size("button"), 20)
        
        # Action button
        self.assertEqual(UIConfig.get_button_height("action_button"), 48)
        self.assertEqual(UIConfig.get_icon_size("action_button"), 25)
        
        # Tool button
        self.assertEqual(UIConfig.get_button_height("tool_button"), 36)
        self.assertEqual(UIConfig.get_icon_size("tool_button"), 20)
    
    def test_button_dimensions_compact(self):
        """Test button dimensions for compact profile."""
        UIConfig.set_profile(DisplayProfile.COMPACT)
        
        # Standard button
        self.assertEqual(UIConfig.get_button_height("button"), 32)
        self.assertEqual(UIConfig.get_icon_size("button"), 18)
        
        # Action button
        self.assertEqual(UIConfig.get_button_height("action_button"), 36)
        self.assertEqual(UIConfig.get_icon_size("action_button"), 22)
        
        # Tool button
        self.assertEqual(UIConfig.get_button_height("tool_button"), 28)
        self.assertEqual(UIConfig.get_icon_size("tool_button"), 16)
    
    def test_spacing_normal(self):
        """Test spacing values for normal profile."""
        UIConfig.set_profile(DisplayProfile.NORMAL)
        
        self.assertEqual(UIConfig.get_spacing("small"), 5)
        self.assertEqual(UIConfig.get_spacing("medium"), 10)
        self.assertEqual(UIConfig.get_spacing("large"), 15)
        self.assertEqual(UIConfig.get_spacing("extra_large"), 20)
    
    def test_spacing_compact(self):
        """Test spacing values for compact profile."""
        UIConfig.set_profile(DisplayProfile.COMPACT)
        
        self.assertEqual(UIConfig.get_spacing("small"), 3)
        self.assertEqual(UIConfig.get_spacing("medium"), 6)
        self.assertEqual(UIConfig.get_spacing("large"), 10)
        self.assertEqual(UIConfig.get_spacing("extra_large"), 15)
    
    def test_margins_normal(self):
        """Test margin values for normal profile."""
        UIConfig.set_profile(DisplayProfile.NORMAL)
        
        tight = UIConfig.get_margins("tight")
        self.assertEqual(tight, {'top': 5, 'right': 5, 'bottom': 5, 'left': 5})
        
        normal = UIConfig.get_margins("normal")
        self.assertEqual(normal, {'top': 10, 'right': 10, 'bottom': 10, 'left': 10})
        
        loose = UIConfig.get_margins("loose")
        self.assertEqual(loose, {'top': 15, 'right': 15, 'bottom': 15, 'left': 15})
    
    def test_margins_compact(self):
        """Test margin values for compact profile."""
        UIConfig.set_profile(DisplayProfile.COMPACT)
        
        tight = UIConfig.get_margins("tight")
        self.assertEqual(tight, {'top': 3, 'right': 3, 'bottom': 3, 'left': 3})
        
        normal = UIConfig.get_margins("normal")
        self.assertEqual(normal, {'top': 6, 'right': 6, 'bottom': 6, 'left': 6})
        
        loose = UIConfig.get_margins("loose")
        self.assertEqual(loose, {'top': 10, 'right': 10, 'bottom': 10, 'left': 10})
    
    def test_padding_dict(self):
        """Test padding dictionary retrieval."""
        UIConfig.set_profile(DisplayProfile.NORMAL)
        
        button_padding = UIConfig.get_padding_dict("button")
        self.assertIsInstance(button_padding, dict)
        self.assertIn('top', button_padding)
        self.assertIn('right', button_padding)
        self.assertIn('bottom', button_padding)
        self.assertIn('left', button_padding)
    
    def test_padding_string(self):
        """Test padding CSS string generation."""
        UIConfig.set_profile(DisplayProfile.NORMAL)
        
        padding_str = UIConfig.get_padding_string("button")
        self.assertIsInstance(padding_str, str)
        self.assertRegex(padding_str, r'\d+px \d+px \d+px \d+px')
    
    def test_format_margins(self):
        """Test margin formatting for setContentsMargins()."""
        UIConfig.set_profile(DisplayProfile.NORMAL)
        
        margins_str = UIConfig.format_margins("normal")
        self.assertIsInstance(margins_str, str)
        self.assertRegex(margins_str, r'\d+, \d+, \d+, \d+')
    
    def test_get_config_component(self):
        """Test getting full component configuration."""
        UIConfig.set_profile(DisplayProfile.NORMAL)
        
        button_config = UIConfig.get_config("button")
        self.assertIsInstance(button_config, dict)
        self.assertIn('height', button_config)
        self.assertIn('icon_size', button_config)
        self.assertIn('padding', button_config)
    
    def test_get_config_key(self):
        """Test getting specific configuration key."""
        UIConfig.set_profile(DisplayProfile.NORMAL)
        
        height = UIConfig.get_config("button", "height")
        self.assertEqual(height, 40)
        
        icon_size = UIConfig.get_config("button", "icon_size")
        self.assertEqual(icon_size, 20)
    
    def test_invalid_component(self):
        """Test handling of invalid component name."""
        result = UIConfig.get_config("nonexistent_component")
        self.assertIsNone(result)
    
    def test_invalid_key(self):
        """Test handling of invalid key name."""
        result = UIConfig.get_config("button", "nonexistent_key")
        self.assertIsNone(result)
    
    def test_all_dimensions(self):
        """Test getting all dimensions for a profile."""
        UIConfig.set_profile(DisplayProfile.NORMAL)
        
        all_dims = UIConfig.get_all_dimensions()
        self.assertIsInstance(all_dims, dict)
        self.assertIn('button', all_dims)
        self.assertIn('spacing', all_dims)
        self.assertIn('margins', all_dims)
    
    def test_profile_completeness(self):
        """Test that both profiles have the same components."""
        compact_profile = UIConfig.PROFILES['compact']
        normal_profile = UIConfig.PROFILES['normal']
        
        # Both should have same keys
        self.assertEqual(set(compact_profile.keys()), set(normal_profile.keys()))
        
        # Check that major components exist
        required_components = [
            'button', 'action_button', 'tool_button',
            'input', 'combobox', 'frame', 'spacing', 'margins'
        ]
        
        for component in required_components:
            self.assertIn(component, compact_profile)
            self.assertIn(component, normal_profile)
    
    def test_compact_smaller_than_normal(self):
        """Test that compact dimensions are generally smaller than normal."""
        # Button heights
        UIConfig.set_profile(DisplayProfile.COMPACT)
        compact_button_height = UIConfig.get_button_height("button")
        
        UIConfig.set_profile(DisplayProfile.NORMAL)
        normal_button_height = UIConfig.get_button_height("button")
        
        self.assertLess(compact_button_height, normal_button_height)
        
        # Spacing
        UIConfig.set_profile(DisplayProfile.COMPACT)
        compact_spacing = UIConfig.get_spacing("medium")
        
        UIConfig.set_profile(DisplayProfile.NORMAL)
        normal_spacing = UIConfig.get_spacing("medium")
        
        self.assertLess(compact_spacing, normal_spacing)
    
    def test_load_from_config(self):
        """Test loading profile from config dictionary."""
        # Test compact loading
        config_compact = {
            "APP": {
                "DOCKWIDGET": {
                    "UI_PROFILE": "compact"
                }
            }
        }
        
        UIConfig.load_from_config(config_compact)
        self.assertEqual(UIConfig.get_profile(), DisplayProfile.COMPACT)
        
        # Test normal loading
        config_normal = {
            "APP": {
                "DOCKWIDGET": {
                    "UI_PROFILE": "normal"
                }
            }
        }
        
        UIConfig.load_from_config(config_normal)
        self.assertEqual(UIConfig.get_profile(), DisplayProfile.NORMAL)
    
    def test_load_from_config_missing_key(self):
        """Test loading when UI_PROFILE is missing from config."""
        config_missing = {
            "APP": {
                "DOCKWIDGET": {}
            }
        }
        
        # Should default to NORMAL
        UIConfig.load_from_config(config_missing)
        self.assertEqual(UIConfig.get_profile(), DisplayProfile.NORMAL)
    
    def test_load_from_config_invalid_structure(self):
        """Test loading with invalid config structure."""
        config_invalid = {"INVALID": "STRUCTURE"}
        
        # Should not crash, defaults to NORMAL
        UIConfig.load_from_config(config_invalid)
        self.assertEqual(UIConfig.get_profile(), DisplayProfile.NORMAL)


class TestUIConfigIntegration(unittest.TestCase):
    """Integration tests for UI configuration system."""
    
    def test_profile_switch_persistence(self):
        """Test that profile switches persist across calls."""
        UIConfig.set_profile(DisplayProfile.COMPACT)
        
        # Multiple calls should return consistent values
        height1 = UIConfig.get_button_height("button")
        height2 = UIConfig.get_button_height("button")
        
        self.assertEqual(height1, height2)
        self.assertEqual(height1, 32)  # Compact button height
    
    def test_mixed_component_access(self):
        """Test accessing different components in sequence."""
        UIConfig.set_profile(DisplayProfile.NORMAL)
        
        button_height = UIConfig.get_button_height("button")
        spacing = UIConfig.get_spacing("medium")
        margins = UIConfig.get_margins("normal")
        input_height = UIConfig.get_config("input", "height")
        
        # All should return valid values
        self.assertIsNotNone(button_height)
        self.assertIsNotNone(spacing)
        self.assertIsNotNone(margins)
        self.assertIsNotNone(input_height)


def run_tests():
    """Run all tests and display results."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestUIConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestUIConfigIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success status
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

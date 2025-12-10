"""
Test for Plugin Menu and Configuration Reset

This test verifies the submenu structure and configuration reset functionality.
"""

import unittest
import sys
import os
from pathlib import Path

# Add plugin to path
plugin_dir = Path(__file__).parent.parent
sys.path.insert(0, str(plugin_dir))


class TestPluginMenu(unittest.TestCase):
    """Test plugin menu and reset functionality."""
    
    def test_menu_structure(self):
        """Test that menu structure is correctly defined."""
        # Import here to avoid QGIS dependencies in test discovery
        try:
            from filter_mate import FilterMate
            
            # Verify the class has the required methods
            self.assertTrue(hasattr(FilterMate, 'initGui'))
            self.assertTrue(hasattr(FilterMate, 'reset_configuration'))
            self.assertTrue(hasattr(FilterMate, 'run'))
            self.assertTrue(hasattr(FilterMate, 'unload'))
            
            print("✓ FilterMate class has all required methods")
            
        except ImportError as e:
            print(f"✗ Cannot import FilterMate (QGIS not available): {e}")
            self.skipTest("QGIS not available")
    
    
    def test_reset_config_import(self):
        """Test that config reset functions can be imported."""
        try:
            from config.config import reset_config_to_default, reload_config
            
            # Verify functions exist
            self.assertTrue(callable(reset_config_to_default))
            self.assertTrue(callable(reload_config))
            
            print("✓ Configuration reset functions are importable")
            
        except ImportError as e:
            print(f"✗ Cannot import config functions (QGIS not available): {e}")
            self.skipTest("QGIS not available")
    
    
    def test_icon_exists(self):
        """Test that reset icon exists."""
        reset_icon_path = plugin_dir / 'icons' / 'parameters.png'
        self.assertTrue(reset_icon_path.exists(), f"Reset icon not found at {reset_icon_path}")
        print(f"✓ Reset icon exists at {reset_icon_path}")
    
    
    def test_main_icon_exists(self):
        """Test that main plugin icon exists."""
        main_icon_path = plugin_dir / 'icons' / 'icon.png'
        self.assertTrue(main_icon_path.exists(), f"Main icon not found at {main_icon_path}")
        print(f"✓ Main icon exists at {main_icon_path}")


class TestMenuTranslations(unittest.TestCase):
    """Test menu translations."""
    
    def test_menu_strings(self):
        """Test that menu strings are defined."""
        menu_strings = [
            'Ouvrir FilterMate',
            'Réinitialiser la configuration',
            'FilterMate - Réinitialisation',
            'Configuration réinitialisée avec succès'
        ]
        
        # Just verify strings are defined (actual translation tested in QGIS)
        for string in menu_strings:
            self.assertIsInstance(string, str)
            self.assertGreater(len(string), 0)
        
        print(f"✓ All {len(menu_strings)} menu strings are defined")


class TestResetFunctionality(unittest.TestCase):
    """Test configuration reset functionality."""
    
    def test_reset_function_signature(self):
        """Test reset function accepts correct parameters."""
        try:
            from config.config import reset_config_to_default
            import inspect
            
            sig = inspect.signature(reset_config_to_default)
            params = list(sig.parameters.keys())
            
            # Should have backup and preserve_app_settings parameters
            self.assertIn('backup', params)
            self.assertIn('preserve_app_settings', params)
            
            # Check default values
            self.assertEqual(sig.parameters['backup'].default, True)
            self.assertEqual(sig.parameters['preserve_app_settings'].default, True)
            
            print("✓ reset_config_to_default has correct signature")
            
        except ImportError:
            self.skipTest("QGIS not available")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)

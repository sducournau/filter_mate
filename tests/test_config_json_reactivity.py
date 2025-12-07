# -*- coding: utf-8 -*-
"""
Test JSON Tree View Reactivity

Tests that changes in the JSON tree view configuration are properly detected,
saved, and applied to the UI.

Tests:
1. itemChanged signal is connected
2. UI_PROFILE changes are detected
3. Profile changes trigger apply_dynamic_dimensions()
4. Configuration is saved when values change
5. ICONS changes still work
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import json
import os
import sys

# Add plugin path to sys.path
plugin_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if plugin_path not in sys.path:
    sys.path.insert(0, plugin_path)


class TestConfigJsonReactivity(unittest.TestCase):
    """Test configuration JSON tree view reactivity"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock QGIS dependencies
        self.mock_qgis_modules()
        
    def mock_qgis_modules(self):
        """Mock all QGIS-related modules"""
        # Create mock modules
        mock_modules = {
            'qgis': MagicMock(),
            'qgis.core': MagicMock(),
            'qgis.gui': MagicMock(),
            'qgis.utils': MagicMock(),
            'qgis.PyQt': MagicMock(),
            'qgis.PyQt.QtCore': MagicMock(),
            'qgis.PyQt.QtGui': MagicMock(),
            'qgis.PyQt.QtWidgets': MagicMock(),
            'osgeo': MagicMock(),
            'osgeo.ogr': MagicMock(),
        }
        
        # Patch sys.modules
        for module_name, module_mock in mock_modules.items():
            sys.modules[module_name] = module_mock
            
        # Setup common QGIS classes
        from qgis.PyQt import QtCore
        QtCore.Qt = MagicMock()
        QtCore.Qt.DisplayRole = 0
        QtCore.pyqtSignal = lambda *args, **kwargs: MagicMock()
        
    def test_itemChanged_signal_connected(self):
        """Test that itemChanged signal is connected to handler"""
        # This test verifies the signal connection exists in the code
        
        # Read the dockwidget file
        dockwidget_path = os.path.join(plugin_path, 'filter_mate_dockwidget.py')
        with open(dockwidget_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check that itemChanged is connected (not commented)
        self.assertIn(
            'itemChanged.connect(self.data_changed_configuration_model)',
            content,
            "itemChanged signal should be connected to data_changed_configuration_model"
        )
        
        # Ensure it's not commented out
        lines = content.split('\n')
        for line in lines:
            if 'itemChanged.connect(self.data_changed_configuration_model)' in line:
                self.assertFalse(
                    line.strip().startswith('#'),
                    "itemChanged connection should not be commented out"
                )
                
    def test_ui_profile_detection_in_handler(self):
        """Test that UI_PROFILE changes are detected in the handler"""
        
        # Read the dockwidget file
        dockwidget_path = os.path.join(plugin_path, 'filter_mate_dockwidget.py')
        with open(dockwidget_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for UI_PROFILE handling
        self.assertIn(
            "'UI_PROFILE' in items_keys_values_path",
            content,
            "Handler should detect UI_PROFILE in the path"
        )
        
        # Check that it calls apply_dynamic_dimensions
        self.assertIn(
            "self.apply_dynamic_dimensions()",
            content,
            "Handler should call apply_dynamic_dimensions() on profile change"
        )
        
    def test_profile_values_handled(self):
        """Test that all profile values (auto, compact, normal) are handled"""
        
        dockwidget_path = os.path.join(plugin_path, 'filter_mate_dockwidget.py')
        with open(dockwidget_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check handling of each profile type
        self.assertIn("== 'compact'", content, "Should handle 'compact' profile")
        self.assertIn("== 'normal'", content, "Should handle 'normal' profile")
        self.assertIn("== 'auto'", content, "Should handle 'auto' profile")
        
        # Check that DisplayProfile enum is used
        self.assertIn("DisplayProfile.COMPACT", content)
        self.assertIn("DisplayProfile.NORMAL", content)
        
    def test_configuration_saved_on_change(self):
        """Test that save_configuration_model is called"""
        
        dockwidget_path = os.path.join(plugin_path, 'filter_mate_dockwidget.py')
        with open(dockwidget_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find data_changed_configuration_model method
        method_start = content.find('def data_changed_configuration_model(')
        method_end = content.find('\n    def ', method_start + 1)
        method_content = content[method_start:method_end]
        
        # Verify save is called
        self.assertIn(
            'self.save_configuration_model()',
            method_content,
            "save_configuration_model() should be called in the handler"
        )
        
    def test_icons_handling_preserved(self):
        """Test that ICONS changes still work after modifications"""
        
        dockwidget_path = os.path.join(plugin_path, 'filter_mate_dockwidget.py')
        with open(dockwidget_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find data_changed_configuration_model method
        method_start = content.find('def data_changed_configuration_model(')
        method_end = content.find('\n    def ', method_start + 1)
        method_content = content[method_start:method_end]
        
        # Verify ICONS handling is still present
        self.assertIn(
            "'ICONS' in items_keys_values_path",
            method_content,
            "ICONS handling should still be present"
        )
        self.assertIn(
            'self.set_widget_icon(items_keys_values_path)',
            method_content,
            "set_widget_icon should still be called for ICONS changes"
        )
        
    def test_user_feedback_on_profile_change(self):
        """Test that user receives feedback when profile changes"""
        
        dockwidget_path = os.path.join(plugin_path, 'filter_mate_dockwidget.py')
        with open(dockwidget_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for user feedback message
        self.assertIn(
            'iface.messageBar().pushSuccess',
            content,
            "Should show success message to user"
        )
        self.assertIn(
            'UI profile changed',
            content,
            "Message should mention UI profile change"
        )
        
    def test_error_handling_present(self):
        """Test that error handling is implemented for profile changes"""
        
        dockwidget_path = os.path.join(plugin_path, 'filter_mate_dockwidget.py')
        with open(dockwidget_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find UI_PROFILE handling section
        ui_profile_start = content.find("if 'UI_PROFILE' in items_keys_values_path:")
        ui_profile_end = content.find("self.save_configuration_model()", ui_profile_start)
        ui_profile_section = content[ui_profile_start:ui_profile_end]
        
        # Verify try-except block
        self.assertIn('try:', ui_profile_section, "Should have try-except for error handling")
        self.assertIn('except Exception as e:', ui_profile_section, "Should catch exceptions")
        self.assertIn('logger.error', ui_profile_section, "Should log errors")


class TestUIConfigIntegration(unittest.TestCase):
    """Test integration with UIConfig system"""
    
    def test_uiconfig_available_check(self):
        """Test that UI_CONFIG_AVAILABLE flag is checked before using UIConfig"""
        
        dockwidget_path = os.path.join(plugin_path, 'filter_mate_dockwidget.py')
        with open(dockwidget_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find UI_PROFILE handling section
        ui_profile_start = content.find("if 'UI_PROFILE' in items_keys_values_path:")
        ui_profile_end = content.find("self.save_configuration_model()", ui_profile_start)
        ui_profile_section = content[ui_profile_start:ui_profile_end]
        
        # Verify UI_CONFIG_AVAILABLE is checked
        self.assertIn(
            'if UI_CONFIG_AVAILABLE:',
            ui_profile_section,
            "Should check UI_CONFIG_AVAILABLE before using UIConfig"
        )
        
    def test_config_json_has_ui_profile(self):
        """Test that config.json contains UI_PROFILE configuration"""
        
        config_path = os.path.join(plugin_path, 'config', 'config.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Check UI_PROFILE exists
        self.assertIn('APP', config)
        self.assertIn('DOCKWIDGET', config['APP'])
        self.assertIn('UI_PROFILE', config['APP']['DOCKWIDGET'])
        
        # Check available profiles are documented
        self.assertIn('UI_PROFILE_OPTIONS', config['APP']['DOCKWIDGET'])
        options = config['APP']['DOCKWIDGET']['UI_PROFILE_OPTIONS']
        self.assertIn('available_profiles', options)
        self.assertIn('auto', options['available_profiles'])
        self.assertIn('compact', options['available_profiles'])
        self.assertIn('normal', options['available_profiles'])


def run_tests():
    """Run all tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add tests
    suite.addTests(loader.loadTestsFromTestCase(TestConfigJsonReactivity))
    suite.addTests(loader.loadTestsFromTestCase(TestUIConfigIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

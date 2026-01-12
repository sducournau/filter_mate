# -*- coding: utf-8 -*-
"""
Test for Widget Migration Fix - v4.0 AttributeError Resolution

Tests the fix for:
AttributeError: 'QgsCheckableComboBoxFeaturesListPickerWidget' object has no attribute 'currentSelectedFeatures'

Author: FilterMate Team
Date: 2026-01-12
"""

import unittest
from unittest.mock import Mock, MagicMock, patch

# Mock QGIS modules before importing
import sys
sys.modules['qgis'] = MagicMock()
sys.modules['qgis.core'] = MagicMock()
sys.modules['qgis.gui'] = MagicMock()
sys.modules['qgis.PyQt'] = MagicMock()
sys.modules['qgis.PyQt.QtCore'] = MagicMock()
sys.modules['qgis.PyQt.QtWidgets'] = MagicMock()


class TestWidgetMigrationFix(unittest.TestCase):
    """Test that compatibility methods exist in new widget."""
    
    def setUp(self):
        """Setup test fixtures."""
        # Import after mocking
        from ui.widgets.custom_widgets import QgsCheckableComboBoxFeaturesListPickerWidget
        self.widget_class = QgsCheckableComboBoxFeaturesListPickerWidget
    
    def test_widget_has_currentSelectedFeatures_method(self):
        """Test that currentSelectedFeatures() method exists."""
        self.assertTrue(
            hasattr(self.widget_class, 'currentSelectedFeatures'),
            "QgsCheckableComboBoxFeaturesListPickerWidget missing currentSelectedFeatures() method"
        )
    
    def test_widget_has_currentVisibleFeatures_method(self):
        """Test that currentVisibleFeatures() method exists."""
        self.assertTrue(
            hasattr(self.widget_class, 'currentVisibleFeatures'),
            "QgsCheckableComboBoxFeaturesListPickerWidget missing currentVisibleFeatures() method"
        )
    
    def test_widget_has_currentLayer_method(self):
        """Test that currentLayer() method exists."""
        self.assertTrue(
            hasattr(self.widget_class, 'currentLayer'),
            "QgsCheckableComboBoxFeaturesListPickerWidget missing currentLayer() method"
        )
    
    def test_method_signatures_match_legacy(self):
        """Test that method signatures match legacy widget."""
        widget = self.widget_class()
        
        # Should accept no parameters (like legacy version)
        try:
            result = widget.currentSelectedFeatures()
            self.assertIn(result, [False, []], "currentSelectedFeatures should return False or list")
        except TypeError as e:
            self.fail(f"currentSelectedFeatures() signature mismatch: {e}")
        
        try:
            result = widget.currentVisibleFeatures()
            self.assertIn(result, [False, []], "currentVisibleFeatures should return False or list")
        except TypeError as e:
            self.fail(f"currentVisibleFeatures() signature mismatch: {e}")
        
        try:
            result = widget.currentLayer()
            self.assertEqual(result, False, "currentLayer should return False when no layer set")
        except TypeError as e:
            self.fail(f"currentLayer() signature mismatch: {e}")


if __name__ == '__main__':
    unittest.main()

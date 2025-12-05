#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for QGIS theme detection

This script demonstrates the theme synchronization functionality.
Run from QGIS Python console to see how FilterMate detects the active QGIS theme.
"""

import sys
import os

# Add plugin path to sys.path
plugin_path = os.path.dirname(os.path.dirname(__file__))
if plugin_path not in sys.path:
    sys.path.insert(0, plugin_path)

from modules.ui_styles import StyleLoader
from qgis.core import QgsApplication

def test_theme_detection():
    """Test QGIS theme detection"""
    print("=" * 60)
    print("FilterMate Theme Detection Test")
    print("=" * 60)
    
    # Get QGIS palette information
    palette = QgsApplication.instance().palette()
    bg_color = palette.color(palette.Window)
    
    print(f"\nQGIS Palette Information:")
    print(f"  Background RGB: ({bg_color.red()}, {bg_color.green()}, {bg_color.blue()})")
    
    # Calculate luminance
    luminance = (0.299 * bg_color.red() + 
                 0.587 * bg_color.green() + 
                 0.114 * bg_color.blue())
    print(f"  Luminance: {luminance:.1f}")
    
    # Detect theme
    detected_theme = StyleLoader.detect_qgis_theme()
    print(f"\nDetected Theme: '{detected_theme}'")
    
    # Show interpretation
    if detected_theme == 'dark':
        print("  → Plugin will use DARK theme")
        print("  → QGIS background is dark (luminance < 128)")
    else:
        print("  → Plugin will use LIGHT/DEFAULT theme")
        print("  → QGIS background is light (luminance >= 128)")
    
    print("\n" + "=" * 60)
    print("Test completed successfully!")
    print("=" * 60)
    
    return detected_theme

if __name__ == "__main__":
    # Run test
    try:
        theme = test_theme_detection()
        print(f"\n✅ Theme detection working: {theme}")
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

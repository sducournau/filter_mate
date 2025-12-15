#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick validation script for config harmonization

This script validates that the config helpers work correctly
with the current configuration structure.
"""

import json
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.config_helpers import (
    get_feedback_level,
    get_ui_action_bar_position,
    get_font_colors,
    get_background_colors,
    get_accent_colors,
    get_layer_properties_count,
    get_postgresql_active_connection,
    is_postgresql_active,
    get_github_page_url,
)


def main():
    """Run validation checks."""
    print("=" * 60)
    print("Configuration Harmonization - Validation")
    print("=" * 60)
    
    # Load current config
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
    
    if not os.path.exists(config_path):
        print(f"❌ Config file not found: {config_path}")
        return False
    
    with open(config_path, 'r') as f:
        config_data = json.load(f)
    
    print(f"\n✅ Loaded config from: {config_path}")
    print(f"   Config keys: {list(config_data.keys())}")
    
    # Test UI helpers
    print("\n" + "-" * 60)
    print("UI Configuration Helpers")
    print("-" * 60)
    
    try:
        feedback_level = get_feedback_level(config_data)
        print(f"✅ Feedback level: {feedback_level}")
    except Exception as e:
        print(f"❌ Feedback level failed: {e}")
        return False
    
    try:
        position = get_ui_action_bar_position(config_data)
        print(f"✅ Action bar position: {position}")
    except Exception as e:
        print(f"❌ Action bar position failed: {e}")
        return False
    
    # Test color helpers
    print("\n" + "-" * 60)
    print("Color Configuration Helpers")
    print("-" * 60)
    
    try:
        font_colors = get_font_colors(config_data)
        print(f"✅ Font colors: {font_colors[:3]}")  # Show first 3
    except Exception as e:
        print(f"❌ Font colors failed: {e}")
        return False
    
    try:
        bg_colors = get_background_colors(config_data)
        print(f"✅ Background colors: {bg_colors[:3]}")
    except Exception as e:
        print(f"❌ Background colors failed: {e}")
        return False
    
    try:
        accent_colors = get_accent_colors(config_data)
        print(f"✅ Accent colors: {list(accent_colors.keys())[:3]}")
    except Exception as e:
        print(f"❌ Accent colors failed: {e}")
        return False
    
    # Test project helpers
    print("\n" + "-" * 60)
    print("Project Configuration Helpers")
    print("-" * 60)
    
    try:
        layer_count = get_layer_properties_count(config_data)
        print(f"✅ Layer properties count: {layer_count}")
    except Exception as e:
        print(f"❌ Layer properties count failed: {e}")
        return False
    
    try:
        pg_connection = get_postgresql_active_connection(config_data)
        pg_active = is_postgresql_active(config_data)
        print(f"✅ PostgreSQL active: {pg_active}")
        print(f"   Connection: {pg_connection if pg_connection else '(none)'}")
    except Exception as e:
        print(f"❌ PostgreSQL helpers failed: {e}")
        return False
    
    # Test paths
    print("\n" + "-" * 60)
    print("Path Configuration Helpers")
    print("-" * 60)
    
    try:
        github_url = get_github_page_url(config_data)
        print(f"✅ GitHub page URL: {github_url}")
    except Exception as e:
        print(f"❌ GitHub URL failed: {e}")
        return False
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ All validation checks passed!")
    print("=" * 60)
    print("\nThe config helpers are working correctly with the")
    print("current configuration structure. Migration to helpers")
    print("can proceed safely.")
    print()
    
    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)

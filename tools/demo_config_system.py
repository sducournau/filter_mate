#!/usr/bin/env python3
"""
Configuration System Demo

Demonstrates the new configuration system with metadata and auto-generated widgets.

Run this script to see:
- Metadata extraction
- Widget type detection
- Validation
- Configuration groups
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.config_metadata import get_config_metadata
from modules.config_helpers import (
    get_widget_type_for_config,
    get_config_description,
    get_config_label,
    get_config_allowed_values,
    validate_config_value_with_metadata,
    get_all_configurable_paths,
    get_config_groups
)


def demo_metadata_extraction():
    """Demonstrate metadata extraction."""
    print("=" * 80)
    print("DEMO 1: Metadata Extraction")
    print("=" * 80)
    
    metadata = get_config_metadata()
    
    # Example parameter
    path = 'app.ui.profile'
    info = metadata.get_metadata(path)
    
    print(f"\nConfiguration path: {path}")
    print(f"Description: {info['description']}")
    print(f"Widget type: {info['widget_type']}")
    print(f"Data type: {info['data_type']}")
    print(f"Default value: {info['default']}")
    print(f"Allowed values: {info['validation']['allowed_values']}")
    print(f"User-friendly label: {info['user_friendly_label']}")


def demo_helper_functions():
    """Demonstrate helper functions."""
    print("\n" + "=" * 80)
    print("DEMO 2: Helper Functions")
    print("=" * 80)
    
    configs = [
        'app.auto_activate',
        'app.ui.theme.active',
        'app.buttons.icon_sizes.action',
        'app.buttons.style.background_color'
    ]
    
    for path in configs:
        print(f"\n{path}:")
        print(f"  Widget type: {get_widget_type_for_config(path)}")
        print(f"  Label: {get_config_label(path)}")
        print(f"  Description: {get_config_description(path)[:60]}...")
        allowed = get_config_allowed_values(path)
        if allowed:
            print(f"  Allowed values: {allowed}")


def demo_validation():
    """Demonstrate validation."""
    print("\n" + "=" * 80)
    print("DEMO 3: Validation")
    print("=" * 80)
    
    # Valid values
    test_cases = [
        ('app.ui.profile', 'auto', True),
        ('app.ui.profile', 'invalid', False),
        ('app.auto_activate', True, True),
        ('app.auto_activate', 'not_boolean', False),
        ('app.buttons.icon_sizes.action', 25, True),
        ('app.buttons.icon_sizes.action', 1000, False),  # Out of range
        ('app.buttons.style.background_color', '#F0F0F0', True),
        ('app.buttons.style.background_color', 'invalid', False),
    ]
    
    for path, value, expected_valid in test_cases:
        valid, error = validate_config_value_with_metadata(path, value)
        status = "✓" if valid == expected_valid else "✗"
        print(f"\n{status} {path} = {value}")
        print(f"  Valid: {valid}")
        if error:
            print(f"  Error: {error}")


def demo_config_listing():
    """Demonstrate configuration listing."""
    print("\n" + "=" * 80)
    print("DEMO 4: Configuration Listing")
    print("=" * 80)
    
    all_paths = get_all_configurable_paths()
    print(f"\nTotal configurable parameters: {len(all_paths)}")
    
    groups = get_config_groups()
    print(f"\nConfiguration groups ({len(groups)}):")
    
    for category, paths in sorted(groups.items()):
        print(f"\n{category} ({len(paths)} parameters):")
        for path in paths[:3]:  # Show first 3 only
            print(f"  - {get_config_label(path)}")
        if len(paths) > 3:
            print(f"  ... and {len(paths) - 3} more")


def demo_markdown_export():
    """Demonstrate markdown export."""
    print("\n" + "=" * 80)
    print("DEMO 5: Markdown Export")
    print("=" * 80)
    
    metadata = get_config_metadata()
    
    # Export to string (not saving to file in demo)
    markdown = metadata.export_schema_to_markdown()
    
    lines = markdown.split('\n')
    print(f"\nGenerated {len(lines)} lines of markdown documentation")
    print("\nFirst 20 lines:")
    print("\n".join(lines[:20]))
    print("\n...")


def demo_widget_type_mapping():
    """Demonstrate widget type to PyQt mapping."""
    print("\n" + "=" * 80)
    print("DEMO 6: Widget Type Mapping")
    print("=" * 80)
    
    widget_mapping = {
        'checkbox': 'QCheckBox',
        'combobox': 'QComboBox',
        'textbox': 'QLineEdit',
        'spinbox': 'QSpinBox',
        'colorpicker': 'QColorDialog + QLineEdit'
    }
    
    print("\nWidget type -> PyQt widget mapping:")
    for widget_type, qt_widget in widget_mapping.items():
        print(f"  {widget_type:12} -> {qt_widget}")
    
    # Count usage
    all_paths = get_all_configurable_paths()
    widget_counts = {}
    
    for path in all_paths:
        widget_type = get_widget_type_for_config(path)
        widget_counts[widget_type] = widget_counts.get(widget_type, 0) + 1
    
    print("\nWidget type usage:")
    for widget_type, count in sorted(widget_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {widget_type:12}: {count} parameters")


def main():
    """Run all demos."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "FilterMate Configuration System Demo" + " " * 22 + "║")
    print("╚" + "=" * 78 + "╝")
    
    try:
        demo_metadata_extraction()
        demo_helper_functions()
        demo_validation()
        demo_config_listing()
        demo_markdown_export()
        demo_widget_type_mapping()
        
        print("\n" + "=" * 80)
        print("All demos completed successfully!")
        print("=" * 80)
        print("\nNext steps:")
        print("  1. Review config/config_schema.json")
        print("  2. Check modules/config_metadata.py")
        print("  3. Explore modules/config_editor_widget.py")
        print("  4. Read docs/CONFIG_SYSTEM.md")
        print("\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Script to remove "_3" suffixes from widget names in filter_mate_dockwidget_base.ui

This script removes legacy "_3" suffixes from all widget object names in the .ui file.
After running this script, regenerate the Python file with: pyuic5 filter_mate_dockwidget_base.ui -o filter_mate_dockwidget_base.py
"""

import re
import sys
from pathlib import Path

def remove_suffixes_from_ui_file(ui_file_path):
    """
    Remove "_3" suffixes from widget names in a Qt Designer .ui file.
    
    Args:
        ui_file_path: Path to the .ui file
    
    Returns:
        tuple: (success: bool, changes_count: int, message: str)
    """
    ui_file = Path(ui_file_path)
    
    if not ui_file.exists():
        return False, 0, f"File not found: {ui_file_path}"
    
    # Read the file content
    try:
        with open(ui_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return False, 0, f"Error reading file: {e}"
    
    # Create backup
    backup_file = ui_file.with_suffix('.ui.backup')
    try:
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ Backup created: {backup_file}")
    except Exception as e:
        return False, 0, f"Error creating backup: {e}"
    
    # Define replacement patterns
    # Pattern 1: Widget names in <widget> tags: name="widgetName_3"
    # Pattern 2: Object names in <property> tags: <string>widgetName_3</string>
    # Pattern 3: References in other attributes
    
    replacements = [
        # Main widgets
        (r'name="toolBox_tabTools_3"', 'name="toolBox_tabTools"'),
        (r'name="FILTERING_3"', 'name="FILTERING"'),
        (r'name="EXPORTING_3"', 'name="EXPORTING"'),
        (r'name="CONFIGURATION_3"', 'name="CONFIGURATION"'),
        
        # Filtering section widgets
        (r'name="verticalLayout_filtering_section_3"', 'name="verticalLayout_filtering_section"'),
        (r'name="verticalLayout_filtering_container_3"', 'name="verticalLayout_filtering_container"'),
        (r'name="horizontalLayout_filtering_main_3"', 'name="horizontalLayout_filtering_main"'),
        (r'name="horizontalLayout_filtering_content_3"', 'name="horizontalLayout_filtering_content"'),
        (r'name="widget_filtering_keys_3"', 'name="widget_filtering_keys"'),
        (r'name="verticalLayout_filtering_keys_container_3"', 'name="verticalLayout_filtering_keys_container"'),
        (r'name="verticalLayout_filtering_keys_3"', 'name="verticalLayout_filtering_keys"'),
        (r'name="verticalLayout_filtering_values_3"', 'name="verticalLayout_filtering_values"'),
        (r'name="horizontalLayout_filtering_values_search_3"', 'name="horizontalLayout_filtering_values_search"'),
        (r'name="horizontalLayout_filtering_values_buttons_3"', 'name="horizontalLayout_filtering_values_buttons"'),
        
        # Filtering buttons
        (r'name="pushButton_checkable_filtering_auto_current_layer_3"', 'name="pushButton_checkable_filtering_auto_current_layer"'),
        (r'name="pushButton_checkable_filtering_layers_to_filter_3"', 'name="pushButton_checkable_filtering_layers_to_filter"'),
        (r'name="pushButton_checkable_filtering_current_layer_combine_operator_3"', 'name="pushButton_checkable_filtering_current_layer_combine_operator"'),
        (r'name="pushButton_checkable_filtering_geometric_predicates_3"', 'name="pushButton_checkable_filtering_geometric_predicates"'),
        (r'name="pushButton_checkable_filtering_buffer_value_3"', 'name="pushButton_checkable_filtering_buffer_value"'),
        (r'name="pushButton_checkable_filtering_buffer_type_3"', 'name="pushButton_checkable_filtering_buffer_type"'),
        
        # Filtering comboboxes and inputs
        (r'name="comboBox_filtering_current_layer_3"', 'name="comboBox_filtering_current_layer"'),
        (r'name="comboBox_filtering_source_layer_combine_operator_3"', 'name="comboBox_filtering_source_layer_combine_operator"'),
        (r'name="comboBox_filtering_other_layers_combine_operator_3"', 'name="comboBox_filtering_other_layers_combine_operator"'),
        (r'name="comboBox_filtering_geometric_predicates_3"', 'name="comboBox_filtering_geometric_predicates"'),
        (r'name="comboBox_filtering_buffer_type_3"', 'name="comboBox_filtering_buffer_type"'),
        (r'name="mPropertyOverrideButton_filtering_buffer_value_property_3"', 'name="mPropertyOverrideButton_filtering_buffer_value_property"'),
        (r'name="mQgsDoubleSpinBox_filtering_buffer_value_3"', 'name="mQgsDoubleSpinBox_filtering_buffer_value"'),
        
        # Exporting section widgets
        (r'name="widget_exporting_keys_3"', 'name="widget_exporting_keys"'),
        (r'name="verticalLayout_exporting_keys_container_3"', 'name="verticalLayout_exporting_keys_container"'),
        (r'name="verticalLayout_exporting_keys_3"', 'name="verticalLayout_exporting_keys"'),
        
        # Exporting buttons
        (r'name="pushButton_checkable_exporting_layers_3"', 'name="pushButton_checkable_exporting_layers"'),
        (r'name="pushButton_checkable_exporting_projection_3"', 'name="pushButton_checkable_exporting_projection"'),
        (r'name="pushButton_checkable_exporting_styles_3"', 'name="pushButton_checkable_exporting_styles"'),
        (r'name="pushButton_checkable_exporting_datatype_3"', 'name="pushButton_checkable_exporting_datatype"'),
        (r'name="pushButton_checkable_exporting_output_folder_3"', 'name="pushButton_checkable_exporting_output_folder"'),
        (r'name="pushButton_checkable_exporting_zip_3"', 'name="pushButton_checkable_exporting_zip"'),
        
        # Exporting inputs
        (r'name="mQgsProjectionSelectionWidget_exporting_projection_3"', 'name="mQgsProjectionSelectionWidget_exporting_projection"'),
        (r'name="comboBox_exporting_styles_3"', 'name="comboBox_exporting_styles"'),
        (r'name="comboBox_exporting_datatype_3"', 'name="comboBox_exporting_datatype"'),
        (r'name="checkBox_batch_exporting_output_folder_3"', 'name="checkBox_batch_exporting_output_folder"'),
        (r'name="lineEdit_exporting_output_folder_3"', 'name="lineEdit_exporting_output_folder"'),
        (r'name="checkBox_batch_exporting_zip_3"', 'name="checkBox_batch_exporting_zip"'),
        (r'name="lineEdit_exporting_zip_3"', 'name="lineEdit_exporting_zip"'),
        
        # Configuration section
        (r'name="verticalLayout_config_section_3"', 'name="verticalLayout_config_section"'),
        (r'name="verticalLayout_configurationPanel_3"', 'name="verticalLayout_configurationPanel"'),
        (r'name="buttonBox_3"', 'name="buttonBox"'),
    ]
    
    # Apply replacements
    changes_count = 0
    original_content = content
    
    for pattern, replacement in replacements:
        matches = re.findall(pattern, content)
        if matches:
            content = re.sub(pattern, replacement, content)
            changes_count += len(matches)
            print(f"  ✓ Replaced {len(matches)}x: {pattern} → {replacement}")
    
    # IMPORTANT: Use a generic regex to catch ALL remaining "_3" suffixes in name= attributes
    # This catches any name="something_3" pattern that wasn't in the explicit list above
    generic_name_pattern = r'name="([^"]+)_3"'
    
    def replace_generic_name(match):
        nonlocal changes_count
        old_name = match.group(1)
        new_name = old_name  # Remove "_3" suffix (captured without it)
        changes_count += 1
        print(f"  ✓ Replaced (generic): name=\"{old_name}_3\" → name=\"{new_name}\"")
        return f'name="{new_name}"'
    
    content = re.sub(generic_name_pattern, replace_generic_name, content)
    
    # Also replace in objectName properties (within <string> tags)
    objectname_pattern = r'<property name="objectName">\s*<string>([^<]+_3)</string>\s*</property>'
    
    def replace_objectname(match):
        nonlocal changes_count
        old_name = match.group(1)
        new_name = old_name[:-2]  # Remove "_3" suffix
        changes_count += 1
        print(f"  ✓ Replaced objectName: {old_name} → {new_name}")
        return f'<property name="objectName">\n   <string>{new_name}</string>\n  </property>'
    
    content = re.sub(objectname_pattern, replace_objectname, content)
    
    # Check if any changes were made
    if content == original_content:
        return True, 0, "No changes needed (no '_3' suffixes found)"
    
    # Write the modified content back to the file
    try:
        with open(ui_file, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        # Restore from backup on error
        try:
            with open(backup_file, 'r', encoding='utf-8') as f:
                backup_content = f.read()
            with open(ui_file, 'w', encoding='utf-8') as f:
                f.write(backup_content)
        except:
            pass
        return False, 0, f"Error writing file: {e}"
    
    return True, changes_count, "Success"


def main():
    """Main entry point."""
    # Get script directory
    script_dir = Path(__file__).parent
    ui_file = script_dir / "filter_mate_dockwidget_base.ui"
    
    print("=" * 70)
    print("Removing '_3' suffixes from FilterMate UI file")
    print("=" * 70)
    print(f"\nProcessing: {ui_file}")
    print()
    
    success, changes, message = remove_suffixes_from_ui_file(ui_file)
    
    if success:
        print()
        print("=" * 70)
        print(f"✓ SUCCESS: {changes} replacements made")
        print("=" * 70)
        print()
        print("Next steps:")
        print("  1. Verify the .ui file in Qt Designer (optional)")
        print("  2. Regenerate Python file:")
        if sys.platform == "win32":
            print("     compile_ui.bat")
        else:
            print("     pyuic5 filter_mate_dockwidget_base.ui -o filter_mate_dockwidget_base.py")
        print("  3. Test the plugin in QGIS")
        print()
        return 0
    else:
        print()
        print("=" * 70)
        print(f"✗ FAILED: {message}")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())

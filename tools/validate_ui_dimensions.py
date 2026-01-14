#!/usr/bin/env python3
"""
UI Dimensions Validation Script

Vérifie que les dimensions UIConfig sont correctement configurées à 20px.
Valide UNIQUEMENT 'combobox' et 'input' (pas les boutons, frames, etc.)

Usage: python tools/validate_ui_dimensions.py
"""

import sys
import os
import re

def main():
    """Main validation function."""
    print("=" * 70)
    print("UI DIMENSIONS VALIDATION - 20px Standard")
    print("=" * 70)
    
    # Read UIConfig file
    config_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'ui', 
        'config', 
        '__init__.py'
    )
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"❌ ERROR: UIConfig file not found at {config_path}")
        return 1
    
    # Track profiles and errors
    current_profile = None
    in_combobox_or_input = False
    current_widget = None
    errors = []
    validated = []
    
    expected_height = 20
    brace_depth = 0
    
    for i, line in enumerate(lines, start=1):
        # Count braces to track nesting depth
        brace_depth += line.count('{') - line.count('}')
        
        # Detect profile sections (only at top level)
        if brace_depth == 1:
            if "'normal':" in line.lower() or "'NORMAL':" in line:
                current_profile = "NORMAL"
                in_combobox_or_input = False
            elif "'compact':" in line.lower() or "'COMPACT':" in line:
                current_profile = "COMPACT"
                in_combobox_or_input = False
        
        # Detect ONLY combobox or input widgets (exact match)
        if current_profile and brace_depth == 2:
            if "'combobox':" in line.lower():
                current_widget = f"{current_profile} ComboBox"
                in_combobox_or_input = True
            elif "'input':" in line.lower() and "input_" not in line.lower():
                # Make sure it's exactly 'input' and not 'input_something'
                if re.match(r"\s*'input':\s*\{", line, re.IGNORECASE):
                    current_widget = f"{current_profile} Input"
                    in_combobox_or_input = True
                else:
                    in_combobox_or_input = False
            elif "}," in line or "}" in line:
                # Exiting a widget config block
                in_combobox_or_input = False
        
        # Check height values ONLY in combobox or input blocks
        if in_combobox_or_input and current_widget:
            height_match = re.search(r"'(height|min_height|max_height)':\s*(\d+)", line)
            if height_match:
                dim_type = height_match.group(1)
                value = int(height_match.group(2))
                
                full_name = f"{current_widget} {dim_type}"
                
                if value != expected_height:
                    errors.append(f"❌ Line {i}: {full_name} = {value}px (expected {expected_height}px)")
                else:
                    validated.append(f"✅ {full_name} = {value}px")
    
    # Display results
    if validated:
        print("\n📊 VALIDATED DIMENSIONS:")
        for v in validated:
            print(v)
    
    # Summary
    print("\n" + "=" * 70)
    if errors:
        print("❌ VALIDATION FAILED\n")
        for error in errors:
            print(error)
        print(f"\nTotal errors: {len(errors)}")
        print(f"Validated correctly: {len(validated)}")
        return 1
    else:
        print("✅ VALIDATION PASSED")
        print(f"\n✨ All {len(validated)} widget dimensions correctly set to {expected_height}px!")
        print("   NORMAL and COMPACT profiles are now unified.\n")
        print("   Widgets validated:")
        print("   - ComboBox (height, min_height, max_height)")
        print("   - Input (height, min_height, max_height)")
        return 0

if __name__ == "__main__":
    sys.exit(main())

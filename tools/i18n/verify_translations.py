#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to verify all tooltips and translations are correctly configured
"""

import os
import re
import xml.etree.ElementTree as ET

def check_python_tooltips(file_path):
    """Check that all tooltips in Python files use translation."""
    issues = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')
    
    # Pattern for setToolTip with hardcoded strings (not using translate)
    pattern = r'setToolTip\s*\(\s*["\']([^"\']+)["\']\s*\)'
    
    for i, line in enumerate(lines, 1):
        if 'setToolTip' in line and 'translate' not in line and 'QCoreApplication' not in line:
            match = re.search(pattern, line)
            if match:
                issues.append({
                    'line': i,
                    'text': match.group(1),
                    'code': line.strip()
                })
    
    return issues

def check_ui_tooltips(file_path):
    """Check tooltips in .ui file are in English (source language)."""
    issues = []
    
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # Find all toolTip properties
        for prop in root.iter('property'):
            if prop.get('name') == 'toolTip':
                string_elem = prop.find('string')
                if string_elem is not None and string_elem.text:
                    text = string_elem.text
                    # Check if it contains French characters or common French words
                    french_indicators = ['é', 'è', 'ê', 'à', 'ù', 'ç', 'œ', 
                                        'Sélectionner', 'Couche', 'Valeur', 
                                        'Filtrage', 'Réinitialiser']
                    
                    if any(indicator in text for indicator in french_indicators):
                        issues.append({
                            'text': text,
                            'reason': 'Contains French text'
                        })
        
    except Exception as e:
        issues.append({'error': str(e)})
    
    return issues

def check_ts_coverage(ts_file, expected_strings):
    """Check if all expected strings are in the .ts file."""
    missing = []
    
    try:
        tree = ET.parse(ts_file)
        root = tree.getroot()
        
        # Get all source strings
        sources = set()
        for context in root.findall('.//context'):
            for message in context.findall('message'):
                source = message.find('source')
                if source is not None and source.text:
                    sources.add(source.text)
        
        # Check for missing translations
        for expected in expected_strings:
            if expected not in sources:
                missing.append(expected)
    
    except Exception as e:
        return [f"Error: {e}"]
    
    return missing

def main():
    """Run all verification checks."""
    print("="*70)
    print("FilterMate Tooltip Translation Verification")
    print("="*70)
    
    # Expected tooltip strings from .ui file
    expected_tooltips = [
        "Multi-layer filtering",
        "Additive filtering for the selected layer",
        "Geospatial filtering",
        "Buffer",
        "Expression layer",
        "Geometric predicate",
        "Value in meters",
        "Select CRS for export",
        "Output format",
        "Filter",
        "Reset",
        "Layers to export",
        "Layers projection",
        "Save styles",
        "Datatype export",
        "Name of file/directory"
    ]
    
    # Expected dynamic tooltips from filter_mate_dockwidget.py
    dynamic_tooltips = [
        "Reload the plugin to apply layout changes (action bar position)",
        "Current layer: {0}",
        "No layer selected",
        "Selected layers:\n{0}",
        "Multiple layers selected",
        "No layers selected",
        "Expression:\n{0}",
        "Expression: {0}",
        "No expression defined",
        "Display expression: {0}",
        "Feature ID: {0}\nFirst attribute: {1}"
    ]
    
    all_errors = []
    
    # 1. Check Python files for hardcoded tooltips
    print("\n1. Checking filter_mate_dockwidget.py for hardcoded tooltips...")
    py_file = 'filter_mate_dockwidget.py'
    if os.path.exists(py_file):
        py_issues = check_python_tooltips(py_file)
        if py_issues:
            print(f"  ✗ Found {len(py_issues)} hardcoded tooltip(s):")
            for issue in py_issues[:5]:  # Show first 5
                print(f"    Line {issue['line']}: {issue['text']}")
            all_errors.extend(py_issues)
        else:
            print("  ✓ No hardcoded tooltips found")
    else:
        print(f"  ⚠ File not found: {py_file}")
    
    # 2. Check .ui file for French tooltips
    print("\n2. Checking filter_mate_dockwidget_base.ui for French text...")
    ui_file = 'filter_mate_dockwidget_base.ui'
    if os.path.exists(ui_file):
        ui_issues = check_ui_tooltips(ui_file)
        if ui_issues:
            print(f"  ✗ Found {len(ui_issues)} French tooltip(s):")
            for issue in ui_issues[:5]:
                if 'text' in issue:
                    print(f"    '{issue['text']}'")
            all_errors.extend(ui_issues)
        else:
            print("  ✓ All tooltips are in English")
    else:
        print(f"  ⚠ File not found: {ui_file}")
    
    # 3. Check .ts files for coverage
    print("\n3. Checking translation file coverage...")
    i18n_dir = 'i18n'
    if os.path.exists(i18n_dir):
        ts_files = [f for f in os.listdir(i18n_dir) if f.endswith('.ts')]
        
        all_expected = expected_tooltips + dynamic_tooltips
        
        for ts_file in sorted(ts_files):
            ts_path = os.path.join(i18n_dir, ts_file)
            missing = check_ts_coverage(ts_path, all_expected)
            
            if missing:
                print(f"  ✗ {ts_file}: Missing {len(missing)} translation(s)")
                for miss in missing[:3]:
                    print(f"      - {miss}")
                all_errors.append({'file': ts_file, 'missing': missing})
            else:
                print(f"  ✓ {ts_file}: All translations present")
    else:
        print(f"  ⚠ Directory not found: {i18n_dir}")
    
    # 4. Check .qm files exist
    print("\n4. Checking compiled translation files (.qm)...")
    if os.path.exists(i18n_dir):
        qm_files = [f for f in os.listdir(i18n_dir) if f.endswith('.qm')]
        ts_files = [f for f in os.listdir(i18n_dir) if f.endswith('.ts')]
        
        if len(qm_files) == len(ts_files):
            print(f"  ✓ All {len(qm_files)} .qm files present")
            
            # Check if .qm files are newer than .ts files
            for ts_file in ts_files:
                qm_file = ts_file.replace('.ts', '.qm')
                ts_path = os.path.join(i18n_dir, ts_file)
                qm_path = os.path.join(i18n_dir, qm_file)
                
                if os.path.exists(qm_path):
                    ts_mtime = os.path.getmtime(ts_path)
                    qm_mtime = os.path.getmtime(qm_path)
                    
                    if ts_mtime > qm_mtime:
                        print(f"  ⚠ {qm_file} is older than {ts_file} - needs recompilation")
        else:
            print(f"  ✗ Only {len(qm_files)}/{len(ts_files)} .qm files found")
            all_errors.append({'error': 'Missing .qm files'})
    
    # Summary
    print("\n" + "="*70)
    if all_errors:
        print(f"VERIFICATION FAILED: {len(all_errors)} issue(s) found")
        print("\nRecommendations:")
        print("1. Fix any hardcoded tooltips in Python files")
        print("2. Replace French text in .ui file with English")
        print("3. Add missing translations to .ts files")
        print("4. Recompile .ts files to .qm using lrelease or the provided script")
    else:
        print("✓ VERIFICATION PASSED: All tooltips and translations configured correctly!")
        print("\nNext steps:")
        print("1. Restart QGIS")
        print("2. Change language in QGIS settings")
        print("3. Test that tooltips appear in the selected language")
    print("="*70)

if __name__ == '__main__':
    main()

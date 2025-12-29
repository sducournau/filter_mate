#!/usr/bin/env python3
"""
Verify that all translatable strings in the source code are present in translation files.
Extracts self.tr() and QCoreApplication.translate() calls from Python files.
"""

import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict

# Base directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(SCRIPT_DIR)
I18N_DIR = os.path.join(PLUGIN_DIR, 'i18n')

# Patterns to find translatable strings
TR_PATTERNS = [
    r'self\.tr\(["\']([^"\']+)["\']\)',  # self.tr("string")
    r'self\.tr\([fru]?["\']([^"\']+)["\']\)',  # self.tr(f"string")
    r'QCoreApplication\.translate\(["\'][^"\']*["\']\s*,\s*["\']([^"\']+)["\']\)',  # QCoreApplication.translate("context", "string")
]

def extract_strings_from_python(filepath):
    """Extract translatable strings from a Python file."""
    strings = set()
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        for pattern in TR_PATTERNS:
            matches = re.findall(pattern, content, re.MULTILINE)
            for match in matches:
                # Clean up the string
                clean_string = match.strip()
                # Skip format placeholders and complex strings
                if clean_string and '{' not in clean_string:
                    strings.add(clean_string)
    except Exception as e:
        print(f"  Error reading {filepath}: {e}")
    
    return strings

def extract_strings_from_ui(filepath):
    """Extract translatable strings from a .ui file."""
    strings = set()
    
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        # Find all text and string elements
        for elem in root.iter():
            if elem.tag in ['string', 'text']:
                text = elem.text
                if text and text.strip():
                    strings.add(text.strip())
            # Find tooltips
            if elem.tag == 'property' and elem.get('name') == 'toolTip':
                for string_elem in elem.findall('string'):
                    if string_elem.text and string_elem.text.strip():
                        strings.add(string_elem.text.strip())
    except Exception as e:
        print(f"  Error reading {filepath}: {e}")
    
    return strings

def get_strings_from_ts(filepath):
    """Get all source strings from a .ts translation file."""
    strings = set()
    
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        for message in root.iter('message'):
            source = message.find('source')
            if source is not None and source.text:
                strings.add(source.text.strip())
    except Exception as e:
        print(f"  Error reading {filepath}: {e}")
    
    return strings

def scan_source_files():
    """Scan all Python and UI files for translatable strings."""
    print("Scanning source files for translatable strings...\n")
    
    all_source_strings = set()
    file_count = 0
    
    # Scan Python files
    for root, dirs, files in os.walk(PLUGIN_DIR):
        # Skip some directories
        if any(skip in root for skip in ['__pycache__', 'i18n', 'tools', 'tests', 'website']):
            continue
            
        for filename in files:
            if filename.endswith('.py'):
                filepath = os.path.join(root, filename)
                strings = extract_strings_from_python(filepath)
                if strings:
                    print(f"  Found {len(strings)} strings in {os.path.relpath(filepath, PLUGIN_DIR)}")
                    all_source_strings.update(strings)
                    file_count += 1
            
            elif filename.endswith('.ui'):
                filepath = os.path.join(root, filename)
                strings = extract_strings_from_ui(filepath)
                if strings:
                    print(f"  Found {len(strings)} strings in {os.path.relpath(filepath, PLUGIN_DIR)}")
                    all_source_strings.update(strings)
                    file_count += 1
    
    print(f"\nTotal: {len(all_source_strings)} unique strings from {file_count} files\n")
    return all_source_strings

def check_translation_files(source_strings):
    """Check which strings are missing from translation files."""
    print("Checking translation files...\n")
    
    # Get one translation file to check
    ts_files = [f for f in os.listdir(I18N_DIR) if f.endswith('.ts')]
    
    if not ts_files:
        print("ERROR: No .ts files found!")
        return
    
    # Check the English translation file
    en_file = os.path.join(I18N_DIR, 'FilterMate_en.ts')
    if os.path.exists(en_file):
        ts_strings = get_strings_from_ts(en_file)
        print(f"Translation file has {len(ts_strings)} source strings\n")
        
        # Find missing strings
        missing = source_strings - ts_strings
        extra = ts_strings - source_strings
        
        if missing:
            print(f"⚠️  MISSING {len(missing)} strings from translation files:")
            print("-" * 60)
            for s in sorted(missing):
                # Only show short strings to avoid clutter
                if len(s) < 100:
                    print(f"  - {s}")
                else:
                    print(f"  - {s[:97]}...")
            print()
        else:
            print("✓ All source strings are present in translation files!\n")
        
        if extra:
            print(f"ℹ️  {len(extra)} strings in translation files not found in source (may be legacy/dynamic strings)")
            print("-" * 60)
            for s in sorted(list(extra)[:20]):  # Show first 20
                if len(s) < 100:
                    print(f"  - {s}")
            if len(extra) > 20:
                print(f"  ... and {len(extra) - 20} more")
            print()
        
        # Summary
        print("=" * 60)
        print(f"SUMMARY:")
        print(f"  Source strings: {len(source_strings)}")
        print(f"  Translation strings: {len(ts_strings)}")
        print(f"  Missing: {len(missing)}")
        print(f"  Extra: {len(extra)}")
        print(f"  Match: {len(source_strings & ts_strings)}")
        print("=" * 60)
    else:
        print(f"ERROR: {en_file} not found!")

def main():
    """Main function."""
    print("FilterMate Translation Verification Tool")
    print("=" * 60)
    print()
    
    source_strings = scan_source_files()
    check_translation_files(source_strings)
    
    print("\nDone!")

if __name__ == "__main__":
    main()

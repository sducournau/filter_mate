#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FilterMate Translation Management Script

This script helps manage translations for the FilterMate QGIS plugin.
It can extract translatable strings and compile translations.

Usage:
    python manage_translations.py extract    # Extract strings to .ts files
    python manage_translations.py compile    # Compile .ts to .qm files
    python manage_translations.py validate   # Check translation completeness
    python manage_translations.py all        # Extract, then compile

Requirements:
    - PyQt5 tools (pylupdate5, lrelease)
    - Or Qt5 tools directly

Author: FilterMate Team
Date: December 2025
"""

import os
import sys
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

# Configuration
PLUGIN_DIR = Path(__file__).parent
I18N_DIR = PLUGIN_DIR / 'i18n'

# Languages to support
LANGUAGES = ['en', 'fr', 'pt', 'es']

# Python source files to extract strings from
PYTHON_FILES = [
    'filter_mate.py',
    'filter_mate_dockwidget.py',
    'filter_mate_app.py',
    'modules/feedback_utils.py',
    'modules/appUtils.py',
    'modules/widgets.py',
    'modules/tasks/filter_task.py',
    'modules/tasks/layer_management_task.py',
]

# UI files
UI_FILES = [
    'filter_mate_dockwidget_base.ui',
]


def find_tool(name):
    """Find a Qt tool in common locations."""
    # Try direct execution first
    try:
        result = subprocess.run([name, '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            return name
    except FileNotFoundError:
        pass
    
    # Common Qt installation paths
    common_paths = [
        # Windows
        r'C:\Qt\5.15.2\msvc2019_64\bin',
        r'C:\Qt\5.15.2\mingw81_64\bin',
        r'C:\OSGeo4W\bin',
        r'C:\OSGeo4W64\bin',
        # Linux
        '/usr/lib/qt5/bin',
        '/usr/lib/x86_64-linux-gnu/qt5/bin',
        # macOS
        '/usr/local/opt/qt@5/bin',
        '/opt/homebrew/opt/qt@5/bin',
    ]
    
    for path in common_paths:
        full_path = Path(path) / name
        if full_path.exists():
            return str(full_path)
        # Windows .exe extension
        full_path_exe = Path(path) / f'{name}.exe'
        if full_path_exe.exists():
            return str(full_path_exe)
    
    return None


def extract_strings():
    """Extract translatable strings from source files."""
    print("=" * 60)
    print("EXTRACTING TRANSLATABLE STRINGS")
    print("=" * 60)
    
    pylupdate = find_tool('pylupdate5')
    if not pylupdate:
        print("ERROR: pylupdate5 not found!")
        print("Please install PyQt5 development tools.")
        print("  pip install PyQt5-tools")
        print("  or install Qt5 development package")
        return False
    
    print(f"Using: {pylupdate}")
    
    # Build file list
    sources = []
    for f in PYTHON_FILES:
        filepath = PLUGIN_DIR / f
        if filepath.exists():
            sources.append(str(filepath))
        else:
            print(f"  Warning: {f} not found")
    
    for f in UI_FILES:
        filepath = PLUGIN_DIR / f
        if filepath.exists():
            sources.append(str(filepath))
        else:
            print(f"  Warning: {f} not found")
    
    if not sources:
        print("ERROR: No source files found!")
        return False
    
    print(f"\nProcessing {len(sources)} source files...")
    
    # Extract for each language
    for lang in LANGUAGES:
        ts_file = I18N_DIR / f'FilterMate_{lang}.ts'
        print(f"\n  Extracting for {lang.upper()}...")
        
        cmd = [pylupdate] + sources + ['-ts', str(ts_file)]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PLUGIN_DIR))
            if result.returncode == 0:
                print(f"    ✓ Created/Updated {ts_file.name}")
            else:
                print(f"    ✗ Error: {result.stderr}")
        except Exception as e:
            print(f"    ✗ Exception: {e}")
    
    print("\n" + "=" * 60)
    print("EXTRACTION COMPLETE")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Open .ts files with Qt Linguist")
    print("  2. Translate untranslated strings")
    print("  3. Run: python manage_translations.py compile")
    
    return True


def compile_translations():
    """Compile .ts files to .qm binary format."""
    print("=" * 60)
    print("COMPILING TRANSLATIONS")
    print("=" * 60)
    
    lrelease = find_tool('lrelease')
    if not lrelease:
        print("ERROR: lrelease not found!")
        print("Please install Qt5 development tools.")
        return False
    
    print(f"Using: {lrelease}")
    
    success_count = 0
    for lang in LANGUAGES:
        ts_file = I18N_DIR / f'FilterMate_{lang}.ts'
        qm_file = I18N_DIR / f'FilterMate_{lang}.qm'
        
        if not ts_file.exists():
            print(f"\n  ⚠ Skipping {lang.upper()}: {ts_file.name} not found")
            continue
        
        print(f"\n  Compiling {lang.upper()}...")
        
        cmd = [lrelease, str(ts_file), '-qm', str(qm_file)]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"    ✓ Created {qm_file.name}")
                success_count += 1
            else:
                print(f"    ✗ Error: {result.stderr}")
        except Exception as e:
            print(f"    ✗ Exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"COMPILATION COMPLETE ({success_count}/{len(LANGUAGES)} languages)")
    print("=" * 60)
    
    return success_count > 0


def validate_translations():
    """Check translation completeness for all languages."""
    print("=" * 60)
    print("VALIDATING TRANSLATIONS")
    print("=" * 60)
    
    results = {}
    
    for lang in LANGUAGES:
        ts_file = I18N_DIR / f'FilterMate_{lang}.ts'
        
        if not ts_file.exists():
            print(f"\n  ❌ {lang.upper()}: File not found")
            results[lang] = {'status': 'missing', 'completion': 0}
            continue
        
        try:
            tree = ET.parse(ts_file)
            root = tree.getroot()
            
            total = 0
            translated = 0
            unfinished = 0
            obsolete = 0
            
            for message in root.iter('message'):
                total += 1
                translation = message.find('translation')
                
                if translation is not None:
                    trans_type = translation.get('type', '')
                    
                    if trans_type == 'obsolete':
                        obsolete += 1
                    elif trans_type == 'unfinished':
                        unfinished += 1
                    elif translation.text and translation.text.strip():
                        translated += 1
            
            # Calculate completion (excluding obsolete)
            active_total = total - obsolete
            completion = (translated / active_total * 100) if active_total > 0 else 0
            
            # Status icon
            if completion == 100:
                status_icon = "✅"
                status = "complete"
            elif completion >= 80:
                status_icon = "🟡"
                status = "mostly"
            elif completion >= 50:
                status_icon = "🟠"
                status = "partial"
            else:
                status_icon = "🔴"
                status = "incomplete"
            
            print(f"\n  {status_icon} {lang.upper()}: {translated}/{active_total} ({completion:.1f}%)")
            if unfinished > 0:
                print(f"      - {unfinished} unfinished")
            if obsolete > 0:
                print(f"      - {obsolete} obsolete (ignored)")
            
            results[lang] = {
                'status': status,
                'completion': completion,
                'translated': translated,
                'total': active_total,
                'unfinished': unfinished,
                'obsolete': obsolete
            }
            
        except ET.ParseError as e:
            print(f"\n  ❌ {lang.upper()}: XML parse error - {e}")
            results[lang] = {'status': 'error', 'completion': 0}
    
    print("\n" + "=" * 60)
    
    # Summary
    complete = sum(1 for r in results.values() if r.get('status') == 'complete')
    print(f"SUMMARY: {complete}/{len(LANGUAGES)} languages complete")
    print("=" * 60)
    
    return results


def print_usage():
    """Print usage information."""
    print("""
FilterMate Translation Management Script

Usage:
    python manage_translations.py <command>

Commands:
    extract     Extract translatable strings from source files to .ts files
    compile     Compile .ts files to .qm binary format for use in QGIS
    validate    Check translation completeness for all languages
    all         Run extract, then compile

Languages supported: EN, FR, PT, ES

For more information, see docs/TOOLTIPS_I18N_PLAN.md
""")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print_usage()
        return 1
    
    command = sys.argv[1].lower()
    
    if command == 'extract':
        success = extract_strings()
    elif command == 'compile':
        success = compile_translations()
    elif command == 'validate':
        results = validate_translations()
        success = all(r.get('completion', 0) >= 80 for r in results.values())
    elif command == 'all':
        success = extract_strings()
        if success:
            success = compile_translations()
    elif command in ['-h', '--help', 'help']:
        print_usage()
        return 0
    else:
        print(f"Unknown command: {command}")
        print_usage()
        return 1
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())

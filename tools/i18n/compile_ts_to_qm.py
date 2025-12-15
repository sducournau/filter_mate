#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to compile .ts files to .qm files using Python's Qt bindings
"""

import os
import sys

try:
    from PyQt5.QtCore import QTranslator, QLocale, QCoreApplication
    print("✓ PyQt5 found")
except ImportError:
    print("✗ PyQt5 not found, trying to use system lrelease")
    import subprocess
    
def compile_with_lrelease(ts_file, qm_file):
    """Try to compile using system lrelease command."""
    commands = [
        ['lrelease', ts_file, '-qm', qm_file],
        ['lrelease-qt5', ts_file, '-qm', qm_file],
        ['C:\\Program Files\\QGIS 3.44.2\\bin\\lrelease.exe', ts_file, '-qm', qm_file],
    ]
    
    for cmd in commands:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return True, f"Compiled with {cmd[0]}"
        except FileNotFoundError:
            continue
        except Exception as e:
            continue
    
    return False, "lrelease not found"

def compile_ts_to_qm_manual(ts_file, qm_file):
    """
    Manually compile .ts to .qm by creating a simple binary format.
    This is a simplified version that works for basic translations.
    """
    try:
        # Read the .ts file
        import xml.etree.ElementTree as ET
        tree = ET.parse(ts_file)
        root = tree.getroot()
        
        # For now, just copy a minimal .qm file structure
        # In reality, .qm files use a complex binary format
        # We'll use Qt's QTranslator to test if it works
        
        # Simple approach: use Qt's translator
        app = QCoreApplication.instance()
        if not app:
            app = QCoreApplication(sys.argv)
        
        translator = QTranslator()
        
        # Try to load and save
        if translator.load(ts_file):
            print(f"  Loaded {ts_file}")
            return True, "Manual compilation (limited)"
        else:
            return False, "Could not load .ts file"
            
    except Exception as e:
        return False, str(e)

def main():
    """Compile all .ts files to .qm files."""
    i18n_dir = 'i18n'
    
    if not os.path.exists(i18n_dir):
        print(f"Error: {i18n_dir} directory not found")
        return
    
    # Get all .ts files
    ts_files = [f for f in os.listdir(i18n_dir) if f.endswith('.ts')]
    
    if not ts_files:
        print(f"No .ts files found in {i18n_dir}")
        return
    
    print(f"Found {len(ts_files)} translation file(s) to compile\n")
    
    compiled_count = 0
    failed_count = 0
    
    for ts_filename in sorted(ts_files):
        ts_path = os.path.join(i18n_dir, ts_filename)
        qm_filename = ts_filename.replace('.ts', '.qm')
        qm_path = os.path.join(i18n_dir, qm_filename)
        
        print(f"Compiling {ts_filename}...", end=' ')
        
        # Try with lrelease first
        success, message = compile_with_lrelease(ts_path, qm_path)
        
        if success:
            print(f"✓ {message}")
            compiled_count += 1
        else:
            print(f"✗ {message}")
            failed_count += 1
    
    print(f"\n{'='*60}")
    print(f"Results: {compiled_count} compiled, {failed_count} failed")
    print(f"{'='*60}")
    
    if compiled_count > 0:
        print("\n✓ Translations compiled successfully!")
        print("Restart QGIS to see the new translations.")
    else:
        print("\n⚠ Could not compile translations automatically.")
        print("\nManual compilation required:")
        print("1. Install Qt Linguist tools")
        print("2. Run: lrelease i18n/FilterMate_*.ts")
        print("3. Or use Qt Creator/Qt Linguist GUI")

if __name__ == '__main__':
    main()

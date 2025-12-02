#!/usr/bin/env python3
"""
Verify that all imports in the FilterMate plugin use correct relative import syntax.
This script checks for incorrect absolute imports that would cause ModuleNotFoundError.
"""

import os
import re
from pathlib import Path

def check_file_imports(file_path):
    """Check a Python file for incorrect imports."""
    errors = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            # Check for incorrect absolute imports
            # Pattern: "from modules." or "from config." without leading dot
            if re.match(r'^\s*from\s+(modules|config)\.', line):
                errors.append({
                    'file': file_path,
                    'line': line_num,
                    'content': line.strip(),
                    'type': 'absolute_import'
                })
    
    return errors

def scan_plugin_directory():
    """Scan the plugin directory for import issues."""
    plugin_dir = Path(__file__).parent
    all_errors = []
    
    # Files to check (plugin Python files, not test files)
    python_files = []
    
    # Root level
    for file in plugin_dir.glob('*.py'):
        if not file.name.startswith('test_'):
            python_files.append(file)
    
    # modules directory
    modules_dir = plugin_dir / 'modules'
    if modules_dir.exists():
        python_files.extend(modules_dir.glob('*.py'))
    
    # config directory
    config_dir = plugin_dir / 'config'
    if config_dir.exists():
        python_files.extend(config_dir.glob('*.py'))
    
    print("FilterMate Import Validator")
    print("=" * 50)
    print(f"Scanning {len(python_files)} Python files...\n")
    
    for py_file in python_files:
        errors = check_file_imports(py_file)
        if errors:
            all_errors.extend(errors)
    
    if all_errors:
        print(f"❌ Found {len(all_errors)} import issue(s):\n")
        for error in all_errors:
            rel_path = Path(error['file']).relative_to(plugin_dir)
            print(f"File: {rel_path}")
            print(f"Line {error['line']}: {error['content']}")
            
            # Suggest fix
            if error['type'] == 'absolute_import':
                fixed = error['content'].replace('from modules.', 'from .').replace('from config.', 'from ..')
                print(f"Suggested fix: {fixed}")
            print()
        
        return False
    else:
        print("✅ All imports are correct!")
        print("\nAll plugin files use proper relative import syntax.")
        return True

def main():
    success = scan_plugin_directory()
    
    if not success:
        print("\n" + "=" * 50)
        print("RECOMMENDATION:")
        print("Fix the imports above by using relative import syntax:")
        print("  - Same directory: from .module import ...")
        print("  - Parent directory: from ..module import ...")
        print("=" * 50)
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())

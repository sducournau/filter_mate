"""
Clear Python bytecode cache for FilterMate plugin.
Run this script to clear cached .pyc files that might cause import issues.
"""

import os
import sys
from pathlib import Path

def clear_pycache(directory):
    """Remove all __pycache__ directories and .pyc files."""
    directory = Path(directory)
    removed_count = 0
    
    # Remove __pycache__ directories
    for pycache_dir in directory.rglob('__pycache__'):
        print(f"Removing: {pycache_dir}")
        for pyc_file in pycache_dir.glob('*.pyc'):
            pyc_file.unlink()
            removed_count += 1
        pycache_dir.rmdir()
    
    # Remove .pyc files in root
    for pyc_file in directory.glob('*.pyc'):
        print(f"Removing: {pyc_file}")
        pyc_file.unlink()
        removed_count += 1
    
    return removed_count

if __name__ == '__main__':
    plugin_dir = Path(__file__).parent
    print(f"Clearing cache for FilterMate plugin in: {plugin_dir}")
    count = clear_pycache(plugin_dir)
    print(f"\nRemoved {count} cached files.")
    print("\nNow reload the FilterMate plugin in QGIS:")
    print("1. Plugin Manager > Installed > Uncheck FilterMate")
    print("2. Close QGIS completely")
    print("3. Reopen QGIS")
    print("4. Plugin Manager > Installed > Check FilterMate")

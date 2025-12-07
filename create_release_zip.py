#!/usr/bin/env python3
"""
Create distribution ZIP for FilterMate plugin
"""
import os
import zipfile
from pathlib import Path

# Patterns to exclude
EXCLUDE_PATTERNS = [
    '.git',
    '__pycache__',
    '.github',
    '.serena',
    '.vscode',
    '.DS_Store',
    '*.pyc',
    '*.pyo',
    'compile_ui.bat',
    'rebuild_ui.bat',
    'filter_mate_dockwidget_base.py.backup',
    'create_release_zip.py',  # Exclude this script itself
]

def should_exclude(file_path):
    """Check if file should be excluded based on patterns"""
    path_str = str(file_path)
    for pattern in EXCLUDE_PATTERNS:
        if pattern.startswith('*'):
            # File extension pattern
            if path_str.endswith(pattern[1:]):
                return True
        else:
            # Directory or filename pattern
            if pattern in path_str:
                return True
    return False

def create_plugin_zip():
    """Create ZIP archive for FilterMate plugin"""
    plugin_dir = Path(__file__).parent
    parent_dir = plugin_dir.parent
    zip_path = parent_dir / 'filter_mate_v2.2.2.zip'
    
    print(f"Creating ZIP archive: {zip_path}")
    print(f"From directory: {plugin_dir}")
    
    file_count = 0
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(plugin_dir):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if not should_exclude(Path(root) / d)]
            
            for file in files:
                file_path = Path(root) / file
                
                # Skip excluded files
                if should_exclude(file_path):
                    continue
                
                # Calculate archive path (relative to parent of plugin_dir)
                rel_path = file_path.relative_to(parent_dir)
                
                # Add to ZIP
                zipf.write(file_path, rel_path)
                file_count += 1
                
                if file_count % 10 == 0:
                    print(f"  Added {file_count} files...")
    
    zip_size = zip_path.stat().st_size / 1024 / 1024  # MB
    print(f"\n✓ Created {zip_path.name}")
    print(f"  Total files: {file_count}")
    print(f"  Size: {zip_size:.2f} MB")
    
    return zip_path

if __name__ == '__main__':
    create_plugin_zip()

#!/usr/bin/env python3
"""
Create distribution ZIP for FilterMate plugin
"""
import os
import re
import json
import shutil
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
    'compile_ui.sh',
    'rebuild_ui.bat',
    'filter_mate_dockwidget_base.py.backup',
    'create_release_zip.py',  # Exclude this script itself
    'website',  # Exclude website directory
    'docs',  # Exclude docs directory
    'tests',  # Exclude tests directory
]

def get_version_from_metadata():
    """Extract version from metadata.txt"""
    metadata_path = Path(__file__).parent / 'metadata.txt'
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            content = f.read()
            match = re.search(r'^version=(.+)$', content, re.MULTILINE)
            if match:
                return match.group(1).strip()
    except Exception as e:
        print(f"Warning: Could not read version from metadata.txt: {e}")
    return "unknown"

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

def clean_config_json(config_path):
    """
    Clean config.json from local-specific values before packaging.
    Returns the path to the cleaned temporary config file.
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Clean APP_SQLITE_PATH - replace with empty string
        if 'APP' in config and 'OPTIONS' in config['APP']:
            config['APP']['OPTIONS']['APP_SQLITE_PATH'] = ""
            config['APP']['OPTIONS']['FRESH_RELOAD_FLAG'] = False
        
        # Clean CURRENT_PROJECT section - reset to empty/default state
        if 'CURRENT_PROJECT' in config:
            # Clean EXPORTING section
            if 'EXPORTING' in config['CURRENT_PROJECT']:
                config['CURRENT_PROJECT']['EXPORTING'] = {
                    "HAS_LAYERS_TO_EXPORT": False,
                    "LAYERS_TO_EXPORT": [],
                    "HAS_PROJECTION_TO_EXPORT": False,
                    "PROJECTION_TO_EXPORT": "",
                    "HAS_STYLES_TO_EXPORT": False,
                    "STYLES_TO_EXPORT": "QML",
                    "HAS_DATATYPE_TO_EXPORT": False,
                    "DATATYPE_TO_EXPORT": "GPKG",
                    "HAS_OUTPUT_FOLDER_TO_EXPORT": False,
                    "OUTPUT_FOLDER_TO_EXPORT": "",
                    "HAS_ZIP_TO_EXPORT": False,
                    "ZIP_TO_EXPORT": "",
                    "BATCH_OUTPUT_FOLDER": False,
                    "BATCH_ZIP": False
                }
            
            # Clean EXPORT section (if different from EXPORTING)
            if 'EXPORT' in config['CURRENT_PROJECT']:
                config['CURRENT_PROJECT']['EXPORT'] = {
                    "HAS_LAYERS_TO_EXPORT": False,
                    "LAYERS_TO_EXPORT": [],
                    "HAS_PROJECTION_TO_EXPORT": False,
                    "PROJECTION_TO_EXPORT": "",
                    "HAS_STYLES_TO_EXPORT": False,
                    "STYLES_TO_EXPORT": "QML",
                    "HAS_DATATYPE_TO_EXPORT": False,
                    "DATATYPE_TO_EXPORT": "GPKG",
                    "HAS_OUTPUT_FOLDER_TO_EXPORT": False,
                    "OUTPUT_FOLDER_TO_EXPORT": "",
                    "HAS_ZIP_TO_EXPORT": False,
                    "ZIP_TO_EXPORT": ""
                }
            
            # Clean OPTIONS section
            if 'OPTIONS' in config['CURRENT_PROJECT']:
                config['CURRENT_PROJECT']['OPTIONS']['PROJECT_ID'] = ""
                config['CURRENT_PROJECT']['OPTIONS']['PROJECT_PATH'] = ""
                config['CURRENT_PROJECT']['OPTIONS']['PROJECT_SQLITE_PATH'] = ""
                config['CURRENT_PROJECT']['OPTIONS']['ACTIVE_POSTGRESQL'] = ""
                config['CURRENT_PROJECT']['OPTIONS']['IS_ACTIVE_POSTGRESQL'] = False
            
            # Clean layers list
            if 'layers' in config['CURRENT_PROJECT']:
                config['CURRENT_PROJECT']['layers'] = []
        
        # Create temporary cleaned config
        temp_config_path = config_path.parent / 'config_clean_temp.json'
        with open(temp_config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        
        print("  ✓ Cleaned config.json from local values")
        return temp_config_path
    
    except Exception as e:
        print(f"  ⚠ Warning: Could not clean config.json: {e}")
        return None

def create_plugin_zip():
    """Create ZIP archive for FilterMate plugin"""
    plugin_dir = Path(__file__).parent
    parent_dir = plugin_dir.parent
    
    # Get version from metadata.txt
    version = get_version_from_metadata()
    zip_path = parent_dir / f'filter_mate_v{version}.zip'
    
    print(f"Creating ZIP archive: {zip_path}")
    print(f"From directory: {plugin_dir}")
    
    # Clean config.json before packaging
    config_path = plugin_dir / 'config' / 'config.json'
    temp_config_path = None
    if config_path.exists():
        temp_config_path = clean_config_json(config_path)
    
    file_count = 0
    
    try:
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
                    
                    # Use cleaned config if this is the config.json file
                    if temp_config_path and file_path == config_path:
                        zipf.write(temp_config_path, rel_path)
                        print(f"  → Using cleaned config.json")
                    else:
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
    
    finally:
        # Clean up temporary config file
        if temp_config_path and temp_config_path.exists():
            temp_config_path.unlink()
            print("  ✓ Cleaned up temporary files")

if __name__ == '__main__':
    create_plugin_zip()

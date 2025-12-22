#!/usr/bin/env python3
"""
FilterMate QGIS Plugin Packager

This script creates a ZIP file for distributing the FilterMate QGIS plugin.
The ZIP file can be uploaded to the QGIS plugin repository or shared directly.

Usage:
    python tools/zip_plugin.py [--output-dir /path/to/output]

Output:
    Creates filter_mate_vX.X.X.zip in the specified output directory (default: dist/)
"""

import argparse
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path
from datetime import datetime


# Plugin name (must match the folder name in QGIS plugins directory)
PLUGIN_NAME = "filter_mate"

# Files and directories to EXCLUDE from the ZIP
EXCLUDE_PATTERNS = [
    # Version control
    ".git",
    ".gitignore",
    ".gitattributes",
    
    # Development tools
    ".vscode",
    ".idea",
    ".serena",
    ".bmad-core",
    ".editorconfig",
    ".mypy_cache",
    ".pytest_cache",
    ".coverage",
    "htmlcov",
    
    # Python cache
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*$py.class",
    "*.so",
    ".Python",
    
    # Build artifacts
    "build",
    "dist",
    "*.egg-info",
    
    # Testing
    "tests",
    "conftest.py",
    "test_*.py",
    "*_test.py",
    "requirements-test.txt",
    "setup_tests.bat",
    "setup_tests.sh",
    
    # Documentation & website (not needed in plugin)
    "docs",
    "website",
    ".github",
    
    # Development files
    "*.log",
    ".env",
    "*.backup",
    "*.bak",
    "*.orig",
    "*.swp",
    "*.swo",
    "*~",
    
    # OS files
    ".DS_Store",
    "Thumbs.db",
    
    # Tools directory (except if you want to include specific tools)
    "tools",
    
    # Config backups
    "config/backups",
    
    # Temporary files
    "*.tmp",
    "*.qgs~",
    "*.qgs.tmp",
]

# Files to ALWAYS include (even if they match exclude patterns)
FORCE_INCLUDE = [
    "metadata.txt",
    "LICENSE",
    "README.md",
    "CHANGELOG.md",
    "__init__.py",
    "icon.png",
]


def get_version_from_metadata(plugin_dir: Path) -> str:
    """Extract version from metadata.txt file."""
    metadata_path = plugin_dir / "metadata.txt"
    
    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.txt not found at {metadata_path}")
    
    with open(metadata_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    match = re.search(r'^version\s*=\s*(.+)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    
    raise ValueError("Version not found in metadata.txt")


def should_exclude(path: Path, base_dir: Path) -> bool:
    """Check if a path should be excluded from the ZIP."""
    relative_path = path.relative_to(base_dir)
    path_str = str(relative_path)
    name = path.name
    
    # Check force include first
    if name in FORCE_INCLUDE:
        return False
    
    for pattern in EXCLUDE_PATTERNS:
        # Exact directory/file match
        if pattern == name:
            return True
        
        # Path contains excluded directory
        if pattern in path_str.split(os.sep):
            return True
        
        # Wildcard pattern match
        if pattern.startswith("*"):
            suffix = pattern[1:]
            if name.endswith(suffix):
                return True
        
        # Path starts with pattern
        if path_str.startswith(pattern):
            return True
    
    return False


def collect_files(plugin_dir: Path) -> list:
    """Collect all files to include in the ZIP."""
    files_to_zip = []
    
    for root, dirs, files in os.walk(plugin_dir):
        root_path = Path(root)
        
        # Filter out excluded directories (modifies dirs in-place)
        dirs[:] = [d for d in dirs if not should_exclude(root_path / d, plugin_dir)]
        
        for file in files:
            file_path = root_path / file
            if not should_exclude(file_path, plugin_dir):
                files_to_zip.append(file_path)
    
    return files_to_zip


def create_zip(plugin_dir: Path, output_dir: Path, version: str) -> Path:
    """Create the plugin ZIP file."""
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # ZIP filename
    zip_filename = f"{PLUGIN_NAME}_v{version}.zip"
    zip_path = output_dir / zip_filename
    
    # Remove existing ZIP if present
    if zip_path.exists():
        zip_path.unlink()
    
    # Collect files
    files_to_zip = collect_files(plugin_dir)
    
    print(f"\n📦 Creating {zip_filename}...")
    print(f"   Source: {plugin_dir}")
    print(f"   Output: {zip_path}")
    print(f"   Files:  {len(files_to_zip)}")
    
    # Create ZIP file
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for file_path in sorted(files_to_zip):
            # Archive name: plugin_name/relative/path
            relative_path = file_path.relative_to(plugin_dir)
            archive_name = f"{PLUGIN_NAME}/{relative_path}"
            
            zf.write(file_path, archive_name)
            print(f"   + {relative_path}")
    
    # Get ZIP size
    zip_size = zip_path.stat().st_size
    zip_size_mb = zip_size / (1024 * 1024)
    
    print(f"\n✅ Created: {zip_path}")
    print(f"   Size: {zip_size_mb:.2f} MB ({zip_size:,} bytes)")
    
    return zip_path


def verify_zip(zip_path: Path) -> bool:
    """Verify the created ZIP file is valid."""
    print("\n🔍 Verifying ZIP file...")
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Check for corruption
            bad_file = zf.testzip()
            if bad_file:
                print(f"   ❌ Corrupted file: {bad_file}")
                return False
            
            # Check required files
            names = zf.namelist()
            required = [
                f"{PLUGIN_NAME}/metadata.txt",
                f"{PLUGIN_NAME}/__init__.py",
                f"{PLUGIN_NAME}/filter_mate.py",
            ]
            
            for req in required:
                if req not in names:
                    print(f"   ❌ Missing required file: {req}")
                    return False
            
            print(f"   ✅ ZIP is valid")
            print(f"   ✅ Contains {len(names)} files")
            return True
            
    except zipfile.BadZipFile:
        print("   ❌ Invalid ZIP file")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Package FilterMate QGIS plugin for distribution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python tools/zip_plugin.py
    python tools/zip_plugin.py --output-dir ~/Desktop
    python tools/zip_plugin.py -o ./releases
        """
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=Path,
        default=None,
        help="Output directory for the ZIP file (default: dist/ in plugin directory)"
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip ZIP verification"
    )
    
    args = parser.parse_args()
    
    # Determine plugin directory (script is in tools/)
    script_dir = Path(__file__).parent.resolve()
    plugin_dir = script_dir.parent
    
    # Verify we're in the right place
    if not (plugin_dir / "metadata.txt").exists():
        print("❌ Error: metadata.txt not found. Run this script from the plugin directory.")
        sys.exit(1)
    
    # Get version
    try:
        version = get_version_from_metadata(plugin_dir)
        print(f"\n🔖 Plugin version: {version}")
    except Exception as e:
        print(f"❌ Error reading version: {e}")
        sys.exit(1)
    
    # Set output directory
    output_dir = args.output_dir or (plugin_dir / "dist")
    
    # Create ZIP
    try:
        zip_path = create_zip(plugin_dir, output_dir, version)
    except Exception as e:
        print(f"❌ Error creating ZIP: {e}")
        sys.exit(1)
    
    # Verify ZIP
    if not args.no_verify:
        if not verify_zip(zip_path):
            sys.exit(1)
    
    print(f"\n🎉 Plugin packaged successfully!")
    print(f"   Upload to: https://plugins.qgis.org/plugins/")
    print(f"   Or install via: Plugins > Manage and Install Plugins > Install from ZIP")


if __name__ == "__main__":
    main()

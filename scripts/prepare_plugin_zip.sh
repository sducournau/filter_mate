#!/bin/bash
# =============================================================================
# FilterMate - Plugin ZIP Preparation Script
# =============================================================================
# Creates a clean ZIP archive ready for upload to plugins.qgis.org
#
# Usage:
#   cd <plugin-root>
#   bash scripts/prepare_plugin_zip.sh
#
# Output:
#   dist/filter_mate_v<VERSION>.zip
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLUGIN_NAME="filter_mate"

# Extract version from metadata.txt
VERSION=$(grep "^version=" "$PLUGIN_DIR/metadata.txt" | cut -d= -f2 | tr -d '[:space:]')
if [ -z "$VERSION" ]; then
    echo "ERROR: Could not extract version from metadata.txt"
    exit 1
fi

DIST_DIR="$PLUGIN_DIR/dist"
BUILD_DIR="$DIST_DIR/build_tmp"
ZIP_NAME="${PLUGIN_NAME}_v${VERSION}.zip"
ZIP_PATH="$DIST_DIR/$ZIP_NAME"

echo "============================================"
echo "  FilterMate Plugin ZIP Builder v${VERSION}"
echo "============================================"
echo ""

# --- Step 1: Clean previous build ---
echo "[1/7] Cleaning previous build artifacts..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/$PLUGIN_NAME"
mkdir -p "$DIST_DIR"

# --- Step 2: Copy plugin files ---
echo "[2/7] Copying plugin files..."
rsync -a --quiet \
    --exclude='.git' \
    --exclude='.git/**' \
    --exclude='.github' \
    --exclude='.github/**' \
    --exclude='.vscode' \
    --exclude='.vscode/**' \
    --exclude='.claude' \
    --exclude='.claude/**' \
    --exclude='.serena' \
    --exclude='.serena/**' \
    --exclude='_bmad' \
    --exclude='_bmad/**' \
    --exclude='_bmad-output' \
    --exclude='_bmad-output/**' \
    --exclude='__pycache__' \
    --exclude='**/__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='*.py[cod]' \
    --exclude='.mcp.json' \
    --exclude='.pml.json' \
    --exclude='.pml' \
    --exclude='.gitignore' \
    --exclude='.gitattributes' \
    --exclude='.DS_Store' \
    --exclude='Thumbs.db' \
    --exclude='*.swp' \
    --exclude='*.swo' \
    --exclude='*~' \
    --exclude='*.log' \
    --exclude='*.env' \
    --exclude='*.backup' \
    --exclude='*.bak' \
    --exclude='*.orig' \
    --exclude='dist' \
    --exclude='dist/**' \
    --exclude='build' \
    --exclude='build/**' \
    --exclude='scripts' \
    --exclude='scripts/**' \
    --exclude='*.egg-info' \
    --exclude='*.egg-info/**' \
    --exclude='.pytest_cache' \
    --exclude='.pytest_cache/**' \
    --exclude='.coverage' \
    --exclude='htmlcov' \
    --exclude='htmlcov/**' \
    --exclude='.mypy_cache' \
    --exclude='.mypy_cache/**' \
    --exclude='.ruff_cache' \
    --exclude='.ruff_cache/**' \
    --exclude='coverage' \
    --exclude='coverage/**' \
    --exclude='pytest.ini' \
    --exclude='setup.cfg' \
    --exclude='config/backups' \
    --exclude='config/backups/**' \
    --exclude='logs/*.log' \
    --exclude='logs/.gitkeep' \
    --exclude='examples' \
    --exclude='examples/**' \
    --exclude='*.code-workspace' \
    --exclude='*.sqlite-wal' \
    --exclude='*.sqlite-shm' \
    --exclude='diagnose_*.py' \
    --exclude='test_*.py' \
    "$PLUGIN_DIR/" "$BUILD_DIR/$PLUGIN_NAME/"

# --- Step 3: Strip trailing whitespace ---
echo "[3/7] Stripping trailing whitespace from Python files..."
find "$BUILD_DIR/$PLUGIN_NAME" -name "*.py" -type f -exec \
    python3 -c "
import sys, re
for path in sys.argv[1:]:
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    cleaned = re.sub(r'[ \t]+\n', '\n', content)
    if cleaned != content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(cleaned)
" {} +

# --- Step 4: Fix file permissions ---
echo "[4/7] Setting correct file permissions..."
find "$BUILD_DIR/$PLUGIN_NAME" -type f -name "*.py" -exec chmod 644 {} +
find "$BUILD_DIR/$PLUGIN_NAME" -type f -name "*.txt" -exec chmod 644 {} +
find "$BUILD_DIR/$PLUGIN_NAME" -type f -name "*.md" -exec chmod 644 {} +
find "$BUILD_DIR/$PLUGIN_NAME" -type f -name "*.ui" -exec chmod 644 {} +
find "$BUILD_DIR/$PLUGIN_NAME" -type f -name "*.qrc" -exec chmod 644 {} +
find "$BUILD_DIR/$PLUGIN_NAME" -type f -name "*.png" -exec chmod 644 {} +
find "$BUILD_DIR/$PLUGIN_NAME" -type f -name "*.svg" -exec chmod 644 {} +
find "$BUILD_DIR/$PLUGIN_NAME" -type f -name "*.ts" -exec chmod 644 {} +
find "$BUILD_DIR/$PLUGIN_NAME" -type f -name "*.qm" -exec chmod 644 {} +
find "$BUILD_DIR/$PLUGIN_NAME" -type d -exec chmod 755 {} +

# --- Step 5: Remove empty directories ---
echo "[5/7] Removing empty directories..."
find "$BUILD_DIR/$PLUGIN_NAME" -type d -empty -delete 2>/dev/null || true

# --- Step 6: Create ZIP ---
echo "[6/7] Creating ZIP archive..."
rm -f "$ZIP_PATH"
if command -v zip &> /dev/null; then
    (cd "$BUILD_DIR" && zip -r -q "$ZIP_PATH" "$PLUGIN_NAME")
else
    echo "  'zip' not found, using Python fallback..."
    python3 -c "
import zipfile, os, sys
build_dir = sys.argv[1]
zip_path = sys.argv[2]
plugin_name = sys.argv[3]
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(os.path.join(build_dir, plugin_name)):
        for f in files:
            full_path = os.path.join(root, f)
            arcname = os.path.relpath(full_path, build_dir)
            zf.write(full_path, arcname)
print(f'  Created {zip_path}')
" "$BUILD_DIR" "$ZIP_PATH" "$PLUGIN_NAME"
fi

# --- Step 7: Cleanup and report ---
echo "[7/7] Cleaning up..."
rm -rf "$BUILD_DIR"

# Stats
ZIP_SIZE=$(du -h "$ZIP_PATH" | cut -f1)
FILE_COUNT=$(python3 -c "import zipfile; z=zipfile.ZipFile('$ZIP_PATH'); print(len(z.namelist()))")
PY_COUNT=$(python3 -c "import zipfile; z=zipfile.ZipFile('$ZIP_PATH'); print(len([n for n in z.namelist() if n.endswith('.py')]))")

echo ""
echo "============================================"
echo "  Build complete!"
echo "============================================"
echo "  Version:    $VERSION"
echo "  Output:     $ZIP_PATH"
echo "  Size:       $ZIP_SIZE"
echo "  Files:      $FILE_COUNT total ($PY_COUNT Python)"
echo "============================================"
echo ""
echo "Ready for upload to plugins.qgis.org"

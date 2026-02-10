#!/bin/bash
# Script to compile .ui files to Python with pyuic5
# Usage: ./compile_ui.sh

echo "============================================================"
echo "FilterMate UI Compilation"
echo "============================================================"
echo ""

# Get script directory (plugin root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Working directory: $SCRIPT_DIR"
echo ""

# UI file to compile
UI_FILE="filter_mate_dockwidget_base.ui"
PY_FILE="filter_mate_dockwidget_base.py"

# Check if .ui file exists
if [ ! -f "$UI_FILE" ]; then
    echo "ERROR: $UI_FILE not found"
    exit 1
fi

echo "Source file: $UI_FILE"
echo "Target file: $PY_FILE"
echo ""

# Create backup of existing .py file
if [ -f "$PY_FILE" ]; then
    echo "Creating backup: ${PY_FILE}.backup"
    cp "$PY_FILE" "${PY_FILE}.backup"
fi

echo ""
echo "Running pyuic5..."
echo ""

# Try to find pyuic5
if command -v pyuic5 &> /dev/null; then
    PYUIC5_CMD="pyuic5"
elif command -v python3 &> /dev/null; then
    # Try using python3 -m PyQt5.uic.pyuic
    PYUIC5_CMD="python3 -m PyQt5.uic.pyuic"
else
    echo "ERROR: pyuic5 not found. Please install PyQt5 tools:"
    echo "  pip install PyQt5"
    echo "  # or on Ubuntu/Debian:"
    echo "  sudo apt install pyqt5-dev-tools"
    exit 1
fi

# Run pyuic5
$PYUIC5_CMD -x "$UI_FILE" -o "$PY_FILE"

# Check result
if [ $? -eq 0 ]; then
    echo ""
    echo "============================================================"
    echo "SUCCESS: File compiled successfully!"
    echo "============================================================"
    echo ""
    echo "Generated file: $PY_FILE"
    echo ""
    
    # Show file info
    if [ -f "$PY_FILE" ]; then
        echo "File size: $(wc -l < "$PY_FILE") lines"
    fi
else
    echo ""
    echo "============================================================"
    echo "ERROR: Compilation failed"
    echo "============================================================"
    echo ""
    
    # Restore backup if exists
    if [ -f "${PY_FILE}.backup" ]; then
        echo "Restoring backup..."
        cp "${PY_FILE}.backup" "$PY_FILE"
        echo "Backup restored."
    fi
    exit 1
fi

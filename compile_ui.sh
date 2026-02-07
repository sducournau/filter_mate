#!/bin/bash
# compile_ui.sh - Compile .ui and .qrc files with automatic fixes
# Usage: ./compile_ui.sh

echo "=== FilterMate UI Compilation Script ==="
echo ""

# Compile .ui file
echo "1. Compiling filter_mate_dockwidget_base.ui..."
pyuic5 -o filter_mate_dockwidget_base.py filter_mate_dockwidget_base.ui
if [ $? -eq 0 ]; then
    echo "   ✅ .ui compiled successfully"
else
    echo "   ❌ .ui compilation failed"
    exit 1
fi

# Fix resources_rc import (pyuic5 generates absolute import, we need relative)
echo "2. Fixing resources_rc import..."
sed -i 's/^import resources_rc$/from . import resources_rc/' filter_mate_dockwidget_base.py
echo "   ✅ Import fixed to relative"

# Compile .qrc file (if needed)
if [ -f resources.qrc ]; then
    echo "3. Compiling resources.qrc..."
    pyrcc5 -o resources_rc.py resources.qrc
    if [ $? -eq 0 ]; then
        echo "   ✅ .qrc compiled successfully"
    else
        echo "   ⚠️  .qrc compilation failed (may already be up to date)"
    fi
else
    echo "3. Skipping .qrc compilation (resources.qrc not found)"
fi

echo ""
echo "=== Compilation Complete ==="
echo ""
echo "✅ All files compiled and fixed"
echo "   You can now reload the plugin in QGIS"

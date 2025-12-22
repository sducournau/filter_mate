#!/bin/bash
# FilterMate QGIS Plugin - ZIP Packaging Script
# 
# Usage: ./tools/zip_plugin.sh [output_dir]
#
# This script creates a distribution-ready ZIP file for the FilterMate QGIS plugin.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(dirname "$SCRIPT_DIR")"

echo "🔧 FilterMate Plugin Packager"
echo "=============================="

# Check Python availability
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo "❌ Python not found. Please install Python 3."
    exit 1
fi

echo "Using: $($PYTHON --version)"

# Run the Python script with any arguments passed
cd "$PLUGIN_DIR"

if [ -n "$1" ]; then
    $PYTHON tools/zip_plugin.py --output-dir "$1"
else
    $PYTHON tools/zip_plugin.py
fi

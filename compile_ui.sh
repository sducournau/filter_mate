#!/bin/bash
# Script de compilation UI pour FilterMate (Linux/WSL)
# Utilise pyuic5 depuis l'environnement QGIS Windows via WSL

echo "============================================================"
echo "FilterMate UI - Compilation"
echo "============================================================"
echo ""

# Chemin vers OSGeo4W sous Windows
OSGEO_PATH="/mnt/c/Program Files/QGIS 3.44.5"
PYUIC5_PATH="${OSGEO_PATH}/apps/Python312/Scripts/pyuic5.exe"

# Si pyuic5 n'est pas trouvé dans OSGeo4W, essayer avec le système local
if [ ! -f "$PYUIC5_PATH" ]; then
    echo "OSGeo4W pyuic5 introuvable, tentative avec pyuic5 système..."
    PYUIC5_CMD="pyuic5"
else
    PYUIC5_CMD="$PYUIC5_PATH"
fi

# Vérifier que le fichier .ui existe
if [ ! -f "filter_mate_dockwidget_base.ui" ]; then
    echo "ERREUR: filter_mate_dockwidget_base.ui introuvable"
    exit 1
fi

# Backup du .py existant
if [ -f "filter_mate_dockwidget_base.py" ]; then
    echo "Création backup .py..."
    cp -f "filter_mate_dockwidget_base.py" "filter_mate_dockwidget_base.py.backup"
fi

# Compilation
echo "Compilation avec pyuic5..."
echo "Commande: $PYUIC5_CMD -x filter_mate_dockwidget_base.ui -o filter_mate_dockwidget_base.py"
echo ""

if command -v pyuic5 &> /dev/null; then
    pyuic5 -x filter_mate_dockwidget_base.ui -o filter_mate_dockwidget_base.py
    RESULT=$?
else
    echo "ERREUR: pyuic5 n'est pas installé ou accessible"
    echo ""
    echo "Solutions possibles:"
    echo "1. Installer PyQt5 tools: pip install pyqt5-tools"
    echo "2. Utiliser le script rebuild_ui.bat depuis Windows"
    echo "3. Installer QGIS sous WSL"
    exit 1
fi

if [ $RESULT -eq 0 ]; then
    echo ""
    echo "============================================================"
    echo "SUCCÈS: UI compilée avec succès!"
    echo "============================================================"
    echo ""
    echo "Fichiers générés:"
    echo "  - filter_mate_dockwidget_base.py (compilé)"
    echo "  - filter_mate_dockwidget_base.py.backup (backup)"
    echo ""
    
    # Apply PyQt5 -> qgis.PyQt fix
    echo "Application du correctif PyQt5 -> qgis.PyQt..."
    python3 fix_compiled_ui.py filter_mate_dockwidget_base.py
    echo ""
else
    echo ""
    echo "============================================================"
    echo "ERREUR: Échec compilation"
    echo "============================================================"
    echo ""
    if [ -f "filter_mate_dockwidget_base.py.backup" ]; then
        echo "Restauration du backup..."
        cp -f "filter_mate_dockwidget_base.py.backup" "filter_mate_dockwidget_base.py"
    fi
    exit 1
fi

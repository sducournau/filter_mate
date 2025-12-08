#!/bin/bash
# Script pour compiler le fichier .ui avec l'environnement QGIS OSGeo4W
# Usage: ./compile_ui.sh

echo "============================================================"
echo "Compilation UI FilterMate avec OSGeo4W"
echo "============================================================"
echo ""

# Chemin vers OSGeo4W.bat (accessible depuis WSL)
OSGEO4W_BAT="/mnt/c/Program Files/QGIS 3.44.5/OSGeo4W.bat"

# Vérifier que OSGeo4W.bat existe
if [ ! -f "$OSGEO4W_BAT" ]; then
    echo "ERREUR: OSGeo4W.bat introuvable à l'emplacement:"
    echo "$OSGEO4W_BAT"
    echo ""
    echo "Veuillez ajuster le chemin dans le script."
    exit 1
fi

# Convertir le chemin WSL en chemin Windows
PLUGIN_DIR=$(pwd)
WIN_PLUGIN_DIR=$(wslpath -w "$PLUGIN_DIR")

echo "Répertoire du plugin: $WIN_PLUGIN_DIR"
echo ""

# Fichiers à compiler
UI_FILE="filter_mate_dockwidget_base.ui"
PY_FILE="filter_mate_dockwidget_base.py"

# Vérifier que le fichier .ui existe
if [ ! -f "$UI_FILE" ]; then
    echo "ERREUR: Fichier $UI_FILE introuvable"
    exit 1
fi

echo "Compilation de $UI_FILE..."
echo ""

# Exécuter la compilation via cmd.exe
# On utilise cmd.exe pour appeler OSGeo4W.bat avec les bonnes commandes
cmd.exe /c "\"C:\\Program Files\\QGIS 3.44.5\\OSGeo4W.bat\" python -m PyQt5.uic.pyuic -x \"$WIN_PLUGIN_DIR\\$UI_FILE\" -o \"$WIN_PLUGIN_DIR\\$PY_FILE\""

# Vérifier le code de retour
if [ $? -eq 0 ]; then
    echo ""
    echo "============================================================"
    echo "SUCCESS: Fichier $PY_FILE généré avec succès!"
    echo "============================================================"
    echo ""
    echo "Le fichier $PY_FILE a été mis à jour."
    echo "Vous pouvez maintenant recharger le plugin dans QGIS."
else
    echo ""
    echo "============================================================"
    echo "ERREUR: La compilation a échoué"
    echo "============================================================"
    exit 1
fi

# Compilation du fichier resources.qrc si nécessaire
if [ -f "resources.qrc" ]; then
    echo ""
    echo "Compilation de resources.qrc..."
    cmd.exe /c "\"C:\\Program Files\\QGIS 3.44.5\\OSGeo4W.bat\" pyrcc5 -o \"$WIN_PLUGIN_DIR\\resources.py\" \"$WIN_PLUGIN_DIR\\resources.qrc\""
    
    if [ $? -eq 0 ]; then
        echo "SUCCESS: resources.py généré avec succès!"
    else
        echo "ERREUR: La compilation de resources.qrc a échoué"
    fi
fi

echo ""
echo "Terminé!"

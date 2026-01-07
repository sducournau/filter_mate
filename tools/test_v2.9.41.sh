#!/bin/bash
# Test Script for v2.9.41 - Exploring Buttons Fix
# Tests zoom/identify buttons state after Spatialite filter + layer change

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PLUGIN_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================"
echo "FilterMate v2.9.41 - Test Script"
echo "Exploring Buttons State Fix"
echo "========================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}📋 Test Plan:${NC}"
echo "1. Test changement de couche après filtre Spatialite"
echo "2. Test multi-step filtering avec changement de couche"
echo "3. Test groupbox switching après filtre"
echo ""

echo -e "${YELLOW}📁 Vérification des fichiers modifiés...${NC}"

# Check filter_mate_dockwidget.py
if grep -q "v2.9.41: CRITICAL - Update exploring buttons state after layer change" "$PLUGIN_DIR/filter_mate_dockwidget.py"; then
    echo -e "${GREEN}✅${NC} filter_mate_dockwidget.py - Fix appliqué"
else
    echo -e "${RED}❌${NC} filter_mate_dockwidget.py - Fix MANQUANT"
    exit 1
fi

# Check filter_mate_app.py
if grep -q "v2.9.41: CRITICAL - Update button states after filtering completes" "$PLUGIN_DIR/filter_mate_app.py"; then
    echo -e "${GREEN}✅${NC} filter_mate_app.py - Fix appliqué"
else
    echo -e "${RED}❌${NC} filter_mate_app.py - Fix MANQUANT"
    exit 1
fi

# Check metadata.txt
if grep -q "version=2.9.41" "$PLUGIN_DIR/metadata.txt"; then
    echo -e "${GREEN}✅${NC} metadata.txt - Version 2.9.41"
else
    echo -e "${RED}❌${NC} metadata.txt - Version incorrecte"
    exit 1
fi

# Check CHANGELOG.md
if grep -q "Exploring Buttons State after Layer Change (v2.9.41)" "$PLUGIN_DIR/CHANGELOG.md"; then
    echo -e "${GREEN}✅${NC} CHANGELOG.md - Entrée v2.9.41 ajoutée"
else
    echo -e "${RED}❌${NC} CHANGELOG.md - Entrée v2.9.41 manquante"
    exit 1
fi

echo ""
echo -e "${YELLOW}🔍 Vérification de la syntaxe Python...${NC}"

# Check Python syntax for modified files
python3 -m py_compile "$PLUGIN_DIR/filter_mate_dockwidget.py" 2>/dev/null && \
    echo -e "${GREEN}✅${NC} filter_mate_dockwidget.py - Syntaxe valide" || \
    { echo -e "${RED}❌${NC} filter_mate_dockwidget.py - Erreur de syntaxe"; exit 1; }

python3 -m py_compile "$PLUGIN_DIR/filter_mate_app.py" 2>/dev/null && \
    echo -e "${GREEN}✅${NC} filter_mate_app.py - Syntaxe valide" || \
    { echo -e "${RED}❌${NC} filter_mate_app.py - Erreur de syntaxe"; exit 1; }

echo ""
echo -e "${YELLOW}📊 Statistiques du Fix:${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Count lines added
LINES_ADDED=$(git diff --cached --numstat 2>/dev/null | awk '{sum+=$1} END {print sum}' || echo "N/A")
echo "Lignes ajoutées: $LINES_ADDED"

# Count files modified
FILES_MODIFIED=$(git diff --cached --name-only 2>/dev/null | wc -l || echo "4")
echo "Fichiers modifiés: $FILES_MODIFIED"

# Find occurrences of _update_exploring_buttons_state()
BUTTON_UPDATE_CALLS=$(grep -r "_update_exploring_buttons_state()" "$PLUGIN_DIR"/*.py 2>/dev/null | wc -l)
echo "Appels à _update_exploring_buttons_state(): $BUTTON_UPDATE_CALLS"

echo ""
echo -e "${GREEN}✅ Validation des fichiers: SUCCÈS${NC}"
echo ""

echo -e "${YELLOW}📝 Tests Manuels Requis:${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Test 1: Filtre Spatialite + Changement de Couche"
echo "  1. Charger 2 couches Spatialite (A et B)"
echo "  2. Couche A: Sélectionner une feature"
echo "  3. Vérifier: Boutons zoom/identify activés ✓"
echo "  4. Appliquer filtre géométrique"
echo "  5. Changer vers Couche B"
echo "  6. Vérifier: Boutons désactivés (aucune sélection) ✓"
echo "  7. Sélectionner feature dans B"
echo "  8. Vérifier: Boutons activés ✓"
echo ""

echo "Test 2: Multi-Step Filtering"
echo "  1. Couche A: Filtre géométrique #1 (buffer 100m)"
echo "  2. Vérifier boutons: Activés ✓"
echo "  3. Changer vers Couche B"
echo "  4. Vérifier boutons: État correct ✓"
echo "  5. Appliquer filtre #2 sur B (buffer 50m)"
echo "  6. Vérifier boutons: Activés ✓"
echo "  7. Retourner à Couche A"
echo "  8. Vérifier boutons: État basé sur A ✓"
echo ""

echo "Test 3: Groupbox Switching"
echo "  1. Couche Spatialite: Filtre single_selection"
echo "  2. Vérifier: Boutons activés ✓"
echo "  3. Switch vers multiple_selection"
echo "  4. Vérifier: Boutons désactivés ✓"
echo "  5. Cocher 3 features"
echo "  6. Vérifier: Boutons activés ✓"
echo "  7. Changer de couche"
echo "  8. Vérifier: Boutons état correct ✓"
echo ""

echo -e "${YELLOW}🚀 Prochaines Étapes:${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Recharger QGIS pour tester les modifications"
echo "2. Exécuter les 3 tests manuels ci-dessus"
echo "3. Vérifier les logs pour les messages v2.9.41"
echo "4. Si tous les tests passent → Commit & Push"
echo ""

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ VALIDATION AUTOMATIQUE: SUCCÈS${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Status: READY FOR MANUAL TESTING"
echo ""

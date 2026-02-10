#!/bin/bash

# Script pour nettoyer tous les caches Python du projet FilterMate
# Usage: ./clean_python_cache.sh

echo "🧹 Nettoyage des caches Python du projet FilterMate..."
echo ""

# Compteurs
pycache_count=0
pyc_count=0
pytest_count=0

# Supprimer tous les dossiers __pycache__ (méthode plus agressive)
echo "📁 Suppression des dossiers __pycache__..."
pycache_count=$(find . -type d -name "__pycache__" | wc -l)
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
echo "  ✓ $pycache_count dossiers __pycache__ supprimés"

# Supprimer tous les fichiers .pyc
echo ""
echo "📄 Suppression des fichiers .pyc..."
pyc_count=$(find . -type f -name "*.pyc" | wc -l)
find . -type f -name "*.pyc" -delete 2>/dev/null || true
echo "  ✓ $pyc_count fichiers .pyc supprimés"

# Supprimer tous les fichiers .pyo
echo ""
echo "📄 Suppression des fichiers .pyo..."
pyo_count=$(find . -type f -name "*.pyo" | wc -l)
find . -type f -name "*.pyo" -delete 2>/dev/null || true
echo "  ✓ $pyo_count fichiers .pyo supprimés"

# Supprimer les dossiers .pytest_cache
echo ""
echo "🧪 Suppression des caches pytest..."
pytest_count=$(find . -type d -name ".pytest_cache" | wc -l)
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
echo "  ✓ $pytest_count dossiers .pytest_cache supprimés"

# Résumé
echo ""
echo "✅ Nettoyage terminé!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Dossiers __pycache__ supprimés: $pycache_count"
echo "  Fichiers .pyc supprimés: $pyc_count"
echo "  Fichiers .pyo supprimés: $pyo_count"
echo "  Dossiers .pytest_cache supprimés: $pytest_count"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Vérification finale
remaining=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l)
if [ "$remaining" -gt 0 ]; then
    echo ""
    echo "⚠️  ATTENTION: $remaining dossiers __pycache__ restants"
    echo "   (probablement recréés par QGIS en cours d'exécution)"
    echo "   → Fermez QGIS avant de relancer le script pour un nettoyage complet"
fi


"""
Script pour activer le logging détaillé de FilterMate

INSTRUCTIONS:
1. Ouvrir Console Python QGIS (Ctrl+Alt+P)
2. Copier-coller ce code
3. Appuyer Entrée
4. Lancer votre filtre
5. Vérifier les logs dans la console

Les logs apparaîtront avec des préfixes:
- 📌 DIAGNOSTIC = Paramètres de filtrage
- 🔍 = Vérifications de conditions
- ⚠️ = Avertissements (couches non filtrées)
- ✓ = Succès
- ❌ = Erreurs
"""

import logging
import sys
from qgis.core import QgsMessageLog, Qgis

print("=" * 80)
print("ACTIVATION DU LOGGING FILTERMATE")
print("=" * 80)

# ÉTAPE 1: Activer TOUS les loggers FilterMate au niveau DEBUG
loggers_to_enable = [
    'FilterMate',
    'FilterMate.FilterMateApp',
    'FilterMate.Tasks.Filter',
    'FilterMate.TaskBuilder',
    'FilterMate.GeometryPreparer',
    'FilterMate.FilterOrchestrator',
    'FilterMate.Core.Services.TaskRunOrchestrator',
]

for logger_name in loggers_to_enable:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    
    # Ajouter un handler console si pas déjà présent
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    print(f"✓ {logger_name}")

print("\n" + "=" * 80)
print("LOGGING ACTIVÉ!")
print("=" * 80)
print("\n📌 Lancez maintenant votre filtre")
print("📌 Les logs apparaîtront dans cette console")
print("📌 Recherchez les messages:")
print("   - 🔍 Checking if distant layers should be filtered...")
print("   - ⚠️ DISTANT LAYERS FILTERING SKIPPED")
print("   - ✓ COMPLETE SUCCESS")
print("\n" + "=" * 80)
print("=" * 80)
print("Logging activé ! Cliquez maintenant sur le bouton Filter.")
print("=" * 80)

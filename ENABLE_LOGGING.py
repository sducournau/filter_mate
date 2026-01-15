"""
Script pour activer le logging détaillé de FilterMate

À exécuter dans la Console Python de QGIS avant de tester le filtrage.
"""

import logging
import sys

# ÉTAPE 1: Nettoyer le cache Python pour forcer le rechargement
print("=" * 80)
print("NETTOYAGE DU CACHE PYTHON")
print("=" * 80)

modules_to_clear = [
    mod for mod in list(sys.modules.keys()) 
    if 'filter_mate' in mod.lower()
]

for mod in modules_to_clear:
    del sys.modules[mod]
    print(f"✓ Module supprimé du cache: {mod}")

print(f"\n{len(modules_to_clear)} modules supprimés du cache\n")

# ÉTAPE 2: Activer tous les loggers FilterMate
loggers_to_enable = [
    'FilterMate',
    'FilterMate.FilterMateApp', 
    'FilterMate.Tasks.Filter',  # CORRIGÉ: Nom réel du logger dans filter_task.py
    'FilterMate.Core.Services.TaskRunOrchestrator',
]

print("=" * 80)
print("ACTIVATION DU LOGGING DÉTAILLÉ FILTERMATE")
print("=" * 80)

for logger_name in loggers_to_enable:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    
    # Ajouter un handler console si pas déjà présent
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    print(f"✓ {logger_name} - Level: {logging.getLevelName(logger.level)}")

print("=" * 80)
print("Logging activé ! Cliquez maintenant sur le bouton Filter.")
print("=" * 80)

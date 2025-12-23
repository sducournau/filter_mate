"""
Script de diagnostic FilterMate
================================

Copiez et collez ce code dans la console Python QGIS pour activer les logs DEBUG
et diagnostiquer les problèmes de filtrage.

Usage:
1. Ouvrez la console Python (Ctrl+Alt+P ou Plugins > Console Python)
2. Copiez tout le code ci-dessous
3. Collez-le dans la console et appuyez sur Entrée
4. Reproduisez l'erreur
5. Vérifiez le panneau Messages de log (Vue > Panneaux > Messages de log)
"""

import logging

# Activer les logs DEBUG pour FilterMate
filter_mate_logger = logging.getLogger('FilterMate')
filter_mate_logger.setLevel(logging.DEBUG)

# Ajouter un handler pour afficher dans la console Python
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# Éviter les doublons
if not filter_mate_logger.handlers:
    filter_mate_logger.addHandler(console_handler)

print("✓ FilterMate DEBUG logs activés!")
print("  Les logs détaillés apparaîtront dans:")
print("  1. Cette console Python")
print("  2. Le panneau Messages de log (Vue > Panneaux > Messages de log)")
print("")
print("Reproduisez maintenant l'erreur et observez les logs.")

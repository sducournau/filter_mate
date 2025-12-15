#!/usr/bin/env python3
"""
Script pour supprimer les suffixes "_3" des noms de widgets dans le fichier .ui
"""
import re

ui_file = 'filter_mate_dockwidget_base.ui'

print(f"Lecture du fichier {ui_file}...")
with open(ui_file, 'r', encoding='utf-8') as f:
    content = f.read()

print("Recherche et remplacement des suffixes '_3'...")
# Remplacer tous les name="xxx_3" par name="xxx"
original_content = content
content = re.sub(r'name="([^"]+)_3"', r'name="\1"', content)

# Compter les remplacements
changes = len(re.findall(r'_3"', original_content))
print(f"✓ {changes} suffixes '_3' supprimés")

print(f"Écriture du fichier modifié...")
with open(ui_file, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\n✅ Fichier {ui_file} mis à jour avec succès!")
print("\nProchaines étapes:")
print("  1. Recompiler le fichier .ui:")
print("     cmd.exe /c compile_ui.bat")
print("  2. Recharger le plugin dans QGIS")

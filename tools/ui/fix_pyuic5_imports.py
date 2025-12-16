#!/usr/bin/env python3
"""
Script pour corriger les imports incorrects générés par pyuic5

Ce script doit être exécuté après compile_ui.bat pour corriger
les imports de widgets QGIS qui sont incorrectement générés.

Usage:
    python fix_pyuic5_imports.py
    
Ou intégrer dans compile_ui.bat :
    call OSGeo4W.bat pyuic5 ...
    python fix_pyuic5_imports.py
"""

import re
from pathlib import Path

def fix_qgis_imports(py_file_path):
    """
    Corrige les imports QGIS incorrects dans un fichier Python généré par pyuic5.
    
    Args:
        py_file_path: Chemin vers le fichier .py à corriger
        
    Returns:
        tuple: (success: bool, message: str)
    """
    py_file = Path(py_file_path)
    
    if not py_file.exists():
        return False, f"Fichier introuvable: {py_file_path}"
    
    # Lire le contenu
    try:
        with open(py_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return False, f"Erreur de lecture: {e}"
    
    # Détecter les imports incorrects à la fin du fichier
    # Pattern: from qgswidgetname import QgsWidgetName
    incorrect_import_pattern = r'from (qgs\w+) import (Qgs\w+)'
    
    matches = re.findall(incorrect_import_pattern, content)
    
    if not matches:
        return True, "Aucun import incorrect trouvé"
    
    # Extraire les noms de classes
    class_names = [match[1] for match in matches]
    
    print(f"Imports incorrects détectés: {len(matches)}")
    for module, class_name in matches:
        print(f"  - from {module} import {class_name}")
    
    # Supprimer tous les imports incorrects
    content = re.sub(incorrect_import_pattern + r'\n?', '', content)
    
    # Ajouter les imports corrects à la fin (avant le if __name__ si présent)
    correct_imports = "from qgis.gui import (\n"
    for class_name in class_names:
        correct_imports += f"    {class_name},\n"
    correct_imports = correct_imports.rstrip(',\n') + "\n)\n"
    
    # Insérer avant le if __name__ ou à la fin
    if 'if __name__ ==' in content:
        content = content.replace('if __name__ ==', correct_imports + '\nif __name__ ==')
    else:
        content = content.rstrip() + '\n' + correct_imports
    
    # Écrire le fichier corrigé
    try:
        with open(py_file, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        return False, f"Erreur d'écriture: {e}"
    
    return True, f"{len(matches)} imports corrigés"


def main():
    """Point d'entrée principal."""
    script_dir = Path(__file__).parent
    py_file = script_dir / "filter_mate_dockwidget_base.py"
    
    print("=" * 70)
    print("Correction des imports QGIS dans le fichier généré par pyuic5")
    print("=" * 70)
    print(f"\nFichier: {py_file}")
    print()
    
    success, message = fix_qgis_imports(py_file)
    
    if success:
        print()
        print("=" * 70)
        print(f"✓ SUCCESS: {message}")
        print("=" * 70)
        return 0
    else:
        print()
        print("=" * 70)
        print(f"✗ ERREUR: {message}")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())

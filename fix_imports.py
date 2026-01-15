#!/usr/bin/env python3
"""
Script pour corriger automatiquement les imports absolus en imports relatifs.
"""

import os
import re
from pathlib import Path

# Dossiers à exclure
EXCLUDED_DIRS = {
    'tests', 'before_migration', '__pycache__', 
    '.serena', '_bmad', 'docs', 'i18n', '_bmad-output',
    'website', 'tools'
}

def should_skip_path(path):
    """Vérifie si le chemin doit être ignoré."""
    parts = Path(path).parts
    return any(excluded in parts for excluded in EXCLUDED_DIRS)

def calculate_relative_import(filepath, plugin_root):
    """Calcule le nombre de points nécessaires pour l'import relatif."""
    rel_path = Path(filepath).relative_to(plugin_root)
    depth = len(rel_path.parent.parts)
    return '.' * (depth + 1)

def fix_imports_in_file(filepath, plugin_root, dry_run=False):
    """Corrige les imports dans un fichier."""
    changes = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    modified = False
    
    for line_num, line in enumerate(lines, 1):
        new_line = line
        
        # Détecter les imports absolus à corriger
        match = re.match(r'^(\s*)from\s+(infrastructure|adapters|core|config)\.(.*)', line)
        if match:
            indent, module, rest = match.groups()
            rel_prefix = calculate_relative_import(filepath, plugin_root)
            new_line = f"{indent}from {rel_prefix}{module}.{rest}"
            
            if new_line != line:
                modified = True
                changes.append({
                    'line': line_num,
                    'old': line.rstrip(),
                    'new': new_line.rstrip()
                })
        
        new_lines.append(new_line)
    
    if modified and not dry_run:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
    
    return changes

def main():
    """Point d'entrée principal."""
    plugin_root = Path(__file__).parent
    total_files = 0
    total_changes = 0
    files_modified = []
    
    print(f"\n{'='*80}")
    print("CORRECTION AUTOMATIQUE DES IMPORTS")
    print(f"{'='*80}\n")
    
    # Parcourir tous les fichiers Python
    for root, dirs, files in os.walk(plugin_root):
        # Filtrer les dossiers exclus
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        
        for filename in files:
            if not filename.endswith('.py'):
                continue
                
            filepath = os.path.join(root, filename)
            
            if should_skip_path(filepath):
                continue
            
            total_files += 1
            changes = fix_imports_in_file(filepath, plugin_root, dry_run=False)
            
            if changes:
                rel_path = Path(filepath).relative_to(plugin_root)
                files_modified.append((rel_path, changes))
                total_changes += len(changes)
    
    # Afficher les résultats
    print(f"Fichiers analysés: {total_files}")
    print(f"Fichiers modifiés: {len(files_modified)}")
    print(f"Total de changements: {total_changes}\n")
    
    if files_modified:
        print(f"{'─'*80}")
        print("DÉTAILS DES MODIFICATIONS:")
        print(f"{'─'*80}\n")
        
        for filepath, changes in files_modified:
            print(f"📄 {filepath} ({len(changes)} changements)")
            for change in changes:
                print(f"   Ligne {change['line']}:")
                print(f"   - {change['old']}")
                print(f"   + {change['new']}")
            print()
    
    print(f"{'='*80}")
    print("✅ Correction terminée!")
    print(f"{'='*80}\n")
    
    return 0

if __name__ == '__main__':
    exit(main())

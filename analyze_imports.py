#!/usr/bin/env python3
"""
Analyse statique des imports dans FilterMate.
Détecte les problèmes d'imports absolus vs relatifs.
"""

import os
import re
from pathlib import Path
from collections import defaultdict

# Dossiers à exclure
EXCLUDED_DIRS = {
    'tests', 'before_migration', '__pycache__', 
    '.serena', '_bmad', 'docs', 'i18n', '_bmad-output',
    'website', 'tools'
}

# Pattern pour détecter les imports
IMPORT_PATTERNS = [
    re.compile(r'^from\s+(infrastructure|adapters|core|config)\.'),
    re.compile(r'^import\s+(infrastructure|adapters|core|config)\.'),
    re.compile(r'^from\s+\.(infrastructure|adapters|core|config)\.'),
    re.compile(r'^from\s+\.\.\.(infrastructure|adapters|core|config)\.'),
]

def should_skip_path(path):
    """Vérifie si le chemin doit être ignoré."""
    parts = Path(path).parts
    return any(excluded in parts for excluded in EXCLUDED_DIRS)

def analyze_file(filepath, plugin_root):
    """Analyse un fichier Python pour les imports."""
    issues = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            # Ignorer les commentaires
            if line.startswith('#'):
                continue
                
            # Détecter imports absolus problématiques
            if re.match(r'^from\s+(infrastructure|adapters|core|config)\.', line):
                # Calculer la profondeur relative
                rel_path = Path(filepath).relative_to(plugin_root)
                depth = len(rel_path.parent.parts)
                
                # Si on est dans un sous-dossier, l'import absolu est problématique
                if depth > 0:
                    issues.append({
                        'file': str(rel_path),
                        'line': line_num,
                        'code': line,
                        'type': 'absolute_import',
                        'depth': depth,
                        'suggestion': 'Utiliser import relatif avec ' + '.' * (depth + 1)
                    })
    
    return issues

def main():
    """Point d'entrée principal."""
    plugin_root = Path(__file__).parent
    all_issues = defaultdict(list)
    file_count = 0
    
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
            
            file_count += 1
            issues = analyze_file(filepath, plugin_root)
            
            if issues:
                all_issues[filepath].extend(issues)
    
    # Afficher les résultats
    print(f"\n{'='*80}")
    print(f"ANALYSE DES IMPORTS - FilterMate")
    print(f"{'='*80}\n")
    print(f"Fichiers analysés: {file_count}")
    print(f"Fichiers avec problèmes: {len(all_issues)}\n")
    
    if not all_issues:
        print("✅ Aucun problème d'import détecté!\n")
        return 0
    
    # Grouper par type
    by_type = defaultdict(list)
    for filepath, issues in all_issues.items():
        for issue in issues:
            by_type[issue['type']].append((filepath, issue))
    
    # Afficher par type
    for issue_type, items in sorted(by_type.items()):
        print(f"\n{'─'*80}")
        print(f"Type: {issue_type.upper()}")
        print(f"{'─'*80}")
        print(f"Total: {len(items)} occurences\n")
        
        for filepath, issue in sorted(items, key=lambda x: x[1]['file']):
            rel_path = Path(filepath).relative_to(plugin_root)
            print(f"📄 {rel_path}")
            print(f"   Ligne {issue['line']}: {issue['code']}")
            if 'suggestion' in issue:
                print(f"   💡 {issue['suggestion']}")
            print()
    
    print(f"\n{'='*80}\n")
    return len(all_issues)

if __name__ == '__main__':
    exit(main())

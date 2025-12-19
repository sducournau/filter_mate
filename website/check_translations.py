#!/usr/bin/env python3
"""Vérifier si les fichiers de traduction sont vraiment traduits ou en anglais."""

import os
import re
from pathlib import Path

def detect_language(content):
    """Détecte la langue basée sur des mots clés."""
    # Mots anglais communs dans la doc
    english_words = ['the', 'and', 'for', 'with', 'this', 'from', 'you', 'are', 'can', 'will', 'your', 'when', 'how']
    # Mots français communs
    french_words = ['le', 'la', 'les', 'de', 'des', 'pour', 'avec', 'vous', 'est', 'sont', 'dans', 'sur']
    # Mots portugais communs
    portuguese_words = ['o', 'a', 'os', 'as', 'de', 'para', 'com', 'você', 'é', 'são', 'em', 'do', 'da']
    
    # Ignorer le front matter YAML
    content_clean = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)
    content_lower = content_clean.lower()
    
    # Compter les mots
    en_count = sum(len(re.findall(r'\b' + word + r'\b', content_lower)) for word in english_words)
    fr_count = sum(len(re.findall(r'\b' + word + r'\b', content_lower)) for word in french_words)
    pt_count = sum(len(re.findall(r'\b' + word + r'\b', content_lower)) for word in portuguese_words)
    
    total = en_count + fr_count + pt_count
    if total == 0:
        return 'unknown'
    
    if en_count > fr_count and en_count > pt_count:
        return 'english'
    elif fr_count > en_count and fr_count > pt_count:
        return 'french'
    elif pt_count > en_count and pt_count > fr_count:
        return 'portuguese'
    else:
        return 'mixed'

def check_directory(base_path, lang):
    """Vérifie tous les fichiers MD dans un répertoire."""
    results = []
    path = Path(base_path) / 'i18n' / lang / 'docusaurus-plugin-content-docs' / 'current'
    
    for md_file in sorted(path.rglob('*.md')):
        relative = md_file.relative_to(path)
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
            detected = detect_language(content)
            
            # Problème si fichier FR contient de l'anglais ou PT contient de l'anglais
            is_problem = (lang == 'fr' and detected == 'english') or \
                        (lang == 'pt' and detected == 'english')
            
            results.append({
                'file': str(relative),
                'detected': detected,
                'is_problem': is_problem
            })
        except Exception as e:
            results.append({
                'file': str(relative),
                'detected': f'ERROR: {e}',
                'is_problem': True
            })
    
    return results

# Vérifier FR et PT
print("=" * 80)
print("VÉRIFICATION DES TRADUCTIONS DOCUSAURUS")
print("=" * 80)
print()

base = Path('/mnt/c/Users/SimonDucorneau/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/filter_mate/website')

for lang in ['fr', 'pt']:
    print(f"\n{'=' * 80}")
    print(f"Langue: {lang.upper()}")
    print('=' * 80)
    
    results = check_directory(str(base), lang)
    
    problems = [r for r in results if r['is_problem']]
    ok = [r for r in results if not r['is_problem']]
    
    print(f"\n✅ Fichiers correctement traduits: {len(ok)}/{len(results)}")
    print(f"❌ Fichiers probablement en anglais: {len(problems)}/{len(results)}")
    
    if problems:
        print(f"\nFICHIERS PROBLÉMATIQUES ({lang.upper()}):")
        print("-" * 80)
        for p in problems:
            print(f"  ❌ {p['file']:60s} -> {p['detected']}")
    
    if False:  # Mettre True pour voir les fichiers OK aussi
        print(f"\nFICHIERS OK ({lang.upper()}):")
        for r in ok[:10]:  # Premiers 10
            print(f"  ✅ {r['file']:60s} -> {r['detected']}")
        if len(ok) > 10:
            print(f"  ... et {len(ok) - 10} autres")

print("\n" + "=" * 80)
print("VÉRIFICATION TERMINÉE")
print("=" * 80)

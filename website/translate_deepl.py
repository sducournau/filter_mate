#!/usr/bin/env python3
"""
Script de traduction via DeepL API.
Nécessite: pip install deepl
Configurer: export DEEPL_API_KEY="votre_clé_ici"
"""

import os
import deepl
from pathlib import Path

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
if not DEEPL_API_KEY:
    print("❌ DEEPL_API_KEY non définie")
    exit(1)

translator = deepl.Translator(DEEPL_API_KEY)

def translate_file(source_path, target_path, target_lang):
    """Traduire un fichier markdown."""
    with open(source_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Séparer le front matter YAML
    parts = content.split('---', 2)
    if len(parts) >= 3:
        front_matter = parts[1]
        body = parts[2]
    else:
        front_matter = ""
        body = content
    
    # Traduire le corps (en évitant les blocs de code)
    result = translator.translate_text(
        body,
        target_lang=target_lang,
        formality="default",
        preserve_formatting=True,
        tag_handling="xml"
    )
    
    # Reconstituer le fichier
    if front_matter:
        translated = f"---{front_matter}---{result.text}"
    else:
        translated = result.text
    
    # Sauvegarder
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, 'w', encoding='utf-8') as f:
        f.write(translated)
    
    print(f"✅ {target_path.name} traduit")

# Exemple d'utilisation
# translate_file("docs/workflows/emergency-services.md", "i18n/fr/.../emergency-services.md", "FR")

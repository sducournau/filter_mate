#!/usr/bin/env python3
"""
Script de traduction automatique pour les fichiers Docusaurus restants.
Utilise l'approche de traduction paragraphe par paragraphe pour maintenir la qualité.
"""

import os
import re
from pathlib import Path

# Configuration
BASE_DIR = Path(__file__).parent
DOCS_DIR = BASE_DIR / "docs"
I18N_FR = BASE_DIR / "i18n" / "fr" / "docusaurus-plugin-content-docs" / "current"
I18N_PT = BASE_DIR / "i18n" / "pt" / "docusaurus-plugin-content-docs" / "current"

# Fichiers restants à traduire (sans workflows/index.md déjà fait)
WORKFLOWS_FILES = [
    "workflows/emergency-services.md",
    "workflows/environmental-protection.md",
    "workflows/real-estate-analysis.md",
    "workflows/transportation-planning.md",
    "workflows/urban-planning-transit.md",
]

ADVANCED_FILES = [
    "advanced/configuration-system.md",
    "advanced/configuration.md",
    "advanced/performance-tuning.md",
    "advanced/troubleshooting.md",
    "advanced/undo-redo-system.md",
]

REFERENCE_FILES = [
    "reference/cheat-sheets/expressions.md",
    "reference/cheat-sheets/spatial-predicates.md",
    "reference/glossary.md",
]

DEVELOPER_FILES = [
    "developer-guide/architecture.md",
    "developer-guide/backend-development.md",
    "developer-guide/code-style.md",
    "developer-guide/contributing.md",
    "developer-guide/development-setup.md",
    "developer-guide/testing.md",
]

# Glossaire SIG pour traductions cohérentes
GLOSSARY = {
    "en": {
        "Layer": {"fr": "Couche", "pt": "Camada"},
        "Feature": {"fr": "Entité", "pt": "Feição"},
        "Attribute": {"fr": "Attribut", "pt": "Atributo"},
        "Buffer": {"fr": "Tampon", "pt": "Buffer"},
        "CRS": {"fr": "SCR", "pt": "SRC"},
        "Filter": {"fr": "Filtre", "pt": "Filtro"},
        "Query": {"fr": "Requête", "pt": "Consulta"},
        "Expression": {"fr": "Expression", "pt": "Expressão"},
        "Backend": {"fr": "Backend", "pt": "Backend"},
        "Workflow": {"fr": "Flux de travail", "pt": "Fluxo de trabalho"},
    }
}


def get_file_info(relative_path):
    """Obtenir des informations sur un fichier source."""
    source_file = DOCS_DIR / relative_path
    if not source_file.exists():
        return None
    
    with open(source_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = len(content.splitlines())
    words = len(content.split())
    
    return {
        'path': relative_path,
        'lines': lines,
        'words': words,
        'size_kb': len(content) / 1024,
        'exists_fr': (I18N_FR / relative_path).exists(),
        'exists_pt': (I18N_PT / relative_path).exists(),
    }


def analyze_remaining_files():
    """Analyser tous les fichiers restants à traduire."""
    print("=" * 80)
    print("ANALYSE DES FICHIERS RESTANTS À TRADUIRE")
    print("=" * 80)
    print()
    
    all_files = WORKFLOWS_FILES + ADVANCED_FILES + REFERENCE_FILES + DEVELOPER_FILES
    
    total_lines_fr = 0
    total_lines_pt = 0
    total_files_fr = 0
    total_files_pt = 0
    
    for category, files in [
        ("WORKFLOWS", WORKFLOWS_FILES),
        ("ADVANCED", ADVANCED_FILES),
        ("REFERENCE", REFERENCE_FILES),
        ("DEVELOPER", DEVELOPER_FILES),
    ]:
        print(f"\n{category}")
        print("-" * 80)
        
        for filepath in files:
            info = get_file_info(filepath)
            if info:
                needs_fr = not info['exists_fr'] or True  # Toujours vérifier
                needs_pt = not info['exists_pt'] or True
                
                if needs_fr:
                    total_lines_fr += info['lines']
                    total_files_fr += 1
                if needs_pt:
                    total_lines_pt += info['lines']
                    total_files_pt += 1
                
                status = []
                if needs_fr:
                    status.append("❌ FR")
                if needs_pt:
                    status.append("❌ PT")
                if not status:
                    status = ["✅ OK"]
                
                print(f"  {filepath:50} {info['lines']:4} lignes  {' '.join(status)}")
    
    print()
    print("=" * 80)
    print(f"TOTAL À TRADUIRE:")
    print(f"  FR: {total_files_fr} fichiers, ~{total_lines_fr} lignes")
    print(f"  PT: {total_files_pt} fichiers, ~{total_lines_pt} lignes")
    print(f"  Estimation: {(total_lines_fr + total_lines_pt) * 2 / 60:.1f} heures (manuel)")
    print(f"  Estimation: {(total_lines_fr + total_lines_pt) * 1 / 60:.1f} heures (avec IA)")
    print("=" * 80)


def generate_deepl_script():
    """Générer un script pour utiliser l'API DeepL."""
    script = '''#!/usr/bin/env python3
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
'''
    
    with open(BASE_DIR / "translate_deepl.py", 'w', encoding='utf-8') as f:
        f.write(script)
    
    print("✅ Script DeepL généré: translate_deepl.py")


def generate_translation_prompts():
    """Générer des prompts optimisés pour ChatGPT/Claude."""
    prompts_file = BASE_DIR / "TRANSLATION_PROMPTS.md"
    
    content = """# Prompts de Traduction pour FilterMate Documentation

## Prompt de Base (Copier-Coller dans ChatGPT/Claude)

```
Je vais te donner un fichier markdown de documentation technique QGIS en anglais.
Traduis-le en [FRANÇAIS/PORTUGAIS] en respectant ces règles:

GLOSSAIRE TECHNIQUE (à utiliser systématiquement):
- Layer → Couche (FR) / Camada (PT)
- Feature → Entité (FR) / Feição (PT)
- Buffer → Tampon (FR) / Buffer (PT)
- CRS/Coordinate System → SCR (FR) / SRC (PT)
- Backend → Backend (garder en anglais)
- Attribute → Attribut (FR) / Atributo (PT)

RÈGLES:
1. Garder le front matter YAML intact (---...---)
2. Garder les blocs de code intacts (```...```)
3. Garder les URLs et chemins de fichiers intacts
4. Traduire les commentaires dans le code
5. Garder les noms de variables/fonctions en anglais
6. Adapter les exemples de noms (Paris → Lyon pour FR, São Paulo pour PT)
7. Utiliser un ton professionnel mais accessible
8. Garder la mise en forme markdown (##, -, **, etc.)

Voici le fichier à traduire:
```

## Prompt Workflow Spécifique

```
CONTEXTE: Ceci est un tutoriel pratique FilterMate pour [DOMAINE].
Le ton doit être pédagogique et encourageant.

ADAPTATIONS CULTURELLES:
- Adapter les exemples géographiques (villes, régions) au contexte local
- Adapter les unités si nécessaire (km, m² sont OK pour FR et PT)
- Adapter les références réglementaires (mentionner que c'est un exemple)

Voici le workflow à traduire:
```

## Vérification Post-Traduction

Après traduction, vérifier:
- [ ] Front matter intact
- [ ] Blocs de code intacts
- [ ] Glossaire SIG utilisé correctement
- [ ] Liens internes fonctionnels
- [ ] Ton professionnel maintenu
- [ ] Pas de termes techniques anglais non nécessaires
"""
    
    with open(prompts_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ Prompts générés: {prompts_file.name}")


def main():
    """Fonction principale."""
    print("\n🔧 OUTIL DE TRADUCTION BATCH FILTERMATE\n")
    
    # Analyser les fichiers restants
    analyze_remaining_files()
    
    print("\n📝 GÉNÉRATION DES OUTILS D'AIDE\n")
    
    # Générer les outils
    generate_deepl_script()
    generate_translation_prompts()
    
    print("\n✅ OUTILS GÉNÉRÉS\n")
    print("Options pour continuer:")
    print("1. Utiliser DeepL API: python translate_deepl.py")
    print("2. Utiliser ChatGPT: Copier les prompts de TRANSLATION_PROMPTS.md")
    print("3. Traduction manuelle: Suivre l'ordre d'analyse ci-dessus")
    print()


if __name__ == "__main__":
    main()

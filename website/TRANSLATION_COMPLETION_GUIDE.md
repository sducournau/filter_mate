# Guide pratique : Compléter les traductions FilterMate
**Date** : 19 décembre 2025  
**Contexte** : 21-23 fichiers restants à traduire en FR/PT

## 🎯 Progression actuelle

### ✅ Terminé dans cette session
- ✅ **Vérification complète** des 44 fichiers (script automatique)
- ✅ **Rapport détaillé** ([TRANSLATION_VERIFICATION_2025-12-19.md](TRANSLATION_VERIFICATION_2025-12-19.md))
- ✅ **Traduction FR** de `user-guide/favorites.md` (487 lignes)

### 📊 Statut
- **Français** : 24/44 (54.5%) ⬆️ +1 fichier
- **Português** : 21/44 (47.7%) - inchangé

## 🚀 Options pour continuer

### Option A : Traduction assistée par IA (RECOMMANDÉ)

**Avantages** :
- Rapide (2-5 min/fichier vs 30-60 min manuel)
- Qualité correcte pour première passe
- Vous gardez le contrôle sur la révision

**Étapes** :

#### 1. Utiliser DeepL API (Meilleur pour FR/PT)

```bash
#!/bin/bash
# translate_with_deepl.sh

API_KEY="your-deepl-api-key"  # https://www.deepl.com/pro-api

translate_file() {
    local source_file=$1
    local target_file=$2
    local target_lang=$3  # "FR" ou "PT"
    
    # Lire le fichier
    content=$(cat "$source_file")
    
    # Traduire via API DeepL
    curl -X POST 'https://api-free.deepl.com/v2/translate' \
        -H "Authorization: DeepL-Auth-Key $API_KEY" \
        -d "text=$content" \
        -d "target_lang=$target_lang" \
        -d "preserve_formatting=1" \
        -d "formality=default" \
        > "$target_file.json"
    
    # Extraire le texte traduit
    jq -r '.translations[0].text' "$target_file.json" > "$target_file"
    rm "$target_file.json"
    
    echo "✅ Traduit: $target_file"
}

# Exemple d'utilisation
translate_file \
    "docs/user-guide/favorites.md" \
    "i18n/pt/docusaurus-plugin-content-docs/current/user-guide/favorites.md" \
    "PT"
```

#### 2. Utiliser ChatGPT/Claude (Sans API)

**Prompt à utiliser** :

```
Traduis ce fichier markdown de documentation technique FilterMate de l'anglais vers le [français/portugais brésilien].

INSTRUCTIONS CRITIQUES:
- Préserver TOUT le formatage markdown (##, ###, ```, :::, **bold**, etc.)
- Préserver TOUS les chemins de fichiers et noms de code
- NE PAS traduire les noms techniques : "FilterMate", "QGIS", "SQLite", etc.
- Utiliser la terminologie SIG standard :
  * Layer = Couche (FR) / Camada (PT)
  * Feature = Entité (FR) / Feição (PT)
  * Buffer = Tampon (FR) / Buffer (PT)
  * CRS = SCR (FR) / SRC (PT)
- Préserver le front matter YAML en haut (---)

FICHIER À TRADUIRE:

[coller le contenu ici]
```

**Puis** :
1. Copier le fichier EN dans le prompt
2. Récupérer la traduction
3. Sauvegarder dans le fichier i18n approprié
4. Vérifier avec `npm run build`

#### 3. Batch avec script Python

```python
#!/usr/bin/env python3
"""Traduire tous les fichiers manquants avec OpenAI API"""

import openai
from pathlib import Path

openai.api_key = "your-api-key"

GLOSSARY = {
    "Layer": {"fr": "Couche", "pt": "Camada"},
    "Feature": {"fr": "Entité", "pt": "Feição"},
    "Buffer": {"fr": "Tampon", "pt": "Buffer"},
    "CRS": {"fr": "SCR", "pt": "SRC"},
    # ... voir TRANSLATION_VERIFICATION_2025-12-19.md pour glossaire complet
}

def translate_file(source_path, target_path, target_lang):
    """Traduire un fichier markdown"""
    with open(source_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    prompt = f"""Translate this FilterMate technical documentation from English to {'French' if target_lang == 'fr' else 'Brazilian Portuguese'}.

PRESERVE:
- All markdown formatting
- Code blocks and paths
- YAML front matter
- Technical terms: {', '.join(GLOSSARY.keys())}

USE TERMINOLOGY:
{chr(10).join(f'- {k}: {v[target_lang]}' for k, v in GLOSSARY.items())}

FILE CONTENT:

{content}"""
    
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a technical translator specialized in GIS documentation."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3  # Plus bas = plus fidèle
    )
    
    translated = response.choices[0].message.content
    
    # Sauvegarder
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, 'w', encoding='utf-8') as f:
        f.write(translated)
    
    print(f"✅ {source_path.name} → {target_lang}")

# Lire la liste des fichiers manquants
missing_files = {
    'fr': [
        'accessibility.md',
        'advanced/configuration-system.md',
        # ... copier depuis TRANSLATION_VERIFICATION_2025-12-19.md
    ],
    'pt': [
        'accessibility.md',
        'getting-started/minute-tutorial.md',
        # ... copier depuis TRANSLATION_VERIFICATION_2025-12-19.md
    ]
}

# Traduire tous
for lang in ['fr', 'pt']:
    for file in missing_files[lang]:
        source = Path(f'docs/{file}')
        target = Path(f'i18n/{lang}/docusaurus-plugin-content-docs/current/{file}')
        translate_file(source, target, lang)
```

### Option B : Traduction manuelle ciblée

**Si vous voulez éviter l'IA**, concentrez-vous sur les fichiers **haute priorité** :

**Phase 1 (5 fichiers - 2-3h)** :
```bash
# FR
docs/accessibility.md → i18n/fr/.../accessibility.md

# PT  
docs/getting-started/minute-tutorial.md → i18n/pt/.../minute-tutorial.md
docs/workflows/index.md → i18n/pt/.../index.md

# FR + PT
# (favorites.md déjà fait FR)
```

**Puis laissez le reste en anglais** pour l'instant.

### Option C : Contribuer plus tard

**Créez des issues GitHub** :

```markdown
# Issue: Traduire documentation avancée en français

## Fichiers à traduire

- [ ] advanced/configuration-system.md
- [ ] advanced/configuration.md
- [ ] advanced/performance-tuning.md
- [ ] advanced/troubleshooting.md
- [ ] advanced/undo-redo-system.md

## Glossaire

Voir [TRANSLATION_VERIFICATION_2025-12-19.md](../website/TRANSLATION_VERIFICATION_2025-12-19.md)

## Estimation

~5-6 heures

## Labels

`translation`, `documentation`, `help-wanted`, `good-first-issue`
```

## 🛠️ Outils utiles

### Vérifier progression

```bash
cd website
python3 check_translations.py

# Ou manuel:
find i18n/fr/docusaurus-plugin-content-docs/current -name "*.md" | wc -l
# Devrait afficher 44 quand terminé
```

### Tester une traduction

```bash
# Build FR seulement
npm run build -- --locale fr

# Build PT seulement
npm run build -- --locale pt

# Servir localement
npm run serve
# Ouvrir http://localhost:3000/fr/docs/
```

### Trouver différences

```bash
# Fichiers EN qui n'ont pas de traduction FR correcte
diff <(find docs -name "*.md" -type f | sort) \
     <(cd website && python3 -c "
from check_translations import *
results = check_directory('.', 'fr')
for r in results:
    if not r['is_problem']:
        print('docs/' + r['file'])
" | sort)
```

## 📋 Checklist de validation

Après chaque traduction :

- [ ] Front matter YAML préservé
- [ ] Pas de code markers (` ````) traduits
- [ ] Liens internes fonctionnent (`[text](./other-file)`)
- [ ] Images référencées correctement
- [ ] Terminologie SIG cohérente (voir glossaire)
- [ ] Build réussit : `npm run build -- --locale [fr|pt]`
- [ ] Pas de warnings DeepL sur liens cassés

## 🎯 Plan d'action immédiat

**Si vous voulez continuer maintenant** :

1. **Choisir méthode** : IA (recommandé) ou manuel
2. **Si IA** : 
   - [ ] Obtenir clé API DeepL ou OpenAI
   - [ ] Tester sur 1 fichier
   - [ ] Lancer batch sur les 21-23 fichiers
   - [ ] Réviser termes techniques
3. **Si manuel** :
   - [ ] Faire Phase 1 (5 fichiers prioritaires)
   - [ ] Créer issues pour le reste
   - [ ] Demander contribution communauté

**Si vous voulez déléguer** :

1. Créer issues GitHub avec:
   - Liste fichiers à traduire
   - Lien vers glossaire
   - Estimation temps
   - Label `help-wanted`

2. Partager sur:
   - Forum QGIS
   - Discord/Slack équipe
   - Réseaux sociaux QGIS communauté

## 📊 Suivi progression

Mettre à jour README.md régulièrement :

```markdown
## 🌍 Translation Status

| Language | Progress | Status |
|----------|----------|--------|
| 🇬🇧 English | 44/44 (100%) | ✅ Complete |
| 🇫🇷 Français | 24/44 (54.5%) | 🔄 In Progress |
| 🇵🇹 Português | 21/44 (47.7%) | 🔄 In Progress |

### Priority Files Status

**Phase 1 (Critical):**
- [x] user-guide/favorites.md (FR)
- [ ] user-guide/favorites.md (PT)
- [ ] accessibility.md (FR/PT)
- [ ] getting-started/minute-tutorial.md (PT)
- [ ] workflows/index.md (PT)

**Phase 2 (Workflows):** 0/11  
**Phase 3 (Advanced):** 0/10  
**Phase 4 (Reference):** 0/6  
**Phase 5 (Developer):** 0/12 (optional)

Last updated: 2025-12-19
```

## 💡 Astuces

1. **Traductions en série** : Ne pas tout faire d'un coup
   - Faire 5 fichiers/jour = terminé en 4-5 jours
   
2. **Révision croisée** : Si équipe
   - Personne A traduit
   - Personne B révise
   
3. **Glossaire vivant** : Ajouter termes au fur et à mesure
   
4. **Tests réguliers** : Build après chaque 5 fichiers

## 📚 Ressources

- **DeepL** : https://www.deepl.com/pro-api
- **OpenAI** : https://platform.openai.com/
- **Docusaurus i18n** : https://docusaurus.io/docs/i18n/tutorial
- **Glossaire QGIS** :
  - FR : https://docs.qgis.org/3.28/fr/
  - PT : https://docs.qgis.org/3.28/pt_BR/

---

**Prochaine étape** : Choisir Option A, B ou C et commencer ! 🚀

**Question ?** Référer à [TRANSLATION_VERIFICATION_2025-12-19.md](TRANSLATION_VERIFICATION_2025-12-19.md) pour détails complets.

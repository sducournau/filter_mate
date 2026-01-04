# 📚 Plan de Mise à Jour des Traductions v2.8.9

## 🎯 Objectif

Mettre à jour les 22 fichiers de traduction avec les nouvelles chaînes ajoutées dans la version 2.8.9 (panneau avancé MV PostgreSQL et popup d'optimisation simplifié).

---

## 📊 État Actuel

| Métrique                          | Valeur                         |
| --------------------------------- | ------------------------------ |
| Langues supportées                | 22                             |
| Chaînes dans le code source       | 76 (détectées automatiquement) |
| Chaînes dans les fichiers .ts     | 282                            |
| Chaînes manquantes (code → .ts)   | 13                             |
| Chaînes extra (legacy/dynamiques) | 219                            |

### Langues Disponibles

| Code | Langue           | Fichier          |
| ---- | ---------------- | ---------------- |
| am   | Amharic          | FilterMate_am.ts |
| da   | Danish           | FilterMate_da.ts |
| de   | German           | FilterMate_de.ts |
| en   | English          | FilterMate_en.ts |
| es   | Spanish          | FilterMate_es.ts |
| fi   | Finnish          | FilterMate_fi.ts |
| fr   | French           | FilterMate_fr.ts |
| hi   | Hindi            | FilterMate_hi.ts |
| id   | Indonesian       | FilterMate_id.ts |
| it   | Italian          | FilterMate_it.ts |
| nb   | Norwegian Bokmål | FilterMate_nb.ts |
| nl   | Dutch            | FilterMate_nl.ts |
| pl   | Polish           | FilterMate_pl.ts |
| pt   | Portuguese       | FilterMate_pt.ts |
| ru   | Russian          | FilterMate_ru.ts |
| sl   | Slovenian        | FilterMate_sl.ts |
| sv   | Swedish          | FilterMate_sv.ts |
| tl   | Filipino/Tagalog | FilterMate_tl.ts |
| tr   | Turkish          | FilterMate_tr.ts |
| uz   | Uzbek            | FilterMate_uz.ts |
| vi   | Vietnamese       | FilterMate_vi.ts |
| zh   | Chinese          | FilterMate_zh.ts |

---

## 🆕 Nouvelles Chaînes v2.8.9

### A. Panneau PostgreSQL - Gestion des MV (MVStatusWidget)

```python
# Status labels
"MV Status: Checking..."
"MV Status: Error"
"MV Status: Clean"
"MV Status:"  # + count
"active"
"No active materialized views"

# Session info
"Session:"
"Other sessions:"

# Cleanup buttons & tooltips
"🧹 Session"
"Cleanup MVs from this session"
"🗑️ Orphaned"
"Cleanup orphaned MVs (>24h old)"
"⚠️ All"
"Cleanup ALL MVs (affects other sessions)"
"Confirm Cleanup"
"Drop ALL materialized views?\nThis affects other FilterMate sessions!"
"Refresh MV status"

# Settings
"Threshold:"
"features"
"Auto-cleanup on exit"
"Automatically drop session MVs when plugin unloads"
"Create MVs for datasets larger than this"
```

### B. Popup d'Optimisation Simplifié

```python
# Header
"faster possible"
"Optimizations available"
"FilterMate - Apply Optimizations?"

# Buttons
"Skip"
"✓ Apply"
"Don't ask for this session"

# Tags
"Centroids"
"Simplify"
"Pre-simplify"
"Fewer segments"
"Flat buffer"
"BBox filter"
"Attr-first"
```

### C. Panneau de Configuration Optimisation

```python
"Optimization Settings"
"Enable optimizations"
"Suggest performance optimizations before filtering"
"Auto-use centroids for remote layers"
"Use centroids to reduce network transfer (~90% faster)"
"Auto-select best strategy"
"Automatically choose optimal filtering strategy"
"Auto-simplify geometries"
"Warning: lossy operation, may change polygon shapes"
"Ask before applying"
"Show confirmation dialog before optimizations"
```

### D. Recommandations et Messages

```python
"Quick Setup"
"Choose a profile or customize settings below"
"Smart Recommendations"
"Analyzing your project... Recommendations will appear here."
"Enable Materialized Views"
"Cache complex spatial queries in indexed temporary tables."
"Enable Auto-Centroid for Remote Layers"
"Use centroids instead of full geometry for distant layers."
"Enable Direct SQL for GeoPackage"
"Execute SQL directly on GeoPackage for better performance."
"Create Spatial Indexes"
"Add indexes to improve spatial query speed."
"Use Balanced Profile"
"Good balance between speed and precision."
"Estimated performance improvement"
"PostgreSQL not available"
"No connection"
```

### E. Options PostgreSQL

```python
"PostgreSQL/PostGIS Optimizations"
"Optimizations for PostgreSQL databases with PostGIS extension"
"Materialized Views"
"Create indexed temporary views for complex spatial queries."
"Two-Phase Filtering"
"First filter by bounding box, then by exact geometry."
"Progressive Loading"
"Stream results in chunks to reduce memory usage."
"Lazy cursor threshold:"
"Query Expression Caching"
"Cache expressions to avoid rebuilding identical queries."
"Connection Pooling"
"Reuse connections to avoid 50-100ms overhead per query."
"EXISTS Subquery for Large WKT"
"Use EXISTS subquery for very large geometries."
"WKT threshold:"
"chars"
"Automatic GIST Index Usage"
"Verify and use GIST spatial indexes for optimal query plans."
```

### F. Options Spatialite/GeoPackage

```python
"Spatialite/GeoPackage Optimizations"
"Optimizations for Spatialite databases and GeoPackage files"
"R-tree Temp Tables"
"Create temporary tables with R-tree spatial indexes for complex queries. Similar to PostgreSQL materialized views."
"WKT size threshold (KB):"
"Use R-tree optimization for WKT larger than this"
"BBox Pre-filtering"
"Use bounding box filter before exact geometry test. Reduces CPU usage significantly."
"Interruptible Queries"
"Execute SQLite queries in background thread with cancellation support. Prevents UI freeze."
"Query timeout (seconds):"
"Direct SQL for GeoPackage"
"Bypass GDAL layer and execute SQL directly on GeoPackage. 2-5x faster for simple filters."
"WKT Geometry Caching"
"Cache converted WKT strings to avoid repeated geometry serialization."
"Auto-detect mod_spatialite"
"Automatically find and load the best mod_spatialite extension."
```

### G. Options OGR/Memory

```python
"OGR/Memory Optimizations"
"Optimizations for file-based formats (Shapefiles, GeoJSON) and memory layers"
"Automatic Spatial Index"
"Automatically create spatial index (.qix/.shx) for layers without one. Essential for large shapefiles."
"Small Dataset Memory Backend"
"For small PostgreSQL layers, copy to memory for faster filtering. Reduces network latency."
"Small dataset threshold:"
"Cancellable Processing"
"Allow cancellation of QGIS processing algorithms. Useful for long-running operations."
"Progressive Chunking"
"Process features in chunks for very large datasets. Provides progress feedback and cancellation."
"Chunk size (features):"
```

---

## 🔧 Outils Disponibles

| Outil                          | Chemin | Description                    |
| ------------------------------ | ------ | ------------------------------ |
| verify_all_translations.py     | tools/ | Vérifie les chaînes manquantes |
| create_new_translations.py     | tools/ | Crée de nouveaux fichiers .ts  |
| compile_translations_simple.py | tools/ | Compile .ts → .qm              |

---

## 📋 Plan d'Action

### Étape 1: Extraction des Chaînes Sources (pylupdate5)

```bash
# Option A: Utiliser pylupdate5 (recommandé)
cd /path/to/filter_mate
pylupdate5 *.py modules/*.py -ts i18n/FilterMate_en.ts

# Option B: Mise à jour manuelle avec lupdate
lupdate *.py modules/*.py filter_mate_dockwidget_base.ui -ts i18n/FilterMate_en.ts
```

### Étape 2: Copier vers les Autres Langues

```bash
# Pour chaque langue, copier les nouvelles entrées depuis en.ts
# Le script update_translations.py peut automatiser cela
python3 tools/update_translations.py
```

### Étape 3: Traduire les Nouvelles Chaînes

#### Option A: Qt Linguist (Manuel)

```bash
# Ouvrir chaque fichier dans Qt Linguist
linguist i18n/FilterMate_fr.ts
```

#### Option B: Script de Traduction Automatique (API)

```python
# Utiliser un service de traduction (Google/DeepL) pour les premières passes
python3 tools/auto_translate.py --lang fr de es it
```

#### Option C: Contribution Communautaire

- Créer des issues GitHub pour chaque langue
- Utiliser Weblate ou Transifex pour la traduction collaborative

### Étape 4: Compilation des Traductions

```bash
# Compiler tous les .ts en .qm
python3 tools/compile_translations_simple.py

# OU utiliser lrelease (plus fiable)
lrelease i18n/FilterMate_*.ts
```

### Étape 5: Vérification

```bash
# Vérifier les chaînes manquantes
python3 tools/verify_all_translations.py

# Tester dans QGIS
# 1. Changer la langue de QGIS
# 2. Recharger le plugin
# 3. Vérifier les nouveaux éléments UI
```

---

## 🛠️ Script de Mise à Jour (À Créer)

### tools/update_translations_v289.py

```python
#!/usr/bin/env python3
"""
Update translation files with new strings from v2.8.9
"""

import os
import xml.etree.ElementTree as ET

I18N_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'i18n')

# New strings for v2.8.9
NEW_STRINGS = {
    # MV Status Widget
    "MV Status: Checking...": {
        "fr": "État MV : Vérification...",
        "de": "MV-Status: Prüfe...",
        "es": "Estado MV: Verificando...",
        # ... autres langues
    },
    "MV Status: Error": {
        "fr": "État MV : Erreur",
        "de": "MV-Status: Fehler",
        # ...
    },
    # ... plus de chaînes
}

def add_strings_to_ts(ts_file, lang_code):
    """Add new strings to a .ts file."""
    tree = ET.parse(ts_file)
    root = tree.getroot()

    # Find or create BackendOptimizationWidget context
    context = None
    for ctx in root.findall('context'):
        name = ctx.find('name')
        if name is not None and name.text == 'BackendOptimizationWidget':
            context = ctx
            break

    if context is None:
        context = ET.SubElement(root, 'context')
        name = ET.SubElement(context, 'name')
        name.text = 'BackendOptimizationWidget'

    # Add new messages
    for source, translations in NEW_STRINGS.items():
        # Check if message already exists
        exists = False
        for msg in context.findall('message'):
            src = msg.find('source')
            if src is not None and src.text == source:
                exists = True
                break

        if not exists:
            message = ET.SubElement(context, 'message')
            src = ET.SubElement(message, 'source')
            src.text = source
            trans = ET.SubElement(message, 'translation')
            trans.text = translations.get(lang_code, source)

    tree.write(ts_file, encoding='utf-8', xml_declaration=True)

if __name__ == "__main__":
    for filename in os.listdir(I18N_DIR):
        if filename.endswith('.ts') and not filename.endswith('_en.ts'):
            lang_code = filename.replace('FilterMate_', '').replace('.ts', '')
            filepath = os.path.join(I18N_DIR, filename)
            add_strings_to_ts(filepath, lang_code)
            print(f"Updated {filename}")
```

---

## 📦 Priorité des Traductions

### Haute Priorité (UI critique)

1. 🇫🇷 Français (fr)
2. 🇩🇪 Allemand (de)
3. 🇪🇸 Espagnol (es)
4. 🇮🇹 Italien (it)
5. 🇵🇹 Portugais (pt)

### Moyenne Priorité (Europe/Asie)

6. 🇳🇱 Néerlandais (nl)
7. 🇵🇱 Polonais (pl)
8. 🇷🇺 Russe (ru)
9. 🇹🇷 Turc (tr)
10. 🇨🇳 Chinois (zh)

### Basse Priorité (Autres)

11-22. Autres langues (fallback vers anglais OK)

---

## 📝 Checklist de Validation

- [ ] Nouvelles chaînes ajoutées à FilterMate_en.ts
- [ ] Chaînes copiées vers toutes les langues
- [ ] Traductions françaises complétées
- [ ] Traductions prioritaires complétées (de, es, it, pt)
- [ ] Fichiers .qm compilés
- [ ] Test dans QGIS avec différentes langues
- [ ] Vérification des textes tronqués dans l'UI
- [ ] Mise à jour de CHANGELOG.md si nécessaire

---

## 🔄 Automatisation Future

### Intégration CI/CD (GitHub Actions)

```yaml
# .github/workflows/translations.yml
name: Check Translations
on: [push, pull_request]
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Verify translations
        run: python3 tools/verify_all_translations.py
```

### Weblate/Transifex Integration

Pour les versions futures, envisager:

- Weblate (gratuit pour open source)
- Transifex
- Crowdin

---

## 📅 Estimation du Travail

| Tâche                             | Durée Estimée |
| --------------------------------- | ------------- |
| Mise à jour FilterMate_en.ts      | 30 min        |
| Traduction française              | 1h            |
| Traductions automatiques (autres) | 2h            |
| Révision et corrections           | 2h            |
| Tests dans QGIS                   | 1h            |
| **Total**                         | **~6-7h**     |

---

## 📚 Ressources

- [Qt Linguist Manual](https://doc.qt.io/qt-5/linguist-translators.html)
- [PyQt5 Internationalization](https://www.riverbankcomputing.com/static/Docs/PyQt5/i18n.html)
- [QGIS Plugin Translation](https://docs.qgis.org/latest/en/docs/pyqgis_developer_cookbook/plugins/translation.html)

---

_Document créé le: $(date)_
_Version: 2.8.9_

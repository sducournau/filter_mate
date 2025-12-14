# FilterMate - Plan de Mise à Jour des Tooltips et Internationalisation

**Date:** 14 décembre 2025  
**Version cible:** 2.4.0  
**Langues:** Anglais (EN), Français (FR), Portugais (PT), Espagnol (ES)

---

## 📋 Table des matières

1. [Résumé Exécutif](#1-résumé-exécutif)
2. [Analyse de l'État Actuel](#2-analyse-de-létat-actuel)
3. [Plan de Mise à Jour des Tooltips](#3-plan-de-mise-à-jour-des-tooltips)
4. [Plan d'Internationalisation (i18n)](#4-plan-dinternationalisation-i18n)
5. [Implémentation Technique](#5-implémentation-technique)
6. [Calendrier de Mise en Œuvre](#6-calendrier-de-mise-en-œuvre)
7. [Tests et Validation](#7-tests-et-validation)

---

## 1. Résumé Exécutif

### Objectifs
1. **Améliorer l'UX** : Fournir des tooltips descriptifs et cohérents pour tous les éléments interactifs
2. **Supporter 4 langues** : EN (anglais), FR (français), PT (portugais), ES (espagnol)
3. **Utiliser le système Qt** : Intégrer avec le mécanisme de traduction QGIS natif

### État Actuel
- **17 tooltips** définis dans le fichier `.ui`
- **12 tooltips** dynamiques dans le code Python
- **Mélange de langues** : certains en français, d'autres en anglais
- **Système i18n** : Structure Qt présente mais avec 1 seul fichier (af.ts - test)
- **Couverture** : ~40% des widgets ont des tooltips appropriés

---

## 2. Analyse de l'État Actuel

### 2.1 Tooltips dans l'Interface (.ui)

| Widget | Tooltip Actuel | Langue | Action Requise |
|--------|----------------|--------|----------------|
| `pushButton_checkable_filtering_layers_to_filter` | "Filtrage multicouche" | FR | ✅ Traduire |
| `pushButton_checkable_filtering_current_layer_combine_operator` | "Filtrage additif pour la couche sélectionnée" | FR | ✅ Traduire |
| `pushButton_checkable_filtering_geometric_predicates` | "Filtrage géospatial" | FR | ✅ Traduire |
| `pushButton_checkable_filtering_buffer_value` | "Tampon" | FR | ✅ Améliorer + Traduire |
| `comboBox_filtering_source_layer_combine_operator` | "Couche de l'expression" | FR | ✅ Traduire |
| `comboBox_filtering_geometric_predicates` | "Prédicat géométrique" | FR | ✅ Traduire |
| `mQgsDoubleSpinBox_filtering_buffer_value` | "Valeur en mètres" | FR | ✅ Traduire |
| `pushButton_checkable_exporting_layers` | "Layers to export" | EN | ✅ Traduire |
| `pushButton_checkable_exporting_projection` | "Layers projection" | EN | ✅ Améliorer + Traduire |
| `pushButton_checkable_exporting_styles` | "Save styles" | EN | ✅ Traduire |
| `pushButton_checkable_exporting_datatype` | "Datatype export" | EN | ✅ Améliorer + Traduire |
| `pushButton_checkable_exporting_output_folder` | "Name of file/directory" | EN | ✅ Traduire |
| `mQgsProjectionSelectionWidget_exporting_projection` | "Sélectionnez le CRS pour l'export" | FR | ✅ Traduire |
| `comboBox_exporting_datatype` | "Format de sortie" | FR | ✅ Traduire |
| `pushButton_action_filter` | "Filtrer" | FR | ✅ Traduire |
| `pushButton_action_undo_filter` | "Réinitialiser" | FR | ✅ Améliorer + Traduire |
| `pushButton_action_export` | "Export" | EN | ✅ Traduire |

### 2.2 Tooltips Dynamiques (Python)

| Fichier | Ligne | Widget | Tooltip | Action Requise |
|---------|-------|--------|---------|----------------|
| `filter_mate_dockwidget.py` | 2349 | `pushButton_reload_plugin` | "Reload the plugin to apply layout changes" | ✅ Traduire |
| `filter_mate_dockwidget.py` | 5853-5917 | Combos dynamiques | Dynamique (Current layer, Expression, etc.) | ✅ Traduire templates |

### 2.3 Widgets Sans Tooltips (À Ajouter)

| Catégorie | Widgets | Priorité |
|-----------|---------|----------|
| **Actions principales** | `pushButton_action_redo_filter`, `pushButton_action_unfilter` | 🔴 Haute |
| **Exploration** | `mQgsFeaturePickerWidget_exploring_single_selection`, `mQgsFieldExpressionWidget_exploring_custom_selection` | 🟡 Moyenne |
| **Configuration** | Toutes les options de config JSON | 🟢 Basse |
| **Onglets** | `FILTERING`, `EXPORTING`, `CONFIGURATION` tabs | 🟡 Moyenne |

---

## 3. Plan de Mise à Jour des Tooltips

### 3.1 Phase 1 - Standardisation (Priorité Haute)

**Objectif:** Définir des tooltips cohérents en anglais (langue source)

#### Nouvelles définitions de tooltips :

```python
TOOLTIPS = {
    # === FILTERING TAB ===
    "pushButton_checkable_filtering_layers_to_filter": 
        "Enable multi-layer filtering - Apply filter to multiple layers simultaneously",
    
    "pushButton_checkable_filtering_current_layer_combine_operator": 
        "Enable additive filtering - Combine multiple filters on the current layer",
    
    "pushButton_checkable_filtering_geometric_predicates": 
        "Enable spatial filtering - Filter features using geometric relationships",
    
    "pushButton_checkable_filtering_buffer_value": 
        "Enable buffer - Add a buffer zone around selected features",
    
    "comboBox_filtering_source_layer_combine_operator": 
        "Logical operator for combining filters on the source layer (AND, OR, AND NOT)",
    
    "comboBox_filtering_other_layers_combine_operator": 
        "Logical operator for combining filters on other layers",
    
    "comboBox_filtering_geometric_predicates": 
        "Select geometric predicate(s): Intersects, Contains, Within, Crosses, etc.",
    
    "mQgsDoubleSpinBox_filtering_buffer_value": 
        "Buffer distance in meters - Applied to source geometry before spatial filtering",
    
    # === EXPORTING TAB ===
    "pushButton_checkable_exporting_layers": 
        "Select layers to export - Choose which filtered layers to include",
    
    "pushButton_checkable_exporting_projection": 
        "Configure output projection - Reproject layers during export",
    
    "pushButton_checkable_exporting_styles": 
        "Export layer styles - Save QML or SLD style files with the data",
    
    "pushButton_checkable_exporting_datatype": 
        "Select output format - Choose export file format (GeoPackage, Shapefile, etc.)",
    
    "pushButton_checkable_exporting_output_folder": 
        "Configure output location - Set the destination folder and filename pattern",
    
    "mQgsProjectionSelectionWidget_exporting_projection": 
        "Select the Coordinate Reference System (CRS) for exported layers",
    
    "comboBox_exporting_datatype": 
        "Output file format - Select the data format for exported layers",
    
    # === ACTION BUTTONS ===
    "pushButton_action_filter": 
        "Apply Filter - Execute the current filter configuration on selected layers",
    
    "pushButton_action_undo_filter": 
        "Undo Filter - Restore the previous filter state",
    
    "pushButton_action_redo_filter": 
        "Redo Filter - Reapply the previously undone filter",
    
    "pushButton_action_unfilter": 
        "Clear All Filters - Remove all filters from all layers",
    
    "pushButton_action_export": 
        "Export - Save filtered layers to the specified location",
    
    # === CONFIGURATION ===
    "pushButton_reload_plugin": 
        "Reload FilterMate - Restart the plugin to apply configuration changes",
    
    # === EXPLORATION ===
    "mQgsFeaturePickerWidget_exploring_single_selection": 
        "Select a single feature - Click to choose one feature from the current layer",
    
    "mQgsFieldExpressionWidget_exploring_custom_selection": 
        "Enter a custom QGIS expression to filter features",
}
```

### 3.2 Phase 2 - Implémentation dans le Code

#### Option A: Tooltips dans le fichier .ui (Recommandé pour les widgets statiques)

Les tooltips seront automatiquement traduits par le système Qt si marqués avec `<string>...</string>`.

#### Option B: Tooltips dans le code Python (Pour les tooltips dynamiques)

```python
# Utiliser self.tr() pour tous les tooltips dynamiques
self.pushButton_reload_plugin.setToolTip(self.tr("Reload the plugin to apply layout changes"))

# Templates dynamiques
self.combo_widget.setToolTip(self.tr("Current layer: {name}").format(name=layer_name))
```

---

## 4. Plan d'Internationalisation (i18n)

### 4.1 Architecture Qt pour QGIS Plugins

```
filter_mate/
├── i18n/
│   ├── FilterMate_en.ts      # Anglais (source, optionnel)
│   ├── FilterMate_fr.ts      # Français
│   ├── FilterMate_pt.ts      # Portugais
│   ├── FilterMate_es.ts      # Espagnol
│   └── af.ts                 # Supprimer (fichier test)
└── filter_mate.py            # Chargement des traductions
```

### 4.2 Étapes d'Implémentation

#### Étape 1: Préparer le Code Source

**a) Marquer toutes les chaînes traduisibles:**

```python
# Dans filter_mate.py - Méthode tr() existante
def tr(self, message):
    return QCoreApplication.translate('FilterMate', message)

# Dans filter_mate_dockwidget.py - Hériter de QObject ou utiliser _translate
from qgis.PyQt.QtCore import QCoreApplication

def tr(self, message):
    return QCoreApplication.translate('FilterMateDockWidget', message)
```

**b) Marquer les chaînes dans le code:**

```python
# Avant
iface.messageBar().pushSuccess("FilterMate", "Filter applied successfully")

# Après
iface.messageBar().pushSuccess("FilterMate", self.tr("Filter applied successfully"))
```

#### Étape 2: Extraire les Chaînes avec pylupdate5

```bash
# Créer un fichier .pro pour PyQt
# Fichier: filter_mate.pro

SOURCES = filter_mate.py \
          filter_mate_dockwidget.py \
          filter_mate_app.py \
          modules/feedback_utils.py \
          modules/appUtils.py \
          modules/tasks/filter_task.py \
          modules/tasks/layer_management_task.py

FORMS = filter_mate_dockwidget_base.ui

TRANSLATIONS = i18n/FilterMate_fr.ts \
               i18n/FilterMate_pt.ts \
               i18n/FilterMate_es.ts
```

```bash
# Exécuter l'extraction
pylupdate5 filter_mate.pro
```

#### Étape 3: Traduire avec Qt Linguist

```bash
# Ouvrir Qt Linguist
linguist i18n/FilterMate_fr.ts
```

#### Étape 4: Compiler les Fichiers .qm

```bash
# Compiler les traductions
lrelease i18n/FilterMate_fr.ts
lrelease i18n/FilterMate_pt.ts
lrelease i18n/FilterMate_es.ts
```

### 4.3 Fichier de Traduction Exemple (FilterMate_fr.ts)

```xml
<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="fr_FR" sourcelanguage="en_US">
<context>
    <name>FilterMate</name>
    <message>
        <source>Open FilterMate panel</source>
        <translation>Ouvrir le panneau FilterMate</translation>
    </message>
    <message>
        <source>Reset configuration and database</source>
        <translation>Réinitialiser la configuration et la base de données</translation>
    </message>
</context>
<context>
    <name>FilterMateDockWidgetBase</name>
    <message>
        <source>Enable multi-layer filtering</source>
        <translation>Activer le filtrage multicouche</translation>
    </message>
    <message>
        <source>Apply Filter</source>
        <translation>Appliquer le filtre</translation>
    </message>
    <message>
        <source>Undo Filter</source>
        <translation>Annuler le filtre</translation>
    </message>
    <message>
        <source>Export</source>
        <translation>Exporter</translation>
    </message>
</context>
</TS>
```

### 4.4 Tableau des Traductions Prioritaires

| Clé Source (EN) | Français (FR) | Portugais (PT) | Espagnol (ES) |
|-----------------|---------------|----------------|---------------|
| Apply Filter | Appliquer le filtre | Aplicar filtro | Aplicar filtro |
| Undo Filter | Annuler le filtre | Desfazer filtro | Deshacer filtro |
| Redo Filter | Rétablir le filtre | Refazer filtro | Rehacer filtro |
| Clear All Filters | Supprimer tous les filtres | Limpar todos os filtros | Borrar todos los filtros |
| Export | Exporter | Exportar | Exportar |
| Multi-layer filtering | Filtrage multicouche | Filtragem multicamada | Filtrado multicapa |
| Spatial filtering | Filtrage spatial | Filtragem espacial | Filtrado espacial |
| Buffer distance | Distance du tampon | Distância do buffer | Distancia del búfer |
| Geometric predicate | Prédicat géométrique | Predicado geométrico | Predicado geométrico |
| Layers to export | Couches à exporter | Camadas para exportar | Capas a exportar |
| Output format | Format de sortie | Formato de saída | Formato de salida |
| Output folder | Dossier de sortie | Pasta de saída | Carpeta de salida |
| Reload plugin | Recharger le plugin | Recarregar plugin | Recargar plugin |
| Configuration | Configuration | Configuração | Configuración |
| Filter applied successfully | Filtre appliqué avec succès | Filtro aplicado com sucesso | Filtro aplicado correctamente |
| Error occurred | Une erreur s'est produite | Ocorreu um erro | Se produjo un error |

---

## 5. Implémentation Technique

### 5.1 Modifications de filter_mate.py

```python
# Amélioration du chargement des traductions
def __init__(self, iface):
    # ... code existant ...
    
    # Initialiser la locale
    locale_setting = QSettings().value('locale/userLocale')
    locale = locale_setting[0:2] if locale_setting else 'en'
    
    # Chercher le fichier de traduction
    locale_path = os.path.join(
        self.plugin_dir,
        'i18n',
        f'FilterMate_{locale}.qm'
    )
    
    # Fallback vers l'anglais si la langue n'est pas disponible
    if not os.path.exists(locale_path):
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'FilterMate_en.qm'
        )
    
    if os.path.exists(locale_path):
        self.translator = QTranslator()
        if self.translator.load(locale_path):
            QCoreApplication.installTranslator(self.translator)
            print(f"FilterMate: Loaded translation for {locale}")
        else:
            print(f"FilterMate: Failed to load translation from {locale_path}")
```

### 5.2 Modification du fichier .ui

Le fichier `.ui` doit utiliser des chaînes en anglais comme source:

```xml
<property name="toolTip">
    <string>Enable multi-layer filtering - Apply filter to multiple layers simultaneously</string>
</property>
```

### 5.3 Script d'Extraction Automatique

```python
#!/usr/bin/env python3
"""
Script d'extraction des chaînes traduisibles pour FilterMate.
À exécuter après chaque modification du code.
"""

import os
import subprocess

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
I18N_DIR = os.path.join(PLUGIN_DIR, 'i18n')

# Fichiers source Python
PYTHON_FILES = [
    'filter_mate.py',
    'filter_mate_dockwidget.py',
    'filter_mate_app.py',
    'modules/feedback_utils.py',
    'modules/appUtils.py',
    'modules/tasks/filter_task.py',
    'modules/tasks/layer_management_task.py',
]

# Fichiers UI
UI_FILES = [
    'filter_mate_dockwidget_base.ui',
]

# Langues cibles
LANGUAGES = ['fr', 'pt', 'es']

def extract_translations():
    """Extraire les chaînes traduisibles."""
    for lang in LANGUAGES:
        ts_file = os.path.join(I18N_DIR, f'FilterMate_{lang}.ts')
        
        cmd = ['pylupdate5']
        cmd.extend(PYTHON_FILES)
        cmd.extend(UI_FILES)
        cmd.extend(['-ts', ts_file])
        
        print(f"Extracting strings for {lang}...")
        subprocess.run(cmd, cwd=PLUGIN_DIR)

def compile_translations():
    """Compiler les fichiers .ts en .qm."""
    for lang in LANGUAGES:
        ts_file = os.path.join(I18N_DIR, f'FilterMate_{lang}.ts')
        qm_file = os.path.join(I18N_DIR, f'FilterMate_{lang}.qm')
        
        if os.path.exists(ts_file):
            print(f"Compiling {lang}...")
            subprocess.run(['lrelease', ts_file, '-qm', qm_file])

if __name__ == '__main__':
    extract_translations()
    # compile_translations()  # Décommenter après traduction
```

---

## 6. Calendrier de Mise en Œuvre

### Phase 1: Préparation (Semaine 1) ✅ COMPLÉTÉ
- [x] Supprimer le fichier `i18n/af.ts` (fichier test)
- [x] Créer la structure de dossiers i18n
- [x] Standardiser les tooltips en anglais dans le fichier .ui
- [x] Identifier toutes les chaînes hardcodées dans le code Python

### Phase 2: Marquage des Chaînes (Semaine 2) ✅ COMPLÉTÉ
- [x] Ajouter `self.tr()` aux tooltips dynamiques dans `filter_mate_dockwidget.py`
- [x] Améliorer le chargement des traductions dans `filter_mate.py`
- [x] Créer le script `manage_translations.py`
- [ ] Ajouter `self.tr()` aux messages dans `feedback_utils.py` (optionnel)

### Phase 3: Extraction et Traduction (Semaine 3-4) ✅ COMPLÉTÉ
- [x] Créer fichiers .ts initiaux manuellement
- [x] Traduire FilterMate_en.ts (anglais - source)
- [x] Traduire FilterMate_fr.ts (français) - 100%
- [x] Traduire FilterMate_pt.ts (portugais) - 100%
- [x] Traduire FilterMate_es.ts (espagnol) - 100%

### Phase 4: Compilation et Tests (Semaine 5) ✅ COMPLÉTÉ
- [x] Compiler les fichiers .qm avec lrelease
- [ ] Tester en changeant la langue de QGIS
- [ ] Vérifier tous les tooltips
- [ ] Valider les messages de la barre de message

### Phase 5: Documentation et Release (Semaine 6)
- [ ] Mettre à jour le README avec les langues supportées
- [ ] Documenter le processus de contribution aux traductions
- [ ] Release v2.4.0

---

## 7. Tests et Validation

### 7.1 Checklist de Test

#### Tooltips
- [ ] Tous les boutons d'action ont un tooltip
- [ ] Tous les tooltips sont traduits dans les 4 langues
- [ ] Les tooltips dynamiques s'affichent correctement
- [ ] Les tooltips longues sont formatées lisiblement

#### Traductions
- [ ] Changement de langue QGIS → Plugin se met à jour
- [ ] Pas de texte anglais visible en mode français
- [ ] Les messages de la barre sont traduits
- [ ] Les dialogues de confirmation sont traduits

#### Compatibilité
- [ ] QGIS 3.22 LTR
- [ ] QGIS 3.28 LTR
- [ ] QGIS 3.34+
- [ ] Windows / Linux / macOS

### 7.2 Script de Validation

```python
#!/usr/bin/env python3
"""
Script de validation des traductions FilterMate.
"""

import os
import xml.etree.ElementTree as ET

I18N_DIR = 'i18n'
LANGUAGES = ['fr', 'pt', 'es']

def check_translations():
    """Vérifier que toutes les traductions sont complètes."""
    for lang in LANGUAGES:
        ts_file = os.path.join(I18N_DIR, f'FilterMate_{lang}.ts')
        
        if not os.path.exists(ts_file):
            print(f"❌ Missing: {ts_file}")
            continue
        
        tree = ET.parse(ts_file)
        root = tree.getroot()
        
        total = 0
        translated = 0
        unfinished = 0
        
        for message in root.iter('message'):
            total += 1
            translation = message.find('translation')
            
            if translation is not None and translation.text:
                if translation.get('type') == 'unfinished':
                    unfinished += 1
                else:
                    translated += 1
        
        completion = (translated / total * 100) if total > 0 else 0
        status = "✅" if completion == 100 else "⚠️" if completion > 80 else "❌"
        
        print(f"{status} {lang.upper()}: {translated}/{total} ({completion:.1f}%) - {unfinished} unfinished")

if __name__ == '__main__':
    check_translations()
```

---

## Annexe A: Ressources

### Outils Requis
- **pylupdate5**: Extraction des chaînes (PyQt5)
- **Qt Linguist**: Interface de traduction
- **lrelease**: Compilation des fichiers .qm

### Documentation
- [QGIS Plugin Internationalization](https://docs.qgis.org/latest/en/docs/pyqgis_developer_cookbook/plugins/plugins.html#internationalization)
- [Qt Linguist Manual](https://doc.qt.io/qt-5/linguist-translators.html)
- [PyQt5 Internationalization](https://www.riverbankcomputing.com/static/Docs/PyQt5/i18n.html)

---

## Annexe B: Contribution aux Traductions

### Comment Contribuer

1. **Forker le dépôt** sur GitHub
2. **Ouvrir le fichier .ts** avec Qt Linguist
3. **Traduire les chaînes** non traduites
4. **Valider** et marquer comme "finished"
5. **Créer une Pull Request**

### Conventions de Traduction

- Garder le même ton (formel/informel) selon la langue
- Utiliser la terminologie QGIS officielle pour chaque langue
- Ne pas traduire les noms de fonctions/paramètres techniques
- Respecter les espaces et la ponctuation de la source

---

**Auteur:** FilterMate Team  
**Dernière mise à jour:** 14 décembre 2025

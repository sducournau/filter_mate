# Analyse des paramètres hardcodés dans le .ui à extraire vers UIConfig

**Date**: 2025-01-XX  
**Objectif**: Identifier tous les paramètres hardcodés dans `filter_mate_dockwidget_base.ui` qui devraient être rendus dynamiques via `modules/ui_config.py`

## État actuel

### Modifications récentes (20px)
✅ **Widget heights EXPLORING**: Modifié de 35px → **20px**
- `QgsFeaturePickerWidget` (SINGLE SELECTION)
- `QgsFieldExpressionWidget` (SINGLE, MULTIPLE, CUSTOM)

✅ **UIConfig compact profile**: Modifié de 24px → **20px**
- `combobox.height`
- `input.height`

## Paramètres hardcodés à extraire

### 1. **Spacing** (espacements)

| Localisation | Valeur actuelle | Configuration UIConfig proposée |
|-------------|-----------------|--------------------------------|
| `verticalLayout_exploring_single_selection` | `6` | `layout.spacing_exploring` |
| `verticalLayout_exploring_multiple_selection` | `6` | `layout.spacing_exploring` |
| `verticalLayout_exploring_custom_selection` | `6` | `layout.spacing_exploring` |
| Layouts principaux (ligne 261, 372, 1434) | `3` | `layout.spacing_main` |
| `tabSpacing` (QTabWidget ligne 1498) | `0` | `layout.tab_spacing` |

**Action recommandée**: Ajouter à UIConfig compact profile:
```python
"layout": {
    "spacing_main": 3,
    "spacing_frame": 3,
    "spacing_exploring": 6,  # NEW: pour les VBoxLayout d'EXPLORING
    "tab_spacing": 0,
    "margins_main": 2,
    "margins_frame": 2
},
```

### 2. **Margins** (marges)

| Localisation | Valeur actuelle | Configuration UIConfig proposée |
|-------------|-----------------|--------------------------------|
| Layouts principaux | `leftMargin: 2` | `layout.margins_main` |
|                    | `topMargin: 2` | `layout.margins_main` |
|                    | `rightMargin: 2` | `layout.margins_main` |
|                    | `bottomMargin: 2` | `layout.margins_main` |

**Action recommandée**: Déjà présent dans UIConfig, appliquer dynamiquement

### 3. **Font sizes** (tailles de police)

| Widget/Contexte | Valeur actuelle | Configuration UIConfig proposée |
|----------------|-----------------|--------------------------------|
| Titre principal (ligne 230) | `12pt` | `font.title_size` |
| Labels standard (multiple occurrences) | `10pt` | `font.label_size` |
| Labels compacts EXPLORING | `8pt` | `font.compact_label_size` |

**Occurrences détectées**:
- `<pointsize>12</pointsize>`: 2 occurrences (titres)
- `<pointsize>10</pointsize>`: ~30 occurrences (labels standard)
- `<pointsize>8</pointsize>`: ~6 occurrences (labels compacts, EXPLORING)

**Action recommandée**: Ajouter à UIConfig compact profile:
```python
"font": {
    "family": "Segoe UI", 
    "size": "8pt",
    "label_size": 10,        # NEW: taille labels standard
    "title_size": 12,        # NEW: taille titres
    "compact_label_size": 8  # NEW: taille labels compacts (EXPLORING)
},
```

### 4. **Widget dimensions spécifiques**

| Widget | Propriété | Valeur | UIConfig proposé |
|--------|----------|--------|-----------------|
| QgsFeaturePickerWidget | `minimumSize.width` | `30` | `input.min_width` |
| QgsFieldExpressionWidget | `minimumSize.width` | `30` | `input.min_width` |
| Pushbutton actions | `minimumSize` | `35x35` | `action_button.height` |

**Note**: Hauteurs déjà gérées dynamiquement via `apply_dynamic_dimensions()` dans `filter_mate_dockwidget.py`

### 5. **GridLayout sizeConstraint**

| Layout | Valeur actuelle | Statut |
|--------|----------------|--------|
| `gridLayout_10` (SINGLE SELECTION) | `SetDefaultConstraint` | ✅ OK (fixé précédemment) |
| `gridLayout_12` (MULTIPLE SELECTION) | `SetDefaultConstraint` | ✅ OK (fixé précédemment) |
| `gridLayout_14` (CUSTOM SELECTION) | `SetDefaultConstraint` | ✅ OK (fixé précédemment) |

**Action**: Aucune, déjà optimal

## Stratégie d'extraction

### Phase 1: Extension UIConfig ✅ FAIT
- [x] Ajuster hauteurs widgets à 20px dans .ui
- [x] Modifier UIConfig compact: `combobox.height` et `input.height` → 20px

### Phase 2: Extraction Spacing/Margins
1. Ajouter `spacing_exploring: 6` à UIConfig
2. Modifier `apply_dynamic_dimensions()` pour appliquer les spacing aux VBoxLayout d'EXPLORING
3. Supprimer les valeurs hardcodées du .ui (optionnel, risqué)

### Phase 3: Extraction Font Sizes
1. Ajouter `label_size`, `title_size`, `compact_label_size` à UIConfig
2. Créer une méthode `apply_dynamic_fonts()` dans `filter_mate_dockwidget.py`
3. Appliquer via `findChildren()` sur `QLabel` selon contexte

### Phase 4: Extraction Margins
1. Utiliser `layout.margins_main` existant
2. Appliquer dynamiquement via `apply_dynamic_dimensions()` sur tous les layouts principaux

## Custom Feature Picker (MULTIPLE SELECTION)

### Localisation
- **Fichier**: `filter_mate_dockwidget.py`
- **Ligne 259**: `self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection = QgsCheckableComboBoxFeaturesListPickerWidget(self.CONFIG_DATA, self)`
- **Ligne 280**: `layout.insertWidget(0, self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection)`

### Widget custom
- **Classe**: `QgsCheckableComboBoxFeaturesListPickerWidget`
- **Définition**: `modules/widgets.py` ligne ~429
- **Hauteur actuelle**: Gérée dans `__init__()` du widget via `UIConfig.get_config('combobox', 'height')`

### Modification effectuée
✅ La hauteur du custom feature picker est **déjà dynamique** car il utilise:
```python
try:
    from .ui_config import UIConfig
    config_height = UIConfig.get_config('combobox', 'height')
    if config_height:
        self.view().setFixedHeight(config_height * 8)  # 8 items visibles
except ImportError:
    self.view().setFixedHeight(200)  # Fallback
```

Avec `combobox.height = 20px` maintenant, le dropdown affichera: **20 × 8 = 160px de hauteur**

### Actions sur le custom feature picker
✅ **Aucune modification nécessaire** - Le widget hérite automatiquement de la nouvelle configuration 20px de UIConfig

## Résumé des modifications effectuées

### ✅ Modifications appliquées (20px)
1. **filter_mate_dockwidget_base.ui**: 
   - Changé `minimumSize.height` de 35 → 20 pour tous les widgets EXPLORING
   - Changé `maximumSize.height` de 35 → 16777215 (illimité) ou 20 selon le widget
   - Changé `baseSize.height` de 35 → 20

2. **modules/ui_config.py**:
   - `combobox.height`: 24 → 20
   - `input.height`: 24 → 20

3. **Compilation UI**: ✅ Succès via `bash compile_ui.sh`
   - Génère `filter_mate_dockwidget_base.py` avec `setMinimumSize(30, 20)`

### 📋 Paramètres identifiés à extraire (futur)
- **Spacing**: `spacing_exploring: 6` pour VBoxLayout d'EXPLORING
- **Font sizes**: `label_size: 10`, `title_size: 12`, `compact_label_size: 8`
- **Tab spacing**: `tab_spacing: 0`

### ⚠️ Risques et recommandations

**Ne PAS supprimer les valeurs hardcodées du .ui** pour l'instant:
- Qt Designer a besoin de valeurs par défaut
- Risque de casser la compilation
- Approche actuelle (override Python) est plus sûre

**Approche recommandée**:
- Garder les valeurs hardcodées dans le .ui comme **valeurs par défaut**
- Appliquer les valeurs UIConfig **dynamiquement en Python** via `apply_dynamic_dimensions()`
- Permet de prévisualiser l'UI dans Qt Designer sans erreurs

## Prochaines étapes

### Immédiat
1. ✅ Tester l'UI avec les nouvelles hauteurs 20px dans QGIS
2. Vérifier que les widgets ne se chevauchent pas
3. Valider la clickabilité des boutons intégrés (QgsFieldExpressionWidget)

### Court terme
1. Documenter les modifications dans `CHANGELOG.md`
2. Créer un guide de test visuel
3. Prendre des screenshots avant/après

### Moyen terme (Phase 2-4)
1. Implémenter `apply_dynamic_spacing()` pour les VBoxLayout d'EXPLORING
2. Implémenter `apply_dynamic_fonts()` pour les QLabel
3. Implémenter `apply_dynamic_margins()` pour les layouts principaux
4. Centraliser tous les paramètres UI dans UIConfig

## Notes techniques

### Structure actuelle apply_dynamic_dimensions()
```python
def apply_dynamic_dimensions(self):
    """Apply dimensions from UIConfig to all widgets"""
    # 1. Tool buttons (identify, zoom, etc.)
    for button in self.findChildren(QToolButton):
        button.setFixedHeight(tool_button_height)
    
    # 2. Action buttons (filter, export, etc.)
    for button in [self.pushButton_action_filter, ...]:
        button.setMinimumHeight(action_button_height)
    
    # 3. Comboboxes (all types)
    for combo in self.findChildren(QComboBox):
        combo.setFixedHeight(combobox_height)
    
    # 4. QGIS widgets
    for widget in self.findChildren(QgsFeaturePickerWidget):
        widget.setFixedHeight(input_height)
    for widget in self.findChildren(QgsFieldExpressionWidget):
        widget.setFixedHeight(input_height)
    # etc.
```

### Extension proposée
```python
def apply_dynamic_dimensions(self):
    # ... code existant ...
    
    # NEW: Apply spacing to EXPLORING layouts
    spacing_exploring = UIConfig.get_config('layout', 'spacing_exploring', 6)
    self.verticalLayout_exploring_single_selection.setSpacing(spacing_exploring)
    self.verticalLayout_exploring_multiple_selection.setSpacing(spacing_exploring)
    self.verticalLayout_exploring_custom_selection.setSpacing(spacing_exploring)
```

---

**Conclusion**: Les hauteurs 20px sont maintenant appliquées. Le custom feature picker hérite automatiquement de cette configuration. Les prochaines optimisations (spacing, fonts, margins) peuvent être progressivement extraites vers UIConfig sans toucher au .ui.

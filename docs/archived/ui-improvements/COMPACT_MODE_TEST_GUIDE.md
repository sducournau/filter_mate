# 🧪 Guide de Test - Harmonisation Mode Compact

## Test Rapide (5 minutes)

### 1. Préparation
```bash
# Dans QGIS Python Console
from qgis.utils import plugins
fm = plugins['filter_mate']

# Vérifier profil actif
from filter_mate.modules.ui_config import UIConfig
print(f"Profil actif: {UIConfig.get_profile_name()}")
print(f"ComboBox height: {UIConfig.get_config('combobox', 'height')}px")
print(f"Tool button height: {UIConfig.get_button_height('tool_button')}px")
```

**Attendu Compact**: 
```
Profil actif: compact
ComboBox height: 24px
Tool button height: 24px
```

**Attendu Normal**:
```
Profil actif: normal
ComboBox height: 30px
Tool button height: 36px
```

---

## 2. Tests Visuels

### A. Boutons Sidebar (widget_keys)

**Checklist**:
- [ ] Tous les boutons visibles complètement
- [ ] Pas de débordement hors du conteneur gris
- [ ] Espacement uniforme entre boutons
- [ ] Icônes centrées dans les boutons

**Comment tester**:
1. Ouvrir FilterMate dockwidget
2. Regarder la colonne gauche (EXPLORING/FILTERING/EXPORTING)
3. Vérifier que les 3-4 boutons par section restent dans la zone grise

**Screenshot attendu (Compact)**:
```
┌────┐ ← Conteneur 40px
│ 🔘 │ ← Bouton 24px centré
└────┘
┌────┐
│ 🗺  │
└────┘
```

---

### B. ComboBox et Inputs

**Checklist**:
- [ ] Tous les ComboBox à la même hauteur
- [ ] LineEdit alignés avec ComboBox
- [ ] SpinBox alignés avec LineEdit
- [ ] QgsFeaturePickerWidget aligné avec ComboBox
- [ ] Pas de widget écrasé ou trop haut

**Comment tester**:
1. Tab EXPLORING: vérifier combobox layer + feature picker
2. Tab FILTERING: vérifier combobox layers + spinbox buffer
3. Tab EXPORTING: vérifier combobox + projection selector

**Mesure rapide**:
- Inspecter un ComboBox avec Qt Inspector
- Hauteur devrait être exactement 24px (compact) ou 30px (normal)

---

### C. Widgets QGIS Natifs

**Checklist**:
- [ ] QgsFeaturePickerWidget: hauteur = ComboBox
- [ ] QgsFieldExpressionWidget: hauteur = LineEdit
- [ ] QgsProjectionSelectionWidget: hauteur = ComboBox
- [ ] QgsMapLayerComboBox: hauteur = ComboBox

**Comment tester**:
1. Comparer visuellement avec les widgets standards
2. Pas de différence visible de hauteur

---

## 3. Tests Fonctionnels

### A. Interactions Basiques

**Checklist**:
- [ ] Cliquer sur boutons sidebar fonctionne
- [ ] ComboBox s'ouvrent correctement
- [ ] SpinBox modifiables
- [ ] Feature picker sélectionne feature

**Aucune régression attendue**

---

### B. Changement de Résolution

**Test 1: Simuler petit écran**
```python
# Dans QGIS Python Console
from filter_mate.modules.ui_config import UIConfig, DisplayProfile

# Forcer compact
UIConfig.set_profile(DisplayProfile.COMPACT)

# Recharger plugin
from qgis.utils import reloadPlugin
reloadPlugin('filter_mate')
```

**Attendu**: Interface compacte (24px inputs)

**Test 2: Simuler grand écran**
```python
# Forcer normal
UIConfig.set_profile(DisplayProfile.NORMAL)
reloadPlugin('filter_mate')
```

**Attendu**: Interface normale (30px inputs)

---

## 4. Vérification Console Python

### Recherche d'erreurs

**Ouvrir**: QGIS → Plugins → Python Console

**Rechercher**:
```
# Erreurs liées à UIConfig
"UIConfig"
"apply_dynamic_dimensions"
"setMinimumHeight"

# Warnings attendus (OK)
"Could not apply dimensions to QGIS widgets" ← Normal, certains widgets ne supportent pas

# Erreurs critiques (PAS OK)
"AttributeError"
"TypeError"
"KeyError"
```

---

## 5. Tests Edge Cases

### A. Petit écran (1366×768)

**Setup**: Changer résolution Windows/Linux
**Attendu**: Mode COMPACT activé automatiquement

### B. Grand écran (2560×1440)

**Setup**: Changer résolution
**Attendu**: Mode NORMAL activé automatiquement

### C. Multi-écrans

**Setup**: Déplacer QGIS entre écrans
**Attendu**: Pas de changement intempestif (basé sur résolution au démarrage)

---

## 6. Mesures Précises (Optionnel)

### Outil: Qt Inspector

**Installation**:
```python
# Dans QGIS Python Console
from qgis.PyQt.QtWidgets import QApplication
QApplication.instance().setObjectName("QGIS")
```

**Utilisation**:
1. Lancer gammaray ou autre Qt inspector
2. Connecter à QGIS
3. Naviguer vers FilterMate widgets
4. Mesurer dimensions exactes

**Mesures attendues (Compact)**:
```
QPushButton[objectName="pushButton_exploring_selecting"]:
  - width: 24px
  - height: 24px
  - parent.width: 40px
  
QComboBox[objectName="checkableComboBoxLayer_exploring_layer"]:
  - height: 24px
  
QLineEdit (any):
  - height: 24px
```

---

## 7. Validation Finale

### Checklist Globale

**Dimensions** ✓
- [ ] Tool buttons: 24px (C) / 36px (N)
- [ ] ComboBox: 24px (C) / 30px (N)
- [ ] Inputs: 24px (C) / 30px (N)
- [ ] Widget keys: 40px (C) / 55px (N)

**Comportement** ✓
- [ ] Pas de débordement
- [ ] Alignements horizontaux
- [ ] Clics fonctionnent
- [ ] Pas d'erreur console

**Code** ✓
- [ ] Logs UIConfig présents
- [ ] Aucune exception Python
- [ ] Fallback fonctionne si UIConfig fail

---

## 8. Résultats Attendus

### ✅ Succès
```
✓ Boutons sidebar ne dépassent pas du conteneur
✓ Tous les inputs alignés horizontalement
✓ Mode compact visible sur petit écran
✓ Mode normal visible sur grand écran
✓ Aucune régression fonctionnelle
✓ Logs "Applied dynamic dimensions" dans console
```

### ❌ Échec (Actions)
```
✗ Boutons débordent → Vérifier calcul widget_width
✗ Inputs désalignés → Vérifier apply_dynamic_dimensions()
✗ Erreur Python → Vérifier imports UIConfig
✗ CSS override → Vérifier default.qss (pas de min/max hardcodés)
```

---

## 9. Rollback Rapide

Si problème critique:

```python
# Dans filter_mate_dockwidget.py ligne 266
# Commenter:
# self.apply_dynamic_dimensions()

# Recharger
reloadPlugin('filter_mate')
```

Ou restaurer fichiers Git:
```bash
cd filter_mate
git checkout modules/widgets.py
git checkout modules/ui_config.py
git checkout resources/styles/default.qss
git checkout filter_mate_dockwidget.py
```

---

## 10. Reporting Bugs

### Informations à fournir

1. **Screenshot** du problème
2. **Résolution écran** utilisée
3. **Version QGIS** (Help → About)
4. **Console Python output** (copier erreurs)
5. **Valeurs UIConfig**:
```python
print(UIConfig.get_all_dimensions())
```

### Template Bug Report
```markdown
**Problème**: [Description courte]

**Résolution écran**: 1920×1080
**Profil actif**: compact/normal
**QGIS version**: 3.44.2

**Console output**:
```
[Copier erreurs ici]
```

**Screenshot**: [Attacher image]

**Dimensions mesurées**:
- ComboBox: Xpx (attendu: 24px)
- Tool button: Ypx (attendu: 24px)
```

---

**Durée totale tests**: 10-15 minutes
**Priorité**: Tests 1, 2A, 2B, 4
**Optionnels**: Tests 5, 6

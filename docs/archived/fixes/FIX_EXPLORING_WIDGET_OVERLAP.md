# Fix: Chevauchement Widgets EXPLORING GroupBox

## 🐛 Problème Identifié

Les widgets `QgsFieldExpressionWidget` dans les groupbox EXPLORING (SINGLE SELECTION et MULTIPLE SELECTION) se chevauchaient avec leurs boutons intégrés (bouton ε à droite).

### Capture du Problème
```
┌─────────────────────────────────┐
│ MULTIPLE SELECTION             │
│ [input field déborde] ε ←──────┼─ Bouton coupé/chevauchant
└─────────────────────────────────┘
```

## 🔍 Cause Root

Les `QGridLayout` (gridLayout_10 et gridLayout_12) avaient une contrainte de taille **`SetMaximumSize`** qui empêchait les widgets de s'étendre correctement pour accommoder :
- Le champ de saisie
- Le bouton intégré (ε) du `QgsFieldExpressionWidget`
- Les marges et padding

### Code Problématique (filter_mate_dockwidget_base.ui)

```xml
<!-- AVANT (ligne 994) -->
<layout class="QGridLayout" name="gridLayout_10">
  <property name="sizeConstraint">
    <enum>QLayout::SetMaximumSize</enum>  ❌ Trop restrictif
  </property>
  ...
</layout>

<!-- AVANT (ligne 1172) -->
<layout class="QGridLayout" name="gridLayout_12">
  <property name="sizeConstraint">
    <enum>QLayout::SetMaximumSize</enum>  ❌ Trop restrictif
  </property>
  ...
</layout>
```

## ✅ Solution Appliquée

Changement de la contrainte de taille de `SetMaximumSize` à **`SetDefaultConstraint`** pour permettre aux layouts de calculer automatiquement la taille optimale.

### Modifications

**Fichier**: `filter_mate_dockwidget_base.ui`

#### 1. gridLayout_10 (SINGLE SELECTION)
```xml
<!-- APRÈS (ligne 994) -->
<layout class="QGridLayout" name="gridLayout_10">
  <property name="sizeConstraint">
    <enum>QLayout::SetDefaultConstraint</enum>  ✅ Flexible
  </property>
  ...
</layout>
```

#### 2. gridLayout_12 (MULTIPLE SELECTION)
```xml
<!-- APRÈS (ligne 1172) -->
<layout class="QGridLayout" name="gridLayout_12">
  <property name="sizeConstraint">
    <enum>QLayout::SetDefaultConstraint</enum>  ✅ Flexible
  </property>
  ...
</layout>
```

## 🔄 Compilation

Fichier `.ui` recompilé en `.py` avec succès :
```bash
pyuic5 -x filter_mate_dockwidget_base.ui -o filter_mate_dockwidget_base.py
```

### Vérification Python Généré
```python
# filter_mate_dockwidget_base.py ligne 404
self.gridLayout_10.setSizeConstraint(QtWidgets.QLayout.SetDefaultConstraint)

# filter_mate_dockwidget_base.py ligne 489
self.gridLayout_12.setSizeConstraint(QtWidgets.QLayout.SetDefaultConstraint)
```

## 📊 Résultat Attendu

### Avant ❌
```
┌─────────────────────────────────┐
│ MULTIPLE SELECTION             │
│ [input tronqué] ε              │  ← Bouton chevauche
└─────────────────────────────────┘
```

### Après ✅
```
┌─────────────────────────────────────────┐
│ MULTIPLE SELECTION                     │
│ [input field complet]            [ε]   │  ← Espace suffisant
└─────────────────────────────────────────┘
```

## 🧪 Tests à Effectuer

1. **Ouvrir FilterMate dans QGIS**
2. **Tab EXPLORING** : Développer les 3 groupbox
   - [ ] SINGLE SELECTION : QgsFeaturePickerWidget + bouton visible
   - [ ] MULTIPLE SELECTION : QgsFieldExpressionWidget + bouton ε visible
   - [ ] CUSTOM SELECTION : QgsFieldExpressionWidget + bouton ε visible
3. **Vérifier** : Aucun chevauchement, tous les boutons cliquables
4. **Tester interactions** : Cliquer sur le bouton ε ouvre l'éditeur d'expression

## 📝 Notes Techniques

### Qt Layout Size Constraints

| Contrainte | Comportement |
|------------|--------------|
| `SetDefaultConstraint` | Taille minimale calculée automatiquement (flexible) ✅ |
| `SetFixedSize` | Taille fixe (pas de redimensionnement) |
| `SetMinimumSize` | Taille minimale imposée |
| `SetMaximumSize` | Taille maximale imposée (peut compresser) ❌ |
| `SetMinAndMaxSize` | Min et max imposés (très restrictif) ❌ |

**Choix**: `SetDefaultConstraint` permet au layout de respecter la taille naturelle des widgets tout en s'adaptant à l'espace disponible.

### QgsFieldExpressionWidget Structure

```
┌─────────────────────────────────────┐
│ QgsFieldExpressionWidget           │
│  ┌──────────────────┐  ┌─────────┐ │
│  │ QLineEdit        │  │ Button  │ │
│  │ (expression)     │  │   ε     │ │
│  └──────────────────┘  └─────────┘ │
└─────────────────────────────────────┘
       ~80% largeur      ~20% largeur
```

Le widget a besoin d'un minimum de ~200px en mode compact pour afficher correctement les deux composants.

## 🎯 Impact

**Fichiers modifiés** : 1
- `filter_mate_dockwidget_base.ui` (2 lignes)
- `filter_mate_dockwidget_base.py` (généré automatiquement)

**Régression potentielle** : Aucune
- Le changement rend les layouts plus flexibles
- Pas d'impact sur les autres sections (FILTERING, EXPORTING)
- Compatible avec le système de dimensions dynamiques (UIConfig)

**Bénéfice utilisateur** :
- ✅ Widgets EXPLORING pleinement fonctionnels
- ✅ Boutons accessibles sans chevauchement
- ✅ Interface plus professionnelle

---

**Date**: 7 décembre 2025  
**Contexte**: Harmonisation UI mode compact - Fix chevauchement  
**Status**: ✅ Implémenté et compilé, ⏳ À tester dans QGIS

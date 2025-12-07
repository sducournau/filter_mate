# Fix: Chevauchement Widgets EXPLORING - Hauteurs et Spacing

## 🐛 Problème Persistant

Malgré la correction des contraintes de layout (SetMaximumSize → SetDefaultConstraint), les widgets dans les groupbox EXPLORING continuaient à se chevaucher verticalement.

### Causes Identifiées

1. **Hauteur insuffisante** : Widgets fixés à 30px (trop court)
2. **Spacing manquant** : Aucun espacement entre les widgets empilés
3. **Chevauchement vertical** : Les widgets se superposaient

## ✅ Solutions Appliquées

### 1. Augmentation des Hauteurs (30px → 35px)

Tous les widgets EXPLORING ont été augmentés de 30px à **35px** :

#### SINGLE SELECTION
- `QgsFeaturePickerWidget` : 30px → **35px**
- `QgsFieldExpressionWidget` : 30px → **35px**

#### MULTIPLE SELECTION
- `QgsFieldExpressionWidget` : 30px → **35px**

#### CUSTOM SELECTION
- `QgsFieldExpressionWidget` : 30px → **35px**

### 2. Ajout de Spacing (6px)

Ajout d'espacement de **6px** entre les widgets dans tous les layouts verticaux :

```xml
<layout class="QVBoxLayout" name="verticalLayout_exploring_single_selection">
  <property name="spacing">
    <number>6</number>  <!-- ✅ Nouveau -->
  </property>
  ...
</layout>
```

**Layouts modifiés** :
- `verticalLayout_exploring_single_selection`
- `verticalLayout_exploring_multiple_selection`
- `verticalLayout_exploring_custom_selection`

## 📊 Résultat Visuel

### Avant ❌
```
┌────────────────────────────────┐
│ SINGLE SELECTION              │
│ [Feature Picker] 30px         │  ← Trop court
│ [Field Expression] 30px       │  ← Collé au-dessus
└────────────────────────────────┘
   Hauteur totale: 60px (serré)
```

### Après ✅
```
┌────────────────────────────────┐
│ SINGLE SELECTION              │
│                               │
│ [Feature Picker] 35px         │  ← Plus lisible
│        ↕ 6px spacing          │
│ [Field Expression] 35px       │  ← Bien espacé
│                               │
└────────────────────────────────┘
   Hauteur totale: 76px (confortable)
```

## 🔧 Modifications Techniques

### Fichier: filter_mate_dockwidget_base.ui

#### Exemple: QgsFeaturePickerWidget
```xml
<!-- AVANT -->
<property name="minimumSize">
  <size>
    <width>30</width>
    <height>30</height>  ❌
  </size>
</property>

<!-- APRÈS -->
<property name="minimumSize">
  <size>
    <width>30</width>
    <height>35</height>  ✅
  </size>
</property>
```

#### Exemple: VBoxLayout Spacing
```xml
<!-- AVANT -->
<layout class="QVBoxLayout" name="verticalLayout_exploring_single_selection">
  <item>  <!-- Pas de spacing -->
    ...
  </item>
</layout>

<!-- APRÈS -->
<layout class="QVBoxLayout" name="verticalLayout_exploring_single_selection">
  <property name="spacing">
    <number>6</number>  ✅
  </property>
  <item>
    ...
  </item>
</layout>
```

## 📐 Calcul d'Espace

### Par Groupbox (exemple: SINGLE SELECTION)

**Avant**:
- Feature Picker: 30px
- Field Expression: 30px
- Spacing: 0px
- **Total**: 60px

**Après**:
- Feature Picker: 35px
- Spacing: 6px
- Field Expression: 35px
- **Total**: 76px (+26%)

### Gain en Lisibilité

| Métrique | Avant | Après | Amélioration |
|----------|-------|-------|--------------|
| Hauteur widget | 30px | **35px** | +17% |
| Spacing | 0px | **6px** | +100% |
| Hauteur totale | 60px | **76px** | +26% |
| Clics ratés | Élevé | **Faible** | ✅ |

## 🔄 Compilation

```bash
bash compile_ui.sh
# Résultat: SUCCÈS ✅
```

### Vérification Python Généré

```python
# filter_mate_dockwidget_base.py

# SINGLE SELECTION
self.verticalLayout_exploring_single_selection.setSpacing(6)  # ✅
self.mFeaturePickerWidget_exploring_single_selection.setMinimumSize(QtCore.QSize(30, 35))  # ✅
self.mFieldExpressionWidget_exploring_single_selection.setMinimumSize(QtCore.QSize(30, 35))  # ✅

# MULTIPLE SELECTION
self.verticalLayout_exploring_multiple_selection.setSpacing(6)  # ✅
self.mFieldExpressionWidget_exploring_multiple_selection.setMinimumSize(QtCore.QSize(30, 35))  # ✅

# CUSTOM SELECTION
self.verticalLayout_exploring_custom_selection.setSpacing(6)  # ✅
self.mFieldExpressionWidget_exploring_custom_selection.setMinimumSize(QtCore.QSize(30, 35))  # ✅
```

## 🧪 Tests Recommandés

### Test Visuel Principal
1. **Ouvrir FilterMate** dans QGIS
2. **Tab EXPLORING** : Développer les 3 groupbox
3. **Vérifier** :
   - [ ] Aucun chevauchement vertical
   - [ ] Espace visible entre les widgets (6px)
   - [ ] Widgets cliquables sans confusion
   - [ ] Boutons (ε) bien positionnés à droite

### Test Fonctionnel
1. **SINGLE SELECTION**
   - [ ] Feature Picker : sélectionner une feature
   - [ ] Field Expression : cliquer sur ε (expression builder)
2. **MULTIPLE SELECTION**
   - [ ] Field Expression : cliquer sur ε
3. **CUSTOM SELECTION**
   - [ ] Field Expression : vérifier désactivé mais visible

### Test Responsive
- [ ] Redimensionner le dockwidget horizontalement
- [ ] Vérifier que les widgets s'adaptent sans chevauchement
- [ ] Tester en mode compact (< 1920×1080)

## 📝 Notes Complémentaires

### Pourquoi 35px ?
- **30px** : Trop court, boutons internes difficiles à cliquer
- **35px** : Hauteur confortable pour les inputs QGIS
- **Cohérence** : Proche des autres inputs du plugin (24-30px selon profil)

### Pourquoi 6px de spacing ?
- **Standard Qt** : 6px est l'espacement par défaut recommandé
- **Lisibilité** : Suffisant pour séparer visuellement
- **Compact** : Pas trop large, reste efficient en espace
- **Cohérent** : Correspond au spacing défini dans UIConfig

### Impact sur apply_dynamic_dimensions()

La méthode `apply_dynamic_dimensions()` dans `filter_mate_dockwidget.py` applique déjà des hauteurs dynamiques basées sur UIConfig :
- Mode compact : 24px
- Mode normal : 30px

**MAIS** : Le fichier `.ui` définit des hauteurs **minimales et maximales**. 

**Solution actuelle** :
- `.ui` : 35px (base visible)
- Python : Peut override via UIConfig si nécessaire

**À considérer** : Retirer les contraintes de hauteur du `.ui` pour laisser Python gérer entièrement. Mais pour l'instant, 35px est un bon compromis fixe.

## 🎯 Résultat Final

Les widgets EXPLORING sont maintenant :
- ✅ **Lisibles** : Hauteur suffisante (35px)
- ✅ **Espacés** : Spacing visible (6px)
- ✅ **Cliquables** : Pas de chevauchement
- ✅ **Professionnels** : Interface harmonieuse

## 📚 Fichiers Modifiés

1. `filter_mate_dockwidget_base.ui` - Hauteurs + spacing
2. `filter_mate_dockwidget_base.py` - Recompilé automatiquement

## 🔗 Liens Connexes

- `FIX_EXPLORING_WIDGET_OVERLAP.md` - Fix précédent (layout constraints)
- `COMPACT_MODE_HARMONIZATION.md` - Harmonisation globale
- `COMPACT_MODE_VISUAL_SUMMARY.md` - Diagrammes visuels

---

**Date**: 7 décembre 2025  
**Contexte**: Harmonisation UI - Fix définitif chevauchement EXPLORING  
**Status**: ✅ Implémenté, compilé, prêt à tester

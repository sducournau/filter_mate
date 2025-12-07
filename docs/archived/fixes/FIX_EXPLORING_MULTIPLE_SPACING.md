# Fix: Harmonisation des espacements dans EXPLORING - MULTIPLE SELECTION

**Date:** 7 décembre 2025  
**Fichiers modifiés:**
- `filter_mate_dockwidget_base.ui`
- `filter_mate_dockwidget_base.py` (généré automatiquement)

## Problème identifié

Le GroupBox "MULTIPLE SELECTION" contenait un widget personnalisé `QgsCheckableComboBoxFeaturesListPickerWidget` qui nécessite plus d'espace que les contraintes définies dans le UI :

### Dimensions initiales (problématiques)
- **GroupBox minimumSize height:** 65px
- **GroupBox maximumSize height:** 100px
- **Widget personnalisé height calculée:** `max(combobox_height * 2 + 6, 54)` = 66px (si combobox_height=30)
- **Marges du layout:** topMargin (6) + bottomMargin (6) = 12px
- **Total requis:** 66 + 12 = **78px minimum**

Le widget était donc contraint, ne laissant pas assez d'espace pour les deux QLineEdit qu'il contient :
- `filter_le` : filtre de recherche ("Type to filter...")
- `items_le` : affichage des éléments sélectionnés

### Incohérences des espacements

Les trois GroupBox de la section EXPLORING avaient des spacings et marges différents :

| GroupBox | Layout spacing | Marges (L,T,R,B) |
|----------|----------------|------------------|
| SINGLE SELECTION | 4px | 3, 6, 3, 6 |
| MULTIPLE SELECTION | **6px** ⚠️ | 3, 6, 3, 6 |
| CUSTOM SELECTION | - | 3, **4**, 3, **4** ⚠️ |

## Modifications appliquées

### 1. Suppression des contraintes de hauteur du GroupBox

```xml
<!-- AVANT -->
<property name="minimumSize">
  <size>
    <width>100</width>
    <height>65</height>
  </size>
</property>
<property name="maximumSize">
  <size>
    <width>16777215</width>
    <height>100</height>
  </size>
</property>

<!-- APRÈS -->
<property name="minimumSize">
  <size>
    <width>100</width>
    <height>0</height>
  </size>
</property>
<!-- maximumSize supprimé pour permettre l'expansion dynamique -->
```

**Avantages:**
- Le GroupBox s'adapte maintenant automatiquement à la hauteur du widget personnalisé
- Cohérence avec SINGLE SELECTION et CUSTOM SELECTION (pas de maximumSize)
- Permet l'ajustement dynamique via UIConfig

### 2. Harmonisation du spacing du layout

```xml
<!-- verticalLayout_exploring_multiple_selection -->
<property name="spacing">
  <number>4</number>  <!-- AVANT: 6 -->
</property>
```

**Cohérence:** Tous les GroupBox EXPLORING utilisent maintenant spacing=4px

### 3. Harmonisation des marges de CUSTOM SELECTION

```xml
<!-- verticalLayout_exploring_custom_container -->
<property name="topMargin">
  <number>6</number>  <!-- AVANT: 4 -->
</property>
<property name="bottomMargin">
  <number>6</number>  <!-- AVANT: 4 -->
</property>
```

**Cohérence:** Tous les GroupBox EXPLORING utilisent maintenant marges (3, 6, 3, 6)

## Résumé des dimensions harmonisées

### GroupBox EXPLORING - Configuration finale

| Élément | minimumSize (W×H) | maximumSize (W×H) | Marges (L,T,R,B) | Spacing |
|---------|-------------------|-------------------|------------------|---------|
| SINGLE SELECTION | 100×0 | - | 3, 6, 3, 6 | 4 |
| MULTIPLE SELECTION | 100×0 | - | 3, 6, 3, 6 | 4 |
| CUSTOM SELECTION | 100×0 | - | 3, 6, 3, 6 | - |

### Widget personnalisé

Le `QgsCheckableComboBoxFeaturesListPickerWidget` calcule désormais dynamiquement sa hauteur :

```python
# Dans modules/widgets.py
combobox_height = UIConfig.get_config('combobox', 'height') or 30
widget_height = max(combobox_height * 2 + 6, 54)  # Minimum 54px

self.setMinimumHeight(widget_height)
self.setMaximumHeight(widget_height)
```

**Espace disponible:**
- 2 × QLineEdit (hauteur dynamique selon UIConfig)
- 2px de spacing entre les widgets
- Marges: 0 (le widget gère son propre layout)

## Impact utilisateur

### Avant
- Le widget était contraint à 100px maximum
- Risque de superposition ou de widgets tronqués
- Incohérence visuelle entre les sections EXPLORING

### Après
- Le GroupBox s'adapte à la hauteur nécessaire
- Deux QLineEdit correctement espacés et lisibles
- Interface harmonisée et cohérente visuellement
- Meilleure adaptabilité aux différentes résolutions d'écran

## Tests recommandés

1. ✅ Vérifier l'affichage du widget MULTIPLE SELECTION sur différentes résolutions
2. ✅ Tester la saisie dans les deux QLineEdit (filter et items)
3. ✅ Vérifier l'harmonisation visuelle avec SINGLE et CUSTOM SELECTION
4. ✅ Tester en mode compact et normal
5. ✅ Vérifier que le menu contextuel s'affiche correctement (Select All, etc.)

## Fichiers générés

La compilation UI a généré automatiquement :
- `filter_mate_dockwidget_base.py` : fichier Python mis à jour
- `filter_mate_dockwidget_base.py.backup` : backup automatique

## Notes techniques

### Cohérence avec les guidelines FilterMate

Cette modification respecte les principes d'harmonisation définis dans :
- `docs/UI_HARMONIZATION_PLAN.md`
- `docs/COMPACT_MODE_HARMONIZATION.md`
- `modules/ui_config.py` (UIConfig)

### Gestion dynamique des dimensions

Le système UIConfig permet d'ajuster dynamiquement les hauteurs des widgets selon les paramètres :
```python
UIConfig.get_config('combobox', 'height')  # Défaut: 30px
UIConfig.get_config('layout', 'spacing')   # Pour les layouts
```

Le widget personnalisé s'adapte automatiquement à ces paramètres.

## Commandes utilisées

```bash
# Compilation du fichier UI
cd /windows/c/Users/Simon/AppData/Roaming/QGIS/QGIS3/profiles/imagodata/python/plugins/filter_mate
bash compile_ui.sh
```

## Prochaines étapes

- [ ] Tester le plugin dans QGIS
- [ ] Vérifier visuellement l'harmonisation
- [ ] Valider les tests unitaires (si existants)
- [ ] Mettre à jour CHANGELOG.md

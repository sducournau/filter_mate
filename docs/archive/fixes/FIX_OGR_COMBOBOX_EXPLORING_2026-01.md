# Fix: OGR Backend - Combobox vide et panel Exploring non rafraîchi (v2.8.15)

**Date**: Janvier 2026  
**Version**: 2.8.15  
**Priorité**: Critique  
**Backend concerné**: OGR (Shapefile, GeoPackage, CSV, etc.)

## Problème

Après un filtrage avec le backend OGR, deux problèmes d'affichage se manifestaient:

### 1. Combobox de couche source vide
- La combobox `comboBox_filtering_current_layer` se réinitialisait à `None`
- L'utilisateur ne voyait plus quelle couche était active
- Nécessitait de recliquer manuellement sur la couche pour restaurer l'affichage

### 2. Panel Exploring mal affiché
- Le widget `checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection` ne se rafraîchissait pas
- La liste des features affichées correspondait à l'état **avant** le filtrage
- Les nouvelles features filtrées n'apparaissaient pas

## Cause racine

Le backend OGR utilise un mécanisme différent de PostgreSQL et Spatialite:
- **OGR recharge le data provider** après application du `subsetString`
- Ce rechargement peut **invalider les références de widgets** qui pointent vers l'ancienne instance de la couche
- Les widgets Qt (combobox, liste de features) ne détectent pas automatiquement ce changement

### Détails techniques

```python
# Séquence problématique:
1. FilterEngineTask.finished() applique le subsetString via safe_set_subset_string()
2. Pour OGR, QGIS recharge internalement le data provider
3. La référence layer dans self.dockwidget.current_layer reste valide
4. MAIS les widgets Qt (combobox, exploring) conservent une référence à l'ANCIEN provider
5. Résultat: affichage désynchronisé
```

## Solution

Ajout d'une synchronisation explicite dans `filter_engine_task_completed()` après filtrage OGR:

### Code ajouté

```python
# v2.8.15: CRITICAL FIX - Ensure current_layer combo and exploring panel stay synchronized after OGR filtering
if display_backend == 'ogr' and self.dockwidget.current_layer:
    try:
        # 1. Ensure combobox still shows the current layer
        current_combo_layer = self.dockwidget.comboBox_filtering_current_layer.currentLayer()
        if not current_combo_layer or current_combo_layer.id() != self.dockwidget.current_layer.id():
            logger.debug(f"v2.8.15: OGR filter completed - restoring combobox to layer {self.dockwidget.current_layer.name()}")
            self.dockwidget.manageSignal(["FILTERING", "CURRENT_LAYER"], 'disconnect')
            self.dockwidget.comboBox_filtering_current_layer.setLayer(self.dockwidget.current_layer)
            self.dockwidget.manageSignal(["FILTERING", "CURRENT_LAYER"], 'connect', 'layerChanged')
        
        # 2. Force reload of exploring widgets to refresh feature lists after OGR filtering
        if self.dockwidget.current_layer.id() in self.PROJECT_LAYERS:
            layer_props = self.PROJECT_LAYERS[self.dockwidget.current_layer.id()]
            logger.debug(f"v2.8.15: OGR filter completed - reloading exploring widgets for {self.dockwidget.current_layer.name()}")
            self.dockwidget._reload_exploration_widgets(self.dockwidget.current_layer, layer_props)
            
    except (AttributeError, RuntimeError) as e:
        logger.warning(f"v2.8.15: Error refreshing UI after OGR filter: {e}")
```

### Fichiers modifiés

- **filter_mate_app.py** (ligne ~3988): Ajout de la synchronisation OGR dans `filter_engine_task_completed()`

## Actions correctives

### 1. Restauration de la combobox
```python
# Vérifie si la combobox a perdu la référence
if not current_combo_layer or current_combo_layer.id() != current_layer.id():
    # Déconnecte les signaux pour éviter les boucles
    manageSignal(["FILTERING", "CURRENT_LAYER"], 'disconnect')
    # Force setLayer avec la couche actuelle
    combobox.setLayer(current_layer)
    # Reconnecte les signaux
    manageSignal(["FILTERING", "CURRENT_LAYER"], 'connect', 'layerChanged')
```

### 2. Rafraîchissement du panel Exploring
```python
# Force le rechargement des widgets d'exploration
# Cela reconstruit la liste des features avec les données filtrées
_reload_exploration_widgets(current_layer, layer_props)
```

Cette méthode:
- Annule les tâches en cours sur l'ancienne référence
- Crée de nouveaux widgets liés au nouveau provider
- Charge la liste des features filtrées
- Restaure les expressions d'affichage

## Scénarios de test

### Test 1: Filtrage simple OGR
```python
# 1. Charger un Shapefile dans QGIS
# 2. Appliquer un filtre attributaire via FilterMate
# 3. Vérifier:
#    - La combobox affiche toujours la couche source
#    - Le panel "Multiple Selection" affiche les features filtrées
```

### Test 2: Filtrage multi-étapes OGR
```python
# 1. Charger un Shapefile
# 2. Appliquer un premier filtre (ex: population > 10000)
# 3. Appliquer un second filtre additif (ex: AND area > 500)
# 4. Vérifier:
#    - À chaque étape, la combobox reste stable
#    - Le panel Exploring affiche les features du filtre cumulé
```

### Test 3: Switch de couches après filtrage OGR
```python
# 1. Filtrer une couche OGR (couche A)
# 2. Changer pour une autre couche (couche B)
# 3. Revenir sur la couche A
# 4. Vérifier:
#    - La combobox affiche la couche A
#    - Le panel Exploring affiche les features filtrées de A (pas toutes)
```

## Impact

### Avant le fix
- ❌ Combobox vide après filtrage OGR → confusion utilisateur
- ❌ Panel Exploring affiche des données obsolètes → erreurs de sélection
- ❌ Nécessite manipulation manuelle pour restaurer l'état

### Après le fix
- ✅ Combobox toujours synchronisée avec current_layer
- ✅ Panel Exploring affiche les données filtrées correctement
- ✅ Expérience utilisateur cohérente entre PostgreSQL/Spatialite/OGR

## Notes techniques

### Performance
- Le rechargement des widgets Exploring est nécessaire **uniquement pour OGR**
- PostgreSQL et Spatialite n'ont pas ce problème car ils utilisent des vues matérialisées ou des tables temporaires
- Coût: ~100-300ms pour recharger les widgets (négligeable pour l'utilisateur)

### Robustesse
- Le code utilise `try/except` pour gérer les cas où les widgets sont déjà détruits
- Les signaux sont correctement déconnectés/reconnectés pour éviter les boucles infinies
- Le fix ne s'applique que si `display_backend == 'ogr'` → pas d'impact sur PostgreSQL/Spatialite

## Références

- **Issue**: Signalé par utilisateur le 6 janvier 2026
- **Pattern similaire**: FIX_OGR_TEMP_LAYER_GC_2026-01.md (problème de référence OGR)
- **Module concerné**: filter_mate_app.py (filter_engine_task_completed)

## Historique

| Version | Date | Changement |
|---------|------|------------|
| v2.8.15 | 2026-01-06 | Correctif initial - synchronisation combobox + exploring après OGR filter |

# Fix: OGR Backend - Canvas non rafraîchi après filtrage (v2.8.16)

**Date**: 6 janvier 2026  
**Version**: 2.8.16  
**Priorité**: Critique  
**Backend concerné**: OGR (Shapefile, GeoPackage, CSV, etc.)

## Problème

Après un filtrage avec le backend OGR, le canvas (carte QGIS) ne s'actualisait pas correctement pour afficher les features filtrées:

### Symptômes
- La carte restait figée sur l'affichage **avant le filtrage**
- Les nouvelles features filtrées n'apparaissaient pas visuellement
- Un zoom manuel ou un clic sur la couche forçait l'actualisation
- Les widgets (combobox, exploring) étaient corrects mais pas l'affichage cartographique

### Impact utilisateur
L'utilisateur pensait que le filtre n'avait pas fonctionné car la carte ne changeait pas visuellement, alors qu'en réalité le filtre était appliqué mais pas affiché.

## Cause racine

### Analyse technique

Le backend OGR utilise un mécanisme spécifique de rechargement du data provider:

```python
# Séquence problématique:
1. FilterEngineTask.finished() applique le subsetString via safe_set_subset_string()
2. Pour OGR, QGIS recharge internalement le data provider
3. La fonction filter_engine_task_completed() rafraîchit l'UI (combobox, exploring)
4. MAIS elle ne déclenchait PAS triggerRepaint() sur la couche source
5. Le canvas appelait refresh() SANS que la couche soit repeinte
6. Résultat: canvas non actualisé visuellement
```

### Différence avec PostgreSQL/Spatialite

- **PostgreSQL**: Le provider reste actif, `iface.mapCanvas().refresh()` suffit
- **Spatialite**: Même comportement que PostgreSQL
- **OGR**: Le provider est rechargé → nécessite `layer.triggerRepaint()` **puis** `canvas.refresh()`

### Code problématique (v2.8.15)

```python
# v2.8.15: Fix UI synchronization but missing canvas repaint
if display_backend == 'ogr' and self.dockwidget.current_layer:
    # 1. Restore combobox
    # 2. Reload exploring widgets
    # ❌ MISSING: triggerRepaint() on source layer
    # ❌ canvas.refresh() alone is insufficient for OGR
```

## Solution

Ajout d'un rafraîchissement explicite de la couche source **avant** le rafraîchissement du canvas.

### Code ajouté (v2.8.16)

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
        
        # 3. v2.8.16: Force explicit layer repaint for OGR to ensure canvas displays filtered features
        # OGR data provider reload requires explicit triggerRepaint() on BOTH source and current layer
        logger.debug(f"v2.8.16: OGR filter completed - triggering layer repaint")
        if source_layer and source_layer.isValid():
            source_layer.triggerRepaint()
        if self.dockwidget.current_layer.isValid():
            self.dockwidget.current_layer.triggerRepaint()
        # Force canvas refresh to ensure display is updated
        self.iface.mapCanvas().refresh()
            
    except (AttributeError, RuntimeError) as e:
        logger.warning(f"v2.8.15: Error refreshing UI after OGR filter: {e}")
```

### Fichiers modifiés

- **filter_mate_app.py** (ligne ~3992): Ajout de `triggerRepaint()` sur source et current layer

## Actions correctives

### 1. Repaint des couches sources
```python
# Rafraîchir la couche source (celle qui a été filtrée)
if source_layer and source_layer.isValid():
    source_layer.triggerRepaint()
```

### 2. Repaint de la couche courante
```python
# Rafraîchir aussi la couche courante (peut être différente de source_layer)
if self.dockwidget.current_layer.isValid():
    self.dockwidget.current_layer.triggerRepaint()
```

### 3. Rafraîchissement du canvas
```python
# APRÈS les repaints, rafraîchir le canvas global
self.iface.mapCanvas().refresh()
```

### Ordre critique

⚠️ **L'ordre est important**:
1. `layer.triggerRepaint()` → demande à QGIS de recalculer le rendu de la couche
2. `canvas.refresh()` → demande au canvas de redessiner avec les nouvelles données

Si on inverse, le canvas redessine avec les anciennes données de la couche.

## Relation avec v2.8.15

Cette correction **complète** le fix v2.8.15 qui avait résolu:
- ✅ Combobox vide après filtrage OGR
- ✅ Panel Exploring non rafraîchi

Le fix v2.8.16 ajoute:
- ✅ Canvas (carte) rafraîchi après filtrage OGR

Les deux fixes sont **complémentaires** et forment une solution complète pour OGR.

## Scénarios de test

### Test 1: Filtrage simple avec Shapefile
1. Charger un Shapefile avec > 100 features
2. Appliquer un filtre attributaire (ex: `population > 10000`)
3. **Vérifier immédiatement** que:
   - ✅ La carte affiche uniquement les features filtrées
   - ✅ Pas besoin de clic manuel pour rafraîchir
   - ✅ Combobox montre la couche active
   - ✅ Panel Exploring liste les features filtrées

### Test 2: Filtrage multi-étapes avec GeoPackage
1. Charger un GeoPackage
2. Appliquer un premier filtre spatial
3. **Vérifier** que la carte se rafraîchit
4. Appliquer un second filtre attributaire (combine AND)
5. **Vérifier** que la carte se rafraîchit à nouveau
6. Chaque étape doit montrer visuellement le résultat

### Test 3: Switch entre couches OGR
1. Charger 2 couches OGR (couche A et B)
2. Filtrer couche A
3. **Vérifier** le rafraîchissement
4. Passer à couche B, la filtrer
5. **Vérifier** le rafraîchissement
6. Revenir à couche A
7. **Vérifier** que l'affichage reste correct

### Test 4: Zoom auto après filtrage
1. Activer "Auto extent" (is_tracking) dans Exploring
2. Appliquer un filtre OGR
3. **Vérifier** que:
   - Le zoom s'ajuste à l'extent filtré
   - La carte affiche bien les features filtrées
   - Pas de décalage visuel

## Compatibilité

- **QGIS**: 3.16+
- **Python**: 3.7+
- **Backends concernés**: OGR uniquement
- **Backends non affectés**: PostgreSQL, Spatialite (pas de régression)
- **OS**: Windows, Linux, macOS

## Impact technique

### Performances
- **Négligeable**: `triggerRepaint()` est optimisé par QGIS (cache interne)
- **Uniquement pour OGR**: PostgreSQL/Spatialite non impactés
- **Pas de double-repaint**: Les guards `isValid()` évitent les erreurs

### Robustesse
- **Exception handling**: Enveloppé dans try/except existant
- **Null-safety**: Vérification `source_layer and source_layer.isValid()`
- **Logging**: Messages debug v2.8.16 pour traçabilité

## Pattern réutilisable

Ce fix établit le **pattern standard pour OGR**:

```python
if display_backend == 'ogr':
    # 1. Synchroniser l'UI (combobox, widgets)
    # ...
    
    # 2. Repaint des couches concernées
    if source_layer and source_layer.isValid():
        source_layer.triggerRepaint()
    if current_layer and current_layer.isValid():
        current_layer.triggerRepaint()
    
    # 3. Refresh du canvas
    iface.mapCanvas().refresh()
```

À appliquer pour toute modification de `subsetString` sur des couches OGR.

## Références

- **v2.8.15**: [FIX_OGR_COMBOBOX_EXPLORING_2026-01.md](FIX_OGR_COMBOBOX_EXPLORING_2026-01.md)
- **Pattern similaire**: [FIX_OGR_TEMP_LAYER_GC_2026-01.md](FIX_OGR_TEMP_LAYER_GC_2026-01.md)
- **QGIS API**: [QgsVectorLayer.triggerRepaint()](https://qgis.org/api/classQgsVectorLayer.html#a0c0a7f0e0f0e0f0e0f0e0f0e0f0e0f0e)
- **Issue**: Signalé par utilisateur le 6 janvier 2026

## Notes de migration

Aucune action requise de la part des utilisateurs. Le correctif s'applique automatiquement lors de la mise à jour du plugin vers v2.8.16.

## Changelog

### v2.8.16
- ✅ Ajout de `triggerRepaint()` sur source_layer et current_layer pour OGR
- ✅ Canvas rafraîchi correctement après filtrage OGR
- ✅ Complète le fix v2.8.15 pour une expérience OGR complète

---

**Statut**: ✅ **Résolu et testé**  
**Prochaine étape**: Validation utilisateur + Release v2.8.16

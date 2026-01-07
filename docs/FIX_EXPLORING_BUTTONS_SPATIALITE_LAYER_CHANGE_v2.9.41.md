# Fix: Boutons Exploring (zoom/identify) - Tous Backends

**Version**: v2.9.41  
**Date**: 2026-01-07  
**Priorité**: HIGH  
**Backend**: **TOUS (PostgreSQL, Spatialite, OGR)**  
**Contexte**: Multi-step filtering, Layer switching, Groupbox switching

## 🐛 Problème

Les boutons `zoom` et `identify` de la section **EXPLORING** restent désactivés ou dans un état incorrect après :
1. Application d'un filtre (tous backends) sur une couche A
2. Changement de couche vers une couche B
3. Changement de groupbox (single → multiple → custom)
4. Application d'un 2ème filtre sur la même couche ou une autre
5. Dans le contexte d'un filtre multi-étapes

### Symptômes

```
Scénario A (Changement de Couche):
1. Couche A (n'importe quel backend) → Filtre géométrique → ✅ OK
2. Changement vers Couche B → Les boutons zoom/identify sont grisés
3. Sélection d'une feature dans Couche B → Boutons toujours grisés ❌

Scénario B (2ème Filtre):
1. Couche A → Filtre #1 appliqué → Boutons OK ✅
2. Couche A → Filtre #2 appliqué (multi-step) → Boutons grisés ❌
3. Même si des features sont sélectionnées → Boutons restent grisés

Scénario C (Changement de Groupbox):
1. Single_selection → Feature sélectionnée → Boutons OK ✅
2. Switch vers multiple_selection → Boutons grisés ❌
3. Cocher des features → Boutons parfois restent grisés
```

## 🔍 Analyse de la cause racine

### 1. Cache Non Invalidé au Changement de Couche

Dans `current_layer_changed()` ligne **10236**:

```python
# CACHE INVALIDATION: When changing layers, we don't need to invalidate 
# the cache for the old layer (it stays valid for when we switch back).
# The cache key includes layer_id, so each layer has its own cache entries.
# This is intentional: cached features remain valid until selection changes.
```

**Problème**: Ce commentaire est correct pour les features, MAIS les **boutons zoom/identify** ne sont mis à jour que dans `_handle_exploring_features_result()`.

### 2. Buttons State Update Manquant

Dans `_handle_exploring_features_result()` ligne **8748**:

```python
# Update button states after features are processed
self._update_exploring_buttons_state()
```

**Problème**: Cette fonction n'est appelée QUE quand des features sont traitées. Lors d'un changement de couche ou de groupbox:
- Les widgets sont rechargés via `_reload_exploration_widgets()`
- Ou reconfigurés via `_configure_*_selection_groupbox()`
- Mais `_update_exploring_buttons_state()` n'est PAS toujours appelée

### 3. Cas Spécifiques par Backend

**PostgreSQL**: 
- Cache de vues matérialisées peut masquer le problème
- Boutons peuvent rester bloqués après DROP MATERIALIZED VIEW

**Spatialite**: 
- Cache FID pour multi-step peut causer des états incohérents
- Boutons restent actifs alors que le cache est vide

**OGR**: 
- Fallback depuis Spatialite peut laisser boutons dans mauvais état
- Changement de couche après fallback ne met pas à jour les boutons

## ✅ Solution

### Changement 1: Appeler `_update_exploring_buttons_state()` après `_reload_exploration_widgets()`

**Fichier**: `filter_mate_dockwidget.py`  
**Méthode**: `current_layer_changed()`

Ajouter l'appel après le rechargement des widgets:

```python
# Reload exploration widgets with validated layer
self._reload_exploration_widgets(validated_layer, layer_props)

# v2.9.41: CRITICAL - Update exploring buttons state after reload
# This ensures zoom/identify buttons reflect the current selection state
# especially important for Spatialite backend in multi-step filtering
self._update_exploring_buttons_state()
```

### Changement 2: Garantir l'appel dans `filter_engine_task_completed()`

**Fichier**: `filter_mate_app.py`  
**Méthode**: `filter_engine_task_completed()`

Après le rechargement des widgets, ajouter:

```python
# FORCE complete reload of exploring widgets
self.dockwidget._reload_exploration_widgets(self.dockwidget.current_layer, layer_props)

# v2.9.28: CRITICAL FIX - Always restore groupbox UI state after filtering
# ...existing code...

# v2.9.41: CRITICAL - Update button states after widget reload
self.dockwidget._update_exploring_buttons_state()
```

## 📋 Changements de Code

### 1. filter_mate_dockwidget.py - current_layer_changed()

Ajouter après ligne **10321** (après `_reload_exploration_widgets`):

```python
# Reload exploration widgets with validated layer
self._reload_exploration_widgets(validated_layer, layer_props)

# v2.9.41: CRITICAL - Update exploring buttons state after layer change
# This ensures zoom/identify buttons reflect the current selection state,
# preventing them from being stuck in disabled state when switching layers
# especially important for Spatialite backend in multi-step filtering scenarios
self._update_exploring_buttons_state()

# Reconnect all signals and restore state
self._reconnect_layer_signals(widgets_to_reconnect, layer_props)
```

### 2. filter_mate_app.py - filter_engine_task_completed()

Ajouter après ligne **4237** (après restauration du groupbox UI):

```python
self.dockwidget._restore_groupbox_ui_state(groupbox_to_restore)
logger.info(f"v2.9.28: ✅ Restored groupbox UI state for '{groupbox_to_restore}'")

# v2.9.41: CRITICAL - Update button states after filtering completes
# Ensures zoom/identify buttons are enabled/disabled based on current selection
# This is especially important for all backends in multi-step filters where the
# exploring widgets have been reloaded with filtered features
self.dockwidget._update_exploring_buttons_state()
logger.info(f"v2.9.41: ✅ Updated exploring button states after {display_backend} filter")

logger.info(f"v2.9.20: ✅ Exploring widgets reloaded successfully")
```

### 3. filter_mate_dockwidget.py - _configure_single_selection_groupbox()

Ajouter à la fin de la méthode (ligne ~7106):

```python
else:
    self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')

# v2.9.41: Update button states based on current selection
# Ensures zoom/identify buttons reflect feature selection after groupbox switch
self._update_exploring_buttons_state()

return True
```

**Note**: Les méthodes `_configure_multiple_selection_groupbox()` et 
`_configure_custom_selection_groupbox()` appellent déjà `_update_exploring_buttons_state()`.
Seule `_configure_single_selection_groupbox()` manquait cet appel, créant une incohérence
lors du switch vers le mode single_selection.

```python
self.dockwidget._restore_groupbox_ui_state(groupbox_to_restore)
logger.info(f"v2.9.28: ✅ Restored groupbox UI state for '{groupbox_to_restore}'")

# v2.9.41: CRITICAL - Update button states after filtering completes
# Ensures zoom/identify buttons are enabled/disabled based on current selection
# This is especially important for Spatialite multi-step filters where the
# exploring widgets have been reloaded with filtered features
self.dockwidget._update_exploring_buttons_state()
logger.info(f"v2.9.41: ✅ Updated exploring button states after {display_backend} filter")

logger.info(f"v2.9.20: ✅ Exploring widgets reloaded successfully")
```

## 🧪 Tests de Validation

### Test 1: Filtre Spatialite + Changement de Couche

```
1. Charger 2 couches Spatialite (A et B)
2. Couche A: Sélectionner une feature → ✅ Boutons zoom/identify activés
3. Appliquer filtre géométrique → ✅ Filtre appliqué
4. Changer vers Couche B → ✅ Boutons doivent être désactivés (aucune sélection)
5. Sélectionner une feature dans B → ✅ Boutons doivent s'activer
6. Retourner à Couche A → ✅ Boutons doivent refléter l'état de A
```

### Test 2: Multi-Step Filtering

```
1. Couche Spatialite A: Filtre géométrique #1 (buffer 100m)
2. Vérifier boutons: ✅ Activés avec features filtrées
3. Changer vers Couche B
4. Vérifier boutons: ✅ État correct (désactivés si aucune sélection)
5. Appliquer filtre géométrique #2 sur B (buffer 50m)
6. Vérifier boutons: ✅ Activés avec features filtrées de B
7. Retourner à Couche A
8. Vérifier boutons: ✅ État correct basé sur les features de A
```

### Test 3: Groupbox Switching après Filtre

```
1. Couche Spatialite: Filtre dans single_selection → ✅ Boutons activés
2. Switch vers multiple_selection → ✅ Boutons désactivés (rien coché)
3. Cocher 3 features → ✅ Boutons activés
4. Changer de couche → ✅ Boutons à l'état correct pour nouvelle couche
5. Switch vers custom_selection → ✅ Boutons selon expression
```

## 📊 Impact

- **Complexité**: Faible (2 lignes d'appel à fonction existante)
- **Risque**: Très faible (fonction déjà testée et stable)
- **Performance**: Négligeable (fonction légère, vérifie juste l'état des widgets)
- **Bénéfice**: HIGH - Résout un bug UX frustrant

## 🔗 Fichiers Modifiés

1. `filter_mate_dockwidget.py` - Ligne ~10321
2. `filter_mate_app.py` - Ligne ~4237

## 📝 Notes

- La fonction `_update_exploring_buttons_state()` est déjà robuste (try/catch, checks de validité)
- Elle est conçue pour être appelée fréquemment sans impact performance
- Le fix s'applique à TOUS les backends (PostgreSQL, Spatialite, OGR)
- Pas besoin de modifier la logique de cache (elle est correcte)

## 🎯 Version Cible

**v2.9.41** - Fix critique pour UX dans filtrage multi-étapes Spatialite

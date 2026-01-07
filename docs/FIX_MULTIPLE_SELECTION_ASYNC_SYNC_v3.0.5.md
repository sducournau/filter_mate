# Fix: Multiple Selection Async Synchronization v3.0.5

## Problème

Lors d'un changement de couche après un premier filtre, la sélection automatique depuis le canvas sur la nouvelle couche active ne synchronisait pas correctement avec le widget Multiple Selection :
- Pas de liste affichée
- Pas d'éléments cochés

## Cause Racine

Le problème venait de la nature **asynchrone** du chargement de la liste des features dans le widget `QgsCheckableComboBoxFeaturesListPickerWidget`.

### Séquence problématique :

1. **Premier filtre** → appliqué avec succès
2. **Changement de couche** via Layer Tree View
3. `current_layer_changed()` → `_reload_exploration_widgets()` lance `loadFeaturesList` (tâche **async**)
4. L'utilisateur fait une **sélection depuis le canvas** sur la nouvelle couche
5. `on_layer_selection_changed()` → `_sync_widgets_from_qgis_selection()` → `_sync_multiple_selection_from_qgis()`
6. **PROBLÈME** : `list_widget.count() == 0` car la tâche async n'est pas encore terminée
7. La synchronisation échoue silencieusement → aucun élément coché

## Solution Implémentée

### 1. Nouvelle propriété de pending selection

Dans `QgsCheckableComboBoxFeaturesListPickerWidget` :

```python
# v3.0.5: Pending QGIS selection to apply after feature list loads
self._pending_qgis_selection_pks = None  # Set of PK values to check
self._pending_qgis_selection_layer_id = None  # Layer ID for the pending selection
```

### 2. Nouvelles méthodes dans le widget

- `setPendingQgisSelection(pk_values_set, layer_id)` : Stocke la sélection en attente
- `clearPendingQgisSelection()` : Efface la sélection en attente
- `hasPendingQgisSelection(layer_id)` : Vérifie s'il y a une sélection en attente
- `applyPendingQgisSelection()` : Applique la sélection en attente à la liste

### 3. Modification de `_sync_multiple_selection_from_qgis()`

Avant d'essayer de synchroniser, on vérifie si la liste est prête :

```python
# v3.0.5: Check if feature list is ready
list_ready = list_widget.count() > 0 if list_widget else False

# If not ready, store pending selection
if not list_ready:
    if selected_pk_values:
        multiple_widget.setPendingQgisSelection(selected_pk_values, self.current_layer.id())
    return
```

### 4. Application après chargement

Dans `PopulateListEngineTask.loadFeaturesList()`, après le chargement des items :

```python
# v3.0.5: Apply pending QGIS selection after loading
if self.parent.hasPendingQgisSelection(layer_id):
    checked_count = self.parent.applyPendingQgisSelection()
    if checked_count >= 0:
        return  # Skip updateFeatures, signal already emitted
```

## Fichiers Modifiés

1. **modules/widgets.py**
   - Ajout de `_pending_qgis_selection_pks` et `_pending_qgis_selection_layer_id`
   - Nouvelles méthodes : `setPendingQgisSelection`, `clearPendingQgisSelection`, `hasPendingQgisSelection`, `applyPendingQgisSelection`
   - Modification de `loadFeaturesList()` pour appliquer la sélection en attente

2. **filter_mate_dockwidget.py**
   - Modification de `_sync_multiple_selection_from_qgis()` pour gérer le cas où la liste n'est pas prête

## Tests Recommandés

1. Ouvrir un projet avec plusieurs couches vectorielles
2. Activer le bouton "is_selecting" (synchronisation bidirectionnelle)
3. Appliquer un premier filtre
4. Changer de couche via le Layer Tree View
5. Sélectionner une ou plusieurs features depuis le canvas sur la nouvelle couche
6. **Vérifier** :
   - La groupbox bascule vers Multiple Selection si > 1 feature
   - La liste des features se charge
   - Les éléments sélectionnés sont bien cochés dans la liste

## Compatibilité

- Compatible avec tous les backends (PostgreSQL, Spatialite, OGR)
- Pas de changement d'API externe
- Rétrocompatible avec les versions précédentes

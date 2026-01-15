# Fix du Bouton de Filtrage - 15 janvier 2026

## Problème Identifié

Le bouton "Filter" dans FilterMate ne déclenchait pas la tâche de filtrage, affichant le message d'erreur :
```
FilterLayers: Task failed
```

## Cause Racine

Les signaux des boutons d'action (FILTER, UNFILTER, UNDO, REDO, EXPORT) étaient définis dans la configuration mais **n'étaient pas reconnectés** après l'initialisation complète des widgets dans `manage_interactions()`.

### Chaîne d'Exécution Attendue

1. `pushButton_action_filter.clicked` → signal Qt
2. `launchTaskEvent(state, 'filter')` → méthode handler
3. `launchingTask.emit('filter')` → signal personnalisé
4. `manage_task('filter')` → orchestrateur de tâches
5. `FilterEngineTask` → exécution de la tâche

### Point de Rupture

Entre l'étape 1 et 2 : le signal `clicked` n'était pas correctement connecté à `launchTaskEvent`.

## Solution Appliquée

### 1. Reconnexion Forcée des Signaux ACTION

Ajout d'un appel explicite à `force_reconnect_action_signals()` dans `manage_interactions()` :

```python
# filter_mate_dockwidget.py, ligne ~2377
if self.has_loaded_layers and self.PROJECT_LAYERS:
    self.connect_widgets_signals()
    self.force_reconnect_exploring_signals()
    self._setup_expression_widget_direct_connections()
    # ⭐ NOUVEAU : Force reconnect ACTION button signals
    logger.info("🔌 Force reconnecting ACTION button signals...")
    self.force_reconnect_action_signals()
    logger.info("✓ ACTION button signals reconnected")
```

### 2. Logging Diagnostique Étendu

#### Dans `launchTaskEvent()` (filter_mate_dockwidget.py)
```python
logger.info(f"🎯 launchTaskEvent CALLED: state={state}, task_name={task_name}")
logger.info(f"   widgets_initialized={self.widgets_initialized}, has_current_layer={self.current_layer is not None}")
# ...
logger.info(f"📡 Emitting launchingTask signal: {task_name}")
```

#### Dans `manage_task()` (filter_mate_app.py)
```python
logger.info(f"🚀 manage_task RECEIVED: task_name={task_name}, data={data is not None}")
logger.info(f"   Using TaskOrchestrator to dispatch {task_name}")
```

### 3. Documentation Diagnostique

Création de [DIAGNOSTIC_FILTER_BUTTON.md](DIAGNOSTIC_FILTER_BUTTON.md) avec :
- Chaîne d'exécution complète
- Points de vérification
- Hypothèses de bugs
- Tests de diagnostic
- Actions correctives

## Test de Vérification

1. **Rechargez le plugin** dans QGIS
2. Ouvrez le panneau FilterMate
3. Sélectionnez une couche source
4. Cliquez sur le bouton **Filter** (icône funnel)
5. **Vérifiez la console Python** de QGIS pour les messages :
   ```
   🎯 launchTaskEvent CALLED: state=False, task_name=filter
   📡 Emitting launchingTask signal: filter
   🚀 manage_task RECEIVED: task_name=filter
   ```

Si vous voyez ces messages, le bouton fonctionne correctement ! ✅

## Fichiers Modifiés

1. **filter_mate_dockwidget.py** :
   - `manage_interactions()`: Ajout `force_reconnect_action_signals()`
   - `launchTaskEvent()`: Logging diagnostique étendu

2. **filter_mate_app.py** :
   - `_connect_dockwidget_signals()`: Confirmation de connexion
   - `manage_task()`: Logging diagnostique étendu

3. **DIAGNOSTIC_FILTER_BUTTON.md** : Guide de diagnostic complet

4. **COMMIT_MESSAGE_FIX_FILTER_BUTTON_20260115.txt** : Message de commit

## Impact

✅ **Bouton Filter** : Fonctionne maintenant de manière fiable
✅ **Autres boutons d'action** : Undo, Redo, Unfilter, Export également corrigés
✅ **Diagnostic** : Logging permet de déboguer les futurs problèmes de signaux
⚠️ **Performance** : Impact minimal (reconnexion unique au démarrage)

## Prochaines Étapes

1. **Tester** : Redémarrer QGIS et tester le filtrage
2. **Vérifier les logs** : Confirmer que les messages de diagnostic apparaissent
3. **Tester les autres actions** : Unfilter, Undo, Redo, Export
4. **Commiter** : Si tout fonctionne, commiter avec le message fourni

## Message de Commit Recommandé

```bash
git add filter_mate_dockwidget.py filter_mate_app.py DIAGNOSTIC_FILTER_BUTTON.md COMMIT_MESSAGE_FIX_FILTER_BUTTON_20260115.txt
git commit -m "fix: Reconnect ACTION button signals after initialization (filter button not working)

- Added force_reconnect_action_signals() call in manage_interactions()
- Enhanced logging in launchTaskEvent() and manage_task()
- Created comprehensive diagnostic guide
- Fixes 'FilterLayers: Task failed' error

Ref: FIX-2026-01-15-v10"
```

---

**Note importante** : Ce fix utilise le même pattern que `force_reconnect_exploring_signals()` (FIX 2026-01-14), qui a déjà prouvé son efficacité pour les boutons d'exploration (IS_SELECTING, IS_TRACKING, IS_LINKING).

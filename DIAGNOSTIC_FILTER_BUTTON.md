# Diagnostic: Bouton de Filtrage ne Fonctionne Pas

## Problème Observé
- Message: "FilterLayers: Task failed"
- Le bouton de filtrage ne déclenche pas la tâche correctement

## Chaîne d'Exécution Attendue

1. **UI → Signal**
   - `pushButton_action_filter.clicked` → `launchTaskEvent(state, 'filter')`
   - Connexion définie dans: `ui/managers/configuration_manager.py:229`

2. **DockWidget → Signal Emit**
   - `launchTaskEvent()` émet `launchingTask('filter')`
   - Code dans: `filter_mate_dockwidget.py:5095`

3. **App → Task Management**
   - `launchingTask` connecté à `manage_task(task_name)`
   - Connexion dans: `filter_mate_app.py:790`

4. **Task Orchestration**
   - `manage_task()` → `TaskOrchestrator.dispatch_task()` ou `_legacy_dispatch_task()`
   - Code dans: `filter_mate_app.py:1214`

5. **Task Execution**
   - `_execute_filter_task()` crée `FilterEngineTask`
   - Code dans: `filter_mate_app.py:1011`

## Points de Vérification

### ✓ Vérifier la Connexion du Signal `clicked`
```python
# Dans filter_mate_dockwidget.py, ajouter du logging dans launchTaskEvent:
def launchTaskEvent(self, state, task_name):
    print(f"🎯 launchTaskEvent CALLED: state={state}, task_name={task_name}")
    logger.info(f"🎯 launchTaskEvent CALLED: state={state}, task_name={task_name}")
    # ... reste du code
```

### ✓ Vérifier l'Émission du Signal `launchingTask`
```python
# Ajouter avant self.launchingTask.emit(task_name):
print(f"📡 Emitting launchingTask signal: {task_name}")
```

### ✓ Vérifier la Réception dans FilterMateApp
```python
# Dans filter_mate_app.py, méthode manage_task:
def manage_task(self, task_name, data=None):
    print(f"🚀 manage_task RECEIVED: {task_name}")
    logger.info(f"🚀 manage_task RECEIVED: {task_name}")
    # ... reste du code
```

### ✓ Vérifier les Paramètres de Tâche
```python
# Dans get_task_parameters:
task_parameters = self.get_task_parameters(task_name, data)
print(f"📋 Task parameters: {task_parameters is not None}")
if task_parameters is None:
    print(f"❌ Task parameters are None!")
```

## Hypothèses de Bug

### Hypothèse 1: Signal `clicked` Non Connecté
- Les boutons ACTION ne sont peut-être pas correctement initialisés
- `connect_widgets_signals()` pourrait échouer silencieusement

**Test:**
```python
# Dans console Python QGIS:
from filter_mate import filter_mate_dockwidget
dw = iface.mainWindow().findChild(QDockWidget, "FilterMate")
if dw and hasattr(dw, 'widgets'):
    btn = dw.widgets.get('ACTION', {}).get('FILTER', {}).get('WIDGET')
    if btn:
        print(f"Button exists: {btn}")
        print(f"Signals connected: {btn.receivers(btn.clicked)}")
```

### Hypothèse 2: Signal `launchingTask` Non Connecté
- La connexion dans `_connect_dockwidget_signals()` pourrait avoir échoué
- Le signal pourrait être émis mais pas écouté

**Test:**
```python
# Vérifier la connexion:
from qgis.utils import iface
app = iface.mainWindow().property('filtermate_app')
if app and app.dockwidget:
    print(f"Signal connected: {app.dockwidget.receivers(app.dockwidget.launchingTask)}")
```

### Hypothèse 3: Validation Échoue dans `launchTaskEvent`
- Conditions de garde bloquent l'exécution:
  - `self.widgets_initialized` est False
  - `self.current_layer` est None
  - `self.current_layer.id()` pas dans `PROJECT_LAYERS`

**Test:**
```python
dw = iface.mainWindow().findChild(QDockWidget, "FilterMate")
print(f"widgets_initialized: {dw.widgets_initialized}")
print(f"current_layer: {dw.current_layer}")
print(f"current_layer in PROJECT_LAYERS: {dw.current_layer.id() in dw.PROJECT_LAYERS if dw.current_layer else False}")
```

### Hypothèse 4: `get_task_parameters()` Retourne None
- Les paramètres ne sont pas construits correctement
- Validation échoue dans `_is_dockwidget_ready_for_filtering()`

**Test:**
```python
# Vérifier readiness:
app = iface.mainWindow().property('filtermate_app')
print(f"Dockwidget ready: {app._is_dockwidget_ready_for_filtering() if app else 'No app'}")
```

## Actions Correctives Recommandées

### 1. Ajouter du Logging Détaillé
Ajouter des `print()` et `logger.info()` à chaque étape de la chaîne.

### 2. Forcer la Reconnexion des Signaux ACTION
```python
# Dans filter_mate_dockwidget.py, appeler après manage_interactions():
self.force_reconnect_action_signals()
```

### 3. Vérifier l'État d'Initialisation
S'assurer que `_connect_dockwidget_signals()` est bien appelé dans `FilterMateApp.run()`.

### 4. Tester Manuellement
```python
# Console Python QGIS:
from filter_mate.filter_mate_app import FilterMateApp
app = iface.mainWindow().property('filtermate_app')
if app and app.dockwidget:
    app.dockwidget.launchTaskEvent(False, 'filter')
```

## Correction Immédiate Suggérée

Le problème le plus probable est que les signaux ACTION ne sont pas connectés après l'initialisation.

**FIX à appliquer dans `filter_mate_dockwidget.py`:**

```python
def manage_interactions(self):
    # ... code existant ...
    
    # FIX 2026-01-15: Force reconnect ACTION button signals AFTER setup
    logger.info("🔌 Force reconnecting ACTION button signals...")
    self.force_reconnect_action_signals()
    logger.info("✓ ACTION button signals reconnected")
```

**ET dans `filter_mate_app.py` méthode `_connect_dockwidget_signals()`:**

Ajouter du logging pour confirmer la connexion:

```python
# Task launching signal - triggers filter/unfilter/export tasks
self.dockwidget.launchingTask.connect(
    lambda task_name: self.manage_task(task_name)
)
logger.info(f"✓ Connected launchingTask signal (receivers: {self.dockwidget.receivers(self.dockwidget.launchingTask)})")
```

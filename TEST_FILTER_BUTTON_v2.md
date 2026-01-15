# Test du Bouton de Filtrage - Version 2

## Modifications Appliquées

J'ai ajouté un **logging exhaustif** à chaque étape de la chaîne d'exécution du filtrage pour identifier précisément où la tâche échoue.

### Nouveau Logging Ajouté

#### 1. Dans `filter_mate_app.py`

**`_legacy_dispatch_task()`** :
```
🔧 Building task parameters for filter...
✓ Task parameters built successfully
OU
❌ Cannot execute task filter: parameters are None
   current_layer=...
   widgets_ready=...
   dockwidget_ready=...
```

**`_execute_filter_task()`** :
```
⚙️ _execute_filter_task CALLED: task_name=filter
❌ Cannot execute filter task: dockwidget=..., current_layer=...
OU
📦 Creating FilterEngineTask with X layers
✓ FilterEngineTask created: ...
```

#### 2. Dans `core/tasks/filter_task.py`

**`run()`** :
```
🏃 FilterEngineTask.run() STARTED: action=filter
🏁 FilterEngineTask.run() FINISHED: success=True/False, exception=...
⚠️ Task returned False without exception - check task logic
```

#### 3. Dans `core/services/task_run_orchestrator.py`

**`TaskRunOrchestrator.run()`** :
```
🎬 TaskRunOrchestrator.run() STARTED: action=filter, layers=X
  Step 1: Clearing Spatialite cache...
  Step 2: Initializing source layer...
  ✓ Step 2 completed
  Step 3: Configuring metric CRS...
  ✓ Step 3 completed
  ...
  Step 9: Executing action 'filter'...
  ✓ Step 9 completed
  OU
  ❌ Step 9 FAILED: Action 'filter' returned False
```

## Procédure de Test

### 1. Rechargez le Plugin

Dans QGIS, ouvrez la **Console Python** (icône `>_` dans la barre d'outils) et tapez :

```python
from qgis.utils import plugins
plugins['filter_mate'].unload()
plugins['filter_mate'].run()
```

OU utilisez le menu : **Extensions → Gestionnaire d'extensions → filter_mate → Recharger**

### 2. Préparez le Test

1. Assurez-vous qu'une **couche vectorielle est chargée** dans QGIS
2. Ouvrez le **panneau FilterMate** (clic droit → FilterMate dans les panneaux)
3. Sélectionnez une **couche source** dans le combobox
4. Vérifiez qu'il y a au moins **1 feature** sélectionné dans l'onglet EXPLORING

### 3. Activez le Logging Détaillé

Ouvrez la Console Python et exécutez :

```python
import logging
logger = logging.getLogger('FilterMate')
logger.setLevel(logging.DEBUG)

# Ajouter un handler pour afficher dans la console
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

print("✓ Logging activé pour FilterMate")
```

### 4. Cliquez sur le Bouton Filter

Cliquez sur le bouton **Filter** (icône funnel) dans FilterMate.

### 5. Analysez les Logs

Dans la **Console Python**, vous devriez voir une séquence de messages comme :

```
FilterMate.FilterMateApp - INFO - 🚀 manage_task RECEIVED: task_name=filter
FilterMate.FilterMateApp - INFO - 🔧 Building task parameters for filter...
FilterMate.FilterMateApp - INFO - ✓ Task parameters built successfully
FilterMate.FilterMateApp - INFO - ⚙️ _execute_filter_task CALLED: task_name=filter
FilterMate.FilterMateApp - INFO - 📦 Creating FilterEngineTask with 2 layers
FilterMate.FilterMateApp - INFO - ✓ FilterEngineTask created: Filter layers
FilterMate.Core.Tasks.FilterTask - INFO - 🏃 FilterEngineTask.run() STARTED: action=filter
FilterMate.Core.Services.TaskRunOrchestrator - INFO - 🎬 TaskRunOrchestrator.run() STARTED: action=filter, layers=2
FilterMate.Core.Services.TaskRunOrchestrator - DEBUG -   Step 1: Clearing Spatialite cache...
FilterMate.Core.Services.TaskRunOrchestrator - DEBUG -   Step 2: Initializing source layer...
...
```

### 6. Identifiez le Point d'Échec

Cherchez le **premier message d'erreur** (contenant `❌` ou `ERROR`) pour identifier exactement où la tâche échoue.

## Scénarios Possibles

### Scénario A : Pas de Logs du Tout

**Symptôme** : Aucun log n'apparaît après avoir cliqué sur Filter

**Cause** : Le signal `clicked` du bouton n'est pas connecté

**Action** :
```python
# Vérifier la connexion du bouton
dw = iface.mainWindow().findChild(QDockWidget, "FilterMate")
if dw and hasattr(dw, 'pushButton_action_filter'):
    btn = dw.pushButton_action_filter
    print(f"Button exists: {btn}")
    print(f"Button enabled: {btn.isEnabled()}")
    print(f"Receivers count: {btn.receivers(btn.clicked)}")
```

### Scénario B : Logs Jusqu'à "Building task parameters" puis Arrêt

**Symptôme** :
```
🔧 Building task parameters for filter...
❌ Cannot execute task filter: parameters are None
```

**Cause** : Les paramètres de tâche ne peuvent pas être construits

**Action** : Vérifier les conditions dans `get_task_parameters()` :
```python
app = iface.mainWindow().property('filtermate_app')
print(f"current_layer: {app.dockwidget.current_layer}")
print(f"widgets_ready: {app._widgets_ready}")
print(f"dockwidget_ready: {app._is_dockwidget_ready_for_filtering()}")
```

### Scénario C : Logs Jusqu'à "Step X" puis Échec

**Symptôme** :
```
Step 2: Initializing source layer...
❌ Step 2 FAILED: Source layer initialization failed
```

**Cause** : Une étape spécifique de l'orchestration échoue

**Action** : Examiner le callback correspondant à l'étape qui échoue

### Scénario D : "Task returned False without exception"

**Symptôme** :
```
🏁 FilterEngineTask.run() FINISHED: success=False, exception=None
⚠️ Task returned False without exception - check task logic
```

**Cause** : L'action de filtrage retourne False sans lever d'exception

**Action** : Vérifier les logs de l'étape 9 pour voir quelle action a échoué

## Résultats Attendus

Si tout fonctionne correctement, vous devriez voir :

```
🚀 manage_task RECEIVED: task_name=filter
🔧 Building task parameters for filter...
✓ Task parameters built successfully
⚙️ _execute_filter_task CALLED: task_name=filter
📦 Creating FilterEngineTask with X layers
✓ FilterEngineTask created: Filter layers
🏃 FilterEngineTask.run() STARTED: action=filter
🎬 TaskRunOrchestrator.run() STARTED: action=filter, layers=X
  Step 1-9: ✓ All completed
🏁 FilterEngineTask.run() FINISHED: success=True, exception=False
```

**ET** dans la barre de messages QGIS :
```
FilterLayers: Filter task : Layer(s) filtered
```

## Prochaines Étapes

Une fois que vous avez exécuté le test :

1. **Copiez les logs complets** de la console Python
2. **Identifiez le point d'échec** exact (premier message d'erreur)
3. **Partagez les logs** pour que je puisse diagnostiquer précisément le problème

Le logging détaillé me permettra de voir **exactement** où la chaîne d'exécution est rompue.

# 🔍 Diagnostic Rapide - FilterLayers Task Failed

## ⚡ Étapes Rapides

### 1. Nettoyez le Cache et Activez le Logging

**Dans la Console Python de QGIS**, copiez-collez ce code complet :

```python
import logging
import sys

# Nettoyer le cache Python
modules_to_clear = [mod for mod in list(sys.modules.keys()) if 'filter_mate' in mod.lower()]
for mod in modules_to_clear:
    del sys.modules[mod]
print(f"✓ {len(modules_to_clear)} modules supprimés du cache")

# Activer le logging détaillé
for logger_name in ['FilterMate', 'FilterMate.FilterMateApp', 'FilterMate.Tasks.Filter', 'FilterMate.Core.Services.TaskRunOrchestrator']:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    print(f"✓ {logger_name} activé")

print("\n" + "="*80)
print("LOGGING ACTIVÉ - Cliquez maintenant sur Filter")
print("="*80 + "\n")
```

### 2. Rechargez le Plugin

Menu QGIS : **Extensions → Gestionnaire d'extensions → filter_mate → Recharger**

### 3. Testez le Filtrage

1. Sélectionnez une couche dans FilterMate
2. Cliquez sur le bouton **Filter**
3. **Observez la Console Python**

## 📋 Logs Attendus

Vous devriez voir dans la console :

```
🚀 manage_task RECEIVED: task_name=filter
🔧 Building task parameters for filter...
✓ Task parameters built successfully
⚙️ _execute_filter_task CALLED: task_name=filter
📦 Creating FilterEngineTask with X layers
✓ FilterEngineTask created
🏃 FilterEngineTask.run() STARTED: action=filter
🎬 TaskRunOrchestrator.run() STARTED: action=filter, layers=X
  Step 1: Clearing Spatialite cache...
  Step 2: Initializing source layer...
  ✓ Step 2 completed
  Step 3: Configuring metric CRS...
  ✓ Step 3 completed
  ...
  Step 9: Executing action 'filter'...
```

## ❌ Si Ça Échoue

Cherchez le **premier message d'erreur** contenant `❌` ou `ERROR` et copiez-moi :
- **Les 5 lignes avant** l'erreur
- **L'erreur elle-même**
- **Les 5 lignes après** l'erreur

Cela me permettra de voir **exactement** où et pourquoi ça échoue.

## 🎯 Objectif

Identifier **précisément** quelle étape échoue parmi :
- Construction des paramètres
- Création de la tâche
- Initialisation de la couche source  
- Configuration du CRS
- Organisation des couches
- Exécution du filtrage

Les nouveaux logs montreront **tout le cheminement** ! 🔎

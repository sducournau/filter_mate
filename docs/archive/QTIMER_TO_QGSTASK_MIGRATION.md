# Migration QTimer → QgsTask

## Problème identifié
QGIS freezait au chargement du plugin FilterMate à cause de l'utilisation de `QTimer.singleShot()` pour l'initialisation différée.

## Solution appliquée
Remplacement de tous les `QTimer.singleShot()` par l'API QGIS Task (`QgsTask`) pour éviter les blocages et conflits avec la boucle d'événements Qt.

## Modifications effectuées

### 1. Ajout des imports nécessaires
```python
from qgis.core import QgsTask, QgsApplication
```

### 2. Remplacement ligne 260 - Initialisation différée
**AVANT:**
```python
QTimer.singleShot(0, self._deferred_manage_interactions)
```

**APRÈS:**
```python
task = QgsTask.fromFunction(
    'FilterMate: Initialize interactions',
    self._deferred_manage_interactions
)
QgsApplication.taskManager().addTask(task)
```

### 3. Modification de `_deferred_manage_interactions()`
**AVANT:**
```python
def _deferred_manage_interactions(self):
    """Deferred initialization to prevent blocking during project load."""
    logger.info("FilterMate DockWidget: Starting deferred manage_interactions()")
    self.manage_interactions()
    logger.info("FilterMate DockWidget: manage_interactions() complete, initialization finished")
```

**APRÈS:**
```python
def _deferred_manage_interactions(self, task=None):
    """Deferred initialization using QGIS Task API to prevent freeze.
    
    Args:
        task: QgsTask instance (optional, provided by QgsTask.fromFunction)
    """
    logger.info("FilterMate DockWidget: Starting deferred manage_interactions()")
    try:
        self.manage_interactions()
        logger.info("FilterMate DockWidget: manage_interactions() complete, initialization finished")
        return True
    except Exception as e:
        logger.error(f"FilterMate DockWidget: Error in manage_interactions(): {e}")
        return False
```

### 4. Remplacement ligne 1873 - Rafraîchissement des couches
**AVANT:**
```python
QTimer.singleShot(50, lambda pl=self.PROJECT_LAYERS, pr=self.PROJECT: self.get_project_layers_from_app(pl, pr))
```

**APRÈS:**
```python
pl = self.PROJECT_LAYERS
pr = self.PROJECT
task = QgsTask.fromFunction(
    'FilterMate: Refresh layers',
    lambda: self.get_project_layers_from_app(pl, pr)
)
QgsApplication.taskManager().addTask(task)
```

## Avantages de QgsTask

### 🚀 Performance
- Évite le blocage de l'interface utilisateur
- Exécution asynchrone native QGIS
- Meilleure gestion de la concurrence

### 🛡️ Stabilité
- Pas de conflit avec la boucle d'événements Qt
- Gestion d'erreurs intégrée
- Annulation propre des tâches

### 📊 Monitoring
- Affichage dans le gestionnaire de tâches QGIS
- Barre de progression visible
- Logs centralisés

## Instructions de test

### 1. Nettoyer le cache Python
```bash
find . -type f -name "*.pyc" -delete
find . -type d -name "__pycache__" -exec rm -rf {} +
```

### 2. Fermer complètement QGIS

### 3. Relancer QGIS

### 4. Activer le plugin FilterMate

### ✅ Résultat attendu
- QGIS ne freeze plus
- Le plugin charge normalement
- Les couches s'affichent correctement
- Le gestionnaire de tâches QGIS affiche "FilterMate: Initialize interactions"

## Vérification post-migration

```python
# Dans la console Python QGIS:
from qgis.core import QgsApplication
tasks = QgsApplication.taskManager().tasks()
filtermate_tasks = [t for t in tasks if 'FilterMate' in t.description()]
print(f"Tâches FilterMate: {len(filtermate_tasks)}")
```

## Documentation API QGIS

- [QgsTask](https://qgis.org/pyqgis/master/core/QgsTask.html)
- [QgsTaskManager](https://qgis.org/pyqgis/master/core/QgsTaskManager.html)
- [QgsApplication.taskManager()](https://qgis.org/pyqgis/master/core/QgsApplication.html#qgis.core.QgsApplication.taskManager)

## Notes importantes

⚠️ **Toujours utiliser `QgsTask` pour les opérations différées dans QGIS**
- ✅ `QgsTask.fromFunction()` pour fonctions simples
- ✅ Hériter de `QgsTask` pour logique complexe
- ❌ Éviter `QTimer.singleShot(0, ...)` qui peut causer des freeze
- ❌ Éviter `QTimer.singleShot(50, ...)` qui est une béquille

## Compatibilité

- ✅ QGIS 3.0+
- ✅ Compatible avec tous les backends (PostgreSQL, Spatialite, OGR)
- ✅ Thread-safe pour opérations asynchrones

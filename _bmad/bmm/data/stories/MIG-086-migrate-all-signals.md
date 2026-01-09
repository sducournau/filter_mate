---
storyId: MIG-086
title: Migrate All Signal Connections
epic: 6.6 - Signal Management
phase: 6
sprint: 8
priority: P1
status: READY_FOR_DEV
effort: 1 day
assignee: null
dependsOn: [MIG-084, MIG-085]
blocks: [MIG-087]
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-086: Migrate All Signal Connections

## 📋 Story

**En tant que** développeur,  
**Je veux** migrer toutes les connexions de signaux vers SignalManager,  
**Afin que** tous les signaux soient gérés de manière centralisée.

---

## 🎯 Objectif

Audit de tous les signaux dans le codebase et migration vers le nouveau `SignalManager` (MIG-084). Marquer les connexions legacy comme deprecated.

---

## ✅ Critères d'Acceptation

### Audit

- [ ] Liste complète de tous les signaux dans le plugin
- [ ] Identification des connexions directes à migrer
- [ ] Identification des signaux legacy à deprecate

### Migration

- [ ] Nouveaux signaux utilisent `SignalManager.register()`
- [ ] Connexions dans controllers utilisent SignalManager
- [ ] Connexions dans dockwidget utilisent SignalManager

### Backward Compatibility

- [ ] Anciennes méthodes de connexion marquées `@deprecated`
- [ ] Warning log pour utilisation legacy
- [ ] Pas de breaking changes pour le code existant

### Tests

- [ ] Tests de régression pour tous les signaux
- [ ] Vérification des connexions via `get_signal_stats()`
- [ ] Couverture > 80%

---

## 📝 Spécifications Techniques

### 1. Audit des Signaux

#### Fichiers à Auditer

| Fichier                     | Signaux Estimés | Priorité |
| --------------------------- | --------------- | -------- |
| `filter_mate_dockwidget.py` | ~40             | 🔴 P0    |
| `filter_mate_app.py`        | ~15             | 🟠 P1    |
| `ui/controllers/*.py`       | ~10             | 🟠 P1    |
| `modules/tasks/*.py`        | ~5              | 🟡 P2    |

#### Pattern de Recherche

```python
# Signaux à identifier:
# - widget.signal.connect(handler)
# - QObject.signal.connect(handler)
# - layer.signalName.connect(handler)
```

### 2. Stratégie de Migration

#### Avant (Legacy)

```python
# Dans filter_mate_dockwidget.py
def _connect_signals(self):
    self.comboBox_layer.currentIndexChanged.connect(
        self.on_layer_changed
    )
    self.pushButton_apply.clicked.connect(
        self.on_apply_clicked
    )
```

#### Après (Via SignalManager)

```python
# Dans filter_mate_dockwidget.py
def _connect_signals(self):
    # Register all signals with SignalManager
    self._signal_manager.register(
        'layer_combo_changed',
        self.comboBox_layer.currentIndexChanged,
        self.on_layer_changed,
        self.comboBox_layer
    )
    self._signal_manager.register(
        'apply_button_clicked',
        self.pushButton_apply.clicked,
        self.on_apply_clicked,
        self.pushButton_apply
    )

    # Connect all at once
    self._signal_manager.connect_widgets_signals()
```

### 3. Décorateur Deprecated

```python
"""
Deprecated decorator for legacy signal connections.
"""

import warnings
import functools


def deprecated_signal_connection(new_method: str):
    """
    Mark a signal connection method as deprecated.

    Args:
        new_method: The new method to use instead
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            warnings.warn(
                f"{func.__name__} is deprecated. "
                f"Use {new_method} instead.",
                DeprecationWarning,
                stacklevel=2
            )
            return func(*args, **kwargs)
        return wrapper
    return decorator
```

### 4. Migration par Catégorie

#### 4.1 Widget Signals (Buttons, Combos, etc.)

```python
# Catégorie: UI Widget Signals
WIDGET_SIGNALS = [
    # Name, Widget Attribute, Signal, Handler
    ('layer_combo_changed', 'comboBox_layer', 'currentIndexChanged', 'on_layer_changed'),
    ('apply_clicked', 'pushButton_apply', 'clicked', 'on_apply_clicked'),
    ('clear_clicked', 'pushButton_clear', 'clicked', 'on_clear_clicked'),
    # ... etc
]

def _register_widget_signals(self):
    for name, widget_attr, signal_name, handler_name in WIDGET_SIGNALS:
        widget = getattr(self, widget_attr, None)
        handler = getattr(self, handler_name, None)
        if widget and handler:
            signal = getattr(widget, signal_name)
            self._signal_manager.register(name, signal, handler, widget)
```

#### 4.2 Layer Signals

```python
# Déléguer à LayerSignalHandler (MIG-085)
self._layer_signal_handler.connect_layer_signals(layer)
```

#### 4.3 Project Signals

```python
# Catégorie: QGIS Project Signals
PROJECT_SIGNALS = [
    ('project_read', QgsProject.instance().readProject, self._on_project_read),
    ('project_cleared', QgsProject.instance().cleared, self._on_project_cleared),
    ('layers_added', QgsProject.instance().layersAdded, self._on_layers_added),
]
```

### 5. Validation Post-Migration

```python
def validate_signal_migration(self):
    """Validate that all signals are properly migrated."""
    stats = self._signal_manager.get_signal_stats()

    expected_signals = 45  # Adjust based on audit
    actual_signals = stats['total_registered']

    if actual_signals < expected_signals:
        logger.warning(
            f"Signal migration incomplete: "
            f"{actual_signals}/{expected_signals} signals registered"
        )
        return False

    connected = stats['total_connected']
    if connected < actual_signals:
        logger.warning(
            f"Not all signals connected: "
            f"{connected}/{actual_signals}"
        )
        return False

    logger.info(f"Signal migration validated: {actual_signals} signals")
    return True
```

---

## 🔗 Dépendances

### Entrée

- MIG-084: SignalManager (infrastructure)
- MIG-085: LayerSignalHandler (layer signals)

### Sortie

- MIG-087: Final refactoring

---

## 📊 Métriques

| Métrique                     | Avant | Après          |
| ---------------------------- | ----- | -------------- |
| Connexions directes          | ~50   | 0 (deprecated) |
| Connexions via SignalManager | 0     | ~50            |
| Signaux trackés              | 0     | 100%           |

---

## 📝 Checklist d'Audit

### filter_mate_dockwidget.py

- [ ] Lister tous les `.connect(`
- [ ] Catégoriser par type (widget, layer, project)
- [ ] Migrer vers SignalManager
- [ ] Ajouter `@deprecated` aux anciennes méthodes

### filter_mate_app.py

- [ ] Lister tous les `.connect(`
- [ ] Migrer les signaux UI
- [ ] Migrer les signaux de tâches

### Controllers

- [ ] ExploringController signaux
- [ ] FilteringController signaux
- [ ] ExportingController signaux

---

## 🧪 Scénarios de Test

### Test 1: All Signals Registered

```python
def test_all_signals_registered():
    """Tous les signaux doivent être enregistrés."""
    dockwidget = FilterMateDockWidget()
    stats = dockwidget._signal_manager.get_signal_stats()

    assert stats['total_registered'] >= 40
```

### Test 2: All Signals Connected

```python
def test_all_signals_connected():
    """Tous les signaux enregistrés doivent être connectés."""
    dockwidget = FilterMateDockWidget()
    stats = dockwidget._signal_manager.get_signal_stats()

    assert stats['total_connected'] == stats['total_registered']
```

### Test 3: Legacy Connection Warns

```python
def test_legacy_connection_warns():
    """L'utilisation legacy doit émettre un warning."""
    with pytest.warns(DeprecationWarning):
        dockwidget._legacy_connect_signals()
```

---

## 📋 Checklist Développeur

- [ ] Auditer tous les fichiers pour les `.connect(`
- [ ] Créer la liste WIDGET_SIGNALS
- [ ] Migrer les connexions widget
- [ ] Migrer les connexions layer (via LayerSignalHandler)
- [ ] Migrer les connexions project
- [ ] Ajouter décorateurs `@deprecated`
- [ ] Créer tests de régression
- [ ] Valider avec `validate_signal_migration()`

---

_Story générée par 🏃 SM Agent (Bob) - 9 janvier 2026_

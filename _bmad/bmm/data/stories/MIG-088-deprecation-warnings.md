---
storyId: MIG-088
title: Add Deprecation Warnings
epic: 6.7 - Final Refactoring
phase: 6
sprint: 9
priority: P1
status: READY_FOR_DEV
effort: 0.5 day
assignee: null
dependsOn: [MIG-087]
blocks: [MIG-089]
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-088: Add Deprecation Warnings

## 📋 Story

**En tant que** développeur d'extension FilterMate,  
**Je veux** des warnings de deprecation clairs,  
**Afin de** préparer les utilisateurs aux changements de l'API.

---

## 🎯 Objectif

Ajouter des décorateurs `@deprecated` à toutes les méthodes façade du dockwidget et signaler les nouvelles locations.

---

## ✅ Critères d'Acceptation

### Code

- [ ] Décorateur `@deprecated` créé dans `utils/deprecation.py`
- [ ] Appliqué à toutes les méthodes façade
- [ ] Warning indique la version de suppression (v4.0)
- [ ] Warning indique la nouvelle location

### Méthodes à Deprecate

- [ ] `apply_filter()` → `FilteringController.apply_filter()`
- [ ] `clear_filter()` → `FilteringController.clear_filter()`
- [ ] `get_exploring_features()` → `ExploringController.get_features()`
- [ ] `export_data()` → `ExportingController.export()`
- [ ] `connect_widgets_signals()` → `SignalManager.connect_widgets_signals()`
- [ ] Et toutes les autres méthodes déléguées...

### Logging

- [ ] Warning émis au premier appel seulement
- [ ] Stack trace inclus pour localiser l'appelant
- [ ] Niveau WARNING dans les logs

### Tests

- [ ] Test que les warnings sont émis
- [ ] Test que les fonctions continuent de marcher
- [ ] Test de suppression de warning après premier appel

---

## 📝 Spécifications Techniques

### Décorateur @deprecated

```python
"""
Deprecation utilities for FilterMate.

Provides decorators and utilities for marking deprecated code.
"""

import functools
import warnings
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def deprecated(
    version: str,
    reason: str,
    replacement: Optional[str] = None
) -> Callable:
    """
    Mark a function or method as deprecated.

    Emits a DeprecationWarning on first call and logs it.
    Subsequent calls do not emit warnings.

    Args:
        version: Version when the function will be removed
        reason: Why it's deprecated
        replacement: What to use instead

    Usage:
        @deprecated(version="4.0", reason="Moved to controller",
                   replacement="FilteringController.apply_filter()")
        def apply_filter(self, expression):
            return self._filtering_controller.apply_filter(expression)
    """
    def decorator(func: Callable) -> Callable:
        # Track if warning has been issued
        _warned = [False]

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not _warned[0]:
                # Build warning message
                msg = f"{func.__qualname__} is deprecated"
                if reason:
                    msg += f": {reason}"
                msg += f". Will be removed in v{version}."
                if replacement:
                    msg += f" Use {replacement} instead."

                # Emit warning
                warnings.warn(msg, DeprecationWarning, stacklevel=2)

                # Log it
                logger.warning(msg)

                _warned[0] = True

            return func(*args, **kwargs)

        # Add metadata for introspection
        wrapper._deprecated_version = version
        wrapper._deprecated_reason = reason
        wrapper._deprecated_replacement = replacement
        wrapper._is_deprecated = True

        return wrapper
    return decorator


def deprecated_property(
    version: str,
    reason: str,
    replacement: Optional[str] = None
) -> Callable:
    """
    Mark a property as deprecated.

    Similar to @deprecated but works with @property decorator.
    """
    def decorator(func: Callable) -> Callable:
        _warned = [False]

        @functools.wraps(func)
        def wrapper(self):
            if not _warned[0]:
                msg = f"{func.__qualname__} property is deprecated"
                if reason:
                    msg += f": {reason}"
                msg += f". Will be removed in v{version}."
                if replacement:
                    msg += f" Use {replacement} instead."

                warnings.warn(msg, DeprecationWarning, stacklevel=2)
                logger.warning(msg)
                _warned[0] = True

            return func(self)

        return property(wrapper)
    return decorator


def deprecated_class(
    version: str,
    reason: str,
    replacement: Optional[str] = None
) -> Callable:
    """
    Mark a class as deprecated.

    Emits warning when the class is instantiated.
    """
    def decorator(cls):
        original_init = cls.__init__

        @functools.wraps(original_init)
        def new_init(self, *args, **kwargs):
            msg = f"{cls.__name__} class is deprecated"
            if reason:
                msg += f": {reason}"
            msg += f". Will be removed in v{version}."
            if replacement:
                msg += f" Use {replacement} instead."

            warnings.warn(msg, DeprecationWarning, stacklevel=2)
            logger.warning(msg)

            original_init(self, *args, **kwargs)

        cls.__init__ = new_init
        cls._deprecated_version = version
        cls._is_deprecated = True

        return cls
    return decorator
```

### Application aux Façades

```python
# Dans filter_mate_dockwidget.py

from utils.deprecation import deprecated

class FilterMateDockWidget(QDockWidget):

    # =========================================================================
    # Deprecated Façades (Backward Compatibility)
    # =========================================================================

    @deprecated(
        version="4.0",
        reason="Moved to controller",
        replacement="FilteringController.apply_filter()"
    )
    def apply_filter(self, expression: str):
        """Apply a filter expression to the current layer."""
        return self._filtering_controller.apply_filter(expression)

    @deprecated(
        version="4.0",
        reason="Moved to controller",
        replacement="FilteringController.clear_filter()"
    )
    def clear_filter(self):
        """Clear the current filter."""
        return self._filtering_controller.clear_filter()

    @deprecated(
        version="4.0",
        reason="Moved to controller",
        replacement="ExploringController.get_features()"
    )
    def get_exploring_features(self, *args, **kwargs):
        """Get features for exploring."""
        return self._exploring_controller.get_features(*args, **kwargs)

    @deprecated(
        version="4.0",
        reason="Moved to controller",
        replacement="ExportingController.export()"
    )
    def export_data(self, *args, **kwargs):
        """Export data."""
        return self._exporting_controller.export(*args, **kwargs)

    @deprecated(
        version="4.0",
        reason="Moved to SignalManager",
        replacement="SignalManager.connect_widgets_signals()"
    )
    def connect_widgets_signals(self):
        """Connect widget signals."""
        return self._signal_manager.connect_widgets_signals()

    @deprecated(
        version="4.0",
        reason="Moved to SignalManager",
        replacement="SignalManager.disconnect_widgets_signals()"
    )
    def disconnect_widgets_signals(self):
        """Disconnect widget signals."""
        return self._signal_manager.disconnect_widgets_signals()
```

### Liste des Méthodes à Deprecate

| Ancienne Méthode                     | Nouvelle Location                            |
| ------------------------------------ | -------------------------------------------- |
| `apply_filter()`                     | `FilteringController.apply_filter()`         |
| `clear_filter()`                     | `FilteringController.clear_filter()`         |
| `get_exploring_features()`           | `ExploringController.get_features()`         |
| `export_data()`                      | `ExportingController.export()`               |
| `connect_widgets_signals()`          | `SignalManager.connect_widgets_signals()`    |
| `disconnect_widgets_signals()`       | `SignalManager.disconnect_widgets_signals()` |
| `apply_stylesheet()`                 | `ThemeManager.apply_stylesheet()`            |
| `set_widget_icon()`                  | `IconManager.set_widget_icon()`              |
| `apply_dynamic_dimensions()`         | `DimensionsManager.apply()`                  |
| `dockwidget_widgets_configuration()` | `ConfigController.configure_widgets()`       |

---

## 🔗 Dépendances

### Entrée

- MIG-087: Simplified DockWidget

### Sortie

- MIG-089: Regression Testing

---

## 📊 Métriques

| Métrique                        | Avant | Après |
| ------------------------------- | ----- | ----- |
| Méthodes documentées deprecated | 0     | ~20   |
| Warnings pour migration         | Non   | Oui   |

---

## 🧪 Scénarios de Test

### Test 1: Warning Emitted on First Call

```python
def test_deprecated_warning_emitted():
    """Le premier appel doit émettre un warning."""
    dockwidget = FilterMateDockWidget(...)

    with pytest.warns(DeprecationWarning, match="apply_filter"):
        dockwidget.apply_filter("id = 1")
```

### Test 2: Function Still Works

```python
def test_deprecated_function_works():
    """La fonction deprecated doit toujours fonctionner."""
    dockwidget = FilterMateDockWidget(...)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = dockwidget.apply_filter("id = 1")

    assert result is True  # Or whatever the expected result
```

### Test 3: Warning Only Once

```python
def test_warning_only_once():
    """Le warning ne doit être émis qu'une fois."""
    dockwidget = FilterMateDockWidget(...)

    # First call - warning
    with pytest.warns(DeprecationWarning):
        dockwidget.apply_filter("id = 1")

    # Second call - no warning
    with warnings.catch_warnings(record=True) as w:
        dockwidget.apply_filter("id = 2")
        assert len(w) == 0
```

---

## 📋 Checklist Développeur

- [ ] Créer `utils/deprecation.py`
- [ ] Implémenter décorateurs `@deprecated`, `@deprecated_property`
- [ ] Identifier toutes les méthodes façade
- [ ] Appliquer les décorateurs
- [ ] Créer tests pour les warnings
- [ ] Documenter dans CHANGELOG.md

---

_Story générée par 🏃 SM Agent (Bob) - 9 janvier 2026_

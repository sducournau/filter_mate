---
storyId: MIG-070
title: Create ConfigController
epic: 6.3 - New Controllers
phase: 6
sprint: 7
priority: P1
status: DONE
effort: 1 day
assignee: Dev Agent
dependsOn: [MIG-020, MIG-021, MIG-022, MIG-060, MIG-065]
blocks: [MIG-087]
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-070: Create ConfigController

## 📋 Story

**En tant que** développeur,  
**Je veux** créer un controller pour la configuration,  
**Afin que** l'onglet Settings soit géré proprement avec une responsabilité unique.

---

## 🎯 Objectif

Extraire les 16 méthodes de gestion de configuration de `filter_mate_dockwidget.py` (lignes 5074-5777) vers un controller dédié.

---

## ✅ Critères d'Acceptation

### Code

- [ ] `ui/controllers/config_controller.py` créé (< 400 lignes)
- [ ] Hérite de `ControllerBase` (si existant) ou pattern cohérent
- [ ] Type hints sur toutes les signatures
- [ ] Docstrings Google style

### Méthodes Extraites

- [ ] `dockwidget_widgets_configuration()`
- [ ] `data_changed_configuration_model()`
- [ ] `_apply_theme_change()`
- [ ] `_apply_ui_profile_change()`
- [ ] `_apply_action_bar_position_change()`
- [ ] `_apply_export_style_change()`
- [ ] `_apply_export_format_change()`
- [ ] `apply_pending_config_changes()`
- [ ] `cancel_pending_config_changes()`
- [ ] `_save_configuration()`
- [ ] `_load_configuration()`
- [ ] `_reset_to_defaults()`
- [ ] `_validate_config_values()`
- [ ] `_emit_config_changed()`
- [ ] `get_current_config()`
- [ ] `set_config_value()`

### Intégration

- [ ] Enregistré dans `ControllerRegistry` (si existant)
- [ ] Délégation depuis dockwidget fonctionne
- [ ] Signaux Qt correctement gérés

### Tests

- [ ] `tests/unit/ui/controllers/test_config_controller.py` créé
- [ ] Tests pour apply/cancel config changes
- [ ] Tests pour validation des valeurs
- [ ] Couverture > 80%

---

## 📝 Spécifications Techniques

### Structure du Controller

```python
"""
Configuration Controller for FilterMate.

Manages the Settings tab and configuration operations.
Extracted from filter_mate_dockwidget.py (lines 5074-5777).
"""

from typing import TYPE_CHECKING, Any, Dict, Optional
import logging

from qgis.PyQt.QtCore import QObject, pyqtSignal

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class ConfigController(QObject):
    """
    Controller for configuration management.

    Handles:
    - Theme changes (dark/light mode)
    - UI profile changes
    - Action bar position
    - Export settings
    - Configuration persistence

    Signals:
        config_changed: Emitted when any configuration value changes
        theme_changed: Emitted when theme changes
    """

    config_changed = pyqtSignal(str, object)  # key, value
    theme_changed = pyqtSignal(str)  # theme name

    def __init__(self, dockwidget: 'FilterMateDockWidget') -> None:
        """Initialize the config controller."""
        super().__init__()
        self.dockwidget = dockwidget
        self._pending_changes: Dict[str, Any] = {}
        self._initialized = False

    def setup(self) -> None:
        """Initialize configuration widgets and load saved config."""
        pass

    def apply_pending_config_changes(self) -> bool:
        """
        Apply all pending configuration changes.

        Returns:
            True if all changes applied successfully
        """
        pass

    def cancel_pending_config_changes(self) -> None:
        """Discard all pending changes and restore current values."""
        pass
```

### Délégation depuis DockWidget

```python
# Dans filter_mate_dockwidget.py

from ui.controllers.config_controller import ConfigController

class FilterMateDockWidget(QDockWidget):
    def __init__(self, ...):
        ...
        self._config_controller = ConfigController(self)

    # Façade pour rétrocompatibilité
    def apply_pending_config_changes(self):
        """@deprecated Use ConfigController.apply_pending_config_changes()"""
        return self._config_controller.apply_pending_config_changes()
```

---

## 🔗 Dépendances

### Entrée

- MIG-020, MIG-021, MIG-022: Controllers existants (pattern à suivre)
- MIG-060: Layout module (pour UI profile)
- MIG-065: Styling module (pour theme)

### Sortie

- MIG-087: Final refactoring (dépend de ce controller)

---

## 📊 Métriques

| Métrique                 | Avant | Après          |
| ------------------------ | ----- | -------------- |
| Lignes dans dockwidget   | ~700  | 0              |
| Méthodes dans dockwidget | 16    | 0 (façades)    |
| Nouveau fichier          | -     | < 400 lignes   |
| Tests                    | 0     | > 80% coverage |

---

## 🧪 Scénarios de Test

### Test 1: Apply Theme Change

```python
def test_apply_theme_change():
    """Le changement de thème doit être appliqué."""
    controller = ConfigController(mock_dockwidget)
    controller._pending_changes['theme'] = 'dark'

    result = controller.apply_pending_config_changes()

    assert result is True
    assert controller._pending_changes == {}
```

### Test 2: Cancel Pending Changes

```python
def test_cancel_pending_changes():
    """Les changements non appliqués doivent être annulés."""
    controller = ConfigController(mock_dockwidget)
    controller._pending_changes['theme'] = 'dark'

    controller.cancel_pending_config_changes()

    assert controller._pending_changes == {}
```

---

## 📋 Checklist Développeur

- [ ] Créer le fichier `ui/controllers/config_controller.py`
- [ ] Implémenter `ConfigController` avec toutes les méthodes
- [ ] Ajouter export dans `ui/controllers/__init__.py`
- [ ] Créer délégation dans dockwidget
- [ ] Marquer anciennes méthodes `@deprecated`
- [ ] Créer fichier de test
- [ ] Exécuter tests et vérifier couverture
- [ ] Mettre à jour architecture.md si nécessaire

---

_Story générée par 🏃 SM Agent (Bob) - 9 janvier 2026_

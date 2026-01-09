---
storyId: MIG-066
title: ThemeManager Extraction
epic: 6.2 - Styling Managers Extraction
phase: 6
sprint: 6
priority: P1
status: DONE
effort: 0.5 day
assignee: null
dependsOn: [MIG-065]
blocks: [MIG-070]
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-066: ThemeManager Extraction

## 📋 Story

**En tant que** développeur,  
**Je veux** centraliser la gestion des thèmes dans un manager dédié,  
**Afin que** le dark/light mode soit géré à un seul endroit et réduire le God Class.

---

## 🎯 Objectif

Extraire les méthodes de gestion des thèmes de `filter_mate_dockwidget.py` (lignes 6154-6444) vers `ui/styling/theme_manager.py`:

| Méthode                    | Lignes    | Responsabilité                 |
| -------------------------- | --------- | ------------------------------ |
| `_apply_stylesheet()`      | 6154-6245 | Application des stylesheets    |
| `manage_ui_style()`        | 6247-6340 | Gestion globale du style UI    |
| `_setup_theme_watcher()`   | 6342-6390 | Configuration du watcher thème |
| `_on_qgis_theme_changed()` | 6392-6444 | Callback changement de thème   |

**Réduction estimée:** ~290 lignes

---

## ✅ Critères d'Acceptation

### Extraction

- [ ] `ThemeManager` implémente les 4 méthodes
- [ ] Hérite de `StylerBase`
- [ ] Fichier < 300 lignes

### Thèmes Supportés

- [ ] Dark mode QGIS
- [ ] Light mode QGIS
- [ ] Thèmes personnalisés (Night Mapping, etc.)
- [ ] Détection automatique du thème

### Intégration

- [ ] Intégration avec `QGISThemeWatcher` existant
- [ ] Utilise `modules/ui_styles.py` pour les stylesheets
- [ ] Émet signals lors des changements

### Configuration

- [ ] Utilise `UIConfig` pour les préférences
- [ ] Option "follow QGIS theme" vs thème forcé
- [ ] Persistance des préférences

### Tests

- [ ] Tests unitaires pour `ThemeManager`
- [ ] Tests dark mode
- [ ] Tests light mode
- [ ] Tests changement dynamique

---

## 🏗️ Fichier Cible

### `ui/styling/theme_manager.py`

```python
"""
Theme Manager for FilterMate.

Manages dark/light mode, QGIS theme integration, and stylesheet application.
Extracted from filter_mate_dockwidget.py (lines 6154-6444).

Story: MIG-066
Phase: 6 - God Class DockWidget Migration
"""

from typing import TYPE_CHECKING, Optional, Callable
import logging

from qgis.PyQt.QtCore import QObject, pyqtSignal

from .base_styler import StylerBase

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget
    from config.config import UIConfig

logger = logging.getLogger(__name__)


class ThemeManager(StylerBase, QObject):
    """
    Manages UI theming for FilterMate dockwidget.

    Handles:
    - Dark/Light mode detection and application
    - QGIS theme integration
    - Dynamic theme switching
    - Stylesheet management

    Signals:
        theme_changed: Emitted when theme changes (theme_name: str)

    Attributes:
        dockwidget: Reference to the parent dockwidget
        config: UI configuration
        _theme_watcher: QGISThemeWatcher instance
        _current_theme: Current theme name
    """

    theme_changed = pyqtSignal(str)

    def __init__(
        self,
        dockwidget: "FilterMateDockWidget",
        config: Optional["UIConfig"] = None
    ) -> None:
        """
        Initialize ThemeManager.

        Args:
            dockwidget: Parent FilterMateDockWidget instance
            config: Optional UI configuration
        """
        StylerBase.__init__(self, dockwidget, config)
        QObject.__init__(self)

        self._theme_watcher = None
        self._current_theme: str = "default"
        self._theme_callbacks: list[Callable] = []

    def apply(self) -> None:
        """
        Apply current theme to all widgets.

        Main entry point for theme application.
        """
        self.manage_ui_style()

    def setup(self) -> None:
        """
        Initial setup of theme management.

        Called during dockwidget initialization.
        """
        self._setup_theme_watcher()
        self.manage_ui_style()

    def manage_ui_style(self) -> None:
        """
        Manage UI style based on current theme.

        Determines current theme and applies appropriate stylesheet.
        """
        # TODO: Extract from lines 6247-6340
        raise NotImplementedError("Pending extraction from dockwidget")

    def _apply_stylesheet(self, stylesheet: str = None) -> None:
        """
        Apply stylesheet to dockwidget.

        Args:
            stylesheet: CSS stylesheet string. If None, generates from theme.
        """
        # TODO: Extract from lines 6154-6245
        raise NotImplementedError("Pending extraction from dockwidget")

    def _setup_theme_watcher(self) -> None:
        """
        Setup QGIS theme change watcher.

        Creates QGISThemeWatcher and connects to theme change signal.
        """
        # TODO: Extract from lines 6342-6390
        raise NotImplementedError("Pending extraction from dockwidget")

    def _on_qgis_theme_changed(self, theme_name: str) -> None:
        """
        Handle QGIS theme change event.

        Called when QGIS theme changes. Updates FilterMate theme
        if configured to follow QGIS theme.

        Args:
            theme_name: Name of new QGIS theme
        """
        # TODO: Extract from lines 6392-6444
        logger.info(f"QGIS theme changed to: {theme_name}")
        self._current_theme = theme_name
        self.theme_changed.emit(theme_name)

        if self.config.get("follow_qgis_theme", True):
            self.manage_ui_style()

    def register_theme_callback(self, callback: Callable[[str], None]) -> None:
        """
        Register callback for theme changes.

        Args:
            callback: Function to call when theme changes.
                     Receives theme name as argument.
        """
        self._theme_callbacks.append(callback)
        self.theme_changed.connect(callback)

    def unregister_theme_callback(self, callback: Callable) -> None:
        """
        Unregister theme change callback.

        Args:
            callback: Previously registered callback
        """
        if callback in self._theme_callbacks:
            self._theme_callbacks.remove(callback)
            try:
                self.theme_changed.disconnect(callback)
            except TypeError:
                pass  # Already disconnected

    def get_current_theme(self) -> str:
        """
        Get current theme name.

        Returns:
            Current theme name
        """
        return self._current_theme

    def set_theme(self, theme_name: str) -> None:
        """
        Force a specific theme.

        Args:
            theme_name: Theme to apply ("dark", "light", or QGIS theme name)
        """
        logger.info(f"Setting theme to: {theme_name}")
        self._current_theme = theme_name
        self.manage_ui_style()
        self.theme_changed.emit(theme_name)

    def cleanup(self) -> None:
        """
        Cleanup theme manager resources.

        Disconnects theme watcher and clears callbacks.
        """
        if self._theme_watcher:
            try:
                self._theme_watcher.theme_changed.disconnect(
                    self._on_qgis_theme_changed
                )
            except TypeError:
                pass
            self._theme_watcher = None

        self._theme_callbacks.clear()
```

---

## 🧪 Tests Requis

### `tests/unit/ui/styling/test_theme_manager.py`

```python
"""Unit tests for ThemeManager."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from ui.styling.theme_manager import ThemeManager


class TestThemeManager:
    """Test suite for ThemeManager."""

    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget."""
        dockwidget = Mock()
        dockwidget.widget = Mock()
        dockwidget.setStyleSheet = Mock()
        return dockwidget

    @pytest.fixture
    def config(self):
        """Default configuration."""
        return {
            "follow_qgis_theme": True,
            "theme": "auto"
        }

    @pytest.fixture
    def manager(self, mock_dockwidget, config):
        """Create ThemeManager instance."""
        return ThemeManager(mock_dockwidget, config)

    def test_init(self, manager):
        """Test manager initialization."""
        assert manager._current_theme == "default"
        assert manager._theme_watcher is None
        assert manager._theme_callbacks == []

    def test_get_current_theme(self, manager):
        """Test getting current theme."""
        assert manager.get_current_theme() == "default"

    def test_set_theme_updates_current(self, manager):
        """Test set_theme updates current_theme."""
        manager.manage_ui_style = Mock()
        manager.set_theme("dark")
        assert manager._current_theme == "dark"

    def test_set_theme_calls_manage_ui_style(self, manager):
        """Test set_theme calls manage_ui_style."""
        manager.manage_ui_style = Mock()
        manager.set_theme("light")
        manager.manage_ui_style.assert_called_once()

    def test_set_theme_emits_signal(self, manager):
        """Test set_theme emits theme_changed signal."""
        manager.manage_ui_style = Mock()

        callback = Mock()
        manager.theme_changed.connect(callback)

        manager.set_theme("dark")
        callback.assert_called_once_with("dark")

    def test_register_theme_callback(self, manager):
        """Test registering theme callback."""
        callback = Mock()
        manager.register_theme_callback(callback)

        assert callback in manager._theme_callbacks

    def test_unregister_theme_callback(self, manager):
        """Test unregistering theme callback."""
        callback = Mock()
        manager.register_theme_callback(callback)
        manager.unregister_theme_callback(callback)

        assert callback not in manager._theme_callbacks

    def test_on_qgis_theme_changed_updates_theme(self, manager):
        """Test QGIS theme change handler."""
        manager.manage_ui_style = Mock()

        manager._on_qgis_theme_changed("Night Mapping")

        assert manager._current_theme == "Night Mapping"

    def test_on_qgis_theme_changed_respects_follow_setting(self, manager):
        """Test QGIS theme change respects follow_qgis_theme setting."""
        manager.manage_ui_style = Mock()
        manager.config["follow_qgis_theme"] = False

        manager._on_qgis_theme_changed("Night Mapping")

        manager.manage_ui_style.assert_not_called()

    def test_cleanup(self, manager):
        """Test cleanup clears resources."""
        callback = Mock()
        manager.register_theme_callback(callback)

        manager.cleanup()

        assert manager._theme_callbacks == []
        assert manager._theme_watcher is None


class TestThemeManagerIntegration:
    """Integration tests for ThemeManager."""

    def test_apply_calls_manage_ui_style(self):
        """Test apply() calls manage_ui_style()."""
        manager = ThemeManager(Mock(), {})
        manager.manage_ui_style = Mock()

        manager.apply()

        manager.manage_ui_style.assert_called_once()
```

---

## 📋 Checklist de Complétion

### Avant Développement

- [ ] MIG-065 (Styling Module Structure) complété
- [ ] Revue du code source lignes 6154-6444
- [ ] `QGISThemeWatcher` analysé

### Développement

- [ ] Fichier `theme_manager.py` créé
- [ ] 4 méthodes extraites et adaptées
- [ ] Signal `theme_changed` implémenté
- [ ] Intégration avec `ui_styles.py`
- [ ] Type hints complets

### Post-Développement

- [ ] Tests unitaires passent
- [ ] Tests de régression passent
- [ ] Review de code approuvée

---

## 🔗 Références

- **Epic:** [epics.md](../epics.md#epic-62-styling-managers-extraction)
- **Code Source:** `filter_mate_dockwidget.py` lignes 6154-6444
- **Existant:** `modules/ui_styles.py`, `QGISThemeWatcher`
- **Dépendance:** MIG-065 (Styling Module Structure)
- **Bloque:** MIG-070 (ConfigController)

---

_Story créée par 🧙 BMad Master - 9 janvier 2026_

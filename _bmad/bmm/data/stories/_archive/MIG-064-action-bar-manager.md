---
storyId: MIG-064
title: ActionBarManager Extraction
epic: 6.1 - Layout Managers Extraction
phase: 6
sprint: 6
priority: P1
status: READY_FOR_DEV
effort: 1.5 days
assignee: null
dependsOn: [MIG-060]
blocks: [MIG-070]
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-064: ActionBarManager Extraction

## 📋 Story

**En tant que** développeur,  
**Je veux** extraire la gestion de l'action bar dans un manager dédié,  
**Afin d'** isoler la logique complexe de positionnement et réduire le God Class.

---

## 🎯 Objectif

Extraire les 14 méthodes de gestion de l'action bar de `filter_mate_dockwidget.py` (lignes 4039-4604) vers `ui/layout/action_bar_manager.py`:

| Méthode                                            | Lignes    | Responsabilité                       |
| -------------------------------------------------- | --------- | ------------------------------------ |
| `_setup_action_bar_layout()`                       | 4039-4095 | Configuration initiale action bar    |
| `_get_action_bar_position()`                       | 4097-4120 | Récupère position config             |
| `_get_action_bar_vertical_alignment()`             | 4122-4145 | Récupère alignement vertical         |
| `_apply_action_bar_position()`                     | 4147-4215 | Applique position à l'UI             |
| `_adjust_header_for_side_position()`               | 4217-4265 | Ajuste header pour position latérale |
| `_restore_header_from_wrapper()`                   | 4267-4305 | Restaure header depuis wrapper       |
| `_clear_action_bar_layout()`                       | 4307-4335 | Nettoie layout action bar            |
| `_create_horizontal_action_layout()`               | 4337-4390 | Crée layout horizontal               |
| `_create_vertical_action_layout()`                 | 4392-4445 | Crée layout vertical                 |
| `_apply_action_bar_size_constraints()`             | 4447-4495 | Contraintes de taille                |
| `_reposition_action_bar_in_main_layout()`          | 4497-4540 | Repositionne dans layout principal   |
| `_create_horizontal_wrapper_for_side_action_bar()` | 4542-4575 | Wrapper horizontal pour sidebar      |
| `_restore_side_action_bar_layout()`                | 4577-4590 | Restaure layout latéral              |
| `_restore_original_layout()`                       | 4592-4604 | Restaure layout original             |

**Réduction estimée:** ~565 lignes

---

## ✅ Critères d'Acceptation

### Extraction

- [ ] `ActionBarManager` implémente les 14 méthodes
- [ ] Hérite de `LayoutManagerBase`
- [ ] Fichier < 600 lignes

### Positions Supportées

- [ ] Position `top` (défaut)
- [ ] Position `bottom`
- [ ] Position `left`
- [ ] Position `right`
- [ ] Transitions fluides entre positions

### Alignement Vertical (pour positions latérales)

- [ ] Alignement `top`
- [ ] Alignement `center`
- [ ] Alignement `bottom`

### Configuration

- [ ] Utilise `UIConfig` pour position et alignement
- [ ] Réagit aux changements de configuration
- [ ] Sauvegarde/restauration état

### Délégation

- [ ] `filter_mate_dockwidget.py` délègue à `ActionBarManager`
- [ ] Méthodes originales marquées `@deprecated`
- [ ] Comportement identique (tests de non-régression)

### Tests

- [ ] Tests unitaires pour toutes les positions
- [ ] Tests de transition entre positions
- [ ] Tests d'alignement vertical
- [ ] Aucune régression sur tests existants

---

## 🏗️ Fichier Cible

### `ui/layout/action_bar_manager.py`

```python
"""
Action Bar Manager for FilterMate.

Manages action bar positioning, layout, and size constraints.
Extracted from filter_mate_dockwidget.py (lines 4039-4604).

Story: MIG-064
Phase: 6 - God Class DockWidget Migration
"""

from typing import TYPE_CHECKING, Optional, Literal
from enum import Enum
import logging

from qgis.PyQt.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFrame, QSizePolicy
)
from qgis.PyQt.QtCore import Qt

from .base_manager import LayoutManagerBase

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget
    from config.config import UIConfig

logger = logging.getLogger(__name__)


class ActionBarPosition(Enum):
    """Action bar position options."""
    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"


class ActionBarAlignment(Enum):
    """Vertical alignment for side positions."""
    TOP = "top"
    CENTER = "center"
    BOTTOM = "bottom"


class ActionBarManager(LayoutManagerBase):
    """
    Manages action bar positioning and layout.

    The action bar contains the main action buttons (filter, explore, export).
    It can be positioned at top, bottom, left, or right of the main content.
    For side positions (left/right), vertical alignment can be configured.

    Attributes:
        dockwidget: Reference to the parent dockwidget
        config: UI configuration with action bar settings
        current_position: Current action bar position
        current_alignment: Current vertical alignment (for side positions)
    """

    def __init__(
        self,
        dockwidget: "FilterMateDockWidget",
        config: Optional["UIConfig"] = None
    ) -> None:
        """
        Initialize ActionBarManager.

        Args:
            dockwidget: Parent FilterMateDockWidget instance
            config: Optional UI configuration. If None, uses defaults.
        """
        super().__init__(dockwidget, config)
        self.current_position: ActionBarPosition = ActionBarPosition.TOP
        self.current_alignment: ActionBarAlignment = ActionBarAlignment.CENTER
        self._original_layout_state: Optional[dict] = None

    def setup(self) -> None:
        """
        Initial setup of action bar layout.

        Called during dockwidget initialization.
        """
        self._setup_action_bar_layout()

    def apply_position(
        self,
        position: Optional[ActionBarPosition] = None,
        alignment: Optional[ActionBarAlignment] = None
    ) -> None:
        """
        Apply action bar position and alignment.

        Args:
            position: Target position. If None, reads from config.
            alignment: Vertical alignment. If None, reads from config.
        """
        if position is None:
            position = self._get_action_bar_position()
        if alignment is None:
            alignment = self._get_action_bar_vertical_alignment()

        logger.info(f"Applying action bar position: {position.value}, alignment: {alignment.value}")

        self._apply_action_bar_position(position, alignment)
        self.current_position = position
        self.current_alignment = alignment

    def _setup_action_bar_layout(self) -> None:
        """
        Setup initial action bar layout structure.

        Creates the base layout and applies default position.
        """
        # TODO: Extract from lines 4039-4095
        raise NotImplementedError("Pending extraction from dockwidget")

    def _get_action_bar_position(self) -> ActionBarPosition:
        """
        Get action bar position from configuration.

        Returns:
            ActionBarPosition enum value
        """
        # TODO: Extract from lines 4097-4120
        position_str = self.config.get("action_bar_position", "top")
        return ActionBarPosition(position_str)

    def _get_action_bar_vertical_alignment(self) -> ActionBarAlignment:
        """
        Get vertical alignment from configuration.

        Returns:
            ActionBarAlignment enum value
        """
        # TODO: Extract from lines 4122-4145
        alignment_str = self.config.get("action_bar_vertical_alignment", "center")
        return ActionBarAlignment(alignment_str)

    def _apply_action_bar_position(
        self,
        position: ActionBarPosition,
        alignment: ActionBarAlignment
    ) -> None:
        """
        Apply action bar position to the UI.

        Args:
            position: Target position
            alignment: Vertical alignment for side positions
        """
        # TODO: Extract from lines 4147-4215
        raise NotImplementedError("Pending extraction from dockwidget")

    def _adjust_header_for_side_position(self) -> None:
        """
        Adjust header layout when action bar is on side.

        Wraps header in horizontal layout to accommodate side action bar.
        """
        # TODO: Extract from lines 4217-4265
        raise NotImplementedError("Pending extraction from dockwidget")

    def _restore_header_from_wrapper(self) -> None:
        """
        Restore header from horizontal wrapper.

        Called when transitioning from side to top/bottom position.
        """
        # TODO: Extract from lines 4267-4305
        raise NotImplementedError("Pending extraction from dockwidget")

    def _clear_action_bar_layout(self) -> None:
        """
        Clear existing action bar layout.

        Removes all widgets from action bar before repositioning.
        """
        # TODO: Extract from lines 4307-4335
        raise NotImplementedError("Pending extraction from dockwidget")

    def _create_horizontal_action_layout(self) -> QHBoxLayout:
        """
        Create horizontal layout for action buttons.

        Returns:
            QHBoxLayout configured for action buttons
        """
        # TODO: Extract from lines 4337-4390
        raise NotImplementedError("Pending extraction from dockwidget")

    def _create_vertical_action_layout(self) -> QVBoxLayout:
        """
        Create vertical layout for action buttons.

        Returns:
            QVBoxLayout configured for action buttons
        """
        # TODO: Extract from lines 4392-4445
        raise NotImplementedError("Pending extraction from dockwidget")

    def _apply_action_bar_size_constraints(self) -> None:
        """
        Apply size constraints to action bar.

        Sets min/max sizes based on current position.
        """
        # TODO: Extract from lines 4447-4495
        raise NotImplementedError("Pending extraction from dockwidget")

    def _reposition_action_bar_in_main_layout(
        self,
        position: ActionBarPosition
    ) -> None:
        """
        Reposition action bar in main layout.

        Args:
            position: Target position in main layout
        """
        # TODO: Extract from lines 4497-4540
        raise NotImplementedError("Pending extraction from dockwidget")

    def _create_horizontal_wrapper_for_side_action_bar(self) -> QWidget:
        """
        Create horizontal wrapper for side action bar.

        Returns:
            QWidget wrapper containing action bar and content
        """
        # TODO: Extract from lines 4542-4575
        raise NotImplementedError("Pending extraction from dockwidget")

    def _restore_side_action_bar_layout(self) -> None:
        """
        Restore layout when removing side action bar.
        """
        # TODO: Extract from lines 4577-4590
        raise NotImplementedError("Pending extraction from dockwidget")

    def _restore_original_layout(self) -> None:
        """
        Restore original layout state.

        Called during cleanup or when resetting to defaults.
        """
        # TODO: Extract from lines 4592-4604
        raise NotImplementedError("Pending extraction from dockwidget")

    def is_horizontal(self) -> bool:
        """
        Check if action bar is in horizontal position.

        Returns:
            True if top or bottom, False if left or right
        """
        return self.current_position in (
            ActionBarPosition.TOP,
            ActionBarPosition.BOTTOM
        )

    def is_vertical(self) -> bool:
        """
        Check if action bar is in vertical position.

        Returns:
            True if left or right, False if top or bottom
        """
        return not self.is_horizontal()
```

---

## 🧪 Tests Requis

### `tests/unit/ui/layout/test_action_bar_manager.py`

```python
"""Unit tests for ActionBarManager."""

import pytest
from unittest.mock import Mock, MagicMock

from ui.layout.action_bar_manager import (
    ActionBarManager,
    ActionBarPosition,
    ActionBarAlignment
)


class TestActionBarPosition:
    """Test ActionBarPosition enum."""

    def test_all_positions_defined(self):
        """Verify all positions are defined."""
        assert ActionBarPosition.TOP.value == "top"
        assert ActionBarPosition.BOTTOM.value == "bottom"
        assert ActionBarPosition.LEFT.value == "left"
        assert ActionBarPosition.RIGHT.value == "right"


class TestActionBarAlignment:
    """Test ActionBarAlignment enum."""

    def test_all_alignments_defined(self):
        """Verify all alignments are defined."""
        assert ActionBarAlignment.TOP.value == "top"
        assert ActionBarAlignment.CENTER.value == "center"
        assert ActionBarAlignment.BOTTOM.value == "bottom"


class TestActionBarManager:
    """Test suite for ActionBarManager."""

    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget."""
        dockwidget = Mock()
        dockwidget.action_bar_frame = Mock()
        dockwidget.main_layout = Mock()
        dockwidget.header_frame = Mock()
        return dockwidget

    @pytest.fixture
    def config_default(self):
        """Default configuration."""
        return {
            "action_bar_position": "top",
            "action_bar_vertical_alignment": "center"
        }

    @pytest.fixture
    def config_left(self):
        """Left position configuration."""
        return {
            "action_bar_position": "left",
            "action_bar_vertical_alignment": "top"
        }

    @pytest.fixture
    def manager(self, mock_dockwidget, config_default):
        """Create ActionBarManager instance."""
        return ActionBarManager(mock_dockwidget, config_default)

    def test_init_default_position(self, manager):
        """Test default position is TOP."""
        assert manager.current_position == ActionBarPosition.TOP

    def test_init_default_alignment(self, manager):
        """Test default alignment is CENTER."""
        assert manager.current_alignment == ActionBarAlignment.CENTER

    def test_get_action_bar_position_from_config(self, manager):
        """Test reading position from config."""
        position = manager._get_action_bar_position()
        assert position == ActionBarPosition.TOP

    def test_get_action_bar_position_left(self, mock_dockwidget, config_left):
        """Test reading left position from config."""
        manager = ActionBarManager(mock_dockwidget, config_left)
        position = manager._get_action_bar_position()
        assert position == ActionBarPosition.LEFT

    def test_is_horizontal_top(self, manager):
        """Test is_horizontal for TOP position."""
        manager.current_position = ActionBarPosition.TOP
        assert manager.is_horizontal() is True

    def test_is_horizontal_bottom(self, manager):
        """Test is_horizontal for BOTTOM position."""
        manager.current_position = ActionBarPosition.BOTTOM
        assert manager.is_horizontal() is True

    def test_is_horizontal_left(self, manager):
        """Test is_horizontal for LEFT position."""
        manager.current_position = ActionBarPosition.LEFT
        assert manager.is_horizontal() is False

    def test_is_vertical_left(self, manager):
        """Test is_vertical for LEFT position."""
        manager.current_position = ActionBarPosition.LEFT
        assert manager.is_vertical() is True

    def test_is_vertical_right(self, manager):
        """Test is_vertical for RIGHT position."""
        manager.current_position = ActionBarPosition.RIGHT
        assert manager.is_vertical() is True


class TestActionBarManagerPositionTransitions:
    """Test position transition scenarios."""

    @pytest.fixture
    def manager(self):
        """Create manager with mocked methods."""
        dockwidget = Mock()
        manager = ActionBarManager(dockwidget, {})
        manager._apply_action_bar_position = Mock()
        return manager

    def test_apply_position_updates_current(self, manager):
        """Test that apply_position updates current_position."""
        manager.apply_position(
            ActionBarPosition.BOTTOM,
            ActionBarAlignment.CENTER
        )
        assert manager.current_position == ActionBarPosition.BOTTOM

    def test_apply_position_calls_internal(self, manager):
        """Test that apply_position calls _apply_action_bar_position."""
        manager.apply_position(
            ActionBarPosition.LEFT,
            ActionBarAlignment.TOP
        )
        manager._apply_action_bar_position.assert_called_once_with(
            ActionBarPosition.LEFT,
            ActionBarAlignment.TOP
        )
```

---

## 📋 Checklist de Complétion

### Avant Développement

- [ ] MIG-060 (Layout Module Structure) complété
- [ ] Revue du code source lignes 4039-4604
- [ ] Analyse des 4 positions et leurs comportements

### Développement

- [ ] Fichier `action_bar_manager.py` créé
- [ ] Enums `ActionBarPosition` et `ActionBarAlignment` définis
- [ ] 14 méthodes extraites et adaptées
- [ ] Délégation depuis dockwidget
- [ ] Type hints complets

### Post-Développement

- [ ] Tests unitaires pour toutes les positions passent
- [ ] Tests de transition entre positions passent
- [ ] Tests de régression passent
- [ ] Review de code approuvée

---

## ⚠️ Points d'Attention

1. **Complexité des transitions**: Le passage d'une position à l'autre nécessite un cleanup propre
2. **Wrapper horizontal**: La position left/right nécessite un wrapper spécial pour le header
3. **État original**: Sauvegarder l'état pour pouvoir restaurer

---

## 🔗 Références

- **Epic:** [epics.md](../epics.md#epic-61-layout-managers-extraction)
- **Code Source:** `filter_mate_dockwidget.py` lignes 4039-4604
- **Dépendance:** MIG-060 (Layout Module Structure)
- **Bloque:** MIG-070 (ConfigController)

---

_Story créée par 🧙 BMad Master - 9 janvier 2026_

---
storyId: MIG-063
title: SpacingManager Extraction
epic: 6.1 - Layout Managers Extraction
phase: 6
sprint: 6
priority: P1
status: READY_FOR_DEV
effort: 0.5 day
assignee: null
dependsOn: [MIG-060]
blocks: [MIG-070]
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-063: SpacingManager Extraction

## 📋 Story

**En tant que** développeur,  
**Je veux** centraliser la gestion des espacements dans un manager dédié,  
**Afin d'** avoir un spacing cohérent et réduire le God Class.

---

## 🎯 Objectif

Extraire les méthodes de gestion des espacements de `filter_mate_dockwidget.py` (lignes 1153-1334, 1546-1612) vers `ui/layout/spacing_manager.py`:

| Méthode                   | Lignes    | Responsabilité                 |
| ------------------------- | --------- | ------------------------------ |
| `_apply_layout_spacing()` | 1153-1250 | Espacements des layouts        |
| `_harmonize_spacers()`    | 1252-1300 | Harmonisation des spacers      |
| `_adjust_row_spacing()`   | 1302-1334 | Ajustement espacement des rows |
| `_apply_margins()`        | 1546-1580 | Marges des conteneurs          |
| `_configure_separators()` | 1582-1612 | Configuration des séparateurs  |

**Réduction estimée:** ~180 lignes

---

## ✅ Critères d'Acceptation

### Extraction

- [ ] `SpacingManager` implémente les 5 méthodes
- [ ] Hérite de `LayoutManagerBase`
- [ ] Fichier < 200 lignes

### Configuration

- [ ] Utilise `UIConfig` pour les valeurs de spacing
- [ ] Supporte les profiles UI (compact: spacing réduit)
- [ ] Constantes de spacing centralisées

### Délégation

- [ ] `filter_mate_dockwidget.py` délègue à `SpacingManager`
- [ ] Méthodes originales marquées `@deprecated`
- [ ] Comportement identique (tests de non-régression)

### Tests

- [ ] Tests unitaires pour `SpacingManager`
- [ ] Tests avec différents profiles
- [ ] Aucune régression sur tests existants

---

## 🏗️ Fichier Cible

### `ui/layout/spacing_manager.py`

```python
"""
Spacing Manager for FilterMate.

Centralizes layout spacing, margins, and separator configuration.
Extracted from filter_mate_dockwidget.py (lines 1153-1334, 1546-1612).

Story: MIG-063
Phase: 6 - God Class DockWidget Migration
"""

from typing import TYPE_CHECKING, Optional, Dict
import logging

from qgis.PyQt.QtWidgets import QLayout, QWidget, QFrame

from .base_manager import LayoutManagerBase

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget
    from config.config import UIConfig

logger = logging.getLogger(__name__)


class SpacingConstants:
    """Spacing constants for different UI profiles."""

    COMPACT = {
        "layout_spacing": 2,
        "content_margins": (2, 2, 2, 2),
        "row_spacing": 2,
        "separator_margin": 1,
    }

    NORMAL = {
        "layout_spacing": 4,
        "content_margins": (4, 4, 4, 4),
        "row_spacing": 4,
        "separator_margin": 2,
    }

    EXTENDED = {
        "layout_spacing": 6,
        "content_margins": (6, 6, 6, 6),
        "row_spacing": 6,
        "separator_margin": 4,
    }


class SpacingManager(LayoutManagerBase):
    """
    Manages spacing, margins, and separators across the dockwidget.

    Provides consistent spacing values based on the current UI profile
    and applies them to layouts, widgets, and separators.

    Attributes:
        dockwidget: Reference to the parent dockwidget
        config: UI configuration with spacing settings
        constants: Current spacing constants based on profile
    """

    def __init__(
        self,
        dockwidget: "FilterMateDockWidget",
        config: Optional["UIConfig"] = None
    ) -> None:
        """
        Initialize SpacingManager.

        Args:
            dockwidget: Parent FilterMateDockWidget instance
            config: Optional UI configuration. If None, uses defaults.
        """
        super().__init__(dockwidget, config)
        self._update_constants()

    def _update_constants(self) -> None:
        """Update spacing constants based on current profile."""
        profile = self.config.get("ui_profile", "normal")

        if profile == "compact":
            self.constants = SpacingConstants.COMPACT
        elif profile == "extended":
            self.constants = SpacingConstants.EXTENDED
        else:
            self.constants = SpacingConstants.NORMAL

    def apply_all_spacing(self) -> None:
        """
        Apply all spacing configurations.

        Main entry point for spacing management.
        """
        logger.debug("Applying all spacing configurations")

        self._update_constants()
        self._apply_layout_spacing()
        self._harmonize_spacers()
        self._adjust_row_spacing()
        self._apply_margins()
        self._configure_separators()

        logger.info("Spacing applied successfully")

    def _apply_layout_spacing(self) -> None:
        """
        Apply spacing to all layouts.

        Iterates through all layouts and sets consistent spacing.
        """
        # TODO: Extract from lines 1153-1250
        raise NotImplementedError("Pending extraction from dockwidget")

    def _harmonize_spacers(self) -> None:
        """
        Harmonize spacer items across layouts.

        Ensures consistent spacer behavior for visual balance.
        """
        # TODO: Extract from lines 1252-1300
        raise NotImplementedError("Pending extraction from dockwidget")

    def _adjust_row_spacing(self) -> None:
        """
        Adjust spacing between rows in form layouts.

        Applies row-specific spacing for form-like layouts.
        """
        # TODO: Extract from lines 1302-1334
        raise NotImplementedError("Pending extraction from dockwidget")

    def _apply_margins(self) -> None:
        """
        Apply content margins to container widgets.

        Sets left, top, right, bottom margins on layouts.
        """
        # TODO: Extract from lines 1546-1580
        raise NotImplementedError("Pending extraction from dockwidget")

    def _configure_separators(self) -> None:
        """
        Configure visual separator widgets.

        Applies styling and margins to QFrame separators.
        """
        # TODO: Extract from lines 1582-1612
        raise NotImplementedError("Pending extraction from dockwidget")

    def get_spacing(self, key: str) -> int:
        """
        Get spacing value by key.

        Args:
            key: Spacing key (layout_spacing, row_spacing, etc.)

        Returns:
            Spacing value in pixels
        """
        return self.constants.get(key, 4)

    def get_margins(self) -> tuple:
        """
        Get content margins tuple.

        Returns:
            Tuple of (left, top, right, bottom) margins
        """
        return self.constants.get("content_margins", (4, 4, 4, 4))
```

---

## 🧪 Tests Requis

### `tests/unit/ui/layout/test_spacing_manager.py`

```python
"""Unit tests for SpacingManager."""

import pytest
from unittest.mock import Mock

from ui.layout.spacing_manager import SpacingManager, SpacingConstants


class TestSpacingConstants:
    """Test SpacingConstants values."""

    def test_compact_spacing_smaller_than_normal(self):
        """Verify compact profile has smaller spacing."""
        assert SpacingConstants.COMPACT["layout_spacing"] < SpacingConstants.NORMAL["layout_spacing"]

    def test_extended_spacing_larger_than_normal(self):
        """Verify extended profile has larger spacing."""
        assert SpacingConstants.EXTENDED["layout_spacing"] > SpacingConstants.NORMAL["layout_spacing"]


class TestSpacingManager:
    """Test suite for SpacingManager."""

    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget."""
        return Mock()

    @pytest.fixture
    def config_normal(self):
        """Normal profile configuration."""
        return {"ui_profile": "normal"}

    @pytest.fixture
    def config_compact(self):
        """Compact profile configuration."""
        return {"ui_profile": "compact"}

    @pytest.fixture
    def manager(self, mock_dockwidget, config_normal):
        """Create SpacingManager with normal profile."""
        return SpacingManager(mock_dockwidget, config_normal)

    def test_init_with_normal_profile(self, manager):
        """Test initialization with normal profile."""
        assert manager.constants == SpacingConstants.NORMAL

    def test_init_with_compact_profile(self, mock_dockwidget, config_compact):
        """Test initialization with compact profile."""
        manager = SpacingManager(mock_dockwidget, config_compact)
        assert manager.constants == SpacingConstants.COMPACT

    def test_get_spacing(self, manager):
        """Test getting spacing value."""
        assert manager.get_spacing("layout_spacing") == 4

    def test_get_margins(self, manager):
        """Test getting margins tuple."""
        assert manager.get_margins() == (4, 4, 4, 4)

    def test_apply_all_spacing_calls_all_methods(self, manager):
        """Test that apply_all_spacing calls all sub-methods."""
        manager._apply_layout_spacing = Mock()
        manager._harmonize_spacers = Mock()
        manager._adjust_row_spacing = Mock()
        manager._apply_margins = Mock()
        manager._configure_separators = Mock()

        manager.apply_all_spacing()

        manager._apply_layout_spacing.assert_called_once()
        manager._harmonize_spacers.assert_called_once()
        manager._adjust_row_spacing.assert_called_once()
        manager._apply_margins.assert_called_once()
        manager._configure_separators.assert_called_once()
```

---

## 📋 Checklist de Complétion

### Avant Développement

- [ ] MIG-060 (Layout Module Structure) complété
- [ ] Revue du code source lignes 1153-1334, 1546-1612
- [ ] Tests existants identifiés

### Développement

- [ ] Fichier `spacing_manager.py` créé
- [ ] 5 méthodes extraites et adaptées
- [ ] SpacingConstants définis
- [ ] Délégation depuis dockwidget
- [ ] Type hints complets

### Post-Développement

- [ ] Tests unitaires passent
- [ ] Tests de régression passent
- [ ] Review de code approuvée

---

## 🔗 Références

- **Epic:** [epics.md](../epics.md#epic-61-layout-managers-extraction)
- **Code Source:** `filter_mate_dockwidget.py` lignes 1153-1334, 1546-1612
- **Dépendance:** MIG-060 (Layout Module Structure)
- **Bloque:** MIG-070 (ConfigController)

---

_Story créée par 🧙 BMad Master - 9 janvier 2026_

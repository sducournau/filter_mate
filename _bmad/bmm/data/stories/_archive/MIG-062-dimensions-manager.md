---
storyId: MIG-062
title: DimensionsManager Extraction
epic: 6.1 - Layout Managers Extraction
phase: 6
sprint: 6
priority: P1
status: READY_FOR_DEV
effort: 1 day
assignee: null
dependsOn: [MIG-060]
blocks: [MIG-070]
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-062: DimensionsManager Extraction

## 📋 Story

**En tant que** développeur,  
**Je veux** centraliser la gestion des dimensions dans un manager dédié,  
**Afin d'** avoir un point unique pour le sizing des widgets et réduire le God Class.

---

## 🎯 Objectif

Extraire les méthodes de gestion des dimensions de `filter_mate_dockwidget.py` (lignes 848-1041, 1334-1403) vers `ui/layout/dimensions_manager.py`:

| Méthode                           | Lignes    | Responsabilité                        |
| --------------------------------- | --------- | ------------------------------------- |
| `apply_dynamic_dimensions()`      | 848-892   | Point d'entrée pour toutes dimensions |
| `_apply_dockwidget_dimensions()`  | 894-940   | Dimensions du dockwidget principal    |
| `_apply_widget_dimensions()`      | 942-1010  | Dimensions génériques des widgets     |
| `_apply_frame_dimensions()`       | 1012-1041 | Dimensions des frames                 |
| `_apply_qgis_widget_dimensions()` | 1334-1403 | Dimensions spécifiques widgets QGIS   |

**Réduction estimée:** ~260 lignes

---

## ✅ Critères d'Acceptation

### Extraction

- [ ] `DimensionsManager` implémente les 5 méthodes
- [ ] Hérite de `LayoutManagerBase`
- [ ] Fichier < 400 lignes

### Configuration

- [ ] Utilise `UIConfig` pour les valeurs par défaut
- [ ] Supporte les profiles UI (compact/normal/extended)
- [ ] Dimensions responsive selon taille fenêtre

### Délégation

- [ ] `filter_mate_dockwidget.py` délègue à `DimensionsManager`
- [ ] Méthodes originales marquées `@deprecated`
- [ ] Comportement identique (tests de non-régression)

### Tests

- [ ] Tests unitaires pour `DimensionsManager`
- [ ] Tests des différents profiles
- [ ] Tests avec différentes tailles de fenêtre
- [ ] Aucune régression sur tests existants

---

## 🏗️ Fichier Cible

### `ui/layout/dimensions_manager.py`

```python
"""
Dimensions Manager for FilterMate.

Centralizes widget sizing logic for dockwidget, frames, and QGIS widgets.
Extracted from filter_mate_dockwidget.py (lines 848-1041, 1334-1403).

Story: MIG-062
Phase: 6 - God Class DockWidget Migration
"""

from typing import TYPE_CHECKING, Optional, Dict, Any
import logging

from qgis.PyQt.QtWidgets import QWidget, QFrame
from qgis.PyQt.QtCore import QSize

from .base_manager import LayoutManagerBase

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget
    from config.config import UIConfig

logger = logging.getLogger(__name__)


class DimensionsManager(LayoutManagerBase):
    """
    Manages widget dimensions across the dockwidget.

    Handles sizing for:
    - Dockwidget itself (min/max constraints)
    - Child frames and widgets
    - QGIS-specific widgets (layer tree, field combo)
    - Profile-based dimension adjustments

    Attributes:
        dockwidget: Reference to the parent dockwidget
        config: UI configuration with dimension settings
    """

    def __init__(
        self,
        dockwidget: "FilterMateDockWidget",
        config: Optional["UIConfig"] = None
    ) -> None:
        """
        Initialize DimensionsManager.

        Args:
            dockwidget: Parent FilterMateDockWidget instance
            config: Optional UI configuration. If None, uses defaults.
        """
        super().__init__(dockwidget, config)
        self._dimension_cache: Dict[str, QSize] = {}

    def apply_dynamic_dimensions(self) -> None:
        """
        Apply all dynamic dimensions based on current configuration.

        Main entry point for dimension management. Applies dimensions
        to dockwidget, frames, and widgets in correct order.

        Note:
            Called during initialization and when profile changes.
        """
        logger.debug("Applying dynamic dimensions")

        self._apply_dockwidget_dimensions()
        self._apply_frame_dimensions()
        self._apply_widget_dimensions()
        self._apply_qgis_widget_dimensions()

        logger.info("Dynamic dimensions applied successfully")

    def _apply_dockwidget_dimensions(self) -> None:
        """
        Apply min/max dimensions to the dockwidget.

        Uses configuration values for min width, max width,
        and height constraints based on current profile.
        """
        # TODO: Extract from lines 894-940
        raise NotImplementedError("Pending extraction from dockwidget")

    def _apply_widget_dimensions(self) -> None:
        """
        Apply dimensions to generic child widgets.

        Iterates through child widgets and applies appropriate
        sizing based on widget type and current profile.
        """
        # TODO: Extract from lines 942-1010
        raise NotImplementedError("Pending extraction from dockwidget")

    def _apply_frame_dimensions(self) -> None:
        """
        Apply dimensions to frame widgets.

        Handles exploring frame, toolset frame, and action bar frame
        dimension constraints.
        """
        # TODO: Extract from lines 1012-1041
        raise NotImplementedError("Pending extraction from dockwidget")

    def _apply_qgis_widget_dimensions(self) -> None:
        """
        Apply dimensions to QGIS-specific widgets.

        Handles special sizing for:
        - QgsMapLayerComboBox
        - QgsFieldComboBox
        - QgsExpression widgets
        """
        # TODO: Extract from lines 1334-1403
        raise NotImplementedError("Pending extraction from dockwidget")

    def get_dimension_for_profile(
        self,
        widget_type: str,
        dimension: str
    ) -> int:
        """
        Get dimension value for widget type based on current profile.

        Args:
            widget_type: Type of widget (dockwidget, frame, button, etc.)
            dimension: Dimension name (min_width, max_height, etc.)

        Returns:
            Dimension value in pixels
        """
        profile = self.config.get("ui_profile", "normal")
        return self.config.get(f"{profile}.{widget_type}.{dimension}", 0)
```

---

## 📝 Implémentation

### Étape 1: Extraction du Code Source

Copier les lignes 848-1041 et 1334-1403 de `filter_mate_dockwidget.py`:

```python
# Lignes à extraire pour chaque méthode
# apply_dynamic_dimensions: 848-892
# _apply_dockwidget_dimensions: 894-940
# _apply_widget_dimensions: 942-1010
# _apply_frame_dimensions: 1012-1041
# _apply_qgis_widget_dimensions: 1334-1403
```

### Étape 2: Adapter les Références

- Remplacer `self.widget` par `self.dockwidget.widget`
- Remplacer accès directs aux widgets par getters
- Utiliser `self.config` au lieu de `self.fm_config`

### Étape 3: Créer Délégation

Dans `filter_mate_dockwidget.py`:

```python
# Ancien code (marquer @deprecated)
@deprecated(version="3.1", reason="Use DimensionsManager.apply_dynamic_dimensions()")
def apply_dynamic_dimensions(self) -> None:
    self._dimensions_manager.apply_dynamic_dimensions()
```

---

## 🧪 Tests Requis

### `tests/unit/ui/layout/test_dimensions_manager.py`

```python
"""Unit tests for DimensionsManager."""

import pytest
from unittest.mock import Mock, MagicMock, patch

from ui.layout.dimensions_manager import DimensionsManager


class TestDimensionsManager:
    """Test suite for DimensionsManager."""

    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget with required attributes."""
        dockwidget = Mock()
        dockwidget.widget = Mock()
        dockwidget.exploring_frame = Mock()
        dockwidget.toolset_frame = Mock()
        return dockwidget

    @pytest.fixture
    def mock_config(self):
        """Create mock UI configuration."""
        return {
            "ui_profile": "normal",
            "normal.dockwidget.min_width": 300,
            "normal.dockwidget.max_width": 600,
            "compact.dockwidget.min_width": 250,
            "compact.dockwidget.max_width": 400,
        }

    @pytest.fixture
    def manager(self, mock_dockwidget, mock_config):
        """Create DimensionsManager instance."""
        return DimensionsManager(mock_dockwidget, mock_config)

    def test_init(self, manager, mock_dockwidget):
        """Test manager initialization."""
        assert manager.dockwidget == mock_dockwidget
        assert manager._dimension_cache == {}

    def test_apply_dynamic_dimensions_calls_all_methods(self, manager):
        """Test that apply_dynamic_dimensions calls all sub-methods."""
        manager._apply_dockwidget_dimensions = Mock()
        manager._apply_frame_dimensions = Mock()
        manager._apply_widget_dimensions = Mock()
        manager._apply_qgis_widget_dimensions = Mock()

        manager.apply_dynamic_dimensions()

        manager._apply_dockwidget_dimensions.assert_called_once()
        manager._apply_frame_dimensions.assert_called_once()
        manager._apply_widget_dimensions.assert_called_once()
        manager._apply_qgis_widget_dimensions.assert_called_once()

    def test_get_dimension_for_profile_normal(self, manager):
        """Test dimension retrieval for normal profile."""
        result = manager.get_dimension_for_profile("dockwidget", "min_width")
        assert result == 300

    def test_get_dimension_for_profile_compact(self, manager, mock_config):
        """Test dimension retrieval for compact profile."""
        mock_config["ui_profile"] = "compact"
        manager = DimensionsManager(Mock(), mock_config)

        result = manager.get_dimension_for_profile("dockwidget", "min_width")
        assert result == 250


class TestDimensionsManagerIntegration:
    """Integration tests with mock dockwidget."""

    def test_dimensions_applied_correctly(self):
        """Test that dimensions are applied to widgets correctly."""
        # TODO: Implement after extraction
        pass

    def test_profile_change_updates_dimensions(self):
        """Test that changing profile updates all dimensions."""
        # TODO: Implement after extraction
        pass
```

---

## 📋 Checklist de Complétion

### Avant Développement

- [ ] MIG-060 (Layout Module Structure) complété
- [ ] Revue du code source lignes 848-1041, 1334-1403
- [ ] Tests existants identifiés

### Développement

- [ ] Fichier `dimensions_manager.py` créé
- [ ] 5 méthodes extraites et adaptées
- [ ] Délégation depuis dockwidget
- [ ] Type hints complets
- [ ] Docstrings Google style

### Post-Développement

- [ ] Tests unitaires passent
- [ ] Tests de régression passent
- [ ] Review de code approuvée
- [ ] Documentation mise à jour

---

## 🔗 Références

- **Epic:** [epics.md](../epics.md#epic-61-layout-managers-extraction)
- **Architecture:** [architecture-v3.md](../../../../docs/architecture-v3.md)
- **Code Source:** `filter_mate_dockwidget.py` lignes 848-1041, 1334-1403
- **Dépendance:** MIG-060 (Layout Module Structure)
- **Bloque:** MIG-070 (ConfigController)

---

_Story créée par 🧙 BMad Master - 9 janvier 2026_

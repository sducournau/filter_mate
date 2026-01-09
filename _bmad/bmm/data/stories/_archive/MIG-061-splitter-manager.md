---
storyId: MIG-061
title: SplitterManager Extraction
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

# MIG-061: SplitterManager Extraction

## 📋 Story

**En tant que** développeur,  
**Je veux** extraire la gestion des splitters dans un manager dédié,  
**Afin d'** isoler la logique de redimensionnement des panneaux et réduire le God Class.

---

## 🎯 Objectif

Extraire 3 méthodes de `filter_mate_dockwidget.py` (lignes 693-848) vers `ui/layout/splitter_manager.py`:

| Méthode                            | Lignes  | Responsabilité                     |
| ---------------------------------- | ------- | ---------------------------------- |
| `_setup_main_splitter()`           | 693-771 | Configuration initiale du splitter |
| `_apply_splitter_frame_policies()` | 773-811 | Politiques de taille des frames    |
| `_set_initial_splitter_sizes()`    | 813-840 | Distribution initiale des tailles  |

**Réduction estimée:** ~150 lignes

---

## ✅ Critères d'Acceptation

### Extraction

- [ ] `SplitterManager` implémente les 3 méthodes
- [ ] Hérite de `LayoutManagerBase`
- [ ] Fichier < 200 lignes

### Délégation

- [ ] `filter_mate_dockwidget.py` délègue à `SplitterManager`
- [ ] Méthodes originales marquées `@deprecated`
- [ ] Comportement identique (tests de non-régression)

### Configuration

- [ ] Utilise `UIConfig` pour la configuration
- [ ] Supporte les profiles compact/normal
- [ ] Styling du handle splitter externalisé

### Tests

- [ ] Tests unitaires pour `SplitterManager`
- [ ] Tests d'intégration avec dockwidget mock
- [ ] Aucune régression sur tests existants

---

## 🏗️ Fichier Cible

### `ui/layout/splitter_manager.py`

```python
"""
Splitter Manager for FilterMate.

Handles main splitter configuration between exploring and toolset frames.
Extracted from filter_mate_dockwidget.py (lines 693-848).

Story: MIG-061
Phase: 6 - God Class DockWidget Migration
"""

from typing import TYPE_CHECKING, Optional, Dict, Any
import logging

from qgis.PyQt.QtWidgets import QSplitter, QSizePolicy, QFrame

from .base_manager import LayoutManagerBase

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class SplitterManager(LayoutManagerBase):
    """
    Manages the main splitter between exploring and toolset frames.

    The splitter divides the dockwidget vertically:
    - Top: frame_exploring (layer info, values)
    - Bottom: frame_toolset (tabs: filtering, exporting, config)

    Configuration is loaded from UIConfig and supports:
    - Handle width and margins
    - Stretch factors for proportional sizing
    - Collapsible behavior
    - Size policies for child frames
    - Initial size distribution

    Attributes:
        _splitter: Reference to the QSplitter widget
        _config: Splitter configuration from UIConfig
    """

    # Policy string to Qt enum mapping
    POLICY_MAP: Dict[str, QSizePolicy.Policy] = {
        'Fixed': QSizePolicy.Fixed,
        'Minimum': QSizePolicy.Minimum,
        'Maximum': QSizePolicy.Maximum,
        'Preferred': QSizePolicy.Preferred,
        'Expanding': QSizePolicy.Expanding,
        'MinimumExpanding': QSizePolicy.MinimumExpanding,
        'Ignored': QSizePolicy.Ignored
    }

    def __init__(self, dockwidget: 'FilterMateDockWidget') -> None:
        """
        Initialize the SplitterManager.

        Args:
            dockwidget: The main FilterMate dockwidget instance
        """
        super().__init__(dockwidget)
        self._splitter: Optional[QSplitter] = None
        self._config: Dict[str, Any] = {}

    def setup(self) -> None:
        """
        Setup the main splitter with configuration from UIConfig.

        Configures:
        - Splitter properties (handle width, collapsible, etc.)
        - Frame size policies
        - Stretch factors
        - Initial size distribution
        - Handle styling
        """
        from modules.ui_config import UIConfig

        try:
            # Get splitter reference from dockwidget
            if not hasattr(self.dockwidget, 'splitter_main'):
                logger.warning("splitter_main not found in dockwidget")
                return

            self._splitter = self.dockwidget.splitter_main

            # Also set as main_splitter for backward compatibility
            self.dockwidget.main_splitter = self._splitter

            # Load configuration
            self._config = UIConfig.get_config('splitter') or {}

            # Apply splitter properties
            self._apply_splitter_properties()

            # Apply handle styling
            self._apply_handle_style()

            # Configure frame size policies
            self._apply_frame_policies()

            # Set stretch factors
            self._apply_stretch_factors()

            # Set initial sizes
            self._set_initial_sizes()

            self._initialized = True
            logger.debug(f"SplitterManager setup complete: {self._config}")

        except Exception as e:
            logger.error(f"Error setting up splitter: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self._splitter = None

    def apply(self) -> None:
        """
        Reapply splitter configuration.

        Called when configuration changes (e.g., profile switch).
        """
        if not self._splitter:
            logger.warning("Cannot apply - splitter not initialized")
            return

        from modules.ui_config import UIConfig
        self._config = UIConfig.get_config('splitter') or {}

        self._apply_splitter_properties()
        self._apply_handle_style()
        self._apply_frame_policies()
        self._apply_stretch_factors()

        logger.debug("SplitterManager configuration reapplied")

    def _apply_splitter_properties(self) -> None:
        """Apply basic splitter properties from config."""
        handle_width = self._config.get('handle_width', 6)
        collapsible = self._config.get('collapsible', False)
        opaque_resize = self._config.get('opaque_resize', True)

        self._splitter.setChildrenCollapsible(collapsible)
        self._splitter.setHandleWidth(handle_width)
        self._splitter.setOpaqueResize(opaque_resize)

    def _apply_handle_style(self) -> None:
        """Apply styling to the splitter handle."""
        handle_width = self._config.get('handle_width', 6)
        handle_margin = self._config.get('handle_margin', 40)

        # Subtle and minimal handle style
        self._splitter.setStyleSheet(f"""
            QSplitter::handle:vertical {{
                background-color: #d0d0d0;
                height: {handle_width - 2}px;
                margin: 2px {handle_margin}px;
                border-radius: {(handle_width - 2) // 2}px;
            }}
            QSplitter::handle:vertical:hover {{
                background-color: #3498db;
            }}
        """)

    def _apply_frame_policies(self) -> None:
        """
        Apply size policies to frames within the splitter.

        - frame_exploring: Minimum policy (can shrink to min but prefers base)
        - frame_toolset: Expanding policy (takes remaining space)
        """
        from modules.ui_config import UIConfig

        # Configure frame_exploring
        if hasattr(self.dockwidget, 'frame_exploring'):
            exploring_config = UIConfig.get_config('frame_exploring') or {}
            h_policy = self.POLICY_MAP.get(
                exploring_config.get('size_policy_h', 'Preferred'),
                QSizePolicy.Preferred
            )
            v_policy = self.POLICY_MAP.get(
                exploring_config.get('size_policy_v', 'Minimum'),
                QSizePolicy.Minimum
            )
            self.dockwidget.frame_exploring.setSizePolicy(h_policy, v_policy)
            logger.debug(f"frame_exploring policy: {exploring_config.get('size_policy_h')}/{exploring_config.get('size_policy_v')}")

        # Configure frame_toolset
        if hasattr(self.dockwidget, 'frame_toolset'):
            toolset_config = UIConfig.get_config('frame_toolset') or {}
            h_policy = self.POLICY_MAP.get(
                toolset_config.get('size_policy_h', 'Preferred'),
                QSizePolicy.Preferred
            )
            v_policy = self.POLICY_MAP.get(
                toolset_config.get('size_policy_v', 'Expanding'),
                QSizePolicy.Expanding
            )
            self.dockwidget.frame_toolset.setSizePolicy(h_policy, v_policy)
            logger.debug(f"frame_toolset policy: {toolset_config.get('size_policy_h')}/{toolset_config.get('size_policy_v')}")

    def _apply_stretch_factors(self) -> None:
        """Set stretch factors for proportional sizing."""
        exploring_stretch = self._config.get('exploring_stretch', 2)
        toolset_stretch = self._config.get('toolset_stretch', 5)

        self._splitter.setStretchFactor(0, exploring_stretch)
        self._splitter.setStretchFactor(1, toolset_stretch)

        logger.debug(f"Stretch factors: exploring={exploring_stretch}, toolset={toolset_stretch}")

    def _set_initial_sizes(self) -> None:
        """
        Set initial splitter sizes based on configuration ratios.

        Uses the available height to distribute space between frames
        according to the configured ratios (50/50 by default).
        """
        exploring_ratio = self._config.get('initial_exploring_ratio', 0.50)
        toolset_ratio = self._config.get('initial_toolset_ratio', 0.50)

        # Get available height from splitter or use default
        total_height = self._splitter.height()
        if total_height < 100:  # Splitter not yet sized
            total_height = 600

        # Calculate sizes based on ratios
        exploring_size = int(total_height * exploring_ratio)
        toolset_size = int(total_height * toolset_ratio)

        self._splitter.setSizes([exploring_size, toolset_size])

        logger.debug(
            f"Initial sizes: exploring={exploring_size}px ({exploring_ratio:.0%}), "
            f"toolset={toolset_size}px ({toolset_ratio:.0%})"
        )

    @property
    def splitter(self) -> Optional[QSplitter]:
        """Return the managed splitter widget."""
        return self._splitter

    def get_sizes(self) -> list:
        """Return current splitter sizes."""
        if self._splitter:
            return self._splitter.sizes()
        return []

    def set_sizes(self, sizes: list) -> None:
        """
        Set splitter sizes.

        Args:
            sizes: List of [exploring_size, toolset_size]
        """
        if self._splitter and len(sizes) == 2:
            self._splitter.setSizes(sizes)

    def teardown(self) -> None:
        """Clean up splitter resources."""
        super().teardown()
        self._splitter = None
        self._config = {}
```

---

## 🔗 Intégration dans DockWidget

### Modification de `filter_mate_dockwidget.py`

```python
# Dans __init__(), après création du dockwidget:
from ui.layout import SplitterManager

# Créer le manager
self._splitter_manager = SplitterManager(self)

# Dans setupUiCustom():
def setupUiCustom(self):
    self.set_multiple_checkable_combobox()

    # Déléguer au SplitterManager
    self._splitter_manager.setup()

    # Suite du setup...
    self.apply_dynamic_dimensions()
    self._fix_toolbox_icons()
    self._setup_backend_indicator()
    self._setup_action_bar_layout()

# Méthodes legacy avec dépréciation:
@deprecated(version="3.1", reason="Use SplitterManager.setup()")
def _setup_main_splitter(self):
    """DEPRECATED: Use self._splitter_manager.setup()"""
    self._splitter_manager.setup()

@deprecated(version="3.1", reason="Use SplitterManager._apply_frame_policies()")
def _apply_splitter_frame_policies(self):
    """DEPRECATED: Use self._splitter_manager._apply_frame_policies()"""
    self._splitter_manager._apply_frame_policies()

@deprecated(version="3.1", reason="Use SplitterManager._set_initial_sizes()")
def _set_initial_splitter_sizes(self):
    """DEPRECATED: Use self._splitter_manager._set_initial_sizes()"""
    self._splitter_manager._set_initial_sizes()
```

---

## 🧪 Tests Requis

### `tests/unit/ui/layout/test_splitter_manager.py`

```python
"""Tests for SplitterManager."""

import pytest
from unittest.mock import Mock, MagicMock, patch

from ui.layout.splitter_manager import SplitterManager


class TestSplitterManager:
    """Tests for SplitterManager class."""

    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget with required attributes."""
        dockwidget = Mock()
        dockwidget.splitter_main = Mock()
        dockwidget.frame_exploring = Mock()
        dockwidget.frame_toolset = Mock()
        return dockwidget

    @pytest.fixture
    def mock_ui_config(self):
        """Mock UIConfig.get_config()."""
        with patch('ui.layout.splitter_manager.UIConfig') as mock:
            mock.get_config.return_value = {
                'handle_width': 6,
                'handle_margin': 40,
                'exploring_stretch': 2,
                'toolset_stretch': 5,
                'collapsible': False,
                'opaque_resize': True,
                'initial_exploring_ratio': 0.50,
                'initial_toolset_ratio': 0.50,
            }
            yield mock

    def test_creation(self, mock_dockwidget):
        """Should create manager with dockwidget reference."""
        manager = SplitterManager(mock_dockwidget)
        assert manager.dockwidget is mock_dockwidget
        assert not manager.is_initialized
        assert manager.splitter is None

    def test_setup_initializes_splitter(self, mock_dockwidget, mock_ui_config):
        """Setup should initialize splitter from dockwidget."""
        manager = SplitterManager(mock_dockwidget)
        manager.setup()

        assert manager.is_initialized
        assert manager.splitter is mock_dockwidget.splitter_main
        assert mock_dockwidget.main_splitter is mock_dockwidget.splitter_main

    def test_setup_applies_properties(self, mock_dockwidget, mock_ui_config):
        """Setup should apply splitter properties from config."""
        manager = SplitterManager(mock_dockwidget)
        manager.setup()

        splitter = mock_dockwidget.splitter_main
        splitter.setChildrenCollapsible.assert_called_with(False)
        splitter.setHandleWidth.assert_called_with(6)
        splitter.setOpaqueResize.assert_called_with(True)

    def test_setup_applies_stretch_factors(self, mock_dockwidget, mock_ui_config):
        """Setup should apply stretch factors."""
        manager = SplitterManager(mock_dockwidget)
        manager.setup()

        splitter = mock_dockwidget.splitter_main
        splitter.setStretchFactor.assert_any_call(0, 2)
        splitter.setStretchFactor.assert_any_call(1, 5)

    def test_setup_applies_stylesheet(self, mock_dockwidget, mock_ui_config):
        """Setup should apply handle styling."""
        manager = SplitterManager(mock_dockwidget)
        manager.setup()

        splitter = mock_dockwidget.splitter_main
        splitter.setStyleSheet.assert_called_once()
        stylesheet = splitter.setStyleSheet.call_args[0][0]
        assert 'QSplitter::handle:vertical' in stylesheet

    def test_setup_handles_missing_splitter(self, mock_dockwidget, mock_ui_config):
        """Setup should handle missing splitter_main gracefully."""
        del mock_dockwidget.splitter_main

        manager = SplitterManager(mock_dockwidget)
        manager.setup()  # Should not raise

        assert not manager.is_initialized

    def test_apply_reloads_config(self, mock_dockwidget, mock_ui_config):
        """Apply should reload and reapply configuration."""
        manager = SplitterManager(mock_dockwidget)
        manager.setup()

        # Reset mock calls
        mock_dockwidget.splitter_main.reset_mock()

        manager.apply()

        # Should reapply properties
        mock_dockwidget.splitter_main.setChildrenCollapsible.assert_called()

    def test_get_sizes(self, mock_dockwidget, mock_ui_config):
        """get_sizes should return current splitter sizes."""
        mock_dockwidget.splitter_main.sizes.return_value = [200, 400]

        manager = SplitterManager(mock_dockwidget)
        manager.setup()

        assert manager.get_sizes() == [200, 400]

    def test_set_sizes(self, mock_dockwidget, mock_ui_config):
        """set_sizes should update splitter sizes."""
        manager = SplitterManager(mock_dockwidget)
        manager.setup()

        manager.set_sizes([150, 450])

        mock_dockwidget.splitter_main.setSizes.assert_called_with([150, 450])

    def test_teardown(self, mock_dockwidget, mock_ui_config):
        """Teardown should clean up resources."""
        manager = SplitterManager(mock_dockwidget)
        manager.setup()

        manager.teardown()

        assert not manager.is_initialized
        assert manager.splitter is None

    def test_policy_map_has_all_policies(self):
        """POLICY_MAP should contain all Qt size policies."""
        expected = ['Fixed', 'Minimum', 'Maximum', 'Preferred',
                   'Expanding', 'MinimumExpanding', 'Ignored']
        assert all(p in SplitterManager.POLICY_MAP for p in expected)
```

---

## 📋 Checklist Développeur

### Préparation

- [ ] MIG-060 complété (structure du module)
- [ ] Lire les méthodes source (lignes 693-848)
- [ ] Comprendre `UIConfig` et les profiles

### Implémentation

- [ ] Implémenter `SplitterManager` complet
- [ ] Ajouter export dans `ui/layout/__init__.py`
- [ ] Intégrer dans `filter_mate_dockwidget.py`
- [ ] Marquer méthodes legacy deprecated

### Validation

- [ ] `python3 -m py_compile ui/layout/splitter_manager.py`
- [ ] Tests unitaires passent
- [ ] Tests d'intégration passent
- [ ] Aucune régression

### Finalisation

- [ ] Commit: `feat(MIG-061): Extract SplitterManager from dockwidget`
- [ ] Mettre à jour kanban

---

## ⏱️ Estimation

| Activité                       | Durée   |
| ------------------------------ | ------- |
| Implémentation SplitterManager | 1h      |
| Intégration dockwidget         | 30 min  |
| Tests unitaires                | 45 min  |
| Tests intégration              | 30 min  |
| Validation                     | 15 min  |
| **Total**                      | **~3h** |

---

_Story créée par 🧙 BMad Master - 9 janvier 2026_

---
storyId: MIG-060
title: Layout Module Structure
epic: 6.1 - Layout Managers Extraction
phase: 6
sprint: 6
priority: P0
status: READY_FOR_DEV
effort: 0.5 day
assignee: null
dependsOn: [MIG-024]
blocks: [MIG-061, MIG-062, MIG-063, MIG-064]
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-060: Layout Module Structure

## 📋 Story

**En tant que** développeur,  
**Je veux** créer la structure du module `ui/layout/`,  
**Afin que** les layout managers aient un emplacement dédié et organisé.

---

## 🎯 Objectif

Créer le squelette du module `ui/layout/` qui contiendra les 4 managers de layout à extraire de `filter_mate_dockwidget.py`:

| Manager           | Story   | Lignes Source        | Responsabilité             |
| ----------------- | ------- | -------------------- | -------------------------- |
| SplitterManager   | MIG-061 | 693-848              | Gestion splitter principal |
| DimensionsManager | MIG-062 | 848-1041, 1334-1403  | Sizing des widgets         |
| SpacingManager    | MIG-063 | 1153-1334, 1546-1612 | Espacements et marges      |
| ActionBarManager  | MIG-064 | 4039-4604            | Positionnement action bar  |

---

## ✅ Critères d'Acceptation

### Structure Fichiers

- [ ] `ui/layout/__init__.py` créé avec exports
- [ ] `ui/layout/base_manager.py` créé avec classe abstraite `LayoutManagerBase`
- [ ] `ui/layout/splitter_manager.py` créé (squelette)
- [ ] `ui/layout/dimensions_manager.py` créé (squelette)
- [ ] `ui/layout/spacing_manager.py` créé (squelette)
- [ ] `ui/layout/action_bar_manager.py` créé (squelette)

### Code Quality

- [ ] Type hints sur toutes les signatures
- [ ] Docstrings complets (Google style)
- [ ] Imports organisés (stdlib, third-party, local)
- [ ] Pas de dépendances circulaires

### Tests

- [ ] `tests/unit/ui/layout/test_base_manager.py` créé
- [ ] Test d'import du module réussit
- [ ] Syntaxe validée (`py_compile`)

---

## 🏗️ Structure Cible

```
ui/
├── __init__.py              # Existant - ajouter exports layout
├── controllers/             # Existant
├── dialogs/                 # Existant
├── styles/                  # Existant
├── widgets/                 # Existant
└── layout/                  # 🆕 NOUVEAU
    ├── __init__.py          # Exports: all managers
    ├── base_manager.py      # LayoutManagerBase ABC
    ├── splitter_manager.py  # SplitterManager (MIG-061)
    ├── dimensions_manager.py # DimensionsManager (MIG-062)
    ├── spacing_manager.py   # SpacingManager (MIG-063)
    └── action_bar_manager.py # ActionBarManager (MIG-064)
```

---

## 📝 Spécifications Techniques

### 1. `ui/layout/__init__.py`

```python
"""
FilterMate Layout Module.

Layout managers extracted from filter_mate_dockwidget.py.
Part of Phase 6 God Class refactoring (MIG-060 → MIG-089).
"""

from .base_manager import LayoutManagerBase
from .splitter_manager import SplitterManager
from .dimensions_manager import DimensionsManager
from .spacing_manager import SpacingManager
from .action_bar_manager import ActionBarManager

__all__ = [
    'LayoutManagerBase',
    'SplitterManager',
    'DimensionsManager',
    'SpacingManager',
    'ActionBarManager',
]
```

### 2. `ui/layout/base_manager.py`

```python
"""
Base class for layout managers.

All layout managers inherit from LayoutManagerBase which provides:
- Common initialization pattern
- Reference to dockwidget
- Logging setup
- Abstract methods for subclasses
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional
import logging

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class LayoutManagerBase(ABC):
    """
    Abstract base class for layout managers.

    Provides common infrastructure for managers that handle
    UI layout, sizing, and positioning operations.

    Attributes:
        dockwidget: Reference to the main dockwidget
        _initialized: Whether setup() has been called
    """

    def __init__(self, dockwidget: 'FilterMateDockWidget') -> None:
        """
        Initialize the layout manager.

        Args:
            dockwidget: The main FilterMate dockwidget instance
        """
        self.dockwidget = dockwidget
        self._initialized = False
        logger.debug(f"{self.__class__.__name__} created")

    @abstractmethod
    def setup(self) -> None:
        """
        Perform initial setup of layout elements.

        Called once during dockwidget initialization.
        Subclasses must implement this method.
        """
        pass

    @abstractmethod
    def apply(self) -> None:
        """
        Apply layout configuration.

        Called when layout needs to be refreshed or reapplied.
        Subclasses must implement this method.
        """
        pass

    def teardown(self) -> None:
        """
        Clean up resources when manager is destroyed.

        Override in subclasses if cleanup is needed.
        """
        logger.debug(f"{self.__class__.__name__} teardown")
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """Return whether the manager has been initialized."""
        return self._initialized
```

### 3. Squelette Manager (exemple: `splitter_manager.py`)

```python
"""
Splitter Manager for FilterMate.

Handles main splitter configuration and behavior.
Extracted from filter_mate_dockwidget.py (lines 693-848).

Story: MIG-061
"""

from typing import TYPE_CHECKING, Optional
import logging

from qgis.PyQt.QtWidgets import QSplitter, QSizePolicy

from .base_manager import LayoutManagerBase

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class SplitterManager(LayoutManagerBase):
    """
    Manages the main splitter between exploring and toolset frames.

    Responsibilities:
    - Configure splitter properties (handle, collapsible, etc.)
    - Apply frame size policies
    - Set initial size distribution
    - Handle splitter styling

    Methods extracted from dockwidget:
    - _setup_main_splitter()
    - _apply_splitter_frame_policies()
    - _set_initial_splitter_sizes()
    """

    def __init__(self, dockwidget: 'FilterMateDockWidget') -> None:
        super().__init__(dockwidget)
        self._splitter: Optional[QSplitter] = None

    def setup(self) -> None:
        """Setup the main splitter with configuration."""
        # TODO: MIG-061 - Extract from dockwidget._setup_main_splitter()
        self._initialized = True
        logger.debug("SplitterManager setup complete")

    def apply(self) -> None:
        """Apply splitter configuration."""
        # TODO: MIG-061 - Extract from dockwidget methods
        pass

    @property
    def splitter(self) -> Optional[QSplitter]:
        """Return the managed splitter widget."""
        return self._splitter
```

---

## 🔗 Dépendances

### Prérequis

| Story   | Titre                   | Statut |
| ------- | ----------------------- | ------ |
| MIG-024 | Réduction FilterMateApp | 🔄 85% |

### Débloque

| Story   | Titre             | Sprint |
| ------- | ----------------- | ------ |
| MIG-061 | SplitterManager   | 6      |
| MIG-062 | DimensionsManager | 6      |
| MIG-063 | SpacingManager    | 6      |
| MIG-064 | ActionBarManager  | 6      |

---

## 🧪 Tests Requis

### `tests/unit/ui/layout/test_base_manager.py`

```python
"""Tests for LayoutManagerBase."""

import pytest
from unittest.mock import Mock, MagicMock

from ui.layout.base_manager import LayoutManagerBase


class ConcreteManager(LayoutManagerBase):
    """Concrete implementation for testing."""

    def setup(self) -> None:
        self._initialized = True

    def apply(self) -> None:
        pass


class TestLayoutManagerBase:
    """Tests for LayoutManagerBase abstract class."""

    def test_cannot_instantiate_abstract(self):
        """Should not instantiate abstract class."""
        mock_dockwidget = Mock()
        with pytest.raises(TypeError):
            LayoutManagerBase(mock_dockwidget)

    def test_concrete_manager_creation(self):
        """Should create concrete manager."""
        mock_dockwidget = Mock()
        manager = ConcreteManager(mock_dockwidget)
        assert manager.dockwidget is mock_dockwidget
        assert not manager.is_initialized

    def test_setup_sets_initialized(self):
        """Setup should set initialized flag."""
        mock_dockwidget = Mock()
        manager = ConcreteManager(mock_dockwidget)
        manager.setup()
        assert manager.is_initialized

    def test_teardown_clears_initialized(self):
        """Teardown should clear initialized flag."""
        mock_dockwidget = Mock()
        manager = ConcreteManager(mock_dockwidget)
        manager.setup()
        manager.teardown()
        assert not manager.is_initialized
```

### `tests/unit/ui/layout/test_module_imports.py`

```python
"""Tests for layout module imports."""

import pytest


def test_import_layout_module():
    """Should import layout module without errors."""
    from ui import layout
    assert hasattr(layout, 'LayoutManagerBase')
    assert hasattr(layout, 'SplitterManager')
    assert hasattr(layout, 'DimensionsManager')
    assert hasattr(layout, 'SpacingManager')
    assert hasattr(layout, 'ActionBarManager')


def test_all_exports():
    """__all__ should contain all public classes."""
    from ui.layout import __all__
    expected = [
        'LayoutManagerBase',
        'SplitterManager',
        'DimensionsManager',
        'SpacingManager',
        'ActionBarManager',
    ]
    assert set(__all__) == set(expected)
```

---

## 📋 Checklist Développeur

### Préparation

- [ ] Lire les méthodes source (lignes 693-1612, 4039-4604)
- [ ] Comprendre les dépendances (`UIConfig`, `QSplitter`, etc.)
- [ ] Vérifier l'architecture existante (`ui/controllers/`)

### Implémentation

- [ ] Créer `ui/layout/` directory
- [ ] Créer `base_manager.py`
- [ ] Créer 4 squelettes de managers
- [ ] Créer `__init__.py` avec exports
- [ ] Mettre à jour `ui/__init__.py`

### Validation

- [ ] `python3 -m py_compile ui/layout/*.py`
- [ ] Tests unitaires passent
- [ ] Pas de régressions sur tests existants

### Finalisation

- [ ] Commit: `feat(MIG-060): Create ui/layout module structure`
- [ ] Mettre à jour kanban (TODO → DONE)

---

## 📚 Références

| Document          | Lien                                                            |
| ----------------- | --------------------------------------------------------------- |
| Plan Migration    | [god-class-migration-plan.md](../god-class-migration-plan.md)   |
| Epics Phase 6     | [epics.md](../epics.md)                                         |
| Architecture v3   | [docs/architecture-v3.md](../../../docs/architecture-v3.md)     |
| Dockwidget Source | [filter_mate_dockwidget.py](../../../filter_mate_dockwidget.py) |

---

## ⏱️ Estimation

| Activité              | Durée   |
| --------------------- | ------- |
| Création structure    | 15 min  |
| `base_manager.py`     | 30 min  |
| 4 squelettes managers | 45 min  |
| Tests                 | 30 min  |
| Validation            | 15 min  |
| **Total**             | **~2h** |

---

_Story créée par 🧙 BMad Master - 9 janvier 2026_

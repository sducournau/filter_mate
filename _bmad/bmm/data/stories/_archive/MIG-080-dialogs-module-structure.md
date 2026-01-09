---
storyId: MIG-080
title: Create Dialogs Module Structure
epic: 6.5 - Dialogs Extraction
phase: 6
sprint: 8
priority: P3
status: READY_FOR_DEV
effort: 0.5 day
assignee: null
dependsOn: [MIG-070, MIG-075, MIG-076, MIG-077]
blocks: [MIG-081, MIG-082, MIG-083]
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-080: Create Dialogs Module Structure

## 📋 Story

**En tant que** développeur,  
**Je veux** créer la structure du module `ui/dialogs/`,  
**Afin que** les dialogues extraits aient un emplacement dédié et organisé.

---

## 🎯 Objectif

Créer le squelette du module `ui/dialogs/` qui contiendra les 3 dialogues à extraire de `filter_mate_dockwidget.py`:

| Dialog                 | Story   | Lignes Source | Responsabilité          |
| ---------------------- | ------- | ------------- | ----------------------- |
| FavoritesManagerDialog | MIG-081 | 2412-2791     | Gestion des favoris     |
| OptimizationDialog     | MIG-082 | 3683-3806     | Options d'optimisation  |
| PostgresInfoDialog     | MIG-083 | 3442-3531     | Informations session PG |

---

## ✅ Critères d'Acceptation

### Structure Fichiers

- [ ] `ui/dialogs/__init__.py` créé avec exports
- [ ] `ui/dialogs/base_dialog.py` créé avec classe abstraite `BaseDialog`
- [ ] `ui/dialogs/favorites_manager_dialog.py` créé (squelette)
- [ ] `ui/dialogs/optimization_dialog.py` créé (squelette)
- [ ] `ui/dialogs/postgres_info_dialog.py` créé (squelette)

### Code Quality

- [ ] Type hints sur toutes les signatures
- [ ] Docstrings complets (Google style)
- [ ] Imports organisés
- [ ] Pas de dépendances circulaires

### Tests

- [ ] `tests/unit/ui/dialogs/test_base_dialog.py` créé
- [ ] Test d'import du module réussit

---

## 📝 Spécifications Techniques

### Structure Cible

```
ui/dialogs/
├── __init__.py                    # Exports: all dialogs
├── base_dialog.py                 # BaseDialog ABC
├── favorites_manager_dialog.py    # MIG-081
├── optimization_dialog.py         # MIG-082
└── postgres_info_dialog.py        # MIG-083
```

### 1. `ui/dialogs/__init__.py`

```python
"""
FilterMate Dialogs Module.

Dialog classes extracted from filter_mate_dockwidget.py.
Part of Phase 6 God Class refactoring (MIG-080 → MIG-083).
"""

from .base_dialog import BaseDialog
from .favorites_manager_dialog import FavoritesManagerDialog
from .optimization_dialog import OptimizationDialog
from .postgres_info_dialog import PostgresInfoDialog

__all__ = [
    'BaseDialog',
    'FavoritesManagerDialog',
    'OptimizationDialog',
    'PostgresInfoDialog',
]
```

### 2. `ui/dialogs/base_dialog.py`

```python
"""
Base class for FilterMate dialogs.

Provides common infrastructure for modal dialogs.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional
import logging

from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox
from qgis.PyQt.QtCore import Qt

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class BaseDialog(QDialog, ABC):
    """
    Abstract base class for FilterMate dialogs.

    Provides:
    - Standard dialog setup
    - OK/Cancel button handling
    - Theme-aware styling
    - Parent dockwidget reference

    Subclasses must implement:
    - _setup_ui(): Create dialog content
    - _on_accept(): Handle OK button
    """

    def __init__(
        self,
        parent: Optional['FilterMateDockWidget'] = None,
        title: str = "FilterMate"
    ) -> None:
        """
        Initialize the base dialog.

        Args:
            parent: Parent widget (dockwidget)
            title: Dialog window title
        """
        super().__init__(parent)
        self.dockwidget = parent
        self.setWindowTitle(title)
        self.setModal(True)

        self._init_base_layout()
        self._setup_ui()
        self._connect_signals()

        logger.debug(f"{self.__class__.__name__} created")

    def _init_base_layout(self) -> None:
        """Initialize the base layout with button box."""
        self._main_layout = QVBoxLayout(self)
        self._content_layout = QVBoxLayout()
        self._main_layout.addLayout(self._content_layout)

        # Standard button box
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self._main_layout.addWidget(self._button_box)

    def _connect_signals(self) -> None:
        """Connect button signals."""
        self._button_box.accepted.connect(self._handle_accept)
        self._button_box.rejected.connect(self.reject)

    def _handle_accept(self) -> None:
        """Handle accept with validation."""
        if self._validate():
            self._on_accept()
            self.accept()

    def _validate(self) -> bool:
        """
        Validate dialog content before accepting.

        Override in subclasses if validation is needed.

        Returns:
            True if valid
        """
        return True

    @abstractmethod
    def _setup_ui(self) -> None:
        """
        Setup dialog UI content.

        Add widgets to self._content_layout.
        """
        pass

    @abstractmethod
    def _on_accept(self) -> None:
        """
        Handle dialog acceptance.

        Called when OK is clicked and validation passes.
        """
        pass

    def apply_theme(self, is_dark: bool) -> None:
        """
        Apply theme styling to dialog.

        Args:
            is_dark: True for dark theme
        """
        # Subclasses can override for custom theming
        pass
```

### 3. Squelette Dialog (exemple)

```python
"""
Favorites Manager Dialog for FilterMate.

Full-featured dialog for managing filter favorites.
Extracted from filter_mate_dockwidget.py (lines 2412-2791).
"""

from typing import TYPE_CHECKING, List, Optional
import logging

from qgis.PyQt.QtWidgets import (
    QLineEdit, QListWidget, QPushButton, QHBoxLayout
)

from .base_dialog import BaseDialog

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget
    from core.services.favorites_service import FavoritesService

logger = logging.getLogger(__name__)


class FavoritesManagerDialog(BaseDialog):
    """
    Dialog for managing filter favorites.

    Features:
    - Search/filter favorites
    - Edit favorite name/expression
    - Delete favorites
    - Import/Export favorites
    """

    def __init__(
        self,
        parent: Optional['FilterMateDockWidget'] = None,
        favorites_service: 'FavoritesService' = None
    ) -> None:
        self._favorites_service = favorites_service
        super().__init__(parent, "Manage Favorites")

    def _setup_ui(self) -> None:
        """Setup the favorites manager UI."""
        # TODO: Implement in MIG-081
        pass

    def _on_accept(self) -> None:
        """Save changes and close."""
        # TODO: Implement in MIG-081
        pass
```

---

## 🔗 Dépendances

### Entrée

- MIG-070→078: Controllers et Services (utilisés par les dialogs)

### Sortie

- MIG-081, MIG-082, MIG-083: Dialogs concrets

---

## 📊 Métriques

| Métrique          | Avant  | Après      |
| ----------------- | ------ | ---------- |
| Structure dialogs | Aucune | Organisée  |
| Base class        | Aucune | BaseDialog |
| Nouveaux fichiers | 0      | 5          |

---

## 📋 Checklist Développeur

- [ ] Créer le dossier `ui/dialogs/`
- [ ] Créer `ui/dialogs/__init__.py`
- [ ] Créer `ui/dialogs/base_dialog.py`
- [ ] Créer squelettes des 3 dialogs
- [ ] Mettre à jour `ui/__init__.py` avec exports
- [ ] Créer test d'import du module
- [ ] Valider syntaxe

---

_Story générée par 🏃 SM Agent (Bob) - 9 janvier 2026_

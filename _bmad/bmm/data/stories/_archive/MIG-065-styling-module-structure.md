---
storyId: MIG-065
title: Styling Module Structure
epic: 6.2 - Styling Managers Extraction
phase: 6
sprint: 6
priority: P0
status: DONE
effort: 0.5 day
assignee: null
dependsOn: [MIG-060]
blocks: [MIG-066, MIG-067, MIG-068]
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-065: Styling Module Structure

## 📋 Story

**En tant que** développeur,  
**Je veux** créer la structure du module `ui/styling/`,  
**Afin que** les styling managers aient un emplacement dédié et organisé.

---

## 🎯 Objectif

Créer le squelette du module `ui/styling/` qui contiendra les 3 managers de styling à extraire de `filter_mate_dockwidget.py`:

| Manager      | Story   | Lignes Source        | Responsabilité             |
| ------------ | ------- | -------------------- | -------------------------- |
| ThemeManager | MIG-066 | 6154-6444            | Dark/Light mode, themes    |
| IconManager  | MIG-067 | 5785-5863, 6444-6500 | Gestion icônes adaptatives |
| ButtonStyler | MIG-068 | 1041-1153, 6166-6245 | Styling des boutons        |

---

## ✅ Critères d'Acceptation

### Structure Fichiers

- [ ] `ui/styling/__init__.py` créé avec exports
- [ ] `ui/styling/base_styler.py` créé avec classe abstraite `StylerBase`
- [ ] `ui/styling/theme_manager.py` créé (squelette)
- [ ] `ui/styling/icon_manager.py` créé (squelette)
- [ ] `ui/styling/button_styler.py` créé (squelette)

### Intégration

- [ ] Intégration avec `modules/ui_styles.py` existant
- [ ] Intégration avec `IconThemeManager` existant
- [ ] Pas de duplication de code

### Code Quality

- [ ] Type hints sur toutes les signatures
- [ ] Docstrings complets (Google style)
- [ ] Imports organisés
- [ ] Pas de dépendances circulaires

### Tests

- [ ] `tests/unit/ui/styling/test_base_styler.py` créé
- [ ] Test d'import du module réussit

---

## 🏗️ Structure Cible

```
ui/
├── __init__.py
├── layout/                  # Créé en MIG-060
└── styling/                 # 🆕 NOUVEAU
    ├── __init__.py          # Exports: all managers
    ├── base_styler.py       # StylerBase ABC
    ├── theme_manager.py     # ThemeManager (MIG-066)
    ├── icon_manager.py      # IconManager (MIG-067)
    └── button_styler.py     # ButtonStyler (MIG-068)
```

---

## 📝 Spécifications Techniques

### 1. `ui/styling/__init__.py`

```python
"""
FilterMate Styling Module.

Styling managers extracted from filter_mate_dockwidget.py.
Part of Phase 6 God Class refactoring (MIG-060 → MIG-089).
"""

from .base_styler import StylerBase
from .theme_manager import ThemeManager
from .icon_manager import IconManager
from .button_styler import ButtonStyler

__all__ = [
    "StylerBase",
    "ThemeManager",
    "IconManager",
    "ButtonStyler",
]
```

### 2. `ui/styling/base_styler.py`

```python
"""
Base class for FilterMate styling managers.

Provides common functionality for all styling managers.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, Any
import logging

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget
    from config.config import UIConfig

logger = logging.getLogger(__name__)


class StylerBase(ABC):
    """
    Abstract base class for styling managers.

    Provides common functionality for:
    - Configuration access
    - Theme detection
    - QGIS integration

    Attributes:
        dockwidget: Reference to the parent dockwidget
        config: UI configuration
    """

    def __init__(
        self,
        dockwidget: "FilterMateDockWidget",
        config: Optional["UIConfig"] = None
    ) -> None:
        """
        Initialize StylerBase.

        Args:
            dockwidget: Parent FilterMateDockWidget instance
            config: Optional UI configuration. If None, uses dockwidget config.
        """
        self.dockwidget = dockwidget
        self.config = config or self._get_default_config()

    def _get_default_config(self) -> dict:
        """Get default configuration."""
        try:
            return self.dockwidget.fm_config or {}
        except AttributeError:
            return {}

    @abstractmethod
    def apply(self) -> None:
        """
        Apply styling.

        Main entry point for applying styles. Must be implemented
        by subclasses.
        """
        pass

    def is_dark_theme(self) -> bool:
        """
        Check if current QGIS theme is dark.

        Returns:
            True if dark theme, False otherwise
        """
        try:
            from modules.ui_styles import is_dark_theme
            return is_dark_theme()
        except ImportError:
            return False

    def get_theme_name(self) -> str:
        """
        Get current QGIS theme name.

        Returns:
            Theme name string
        """
        try:
            from qgis.core import QgsApplication
            return QgsApplication.uiTheme()
        except ImportError:
            return "default"
```

### 3. Squelettes pour managers

Chaque fichier manager aura cette structure de base:

```python
"""
[Manager Name] for FilterMate.

[Description of what this manager does]
Extracted from filter_mate_dockwidget.py (lines X-Y).

Story: MIG-06X
Phase: 6 - God Class DockWidget Migration
"""

from typing import TYPE_CHECKING, Optional
import logging

from .base_styler import StylerBase

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class [ManagerName](StylerBase):
    """
    [Manager description]

    Attributes:
        [attributes]
    """

    def __init__(
        self,
        dockwidget: "FilterMateDockWidget",
        config: Optional[dict] = None
    ) -> None:
        """Initialize [ManagerName]."""
        super().__init__(dockwidget, config)

    def apply(self) -> None:
        """Apply [styling type]."""
        # TODO: Implement in MIG-06X
        raise NotImplementedError("Pending implementation")
```

---

## 🧪 Tests Requis

### `tests/unit/ui/styling/__init__.py`

```python
"""Unit tests for styling module."""
```

### `tests/unit/ui/styling/test_base_styler.py`

```python
"""Unit tests for StylerBase."""

import pytest
from unittest.mock import Mock, patch


class TestStylerBase:
    """Test suite for StylerBase abstract class."""

    def test_cannot_instantiate_directly(self):
        """StylerBase cannot be instantiated directly."""
        from ui.styling.base_styler import StylerBase

        with pytest.raises(TypeError):
            StylerBase(Mock(), {})

    def test_concrete_implementation_works(self):
        """Concrete implementation can be instantiated."""
        from ui.styling.base_styler import StylerBase

        class ConcreteStyler(StylerBase):
            def apply(self):
                pass

        dockwidget = Mock()
        styler = ConcreteStyler(dockwidget, {})
        assert styler.dockwidget == dockwidget

    def test_is_dark_theme_returns_bool(self):
        """is_dark_theme returns boolean."""
        from ui.styling.base_styler import StylerBase

        class ConcreteStyler(StylerBase):
            def apply(self):
                pass

        with patch('ui.styling.base_styler.is_dark_theme', return_value=True):
            styler = ConcreteStyler(Mock(), {})
            assert styler.is_dark_theme() is True


class TestModuleImports:
    """Test module imports work correctly."""

    def test_import_all_exports(self):
        """All exports can be imported."""
        from ui.styling import (
            StylerBase,
            ThemeManager,
            IconManager,
            ButtonStyler,
        )

        assert StylerBase is not None
        assert ThemeManager is not None
        assert IconManager is not None
        assert ButtonStyler is not None
```

---

## 📋 Checklist de Complétion

### Avant Développement

- [ ] MIG-060 complété (pour pattern cohérent)
- [ ] `modules/ui_styles.py` analysé
- [ ] `IconThemeManager` localisé

### Développement

- [ ] Structure dossier créée
- [ ] `__init__.py` avec exports
- [ ] `base_styler.py` implémenté
- [ ] Squelettes des 3 managers créés

### Post-Développement

- [ ] Tests d'import passent
- [ ] Pas de dépendances circulaires
- [ ] Review de code approuvée

---

## 🔗 Références

- **Epic:** [epics.md](../epics.md#epic-62-styling-managers-extraction)
- **Pattern:** Similaire à MIG-060 (Layout Module)
- **Existant:** `modules/ui_styles.py`, `IconThemeManager`
- **Bloque:** MIG-066, MIG-067, MIG-068

---

_Story créée par 🧙 BMad Master - 9 janvier 2026_

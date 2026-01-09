---
storyId: MIG-068
title: ButtonStyler Extraction
epic: 6.2 - Styling Managers Extraction
phase: 6
sprint: 6
priority: P2
status: READY_FOR_DEV
effort: 0.5 day
assignee: null
dependsOn: [MIG-065]
blocks: []
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-068: ButtonStyler Extraction

## 📋 Story

**En tant que** développeur,  
**Je veux** extraire la logique de styling des boutons dans un manager dédié,  
**Afin d'** avoir un styling cohérent et réduire le God Class.

---

## 🎯 Objectif

Extraire les méthodes de styling des boutons de `filter_mate_dockwidget.py` (lignes 1041-1153, 6166-6245) vers `ui/styling/button_styler.py`:

| Méthode                              | Lignes    | Responsabilité                       |
| ------------------------------------ | --------- | ------------------------------------ |
| `_harmonize_checkable_pushbuttons()` | 1041-1100 | Uniformiser style boutons checkables |
| `_configure_pushbuttons()`           | 1102-1153 | Configuration globale des boutons    |
| `_apply_button_styles()`             | 6166-6200 | Application des styles CSS           |
| `_update_button_states()`            | 6202-6245 | Mise à jour états visuels            |

**Réduction estimée:** ~190 lignes

---

## ✅ Critères d'Acceptation

### Extraction

- [ ] `ButtonStyler` implémente les 4 méthodes
- [ ] Hérite de `StylerBase`
- [ ] Fichier < 200 lignes

### Types de Boutons

- [ ] QPushButton standard
- [ ] QPushButton checkable
- [ ] QToolButton
- [ ] Action buttons (filter, explore, export)

### États Visuels

- [ ] Normal
- [ ] Hover
- [ ] Pressed
- [ ] Checked
- [ ] Disabled

### Intégration

- [ ] Réutilise les styles de `modules/ui_styles.py`
- [ ] Respecte le thème courant
- [ ] S'adapte au profile UI (compact/normal)

### Tests

- [ ] Tests unitaires pour `ButtonStyler`
- [ ] Tests par type de bouton
- [ ] Tests des états visuels

---

## 🏗️ Fichier Cible

### `ui/styling/button_styler.py`

```python
"""
Button Styler for FilterMate.

Manages button styling, states, and theme integration.
Extracted from filter_mate_dockwidget.py (lines 1041-1153, 6166-6245).

Story: MIG-068
Phase: 6 - God Class DockWidget Migration
"""

from typing import TYPE_CHECKING, Optional, List
import logging

from qgis.PyQt.QtWidgets import QPushButton, QToolButton, QWidget

from .base_styler import StylerBase

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget
    from config.config import UIConfig

logger = logging.getLogger(__name__)


class ButtonStyler(StylerBase):
    """
    Manages button styling for FilterMate dockwidget.

    Handles:
    - Checkable button harmonization
    - Button configuration
    - Style application
    - State updates

    Attributes:
        dockwidget: Reference to the parent dockwidget
        config: UI configuration
        _styled_buttons: List of styled buttons for tracking
    """

    def __init__(
        self,
        dockwidget: "FilterMateDockWidget",
        config: Optional["UIConfig"] = None
    ) -> None:
        """
        Initialize ButtonStyler.

        Args:
            dockwidget: Parent FilterMateDockWidget instance
            config: Optional UI configuration
        """
        super().__init__(dockwidget, config)
        self._styled_buttons: List[QWidget] = []

    def apply(self) -> None:
        """
        Apply button styling to all buttons.

        Main entry point for button styling.
        """
        self._configure_pushbuttons()
        self._harmonize_checkable_pushbuttons()
        self._apply_button_styles()

    def setup(self) -> None:
        """
        Initial setup of button styling.

        Called during dockwidget initialization.
        """
        self.apply()

    def _harmonize_checkable_pushbuttons(self) -> None:
        """
        Harmonize styling of checkable pushbuttons.

        Ensures consistent appearance for all checkable buttons:
        - Same checked/unchecked styling
        - Consistent icon placement
        - Uniform size policy
        """
        # TODO: Extract from lines 1041-1100
        raise NotImplementedError("Pending extraction from dockwidget")

    def _configure_pushbuttons(self) -> None:
        """
        Configure all pushbuttons in the dockwidget.

        Sets up:
        - Size policies
        - Cursor styles
        - Flat mode for specific buttons
        - Tool tips
        """
        # TODO: Extract from lines 1102-1153
        raise NotImplementedError("Pending extraction from dockwidget")

    def _apply_button_styles(self) -> None:
        """
        Apply CSS styles to buttons.

        Applies theme-appropriate styles including:
        - Background colors
        - Border styles
        - Hover effects
        - Pressed effects
        """
        # TODO: Extract from lines 6166-6200
        raise NotImplementedError("Pending extraction from dockwidget")

    def _update_button_states(self) -> None:
        """
        Update visual states of buttons.

        Synchronizes button visual states with their logical states:
        - Checked state styling
        - Enabled/disabled styling
        - Active indicator styling
        """
        # TODO: Extract from lines 6202-6245
        raise NotImplementedError("Pending extraction from dockwidget")

    def style_action_buttons(self) -> None:
        """
        Style the main action buttons (filter, explore, export).

        These buttons have special styling requirements.
        """
        action_buttons = [
            self.dockwidget.btn_filtering,
            self.dockwidget.btn_exploring,
            self.dockwidget.btn_exporting,
        ]

        for btn in action_buttons:
            if btn:
                self._apply_action_button_style(btn)
                self._styled_buttons.append(btn)

    def _apply_action_button_style(self, button: QPushButton) -> None:
        """
        Apply styling to an action button.

        Args:
            button: Action button to style
        """
        profile = self.config.get("ui_profile", "normal")

        if profile == "compact":
            button.setMinimumHeight(28)
        else:
            button.setMinimumHeight(36)

        # Apply theme-specific styling
        if self.is_dark_theme():
            button.setStyleSheet(self._get_dark_action_button_style())
        else:
            button.setStyleSheet(self._get_light_action_button_style())

    def _get_dark_action_button_style(self) -> str:
        """
        Get CSS for action buttons in dark theme.

        Returns:
            CSS stylesheet string
        """
        return """
            QPushButton {
                background-color: #3d3d3d;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
                border-color: #666666;
            }
            QPushButton:pressed {
                background-color: #2d2d2d;
            }
            QPushButton:checked {
                background-color: #0d6efd;
                border-color: #0d6efd;
            }
            QPushButton:disabled {
                background-color: #2d2d2d;
                color: #666666;
            }
        """

    def _get_light_action_button_style(self) -> str:
        """
        Get CSS for action buttons in light theme.

        Returns:
            CSS stylesheet string
        """
        return """
            QPushButton {
                background-color: #f8f9fa;
                color: #212529;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
            }
            QPushButton:checked {
                background-color: #0d6efd;
                color: #ffffff;
                border-color: #0d6efd;
            }
            QPushButton:disabled {
                background-color: #e9ecef;
                color: #adb5bd;
            }
        """

    def on_theme_changed(self, theme_name: str) -> None:
        """
        Handle theme change event.

        Args:
            theme_name: New theme name
        """
        logger.info(f"Theme changed to {theme_name}, updating button styles")
        self.apply()

    def cleanup(self) -> None:
        """
        Cleanup styled button references.
        """
        self._styled_buttons.clear()
```

---

## 🧪 Tests Requis

### `tests/unit/ui/styling/test_button_styler.py`

```python
"""Unit tests for ButtonStyler."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from ui.styling.button_styler import ButtonStyler


class TestButtonStyler:
    """Test suite for ButtonStyler."""

    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget with buttons."""
        dockwidget = Mock()
        dockwidget.btn_filtering = Mock()
        dockwidget.btn_exploring = Mock()
        dockwidget.btn_exporting = Mock()
        return dockwidget

    @pytest.fixture
    def config(self):
        """Default configuration."""
        return {"ui_profile": "normal"}

    @pytest.fixture
    def styler(self, mock_dockwidget, config):
        """Create ButtonStyler instance."""
        return ButtonStyler(mock_dockwidget, config)

    def test_init(self, styler):
        """Test styler initialization."""
        assert styler._styled_buttons == []

    def test_apply_calls_all_methods(self, styler):
        """Test apply calls all styling methods."""
        styler._configure_pushbuttons = Mock()
        styler._harmonize_checkable_pushbuttons = Mock()
        styler._apply_button_styles = Mock()

        styler.apply()

        styler._configure_pushbuttons.assert_called_once()
        styler._harmonize_checkable_pushbuttons.assert_called_once()
        styler._apply_button_styles.assert_called_once()

    def test_style_action_buttons(self, styler):
        """Test styling action buttons."""
        styler._apply_action_button_style = Mock()

        styler.style_action_buttons()

        assert styler._apply_action_button_style.call_count == 3
        assert len(styler._styled_buttons) == 3

    def test_action_button_height_normal_profile(self, styler, mock_dockwidget):
        """Test action button height for normal profile."""
        button = mock_dockwidget.btn_filtering

        styler._apply_action_button_style(button)

        button.setMinimumHeight.assert_called_with(36)

    def test_action_button_height_compact_profile(self, mock_dockwidget):
        """Test action button height for compact profile."""
        config = {"ui_profile": "compact"}
        styler = ButtonStyler(mock_dockwidget, config)
        button = mock_dockwidget.btn_filtering

        styler._apply_action_button_style(button)

        button.setMinimumHeight.assert_called_with(28)

    def test_dark_theme_style_applied(self, styler, mock_dockwidget):
        """Test dark theme style application."""
        styler.is_dark_theme = Mock(return_value=True)
        button = mock_dockwidget.btn_filtering

        styler._apply_action_button_style(button)

        call_args = button.setStyleSheet.call_args[0][0]
        assert "#3d3d3d" in call_args  # Dark background

    def test_light_theme_style_applied(self, styler, mock_dockwidget):
        """Test light theme style application."""
        styler.is_dark_theme = Mock(return_value=False)
        button = mock_dockwidget.btn_filtering

        styler._apply_action_button_style(button)

        call_args = button.setStyleSheet.call_args[0][0]
        assert "#f8f9fa" in call_args  # Light background

    def test_on_theme_changed_calls_apply(self, styler):
        """Test theme change triggers apply."""
        styler.apply = Mock()

        styler.on_theme_changed("dark")

        styler.apply.assert_called_once()

    def test_cleanup(self, styler):
        """Test cleanup clears button list."""
        styler._styled_buttons = [Mock(), Mock()]

        styler.cleanup()

        assert styler._styled_buttons == []


class TestButtonStylerCSS:
    """Test CSS generation."""

    @pytest.fixture
    def styler(self):
        """Create ButtonStyler instance."""
        return ButtonStyler(Mock(), {})

    def test_dark_style_includes_hover(self, styler):
        """Test dark style includes hover state."""
        css = styler._get_dark_action_button_style()
        assert ":hover" in css

    def test_dark_style_includes_checked(self, styler):
        """Test dark style includes checked state."""
        css = styler._get_dark_action_button_style()
        assert ":checked" in css

    def test_light_style_includes_disabled(self, styler):
        """Test light style includes disabled state."""
        css = styler._get_light_action_button_style()
        assert ":disabled" in css
```

---

## 📋 Checklist de Complétion

### Avant Développement

- [ ] MIG-065 (Styling Module Structure) complété
- [ ] Revue du code source lignes 1041-1153, 6166-6245
- [ ] Styles existants analysés dans `modules/ui_styles.py`

### Développement

- [ ] Fichier `button_styler.py` créé
- [ ] 4 méthodes extraites et adaptées
- [ ] Styles CSS pour dark/light themes
- [ ] Type hints complets

### Post-Développement

- [ ] Tests unitaires passent
- [ ] Tests de régression passent
- [ ] Review de code approuvée

---

## 🔗 Références

- **Epic:** [epics.md](../epics.md#epic-62-styling-managers-extraction)
- **Code Source:** `filter_mate_dockwidget.py` lignes 1041-1153, 6166-6245
- **Existant:** `modules/ui_styles.py`
- **Dépendance:** MIG-065 (Styling Module Structure)

---

_Story créée par 🧙 BMad Master - 9 janvier 2026_

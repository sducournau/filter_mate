---
storyId: MIG-072
title: Create FavoritesController
epic: 6.3 - New Controllers
phase: 6
sprint: 7
priority: P1
status: READY_FOR_DEV
effort: 1 day
assignee: null
dependsOn: [MIG-020, MIG-076]
blocks: [MIG-081, MIG-087]
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-072: Create FavoritesController

## 📋 Story

**En tant que** développeur,  
**Je veux** créer un controller pour les favoris,  
**Afin que** la gestion des favoris soit isolée et testable.

---

## 🎯 Objectif

Extraire les méthodes de gestion des favoris de `filter_mate_dockwidget.py` (lignes 1966-2897) vers un controller dédié qui délègue la logique métier à `FavoritesService`.

---

## ✅ Critères d'Acceptation

### Code

- [ ] `ui/controllers/favorites_controller.py` créé (< 400 lignes)
- [ ] Type hints sur toutes les signatures
- [ ] Docstrings Google style

### Méthodes Extraites

- [ ] `_on_favorite_indicator_clicked()`
- [ ] `_get_current_filter_expression()`
- [ ] `_update_favorite_indicator()`
- [ ] `_show_favorites_menu()`
- [ ] `_on_add_favorite()`
- [ ] `_on_apply_favorite()`
- [ ] `_on_remove_favorite()`
- [ ] `_on_edit_favorite()`
- [ ] `_on_import_favorites()`
- [ ] `_on_export_favorites()`
- [ ] `_refresh_favorites_list()`
- [ ] `_validate_favorite_name()`

### Intégration

- [ ] Délègue à `FavoritesService` pour la logique métier (MIG-076)
- [ ] Délégation depuis dockwidget fonctionne
- [ ] Signaux Qt correctement gérés
- [ ] Prépare l'intégration avec FavoritesManagerDialog (MIG-081)

### Tests

- [ ] `tests/unit/ui/controllers/test_favorites_controller.py` créé
- [ ] Tests pour ajout/suppression de favoris
- [ ] Tests pour application de favoris
- [ ] Couverture > 80%

---

## 📝 Spécifications Techniques

### Structure du Controller

```python
"""
Favorites Controller for FilterMate.

Manages the favorites indicator and favorites operations UI.
Extracted from filter_mate_dockwidget.py (lines 1966-2897).
"""

from typing import TYPE_CHECKING, List, Optional
import logging

from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.PyQt.QtWidgets import QMenu, QInputDialog, QMessageBox

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget
    from core.services.favorites_service import FavoritesService
    from core.domain.entities import Favorite

logger = logging.getLogger(__name__)


class FavoritesController(QObject):
    """
    Controller for favorites management.

    Handles:
    - Favorites indicator display
    - Add/Remove/Apply favorites
    - Import/Export favorites
    - Favorites menu and dialogs

    Signals:
        favorite_added: Emitted when a favorite is added
        favorite_applied: Emitted when a favorite is applied
        favorite_removed: Emitted when a favorite is removed
    """

    favorite_added = pyqtSignal(str)  # favorite_name
    favorite_applied = pyqtSignal(str)  # favorite_name
    favorite_removed = pyqtSignal(str)  # favorite_name

    def __init__(
        self,
        dockwidget: 'FilterMateDockWidget',
        favorites_service: 'FavoritesService'
    ) -> None:
        """
        Initialize the favorites controller.

        Args:
            dockwidget: Main dockwidget reference
            favorites_service: Service for favorites operations
        """
        super().__init__()
        self.dockwidget = dockwidget
        self._favorites_service = favorites_service

    def setup(self) -> None:
        """Setup favorites indicator widget."""
        self._setup_favorite_indicator()
        self._connect_signals()

    def _on_favorite_indicator_clicked(self) -> None:
        """Handle click on favorite indicator."""
        self._show_favorites_menu()

    def _show_favorites_menu(self) -> None:
        """Show context menu with favorites options."""
        menu = QMenu()

        # Get favorites for current layer
        layer = self.dockwidget.current_layer
        favorites = self._favorites_service.get_favorites_for_layer(layer)

        if favorites:
            for fav in favorites:
                action = menu.addAction(fav.name)
                action.triggered.connect(
                    lambda checked, f=fav: self._on_apply_favorite(f)
                )
            menu.addSeparator()

        menu.addAction("Add Current Filter...", self._on_add_favorite)
        menu.addAction("Manage Favorites...", self._on_manage_favorites)

        menu.exec_(...)

    def _on_add_favorite(self) -> None:
        """Add current filter as a favorite."""
        expression = self._get_current_filter_expression()
        if not expression:
            QMessageBox.warning(
                self.dockwidget,
                "No Filter",
                "No active filter to save."
            )
            return

        name, ok = QInputDialog.getText(
            self.dockwidget,
            "Add Favorite",
            "Favorite name:"
        )

        if ok and name:
            if self._validate_favorite_name(name):
                self._favorites_service.add_favorite(name, expression)
                self.favorite_added.emit(name)
                self._update_favorite_indicator()

    def _on_apply_favorite(self, favorite: 'Favorite') -> None:
        """Apply a saved favorite filter."""
        self._favorites_service.apply_favorite(favorite)
        self.favorite_applied.emit(favorite.name)

    def _get_current_filter_expression(self) -> Optional[str]:
        """Get the current filter expression from filtering controller."""
        filtering_controller = self.dockwidget._filtering_controller
        return filtering_controller.get_current_expression()
```

---

## 🔗 Dépendances

### Entrée

- MIG-020: FilteringController (pour obtenir l'expression courante)
- MIG-076: FavoritesService (logique métier)

### Sortie

- MIG-081: FavoritesManagerDialog (utilise ce controller)
- MIG-087: Final refactoring

---

## 📊 Métriques

| Métrique               | Avant  | Après        |
| ---------------------- | ------ | ------------ |
| Lignes dans dockwidget | ~930   | 0            |
| Nouveau fichier        | -      | < 400 lignes |
| Testabilité            | Faible | Élevée       |

---

## 🧪 Scénarios de Test

### Test 1: Add Favorite

```python
def test_add_favorite():
    """Ajouter un favori doit appeler le service."""
    mock_service = Mock()
    controller = FavoritesController(mock_dockwidget, mock_service)

    controller._on_add_favorite_with_name("My Filter", "population > 1000")

    mock_service.add_favorite.assert_called_once_with(
        "My Filter", "population > 1000"
    )
```

### Test 2: Apply Favorite

```python
def test_apply_favorite():
    """Appliquer un favori doit déclencher le filtrage."""
    mock_service = Mock()
    favorite = Mock(name="Test", expression="id = 1")
    controller = FavoritesController(mock_dockwidget, mock_service)

    controller._on_apply_favorite(favorite)

    mock_service.apply_favorite.assert_called_once_with(favorite)
```

---

## 📋 Checklist Développeur

- [ ] Créer le fichier `ui/controllers/favorites_controller.py`
- [ ] Implémenter `FavoritesController`
- [ ] Ajouter export dans `ui/controllers/__init__.py`
- [ ] Créer délégation dans dockwidget
- [ ] Créer fichier de test
- [ ] Vérifier intégration avec FavoritesService (MIG-076)

---

_Story générée par 🏃 SM Agent (Bob) - 9 janvier 2026_

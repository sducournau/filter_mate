---
storyId: MIG-081
title: Extract FavoritesManagerDialog
epic: 6.5 - Dialogs Extraction
phase: 6
sprint: 8
priority: P2
status: READY_FOR_DEV
effort: 1 day
assignee: null
dependsOn: [MIG-080, MIG-072, MIG-076]
blocks: [MIG-087]
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-081: Extract FavoritesManagerDialog

## 📋 Story

**En tant que** utilisateur,  
**Je veux** un dialogue de gestion des favoris complet,  
**Afin de** pouvoir rechercher, éditer, supprimer et importer/exporter mes favoris.

---

## 🎯 Objectif

Extraire le code inline de gestion des favoris de `filter_mate_dockwidget.py` (lignes 2412-2791) vers un dialogue dédié et réutilisable.

---

## ✅ Critères d'Acceptation

### Code

- [ ] `ui/dialogs/favorites_manager_dialog.py` créé (< 400 lignes)
- [ ] Hérite de `BaseDialog`
- [ ] Type hints sur toutes les signatures
- [ ] Docstrings Google style

### Fonctionnalités UI

- [ ] Liste des favoris avec icônes
- [ ] Barre de recherche avec filtre temps réel
- [ ] Bouton "Edit" pour modifier un favori
- [ ] Bouton "Delete" avec confirmation
- [ ] Bouton "Import" pour importer depuis JSON
- [ ] Bouton "Export" pour exporter vers JSON
- [ ] Double-clic pour appliquer un favori
- [ ] Tri par nom, date de création, dernière utilisation

### Intégration

- [ ] Utilise `FavoritesService` (MIG-076)
- [ ] Coordonne avec `FavoritesController` (MIG-072)
- [ ] Thème dark/light supporté

### Tests

- [ ] `tests/unit/ui/dialogs/test_favorites_manager_dialog.py` créé
- [ ] Tests pour recherche
- [ ] Tests pour actions CRUD
- [ ] Couverture > 75%

---

## 📝 Spécifications Techniques

### Structure du Dialog

```python
"""
Favorites Manager Dialog for FilterMate.

Full-featured dialog for managing filter favorites.
Extracted from filter_mate_dockwidget.py (lines 2412-2791).
"""

from typing import TYPE_CHECKING, List, Optional
import logging

from qgis.PyQt.QtWidgets import (
    QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QHBoxLayout, QVBoxLayout, QMessageBox, QFileDialog,
    QMenu, QAction
)
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QIcon

from .base_dialog import BaseDialog

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget
    from core.services.favorites_service import FavoritesService
    from core.domain.entities import Favorite

logger = logging.getLogger(__name__)


class FavoritesManagerDialog(BaseDialog):
    """
    Dialog for managing filter favorites.

    Features:
    - Search/filter favorites in real-time
    - Edit favorite name and expression
    - Delete with confirmation
    - Import/Export to JSON
    - Sort by name, date, usage

    Signals:
        favorite_applied: Emitted when a favorite should be applied
        favorites_changed: Emitted when favorites list changes
    """

    favorite_applied = pyqtSignal(object)  # Favorite
    favorites_changed = pyqtSignal()

    def __init__(
        self,
        parent: Optional['FilterMateDockWidget'] = None,
        favorites_service: 'FavoritesService' = None
    ) -> None:
        """
        Initialize the favorites manager dialog.

        Args:
            parent: Parent dockwidget
            favorites_service: Service for favorites operations
        """
        self._favorites_service = favorites_service
        self._favorites: List['Favorite'] = []
        super().__init__(parent, "Manage Favorites")
        self.resize(500, 400)

    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        # Search bar
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search favorites...")
        self._search_input.textChanged.connect(self._on_search_changed)
        self._content_layout.addWidget(self._search_input)

        # Favorites list
        self._favorites_list = QListWidget()
        self._favorites_list.setSelectionMode(QListWidget.SingleSelection)
        self._favorites_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._favorites_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._favorites_list.customContextMenuRequested.connect(
            self._show_context_menu
        )
        self._content_layout.addWidget(self._favorites_list)

        # Action buttons
        button_layout = QHBoxLayout()

        self._edit_btn = QPushButton("Edit")
        self._edit_btn.clicked.connect(self._on_edit_clicked)
        button_layout.addWidget(self._edit_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        button_layout.addWidget(self._delete_btn)

        button_layout.addStretch()

        self._import_btn = QPushButton("Import...")
        self._import_btn.clicked.connect(self._on_import_clicked)
        button_layout.addWidget(self._import_btn)

        self._export_btn = QPushButton("Export...")
        self._export_btn.clicked.connect(self._on_export_clicked)
        button_layout.addWidget(self._export_btn)

        self._content_layout.addLayout(button_layout)

        # Load favorites
        self._load_favorites()

    def _load_favorites(self) -> None:
        """Load favorites from service."""
        if self._favorites_service:
            self._favorites = self._favorites_service.get_all_favorites()
            self._refresh_list()

    def _refresh_list(self, filter_text: str = "") -> None:
        """
        Refresh the favorites list with optional filter.

        Args:
            filter_text: Text to filter favorites by
        """
        self._favorites_list.clear()

        for favorite in self._favorites:
            # Apply filter
            if filter_text:
                if (filter_text.lower() not in favorite.name.lower() and
                    filter_text.lower() not in favorite.expression.lower()):
                    continue

            item = QListWidgetItem(favorite.name)
            item.setData(Qt.UserRole, favorite)
            item.setToolTip(favorite.expression)
            self._favorites_list.addItem(item)

    def _on_search_changed(self, text: str) -> None:
        """Handle search text change."""
        self._refresh_list(text)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle double-click to apply favorite."""
        favorite = item.data(Qt.UserRole)
        self.favorite_applied.emit(favorite)
        self.accept()

    def _on_edit_clicked(self) -> None:
        """Handle edit button click."""
        item = self._favorites_list.currentItem()
        if not item:
            return

        favorite = item.data(Qt.UserRole)
        # TODO: Open edit dialog

    def _on_delete_clicked(self) -> None:
        """Handle delete button click."""
        item = self._favorites_list.currentItem()
        if not item:
            return

        favorite = item.data(Qt.UserRole)

        reply = QMessageBox.question(
            self,
            "Delete Favorite",
            f"Are you sure you want to delete '{favorite.name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self._favorites_service.remove_favorite(favorite.id)
            self._load_favorites()
            self.favorites_changed.emit()

    def _on_import_clicked(self) -> None:
        """Handle import button click."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Favorites",
            "",
            "JSON Files (*.json)"
        )

        if path:
            count = self._favorites_service.import_favorites(path)
            QMessageBox.information(
                self,
                "Import Complete",
                f"Imported {count} favorites."
            )
            self._load_favorites()
            self.favorites_changed.emit()

    def _on_export_clicked(self) -> None:
        """Handle export button click."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Favorites",
            "filtermate_favorites.json",
            "JSON Files (*.json)"
        )

        if path:
            self._favorites_service.export_favorites(path)
            QMessageBox.information(
                self,
                "Export Complete",
                f"Exported favorites to {path}"
            )

    def _show_context_menu(self, pos) -> None:
        """Show context menu for favorites list."""
        item = self._favorites_list.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)
        menu.addAction("Apply", lambda: self._on_item_double_clicked(item))
        menu.addAction("Edit", self._on_edit_clicked)
        menu.addSeparator()
        menu.addAction("Delete", self._on_delete_clicked)
        menu.exec_(self._favorites_list.mapToGlobal(pos))

    def _on_accept(self) -> None:
        """Handle dialog acceptance."""
        pass  # No action needed on OK
```

---

## 🔗 Dépendances

### Entrée

- MIG-080: Base dialog structure
- MIG-072: FavoritesController
- MIG-076: FavoritesService

### Sortie

- MIG-087: Final refactoring

---

## 📊 Métriques

| Métrique                    | Avant       | Après        |
| --------------------------- | ----------- | ------------ |
| Code inline dans dockwidget | ~380 lignes | 0            |
| Nouveau fichier             | -           | < 400 lignes |
| Réutilisabilité             | Aucune      | Haute        |

---

## 🧪 Scénarios de Test

### Test 1: Search Filters List

```python
def test_search_filters_list():
    """La recherche doit filtrer la liste."""
    dialog = FavoritesManagerDialog(None, mock_service)
    dialog._favorites = [
        Mock(name="Population Filter", expression="pop > 100"),
        Mock(name="Area Check", expression="area > 500"),
    ]

    dialog._on_search_changed("pop")

    assert dialog._favorites_list.count() == 1
```

### Test 2: Delete With Confirmation

```python
def test_delete_requires_confirmation():
    """La suppression doit demander confirmation."""
    mock_service = Mock()
    dialog = FavoritesManagerDialog(None, mock_service)

    # Simuler clic sur Non
    with patch.object(QMessageBox, 'question', return_value=QMessageBox.No):
        dialog._on_delete_clicked()

    mock_service.remove_favorite.assert_not_called()
```

---

## 📋 Checklist Développeur

- [ ] Créer `ui/dialogs/favorites_manager_dialog.py`
- [ ] Implémenter toutes les fonctionnalités UI
- [ ] Connecter avec FavoritesService
- [ ] Ajouter support thème dark/light
- [ ] Créer fichier de test
- [ ] Tester import/export JSON

---

_Story générée par 🏃 SM Agent (Bob) - 9 janvier 2026_

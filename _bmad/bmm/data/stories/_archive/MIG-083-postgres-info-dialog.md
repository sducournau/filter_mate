---
storyId: MIG-083
title: Extract PostgresInfoDialog
epic: 6.5 - Dialogs Extraction
phase: 6
sprint: 8
priority: P3
status: READY_FOR_DEV
effort: 0.5 day
assignee: null
dependsOn: [MIG-080, MIG-078]
blocks: [MIG-087]
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-083: Extract PostgresInfoDialog

## 📋 Story

**En tant que** utilisateur avancé,  
**Je veux** voir les informations de ma session PostgreSQL,  
**Afin de** comprendre quelles ressources sont utilisées.

---

## 🎯 Objectif

Extraire le code inline d'information PostgreSQL de `filter_mate_dockwidget.py` (lignes 3442-3531) vers un dialogue dédié.

---

## ✅ Critères d'Acceptation

### Code

- [ ] `ui/dialogs/postgres_info_dialog.py` créé (< 150 lignes)
- [ ] Hérite de `BaseDialog`
- [ ] Type hints sur toutes les signatures

### Fonctionnalités UI

- [ ] Affichage du nom de connexion
- [ ] Affichage du schéma utilisé
- [ ] Liste des vues temporaires actives
- [ ] Bouton "Cleanup Now" pour nettoyer les vues
- [ ] Checkbox "Auto-cleanup on close"
- [ ] Affichage "PostgreSQL not available" si non disponible

### Intégration

- [ ] Utilise `PostgresSessionManager` (MIG-078)
- [ ] Read-only sauf pour les actions de cleanup

### Tests

- [ ] `tests/unit/ui/dialogs/test_postgres_info_dialog.py` créé
- [ ] Tests pour état sans PostgreSQL
- [ ] Couverture > 75%

---

## 📝 Spécifications Techniques

### Structure du Dialog

```python
"""
PostgreSQL Info Dialog for FilterMate.

Dialog displaying PostgreSQL session information.
Extracted from filter_mate_dockwidget.py (lines 3442-3531).
"""

from typing import TYPE_CHECKING, Optional
import logging

from qgis.PyQt.QtWidgets import (
    QLabel, QListWidget, QPushButton, QCheckBox,
    QGroupBox, QFormLayout, QHBoxLayout, QMessageBox
)
from qgis.PyQt.QtCore import Qt

from .base_dialog import BaseDialog

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget
    from adapters.backends.postgres_session_manager import PostgresSessionManager

logger = logging.getLogger(__name__)


class PostgresInfoDialog(BaseDialog):
    """
    Dialog displaying PostgreSQL session information.

    Shows:
    - Connection name
    - Schema used for temp objects
    - Active temporary views
    - Cleanup options

    If PostgreSQL is not available, shows a message instead.
    """

    def __init__(
        self,
        parent: Optional['FilterMateDockWidget'] = None,
        session_manager: 'PostgresSessionManager' = None
    ) -> None:
        """
        Initialize the PostgreSQL info dialog.

        Args:
            parent: Parent dockwidget
            session_manager: Manager for PostgreSQL session
        """
        self._session_manager = session_manager
        super().__init__(parent, "PostgreSQL Session Info")
        self.resize(400, 300)

        # Hide OK button, only Cancel (Close)
        self._button_box.button(self._button_box.Ok).hide()
        self._button_box.button(self._button_box.Cancel).setText("Close")

    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        # Check if PostgreSQL is available
        if not self._session_manager or not self._session_manager.is_available:
            self._setup_unavailable_ui()
            return

        self._setup_available_ui()

    def _setup_unavailable_ui(self) -> None:
        """Setup UI when PostgreSQL is not available."""
        label = QLabel(
            "PostgreSQL is not available.\n\n"
            "To use PostgreSQL features, install psycopg2:\n"
            "pip install psycopg2-binary\n\n"
            "Then restart QGIS."
        )
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        self._content_layout.addWidget(label)

    def _setup_available_ui(self) -> None:
        """Setup UI when PostgreSQL is available."""
        # Connection info group
        info_group = QGroupBox("Connection Info")
        info_layout = QFormLayout()

        self._connection_label = QLabel("Default")
        info_layout.addRow("Connection:", self._connection_label)

        self._schema_label = QLabel(self._session_manager.FILTERMATE_SCHEMA)
        info_layout.addRow("Temp Schema:", self._schema_label)

        info_group.setLayout(info_layout)
        self._content_layout.addWidget(info_group)

        # Temporary views group
        views_group = QGroupBox("Temporary Views")
        views_layout = QFormLayout()

        self._views_list = QListWidget()
        self._views_list.setMaximumHeight(150)
        views_layout.addRow(self._views_list)

        views_group.setLayout(views_layout)
        self._content_layout.addWidget(views_group)

        # Cleanup options
        cleanup_group = QGroupBox("Cleanup Options")
        cleanup_layout = QFormLayout()

        self._auto_cleanup_cb = QCheckBox()
        self._auto_cleanup_cb.setChecked(
            self._session_manager._auto_cleanup_enabled
        )
        self._auto_cleanup_cb.stateChanged.connect(self._on_auto_cleanup_changed)
        self._auto_cleanup_cb.setToolTip(
            "Automatically cleanup temporary views when FilterMate closes."
        )
        cleanup_layout.addRow("Auto-cleanup on close:", self._auto_cleanup_cb)

        # Cleanup button
        button_layout = QHBoxLayout()
        self._cleanup_btn = QPushButton("Cleanup Now")
        self._cleanup_btn.clicked.connect(self._on_cleanup_clicked)
        button_layout.addWidget(self._cleanup_btn)
        button_layout.addStretch()
        cleanup_layout.addRow(button_layout)

        cleanup_group.setLayout(cleanup_layout)
        self._content_layout.addWidget(cleanup_group)

        # Load data
        self._refresh_views()

    def _refresh_views(self) -> None:
        """Refresh the list of temporary views."""
        if not self._session_manager:
            return

        self._views_list.clear()
        views = self._session_manager.get_session_views()

        for view in views:
            self._views_list.addItem(view)

        if not views:
            self._views_list.addItem("(No temporary views)")
            self._cleanup_btn.setEnabled(False)
        else:
            self._cleanup_btn.setEnabled(True)

    def _on_auto_cleanup_changed(self, state: int) -> None:
        """Handle auto-cleanup checkbox change."""
        enabled = state == Qt.Checked
        self._session_manager.toggle_auto_cleanup(enabled)
        logger.debug(f"Auto-cleanup set to {enabled}")

    def _on_cleanup_clicked(self) -> None:
        """Handle cleanup button click."""
        reply = QMessageBox.question(
            self,
            "Confirm Cleanup",
            "This will drop all temporary views created by FilterMate.\n"
            "Any unsaved filter results will be lost.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            count = self._session_manager.cleanup_session_views()
            self._session_manager.cleanup_schema_if_empty()

            QMessageBox.information(
                self,
                "Cleanup Complete",
                f"Removed {count} temporary views."
            )

            self._refresh_views()

    def _on_accept(self) -> None:
        """Handle dialog acceptance (not used)."""
        pass
```

---

## 🔗 Dépendances

### Entrée

- MIG-080: Base dialog structure
- MIG-078: PostgresSessionManager

### Sortie

- MIG-087: Final refactoring

---

## 📊 Métriques

| Métrique                    | Avant      | Après        |
| --------------------------- | ---------- | ------------ |
| Code inline dans dockwidget | ~90 lignes | 0            |
| Nouveau fichier             | -          | < 150 lignes |

---

## 🧪 Scénarios de Test

### Test 1: Show Unavailable Message

```python
def test_show_unavailable_when_no_postgres():
    """Le dialogue doit afficher un message si PG indisponible."""
    dialog = PostgresInfoDialog(None, None)

    # Vérifier que le message d'indisponibilité est affiché
    # (Implémenter selon la structure exacte)
```

### Test 2: Cleanup Button Disabled When No Views

```python
def test_cleanup_disabled_when_no_views():
    """Le bouton cleanup doit être désactivé sans vues."""
    mock_manager = Mock()
    mock_manager.is_available = True
    mock_manager.get_session_views.return_value = []

    dialog = PostgresInfoDialog(None, mock_manager)

    assert dialog._cleanup_btn.isEnabled() is False
```

---

## 📋 Checklist Développeur

- [ ] Créer `ui/dialogs/postgres_info_dialog.py`
- [ ] Implémenter UI d'information
- [ ] Ajouter gestion du cas "non disponible"
- [ ] Connecter avec PostgresSessionManager
- [ ] Créer fichier de test

---

_Story générée par 🏃 SM Agent (Bob) - 9 janvier 2026_

---
storyId: MIG-071
title: Create BackendController
epic: 6.3 - New Controllers
phase: 6
sprint: 7
priority: P1
status: READY_FOR_DEV
effort: 1 day
assignee: null
dependsOn: [MIG-020, MIG-075]
blocks: [MIG-087]
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-071: Create BackendController

## 📋 Story

**En tant que** développeur,  
**Je veux** créer un controller pour l'indicateur de backend,  
**Afin que** la sélection et l'affichage du backend soient isolés.

---

## 🎯 Objectif

Extraire les méthodes de gestion du backend indicator de `filter_mate_dockwidget.py` (lignes 1612-1966) vers un controller dédié qui délègue la logique métier à `BackendService`.

---

## ✅ Critères d'Acceptation

### Code

- [ ] `ui/controllers/backend_controller.py` créé (< 300 lignes)
- [ ] Type hints sur toutes les signatures
- [ ] Docstrings Google style

### Méthodes Extraites

- [ ] `_setup_backend_indicator()`
- [ ] `_on_backend_indicator_clicked()`
- [ ] `_update_backend_indicator_display()`
- [ ] `_show_backend_selection_menu()`
- [ ] `_on_backend_selected()`
- [ ] `_get_backend_icon()`
- [ ] `_get_backend_tooltip()`

### Intégration

- [ ] Délègue à `BackendService` pour la logique métier (MIG-075)
- [ ] Délégation depuis dockwidget fonctionne
- [ ] Signaux Qt correctement gérés

### Tests

- [ ] `tests/unit/ui/controllers/test_backend_controller.py` créé
- [ ] Tests pour affichage de l'indicateur
- [ ] Tests pour sélection de backend
- [ ] Couverture > 80%

---

## 📝 Spécifications Techniques

### Structure du Controller

```python
"""
Backend Controller for FilterMate.

Manages the backend indicator widget and selection menu.
Extracted from filter_mate_dockwidget.py (lines 1612-1966).
"""

from typing import TYPE_CHECKING, Optional
import logging

from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.PyQt.QtWidgets import QMenu, QAction

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget
    from core.services.backend_service import BackendService

logger = logging.getLogger(__name__)


class BackendController(QObject):
    """
    Controller for backend indicator management.

    Handles:
    - Backend indicator display
    - Backend selection menu
    - Backend switching

    Signals:
        backend_changed: Emitted when backend is switched
    """

    backend_changed = pyqtSignal(str)  # backend_name

    def __init__(
        self,
        dockwidget: 'FilterMateDockWidget',
        backend_service: 'BackendService'
    ) -> None:
        """
        Initialize the backend controller.

        Args:
            dockwidget: Main dockwidget reference
            backend_service: Service for backend operations
        """
        super().__init__()
        self.dockwidget = dockwidget
        self._backend_service = backend_service
        self._current_backend: Optional[str] = None

    def setup(self) -> None:
        """Setup backend indicator widget."""
        self._setup_backend_indicator()
        self._connect_signals()

    def _setup_backend_indicator(self) -> None:
        """Configure the backend indicator button."""
        pass

    def _on_backend_indicator_clicked(self) -> None:
        """Handle click on backend indicator."""
        self._show_backend_selection_menu()

    def _show_backend_selection_menu(self) -> None:
        """Show menu with available backends for current layer."""
        pass

    def _on_backend_selected(self, backend_name: str) -> None:
        """
        Handle backend selection from menu.

        Args:
            backend_name: Name of selected backend
        """
        pass

    def update_for_layer(self, layer) -> None:
        """
        Update indicator for current layer.

        Args:
            layer: Current QgsVectorLayer
        """
        pass
```

### Interaction avec BackendService

```python
# Le controller délègue la logique au service
def _show_backend_selection_menu(self) -> None:
    layer = self.dockwidget.current_layer
    if not layer:
        return

    # Logique métier dans le service
    available = self._backend_service.get_available_backends_for_layer(layer)
    optimal = self._backend_service.get_optimal_backend_for_layer(layer)

    # Le controller gère uniquement l'UI
    menu = QMenu()
    for backend in available:
        action = menu.addAction(backend)
        if backend == optimal:
            action.setIcon(self._get_recommended_icon())
        action.triggered.connect(lambda b=backend: self._on_backend_selected(b))

    menu.exec_(...)
```

---

## 🔗 Dépendances

### Entrée

- MIG-020: FilteringController (pattern à suivre)
- MIG-075: BackendService (logique métier)

### Sortie

- MIG-087: Final refactoring

---

## 📊 Métriques

| Métrique               | Avant | Après                |
| ---------------------- | ----- | -------------------- |
| Lignes dans dockwidget | ~350  | 0                    |
| Nouveau fichier        | -     | < 300 lignes         |
| Couplage               | Fort  | Faible (via service) |

---

## 🧪 Scénarios de Test

### Test 1: Update for PostgreSQL Layer

```python
def test_update_for_postgresql_layer():
    """L'indicateur doit afficher PostgreSQL pour une couche postgres."""
    controller = BackendController(mock_dockwidget, mock_service)
    mock_layer = Mock(providerType=Mock(return_value='postgres'))

    controller.update_for_layer(mock_layer)

    assert controller._current_backend == 'postgresql'
```

### Test 2: Show Available Backends Menu

```python
def test_show_backend_menu():
    """Le menu doit afficher les backends disponibles."""
    mock_service = Mock()
    mock_service.get_available_backends_for_layer.return_value = [
        'postgresql', 'spatialite', 'ogr'
    ]
    controller = BackendController(mock_dockwidget, mock_service)

    # Vérifier que le menu est créé avec les bons backends
```

---

## 📋 Checklist Développeur

- [ ] Créer le fichier `ui/controllers/backend_controller.py`
- [ ] Implémenter `BackendController`
- [ ] Ajouter export dans `ui/controllers/__init__.py`
- [ ] Créer délégation dans dockwidget
- [ ] Créer fichier de test
- [ ] Vérifier intégration avec BackendService (MIG-075)

---

_Story générée par 🏃 SM Agent (Bob) - 9 janvier 2026_

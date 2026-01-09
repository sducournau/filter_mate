---
storyId: MIG-082
title: Extract OptimizationDialog
epic: 6.5 - Dialogs Extraction
phase: 6
sprint: 8
priority: P2
status: READY_FOR_DEV
effort: 0.5 day
assignee: null
dependsOn: [MIG-080, MIG-075]
blocks: [MIG-087]
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-082: Extract OptimizationDialog

## 📋 Story

**En tant que** utilisateur avancé,  
**Je veux** un dialogue pour configurer les options d'optimisation,  
**Afin de** pouvoir ajuster les performances du filtrage.

---

## 🎯 Objectif

Extraire le code inline des options d'optimisation de `filter_mate_dockwidget.py` (lignes 3683-3806) vers un dialogue dédié.

---

## ✅ Critères d'Acceptation

### Code

- [ ] `ui/dialogs/optimization_dialog.py` créé (< 200 lignes)
- [ ] Hérite de `BaseDialog`
- [ ] Type hints sur toutes les signatures

### Fonctionnalités UI

- [ ] Option "Use spatial index" (checkbox)
- [ ] Option "Use materialized views" (checkbox, PostgreSQL only)
- [ ] Option "Batch size" (spinbox)
- [ ] Option "Parallel processing" (checkbox)
- [ ] Affichage conditionnel selon backend disponible
- [ ] Tooltips explicatifs pour chaque option

### Intégration

- [ ] Utilise `BackendService` pour vérifier les capabilities (MIG-075)
- [ ] Sauvegarde les options dans la configuration

### Tests

- [ ] `tests/unit/ui/dialogs/test_optimization_dialog.py` créé
- [ ] Tests pour options conditionnelles
- [ ] Couverture > 80%

---

## 📝 Spécifications Techniques

### Structure du Dialog

```python
"""
Optimization Dialog for FilterMate.

Dialog for configuring performance options.
Extracted from filter_mate_dockwidget.py (lines 3683-3806).
"""

from typing import TYPE_CHECKING, Optional, Dict, Any
import logging

from qgis.PyQt.QtWidgets import (
    QCheckBox, QSpinBox, QLabel, QGroupBox,
    QFormLayout, QVBoxLayout
)
from qgis.PyQt.QtCore import Qt

from .base_dialog import BaseDialog

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget
    from core.services.backend_service import BackendService

logger = logging.getLogger(__name__)


class OptimizationDialog(BaseDialog):
    """
    Dialog for configuring optimization options.

    Options available:
    - Spatial index usage
    - Materialized views (PostgreSQL only)
    - Batch processing size
    - Parallel processing

    Options are conditionally shown based on
    available backends and their capabilities.
    """

    def __init__(
        self,
        parent: Optional['FilterMateDockWidget'] = None,
        backend_service: 'BackendService' = None,
        current_options: Dict[str, Any] = None
    ) -> None:
        """
        Initialize the optimization dialog.

        Args:
            parent: Parent dockwidget
            backend_service: Service for backend capabilities
            current_options: Current option values
        """
        self._backend_service = backend_service
        self._current_options = current_options or {}
        super().__init__(parent, "Optimization Options")

    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        # General options group
        general_group = QGroupBox("General Options")
        general_layout = QFormLayout()

        # Spatial index
        self._spatial_index_cb = QCheckBox()
        self._spatial_index_cb.setChecked(
            self._current_options.get('use_spatial_index', True)
        )
        self._spatial_index_cb.setToolTip(
            "Use spatial indexes for faster filtering. "
            "Recommended for all backends."
        )
        general_layout.addRow("Use spatial index:", self._spatial_index_cb)

        # Batch size
        self._batch_size_spin = QSpinBox()
        self._batch_size_spin.setRange(100, 100000)
        self._batch_size_spin.setSingleStep(1000)
        self._batch_size_spin.setValue(
            self._current_options.get('batch_size', 10000)
        )
        self._batch_size_spin.setToolTip(
            "Number of features to process in each batch. "
            "Larger values may improve performance but use more memory."
        )
        general_layout.addRow("Batch size:", self._batch_size_spin)

        general_group.setLayout(general_layout)
        self._content_layout.addWidget(general_group)

        # PostgreSQL options group
        self._pg_group = QGroupBox("PostgreSQL Options")
        pg_layout = QFormLayout()

        # Materialized views
        self._mat_views_cb = QCheckBox()
        self._mat_views_cb.setChecked(
            self._current_options.get('use_materialized_views', True)
        )
        self._mat_views_cb.setToolTip(
            "Use materialized views for complex filters. "
            "Improves performance for repeated queries."
        )
        pg_layout.addRow("Use materialized views:", self._mat_views_cb)

        # Parallel processing
        self._parallel_cb = QCheckBox()
        self._parallel_cb.setChecked(
            self._current_options.get('parallel_processing', False)
        )
        self._parallel_cb.setToolTip(
            "Enable parallel query execution. "
            "Requires PostgreSQL 9.6+ with parallel settings enabled."
        )
        pg_layout.addRow("Parallel processing:", self._parallel_cb)

        self._pg_group.setLayout(pg_layout)
        self._content_layout.addWidget(self._pg_group)

        # Update visibility based on capabilities
        self._update_capabilities_ui()

    def _update_capabilities_ui(self) -> None:
        """Update UI based on backend capabilities."""
        if not self._backend_service:
            return

        # Check if PostgreSQL is available
        pg_available = self._backend_service.is_backend_available('postgresql')
        self._pg_group.setEnabled(pg_available)

        if not pg_available:
            self._pg_group.setTitle("PostgreSQL Options (Not Available)")

        # Check specific capabilities
        if pg_available:
            caps = self._backend_service.get_backend_capabilities('postgresql')
            self._mat_views_cb.setEnabled(caps.supports_materialized_views)
            self._parallel_cb.setEnabled(caps.supports_concurrent_queries)

    def get_options(self) -> Dict[str, Any]:
        """
        Get the current option values.

        Returns:
            Dictionary of option values
        """
        return {
            'use_spatial_index': self._spatial_index_cb.isChecked(),
            'batch_size': self._batch_size_spin.value(),
            'use_materialized_views': self._mat_views_cb.isChecked(),
            'parallel_processing': self._parallel_cb.isChecked(),
        }

    def _on_accept(self) -> None:
        """Handle dialog acceptance."""
        # Options are retrieved via get_options()
        logger.debug(f"Optimization options accepted: {self.get_options()}")
```

---

## 🔗 Dépendances

### Entrée

- MIG-080: Base dialog structure
- MIG-075: BackendService (pour capabilities)

### Sortie

- MIG-087: Final refactoring

---

## 📊 Métriques

| Métrique                    | Avant       | Après        |
| --------------------------- | ----------- | ------------ |
| Code inline dans dockwidget | ~125 lignes | 0            |
| Nouveau fichier             | -           | < 200 lignes |

---

## 🧪 Scénarios de Test

### Test 1: PostgreSQL Options Disabled When Unavailable

```python
def test_pg_options_disabled_when_unavailable():
    """Les options PG doivent être désactivées si PG indisponible."""
    mock_service = Mock()
    mock_service.is_backend_available.return_value = False

    dialog = OptimizationDialog(None, mock_service)

    assert dialog._pg_group.isEnabled() is False
```

### Test 2: Get Options Returns Correct Values

```python
def test_get_options():
    """get_options doit retourner les valeurs actuelles."""
    dialog = OptimizationDialog(None, None, {
        'use_spatial_index': False,
        'batch_size': 5000
    })

    options = dialog.get_options()

    assert options['use_spatial_index'] is False
    assert options['batch_size'] == 5000
```

---

## 📋 Checklist Développeur

- [ ] Créer `ui/dialogs/optimization_dialog.py`
- [ ] Implémenter UI avec options
- [ ] Ajouter logique de capabilities
- [ ] Ajouter tooltips explicatifs
- [ ] Créer fichier de test

---

_Story générée par 🏃 SM Agent (Bob) - 9 janvier 2026_

---
storyId: MIG-073
title: Create LayerSyncController
epic: 6.3 - New Controllers
phase: 6
sprint: 7
priority: P1
status: READY_FOR_DEV
effort: 1.5 days
assignee: null
dependsOn: [MIG-020, MIG-077, MIG-084]
blocks: [MIG-087]
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-073: Create LayerSyncController

## 📋 Story

**En tant que** développeur,  
**Je veux** créer un controller pour la synchronisation des layers,  
**Afin que** le changement de layer soit géré proprement et sans bugs.

---

## 🎯 Objectif

Extraire les méthodes de synchronisation des layers de `filter_mate_dockwidget.py` (lignes 9826-10796) vers un controller dédié.

**Note:** Ce controller est critique car il est au cœur du bug CRIT-005 (perte de couche courante après filtre).

---

## ✅ Critères d'Acceptation

### Code

- [ ] `ui/controllers/layer_sync_controller.py` créé (< 600 lignes)
- [ ] Type hints sur toutes les signatures
- [ ] Docstrings Google style
- [ ] Gestion robuste des edge cases

### Méthodes Extraites

- [ ] `_synchronize_layer_widgets()`
- [ ] `_reload_exploration_widgets()`
- [ ] `_restore_groupbox_ui_state()`
- [ ] `current_layer_changed()`
- [ ] `_on_layer_added()`
- [ ] `_on_layer_removed()`
- [ ] `_on_layers_will_be_removed()`
- [ ] `_ensure_valid_current_layer()`
- [ ] `_is_within_post_filter_protection()`
- [ ] `_save_current_layer_before_filter()`
- [ ] `_restore_current_layer_after_filter()`

### Protection Post-Filtre

- [ ] Fenêtre de protection intégrée (5 secondes)
- [ ] Blocage des changements layer=None pendant protection
- [ ] Logs détaillés pour debugging

### Intégration

- [ ] Délègue à `LayerService` pour la validation (MIG-077)
- [ ] Coordonne avec `SignalManager` (MIG-084)
- [ ] Délégation depuis dockwidget fonctionne

### Tests

- [ ] `tests/unit/ui/controllers/test_layer_sync_controller.py` créé
- [ ] Tests pour changement de layer normal
- [ ] Tests pour protection post-filtre
- [ ] Tests pour layer=None bloqué
- [ ] Couverture > 85%

---

## 📝 Spécifications Techniques

### Structure du Controller

```python
"""
Layer Sync Controller for FilterMate.

Manages layer change synchronization and widget updates.
Extracted from filter_mate_dockwidget.py (lines 9826-10796).

CRITICAL: This controller handles the post-filter protection
to prevent CRIT-005 (layer loss after filter).
"""

from typing import TYPE_CHECKING, Optional
import logging
import time

from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.core import QgsVectorLayer, QgsProject

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget
    from core.services.layer_service import LayerService

logger = logging.getLogger(__name__)

# Protection window after filter completes
POST_FILTER_PROTECTION_WINDOW = 5.0  # seconds


class LayerSyncController(QObject):
    """
    Controller for layer synchronization.

    Handles:
    - Layer change events
    - Widget synchronization on layer change
    - Post-filter protection (CRIT-005 fix)
    - Layer add/remove events

    Signals:
        layer_synchronized: Emitted when layer sync completes
        sync_blocked: Emitted when sync is blocked (protection)
    """

    layer_synchronized = pyqtSignal(object)  # QgsVectorLayer
    sync_blocked = pyqtSignal(str)  # reason

    def __init__(
        self,
        dockwidget: 'FilterMateDockWidget',
        layer_service: 'LayerService'
    ) -> None:
        """
        Initialize the layer sync controller.

        Args:
            dockwidget: Main dockwidget reference
            layer_service: Service for layer operations
        """
        super().__init__()
        self.dockwidget = dockwidget
        self._layer_service = layer_service
        self._filter_completed_time: Optional[float] = None
        self._saved_layer_id_before_filter: Optional[str] = None
        self._current_layer_id: Optional[str] = None

    def setup(self) -> None:
        """Connect to QGIS layer change signals."""
        iface = self.dockwidget.iface
        iface.currentLayerChanged.connect(self.current_layer_changed)
        QgsProject.instance().layerWasAdded.connect(self._on_layer_added)
        QgsProject.instance().layersWillBeRemoved.connect(
            self._on_layers_will_be_removed
        )

    def current_layer_changed(self, layer: Optional[QgsVectorLayer]) -> None:
        """
        Handle layer change event.

        Args:
            layer: New current layer (can be None)
        """
        # CRITICAL: Post-filter protection
        if self._is_within_post_filter_protection():
            if layer is None:
                logger.warning(
                    "BLOCKED layer=None during post-filter protection"
                )
                self.sync_blocked.emit("layer_none_during_protection")
                return

            if (self._saved_layer_id_before_filter and
                layer.id() != self._saved_layer_id_before_filter):
                logger.warning(
                    f"BLOCKED layer change to {layer.name()} during protection"
                )
                self.sync_blocked.emit("layer_change_during_protection")
                return

        # Normal layer change handling
        if layer is None:
            self._handle_no_layer()
            return

        if not self._layer_service.validate_and_prepare_layer(layer):
            logger.warning(f"Layer {layer.name()} failed validation")
            return

        self._current_layer_id = layer.id()
        self._synchronize_layer_widgets(layer)
        self.layer_synchronized.emit(layer)

    def _is_within_post_filter_protection(self) -> bool:
        """Check if we're within the post-filter protection window."""
        if self._filter_completed_time is None:
            return False
        elapsed = time.time() - self._filter_completed_time
        return elapsed < POST_FILTER_PROTECTION_WINDOW

    def save_current_layer_before_filter(self) -> None:
        """Save current layer ID before filter starts."""
        layer = self.dockwidget.current_layer
        if layer:
            self._saved_layer_id_before_filter = layer.id()
            logger.debug(f"Saved layer before filter: {layer.name()}")

    def mark_filter_completed(self) -> None:
        """Mark that a filter has just completed."""
        self._filter_completed_time = time.time()
        logger.debug("Filter completed, protection window started")

    def _synchronize_layer_widgets(self, layer: QgsVectorLayer) -> None:
        """Synchronize all widgets for the new layer."""
        pass

    def _reload_exploration_widgets(self, layer: QgsVectorLayer) -> None:
        """Reload exploring widgets for the layer."""
        pass
```

---

## 🔗 Dépendances

### Entrée

- MIG-020: FilteringController (coordination)
- MIG-077: LayerService (validation layer)
- MIG-084: SignalManager (gestion signaux)

### Sortie

- MIG-087: Final refactoring

---

## 📊 Métriques

| Métrique               | Avant   | Après        |
| ---------------------- | ------- | ------------ |
| Lignes dans dockwidget | ~970    | 0            |
| Nouveau fichier        | -       | < 600 lignes |
| Bug CRIT-005           | Présent | Fixé         |

---

## 🧪 Scénarios de Test

### Test 1: Normal Layer Change

```python
def test_normal_layer_change():
    """Le changement de layer doit synchroniser les widgets."""
    controller = LayerSyncController(mock_dockwidget, mock_service)
    mock_layer = Mock(id=Mock(return_value='layer123'))

    controller.current_layer_changed(mock_layer)

    assert controller._current_layer_id == 'layer123'
```

### Test 2: Block layer=None During Protection

```python
def test_block_none_during_protection():
    """layer=None doit être bloqué pendant la protection."""
    controller = LayerSyncController(mock_dockwidget, mock_service)
    controller.mark_filter_completed()  # Start protection

    controller.current_layer_changed(None)

    # Should be blocked
    assert controller._current_layer_id is not None  # Unchanged
```

### Test 3: Allow Change After Protection Expires

```python
def test_allow_after_protection():
    """Le changement doit être permis après expiration."""
    controller = LayerSyncController(mock_dockwidget, mock_service)
    controller._filter_completed_time = time.time() - 10  # 10s ago

    controller.current_layer_changed(None)

    # Should be allowed
```

---

## ⚠️ Risques

| Risque                 | Impact      | Mitigation                |
| ---------------------- | ----------- | ------------------------- |
| Régression CRIT-005    | 🔴 Critique | Tests exhaustifs          |
| Race conditions        | 🟠 Élevé    | Mutex/locks si nécessaire |
| Signaux Qt asynchrones | 🟠 Élevé    | blockSignals pattern      |

---

## 📋 Checklist Développeur

- [ ] Créer le fichier `ui/controllers/layer_sync_controller.py`
- [ ] Implémenter `LayerSyncController`
- [ ] Ajouter protection post-filtre robuste
- [ ] Ajouter logging détaillé
- [ ] Créer délégation dans dockwidget
- [ ] Créer fichier de test exhaustif
- [ ] Tester avec tous les backends (OGR, Spatialite, PostgreSQL)
- [ ] Valider que CRIT-005 reste fixé

---

_Story générée par 🏃 SM Agent (Bob) - 9 janvier 2026_

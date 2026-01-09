---
storyId: MIG-085
title: Create LayerSignalHandler
epic: 6.6 - Signal Management
phase: 6
sprint: 8
priority: P1
status: READY_FOR_DEV
effort: 1 day
assignee: null
dependsOn: [MIG-084, MIG-073]
blocks: [MIG-086, MIG-087]
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-085: Create LayerSignalHandler

## 📋 Story

**En tant que** développeur,  
**Je veux** un handler dédié aux signaux liés aux layers,  
**Afin que** les connexions/déconnexions de layers soient gérées proprement.

---

## 🎯 Objectif

Extraire les méthodes de gestion des signaux layer de `filter_mate_dockwidget.py` (lignes 9702-9758, 10326-10437) vers un handler dédié qui travaille avec `SignalManager`.

---

## ✅ Critères d'Acceptation

### Code

- [ ] `adapters/qgis/signals/layer_signal_handler.py` créé (< 200 lignes)
- [ ] Type hints sur toutes les signatures
- [ ] Docstrings Google style

### Méthodes à Implémenter

- [ ] `connect_layer_signals(layer) -> int`
- [ ] `disconnect_layer_signals(layer) -> int`
- [ ] `reconnect_layer_signals(layer) -> None`
- [ ] `is_layer_connected(layer) -> bool`
- [ ] `get_connected_layers() -> List[str]`

### Signaux Gérés

- [ ] `layer.subsetStringChanged`
- [ ] `layer.featureAdded`
- [ ] `layer.featureDeleted`
- [ ] `layer.attributeValueChanged`
- [ ] `layer.beforeEditingStarted`
- [ ] `layer.editingStopped`
- [ ] `layer.willBeDeleted`

### Intégration

- [ ] Enregistre les signaux dans `SignalManager` (MIG-084)
- [ ] Coordonne avec `LayerSyncController` (MIG-073)

### Tests

- [ ] `tests/unit/adapters/qgis/signals/test_layer_signal_handler.py` créé
- [ ] Tests pour connect/disconnect layer
- [ ] Couverture > 80%

---

## 📝 Spécifications Techniques

### Structure du Handler

```python
"""
Layer Signal Handler for FilterMate.

Manages Qt signals specific to QGIS layers.
Extracted from filter_mate_dockwidget.py (lines 9702-9758, 10326-10437).
"""

from typing import TYPE_CHECKING, Dict, Set, List, Callable
import logging
import weakref

from qgis.core import QgsVectorLayer

if TYPE_CHECKING:
    from .signal_manager import SignalManager
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class LayerSignalHandler:
    """
    Handler for layer-specific Qt signals.

    Manages the lifecycle of signal connections for vector layers:
    - Connects signals when a layer becomes current
    - Disconnects signals when layer changes or is removed
    - Tracks which layers have active connections

    Works with SignalManager for centralized tracking.
    """

    # Signals to connect for each layer
    LAYER_SIGNALS = [
        'subsetStringChanged',
        'featureAdded',
        'featureDeleted',
        'attributeValueChanged',
        'beforeEditingStarted',
        'editingStopped',
        'willBeDeleted',
    ]

    def __init__(
        self,
        dockwidget: 'FilterMateDockWidget',
        signal_manager: 'SignalManager' = None
    ) -> None:
        """
        Initialize the layer signal handler.

        Args:
            dockwidget: Reference to main dockwidget
            signal_manager: Central signal manager
        """
        self.dockwidget = dockwidget
        self._signal_manager = signal_manager
        self._connected_layers: Dict[str, weakref.ref] = {}
        self._handlers: Dict[str, Callable] = {}

        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Setup default signal handlers."""
        self._handlers = {
            'subsetStringChanged': self._on_subset_string_changed,
            'featureAdded': self._on_feature_added,
            'featureDeleted': self._on_feature_deleted,
            'attributeValueChanged': self._on_attribute_changed,
            'beforeEditingStarted': self._on_editing_started,
            'editingStopped': self._on_editing_stopped,
            'willBeDeleted': self._on_layer_will_be_deleted,
        }

    def connect_layer_signals(self, layer: QgsVectorLayer) -> int:
        """
        Connect all signals for a layer.

        Args:
            layer: Vector layer to connect

        Returns:
            Number of signals connected
        """
        if not layer or not layer.isValid():
            return 0

        layer_id = layer.id()

        # Check if already connected
        if layer_id in self._connected_layers:
            logger.debug(f"Layer {layer.name()} already connected")
            return 0

        connected = 0

        for signal_name in self.LAYER_SIGNALS:
            signal = getattr(layer, signal_name, None)
            if signal is None:
                continue

            handler = self._handlers.get(signal_name)
            if handler is None:
                continue

            try:
                signal.connect(handler)
                connected += 1

                # Also register with signal manager
                if self._signal_manager:
                    full_name = f"layer_{layer_id}_{signal_name}"
                    self._signal_manager.register(
                        full_name, signal, handler, layer
                    )

            except Exception as e:
                logger.warning(f"Failed to connect {signal_name}: {e}")

        if connected > 0:
            self._connected_layers[layer_id] = weakref.ref(layer)
            logger.debug(
                f"Connected {connected} signals for layer {layer.name()}"
            )

        return connected

    def disconnect_layer_signals(self, layer: QgsVectorLayer) -> int:
        """
        Disconnect all signals for a layer.

        Args:
            layer: Vector layer to disconnect

        Returns:
            Number of signals disconnected
        """
        if not layer:
            return 0

        layer_id = layer.id() if hasattr(layer, 'id') else str(id(layer))

        if layer_id not in self._connected_layers:
            return 0

        disconnected = 0

        for signal_name in self.LAYER_SIGNALS:
            signal = getattr(layer, signal_name, None)
            if signal is None:
                continue

            handler = self._handlers.get(signal_name)
            if handler is None:
                continue

            try:
                signal.disconnect(handler)
                disconnected += 1

                # Also unregister from signal manager
                if self._signal_manager:
                    full_name = f"layer_{layer_id}_{signal_name}"
                    self._signal_manager.unregister(full_name)

            except TypeError:
                # Signal was not connected
                pass
            except Exception as e:
                logger.warning(f"Failed to disconnect {signal_name}: {e}")

        del self._connected_layers[layer_id]
        logger.debug(
            f"Disconnected {disconnected} signals for layer"
        )

        return disconnected

    def reconnect_layer_signals(self, layer: QgsVectorLayer) -> None:
        """
        Disconnect and reconnect all signals for a layer.

        Args:
            layer: Vector layer to reconnect
        """
        self.disconnect_layer_signals(layer)
        self.connect_layer_signals(layer)

    def disconnect_all_layers(self) -> int:
        """
        Disconnect signals from all layers.

        Returns:
            Total signals disconnected
        """
        total = 0

        for layer_id in list(self._connected_layers.keys()):
            layer_ref = self._connected_layers[layer_id]
            layer = layer_ref()
            if layer:
                total += self.disconnect_layer_signals(layer)
            else:
                # Layer was garbage collected
                del self._connected_layers[layer_id]

        return total

    def is_layer_connected(self, layer: QgsVectorLayer) -> bool:
        """Check if a layer has connected signals."""
        if not layer:
            return False
        return layer.id() in self._connected_layers

    def get_connected_layers(self) -> List[str]:
        """Get list of connected layer IDs."""
        return list(self._connected_layers.keys())

    # Signal Handlers

    def _on_subset_string_changed(self) -> None:
        """Handle subset string change."""
        logger.debug("Layer subset string changed")
        # Notify controllers

    def _on_feature_added(self, fid: int) -> None:
        """Handle feature added."""
        logger.debug(f"Feature added: {fid}")

    def _on_feature_deleted(self, fid: int) -> None:
        """Handle feature deleted."""
        logger.debug(f"Feature deleted: {fid}")

    def _on_attribute_changed(self, fid: int, idx: int, value) -> None:
        """Handle attribute value change."""
        logger.debug(f"Attribute changed: feature {fid}, field {idx}")

    def _on_editing_started(self) -> None:
        """Handle editing session start."""
        logger.debug("Layer editing started")

    def _on_editing_stopped(self) -> None:
        """Handle editing session end."""
        logger.debug("Layer editing stopped")

    def _on_layer_will_be_deleted(self) -> None:
        """Handle layer about to be deleted."""
        logger.debug("Layer will be deleted")
        # Auto-disconnect will happen via weakref
```

---

## 🔗 Dépendances

### Entrée

- MIG-084: SignalManager (pour tracking)
- MIG-073: LayerSyncController (coordination)

### Sortie

- MIG-086: Migrate all signals
- MIG-087: Final refactoring

---

## 📊 Métriques

| Métrique                           | Avant       | Après        |
| ---------------------------------- | ----------- | ------------ |
| Code signaux layer dans dockwidget | ~180 lignes | 0            |
| Nouveau fichier                    | -           | < 200 lignes |
| Tracking des layers                | Aucun       | Complet      |

---

## 🧪 Scénarios de Test

### Test 1: Connect Layer Signals

```python
def test_connect_layer_signals():
    """Connecter un layer doit connecter tous les signaux."""
    handler = LayerSignalHandler(mock_dockwidget)
    mock_layer = Mock()
    mock_layer.id.return_value = 'layer123'
    mock_layer.isValid.return_value = True

    count = handler.connect_layer_signals(mock_layer)

    assert count > 0
    assert handler.is_layer_connected(mock_layer)
```

### Test 2: Disconnect Cleans Up

```python
def test_disconnect_removes_from_tracking():
    """Déconnecter doit retirer le layer du tracking."""
    handler = LayerSignalHandler(mock_dockwidget)
    mock_layer = Mock(id=Mock(return_value='layer123'))
    mock_layer.isValid.return_value = True

    handler.connect_layer_signals(mock_layer)
    handler.disconnect_layer_signals(mock_layer)

    assert not handler.is_layer_connected(mock_layer)
```

---

## 📋 Checklist Développeur

- [ ] Créer `adapters/qgis/signals/layer_signal_handler.py`
- [ ] Implémenter toutes les méthodes
- [ ] Ajouter intégration avec SignalManager
- [ ] Créer handlers pour chaque signal
- [ ] Créer fichier de test
- [ ] Tester avec différents types de layers

---

_Story générée par 🏃 SM Agent (Bob) - 9 janvier 2026_

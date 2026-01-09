---
storyId: MIG-084
title: Complete SignalManager
epic: 6.6 - Signal Management
phase: 6
sprint: 8
priority: P0
status: READY_FOR_DEV
effort: 1 day
assignee: null
dependsOn: [MIG-070, MIG-071, MIG-072, MIG-073, MIG-074]
blocks: [MIG-085, MIG-086, MIG-087]
createdAt: 2026-01-09
updatedAt: 2026-01-09
risk: HIGH
---

# MIG-084: Complete SignalManager

## 📋 Story

**En tant que** développeur,  
**Je veux** centraliser tous les signaux dans SignalManager,  
**Afin d'** éviter les fuites de connexions et les bugs de signaux.

---

## 🎯 Objectif

Compléter le `SignalManager` existant avec les méthodes extraites de `filter_mate_dockwidget.py` (lignes 419-593, 6546-6760) pour centraliser TOUS les signaux Qt du plugin.

⚠️ **RISQUE ÉLEVÉ**: Les signaux Qt sont au cœur de nombreux bugs (CRIT-005). Cette story nécessite une attention particulière.

---

## ✅ Critères d'Acceptation

### Code

- [ ] `adapters/qgis/signals/signal_manager.py` complété (< 500 lignes)
- [ ] Type hints sur toutes les signatures
- [ ] Docstrings Google style
- [ ] Logging exhaustif pour debugging

### Méthodes à Implémenter/Compléter

- [ ] `getSignal(signal_name: str) -> pyqtSignal`
- [ ] `manageSignal(action: str, signal_name: str, handler) -> bool`
- [ ] `changeSignalState(signal_name: str, enabled: bool) -> None`
- [ ] `connect_widgets_signals() -> int`
- [ ] `disconnect_widgets_signals() -> int`
- [ ] `force_reconnect_action_signals() -> None`
- [ ] `force_reconnect_exploring_signals() -> None`
- [ ] `block_all_signals() -> ContextManager`
- [ ] `is_signal_connected(signal_name: str) -> bool`
- [ ] `get_connection_count() -> int`

### Tracking des Connexions

- [ ] Chaque connexion est trackée
- [ ] Détection des connexions dupliquées
- [ ] Cleanup propre au teardown
- [ ] Warning si connexion orpheline

### Tests

- [ ] `tests/unit/adapters/qgis/signals/test_signal_manager.py` créé
- [ ] Tests pour connect/disconnect
- [ ] Tests pour block context manager
- [ ] Tests pour tracking
- [ ] Couverture > 85%

---

## 📝 Spécifications Techniques

### Structure du SignalManager

```python
"""
Signal Manager for FilterMate.

Centralized management of Qt signals to prevent connection leaks.
Extracted from filter_mate_dockwidget.py (lines 419-593, 6546-6760).
"""

from typing import TYPE_CHECKING, Callable, Dict, Set, Optional, Any
from contextlib import contextmanager
import logging
import weakref

from qgis.PyQt.QtCore import QObject, pyqtSignal

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class SignalConnection:
    """Represents a tracked signal connection."""

    def __init__(
        self,
        signal_name: str,
        signal: pyqtSignal,
        handler: Callable,
        source_widget: QObject
    ) -> None:
        self.signal_name = signal_name
        self.signal = signal
        self.handler = handler
        self.source_widget = weakref.ref(source_widget)
        self.is_connected = False
        self.connection_count = 0

    def connect(self) -> bool:
        """Connect the signal."""
        if self.is_connected:
            logger.warning(f"Signal {self.signal_name} already connected")
            return False

        try:
            self.signal.connect(self.handler)
            self.is_connected = True
            self.connection_count += 1
            logger.debug(f"Connected: {self.signal_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect {self.signal_name}: {e}")
            return False

    def disconnect(self) -> bool:
        """Disconnect the signal."""
        if not self.is_connected:
            return False

        try:
            self.signal.disconnect(self.handler)
            self.is_connected = False
            logger.debug(f"Disconnected: {self.signal_name}")
            return True
        except TypeError:
            # Signal was not connected
            self.is_connected = False
            return False
        except Exception as e:
            logger.error(f"Failed to disconnect {self.signal_name}: {e}")
            return False


class SignalManager(QObject):
    """
    Centralized manager for Qt signal connections.

    Features:
    - Track all signal connections
    - Prevent duplicate connections
    - Bulk connect/disconnect
    - Context manager for temporary blocking
    - Debug logging for signal flow

    Usage:
        manager = SignalManager(dockwidget)
        manager.register('layer_changed', layer_combo.currentIndexChanged, handler)
        manager.connect_all()

        with manager.block_all_signals():
            # Do work without triggering signals
            pass
    """

    def __init__(self, dockwidget: 'FilterMateDockWidget') -> None:
        """
        Initialize the signal manager.

        Args:
            dockwidget: Reference to main dockwidget
        """
        super().__init__()
        self.dockwidget = dockwidget
        self._connections: Dict[str, SignalConnection] = {}
        self._blocked_signals: Set[str] = set()
        self._initialized = False

    def register(
        self,
        signal_name: str,
        signal: pyqtSignal,
        handler: Callable,
        source_widget: QObject = None
    ) -> bool:
        """
        Register a signal for management.

        Args:
            signal_name: Unique name for this signal
            signal: The Qt signal to manage
            handler: Handler function
            source_widget: Widget owning the signal

        Returns:
            True if registered successfully
        """
        if signal_name in self._connections:
            logger.warning(f"Signal {signal_name} already registered")
            return False

        connection = SignalConnection(
            signal_name=signal_name,
            signal=signal,
            handler=handler,
            source_widget=source_widget or self.dockwidget
        )

        self._connections[signal_name] = connection
        logger.debug(f"Registered signal: {signal_name}")
        return True

    def unregister(self, signal_name: str) -> bool:
        """
        Unregister and disconnect a signal.

        Args:
            signal_name: Name of signal to unregister

        Returns:
            True if unregistered
        """
        if signal_name not in self._connections:
            return False

        connection = self._connections[signal_name]
        connection.disconnect()
        del self._connections[signal_name]
        return True

    def connect(self, signal_name: str) -> bool:
        """
        Connect a specific signal.

        Args:
            signal_name: Name of signal to connect

        Returns:
            True if connected
        """
        if signal_name not in self._connections:
            logger.error(f"Signal {signal_name} not registered")
            return False

        return self._connections[signal_name].connect()

    def disconnect(self, signal_name: str) -> bool:
        """
        Disconnect a specific signal.

        Args:
            signal_name: Name of signal to disconnect

        Returns:
            True if disconnected
        """
        if signal_name not in self._connections:
            return False

        return self._connections[signal_name].disconnect()

    def connect_widgets_signals(self) -> int:
        """
        Connect all registered signals.

        Returns:
            Number of signals connected
        """
        connected = 0
        for name, connection in self._connections.items():
            if connection.connect():
                connected += 1

        self._initialized = True
        logger.info(f"Connected {connected} widget signals")
        return connected

    def disconnect_widgets_signals(self) -> int:
        """
        Disconnect all registered signals.

        Returns:
            Number of signals disconnected
        """
        disconnected = 0
        for name, connection in self._connections.items():
            if connection.disconnect():
                disconnected += 1

        logger.info(f"Disconnected {disconnected} widget signals")
        return disconnected

    def force_reconnect_action_signals(self) -> None:
        """Force reconnect all action-related signals."""
        action_signals = [
            name for name in self._connections.keys()
            if 'action' in name.lower() or 'button' in name.lower()
        ]

        for name in action_signals:
            self.disconnect(name)
            self.connect(name)

        logger.debug(f"Force reconnected {len(action_signals)} action signals")

    def force_reconnect_exploring_signals(self) -> None:
        """Force reconnect all exploring-related signals."""
        exploring_signals = [
            name for name in self._connections.keys()
            if 'exploring' in name.lower() or 'groupbox' in name.lower()
        ]

        for name in exploring_signals:
            self.disconnect(name)
            self.connect(name)

        logger.debug(f"Force reconnected {len(exploring_signals)} exploring signals")

    @contextmanager
    def block_all_signals(self):
        """
        Context manager to temporarily block all signals.

        Usage:
            with signal_manager.block_all_signals():
                # Do work that might trigger signals
                pass
        """
        # Store current states and block
        blocked_widgets = []
        try:
            for name, connection in self._connections.items():
                widget = connection.source_widget()
                if widget and hasattr(widget, 'blockSignals'):
                    was_blocked = widget.signalsBlocked()
                    widget.blockSignals(True)
                    blocked_widgets.append((widget, was_blocked))

            logger.debug(f"Blocked signals on {len(blocked_widgets)} widgets")
            yield

        finally:
            # Restore previous states
            for widget, was_blocked in blocked_widgets:
                if widget:
                    widget.blockSignals(was_blocked)

            logger.debug("Restored signal states")

    def is_signal_connected(self, signal_name: str) -> bool:
        """Check if a signal is currently connected."""
        if signal_name not in self._connections:
            return False
        return self._connections[signal_name].is_connected

    def get_connection_count(self) -> int:
        """Get total number of active connections."""
        return sum(
            1 for c in self._connections.values()
            if c.is_connected
        )

    def get_signal_stats(self) -> Dict[str, Any]:
        """Get statistics about signal connections."""
        return {
            'total_registered': len(self._connections),
            'total_connected': self.get_connection_count(),
            'signals': {
                name: {
                    'connected': c.is_connected,
                    'connection_count': c.connection_count,
                }
                for name, c in self._connections.items()
            }
        }

    def teardown(self) -> None:
        """Cleanup all connections."""
        self.disconnect_widgets_signals()
        self._connections.clear()
        self._initialized = False
        logger.info("SignalManager teardown complete")
```

---

## 🔗 Dépendances

### Entrée

- MIG-070→074: Controllers (utilisent SignalManager)

### Sortie

- MIG-085: LayerSignalHandler
- MIG-086: Migrate all signals
- MIG-087: Final refactoring

---

## 📊 Métriques

| Métrique             | Avant     | Après      |
| -------------------- | --------- | ---------- |
| Signaux éparpillés   | ~50       | 0          |
| Tracking             | Aucun     | Complet    |
| Fuites de connexions | Possibles | Impossible |

---

## 🧪 Scénarios de Test

### Test 1: Register and Connect Signal

```python
def test_register_and_connect():
    """Un signal enregistré doit pouvoir être connecté."""
    manager = SignalManager(mock_dockwidget)
    mock_signal = Mock()

    manager.register('test_signal', mock_signal, lambda: None)
    result = manager.connect('test_signal')

    assert result is True
    assert manager.is_signal_connected('test_signal') is True
```

### Test 2: Block All Signals Context Manager

```python
def test_block_all_signals():
    """Le context manager doit bloquer puis restaurer les signaux."""
    manager = SignalManager(mock_dockwidget)
    mock_widget = Mock()
    mock_widget.signalsBlocked.return_value = False

    manager.register('test', mock_widget.signal, lambda: None, mock_widget)

    with manager.block_all_signals():
        mock_widget.blockSignals.assert_called_with(True)

    # After context, should restore
    mock_widget.blockSignals.assert_called_with(False)
```

### Test 3: Prevent Duplicate Connections

```python
def test_prevent_duplicate_connections():
    """Connecter deux fois doit retourner False."""
    manager = SignalManager(mock_dockwidget)
    manager.register('test', Mock(), lambda: None)

    manager.connect('test')
    result = manager.connect('test')  # Second time

    assert result is False
```

---

## ⚠️ Risques et Mitigations

| Risque               | Impact      | Mitigation           |
| -------------------- | ----------- | -------------------- |
| Régression signaux   | 🔴 Critique | Tests exhaustifs     |
| Performance tracking | 🟡 Moyen    | weakref pour widgets |
| Thread safety        | 🟠 Élevé    | Mutex si nécessaire  |

---

## 📋 Checklist Développeur

- [ ] Compléter `adapters/qgis/signals/signal_manager.py`
- [ ] Implémenter toutes les méthodes
- [ ] Ajouter tracking des connexions
- [ ] Ajouter context manager block_all
- [ ] Créer fichier de test exhaustif
- [ ] Tester avec le bug CRIT-005 en tête
- [ ] Valider pas de régression

---

_Story générée par 🏃 SM Agent (Bob) - 9 janvier 2026_

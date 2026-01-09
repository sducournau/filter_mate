"""
Tests for LayerSignalHandler.

Story: MIG-085
Phase: 6 - God Class DockWidget Migration
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add plugin path for imports
plugin_path = Path(__file__).parents[5]
if str(plugin_path) not in sys.path:
    sys.path.insert(0, str(plugin_path))


# ─────────────────────────────────────────────────────────────────
# Mock Signal and Layer Classes
# ─────────────────────────────────────────────────────────────────

class MockSignal:
    """Mock Qt signal for testing."""
    
    def __init__(self, name: str = "signal"):
        self.name = name
        self._connections = []
        self.connect_count = 0
        self.disconnect_count = 0
    
    def connect(self, handler):
        if handler not in self._connections:
            self._connections.append(handler)
            self.connect_count += 1
    
    def disconnect(self, handler=None):
        if handler is None:
            self._connections.clear()
        elif handler in self._connections:
            self._connections.remove(handler)
        self.disconnect_count += 1
    
    def emit(self, *args, **kwargs):
        for handler in self._connections:
            handler(*args, **kwargs)
    
    @property
    def is_connected(self):
        return len(self._connections) > 0


class MockVectorLayer:
    """Mock QgsVectorLayer for testing."""
    
    def __init__(self, layer_id: str = "layer_001", name: str = "TestLayer"):
        self._id = layer_id
        self._name = name
        self._valid = True
        
        # Create mock signals
        self.subsetStringChanged = MockSignal("subsetStringChanged")
        self.featureAdded = MockSignal("featureAdded")
        self.featureDeleted = MockSignal("featureDeleted")
        self.attributeValueChanged = MockSignal("attributeValueChanged")
        self.beforeEditingStarted = MockSignal("beforeEditingStarted")
        self.editingStopped = MockSignal("editingStopped")
        self.willBeDeleted = MockSignal("willBeDeleted")
    
    def id(self):
        return self._id
    
    def name(self):
        return self._name
    
    def isValid(self):
        return self._valid


class MockSignalManager:
    """Mock SignalManager for testing."""
    
    def __init__(self):
        self._connections = {}
        self._counter = 0
    
    def connect(self, sender, signal_name, receiver, context=None):
        self._counter += 1
        conn_id = f"sig_{self._counter:05d}"
        self._connections[conn_id] = {
            'sender': sender,
            'signal_name': signal_name,
            'receiver': receiver,
            'context': context
        }
        # Actually connect
        signal = getattr(sender, signal_name, None)
        if signal:
            signal.connect(receiver)
        return conn_id
    
    def disconnect(self, connection_id):
        if connection_id in self._connections:
            conn = self._connections[connection_id]
            sender = conn['sender']
            signal = getattr(sender, conn['signal_name'], None)
            if signal:
                try:
                    signal.disconnect(conn['receiver'])
                except:
                    pass
            del self._connections[connection_id]
            return True
        return False
    
    def get_connection_count(self):
        return len(self._connections)


# ─────────────────────────────────────────────────────────────────
# Import LayerSignalHandler
# ─────────────────────────────────────────────────────────────────

from adapters.qgis.signals.layer_signal_handler import LayerSignalHandler


# ─────────────────────────────────────────────────────────────────
# Test Fixtures
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def layer():
    """Create a mock layer."""
    return MockVectorLayer()


@pytest.fixture
def signal_manager():
    """Create a mock signal manager."""
    return MockSignalManager()


@pytest.fixture
def handler(signal_manager):
    """Create a LayerSignalHandler with signal manager."""
    return LayerSignalHandler(signal_manager=signal_manager)


@pytest.fixture
def handler_no_manager():
    """Create a LayerSignalHandler without signal manager."""
    return LayerSignalHandler()


# ─────────────────────────────────────────────────────────────────
# Test Initialization
# ─────────────────────────────────────────────────────────────────

class TestLayerSignalHandlerInit:
    """Tests for LayerSignalHandler initialization."""
    
    def test_init_default(self):
        """Test default initialization."""
        handler = LayerSignalHandler()
        
        assert len(handler) == 0
        assert handler._signal_manager is None
    
    def test_init_with_signal_manager(self, signal_manager):
        """Test initialization with signal manager."""
        handler = LayerSignalHandler(signal_manager=signal_manager)
        
        assert handler._signal_manager is signal_manager
    
    def test_init_with_custom_handlers(self):
        """Test initialization with custom handlers."""
        custom_handler = Mock()
        
        handler = LayerSignalHandler(
            on_subset_changed=custom_handler
        )
        
        assert handler._handlers['subsetStringChanged'] is custom_handler
    
    def test_repr(self):
        """Test string representation."""
        handler = LayerSignalHandler()
        
        assert "LayerSignalHandler" in repr(handler)
        assert "0 layers" in repr(handler)


# ─────────────────────────────────────────────────────────────────
# Test Connect/Disconnect
# ─────────────────────────────────────────────────────────────────

class TestLayerSignalHandlerConnect:
    """Tests for connection methods."""
    
    def test_connect_layer_signals(self, handler, layer):
        """Test connecting layer signals."""
        count = handler.connect_layer_signals(layer)
        
        assert count == 7  # All 7 signals
        assert len(handler) == 1
        assert handler.is_layer_connected(layer)
    
    def test_connect_layer_signals_no_manager(self, handler_no_manager, layer):
        """Test connecting without signal manager."""
        count = handler_no_manager.connect_layer_signals(layer)
        
        assert count == 7
        assert layer.subsetStringChanged.is_connected
    
    def test_connect_already_connected_layer(self, handler, layer):
        """Test connecting already connected layer."""
        handler.connect_layer_signals(layer)
        count = handler.connect_layer_signals(layer)
        
        assert count == 0  # Already connected
    
    def test_connect_none_layer(self, handler):
        """Test connecting None layer."""
        count = handler.connect_layer_signals(None)
        
        assert count == 0
    
    def test_connect_invalid_layer(self, handler):
        """Test connecting invalid layer."""
        layer = MockVectorLayer()
        layer._valid = False
        
        count = handler.connect_layer_signals(layer)
        
        assert count == 0
    
    def test_disconnect_layer_signals(self, handler, layer):
        """Test disconnecting layer signals."""
        handler.connect_layer_signals(layer)
        count = handler.disconnect_layer_signals(layer)
        
        assert count == 7
        assert len(handler) == 0
        assert not handler.is_layer_connected(layer)
    
    def test_disconnect_not_connected_layer(self, handler, layer):
        """Test disconnecting non-connected layer."""
        count = handler.disconnect_layer_signals(layer)
        
        assert count == 0
    
    def test_disconnect_none_layer(self, handler):
        """Test disconnecting None layer."""
        count = handler.disconnect_layer_signals(None)
        
        assert count == 0
    
    def test_reconnect_layer_signals(self, handler, layer):
        """Test reconnecting layer signals."""
        handler.connect_layer_signals(layer)
        
        handler.reconnect_layer_signals(layer)
        
        assert handler.is_layer_connected(layer)
        # Should have disconnected and reconnected
        assert layer.subsetStringChanged.disconnect_count >= 1
    
    def test_disconnect_all(self, handler):
        """Test disconnecting all layers."""
        layer1 = MockVectorLayer("layer_001", "Layer1")
        layer2 = MockVectorLayer("layer_002", "Layer2")
        
        handler.connect_layer_signals(layer1)
        handler.connect_layer_signals(layer2)
        
        assert len(handler) == 2
        
        total = handler.disconnect_all()
        
        assert total == 14  # 7 signals * 2 layers
        assert len(handler) == 0


# ─────────────────────────────────────────────────────────────────
# Test Query Methods
# ─────────────────────────────────────────────────────────────────

class TestLayerSignalHandlerQuery:
    """Tests for query methods."""
    
    def test_is_layer_connected(self, handler, layer):
        """Test is_layer_connected method."""
        assert not handler.is_layer_connected(layer)
        
        handler.connect_layer_signals(layer)
        
        assert handler.is_layer_connected(layer)
    
    def test_is_layer_connected_none(self, handler):
        """Test is_layer_connected with None."""
        assert not handler.is_layer_connected(None)
    
    def test_get_connected_layers(self, handler):
        """Test getting connected layer IDs."""
        layer1 = MockVectorLayer("layer_001", "Layer1")
        layer2 = MockVectorLayer("layer_002", "Layer2")
        
        handler.connect_layer_signals(layer1)
        handler.connect_layer_signals(layer2)
        
        layers = handler.get_connected_layers()
        
        assert len(layers) == 2
        assert "layer_001" in layers
        assert "layer_002" in layers
    
    def test_get_connected_layer_count(self, handler):
        """Test getting connected layer count."""
        assert handler.get_connected_layer_count() == 0
        
        layer = MockVectorLayer()
        handler.connect_layer_signals(layer)
        
        assert handler.get_connected_layer_count() == 1


# ─────────────────────────────────────────────────────────────────
# Test Custom Handlers
# ─────────────────────────────────────────────────────────────────

class TestLayerSignalHandlerCustom:
    """Tests for custom handler functionality."""
    
    def test_set_handler(self, handler):
        """Test setting a custom handler."""
        custom = Mock()
        
        handler.set_handler('subsetStringChanged', custom)
        
        assert handler._handlers['subsetStringChanged'] is custom
    
    def test_set_handler_invalid_signal(self, handler):
        """Test setting handler for invalid signal."""
        custom = Mock()
        
        handler.set_handler('invalidSignal', custom)
        
        assert 'invalidSignal' not in handler._handlers
    
    def test_custom_handler_receives_signal(self):
        """Test that custom handler receives signals."""
        received = []
        
        def custom_handler():
            received.append('called')
        
        handler = LayerSignalHandler(
            on_subset_changed=custom_handler
        )
        layer = MockVectorLayer()
        
        handler.connect_layer_signals(layer)
        
        # Emit signal
        layer.subsetStringChanged.emit()
        
        assert received == ['called']


# ─────────────────────────────────────────────────────────────────
# Test Cleanup Methods
# ─────────────────────────────────────────────────────────────────

class TestLayerSignalHandlerCleanup:
    """Tests for cleanup methods."""
    
    def test_prune_dead_layers(self, handler, signal_manager):
        """Test pruning dead layer connections."""
        layer = MockVectorLayer()
        handler.connect_layer_signals(layer)
        
        # Simulate layer deletion by clearing weakref
        layer_id = layer.id()
        handler._connected_layers[layer_id] = lambda: None
        
        count = handler.prune_dead_layers()
        
        assert count == 1
        assert len(handler) == 0
    
    def test_cleanup(self, handler, layer):
        """Test full cleanup."""
        handler.connect_layer_signals(layer)
        
        handler.cleanup()
        
        assert len(handler) == 0
        assert not handler.is_layer_connected(layer)


# ─────────────────────────────────────────────────────────────────
# Test Signal Manager Integration
# ─────────────────────────────────────────────────────────────────

class TestLayerSignalHandlerIntegration:
    """Tests for signal manager integration."""
    
    def test_signals_registered_with_manager(self, handler, signal_manager, layer):
        """Test that signals are registered with signal manager."""
        handler.connect_layer_signals(layer)
        
        assert signal_manager.get_connection_count() == 7
    
    def test_signals_unregistered_from_manager(self, handler, signal_manager, layer):
        """Test that signals are unregistered from manager."""
        handler.connect_layer_signals(layer)
        handler.disconnect_layer_signals(layer)
        
        assert signal_manager.get_connection_count() == 0
    
    def test_connection_ids_tracked(self, handler, signal_manager, layer):
        """Test that connection IDs are tracked."""
        handler.connect_layer_signals(layer)
        
        layer_id = layer.id()
        assert layer_id in handler._connection_ids
        assert len(handler._connection_ids[layer_id]) == 7


# ─────────────────────────────────────────────────────────────────
# Test Multiple Layers
# ─────────────────────────────────────────────────────────────────

class TestLayerSignalHandlerMultipleLayers:
    """Tests for handling multiple layers."""
    
    def test_multiple_layers_independent(self, handler):
        """Test that multiple layers are handled independently."""
        layer1 = MockVectorLayer("layer_001", "Layer1")
        layer2 = MockVectorLayer("layer_002", "Layer2")
        
        handler.connect_layer_signals(layer1)
        handler.connect_layer_signals(layer2)
        
        assert len(handler) == 2
        
        handler.disconnect_layer_signals(layer1)
        
        assert len(handler) == 1
        assert handler.is_layer_connected(layer2)
        assert not handler.is_layer_connected(layer1)
    
    def test_each_layer_gets_own_handlers(self, handler):
        """Test that each layer gets separate handler connections."""
        layer1 = MockVectorLayer("layer_001", "Layer1")
        layer2 = MockVectorLayer("layer_002", "Layer2")
        
        handler.connect_layer_signals(layer1)
        handler.connect_layer_signals(layer2)
        
        # Emit signal on layer1 only
        layer1.subsetStringChanged.emit()
        
        # Layer2's signal should not have emitted
        assert layer1.subsetStringChanged.is_connected
        assert layer2.subsetStringChanged.is_connected


# ─────────────────────────────────────────────────────────────────
# Test Edge Cases
# ─────────────────────────────────────────────────────────────────

class TestLayerSignalHandlerEdgeCases:
    """Tests for edge cases."""
    
    def test_layer_without_some_signals(self, handler):
        """Test layer that doesn't have all signals."""
        layer = MockVectorLayer()
        delattr(layer, 'featureAdded')  # Remove one signal
        
        count = handler.connect_layer_signals(layer)
        
        assert count == 6  # Only 6 signals connected
    
    def test_len(self, handler):
        """Test __len__ method."""
        assert len(handler) == 0
        
        layer = MockVectorLayer()
        handler.connect_layer_signals(layer)
        
        assert len(handler) == 1
    
    def test_concurrent_connect_disconnect(self, handler):
        """Test rapid connect/disconnect cycles."""
        layer = MockVectorLayer()
        
        for _ in range(10):
            handler.connect_layer_signals(layer)
            handler.disconnect_layer_signals(layer)
        
        assert len(handler) == 0

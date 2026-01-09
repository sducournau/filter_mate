"""
Tests for SignalManager.

Story: MIG-084
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
# Mock Signal Classes
# ─────────────────────────────────────────────────────────────────

class MockSignal:
    """Mock Qt signal for testing."""
    
    def __init__(self, name: str = "signal"):
        self.name = name
        self._connections = []
        self.connect_count = 0
        self.disconnect_count = 0
    
    def connect(self, handler):
        """Connect a handler to the signal."""
        if handler not in self._connections:
            self._connections.append(handler)
            self.connect_count += 1
    
    def disconnect(self, handler=None):
        """Disconnect a handler from the signal."""
        if handler is None:
            self._connections.clear()
        elif handler in self._connections:
            self._connections.remove(handler)
        self.disconnect_count += 1
    
    def emit(self, *args, **kwargs):
        """Emit the signal to all handlers."""
        for handler in self._connections:
            handler(*args, **kwargs)
    
    @property
    def is_connected(self):
        return len(self._connections) > 0


class MockSender:
    """Mock sender object with signals."""
    
    def __init__(self):
        self.clicked = MockSignal("clicked")
        self.valueChanged = MockSignal("valueChanged")
        self.textChanged = MockSignal("textChanged")
        self.currentIndexChanged = MockSignal("currentIndexChanged")


# ─────────────────────────────────────────────────────────────────
# Import SignalManager
# ─────────────────────────────────────────────────────────────────

from adapters.qgis.signals.signal_manager import SignalManager, SignalConnection


# ─────────────────────────────────────────────────────────────────
# Test Fixtures
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def signal_manager():
    """Create a SignalManager instance."""
    return SignalManager(debug=True)


@pytest.fixture
def sender():
    """Create a mock sender object."""
    return MockSender()


@pytest.fixture
def handler():
    """Create a mock handler function."""
    return Mock()


# ─────────────────────────────────────────────────────────────────
# Test SignalConnection
# ─────────────────────────────────────────────────────────────────

class TestSignalConnection:
    """Tests for SignalConnection dataclass."""
    
    def test_init(self, sender, handler):
        """Test SignalConnection initialization."""
        from weakref import ref
        
        conn = SignalConnection(
            id="sig_00001",
            sender_ref=ref(sender),
            signal_name="clicked",
            receiver=handler,
            context="test"
        )
        
        assert conn.id == "sig_00001"
        assert conn.signal_name == "clicked"
        assert conn.receiver is handler
        assert conn.context == "test"
    
    def test_sender_property(self, sender, handler):
        """Test sender property returns the sender."""
        from weakref import ref
        
        conn = SignalConnection(
            id="sig_00001",
            sender_ref=ref(sender),
            signal_name="clicked",
            receiver=handler
        )
        
        assert conn.sender is sender
    
    def test_sender_property_none_ref(self, handler):
        """Test sender property with None reference."""
        conn = SignalConnection(
            id="sig_00001",
            sender_ref=None,
            signal_name="clicked",
            receiver=handler
        )
        
        assert conn.sender is None


# ─────────────────────────────────────────────────────────────────
# Test SignalManager Initialization
# ─────────────────────────────────────────────────────────────────

class TestSignalManagerInit:
    """Tests for SignalManager initialization."""
    
    def test_init_default(self):
        """Test default initialization."""
        manager = SignalManager()
        
        assert len(manager) == 0
        assert manager._debug is False
    
    def test_init_debug(self):
        """Test initialization with debug enabled."""
        manager = SignalManager(debug=True)
        
        assert manager._debug is True
    
    def test_repr(self, signal_manager):
        """Test string representation."""
        assert "SignalManager" in repr(signal_manager)
        assert "0 connections" in repr(signal_manager)


# ─────────────────────────────────────────────────────────────────
# Test Connect/Disconnect
# ─────────────────────────────────────────────────────────────────

class TestSignalManagerConnect:
    """Tests for connection methods."""
    
    def test_connect(self, signal_manager, sender, handler):
        """Test basic connect."""
        conn_id = signal_manager.connect(
            sender=sender,
            signal_name="clicked",
            receiver=handler
        )
        
        assert conn_id.startswith("sig_")
        assert len(signal_manager) == 1
        assert sender.clicked.is_connected
    
    def test_connect_with_context(self, signal_manager, sender, handler):
        """Test connect with context."""
        conn_id = signal_manager.connect(
            sender=sender,
            signal_name="clicked",
            receiver=handler,
            context="actions"
        )
        
        assert conn_id in signal_manager.get_connections_by_context("actions")
    
    def test_connect_invalid_signal_raises(self, signal_manager, sender, handler):
        """Test connect with invalid signal raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            signal_manager.connect(
                sender=sender,
                signal_name="nonexistent",
                receiver=handler
            )
    
    def test_disconnect_by_id(self, signal_manager, sender, handler):
        """Test disconnect by connection ID."""
        conn_id = signal_manager.connect(
            sender=sender,
            signal_name="clicked",
            receiver=handler
        )
        
        result = signal_manager.disconnect(conn_id)
        
        assert result is True
        assert len(signal_manager) == 0
    
    def test_disconnect_nonexistent(self, signal_manager):
        """Test disconnect with nonexistent ID returns False."""
        result = signal_manager.disconnect("sig_99999")
        
        assert result is False
    
    def test_disconnect_by_sender(self, signal_manager, sender, handler):
        """Test disconnect all signals from a sender."""
        signal_manager.connect(sender, "clicked", handler)
        signal_manager.connect(sender, "valueChanged", handler)
        
        count = signal_manager.disconnect_by_sender(sender)
        
        assert count == 2
        assert len(signal_manager) == 0
    
    def test_disconnect_by_context(self, signal_manager, sender, handler):
        """Test disconnect by context."""
        signal_manager.connect(sender, "clicked", handler, context="ui")
        signal_manager.connect(sender, "valueChanged", handler, context="data")
        
        count = signal_manager.disconnect_by_context("ui")
        
        assert count == 1
        assert len(signal_manager) == 1
    
    def test_disconnect_all(self, signal_manager, sender, handler):
        """Test disconnect all signals."""
        signal_manager.connect(sender, "clicked", handler)
        signal_manager.connect(sender, "valueChanged", handler)
        signal_manager.connect(sender, "textChanged", handler)
        
        count = signal_manager.disconnect_all()
        
        assert count == 3
        assert len(signal_manager) == 0


# ─────────────────────────────────────────────────────────────────
# Test Block/Unblock
# ─────────────────────────────────────────────────────────────────

class TestSignalManagerBlock:
    """Tests for blocking methods."""
    
    def test_block_context(self, signal_manager, sender, handler):
        """Test blocking a context."""
        signal_manager.connect(sender, "clicked", handler, context="ui")
        
        signal_manager.block_context("ui")
        
        assert signal_manager.is_context_blocked("ui")
    
    def test_unblock_context(self, signal_manager, sender, handler):
        """Test unblocking a context."""
        signal_manager.connect(sender, "clicked", handler, context="ui")
        signal_manager.block_context("ui")
        
        signal_manager.unblock_context("ui")
        
        assert not signal_manager.is_context_blocked("ui")
    
    def test_block_all_signals_context_manager(self, signal_manager, sender, handler):
        """Test block_all_signals context manager."""
        signal_manager.connect(sender, "clicked", handler)
        
        # Verify connected
        assert sender.clicked.is_connected
        
        with signal_manager.block_all_signals():
            # Signals should be disconnected inside context
            assert not sender.clicked.is_connected
        
        # Signals should be reconnected after context
        assert sender.clicked.is_connected
    
    def test_block_context_signals_context_manager(
        self, signal_manager, sender, handler
    ):
        """Test block_context_signals context manager."""
        signal_manager.connect(sender, "clicked", handler, context="ui")
        signal_manager.connect(sender, "valueChanged", handler, context="data")
        
        with signal_manager.block_context_signals("ui"):
            assert signal_manager.is_context_blocked("ui")
            assert not signal_manager.is_context_blocked("data")
        
        assert not signal_manager.is_context_blocked("ui")


# ─────────────────────────────────────────────────────────────────
# Test Force Reconnect
# ─────────────────────────────────────────────────────────────────

class TestSignalManagerReconnect:
    """Tests for force reconnect methods."""
    
    def test_force_reconnect_context(self, signal_manager, sender, handler):
        """Test force reconnecting a context."""
        signal_manager.connect(sender, "clicked", handler, context="actions")
        
        count = signal_manager.force_reconnect_context("actions")
        
        assert count == 1
        assert sender.clicked.disconnect_count >= 1
        assert sender.clicked.connect_count >= 2  # Initial + reconnect
    
    def test_force_reconnect_action_signals(self, signal_manager, sender, handler):
        """Test force reconnecting action signals."""
        signal_manager.connect(sender, "clicked", handler, context="actions")
        
        count = signal_manager.force_reconnect_action_signals()
        
        assert count == 1
    
    def test_force_reconnect_exploring_signals(self, signal_manager, sender, handler):
        """Test force reconnecting exploring signals."""
        signal_manager.connect(sender, "valueChanged", handler, context="exploring")
        
        count = signal_manager.force_reconnect_exploring_signals()
        
        assert count == 1
    
    def test_force_reconnect_empty_context(self, signal_manager):
        """Test force reconnecting empty context."""
        count = signal_manager.force_reconnect_context("nonexistent")
        
        assert count == 0


# ─────────────────────────────────────────────────────────────────
# Test Query Methods
# ─────────────────────────────────────────────────────────────────

class TestSignalManagerQuery:
    """Tests for query methods."""
    
    def test_get_connection_count(self, signal_manager, sender, handler):
        """Test getting connection count."""
        assert signal_manager.get_connection_count() == 0
        
        signal_manager.connect(sender, "clicked", handler)
        signal_manager.connect(sender, "valueChanged", handler)
        
        assert signal_manager.get_connection_count() == 2
    
    def test_get_connections_by_context(self, signal_manager, sender, handler):
        """Test getting connections by context."""
        signal_manager.connect(sender, "clicked", handler, context="ui")
        signal_manager.connect(sender, "valueChanged", handler, context="ui")
        signal_manager.connect(sender, "textChanged", handler, context="data")
        
        ui_connections = signal_manager.get_connections_by_context("ui")
        
        assert len(ui_connections) == 2
    
    def test_is_connected(self, signal_manager, sender, handler):
        """Test is_connected method."""
        conn_id = signal_manager.connect(sender, "clicked", handler)
        
        assert signal_manager.is_connected(conn_id) is True
        
        signal_manager.disconnect(conn_id)
        
        assert signal_manager.is_connected(conn_id) is False
    
    def test_is_signal_connected_by_name(self, signal_manager, sender, handler):
        """Test is_signal_connected_by_name method."""
        assert signal_manager.is_signal_connected_by_name(sender, "clicked") is False
        
        signal_manager.connect(sender, "clicked", handler)
        
        assert signal_manager.is_signal_connected_by_name(sender, "clicked") is True
        assert signal_manager.is_signal_connected_by_name(sender, "valueChanged") is False
    
    def test_get_connections_summary(self, signal_manager, sender, handler):
        """Test getting connections summary."""
        signal_manager.connect(sender, "clicked", handler, context="ui")
        signal_manager.connect(sender, "valueChanged", handler, context="data")
        
        summary = signal_manager.get_connections_summary()
        
        assert "SignalManager" in summary
        assert "2 active connections" in summary
        assert "[ui]" in summary
        assert "[data]" in summary


# ─────────────────────────────────────────────────────────────────
# Test Cleanup Methods
# ─────────────────────────────────────────────────────────────────

class TestSignalManagerCleanup:
    """Tests for cleanup methods."""
    
    def test_prune_dead_connections(self, signal_manager, handler):
        """Test pruning dead connections."""
        sender = MockSender()
        signal_manager.connect(sender, "clicked", handler)
        
        # Simulate sender deletion by clearing weakref
        for conn in signal_manager._connections.values():
            conn.sender_ref = lambda: None
        
        count = signal_manager.prune_dead_connections()
        
        assert count == 1
        assert len(signal_manager) == 0
    
    def test_cleanup(self, signal_manager, sender, handler):
        """Test full cleanup."""
        signal_manager.connect(sender, "clicked", handler, context="ui")
        signal_manager.block_context("ui")
        
        signal_manager.cleanup()
        
        assert len(signal_manager) == 0
        assert not signal_manager.is_context_blocked("ui")


# ─────────────────────────────────────────────────────────────────
# Test Edge Cases
# ─────────────────────────────────────────────────────────────────

class TestSignalManagerEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_multiple_handlers_same_signal(self, signal_manager, sender):
        """Test multiple handlers on same signal."""
        handler1 = Mock()
        handler2 = Mock()
        
        id1 = signal_manager.connect(sender, "clicked", handler1)
        id2 = signal_manager.connect(sender, "clicked", handler2)
        
        assert len(signal_manager) == 2
        assert id1 != id2
    
    def test_disconnect_during_blocked_context(self, signal_manager, sender, handler):
        """Test disconnecting while context is blocked."""
        conn_id = signal_manager.connect(sender, "clicked", handler, context="ui")
        signal_manager.block_context("ui")
        
        # Should still disconnect from tracking
        result = signal_manager.disconnect(conn_id)
        
        assert result is True
        assert len(signal_manager) == 0
    
    def test_block_all_with_exception(self, signal_manager, sender, handler):
        """Test block_all_signals properly restores on exception."""
        signal_manager.connect(sender, "clicked", handler)
        
        try:
            with signal_manager.block_all_signals():
                raise ValueError("Test error")
        except ValueError:
            pass
        
        # Signals should still be reconnected
        assert sender.clicked.is_connected
    
    def test_len(self, signal_manager, sender, handler):
        """Test __len__ method."""
        assert len(signal_manager) == 0
        
        signal_manager.connect(sender, "clicked", handler)
        signal_manager.connect(sender, "valueChanged", handler)
        
        assert len(signal_manager) == 2


# ─────────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────────

class TestSignalManagerIntegration:
    """Integration tests for SignalManager."""
    
    def test_full_workflow(self, signal_manager):
        """Test complete workflow."""
        sender1 = MockSender()
        sender2 = MockSender()
        handler1 = Mock()
        handler2 = Mock()
        
        # Connect signals
        id1 = signal_manager.connect(sender1, "clicked", handler1, context="ui")
        id2 = signal_manager.connect(sender1, "valueChanged", handler2, context="data")
        id3 = signal_manager.connect(sender2, "clicked", handler1, context="ui")
        
        assert len(signal_manager) == 3
        
        # Block UI context
        with signal_manager.block_context_signals("ui"):
            assert signal_manager.is_context_blocked("ui")
        
        # Force reconnect
        signal_manager.force_reconnect_context("ui")
        
        # Disconnect by context
        signal_manager.disconnect_by_context("data")
        assert len(signal_manager) == 2
        
        # Cleanup
        signal_manager.cleanup()
        assert len(signal_manager) == 0
    
    def test_signal_emission_after_connect(self, signal_manager, sender):
        """Test that signals work after connecting through manager."""
        received = []
        
        def handler(value):
            received.append(value)
        
        signal_manager.connect(sender, "valueChanged", handler)
        
        # Emit signal
        sender.valueChanged.emit(42)
        
        assert received == [42]
    
    def test_no_emission_after_disconnect(self, signal_manager, sender):
        """Test that signals don't emit after disconnecting."""
        received = []
        
        def handler(value):
            received.append(value)
        
        conn_id = signal_manager.connect(sender, "valueChanged", handler)
        signal_manager.disconnect(conn_id)
        
        # Emit signal - should not be received
        sender.valueChanged.emit(42)
        
        assert received == []

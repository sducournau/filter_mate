"""
Unit tests for BaseController.

Tests the abstract base controller class that all tab controllers inherit from.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch


class ConcreteController:
    """
    Concrete implementation of BaseController for testing.
    
    We import and inherit inside to avoid QGIS import issues in tests.
    """
    pass


def create_concrete_controller_class():
    """Create a concrete controller class for testing."""
    from ui.controllers.base_controller import BaseController
    
    class TestableController(BaseController):
        """Concrete implementation for testing."""
        
        def __init__(self, dockwidget, filter_service=None, signal_manager=None):
            super().__init__(dockwidget, filter_service, signal_manager)
            self.setup_called = False
            self.teardown_called = False
        
        def setup(self) -> None:
            """Test implementation of setup."""
            self.setup_called = True
        
        def teardown(self) -> None:
            """Test implementation of teardown."""
            self.teardown_called = True
    
    return TestableController


class TestBaseControllerInitialization:
    """Tests for controller initialization."""
    
    def test_controller_initializes_with_required_dependencies(self):
        """Test controller initializes with dockwidget."""
        TestableController = create_concrete_controller_class()
        
        dockwidget = Mock()
        controller = TestableController(dockwidget)
        
        assert controller.dockwidget is dockwidget
        assert controller.filter_service is None
        assert controller.signal_manager is None
        assert not controller.is_active
    
    def test_controller_initializes_with_all_dependencies(self):
        """Test controller initializes with all optional dependencies."""
        TestableController = create_concrete_controller_class()
        
        dockwidget = Mock()
        filter_service = Mock()
        signal_manager = Mock()
        
        controller = TestableController(
            dockwidget=dockwidget,
            filter_service=filter_service,
            signal_manager=signal_manager
        )
        
        assert controller.dockwidget is dockwidget
        assert controller.filter_service is filter_service
        assert controller.signal_manager is signal_manager
    
    def test_controller_starts_inactive(self):
        """Test controller starts in inactive state."""
        TestableController = create_concrete_controller_class()
        
        controller = TestableController(Mock())
        
        assert controller.is_active is False
    
    def test_controller_starts_with_empty_connections(self):
        """Test controller starts with no signal connections."""
        TestableController = create_concrete_controller_class()
        
        controller = TestableController(Mock())
        
        assert len(controller._connection_ids) == 0


class TestTabActivationState:
    """Tests for tab activation/deactivation."""
    
    def test_on_tab_activated_sets_active_true(self):
        """Test tab activation updates state."""
        TestableController = create_concrete_controller_class()
        
        controller = TestableController(Mock())
        assert not controller.is_active
        
        controller.on_tab_activated()
        
        assert controller.is_active is True
    
    def test_on_tab_deactivated_sets_active_false(self):
        """Test tab deactivation updates state."""
        TestableController = create_concrete_controller_class()
        
        controller = TestableController(Mock())
        controller.on_tab_activated()
        assert controller.is_active
        
        controller.on_tab_deactivated()
        
        assert controller.is_active is False
    
    def test_tab_activation_cycle(self):
        """Test complete activation/deactivation cycle."""
        TestableController = create_concrete_controller_class()
        
        controller = TestableController(Mock())
        
        # Start inactive
        assert not controller.is_active
        
        # Activate
        controller.on_tab_activated()
        assert controller.is_active
        
        # Deactivate
        controller.on_tab_deactivated()
        assert not controller.is_active
        
        # Re-activate
        controller.on_tab_activated()
        assert controller.is_active


class TestSignalConnectionTracking:
    """Tests for signal connection management."""
    
    def test_connect_signal_returns_connection_id(self):
        """Test signal connection returns ID."""
        TestableController = create_concrete_controller_class()
        
        signal_manager = Mock()
        signal_manager.connect.return_value = "sig_00001"
        
        controller = TestableController(Mock(), signal_manager=signal_manager)
        sender = Mock()
        
        conn_id = controller._connect_signal(
            sender=sender,
            signal_name='clicked',
            receiver=lambda: None
        )
        
        assert conn_id == "sig_00001"
    
    def test_connect_signal_tracks_connection(self):
        """Test connected signals are tracked."""
        TestableController = create_concrete_controller_class()
        
        signal_manager = Mock()
        signal_manager.connect.return_value = "sig_00001"
        
        controller = TestableController(Mock(), signal_manager=signal_manager)
        
        controller._connect_signal(Mock(), 'clicked', lambda: None)
        
        assert "sig_00001" in controller._connection_ids
    
    def test_connect_multiple_signals(self):
        """Test multiple signals can be tracked."""
        TestableController = create_concrete_controller_class()
        
        signal_manager = Mock()
        signal_manager.connect.side_effect = ["sig_00001", "sig_00002", "sig_00003"]
        
        controller = TestableController(Mock(), signal_manager=signal_manager)
        
        controller._connect_signal(Mock(), 'signal1', lambda: None)
        controller._connect_signal(Mock(), 'signal2', lambda: None)
        controller._connect_signal(Mock(), 'signal3', lambda: None)
        
        assert len(controller._connection_ids) == 3
        assert "sig_00001" in controller._connection_ids
        assert "sig_00002" in controller._connection_ids
        assert "sig_00003" in controller._connection_ids
    
    def test_connect_signal_uses_class_name_as_default_context(self):
        """Test connection uses class name as default context."""
        TestableController = create_concrete_controller_class()
        
        signal_manager = Mock()
        signal_manager.connect.return_value = "sig_00001"
        
        controller = TestableController(Mock(), signal_manager=signal_manager)
        
        controller._connect_signal(Mock(), 'clicked', lambda: None)
        
        # Check that connect was called with class name as context
        call_kwargs = signal_manager.connect.call_args.kwargs
        assert call_kwargs.get('context') == 'TestableController'
    
    def test_connect_signal_uses_custom_context(self):
        """Test connection can use custom context."""
        TestableController = create_concrete_controller_class()
        
        signal_manager = Mock()
        signal_manager.connect.return_value = "sig_00001"
        
        controller = TestableController(Mock(), signal_manager=signal_manager)
        
        controller._connect_signal(
            Mock(), 'clicked', lambda: None,
            context='custom_context'
        )
        
        call_kwargs = signal_manager.connect.call_args.kwargs
        assert call_kwargs.get('context') == 'custom_context'
    
    def test_connect_signal_without_signal_manager(self):
        """Test fallback when no SignalManager available."""
        TestableController = create_concrete_controller_class()
        
        controller = TestableController(Mock(), signal_manager=None)
        sender = Mock()
        sender.clicked = Mock()  # Mock signal
        
        conn_id = controller._connect_signal(sender, 'clicked', lambda: None)
        
        # Returns None when no SignalManager
        assert conn_id is None
        # But signal was still connected directly
        sender.clicked.connect.assert_called_once()


class TestSignalDisconnection:
    """Tests for signal disconnection."""
    
    def test_disconnect_single_signal(self):
        """Test disconnecting a single signal."""
        TestableController = create_concrete_controller_class()
        
        signal_manager = Mock()
        signal_manager.connect.return_value = "sig_00001"
        signal_manager.disconnect.return_value = True
        
        controller = TestableController(Mock(), signal_manager=signal_manager)
        controller._connect_signal(Mock(), 'clicked', lambda: None)
        
        success = controller._disconnect_signal("sig_00001")
        
        assert success is True
        assert "sig_00001" not in controller._connection_ids
    
    def test_disconnect_all_signals(self):
        """Test all signals are disconnected on cleanup."""
        TestableController = create_concrete_controller_class()
        
        signal_manager = Mock()
        signal_manager.connect.side_effect = ["sig_00001", "sig_00002", "sig_00003"]
        signal_manager.disconnect.return_value = True
        
        controller = TestableController(Mock(), signal_manager=signal_manager)
        
        controller._connect_signal(Mock(), 'sig1', lambda: None)
        controller._connect_signal(Mock(), 'sig2', lambda: None)
        controller._connect_signal(Mock(), 'sig3', lambda: None)
        
        count = controller._disconnect_all_signals()
        
        assert count == 3
        assert len(controller._connection_ids) == 0
    
    def test_disconnect_all_clears_list_even_on_failure(self):
        """Test connection list is cleared even if disconnection fails."""
        TestableController = create_concrete_controller_class()
        
        signal_manager = Mock()
        signal_manager.connect.side_effect = ["sig_00001", "sig_00002"]
        signal_manager.disconnect.return_value = False  # All fail
        
        controller = TestableController(Mock(), signal_manager=signal_manager)
        
        controller._connect_signal(Mock(), 'sig1', lambda: None)
        controller._connect_signal(Mock(), 'sig2', lambda: None)
        
        count = controller._disconnect_all_signals()
        
        assert count == 0  # None succeeded
        assert len(controller._connection_ids) == 0  # But list is cleared
    
    def test_disconnect_without_signal_manager(self):
        """Test disconnection without SignalManager."""
        TestableController = create_concrete_controller_class()
        
        controller = TestableController(Mock(), signal_manager=None)
        
        count = controller._disconnect_all_signals()
        
        assert count == 0


class TestSetupTeardown:
    """Tests for setup and teardown lifecycle."""
    
    def test_setup_is_called(self):
        """Test setup method can be called."""
        TestableController = create_concrete_controller_class()
        
        controller = TestableController(Mock())
        controller.setup()
        
        assert controller.setup_called is True
    
    def test_teardown_is_called(self):
        """Test teardown method can be called."""
        TestableController = create_concrete_controller_class()
        
        controller = TestableController(Mock())
        controller.teardown()
        
        assert controller.teardown_called is True


class TestUtilityMethods:
    """Tests for utility methods."""
    
    def test_repr_shows_controller_state(self):
        """Test string representation shows state."""
        TestableController = create_concrete_controller_class()
        
        signal_manager = Mock()
        signal_manager.connect.side_effect = ["sig_00001", "sig_00002"]
        
        controller = TestableController(Mock(), signal_manager=signal_manager)
        controller._connect_signal(Mock(), 'sig1', lambda: None)
        controller._connect_signal(Mock(), 'sig2', lambda: None)
        controller.on_tab_activated()
        
        repr_str = repr(controller)
        
        assert 'TestableController' in repr_str
        assert 'active=True' in repr_str
        assert 'connections=2' in repr_str


class TestAbstractMethods:
    """Tests for abstract method enforcement."""
    
    def test_cannot_instantiate_base_controller_directly(self):
        """Test BaseController cannot be instantiated directly."""
        from ui.controllers.base_controller import BaseController
        
        with pytest.raises(TypeError) as excinfo:
            BaseController(Mock())
        
        assert "abstract" in str(excinfo.value).lower()
    
    def test_must_implement_setup(self):
        """Test subclass must implement setup."""
        from ui.controllers.base_controller import BaseController
        
        class IncompleteController(BaseController):
            def teardown(self):
                pass
        
        with pytest.raises(TypeError):
            IncompleteController(Mock())
    
    def test_must_implement_teardown(self):
        """Test subclass must implement teardown."""
        from ui.controllers.base_controller import BaseController
        
        class IncompleteController(BaseController):
            def setup(self):
                pass
        
        with pytest.raises(TypeError):
            IncompleteController(Mock())


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

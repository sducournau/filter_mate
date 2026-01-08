"""
Unit tests for ControllerRegistry.

Tests the registry pattern for controller lifecycle management.
"""
import pytest
from unittest.mock import Mock, MagicMock


def create_mock_controller(name: str = "test"):
    """Create a mock controller for testing."""
    from ui.controllers.base_controller import BaseController
    
    class MockController(BaseController):
        def __init__(self, dockwidget, filter_service=None, signal_manager=None):
            super().__init__(dockwidget, filter_service, signal_manager)
            self.name = name
            self.setup_called = False
            self.teardown_called = False
            self.setup_order = None
            self.teardown_order = None
        
        def setup(self) -> None:
            self.setup_called = True
        
        def teardown(self) -> None:
            self.teardown_called = True
    
    return MockController(Mock())


class TestControllerRegistration:
    """Tests for controller registration."""
    
    def test_register_controller(self):
        """Test basic controller registration."""
        from ui.controllers.registry import ControllerRegistry
        
        registry = ControllerRegistry()
        controller = create_mock_controller()
        
        registry.register('test', controller)
        
        assert 'test' in registry
        assert len(registry) == 1
    
    def test_register_with_tab_index(self):
        """Test registration with tab index."""
        from ui.controllers.registry import ControllerRegistry, TabIndex
        
        registry = ControllerRegistry()
        controller = create_mock_controller()
        
        registry.register('filtering', controller, tab_index=TabIndex.FILTERING)
        
        assert registry.get_for_tab(TabIndex.FILTERING) is controller
    
    def test_register_duplicate_name_raises(self):
        """Test duplicate name raises error."""
        from ui.controllers.registry import ControllerRegistry
        
        registry = ControllerRegistry()
        controller1 = create_mock_controller()
        controller2 = create_mock_controller()
        
        registry.register('test', controller1)
        
        with pytest.raises(ValueError) as excinfo:
            registry.register('test', controller2)
        
        assert "already registered" in str(excinfo.value)
    
    def test_register_invalid_controller_raises(self):
        """Test registering non-controller raises error."""
        from ui.controllers.registry import ControllerRegistry
        
        registry = ControllerRegistry()
        
        with pytest.raises(ValueError) as excinfo:
            registry.register('test', "not a controller")
        
        assert "must inherit from BaseController" in str(excinfo.value)
    
    def test_unregister_controller(self):
        """Test controller unregistration."""
        from ui.controllers.registry import ControllerRegistry
        
        registry = ControllerRegistry()
        controller = create_mock_controller()
        
        registry.register('test', controller)
        result = registry.unregister('test')
        
        assert result is True
        assert 'test' not in registry
        assert len(registry) == 0
    
    def test_unregister_nonexistent_returns_false(self):
        """Test unregistering nonexistent controller returns False."""
        from ui.controllers.registry import ControllerRegistry
        
        registry = ControllerRegistry()
        
        result = registry.unregister('nonexistent')
        
        assert result is False


class TestControllerRetrieval:
    """Tests for controller retrieval."""
    
    def test_get_controller_by_name(self):
        """Test getting controller by name."""
        from ui.controllers.registry import ControllerRegistry
        
        registry = ControllerRegistry()
        controller = create_mock_controller()
        
        registry.register('test', controller)
        
        result = registry.get('test')
        
        assert result is controller
    
    def test_get_nonexistent_returns_none(self):
        """Test getting nonexistent controller returns None."""
        from ui.controllers.registry import ControllerRegistry
        
        registry = ControllerRegistry()
        
        result = registry.get('nonexistent')
        
        assert result is None
    
    def test_get_typed_returns_correct_type(self):
        """Test get_typed returns correctly typed controller."""
        from ui.controllers.registry import ControllerRegistry
        from ui.controllers.base_controller import BaseController
        
        registry = ControllerRegistry()
        controller = create_mock_controller()
        
        registry.register('test', controller)
        
        result = registry.get_typed('test', BaseController)
        
        assert result is controller
    
    def test_get_typed_wrong_type_returns_none(self):
        """Test get_typed with wrong type returns None."""
        from ui.controllers.registry import ControllerRegistry
        
        registry = ControllerRegistry()
        controller = create_mock_controller()
        
        registry.register('test', controller)
        
        # Create a different controller class
        class OtherController:
            pass
        
        result = registry.get_typed('test', OtherController)
        
        assert result is None
    
    def test_get_for_tab(self):
        """Test getting controller by tab index."""
        from ui.controllers.registry import ControllerRegistry, TabIndex
        
        registry = ControllerRegistry()
        controller = create_mock_controller()
        
        registry.register('filtering', controller, tab_index=TabIndex.FILTERING)
        
        result = registry.get_for_tab(TabIndex.FILTERING)
        
        assert result is controller
    
    def test_get_for_tab_no_mapping_returns_none(self):
        """Test getting controller for unmapped tab returns None."""
        from ui.controllers.registry import ControllerRegistry, TabIndex
        
        registry = ControllerRegistry()
        
        result = registry.get_for_tab(TabIndex.FILTERING)
        
        assert result is None
    
    def test_get_all(self):
        """Test getting all controllers."""
        from ui.controllers.registry import ControllerRegistry
        
        registry = ControllerRegistry()
        controller1 = create_mock_controller("c1")
        controller2 = create_mock_controller("c2")
        
        registry.register('c1', controller1)
        registry.register('c2', controller2)
        
        all_controllers = registry.get_all()
        
        assert len(all_controllers) == 2
        assert all_controllers['c1'] is controller1
        assert all_controllers['c2'] is controller2
    
    def test_get_names(self):
        """Test getting all controller names in order."""
        from ui.controllers.registry import ControllerRegistry
        
        registry = ControllerRegistry()
        
        registry.register('first', create_mock_controller())
        registry.register('second', create_mock_controller())
        registry.register('third', create_mock_controller())
        
        names = registry.get_names()
        
        assert names == ['first', 'second', 'third']


class TestLifecycleManagement:
    """Tests for setup/teardown lifecycle."""
    
    def test_setup_all_calls_setup_on_each(self):
        """Test setup_all calls setup on each controller."""
        from ui.controllers.registry import ControllerRegistry
        
        registry = ControllerRegistry()
        controller1 = create_mock_controller()
        controller2 = create_mock_controller()
        
        registry.register('c1', controller1)
        registry.register('c2', controller2)
        
        count = registry.setup_all()
        
        assert count == 2
        assert controller1.setup_called is True
        assert controller2.setup_called is True
    
    def test_teardown_all_calls_teardown_on_each(self):
        """Test teardown_all calls teardown on each controller."""
        from ui.controllers.registry import ControllerRegistry
        
        registry = ControllerRegistry()
        controller1 = create_mock_controller()
        controller2 = create_mock_controller()
        
        registry.register('c1', controller1)
        registry.register('c2', controller2)
        
        count = registry.teardown_all()
        
        assert count == 2
        assert controller1.teardown_called is True
        assert controller2.teardown_called is True
    
    def test_setup_order_is_registration_order(self):
        """Test setup happens in registration order."""
        from ui.controllers.registry import ControllerRegistry
        from ui.controllers.base_controller import BaseController
        
        setup_order = []
        
        class OrderTrackingController(BaseController):
            def __init__(self, name):
                super().__init__(Mock())
                self.name = name
            
            def setup(self):
                setup_order.append(self.name)
            
            def teardown(self):
                pass
        
        registry = ControllerRegistry()
        registry.register('first', OrderTrackingController('first'))
        registry.register('second', OrderTrackingController('second'))
        registry.register('third', OrderTrackingController('third'))
        
        registry.setup_all()
        
        assert setup_order == ['first', 'second', 'third']
    
    def test_teardown_order_is_reverse_registration(self):
        """Test teardown happens in reverse registration order."""
        from ui.controllers.registry import ControllerRegistry
        from ui.controllers.base_controller import BaseController
        
        teardown_order = []
        
        class OrderTrackingController(BaseController):
            def __init__(self, name):
                super().__init__(Mock())
                self.name = name
            
            def setup(self):
                pass
            
            def teardown(self):
                teardown_order.append(self.name)
        
        registry = ControllerRegistry()
        registry.register('first', OrderTrackingController('first'))
        registry.register('second', OrderTrackingController('second'))
        registry.register('third', OrderTrackingController('third'))
        
        registry.teardown_all()
        
        assert teardown_order == ['third', 'second', 'first']


class TestTabNotification:
    """Tests for tab change notification."""
    
    def test_notify_tab_changed_deactivates_old(self):
        """Test tab change deactivates old controller."""
        from ui.controllers.registry import ControllerRegistry, TabIndex
        
        registry = ControllerRegistry()
        old_controller = create_mock_controller()
        new_controller = create_mock_controller()
        
        registry.register('filtering', old_controller, tab_index=TabIndex.FILTERING)
        registry.register('exporting', new_controller, tab_index=TabIndex.EXPORTING)
        
        # Simulate old controller was active
        old_controller.on_tab_activated()
        assert old_controller.is_active
        
        registry.notify_tab_changed(
            old_index=TabIndex.FILTERING,
            new_index=TabIndex.EXPORTING
        )
        
        assert old_controller.is_active is False
    
    def test_notify_tab_changed_activates_new(self):
        """Test tab change activates new controller."""
        from ui.controllers.registry import ControllerRegistry, TabIndex
        
        registry = ControllerRegistry()
        old_controller = create_mock_controller()
        new_controller = create_mock_controller()
        
        registry.register('filtering', old_controller, tab_index=TabIndex.FILTERING)
        registry.register('exporting', new_controller, tab_index=TabIndex.EXPORTING)
        
        assert not new_controller.is_active
        
        registry.notify_tab_changed(
            old_index=TabIndex.FILTERING,
            new_index=TabIndex.EXPORTING
        )
        
        assert new_controller.is_active is True
    
    def test_notify_tab_changed_handles_unmapped_tabs(self):
        """Test tab change handles unmapped tab indices gracefully."""
        from ui.controllers.registry import ControllerRegistry, TabIndex
        
        registry = ControllerRegistry()
        controller = create_mock_controller()
        
        registry.register('filtering', controller, tab_index=TabIndex.FILTERING)
        
        # Should not raise even with unmapped indices
        registry.notify_tab_changed(old_index=99, new_index=100)


class TestTabIndexEnum:
    """Tests for TabIndex enum."""
    
    def test_tab_index_values(self):
        """Test TabIndex enum has correct values."""
        from ui.controllers.registry import TabIndex
        
        assert TabIndex.FILTERING == 0
        assert TabIndex.EXPORTING == 1
        assert TabIndex.CONFIGURATION == 2
    
    def test_tab_index_is_int(self):
        """Test TabIndex values can be used as int."""
        from ui.controllers.registry import TabIndex
        
        # Can be used in dictionary
        d = {}
        d[TabIndex.FILTERING] = "filtering"
        assert d[0] == "filtering"


class TestRegistryDunderMethods:
    """Tests for special methods."""
    
    def test_len(self):
        """Test len() returns controller count."""
        from ui.controllers.registry import ControllerRegistry
        
        registry = ControllerRegistry()
        
        assert len(registry) == 0
        
        registry.register('c1', create_mock_controller())
        assert len(registry) == 1
        
        registry.register('c2', create_mock_controller())
        assert len(registry) == 2
    
    def test_contains(self):
        """Test 'in' operator works."""
        from ui.controllers.registry import ControllerRegistry
        
        registry = ControllerRegistry()
        registry.register('test', create_mock_controller())
        
        assert 'test' in registry
        assert 'other' not in registry
    
    def test_repr(self):
        """Test string representation."""
        from ui.controllers.registry import ControllerRegistry
        
        registry = ControllerRegistry()
        registry.register('exploring', create_mock_controller())
        registry.register('filtering', create_mock_controller())
        
        repr_str = repr(registry)
        
        assert 'ControllerRegistry' in repr_str
        assert 'exploring' in repr_str
        assert 'filtering' in repr_str


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

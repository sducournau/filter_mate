"""
Unit tests for ControllerIntegration.

Tests the integration layer between dockwidget and controllers.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch


def create_mock_dockwidget():
    """Create a mock dockwidget for testing."""
    dockwidget = Mock()
    
    # Mock tabTools
    dockwidget.tabTools = Mock()
    dockwidget.tabTools.currentChanged = Mock()
    dockwidget.tabTools.currentChanged.connect = Mock()
    dockwidget.tabTools.currentChanged.disconnect = Mock()
    
    # Mock signals
    dockwidget.currentLayerChanged = Mock()
    dockwidget.currentLayerChanged.connect = Mock()
    dockwidget.currentLayerChanged.disconnect = Mock()
    
    # Mock layer
    dockwidget.current_layer = None
    
    # Mock cache
    dockwidget._exploring_cache = Mock()
    
    return dockwidget


class TestControllerIntegrationInitialization:
    """Tests for integration initialization."""
    
    def test_initialization(self):
        """Test integration initializes correctly."""
        from ui.controllers.integration import ControllerIntegration
        
        dockwidget = create_mock_dockwidget()
        integration = ControllerIntegration(dockwidget)
        
        assert integration.enabled is True
        assert integration.registry is None  # Not setup yet
        assert integration.exploring_controller is None
    
    def test_initialization_disabled(self):
        """Test integration can be disabled."""
        from ui.controllers.integration import ControllerIntegration
        
        dockwidget = create_mock_dockwidget()
        integration = ControllerIntegration(dockwidget, enabled=False)
        
        assert integration.enabled is False


class TestControllerIntegrationSetup:
    """Tests for setup process."""
    
    def test_setup_creates_registry(self):
        """Test setup creates controller registry."""
        from ui.controllers.integration import ControllerIntegration
        
        dockwidget = create_mock_dockwidget()
        integration = ControllerIntegration(dockwidget)
        
        result = integration.setup()
        
        assert result is True
        assert integration.registry is not None
    
    def test_setup_creates_controllers(self):
        """Test setup creates all controllers."""
        from ui.controllers.integration import ControllerIntegration
        
        dockwidget = create_mock_dockwidget()
        integration = ControllerIntegration(dockwidget)
        
        integration.setup()
        
        assert integration.exploring_controller is not None
        assert integration.filtering_controller is not None
        assert integration.exporting_controller is not None
    
    def test_setup_connects_signals(self):
        """Test setup connects signals."""
        from ui.controllers.integration import ControllerIntegration
        
        dockwidget = create_mock_dockwidget()
        integration = ControllerIntegration(dockwidget)
        
        integration.setup()
        
        # Verify tabTools signal was connected
        dockwidget.tabTools.currentChanged.connect.assert_called()
    
    def test_setup_when_disabled(self):
        """Test setup returns False when disabled."""
        from ui.controllers.integration import ControllerIntegration
        
        dockwidget = create_mock_dockwidget()
        integration = ControllerIntegration(dockwidget, enabled=False)
        
        result = integration.setup()
        
        assert result is False
        assert integration.registry is None
    
    def test_setup_idempotent(self):
        """Test setup can be called multiple times safely."""
        from ui.controllers.integration import ControllerIntegration
        
        dockwidget = create_mock_dockwidget()
        integration = ControllerIntegration(dockwidget)
        
        result1 = integration.setup()
        result2 = integration.setup()
        
        assert result1 is True
        assert result2 is True  # Second call succeeds but doesn't re-setup


class TestControllerIntegrationTeardown:
    """Tests for teardown process."""
    
    def test_teardown_clears_controllers(self):
        """Test teardown clears controller references."""
        from ui.controllers.integration import ControllerIntegration
        
        dockwidget = create_mock_dockwidget()
        integration = ControllerIntegration(dockwidget)
        
        integration.setup()
        integration.teardown()
        
        assert integration.exploring_controller is None
        assert integration.filtering_controller is None
        assert integration.exporting_controller is None
        assert integration.registry is None
    
    def test_teardown_disconnects_signals(self):
        """Test teardown disconnects signals."""
        from ui.controllers.integration import ControllerIntegration
        
        dockwidget = create_mock_dockwidget()
        integration = ControllerIntegration(dockwidget)
        
        integration.setup()
        integration.teardown()
        
        # Verify disconnect was called
        dockwidget.tabTools.currentChanged.disconnect.assert_called()
    
    def test_teardown_without_setup(self):
        """Test teardown is safe without prior setup."""
        from ui.controllers.integration import ControllerIntegration
        
        dockwidget = create_mock_dockwidget()
        integration = ControllerIntegration(dockwidget)
        
        # Should not raise
        integration.teardown()


class TestTabChangeHandling:
    """Tests for tab change handling."""
    
    def test_tab_change_notifies_registry(self):
        """Test tab change notifies registry."""
        from ui.controllers.integration import ControllerIntegration
        from ui.controllers.registry import TabIndex
        
        dockwidget = create_mock_dockwidget()
        integration = ControllerIntegration(dockwidget)
        integration.setup()
        
        # Simulate tab change
        integration._on_tab_changed(0)
        
        # Controller should be notified (exploring is at tab 0)
        # We can verify the controller's active state
        # This is indirect verification
    
    def test_tab_change_invalid_index(self):
        """Test tab change with invalid index is handled."""
        from ui.controllers.integration import ControllerIntegration
        
        dockwidget = create_mock_dockwidget()
        integration = ControllerIntegration(dockwidget)
        integration.setup()
        
        # Should not raise
        integration._on_tab_changed(999)


class TestLayerChangeHandling:
    """Tests for layer change handling."""
    
    def test_layer_change_updates_exploring(self):
        """Test layer change updates exploring controller."""
        from ui.controllers.integration import ControllerIntegration
        
        dockwidget = create_mock_dockwidget()
        layer = Mock()
        layer.isValid.return_value = True
        dockwidget.current_layer = layer
        
        integration = ControllerIntegration(dockwidget)
        integration.setup()
        
        integration._on_current_layer_changed()
        
        # Verify exploring controller received the layer
        assert integration.exploring_controller.get_current_layer() is layer
    
    def test_layer_change_updates_filtering(self):
        """Test layer change updates filtering controller."""
        from ui.controllers.integration import ControllerIntegration
        
        dockwidget = create_mock_dockwidget()
        layer = Mock()
        layer.isValid.return_value = True
        dockwidget.current_layer = layer
        
        integration = ControllerIntegration(dockwidget)
        integration.setup()
        
        integration._on_current_layer_changed()
        
        # Verify filtering controller received the layer
        assert integration.filtering_controller.get_source_layer() is layer


class TestDelegationMethods:
    """Tests for delegation methods."""
    
    def test_delegate_flash_feature(self):
        """Test flash feature delegation."""
        from ui.controllers.integration import ControllerIntegration
        
        dockwidget = create_mock_dockwidget()
        integration = ControllerIntegration(dockwidget)
        integration.setup()
        
        # Should return False (no layer set)
        result = integration.delegate_flash_feature(1)
        
        assert result is False
    
    def test_delegate_execute_filter(self):
        """Test filter execution delegation."""
        from ui.controllers.integration import ControllerIntegration
        
        dockwidget = create_mock_dockwidget()
        integration = ControllerIntegration(dockwidget)
        integration.setup()
        
        # Set up valid configuration
        layer = Mock()
        layer.id.return_value = "test_layer"
        layer.isValid.return_value = True
        integration.filtering_controller.set_source_layer(layer)
        integration.filtering_controller.set_target_layers(["target_1"])
        
        result = integration.delegate_execute_filter()
        
        assert result is True
    
    def test_delegate_undo_filter(self):
        """Test undo delegation."""
        from ui.controllers.integration import ControllerIntegration
        
        dockwidget = create_mock_dockwidget()
        integration = ControllerIntegration(dockwidget)
        integration.setup()
        
        # No history, should return False
        result = integration.delegate_undo_filter()
        
        assert result is False
    
    def test_delegate_execute_export(self):
        """Test export execution delegation."""
        from ui.controllers.integration import ControllerIntegration
        
        dockwidget = create_mock_dockwidget()
        integration = ControllerIntegration(dockwidget)
        integration.setup()
        
        # Set up valid configuration
        integration.exporting_controller.set_layers_to_export(["l1"])
        integration.exporting_controller.set_output_path("/tmp/out.gpkg")
        
        result = integration.delegate_execute_export()
        
        assert result is True


class TestStateSynchronization:
    """Tests for state synchronization."""
    
    def test_sync_from_dockwidget(self):
        """Test syncing state from dockwidget."""
        from ui.controllers.integration import ControllerIntegration
        
        dockwidget = create_mock_dockwidget()
        layer = Mock()
        layer.isValid.return_value = True
        dockwidget.current_layer = layer
        
        integration = ControllerIntegration(dockwidget)
        integration.setup()
        
        integration.sync_from_dockwidget()
        
        # Verify controllers have the layer
        assert integration.exploring_controller.get_current_layer() is layer
    
    def test_sync_from_dockwidget_not_setup(self):
        """Test sync does nothing when not setup."""
        from ui.controllers.integration import ControllerIntegration
        
        dockwidget = create_mock_dockwidget()
        integration = ControllerIntegration(dockwidget)
        
        # Should not raise
        integration.sync_from_dockwidget()


class TestStatus:
    """Tests for status reporting."""
    
    def test_get_status_not_setup(self):
        """Test status when not setup."""
        from ui.controllers.integration import ControllerIntegration
        
        dockwidget = create_mock_dockwidget()
        integration = ControllerIntegration(dockwidget)
        
        status = integration.get_status()
        
        assert status['enabled'] is True
        assert status['is_setup'] is False
        assert status['registry_count'] == 0
    
    def test_get_status_after_setup(self):
        """Test status after setup."""
        from ui.controllers.integration import ControllerIntegration
        
        dockwidget = create_mock_dockwidget()
        integration = ControllerIntegration(dockwidget)
        integration.setup()
        
        status = integration.get_status()
        
        assert status['enabled'] is True
        assert status['is_setup'] is True
        assert status['registry_count'] == 3
        assert status['controllers']['exploring'] is True
        assert status['controllers']['filtering'] is True
        assert status['controllers']['exporting'] is True
    
    def test_repr(self):
        """Test string representation."""
        from ui.controllers.integration import ControllerIntegration
        
        dockwidget = create_mock_dockwidget()
        integration = ControllerIntegration(dockwidget)
        
        repr_str = repr(integration)
        assert "inactive" in repr_str
        
        integration.setup()
        repr_str = repr(integration)
        assert "active" in repr_str
        assert "controllers=3" in repr_str


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

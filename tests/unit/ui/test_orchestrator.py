"""
Tests for DockWidgetOrchestrator.

Story: MIG-087
Phase: 6 - God Class DockWidget Migration
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add plugin path
plugin_path = Path(__file__).parents[4]
if str(plugin_path) not in sys.path:
    sys.path.insert(0, str(plugin_path))


# ─────────────────────────────────────────────────────────────────
# Mock Classes
# ─────────────────────────────────────────────────────────────────

class MockDockWidget:
    """Mock QDockWidget for testing."""
    
    def __init__(self):
        self.visible = True
        self.title = "FilterMate"
    
    def show(self):
        self.visible = True
    
    def hide(self):
        self.visible = False


class MockApp:
    """Mock FilterMateApp."""
    
    def __init__(self):
        self.name = "FilterMate"
        self.version = "3.0.0"


class MockIface:
    """Mock QGIS iface."""
    
    def __init__(self):
        self.mainWindow = Mock()
    
    def messageBar(self):
        return Mock()


class MockManager:
    """Mock manager with setup/teardown."""
    
    def __init__(self, dockwidget):
        self.dockwidget = dockwidget
        self.setup_called = False
        self.teardown_called = False
    
    def setup(self):
        self.setup_called = True
    
    def teardown(self):
        self.teardown_called = True


class MockController:
    """Mock controller with setup."""
    
    def __init__(self, dockwidget, service=None):
        self.dockwidget = dockwidget
        self.service = service
        self.setup_called = False
        self.current_layer = Mock()
        self.current_backend = 'memory'
        self.is_in_progress = False
    
    def setup(self):
        self.setup_called = True
    
    def apply_filter(self, expression=None):
        return True
    
    def clear_filter(self):
        return True
    
    def reset_all(self):
        return True
    
    def export(self, format_type, **kwargs):
        return True
    
    def refresh_layers(self):
        pass
    
    def switch_backend(self, name):
        return True


class MockService:
    """Mock service with cleanup."""
    
    def __init__(self, dockwidget):
        self.dockwidget = dockwidget
        self.cleanup_called = False
    
    def cleanup(self):
        self.cleanup_called = True


class MockSignalManager:
    """Mock signal manager."""
    
    def __init__(self, dockwidget):
        self.dockwidget = dockwidget
        self.teardown_called = False
    
    def connect_widgets_signals(self):
        pass
    
    def teardown(self):
        self.teardown_called = True


class MockLayerSignalHandler:
    """Mock layer signal handler."""
    
    def __init__(self, dockwidget, signal_manager):
        self.dockwidget = dockwidget
        self.signal_manager = signal_manager
        self.disconnected = False
    
    def disconnect_all_layers(self):
        self.disconnected = True


# ─────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def dockwidget():
    """Create mock dockwidget."""
    return MockDockWidget()


@pytest.fixture
def app():
    """Create mock app."""
    return MockApp()


@pytest.fixture
def iface():
    """Create mock iface."""
    return MockIface()


@pytest.fixture
def orchestrator(dockwidget, app, iface):
    """Create orchestrator without initialization."""
    from ui.orchestrator import DockWidgetOrchestrator
    return DockWidgetOrchestrator(dockwidget, app, iface)


# ─────────────────────────────────────────────────────────────────
# Test Initialization
# ─────────────────────────────────────────────────────────────────

class TestOrchestratorInit:
    """Tests for orchestrator initialization."""
    
    def test_init(self, dockwidget, app, iface):
        """Test basic initialization."""
        from ui.orchestrator import DockWidgetOrchestrator
        
        orch = DockWidgetOrchestrator(dockwidget, app, iface)
        
        assert orch._dockwidget is dockwidget
        assert orch._app is app
        assert orch._iface is iface
        assert not orch._initialized
        assert not orch._setup_complete
    
    def test_repr(self, orchestrator):
        """Test string representation."""
        result = repr(orchestrator)
        
        assert "DockWidgetOrchestrator" in result
        assert "initialized=False" in result
    
    def test_properties_before_init(self, orchestrator):
        """Test properties before initialization."""
        assert orchestrator.dockwidget is not None
        assert orchestrator.app is not None
        assert orchestrator.iface is not None
        assert not orchestrator.is_initialized
        assert not orchestrator.is_setup_complete


class TestOrchestratorInitialize:
    """Tests for initialize method."""
    
    @patch('ui.orchestrator.SignalManager', MockSignalManager)
    @patch('ui.orchestrator.LayerSignalHandler', MockLayerSignalHandler)
    def test_initialize_signal_management(self, orchestrator):
        """Test signal management initialization."""
        # Mock other imports
        with patch.dict('sys.modules', {
            'ui.layout': Mock(),
            'ui.styles': Mock(),
            'core.services': Mock(),
            'ui.controllers': Mock(),
        }):
            # Patch individual managers/controllers
            with patch.object(orchestrator, '_init_layout_managers'):
                with patch.object(orchestrator, '_init_style_managers'):
                    with patch.object(orchestrator, '_init_services'):
                        with patch.object(orchestrator, '_init_controllers'):
                            orchestrator._init_signal_management()
        
        assert orchestrator._signal_manager is not None
    
    def test_initialize_sets_flag(self, orchestrator):
        """Test that initialization sets flag."""
        with patch.object(orchestrator, '_init_signal_management'):
            with patch.object(orchestrator, '_init_layout_managers'):
                with patch.object(orchestrator, '_init_style_managers'):
                    with patch.object(orchestrator, '_init_services'):
                        with patch.object(orchestrator, '_init_controllers'):
                            result = orchestrator.initialize()
        
        assert result is True
        assert orchestrator._initialized is True
    
    def test_initialize_twice(self, orchestrator):
        """Test initializing twice returns True without re-init."""
        orchestrator._initialized = True
        
        result = orchestrator.initialize()
        
        assert result is True


class TestOrchestratorSetup:
    """Tests for setup method."""
    
    def test_setup_without_init(self, orchestrator):
        """Test setup fails without initialization."""
        result = orchestrator.setup()
        
        assert result is False
    
    def test_setup_calls_manager_setup(self, orchestrator):
        """Test setup calls all manager setups."""
        orchestrator._initialized = True
        
        # Add mock managers
        mock_manager = MockManager(orchestrator._dockwidget)
        orchestrator._layout_managers = {'test': mock_manager}
        orchestrator._style_managers = {}
        orchestrator._controllers = {}
        orchestrator._signal_manager = MockSignalManager(orchestrator._dockwidget)
        
        result = orchestrator.setup()
        
        assert result is True
        assert mock_manager.setup_called
        assert orchestrator._setup_complete
    
    def test_setup_twice(self, orchestrator):
        """Test setup twice returns True."""
        orchestrator._initialized = True
        orchestrator._setup_complete = True
        
        result = orchestrator.setup()
        
        assert result is True


# ─────────────────────────────────────────────────────────────────
# Test Public Properties
# ─────────────────────────────────────────────────────────────────

class TestOrchestratorProperties:
    """Tests for public properties."""
    
    def test_current_layer(self, orchestrator):
        """Test current_layer property."""
        mock_controller = MockController(orchestrator._dockwidget)
        orchestrator._controllers = {'layer_sync': mock_controller}
        
        result = orchestrator.current_layer
        
        assert result is mock_controller.current_layer
    
    def test_current_layer_no_controller(self, orchestrator):
        """Test current_layer with no controller."""
        orchestrator._controllers = {}
        
        result = orchestrator.current_layer
        
        assert result is None
    
    def test_current_backend(self, orchestrator):
        """Test current_backend property."""
        mock_controller = MockController(orchestrator._dockwidget)
        orchestrator._controllers = {'backend': mock_controller}
        
        result = orchestrator.current_backend
        
        assert result == 'memory'
    
    def test_is_filtering_in_progress(self, orchestrator):
        """Test is_filtering_in_progress property."""
        mock_controller = MockController(orchestrator._dockwidget)
        mock_controller.is_in_progress = True
        orchestrator._controllers = {'filtering': mock_controller}
        
        result = orchestrator.is_filtering_in_progress
        
        assert result is True


# ─────────────────────────────────────────────────────────────────
# Test Component Access
# ─────────────────────────────────────────────────────────────────

class TestOrchestratorComponentAccess:
    """Tests for component access methods."""
    
    def test_get_controller(self, orchestrator):
        """Test get_controller method."""
        mock_controller = MockController(orchestrator._dockwidget)
        orchestrator._controllers = {'filtering': mock_controller}
        
        result = orchestrator.get_controller('filtering')
        
        assert result is mock_controller
    
    def test_get_controller_not_found(self, orchestrator):
        """Test get_controller with unknown name."""
        orchestrator._controllers = {}
        
        result = orchestrator.get_controller('unknown')
        
        assert result is None
    
    def test_get_layout_manager(self, orchestrator):
        """Test get_layout_manager method."""
        mock_manager = MockManager(orchestrator._dockwidget)
        orchestrator._layout_managers = {'splitter': mock_manager}
        
        result = orchestrator.get_layout_manager('splitter')
        
        assert result is mock_manager
    
    def test_get_style_manager(self, orchestrator):
        """Test get_style_manager method."""
        mock_manager = MockManager(orchestrator._dockwidget)
        orchestrator._style_managers = {'theme': mock_manager}
        
        result = orchestrator.get_style_manager('theme')
        
        assert result is mock_manager
    
    def test_get_service(self, orchestrator):
        """Test get_service method."""
        mock_service = MockService(orchestrator._dockwidget)
        orchestrator._services = {'backend': mock_service}
        
        result = orchestrator.get_service('backend')
        
        assert result is mock_service
    
    def test_get_all_controllers(self, orchestrator):
        """Test get_all_controllers method."""
        ctrl1 = MockController(orchestrator._dockwidget)
        ctrl2 = MockController(orchestrator._dockwidget)
        orchestrator._controllers = {'a': ctrl1, 'b': ctrl2}
        
        result = orchestrator.get_all_controllers()
        
        assert len(result) == 2
        assert ctrl1 in result
        assert ctrl2 in result
    
    def test_get_all_managers(self, orchestrator):
        """Test get_all_managers method."""
        mgr1 = MockManager(orchestrator._dockwidget)
        mgr2 = MockManager(orchestrator._dockwidget)
        orchestrator._layout_managers = {'a': mgr1}
        orchestrator._style_managers = {'b': mgr2}
        
        result = orchestrator.get_all_managers()
        
        assert len(result) == 2


# ─────────────────────────────────────────────────────────────────
# Test Public API
# ─────────────────────────────────────────────────────────────────

class TestOrchestratorPublicAPI:
    """Tests for public API methods."""
    
    def test_apply_filter(self, orchestrator):
        """Test apply_filter method."""
        mock_controller = MockController(orchestrator._dockwidget)
        orchestrator._controllers = {'filtering': mock_controller}
        
        result = orchestrator.apply_filter("id > 10")
        
        assert result is True
    
    def test_apply_filter_no_controller(self, orchestrator):
        """Test apply_filter with no controller."""
        orchestrator._controllers = {}
        
        result = orchestrator.apply_filter()
        
        assert result is False
    
    def test_clear_filter(self, orchestrator):
        """Test clear_filter method."""
        mock_controller = MockController(orchestrator._dockwidget)
        orchestrator._controllers = {'filtering': mock_controller}
        
        result = orchestrator.clear_filter()
        
        assert result is True
    
    def test_reset_all(self, orchestrator):
        """Test reset_all method."""
        mock_controller = MockController(orchestrator._dockwidget)
        orchestrator._controllers = {'filtering': mock_controller}
        
        result = orchestrator.reset_all()
        
        assert result is True
    
    def test_export_layer(self, orchestrator):
        """Test export_layer method."""
        mock_controller = MockController(orchestrator._dockwidget)
        orchestrator._controllers = {'exporting': mock_controller}
        
        result = orchestrator.export_layer('gpkg')
        
        assert result is True
    
    def test_refresh_layer_list(self, orchestrator):
        """Test refresh_layer_list method."""
        mock_controller = MockController(orchestrator._dockwidget)
        mock_controller.refresh_layers = Mock()
        orchestrator._controllers = {'layer_sync': mock_controller}
        
        orchestrator.refresh_layer_list()
        
        mock_controller.refresh_layers.assert_called_once()
    
    def test_switch_backend(self, orchestrator):
        """Test switch_backend method."""
        mock_controller = MockController(orchestrator._dockwidget)
        orchestrator._controllers = {'backend': mock_controller}
        
        result = orchestrator.switch_backend('postgresql')
        
        assert result is True


# ─────────────────────────────────────────────────────────────────
# Test Teardown
# ─────────────────────────────────────────────────────────────────

class TestOrchestratorTeardown:
    """Tests for teardown method."""
    
    def test_teardown(self, orchestrator):
        """Test teardown clears all components."""
        # Setup some mocks
        orchestrator._initialized = True
        orchestrator._setup_complete = True
        orchestrator._signal_manager = MockSignalManager(orchestrator._dockwidget)
        orchestrator._layer_signal_handler = MockLayerSignalHandler(
            orchestrator._dockwidget,
            orchestrator._signal_manager
        )
        
        mock_manager = MockManager(orchestrator._dockwidget)
        orchestrator._layout_managers = {'test': mock_manager}
        
        mock_service = MockService(orchestrator._dockwidget)
        orchestrator._services = {'test': mock_service}
        
        orchestrator.teardown()
        
        assert not orchestrator._initialized
        assert not orchestrator._setup_complete
        assert len(orchestrator._layout_managers) == 0
        assert len(orchestrator._services) == 0
        assert orchestrator._signal_manager.teardown_called
        assert orchestrator._layer_signal_handler.disconnected
    
    def test_teardown_with_error(self, orchestrator):
        """Test teardown handles errors gracefully."""
        orchestrator._initialized = True
        
        # Create manager that raises on teardown
        class ErrorManager:
            def teardown(self):
                raise RuntimeError("Test error")
        
        orchestrator._layout_managers = {'error': ErrorManager()}
        orchestrator._style_managers = {}
        orchestrator._services = {}
        orchestrator._controllers = {}
        orchestrator._signal_manager = None
        orchestrator._layer_signal_handler = None
        
        # Should not raise
        orchestrator.teardown()
        
        assert not orchestrator._initialized
    
    def test_close_event_handler(self, orchestrator):
        """Test close_event_handler calls teardown."""
        orchestrator._initialized = True
        orchestrator._layout_managers = {}
        orchestrator._style_managers = {}
        orchestrator._services = {}
        orchestrator._controllers = {}
        orchestrator._signal_manager = None
        orchestrator._layer_signal_handler = None
        
        mock_event = Mock()
        
        orchestrator.close_event_handler(mock_event)
        
        assert not orchestrator._initialized


# ─────────────────────────────────────────────────────────────────
# Test Deprecated Façades
# ─────────────────────────────────────────────────────────────────

class TestOrchestratorDeprecated:
    """Tests for deprecated façade methods."""
    
    def test_manage_filter_warning(self, orchestrator):
        """Test manage_filter issues deprecation warning."""
        mock_controller = MockController(orchestrator._dockwidget)
        orchestrator._controllers = {'filtering': mock_controller}
        
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = orchestrator.manage_filter()
            
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert 'deprecated' in str(w[0].message).lower()
    
    def test_get_splitter_manager_warning(self, orchestrator):
        """Test get_splitter_manager issues deprecation warning."""
        mock_manager = MockManager(orchestrator._dockwidget)
        orchestrator._layout_managers = {'splitter': mock_manager}
        
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = orchestrator.get_splitter_manager()
            
            assert len(w) == 1
            assert result is mock_manager


# ─────────────────────────────────────────────────────────────────
# Test Factory Function
# ─────────────────────────────────────────────────────────────────

class TestCreateOrchestrator:
    """Tests for factory function."""
    
    def test_create_without_auto(self, dockwidget, app, iface):
        """Test create without auto-init."""
        from ui.orchestrator import create_orchestrator
        
        with patch('ui.orchestrator.DockWidgetOrchestrator') as MockOrch:
            mock_instance = Mock()
            MockOrch.return_value = mock_instance
            
            result = create_orchestrator(
                dockwidget, app, iface,
                auto_init=False,
                auto_setup=False
            )
            
            mock_instance.initialize.assert_not_called()
            mock_instance.setup.assert_not_called()
    
    def test_create_with_auto_init(self, dockwidget, app, iface):
        """Test create with auto-init only."""
        from ui.orchestrator import create_orchestrator
        
        with patch('ui.orchestrator.DockWidgetOrchestrator') as MockOrch:
            mock_instance = Mock()
            MockOrch.return_value = mock_instance
            
            result = create_orchestrator(
                dockwidget, app, iface,
                auto_init=True,
                auto_setup=False
            )
            
            mock_instance.initialize.assert_called_once()
            mock_instance.setup.assert_not_called()
    
    def test_create_with_auto_setup(self, dockwidget, app, iface):
        """Test create with auto-init and auto-setup."""
        from ui.orchestrator import create_orchestrator
        
        with patch('ui.orchestrator.DockWidgetOrchestrator') as MockOrch:
            mock_instance = Mock()
            MockOrch.return_value = mock_instance
            
            result = create_orchestrator(
                dockwidget, app, iface,
                auto_init=True,
                auto_setup=True
            )
            
            mock_instance.initialize.assert_called_once()
            mock_instance.setup.assert_called_once()


# ─────────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────────

class TestOrchestratorIntegration:
    """Integration tests for orchestrator."""
    
    def test_full_lifecycle(self, orchestrator):
        """Test full init -> setup -> use -> teardown lifecycle."""
        # Patch all initializations
        with patch.object(orchestrator, '_init_signal_management') as mock_sig:
            with patch.object(orchestrator, '_init_layout_managers') as mock_layout:
                with patch.object(orchestrator, '_init_style_managers') as mock_style:
                    with patch.object(orchestrator, '_init_services') as mock_svc:
                        with patch.object(orchestrator, '_init_controllers') as mock_ctrl:
                            # Initialize
                            result = orchestrator.initialize()
                            assert result is True
                            
                            mock_sig.assert_called_once()
                            mock_layout.assert_called_once()
                            mock_style.assert_called_once()
                            mock_svc.assert_called_once()
                            mock_ctrl.assert_called_once()
        
        # Setup with empty managers/controllers
        orchestrator._layout_managers = {}
        orchestrator._style_managers = {}
        orchestrator._controllers = {}
        orchestrator._signal_manager = None
        
        result = orchestrator.setup()
        assert result is True
        
        # Teardown
        orchestrator._services = {}
        orchestrator._layer_signal_handler = None
        
        orchestrator.teardown()
        assert not orchestrator._initialized
        assert not orchestrator._setup_complete

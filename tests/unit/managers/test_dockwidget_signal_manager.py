"""
Tests for DockwidgetSignalManager.

Refactoring: Unit tests for extracted signal management.
"""

import os
import sys
from unittest.mock import Mock, MagicMock, patch

import pytest


# Add plugin root to path for imports
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, PLUGIN_ROOT)

# Mock QGIS modules before importing
sys.modules['qgis'] = Mock()
sys.modules['qgis.core'] = Mock()
sys.modules['qgis.gui'] = Mock()
sys.modules['qgis.PyQt'] = Mock()
sys.modules['qgis.PyQt.QtCore'] = Mock()
sys.modules['qgis.PyQt.QtCore'].QObject = Mock
sys.modules['qgis.PyQt.QtWidgets'] = Mock()
sys.modules['qgis.PyQt.QtGui'] = Mock()
sys.modules['qgis.utils'] = Mock()
sys.modules['osgeo'] = Mock()
sys.modules['osgeo.ogr'] = Mock()

# Mock infrastructure modules
sys.modules['infrastructure'] = Mock()
sys.modules['infrastructure.logging'] = Mock()
sys.modules['infrastructure.logging'].get_app_logger = Mock(return_value=Mock())


class MockQObject:
    """Mock QObject for testing signal management."""
    
    def __init__(self):
        self._signals_connected = {}
        self._meta_object = Mock()
    
    def metaObject(self):
        return self._meta_object
    
    def isSignalConnected(self, signal):
        return self._signals_connected.get(signal, False)


class MockSignal:
    """Mock PyQt signal for testing."""
    
    def __init__(self):
        self._connected_slots = []
    
    def connect(self, slot):
        self._connected_slots.append(slot)
    
    def disconnect(self, slot=None):
        if slot:
            if slot in self._connected_slots:
                self._connected_slots.remove(slot)
            else:
                raise TypeError("Slot not connected")
        else:
            self._connected_slots.clear()


class MockDockwidget:
    """Mock FilterMateDockWidget for testing."""
    
    def __init__(self):
        self.widgets_initialized = True
        
        # Create widget with featureChanged signal attribute
        single_selection_widget = MockQObject()
        single_selection_widget.featureChanged = MockSignal()
        
        self.widgets = {
            'EXPLORING': {
                'SINGLE_SELECTION_FEATURES': {
                    'WIDGET': single_selection_widget,
                    'SIGNALS': [('featureChanged', Mock())]
                }
            },
            'ACTION': {
                'FILTER': {
                    'WIDGET': Mock(),
                    'SIGNALS': [('clicked', Mock())]
                }
            },
            'QGIS': {
                'LAYER_TREE_VIEW': {
                    'WIDGET': Mock(),
                    'SIGNALS': [('currentLayerChanged', Mock())]
                }
            },
            'FILTERING': {
                'HAS_LAYERS_TO_FILTER': {
                    'WIDGET': Mock(HAS_LAYERS_TO_FILTER=MockSignal()),
                    'SIGNALS': []
                }
            }
        }
        self.project_props = {}
        self.current_layer = None
        self.PROJECT_LAYERS = {}
        
        # Mock button widgets
        self.pushButton_action_filter = Mock()
        self.pushButton_action_filter.clicked = MockSignal()
        self.pushButton_action_unfilter = Mock()
        self.pushButton_action_unfilter.clicked = MockSignal()
        self.pushButton_action_undo_filter = Mock()
        self.pushButton_action_undo_filter.clicked = MockSignal()
        self.pushButton_action_redo_filter = Mock()
        self.pushButton_action_redo_filter.clicked = MockSignal()
        self.pushButton_action_export = Mock()
        self.pushButton_action_export.clicked = MockSignal()
        
        # Mock exploring buttons
        self.pushButton_exploring_identify = Mock()
        self.pushButton_exploring_identify.clicked = MockSignal()
        self.pushButton_exploring_zoom = Mock()
        self.pushButton_exploring_zoom.clicked = MockSignal()
        self.pushButton_exploring_reset_layer_properties = Mock()
        self.pushButton_exploring_reset_layer_properties.clicked = MockSignal()
        self.pushButton_checkable_exploring_selecting = Mock()
        self.pushButton_checkable_exploring_selecting.toggled = MockSignal()
        self.pushButton_checkable_exploring_selecting.isChecked = Mock(return_value=False)
        self.pushButton_checkable_exploring_tracking = Mock()
        self.pushButton_checkable_exploring_tracking.toggled = MockSignal()
        self.pushButton_checkable_exploring_tracking.isChecked = Mock(return_value=False)
        self.pushButton_checkable_exploring_linking = Mock()
        self.pushButton_checkable_exploring_linking.toggled = MockSignal()
        self.pushButton_checkable_exploring_linking.isChecked = Mock(return_value=False)
        
        # Mock groupboxes
        self.mGroupBox_exploring_single_selection = Mock()
        self.mGroupBox_exploring_single_selection.toggled = MockSignal()
        self.mGroupBox_exploring_single_selection.collapsedStateChanged = MockSignal()
        self.mGroupBox_exploring_multiple_selection = Mock()
        self.mGroupBox_exploring_multiple_selection.toggled = MockSignal()
        self.mGroupBox_exploring_multiple_selection.collapsedStateChanged = MockSignal()
        self.mGroupBox_exploring_custom_selection = Mock()
        self.mGroupBox_exploring_custom_selection.toggled = MockSignal()
        self.mGroupBox_exploring_custom_selection.collapsedStateChanged = MockSignal()
        
        # Mock methods
        self.launchTaskEvent = Mock()
        self.exploring_identify_clicked = Mock()
        self.exploring_zoom_clicked = Mock()
        self.resetLayerVariableEvent = Mock()
        self._on_groupbox_clicked = Mock()
        self._on_groupbox_collapse_changed = Mock()
        self._is_layer_valid = Mock(return_value=True)
        self.exploring_select_features = Mock()
        self.exploring_deselect_features = Mock()
        self._ensure_selection_changed_connected = Mock()
        self.exploring_sync_expressions = Mock()
        self._setup_expression_widget_direct_connections = Mock()


# Import the module directly (not through __init__.py to avoid cascading imports)
import importlib.util
spec = importlib.util.spec_from_file_location(
    "dockwidget_signal_manager",
    os.path.join(PLUGIN_ROOT, "ui", "managers", "dockwidget_signal_manager.py")
)
dockwidget_signal_manager_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dockwidget_signal_manager_module)

DockwidgetSignalManager = dockwidget_signal_manager_module.DockwidgetSignalManager
SignalStateChangeError = dockwidget_signal_manager_module.SignalStateChangeError


class TestDockwidgetSignalManager:
    """Tests for DockwidgetSignalManager class."""
    
    @pytest.fixture
    def mock_dockwidget(self):
        """Create a mock dockwidget for testing."""
        return MockDockwidget()
    
    @pytest.fixture
    def manager(self, mock_dockwidget):
        """Create a signal manager with mocked dockwidget."""
        return DockwidgetSignalManager(mock_dockwidget)
    
    def test_initialization(self, manager, mock_dockwidget):
        """Test manager initialization."""
        assert manager.dockwidget is mock_dockwidget
        assert manager._signal_connection_states == {}
        assert manager._layer_tree_view_signal_connected is False
    
    def test_widgets_property(self, manager, mock_dockwidget):
        """Test widgets property accessor."""
        assert manager.widgets is mock_dockwidget.widgets
    
    def test_widgets_initialized_property(self, manager, mock_dockwidget):
        """Test widgets_initialized property accessor."""
        assert manager.widgets_initialized is True
        mock_dockwidget.widgets_initialized = False
        assert manager.widgets_initialized is False
    
    def test_cache_operations(self, manager):
        """Test cache get/set/clear operations."""
        # Initial state - empty cache
        assert manager.get_cache_state("TEST.KEY") is None
        
        # Set state manually
        manager._signal_connection_states["TEST.KEY"] = True
        assert manager.get_cache_state("TEST.KEY") is True
        
        # Clear specific key
        manager.clear_cache("TEST.KEY")
        assert manager.get_cache_state("TEST.KEY") is None
        
        # Set multiple keys
        manager._signal_connection_states["KEY1"] = True
        manager._signal_connection_states["KEY2"] = False
        
        # Clear all
        manager.clear_cache()
        assert manager._signal_connection_states == {}
    
    def test_force_reconnect_action_signals(self, manager, mock_dockwidget):
        """Test force reconnection of ACTION button signals."""
        manager.force_reconnect_action_signals()
        
        # Check that signals were connected
        assert len(mock_dockwidget.pushButton_action_filter.clicked._connected_slots) == 1
        assert len(mock_dockwidget.pushButton_action_unfilter.clicked._connected_slots) == 1
        assert len(mock_dockwidget.pushButton_action_undo_filter.clicked._connected_slots) == 1
        assert len(mock_dockwidget.pushButton_action_redo_filter.clicked._connected_slots) == 1
        assert len(mock_dockwidget.pushButton_action_export.clicked._connected_slots) == 1
        
        # Check cache state
        assert manager.get_cache_state("ACTION.FILTER.clicked") is True
        assert manager.get_cache_state("ACTION.UNFILTER.clicked") is True
    
    def test_force_reconnect_action_signals_triggers_task(self, manager, mock_dockwidget):
        """Test that ACTION button handlers trigger launchTaskEvent."""
        manager.force_reconnect_action_signals()
        
        # Get the connected handler and call it
        filter_handler = mock_dockwidget.pushButton_action_filter.clicked._connected_slots[0]
        filter_handler()
        
        # Verify launchTaskEvent was called with correct task name
        mock_dockwidget.launchTaskEvent.assert_called_once()
        call_args = mock_dockwidget.launchTaskEvent.call_args
        assert call_args[0][1] == 'filter'  # Second arg is task name
    
    def test_connect_widgets_signals(self, manager):
        """Test connecting all widget signals."""
        # This should not raise
        manager.connect_widgets_signals()
    
    def test_disconnect_widgets_signals(self, manager):
        """Test disconnecting all widget signals."""
        # This should not raise
        manager.disconnect_widgets_signals()
    
    def test_disconnect_widgets_signals_empty_widgets(self, manager, mock_dockwidget):
        """Test disconnect with empty widgets dict."""
        mock_dockwidget.widgets = {}
        # Should not raise
        manager.disconnect_widgets_signals()
    
    def test_connect_exploring_buttons_directly(self, manager, mock_dockwidget):
        """Test direct connection of exploring buttons."""
        manager._connect_exploring_buttons_directly()
        
        # Check IDENTIFY button
        assert len(mock_dockwidget.pushButton_exploring_identify.clicked._connected_slots) == 1
        
        # Check ZOOM button
        assert len(mock_dockwidget.pushButton_exploring_zoom.clicked._connected_slots) == 1
        
        # Check RESET button
        assert len(mock_dockwidget.pushButton_exploring_reset_layer_properties.clicked._connected_slots) == 1
        
        # Check toggle buttons
        assert len(mock_dockwidget.pushButton_checkable_exploring_selecting.toggled._connected_slots) == 1
        assert len(mock_dockwidget.pushButton_checkable_exploring_tracking.toggled._connected_slots) == 1
        assert len(mock_dockwidget.pushButton_checkable_exploring_linking.toggled._connected_slots) == 1
    
    def test_connect_groupbox_signals_directly(self, manager, mock_dockwidget):
        """Test direct connection of groupbox signals."""
        manager.connect_groupbox_signals_directly()
        
        # Check that all groupboxes have toggled signals connected
        assert len(mock_dockwidget.mGroupBox_exploring_single_selection.toggled._connected_slots) == 1
        assert len(mock_dockwidget.mGroupBox_exploring_multiple_selection.toggled._connected_slots) == 1
        assert len(mock_dockwidget.mGroupBox_exploring_custom_selection.toggled._connected_slots) == 1
        
        # Check that collapsedStateChanged signals are also connected
        assert len(mock_dockwidget.mGroupBox_exploring_single_selection.collapsedStateChanged._connected_slots) == 1
    
    def test_disconnect_layer_signals_returns_widget_paths(self, manager, mock_dockwidget):
        """Test that disconnect_layer_signals builds correct widget paths list."""
        # Mock manage_signal to avoid actual signal operations
        manager.manage_signal = Mock()
        
        widgets_stopped = manager.disconnect_layer_signals()
        
        # Should return list of widget paths that were processed
        assert isinstance(widgets_stopped, list)
        assert len(widgets_stopped) > 0
        
        # Check that expected widget paths are in the list
        assert ["EXPLORING", "SINGLE_SELECTION_FEATURES"] in widgets_stopped
        assert ["EXPLORING", "ZOOM"] in widgets_stopped
        assert ["FILTERING", "HAS_LAYERS_TO_FILTER"] in widgets_stopped
        
        # Verify manage_signal was called for each widget path
        assert manager.manage_signal.call_count == len(widgets_stopped)
        # Check some expected widget paths
        assert ["EXPLORING", "SINGLE_SELECTION_FEATURES"] in widgets_stopped
        assert ["FILTERING", "HAS_LAYERS_TO_FILTER"] in widgets_stopped


class TestSignalStateChangeError:
    """Tests for SignalStateChangeError exception."""
    
    def test_exception_creation(self):
        """Test exception can be created with proper attributes."""
        error = SignalStateChangeError(None, ["TEST", "WIDGET"], "Test error")
        
        assert error.state is None
        assert error.widget_path == ["TEST", "WIDGET"]
        assert "Test error" in str(error)
    
    def test_exception_default_message(self):
        """Test exception with default message."""
        error = SignalStateChangeError(True, ["CAT", "WIDGET"])
        
        assert "CAT" in str(error)
        assert "WIDGET" in str(error)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

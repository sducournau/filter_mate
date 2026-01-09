"""
Tests for LayerSyncController.

CRITICAL: These tests verify the post-filter protection (CRIT-005 fix).

Story: MIG-073
Phase: 6 - God Class DockWidget Migration
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import time
from pathlib import Path

# Add plugin path for imports
plugin_path = Path(__file__).parents[4]
if str(plugin_path) not in sys.path:
    sys.path.insert(0, str(plugin_path))


class TestLayerSyncController:
    """Tests for LayerSyncController class."""

    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget."""
        dockwidget = Mock()
        dockwidget.plugin_dir = str(plugin_path)
        dockwidget.current_layer = None
        dockwidget.PROJECT_LAYERS = {}
        dockwidget._filter_completed_time = 0
        dockwidget._saved_layer_id_before_filter = None
        dockwidget._filtering_in_progress = False
        dockwidget._updating_current_layer = False
        
        # Mock combobox
        combobox = Mock()
        combobox.currentLayer = Mock(return_value=None)
        combobox.setLayer = Mock()
        combobox.blockSignals = Mock()
        dockwidget.comboBox_filtering_current_layer = combobox
        
        return dockwidget

    @pytest.fixture
    def mock_layer(self):
        """Create mock QgsVectorLayer."""
        layer = Mock()
        layer.id = Mock(return_value="layer_123")
        layer.name = Mock(return_value="Test Layer")
        layer.isValid = Mock(return_value=True)
        return layer

    @pytest.fixture
    def controller(self, mock_dockwidget):
        """Create LayerSyncController instance."""
        from ui.controllers.layer_sync_controller import LayerSyncController
        return LayerSyncController(mock_dockwidget)

    def test_creation(self, mock_dockwidget):
        """Should create controller with dockwidget reference."""
        from ui.controllers.layer_sync_controller import LayerSyncController
        
        controller = LayerSyncController(mock_dockwidget)
        
        assert controller.dockwidget is mock_dockwidget
        assert not controller.is_initialized
        assert controller.current_layer_id is None
        assert not controller.is_within_protection_window

    def test_setup_initializes_controller(self, controller):
        """Setup should initialize the controller."""
        controller.setup()
        
        assert controller.is_initialized

    def test_teardown_clears_state(self, controller):
        """Teardown should clear protection state."""
        controller.setup()
        controller._filter_completed_time = time.time()
        controller._saved_layer_id_before_filter = "layer_123"
        
        controller.teardown()
        
        assert controller._filter_completed_time == 0
        assert controller._saved_layer_id_before_filter is None
        assert not controller.is_initialized


class TestPostFilterProtection:
    """Tests for CRIT-005 post-filter protection."""

    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget."""
        dockwidget = Mock()
        dockwidget.plugin_dir = str(plugin_path)
        dockwidget.current_layer = None
        dockwidget.PROJECT_LAYERS = {}
        dockwidget._filter_completed_time = 0
        dockwidget._saved_layer_id_before_filter = None
        dockwidget._filtering_in_progress = False
        dockwidget._updating_current_layer = False
        dockwidget.comboBox_filtering_current_layer = Mock()
        return dockwidget

    @pytest.fixture
    def mock_layer(self):
        """Create mock QgsVectorLayer."""
        layer = Mock()
        layer.id = Mock(return_value="layer_123")
        layer.name = Mock(return_value="Test Layer")
        layer.isValid = Mock(return_value=True)
        return layer

    @pytest.fixture
    def controller(self, mock_dockwidget, mock_layer):
        """Create controller with active protection."""
        from ui.controllers.layer_sync_controller import LayerSyncController
        controller = LayerSyncController(mock_dockwidget)
        controller.setup()
        return controller

    def test_protection_window_not_active_initially(self, controller):
        """Protection should not be active initially."""
        assert not controller.is_within_protection_window
        assert controller.protection_remaining == 0.0

    def test_mark_filter_completed_activates_protection(self, controller):
        """Mark filter completed should start protection window."""
        controller.mark_filter_completed()
        
        assert controller.is_within_protection_window
        assert controller.protection_remaining > 4.0  # ~5 seconds

    def test_clear_protection_stops_protection(self, controller):
        """Clear protection should stop protection window."""
        controller.mark_filter_completed()
        assert controller.is_within_protection_window
        
        controller.clear_protection()
        
        assert not controller.is_within_protection_window

    def test_save_layer_before_filter(self, controller, mock_layer):
        """Should save layer before filter starts."""
        controller.save_layer_before_filter(mock_layer)
        
        assert controller._saved_layer_id_before_filter == "layer_123"

    def test_block_layer_none_during_protection(self, controller, mock_dockwidget, mock_layer):
        """Should block layer=None during protection window."""
        # Save layer and start protection
        mock_dockwidget.current_layer = mock_layer
        controller.save_layer_before_filter(mock_layer)
        controller.mark_filter_completed()
        
        # Track blocked signals
        signals_received = []
        controller.sync_blocked.connect(lambda r: signals_received.append(r))
        
        # Try to change to None
        result = controller.on_current_layer_changed(None)
        
        assert result is False
        assert len(signals_received) == 1
        assert signals_received[0] == "layer_none_during_protection"

    def test_block_different_layer_during_protection(self, controller, mock_dockwidget, mock_layer):
        """Should block different layer during protection window."""
        # Save layer and start protection
        mock_dockwidget.current_layer = mock_layer
        controller.save_layer_before_filter(mock_layer)
        controller.mark_filter_completed()
        
        # Create different layer
        different_layer = Mock()
        different_layer.id = Mock(return_value="layer_456")
        different_layer.name = Mock(return_value="Different Layer")
        different_layer.isValid = Mock(return_value=True)
        
        # Track blocked signals
        signals_received = []
        controller.sync_blocked.connect(lambda r: signals_received.append(r))
        
        # Try to change to different layer
        result = controller.on_current_layer_changed(different_layer)
        
        assert result is False
        assert len(signals_received) == 1
        assert signals_received[0] == "layer_change_during_protection"

    def test_allow_same_layer_during_protection(self, controller, mock_dockwidget, mock_layer):
        """Should allow same layer during protection window."""
        # Save layer and start protection
        mock_dockwidget.current_layer = mock_layer
        mock_dockwidget.PROJECT_LAYERS = {"layer_123": {}}
        controller.save_layer_before_filter(mock_layer)
        controller.mark_filter_completed()
        
        # Track signals
        signals_received = []
        controller.layer_synchronized.connect(lambda l: signals_received.append(l))
        
        # Change to same layer should succeed
        result = controller.on_current_layer_changed(mock_layer)
        
        assert result is True
        assert len(signals_received) == 1

    def test_block_during_filtering_in_progress(self, controller, mock_layer):
        """Should block layer changes during active filtering."""
        controller.set_filtering_in_progress(True)
        
        signals_received = []
        controller.sync_blocked.connect(lambda r: signals_received.append(r))
        
        result = controller.on_current_layer_changed(mock_layer)
        
        assert result is False
        assert "filtering_in_progress" in signals_received


class TestLayerValidation:
    """Tests for layer validation."""

    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget."""
        dockwidget = Mock()
        dockwidget.plugin_dir = str(plugin_path)
        dockwidget.current_layer = None
        dockwidget.PROJECT_LAYERS = {}
        dockwidget._filter_completed_time = 0
        dockwidget._filtering_in_progress = False
        dockwidget._updating_current_layer = False
        dockwidget.comboBox_filtering_current_layer = Mock()
        return dockwidget

    @pytest.fixture
    def controller(self, mock_dockwidget):
        """Create LayerSyncController instance."""
        from ui.controllers.layer_sync_controller import LayerSyncController
        controller = LayerSyncController(mock_dockwidget)
        controller.setup()
        return controller

    def test_validate_layer_valid(self, controller):
        """Should return True for valid layer."""
        layer = Mock()
        layer.name = Mock(return_value="Test")
        layer.id = Mock(return_value="id_123")
        layer.isValid = Mock(return_value=True)
        
        assert controller.validate_layer(layer) is True

    def test_validate_layer_none(self, controller):
        """Should return False for None."""
        assert controller.validate_layer(None) is False

    def test_validate_layer_invalid(self, controller):
        """Should return False for invalid layer."""
        layer = Mock()
        layer.name = Mock(return_value="Test")
        layer.id = Mock(return_value="id_123")
        layer.isValid = Mock(return_value=False)
        
        assert controller.validate_layer(layer) is False

    def test_validate_layer_deleted(self, controller):
        """Should return False for deleted C++ object."""
        layer = Mock()
        layer.name = Mock(side_effect=RuntimeError("C++ object deleted"))
        
        assert controller.validate_layer(layer) is False


class TestLayerEvents:
    """Tests for layer add/remove events."""

    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget."""
        dockwidget = Mock()
        dockwidget.plugin_dir = str(plugin_path)
        dockwidget.current_layer = None
        dockwidget.PROJECT_LAYERS = {}
        dockwidget._filter_completed_time = 0
        dockwidget._filtering_in_progress = False
        dockwidget._updating_current_layer = False
        dockwidget.comboBox_filtering_current_layer = Mock()
        return dockwidget

    @pytest.fixture
    def mock_layer(self):
        """Create mock QgsVectorLayer."""
        layer = Mock()
        layer.id = Mock(return_value="layer_123")
        layer.name = Mock(return_value="Test Layer")
        layer.isValid = Mock(return_value=True)
        return layer

    @pytest.fixture
    def controller(self, mock_dockwidget):
        """Create LayerSyncController instance."""
        from ui.controllers.layer_sync_controller import LayerSyncController
        controller = LayerSyncController(mock_dockwidget)
        controller.setup()
        return controller

    def test_on_layer_added_sets_current(self, controller, mock_dockwidget, mock_layer):
        """Adding layer when none selected should set as current."""
        mock_dockwidget.current_layer = None
        
        controller.on_layer_added(mock_layer)
        
        assert mock_dockwidget.current_layer is mock_layer

    def test_on_layer_added_ignores_non_vector(self, controller, mock_dockwidget):
        """Should ignore non-vector layers."""
        raster_layer = Mock()  # Not a QgsVectorLayer
        raster_layer.__class__.__name__ = "QgsRasterLayer"
        
        controller.on_layer_added(raster_layer)
        
        assert mock_dockwidget.current_layer is None

    def test_on_layers_will_be_removed_finds_replacement(
        self, controller, mock_dockwidget, mock_layer
    ):
        """Should find replacement when current layer is removed."""
        mock_dockwidget.current_layer = mock_layer
        
        # Create replacement layer
        replacement = Mock()
        replacement.id = Mock(return_value="layer_456")
        replacement.name = Mock(return_value="Replacement")
        replacement.isValid = Mock(return_value=True)
        
        with patch('ui.controllers.layer_sync_controller.QgsProject') as mock_project:
            mock_instance = Mock()
            mock_instance.mapLayers.return_value.values.return_value = [replacement]
            mock_project.instance.return_value = mock_instance
            
            controller.on_layers_will_be_removed(["layer_123"])
            
            assert mock_dockwidget.current_layer is replacement

    def test_on_layer_removed_clears_saved(self, controller):
        """Should clear saved layer if it was removed."""
        controller._saved_layer_id_before_filter = "layer_123"
        
        controller.on_layer_removed("layer_123")
        
        assert controller._saved_layer_id_before_filter is None


class TestSignals:
    """Tests for controller signals."""

    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget."""
        dockwidget = Mock()
        dockwidget.plugin_dir = str(plugin_path)
        dockwidget.current_layer = None
        dockwidget.PROJECT_LAYERS = {"layer_123": {}}
        dockwidget._filter_completed_time = 0
        dockwidget._filtering_in_progress = False
        dockwidget._updating_current_layer = False
        dockwidget.comboBox_filtering_current_layer = Mock()
        return dockwidget

    @pytest.fixture
    def mock_layer(self):
        """Create mock QgsVectorLayer."""
        layer = Mock()
        layer.id = Mock(return_value="layer_123")
        layer.name = Mock(return_value="Test Layer")
        layer.isValid = Mock(return_value=True)
        return layer

    @pytest.fixture
    def controller(self, mock_dockwidget):
        """Create LayerSyncController instance."""
        from ui.controllers.layer_sync_controller import LayerSyncController
        return LayerSyncController(mock_dockwidget)

    def test_layer_synchronized_signal(self, controller, mock_dockwidget, mock_layer):
        """Should emit layer_synchronized on successful change."""
        controller.setup()
        mock_dockwidget.current_layer = mock_layer
        
        signals_received = []
        controller.layer_synchronized.connect(lambda l: signals_received.append(l))
        
        controller.on_current_layer_changed(mock_layer)
        
        assert len(signals_received) == 1
        assert signals_received[0] is mock_layer

    def test_layer_changed_signal(self, controller, mock_dockwidget, mock_layer):
        """Should emit layer_changed on layer change."""
        controller.setup()
        
        signals_received = []
        controller.layer_changed.connect(lambda l: signals_received.append(l))
        
        controller.on_current_layer_changed(mock_layer)
        
        assert len(signals_received) == 1

    def test_sync_blocked_signal(self, controller, mock_dockwidget, mock_layer):
        """Should emit sync_blocked when change is blocked."""
        controller.setup()
        controller.set_filtering_in_progress(True)
        
        signals_received = []
        controller.sync_blocked.connect(lambda r: signals_received.append(r))
        
        controller.on_current_layer_changed(mock_layer)
        
        assert len(signals_received) == 1
        assert signals_received[0] == "filtering_in_progress"

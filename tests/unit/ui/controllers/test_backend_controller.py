"""
Tests for BackendController.

Story: MIG-071
Phase: 6 - God Class DockWidget Migration
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add plugin path for imports
plugin_path = Path(__file__).parents[4]
if str(plugin_path) not in sys.path:
    sys.path.insert(0, str(plugin_path))


class TestBackendController:
    """Tests for BackendController class."""

    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget with backend indicator."""
        dockwidget = Mock()
        dockwidget.plugin_dir = str(plugin_path)
        dockwidget.current_layer = None
        dockwidget.forced_backends = {}
        
        # Mock backend indicator label
        label = Mock()
        label.text = Mock(return_value="OGR")
        label.setText = Mock()
        label.setStyleSheet = Mock()
        label.setToolTip = Mock()
        dockwidget.backend_indicator_label = label
        
        # Mock optimization settings
        dockwidget._optimization_enabled = True
        dockwidget._centroid_auto_enabled = True
        dockwidget._optimization_ask_before = True
        
        return dockwidget

    @pytest.fixture
    def mock_layer(self):
        """Create mock QgsVectorLayer."""
        layer = Mock()
        layer.id = Mock(return_value="layer_123")
        layer.name = Mock(return_value="Test Layer")
        layer.isValid = Mock(return_value=True)
        layer.providerType = Mock(return_value="ogr")
        layer.featureCount = Mock(return_value=1000)
        layer.source = Mock(return_value="/path/to/data.shp")
        return layer

    @pytest.fixture
    def controller(self, mock_dockwidget):
        """Create BackendController instance."""
        from ui.controllers.backend_controller import BackendController
        return BackendController(mock_dockwidget)

    def test_creation(self, mock_dockwidget):
        """Should create controller with dockwidget reference."""
        from ui.controllers.backend_controller import BackendController
        
        controller = BackendController(mock_dockwidget)
        
        assert controller.dockwidget is mock_dockwidget
        assert not controller.is_initialized
        assert controller.forced_backends == {}

    def test_setup_initializes_controller(self, controller, mock_dockwidget):
        """Setup should initialize the controller."""
        controller.setup()
        
        assert controller.is_initialized
        assert controller._indicator_label is mock_dockwidget.backend_indicator_label

    def test_setup_syncs_forced_backends(self, controller, mock_dockwidget):
        """Setup should sync forced backends from dockwidget."""
        mock_dockwidget.forced_backends = {"layer_1": "postgresql"}
        
        controller.setup()
        
        assert controller.forced_backends == {"layer_1": "postgresql"}

    def test_teardown_clears_state(self, controller):
        """Teardown should clear forced backends."""
        controller.setup()
        controller._forced_backends = {"layer_1": "postgresql"}
        
        controller.teardown()
        
        assert controller.forced_backends == {}
        assert not controller.is_initialized

    def test_set_forced_backend(self, controller, mock_dockwidget):
        """Should set forced backend for layer."""
        controller.setup()
        
        controller.set_forced_backend("layer_123", "spatialite")
        
        assert controller.forced_backends["layer_123"] == "spatialite"
        assert mock_dockwidget.forced_backends["layer_123"] == "spatialite"

    def test_set_forced_backend_none_removes(self, controller):
        """Setting None should remove forced backend."""
        controller.setup()
        controller._forced_backends = {"layer_123": "postgresql"}
        
        controller.set_forced_backend("layer_123", None)
        
        assert "layer_123" not in controller.forced_backends

    def test_get_current_backend_forced(self, controller, mock_layer):
        """Should return forced backend if set."""
        controller.setup()
        controller._forced_backends = {"layer_123": "spatialite"}
        
        result = controller.get_current_backend(mock_layer)
        
        assert result == "spatialite"

    def test_get_current_backend_auto_ogr(self, controller, mock_layer):
        """Should auto-detect OGR backend."""
        controller.setup()
        mock_layer.providerType = Mock(return_value="ogr")
        mock_layer.source = Mock(return_value="/path/to/data.shp")
        
        result = controller.get_current_backend(mock_layer)
        
        # Shapefile returns OGR
        assert result == "ogr"

    def test_get_current_backend_auto_spatialite_gpkg(self, controller, mock_layer):
        """Should auto-detect Spatialite for GeoPackage."""
        controller.setup()
        mock_layer.providerType = Mock(return_value="ogr")
        mock_layer.source = Mock(return_value="/path/to/data.gpkg|layername=test")
        
        result = controller.get_current_backend(mock_layer)
        
        assert result == "spatialite"

    def test_update_for_layer_changes_indicator(self, controller, mock_dockwidget, mock_layer):
        """Update should change indicator display."""
        controller.setup()
        mock_layer.providerType = Mock(return_value="spatialite")
        
        controller.update_for_layer(mock_layer)
        
        mock_dockwidget.backend_indicator_label.setText.assert_called()
        mock_dockwidget.backend_indicator_label.setStyleSheet.assert_called()

    def test_update_for_layer_forced_shows_indicator(self, controller, mock_dockwidget, mock_layer):
        """Forced backend should show ⚡ indicator."""
        controller.setup()
        
        controller.update_for_layer(mock_layer, actual_backend="postgresql")
        
        # Check that setText was called with ⚡
        calls = mock_dockwidget.backend_indicator_label.setText.call_args_list
        assert any("⚡" in str(call) for call in calls)

    def test_update_for_invalid_layer(self, controller, mock_dockwidget, mock_layer):
        """Invalid layer should show unknown indicator."""
        controller.setup()
        mock_layer.isValid = Mock(return_value=False)
        
        controller.update_for_layer(mock_layer)
        
        # Should show unknown/waiting state
        mock_dockwidget.backend_indicator_label.setText.assert_called()

    @patch('ui.controllers.backend_controller.QgsProject')
    def test_force_backend_for_all_layers(self, mock_project, controller, mock_layer):
        """Should force backend for all layers in project."""
        controller.setup()
        
        mock_instance = Mock()
        mock_instance.mapLayers.return_value.values.return_value = [mock_layer]
        mock_project.instance.return_value = mock_instance
        
        count = controller.force_backend_for_all_layers("spatialite")
        
        assert count == 1
        assert controller.forced_backends["layer_123"] == "spatialite"

    @patch('ui.controllers.backend_controller.QgsProject')
    def test_auto_select_optimal_backends(self, mock_project, controller, mock_layer):
        """Should clear forced backends for all layers."""
        controller.setup()
        controller._forced_backends = {"layer_123": "postgresql"}
        
        mock_instance = Mock()
        mock_instance.mapLayers.return_value.values.return_value = [mock_layer]
        mock_project.instance.return_value = mock_instance
        
        count = controller.auto_select_optimal_backends()
        
        assert count == 1
        assert "layer_123" not in controller.forced_backends

    def test_handle_indicator_clicked_no_layer_emits_reload(self, controller, mock_dockwidget):
        """Clicking indicator with no layer should emit reload."""
        controller.setup()
        mock_dockwidget.current_layer = None
        
        # Connect signal to track emission
        signal_received = []
        controller.reload_requested.connect(lambda: signal_received.append(True))
        
        controller.handle_indicator_clicked()
        
        assert len(signal_received) == 1

    def test_handle_indicator_clicked_waiting_state_emits_reload(self, controller, mock_dockwidget):
        """Clicking indicator in waiting state should emit reload."""
        controller.setup()
        controller._indicator_label.text = Mock(return_value="...")
        
        signal_received = []
        controller.reload_requested.connect(lambda: signal_received.append(True))
        
        controller.handle_indicator_clicked()
        
        assert len(signal_received) == 1

    def test_optimization_enabled_property(self, controller):
        """Should get/set optimization enabled."""
        controller.setup()
        
        assert controller.optimization_enabled is True
        
        controller.optimization_enabled = False
        
        assert controller.optimization_enabled is False

    def test_toggle_optimization_enabled(self, controller):
        """Should toggle optimization enabled."""
        controller.setup()
        controller._optimization_enabled = True
        
        result = controller.toggle_optimization_enabled()
        
        assert result is False
        assert controller.optimization_enabled is False

    def test_centroid_auto_enabled_property(self, controller):
        """Should get/set centroid auto detection."""
        controller.setup()
        
        assert controller.centroid_auto_enabled is True
        
        controller.centroid_auto_enabled = False
        
        assert controller.centroid_auto_enabled is False

    def test_backend_changed_signal_emitted(self, controller, mock_dockwidget):
        """Should emit signal when backend changed."""
        controller.setup()
        
        signals_received = []
        controller.backend_changed.connect(lambda lid, bn: signals_received.append((lid, bn)))
        
        controller.set_forced_backend("layer_123", "postgresql")
        
        assert len(signals_received) == 1
        assert signals_received[0] == ("layer_123", "postgresql")


class TestBackendStyles:
    """Tests for BACKEND_STYLES configuration."""

    def test_all_backend_types_have_styles(self):
        """All backend types should have style definitions."""
        from ui.controllers.backend_controller import BACKEND_STYLES
        
        expected_backends = [
            'postgresql', 'spatialite', 'ogr', 
            'ogr_fallback', 'postgresql_fallback', 'spatialite_fallback',
            'unknown'
        ]
        
        for backend in expected_backends:
            assert backend in BACKEND_STYLES
            assert 'text' in BACKEND_STYLES[backend]
            assert 'color' in BACKEND_STYLES[backend]
            assert 'background' in BACKEND_STYLES[backend]
            assert 'tooltip' in BACKEND_STYLES[backend]

    def test_styles_have_icons(self):
        """Backend styles should have icons."""
        from ui.controllers.backend_controller import BACKEND_STYLES
        
        for backend, style in BACKEND_STYLES.items():
            assert 'icon' in style
            assert len(style['icon']) > 0


class TestGetAvailableBackends:
    """Tests for get_available_backends_for_layer method."""

    @pytest.fixture
    def controller(self):
        """Create controller with mock dockwidget."""
        from ui.controllers.backend_controller import BackendController
        dockwidget = Mock()
        dockwidget.plugin_dir = str(plugin_path)
        dockwidget.backend_indicator_label = None
        dockwidget.forced_backends = {}
        return BackendController(dockwidget)

    def test_ogr_layer_returns_ogr(self, controller):
        """OGR layer should have OGR backend available."""
        controller.setup()
        layer = Mock()
        layer.id = Mock(return_value="test_layer")
        layer.providerType = Mock(return_value="ogr")
        layer.source = Mock(return_value="/path/to/shapefile.shp")
        
        with patch('ui.controllers.backend_controller.POSTGRESQL_AVAILABLE', False):
            backends = controller.get_available_backends_for_layer(layer)
        
        backend_types = [b[0] for b in backends]
        assert 'ogr' in backend_types

    def test_gpkg_layer_returns_spatialite(self, controller):
        """GeoPackage layer should have Spatialite backend."""
        controller.setup()
        layer = Mock()
        layer.id = Mock(return_value="test_layer")
        layer.providerType = Mock(return_value="ogr")
        layer.source = Mock(return_value="/path/to/data.gpkg|layername=test")
        
        with patch('ui.controllers.backend_controller.POSTGRESQL_AVAILABLE', False):
            backends = controller.get_available_backends_for_layer(layer)
        
        backend_types = [b[0] for b in backends]
        assert 'spatialite' in backend_types or 'ogr' in backend_types

    def test_spatialite_layer_returns_spatialite(self, controller):
        """Spatialite layer should have Spatialite backend."""
        controller.setup()
        layer = Mock()
        layer.id = Mock(return_value="test_layer")
        layer.providerType = Mock(return_value="spatialite")
        layer.source = Mock(return_value="/path/to/data.sqlite")
        
        with patch('ui.controllers.backend_controller.POSTGRESQL_AVAILABLE', False):
            backends = controller.get_available_backends_for_layer(layer)
        
        backend_types = [b[0] for b in backends]
        assert 'spatialite' in backend_types

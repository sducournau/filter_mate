"""
Tests for PropertyController.

Story: MIG-074
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


class TestPropertyController:
    """Tests for PropertyController class."""

    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget."""
        dockwidget = Mock()
        dockwidget.plugin_dir = str(plugin_path)
        dockwidget.widgets_initialized = True
        
        # Mock current layer
        layer = Mock()
        layer.id = Mock(return_value="layer_123")
        layer.name = Mock(return_value="Test Layer")
        dockwidget.current_layer = layer
        
        # Mock PROJECT_LAYERS
        dockwidget.PROJECT_LAYERS = {
            "layer_123": {
                "is": {"is_selecting": False, "is_tracking": False},
                "selection_expression": {"single_expression": ""},
                "filtering": {"has_layers_to_filter": False}
            }
        }
        
        # Mock layer_properties_tuples_dict
        dockwidget.layer_properties_tuples_dict = {
            "is": [
                ("is", "is_selecting"),
                ("is", "is_tracking")
            ],
            "selection_expression": [
                ("selection_expression", "single_expression")
            ],
            "filtering": [
                ("filtering", "has_layers_to_filter"),
                ("filtering", "layers_to_filter")
            ]
        }
        
        # Mock widgets
        dockwidget.widgets = {
            "EXPLORING": {
                "SINGLE_SELECTION_FEATURES": {"WIDGET": Mock()},
                "SINGLE_SELECTION_EXPRESSION": {"WIDGET": Mock()},
                "MULTIPLE_SELECTION_FEATURES": {"WIDGET": Mock()},
                "MULTIPLE_SELECTION_EXPRESSION": {"WIDGET": Mock()},
                "CUSTOM_SELECTION_EXPRESSION": {"WIDGET": Mock()}
            },
            "FILTERING": {
                "HAS_LAYERS_TO_FILTER": {"TYPE": "PushButton", "WIDGET": Mock()}
            }
        }
        
        dockwidget.manageSignal = Mock()
        dockwidget.setLayerVariableEvent = Mock()
        dockwidget.exploring_features_changed = Mock()
        
        return dockwidget

    @pytest.fixture
    def controller(self, mock_dockwidget):
        """Create PropertyController instance."""
        from ui.controllers.property_controller import PropertyController
        return PropertyController(mock_dockwidget)

    def test_creation(self, mock_dockwidget):
        """Should create controller with dockwidget reference."""
        from ui.controllers.property_controller import PropertyController
        
        controller = PropertyController(mock_dockwidget)
        
        assert controller.dockwidget is mock_dockwidget
        assert not controller.is_initialized

    def test_setup_initializes_controller(self, controller):
        """Setup should initialize the controller."""
        controller.setup()
        
        assert controller.is_initialized

    def test_teardown_clears_cache(self, controller):
        """Teardown should clear property type cache."""
        controller.setup()
        controller._property_type_cache['test'] = 'value'
        
        controller.teardown()
        
        assert len(controller._property_type_cache) == 0
        assert not controller.is_initialized


class TestPropertyParsing:
    """Tests for property data parsing."""

    @pytest.fixture
    def mock_dockwidget(self):
        """Create minimal mock dockwidget."""
        dockwidget = Mock()
        dockwidget.plugin_dir = str(plugin_path)
        dockwidget.widgets_initialized = False
        dockwidget.current_layer = None
        return dockwidget

    @pytest.fixture
    def controller(self, mock_dockwidget):
        """Create PropertyController instance."""
        from ui.controllers.property_controller import PropertyController
        return PropertyController(mock_dockwidget)

    def test_parse_dict_data(self, controller):
        """Should parse dict data correctly."""
        data, state = controller._parse_property_data({"key": "value"})
        
        assert data == {"key": "value"}
        assert state is True

    def test_parse_list_data(self, controller):
        """Should parse list data correctly."""
        data, state = controller._parse_property_data([1, 2, 3])
        
        assert data == [1, 2, 3]
        assert state is True

    def test_parse_empty_list(self, controller):
        """Should parse empty list correctly."""
        data, state = controller._parse_property_data([])
        
        assert data == []
        assert state is True

    def test_parse_string_data(self, controller):
        """Should parse string data correctly."""
        data, state = controller._parse_property_data("test value")
        
        assert data == "test value"
        assert state is True

    def test_parse_int_data(self, controller):
        """Should parse int data correctly."""
        data, state = controller._parse_property_data(42)
        
        assert data == 42
        assert state is True

    def test_parse_float_data_truncates(self, controller):
        """Should truncate float to 2 decimal places."""
        data, state = controller._parse_property_data(3.14159)
        
        assert data == 3.14
        assert state is True

    def test_parse_bool_true(self, controller):
        """Should parse boolean true correctly."""
        data, state = controller._parse_property_data(True)
        
        assert data is True
        assert state is True

    def test_parse_bool_false(self, controller):
        """Should parse boolean false correctly."""
        data, state = controller._parse_property_data(False)
        
        assert data is False
        assert state is False

    def test_parse_none(self, controller):
        """Should parse None correctly."""
        data, state = controller._parse_property_data(None)
        
        assert data is None
        assert state is False


class TestPropertyPath:
    """Tests for property path resolution."""

    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget with property definitions."""
        dockwidget = Mock()
        dockwidget.plugin_dir = str(plugin_path)
        dockwidget.layer_properties_tuples_dict = {
            "is": [
                ("is", "is_selecting"),
                ("is", "is_tracking"),
                ("is", "is_linking")
            ],
            "filtering": [
                ("filtering", "has_layers_to_filter"),
                ("filtering", "layers_to_filter")
            ]
        }
        return dockwidget

    @pytest.fixture
    def controller(self, mock_dockwidget):
        """Create PropertyController instance."""
        from ui.controllers.property_controller import PropertyController
        return PropertyController(mock_dockwidget)

    def test_find_is_property(self, controller):
        """Should find 'is' type property."""
        group, path, tuples, index = controller._find_property_path("is_selecting")
        
        assert group == "is"
        assert path == ("is", "is_selecting")
        assert index == 0

    def test_find_filtering_property(self, controller):
        """Should find filtering property."""
        group, path, tuples, index = controller._find_property_path("layers_to_filter")
        
        assert group == "filtering"
        assert path == ("filtering", "layers_to_filter")
        assert index == 1

    def test_find_nonexistent_property(self, controller):
        """Should return None for nonexistent property."""
        group, path, tuples, index = controller._find_property_path("nonexistent")
        
        assert group is None
        assert path is None
        assert tuples is None
        assert index is None


class TestPropertyChanges:
    """Tests for property change operations."""

    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget with full setup."""
        dockwidget = Mock()
        dockwidget.plugin_dir = str(plugin_path)
        dockwidget.widgets_initialized = True
        
        # Mock current layer
        layer = Mock()
        layer.id = Mock(return_value="layer_123")
        layer.name = Mock(return_value="Test Layer")
        dockwidget.current_layer = layer
        
        # Mock PROJECT_LAYERS
        dockwidget.PROJECT_LAYERS = {
            "layer_123": {
                "is": {"is_selecting": False, "is_tracking": False},
                "selection_expression": {"single_expression": ""},
                "filtering": {"has_layers_to_filter": False}
            }
        }
        
        # Mock layer_properties_tuples_dict
        dockwidget.layer_properties_tuples_dict = {
            "is": [
                ("is", "is_selecting"),
                ("is", "is_tracking")
            ],
            "selection_expression": [
                ("selection_expression", "single_expression")
            ]
        }
        
        # Mock widgets
        dockwidget.widgets = {
            "EXPLORING": {
                "SINGLE_SELECTION_FEATURES": {
                    "WIDGET": Mock(featureChanged=Mock())
                },
                "SINGLE_SELECTION_EXPRESSION": {"WIDGET": Mock()},
                "MULTIPLE_SELECTION_FEATURES": {"WIDGET": Mock()},
                "MULTIPLE_SELECTION_EXPRESSION": {"WIDGET": Mock()},
                "CUSTOM_SELECTION_EXPRESSION": {"WIDGET": Mock()}
            }
        }
        
        dockwidget.manageSignal = Mock()
        dockwidget.setLayerVariableEvent = Mock()
        dockwidget.exploring_features_changed = Mock()
        dockwidget.switch_widget_icon = Mock()
        
        return dockwidget

    @pytest.fixture
    def controller(self, mock_dockwidget):
        """Create PropertyController instance."""
        from ui.controllers.property_controller import PropertyController
        controller = PropertyController(mock_dockwidget)
        controller.setup()
        return controller

    def test_change_is_property_to_true(self, controller, mock_dockwidget):
        """Should change 'is' property from False to True."""
        signals_received = []
        controller.property_changed.connect(
            lambda n, new, old: signals_received.append((n, new, old))
        )
        
        result = controller.change_property("is_selecting", True)
        
        assert result is True
        assert mock_dockwidget.PROJECT_LAYERS["layer_123"]["is"]["is_selecting"] is True
        assert len(signals_received) == 1
        assert signals_received[0][1] is True

    def test_change_is_property_no_change(self, controller, mock_dockwidget):
        """Should not change 'is' property when value is same."""
        # Value is already False
        result = controller.change_property("is_selecting", False)
        
        assert result is False  # No change
        assert mock_dockwidget.PROJECT_LAYERS["layer_123"]["is"]["is_selecting"] is False

    def test_change_selection_expression(self, controller, mock_dockwidget):
        """Should change selection expression."""
        result = controller.change_property("single_expression", "field_name")
        
        # Always returns True for selection expressions
        assert result is True
        assert mock_dockwidget.PROJECT_LAYERS["layer_123"]["selection_expression"]["single_expression"] == "field_name"

    def test_change_property_calls_on_change(self, controller, mock_dockwidget):
        """Should call ON_CHANGE callback when property changes."""
        callback_called = []
        custom_functions = {
            "ON_CHANGE": lambda x: callback_called.append("on_change")
        }
        
        controller.change_property("is_selecting", True, custom_functions)
        
        assert "on_change" in callback_called

    def test_change_property_calls_on_true(self, controller, mock_dockwidget):
        """Should call ON_TRUE callback when setting to True."""
        callback_called = []
        custom_functions = {
            "ON_TRUE": lambda x: callback_called.append("on_true")
        }
        
        controller.change_property("is_selecting", True, custom_functions)
        
        assert "on_true" in callback_called

    def test_change_property_without_widgets_initialized(self, controller, mock_dockwidget):
        """Should return False when widgets not initialized."""
        mock_dockwidget.widgets_initialized = False
        
        result = controller.change_property("is_selecting", True)
        
        assert result is False

    def test_change_property_without_current_layer(self, controller, mock_dockwidget):
        """Should return False when no current layer."""
        mock_dockwidget.current_layer = None
        
        result = controller.change_property("is_selecting", True)
        
        assert result is False

    def test_change_property_layer_not_in_project(self, controller, mock_dockwidget):
        """Should emit error when layer not in PROJECT_LAYERS."""
        mock_dockwidget.PROJECT_LAYERS = {}
        
        errors_received = []
        controller.property_error.connect(
            lambda p, e: errors_received.append((p, e))
        )
        
        result = controller.change_property("is_selecting", True)
        
        assert result is False
        assert len(errors_received) == 1
        assert "not in PROJECT_LAYERS" in errors_received[0][1]


class TestBufferStyling:
    """Tests for buffer value styling."""

    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget with buffer spinbox."""
        dockwidget = Mock()
        dockwidget.plugin_dir = str(plugin_path)
        dockwidget.widgets_initialized = True
        
        # Mock buffer spinbox
        spinbox = Mock()
        spinbox.setStyleSheet = Mock()
        spinbox.setToolTip = Mock()
        spinbox.setMinimum = Mock()
        dockwidget.mQgsDoubleSpinBox_filtering_buffer_value = spinbox
        
        # Mock current layer
        layer = Mock()
        layer.id = Mock(return_value="layer_123")
        dockwidget.current_layer = layer
        
        dockwidget.PROJECT_LAYERS = {"layer_123": {}}
        dockwidget.layer_properties_tuples_dict = {}
        dockwidget.widgets = {}
        dockwidget.tr = Mock(side_effect=lambda x: x)
        
        return dockwidget

    @pytest.fixture
    def controller(self, mock_dockwidget):
        """Create PropertyController instance."""
        from ui.controllers.property_controller import PropertyController
        controller = PropertyController(mock_dockwidget)
        controller.setup()
        return controller

    def test_negative_buffer_applies_erosion_style(self, controller, mock_dockwidget):
        """Negative buffer should apply erosion style."""
        signals_received = []
        controller.buffer_style_changed.connect(lambda v: signals_received.append(v))
        
        controller._update_buffer_style(-10.0)
        
        spinbox = mock_dockwidget.mQgsDoubleSpinBox_filtering_buffer_value
        spinbox.setStyleSheet.assert_called_once()
        assert "FFF3CD" in spinbox.setStyleSheet.call_args[0][0]  # Erosion color
        assert len(signals_received) == 1
        assert signals_received[0] == -10.0

    def test_positive_buffer_clears_style(self, controller, mock_dockwidget):
        """Positive buffer should clear style."""
        controller._update_buffer_style(10.0)
        
        spinbox = mock_dockwidget.mQgsDoubleSpinBox_filtering_buffer_value
        spinbox.setStyleSheet.assert_called_with("")

    def test_zero_buffer_clears_style(self, controller, mock_dockwidget):
        """Zero buffer should clear style."""
        controller._update_buffer_style(0.0)
        
        spinbox = mock_dockwidget.mQgsDoubleSpinBox_filtering_buffer_value
        spinbox.setStyleSheet.assert_called_with("")


class TestSignals:
    """Tests for controller signals."""

    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget."""
        dockwidget = Mock()
        dockwidget.plugin_dir = str(plugin_path)
        dockwidget.widgets_initialized = True
        
        layer = Mock()
        layer.id = Mock(return_value="layer_123")
        dockwidget.current_layer = layer
        
        dockwidget.PROJECT_LAYERS = {
            "layer_123": {"is": {"is_selecting": False}}
        }
        dockwidget.layer_properties_tuples_dict = {
            "is": [("is", "is_selecting")]
        }
        dockwidget.widgets = {
            "EXPLORING": {
                "SINGLE_SELECTION_FEATURES": {"WIDGET": Mock()},
                "SINGLE_SELECTION_EXPRESSION": {"WIDGET": Mock()},
                "MULTIPLE_SELECTION_FEATURES": {"WIDGET": Mock()},
                "MULTIPLE_SELECTION_EXPRESSION": {"WIDGET": Mock()},
                "CUSTOM_SELECTION_EXPRESSION": {"WIDGET": Mock()}
            }
        }
        dockwidget.manageSignal = Mock()
        dockwidget.setLayerVariableEvent = Mock()
        
        return dockwidget

    @pytest.fixture
    def controller(self, mock_dockwidget):
        """Create PropertyController instance."""
        from ui.controllers.property_controller import PropertyController
        return PropertyController(mock_dockwidget)

    def test_property_changed_signal(self, controller, mock_dockwidget):
        """Should emit property_changed on successful change."""
        controller.setup()
        
        signals_received = []
        controller.property_changed.connect(
            lambda n, new, old: signals_received.append((n, new, old))
        )
        
        controller.change_property("is_selecting", True)
        
        assert len(signals_received) == 1
        assert signals_received[0] == ("is_selecting", True, False)

    def test_property_validated_signal(self, controller, mock_dockwidget):
        """Should emit property_validated signal."""
        controller.setup()
        
        signals_received = []
        controller.property_validated.connect(
            lambda p, v: signals_received.append((p, v))
        )
        
        controller.change_property("is_selecting", True)
        
        assert len(signals_received) == 1
        assert signals_received[0] == ("is_selecting", True)

    def test_property_error_signal(self, controller, mock_dockwidget):
        """Should emit property_error for invalid property."""
        controller.setup()
        mock_dockwidget.layer_properties_tuples_dict = {}
        
        signals_received = []
        controller.property_error.connect(
            lambda p, e: signals_received.append((p, e))
        )
        
        controller.change_property("nonexistent_property", True)
        
        assert len(signals_received) == 1
        assert "nonexistent_property" in signals_received[0][0]

"""
Unit tests for FilteringController.

Tests the filtering tab controller functionality including
source/target layer selection, predicate configuration,
expression building, filter execution, and undo/redo.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch


def create_filtering_controller(with_service=True, with_undo=True):
    """Create a FilteringController for testing."""
    from ui.controllers.filtering_controller import FilteringController
    
    dockwidget = Mock()
    signal_manager = Mock()
    signal_manager.connect.return_value = "sig_001"
    
    filter_service = Mock() if with_service else None
    undo_manager = Mock() if with_undo else None
    
    controller = FilteringController(
        dockwidget=dockwidget,
        filter_service=filter_service,
        signal_manager=signal_manager,
        undo_manager=undo_manager
    )
    
    return controller


def create_mock_layer(layer_id="layer_123", name="Test Layer", provider="ogr"):
    """Create a mock QGIS vector layer."""
    layer = Mock()
    layer.id.return_value = layer_id
    layer.name.return_value = name
    layer.isValid.return_value = True
    layer.providerType.return_value = provider
    return layer


class TestFilteringControllerInitialization:
    """Tests for controller initialization."""
    
    def test_initialization(self):
        """Test controller initializes correctly."""
        controller = create_filtering_controller()
        
        assert controller.dockwidget is not None
        assert controller.get_source_layer() is None
        assert controller.get_target_layers() == []
        assert controller.get_expression() == ""
    
    def test_initialization_without_service(self):
        """Test controller works without filter service."""
        controller = create_filtering_controller(with_service=False)
        
        assert controller.filter_service is None
        assert controller is not None
    
    def test_default_predicate(self):
        """Test default predicate is INTERSECTS."""
        from ui.controllers.filtering_controller import PredicateType
        
        controller = create_filtering_controller()
        
        assert controller.get_predicate() == PredicateType.INTERSECTS


class TestSourceLayerSelection:
    """Tests for source layer selection."""
    
    def test_set_source_layer(self):
        """Test setting source layer."""
        controller = create_filtering_controller()
        layer = create_mock_layer()
        
        controller.set_source_layer(layer)
        
        assert controller.get_source_layer() is layer
    
    def test_set_source_layer_none(self):
        """Test clearing source layer."""
        controller = create_filtering_controller()
        layer = create_mock_layer()
        
        controller.set_source_layer(layer)
        controller.set_source_layer(None)
        
        assert controller.get_source_layer() is None
    
    def test_source_layer_change_clears_targets(self):
        """Test changing source layer clears target layers."""
        controller = create_filtering_controller()
        
        layer1 = create_mock_layer("layer_1", "Layer 1")
        layer2 = create_mock_layer("layer_2", "Layer 2")
        
        controller.set_source_layer(layer1)
        controller.set_target_layers(["target_1", "target_2"])
        
        controller.set_source_layer(layer2)
        
        assert controller.get_target_layers() == []
    
    def test_on_source_layer_changed_handler(self):
        """Test on_source_layer_changed handler."""
        controller = create_filtering_controller()
        layer = create_mock_layer()
        
        controller.on_source_layer_changed(layer)
        
        assert controller.get_source_layer() is layer
    
    def test_get_current_layer_returns_source(self):
        """Test get_current_layer returns source layer (mixin compat)."""
        controller = create_filtering_controller()
        layer = create_mock_layer()
        
        controller.set_source_layer(layer)
        
        assert controller.get_current_layer() is layer


class TestTargetLayersSelection:
    """Tests for target layers selection."""
    
    def test_set_target_layers(self):
        """Test setting target layers."""
        controller = create_filtering_controller()
        
        controller.set_target_layers(["layer_1", "layer_2"])
        
        assert controller.get_target_layers() == ["layer_1", "layer_2"]
    
    def test_add_target_layer(self):
        """Test adding a target layer."""
        controller = create_filtering_controller()
        
        controller.add_target_layer("layer_1")
        controller.add_target_layer("layer_2")
        
        assert "layer_1" in controller.get_target_layers()
        assert "layer_2" in controller.get_target_layers()
    
    def test_add_duplicate_target_layer(self):
        """Test adding duplicate target is ignored."""
        controller = create_filtering_controller()
        
        controller.add_target_layer("layer_1")
        controller.add_target_layer("layer_1")
        
        assert controller.get_target_layers().count("layer_1") == 1
    
    def test_remove_target_layer(self):
        """Test removing a target layer."""
        controller = create_filtering_controller()
        
        controller.set_target_layers(["layer_1", "layer_2", "layer_3"])
        controller.remove_target_layer("layer_2")
        
        assert controller.get_target_layers() == ["layer_1", "layer_3"]
    
    def test_on_target_layers_changed_handler(self):
        """Test on_target_layers_changed handler."""
        controller = create_filtering_controller()
        
        controller.on_target_layers_changed(["t1", "t2", "t3"])
        
        assert controller.get_target_layers() == ["t1", "t2", "t3"]


class TestPredicateConfiguration:
    """Tests for predicate configuration."""
    
    def test_set_predicate(self):
        """Test setting predicate."""
        from ui.controllers.filtering_controller import PredicateType
        
        controller = create_filtering_controller()
        
        controller.set_predicate(PredicateType.CONTAINS)
        
        assert controller.get_predicate() == PredicateType.CONTAINS
    
    def test_get_available_predicates(self):
        """Test getting available predicates."""
        from ui.controllers.filtering_controller import PredicateType
        
        controller = create_filtering_controller()
        
        predicates = controller.get_available_predicates()
        
        assert len(predicates) == len(PredicateType)
        assert PredicateType.INTERSECTS in predicates
        assert PredicateType.CONTAINS in predicates
    
    def test_on_predicate_changed_handler(self):
        """Test on_predicate_changed handler."""
        from ui.controllers.filtering_controller import PredicateType
        
        controller = create_filtering_controller()
        
        controller.on_predicate_changed("within")
        
        assert controller.get_predicate() == PredicateType.WITHIN
    
    def test_on_predicate_changed_invalid(self):
        """Test on_predicate_changed with invalid value."""
        from ui.controllers.filtering_controller import PredicateType
        
        controller = create_filtering_controller()
        
        controller.on_predicate_changed("invalid_predicate")
        
        # Should keep default
        assert controller.get_predicate() == PredicateType.INTERSECTS


class TestBufferConfiguration:
    """Tests for buffer configuration."""
    
    def test_set_buffer_value(self):
        """Test setting buffer value."""
        controller = create_filtering_controller()
        
        controller.set_buffer_value(100.5)
        
        assert controller.get_buffer_value() == 100.5
    
    def test_set_negative_buffer_value(self):
        """Test negative buffer is converted to 0."""
        controller = create_filtering_controller()
        
        controller.set_buffer_value(-50)
        
        assert controller.get_buffer_value() == 0.0
    
    def test_set_buffer_type(self):
        """Test setting buffer type."""
        from ui.controllers.filtering_controller import BufferType
        
        controller = create_filtering_controller()
        
        controller.set_buffer_type(BufferType.SOURCE)
        
        assert controller.get_buffer_type() == BufferType.SOURCE
    
    def test_on_buffer_changed_handler(self):
        """Test on_buffer_changed handler."""
        from ui.controllers.filtering_controller import BufferType
        
        controller = create_filtering_controller()
        
        controller.on_buffer_changed(250.0, "target")
        
        assert controller.get_buffer_value() == 250.0
        assert controller.get_buffer_type() == BufferType.TARGET


class TestExpressionManagement:
    """Tests for expression building."""
    
    def test_get_expression_initially_empty(self):
        """Test expression is empty initially."""
        controller = create_filtering_controller()
        
        assert controller.get_expression() == ""
    
    def test_set_expression(self):
        """Test setting expression directly."""
        controller = create_filtering_controller()
        
        controller.set_expression("field = 'value'")
        
        assert controller.get_expression() == "field = 'value'"
    
    def test_expression_built_from_config(self):
        """Test expression is built when config changes."""
        controller = create_filtering_controller()
        layer = create_mock_layer()
        
        controller.set_source_layer(layer)
        controller.set_target_layers(["target_1"])
        
        expression = controller.get_expression()
        
        assert "intersects" in expression
        assert "target_1" in expression


class TestFilterConfiguration:
    """Tests for FilterConfiguration dataclass."""
    
    def test_build_configuration(self):
        """Test building configuration object."""
        controller = create_filtering_controller()
        layer = create_mock_layer()
        
        controller.set_source_layer(layer)
        controller.set_target_layers(["t1", "t2"])
        
        config = controller.build_configuration()
        
        assert config.source_layer_id == "layer_123"
        assert config.target_layer_ids == ["t1", "t2"]
    
    def test_configuration_is_valid(self):
        """Test configuration validity check."""
        from ui.controllers.filtering_controller import FilterConfiguration
        
        # Valid config
        valid_config = FilterConfiguration(
            source_layer_id="src_1",
            target_layer_ids=["t1"]
        )
        assert valid_config.is_valid() is True
        
        # Invalid - no source
        invalid_config = FilterConfiguration(
            source_layer_id=None,
            target_layer_ids=["t1"]
        )
        assert invalid_config.is_valid() is False
        
        # Invalid - no targets
        invalid_config2 = FilterConfiguration(
            source_layer_id="src_1",
            target_layer_ids=[]
        )
        assert invalid_config2.is_valid() is False
    
    def test_configuration_to_dict(self):
        """Test configuration serialization."""
        from ui.controllers.filtering_controller import FilterConfiguration, PredicateType
        
        config = FilterConfiguration(
            source_layer_id="src",
            target_layer_ids=["t1"],
            predicate=PredicateType.CONTAINS
        )
        
        data = config.to_dict()
        
        assert data["source_layer_id"] == "src"
        assert data["predicate"] == "contains"
    
    def test_configuration_from_dict(self):
        """Test configuration deserialization."""
        from ui.controllers.filtering_controller import FilterConfiguration, PredicateType
        
        data = {
            "source_layer_id": "src",
            "target_layer_ids": ["t1", "t2"],
            "predicate": "within",
            "buffer_value": 100.0
        }
        
        config = FilterConfiguration.from_dict(data)
        
        assert config.source_layer_id == "src"
        assert config.predicate == PredicateType.WITHIN
        assert config.buffer_value == 100.0


class TestFilterExecution:
    """Tests for filter execution."""
    
    def test_can_execute_valid_config(self):
        """Test can_execute with valid configuration."""
        controller = create_filtering_controller()
        layer = create_mock_layer()
        
        controller.set_source_layer(layer)
        controller.set_target_layers(["t1"])
        
        assert controller.can_execute() is True
    
    def test_can_execute_invalid_config(self):
        """Test can_execute with invalid configuration."""
        controller = create_filtering_controller()
        
        # No source layer
        assert controller.can_execute() is False
    
    def test_execute_filter(self):
        """Test execute filter."""
        controller = create_filtering_controller()
        layer = create_mock_layer()
        
        controller.set_source_layer(layer)
        controller.set_target_layers(["t1"])
        
        result = controller.execute_filter()
        
        assert result is True
    
    def test_get_last_result(self):
        """Test getting last filter result."""
        controller = create_filtering_controller()
        layer = create_mock_layer()
        
        controller.set_source_layer(layer)
        controller.set_target_layers(["t1"])
        controller.execute_filter()
        
        result = controller.get_last_result()
        
        assert result is not None
        assert result.success is True


class TestUndoRedo:
    """Tests for undo/redo functionality."""
    
    def test_initially_no_undo(self):
        """Test no undo available initially."""
        controller = create_filtering_controller()
        
        assert controller.can_undo() is False
        assert controller.get_undo_count() == 0
    
    def test_initially_no_redo(self):
        """Test no redo available initially."""
        controller = create_filtering_controller()
        
        assert controller.can_redo() is False
        assert controller.get_redo_count() == 0
    
    def test_undo_after_filter(self):
        """Test undo is available after filter execution."""
        controller = create_filtering_controller()
        layer = create_mock_layer()
        
        controller.set_source_layer(layer)
        controller.set_target_layers(["t1"])
        controller.execute_filter()
        
        assert controller.can_undo() is True
        assert controller.get_undo_count() == 1
    
    def test_undo_operation(self):
        """Test performing undo."""
        controller = create_filtering_controller()
        layer = create_mock_layer()
        
        controller.set_source_layer(layer)
        controller.set_target_layers(["t1"])
        controller.execute_filter()
        
        result = controller.undo()
        
        assert result is True
        assert controller.can_redo() is True
    
    def test_redo_after_undo(self):
        """Test redo after undo."""
        controller = create_filtering_controller()
        layer = create_mock_layer()
        
        controller.set_source_layer(layer)
        controller.set_target_layers(["t1"])
        controller.execute_filter()
        controller.undo()
        
        result = controller.redo()
        
        assert result is True
    
    def test_clear_history(self):
        """Test clearing history."""
        controller = create_filtering_controller()
        layer = create_mock_layer()
        
        controller.set_source_layer(layer)
        controller.set_target_layers(["t1"])
        controller.execute_filter()
        
        controller.clear_history()
        
        assert controller.can_undo() is False
        assert controller.can_redo() is False


class TestCallbacks:
    """Tests for callback registration."""
    
    def test_register_expression_callback(self):
        """Test registering expression change callback."""
        controller = create_filtering_controller()
        callback_called = []
        
        def on_expr_changed(expr):
            callback_called.append(expr)
        
        controller.register_expression_callback(on_expr_changed)
        controller.set_expression("test = 1")
        
        assert "test = 1" in callback_called
    
    def test_unregister_expression_callback(self):
        """Test unregistering callback."""
        controller = create_filtering_controller()
        callback_called = []
        
        def on_expr_changed(expr):
            callback_called.append(expr)
        
        controller.register_expression_callback(on_expr_changed)
        controller.unregister_expression_callback(on_expr_changed)
        controller.set_expression("test = 1")
        
        assert len(callback_called) == 0
    
    def test_config_callback(self):
        """Test configuration change callback."""
        controller = create_filtering_controller()
        configs_received = []
        
        def on_config_changed(config):
            configs_received.append(config)
        
        controller.register_config_callback(on_config_changed)
        layer = create_mock_layer()
        controller.set_source_layer(layer)
        
        assert len(configs_received) > 0


class TestLifecycle:
    """Tests for controller lifecycle."""
    
    def test_setup(self):
        """Test setup is called without error."""
        controller = create_filtering_controller()
        
        controller.setup()
        
        # No exception = success
    
    def test_teardown(self):
        """Test teardown cleans up state."""
        controller = create_filtering_controller()
        layer = create_mock_layer()
        
        controller.set_source_layer(layer)
        controller.set_target_layers(["t1", "t2"])
        controller.execute_filter()
        
        controller.teardown()
        
        assert controller.get_source_layer() is None
        assert controller.get_target_layers() == []
        assert controller.can_undo() is False
    
    def test_reset(self):
        """Test reset clears all configuration."""
        from ui.controllers.filtering_controller import PredicateType
        
        controller = create_filtering_controller()
        layer = create_mock_layer()
        
        controller.set_source_layer(layer)
        controller.set_target_layers(["t1"])
        controller.set_predicate(PredicateType.CONTAINS)
        controller.set_buffer_value(100)
        
        controller.reset()
        
        assert controller.get_source_layer() is None
        assert controller.get_target_layers() == []
        assert controller.get_predicate() == PredicateType.INTERSECTS
        assert controller.get_buffer_value() == 0.0


class TestRepr:
    """Tests for string representation."""
    
    def test_repr(self):
        """Test repr output."""
        controller = create_filtering_controller()
        layer = create_mock_layer("src_1", "Source Layer")
        
        controller._source_layer = layer
        controller._target_layer_ids = ["t1", "t2"]
        
        repr_str = repr(controller)
        
        assert "FilteringController" in repr_str
        assert "Source Layer" in repr_str
        assert "targets=2" in repr_str


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

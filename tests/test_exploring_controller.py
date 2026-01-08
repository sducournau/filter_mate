"""
Unit tests for ExploringController.

Tests the exploring tab controller functionality.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch


def create_exploring_controller(with_cache=True):
    """Create an ExploringController for testing."""
    from ui.controllers.exploring_controller import ExploringController
    
    dockwidget = Mock()
    filter_service = Mock()
    signal_manager = Mock()
    signal_manager.connect.return_value = "sig_001"
    
    # Mock cache
    if with_cache:
        cache = Mock()
        cache.get.return_value = None
        cache.set.return_value = None
        cache.clear.return_value = None
        cache.get_stats.return_value = {'hits': 0, 'misses': 0}
    else:
        cache = None
    
    controller = ExploringController(
        dockwidget=dockwidget,
        filter_service=filter_service,
        signal_manager=signal_manager,
        features_cache=cache
    )
    
    return controller


class TestExploringControllerInitialization:
    """Tests for controller initialization."""
    
    def test_initialization(self):
        """Test controller initializes correctly."""
        controller = create_exploring_controller()
        
        assert controller.dockwidget is not None
        assert controller._current_layer is None
        assert controller._current_field is None
        assert controller._selected_features == []
    
    def test_initialization_without_cache(self):
        """Test controller works without cache."""
        controller = create_exploring_controller(with_cache=False)
        
        # Should either have no cache or create one
        # Not crash
        assert controller is not None


class TestLayerSelection:
    """Tests for layer selection."""
    
    def test_get_current_layer_initially_none(self):
        """Test current layer is None initially."""
        controller = create_exploring_controller()
        
        assert controller.get_current_layer() is None
    
    def test_set_layer_valid(self):
        """Test setting a valid layer."""
        controller = create_exploring_controller()
        
        layer = Mock()
        layer.id.return_value = 'layer_123'
        layer.name.return_value = 'Test Layer'
        layer.isValid.return_value = True
        layer.providerType.return_value = 'ogr'
        
        controller.set_layer(layer)
        
        assert controller.get_current_layer() is layer
    
    def test_set_layer_none(self):
        """Test setting layer to None."""
        controller = create_exploring_controller()
        
        # First set a layer
        layer = Mock()
        layer.isValid.return_value = True
        controller.set_layer(layer)
        
        # Then clear it
        controller.set_layer(None)
        
        assert controller.get_current_layer() is None
    
    def test_layer_changed_clears_field(self):
        """Test changing layer clears current field."""
        controller = create_exploring_controller()
        
        # Set initial layer and field
        layer1 = Mock()
        layer1.isValid.return_value = True
        controller.set_layer(layer1)
        controller._current_field = 'some_field'
        
        # Change to new layer
        layer2 = Mock()
        layer2.isValid.return_value = True
        controller.set_layer(layer2)
        
        assert controller._current_field is None


class TestFieldSelection:
    """Tests for field selection."""
    
    def test_get_current_field_initially_none(self):
        """Test current field is None initially."""
        controller = create_exploring_controller()
        
        assert controller.get_current_field() is None
    
    def test_set_field(self):
        """Test setting a field."""
        controller = create_exploring_controller()
        
        controller.set_field('test_field')
        
        assert controller.get_current_field() == 'test_field'


class TestSpatialNavigation:
    """Tests for flash/zoom/identify functionality."""
    
    def test_flash_feature_no_layer(self):
        """Test flash feature with no layer set."""
        controller = create_exploring_controller()
        
        result = controller.flash_feature(1)
        
        # Should return False gracefully
        assert result is False
    
    def test_zoom_to_feature_no_layer(self):
        """Test zoom to feature with no layer set."""
        controller = create_exploring_controller()
        
        result = controller.zoom_to_feature(1)
        
        assert result is False
    
    def test_identify_feature_no_layer(self):
        """Test identify feature with no layer set."""
        controller = create_exploring_controller()
        
        result = controller.identify_feature(1)
        
        assert result is False
    
    def test_zoom_to_selected_no_layer(self):
        """Test zoom to selected with no layer set."""
        controller = create_exploring_controller()
        
        result = controller.zoom_to_selected()
        
        assert result is False


class TestMultipleSelection:
    """Tests for multiple feature selection."""
    
    def test_get_selected_features_initially_empty(self):
        """Test selected features is empty initially."""
        controller = create_exploring_controller()
        
        assert controller.get_selected_features() == []
    
    def test_set_selected_features(self):
        """Test setting selected features."""
        controller = create_exploring_controller()
        
        controller.set_selected_features(['value1', 'value2', 'value3'])
        
        assert controller.get_selected_features() == ['value1', 'value2', 'value3']
    
    def test_on_selection_changed(self):
        """Test handling selection change."""
        controller = create_exploring_controller()
        
        controller.on_selection_changed(['a', 'b', 'c'])
        
        assert controller.get_selected_features() == ['a', 'b', 'c']
    
    def test_clear_selection(self):
        """Test clearing selection."""
        controller = create_exploring_controller()
        
        controller.set_selected_features(['value1', 'value2'])
        controller.clear_selection()
        
        assert controller.get_selected_features() == []


class TestCacheManagement:
    """Tests for cache management."""
    
    def test_clear_cache(self):
        """Test cache clearing."""
        controller = create_exploring_controller(with_cache=True)
        
        controller.clear_cache()
        
        controller._features_cache.clear.assert_called_once()
    
    def test_get_cache_stats(self):
        """Test getting cache stats."""
        controller = create_exploring_controller(with_cache=True)
        
        stats = controller.get_cache_stats()
        
        assert 'hits' in stats
        assert 'misses' in stats
    
    def test_cache_stats_without_cache(self):
        """Test cache stats without cache returns empty dict."""
        controller = create_exploring_controller(with_cache=False)
        controller._features_cache = None
        
        stats = controller.get_cache_stats()
        
        assert stats == {}


class TestLifecycle:
    """Tests for controller lifecycle."""
    
    def test_setup(self):
        """Test setup is called without error."""
        controller = create_exploring_controller()
        
        # Should not raise
        controller.setup()
    
    def test_teardown(self):
        """Test teardown cleans up state."""
        controller = create_exploring_controller()
        
        # Set some state
        controller._current_field = 'test'
        controller._selected_features = ['a', 'b']
        
        controller.teardown()
        
        assert controller._current_layer is None
        assert controller._current_field is None
        assert controller._selected_features == []
    
    def test_tab_activated(self):
        """Test tab activation sets active state."""
        controller = create_exploring_controller()
        
        assert not controller.is_active
        
        controller.on_tab_activated()
        
        assert controller.is_active
    
    def test_tab_deactivated(self):
        """Test tab deactivation clears active state."""
        controller = create_exploring_controller()
        controller.on_tab_activated()
        
        controller.on_tab_deactivated()
        
        assert not controller.is_active


class TestLayerSelectionMixin:
    """Tests for LayerSelectionMixin integration."""
    
    def test_is_layer_valid(self):
        """Test layer validation from mixin."""
        controller = create_exploring_controller()
        
        layer = Mock()
        layer.isValid.return_value = True
        
        # Should use mixin method
        result = controller.is_layer_valid(layer)
        
        assert result is True
    
    def test_get_layer_provider_type(self):
        """Test provider type detection from mixin."""
        controller = create_exploring_controller()
        
        layer = Mock()
        layer.providerType.return_value = 'postgres'
        
        result = controller.get_layer_provider_type(layer)
        
        assert result == 'postgresql'


class TestRepr:
    """Tests for string representation."""
    
    def test_repr_no_layer(self):
        """Test repr without layer."""
        controller = create_exploring_controller()
        
        repr_str = repr(controller)
        
        assert 'ExploringController' in repr_str
        assert 'layer=None' in repr_str
    
    def test_repr_with_layer(self):
        """Test repr with layer."""
        controller = create_exploring_controller()
        
        layer = Mock()
        layer.name.return_value = 'MyLayer'
        layer.isValid.return_value = True
        controller._current_layer = layer
        controller._current_field = 'id'
        controller._selected_features = ['a', 'b']
        
        repr_str = repr(controller)
        
        assert 'MyLayer' in repr_str
        assert 'field=id' in repr_str
        assert 'selected=2' in repr_str


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

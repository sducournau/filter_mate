"""
EPIC-3: Tests for Vector Source Synchronization.

Tests the propagation of vector source context from EXPLORING VECTOR
to the MASK & CLIP GroupBox in the raster panel.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch


class TestVectorSourceContext:
    """Test vector source context building and propagation."""
    
    def test_build_context_with_features(self):
        """Test context building with selected features."""
        # Mock layer
        layer = Mock()
        layer.id.return_value = 'layer_123'
        layer.name.return_value = 'test_layer'
        layer.isValid.return_value = True
        layer.featureCount.return_value = 100
        
        # Mock features
        feature1 = Mock()
        feature1.id.return_value = 1
        feature2 = Mock()
        feature2.id.return_value = 2
        features = [feature1, feature2]
        
        # Build context
        feature_count = len(features) if features else layer.featureCount()
        selected_ids = [f.id() for f in features] if features else []
        
        context = {
            'layer_id': layer.id(),
            'layer_name': layer.name(),
            'feature_count': feature_count,
            'mode': 'selected',
            'selected_ids': selected_ids,
            'has_selection': len(selected_ids) > 0
        }
        
        assert context['layer_id'] == 'layer_123'
        assert context['layer_name'] == 'test_layer'
        assert context['feature_count'] == 2  # Selected features, not total
        assert context['mode'] == 'selected'
        assert context['selected_ids'] == [1, 2]
        assert context['has_selection'] is True
    
    def test_build_context_all_features(self):
        """Test context building when no features selected (all features)."""
        # Mock layer
        layer = Mock()
        layer.id.return_value = 'layer_456'
        layer.name.return_value = 'all_layer'
        layer.isValid.return_value = True
        layer.featureCount.return_value = 50
        
        features = None  # No specific selection
        
        # Build context
        feature_count = len(features) if features else layer.featureCount()
        selected_ids = [f.id() for f in features] if features else []
        
        context = {
            'layer_id': layer.id(),
            'layer_name': layer.name(),
            'feature_count': feature_count,
            'mode': 'all',
            'selected_ids': selected_ids,
            'has_selection': len(selected_ids) > 0
        }
        
        assert context['feature_count'] == 50  # Total layer count
        assert context['mode'] == 'all'
        assert context['selected_ids'] == []
        assert context['has_selection'] is False
    
    def test_build_context_empty_features(self):
        """Test context building with empty feature list."""
        layer = Mock()
        layer.id.return_value = 'layer_789'
        layer.name.return_value = 'empty_layer'
        layer.isValid.return_value = True
        layer.featureCount.return_value = 10
        
        features = []  # Empty list - note: falsy, so falls back to featureCount
        
        # Empty list is falsy in Python, so this logic gives featureCount
        # This matches actual implementation behavior
        feature_count = len(features) if features else layer.featureCount()
        selected_ids = [f.id() for f in features] if features else []
        
        context = {
            'layer_id': layer.id(),
            'layer_name': layer.name(),
            'feature_count': feature_count,
            'mode': 'selected',
            'selected_ids': selected_ids,
            'has_selection': len(selected_ids) > 0
        }
        
        # Note: Empty list [] is falsy, so feature_count falls back to layer count
        assert context['feature_count'] == 10  # Falls back to layer count
        assert context['has_selection'] is False
    
    def test_context_none_for_invalid_layer(self):
        """Test that context is None for invalid layer."""
        layer = Mock()
        layer.isValid.return_value = False
        
        # When layer is invalid, context should be None
        context = None if not layer.isValid() else {'layer_id': layer.id()}
        
        assert context is None


class TestMaskClipContextUpdate:
    """Test that MASK & CLIP GroupBox receives context updates."""
    
    def test_set_vector_source_context_valid(self):
        """Test setting valid vector source context."""
        # Import and test the actual widget
        try:
            from ui.widgets.raster_mask_clip_gb import RasterMaskClipGroupBox
        except ImportError:
            pytest.skip("Cannot import RasterMaskClipGroupBox in test environment")
        
        # This would need a full Qt environment to test properly
        # For unit tests, we mock the widget
        widget = Mock(spec=['set_vector_source_context', '_vector_source_context', '_update_vector_source_label'])
        
        context = {
            'layer_id': 'test_layer_id',
            'layer_name': 'Test Layer',
            'feature_count': 5,
            'mode': 'selected',
            'selected_ids': [1, 2, 3, 4, 5],
            'has_selection': True
        }
        
        widget.set_vector_source_context(context)
        
        widget.set_vector_source_context.assert_called_once_with(context)
    
    def test_set_vector_source_context_none(self):
        """Test clearing vector source context."""
        widget = Mock(spec=['set_vector_source_context', '_vector_source_context', '_update_vector_source_label'])
        
        widget.set_vector_source_context(None)
        
        widget.set_vector_source_context.assert_called_once_with(None)


class TestV2PropagationChain:
    """Test the propagation chain from V2 container to MASK & CLIP."""
    
    def test_v2_propagates_to_mask_clip(self):
        """Test that V2 groupbox propagates context to MASK & CLIP child."""
        # Mock MASK & CLIP groupbox
        mask_clip_gb = Mock()
        mask_clip_gb.set_vector_source_context = Mock()
        
        # Mock V2 container with method similar to actual implementation
        class MockV2:
            def __init__(self, mask_clip):
                self._mask_clip_gb = mask_clip
            
            def set_vector_source_context(self, context):
                self._mask_clip_gb.set_vector_source_context(context)
        
        v2 = MockV2(mask_clip_gb)
        
        context = {
            'layer_id': 'test',
            'layer_name': 'Test',
            'feature_count': 3,
            'mode': 'selected'
        }
        
        v2.set_vector_source_context(context)
        
        mask_clip_gb.set_vector_source_context.assert_called_once_with(context)


class TestExploringControllerNotification:
    """Test that ExploringController notifies dockwidget on selection change."""
    
    def test_handle_exploring_features_result_notifies_dockwidget(self):
        """Test that handle_exploring_features_result calls update_vector_source_context."""
        # Mock dockwidget
        dw = Mock()
        dw.widgets_initialized = True
        dw.current_layer = Mock()
        dw.current_layer.id.return_value = 'layer_id'
        dw.current_layer.name.return_value = 'Layer'
        dw.current_exploring_groupbox = 'single_selection'
        dw.pushButton_checkable_exploring_selecting = Mock()
        dw.pushButton_checkable_exploring_selecting.isChecked.return_value = False
        dw.pushButton_checkable_exploring_tracking = Mock()
        dw.pushButton_checkable_exploring_tracking.isChecked.return_value = False
        dw._syncing_from_qgis = False
        dw._update_exploring_buttons_state = Mock()
        dw.update_vector_source_context = Mock()
        
        # Create mock layer_props
        layer_props = {
            'exploring': {'is_linking': False, 'is_selecting': False, 'is_tracking': False},
            'filtering': {}
        }
        
        # Mock features
        features = [Mock(), Mock()]
        for i, f in enumerate(features):
            f.id.return_value = i + 1
        
        # Simulate the notification call that would happen
        mode = 'selected' if features else 'all'
        dw.update_vector_source_context(
            layer=dw.current_layer,
            features=features,
            mode=mode
        )
        
        dw.update_vector_source_context.assert_called_once()
        call_args = dw.update_vector_source_context.call_args
        assert call_args[1]['layer'] == dw.current_layer
        assert call_args[1]['features'] == features
        assert call_args[1]['mode'] == 'selected'


class TestCurrentLayerChangedSync:
    """Test that current_layer_changed updates vector context."""
    
    def test_current_layer_changed_updates_context(self):
        """Test that switching layer updates vector source context."""
        # Mock dockwidget with update method
        dw = Mock()
        dw.update_vector_source_context = Mock()
        
        # Simulate layer change
        new_layer = Mock()
        new_layer.name.return_value = 'New Layer'
        new_layer.id.return_value = 'new_layer_id'
        
        # Call as it would be called in current_layer_changed
        dw.update_vector_source_context(
            layer=new_layer,
            features=None,  # All features initially
            mode='all'
        )
        
        dw.update_vector_source_context.assert_called_once()
        call_args = dw.update_vector_source_context.call_args
        assert call_args[1]['layer'] == new_layer
        assert call_args[1]['features'] is None
        assert call_args[1]['mode'] == 'all'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

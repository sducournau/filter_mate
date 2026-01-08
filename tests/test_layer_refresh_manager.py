"""
Tests for LayerRefreshManager and TaskCompletionMessenger

Unit tests for the extracted layer refresh and messaging modules.
Part of MIG-024 (God Class reduction).
"""

import unittest
from unittest.mock import Mock, MagicMock, patch


class TestLayerRefreshManager(unittest.TestCase):
    """Tests for LayerRefreshManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_iface = MagicMock()
        self.mock_canvas = MagicMock()
        self.mock_iface.mapCanvas.return_value = self.mock_canvas
        self.mock_get_iface = Mock(return_value=self.mock_iface)
        
    def _create_manager(self, **kwargs):
        """Create manager with mocked dependencies."""
        from adapters.layer_refresh_manager import LayerRefreshManager
        
        return LayerRefreshManager(
            get_iface=self.mock_get_iface,
            **kwargs
        )
        
    def test_init_creates_manager(self):
        """Test manager initialization."""
        manager = self._create_manager()
        self.assertIsNotNone(manager)
        
    def test_init_with_custom_thresholds(self):
        """Test manager initialization with custom thresholds."""
        manager = self._create_manager(
            stabilization_ms=500,
            update_extents_threshold=100000
        )
        self.assertEqual(manager._stabilization_ms, 500)
        self.assertEqual(manager._update_extents_threshold, 100000)
        
    def test_refresh_layer_none(self):
        """Test refresh_layer_and_canvas with None layer."""
        manager = self._create_manager()
        
        # Should not raise exception
        manager.refresh_layer_and_canvas(None)
        
    @patch('adapters.layer_refresh_manager.GdalErrorHandler')
    def test_refresh_layer_immediate_for_postgres(self, mock_handler):
        """Test immediate refresh for PostgreSQL layers."""
        manager = self._create_manager()
        
        mock_layer = MagicMock()
        mock_layer.providerType.return_value = 'postgres'
        mock_layer.featureCount.return_value = 100
        
        mock_handler.return_value.__enter__ = Mock()
        mock_handler.return_value.__exit__ = Mock(return_value=False)
        
        manager.refresh_layer_and_canvas(mock_layer)
        
        mock_layer.triggerRepaint.assert_called_once()
        self.mock_canvas.refresh.assert_called()
        
    @patch('adapters.layer_refresh_manager.GdalErrorHandler')
    def test_refresh_layer_skip_update_extents_for_large_layers(self, mock_handler):
        """Test that updateExtents is skipped for large layers."""
        manager = self._create_manager(update_extents_threshold=1000)
        
        mock_layer = MagicMock()
        mock_layer.providerType.return_value = 'postgres'
        mock_layer.featureCount.return_value = 50000  # Above threshold
        
        mock_handler.return_value.__enter__ = Mock()
        mock_handler.return_value.__exit__ = Mock(return_value=False)
        
        manager.refresh_layer_and_canvas(mock_layer)
        
        # updateExtents should NOT be called (layer too large)
        mock_layer.updateExtents.assert_not_called()
        mock_layer.triggerRepaint.assert_called_once()
        
    @patch('adapters.layer_refresh_manager.GdalErrorHandler')
    def test_refresh_layer_calls_update_extents_for_small_layers(self, mock_handler):
        """Test that updateExtents is called for small layers."""
        manager = self._create_manager(update_extents_threshold=1000)
        
        mock_layer = MagicMock()
        mock_layer.providerType.return_value = 'postgres'
        mock_layer.featureCount.return_value = 500  # Below threshold
        
        mock_handler.return_value.__enter__ = Mock()
        mock_handler.return_value.__exit__ = Mock(return_value=False)
        
        manager.refresh_layer_and_canvas(mock_layer)
        
        mock_layer.updateExtents.assert_called_once()
        mock_layer.triggerRepaint.assert_called_once()
        
    def test_refresh_multiple_layers_empty(self):
        """Test refresh_multiple_layers with empty list."""
        manager = self._create_manager()
        
        # Should not raise exception
        manager.refresh_multiple_layers([])
        
    def test_refresh_multiple_layers(self):
        """Test refresh_multiple_layers with layers."""
        manager = self._create_manager()
        
        mock_layer1 = MagicMock()
        mock_layer2 = MagicMock()
        
        manager.refresh_multiple_layers([mock_layer1, mock_layer2])
        
        mock_layer1.updateExtents.assert_called_once()
        mock_layer1.triggerRepaint.assert_called_once()
        mock_layer2.updateExtents.assert_called_once()
        mock_layer2.triggerRepaint.assert_called_once()
        self.mock_canvas.refreshAllLayers.assert_called()
        
    def test_zoom_to_layer_extent_none(self):
        """Test zoom_to_layer_extent with None layer."""
        manager = self._create_manager()
        
        # Should not raise exception
        manager.zoom_to_layer_extent(None)
        
    def test_zoom_to_layer_extent(self):
        """Test zoom_to_layer_extent with valid layer."""
        manager = self._create_manager()
        
        mock_layer = MagicMock()
        mock_extent = MagicMock()
        mock_extent.isEmpty.return_value = False
        mock_layer.extent.return_value = mock_extent
        
        manager.zoom_to_layer_extent(mock_layer)
        
        mock_layer.updateExtents.assert_called_once()
        self.mock_canvas.zoomToFeatureExtent.assert_called_once_with(mock_extent)


class TestTaskCompletionMessenger(unittest.TestCase):
    """Tests for TaskCompletionMessenger class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_show_success = Mock()
        self.mock_show_info = Mock()
        self.mock_should_show = Mock(return_value=True)
        
    def _create_messenger(self):
        """Create messenger with mocked callbacks."""
        from adapters.layer_refresh_manager import TaskCompletionMessenger
        
        return TaskCompletionMessenger(
            show_success_callback=self.mock_show_success,
            show_info_callback=self.mock_show_info,
            should_show_message_callback=self.mock_should_show
        )
        
    def test_init_creates_messenger(self):
        """Test messenger initialization."""
        messenger = self._create_messenger()
        self.assertIsNotNone(messenger)
        
    def test_show_task_completion_filter(self):
        """Test show_task_completion for filter task."""
        messenger = self._create_messenger()
        
        mock_layer = MagicMock()
        mock_layer.featureCount.return_value = 150
        
        messenger.show_task_completion(
            task_name='filter',
            layer=mock_layer,
            provider_type='spatialite',
            layer_count=2,
            is_fallback=False
        )
        
        self.mock_show_success.assert_called_once_with(
            'spatialite', 'filter', 2, False
        )
        self.mock_show_info.assert_called_once()
        
    def test_show_task_completion_unfilter(self):
        """Test show_task_completion for unfilter task."""
        messenger = self._create_messenger()
        
        mock_layer = MagicMock()
        mock_layer.featureCount.return_value = 500
        
        messenger.show_task_completion(
            task_name='unfilter',
            layer=mock_layer,
            provider_type='postgresql',
            layer_count=1,
            is_fallback=False
        )
        
        self.mock_show_success.assert_called_once()
        # Should contain "All filters cleared"
        call_args = self.mock_show_info.call_args[0][0]
        self.assertIn("All filters cleared", call_args)
        
    def test_show_task_completion_respects_should_show(self):
        """Test that show_task_completion respects should_show callback."""
        self.mock_should_show.return_value = False
        messenger = self._create_messenger()
        
        mock_layer = MagicMock()
        mock_layer.featureCount.return_value = 100
        
        messenger.show_task_completion(
            task_name='filter',
            layer=mock_layer,
            provider_type='ogr',
            layer_count=1
        )
        
        # Success message should still be shown
        self.mock_show_success.assert_called_once()
        # But info message should NOT be shown
        self.mock_show_info.assert_not_called()
        
    def test_show_filter_applied(self):
        """Test show_filter_applied message."""
        messenger = self._create_messenger()
        
        messenger.show_filter_applied(
            layer_name="Test Layer",
            feature_count=42,
            expression_preview="population > 1000"
        )
        
        call_args = self.mock_show_info.call_args[0][0]
        self.assertIn("Test Layer", call_args)
        self.assertIn("42", call_args)
        
    def test_show_filter_cleared(self):
        """Test show_filter_cleared message."""
        messenger = self._create_messenger()
        
        messenger.show_filter_cleared(
            layer_name="Test Layer",
            feature_count=1000
        )
        
        call_args = self.mock_show_info.call_args[0][0]
        self.assertIn("Filter cleared", call_args)
        self.assertIn("Test Layer", call_args)


class TestLayerRefreshManagerIntegration(unittest.TestCase):
    """Integration tests for layer refresh manager module."""
    
    def test_module_imports(self):
        """Test that module can be imported."""
        try:
            from adapters.layer_refresh_manager import (
                LayerRefreshManager,
                TaskCompletionMessenger
            )
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import layer_refresh_manager module: {e}")
            
    def test_manager_interface_complete(self):
        """Test that LayerRefreshManager has all required methods."""
        from adapters.layer_refresh_manager import LayerRefreshManager
        
        required_methods = [
            'refresh_layer_and_canvas',
            'refresh_multiple_layers',
            'zoom_to_layer_extent'
        ]
        
        for method in required_methods:
            self.assertTrue(
                hasattr(LayerRefreshManager, method),
                f"Missing method: {method}"
            )
            
    def test_messenger_interface_complete(self):
        """Test that TaskCompletionMessenger has all required methods."""
        from adapters.layer_refresh_manager import TaskCompletionMessenger
        
        required_methods = [
            'show_task_completion',
            'show_filter_applied',
            'show_filter_cleared'
        ]
        
        for method in required_methods:
            self.assertTrue(
                hasattr(TaskCompletionMessenger, method),
                f"Missing method: {method}"
            )


if __name__ == '__main__':
    unittest.main()

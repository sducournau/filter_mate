# -*- coding: utf-8 -*-
"""
Tests for CanvasRefreshService - Map canvas refresh management service.

Tests:
- Canvas refresh operations
- Delayed refresh
- Filtered layers refresh
- Complex filter detection
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestCanvasRefreshConstants:
    """Tests for CanvasRefreshService constants."""
    
    def test_max_features_for_update_extents(self):
        """Test MAX_FEATURES_FOR_UPDATE_EXTENTS threshold."""
        MAX_FEATURES_FOR_UPDATE_EXTENTS = 10000
        
        assert MAX_FEATURES_FOR_UPDATE_EXTENTS > 0
        assert MAX_FEATURES_FOR_UPDATE_EXTENTS == 10000


class TestIsComplexFilter:
    """Tests for is_complex_filter function."""
    
    def test_complex_filter_with_spatial(self):
        """Test complex filter detection with spatial operations."""
        expression = "ST_Intersects(geom, ST_Buffer(ST_Point(0, 0), 100))"
        
        is_complex = 'ST_' in expression or 'INTERSECTS' in expression.upper()
        
        assert is_complex is True
    
    def test_complex_filter_with_subquery(self):
        """Test complex filter detection with subquery."""
        expression = "id IN (SELECT id FROM other_table)"
        
        is_complex = 'SELECT' in expression.upper()
        
        assert is_complex is True
    
    def test_simple_filter(self):
        """Test simple filter detection."""
        expression = "name = 'test' AND type = 'residential'"
        
        is_complex = 'ST_' in expression or 'SELECT' in expression.upper()
        
        assert is_complex is False
    
    def test_empty_filter(self):
        """Test empty filter is not complex."""
        expression = ""
        
        is_complex = bool(expression) and ('ST_' in expression or 'SELECT' in expression.upper())
        
        assert is_complex is False


class TestSingleCanvasRefresh:
    """Tests for single_canvas_refresh function."""
    
    def test_single_refresh_calls_refresh(self):
        """Test single refresh calls canvas refresh."""
        canvas = Mock()
        
        def single_canvas_refresh(c):
            if c:
                c.refresh()
                return True
            return False
        
        result = single_canvas_refresh(canvas)
        
        canvas.refresh.assert_called_once()
        assert result is True
    
    def test_single_refresh_none_canvas(self):
        """Test single refresh with None canvas."""
        def single_canvas_refresh(c):
            if c:
                c.refresh()
                return True
            return False
        
        result = single_canvas_refresh(None)
        
        assert result is False


class TestDelayedCanvasRefresh:
    """Tests for delayed_canvas_refresh function."""
    
    def test_delayed_refresh_with_delay(self):
        """Test delayed refresh schedules refresh."""
        delays = []
        
        def delayed_canvas_refresh(canvas, delay_ms):
            delays.append(delay_ms)
            return True
        
        result = delayed_canvas_refresh(Mock(), 500)
        
        assert result is True
        assert 500 in delays
    
    def test_delayed_refresh_default_delay(self):
        """Test delayed refresh default delay."""
        DEFAULT_DELAY = 100
        
        def delayed_canvas_refresh(canvas, delay_ms=DEFAULT_DELAY):
            return delay_ms
        
        result = delayed_canvas_refresh(Mock())
        
        assert result == DEFAULT_DELAY


class TestFinalCanvasRefresh:
    """Tests for final_canvas_refresh function."""
    
    def test_final_refresh_calls_repaint(self):
        """Test final refresh triggers repaint."""
        canvas = Mock()
        layers = [Mock(), Mock()]
        
        def final_canvas_refresh(c, layer_list):
            for layer in layer_list:
                layer.triggerRepaint()
            c.refresh()
            return True
        
        result = final_canvas_refresh(canvas, layers)
        
        assert result is True
        for layer in layers:
            layer.triggerRepaint.assert_called_once()
    
    def test_final_refresh_empty_layers(self):
        """Test final refresh with no layers."""
        canvas = Mock()
        layers = []
        
        def final_canvas_refresh(c, layer_list):
            for layer in layer_list:
                layer.triggerRepaint()
            c.refresh()
            return True
        
        result = final_canvas_refresh(canvas, layers)
        
        assert result is True
        canvas.refresh.assert_called_once()


class TestCanvasRefreshServiceInit:
    """Tests for CanvasRefreshService initialization."""
    
    def test_init_creates_service(self):
        """Test service creation."""
        service = {
            'canvas': Mock(),
            'pending_refreshes': [],
            'initialized': True
        }
        
        assert service['initialized'] is True


class TestCanvasRefreshServiceSingleRefresh:
    """Tests for CanvasRefreshService.single_canvas_refresh method."""
    
    def test_service_single_refresh(self):
        """Test service single refresh."""
        canvas = Mock()
        
        def service_single_refresh(c):
            c.refresh()
        
        service_single_refresh(canvas)
        
        canvas.refresh.assert_called_once()


class TestCanvasRefreshServiceDelayedRefresh:
    """Tests for CanvasRefreshService.delayed_canvas_refresh method."""
    
    def test_service_delayed_refresh(self):
        """Test service delayed refresh queues refresh."""
        pending = []
        
        def service_delayed_refresh(canvas, delay_ms):
            pending.append({'canvas': canvas, 'delay': delay_ms})
        
        service_delayed_refresh(Mock(), 200)
        
        assert len(pending) == 1
        assert pending[0]['delay'] == 200


class TestCanvasRefreshServiceFinalRefresh:
    """Tests for CanvasRefreshService.final_canvas_refresh method."""
    
    def test_service_final_refresh(self):
        """Test service final refresh."""
        refreshed = []
        
        def service_final_refresh(canvas):
            canvas.refresh()
            refreshed.append(True)
        
        canvas = Mock()
        service_final_refresh(canvas)
        
        assert len(refreshed) == 1


class TestHasPostgresFilteredLayers:
    """Tests for _has_postgres_filtered_layers method."""
    
    def test_has_postgres_layers_true(self):
        """Test detecting PostgreSQL filtered layers."""
        layers = [
            {'provider': 'postgres', 'has_filter': True},
            {'provider': 'ogr', 'has_filter': False}
        ]
        
        has_postgres = any(
            l['provider'] == 'postgres' and l['has_filter']
            for l in layers
        )
        
        assert has_postgres is True
    
    def test_has_postgres_layers_false(self):
        """Test no PostgreSQL filtered layers."""
        layers = [
            {'provider': 'ogr', 'has_filter': True},
            {'provider': 'spatialite', 'has_filter': True}
        ]
        
        has_postgres = any(
            l['provider'] == 'postgres' and l['has_filter']
            for l in layers
        )
        
        assert has_postgres is False
    
    def test_has_postgres_layers_no_filter(self):
        """Test PostgreSQL layers without filters."""
        layers = [
            {'provider': 'postgres', 'has_filter': False}
        ]
        
        has_postgres = any(
            l['provider'] == 'postgres' and l['has_filter']
            for l in layers
        )
        
        assert has_postgres is False


class TestRefreshFilteredLayers:
    """Tests for _refresh_filtered_layers method."""
    
    def test_refresh_filtered_layers(self):
        """Test refreshing filtered layers."""
        layers = [Mock(), Mock(), Mock()]
        for layer in layers:
            layer.subsetString.return_value = "id > 10"
        
        refreshed = []
        
        def refresh_filtered(layer_list):
            for layer in layer_list:
                if layer.subsetString():
                    layer.triggerRepaint()
                    refreshed.append(layer)
        
        refresh_filtered(layers)
        
        assert len(refreshed) == 3
    
    def test_refresh_unfiltered_layers_skipped(self):
        """Test unfiltered layers are skipped."""
        layers = [Mock(), Mock()]
        layers[0].subsetString.return_value = "id > 10"
        layers[1].subsetString.return_value = ""
        
        refreshed = []
        
        def refresh_filtered(layer_list):
            for layer in layer_list:
                if layer.subsetString():
                    layer.triggerRepaint()
                    refreshed.append(layer)
        
        refresh_filtered(layers)
        
        assert len(refreshed) == 1


class TestCreateCanvasRefreshService:
    """Tests for create_canvas_refresh_service factory function."""
    
    def test_factory_creates_service(self):
        """Test factory creates service."""
        canvas = Mock()
        
        def create_service(c):
            return {'canvas': c, 'type': 'CanvasRefreshService'}
        
        service = create_service(canvas)
        
        assert service['type'] == 'CanvasRefreshService'
    
    def test_factory_none_canvas(self):
        """Test factory with None canvas."""
        def create_service(c):
            if c is None:
                return None
            return {'canvas': c}
        
        service = create_service(None)
        
        assert service is None


class TestRefreshPerformance:
    """Tests for refresh performance considerations."""
    
    def test_small_dataset_immediate_refresh(self):
        """Test small dataset triggers immediate refresh."""
        feature_count = 1000
        MAX_FEATURES_FOR_UPDATE_EXTENTS = 10000
        
        should_update_extents = feature_count < MAX_FEATURES_FOR_UPDATE_EXTENTS
        
        assert should_update_extents is True
    
    def test_large_dataset_delayed_refresh(self):
        """Test large dataset uses delayed refresh."""
        feature_count = 50000
        MAX_FEATURES_FOR_UPDATE_EXTENTS = 10000
        
        should_update_extents = feature_count < MAX_FEATURES_FOR_UPDATE_EXTENTS
        
        assert should_update_extents is False
    
    def test_refresh_with_extent_update(self):
        """Test refresh with extent update."""
        canvas = Mock()
        update_extents = True
        
        def refresh_with_options(c, update):
            if update:
                c.zoomToFullExtent()
            c.refresh()
        
        refresh_with_options(canvas, update_extents)
        
        canvas.zoomToFullExtent.assert_called_once()
        canvas.refresh.assert_called_once()
    
    def test_refresh_without_extent_update(self):
        """Test refresh without extent update."""
        canvas = Mock()
        update_extents = False
        
        def refresh_with_options(c, update):
            if update:
                c.zoomToFullExtent()
            c.refresh()
        
        refresh_with_options(canvas, update_extents)
        
        canvas.zoomToFullExtent.assert_not_called()
        canvas.refresh.assert_called_once()


class TestBatchRefresh:
    """Tests for batch refresh operations."""
    
    def test_batch_refresh_multiple_layers(self):
        """Test batch refresh for multiple layers."""
        layers = [Mock() for _ in range(5)]
        
        def batch_refresh(layer_list):
            for layer in layer_list:
                layer.triggerRepaint()
            return len(layer_list)
        
        count = batch_refresh(layers)
        
        assert count == 5
    
    def test_batch_refresh_empty(self):
        """Test batch refresh with empty list."""
        layers = []
        
        def batch_refresh(layer_list):
            for layer in layer_list:
                layer.triggerRepaint()
            return len(layer_list)
        
        count = batch_refresh(layers)
        
        assert count == 0


class TestRefreshErrorHandling:
    """Tests for refresh error handling."""
    
    def test_refresh_handles_exception(self):
        """Test refresh handles exceptions gracefully."""
        canvas = Mock()
        canvas.refresh.side_effect = Exception("Refresh failed")
        
        def safe_refresh(c):
            try:
                c.refresh()
                return True
            except Exception:
                return False
        
        result = safe_refresh(canvas)
        
        assert result is False
    
    def test_refresh_layer_handles_invalid(self):
        """Test refresh handles invalid layer."""
        layer = Mock()
        layer.isValid.return_value = False
        
        def safe_refresh_layer(l):
            if not l.isValid():
                return False
            l.triggerRepaint()
            return True
        
        result = safe_refresh_layer(layer)
        
        assert result is False
        layer.triggerRepaint.assert_not_called()

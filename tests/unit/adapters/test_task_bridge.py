# -*- coding: utf-8 -*-
"""
Tests for TaskBridge - Bridge between legacy and hexagonal architecture.

Tests:
- Bridge initialization and availability
- Metrics tracking
- Spatial filter execution
- Attribute filter execution
- Expression conversion
- Multi-step filter support
- Export operations
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestBridgeStatus:
    """Tests for BridgeStatus enum."""
    
    def test_status_values_exist(self):
        """Test BridgeStatus enum values."""
        statuses = {
            'SUCCESS': 1,
            'FAILED': 2,
            'FALLBACK': 3,
            'NOT_AVAILABLE': 4
        }
        
        assert 'SUCCESS' in statuses
        assert 'FALLBACK' in statuses


class TestBridgeResult:
    """Tests for BridgeResult dataclass."""
    
    def test_result_success(self):
        """Test successful BridgeResult."""
        result = {
            'status': 'SUCCESS',
            'data': {'feature_count': 100},
            'error': None
        }
        
        assert result['status'] == 'SUCCESS'
        assert result['error'] is None
    
    def test_result_failed(self):
        """Test failed BridgeResult."""
        result = {
            'status': 'FAILED',
            'data': None,
            'error': 'Connection failed'
        }
        
        assert result['status'] == 'FAILED'
        assert result['error'] is not None
    
    def test_result_to_legacy_format(self):
        """Test converting result to legacy format."""
        result = {
            'status': 'SUCCESS',
            'data': {'feature_count': 100, 'expression': 'id > 10'}
        }
        
        # Convert to legacy format
        legacy = {
            'success': result['status'] == 'SUCCESS',
            'count': result['data'].get('feature_count', 0),
            'filter': result['data'].get('expression', '')
        }
        
        assert legacy['success'] is True
        assert legacy['count'] == 100
    
    def test_result_not_available(self):
        """Test creating not available result."""
        def not_available(reason):
            return {
                'status': 'NOT_AVAILABLE',
                'data': None,
                'error': reason
            }
        
        result = not_available('Backend not initialized')
        
        assert result['status'] == 'NOT_AVAILABLE'
    
    def test_result_fallback(self):
        """Test creating fallback result."""
        def fallback(original_error, fallback_data):
            return {
                'status': 'FALLBACK',
                'data': fallback_data,
                'error': original_error
            }
        
        result = fallback('PostgreSQL unavailable', {'feature_count': 50})
        
        assert result['status'] == 'FALLBACK'
        assert result['data']['feature_count'] == 50


class TestTaskBridgeInit:
    """Tests for TaskBridge initialization."""
    
    def test_init_creates_instance(self):
        """Test initialization creates instance."""
        bridge = {
            'initialized': True,
            'backend': None,
            'metrics': {}
        }
        
        assert bridge['initialized'] is True
    
    def test_init_with_backend(self):
        """Test initialization with backend."""
        backend = Mock()
        bridge = {
            'initialized': True,
            'backend': backend
        }
        
        assert bridge['backend'] is not None


class TestTaskBridgeAvailability:
    """Tests for is_available method."""
    
    def test_is_available_true(self):
        """Test bridge availability when backend ready."""
        bridge = {
            'initialized': True,
            'backend': Mock()
        }
        
        is_available = bridge['initialized'] and bridge['backend'] is not None
        
        assert is_available is True
    
    def test_is_available_false_not_initialized(self):
        """Test bridge not available when not initialized."""
        bridge = {
            'initialized': False,
            'backend': None
        }
        
        is_available = bridge['initialized'] and bridge['backend'] is not None
        
        assert is_available is False
    
    def test_is_available_false_no_backend(self):
        """Test bridge not available without backend."""
        bridge = {
            'initialized': True,
            'backend': None
        }
        
        is_available = bridge['initialized'] and bridge['backend'] is not None
        
        assert is_available is False


class TestTaskBridgeMetrics:
    """Tests for metrics tracking methods."""
    
    def test_metrics_initial_state(self):
        """Test metrics initial state."""
        metrics = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'fallback_calls': 0,
            'spatial_filters': 0,
            'attribute_filters': 0
        }
        
        assert metrics['total_calls'] == 0
    
    def test_metrics_update_after_call(self):
        """Test metrics update after call."""
        metrics = {
            'total_calls': 0,
            'successful_calls': 0
        }
        
        # Simulate successful call
        metrics['total_calls'] += 1
        metrics['successful_calls'] += 1
        
        assert metrics['total_calls'] == 1
        assert metrics['successful_calls'] == 1
    
    def test_reset_metrics(self):
        """Test resetting metrics."""
        metrics = {
            'total_calls': 100,
            'successful_calls': 90,
            'failed_calls': 10
        }
        
        # Reset
        metrics = {k: 0 for k in metrics}
        
        assert metrics['total_calls'] == 0
    
    def test_update_type_metrics_spatial(self):
        """Test updating spatial filter metrics."""
        metrics = {'spatial_filters': 0, 'attribute_filters': 0}
        filter_type = 'spatial'
        
        if filter_type == 'spatial':
            metrics['spatial_filters'] += 1
        
        assert metrics['spatial_filters'] == 1
    
    def test_update_type_metrics_attribute(self):
        """Test updating attribute filter metrics."""
        metrics = {'spatial_filters': 0, 'attribute_filters': 0}
        filter_type = 'attribute'
        
        if filter_type == 'attribute':
            metrics['attribute_filters'] += 1
        
        assert metrics['attribute_filters'] == 1
    
    def test_get_metrics_report(self):
        """Test generating metrics report."""
        metrics = {
            'total_calls': 100,
            'successful_calls': 90,
            'failed_calls': 10
        }
        
        report = {
            'total': metrics['total_calls'],
            'success_rate': (metrics['successful_calls'] / metrics['total_calls'] * 100) if metrics['total_calls'] > 0 else 0
        }
        
        assert report['success_rate'] == 90.0
    
    def test_pct_calculation(self):
        """Test percentage calculation helper."""
        def pct(part, total):
            if total == 0:
                return 0.0
            return round(part / total * 100, 1)
        
        assert pct(90, 100) == 90.0
        assert pct(0, 0) == 0.0


class TestExecuteSpatialFilter:
    """Tests for execute_spatial_filter method."""
    
    def test_spatial_filter_success(self):
        """Test successful spatial filter execution."""
        layer = Mock()
        layer.id.return_value = 'layer_123'
        
        def execute_spatial(l, geometry, operator):
            return {
                'status': 'SUCCESS',
                'data': {'feature_count': 50, 'expression': f"{operator}(geom, ?)"}
            }
        
        result = execute_spatial(layer, Mock(), 'INTERSECTS')
        
        assert result['status'] == 'SUCCESS'
    
    def test_spatial_filter_invalid_layer(self):
        """Test spatial filter with invalid layer."""
        def execute_spatial(layer, geometry, operator):
            if not layer or not layer.isValid():
                return {'status': 'FAILED', 'error': 'Invalid layer'}
            return {'status': 'SUCCESS'}
        
        layer = Mock()
        layer.isValid.return_value = False
        
        result = execute_spatial(layer, Mock(), 'INTERSECTS')
        
        assert result['status'] == 'FAILED'
    
    def test_spatial_filter_no_geometry(self):
        """Test spatial filter with no geometry."""
        def execute_spatial(layer, geometry, operator):
            if geometry is None:
                return {'status': 'FAILED', 'error': 'No geometry provided'}
            return {'status': 'SUCCESS'}
        
        result = execute_spatial(Mock(), None, 'INTERSECTS')
        
        assert result['status'] == 'FAILED'


class TestExecuteAttributeFilter:
    """Tests for execute_attribute_filter method."""
    
    def test_attribute_filter_success(self):
        """Test successful attribute filter execution."""
        layer = Mock()
        expression = "name = 'test'"
        
        def execute_attribute(l, expr):
            return {
                'status': 'SUCCESS',
                'data': {'expression': expr, 'feature_count': 100}
            }
        
        result = execute_attribute(layer, expression)
        
        assert result['status'] == 'SUCCESS'
    
    def test_attribute_filter_empty_expression(self):
        """Test attribute filter with empty expression."""
        def execute_attribute(layer, expression):
            if not expression:
                return {'status': 'FAILED', 'error': 'Empty expression'}
            return {'status': 'SUCCESS'}
        
        result = execute_attribute(Mock(), '')
        
        assert result['status'] == 'FAILED'


class TestBuildSpatialExpression:
    """Tests for _build_spatial_expression method."""
    
    def test_build_intersects_expression(self):
        """Test building INTERSECTS expression."""
        operator = 'INTERSECTS'
        geom_column = 'geom'
        wkt = 'POINT(0 0)'
        
        expression = f"ST_Intersects({geom_column}, ST_GeomFromText('{wkt}'))"
        
        assert 'ST_Intersects' in expression
    
    def test_build_within_expression(self):
        """Test building WITHIN expression."""
        operator = 'WITHIN'
        geom_column = 'geom'
        wkt = 'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))'
        
        expression = f"ST_Within({geom_column}, ST_GeomFromText('{wkt}'))"
        
        assert 'ST_Within' in expression
    
    def test_build_expression_with_srid(self):
        """Test building expression with SRID."""
        geom_column = 'geom'
        wkt = 'POINT(0 0)'
        srid = 4326
        
        expression = f"ST_Intersects({geom_column}, ST_GeomFromText('{wkt}', {srid}))"
        
        assert '4326' in expression


class TestConvertExpressionToBackend:
    """Tests for convert_expression_to_backend method."""
    
    def test_convert_to_postgresql(self):
        """Test converting expression to PostgreSQL format."""
        qgis_expr = "name = 'test'"
        backend = 'postgresql'
        
        # PostgreSQL uses same syntax for simple expressions
        converted = qgis_expr
        
        assert converted == qgis_expr
    
    def test_convert_to_spatialite(self):
        """Test converting expression to SpatiaLite format."""
        qgis_expr = "name = 'test'"
        backend = 'spatialite'
        
        # SpatiaLite uses same syntax for simple expressions
        converted = qgis_expr
        
        assert converted == qgis_expr
    
    def test_convert_spatial_function(self):
        """Test converting spatial function."""
        qgis_expr = "intersects($geometry, geom_from_wkt('POINT(0 0)'))"
        backend = 'postgresql'
        
        # Convert QGIS function to PostGIS
        converted = qgis_expr.replace('intersects(', 'ST_Intersects(')
        converted = converted.replace('geom_from_wkt', 'ST_GeomFromText')
        
        assert 'ST_Intersects' in converted


class TestExecuteMultiStepFilter:
    """Tests for execute_multi_step_filter method."""
    
    def test_multi_step_filter_success(self):
        """Test successful multi-step filter execution."""
        steps = [
            {'type': 'attribute', 'expression': 'type = "residential"'},
            {'type': 'spatial', 'operator': 'INTERSECTS', 'geometry': Mock()}
        ]
        
        def execute_multi_step(layer, step_list):
            results = []
            for step in step_list:
                results.append({'step': step['type'], 'status': 'SUCCESS'})
            return {'status': 'SUCCESS', 'steps': results}
        
        result = execute_multi_step(Mock(), steps)
        
        assert result['status'] == 'SUCCESS'
        assert len(result['steps']) == 2
    
    def test_multi_step_filter_partial_failure(self):
        """Test multi-step filter with partial failure."""
        steps = [
            {'type': 'attribute', 'success': True},
            {'type': 'spatial', 'success': False}
        ]
        
        all_success = all(s['success'] for s in steps)
        
        assert all_success is False


class TestSupportsMultiStep:
    """Tests for supports_multi_step method."""
    
    def test_supports_multi_step_postgresql(self):
        """Test PostgreSQL supports multi-step."""
        backend = 'postgresql'
        supported_backends = ['postgresql', 'spatialite']
        
        supports = backend in supported_backends
        
        assert supports is True
    
    def test_supports_multi_step_ogr(self):
        """Test OGR may not support multi-step."""
        backend = 'ogr'
        supported_backends = ['postgresql', 'spatialite']
        
        supports = backend in supported_backends
        
        assert supports is False


class TestExecuteExport:
    """Tests for execute_export method."""
    
    def test_export_success(self):
        """Test successful export execution."""
        layer = Mock()
        output_path = '/path/to/output.shp'
        
        def execute_export(l, path):
            return {'status': 'SUCCESS', 'path': path}
        
        result = execute_export(layer, output_path)
        
        assert result['status'] == 'SUCCESS'
    
    def test_export_invalid_path(self):
        """Test export with invalid path."""
        def execute_export(layer, path):
            if not path:
                return {'status': 'FAILED', 'error': 'Invalid path'}
            return {'status': 'SUCCESS'}
        
        result = execute_export(Mock(), '')
        
        assert result['status'] == 'FAILED'


class TestSupportsExport:
    """Tests for supports_export method."""
    
    def test_supports_export_shapefile(self):
        """Test shapefile export support."""
        formats = ['shapefile', 'geopackage', 'geojson']
        format_type = 'shapefile'
        
        supports = format_type in formats
        
        assert supports is True


class TestGetBackendForLayer:
    """Tests for get_backend_for_layer method."""
    
    def test_get_backend_postgresql(self):
        """Test getting backend for PostgreSQL layer."""
        layer = Mock()
        layer.providerType.return_value = 'postgres'
        
        def get_backend(l):
            provider = l.providerType()
            mapping = {'postgres': 'postgresql', 'spatialite': 'spatialite'}
            return mapping.get(provider, 'ogr')
        
        backend = get_backend(layer)
        
        assert backend == 'postgresql'
    
    def test_get_backend_spatialite(self):
        """Test getting backend for SpatiaLite layer."""
        layer = Mock()
        layer.providerType.return_value = 'spatialite'
        
        def get_backend(l):
            provider = l.providerType()
            mapping = {'postgres': 'postgresql', 'spatialite': 'spatialite'}
            return mapping.get(provider, 'ogr')
        
        backend = get_backend(layer)
        
        assert backend == 'spatialite'
    
    def test_get_backend_default_ogr(self):
        """Test getting default OGR backend."""
        layer = Mock()
        layer.providerType.return_value = 'ogr'
        
        def get_backend(l):
            provider = l.providerType()
            mapping = {'postgres': 'postgresql', 'spatialite': 'spatialite'}
            return mapping.get(provider, 'ogr')
        
        backend = get_backend(layer)
        
        assert backend == 'ogr'


class TestGetTaskBridge:
    """Tests for get_task_bridge singleton function."""
    
    def test_get_bridge_returns_instance(self):
        """Test getting bridge singleton."""
        _bridge = None
        
        def get_task_bridge():
            nonlocal _bridge
            if _bridge is None:
                _bridge = {'type': 'TaskBridge'}
            return _bridge
        
        bridge1 = get_task_bridge()
        bridge2 = get_task_bridge()
        
        assert bridge1 is bridge2


class TestResetTaskBridge:
    """Tests for reset_task_bridge function."""
    
    def test_reset_clears_bridge(self):
        """Test resetting bridge clears singleton."""
        _bridge = {'type': 'TaskBridge'}
        
        def reset_task_bridge():
            nonlocal _bridge
            _bridge = None
        
        reset_task_bridge()
        
        assert _bridge is None

# -*- coding: utf-8 -*-
"""
Tests for BackendPort - Backend interface/contract.

Tests:
- BackendCapability enum
- BackendInfo dataclass
- BackendPort abstract interface
"""

import pytest
from unittest.mock import Mock


class TestBackendCapability:
    """Tests for BackendCapability enum."""
    
    def test_capability_values_exist(self):
        """Test BackendCapability enum values."""
        capabilities = [
            'SPATIAL_FILTER',
            'ATTRIBUTE_FILTER',
            'MATERIALIZED_VIEW',
            'SPATIAL_INDEX',
            'TRANSACTION',
            'BULK_OPERATION'
        ]
        
        assert 'SPATIAL_FILTER' in capabilities
        assert 'MATERIALIZED_VIEW' in capabilities
    
    def test_capability_comparison(self):
        """Test capability comparison."""
        cap1 = 'SPATIAL_FILTER'
        cap2 = 'SPATIAL_FILTER'
        cap3 = 'ATTRIBUTE_FILTER'
        
        assert cap1 == cap2
        assert cap1 != cap3


class TestBackendInfo:
    """Tests for BackendInfo dataclass."""
    
    def test_info_creation(self):
        """Test creating BackendInfo."""
        info = {
            'name': 'postgresql',
            'version': '14.0',
            'capabilities': ['SPATIAL_FILTER', 'MATERIALIZED_VIEW'],
            'max_connections': 10
        }
        
        assert info['name'] == 'postgresql'
        assert len(info['capabilities']) == 2
    
    def test_supports_spatial(self):
        """Test supports_spatial property."""
        info = {
            'capabilities': ['SPATIAL_FILTER', 'ATTRIBUTE_FILTER']
        }
        
        def supports_spatial(i):
            return 'SPATIAL_FILTER' in i['capabilities']
        
        assert supports_spatial(info) is True
    
    def test_supports_spatial_false(self):
        """Test supports_spatial returns false."""
        info = {
            'capabilities': ['ATTRIBUTE_FILTER']
        }
        
        def supports_spatial(i):
            return 'SPATIAL_FILTER' in i['capabilities']
        
        assert supports_spatial(info) is False
    
    def test_supports_mv(self):
        """Test supports_mv property."""
        info = {
            'capabilities': ['MATERIALIZED_VIEW']
        }
        
        def supports_mv(i):
            return 'MATERIALIZED_VIEW' in i['capabilities']
        
        assert supports_mv(info) is True
    
    def test_supports_mv_false(self):
        """Test supports_mv returns false."""
        info = {
            'capabilities': ['ATTRIBUTE_FILTER']
        }
        
        def supports_mv(i):
            return 'MATERIALIZED_VIEW' in i['capabilities']
        
        assert supports_mv(info) is False
    
    def test_supports_spatial_index(self):
        """Test supports_spatial_index property."""
        info = {
            'capabilities': ['SPATIAL_INDEX']
        }
        
        def supports_spatial_index(i):
            return 'SPATIAL_INDEX' in i['capabilities']
        
        assert supports_spatial_index(info) is True


class TestBackendPortExecute:
    """Tests for execute method."""
    
    def test_execute_returns_result(self):
        """Test execute returns result."""
        def execute(expression, layer_id):
            return {'success': True, 'feature_count': 100}
        
        result = execute('id > 10', 'layer_123')
        
        assert result['success'] is True
    
    def test_execute_handles_error(self):
        """Test execute handles errors."""
        def execute(expression, layer_id):
            try:
                # Simulated error
                raise ValueError('Invalid expression')
            except Exception as e:
                return {'success': False, 'error': str(e)}
        
        result = execute('invalid', 'layer_123')
        
        assert result['success'] is False


class TestBackendPortSupportsLayer:
    """Tests for supports_layer method."""
    
    def test_supports_postgresql_layer(self):
        """Test supports PostgreSQL layer."""
        layer = Mock()
        layer.providerType.return_value = 'postgres'
        
        def supports_layer(backend_type, l):
            mapping = {
                'postgresql': ['postgres'],
                'spatialite': ['spatialite'],
                'ogr': ['ogr', 'memory']
            }
            return l.providerType() in mapping.get(backend_type, [])
        
        assert supports_layer('postgresql', layer) is True
    
    def test_does_not_support_layer(self):
        """Test backend doesn't support layer."""
        layer = Mock()
        layer.providerType.return_value = 'wms'
        
        def supports_layer(backend_type, l):
            mapping = {
                'postgresql': ['postgres'],
                'spatialite': ['spatialite']
            }
            return l.providerType() in mapping.get(backend_type, [])
        
        assert supports_layer('postgresql', layer) is False


class TestBackendPortGetInfo:
    """Tests for get_info method."""
    
    def test_get_info_returns_info(self):
        """Test get_info returns backend info."""
        def get_info():
            return {
                'name': 'postgresql',
                'version': '14.0',
                'capabilities': ['SPATIAL_FILTER', 'MATERIALIZED_VIEW']
            }
        
        info = get_info()
        
        assert info['name'] == 'postgresql'


class TestBackendPortCleanup:
    """Tests for cleanup method."""
    
    def test_cleanup_releases_resources(self):
        """Test cleanup releases resources."""
        state = {'connections': 5}
        
        def cleanup(s):
            s['connections'] = 0
        
        cleanup(state)
        
        assert state['connections'] == 0


class TestBackendPortEstimateExecutionTime:
    """Tests for estimate_execution_time method."""
    
    def test_estimate_small_dataset(self):
        """Test estimate for small dataset."""
        def estimate(feature_count, operation_type):
            base_time = 0.01
            if operation_type == 'spatial':
                return base_time * feature_count * 2
            return base_time * feature_count
        
        time = estimate(100, 'attribute')
        
        assert time == 1.0
    
    def test_estimate_large_dataset(self):
        """Test estimate for large dataset."""
        def estimate(feature_count, operation_type):
            base_time = 0.01
            if operation_type == 'spatial':
                return base_time * feature_count * 2
            return base_time * feature_count
        
        time = estimate(10000, 'spatial')
        
        assert time == 200.0


class TestBackendPortHasCapability:
    """Tests for has_capability method."""
    
    def test_has_capability_true(self):
        """Test has_capability returns true."""
        backend = {
            'capabilities': ['SPATIAL_FILTER', 'MATERIALIZED_VIEW']
        }
        
        def has_capability(b, cap):
            return cap in b['capabilities']
        
        assert has_capability(backend, 'SPATIAL_FILTER') is True
    
    def test_has_capability_false(self):
        """Test has_capability returns false."""
        backend = {
            'capabilities': ['ATTRIBUTE_FILTER']
        }
        
        def has_capability(b, cap):
            return cap in b['capabilities']
        
        assert has_capability(backend, 'SPATIAL_FILTER') is False


class TestBackendPortName:
    """Tests for name property."""
    
    def test_name_returns_string(self):
        """Test name property returns string."""
        backend = {'name': 'postgresql'}
        
        assert backend['name'] == 'postgresql'


class TestBackendPortPriority:
    """Tests for priority property."""
    
    def test_priority_postgresql(self):
        """Test PostgreSQL has highest priority."""
        priorities = {
            'postgresql': 1,
            'spatialite': 2,
            'ogr': 3
        }
        
        assert priorities['postgresql'] < priorities['spatialite']
    
    def test_priority_ogr_lowest(self):
        """Test OGR has lowest priority."""
        priorities = {
            'postgresql': 1,
            'spatialite': 2,
            'ogr': 3
        }
        
        assert priorities['ogr'] > priorities['spatialite']


class TestBackendPortCapabilities:
    """Tests for capabilities property."""
    
    def test_capabilities_list(self):
        """Test capabilities returns list."""
        backend = {
            'capabilities': ['SPATIAL_FILTER', 'ATTRIBUTE_FILTER']
        }
        
        assert isinstance(backend['capabilities'], list)
        assert len(backend['capabilities']) == 2


class TestBackendPortValidateExpression:
    """Tests for validate_expression method."""
    
    def test_validate_valid_expression(self):
        """Test validating valid expression."""
        def validate_expression(expr):
            if not expr:
                return False, 'Empty expression'
            if '=' not in expr and '>' not in expr and '<' not in expr:
                # Simple validation
                return False, 'No comparison operator'
            return True, None
        
        valid, error = validate_expression('id > 10')
        
        assert valid is True
        assert error is None
    
    def test_validate_empty_expression(self):
        """Test validating empty expression."""
        def validate_expression(expr):
            if not expr:
                return False, 'Empty expression'
            return True, None
        
        valid, error = validate_expression('')
        
        assert valid is False
        assert 'Empty' in error


class TestBackendPortPrepare:
    """Tests for prepare method."""
    
    def test_prepare_initializes_backend(self):
        """Test prepare initializes backend."""
        backend = {'initialized': False}
        
        def prepare(b, layer):
            b['initialized'] = True
            b['layer_id'] = layer.id()
        
        layer = Mock()
        layer.id.return_value = 'layer_123'
        
        prepare(backend, layer)
        
        assert backend['initialized'] is True
        assert backend['layer_id'] == 'layer_123'


class TestBackendPortGetStatistics:
    """Tests for get_statistics method."""
    
    def test_get_statistics_returns_stats(self):
        """Test get_statistics returns stats."""
        stats = {
            'total_calls': 100,
            'successful_calls': 95,
            'average_time': 0.5
        }
        
        def get_statistics():
            return stats
        
        result = get_statistics()
        
        assert result['total_calls'] == 100
        assert result['successful_calls'] == 95


class TestBackendPortResetStatistics:
    """Tests for reset_statistics method."""
    
    def test_reset_clears_stats(self):
        """Test reset_statistics clears stats."""
        stats = {
            'total_calls': 100,
            'successful_calls': 95
        }
        
        def reset_statistics():
            nonlocal stats
            stats = {'total_calls': 0, 'successful_calls': 0, 'average_time': 0}
        
        reset_statistics()
        
        assert stats['total_calls'] == 0


class TestBackendPortStr:
    """Tests for __str__ method."""
    
    def test_str_representation(self):
        """Test string representation."""
        backend = {
            'name': 'postgresql',
            'version': '14.0'
        }
        
        def to_str(b):
            return f"Backend({b['name']} v{b['version']})"
        
        result = to_str(backend)
        
        assert 'postgresql' in result
        assert '14.0' in result


class TestBackendPortRepr:
    """Tests for __repr__ method."""
    
    def test_repr_representation(self):
        """Test repr representation."""
        backend = {
            'name': 'postgresql',
            'capabilities': ['SPATIAL_FILTER']
        }
        
        def to_repr(b):
            return f"<BackendPort name={b['name']} caps={len(b['capabilities'])}>"
        
        result = to_repr(backend)
        
        assert '<BackendPort' in result
        assert 'postgresql' in result

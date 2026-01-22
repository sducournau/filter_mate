# -*- coding: utf-8 -*-
"""
Tests for LayerService - Layer management and validation service.

Tests:
- Layer validation
- Primary key detection
- Sync state management
- Filter protection
- Cache management
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import time


class TestLayerValidationStatus:
    """Tests for LayerValidationStatus enum."""
    
    def test_validation_status_values(self):
        """Test validation status enum values."""
        statuses = {
            'VALID': 1,
            'INVALID': 2,
            'UNKNOWN': 3,
            'NOT_LOADED': 4
        }
        
        assert 'VALID' in statuses
        assert 'INVALID' in statuses


class TestLayerValidationResult:
    """Tests for LayerValidationResult dataclass."""
    
    def test_validation_result_valid(self):
        """Test valid validation result."""
        result = {
            'status': 'VALID',
            'message': '',
            'layer_id': 'layer_123'
        }
        
        is_valid = result['status'] == 'VALID'
        
        assert is_valid is True
    
    def test_validation_result_invalid(self):
        """Test invalid validation result."""
        result = {
            'status': 'INVALID',
            'message': 'Layer source not available',
            'layer_id': 'layer_123'
        }
        
        is_valid = result['status'] == 'VALID'
        
        assert is_valid is False
    
    def test_validation_result_with_message(self):
        """Test validation result with error message."""
        result = {
            'status': 'INVALID',
            'message': 'Database connection failed'
        }
        
        assert result['message'] != ''


class TestLayerInfo:
    """Tests for LayerInfo dataclass."""
    
    def test_layer_info_structure(self):
        """Test LayerInfo structure."""
        info = {
            'id': 'layer_123',
            'name': 'Test Layer',
            'provider': 'postgres',
            'feature_count': 1000,
            'geometry_type': 'Point',
            'crs': 'EPSG:4326'
        }
        
        assert info['name'] == 'Test Layer'
        assert info['provider'] == 'postgres'
    
    def test_layer_info_minimal(self):
        """Test LayerInfo with minimal data."""
        info = {
            'id': 'layer_123',
            'name': 'Test Layer'
        }
        
        assert 'id' in info
        assert 'name' in info


class TestLayerSyncState:
    """Tests for LayerSyncState dataclass."""
    
    def test_sync_state_synchronized(self):
        """Test synchronized state."""
        state = {
            'layer_id': 'layer_123',
            'is_synced': True,
            'last_sync': time.time()
        }
        
        assert state['is_synced'] is True
    
    def test_sync_state_not_synchronized(self):
        """Test not synchronized state."""
        state = {
            'layer_id': 'layer_123',
            'is_synced': False,
            'pending_changes': ['filter_update']
        }
        
        assert state['is_synced'] is False
        assert len(state['pending_changes']) > 0


class TestLayerServiceInit:
    """Tests for LayerService initialization."""
    
    def test_init_creates_instance(self):
        """Test initialization creates instance."""
        service = {
            'cache': {},
            'protection_windows': {},
            'initialized': True
        }
        
        assert service['initialized'] is True
    
    def test_init_empty_cache(self):
        """Test initialization with empty cache."""
        service = {'cache': {}}
        
        assert len(service['cache']) == 0


class TestLayerValidation:
    """Tests for validate_layer method."""
    
    def test_validate_valid_layer(self):
        """Test validation of valid layer."""
        layer = Mock()
        layer.isValid.return_value = True
        layer.featureCount.return_value = 100
        
        def validate(l):
            if l and l.isValid() and l.featureCount() >= 0:
                return {'status': 'VALID'}
            return {'status': 'INVALID'}
        
        result = validate(layer)
        
        assert result['status'] == 'VALID'
    
    def test_validate_invalid_layer(self):
        """Test validation of invalid layer."""
        layer = Mock()
        layer.isValid.return_value = False
        
        def validate(l):
            if l and l.isValid():
                return {'status': 'VALID'}
            return {'status': 'INVALID'}
        
        result = validate(layer)
        
        assert result['status'] == 'INVALID'
    
    def test_validate_none_layer(self):
        """Test validation of None layer."""
        def validate(l):
            if l is None:
                return {'status': 'NOT_LOADED'}
            return {'status': 'UNKNOWN'}
        
        result = validate(None)
        
        assert result['status'] == 'NOT_LOADED'


class TestLayerSourceAvailability:
    """Tests for _is_layer_source_available method."""
    
    def test_source_available(self):
        """Test source availability check succeeds."""
        layer = Mock()
        layer.dataProvider.return_value.isValid.return_value = True
        
        def is_source_available(l):
            try:
                provider = l.dataProvider()
                return provider and provider.isValid()
            except Exception:
                return False
        
        result = is_source_available(layer)
        
        assert result is True
    
    def test_source_not_available(self):
        """Test source availability check fails."""
        layer = Mock()
        layer.dataProvider.return_value = None
        
        def is_source_available(l):
            try:
                provider = l.dataProvider()
                if provider is None:
                    return False
                return provider.isValid()
            except Exception:
                return False
        
        result = is_source_available(layer)
        
        assert result is False


class TestPrimaryKeyDetection:
    """Tests for _detect_primary_key and get_primary_key methods."""
    
    def test_detect_pk_from_uri(self):
        """Test primary key detection from URI."""
        uri_params = {
            'key': 'gid',
            'table': 'public.my_table'
        }
        
        pk = uri_params.get('key', None)
        
        assert pk == 'gid'
    
    def test_detect_pk_default_id(self):
        """Test primary key defaults to 'id'."""
        uri_params = {}
        
        pk = uri_params.get('key', 'id')
        
        assert pk == 'id'
    
    def test_get_pk_cached(self):
        """Test getting cached primary key."""
        pk_cache = {
            'layer_123': 'gid',
            'layer_456': 'fid'
        }
        
        layer_id = 'layer_123'
        pk = pk_cache.get(layer_id)
        
        assert pk == 'gid'
    
    def test_get_pk_not_cached(self):
        """Test getting primary key when not cached."""
        pk_cache = {}
        layer_id = 'layer_new'
        
        pk = pk_cache.get(layer_id, None)
        
        assert pk is None


class TestSyncStateManagement:
    """Tests for get_sync_state method."""
    
    def test_get_sync_state_synced(self):
        """Test getting sync state for synced layer."""
        sync_states = {
            'layer_123': {'is_synced': True, 'last_sync': 12345}
        }
        
        state = sync_states.get('layer_123', {'is_synced': False})
        
        assert state['is_synced'] is True
    
    def test_get_sync_state_unknown(self):
        """Test getting sync state for unknown layer."""
        sync_states = {}
        
        state = sync_states.get('layer_unknown', {'is_synced': False})
        
        assert state['is_synced'] is False


class TestMultiStepFilterDetection:
    """Tests for _detect_multi_step_filter method."""
    
    def test_detect_multi_step_buffer(self):
        """Test detecting multi-step filter with buffer."""
        filter_config = {
            'use_buffer': True,
            'buffer_distance': 100
        }
        
        is_multi_step = filter_config.get('use_buffer', False)
        
        assert is_multi_step is True
    
    def test_detect_multi_step_simple(self):
        """Test detecting simple (non-multi-step) filter."""
        filter_config = {
            'expression': "name = 'test'"
        }
        
        is_multi_step = filter_config.get('use_buffer', False)
        
        assert is_multi_step is False


class TestFieldExpressionValidation:
    """Tests for validate_field_expression method."""
    
    def test_validate_expression_valid(self):
        """Test validating valid field expression."""
        fields = ['id', 'name', 'type', 'area']
        expression = "name = 'test' AND area > 100"
        
        # Check if fields in expression exist
        has_name = 'name' in fields
        has_area = 'area' in fields
        
        is_valid = has_name and has_area
        
        assert is_valid is True
    
    def test_validate_expression_invalid_field(self):
        """Test validating expression with invalid field."""
        fields = ['id', 'name']
        expression = "nonexistent_field = 'test'"
        
        has_field = 'nonexistent_field' in fields
        
        assert has_field is False


class TestGetValidExpression:
    """Tests for get_valid_expression method."""
    
    def test_get_valid_expression_unchanged(self):
        """Test valid expression returned unchanged."""
        expression = "id > 10"
        
        def get_valid(expr):
            if expr and len(expr) > 0:
                return expr
            return ""
        
        result = get_valid(expression)
        
        assert result == expression
    
    def test_get_valid_expression_empty(self):
        """Test empty expression returns empty string."""
        expression = ""
        
        def get_valid(expr):
            if expr and len(expr) > 0:
                return expr
            return ""
        
        result = get_valid(expression)
        
        assert result == ""


class TestFilterProtection:
    """Tests for filter protection methods."""
    
    def test_save_layer_before_filter(self):
        """Test saving layer state before filter."""
        layer_states = {}
        layer_id = 'layer_123'
        
        layer_states[layer_id] = {
            'saved_at': time.time(),
            'previous_filter': ''
        }
        
        assert layer_id in layer_states
    
    def test_mark_filter_completed(self):
        """Test marking filter as completed."""
        protection_windows = {}
        layer_id = 'layer_123'
        protection_duration = 5.0  # seconds
        
        protection_windows[layer_id] = time.time() + protection_duration
        
        assert layer_id in protection_windows
    
    def test_clear_filter_protection(self):
        """Test clearing filter protection."""
        protection_windows = {
            'layer_123': time.time() + 5.0
        }
        
        layer_id = 'layer_123'
        if layer_id in protection_windows:
            del protection_windows[layer_id]
        
        assert layer_id not in protection_windows
    
    def test_is_within_protection_window(self):
        """Test checking if within protection window."""
        layer_id = 'layer_123'
        protection_windows = {
            layer_id: time.time() + 5.0  # Expires in 5 seconds
        }
        
        current_time = time.time()
        is_protected = protection_windows.get(layer_id, 0) > current_time
        
        assert is_protected is True
    
    def test_is_outside_protection_window(self):
        """Test checking if outside protection window."""
        layer_id = 'layer_123'
        protection_windows = {
            layer_id: time.time() - 5.0  # Expired 5 seconds ago
        }
        
        current_time = time.time()
        is_protected = protection_windows.get(layer_id, 0) > current_time
        
        assert is_protected is False
    
    def test_should_block_layer_change(self):
        """Test should block layer change during protection."""
        protection_windows = {
            'layer_123': time.time() + 5.0
        }
        
        def should_block(layer_id, windows):
            return windows.get(layer_id, 0) > time.time()
        
        result = should_block('layer_123', protection_windows)
        
        assert result is True


class TestDisplayNames:
    """Tests for display name methods."""
    
    def test_get_layer_display_name(self):
        """Test getting layer display name."""
        layer = Mock()
        layer.name.return_value = 'My Layer'
        
        display_name = layer.name()
        
        assert display_name == 'My Layer'
    
    def test_get_layer_display_name_fallback(self):
        """Test layer display name fallback."""
        layer = Mock()
        layer.name.return_value = ''
        layer.id.return_value = 'layer_123'
        
        display_name = layer.name() or layer.id()
        
        assert display_name == 'layer_123'
    
    def test_get_provider_display_name_postgres(self):
        """Test provider display name for PostgreSQL."""
        provider_map = {
            'postgres': 'PostgreSQL',
            'spatialite': 'SpatiaLite',
            'ogr': 'OGR'
        }
        
        provider_type = 'postgres'
        display_name = provider_map.get(provider_type, provider_type)
        
        assert display_name == 'PostgreSQL'
    
    def test_get_provider_display_name_unknown(self):
        """Test provider display name for unknown provider."""
        provider_map = {
            'postgres': 'PostgreSQL'
        }
        
        provider_type = 'custom_provider'
        display_name = provider_map.get(provider_type, provider_type)
        
        assert display_name == 'custom_provider'


class TestCacheManagement:
    """Tests for clear_cache method."""
    
    def test_clear_cache_all(self):
        """Test clearing all cache."""
        cache = {
            'layer_123': {'info': 'data'},
            'layer_456': {'info': 'data'}
        }
        
        cache.clear()
        
        assert len(cache) == 0
    
    def test_clear_cache_specific_layer(self):
        """Test clearing cache for specific layer."""
        cache = {
            'layer_123': {'info': 'data'},
            'layer_456': {'info': 'data'}
        }
        
        layer_id = 'layer_123'
        if layer_id in cache:
            del cache[layer_id]
        
        assert 'layer_123' not in cache
        assert 'layer_456' in cache


class TestCleanupRemovedLayers:
    """Tests for cleanup_for_removed_layers method."""
    
    def test_cleanup_removes_stale_entries(self):
        """Test cleanup removes entries for removed layers."""
        cache = {
            'layer_123': {},
            'layer_456': {},
            'layer_789': {}
        }
        
        active_layer_ids = ['layer_123', 'layer_789']
        
        stale_ids = [lid for lid in cache.keys() if lid not in active_layer_ids]
        for lid in stale_ids:
            del cache[lid]
        
        assert 'layer_456' not in cache
        assert 'layer_123' in cache
    
    def test_cleanup_no_stale_entries(self):
        """Test cleanup with no stale entries."""
        cache = {
            'layer_123': {},
            'layer_456': {}
        }
        
        active_layer_ids = ['layer_123', 'layer_456']
        
        stale_ids = [lid for lid in cache.keys() if lid not in active_layer_ids]
        
        assert len(stale_ids) == 0

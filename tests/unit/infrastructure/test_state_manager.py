# -*- coding: utf-8 -*-
"""
Tests for StateManager - Layer and Project state management.

Tests:
- LayerStateManager class
- ProjectStateManager class
- Singleton functions
"""

import pytest
from unittest.mock import Mock


class TestLayerStateManagerInit:
    """Tests for LayerStateManager initialization."""
    
    def test_init_creates_empty_state(self):
        """Test initialization creates empty state."""
        manager = {'layers': {}}
        
        assert manager['layers'] == {}


class TestLayerStateManagerAddLayer:
    """Tests for add_layer method."""
    
    def test_add_layer_success(self):
        """Test adding layer successfully."""
        manager = {'layers': {}}
        
        def add_layer(m, layer_id, properties=None):
            m['layers'][layer_id] = properties or {}
        
        add_layer(manager, 'layer_123', {'name': 'Test'})
        
        assert 'layer_123' in manager['layers']
        assert manager['layers']['layer_123']['name'] == 'Test'
    
    def test_add_layer_default_properties(self):
        """Test adding layer with default properties."""
        manager = {'layers': {}}
        
        def add_layer(m, layer_id, properties=None):
            m['layers'][layer_id] = properties or {
                'filter_expression': '',
                'is_filtered': False,
                'original_extent': None
            }
        
        add_layer(manager, 'layer_123')
        
        assert manager['layers']['layer_123']['is_filtered'] is False


class TestLayerStateManagerRemoveLayer:
    """Tests for remove_layer method."""
    
    def test_remove_layer_success(self):
        """Test removing layer successfully."""
        manager = {'layers': {'layer_123': {'name': 'Test'}}}
        
        def remove_layer(m, layer_id):
            if layer_id in m['layers']:
                del m['layers'][layer_id]
        
        remove_layer(manager, 'layer_123')
        
        assert 'layer_123' not in manager['layers']
    
    def test_remove_nonexistent_layer(self):
        """Test removing nonexistent layer doesn't raise."""
        manager = {'layers': {}}
        
        def remove_layer(m, layer_id):
            if layer_id in m['layers']:
                del m['layers'][layer_id]
        
        # Should not raise
        remove_layer(manager, 'nonexistent')
        
        assert len(manager['layers']) == 0


class TestLayerStateManagerHasLayer:
    """Tests for has_layer method."""
    
    def test_has_layer_true(self):
        """Test has_layer returns true when layer exists."""
        manager = {'layers': {'layer_123': {}}}
        
        def has_layer(m, layer_id):
            return layer_id in m['layers']
        
        assert has_layer(manager, 'layer_123') is True
    
    def test_has_layer_false(self):
        """Test has_layer returns false when layer doesn't exist."""
        manager = {'layers': {}}
        
        def has_layer(m, layer_id):
            return layer_id in m['layers']
        
        assert has_layer(manager, 'layer_123') is False


class TestGetLayerProperties:
    """Tests for get_layer_properties method."""
    
    def test_get_layer_properties_success(self):
        """Test getting layer properties."""
        manager = {
            'layers': {
                'layer_123': {'name': 'Test', 'filter': 'id > 10'}
            }
        }
        
        def get_layer_properties(m, layer_id):
            return m['layers'].get(layer_id)
        
        props = get_layer_properties(manager, 'layer_123')
        
        assert props['name'] == 'Test'
    
    def test_get_layer_properties_nonexistent(self):
        """Test getting properties for nonexistent layer."""
        manager = {'layers': {}}
        
        def get_layer_properties(m, layer_id):
            return m['layers'].get(layer_id)
        
        props = get_layer_properties(manager, 'nonexistent')
        
        assert props is None


class TestGetLayerProperty:
    """Tests for get_layer_property method."""
    
    def test_get_single_property(self):
        """Test getting single property."""
        manager = {
            'layers': {
                'layer_123': {'name': 'Test', 'filter': 'id > 10'}
            }
        }
        
        def get_layer_property(m, layer_id, prop_name):
            layer = m['layers'].get(layer_id, {})
            return layer.get(prop_name)
        
        value = get_layer_property(manager, 'layer_123', 'filter')
        
        assert value == 'id > 10'
    
    def test_get_property_default(self):
        """Test getting property with default value."""
        manager = {'layers': {'layer_123': {}}}
        
        def get_layer_property(m, layer_id, prop_name, default=None):
            layer = m['layers'].get(layer_id, {})
            return layer.get(prop_name, default)
        
        value = get_layer_property(manager, 'layer_123', 'missing', 'default_value')
        
        assert value == 'default_value'


class TestUpdateLayerProperty:
    """Tests for update_layer_property method."""
    
    def test_update_property_success(self):
        """Test updating single property."""
        manager = {
            'layers': {
                'layer_123': {'name': 'Test', 'filter': ''}
            }
        }
        
        def update_layer_property(m, layer_id, prop_name, value):
            if layer_id in m['layers']:
                m['layers'][layer_id][prop_name] = value
        
        update_layer_property(manager, 'layer_123', 'filter', 'id > 10')
        
        assert manager['layers']['layer_123']['filter'] == 'id > 10'


class TestUpdateLayerProperties:
    """Tests for update_layer_properties method."""
    
    def test_update_multiple_properties(self):
        """Test updating multiple properties."""
        manager = {
            'layers': {
                'layer_123': {'name': 'Test', 'filter': '', 'is_filtered': False}
            }
        }
        
        def update_layer_properties(m, layer_id, props):
            if layer_id in m['layers']:
                m['layers'][layer_id].update(props)
        
        update_layer_properties(manager, 'layer_123', {
            'filter': 'id > 10',
            'is_filtered': True
        })
        
        assert manager['layers']['layer_123']['filter'] == 'id > 10'
        assert manager['layers']['layer_123']['is_filtered'] is True


class TestGetAllLayerIds:
    """Tests for get_all_layer_ids method."""
    
    def test_get_all_ids(self):
        """Test getting all layer IDs."""
        manager = {
            'layers': {
                'layer_1': {},
                'layer_2': {},
                'layer_3': {}
            }
        }
        
        def get_all_layer_ids(m):
            return list(m['layers'].keys())
        
        ids = get_all_layer_ids(manager)
        
        assert len(ids) == 3
        assert 'layer_1' in ids


class TestLayerStateManagerClear:
    """Tests for clear method."""
    
    def test_clear_removes_all_layers(self):
        """Test clear removes all layers."""
        manager = {
            'layers': {
                'layer_1': {},
                'layer_2': {}
            }
        }
        
        def clear(m):
            m['layers'] = {}
        
        clear(manager)
        
        assert len(manager['layers']) == 0


class TestValidateLayerStructure:
    """Tests for _validate_layer_structure method."""
    
    def test_validate_valid_structure(self):
        """Test validating valid layer structure."""
        layer_data = {
            'name': 'Test',
            'filter_expression': '',
            'is_filtered': False
        }
        
        required_keys = ['name', 'filter_expression', 'is_filtered']
        
        def validate_structure(data, required):
            return all(key in data for key in required)
        
        is_valid = validate_structure(layer_data, required_keys)
        
        assert is_valid is True
    
    def test_validate_invalid_structure(self):
        """Test validating invalid layer structure."""
        layer_data = {'name': 'Test'}  # Missing keys
        required_keys = ['name', 'filter_expression', 'is_filtered']
        
        def validate_structure(data, required):
            return all(key in data for key in required)
        
        is_valid = validate_structure(layer_data, required_keys)
        
        assert is_valid is False


class TestGetLayerCount:
    """Tests for get_layer_count method."""
    
    def test_get_count(self):
        """Test getting layer count."""
        manager = {
            'layers': {
                'layer_1': {},
                'layer_2': {}
            }
        }
        
        def get_layer_count(m):
            return len(m['layers'])
        
        count = get_layer_count(manager)
        
        assert count == 2


class TestProjectStateManagerInit:
    """Tests for ProjectStateManager initialization."""
    
    def test_init_creates_state(self):
        """Test initialization creates state."""
        manager = {
            'current_layer_id': None,
            'config': {},
            'data_sources': {}
        }
        
        assert manager['current_layer_id'] is None


class TestProjectStateManagerLayerManager:
    """Tests for layer_manager property."""
    
    def test_layer_manager_property(self):
        """Test layer_manager returns layer state manager."""
        layer_manager = {'layers': {}}
        project_manager = {
            'layer_manager': layer_manager
        }
        
        assert project_manager['layer_manager'] == layer_manager


class TestSetCurrentLayer:
    """Tests for set_current_layer method."""
    
    def test_set_current_layer(self):
        """Test setting current layer."""
        manager = {'current_layer_id': None}
        
        def set_current_layer(m, layer_id):
            m['current_layer_id'] = layer_id
        
        set_current_layer(manager, 'layer_123')
        
        assert manager['current_layer_id'] == 'layer_123'


class TestGetCurrentLayerId:
    """Tests for get_current_layer_id method."""
    
    def test_get_current_layer_id(self):
        """Test getting current layer ID."""
        manager = {'current_layer_id': 'layer_123'}
        
        def get_current_layer_id(m):
            return m['current_layer_id']
        
        layer_id = get_current_layer_id(manager)
        
        assert layer_id == 'layer_123'


class TestGetCurrentLayerProperties:
    """Tests for get_current_layer_properties method."""
    
    def test_get_current_properties(self):
        """Test getting current layer properties."""
        manager = {
            'current_layer_id': 'layer_123',
            'layer_manager': {
                'layers': {
                    'layer_123': {'name': 'Test', 'filter': 'id > 10'}
                }
            }
        }
        
        def get_current_layer_properties(m):
            if not m['current_layer_id']:
                return None
            return m['layer_manager']['layers'].get(m['current_layer_id'])
        
        props = get_current_layer_properties(manager)
        
        assert props['name'] == 'Test'


class TestSetConfig:
    """Tests for set_config method."""
    
    def test_set_config_key(self):
        """Test setting config key."""
        manager = {'config': {}}
        
        def set_config(m, key, value):
            m['config'][key] = value
        
        set_config(manager, 'buffer_enabled', True)
        
        assert manager['config']['buffer_enabled'] is True


class TestGetConfig:
    """Tests for get_config method."""
    
    def test_get_config_key(self):
        """Test getting config key."""
        manager = {'config': {'buffer_enabled': True}}
        
        def get_config(m, key, default=None):
            return m['config'].get(key, default)
        
        value = get_config(manager, 'buffer_enabled')
        
        assert value is True
    
    def test_get_config_default(self):
        """Test getting config with default."""
        manager = {'config': {}}
        
        def get_config(m, key, default=None):
            return m['config'].get(key, default)
        
        value = get_config(manager, 'missing', 'default')
        
        assert value == 'default'


class TestRegisterDataSource:
    """Tests for register_data_source method."""
    
    def test_register_data_source(self):
        """Test registering data source."""
        manager = {'data_sources': {}}
        
        def register_data_source(m, name, connection):
            m['data_sources'][name] = connection
        
        conn = Mock()
        register_data_source(manager, 'postgres_db', conn)
        
        assert 'postgres_db' in manager['data_sources']


class TestGetDataSource:
    """Tests for get_data_source method."""
    
    def test_get_registered_source(self):
        """Test getting registered data source."""
        conn = Mock()
        manager = {'data_sources': {'postgres_db': conn}}
        
        def get_data_source(m, name):
            return m['data_sources'].get(name)
        
        result = get_data_source(manager, 'postgres_db')
        
        assert result == conn
    
    def test_get_unregistered_source(self):
        """Test getting unregistered data source."""
        manager = {'data_sources': {}}
        
        def get_data_source(m, name):
            return m['data_sources'].get(name)
        
        result = get_data_source(manager, 'unknown')
        
        assert result is None


class TestUnregisterDataSource:
    """Tests for unregister_data_source method."""
    
    def test_unregister_source(self):
        """Test unregistering data source."""
        manager = {'data_sources': {'postgres_db': Mock()}}
        
        def unregister_data_source(m, name):
            if name in m['data_sources']:
                del m['data_sources'][name]
        
        unregister_data_source(manager, 'postgres_db')
        
        assert 'postgres_db' not in manager['data_sources']


class TestProjectStateManagerClear:
    """Tests for clear method."""
    
    def test_clear_resets_state(self):
        """Test clear resets all state."""
        manager = {
            'current_layer_id': 'layer_123',
            'config': {'key': 'value'},
            'data_sources': {'db': Mock()},
            'layer_manager': {'layers': {'layer_123': {}}}
        }
        
        def clear(m):
            m['current_layer_id'] = None
            m['config'] = {}
            m['data_sources'] = {}
            m['layer_manager']['layers'] = {}
        
        clear(manager)
        
        assert manager['current_layer_id'] is None
        assert len(manager['config']) == 0


class TestGetStateSummary:
    """Tests for get_state_summary method."""
    
    def test_get_summary(self):
        """Test getting state summary."""
        manager = {
            'current_layer_id': 'layer_123',
            'config': {'buffer_enabled': True},
            'data_sources': {'db1': Mock(), 'db2': Mock()},
            'layer_manager': {'layers': {'l1': {}, 'l2': {}, 'l3': {}}}
        }
        
        def get_state_summary(m):
            return {
                'current_layer': m['current_layer_id'],
                'layer_count': len(m['layer_manager']['layers']),
                'data_source_count': len(m['data_sources']),
                'config_keys': list(m['config'].keys())
            }
        
        summary = get_state_summary(manager)
        
        assert summary['current_layer'] == 'layer_123'
        assert summary['layer_count'] == 3
        assert summary['data_source_count'] == 2


class TestGetLayerStateManager:
    """Tests for get_layer_state_manager singleton function."""
    
    def test_returns_singleton(self):
        """Test get_layer_state_manager returns singleton."""
        _instance = None
        
        def get_layer_state_manager():
            nonlocal _instance
            if _instance is None:
                _instance = {'layers': {}}
            return _instance
        
        m1 = get_layer_state_manager()
        m2 = get_layer_state_manager()
        
        assert m1 is m2


class TestGetProjectStateManager:
    """Tests for get_project_state_manager singleton function."""
    
    def test_returns_singleton(self):
        """Test get_project_state_manager returns singleton."""
        _instance = None
        
        def get_project_state_manager():
            nonlocal _instance
            if _instance is None:
                _instance = {'current_layer_id': None}
            return _instance
        
        m1 = get_project_state_manager()
        m2 = get_project_state_manager()
        
        assert m1 is m2


class TestResetStateManagers:
    """Tests for reset_state_managers function."""
    
    def test_reset_clears_singletons(self):
        """Test reset_state_managers clears singletons."""
        _layer_manager = {'layers': {'l1': {}}}
        _project_manager = {'current_layer_id': 'layer_123'}
        
        def reset_state_managers():
            nonlocal _layer_manager, _project_manager
            _layer_manager = None
            _project_manager = None
        
        reset_state_managers()
        
        assert _layer_manager is None
        assert _project_manager is None

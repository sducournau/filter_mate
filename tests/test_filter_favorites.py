"""
Unit tests for filter_favorites module.

Tests FilterFavorite and FavoritesManager classes including:
- Creating and serializing favorites
- Adding/removing/updating favorites
- Searching and filtering
- Export/import functionality
- Configuration capture and application

Author: FilterMate Development Team
Date: December 2025
"""

import pytest
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

# Import modules to test
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from modules.filter_favorites import (
    FilterFavorite,
    FavoritesManager,
    capture_filter_configuration,
    apply_filter_configuration
)


class TestFilterFavorite:
    """Tests for FilterFavorite class"""
    
    def test_create_favorite(self):
        """Test creating a basic favorite"""
        config = {
            'expression': 'population > 10000',
            'geometric_predicates': ['intersects'],
            'buffer_distance': 1000
        }
        
        favorite = FilterFavorite("Test Favorite", config, "Test description")
        
        assert favorite.name == "Test Favorite"
        assert favorite.description == "Test description"
        assert favorite.configuration == config
        assert isinstance(favorite.id, str)
        assert len(favorite.id) == 36  # UUID length
        assert favorite.metadata['usage_count'] == 0
        assert favorite.metadata['last_used'] is None
    
    def test_record_usage(self):
        """Test usage tracking"""
        config = {'expression': 'test'}
        favorite = FilterFavorite("Test", config)
        
        assert favorite.metadata['usage_count'] == 0
        
        # Record usage
        favorite.record_usage()
        assert favorite.metadata['usage_count'] == 1
        assert favorite.metadata['last_used'] is not None
        
        # Record again
        favorite.record_usage()
        assert favorite.metadata['usage_count'] == 2
    
    def test_to_dict(self):
        """Test serialization to dictionary"""
        config = {'expression': 'test', 'buffer_distance': 500}
        metadata = {'tags': ['test', 'example'], 'author': 'test_user'}
        
        favorite = FilterFavorite("Test", config, "Description", metadata)
        fav_dict = favorite.to_dict()
        
        assert fav_dict['name'] == "Test"
        assert fav_dict['description'] == "Description"
        assert fav_dict['configuration'] == config
        assert fav_dict['metadata']['tags'] == ['test', 'example']
        assert fav_dict['metadata']['author'] == 'test_user'
        assert 'created_at' in fav_dict
        assert 'modified_at' in fav_dict
    
    def test_from_dict(self):
        """Test deserialization from dictionary"""
        fav_dict = {
            'id': 'test-uuid-1234',
            'name': 'Test',
            'description': 'Description',
            'configuration': {'expression': 'test'},
            'metadata': {'tags': ['test']},
            'created_at': '2025-12-08T10:30:00',
            'modified_at': '2025-12-08T11:00:00'
        }
        
        favorite = FilterFavorite.from_dict(fav_dict)
        
        assert favorite.id == 'test-uuid-1234'
        assert favorite.name == 'Test'
        assert favorite.description == 'Description'
        assert favorite.configuration == {'expression': 'test'}
        assert favorite.metadata['tags'] == ['test']
    
    def test_round_trip_serialization(self):
        """Test that serialization + deserialization preserves data"""
        config = {
            'expression': 'population > 10000',
            'geometric_predicates': ['intersects', 'within'],
            'buffer_distance': 1000,
            'buffer_type': 'flat'
        }
        metadata = {'tags': ['urban', 'population'], 'author': 'test@example.com'}
        
        original = FilterFavorite("Test Favorite", config, "Test description", metadata)
        original.record_usage()
        
        # Serialize
        fav_dict = original.to_dict()
        
        # Deserialize
        restored = FilterFavorite.from_dict(fav_dict)
        
        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.description == original.description
        assert restored.configuration == original.configuration
        assert restored.metadata['tags'] == metadata['tags']
        assert restored.metadata['usage_count'] == 1


class TestFavoritesManager:
    """Tests for FavoritesManager class"""
    
    @pytest.fixture
    def temp_favorites_file(self):
        """Create a temporary favorites file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        yield temp_path
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    @pytest.fixture
    def manager(self, temp_favorites_file):
        """Create a FavoritesManager instance with temp file"""
        return FavoritesManager(user_favorites_path=temp_favorites_file)
    
    def test_initialization(self, manager):
        """Test manager initialization"""
        assert isinstance(manager, FavoritesManager)
        assert isinstance(manager.favorites, dict)
        assert len(manager.favorites) == 0
    
    def test_add_favorite(self, manager):
        """Test adding a favorite"""
        config = {'expression': 'test'}
        favorite = FilterFavorite("Test", config)
        
        result = manager.add_favorite(favorite)
        
        assert result is True
        assert favorite.id in manager.favorites
        assert manager.favorites[favorite.id] == favorite
        assert len(manager.favorites) == 1
    
    def test_add_duplicate_favorite(self, manager):
        """Test adding a favorite with duplicate ID"""
        config = {'expression': 'test'}
        favorite1 = FilterFavorite("Test 1", config, favorite_id='duplicate-id')
        favorite2 = FilterFavorite("Test 2", config, favorite_id='duplicate-id')
        
        manager.add_favorite(favorite1)
        result = manager.add_favorite(favorite2)
        
        assert result is False
        assert len(manager.favorites) == 1
        assert manager.favorites['duplicate-id'].name == "Test 1"
    
    def test_remove_favorite(self, manager):
        """Test removing a favorite"""
        config = {'expression': 'test'}
        favorite = FilterFavorite("Test", config)
        
        manager.add_favorite(favorite)
        assert len(manager.favorites) == 1
        
        result = manager.remove_favorite(favorite.id)
        
        assert result is True
        assert len(manager.favorites) == 0
        assert favorite.id not in manager.favorites
    
    def test_remove_nonexistent_favorite(self, manager):
        """Test removing a favorite that doesn't exist"""
        result = manager.remove_favorite('nonexistent-id')
        assert result is False
    
    def test_get_favorite(self, manager):
        """Test getting a favorite by ID"""
        config = {'expression': 'test'}
        favorite = FilterFavorite("Test", config)
        
        manager.add_favorite(favorite)
        
        retrieved = manager.get_favorite(favorite.id)
        assert retrieved is not None
        assert retrieved.id == favorite.id
        assert retrieved.name == favorite.name
    
    def test_get_nonexistent_favorite(self, manager):
        """Test getting a favorite that doesn't exist"""
        retrieved = manager.get_favorite('nonexistent-id')
        assert retrieved is None
    
    def test_get_all_favorites(self, manager):
        """Test getting all favorites"""
        config = {'expression': 'test'}
        fav1 = FilterFavorite("Test 1", config)
        fav2 = FilterFavorite("Test 2", config)
        fav3 = FilterFavorite("Test 3", config)
        
        manager.add_favorite(fav1)
        manager.add_favorite(fav2)
        manager.add_favorite(fav3)
        
        all_favs = manager.get_all_favorites()
        
        assert len(all_favs) == 3
        assert fav1 in all_favs
        assert fav2 in all_favs
        assert fav3 in all_favs
    
    def test_search_favorites_by_name(self, manager):
        """Test searching favorites by name"""
        manager.add_favorite(FilterFavorite("Urban Cities", {'expression': 'test'}))
        manager.add_favorite(FilterFavorite("Rural Areas", {'expression': 'test'}))
        manager.add_favorite(FilterFavorite("Urban Zones", {'expression': 'test'}))
        
        results = manager.search_favorites(query="urban")
        
        assert len(results) == 2
        assert all('urban' in f.name.lower() for f in results)
    
    def test_search_favorites_by_description(self, manager):
        """Test searching favorites by description"""
        manager.add_favorite(FilterFavorite("Test 1", {'expression': 'test'}, "Population filter"))
        manager.add_favorite(FilterFavorite("Test 2", {'expression': 'test'}, "Area filter"))
        manager.add_favorite(FilterFavorite("Test 3", {'expression': 'test'}, "Population count"))
        
        results = manager.search_favorites(query="population")
        
        assert len(results) == 2
    
    def test_search_favorites_by_tags(self, manager):
        """Test filtering favorites by tags"""
        fav1 = FilterFavorite("Test 1", {'expression': 'test'}, metadata={'tags': ['urban', 'population']})
        fav2 = FilterFavorite("Test 2", {'expression': 'test'}, metadata={'tags': ['rural']})
        fav3 = FilterFavorite("Test 3", {'expression': 'test'}, metadata={'tags': ['urban', 'area']})
        
        manager.add_favorite(fav1)
        manager.add_favorite(fav2)
        manager.add_favorite(fav3)
        
        results = manager.search_favorites(tags=['urban'])
        
        assert len(results) == 2
        assert fav1 in results
        assert fav3 in results
    
    def test_search_favorites_sort_by_name(self, manager):
        """Test sorting search results by name"""
        manager.add_favorite(FilterFavorite("Charlie", {'expression': 'test'}))
        manager.add_favorite(FilterFavorite("Alpha", {'expression': 'test'}))
        manager.add_favorite(FilterFavorite("Bravo", {'expression': 'test'}))
        
        results = manager.search_favorites(sort_by='name')
        
        assert results[0].name == "Alpha"
        assert results[1].name == "Bravo"
        assert results[2].name == "Charlie"
    
    def test_search_favorites_sort_by_usage(self, manager):
        """Test sorting search results by usage count"""
        fav1 = FilterFavorite("Test 1", {'expression': 'test'})
        fav2 = FilterFavorite("Test 2", {'expression': 'test'})
        fav3 = FilterFavorite("Test 3", {'expression': 'test'})
        
        # Record different usage counts
        fav1.record_usage()
        fav2.record_usage()
        fav2.record_usage()
        fav2.record_usage()
        fav3.record_usage()
        fav3.record_usage()
        
        manager.add_favorite(fav1)
        manager.add_favorite(fav2)
        manager.add_favorite(fav3)
        
        results = manager.search_favorites(sort_by='usage_count')
        
        assert results[0].metadata['usage_count'] == 3  # fav2
        assert results[1].metadata['usage_count'] == 2  # fav3
        assert results[2].metadata['usage_count'] == 1  # fav1
    
    def test_update_favorite(self, manager):
        """Test updating a favorite"""
        favorite = FilterFavorite("Original Name", {'expression': 'test'}, "Original description")
        manager.add_favorite(favorite)
        
        result = manager.update_favorite(
            favorite.id,
            name="Updated Name",
            description="Updated description"
        )
        
        assert result is True
        updated = manager.get_favorite(favorite.id)
        assert updated.name == "Updated Name"
        assert updated.description == "Updated description"
    
    def test_update_nonexistent_favorite(self, manager):
        """Test updating a favorite that doesn't exist"""
        result = manager.update_favorite('nonexistent-id', name="New Name")
        assert result is False
    
    def test_save_and_load_user_favorites(self, manager, temp_favorites_file):
        """Test saving and loading favorites from file"""
        # Add favorites
        fav1 = FilterFavorite("Test 1", {'expression': 'test1'})
        fav2 = FilterFavorite("Test 2", {'expression': 'test2'})
        
        manager.add_favorite(fav1)
        manager.add_favorite(fav2)
        
        # Save
        result = manager.save_user_favorites()
        assert result is True
        assert os.path.exists(temp_favorites_file)
        
        # Load in new manager
        manager2 = FavoritesManager(user_favorites_path=temp_favorites_file)
        
        assert len(manager2.favorites) == 2
        assert fav1.id in manager2.favorites
        assert fav2.id in manager2.favorites
        assert manager2.favorites[fav1.id].name == "Test 1"
        assert manager2.favorites[fav2.id].name == "Test 2"
    
    def test_export_all_favorites(self, manager):
        """Test exporting all favorites to file"""
        fav1 = FilterFavorite("Test 1", {'expression': 'test1'})
        fav2 = FilterFavorite("Test 2", {'expression': 'test2'})
        
        manager.add_favorite(fav1)
        manager.add_favorite(fav2)
        
        # Export
        export_path = tempfile.mktemp(suffix='.json')
        try:
            result = manager.export_to_file(None, export_path)
            
            assert result is True
            assert os.path.exists(export_path)
            
            # Verify file contents
            with open(export_path, 'r') as f:
                data = json.load(f)
            
            assert data['favorites_count'] == 2
            assert len(data['favorites']) == 2
            assert data['filtermate_favorites_version'] == '1.0'
            
        finally:
            if os.path.exists(export_path):
                os.remove(export_path)
    
    def test_export_selected_favorites(self, manager):
        """Test exporting specific favorites"""
        fav1 = FilterFavorite("Test 1", {'expression': 'test1'})
        fav2 = FilterFavorite("Test 2", {'expression': 'test2'})
        fav3 = FilterFavorite("Test 3", {'expression': 'test3'})
        
        manager.add_favorite(fav1)
        manager.add_favorite(fav2)
        manager.add_favorite(fav3)
        
        # Export only fav1 and fav3
        export_path = tempfile.mktemp(suffix='.json')
        try:
            result = manager.export_to_file([fav1.id, fav3.id], export_path)
            
            assert result is True
            
            # Verify only 2 favorites exported
            with open(export_path, 'r') as f:
                data = json.load(f)
            
            assert data['favorites_count'] == 2
            exported_ids = [f['id'] for f in data['favorites']]
            assert fav1.id in exported_ids
            assert fav3.id in exported_ids
            assert fav2.id not in exported_ids
            
        finally:
            if os.path.exists(export_path):
                os.remove(export_path)
    
    def test_import_favorites(self, manager):
        """Test importing favorites from file"""
        # Create export file
        export_data = {
            'filtermate_favorites_version': '1.0',
            'favorites': [
                {
                    'id': 'import-test-1',
                    'name': 'Imported 1',
                    'description': 'Test',
                    'configuration': {'expression': 'test1'},
                    'metadata': {},
                    'created_at': '2025-12-08T10:00:00',
                    'modified_at': '2025-12-08T10:00:00'
                },
                {
                    'id': 'import-test-2',
                    'name': 'Imported 2',
                    'description': 'Test',
                    'configuration': {'expression': 'test2'},
                    'metadata': {},
                    'created_at': '2025-12-08T10:00:00',
                    'modified_at': '2025-12-08T10:00:00'
                }
            ]
        }
        
        import_path = tempfile.mktemp(suffix='.json')
        try:
            with open(import_path, 'w') as f:
                json.dump(export_data, f)
            
            # Import
            count = manager.import_from_file(import_path)
            
            assert count == 2
            assert len(manager.favorites) == 2
            assert 'import-test-1' in manager.favorites
            assert 'import-test-2' in manager.favorites
            assert manager.favorites['import-test-1'].name == 'Imported 1'
            
        finally:
            if os.path.exists(import_path):
                os.remove(import_path)
    
    def test_import_with_overwrite(self, manager):
        """Test importing with overwrite existing"""
        # Add existing favorite
        existing = FilterFavorite("Original", {'expression': 'original'}, favorite_id='test-id')
        manager.add_favorite(existing)
        
        # Create import with same ID but different data
        export_data = {
            'filtermate_favorites_version': '1.0',
            'favorites': [
                {
                    'id': 'test-id',
                    'name': 'Updated',
                    'description': 'Updated description',
                    'configuration': {'expression': 'updated'},
                    'metadata': {},
                    'created_at': '2025-12-08T10:00:00',
                    'modified_at': '2025-12-08T10:00:00'
                }
            ]
        }
        
        import_path = tempfile.mktemp(suffix='.json')
        try:
            with open(import_path, 'w') as f:
                json.dump(export_data, f)
            
            # Import with overwrite
            count = manager.import_from_file(import_path, overwrite_existing=True)
            
            assert count == 1
            updated = manager.get_favorite('test-id')
            assert updated.name == 'Updated'
            assert updated.configuration['expression'] == 'updated'
            
        finally:
            if os.path.exists(import_path):
                os.remove(import_path)
    
    def test_get_statistics(self, manager):
        """Test getting usage statistics"""
        fav1 = FilterFavorite("Test 1", {'expression': 'test1'})
        fav2 = FilterFavorite("Test 2", {'expression': 'test2'})
        fav3 = FilterFavorite("Test 3", {'expression': 'test3'})
        
        # Add usage
        fav1.record_usage()
        fav1.record_usage()
        fav2.record_usage()
        
        manager.add_favorite(fav1)
        manager.add_favorite(fav2)
        manager.add_favorite(fav3)
        
        stats = manager.get_statistics()
        
        assert stats['total_count'] == 3
        assert stats['total_usage_count'] == 3
        assert len(stats['most_used']) > 0
        assert stats['most_used'][0]['id'] == fav1.id  # Most used
        assert stats['most_used'][0]['usage_count'] == 2


class TestConfigurationCapture:
    """Tests for configuration capture and application"""
    
    def test_capture_filter_configuration(self):
        """Test capturing filter configuration from layer properties"""
        project_layers = {
            'layer1': {
                'infos': {
                    'layer_geometry_type': 'Polygon',
                    'layer_provider_type': 'postgresql',
                    'layer_name': 'test_layer'
                },
                'filtering': {
                    'filter_expression': 'population > 10000',
                    'geometric_predicates': ['intersects', 'within'],
                    'buffer_value': 1000,
                    'buffer_type': 'flat',
                    'buffer_value_expression': '',
                    'source_layer_combine_operator': 'AND',
                    'other_layers_combine_operator': 'OR',
                    'layers_to_filter': ['layer2']
                }
            },
            'layer2': {
                'infos': {
                    'layer_geometry_type': 'Line',
                    'layer_name': 'roads'
                }
            }
        }
        
        config = capture_filter_configuration(project_layers, 'layer1')
        
        assert config['expression'] == 'population > 10000'
        assert config['geometric_predicates'] == ['intersects', 'within']
        assert config['buffer_distance'] == 1000
        assert config['buffer_type'] == 'flat'
        assert config['source_layer_combine_operator'] == 'AND'
        assert config['other_layers_combine_operator'] == 'OR'
        assert 'Line' in config['associated_layers_by_type']
        assert 'roads' in config['associated_layers_by_type']['Line']
    
    def test_capture_configuration_no_layer(self):
        """Test capturing configuration for nonexistent layer"""
        project_layers = {}
        config = capture_filter_configuration(project_layers, 'nonexistent')
        assert config == {}
    
    def test_apply_filter_configuration(self):
        """Test applying filter configuration to a layer"""
        config = {
            'expression': 'population > 10000',
            'geometric_predicates': ['intersects'],
            'buffer_distance': 1000,
            'buffer_type': 'flat',
            'buffer_expression': '',
            'source_layer_combine_operator': 'AND',
            'other_layers_combine_operator': 'OR',
            'associated_layers_by_type': {
                'Line': ['roads', 'highways']
            }
        }
        
        project_layers = {
            'target_layer': {
                'infos': {'layer_name': 'target'},
                'filtering': {}
            },
            'layer2': {
                'infos': {
                    'layer_geometry_type': 'Line',
                    'layer_name': 'roads_network'
                }
            },
            'layer3': {
                'infos': {
                    'layer_geometry_type': 'Line',
                    'layer_name': 'highways_main'
                }
            }
        }
        
        result = apply_filter_configuration(config, project_layers, 'target_layer')
        
        assert result is True
        assert project_layers['target_layer']['filtering']['filter_expression'] == 'population > 10000'
        assert project_layers['target_layer']['filtering']['geometric_predicates'] == ['intersects']
        assert project_layers['target_layer']['filtering']['buffer_value'] == 1000
        # Fuzzy matching should find roads_network and highways_main
        assert len(project_layers['target_layer']['filtering']['layers_to_filter']) == 2
    
    def test_apply_configuration_strict_matching(self):
        """Test applying configuration with strict layer name matching"""
        config = {
            'expression': 'test',
            'geometric_predicates': [],
            'buffer_distance': 0,
            'buffer_type': 'flat',
            'buffer_expression': '',
            'source_layer_combine_operator': 'AND',
            'other_layers_combine_operator': 'OR',
            'associated_layers_by_type': {
                'Polygon': ['exact_name']
            }
        }
        
        project_layers = {
            'target': {
                'infos': {'layer_name': 'target'},
                'filtering': {}
            },
            'layer2': {
                'infos': {
                    'layer_geometry_type': 'Polygon',
                    'layer_name': 'exact_name'
                }
            },
            'layer3': {
                'infos': {
                    'layer_geometry_type': 'Polygon',
                    'layer_name': 'exact_name_different'
                }
            }
        }
        
        result = apply_filter_configuration(config, project_layers, 'target', strict_matching=True)
        
        assert result is True
        # Should only match exact_name, not exact_name_different
        assert len(project_layers['target']['filtering']['layers_to_filter']) == 1
        assert 'layer2' in project_layers['target']['filtering']['layers_to_filter']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

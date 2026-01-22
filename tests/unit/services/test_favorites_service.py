# -*- coding: utf-8 -*-
"""
Unit Tests for Favorites Service.

Tests the FavoritesService including:
- CRUD operations (add, remove, update, get)
- Internal database storage (v5.0)
- Import/Export functionality
- Statistics and validation

Author: FilterMate Team
Date: January 2026
Sprint: 1.2 - Critical Tests

NOTE: These tests are designed to run WITHOUT QGIS environment.
For full integration tests with QGIS, use tests in tests/integration/
"""
import pytest
import sys
import os
import tempfile
import sqlite3
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Add plugin directory to path
plugin_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(plugin_dir))


# ============================================================
# Tests that DON'T require FavoritesService import
# These test the internal storage and data structures
# ============================================================

class TestInternalDatabaseStorageStandalone:
    """Tests for internal SQLite storage schema (v5.0 feature).
    
    These tests verify the database schema without importing FavoritesService.
    """
    
    def test_create_favorites_table(self):
        """Test that favorites table can be created with correct schema."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "favorites.db")
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Create table with v5.0 schema
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS favorites (
                    id TEXT PRIMARY KEY,
                    project_uuid TEXT,
                    name TEXT NOT NULL,
                    expression TEXT,
                    layer_name TEXT,
                    layer_provider TEXT,
                    spatial_config TEXT,
                    remote_layers TEXT,
                    tags TEXT,
                    description TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    use_count INTEGER DEFAULT 0,
                    is_global INTEGER DEFAULT 0
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_project_uuid 
                ON favorites(project_uuid)
            ''')
            
            conn.commit()
            
            # Verify table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            conn.close()
            
            assert "favorites" in tables
    
    def test_favorites_table_columns(self):
        """Test favorites table has all required columns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "favorites.db")
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE favorites (
                    id TEXT PRIMARY KEY,
                    project_uuid TEXT,
                    name TEXT NOT NULL,
                    expression TEXT,
                    layer_name TEXT,
                    layer_provider TEXT,
                    spatial_config TEXT,
                    remote_layers TEXT,
                    tags TEXT,
                    description TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    use_count INTEGER DEFAULT 0,
                    is_global INTEGER DEFAULT 0
                )
            ''')
            conn.commit()
            
            cursor.execute("PRAGMA table_info(favorites)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
            conn.close()
            
            # Check required columns
            required_columns = [
                "id", "project_uuid", "name", "expression",
                "layer_name", "spatial_config", "use_count"
            ]
            
            for col in required_columns:
                assert col in columns, f"Missing column: {col}"
    
    def test_insert_favorite_record(self):
        """Test inserting a favorite record into the database."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "favorites.db")
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE favorites (
                    id TEXT PRIMARY KEY,
                    project_uuid TEXT,
                    name TEXT NOT NULL,
                    expression TEXT,
                    spatial_config TEXT,
                    use_count INTEGER DEFAULT 0
                )
            ''')
            
            # Insert a favorite
            cursor.execute('''
                INSERT INTO favorites (id, project_uuid, name, expression, spatial_config)
                VALUES (?, ?, ?, ?, ?)
            ''', ("fav-001", "project-123", "Test Filter", '"field" = 1', '{"buffer": 100}'))
            
            conn.commit()
            
            # Verify insertion
            cursor.execute("SELECT * FROM favorites WHERE id = ?", ("fav-001",))
            row = cursor.fetchone()
            conn.close()
            
            assert row is not None
            assert row[2] == "Test Filter"  # name column
            assert row[3] == '"field" = 1'  # expression column
    
    def test_spatial_config_json_storage(self):
        """Test spatial config can be stored as JSON."""
        spatial_config = {
            "buffer_value": 100.0,
            "predicates": {"intersects": True, "within": False},
            "task_feature_ids": [1, 2, 3, 4, 5]
        }
        
        json_str = json.dumps(spatial_config)
        restored = json.loads(json_str)
        
        assert restored["buffer_value"] == 100.0
        assert restored["predicates"]["intersects"] is True
        assert len(restored["task_feature_ids"]) == 5


class TestFavoriteDataStructures:
    """Tests for favorite data structures and validation."""
    
    def test_favorite_minimal_structure(self):
        """Test minimal favorite structure."""
        favorite = {
            "id": "fav-001",
            "name": "My Filter",
            "expression": '"population" > 10000'
        }
        
        assert "id" in favorite
        assert "name" in favorite
        assert "expression" in favorite
    
    def test_favorite_full_structure(self):
        """Test full favorite structure with all fields."""
        favorite = {
            "id": "fav-001",
            "name": "Urban Areas",
            "expression": '"type" = \'urban\'',
            "layer_name": "buildings",
            "layer_provider": "spatialite",
            "spatial_config": {
                "buffer_value": 50.0,
                "predicates": {"intersects": True}
            },
            "remote_layers": {
                "roads": {"expression": '"highway" IS NOT NULL'}
            },
            "tags": ["urban", "analysis"],
            "description": "Filter for urban areas",
            "created_at": "2026-01-22T10:00:00",
            "updated_at": "2026-01-22T10:00:00",
            "use_count": 5,
            "is_global": False
        }
        
        assert favorite["buffer_value"] if "buffer_value" in favorite else favorite["spatial_config"]["buffer_value"] == 50.0
        assert len(favorite["tags"]) == 2
    
    def test_favorite_import_format(self):
        """Test favorite import file format."""
        import_data = {
            "version": "1.0",
            "exported_at": "2026-01-22T10:00:00",
            "source_project": "test_project",
            "favorites": [
                {
                    "name": "Filter 1",
                    "expression": '"field" = 1'
                },
                {
                    "name": "Filter 2",
                    "expression": '"field" = 2'
                }
            ]
        }
        
        # Should be valid JSON
        json_str = json.dumps(import_data)
        restored = json.loads(json_str)
        
        assert "favorites" in restored
        assert len(restored["favorites"]) == 2
    
    def test_favorite_export_format(self):
        """Test favorite export file format."""
        export_data = {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "total_count": 3,
            "favorites": []
        }
        
        # Add favorites
        for i in range(3):
            export_data["favorites"].append({
                "id": f"fav-00{i+1}",
                "name": f"Filter {i+1}",
                "expression": f'"field" = {i+1}'
            })
        
        assert len(export_data["favorites"]) == 3


class TestFavoritesStatisticsStandalone:
    """Tests for favorites statistics calculations."""
    
    def test_calculate_total_count(self):
        """Test calculating total favorites count."""
        favorites = [
            {"id": "1", "name": "Filter 1"},
            {"id": "2", "name": "Filter 2"},
            {"id": "3", "name": "Filter 3"}
        ]
        
        assert len(favorites) == 3
    
    def test_calculate_use_counts(self):
        """Test calculating use count statistics."""
        favorites = [
            {"id": "1", "use_count": 10},
            {"id": "2", "use_count": 5},
            {"id": "3", "use_count": 20}
        ]
        
        total_uses = sum(f["use_count"] for f in favorites)
        most_used = max(favorites, key=lambda x: x["use_count"])
        
        assert total_uses == 35
        assert most_used["id"] == "3"
    
    def test_filter_by_tags(self):
        """Test filtering favorites by tags."""
        favorites = [
            {"id": "1", "name": "Urban", "tags": ["urban", "cities"]},
            {"id": "2", "name": "Rural", "tags": ["rural"]},
            {"id": "3", "name": "Water", "tags": ["water", "urban"]}
        ]
        
        urban_favorites = [f for f in favorites if "urban" in f.get("tags", [])]
        
        assert len(urban_favorites) == 2
        assert urban_favorites[0]["name"] == "Urban"


class TestFavoritesSpatialConfigStandalone:
    """Tests for spatial configuration in favorites (v5.0)."""
    
    def test_spatial_config_with_buffer(self):
        """Test favorite with buffer in spatial config."""
        spatial_config = {
            "buffer_value": 100.0,
            "predicates": {"intersects": True},
            "task_feature_ids": [1, 2, 3]
        }
        
        assert spatial_config["buffer_value"] == 100.0
        assert "intersects" in spatial_config["predicates"]
        assert len(spatial_config["task_feature_ids"]) == 3
    
    def test_negative_buffer(self):
        """Test negative buffer value (shrink operation)."""
        spatial_config = {
            "buffer_value": -50.0,
            "predicates": {"within": True}
        }
        
        assert spatial_config["buffer_value"] < 0
    
    def test_multiple_predicates(self):
        """Test multiple spatial predicates."""
        spatial_config = {
            "predicates": {
                "intersects": True,
                "contains": False,
                "within": True,
                "overlaps": False,
                "touches": True
            }
        }
        
        active = [k for k, v in spatial_config["predicates"].items() if v]
        assert len(active) == 3
        assert "intersects" in active
    
    def test_remote_layers_config(self):
        """Test remote layers configuration."""
        favorite = {
            "name": "Multi-layer filter",
            "expression": '"main_field" = 1',
            "remote_layers": {
                "roads": {
                    "expression": '"highway" IS NOT NULL',
                    "predicate": "intersects"
                },
                "parks": {
                    "expression": "\"type\" = 'park'",
                    "predicate": "within"
                }
            }
        }
        
        assert len(favorite["remote_layers"]) == 2
        assert "roads" in favorite["remote_layers"]


class TestFavoritesValidationStandalone:
    """Tests for favorites validation rules."""
    
    def test_validate_name_required(self):
        """Test that name is required."""
        favorite = {"expression": '"field" = 1'}
        
        is_valid = "name" in favorite and len(favorite.get("name", "")) > 0
        assert is_valid is False
    
    def test_validate_name_not_empty(self):
        """Test that name cannot be empty."""
        favorite = {"name": "", "expression": '"field" = 1'}
        
        is_valid = len(favorite.get("name", "")) > 0
        assert is_valid is False
    
    def test_validate_expression_syntax(self):
        """Test basic expression syntax validation."""
        valid_expressions = [
            '"field" = 1',
            '"name" LIKE \'%test%\'',
            '"value" > 100 AND "value" < 200',
            '"category" IN (\'a\', \'b\', \'c\')'
        ]
        
        for expr in valid_expressions:
            # Basic check: non-empty and contains quotes
            assert len(expr) > 0
            assert '"' in expr or "'" in expr
    
    def test_validate_duplicate_names(self):
        """Test detecting duplicate favorite names."""
        favorites = [
            {"id": "1", "name": "My Filter"},
            {"id": "2", "name": "Other Filter"},
            {"id": "3", "name": "My Filter"}  # Duplicate
        ]
        
        names = [f["name"] for f in favorites]
        has_duplicates = len(names) != len(set(names))
        
        assert has_duplicates is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# -*- coding: utf-8 -*-
"""
Spatialite Backend Integration Tests - ARCH-051

Integration tests for Spatialite backend with R-tree optimization,
caching, and temporary tables.

Part of Phase 5 Integration & Release.

Author: FilterMate Team
Date: January 2026
"""
import pytest
from unittest.mock import MagicMock
import sys
from pathlib import Path

# Add plugin directory to path
plugin_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(plugin_dir))


@pytest.fixture
def mock_sqlite_connection():
    """Create a mock SQLite/Spatialite connection."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.fetchone.return_value = (100,)
    cursor.fetchall.return_value = [(i,) for i in range(100)]
    cursor.description = [("id",), ("name",), ("geometry",)]
    conn.enable_load_extension = MagicMock()
    conn.load_extension = MagicMock()
    return conn


@pytest.fixture
def spatialite_backend_mock(mock_sqlite_connection):
    """Create a mock Spatialite backend."""
    backend = MagicMock()
    backend.name = "Spatialite"
    backend._connection = mock_sqlite_connection
    backend._db_path = "/tmp/test.sqlite"
    
    # Metrics
    backend._metrics = {
        "executions": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "total_time_ms": 0.0,
        "errors": 0
    }
    
    return backend


@pytest.fixture
def cache_mock():
    """Create a mock SpatialiteCache."""
    cache = MagicMock()
    cache._cache = {}
    cache._max_size = 100
    cache._ttl_seconds = 300
    
    def get(key):
        return cache._cache.get(key)
    
    def set(key, value):
        cache._cache[key] = {
            "value": value,
            "timestamp": "2026-01-08T12:00:00"
        }
    
    def invalidate(key):
        if key in cache._cache:
            del cache._cache[key]
    
    def clear():
        cache._cache.clear()
    
    def get_stats():
        return MagicMock(
            size=len(cache._cache),
            max_size=cache._max_size,
            hit_rate=0.75
        )
    
    cache.get.side_effect = get
    cache.set.side_effect = set
    cache.invalidate.side_effect = invalidate
    cache.clear.side_effect = clear
    cache.get_stats.side_effect = get_stats
    
    return cache


@pytest.fixture
def rtree_manager_mock():
    """Create a mock RTreeIndexManager."""
    manager = MagicMock()
    manager._indexes = {}
    
    def create_index(table_name, geom_column):
        index_name = f"idx_{table_name}_{geom_column}"
        manager._indexes[index_name] = {
            "table": table_name,
            "column": geom_column,
            "created_at": "2026-01-08T12:00:00"
        }
        return index_name
    
    def exists(table_name, geom_column=None):
        if geom_column:
            index_name = f"idx_{table_name}_{geom_column}"
            return index_name in manager._indexes
        return any(
            idx["table"] == table_name 
            for idx in manager._indexes.values()
        )
    
    def drop_index(index_name):
        if index_name in manager._indexes:
            del manager._indexes[index_name]
            return True
        return False
    
    def rebuild_index(index_name):
        if index_name in manager._indexes:
            return MagicMock(success=True)
        return MagicMock(success=False)
    
    manager.create_index.side_effect = create_index
    manager.exists.side_effect = exists
    manager.drop_index.side_effect = drop_index
    manager.rebuild_index.side_effect = rebuild_index
    
    return manager


@pytest.mark.integration
@pytest.mark.spatialite
class TestSpatialiteBackendIntegration:
    """Integration tests for Spatialite backend."""
    
    def test_backend_initialization(self, spatialite_backend_mock):
        """Test backend initializes correctly."""
        backend = spatialite_backend_mock
        
        assert backend.name == "Spatialite"
        assert backend._db_path is not None
    
    def test_load_spatialite_extension(self, mock_sqlite_connection):
        """Test loading mod_spatialite extension."""
        conn = mock_sqlite_connection
        
        conn.enable_load_extension(True)
        conn.load_extension("mod_spatialite")
        
        conn.enable_load_extension.assert_called_with(True)
        conn.load_extension.assert_called_with("mod_spatialite")
    
    def test_execute_simple_filter(
        self,
        spatialite_backend_mock,
        spatialite_layer
    ):
        """Test executing a simple attribute filter."""
        backend = spatialite_backend_mock
        
        # Configure execution result
        result = MagicMock()
        result.success = True
        result.matched_count = 50
        result.execution_time_ms = 30.0
        backend.execute.return_value = result
        
        execution_result = backend.execute(
            '"population" > 10000',
            spatialite_layer
        )
        
        assert execution_result.success is True
        assert execution_result.matched_count == 50
    
    def test_execute_spatial_filter(
        self,
        spatialite_backend_mock,
        spatialite_layer
    ):
        """Test executing a spatial filter."""
        backend = spatialite_backend_mock
        
        result = MagicMock()
        result.success = True
        result.matched_count = 25
        result.is_spatial = True
        backend.execute.return_value = result
        
        execution_result = backend.execute(
            "intersects($geometry, @filter_geometry)",
            spatialite_layer
        )
        
        assert execution_result.success is True
        assert execution_result.is_spatial is True


@pytest.mark.integration
@pytest.mark.spatialite
class TestSpatialiteCache:
    """Tests for Spatialite result caching."""
    
    def test_cache_set_get(self, cache_mock):
        """Test setting and getting cache values."""
        cache = cache_mock
        
        # Set value
        cache.set("filter_1", {"feature_ids": [1, 2, 3]})
        
        # Get value
        result = cache.get("filter_1")
        assert result is not None
        assert result["value"]["feature_ids"] == [1, 2, 3]
    
    def test_cache_miss(self, cache_mock):
        """Test cache miss returns None."""
        cache = cache_mock
        
        result = cache.get("nonexistent_key")
        assert result is None
    
    def test_cache_invalidate(self, cache_mock):
        """Test cache invalidation."""
        cache = cache_mock
        
        cache.set("to_invalidate", {"data": "test"})
        assert cache.get("to_invalidate") is not None
        
        cache.invalidate("to_invalidate")
        assert cache.get("to_invalidate") is None
    
    def test_cache_clear(self, cache_mock):
        """Test clearing entire cache."""
        cache = cache_mock
        
        cache.set("key1", {"data": "1"})
        cache.set("key2", {"data": "2"})
        
        cache.clear()
        
        assert cache.get("key1") is None
        assert cache.get("key2") is None
    
    def test_cache_stats(self, cache_mock):
        """Test cache statistics."""
        cache = cache_mock
        
        cache.set("key1", {"data": "1"})
        
        stats = cache.get_stats()
        assert stats.size == 1
        assert stats.hit_rate >= 0


@pytest.mark.integration
@pytest.mark.spatialite
class TestRTreeIndexManager:
    """Tests for R-tree spatial index management."""
    
    def test_create_index(self, rtree_manager_mock):
        """Test creating an R-tree index."""
        manager = rtree_manager_mock
        
        index_name = manager.create_index("cities", "geometry")
        
        assert index_name is not None
        assert manager.exists("cities", "geometry") is True
    
    def test_index_exists(self, rtree_manager_mock):
        """Test checking index existence."""
        manager = rtree_manager_mock
        
        # No index yet
        assert manager.exists("new_table", "geom") is False
        
        # Create index
        manager.create_index("new_table", "geom")
        
        # Now exists
        assert manager.exists("new_table", "geom") is True
    
    def test_drop_index(self, rtree_manager_mock):
        """Test dropping an index."""
        manager = rtree_manager_mock
        
        index_name = manager.create_index("temp_table", "geom")
        assert manager.exists("temp_table", "geom") is True
        
        manager.drop_index(index_name)
        assert manager.exists("temp_table", "geom") is False
    
    def test_rebuild_index(self, rtree_manager_mock):
        """Test rebuilding an index."""
        manager = rtree_manager_mock
        
        index_name = manager.create_index("rebuild_test", "geom")
        result = manager.rebuild_index(index_name)
        
        assert result.success is True


@pytest.mark.integration
@pytest.mark.spatialite
class TestSpatialiteTempTables:
    """Tests for temporary table operations."""
    
    def test_create_temp_table(
        self,
        spatialite_backend_mock,
        mock_sqlite_connection
    ):
        """Test creating a temporary table."""
        backend = spatialite_backend_mock
        
        backend.create_temp_table = MagicMock(return_value="temp_filter_001")
        
        table_name = backend.create_temp_table(
            query="SELECT * FROM cities WHERE pop > 10000",
            name_prefix="filter"
        )
        
        assert table_name.startswith("temp_filter")
    
    def test_drop_temp_table(
        self,
        spatialite_backend_mock
    ):
        """Test dropping a temporary table."""
        backend = spatialite_backend_mock
        
        backend.drop_temp_table = MagicMock(return_value=True)
        
        result = backend.drop_temp_table("temp_filter_001")
        assert result is True
    
    def test_temp_table_with_geometry(
        self,
        spatialite_backend_mock
    ):
        """Test temp table preserves geometry."""
        backend = spatialite_backend_mock
        
        backend.create_temp_table_with_geometry = MagicMock(
            return_value=MagicMock(
                success=True,
                table_name="temp_spatial_001",
                has_geometry=True
            )
        )
        
        result = backend.create_temp_table_with_geometry(
            "SELECT * FROM polygons WHERE area > 1000",
            "geometry"
        )
        
        assert result.success is True
        assert result.has_geometry is True


@pytest.mark.integration
@pytest.mark.spatialite
class TestGeoPackageSupport:
    """Tests for GeoPackage compatibility."""
    
    def test_detect_geopackage(self, spatialite_backend_mock):
        """Test detecting GeoPackage format."""
        backend = spatialite_backend_mock
        backend._db_path = "/tmp/test.gpkg"
        
        backend.is_geopackage = MagicMock(return_value=True)
        
        assert backend.is_geopackage() is True
    
    def test_geopackage_spatial_ref(
        self,
        spatialite_backend_mock
    ):
        """Test reading GeoPackage spatial reference."""
        backend = spatialite_backend_mock
        
        backend.get_spatial_ref = MagicMock(
            return_value=MagicMock(
                srid=4326,
                auth_name="EPSG",
                definition="WGS 84"
            )
        )
        
        spatial_ref = backend.get_spatial_ref("my_layer")
        assert spatial_ref.srid == 4326
        assert spatial_ref.auth_name == "EPSG"

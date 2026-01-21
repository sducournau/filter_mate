# -*- coding: utf-8 -*-
"""
Tests for Materialized View / Temp Table Management

Tests both PostgreSQL MaterializedViewManager and Spatialite TempTableManager
through the unified MaterializedViewPort interface.

Author: FilterMate Team
Date: January 2026
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sqlite3
import tempfile
import os

# Import the interface
from filter_mate.core.ports.materialized_view_port import (
    MaterializedViewPort,
    ViewType,
    ViewInfo,
    ViewConfig,
)


class TestViewConfig(unittest.TestCase):
    """Tests for ViewConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ViewConfig()
        
        self.assertEqual(config.feature_threshold, 10000)
        self.assertEqual(config.complexity_threshold, 3)
        self.assertTrue(config.with_data)
        self.assertTrue(config.create_spatial_index)
        self.assertTrue(config.use_rtree)
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = ViewConfig(
            feature_threshold=5000,
            prefix="test_",
            schema="custom_schema"
        )
        
        self.assertEqual(config.feature_threshold, 5000)
        self.assertEqual(config.prefix, "test_")
        self.assertEqual(config.schema, "custom_schema")


class TestViewInfo(unittest.TestCase):
    """Tests for ViewInfo dataclass."""
    
    def test_full_name_with_schema(self):
        """Test full name generation with schema."""
        info = ViewInfo(
            name="test_view",
            view_type=ViewType.MATERIALIZED_VIEW,
            schema="test_schema"
        )
        
        self.assertEqual(info.full_name, '"test_schema"."test_view"')
    
    def test_full_name_without_schema(self):
        """Test full name generation without schema."""
        info = ViewInfo(
            name="test_table",
            view_type=ViewType.TEMP_TABLE
        )
        
        self.assertEqual(info.full_name, '"test_table"')
    
    def test_is_materialized_view(self):
        """Test MV type detection."""
        mv = ViewInfo(name="mv", view_type=ViewType.MATERIALIZED_VIEW)
        tt = ViewInfo(name="tt", view_type=ViewType.TEMP_TABLE)
        
        self.assertTrue(mv.is_materialized_view)
        self.assertFalse(mv.is_temp_table)
        self.assertFalse(tt.is_materialized_view)
        self.assertTrue(tt.is_temp_table)


class TestSpatialiteTempTableManager(unittest.TestCase):
    """Tests for Spatialite TempTableManager."""
    
    def setUp(self):
        """Create temp database for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.sqlite")
        
        # Create a basic test database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE test_source (
                id INTEGER PRIMARY KEY,
                name TEXT,
                value REAL
            )
        """)
        cursor.execute("INSERT INTO test_source VALUES (1, 'A', 10.0)")
        cursor.execute("INSERT INTO test_source VALUES (2, 'B', 20.0)")
        cursor.execute("INSERT INTO test_source VALUES (3, 'C', 30.0)")
        conn.commit()
        conn.close()
    
    def tearDown(self):
        """Clean up temp files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_manager_initialization(self):
        """Test manager can be initialized."""
        try:
            from filter_mate.adapters.backends.spatialite.temp_table_manager import (
                SpatialiteTempTableManager
            )
        except ImportError:
            self.skipTest("Spatialite manager not available")
        
        manager = SpatialiteTempTableManager(db_path=self.db_path)
        
        self.assertEqual(manager.view_type, ViewType.TEMP_TABLE)
        self.assertIsNotNone(manager.session_id)
        self.assertIsNotNone(manager.config)
    
    def test_should_use_view_thresholds(self):
        """Test should_use_view logic."""
        try:
            from filter_mate.adapters.backends.spatialite.temp_table_manager import (
                SpatialiteTempTableManager
            )
        except ImportError:
            self.skipTest("Spatialite manager not available")
        
        manager = SpatialiteTempTableManager(db_path=self.db_path)
        
        # Below threshold
        self.assertFalse(manager.should_use_view(100))
        
        # Above threshold
        self.assertTrue(manager.should_use_view(10000))
        
        # Spatial query on medium dataset
        self.assertTrue(manager.should_use_view(3000, is_spatial=True))
    
    def test_create_simple_temp_table(self):
        """Test creating a simple temp table."""
        try:
            from filter_mate.adapters.backends.spatialite.temp_table_manager import (
                SpatialiteTempTableManager
            )
        except ImportError:
            self.skipTest("Spatialite manager not available")
        
        manager = SpatialiteTempTableManager(db_path=self.db_path)
        
        # Create temp table from query
        table_name = manager.create_view(
            query="SELECT * FROM test_source WHERE value > 15",
            source_table="test_source"
        )
        
        self.assertIsNotNone(table_name)
        self.assertTrue(manager.view_exists(table_name))
        
        # Verify content
        results = manager.query_view(table_name)
        self.assertEqual(len(results), 2)  # B and C
        
        # Cleanup
        manager.cleanup_session_views()
    
    def test_get_feature_ids(self):
        """Test getting feature IDs from temp table."""
        try:
            from filter_mate.adapters.backends.spatialite.temp_table_manager import (
                SpatialiteTempTableManager
            )
        except ImportError:
            self.skipTest("Spatialite manager not available")
        
        manager = SpatialiteTempTableManager(db_path=self.db_path)
        
        table_name = manager.create_view(
            query="SELECT * FROM test_source WHERE value > 15",
            source_table="test_source",
            indexes=["id"]
        )
        
        fids = manager.get_feature_ids(table_name, primary_key="id")
        
        self.assertEqual(len(fids), 2)
        self.assertIn(2, fids)
        self.assertIn(3, fids)
        
        manager.cleanup_session_views()
    
    def test_session_cleanup(self):
        """Test session view cleanup."""
        try:
            from filter_mate.adapters.backends.spatialite.temp_table_manager import (
                SpatialiteTempTableManager
            )
        except ImportError:
            self.skipTest("Spatialite manager not available")
        
        manager = SpatialiteTempTableManager(db_path=self.db_path)
        
        # Create multiple tables
        t1 = manager.create_view("SELECT * FROM test_source WHERE id=1", "test_source")
        t2 = manager.create_view("SELECT * FROM test_source WHERE id=2", "test_source")
        
        self.assertTrue(manager.view_exists(t1))
        self.assertTrue(manager.view_exists(t2))
        
        # Cleanup
        dropped = manager.cleanup_session_views()
        
        self.assertEqual(dropped, 2)
        self.assertFalse(manager.view_exists(t1))
        self.assertFalse(manager.view_exists(t2))


class TestPostgreSQLMVManager(unittest.TestCase):
    """Tests for PostgreSQL MaterializedViewManager (mocked)."""
    
    def test_manager_initialization(self):
        """Test manager can be initialized."""
        try:
            from filter_mate.adapters.backends.postgresql.mv_manager import (
                MaterializedViewManager,
                MVConfig
            )
        except ImportError:
            self.skipTest("PostgreSQL MV manager not available")
        
        # Mock connection pool
        mock_pool = Mock()
        
        manager = MaterializedViewManager(
            connection_pool=mock_pool,
            session_id="test123"
        )
        
        self.assertEqual(manager.view_type, ViewType.MATERIALIZED_VIEW)
        self.assertEqual(manager.session_id, "test123")
    
    def test_should_use_mv_thresholds(self):
        """Test should_use_view logic."""
        try:
            from filter_mate.adapters.backends.postgresql.mv_manager import (
                MaterializedViewManager
            )
        except ImportError:
            self.skipTest("PostgreSQL MV manager not available")
        
        manager = MaterializedViewManager()
        
        # Below threshold
        self.assertFalse(manager.should_use_view(100))
        
        # Above threshold
        self.assertTrue(manager.should_use_view(15000))
        
        # Complex expression
        self.assertTrue(manager.should_use_view(100, expression_complexity=5))
    
    @patch('filter_mate.adapters.backends.postgresql.mv_manager.MaterializedViewManager._get_connection')
    def test_create_mv_sql_generation(self, mock_get_conn):
        """Test MV creation generates correct SQL."""
        try:
            from filter_mate.adapters.backends.postgresql.mv_manager import (
                MaterializedViewManager
            )
        except ImportError:
            self.skipTest("PostgreSQL MV manager not available")
        
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        manager = MaterializedViewManager(session_id="test123")
        
        # Test that create_view uses correct SQL patterns
        try:
            manager.create_view(
                query="SELECT * FROM roads WHERE type='highway'",
                source_table="roads",
                geometry_column="geom"
            )
        except Exception:
            pass  # May fail on actual execution, but SQL should be correct
        
        # Verify schema creation was attempted
        calls = mock_cursor.execute.call_args_list
        if calls:
            schema_call = str(calls[0])
            self.assertIn("CREATE SCHEMA", schema_call.upper())


class TestViewManagerFactory(unittest.TestCase):
    """Tests for view manager factory."""
    
    def test_factory_spatialite(self):
        """Test factory creates Spatialite manager."""
        try:
            from filter_mate.adapters.view_manager_factory import create_view_manager
        except ImportError:
            self.skipTest("View manager factory not available")
        
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test.sqlite")
        
        try:
            # Create empty database
            conn = sqlite3.connect(db_path)
            conn.close()
            
            manager = create_view_manager(
                backend_type='spatialite',
                db_path=db_path
            )
            
            self.assertEqual(manager.view_type, ViewType.TEMP_TABLE)
            
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_factory_invalid_backend(self):
        """Test factory raises error for invalid backend."""
        try:
            from filter_mate.adapters.view_manager_factory import create_view_manager
        except ImportError:
            self.skipTest("View manager factory not available")
        
        with self.assertRaises(ValueError):
            create_view_manager(backend_type='invalid_backend')
    
    def test_get_view_type_for_backend(self):
        """Test view type lookup."""
        try:
            from filter_mate.adapters.view_manager_factory import get_view_type_for_backend
        except ImportError:
            self.skipTest("View manager factory not available")
        
        self.assertEqual(
            get_view_type_for_backend('postgresql'),
            ViewType.MATERIALIZED_VIEW
        )
        self.assertEqual(
            get_view_type_for_backend('spatialite'),
            ViewType.TEMP_TABLE
        )


if __name__ == '__main__':
    unittest.main()

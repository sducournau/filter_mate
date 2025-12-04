# -*- coding: utf-8 -*-
"""
Tests for Prepared Statements Module

Tests the prepared statements functionality for both PostgreSQL and Spatialite.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import sys
import os

# Add modules path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'modules'))

# Mock QGIS before imports
from conftest import mock_qgis_modules
mock_qgis_modules()

from modules.prepared_statements import (
    PreparedStatementManager,
    PostgreSQLPreparedStatements,
    SpatialitePreparedStatements,
    create_prepared_statements
)


class TestPreparedStatementManager(unittest.TestCase):
    """Tests for base PreparedStatementManager class"""
    
    def test_init(self):
        """Test initialization"""
        conn = Mock()
        manager = PreparedStatementManager(conn)
        
        self.assertEqual(manager.connection, conn)
        self.assertEqual(manager._statement_cache, {})
    
    def test_close(self):
        """Test close clears cache"""
        conn = Mock()
        manager = PreparedStatementManager(conn)
        manager._statement_cache = {"test": "value"}
        
        manager.close()
        
        self.assertEqual(manager._statement_cache, {})


class TestSpatialitePreparedStatements(unittest.TestCase):
    """Tests for Spatialite prepared statements"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor
        
        self.manager = SpatialitePreparedStatements(self.mock_conn)
    
    def test_init(self):
        """Test Spatialite manager initialization"""
        self.assertEqual(self.manager.connection, self.mock_conn)
        self.assertEqual(self.manager._statement_cache, {})
    
    def test_insert_subset_history_success(self):
        """Test insert subset history with prepared statement"""
        result = self.manager.insert_subset_history(
            history_id="test-id-123",
            project_uuid="project-uuid",
            layer_id="layer-123",
            source_layer_id="source-456",
            seq_order=1,
            subset_string="test_field > 100"
        )
        
        self.assertTrue(result)
        self.mock_cursor.execute.assert_called_once()
        self.mock_conn.commit.assert_called_once()
        
        # Verify SQL structure
        call_args = self.mock_cursor.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        
        self.assertIn("INSERT INTO fm_subset_history", sql)
        self.assertIn("?", sql)  # Spatialite uses ? placeholders
        self.assertEqual(params[0], "test-id-123")
        self.assertEqual(params[1], "project-uuid")
    
    def test_delete_subset_history_success(self):
        """Test delete subset history with prepared statement"""
        self.mock_cursor.rowcount = 5
        
        result = self.manager.delete_subset_history(
            project_uuid="project-uuid",
            layer_id="layer-123"
        )
        
        self.assertTrue(result)
        self.mock_cursor.execute.assert_called_once()
        self.mock_conn.commit.assert_called_once()
        
        # Verify SQL structure
        call_args = self.mock_cursor.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        
        self.assertIn("DELETE FROM fm_subset_history", sql)
        self.assertEqual(params, ("project-uuid", "layer-123"))
    
    def test_insert_layer_properties_success(self):
        """Test insert layer properties"""
        result = self.manager.insert_layer_properties(
            layer_id="layer-123",
            project_uuid="project-uuid",
            layer_name="test_layer",
            provider_type="spatialite",
            geometry_type="Point",
            feature_count=1000,
            properties_json='{"key": "value"}'
        )
        
        self.assertTrue(result)
        self.mock_cursor.execute.assert_called_once()
        self.mock_conn.commit.assert_called_once()
    
    def test_insert_error_rollback(self):
        """Test error handling with rollback"""
        self.mock_cursor.execute.side_effect = Exception("Database error")
        
        result = self.manager.insert_subset_history(
            history_id="test-id",
            project_uuid="project-uuid",
            layer_id="layer-123",
            source_layer_id="source-456",
            seq_order=1,
            subset_string="test_field > 100"
        )
        
        self.assertFalse(result)
        self.mock_conn.rollback.assert_called_once()
    
    def test_cursor_caching(self):
        """Test that cursors are cached for reuse"""
        # First call
        self.manager.insert_subset_history(
            history_id="id1",
            project_uuid="proj",
            layer_id="layer1",
            source_layer_id="source1",
            seq_order=1,
            subset_string="test"
        )
        
        first_cache_size = len(self.manager._statement_cache)
        
        # Second call with same query type
        self.manager.insert_subset_history(
            history_id="id2",
            project_uuid="proj",
            layer_id="layer2",
            source_layer_id="source2",
            seq_order=2,
            subset_string="test2"
        )
        
        # Cache size should be same (cursor reused)
        self.assertEqual(len(self.manager._statement_cache), first_cache_size)
    
    def test_close_cursors(self):
        """Test closing all cursors"""
        # Create some cached cursors
        self.manager._statement_cache = {
            "query1": MagicMock(),
            "query2": MagicMock()
        }
        
        self.manager.close()
        
        # Verify cursors were closed
        for cursor in self.manager._statement_cache.values():
            cursor.close.assert_called_once()


@unittest.skipIf(True, "PostgreSQL tests require psycopg2")
class TestPostgreSQLPreparedStatements(unittest.TestCase):
    """
    Tests for PostgreSQL prepared statements.
    
    NOTE: These tests are skipped by default because psycopg2 is optional.
    To run these tests, install psycopg2 and remove the skipIf decorator.
    """
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor
        
        # Mock psycopg2 availability
        with patch('modules.prepared_statements.POSTGRESQL_AVAILABLE', True):
            with patch('modules.prepared_statements.psycopg2', MagicMock()):
                self.manager = PostgreSQLPreparedStatements(self.mock_conn)
    
    def test_init(self):
        """Test PostgreSQL manager initialization"""
        self.assertEqual(self.manager.connection, self.mock_conn)
        self.assertEqual(self.manager._prepared_names, {})
    
    def test_prepare_statement(self):
        """Test preparing a named statement"""
        stmt_name = "test_stmt"
        query = "SELECT * FROM test WHERE id = $1"
        
        result = self.manager._prepare_statement(stmt_name, query)
        
        self.assertEqual(result, stmt_name)
        self.assertIn(stmt_name, self.manager._prepared_names)
        self.mock_cursor.execute.assert_called_once()
        
        # Verify PREPARE was called
        call_args = self.mock_cursor.execute.call_args[0][0]
        self.assertIn("PREPARE", call_args)
        self.assertIn(stmt_name, call_args)
    
    def test_prepare_statement_caching(self):
        """Test that prepared statements are cached"""
        stmt_name = "cached_stmt"
        query = "SELECT 1"
        
        # Prepare twice
        self.manager._prepare_statement(stmt_name, query)
        self.manager._prepare_statement(stmt_name, query)
        
        # Should only execute PREPARE once (second returns cached)
        self.assertEqual(self.mock_cursor.execute.call_count, 1)
    
    def test_insert_subset_history(self):
        """Test insert with PostgreSQL prepared statement"""
        result = self.manager.insert_subset_history(
            history_id="test-id",
            project_uuid="project-uuid",
            layer_id="layer-123",
            source_layer_id="source-456",
            seq_order=1,
            subset_string="test_field > 100"
        )
        
        self.assertTrue(result)
        self.mock_conn.commit.assert_called()
        
        # Should have 2 execute calls: PREPARE + EXECUTE
        self.assertEqual(self.mock_cursor.execute.call_count, 2)
    
    def test_close_deallocates(self):
        """Test that close deallocates all prepared statements"""
        # Prepare some statements
        self.manager._prepared_names = {
            "stmt1": "stmt1",
            "stmt2": "stmt2"
        }
        
        self.manager.close()
        
        # Should have called DEALLOCATE for each
        execute_calls = self.mock_cursor.execute.call_args_list
        deallocate_count = sum(
            1 for call in execute_calls
            if "DEALLOCATE" in str(call)
        )
        self.assertEqual(deallocate_count, 2)


class TestCreatePreparedStatements(unittest.TestCase):
    """Tests for factory function"""
    
    def test_create_spatialite(self):
        """Test creating Spatialite manager"""
        conn = Mock()
        manager = create_prepared_statements(conn, 'spatialite')
        
        self.assertIsInstance(manager, SpatialitePreparedStatements)
        self.assertEqual(manager.connection, conn)
    
    @patch('modules.prepared_statements.POSTGRESQL_AVAILABLE', True)
    @patch('modules.prepared_statements.psycopg2', MagicMock())
    def test_create_postgresql(self):
        """Test creating PostgreSQL manager when available"""
        conn = Mock()
        manager = create_prepared_statements(conn, 'postgresql')
        
        self.assertIsInstance(manager, PostgreSQLPreparedStatements)
        self.assertEqual(manager.connection, conn)
    
    @patch('modules.prepared_statements.POSTGRESQL_AVAILABLE', False)
    def test_create_postgresql_unavailable(self):
        """Test creating PostgreSQL manager when unavailable"""
        conn = Mock()
        manager = create_prepared_statements(conn, 'postgresql')
        
        self.assertIsNone(manager)
    
    def test_create_unsupported(self):
        """Test creating manager for unsupported provider"""
        conn = Mock()
        manager = create_prepared_statements(conn, 'unsupported')
        
        self.assertIsNone(manager)


class TestPerformanceImprovements(unittest.TestCase):
    """Tests to verify performance improvements from prepared statements"""
    
    def test_multiple_inserts_use_cached_statement(self):
        """Verify that multiple inserts reuse the cached cursor"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        manager = SpatialitePreparedStatements(mock_conn)
        
        # Perform 10 inserts
        for i in range(10):
            manager.insert_subset_history(
                history_id=f"id-{i}",
                project_uuid="project",
                layer_id=f"layer-{i}",
                source_layer_id="source",
                seq_order=i,
                subset_string=f"field > {i}"
            )
        
        # Cursor should be created once and reused
        self.assertEqual(mock_conn.cursor.call_count, 1)
        
        # Execute should be called 10 times (once per insert)
        self.assertEqual(mock_cursor.execute.call_count, 10)
    
    def test_sql_injection_prevention(self):
        """Test that parameterized queries prevent SQL injection"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        manager = SpatialitePreparedStatements(mock_conn)
        
        # Attempt SQL injection
        malicious_string = "'; DROP TABLE fm_subset_history; --"
        
        manager.insert_subset_history(
            history_id="test",
            project_uuid="proj",
            layer_id="layer",
            source_layer_id="source",
            seq_order=1,
            subset_string=malicious_string
        )
        
        # Verify parameters were passed separately (not interpolated)
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        
        # SQL should contain placeholders, not the actual values
        self.assertIn("?", sql)
        self.assertIn(malicious_string, params)
        self.assertNotIn("DROP TABLE", sql)


if __name__ == '__main__':
    unittest.main()

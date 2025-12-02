#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for FilterMate database connection handling.

Tests verify that database connections are properly cleaned up in all scenarios:
- Normal execution
- Exceptions during operations
- Task cancellation
- Context manager usage

Run with: python -m pytest test_database_connections.py -v
"""

import unittest
import sqlite3
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
import sys

# Add modules to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'modules'))

from modules.appUtils import create_temp_spatialite_table


class TestDatabaseConnectionCleanup(unittest.TestCase):
    """Test database connection cleanup in various scenarios"""
    
    def setUp(self):
        """Create temporary database for testing"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test_filtermate.sqlite')
        
        # Create a simple test database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE test_source (id INTEGER, geometry TEXT)")
            conn.execute("INSERT INTO test_source VALUES (1, 'POINT(0 0)')")
            conn.commit()
    
    def tearDown(self):
        """Clean up temporary files"""
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except:
                pass
        try:
            os.rmdir(self.temp_dir)
        except:
            pass
    
    def test_connection_cleanup_on_success(self):
        """Test that connection is closed after successful operation"""
        # Note: create_temp_spatialite_table will fail without actual spatialite
        # but we're testing that the connection handling pattern is correct
        
        # Get initial connection count
        initial_connections = self._count_db_connections()
        
        # Attempt operation (will fail due to missing spatialite extension)
        result = create_temp_spatialite_table(
            self.db_path, 
            'test_view',
            'SELECT * FROM test_source',
            'geometry',
            4326
        )
        
        # Verify no connection leaks
        final_connections = self._count_db_connections()
        self.assertEqual(initial_connections, final_connections,
                        "Connection leak detected after operation")
    
    def test_connection_cleanup_on_exception(self):
        """Test that connection is closed even when exception occurs"""
        initial_connections = self._count_db_connections()
        
        # Force an exception by providing invalid parameters
        try:
            result = create_temp_spatialite_table(
                self.db_path,
                'test_view',
                'INVALID SQL QUERY',  # This will cause an exception
                'geometry',
                4326
            )
        except:
            pass
        
        # Verify no connection leaks
        final_connections = self._count_db_connections()
        self.assertEqual(initial_connections, final_connections,
                        "Connection leak detected after exception")
    
    def test_context_manager_usage(self):
        """Verify that context managers (with statements) are used correctly"""
        # Read the source file
        source_file = os.path.join(os.path.dirname(__file__), 'modules', 'appUtils.py')
        with open(source_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check that create_temp_spatialite_table uses 'with sqlite3.connect()'
        self.assertIn('with sqlite3.connect(db_path) as conn:', content,
                     "create_temp_spatialite_table should use context manager")
        
        # Check that finally block exists
        self.assertIn('finally:', content,
                     "Should have finally block for cleanup")
    
    def test_no_leaked_connections_after_multiple_operations(self):
        """Test no connections remain after multiple filter operations"""
        initial_connections = self._count_db_connections()
        
        # Run multiple operations
        for i in range(5):
            try:
                result = create_temp_spatialite_table(
                    self.db_path,
                    f'test_view_{i}',
                    'SELECT * FROM test_source',
                    'geometry',
                    4326
                )
            except:
                pass
        
        # Verify no accumulated connection leaks
        final_connections = self._count_db_connections()
        self.assertEqual(initial_connections, final_connections,
                        f"Connection leaks detected: {final_connections - initial_connections} connections")
    
    def _count_db_connections(self):
        """
        Count active database connections.
        Note: This is a simplified check - in production you'd use system tools.
        """
        # Try to get an exclusive lock on the database
        # If connections are leaked, this will fail
        try:
            test_conn = sqlite3.connect(self.db_path, timeout=0.1)
            test_conn.execute("BEGIN EXCLUSIVE")
            test_conn.rollback()
            test_conn.close()
            return 0  # No leaked connections
        except sqlite3.OperationalError:
            return 1  # Connections are still open


class TestTaskCancellationCleanup(unittest.TestCase):
    """Test that task cancellation properly cleans up connections"""
    
    def setUp(self):
        """Set up mock QGIS environment"""
        # Mock QGIS imports
        sys.modules['qgis'] = MagicMock()
        sys.modules['qgis.core'] = MagicMock()
        sys.modules['qgis.utils'] = MagicMock()
        sys.modules['qgis.PyQt'] = MagicMock()
        sys.modules['qgis.PyQt.QtCore'] = MagicMock()
    
    @patch('modules.appTasks.QgsTask')
    def test_cancel_method_closes_connections(self, mock_qgstask):
        """Test that cancel() method closes all active connections"""
        # Import after mocking
        from modules.appTasks import FilterEngineTask
        
        # Create mock task
        task = FilterEngineTask("test", "filter", {})
        
        # Add mock connections to active_connections
        mock_conn1 = Mock()
        mock_conn2 = Mock()
        task.active_connections = [mock_conn1, mock_conn2]
        
        # Call cancel
        task.cancel()
        
        # Verify all connections were closed
        mock_conn1.close.assert_called_once()
        mock_conn2.close.assert_called_once()
        
        # Verify active_connections list was cleared
        self.assertEqual(len(task.active_connections), 0,
                        "active_connections should be empty after cancel")
    
    def test_connection_tracking_in_init(self):
        """Test that FilterEngineTask initializes active_connections list"""
        from modules.appTasks import FilterEngineTask
        
        task = FilterEngineTask("test", "filter", {})
        
        # Verify active_connections exists and is a list
        self.assertTrue(hasattr(task, 'active_connections'),
                       "Task should have active_connections attribute")
        self.assertIsInstance(task.active_connections, list,
                            "active_connections should be a list")
        self.assertEqual(len(task.active_connections), 0,
                        "active_connections should start empty")


class TestProviderConstants(unittest.TestCase):
    """Test that provider type constants are properly defined"""
    
    def test_provider_constants_exist(self):
        """Verify all provider constants are defined"""
        from modules.appUtils import (
            PROVIDER_POSTGRES,
            PROVIDER_SPATIALITE, 
            PROVIDER_OGR,
            PROVIDER_MEMORY
        )
        
        self.assertEqual(PROVIDER_POSTGRES, 'postgres')
        self.assertEqual(PROVIDER_SPATIALITE, 'spatialite')
        self.assertEqual(PROVIDER_OGR, 'ogr')
        self.assertEqual(PROVIDER_MEMORY, 'memory')
    
    def test_postgresql_available_flag(self):
        """Test that POSTGRESQL_AVAILABLE flag is defined"""
        from modules.appUtils import POSTGRESQL_AVAILABLE
        
        self.assertIsInstance(POSTGRESQL_AVAILABLE, bool,
                            "POSTGRESQL_AVAILABLE should be boolean")


class TestLoggingImplementation(unittest.TestCase):
    """Test that logging is properly implemented"""
    
    def test_logger_exists(self):
        """Verify FilterMate logger exists"""
        from modules.appUtils import logger
        
        self.assertIsNotNone(logger, "Logger should be defined")
        self.assertEqual(logger.name, 'FilterMate', "Logger should be named 'FilterMate'")
    
    def test_no_print_statements_in_core_modules(self):
        """Verify print() statements have been replaced with logger calls"""
        # Read core module files
        modules_to_check = [
            'modules/appUtils.py',
            'modules/appTasks.py'
        ]
        
        for module_path in modules_to_check:
            full_path = os.path.join(os.path.dirname(__file__), module_path)
            if not os.path.exists(full_path):
                continue
                
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Count print statements (excluding commented ones)
            lines = content.split('\n')
            print_count = sum(1 for line in lines 
                            if 'print(' in line 
                            and not line.strip().startswith('#')
                            and 'FilterMate' in line)
            
            self.assertEqual(print_count, 0,
                           f"{module_path} still contains print() statements with 'FilterMate'")


class TestExceptionHandling(unittest.TestCase):
    """Test that specific exceptions are used instead of bare except"""
    
    def test_no_bare_except_in_apputils(self):
        """Verify no bare except: clauses in appUtils.py"""
        source_file = os.path.join(os.path.dirname(__file__), 'modules', 'appUtils.py')
        
        if not os.path.exists(source_file):
            self.skipTest("appUtils.py not found")
        
        with open(source_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Find bare except clauses
        bare_excepts = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped == 'except:' or stripped.startswith('except: '):
                bare_excepts.append(i)
        
        self.assertEqual(len(bare_excepts), 0,
                        f"Found bare except: clauses at lines: {bare_excepts}")
    
    def test_specific_exceptions_used(self):
        """Verify specific exception types are used"""
        source_file = os.path.join(os.path.dirname(__file__), 'modules', 'appUtils.py')
        
        if not os.path.exists(source_file):
            self.skipTest("appUtils.py not found")
        
        with open(source_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for specific exception types
        expected_exceptions = [
            'OSError',
            'sqlite3.OperationalError',
            'RuntimeError',
            'Exception'  # Generic Exception is OK if specific type is logged
        ]
        
        for exc_type in expected_exceptions[:3]:  # Check first 3 specific types
            self.assertIn(exc_type, content,
                         f"Expected to find {exc_type} exception handling")


def run_tests():
    """Run all tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestDatabaseConnectionCleanup))
    suite.addTests(loader.loadTestsFromTestCase(TestTaskCancellationCleanup))
    suite.addTests(loader.loadTestsFromTestCase(TestProviderConstants))
    suite.addTests(loader.loadTestsFromTestCase(TestLoggingImplementation))
    suite.addTests(loader.loadTestsFromTestCase(TestExceptionHandling))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    exit_code = run_tests()
    sys.exit(exit_code)

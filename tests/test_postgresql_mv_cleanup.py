"""
Test PostgreSQL Materialized Views Cleanup

Tests the automatic cleanup of PostgreSQL materialized views created during filtering.
This ensures temporary MVs don't accumulate in the database.

Test scenarios:
1. Cleanup after successful filter operation
2. Cleanup after task cancellation
3. Cleanup after exception/error
4. Cleanup when psycopg2 not available (should skip gracefully)
5. Cleanup when layer is not PostgreSQL (should skip)
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call
import sys
import os

# Add parent directory to path for imports
plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)


class TestPostgreSQLMVCleanup(unittest.TestCase):
    """Test automatic cleanup of PostgreSQL materialized views."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock QGIS dependencies
        self.qgis_patches = [
            patch('qgis.core.QgsTask'),
            patch('qgis.core.QgsMessageLog'),
            patch('qgis.utils.iface'),
        ]
        for p in self.qgis_patches:
            p.start()
    
    def tearDown(self):
        """Clean up patches."""
        for p in self.qgis_patches:
            p.stop()
    
    @patch('filter_mate.core.tasks.filter_task.POSTGRESQL_AVAILABLE', True)
    @patch('filter_mate.core.tasks.filter_task.logger')
    def test_cleanup_called_on_finished_success(self, mock_logger):
        """Test that cleanup is called when task finishes successfully."""
        from filter_mate.core.tasks.filter_task import FilterEngineTask
        
        # Create mock task
        task = FilterEngineTask("Test Task", "filter", {
            'source_layer': Mock(),
        })
        task.param_source_provider_type = 'postgresql'
        task.source_layer = Mock()
        task.source_layer.providerType.return_value = 'postgres'
        
        # Mock the cleanup method
        task._cleanup_postgresql_materialized_views = Mock()
        
        # Call finished with success
        with patch('filter_mate.core.tasks.filter_task.MESSAGE_TASKS_CATEGORIES', {'filter': 'FilterLayers'}):
            task.finished(result=True)
        
        # Verify cleanup was called
        task._cleanup_postgresql_materialized_views.assert_called_once()
        mock_logger.debug.assert_any_call("PostgreSQL materialized views cleaned up successfully")
    
    @patch('filter_mate.core.tasks.filter_task.POSTGRESQL_AVAILABLE', True)
    @patch('filter_mate.core.tasks.filter_task.logger')
    def test_cleanup_called_on_cancel(self, mock_logger):
        """Test that cleanup is called when task is cancelled."""
        from filter_mate.core.tasks.filter_task import FilterEngineTask
        
        # Create mock task
        task = FilterEngineTask("Test Task", "filter", {
            'source_layer': Mock(),
        })
        task.param_source_provider_type = 'postgresql'
        task.source_layer = Mock()
        
        # Mock the cleanup method
        task._cleanup_postgresql_materialized_views = Mock()
        
        # Mock parent cancel
        with patch('qgis.core.QgsTask.cancel'):
            task.cancel()
        
        # Verify cleanup was called before connections cleanup
        task._cleanup_postgresql_materialized_views.assert_called_once()
    
    @patch('filter_mate.core.tasks.filter_task.POSTGRESQL_AVAILABLE', False)
    @patch('filter_mate.core.tasks.filter_task.logger')
    def test_cleanup_skipped_when_postgresql_unavailable(self, mock_logger):
        """Test that cleanup is skipped gracefully when psycopg2 not available."""
        from filter_mate.core.tasks.filter_task import FilterEngineTask
        
        # Create mock task
        task = FilterEngineTask("Test Task", "filter", {})
        task.param_source_provider_type = 'postgresql'
        
        # Call cleanup directly
        task._cleanup_postgresql_materialized_views()
        
        # Should return early without errors
        # No specific logger call expected (early return)
    
    @patch('filter_mate.core.tasks.filter_task.POSTGRESQL_AVAILABLE', True)
    @patch('filter_mate.core.tasks.filter_task.logger')
    def test_cleanup_skipped_for_non_postgresql_layer(self, mock_logger):
        """Test that cleanup is skipped for non-PostgreSQL layers."""
        from filter_mate.core.tasks.filter_task import FilterEngineTask
        
        # Create mock task with Spatialite layer
        task = FilterEngineTask("Test Task", "filter", {})
        task.param_source_provider_type = 'spatialite'
        
        # Call cleanup directly
        task._cleanup_postgresql_materialized_views()
        
        # Should return early without attempting cleanup
        # Logger not called for PostgreSQL cleanup
    
    @patch('filter_mate.core.tasks.filter_task.POSTGRESQL_AVAILABLE', True)
    @patch('filter_mate.adapters.backends.postgresql.backend.get_datasource_connexion_from_layer')
    @patch('filter_mate.core.tasks.filter_task.logger')
    def test_cleanup_calls_backend_method(self, mock_logger, mock_get_conn):
        """Test that cleanup properly calls backend cleanup_materialized_views."""
        from filter_mate.core.tasks.filter_task import FilterEngineTask
        
        # Create mock layer
        mock_layer = Mock()
        mock_layer.providerType.return_value = 'postgres'
        
        # Create mock task
        task = FilterEngineTask("Test Task", "filter", {
            'source_layer': mock_layer,
        })
        task.param_source_provider_type = 'postgresql'
        task.source_layer = mock_layer
        
        # Mock PostgreSQL backend
        mock_backend = Mock()
        mock_backend.cleanup_materialized_views.return_value = True
        
        with patch('filter_mate.core.tasks.filter_task.PostgreSQLGeometricFilter', return_value=mock_backend):
            task._cleanup_postgresql_materialized_views()
        
        # Verify backend cleanup was called
        mock_backend.cleanup_materialized_views.assert_called_once_with(mock_layer)
        mock_logger.debug.assert_called_with("PostgreSQL materialized views cleaned up successfully")
    
    @patch('filter_mate.core.tasks.filter_task.POSTGRESQL_AVAILABLE', True)
    @patch('filter_mate.core.tasks.filter_task.logger')
    def test_cleanup_handles_exceptions_gracefully(self, mock_logger):
        """Test that cleanup exceptions don't crash the task."""
        from filter_mate.core.tasks.filter_task import FilterEngineTask
        
        # Create mock task
        mock_layer = Mock()
        task = FilterEngineTask("Test Task", "filter", {
            'source_layer': mock_layer,
        })
        task.param_source_provider_type = 'postgresql'
        task.source_layer = mock_layer
        
        # Mock backend to raise exception
        mock_backend = Mock()
        mock_backend.cleanup_materialized_views.side_effect = Exception("Connection error")
        
        with patch('filter_mate.core.tasks.filter_task.PostgreSQLGeometricFilter', return_value=mock_backend):
            # Should not raise exception
            task._cleanup_postgresql_materialized_views()
        
        # Verify error was logged
        mock_logger.debug.assert_called()
        logged_message = str(mock_logger.debug.call_args)
        self.assertIn("Error during PostgreSQL MV cleanup", logged_message)
    
    @patch('filter_mate.core.tasks.filter_task.POSTGRESQL_AVAILABLE', True)
    @patch('filter_mate.adapters.backends.postgresql.backend.get_datasource_connexion_from_layer')
    @patch('filter_mate.core.tasks.filter_task.logger')
    def test_cleanup_with_source_layer_from_attributes(self, mock_logger, mock_get_conn):
        """Test cleanup retrieves source layer from task attributes."""
        from filter_mate.core.tasks.filter_task import FilterEngineTask
        
        # Create mock layer
        mock_layer = Mock()
        mock_layer.providerType.return_value = 'postgres'
        
        # Create task WITHOUT source_layer in parameters
        task = FilterEngineTask("Test Task", "filter", {})
        task.param_source_provider_type = 'postgresql'
        task.source_layer = mock_layer  # Set as attribute
        
        # Mock backend
        mock_backend = Mock()
        mock_backend.cleanup_materialized_views.return_value = True
        
        with patch('filter_mate.core.tasks.filter_task.PostgreSQLGeometricFilter', return_value=mock_backend):
            task._cleanup_postgresql_materialized_views()
        
        # Verify cleanup was performed with source_layer from attribute
        mock_backend.cleanup_materialized_views.assert_called_once_with(mock_layer)
    
    @patch('filter_mate.core.tasks.filter_task.POSTGRESQL_AVAILABLE', True)
    @patch('filter_mate.core.tasks.filter_task.logger')
    def test_cleanup_logs_warning_when_no_source_layer(self, mock_logger):
        """Test cleanup logs debug when source layer not available."""
        from filter_mate.core.tasks.filter_task import FilterEngineTask
        
        # Create task without source layer
        task = FilterEngineTask("Test Task", "filter", {})
        task.param_source_provider_type = 'postgresql'
        # Don't set source_layer
        
        task._cleanup_postgresql_materialized_views()
        
        # Verify debug message logged
        mock_logger.debug.assert_called_with("No source layer available for PostgreSQL MV cleanup")


class TestBackendCleanupIntegration(unittest.TestCase):
    """Test integration with PostgreSQL backend cleanup method."""
    
    @patch('filter_mate.adapters.backends.postgresql.backend.get_datasource_connexion_from_layer')
    @patch('filter_mate.adapters.backends.postgresql.backend.logger')
    def test_backend_cleanup_drops_materialized_views(self, mock_logger, mock_get_conn):
        """Test that backend cleanup actually drops materialized views."""
        from filter_mate.adapters.backends.postgresql.backend import PostgreSQLGeometricFilter
        
        # Mock PostgreSQL connection
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock cursor.fetchall to return MV names (using new unified prefix)
        mock_cursor.fetchall.return_value = [
            ('fm_temp_mv_abc123',),
            ('fm_temp_mv_def456',),
        ]
        
        mock_source_uri = Mock()
        mock_source_uri.schema.return_value = 'public'
        
        mock_get_conn.return_value = (mock_conn, mock_source_uri)
        
        # Create backend
        backend = PostgreSQLGeometricFilter({})
        
        # Create mock layer
        mock_layer = Mock()
        
        # Call cleanup
        result = backend.cleanup_materialized_views(mock_layer)
        
        # Verify cleanup was successful
        self.assertTrue(result)
        
        # Verify SQL queries were executed
        self.assertEqual(mock_cursor.execute.call_count, 3)  # 1 SELECT + 2 DROPs
        
        # Verify DROP statements were called
        drop_calls = [call[0][0] for call in mock_cursor.execute.call_args_list if 'DROP' in call[0][0]]
        self.assertEqual(len(drop_calls), 2)
        self.assertIn('fm_temp_mv_abc123', drop_calls[0])
        self.assertIn('fm_temp_mv_def456', drop_calls[1])
        
        # Verify connection was closed
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()
    
    @patch('filter_mate.adapters.backends.postgresql.backend.get_datasource_connexion_from_layer')
    @patch('filter_mate.adapters.backends.postgresql.backend.logger')
    def test_backend_cleanup_handles_no_views(self, mock_logger, mock_get_conn):
        """Test cleanup when no materialized views exist."""
        from filter_mate.adapters.backends.postgresql.backend import PostgreSQLGeometricFilter
        
        # Mock connection returning empty result
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []  # No MVs
        
        mock_source_uri = Mock()
        mock_source_uri.schema.return_value = 'public'
        
        mock_get_conn.return_value = (mock_conn, mock_source_uri)
        
        backend = PostgreSQLGeometricFilter({})
        mock_layer = Mock()
        
        result = backend.cleanup_materialized_views(mock_layer)
        
        # Should succeed without errors
        self.assertTrue(result)
        
        # Only SELECT query executed, no DROPs
        self.assertEqual(mock_cursor.execute.call_count, 1)


class TestCleanupPerformance(unittest.TestCase):
    """Test cleanup performance and overhead."""
    
    @patch('filter_mate.core.tasks.filter_task.POSTGRESQL_AVAILABLE', True)
    def test_cleanup_overhead_is_minimal(self):
        """Test that cleanup adds minimal overhead to task completion."""
        import time
        from filter_mate.core.tasks.filter_task import FilterEngineTask
        
        # Create task
        task = FilterEngineTask("Test Task", "filter", {})
        task.param_source_provider_type = 'spatialite'  # Will skip cleanup
        
        # Measure time
        start = time.time()
        for _ in range(1000):
            task._cleanup_postgresql_materialized_views()
        elapsed = time.time() - start
        
        # Should be very fast (< 10ms for 1000 calls)
        self.assertLess(elapsed, 0.01, f"Cleanup overhead too high: {elapsed:.4f}s for 1000 calls")


def run_tests():
    """Run all tests and print results."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestPostgreSQLMVCleanup))
    suite.addTests(loader.loadTestsFromTestCase(TestBackendCleanupIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestCleanupPerformance))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

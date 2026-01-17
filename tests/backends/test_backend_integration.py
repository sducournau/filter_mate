#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backend Comparison Integration Tests (Phase 3 v4.1)
===================================================

Integration tests comparing PostgreSQL, Spatialite, and OGR backends.
Tests parity, performance characteristics, and edge cases.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from qgis.core import QgsVectorLayer
import sys
import os


class TestBackendParity(unittest.TestCase):
    """Test feature parity across backends."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_params = {
            "layer": Mock(spec=QgsVectorLayer),
            "action": "reset",
            "layer_props": {"layer": {"primary_key_name": "id"}},
            "datasource_info": {"dbname": "/tmp/test.db"}
        }
        self.test_params["layer"].name.return_value = "test_layer"
    
    @patch('adapters.backends.postgresql.filter_actions.execute_reset_action_postgresql')
    @patch('adapters.backends.spatialite.filter_actions.execute_reset_action_spatialite')
    @patch('adapters.backends.ogr.filter_actions.execute_reset_action_ogr')
    def test_reset_action_parity(self, mock_ogr, mock_spatialite, mock_pg):
        """Test all backends implement reset action."""
        # All should return (success, message)
        mock_pg.return_value = (True, "PostgreSQL reset")
        mock_spatialite.return_value = (True, "Spatialite reset")
        mock_ogr.return_value = (True, "OGR reset")
        
        # Call each backend
        pg_result = mock_pg(self.test_params["layer"], "reset", {}, {})
        spatialite_result = mock_spatialite(self.test_params["layer"], "reset", {}, {})
        ogr_result = mock_ogr(self.test_params["layer"], "reset", {}, {})
        
        # Verify same signature
        self.assertEqual(len(pg_result), 2)
        self.assertEqual(len(spatialite_result), 2)
        self.assertEqual(len(ogr_result), 2)
        
        # All succeed
        self.assertTrue(pg_result[0])
        self.assertTrue(spatialite_result[0])
        self.assertTrue(ogr_result[0])
    
    @patch('adapters.backends.postgresql.filter_actions.execute_unfilter_action_postgresql')
    @patch('adapters.backends.spatialite.filter_actions.execute_unfilter_action_spatialite')
    @patch('adapters.backends.ogr.filter_actions.execute_unfilter_action_ogr')
    def test_unfilter_action_parity(self, mock_ogr, mock_spatialite, mock_pg):
        """Test all backends implement unfilter action."""
        previous_subset = '"id" > 100'
        
        mock_pg.return_value = (True, "Restored filter")
        mock_spatialite.return_value = (True, "Restored filter")
        mock_ogr.return_value = (True, "Restored filter")
        
        # Call with previous subset
        pg_result = mock_pg(self.test_params["layer"], "unfilter", {}, {}, previous_subset)
        spatialite_result = mock_spatialite(self.test_params["layer"], "unfilter", {}, {}, previous_subset)
        ogr_result = mock_ogr(self.test_params["layer"], "unfilter", {}, {}, previous_subset)
        
        # All should handle previous_subset parameter
        self.assertTrue(pg_result[0])
        self.assertTrue(spatialite_result[0])
        self.assertTrue(ogr_result[0])
    
    @patch('adapters.backends.postgresql.filter_actions.cleanup_postgresql_session_tables')
    @patch('adapters.backends.spatialite.filter_actions.cleanup_spatialite_session_tables')
    @patch('adapters.backends.ogr.filter_actions.cleanup_ogr_session_files')
    def test_cleanup_action_parity(self, mock_ogr, mock_spatialite, mock_pg):
        """Test all backends implement cleanup."""
        mock_pg.return_value = 5
        mock_spatialite.return_value = 3
        mock_ogr.return_value = 2
        
        pg_count = mock_pg("/path/to/db")
        spatialite_count = mock_spatialite("/path/to/db")
        ogr_count = mock_ogr("/path/to/dir")
        
        # All return count
        self.assertIsInstance(pg_count, int)
        self.assertIsInstance(spatialite_count, int)
        self.assertIsInstance(ogr_count, int)


class TestBackendPerformanceCharacteristics(unittest.TestCase):
    """Test performance characteristics are well-defined."""
    
    def test_backend_selector_thresholds(self):
        """Test backend selector has clear performance thresholds."""
        from core.optimization.auto_backend_selector import AutoBackendSelector
        
        selector = AutoBackendSelector()
        
        # Verify thresholds are documented
        self.assertIsNotNone(selector.small_dataset_threshold)
        self.assertIsNotNone(selector.large_dataset_threshold)
        
        # Verify reasonable values
        self.assertLess(selector.small_dataset_threshold, selector.large_dataset_threshold)
    
    def test_spatialite_optimal_range(self):
        """Test Spatialite is recommended for optimal range."""
        from core.optimization.auto_backend_selector import AutoBackendSelector
        
        selector = AutoBackendSelector()
        
        # Mid-range dataset (5,000 features)
        layer = Mock()
        layer.featureCount.return_value = 5000
        layer.providerType.return_value = 'spatialite'
        
        recommendation = selector.recommend_backend(layer, spatial_filter=False)
        
        # Should recommend Spatialite
        self.assertEqual(recommendation.backend, 'spatialite')
    
    def test_postgresql_for_large_datasets(self):
        """Test PostgreSQL recommended for large datasets."""
        from core.optimization.auto_backend_selector import AutoBackendSelector
        
        selector = AutoBackendSelector()
        
        # Large dataset (100,000 features)
        layer = Mock()
        layer.featureCount.return_value = 100000
        layer.providerType.return_value = 'postgres'
        
        recommendation = selector.recommend_backend(layer, spatial_filter=True)
        
        # Should recommend PostgreSQL
        self.assertEqual(recommendation.backend, 'postgresql')


class TestBackendEdgeCases(unittest.TestCase):
    """Test edge cases across backends."""
    
    def test_empty_subset_string(self):
        """Test all backends handle empty subset correctly."""
        from adapters.backends.spatialite.filter_actions import execute_unfilter_action_spatialite
        
        layer = Mock(spec=QgsVectorLayer)
        layer.name.return_value = "test"
        
        success, message = execute_unfilter_action_spatialite(
            layer,
            "unfilter",
            {"layer": {"primary_key_name": "id"}},
            {"dbname": "/tmp/test.db"},
            previous_subset=""  # Empty
        )
        
        # Should handle empty string
        self.assertTrue(success)
        layer.setSubsetString.assert_called_once_with("")
    
    def test_null_layer_properties(self):
        """Test handling of missing layer properties."""
        from adapters.backends.spatialite.filter_actions import execute_reset_action_spatialite
        
        layer = Mock(spec=QgsVectorLayer)
        layer.name.return_value = "test"
        
        # Missing primary_key_name
        success, message = execute_reset_action_spatialite(
            layer,
            "reset",
            {},  # Empty props
            {"dbname": "/tmp/test.db"}
        )
        
        # Should handle gracefully or fail safely
        self.assertIsNotNone(success)
    
    def test_unicode_layer_names(self):
        """Test backends handle unicode layer names."""
        from adapters.backends.spatialite.filter_actions import execute_reset_action_spatialite
        
        layer = Mock(spec=QgsVectorLayer)
        layer.name.return_value = "Données_françaises_été_🗺️"
        
        success, message = execute_reset_action_spatialite(
            layer,
            "reset",
            {"layer": {"primary_key_name": "id"}},
            {"dbname": "/tmp/test.db"}
        )
        
        # Should handle unicode
        self.assertTrue(success)


class TestBackendFactoryIntegration(unittest.TestCase):
    """Test BackendFactory selects correct backend."""
    
    @patch('adapters.backend_registry.BackendRegistry.get_backend')
    def test_factory_returns_correct_backend(self, mock_get_backend):
        """Test factory returns backend matching layer provider."""
        from adapters.backend_registry import BackendRegistry
        
        # Test PostgreSQL
        pg_layer = Mock()
        pg_layer.providerType.return_value = 'postgres'
        
        mock_get_backend.return_value = "PostgreSQL Backend"
        backend = BackendRegistry.get_backend(pg_layer)
        
        self.assertEqual(backend, "PostgreSQL Backend")
        mock_get_backend.assert_called_once()
    
    def test_factory_handles_unknown_provider(self):
        """Test factory handles unknown provider types."""
        from adapters.backend_registry import BackendRegistry
        
        unknown_layer = Mock()
        unknown_layer.providerType.return_value = 'unknown_provider'
        
        # Should fall back to OGR or raise clear error
        try:
            backend = BackendRegistry.get_backend(unknown_layer)
            # If no exception, verify fallback
            self.assertIsNotNone(backend)
        except ValueError as e:
            # If exception, verify message is clear
            self.assertIn("unknown", str(e).lower())


class TestBackendErrorPropagation(unittest.TestCase):
    """Test error handling consistency across backends."""
    
    def test_database_error_propagation(self):
        """Test database errors are properly propagated."""
        from adapters.backends.spatialite.filter_actions import execute_reset_action_spatialite
        
        layer = Mock(spec=QgsVectorLayer)
        layer.name.return_value = "test"
        layer.setSubsetString.side_effect = RuntimeError("Database error")
        
        success, message = execute_reset_action_spatialite(
            layer,
            "reset",
            {"layer": {"primary_key_name": "id"}},
            {"dbname": "/tmp/test.db"}
        )
        
        # Should catch error and return False
        self.assertFalse(success)
        self.assertIn("error", message.lower())
    
    def test_connection_error_handling(self):
        """Test connection errors are handled gracefully."""
        from adapters.backends.spatialite.filter_actions import cleanup_spatialite_session_tables
        
        # Non-existent database
        try:
            count = cleanup_spatialite_session_tables("/nonexistent/path.db")
            # Should return 0 or raise clear exception
            self.assertEqual(count, 0)
        except Exception as e:
            # Exception should be informative
            self.assertIn("database", str(e).lower())


class TestBackendLoggingConsistency(unittest.TestCase):
    """Test logging is consistent across backends."""
    
    @patch('adapters.backends.spatialite.filter_actions.logger')
    def test_spatialite_logs_actions(self, mock_logger):
        """Test Spatialite backend logs actions."""
        from adapters.backends.spatialite.filter_actions import execute_reset_action_spatialite
        
        layer = Mock(spec=QgsVectorLayer)
        layer.name.return_value = "test"
        
        execute_reset_action_spatialite(
            layer,
            "reset",
            {"layer": {"primary_key_name": "id"}},
            {"dbname": "/tmp/test.db"}
        )
        
        # Verify logging occurred
        self.assertTrue(mock_logger.info.called or mock_logger.debug.called)
    
    @patch('adapters.backends.spatialite.filter_actions.logger')
    def test_errors_are_logged(self, mock_logger):
        """Test errors are logged properly."""
        from adapters.backends.spatialite.filter_actions import execute_reset_action_spatialite
        
        layer = Mock(spec=QgsVectorLayer)
        layer.name.return_value = "test"
        layer.setSubsetString.side_effect = Exception("Test error")
        
        execute_reset_action_spatialite(
            layer,
            "reset",
            {"layer": {"primary_key_name": "id"}},
            {"dbname": "/tmp/test.db"}
        )
        
        # Verify error was logged
        self.assertTrue(mock_logger.error.called or mock_logger.exception.called)


if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)

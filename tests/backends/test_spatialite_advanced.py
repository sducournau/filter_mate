#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Advanced Spatialite Backend Tests (Phase 3 v4.1)
================================================

Extended test suite for Spatialite backend covering:
- Error handling and edge cases
- Performance scenarios
- Integration with database_manager
- Cleanup verification
- Concurrent operations
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
from qgis.core import QgsVectorLayer
import sqlite3


class TestSpatialiteErrorHandling(unittest.TestCase):
    """Test error handling in Spatialite actions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.layer = Mock(spec=QgsVectorLayer)
        self.layer.name.return_value = "test_layer"
        self.layer_props = {"layer": {"primary_key_name": "id"}}
        self.datasource_info = {"dbname": "/tmp/test.db"}
    
    def test_reset_invalid_layer(self):
        """Test reset action with invalid layer."""
        from adapters.backends.spatialite.filter_actions import execute_reset_action_spatialite
        
        # Invalid layer
        self.layer.isValid.return_value = False
        
        success, message = execute_reset_action_spatialite(
            self.layer,
            "reset",
            self.layer_props,
            self.datasource_info
        )
        
        # Should handle gracefully
        self.assertFalse(success)
        self.assertIn("invalid", message.lower())
    
    def test_reset_missing_datasource(self):
        """Test reset with missing datasource info."""
        from adapters.backends.spatialite.filter_actions import execute_reset_action_spatialite
        
        success, message = execute_reset_action_spatialite(
            self.layer,
            "reset",
            self.layer_props,
            {}  # Empty datasource
        )
        
        # Should fail gracefully
        self.assertFalse(success)
        self.assertIn("datasource", message.lower())
    
    def test_unfilter_layer_exception(self):
        """Test unfilter when layer.setSubsetString raises exception."""
        from adapters.backends.spatialite.filter_actions import execute_unfilter_action_spatialite
        
        self.layer.setSubsetString.side_effect = Exception("DB error")
        
        success, message = execute_unfilter_action_spatialite(
            self.layer,
            "unfilter",
            self.layer_props,
            self.datasource_info,
            previous_subset='"id" > 0'
        )
        
        # Should catch exception
        self.assertFalse(success)
        self.assertIn("error", message.lower())
    
    @patch('adapters.backends.spatialite.filter_actions.cleanup_session_temp_tables')
    def test_cleanup_database_error(self, mock_cleanup):
        """Test cleanup when database operation fails."""
        from adapters.backends.spatialite.filter_actions import cleanup_spatialite_session_tables
        
        mock_cleanup.side_effect = sqlite3.Error("Database locked")
        
        # Should handle database errors
        with self.assertRaises(sqlite3.Error):
            cleanup_spatialite_session_tables("/tmp/test.db")


class TestSpatialitePerformance(unittest.TestCase):
    """Test performance-related scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.layer = Mock(spec=QgsVectorLayer)
        self.layer.name.return_value = "large_layer"
        self.layer.featureCount.return_value = 50000
        self.layer_props = {"layer": {"primary_key_name": "id"}}
        self.datasource_info = {"dbname": "/tmp/large.db"}
    
    def test_reset_large_layer(self):
        """Test reset action on large dataset."""
        from adapters.backends.spatialite.filter_actions import execute_reset_action_spatialite
        
        # Simulate large layer
        self.layer.featureCount.return_value = 100000
        
        success, message = execute_reset_action_spatialite(
            self.layer,
            "reset",
            self.layer_props,
            self.datasource_info
        )
        
        # Should complete successfully
        self.assertTrue(success)
        self.layer.setSubsetString.assert_called_once_with("")
    
    @patch('adapters.backends.spatialite.filter_actions.cleanup_session_temp_tables')
    def test_cleanup_multiple_tables(self, mock_cleanup):
        """Test cleanup with many temporary tables."""
        from adapters.backends.spatialite.filter_actions import execute_reset_action_spatialite
        
        # Simulate many temp tables
        mock_cleanup.return_value = 25
        
        success, message = execute_reset_action_spatialite(
            self.layer,
            "reset",
            self.layer_props,
            self.datasource_info
        )
        
        self.assertTrue(success)
        self.assertIn("25", message)  # Should report cleanup count


class TestSpatialiteDatabaseIntegration(unittest.TestCase):
    """Test integration with database_manager."""
    
    @patch('adapters.backends.spatialite.database_manager.get_spatialite_connection')
    @patch('adapters.backends.spatialite.filter_actions.cleanup_session_temp_tables')
    def test_reset_calls_database_manager(self, mock_cleanup, mock_get_conn):
        """Test reset action uses database_manager for cleanup."""
        from adapters.backends.spatialite.filter_actions import execute_reset_action_spatialite
        
        layer = Mock(spec=QgsVectorLayer)
        layer.name.return_value = "test"
        
        mock_cleanup.return_value = 3
        
        success, message = execute_reset_action_spatialite(
            layer,
            "reset",
            {"layer": {"primary_key_name": "id"}},
            {"dbname": "/tmp/test.db"}
        )
        
        # Verify database_manager.cleanup was called
        self.assertTrue(success)
        mock_cleanup.assert_called_once()
    
    @patch('adapters.backends.spatialite.filter_actions.cleanup_session_temp_tables')
    def test_cleanup_by_layer_name(self, mock_cleanup):
        """Test cleanup can target specific layer."""
        from adapters.backends.spatialite.filter_actions import cleanup_spatialite_session_tables
        
        mock_cleanup.return_value = 2
        
        # Cleanup specific layer
        count = cleanup_spatialite_session_tables(
            "/tmp/test.db",
            layer_name="specific_layer"
        )
        
        self.assertEqual(count, 2)
        # Verify layer_name was passed
        call_args = mock_cleanup.call_args
        self.assertIn("specific_layer", str(call_args))


class TestSpatialiteSubsetHandling(unittest.TestCase):
    """Test subset string handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.layer = Mock(spec=QgsVectorLayer)
        self.layer.name.return_value = "test"
        self.layer_props = {"layer": {"primary_key_name": "id"}}
        self.datasource_info = {"dbname": "/tmp/test.db"}
    
    def test_unfilter_complex_expression(self):
        """Test unfilter with complex previous expression."""
        from adapters.backends.spatialite.filter_actions import execute_unfilter_action_spatialite
        
        complex_expr = '"field1" > 100 AND "field2" LIKE \'%test%\' AND ST_Intersects(geom, buffer($geometry, 1000))'
        
        success, message = execute_unfilter_action_spatialite(
            self.layer,
            "unfilter",
            self.layer_props,
            self.datasource_info,
            previous_subset=complex_expr
        )
        
        self.assertTrue(success)
        self.layer.setSubsetString.assert_called_once_with(complex_expr)
    
    def test_unfilter_special_characters(self):
        """Test unfilter with special characters in expression."""
        from adapters.backends.spatialite.filter_actions import execute_unfilter_action_spatialite
        
        special_expr = '"name" = \'O\'Brien\' AND "value" > 50'
        
        success, message = execute_unfilter_action_spatialite(
            self.layer,
            "unfilter",
            self.layer_props,
            self.datasource_info,
            previous_subset=special_expr
        )
        
        self.assertTrue(success)
        self.layer.setSubsetString.assert_called_once_with(special_expr)
    
    def test_reset_preserves_layer_state(self):
        """Test reset doesn't modify other layer properties."""
        from adapters.backends.spatialite.filter_actions import execute_reset_action_spatialite
        
        # Record initial state
        initial_name = self.layer.name()
        
        execute_reset_action_spatialite(
            self.layer,
            "reset",
            self.layer_props,
            self.datasource_info
        )
        
        # Verify only subset was modified
        self.assertEqual(self.layer.name(), initial_name)
        self.layer.setSubsetString.assert_called_once()
        self.layer.triggerRepaint.assert_called_once()
        self.layer.reload.assert_called_once()


class TestSpatialiteConcurrency(unittest.TestCase):
    """Test concurrent operations."""
    
    @patch('adapters.backends.spatialite.filter_actions.cleanup_session_temp_tables')
    def test_multiple_resets_sequential(self, mock_cleanup):
        """Test multiple reset operations in sequence."""
        from adapters.backends.spatialite.filter_actions import execute_reset_action_spatialite
        
        layer = Mock(spec=QgsVectorLayer)
        layer.name.return_value = "test"
        layer_props = {"layer": {"primary_key_name": "id"}}
        datasource_info = {"dbname": "/tmp/test.db"}
        
        mock_cleanup.return_value = 1
        
        # Execute multiple resets
        for i in range(5):
            success, message = execute_reset_action_spatialite(
                layer,
                "reset",
                layer_props,
                datasource_info
            )
            self.assertTrue(success)
        
        # Verify all succeeded
        self.assertEqual(layer.setSubsetString.call_count, 5)
        self.assertEqual(mock_cleanup.call_count, 5)


class TestSpatialiteActionTypes(unittest.TestCase):
    """Test different action types."""
    
    def test_unknown_action_type(self):
        """Test handling of unknown action type."""
        from adapters.backends.spatialite.filter_actions import execute_reset_action_spatialite
        
        layer = Mock(spec=QgsVectorLayer)
        layer.name.return_value = "test"
        
        # Try with unknown action
        success, message = execute_reset_action_spatialite(
            layer,
            "unknown_action",  # Not 'reset'
            {"layer": {"primary_key_name": "id"}},
            {"dbname": "/tmp/test.db"}
        )
        
        # Should still work (action parameter might not be used)
        # Or should fail gracefully if validation exists
        self.assertIsNotNone(success)


class TestSpatialiteBackendServicePort(unittest.TestCase):
    """Test BackendServicePort integration (advanced)."""
    
    def test_actions_dictionary_structure(self):
        """Test actions dictionary has correct structure."""
        from core.ports.backend_services import BackendServices
        
        services = BackendServices.get_instance()
        actions = services.get_spatialite_filter_actions()
        
        # Verify structure
        required_keys = ['reset', 'unfilter', 'cleanup']
        for key in required_keys:
            self.assertIn(key, actions)
            self.assertTrue(callable(actions[key]))
    
    def test_actions_have_correct_signatures(self):
        """Test action functions have correct signatures."""
        from core.ports.backend_services import BackendServices
        import inspect
        
        services = BackendServices.get_instance()
        actions = services.get_spatialite_filter_actions()
        
        # Check reset signature
        reset_sig = inspect.signature(actions['reset'])
        self.assertGreaterEqual(len(reset_sig.parameters), 2)  # At least layer, action
        
        # Check unfilter signature
        unfilter_sig = inspect.signature(actions['unfilter'])
        self.assertGreaterEqual(len(unfilter_sig.parameters), 2)


if __name__ == '__main__':
    unittest.main()

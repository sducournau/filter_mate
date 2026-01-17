#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Spatialite Filter Actions (Phase 1 v4.1)
==============================================

Tests for:
- execute_reset_action_spatialite()
- execute_unfilter_action_spatialite()
- cleanup_spatialite_session_tables()
- Integration with BackendServicePort
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from qgis.core import QgsVectorLayer


class TestSpatialiteFilterActions(unittest.TestCase):
    """Test Spatialite backend filter actions."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock layer
        self.layer = Mock(spec=QgsVectorLayer)
        self.layer.name.return_value = "test_layer"
        self.layer.setSubsetString = Mock()
        self.layer.triggerRepaint = Mock()
        self.layer.reload = Mock()
        
        # Test data
        self.layer_props = {
            "layer": {
                "primary_key_name": "id"
            }
        }
        self.datasource_info = {
            "dbname": "/tmp/test.db"
        }
    
    def test_reset_action_clears_filter(self):
        """Test reset action clears subset string."""
        from adapters.backends.spatialite.filter_actions import execute_reset_action_spatialite
        
        # Execute reset
        success, message = execute_reset_action_spatialite(
            self.layer,
            "reset",
            self.layer_props,
            self.datasource_info
        )
        
        # Verify
        self.assertTrue(success)
        self.assertIn("reset successfully", message.lower())
        self.layer.setSubsetString.assert_called_once_with("")
        self.layer.triggerRepaint.assert_called_once()
        self.layer.reload.assert_called_once()
    
    @patch('adapters.backends.spatialite.filter_actions.cleanup_session_temp_tables')
    def test_reset_action_cleanup_temp_tables(self, mock_cleanup):
        """Test reset action cleans up temporary tables."""
        from adapters.backends.spatialite.filter_actions import execute_reset_action_spatialite
        
        mock_cleanup.return_value = 3  # 3 tables cleaned
        
        # Execute reset
        success, message = execute_reset_action_spatialite(
            self.layer,
            "reset",
            self.layer_props,
            self.datasource_info
        )
        
        # Verify cleanup was called
        self.assertTrue(success)
        mock_cleanup.assert_called_once_with("/tmp/test.db")
    
    def test_unfilter_action_restores_previous(self):
        """Test unfilter action restores previous subset."""
        from adapters.backends.spatialite.filter_actions import execute_unfilter_action_spatialite
        
        previous_subset = '"population" > 10000'
        
        # Execute unfilter
        success, message = execute_unfilter_action_spatialite(
            self.layer,
            "unfilter",
            self.layer_props,
            self.datasource_info,
            previous_subset=previous_subset
        )
        
        # Verify
        self.assertTrue(success)
        self.assertIn("restored", message.lower())
        self.layer.setSubsetString.assert_called_once_with(previous_subset)
        self.layer.triggerRepaint.assert_called_once()
        self.layer.reload.assert_called_once()
    
    def test_unfilter_action_no_previous_clears(self):
        """Test unfilter action without previous subset clears filter."""
        from adapters.backends.spatialite.filter_actions import execute_unfilter_action_spatialite
        
        # Execute unfilter without previous_subset
        success, message = execute_unfilter_action_spatialite(
            self.layer,
            "unfilter",
            self.layer_props,
            self.datasource_info,
            previous_subset=None
        )
        
        # Verify it clears the filter
        self.assertTrue(success)
        self.layer.setSubsetString.assert_called_once_with("")
    
    @patch('adapters.backends.spatialite.filter_actions.cleanup_session_temp_tables')
    def test_cleanup_session_tables(self, mock_cleanup):
        """Test cleanup_spatialite_session_tables wrapper."""
        from adapters.backends.spatialite.filter_actions import cleanup_spatialite_session_tables
        
        mock_cleanup.return_value = 5
        
        # Execute cleanup
        count = cleanup_spatialite_session_tables("/tmp/test.db")
        
        # Verify
        self.assertEqual(count, 5)
        mock_cleanup.assert_called_once_with("/tmp/test.db")
    
    def test_backend_service_port_integration(self):
        """Test Spatialite actions are accessible via BackendServicePort."""
        from core.ports.backend_services import BackendServices
        
        services = BackendServices.get_instance()
        actions = services.get_spatialite_filter_actions()
        
        # Verify actions are available
        self.assertIsNotNone(actions)
        self.assertIn('reset', actions)
        self.assertIn('unfilter', actions)
        self.assertIn('cleanup', actions)
        
        # Verify they're callable
        self.assertTrue(callable(actions['reset']))
        self.assertTrue(callable(actions['unfilter']))
        self.assertTrue(callable(actions['cleanup']))


class TestSpatialiteExploring ReloadProtection(unittest.TestCase):
    """Test Exploring Controller feature reload protection."""
    
    def test_exploring_features_reload_prevents_crash(self):
        """Test reload feature prevents C++ crashes."""
        # This will be implemented after exploring_controller.py changes
        # For now, just verify the pattern exists
        
        from ui.controllers.exploring_controller import ExploringController
        
        # Verify method exists
        controller = Mock(spec=ExploringController)
        self.assertTrue(hasattr(ExploringController, 'get_exploring_features'))


if __name__ == '__main__':
    unittest.main()

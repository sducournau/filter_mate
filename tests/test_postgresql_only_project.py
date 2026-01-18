# -*- coding: utf-8 -*-
"""
Test for PostgreSQL-only project detection (Option C - Hybrid approach).

Tests that BackendFactory correctly detects when a QGIS project contains
ONLY PostgreSQL layers and automatically forces PostgreSQL backend.

Author: FilterMate Team  
Date: 2026-01-18
"""

import unittest
from unittest.mock import Mock, patch, MagicMock


class TestPostgreSQLOnlyProjectDetection(unittest.TestCase):
    """Test smart initialization for PostgreSQL-only projects."""
    
    @patch('adapters.backends.factory.QgsProject')
    def test_detect_postgresql_only_project_at_startup(self, mock_qgs_project):
        """Test that BackendFactory detects PG-only project at initialization."""
        from adapters.backends.factory import BackendFactory
        
        # Mock QGIS project with 3 PostgreSQL layers
        mock_project_instance = MagicMock()
        mock_qgs_project.instance.return_value = mock_project_instance
        
        # Create 3 mock PostgreSQL layers
        pg_layer_1 = Mock()
        pg_layer_1.providerType.return_value = 'postgres'
        pg_layer_1.type.return_value = 0  # QgsMapLayer.VectorLayer
        
        pg_layer_2 = Mock()
        pg_layer_2.providerType.return_value = 'postgres'
        pg_layer_2.type.return_value = 0
        
        pg_layer_3 = Mock()
        pg_layer_3.providerType.return_value = 'postgres'
        pg_layer_3.type.return_value = 0
        
        # Mock mapLayers() to return our PostgreSQL layers
        mock_project_instance.mapLayers.return_value = {
            'layer1': pg_layer_1,
            'layer2': pg_layer_2,
            'layer3': pg_layer_3
        }
        
        # Initialize BackendFactory with PostgreSQL available
        config = {
            'small_dataset_optimization': {
                'enabled': True,
                'threshold': 5000,
                'prefer_native_for_postgresql_project': True
            }
        }
        
        with patch('adapters.backends.factory.BackendFactory._check_postgresql_available', return_value=True):
            factory = BackendFactory(config=config)
            
            # Verify that prefer_native_backend was set to True at initialization
            self.assertTrue(factory._selector._prefer_native_backend)
    
    @patch('adapters.backends.factory.QgsProject')
    def test_detect_mixed_project_at_startup(self, mock_qgs_project):
        """Test that mixed project (PG + Shapefile) doesn't force PG backend."""
        from adapters.backends.factory import BackendFactory
        
        # Mock QGIS project with mixed layers
        mock_project_instance = MagicMock()
        mock_qgs_project.instance.return_value = mock_project_instance
        
        # Create PostgreSQL layer
        pg_layer = Mock()
        pg_layer.providerType.return_value = 'postgres'
        pg_layer.type.return_value = 0
        
        # Create OGR layer (Shapefile)
        ogr_layer = Mock()
        ogr_layer.providerType.return_value = 'ogr'
        ogr_layer.type.return_value = 0
        
        # Mock mapLayers() to return mixed layers
        mock_project_instance.mapLayers.return_value = {
            'layer1': pg_layer,
            'layer2': ogr_layer
        }
        
        # Initialize BackendFactory
        config = {
            'small_dataset_optimization': {
                'enabled': True,
                'threshold': 5000,
                'prefer_native_for_postgresql_project': True
            }
        }
        
        with patch('adapters.backends.factory.BackendFactory._check_postgresql_available', return_value=True):
            factory = BackendFactory(config=config)
            
            # Verify that prefer_native_backend was NOT set (mixed project)
            self.assertFalse(factory._selector._prefer_native_backend)
    
    @patch('adapters.backends.factory.QgsProject')
    def test_dynamic_update_overrides_initial_detection(self, mock_qgs_project):
        """Test that update_project_context() can update initial detection."""
        from adapters.backends.factory import BackendFactory
        
        # Mock empty project at startup
        mock_project_instance = MagicMock()
        mock_qgs_project.instance.return_value = mock_project_instance
        mock_project_instance.mapLayers.return_value = {}
        
        config = {
            'small_dataset_optimization': {
                'enabled': True,
                'threshold': 5000,
                'prefer_native_for_postgresql_project': True
            }
        }
        
        with patch('adapters.backends.factory.BackendFactory._check_postgresql_available', return_value=True):
            factory = BackendFactory(config=config)
            
            # Initially should be False (empty project)
            self.assertFalse(factory._selector._prefer_native_backend)
            
            # Now user adds PostgreSQL layers - simulate update_project_context()
            pg_layer_1 = Mock()
            pg_layer_1.providerType.return_value = 'postgres'
            pg_layer_1.id.return_value = 'layer1'
            
            pg_layer_2 = Mock()
            pg_layer_2.providerType.return_value = 'postgres'
            pg_layer_2.id.return_value = 'layer2'
            
            # Call update_project_context with all PostgreSQL layers
            factory.update_project_context(all_layers_postgresql=True)
            
            # Now prefer_native_backend should be True
            self.assertTrue(factory._selector._prefer_native_backend)
    
    def test_is_all_layers_postgresql_helper(self):
        """Test the is_all_layers_postgresql helper method."""
        from adapters.backends.factory import BackendFactory
        
        factory = BackendFactory()
        
        # Test with all PostgreSQL layers
        pg_layer_1 = Mock()
        pg_layer_1.providerType.return_value = 'postgres'
        
        pg_layer_2 = Mock()
        pg_layer_2.providerType.return_value = 'postgres'
        
        self.assertTrue(factory.is_all_layers_postgresql([pg_layer_1, pg_layer_2]))
        
        # Test with mixed layers
        ogr_layer = Mock()
        ogr_layer.providerType.return_value = 'ogr'
        
        self.assertFalse(factory.is_all_layers_postgresql([pg_layer_1, ogr_layer]))
        
        # Test with empty list
        self.assertFalse(factory.is_all_layers_postgresql([]))
        
        # Test with None layer
        self.assertFalse(factory.is_all_layers_postgresql([None]))


if __name__ == '__main__':
    unittest.main()

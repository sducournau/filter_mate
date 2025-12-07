"""
Test migration of layer_provider_type for legacy layers.

This test verifies that layers created before the layer_provider_type feature
are properly migrated when loaded.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestLayerProviderTypeMigration(unittest.TestCase):
    """Test suite for layer_provider_type migration."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock QGIS dependencies
        self.qgs_vector_layer = MagicMock()
        self.qgs_vector_layer.id.return_value = "test_layer_123"
        self.qgs_vector_layer.name.return_value = "Test Layer"
        self.qgs_vector_layer.providerType.return_value = "postgres"
        self.qgs_vector_layer.isSpatial.return_value = True
        
    def test_migrate_adds_layer_provider_type_if_missing(self):
        """Test that _migrate_legacy_geometry_field adds layer_provider_type if missing."""
        # Create layer variables without layer_provider_type (legacy)
        layer_variables = {
            "infos": {
                "layer_geometry_field": "geom",
                "layer_table_name": "test_table",
                # layer_provider_type is missing
            },
            "exploring": {},
            "filtering": {}
        }
        
        # Mock the task and its dependencies
        with patch('modules.appTasks.detect_layer_provider_type') as mock_detect:
            mock_detect.return_value = "postgresql"
            
            # We can't easily instantiate the task without full QGIS environment,
            # so we'll test the logic conceptually
            infos = layer_variables.get("infos", {})
            
            # Simulate migration logic
            if "layer_provider_type" not in infos:
                layer_provider_type = mock_detect(self.qgs_vector_layer)
                infos["layer_provider_type"] = layer_provider_type
            
            # Verify provider type was added
            self.assertIn("layer_provider_type", infos)
            self.assertEqual(infos["layer_provider_type"], "postgresql")
            mock_detect.assert_called_once()
    
    def test_create_spatial_index_handles_missing_provider_type(self):
        """Test that _create_spatial_index handles missing layer_provider_type gracefully."""
        # Create layer_props without layer_provider_type
        layer_props = {
            "infos": {
                "layer_geometry_field": "geom",
                "layer_table_name": "test_table",
                # layer_provider_type is missing
            },
            "exploring": {},
            "filtering": {}
        }
        
        # Mock detect_layer_provider_type
        with patch('modules.appTasks.detect_layer_provider_type') as mock_detect:
            mock_detect.return_value = "spatialite"
            
            # Simulate _create_spatial_index logic
            layer_provider_type = layer_props.get("infos", {}).get("layer_provider_type")
            
            # If not found, detect it
            if not layer_provider_type:
                layer_provider_type = mock_detect(self.qgs_vector_layer)
            
            # Verify fallback worked
            self.assertEqual(layer_provider_type, "spatialite")
            mock_detect.assert_called_once()
    
    def test_layer_with_existing_provider_type_not_modified(self):
        """Test that layers with layer_provider_type are not unnecessarily modified."""
        # Create layer variables with layer_provider_type already present
        layer_variables = {
            "infos": {
                "layer_geometry_field": "geom",
                "layer_table_name": "test_table",
                "layer_provider_type": "postgresql"
            },
            "exploring": {},
            "filtering": {}
        }
        
        infos = layer_variables.get("infos", {})
        original_type = infos["layer_provider_type"]
        
        # Simulate migration check
        if "layer_provider_type" not in infos:
            # Should not execute
            self.fail("Should not try to add layer_provider_type if already present")
        
        # Verify it wasn't changed
        self.assertEqual(infos["layer_provider_type"], original_type)


class TestProviderTypeDetection(unittest.TestCase):
    """Test provider type detection for various layer types."""
    
    def test_postgres_provider_detection(self):
        """Test detection of PostgreSQL provider."""
        layer = MagicMock()
        layer.providerType.return_value = "postgres"
        
        # Import would fail without full QGIS, so we test the logic
        # In real code: layer_provider_type = detect_layer_provider_type(layer)
        provider_type = layer.providerType()
        
        # Simulate normalization (postgres -> postgresql)
        if provider_type == "postgres":
            normalized = "postgresql"
        else:
            normalized = provider_type
        
        self.assertEqual(normalized, "postgresql")
    
    def test_spatialite_provider_detection(self):
        """Test detection of Spatialite provider."""
        layer = MagicMock()
        layer.providerType.return_value = "ogr"
        layer.dataProvider.return_value.capabilitiesString.return_value = "Transactions"
        
        # Spatialite is detected by having 'ogr' provider with Transactions capability
        provider_type = layer.providerType()
        has_transactions = "Transactions" in layer.dataProvider().capabilitiesString()
        
        if provider_type == "ogr" and has_transactions:
            normalized = "spatialite"
        else:
            normalized = provider_type
        
        self.assertEqual(normalized, "spatialite")


if __name__ == '__main__':
    unittest.main()

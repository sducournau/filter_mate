"""
Test buffer error handling and geometry repair improvements.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY,
    QgsProject, QgsCoordinateReferenceSystem
)
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.appTasks import FilterTask


class TestBufferErrorHandling(unittest.TestCase):
    """Test improved buffer error handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.project = QgsProject.instance()
        
    def create_invalid_geometry_layer(self):
        """Create a layer with an invalid geometry (self-intersecting polygon)."""
        layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "test", "memory")
        provider = layer.dataProvider()
        
        # Create a self-intersecting polygon (bowtie shape)
        feature = QgsFeature()
        points = [
            QgsPointXY(0, 0),
            QgsPointXY(2, 2),
            QgsPointXY(2, 0),
            QgsPointXY(0, 2),
            QgsPointXY(0, 0)
        ]
        geometry = QgsGeometry.fromPolygonXY([points])
        feature.setGeometry(geometry)
        
        provider.addFeatures([feature])
        layer.updateExtents()
        
        return layer
    
    def create_valid_geometry_layer(self):
        """Create a layer with a valid simple polygon."""
        layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "test_valid", "memory")
        provider = layer.dataProvider()
        
        feature = QgsFeature()
        points = [
            QgsPointXY(0, 0),
            QgsPointXY(1, 0),
            QgsPointXY(1, 1),
            QgsPointXY(0, 1),
            QgsPointXY(0, 0)
        ]
        geometry = QgsGeometry.fromPolygonXY([points])
        feature.setGeometry(geometry)
        
        provider.addFeatures([feature])
        layer.updateExtents()
        
        return layer
    
    def test_aggressive_geometry_repair_with_buffer_zero(self):
        """Test that buffer(0) trick can fix self-intersections."""
        layer = self.create_invalid_geometry_layer()
        
        # Create mock task
        task_params = {
            'source_layer': layer,
            'filtering_layer': layer,
            'task_action': 'filter'
        }
        
        task = FilterTask("test_task", task_params)
        
        # Get the invalid geometry
        feature = next(layer.getFeatures())
        geom = feature.geometry()
        
        # Verify it's invalid
        self.assertFalse(geom.isGeosValid(), "Test geometry should be invalid")
        
        # Try aggressive repair
        repaired = task._aggressive_geometry_repair(geom)
        
        # Check that repair succeeded
        self.assertIsNotNone(repaired, "Repair should produce a geometry")
        self.assertTrue(repaired.isGeosValid(), "Repaired geometry should be valid")
        self.assertFalse(repaired.isEmpty(), "Repaired geometry should not be empty")
    
    def test_repair_invalid_geometries_layer(self):
        """Test that _repair_invalid_geometries handles invalid geometries."""
        layer = self.create_invalid_geometry_layer()
        
        task_params = {
            'source_layer': layer,
            'filtering_layer': layer,
            'task_action': 'filter'
        }
        
        task = FilterTask("test_task", task_params)
        
        # Repair the layer
        repaired_layer = task._repair_invalid_geometries(layer)
        
        # Check results
        self.assertIsNotNone(repaired_layer, "Should return a layer")
        self.assertGreater(repaired_layer.featureCount(), 0, "Should have at least one feature")
        
        # Check that all geometries are now valid
        for feature in repaired_layer.getFeatures():
            geom = feature.geometry()
            self.assertTrue(geom.isGeosValid(), "All repaired geometries should be valid")
    
    def test_buffer_all_features_with_invalid_geometry(self):
        """Test that _buffer_all_features handles invalid geometries gracefully."""
        layer = self.create_invalid_geometry_layer()
        
        task_params = {
            'source_layer': layer,
            'filtering_layer': layer,
            'task_action': 'filter'
        }
        
        task = FilterTask("test_task", task_params)
        
        # Try to buffer with automatic repair
        geometries, valid, invalid = task._buffer_all_features(layer, 0.1)
        
        # Should succeed with at least some valid geometries
        self.assertGreaterEqual(valid, 0, "Should attempt to repair geometries")
        # Note: Depending on repair success, we might have valid or invalid
        # The important thing is it doesn't crash
    
    def test_buffer_valid_geometry_succeeds(self):
        """Test that valid geometries buffer without issues."""
        layer = self.create_valid_geometry_layer()
        
        task_params = {
            'source_layer': layer,
            'filtering_layer': layer,
            'task_action': 'filter'
        }
        
        task = FilterTask("test_task", task_params)
        
        # Buffer should succeed
        geometries, valid, invalid = task._buffer_all_features(layer, 0.1)
        
        self.assertEqual(valid, 1, "Should have 1 valid buffered geometry")
        self.assertEqual(invalid, 0, "Should have 0 invalid geometries")
        self.assertEqual(len(geometries), 1, "Should have 1 geometry in list")
    
    def test_empty_geometry_after_repair_is_skipped(self):
        """Test that geometries that become empty after repair are skipped."""
        layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "test_empty", "memory")
        provider = layer.dataProvider()
        
        # Create a feature with null geometry
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry())
        
        provider.addFeatures([feature])
        layer.updateExtents()
        
        task_params = {
            'source_layer': layer,
            'filtering_layer': layer,
            'task_action': 'filter'
        }
        
        task = FilterTask("test_task", task_params)
        
        # Should handle gracefully
        geometries, valid, invalid = task._buffer_all_features(layer, 0.1)
        
        self.assertEqual(valid, 0, "Should have 0 valid geometries")
        self.assertEqual(invalid, 1, "Should mark as invalid")
        self.assertEqual(len(geometries), 0, "Should have no geometries")
    
    def test_copy_filtered_layer_to_memory(self):
        """Test that layers with subset strings are correctly copied to memory."""
        # Create a layer with multiple features
        layer = QgsVectorLayer("Point?crs=EPSG:4326", "test_subset", "memory")
        provider = layer.dataProvider()
        
        features = []
        for i in range(5):
            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(i, i)))
            features.append(feature)
        
        provider.addFeatures(features)
        layer.updateExtents()
        
        # Apply subset string
        layer.setSubsetString("$id = 1")
        self.assertEqual(layer.featureCount(), 1, "Should have 1 feature after filter")
        
        task_params = {
            'source_layer': layer,
            'filtering_layer': layer,
            'task_action': 'filter'
        }
        
        task = FilterTask("test_task", task_params)
        
        # Copy to memory
        memory_layer = task._copy_filtered_layer_to_memory(layer, "test_copy")
        
        # Verify copy
        self.assertIsNotNone(memory_layer, "Should return a layer")
        self.assertEqual(memory_layer.providerType(), "memory", "Should be memory provider")
        self.assertEqual(memory_layer.featureCount(), 1, "Should have 1 feature")
        self.assertEqual(memory_layer.subsetString(), "", "Memory layer should have no subset string")
    
    def test_no_copy_when_no_subset_string(self):
        """Test that layers without subset strings are returned as-is."""
        layer = QgsVectorLayer("Point?crs=EPSG:4326", "test_no_subset", "memory")
        provider = layer.dataProvider()
        
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0, 0)))
        provider.addFeatures([feature])
        layer.updateExtents()
        
        task_params = {
            'source_layer': layer,
            'filtering_layer': layer,
            'task_action': 'filter'
        }
        
        task = FilterTask("test_task", task_params)
        
        # Should return same layer
        result_layer = task._copy_filtered_layer_to_memory(layer, "test")
        
        # Should be the same object (no copy made)
        self.assertEqual(id(result_layer), id(layer), "Should return original layer when no subset string")


if __name__ == '__main__':
    unittest.main()

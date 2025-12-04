"""
Tests for geometry validation and repair functionality.
"""
import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestGeometryRepair(unittest.TestCase):
    """Test geometry repair functionality in FilterEngineTask."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock QGIS modules
        self.qgis_core_mock = MagicMock()
        self.qgis_utils_mock = MagicMock()
        sys.modules['qgis.core'] = self.qgis_core_mock
        sys.modules['qgis.utils'] = self.qgis_utils_mock
        sys.modules['qgis.PyQt.QtCore'] = MagicMock()
        sys.modules['qgis.PyQt.QtGui'] = MagicMock()
        sys.modules['qgis.PyQt.QtWidgets'] = MagicMock()
        sys.modules['qgis'] = MagicMock()
        
    def test_all_valid_geometries(self):
        """Test that valid geometries are not modified."""
        from modules.appTasks import FilterEngineTask
        
        # Create mock layer with valid geometries
        mock_layer = Mock()
        mock_layer.featureCount.return_value = 5
        
        # Create valid features
        valid_features = []
        for i in range(5):
            feature = Mock()
            geom = Mock()
            geom.isNull.return_value = False
            geom.isGeosValid.return_value = True
            feature.geometry.return_value = geom
            feature.id.return_value = i
            valid_features.append(feature)
        
        mock_layer.getFeatures.return_value = valid_features
        
        # Create task instance with proper parameters
        task = FilterEngineTask('test', 'filter', {})
        
        # Test repair - should return original layer
        result = task._repair_invalid_geometries(mock_layer)
        self.assertEqual(result, mock_layer)
        
    def test_invalid_geometries_repaired(self):
        """Test that invalid geometries are repaired."""
        from modules.appTasks import FilterEngineTask
        
        # Mock QgsVectorLayer
        mock_memory_layer = Mock()
        mock_provider = Mock()
        mock_memory_layer.dataProvider.return_value = mock_provider
        
        with patch('modules.appTasks.QgsVectorLayer', return_value=mock_memory_layer):
            # Create mock layer with invalid geometries
            mock_layer = Mock()
            mock_layer.featureCount.return_value = 3
            mock_layer.wkbType.return_value = 1  # Point
            mock_layer.crs.return_value.authid.return_value = 'EPSG:4326'
            mock_layer.fields.return_value = []
            
            # Create features: 2 invalid, 1 valid
            features = []
            
            # Invalid feature 1 (can be repaired)
            feat1 = Mock()
            geom1 = Mock()
            geom1.isNull.return_value = False
            geom1.isGeosValid.side_effect = [False, True]  # Invalid, then valid after repair
            repaired_geom1 = Mock()
            repaired_geom1.isNull.return_value = False
            repaired_geom1.isGeosValid.return_value = True
            geom1.makeValid.return_value = repaired_geom1
            feat1.geometry.return_value = geom1
            feat1.id.return_value = 1
            features.append(feat1)
            
            # Invalid feature 2 (cannot be repaired)
            feat2 = Mock()
            geom2 = Mock()
            geom2.isNull.return_value = False
            geom2.isGeosValid.side_effect = [False, False]
            repaired_geom2 = Mock()
            repaired_geom2.isNull.return_value = True
            geom2.makeValid.return_value = repaired_geom2
            feat2.geometry.return_value = geom2
            feat2.id.return_value = 2
            features.append(feat2)
            
            # Valid feature
            feat3 = Mock()
            geom3 = Mock()
            geom3.isNull.return_value = False
            geom3.isGeosValid.return_value = True
            feat3.geometry.return_value = geom3
            feat3.id.return_value = 3
            features.append(feat3)
            
            mock_layer.getFeatures.return_value = features
            
            # Create task instance with proper parameters
            task = FilterEngineTask('test', 'filter', {})
            
            # Test repair
            result = task._repair_invalid_geometries(mock_layer)
            
            # Should return new layer (not original)
            self.assertNotEqual(result, mock_layer)
            self.assertEqual(result, mock_memory_layer)
            
            # Should have added 2 features (1 repaired + 1 valid, excluding unrepairable)
            self.assertEqual(mock_provider.addFeatures.call_count, 1)
            added_features = mock_provider.addFeatures.call_args[0][0]
            self.assertEqual(len(added_features), 2)
            
    def test_buffer_with_geometry_repair(self):
        """Test that buffer operation repairs geometries automatically."""
        from modules.appTasks import FilterEngineTask
        
        # Create mock layer
        mock_layer = Mock()
        mock_layer.featureCount.return_value = 2
        
        # Create invalid features
        invalid_features = []
        for i in range(2):
            feature = Mock()
            geom = Mock()
            geom.isNull.return_value = False
            geom.isGeosValid.return_value = False
            feature.geometry.return_value = geom
            feature.id.return_value = i
            invalid_features.append(feature)
        
        mock_layer.getFeatures.return_value = invalid_features
        
        # Create task instance with proper parameters
        task = FilterEngineTask('test', 'filter', {})
        
        # Mock _repair_invalid_geometries to return a fixed layer
        fixed_layer = Mock()
        task._repair_invalid_geometries = Mock(return_value=fixed_layer)
        
        # Mock _apply_qgis_buffer to succeed with fixed layer
        buffered_layer = Mock()
        task._apply_qgis_buffer = Mock(return_value=buffered_layer)
        
        # Test buffer with fallback
        result = task._apply_buffer_with_fallback(mock_layer, 10.0)
        
        # Should have called repair first
        task._repair_invalid_geometries.assert_called_once_with(mock_layer)
        
        # Should have tried buffer with repaired layer
        task._apply_qgis_buffer.assert_called_once_with(fixed_layer, 10.0)
        
        # Should return buffered result
        self.assertEqual(result, buffered_layer)


if __name__ == '__main__':
    unittest.main()

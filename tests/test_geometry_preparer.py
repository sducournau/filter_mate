"""
Unit tests for geometry_preparer module.

v4.7 E6-S3 Code Review Fix: Basic test coverage for extracted geometry preparation logic.
"""
import unittest
from unittest.mock import Mock, MagicMock, patch


class TestGeometryPreparer(unittest.TestCase):
    """Test geometry preparation for multi-backend filtering."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_layer = Mock()
        self.mock_layer.crs.return_value.authid.return_value = "EPSG:4326"
        self.mock_layer.featureCount.return_value = 100
        
        self.task_params = {
            'source_layer_id': 'test_layer',
            'filter_geometry_layer_id': 'filter_layer',
            'source_provider_type': 'postgresql'
        }
        
        self.mock_logger = Mock()
    
    def test_prepare_geometries_postgresql_success(self):
        """Test PostgreSQL geometry preparation with successful callback."""
        from core.services.geometry_preparer import prepare_geometries_by_provider
        
        # Mock callbacks
        postgresql_callback = Mock(return_value=True)
        spatialite_callback = Mock()
        ogr_callback = Mock()
        
        result = prepare_geometries_by_provider(
            provider_list=['postgresql'],
            task_parameters=self.task_params,
            source_layer=self.mock_layer,
            param_source_provider_type='postgresql',
            param_buffer_expression=None,
            layers_dict=None,
            prepare_postgresql_geom_callback=postgresql_callback,
            prepare_spatialite_geom_callback=spatialite_callback,
            prepare_ogr_geom_callback=ogr_callback,
            logger=self.mock_logger,
            postgresql_available=True
        )
        
        # Assertions
        self.assertTrue(result['success'])
        postgresql_callback.assert_called_once()
        spatialite_callback.assert_not_called()
        ogr_callback.assert_not_called()
    
    def test_prepare_geometries_spatialite_success(self):
        """Test Spatialite geometry preparation with successful callback."""
        from core.services.geometry_preparer import prepare_geometries_by_provider
        
        # Mock callbacks
        postgresql_callback = Mock()
        spatialite_callback = Mock(return_value=True)
        ogr_callback = Mock()
        
        result = prepare_geometries_by_provider(
            provider_list=['spatialite'],
            task_parameters=self.task_params,
            source_layer=self.mock_layer,
            param_source_provider_type='spatialite',
            param_buffer_expression=None,
            layers_dict=None,
            prepare_postgresql_geom_callback=postgresql_callback,
            prepare_spatialite_geom_callback=spatialite_callback,
            prepare_ogr_geom_callback=ogr_callback,
            logger=self.mock_logger,
            postgresql_available=False
        )
        
        # Assertions
        self.assertTrue(result['success'])
        postgresql_callback.assert_not_called()
        spatialite_callback.assert_called_once()
        ogr_callback.assert_not_called()
    
    def test_prepare_geometries_ogr_fallback(self):
        """Test OGR fallback when PostgreSQL unavailable."""
        from core.services.geometry_preparer import prepare_geometries_by_provider
        
        # Mock callbacks
        postgresql_callback = Mock()
        spatialite_callback = Mock()
        ogr_callback = Mock(return_value=True)
        
        result = prepare_geometries_by_provider(
            provider_list=['ogr'],
            task_parameters=self.task_params,
            source_layer=self.mock_layer,
            param_source_provider_type='ogr',
            param_buffer_expression=None,
            layers_dict=None,
            prepare_postgresql_geom_callback=postgresql_callback,
            prepare_spatialite_geom_callback=spatialite_callback,
            prepare_ogr_geom_callback=ogr_callback,
            logger=self.mock_logger,
            postgresql_available=False
        )
        
        # Assertions
        self.assertTrue(result['success'])
        postgresql_callback.assert_not_called()
        spatialite_callback.assert_not_called()
        ogr_callback.assert_called_once()
    
    def test_prepare_geometries_callback_failure(self):
        """Test handling of callback failures."""
        from core.services.geometry_preparer import prepare_geometries_by_provider
        
        # Mock failing callback
        postgresql_callback = Mock(return_value=False)
        spatialite_callback = Mock()
        ogr_callback = Mock()
        
        result = prepare_geometries_by_provider(
            provider_list=['postgresql'],
            task_parameters=self.task_params,
            source_layer=self.mock_layer,
            param_source_provider_type='postgresql',
            param_buffer_expression=None,
            layers_dict=None,
            prepare_postgresql_geom_callback=postgresql_callback,
            prepare_spatialite_geom_callback=spatialite_callback,
            prepare_ogr_geom_callback=ogr_callback,
            logger=self.mock_logger,
            postgresql_available=True
        )
        
        # Should still call the callback
        postgresql_callback.assert_called_once()
        # Result depends on implementation - update based on actual behavior
    
    def test_prepare_geometries_return_structure(self):
        """Test that result dict has expected keys."""
        from core.services.geometry_preparer import prepare_geometries_by_provider
        
        # Mock callbacks
        postgresql_callback = Mock(return_value=True)
        spatialite_callback = Mock()
        ogr_callback = Mock()
        
        result = prepare_geometries_by_provider(
            provider_list=['postgresql'],
            task_parameters=self.task_params,
            source_layer=self.mock_layer,
            param_source_provider_type='postgresql',
            param_buffer_expression=None,
            layers_dict=None,
            prepare_postgresql_geom_callback=postgresql_callback,
            prepare_spatialite_geom_callback=spatialite_callback,
            prepare_ogr_geom_callback=ogr_callback,
            logger=self.mock_logger,
            postgresql_available=True
        )
        
        # Verify expected keys in result dict
        self.assertIn('success', result)
        self.assertIn('postgresql_source_geom', result)
        self.assertIn('spatialite_source_geom', result)
        self.assertIn('ogr_source_geom', result)
        self.assertIsInstance(result['success'], bool)


if __name__ == '__main__':
    unittest.main()

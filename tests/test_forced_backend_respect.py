"""
Tests for forced backend respect functionality.

These tests verify that when a user explicitly forces a backend choice,
the system respects that choice even if the backend may not be optimal
for the layer type.

Author: FilterMate
Date: 2025-12-17
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from qgis.core import QgsVectorLayer


class TestForcedBackendRespect(unittest.TestCase):
    """Test that forced backends are strictly respected."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock layer
        self.mock_layer = Mock(spec=QgsVectorLayer)
        self.mock_layer.id.return_value = "test_layer_id"
        self.mock_layer.name.return_value = "Test Layer"
        
        # Base task parameters
        self.base_task_params = {
            'options': {},
            'db_file_path': '/tmp/test.db'
        }
    
    @patch('modules.backends.factory.POSTGRESQL_AVAILABLE', True)
    @patch('modules.backends.factory.PostgreSQLGeometricFilter')
    def test_forced_postgresql_backend_is_used(self, mock_pg_class):
        """Test that forced PostgreSQL backend is used even if supports_layer returns False."""
        from modules.backends.factory import BackendFactory
        
        # Setup mock backend
        mock_backend = Mock()
        mock_backend.supports_layer.return_value = False  # Simulate unsupported
        mock_pg_class.return_value = mock_backend
        
        # Force PostgreSQL backend
        task_params = self.base_task_params.copy()
        task_params['forced_backends'] = {
            'test_layer_id': 'postgresql'
        }
        
        # Get backend
        backend = BackendFactory.get_backend(
            'ogr',  # Layer is OGR but PostgreSQL is forced
            self.mock_layer,
            task_params
        )
        
        # Verify PostgreSQL backend was created and returned
        mock_pg_class.assert_called_once_with(task_params)
        self.assertEqual(backend, mock_backend)
        # Backend should still be returned even though supports_layer is False
    
    @patch('modules.backends.factory.SpatialiteGeometricFilter')
    def test_forced_spatialite_backend_is_used(self, mock_spatialite_class):
        """Test that forced Spatialite backend is used even if supports_layer returns False."""
        from modules.backends.factory import BackendFactory
        
        # Setup mock backend
        mock_backend = Mock()
        mock_backend.supports_layer.return_value = False  # Simulate unsupported
        mock_spatialite_class.return_value = mock_backend
        
        # Force Spatialite backend
        task_params = self.base_task_params.copy()
        task_params['forced_backends'] = {
            'test_layer_id': 'spatialite'
        }
        
        # Get backend (simulating PostgreSQL layer)
        backend = BackendFactory.get_backend(
            'postgresql',  # Layer is PostgreSQL but Spatialite is forced
            self.mock_layer,
            task_params
        )
        
        # Verify Spatialite backend was created and returned
        mock_spatialite_class.assert_called_once_with(task_params)
        self.assertEqual(backend, mock_backend)
    
    @patch('modules.backends.factory.OGRGeometricFilter')
    def test_forced_ogr_backend_is_used(self, mock_ogr_class):
        """Test that forced OGR backend is always used."""
        from modules.backends.factory import BackendFactory
        
        # Setup mock backend
        mock_backend = Mock()
        mock_ogr_class.return_value = mock_backend
        
        # Force OGR backend
        task_params = self.base_task_params.copy()
        task_params['forced_backends'] = {
            'test_layer_id': 'ogr'
        }
        
        # Get backend
        backend = BackendFactory.get_backend(
            'postgresql',  # Layer is PostgreSQL but OGR is forced
            self.mock_layer,
            task_params
        )
        
        # Verify OGR backend was created and returned
        mock_ogr_class.assert_called_once_with(task_params)
        self.assertEqual(backend, mock_backend)
    
    @patch('modules.backends.factory.POSTGRESQL_AVAILABLE', False)
    @patch('modules.backends.factory.PostgreSQLGeometricFilter')
    def test_forced_postgresql_without_psycopg2_still_creates_backend(self, mock_pg_class):
        """Test that PostgreSQL backend is created even without psycopg2."""
        from modules.backends.factory import BackendFactory
        
        # Setup mock backend
        mock_backend = Mock()
        mock_pg_class.return_value = mock_backend
        
        # Force PostgreSQL backend
        task_params = self.base_task_params.copy()
        task_params['forced_backends'] = {
            'test_layer_id': 'postgresql'
        }
        
        # Get backend
        backend = BackendFactory.get_backend(
            'ogr',
            self.mock_layer,
            task_params
        )
        
        # Verify PostgreSQL backend was still created
        mock_pg_class.assert_called_once_with(task_params)
        self.assertEqual(backend, mock_backend)
    
    @patch('modules.backends.factory.PostgreSQLGeometricFilter')
    @patch('modules.backends.factory.POSTGRESQL_AVAILABLE', True)
    def test_auto_selection_when_no_forced_backend(self, mock_pg_class):
        """Test that auto-selection still works when no backend is forced."""
        from modules.backends.factory import BackendFactory
        
        # Setup mock backend
        mock_backend = Mock()
        mock_backend.supports_layer.return_value = True
        mock_pg_class.return_value = mock_backend
        
        # NO forced backend
        task_params = self.base_task_params.copy()
        # Don't include forced_backends at all
        
        # Get backend for PostgreSQL layer
        backend = BackendFactory.get_backend(
            'postgresql',
            self.mock_layer,
            task_params
        )
        
        # Verify auto-selection worked
        mock_pg_class.assert_called_once_with(task_params)
        self.assertEqual(backend, mock_backend)
    
    @patch('modules.backends.factory.OGRGeometricFilter')
    def test_unknown_forced_backend_falls_back_to_auto_selection(self, mock_ogr_class):
        """Test that unknown forced backend name falls back to auto-selection."""
        from modules.backends.factory import BackendFactory
        
        # Setup mock backend
        mock_backend = Mock()
        mock_ogr_class.return_value = mock_backend
        
        # Force unknown backend
        task_params = self.base_task_params.copy()
        task_params['forced_backends'] = {
            'test_layer_id': 'unknown_backend'  # Invalid backend name
        }
        
        # Get backend for OGR layer
        backend = BackendFactory.get_backend(
            'ogr',
            self.mock_layer,
            task_params
        )
        
        # Should fall back to OGR for OGR layer
        mock_ogr_class.assert_called_once_with(task_params)
        self.assertEqual(backend, mock_backend)


if __name__ == '__main__':
    unittest.main()

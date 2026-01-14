"""
Tests unitaires pour BackendConnector

Coverage:
- Détection du provider type
- Connexion PostgreSQL
- Connexion Spatialite
- Nettoyage des ressources
- Intégration avec BackendRegistry
- Gestion du context manager
- Gestion des erreurs

Créé: Janvier 2026 (Phase E13)
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sqlite3

# Import the class to test
from core.tasks.connectors.backend_connector import BackendConnector


class TestBackendConnectorInit(unittest.TestCase):
    """Test initialization and provider detection."""
    
    def test_init_without_layer(self):
        """Should initialize without layer."""
        connector = BackendConnector()
        
        self.assertIsNone(connector.layer)
        self.assertIsNone(connector.backend_registry)
        self.assertIsNone(connector.provider_type)
    
    def test_init_with_layer(self):
        """Should detect provider type from layer."""
        mock_layer = Mock()
        mock_layer.providerType.return_value = 'postgres'
        
        with patch('core.tasks.connectors.backend_connector.detect_layer_provider_type', return_value='postgresql'):
            connector = BackendConnector(layer=mock_layer)
        
        self.assertEqual(connector.layer, mock_layer)
        self.assertEqual(connector.provider_type, 'postgresql')
    
    def test_init_with_backend_registry(self):
        """Should store backend registry reference."""
        mock_registry = Mock()
        
        connector = BackendConnector(backend_registry=mock_registry)
        
        self.assertEqual(connector.backend_registry, mock_registry)


class TestBackendConnectorRegistryIntegration(unittest.TestCase):
    """Test BackendRegistry integration."""
    
    def test_get_backend_executor_with_registry(self):
        """Should use registry to get executor."""
        mock_registry = Mock()
        mock_executor = Mock()
        mock_registry.get_executor.return_value = mock_executor
        
        connector = BackendConnector(backend_registry=mock_registry)
        
        layer_info = {'layer_provider_type': 'postgresql'}
        result = connector.get_backend_executor(layer_info)
        
        self.assertEqual(result, mock_executor)
        mock_registry.get_executor.assert_called_once_with(layer_info)
    
    def test_get_backend_executor_without_registry(self):
        """Should return None without registry."""
        connector = BackendConnector()
        
        layer_info = {'layer_provider_type': 'postgresql'}
        result = connector.get_backend_executor(layer_info)
        
        self.assertIsNone(result)
    
    def test_get_backend_executor_registry_error(self):
        """Should return None if registry fails."""
        mock_registry = Mock()
        mock_registry.get_executor.side_effect = Exception("Registry error")
        
        connector = BackendConnector(backend_registry=mock_registry)
        
        layer_info = {'layer_provider_type': 'postgresql'}
        result = connector.get_backend_executor(layer_info)
        
        # Should fallback to None
        self.assertIsNone(result)
    
    def test_has_backend_registry_true(self):
        """Should return True when registry available."""
        mock_registry = Mock()
        connector = BackendConnector(backend_registry=mock_registry)
        
        self.assertTrue(connector.has_backend_registry())
    
    def test_has_backend_registry_false(self):
        """Should return False without registry."""
        connector = BackendConnector()
        
        self.assertFalse(connector.has_backend_registry())
    
    def test_is_postgresql_available_from_registry(self):
        """Should check PostgreSQL availability from registry."""
        mock_registry = Mock()
        mock_registry.postgresql_available = True
        
        connector = BackendConnector(backend_registry=mock_registry)
        
        self.assertTrue(connector.is_postgresql_available())
    
    @patch('core.tasks.connectors.backend_connector.POSTGRESQL_AVAILABLE', True)
    def test_is_postgresql_available_fallback(self):
        """Should fallback to global constant."""
        connector = BackendConnector()
        
        self.assertTrue(connector.is_postgresql_available())


class TestBackendConnectorPostgreSQL(unittest.TestCase):
    """Test PostgreSQL connection management."""
    
    @patch('core.tasks.connectors.backend_connector.POSTGRESQL_AVAILABLE', False)
    def test_get_postgresql_connection_unavailable(self):
        """Should return None when PostgreSQL unavailable."""
        connector = BackendConnector()
        
        result = connector.get_postgresql_connection()
        
        self.assertIsNone(result)
    
    @patch('core.tasks.connectors.backend_connector.POSTGRESQL_AVAILABLE', True)
    def test_get_postgresql_connection_no_layer(self):
        """Should return None without layer."""
        connector = BackendConnector()
        
        result = connector.get_postgresql_connection()
        
        self.assertIsNone(result)
    
    @patch('core.tasks.connectors.backend_connector.POSTGRESQL_AVAILABLE', True)
    def test_get_postgresql_connection_wrong_provider(self):
        """Should return None for non-PostgreSQL layer."""
        mock_layer = Mock()
        
        with patch('core.tasks.connectors.backend_connector.detect_layer_provider_type', return_value='spatialite'):
            connector = BackendConnector(layer=mock_layer)
        
        result = connector.get_postgresql_connection()
        
        self.assertIsNone(result)
    
    @patch('core.tasks.connectors.backend_connector.POSTGRESQL_AVAILABLE', True)
    @patch('core.tasks.connectors.backend_connector.get_datasource_connexion_from_layer')
    def test_get_postgresql_connection_success(self, mock_get_conn):
        """Should get PostgreSQL connection from layer."""
        mock_layer = Mock()
        mock_conn = Mock()
        mock_get_conn.return_value = (mock_conn, "connection_uri")
        
        with patch('core.tasks.connectors.backend_connector.detect_layer_provider_type', return_value='postgresql'):
            connector = BackendConnector(layer=mock_layer)
        
        result = connector.get_postgresql_connection()
        
        self.assertEqual(result, mock_conn)
        mock_get_conn.assert_called_once_with(mock_layer)
    
    @patch('core.tasks.connectors.backend_connector.POSTGRESQL_AVAILABLE', True)
    @patch('core.tasks.connectors.backend_connector.get_datasource_connexion_from_layer')
    def test_get_postgresql_connection_reuse_cached(self, mock_get_conn):
        """Should reuse valid cached connection."""
        mock_layer = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = (mock_conn, "connection_uri")
        
        with patch('core.tasks.connectors.backend_connector.detect_layer_provider_type', return_value='postgresql'):
            connector = BackendConnector(layer=mock_layer)
        
        # First call - creates connection
        result1 = connector.get_postgresql_connection()
        
        # Second call - should reuse
        result2 = connector.get_postgresql_connection()
        
        self.assertEqual(result1, result2)
        # Should only call get_datasource_connexion_from_layer once
        self.assertEqual(mock_get_conn.call_count, 1)
    
    @patch('core.tasks.connectors.backend_connector.POSTGRESQL_AVAILABLE', True)
    @patch('core.tasks.connectors.backend_connector.get_datasource_connexion_from_layer')
    def test_get_postgresql_connection_recreate_invalid(self, mock_get_conn):
        """Should recreate connection if cached is invalid."""
        mock_layer = Mock()
        mock_conn1 = Mock()
        mock_conn1.cursor.side_effect = Exception("Connection lost")
        
        mock_conn2 = Mock()
        mock_get_conn.side_effect = [(mock_conn1, "uri1"), (mock_conn2, "uri2")]
        
        with patch('core.tasks.connectors.backend_connector.detect_layer_provider_type', return_value='postgresql'):
            connector = BackendConnector(layer=mock_layer)
        
        # First call - creates connection
        result1 = connector.get_postgresql_connection()
        
        # Second call - cached is invalid, recreates
        result2 = connector.get_postgresql_connection()
        
        self.assertEqual(result1, mock_conn1)
        self.assertEqual(result2, mock_conn2)
        self.assertEqual(mock_get_conn.call_count, 2)


class TestBackendConnectorSpatialite(unittest.TestCase):
    """Test Spatialite connection management."""
    
    @patch('core.tasks.connectors.backend_connector.safe_spatialite_connect')
    def test_get_spatialite_connection_with_path(self, mock_safe_connect):
        """Should connect to Spatialite with provided path."""
        mock_conn = Mock()
        mock_safe_connect.return_value = mock_conn
        
        connector = BackendConnector()
        
        result = connector.get_spatialite_connection(db_path="/path/to/db.sqlite")
        
        self.assertEqual(result, mock_conn)
        mock_safe_connect.assert_called_once_with("/path/to/db.sqlite")
    
    @patch('core.tasks.connectors.backend_connector.safe_spatialite_connect')
    def test_get_spatialite_connection_from_layer(self, mock_safe_connect):
        """Should extract path from layer data source."""
        mock_layer = Mock()
        mock_provider = Mock()
        mock_provider.dataSourceUri.return_value = "/path/to/layer.sqlite|layername=test"
        mock_layer.dataProvider.return_value = mock_provider
        
        mock_conn = Mock()
        mock_safe_connect.return_value = mock_conn
        
        connector = BackendConnector(layer=mock_layer)
        
        result = connector.get_spatialite_connection()
        
        self.assertEqual(result, mock_conn)
        mock_safe_connect.assert_called_once_with("/path/to/layer.sqlite")
    
    def test_get_spatialite_connection_no_path_no_layer(self):
        """Should return None without path or layer."""
        connector = BackendConnector()
        
        result = connector.get_spatialite_connection()
        
        self.assertIsNone(result)
    
    @patch('core.tasks.connectors.backend_connector.safe_spatialite_connect')
    def test_get_spatialite_connection_error(self, mock_safe_connect):
        """Should raise exception on connection error."""
        mock_safe_connect.side_effect = Exception("Spatialite error")
        
        connector = BackendConnector()
        
        with self.assertRaises(Exception):
            connector.get_spatialite_connection(db_path="/invalid/path.sqlite")


class TestBackendConnectorCleanup(unittest.TestCase):
    """Test resource cleanup."""
    
    @patch('core.tasks.connectors.backend_connector.POSTGRESQL_AVAILABLE', True)
    @patch('core.tasks.connectors.backend_connector.get_datasource_connexion_from_layer')
    def test_cleanup_postgresql_connection(self, mock_get_conn):
        """Should close PostgreSQL connection on cleanup."""
        mock_layer = Mock()
        mock_conn = Mock()
        mock_get_conn.return_value = (mock_conn, "uri")
        
        with patch('core.tasks.connectors.backend_connector.detect_layer_provider_type', return_value='postgresql'):
            connector = BackendConnector(layer=mock_layer)
        
        # Get connection
        connector.get_postgresql_connection()
        
        # Cleanup
        connector.cleanup_backend_resources()
        
        # Should close connection
        mock_conn.close.assert_called_once()
    
    @patch('core.tasks.connectors.backend_connector.safe_spatialite_connect')
    def test_cleanup_spatialite_connection(self, mock_safe_connect):
        """Should close Spatialite connection on cleanup."""
        mock_conn = Mock()
        mock_safe_connect.return_value = mock_conn
        
        connector = BackendConnector()
        
        # Get connection
        connector.get_spatialite_connection(db_path="/path/to/db.sqlite")
        
        # Cleanup
        connector.cleanup_backend_resources()
        
        # Should close connection
        mock_conn.close.assert_called_once()
    
    def test_cleanup_with_backend_registry(self):
        """Should delegate cleanup to registry."""
        mock_registry = Mock()
        
        connector = BackendConnector(backend_registry=mock_registry)
        
        connector.cleanup_backend_resources()
        
        mock_registry.cleanup_all.assert_called_once()
    
    @patch('core.tasks.connectors.backend_connector.POSTGRESQL_AVAILABLE', True)
    @patch('core.tasks.connectors.backend_connector.get_datasource_connexion_from_layer')
    def test_cleanup_handles_close_error(self, mock_get_conn):
        """Should handle errors during connection close."""
        mock_layer = Mock()
        mock_conn = Mock()
        mock_conn.close.side_effect = Exception("Close error")
        mock_get_conn.return_value = (mock_conn, "uri")
        
        with patch('core.tasks.connectors.backend_connector.detect_layer_provider_type', return_value='postgresql'):
            connector = BackendConnector(layer=mock_layer)
        
        # Get connection
        connector.get_postgresql_connection()
        
        # Cleanup - should not raise
        connector.cleanup_backend_resources()


class TestBackendConnectorProviderDetection(unittest.TestCase):
    """Test provider type detection."""
    
    def test_detect_provider_type_from_layer(self):
        """Should detect provider from provided layer."""
        mock_layer = Mock()
        
        with patch('core.tasks.connectors.backend_connector.detect_layer_provider_type', return_value='postgresql') as mock_detect:
            connector = BackendConnector()
            
            result = connector.detect_provider_type(layer=mock_layer)
        
        self.assertEqual(result, 'postgresql')
        mock_detect.assert_called_once_with(mock_layer)
    
    def test_detect_provider_type_from_self_layer(self):
        """Should detect provider from self.layer."""
        mock_layer = Mock()
        
        with patch('core.tasks.connectors.backend_connector.detect_layer_provider_type', return_value='spatialite') as mock_detect:
            connector = BackendConnector(layer=mock_layer)
            
            result = connector.detect_provider_type()
        
        self.assertEqual(result, 'spatialite')
    
    def test_detect_provider_type_no_layer(self):
        """Should return 'unknown' without layer."""
        connector = BackendConnector()
        
        result = connector.detect_provider_type()
        
        self.assertEqual(result, 'unknown')


class TestBackendConnectorContextManager(unittest.TestCase):
    """Test context manager protocol."""
    
    def test_context_manager_enter(self):
        """Should return self on enter."""
        connector = BackendConnector()
        
        with connector as ctx:
            self.assertEqual(ctx, connector)
    
    @patch('core.tasks.connectors.backend_connector.POSTGRESQL_AVAILABLE', True)
    @patch('core.tasks.connectors.backend_connector.get_datasource_connexion_from_layer')
    def test_context_manager_exit_cleanup(self, mock_get_conn):
        """Should cleanup on exit."""
        mock_layer = Mock()
        mock_conn = Mock()
        mock_get_conn.return_value = (mock_conn, "uri")
        
        with patch('core.tasks.connectors.backend_connector.detect_layer_provider_type', return_value='postgresql'):
            connector = BackendConnector(layer=mock_layer)
        
        with connector:
            connector.get_postgresql_connection()
        
        # Should close connection on exit
        mock_conn.close.assert_called_once()
    
    @patch('core.tasks.connectors.backend_connector.POSTGRESQL_AVAILABLE', True)
    @patch('core.tasks.connectors.backend_connector.get_datasource_connexion_from_layer')
    def test_context_manager_exit_with_exception(self, mock_get_conn):
        """Should cleanup even with exception."""
        mock_layer = Mock()
        mock_conn = Mock()
        mock_get_conn.return_value = (mock_conn, "uri")
        
        with patch('core.tasks.connectors.backend_connector.detect_layer_provider_type', return_value='postgresql'):
            connector = BackendConnector(layer=mock_layer)
        
        try:
            with connector:
                connector.get_postgresql_connection()
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # Should still cleanup
        mock_conn.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()

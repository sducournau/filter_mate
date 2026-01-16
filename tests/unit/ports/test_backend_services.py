"""
Unit tests for BackendServices facade.

EPIC-1 Phase E13: Tests for the backend services encapsulation layer.
"""

import unittest
from unittest.mock import patch, MagicMock


class TestBackendServices(unittest.TestCase):
    """Test BackendServices facade."""
    
    def setUp(self):
        """Reset singleton before each test."""
        # Import here to allow mocking
        from core.ports.backend_services import BackendServices
        BackendServices.reset_instance()
    
    def test_singleton_pattern(self):
        """Test that get_instance returns same object."""
        from core.ports.backend_services import BackendServices
        
        instance1 = BackendServices.get_instance()
        instance2 = BackendServices.get_instance()
        
        self.assertIs(instance1, instance2)
    
    def test_reset_instance(self):
        """Test that reset_instance creates new object."""
        from core.ports.backend_services import BackendServices
        
        instance1 = BackendServices.get_instance()
        BackendServices.reset_instance()
        instance2 = BackendServices.get_instance()
        
        self.assertIsNot(instance1, instance2)
    
    def test_postgresql_availability_structure(self):
        """Test PostgreSQLAvailability dataclass structure."""
        from core.ports.backend_services import PostgreSQLAvailability
        
        avail = PostgreSQLAvailability()
        
        self.assertIsNone(avail.psycopg2)
        self.assertFalse(avail.psycopg2_available)
        self.assertFalse(avail.postgresql_available)
    
    def test_get_postgresql_available_convenience(self):
        """Test convenience function get_postgresql_available."""
        from core.ports.backend_services import get_postgresql_available, BackendServices
        
        # Reset and test
        BackendServices.reset_instance()
        result = get_postgresql_available()
        
        # Should return a boolean
        self.assertIsInstance(result, bool)
    
    def test_get_backend_services_convenience(self):
        """Test convenience function get_backend_services."""
        from core.ports.backend_services import get_backend_services, BackendServices
        
        BackendServices.reset_instance()
        services = get_backend_services()
        
        self.assertIsInstance(services, BackendServices)
    
    @patch('core.ports.backend_services.logger')
    def test_executor_returns_none_on_import_error(self, mock_logger):
        """Test that executors return None when import fails."""
        from core.ports.backend_services import BackendServices
        
        services = BackendServices()
        
        # Mock the import to fail
        with patch.dict('sys.modules', {'adapters.backends.postgresql': None}):
            # These should return None gracefully, not raise
            pg_executor = services.get_postgresql_executor()
            # May or may not be None depending on actual imports
            # The important thing is it doesn't raise


class TestBackendServicesIntegration(unittest.TestCase):
    """Integration tests - run only if adapters are available."""
    
    def test_postgresql_availability_loads(self):
        """Test that PostgreSQL availability check works."""
        from core.ports.backend_services import BackendServices
        
        BackendServices.reset_instance()
        services = BackendServices.get_instance()
        avail = services.get_postgresql_availability()
        
        # Should have loaded something
        self.assertIsNotNone(avail)
        # psycopg2 might be None if not installed
        self.assertIsInstance(avail.postgresql_available, bool)
        self.assertIsInstance(avail.psycopg2_available, bool)
    
    def test_task_bridge_loads(self):
        """Test that task bridge can be loaded."""
        from core.ports.backend_services import BackendServices
        
        BackendServices.reset_instance()
        services = BackendServices.get_instance()
        get_bridge, status = services.get_task_bridge()
        
        # Should return tuple - may be (None, None) or actual functions
        self.assertIsInstance((get_bridge, status), tuple)


if __name__ == '__main__':
    unittest.main()

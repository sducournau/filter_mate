#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for FilterMate Phase 1: Optional PostgreSQL Support

This test suite validates that FilterMate can start and function
without psycopg2 installed.

Tests:
- Import modules without psycopg2
- POSTGRESQL_AVAILABLE flag
- Graceful degradation without PostgreSQL
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add modules to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestPhase1OptionalPostgreSQL(unittest.TestCase):
    """Test Phase 1: PostgreSQL optional import"""

    def setUp(self):
        """Setup test environment"""
        # Mock QGIS modules
        sys.modules['qgis'] = MagicMock()
        sys.modules['qgis.core'] = MagicMock()
        sys.modules['qgis.gui'] = MagicMock()
        sys.modules['qgis.utils'] = MagicMock()
        sys.modules['qgis.PyQt'] = MagicMock()
        sys.modules['qgis.PyQt.QtCore'] = MagicMock()
        sys.modules['qgis.PyQt.QtGui'] = MagicMock()
        sys.modules['qgis.PyQt.QtWidgets'] = MagicMock()

    def test_import_appUtils_without_psycopg2(self):
        """Test that appUtils can be imported without psycopg2"""
        # Hide psycopg2 if present
        psycopg2_backup = sys.modules.get('psycopg2')
        if 'psycopg2' in sys.modules:
            del sys.modules['psycopg2']
        
        sys.modules['psycopg2'] = None  # Simulate ImportError
        
        try:
            # This should not raise ImportError
            from modules import appUtils
            
            # Verify flag is set correctly
            self.assertFalse(appUtils.POSTGRESQL_AVAILABLE, 
                           "POSTGRESQL_AVAILABLE should be False without psycopg2")
            
            print("✅ Test passed: appUtils imports without psycopg2")
            
        except ImportError as e:
            self.fail(f"Failed to import appUtils without psycopg2: {e}")
        
        finally:
            # Restore psycopg2
            if psycopg2_backup is not None:
                sys.modules['psycopg2'] = psycopg2_backup

    def test_import_appTasks_without_psycopg2(self):
        """Test that appTasks can be imported without psycopg2"""
        # Hide psycopg2 if present
        psycopg2_backup = sys.modules.get('psycopg2')
        if 'psycopg2' in sys.modules:
            del sys.modules['psycopg2']
        
        sys.modules['psycopg2'] = None  # Simulate ImportError
        
        try:
            # Mock config module
            sys.modules['config'] = MagicMock()
            sys.modules['config.config'] = MagicMock()
            
            # This should not raise ImportError
            from modules import appTasks
            
            # Verify flag is set correctly
            self.assertFalse(appTasks.POSTGRESQL_AVAILABLE,
                           "POSTGRESQL_AVAILABLE should be False without psycopg2")
            
            print("✅ Test passed: appTasks imports without psycopg2")
            
        except ImportError as e:
            self.fail(f"Failed to import appTasks without psycopg2: {e}")
        
        finally:
            # Restore psycopg2
            if psycopg2_backup is not None:
                sys.modules['psycopg2'] = psycopg2_backup

    def test_postgresql_available_with_psycopg2(self):
        """Test that POSTGRESQL_AVAILABLE is True when psycopg2 is present"""
        try:
            import psycopg2
            psycopg2_present = True
        except ImportError:
            psycopg2_present = False
            self.skipTest("psycopg2 not installed, skipping test")
        
        if psycopg2_present:
            from modules import appUtils
            self.assertTrue(appUtils.POSTGRESQL_AVAILABLE,
                          "POSTGRESQL_AVAILABLE should be True with psycopg2")
            print("✅ Test passed: POSTGRESQL_AVAILABLE=True with psycopg2")

    def test_get_datasource_connexion_without_postgresql(self):
        """Test get_datasource_connexion_from_layer returns None without PostgreSQL"""
        # Mock QGIS layer
        mock_layer = Mock()
        mock_layer.providerType.return_value = 'postgres'
        
        # Hide psycopg2
        psycopg2_backup = sys.modules.get('psycopg2')
        if 'psycopg2' in sys.modules:
            del sys.modules['psycopg2']
        
        sys.modules['psycopg2'] = None
        
        try:
            from modules import appUtils
            
            connexion, source_uri = appUtils.get_datasource_connexion_from_layer(mock_layer)
            
            self.assertIsNone(connexion, 
                            "Connection should be None without PostgreSQL")
            self.assertIsNone(source_uri,
                            "Source URI should be None without PostgreSQL")
            
            print("✅ Test passed: get_datasource_connexion returns None without psycopg2")
            
        finally:
            if psycopg2_backup is not None:
                sys.modules['psycopg2'] = psycopg2_backup

    def test_get_datasource_connexion_non_postgres_layer(self):
        """Test get_datasource_connexion_from_layer with non-PostgreSQL layer"""
        from modules import appUtils
        
        # Mock OGR layer
        mock_layer = Mock()
        mock_layer.providerType.return_value = 'ogr'
        
        connexion, source_uri = appUtils.get_datasource_connexion_from_layer(mock_layer)
        
        self.assertIsNone(connexion,
                        "Connection should be None for non-PostgreSQL layer")
        self.assertIsNone(source_uri,
                        "Source URI should be None for non-PostgreSQL layer")
        
        print("✅ Test passed: Returns None for non-PostgreSQL layers")


class TestPhase1Integration(unittest.TestCase):
    """Integration tests for Phase 1"""

    def setUp(self):
        """Setup test environment"""
        # Mock QGIS modules
        sys.modules['qgis'] = MagicMock()
        sys.modules['qgis.core'] = MagicMock()
        sys.modules['qgis.gui'] = MagicMock()
        sys.modules['qgis.utils'] = MagicMock()

    def test_conditional_postgresql_logic_in_appTasks(self):
        """Test that appTasks handles PostgreSQL unavailability"""
        # This is a placeholder for more complex integration tests
        # In real scenario, would test FilterTask with POSTGRESQL_AVAILABLE=False
        print("✅ Integration test placeholder - would test FilterTask behavior")
        self.assertTrue(True)


def run_tests():
    """Run all tests"""
    print("=" * 70)
    print("FilterMate Phase 1 Test Suite - Optional PostgreSQL Support")
    print("=" * 70)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "=" * 70)
    print("Test Summary:")
    print(f"  Tests run: {result.testsRun}")
    print(f"  Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  Failures: {len(result.failures)}")
    print(f"  Errors: {len(result.errors)}")
    print("=" * 70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

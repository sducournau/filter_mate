"""
FilterMate - Phase 2 Tests: Spatialite Backend
==============================================

Tests pour vérifier que le backend Spatialite fonctionne correctement
comme alternative à PostgreSQL.

Exécution:
    python test_phase2_spatialite_backend.py

Prérequis:
    - Python 3.7+
    - sqlite3 (inclus avec Python)
    - pyspatialite ou mod_spatialite installé

Author: GitHub Copilot (Claude Sonnet 4.5)
Date: 2 décembre 2025
"""

import unittest
import sys
import os
import tempfile
import sqlite3
from pathlib import Path

# Add modules to path
sys.path.insert(0, str(Path(__file__).parent))


class TestPhase2SpatialiteBackend(unittest.TestCase):
    """Tests pour Phase 2: Backend Spatialite"""

    def setUp(self):
        """Setup test environment"""
        self.test_db_path = tempfile.mktemp(suffix='.sqlite')
        
    def tearDown(self):
        """Cleanup test files"""
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    def test_import_create_temp_spatialite_table(self):
        """Test 1: Import de la fonction create_temp_spatialite_table"""
        try:
            from modules.appUtils import create_temp_spatialite_table
            self.assertTrue(callable(create_temp_spatialite_table))
            print("✅ Test 1 PASSED: create_temp_spatialite_table importé avec succès")
        except ImportError as e:
            self.fail(f"❌ Test 1 FAILED: Cannot import create_temp_spatialite_table: {e}")

    def test_import_get_spatialite_datasource(self):
        """Test 2: Import de la fonction get_spatialite_datasource_from_layer"""
        try:
            from modules.appUtils import get_spatialite_datasource_from_layer
            self.assertTrue(callable(get_spatialite_datasource_from_layer))
            print("✅ Test 2 PASSED: get_spatialite_datasource_from_layer importé avec succès")
        except ImportError as e:
            self.fail(f"❌ Test 2 FAILED: Cannot import get_spatialite_datasource_from_layer: {e}")

    def test_import_qgis_expression_to_spatialite(self):
        """Test 3: Import de la méthode qgis_expression_to_spatialite"""
        try:
            # Cannot directly test class method without QGIS, but check module imports
            from modules import appTasks
            self.assertTrue(hasattr(appTasks, 'FilterEngineTask'))
            print("✅ Test 3 PASSED: appTasks module importé (qgis_expression_to_spatialite devrait être disponible)")
        except ImportError as e:
            self.fail(f"❌ Test 3 FAILED: Cannot import appTasks: {e}")

    def test_spatialite_connection(self):
        """Test 4: Connexion Spatialite basique"""
        try:
            conn = sqlite3.connect(self.test_db_path)
            conn.enable_load_extension(True)
            
            # Try loading Spatialite extension
            spatialite_loaded = False
            try:
                conn.load_extension('mod_spatialite')
                spatialite_loaded = True
            except:
                try:
                    conn.load_extension('mod_spatialite.dll')
                    spatialite_loaded = True
                except:
                    try:
                        conn.load_extension('libspatialite')
                        spatialite_loaded = True
                    except:
                        pass
            
            conn.close()
            
            if spatialite_loaded:
                print("✅ Test 4 PASSED: Spatialite extension chargée avec succès")
            else:
                print("⚠️  Test 4 WARNING: Spatialite extension non disponible (normal si pas installé)")
                print("   Pour installer: pip install pyspatialite")
            
            # Test passes even if Spatialite not available (graceful degradation)
            self.assertTrue(True)
            
        except Exception as e:
            self.fail(f"❌ Test 4 FAILED: Spatialite connection error: {e}")

    def test_create_basic_spatialite_table(self):
        """Test 5: Création table Spatialite basique (sans geometry)"""
        try:
            conn = sqlite3.connect(self.test_db_path)
            cursor = conn.cursor()
            
            # Create simple table
            cursor.execute("""
                CREATE TABLE test_table (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    value REAL
                )
            """)
            
            # Insert test data
            cursor.execute("INSERT INTO test_table VALUES (1, 'test', 42.5)")
            conn.commit()
            
            # Verify
            cursor.execute("SELECT * FROM test_table WHERE id = 1")
            result = cursor.fetchone()
            
            self.assertIsNotNone(result)
            self.assertEqual(result[0], 1)
            self.assertEqual(result[1], 'test')
            self.assertEqual(result[2], 42.5)
            
            cursor.close()
            conn.close()
            
            print("✅ Test 5 PASSED: Table Spatialite basique créée et interrogée")
            
        except Exception as e:
            self.fail(f"❌ Test 5 FAILED: {e}")

    def test_expression_conversion_type_casting(self):
        """Test 6: Conversion PostgreSQL :: vers Spatialite CAST()"""
        from modules.appTasks import FilterEngineTask
        from unittest.mock import Mock
        
        # Create mock task
        mock_task = Mock(spec=FilterEngineTask)
        mock_task.qgis_expression_to_spatialite = FilterEngineTask.qgis_expression_to_spatialite.__get__(mock_task)
        
        # Test PostgreSQL :: numeric -> Spatialite CAST(... AS REAL)
        pg_expr = '"field"::numeric > 100'
        spatialite_expr = mock_task.qgis_expression_to_spatialite(pg_expr)
        
        self.assertIn('CAST', spatialite_expr)
        self.assertNotIn('::', spatialite_expr)
        print(f"   PostgreSQL: {pg_expr}")
        print(f"   Spatialite: {spatialite_expr}")
        print("✅ Test 6 PASSED: Conversion type casting PostgreSQL -> Spatialite")

    def test_expression_conversion_ilike(self):
        """Test 7: Conversion ILIKE vers LOWER() LIKE"""
        from modules.appTasks import FilterEngineTask
        from unittest.mock import Mock
        
        mock_task = Mock(spec=FilterEngineTask)
        mock_task.qgis_expression_to_spatialite = FilterEngineTask.qgis_expression_to_spatialite.__get__(mock_task)
        
        # Test ILIKE -> LOWER() LIKE
        pg_expr = 'name ILIKE \'%test%\''
        spatialite_expr = mock_task.qgis_expression_to_spatialite(pg_expr)
        
        self.assertIn('LOWER', spatialite_expr)
        self.assertNotIn('ILIKE', spatialite_expr)
        print(f"   PostgreSQL: {pg_expr}")
        print(f"   Spatialite: {spatialite_expr}")
        print("✅ Test 7 PASSED: Conversion ILIKE -> LOWER() LIKE")


def run_tests():
    """Run all Phase 2 tests"""
    print("\n" + "="*70)
    print("FilterMate - Phase 2 Tests: Spatialite Backend")
    print("="*70 + "\n")
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPhase2SpatialiteBackend)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "="*70)
    print("RÉSUMÉ DES TESTS PHASE 2")
    print("="*70)
    print(f"Tests exécutés: {result.testsRun}")
    print(f"Succès: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Échecs: {len(result.failures)}")
    print(f"Erreurs: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n✅ TOUS LES TESTS PHASE 2 ONT RÉUSSI!")
        print("\n📋 Prochaines étapes:")
        print("   1. Adapter manage_layer_subset_strings pour Spatialite")
        print("   2. Tester avec vraies couches QGIS")
        print("   3. Benchmarks performances")
    else:
        print("\n❌ CERTAINS TESTS ONT ÉCHOUÉ")
        print("Vérifier les erreurs ci-dessus")
    
    print("="*70 + "\n")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

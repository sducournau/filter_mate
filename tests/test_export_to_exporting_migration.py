"""
Test migration from EXPORT to EXPORTING in CURRENT_PROJECT
"""

import unittest
import sys
import os
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import migrate_export_to_exporting


class TestExportToExportingMigration(unittest.TestCase):
    """Test suite for EXPORT to EXPORTING migration"""
    
    def test_migrate_export_to_exporting_simple(self):
        """Test migration of EXPORT to EXPORTING when only EXPORT exists"""
        config = {
            "CURRENT_PROJECT": {
                "EXPORT": {
                    "HAS_LAYERS_TO_EXPORT": True,
                    "LAYERS_TO_EXPORT": ["layer1", "layer2"],
                    "PROJECTION_TO_EXPORT": "EPSG:4326"
                }
            }
        }
        
        migrated = migrate_export_to_exporting(config)
        
        # Check EXPORTING exists
        self.assertIn("EXPORTING", migrated["CURRENT_PROJECT"])
        
        # Check EXPORT is removed
        self.assertNotIn("EXPORT", migrated["CURRENT_PROJECT"])
        
        # Check data was migrated correctly
        self.assertEqual(
            migrated["CURRENT_PROJECT"]["EXPORTING"]["HAS_LAYERS_TO_EXPORT"],
            True
        )
        self.assertEqual(
            migrated["CURRENT_PROJECT"]["EXPORTING"]["LAYERS_TO_EXPORT"],
            ["layer1", "layer2"]
        )
        self.assertEqual(
            migrated["CURRENT_PROJECT"]["EXPORTING"]["PROJECTION_TO_EXPORT"],
            "EPSG:4326"
        )
    
    def test_migrate_both_exist_keeps_exporting(self):
        """Test that when both exist, EXPORTING is kept and EXPORT is removed"""
        config = {
            "CURRENT_PROJECT": {
                "EXPORT": {
                    "HAS_LAYERS_TO_EXPORT": False,
                    "LAYERS_TO_EXPORT": ["old_layer"]
                },
                "EXPORTING": {
                    "HAS_LAYERS_TO_EXPORT": True,
                    "LAYERS_TO_EXPORT": ["new_layer"]
                }
            }
        }
        
        migrated = migrate_export_to_exporting(config)
        
        # Check EXPORTING exists with original data
        self.assertIn("EXPORTING", migrated["CURRENT_PROJECT"])
        self.assertEqual(
            migrated["CURRENT_PROJECT"]["EXPORTING"]["LAYERS_TO_EXPORT"],
            ["new_layer"]
        )
        
        # Check EXPORT is removed
        self.assertNotIn("EXPORT", migrated["CURRENT_PROJECT"])
    
    def test_no_migration_when_only_exporting_exists(self):
        """Test that no migration happens when only EXPORTING exists"""
        config = {
            "CURRENT_PROJECT": {
                "EXPORTING": {
                    "HAS_LAYERS_TO_EXPORT": True,
                    "LAYERS_TO_EXPORT": ["layer1"]
                }
            }
        }
        
        migrated = migrate_export_to_exporting(config)
        
        # Check EXPORTING still exists with same data
        self.assertIn("EXPORTING", migrated["CURRENT_PROJECT"])
        self.assertEqual(
            migrated["CURRENT_PROJECT"]["EXPORTING"]["LAYERS_TO_EXPORT"],
            ["layer1"]
        )
        
        # Check EXPORT doesn't exist
        self.assertNotIn("EXPORT", migrated["CURRENT_PROJECT"])
    
    def test_no_migration_when_no_current_project(self):
        """Test that migration handles missing CURRENT_PROJECT gracefully"""
        config = {
            "APP": {
                "OPTIONS": {}
            }
        }
        
        # Should not raise an error
        migrated = migrate_export_to_exporting(config)
        
        # Config should be unchanged
        self.assertEqual(migrated, config)
    
    def test_migration_preserves_other_keys(self):
        """Test that migration doesn't affect other keys in CURRENT_PROJECT"""
        config = {
            "CURRENT_PROJECT": {
                "EXPORT": {
                    "HAS_LAYERS_TO_EXPORT": True
                },
                "OPTIONS": {
                    "PROJECT_ID": "test123"
                },
                "layers": []
            }
        }
        
        migrated = migrate_export_to_exporting(config)
        
        # Check other keys are preserved
        self.assertIn("OPTIONS", migrated["CURRENT_PROJECT"])
        self.assertIn("layers", migrated["CURRENT_PROJECT"])
        self.assertEqual(
            migrated["CURRENT_PROJECT"]["OPTIONS"]["PROJECT_ID"],
            "test123"
        )
        
        # Check migration happened
        self.assertIn("EXPORTING", migrated["CURRENT_PROJECT"])
        self.assertNotIn("EXPORT", migrated["CURRENT_PROJECT"])


if __name__ == '__main__':
    unittest.main()

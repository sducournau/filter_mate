"""
Test primary key detection for all provider types.

This test validates that FilterMate correctly detects primary keys for:
- PostgreSQL layers (with and without PRIMARY KEY constraint)
- Spatialite layers
- OGR/Shapefile layers (using FID)
- Memory layers
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from qgis.core import QgsField, QgsVectorLayer
from qgis.PyQt.QtCore import QMetaType


class TestPrimaryKeyDetection(unittest.TestCase):
    """Test suite for primary key detection across all provider types."""
    
    def setUp(self):
        """Set up test fixtures."""
        # v4.0: migrated from modules/ to core/tasks/
        from filter_mate.core.tasks.layer_management_task import LayersManagementEngineTask
        self.task = LayersManagementEngineTask("Test Task", {})
    
    def test_postgresql_with_declared_primary_key(self):
        """PostgreSQL layer with declared PRIMARY KEY should use it directly."""
        mock_layer = Mock()
        mock_layer.providerType.return_value = 'postgres'
        mock_layer.name.return_value = "postgresql_with_pk"
        mock_layer.featureCount.return_value = 1000
        mock_layer.primaryKeyAttributes.return_value = [0]  # PK at index 0
        
        # Create mock field
        mock_field = Mock()
        mock_field.name.return_value = "gid"
        mock_field.typeName.return_value = "INTEGER"
        mock_field.isNumeric.return_value = True
        
        mock_fields = Mock()
        mock_fields.__getitem__ = Mock(return_value=mock_field)
        mock_layer.fields.return_value = mock_fields
        
        # Should NOT call uniqueValues (would freeze on large tables)
        result = self.task.search_primary_key_from_layer(mock_layer)
        
        # Verify result
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0], "gid")  # field name
        self.assertEqual(result[1], 0)      # field index
        self.assertEqual(result[2], "INTEGER")  # field type
        self.assertTrue(result[3])          # is numeric
        
        # Verify uniqueValues was NOT called (critical for performance)
        mock_layer.uniqueValues.assert_not_called()
    
    def test_postgresql_without_primary_key_uses_ctid(self):
        """PostgreSQL layer without PRIMARY KEY should use 'ctid'."""
        mock_layer = Mock()
        mock_layer.providerType.return_value = 'postgres'
        mock_layer.name.return_value = "postgresql_no_pk"
        mock_layer.featureCount.return_value = 1000
        mock_layer.primaryKeyAttributes.return_value = []  # No declared PK
        
        # Create mock fields without 'id' in name
        mock_field1 = Mock()
        mock_field1.name.return_value = "name"
        mock_field2 = Mock()
        mock_field2.name.return_value = "status"
        
        mock_fields = Mock()
        mock_fields.__iter__ = Mock(return_value=iter([mock_field1, mock_field2]))
        mock_layer.fields.return_value = mock_fields
        
        result = self.task.search_primary_key_from_layer(mock_layer)
        
        # Should return ctid
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[0], "ctid")
        self.assertEqual(result[1], -1)  # Special index for ctid
        self.assertEqual(result[2], "tid")
        self.assertFalse(result[3])  # not numeric (special type)
    
    def test_postgresql_finds_id_field_without_pk(self):
        """PostgreSQL without declared PK but with 'id' field should use it."""
        mock_layer = Mock()
        mock_layer.providerType.return_value = 'postgres'
        mock_layer.name.return_value = "postgresql_with_id_field"
        mock_layer.featureCount.return_value = 1000
        mock_layer.primaryKeyAttributes.return_value = []  # No declared PK
        
        # Create mock fields
        mock_id_field = Mock()
        mock_id_field.name.return_value = "id"
        mock_id_field.typeName.return_value = "INTEGER"
        mock_id_field.isNumeric.return_value = True
        
        mock_name_field = Mock()
        mock_name_field.name.return_value = "name"
        
        mock_fields = Mock()
        mock_fields.__iter__ = Mock(return_value=iter([mock_id_field, mock_name_field]))
        mock_fields.indexFromName = Mock(return_value=0)
        mock_layer.fields.return_value = mock_fields
        
        result = self.task.search_primary_key_from_layer(mock_layer)
        
        # Should find and use the 'id' field
        self.assertEqual(result[0], "id")
        self.assertEqual(result[2], "INTEGER")
        self.assertTrue(result[3])
    
    def test_spatialite_with_declared_primary_key(self):
        """Spatialite layer with declared PRIMARY KEY."""
        mock_layer = Mock()
        mock_layer.providerType.return_value = 'spatialite'
        mock_layer.name.return_value = "spatialite_layer"
        mock_layer.featureCount.return_value = 100
        mock_layer.primaryKeyAttributes.return_value = [0]
        
        mock_field = Mock()
        mock_field.name.return_value = "fid"
        mock_field.typeName.return_value = "INTEGER"
        mock_field.isNumeric.return_value = True
        
        mock_fields = Mock()
        mock_fields.__getitem__ = Mock(return_value=mock_field)
        mock_layer.fields.return_value = mock_fields
        
        # CRITICAL FIX: uniqueValues() is NOT called anymore (thread-safety)
        # Declared primary key is trusted without verification
        
        result = self.task.search_primary_key_from_layer(mock_layer)
        
        self.assertEqual(result[0], "fid")
        self.assertTrue(result[3])  # is numeric
        # Verify uniqueValues was NOT called (thread-safety fix)
        mock_layer.uniqueValues.assert_not_called()
    
    def test_ogr_shapefile_finds_fid(self):
        """OGR/Shapefile layer should find FID field."""
        mock_layer = Mock()
        mock_layer.providerType.return_value = 'ogr'
        mock_layer.name.return_value = "shapefile"
        mock_layer.featureCount.return_value = 50
        mock_layer.primaryKeyAttributes.return_value = [0]  # FID at index 0
        
        mock_field = Mock()
        mock_field.name.return_value = "fid"
        mock_field.typeName.return_value = "Integer64"
        mock_field.isNumeric.return_value = True
        
        mock_fields = Mock()
        mock_fields.__getitem__ = Mock(return_value=mock_field)
        mock_layer.fields.return_value = mock_fields
        
        # CRITICAL FIX: uniqueValues() is NOT called anymore (thread-safety)
        # Declared primary key is trusted without verification
        
        result = self.task.search_primary_key_from_layer(mock_layer)
        
        self.assertEqual(result[0], "fid")
        self.assertTrue(result[3])
        # Verify uniqueValues was NOT called (thread-safety fix)
        mock_layer.uniqueValues.assert_not_called()
    
    def test_memory_layer_uses_first_field(self):
        """Memory layer without PK should use first field (thread-safety fix).
        
        CRITICAL FIX: Previously, uniqueValues() was called to verify uniqueness.
        This caused access violations when run from QgsTask background thread.
        Now we trust the first field without verification.
        """
        mock_layer = Mock()
        mock_layer.providerType.return_value = 'memory'
        mock_layer.name.return_value = "memory_layer"
        mock_layer.featureCount.return_value = 10
        mock_layer.primaryKeyAttributes.return_value = []
        
        # First field (may or may not be unique - we don't check anymore)
        mock_field = Mock()
        mock_field.name.return_value = "category"
        mock_field.typeName.return_value = "String"
        mock_field.isNumeric.return_value = False
        
        mock_fields = Mock()
        mock_fields.__iter__ = Mock(return_value=iter([mock_field]))
        mock_fields.__getitem__ = Mock(return_value=mock_field)
        mock_fields.count.return_value = 1
        mock_fields.indexFromName = Mock(return_value=0)
        mock_fields.indexOf = Mock(return_value=0)
        mock_layer.fields.return_value = mock_fields
        
        result = self.task.search_primary_key_from_layer(mock_layer)
        
        # CRITICAL FIX: Should use first field instead of creating virtual_id
        # This avoids thread-unsafe uniqueValues() call
        self.assertEqual(result[0], "category")
        # Verify uniqueValues was NOT called (thread-safety fix)
        mock_layer.uniqueValues.assert_not_called()
        # Verify addExpressionField was NOT called (no virtual_id needed)
        mock_layer.addExpressionField.assert_not_called()
    
    def test_large_postgresql_layer_no_uniqueness_check(self):
        """Large PostgreSQL layer should skip uniqueness check (performance)."""
        mock_layer = Mock()
        mock_layer.providerType.return_value = 'postgres'
        mock_layer.name.return_value = "large_postgresql"
        mock_layer.featureCount.return_value = 500000  # Large table
        mock_layer.primaryKeyAttributes.return_value = [2]
        
        mock_field = Mock()
        mock_field.name.return_value = "id"
        mock_field.typeName.return_value = "BIGINT"
        mock_field.isNumeric.return_value = True
        
        mock_fields = Mock()
        mock_fields.__getitem__ = Mock(return_value=mock_field)
        mock_layer.fields.return_value = mock_fields
        
        result = self.task.search_primary_key_from_layer(mock_layer)
        
        # Should use declared PK without uniqueness check
        self.assertEqual(result[0], "id")
        mock_layer.uniqueValues.assert_not_called()  # CRITICAL: no freeze
    
    def test_unknown_feature_count_uses_declared_pk(self):
        """Layer with unknown feature count (-1) should trust declared PK."""
        mock_layer = Mock()
        mock_layer.providerType.return_value = 'postgres'
        mock_layer.name.return_value = "large_view"
        mock_layer.featureCount.return_value = -1  # Unknown count
        mock_layer.primaryKeyAttributes.return_value = [0]
        
        mock_field = Mock()
        mock_field.name.return_value = "pk_field"
        mock_field.typeName.return_value = "INTEGER"
        mock_field.isNumeric.return_value = True
        
        mock_fields = Mock()
        mock_fields.__getitem__ = Mock(return_value=mock_field)
        mock_layer.fields.return_value = mock_fields
        
        result = self.task.search_primary_key_from_layer(mock_layer)
        
        self.assertEqual(result[0], "pk_field")
        # Should NOT call uniqueValues with unknown count
        mock_layer.uniqueValues.assert_not_called()


class TestPrimaryKeyEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""
    
    def setUp(self):
        """Set up test fixtures."""
        # v4.0: migrated from modules/ to core/tasks/
        from filter_mate.core.tasks.layer_management_task import LayersManagementEngineTask
        self.task = LayersManagementEngineTask("Test Task", {})
    
    def test_composite_primary_key_uses_first(self):
        """Composite primary key (multiple fields) should use first field."""
        mock_layer = Mock()
        mock_layer.providerType.return_value = 'postgres'
        mock_layer.name.return_value = "composite_pk"
        mock_layer.featureCount.return_value = 100
        mock_layer.primaryKeyAttributes.return_value = [0, 1]  # Composite PK
        
        mock_field1 = Mock()
        mock_field1.name.return_value = "region_id"
        mock_field1.typeName.return_value = "INTEGER"
        mock_field1.isNumeric.return_value = True
        
        mock_fields = Mock()
        mock_fields.__getitem__ = Mock(return_value=mock_field1)
        mock_layer.fields.return_value = mock_fields
        
        result = self.task.search_primary_key_from_layer(mock_layer)
        
        # Should use first field of composite key
        self.assertEqual(result[0], "region_id")
    
    def test_field_name_variations_for_id(self):
        """Test that various ID field names are detected."""
        id_variations = ['id', 'ID', 'Id', 'object_id', 'feature_id', 'gid', 'oid']
        
        for id_name in id_variations:
            with self.subTest(id_name=id_name):
                mock_layer = Mock()
                mock_layer.providerType.return_value = 'postgres'
                mock_layer.name.return_value = f"layer_with_{id_name}"
                mock_layer.featureCount.return_value = 100
                mock_layer.primaryKeyAttributes.return_value = []
                
                mock_field = Mock()
                mock_field.name.return_value = id_name
                mock_field.typeName.return_value = "INTEGER"
                mock_field.isNumeric.return_value = True
                
                mock_fields = Mock()
                mock_fields.__iter__ = Mock(return_value=iter([mock_field]))
                mock_fields.indexFromName = Mock(return_value=0)
                mock_layer.fields.return_value = mock_fields
                
                result = self.task.search_primary_key_from_layer(mock_layer)
                
                # Should find ID field (case-insensitive, contains 'id')
                self.assertEqual(result[0], id_name)


if __name__ == '__main__':
    unittest.main()

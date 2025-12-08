# -*- coding: utf-8 -*-
"""
Test to verify the Spatialite temp table fix.

This test verifies that:
1. Temp tables are disabled (_use_temp_table = False)
2. Expressions use inline WKT with GeomFromText()
3. No references to temp tables in generated expressions
"""

import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSpatialiteTempTableFix(unittest.TestCase):
    """Test the fix for Spatialite temp table issue."""
    
    def test_temp_table_disabled_by_default(self):
        """Verify that temp tables are disabled in backend initialization."""
        from modules.backends.spatialite_backend import SpatialiteGeometricFilter
        
        backend = SpatialiteGeometricFilter({})
        
        # CRITICAL: _use_temp_table must be False
        self.assertFalse(
            backend._use_temp_table,
            "Temp tables must be disabled for setSubsetString compatibility"
        )
    
    def test_expression_uses_inline_wkt(self):
        """Verify that expressions use inline WKT instead of temp tables."""
        from modules.backends.spatialite_backend import SpatialiteGeometricFilter
        
        backend = SpatialiteGeometricFilter({})
        
        # Mock layer properties
        layer_props = {
            "layer_name": "test_layer",
            "layer_table_name": "test_table",
            "layer_geometry_field": "geom",
            "primary_key_name": "id",
            "layer": None  # No actual layer needed for expression building
        }
        
        # Simple predicates
        predicates = {
            "intersects": "ST_Intersects"
        }
        
        # Simple WKT (point)
        source_geom = "POINT(0 0)"
        
        # Build expression
        expression = backend.build_expression(
            layer_props=layer_props,
            predicates=predicates,
            source_geom=source_geom
        )
        
        # Verify expression exists
        self.assertIsNotNone(expression, "Expression should be generated")
        self.assertNotEqual(expression, "", "Expression should not be empty")
        
        # CRITICAL: Expression must use GeomFromText(), NOT temp table reference
        self.assertIn("GeomFromText", expression, "Expression must use GeomFromText()")
        self.assertNotIn("_fm_temp_geom_", expression, "Expression must NOT reference temp tables")
        
        # Verify it contains the WKT
        self.assertIn(source_geom, expression, "Expression must contain the source WKT")
        
        # Verify spatial function is present
        self.assertIn("ST_Intersects", expression, "Expression must contain spatial predicate")
    
    def test_no_temp_table_creation_in_build_expression(self):
        """Verify that build_expression never creates temp tables."""
        from modules.backends.spatialite_backend import SpatialiteGeometricFilter
        
        backend = SpatialiteGeometricFilter({})
        
        # Mock layer properties
        layer_props = {
            "layer_name": "test_layer",
            "layer_geometry_field": "geom",
            "primary_key_name": "id",
            "layer": None
        }
        
        predicates = {"intersects": "ST_Intersects"}
        
        # Large WKT to trigger temp table logic (if it were enabled)
        large_wkt = "POLYGON((" + ",".join([f"{i} {i}" for i in range(10000)]) + "))"
        
        # Build expression
        expression = backend.build_expression(
            layer_props=layer_props,
            predicates=predicates,
            source_geom=large_wkt
        )
        
        # Even with large WKT, no temp table should be created
        self.assertIsNone(backend._temp_table_name, "No temp table should be created")
        self.assertIsNone(backend._temp_table_conn, "No connection should be opened")
        
        # Expression should use inline WKT
        self.assertIn("GeomFromText", expression, "Must use GeomFromText even with large WKT")
        self.assertNotIn("_fm_temp_geom_", expression, "Must not reference temp table")
    
    def test_expression_with_multiple_predicates(self):
        """Test that multiple predicates work correctly with inline WKT."""
        from modules.backends.spatialite_backend import SpatialiteGeometricFilter
        
        backend = SpatialiteGeometricFilter({})
        
        layer_props = {
            "layer_name": "test_layer",
            "layer_geometry_field": "geom",
            "primary_key_name": "id",
            "layer": None
        }
        
        predicates = {
            "intersects": "ST_Intersects",
            "within": "ST_Within",
            "overlaps": "ST_Overlaps"
        }
        
        source_geom = "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
        
        expression = backend.build_expression(
            layer_props=layer_props,
            predicates=predicates,
            source_geom=source_geom
        )
        
        # Verify all predicates present
        self.assertIn("ST_Intersects", expression)
        self.assertIn("ST_Within", expression)
        self.assertIn("ST_Overlaps", expression)
        
        # Verify OR combination
        self.assertIn(" OR ", expression)
        
        # Verify no temp tables
        self.assertNotIn("_fm_temp_geom_", expression)
        
        # Each predicate should use GeomFromText with the same WKT
        self.assertEqual(expression.count("GeomFromText"), 3, "Should have 3 GeomFromText calls")


class TestSpatialiteExpressionFormat(unittest.TestCase):
    """Test the format of generated Spatialite expressions."""
    
    def test_expression_sql_syntax(self):
        """Verify that generated expressions have valid SQL syntax."""
        from modules.backends.spatialite_backend import SpatialiteGeometricFilter
        
        backend = SpatialiteGeometricFilter({})
        
        layer_props = {
            "layer_name": "my_layer",
            "layer_geometry_field": "geometry",
            "primary_key_name": "fid",
            "layer": None
        }
        
        predicates = {"intersects": "ST_Intersects"}
        source_geom = "POINT(100 50)"
        
        expression = backend.build_expression(
            layer_props=layer_props,
            predicates=predicates,
            source_geom=source_geom
        )
        
        # Expected format: ST_Intersects("geometry", GeomFromText('POINT(100 50)'))
        # Verify structure
        self.assertTrue(expression.startswith("ST_Intersects"), "Should start with function name")
        self.assertIn('"geometry"', expression, "Geometry field should be quoted")
        self.assertIn("GeomFromText('", expression, "WKT should be in single quotes")
        self.assertIn("')", expression, "WKT single quote should be closed")
        
        # Count parentheses (should be balanced)
        open_parens = expression.count('(')
        close_parens = expression.count(')')
        self.assertEqual(open_parens, close_parens, "Parentheses must be balanced")


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)

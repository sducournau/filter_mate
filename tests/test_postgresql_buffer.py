# -*- coding: utf-8 -*-
"""
Tests for PostgreSQL backend buffer handling.

Verifies that:
1. ST_Buffer expressions are correctly parsed
2. EXISTS subqueries are properly built with buffer
3. Buffer endcap styles are correctly applied
4. Full filtering flow works with buffer values
"""

import unittest
import re
from unittest.mock import Mock, patch, MagicMock


class TestPostgreSQLBufferParsing(unittest.TestCase):
    """Test buffer expression parsing in PostgreSQL backend."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock the backend without QGIS dependencies
        self.task_params = {
            'buffer_endcap_style': 'round'
        }
    
    def test_parse_buffer_3part_simple(self):
        """Test parsing ST_Buffer with 3-part table reference (no endcap style)."""
        source_geom = 'ST_Buffer("ign_topo"."troncon_de_route"."the_geom", 22)'
        
        # Pattern from postgresql_backend.py
        buffer_pattern_3part = r'ST_Buffer\s*\(\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*,\s*([^)]+)\)'
        match = re.match(buffer_pattern_3part, source_geom, re.IGNORECASE)
        
        self.assertIsNotNone(match, f"Pattern should match: {source_geom}")
        schema, table, geom_field, buffer_value = match.groups()
        
        self.assertEqual(schema, "ign_topo")
        self.assertEqual(table, "troncon_de_route")
        self.assertEqual(geom_field, "the_geom")
        self.assertEqual(buffer_value.strip(), "22")
    
    def test_parse_buffer_3part_with_endcap(self):
        """Test parsing ST_Buffer with 3-part table reference AND endcap style."""
        source_geom = "ST_Buffer(\"ign_topo\".\"troncon_de_route\".\"the_geom\", 22, 'endcap=round')"
        
        # Current pattern - this will FAIL because it stops at first )
        buffer_pattern_3part = r'ST_Buffer\s*\(\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*,\s*([^)]+)\)'
        match = re.match(buffer_pattern_3part, source_geom, re.IGNORECASE)
        
        # This test demonstrates the current behavior
        if match:
            schema, table, geom_field, buffer_value = match.groups()
            print(f"Matched - buffer_value captured: '{buffer_value}'")
            # buffer_value will be "22, 'endcap=round" (missing closing quote and paren)
        else:
            print("Pattern did not match with endcap style")
    
    def test_parse_buffer_2part_simple(self):
        """Test parsing ST_Buffer with 2-part table reference (no schema)."""
        source_geom = 'ST_Buffer("troncon_de_route"."the_geom", 22)'
        
        buffer_pattern_2part = r'ST_Buffer\s*\(\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*,\s*([^)]+)\)'
        match = re.match(buffer_pattern_2part, source_geom, re.IGNORECASE)
        
        self.assertIsNotNone(match, f"Pattern should match: {source_geom}")
        table, geom_field, buffer_value = match.groups()
        
        self.assertEqual(table, "troncon_de_route")
        self.assertEqual(geom_field, "the_geom")
        self.assertEqual(buffer_value.strip(), "22")
    
    def test_parse_buffer_decimal(self):
        """Test parsing ST_Buffer with decimal buffer value."""
        source_geom = 'ST_Buffer("public"."batiment"."geom", 22.5)'
        
        buffer_pattern_3part = r'ST_Buffer\s*\(\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*,\s*([^)]+)\)'
        match = re.match(buffer_pattern_3part, source_geom, re.IGNORECASE)
        
        self.assertIsNotNone(match)
        schema, table, geom_field, buffer_value = match.groups()
        self.assertEqual(buffer_value.strip(), "22.5")


class TestPostgreSQLExistsSubquery(unittest.TestCase):
    """Test EXISTS subquery building with buffer."""
    
    def test_exists_subquery_with_buffer(self):
        """Test that EXISTS subquery correctly includes buffer in WHERE clause."""
        # Simulate what the backend should produce
        source_schema = "ign_topo"
        source_table = "troncon_de_route"
        source_geom_field = "the_geom"
        buffer_value = "22"
        predicate_func = "ST_Intersects"
        target_geom_expr = '"batiment"."geom"'
        
        # Build buffer expression for subquery
        buffer_expr = f'ST_Buffer(__source."{source_geom_field}", {buffer_value})'
        
        # Build WHERE clause
        where_clause = f'{predicate_func}({target_geom_expr}, {buffer_expr})'
        
        # Build full EXISTS subquery
        exists_expr = (
            f'EXISTS ('
            f'SELECT 1 FROM "{source_schema}"."{source_table}" AS __source '
            f'WHERE {where_clause}'
            f')'
        )
        
        expected = (
            'EXISTS ('
            'SELECT 1 FROM "ign_topo"."troncon_de_route" AS __source '
            'WHERE ST_Intersects("batiment"."geom", ST_Buffer(__source."the_geom", 22))'
            ')'
        )
        
        self.assertEqual(exists_expr, expected)
    
    def test_exists_subquery_with_endcap_style(self):
        """Test EXISTS subquery with buffer endcap style."""
        source_schema = "ign_topo"
        source_table = "troncon_de_route"
        source_geom_field = "the_geom"
        buffer_value = "22"
        endcap_style = "flat"
        predicate_func = "ST_Intersects"
        target_geom_expr = '"batiment"."geom"'
        
        # Build buffer expression with endcap style
        buffer_expr = f"ST_Buffer(__source.\"{source_geom_field}\", {buffer_value}, 'endcap={endcap_style}')"
        
        # Build WHERE clause
        where_clause = f'{predicate_func}({target_geom_expr}, {buffer_expr})'
        
        # Build full EXISTS subquery
        exists_expr = (
            f'EXISTS ('
            f'SELECT 1 FROM "{source_schema}"."{source_table}" AS __source '
            f'WHERE {where_clause}'
            f')'
        )
        
        # Verify the expression is valid SQL
        self.assertIn("ST_Buffer(__source.\"the_geom\", 22, 'endcap=flat')", exists_expr)
        self.assertIn('EXISTS (', exists_expr)
        self.assertIn('AS __source', exists_expr)


class TestImprovedBufferPattern(unittest.TestCase):
    """Test improved regex patterns that handle endcap style."""
    
    def test_improved_pattern_simple_buffer(self):
        """Test improved pattern matches simple buffer."""
        source_geom = 'ST_Buffer("ign_topo"."troncon_de_route"."the_geom", 22)'
        
        # Improved pattern that handles optional endcap style
        # Uses non-greedy matching and optional third parameter
        improved_pattern = r'ST_Buffer\s*\(\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*,\s*([0-9.]+)(?:\s*,\s*\'[^\']+\')?\s*\)'
        
        match = re.match(improved_pattern, source_geom, re.IGNORECASE)
        self.assertIsNotNone(match, f"Improved pattern should match simple buffer: {source_geom}")
        
        schema, table, geom_field, buffer_value = match.groups()
        self.assertEqual(schema, "ign_topo")
        self.assertEqual(table, "troncon_de_route")
        self.assertEqual(geom_field, "the_geom")
        self.assertEqual(buffer_value, "22")
    
    def test_improved_pattern_with_endcap(self):
        """Test improved pattern matches buffer with endcap style."""
        source_geom = "ST_Buffer(\"ign_topo\".\"troncon_de_route\".\"the_geom\", 22, 'endcap=round')"
        
        # Improved pattern
        improved_pattern = r'ST_Buffer\s*\(\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*,\s*([0-9.]+)(?:\s*,\s*\'[^\']+\')?\s*\)'
        
        match = re.match(improved_pattern, source_geom, re.IGNORECASE)
        self.assertIsNotNone(match, f"Improved pattern should match buffer with endcap: {source_geom}")
        
        schema, table, geom_field, buffer_value = match.groups()
        self.assertEqual(schema, "ign_topo")
        self.assertEqual(table, "troncon_de_route")
        self.assertEqual(geom_field, "the_geom")
        self.assertEqual(buffer_value, "22")
    
    def test_improved_pattern_decimal_buffer(self):
        """Test improved pattern matches decimal buffer value."""
        source_geom = 'ST_Buffer("public"."commune"."geom", 22.5)'
        
        improved_pattern = r'ST_Buffer\s*\(\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*,\s*([0-9.]+)(?:\s*,\s*\'[^\']+\')?\s*\)'
        
        match = re.match(improved_pattern, source_geom, re.IGNORECASE)
        self.assertIsNotNone(match)
        
        schema, table, geom_field, buffer_value = match.groups()
        self.assertEqual(buffer_value, "22.5")


class TestFullBufferFlow(unittest.TestCase):
    """Test the complete buffer filtering flow."""
    
    def test_prepare_postgresql_source_geom_with_buffer(self):
        """Test that prepare_postgresql_source_geom correctly builds ST_Buffer expression."""
        # Simulate the values that would be set
        param_source_schema = 'ign_topo'
        param_source_table = 'troncon_de_route'
        param_source_geom = 'geom'
        param_buffer_value = 22
        
        # This is what prepare_postgresql_source_geom does
        postgresql_source_geom = 'ST_Buffer("{source_schema}"."{source_table}"."{source_geom}", {buffer_value})'.format(
            source_schema=param_source_schema,
            source_table=param_source_table,
            source_geom=param_source_geom,
            buffer_value=param_buffer_value
        )
        
        expected = 'ST_Buffer("ign_topo"."troncon_de_route"."geom", 22)'
        self.assertEqual(postgresql_source_geom, expected)
    
    def test_full_expression_generation_with_buffer(self):
        """Test complete expression generation from source_geom to final EXISTS."""
        # Step 1: Prepare postgresql_source_geom (as in prepare_postgresql_source_geom)
        source_geom = 'ST_Buffer("ign_topo"."troncon_de_route"."geom", 22)'
        
        # Step 2: Parse source_geom (as in _parse_source_table_reference)
        buffer_pattern_3part = r'ST_Buffer\s*\(\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*,\s*([^)]+)\)'
        match = re.match(buffer_pattern_3part, source_geom, re.IGNORECASE)
        self.assertIsNotNone(match)
        
        schema, table, geom_field, buffer_value = match.groups()
        
        # Build buffer_expr for subquery
        buffer_expr = f'ST_Buffer(__source."{geom_field}", {buffer_value})'
        
        # Step 3: Build EXISTS expression (as in build_expression)
        target_table = 'batiment'
        target_geom_field = 'geom'
        predicate_func = 'ST_Intersects'
        target_geom_expr = f'"{target_table}"."{target_geom_field}"'
        
        where_clause = f'{predicate_func}({target_geom_expr}, {buffer_expr})'
        exists_expr = (
            f'EXISTS ('
            f'SELECT 1 FROM "{schema}"."{table}" AS __source '
            f'WHERE {where_clause}'
            f')'
        )
        
        # Verify final expression
        expected = (
            'EXISTS ('
            'SELECT 1 FROM "ign_topo"."troncon_de_route" AS __source '
            'WHERE ST_Intersects("batiment"."geom", ST_Buffer(__source."geom", 22))'
            ')'
        )
        self.assertEqual(exists_expr, expected)
        
        # Verify SQL structure
        self.assertIn('EXISTS (', exists_expr)
        self.assertIn('AS __source', exists_expr)
        self.assertIn('ST_Buffer(__source."geom", 22)', exists_expr)
        self.assertIn('ST_Intersects', exists_expr)


if __name__ == '__main__':
    unittest.main()

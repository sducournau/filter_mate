"""
Tests for Filter Chaining with Multiple EXISTS Clauses

v4.2.9: Validates the filter chaining feature where multiple spatial filters
are combined for distant layers.

Use Case:
    1. Filter 1 (zone_pop): Spatial selection → intersects distant layers
    2. Filter 2 (ducts with buffer): Buffer intersection → combines with zone_pop filter

Expected Result for distant layer (subducts):
    EXISTS (SELECT 1 FROM zone_pop AS __source WHERE ...)
    AND
    EXISTS (SELECT 1 FROM ducts AS __source WHERE ST_Intersects(..., ST_Buffer(...)))

Author: FilterMate Team
Date: 2026-01-21
"""

import unittest
import sys
import os

# Add parent path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from core.filter.expression_combiner import (
    extract_exists_clauses,
    chain_exists_filters,
    build_chained_distant_filter,
    detect_filter_chain_scenario,
    should_replace_old_subset,
    adapt_exists_for_nested_context
)


class TestExtractExistsClauses(unittest.TestCase):
    """Test extraction of EXISTS clauses from expressions."""
    
    def test_extract_single_exists(self):
        """Test extracting a single EXISTS clause."""
        expression = '''EXISTS (SELECT 1 FROM "ref"."zone_pop" AS __source WHERE ST_Intersects(ST_PointOnSurface("subducts"."geom"), __source."geom") AND (__source."id" IN ('abc'::uuid)))'''
        
        clauses = extract_exists_clauses(expression)
        
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0]['schema'], 'ref')
        self.assertEqual(clauses[0]['table'], 'zone_pop')
        self.assertEqual(clauses[0]['alias'], '__source')
        self.assertIn('EXISTS', clauses[0]['sql'])
    
    def test_extract_multiple_exists(self):
        """Test extracting multiple EXISTS clauses."""
        expression = '''EXISTS (SELECT 1 FROM "ref"."zone_pop" AS __source WHERE ST_Intersects("target"."geom", __source."geom")) AND EXISTS (SELECT 1 FROM "infra"."ducts" AS __source WHERE ST_Intersects("target"."geom", ST_Buffer(__source."geom", 10)))'''
        
        clauses = extract_exists_clauses(expression)
        
        self.assertEqual(len(clauses), 2)
        # First EXISTS - zone_pop
        self.assertEqual(clauses[0]['table'], 'zone_pop')
        # Second EXISTS - ducts
        self.assertEqual(clauses[1]['table'], 'ducts')
    
    def test_extract_no_exists(self):
        """Test extraction when no EXISTS present."""
        expression = '''"id" IN (1, 2, 3)'''
        
        clauses = extract_exists_clauses(expression)
        
        self.assertEqual(len(clauses), 0)
    
    def test_extract_empty_expression(self):
        """Test extraction with empty expression."""
        self.assertEqual(extract_exists_clauses(""), [])
        self.assertEqual(extract_exists_clauses(None), [])


class TestChainExistsFilters(unittest.TestCase):
    """Test chaining of EXISTS filters."""
    
    def test_chain_two_exists(self):
        """Test chaining two EXISTS filters with AND."""
        old_exists = '''EXISTS (SELECT 1 FROM "ref"."zone_pop" AS __source WHERE ST_Intersects("target"."geom", __source."geom"))'''
        new_exists = '''EXISTS (SELECT 1 FROM "infra"."ducts" AS __source WHERE ST_Intersects("target"."geom", ST_Buffer(__source."geom", 10)))'''
        
        result = chain_exists_filters(old_exists, new_exists, 'AND')
        
        # Both EXISTS should be present
        self.assertIn('zone_pop', result)
        self.assertIn('ducts', result)
        self.assertIn('AND', result)
        # Both should be wrapped in parentheses
        self.assertTrue(result.startswith('('))
        self.assertTrue(')' in result)
    
    def test_chain_exists_with_field_condition(self):
        """Test chaining EXISTS with non-EXISTS condition."""
        old_exists = '''EXISTS (SELECT 1 FROM "ref"."zone_pop" AS __source WHERE ST_Intersects("target"."geom", __source."geom"))'''
        new_condition = '''"status" = 'active' '''
        
        result = chain_exists_filters(old_exists, new_condition, 'AND')
        
        self.assertIn('zone_pop', result)
        self.assertIn('status', result)
        self.assertIn('AND', result)
    
    def test_chain_empty_old(self):
        """Test chaining when old expression is empty."""
        new_exists = '''EXISTS (SELECT 1 FROM "infra"."ducts" AS __source WHERE ...)'''
        
        result = chain_exists_filters("", new_exists)
        
        self.assertEqual(result, new_exists)
    
    def test_chain_empty_new(self):
        """Test chaining when new expression is empty."""
        old_exists = '''EXISTS (SELECT 1 FROM "ref"."zone_pop" AS __source WHERE ...)'''
        
        result = chain_exists_filters(old_exists, "")
        
        self.assertEqual(result, old_exists)


class TestBuildChainedDistantFilter(unittest.TestCase):
    """Test building complete chained filter for distant layers."""
    
    def test_build_complete_chain(self):
        """Test building complete filter with zone_pop + ducts buffer."""
        zone_pop_filter = '''EXISTS (SELECT 1 FROM "ref"."zone_pop" AS __source WHERE ST_Intersects(ST_PointOnSurface("subducts"."geom"), __source."geom") AND (__source."id" IN ('abc'::uuid, 'def'::uuid)))'''
        ducts_buffer_filter = '''EXISTS (SELECT 1 FROM "infra"."ducts" AS __source WHERE ST_Intersects("subducts"."geom", ST_Buffer(__source."geom", 10)))'''
        
        result = build_chained_distant_filter(zone_pop_filter, ducts_buffer_filter)
        
        # Check both filters are present
        self.assertIn('zone_pop', result)
        self.assertIn('ducts', result)
        self.assertIn('ST_Buffer', result)
        self.assertIn('AND', result)
    
    def test_build_with_additional_conditions(self):
        """Test building filter with additional non-spatial conditions."""
        zone_pop_filter = '''EXISTS (SELECT 1 FROM "ref"."zone_pop" AS __source WHERE ...)'''
        ducts_buffer_filter = '''EXISTS (SELECT 1 FROM "infra"."ducts" AS __source WHERE ...)'''
        additional = ['"status" = \'active\'', '"type" IN (1, 2)']
        
        result = build_chained_distant_filter(
            zone_pop_filter, 
            ducts_buffer_filter,
            additional_conditions=additional
        )
        
        self.assertIn('zone_pop', result)
        self.assertIn('ducts', result)
        self.assertIn('status', result)
        self.assertIn('type', result)


class TestDetectFilterChainScenario(unittest.TestCase):
    """Test scenario detection for filter chaining."""
    
    def test_detect_spatial_chain(self):
        """Test detection of spatial chain scenario."""
        source_subset = '''EXISTS (SELECT 1 FROM "ref"."zone_pop" AS __source WHERE ...)'''
        
        scenario, context = detect_filter_chain_scenario(
            source_layer_subset=source_subset,
            custom_expression=None,
            buffer_expression="10",  # Buffer active
            has_combine_operator=False
        )
        
        self.assertEqual(scenario, 'spatial_chain')
        self.assertTrue(context['has_spatial_filter'])
        self.assertTrue(context['has_buffer_expression'])
        self.assertFalse(context['has_custom_expression'])
    
    def test_detect_spatial_chain_with_custom(self):
        """Test detection when custom expression is also active."""
        source_subset = '''EXISTS (SELECT 1 FROM "ref"."zone_pop" AS __source WHERE ...)'''
        
        scenario, context = detect_filter_chain_scenario(
            source_layer_subset=source_subset,
            custom_expression='"type" = 1',
            buffer_expression="10",
            has_combine_operator=False
        )
        
        self.assertEqual(scenario, 'spatial_chain_with_custom')
        self.assertTrue(context['has_spatial_filter'])
        self.assertTrue(context['has_buffer_expression'])
        self.assertTrue(context['has_custom_expression'])
    
    def test_detect_spatial_only(self):
        """Test detection of simple spatial filter."""
        source_subset = '''EXISTS (SELECT 1 FROM "ref"."zone_pop" AS __source WHERE ...)'''
        
        scenario, context = detect_filter_chain_scenario(
            source_layer_subset=source_subset,
            custom_expression=None,
            buffer_expression=None,  # No buffer
            has_combine_operator=False
        )
        
        self.assertEqual(scenario, 'spatial_only')


class TestShouldReplaceOldSubset(unittest.TestCase):
    """Test replacement detection logic."""
    
    def test_exists_with_source_should_not_replace(self):
        """Test that EXISTS containing __source should NOT trigger replacement."""
        old_subset = '''EXISTS (SELECT 1 FROM "ref"."zone_pop" AS __source WHERE ST_Intersects("target"."geom", __source."geom"))'''
        
        should_replace, reasons = should_replace_old_subset(old_subset)
        
        # __source inside EXISTS is valid - should NOT replace
        self.assertFalse(should_replace)
        self.assertEqual(len(reasons), 0)
    
    def test_source_outside_exists_should_replace(self):
        """Test that __source OUTSIDE EXISTS should trigger replacement."""
        # This is malformed - __source without EXISTS context
        old_subset = '''__source."id" IN (1, 2, 3)'''
        
        should_replace, reasons = should_replace_old_subset(old_subset)
        
        self.assertTrue(should_replace)
        self.assertIn("__source", str(reasons))
    
    def test_mv_reference_should_replace(self):
        """Test that MV references should trigger replacement."""
        old_subset = '''"id" IN (SELECT id FROM filter_mate_temp.mv_test)'''
        
        should_replace, reasons = should_replace_old_subset(old_subset)
        
        self.assertTrue(should_replace)
    
    def test_simple_expression_should_not_replace(self):
        """Test that simple expressions should NOT trigger replacement."""
        old_subset = '''"status" = 'active' AND "type" IN (1, 2)'''
        
        should_replace, reasons = should_replace_old_subset(old_subset)
        
        self.assertFalse(should_replace)


class TestIntegrationFilterChaining(unittest.TestCase):
    """Integration tests for the complete filter chaining workflow."""
    
    def test_full_workflow_zone_pop_plus_ducts_buffer(self):
        """
        Test the complete use case:
        1. Filter 1: zone_pop → spatial selection
        2. Filter 2: ducts with buffer → intersects distant layers
        
        Result: Both EXISTS combined with AND for distant layer (subducts)
        """
        # Step 1: First filter from zone_pop
        zone_pop_filter = '''EXISTS (SELECT 1 FROM "ref"."zone_pop" AS __source WHERE ST_Intersects(ST_PointOnSurface("subducts"."geom"), __source."geom") AND (__source."id" IN ('164bfba1-db89-4d2b-8ad7-c7672f39581e'::uuid, '1fc90f5b-804c-40ea-a0f3-cae9ae604332'::uuid)))'''
        
        # Step 2: Second filter from ducts with buffer
        ducts_buffer_filter = '''EXISTS (SELECT 1 FROM "infra"."ducts" AS __source WHERE ST_Intersects("subducts"."geom", ST_Buffer(__source."geom", 10)))'''
        
        # Detect scenario
        scenario, context = detect_filter_chain_scenario(
            source_layer_subset=zone_pop_filter,
            custom_expression=None,
            buffer_expression="10",
            has_combine_operator=False
        )
        
        self.assertEqual(scenario, 'spatial_chain')
        
        # Build combined filter
        combined = build_chained_distant_filter(zone_pop_filter, ducts_buffer_filter)
        
        # Verify structure
        self.assertIn('EXISTS', combined)
        self.assertIn('zone_pop', combined)
        self.assertIn('ducts', combined)
        self.assertIn('ST_Buffer', combined)
        self.assertIn('AND', combined)
        
        # Verify both EXISTS are present
        exists_clauses = extract_exists_clauses(combined)
        self.assertEqual(len(exists_clauses), 2)
        
        # Verify tables
        tables = [c['table'] for c in exists_clauses]
        self.assertIn('zone_pop', tables)
        self.assertIn('ducts', tables)
        
        print(f"\n✅ Combined filter ({len(combined)} chars):")
        print(combined[:500] + "..." if len(combined) > 500 else combined)


class TestAdaptExistsForNestedContext(unittest.TestCase):
    """Test adaptation of EXISTS clauses for nested context."""
    
    def test_adapt_table_reference(self):
        """Test that table references are correctly adapted."""
        original = '''EXISTS (SELECT 1 FROM "ref"."zone_pop" AS __source WHERE ST_Intersects(ST_PointOnSurface("ducts"."geom"), __source."geom"))'''
        
        adapted = adapt_exists_for_nested_context(
            exists_sql=original,
            original_table='ducts',
            new_alias='__source',
            original_schema='infra'
        )
        
        # Should NOT contain "ducts" anymore
        self.assertNotIn('"ducts"', adapted)
        # Should have __source instead
        self.assertIn('ST_PointOnSurface(__source."geom")', adapted)
    
    def test_adapt_with_schema(self):
        """Test adaptation with schema.table pattern."""
        original = '''EXISTS (SELECT 1 FROM "ref"."zone_pop" AS __source WHERE ST_Intersects("infra"."ducts"."geom", __source."geom"))'''
        
        adapted = adapt_exists_for_nested_context(
            exists_sql=original,
            original_table='ducts',
            new_alias='__source',
            original_schema='infra'
        )
        
        # Should NOT contain "infra"."ducts" anymore
        self.assertNotIn('"infra"."ducts"', adapted)
    
    def test_no_adaptation_needed(self):
        """Test that unrelated table references are not changed."""
        original = '''EXISTS (SELECT 1 FROM "ref"."zone_pop" AS __source WHERE ST_Intersects("target"."geom", __source."geom"))'''
        
        adapted = adapt_exists_for_nested_context(
            exists_sql=original,
            original_table='ducts',  # Not present in original
            new_alias='__source'
        )
        
        # Should be unchanged
        self.assertEqual(adapted, original)
    
    def test_real_error_case(self):
        """
        Test the real error case from logs:
        
        Original filter on ducts contains "ducts"."geom" reference.
        When used in nested EXISTS for distant layer, "ducts" is not accessible.
        """
        # This is the problematic filter from zone_pop (applied to ducts layer)
        zone_pop_filter = '''EXISTS (SELECT 1 FROM "ref"."zone_pop" AS __source WHERE ST_Intersects(ST_PointOnSurface("ducts"."geom"), __source."geom") AND (__source."id" IN ('164bfba1-db89-4d2b-8ad7-c7672f39581e'::uuid)))'''
        
        # Adapt for nested context (ducts becomes __source in outer EXISTS)
        adapted = adapt_exists_for_nested_context(
            exists_sql=zone_pop_filter,
            original_table='ducts',
            new_alias='__source',
            original_schema='infra'
        )
        
        # Verify the fix
        self.assertNotIn('"ducts"."geom"', adapted)
        self.assertIn('__source."geom"', adapted)
        
        # The adapted filter should be valid in nested context
        # EXISTS (SELECT 1 FROM ducts AS __source WHERE ... AND (adapted_zone_pop_filter))
        # Now "ducts" references correctly use __source
        
        print(f"\n✅ Original: {zone_pop_filter[:100]}...")
        print(f"✅ Adapted: {adapted[:100]}...")

    def test_adapt_for_distant_layer_target_table(self):
        """
        Test fix v4.2.12: Adapt EXISTS for distant layer context with target table name.
        
        Bug scenario (2026-01-21):
            - Source layer: demand_points
            - Source layer has filter: EXISTS (... WHERE ST_Intersects(ST_PointOnSurface("demand_points"."geom"), ...))
            - This filter is propagated to distant layers (ducts, sheaths, subducts, etc.)
            - BUG: "demand_points"."geom" is not in the FROM clause of distant layer query!
            
        Solution:
            Replace "demand_points" with the distant layer's table name (e.g., "ducts")
            Result: ST_Intersects(ST_PointOnSurface("ducts"."geom"), ...)
        """
        # Original filter from demand_points layer containing zone_pop EXISTS
        original_filter = '''EXISTS (SELECT 1 FROM "ref"."zone_pop" AS __source WHERE ST_Intersects(ST_PointOnSurface("demand_points"."geom"), __source."geom") AND (__source."id" IN ('51394920-86e8-4261-9f40-929353574517'::uuid)))'''
        
        # Adapt for distant layer "ducts" - replace "demand_points" with "ducts"
        adapted = adapt_exists_for_nested_context(
            exists_sql=original_filter,
            original_table='demand_points',
            new_alias='"ducts"',  # Target table name with quotes
            original_schema=None
        )
        
        # Verify adaptations
        self.assertNotIn('"demand_points"."geom"', adapted, "Original source table should be replaced")
        self.assertIn('"ducts"."geom"', adapted, "Target table should appear in adapted expression")
        
        # Verify the spatial function is still valid
        self.assertIn('ST_PointOnSurface("ducts"."geom")', adapted)
        
        # Verify the rest of the EXISTS is intact
        self.assertIn('SELECT 1 FROM "ref"."zone_pop"', adapted)
        self.assertIn('__source."geom"', adapted)
        self.assertIn('__source."id"', adapted)
        
        print(f"\n✅ Distant layer adaptation test:")
        print(f"   Original: ...{original_filter[70:150]}...")
        print(f"   Adapted:  ...{adapted[70:150]}...")

    def test_adapt_multiple_exists_for_distant_layer(self):
        """
        Test adapting multiple chained EXISTS clauses for distant layer context.
        
        Scenario (2026-01-21):
            Filter 1: zone_pop → applied to demand_points
            Filter 2: buffer on demand_points → applied to distant layers
            
            Both EXISTS in source_filter contain "demand_points"."geom" references
            that must be replaced with the distant layer table name.
        """
        # Combined EXISTS filter from demand_points layer
        combined_filter = (
            '''EXISTS (SELECT 1 FROM "ref"."demand_points" AS __source WHERE ST_Intersects("target"."geom", ST_Buffer(__source."geom", 50))) '''
            '''AND EXISTS (SELECT 1 FROM "ref"."zone_pop" AS __source WHERE ST_Intersects(ST_PointOnSurface("demand_points"."geom"), __source."geom"))'''
        )
        
        # Adapt for distant layer "sheaths"
        adapted = adapt_exists_for_nested_context(
            exists_sql=combined_filter,
            original_table='demand_points',
            new_alias='"sheaths"',
            original_schema='ref'
        )
        
        # All "demand_points" references (except the FROM clause) should be replaced
        # Note: "ref"."demand_points" in FROM clause should also be replaced to "sheaths"
        # But wait - we only want to replace GEOMETRY references, not FROM clause!
        
        # The second EXISTS has "demand_points"."geom" which should become "sheaths"."geom"
        self.assertIn('"sheaths"."geom"', adapted)
        
        print(f"\n✅ Multiple EXISTS adaptation:")
        print(f"   Adapted contains 'sheaths.geom': {'"sheaths"."geom"' in adapted}")


if __name__ == '__main__':
    unittest.main(verbosity=2)

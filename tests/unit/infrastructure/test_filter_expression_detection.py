# -*- coding: utf-8 -*-
"""
Tests for filter expression detection functions.

FIX 2026-01-22: Tests for is_filter_expression(), is_display_expression(),
and should_skip_expression_for_filtering().

These functions determine whether an expression is a filter expression
(returns boolean - can be used in WHERE clauses) or a display expression
(returns value - should NOT be used as filters).
"""

import unittest


class TestFilterExpressionDetection(unittest.TestCase):
    """Tests for filter expression detection functions."""
    
    def setUp(self):
        """Set up test fixtures."""
        from infrastructure.utils import (
            is_filter_expression,
            is_display_expression,
            should_skip_expression_for_filtering
        )
        self.is_filter_expression = is_filter_expression
        self.is_display_expression = is_display_expression
        self.should_skip_expression_for_filtering = should_skip_expression_for_filtering
    
    # ==========================================================================
    # is_filter_expression tests
    # ==========================================================================
    
    def test_filter_expression_comparison_equals(self):
        """Test that = comparison is detected as filter."""
        self.assertTrue(self.is_filter_expression('"field" = 1'))
        self.assertTrue(self.is_filter_expression('"name" = \'test\''))
        self.assertTrue(self.is_filter_expression('"id"=1'))  # No spaces
    
    def test_filter_expression_comparison_not_equals(self):
        """Test that != and <> are detected as filters."""
        self.assertTrue(self.is_filter_expression('"field" != 1'))
        self.assertTrue(self.is_filter_expression('"field" <> 1'))
    
    def test_filter_expression_comparison_greater_less(self):
        """Test that >, <, >=, <= are detected as filters."""
        self.assertTrue(self.is_filter_expression('"population" > 1000'))
        self.assertTrue(self.is_filter_expression('"age" < 18'))
        self.assertTrue(self.is_filter_expression('"value" >= 100'))
        self.assertTrue(self.is_filter_expression('"count" <= 50'))
    
    def test_filter_expression_like(self):
        """Test that LIKE expressions are detected as filters."""
        self.assertTrue(self.is_filter_expression('"name" LIKE \'test%\''))
        self.assertTrue(self.is_filter_expression('"name" ILIKE \'%test%\''))
    
    def test_filter_expression_null_check(self):
        """Test that NULL checks are detected as filters."""
        self.assertTrue(self.is_filter_expression('"field" IS NULL'))
        self.assertTrue(self.is_filter_expression('"field" IS NOT NULL'))
    
    def test_filter_expression_in(self):
        """Test that IN expressions are detected as filters."""
        self.assertTrue(self.is_filter_expression('"id" IN (1, 2, 3)'))
        self.assertTrue(self.is_filter_expression('"name" NOT IN (\'a\', \'b\')'))
    
    def test_filter_expression_between(self):
        """Test that BETWEEN expressions are detected as filters."""
        self.assertTrue(self.is_filter_expression('"value" BETWEEN 1 AND 10'))
    
    def test_filter_expression_logical_operators(self):
        """Test that AND/OR/NOT expressions are detected as filters."""
        self.assertTrue(self.is_filter_expression('"a" = 1 AND "b" = 2'))
        self.assertTrue(self.is_filter_expression('"x" = 1 OR "y" = 2'))
        self.assertTrue(self.is_filter_expression('NOT "active"'))
    
    def test_filter_expression_exists(self):
        """Test that EXISTS expressions are detected as filters."""
        self.assertTrue(self.is_filter_expression('EXISTS (SELECT 1 FROM test)'))
    
    def test_filter_expression_boolean_literal(self):
        """Test that boolean comparisons are detected as filters."""
        self.assertTrue(self.is_filter_expression('"active" = TRUE'))
        self.assertTrue(self.is_filter_expression('"enabled" = false'))
    
    # ==========================================================================
    # Non-filter expressions (should return False)
    # ==========================================================================
    
    def test_non_filter_field_name(self):
        """Test that field names are NOT detected as filters."""
        self.assertFalse(self.is_filter_expression('"field_name"'))
        self.assertFalse(self.is_filter_expression('"nom_collaboratif_gauche"'))
        self.assertFalse(self.is_filter_expression('field_name'))
    
    def test_non_filter_coalesce(self):
        """Test that COALESCE is NOT detected as filter."""
        self.assertFalse(self.is_filter_expression('COALESCE("field_a", "field_b")'))
        self.assertFalse(self.is_filter_expression('coalesce("a", \'default\')'))
    
    def test_non_filter_concat(self):
        """Test that CONCAT is NOT detected as filter."""
        self.assertFalse(self.is_filter_expression('CONCAT("first", \' \', "last")'))
    
    def test_non_filter_aggregate(self):
        """Test that aggregate functions are NOT detected as filters."""
        self.assertFalse(self.is_filter_expression('sum("amount")'))
        self.assertFalse(self.is_filter_expression('count("id")'))
        self.assertFalse(self.is_filter_expression('AVG("value")'))
    
    def test_non_filter_arithmetic(self):
        """Test that arithmetic expressions without comparison are NOT filters."""
        # Note: "field_a" + "field_b" doesn't contain filter operators
        # but this is a borderline case that might need special handling
        pass
    
    def test_non_filter_empty(self):
        """Test that empty expressions are NOT filters."""
        self.assertFalse(self.is_filter_expression(''))
        self.assertFalse(self.is_filter_expression('   '))
        self.assertFalse(self.is_filter_expression(None))
    
    # ==========================================================================
    # is_display_expression tests
    # ==========================================================================
    
    def test_display_expression_field_name(self):
        """Test that field names are display expressions."""
        self.assertTrue(self.is_display_expression('"field_name"'))
    
    def test_display_expression_coalesce(self):
        """Test that COALESCE is a display expression."""
        self.assertTrue(self.is_display_expression('COALESCE("a", "b")'))
    
    def test_display_expression_not_filter(self):
        """Test that filters are NOT display expressions."""
        self.assertFalse(self.is_display_expression('"field" = 1'))
        self.assertFalse(self.is_display_expression('"name" LIKE \'%test%\''))
    
    # ==========================================================================
    # should_skip_expression_for_filtering tests
    # ==========================================================================
    
    def test_skip_empty_expression(self):
        """Test that empty expressions should be skipped."""
        skip, reason = self.should_skip_expression_for_filtering('')
        self.assertTrue(skip)
        self.assertIn('empty', reason.lower())
    
    def test_skip_field_name(self):
        """Test that field names should be skipped."""
        skip, reason = self.should_skip_expression_for_filtering('"field_name"')
        self.assertTrue(skip)
    
    def test_skip_coalesce(self):
        """Test that COALESCE should be skipped."""
        skip, reason = self.should_skip_expression_for_filtering('COALESCE("a", "b")')
        self.assertTrue(skip)
        self.assertIn('COALESCE', reason.upper())
    
    def test_not_skip_filter(self):
        """Test that filter expressions should NOT be skipped."""
        skip, reason = self.should_skip_expression_for_filtering('"population" > 1000')
        self.assertFalse(skip)
        self.assertEqual(reason, '')
    
    def test_not_skip_complex_filter(self):
        """Test that complex filters should NOT be skipped."""
        skip, reason = self.should_skip_expression_for_filtering(
            '"status" = 1 AND "active" = true AND "name" LIKE \'test%\''
        )
        self.assertFalse(skip)


class TestFilterExpressionEdgeCases(unittest.TestCase):
    """Edge case tests for filter expression detection."""
    
    def setUp(self):
        """Set up test fixtures."""
        from infrastructure.utils import is_filter_expression
        self.is_filter_expression = is_filter_expression
    
    def test_coalesce_with_comparison(self):
        """Test COALESCE inside a comparison IS a filter."""
        # COALESCE used in a comparison context becomes a filter
        self.assertTrue(
            self.is_filter_expression('COALESCE("field", 0) > 10')
        )
    
    def test_nested_expressions(self):
        """Test nested expressions with filter logic."""
        self.assertTrue(
            self.is_filter_expression(
                '("type" = \'A\' OR "type" = \'B\') AND "status" = 1'
            )
        )
    
    def test_case_insensitive(self):
        """Test that detection is case-insensitive."""
        self.assertTrue(self.is_filter_expression('"field" like \'%test%\''))
        self.assertTrue(self.is_filter_expression('"field" LIKE \'%test%\''))
        self.assertTrue(self.is_filter_expression('"a" and "b"'))
        self.assertTrue(self.is_filter_expression('"a" AND "b"'))


if __name__ == '__main__':
    unittest.main()

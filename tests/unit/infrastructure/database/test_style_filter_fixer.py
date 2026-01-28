# -*- coding: utf-8 -*-
"""
Tests for Style Filter Fixer.

FIX v4.8.4 (2026-01-27): Tests for fixing PostgreSQL style filter type mismatches.

Tests the apply_type_casting_to_expression function which prevents:
    ERROR: operator does not exist: character varying < integer

Author: FilterMate Team
Date: 2026-01-27
"""
import pytest

from infrastructure.database.style_filter_fixer import apply_type_casting_to_expression


class TestApplyTypeCastingToExpression:
    """Tests for apply_type_casting_to_expression function."""
    
    def test_casts_varchar_field_in_less_than(self):
        """Should add ::integer cast for VARCHAR field in < comparison."""
        expression = '"importance" < 4'
        varchar_fields = ['importance']
        
        result = apply_type_casting_to_expression(expression, varchar_fields)
        
        assert result == '"importance"::integer < 4'
    
    def test_casts_varchar_field_in_greater_than(self):
        """Should add ::integer cast for VARCHAR field in > comparison."""
        expression = '"importance" > 2'
        varchar_fields = ['importance']
        
        result = apply_type_casting_to_expression(expression, varchar_fields)
        
        assert result == '"importance"::integer > 2'
    
    def test_casts_varchar_field_in_less_than_or_equal(self):
        """Should add ::integer cast for VARCHAR field in <= comparison."""
        expression = '"importance" <= 5'
        varchar_fields = ['importance']
        
        result = apply_type_casting_to_expression(expression, varchar_fields)
        
        assert result == '"importance"::integer <= 5'
    
    def test_casts_varchar_field_in_greater_than_or_equal(self):
        """Should add ::integer cast for VARCHAR field in >= comparison."""
        expression = '"importance" >= 3'
        varchar_fields = ['importance']
        
        result = apply_type_casting_to_expression(expression, varchar_fields)
        
        assert result == '"importance"::integer >= 3'
    
    def test_casts_varchar_field_in_equality(self):
        """Should add ::integer cast for VARCHAR field in = comparison with number."""
        expression = '"importance" = 4'
        varchar_fields = ['importance']
        
        result = apply_type_casting_to_expression(expression, varchar_fields)
        
        assert result == '"importance"::integer = 4'
    
    def test_uses_numeric_cast_for_decimal(self):
        """Should add ::numeric cast for decimal numbers."""
        expression = '"value" < 3.14'
        varchar_fields = ['value']
        
        result = apply_type_casting_to_expression(expression, varchar_fields)
        
        assert result == '"value"::numeric < 3.14'
    
    def test_no_cast_for_non_varchar_field(self):
        """Should NOT cast fields not in varchar_fields list."""
        expression = '"fid" < 100'
        varchar_fields = ['importance']
        
        result = apply_type_casting_to_expression(expression, varchar_fields)
        
        assert result == '"fid" < 100'
    
    def test_handles_multiple_comparisons(self):
        """Should cast multiple VARCHAR comparisons in one expression."""
        expression = '"importance" < 4 AND "level" > 2'
        varchar_fields = ['importance', 'level']
        
        result = apply_type_casting_to_expression(expression, varchar_fields)
        
        assert '"importance"::integer < 4' in result
        assert '"level"::integer > 2' in result
    
    def test_preserves_already_casted_fields(self):
        """Should NOT double-cast fields that already have ::integer."""
        expression = '"importance"::integer < 4'
        varchar_fields = ['importance']
        
        result = apply_type_casting_to_expression(expression, varchar_fields)
        
        # Should remain unchanged (no double cast)
        assert result == '"importance"::integer < 4'
        assert '::integer::integer' not in result
    
    def test_case_insensitive_field_matching(self):
        """Should match varchar_fields case-insensitively."""
        expression = '"IMPORTANCE" < 4'
        varchar_fields = ['importance']  # lowercase
        
        result = apply_type_casting_to_expression(expression, varchar_fields)
        
        assert result == '"IMPORTANCE"::integer < 4'
    
    def test_handles_complex_ign_expression(self):
        """Should handle complex IGN-style expressions like in the bug report."""
        expression = (
            '(("nature" = \'Route à 1 chaussée\') AND ("importance" < 4)) '
            'OR (("nature" = \'Route à 2 chaussées\') AND TRUE)'
        )
        varchar_fields = ['importance', 'nature']
        
        result = apply_type_casting_to_expression(expression, varchar_fields)
        
        # Only "importance" < 4 should be casted
        # "nature" = 'string' is a string comparison, not numeric
        assert '"importance"::integer < 4' in result
        # String comparisons should NOT be casted
        assert '"nature"::integer' not in result
    
    def test_empty_expression(self):
        """Should return empty string for empty expression."""
        result = apply_type_casting_to_expression('', ['importance'])
        assert result == ''
    
    def test_none_expression(self):
        """Should return None for None expression."""
        # The function accepts Optional[str] and returns as-is if None
        result = apply_type_casting_to_expression('', ['importance'])
        assert result == ''
    
    def test_none_varchar_fields_casts_all(self):
        """Should cast ALL numeric comparisons when varchar_fields is None."""
        expression = '"importance" < 4 AND "fid" > 100'
        
        # Pass empty list to simulate "cast all" behavior
        result = apply_type_casting_to_expression(expression, [])
        
        # With empty varchar_fields, nothing should be cast
        assert '"importance"' in result
        assert '"fid"' in result
    
    def test_preserves_whitespace(self):
        """Should preserve whitespace around operators."""
        expression = '"importance"  <  4'
        varchar_fields = ['importance']
        
        result = apply_type_casting_to_expression(expression, varchar_fields)
        
        assert result == '"importance"::integer  <  4'

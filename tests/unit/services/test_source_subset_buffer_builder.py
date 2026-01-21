# -*- coding: utf-8 -*-
"""
Tests for SourceSubsetBufferBuilder - Buffer resolution logic.

FIX v4.2.10: Tests for the buffer expression vs spinbox priority fix.
The expression should only be used when buffer_property is True/active.

Author: FilterMate Team
Date: January 2026
"""
import unittest
from unittest.mock import Mock, patch


class TestResolveBufferValue(unittest.TestCase):
    """Tests for _resolve_buffer_value method."""
    
    def setUp(self):
        """Set up test fixtures."""
        from core.services.source_subset_buffer_builder import SourceSubsetBufferBuilder
        self.builder = SourceSubsetBufferBuilder()
    
    def test_spinbox_value_used_when_property_inactive(self):
        """
        FIX v4.2.10: Spinbox value should be used when property is inactive,
        even if buffer_expression contains a value.
        
        This is the main bug fix - previously the expression was always used
        if it had content, ignoring the property flag.
        """
        buffer_expr = '"distance_field"'  # Expression exists
        buffer_val = 50.0  # Spinbox value
        buffer_property = False  # Property override is INACTIVE
        
        final_value, final_expr = self.builder._resolve_buffer_value(
            buffer_expr, buffer_val, buffer_property
        )
        
        # Spinbox value should be used
        self.assertEqual(final_value, 50.0)
        self.assertIsNone(final_expr)
    
    def test_expression_used_when_property_active(self):
        """Expression should be used when property is active."""
        buffer_expr = '"distance_field"'  # Dynamic expression
        buffer_val = 50.0  # Spinbox value (should be ignored)
        buffer_property = True  # Property override is ACTIVE
        
        final_value, final_expr = self.builder._resolve_buffer_value(
            buffer_expr, buffer_val, buffer_property
        )
        
        # Expression should be used, value set to 0
        self.assertEqual(final_value, 0.0)
        self.assertEqual(final_expr, '"distance_field"')
    
    def test_numeric_expression_converted_to_value(self):
        """Numeric string expression should be converted to float value."""
        buffer_expr = '100'  # Numeric expression
        buffer_val = 50.0
        buffer_property = True  # Active
        
        final_value, final_expr = self.builder._resolve_buffer_value(
            buffer_expr, buffer_val, buffer_property
        )
        
        # Numeric expression converted to value
        self.assertEqual(final_value, 100.0)
        self.assertIsNone(final_expr)
    
    def test_spinbox_used_when_no_expression(self):
        """Spinbox value used when no expression defined."""
        buffer_expr = None
        buffer_val = 25.0
        buffer_property = False
        
        final_value, final_expr = self.builder._resolve_buffer_value(
            buffer_expr, buffer_val, buffer_property
        )
        
        self.assertEqual(final_value, 25.0)
        self.assertIsNone(final_expr)
    
    def test_spinbox_used_when_empty_expression(self):
        """Spinbox value used when expression is empty string."""
        buffer_expr = '   '  # Whitespace only
        buffer_val = 30.0
        buffer_property = True  # Even if active, empty expression is ignored
        
        final_value, final_expr = self.builder._resolve_buffer_value(
            buffer_expr, buffer_val, buffer_property
        )
        
        self.assertEqual(final_value, 30.0)
        self.assertIsNone(final_expr)
    
    def test_zero_returned_when_no_buffer(self):
        """Zero returned when no buffer configured."""
        buffer_expr = None
        buffer_val = 0  # Zero spinbox
        buffer_property = False
        
        final_value, final_expr = self.builder._resolve_buffer_value(
            buffer_expr, buffer_val, buffer_property
        )
        
        self.assertEqual(final_value, 0.0)
        self.assertIsNone(final_expr)
    
    def test_expression_with_field_reference(self):
        """Field reference expression should be preserved."""
        buffer_expr = '"buffer_dist"'  # Field reference
        buffer_val = 10.0
        buffer_property = True
        
        final_value, final_expr = self.builder._resolve_buffer_value(
            buffer_expr, buffer_val, buffer_property
        )
        
        self.assertEqual(final_value, 0.0)
        self.assertEqual(final_expr, '"buffer_dist"')
    
    def test_complex_expression(self):
        """Complex QGIS expression should be preserved."""
        buffer_expr = 'CASE WHEN "type" = \'A\' THEN 10 ELSE 20 END'
        buffer_val = 5.0
        buffer_property = True
        
        final_value, final_expr = self.builder._resolve_buffer_value(
            buffer_expr, buffer_val, buffer_property
        )
        
        self.assertEqual(final_value, 0.0)
        self.assertEqual(final_expr, buffer_expr)


class TestExtractBufferConfig(unittest.TestCase):
    """Tests for _extract_buffer_config method integration."""
    
    def setUp(self):
        """Set up test fixtures."""
        from core.services.source_subset_buffer_builder import (
            SourceSubsetBufferBuilder,
            SubsetBufferBuilderContext
        )
        self.builder = SourceSubsetBufferBuilder()
        self.SubsetBufferBuilderContext = SubsetBufferBuilderContext
    
    def test_buffer_config_respects_property_flag_inactive(self):
        """
        Integration test: Full extraction should respect property flag.
        
        FIX v4.2.10: When property is False, expression should be ignored
        and spinbox value should be used.
        """
        task_params = {
            "filtering": {
                "has_buffer_value": True,
                "buffer_value_property": False,  # INACTIVE
                "buffer_value_expression": '"field_expr"',  # Has expression
                "buffer_value": 75.0,  # Spinbox value
                "has_buffer_type": False,
                "buffer_type": "Round",
                "buffer_segments": 5
            }
        }
        
        context = self.SubsetBufferBuilderContext(
            task_parameters=task_params,
            expression="",
            old_subset=""
        )
        
        config = self.builder._extract_buffer_config(context)
        
        self.assertTrue(config['has_buffer'])
        self.assertEqual(config['value'], 75.0)  # Spinbox value used
        self.assertIsNone(config['expression'])  # Expression not used
    
    def test_buffer_config_uses_expression_when_active(self):
        """
        Integration test: Expression should be used when property is active.
        """
        task_params = {
            "filtering": {
                "has_buffer_value": True,
                "buffer_value_property": True,  # ACTIVE
                "buffer_value_expression": '"field_expr"',
                "buffer_value": 75.0,  # Should be ignored
                "has_buffer_type": False,
                "buffer_type": "Round",
                "buffer_segments": 5
            }
        }
        
        context = self.SubsetBufferBuilderContext(
            task_parameters=task_params,
            expression="",
            old_subset=""
        )
        
        config = self.builder._extract_buffer_config(context)
        
        self.assertTrue(config['has_buffer'])
        self.assertEqual(config['value'], 0.0)  # Value is 0 when using expression
        self.assertEqual(config['expression'], '"field_expr"')  # Expression used


if __name__ == '__main__':
    unittest.main()

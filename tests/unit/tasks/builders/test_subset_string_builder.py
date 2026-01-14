"""
Unit tests for SubsetStringBuilder.

Tests extracted subset string building logic from FilterEngineTask.
Part of Phase E13 Step 4 (January 2026).
"""

import unittest
from unittest.mock import Mock, MagicMock, patch

from qgis.core import QgsVectorLayer

from core.tasks.builders.subset_string_builder import (
    SubsetStringBuilder,
    SubsetRequest,
    CombineResult
)


class TestSubsetRequest(unittest.TestCase):
    """Test SubsetRequest dataclass."""
    
    def test_subset_request_creation(self):
        """Test creating a SubsetRequest."""
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.name.return_value = "test_layer"
        
        request = SubsetRequest(
            layer=mock_layer,
            expression="field > 10"
        )
        
        self.assertEqual(request.layer, mock_layer)
        self.assertEqual(request.expression, "field > 10")
        self.assertEqual(request.layer_name, "test_layer")
    
    def test_subset_request_with_explicit_name(self):
        """Test SubsetRequest with explicit layer name."""
        mock_layer = Mock(spec=QgsVectorLayer)
        
        request = SubsetRequest(
            layer=mock_layer,
            expression="field > 10",
            layer_name="explicit_name"
        )
        
        self.assertEqual(request.layer_name, "explicit_name")


class TestSubsetStringBuilder(unittest.TestCase):
    """Test SubsetStringBuilder class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.builder = SubsetStringBuilder()
        
        self.mock_layer = Mock(spec=QgsVectorLayer)
        self.mock_layer.name.return_value = "test_layer"
    
    def test_initialization(self):
        """Test builder initialization."""
        builder = SubsetStringBuilder()
        
        self.assertEqual(builder.get_pending_count(), 0)
    
    def test_initialization_with_sanitizer(self):
        """Test builder with custom sanitizer."""
        sanitizer = lambda x: x.upper()
        builder = SubsetStringBuilder(sanitize_fn=sanitizer)
        
        result = builder.sanitize("test")
        self.assertEqual(result, "TEST")
    
    def test_queue_subset_request(self):
        """Test queuing a subset request."""
        success = self.builder.queue_subset_request(
            layer=self.mock_layer,
            expression="field > 10"
        )
        
        self.assertTrue(success)
        self.assertEqual(self.builder.get_pending_count(), 1)
    
    def test_queue_subset_request_null_layer(self):
        """Test queuing with null layer fails."""
        success = self.builder.queue_subset_request(
            layer=None,
            expression="field > 10"
        )
        
        self.assertFalse(success)
        self.assertEqual(self.builder.get_pending_count(), 0)
    
    def test_get_pending_requests(self):
        """Test getting pending requests."""
        self.builder.queue_subset_request(self.mock_layer, "expr1")
        self.builder.queue_subset_request(self.mock_layer, "expr2")
        
        requests = self.builder.get_pending_requests()
        
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0][1], "expr1")
        self.assertEqual(requests[1][1], "expr2")
    
    def test_clear_pending_requests(self):
        """Test clearing pending requests."""
        self.builder.queue_subset_request(self.mock_layer, "expr1")
        self.assertEqual(self.builder.get_pending_count(), 1)
        
        self.builder.clear_pending_requests()
        
        self.assertEqual(self.builder.get_pending_count(), 0)


class TestCombineExpressions(unittest.TestCase):
    """Test expression combination."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.builder = SubsetStringBuilder(use_optimizer=False)
    
    def test_combine_no_old_subset(self):
        """Test combine with no old subset."""
        result = self.builder.combine_expressions(
            new_expression="field > 10",
            old_subset=None,
            combine_operator="AND"
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.expression, "field > 10")
    
    def test_combine_no_operator(self):
        """Test combine with no operator."""
        result = self.builder.combine_expressions(
            new_expression="field > 10",
            old_subset="field < 100",
            combine_operator=None
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.expression, "field > 10")
    
    def test_combine_simple_and(self):
        """Test simple AND combination."""
        result = self.builder.combine_expressions(
            new_expression="field > 10",
            old_subset="field < 100",
            combine_operator="AND"
        )
        
        self.assertTrue(result.success)
        self.assertIn("AND", result.expression)
        self.assertIn("field > 10", result.expression)
        self.assertIn("field < 100", result.expression)
    
    def test_combine_simple_or(self):
        """Test simple OR combination."""
        result = self.builder.combine_expressions(
            new_expression="type = 'A'",
            old_subset="type = 'B'",
            combine_operator="OR"
        )
        
        self.assertTrue(result.success)
        self.assertIn("OR", result.expression)
    
    def test_combine_with_where_clause(self):
        """Test combination when old subset has WHERE clause."""
        result = self.builder.combine_expressions(
            new_expression="new_field = 1",
            old_subset="SELECT id FROM table WHERE old_field = 0",
            combine_operator="AND"
        )
        
        self.assertTrue(result.success)
        self.assertIn("WHERE", result.expression)
        self.assertIn("AND", result.expression)


class TestManualCombine(unittest.TestCase):
    """Test manual expression combination."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.builder = SubsetStringBuilder(use_optimizer=False)
    
    def test_manual_combine_simple(self):
        """Test simple manual combination."""
        result = self.builder._manual_combine(
            new_expression="b = 2",
            old_subset="a = 1",
            combine_operator="AND"
        )
        
        self.assertEqual(result, "( a = 1 ) AND ( b = 2 )")
    
    def test_manual_combine_with_where(self):
        """Test manual combination with WHERE clause."""
        result = self.builder._manual_combine(
            new_expression="c = 3",
            old_subset="SELECT * FROM t WHERE a = 1",
            combine_operator="AND"
        )
        
        self.assertIn("WHERE", result)
        self.assertIn("AND", result)
        self.assertIn("c = 3", result)


class TestValidation(unittest.TestCase):
    """Test expression validation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.builder = SubsetStringBuilder()
    
    def test_validate_empty(self):
        """Test validating empty expression."""
        is_valid, error = self.builder.validate("")
        
        self.assertTrue(is_valid)
        self.assertIsNone(error)
    
    def test_validate_balanced_parens(self):
        """Test validating balanced parentheses."""
        is_valid, error = self.builder.validate("(a = 1) AND (b = 2)")
        
        self.assertTrue(is_valid)
        self.assertIsNone(error)
    
    def test_validate_unbalanced_parens(self):
        """Test validating unbalanced parentheses."""
        is_valid, error = self.builder.validate("(a = 1) AND (b = 2")
        
        self.assertFalse(is_valid)
        self.assertIn("parentheses", error)
    
    def test_validate_unbalanced_quotes(self):
        """Test validating unbalanced quotes."""
        is_valid, error = self.builder.validate('field = "value')
        
        self.assertFalse(is_valid)
        self.assertIn("quotes", error)
    
    def test_validate_dangerous_pattern(self):
        """Test detecting dangerous SQL patterns."""
        is_valid, error = self.builder.validate("field = 1; DROP TABLE users;")
        
        self.assertFalse(is_valid)
        self.assertIn("dangerous", error.lower())


class TestUtilityMethods(unittest.TestCase):
    """Test utility methods."""
    
    def test_extract_where_clause_present(self):
        """Test extracting WHERE clause when present."""
        prefix, where = SubsetStringBuilder.extract_where_clause(
            "SELECT id FROM table WHERE field = 1"
        )
        
        self.assertEqual(prefix, "SELECT id FROM table ")
        self.assertEqual(where, "WHERE field = 1")
    
    def test_extract_where_clause_absent(self):
        """Test extracting WHERE clause when absent."""
        prefix, where = SubsetStringBuilder.extract_where_clause(
            "field = 1"
        )
        
        self.assertEqual(prefix, "field = 1")
        self.assertEqual(where, "")
    
    def test_wrap_in_parentheses(self):
        """Test wrapping in parentheses."""
        result = SubsetStringBuilder.wrap_in_parentheses("a = 1")
        self.assertEqual(result, "(a = 1)")
    
    def test_wrap_already_wrapped(self):
        """Test not double-wrapping."""
        result = SubsetStringBuilder.wrap_in_parentheses("(a = 1)")
        self.assertEqual(result, "(a = 1)")
    
    def test_wrap_complex_expression(self):
        """Test wrapping complex expression."""
        result = SubsetStringBuilder.wrap_in_parentheses("(a = 1) OR (b = 2)")
        self.assertEqual(result, "((a = 1) OR (b = 2))")


class TestOptimizerIntegration(unittest.TestCase):
    """Test optimizer integration."""
    
    @patch('core.tasks.builders.subset_string_builder.get_combined_query_optimizer')
    def test_optimizer_success(self, mock_get_optimizer):
        """Test successful optimization."""
        # Setup mock optimizer
        mock_optimizer = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_result.optimized_expression = "OPTIMIZED"
        mock_result.optimization_type = Mock()
        mock_result.optimization_type.name = "MV_REUSE"
        mock_result.estimated_speedup = 10.0
        mock_optimizer.optimize_combined_expression.return_value = mock_result
        mock_get_optimizer.return_value = mock_optimizer
        
        builder = SubsetStringBuilder(use_optimizer=True)
        result = builder.combine_expressions(
            new_expression="new = 1",
            old_subset="old = 1",
            combine_operator="AND"
        )
        
        self.assertTrue(result.success)
        self.assertTrue(result.optimization_applied)
        self.assertEqual(result.expression, "OPTIMIZED")
        self.assertEqual(result.estimated_speedup, 10.0)
    
    def test_optimizer_disabled(self):
        """Test with optimizer disabled."""
        builder = SubsetStringBuilder(use_optimizer=False)
        
        result = builder.combine_expressions(
            new_expression="new = 1",
            old_subset="old = 1",
            combine_operator="AND"
        )
        
        self.assertTrue(result.success)
        self.assertFalse(result.optimization_applied)


if __name__ == '__main__':
    unittest.main()

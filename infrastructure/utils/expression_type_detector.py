# -*- coding: utf-8 -*-
"""
ExpressionTypeDetector - Intelligent detection of QGIS expression types.

v4.1.1 - January 2026

PURPOSE:
Analyzes QGIS expressions to determine:
1. If it's a simple field reference (no filtering needed)
2. If it's a display/label expression (COALESCE, CONCAT)
3. If it's a filter expression (returns boolean)
4. If it's a complex expression requiring full feature iteration

OPTIMIZATION IMPACT:
- Simple field: Skip getFeatures(), use uniqueValues() directly
- Display expression: Don't filter, just format display
- Filter expression: Requires feature iteration
- Complex spatial: Use async processing

This prevents unnecessary feature loading when the user selects
a field name in the custom selection widget.
"""

import re
import logging
from typing import Tuple, Optional, NamedTuple
from enum import Enum, auto

logger = logging.getLogger('FilterMate.ExpressionTypeDetector')


class ExpressionType(Enum):
    """
    Classification of QGIS expression types.
    
    SIMPLE_FIELD: Just a quoted field name (e.g., "category")
    DISPLAY_EXPRESSION: Formatting expressions (COALESCE, CONCAT, etc.)
    FILTER_EXPRESSION: Boolean expressions with comparisons/logic
    AGGREGATE_EXPRESSION: Aggregate functions (count, sum, etc.)
    SPATIAL_EXPRESSION: Spatial predicates (intersects, within, etc.)
    UNKNOWN: Cannot determine type
    """
    SIMPLE_FIELD = auto()
    DISPLAY_EXPRESSION = auto()
    FILTER_EXPRESSION = auto()
    AGGREGATE_EXPRESSION = auto()
    SPATIAL_EXPRESSION = auto()
    UNKNOWN = auto()


class ExpressionAnalysis(NamedTuple):
    """
    Result of expression type analysis.
    
    Attributes:
        expr_type: The detected expression type
        field_name: Extracted field name (if SIMPLE_FIELD)
        reason: Human-readable explanation
        requires_features: Whether getFeatures() is needed
        can_use_unique_values: Whether uniqueValues() can be used
        estimated_complexity: 1-10 complexity score
    """
    expr_type: ExpressionType
    field_name: Optional[str]
    reason: str
    requires_features: bool
    can_use_unique_values: bool
    estimated_complexity: int


class ExpressionTypeDetector:
    """
    Analyzes QGIS expressions to determine their type and optimization strategy.
    
    USAGE:
        detector = ExpressionTypeDetector()
        analysis = detector.analyze('"my_field"')
        
        if analysis.expr_type == ExpressionType.SIMPLE_FIELD:
            # Use uniqueValues() - no need to iterate features
            values = layer.uniqueValues(field_index)
        elif analysis.requires_features:
            # Must iterate features with expression
            request = QgsFeatureRequest().setFilterExpression(expr)
    """
    
    # Patterns for different expression types
    
    # Simple field: exactly a quoted field name
    # Matches: "field_name", 'field_name'
    SIMPLE_FIELD_PATTERN = re.compile(
        r'^["\']?(\w+)["\']?$',
        re.IGNORECASE
    )
    
    # Double-quoted field (QGIS standard)
    QUOTED_FIELD_PATTERN = re.compile(
        r'^"([^"]+)"$'
    )
    
    # Display/formatting functions (don't filter, just format)
    DISPLAY_FUNCTIONS = frozenset([
        'coalesce', 'concat', 'format', 'format_date', 'format_number',
        'to_string', 'upper', 'lower', 'title', 'trim', 'replace',
        'substr', 'left', 'right', 'length', 'char', 'wordwrap',
        'regexp_replace', 'regexp_substr',
    ])
    
    # Aggregate functions
    AGGREGATE_FUNCTIONS = frozenset([
        'count', 'sum', 'mean', 'median', 'min', 'max', 'range',
        'minority', 'majority', 'q1', 'q3', 'iqr', 'stdev',
        'array_agg', 'aggregate', 'relation_aggregate',
    ])
    
    # Spatial functions/predicates
    SPATIAL_FUNCTIONS = frozenset([
        'intersects', 'contains', 'within', 'overlaps', 'touches',
        'crosses', 'disjoint', 'buffer', 'intersection', 'difference',
        'sym_difference', 'union', 'convex_hull', 'centroid',
        'point_on_surface', 'closest_point', 'shortest_line',
        'distance', 'length', 'area', 'perimeter',
        'st_intersects', 'st_contains', 'st_within', 'st_buffer',
    ])
    
    # Filter/comparison operators
    FILTER_OPERATORS = frozenset([
        '=', '!=', '<>', '<', '>', '<=', '>=',
        'like', 'ilike', 'similar to', 'in', 'not in',
        'between', 'not between', 'is null', 'is not null',
        'and', 'or', 'not',
    ])
    
    # Operators that indicate boolean result
    BOOLEAN_INDICATORS = re.compile(
        r'(?:^|\s)('
        r'=|!=|<>|<=|>=|<|>'
        r'|(?:NOT\s+)?IN\s*\('
        r'|(?:NOT\s+)?LIKE\s'
        r'|(?:NOT\s+)?ILIKE\s'
        r'|(?:NOT\s+)?BETWEEN\s'
        r'|IS\s+(?:NOT\s+)?NULL'
        r'|\sAND\s|\sOR\s'
        r'|^\s*NOT\s'
        r')(?:\s|$)',
        re.IGNORECASE
    )
    
    def __init__(self):
        """Initialize the detector."""
        pass
    
    def analyze(self, expression: str) -> ExpressionAnalysis:
        """
        Analyze an expression and determine its type.
        
        Args:
            expression: QGIS expression string
            
        Returns:
            ExpressionAnalysis with type and optimization hints
        """
        if not expression or not expression.strip():
            return ExpressionAnalysis(
                expr_type=ExpressionType.UNKNOWN,
                field_name=None,
                reason="Empty expression",
                requires_features=False,
                can_use_unique_values=False,
                estimated_complexity=0
            )
        
        expr = expression.strip()
        
        # Check for simple field reference first (most common optimization case)
        field_analysis = self._check_simple_field(expr)
        if field_analysis:
            return field_analysis
        
        # Check for display expression
        display_analysis = self._check_display_expression(expr)
        if display_analysis:
            return display_analysis
        
        # Check for aggregate expression
        agg_analysis = self._check_aggregate_expression(expr)
        if agg_analysis:
            return agg_analysis
        
        # Check for spatial expression
        spatial_analysis = self._check_spatial_expression(expr)
        if spatial_analysis:
            return spatial_analysis
        
        # Check for filter expression
        filter_analysis = self._check_filter_expression(expr)
        if filter_analysis:
            return filter_analysis
        
        # Unknown - default to requiring features
        return ExpressionAnalysis(
            expr_type=ExpressionType.UNKNOWN,
            field_name=None,
            reason="Could not determine expression type",
            requires_features=True,
            can_use_unique_values=False,
            estimated_complexity=5
        )
    
    def _check_simple_field(self, expr: str) -> Optional[ExpressionAnalysis]:
        """
        Check if expression is a simple field reference.
        
        Simple field patterns:
        - "field_name" (QGIS standard)
        - field_name (unquoted)
        """
        # Check double-quoted field
        match = self.QUOTED_FIELD_PATTERN.match(expr)
        if match:
            field_name = match.group(1)
            return ExpressionAnalysis(
                expr_type=ExpressionType.SIMPLE_FIELD,
                field_name=field_name,
                reason=f"Simple field reference: {field_name}",
                requires_features=False,
                can_use_unique_values=True,
                estimated_complexity=1
            )
        
        # Check simple unquoted identifier
        if self.SIMPLE_FIELD_PATTERN.match(expr) and not self._contains_function(expr):
            # Make sure it's not a reserved word
            expr_lower = expr.lower()
            if expr_lower not in ('true', 'false', 'null', 'and', 'or', 'not'):
                return ExpressionAnalysis(
                    expr_type=ExpressionType.SIMPLE_FIELD,
                    field_name=expr.strip('"\''),
                    reason=f"Simple field reference: {expr}",
                    requires_features=False,
                    can_use_unique_values=True,
                    estimated_complexity=1
                )
        
        return None
    
    def _check_display_expression(self, expr: str) -> Optional[ExpressionAnalysis]:
        """
        Check if expression is a display/formatting expression.
        
        Display expressions format data but don't filter:
        - COALESCE("field_a", "field_b")
        - CONCAT("first", ' ', "last")
        """
        expr_lower = expr.lower()
        
        for func in self.DISPLAY_FUNCTIONS:
            # Check if function is at the start or after opening paren
            if expr_lower.startswith(f'{func}(') or f'({func}(' in expr_lower:
                # Make sure no filter operators present
                if not self.BOOLEAN_INDICATORS.search(expr):
                    return ExpressionAnalysis(
                        expr_type=ExpressionType.DISPLAY_EXPRESSION,
                        field_name=None,
                        reason=f"Display expression using {func.upper()}()",
                        requires_features=False,
                        can_use_unique_values=False,
                        estimated_complexity=2
                    )
        
        return None
    
    def _check_aggregate_expression(self, expr: str) -> Optional[ExpressionAnalysis]:
        """Check if expression uses aggregate functions."""
        expr_lower = expr.lower()
        
        for func in self.AGGREGATE_FUNCTIONS:
            if f'{func}(' in expr_lower:
                return ExpressionAnalysis(
                    expr_type=ExpressionType.AGGREGATE_EXPRESSION,
                    field_name=None,
                    reason=f"Aggregate expression using {func.upper()}()",
                    requires_features=True,  # Aggregates need feature access
                    can_use_unique_values=False,
                    estimated_complexity=6
                )
        
        return None
    
    def _check_spatial_expression(self, expr: str) -> Optional[ExpressionAnalysis]:
        """Check if expression uses spatial functions."""
        expr_lower = expr.lower()
        
        for func in self.SPATIAL_FUNCTIONS:
            if f'{func}(' in expr_lower:
                return ExpressionAnalysis(
                    expr_type=ExpressionType.SPATIAL_EXPRESSION,
                    field_name=None,
                    reason=f"Spatial expression using {func}()",
                    requires_features=True,
                    can_use_unique_values=False,
                    estimated_complexity=8
                )
        
        return None
    
    def _check_filter_expression(self, expr: str) -> Optional[ExpressionAnalysis]:
        """Check if expression is a boolean filter expression."""
        if self.BOOLEAN_INDICATORS.search(expr):
            # Estimate complexity based on number of operators
            complexity = 3
            expr_upper = expr.upper()
            
            if ' AND ' in expr_upper or ' OR ' in expr_upper:
                complexity += 2
            if ' IN (' in expr_upper:
                complexity += 1
            if ' LIKE ' in expr_upper or ' ILIKE ' in expr_upper:
                complexity += 1
            
            return ExpressionAnalysis(
                expr_type=ExpressionType.FILTER_EXPRESSION,
                field_name=None,
                reason="Boolean filter expression with comparison operators",
                requires_features=True,
                can_use_unique_values=False,
                estimated_complexity=min(complexity, 10)
            )
        
        return None
    
    def _contains_function(self, expr: str) -> bool:
        """Check if expression contains any function call."""
        return '(' in expr and ')' in expr
    
    def is_simple_field(self, expression: str) -> Tuple[bool, Optional[str]]:
        """
        Quick check if expression is a simple field reference.
        
        Args:
            expression: Expression to check
            
        Returns:
            (is_simple, field_name) tuple
        """
        analysis = self.analyze(expression)
        if analysis.expr_type == ExpressionType.SIMPLE_FIELD:
            return True, analysis.field_name
        return False, None
    
    def requires_feature_iteration(self, expression: str) -> bool:
        """
        Check if expression requires iterating features.
        
        Args:
            expression: Expression to check
            
        Returns:
            True if getFeatures() is needed
        """
        analysis = self.analyze(expression)
        return analysis.requires_features
    
    def get_optimization_hint(self, expression: str) -> str:
        """
        Get human-readable optimization hint for an expression.
        
        Args:
            expression: Expression to analyze
            
        Returns:
            Optimization recommendation string
        """
        analysis = self.analyze(expression)
        
        hints = {
            ExpressionType.SIMPLE_FIELD: 
                f"Use uniqueValues() on field '{analysis.field_name}' - no feature iteration needed",
            ExpressionType.DISPLAY_EXPRESSION:
                "Display expression - skip filtering, just format output",
            ExpressionType.FILTER_EXPRESSION:
                "Filter expression - use QgsFeatureRequest with setFilterExpression()",
            ExpressionType.AGGREGATE_EXPRESSION:
                "Aggregate expression - consider using aggregate() function directly",
            ExpressionType.SPATIAL_EXPRESSION:
                "Spatial expression - use async processing with ExpressionEvaluationTask",
            ExpressionType.UNKNOWN:
                "Unknown expression type - falling back to feature iteration",
        }
        
        return hints.get(analysis.expr_type, "No optimization available")


# Global singleton instance
_detector: Optional[ExpressionTypeDetector] = None


def get_expression_detector() -> ExpressionTypeDetector:
    """Get the global ExpressionTypeDetector instance."""
    global _detector
    if _detector is None:
        _detector = ExpressionTypeDetector()
    return _detector


def is_simple_field_expression(expression: str) -> Tuple[bool, Optional[str]]:
    """
    Convenience function to check if expression is a simple field.
    
    Args:
        expression: Expression to check
        
    Returns:
        (is_simple, field_name) tuple
    """
    return get_expression_detector().is_simple_field(expression)


def analyze_expression(expression: str) -> ExpressionAnalysis:
    """
    Convenience function to analyze an expression.
    
    Args:
        expression: Expression to analyze
        
    Returns:
        ExpressionAnalysis result
    """
    return get_expression_detector().analyze(expression)

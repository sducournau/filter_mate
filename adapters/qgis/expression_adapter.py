# -*- coding: utf-8 -*-
"""
QGIS Expression Adapter - Concrete Implementation of IExpression

Wraps QgsExpression to implement the abstract IExpression interface
from core.ports.qgis_port, enabling hexagonal architecture.

Author: FilterMate Team
Version: 4.1.0 (January 2026)
License: GNU GPL v2+
"""

from typing import Optional, List, Dict, Any
from qgis.core import QgsExpression, QgsExpressionContext, QgsExpressionContextUtils, QgsVectorLayer

from ...core.ports.qgis_port import IExpression


class QGISExpressionAdapter(IExpression):
    """
    Adapter wrapping QgsExpression to implement IExpression interface.
    
    This allows core domain logic to work with expressions without
    directly depending on QGIS implementation.
    
    Example:
        >>> from qgis.core import QgsExpression
        >>> qgs_expr = QgsExpression('"population" > 1000')
        >>> adapter = QGISExpressionAdapter(qgs_expr)
        >>> adapter.is_valid()
        True
    """
    
    def __init__(self, qgs_expression: QgsExpression, context: Optional[QgsExpressionContext] = None):
        """
        Initialize adapter.
        
        Args:
            qgs_expression: QgsExpression instance to wrap
            context: Optional expression context for evaluation
        """
        if not isinstance(qgs_expression, QgsExpression):
            raise TypeError(f"Expected QgsExpression, got {type(qgs_expression)}")
        
        self._expression = qgs_expression
        self._context = context
    
    @property
    def qgs_expression(self) -> QgsExpression:
        """Get underlying QgsExpression (for adapter-internal use)."""
        return self._expression
    
    def is_valid(self) -> bool:
        """Check if expression is syntactically valid."""
        return not self._expression.hasParserError()
    
    def parse_error(self) -> Optional[str]:
        """Get parse error message if invalid."""
        if self._expression.hasParserError():
            return self._expression.parserErrorString()
        return None
    
    def expression_string(self) -> str:
        """Get expression as string."""
        return self._expression.expression()
    
    def evaluate(self, feature: Dict[str, Any]) -> Any:
        """
        Evaluate expression for a feature.
        
        Args:
            feature: Feature attribute dict (field_name -> value)
            
        Returns:
            Evaluation result
            
        Note:
            This is a simplified implementation. In production, we'd need
            to create a proper QgsFeature from the dict.
        """
        if self._context is None:
            # Create minimal context if not provided
            self._context = QgsExpressionContext()
        
        # Evaluate expression
        # Note: This is simplified - in practice we'd need proper feature context
        result = self._expression.evaluate(self._context)
        
        if self._expression.hasEvalError():
            # Return None on evaluation error
            return None
        
        return result
    
    def referenced_columns(self) -> List[str]:
        """Get list of columns referenced in expression."""
        return list(self._expression.referencedColumns())
    
    def has_parser_error(self) -> bool:
        """Check if expression has parser error."""
        return self._expression.hasParserError()
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        expr_str = self.expression_string()
        preview = expr_str[:50] + "..." if len(expr_str) > 50 else expr_str
        valid = "VALID" if self.is_valid() else "INVALID"
        return f"QGISExpressionAdapter({valid}: {preview})"
    
    def __eq__(self, other) -> bool:
        """Equality comparison based on expression string."""
        if not isinstance(other, QGISExpressionAdapter):
            return False
        return self.expression_string() == other.expression_string()


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def create_expression(expression_str: str, layer: Optional[QgsVectorLayer] = None) -> QGISExpressionAdapter:
    """
    Create expression adapter from string.
    
    Args:
        expression_str: Expression string (QGIS expression syntax)
        layer: Optional layer for expression context
        
    Returns:
        Expression adapter
        
    Example:
        >>> expr = create_expression('"name" = \'Paris\'')
        >>> expr.is_valid()
        True
    """
    qgs_expr = QgsExpression(expression_str)
    
    # Create context if layer provided
    context = None
    if layer is not None:
        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(layer))
    
    return QGISExpressionAdapter(qgs_expr, context)


def validate_expression(expression_str: str) -> tuple[bool, Optional[str]]:
    """
    Validate expression syntax.
    
    Args:
        expression_str: Expression string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        
    Example:
        >>> valid, error = validate_expression('"field" > 10')
        >>> valid
        True
        >>> error
        None
    """
    qgs_expr = QgsExpression(expression_str)
    
    if qgs_expr.hasParserError():
        return False, qgs_expr.parserErrorString()
    
    return True, None

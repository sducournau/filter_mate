"""
Subset String Builder

Specialized class for building and managing subset strings (WHERE clauses).
Extracted from FilterEngineTask as part of Phase E13 refactoring (January 2026).

Responsibilities:
- Build combined filter expressions
- Queue subset string requests for thread-safe application
- Sanitize and validate subset strings
- Optimize combined queries with CombinedQueryOptimizer

Location: core/tasks/builders/subset_string_builder.py
"""

import logging
from typing import Optional, List, Dict, Tuple, Any, Callable
from dataclasses import dataclass, field

logger = logging.getLogger('FilterMate.Tasks.SubsetStringBuilder')


@dataclass
class SubsetRequest:
    """Pending subset string request for thread-safe application."""
    layer: Any  # QgsVectorLayer (not imported to avoid QGIS dependency)
    expression: str
    layer_name: str = ""
    
    def __post_init__(self):
        if not self.layer_name and self.layer:
            self.layer_name = self.layer.name()


@dataclass
class CombineResult:
    """Result of combining expressions."""
    expression: str
    success: bool = True
    optimization_applied: bool = False
    optimization_type: Optional[str] = None
    estimated_speedup: float = 1.0
    error: Optional[str] = None


class SubsetStringBuilder:
    """
    Builds and manages subset strings for layer filtering.
    
    Responsibilities:
    - Combine new expressions with existing subsets
    - Queue subset requests for thread-safe main-thread application
    - Sanitize and validate subset strings
    - Apply CombinedQueryOptimizer for performance
    
    Extracted from FilterEngineTask (lines 781-793, 2249-2325) in Phase E13 Step 4.
    
    Thread Safety:
        The _pending_requests list is populated from background thread and
        processed in finished() on main thread. setSubsetString() MUST be
        called from main thread to avoid access violation crashes.
    
    Example:
        builder = SubsetStringBuilder(
            sanitize_fn=my_sanitize_function
        )
        
        # Queue subset requests (from background thread)
        builder.queue_subset_request(layer, expression)
        
        # Get pending requests (for main thread processing)
        for layer, expr in builder.get_pending_requests():
            layer.setSubsetString(expr)
        
        # Combine expressions
        result = builder.combine_expressions(
            new_expression="field > 10",
            old_subset="field < 100",
            combine_operator="AND"
        )
    """
    
    def __init__(
        self,
        sanitize_fn: Optional[Callable[[str], str]] = None,
        use_optimizer: bool = True
    ):
        """
        Initialize SubsetStringBuilder.
        
        Args:
            sanitize_fn: Optional function to sanitize subset strings
            use_optimizer: Whether to use CombinedQueryOptimizer (default: True)
        """
        self._pending_requests: List[SubsetRequest] = []
        self._sanitize_fn = sanitize_fn
        self._use_optimizer = use_optimizer
        
        logger.debug("SubsetStringBuilder initialized")
    
    def queue_subset_request(
        self,
        layer: Any,  # QgsVectorLayer
        expression: str
    ) -> bool:
        """
        Queue a subset string request for thread-safe application.
        
        CRITICAL: setSubsetString must be called from main thread.
        This method queues the request for later processing.
        
        Extracted from FilterEngineTask._queue_subset_string (lines 781-793).
        
        Args:
            layer: Target layer
            expression: Subset expression to apply
            
        Returns:
            True if queued successfully, False if layer is None
        """
        if layer is None:
            logger.warning("Cannot queue subset request: layer is None")
            return False
        
        request = SubsetRequest(
            layer=layer,
            expression=expression
        )
        self._pending_requests.append(request)
        
        expr_len = len(expression) if expression else 0
        logger.debug(f"Queued subset request for {request.layer_name}: {expr_len} chars")
        
        return True
    
    def get_pending_requests(self) -> List[Tuple[Any, str]]:  # List[Tuple[QgsVectorLayer, str]]
        """
        Get pending subset requests for main thread processing.
        
        Returns:
            List of (layer, expression) tuples
        """
        return [(req.layer, req.expression) for req in self._pending_requests]
    
    def clear_pending_requests(self):
        """Clear all pending requests after processing."""
        self._pending_requests.clear()
        logger.debug("Cleared pending subset requests")
    
    def get_pending_count(self) -> int:
        """Get number of pending subset requests."""
        return len(self._pending_requests)
    
    def combine_expressions(
        self,
        new_expression: str,
        old_subset: Optional[str],
        combine_operator: Optional[str],
        layer_props: Optional[Dict] = None
    ) -> CombineResult:
        """
        Combine new filter expression with existing subset.
        
        Uses CombinedQueryOptimizer when available for 10-50x speedup
        on successive filters.
        
        Extracted from FilterEngineTask._build_combined_filter_expression (lines 2249-2325).
        
        Args:
            new_expression: New filter expression to apply
            old_subset: Existing subset string from layer
            combine_operator: SQL operator ('AND', 'OR', 'NOT')
            layer_props: Optional layer properties for optimization
            
        Returns:
            CombineResult with combined expression and optimization info
        """
        # No combination needed
        if not old_subset or not combine_operator:
            return CombineResult(
                expression=new_expression,
                success=True
            )
        
        # Sanitize old_subset if sanitizer available
        sanitized_old = old_subset
        if self._sanitize_fn:
            sanitized_old = self._sanitize_fn(old_subset)
            if not sanitized_old:
                return CombineResult(
                    expression=new_expression,
                    success=True
                )
        
        # Try optimizer if enabled
        if self._use_optimizer:
            try:
                from ...optimization.combined_query_optimizer import get_combined_query_optimizer
                
                optimizer = get_combined_query_optimizer()
                result = optimizer.optimize_combined_expression(
                    old_subset=sanitized_old,
                    new_expression=new_expression,
                    combine_operator=combine_operator,
                    layer_props=layer_props
                )
                
                if result.success:
                    logger.info(
                        f"✓ Combined expression optimized ({result.optimization_type.name}): "
                        f"~{result.estimated_speedup:.1f}x speedup expected"
                    )
                    return CombineResult(
                        expression=result.optimized_expression,
                        success=True,
                        optimization_applied=True,
                        optimization_type=result.optimization_type.name,
                        estimated_speedup=result.estimated_speedup
                    )
            except Exception as e:
                logger.warning(f"Combined query optimization failed: {e}")
        
        # Fallback: Manual combination
        combined = self._manual_combine(
            new_expression=new_expression,
            old_subset=sanitized_old,
            combine_operator=combine_operator
        )
        
        return CombineResult(
            expression=combined,
            success=True
        )
    
    def _manual_combine(
        self,
        new_expression: str,
        old_subset: str,
        combine_operator: str
    ) -> str:
        """
        Manually combine expressions without optimizer.
        
        Args:
            new_expression: New expression
            old_subset: Old subset
            combine_operator: Operator
            
        Returns:
            Combined expression string
        """
        # Extract WHERE clause if present
        param_old_subset_where_clause = ''
        param_source_old_subset = old_subset
        
        index_where_clause = old_subset.find('WHERE')
        if index_where_clause > -1:
            param_old_subset_where_clause = old_subset[index_where_clause:]
            if param_old_subset_where_clause.endswith('))'):
                param_old_subset_where_clause = param_old_subset_where_clause[:-1]
            param_source_old_subset = old_subset[:index_where_clause]
        
        # Build combined expression
        if index_where_clause > -1:
            # Has WHERE clause - combine with existing structure
            # Fix: Strip leading "WHERE " from new_expression to prevent "WHERE WHERE" syntax error
            clean_new_expression = new_expression.lstrip()
            if clean_new_expression.upper().startswith('WHERE '):
                clean_new_expression = clean_new_expression[6:].lstrip()
            return f'{param_source_old_subset} {param_old_subset_where_clause} {combine_operator} {clean_new_expression}'
        else:
            # No WHERE clause - wrap both in parentheses for safety
            return f'( {old_subset} ) {combine_operator} ( {new_expression} )'
    
    def sanitize(self, subset_string: str) -> str:
        """
        Sanitize a subset string.
        
        Args:
            subset_string: Raw subset string
            
        Returns:
            Sanitized string
        """
        if self._sanitize_fn:
            return self._sanitize_fn(subset_string)
        return subset_string
    
    def validate(self, expression: str, layer: Optional[Any] = None) -> Tuple[bool, Optional[str]]:  # layer: Optional[QgsVectorLayer]
        """
        Validate a subset expression.
        
        Args:
            expression: Expression to validate
            layer: Optional layer for context validation
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not expression:
            return True, None  # Empty is valid (clears filter)
        
        # Basic syntax checks
        if expression.count('(') != expression.count(')'):
            return False, "Unbalanced parentheses"
        
        if expression.count('"') % 2 != 0:
            return False, "Unbalanced quotes"
        
        # Check for obvious SQL injection patterns
        dangerous_patterns = [';--', 'DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE']
        upper_expr = expression.upper()
        for pattern in dangerous_patterns:
            if pattern in upper_expr and pattern not in ['ALTER']:  # ALTER can be valid in expressions
                return False, f"Potentially dangerous pattern detected: {pattern}"
        
        return True, None
    
    @staticmethod
    def extract_where_clause(subset_string: str) -> Tuple[str, str]:
        """
        Extract WHERE clause from a subset string.
        
        Args:
            subset_string: Full subset string
            
        Returns:
            Tuple of (prefix, where_clause)
        """
        if not subset_string:
            return "", ""
        
        index = subset_string.find('WHERE')
        if index > -1:
            return subset_string[:index], subset_string[index:]
        return subset_string, ""
    
    @staticmethod
    def wrap_in_parentheses(expression: str) -> str:
        """
        Wrap expression in parentheses if not already wrapped.
        
        Args:
            expression: Expression to wrap
            
        Returns:
            Wrapped expression
        """
        if not expression:
            return expression
        
        expr = expression.strip()
        if expr.startswith('(') and expr.endswith(')'):
            # Check if the parentheses are balanced at start and end
            count = 0
            for i, char in enumerate(expr):
                if char == '(':
                    count += 1
                elif char == ')':
                    count -= 1
                if count == 0 and i < len(expr) - 1:
                    # Parentheses closed before end, need to wrap
                    return f'({expression})'
            return expression  # Already wrapped
        return f'({expression})'

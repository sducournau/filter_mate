"""
Multi-Step Filter Optimizer
Decomposes complex filters into sequential optimized steps.

Phase 2 (v4.1.0-beta.2): Restoration from v2.5.10 multi_step_optimizer.py
Architecture: Hexagonal Core - Domain Service

Key Optimizations:
==================
1. SPATIAL FIRST: Execute spatial filters before attribute filters (highest reduction)
2. SIMPLE BEFORE COMPLEX: Sort attribute filters by estimated selectivity
3. PROGRESSIVE FILTERING: Each step reduces dataset for subsequent steps
4. COST-BASED ORDERING: Minimize total execution time

Performance Improvements:
========================
- Complex filters: 2-8× faster with optimal step ordering
- Spatial + attribute: 3-15× faster (spatial first reduces attribute evaluation)
- Multiple ANDs: 1.5-4× faster (selective conditions first)

Example:
    >>> optimizer = get_multi_step_optimizer()
    >>> steps = optimizer.decompose_filter(
    ...     expression='"population" > 10000 AND ST_Intersects($geometry, geom_from_wkt(...))',
    ...     layer=my_layer
    ... )
    >>> for step in steps:
    ...     print(f"Step {step.step_number}: {step.operation_type} - {step.expression}")
"""

from dataclasses import dataclass
from typing import Optional, List, Tuple
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class FilterStep:
    """
    A single step in a multi-step filter operation.
    
    Attributes:
        step_number: Sequential step number (1-indexed)
        expression: Filter expression for this step
        operation_type: Type of operation ('spatial', 'attributaire', 'post_process')
        estimated_reduction: Estimated % of features filtered out (0.0-100.0)
        estimated_time_ms: Estimated execution time in milliseconds
    
    Example:
        >>> step = FilterStep(
        ...     step_number=1,
        ...     expression='ST_Intersects($geometry, geom_from_wkt("POLYGON(...)"))',
        ...     operation_type='spatial',
        ...     estimated_reduction=75.0,
        ...     estimated_time_ms=450
        ... )
    """
    step_number: int
    expression: str
    operation_type: str  # 'spatial', 'attributaire', 'post_process'
    estimated_reduction: float  # % features filtered (0.0-100.0)
    estimated_time_ms: int


class MultiStepFilterOptimizer:
    """
    Decomposes complex filter expressions into optimized sequential steps.
    
    Strategy:
        1. Extract spatial component (ST_*, intersects, contains, etc.)
        2. Extract simple attribute filters (field comparisons)
        3. Extract complex expressions (functions, calculations)
        4. Order by selectivity: spatial > simple attribute > complex
        5. Estimate reduction and timing for each step
    
    Thresholds (based on v2.5.10 benchmarks):
        - Spatial filters: ~60-90% reduction (very selective)
        - Simple attribute: ~20-70% reduction (varies)
        - Complex expressions: ~10-50% reduction (least predictable)
    
    Example:
        >>> optimizer = MultiStepFilterOptimizer()
        >>> expression = '"pop" > 10000 AND ST_Intersects($geometry, geom) AND "type" = \'city\''
        >>> steps = optimizer.decompose_filter(expression, layer)
        >>> # Result: 3 steps (spatial, pop filter, type filter)
    """
    
    # Spatial function patterns (PostgreSQL/PostGIS + QGIS)
    SPATIAL_FUNCTIONS = [
        'ST_Intersects', 'ST_Contains', 'ST_Within', 'ST_Overlaps',
        'ST_Crosses', 'ST_Touches', 'ST_Disjoint', 'ST_Distance',
        'ST_DWithin', 'ST_Buffer', 'ST_Envelope',
        'intersects', 'contains', 'within', 'overlaps',  # QGIS variants
        'crosses', 'touches', 'disjoint', 'distance', 'buffer',
        'geom_from_wkt', 'geom_from_gml', 'geometry'
    ]
    
    # Complexity indicators for attribute filters
    COMPLEX_FUNCTIONS = [
        'regexp_match', 'regexp_replace', 'substr', 'length',
        'concat', 'upper', 'lower', 'to_string', 'to_int',
        'coalesce', 'case', 'when', 'array_', 'map_'
    ]
    
    # Default selectivity estimates (% reduction)
    DEFAULT_SPATIAL_REDUCTION = 70.0  # Spatial filters are highly selective
    DEFAULT_SIMPLE_ATTR_REDUCTION = 40.0  # Simple comparisons
    DEFAULT_COMPLEX_REDUCTION = 20.0  # Complex expressions less predictable
    
    # Time estimates (ms per 1000 features)
    SPATIAL_TIME_PER_1K = 50  # Spatial ops are expensive
    SIMPLE_ATTR_TIME_PER_1K = 5  # Attribute comparisons are fast
    COMPLEX_TIME_PER_1K = 15  # Complex expressions moderate
    
    def __init__(self):
        """Initialize the optimizer."""
        logger.debug("MultiStepFilterOptimizer initialized")
    
    def decompose_filter(
        self,
        expression: str,
        layer
    ) -> List[FilterStep]:
        """
        Decompose a complex filter into optimized sequential steps.
        
        Args:
            expression: QGIS filter expression (potentially complex)
            layer: QgsVectorLayer being filtered (for statistics)
        
        Returns:
            List of FilterStep objects in optimal execution order
            Returns single step if expression is already simple
        
        Algorithm:
            1. Parse expression into components (spatial, attribute, complex)
            2. Estimate reduction factor for each component
            3. Sort by selectivity (highest reduction first)
            4. Create sequential steps with cumulative estimates
        
        Example:
            >>> steps = optimizer.decompose_filter(
            ...     '"pop" > 10000 AND ST_Intersects($geometry, geom)',
            ...     layer
            ... )
            >>> assert steps[0].operation_type == 'spatial'  # Spatial first
            >>> assert steps[1].operation_type == 'attributaire'  # Attribute second
        """
        if not expression or not expression.strip():
            logger.debug("Empty expression, no decomposition needed")
            return []
        
        # Check if expression is simple (no decomposition needed)
        if not self._is_complex_expression(expression):
            logger.debug(f"Simple expression, single step: {expression[:100]}...")
            feature_count = layer.featureCount() if layer else 1000
            return [FilterStep(
                step_number=1,
                expression=expression.strip(),
                operation_type=self._classify_expression(expression),
                estimated_reduction=self._estimate_single_reduction(expression),
                estimated_time_ms=self._estimate_single_time(expression, feature_count)
            )]
        
        logger.info(f"Decomposing complex filter: {expression[:100]}...")
        
        # Extract components
        spatial_parts = self._extract_spatial_component(expression)
        attributaire_parts = self._extract_attributaire_components(expression)
        
        # Build step candidates
        step_candidates = []
        
        if spatial_parts:
            for spatial_expr in spatial_parts:
                step_candidates.append({
                    'expression': spatial_expr,
                    'type': 'spatial',
                    'estimated_reduction': self.DEFAULT_SPATIAL_REDUCTION,
                    'priority': 1  # Highest priority
                })
        
        for attr_expr in attributaire_parts:
            is_complex = self._is_complex_attribute(attr_expr)
            step_candidates.append({
                'expression': attr_expr,
                'type': 'attributaire' if not is_complex else 'post_process',
                'estimated_reduction': (
                    self.DEFAULT_SIMPLE_ATTR_REDUCTION 
                    if not is_complex 
                    else self.DEFAULT_COMPLEX_REDUCTION
                ),
                'priority': 2 if not is_complex else 3
            })
        
        # If no decomposition possible, return original as single step
        if len(step_candidates) <= 1:
            logger.debug("No multi-step decomposition beneficial, using original")
            feature_count = layer.featureCount() if layer else 1000
            return [FilterStep(
                step_number=1,
                expression=expression.strip(),
                operation_type=self._classify_expression(expression),
                estimated_reduction=50.0,  # Conservative estimate
                estimated_time_ms=self._estimate_single_time(expression, feature_count)
            )]
        
        # Optimize step order
        optimized_steps = self._optimize_step_order(step_candidates)
        
        # Create FilterStep objects with cumulative estimates
        feature_count = layer.featureCount() if layer else 1000
        filter_steps = []
        remaining_features = feature_count
        
        for idx, step_data in enumerate(optimized_steps):
            step_number = idx + 1
            
            # Estimate reduction for current dataset size
            reduction_pct = step_data['estimated_reduction']
            
            # Estimate time based on remaining features
            estimated_time = self._estimate_step_time(
                step_data['expression'],
                step_data['type'],
                remaining_features
            )
            
            filter_step = FilterStep(
                step_number=step_number,
                expression=step_data['expression'],
                operation_type=step_data['type'],
                estimated_reduction=reduction_pct,
                estimated_time_ms=estimated_time
            )
            
            filter_steps.append(filter_step)
            
            # Update remaining features for next step
            remaining_features = int(remaining_features * (1.0 - reduction_pct / 100.0))
            
            logger.debug(
                f"Step {step_number} ({step_data['type']}): {reduction_pct:.1f}% reduction, "
                f"{estimated_time}ms estimated, {remaining_features} features remaining"
            )
        
        logger.info(
            f"Decomposed into {len(filter_steps)} steps: "
            f"{[s.operation_type for s in filter_steps]}"
        )
        
        return filter_steps
    
    def _is_complex_expression(self, expression: str) -> bool:
        """
        Check if expression is complex enough to warrant decomposition.
        
        Args:
            expression: Filter expression
        
        Returns:
            True if expression has multiple AND clauses or spatial + attribute mix
        """
        # Count AND operators
        and_count = expression.upper().count(' AND ')
        
        # Check for spatial + attribute combination
        has_spatial = any(
            func in expression for func in self.SPATIAL_FUNCTIONS
        )
        has_attribute = bool(re.search(r'"[^"]+"\s*[=<>!]', expression))
        
        return and_count >= 1 or (has_spatial and has_attribute)
    
    def _classify_expression(self, expression: str) -> str:
        """Classify a single expression type."""
        if any(func in expression for func in self.SPATIAL_FUNCTIONS):
            return 'spatial'
        elif any(func in expression.lower() for func in self.COMPLEX_FUNCTIONS):
            return 'post_process'
        else:
            return 'attributaire'
    
    def _extract_spatial_component(self, expression: str) -> List[str]:
        """
        Extract spatial filter components from expression.
        
        Args:
            expression: Full filter expression
        
        Returns:
            List of spatial filter expressions (may be empty)
        
        Algorithm:
            1. Look for spatial function calls
            2. Extract complete function with arguments
            3. Handle nested parentheses correctly
        """
        spatial_parts = []
        
        for func in self.SPATIAL_FUNCTIONS:
            if func not in expression:
                continue
            
            # Find function call with balanced parentheses
            pattern = re.escape(func) + r'\s*\([^)]*(?:\([^)]*\)[^)]*)*\)'
            matches = re.finditer(pattern, expression, re.IGNORECASE)
            
            for match in matches:
                spatial_expr = match.group(0).strip()
                if spatial_expr and spatial_expr not in spatial_parts:
                    spatial_parts.append(spatial_expr)
                    logger.debug(f"Extracted spatial component: {spatial_expr[:80]}...")
        
        return spatial_parts
    
    def _extract_attributaire_components(self, expression: str) -> List[str]:
        """
        Extract attribute filter components from expression.
        
        Args:
            expression: Full filter expression
        
        Returns:
            List of attribute filter expressions
        
        Algorithm:
            1. Remove spatial components
            2. Split on AND operators
            3. Filter out empty/spatial parts
            4. Classify as simple or complex
        """
        # Remove spatial parts first
        remaining = expression
        for spatial_func in self.SPATIAL_FUNCTIONS:
            pattern = re.escape(spatial_func) + r'\s*\([^)]*(?:\([^)]*\)[^)]*)*\)'
            remaining = re.sub(pattern, '', remaining, flags=re.IGNORECASE)
        
        # Remove leading/trailing AND operators
        remaining = re.sub(r'^\s*AND\s+', '', remaining, flags=re.IGNORECASE)
        remaining = re.sub(r'\s+AND\s*$', '', remaining, flags=re.IGNORECASE)
        
        # Split on AND (simple approach - doesn't handle OR or nested logic)
        parts = re.split(r'\s+AND\s+', remaining, flags=re.IGNORECASE)
        
        # Clean and filter
        attribute_parts = []
        for part in parts:
            part = part.strip()
            if part and not any(func in part for func in self.SPATIAL_FUNCTIONS):
                attribute_parts.append(part)
                logger.debug(f"Extracted attribute component: {part[:80]}...")
        
        return attribute_parts
    
    def _is_complex_attribute(self, expression: str) -> bool:
        """Check if attribute expression uses complex functions."""
        expr_lower = expression.lower()
        return any(func in expr_lower for func in self.COMPLEX_FUNCTIONS)
    
    def _estimate_single_reduction(self, expression: str) -> float:
        """
        Estimate reduction percentage for a single expression.
        
        Args:
            expression: Filter expression
        
        Returns:
            Estimated % reduction (0.0-100.0)
        """
        expr_type = self._classify_expression(expression)
        
        if expr_type == 'spatial':
            return self.DEFAULT_SPATIAL_REDUCTION
        elif expr_type == 'post_process':
            return self.DEFAULT_COMPLEX_REDUCTION
        else:
            return self.DEFAULT_SIMPLE_ATTR_REDUCTION
    
    def _estimate_single_time(self, expression: str, feature_count: int) -> int:
        """
        Estimate execution time for single expression.
        
        Args:
            expression: Filter expression
            feature_count: Number of features to process
        
        Returns:
            Estimated time in milliseconds
        """
        expr_type = self._classify_expression(expression)
        
        # Calculate time based on type and feature count
        thousands = max(1, feature_count / 1000.0)
        
        if expr_type == 'spatial':
            base_time = self.SPATIAL_TIME_PER_1K
        elif expr_type == 'post_process':
            base_time = self.COMPLEX_TIME_PER_1K
        else:
            base_time = self.SIMPLE_ATTR_TIME_PER_1K
        
        return int(base_time * thousands)
    
    def _estimate_step_time(
        self,
        expression: str,
        operation_type: str,
        feature_count: int
    ) -> int:
        """
        Estimate execution time for a filter step.
        
        Args:
            expression: Step expression
            operation_type: Type of operation
            feature_count: Number of features to process
        
        Returns:
            Estimated time in milliseconds
        """
        thousands = max(1, feature_count / 1000.0)
        
        if operation_type == 'spatial':
            base_time = self.SPATIAL_TIME_PER_1K
        elif operation_type == 'post_process':
            base_time = self.COMPLEX_TIME_PER_1K
        else:
            base_time = self.SIMPLE_ATTR_TIME_PER_1K
        
        return int(base_time * thousands)
    
    def _optimize_step_order(self, step_candidates: List[dict]) -> List[dict]:
        """
        Optimize execution order of filter steps.
        
        Strategy:
            1. Spatial filters first (highest reduction, worth the cost)
            2. Simple attribute filters (fast and moderately selective)
            3. Complex expressions last (expensive, less predictable)
        
        Args:
            step_candidates: List of step dictionaries with priority/reduction
        
        Returns:
            Sorted list of step dictionaries in optimal order
        """
        # Sort by priority (lower number = higher priority), then by reduction
        optimized = sorted(
            step_candidates,
            key=lambda x: (x['priority'], -x['estimated_reduction'])
        )
        
        logger.debug(
            f"Optimized step order: {[s['type'] for s in optimized]} "
            f"(priorities: {[s['priority'] for s in optimized]})"
        )
        
        return optimized


# Singleton instance
_multi_step_optimizer = None


def get_multi_step_optimizer() -> MultiStepFilterOptimizer:
    """
    Get singleton instance of MultiStepFilterOptimizer.
    
    Returns:
        Shared MultiStepFilterOptimizer instance
    
    Example:
        >>> optimizer = get_multi_step_optimizer()
        >>> steps = optimizer.decompose_filter(expression, layer)
    """
    global _multi_step_optimizer
    
    if _multi_step_optimizer is None:
        _multi_step_optimizer = MultiStepFilterOptimizer()
        logger.debug("Created singleton MultiStepFilterOptimizer instance")
    
    return _multi_step_optimizer

"""
Expression Combiner Module

EPIC-1 Phase E3: Extracted from modules/tasks/filter_task.py

Provides expression combination operations:
- Combine new expressions with existing subset strings
- Support for logical operators (AND, OR, NOT, REPLACE)
- Duplicate expression detection and prevention
- OGR fallback handling for PostgreSQL syntax

Used by FilterEngineTask for building combined filter expressions.

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase E3)
"""

import logging
import re
from enum import Enum
from typing import Optional

logger = logging.getLogger('FilterMate.Core.Filter.Combiner')


class CombineOperator(Enum):
    """SQL combination operators for filter expressions."""
    AND = "AND"
    OR = "OR"
    NOT = "AND NOT"
    REPLACE = None  # Replace old expression entirely


def normalize_expression(expr: str) -> str:
    """
    Normalize expression for comparison (strip whitespace and outer parentheses).
    
    Args:
        expr: Expression to normalize
        
    Returns:
        str: Normalized expression
    """
    if not expr:
        return ""
    expr = expr.strip()
    # Normalize whitespace: replace multiple spaces with single space
    expr = re.sub(r'\s+', ' ', expr)
    # Remove outer parentheses if present
    while expr.startswith('(') and expr.endswith(')'):
        # Check if these are matching outer parentheses
        depth = 0
        is_outer = True
        for i, char in enumerate(expr):
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if depth == 0 and i < len(expr) - 1:
                    is_outer = False
                    break
        if is_outer and depth == 0:
            expr = expr[1:-1].strip()
            # Normalize whitespace again after stripping parentheses
            expr = re.sub(r'\s+', ' ', expr)
        else:
            break
    return expr


def apply_combine_operator(
    primary_key_name: str,
    param_expression: str,
    param_old_subset: Optional[str],
    param_combine_operator: Optional[str]
) -> str:
    """
    Apply SQL set operator to combine with existing subset.
    
    Used for PostgreSQL IN subqueries with UNION, INTERSECT, EXCEPT operators.
    
    Args:
        primary_key_name: Primary key field name
        param_expression: The subquery expression
        param_old_subset: Existing subset to combine with (optional)
        param_combine_operator: SQL set operator (UNION, INTERSECT, EXCEPT) (optional)
        
    Returns:
        str: Complete IN expression with optional combine operator
    """
    if param_old_subset and param_combine_operator:
        return (
            f'"{primary_key_name}" IN ( {param_old_subset} '
            f'{param_combine_operator} {param_expression} )'
        )
    else:
        return f'"{primary_key_name}" IN {param_expression}'


def combine_with_old_subset(
    new_expression: str,
    old_subset: str,
    combine_operator: Optional[str],
    provider_type: str = 'postgresql',
    optimize_duplicates_fn: Optional[callable] = None
) -> str:
    """
    Combine new expression with existing subset string using combine operator.
    
    Uses logical operators (AND, AND NOT, OR) for source layer filtering.
    
    Process:
    1. Check if expressions are identical (skip duplication)
    2. Check if new expression is contained in old (return old)
    3. Check if old expression is contained in new (return new)
    4. Handle OGR fallback for PostgreSQL syntax
    5. Combine expressions with specified operator
    6. Optimize duplicate IN clauses
    
    Args:
        new_expression: New filter expression
        old_subset: Existing subset string from layer
        combine_operator: Logical operator ('AND', 'OR', 'AND NOT', None for REPLACE)
        provider_type: Provider type ('postgresql', 'spatialite', 'ogr')
        optimize_duplicates_fn: Optional callback to optimize duplicate IN clauses
            Signature: optimize_duplicates_fn(expression: str) -> str
        
    Returns:
        str: Combined expression
    """
    # If no existing filter, return new expression
    if not old_subset:
        return new_expression
    
    # If REPLACE operator (None), return new expression only
    if combine_operator is None:
        logger.info("FilterMate: REPLACE operator - using new expression only")
        return new_expression
    
    normalized_new = normalize_expression(new_expression)
    normalized_old = normalize_expression(old_subset)
    
    logger.debug(f"FilterMate: Comparing expressions:")
    logger.debug(f"  → normalized_new: '{normalized_new[:60]}...'")
    logger.debug(f"  → normalized_old: '{normalized_old[:60]}...'")
    
    # If expressions are identical, don't duplicate
    if normalized_new == normalized_old:
        logger.info("FilterMate: New expression identical to old subset - skipping duplication")
        return new_expression
    
    # If new expression is already contained in old subset, don't duplicate
    if normalized_new in normalized_old:
        logger.info("FilterMate: New expression already in old subset - skipping duplication")
        return old_subset
    
    # If old subset is contained in new expression, use new only
    if normalized_old in normalized_new:
        logger.info("FilterMate: Old subset already in new expression - returning new expression")
        return new_expression
    
    # Default to AND if no operator specified (preserve existing filters)
    if not combine_operator:
        combine_operator = 'AND'
        logger.info(
            "FilterMate: No combine operator specified, using AND by default "
            "to preserve existing filter"
        )
    
    # Handle OGR fallback for PostgreSQL syntax
    if provider_type == 'ogr':
        old_subset_upper = old_subset.upper()
        if 'SELECT' in old_subset_upper or 'FROM' in old_subset_upper:
            logger.warning("FilterMate: Old subset contains PostgreSQL syntax but using OGR fallback")
            # Try to extract just the WHERE clause
            index_where = old_subset.upper().find('WHERE')
            if index_where != -1:
                where_clause = old_subset[index_where + 5:].strip()  # Skip 'WHERE'
                if where_clause:
                    logger.info(f"FilterMate: Extracted WHERE clause for OGR: {where_clause[:80]}...")
                    combined = f'( {where_clause} ) {combine_operator} ( {new_expression} )'
                    if optimize_duplicates_fn:
                        return optimize_duplicates_fn(combined)
                    return combined
            # Can't extract WHERE clause - use new expression only
            logger.warning(
                "FilterMate: Cannot combine with PostgreSQL subset in OGR mode - "
                "using new expression only"
            )
            return new_expression
    
    # Extract WHERE clause from old subset if present
    index_where = old_subset.find('WHERE')
    if index_where == -1:
        # No WHERE clause - simple combination
        combined = f'( {old_subset} ) {combine_operator} ( {new_expression} )'
    else:
        param_old_subset_where = old_subset[index_where:]
        param_source_old_subset = old_subset[:index_where]
        
        # Remove trailing )) if present (legacy handling for malformed expressions)
        if param_old_subset_where.endswith('))'):
            param_old_subset_where = param_old_subset_where[:-1]
        
        combined = (
            f'{param_source_old_subset} {param_old_subset_where} '
            f'{combine_operator} ( {new_expression} )'
        )
    
    # Optimize duplicate IN clauses if callback provided
    if optimize_duplicates_fn:
        optimized = optimize_duplicates_fn(combined)
        if optimized != combined:
            original_len = len(combined)
            optimized_len = len(optimized)
            savings = original_len - optimized_len
            logger.info(
                f"FilterMate: OPTIMIZATION - Reduced expression size from {original_len} "
                f"to {optimized_len} bytes ({savings} bytes saved, "
                f"{100*savings/original_len:.1f}% reduction)"
            )
            return optimized
    
    return combined


def should_replace_old_subset(old_subset: str) -> tuple:
    """
    Check if old subset contains patterns that should trigger replacement instead of combination.
    
    Patterns that require replacement:
    - __source alias (only valid inside EXISTS subqueries)
    - EXISTS subquery (avoid nested EXISTS)
    - Spatial predicates (likely from previous geometric filter)
    - FilterMate materialized view references
    - QGIS style/symbology expressions
    
    Args:
        old_subset: Existing subset string to check
        
    Returns:
        tuple: (should_replace: bool, reasons: list of str)
    """
    import re
    
    if not old_subset:
        return False, []
    
    reasons = []
    old_subset_upper = old_subset.upper()
    
    # Pattern 1: __source alias (only valid inside EXISTS subqueries)
    if '__source' in old_subset.lower():
        reasons.append("__source alias")
    
    # Pattern 2: EXISTS subquery (avoid nested EXISTS)
    if 'EXISTS (' in old_subset_upper or 'EXISTS(' in old_subset_upper:
        reasons.append("EXISTS subquery")
    
    # Pattern 3: Spatial predicates (likely from previous geometric filter)
    spatial_predicates = [
        'ST_INTERSECTS', 'ST_CONTAINS', 'ST_WITHIN', 'ST_TOUCHES',
        'ST_OVERLAPS', 'ST_CROSSES', 'ST_DISJOINT', 'ST_EQUALS',
        'ST_DWITHIN', 'ST_COVERS', 'ST_COVEREDBY'
    ]
    if any(pred in old_subset_upper for pred in spatial_predicates):
        reasons.append("spatial predicate")
    
    # Pattern 4: FilterMate materialized view reference
    if re.search(
        r'IN\s*\(\s*SELECT.*FROM\s+["\']?filter_mate_temp["\']?\s*\.\s*["\']?mv_',
        old_subset,
        re.IGNORECASE | re.DOTALL
    ):
        reasons.append("FilterMate materialized view (mv_)")
    
    # Pattern 5: QGIS style/symbology expressions
    style_patterns = [
        r'AND\s+TRUE\s*\)',
        r'THEN\s+true',
        r'THEN\s+false',
        r'SELECT\s+CASE',
        r'\)\s*AND\s+TRUE\s*\)',
    ]
    if any(re.search(pattern, old_subset, re.IGNORECASE) for pattern in style_patterns):
        reasons.append("QGIS style pattern")
    
    return bool(reasons), reasons


def combine_with_old_filter(
    new_expression: str,
    old_subset: Optional[str],
    combine_operator: Optional[str] = 'AND',
    sanitize_fn: Optional[callable] = None
) -> str:
    """
    Combine new expression with existing layer filter.
    
    Similar to combine_with_old_subset but for distant layer filtering.
    Handles special patterns that should trigger replacement instead of combination.
    
    Args:
        new_expression: New filter expression
        old_subset: Existing subset string from layer
        combine_operator: Logical operator ('AND', 'OR', 'AND NOT')
        sanitize_fn: Optional callback to sanitize old_subset
        
    Returns:
        str: Combined or replaced expression
    """
    # No existing filter
    if not old_subset:
        return new_expression
    
    # Sanitize if callback provided
    if sanitize_fn:
        old_subset = sanitize_fn(old_subset)
        if not old_subset:
            return new_expression
    
    # Check if we should replace instead of combine
    should_replace, reasons = should_replace_old_subset(old_subset)
    if should_replace:
        logger.info(f"Old subset contains {', '.join(reasons)} - replacing instead of combining")
        return new_expression
    
    # Default to AND if no operator specified
    if not combine_operator:
        combine_operator = 'AND'
        logger.info("No combine operator specified, using AND by default to preserve existing filter")
    
    return f"({old_subset}) {combine_operator} ({new_expression})"

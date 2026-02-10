"""
Expression Combiner Module

EPIC-1 Phase E3: Extracted from modules/tasks/filter_task.py

Provides expression combination operations:
- Combine new expressions with existing subset strings
- Support for logical operators (AND, OR, NOT, REPLACE)
- Duplicate expression detection and prevention
- OGR fallback handling for PostgreSQL syntax
- Chain multiple EXISTS filters from different sources (v4.2.9)

Used by FilterEngineTask for building combined filter expressions.

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase E3)
Updated: January 2026 (v4.2.9 - Filter chaining with multiple EXISTS)
"""

import logging
import re
from enum import Enum
from typing import Optional, List, Dict, Tuple

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


def extract_exists_clauses(expression: str) -> List[Dict[str, str]]:
    """
    Extract all EXISTS clauses from an expression.

    v4.2.9: Used for filter chaining to identify and preserve spatial filters.

    Example:
        Input: "EXISTS (SELECT 1 FROM zone_pop AS __source WHERE ...) AND field='value'"
        Output: [{'sql': 'EXISTS (SELECT 1 FROM zone_pop AS __source WHERE ...)',
                  'table': 'zone_pop', 'alias': '__source'}]

    Args:
        expression: SQL expression potentially containing EXISTS clauses

    Returns:
        List of dicts with extracted EXISTS clause info
    """
    if not expression:
        return []

    exists_clauses = []

    # Find all EXISTS with proper parenthesis matching
    i = 0
    while i < len(expression):
        match = re.search(r'EXISTS\s*\(', expression[i:], re.IGNORECASE)
        if not match:
            break

        start = i + match.start()
        # Find matching closing parenthesis
        paren_count = 0
        j = i + match.end()

        while j < len(expression):
            if expression[j] == '(':
                paren_count += 1
            elif expression[j] == ')':
                if paren_count == 0:
                    # Found matching closing paren
                    exists_sql = expression[start:j + 1]

                    # Extract table name
                    table_match = re.search(
                        r'FROM\s+"?(\w+)"?\s*\.\s*"?(\w+)"?\s+AS\s+(\w+)',
                        exists_sql,
                        re.IGNORECASE
                    )
                    if not table_match:
                        # Try simpler pattern without schema
                        table_match = re.search(
                            r'FROM\s+"?(\w+)"?\s+AS\s+(\w+)',
                            exists_sql,
                            re.IGNORECASE
                        )

                    if table_match:
                        if len(table_match.groups()) == 3:
                            # schema.table AS alias
                            exists_clauses.append({
                                'sql': exists_sql,
                                'schema': table_match.group(1),
                                'table': table_match.group(2),
                                'alias': table_match.group(3),
                                'start': start,
                                'end': j + 1
                            })
                        else:
                            # table AS alias
                            exists_clauses.append({
                                'sql': exists_sql,
                                'schema': 'public',
                                'table': table_match.group(1),
                                'alias': table_match.group(2),
                                'start': start,
                                'end': j + 1
                            })
                    else:
                        # Couldn't parse table name, still include the clause
                        exists_clauses.append({
                            'sql': exists_sql,
                            'schema': 'unknown',
                            'table': 'unknown',
                            'alias': '__source',
                            'start': start,
                            'end': j + 1
                        })

                    i = j + 1
                    break
                else:
                    paren_count -= 1
            j += 1
        else:
            # No matching paren found
            i = j

    return exists_clauses


def adapt_exists_for_nested_context(
    exists_sql: str,
    original_table: str,
    new_alias: str = '__source',
    original_schema: Optional[str] = None
) -> str:
    """
    Adapt an EXISTS clause for use in a nested context.

    v4.2.9: When an EXISTS filter from a source layer is used as source_filter
    in a new EXISTS (for distant layers), table references must be updated.

    Problem:
        Original filter on ducts:
            EXISTS (SELECT 1 FROM zone_pop AS __source
                    WHERE ST_Intersects(ST_PointOnSurface("ducts"."geom"), __source."geom"))

        When used in distant layer context:
            EXISTS (SELECT 1 FROM ducts AS __source WHERE ... AND (original_filter))

        The "ducts"."geom" reference is invalid because "ducts" is not in the FROM clause!
        It should be __source."geom" (the outer EXISTS alias).

    Solution:
        Replace "original_table"."column" with new_alias."column"

    Args:
        exists_sql: The EXISTS SQL to adapt
        original_table: Original table name to replace (e.g., "ducts")
        new_alias: New alias to use (default: "__source")
        original_schema: Optional schema of the original table

    Returns:
        Adapted EXISTS SQL with table references updated
    """
    if not exists_sql or not original_table:
        return exists_sql

    adapted = exists_sql

    # Pattern 1: "schema"."table"."column" → new_alias."column"
    if original_schema:
        pattern1 = rf'"{re.escape(original_schema)}"\s*\.\s*"{re.escape(original_table)}"\s*\.\s*"(\w+)"'
        adapted = re.sub(pattern1, rf'{new_alias}."\1"', adapted, flags=re.IGNORECASE)

    # Pattern 2: "table"."column" → new_alias."column"
    pattern2 = rf'"{re.escape(original_table)}"\s*\.\s*"(\w+)"'
    adapted = re.sub(pattern2, rf'{new_alias}."\1"', adapted, flags=re.IGNORECASE)

    # Pattern 3: table."column" (without quotes on table) → new_alias."column"
    pattern3 = rf'\b{re.escape(original_table)}\s*\.\s*"(\w+)"'
    adapted = re.sub(pattern3, rf'{new_alias}."\1"', adapted, flags=re.IGNORECASE)

    if adapted != exists_sql:
        logger.info("🔄 Adapted EXISTS for nested context:")
        logger.info(f"   → Replaced references to '{original_table}' with '{new_alias}'")
        logger.debug(f"   → Original: {exists_sql[:100]}...")
        logger.debug(f"   → Adapted: {adapted[:100]}...")

    return adapted


def chain_exists_filters(
    old_expression: str,
    new_exists_clause: str,
    combine_operator: str = 'AND'
) -> str:
    """
    Chain multiple EXISTS filters from different sources.

    v4.2.9: Implements filter chaining for sequential filtering scenarios.

    Scenario:
        1. Filter 1 (zone_pop): Spatial selection on source features
           → EXISTS (SELECT 1 FROM zone_pop AS __source WHERE ST_Intersects(...))

        2. Filter 2 (ducts): Buffer intersection from filtered ducts
           → EXISTS (SELECT 1 FROM ducts AS __source WHERE ST_Intersects(..., ST_Buffer(...)))

        Result for distant layers (subducts):
           → EXISTS (zone_pop filter) AND EXISTS (ducts buffer filter)

    This function:
    1. Detects if old_expression contains EXISTS clauses
    2. Verifies new_exists_clause is a valid EXISTS
    3. Combines them with the specified operator
    4. Preserves non-EXISTS conditions from old_expression

    Args:
        old_expression: Existing filter expression (may contain EXISTS)
        new_exists_clause: New EXISTS clause to add
        combine_operator: Logical operator ('AND' or 'OR')

    Returns:
        Combined expression with chained EXISTS filters
    """
    if not old_expression:
        return new_exists_clause

    if not new_exists_clause:
        return old_expression

    # Validate combine_operator
    combine_operator = combine_operator.upper()
    if combine_operator not in ('AND', 'OR'):
        combine_operator = 'AND'

    # Extract EXISTS clauses from old expression
    old_exists_clauses = extract_exists_clauses(old_expression)
    new_exists_clauses = extract_exists_clauses(new_exists_clause)

    logger.info(f"🔗 Filter Chaining: Combining {len(old_exists_clauses)} existing EXISTS with {len(new_exists_clauses)} new EXISTS")

    if old_exists_clauses:
        # Log existing spatial filters
        for i, clause in enumerate(old_exists_clauses):
            logger.debug(f"   → Old EXISTS #{i + 1}: table={clause['table']}")

    if new_exists_clauses:
        # Log new spatial filters
        for i, clause in enumerate(new_exists_clauses):
            logger.debug(f"   → New EXISTS #{i + 1}: table={clause['table']}")

    # Check if new_exists_clause is a valid EXISTS
    is_new_exists = new_exists_clause.strip().upper().startswith('EXISTS')

    if is_new_exists:
        # Both are EXISTS - combine with operator
        # Wrap each part in parentheses for clarity
        combined = f"({old_expression}) {combine_operator} ({new_exists_clause})"

        logger.info(f"   ✅ Combined with {combine_operator}: {len(combined)} chars")
        logger.debug(f"   → Preview: {combined[:200]}...")

        return combined
    else:
        # New expression is not an EXISTS (e.g., field condition)
        # Use standard combination
        combined = f"({old_expression}) {combine_operator} ({new_exists_clause})"

        logger.info(f"   ℹ️ Combined EXISTS with non-EXISTS condition: {len(combined)} chars")

        return combined


def build_chained_distant_filter(
    base_spatial_filter: str,
    new_source_exists: str,
    additional_conditions: Optional[List[str]] = None,
    combine_operator: str = 'AND'
) -> str:
    """
    Build complete filter for distant layer with multiple chained spatial conditions.

    v4.2.9: Main entry point for filter chaining on distant layers.

    Scenario (user's request):
        1. Filter 1: zone_pop → intersects all distant layers
        2. Filter 2: ducts (with buffer) → intersects distant layers while keeping zone_pop filter

    Result for "subducts" layer:
        EXISTS (SELECT 1 FROM zone_pop AS __source
                WHERE ST_Intersects(ST_PointOnSurface("subducts"."geom"), __source."geom")
                AND (__source."id" IN (...)))
        AND
        EXISTS (SELECT 1 FROM ducts AS __source
                WHERE ST_Intersects("subducts"."geom", ST_Buffer(__source."geom", 10)))

    Args:
        base_spatial_filter: First EXISTS filter (e.g., zone_pop)
        new_source_exists: Second EXISTS filter (e.g., ducts with buffer)
        additional_conditions: Optional list of non-spatial conditions to include
        combine_operator: How to combine filters ('AND' or 'OR')

    Returns:
        Complete chained filter expression
    """
    if not base_spatial_filter and not new_source_exists:
        return ""

    if not base_spatial_filter:
        base_expr = new_source_exists
    elif not new_source_exists:
        base_expr = base_spatial_filter
    else:
        # Chain the two EXISTS filters
        base_expr = chain_exists_filters(
            base_spatial_filter,
            new_source_exists,
            combine_operator
        )

    # Add additional conditions if provided
    if additional_conditions:
        for condition in additional_conditions:
            if condition and condition.strip():
                base_expr = f"({base_expr}) {combine_operator} ({condition.strip()})"

    logger.info(f"🎯 Built chained distant filter: {len(base_expr)} chars")
    logger.debug(f"   → Final: {base_expr[:300]}...")

    return base_expr


def detect_filter_chain_scenario(
    source_layer_subset: str,
    custom_expression: Optional[str],
    buffer_expression: Optional[str],
    has_combine_operator: bool
) -> Tuple[str, Dict]:
    """
    Detect the filter chaining scenario based on current state.

    v4.2.9: Analyzes the filtering context to determine the correct chaining strategy.

    Scenarios:
        A. "spatial_only": Only spatial filter (zone_pop), no custom expression
        B. "custom_only": Only custom expression, no spatial filter
        C. "spatial_with_custom": Spatial filter + custom expression (exploring mode)
        D. "spatial_chain": Spatial filter + new spatial filter (buffer) - CHAIN BOTH
        E. "spatial_chain_with_custom": All three - CHAIN spatial, ignore custom for distant

    Args:
        source_layer_subset: Current subsetString of source layer
        custom_expression: Custom expression for exploring
        buffer_expression: Buffer expression for new spatial filter
        has_combine_operator: Whether combine operator is active

    Returns:
        Tuple of (scenario_name, context_dict)
    """
    context = {
        'has_spatial_filter': False,
        'has_custom_expression': bool(custom_expression and custom_expression.strip()),
        'has_buffer_expression': bool(buffer_expression and buffer_expression.strip()),
        'has_combine_operator': has_combine_operator,
        'spatial_exists_clauses': []
    }

    # Check for spatial filter (EXISTS clauses)
    if source_layer_subset:
        exists_clauses = extract_exists_clauses(source_layer_subset)
        context['has_spatial_filter'] = len(exists_clauses) > 0
        context['spatial_exists_clauses'] = exists_clauses

    # Determine scenario
    if context['has_spatial_filter'] and context['has_buffer_expression']:
        if context['has_custom_expression']:
            scenario = 'spatial_chain_with_custom'
            logger.info("🔗 Filter Chain Scenario: SPATIAL_CHAIN_WITH_CUSTOM")
            logger.info("   → Spatial filter + buffer expression + custom expression")
            logger.info("   → Strategy: Chain spatial filters, custom expression for source only")
        else:
            scenario = 'spatial_chain'
            logger.info("🔗 Filter Chain Scenario: SPATIAL_CHAIN")
            logger.info("   → Spatial filter + buffer expression")
            logger.info("   → Strategy: Chain both spatial filters for distant layers")
    elif context['has_spatial_filter'] and context['has_custom_expression']:
        scenario = 'spatial_with_custom'
        logger.info("🔗 Filter Chain Scenario: SPATIAL_WITH_CUSTOM")
        logger.info("   → Spatial filter + custom expression (exploring)")
    elif context['has_spatial_filter']:
        scenario = 'spatial_only'
        logger.info("🔗 Filter Chain Scenario: SPATIAL_ONLY")
    elif context['has_custom_expression']:
        scenario = 'custom_only'
        logger.info("🔗 Filter Chain Scenario: CUSTOM_ONLY")
    else:
        scenario = 'none'
        logger.info("🔗 Filter Chain Scenario: NONE")

    return scenario, context


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

    logger.debug("FilterMate: Comparing expressions:")
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

    # SPECIAL CASE: EXISTS subquery pattern (re-filtering already filtered layer)
    # When old_subset contains EXISTS, we MUST combine carefully to ensure sequential filtering
    old_subset_upper = old_subset.upper()
    has_exists = 'EXISTS (' in old_subset_upper or 'EXISTS(' in old_subset_upper

    if has_exists:
        logger.info("FilterMate: Detected EXISTS pattern in old_subset")
        logger.info(f"  → Old subset (truncated): {old_subset[:150]}...")
        logger.info(f"  → New expression: {new_expression}")
        logger.info(f"  → Combine operator: {combine_operator}")

        # Strip leading "WHERE " from new_expression if present
        clean_new_expression = new_expression.lstrip()
        if clean_new_expression.upper().startswith('WHERE '):
            clean_new_expression = clean_new_expression[6:].lstrip()
            logger.debug(f"Stripped WHERE prefix from new_expression: '{clean_new_expression[:50]}...'")

        if combine_operator == 'AND':
            # Combine EXISTS with new filter - both conditions must be true
            # PostgreSQL will evaluate: rows where EXISTS(...) is true AND (new_filter) is true
            # This correctly filters the already-filtered data
            combined = f'( {old_subset} ) AND ( {clean_new_expression} )'
            logger.info(
                "FilterMate: Combined EXISTS with attribute filter using AND"
            )
            logger.info(f"  → Result (truncated): {combined[:200]}...")
        elif combine_operator in ('OR', 'AND NOT'):
            # For OR/AND NOT with EXISTS: Simple combination
            combined = f'( {old_subset} ) {combine_operator} ( {clean_new_expression} )'
            logger.info(
                f"FilterMate: Combined EXISTS with new filter using {combine_operator} operator"
            )
        else:
            # REPLACE mode (combine_operator is None)
            logger.warning(
                "FilterMate: REPLACE mode with EXISTS pattern - old EXISTS filter will be LOST"
            )
            combined = clean_new_expression

    # Extract WHERE clause from old subset if present
    elif old_subset.find('WHERE') != -1:
        index_where = old_subset.find('WHERE')
        param_old_subset_where = old_subset[index_where:]
        param_source_old_subset = old_subset[:index_where]

        # Remove trailing )) if present (legacy handling for malformed expressions)
        if param_old_subset_where.endswith('))'):
            param_old_subset_where = param_old_subset_where[:-1]

        # FIX 2026-01-16: Strip leading "WHERE " from new_expression to prevent "WHERE WHERE" syntax error
        clean_new_expression = new_expression.lstrip()
        if clean_new_expression.upper().startswith('WHERE '):
            clean_new_expression = clean_new_expression[6:].lstrip()
            logger.debug(f"Stripped WHERE prefix from new_expression: '{clean_new_expression[:50]}...'")

        combined = (
            f'{param_source_old_subset} {param_old_subset_where} '
            f'{combine_operator} ( {clean_new_expression} )'
        )
    else:
        # No WHERE clause - simple combination
        combined = f'( {old_subset} ) {combine_operator} ( {new_expression} )'

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
                f"{100 * savings / original_len:.1f}% reduction)"
            )
            return optimized

    return combined


def should_replace_old_subset(old_subset: str) -> tuple:
    """
    Check if old subset contains patterns that should trigger replacement instead of combination.

    Patterns that require replacement:
    - __source alias OUTSIDE of EXISTS subqueries (invalid context)
    - FilterMate materialized view references
    - QGIS style/symbology expressions

    NOTE: EXISTS subqueries and spatial predicates are now combinable (v4.2.8+).
    These patterns no longer trigger automatic replacement.
    __source INSIDE EXISTS is valid and should NOT trigger replacement (v4.2.9).

    Args:
        old_subset: Existing subset string to check

    Returns:
        tuple: (should_replace: bool, reasons: list of str)
    """
    import re

    if not old_subset:
        return False, []

    reasons = []
    old_subset.upper()

    # Pattern 1: __source alias - ONLY if OUTSIDE of EXISTS subqueries
    # v4.2.9 FIX: __source INSIDE EXISTS is valid (self-contained alias scope)
    # Only trigger replacement if __source appears OUTSIDE EXISTS context
    if '__source' in old_subset.lower():
        # Check if ALL occurrences of __source are inside EXISTS
        # If any __source is OUTSIDE EXISTS, trigger replacement
        exists_clauses = extract_exists_clauses(old_subset)
        if exists_clauses:
            # Extract all EXISTS SQL
            ' '.join([c['sql'] for c in exists_clauses])

            # Remove EXISTS portions from old_subset to check remaining
            remaining = old_subset
            for clause in sorted(exists_clauses, key=lambda c: c['start'], reverse=True):
                remaining = remaining[:clause['start']] + remaining[clause['end']:]

            # If __source still exists in remaining (outside EXISTS), that's invalid
            if '__source' in remaining.lower():
                reasons.append("__source alias outside EXISTS context")
                logger.debug("   ⚠️ Found __source OUTSIDE EXISTS - will replace")
            else:
                # All __source are inside EXISTS - this is VALID for chaining!
                logger.debug("   ✅ All __source references inside EXISTS - combinable")
        else:
            # No EXISTS found but __source present - invalid
            reasons.append("__source alias without EXISTS context")

    # Pattern 2: EXISTS subquery - NO LONGER TRIGGERS REPLACEMENT (v4.2.8+)
    # We can now combine EXISTS patterns intelligently: EXISTS(...) AND (new_filter)
    # if 'EXISTS (' in old_subset_upper or 'EXISTS(' in old_subset_upper:
    #     reasons.append("EXISTS subquery")

    # Pattern 3: Spatial predicates - NO LONGER TRIGGERS REPLACEMENT (v4.2.8+)
    # Spatial filters can be combined with attribute filters
    # spatial_predicates = [
    #     'ST_INTERSECTS', 'ST_CONTAINS', 'ST_WITHIN', 'ST_TOUCHES',
    #     'ST_OVERLAPS', 'ST_CROSSES', 'ST_DISJOINT', 'ST_EQUALS',
    #     'ST_DWITHIN', 'ST_COVERS', 'ST_COVEREDBY'
    # ]
    # if any(pred in old_subset_upper for pred in spatial_predicates):
    #     reasons.append("spatial predicate")

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

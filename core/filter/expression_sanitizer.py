"""
Expression Sanitizer Module

EPIC-1 Phase E3: Extracted from modules/tasks/filter_task.py

Provides expression sanitization and optimization:
- Remove non-boolean display expressions (coalesce, CASE)
- Normalize French SQL operators (ET, OU, NON → AND, OR, NOT)
- Fix unbalanced parentheses
- Optimize duplicate IN clauses
- Clean up orphaned operators and whitespace

Used to clean expressions before applying as SQL WHERE clauses.

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase E3)
"""

import logging
import re
from typing import Optional

logger = logging.getLogger('FilterMate.Core.Filter.Sanitizer')


def sanitize_subset_string(subset_string: str) -> str:
    """
    Remove non-boolean display expressions and fix type casting issues in subset string.

    Display expressions like 'coalesce("field",'<NULL>')' or CASE expressions that
    return true/false are valid QGIS expressions but cause issues in SQL WHERE clauses.
    This function removes such expressions and fixes common type casting issues.

    Process:
    1. Normalize French SQL operators (ET/OU/NON → AND/OR/NOT)
    2. Remove non-boolean display expressions (coalesce, CASE)
    3. Fix unbalanced parentheses
    4. Clean up whitespace and orphaned operators

    Args:
        subset_string: The original subset string

    Returns:
        str: Sanitized subset string with non-boolean expressions removed
    """
    if not subset_string:
        return subset_string

    sanitized = subset_string

    # ========================================================================
    # PHASE 0: Normalize French SQL operators to English
    # ========================================================================
    # QGIS expressions support French operators (ET, OU, NON) but PostgreSQL
    # only understands English operators (AND, OR, NOT). This normalization
    # ensures compatibility with all SQL backends.
    #
    # FIX v2.5.12: Handle French operators that cause SQL syntax errors like:
    # "syntax error at or near 'ET'"

    french_operators = [
        (r'\)\s+ET\s+\(', ') AND ('),      # ) ET ( -> ) AND (
        (r'\)\s+OU\s+\(', ') OR ('),       # ) OU ( -> ) OR (
        (r'\s+ET\s+', ' AND '),            # ... ET ... -> ... AND ...
        (r'\s+OU\s+', ' OR '),             # ... OU ... -> ... OR ...
        (r'\s+ET\s+NON\s+', ' AND NOT '),  # ET NON -> AND NOT
        (r'\s+NON\s+', ' NOT '),           # NON ... -> NOT ...
    ]

    for pattern, replacement in french_operators:
        if re.search(pattern, sanitized, re.IGNORECASE):
            logger.info(
                f"FilterMate: Normalizing French operator '{pattern}' to '{replacement}'"
            )
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

    # ========================================================================
    # PHASE 1: Remove non-boolean display expressions
    # ========================================================================

    # Pattern to match AND/OR followed by coalesce display expressions
    # CRITICAL: These patterns must match display expressions that return values, not booleans
    # Example: AND ( COALESCE( "LABEL", '<NULL>' ) ) - returns text, not boolean
    # Note: The outer ( ) wraps coalesce(...) with possible spaces
    #
    # FIX v2.5.13: Handle spaces INSIDE COALESCE( ... ) and around parentheses
    # Real-world example that FAILED: AND ( COALESCE( "LABEL", '<NULL>' ) )
    coalesce_patterns = [
        # Match coalesce with spaces everywhere: AND ( COALESCE( "field", '<NULL>' ) )
        # This handles the PostgreSQL-generated format with spaces
        r'(?:^|\s+)AND\s+\(\s*COALESCE\s*\(\s*"[^"]+"\s*,\s*\'[^\']*\'\s*\)\s*\)',
        r'(?:^|\s+)OR\s+\(\s*COALESCE\s*\(\s*"[^"]+"\s*,\s*\'[^\']*\'\s*\)\s*\)',
        # Match coalesce with quoted string containing special chars like '<NULL>'
        # Pattern: AND (coalesce("field",'<NULL>'))  - compact format
        r'(?:^|\s+)AND\s+\(\s*coalesce\s*\(\s*"[^"]+"\s*,\s*\'[^\']*\'\s*\)\s*\)',
        r'(?:^|\s+)OR\s+\(\s*coalesce\s*\(\s*"[^"]+"\s*,\s*\'[^\']*\'\s*\)\s*\)',
        # Match AND/OR followed by coalesce expression with nested content
        r'(?:^|\s+)AND\s+\(\s*coalesce\s*\([^)]*(?:\([^)]*\)[^)]*)*\)\s*\)',
        r'(?:^|\s+)OR\s+\(\s*coalesce\s*\([^)]*(?:\([^)]*\)[^)]*)*\)\s*\)',
        # Simpler patterns for common cases
        r'(?:^|\s+)AND\s+\(\s*coalesce\s*\([^)]+\)\s*\)',
        r'(?:^|\s+)OR\s+\(\s*coalesce\s*\([^)]+\)\s*\)',
        # Match table.field syntax
        r'(?:^|\s+)AND\s+\(\s*coalesce\s*\(\s*"[^"]+"\s*\.\s*"[^"]+"\s*,\s*\'[^\']*\'\s*\)\s*\)',
        r'(?:^|\s+)OR\s+\(\s*coalesce\s*\(\s*"[^"]+"\s*\.\s*"[^"]+"\s*,\s*\'[^\']*\'\s*\)\s*\)',
    ]

    for pattern in coalesce_patterns:
        match = re.search(pattern, sanitized, re.IGNORECASE)
        if match:
            logger.info(
                "FilterMate: Removing invalid coalesce expression: "
                f"'{match.group()[:60]}...'"
            )
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)

    # Pattern to match AND/OR followed by CASE expressions that just return true/false
    # These are style/display expressions, not filter conditions
    # Match: AND ( case when ... end ) OR AND ( SELECT CASE when ... end )
    # with multiple closing parentheses (malformed)
    #
    # CRITICAL FIX v2.5.10: Improved patterns to handle multi-line CASE expressions
    # like those from rule-based symbology:
    #   AND ( SELECT CASE
    #     WHEN 'AV' = left("table"."field", 2) THEN true
    #     WHEN 'PL' = left("table"."field", 2) THEN true
    #     ...
    #   end )

    # IMPROVED PATTERN: Match AND ( SELECT CASE ... WHEN ... THEN true/false ... end )
    # This pattern is more robust for multi-line expressions from QGIS rule-based symbology
    select_case_pattern = (
        r'\s*AND\s+\(\s*SELECT\s+CASE\s+'
        r'(?:WHEN\s+.+?THEN\s+(?:true|false)\s*)+'
        r'\s*(?:ELSE\s+.+?)?\s*end\s*\)'
    )

    match = re.search(select_case_pattern, sanitized, re.IGNORECASE | re.DOTALL)
    if match:
        logger.info(
            f"FilterMate: Removing SELECT CASE style expression: '{match.group()[:80]}...'"  # nosec B608
        )
        sanitized = re.sub(
            select_case_pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL
        )

    # Also check for simpler CASE patterns without SELECT
    case_patterns = [
        # Standard CASE expression with true/false returns
        (r'\s*AND\s+\(\s*CASE\s+(?:WHEN\s+.+?THEN\s+(?:true|false)\s*)+'
         r'(?:ELSE\s+.+?)?\s*END\s*\)+'),
        (r'\s*OR\s+\(\s*CASE\s+(?:WHEN\s+.+?THEN\s+(?:true|false)\s*)+'
         r'(?:ELSE\s+.+?)?\s*END\s*\)+'),
        # SELECT CASE expression (from rule-based styles) - backup pattern
        r'\s*AND\s+\(\s*SELECT\s+CASE\s+.+?\s+END\s*\)+',
        r'\s*OR\s+\(\s*SELECT\s+CASE\s+.+?\s+END\s*\)+',
    ]

    for pattern in case_patterns:
        match = re.search(pattern, sanitized, re.IGNORECASE | re.DOTALL)
        if match:
            # Verify this is a display/style expression (returns true/false, not a comparison)
            matched_text = match.group()
            # Check if it's just "then true/false" without external comparison
            if re.search(r'\bTHEN\s+(true|false)\b', matched_text, re.IGNORECASE):
                logger.info(
                    "FilterMate: Removing invalid CASE/style expression: "
                    f"'{matched_text[:60]}...'"
                )
                sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)

    # Remove standalone coalesce expressions at start
    # FIX v2.5.13: Handle spaces inside coalesce expressions
    standalone_coalesce = r'^\s*\(\s*coalesce\s*\([^)]*(?:\([^)]*\)[^)]*)*\)\s*\)\s*(?:AND|OR)?'
    if re.match(standalone_coalesce, sanitized, re.IGNORECASE):
        match = re.match(standalone_coalesce, sanitized, re.IGNORECASE)
        logger.info(f"FilterMate: Removing standalone coalesce: '{match.group()[:60]}...'")
        sanitized = re.sub(standalone_coalesce, '', sanitized, flags=re.IGNORECASE)

    # ========================================================================
    # PHASE 2: Fix unbalanced parentheses
    # ========================================================================

    # Count parentheses and fix if unbalanced
    open_count = sanitized.count('(')
    close_count = sanitized.count(')')

    if close_count > open_count:
        # Remove excess closing parentheses from the end
        excess = close_count - open_count
        # Remove trailing )))) patterns
        trailing_parens = re.search(r'\)+\s*$', sanitized)
        if trailing_parens:
            parens_at_end = len(trailing_parens.group().strip())
            if parens_at_end >= excess:
                sanitized = re.sub(r'\){' + str(excess) + r'}\s*$', '', sanitized)
                logger.info(f"FilterMate: Removed {excess} excess closing parentheses")

    # ========================================================================
    # PHASE 2.5: Remove non-boolean field references
    # ========================================================================
    # FIX v4.8.0 (2026-01-25): Handle PostgreSQL type errors
    #
    # Problem: QGIS expressions can generate clauses like:
    #   1. AND ("field_name") - a text/varchar field used as boolean
    #   2. AND ("field"::type < value) - comparison without proper type casting
    #
    # Error 1: "argument of AND must be type boolean, not type character varying"
    # Error 2: "operator does not exist: character varying < integer"
    #
    # These typically come from rule-based symbology expressions or display expressions
    # that return the field value itself rather than a boolean comparison.

    # Pattern to match: AND ( "field_name" ) - field reference without comparison operator
    # This matches: AND ( "any_field" ) where there's no =, <, >, IN, LIKE, IS, etc.
    #
    # The pattern looks for:
    # - AND/OR followed by opening paren
    # - Optional whitespace
    # - Quoted field name (with optional table prefix)
    # - Optional whitespace
    # - Closing paren
    # - NO comparison operators (=, <, >, !, IN, LIKE, IS, BETWEEN, etc.)

    non_boolean_field_patterns = [
        # Simple field reference: AND ( "field" )
        r'\s+AND\s+\(\s*"[^"]+"\s*\)(?!\s*[=<>!])',
        # Table.field reference: AND ( "table"."field" )
        r'\s+AND\s+\(\s*"[^"]+"\s*\.\s*"[^"]+"\s*\)(?!\s*[=<>!])',
        # Field with cast but no comparison: AND ( "field"::type )
        r'\s+AND\s+\(\s*"[^"]+"(?:::\w+)?\s*\)(?!\s*[=<>!])',
        # OR variants
        r'\s+OR\s+\(\s*"[^"]+"\s*\)(?!\s*[=<>!])',
        r'\s+OR\s+\(\s*"[^"]+"\s*\.\s*"[^"]+"\s*\)(?!\s*[=<>!])',
    ]

    for pattern in non_boolean_field_patterns:
        match = re.search(pattern, sanitized, re.IGNORECASE)
        if match:
            matched_text = match.group()
            logger.info(
                "FilterMate: Removing non-boolean field expression (PostgreSQL type error fix): "
                f"'{matched_text[:60]}'"
            )
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)

    # ========================================================================
    # PHASE 3: Clean up whitespace and orphaned operators
    # ========================================================================

    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    sanitized = re.sub(r'\s+(AND|OR)\s*$', '', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'^\s*(AND|OR)\s+', '', sanitized, flags=re.IGNORECASE)

    # Remove duplicate AND/OR operators
    sanitized = re.sub(r'\s+AND\s+AND\s+', ' AND ', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'\s+OR\s+OR\s+', ' OR ', sanitized, flags=re.IGNORECASE)

    if sanitized != subset_string:
        logger.info(
            f"FilterMate: Subset sanitized from '{subset_string[:80]}...' "
            f"to '{sanitized[:80]}...'"
        )

    return sanitized


def optimize_duplicate_in_clauses(expression: str) -> str:
    """
    Remove duplicate IN clauses from an expression.

    OPTIMIZATION v2.5.13: Multi-step filtering generates duplicate clauses like:
    (A AND fid IN (1,2,3)) AND (fid IN (1,2,3)) AND (fid IN (1,2,3))

    This function detects and removes the duplicates, keeping only ONE IN clause per field.

    Args:
        expression: SQL expression potentially containing duplicate IN clauses

    Returns:
        str: Optimized expression with duplicate IN clauses removed
    """
    if not expression:
        return expression

    # Pattern to match "field" IN (...) or "table"."field" IN (...)
    pattern = r'"([^"]+)"(?:\."([^"]+)")?\s+IN\s*\([^)]+\)'
    matches = list(re.finditer(pattern, expression, re.IGNORECASE))

    if len(matches) <= 1:
        return expression  # No duplicates possible

    # Group matches by field name
    field_matches = {}
    for match in matches:
        if match.group(2):
            field_key = f'"{match.group(1)}"."{match.group(2)}"'
        else:
            field_key = f'"{match.group(1)}"'

        if field_key not in field_matches:
            field_matches[field_key] = []
        field_matches[field_key].append(match)

    # Check for duplicates (more than one IN clause for same field)
    has_duplicates = False
    for field_key, field_match_list in field_matches.items():
        if len(field_match_list) > 1:
            has_duplicates = True
            logger.info(
                f"FilterMate: OPTIMIZATION - Found {len(field_match_list)} "
                f"duplicate IN clauses for {field_key}"
            )

    if not has_duplicates:
        return expression

    # Remove duplicates - keep first occurrence, remove subsequent ones
    result = expression
    for field_key, field_match_list in field_matches.items():
        if len(field_match_list) <= 1:
            continue

        # Process from end to start to preserve indices
        for match in reversed(field_match_list[1:]):
            start, end = match.span()

            # Find the surrounding AND operator and parentheses
            # Look for " AND (" before the match
            search_start = max(0, start - 20)
            before = result[search_start:start]

            # Pattern: " AND (" or " AND " before the IN clause
            and_pattern = r'\s+AND\s+\(\s*$'
            and_match = re.search(and_pattern, before, re.IGNORECASE)

            if and_match:
                # Find corresponding closing paren after the IN clause
                actual_start = search_start + and_match.start()
                depth = 0
                close_pos = end

                for i, char in enumerate(result[actual_start:], actual_start):
                    if char == '(':
                        depth += 1
                    elif char == ')':
                        depth -= 1
                        if depth == 0:
                            close_pos = i + 1
                            break

                # Remove " AND ( ... IN (...) )"
                result = result[:actual_start] + result[close_pos:]
                logger.debug(f"FilterMate: Removed duplicate clause for {field_key}")

    # Clean up any double spaces or malformed syntax
    result = re.sub(r'\s+', ' ', result)
    result = re.sub(r'\(\s*\)', '', result)  # Remove empty parens
    result = re.sub(r'AND\s+AND', 'AND', result, flags=re.IGNORECASE)
    result = re.sub(r'\(\s*AND', '(', result, flags=re.IGNORECASE)
    result = re.sub(r'AND\s*\)', ')', result, flags=re.IGNORECASE)

    # Log optimization results
    if len(result) < len(expression):
        savings = len(expression) - len(result)
        pct = 100 * savings / len(expression)
        logger.info(
            f"FilterMate: OPTIMIZATION - Reduced expression by {savings} bytes "
            f"({pct:.1f}% reduction)"
        )

    return result.strip()


def extract_spatial_clauses_for_exists(filter_expr: str, source_table: Optional[str] = None) -> Optional[str]:
    """
    Extract only spatial clauses (ST_Intersects, etc.) from a filter expression.

    EPIC-1 Phase E7.5: Extracted from filter_task.py _extract_spatial_clauses_for_exists.

    CRITICAL FIX v2.5.11: For EXISTS subqueries in PostgreSQL, we must include
    the source layer's spatial filter to ensure we only consider filtered features.
    However, we must EXCLUDE:
    - Style-based rules (SELECT CASE ... THEN true/false)
    - Attribute-only filters (without spatial predicates)
    - coalesce display expressions

    This ensures the EXISTS query sees the same filtered source as QGIS.

    Args:
        filter_expr: The source layer's current subsetString
        source_table: Source table name for reference replacement (unused, kept for API)

    Returns:
        str: Extracted spatial clauses only, or None if no spatial predicates found
    """
    if not filter_expr:
        return None

    # List of spatial predicates to extract
    SPATIAL_PREDICATES = [
        'ST_Intersects', 'ST_Contains', 'ST_Within', 'ST_Touches',
        'ST_Overlaps', 'ST_Crosses', 'ST_Disjoint', 'ST_Equals',
        'ST_DWithin', 'ST_Covers', 'ST_CoveredBy'
    ]

    # Check if filter contains any spatial predicates
    filter_upper = filter_expr.upper()
    has_spatial = any(pred.upper() in filter_upper for pred in SPATIAL_PREDICATES)

    if not has_spatial:
        logger.debug("extract_spatial_clauses: No spatial predicates in filter")
        return None

    # First, remove style-based expressions (SELECT CASE ... THEN true/false)
    cleaned = filter_expr

    # Pattern for SELECT CASE style rules (multi-line support)
    select_case_pattern = r'\s*AND\s+\(\s*SELECT\s+CASE\s+(?:WHEN\s+.+?THEN\s+(?:true|false)\s*)+\s*(?:ELSE\s+.+?)?\s*end\s*\)'
    cleaned = re.sub(select_case_pattern, '', cleaned, flags=re.IGNORECASE | re.DOTALL)

    # Pattern for simple CASE style rules
    case_pattern = r'\s*AND\s+\(\s*CASE\s+(?:WHEN\s+.+?THEN\s+(?:true|false)\s*)+(?:ELSE\s+.+?)?\s*END\s*\)+'
    cleaned = re.sub(case_pattern, '', cleaned, flags=re.IGNORECASE | re.DOTALL)

    # Remove coalesce display expressions
    # FIX v2.5.13: Handle spaces inside COALESCE( ... )
    coalesce_pattern = r'\s*(?:AND|OR)\s+\(\s*coalesce\s*\([^)]*(?:\([^)]*\)[^)]*)*\)\s*\)'
    cleaned = re.sub(coalesce_pattern, '', cleaned, flags=re.IGNORECASE)

    # Clean up whitespace and operators
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = re.sub(r'\s+(AND|OR)\s*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^\s*(AND|OR)\s+', '', cleaned, flags=re.IGNORECASE)

    # Remove outer parentheses if present
    while cleaned.startswith('(') and cleaned.endswith(')'):
        # Check if these are matching outer parens
        depth = 0
        is_outer = True
        for i, char in enumerate(cleaned):
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if depth == 0 and i < len(cleaned) - 1:
                    is_outer = False
                    break
        if is_outer and depth == 0:
            cleaned = cleaned[1:-1].strip()
        else:
            break

    # Verify cleaned expression still contains spatial predicates
    cleaned_upper = cleaned.upper()
    has_spatial_after_clean = any(pred.upper() in cleaned_upper for pred in SPATIAL_PREDICATES)

    if not has_spatial_after_clean:
        logger.debug("extract_spatial_clauses: Spatial predicates removed during cleaning")
        return None

    # Validate parentheses are balanced
    if cleaned.count('(') != cleaned.count(')'):
        logger.warning("extract_spatial_clauses: Unbalanced parentheses after extraction")
        return None

    logger.info(f"extract_spatial_clauses: Extracted spatial filter: '{cleaned[:100]}...'")
    return cleaned

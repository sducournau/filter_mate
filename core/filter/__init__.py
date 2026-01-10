"""
Filter Expression Module

EPIC-1 Phase E3: Extracted from modules/tasks/filter_task.py

This module provides filter expression operations:
- Expression building and combination
- Expression sanitization and optimization
- Primary key formatting for SQL
- Expression combiners (AND, OR, NOT, REPLACE)

Used by FilterEngineTask for building complex filter expressions.

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase E3)
"""

# Expression builders
from core.filter.expression_builder import (
    build_feature_id_expression,
    build_combined_filter_expression,
)

# Expression sanitizers
from core.filter.expression_sanitizer import (
    sanitize_subset_string,
    optimize_duplicate_in_clauses,
)

# PK formatters
from core.filter.pk_formatter import (
    is_pk_numeric,
    format_pk_values_for_sql,
)

# Expression combiners
from core.filter.expression_combiner import (
    apply_combine_operator,
    combine_with_old_subset,
    CombineOperator,
)

__all__ = [
    # Builders
    'build_feature_id_expression',
    'build_combined_filter_expression',
    # Sanitizers
    'sanitize_subset_string',
    'optimize_duplicate_in_clauses',
    # PK formatters
    'is_pk_numeric',
    'format_pk_values_for_sql',
    # Combiners
    'apply_combine_operator',
    'combine_with_old_subset',
    'CombineOperator',
]

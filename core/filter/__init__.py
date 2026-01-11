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

# Source filter builders (Phase E5)
from core.filter.source_filter_builder import (
    should_skip_source_subset,
    get_primary_key_field,
    get_source_table_name,
    extract_feature_ids,
    build_source_filter_inline,
    build_source_filter_with_mv,
    get_visible_feature_ids,
    get_source_wkt_and_srid,
    get_source_feature_count,
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
    # Source filter builders (Phase E5)
    'should_skip_source_subset',
    'get_primary_key_field',
    'get_source_table_name',
    'extract_feature_ids',
    'build_source_filter_inline',
    'build_source_filter_with_mv',
    'get_visible_feature_ids',
    'get_source_wkt_and_srid',
    'get_source_feature_count',
]

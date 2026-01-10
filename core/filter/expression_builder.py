"""
Expression Builder Module

EPIC-1 Phase E3: Extracted from modules/tasks/filter_task.py

Provides filter expression building operations:
- Feature ID expressions (IN clauses)
- Combined filter expressions with optimization
- Provider-specific syntax handling

Used by FilterEngineTask for building SQL filter expressions.

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase E3)
"""

import logging
from typing import List, Optional

logger = logging.getLogger('FilterMate.Core.Filter.Builder')


def build_feature_id_expression(
    features_ids: List[str],
    primary_key_name: str,
    table_name: Optional[str],
    provider_type: str,
    is_numeric: bool = True
) -> str:
    """
    Build SQL IN expression from list of feature IDs.
    
    Handles provider-specific syntax:
    - PostgreSQL: "table"."pk" IN (...)
    - Spatialite/OGR: "pk" IN (...) or fid IN (unquoted for compatibility)
    
    Args:
        features_ids: List of feature ID values (as strings)
        primary_key_name: Primary key field name
        table_name: Table name (optional, used for PostgreSQL qualified syntax)
        provider_type: Provider type ('postgresql', 'spatialite', 'ogr')
        is_numeric: Whether PK is numeric (affects quoting)
        
    Returns:
        str: SQL IN expression
    """
    if not features_ids:
        return ""
    
    # CRITICAL FIX v2.8.10: Use unquoted 'fid' for OGR/GeoPackage compatibility
    # OGR driver does NOT support quoted "fid" in setSubsetString()
    if provider_type == 'ogr':
        pk_ref = 'fid' if primary_key_name == 'fid' else f'"{primary_key_name}"'
        if is_numeric:
            return f'{pk_ref} IN ({", ".join(features_ids)})'
        else:
            return f'{pk_ref} IN ({", ".join(repr(fid) for fid in features_ids)})'
    
    elif provider_type == 'spatialite':
        pk_ref = 'fid' if primary_key_name == 'fid' else f'"{primary_key_name}"'
        if is_numeric:
            return f'{pk_ref} IN ({", ".join(features_ids)})'
        else:
            return f'{pk_ref} IN ({", ".join(repr(fid) for fid in features_ids)})'
    
    else:  # PostgreSQL
        if is_numeric:
            if table_name:
                return f'"{table_name}"."{primary_key_name}" IN ({", ".join(features_ids)})'
            else:
                return f'"{primary_key_name}" IN ({", ".join(features_ids)})'
        else:
            if table_name:
                return (
                    f'"{table_name}"."{primary_key_name}" IN '
                    f"({', '.join(repr(fid) for fid in features_ids)})"
                )
            else:
                return f'"{primary_key_name}" IN ({", ".join(repr(fid) for fid in features_ids)})'


def build_combined_filter_expression(
    new_expression: str,
    old_subset: Optional[str],
    combine_operator: Optional[str],
    sanitize_fn: Optional[callable] = None
) -> str:
    """
    Combine new filter expression with existing subset using specified operator.
    
    Used for combining new spatial/attribute filters with existing layer filters.
    
    Args:
        new_expression: New filter expression to apply
        old_subset: Existing subset string from layer (optional)
        combine_operator: SQL operator ('AND', 'OR', 'NOT') (optional)
        sanitize_fn: Optional callback to sanitize old_subset
            Signature: sanitize_fn(subset: str) -> str
            
    Returns:
        str: Combined filter expression
    """
    if not old_subset or not combine_operator:
        return new_expression
    
    # Sanitize old_subset to remove non-boolean display expressions
    if sanitize_fn:
        old_subset = sanitize_fn(old_subset)
        if not old_subset:
            return new_expression
    
    # Extract WHERE clause from old subset if present
    param_old_subset_where_clause = ''
    param_source_old_subset = old_subset
    
    index_where_clause = old_subset.find('WHERE')
    if index_where_clause > -1:
        param_old_subset_where_clause = old_subset[index_where_clause:]
        if param_old_subset_where_clause.endswith('))'):
            param_old_subset_where_clause = param_old_subset_where_clause[:-1]
        param_source_old_subset = old_subset[:index_where_clause]
    
    # Combine expressions
    if index_where_clause > -1:
        # Has WHERE clause - combine with existing structure
        return (
            f'{param_source_old_subset} {param_old_subset_where_clause} '
            f'{combine_operator} {new_expression}'
        )
    else:
        # No WHERE clause - wrap both in parentheses for safety
        return f'( {old_subset} ) {combine_operator} ( {new_expression} )'

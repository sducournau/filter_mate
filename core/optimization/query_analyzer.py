"""
Query Analyzer Module

EPIC-1 Phase E7.5: Extracted from modules/tasks/filter_task.py

Provides SQL query analysis for:
- Detecting expensive spatial patterns
- Identifying queries that should be materialized
- Checking query complexity

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase E7.5)
"""

import logging
from typing import Optional

logger = logging.getLogger('FilterMate.Core.Optimization.QueryAnalyzer')


def has_expensive_spatial_expression(sql_string: str) -> bool:
    """
    Detect if a SQL expression contains expensive spatial predicates that should be materialized.
    
    Expensive patterns detected:
    - EXISTS with ST_Intersects/ST_Contains/ST_Within
    - EXISTS with ST_Buffer
    - Combination of MV reference AND EXISTS clause
    - __source alias with spatial predicate (indicates EXISTS subquery pattern)
    
    When a layer's subsetString contains expensive patterns, PostgreSQL must
    re-execute the expensive query for EVERY feature request from QGIS,
    causing slow rendering during pan/zoom operations.
    
    Solution: Materialize the result in a MV and use a simple 
    "fid IN (SELECT pk FROM mv)" as the subsetString.
    
    Args:
        sql_string: SQL expression or SELECT statement to analyze
        
    Returns:
        True if expression contains expensive patterns that should be materialized
    """
    if not sql_string:
        return False
    
    sql_upper = sql_string.upper()
    
    # Pattern 1: EXISTS clause with spatial predicate - always expensive
    # These are evaluated for every row and cannot use indexes efficiently in subqueries
    has_exists = 'EXISTS' in sql_upper or 'EXISTS(' in sql_upper
    has_spatial_predicate = any(pred in sql_upper for pred in [
        'ST_INTERSECTS', 'ST_CONTAINS', 'ST_WITHIN', 'ST_TOUCHES',
        'ST_OVERLAPS', 'ST_CROSSES', 'ST_COVERS', 'ST_COVEREDBY'
    ])
    
    # Pattern 2: ST_Buffer in subquery - very expensive as buffer is computed for each row
    has_buffer = 'ST_BUFFER' in sql_upper
    
    # Pattern 3: Combination patterns that are particularly expensive
    # EXISTS + spatial predicate = expensive (re-evaluated per row)
    if has_exists and has_spatial_predicate:
        logger.debug("Detected expensive pattern: EXISTS + spatial predicate")
        return True
    
    # EXISTS + ST_Buffer = very expensive (buffer computed per row)
    if has_exists and has_buffer:
        logger.debug("Detected expensive pattern: EXISTS + ST_Buffer")
        return True
    
    # Pattern 4: MV reference AND EXISTS - this is the multi-step filter case
    # Example: ("fid" IN (SELECT "pk" FROM "fm_temp_mv_xxx")) AND (EXISTS (...ST_Intersects...))
    # Supports both new (fm_temp_*) and legacy (filtermate_mv_*, mv_*) prefixes
    has_mv_reference = 'FM_TEMP_' in sql_upper or 'FILTERMATE_MV_' in sql_upper or 'MV_' in sql_upper
    if has_mv_reference and has_exists:
        logger.debug("Detected expensive pattern: MV reference + EXISTS clause")
        return True
    
    # Pattern 5: __source alias with spatial predicate - indicates EXISTS subquery pattern
    has_source_alias = '__SOURCE' in sql_upper
    if has_source_alias and has_spatial_predicate:
        logger.debug("Detected expensive pattern: __source alias + spatial predicate")
        return True
    
    return False


def is_complex_filter(subset: str, provider_type: str) -> bool:
    """
    Check if a filter expression is complex (requires longer refresh delay).
    
    Used to determine appropriate refresh timing after filter application.
    Complex filters include:
    - PostgreSQL: EXISTS, ST_Buffer, ST_Intersects, __source, large IN clauses
    - Spatialite: ST_*, Intersects, Contains, Within functions
    - OGR: Large IN clauses (>50 IDs) or expressions > 1000 chars
    
    Args:
        subset: The filter expression string
        provider_type: Layer provider type ('postgres', 'spatialite', 'ogr', 'postgresql')
        
    Returns:
        True if filter is complex, False otherwise
    """
    if not subset:
        return False
        
    subset_upper = subset.upper()
    
    # Normalize provider type
    if provider_type in ('postgres', 'postgresql'):
        return (
            'EXISTS' in subset_upper or
            'ST_BUFFER' in subset_upper or
            'ST_INTERSECTS' in subset_upper or
            'ST_CONTAINS' in subset_upper or
            'ST_WITHIN' in subset_upper or
            '__source' in subset.lower() or
            (subset_upper.count(',') > 100 and ' IN (' in subset_upper)
        )
    elif provider_type == 'spatialite':
        return (
            'ST_BUFFER' in subset_upper or
            'ST_INTERSECTS' in subset_upper or
            'ST_CONTAINS' in subset_upper or
            'ST_WITHIN' in subset_upper or
            'INTERSECTS(' in subset_upper or
            'CONTAINS(' in subset_upper or
            'WITHIN(' in subset_upper or
            (subset_upper.count(',') > 100 and ' IN (' in subset_upper)
        )
    elif provider_type == 'ogr':
        return (
            (subset_upper.count(',') > 50 and ' IN (' in subset_upper) or
            len(subset) > 1000
        )
    return False

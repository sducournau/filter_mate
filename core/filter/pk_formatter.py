"""
Primary Key Formatter Module

EPIC-1 Phase E3: Extracted from modules/tasks/filter_task.py

Provides formatting utilities for primary key values in SQL expressions.
Handles both numeric and text-based primary keys (UUID, varchar, etc.).

Critical fixes:
- v2.8.5: UUID fields must be quoted with single quotes in SQL
- Supports fid, ctid, and custom primary keys

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase E3)
"""

import logging
from typing import List, Optional

try:
    from qgis.core import QgsVectorLayer
except ImportError:
    QgsVectorLayer = None

logger = logging.getLogger('FilterMate.Core.Filter.PKFormatter')


def is_pk_numeric(
    layer: 'QgsVectorLayer',
    pk_field: str
) -> bool:
    """
    Check if the primary key field is numeric.
    
    CRITICAL FIX v2.8.5: UUID fields and other text-based PKs must be quoted in SQL.
    
    Args:
        layer: QgsVectorLayer to check
        pk_field: Primary key field name
        
    Returns:
        bool: True if PK is numeric (int, bigint, etc.), False if text (UUID, varchar, etc.)
    """
    if not layer or not pk_field:
        # Default to numeric for safety (most common case)
        return True
    
    try:
        field_idx = layer.fields().indexOf(pk_field)
        if field_idx >= 0:
            field = layer.fields().field(field_idx)
            return field.isNumeric()
    except Exception as e:
        logger.debug(f"Could not determine PK type, assuming numeric: {e}")
    
    return True


def format_pk_values_for_sql(
    values: List,
    is_numeric: Optional[bool] = None,
    layer: Optional['QgsVectorLayer'] = None,
    pk_field: Optional[str] = None
) -> str:
    """
    Format primary key values for SQL IN clause.
    
    CRITICAL FIX v2.8.5: UUID fields must be quoted with single quotes in SQL.
    
    Examples:
        - Numeric: IN (1, 2, 3)
        - UUID/Text: IN ('7b2e1a3e-b812-4d51-bf33-7f0cd0271ef3', ...)
    
    Args:
        values: List of primary key values
        is_numeric: Whether PK is numeric (optional, auto-detected if None)
        layer: QgsVectorLayer to check PK type (optional, for auto-detection)
        pk_field: Primary key field name (optional, for auto-detection)
        
    Returns:
        str: Comma-separated values formatted for SQL IN clause
    """
    if not values:
        return ''
    
    # Auto-detect if not specified
    if is_numeric is None:
        if layer and pk_field:
            is_numeric = is_pk_numeric(layer, pk_field)
        else:
            # Default to numeric
            is_numeric = True
    
    if is_numeric:
        # Numeric: simple conversion to string
        return ', '.join(str(v) for v in values)
    else:
        # Text/UUID: quote with single quotes, escape existing quotes
        formatted = []
        for v in values:
            # Convert to string and escape single quotes
            str_val = str(v).replace("'", "''")
            formatted.append(f"'{str_val}'")
        return ', '.join(formatted)

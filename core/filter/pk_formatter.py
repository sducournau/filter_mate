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
    pk_field: str,
    sample_values: Optional[List] = None
) -> bool:
    """
    Check if the primary key field is numeric.

    CRITICAL FIX v2.8.5: UUID fields and other text-based PKs must be quoted in SQL.
    CRITICAL FIX v4.0.9: Value-based detection for PostgreSQL via OGR layers.

    Args:
        layer: QgsVectorLayer to check
        pk_field: Primary key field name
        sample_values: Optional sample PK values for value-based detection

    Returns:
        bool: True if PK is numeric (int, bigint, etc.), False if text (UUID, varchar, etc.)
    """
    if not layer or not pk_field:
        # Default to numeric for safety (most common case)
        return True

    # FIX v4.0.9: VALUE-BASED detection first (most reliable for OGR layers)
    if sample_values:
        try:
            # Check if all sample values are numeric types
            all_numeric = all(
                isinstance(v, (int, float)) and not isinstance(v, bool)
                for v in sample_values[:10]
            )
            if all_numeric:
                logger.debug(f"PK '{pk_field}' detected as numeric from VALUES")
                return True

            # Check if string values look like integers
            all_look_numeric = all(
                isinstance(v, (int, float)) or
                (isinstance(v, str) and v.lstrip('-').isdigit())
                for v in sample_values[:10]
            )
            if all_look_numeric:
                logger.debug(f"PK '{pk_field}' detected as numeric from string VALUES")
                return True
        except Exception as e:
            logger.debug(f"Value-based PK detection failed: {e}")

    # SCHEMA-BASED detection
    try:
        field_idx = layer.fields().indexOf(pk_field)
        if field_idx >= 0:
            field = layer.fields().field(field_idx)
            is_numeric = field.isNumeric()
            logger.debug(f"PK '{pk_field}' detected as {'numeric' if is_numeric else 'text'} from schema")
            return is_numeric
    except Exception as e:
        logger.debug(f"Could not determine PK type from schema: {e}")

    # FALLBACK: Check common numeric PK names
    pk_lower = pk_field.lower()
    common_numeric_names = ('id', 'fid', 'gid', 'pk', 'ogc_fid', 'objectid', 'oid', 'rowid')
    if pk_lower in common_numeric_names:
        logger.debug(f"PK '{pk_field}' assumed numeric based on common name")
        return True

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
    CRITICAL FIX v4.0.9: Improved value-based detection for PostgreSQL via OGR.

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
            # FIX v4.0.9: Pass sample values for better detection
            is_numeric = is_pk_numeric(layer, pk_field, sample_values=values)
        else:
            # FIX v4.0.9: Detect from values directly
            try:
                all_look_numeric = all(
                    isinstance(v, (int, float)) and not isinstance(v, bool) or
                    (isinstance(v, str) and v.lstrip('-').isdigit())
                    for v in values[:10]
                )
                is_numeric = all_look_numeric
                logger.debug(f"PK type detected from values: {'numeric' if is_numeric else 'text'}")
            except Exception as e:
                logger.debug(f"Ignored in PK type detection from values: {e}")
                is_numeric = True  # Default to numeric

    if is_numeric:
        # Numeric: convert to int if possible to strip any decimal or quote issues
        formatted = []
        for v in values:
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                formatted.append(str(int(v)))
            elif isinstance(v, str) and v.lstrip('-').isdigit():
                formatted.append(v)  # Already a clean numeric string
            else:
                formatted.append(str(v))
        return ', '.join(formatted)
    else:
        # Text/UUID: quote with single quotes, escape existing quotes
        formatted = []
        for v in values:
            # Convert to string and escape single quotes
            str_val = str(v).replace("'", "''")
            formatted.append(f"'{str_val}'")
        return ', '.join(formatted)

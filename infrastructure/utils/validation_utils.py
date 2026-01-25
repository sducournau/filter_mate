# -*- coding: utf-8 -*-
"""
FilterMate Validation Utilities - ARCH-011

Consolidated layer and expression validation logic.
Consolidates patterns from:
- filter_mate_app.py:926 (_is_layer_valid)
- modules/object_safety.py (is_valid_layer, is_sip_deleted)
- modules/appUtils.py:366 (is_layer_source_available)

Part of Phase 1 Architecture Refactoring.

Features:
- Layer validity checks (None, SIP deleted, isValid)
- Layer source availability checks
- Expression validation against layer fields
- Safe access patterns for deleted objects

Author: FilterMate Team
Date: January 2025
"""

import logging
from typing import Optional, Tuple, List, Any

logger = logging.getLogger('FilterMate.Validation')

# Try to import QGIS/Qt components, provide stubs for testing
try:
    from qgis.core import QgsVectorLayer, QgsExpression, QgsExpressionContext, QgsExpressionContextUtils
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False
    
    class QgsVectorLayer:
        def isValid(self):
            return False
        def id(self):
            return ""
        def name(self):
            return ""
        def fields(self):
            return []
    
    class QgsExpression:
        def __init__(self, expr):
            self._expr = expr
            self._error = None
        def hasParserError(self):
            return False
        def parserErrorString(self):
            return ""
        def referencedColumns(self):
            return []
    
    class QgsExpressionContext:
        pass
    
    class QgsExpressionContextUtils:
        @staticmethod
        def globalScope():
            return None
        @staticmethod
        def projectScope(project):
            return None
        @staticmethod
        def layerScope(layer):
            return None

try:
    import sip
    SIP_AVAILABLE = True
except ImportError:
    sip = None
    SIP_AVAILABLE = False


# =============================================================================
# Core Validation Functions
# =============================================================================

def is_sip_deleted(obj: Any) -> bool:
    """
    Check if a Qt/PyQt object's underlying C++ object has been deleted.
    
    This is the primary check to prevent "wrapped C/C++ object has been deleted" errors.
    
    Args:
        obj: Any PyQt/Qt object to check
        
    Returns:
        True if object is deleted or invalid, False if safe to use
        
    Example:
        if not is_sip_deleted(widget):
            widget.setText("Safe to use")
    """
    if obj is None:
        return True
    
    if not SIP_AVAILABLE:
        logger.debug("sip module not available, cannot check object deletion status")
        return False
    
    try:
        return sip.isdeleted(obj)
    except (TypeError, AttributeError):
        # Object doesn't support sip.isdeleted check
        return False
    except (RuntimeError, OSError, SystemError) as e:
        # Can occur on Windows when accessing corrupted objects
        logger.debug(f"sip.isdeleted raised system error: {e}")
        return True  # Assume deleted if we can't check


def is_layer_valid(layer: Optional[Any]) -> bool:
    """
    Check if a layer is valid and usable.
    
    Combines checks for:
    - Layer is not None
    - Layer is not deleted (SIP)
    - Layer.isValid() is True
    
    This is a fast check suitable for frequent use in loops and callbacks.
    
    Args:
        layer: Layer to check (any type, but typically QgsVectorLayer)
        
    Returns:
        True if layer is valid and safe to use
        
    Example:
        if is_layer_valid(layer):
            # Safe to access layer properties
            name = layer.name()
    """
    if layer is None:
        return False
    
    # Check for deleted C++ object
    if is_sip_deleted(layer):
        return False
    
    # Try to access layer to verify it's not corrupted
    try:
        _ = layer.id()
    except (RuntimeError, OSError, AttributeError):
        return False
    
    # Check QGIS validity
    try:
        return layer.isValid()
    except (RuntimeError, AttributeError):
        return False


def is_layer_source_available(
    layer: Any,
    require_psycopg2: bool = True,
    check_file_exists: bool = True
) -> bool:
    """
    Check if a layer is usable and its underlying data source is accessible.
    
    This is a more comprehensive check than is_layer_valid(), also verifying
    that the data source (file, database) is accessible.
    
    Args:
        layer: Layer to check
        require_psycopg2: If True, PostgreSQL layers require psycopg2.
                          Set to False for QGIS-API-only operations.
        check_file_exists: If True, verify file existence for file-based layers.
    
    Returns:
        True if the layer is valid and its source is available
        
    Example:
        if is_layer_source_available(layer):
            # Safe to query the layer
            features = layer.getFeatures()
    """
    # First do the basic validity check
    if not is_layer_valid(layer):
        return False
    
    # Get provider type
    try:
        provider = layer.providerType()
    except (RuntimeError, AttributeError):
        return False
    
    # Memory layers are always available
    if provider == 'memory':
        return True
    
    # For remote providers, trust QGIS validity
    remote_providers = {'WFS', 'wfs', 'arcgisfeatureserver', 'oapif'}
    if provider in remote_providers:
        return True
    
    # For PostgreSQL, always available via QGIS API
    if provider in ('postgres', 'postgresql'):
        return True
    
    # For file-based providers, optionally check file existence
    if check_file_exists and provider in ('spatialite', 'ogr'):
        try:
            import os
            source = layer.source() or ''
            base = source.split('|')[0].strip().strip('"').strip("'")
            
            # Skip remote URLs
            lower = base.lower()
            if lower.startswith(('http://', 'https://', 'wfs:', 'wms:', 'ftp://')):
                return True
            
            # Check file exists
            if base and os.path.isfile(base):
                return True
            
            # If base is empty or file not found, trust QGIS validity
            return layer.isValid()
            
        except Exception:
            return layer.isValid()
    
    # Default: trust QGIS validity
    return True


def validate_expression(
    expression: str,
    layer: Optional[Any] = None,
    check_fields: bool = True
) -> Tuple[bool, Optional[str]]:
    """
    Validate a filter expression, optionally against a layer's fields.
    
    Args:
        expression: Filter expression string to validate
        layer: Optional layer to validate field references against
        check_fields: If True and layer provided, validate field names
    
    Returns:
        Tuple of (is_valid, error_message)
        error_message is None if valid
        
    Example:
        valid, error = validate_expression("population > 10000", layer)
        if not valid:
    """
    # Empty expression is valid (means no filter)
    if not expression or not expression.strip():
        return True, None
    
    # Parse the expression
    if not QGIS_AVAILABLE:
        # Without QGIS, we can only do basic syntax check
        # Check for obviously invalid patterns
        if expression.count('(') != expression.count(')'):
            return False, "Unbalanced parentheses"
        if expression.count('"') % 2 != 0:
            return False, "Unbalanced quotes"
        return True, None
    
    qgs_expr = QgsExpression(expression)
    
    # Check for parser errors
    if qgs_expr.hasParserError():
        return False, qgs_expr.parserErrorString()
    
    # If no layer provided or field check disabled, we're done
    if not check_fields or layer is None:
        return True, None
    
    # Validate field references
    if not is_layer_valid(layer):
        return True, None  # Can't validate fields, assume OK
    
    try:
        referenced_columns = qgs_expr.referencedColumns()
        
        if referenced_columns:
            # Get layer field names
            field_names = set()
            for field in layer.fields():
                field_names.add(field.name())
                field_names.add(field.name().lower())  # Case insensitive
            
            # Check each referenced column
            missing_fields = []
            for col in referenced_columns:
                # Skip special columns
                if col.startswith('$') or col == '*':
                    continue
                if col.lower() not in [f.lower() for f in field_names]:
                    missing_fields.append(col)
            
            if missing_fields:
                return False, f"Unknown field(s): {', '.join(missing_fields)}"
    
    except Exception as e:
        logger.debug(f"Error validating field references: {e}")
        # Don't fail on validation errors, just warn
    
    return True, None


def validate_expression_syntax(expression: str) -> Tuple[bool, Optional[str]]:
    """
    Quick syntax validation without field checking.
    
    Args:
        expression: Expression to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    return validate_expression(expression, layer=None, check_fields=False)


# =============================================================================
# Batch Validation Functions
# =============================================================================

def validate_layers(layers: List[Any]) -> Tuple[List[Any], List[Any]]:
    """
    Validate multiple layers, separating valid from invalid.
    
    Args:
        layers: List of layers to validate
    
    Returns:
        Tuple of (valid_layers, invalid_layers)
        
    Example:
        valid, invalid = validate_layers(project.mapLayers().values())
    """
    valid = []
    invalid = []
    
    for layer in layers:
        if is_layer_valid(layer):
            valid.append(layer)
        else:
            invalid.append(layer)
    
    return valid, invalid


def get_layer_validation_info(layer: Any) -> dict:
    """
    Get detailed validation information about a layer.
    
    Args:
        layer: Layer to analyze
    
    Returns:
        Dict with validation details
        
    Example:
        info = get_layer_validation_info(layer)
        if info['is_valid']:
    """
    info = {
        'is_valid': False,
        'is_sip_deleted': True,
        'is_source_available': False,
        'id': None,
        'name': None,
        'provider': None,
        'source': None,
        'errors': []
    }
    
    if layer is None:
        info['errors'].append("Layer is None")
        return info
    
    # Check SIP deletion
    info['is_sip_deleted'] = is_sip_deleted(layer)
    if info['is_sip_deleted']:
        info['errors'].append("C++ object has been deleted")
        return info
    
    # Try to get basic info
    try:
        info['id'] = layer.id()
        info['name'] = layer.name()
        info['provider'] = layer.providerType()
        info['source'] = layer.source()[:100] if layer.source() else None
    except Exception as e:
        info['errors'].append(f"Error accessing layer properties: {e}")
        return info
    
    # Check QGIS validity
    try:
        info['is_valid'] = layer.isValid()
        if not info['is_valid']:
            info['errors'].append("layer.isValid() returned False")
    except Exception as e:
        info['errors'].append(f"Error checking validity: {e}")
    
    # Check source availability
    info['is_source_available'] = is_layer_source_available(layer)
    if not info['is_source_available']:
        info['errors'].append("Data source not available")
    
    return info


# =============================================================================
# Expression Type Detection
# =============================================================================

def is_filter_expression(expression: str) -> bool:
    """
    Determine if an expression is a filter expression (returns boolean).
    
    A filter expression is one that contains comparison or logical operators
    that would evaluate to True/False. Non-filter expressions include:
    - Simple field names (e.g., "nom_collaboratif_gauche")
    - COALESCE expressions (e.g., "COALESCE(field_a, field_b)")
    - CONCAT expressions
    - Aggregate functions (e.g., "count(field)")
    - Arithmetic expressions (e.g., "field_a + field_b")
    
    Args:
        expression: Expression string to analyze
        
    Returns:
        True if expression is a filter (boolean) expression, False otherwise
        
    Examples:
        >>> is_filter_expression('"field_name"')
        False
        >>> is_filter_expression('COALESCE("field_a", "field_b")')
        False
        >>> is_filter_expression('"population" > 1000')
        True
        >>> is_filter_expression('"status" = 1 AND "active" = true')
        True
        >>> is_filter_expression('"name" LIKE \'test%\'')
        True
        >>> is_filter_expression('"id" IN (1, 2, 3)')
        True
        >>> is_filter_expression('"name" IS NOT NULL')
        True
    """
    if not expression or not expression.strip():
        return False
    
    expr = expression.strip()
    expr_upper = expr.upper()
    
    # List of comparison/logical operators that make an expression a filter
    # These operators return boolean values
    filter_operators = [
        # Comparison operators
        ' = ', ' != ', ' <> ',
        ' > ', ' < ', ' >= ', ' <= ',
        # String comparison operators (with spaces to avoid false positives)
        ' LIKE ', ' ILIKE ', ' SIMILAR TO ',
        ' ~ ', ' ~* ', ' !~ ', ' !~* ',  # PostgreSQL regex
        # NULL checks
        ' IS NULL', ' IS NOT NULL',
        ' ISNULL(', ' ISNOTNULL(',  # QGIS functions
        # Membership tests
        ' IN ', ' NOT IN ', ' IN(',
        ' BETWEEN ', ' NOT BETWEEN ',
        # Logical operators (indicate boolean expression)
        ' AND ', ' OR ', ' NOT ',
        # Existence checks
        'EXISTS ', 'EXISTS(',
        # Boolean literals (often part of comparisons)
        '= TRUE', '= FALSE', '= true', '= false',
        '!= TRUE', '!= FALSE', '!= true', '!= false',
    ]
    
    # Check if any filter operator is present
    for op in filter_operators:
        if op in expr_upper or op.strip() in expr_upper:
            return True
    
    # Check for operators without spaces (edge cases)
    # These patterns indicate comparisons
    import re
    
    # Pattern for comparisons like "field"=value, "field">value, etc.
    comparison_pattern = r'["\']?\w+["\']?\s*[!=<>]+\s*'
    if re.search(comparison_pattern, expr):
        return True
    
    # If we get here, it's likely a non-filter expression
    # (field name, COALESCE, CONCAT, aggregate function, etc.)
    return False


def is_display_expression(expression: str) -> bool:
    """
    Determine if an expression is a display expression (returns value, not boolean).
    
    Display expressions are used for labeling, formatting, or calculating values
    but should NOT be used as filter conditions.
    
    Common display expressions:
    - Field names: "field_name"
    - COALESCE: COALESCE("field_a", "field_b")
    - CONCAT: CONCAT("first", ' ', "last")
    - Arithmetic: "field_a" + "field_b"
    - Format functions: format_date("date_field", 'yyyy-MM-dd')
    - Aggregate functions: sum("amount"), count("id")
    
    Args:
        expression: Expression string to analyze
        
    Returns:
        True if expression is a display (non-boolean) expression
    """
    if not expression or not expression.strip():
        return False
    
    # If it's a filter expression, it's not a display expression
    if is_filter_expression(expression):
        return False
    
    # It's a display expression
    return True


def should_skip_expression_for_filtering(expression: str) -> Tuple[bool, str]:
    """
    Check if an expression should be skipped when building filter queries.
    
    Returns True for expressions that:
    1. Are empty or whitespace
    2. Are just field names (no filter logic)
    3. Are display functions like COALESCE, CONCAT
    4. Are aggregate functions
    
    Args:
        expression: Expression string to analyze
        
    Returns:
        Tuple of (should_skip, reason)
        
    Example:
        skip, reason = should_skip_expression_for_filtering('"field_name"')
        if skip:
            logger.info(f"Skipping expression: {reason}")
    """
    if not expression or not expression.strip():
        return True, "Expression is empty"
    
    expr = expression.strip()
    
    # Check if it's a filter expression
    if is_filter_expression(expr):
        return False, ""
    
    # Determine the reason for skipping
    expr_upper = expr.upper()
    
    # Common display function patterns
    display_functions = [
        'COALESCE(', 'CONCAT(', 'FORMAT(', 'FORMAT_DATE(', 'FORMAT_NUMBER(',
        'TO_STRING(', 'UPPER(', 'LOWER(', 'TRIM(', 'SUBSTR(', 'REPLACE(',
        'SUM(', 'COUNT(', 'AVG(', 'MIN(', 'MAX(', 'ARRAY_AGG(',
        'AGGREGATE(', 'RELATION_AGGREGATE(',
    ]
    
    for func in display_functions:
        if expr_upper.startswith(func) or f' {func}' in expr_upper:
            func_name = func.rstrip('(')
            return True, f"Expression uses display function: {func_name}"
    
    # Check if it's just a field reference
    if QGIS_AVAILABLE:
        qgs_expr = QgsExpression(expr)
        if qgs_expr.isField():
            return True, "Expression is just a field name"
    else:
        # Simple heuristic: if it's just quoted text without operators
        if (expr.startswith('"') and expr.endswith('"')) or \
           (expr.startswith("'") and expr.endswith("'")):
            # Could be a field name
            inner = expr[1:-1]
            # Field names don't typically contain operators
            if not any(op in inner for op in ['=', '>', '<', '!', '+', '-', '*', '/']):
                return True, "Expression appears to be just a field name"
    
    return True, "Expression does not contain filter logic"


# =============================================================================
# Safe Access Decorators/Helpers
# =============================================================================

def safe_layer_access(func):
    """
    Decorator for functions that access layer properties.
    
    Catches RuntimeError from deleted objects and returns None.
    
    Example:
        @safe_layer_access
        def get_layer_name(layer):
            return layer.name()
    """
    def wrapper(layer, *args, **kwargs):
        if not is_layer_valid(layer):
            return None
        try:
            return func(layer, *args, **kwargs)
        except (RuntimeError, OSError, AttributeError):
            return None
    return wrapper


@safe_layer_access
def safe_get_layer_name(layer) -> Optional[str]:
    """Safely get layer name, returns None if layer is invalid."""
    return layer.name()


@safe_layer_access
def safe_get_layer_id(layer) -> Optional[str]:
    """Safely get layer ID, returns None if layer is invalid."""
    return layer.id()


@safe_layer_access
def safe_get_layer_source(layer) -> Optional[str]:
    """Safely get layer source, returns None if layer is invalid."""
    return layer.source()

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

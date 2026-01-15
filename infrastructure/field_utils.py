# -*- coding: utf-8 -*-
"""
QGIS Field Utilities

Utilities for working with QGIS layer fields, value relations, and widget configurations.

Created during modules/ migration (Phase 2).
"""

import logging

logger = logging.getLogger('FilterMate.Infrastructure.FieldUtils')


def get_value_relation_info(layer, field_name: str, check_layer_availability: bool = True) -> dict:
    """
    Get value relation widget configuration for a field.
    
    DELEGATION: This function is a wrapper around infrastructure.utils.layer_utils.
    
    Args:
        layer: QgsVectorLayer containing the field
        field_name: Name of the field to check
        check_layer_availability: Whether to verify referenced layer exists
        
    Returns:
        dict: Value relation info or None if field doesn't use value relation
    """
    try:
        from .utils.layer_utils import get_value_relation_info as canonical_get_value_relation
        
        # Delegate to canonical implementation
        return canonical_get_value_relation(layer, field_name, check_layer_availability)
        
    except Exception as e:
        logger.error(f"Error in get_value_relation_info wrapper for {field_name}: {e}")
        return None


def clean_buffer_value(value):
    """
    Clean buffer distance value from float precision errors.
    
    Fixes common floating point precision issues that occur when
    storing/retrieving buffer distances (e.g., 100.0000000001 → 100).
    
    Args:
        value: Buffer distance value (float, int, or string)
        
    Returns:
        float: Cleaned buffer value with precision errors removed
        
    Examples:
        >>> clean_buffer_value(100.0000000001)
        100.0
        >>> clean_buffer_value("50.9999999999")
        51.0
        >>> clean_buffer_value(0.3333333333)
        0.33
    """
    try:
        if value is None or value == '':
            return 0.0
        
        # Convert to float
        float_val = float(value)
        
        # Round to reasonable precision (2 decimal places for most GIS use cases)
        # But preserve integer values exactly
        if abs(float_val - round(float_val)) < 0.0001:
            # Very close to integer
            return float(round(float_val))
        else:
            # Has decimals - round to 2 places
            return round(float_val, 2)
            
    except (ValueError, TypeError) as e:
        logger.warning(f"Could not clean buffer value {value}: {e}")
        return 0.0


def cleanup_corrupted_layer_filters(layers=None):
    """
    Clean up corrupted or invalid subset strings (filters) on layers.
    
    DELEGATION: This function is a wrapper around infrastructure.utils.layer_utils.
    
    Args:
        layers: List of QgsVectorLayers to check (default: all project layers)
        
    Returns:
        list: List of layer names that had filters cleaned up
    """
    try:
        from qgis.core import QgsProject
        from .utils.layer_utils import cleanup_corrupted_layer_filters as canonical_cleanup
        
        # If layers not specified, use entire project
        if layers is None:
            project = QgsProject.instance()
            return canonical_cleanup(project)
        
        # TODO: Handle explicit layers list
        # The canonical version expects a project, not a list of layers
        # For now, fall back to project-wide cleanup
        logger.warning("cleanup_corrupted_layer_filters: explicit layers list not yet supported, using project-wide cleanup")
        project = QgsProject.instance()
        return canonical_cleanup(project)
        
    except Exception as e:
        logger.error(f"Error in cleanup_corrupted_layer_filters wrapper: {e}")
        return []


__all__ = [
    'get_value_relation_info',
    'clean_buffer_value',
    'cleanup_corrupted_layer_filters',
]

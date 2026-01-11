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
    
    Extracts configuration from QGIS value relation widgets that reference
    other layers for dropdown values (foreign key-like relationships).
    
    Args:
        layer: QgsVectorLayer containing the field
        field_name: Name of the field to check
        check_layer_availability: Whether to verify referenced layer exists
        
    Returns:
        dict: Value relation info or None if field doesn't use value relation
            {
                'layer_id': Referenced layer ID,
                'layer_name': Referenced layer name,
                'layer_available': True if layer exists (if check_layer_availability=True),
                'key_column': Column used as key,
                'value_column': Column displayed to user,
                'filter_expression': Optional filter on referenced layer
            }
            
    Example:
        >>> info = get_value_relation_info(cities_layer, 'country_id')
        >>> if info:
        ...     print(f"References {info['layer_name']} layer")
    """
    try:
        from qgis.core import QgsProject
        
        if not layer or not hasattr(layer, 'fields'):
            return None
        
        field_idx = layer.fields().indexOf(field_name)
        if field_idx < 0:
            return None
        
        # Get widget configuration
        widget_config = layer.editorWidgetSetup(field_idx)
        widget_type = widget_config.type()
        
        if widget_type != 'ValueRelation':
            return None
        
        config = widget_config.config()
        
        if not config:
            return None
        
        layer_id = config.get('Layer', '')
        if not layer_id:
            return None
        
        result = {
            'layer_id': layer_id,
            'key_column': config.get('Key', ''),
            'value_column': config.get('Value', ''),
            'filter_expression': config.get('FilterExpression', ''),
            'allow_multi': config.get('AllowMulti', False),
            'allow_null': config.get('AllowNull', True),
        }
        
        # Check if referenced layer is available
        if check_layer_availability:
            project = QgsProject.instance()
            ref_layer = project.mapLayer(layer_id)
            result['layer_available'] = ref_layer is not None and ref_layer.isValid()
            result['layer_name'] = ref_layer.name() if ref_layer else 'Unknown'
        else:
            result['layer_available'] = None
            result['layer_name'] = None
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting value relation info for {field_name}: {e}")
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
    
    Iterates through layers and removes subset strings that:
    - Reference non-existent fields
    - Have invalid syntax
    - Cause errors when evaluated
    
    This prevents QGIS crashes or errors when loading projects with
    corrupted layer filters.
    
    Args:
        layers: List of QgsVectorLayers to check (default: all project layers)
        
    Returns:
        list: List of layer names that had filters cleaned up
        
    Example:
        >>> cleaned = cleanup_corrupted_layer_filters()
        >>> if cleaned:
        ...     print(f"Cleaned filters on: {', '.join(cleaned)}")
    """
    try:
        from qgis.core import QgsProject, QgsExpression
        
        if layers is None:
            project = QgsProject.instance()
            layers = [layer for layer in project.mapLayers().values()
                     if hasattr(layer, 'setSubsetString')]
        
        cleaned_layers = []
        
        for layer in layers:
            try:
                if not layer or not hasattr(layer, 'subsetString'):
                    continue
                
                subset = layer.subsetString()
                if not subset:
                    continue
                
                # Try to validate expression
                expr = QgsExpression(subset)
                
                # Check for parser errors
                if expr.hasParserError():
                    logger.warning(
                        f"Layer {layer.name()} has invalid filter: {expr.parserErrorString()}"
                    )
                    layer.setSubsetString('')
                    cleaned_layers.append(layer.name())
                    continue
                
                # Check if expression references non-existent fields
                fields = set(f.name() for f in layer.fields())
                referenced = set(expr.referencedColumns())
                
                # Special QGIS variables ($id, $geometry, etc.) are OK
                referenced_fields = {f for f in referenced if not f.startswith('$')}
                
                if referenced_fields and not referenced_fields.issubset(fields):
                    missing = referenced_fields - fields
                    logger.warning(
                        f"Layer {layer.name()} filter references missing fields: {missing}"
                    )
                    layer.setSubsetString('')
                    cleaned_layers.append(layer.name())
                    
            except Exception as e:
                logger.error(f"Error checking filter for layer {layer.name()}: {e}")
                # Try to clear the filter as a safety measure
                try:
                    layer.setSubsetString('')
                    cleaned_layers.append(layer.name())
                except:
                    pass
        
        if cleaned_layers:
            logger.info(f"Cleaned corrupted filters on {len(cleaned_layers)} layers")
        
        return cleaned_layers
        
    except Exception as e:
        logger.error(f"Error in cleanup_corrupted_layer_filters: {e}")
        return []


__all__ = [
    'get_value_relation_info',
    'clean_buffer_value',
    'cleanup_corrupted_layer_filters',
]

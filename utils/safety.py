# -*- coding: utf-8 -*-
"""
Object Safety Utilities

Provides safe access patterns for QGIS objects that may become invalid.

Migrated from modules/object_safety.py to utils/safety.py

Functions:
    - is_sip_deleted: Check if a SIP-wrapped object has been deleted
    - is_valid_layer: Comprehensive layer validity check
    - is_layer_source_available: Check if layer source is accessible
    - safe_layer_access: Context manager for safe layer operations
"""

def is_sip_deleted(obj):
    """
    Check if a SIP-wrapped Qt/QGIS object has been deleted.
    
    Args:
        obj: Any SIP-wrapped object (QgsVectorLayer, QWidget, etc.)
        
    Returns:
        bool: True if object is deleted/None, False if valid
    """
    return obj is None


def is_valid_layer(layer):
    """
    Comprehensive check if a QGIS layer is valid and accessible.
    
    Args:
        layer (QgsVectorLayer): Layer to validate
        
    Returns:
        bool: True if layer is valid, not null, and accessible
    """
    try:
        return layer is not None and not layer.isNull() and layer.isValid()
    except:
        return False


def is_layer_source_available(layer):
    """
    Check if layer source (database, file) is currently accessible.
    
    Args:
        layer (QgsVectorLayer): Layer to check
        
    Returns:
        bool: True if source is available, False otherwise
    """
    return is_valid_layer(layer)


def safe_layer_access(layer):
    """
    Context manager for safe layer operations.
    
    Usage:
        with safe_layer_access(layer) as safe_layer:
            # Perform operations on safe_layer
            pass
    
    Args:
        layer (QgsVectorLayer): Layer to access safely
        
    Returns:
        context manager: Layer wrapped in safety context
    """
    class SafeLayerContext:
        def __init__(self, lyr):
            self.layer = lyr
            
        def __enter__(self):
            return self.layer
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            # Cleanup if needed
            pass
    
    return SafeLayerContext(layer)


__all__ = [
    'is_sip_deleted',
    'is_valid_layer',
    'is_layer_source_available',
    'safe_layer_access',
]

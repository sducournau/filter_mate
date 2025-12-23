# -*- coding: utf-8 -*-
"""
Object Safety Module - FilterMate v2.3.9+

Provides safe wrappers for Qt/QGIS object operations to prevent
access violations and crashes from accessing deleted C++ objects.

CRITICAL: These functions prevent the common error:
    RuntimeError: wrapped C/C++ object of type X has been deleted

Common scenarios that cause this error:
- Accessing a QgsVectorLayer after it was removed from project
- Emitting signals from a QgsTask after it finished
- Using widgets after their parent was deleted
- Timer callbacks after object destruction

Usage:
    from modules.object_safety import (
        is_valid_qobject,
        is_valid_layer,
        safe_layer_access,
        safe_disconnect,
        safe_emit
    )

Author: FilterMate Team
Date: December 2025
"""

import logging
import weakref
from typing import Optional, Any, Callable, TypeVar
from functools import wraps

try:
    import sip
except ImportError:
    # Fallback for environments without sip
    sip = None

from qgis.core import QgsVectorLayer, QgsProject, QgsMapLayer
from qgis.PyQt.QtCore import QObject

logger = logging.getLogger('FilterMate.ObjectSafety')


# =============================================================================
# Core Safety Functions
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
    
    if sip is None:
        # Without sip module, we can't check - assume valid but warn
        logger.debug("sip module not available, cannot check object deletion status")
        return False
    
    try:
        return sip.isdeleted(obj)
    except (TypeError, AttributeError):
        # Object doesn't support sip.isdeleted check
        return False


def is_valid_qobject(obj: Any) -> bool:
    """
    Check if a QObject is valid and safe to use.
    
    Combines multiple checks:
    - Not None
    - Not sip deleted
    - For QObject types, check internal validity
    
    Args:
        obj: Object to validate
        
    Returns:
        True if object is valid and safe to use
        
    Example:
        if is_valid_qobject(self.combo_box):
            self.combo_box.currentText()
    """
    if obj is None:
        return False
    
    if is_sip_deleted(obj):
        return False
    
    # Additional check for QObject
    if isinstance(obj, QObject):
        try:
            # Accessing objectName() will fail if C++ object deleted
            _ = obj.objectName()
            return True
        except RuntimeError:
            return False
    
    return True


def is_valid_layer(layer: Any) -> bool:
    """
    Check if a QGIS layer is valid and safe to use for operations.
    
    Combines multiple checks:
    - Not None
    - Not sip deleted
    - Is a QgsVectorLayer
    - Layer.isValid() returns True
    - Layer still exists in project (optional but recommended)
    
    Args:
        layer: Layer to validate
        
    Returns:
        True if layer is valid and safe to use
        
    Example:
        if is_valid_layer(layer):
            layer.setSubsetString("field > 5")
    """
    if layer is None:
        return False
    
    if is_sip_deleted(layer):
        logger.debug(f"Layer is sip deleted")
        return False
    
    if not isinstance(layer, QgsVectorLayer):
        return False
    
    try:
        # These calls will raise RuntimeError if C++ object deleted
        if not layer.isValid():
            return False
        
        # Additional sanity check - access layer ID
        _ = layer.id()
        return True
        
    except RuntimeError:
        logger.debug(f"Layer access raised RuntimeError (C++ object deleted)")
        return False
    except Exception as e:
        logger.debug(f"Layer validation failed: {e}")
        return False


def is_layer_in_project(layer: Any, project: Optional[QgsProject] = None) -> bool:
    """
    Check if a layer still exists in the QGIS project.
    
    This prevents access violations when a layer was removed between
    getting a reference and using it.
    
    Args:
        layer: Layer to check
        project: Optional project to check in. Uses QgsProject.instance() if None
        
    Returns:
        True if layer exists in project
    """
    if not is_valid_layer(layer):
        return False
    
    try:
        if project is None:
            project = QgsProject.instance()
        
        if project is None:
            return False
        
        layer_id = layer.id()
        return project.mapLayer(layer_id) is not None
        
    except RuntimeError:
        return False


# =============================================================================
# Safe Operation Wrappers
# =============================================================================

def safe_layer_access(layer: Any, default: Any = None) -> Callable:
    """
    Decorator factory for safe layer operations.
    
    Returns the function result if layer is valid, otherwise returns default.
    
    Args:
        layer: Layer to validate before function call
        default: Value to return if layer is invalid
        
    Returns:
        Decorator function
        
    Example:
        @safe_layer_access(self.layer, default=[])
        def get_features():
            return list(layer.getFeatures())
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not is_valid_layer(layer):
                logger.debug(f"Skipping {func.__name__}: layer is invalid")
                return default
            try:
                return func(*args, **kwargs)
            except RuntimeError as e:
                logger.warning(f"RuntimeError in {func.__name__}: {e}")
                return default
        return wrapper
    return decorator


def safe_disconnect(signal: Any, slot: Optional[Callable] = None) -> bool:
    """
    Safely disconnect a Qt signal, handling already-disconnected or deleted cases.
    
    Args:
        signal: The signal to disconnect
        slot: Optional specific slot to disconnect. If None, disconnects all.
        
    Returns:
        True if disconnection was successful or signal was already disconnected
        
    Example:
        safe_disconnect(self.layer.layerModified, self.on_layer_modified)
        safe_disconnect(self.button.clicked)  # Disconnect all slots
    """
    if signal is None:
        return True
    
    try:
        if slot is not None:
            signal.disconnect(slot)
        else:
            signal.disconnect()
        return True
    except TypeError:
        # Signal was not connected to this slot
        logger.debug("Signal was not connected (TypeError)")
        return True
    except RuntimeError:
        # Signal's object has been deleted
        logger.debug("Signal's object has been deleted (RuntimeError)")
        return True
    except Exception as e:
        logger.warning(f"Unexpected error disconnecting signal: {e}")
        return False


def safe_emit(signal: Any, *args) -> bool:
    """
    Safely emit a Qt signal, handling deleted object cases.
    
    Args:
        signal: The signal to emit
        *args: Arguments to pass to the signal
        
    Returns:
        True if emission was successful
        
    Example:
        safe_emit(self.resultingLayers, self.project_layers)
    """
    if signal is None:
        return False
    
    try:
        signal.emit(*args)
        return True
    except RuntimeError as e:
        logger.debug(f"Could not emit signal (object may be deleted): {e}")
        return False
    except Exception as e:
        logger.warning(f"Unexpected error emitting signal: {e}")
        return False


def safe_block_signals(widget: Any, block: bool) -> bool:
    """
    Safely block/unblock widget signals.
    
    Args:
        widget: QWidget or QObject to block
        block: True to block, False to unblock
        
    Returns:
        Previous blocking state, or False if operation failed
    """
    if not is_valid_qobject(widget):
        return False
    
    try:
        return widget.blockSignals(block)
    except RuntimeError:
        logger.debug("Could not block signals: widget deleted")
        return False


# =============================================================================
# WeakRef Utilities for Callbacks
# =============================================================================

def make_safe_callback(obj: Any, method_name: str) -> Callable:
    """
    Create a safe callback that checks object validity before calling method.
    
    This is essential for QTimer.singleShot and other deferred callbacks
    that may execute after the object has been deleted.
    
    Args:
        obj: Object containing the method
        method_name: Name of the method to call
        
    Returns:
        Safe wrapper function that checks validity
        
    Example:
        # Instead of:
        QTimer.singleShot(100, self.update_ui)  # DANGEROUS!
        
        # Use:
        QTimer.singleShot(100, make_safe_callback(self, 'update_ui'))
    """
    weak_ref = weakref.ref(obj)
    
    def safe_callback(*args, **kwargs):
        strong_ref = weak_ref()
        if strong_ref is None:
            logger.debug(f"Skipping callback {method_name}: object was garbage collected")
            return None
        
        if is_sip_deleted(strong_ref):
            logger.debug(f"Skipping callback {method_name}: C++ object was deleted")
            return None
        
        try:
            method = getattr(strong_ref, method_name, None)
            if method is not None and callable(method):
                return method(*args, **kwargs)
        except RuntimeError as e:
            logger.debug(f"RuntimeError in callback {method_name}: {e}")
            return None
    
    return safe_callback


def make_safe_lambda(obj: Any, func: Callable) -> Callable:
    """
    Wrap a lambda or function that captures 'self' to be safe against deletion.
    
    Args:
        obj: The object that might be deleted (usually 'self')
        func: Function/lambda that uses obj
        
    Returns:
        Safe wrapper that checks obj validity
        
    Example:
        # Instead of:
        QTimer.singleShot(100, lambda: self.do_something())  # DANGEROUS!
        
        # Use:
        QTimer.singleShot(100, make_safe_lambda(self, lambda s: s.do_something()))
    """
    weak_ref = weakref.ref(obj)
    
    def safe_wrapper(*args, **kwargs):
        strong_ref = weak_ref()
        if strong_ref is None:
            return None
        
        if is_sip_deleted(strong_ref):
            return None
        
        try:
            return func(strong_ref, *args, **kwargs)
        except RuntimeError as e:
            logger.debug(f"RuntimeError in lambda callback: {e}")
            return None
    
    return safe_wrapper


# =============================================================================
# Context Managers
# =============================================================================

class SafeLayerContext:
    """
    Context manager for safe layer operations.
    
    Validates layer before entering context and catches RuntimeError.
    
    Usage:
        with SafeLayerContext(layer) as safe_layer:
            if safe_layer:
                safe_layer.setSubsetString("field > 5")
    """
    
    def __init__(self, layer: Any):
        self.layer = layer
        self.valid = False
    
    def __enter__(self):
        self.valid = is_valid_layer(self.layer)
        return self.layer if self.valid else None
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is RuntimeError:
            logger.debug(f"RuntimeError caught in SafeLayerContext: {exc_val}")
            return True  # Suppress RuntimeError
        return False


class SafeSignalContext:
    """
    Context manager for safe signal emission in QgsTask.finished().
    
    Ensures signal is emitted and disconnected safely, even if
    the receiver object has been deleted.
    
    Usage:
        with SafeSignalContext(self.resultingLayers, data) as emitted:
            if emitted:
                logger.info("Signal emitted successfully")
    """
    
    def __init__(self, signal: Any, *emit_args):
        self.signal = signal
        self.emit_args = emit_args
        self.emitted = False
    
    def __enter__(self):
        self.emitted = safe_emit(self.signal, *self.emit_args)
        return self.emitted
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Always try to disconnect
        safe_disconnect(self.signal)
        return False


# =============================================================================
# GeoPackage / OGR Layer Safety Functions (v2.3.10)
# =============================================================================

def is_gpkg_file_accessible(layer: QgsVectorLayer) -> bool:
    """
    Check if a GeoPackage layer's underlying file is accessible.
    
    OGR/GeoPackage errors like "unable to open database file" often occur when:
    - File is locked by another process
    - File was moved/deleted
    - Concurrent access causes SQLite locking
    
    Args:
        layer: QGIS vector layer to check
        
    Returns:
        True if file is accessible, False otherwise
    """
    import os
    
    if not is_valid_layer(layer):
        return False
    
    try:
        # Only applies to OGR provider (includes GeoPackage)
        if layer.providerType() != 'ogr':
            return True
        
        # Extract file path from layer source
        source = layer.source()
        if not source:
            return False
        
        # GeoPackage source format: "/path/to/file.gpkg|layername=layer_name"
        file_path = source.split('|')[0]
        
        # Check if file exists and is readable
        if not os.path.exists(file_path):
            logger.warning(f"GeoPackage file not found: {file_path}")
            return False
        
        if not os.access(file_path, os.R_OK):
            logger.warning(f"GeoPackage file not readable: {file_path}")
            return False
        
        # Try to detect if file is locked by attempting a read
        # This doesn't guarantee no locking issues but catches obvious cases
        try:
            with open(file_path, 'rb') as f:
                # Just read the SQLite header (first 16 bytes)
                header = f.read(16)
                if not header.startswith(b'SQLite format 3'):
                    logger.warning(f"File is not a valid SQLite/GeoPackage: {file_path}")
                    return False
        except IOError as e:
            logger.warning(f"GeoPackage file locked or inaccessible: {file_path} - {e}")
            return False
        
        return True
        
    except Exception as e:
        logger.warning(f"Error checking GeoPackage accessibility: {e}")
        return False


def safe_get_features(layer: QgsVectorLayer, request=None, max_retries: int = 3, 
                      retry_delay: float = 0.5) -> list:
    """
    Safely get features from a layer with retry logic for OGR/GeoPackage layers.
    
    Handles the common OGR error:
    "sqlite3_step() : unable to open database file"
    
    This error occurs when the GeoPackage file is temporarily locked by another
    operation. The retry logic allows brief locks to clear.
    
    Args:
        layer: QGIS vector layer
        request: Optional QgsFeatureRequest
        max_retries: Maximum number of retry attempts (default 3)
        retry_delay: Delay between retries in seconds (default 0.5)
        
    Returns:
        List of features, or empty list on failure
        
    Example:
        features = safe_get_features(layer, QgsFeatureRequest().setLimit(100))
    """
    import time
    from qgis.core import QgsFeatureRequest
    
    if not is_valid_layer(layer):
        logger.warning("safe_get_features: Invalid layer provided")
        return []
    
    # For non-OGR layers, just get features directly
    is_ogr = layer.providerType() == 'ogr'
    
    for attempt in range(max_retries):
        try:
            if request:
                features = list(layer.getFeatures(request))
            else:
                features = list(layer.getFeatures())
            return features
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Check for known recoverable errors
            is_recoverable = any(x in error_str for x in [
                'unable to open database file',
                'database is locked',
                'disk i/o error',
            ])
            
            if is_recoverable and attempt < max_retries - 1:
                logger.warning(
                    f"OGR/GeoPackage access error (attempt {attempt + 1}/{max_retries}): {e}. "
                    f"Retrying in {retry_delay}s..."
                )
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(f"Failed to get features from layer '{layer.name()}': {e}")
                return []
    
    return []


def refresh_ogr_layer(layer: QgsVectorLayer) -> bool:
    """
    Refresh an OGR layer's data source to clear stale connections.
    
    Useful when encountering "unable to open database file" errors
    due to stale file handles or connection issues.
    
    Args:
        layer: OGR-based vector layer to refresh
        
    Returns:
        True if refresh succeeded, False otherwise
    """
    if not is_valid_layer(layer):
        return False
    
    try:
        if layer.providerType() != 'ogr':
            return True  # Not an OGR layer, nothing to refresh
        
        # Trigger provider refresh
        layer.dataProvider().reloadData()
        layer.reload()
        layer.triggerRepaint()
        
        logger.debug(f"Refreshed OGR layer: {layer.name()}")
        return True
        
    except Exception as e:
        logger.warning(f"Failed to refresh OGR layer '{layer.name()}': {e}")
        return False


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Core checks
    'is_sip_deleted',
    'is_valid_qobject', 
    'is_valid_layer',
    'is_layer_in_project',
    
    # Safe operations
    'safe_layer_access',
    'safe_disconnect',
    'safe_emit',
    'safe_block_signals',
    
    # Callback safety
    'make_safe_callback',
    'make_safe_lambda',
    
    # Context managers
    'SafeLayerContext',
    'SafeSignalContext',
    
    # GeoPackage/OGR safety (v2.3.10)
    'is_gpkg_file_accessible',
    'safe_get_features',
    'refresh_ogr_layer',
]

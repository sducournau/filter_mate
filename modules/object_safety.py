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
from qgis.PyQt.QtWidgets import QApplication
import platform

logger = logging.getLogger('FilterMate.ObjectSafety')

# Flag to track if we're on Windows (where access violations are fatal)
IS_WINDOWS = platform.system() == 'Windows'


def is_qgis_alive() -> bool:
    """
    Check if QGIS application is still alive and safe to access.
    
    CRASH FIX (v2.3.14): This function checks if the QApplication instance exists
    and is not deleted. This is a pre-check before accessing QgsProject.instance()
    which can cause a Windows fatal exception (access violation) if called during
    QGIS shutdown or when the application is in an unstable state.
    
    The access violation at QgsProject.instance() cannot be caught by Python's
    try/except because it's an OS-level signal. This canary check prevents the
    crash by detecting when QGIS is shutting down.
    
    Returns:
        True if QGIS is alive and safe to access, False otherwise
    """
    try:
        app = QApplication.instance()
        if app is None:
            return False
        
        # Check if the app object is deleted (sip check)
        if sip is not None:
            try:
                if sip.isdeleted(app):
                    return False
            except (TypeError, AttributeError):
                # If sip check fails, assume not safe
                return False
        
        return True
    except Exception:
        return False


# =============================================================================
# Core Safety Functions
# =============================================================================

def is_sip_deleted(obj: Any) -> bool:
    """
    Check if a Qt/PyQt object's underlying C++ object has been deleted.
    
    This is the primary check to prevent "wrapped C/C++ object has been deleted" errors.
    
    CRASH FIX (v2.3.13): Added OSError/SystemError handling for Windows access violations.
    
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
    except (RuntimeError, OSError, SystemError) as e:
        # CRASH FIX (v2.3.13): These can occur on Windows when accessing corrupted objects
        logger.debug(f"sip.isdeleted raised system error: {e}")
        return True  # Assume deleted if we can't check


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
    
    CRASH FIX (v2.3.13): Enhanced protection against access violations by
    wrapping validity checks in individual try/except blocks.
    
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
    
    # CRASH FIX (v2.3.13): Check sip deletion with try/except wrapper
    try:
        if is_sip_deleted(layer):
            logger.debug(f"Layer is sip deleted")
            return False
    except (RuntimeError, OSError, SystemError) as e:
        logger.debug(f"sip deletion check failed: {e}")
        return False
    
    if not isinstance(layer, QgsVectorLayer):
        return False
    
    try:
        # These calls will raise RuntimeError if C++ object deleted
        # CRASH FIX (v2.3.13): Can also raise OSError/SystemError on Windows
        if not layer.isValid():
            return False
        
        # Additional sanity check - access layer ID
        _ = layer.id()
        return True
        
    except RuntimeError:
        logger.debug(f"Layer access raised RuntimeError (C++ object deleted)")
        return False
    except (OSError, SystemError) as e:
        # CRASH FIX (v2.3.13): Windows access violations may surface as these
        logger.debug(f"Layer access raised system error: {e}")
        return False
    except Exception as e:
        logger.debug(f"Layer validation failed: {e}")
        return False


def is_layer_in_project(layer: Any, project: Optional[QgsProject] = None) -> bool:
    """
    Check if a layer still exists in the QGIS project.
    
    This prevents access violations when a layer was removed between
    getting a reference and using it.
    
    CRASH FIX (v2.3.14): Added is_qgis_alive() check before QgsProject.instance()
    to prevent Windows access violations during QGIS shutdown.
    
    Args:
        layer: Layer to check
        project: Optional project to check in. Uses QgsProject.instance() if None
        
    Returns:
        True if layer exists in project
    """
    if not is_valid_layer(layer):
        return False
    
    try:
        # CRASH FIX (v2.3.14): Check if QGIS is alive before accessing project
        if project is None:
            if not is_qgis_alive():
                return False
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


def require_valid_layer(default_return=None, log_level: str = 'warning'):
    """
    Decorator to validate layer before method execution.
    
    Checks if the first argument (after self) is a valid QGIS layer.
    If invalid, returns default_return without executing the function.
    Catches RuntimeError during execution for deleted C++ objects.
    
    PERFORMANCE & STABILITY IMPROVEMENT (v2.6.0):
    Centralizes layer validation logic to reduce code duplication and
    prevent access violations from deleted C++ objects.
    
    Args:
        default_return: Value to return if layer is invalid (default: None)
        log_level: Logging level for invalid layer messages ('debug', 'warning', 'error')
        
    Returns:
        Decorated function
        
    Example:
        class MyClass:
            @require_valid_layer(default_return=[])
            def get_features(self, layer):
                return list(layer.getFeatures())
            
            @require_valid_layer(default_return=False, log_level='debug')
            def apply_filter(self, layer, expression):
                return layer.setSubsetString(expression)
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(self, layer, *args, **kwargs):
            # Validate layer
            if not is_valid_layer(layer):
                msg = f"Skipping {func.__name__}: layer is invalid or deleted"
                if log_level == 'debug':
                    logger.debug(msg)
                elif log_level == 'error':
                    logger.error(msg)
                else:
                    logger.warning(msg)
                return default_return
            
            try:
                return func(self, layer, *args, **kwargs)
            except RuntimeError as e:
                if "deleted" in str(e).lower():
                    logger.warning(f"{func.__name__}: Layer deleted during operation")
                    return default_return
                raise
            except (OSError, SystemError) as e:
                # Windows access violations may surface as these
                logger.warning(f"{func.__name__}: System error during layer operation: {e}")
                return default_return
        return wrapper
    return decorator


def require_valid_qobject(default_return=None):
    """
    Decorator to validate QObject before method execution.
    
    Similar to require_valid_layer but for general QObjects (widgets, etc.).
    
    Args:
        default_return: Value to return if object is invalid
        
    Example:
        @require_valid_qobject(default_return=None)
        def get_widget_text(self, widget):
            return widget.text()
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(self, qobject, *args, **kwargs):
            if not is_valid_qobject(qobject):
                logger.debug(f"Skipping {func.__name__}: QObject is invalid")
                return default_return
            
            try:
                return func(self, qobject, *args, **kwargs)
            except RuntimeError as e:
                if "deleted" in str(e).lower():
                    logger.warning(f"{func.__name__}: QObject deleted during operation")
                    return default_return
                raise
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


def safe_set_layer_variable(layer_id: str, variable_key: str, value: Any, project: Optional[QgsProject] = None) -> bool:
    """
    Safely set a layer variable, preventing access violations.
    
    CRASH FIX (v2.3.14): Enhanced protection against access violations by:
    1. Checking if QGIS is alive BEFORE calling QgsProject.instance()
    2. Checking sip deletion status BEFORE any layer method calls
    3. Using multiple validation gates to catch race conditions
    4. Wrapping all layer access in try/except for RuntimeError
    
    The Windows access violation on QgsProject.instance() was caused by QGIS
    being in an unstable state (shutdown, task manager cleanup, etc.).
    Python's try/except cannot catch OS-level access violations, so we use
    a QApplication.instance() canary check before accessing QgsProject.
    
    Args:
        layer_id: Layer ID to set variable on
        variable_key: Variable key to set
        value: Value to set
        project: Optional project to use. Uses QgsProject.instance() if None.
        
    Returns:
        True if the variable was set successfully
    """
    try:
        # CRASH FIX (v2.3.14): Check if QGIS is alive BEFORE QgsProject.instance()
        # Windows access violations cannot be caught by try/except
        if not is_qgis_alive():
            logger.debug("QGIS is not alive, skipping safe_set_layer_variable")
            return False
        
        if project is None:
            project = QgsProject.instance()
        
        if project is None:
            logger.debug("No project available for safe_set_layer_variable")
            return False
        
        # CRASH FIX (v2.3.13): Check if project itself is still valid
        if sip is not None:
            try:
                if sip.isdeleted(project):
                    logger.debug("Project C++ object is deleted")
                    return False
            except (TypeError, AttributeError):
                pass
        
        # Re-fetch layer fresh from project registry
        # This is the safest way - let QGIS give us the current layer object
        layer = project.mapLayer(layer_id)
        
        if layer is None:
            logger.debug(f"Layer {layer_id} not found in project")
            return False
        
        # CRASH FIX (v2.3.13): Immediate sip deletion check FIRST
        # This must happen before ANY method call on the layer object
        if sip is not None:
            try:
                if sip.isdeleted(layer):
                    logger.debug(f"Layer {layer_id} C++ object is deleted")
                    return False
            except (TypeError, AttributeError) as e:
                # If sip.isdeleted() itself fails, layer is likely corrupted
                logger.debug(f"sip.isdeleted check failed for {layer_id}: {e}")
                return False
        
        # CRASH FIX (v2.3.13): Wrap isValid() call in its own try/except
        # layer.isValid() can cause access violation if layer is partially deleted
        try:
            is_valid = layer.isValid()
        except (RuntimeError, OSError, SystemError) as e:
            logger.debug(f"Layer {layer_id} validity check failed: {e}")
            return False
        
        if not is_valid:
            logger.debug(f"Layer {layer_id} is invalid")
            return False
        
        # CRASH FIX (v2.3.13): Final sip check immediately before C++ call
        # Minimizes race condition window
        if sip is not None:
            try:
                if sip.isdeleted(layer):
                    logger.debug(f"Layer {layer_id} deleted before setLayerVariable")
                    return False
            except (TypeError, AttributeError):
                return False
        
        # CRASH FIX (v2.4.7): Flush pending Qt events BEFORE the C++ call
        # This allows any pending layer deletions to complete, reducing the race window.
        # Critical for Windows where access violations are fatal and cannot be caught.
        if IS_WINDOWS:
            try:
                app = QApplication.instance()
                if app is not None:
                    # Process pending events that might include layer deletions
                    app.processEvents()
                    
                    # Re-verify layer after processing events
                    if sip is not None:
                        try:
                            if sip.isdeleted(layer):
                                logger.debug(f"Layer {layer_id} deleted after processEvents")
                                return False
                        except (TypeError, AttributeError):
                            return False
                    
                    # Re-fetch layer one more time to be absolutely sure
                    layer = project.mapLayer(layer_id)
                    if layer is None:
                        logger.debug(f"Layer {layer_id} no longer in project after processEvents")
                        return False
            except Exception as e:
                logger.debug(f"Error during pre-operation event flush: {e}")
                return False
        
        # CRASH FIX (v2.4.8): Atomic-style final validation before C++ call
        # Re-fetch the layer immediately before the call to minimize race window
        # This is the absolute last defense before the C++ operation
        fresh_layer = project.mapLayer(layer_id)
        if fresh_layer is None:
            logger.debug(f"Layer {layer_id} not found in final fetch before setLayerVariable")
            return False
        
        # Immediate sip check on the fresh layer reference
        if sip is not None:
            try:
                if sip.isdeleted(fresh_layer):
                    logger.debug(f"Fresh layer {layer_id} is sip-deleted before setLayerVariable")
                    return False
            except (TypeError, AttributeError):
                logger.debug(f"sip check failed on fresh layer {layer_id}")
                return False
        
        # Final validity check on the fresh layer
        try:
            if not fresh_layer.isValid():
                logger.debug(f"Fresh layer {layer_id} is invalid before setLayerVariable")
                return False
        except (RuntimeError, OSError, SystemError):
            logger.debug(f"Fresh layer {layer_id} validity check crashed")
            return False
        
        # CRASH FIX (v2.4.9): Use direct setCustomProperty instead of 
        # QgsExpressionContextUtils.setLayerVariable. This allows us to wrap the
        # actual C++ call in a try/except that can catch RuntimeError.
        # QgsExpressionContextUtils.setLayerVariable internally calls setCustomProperty
        # with key format "variableValues/<variable_name>" for the value and
        # "variableNames" for tracking variable names.
        try:
            # Format variable key as QGIS expects for layer variables
            prop_key = f"variableValues/{variable_key}"
            
            # Get existing variable names list
            existing_names = fresh_layer.customProperty('variableNames', [])
            if not isinstance(existing_names, list):
                existing_names = [existing_names] if existing_names else []
            
            # Add variable name if not already tracked
            if variable_key not in existing_names:
                existing_names.append(variable_key)
                fresh_layer.setCustomProperty('variableNames', existing_names)
            
            # Set the variable value
            fresh_layer.setCustomProperty(prop_key, value)
            
            logger.debug(f"Successfully set layer variable {variable_key} for {layer_id}")
            return True
            
        except (RuntimeError, OSError, SystemError) as e:
            # These errors indicate the layer C++ object was deleted during the operation
            logger.debug(f"Layer {layer_id} was deleted during setCustomProperty: {e}")
            return False
        
    except RuntimeError as e:
        logger.debug(f"RuntimeError in safe_set_layer_variable for {layer_id}: {e}")
        return False
    except (OSError, SystemError) as e:
        # CRASH FIX (v2.3.13): These can occur on Windows when accessing deleted objects
        logger.debug(f"System error in safe_set_layer_variable for {layer_id}: {e}")
        return False
    except Exception as e:
        logger.warning(f"Error in safe_set_layer_variable for {layer_id}: {e}")
        return False


def safe_set_layer_variables(layer_id: str, variables: dict, project: Optional[QgsProject] = None) -> bool:
    """
    Safely set/clear all layer variables, preventing access violations.
    
    CRASH FIX (v2.3.14): Enhanced protection against access violations by:
    1. Checking if QGIS is alive BEFORE calling QgsProject.instance()
    2. Checking sip deletion status BEFORE any layer method calls
    3. Using multiple validation gates to catch race conditions
    4. Wrapping all layer access in try/except for RuntimeError
    
    Args:
        layer_id: Layer ID to set variables on
        variables: Dictionary of variables to set (empty dict clears all)
        project: Optional project to use. Uses QgsProject.instance() if None.
        
    Returns:
        True if the variables were set successfully
    """
    try:
        # CRASH FIX (v2.3.14): Check if QGIS is alive BEFORE QgsProject.instance()
        # Windows access violations cannot be caught by try/except
        if not is_qgis_alive():
            logger.debug("QGIS is not alive, skipping safe_set_layer_variables")
            return False
        
        if project is None:
            project = QgsProject.instance()
        
        if project is None:
            logger.debug("No project available for safe_set_layer_variables")
            return False
        
        # CRASH FIX (v2.3.13): Check if project itself is still valid
        if sip is not None:
            try:
                if sip.isdeleted(project):
                    logger.debug("Project C++ object is deleted")
                    return False
            except (TypeError, AttributeError):
                pass
        
        # Re-fetch layer fresh from project registry
        layer = project.mapLayer(layer_id)
        
        if layer is None:
            logger.debug(f"Layer {layer_id} not found in project")
            return False
        
        # CRASH FIX (v2.3.13): Immediate sip deletion check FIRST
        if sip is not None:
            try:
                if sip.isdeleted(layer):
                    logger.debug(f"Layer {layer_id} C++ object is deleted")
                    return False
            except (TypeError, AttributeError) as e:
                logger.debug(f"sip.isdeleted check failed for {layer_id}: {e}")
                return False
        
        # CRASH FIX (v2.3.13): Wrap isValid() call in its own try/except
        try:
            is_valid = layer.isValid()
        except (RuntimeError, OSError, SystemError) as e:
            logger.debug(f"Layer {layer_id} validity check failed: {e}")
            return False
        
        if not is_valid:
            logger.debug(f"Layer {layer_id} is invalid")
            return False
        
        # CRASH FIX (v2.3.13): Final sip check immediately before C++ call
        if sip is not None:
            try:
                if sip.isdeleted(layer):
                    logger.debug(f"Layer {layer_id} deleted before setLayerVariables")
                    return False
            except (TypeError, AttributeError):
                return False
        
        # CRASH FIX (v2.4.7): Flush pending Qt events BEFORE the C++ call
        # This allows any pending layer deletions to complete, reducing the race window.
        # Critical for Windows where access violations are fatal and cannot be caught.
        if IS_WINDOWS:
            try:
                app = QApplication.instance()
                if app is not None:
                    # Process pending events that might include layer deletions
                    app.processEvents()
                    
                    # Re-verify layer after processing events
                    if sip is not None:
                        try:
                            if sip.isdeleted(layer):
                                logger.debug(f"Layer {layer_id} deleted after processEvents")
                                return False
                        except (TypeError, AttributeError):
                            return False
                    
                    # Re-fetch layer one more time to be absolutely sure
                    layer = project.mapLayer(layer_id)
                    if layer is None:
                        logger.debug(f"Layer {layer_id} no longer in project after processEvents")
                        return False
            except Exception as e:
                logger.debug(f"Error during pre-operation event flush: {e}")
                return False
        
        # CRASH FIX (v2.4.8): Atomic-style final validation before C++ call
        # Re-fetch the layer immediately before the call to minimize race window
        # This is the absolute last defense before the C++ operation
        fresh_layer = project.mapLayer(layer_id)
        if fresh_layer is None:
            logger.debug(f"Layer {layer_id} not found in final fetch before setLayerVariables")
            return False
        
        # Immediate sip check on the fresh layer reference
        if sip is not None:
            try:
                if sip.isdeleted(fresh_layer):
                    logger.debug(f"Fresh layer {layer_id} is sip-deleted before setLayerVariables")
                    return False
            except (TypeError, AttributeError):
                logger.debug(f"sip check failed on fresh layer {layer_id}")
                return False
        
        # Final validity check on the fresh layer
        try:
            if not fresh_layer.isValid():
                logger.debug(f"Fresh layer {layer_id} is invalid before setLayerVariables")
                return False
        except (RuntimeError, OSError, SystemError):
            logger.debug(f"Fresh layer {layer_id} validity check crashed")
            return False
        
        # CRASH FIX (v2.4.9): Use direct setCustomProperty instead of
        # QgsExpressionContextUtils.setLayerVariables. This allows us to wrap
        # the actual C++ calls in try/except that can catch RuntimeError.
        try:
            if not variables:
                # Clear all variables - remove all variableValues/* properties
                existing_names = fresh_layer.customProperty('variableNames', [])
                if not isinstance(existing_names, list):
                    existing_names = [existing_names] if existing_names else []
                
                for var_name in existing_names:
                    try:
                        fresh_layer.removeCustomProperty(f'variableValues/{var_name}')
                    except (RuntimeError, OSError, SystemError):
                        logger.debug(f"Failed to remove variable {var_name} for {layer_id}")
                
                # Clear the names list
                try:
                    fresh_layer.removeCustomProperty('variableNames')
                except (RuntimeError, OSError, SystemError):
                    pass
            else:
                # Set all variables
                for var_key, var_value in variables.items():
                    prop_key = f"variableValues/{var_key}"
                    fresh_layer.setCustomProperty(prop_key, var_value)
                
                # Update variable names list
                fresh_layer.setCustomProperty('variableNames', list(variables.keys()))
            
            logger.debug(f"Successfully set layer variables for {layer_id}")
            return True
            
        except (RuntimeError, OSError, SystemError) as e:
            # These errors indicate the layer C++ object was deleted during the operation
            logger.debug(f"Layer {layer_id} was deleted during setCustomProperty: {e}")
            return False
        
    except RuntimeError as e:
        logger.debug(f"RuntimeError in safe_set_layer_variables for {layer_id}: {e}")
        return False
    except (OSError, SystemError) as e:
        # CRASH FIX (v2.3.13): These can occur on Windows when accessing deleted objects
        logger.debug(f"System error in safe_set_layer_variables for {layer_id}: {e}")
        return False
    except Exception as e:
        logger.warning(f"Error in safe_set_layer_variables for {layer_id}: {e}")
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
# GDAL Error Handling (v2.3.11)
# =============================================================================

# Try to import GDAL for error handling
try:
    from osgeo import gdal
    GDAL_AVAILABLE = True
except ImportError:
    GDAL_AVAILABLE = False
    gdal = None


class GdalErrorHandler:
    """
    Context manager to suppress known spurious GDAL/OGR warnings.
    
    Use this during OGR operations that may trigger transient SQLite
    file locking warnings like:
    - "sqlite3_step() : unable to open database file"
    - "database is locked"
    
    These warnings are often harmless and caused by brief file locks
    during concurrent operations. GDAL/OGR typically retries internally.
    
    Example:
        with GdalErrorHandler(suppress_patterns=['unable to open database file']):
            features = list(layer.getFeatures())
    """
    
    # Default patterns to suppress (known harmless transient errors)
    DEFAULT_SUPPRESS_PATTERNS = [
        'unable to open database file',
        'database is locked',
        'disk i/o error',
        'sqlite3_step',
        'sqlite3_get_table',
        'gpkg_metadata',
    ]
    
    def __init__(self, suppress_patterns=None, log_suppressed=False):
        """
        Initialize GDAL error handler.
        
        Args:
            suppress_patterns: List of patterns to suppress (case-insensitive).
                             Uses DEFAULT_SUPPRESS_PATTERNS if None.
            log_suppressed: If True, log suppressed messages at DEBUG level.
        """
        self.suppress_patterns = suppress_patterns or self.DEFAULT_SUPPRESS_PATTERNS
        self.log_suppressed = log_suppressed
        self._original_handler = None
        self._suppressed_count = 0
    
    def _custom_error_handler(self, err_class, err_num, err_msg):
        """Custom GDAL error handler that filters known spurious warnings."""
        if err_msg:
            msg_lower = err_msg.lower()
            for pattern in self.suppress_patterns:
                if pattern.lower() in msg_lower:
                    self._suppressed_count += 1
                    if self.log_suppressed:
                        logger.debug(f"Suppressed GDAL warning: {err_msg}")
                    return  # Suppress this warning
        
        # For non-suppressed errors, log them appropriately
        if GDAL_AVAILABLE and gdal:
            if err_class == gdal.CE_Warning:
                logger.warning(f"GDAL Warning: {err_msg}")
            elif err_class >= gdal.CE_Failure:
                logger.error(f"GDAL Error ({err_class}): {err_msg}")
            else:
                logger.debug(f"GDAL Message: {err_msg}")
    
    def __enter__(self):
        """Enter context - install custom error handler."""
        if not GDAL_AVAILABLE:
            return self
        
        try:
            # Install custom error handler
            gdal.PushErrorHandler(self._custom_error_handler)
            self._suppressed_count = 0
        except Exception as e:
            logger.debug(f"Could not install GDAL error handler: {e}")
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context - restore original error handler."""
        if not GDAL_AVAILABLE:
            return False
        
        try:
            # Restore original error handler
            gdal.PopErrorHandler()
            
            if self._suppressed_count > 0:
                logger.debug(
                    f"Suppressed {self._suppressed_count} transient GDAL/OGR warnings "
                    f"(SQLite file locking during concurrent access)"
                )
        except Exception as e:
            logger.debug(f"Could not restore GDAL error handler: {e}")
        
        return False  # Don't suppress exceptions
    
    @property
    def suppressed_count(self) -> int:
        """Number of suppressed messages during this context."""
        return self._suppressed_count


def suppress_gdal_warnings():
    """
    Decorator to suppress known spurious GDAL warnings for a function.
    
    Example:
        @suppress_gdal_warnings()
        def my_function():
            # OGR operations that may trigger transient warnings
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with GdalErrorHandler():
                return func(*args, **kwargs)
        return wrapper
    return decorator


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
    Suppresses transient GDAL/OGR warnings that are handled by retry logic.
    
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
    
    # Use GDAL error handler to suppress transient SQLite warnings during feature retrieval
    with GdalErrorHandler():
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


def refresh_ogr_layer(layer: QgsVectorLayer, max_retries: int = 3, retry_delay: float = 0.3) -> bool:
    """
    Refresh an OGR layer's data source to clear stale connections.
    
    Useful when encountering "unable to open database file" errors
    due to stale file handles or connection issues. Uses GDAL error
    suppression to handle transient SQLite warnings during refresh.
    
    Args:
        layer: OGR-based vector layer to refresh
        max_retries: Maximum refresh attempts (default 3)
        retry_delay: Initial delay between retries in seconds (default 0.3)
        
    Returns:
        True if refresh succeeded, False otherwise
    """
    import time
    
    if not is_valid_layer(layer):
        return False
    
    if layer.providerType() != 'ogr':
        return True  # Not an OGR layer, nothing to refresh
    
    for attempt in range(max_retries):
        try:
            # Use GDAL error handler to suppress transient SQLite warnings
            with GdalErrorHandler():
                # Trigger provider refresh
                layer.dataProvider().reloadData()
                layer.reload()
                layer.triggerRepaint()
            
            logger.debug(f"Refreshed OGR layer: {layer.name()}")
            return True
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Check for recoverable SQLite errors
            is_recoverable = any(x in error_str for x in [
                'unable to open database file',
                'database is locked',
                'sqlite3_step',
            ])
            
            if is_recoverable and attempt < max_retries - 1:
                logger.debug(
                    f"OGR layer refresh retry for '{layer.name()}' "
                    f"(attempt {attempt + 1}/{max_retries}): {e}"
                )
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 2.0)  # Cap at 2 seconds
            else:
                logger.warning(f"Failed to refresh OGR layer '{layer.name()}': {e}")
                return False
    
    return False


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Core checks
    'is_qgis_alive',
    'is_sip_deleted',
    'is_valid_qobject', 
    'is_valid_layer',
    'is_layer_in_project',
    
    # Safe operations
    'safe_layer_access',
    'safe_disconnect',
    'safe_emit',
    'safe_block_signals',
    
    # Safe layer variable operations (v2.3.14)
    'safe_set_layer_variable',
    'safe_set_layer_variables',
    
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
    
    # GDAL error handling (v2.3.11)
    'GdalErrorHandler',
    'suppress_gdal_warnings',
    'GDAL_AVAILABLE',
]

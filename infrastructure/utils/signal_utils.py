# -*- coding: utf-8 -*-
"""
FilterMate Signal and Layer Variable Utilities - EPIC-1 Migration

Safe wrappers for Qt signals and QGIS layer variables.
Migrated from modules/object_safety.py.

Provides crash-safe functions for:
- Signal emission and disconnection
- Layer variable management
- Layer project membership checking

All functions handle SIP deletion, RuntimeError, and OS-level access violations.

Author: FilterMate Team
Date: January 2026
Version: 4.0.8
"""

import logging
from typing import Any, Optional, Dict

logger = logging.getLogger('FilterMate.SignalUtils')

# Import QGIS components
try:
    from qgis.core import QgsProject
    from qgis.PyQt.QtWidgets import QApplication
    import platform
    QGIS_AVAILABLE = True
    IS_WINDOWS = platform.system() == 'Windows'
except ImportError:
    QGIS_AVAILABLE = False
    IS_WINDOWS = False
    QgsProject = None
    QApplication = None

# Import sip for C++ object deletion checks
try:
    import sip
    SIP_AVAILABLE = True
except ImportError:
    sip = None
    SIP_AVAILABLE = False

# Import validation utilities from same package
from .validation_utils import is_layer_valid


# =============================================================================
# QGIS Lifecycle Functions
# =============================================================================

def is_qgis_alive() -> bool:
    """
    Check if QGIS application is still running and accessible.

    CRASH FIX (v2.3.14): Must be called BEFORE QgsProject.instance()
    to prevent Windows access violations during shutdown.

    Returns:
        bool: True if QGIS is alive, False otherwise
    """
    try:
        from qgis.core import QgsApplication
        return QgsApplication.instance() is not None
    except Exception:
        return False


# =============================================================================
# Layer Project Membership
# =============================================================================

def is_layer_in_project(layer: Any, project: Optional[Any] = None) -> bool:
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
    if not is_layer_valid(layer):
        return False

    try:
        # Check if QGIS is alive before accessing project
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
# Signal Safety Functions
# =============================================================================

def safe_disconnect(signal: Any, slot: Any) -> bool:
    """
    Safely disconnect a signal from a slot.

    Handles cases where the signal is not connected or objects are deleted.

    Args:
        signal: Qt signal to disconnect
        slot: Slot to disconnect from the signal

    Returns:
        True if disconnection was successful
    """
    if signal is None or slot is None:
        return False

    try:
        signal.disconnect(slot)
        return True
    except TypeError:
        # Signal was not connected
        logger.debug("Signal was not connected")
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


# =============================================================================
# Layer Variable Management
# =============================================================================

def safe_set_layer_variable(layer_id: str, variable_key: str, value: Any, project: Optional[Any] = None) -> bool:
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
        # Check if QGIS is alive BEFORE QgsProject.instance()
        # Windows access violations cannot be caught by try/except
        if not is_qgis_alive():
            logger.debug("QGIS is not alive, skipping safe_set_layer_variable")
            return False

        if project is None:
            project = QgsProject.instance()

        if project is None:
            logger.debug("No project available for safe_set_layer_variable")
            return False

        # Check if project itself is still valid
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

        # Immediate sip deletion check FIRST
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

        # Wrap isValid() call in its own try/except
        # layer.isValid() can cause access violation if layer is partially deleted
        try:
            is_valid = layer.isValid()
        except (RuntimeError, OSError, SystemError) as e:
            logger.debug(f"Layer {layer_id} validity check failed: {e}")
            return False

        if not is_valid:
            logger.debug(f"Layer {layer_id} is invalid")
            return False

        # Final sip check immediately before C++ call
        # Minimizes race condition window
        if sip is not None:
            try:
                if sip.isdeleted(layer):
                    logger.debug(f"Layer {layer_id} deleted before setLayerVariable")
                    return False
            except (TypeError, AttributeError):
                return False

        # Flush pending Qt events BEFORE the C++ call
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

        # Atomic-style final validation before C++ call
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

        # Use direct setCustomProperty instead of
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
        # These can occur on Windows when accessing deleted objects
        logger.debug(f"System error in safe_set_layer_variable for {layer_id}: {e}")
        return False
    except Exception as e:
        logger.warning(f"Error in safe_set_layer_variable for {layer_id}: {e}")
        return False


def safe_set_layer_variables(layer_id: str, variables: Dict[str, Any], project: Optional[Any] = None) -> bool:
    """
    Safely set multiple layer variables.

    Args:
        layer_id: Layer ID to set variables on
        variables: Dictionary of variables to set
        project: Optional project to use. Uses QgsProject.instance() if None.

    Returns:
        True if all variables were set successfully
    """
    if not variables:
        # Empty dict - nothing to do
        return True

    # Set each variable individually using the safe wrapper
    all_success = True
    for key, value in variables.items():
        if not safe_set_layer_variable(layer_id, key, value, project):
            all_success = False
            logger.debug(f"Failed to set variable {key} for layer {layer_id}")

    return all_success


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'is_qgis_alive',
    'is_layer_in_project',
    'safe_disconnect',
    'safe_emit',
    'safe_set_layer_variable',
    'safe_set_layer_variables',
]

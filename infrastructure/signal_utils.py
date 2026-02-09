# -*- coding: utf-8 -*-
"""
FilterMate Signal Management Utilities

Context managers and utilities for handling Qt signals cleanly and safely.

Migrated from before_migration/modules/signal_utils.py for v4.0 hexagonal architecture.
"""

from typing import List, Optional, Callable, Any
import logging

try:
    from qgis.PyQt.QtCore import QObject
except ImportError:
    from PyQt5.QtCore import QObject

logger = logging.getLogger('FilterMate.SignalUtils')


class SignalBlocker:
    """
    Context manager for temporarily blocking Qt widget signals.
    
    This provides a cleaner, more reliable alternative to manually calling
    blockSignals(True/False) with proper cleanup even if exceptions occur.
    
    Features:
        - Automatic signal restoration on context exit
        - Handles multiple widgets simultaneously
        - Exception-safe (signals restored even on error)
        - Supports nested blocking contexts
        
    Usage:
        # Block signals for single widget
        with SignalBlocker(self.combo_box):
            self.combo_box.setCurrentIndex(5)
            # No signals emitted
        # Signals automatically restored
        
        # Block signals for multiple widgets
        with SignalBlocker(self.combo1, self.combo2, self.spin_box):
            self.combo1.setCurrentIndex(0)
            self.combo2.setCurrentIndex(1)
            self.spin_box.setValue(100)
            # No signals emitted from any widget
        # All signals automatically restored
    """
    
    def __init__(self, *widgets: QObject):
        """
        Initialize signal blocker.
        
        Args:
            *widgets: One or more Qt widgets/objects to block signals for
        """
        self.widgets = widgets
        self._previous_states = {}
        self._active = False
    
    def __enter__(self):
        """Enter context - block signals for all widgets."""
        self._active = True
        
        for widget in self.widgets:
            if widget is not None:
                try:
                    self._previous_states[widget] = widget.signalsBlocked()
                    widget.blockSignals(True)
                    logger.debug(f"Blocked signals for {widget.__class__.__name__}")
                except (AttributeError, RuntimeError) as e:
                    logger.debug(f"Could not block signals for widget: {e}")
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context - restore previous signal state for all widgets."""
        if not self._active:
            return False
        
        for widget, previous_state in self._previous_states.items():
            if widget is not None:
                try:
                    widget.blockSignals(previous_state)
                    logger.debug(f"Restored signals for {widget.__class__.__name__} to {previous_state}")
                except (AttributeError, RuntimeError) as e:
                    logger.debug(f"Could not restore signals for widget: {e}")
        
        self._previous_states.clear()
        self._active = False
        return False
    
    def is_active(self) -> bool:
        """Check if signal blocking is currently active."""
        return self._active


class SignalBlockerGroup:
    """
    Context manager for blocking signals on a group of widgets.
    
    Similar to SignalBlocker but optimized for handling large groups
    of widgets more efficiently.
    
    Usage:
        widgets = [widget1, widget2, widget3, widget4]
        with SignalBlockerGroup(widgets):
            for w in widgets:
                w.setValue(0)
    """
    
    def __init__(self, widgets: List[QObject]):
        """
        Initialize signal blocker group.
        
        Args:
            widgets: List of Qt widgets/objects to block signals for
        """
        self.widgets = widgets or []
        self._previous_states = {}
        self._active = False
    
    def __enter__(self):
        """Enter context - block signals for all widgets in group."""
        self._active = True
        
        for widget in self.widgets:
            if widget is not None:
                try:
                    self._previous_states[id(widget)] = (widget, widget.signalsBlocked())
                    widget.blockSignals(True)
                except (AttributeError, RuntimeError):
                    pass
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context - restore previous signal state for all widgets."""
        if not self._active:
            return False
        
        for widget_id, (widget, previous_state) in self._previous_states.items():
            if widget is not None:
                try:
                    widget.blockSignals(previous_state)
                except (AttributeError, RuntimeError):
                    pass
        
        self._previous_states.clear()
        self._active = False
        return False


class SignalConnection:
    """
    Context manager for temporarily connecting a signal.
    
    Automatically disconnects the signal when exiting the context,
    even if an exception occurs. Useful for one-time signal handlers.
    
    Usage:
        with SignalConnection(widget.signal, handler_function):
            widget.trigger_signal()
        # signal automatically disconnected
    """
    
    def __init__(self, signal, slot: Callable):
        """
        Initialize signal connection.
        
        Args:
            signal: Qt signal to connect
            slot: Function/method to connect to signal
        """
        self.signal = signal
        self.slot = slot
        self._connected = False
    
    def __enter__(self):
        """Enter context - connect signal to slot."""
        try:
            self.signal.connect(self.slot)
            self._connected = True
            logger.debug(f"Connected signal to {self.slot.__name__}")
        except (AttributeError, TypeError, RuntimeError) as e:
            logger.debug(f"Could not connect signal: {e}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context - disconnect signal from slot."""
        if self._connected:
            try:
                self.signal.disconnect(self.slot)
                logger.debug(f"Disconnected signal from {self.slot.__name__}")
            except (AttributeError, TypeError, RuntimeError) as e:
                logger.debug(f"Could not disconnect signal: {e}")
        self._connected = False
        return False


class SafeSignalEmitter:
    """
    Wrapper for safely emitting signals with error handling.
    
    Prevents exceptions during signal emission from crashing the application.
    
    Usage:
        emitter = SafeSignalEmitter(widget.mySignal)
        emitter.emit(arg1, arg2)  # Won't crash even if slot raises
    """
    
    def __init__(self, signal, error_handler: Optional[Callable] = None):
        """
        Initialize safe signal emitter.
        
        Args:
            signal: Qt signal to wrap
            error_handler: Optional callback for handling errors
        """
        self.signal = signal
        self.error_handler = error_handler
    
    def emit(self, *args, **kwargs) -> bool:
        """
        Safely emit the signal.
        
        Args:
            *args: Arguments to pass to signal.emit()
            **kwargs: Not used (for compatibility)
            
        Returns:
            True if emission was successful
        """
        try:
            self.signal.emit(*args)
            return True
        except Exception as e:
            logger.error(f"Error emitting signal: {e}")
            if self.error_handler:
                try:
                    self.error_handler(e)
                except Exception:
                    pass
            return False


def block_signals(*widgets):
    """
    Convenience function for creating a SignalBlocker context manager.
    
    Args:
        *widgets: Widgets to block signals for
        
    Returns:
        SignalBlocker context manager
        
    Usage:
        with block_signals(combo1, combo2):
            # Update widgets without triggering signals
            pass
    """
    return SignalBlocker(*widgets)


def block_signals_group(widgets: List[QObject]):
    """
    Convenience function for creating a SignalBlockerGroup context manager.
    
    Args:
        widgets: List of widgets to block signals for
        
    Returns:
        SignalBlockerGroup context manager
    """
    return SignalBlockerGroup(widgets)


__all__ = [
    'SignalBlocker',
    'SignalBlockerGroup', 
    'SignalConnection',
    'SafeSignalEmitter',
    'block_signals',
    'block_signals_group',
]

"""
FilterMate Signal Management Utilities

Context managers and utilities for handling Qt signals cleanly and safely.
"""

from typing import List, Optional
try:
    from qgis.PyQt.QtCore import QObject
except ImportError:
    from PyQt5.QtCore import QObject

import logging
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
        
        # Nested blocking
        with SignalBlocker(self.widget1):
            # widget1 signals blocked
            with SignalBlocker(self.widget2):
                # Both blocked
                pass
            # Only widget1 still blocked
        # All restored
    """
    
    def __init__(self, *widgets: QObject):
        """
        Initialize signal blocker.
        
        Args:
            *widgets: One or more Qt widgets/objects to block signals for
            
        Example:
            blocker = SignalBlocker(combo_box, spin_box, button)
        """
        self.widgets = widgets
        self._previous_states = {}
        self._active = False
    
    def __enter__(self):
        """
        Enter context - block signals for all widgets.
        
        Returns:
            Self for use in 'with ... as' statements
        """
        self._active = True
        
        # Store previous signal state for each widget
        for widget in self.widgets:
            if widget is not None:
                try:
                    self._previous_states[widget] = widget.signalsBlocked()
                    widget.blockSignals(True)
                    logger.debug(f"Blocked signals for {widget.__class__.__name__}")
                except (AttributeError, RuntimeError) as e:
                    # Widget may not support signals or may be deleted
                    logger.debug(f"Could not block signals for widget: {e}")
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit context - restore previous signal state for all widgets.
        
        Args:
            exc_type: Exception type (if exception occurred)
            exc_val: Exception value
            exc_tb: Exception traceback
            
        Returns:
            False to propagate exceptions (normal behavior)
        """
        if not self._active:
            return False
        
        # Restore previous signal state for each widget
        for widget, previous_state in self._previous_states.items():
            if widget is not None:
                try:
                    widget.blockSignals(previous_state)
                    logger.debug(f"Restored signals for {widget.__class__.__name__} to {previous_state}")
                except (AttributeError, RuntimeError) as e:
                    # Widget may have been deleted
                    logger.debug(f"Could not restore signals for widget: {e}")
        
        self._previous_states.clear()
        self._active = False
        
        # Don't suppress exceptions
        return False
    
    def is_active(self) -> bool:
        """
        Check if signal blocking is currently active.
        
        Returns:
            True if currently inside the context manager
        """
        return self._active


class SignalConnection:
    """
    Context manager for temporarily connecting a signal.
    
    Automatically disconnects the signal when exiting the context,
    even if an exception occurs. Useful for one-time signal handlers.
    
    Usage:
        with SignalConnection(widget.signal, handler_function):
            # signal connected to handler
            widget.trigger_signal()
        # signal automatically disconnected
    """
    
    def __init__(self, signal, slot):
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
        """Enter context - connect signal."""
        try:
            self.signal.connect(self.slot)
            self._connected = True
            logger.debug(f"Connected signal {self.signal} to {self.slot}")
        except Exception as e:
            logger.warning(f"Could not connect signal: {e}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context - disconnect signal."""
        if self._connected:
            try:
                self.signal.disconnect(self.slot)
                logger.debug(f"Disconnected signal {self.signal} from {self.slot}")
            except Exception as e:
                logger.debug(f"Could not disconnect signal (may already be disconnected): {e}")
        return False


class SignalBlockerGroup:
    """
    Manages multiple SignalBlocker contexts for complex widget hierarchies.
    
    Useful when you need to block/unblock groups of widgets repeatedly,
    or want to organize blocking by functional groups.
    
    Usage:
        blocker = SignalBlockerGroup()
        blocker.add_group('exploring', exploring_widget1, exploring_widget2)
        blocker.add_group('filtering', filtering_widget1, filtering_widget2)
        
        # Block only exploring widgets
        with blocker.block('exploring'):
            # Update exploring widgets
            pass
        
        # Block all widgets
        with blocker.block_all():
            # Update all widgets
            pass
    """
    
    def __init__(self):
        """Initialize signal blocker group."""
        self._groups = {}
    
    def add_group(self, name: str, *widgets: QObject):
        """
        Add a named group of widgets.
        
        Args:
            name: Group identifier
            *widgets: Widgets to include in group
        """
        self._groups[name] = list(widgets)
        logger.debug(f"Added signal blocker group '{name}' with {len(widgets)} widgets")
    
    def remove_group(self, name: str):
        """
        Remove a named group.
        
        Args:
            name: Group identifier to remove
        """
        if name in self._groups:
            del self._groups[name]
            logger.debug(f"Removed signal blocker group '{name}'")
    
    def block(self, *group_names: str):
        """
        Create SignalBlocker for specified groups.
        
        Args:
            *group_names: Names of groups to block
            
        Returns:
            SignalBlocker context manager
            
        Example:
            with blocker.block('exploring', 'filtering'):
                # Both groups blocked
                pass
        """
        widgets = []
        for name in group_names:
            if name in self._groups:
                widgets.extend(self._groups[name])
            else:
                logger.warning(f"Signal blocker group '{name}' not found")
        
        return SignalBlocker(*widgets)
    
    def block_all(self):
        """
        Create SignalBlocker for all registered groups.
        
        Returns:
            SignalBlocker context manager blocking all groups
        """
        all_widgets = []
        for widgets in self._groups.values():
            all_widgets.extend(widgets)
        
        return SignalBlocker(*all_widgets)
    
    def get_group(self, name: str) -> Optional[List[QObject]]:
        """
        Get widgets in a named group.
        
        Args:
            name: Group identifier
            
        Returns:
            List of widgets in group, or None if group doesn't exist
        """
        return self._groups.get(name)
    
    def list_groups(self) -> List[str]:
        """
        Get names of all registered groups.
        
        Returns:
            List of group names
        """
        return list(self._groups.keys())


# ============================================================================
# Convenience Functions
# ============================================================================

def block_signals(*widgets: QObject):
    """
    Create a SignalBlocker context manager (convenience function).
    
    Args:
        *widgets: Widgets to block signals for
        
    Returns:
        SignalBlocker context manager
        
    Example:
        with block_signals(widget1, widget2):
            widget1.setValue(10)
            widget2.setCurrentIndex(0)
    """
    return SignalBlocker(*widgets)


def connect_signal(signal, slot):
    """
    Create a SignalConnection context manager (convenience function).
    
    Args:
        signal: Qt signal to connect
        slot: Function/method to connect
        
    Returns:
        SignalConnection context manager
        
    Example:
        with connect_signal(button.clicked, on_click_handler):
            button.click()  # Handler will be called
    """
    return SignalConnection(signal, slot)


def safe_disconnect(signal, slot=None):
    """
    Safely disconnect a signal without raising errors.
    
    Args:
        signal: Qt signal to disconnect
        slot: Optional specific slot to disconnect. If None, disconnects all.
        
    Returns:
        True if disconnection successful, False otherwise
        
    Example:
        # Disconnect specific slot
        safe_disconnect(widget.valueChanged, on_value_changed)
        
        # Disconnect all slots
        safe_disconnect(widget.valueChanged)
    """
    try:
        if slot is None:
            signal.disconnect()
        else:
            signal.disconnect(slot)
        return True
    except (TypeError, RuntimeError) as e:
        logger.debug(f"Could not disconnect signal (may not be connected): {e}")
        return False


def safe_connect(signal, slot, connection_type=None):
    """
    Safely connect a signal, disconnecting first if already connected.
    
    Prevents duplicate connections by disconnecting the specific slot first,
    then connecting cleanly. This is safer than just connecting, as Qt will
    create multiple connections if you call connect() multiple times.
    
    Args:
        signal: Qt signal to connect
        slot: Function/method to connect
        connection_type: Optional Qt.ConnectionType (e.g., Qt.QueuedConnection)
        
    Returns:
        True if connection successful, False otherwise
        
    Example:
        # Safe connection - won't create duplicates
        safe_connect(widget.valueChanged, on_value_changed)
        safe_connect(widget.valueChanged, on_value_changed)  # Won't duplicate
        
        # With connection type
        from qgis.PyQt.QtCore import Qt
        safe_connect(widget.signal, handler, Qt.QueuedConnection)
    """
    try:
        # First disconnect this specific slot if connected
        safe_disconnect(signal, slot)
        
        # Now connect cleanly
        if connection_type is None:
            signal.connect(slot)
        else:
            signal.connect(slot, connection_type)
        
        logger.debug(f"Safely connected signal to {slot.__name__ if hasattr(slot, '__name__') else slot}")
        return True
    except (TypeError, RuntimeError, AttributeError) as e:
        logger.error(f"Could not connect signal: {e}")
        return False


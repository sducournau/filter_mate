# -*- coding: utf-8 -*-
"""
Integration Test Utilities - Signal Spy - ARCH-049

Utilities for verifying Qt signal emissions during testing.

Part of Phase 5 Integration & Release.

Author: FilterMate Team
Date: January 2026
"""
from typing import List, Any, Optional, Callable
from unittest.mock import MagicMock
import time


class SignalSpy:
    """
    Utility for spying on Qt signal emissions.
    
    Records all emissions of a signal and provides
    verification methods for testing.
    
    Example:
        spy = SignalSpy()
        signal.connect(spy.slot)
        # ... trigger signal ...
        assert spy.count == 1
        assert spy.last_args == (expected_arg,)
    """
    
    def __init__(self, signal=None):
        """
        Initialize signal spy.
        
        Args:
            signal: Optional signal to connect to immediately
        """
        self._emissions: List[tuple] = []
        self._connected_signals: List = []
        
        if signal is not None:
            self.connect(signal)
    
    def connect(self, signal) -> 'SignalSpy':
        """
        Connect to a signal.
        
        Args:
            signal: Qt signal to spy on
            
        Returns:
            Self for chaining
        """
        signal.connect(self.slot)
        self._connected_signals.append(signal)
        return self
    
    def disconnect(self) -> None:
        """Disconnect from all connected signals."""
        for signal in self._connected_signals:
            try:
                signal.disconnect(self.slot)
            except (TypeError, RuntimeError):
                pass  # Already disconnected
        self._connected_signals.clear()
    
    def slot(self, *args, **kwargs) -> None:
        """Slot that records signal emissions."""
        self._emissions.append((args, kwargs))
    
    def clear(self) -> None:
        """Clear recorded emissions."""
        self._emissions.clear()
    
    @property
    def count(self) -> int:
        """Number of times signal was emitted."""
        return len(self._emissions)
    
    @property
    def emissions(self) -> List[tuple]:
        """All recorded emissions."""
        return self._emissions.copy()
    
    @property
    def last_emission(self) -> Optional[tuple]:
        """Most recent emission (args, kwargs) or None."""
        return self._emissions[-1] if self._emissions else None
    
    @property
    def last_args(self) -> Optional[tuple]:
        """Args from most recent emission."""
        if self._emissions:
            return self._emissions[-1][0]
        return None
    
    @property
    def last_kwargs(self) -> Optional[dict]:
        """Kwargs from most recent emission."""
        if self._emissions:
            return self._emissions[-1][1]
        return None
    
    def was_emitted(self) -> bool:
        """Check if signal was emitted at least once."""
        return len(self._emissions) > 0
    
    def was_emitted_with(self, *expected_args, **expected_kwargs) -> bool:
        """
        Check if signal was emitted with specific arguments.
        
        Args:
            *expected_args: Expected positional arguments
            **expected_kwargs: Expected keyword arguments
            
        Returns:
            True if any emission matches
        """
        for args, kwargs in self._emissions:
            if args == expected_args and kwargs == expected_kwargs:
                return True
        return False
    
    def wait_for_emission(
        self,
        timeout_ms: int = 1000,
        count: int = 1
    ) -> bool:
        """
        Wait for signal emission(s).
        
        Args:
            timeout_ms: Maximum wait time in milliseconds
            count: Number of emissions to wait for
            
        Returns:
            True if expected emissions occurred within timeout
        """
        start = time.time()
        timeout_s = timeout_ms / 1000.0
        
        while (time.time() - start) < timeout_s:
            if self.count >= count:
                return True
            time.sleep(0.01)
        
        return self.count >= count


class SignalBlocker:
    """
    Context manager that temporarily blocks signals.
    
    Example:
        with SignalBlocker(widget):
            widget.setValue(10)  # Won't emit valueChanged
    """
    
    def __init__(self, *objects):
        """
        Initialize signal blocker.
        
        Args:
            *objects: Qt objects to block signals for
        """
        self._objects = objects
        self._previous_states: List[bool] = []
    
    def __enter__(self):
        """Block signals on enter."""
        for obj in self._objects:
            if hasattr(obj, 'blockSignals'):
                self._previous_states.append(obj.signalsBlocked())
                obj.blockSignals(True)
            else:
                self._previous_states.append(False)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore signal states on exit."""
        for obj, state in zip(self._objects, self._previous_states):
            if hasattr(obj, 'blockSignals'):
                obj.blockSignals(state)
        return False


class MockSignal:
    """
    Mock Qt signal for testing.
    
    Simulates a Qt signal without requiring Qt.
    
    Example:
        signal = MockSignal()
        handler = Mock()
        signal.connect(handler)
        signal.emit("value")
        handler.assert_called_once_with("value")
    """
    
    def __init__(self):
        """Initialize mock signal."""
        self._handlers: List[Callable] = []
        self._emission_count = 0
    
    def connect(self, handler: Callable) -> None:
        """Connect a handler to the signal."""
        self._handlers.append(handler)
    
    def disconnect(self, handler: Optional[Callable] = None) -> None:
        """
        Disconnect handler(s) from signal.
        
        Args:
            handler: Specific handler to disconnect, or None for all
        """
        if handler is None:
            self._handlers.clear()
        elif handler in self._handlers:
            self._handlers.remove(handler)
    
    def emit(self, *args, **kwargs) -> None:
        """
        Emit the signal with arguments.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        self._emission_count += 1
        for handler in self._handlers:
            handler(*args, **kwargs)
    
    @property
    def emission_count(self) -> int:
        """Number of times signal was emitted."""
        return self._emission_count
    
    def __call__(self, *args, **kwargs):
        """Allow calling signal directly to emit."""
        self.emit(*args, **kwargs)


def create_mock_signal() -> MockSignal:
    """Factory function to create mock signals."""
    return MockSignal()

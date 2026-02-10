# -*- coding: utf-8 -*-
"""
Flag Manager for FilterMate

Provides thread-safe, timeout-protected flags for coordinating
asynchronous operations and preventing deadlocks.

Key Features:
- Automatic timeout and reset for stale flags
- Context manager support for safe acquisition
- Thread-safe operations with RLock
- Monitoring and debugging support

Usage:
    from infrastructure.state.flag_manager import FlagManager, TimedFlag

    # Create a timed flag
    loading_flag = TimedFlag("loading_project", timeout_ms=30000)

    # Using context manager (recommended)
    with loading_flag.acquire():
        # Flag is automatically set and will reset on exit
        do_loading_work()

    # Or manual control
    loading_flag.set()
    try:
        do_work()
    finally:
        loading_flag.clear()

Author: FilterMate Team
Version: 2.6.0 (December 2025)
"""

import threading
import time
from typing import Dict, Optional, Any, Callable
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum

from ..logging import get_app_logger

logger = get_app_logger()


class FlagState(Enum):
    """Flag states for monitoring."""
    CLEAR = "clear"
    SET = "set"
    EXPIRED = "expired"
    ACQUIRED = "acquired"  # Set via context manager


@dataclass
class FlagStats:
    """Statistics for flag usage."""
    total_acquisitions: int = 0
    total_timeouts: int = 0
    total_manual_clears: int = 0
    longest_hold_ms: float = 0.0
    current_hold_ms: float = 0.0


class TimedFlag:
    """
    Thread-safe flag with automatic timeout protection.

    Prevents deadlocks by automatically resetting flags that have been
    set for longer than the configured timeout. Provides context manager
    support for safe acquisition/release patterns.

    Thread Safety:
        All operations are protected by RLock, safe for concurrent access.

    Timeout Behavior:
        When checking is_set, if the flag has been set for longer than
        timeout_ms, it will be automatically reset and logged as a warning.

    Example:
        >>> flag = TimedFlag("loading", timeout_ms=30000)
        >>>
        >>> # Context manager (recommended)
        >>> with flag.acquire():
        ...     perform_loading()
        >>>
        >>> # Check if set
        >>> if flag.is_set:
        ...     print("Still loading...")
    """

    def __init__(
        self,
        name: str,
        timeout_ms: int = 30000,
        on_timeout: Callable[['TimedFlag'], None] = None,
        auto_log: bool = True
    ):
        """
        Initialize timed flag.

        Args:
            name: Human-readable name for logging
            timeout_ms: Milliseconds before auto-reset (default: 30000)
            on_timeout: Optional callback when timeout occurs
            auto_log: Whether to log state changes (default: True)
        """
        self.name = name
        self.timeout_ms = timeout_ms
        self.on_timeout = on_timeout
        self.auto_log = auto_log

        self._value = False
        self._timestamp = 0.0
        self._lock = threading.RLock()
        self._owner_thread: Optional[int] = None

        # Statistics
        self.stats = FlagStats()

        if self.auto_log:
            logger.debug(f"TimedFlag '{name}' created (timeout={timeout_ms}ms)")

    def _current_time_ms(self) -> float:
        """Get current time in milliseconds."""
        return time.time() * 1000

    def _check_timeout(self) -> bool:
        """
        Check if flag has timed out and reset if so.

        Returns:
            True if timeout occurred and flag was reset
        """
        if not self._value:
            return False

        elapsed = self._current_time_ms() - self._timestamp
        if elapsed > self.timeout_ms:
            if self.auto_log:
                logger.warning(
                    f"🔧 STABILITY: TimedFlag '{self.name}' auto-reset "
                    f"after timeout ({elapsed:.0f}ms > {self.timeout_ms}ms)"
                )

            self.stats.total_timeouts += 1
            self._value = False
            self._timestamp = 0
            self._owner_thread = None

            # Call timeout callback if provided
            if self.on_timeout:
                try:
                    self.on_timeout(self)
                except Exception as e:
                    logger.error(f"Error in timeout callback for '{self.name}': {e}")

            return True
        return False

    @property
    def is_set(self) -> bool:
        """
        Check if flag is currently set (with timeout check).

        Automatically resets flag if timeout has expired.

        Returns:
            True if flag is set and not timed out
        """
        with self._lock:
            self._check_timeout()
            return self._value

    @property
    def elapsed_ms(self) -> float:
        """
        Get milliseconds since flag was set.

        Returns:
            Elapsed time in ms, or 0 if not set
        """
        with self._lock:
            if not self._value:
                return 0.0
            return self._current_time_ms() - self._timestamp

    @property
    def state(self) -> FlagState:
        """Get current flag state."""
        with self._lock:
            if self._check_timeout():
                return FlagState.EXPIRED
            if self._value:
                if self._owner_thread is not None:
                    return FlagState.ACQUIRED
                return FlagState.SET
            return FlagState.CLEAR

    def set(self) -> bool:
        """
        Set the flag.

        Returns:
            True if flag was set, False if already set
        """
        with self._lock:
            if self._value:
                return False

            self._value = True
            self._timestamp = self._current_time_ms()
            self.stats.total_acquisitions += 1

            if self.auto_log:
                logger.debug(f"TimedFlag '{self.name}' SET")

            return True

    def clear(self) -> bool:
        """
        Clear the flag.

        Returns:
            True if flag was cleared, False if already clear
        """
        with self._lock:
            if not self._value:
                return False

            # Update statistics
            elapsed = self._current_time_ms() - self._timestamp
            self.stats.current_hold_ms = elapsed
            if elapsed > self.stats.longest_hold_ms:
                self.stats.longest_hold_ms = elapsed

            self._value = False
            self._timestamp = 0
            self._owner_thread = None
            self.stats.total_manual_clears += 1

            if self.auto_log:
                logger.debug(f"TimedFlag '{self.name}' CLEARED (held {elapsed:.0f}ms)")

            return True

    @contextmanager
    def acquire(self):
        """
        Context manager for safe flag acquisition.

        Automatically sets flag on enter and clears on exit,
        even if an exception occurs.

        Example:
            >>> with flag.acquire():
            ...     # Flag is set
            ...     do_work()
            >>> # Flag is automatically cleared

        Yields:
            self for optional chaining
        """
        with self._lock:
            self._value = True
            self._timestamp = self._current_time_ms()
            self._owner_thread = threading.current_thread().ident
            self.stats.total_acquisitions += 1

            if self.auto_log:
                logger.debug(f"TimedFlag '{self.name}' ACQUIRED (thread {self._owner_thread})")

        try:
            yield self
        finally:
            with self._lock:
                elapsed = self._current_time_ms() - self._timestamp
                self.stats.current_hold_ms = elapsed
                if elapsed > self.stats.longest_hold_ms:
                    self.stats.longest_hold_ms = elapsed

                self._value = False
                self._timestamp = 0
                self._owner_thread = None

                if self.auto_log:
                    logger.debug(f"TimedFlag '{self.name}' RELEASED (held {elapsed:.0f}ms)")

    def get_status(self) -> Dict[str, Any]:
        """
        Get detailed status for monitoring.

        Returns:
            Dict with current state and statistics
        """
        with self._lock:
            return {
                'name': self.name,
                'is_set': self._value,
                'state': self.state.value,
                'elapsed_ms': self.elapsed_ms,
                'timeout_ms': self.timeout_ms,
                'owner_thread': self._owner_thread,
                'stats': {
                    'total_acquisitions': self.stats.total_acquisitions,
                    'total_timeouts': self.stats.total_timeouts,
                    'total_manual_clears': self.stats.total_manual_clears,
                    'longest_hold_ms': self.stats.longest_hold_ms,
                }
            }


class FlagManager:
    """
    Centralized manager for all application flags.

    Provides:
    - Centralized flag creation and access
    - Periodic health checks for stale flags
    - Debugging and monitoring support

    Example:
        >>> manager = FlagManager()
        >>>
        >>> # Get or create flag
        >>> loading = manager.get_flag("loading_project", timeout_ms=30000)
        >>>
        >>> # Check all flags
        >>> stale = manager.check_stale_flags()
        >>> if stale:
        ...     print(f"Reset {len(stale)} stale flags")
    """

    # Default timeouts for common operations
    DEFAULT_TIMEOUTS = {
        'loading_project': 30000,      # 30 seconds
        'initializing_project': 30000,  # 30 seconds
        'processing_queue': 60000,      # 60 seconds
        'updating_layers': 15000,       # 15 seconds
        'plugin_busy': 60000,           # 60 seconds
    }

    def __init__(self):
        """Initialize flag manager."""
        self._flags: Dict[str, TimedFlag] = {}
        self._lock = threading.RLock()

        logger.info("✓ FlagManager initialized")

    def get_flag(
        self,
        name: str,
        timeout_ms: int = None,
        **kwargs
    ) -> TimedFlag:
        """
        Get or create a timed flag.

        Args:
            name: Flag name
            timeout_ms: Optional custom timeout (uses DEFAULT_TIMEOUTS if not specified)
            **kwargs: Additional TimedFlag configuration

        Returns:
            TimedFlag instance
        """
        with self._lock:
            if name not in self._flags:
                if timeout_ms is None:
                    timeout_ms = self.DEFAULT_TIMEOUTS.get(name, 30000)

                self._flags[name] = TimedFlag(name, timeout_ms=timeout_ms, **kwargs)

            return self._flags[name]

    def check_stale_flags(self) -> list:
        """
        Check all flags for timeout and reset stale ones.

        Returns:
            List of flag names that were reset
        """
        reset_flags = []

        with self._lock:
            for name, flag in self._flags.items():
                # Access is_set to trigger timeout check
                if flag._check_timeout():
                    reset_flags.append(name)

        return reset_flags

    def reset_all(self):
        """Reset all flags to clear state."""
        with self._lock:
            for flag in self._flags.values():
                flag.clear()
            logger.info(f"Reset all {len(self._flags)} flags")

    def get_all_statuses(self) -> Dict[str, Dict]:
        """
        Get status of all flags.

        Returns:
            Dict mapping flag names to their status dicts
        """
        with self._lock:
            return {
                name: flag.get_status()
                for name, flag in self._flags.items()
            }

    def get_set_flags(self) -> list:
        """
        Get list of currently set flags.

        Returns:
            List of names of set flags
        """
        with self._lock:
            return [
                name for name, flag in self._flags.items()
                if flag.is_set
            ]


# Global manager instance
flag_manager = FlagManager()


# Convenience function for common flags
def get_loading_flag() -> TimedFlag:
    """Get the loading_project flag."""
    return flag_manager.get_flag("loading_project")


def get_initializing_flag() -> TimedFlag:
    """Get the initializing_project flag."""
    return flag_manager.get_flag("initializing_project")


def get_processing_flag() -> TimedFlag:
    """Get the processing_queue flag."""
    return flag_manager.get_flag("processing_queue")

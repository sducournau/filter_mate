"""
FilterMate Debouncer Utility.

Debounce function calls with configurable delay.
Replaces scattered QTimer debouncing logic throughout the codebase.
"""
from typing import Callable, Optional

try:
    from qgis.PyQt.QtCore import QTimer, QObject
    HAS_QT = True
except ImportError:
    HAS_QT = False
    QObject = object


class Debouncer(QObject if HAS_QT else object):
    """
    Debounce function calls with configurable delay.

    Useful for delaying expensive operations (like filtering) until
    user input has stopped for a specified duration.

    Usage:
        # Create debouncer with 300ms delay
        debouncer = Debouncer(delay_ms=300)

        # In event handler
        def on_text_changed(text):
            debouncer.call(expensive_search, text)

        # Cancel pending call
        debouncer.cancel()

        # Execute immediately if pending
        debouncer.flush()

        # Cleanup when done
        debouncer.cleanup()
    """

    def __init__(self, delay_ms: int = 300, parent=None):
        """
        Initialize Debouncer.

        Args:
            delay_ms: Delay in milliseconds before executing
            parent: Optional parent QObject for memory management
        """
        if HAS_QT:
            super().__init__(parent)
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self._execute)
        else:
            self._timer = None

        self._delay = delay_ms
        self._pending_func: Optional[Callable] = None
        self._pending_args: tuple = ()
        self._pending_kwargs: dict = {}
        self._is_cancelled = False

    @property
    def delay_ms(self) -> int:
        """Get current delay in milliseconds."""
        return self._delay

    @delay_ms.setter
    def delay_ms(self, value: int):
        """Set delay in milliseconds."""
        self._delay = max(0, value)

    def call(self, func: Callable, *args, **kwargs):
        """
        Schedule a debounced function call.

        If called multiple times within the delay period,
        only the last call will be executed.

        Args:
            func: Function to call after delay
            *args: Positional arguments to pass to func
            **kwargs: Keyword arguments to pass to func
        """
        self._pending_func = func
        self._pending_args = args
        self._pending_kwargs = kwargs
        self._is_cancelled = False

        if HAS_QT and self._timer:
            self._timer.stop()
            self._timer.start(self._delay)
        else:
            # Fallback: immediate execution if Qt not available
            self._execute()

    def _execute(self):
        """Execute the pending function."""
        if self._is_cancelled:
            self._clear_pending()
            return

        if self._pending_func is not None:
            try:
                self._pending_func(*self._pending_args, **self._pending_kwargs)
            finally:
                self._clear_pending()

    def _clear_pending(self):
        """Clear pending call state."""
        self._pending_func = None
        self._pending_args = ()
        self._pending_kwargs = {}

    def cancel(self):
        """
        Cancel any pending call.

        The pending function will not be executed.
        """
        self._is_cancelled = True
        if HAS_QT and self._timer:
            self._timer.stop()
        self._clear_pending()

    def flush(self):
        """
        Execute pending call immediately if any.

        Useful when you need to force execution before
        the delay expires (e.g., on form submit).
        """
        if HAS_QT and self._timer and self._timer.isActive():
            self._timer.stop()
            self._execute()
        elif self._pending_func is not None:
            self._execute()

    def is_pending(self) -> bool:
        """
        Check if there's a pending call.

        Returns:
            True if a call is scheduled and not yet executed
        """
        if HAS_QT and self._timer:
            return self._timer.isActive()
        return self._pending_func is not None

    def remaining_time(self) -> int:
        """
        Get remaining time until execution.

        Returns:
            Remaining time in milliseconds, or 0 if not pending
        """
        if HAS_QT and self._timer:
            return self._timer.remainingTime() if self._timer.isActive() else 0
        return 0

    def cleanup(self):
        """
        Clean up resources.

        Call this when the debouncer is no longer needed.
        """
        self.cancel()
        if HAS_QT and self._timer:
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None

    def __del__(self):
        """Destructor cleanup."""
        try:
            if self._timer is not None:
                self._timer.stop()
        except (RuntimeError, AttributeError):
            # Qt object may already be deleted
            pass


class ThrottledDebouncer(Debouncer):
    """
    Debouncer variant that also throttles calls.

    Executes immediately on first call, then debounces subsequent calls.
    Useful for responsive UI that still needs rate limiting.

    Usage:
        throttled = ThrottledDebouncer(delay_ms=300, throttle_ms=100)

        # First call executes immediately
        throttled.call(search, "a")

        # Subsequent rapid calls are debounced
        throttled.call(search, "ab")
        throttled.call(search, "abc")  # Only this one executes after delay
    """

    def __init__(self, delay_ms: int = 300, throttle_ms: int = 100, parent=None):
        """
        Initialize ThrottledDebouncer.

        Args:
            delay_ms: Debounce delay in milliseconds
            throttle_ms: Minimum time between immediate executions
            parent: Optional parent QObject
        """
        super().__init__(delay_ms, parent)
        self._throttle_ms = throttle_ms
        self._last_execution = 0

        if HAS_QT:
            from qgis.PyQt.QtCore import QDateTime
            self._get_time = lambda: QDateTime.currentMSecsSinceEpoch()
        else:
            import time
            self._get_time = lambda: int(time.time() * 1000)

    def call(self, func: Callable, *args, **kwargs):
        """
        Schedule a throttled+debounced function call.

        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        current_time = self._get_time()
        time_since_last = current_time - self._last_execution

        if time_since_last >= self._throttle_ms:
            # Enough time has passed, execute immediately
            self._last_execution = current_time
            self.cancel()
            try:
                func(*args, **kwargs)
            except Exception:
                raise
        else:
            # Within throttle period, use debounce
            super().call(func, *args, **kwargs)

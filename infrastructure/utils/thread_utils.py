"""
Thread safety utilities for FilterMate.

Provides decorators and helpers to enforce thread-safety constraints
at development time, particularly for methods that must only be called
from the Qt main thread (e.g. finished(), UI callbacks, iface access).

The @main_thread_only decorator is active when Python runs in debug mode
(the default). It becomes a no-op when Python is run with -O (optimized),
so there is zero overhead in production.
"""

import functools
import logging
import threading

logger = logging.getLogger(__name__)

# Cache the main thread ID at import time (module is imported from main thread)
_MAIN_THREAD_ID = threading.main_thread().ident


def main_thread_only(func):
    """Decorator that asserts the wrapped function runs on the main thread.

    In debug mode (default Python), raises RuntimeError if the decorated
    function is called from a worker thread. In optimized mode (python -O),
    this decorator is a transparent no-op.

    Usage::

        @main_thread_only
        def finished(self, result):
            iface.messageBar().pushMessage(...)

    Args:
        func: The function or method to wrap.

    Returns:
        The wrapped function with a main-thread guard (debug) or
        the original function unchanged (optimized).
    """
    if not __debug__:
        return func

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        current = threading.current_thread()
        if current.ident != _MAIN_THREAD_ID:
            raise RuntimeError(
                f"{func.__qualname__}() must be called from the main thread, "
                f"but was called from thread '{current.name}' "
                f"(id={current.ident}). "
                f"Move this call to finished() or use QTimer.singleShot()."
            )
        return func(*args, **kwargs)

    return wrapper

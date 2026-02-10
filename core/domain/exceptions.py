# -*- coding: utf-8 -*-
"""
FilterMate Domain Exceptions

Custom exceptions used throughout FilterMate.

Migrated from modules/customExceptions.py to core/domain/exceptions.py
"""


class SignalStateChangeError(Exception):
    """
    Error raised when a signal state change operation fails.

    This can occur when:
    - Signals are blocked/unblocked incorrectly
    - Signal handlers are not connected/disconnected properly
    - Widget state is inconsistent during signal operations
    """


class LayerInvalidError(Exception):
    """Error raised when a layer is invalid or has been deleted."""


class ExpressionValidationError(Exception):
    """Error raised when a QGIS expression fails validation."""


class ConfigurationError(Exception):
    """Error raised when configuration is invalid or missing."""


class BackendNotAvailableError(Exception):
    """Error raised when a required backend is not available."""


__all__ = [
    'SignalStateChangeError',
    'LayerInvalidError',
    'ExpressionValidationError',
    'ConfigurationError',
    'BackendNotAvailableError',
]

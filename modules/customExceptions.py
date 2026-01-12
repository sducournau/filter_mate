# -*- coding: utf-8 -*-
"""
DEPRECATED: Legacy compatibility shim for modules/customExceptions

Migrated to core/domain/exceptions.py
This file provides backward compatibility only.
"""
import warnings

warnings.warn(
    "modules.customExceptions is deprecated. Use core.domain.exceptions instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
try:
    from ..core.domain.exceptions import SignalStateChangeError
except ImportError:
    # Fallback
    class SignalStateChangeError(Exception):
        """Error during signal state change."""
        pass

__all__ = ['SignalStateChangeError']

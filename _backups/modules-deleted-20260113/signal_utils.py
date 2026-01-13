# -*- coding: utf-8 -*-
"""
DEPRECATED: Use infrastructure.signal_utils instead

Shim module for backward compatibility.
This file will be removed in v5.0.

Migration guide:
    OLD: from modules.signal_utils import SignalBlocker, SignalBlockerGroup
    NEW: from infrastructure.signal_utils import SignalBlocker, SignalBlockerGroup
    
Or use shorthand:
    from infrastructure import SignalBlocker, SignalBlockerGroup
"""

import warnings

warnings.warn(
    "modules.signal_utils is deprecated. Use infrastructure.signal_utils instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from infrastructure.signal_utils import (
    SignalBlocker,
    SignalBlockerGroup,
    SignalConnection,
    ConnectionManager,
    SafeSignalEmitter,
    block_signals,
    block_signals_group,
)

__all__ = [
    'SignalBlocker',
    'SignalBlockerGroup',
    'SignalConnection',
    'ConnectionManager',
    'SafeSignalEmitter',
    'block_signals',
    'block_signals_group',
]

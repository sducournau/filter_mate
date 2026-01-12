"""
FilterMate Infrastructure Module.

Cross-cutting concerns: configuration, caching, logging, utilities.
"""

# Signal management utilities
from .signal_utils import (
    SignalBlocker,
    SignalBlockerGroup,
    SignalConnection,
    ConnectionManager,
    SafeSignalEmitter,
    block_signals,
    block_signals_group,
)

# State management
from .state_manager import (
    LayerStateManager,
    ProjectStateManager,
    get_layer_state_manager,
    get_project_state_manager,
    reset_state_managers,
)

__all__ = [
    # Signal utils
    'SignalBlocker',
    'SignalBlockerGroup',
    'SignalConnection',
    'ConnectionManager',
    'SafeSignalEmitter',
    'block_signals',
    'block_signals_group',
    # State management
    'LayerStateManager',
    'ProjectStateManager',
    'get_layer_state_manager',
    'get_project_state_manager',
    'reset_state_managers',
]

"""
FilterMate Infrastructure Module.

Cross-cutting concerns: configuration, caching, logging, utilities.
Resilience patterns: Circuit breaker, connection pooling.
"""

# Signal management utilities
from .signal_utils import (
    SignalBlocker,
    SignalBlockerGroup,
    SignalConnection,
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

# Resilience patterns (v4.0.4 - restored from before_migration)
from .resilience import (
    CircuitBreaker,
    CircuitBreakerRegistry,
    CircuitBreakerStats,
    CircuitOpenError,
    CircuitState,
    circuit_breakers,
    circuit_protected,
    get_postgresql_breaker,
    get_spatialite_breaker,
)

__all__ = [
    # Signal utils
    'SignalBlocker',
    'SignalBlockerGroup',
    'SignalConnection',
    'SafeSignalEmitter',
    'block_signals',
    'block_signals_group',
    # State management
    'LayerStateManager',
    'ProjectStateManager',
    'get_layer_state_manager',
    'get_project_state_manager',
    'reset_state_managers',
    # Resilience patterns
    'CircuitBreaker',
    'CircuitBreakerRegistry',
    'CircuitBreakerStats',
    'CircuitOpenError',
    'CircuitState',
    'circuit_breakers',
    'circuit_protected',
    'get_postgresql_breaker',
    'get_spatialite_breaker',
]

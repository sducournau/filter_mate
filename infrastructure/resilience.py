# -*- coding: utf-8 -*-
"""
Resilience infrastructure module.

Re-exports circuit breaker components from modules for infrastructure layer access.

STABILITY v2.6.0: Circuit breaker for PostgreSQL connection protection.
"""

from ..infrastructure.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    get_postgresql_breaker,
    get_spatialite_breaker,
)

__all__ = [
    'CircuitBreaker',
    'CircuitOpenError', 
    'CircuitState',
    'get_postgresql_breaker',
    'get_spatialite_breaker',
]

# -*- coding: utf-8 -*-
"""
Resilience infrastructure module.

Circuit breaker pattern implementation for PostgreSQL connection protection.

STABILITY v2.6.0: Circuit breaker for PostgreSQL connection protection.
"""

import time
import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing if recovered


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """
    Circuit breaker to protect against repeated failures.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, blocking requests
    - HALF_OPEN: Testing if service recovered
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        name: str = "CircuitBreaker"
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds to wait before attempting recovery (OPEN -> HALF_OPEN)
            name: Name for logging
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.name = name
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
    
    @property
    def state(self) -> CircuitState:
        """Get current state, auto-transitioning if timeout expired."""
        if self._state == CircuitState.OPEN:
            if self._last_failure_time and (time.time() - self._last_failure_time) >= self.timeout:
                logger.info(f"{self.name}: Timeout expired, transitioning OPEN -> HALF_OPEN")
                self._state = CircuitState.HALF_OPEN
        return self._state
    
    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        return self.state == CircuitState.OPEN
    
    def record_success(self) -> None:
        """Record successful operation."""
        if self._state == CircuitState.HALF_OPEN:
            logger.info(f"{self.name}: Success in HALF_OPEN, transitioning -> CLOSED")
            self._state = CircuitState.CLOSED
        
        self._failure_count = 0
        self._last_failure_time = None
    
    def record_failure(self) -> None:
        """Record failed operation."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._state == CircuitState.HALF_OPEN:
            logger.warning(f"{self.name}: Failure in HALF_OPEN, transitioning -> OPEN")
            self._state = CircuitState.OPEN
        elif self._failure_count >= self.failure_threshold:
            logger.warning(
                f"{self.name}: Failure threshold reached ({self._failure_count}/{self.failure_threshold}), "
                f"transitioning CLOSED -> OPEN"
            )
            self._state = CircuitState.OPEN
    
    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state."""
        logger.info(f"{self.name}: Manual reset -> CLOSED")
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None


# Global circuit breakers
_postgresql_breaker: Optional[CircuitBreaker] = None
_spatialite_breaker: Optional[CircuitBreaker] = None


def get_postgresql_breaker() -> CircuitBreaker:
    """Get or create PostgreSQL circuit breaker."""
    global _postgresql_breaker
    if _postgresql_breaker is None:
        _postgresql_breaker = CircuitBreaker(
            failure_threshold=5,
            timeout=60.0,
            name="PostgreSQL"
        )
    return _postgresql_breaker


def get_spatialite_breaker() -> CircuitBreaker:
    """Get or create Spatialite circuit breaker."""
    global _spatialite_breaker
    if _spatialite_breaker is None:
        _spatialite_breaker = CircuitBreaker(
            failure_threshold=3,
            timeout=30.0,
            name="Spatialite"
        )
    return _spatialite_breaker


__all__ = [
    'CircuitBreaker',
    'CircuitOpenError', 
    'CircuitState',
    'get_postgresql_breaker',
    'get_spatialite_breaker',
]

# -*- coding: utf-8 -*-
"""
Circuit Breaker Pattern for FilterMate

Protects against cascading failures when PostgreSQL or other external
services become unavailable. Implements the circuit breaker pattern
to fail fast and recover gracefully.

Pattern States:
    CLOSED: Normal operation, all calls pass through
    OPEN: Service down, all calls fail immediately (fast fail)
    HALF_OPEN: Testing recovery, limited calls allowed

Performance Benefits:
    - Prevents thread blocking on failed connections
    - Reduces database load during outages
    - Automatic recovery detection

Usage:
    from modules.circuit_breaker import CircuitBreaker, circuit_breakers
    
    # Get or create breaker for a specific service
    breaker = circuit_breakers.get_breaker("postgresql_main")
    
    # Protected call
    try:
        result = breaker.call(my_database_function, arg1, arg2)
    except CircuitOpenError:
        # Handle service unavailable
        pass

Author: FilterMate Team
Version: 2.6.0 (December 2025)
"""

import logging
import threading
import time
from enum import Enum
from typing import Callable, Any, Optional, Dict
from dataclasses import dataclass, field
from functools import wraps

from .logging_config import get_tasks_logger

logger = get_tasks_logger()


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation - all calls pass through
    OPEN = "open"           # Blocking all calls - service is down
    HALF_OPEN = "half_open" # Testing recovery - limited calls allowed


class CircuitOpenError(Exception):
    """Raised when circuit is open and calls are being rejected."""
    
    def __init__(self, breaker_name: str, message: str = None):
        self.breaker_name = breaker_name
        self.message = message or f"Circuit breaker '{breaker_name}' is OPEN - service unavailable"
        super().__init__(self.message)


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0  # Calls rejected due to open circuit
    last_failure_time: float = 0
    last_success_time: float = 0
    state_changes: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_calls == 0:
            return 100.0
        return (self.successful_calls / self.total_calls) * 100


class CircuitBreaker:
    """
    Thread-safe circuit breaker implementation.
    
    Protects external service calls (PostgreSQL, network resources) by:
    1. Tracking consecutive failures
    2. Opening circuit after threshold reached
    3. Periodically testing for recovery
    4. Resuming normal operation after successful recovery
    
    Configuration:
        failure_threshold: Number of failures before opening circuit (default: 5)
        success_threshold: Successes in half-open to close circuit (default: 2)
        recovery_timeout: Seconds before testing recovery (default: 30)
        call_timeout: Max seconds per call (default: 10)
    
    Example:
        >>> breaker = CircuitBreaker("postgres_pool", failure_threshold=3)
        >>> 
        >>> # Will fail fast if service is down
        >>> result = breaker.call(get_db_connection, host, port)
    """
    
    # Default configuration
    DEFAULT_FAILURE_THRESHOLD = 5
    DEFAULT_SUCCESS_THRESHOLD = 2
    DEFAULT_RECOVERY_TIMEOUT = 30.0  # seconds
    DEFAULT_CALL_TIMEOUT = 10.0  # seconds
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = None,
        success_threshold: int = None,
        recovery_timeout: float = None,
        call_timeout: float = None,
        on_state_change: Callable[[str, CircuitState, CircuitState], None] = None
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Unique identifier for this breaker
            failure_threshold: Failures before opening (default: 5)
            success_threshold: Successes in half-open to close (default: 2)
            recovery_timeout: Seconds before testing recovery (default: 30)
            call_timeout: Max seconds per call (default: 10)
            on_state_change: Optional callback(name, old_state, new_state)
        """
        self.name = name
        self.failure_threshold = failure_threshold or self.DEFAULT_FAILURE_THRESHOLD
        self.success_threshold = success_threshold or self.DEFAULT_SUCCESS_THRESHOLD
        self.recovery_timeout = recovery_timeout or self.DEFAULT_RECOVERY_TIMEOUT
        self.call_timeout = call_timeout or self.DEFAULT_CALL_TIMEOUT
        self.on_state_change = on_state_change
        
        # State management (thread-safe)
        self._state = CircuitState.CLOSED
        self._lock = threading.RLock()
        self._last_failure_time = 0.0
        self._half_open_calls = 0  # Track calls in half-open state
        
        # Statistics
        self.stats = CircuitBreakerStats()
        
        logger.info(
            f"✓ CircuitBreaker '{name}' initialized "
            f"(failure_threshold={self.failure_threshold}, "
            f"recovery_timeout={self.recovery_timeout}s)"
        )
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state (thread-safe)."""
        with self._lock:
            return self._state
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking calls)."""
        return self.state == CircuitState.OPEN
    
    def _set_state(self, new_state: CircuitState):
        """
        Set new state with callback notification.
        
        Args:
            new_state: New circuit state
        """
        with self._lock:
            if self._state != new_state:
                old_state = self._state
                self._state = new_state
                self.stats.state_changes += 1
                
                logger.info(
                    f"CircuitBreaker '{self.name}' state change: "
                    f"{old_state.value} → {new_state.value}"
                )
                
                if self.on_state_change:
                    try:
                        self.on_state_change(self.name, old_state, new_state)
                    except Exception as e:
                        logger.warning(f"Error in state change callback: {e}")
    
    def _should_allow_call(self) -> bool:
        """
        Determine if a call should be allowed based on current state.
        
        Returns:
            True if call should proceed, False if should be rejected
        """
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            
            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if time.time() - self._last_failure_time > self.recovery_timeout:
                    self._set_state(CircuitState.HALF_OPEN)
                    self._half_open_calls = 0
                    return True
                return False
            
            if self._state == CircuitState.HALF_OPEN:
                # Allow limited calls in half-open state
                if self._half_open_calls < self.success_threshold:
                    self._half_open_calls += 1
                    return True
                return False
            
            return False
    
    def _on_success(self):
        """Handle successful call."""
        with self._lock:
            self.stats.total_calls += 1
            self.stats.successful_calls += 1
            self.stats.last_success_time = time.time()
            self.stats.consecutive_successes += 1
            self.stats.consecutive_failures = 0
            
            if self._state == CircuitState.HALF_OPEN:
                if self.stats.consecutive_successes >= self.success_threshold:
                    self._set_state(CircuitState.CLOSED)
    
    def _on_failure(self, error: Exception):
        """
        Handle failed call.
        
        Args:
            error: Exception that caused the failure
        """
        with self._lock:
            self.stats.total_calls += 1
            self.stats.failed_calls += 1
            self.stats.last_failure_time = time.time()
            self._last_failure_time = time.time()
            self.stats.consecutive_failures += 1
            self.stats.consecutive_successes = 0
            
            if self._state == CircuitState.HALF_OPEN:
                # Failed during recovery test - reopen circuit
                self._set_state(CircuitState.OPEN)
                logger.warning(
                    f"CircuitBreaker '{self.name}' recovery failed, reopening circuit"
                )
            elif self._state == CircuitState.CLOSED:
                if self.stats.consecutive_failures >= self.failure_threshold:
                    self._set_state(CircuitState.OPEN)
                    logger.error(
                        f"CircuitBreaker '{self.name}' opened after "
                        f"{self.stats.consecutive_failures} consecutive failures"
                    )
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Result of func(*args, **kwargs)
            
        Raises:
            CircuitOpenError: If circuit is open
            Exception: Original exception from func
        """
        if not self._should_allow_call():
            self.stats.rejected_calls += 1
            raise CircuitOpenError(self.name)
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise
    
    def reset(self):
        """
        Manually reset circuit to closed state.
        
        Use when you know the service has recovered.
        """
        with self._lock:
            self._set_state(CircuitState.CLOSED)
            self.stats.consecutive_failures = 0
            self.stats.consecutive_successes = 0
            logger.info(f"CircuitBreaker '{self.name}' manually reset to CLOSED")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current status and statistics.
        
        Returns:
            Dict with state, stats, and configuration
        """
        with self._lock:
            return {
                'name': self.name,
                'state': self._state.value,
                'stats': {
                    'total_calls': self.stats.total_calls,
                    'successful_calls': self.stats.successful_calls,
                    'failed_calls': self.stats.failed_calls,
                    'rejected_calls': self.stats.rejected_calls,
                    'success_rate': self.stats.success_rate,
                    'consecutive_failures': self.stats.consecutive_failures,
                    'state_changes': self.stats.state_changes,
                },
                'config': {
                    'failure_threshold': self.failure_threshold,
                    'success_threshold': self.success_threshold,
                    'recovery_timeout': self.recovery_timeout,
                }
            }


class CircuitBreakerRegistry:
    """
    Thread-safe registry for managing multiple circuit breakers.
    
    Provides centralized access to all circuit breakers in the application.
    
    Usage:
        >>> registry = CircuitBreakerRegistry()
        >>> 
        >>> # Get or create breaker
        >>> pg_breaker = registry.get_breaker("postgresql_main")
        >>> 
        >>> # Get all statuses
        >>> statuses = registry.get_all_statuses()
    """
    
    def __init__(self):
        """Initialize registry."""
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.RLock()
    
    def get_breaker(
        self,
        name: str,
        failure_threshold: int = None,
        recovery_timeout: float = None,
        **kwargs
    ) -> CircuitBreaker:
        """
        Get or create a circuit breaker.
        
        Args:
            name: Unique name for the breaker
            failure_threshold: Optional custom failure threshold
            recovery_timeout: Optional custom recovery timeout
            **kwargs: Additional CircuitBreaker configuration
            
        Returns:
            CircuitBreaker instance
        """
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(
                    name,
                    failure_threshold=failure_threshold,
                    recovery_timeout=recovery_timeout,
                    **kwargs
                )
            return self._breakers[name]
    
    def remove_breaker(self, name: str) -> bool:
        """
        Remove a circuit breaker from registry.
        
        Args:
            name: Name of breaker to remove
            
        Returns:
            True if removed, False if not found
        """
        with self._lock:
            if name in self._breakers:
                del self._breakers[name]
                return True
            return False
    
    def reset_all(self):
        """Reset all circuit breakers to closed state."""
        with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()
            logger.info(f"Reset all {len(self._breakers)} circuit breakers")
    
    def get_all_statuses(self) -> Dict[str, Dict]:
        """
        Get status of all registered circuit breakers.
        
        Returns:
            Dict mapping breaker names to their status dicts
        """
        with self._lock:
            return {
                name: breaker.get_status()
                for name, breaker in self._breakers.items()
            }
    
    def get_open_breakers(self) -> list:
        """
        Get list of currently open circuit breakers.
        
        Returns:
            List of names of open breakers
        """
        with self._lock:
            return [
                name for name, breaker in self._breakers.items()
                if breaker.is_open
            ]


# Global registry instance
circuit_breakers = CircuitBreakerRegistry()


def circuit_protected(breaker_name: str, **breaker_kwargs):
    """
    Decorator to protect a function with a circuit breaker.
    
    Args:
        breaker_name: Name of the circuit breaker to use
        **breaker_kwargs: Configuration for the breaker
        
    Example:
        >>> @circuit_protected("postgresql", failure_threshold=3)
        ... def get_database_connection():
        ...     return psycopg2.connect(...)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            breaker = circuit_breakers.get_breaker(breaker_name, **breaker_kwargs)
            return breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator


# Pre-configured breakers for common services
def get_postgresql_breaker() -> CircuitBreaker:
    """Get circuit breaker for PostgreSQL connections."""
    return circuit_breakers.get_breaker(
        "postgresql_main",
        failure_threshold=5,
        recovery_timeout=30.0,
        success_threshold=2
    )


def get_spatialite_breaker() -> CircuitBreaker:
    """Get circuit breaker for Spatialite operations."""
    return circuit_breakers.get_breaker(
        "spatialite_main",
        failure_threshold=10,  # Higher threshold (local file)
        recovery_timeout=10.0,  # Shorter recovery (local)
        success_threshold=1
    )

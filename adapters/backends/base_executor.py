#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base Executor - Abstract Backend Class
=======================================

Abstract base class for all FilterMate backends.
Eliminates code duplication by providing common infrastructure:
- Connection management (open, close, reconnect)
- Error handling patterns
- Cleanup operations
- Logging standardization
- Metrics tracking

All backends (PostgreSQL, Spatialite, OGR) inherit from this class.

Architecture:
    BaseExecutor (abstract)
    ├── PostgreSQLBackend
    ├── SpatialiteBackend
    └── OGRBackend
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class BaseExecutor(ABC):
    """
    Abstract base class for all backend executors.

    Provides common functionality for connection management,
    error handling, cleanup, and metrics tracking.

    Subclasses must implement:
    - _connect(): Establish backend-specific connection
    - _disconnect(): Close connection
    - _test_connection_impl(): Test if connection is alive
    - execute_filter(): Apply filter to layer
    - cleanup_resources(): Remove temporary resources
    """

    def __init__(self, backend_name: str, connection_params: Optional[Dict[str, Any]] = None):
        """
        Initialize base executor.

        Args:
            backend_name: Name of backend (postgresql, spatialite, ogr)
            connection_params: Backend-specific connection parameters
        """
        self._backend_name = backend_name.capitalize()
        self._connection_params = connection_params or {}
        self._connection = None
        self._is_connected = False

        # Metrics tracking
        self._metrics = {
            'executions': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'total_time_ms': 0.0,
            'errors': 0,
            'cleanups': 0
        }

        logger.debug(f"[{self._backend_name}] Base Executor Initialized - Params: {list(connection_params.keys()) if connection_params else 'None'}")

    # =========================================================================
    # Connection Management (Template Method Pattern)
    # =========================================================================

    def connect(self) -> bool:
        """
        Establish connection to backend.

        Template method that handles common logic and delegates
        to backend-specific _connect() implementation.

        Returns:
            bool: True if connected successfully
        """
        if self._is_connected:
            logger.debug(f"[{self._backend_name}] Already Connected - Reusing existing connection")
            return True

        try:
            logger.debug(f"[{self._backend_name}] Connecting - Params: {self._get_connection_summary()}")
            self._connection = self._connect()
            self._is_connected = True
            logger.debug(f"[{self._backend_name}] Connection Established Successfully")
            return True

        except Exception as e:
            self._metrics['errors'] += 1
            logger.error(f"[{self._backend_name}] Connection Failed - {type(e).__name__}: {str(e)}", exc_info=True)
            self._is_connected = False
            return False

    @abstractmethod
    def _connect(self) -> Any:
        """
        Backend-specific connection logic.

        Must be implemented by subclasses.

        Returns:
            Connection object (psycopg2.connection, sqlite3.Connection, etc.)
        """

    def disconnect(self) -> bool:
        """
        Close connection to backend.

        Template method for connection cleanup.

        Returns:
            bool: True if disconnected successfully
        """
        if not self._is_connected:
            logger.debug(f"[{self._backend_name}] Already Disconnected - No action needed")
            return True

        try:
            logger.debug(f"[{self._backend_name}] Disconnecting - Closing connection")
            self._disconnect()
            self._connection = None
            self._is_connected = False
            logger.debug(f"[{self._backend_name}] Disconnected Successfully")
            return True

        except Exception as e:
            self._metrics['errors'] += 1
            logger.error(f"[{self._backend_name}] Disconnect Failed - {type(e).__name__}: {str(e)}", exc_info=True)
            return False

    @abstractmethod
    def _disconnect(self):
        """
        Backend-specific disconnection logic.

        Must be implemented by subclasses.
        """

    def reconnect(self) -> bool:
        """
        Reconnect to backend (disconnect + connect).

        Useful for recovering from connection errors.

        Returns:
            bool: True if reconnected successfully
        """
        logger.debug(f"[{self._backend_name}] Reconnecting - Closing and reopening connection")
        self.disconnect()
        return self.connect()

    def test_connection(self) -> bool:
        """
        Test if connection is alive.

        Returns:
            bool: True if connection is alive
        """
        if not self._is_connected:
            return False

        try:
            result = self._test_connection_impl()
            if not result:
                logger.warning(f"[{self._backend_name}] Connection Test Failed - Connection may be stale")
            return result

        except Exception as e:
            logger.error(f"[{self._backend_name}] Connection Test Error - {type(e).__name__}: {str(e)}")
            return False

    @abstractmethod
    def _test_connection_impl(self) -> bool:
        """
        Backend-specific connection test.

        Must be implemented by subclasses.

        Returns:
            bool: True if connection is alive
        """

    def _get_connection_summary(self) -> str:
        """
        Get human-readable connection summary.

        Returns:
            str: Connection parameters summary
        """
        if 'dbname' in self._connection_params:
            return Path(self._connection_params['dbname']).name
        elif 'database' in self._connection_params:
            return self._connection_params['database']
        elif 'host' in self._connection_params:
            return f"{self._connection_params.get('host')}:{self._connection_params.get('port', '?')}"
        else:
            return "In-memory"

    # =========================================================================
    # Error Handling (Decorator Pattern)
    # =========================================================================

    def handle_errors(self, operation: str):
        """
        Decorator for standardized error handling.

        Usage:
            @executor.handle_errors("filter execution")
            def execute_filter(self, ...):
                ...

        Args:
            operation: Human-readable operation name
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    self._metrics['errors'] += 1
                    logger.error(
                        f"[{self._backend_name}] {operation} Failed - "
                        f"{type(e).__name__}: {str(e)}",
                        exc_info=True
                    )
                    return None, f"Error during {operation}: {str(e)}"
            return wrapper
        return decorator

    # =========================================================================
    # Abstract Methods (Must be implemented by subclasses)
    # =========================================================================

    @abstractmethod
    def execute_filter(self, layer, expression: str, **kwargs) -> Tuple[bool, str]:
        """
        Execute filter on layer.

        Must be implemented by subclasses.

        Args:
            layer: QgsVectorLayer to filter
            expression: Filter expression
            **kwargs: Backend-specific parameters

        Returns:
            Tuple[bool, str]: (success, message)
        """

    @abstractmethod
    def cleanup_resources(self, **kwargs) -> int:
        """
        Cleanup temporary resources (tables, views, files).

        Must be implemented by subclasses.

        Args:
            **kwargs: Backend-specific cleanup parameters

        Returns:
            int: Number of resources cleaned
        """

    # =========================================================================
    # Metrics & Statistics
    # =========================================================================

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get execution metrics.

        Returns:
            dict: Copy of metrics dictionary
        """
        return self._metrics.copy()

    def reset_metrics(self):
        """Reset all metrics to zero."""
        for key in self._metrics:
            if isinstance(self._metrics[key], (int, float)):
                self._metrics[key] = 0
        logger.debug(f"[{self._backend_name}] Metrics Reset - All counters zeroed")

    def increment_metric(self, metric_name: str, value: float = 1.0):
        """
        Increment a metric.

        Args:
            metric_name: Name of metric
            value: Value to add (default 1.0)
        """
        if metric_name in self._metrics:
            self._metrics[metric_name] += value

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get detailed statistics including derived metrics.

        Returns:
            dict: Statistics with calculations
        """
        metrics = self.get_metrics()

        # Calculate derived metrics
        total_requests = metrics['executions']
        if total_requests > 0:
            metrics['cache_hit_rate'] = (metrics['cache_hits'] / total_requests) * 100
            metrics['average_time_ms'] = metrics['total_time_ms'] / total_requests
            metrics['error_rate'] = (metrics['errors'] / total_requests) * 100
        else:
            metrics['cache_hit_rate'] = 0.0
            metrics['average_time_ms'] = 0.0
            metrics['error_rate'] = 0.0

        metrics['backend'] = self._backend_name
        metrics['connected'] = self._is_connected

        return metrics

    # =========================================================================
    # Context Manager Support
    # =========================================================================

    def __enter__(self):
        """Context manager entry - auto-connect."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - auto-disconnect."""
        self.disconnect()
        return False  # Don't suppress exceptions

    # =========================================================================
    # String Representation
    # =========================================================================

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<{self.__class__.__name__} "
            f"backend={self._backend_name} "
            f"connected={self._is_connected} "
            f"executions={self._metrics['executions']}>"
        )

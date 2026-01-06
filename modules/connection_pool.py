# -*- coding: utf-8 -*-
"""
PostgreSQL Connection Pool for FilterMate

Provides efficient connection pooling to avoid the overhead of opening/closing
connections for each operation. Significantly improves performance for:
- Layer loading (multiple metadata queries per layer)
- Batch filtering operations
- Spatial index creation

Performance Benefits:
- Connection reuse: ~50-100ms saved per query (connection overhead)
- Reduced database load: fewer connection slots used
- Thread-safe: one pool per datasource URI

Usage:
    from modules.connection_pool import PostgreSQLConnectionPool, get_pool_manager
    
    # Get the global pool manager
    pool_manager = get_pool_manager()
    
    # Get a connection from pool (auto-creates pool if needed)
    conn = pool_manager.get_connection(host, port, dbname, username, password)
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT ...")
        # ... use connection
    finally:
        # Return connection to pool (don't close!)
        pool_manager.release_connection(conn, host, port, dbname)
    
    # Or use context manager:
    with pool_manager.connection(host, port, dbname, username, password) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ...")
"""

import logging
import threading
import time
import os
import atexit
from typing import Dict, Optional, Tuple, Any, Generator
from contextlib import contextmanager
from collections import OrderedDict
from queue import Queue, Empty
from dataclasses import dataclass, field

# Import logging configuration
from .logging_config import setup_logger
from ..config.config import ENV_VARS

# Setup logger
logger = setup_logger(
    'FilterMate.ConnectionPool',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_pool.log'),
    level=logging.INFO
)

# Centralized psycopg2 availability (v2.8.6 refactoring)
from .psycopg2_availability import psycopg2, PSYCOPG2_AVAILABLE, POSTGRESQL_AVAILABLE

# Import psycopg2.pool if available (needed for connection pooling)
if PSYCOPG2_AVAILABLE:
    from psycopg2 import pool as psycopg2_pool
else:
    psycopg2_pool = None


@dataclass
class PoolStats:
    """Statistics for a connection pool."""
    total_connections_created: int = 0
    total_connections_reused: int = 0
    current_pool_size: int = 0
    peak_pool_size: int = 0
    total_wait_time_ms: float = 0.0
    cache_hit_rate: float = 0.0
    
    def update_hit_rate(self):
        """Update the cache hit rate."""
        total = self.total_connections_created + self.total_connections_reused
        if total > 0:
            self.cache_hit_rate = self.total_connections_reused / total


class PostgreSQLConnectionPool:
    """
    Thread-safe connection pool for a single PostgreSQL database.
    
    This pool manages a set of reusable connections to avoid the
    ~50-100ms overhead of establishing new connections.
    
    PERFORMANCE IMPROVEMENTS (v2.6.0):
    - Increased max connections from 10 to 15
    - Reduced idle timeout from 300s to 180s
    - Added periodic health check thread
    - Integrated with circuit breaker for failure protection
    
    Features:
    - Thread-safe connection management
    - Automatic connection health checking
    - Periodic background health checks
    - Configurable pool size (min/max connections)
    - Connection timeout handling
    - Statistics tracking for monitoring
    - Circuit breaker integration
    
    Configuration:
    - min_connections: Minimum connections to keep open (default: 2)
    - max_connections: Maximum connections allowed (default: 15)
    - connection_timeout: Seconds to wait for available connection (default: 30)
    - idle_timeout: Seconds before closing idle connections (default: 180)
    - health_check_interval: Seconds between health checks (default: 60)
    """
    
    # Default configuration - OPTIMIZED v2.6.0
    DEFAULT_MIN_CONNECTIONS = 2
    DEFAULT_MAX_CONNECTIONS = 15    # Increased from 10 for better parallelism
    DEFAULT_CONNECTION_TIMEOUT = 30  # seconds
    DEFAULT_IDLE_TIMEOUT = 180       # Reduced from 300 for faster cleanup
    DEFAULT_HEALTH_CHECK_INTERVAL = 60  # New: periodic health check
    
    def __init__(
        self,
        host: str,
        port: str,
        database: str,
        user: str,
        password: str,
        min_connections: int = None,
        max_connections: int = None,
        sslmode: str = None,
        enable_health_check: bool = True
    ):
        """
        Initialize PostgreSQL connection pool.
        
        Args:
            host: Database host
            port: Database port
            database: Database name
            user: Username
            password: Password
            min_connections: Minimum pool size (default: 2)
            max_connections: Maximum pool size (default: 15)
            sslmode: SSL mode (optional)
            enable_health_check: Enable periodic health check (default: True)
        """
        if not POSTGRESQL_AVAILABLE:
            raise RuntimeError("psycopg2 not available - cannot create connection pool")
        
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.sslmode = sslmode
        
        self.min_connections = min_connections or self.DEFAULT_MIN_CONNECTIONS
        self.max_connections = max_connections or self.DEFAULT_MAX_CONNECTIONS
        
        # Connection pool (queue for thread-safety)
        self._pool: Queue = Queue(maxsize=self.max_connections)
        self._active_connections: int = 0
        self._lock = threading.RLock()
        
        # Connection tracking for health checks
        self._connection_timestamps: Dict[int, float] = {}
        
        # Health check thread management
        self._health_check_enabled = enable_health_check
        self._health_check_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        
        # Statistics
        self.stats = PoolStats()
        
        # Pool key for identification
        self._pool_key = f"{host}:{port}/{database}"
        
        logger.info(f"✓ PostgreSQL connection pool created for {self._pool_key} "
                   f"(min={self.min_connections}, max={self.max_connections})")
        
        # Pre-create minimum connections
        self._initialize_pool()
        
        # Start health check thread if enabled
        if self._health_check_enabled:
            self._start_health_check_thread()
    
    def _start_health_check_thread(self):
        """Start background thread for periodic health checks.
        
        CRASH FIX (v2.8.6): Added additional safety checks to detect QGIS shutdown
        and prevent the thread from causing access violations when QGIS exits.
        """
        def health_check_loop():
            while not self._shutdown_event.is_set():
                # CRASH FIX (v2.8.6): Check if QGIS is still alive before any operation
                # This prevents access violations when QGIS is shutting down
                try:
                    from qgis.PyQt.QtWidgets import QApplication
                    if QApplication.instance() is None:
                        logger.debug("QApplication gone, stopping health check thread")
                        break
                except Exception:
                    # If we can't check QGIS state, assume it's shutting down
                    break
                
                try:
                    self._perform_health_check()
                except Exception as e:
                    logger.debug(f"Health check error: {e}")
                
                # Wait for interval or shutdown
                self._shutdown_event.wait(self.DEFAULT_HEALTH_CHECK_INTERVAL)
        
        self._health_check_thread = threading.Thread(
            target=health_check_loop,
            name=f"PoolHealthCheck-{self._pool_key}",
            daemon=True
        )
        self._health_check_thread.start()
        logger.debug(f"Health check thread started for {self._pool_key}")
    
    def _perform_health_check(self):
        """
        Perform health check on pooled connections.
        
        - Removes unhealthy connections
        - Closes idle connections beyond timeout
        - Ensures minimum connections are maintained
        """
        removed_count = 0
        
        # Get all connections from pool
        connections_to_check = []
        while True:
            try:
                conn = self._pool.get_nowait()
                connections_to_check.append(conn)
            except Empty:
                break
        
        # Check each connection
        for conn in connections_to_check:
            should_keep = True
            
            # Check health
            if not self._is_connection_healthy(conn):
                should_keep = False
                removed_count += 1
            # Check idle timeout
            elif self._is_connection_idle_too_long(conn):
                with self._lock:
                    if self._active_connections > self.min_connections:
                        should_keep = False
                        removed_count += 1
            
            if should_keep:
                try:
                    self._pool.put_nowait(conn)
                    self._connection_timestamps[id(conn)] = time.time()
                except queue.Full:
                    self._close_connection(conn)  # Pool is full
            else:
                self._close_connection(conn)
        
        if removed_count > 0:
            logger.debug(f"Health check: removed {removed_count} connections from {self._pool_key}")
        
        # Ensure minimum connections
        with self._lock:
            while self._active_connections < self.min_connections:
                try:
                    conn = self._create_connection()
                    if conn:
                        self._pool.put(conn)
                        self.stats.current_pool_size += 1
                except Exception:
                    break
    
    def shutdown(self):
        """
        Gracefully shutdown the pool.
        
        Stops health check thread and closes all connections.
        """
        logger.info(f"Shutting down connection pool {self._pool_key}")
        
        # Stop health check thread
        self._shutdown_event.set()
        if self._health_check_thread and self._health_check_thread.is_alive():
            self._health_check_thread.join(timeout=5)
        
        # Close all connections
        while True:
            try:
                conn = self._pool.get_nowait()
                self._close_connection(conn)
            except Empty:
                break
        
        logger.info(f"Connection pool {self._pool_key} shut down")
    
    def _initialize_pool(self):
        """Pre-create minimum number of connections."""
        for _ in range(self.min_connections):
            try:
                conn = self._create_connection()
                if conn:
                    self._pool.put(conn)
                    self.stats.current_pool_size += 1
            except Exception as e:
                logger.warning(f"Failed to pre-create connection: {e}")
    
    # Statement timeout in seconds for PostgreSQL queries
    # Prevents queries from blocking indefinitely (e.g., complex ST_Intersects on large datasets)
    # Default: 300 seconds (5 minutes) - long enough for complex queries on large tables like batiment
    DEFAULT_STATEMENT_TIMEOUT = 300
    
    def _create_connection(self):
        """
        Create a new database connection.
        
        Configures statement_timeout to prevent queries from blocking indefinitely.
        This is critical for FilterMate because complex spatial queries (EXISTS with
        ST_Intersects on large datasets) can take very long and block the task thread.
        
        Returns:
            psycopg2 connection or None on failure
        """
        try:
            connect_kwargs = {
                'host': self.host,
                'port': self.port,
                'database': self.database,
                'user': self.user,
                'password': self.password,
            }
            
            # Remove empty values
            connect_kwargs = {k: v for k, v in connect_kwargs.items() if v}
            
            if self.sslmode:
                connect_kwargs['sslmode'] = self.sslmode
            
            conn = psycopg2.connect(**connect_kwargs)
            
            # CRITICAL FIX v2.5.18: Set statement_timeout to prevent blocking queries
            # This prevents complex spatial queries from hanging indefinitely and
            # causing QGIS to appear unresponsive. If timeout is reached, query
            # is cancelled and fallback to OGR backend can be attempted.
            try:
                with conn.cursor() as cursor:
                    timeout_ms = self.DEFAULT_STATEMENT_TIMEOUT * 1000
                    cursor.execute(f"SET statement_timeout = {timeout_ms}")
                    conn.commit()
                logger.debug(f"Set statement_timeout={self.DEFAULT_STATEMENT_TIMEOUT}s for {self._pool_key}")
            except Exception as timeout_err:
                logger.warning(f"Could not set statement_timeout: {timeout_err}")
            
            # Track creation time for idle timeout
            self._connection_timestamps[id(conn)] = time.time()
            
            with self._lock:
                self._active_connections += 1
                self.stats.total_connections_created += 1
                self.stats.peak_pool_size = max(
                    self.stats.peak_pool_size, 
                    self._active_connections
                )
            
            logger.debug(f"Created new connection to {self._pool_key} "
                        f"(active: {self._active_connections})")
            
            return conn
            
        except Exception as e:
            logger.error(f"Failed to create connection to {self._pool_key}: {e}")
            return None
    
    def _is_connection_healthy(self, conn) -> bool:
        """
        Check if a connection is still valid and usable.
        
        Args:
            conn: psycopg2 connection
        
        Returns:
            True if connection is healthy
        """
        try:
            # Check connection status
            if conn.closed:
                return False
            
            # Quick ping test
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            return True
            
        except Exception:
            return False
    
    def _is_connection_idle_too_long(self, conn) -> bool:
        """Check if connection has been idle beyond timeout."""
        conn_id = id(conn)
        if conn_id in self._connection_timestamps:
            idle_time = time.time() - self._connection_timestamps[conn_id]
            return idle_time > self.DEFAULT_IDLE_TIMEOUT
        return False
    
    def get_connection(self, timeout: float = None):
        """
        Get a connection from the pool.
        
        If no connection is available and pool isn't at max capacity,
        creates a new connection. Otherwise waits for available connection.
        
        Args:
            timeout: Seconds to wait for available connection
        
        Returns:
            psycopg2 connection
        
        Raises:
            TimeoutError: If no connection available within timeout
        """
        timeout = timeout or self.DEFAULT_CONNECTION_TIMEOUT
        start_time = time.time()
        
        while True:
            # Try to get from pool first
            try:
                conn = self._pool.get_nowait()
                
                # Check connection health
                if self._is_connection_healthy(conn):
                    # Update timestamp and return
                    self._connection_timestamps[id(conn)] = time.time()
                    self.stats.total_connections_reused += 1
                    self.stats.update_hit_rate()
                    logger.debug(f"Reusing connection from pool {self._pool_key}")
                    return conn
                else:
                    # Connection is bad, close it and try again
                    self._close_connection(conn)
                    continue
                    
            except Empty:
                pass
            
            # No connection in pool, try to create new one
            with self._lock:
                if self._active_connections < self.max_connections:
                    conn = self._create_connection()
                    if conn:
                        return conn
            
            # Pool is at max capacity, wait for release
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                raise TimeoutError(
                    f"Timeout waiting for connection to {self._pool_key} "
                    f"(waited {elapsed:.1f}s, pool size: {self._active_connections})"
                )
            
            # Wait a bit before retrying
            wait_time = min(0.1, timeout - elapsed)
            time.sleep(wait_time)
            self.stats.total_wait_time_ms += wait_time * 1000
    
    def release_connection(self, conn):
        """
        Return a connection to the pool.
        
        Connection will be reused if healthy, otherwise closed.
        
        Args:
            conn: psycopg2 connection to release
        """
        if conn is None:
            return
        
        try:
            # Check if connection is still usable
            if conn.closed:
                with self._lock:
                    self._active_connections -= 1
                return
            
            # Rollback any uncommitted transaction
            try:
                conn.rollback()
            except Exception:
                pass
            
            # Check health and idle time
            if self._is_connection_healthy(conn) and not self._is_connection_idle_too_long(conn):
                # Return to pool
                try:
                    self._pool.put_nowait(conn)
                    self._connection_timestamps[id(conn)] = time.time()
                    logger.debug(f"Connection returned to pool {self._pool_key}")
                    return
                except Exception:
                    # Pool is full, close the connection
                    pass
            
            # Close the connection
            self._close_connection(conn)
            
        except Exception as e:
            logger.warning(f"Error releasing connection: {e}")
            self._close_connection(conn)
    
    def _close_connection(self, conn):
        """Close a connection and update counters."""
        try:
            if conn and not conn.closed:
                conn.close()
            
            # Remove from tracking
            conn_id = id(conn)
            self._connection_timestamps.pop(conn_id, None)
            
            with self._lock:
                self._active_connections = max(0, self._active_connections - 1)
                self.stats.current_pool_size = max(0, self.stats.current_pool_size - 1)
                
        except Exception as e:
            logger.debug(f"Error closing connection: {e}")
    
    @contextmanager
    def connection(self, timeout: float = None):
        """
        Context manager for getting a pooled connection.
        
        Usage:
            with pool.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT ...")
        
        Args:
            timeout: Connection timeout in seconds
        
        Yields:
            psycopg2 connection
        """
        conn = None
        try:
            conn = self.get_connection(timeout)
            yield conn
        finally:
            if conn:
                self.release_connection(conn)
    
    def close_all(self):
        """Close all connections in the pool."""
        logger.info(f"Closing connection pool for {self._pool_key}")
        
        # Close all pooled connections
        while True:
            try:
                conn = self._pool.get_nowait()
                self._close_connection(conn)
            except Empty:
                break
        
        self._connection_timestamps.clear()
        
        with self._lock:
            self._active_connections = 0
            self.stats.current_pool_size = 0
        
        logger.info(f"✓ Connection pool closed for {self._pool_key}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        self.stats.update_hit_rate()
        return {
            'pool_key': self._pool_key,
            'active_connections': self._active_connections,
            'pooled_connections': self._pool.qsize(),
            'total_created': self.stats.total_connections_created,
            'total_reused': self.stats.total_connections_reused,
            'hit_rate': f"{self.stats.cache_hit_rate:.1%}",
            'peak_size': self.stats.peak_pool_size,
            'avg_wait_ms': self.stats.total_wait_time_ms / max(1, self.stats.total_connections_reused)
        }


class PostgreSQLPoolManager:
    """
    Global manager for PostgreSQL connection pools.
    
    Maintains one pool per unique database connection (host:port/database).
    Thread-safe singleton pattern ensures pools are shared across the application.
    
    Usage:
        manager = get_pool_manager()
        
        # Get connection using layer
        with manager.connection_from_layer(layer) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ...")
        
        # Or with explicit parameters
        with manager.connection(host, port, db, user, pwd) as conn:
            ...
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize pool manager (only once)."""
        if self._initialized:
            return
        
        self._pools: Dict[str, PostgreSQLConnectionPool] = {}
        self._pools_lock = threading.RLock()
        self._initialized = True
        
        logger.info("✓ PostgreSQL Pool Manager initialized")
    
    def _get_pool_key(self, host: str, port: str, database: str) -> str:
        """Generate unique key for pool identification."""
        return f"{host}:{port}/{database}"
    
    def get_pool(
        self,
        host: str,
        port: str,
        database: str,
        user: str = None,
        password: str = None,
        sslmode: str = None
    ) -> PostgreSQLConnectionPool:
        """
        Get or create a connection pool for the specified database.
        
        Args:
            host: Database host
            port: Database port
            database: Database name
            user: Username (required for new pools)
            password: Password (required for new pools)
            sslmode: SSL mode (optional)
        
        Returns:
            PostgreSQLConnectionPool instance
        """
        pool_key = self._get_pool_key(host, port, database)
        
        with self._pools_lock:
            if pool_key not in self._pools:
                if user is None:
                    raise ValueError(f"Credentials required to create new pool for {pool_key}")
                
                self._pools[pool_key] = PostgreSQLConnectionPool(
                    host=host,
                    port=port,
                    database=database,
                    user=user,
                    password=password,
                    sslmode=sslmode
                )
            
            return self._pools[pool_key]
    
    def get_connection(
        self,
        host: str,
        port: str,
        database: str,
        user: str = None,
        password: str = None,
        sslmode: str = None,
        timeout: float = None
    ):
        """
        Get a connection from the appropriate pool.
        
        Args:
            host, port, database, user, password: Connection parameters
            sslmode: SSL mode
            timeout: Connection timeout
        
        Returns:
            psycopg2 connection
        """
        pool = self.get_pool(host, port, database, user, password, sslmode)
        return pool.get_connection(timeout)
    
    def release_connection(self, conn, host: str, port: str, database: str):
        """
        Release a connection back to its pool.
        
        Args:
            conn: Connection to release
            host, port, database: Pool identification
        """
        pool_key = self._get_pool_key(host, port, database)
        
        with self._pools_lock:
            if pool_key in self._pools:
                self._pools[pool_key].release_connection(conn)
            else:
                # No pool found, just close the connection
                try:
                    if conn and not conn.closed:
                        conn.close()
                except Exception:
                    pass
    
    @contextmanager
    def connection(
        self,
        host: str,
        port: str,
        database: str,
        user: str = None,
        password: str = None,
        sslmode: str = None,
        timeout: float = None
    ):
        """
        Context manager for getting a pooled connection.
        
        Usage:
            with manager.connection(host, port, db, user, pwd) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT ...")
        """
        pool = self.get_pool(host, port, database, user, password, sslmode)
        with pool.connection(timeout) as conn:
            yield conn
    
    @contextmanager
    def connection_from_uri(self, source_uri, timeout: float = None):
        """
        Context manager for connection using QgsDataSourceUri.
        
        Args:
            source_uri: QgsDataSourceUri from layer
            timeout: Connection timeout
        
        Yields:
            psycopg2 connection
        """
        from qgis.core import QgsApplication, QgsAuthMethodConfig
        
        host = source_uri.host()
        port = source_uri.port()
        database = source_uri.database()
        user = source_uri.username()
        password = source_uri.password()
        ssl_mode = source_uri.sslMode()
        
        # Handle authcfg authentication
        authcfg_id = source_uri.param('authcfg')
        if authcfg_id:
            auth_config = QgsAuthMethodConfig()
            if authcfg_id in QgsApplication.authManager().configIds():
                QgsApplication.authManager().loadAuthenticationConfig(authcfg_id, auth_config, True)
                user = auth_config.config("username")
                password = auth_config.config("password")
        
        sslmode = None
        if ssl_mode is not None:
            sslmode = source_uri.encodeSslMode(ssl_mode)
        
        with self.connection(host, port, database, user, password, sslmode, timeout) as conn:
            yield conn
    
    def close_pool(self, host: str, port: str, database: str):
        """Close a specific connection pool."""
        pool_key = self._get_pool_key(host, port, database)
        
        with self._pools_lock:
            if pool_key in self._pools:
                self._pools[pool_key].close_all()
                del self._pools[pool_key]
                logger.info(f"Closed pool: {pool_key}")
    
    def close_all_pools(self):
        """Close all connection pools (call on plugin unload)."""
        with self._pools_lock:
            for pool_key, pool in list(self._pools.items()):
                try:
                    pool.close_all()
                except Exception as e:
                    logger.warning(f"Error closing pool {pool_key}: {e}")
            
            self._pools.clear()
            logger.info("✓ All connection pools closed")
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """Get statistics for all pools."""
        with self._pools_lock:
            return {
                pool_key: pool.get_stats()
                for pool_key, pool in self._pools.items()
            }
    
    def log_stats(self):
        """Log statistics for all pools."""
        stats = self.get_all_stats()
        if stats:
            logger.info("=== Connection Pool Statistics ===")
            for pool_key, pool_stats in stats.items():
                logger.info(
                    f"  {pool_key}: "
                    f"active={pool_stats['active_connections']}, "
                    f"pooled={pool_stats['pooled_connections']}, "
                    f"reused={pool_stats['total_reused']}, "
                    f"hit_rate={pool_stats['hit_rate']}"
                )


# Global pool manager instance
_pool_manager: Optional[PostgreSQLPoolManager] = None


def get_pool_manager() -> PostgreSQLPoolManager:
    """
    Get the global PostgreSQL pool manager.
    
    Returns:
        PostgreSQLPoolManager singleton instance
    """
    global _pool_manager
    
    if not POSTGRESQL_AVAILABLE:
        raise RuntimeError("psycopg2 not available - connection pooling disabled")
    
    if _pool_manager is None:
        _pool_manager = PostgreSQLPoolManager()
    
    return _pool_manager


def get_pooled_connection_from_layer(layer):
    """
    Get a pooled connection for a PostgreSQL layer.
    
    This is a drop-in replacement for get_datasource_connexion_from_layer()
    that uses connection pooling for better performance.
    
    Args:
        layer: QgsVectorLayer (must be PostgreSQL provider)
    
    Returns:
        tuple: (connection, source_uri) or (None, None) if not PostgreSQL
    
    Usage:
        conn, uri = get_pooled_connection_from_layer(layer)
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT ...")
            finally:
                # IMPORTANT: Release back to pool!
                release_pooled_connection(conn, uri)
    """
    if not POSTGRESQL_AVAILABLE:
        return None, None
    
    if layer.providerType() != 'postgres':
        return None, None
    
    from qgis.core import QgsDataSourceUri, QgsApplication, QgsAuthMethodConfig
    
    source_uri = QgsDataSourceUri(layer.source())
    
    host = source_uri.host()
    port = source_uri.port()
    database = source_uri.database()
    user = source_uri.username()
    password = source_uri.password()
    ssl_mode = source_uri.sslMode()
    
    # Handle authcfg
    authcfg_id = source_uri.param('authcfg')
    if authcfg_id:
        auth_config = QgsAuthMethodConfig()
        if authcfg_id in QgsApplication.authManager().configIds():
            QgsApplication.authManager().loadAuthenticationConfig(authcfg_id, auth_config, True)
            user = auth_config.config("username")
            password = auth_config.config("password")
    
    sslmode = None
    if ssl_mode is not None:
        sslmode = source_uri.encodeSslMode(ssl_mode)
    
    try:
        manager = get_pool_manager()
        conn = manager.get_connection(host, port, database, user, password, sslmode)
        return conn, source_uri
    except Exception as e:
        logger.error(f"Failed to get pooled connection for {layer.name()}: {e}")
        return None, None


def release_pooled_connection(conn, source_uri):
    """
    Release a pooled connection back to the pool.
    
    CRITICAL: Always call this after using a pooled connection!
    
    Args:
        conn: psycopg2 connection from get_pooled_connection_from_layer()
        source_uri: QgsDataSourceUri from get_pooled_connection_from_layer()
    """
    if conn is None or source_uri is None:
        return
    
    try:
        manager = get_pool_manager()
        manager.release_connection(
            conn,
            source_uri.host(),
            source_uri.port(),
            source_uri.database()
        )
    except Exception as e:
        logger.warning(f"Error releasing pooled connection: {e}")
        # Fallback: just close the connection
        try:
            if conn and not conn.closed:
                conn.close()
        except Exception:
            pass


@contextmanager
def pooled_connection_from_layer(layer, timeout: float = None):
    """
    Context manager for getting a pooled connection from a layer.
    
    This is the recommended way to use pooled connections as it
    automatically handles release back to the pool.
    
    Args:
        layer: QgsVectorLayer (PostgreSQL)
        timeout: Connection timeout in seconds
    
    Yields:
        tuple: (connection, source_uri) or (None, None)
    
    Usage:
        with pooled_connection_from_layer(layer) as (conn, uri):
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT ...")
    """
    conn = None
    source_uri = None
    
    try:
        conn, source_uri = get_pooled_connection_from_layer(layer)
        yield conn, source_uri
    finally:
        if conn and source_uri:
            release_pooled_connection(conn, source_uri)


def cleanup_pools():
    """
    Clean up all connection pools.
    
    Call this when the plugin is unloaded to properly close all connections.
    """
    global _pool_manager
    
    if _pool_manager is not None:
        _pool_manager.log_stats()
        _pool_manager.close_all_pools()
        _pool_manager = None
        logger.info("✓ Connection pool cleanup complete")


# CRASH FIX (v2.8.6): Register atexit handler to ensure pools are cleaned up
# even if the plugin's unload() is not called (e.g., during QGIS crash or kill)
def _atexit_cleanup():
    """Cleanup handler called when Python interpreter exits."""
    global _pool_manager
    if _pool_manager is not None:
        try:
            _pool_manager.close_all_pools()
            _pool_manager = None
        except Exception:
            pass  # Silently ignore errors during exit


atexit.register(_atexit_cleanup)

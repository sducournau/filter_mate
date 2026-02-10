# -*- coding: utf-8 -*-
"""
Interruptible SQLite Query Module

Provides thread-safe, cancellable SQLite query execution to prevent QGIS freezing
on long-running queries.

Migrated from: before_migration/modules/backends/spatialite_backend.py
Target: adapters/backends/spatialite/interruptible_query.py

v4.1.0 - Hexagonal Architecture Migration (January 2026)

Features:
- Executes SQLite queries in background thread
- Periodic cancellation check via callback
- SQLite interrupt() for immediate query termination
- Timeout support to prevent infinite waits

Usage:
    query = InterruptibleSQLiteQuery(conn, "SELECT * FROM table WHERE ...")
    results, error = query.execute(timeout=60, cancel_check=lambda: task.isCanceled())
"""

import logging
import sqlite3
import threading
import time
from typing import List, Optional, Tuple, Callable, Any

logger = logging.getLogger('FilterMate.Adapters.Backends.Spatialite.InterruptibleQuery')

# Performance and timeout constants for complex geometric filters
# These prevent QGIS freezing on large datasets
SPATIALITE_QUERY_TIMEOUT = 120  # Maximum seconds for SQLite queries
SPATIALITE_BATCH_SIZE = 5000    # Process FIDs in batches to avoid memory issues
SPATIALITE_PROGRESS_INTERVAL = 1000  # Report progress every N features
SPATIALITE_INTERRUPT_CHECK_INTERVAL = 0.5  # Check for cancellation every N seconds

# WKT simplification thresholds to prevent GeomFromText freeze on complex geometries
# GeomFromText parsing complexity is O(n²) for polygon validation
SPATIALITE_WKT_SIMPLIFY_THRESHOLD = 30000  # 30KB - trigger Python simplification
SPATIALITE_WKT_MAX_POINTS = 3000  # Max points before aggressive simplification
SPATIALITE_GEOM_INSERT_TIMEOUT = 30  # Timeout for geometry insertion (seconds)

# Sentinel value to signal that OGR fallback is required
# Used when GeometryCollection cannot be converted and RTTOPO MakeValid would fail
USE_OGR_FALLBACK = "__USE_OGR_FALLBACK__"


class InterruptibleSQLiteQuery:
    """
    Execute SQLite queries in a separate thread with interrupt capability.

    This class solves the QGIS freeze problem by:
    1. Running the query in a background thread
    2. Periodically checking for cancellation
    3. Using SQLite's interrupt() method to stop long-running queries

    Thread Safety:
        Uses SQLite connection with check_same_thread=False to allow
        cross-thread interrupt() calls.

    Example:
        >>> conn = sqlite3.connect(db_path, check_same_thread=False)
        >>> query = InterruptibleSQLiteQuery(conn, "SELECT * FROM big_table WHERE ...")
        >>> results, error = query.execute(
        ...     timeout=60,
        ...     cancel_check=lambda: task.isCanceled()
        ... )
        >>> if error:
        ...     print(f"Query failed: {error}")
        >>> else:
        ...     process_results(results)

    Attributes:
        connection: SQLite connection (should have check_same_thread=False)
        sql: SQL query to execute
        results: List of result rows (populated after execute)
        error: Exception if query failed
        completed: True when query finished (success or error)
    """

    def __init__(self, connection: sqlite3.Connection, sql: str):
        """
        Initialize interruptible query.

        Args:
            connection: SQLite connection (recommend check_same_thread=False)
            sql: SQL query string to execute
        """
        self.connection = connection
        self.sql = sql
        self.results: List[Any] = []
        self.error: Optional[Exception] = None
        self.completed: bool = False
        self._thread: Optional[threading.Thread] = None
        self._start_time: float = 0.0

    def _execute_query(self):
        """Execute the query in background thread."""
        try:
            cursor = self.connection.cursor()
            cursor.execute(self.sql)
            self.results = cursor.fetchall()
            self.completed = True
        except sqlite3.Error as e:
            self.error = e
            self.completed = True

    def execute(
        self,
        timeout: float = SPATIALITE_QUERY_TIMEOUT,
        cancel_check: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Tuple[List, Optional[Exception]]:
        """
        Execute query with timeout and cancellation support.

        This method blocks until:
        1. Query completes successfully
        2. Query fails with an error
        3. Timeout is reached
        4. cancel_check() returns True

        Args:
            timeout: Maximum time in seconds to wait for query (default: 120)
            cancel_check: Callable that returns True if operation should be cancelled
            progress_callback: Optional callback(progress) where progress is 0.0-1.0

        Returns:
            Tuple of (results list, error or None)
            - On success: (results, None)
            - On timeout: ([], Exception("Query timeout..."))
            - On cancel: ([], Exception("Query cancelled..."))
            - On error: ([], original_exception)

        Example:
            >>> results, error = query.execute(
            ...     timeout=60,
            ...     cancel_check=lambda: user_cancelled,
            ...     progress_callback=lambda p: update_ui(p)
            ... )
        """
        self._start_time = time.time()

        # Start query in background thread
        self._thread = threading.Thread(target=self._execute_query, daemon=True)
        self._thread.start()

        logger.debug(f"[InterruptibleQuery] Started query execution (timeout={timeout}s)")

        # Wait for completion with periodic cancellation checks
        while not self.completed:
            elapsed = time.time() - self._start_time

            # Report progress (linear estimate based on timeout)
            if progress_callback:
                progress = min(elapsed / timeout, 0.99)  # Never report 100% until done
                try:
                    progress_callback(progress)
                except Exception:  # catch-all safety net
                    pass  # Ignore callback errors

            # Check timeout
            if elapsed > timeout:
                logger.warning(f"[InterruptibleQuery] Query timeout after {timeout}s")
                self._interrupt_query()
                return [], Exception(f"Query timeout after {timeout}s")

            # Check for cancellation
            if cancel_check is not None:
                try:
                    if cancel_check():
                        logger.info("[InterruptibleQuery] Query cancelled by user")
                        self._interrupt_query()
                        return [], Exception("Query cancelled by user")
                except Exception as e:  # catch-all safety net
                    logger.warning(f"[InterruptibleQuery] Cancel check failed: {e}")

            # Sleep briefly before next check
            time.sleep(SPATIALITE_INTERRUPT_CHECK_INTERVAL)

        # Wait for thread to finish (should be immediate since completed=True)
        if self._thread is not None:
            self._thread.join(timeout=1.0)

        elapsed = time.time() - self._start_time

        if self.error:
            logger.debug(f"[InterruptibleQuery] Query failed after {elapsed:.2f}s: {self.error}")
            return [], self.error

        logger.debug(f"[InterruptibleQuery] Query completed in {elapsed:.2f}s ({len(self.results)} rows)")
        return self.results, None

    def _interrupt_query(self):
        """Interrupt the SQLite query using connection.interrupt()."""
        try:
            self.connection.interrupt()
            logger.debug("[InterruptibleQuery] SQLite interrupt() called")
        except sqlite3.Error as e:
            logger.warning(f"[InterruptibleQuery] Failed to interrupt query: {e}")

    @property
    def elapsed_time(self) -> float:
        """Time elapsed since execute() was called."""
        if self._start_time == 0:
            return 0.0
        return time.time() - self._start_time


class BatchedSQLiteQuery:
    """
    Execute large SQLite queries in batches to avoid memory issues.

    Useful for queries that return many rows, processing them in chunks
    to maintain low memory footprint and allow progress reporting.

    Example:
        >>> batched = BatchedSQLiteQuery(conn, "SELECT fid FROM huge_table")
        >>> for batch in batched.execute_batches(batch_size=5000):
        ...     process_batch(batch)
    """

    def __init__(self, connection: sqlite3.Connection, sql: str):
        """
        Initialize batched query.

        Args:
            connection: SQLite connection
            sql: SQL query string
        """
        self.connection = connection
        self.sql = sql

    def execute_batches(
        self,
        batch_size: int = SPATIALITE_BATCH_SIZE,
        cancel_check: Optional[Callable[[], bool]] = None
    ):
        """
        Execute query and yield results in batches.

        Args:
            batch_size: Number of rows per batch
            cancel_check: Callable that returns True to stop iteration

        Yields:
            List of rows for each batch

        Raises:
            StopIteration: When all rows processed or cancelled
        """
        cursor = self.connection.cursor()
        cursor.execute(self.sql)

        while True:
            # Check for cancellation
            if cancel_check is not None and cancel_check():
                logger.info("[BatchedQuery] Cancelled by user")
                break

            batch = cursor.fetchmany(batch_size)
            if not batch:
                break

            yield batch


def create_interruptible_connection(db_path: str) -> sqlite3.Connection:
    """
    Create SQLite connection suitable for interruptible queries.

    The connection is created with check_same_thread=False to allow
    interrupt() calls from the main thread while query runs in background.

    Args:
        db_path: Path to SQLite/Spatialite database

    Returns:
        SQLite connection configured for cross-thread access

    Example:
        >>> conn = create_interruptible_connection("/path/to/db.sqlite")
        >>> query = InterruptibleSQLiteQuery(conn, "SELECT ...")
        >>> results, error = query.execute(cancel_check=lambda: task.isCanceled())
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    logger.debug(f"[InterruptibleQuery] Created connection (check_same_thread=False): {db_path}")
    return conn


# Export symbols
__all__ = [
    'InterruptibleSQLiteQuery',
    'BatchedSQLiteQuery',
    'create_interruptible_connection',
    'SPATIALITE_QUERY_TIMEOUT',
    'SPATIALITE_BATCH_SIZE',
    'SPATIALITE_PROGRESS_INTERVAL',
    'SPATIALITE_INTERRUPT_CHECK_INTERVAL',
    'SPATIALITE_WKT_SIMPLIFY_THRESHOLD',
    'SPATIALITE_WKT_MAX_POINTS',
    'SPATIALITE_GEOM_INSERT_TIMEOUT',
    'USE_OGR_FALLBACK',
]

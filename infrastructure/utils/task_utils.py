# -*- coding: utf-8 -*-
"""
Task Utilities for FilterMate - EPIC-1 Migration

Common utility functions used by FilterMate tasks.
Migrated from modules/tasks/task_utils.py (EPIC-1).

Functions:
    - spatialite_connect: Create Spatialite database connection with WAL mode
    - safe_spatialite_connect: Context manager for Spatialite connections
    - sqlite_execute_with_retry: Execute SQLite operations with retry logic
    - ensure_db_directory_exists: Ensure database directory exists
    - get_best_metric_crs: Determine optimal metric CRS for calculations
    - should_reproject_layer: Check if layer needs reprojection
    - needs_metric_conversion: Check if distance unit needs conversion

Author: FilterMate Team
Date: January 2026
"""

import logging
import os
import sqlite3
import time
from typing import Optional, Tuple
from contextlib import contextmanager

# QGIS imports
try:
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsUnitTypes
    )
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False
    QgsCoordinateReferenceSystem = None
    QgsUnitTypes = None

# FilterMate imports
from ..logging import setup_logger
from ...config.config import ENV_VARS

# Setup logger with rotation
logger = setup_logger(
    'FilterMate.Tasks.Utils',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_tasks.log'),
    level=logging.INFO
)

# =============================================================================
# SQLite Configuration Constants
# =============================================================================

# SQLite connection timeout in seconds (60 seconds to handle concurrent access)
SQLITE_TIMEOUT = 60.0

# Maximum number of retries for database operations when locked
SQLITE_MAX_RETRIES = 10

# Initial delay between retries (will increase exponentially)
SQLITE_RETRY_DELAY = 0.5

# Maximum total retry time in seconds (prevents infinite waiting)
SQLITE_MAX_RETRY_TIME = 30.0

# Task message categories mapping
MESSAGE_TASKS_CATEGORIES = {
    'filter': 'FilterLayers',
    'unfilter': 'FilterLayers',
    'reset': 'FilterLayers',
    'export': 'ExportLayers',
    'add_layers': 'ManageLayers',
    'remove_layers': 'ManageLayers',
    'save_layer_variable': 'ManageLayersProperties',
    'remove_layer_variable': 'ManageLayersProperties'
}


# =============================================================================
# Spatialite Connection Functions
# =============================================================================

def spatialite_connect(db_path: str, timeout: float = SQLITE_TIMEOUT):
    """
    Connect to a Spatialite database with proper timeout to avoid locking issues.
    
    Enables WAL (Write-Ahead Logging) mode for better concurrent access.
    WAL mode allows multiple readers and one writer simultaneously.
    
    Args:
        db_path: Path to the SQLite/Spatialite database file
        timeout: Timeout in seconds for database lock (default 60 seconds)
    
    Returns:
        sqlite3.Connection: Database connection with Spatialite extension loaded
    
    Raises:
        sqlite3.OperationalError: If connection fails or Spatialite extension unavailable
    """
    try:
        # Connect with timeout to handle concurrent access
        conn = sqlite3.connect(db_path, timeout=timeout, isolation_level=None)
        
        # Enable WAL mode for better concurrency
        try:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA busy_timeout=60000')  # 60 second busy timeout
        except sqlite3.OperationalError as e:
            logger.warning(f"Could not configure PRAGMA settings for {db_path}: {e}")
        
        conn.enable_load_extension(True)
        
        # Try to load Spatialite extension (multiple paths for compatibility)
        try:
            conn.load_extension('mod_spatialite')
        except (OSError, sqlite3.OperationalError):
            try:
                conn.load_extension('mod_spatialite.dll')  # Windows
            except (OSError, sqlite3.OperationalError):
                try:
                    conn.load_extension('libspatialite')  # Linux/Mac
                except (OSError, sqlite3.OperationalError) as e:
                    logger.error(f"Could not load Spatialite extension: {e}")
                    raise
        
        return conn
    
    except Exception as e:
        logger.error(f"Failed to connect to Spatialite database {db_path}: {e}")
        raise


@contextmanager
def safe_spatialite_connect(db_path: str, timeout: float = SQLITE_TIMEOUT):
    """
    Context manager for Spatialite connections with automatic cleanup.
    
    Usage:
        with safe_spatialite_connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
    
    Args:
        db_path: Path to the database
        timeout: Connection timeout
    
    Yields:
        sqlite3.Connection: Database connection
    """
    conn = None
    try:
        conn = spatialite_connect(db_path, timeout)
        yield conn
    except Exception as e:
        logger.error(f"Error in safe_spatialite_connect: {e}")
        raise
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")


def sqlite_execute_with_retry(
    conn,
    sql: str,
    params: tuple = None,
    max_retries: int = SQLITE_MAX_RETRIES,
    retry_delay: float = SQLITE_RETRY_DELAY
):
    """
    Execute SQLite query with automatic retry on database lock.
    
    This function handles SQLite's database lock errors by retrying with
    exponential backoff. Useful for concurrent access scenarios.
    
    Args:
        conn: sqlite3.Connection object
        sql: SQL query to execute
        params: Query parameters (optional)
        max_retries: Maximum number of retry attempts
        retry_delay: Initial delay between retries (seconds)
    
    Returns:
        cursor: Result cursor if successful
    
    Raises:
        sqlite3.OperationalError: If max retries exceeded
    """
    retry_count = 0
    current_delay = retry_delay
    start_time = time.time()
    
    while retry_count < max_retries:
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            return cursor
        
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                retry_count += 1
                elapsed = time.time() - start_time
                
                if elapsed > SQLITE_MAX_RETRY_TIME:
                    logger.error(f"SQLite retry timeout exceeded ({SQLITE_MAX_RETRY_TIME}s)")
                    raise
                
                if retry_count >= max_retries:
                    logger.error(f"SQLite max retries ({max_retries}) exceeded")
                    raise
                
                logger.debug(
                    f"Database locked, retry {retry_count}/{max_retries} "
                    f"after {current_delay:.2f}s delay"
                )
                time.sleep(current_delay)
                current_delay *= 2  # Exponential backoff
            else:
                raise
    
    raise sqlite3.OperationalError(f"Max retries ({max_retries}) exceeded")


# =============================================================================
# File System Utilities
# =============================================================================

def ensure_db_directory_exists(db_path: str) -> None:
    """
    Ensure the directory for a database file exists.
    
    Args:
        db_path: Path to the database file
    """
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir, exist_ok=True)
            logger.debug(f"Created directory for database: {db_dir}")
        except OSError as e:
            logger.error(f"Failed to create directory {db_dir}: {e}")
            raise


# =============================================================================
# CRS Utilities
# =============================================================================

def get_best_metric_crs(layer_crs) -> str:
    """
    Determine the best metric CRS for a layer.
    
    For geographic CRS (lat/lon), returns an appropriate metric projection.
    For projected CRS, returns the same CRS if it's already metric.
    
    Args:
        layer_crs: QgsCoordinateReferenceSystem or EPSG code string
    
    Returns:
        str: EPSG code of the best metric CRS (e.g., "EPSG:3857")
    """
    if not QGIS_AVAILABLE:
        return "EPSG:3857"  # Default Web Mercator
    
    # Convert to QgsCoordinateReferenceSystem if needed
    if isinstance(layer_crs, str):
        layer_crs = QgsCoordinateReferenceSystem(layer_crs)
    
    # If already metric, return as-is
    if layer_crs.mapUnits() in (QgsUnitTypes.DistanceMeters, QgsUnitTypes.DistanceKilometers):
        return layer_crs.authid()
    
    # For geographic CRS, use Web Mercator as default
    if layer_crs.isGeographic():
        return "EPSG:3857"
    
    # Fallback
    return layer_crs.authid()


def should_reproject_layer(layer, target_crs_auth_id: str = None) -> bool:
    """
    Check if a layer needs reprojection for metric operations.
    
    Args:
        layer: QgsVectorLayer
        target_crs_auth_id: Target CRS auth ID (e.g., "EPSG:3857")
    
    Returns:
        bool: True if reprojection is needed
    """
    if not QGIS_AVAILABLE:
        return False
    
    try:
        layer_crs = layer.crs()
        
        # If target CRS specified, check if different
        if target_crs_auth_id:
            target_crs = QgsCoordinateReferenceSystem(target_crs_auth_id)
            return layer_crs != target_crs
        
        # Otherwise check if geographic (needs projection for metric operations)
        return layer_crs.isGeographic()
    
    except Exception:
        return False


def needs_metric_conversion(layer) -> bool:
    """
    Check if layer units need conversion to meters.
    
    Args:
        layer: QgsVectorLayer
    
    Returns:
        bool: True if conversion needed
    """
    if not QGIS_AVAILABLE:
        return False
    
    try:
        units = layer.crs().mapUnits()
        return units not in (QgsUnitTypes.DistanceMeters, QgsUnitTypes.DistanceKilometers)
    except Exception:
        return True  # Assume conversion needed if can't determine


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Spatialite functions
    'spatialite_connect',
    'safe_spatialite_connect',
    'sqlite_execute_with_retry',
    
    # File system
    'ensure_db_directory_exists',
    
    # CRS utilities
    'get_best_metric_crs',
    'should_reproject_layer',
    'needs_metric_conversion',
    
    # Constants
    'SQLITE_TIMEOUT',
    'SQLITE_MAX_RETRIES',
    'SQLITE_RETRY_DELAY',
    'SQLITE_MAX_RETRY_TIME',
    'MESSAGE_TASKS_CATEGORIES',
]

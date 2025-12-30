"""
Task Utilities Module

This module provides common utility functions used by FilterMate tasks.
Extracted from appTasks.py during Phase 3 refactoring (Dec 2025).

Functions:
    - spatialite_connect: Create Spatialite database connection with WAL mode
    - sqlite_execute_with_retry: Execute SQLite operations with retry logic
    - get_best_metric_crs: Determine optimal metric CRS for calculations
    - should_reproject_layer: Check if layer needs reprojection
"""

import logging
import os
import sqlite3
import time

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsUnitTypes
)

# Import logging configuration
from ..logging_config import setup_logger
from ...config.config import ENV_VARS

# Setup logger with rotation
logger = setup_logger(
    'FilterMate.Tasks.Utils',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_tasks.log'),
    level=logging.INFO
)

# SQLite connection timeout in seconds (60 seconds to handle concurrent access)
SQLITE_TIMEOUT = 60.0

# Maximum number of retries for database operations when locked
# Increased from 5 to 10 for better handling of concurrent access
SQLITE_MAX_RETRIES = 10

# Initial delay between retries (will increase exponentially)
# Increased from 0.1 to 0.5 for more realistic wait times
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


def spatialite_connect(db_path, timeout=SQLITE_TIMEOUT):
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
        # Use isolation_level=None for autocommit mode which reduces lock contention
        conn = sqlite3.connect(db_path, timeout=timeout, isolation_level=None)
        
        # Enable WAL mode for better concurrency
        # WAL allows multiple readers and one writer without blocking
        try:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')  # Balance between safety and performance
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
                    logger.warning(
                        f"Spatialite extension not available for {db_path}. "
                        f"Spatial operations may be limited. Error: {e}"
                    )
        
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database {db_path}: {e}")
        raise


def ensure_db_directory_exists(db_file_path):
    """
    Ensure the database directory exists before connecting.
    
    This is a shared utility used by both FilterEngineTask and LayersManagementEngineTask
    to validate and create database directories as needed.
    
    Args:
        db_file_path: Path to the database file
    
    Raises:
        OSError: If directory cannot be created
        ValueError: If db_file_path is invalid
    """
    if not db_file_path:
        raise ValueError("db_file_path is not set")
    
    # Normalize path to handle any separator inconsistencies
    normalized_path = os.path.normpath(db_file_path)
    db_dir = os.path.dirname(normalized_path)
    
    if not db_dir:
        raise ValueError(f"Invalid database path: {db_file_path}")
    
    if os.path.exists(db_dir):
        # Directory already exists, check if it's writable
        if not os.access(db_dir, os.W_OK):
            raise OSError(f"Database directory exists but is not writable: {db_dir}")
        logger.debug(f"Database directory exists: {db_dir}")
    else:
        # Validate parent directories before attempting creation
        parent_dir = os.path.dirname(db_dir)
        
        if not parent_dir or not os.path.exists(parent_dir):
            error_msg = (
                f"Cannot create database directory '{db_dir}': "
                f"parent directory '{parent_dir}' does not exist. "
                f"Original path: {db_file_path}"
            )
            logger.error(error_msg)
            raise OSError(error_msg)
        
        if not os.access(parent_dir, os.W_OK):
            error_msg = (
                f"Cannot create database directory '{db_dir}': "
                f"parent directory '{parent_dir}' is not writable. "
                f"Original path: {db_file_path}"
            )
            logger.error(error_msg)
            raise OSError(error_msg)
        
        # Create directory with all intermediate directories
        try:
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Created database directory: {db_dir}")
        except OSError as e:
            error_msg = (
                f"Failed to create database directory '{db_dir}': {e}. "
                f"Original path: {db_file_path}, "
                f"Normalized: {normalized_path}"
            )
            logger.error(error_msg)
            raise OSError(error_msg) from e


def safe_spatialite_connect(db_file_path, timeout=SQLITE_TIMEOUT):
    """
    Safely connect to Spatialite database, ensuring directory exists.
    
    This is a convenience function that combines ensure_db_directory_exists()
    and spatialite_connect() for common use cases in FilterMate tasks.
    
    Args:
        db_file_path: Path to the SQLite/Spatialite database file
        timeout: Timeout in seconds for database lock (default SQLITE_TIMEOUT)
    
    Returns:
        sqlite3.Connection: Database connection with Spatialite extension loaded
        
    Raises:
        OSError: If directory cannot be created
        ValueError: If db_file_path is invalid
        sqlite3.OperationalError: If connection fails or Spatialite extension unavailable
    """
    ensure_db_directory_exists(db_file_path)
    
    try:
        conn = spatialite_connect(db_file_path, timeout)
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to Spatialite database at {db_file_path}: {e}")
        raise


def sqlite_execute_with_retry(operation_func, operation_name="database operation", 
                               max_retries=SQLITE_MAX_RETRIES, initial_delay=SQLITE_RETRY_DELAY,
                               max_total_time=SQLITE_MAX_RETRY_TIME):
    """
    Execute a SQLite operation with retry logic for handling database locks.
    
    Implements exponential backoff for "database is locked" errors with both
    retry count and total time limits for robust handling of concurrent access.
    
    Args:
        operation_func: Callable that performs the database operation. 
                       Should return True on success, raise exception on error.
        operation_name: Description of the operation for logging
        max_retries: Maximum number of retry attempts (default: 10)
        initial_delay: Initial delay between retries in seconds (default: 0.5)
        max_total_time: Maximum total time to spend retrying in seconds (default: 30)
    
    Returns:
        Result from operation_func
        
    Raises:
        sqlite3.OperationalError: If operation fails after all retries or timeout
        Exception: Any other exception from operation_func
        
    Example:
        def my_insert():
            conn = spatialite_connect(db_path)
            try:
                cur = conn.cursor()
                cur.execute("INSERT INTO ...")
                conn.commit()
                return True
            finally:
                conn.close()
                
        sqlite_execute_with_retry(my_insert, "insert properties")
    """
    retry_delay = initial_delay
    last_exception = None
    start_time = time.time()
    
    for attempt in range(max_retries):
        # Check total time limit
        elapsed_time = time.time() - start_time
        if elapsed_time >= max_total_time:
            logger.error(
                f"Database operation '{operation_name}' timed out after {elapsed_time:.1f}s "
                f"({attempt} attempts)"
            )
            if last_exception:
                raise last_exception
            raise sqlite3.OperationalError(
                f"Operation timed out after {max_total_time}s: {operation_name}"
            )
        
        try:
            return operation_func()
            
        except sqlite3.OperationalError as e:
            last_exception = e
            error_msg = str(e).lower()
            
            # Check for recoverable database lock errors
            is_locked = "database is locked" in error_msg or "database is busy" in error_msg
            
            if is_locked and attempt < max_retries - 1:
                # Check if we still have time for another retry
                remaining_time = max_total_time - (time.time() - start_time)
                actual_delay = min(retry_delay, remaining_time - 0.1)  # Leave 0.1s margin
                
                if actual_delay <= 0:
                    logger.error(
                        f"Database operation '{operation_name}' timed out during retry"
                    )
                    raise
                
                # Database locked - retry with exponential backoff
                logger.warning(
                    f"Database locked during {operation_name}. "
                    f"Retry {attempt + 1}/{max_retries} after {actual_delay:.2f}s "
                    f"(elapsed: {time.time() - start_time:.1f}s)"
                )
                time.sleep(actual_delay)
                # Exponential backoff with cap at 5 seconds
                retry_delay = min(retry_delay * 2, 5.0)
                continue
            else:
                # Final attempt failed or different error
                logger.error(
                    f"Database operation '{operation_name}' failed after {attempt + 1} attempts: {e}"
                )
                raise
                
        except Exception as e:
            # Non-recoverable error
            logger.error(f"Error during {operation_name}: {e}")
            raise
    
    # Should not reach here, but just in case
    if last_exception:
        raise last_exception


# =============================================================================
# CRS Functions - Now delegating to crs_utils module
# =============================================================================

def get_best_metric_crs(project, source_crs, extent=None):
    """
    Détermine le meilleur CRS métrique à utiliser pour les calculs.
    
    Cette fonction délègue maintenant au module crs_utils pour une meilleure
    gestion des CRS et le support des zones UTM.
    
    Priorité:
    1. CRS du projet s'il est métrique
    2. Zone UTM optimale basée sur l'emprise (si extent fourni)
    3. EPSG:3857 (Web Mercator) par défaut
    
    Args:
        project: QgsProject instance
        source_crs: QgsCoordinateReferenceSystem du layer source
        extent: QgsRectangle (optionnel) - emprise pour calcul UTM optimal
    
    Returns:
        str: authid du CRS métrique optimal (ex: 'EPSG:3857', 'EPSG:32631')
    """
    try:
        from ..crs_utils import get_optimal_metric_crs
        return get_optimal_metric_crs(
            project=project,
            source_crs=source_crs,
            extent=extent,
            prefer_utm=True
        )
    except ImportError:
        # Fallback to legacy implementation if crs_utils not available
        logger.warning("crs_utils module not available, using legacy get_best_metric_crs")
        return _legacy_get_best_metric_crs(project, source_crs)


def _legacy_get_best_metric_crs(project, source_crs):
    """
    Legacy implementation of get_best_metric_crs.
    Used as fallback if crs_utils module is not available.
    """
    # 1. Vérifier le CRS du projet
    project_crs = project.crs()
    if project_crs and not project_crs.isGeographic():
        map_units = project_crs.mapUnits()
        if map_units not in [QgsUnitTypes.DistanceUnit.Degrees, QgsUnitTypes.DistanceUnit.Unknown]:
            logger.info(f"Using project CRS for metric calculations: {project_crs.authid()}")
            return project_crs.authid()
    
    # 2. Essayer d'obtenir un CRS UTM basé sur l'emprise
    if source_crs and hasattr(QgsCoordinateReferenceSystem, 'createFromWkt'):
        try:
            extent = None
            if hasattr(source_crs, 'bounds'):
                extent = source_crs.bounds()
            
            if extent and extent.isFinite():
                center_lon = (extent.xMinimum() + extent.xMaximum()) / 2
                center_lat = (extent.yMinimum() + extent.yMaximum()) / 2
                
                utm_zone = int((center_lon + 180) / 6) + 1
                
                if center_lat >= 0:
                    utm_epsg = 32600 + utm_zone
                else:
                    utm_epsg = 32700 + utm_zone
                
                utm_crs = QgsCoordinateReferenceSystem(f"EPSG:{utm_epsg}")
                if utm_crs.isValid():
                    logger.info(f"Using calculated UTM CRS for metric calculations: EPSG:{utm_epsg}")
                    return f"EPSG:{utm_epsg}"
        except Exception as e:
            logger.debug(f"Could not calculate optimal UTM CRS: {e}")
    
    # 3. Par défaut, Web Mercator
    logger.info("Using default Web Mercator (EPSG:3857) for metric calculations")
    return "EPSG:3857"


def should_reproject_layer(layer, target_crs_authid):
    """
    Détermine si un layer doit être reprojeté vers le CRS cible.
    
    Utilise crs_utils pour une meilleure détection des CRS géographiques.
    
    Args:
        layer: QgsVectorLayer à vérifier
        target_crs_authid: CRS cible (ex: 'EPSG:3857')
    
    Returns:
        bool: True si reprojection nécessaire
    """
    if not layer or not target_crs_authid:
        return False
    
    layer_crs = layer.sourceCrs()
    
    # Vérifier si les CRS sont identiques
    if layer_crs.authid() == target_crs_authid:
        logger.debug(f"Layer {layer.name()} already in target CRS {target_crs_authid}")
        return False
    
    # Utiliser crs_utils pour une meilleure détection
    try:
        from ..crs_utils import is_geographic_crs, is_metric_crs
        
        if is_geographic_crs(layer_crs):
            logger.info(f"Layer {layer.name()} has geographic CRS {layer_crs.authid()}, will reproject to {target_crs_authid}")
            return True
        
        if not is_metric_crs(layer_crs):
            logger.info(f"Layer {layer.name()} has non-metric units, will reproject to {target_crs_authid}")
            return True
            
    except ImportError:
        # Fallback sans crs_utils
        if layer_crs.isGeographic():
            logger.info(f"Layer {layer.name()} has geographic CRS {layer_crs.authid()}, will reproject to {target_crs_authid}")
            return True
        
        map_units = layer_crs.mapUnits()
        if map_units in [QgsUnitTypes.DistanceUnit.Degrees, QgsUnitTypes.DistanceUnit.Unknown]:
            logger.info(f"Layer {layer.name()} has non-metric units, will reproject to {target_crs_authid}")
            return True
    
    # Le layer est déjà dans un CRS métrique mais différent
    logger.info(f"Layer {layer.name()} will be reprojected from {layer_crs.authid()} to {target_crs_authid} for consistency")
    return True


def needs_metric_conversion(crs):
    """
    Vérifie si un CRS nécessite une conversion vers un CRS métrique.
    
    Args:
        crs: QgsCoordinateReferenceSystem à vérifier
    
    Returns:
        bool: True si le CRS nécessite une conversion pour les opérations métriques
    """
    if not crs or not crs.isValid():
        return True  # Par sécurité, convertir si invalide
    
    try:
        from ..crs_utils import is_geographic_crs, is_metric_crs
        return is_geographic_crs(crs) or not is_metric_crs(crs)
    except ImportError:
        # Fallback
        if crs.isGeographic():
            return True
        map_units = crs.mapUnits()
        return map_units in [QgsUnitTypes.DistanceUnit.Degrees, QgsUnitTypes.DistanceUnit.Unknown]

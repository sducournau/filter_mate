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
SQLITE_MAX_RETRIES = 5

# Initial delay between retries (will increase exponentially)
SQLITE_RETRY_DELAY = 0.1

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
        conn = sqlite3.connect(db_path, timeout=timeout)
        
        # Enable WAL mode for better concurrency
        # WAL allows multiple readers and one writer without blocking
        try:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')  # Balance between safety and performance
        except sqlite3.OperationalError as e:
            logger.warning(f"Could not enable WAL mode for {db_path}: {e}")
        
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


def sqlite_execute_with_retry(operation_func, operation_name="database operation", 
                               max_retries=SQLITE_MAX_RETRIES, initial_delay=SQLITE_RETRY_DELAY):
    """
    Execute a SQLite operation with retry logic for handling database locks.
    
    Implements exponential backoff for "database is locked" errors.
    
    Args:
        operation_func: Callable that performs the database operation. 
                       Should return True on success, raise exception on error.
        operation_name: Description of the operation for logging
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries (will increase exponentially)
    
    Returns:
        Result from operation_func
        
    Raises:
        sqlite3.OperationalError: If operation fails after all retries
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
    
    for attempt in range(max_retries):
        try:
            return operation_func()
            
        except sqlite3.OperationalError as e:
            last_exception = e
            
            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                # Database locked - retry with exponential backoff
                logger.warning(
                    f"Database locked during {operation_name}. "
                    f"Retry {attempt + 1}/{max_retries} after {retry_delay:.2f}s"
                )
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
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


def get_best_metric_crs(project, source_crs):
    """
    Détermine le meilleur CRS métrique à utiliser pour les calculs.
    Priorité:
    1. CRS du projet s'il est métrique
    2. CRS suggéré par QGIS basé sur l'emprise
    3. EPSG:3857 (Web Mercator) par défaut
    
    Args:
        project: QgsProject instance
        source_crs: QgsCoordinateReferenceSystem du layer source
    
    Returns:
        str: authid du CRS métrique optimal (ex: 'EPSG:3857')
    """
    # 1. Vérifier le CRS du projet
    project_crs = project.crs()
    if project_crs and not project_crs.isGeographic():
        # Le CRS du projet est métrique, l'utiliser
        map_units = project_crs.mapUnits()
        if map_units not in [QgsUnitTypes.DistanceUnit.Degrees, QgsUnitTypes.DistanceUnit.Unknown]:
            logger.info(f"Using project CRS for metric calculations: {project_crs.authid()}")
            return project_crs.authid()
    
    # 2. Essayer d'obtenir un CRS suggéré basé sur l'emprise
    if source_crs and hasattr(QgsCoordinateReferenceSystem, 'createFromWkt'):
        try:
            # Obtenir les limites du layer
            extent = None
            if hasattr(source_crs, 'bounds'):
                extent = source_crs.bounds()
            
            # Si possible, obtenir un CRS UTM approprié basé sur la longitude centrale
            if extent and extent.isFinite():
                center_lon = (extent.xMinimum() + extent.xMaximum()) / 2
                center_lat = (extent.yMinimum() + extent.yMaximum()) / 2
                
                # Calculer la zone UTM
                utm_zone = int((center_lon + 180) / 6) + 1
                
                # Déterminer si hémisphère nord ou sud
                if center_lat >= 0:
                    # Hémisphère nord
                    utm_epsg = 32600 + utm_zone
                else:
                    # Hémisphère sud
                    utm_epsg = 32700 + utm_zone
                
                utm_crs = QgsCoordinateReferenceSystem(f"EPSG:{utm_epsg}")
                if utm_crs.isValid():
                    logger.info(f"Using calculated UTM CRS for metric calculations: EPSG:{utm_epsg}")
                    return f"EPSG:{utm_epsg}"
        except Exception as e:
            logger.debug(f"Could not calculate optimal UTM CRS: {e}")
    
    # 3. Par défaut, utiliser Web Mercator (EPSG:3857)
    logger.info("Using default Web Mercator (EPSG:3857) for metric calculations")
    return "EPSG:3857"


def should_reproject_layer(layer, target_crs_authid):
    """
    Détermine si un layer doit être reprojeté vers le CRS cible.
    
    Args:
        layer: QgsVectorLayer à vérifier
        target_crs_authid: CRS cible (ex: 'EPSG:3857')
    
    Returns:
        bool: True si reprojection nécessaire
    """
    if not layer or not target_crs_authid:
        return False
    
    layer_crs = layer.sourceCrs()
    
    # Vérifier si les CRS sont différents
    if layer_crs.authid() == target_crs_authid:
        logger.debug(f"Layer {layer.name()} already in target CRS {target_crs_authid}")
        return False
    
    # Vérifier si le CRS du layer est géographique
    if layer_crs.isGeographic():
        logger.info(f"Layer {layer.name()} has geographic CRS {layer_crs.authid()}, will reproject to {target_crs_authid}")
        return True
    
    # Vérifier les unités de distance
    map_units = layer_crs.mapUnits()
    if map_units in [QgsUnitTypes.DistanceUnit.Degrees, QgsUnitTypes.DistanceUnit.Unknown]:
        logger.info(f"Layer {layer.name()} has non-metric units, will reproject to {target_crs_authid}")
        return True
    
    # Le layer est déjà dans un CRS métrique mais différent
    # Pour la cohérence, reprojetons quand même vers le CRS cible commun
    logger.info(f"Layer {layer.name()} will be reprojected from {layer_crs.authid()} to {target_crs_authid} for consistency")
    return True

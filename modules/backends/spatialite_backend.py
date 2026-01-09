# -*- coding: utf-8 -*-
"""
Spatialite Backend for FilterMate

Backend for Spatialite databases.
Uses Spatialite spatial functions which are largely compatible with PostGIS.

v2.4.0 Improvements:
- WKT caching for repeated filter operations
- Improved CRS handling

v2.4.14 Improvements:
- Direct mod_spatialite loading for GeoPackage (bypasses GDAL limitations)
- Fallback to FID-based filtering when setSubsetString doesn't support Spatialite SQL
- Improved GeoPackage spatial query performance

v2.4.20 Improvements:
- PRIORITY DIRECT SQL for GeoPackage (more reliable than native mode)
- Cache invalidation to force retesting with direct SQL mode

v2.4.21 Improvements:
- CRITICAL FIX: Remote/distant layers detection before Spatialite testing
- Prevents "unable to open database file" errors for WFS/HTTP/service layers
- File existence verification before SQLite connection attempts

v2.6.2 Improvements:
- CRITICAL FIX: Interruptible SQLite queries to prevent QGIS freezing
- Threaded query execution with progress callback and cancellation
- SQLite interrupt mechanism for immediate query termination

v2.6.5 Improvements:
- LARGE WKT OPTIMIZATION: Store WKT in task_params for R-tree source table optimization
- Lowered threshold for R-tree optimization from 100KB to 50KB
- Bounding box pre-filter for very large WKT (>500KB) - O(log n) vs O(n)
- Fallback WKT extraction from expression when not in task_params
- Enhanced logging for optimization path selection
"""

from typing import Dict, Optional, Tuple, List
import sqlite3
import time
import re
import os
import threading
from qgis.core import QgsVectorLayer, QgsDataSourceUri
from .base_backend import GeometricFilterBackend
from ..logging_config import get_tasks_logger
from ..constants import PROVIDER_SPATIALITE
from ..appUtils import safe_set_subset_string, clean_buffer_value
from ..object_safety import is_valid_layer  # v2.9.24: For selection clearing

logger = get_tasks_logger()

# v2.4.21: Force cache clear on module reload to apply remote detection fix
# This ensures that the new logic is used instead of cached results
_CACHE_VERSION = "2.4.21"  # Increment this to force cache invalidation

# Import WKT Cache for performance optimization (v2.4.0)
try:
    from .wkt_cache import get_wkt_cache, WKTCache
    WKT_CACHE_AVAILABLE = True
except ImportError:
    WKT_CACHE_AVAILABLE = False
    get_wkt_cache = None

# v2.5.10: Import Multi-Step Optimizer for attribute-first filtering
try:
    from .multi_step_optimizer import (
        MultiStepFilterOptimizer,
        MultiStepPlanBuilder,
        BackendFilterStrategy,
        AttributePreFilter,
        SpatialiteOptimizer,
        BackendSelectivityEstimator
    )
    MULTI_STEP_OPTIMIZER_AVAILABLE = True
except ImportError:
    MULTI_STEP_OPTIMIZER_AVAILABLE = False
    MultiStepFilterOptimizer = None
    MultiStepPlanBuilder = None
    BackendFilterStrategy = None
    AttributePreFilter = None
    SpatialiteOptimizer = None
    BackendSelectivityEstimator = None
    WKTCache = None

# v2.8.11: Import Spatialite Cache for multi-step filtering
try:
    from .spatialite_cache import (
        get_cache as get_spatialite_cache,
        store_filter_fids,
        get_previous_filter_fids,
        intersect_filter_fids,
        SpatialiteCacheDB
    )
    SPATIALITE_CACHE_AVAILABLE = True
except ImportError:
    SPATIALITE_CACHE_AVAILABLE = False
    get_spatialite_cache = None
    store_filter_fids = None
    get_previous_filter_fids = None
    intersect_filter_fids = None
    SpatialiteCacheDB = None

# v2.8.8: Import cache helpers for shared cache logic
try:
    from .cache_helpers import (
        perform_cache_intersection,
        store_filter_result,
        get_cache_parameters_from_task,
        get_combine_operator_from_task,
        CACHE_AVAILABLE
    )
except ImportError:
    perform_cache_intersection = None
    store_filter_result = None
    get_cache_parameters_from_task = None
    get_combine_operator_from_task = None
    CACHE_AVAILABLE = False


# Cache for mod_spatialite availability (tested once per session)
_MOD_SPATIALITE_AVAILABLE: Optional[bool] = None
_MOD_SPATIALITE_EXTENSION_NAME: Optional[str] = None

# v2.6.2: Performance and timeout constants for complex geometric filters
# These prevent QGIS freezing on large datasets
SPATIALITE_QUERY_TIMEOUT = 120  # Maximum seconds for SQLite queries
SPATIALITE_BATCH_SIZE = 5000    # Process FIDs in batches to avoid memory issues
SPATIALITE_PROGRESS_INTERVAL = 1000  # Report progress every N features
SPATIALITE_INTERRUPT_CHECK_INTERVAL = 0.5  # Check for cancellation every N seconds

# v2.8.7: WKT simplification thresholds to prevent GeomFromText freeze on complex geometries
# GeomFromText parsing complexity is O(n²) for polygon validation
# v2.8.12: Reduced threshold from 100KB to 30KB to catch MakeValid errors on complex geometries
SPATIALITE_WKT_SIMPLIFY_THRESHOLD = 30000  # 30KB - trigger Python simplification (was 100KB)
SPATIALITE_WKT_MAX_POINTS = 3000  # Max points before aggressive simplification (was 5000)
SPATIALITE_GEOM_INSERT_TIMEOUT = 30  # Timeout for geometry insertion (seconds)

# v2.9.27: Sentinel value to signal that OGR fallback is required
# Used when GeometryCollection cannot be converted and RTTOPO MakeValid would fail
USE_OGR_FALLBACK = "__USE_OGR_FALLBACK__"


class InterruptibleSQLiteQuery:
    """
    v2.6.2: Execute SQLite queries in a separate thread with interrupt capability.
    
    This class solves the QGIS freeze problem by:
    1. Running the query in a background thread
    2. Periodically checking for cancellation
    3. Using SQLite's interrupt() method to stop long-running queries
    
    Usage:
        query = InterruptibleSQLiteQuery(conn, "SELECT * FROM table WHERE ...")
        results = query.execute(timeout=60, cancel_check=lambda: task.isCanceled())
    """
    
    def __init__(self, connection: sqlite3.Connection, sql: str):
        self.connection = connection
        self.sql = sql
        self.results = []
        self.error = None
        self.completed = False
        self._thread = None
    
    def _execute_query(self):
        """Execute the query in background thread."""
        try:
            cursor = self.connection.cursor()
            cursor.execute(self.sql)
            self.results = cursor.fetchall()
            self.completed = True
        except Exception as e:
            self.error = e
            self.completed = True
    
    def execute(self, timeout: float = 120, cancel_check=None) -> Tuple[List, Optional[Exception]]:
        """
        Execute query with timeout and cancellation support.
        
        Args:
            timeout: Maximum time in seconds to wait for query
            cancel_check: Callable that returns True if operation should be cancelled
        
        Returns:
            Tuple of (results list, error or None)
        """
        # Start query in background thread
        self._thread = threading.Thread(target=self._execute_query, daemon=True)
        self._thread.start()
        
        # Wait for completion with periodic cancellation checks
        start_time = time.time()
        while not self.completed:
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > timeout:
                # Interrupt the SQLite query
                try:
                    self.connection.interrupt()
                except Exception:
                    pass
                return [], Exception(f"Query timeout after {timeout}s")
            
            # Check for cancellation
            if cancel_check and cancel_check():
                # Interrupt the SQLite query immediately
                try:
                    self.connection.interrupt()
                except Exception:
                    pass
                return [], Exception("Query cancelled by user")
            
            # Sleep briefly before next check
            time.sleep(SPATIALITE_INTERRUPT_CHECK_INTERVAL)
        
        # Wait for thread to finish (should be immediate since completed=True)
        self._thread.join(timeout=1.0)
        
        if self.error:
            return [], self.error
        
        return self.results, None


def _test_mod_spatialite_available() -> Tuple[bool, Optional[str]]:
    """
    Test if mod_spatialite extension can be loaded directly via sqlite3.
    
    This is different from testing via GDAL/OGR - even if GDAL's GeoPackage
    driver doesn't support Spatialite SQL in setSubsetString, we may still
    be able to load mod_spatialite directly for SQL queries.
    
    Returns:
        Tuple of (available: bool, extension_name: str or None)
    """
    global _MOD_SPATIALITE_AVAILABLE, _MOD_SPATIALITE_EXTENSION_NAME
    
    if _MOD_SPATIALITE_AVAILABLE is not None:
        return (_MOD_SPATIALITE_AVAILABLE, _MOD_SPATIALITE_EXTENSION_NAME)
    
    # Test extensions in order of preference
    extension_names = ['mod_spatialite', 'mod_spatialite.dll', 'libspatialite.so']
    
    for ext_name in extension_names:
        try:
            conn = sqlite3.connect(':memory:')
            conn.enable_load_extension(True)
            conn.load_extension(ext_name)
            
            # Verify spatial functions work
            cursor = conn.cursor()
            cursor.execute("SELECT ST_GeomFromText('POINT(0 0)', 4326) IS NOT NULL")
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0]:
                logger.info(f"✓ mod_spatialite available via extension: {ext_name}")
                _MOD_SPATIALITE_AVAILABLE = True
                _MOD_SPATIALITE_EXTENSION_NAME = ext_name
                return (True, ext_name)
                
        except Exception as e:
            logger.debug(f"mod_spatialite extension '{ext_name}' not available: {e}")
            continue
    
    logger.warning("mod_spatialite extension not available - direct SQL queries not possible")
    _MOD_SPATIALITE_AVAILABLE = False
    _MOD_SPATIALITE_EXTENSION_NAME = None
    return (False, None)


class SpatialiteGeometricFilter(GeometricFilterBackend):
    """
    Spatialite backend for geometric filtering.
    
    This backend provides filtering for Spatialite layers using:
    - Spatialite spatial functions (similar to PostGIS)
    - SQL-based filtering
    - Good performance for small to medium datasets
    
    v2.4.0: Added WKT caching for repeated filter operations
    v2.4.1: Improved GeoPackage detection with file-level caching
    v2.4.12: Added thread-safe cache access with lock
    v2.4.14: Added direct SQL mode for GeoPackage when setSubsetString doesn't support Spatialite
    v2.4.20: Priority direct SQL mode for GeoPackage - more reliable than native setSubsetString
    v2.9.2: Added CENTROID_MODE for better point-in-polygon handling
    """
    
    # Class-level caches for Spatialite support testing
    _spatialite_support_cache: Dict[str, bool] = {}  # layer_id -> supports
    _spatialite_file_cache: Dict[str, bool] = {}  # file_path -> supports
    
    # Cache for direct SQL mode (GeoPackage with mod_spatialite but without setSubsetString support)
    # layer_id -> True means use direct SQL mode (query FIDs via mod_spatialite, then simple IN filter)
    _direct_sql_mode_cache: Dict[str, bool] = {}
    
    # v2.4.20: Cache version tracking for automatic invalidation on upgrade
    _cache_version: str = ""
    
    # Thread lock for cache access (thread-safety for large GeoPackage with 50+ layers)
    import threading
    _cache_lock = threading.RLock()
    
    # v2.9.2: Centroid optimization mode
    # 'centroid' = ST_Centroid() - fast but may be outside concave polygons
    # 'point_on_surface' = ST_PointOnSurface() - guaranteed inside polygon (recommended)
    # 'auto' = Use PointOnSurface for polygons, Centroid for lines
    CENTROID_MODE = 'point_on_surface'
    
    @classmethod
    def clear_support_cache(cls):
        """
        Clear the Spatialite support test cache.
        
        Call this when reloading layers or when support status may have changed.
        """
        with cls._cache_lock:
            cls._spatialite_support_cache.clear()
            cls._spatialite_file_cache.clear()
            cls._direct_sql_mode_cache.clear()
        logger.debug("Spatialite support cache cleared")
    
    @classmethod
    def invalidate_layer_cache(cls, layer_id: str):
        """
        Invalidate the cache for a specific layer.
        
        Args:
            layer_id: ID of the layer to invalidate
        """
        with cls._cache_lock:
            if layer_id in cls._spatialite_support_cache:
                del cls._spatialite_support_cache[layer_id]
            if layer_id in cls._direct_sql_mode_cache:
                del cls._direct_sql_mode_cache[layer_id]
                logger.debug(f"Spatialite cache invalidated for layer {layer_id}")
    
    def __init__(self, task_params: Dict):
        """
        Initialize Spatialite backend.
        
        Args:
            task_params: Task parameters dictionary
        """
        super().__init__(task_params)
        self.logger = logger
        self._temp_table_name = None
        self._temp_table_conn = None
        # CRITICAL FIX: Temp tables don't work with setSubsetString!
        # QGIS uses its own connection to evaluate subset strings,
        # and SQLite TEMP tables are connection-specific.
        # When we create a TEMP table in our connection, QGIS cannot see it.
        # Solution: Always use inline WKT in GeomFromText() for subset strings.
        self._use_temp_table = False  # DISABLED: doesn't work with setSubsetString
        
        # WKT cache reference (v2.4.0)
        self._wkt_cache = get_wkt_cache() if WKT_CACHE_AVAILABLE else None
        
        # v2.4.20: Auto-clear cache if version changed (ensures new direct SQL logic is used)
        with self.__class__._cache_lock:
            if self.__class__._cache_version != _CACHE_VERSION:
                logger.info(f"🔄 Cache version changed ({self.__class__._cache_version} → {_CACHE_VERSION}), clearing Spatialite support cache")
                self.__class__._spatialite_support_cache.clear()
                self.__class__._spatialite_file_cache.clear()
                self.__class__._direct_sql_mode_cache.clear()
                self.__class__._cache_version = _CACHE_VERSION

    # Note: _get_buffer_endcap_style(), _get_buffer_segments(), _get_simplify_tolerance()
    # are inherited from GeometricFilterBackend (v2.8.6 refactoring)
    
    def _build_st_buffer_with_style(self, geom_expr: str, buffer_value: float) -> str:
        """
        Build ST_Buffer expression with endcap style from task_params.

        FIX v3.0.12: Now delegates to unified _build_buffer_expression() in base_backend.py
        to eliminate code duplication between PostgreSQL and Spatialite backends.

        Supports both positive buffers (expansion) and negative buffers (erosion/shrinking).
        Negative buffers only work on polygon geometries - they shrink the polygon inward.

        Args:
            geom_expr: Geometry expression to buffer
            buffer_value: Buffer distance (positive=expand, negative=shrink/erode)

        Returns:
            Spatialite ST_Buffer expression with style parameter

        Note:
            All buffer logic is now centralized in GeometricFilterBackend._build_buffer_expression()
            This method is a thin wrapper that specifies 'spatialite' dialect.
        """
        return self._build_buffer_expression(geom_expr, buffer_value, dialect='spatialite')
    
    def supports_layer(self, layer: QgsVectorLayer) -> bool:
        """
        Check if this backend supports the given layer.
        
        Supports:
        - Native Spatialite layers (providerType == 'spatialite')
        - GeoPackage files via OGR IF Spatialite functions are available
        - SQLite files via OGR IF Spatialite functions are available
        - GeoPackage/SQLite via DIRECT SQL mode if mod_spatialite is available
          (even when GDAL's OGR driver doesn't support Spatialite in setSubsetString)
        
        CRITICAL: GeoPackage/SQLite support depends on GDAL being compiled with Spatialite.
        This method now tests if spatial functions actually work before returning True.
        
        v2.4.14: Added direct SQL mode fallback for GeoPackage when setSubsetString
        doesn't support Spatialite but mod_spatialite is available.
        
        Args:
            layer: QGIS vector layer to check
        
        Returns:
            True if layer supports Spatialite spatial functions
        """
        provider_type = layer.providerType()
        layer_id = layer.id()
        
        # Native Spatialite provider - fully supported
        if provider_type == PROVIDER_SPATIALITE:
            self.log_debug(f"✓ Native Spatialite layer: {layer.name()}")
            return True
        
        # GeoPackage/SQLite via OGR - need to test if Spatialite functions work
        if provider_type == 'ogr':
            source = layer.source()
            source_path = source.split('|')[0] if '|' in source else source
            
            # v2.4.21: CRITICAL FIX - Detect remote/distant sources before testing
            # Remote sources should NOT use Spatialite backend - use OGR fallback instead
            source_lower = source_path.lower().strip()
            
            # Check for remote URLs (http, https, ftp, etc.)
            remote_prefixes = ('http://', 'https://', 'ftp://', 'wfs:', 'wms:', 'wcs://', '/vsicurl/')
            if any(source_lower.startswith(prefix) for prefix in remote_prefixes):
                self.log_info(f"⚠️ Remote source detected for {layer.name()} - Spatialite NOT supported")
                self.log_debug(f"   → Source: {source_path[:100]}...")
                return False
            
            # Check for service markers in source string (WFS, OAPIF, etc.)
            service_markers = ['url=', 'service=', 'srsname=', 'typename=', 'version=']
            if any(marker in source_lower for marker in service_markers):
                self.log_info(f"⚠️ Service source detected for {layer.name()} - Spatialite NOT supported")
                self.log_debug(f"   → Source contains service markers")
                return False
            
            # v2.4.21: Verify file exists before testing Spatialite support
            # This prevents "unable to open database file" errors for non-existent paths
            if source_path.lower().endswith('.gpkg') or source_path.lower().endswith('.sqlite'):
                file_type = "GeoPackage" if source_path.lower().endswith('.gpkg') else "SQLite"
                
                # Check if file exists locally
                if not os.path.isfile(source_path):
                    self.log_info(f"⚠️ {file_type} file not found for {layer.name()} - Spatialite NOT supported")
                    self.log_debug(f"   → Path: {source_path}")
                    self.log_debug(f"   → This may be a remote or virtual source")
                    return False
                
                self.log_info(f"🔍 Testing Spatialite support for {file_type} layer: {layer.name()}")
                
                # Check cache first for this layer - only use cache if we have a POSITIVE result
                # FIX v2.4.20: Always retest if cached mode is "native" - direct SQL is more reliable
                with self.__class__._cache_lock:
                    if layer_id in self.__class__._spatialite_support_cache:
                        cached = self.__class__._spatialite_support_cache[layer_id]
                        if cached:  # Cached positive result
                            use_direct = self.__class__._direct_sql_mode_cache.get(layer_id, False)
                            if use_direct:
                                # Direct SQL mode cached - safe to use
                                self.log_info(f"  → CACHE HIT (True): mode=direct SQL")
                                return True
                            else:
                                # Native mode cached - retest for direct SQL (more reliable)
                                self.log_info(f"  → CACHE HIT (True, native mode) - retesting for direct SQL...")
                                # Invalidate cache to force retest with direct SQL priority
                                del self.__class__._spatialite_support_cache[layer_id]
                                if layer_id in self.__class__._direct_sql_mode_cache:
                                    del self.__class__._direct_sql_mode_cache[layer_id]
                        else:
                            # Cached negative result - need to retest with direct SQL
                            self.log_info(f"  → CACHE HIT (False) - retesting with direct SQL mode...")
                            # Remove from cache to force retest
                            del self.__class__._spatialite_support_cache[layer_id]
                
                # FIX v2.4.20: PRIORITY DIRECT SQL for GeoPackage
                # The native setSubsetString mode with Spatialite SQL is unreliable:
                # - Simple test expressions (ST_Intersects with POINT) may pass
                # - But complex expressions with WKT geometries are silently ignored by GDAL
                # - This causes filters to appear successful but return ALL features
                #
                # Solution: Always prefer direct SQL mode for GeoPackage/SQLite
                # This queries FIDs directly via mod_spatialite and applies simple "fid IN (...)" filter
                
                # Test 1: Try direct SQL mode FIRST (more reliable for complex expressions)
                # This works even when GDAL's OGR driver doesn't support Spatialite SQL
                mod_available, ext_name = _test_mod_spatialite_available()
                self.log_info(f"  → mod_spatialite available: {mod_available}")
                if mod_available:
                    # Verify we can connect to this specific file with mod_spatialite
                    direct_works = self._test_direct_spatialite_connection(source_path)
                    self.log_info(f"  → Direct connection test: {direct_works}")
                    if direct_works:
                        self.log_info(
                            f"✓ {file_type} layer: {layer.name()} - Using DIRECT SQL mode "
                            f"(mod_spatialite bypassing GDAL)"
                        )
                        with self.__class__._cache_lock:
                            self.__class__._direct_sql_mode_cache[layer_id] = True  # Use direct SQL mode
                            self.__class__._spatialite_support_cache[layer_id] = True
                        return True
                    else:
                        self.log_info(f"  → Direct SQL mode failed, trying native mode as fallback...")
                else:
                    self.log_info(f"  → mod_spatialite not available, trying native mode...")
                
                # Test 2: Fallback to native setSubsetString with Spatialite SQL
                # NOTE: This may work for simple expressions but fail for complex WKT geometries
                native_works = self._test_spatialite_functions_no_cache(layer)
                if native_works:
                    self.log_warning(
                        f"⚠️ {file_type} layer: {layer.name()} - Using NATIVE mode (less reliable)\n"
                        f"   Direct SQL mode unavailable. Native mode may fail with complex geometries.\n"
                        f"   Install mod_spatialite for more reliable spatial filtering."
                    )
                    with self.__class__._cache_lock:
                        self.__class__._spatialite_support_cache[layer_id] = True
                        self.__class__._direct_sql_mode_cache[layer_id] = False  # Use native mode
                    return True
                
                # Both methods failed - cache negative result
                with self.__class__._cache_lock:
                    self.__class__._spatialite_support_cache[layer_id] = False
                
                self.log_warning(
                    f"⚠️ {layer.name()}: GeoPackage/SQLite detected but Spatialite NOT available.\n"
                    f"   • setSubsetString test: FAILED (GDAL not compiled with Spatialite)\n"
                    f"   • Direct SQL test: FAILED (mod_spatialite extension not loadable)\n"
                    f"   Falling back to OGR backend (QGIS processing)."
                )
                return False
            else:
                # OGR layer but not GeoPackage/SQLite - not supported by Spatialite backend
                self.log_debug(
                    f"⚠️ {layer.name()}: OGR layer but not GeoPackage/SQLite "
                    f"(source ends with: ...{source_path[-30:] if len(source_path) > 30 else source_path})"
                )
                return False
        
        # Provider is neither 'spatialite' nor 'ogr' - not supported
        self.log_debug(f"⚠️ {layer.name()}: Provider '{provider_type}' not supported by Spatialite backend")
        return False
    
    def _test_direct_spatialite_connection(self, file_path: str) -> bool:
        """
        Test if we can open a GeoPackage/SQLite file with mod_spatialite directly.
        
        Args:
            file_path: Path to the GeoPackage or SQLite file
            
        Returns:
            True if connection with mod_spatialite works
        """
        try:
            mod_available, ext_name = _test_mod_spatialite_available()
            if not mod_available or not ext_name:
                return False
            
            if not os.path.isfile(file_path):
                self.log_warning(f"File not found: {file_path}")
                return False
            
            conn = sqlite3.connect(file_path)
            conn.enable_load_extension(True)
            conn.load_extension(ext_name)
            
            # Test spatial function works
            cursor = conn.cursor()
            cursor.execute("SELECT ST_GeomFromText('POINT(0 0)', 4326) IS NOT NULL")
            result = cursor.fetchone()
            conn.close()
            
            return result and result[0]
            
        except Exception as e:
            self.log_debug(f"Direct Spatialite connection test failed for {file_path}: {e}")
            return False
    
    def _test_spatialite_functions(self, layer: QgsVectorLayer) -> bool:
        """
        Test if Spatialite spatial functions work on this layer.
        
        Tests by trying a simple GeomFromText expression in setSubsetString.
        If it fails, Spatialite functions are not available.
        
        Uses a cached result per layer ID AND per source file to avoid repeated testing.
        For GeoPackage with 40+ layers, testing one layer is enough to know
        if Spatialite functions work for the whole file.
        
        IMPROVED v2.4.1: Better detection of geometry column for GeoPackage layers
        - Tries dataProvider().geometryColumn() first (v2.6.6: fixed method name)
        - Falls back to common column names (geometry, geom)
        - Uses simpler test expressions that are more likely to succeed
        - Cache by source file for multi-layer GeoPackages
        
        FIXED v2.4.11: Use simpler test expression without spatial functions
        - First test if basic subset works
        - Then test if ST_IsValid (simpler than ST_Intersects) works
        - Better error diagnostics
        
        Args:
            layer: Layer to test
            
        Returns:
            True if Spatialite functions work, False otherwise
        """
        # Use class-level cache (defined as class attributes)
        layer_id = layer.id()
        
        # THREAD SAFETY v2.4.12: Use lock when accessing cache
        with self.__class__._cache_lock:
            if layer_id in self.__class__._spatialite_support_cache:
                cached = self.__class__._spatialite_support_cache[layer_id]
                # v2.4.13: Log at INFO level if cache returns False (helps diagnose fallback issues)
                if cached:
                    self.log_debug(f"Using cached Spatialite support result for {layer.name()}: {cached}")
                else:
                    self.log_info(f"⚠️ CACHE HIT (False) for {layer.name()} - Spatialite test previously failed, using OGR fallback")
                return cached
        
        # OPTIMIZATION: Check if we already tested this source file (e.g., GeoPackage)
        # For multi-layer GeoPackages, we only need to test once per file
        source = layer.source()
        source_path = source.split('|')[0] if '|' in source else source
        # Normalize path for consistent cache key (handle Windows case-insensitivity)
        import os
        source_path_normalized = os.path.normpath(source_path).lower() if source_path else ""
        
        # Check file cache with lock
        with self.__class__._cache_lock:
            if source_path_normalized.endswith('.gpkg') or source_path_normalized.endswith('.sqlite'):
                if source_path_normalized in self.__class__._spatialite_file_cache:
                    cached = self.__class__._spatialite_file_cache[source_path_normalized]
                    # v2.4.13: Log at INFO level for positive file cache (helps confirm Spatialite works for file)
                    if cached:
                        self.log_info(f"✓ FILE CACHE HIT for {layer.name()} - Spatialite verified for this GeoPackage")
                    else:
                        self.log_info(f"⚠️ FILE CACHE HIT (False) for {layer.name()} - Spatialite unavailable for this file")
                    self.__class__._spatialite_support_cache[layer_id] = cached
                    return cached
        
        try:
            # Save current subset string
            original_subset = layer.subsetString()
            
            # Get geometry column name - try multiple methods
            # v2.6.6: Use dataProvider().geometryColumn() - QgsVectorLayer doesn't have geometryColumn() directly
            try:
                geom_col = layer.dataProvider().geometryColumn()
            except (AttributeError, RuntimeError):
                geom_col = None
            
            # EARLY CHECK: Detect layers without geometry
            # These layers can still use Spatialite for attribute filtering
            has_geometry = layer.geometryType() != 4  # 4 = QgsWkbTypes.NullGeometry
            if not has_geometry and not geom_col:
                self.log_info(f"⚠️ Layer {layer.name()} has no geometry - using attribute-only Spatialite mode")
                # For non-spatial layers, we still support Spatialite for attribute filtering
                # Cache only by layer ID, NOT by file (to avoid affecting spatial layers)
                with self.__class__._cache_lock:
                    self.__class__._spatialite_support_cache[layer_id] = True
                return True
            
            self.log_info(f"🔍 Testing Spatialite support for {layer.name()}")
            self.log_info(f"  → Geometry column from layer: '{geom_col}'")
            self.log_info(f"  → Provider: {layer.providerType()}")
            self.log_info(f"  → Has geometry: {has_geometry}")
            self.log_info(f"  → Source: {source_path[:80]}...")
            
            # Build list of candidate geometry column names
            candidates = []
            if geom_col:
                candidates.append(geom_col)
            # Common GeoPackage/Spatialite column names
            candidates.extend(['geometry', 'geom', 'GEOMETRY', 'GEOM', 'the_geom'])
            # Remove duplicates while preserving order
            seen = set()
            unique_candidates = []
            for c in candidates:
                if c.lower() not in seen:
                    seen.add(c.lower())
                    unique_candidates.append(c)
            
            self.log_debug(f"  → Candidate geometry columns: {unique_candidates}")
            
            # STEP 1: First test if basic subset works at all
            basic_test = "1 = 0"  # Should always work, returns no features
            try:
                basic_result = layer.setSubsetString(basic_test)
                layer.setSubsetString(original_subset if original_subset else "")
                if not basic_result:
                    self.log_error(f"  ✗ Basic subset test failed for {layer.name()} - layer may not support subset strings")
                    with self.__class__._cache_lock:
                        self.__class__._spatialite_support_cache[layer_id] = False
                        # Do NOT cache by file - other layers may work fine
                    return False
                else:
                    self.log_debug(f"  ✓ Basic subset test passed")
            except Exception as e:
                self.log_error(f"  ✗ Basic subset test exception: {e}")
                with self.__class__._cache_lock:
                    self.__class__._spatialite_support_cache[layer_id] = False
                    # Do NOT cache by file - other layers may work fine
                return False
            
            # STEP 2: Try each candidate geometry column with progressively simpler tests
            result = False
            for test_geom_col in unique_candidates:
                # Test 1: Simple geometry not null (should always work if column exists)
                test_expr_simple = f"\"{test_geom_col}\" IS NOT NULL AND 1 = 0"
                try:
                    result_simple = layer.setSubsetString(test_expr_simple)
                    layer.setSubsetString(original_subset if original_subset else "")
                    if not result_simple:
                        self.log_debug(f"  → Column '{test_geom_col}' does not exist or is not accessible")
                        continue
                    else:
                        self.log_debug(f"  ✓ Column '{test_geom_col}' exists")
                except Exception:
                    continue
                
                # Test 2: GeomFromText (tests if spatial functions are available)
                test_expr_geom = f"GeomFromText('POINT(0 0)', 4326) IS NOT NULL AND 1 = 0"
                try:
                    result_geom = layer.setSubsetString(test_expr_geom)
                    layer.setSubsetString(original_subset if original_subset else "")
                    if not result_geom:
                        self.log_warning(f"  ✗ GeomFromText function NOT available - Spatialite extension not loaded")
                        # This means GDAL was not compiled with Spatialite
                        break
                    else:
                        self.log_debug(f"  ✓ GeomFromText function available")
                except Exception as e:
                    self.log_warning(f"  ✗ GeomFromText test exception: {e}")
                    break
                
                # Test 3: Full ST_Intersects test
                test_expr = f"ST_Intersects(\"{test_geom_col}\", GeomFromText('POINT(0 0)', 4326)) = 1 AND 1 = 0"
                try:
                    result = layer.setSubsetString(test_expr)
                except Exception as e:
                    self.log_debug(f"  → ST_Intersects test exception with column '{test_geom_col}': {e}")
                    result = False
                
                # Restore original subset immediately
                try:
                    layer.setSubsetString(original_subset if original_subset else "")
                except Exception:
                    pass
                
                if result:
                    self.log_info(f"  ✓ Spatialite test PASSED for {layer.name()} with column '{test_geom_col}'")
                    break
                else:
                    self.log_debug(f"  → ST_Intersects test failed with column '{test_geom_col}', trying next...")
            
            # Cache the result by layer ID (with lock for thread safety)
            with self.__class__._cache_lock:
                self.__class__._spatialite_support_cache[layer_id] = result
                
                # IMPORTANT FIX: Only cache POSITIVE results by file
                # A layer may fail the test due to missing geometry column, but other layers
                # in the same file may have geometry and support Spatialite functions.
                # Caching negative results by file would cause false negatives.
                if result and (source_path_normalized.endswith('.gpkg') or source_path_normalized.endswith('.sqlite')):
                    self.__class__._spatialite_file_cache[source_path_normalized] = True
                    self.log_info(f"✓ Spatialite support verified for file: {source_path}")
            
            if result:
                self.log_debug(f"✓ Spatialite function test PASSED for {layer.name()}")
                return True
            else:
                # Log more informatively for user troubleshooting
                provider_type = layer.providerType()
                source = layer.source()
                source_path = source.split('|')[0] if '|' in source else source
                file_ext = source_path.split('.')[-1].lower() if '.' in source_path else 'unknown'
                
                if file_ext in ('shp', 'geojson', 'json', 'kml'):
                    self.log_warning(
                        f"✗ Spatialite functions NOT supported for {layer.name()} ({file_ext}). "
                        f"Only GeoPackage (.gpkg) and SQLite (.sqlite) support Spatialite SQL. "
                        f"Using OGR backend (QGIS processing) as fallback."
                    )
                elif file_ext in ('gpkg', 'sqlite'):
                    self.log_warning(
                        f"✗ Spatialite functions unavailable for {layer.name()}. "
                        f"GDAL may not be compiled with Spatialite extension. "
                        f"Using OGR backend (QGIS processing) as fallback."
                    )
                else:
                    self.log_debug(f"✗ Spatialite function test FAILED for {layer.name()} - tried all column candidates")
                return False
                
        except Exception as e:
            self.log_error(f"✗ Spatialite function test ERROR for {layer.name()}: {e}")
            import traceback
            self.log_debug(f"Traceback: {traceback.format_exc()}")
            # IMPORTANT FIX: Only cache by layer ID, NOT by file
            # An error for one layer shouldn't affect other layers in the same file
            with self.__class__._cache_lock:
                self.__class__._spatialite_support_cache[layer_id] = False
                # Do NOT cache by file on error - other layers may work fine
            return False
    
    def _test_spatialite_functions_no_cache(self, layer: QgsVectorLayer) -> bool:
        """
        Test if Spatialite spatial functions work on this layer WITHOUT using cache.
        
        This is a lighter version of _test_spatialite_functions that:
        - Does NOT check or update the cache
        - Only tests the basic Spatialite functionality
        - Used by supports_layer() for retesting when cache has negative results
        
        Args:
            layer: Layer to test
            
        Returns:
            True if Spatialite functions work via setSubsetString, False otherwise
        """
        try:
            # Save current subset string
            original_subset = layer.subsetString()
            
            # Get geometry column name
            # v2.6.6: Use dataProvider().geometryColumn() - QgsVectorLayer doesn't have geometryColumn() directly
            try:
                geom_col = layer.dataProvider().geometryColumn()
            except (AttributeError, RuntimeError):
                geom_col = None
            
            # Check for non-geometry layers
            has_geometry = layer.geometryType() != 4  # 4 = QgsWkbTypes.NullGeometry
            if not has_geometry and not geom_col:
                self.log_debug(f"Layer {layer.name()} has no geometry - attribute-only mode")
                return True  # Non-spatial layers work fine
            
            # Build list of candidate geometry column names
            candidates = []
            if geom_col:
                candidates.append(geom_col)
            candidates.extend(['geometry', 'geom', 'GEOMETRY', 'GEOM', 'the_geom'])
            # Remove duplicates
            seen = set()
            unique_candidates = []
            for c in candidates:
                if c.lower() not in seen:
                    seen.add(c.lower())
                    unique_candidates.append(c)
            
            # Test 1: Basic subset string
            basic_test = "1 = 0"
            try:
                basic_result = layer.setSubsetString(basic_test)
                layer.setSubsetString(original_subset if original_subset else "")
                if not basic_result:
                    return False
            except Exception:
                return False
            
            # Test 2: GeomFromText and ST_Intersects
            for test_geom_col in unique_candidates:
                # Check column exists
                test_expr_simple = f"\"{test_geom_col}\" IS NOT NULL AND 1 = 0"
                try:
                    result_simple = layer.setSubsetString(test_expr_simple)
                    layer.setSubsetString(original_subset if original_subset else "")
                    if not result_simple:
                        continue
                except Exception:
                    continue
                
                # Test GeomFromText
                test_expr_geom = f"GeomFromText('POINT(0 0)', 4326) IS NOT NULL AND 1 = 0"
                try:
                    result_geom = layer.setSubsetString(test_expr_geom)
                    layer.setSubsetString(original_subset if original_subset else "")
                    if not result_geom:
                        return False  # GDAL not compiled with Spatialite
                except Exception:
                    return False
                
                # Test ST_Intersects
                test_expr = f"ST_Intersects(\"{test_geom_col}\", GeomFromText('POINT(0 0)', 4326)) = 1 AND 1 = 0"
                try:
                    result = layer.setSubsetString(test_expr)
                    layer.setSubsetString(original_subset if original_subset else "")
                    if result:
                        return True  # Success!
                except Exception:
                    pass
            
            return False
            
        except Exception as e:
            self.log_debug(f"_test_spatialite_functions_no_cache error: {e}")
            return False
    
    def _get_spatialite_db_path(self, layer: QgsVectorLayer) -> Optional[str]:
        """
        Extract database file path from Spatialite/GeoPackage layer.
        
        Supports:
        - Native Spatialite databases (.sqlite)
        - GeoPackage files (.gpkg) - which use SQLite internally
        
        Note: GDAL GeoPackage driver requires read/write access to the file.
        
        Args:
            layer: Spatialite/GeoPackage vector layer
        
        Returns:
            Database file path or None if not found or not accessible
        """
        import os
        
        try:
            source = layer.source()
            self.log_debug(f"Layer source: {source}")
            
            # Try using QgsDataSourceUri (most reliable)
            uri = QgsDataSourceUri(source)
            db_path = uri.database()
            
            if db_path and db_path.strip():
                self.log_debug(f"Database path from URI: {db_path}")
                
                # Verify file exists
                if not os.path.isfile(db_path):
                    self.log_error(f"Database file not found: {db_path}")
                    return None
                
                # Check file permissions (GDAL GeoPackage driver requires read/write)
                if not os.access(db_path, os.R_OK):
                    self.log_error(
                        f"GeoPackage/Spatialite file not readable: {db_path}. "
                        f"GDAL driver requires read access."
                    )
                    return None
                
                if not os.access(db_path, os.W_OK):
                    self.log_warning(
                        f"GeoPackage/Spatialite file not writable: {db_path}. "
                        f"GDAL driver typically requires write access even for read operations. "
                        f"This may cause issues with spatial indexes and temporary tables."
                    )
                    # Don't return None - allow read-only operation but warn
                
                return db_path
            
            # Fallback: Parse source string manually
            # Format: dbname='/path/to/file.sqlite' table="table_name"
            match = re.search(r"dbname='([^']+)'", source)
            if match:
                db_path = match.group(1)
                self.log_debug(f"Database path from regex: {db_path}")
                return db_path
            
            # Another format: /path/to/file.gpkg|layername=table_name (GeoPackage)
            # or /path/to/file.sqlite|layername=table_name
            if '|' in source:
                db_path = source.split('|')[0]
                self.log_debug(f"Database path from pipe split: {db_path}")
                return db_path
            
            self.log_warning(f"Could not extract database path from source: {source}")
            return None
            
        except Exception as e:
            self.log_error(f"Error extracting database path: {str(e)}")
            return None
    
    def _create_temp_geometry_table(
        self,
        db_path: str,
        wkt_geom: str,
        srid: int = 4326
    ) -> Tuple[Optional[str], Optional[sqlite3.Connection]]:
        """
        Create temporary table with source geometry and spatial index.
        
        ⚠️ WARNING: This optimization is DISABLED for setSubsetString!
        
        WHY DISABLED:
        - SQLite TEMP tables are connection-specific
        - QGIS uses its own connection for evaluating subset strings
        - When we create a TEMP table, QGIS cannot see it
        - Result: "no such table: _fm_temp_geom_xxx" error
        
        SOLUTION:
        - Use inline WKT with GeomFromText() for subset strings
        - This function kept for potential future use with direct SQL queries
        - Could be re-enabled for export operations (not filtering)
        
        Performance Note:
        - Inline WKT: O(n × m) where m = WKT parsing time
        - With temp table: O(1) insertion + O(log n) indexed queries
        - Trade-off: Compatibility vs Performance
        
        Args:
            db_path: Path to Spatialite database
            wkt_geom: WKT geometry string
            srid: SRID for geometry (default 4326)
        
        Returns:
            Tuple (temp_table_name, connection) or (None, None) if failed
        """
        try:
            # Generate unique temp table name based on timestamp
            timestamp = int(time.time() * 1000000)  # Microseconds
            temp_table = f"_fm_temp_geom_{timestamp}"
            
            self.log_info(f"Creating temp geometry table '{temp_table}' in {db_path}")
            
            # Connect to database
            conn = sqlite3.connect(db_path)
            conn.enable_load_extension(True)
            
            # Load spatialite extension
            try:
                conn.load_extension('mod_spatialite')
            except (AttributeError, OSError):
                try:
                    conn.load_extension('mod_spatialite.dll')  # Windows
                except Exception as ext_error:
                    self.log_error(f"Could not load spatialite extension: {ext_error}")
                    conn.close()
                    return None, None
            
            cursor = conn.cursor()
            
            # Create temp table
            cursor.execute(f"""
                CREATE TEMP TABLE {temp_table} (
                    id INTEGER PRIMARY KEY,
                    geometry GEOMETRY
                )
            """)
            self.log_debug(f"Temp table {temp_table} created")
            
            # Insert geometry
            cursor.execute(f"""
                INSERT INTO {temp_table} (id, geometry)
                VALUES (1, GeomFromText(?, ?))
            """, (wkt_geom, srid))
            
            self.log_debug(f"Geometry inserted into {temp_table}")
            
            # Create spatial index on temp table
            # Spatialite uses virtual table for spatial index
            try:
                cursor.execute(f"""
                    SELECT CreateSpatialIndex('{temp_table}', 'geometry')
                """)
                self.log_info(f"✓ Spatial index created on {temp_table}")
            except Exception as idx_error:
                self.log_warning(f"Could not create spatial index: {idx_error}. Continuing without index.")
            
            conn.commit()
            
            self.log_info(
                f"✓ Temp table '{temp_table}' created successfully with spatial index. "
                f"WKT size: {len(wkt_geom)} chars"
            )
            
            return temp_table, conn
            
        except Exception as e:
            self.log_error(f"Error creating temp geometry table: {str(e)}")
            import traceback
            self.log_debug(f"Traceback: {traceback.format_exc()}")
            if conn:
                try:
                    conn.close()
                except (AttributeError, OSError):
                    pass
            return None, None

    # v2.6.1: Threshold for using permanent source tables
    LARGE_DATASET_THRESHOLD = 10000  # Features count for permanent table strategy
    # v2.6.5: Lowered threshold for large WKT - use source table to avoid inline WKT freezing
    # Previously 100KB, now 50KB - triggers R-tree optimization more aggressively
    LARGE_WKT_THRESHOLD = 50000  # WKT chars - above this, inline SQL can freeze QGIS
    # v2.6.5/v3.0.5: Very large WKT threshold - use bounding box pre-filter for extreme cases
    # v3.0.5: PERFORMANCE FIX - Lowered from 500KB to 150KB to prevent freezes with complex
    # geometries in 150-500KB range. Bbox pre-filter adds minimal overhead but provides
    # much better safety margin for complex geometries (many vertices, holes, multi-parts).
    VERY_LARGE_WKT_THRESHOLD = 150000  # WKT chars - above this, use bbox pre-filter
    SOURCE_TABLE_PREFIX = "_fm_source_"  # Prefix for permanent source tables
    
    def _simplify_wkt_if_needed(self, wkt: str, max_points: int = None) -> str:
        """
        v2.8.7: Simplify WKT geometry using QGIS if it's too complex.
        
        This prevents GeomFromText() freezing on very complex geometries like
        detailed administrative boundaries (communes, etc.).
        
        v2.8.12: Use simplifyPreserveTopology for more robust results and
        improved tolerance calculation for better convergence.
        
        v2.9.7: CRITICAL FIX for GeometryCollection and RTTOPO errors:
        - Convert GeometryCollection to MultiPolygon (extract polygons only)
        - Reduce coordinate precision to prevent RTTOPO "Unknown Reason" errors
        - Apply makeValid() in QGIS before sending to Spatialite
        - Better handling of complex multi-part geometries
        
        Args:
            wkt: Input WKT geometry string
            max_points: Maximum number of points (default: SPATIALITE_WKT_MAX_POINTS)
        
        Returns:
            Simplified WKT string, or original if simplification not needed/failed
        """
        if max_points is None:
            max_points = SPATIALITE_WKT_MAX_POINTS
        
        # v2.9.7: Always process GeometryCollection, even if below size threshold
        # GeometryCollection causes "MakeValid error - RTTOPO reports: Unknown Reason"
        is_geometry_collection = wkt.strip().upper().startswith('GEOMETRYCOLLECTION')
        
        # v2.8.12: Always check if simplification might help, even for smaller WKT
        # Complex geometries under threshold can still cause MakeValid errors
        if len(wkt) < SPATIALITE_WKT_SIMPLIFY_THRESHOLD and not is_geometry_collection:
            return wkt
        
        try:
            from qgis.core import QgsGeometry, QgsWkbTypes
            
            geom = QgsGeometry.fromWkt(wkt)
            if geom.isNull() or geom.isEmpty():
                self.log_warning(f"Could not parse WKT for simplification ({len(wkt)} chars)")
                return wkt
            
            # v2.9.7: CRITICAL - Convert GeometryCollection to homogeneous geometry
            # RTTOPO in Spatialite cannot properly handle GeometryCollection with MakeValid()
            # v2.9.25: Improved extraction logic for GeometryCollection containing MultiPolygon
            if is_geometry_collection:
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"🔧 Converting GeometryCollection to homogeneous geometry (type: {QgsWkbTypes.displayString(geom.wkbType())})",
                    "FilterMate", Qgis.Info
                )
                
                # v2.9.26: CRITICAL FIX - If GeometryCollection contains only one part that is already
                # a valid MultiPolygon or Polygon, use it directly instead of re-collecting
                parts_list = list(geom.parts())
                
                if len(parts_list) == 1:
                    # GeometryCollection contains single element - extract it directly
                    single_part = QgsGeometry(parts_list[0].clone())
                    single_type = QgsWkbTypes.geometryType(single_part.wkbType())
                    
                    if single_type == QgsWkbTypes.PolygonGeometry:
                        # It's already a valid polygon/multipolygon - use it directly
                        geom = single_part
                        QgsMessageLog.logMessage(
                            f"  ✓ Extracted single {QgsWkbTypes.displayString(geom.wkbType())} from GeometryCollection",
                            "FilterMate", Qgis.Info
                        )
                else:
                    # Multiple parts - need to combine them
                    QgsMessageLog.logMessage(
                        f"  → GeometryCollection has {len(parts_list)} parts, combining...",
                        "FilterMate", Qgis.Info
                    )
                    
                    # Extract all polygon parts from the GeometryCollection
                    polygons = []
                    for part in parts_list:
                        part_geom = QgsGeometry(part.clone())
                        part_wkb_type = part_geom.wkbType()
                        geom_type = QgsWkbTypes.geometryType(part_wkb_type)
                        
                        if geom_type == QgsWkbTypes.PolygonGeometry:
                            # It's a polygon or multipolygon
                            if part_geom.isMultipart():
                                # v2.9.25: For MultiPolygon, extract individual polygons
                                for sub_part in part_geom.parts():
                                    sub_geom = QgsGeometry(sub_part.clone())
                                    if not sub_geom.isNull() and not sub_geom.isEmpty():
                                        polygons.append(sub_geom)
                            else:
                                polygons.append(part_geom)
                        elif QgsWkbTypes.isMultiType(part_wkb_type):
                            # v2.9.25: Handle other multi-types (MultiLineString, etc.)
                            for sub_part in part_geom.parts():
                                sub_geom = QgsGeometry(sub_part.clone())
                                if not sub_geom.isNull() and not sub_geom.isEmpty():
                                    polygons.append(sub_geom)
                    
                    QgsMessageLog.logMessage(
                        f"  → Extracted {len(polygons)} geometry parts from GeometryCollection",
                        "FilterMate", Qgis.Info
                    )
                    
                    if polygons:
                        # v2.9.25: Use unaryUnion for more robust combination
                        # collectGeometry can fail with complex geometries
                        try:
                            combined = QgsGeometry.unaryUnion(polygons)
                            if combined.isNull() or combined.isEmpty():
                                # Fallback to collectGeometry
                                combined = QgsGeometry.collectGeometry(polygons)
                        except Exception as union_err:
                            self.log_warning(f"  → unaryUnion failed: {union_err}, trying collectGeometry...")
                            combined = QgsGeometry.collectGeometry(polygons)
                        
                        if not combined.isNull() and not combined.isEmpty():
                            geom = combined
                            QgsMessageLog.logMessage(
                                f"  ✓ Combined to {QgsWkbTypes.displayString(geom.wkbType())} ({len(polygons)} parts)",
                                "FilterMate", Qgis.Info
                            )
                        else:
                            self.log_warning(f"  Could not combine polygons, using original geometry")
                    else:
                        self.log_warning(f"  No polygon parts found in GeometryCollection")
            
            # v2.8.12: Make geometry valid first to avoid issues during simplification
            if not geom.isGeosValid():
                self.log_info("  → Source geometry invalid, applying makeValid() first")
                geom = geom.makeValid()
                if geom.isNull() or geom.isEmpty():
                    self.log_warning("makeValid() produced empty geometry")
                    return wkt
            
            # Count vertices
            vertex_count = 0
            for part in geom.parts():
                vertex_count += part.vertexCount()
            
            # v2.9.7: Reduce coordinate precision to prevent RTTOPO issues
            # Coordinates with 15+ decimal places (like 169803.42999999999301508)
            # can cause parsing errors in RTTOPO
            def _reduce_precision_wkt(wkt_str: str, precision: int = 2) -> str:
                """Reduce coordinate precision in WKT string."""
                import re
                # Match floating point numbers (with optional sign)
                def round_match(match):
                    num = float(match.group(0))
                    return f"{num:.{precision}f}"
                
                # Replace all floating point numbers with reduced precision
                # Pattern matches numbers like: 153561.25, -169803.42999999999301508, etc.
                pattern = r'-?\d+\.\d+'
                return re.sub(pattern, round_match, wkt_str)
            
            if vertex_count <= max_points:
                self.log_debug(f"WKT has {vertex_count} vertices, no simplification needed")
                # v2.9.7: Return the valid geometry WKT with reduced precision
                result_wkt = geom.asWkt()
                
                # Reduce precision if WKT is still large (likely has excessive decimals)
                if len(result_wkt) > 10000:
                    old_len = len(result_wkt)
                    result_wkt = _reduce_precision_wkt(result_wkt, precision=2)
                    if len(result_wkt) < old_len:
                        self.log_info(f"  ✓ Reduced coordinate precision: {old_len:,} → {len(result_wkt):,} chars")
                
                return result_wkt
            
            self.log_info(f"🔧 Simplifying large WKT: {vertex_count:,} vertices → target {max_points:,}")
            
            # Calculate simplification tolerance based on extent
            bbox = geom.boundingBox()
            extent = max(bbox.width(), bbox.height())
            
            # v2.8.12: Better initial tolerance - start larger for faster convergence
            # Estimate tolerance needed based on vertex count ratio
            reduction_ratio = vertex_count / max_points
            tolerance = extent / 5000 * reduction_ratio  # Scale initial tolerance by needed reduction
            
            max_attempts = 12
            best_simplified = None
            best_count = vertex_count
            
            for attempt in range(max_attempts):
                # v2.8.12: Use simplifyPreserveTopology for more robust results
                # This maintains the topology (no self-intersections) better than simplify()
                simplified = geom.simplify(tolerance)
                
                if simplified.isNull() or simplified.isEmpty():
                    self.log_debug(f"  Attempt {attempt+1}: tolerance {tolerance:.6f} produced empty geometry")
                    tolerance /= 2  # Reduce tolerance
                    continue
                
                # Count simplified vertices
                simplified_count = 0
                for part in simplified.parts():
                    simplified_count += part.vertexCount()
                
                # Track best result
                if simplified_count < best_count:
                    best_simplified = simplified
                    best_count = simplified_count
                
                if simplified_count <= max_points:
                    result_wkt = simplified.asWkt()
                    
                    # v2.9.7: Reduce precision for large WKT
                    if len(result_wkt) > 10000:
                        old_len = len(result_wkt)
                        result_wkt = _reduce_precision_wkt(result_wkt, precision=2)
                        if len(result_wkt) < old_len:
                            self.log_info(f"  ✓ Reduced coordinate precision: {old_len:,} → {len(result_wkt):,} chars")
                    
                    self.log_info(f"  ✓ Simplified: {vertex_count:,} → {simplified_count:,} vertices (tolerance: {tolerance:.4f})")
                    self.log_info(f"  ✓ WKT size: {len(wkt):,} → {len(result_wkt):,} chars")
                    return result_wkt
                
                # v2.8.12: Smarter tolerance adjustment based on current count vs target
                current_ratio = simplified_count / max_points
                if current_ratio > 2:
                    tolerance *= 2.5  # Need aggressive increase
                elif current_ratio > 1.5:
                    tolerance *= 1.8
                else:
                    tolerance *= 1.5  # Getting close
            
            # If we couldn't simplify enough, use the best version we found
            if best_simplified and not best_simplified.isNull() and not best_simplified.isEmpty():
                result_wkt = best_simplified.asWkt()
                
                # v2.9.7: Reduce precision for large WKT
                if len(result_wkt) > 10000:
                    old_len = len(result_wkt)
                    result_wkt = _reduce_precision_wkt(result_wkt, precision=2)
                    if len(result_wkt) < old_len:
                        self.log_info(f"  ✓ Reduced coordinate precision: {old_len:,} → {len(result_wkt):,} chars")
                
                self.log_warning(f"Could not simplify to {max_points:,} vertices, using best result: {best_count:,} vertices")
                self.log_info(f"  → WKT size: {len(wkt):,} → {len(result_wkt):,} chars")
                return result_wkt
            
            self.log_warning("Simplification failed, using original WKT")
            return wkt
            
        except Exception as e:
            self.log_warning(f"WKT simplification error: {e}")
            import traceback
            self.log_debug(f"Simplification traceback: {traceback.format_exc()}")
            return wkt
    
    def _extract_wkt_from_expression(self, expression: str) -> Optional[str]:
        """
        v2.6.5: Extract WKT string from a Spatialite expression as fallback.
        
        Parses expressions like:
            ST_Intersects(GeomFromGPB("geom"), GeomFromText('MULTILINESTRING(...)', 2154))
        
        Args:
            expression: Spatialite SQL expression containing GeomFromText
        
        Returns:
            WKT string if found, None otherwise
        """
        import re
        
        # Pattern to match GeomFromText('...WKT...', SRID) - handles escaped quotes
        pattern = r"GeomFromText\s*\(\s*'((?:[^']|'')+)'\s*,\s*\d+\s*\)"
        
        match = re.search(pattern, expression, re.IGNORECASE | re.DOTALL)
        if match:
            wkt = match.group(1)
            # Unescape SQL single quotes
            wkt = wkt.replace("''", "'")
            return wkt
        
        return None
    
    def _create_permanent_source_table(
        self,
        db_path: str,
        source_wkt: str,
        source_srid: int,
        buffer_value: float = 0,
        source_features: Optional[List] = None
    ) -> Tuple[Optional[str], bool]:
        """
        v2.6.1: Create a PERMANENT source geometry table with R-tree spatial index.
        
        Unlike TEMP tables, permanent tables are visible to QGIS's connection.
        This enables optimized spatial queries using R-tree indexes.
        
        Used when:
        - Source has multiple features (multi-selection filter)
        - Large target dataset (> LARGE_DATASET_THRESHOLD features)
        - Buffered geometric filters (avoid recomputing buffer)
        
        Performance benefits:
        - R-tree spatial index: O(log n) spatial lookups vs O(n) for inline WKT
        - Pre-computed buffers: avoid N * M buffer calculations
        - Persistent across QGIS connections: works with setSubsetString
        
        Cleanup:
        - Tables are automatically cleaned up in cleanup() method
        - Tables have timestamp in name for identification
        - cleanup_old_source_tables() removes stale tables
        
        Args:
            db_path: Path to GeoPackage/Spatialite database
            source_wkt: WKT geometry (single geometry or GEOMETRYCOLLECTION)
            source_srid: SRID of source geometry
            buffer_value: Optional buffer distance (0 = no buffer)
            source_features: Optional list of (fid, wkt) tuples for multi-feature sources
        
        Returns:
            Tuple (table_name, has_buffer) or (None, False) if failed
        """
        conn = None
        try:
            import uuid
            timestamp = int(time.time())
            table_name = f"{self.SOURCE_TABLE_PREFIX}{timestamp}_{uuid.uuid4().hex[:6]}"
            
            self.log_info(f"📦 Creating permanent source table '{table_name}' in {os.path.basename(db_path)}")
            
            # Get mod_spatialite extension
            mod_available, ext_name = _test_mod_spatialite_available()
            if not mod_available:
                self.log_warning("mod_spatialite not available - cannot create permanent source table")
                return None, False
            
            # v2.8.7: Connect with check_same_thread=False to allow InterruptibleSQLiteQuery
            # to execute in background thread for timeout/cancellation support
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.enable_load_extension(True)
            conn.load_extension(ext_name)
            cursor = conn.cursor()
            
            # Determine if we need buffered geometry column
            # v2.8.10: FIX - Include negative buffers (erosion) as well as positive buffers
            # Negative buffers need MakeValid() to handle potential invalid/empty geometries
            has_buffer = buffer_value != 0
            is_negative_buffer = buffer_value < 0
            
            # Create table with geometry column(s)
            if has_buffer:
                cursor.execute(f'''
                    CREATE TABLE "{table_name}" (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_fid INTEGER,
                        geom GEOMETRY,
                        geom_buffered GEOMETRY
                    )
                ''')
                self.log_info(f"  → Table created with geom + geom_buffered columns")
            else:
                cursor.execute(f'''
                    CREATE TABLE "{table_name}" (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_fid INTEGER,
                        geom GEOMETRY
                    )
                ''')
                self.log_info(f"  → Table created with geom column")
            
            # Insert geometries
            inserted_count = 0
            
            # v2.6.10: DISABLED - ST_Simplify in Spatialite was producing invalid/empty geometry
            # that caused 0 features matched. Rely on Python-side simplification instead.
            # The improved tolerance scaling in filter_task.py should handle large WKT now.
            # 
            # If Python simplification isn't aggressive enough, the OGR fallback will be triggered
            # when 0 features are matched on a large dataset.
            needs_spatialite_simplify = False  # Disabled - use Python simplification only
            # LARGE_WKT_THRESHOLD_SIMPLIFY = 500000  # 500KB
            # needs_spatialite_simplify = len(source_wkt) > LARGE_WKT_THRESHOLD_SIMPLIFY
            # simplify_tolerance = 10.0  # 10 meters
            
            # v2.8.7: CRITICAL FIX - Simplify WKT BEFORE sending to Spatialite to prevent freeze
            # GeomFromText on complex geometries (like detailed commune boundaries) can block indefinitely
            # Python simplification is done BEFORE SQLite call, making it interruptible
            
            if source_features and len(source_features) > 0:
                # Multi-feature source (from selection or filtered layer)
                for fid, wkt in source_features:
                    # v2.8.7: Simplify large WKT in Python to prevent GeomFromText freeze
                    simplified_wkt = self._simplify_wkt_if_needed(wkt)
                    
                    if has_buffer:
                        # v2.8.10: Use MakeValid for negative buffers to handle invalid/empty geometries
                        if is_negative_buffer:
                            buffer_expr = f"MakeValid(ST_Buffer(GeomFromText('{simplified_wkt.replace(chr(39), chr(39)+chr(39))}', {source_srid}), {buffer_value}))"
                        else:
                            buffer_expr = f"ST_Buffer(GeomFromText('{simplified_wkt.replace(chr(39), chr(39)+chr(39))}', {source_srid}), {buffer_value})"
                        
                        if needs_spatialite_simplify:
                            # v2.8.11: CRITICAL FIX - Apply MakeValid() to source geometry too
                            # Source geometries from GeoPackage can be invalid, causing 0 results
                            if is_negative_buffer:
                                cursor.execute(f'''
                                    INSERT INTO "{table_name}" (source_fid, geom, geom_buffered)
                                    VALUES (?, MakeValid(ST_Simplify(GeomFromText(?, ?), ?)), MakeValid(ST_Buffer(ST_Simplify(GeomFromText(?, ?), ?), ?)))
                                ''', (fid, simplified_wkt, source_srid, simplify_tolerance, simplified_wkt, source_srid, simplify_tolerance, buffer_value))
                            else:
                                cursor.execute(f'''
                                    INSERT INTO "{table_name}" (source_fid, geom, geom_buffered)
                                    VALUES (?, MakeValid(ST_Simplify(GeomFromText(?, ?), ?)), ST_Buffer(MakeValid(ST_Simplify(GeomFromText(?, ?), ?)), ?))
                                ''', (fid, simplified_wkt, source_srid, simplify_tolerance, simplified_wkt, source_srid, simplify_tolerance, buffer_value))
                        else:
                            # v2.8.7: Use interruptible insert for geometry
                            # v2.8.10: Use MakeValid for negative buffer to handle invalid geometries
                            # v2.8.11: CRITICAL FIX - Apply MakeValid() to source geometry too
                            # Source geometries from GeoPackage can be invalid, causing 0 results
                            if is_negative_buffer:
                                insert_sql = f'''
                                    INSERT INTO "{table_name}" (source_fid, geom, geom_buffered)
                                    VALUES ({fid}, MakeValid(GeomFromText('{simplified_wkt.replace("'", "''")}', {source_srid})), 
                                            MakeValid(ST_Buffer(GeomFromText('{simplified_wkt.replace("'", "''")}', {source_srid}), {buffer_value})))
                                '''
                            else:
                                insert_sql = f'''
                                    INSERT INTO "{table_name}" (source_fid, geom, geom_buffered)
                                    VALUES ({fid}, MakeValid(GeomFromText('{simplified_wkt.replace("'", "''")}', {source_srid})), 
                                            ST_Buffer(MakeValid(GeomFromText('{simplified_wkt.replace("'", "''")}', {source_srid})), {buffer_value}))
                                '''
                            interruptible = InterruptibleSQLiteQuery(conn, insert_sql)
                            _, error = interruptible.execute(
                                timeout=SPATIALITE_GEOM_INSERT_TIMEOUT,
                                cancel_check=self._is_task_canceled
                            )
                            if error:
                                self.log_error(f"Geometry insert timeout/error: {error}")
                                raise Exception(f"Geometry insert failed: {error}")
                    else:
                        # v2.8.11: CRITICAL FIX - Apply MakeValid() to source geometry
                        if needs_spatialite_simplify:
                            cursor.execute(f'''
                                INSERT INTO "{table_name}" (source_fid, geom)
                                VALUES (?, MakeValid(ST_Simplify(GeomFromText(?, ?), ?)))
                            ''', (fid, simplified_wkt, source_srid, simplify_tolerance))
                        else:
                            # v2.8.7: Use interruptible insert for geometry
                            # v2.8.11: Apply MakeValid() to ensure valid geometry
                            insert_sql = f'''
                                INSERT INTO "{table_name}" (source_fid, geom)
                                VALUES ({fid}, MakeValid(GeomFromText('{simplified_wkt.replace("'", "''")}', {source_srid})))
                            '''
                            interruptible = InterruptibleSQLiteQuery(conn, insert_sql)
                            _, error = interruptible.execute(
                                timeout=SPATIALITE_GEOM_INSERT_TIMEOUT,
                                cancel_check=self._is_task_canceled
                            )
                            if error:
                                self.log_error(f"Geometry insert timeout/error: {error}")
                                raise Exception(f"Geometry insert failed: {error}")
                    inserted_count += 1
            else:
                # Single geometry source
                # v2.8.7: Simplify large WKT in Python to prevent GeomFromText freeze
                simplified_wkt = self._simplify_wkt_if_needed(source_wkt)
                
                if has_buffer:
                    # v2.8.10: Use MakeValid for negative buffers to handle invalid/empty geometries
                    # v2.8.11: CRITICAL FIX - Apply MakeValid() to source geometry too
                    if needs_spatialite_simplify:
                        if is_negative_buffer:
                            cursor.execute(f'''
                                INSERT INTO "{table_name}" (source_fid, geom, geom_buffered)
                                VALUES (0, MakeValid(ST_Simplify(GeomFromText(?, ?), ?)), MakeValid(ST_Buffer(ST_Simplify(GeomFromText(?, ?), ?), ?)))
                            ''', (simplified_wkt, source_srid, simplify_tolerance, simplified_wkt, source_srid, simplify_tolerance, buffer_value))
                        else:
                            cursor.execute(f'''
                                INSERT INTO "{table_name}" (source_fid, geom, geom_buffered)
                                VALUES (0, MakeValid(ST_Simplify(GeomFromText(?, ?), ?)), ST_Buffer(MakeValid(ST_Simplify(GeomFromText(?, ?), ?)), ?))
                            ''', (simplified_wkt, source_srid, simplify_tolerance, simplified_wkt, source_srid, simplify_tolerance, buffer_value))
                    else:
                        # v2.8.7: Use interruptible insert with timeout for large geometries
                        # v2.8.10: Use MakeValid for negative buffer to handle invalid geometries
                        # v2.8.11: CRITICAL FIX - Apply MakeValid() to source geometry too
                        if is_negative_buffer:
                            insert_sql = f'''
                                INSERT INTO "{table_name}" (source_fid, geom, geom_buffered)
                                VALUES (0, MakeValid(GeomFromText('{simplified_wkt.replace("'", "''")}', {source_srid})), 
                                        MakeValid(ST_Buffer(GeomFromText('{simplified_wkt.replace("'", "''")}', {source_srid}), {buffer_value})))
                            '''
                        else:
                            insert_sql = f'''
                                INSERT INTO "{table_name}" (source_fid, geom, geom_buffered)
                                VALUES (0, MakeValid(GeomFromText('{simplified_wkt.replace("'", "''")}', {source_srid})), 
                                        ST_Buffer(MakeValid(GeomFromText('{simplified_wkt.replace("'", "''")}', {source_srid})), {buffer_value}))
                            '''
                        self.log_info(f"  → Inserting geometry with {SPATIALITE_GEOM_INSERT_TIMEOUT}s timeout...")
                        interruptible = InterruptibleSQLiteQuery(conn, insert_sql)
                        _, error = interruptible.execute(
                            timeout=SPATIALITE_GEOM_INSERT_TIMEOUT,
                            cancel_check=self._is_task_canceled
                        )
                        if error:
                            error_msg = str(error)
                            # v2.9.28: Detect RTTOPO errors for better fallback handling
                            if "makevalid" in error_msg.lower() or "rttopo" in error_msg.lower():
                                self.log_warning(f"Spatialite RTTOPO error - geometry too complex for MakeValid()")
                                self.log_info(f"  → Error: {error_msg}")
                                self.log_info(f"  → Will abort source table and trigger OGR fallback")
                                raise Exception(f"RTTOPO error: {error_msg}")
                            elif "timeout" in error_msg.lower():
                                self.log_error(f"Geometry insert timeout after {SPATIALITE_GEOM_INSERT_TIMEOUT}s - geometry too complex")
                                from qgis.core import QgsMessageLog, Qgis
                                QgsMessageLog.logMessage(
                                    f"GeomFromText timeout - geometry too complex ({len(simplified_wkt):,} chars). Try OGR backend.",
                                    "FilterMate", Qgis.Warning
                                )
                            elif "cancelled" in error_msg.lower():
                                self.log_info("Geometry insert cancelled by user")
                            else:
                                self.log_error(f"Geometry insert error: {error}")
                            raise Exception(f"Geometry insert failed: {error}")
                else:
                    # v2.8.11: CRITICAL FIX - Apply MakeValid() to source geometry
                    if needs_spatialite_simplify:
                        cursor.execute(f'''
                            INSERT INTO "{table_name}" (source_fid, geom)
                            VALUES (0, MakeValid(ST_Simplify(GeomFromText(?, ?), ?)))
                        ''', (simplified_wkt, source_srid, simplify_tolerance))
                    else:
                        # v2.8.7: Use interruptible insert with timeout for large geometries
                        # v2.8.11: Apply MakeValid() to ensure valid geometry
                        insert_sql = f'''
                            INSERT INTO "{table_name}" (source_fid, geom)
                            VALUES (0, MakeValid(GeomFromText('{simplified_wkt.replace("'", "''")}', {source_srid})))
                        '''
                        self.log_info(f"  → Inserting geometry with {SPATIALITE_GEOM_INSERT_TIMEOUT}s timeout...")
                        interruptible = InterruptibleSQLiteQuery(conn, insert_sql)
                        _, error = interruptible.execute(
                            timeout=SPATIALITE_GEOM_INSERT_TIMEOUT,
                            cancel_check=self._is_task_canceled
                        )
                        if error:
                            error_msg = str(error)
                            # v2.9.28: Detect RTTOPO errors for better fallback handling  
                            if "makevalid" in error_msg.lower() or "rttopo" in error_msg.lower():
                                self.log_warning(f"Spatialite RTTOPO error - geometry too complex for MakeValid()")
                                self.log_info(f"  → Error: {error_msg}")
                                self.log_info(f"  → Will abort source table and trigger OGR fallback")
                                raise Exception(f"RTTOPO error: {error_msg}")
                            elif "timeout" in error_msg.lower():
                                self.log_error(f"Geometry insert timeout after {SPATIALITE_GEOM_INSERT_TIMEOUT}s - geometry too complex")
                                from qgis.core import QgsMessageLog, Qgis
                                QgsMessageLog.logMessage(
                                    f"GeomFromText timeout - geometry too complex ({len(simplified_wkt):,} chars). Try OGR backend.",
                                    "FilterMate", Qgis.Warning
                                )
                            elif "cancelled" in error_msg.lower():
                                self.log_info("Geometry insert cancelled by user")
                            else:
                                self.log_error(f"Geometry insert error: {error}")
                            raise Exception(f"Geometry insert failed: {error}")
                inserted_count = 1
            
            conn.commit()
            self.log_info(f"  → Inserted {inserted_count} source geometries")
            
            # v2.6.6: CRITICAL - Validate that geometry was actually inserted (not NULL)
            # Large WKT strings (>500KB) can cause GeomFromText to fail silently, returning NULL
            cursor.execute(f'SELECT COUNT(*) FROM "{table_name}" WHERE geom IS NOT NULL')
            valid_geom_count = cursor.fetchone()[0]
            
            if valid_geom_count == 0:
                from qgis.core import QgsMessageLog, Qgis
                error_msg = f"Source geometry is NULL after insertion (WKT too large: {len(source_wkt):,} chars)"
                self.log_error(error_msg)
                QgsMessageLog.logMessage(
                    f"_create_permanent_source_table FAILED: {error_msg}",
                    "FilterMate", Qgis.Warning
                )
                # Clean up the empty table
                cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
                conn.commit()
                conn.close()
                return None, False
            
            self.log_info(f"  ✓ Validated {valid_geom_count} non-NULL geometries")
            
            # Create R-tree spatial index on geom column
            try:
                cursor.execute(f'SELECT CreateSpatialIndex("{table_name}", "geom")')
                conn.commit()
                self.log_info(f"  → R-tree spatial index created on geom")
            except Exception as idx_err:
                self.log_warning(f"Could not create spatial index on geom: {idx_err}")
            
            # Create R-tree on buffered geom if applicable
            if has_buffer:
                try:
                    cursor.execute(f'SELECT CreateSpatialIndex("{table_name}", "geom_buffered")')
                    conn.commit()
                    self.log_info(f"  → R-tree spatial index created on geom_buffered")
                except Exception as idx_err:
                    self.log_warning(f"Could not create spatial index on geom_buffered: {idx_err}")
            
            # Store table name for cleanup
            self._permanent_source_table = table_name
            self._permanent_source_db_path = db_path
            
            conn.close()
            
            self.log_info(f"✓ Permanent source table '{table_name}' ready with {inserted_count} geometries")
            if has_buffer:
                self.log_info(f"  → Pre-computed buffer: {buffer_value}m")
            
            return table_name, has_buffer
            
        except Exception as e:
            self.log_error(f"Error creating permanent source table: {e}")
            import traceback
            self.log_debug(f"Traceback: {traceback.format_exc()}")

            # FIX v3.0.12: Clean up partially created table on failure
            # If CREATE TABLE succeeded but subsequent operations failed (insert, index creation, etc.),
            # we need to remove the orphaned table to prevent database bloat
            from .base_backend import TemporaryTableManager
            cleanup_manager = TemporaryTableManager(db_path, table_name, logger=self.logger)
            cleanup_manager.mark_created()  # Mark as created to enable cleanup
            cleanup_manager._cleanup()  # Immediate cleanup
            self.log_info(f"  → Cleaned up partially created table '{table_name}' after error")

            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            return None, False
    
    def _cleanup_permanent_source_tables(self, db_path: str, max_age_seconds: int = 3600):
        """
        v2.6.1: Clean up old permanent source tables from the database.
        
        Removes tables with _fm_source_ prefix that are older than max_age_seconds.
        This prevents accumulation of temporary tables in user databases.
        
        Args:
            db_path: Path to GeoPackage/Spatialite database
            max_age_seconds: Maximum age in seconds (default 1 hour)
        """
        conn = None
        try:
            if not os.path.isfile(db_path):
                return
            
            mod_available, ext_name = _test_mod_spatialite_available()
            if not mod_available:
                return
            
            conn = sqlite3.connect(db_path)
            conn.enable_load_extension(True)
            conn.load_extension(ext_name)
            cursor = conn.cursor()
            
            # Find all FilterMate source tables
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name LIKE '_fm_source_%'
            """)
            tables = cursor.fetchall()
            
            current_time = int(time.time())
            cleaned_count = 0
            
            for (table_name,) in tables:
                try:
                    # Extract timestamp from table name: _fm_source_TIMESTAMP_UUID
                    parts = table_name.split('_')
                    if len(parts) >= 4:
                        table_timestamp = int(parts[3])
                        age = current_time - table_timestamp
                        
                        if age > max_age_seconds:
                            # Drop the R-tree index first
                            try:
                                cursor.execute(f'SELECT DisableSpatialIndex("{table_name}", "geom")')
                            except Exception:
                                pass
                            try:
                                cursor.execute(f'SELECT DisableSpatialIndex("{table_name}", "geom_buffered")')
                            except Exception:
                                pass
                            
                            # Drop the table
                            cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
                            cleaned_count += 1
                            self.log_debug(f"Cleaned up old source table: {table_name} (age: {age}s)")
                except Exception as parse_err:
                    self.log_debug(f"Could not parse table name {table_name}: {parse_err}")
            
            conn.commit()
            conn.close()
            
            if cleaned_count > 0:
                self.log_info(f"🧹 Cleaned up {cleaned_count} old source table(s) from {os.path.basename(db_path)}")
            
        except Exception as e:
            self.log_debug(f"Error during source table cleanup: {e}")
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
    
    def cleanup(self):
        """
        Clean up temporary table and close connection.
        
        Should be called after filtering is complete.
        """
        if self._temp_table_name and self._temp_table_conn:
            try:
                self.log_debug(f"Cleaning up temp table {self._temp_table_name}")
                cursor = self._temp_table_conn.cursor()
                cursor.execute(f"DROP TABLE IF EXISTS {self._temp_table_name}")
                self._temp_table_conn.commit()
                self._temp_table_conn.close()
                self.log_info(f"✓ Temp table {self._temp_table_name} cleaned up")
            except Exception as e:
                self.log_warning(f"Error cleaning up temp table: {str(e)}")
            finally:
                self._temp_table_name = None
                self._temp_table_conn = None
        
        # v2.8.7: Clean up FID tables created for large result sets
        self._cleanup_fid_tables()
    
    def build_expression(
        self,
        layer_props: Dict,
        predicates: Dict,
        source_geom: Optional[str] = None,
        buffer_value: Optional[float] = None,
        buffer_expression: Optional[str] = None,
        source_filter: Optional[str] = None,
        use_centroids: bool = False,
        **kwargs
    ) -> str:
        """
        Build Spatialite filter expression.
        
        OPTIMIZATION: Uses temporary table with spatial index instead of inline WKT
        for massive performance improvement on medium-large datasets.
        
        Performance:
        - Without temp table: O(n × m) where m = WKT parsing overhead
        - With temp table: O(n log n) with spatial index
        - Gain: 10× on 5k features, 50× on 20k features
        
        Args:
            layer_props: Layer properties
            predicates: Spatial predicates to apply
            source_geom: Source geometry (WKT string)
            buffer_value: Buffer distance
            buffer_expression: Expression for dynamic buffer
            source_filter: Source layer filter (not used in Spatialite)
            use_centroids: If True, use ST_Centroid() on distant layer geometries for faster queries
        
        Returns:
            Spatialite SQL expression string
        """
        self.log_debug(f"Building Spatialite expression for {layer_props.get('layer_name', 'unknown')}")
        
        # Extract layer properties
        # Use layer_table_name (actual source table) if available, fallback to layer_name (display name)
        table = layer_props.get("layer_table_name") or layer_props.get("layer_name")
        geom_field = layer_props.get("layer_geometry_field", "geom")
        primary_key = layer_props.get("primary_key_name")
        layer = layer_props.get("layer")  # QgsVectorLayer instance
        
        # CRITICAL FIX: Get actual geometry column name from layer's data source
        # Use QGIS APIs in the safest order to avoid bad guesses that break subset strings
        # FIX v2.4.13: Only use fallback methods if previous method returned nothing
        detected_geom_field = None
        if layer:
            try:
                # METHOD 0: Directly ask the layer via dataProvider (most reliable and cheap)
                # v2.6.6: Use dataProvider().geometryColumn() - QgsVectorLayer doesn't have geometryColumn() directly
                try:
                    geom_col_from_layer = layer.dataProvider().geometryColumn()
                except (AttributeError, RuntimeError):
                    geom_col_from_layer = None
                if geom_col_from_layer and geom_col_from_layer.strip():
                    detected_geom_field = geom_col_from_layer
                    self.log_debug(f"Geometry column from dataProvider().geometryColumn(): '{detected_geom_field}'")
                
                # METHOD 1: QGIS provider URI parsing (only if METHOD 0 failed)
                if not detected_geom_field:
                    provider = layer.dataProvider()
                    from qgis.core import QgsDataSourceUri
                    uri_string = provider.dataSourceUri()
                    uri_obj = QgsDataSourceUri(uri_string)
                    uri_geom_col = uri_obj.geometryColumn()
                    if uri_geom_col and uri_geom_col.strip():
                        detected_geom_field = uri_geom_col
                        self.log_debug(f"Geometry column from URI: '{detected_geom_field}'")
                    else:
                        # METHOD 2: Manual URI inspection (only if METHOD 1 failed)
                        if '|' in uri_string:
                            parts = uri_string.split('|')
                            for part in parts:
                                if part.startswith('geometryname='):
                                    detected_geom_field = part.split('=')[1]
                                    self.log_debug(f"Geometry column from URI part: '{detected_geom_field}'")
                                    break
                
                # METHOD 3: Query database metadata as last resort (only if previous methods failed)
                if not detected_geom_field:
                    db_path = self._get_spatialite_db_path(layer)
                    
                    if db_path:
                        # FIX v3.1.1: Use global sqlite3 import (line 40) instead of local import
                        try:
                            conn = sqlite3.connect(db_path)
                            cursor = conn.cursor()
                            
                            # Extract actual table name from URI (without layer name prefix)
                            from qgis.core import QgsDataSourceUri
                            provider = layer.dataProvider()
                            uri_string = provider.dataSourceUri()
                            uri_obj = QgsDataSourceUri(uri_string)
                            actual_table = uri_obj.table()
                            if not actual_table:
                                # Fallback: extract from URI string
                                for part in uri_string.split('|'):
                                    if part.startswith('layername='):
                                        actual_table = part.split('=')[1]
                                        break
                            
                            if actual_table:
                                # Query GeoPackage geometry_columns table
                                cursor.execute(
                                    "SELECT column_name FROM gpkg_geometry_columns WHERE table_name = ?",
                                    (actual_table,)
                                )
                                result = cursor.fetchone()
                                if result and result[0]:
                                    detected_geom_field = result[0]
                                    self.log_debug(f"Geometry column from gpkg_geometry_columns: '{detected_geom_field}'")
                            
                            conn.close()
                        except Exception as e:
                            self.log_warning(f"Database query error: {e}")
                
                # Apply detected geometry field
                if detected_geom_field:
                    geom_field = detected_geom_field
                    self.log_info(f"✓ Detected geometry column: '{geom_field}'")
                else:
                    self.log_warning(f"Could not detect geometry column, using default: '{geom_field}'")
                    
            except Exception as e:
                self.log_warning(f"Error detecting geometry column name: {e}")
        
        # Source geometry should be WKT string from prepare_spatialite_source_geom
        if not source_geom:
            # v2.8.2 FIX: Return "0 features" filter instead of empty string
            self.log_error("No source geometry provided for Spatialite filter")
            self.log_warning("  → v2.8.2: Returning '0 features' filter instead of empty expression")
            return "1 = 0"  # Universal FALSE condition
        
        if not isinstance(source_geom, str):
            # v2.8.2 FIX: Return "0 features" filter instead of empty string
            self.log_error(f"Invalid source geometry type for Spatialite: {type(source_geom)}")
            self.log_warning("  → v2.8.2: Returning '0 features' filter instead of empty expression")
            return "1 = 0"  # Universal FALSE condition
        
        wkt_length = len(source_geom)
        self.log_debug(f"Source WKT length: {wkt_length} chars")
        
        # v2.9.26: CRITICAL - Always simplify GeometryCollection to avoid RTTOPO MakeValid errors
        # Check for GeometryCollection BEFORE the size threshold check
        is_geometry_collection = source_geom.strip().upper().startswith('GEOMETRYCOLLECTION')
        if is_geometry_collection:
            from qgis.core import QgsMessageLog, Qgis
            QgsMessageLog.logMessage(
                f"🔧 GeometryCollection detected ({wkt_length} chars) - converting before SQL",
                "FilterMate", Qgis.Info
            )
            simplified_wkt = self._simplify_wkt_if_needed(source_geom)
            # v2.9.26: Check if WKT type changed, not just if content changed
            simplified_is_gc = simplified_wkt.strip().upper().startswith('GEOMETRYCOLLECTION')
            if simplified_wkt != source_geom or not simplified_is_gc:
                old_len = wkt_length
                old_type = "GeometryCollection"
                source_geom = simplified_wkt
                wkt_length = len(source_geom)
                new_type = simplified_wkt.split('(')[0].strip() if '(' in simplified_wkt else "Unknown"
                QgsMessageLog.logMessage(
                    f"  ✓ Converted: {old_type}({old_len:,} chars) → {new_type}({wkt_length:,} chars)",
                    "FilterMate", Qgis.Info
                )
            else:
                QgsMessageLog.logMessage(
                    f"  ⚠️ Conversion failed - still GeometryCollection ({wkt_length} chars)",
                    "FilterMate", Qgis.Warning
                )
                # v2.9.27: GeometryCollection causes RTTOPO MakeValid errors
                # Force OGR fallback instead of attempting SQL with MakeValid
                QgsMessageLog.logMessage(
                    f"  → v2.9.27: Returning USE_OGR_FALLBACK to avoid RTTOPO error",
                    "FilterMate", Qgis.Info
                )
                return USE_OGR_FALLBACK
        
        # v2.8.12: Apply WKT simplification BEFORE building SQL expression
        # This prevents MakeValid errors on complex geometries (e.g., detailed commune boundaries)
        elif wkt_length >= SPATIALITE_WKT_SIMPLIFY_THRESHOLD:
            self.log_info(f"🔧 Large WKT detected ({wkt_length:,} chars) - applying simplification before SQL")
            simplified_wkt = self._simplify_wkt_if_needed(source_geom)
            if simplified_wkt != source_geom:
                old_len = wkt_length
                source_geom = simplified_wkt
                wkt_length = len(source_geom)
                self.log_info(f"  ✓ WKT simplified: {old_len:,} → {wkt_length:,} chars")
        
        # DIAGNOSTIC v2.4.10: Log WKT preview and bounding box
        from qgis.core import QgsMessageLog, Qgis, QgsGeometry
        wkt_preview = source_geom[:250] if len(source_geom) > 250 else source_geom
        QgsMessageLog.logMessage(
            f"Spatialite build_expression WKT ({wkt_length} chars): {wkt_preview}...",
            "FilterMate", Qgis.Info
        )
        # Try to calculate bounding box of source geometry
        try:
            temp_geom = QgsGeometry.fromWkt(source_geom.replace("''", "'"))
            if temp_geom and not temp_geom.isEmpty():
                bbox = temp_geom.boundingBox()
                QgsMessageLog.logMessage(
                    f"  Source geometry bbox: ({bbox.xMinimum():.1f},{bbox.yMinimum():.1f})-({bbox.xMaximum():.1f},{bbox.yMaximum():.1f})",
                    "FilterMate", Qgis.Info
                )
        except Exception as e:
            QgsMessageLog.logMessage(f"  Could not parse WKT bbox: {e}", "FilterMate", Qgis.Warning)
        
        # Build geometry expression for target layer
        # CRITICAL FIX v2.4.12/v2.4.13: GeoPackage stores geometries in GPB (GeoPackage Binary) format
        # We MUST use GeomFromGPB() to convert GPB to Spatialite geometry before spatial predicates
        # NOTE: The function is GeomFromGPB() NOT ST_GeomFromGPB() (ST_ version doesn't exist!)
        # Without this conversion, ST_Intersects returns TRUE for ALL features!
        geom_expr = f'"{geom_field}"'
        
        # Check if we need table prefix (usually not needed for subset strings)
        if table and '.' in str(table):
            geom_expr = f'"{table}"."{geom_field}"'
        
        # Detect if this is a GeoPackage layer (needs GPB conversion)
        is_geopackage = False
        if layer:
            source = layer.source().lower()
            is_geopackage = '.gpkg' in source or 'gpkg|' in source
        
        # Apply GPB conversion for GeoPackage layers
        # CRITICAL v2.4.13: Use GeomFromGPB() NOT ST_GeomFromGPB()
        # The SpatiaLite function is GeomFromGPB() (without ST_ prefix)
        # Alternatively, CastAutomagic() auto-detects GPB or standard WKB
        if is_geopackage:
            geom_expr = f'GeomFromGPB({geom_expr})'
            self.log_info(f"GeoPackage detected: using GeomFromGPB() for geometry conversion")
        
        # CENTROID OPTIMIZATION v2.9.2: Convert distant layer geometry to point if enabled
        # This significantly speeds up queries for complex polygons (e.g., buildings)
        # v2.9.2: Use ST_PointOnSurface() instead of ST_Centroid() for polygons
        # ST_PointOnSurface() guarantees the point is INSIDE the polygon (better for concave shapes)
        # ST_Centroid() may return a point OUTSIDE concave polygons (L-shapes, rings, etc.)
        # Note: Spatialite supports both functions since version 4.0
        if use_centroids:
            # Get centroid mode from class attribute or config
            centroid_mode = getattr(self, 'CENTROID_MODE', 'point_on_surface')
            geometry_type = layer_props.get("layer_geometry_type", None)
            
            # v3.0.7: CRITICAL FIX - ST_PointOnSurface() returns NULL on line geometries in Spatialite
            # Always check geometry type before applying centroid functions
            # - Polygons: Use ST_PointOnSurface() (guaranteed point inside)
            # - Lines/Points: Use ST_Centroid() (works correctly on all geometry types)
            from qgis.core import QgsWkbTypes
            is_polygon = geometry_type in (QgsWkbTypes.PolygonGeometry, 2) if geometry_type is not None else False
            is_line = geometry_type in (QgsWkbTypes.LineGeometry, 1) if geometry_type is not None else False
            
            if centroid_mode == 'auto':
                # Auto mode: Use PointOnSurface for polygons, Centroid for lines
                if is_polygon:
                    geom_expr = f"ST_PointOnSurface({geom_expr})"
                    self.log_info(f"✓ Spatialite: Using ST_PointOnSurface for polygon layer (guaranteed inside)")
                elif is_line:
                    geom_expr = f"ST_Centroid({geom_expr})"
                    self.log_info(f"✓ Spatialite: Using ST_Centroid for line layer (ST_PointOnSurface returns NULL on lines)")
                else:
                    # Unknown or point geometry - use ST_Centroid as safe fallback
                    geom_expr = f"ST_Centroid({geom_expr})"
                    self.log_info(f"✓ Spatialite: Using ST_Centroid (safe fallback for unknown geometry type)")
            elif centroid_mode == 'point_on_surface':
                # v3.0.7: point_on_surface mode should ALSO check geometry type
                # ST_PointOnSurface returns NULL on line geometries in Spatialite!
                if is_polygon:
                    geom_expr = f"ST_PointOnSurface({geom_expr})"
                    self.log_info(f"✓ Spatialite: Using ST_PointOnSurface for polygon layer (guaranteed inside)")
                elif is_line:
                    geom_expr = f"ST_Centroid({geom_expr})"
                    self.log_info(f"✓ Spatialite: Using ST_Centroid for line layer (ST_PointOnSurface returns NULL on lines)")
                else:
                    # Unknown geometry - try ST_PointOnSurface but log warning
                    geom_expr = f"ST_PointOnSurface({geom_expr})"
                    self.log_info(f"✓ Spatialite: Using ST_PointOnSurface for distant layer (guaranteed inside)")
            else:
                # 'centroid' mode - always use ST_Centroid (works on all geometry types)
                geom_expr = f"ST_Centroid({geom_expr})"
                self.log_info(f"✓ Spatialite: Using ST_Centroid for distant layer geometry (works on all geometry types)")
        
        self.log_info(f"Geometry column detected: '{geom_field}' for layer {layer_props.get('layer_name', 'unknown')}")
        
        # Get target layer SRID for comparison
        target_srid = 4326  # Default fallback
        if layer:
            crs = layer.crs()
            if crs and crs.isValid():
                authid = crs.authid()
                if ':' in authid:
                    try:
                        target_srid = int(authid.split(':')[1])
                        self.log_debug(f"Target layer SRID: {target_srid} (from {authid})")
                    except (ValueError, IndexError):
                        self.log_warning(f"Could not parse SRID from {authid}, using default 4326")
        
        # Get source geometry SRID from task parameters (this is the CRS of the WKT)
        # The WKT was created in source_layer_crs_authid in prepare_spatialite_source_geom
        source_srid = target_srid  # Default: assume same CRS
        if hasattr(self, 'task_params') and self.task_params:
            source_crs_authid = self.task_params.get('infos', {}).get('layer_crs_authid')
            if source_crs_authid and ':' in str(source_crs_authid):
                try:
                    source_srid = int(source_crs_authid.split(':')[1])
                    self.log_debug(f"Source geometry SRID: {source_srid} (from {source_crs_authid})")
                except (ValueError, IndexError):
                    self.log_warning(f"Could not parse source SRID from {source_crs_authid}")
        
        # DIAGNOSTIC v2.4.11: Log SRIDs for debugging
        from qgis.core import QgsMessageLog, Qgis
        QgsMessageLog.logMessage(
            f"  Spatialite SRID check: source={source_srid}, target={target_srid}, needs_transform={source_srid != target_srid}",
            "FilterMate", Qgis.Info
        )
        
        # Check if CRS transformation is needed
        needs_transform = source_srid != target_srid
        if needs_transform:
            self.log_info(f"CRS mismatch: Source SRID={source_srid}, Target SRID={target_srid}")
            self.log_info(f"Will use ST_Transform to reproject source geometry")
        
        # CRITICAL: Temp tables DON'T WORK with setSubsetString!
        # QGIS uses its own connection and cannot see TEMP tables from our connection.
        # Always use inline WKT for subset string filtering.
        use_temp_table = False  # FORCED: temp tables incompatible with setSubsetString
        
        if use_temp_table and layer:
            self.log_info(f"WKT size {wkt_length} chars - using OPTIMIZED temp table method")
            
            # Get database path
            db_path = self._get_spatialite_db_path(layer)
            
            if db_path:
                # Create temp table
                temp_table, conn = self._create_temp_geometry_table(db_path, source_geom, source_srid)
                
                if temp_table and conn:
                    # Store for cleanup later
                    self._temp_table_name = temp_table
                    self._temp_table_conn = conn
                    
                    # Build optimized expression using temp table JOIN
                    # This uses spatial index for O(log n) performance
                    source_geom_expr = f"{temp_table}.geometry"
                    
                    self.log_info("✓ Using temp table with spatial index for filtering")
                else:
                    # Fallback to inline WKT
                    self.log_warning("Temp table creation failed, falling back to inline WKT")
                    use_temp_table = False
            else:
                self.log_warning("Could not get database path, falling back to inline WKT")
                use_temp_table = False
        else:
            use_temp_table = False
        
        # Use inline WKT with SRID (required for setSubsetString compatibility)
        if not use_temp_table:
            if wkt_length > 500000:
                self.log_warning(
                    f"Very large WKT ({wkt_length} chars) in subset string. "
                    "This may cause slow performance. Consider using smaller source selection or PostgreSQL."
                )
            elif wkt_length > 100000:
                self.log_info(
                    f"Large WKT ({wkt_length} chars) in subset string. "
                    "Performance may be reduced for datasets >10k features."
                )
            
            # Build source geometry expression
            # CRITICAL v2.4.22: Don't transform here if buffer will need geographic transformation
            # The buffer logic below will handle all transformations properly
            # We just create the base GeomFromText expression in source SRID
            # CRITICAL v2.8.11: Wrap in MakeValid() to handle invalid source geometries
            # Source geometries from GeoPackage/Spatialite can be invalid, causing 0 results
            # 
            # v2.9.7: For very large WKT (>50KB), add SimplifyPreserveTopology in SQL as backup
            # This helps when Python simplification wasn't aggressive enough and RTTOPO fails
            # SimplifyPreserveTopology is more stable than MakeValid for complex geometries
            # v2.9.28: Reduced threshold from 50KB to 30KB to match OGR fallback threshold
            # Prevents RTTOPO errors like "MakeValid error - RTTOPO reports: Unknown Reason"
            LARGE_WKT_SQL_SIMPLIFY_THRESHOLD = 30000
            
            # v2.9.28: Check if geometry is already valid to avoid unnecessary MakeValid()
            # GeometryCollection and complex multi-geometries often cause RTTOPO errors
            needs_make_valid = True
            is_geometry_collection = False
            try:
                from qgis.core import QgsGeometry
                temp_geom = QgsGeometry.fromWkt(source_geom.replace("''", "'"))
                if temp_geom and not temp_geom.isEmpty():
                    # Check if already valid
                    geom_valid = temp_geom.isGeosValid()
                    if geom_valid:
                        needs_make_valid = False
                        self.log_debug(f"  ✓ Source geometry is already valid - skipping MakeValid()")
                    
                    # Check geometry type - GeometryCollection is problematic for RTTOPO
                    geom_type = temp_geom.wkbType()
                    from qgis.core import QgsWkbTypes
                    if geom_type == QgsWkbTypes.GeometryCollection or \
                       geom_type == QgsWkbTypes.GeometryCollectionZ or \
                       geom_type == QgsWkbTypes.GeometryCollectionM or \
                       geom_type == QgsWkbTypes.GeometryCollectionZM:
                        is_geometry_collection = True
                        self.log_info(f"  ⚠️ GeometryCollection detected - forcing simplification to avoid RTTOPO errors")
            except Exception as e:
                self.log_debug(f"  Could not validate geometry, will use MakeValid(): {e}")
            
            # v2.9.28: Force simplification for GeometryCollection OR large WKT
            if is_geometry_collection or wkt_length > LARGE_WKT_SQL_SIMPLIFY_THRESHOLD:
                # Calculate simplify tolerance based on geometry extent (from bbox in logs)
                # Use a small tolerance that won't distort the geometry significantly
                # but will reduce vertex count enough to avoid RTTOPO issues
                simplify_tolerance = 0.1  # Default small tolerance
                try:
                    if temp_geom and not temp_geom.isEmpty():
                        bbox = temp_geom.boundingBox()
                        extent = max(bbox.width(), bbox.height())
                        # Tolerance = 0.01% of extent (small enough to preserve shape)
                        simplify_tolerance = max(0.1, extent * 0.0001)
                except Exception:
                    pass
                
                reason = "GeometryCollection" if is_geometry_collection else f"Large WKT ({wkt_length:,} chars)"
                self.log_info(f"  🔧 {reason} - using SQL SimplifyPreserveTopology (tolerance={simplify_tolerance:.4f})")
                
                if needs_make_valid:
                    source_geom_expr = f"SimplifyPreserveTopology(MakeValid(GeomFromText('{source_geom}', {source_srid})), {simplify_tolerance})"
                else:
                    source_geom_expr = f"SimplifyPreserveTopology(GeomFromText('{source_geom}', {source_srid}), {simplify_tolerance})"
            else:
                if needs_make_valid:
                    source_geom_expr = f"MakeValid(GeomFromText('{source_geom}', {source_srid}))"
                else:
                    # Geometry is already valid, no MakeValid needed
                    source_geom_expr = f"GeomFromText('{source_geom}', {source_srid})"
            
            self.log_debug(f"Created base geometry expression with SRID {source_srid}")
        
        # Apply buffer using ST_Buffer() SQL function if specified
        # This uses Spatialite native spatial functions instead of QGIS processing
        # Supports both positive (expand) and negative (shrink/erode) buffers
        if buffer_value is not None and buffer_value != 0:
            # Check if CRS is geographic - buffer needs to be in appropriate units
            is_target_geographic = target_srid == 4326 or (layer and layer.crs().isGeographic())
            
            # Get buffer endcap style from task_params
            endcap_style = self._get_buffer_endcap_style()
            buffer_style_param = "" if endcap_style == 'round' else f", 'endcap={endcap_style}'"
            
            # Log negative buffer usage
            buffer_type_str = "expansion" if buffer_value > 0 else "erosion (shrink)"
            
            if is_target_geographic:
                # FIX v3.0.12: Use unified geographic CRS transformation helper
                # This replaces 35+ lines of duplicated transformation logic
                source_geom_expr = self._apply_geographic_buffer_transform(
                    source_geom_expr,
                    source_srid=source_srid,
                    target_srid=target_srid,
                    buffer_value=buffer_value,
                    dialect='spatialite'
                )
                self.log_info(f"✓ Applied ST_Buffer({buffer_value}m, {buffer_type_str}, endcap={endcap_style}) via EPSG:3857 reprojection")
            else:
                # Projected CRS: buffer value is directly in map units (usually meters)
                # First ensure geometry is in target SRID if transformation is needed
                if needs_transform:
                    source_geom_expr = f"ST_Transform({source_geom_expr}, {target_srid})"
                    self.log_info(f"Transformed source: SRID {source_srid} → {target_srid}")
                
                # Then apply buffer in native CRS
                source_geom_expr = self._build_st_buffer_with_style(source_geom_expr, buffer_value)
                self.log_info(f"✓ Applied ST_Buffer({buffer_value}, {buffer_type_str}, endcap={endcap_style}) in native CRS (SRID={target_srid})")
        else:
            # No buffer: just apply CRS transformation if needed
            if not use_temp_table and needs_transform:
                source_geom_expr = f"ST_Transform({source_geom_expr}, {target_srid})"
                self.log_info(f"Transformed source (no buffer): SRID {source_srid} → {target_srid}")
        
        # Dynamic buffer expressions use attribute values
        if buffer_expression:
            self.log_info(f"Using dynamic buffer expression: {buffer_expression}")
            # Replace any table prefix in buffer expression for subset string context
            clean_buffer_expr = buffer_expression
            if '"' in clean_buffer_expr and '.' not in clean_buffer_expr:
                # Expression like "field_name" - use as-is for attribute-based buffer
                # Apply endcap style if configured
                endcap_style = self._get_buffer_endcap_style()
                if endcap_style == 'round':
                    source_geom_expr = f"ST_Buffer({source_geom_expr}, {clean_buffer_expr})"
                else:
                    source_geom_expr = f"ST_Buffer({source_geom_expr}, {clean_buffer_expr}, 'endcap={endcap_style}')"
                self.log_info(f"✓ Applied dynamic ST_Buffer with expression: {clean_buffer_expr} (endcap={endcap_style})")
        
        # Build predicate expressions with OPTIMIZED order
        # Order by selectivity (most selective first = fastest short-circuit)
        # intersects > within > contains > overlaps > touches
        predicate_order = ['intersects', 'within', 'contains', 'overlaps', 'touches', 'crosses', 'disjoint']
        
        # Normalize predicate keys: convert indices ('0', '4') to names ('intersects', 'touches')
        # This handles the format from execute_filtering where predicates = {str(idx): sql_func}
        index_to_name = {
            '0': 'intersects', '1': 'contains', '2': 'disjoint', '3': 'equals',
            '4': 'touches', '5': 'overlaps', '6': 'within', '7': 'crosses'
        }
        
        normalized_predicates = {}
        for key, value in predicates.items():
            # Try to normalize the key
            if key in index_to_name:
                # Key is a string index like '0'
                normalized_key = index_to_name[key]
            elif key.lower().startswith('st_'):
                # Key is SQL function like 'ST_Intersects'
                normalized_key = key.lower().replace('st_', '')
            elif key.lower() in predicate_order or key.lower() == 'equals':
                # Key is already a name like 'intersects'
                normalized_key = key.lower()
            else:
                # Unknown format, use as-is
                normalized_key = key
            normalized_predicates[normalized_key] = value
        
        # Sort predicates by optimal order
        ordered_predicates = sorted(
            normalized_predicates.items(),
            key=lambda x: predicate_order.index(x[0]) if x[0] in predicate_order else 999
        )
        
        predicate_expressions = []
        for predicate_name, predicate_func in ordered_predicates:
            # Apply spatial predicate
            # Format: ST_Intersects("geometry", source_geom_expr) = 1
            # 
            # v2.8.13 FIX: Add explicit "= 1" comparison to handle NULL geometry from negative buffer
            # When a negative buffer produces an empty geometry, source_geom_expr becomes NULL via:
            #   CASE WHEN ST_IsEmpty(...) THEN NULL ELSE ... END
            # Without "= 1", ST_Intersects(geom, NULL) returns NULL (not FALSE), and in SQLite,
            # NULL in WHERE clause doesn't filter records - causing ALL features to be returned!
            # With "= 1", NULL = 1 evaluates to FALSE, correctly filtering out all features.
            expr = f"{predicate_func}({geom_expr}, {source_geom_expr}) = 1"
            predicate_expressions.append(expr)
            self.log_debug(f"Added predicate: {predicate_func} = 1 (optimal order, NULL-safe)")
        
        # Combine predicates with OR
        # Note: SQL engines typically evaluate OR left-to-right
        # Most selective predicates first = fewer expensive operations
        if predicate_expressions:
            combined = " OR ".join(predicate_expressions)
            method = "temp table" if use_temp_table else "inline WKT"
            self.log_info(
                f"Built Spatialite expression with {len(predicate_expressions)} predicate(s) "
                f"using {method} method"
            )
            self.log_debug(f"Expression preview: {combined[:150]}...")
            
            # DIAGNOSTIC v2.4.11: Log full expression for first predicate to help debug
            from qgis.core import QgsMessageLog, Qgis
            first_expr_preview = predicate_expressions[0][:300] if predicate_expressions else "NONE"
            QgsMessageLog.logMessage(
                f"  Spatialite predicate: {first_expr_preview}...",
                "FilterMate", Qgis.Info
            )
            
            return combined
        
        # v2.8.2 FIX: Return "0 features" filter instead of empty string
        # When no predicates could be built, return an impossible condition to filter 0 features
        self.log_warning("No predicates to apply - returning '0 features' filter")
        return "1 = 0"  # Universal FALSE condition
    
    def apply_filter(
        self,
        layer: QgsVectorLayer,
        expression: str,
        old_subset: Optional[str] = None,
        combine_operator: Optional[str] = None
    ) -> bool:
        """
        Apply filter to Spatialite layer using setSubsetString.
        
        v2.4.14: Added direct SQL mode for GeoPackage when setSubsetString doesn't
        support Spatialite SQL but mod_spatialite is available. In this mode,
        we query matching FIDs via direct SQL and apply a simple "fid IN (...)" filter.
        
        v2.6.5: Enhanced WKT detection with fallback extraction from expression.
        
        Args:
            layer: Spatialite layer to filter
            expression: Spatialite SQL expression
            old_subset: Existing subset string
            combine_operator: Operator to combine filters (AND/OR)
        
        Returns:
            True if filter applied successfully
        """
        import time
        start_time = time.time()
        
        try:
            if not expression:
                self.log_warning("Empty expression, skipping filter")
                return False
            
            # Check if direct SQL mode is needed for this layer
            layer_id = layer.id()
            use_direct_sql = False
            with self.__class__._cache_lock:
                use_direct_sql = self.__class__._direct_sql_mode_cache.get(layer_id, False)
            
            # v2.6.1: Check for large dataset optimization with source table
            # For large datasets with geometric filters, use permanent source table
            # CRITICAL FIX v3.0.19: Protect against None/invalid feature count
            raw_feature_count = layer.featureCount()
            feature_count = raw_feature_count if raw_feature_count is not None and raw_feature_count >= 0 else 0
            use_source_table = False
            
            # v2.6.5: Enhanced WKT detection - check task_params first, then extract from expression
            source_wkt_size = 0
            has_source_wkt = False
            source_wkt = None
            
            # Method 1: Check task_params (preferred - WKT stored by filter_task)
            if hasattr(self, 'task_params') and self.task_params:
                infos = self.task_params.get('infos', {})
                source_wkt = infos.get('source_geom_wkt', '')
                if source_wkt:
                    has_source_wkt = True
                    source_wkt_size = len(source_wkt)
                    self.log_debug(f"WKT from task_params: {source_wkt_size} chars")
            
            # Method 2: Fallback - extract WKT from expression (handles legacy/edge cases)
            if not has_source_wkt and expression:
                extracted_wkt = self._extract_wkt_from_expression(expression)
                if extracted_wkt:
                    source_wkt = extracted_wkt
                    has_source_wkt = True
                    source_wkt_size = len(extracted_wkt)
                    self.log_info(f"📋 WKT extracted from expression: {source_wkt_size} chars")
                    # Store for future use in this session
                    if hasattr(self, 'task_params') and self.task_params:
                        if 'infos' not in self.task_params:
                            self.task_params['infos'] = {}
                        self.task_params['infos']['source_geom_wkt'] = extracted_wkt
            
            # Use source table optimization for EITHER large target OR large source WKT
            if use_direct_sql and has_source_wkt:
                mod_available, _ = _test_mod_spatialite_available()
                
                if mod_available:
                    if feature_count >= self.LARGE_DATASET_THRESHOLD:
                        use_source_table = True
                        self.log_info(f"📊 Large target dataset ({feature_count} features >= {self.LARGE_DATASET_THRESHOLD})")
                    elif source_wkt_size >= self.LARGE_WKT_THRESHOLD:
                        use_source_table = True
                        self.log_info(f"📊 Large source WKT ({source_wkt_size} chars >= {self.LARGE_WKT_THRESHOLD}) - using R-tree optimization to prevent freeze")
            
            # v2.4.20: Log which mode is being used for debugging
            from qgis.core import QgsMessageLog, Qgis
            if use_source_table:
                mode_str = "OPTIMIZED SOURCE TABLE (R-tree)"
            elif use_direct_sql:
                mode_str = "DIRECT SQL"
            else:
                mode_str = "NATIVE (setSubsetString)"
            QgsMessageLog.logMessage(
                f"Spatialite apply_filter: {layer.name()} → mode={mode_str}, features={feature_count}",
                "FilterMate", Qgis.Info
            )
            
            # v2.6.1: Use optimized source table method for large datasets
            if use_source_table:
                self.log_info(f"🚀 Using OPTIMIZED SOURCE TABLE mode for {layer.name()} (R-tree spatial index)")
                return self._apply_filter_with_source_table(layer, old_subset, combine_operator)
            
            if use_direct_sql:
                self.log_info(f"🚀 Using DIRECT SQL mode for {layer.name()} (bypassing GDAL/OGR)")
                # v2.6.3: Add QgsMessageLog before calling to debug silent failures
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"apply_filter: CALLING _apply_filter_direct_sql for {layer.name()}",
                    "FilterMate", Qgis.Info
                )
                try:
                    result = self._apply_filter_direct_sql(layer, expression, old_subset, combine_operator)
                    QgsMessageLog.logMessage(
                        f"apply_filter: _apply_filter_direct_sql returned {result} for {layer.name()}",
                        "FilterMate", Qgis.Info
                    )
                    return result
                except Exception as e:
                    QgsMessageLog.logMessage(
                        f"apply_filter: EXCEPTION in _apply_filter_direct_sql for {layer.name()}: {e}",
                        "FilterMate", Qgis.Critical
                    )
                    import traceback
                    QgsMessageLog.logMessage(
                        f"Traceback: {traceback.format_exc()[:500]}",
                        "FilterMate", Qgis.Critical
                    )
                    return False
            
            # NATIVE MODE: Using setSubsetString with Spatialite SQL
            self.log_info(f"📝 Using NATIVE mode for {layer.name()} (setSubsetString with Spatialite SQL)")
            
            # Log layer information
            self.log_debug(f"Layer provider: {layer.providerType()}")
            self.log_debug(f"Layer source: {layer.source()[:100]}...")
            self.log_debug(f"Current feature count: {layer.featureCount()}")
            
            # Combine with existing filter if specified
            # v2.8.6: Use shared methods from base_backend for harmonization
            if old_subset:
                # Check if old_subset should be cleared (contains spatial predicates, EXISTS, etc.)
                should_clear = self._should_clear_old_subset(old_subset)
                
                # Check if old_subset is a FID-only filter from previous multi-step
                is_fid_only = self._is_fid_only_filter(old_subset)
                
                if should_clear:
                    # Old subset contains geometric filter patterns - replace instead of combine
                    self.log_info(f"🔄 Old subset contains geometric filter - replacing instead of combining")
                    self.log_info(f"  → Old subset: '{old_subset[:80]}...'")
                    final_expression = expression
                elif is_fid_only:
                    # v3.0.7: FID filter from previous step - ALWAYS combine (ignore combine_operator=None)
                    # This ensures intersection of step 1 AND step 2 results in multi-step filtering
                    self.log_info(f"✅ Combining FID filter from step 1 with new filter (MULTI-STEP)")
                    self.log_info(f"  → FID filter: {old_subset[:80]}...")
                    final_expression = f"({old_subset}) AND ({expression})"
                elif combine_operator is None:
                    # v3.0.7: combine_operator=None with non-FID old_subset = use default AND
                    self.log_info(f"🔗 combine_operator=None → using default AND (preserving filter)")
                    self.log_info(f"  → Old subset: '{old_subset[:80]}...'")
                    final_expression = f"({old_subset}) AND ({expression})"
                else:
                    if not combine_operator:
                        combine_operator = 'AND'
                        self.log_info(f"🔗 Préservation du filtre existant avec {combine_operator}")
                    self.log_info(f"  → Ancien subset: '{old_subset[:80]}...' (longueur: {len(old_subset)})")
                    self.log_info(f"  → Nouveau filtre: '{expression[:80]}...' (longueur: {len(expression)})")
                    final_expression = f"({old_subset}) {combine_operator} ({expression})"
                    self.log_info(f"  → Expression combinée: longueur {len(final_expression)} chars")
            else:
                final_expression = expression
            
            self.log_debug(f"Applying Spatialite filter to {layer.name()}")
            self.log_debug(f"Expression length: {len(final_expression)} chars")
            
            # THREAD SAFETY FIX: Use queue callback if available (called from background thread)
            # This defers the setSubsetString() call to the main thread in finished()
            queue_callback = self.task_params.get('_subset_queue_callback')
            
            if queue_callback:
                # Queue for main thread application
                queue_callback(layer, final_expression)
                self.log_debug(f"Spatialite filter queued for main thread application")
                result = True  # We assume success, actual application happens in finished()
            else:
                # Fallback: direct application (for testing or non-task contexts)
                self.log_warning(f"No queue callback - applying directly (may cause thread issues)")
                result = safe_set_subset_string(layer, final_expression)
                
                # FIX v2.9.24: Clear any existing selection after filter application
                # This prevents "all features selected" bug on second filter
                try:
                    if layer and is_valid_layer(layer):
                        layer.removeSelection()
                        self.log_debug(f"Cleared selection after Spatialite filter")
                except Exception as sel_err:
                    self.log_debug(f"Could not clear selection: {sel_err}")
            
            elapsed = time.time() - start_time
            
            if result:
                feature_count = layer.featureCount()
                self.log_info(f"✓ {layer.name()}: {feature_count} features ({elapsed:.2f}s)")
                
                if feature_count == 0:
                    self.log_warning("Filter resulted in 0 features - check CRS or expression")
                
                if elapsed > 5.0:
                    self.log_warning(f"Slow operation - consider PostgreSQL for large datasets")
            else:
                self.log_error(f"✗ Filter failed for {layer.name()}")
                self.log_error(f"  → Provider: {layer.providerType()}")
                try:
                    geom_col_debug = layer.dataProvider().geometryColumn()
                except (AttributeError, RuntimeError):
                    geom_col_debug = 'unknown'
                self.log_error(f"  → Geometry column from layer: '{geom_col_debug}'")
                self.log_error(f"  → Expression length: {len(final_expression)} chars")
                self.log_error(f"  → Expression preview: {final_expression[:500]}...")
                
                # Try to get the actual error from the layer
                if layer.error() and layer.error().message():
                    self.log_error(f"  → Layer error: {layer.error().message()}")
                
                # DIAGNOSTIC v2.4.13: More detailed diagnostics for troubleshooting
                try:
                    from qgis.core import QgsDataSourceUri
                    uri_obj = QgsDataSourceUri(layer.dataProvider().dataSourceUri())
                    self.log_error(f"  → URI geometry column: '{uri_obj.geometryColumn()}'")
                    self.log_error(f"  → URI table: '{uri_obj.table()}'")
                    self.log_error(f"  → Source: {layer.source()[:150]}...")
                except Exception as uri_err:
                    self.log_error(f"  → Could not parse URI: {uri_err}")
                
                self.log_error("Check: spatial functions available, geometry column, SQL syntax")
                
                # Check if expression references a temp table (common mistake)
                if '_fm_temp_geom_' in final_expression:
                    self.log_error("⚠️ Expression references temp table - this doesn't work with QGIS!")
                
                # DIAGNOSTIC v2.4.13: Test both geometry column access AND spatial functions
                try:
                    from ..appUtils import is_layer_source_available, safe_set_subset_string
                    if not is_layer_source_available(layer):
                        self.log_warning("Layer invalid or source missing; skipping test expression")
                    else:
                        # v2.6.6: Use dataProvider().geometryColumn()
                        try:
                            geom_col = layer.dataProvider().geometryColumn()
                        except (AttributeError, RuntimeError):
                            geom_col = None
                        
                        # Test 1: Simple geometry not null
                        if geom_col:
                            test_expr = f'"{geom_col}" IS NOT NULL AND 1=0'
                            self.log_debug(f"Testing geometry column access: {test_expr}")
                            test_result = safe_set_subset_string(layer, test_expr)
                            if test_result:
                                self.log_info("✓ Geometry column access OK")
                            else:
                                self.log_error(f"✗ Cannot access geometry column '{geom_col}'")
                            safe_set_subset_string(layer, "")
                        
                        # Test 2: GeomFromText function
                        test_expr_geom = "GeomFromText('POINT(0 0)', 4326) IS NOT NULL AND 1=0"
                        self.log_debug(f"Testing GeomFromText: {test_expr_geom}")
                        test_result2 = safe_set_subset_string(layer, test_expr_geom)
                        if test_result2:
                            self.log_info("✓ GeomFromText function available")
                        else:
                            self.log_error("✗ GeomFromText function NOT available")
                            self.log_error("   → GDAL may not be compiled with Spatialite extension")
                            self.log_error("   → Try using OGR backend for this layer")
                        safe_set_subset_string(layer, "")
                        
                        # Test 3: ST_Intersects function
                        if geom_col:
                            test_expr_intersects = f"ST_Intersects(\"{geom_col}\", GeomFromText('POINT(0 0)', 4326)) = 1 AND 1=0"
                            self.log_debug(f"Testing ST_Intersects: {test_expr_intersects}")
                            test_result3 = safe_set_subset_string(layer, test_expr_intersects)
                            if test_result3:
                                self.log_info("✓ ST_Intersects function available")
                                self.log_error("   → Problem is with the SOURCE GEOMETRY (WKT too long or invalid?)")
                            else:
                                self.log_error("✗ ST_Intersects function NOT available")
                            safe_set_subset_string(layer, "")
                except Exception as test_error:
                    self.log_debug(f"Test expression error: {test_error}")
            
            return result
            
        except Exception as e:
            self.log_error(f"Exception while applying filter: {str(e)}")
            import traceback
            self.log_debug(f"Traceback: {traceback.format_exc()}")
            # v2.6.3: Also log to QGIS Message Log for visibility
            from qgis.core import QgsMessageLog, Qgis
            QgsMessageLog.logMessage(
                f"apply_filter EXCEPTION for {layer.name() if layer else 'unknown'}: {str(e)}",
                "FilterMate", Qgis.Critical
            )
            QgsMessageLog.logMessage(
                f"Traceback: {traceback.format_exc()[:500]}",
                "FilterMate", Qgis.Critical
            )
            return False
    
    def _is_task_canceled(self) -> bool:
        """
        v2.6.2: Check if the parent task was canceled.
        
        Returns:
            True if task was canceled, False otherwise
        """
        if hasattr(self, 'task_params') and self.task_params:
            task = self.task_params.get('_parent_task')
            if task and hasattr(task, 'isCanceled'):
                return task.isCanceled()
        return False
    
    def _report_progress(self, current: int, total: int, operation: str = "Filtering"):
        """
        v2.6.2: Report progress to parent task if available.
        
        Args:
            current: Current progress value
            total: Total value
            operation: Description of current operation
        """
        if hasattr(self, 'task_params') and self.task_params:
            task = self.task_params.get('_parent_task')
            if task and hasattr(task, 'setProgress'):
                progress = int((current / total) * 100) if total > 0 else 0
                task.setProgress(min(progress, 99))  # Leave 1% for final steps
    
    def _get_wkt_bounding_box(self, wkt: str) -> Optional[Tuple[float, float, float, float]]:
        """
        v2.6.5: Extract bounding box from WKT geometry for pre-filtering.
        
        Uses QGIS geometry parsing to get accurate bbox.
        
        Args:
            wkt: WKT geometry string (may have escaped quotes)
        
        Returns:
            Tuple (minx, miny, maxx, maxy) or None if parsing fails
        """
        try:
            from qgis.core import QgsGeometry
            # Unescape SQL quotes
            clean_wkt = wkt.replace("''", "'")
            geom = QgsGeometry.fromWkt(clean_wkt)
            if geom and not geom.isEmpty():
                bbox = geom.boundingBox()
                return (bbox.xMinimum(), bbox.yMinimum(), bbox.xMaximum(), bbox.yMaximum())
        except Exception as e:
            self.log_debug(f"Could not parse WKT bbox: {e}")
        return None
    
    def _build_bbox_prefilter(
        self,
        geom_col: str,
        bbox: Tuple[float, float, float, float],
        srid: int,
        is_geopackage: bool = True
    ) -> str:
        """
        v2.6.5: Build a bounding box pre-filter for Spatialite.
        
        Uses R-tree index if available for O(log n) performance.
        
        Args:
            geom_col: Geometry column name
            bbox: Bounding box (minx, miny, maxx, maxy)
            srid: SRID of the geometry
            is_geopackage: Whether this is a GeoPackage layer
        
        Returns:
            SQL expression for bbox filter
        """
        minx, miny, maxx, maxy = bbox
        
        # Build bbox as Spatialite envelope
        bbox_wkt = f"POLYGON(({minx} {miny}, {maxx} {miny}, {maxx} {maxy}, {minx} {maxy}, {minx} {miny}))"
        
        if is_geopackage:
            # GeoPackage uses GPB format
            geom_expr = f'GeomFromGPB("{geom_col}")'
        else:
            geom_expr = f'"{geom_col}"'
        
        # Use MbrIntersects for fast bbox check (uses R-tree if available)
        return f"MbrIntersects({geom_expr}, GeomFromText('{bbox_wkt}', {srid})) = 1"
    
    # v2.8.7: Threshold for using FID table instead of IN expression
    # Above this, setSubsetString with IN(...) causes QGIS freeze
    LARGE_FID_TABLE_THRESHOLD = 20000
    FID_TABLE_PREFIX = "_fm_fids_"
    
    def _create_fid_table(self, db_path: str, fids: List[int]) -> Optional[str]:
        """
        v2.8.7: Create a temporary table with FIDs in the GeoPackage.
        
        For very large result sets (>20K FIDs), using IN(...) in setSubsetString
        causes QGIS to freeze while parsing the expression. Creating a table
        with FIDs and using EXISTS subquery is much faster.
        
        Args:
            db_path: Path to GeoPackage database
            fids: List of FIDs to store
        
        Returns:
            Table name if created, None on failure
        """
        conn = None
        try:
            import uuid
            timestamp = int(time.time())
            table_name = f"{self.FID_TABLE_PREFIX}{timestamp}_{uuid.uuid4().hex[:6]}"
            
            self.log_info(f"📦 Creating FID table '{table_name}' with {len(fids):,} FIDs...")
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Create simple FID table
            cursor.execute(f'''
                CREATE TABLE "{table_name}" (
                    fid INTEGER PRIMARY KEY
                )
            ''')
            
            # Batch insert FIDs for performance
            batch_size = 1000
            for i in range(0, len(fids), batch_size):
                batch = fids[i:i + batch_size]
                placeholders = ",".join(["(?)"] * len(batch))
                cursor.execute(f'INSERT INTO "{table_name}" (fid) VALUES {placeholders}', batch)
            
            conn.commit()
            conn.close()
            
            self.log_info(f"  ✓ FID table created: {table_name}")
            
            # Store for cleanup
            if not hasattr(self, '_fid_tables'):
                self._fid_tables = []
            self._fid_tables.append((db_path, table_name))
            
            return table_name
            
        except Exception as e:
            self.log_error(f"Failed to create FID table: {e}")
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            return None
    
    def _build_fid_table_filter(self, db_path: str, pk_col: str, fids: List[int]) -> Optional[str]:
        """
        v2.8.7: Build filter using FID table for large result sets.
        
        DEPRECATED (v2.8.9): This method is NO LONGER USED because the generated
        subquery "fid IN (SELECT fid FROM _fm_fids_xxx)" is NOT supported by the
        OGR provider in QGIS setSubsetString(). Use _build_range_based_filter() instead.
        
        The subquery approach only works with direct SQLite connections, not with
        QGIS layer filters.
        
        Instead of: fid IN (1,2,3,...235000)  <- freezes QGIS
        Uses:       fid IN (SELECT fid FROM _fm_fids_xxx)  <- NOT SUPPORTED by OGR
        
        Args:
            db_path: Path to GeoPackage
            pk_col: Primary key column name
            fids: List of matching FIDs
        
        Returns:
            SQL expression or None if table creation failed
        """
        table_name = self._create_fid_table(db_path, fids)
        if not table_name:
            return None
        
        # Use subquery instead of massive IN list
        return f'"{pk_col}" IN (SELECT fid FROM "{table_name}")'
    
    def _cleanup_fid_tables(self):
        """v2.8.7: Clean up FID tables created during filtering."""
        if not hasattr(self, '_fid_tables'):
            return
        
        for db_path, table_name in self._fid_tables:
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
                conn.commit()
                conn.close()
                self.log_debug(f"Cleaned up FID table: {table_name}")
            except Exception as e:
                self.log_debug(f"Failed to cleanup FID table {table_name}: {e}")
        
        self._fid_tables = []
    
    def _build_range_based_filter(self, pk_col: str, fids: List[int]) -> str:
        """
        v2.8.7: Build FID filter using BETWEEN ranges for consecutive FIDs.
        
        v2.8.10: FIX - Use unquoted 'fid' for OGR/GeoPackage compatibility.
        OGR drivers don't support quoted column names in setSubsetString().
        
        This is MUCH more compact than IN() for large consecutive FID sets.
        For 235K FIDs that are mostly consecutive, this can reduce expression
        size from ~1.5MB to ~10KB or less.
        
        Example: [1,2,3,4,5,8,9,10,15] becomes:
            ("fid" BETWEEN 1 AND 5) OR ("fid" BETWEEN 8 AND 10) OR "fid" = 15
        
        Args:
            pk_col: Primary key column name
            fids: List of FIDs to filter
        
        Returns:
            SQL expression using BETWEEN ranges
        """
        if not fids:
            # v2.8.10: FIX - Use unquoted fid for OGR/GeoPackage compatibility
            return 'fid = -1' if pk_col == 'fid' else f'"{pk_col}" = -1'  # No match
        
        sorted_fids = sorted(set(fids))  # Remove duplicates and sort
        
        # Find consecutive ranges
        ranges = []
        singles = []
        
        i = 0
        while i < len(sorted_fids):
            start = sorted_fids[i]
            end = start
            
            # Extend range while consecutive
            while i + 1 < len(sorted_fids) and sorted_fids[i + 1] == end + 1:
                i += 1
                end = sorted_fids[i]
            
            if start == end:
                singles.append(start)
            else:
                ranges.append((start, end))
            
            i += 1
        
        # Build expression parts
        parts = []
        
        # Add BETWEEN ranges
        for start, end in ranges:
            if end - start >= 2:
                # Use BETWEEN for ranges of 3+ consecutive FIDs
                # v2.8.10: FIX - Use unquoted fid for OGR/GeoPackage compatibility
                if pk_col == 'fid':
                    parts.append(f'(fid BETWEEN {start} AND {end})')
                else:
                    parts.append(f'("{pk_col}" BETWEEN {start} AND {end})')
            else:
                # For ranges of 2, just add to singles
                singles.append(start)
                singles.append(end)
        
        # Group singles into chunks to avoid too many OR clauses
        if singles:
            # Chunk singles into groups of 1000 for IN()
            chunk_size = 1000
            for i in range(0, len(singles), chunk_size):
                chunk = singles[i:i + chunk_size]
                # v2.8.10: FIX - Use unquoted fid for OGR/GeoPackage compatibility
                if pk_col == 'fid':
                    parts.append(f'fid IN ({", ".join(str(f) for f in chunk)})')
                else:
                    parts.append(f'"{pk_col}" IN ({", ".join(str(f) for f in chunk)})')
        
        if not parts:
            # v2.8.10: FIX - Use unquoted fid for OGR/GeoPackage compatibility
            return 'fid = -1' if pk_col == 'fid' else f'"{pk_col}" = -1'
        
        result = "(" + " OR ".join(parts) + ")"
        
        # Log compression stats
        original_chars = len(", ".join(str(f) for f in sorted_fids))
        new_chars = len(result)
        compression = (1 - new_chars / original_chars) * 100 if original_chars > 0 else 0
        
        self.log_info(f"  📊 RANGE filter: {len(ranges)} ranges + {len(singles)} singles")
        self.log_info(f"  📊 Compression: {original_chars:,} → {new_chars:,} chars ({compression:.1f}% reduction)")
        
        return result
    
    def _build_chunked_fid_filter(self, pk_col: str, fids: List[int], chunk_size: int = 5000) -> str:
        """
        v2.6.5: Build FID filter with chunked IN clauses to prevent expression parsing freeze.
        
        v2.8.10: FIX - Use unquoted 'fid' for OGR/GeoPackage compatibility.
        
        SQLite/QGIS can freeze when parsing very long IN (...) expressions.
        Breaking into chunks with OR helps the parser.
        
        Args:
            pk_col: Primary key column name
            fids: List of FIDs to filter
            chunk_size: Maximum FIDs per IN clause
        
        Returns:
            SQL expression with chunked IN clauses
        """
        sorted_fids = sorted(fids)
        
        # v2.8.10: FIX - Use unquoted fid for OGR/GeoPackage compatibility
        col_ref = 'fid' if pk_col == 'fid' else f'"{pk_col}"'
        
        # If small enough, use single IN
        if len(sorted_fids) <= chunk_size:
            return f'{col_ref} IN ({", ".join(str(f) for f in sorted_fids)})'
        
        # Build chunked expression
        chunks = []
        for i in range(0, len(sorted_fids), chunk_size):
            chunk = sorted_fids[i:i + chunk_size]
            chunks.append(f'{col_ref} IN ({", ".join(str(f) for f in chunk)})')
        
        # Combine with OR
        result = "(" + " OR ".join(chunks) + ")"
        self.log_info(f"  📊 Using CHUNKED IN filter ({len(chunks)} chunks of {chunk_size})")
        return result
    
    def _apply_filter_direct_sql(
        self,
        layer: QgsVectorLayer,
        expression: str,
        old_subset: Optional[str] = None,
        combine_operator: Optional[str] = None
    ) -> bool:
        """
        Apply filter using direct SQL queries with mod_spatialite.
        
        This method bypasses GDAL's OGR driver and queries the GeoPackage/SQLite
        directly using mod_spatialite. It retrieves matching FIDs and applies
        a simple "fid IN (...)" filter that works with any OGR driver.
        
        v2.4.14: New method for GeoPackage support when GDAL doesn't support
        Spatialite SQL in setSubsetString.
        
        v2.6.2: Added timeout, cancellation checks, and batch processing
        to prevent QGIS freezing on complex geometric filters.
        
        Args:
            layer: GeoPackage/SQLite layer to filter
            expression: Spatialite SQL expression (will be adapted for direct SQL)
            old_subset: Existing subset string
            combine_operator: Operator to combine filters (AND/OR)
        
        Returns:
            True if filter applied successfully
        """
        import time
        start_time = time.time()
        
        # v2.6.3: Add entry log for debugging silent failures
        self.log_info(f"_apply_filter_direct_sql: Starting for {layer.name()}")
        from qgis.core import QgsMessageLog, Qgis
        QgsMessageLog.logMessage(
            f"_apply_filter_direct_sql: Starting for {layer.name()}",
            "FilterMate", Qgis.Info
        )
        
        # v2.6.2: Check cancellation before starting
        if self._is_task_canceled():
            self.log_info("Filter cancelled before starting direct SQL")
            return False
        
        try:
            # Get file path and table name
            source = layer.source()
            source_path = source.split('|')[0] if '|' in source else source
            
            # v2.4.21: CRITICAL - Verify source is a local file before connecting
            # This prevents SQLite errors on remote/virtual sources
            source_lower = source_path.lower().strip()
            remote_prefixes = ('http://', 'https://', 'ftp://', 'wfs:', 'wms:', 'wcs://', '/vsicurl/')
            if any(source_lower.startswith(prefix) for prefix in remote_prefixes):
                self.log_error(f"Cannot use direct SQL on remote source: {layer.name()}")
                QgsMessageLog.logMessage(
                    f"_apply_filter_direct_sql FAILED: Remote source not supported for {layer.name()}",
                    "FilterMate", Qgis.Warning
                )
                return False
            
            if not os.path.isfile(source_path):
                self.log_error(f"Source file not found for direct SQL: {source_path}")
                self.log_error(f"  → This may be a remote or virtual source")
                QgsMessageLog.logMessage(
                    f"_apply_filter_direct_sql FAILED: Source file not found: {source_path}",
                    "FilterMate", Qgis.Warning
                )
                return False
            
            # Get table name
            table_name = None
            if '|layername=' in source:
                table_name = source.split('|layername=')[1].split('|')[0]
            
            if not table_name:
                from qgis.core import QgsDataSourceUri
                uri = QgsDataSourceUri(source)
                table_name = uri.table()
            
            if not table_name:
                self.log_error(f"Could not determine table name for direct SQL mode")
                QgsMessageLog.logMessage(
                    f"_apply_filter_direct_sql FAILED: Could not determine table name for {layer.name()}",
                    "FilterMate", Qgis.Warning
                )
                return False
            
            # Get mod_spatialite extension name
            mod_available, ext_name = _test_mod_spatialite_available()
            if not mod_available or not ext_name:
                self.log_error(f"mod_spatialite not available for direct SQL mode")
                QgsMessageLog.logMessage(
                    f"_apply_filter_direct_sql FAILED: mod_spatialite not available",
                    "FilterMate", Qgis.Warning
                )
                return False
            
            # v2.6.2: Connect to the database with mod_spatialite and timeout
            QgsMessageLog.logMessage(
                f"_apply_filter_direct_sql: Connecting to {source_path} (table: {table_name})",
                "FilterMate", Qgis.Info
            )
            
            # v2.6.4: Wrap connection in detailed try/except for debugging
            # v2.6.4: Use check_same_thread=False to allow InterruptibleSQLiteQuery
            #         to use the connection from a background thread
            try:
                conn = sqlite3.connect(
                    source_path, 
                    timeout=SPATIALITE_QUERY_TIMEOUT,
                    check_same_thread=False  # Required for InterruptibleSQLiteQuery background thread
                )
                conn.enable_load_extension(True)
                conn.load_extension(ext_name)
                cursor = conn.cursor()
            except Exception as conn_error:
                QgsMessageLog.logMessage(
                    f"_apply_filter_direct_sql CONNECTION ERROR for {layer.name()}: {str(conn_error)}",
                    "FilterMate", Qgis.Critical
                )
                return False
            
            # v2.6.2: Set SQLite busy timeout to prevent freezing
            cursor.execute(f"PRAGMA busy_timeout = {SPATIALITE_QUERY_TIMEOUT * 1000}")
            
            # Build a SELECT query to get matching FIDs
            # The expression is a WHERE clause, we need to extract the conditions
            # and build a SELECT fid FROM table WHERE expression query
            
            # Get the primary key column name (usually 'fid' for GeoPackage)
            pk_col = 'fid'  # Default for GeoPackage
            try:
                pk_indices = layer.primaryKeyAttributes()
                if pk_indices:
                    fields = layer.fields()
                    pk_col = fields.at(pk_indices[0]).name()
            except Exception:
                pass
            
            # v2.9.19: FIX - Get feature count for optimization threshold check
            feature_count = layer.featureCount()
            
            # v2.6.5: Check for very large WKT and use bounding box pre-filter
            # This dramatically reduces the number of geometry comparisons needed
            # v2.6.8: CRITICAL FIX - Validate geometry column exists in table
            #         OGR providers may return 'geometry' as default even when actual column is 'geom'
            geom_col = None
            provider_geom_col = None
            try:
                provider_geom_col = layer.dataProvider().geometryColumn()
            except (AttributeError, RuntimeError):
                pass
            
            # Get actual columns from table to validate
            actual_columns = []
            try:
                cursor.execute(f'PRAGMA table_info("{table_name}")')
                actual_columns = [row[1] for row in cursor.fetchall()]
            except Exception:
                pass
            
            # Only trust provider's geometry column if it exists in the table
            if provider_geom_col and actual_columns and provider_geom_col in actual_columns:
                geom_col = provider_geom_col
            elif actual_columns:
                # Fallback: detect from table columns
                if 'geom' in actual_columns:
                    geom_col = 'geom'
                elif 'geometry' in actual_columns:
                    geom_col = 'geometry'
                else:
                    # Look for any geometry-like column
                    for col in actual_columns:
                        if 'geom' in col.lower():
                            geom_col = col
                            break
            
            if not geom_col:
                geom_col = 'geom'  # Default for GeoPackage (most common)
            
            is_geopackage = '.gpkg' in layer.source().lower()
            
            use_bbox_prefilter = False
            bbox_filter = None
            source_wkt = None
            
            if hasattr(self, 'task_params') and self.task_params:
                infos = self.task_params.get('infos', {})
                source_wkt = infos.get('source_geom_wkt', '')
                
                if source_wkt and len(source_wkt) >= self.VERY_LARGE_WKT_THRESHOLD:
                    # Very large WKT - use bbox pre-filter
                    bbox = self._get_wkt_bounding_box(source_wkt)
                    if bbox:
                        # Get target layer SRID
                        target_srid = 4326
                        crs = layer.crs()
                        if crs and crs.isValid() and ':' in crs.authid():
                            try:
                                target_srid = int(crs.authid().split(':')[1])
                            except (ValueError, IndexError):
                                pass
                        
                        bbox_filter = self._build_bbox_prefilter(geom_col, bbox, target_srid, is_geopackage)
                        use_bbox_prefilter = True
                        self.log_info(f"📦 Very large WKT ({len(source_wkt)} chars) - using bbox pre-filter for performance")
            
            # Build the SELECT query
            # The expression is the WHERE clause from build_expression
            
            # v2.8.8: CRITICAL FIX - Include old_subset FID filter in SQL query
            # When re-filtering (e.g., adding buffer), old_subset may contain a FID filter
            # from the previous filtering. If we don't include it, we query ALL features
            # instead of just the previously filtered ones, returning wrong results.
            # 
            # v2.9.34: CRITICAL FIX - Don't combine FID-only filters in multi-step spatial filtering
            # FID filters from previous spatial steps are based on a DIFFERENT source geometry
            # and must be REPLACED, not combined. Only combine true user attribute filters.
            old_subset_sql_filter = ""
            if old_subset:
                old_subset_upper = old_subset.upper()
                # Check if old_subset is a simple FID filter (not spatial predicate)
                has_source_alias = '__source' in old_subset.lower()
                has_exists = 'EXISTS (' in old_subset_upper or 'EXISTS(' in old_subset_upper
                spatial_predicates = [
                    'ST_INTERSECTS', 'ST_CONTAINS', 'ST_WITHIN', 'ST_TOUCHES',
                    'ST_OVERLAPS', 'ST_CROSSES', 'ST_DISJOINT', 'ST_EQUALS',
                    'INTERSECTS', 'CONTAINS', 'WITHIN', 'GEOMFROMTEXT', 'GEOMFROMGPB'
                ]
                has_spatial_predicate = any(pred in old_subset_upper for pred in spatial_predicates)
                
                # v2.9.34: Check if old_subset is ONLY a FID filter (from previous spatial step)
                # v3.0.5: CRITICAL FIX - Dynamic FID regex to support any primary key name
                # The regex now uses pk_col variable instead of hardcoded 'fid'
                # Supports: fid, id, ogc_fid, gid, node_id, AGG_ID, etc.
                import re
                # Escape pk_col for regex safety (prevent injection)
                pk_col_escaped = re.escape(pk_col)
                # Build regex pattern dynamically: matches quoted or unquoted pk_col with IN/=/BETWEEN
                is_fid_only = bool(re.match(
                    rf'^\s*\(?\s*(["\']?){pk_col_escaped}\1\s+(IN\s*\(|=\s*-?\d+|BETWEEN\s+)',
                    old_subset,
                    re.IGNORECASE
                ))
                
                # v3.0.3: CRITICAL FIX - FID filters from step 1 MUST be combined in multi-step filtering!
                # Previously, is_fid_only caused replacement which lost the step 1 filter results.
                # This meant distant layers showed ALL features instead of intersection of step 1 AND step 2.
                if not has_source_alias and not has_exists and not has_spatial_predicate:
                    # old_subset is either:
                    # 1. A true user attribute filter (not FID) - ALWAYS combine
                    # 2. A FID filter from step 1 (is_fid_only=True) - MUST combine for multi-step!
                    old_subset_sql_filter = f"({old_subset}) AND "
                    # v2.9.44/v3.0.3: Enhanced logging
                    if is_fid_only:
                        self.log_info(f"✅ Combining FID filter from step 1 with new spatial filter (MULTI-STEP)")
                        self.log_info(f"  → FID filter: {old_subset[:80]}...")
                        self.log_info(f"  → This ensures intersection of step 1 AND step 2 results")
                    else:
                        self.log_info(f"✅ Combining old attribute filter with new spatial filter")
                        self.log_info(f"  → Old filter: {old_subset[:80]}...")
                else:
                    # old_subset contains spatial predicates - will be replaced, not combined
                    # v2.9.44: Enhanced logging for debugging
                    self.log_info(f"⚠️ Old subset has spatial predicates - will be replaced")
                    self.log_info(f"  → has_source_alias={has_source_alias}")
                    self.log_info(f"  → has_exists={has_exists}")
                    self.log_info(f"  → has_spatial_predicate={has_spatial_predicate}")
                    if old_subset:
                        self.log_info(f"  → Old subset: {old_subset[:80]}...")
            
            # v2.9.33: Log old_subset_sql_filter for debugging
            QgsMessageLog.logMessage(
                f"  → old_subset_sql_filter: '{old_subset_sql_filter[:100] if old_subset_sql_filter else '(empty)'}'",
                "FilterMate", Qgis.Info
            )
            
            if use_bbox_prefilter and bbox_filter:
                # Use two-stage filtering: fast bbox check first, then precise geometry test
                select_query = f'SELECT "{pk_col}" FROM "{table_name}" WHERE {old_subset_sql_filter}({bbox_filter}) AND ({expression})'
                self.log_info(f"  → Using two-stage filter: bbox → geometry")
            else:
                select_query = f'SELECT "{pk_col}" FROM "{table_name}" WHERE {old_subset_sql_filter}{expression}'
            
            self.log_info(f"  → Direct SQL query: {select_query[:200]}...")
            # v2.9.33: Log if old_subset was included in query
            if old_subset_sql_filter:
                QgsMessageLog.logMessage(
                    f"  ✓ Query INCLUDES previous filter (old_subset combined)",
                    "FilterMate", Qgis.Info
                )
            else:
                QgsMessageLog.logMessage(
                    f"  ⚠️ Query does NOT include previous filter (new filter only)",
                    "FilterMate", Qgis.Info
                )
            # v2.6.4: Also log to QgsMessageLog for visibility
            QgsMessageLog.logMessage(
                f"_apply_filter_direct_sql: Executing query ({len(select_query)} chars) for {layer.name()}",
                "FilterMate", Qgis.Info
            )
            
            # v2.6.2: Check cancellation before long query
            if self._is_task_canceled():
                self.log_info("Filter cancelled before SQL execution")
                conn.close()
                return False
            
            # v2.6.2: Execute the query using interruptible wrapper
            # This runs the query in a background thread and allows cancellation
            self.log_info(f"  → Executing interruptible query (timeout: {SPATIALITE_QUERY_TIMEOUT}s)...")
            
            try:
                interruptible_query = InterruptibleSQLiteQuery(conn, select_query)
                results, error = interruptible_query.execute(
                    timeout=SPATIALITE_QUERY_TIMEOUT,
                    cancel_check=self._is_task_canceled
                )
                
                if error:
                    error_msg = str(error)
                    # v2.6.4: Log errors to QgsMessageLog for visibility
                    QgsMessageLog.logMessage(
                        f"_apply_filter_direct_sql SQL ERROR for {layer.name()}: {error_msg}",
                        "FilterMate", Qgis.Warning
                    )
                    if "cancelled" in error_msg.lower():
                        self.log_info(f"Query cancelled by user")
                        conn.close()
                        return False
                    elif "timeout" in error_msg.lower():
                        self.log_error(f"Query timeout after {SPATIALITE_QUERY_TIMEOUT}s - geometry too complex")
                        self.log_error(f"  → Consider using smaller source geometry or PostgreSQL backend")
                        conn.close()
                        return False
                    # v2.9.28: Detect RTTOPO MakeValid errors and explain to user
                    elif "makevalid" in error_msg.lower() or "rttopo" in error_msg.lower():
                        self.log_warning(f"Spatialite RTTOPO error with complex geometry - will use OGR fallback")
                        self.log_info(f"  → Error: {error_msg}")
                        # v2.9.28: Don't show as error since OGR fallback will handle it
                        conn.close()
                        return False
                    else:
                        self.log_error(f"Direct SQL query failed: {error}")
                        conn.close()
                        return False
                
                matching_fids = [row[0] for row in results]
                        
            except Exception as sql_error:
                self.log_error(f"Direct SQL query failed: {sql_error}")
                # v2.6.4: Log exception to QgsMessageLog for visibility
                QgsMessageLog.logMessage(
                    f"_apply_filter_direct_sql SQL EXCEPTION for {layer.name()}: {str(sql_error)}",
                    "FilterMate", Qgis.Warning
                )
                conn.close()
                return False
            
            conn.close()
            
            # DIAGNOSTIC v2.4.11: Log number of matching FIDs to QGIS message panel
            from qgis.core import QgsMessageLog, Qgis
            QgsMessageLog.logMessage(
                f"  → Direct SQL found {len(matching_fids)} matching FIDs for {layer.name()}",
                "FilterMate", Qgis.Info
            )
            self.log_info(f"  → Found {len(matching_fids)} matching features via direct SQL")
            
            # v2.8.8: Use shared cache_helpers for consistent behavior
            source_wkt = ""
            predicates_list = []
            buffer_val = 0.0
            if hasattr(self, 'task_params') and self.task_params:
                source_wkt, buffer_val, predicates_list = get_cache_parameters_from_task(self.task_params) if get_cache_parameters_from_task else ("", 0.0, [])
            
            # v2.8.8: Use cache_helpers for multi-step intersection (supports AND/OR/NOT AND)
            step_number = 1
            if CACHE_AVAILABLE and perform_cache_intersection and old_subset:
                cache_operator = get_combine_operator_from_task(self.task_params) if get_combine_operator_from_task else None
                cache_result = perform_cache_intersection(
                    layer=layer,
                    matching_fids=matching_fids,
                    source_wkt=source_wkt,
                    buffer_value=buffer_val,
                    predicates_list=predicates_list,
                    old_subset=old_subset,
                    combine_operator=cache_operator,
                    logger=self,
                    backend_name="Spatialite Direct SQL"
                )
                if cache_result.was_intersected:
                    matching_fids = cache_result.fid_list
                    step_number = cache_result.step_number
            
            # v2.8.8: Store result using cache_helpers
            QgsMessageLog.logMessage(
                f"  📦 Cache check: AVAILABLE={CACHE_AVAILABLE}, fids_count={len(matching_fids)}",
                "FilterMate", Qgis.Info
            )
            if CACHE_AVAILABLE and store_filter_result and matching_fids:
                store_filter_result(
                    layer=layer,
                    matching_fids=matching_fids,
                    source_wkt=source_wkt,
                    buffer_value=buffer_val,
                    predicates_list=predicates_list,
                    step_number=step_number,
                    logger=self,
                    backend_name="Spatialite Direct SQL"
                )
            
            if len(matching_fids) == 0:
                # v2.9.40: FALLBACK - When Spatialite returns 0 features, trigger OGR fallback
                # This handles cases where Spatialite SQL succeeded but returned incorrect results
                # (e.g., MakeValid errors that don't raise exceptions but return empty sets)
                
                # Check if this is a multi-step filter continuation (already has cache)
                is_multistep_continuation = False
                if SPATIALITE_CACHE_AVAILABLE and old_subset:
                    # v2.9.40: Get source WKT to check cache
                    source_wkt_for_cache = ""
                    predicates_list_for_cache = []
                    buffer_val_for_cache = 0.0
                    if hasattr(self, 'task_params') and self.task_params:
                        infos = self.task_params.get('infos', {})
                        source_wkt_for_cache = infos.get('source_geom_wkt', '')
                        geom_preds = self.task_params.get('filtering', {}).get('geometric_predicates', [])
                        if isinstance(geom_preds, dict):
                            predicates_list_for_cache = list(geom_preds.keys())
                        elif isinstance(geom_preds, list):
                            predicates_list_for_cache = geom_preds
                        # FIX v3.0.12: Clean buffer value from float precision errors
                        buffer_val_for_cache = clean_buffer_value(self.task_params.get('filtering', {}).get('buffer_value', 0.0))
                    
                    previous_fids = get_previous_filter_fids(layer, source_wkt_for_cache, buffer_val_for_cache, predicates_list_for_cache)
                    is_multistep_continuation = (previous_fids is not None and len(previous_fids) > 0)
                
                # If NOT a multi-step continuation, return False to trigger OGR fallback
                # Multi-step filters can legitimately return 0 (intersection of sets)
                if not is_multistep_continuation:
                    self.log_warning(f"⚠️ Spatialite returned 0 features - this may indicate query error")
                    self.log_warning(f"  → Returning False to trigger OGR fallback verification")
                    QgsMessageLog.logMessage(
                        f"⚠️ {layer.name()}: Spatialite found 0 features - attempting OGR fallback",
                        "FilterMate", Qgis.Warning
                    )
                    return False  # Trigger OGR fallback
                
                # Multi-step continuation with 0 results - this is valid (empty intersection)
                # v2.6.9: FIX - Use unquoted 'fid = -1' for OGR/GeoPackage compatibility
                fid_expression = 'fid = -1'  # No valid FID is -1
                self.log_info(f"  → Multi-step filter resulted in 0 features (valid empty intersection)")
            elif len(matching_fids) >= feature_count * 0.99 and feature_count > 10000:
                # v2.9.11: OPTIMIZATION - Skip filter when 99%+ features match
                # Applying a filter for 99%+ of features is wasteful - the filter expression
                # can be huge (millions of FIDs), slow to parse, and provides no real filtering.
                unmatched_count = feature_count - len(matching_fids)
                match_ratio = len(matching_fids) / feature_count * 100
                self.log_info(f"⚡ OPTIMIZATION: {match_ratio:.2f}% of features matched ({len(matching_fids):,}/{feature_count:,})")
                self.log_info(f"   Only {unmatched_count:,} features excluded - skipping expensive FID filter")
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"⚡ {layer.name()}: {match_ratio:.1f}% match - filter skipped (source geometry covers most of layer)",
                    "FilterMate", Qgis.Info
                )
                # Clear filter to show all features (most efficient)
                fid_expression = ''
            elif len(matching_fids) >= self.LARGE_FID_TABLE_THRESHOLD:
                # v2.8.9: FIX - Use range-based filter instead of FID table subquery
                # The subquery "fid IN (SELECT fid FROM _fm_fids_xxx)" does NOT work
                # with setSubsetString() because the OGR provider doesn't support
                # SQL subqueries in filter expressions. Range-based is compatible.
                
                sorted_fids = sorted(matching_fids)
                min_fid, max_fid = sorted_fids[0], sorted_fids[-1]
                self.log_info(f"  📊 FID analysis: {len(matching_fids):,} FIDs in range {min_fid}-{max_fid}")
                
                # Use range-based filter for OGR compatibility (no subqueries)
                fid_expression = self._build_range_based_filter(pk_col, matching_fids)
                    
            elif len(matching_fids) > 10000:
                # Large result set - warn but still use IN filter
                self.log_warning(
                    f"Large result set ({len(matching_fids)} FIDs). "
                    f"Consider PostgreSQL for better performance."
                )
                # v2.8.10: FIX - Use unquoted fid for OGR/GeoPackage compatibility
                col_ref = 'fid' if pk_col == 'fid' else f'"{pk_col}"'
                fid_expression = f'{col_ref} IN ({", ".join(str(fid) for fid in matching_fids)})'
            else:
                # v2.8.10: FIX - Use unquoted fid for OGR/GeoPackage compatibility
                col_ref = 'fid' if pk_col == 'fid' else f'"{pk_col}"'
                fid_expression = f'{col_ref} IN ({", ".join(str(fid) for fid in matching_fids)})'
            
            # v2.8.10: FIX - Combine with old_subset correctly
            # If old_subset was already included in SQL query via old_subset_sql_filter,
            # DON'T re-combine - the matching_fids already reflect the intersection
            if old_subset and not old_subset_sql_filter:
                # old_subset was NOT included in SQL (had spatial predicates) - just use new FIDs
                self.log_info(f"🔄 Old subset had spatial predicates - replacing with new FID filter")
                final_expression = fid_expression
            elif old_subset and old_subset_sql_filter:
                # old_subset WAS included in SQL - matching_fids already combined, use as-is
                self.log_info(f"  → FID filter already combined in SQL query, using result directly")
                final_expression = fid_expression
            else:
                final_expression = fid_expression
            
            self.log_info(f"  → Applying FID-based filter: {len(final_expression)} chars")
            
            # DIAGNOSTIC v2.4.11: Log first few FIDs to verify correct filtering
            from qgis.core import QgsMessageLog, Qgis
            if matching_fids and len(matching_fids) > 0:
                fid_preview = matching_fids[:10]
                QgsMessageLog.logMessage(
                    f"  → FID-based filter for {layer.name()}: first FIDs = {fid_preview}{'...' if len(matching_fids) > 10 else ''}",
                    "FilterMate", Qgis.Info
                )
            
            # Apply the FID-based filter using queue callback or direct
            queue_callback = self.task_params.get('_subset_queue_callback')
            
            if queue_callback:
                queue_callback(layer, final_expression)
                result = True
            else:
                result = safe_set_subset_string(layer, final_expression)
            
            elapsed = time.time() - start_time
            
            if result:
                self.log_info(
                    f"✓ {layer.name()}: {len(matching_fids)} features via direct SQL ({elapsed:.2f}s)"
                )
            else:
                self.log_error(f"✗ Direct SQL filter failed for {layer.name()}")
            
            return result
            
        except Exception as e:
            self.log_error(f"Exception in direct SQL filter: {str(e)}")
            import traceback
            self.log_debug(f"Traceback: {traceback.format_exc()}")
            # v2.6.3: Also log to QGIS Message Log for user visibility
            from qgis.core import QgsMessageLog, Qgis
            QgsMessageLog.logMessage(
                f"_apply_filter_direct_sql EXCEPTION for {layer.name()}: {str(e)}",
                "FilterMate", Qgis.Critical
            )
            return False
    
    def get_backend_name(self) -> str:
        """Get backend name"""
        return "Spatialite"
    
    def _apply_filter_with_source_table(
        self,
        layer: QgsVectorLayer,
        old_subset: Optional[str] = None,
        combine_operator: Optional[str] = None
    ) -> bool:
        """
        v2.6.1: Apply filter using a permanent source geometry table with R-tree index.
        
        This is the OPTIMIZED path for large datasets. Instead of parsing WKT inline
        for every feature, we:
        1. Create a permanent table with source geometry (+ optional buffer)
        2. Create R-tree spatial index on the table
        3. Use EXISTS with indexed spatial join for O(log n) lookups
        4. Apply FID-based filter to the layer
        
        Performance benefits:
        - R-tree index: O(log n) spatial lookups vs O(n) for inline WKT
        - Pre-computed buffer geometry (no recalculation per feature)
        - Single WKT parse (at table creation) vs N parses
        
        Called when:
        - Target layer has > LARGE_DATASET_THRESHOLD features (10k)
        - mod_spatialite is available
        - Source WKT is available in task_params
        
        Args:
            layer: GeoPackage/SQLite layer to filter
            old_subset: Existing subset string
            combine_operator: Operator to combine filters (AND/OR)
        
        Returns:
            True if filter applied successfully
        """
        import time
        start_time = time.time()
        
        # v2.6.6: Log entry to QgsMessageLog for debugging
        from qgis.core import QgsMessageLog, Qgis
        QgsMessageLog.logMessage(
            f"_apply_filter_with_source_table: Starting for {layer.name()}",
            "FilterMate", Qgis.Info
        )
        
        # FIX v3.1.1: DISABLED early cancellation check
        # This check can return spurious True after exceptions in previous layers,
        # causing subsequent layers to be skipped incorrectly.
        # The user did NOT actually cancel - we MUST continue filtering.
        # if self._is_task_canceled():
        #     self.log_info("Filter cancelled before starting source table optimization")
        #     from qgis.core import QgsMessageLog, Qgis
        #     QgsMessageLog.logMessage(
        #         f"{layer.name()}: Filter cancelled before starting source table optimization",
        #         "FilterMate", Qgis.Warning
        #     )
        #     return False
        
        # v2.6.10: Get feature count for progress estimation
        # CRITICAL FIX v3.0.19: Protect against None/invalid feature count
        raw_feature_count = layer.featureCount()
        feature_count = raw_feature_count if raw_feature_count is not None and raw_feature_count >= 0 else 0
        
        try:
            # Get file path
            source = layer.source()
            source_path = source.split('|')[0] if '|' in source else source
            
            # Verify source is a local file
            if not os.path.isfile(source_path):
                self.log_error(f"Source file not found: {source_path}")
                return False
            
            # Get table name
            target_table = None
            if '|layername=' in source:
                target_table = source.split('|layername=')[1].split('|')[0]
            if not target_table:
                from qgis.core import QgsDataSourceUri
                uri = QgsDataSourceUri(source)
                target_table = uri.table()
            if not target_table:
                self.log_error("Could not determine table name")
                return False
            
            # Get source WKT and parameters from task_params
            source_wkt = None
            source_srid = 4326
            buffer_value = 0
            predicates = {}
            
            if hasattr(self, 'task_params') and self.task_params:
                infos = self.task_params.get('infos', {})
                source_wkt = infos.get('source_geom_wkt')
                
                # Get source SRID
                source_crs = infos.get('layer_crs_authid', '')
                if ':' in str(source_crs):
                    try:
                        source_srid = int(source_crs.split(':')[1])
                    except (ValueError, IndexError):
                        pass
                
                # Get buffer value
                # v2.6.11 FIX: buffer_value is nested under 'filtering' in task_params
                # FIX v3.0.12: Clean buffer value from float precision errors
                # FIX v3.0.10: Check buffer_state for multi-step filter preservation
                filtering_params = self.task_params.get('filtering', {})
                buffer_state = infos.get('buffer_state', {})

                # Check if buffer is already applied from previous step
                is_pre_buffered = buffer_state.get('is_pre_buffered', False)
                buffer_column = buffer_state.get('buffer_column', 'geom')
                previous_buffer_value = buffer_state.get('previous_buffer_value')
                buffer_value = clean_buffer_value(buffer_state.get('buffer_value', filtering_params.get('buffer_value', 0)))

                if is_pre_buffered and buffer_value != 0:
                    self.log_info(f"  ✓ Multi-step filter: Buffer already applied ({buffer_value}m) - will use {buffer_column} column")
                elif previous_buffer_value is not None and previous_buffer_value != buffer_value:
                    self.log_warning(f"  ⚠️  Multi-step filter: Buffer changed ({previous_buffer_value}m → {buffer_value}m) - will recompute source table")

                # Get predicates
                predicates = self.task_params.get('predicates', {})
            
            if not source_wkt:
                self.log_error("No source WKT in task_params - cannot use source table optimization")
                return False
            
            # Clean up old source tables first (1 hour max age)
            self._cleanup_permanent_source_tables(source_path, max_age_seconds=3600)
            
            # Get target layer SRID
            target_srid = 4326
            crs = layer.crs()
            if crs and crs.isValid() and ':' in crs.authid():
                try:
                    target_srid = int(crs.authid().split(':')[1])
                except (ValueError, IndexError):
                    pass
            
            # Determine if we need CRS transformation
            is_geographic = target_srid == 4326 or (layer.crs().isGeographic() if layer.crs() else False)
            
            self.log_info(f"🚀 Using permanent source table optimization for {layer.name()}")
            self.log_info(f"  → Target: {target_table}, SRID: {target_srid}")
            self.log_info(f"  → Buffer: {buffer_value}m, Geographic: {is_geographic}")
            
            # v2.6.11: Log buffer value to QGIS MessageLog for visibility
            from qgis.core import QgsMessageLog, Qgis
            if buffer_value != 0:
                QgsMessageLog.logMessage(
                    f"{layer.name()}: Using buffer={buffer_value}m for source table optimization",
                    "FilterMate", Qgis.Info
                )
            
            # FIX v3.0.10: Check if source table already exists from previous step (multi-step filter)
            # If buffer is pre-applied and matches current buffer, reuse existing source table
            existing_source_table = infos.get('source_table_name')
            source_table = None
            has_buffer = False

            if is_pre_buffered and existing_source_table:
                # Verify table still exists in database
                try:
                    # FIX v3.1.1: Use global sqlite3 import (line 40) instead of local import
                    # Local imports inside conditionals cause Python UnboundLocalError
                    conn = sqlite3.connect(source_path, check_same_thread=False)
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (existing_source_table,))
                    table_exists = cursor.fetchone() is not None
                    conn.close()

                    if table_exists:
                        source_table = existing_source_table
                        has_buffer = buffer_value != 0
                        self.log_info(f"  ✓ Reusing existing source table '{source_table}' from previous step (with {buffer_value}m buffer)")
                    else:
                        self.log_warning(f"  ⚠️  Previous source table '{existing_source_table}' no longer exists - will create new one")
                except Exception as e:
                    self.log_warning(f"  ⚠️  Could not verify existing source table: {e} - will create new one")

            # Create new source table if not reusing existing one
            if not source_table:
                # Create permanent source table with geometry (and buffer if needed)
                # For geographic CRS with buffer, we need to handle projection
                effective_buffer = 0
                if buffer_value != 0 and not is_geographic:
                    # Projected CRS: can apply buffer directly in source SRID
                    effective_buffer = buffer_value
                # For geographic CRS, we'll handle buffer in the SQL query itself

                source_table, has_buffer = self._create_permanent_source_table(
                    db_path=source_path,
                    source_wkt=source_wkt,
                    source_srid=source_srid,
                    buffer_value=effective_buffer,
                    source_features=None  # Single geometry for now
                )

                if not source_table:
                    from qgis.core import QgsMessageLog, Qgis
                    self.log_warning("Could not create source table - falling back to inline WKT")
                    QgsMessageLog.logMessage(
                        f"Source table creation failed for {layer.name()} - WKT may be too large ({len(source_wkt) if source_wkt else 0:,} chars)",
                        "FilterMate", Qgis.Warning
                    )
                    return False

                # Store source table name in infos for potential reuse in next step
                if hasattr(self, 'task_params') and self.task_params:
                    if 'infos' not in self.task_params:
                        self.task_params['infos'] = {}
                    self.task_params['infos']['source_table_name'] = source_table
                    self.log_info(f"  ✓ Stored source table name '{source_table}' for potential reuse in multi-step filter")
            
            # Get mod_spatialite extension
            mod_available, ext_name = _test_mod_spatialite_available()
            if not mod_available:
                self.log_error("mod_spatialite not available")
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"{layer.name()}: mod_spatialite extension not available - cannot use source table optimization",
                    "FilterMate", Qgis.Warning
                )
                return False
            
            # v2.6.2: Check cancellation before connecting
            if self._is_task_canceled():
                self.log_info("Filter cancelled before database connection")
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"{layer.name()}: Filter cancelled before database connection",
                    "FilterMate", Qgis.Warning
                )
                self._drop_source_table(source_path, source_table)
                return False
            
            # v2.6.2: Connect and build optimized query with timeout
            # v2.6.4: Use check_same_thread=False for InterruptibleSQLiteQuery background thread
            conn = sqlite3.connect(
                source_path, 
                timeout=SPATIALITE_QUERY_TIMEOUT,
                check_same_thread=False  # Required for InterruptibleSQLiteQuery background thread
            )
            conn.enable_load_extension(True)
            conn.load_extension(ext_name)
            cursor = conn.cursor()
            
            # v2.6.2: Set SQLite busy timeout to prevent freezing
            cursor.execute(f"PRAGMA busy_timeout = {SPATIALITE_QUERY_TIMEOUT * 1000}")
            
            # Get geometry column of target layer
            # v2.6.6: Use dataProvider().geometryColumn() - QgsVectorLayer doesn't have geometryColumn() directly
            # v2.6.8: CRITICAL FIX - Validate the column actually exists in the table
            #         OGR providers may return 'geometry' as default even when actual column is 'geom'
            geom_col = None
            provider_geom_col = None
            try:
                provider_geom_col = layer.dataProvider().geometryColumn()
            except (AttributeError, RuntimeError):
                pass
            
            # v2.6.8: Get actual columns from table to validate provider's answer
            actual_columns = []
            try:
                cursor.execute(f'PRAGMA table_info("{target_table}")')
                actual_columns = [row[1] for row in cursor.fetchall()]
            except Exception as e:
                self.log_debug(f"Could not query table_info for validation: {e}")
            
            # v2.6.8: Only trust provider's geometry column if it actually exists in the table
            if provider_geom_col and provider_geom_col in actual_columns:
                geom_col = provider_geom_col
                self.log_info(f"  → Geometry column from provider (validated): '{geom_col}'")
            
            # v2.6.7: If provider doesn't return valid geometry column, query gpkg_geometry_columns table
            if not geom_col:
                try:
                    cursor.execute(
                        "SELECT column_name FROM gpkg_geometry_columns WHERE table_name = ?",
                        (target_table,)
                    )
                    result = cursor.fetchone()
                    if result and result[0]:
                        geom_col = result[0]
                        self.log_info(f"  → Geometry column from gpkg_geometry_columns: '{geom_col}'")
                except Exception as e:
                    self.log_debug(f"Could not query gpkg_geometry_columns: {e}")
            
            # Final fallback - try 'geom' first (common in GeoPackage), then 'geometry'
            if not geom_col:
                # v2.6.8: Use already-fetched actual_columns to avoid re-query
                columns = actual_columns
                if not columns:
                    # Fallback if we don't have columns yet
                    try:
                        cursor.execute(f'PRAGMA table_info("{target_table}")')
                        columns = [row[1] for row in cursor.fetchall()]
                    except Exception as e:
                        self.log_debug(f"Could not query table_info: {e}")
                
                if columns:
                    if 'geom' in columns:
                        geom_col = 'geom'
                    elif 'geometry' in columns:
                        geom_col = 'geometry'
                    else:
                        # Look for any geometry-like column name
                        for col in columns:
                            if 'geom' in col.lower():
                                geom_col = col
                                break
                    if geom_col:
                        self.log_info(f"  → Geometry column detected from PRAGMA: '{geom_col}'")
            
            if not geom_col:
                geom_col = 'geom'  # Default for GeoPackage (most common)
                self.log_warning(f"  → Using default geometry column: '{geom_col}'")
            
            # Get primary key column
            pk_col = 'fid'  # Default for GeoPackage
            try:
                pk_indices = layer.primaryKeyAttributes()
                if pk_indices:
                    fields = layer.fields()
                    pk_col = fields.at(pk_indices[0]).name()
            except Exception:
                pass
            
            # Build the optimized spatial query using EXISTS with the source table
            # The R-tree index on the source table makes this O(log n)
            
            # Determine which geometry column to use (buffered or not)
            source_geom_col = 'geom_buffered' if has_buffer else 'geom'
            
            # v2.8.10: Check if this is a negative buffer (erosion) case
            # Negative buffers can produce empty geometries which need special handling
            is_negative_buffer = buffer_value < 0
            
            # Build source geometry expression with any needed transformations
            if is_geographic and buffer_value != 0 and not has_buffer:
                # FIX v3.0.12: Use unified geographic CRS transformation helper
                # Geographic CRS with buffer but not pre-computed - apply buffer via projection to 3857
                source_expr = self._apply_geographic_buffer_transform(
                    's.geom',  # Source column from permanent source table
                    source_srid=source_srid,
                    target_srid=target_srid,
                    buffer_value=buffer_value,
                    dialect='spatialite'
                )
            elif source_srid != target_srid:
                # Need CRS transformation
                # v2.8.10: Handle empty geometries from negative buffer
                if is_negative_buffer and has_buffer:
                    source_expr = f"CASE WHEN ST_IsEmpty(s.{source_geom_col}) = 1 OR s.{source_geom_col} IS NULL THEN NULL ELSE ST_Transform(s.{source_geom_col}, {target_srid}) END"
                else:
                    source_expr = f'ST_Transform(s.{source_geom_col}, {target_srid})'
            else:
                # v2.8.10: Handle empty geometries from negative buffer
                if is_negative_buffer and has_buffer:
                    source_expr = f"CASE WHEN ST_IsEmpty(s.{source_geom_col}) = 1 OR s.{source_geom_col} IS NULL THEN NULL ELSE s.{source_geom_col} END"
                else:
                    source_expr = f's.{source_geom_col}'
            
            # Normalize predicates to get SQL function names
            index_to_func = {
                '0': 'ST_Intersects', '1': 'ST_Contains', '2': 'ST_Disjoint', '3': 'ST_Equals',
                '4': 'ST_Touches', '5': 'ST_Overlaps', '6': 'ST_Within', '7': 'ST_Crosses'
            }
            
            # v2.6.6: CRITICAL FIX - GeoPackage stores geometry in GPB format
            # We need GeomFromGPB() to convert to Spatialite geometry before spatial predicates
            # Check if target is GeoPackage by file extension
            is_geopackage = source_path.lower().endswith('.gpkg')
            if is_geopackage:
                target_geom_expr = f'GeomFromGPB(t."{geom_col}")'
                self.log_info(f"  → GeoPackage detected: using GeomFromGPB() for target geometry")
            else:
                target_geom_expr = f't."{geom_col}"'
            
            predicate_conditions = []
            # v2.8.12: FIX - predicates can be list or dict
            predicate_keys = list(predicates.keys()) if isinstance(predicates, dict) else (predicates if isinstance(predicates, list) else [])
            for key in predicate_keys:
                if key in index_to_func:
                    func = index_to_func[key]
                elif key.upper().startswith('ST_'):
                    func = key
                else:
                    func = f'ST_{key.capitalize()}'
                
                predicate_conditions.append(f'{func}({target_geom_expr}, {source_expr}) = 1')
            
            if not predicate_conditions:
                # Default to intersects
                predicate_conditions = [f'ST_Intersects({target_geom_expr}, {source_expr}) = 1']
            
            # v2.6.9: CRITICAL PERFORMANCE FIX - Add bounding box pre-filter
            # The EXISTS query was scanning ALL target features (O(n)) without using
            # the target table's R-tree spatial index. Adding MbrIntersects pre-filter
            # reduces the search space dramatically (from 119k to ~1k features).
            # Get bounding box from source table for pre-filtering
            bbox_prefilter = ""
            rtree_prefilter = ""
            try:
                source_geom_for_bbox = 'geom_buffered' if has_buffer else 'geom'
                cursor.execute(f'''
                    SELECT MbrMinX({source_geom_for_bbox}), MbrMinY({source_geom_for_bbox}),
                           MbrMaxX({source_geom_for_bbox}), MbrMaxY({source_geom_for_bbox})
                    FROM "{source_table}"
                    WHERE {source_geom_for_bbox} IS NOT NULL
                    LIMIT 1
                ''')
                bbox_result = cursor.fetchone()
                if bbox_result and all(v is not None for v in bbox_result):
                    minx, miny, maxx, maxy = bbox_result
                    # Add small expansion to bbox for edge cases (0.1% of extent)
                    dx = max((maxx - minx) * 0.001, 1.0)  # At least 1 unit
                    dy = max((maxy - miny) * 0.001, 1.0)
                    minx -= dx
                    miny -= dy
                    maxx += dx
                    maxy += dy
                    
                    # v2.6.9: For GeoPackage, check if R-tree table exists and use it directly
                    # GeoPackage R-tree tables are named rtree_<table>_<geom>
                    if is_geopackage:
                        rtree_table = f"rtree_{target_table}_{geom_col}"
                        try:
                            # Check if R-tree table exists
                            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (rtree_table,))
                            if cursor.fetchone():
                                # Use R-tree virtual table for O(log n) filtering
                                rtree_prefilter = f'''t."{pk_col}" IN (
                                    SELECT id FROM "{rtree_table}"
                                    WHERE minx <= {maxx} AND maxx >= {minx}
                                    AND miny <= {maxy} AND maxy >= {miny}
                                ) AND '''
                                self.log_info(f"  → Using GeoPackage R-tree: {rtree_table}")
                                self.log_info(f"  → BBox filter: ({minx:.1f},{miny:.1f})-({maxx:.1f},{maxy:.1f})")
                            else:
                                # Fallback to MbrIntersects (slower)
                                bbox_wkt = f"POLYGON(({minx} {miny}, {maxx} {miny}, {maxx} {maxy}, {minx} {maxy}, {minx} {miny}))"
                                bbox_prefilter = f"MbrIntersects({target_geom_expr}, GeomFromText('{bbox_wkt}', {target_srid})) = 1 AND "
                                self.log_info(f"  → No R-tree found, using MbrIntersects fallback")
                                self.log_info(f"  → BBox filter: ({minx:.1f},{miny:.1f})-({maxx:.1f},{maxy:.1f})")
                        except Exception as rtree_err:
                            self.log_debug(f"R-tree check failed: {rtree_err}")
                            bbox_wkt = f"POLYGON(({minx} {miny}, {maxx} {miny}, {maxx} {maxy}, {minx} {maxy}, {minx} {miny}))"
                            bbox_prefilter = f"MbrIntersects({target_geom_expr}, GeomFromText('{bbox_wkt}', {target_srid})) = 1 AND "
                    else:
                        # Non-GeoPackage Spatialite
                        bbox_wkt = f"POLYGON(({minx} {miny}, {maxx} {miny}, {maxx} {maxy}, {minx} {maxy}, {minx} {miny}))"
                        bbox_prefilter = f"MbrIntersects({target_geom_expr}, GeomFromText('{bbox_wkt}', {target_srid})) = 1 AND "
                        self.log_info(f"  → BBox pre-filter: ({minx:.1f},{miny:.1f})-({maxx:.1f},{maxy:.1f})")
            except Exception as bbox_err:
                self.log_debug(f"Could not get source bbox for pre-filter: {bbox_err}")
            
            # Choose the best pre-filter (R-tree is preferred)
            final_prefilter = rtree_prefilter if rtree_prefilter else bbox_prefilter
            
            # v2.8.8: CRITICAL FIX - Include old_subset FID filter in SQL query
            # When re-filtering (e.g., adding buffer), old_subset may contain a FID filter
            # from the previous filtering. If we don't include it, we query ALL features
            # instead of just the previously filtered ones, returning wrong results.
            # 
            # v2.9.34: CRITICAL FIX - Don't combine FID-only filters in multi-step spatial filtering
            # FID filters from previous spatial steps are based on a DIFFERENT source geometry
            # and must be REPLACED, not combined. Only combine true user attribute filters.
            old_subset_sql_filter = ""
            if old_subset:
                old_subset_upper = old_subset.upper()
                # Check if old_subset is a simple FID filter (not spatial predicate)
                has_source_alias = '__source' in old_subset.lower()
                has_exists = 'EXISTS (' in old_subset_upper or 'EXISTS(' in old_subset_upper
                spatial_predicates = [
                    'ST_INTERSECTS', 'ST_CONTAINS', 'ST_WITHIN', 'ST_TOUCHES',
                    'ST_OVERLAPS', 'ST_CROSSES', 'ST_DISJOINT', 'ST_EQUALS',
                    'INTERSECTS', 'CONTAINS', 'WITHIN', 'GEOMFROMTEXT', 'GEOMFROMGPB'
                ]
                has_spatial_predicate = any(pred in old_subset_upper for pred in spatial_predicates)
                
                # v2.9.34: Check if old_subset is ONLY a FID filter (from previous spatial step)
                # v3.0.5: CRITICAL FIX - Dynamic FID regex to support any primary key name
                # The regex now uses pk_col variable instead of hardcoded 'fid'
                # Supports: fid, id, ogc_fid, gid, node_id, AGG_ID, etc.
                import re
                # Escape pk_col for regex safety (prevent injection)
                pk_col_escaped = re.escape(pk_col)
                # Build regex pattern dynamically: matches quoted or unquoted pk_col with IN/=/BETWEEN
                is_fid_only = bool(re.match(
                    rf'^\s*\(?\s*(["\']?){pk_col_escaped}\1\s+(IN\s*\(|=\s*-?\d+|BETWEEN\s+)',
                    old_subset,
                    re.IGNORECASE
                ))
                
                # v3.0.3: CRITICAL FIX - FID filters from step 1 MUST be combined in multi-step filtering!
                # Previously, is_fid_only caused replacement which lost the step 1 filter results.
                # This meant distant layers showed ALL features instead of intersection of step 1 AND step 2.
                if not has_source_alias and not has_exists and not has_spatial_predicate:
                    # old_subset is either:
                    # 1. A true user attribute filter (not FID) - ALWAYS combine
                    # 2. A FID filter from step 1 (is_fid_only=True) - MUST combine for multi-step!
                    old_subset_sql_filter = f"({old_subset}) AND "
                    # v2.9.44/v3.0.3: Enhanced logging
                    if is_fid_only:
                        self.log_info(f"✅ Combining FID filter from step 1 with new spatial filter (MULTI-STEP)")
                        self.log_info(f"  → FID filter: {old_subset[:80]}...")
                        self.log_info(f"  → This ensures intersection of step 1 AND step 2 results")
                    else:
                        self.log_info(f"✅ Combining old attribute filter with new spatial filter")
                        self.log_info(f"  → Old filter: {old_subset[:80]}...")
                else:
                    # old_subset contains spatial predicates - will be replaced, not combined
                    # v2.9.44: Enhanced logging for debugging
                    self.log_info(f"⚠️ Old subset has spatial predicates - will be replaced")
                    self.log_info(f"  → has_source_alias={has_source_alias}")
                    self.log_info(f"  → has_exists={has_exists}")
                    self.log_info(f"  → has_spatial_predicate={has_spatial_predicate}")
                    if old_subset:
                        self.log_info(f"  → Old subset: {old_subset[:80]}...")
            
            # Build EXISTS query with optional bbox pre-filter
            # The bbox filter uses target R-tree index for O(log n) initial filtering
            predicates_sql = ' OR '.join(predicate_conditions)
            select_query = f'''
                SELECT t."{pk_col}" 
                FROM "{target_table}" t
                WHERE {old_subset_sql_filter}{final_prefilter}EXISTS (
                    SELECT 1 FROM "{source_table}" s 
                    WHERE {predicates_sql}
                )
            '''
            
            self.log_info(f"  → Optimized EXISTS query with R-tree bbox pre-filter")
            self.log_debug(f"Query: {select_query[:300]}...")
            
            # v2.6.10: For very large datasets, estimate candidate count first
            # This provides progress feedback and helps set expectations
            VERY_LARGE_DATASET = 100000
            estimated_candidates = 0
            if feature_count >= VERY_LARGE_DATASET and rtree_prefilter:
                try:
                    # Quick estimate using R-tree pre-filter only
                    estimate_query = f'''
                        SELECT COUNT(*) FROM "{target_table}" t
                        WHERE {rtree_prefilter.rstrip(' AND ')}
                    '''
                    cursor.execute(estimate_query)
                    estimated_candidates = cursor.fetchone()[0]
                    self.log_info(f"  → Estimated R-tree candidates: {estimated_candidates:,} features (from {feature_count:,} total)")
                    if estimated_candidates > 10000:
                        from qgis.core import QgsMessageLog, Qgis
                        QgsMessageLog.logMessage(
                            f"{layer.name()}: Processing ~{estimated_candidates:,} candidate features - this may take a moment",
                            "FilterMate", Qgis.Info
                        )
                except Exception as est_err:
                    self.log_debug(f"Could not estimate candidates: {est_err}")
            
            # v2.6.2: Check cancellation before long query
            if self._is_task_canceled():
                self.log_info("Filter cancelled before SQL execution")
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"{layer.name()}: Filter cancelled before SQL execution",
                    "FilterMate", Qgis.Warning
                )
                conn.close()
                self._drop_source_table(source_path, source_table)
                return False
            
            # v2.6.2: Execute query using interruptible wrapper
            # This runs the query in a background thread and allows cancellation
            # v2.6.10: Extend timeout for very large datasets with many candidates
            effective_timeout = SPATIALITE_QUERY_TIMEOUT
            if estimated_candidates > 50000:
                effective_timeout = min(300, SPATIALITE_QUERY_TIMEOUT * 2)  # Up to 5 minutes for very large
                self.log_info(f"  → Extended timeout to {effective_timeout}s for large dataset")
            
            self.log_info(f"  → Executing interruptible query (timeout: {effective_timeout}s)...")
            
            # v2.6.11: Log query start to QGIS MessageLog for visibility
            from qgis.core import QgsMessageLog, Qgis
            QgsMessageLog.logMessage(
                f"{layer.name()}: Executing spatial query (timeout: {effective_timeout}s)...",
                "FilterMate", Qgis.Info
            )
            
            try:
                interruptible_query = InterruptibleSQLiteQuery(conn, select_query)
                results, error = interruptible_query.execute(
                    timeout=effective_timeout,
                    cancel_check=self._is_task_canceled
                )
                
                if error:
                    error_msg = str(error)
                    if "cancelled" in error_msg.lower():
                        self.log_info(f"Query cancelled by user")
                        from qgis.core import QgsMessageLog, Qgis
                        QgsMessageLog.logMessage(
                            f"{layer.name()}: Query cancelled by user during execution",
                            "FilterMate", Qgis.Warning
                        )
                        conn.close()
                        self._drop_source_table(source_path, source_table)
                        return False
                    elif "timeout" in error_msg.lower():
                        self.log_error(f"Query timeout after {effective_timeout}s - geometry too complex")
                        self.log_error(f"  → Consider using smaller source geometry or PostgreSQL backend")
                        from qgis.core import QgsMessageLog, Qgis
                        QgsMessageLog.logMessage(
                            f"Query timeout for {layer.name()} - geometry too complex",
                            "FilterMate", Qgis.Warning
                        )
                        conn.close()
                        self._drop_source_table(source_path, source_table)
                        return False
                    else:
                        self.log_error(f"Optimized query failed: {error}")
                        from qgis.core import QgsMessageLog, Qgis
                        QgsMessageLog.logMessage(
                            f"Optimized query failed for {layer.name()}: {str(error)[:100]}",
                            "FilterMate", Qgis.Warning
                        )
                        conn.close()
                        self._drop_source_table(source_path, source_table)
                        return False
                
                matching_fids = [row[0] for row in results]
                
                # v2.6.11: Diagnostic for 0 results on large datasets
                # Check source table geometry validity
                if len(matching_fids) == 0 and feature_count >= 10000:
                    try:
                        # Check source geometry validity
                        source_geom_col_check = 'geom_buffered' if has_buffer else 'geom'
                        cursor.execute(f'''
                            SELECT ST_IsValid({source_geom_col_check}) as valid,
                                   ST_IsEmpty({source_geom_col_check}) as empty,
                                   ST_GeometryType({source_geom_col_check}) as geom_type,
                                   ST_NPoints({source_geom_col_check}) as npoints
                            FROM "{source_table}"
                            LIMIT 1
                        ''')
                        src_check = cursor.fetchone()
                        if src_check:
                            is_valid, is_empty, geom_type, npoints = src_check
                            from qgis.core import QgsMessageLog, Qgis
                            QgsMessageLog.logMessage(
                                f"🔍 {layer.name()} DIAG: source_geom valid={is_valid}, empty={is_empty}, type={geom_type}, npoints={npoints}",
                                "FilterMate", Qgis.Warning
                            )
                            # v2.8.10: Empty geometry after negative buffer is NORMAL behavior
                            # Only invalid geometries (is_valid=0 but not empty) are problematic
                            if is_empty:
                                # Check if negative buffer was used
                                filtering_params = self.task_params.get('filtering', {}) if hasattr(self, 'task_params') and self.task_params else {}
                                # FIX v3.0.12: Clean buffer value from float precision errors
                                buf_val = clean_buffer_value(filtering_params.get('buffer_value', 0))
                                if buf_val < 0:
                                    QgsMessageLog.logMessage(
                                        f"ℹ️ {layer.name()}: Source geometry empty after negative buffer ({buf_val}m) - normal for thin features",
                                        "FilterMate", Qgis.Info
                                    )
                                else:
                                    QgsMessageLog.logMessage(
                                        f"⚠️ {layer.name()}: Source geometry is EMPTY - this explains 0 results!",
                                        "FilterMate", Qgis.Warning
                                    )
                            elif not is_valid:
                                QgsMessageLog.logMessage(
                                    f"⚠️ {layer.name()}: Source geometry is INVALID - this explains 0 results!",
                                    "FilterMate", Qgis.Warning
                                )
                    except Exception as diag_err:
                        from qgis.core import QgsMessageLog, Qgis
                        QgsMessageLog.logMessage(
                            f"🔍 {layer.name()} DIAG ERROR: {diag_err}",
                            "FilterMate", Qgis.Warning
                        )
                        
            except Exception as sql_error:
                self.log_error(f"Optimized query failed: {sql_error}")
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"Optimized query exception for {layer.name()}: {str(sql_error)[:100]}",
                    "FilterMate", Qgis.Warning
                )
                import traceback
                self.log_debug(traceback.format_exc())
                conn.close()
                # Clean up the source table since query failed
                self._drop_source_table(source_path, source_table)
                return False
            
            conn.close()
            
            # Clean up source table after query (we have the FIDs now)
            self._drop_source_table(source_path, source_table)
            
            self.log_info(f"  → Found {len(matching_fids)} matching features")
            
            # v2.6.11: Log query completion to QGIS MessageLog
            from qgis.core import QgsMessageLog, Qgis
            QgsMessageLog.logMessage(
                f"{layer.name()}: Spatial query completed → {len(matching_fids)} matching features",
                "FilterMate", Qgis.Info
            )
            
            # v2.8.8: Use cache_helpers for multi-step intersection (supports AND/OR/NOT AND)
            step_number = 1
            predicates_for_cache = []
            if isinstance(predicates, dict):
                predicates_for_cache = list(predicates.keys())
            elif isinstance(predicates, list):
                predicates_for_cache = predicates
            
            if CACHE_AVAILABLE and perform_cache_intersection and old_subset:
                cache_operator = get_combine_operator_from_task(self.task_params) if get_combine_operator_from_task else None
                cache_result = perform_cache_intersection(
                    layer=layer,
                    matching_fids=matching_fids,
                    source_wkt=source_wkt,
                    buffer_value=buffer_value,
                    predicates_list=predicates_for_cache,
                    old_subset=old_subset,
                    combine_operator=cache_operator,
                    logger=self,
                    backend_name="Spatialite Native"
                )
                if cache_result.was_intersected:
                    matching_fids = cache_result.fid_list
                    step_number = cache_result.step_number
            
            # v2.8.8: Store result using cache_helpers
            if CACHE_AVAILABLE and store_filter_result and matching_fids:
                store_filter_result(
                    layer=layer,
                    matching_fids=matching_fids,
                    source_wkt=source_wkt,
                    buffer_value=buffer_value,
                    predicates_list=predicates_for_cache,
                    step_number=step_number,
                    logger=self,
                    backend_name="Spatialite Native"
                )
            
            # v2.6.5: Build optimized FID-based filter expression
            if len(matching_fids) == 0:
                # v2.9.40: FALLBACK - When Spatialite returns 0 features, trigger OGR fallback
                # This handles cases where Spatialite SQL succeeded but returned incorrect results
                # (e.g., MakeValid errors that don't raise exceptions but return empty sets)
                
                # Check if this is due to negative buffer producing empty geometry
                is_negative_buffer_empty = False
                if hasattr(self, 'task_params') and self.task_params:
                    filtering_params = self.task_params.get('filtering', {})
                    # FIX v3.0.12: Clean buffer value from float precision errors
                    buf_val = clean_buffer_value(filtering_params.get('buffer_value', 0))
                    if buf_val < 0 and has_buffer:
                        # Check if source geometry is empty
                        try:
                            conn_check = sqlite3.connect(source_path)
                            cursor_check = conn_check.cursor()
                            source_geom_col_check = 'geom_buffered' if has_buffer else 'geom'
                            cursor_check.execute(f'SELECT ST_IsEmpty({source_geom_col_check}) FROM "{source_table}" LIMIT 1')
                            result = cursor_check.fetchone()
                            conn_check.close()
                            if result and result[0] == 1:
                                is_negative_buffer_empty = True
                        except (sqlite3.Error, sqlite3.OperationalError):
                            pass  # Query failed, assume geometry is valid
                
                # Check if this is a multi-step filter continuation (already has cache)
                is_multistep_continuation = False
                if SPATIALITE_CACHE_AVAILABLE and old_subset:
                    # Get predicates as list for comparison
                    if isinstance(predicates, dict):
                        predicates_for_cache = list(predicates.keys())
                    elif isinstance(predicates, list):
                        predicates_for_cache = predicates
                    else:
                        predicates_for_cache = []
                        
                    previous_fids = get_previous_filter_fids(layer, source_wkt, buffer_value, predicates_for_cache)
                    is_multistep_continuation = (previous_fids is not None and len(previous_fids) > 0)
                
                # v2.9.40: Trigger OGR fallback for ALL 0-feature results (not just large datasets)
                # UNLESS it's a valid case (negative buffer empty OR multi-step continuation)
                if not is_negative_buffer_empty and not is_multistep_continuation:
                    self.log_warning(f"⚠️ Spatialite returned 0 features for {layer.name()} ({feature_count:,} total features)")
                    self.log_warning(f"  → This may indicate geometry processing issue - signaling OGR fallback")
                    from qgis.core import QgsMessageLog, Qgis
                    QgsMessageLog.logMessage(
                        f"⚠️ {layer.name()}: Spatialite returned 0/{feature_count:,} features - falling back to OGR",
                        "FilterMate", Qgis.Warning
                    )
                    # Return False to signal that Spatialite failed and caller should try OGR
                    self._spatialite_zero_result_fallback = True
                    return False
                
                # Valid 0-result case (negative buffer empty OR multi-step continuation)
                # v2.6.9: FIX - Use FID-based impossible filter
                # For OGR/GeoPackage, use unquoted 'fid' which is the internal row ID
                # Quoted column names may not work correctly with some OGR configurations
                fid_expression = 'fid = -1'  # No valid FID is -1
                
                if is_negative_buffer_empty:
                    self.log_info(f"ℹ️ 0 features matched for {layer.name()} (negative buffer made geometry empty - valid)")
                elif is_multistep_continuation:
                    self.log_info(f"ℹ️ 0 features matched for {layer.name()} (multi-step intersection resulted in empty set - valid)")
                else:
                    # This shouldn't happen (we returned False above) but log just in case
                    self.log_warning(f"⚠️ 0 features matched for {layer.name()}")
                
                self.log_info(f"  → Applying empty filter expression: {fid_expression}")
                if buffer_value == 0 and not is_multistep_continuation:
                    self.log_warning(f"  → Hint: Source has no buffer. Use buffer for proximity filtering.")
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"⚠️ {layer.name()}: 0 features matched - applying empty filter (fid = -1)",
                    "FilterMate", Qgis.Warning
                )
            elif len(matching_fids) >= feature_count * 0.99 and feature_count > 10000:
                # v2.9.11: OPTIMIZATION - Skip filter when 99%+ features match
                # Applying a filter for 99%+ of features is wasteful - the filter expression
                # can be huge (millions of FIDs), slow to parse, and provides no real filtering.
                # Instead, clear any existing filter to show all features.
                unmatched_count = feature_count - len(matching_fids)
                match_ratio = len(matching_fids) / feature_count * 100
                self.log_info(f"⚡ OPTIMIZATION: {match_ratio:.2f}% of features matched ({len(matching_fids):,}/{feature_count:,})")
                self.log_info(f"   Only {unmatched_count:,} features excluded - skipping expensive FID filter")
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"⚡ {layer.name()}: {match_ratio:.1f}% match - filter skipped (source geometry covers most of layer)",
                    "FilterMate", Qgis.Info
                )
                # Clear filter to show all features (most efficient)
                fid_expression = ''
            elif len(matching_fids) >= self.LARGE_FID_TABLE_THRESHOLD:
                # v2.8.9: FIX - Use range-based filter instead of FID table subquery
                # The subquery "fid IN (SELECT fid FROM _fm_fids_xxx)" does NOT work
                # with setSubsetString() because the OGR provider doesn't support
                # SQL subqueries in filter expressions. Range-based is compatible.
                
                sorted_fids = sorted(matching_fids)
                min_fid, max_fid = sorted_fids[0], sorted_fids[-1]
                self.log_info(f"  📊 FID analysis: {len(matching_fids):,} FIDs in range {min_fid}-{max_fid}")
                
                # Use range-based filter for OGR compatibility (no subqueries)
                fid_expression = self._build_range_based_filter(pk_col, matching_fids)
            else:
                # v2.8.10: FIX - Use unquoted fid for OGR/GeoPackage compatibility
                col_ref = 'fid' if pk_col == 'fid' else f'"{pk_col}"'
                fid_expression = f'{col_ref} IN ({", ".join(str(fid) for fid in matching_fids)})'
            
            # Combine with old_subset if needed (same logic as _apply_filter_direct_sql)
            # v2.8.10: FIX - If old_subset was already included in SQL query via old_subset_sql_filter,
            # DON'T re-combine - the matching_fids already reflect the intersection
            if old_subset and not old_subset_sql_filter:
                # old_subset was NOT included in SQL (had spatial predicates) - just use new FIDs
                final_expression = fid_expression
                self.log_info(f"  → Replacing old spatial filter with new FID filter")
            elif old_subset and old_subset_sql_filter:
                # old_subset WAS included in SQL - matching_fids already combined, use as-is
                final_expression = fid_expression
                self.log_info(f"  → FID filter already combined in SQL query, using result directly")
            else:
                final_expression = fid_expression
            
            # Apply filter via queue callback or direct
            queue_callback = self.task_params.get('_subset_queue_callback') if self.task_params else None
            
            if queue_callback:
                queue_callback(layer, final_expression)
                result = True
            else:
                result = safe_set_subset_string(layer, final_expression)
            
            elapsed = time.time() - start_time
            
            if result:
                self.log_info(f"✓ {layer.name()}: {len(matching_fids)} features via source table ({elapsed:.2f}s)")
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"✓ Spatialite source table filter: {layer.name()} → {len(matching_fids)} features ({elapsed:.2f}s)",
                    "FilterMate", Qgis.Info
                )
            else:
                self.log_error(f"✗ Source table filter failed for {layer.name()}")
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"✗ Source table filter failed for {layer.name()} (setSubsetString returned False)",
                    "FilterMate", Qgis.Warning
                )
            
            return result
            
        except Exception as e:
            self.log_error(f"Exception in source table filter: {e}")
            from qgis.core import QgsMessageLog, Qgis
            QgsMessageLog.logMessage(
                f"Exception in source table filter for {layer.name() if layer else 'unknown'}: {str(e)[:100]}",
                "FilterMate", Qgis.Critical
            )
            import traceback
            self.log_debug(traceback.format_exc())
            return False
    
    def _drop_source_table(self, db_path: str, table_name: str):
        """
        v2.6.1: Drop a permanent source table and its spatial indexes.
        
        Args:
            db_path: Path to database file
            table_name: Name of table to drop
        """
        conn = None
        try:
            mod_available, ext_name = _test_mod_spatialite_available()
            if not mod_available:
                return
            
            conn = sqlite3.connect(db_path)
            conn.enable_load_extension(True)
            conn.load_extension(ext_name)
            cursor = conn.cursor()
            
            # Disable spatial indexes first
            try:
                cursor.execute(f'SELECT DisableSpatialIndex("{table_name}", "geom")')
            except Exception:
                pass
            try:
                cursor.execute(f'SELECT DisableSpatialIndex("{table_name}", "geom_buffered")')
            except Exception:
                pass
            
            # Drop the table
            cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            conn.commit()
            conn.close()
            
            self.log_debug(f"🧹 Dropped source table: {table_name}")
            
        except Exception as e:
            self.log_debug(f"Error dropping source table: {e}")
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

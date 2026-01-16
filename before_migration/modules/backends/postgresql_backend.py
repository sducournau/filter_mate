# -*- coding: utf-8 -*-
"""
PostgreSQL Backend for FilterMate

Optimized backend for PostgreSQL/PostGIS databases.
Uses native PostGIS spatial functions and SQL queries for maximum performance.

Performance Strategy:
- Small datasets (< 10k features): Direct setSubsetString for simplicity
- Large datasets (≥ 10k features): Materialized views with GIST spatial indexes
- Custom buffers: Always use materialized views for geometry operations

v2.4.0 Performance Improvements:
- Connection pooling to avoid ~50-100ms connection overhead per query
- Batch metadata loading for multiple layers
- Server-side cursors for streaming large result sets

v2.5.9 Performance Improvements:
- Two-phase filtering for complex expressions (3-10x faster)
- Progressive/lazy loading for very large datasets (50-80% memory reduction)
- Query complexity estimation for adaptive strategy selection
- Enhanced expression caching with result count caching
"""

from typing import Dict, Optional, Tuple
from qgis.core import QgsVectorLayer, QgsDataSourceUri
from .base_backend import GeometricFilterBackend
from ..logging_config import get_tasks_logger
from ..psycopg2_availability import psycopg2, PSYCOPG2_AVAILABLE, POSTGRESQL_AVAILABLE
from ..constants import DEFAULT_TEMP_SCHEMA
from ..appUtils import (
    safe_set_subset_string, 
    get_datasource_connexion_from_layer, 
    apply_postgresql_type_casting
)
import time
import uuid

logger = get_tasks_logger()

# Import MV Registry for cleanup management (v2.4.0)
try:
    from .mv_registry import get_mv_registry, MVRegistry
    MV_REGISTRY_AVAILABLE = True
except ImportError:
    MV_REGISTRY_AVAILABLE = False
    get_mv_registry = None
    MVRegistry = None

# Import connection pooling for optimized PostgreSQL operations
try:
    from ..connection_pool import (
        get_pool_manager,
        pooled_connection_from_layer,
        POSTGRESQL_AVAILABLE as POOL_AVAILABLE
    )
    CONNECTION_POOL_AVAILABLE = POOL_AVAILABLE
except ImportError:
    CONNECTION_POOL_AVAILABLE = False
    get_pool_manager = None
    pooled_connection_from_layer = None

# Import progressive filtering for large datasets (v2.5.9)
try:
    from ..tasks.progressive_filter import (
        ProgressiveFilterExecutor,
        TwoPhaseFilter,
        LazyResultIterator,
        FilterStrategy,
        LayerProperties
    )
    PROGRESSIVE_FILTER_AVAILABLE = True
except ImportError:
    PROGRESSIVE_FILTER_AVAILABLE = False
    ProgressiveFilterExecutor = None
    TwoPhaseFilter = None
    LazyResultIterator = None
    FilterStrategy = None

# Import query complexity estimator (v2.5.9)
try:
    from ..tasks.query_complexity_estimator import (
        QueryComplexityEstimator,
        get_complexity_estimator,
        estimate_query_complexity
    )
    COMPLEXITY_ESTIMATOR_AVAILABLE = True
except ImportError:
    COMPLEXITY_ESTIMATOR_AVAILABLE = False
    QueryComplexityEstimator = None
    get_complexity_estimator = None

# Import multi-step filter optimizer (v2.5.10)
try:
    from ..tasks.multi_step_filter import (
        MultiStepFilterOptimizer,
        FilterPlanBuilder,
        SelectivityEstimator,
        LayerStatistics,
        FilterStrategy as MultiStepStrategy,
        get_optimal_filter_plan
    )
    MULTI_STEP_FILTER_AVAILABLE = True
except ImportError:
    MULTI_STEP_FILTER_AVAILABLE = False
    MultiStepFilterOptimizer = None
    FilterPlanBuilder = None
    SelectivityEstimator = None
    LayerStatistics = None
    get_optimal_filter_plan = None

# Import buffer optimizer for large buffer workflows (v2.9.0)
try:
    from .postgresql_buffer_optimizer import (
        PostgreSQLBufferOptimizer,
        BufferOptimizationConfig,
        BufferOptimizationResult,
        get_buffer_optimizer,
        BUFFER_OPTIMIZER_AVAILABLE
    )
except ImportError:
    BUFFER_OPTIMIZER_AVAILABLE = False
    PostgreSQLBufferOptimizer = None
    BufferOptimizationConfig = None
    BufferOptimizationResult = None
    get_buffer_optimizer = None


class PostgreSQLGeometricFilter(GeometricFilterBackend):
    """
    PostgreSQL/PostGIS backend for geometric filtering.
    
    This backend provides optimized filtering for PostgreSQL layers using:
    - Native PostGIS spatial functions (ST_Intersects, ST_Contains, etc.)
    - Efficient spatial indexes
    - SQL-based filtering for maximum performance
    
    Strategy by source feature count:
    - Tiny (< 50): Direct WKT geometry literal (simplest, no subquery)
    - Small (< 10k): EXISTS subquery with source filter
    - Large (≥ 10k): Materialized views with spatial indexes
    
    v2.5.9 Progressive Filter Strategies:
    - Complex expressions (score > 100): Two-phase bbox pre-filter
    - Very large results (> 100k): Lazy cursor streaming
    - Adaptive strategy selection based on query complexity
    """
    
    # Performance thresholds
    SIMPLE_WKT_THRESHOLD = 50            # Use direct WKT for very small source datasets
    MATERIALIZED_VIEW_THRESHOLD = 10000  # Features count threshold for MV strategy
    LARGE_DATASET_THRESHOLD = 100000     # Features count for additional logging
    
    # WKT size limits (v2.5.11, v2.7.3) - prevent very long SQL expressions
    # PostgreSQL can handle very long expressions but performance degrades
    # and some layer display issues can occur with very complex geometries
    # v2.7.3: Increased from 50000 to 100000 to handle detailed French communes
    # (e.g., Toulouse commune boundary is ~60000 chars)
    MAX_WKT_LENGTH = 100000              # Max WKT chars before forcing EXISTS subquery
    WKT_SIMPLIFY_THRESHOLD = 200000      # WKT chars threshold for geometry simplification warning
    
    # Progressive filter thresholds (v2.5.9)
    TWO_PHASE_COMPLEXITY_THRESHOLD = 100  # Min complexity score for two-phase
    LAZY_CURSOR_THRESHOLD = 50000         # Min features for lazy cursor streaming
    
    # Predicate ordering for performance optimization
    # Most selective/fastest predicates first = better query plans
    # disjoint is fastest (eliminates most), equals is slowest (most expensive comparison)
    PREDICATE_ORDER = {
        'disjoint': 1,     # ST_Disjoint - fastest, eliminates most features
        'intersects': 2,   # ST_Intersects - fast with spatial index
        'touches': 3,      # ST_Touches - fast boundary check
        'crosses': 4,      # ST_Crosses - moderate
        'within': 5,       # ST_Within - moderate, uses index
        'contains': 6,     # ST_Contains - expensive
        'overlaps': 7,     # ST_Overlaps - expensive
        'equals': 8,       # ST_Equals - most expensive comparison
    }
    
    # MV optimization flags
    ENABLE_MV_CLUSTER = True       # CLUSTER operation (improves seq scans but slow to create)
    ENABLE_MV_ANALYZE = True       # ANALYZE for query optimizer statistics
    # Note: PostgreSQL does NOT support UNLOGGED for materialized views (only regular tables)
    # Setting to False to prevent "materialized views cannot be unlogged" error
    ENABLE_MV_UNLOGGED = False     # UNLOGGED not supported for MVs in PostgreSQL
    MV_INDEX_FILLFACTOR = 90       # Index fill factor (90 = good for read-heavy, 70 = for updates)
    
    # v2.9.1: Advanced MV optimization flags
    ENABLE_INDEX_INCLUDE = True    # Use INCLUDE clause in GIST index (PostgreSQL 11+, avoids table lookup)
    ENABLE_EXTENDED_STATS = True   # Create extended statistics for better query plans
    ENABLE_ASYNC_CLUSTER = True    # Run CLUSTER asynchronously for large datasets
    ASYNC_CLUSTER_THRESHOLD = 50000  # Features threshold for async CLUSTER
    ENABLE_BBOX_COLUMN = True      # Add bbox column to MV for fast pre-filtering
    
    # v2.9.2: Centroid optimization mode
    # 'centroid' = ST_Centroid() - fast but may be outside concave polygons
    # 'point_on_surface' = ST_PointOnSurface() - guaranteed inside polygon (recommended)
    # 'auto' = Use PointOnSurface for polygons, Centroid for lines
    CENTROID_MODE = 'point_on_surface'
    
    # v2.9.2: Simplification before buffer (server-side)
    ENABLE_SIMPLIFY_BEFORE_BUFFER = True   # Apply ST_SimplifyPreserveTopology before buffer
    SIMPLIFY_TOLERANCE_FACTOR = 0.1        # tolerance = buffer_distance * factor
    SIMPLIFY_MIN_TOLERANCE = 0.5           # Minimum tolerance (meters)
    SIMPLIFY_MAX_TOLERANCE = 10.0          # Maximum tolerance (meters)
    SIMPLIFY_VERTEX_THRESHOLD = 100        # Only simplify if avg vertices > this
    SIMPLIFY_FEATURE_THRESHOLD = 500       # Only simplify if features > this
    
    # v2.9.1: PostgreSQL version detection cache
    _pg_version_cache = {}         # Cache: conn_hash -> (version, timestamp)
    
    def __init__(self, task_params: Dict):
        """
        Initialize PostgreSQL backend.
        
        Args:
            task_params: Task parameters dictionary
        """
        super().__init__(task_params)
        self.logger = logger
        self.mv_schema = DEFAULT_TEMP_SCHEMA  # v2.8.8: Use filtermate_temp schema for MVs
        self.mv_prefix = "filtermate_mv_"  # Prefix for MV names

    def _get_postgresql_version(self, conn) -> int:
        """
        Get PostgreSQL major version number with caching.
        
        v2.9.1: Used to enable version-specific optimizations:
        - PostgreSQL 10+: Extended statistics
        - PostgreSQL 11+: INCLUDE clause in indexes
        - PostgreSQL 12+: Better GIST index performance
        
        Args:
            conn: psycopg2 database connection
            
        Returns:
            int: Major version number (e.g., 11, 12, 13, 14, 15, 16)
        """
        import time
        
        if conn is None:
            return 9  # Conservative fallback
        
        try:
            # Check cache (valid for 1 hour)
            conn_hash = id(conn)
            cache_entry = self._pg_version_cache.get(conn_hash)
            if cache_entry:
                version, timestamp = cache_entry
                if time.time() - timestamp < 3600:  # 1 hour cache
                    return version
            
            # Query PostgreSQL version
            with conn.cursor() as cursor:
                cursor.execute("SHOW server_version_num;")
                version_num = int(cursor.fetchone()[0])
                # server_version_num format: XXYYZZ (e.g., 140005 = 14.0.5)
                major_version = version_num // 10000
                
                # Cache result
                self._pg_version_cache[conn_hash] = (major_version, time.time())
                
                self.log_debug(f"📊 PostgreSQL version: {major_version} (raw: {version_num})")
                return major_version
                
        except Exception as e:
            self.log_debug(f"Could not detect PostgreSQL version: {e}")
            return 9  # Conservative fallback
    
    def _schedule_async_cluster(self, conn, full_mv_name: str, index_name: str, 
                                 schema: str, mv_name: str):
        """
        Schedule CLUSTER operation to run asynchronously.
        
        v2.9.1: For medium-sized datasets (50k-100k features), CLUSTER can take
        10-30 seconds. Running it asynchronously improves user experience while
        still providing the performance benefits eventually.
        
        The CLUSTER operation reorders table data to match the spatial index,
        dramatically improving sequential scan performance (2-5x faster).
        
        Args:
            conn: psycopg2 database connection (not used - we create new connection)
            full_mv_name: Full qualified MV name (e.g., '"schema"."mv_name"')
            index_name: Name of the GIST index to cluster by
            schema: Schema name
            mv_name: MV name (unqualified)
        """
        import threading
        
        def run_cluster():
            """Background thread for CLUSTER operation."""
            try:
                # Get fresh connection for background thread
                from qgis.core import QgsProject
                
                # Find any PostgreSQL layer to get connection params
                for layer_id, layer in QgsProject.instance().mapLayers().items():
                    if hasattr(layer, 'providerType') and layer.providerType() == 'postgres':
                        bg_conn, _ = get_datasource_connexion_from_layer(layer)
                        if bg_conn:
                            try:
                                with bg_conn.cursor() as cursor:
                                    # Set statement timeout to prevent runaway queries
                                    cursor.execute("SET statement_timeout = '120s';")
                                    cursor.execute(f'CLUSTER {full_mv_name} USING "{index_name}";')
                                    bg_conn.commit()
                                    
                                    # Also run ANALYZE after CLUSTER
                                    cursor.execute(f'ANALYZE {full_mv_name};')
                                    bg_conn.commit()
                                    
                                logger.info(f"✓ Async CLUSTER completed for {mv_name}")
                            except Exception as cluster_err:
                                logger.warning(f"Async CLUSTER failed: {cluster_err}")
                                try:
                                    bg_conn.rollback()
                                except Exception:
                                    pass  # Connection may be in bad state
                            finally:
                                bg_conn.close()
                        break
            except Exception as e:
                logger.warning(f"Async CLUSTER error: {e}")
        
        # Start background thread
        cluster_thread = threading.Thread(
            target=run_cluster,
            daemon=True,
            name=f"FilterMate-CLUSTER-{mv_name[:8]}"
        )
        cluster_thread.start()
        self.log_debug(f"  🔄 CLUSTER scheduled in background thread")

    def _ensure_mv_schema_exists(self, conn, schema_name: str) -> str:
        """
        Ensure the MV schema exists, with fallback to 'public' if creation fails.
        
        v2.8.8: All FilterMate materialized views are created in a dedicated temp schema.
        If the schema cannot be created (permission issues), falls back to 'public'.
        
        Args:
            conn: psycopg2 connection
            schema_name: Desired schema name (e.g., 'filtermate_temp')
            
        Returns:
            str: Name of the schema to use (schema_name if created/exists, 'public' as fallback)
        """
        if conn is None:
            self.log_warning("Cannot ensure MV schema: connection is None, using 'public'")
            return 'public'
        
        # Check if schema already exists
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT schema_name FROM information_schema.schemata 
                    WHERE schema_name = %s
                """, (schema_name,))
                if cursor.fetchone():
                    return schema_name
        except Exception as e:
            self.log_debug(f"Could not check if schema '{schema_name}' exists: {e}")
        
        # Try to create the schema
        try:
            with conn.cursor() as cursor:
                cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}";')
                conn.commit()
            self.log_debug(f"Created schema '{schema_name}'")
            return schema_name
        except Exception as e:
            self.log_warning(f"Cannot create schema '{schema_name}': {e}")
            try:
                conn.rollback()
            except Exception:
                pass  # Connection may be in bad state
            
            # Fallback to public schema
            self.log_info(f"Using 'public' schema as fallback for MVs")
            return 'public'

    def _has_expensive_spatial_expression(self, sql_string: str) -> bool:
        """
        Detect if a SQL expression contains expensive spatial predicates that require materialization.
        
        v2.8.7: Added to prevent slow canvas rendering caused by re-executing expensive
        spatial queries on each canvas interaction (pan, zoom, render tiles).
        
        When a layer's subsetString contains complex spatial expressions like:
            ("fid" IN (SELECT "pk" FROM "public"."filtermate_mv_xxx")) 
            AND 
            (EXISTS (SELECT 1 FROM "table" WHERE ST_Intersects(..., ST_Buffer(...))))
        
        PostgreSQL must re-execute the expensive EXISTS + ST_Buffer + ST_Intersects
        query for EVERY feature request from QGIS. This causes:
        - Slow rendering when panning/zooming
        - Features appearing slowly on the canvas
        - Poor user experience
        
        Solution: Force materialization even for small datasets when expression is complex.
        The expensive query is executed ONCE during MV creation.
        
        Expensive patterns detected:
        - EXISTS with ST_Intersects/ST_Contains/ST_Within
        - EXISTS with ST_Buffer
        - Combination of MV reference AND EXISTS clause (multi-step filter)
        - __source alias with spatial predicate
        
        Args:
            sql_string: SQL expression to analyze
            
        Returns:
            True if expression contains expensive patterns requiring materialization
        """
        if not sql_string:
            return False
        
        sql_upper = sql_string.upper()
        
        # Pattern 1: EXISTS clause with spatial predicate - always expensive
        # These are evaluated for every row and cannot use indexes efficiently in subqueries
        has_exists = 'EXISTS' in sql_upper or 'EXISTS(' in sql_upper
        has_spatial_predicate = any(pred in sql_upper for pred in [
            'ST_INTERSECTS', 'ST_CONTAINS', 'ST_WITHIN', 'ST_TOUCHES',
            'ST_OVERLAPS', 'ST_CROSSES', 'ST_COVERS', 'ST_COVEREDBY'
        ])
        
        # Pattern 2: ST_Buffer in subquery - very expensive as buffer is computed for each row
        has_buffer = 'ST_BUFFER' in sql_upper
        
        # Pattern 3: Combination patterns that are particularly expensive
        # EXISTS + spatial predicate = expensive (re-evaluated per row)
        if has_exists and has_spatial_predicate:
            self.log_debug(f"Detected expensive pattern: EXISTS + spatial predicate")
            return True
        
        # EXISTS + ST_Buffer = very expensive (buffer computed per row)
        if has_exists and has_buffer:
            self.log_debug(f"Detected expensive pattern: EXISTS + ST_Buffer")
            return True
        
        # Pattern 4: MV reference AND EXISTS - this is the multi-step filter case
        # Example: ("fid" IN (SELECT "pk" FROM "mv_xxx")) AND (EXISTS (...ST_Intersects...))
        has_mv_reference = 'FILTERMATE_MV_' in sql_upper or 'MV_' in sql_upper
        if has_mv_reference and has_exists:
            self.log_debug(f"Detected expensive pattern: MV reference + EXISTS clause")
            return True
        
        # Pattern 5: __source alias with spatial predicate - indicates EXISTS subquery pattern
        has_source_alias = '__SOURCE' in sql_upper
        if has_source_alias and has_spatial_predicate:
            self.log_debug(f"Detected expensive pattern: __source alias + spatial predicate")
            return True
        
        return False

    # Note: _get_buffer_endcap_style(), _get_buffer_segments(), _get_simplify_tolerance()
    # are inherited from GeometricFilterBackend (v2.8.6 refactoring)
    
    def _build_st_buffer_with_style(self, geom_expr: str, buffer_value: float) -> str:
        """
        Build ST_Buffer expression with endcap style from task_params.
        
        Supports both positive buffers (expansion) and negative buffers (erosion/shrinking).
        Negative buffers only work on polygon geometries - they shrink the polygon inward.
        
        v2.6.x: Optionally applies ST_SimplifyPreserveTopology before buffer to reduce
        vertex count and improve performance for complex geometries.
        
        Args:
            geom_expr: Geometry expression to buffer
            buffer_value: Buffer distance (positive=expand, negative=shrink/erode)
            
        Returns:
            PostGIS ST_Buffer expression with style parameter
            
        Note:
            - Negative buffer on a polygon shrinks it inward
            - Negative buffer on a point or line returns empty geometry
            - Very large negative buffers may collapse the polygon entirely
            - Negative buffers are wrapped in ST_MakeValid() to prevent invalid geometries
            - Returns NULL if buffer produces empty geometry (v2.4.23 fix for negative buffers)
            - Simplification uses ST_SimplifyPreserveTopology to maintain topology
        """
        endcap_style = self._get_buffer_endcap_style()
        quad_segs = self._get_buffer_segments()
        simplify_tolerance = self._get_simplify_tolerance()
        
        # Log negative buffer usage for visibility
        if buffer_value < 0:
            self.log_debug(f"📐 Using negative buffer (erosion): {buffer_value}m")
        
        # v2.6.x: Apply geometry simplification before buffer if tolerance is set
        # ST_SimplifyPreserveTopology maintains valid topology (no self-intersections)
        working_geom = geom_expr
        if simplify_tolerance > 0:
            working_geom = f"ST_SimplifyPreserveTopology({geom_expr}, {simplify_tolerance})"
            self.log_info(f"  📐 Applying ST_SimplifyPreserveTopology({simplify_tolerance}m) before buffer")
        
        # Build base buffer expression with quad_segs and endcap style
        # PostGIS ST_Buffer syntax: ST_Buffer(geom, distance, 'quad_segs=N endcap=style')
        style_params = f"quad_segs={quad_segs}"
        if endcap_style != 'round':
            style_params += f" endcap={endcap_style}"
        
        buffer_expr = f"ST_Buffer({working_geom}, {buffer_value}, '{style_params}')"
        self.log_debug(f"Buffer expression: {buffer_expr}")
        
        # CRITICAL FIX v2.3.9: Wrap negative buffers in ST_MakeValid()
        # CRITICAL FIX v2.4.23: Use ST_IsEmpty() to detect ALL empty geometry types
        # CRITICAL FIX v2.5.4: Fixed bug where NULLIF only detected GEOMETRYCOLLECTION EMPTY
        #                      but not POLYGON EMPTY, MULTIPOLYGON EMPTY, etc.
        # Negative buffers (erosion/shrinking) can produce invalid or empty geometries,
        # especially on complex polygons or when buffer is too large.
        # ST_MakeValid() ensures the result is always geometrically valid.
        # ST_IsEmpty() detects ALL empty geometry types (POLYGON EMPTY, MULTIPOLYGON EMPTY, etc.)
        if buffer_value < 0:
            self.log_info(f"  🛡️ Wrapping negative buffer in ST_MakeValid() + ST_IsEmpty check for empty geometry handling")
            # Use CASE WHEN to return NULL if buffer produces empty geometry
            # This ensures empty results from negative buffers don't match spatial predicates
            validated_expr = f"ST_MakeValid({buffer_expr})"
            return f"CASE WHEN ST_IsEmpty({validated_expr}) THEN NULL ELSE {validated_expr} END"
        else:
            return buffer_expr
    
    def supports_layer(self, layer: QgsVectorLayer) -> bool:
        """
        Check if this backend supports the given layer.
        
        v2.5.x: PostgreSQL layers are now ALWAYS supported via QGIS native API.
        psycopg2 is only required for advanced features (materialized views).
        
        When psycopg2 is not available:
        - Simple filtering via setSubsetString still works
        - Advanced features (MVs, spatial indexes) are disabled
        
        Args:
            layer: QGIS vector layer to check
        
        Returns:
            True if layer is from PostgreSQL provider (QGIS handles connection)
        """
        if layer.providerType() != 'postgres':
            return False
        
        # v2.5.x: QGIS native PostgreSQL support - no psycopg2 required for basic operations
        # The layer is already loaded in QGIS, so connection works
        if not layer.isValid():
            self.log_warning(f"PostgreSQL layer '{layer.name()}' is not valid")
            return False
        
        # If psycopg2 is available, optionally test connection for advanced features
        if PSYCOPG2_AVAILABLE:
            try:
                if CONNECTION_POOL_AVAILABLE and pooled_connection_from_layer:
                    # Use pooled connection (more efficient for repeated checks)
                    with pooled_connection_from_layer(layer) as (conn, source_uri):
                        if conn is None:
                            self.log_info(
                                f"PostgreSQL psycopg2 connection failed for layer {layer.name()}, "
                                f"advanced features disabled but basic filtering available via QGIS API"
                            )
                            # Still return True - basic filtering via setSubsetString works
                        else:
                            # Test connection with simple query
                            with conn.cursor() as cursor:
                                cursor.execute("SELECT 1")
                            self.log_debug(f"PostgreSQL psycopg2 connection OK for layer {layer.name()}")
                else:
                    # Fallback to non-pooled connection
                    conn, source_uri = get_datasource_connexion_from_layer(layer)
                    if conn is None:
                        self.log_info(
                            f"PostgreSQL psycopg2 connection failed for layer {layer.name()}, "
                            f"advanced features disabled but basic filtering available via QGIS API"
                        )
                    else:
                        with conn.cursor() as cursor:
                            cursor.execute("SELECT 1")
                        conn.close()
                        self.log_debug(f"PostgreSQL psycopg2 connection OK for layer {layer.name()}")
            except Exception as e:
                self.log_info(
                    f"PostgreSQL psycopg2 connection test failed for layer {layer.name()}: {e}, "
                    f"advanced features disabled but basic filtering available via QGIS API"
                )
        else:
            self.log_info(
                f"psycopg2 not available - PostgreSQL layer '{layer.name()}' will use "
                f"QGIS native API (setSubsetString). Materialized views disabled."
            )
        
        # Always return True for valid PostgreSQL layers - basic filtering always works
        return True

    def _parse_source_table_reference(self, source_geom: str) -> Optional[Dict]:
        """
        Parse source geometry expression to detect table references.
        
        PostgreSQL source_geom can have several formats:
        1. "schema"."table"."geom" - direct table reference
        2. "mv_xxx_dump"."geom" - materialized view reference
        3. ST_Buffer("schema"."table"."geom", value) - with buffer
        4. "table"."geom" - table reference without schema (uses default "public")
        5. ST_Buffer("table"."geom", value) - buffer without schema
        6. CASE WHEN ST_IsEmpty(...ST_Buffer("schema"."table"."geom"...) - negative buffer wrapper
        
        For formats 1, 3, 4, 5, 6 we need to use EXISTS subquery in setSubsetString.
        For format 2 (materialized view), it's OK to use direct reference.
        
        Args:
            source_geom: Source geometry SQL expression
        
        Returns:
            Dict with schema, table, geom_field, and optional buffer_expr, or None if not a table reference
        """
        import re
        
        # Get buffer endcap style for use in buffer expressions
        endcap_style = self._get_buffer_endcap_style()
        
        def build_buffer_expr(geom_ref: str, buffer_value: str) -> str:
            """
            Build ST_Buffer expression with appropriate endcap style.
            
            CRITICAL FIX v2.5.6: Handle negative buffers (erosion) properly.
            Negative buffers can produce empty geometries which must be handled
            with ST_MakeValid() and ST_IsEmpty() to prevent matching issues.
            """
            # Build base buffer expression
            if endcap_style == 'round':
                buffer_expr = f'ST_Buffer({geom_ref}, {buffer_value})'
            else:
                buffer_expr = f"ST_Buffer({geom_ref}, {buffer_value}, 'endcap={endcap_style}')"
            
            # CRITICAL FIX v2.5.6: Wrap negative buffers in ST_MakeValid() + ST_IsEmpty check
            # Try to parse buffer_value as float to detect negative values
            try:
                buffer_float = float(buffer_value.strip())
                if buffer_float < 0:
                    # Negative buffer (erosion): wrap in ST_MakeValid and return NULL if empty
                    validated_expr = f"ST_MakeValid({buffer_expr})"
                    return f"CASE WHEN ST_IsEmpty({validated_expr}) THEN NULL ELSE {validated_expr} END"
            except (ValueError, TypeError):
                # buffer_value is an expression, not a numeric literal - can't determine sign
                pass
            
            return buffer_expr
        
        # v2.7.11 DIAGNOSTIC: Log source_geom being parsed
        self.log_info(f"🔍 _parse_source_table_reference: source_geom length={len(source_geom)}")
        self.log_info(f"   Preview: '{source_geom[:120]}...'")
        
        # CRITICAL FIX v2.7.5: Handle CASE WHEN wrapper for negative buffers
        # When postgresql_source_geom contains a negative buffer, it's wrapped as:
        # CASE WHEN ST_IsEmpty(ST_MakeValid(ST_Buffer("schema"."table"."geom", -100))) THEN NULL ELSE ... END
        # This must be parsed to extract the table reference, then rebuilt with __source alias
        # Pattern: CASE WHEN ... ST_Buffer("schema"."table"."geom", value) ...
        if source_geom.upper().startswith('CASE WHEN'):
            self.log_info(f"🔍 CASE WHEN detected - trying inner patterns")
            
            # Try to find 3-part table reference inside ST_Buffer
            inner_3part_pattern = r'ST_Buffer\s*\(\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*,\s*([^,)]+)'
            inner_match = re.search(inner_3part_pattern, source_geom, re.IGNORECASE)
            self.log_info(f"🔍 3-part pattern match: {inner_match is not None}")
            if inner_match:
                schema, table, geom_field, buffer_value = inner_match.groups()
                self.log_info(f"🔍 Extracted: schema='{schema}', table='{table}', geom='{geom_field}', buffer='{buffer_value}'")
                # Skip materialized views
                if table.startswith('mv_') and table.endswith('_dump'):
                    self.log_debug(f"Source is materialized view '{table}' with CASE wrapper - using direct reference")
                    return None
                self.log_info(f"  ✓ Extracted from CASE WHEN: schema='{schema}', table='{table}', geom='{geom_field}', buffer={buffer_value}")
                return {
                    'schema': schema,
                    'table': table,
                    'geom_field': geom_field,
                    'buffer_expr': build_buffer_expr(f'__source."{geom_field}"', buffer_value)
                }
            
            # Try to find 2-part table reference inside ST_Buffer (no schema)
            inner_2part_pattern = r'ST_Buffer\s*\(\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*,\s*([^,)]+)'
            inner_match = re.search(inner_2part_pattern, source_geom, re.IGNORECASE)
            if inner_match:
                table, geom_field, buffer_value = inner_match.groups()
                # Skip materialized views
                if table.startswith('mv_') and table.endswith('_dump'):
                    self.log_debug(f"Source is materialized view '{table}' with CASE wrapper - using direct reference")
                    return None
                self.log_info(f"  ✓ Extracted from CASE WHEN (2-part): table='{table}', geom='{geom_field}', buffer={buffer_value}")
                return {
                    'schema': 'public',
                    'table': table,
                    'geom_field': geom_field,
                    'buffer_expr': build_buffer_expr(f'__source."{geom_field}"', buffer_value)
                }
        
        # Pattern 1: ST_Buffer("schema"."table"."geom", value) - 3-part with buffer
        buffer_pattern_3part = r'ST_Buffer\s*\(\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*,\s*([^)]+)\)'
        match = re.match(buffer_pattern_3part, source_geom, re.IGNORECASE)
        if match:
            schema, table, geom_field, buffer_value = match.groups()
            return {
                'schema': schema,
                'table': table,
                'geom_field': geom_field,
                'buffer_expr': build_buffer_expr(f'__source."{geom_field}"', buffer_value)
            }
        
        # Pattern 2: ST_Buffer("table"."geom", value) - 2-part with buffer (no schema)
        buffer_pattern_2part = r'ST_Buffer\s*\(\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*,\s*([^)]+)\)'
        match = re.match(buffer_pattern_2part, source_geom, re.IGNORECASE)
        if match:
            table, geom_field, buffer_value = match.groups()
            # Skip materialized views - they're safe to reference directly
            if table.startswith('mv_') and table.endswith('_dump'):
                self.log_debug(f"Source is materialized view '{table}' with buffer - using direct reference")
                return None
            self.log_debug(f"Detected 2-part buffer reference: table='{table}', geom='{geom_field}', using schema='public'")
            return {
                'schema': 'public',
                'table': table,
                'geom_field': geom_field,
                'buffer_expr': build_buffer_expr(f'__source."{geom_field}"', buffer_value)
            }
        
        # Pattern 3: "schema"."table"."geom" (3-part identifier)
        three_part_pattern = r'\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"'
        match = re.match(three_part_pattern, source_geom)
        if match:
            schema, table, geom_field = match.groups()
            # Skip materialized views - they're safe to reference directly
            if table.startswith('mv_') and table.endswith('_dump'):
                self.log_debug(f"Source is materialized view '{table}' - using direct reference")
                return None
            return {
                'schema': schema,
                'table': table,
                'geom_field': geom_field
            }
        
        # Pattern 4: "table"."geom" (2-part, table reference without schema)
        # CRITICAL FIX: Handle 2-part table references for regular tables, not just MVs
        two_part_pattern = r'\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"'
        match = re.match(two_part_pattern, source_geom)
        if match:
            table, geom_field = match.groups()
            # Skip materialized views - they're safe to reference directly
            if table.startswith('mv_') and table.endswith('_dump'):
                self.log_debug(f"Source is materialized view '{table}' - using direct reference")
                return None
            # CRITICAL FIX: For regular tables without schema, use default schema "public"
            # This ensures EXISTS subquery is used to avoid "missing FROM-clause entry" error
            self.log_debug(f"Detected 2-part table reference: table='{table}', geom='{geom_field}', using schema='public'")
            return {
                'schema': 'public',
                'table': table,
                'geom_field': geom_field
            }
        
        # Not a table reference (could be WKT, ST_GeomFromText, etc.)
        self.log_info(f"🔍 _parse_source_table_reference: NO PATTERN MATCHED - returning None")
        self.log_debug(f"Source geometry is not a table reference - using direct expression")
        return None

    def _adapt_filter_for_subquery(self, filter_expr: str, schema: str, table: str) -> str:
        """
        Adapt a filter expression to work inside an EXISTS subquery.
        
        Replaces qualified table references like "schema"."table"."column" or "table"."column"
        with the subquery alias __source."column".
        
        Also strips outer parentheses to avoid syntax errors when combining with AND.
        
        Examples:
            Input:  "Distribution Cluster"."id" = 1
            Output: __source."id" = 1
            
            Input:  ("public"."Distribution Cluster"."id" = 1)
            Output: __source."id" = 1
            
            Input:  (("Structures"."SUB_TYPE" = 'Facade Point'))
            Output: __source."SUB_TYPE" = 'Facade Point'
        
        Args:
            filter_expr: Original filter expression with qualified table names
            schema: Schema name to replace
            table: Table name to replace
        
        Returns:
            Adapted filter expression using __source alias
        """
        import re
        
        def strip_balanced_outer_parens(expr: str) -> str:
            """
            Strip balanced outer parentheses from expression.
            
            Only strips if the opening '(' at position 0 matches the closing ')' at the end.
            Uses a proper parenthesis counting algorithm to verify balance.
            """
            expr = expr.strip()
            while expr.startswith('(') and expr.endswith(')'):
                # Check if these are matching outer parentheses
                # by ensuring the closing paren matches the opening one
                depth = 0
                is_outer = True
                for i, char in enumerate(expr):
                    if char == '(':
                        depth += 1
                    elif char == ')':
                        depth -= 1
                        if depth == 0 and i < len(expr) - 1:
                            # Found a closing paren before the end - not outer parens
                            is_outer = False
                            break
                if is_outer and depth == 0:
                    expr = expr[1:-1].strip()
                else:
                    break
            return expr
        
        # Step 1: Strip outer parentheses BEFORE regex substitution
        filter_expr = strip_balanced_outer_parens(filter_expr)
        
        # v2.7.9: DIAGNOSTIC - Log the adaptation parameters
        self.log_info(f"  🔄 _adapt_filter_for_subquery:")
        self.log_info(f"     → schema='{schema}', table='{table}'")
        self.log_info(f"     → input: '{filter_expr[:80]}'...")
        
        # Step 2: Apply regex substitutions for table references
        # Pattern 1: "schema"."table"."column" -> __source."column"
        three_part_pattern = rf'"{re.escape(schema)}"\s*\.\s*"{re.escape(table)}"\s*\.\s*"([^"]+)"'
        adapted = re.sub(three_part_pattern, r'__source."\1"', filter_expr)
        
        # Pattern 2: "table"."column" -> __source."column"
        two_part_pattern = rf'"{re.escape(table)}"\s*\.\s*"([^"]+)"'
        adapted = re.sub(two_part_pattern, r'__source."\1"', adapted)
        
        # v2.7.9: Log the result of adaptation
        self.log_info(f"     → output: '{adapted[:80]}'...")
        
        # Step 3: CRITICAL FIX - Strip outer parentheses AFTER regex substitution
        # The regex may have changed the structure, leaving orphan parentheses
        # Example: (("Structures"."col" = 'val')) -> ((__source."col" = 'val')) -> __source."col" = 'val'
        adapted = strip_balanced_outer_parens(adapted)
        
        # Step 4: Validate parentheses balance to catch any edge cases
        open_count = adapted.count('(')
        close_count = adapted.count(')')
        if open_count != close_count:
            self.log_warning(f"⚠️ Unbalanced parentheses in adapted filter: {open_count} open vs {close_count} close")
            self.log_warning(f"  → Original: '{filter_expr[:100]}'...")
            self.log_warning(f"  → Adapted: '{adapted[:100]}'...")
            
            # CRITICAL FIX: Remove trailing unmatched parentheses more aggressively
            # This handles cases where multiple closing parens are orphaned
            while adapted.count(')') > adapted.count('('):
                # Find and remove the last closing paren
                last_close_idx = adapted.rfind(')')
                if last_close_idx != -1:
                    adapted = adapted[:last_close_idx] + adapted[last_close_idx+1:]
                    adapted = adapted.strip()
                    self.log_info(f"  → Removed trailing ')': '{adapted[:100]}'...")
                else:
                    break
            
            # Also remove leading unmatched opening parentheses if any
            while adapted.count('(') > adapted.count(')'):
                first_open_idx = adapted.find('(')
                if first_open_idx != -1:
                    adapted = adapted[:first_open_idx] + adapted[first_open_idx+1:]
                    adapted = adapted.strip()
                    self.log_info(f"  → Removed leading '(': '{adapted[:100]}'...")
                else:
                    break
        
        # Step 5: Apply PostgreSQL type casting for numeric comparisons
        # This fixes "operator does not exist: character varying < integer" errors
        # when source layer filter contains expressions like ("importance" < 4)
        adapted = apply_postgresql_type_casting(adapted)
        
        return adapted

    def _normalize_column_case(self, expression: str, layer: QgsVectorLayer) -> str:
        """
        Normalize column names in expression to match actual PostgreSQL column case.
        
        PostgreSQL is case-sensitive for quoted identifiers. If columns were created
        without quotes (standard practice), they are stored in lowercase.
        QGIS may display or store field names with different case, causing
        "column X does not exist" errors.
        
        This function corrects column names in filter expressions to match the
        actual column names from the layer's field list.
        
        Example: "SUB_TYPE" → "sub_type" if the actual column is "sub_type"
        
        Args:
            expression: SQL expression string with potentially incorrect column case
            layer: QgsVectorLayer to get actual field names from
        
        Returns:
            Expression with corrected column names
        """
        import re
        
        if not expression or not layer:
            return expression
        
        # Get actual field names from layer
        field_names = [field.name() for field in layer.fields()]
        if not field_names:
            return expression
        
        result_expression = expression
        
        # Build case-insensitive lookup map: lowercase → actual name
        field_lookup = {name.lower(): name for name in field_names}
        
        # Find all quoted column names in expression (e.g., "SUB_TYPE")
        # This regex finds quoted identifiers: "something"
        quoted_cols = re.findall(r'"([^"]+)"', result_expression)
        
        corrections_made = []
        for col_name in quoted_cols:
            # Skip if column exists with exact case (no correction needed)
            if col_name in field_names:
                continue
            
            # Skip known non-column identifiers (schemas, tables, aliases)
            # These are typically lowercase already or are special identifiers
            if col_name in ['__source', 'public', 'geometry', 'geom']:
                continue
            
            # Check for case-insensitive match
            col_lower = col_name.lower()
            if col_lower in field_lookup:
                correct_name = field_lookup[col_lower]
                if col_name != correct_name:  # Only replace if actually different
                    # Replace the incorrectly cased column name with correct one
                    result_expression = result_expression.replace(
                        f'"{col_name}"',
                        f'"{correct_name}"'
                    )
                    corrections_made.append(f'"{col_name}" → "{correct_name}"')
        
        if corrections_made:
            self.log_info(f"🔧 PostgreSQL column case normalization: {', '.join(corrections_made)}")
        
        return result_expression

    def _apply_numeric_type_casting(self, expression: str, layer: QgsVectorLayer) -> str:
        """
        Apply ::numeric type casting to fix varchar/integer comparison errors.
        
        PostgreSQL is strict about type comparisons. When a varchar field like "importance"
        is compared to an integer (e.g., "importance" < 4), PostgreSQL throws:
        "ERROR: operator does not exist: character varying < integer"
        
        This function adds explicit ::numeric casting for numeric comparisons.
        
        Args:
            expression: SQL expression string
            layer: QgsVectorLayer to check field types
        
        Returns:
            Expression with type casting applied where needed
        """
        import re
        
        if not expression or not layer:
            return expression
        
        # Get varchar/text fields from layer
        varchar_fields = set()
        for field in layer.fields():
            type_name = field.typeName().lower()
            if type_name in ('varchar', 'text', 'character varying', 'char', 'character'):
                varchar_fields.add(field.name().lower())
        
        if not varchar_fields:
            return expression
        
        result_expression = expression
        
        # Pattern: "field" followed by comparison operator and number
        # We need to check if the field is varchar and add ::numeric if so
        numeric_comparison = re.compile(
            r'"([^"]+)"(\s*)(<|>|<=|>=)(\s*)(\d+(?:\.\d+)?)',
            re.IGNORECASE
        )
        
        def cast_if_varchar(match):
            field = match.group(1)
            space1 = match.group(2)
            operator = match.group(3)
            space2 = match.group(4)
            number = match.group(5)
            
            # Check if this field is a varchar type
            if field.lower() in varchar_fields:
                self.log_debug(f"Adding ::numeric cast to varchar field '{field}' for numeric comparison")
                return f'"{field}"::numeric{space1}{operator}{space2}{number}'
            return match.group(0)  # Return unchanged
        
        # Only apply if not already cast
        if '::numeric' not in result_expression:
            result_expression = numeric_comparison.sub(cast_if_varchar, result_expression)
        
        if result_expression != expression:
            self.log_info(f"🔧 Applied numeric type casting for varchar field comparisons")
        
        return result_expression

    def _build_simple_wkt_expression(
        self,
        geom_expr: str,
        predicate_func: str,
        source_wkt: str,
        source_srid: int,
        buffer_value: Optional[float] = None
    ) -> str:
        """
        Build a simple PostGIS expression using direct WKT geometry literal.
        
        This is the simplest and most efficient method for small source datasets.
        Instead of using EXISTS subquery, we embed the source geometry directly.
        
        Args:
            geom_expr: Target layer geometry expression (e.g., "table"."geom")
            predicate_func: PostGIS predicate (e.g., "ST_Intersects")
            source_wkt: WKT string of source geometry (already merged/unioned)
            source_srid: SRID of the source geometry
            buffer_value: Optional buffer to apply to source geometry
        
        Returns:
            Simple PostGIS expression like:
            ST_Intersects("table"."geom", ST_GeomFromText('POLYGON(...)', 31370))
        """
        self.log_debug(f"📝 _build_simple_wkt_expression: buffer_value={buffer_value}, source_srid={source_srid}")
        
        # Build source geometry from WKT
        # CRITICAL v2.9.6: Wrap in ST_MakeValid() to handle invalid source geometries
        # Source geometries can be invalid (self-intersecting, etc.) causing 0 results
        source_geom_sql = f"ST_MakeValid(ST_GeomFromText('{source_wkt}', {source_srid}))"
        
        # Apply buffer if specified (with endcap style)
        # Supports both positive (expand) and negative (shrink/erode) buffers
        # v2.4.22: Handle geographic CRS by transforming to EPSG:3857 for metric buffer
        if buffer_value is not None and buffer_value != 0:
            self.log_debug(f"  ✓ Applying buffer: {buffer_value}m")
            
            # Check if source CRS is geographic (SRID 4326 or similar)
            # Geographic CRS use degrees, so buffer in meters requires transformation
            is_geographic = source_srid == 4326 or (
                hasattr(self, 'task_params') and 
                self.task_params and 
                self.task_params.get('infos', {}).get('layer_crs_authid', '').startswith('EPSG:4') and
                source_srid < 5000  # Heuristic: low SRID numbers are often geographic
            )
            
            if is_geographic:
                # Geographic CRS: transform to EPSG:3857 for metric buffer, then back
                self.log_info(f"  🌍 Geographic CRS (SRID={source_srid}) - applying buffer via EPSG:3857")
                endcap_style = self._get_buffer_endcap_style()
                buffer_style_param = "" if endcap_style == 'round' else f", 'endcap={endcap_style}'"
                
                # Transform -> Buffer -> Transform back
                buffer_expr_3857 = (
                    f"ST_Transform("
                    f"ST_Buffer("
                    f"ST_Transform({source_geom_sql}, 3857), "
                    f"{buffer_value}{buffer_style_param}), "
                    f"{source_srid})"
                )
                
                # CRITICAL FIX v2.3.9: Wrap negative buffers in ST_MakeValid()
                # CRITICAL FIX v2.4.23: Use ST_IsEmpty() to detect ALL empty geometry types
                # CRITICAL FIX v2.5.4: Fixed bug where NULLIF only detected GEOMETRYCOLLECTION EMPTY
                if buffer_value < 0:
                    self.log_info(f"  🛡️ Wrapping negative buffer in ST_MakeValid() + ST_IsEmpty check for empty geometry handling")
                    validated_expr = f"ST_MakeValid({buffer_expr_3857})"
                    source_geom_sql = f"CASE WHEN ST_IsEmpty({validated_expr}) THEN NULL ELSE {validated_expr} END"
                else:
                    source_geom_sql = buffer_expr_3857
                
                buffer_type_str = "expansion" if buffer_value > 0 else "erosion (shrink)"
                self.log_info(f"  ✓ Applied ST_Buffer({buffer_value}m, {buffer_type_str}) via EPSG:3857 reprojection")
            else:
                # Projected CRS: buffer directly in native units
                source_geom_sql = self._build_st_buffer_with_style(source_geom_sql, buffer_value)
                buffer_type_str = "expansion" if buffer_value > 0 else "erosion (shrink)"
                self.log_debug(f"📐 Buffer APPLIED: {buffer_value}m ({buffer_type_str}) for SRID={source_srid}")
        else:
            self.log_debug(f"  ℹ️ No buffer applied (buffer_value={buffer_value})")
        
        final_expr = f"{predicate_func}({geom_expr}, {source_geom_sql})"
        self.log_debug(f"📝 _build_simple_wkt_expression FINAL: {final_expr[:200]}...")
        return final_expr

    def build_expression(
        self,
        layer_props: Dict,
        predicates: Dict,
        source_geom: Optional[str] = None,
        buffer_value: Optional[float] = None,
        buffer_expression: Optional[str] = None,
        source_filter: Optional[str] = None,
        source_wkt: Optional[str] = None,
        source_srid: Optional[int] = None,
        source_feature_count: Optional[int] = None,
        use_centroids: bool = False
    ) -> str:
        """
        Build PostGIS filter expression.
        
        Strategy based on source feature count:
        - Tiny (< SIMPLE_WKT_THRESHOLD): Use direct WKT geometry literal (simplest)
        - Larger: Use EXISTS subquery with source filter
        
        Args:
            layer_props: Layer properties (schema, table, geometry field, etc.)
            predicates: Spatial predicates to apply
            source_geom: Source geometry expression (table reference for EXISTS)
            buffer_value: Buffer distance
            buffer_expression: Expression for dynamic buffer
            source_filter: Optional filter expression for source layer (for EXISTS subqueries)
            use_centroids: If True, use ST_Centroid() on distant layer geometries for faster queries
            source_wkt: Optional WKT string for simple mode (when few source features)
            source_srid: SRID for the source WKT geometry
            source_feature_count: Number of source features (to choose strategy)
        
        Returns:
            PostGIS SQL expression string
        """
        self.log_debug(f"Building PostgreSQL expression for {layer_props.get('layer_name', 'unknown')}, buffer={buffer_value}")
        
        # v2.7.10 DIAGNOSTIC: Log source_filter value
        self.log_info(f"🔍 build_expression DEBUG: source_filter={'None' if source_filter is None else f'len={len(source_filter)}'}")
        if source_filter:
            self.log_info(f"   → source_filter preview: '{source_filter[:80]}...'")
        
        # Extract layer properties
        schema = layer_props.get("layer_schema", "public")
        # Use layer_table_name (actual source table) if available, fallback to layer_name (display name)
        table = layer_props.get("layer_table_name") or layer_props.get("layer_name")
        geom_field = layer_props.get("layer_geometry_field", "geom")
        layer = layer_props.get("layer")  # QgsVectorLayer instance
        
        # CRITICAL FIX: Get actual geometry column name using QGIS API
        if layer:
            try:
                from qgis.core import QgsDataSourceUri
                
                provider = layer.dataProvider()
                uri_string = provider.dataSourceUri()
                
                # Parse the URI to get geometry column
                uri_obj = QgsDataSourceUri(uri_string)
                geom_col_from_uri = uri_obj.geometryColumn()
                
                if geom_col_from_uri:
                    geom_field = geom_col_from_uri
                    self.log_debug(f"Found geometry column from QgsDataSourceUri: '{geom_field}'")
                else:
                    self.log_debug(f"QgsDataSourceUri.geometryColumn() returned empty, using fallback")
                    
            except Exception as e:
                self.log_warning(f"Error detecting PostgreSQL geometry column: {e}")
        
        self.log_debug(f"Using geometry field: '{geom_field}'")
        
        # Build geometry expression for target layer
        # CRITICAL FIX v2.6.7: Use UNQUALIFIED column name (without table prefix)
        # In setSubsetString context, PostgreSQL generates: SELECT * FROM schema.table WHERE <expression>
        # The target table is IMPLICIT, so using "table"."column" causes "missing FROM-clause entry" error
        # The geometry column should be referenced directly as "column" since it belongs to the target table
        geom_expr = f'"{geom_field}"'
        
        # CENTROID OPTIMIZATION v2.9.2: Convert distant layer geometry to point if enabled
        # This significantly speeds up queries for complex polygons (e.g., buildings)
        # v2.9.2: Use ST_PointOnSurface() instead of ST_Centroid() for polygons
        # ST_PointOnSurface() guarantees the point is INSIDE the polygon (better for concave shapes)
        # ST_Centroid() may return a point OUTSIDE concave polygons (L-shapes, rings, etc.)
        if use_centroids:
            centroid_mode = getattr(self, 'CENTROID_MODE', 'point_on_surface')
            geometry_type = layer_props.get("layer_geometry_type", None)
            
            # v2.9.2: Choose function based on mode and geometry type
            if centroid_mode == 'auto':
                # Auto mode: Use PointOnSurface for polygons (more accurate), Centroid for lines (faster)
                if geometry_type is not None:
                    from qgis.core import QgsWkbTypes
                    is_polygon = geometry_type in (QgsWkbTypes.PolygonGeometry, 2)  # 2 = Polygon
                    if is_polygon:
                        geom_expr = f"ST_PointOnSurface({geom_expr})"
                        self.log_info(f"✓ PostgreSQL: Using ST_PointOnSurface for polygon layer (guaranteed inside)")
                    else:
                        geom_expr = f"ST_Centroid({geom_expr})"
                        self.log_info(f"✓ PostgreSQL: Using ST_Centroid for line layer (faster)")
                else:
                    # Unknown geometry type - use PointOnSurface as safer default
                    geom_expr = f"ST_PointOnSurface({geom_expr})"
                    self.log_info(f"✓ PostgreSQL: Using ST_PointOnSurface (default for unknown geometry)")
            elif centroid_mode == 'point_on_surface':
                geom_expr = f"ST_PointOnSurface({geom_expr})"
                self.log_info(f"✓ PostgreSQL: Using ST_PointOnSurface for distant layer (guaranteed inside polygon)")
            else:
                # 'centroid' mode - use ST_Centroid (legacy behavior)
                geom_expr = f"ST_Centroid({geom_expr})"
                self.log_info(f"✓ PostgreSQL: Using ST_Centroid for distant layer geometry (faster queries)")
        
        # NOTE: Buffer is applied to SOURCE geometry, not target geometry
        # The buffer_value will be passed to source geometry expression builders
        # (e.g., _build_simple_wkt_expression, EXISTS subquery source geom)
        # This ensures "find features in target that intersect buffered source"
        
        # Dynamic buffer expression handling (for attribute-based buffer)
        if buffer_expression:
            # Dynamic buffer expression - use endcap style
            endcap_style = self._get_buffer_endcap_style()
            if endcap_style == 'round':
                geom_expr = f"ST_Buffer({geom_expr}, {buffer_expression})"
            else:
                geom_expr = f"ST_Buffer({geom_expr}, {buffer_expression}, 'endcap={endcap_style}')"
        
        # Determine strategy based on source feature count AND WKT size
        # v2.5.11: Also check WKT length to avoid very long SQL expressions
        # that can cause display issues or performance problems
        wkt_length = len(source_wkt) if source_wkt else 0
        wkt_too_long = wkt_length > self.MAX_WKT_LENGTH
        
        use_simple_wkt = (
            source_wkt is not None and 
            source_srid is not None and
            source_feature_count is not None and
            source_feature_count <= self.SIMPLE_WKT_THRESHOLD and
            not wkt_too_long  # v2.5.11: Don't use simple WKT if geometry is too complex
        )
        
        if use_simple_wkt:
            # v2.7.2: Log WKT mode usage - especially important for OGR source + PostgreSQL distant
            self.log_info(f"📝 Using SIMPLE WKT mode for {layer_props.get('layer_name', 'unknown')}")
            self.log_info(f"  - Source features: {source_feature_count} (≤ {self.SIMPLE_WKT_THRESHOLD} threshold)")
            self.log_info(f"  - WKT length: {wkt_length} chars")
            self.log_info(f"  - SRID: {source_srid}")
        elif wkt_too_long and source_feature_count <= self.SIMPLE_WKT_THRESHOLD:
            # WKT exceeds size limit even with few features (complex buffer geometry)
            self.log_info(f"⚠️ WKT too long ({wkt_length} chars > {self.MAX_WKT_LENGTH} max)")
            self.log_info(f"  → Switching from SIMPLE WKT to EXISTS subquery for better performance")
            self.log_info(f"  → Layer: {layer_props.get('layer_name', 'unknown')}")
            if wkt_length > self.WKT_SIMPLIFY_THRESHOLD:
                self.log_warning(f"  ⚠️ Very large geometry ({wkt_length} chars) - consider reducing buffer or simplifying source")
        
        # v2.7.11 DIAGNOSTIC: Log use_simple_wkt decision and source_geom info
        self.log_info(f"🔍 Strategy selection:")
        self.log_info(f"   use_simple_wkt: {use_simple_wkt}")
        self.log_info(f"   source_geom type: {type(source_geom).__name__ if source_geom else 'None'}")
        self.log_info(f"   source_geom preview: '{str(source_geom)[:80]}...'" if source_geom else "   source_geom: None")
        
        # Build predicate expressions with OPTIMIZED order
        # Sort predicates for better query performance:
        # - Most selective predicates first = faster short-circuit evaluation
        # - PostgreSQL query planner benefits from predicate ordering
        predicate_expressions = []
        
        # Extract and sort predicates by optimal order
        predicate_items = []
        for key, func in predicates.items():
            # FIX v2.7.1: Extract predicate name from the VALUE (func), not the key
            # Previously, when key was a string index like '0', this failed to match PREDICATE_ORDER
            # Now handles both old index-based format and new function-based format
            # e.g., 'ST_Intersects' -> 'intersects', or '0' key with 'ST_Intersects' value
            predicate_lower = func.lower().replace('st_', '')
            order = self.PREDICATE_ORDER.get(predicate_lower, 99)
            predicate_items.append((key, func, order))
        
        # Sort by order (most selective first)
        predicate_items.sort(key=lambda x: x[2])
        
        if len(predicate_items) > 1:
            self.log_debug(f"Predicates reordered for performance: {[p[0] for p in predicate_items]}")
        
        for predicate_name, predicate_func, _ in predicate_items:
            # STRATEGY 1: Simple WKT mode (few source features)
            # Use direct ST_GeomFromText() - simplest and most efficient for small datasets
            if use_simple_wkt:
                expr = self._build_simple_wkt_expression(
                    geom_expr=geom_expr,
                    predicate_func=predicate_func,
                    source_wkt=source_wkt,
                    source_srid=source_srid,
                    buffer_value=buffer_value  # Apply buffer to source geometry
                )
                self.log_debug(f"  ✓ Simple WKT expression: {expr[:100]}...")
                predicate_expressions.append(expr)
                continue
            
            # STRATEGY 2: EXISTS subquery mode (many source features or no WKT available)
            if source_geom:
                # CRITICAL FIX: Detect if source_geom references another table
                # Pattern: "schema"."table"."column" or ST_Buffer("schema"."table"."column", value)
                # In these cases, we MUST use EXISTS subquery because setSubsetString 
                # cannot reference other tables directly (would cause "missing FROM-clause entry" error)
                
                # Parse source_geom to extract table reference
                source_table_ref = self._parse_source_table_reference(source_geom)
                
                # v2.7.11 DIAGNOSTIC
                self.log_info(f"🔍 STRATEGY 2: source_table_ref = {'None' if source_table_ref is None else source_table_ref}")
                
                if source_table_ref:
                    # Use EXISTS subquery to avoid "missing FROM-clause entry" error
                    source_schema_name = source_table_ref['schema']
                    source_table_name = source_table_ref['table']
                    source_geom_field = source_table_ref['geom_field']
                    source_has_buffer_expr = source_table_ref.get('buffer_expr')
                    
                    # Build source geometry expression within subquery
                    # Start with base geometry reference
                    source_geom_in_subquery = f'__source."{source_geom_field}"'
                    
                    # Determine actual buffer value to apply
                    # Priority: buffer_value parameter > embedded buffer in source_geom
                    actual_buffer_value = None
                    
                    if buffer_value is not None and buffer_value != 0:
                        # Explicit buffer_value parameter takes precedence
                        actual_buffer_value = buffer_value
                        self.log_info(f"  ✓ Using explicit buffer_value parameter: {buffer_value}m")
                    elif source_has_buffer_expr:
                        # Extract buffer value from embedded ST_Buffer() expression
                        # Pattern: ST_Buffer(__source."geom", VALUE) or ST_Buffer(__source."geom", VALUE, ...)
                        import re
                        buffer_match = re.search(r'ST_Buffer\s*\([^,]+,\s*([^,)]+)', source_has_buffer_expr, re.IGNORECASE)
                        if buffer_match:
                            try:
                                actual_buffer_value = float(buffer_match.group(1).strip())
                                self.log_info(f"  ✓ Extracted buffer from source_geom: {actual_buffer_value}m")
                            except ValueError:
                                self.log_warning(f"  ⚠️ Could not parse buffer value from: {source_has_buffer_expr}")
                    
                    # Apply buffer with proper geographic CRS handling (same logic as _build_simple_wkt_expression)
                    if actual_buffer_value is not None and actual_buffer_value != 0:
                        self.log_info(f"  ✓ Applying buffer to source geometry in EXISTS: {actual_buffer_value}m")
                        if actual_buffer_value < 0:
                            self.log_info(f"  ⚠️ NEGATIVE BUFFER (erosion) in EXISTS subquery: {actual_buffer_value}m")
                        
                        # CRITICAL FIX: Check if source layer uses geographic CRS
                        # For geographic CRS (degrees), transform to EPSG:3857 for metric buffer
                        # Get source SRID from task_params (infos section contains source layer CRS)
                        source_srid_value = None
                        is_geographic = False
                        
                        if hasattr(self, 'task_params') and self.task_params:
                            source_crs_authid = self.task_params.get('infos', {}).get('source_layer_crs_authid', '')
                            if source_crs_authid.startswith('EPSG:'):
                                try:
                                    source_srid_value = int(source_crs_authid.split(':')[1])
                                    # Check if SRID indicates geographic CRS (e.g., 4326)
                                    is_geographic = source_srid_value == 4326 or (
                                        source_crs_authid.startswith('EPSG:4') and
                                        source_srid_value < 5000  # Heuristic: low SRID numbers are often geographic
                                    )
                                except (ValueError, IndexError):
                                    pass
                        
                        if is_geographic:
                            # Geographic CRS: transform to EPSG:3857 for metric buffer, then back
                            self.log_info(f"  🌍 Geographic CRS detected (SRID={source_srid_value}) - applying buffer via EPSG:3857")
                            endcap_style = self._get_buffer_endcap_style()
                            buffer_style_param = "" if endcap_style == 'round' else f", 'endcap={endcap_style}'"
                            
                            # Transform -> Buffer -> Transform back
                            buffer_expr_3857 = (
                                f"ST_Transform("
                                f"ST_Buffer("
                                f"ST_Transform({source_geom_in_subquery}, 3857), "
                                f"{actual_buffer_value}{buffer_style_param}), "
                                f"{source_srid_value})"
                            )
                            
                            # CRITICAL FIX v2.3.9: Wrap negative buffers in ST_MakeValid()
                            # CRITICAL FIX v2.4.23: Use ST_IsEmpty() to detect ALL empty geometry types
                            # CRITICAL FIX v2.5.4: Fixed bug where NULLIF only detected GEOMETRYCOLLECTION EMPTY
                            if actual_buffer_value < 0:
                                self.log_info(f"  🛡️ Wrapping negative buffer in ST_MakeValid() + ST_IsEmpty check for empty geometry handling")
                                validated_expr = f"ST_MakeValid({buffer_expr_3857})"
                                source_geom_in_subquery = f"CASE WHEN ST_IsEmpty({validated_expr}) THEN NULL ELSE {validated_expr} END"
                            else:
                                source_geom_in_subquery = buffer_expr_3857
                            
                            buffer_type_str = "expansion" if actual_buffer_value > 0 else "erosion (shrink)"
                            self.log_info(f"  ✓ Applied ST_Buffer({actual_buffer_value}m, {buffer_type_str}) via EPSG:3857 reprojection")
                        else:
                            # Projected CRS: buffer directly in native units
                            source_geom_in_subquery = self._build_st_buffer_with_style(
                                source_geom_in_subquery, 
                                actual_buffer_value
                            )
                    else:
                        self.log_info(f"  ℹ️ No buffer to apply in EXISTS (buffer_value={actual_buffer_value})")
                    
                    # CRITICAL FIX v2.5.6: Initialize where_clauses with the spatial predicate
                    # The spatial predicate MUST be the first clause in the WHERE clause
                    # 
                    # CRITICAL FIX v2.10.0: DO NOT qualify target geometry in EXISTS for setSubsetString
                    # 
                    # v2.7.16 BUG IDENTIFIED: Previous code qualified geometry as "table"."geom" for EXISTS,
                    # which was INCORRECT for setSubsetString context. This caused "missing FROM-clause entry" errors.
                    # 
                    # CONTEXT ANALYSIS:
                    # 1. setSubsetString (DIRECT mode - THIS context):
                    #    PostgreSQL executes: SELECT * FROM target WHERE <expression>
                    #    Target table is IMPLICIT in FROM clause
                    #    → Geometry MUST be unqualified: "geom"
                    #    → Using "target"."geom" causes "missing FROM-clause entry" error
                    # 
                    # 2. TwoPhaseFilter Phase 2 (DIFFERENT context - NOT this code path):
                    #    PostgreSQL executes: SELECT pk FROM target WHERE pk IN (...) AND <expression>
                    #    Target table is EXPLICIT in FROM clause
                    #    → Geometry CAN be qualified: "target"."geom"
                    #    → But TwoPhaseFilter doesn't use build_expression() for Phase 2
                    #    → It builds its own SQL with qualified columns
                    # 
                    # SOLUTION: Always use unqualified geometry (geom_expr) for EXISTS in build_expression()
                    # This function is called for setSubsetString context, not TwoPhaseFilter Phase 2
                    # 
                    # v2.10.0: Use geom_expr (already correctly set as unqualified at line 1188)
                    self.log_info(f"  ✓ v2.10.0: Using unqualified geom for EXISTS/setSubsetString: {geom_expr}")
                    
                    spatial_predicate = f"{predicate_func}({geom_expr}, {source_geom_in_subquery})"
                    where_clauses = [spatial_predicate]
                    self.log_debug(f"  ✓ Spatial predicate: {spatial_predicate[:100]}...")
                    
                    # v2.7.12 DIAGNOSTIC: Log source_filter processing in EXISTS path
                    source_filter_status = 'None' if source_filter is None else f'len={len(source_filter)}'
                    self.log_info(f"  🔍 EXISTS path: source_filter={source_filter_status}")
                    
                    if source_filter:
                        # CRITICAL FIX v2.5.11: Include source layer's spatial filter in EXISTS
                        # 
                        # The source_filter now comes from _extract_spatial_clauses_for_exists()
                        # which has already cleaned out style rules (SELECT CASE, etc.)
                        # and kept only spatial predicates like ST_Intersects with the emprise.
                        #
                        # We MUST include this filter because:
                        # 1. EXISTS queries PostgreSQL directly, not QGIS's filtered view
                        # 2. Without it, EXISTS sees ALL source features, not just filtered ones
                        # 3. This was the root cause of display issues after multi-step filtering
                        #
                        # We only skip if:
                        # - Filter contains __source alias (already adapted, would cause recursion)
                        # - Filter contains EXISTS (from previous geometric filter)
                        # - Filter contains FilterMate materialized view reference (mv_) from previous filtering
                        source_filter_upper = source_filter.upper()
                        
                        # Check for recursion/duplication indicators ONLY
                        skip_filter = any(pattern in source_filter_upper for pattern in [
                            '__SOURCE',  # Already adapted - would cause alias conflict
                            'EXISTS(',   # From previous geometric filter
                            'EXISTS ('
                        ])
                        
                        # CRITICAL FIX v2.5.12: Also skip if source filter contains FilterMate MV references
                        # Format: "fid" IN (SELECT ... FROM "filter_mate_temp"."mv_...")
                        # These are from previous multi-step geometric filters and cannot be adapted
                        # because they reference temporary materialized views, not the source table
                        #
                        # v2.8.0 EXCEPTION: Do NOT skip source selection MVs (mv_src_sel_)
                        # These are created by create_source_selection_mv() specifically for this filter
                        # and ARE designed to be used in EXISTS subqueries
                        if not skip_filter:
                            import re
                            # Check for MV reference that is NOT a source selection MV
                            has_mv_filter = bool(re.search(
                                r'IN\s*\(\s*SELECT.*FROM\s+["\']?filter_mate_temp["\']?\s*\.\s*["\']?mv_(?!src_sel_)',
                                source_filter,
                                re.IGNORECASE | re.DOTALL
                            ))
                            if has_mv_filter:
                                skip_filter = True
                                self.log_warning(f"  ⚠️ Source filter contains FilterMate MV reference (mv_) - SKIPPING")
                                self.log_warning(f"  → Filter: '{source_filter[:100]}'...")
                                self.log_warning(f"  → Reason: MV references cannot be adapted for subquery")
                            else:
                                # v2.8.0: Check if it's a source selection MV (keep this)
                                has_src_sel_mv = bool(re.search(
                                    r'IN\s*\(\s*SELECT.*FROM\s+["\']?filter_mate_temp["\']?\s*\.\s*["\']?.*mv_.*src_sel_',
                                    source_filter,
                                    re.IGNORECASE | re.DOTALL
                                ))
                                if has_src_sel_mv:
                                    self.log_info(f"  ✓ v2.8.0: Source filter uses source selection MV - KEEPING")
                        
                        # CRITICAL FIX v2.5.20: Also detect external table references
                        # If source filter contains references to tables OTHER than the source table,
                        # these cannot be adapted and would cause "missing FROM-clause entry" errors.
                        # Example: filter with "commune"."fid" when source table is "troncon_de_route"
                        #
                        # v2.8.0 EXCEPTION: filter_mate_temp schema is allowed (for source selection MVs)
                        if not skip_filter:
                            # Pattern to find ANY table references in the filter: "table"."column" or "schema"."table"."column"
                            external_table_pattern = re.compile(r'"([^"]+)"\s*\.\s*"([^"]+)"')
                            matches = external_table_pattern.findall(source_filter)
                            
                            for match in matches:
                                # match is (schema_or_table, table_or_column) or (table, column)
                                potential_table = match[0]
                                
                                # v2.8.0: Skip filter_mate_temp (allowed for source selection MVs)
                                if potential_table.lower() == 'filter_mate_temp':
                                    continue
                                
                                # Check if this reference is NOT to the source table
                                # It could be: "schema"."table" or "table"."column"
                                # We need to check if potential_table is the source table or source schema
                                if (potential_table.lower() != source_table_name.lower() and 
                                    potential_table.lower() != source_schema_name.lower()):
                                    # This could be an external table reference
                                    # Check if second part is also not the source table (for "schema"."table"."col" pattern)
                                    second_part = match[1]
                                    if second_part.lower() != source_table_name.lower():
                                        # Definitely an external table reference
                                        skip_filter = True
                                        self.log_warning(f"  ⚠️ Source filter contains EXTERNAL TABLE reference: '{potential_table}'")
                                        self.log_warning(f"  → Filter: '{source_filter[:100]}'...")
                                        self.log_warning(f"  → Reason: External table cannot be referenced in EXISTS subquery")
                                        break
                        
                        if skip_filter:
                            self.log_warning(f"  ⚠️ Source filter contains __source, EXISTS, MV, or external table reference - SKIPPING")
                            self.log_warning(f"  → Filter: '{source_filter[:100]}'...")
                            # v2.7.13: Log to QGIS panel
                            from qgis.core import QgsMessageLog, Qgis
                            QgsMessageLog.logMessage(
                                f"v2.7.13 EXISTS: source_filter SKIPPED - contains disallowed pattern",
                                "FilterMate", Qgis.Warning
                            )
                        else:
                            # CRITICAL: Replace table references with __source alias
                            # The source_filter comes from setSubsetString and contains qualified table names
                            # like "troncon_de_route"."geometrie" which must become __source."geometrie"
                            self.log_info(f"  🎯 Including source spatial filter in EXISTS:")
                            self.log_info(f"  - Original: '{source_filter[:100]}'...")
                            adapted_filter = self._adapt_filter_for_subquery(
                                source_filter, 
                                source_schema_name, 
                                source_table_name
                            )
                            
                            # CRITICAL FIX v2.5.20: Verify adapted filter doesn't have residual table references
                            # After adaptation, there should be no "table"."column" patterns left (except __source)
                            residual_table_refs = re.findall(r'"(?!__source)([^"]+)"\s*\.\s*"([^"]+)"', adapted_filter)
                            if residual_table_refs:
                                self.log_warning(f"  ⚠️ Adapted filter still has table references: {residual_table_refs}")
                                self.log_warning(f"  → Skipping filter to avoid SQL error")
                            else:
                                # Add the adapted filter to WHERE clause
                                where_clauses.append(f"({adapted_filter})")
                                self.log_info(f"  - Adapted: '{adapted_filter[:100]}'...")
                                self.log_info(f"  ✓ EXISTS will filter source to match QGIS view")
                    
                    # v2.7.12 DIAGNOSTIC: Log WHERE clauses BEFORE joining
                    self.log_info(f"  🔍 WHERE CLAUSES COUNT: {len(where_clauses)}")
                    for i, clause in enumerate(where_clauses):
                        self.log_info(f"     [{i}] {clause[:80]}...")
                    
                    where_clause = ' AND '.join(where_clauses)
                    
                    # Build EXISTS subquery
                    expr = (
                        f'EXISTS ('
                        f'SELECT 1 FROM "{source_schema_name}"."{source_table_name}" AS __source '
                        f'WHERE {where_clause}'
                        f')'
                    )
                    self.log_info(f"  ✓ Built EXISTS expression: '{expr[:150]}'...")
                    self.log_info(f"  🔍 EXISTS WHERE clause length: {len(where_clause)} chars")
                    self.log_debug(f"Using EXISTS subquery to avoid missing FROM-clause error")
                else:
                    # Simple expression (WKT, geometry literal, etc.) - can use directly
                    # CRITICAL FIX v2.6.8: Detect if source_geom is raw WKT and wrap in ST_GeomFromText
                    # When source layer is not PostgreSQL (e.g., GeoPackage), postgresql_source_geom
                    # may not be set, causing fallback to WKT. Raw WKT must be wrapped in
                    # ST_GeomFromText('WKT', SRID) for PostgreSQL to parse it as geometry.
                    source_geom_sql = source_geom
                    
                    # Check if source_geom looks like raw WKT (starts with geometry type keyword)
                    wkt_prefixes = (
                        'POINT', 'LINESTRING', 'POLYGON', 'MULTIPOINT', 'MULTILINESTRING',
                        'MULTIPOLYGON', 'GEOMETRYCOLLECTION', 'CIRCULARSTRING', 'COMPOUNDCURVE',
                        'CURVEPOLYGON', 'MULTICURVE', 'MULTISURFACE'
                    )
                    source_geom_upper = source_geom.upper().strip() if source_geom else ''
                    is_raw_wkt = any(source_geom_upper.startswith(prefix) for prefix in wkt_prefixes)
                    
                    if is_raw_wkt:
                        # CRITICAL FIX v2.7.6: Check if WKT is too large for direct embedding
                        # Large WKT (> MAX_WKT_LENGTH) can cause PostgreSQL to fail silently
                        # or return incorrect results when used in setSubsetString.
                        # In this case, return empty to trigger OGR fallback.
                        source_geom_len = len(source_geom) if source_geom else 0
                        if source_geom_len > self.MAX_WKT_LENGTH:
                            self.log_error(f"❌ STRATEGY 2 ABORT: WKT too large ({source_geom_len:,} chars > {self.MAX_WKT_LENGTH:,} max)")
                            self.log_error(f"  → Cannot embed {source_geom_len:,} char WKT into SQL expression")
                            self.log_error(f"  → Layer: {layer_props.get('layer_name', 'unknown')}")
                            self.log_error(f"  → Source geometry is too complex for PostgreSQL ST_GeomFromText")
                            self.log_error(f"  → Returning empty expression to trigger OGR fallback")
                            # Return empty string to signal failure and trigger OGR fallback
                            return ""
                        
                        self.log_warning(f"⚠️ source_geom is raw WKT - wrapping in ST_GeomFromText()")
                        
                        # Get SRID from source layer or fallback to default
                        fallback_srid = 4326  # Default WGS84
                        if source_srid is not None:
                            fallback_srid = source_srid
                        elif hasattr(self, 'task_params') and self.task_params:
                            source_crs_authid = self.task_params.get('infos', {}).get('source_layer_crs_authid', '')
                            if source_crs_authid.startswith('EPSG:'):
                                try:
                                    fallback_srid = int(source_crs_authid.split(':')[1])
                                except (ValueError, IndexError):
                                    pass
                        
                        # Wrap WKT in ST_GeomFromText
                        # CRITICAL v2.9.6: Wrap in ST_MakeValid() to handle invalid source geometries
                        source_geom_sql = f"ST_MakeValid(ST_GeomFromText('{source_geom}', {fallback_srid}))"
                        self.log_info(f"  ✓ Wrapped WKT in ST_MakeValid(ST_GeomFromText()) with SRID={fallback_srid}")
                        
                        # Apply buffer if needed
                        if buffer_value is not None and buffer_value != 0:
                            self.log_info(f"  ✓ Applying buffer {buffer_value}m to WKT geometry")
                            source_geom_sql = self._build_st_buffer_with_style(source_geom_sql, buffer_value)
                    
                    expr = f"{predicate_func}({geom_expr}, {source_geom_sql})"
                
                predicate_expressions.append(expr)
            
            # STRATEGY 3: WKT fallback for OGR source layers (v2.7.4)
            # When WKT is too long but source_geom is None (OGR/GeoPackage source layer),
            # we MUST still use WKT because there's no alternative. Without this fallback,
            # the filter expression is empty and returns ALL features unfiltered!
            # This happens when selecting complex geometries from GeoPackage layers.
            # CRITICAL FIX v2.7.6: Check WKT size - if too large, return empty to trigger OGR fallback
            elif source_wkt is not None and source_srid is not None:
                # v2.7.6: Check if WKT is too large for PostgreSQL embedding
                if wkt_length > self.MAX_WKT_LENGTH:
                    self.log_error(f"❌ STRATEGY 3 ABORT: WKT too large ({wkt_length:,} chars > {self.MAX_WKT_LENGTH:,} max)")
                    self.log_error(f"  → Cannot embed {wkt_length:,} char WKT into SQL expression")
                    self.log_error(f"  → Layer: {layer_props.get('layer_name', 'unknown')}")
                    self.log_error(f"  → Source geometry is too complex for PostgreSQL ST_GeomFromText")
                    self.log_error(f"  → Returning empty expression to trigger OGR fallback")
                    return ""
                
                self.log_warning(f"⚠️ STRATEGY 3: WKT fallback for OGR source layer")
                self.log_warning(f"  → source_geom is None (non-PostgreSQL source)")
                self.log_warning(f"  → WKT is large ({wkt_length} chars) but no alternative available")
                self.log_warning(f"  → Using WKT anyway - may cause slow queries for very complex geometries")
                
                # Use the same logic as STRATEGY 1 (simple WKT) but with a warning
                expr = self._build_simple_wkt_expression(
                    geom_expr=geom_expr,
                    predicate_func=predicate_func,
                    source_wkt=source_wkt,
                    source_srid=source_srid,
                    buffer_value=buffer_value
                )
                self.log_info(f"  ✓ WKT fallback expression built: {expr[:100]}...")
                predicate_expressions.append(expr)
            else:
                # No valid geometry source available - log error
                self.log_error(f"❌ No geometry source available for {layer_props.get('layer_name', 'unknown')}")
                self.log_error(f"  → source_geom: {source_geom is not None}")
                self.log_error(f"  → source_wkt: {source_wkt is not None}")
                self.log_error(f"  → source_srid: {source_srid}")
                
                # v2.8.2 FIX: Return "0 features" filter instead of empty string
                # When no valid geometry source is available, this means no intersection is possible.
                # Instead of returning "" (which causes old filter to persist or fallback to show all features),
                # we return an IMPOSSIBLE condition that filters to 0 features.
                self.log_warning(f"  → v2.8.2: Generating '0 features' filter instead of empty expression")
                layer = layer_props.get('layer')
                if layer:
                    from ..appUtils import get_primary_key_name
                    key_column = get_primary_key_name(layer)
                    zero_filter = f'"{key_column}" IS NULL AND "{key_column}" IS NOT NULL'
                    self.log_info(f"  ✓ Zero filter: {zero_filter}")
                    predicate_expressions.append(zero_filter)
                else:
                    self.log_error(f"  → Cannot generate zero filter: no layer in layer_props")
        
        # Combine predicates with OR
        if predicate_expressions:
            # CRITICAL FIX v2.10.0: Deduplicate identical expressions
            # Bug: filter_task.py stores BOTH string and numeric keys for same predicate
            # (e.g., 'ST_Intersects': 'ST_Intersects' AND 0: 'ST_Intersects')
            # This causes build_expression() to generate duplicate EXISTS clauses
            # Example: EXISTS(...) OR EXISTS(...) with identical content
            unique_expressions = list(dict.fromkeys(predicate_expressions))  # Preserve order
            if len(unique_expressions) < len(predicate_expressions):
                removed = len(predicate_expressions) - len(unique_expressions)
                self.log_info(f"🔧 v2.10.0: Removed {removed} duplicate predicate expression(s)")
                self.log_info(f"   Original: {len(predicate_expressions)} expressions")
                self.log_info(f"   Deduplicated: {len(unique_expressions)} unique expressions")
            
            combined = " OR ".join(unique_expressions)
            self.log_debug(f"PostgreSQL FINAL expression ({len(combined)} chars): {combined[:200]}...")
            return combined
        
        # v2.8.2 FIX: If still no expressions, return a hard-coded impossible condition
        # This ensures 0 features are displayed instead of all features
        self.log_warning(f"❌ No predicate expressions generated - returning impossible filter for 0 features")
        return "1 = 0"  # Universal FALSE condition that all SQL databases understand
    
    def apply_filter(
        self,
        layer: QgsVectorLayer,
        expression: str,
        old_subset: Optional[str] = None,
        combine_operator: Optional[str] = None
    ) -> bool:
        """
        Apply filter to PostgreSQL layer.
        
        Strategy adapts based on dataset size:
        - Small datasets (< 10k features): Direct setSubsetString for simplicity
        - Large datasets (≥ 10k features): Materialized views with spatial indexes
        
        Args:
            layer: PostgreSQL layer to filter
            expression: PostGIS SQL expression
            old_subset: Existing subset string
            combine_operator: Operator to combine filters (AND/OR)
        
        Returns:
            True if filter applied successfully
        """
        start_time = time.time()
        
        try:
            if not expression:
                self.log_warning("Empty expression, skipping filter")
                return False
            
            # CRITICAL FIX: Normalize column names in expression and old_subset
            # PostgreSQL is case-sensitive for quoted identifiers. Columns created without
            # quotes are stored lowercase, but QGIS may use uppercase (e.g., "SUB_TYPE").
            # This causes "column X does not exist" errors.
            expression = self._normalize_column_case(expression, layer)
            if old_subset:
                old_subset = self._normalize_column_case(old_subset, layer)
            
            # CRITICAL FIX v2.4.14: Apply numeric type casting for varchar fields
            # This fixes "operator does not exist: character varying < integer" errors
            # Example: "importance" < 4 → "importance"::numeric < 4 when importance is varchar
            expression = self._apply_numeric_type_casting(expression, layer)
            if old_subset:
                old_subset = self._apply_numeric_type_casting(old_subset, layer)
            
            # Get feature count to determine strategy
            feature_count = layer.featureCount()
            
            # Check if layer uses ctid (no primary key)
            from ..appUtils import get_primary_key_name
            key_column = get_primary_key_name(layer)
            uses_ctid = (key_column == 'ctid')
            
            # v2.5.9: Estimate query complexity for adaptive strategy
            complexity_score = 0.0
            if COMPLEXITY_ESTIMATOR_AVAILABLE:
                try:
                    complexity_score = estimate_query_complexity(expression, feature_count)
                    self.log_debug(f"📊 Query complexity score: {complexity_score:.1f}")
                except Exception as e:
                    self.log_debug(f"Could not estimate complexity: {e}")
            
            # CRITICAL FIX v2.5.10: Intelligently handle existing subset during geometric filtering
            # - REPLACE existing subset if it contains geometric predicates (EXISTS, ST_*, __source)
            # - COMBINE with existing subset if it's a simple attribute filter
            # 
            # This preserves user's attribute filters while avoiding nested geometric filters
            # which would cause SQL errors like:
            # - "missing FROM-clause entry for table __source"
            # - nested EXISTS subqueries
            # - type mismatch errors from style expressions
            if old_subset:
                old_subset_upper = old_subset.upper()
                
                # Check if old_subset contains geometric filter patterns
                is_geometric_filter = (
                    '__source' in old_subset.lower() or
                    'EXISTS (' in old_subset_upper or
                    'EXISTS(' in old_subset_upper or
                    any(pred in old_subset_upper for pred in [
                        'ST_INTERSECTS', 'ST_CONTAINS', 'ST_WITHIN', 'ST_TOUCHES',
                        'ST_OVERLAPS', 'ST_CROSSES', 'ST_DISJOINT', 'ST_EQUALS',
                        'ST_DWITHIN', 'ST_COVERS', 'ST_COVEREDBY', 'ST_BUFFER'
                    ])
                )
                
                # CRITICAL FIX v2.5.11: Detect FilterMate materialized view references
                # Format: "fid" IN (SELECT ... FROM "filter_mate_temp"."mv_...")
                # These are previous geometric filters that should be REPLACED
                import re
                has_mv_filter = bool(re.search(
                    r'IN\s*\(\s*SELECT.*FROM\s+["\']?filter_mate_temp["\']?\s*\.\s*["\']?mv_',
                    old_subset,
                    re.IGNORECASE | re.DOTALL
                ))
                
                # Check for style/display expression patterns that should be replaced
                # CRITICAL FIX v2.5.10: Enhanced detection for SELECT CASE expressions
                # These come from QGIS rule-based symbology and cannot be used in SQL WHERE clauses
                is_style_expression = any(re.search(pattern, old_subset, re.IGNORECASE | re.DOTALL) for pattern in [
                    r'AND\s+TRUE\s*\)',              # Rule-based style pattern
                    r'THEN\s+true\b',                # CASE THEN true
                    r'THEN\s+false\b',               # CASE THEN false  
                    r'coalesce\s*\([^)]+,\s*\'',     # Display expression
                    r'SELECT\s+CASE\s+',             # SELECT CASE expression from rule-based styles
                    r'\(\s*CASE\s+WHEN\s+.+THEN\s+true',  # CASE WHEN ... THEN true
                ])
                
                if is_geometric_filter or has_mv_filter:
                    reason = "Cannot nest geometric filters"
                    if has_mv_filter:
                        reason = "Previous FilterMate materialized view filter (mv_) must be replaced"
                    elif is_geometric_filter:
                        reason = "Cannot nest geometric filters (EXISTS, ST_*, __source)"
                    self.log_info(f"🔄 Existing subset contains GEOMETRIC filter - will be REPLACED")
                    self.log_info(f"  → Existing: '{old_subset[:100]}...'")
                    self.log_info(f"  → Reason: {reason}")
                    old_subset = None  # Replace geometric filters
                elif is_style_expression:
                    self.log_info(f"🔄 Existing subset contains STYLE expression - will be REPLACED")
                    self.log_info(f"  → Existing: '{old_subset[:100]}...'")
                    self.log_info(f"  → Reason: Style expressions cause type mismatch errors")
                    old_subset = None  # Replace style expressions
                else:
                    # Simple attribute filter - PRESERVE and COMBINE
                    self.log_info(f"✅ Existing subset is ATTRIBUTE filter - will be COMBINED")
                    self.log_info(f"  → Existing: '{old_subset[:100]}...'")
                    self.log_info(f"  → Reason: Preserving user's attribute filter with geometric filter")
                    # old_subset is kept - will be combined below
            
            # Check if expression already contains EXISTS subquery
            has_exists_subquery = 'EXISTS (' in expression.upper()
            
            # DIAGNOSTIC: Log filter status
            self.log_info(f"🔍 Filter preparation:")
            self.log_info(f"  - Expression contains EXISTS: {has_exists_subquery}")
            self.log_info(f"  - Expression length: {len(expression)} chars")
            self.log_info(f"  - Complexity score: {complexity_score:.1f}")
            self.log_info(f"  - Preserve old_subset: {old_subset is not None}")
            
            # CRITICAL FIX v2.5.10: Combine attribute filter with geometric filter
            # If old_subset is still set (was determined to be an attribute filter),
            # combine it with the geometric expression using AND operator
            # 
            # CRITICAL FIX v2.9.42: Respect combine_operator=None as REPLACE signal
            # When combine_operator is explicitly None (not just missing), it means:
            # "Replace old_subset, don't combine" - used for FID filters in multi-step filtering
            if old_subset:
                # Check if combine_operator is explicitly None (REPLACE signal)
                if combine_operator is None:
                    # Explicit None = REPLACE the old filter
                    self.log_info(f"🔄 combine_operator=None → REPLACING old subset (multi-step filter)")
                    self.log_info(f"  → Old subset: '{old_subset[:100]}...'")
                    final_expression = expression
                else:
                    # Use provided operator or default to AND
                    op = combine_operator if combine_operator else 'AND'
                    final_expression = f"({old_subset}) {op} ({expression})"
                    self.log_info(f"✅ Combined expression: ({len(final_expression)} chars)")
                    self.log_info(f"  → Attribute filter + {op} + Geometric filter")
                    self.log_debug(f"  → Combined: {final_expression[:200]}...")
            else:
                final_expression = expression
            
            # Decide strategy based on dataset size, complexity, and primary key availability
            # v2.5.x: Also check PSYCOPG2_AVAILABLE for advanced features (MVs, progressive filter)
            if uses_ctid:
                # No primary key (using ctid) - MUST use direct method
                self.log_info(
                    f"PostgreSQL: Layer without PRIMARY KEY (using ctid). "
                    f"Using direct filtering (materialized views disabled)."
                )
                return self._apply_direct(layer, final_expression)
            
            # v2.5.x: If psycopg2 not available, always use direct method (QGIS native API)
            elif not PSYCOPG2_AVAILABLE:
                self.log_info(
                    f"PostgreSQL: psycopg2 not available - using QGIS native API (setSubsetString). "
                    f"MVs and progressive filtering disabled. Feature count: {feature_count:,}"
                )
                return self._apply_direct(layer, final_expression)
            
            # v2.5.9: Check if two-phase or progressive filtering should be used
            elif (PROGRESSIVE_FILTER_AVAILABLE and 
                  complexity_score >= self.TWO_PHASE_COMPLEXITY_THRESHOLD and
                  feature_count >= self.MATERIALIZED_VIEW_THRESHOLD):
                # Complex expression on large dataset - use two-phase filtering
                self.log_info(
                    f"📦 PostgreSQL: Complex expression (score={complexity_score:.1f}) on "
                    f"{feature_count:,} features. Using TWO-PHASE filtering for 3-10x speedup."
                )
                return self._apply_with_progressive_filter(
                    layer, final_expression, feature_count, complexity_score
                )
            
            elif feature_count >= self.MATERIALIZED_VIEW_THRESHOLD:
                # Large dataset with PK - use materialized views
                if feature_count >= self.LARGE_DATASET_THRESHOLD:
                    self.log_info(
                        f"PostgreSQL: Very large dataset ({feature_count:,} features). "
                        f"Using materialized views with spatial index for optimal performance."
                    )
                else:
                    self.log_info(
                        f"PostgreSQL: Large dataset ({feature_count:,} features ≥ {self.MATERIALIZED_VIEW_THRESHOLD:,}). "
                        f"Using materialized views for better performance."
                    )
                
                return self._apply_with_materialized_view(layer, final_expression)
            
            # v2.8.7: Check if expression contains expensive spatial predicates
            # that require materialization even for small datasets.
            # This prevents slow canvas rendering from re-executing EXISTS + ST_Buffer
            # on every pan/zoom/render operation.
            elif self._has_expensive_spatial_expression(final_expression):
                self.log_info(
                    f"PostgreSQL: Complex spatial expression detected (EXISTS/ST_Buffer/ST_Intersects) "
                    f"on {feature_count:,} features. Using materialized views to cache result "
                    f"and prevent slow canvas rendering."
                )
                return self._apply_with_materialized_view(layer, final_expression)
            
            else:
                # Small dataset with simple expression - use direct setSubsetString
                self.log_info(
                    f"PostgreSQL: Small dataset ({feature_count:,} features < {self.MATERIALIZED_VIEW_THRESHOLD:,}). "
                    f"Using direct setSubsetString for simplicity."
                )
                
                return self._apply_direct(layer, final_expression)
            
        except Exception as e:
            self.log_error(f"Error applying filter: {str(e)}")
            import traceback
            self.log_debug(f"Traceback: {traceback.format_exc()}")
            return False
    
    def _apply_with_progressive_filter(
        self,
        layer: QgsVectorLayer,
        expression: str,
        feature_count: int,
        complexity_score: float
    ) -> bool:
        """
        Apply filter using progressive/multi-step filtering for complex queries.
        
        This method is optimized for:
        - Complex expressions with multiple spatial predicates
        - Large datasets where bounding box pre-filtering reduces candidates significantly
        - Combined attribute + geometric filters (attribute-first strategy)
        - Memory-efficient streaming for very large result sets
        
        v2.5.10 Strategies (in order of preference):
        1. MULTI-STEP ATTRIBUTE-FIRST: If attribute filter is highly selective
           - Apply attribute filter first (uses B-tree indexes)
           - Then apply bbox pre-filter on reduced set
           - Finally apply full spatial predicate
        2. TWO-PHASE: Classic bbox pre-filter + full predicate
        3. PROGRESSIVE STREAMING: Chunked lazy cursor for very large results
        
        Performance:
        - 5-20x faster with selective attribute filters
        - 3-10x faster than single-phase on complex expressions
        - 50-80% memory reduction via streaming
        
        Args:
            layer: Target PostgreSQL layer
            expression: Full SQL WHERE clause
            feature_count: Target feature count
            complexity_score: Query complexity score
        
        Returns:
            True if filter applied successfully
        """
        start_time = time.time()
        
        try:
            # Get database connection
            if CONNECTION_POOL_AVAILABLE and pooled_connection_from_layer:
                # Use pooled connection for better performance
                pool_context = pooled_connection_from_layer(layer)
                conn, source_uri = pool_context.__enter__()
                use_pool = True
            else:
                conn, source_uri = get_datasource_connexion_from_layer(layer)
                use_pool = False
                
            if not conn:
                self.log_warning("No PostgreSQL connection, falling back to MV method")
                return self._apply_with_materialized_view(layer, expression)
            
            # Build layer properties for executor
            from ..appUtils import get_primary_key_name
            key_column = get_primary_key_name(layer)
            
            layer_props = {
                'layer_schema': source_uri.schema() or "public",
                'layer_table_name': source_uri.table(),
                'layer_geometry_field': source_uri.geometryColumn() or "geom",
                'layer_pk': key_column,
                'layer_srid': layer.crs().postgisSrid() if layer.crs().isValid() else 4326,
                'feature_count': feature_count,
                'has_spatial_index': True  # Assume PostgreSQL layers have GIST index
            }
            
            # Extract source bounds from task_params if available
            source_bounds = self._extract_source_bounds_from_params()
            
            # v2.5.10: Try multi-step filter optimization if available
            if MULTI_STEP_FILTER_AVAILABLE and feature_count >= 50000:
                result = self._try_multi_step_filter(
                    conn, layer, layer_props, expression, 
                    source_bounds, key_column, start_time
                )
                if result is not None:
                    if use_pool:
                        pool_context.__exit__(None, None, None)
                    return result
            
            # Determine if two-phase is beneficial
            use_two_phase = (
                source_bounds is not None and
                complexity_score >= self.TWO_PHASE_COMPLEXITY_THRESHOLD
            )
            
            if use_two_phase:
                self.log_info(f"🚀 Using TWO-PHASE filter (bbox pre-filter + full predicate)")
                
                # Create LayerProperties for two-phase filter
                lp = LayerProperties(
                    schema=layer_props['layer_schema'],
                    table=layer_props['layer_table_name'],
                    geometry_column=layer_props['layer_geometry_field'],
                    primary_key=key_column,
                    srid=layer_props['layer_srid'],
                    estimated_feature_count=feature_count,
                    has_spatial_index=True
                )
                
                # Create two-phase filter
                two_phase = TwoPhaseFilter(conn, lp, chunk_size=5000)
                
                # Execute two-phase filtering
                result = two_phase.execute(
                    full_expression=expression,
                    source_bbox=source_bounds
                )
                
                if result.success and result.feature_ids:
                    # Build IN clause from result IDs
                    final_expression = self._build_in_clause_expression(
                        result.feature_ids, key_column
                    )
                    
                    # Log performance metrics
                    elapsed_ms = (time.time() - start_time) * 1000
                    self.log_info(
                        f"✓ Two-phase complete: {result.feature_count:,} features "
                        f"(Phase1: {result.phase1_time_ms:.1f}ms → {result.candidates_after_phase1:,} candidates, "
                        f"Phase2: {result.phase2_time_ms:.1f}ms, "
                        f"Total: {elapsed_ms:.1f}ms)"
                    )
                    
                    # Apply via queue callback or direct
                    queue_callback = self.task_params.get('_subset_queue_callback')
                    if queue_callback:
                        queue_callback(layer, final_expression)
                        return True
                    else:
                        return safe_set_subset_string(layer, final_expression)
                
                elif result.success and result.feature_count == 0:
                    # No results - apply empty filter
                    self.log_info("Two-phase filter: 0 features matched")
                    empty_expr = f'"{key_column}" IS NULL AND "{key_column}" IS NOT NULL'
                    queue_callback = self.task_params.get('_subset_queue_callback')
                    if queue_callback:
                        queue_callback(layer, empty_expr)
                        return True
                    return safe_set_subset_string(layer, empty_expr)
                
                else:
                    # Error in two-phase - fall back
                    self.log_warning(f"Two-phase filter failed: {result.error}, falling back to MV")
                    conn.close()
                    return self._apply_with_materialized_view(layer, expression)
            
            else:
                # Use lazy cursor streaming for memory efficiency
                self.log_info(f"🌊 Using LAZY CURSOR streaming (memory-efficient)")
                
                executor = ProgressiveFilterExecutor(conn, layer_props)
                result = executor.execute_optimal(
                    expression=expression,
                    complexity_score=complexity_score
                )
                
                if result.success and result.feature_ids:
                    final_expression = self._build_in_clause_expression(
                        result.feature_ids, key_column
                    )
                    
                    elapsed_ms = (time.time() - start_time) * 1000
                    self.log_info(
                        f"✓ Progressive filter complete: {result.feature_count:,} features "
                        f"in {elapsed_ms:.1f}ms (strategy: {result.strategy_used.value})"
                    )
                    
                    queue_callback = self.task_params.get('_subset_queue_callback')
                    if queue_callback:
                        queue_callback(layer, final_expression)
                        return True
                    return safe_set_subset_string(layer, final_expression)
                
                elif result.success:
                    self.log_info("Progressive filter: 0 features matched")
                    empty_expr = f'"{key_column}" IS NULL AND "{key_column}" IS NOT NULL'
                    queue_callback = self.task_params.get('_subset_queue_callback')
                    if queue_callback:
                        queue_callback(layer, empty_expr)
                        return True
                    return safe_set_subset_string(layer, empty_expr)
                
                else:
                    self.log_warning(f"Progressive filter failed: {result.error}, falling back to MV")
                    conn.close()
                    return self._apply_with_materialized_view(layer, expression)
            
        except Exception as e:
            self.log_error(f"Progressive filter error: {e}")
            import traceback
            self.log_debug(traceback.format_exc())
            # Fall back to materialized view method
            return self._apply_with_materialized_view(layer, expression)
    
    def _try_multi_step_filter(
        self,
        conn,
        layer: QgsVectorLayer,
        layer_props: Dict,
        expression: str,
        source_bounds: Optional[Tuple[float, float, float, float]],
        key_column: str,
        start_time: float
    ) -> Optional[bool]:
        """
        Try to use multi-step filter optimization for combined attribute + geometry filters.
        
        v2.5.10: Intelligent filter ordering based on selectivity estimation.
        
        The key insight is that attribute filters (using B-tree indexes) are often
        much faster than spatial predicates. If the attribute filter is selective
        (filters out >90% of rows), applying it FIRST dramatically reduces the
        candidates for the expensive spatial operation.
        
        Example performance on 500k features with status='active' (1% of rows):
        - GEOMETRY-FIRST: ST_Intersects on 500k → 25k results, 15 seconds
        - ATTRIBUTE-FIRST: status filter → 5k rows → ST_Intersects → 250 results, 0.5 seconds
        
        Args:
            conn: PostgreSQL connection
            layer: Target layer
            layer_props: Layer properties dict
            expression: Complete WHERE clause
            source_bounds: Source geometry bounding box
            key_column: Primary key column name
            start_time: Start timestamp for performance logging
        
        Returns:
            True/False if handled, None to fall through to other strategies
        """
        try:
            # Parse expression to separate attribute and spatial components
            attribute_expr, spatial_expr = self._split_expression_components(expression)
            
            # Only use multi-step if we have both components
            if not attribute_expr or not spatial_expr:
                self.log_debug("Expression has only one component, skipping multi-step")
                return None
            
            self.log_info(f"🔬 Analyzing expression for MULTI-STEP optimization:")
            self.log_info(f"   Attribute component: {attribute_expr[:80]}...")
            self.log_info(f"   Spatial component: {spatial_expr[:80]}...")
            
            # Create multi-step optimizer
            optimizer = MultiStepFilterOptimizer(
                conn, layer_props, use_statistics=True
            )
            
            # Get optimal execution plan
            strategy, steps = optimizer.create_optimal_plan(
                attribute_expr=attribute_expr,
                spatial_expr=spatial_expr,
                source_bbox=source_bounds
            )
            
            self.log_info(f"📊 Multi-step plan: {strategy.value} with {len(steps)} steps")
            for i, step in enumerate(steps, 1):
                self.log_debug(f"   Step {i}: {step.step_type.name} (selectivity: {step.estimated_selectivity:.3f})")
            
            # Only proceed if multi-step provides benefit
            if strategy.value == 'direct':
                self.log_debug("Multi-step recommends direct execution, falling through")
                return None
            
            # Execute multi-step plan
            result = optimizer.filter_optimal(
                attribute_expr=attribute_expr,
                spatial_expr=spatial_expr,
                source_bbox=source_bounds
            )
            
            if result.success and result.feature_ids:
                # Build IN clause from result IDs
                final_expression = self._build_in_clause_expression(
                    result.feature_ids, key_column
                )
                
                elapsed_ms = (time.time() - start_time) * 1000
                self.log_info(
                    f"✅ Multi-step filter complete ({result.strategy_used.value}):"
                )
                self.log_info(f"   {result.feature_count:,} features in {elapsed_ms:.1f}ms")
                self.log_info(f"   Overall reduction: {result.overall_reduction_ratio:.1%}")
                self.log_info(f"   Steps executed: {result.steps_executed}")
                
                # Log step breakdown
                for i, step_result in enumerate(result.step_results, 1):
                    self.log_debug(
                        f"   Step {i} ({step_result.step_type.name}): "
                        f"{step_result.candidate_count:,} candidates, "
                        f"{step_result.execution_time_ms:.1f}ms"
                    )
                
                # Apply via queue callback or direct
                queue_callback = self.task_params.get('_subset_queue_callback')
                if queue_callback:
                    queue_callback(layer, final_expression)
                    return True
                else:
                    return safe_set_subset_string(layer, final_expression)
            
            elif result.success and result.feature_count == 0:
                # No results
                self.log_info("Multi-step filter: 0 features matched")
                empty_expr = f'"{key_column}" IS NULL AND "{key_column}" IS NOT NULL'
                queue_callback = self.task_params.get('_subset_queue_callback')
                if queue_callback:
                    queue_callback(layer, empty_expr)
                    return True
                return safe_set_subset_string(layer, empty_expr)
            
            else:
                # Error - fall through to other strategies
                self.log_warning(f"Multi-step filter failed: {result.error}")
                return None
            
        except Exception as e:
            self.log_debug(f"Multi-step filter unavailable: {e}")
            return None
    
    def _split_expression_components(self, expression: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Split a combined expression into attribute and spatial components.
        
        Identifies spatial predicates (ST_*, EXISTS with geometry) and separates
        them from non-spatial (attribute) predicates.
        
        Args:
            expression: Combined SQL WHERE clause
        
        Returns:
            (attribute_expression, spatial_expression)
        """
        import re
        
        # Spatial predicate patterns
        spatial_patterns = [
            r'ST_\w+\s*\([^)]+\)',  # ST_Intersects(...), ST_Contains(...), etc.
            r'EXISTS\s*\(\s*SELECT',  # EXISTS subquery (typically spatial join)
            r'"\w+"\s*&&\s*',  # Bounding box operator
        ]
        
        # Check if expression contains spatial predicates
        has_spatial = any(re.search(p, expression, re.IGNORECASE) for p in spatial_patterns)
        
        if not has_spatial:
            # Pure attribute expression
            return (expression, None)
        
        # Try to split on AND at the top level
        # This is a simplified parser - works for common cases
        
        # Find top-level AND operators (not inside parentheses)
        parts = []
        current = ""
        depth = 0
        
        i = 0
        while i < len(expression):
            char = expression[i]
            
            if char == '(':
                depth += 1
                current += char
            elif char == ')':
                depth -= 1
                current += char
            elif depth == 0 and expression[i:i+4].upper() == ' AND':
                # Found top-level AND
                if current.strip():
                    parts.append(current.strip())
                current = ""
                i += 3  # Skip "AND"
            else:
                current += char
            
            i += 1
        
        if current.strip():
            parts.append(current.strip())
        
        # Classify each part
        attribute_parts = []
        spatial_parts = []
        
        for part in parts:
            # Remove surrounding parentheses for analysis
            test_part = part.strip()
            while test_part.startswith('(') and test_part.endswith(')'):
                test_part = test_part[1:-1].strip()
            
            is_spatial = any(re.search(p, test_part, re.IGNORECASE) for p in spatial_patterns)
            
            if is_spatial:
                spatial_parts.append(part)
            else:
                attribute_parts.append(part)
        
        # Build result expressions
        attribute_expr = " AND ".join(attribute_parts) if attribute_parts else None
        spatial_expr = " AND ".join(spatial_parts) if spatial_parts else None
        
        return (attribute_expr, spatial_expr)

    def _extract_source_bounds_from_params(self) -> Optional[Tuple[float, float, float, float]]:
        """
        Extract source geometry bounding box from task_params.
        
        Returns:
            Tuple (xmin, ymin, xmax, ymax) or None if not available
        """
        try:
            if not self.task_params:
                return None
            
            # Try to get bounds from filtering parameters
            filtering = self.task_params.get('filtering', {})
            
            # Check for explicit source bounds
            if 'source_bounds' in filtering:
                bounds = filtering['source_bounds']
                if isinstance(bounds, (list, tuple)) and len(bounds) == 4:
                    return tuple(float(x) for x in bounds)
            
            # Try to extract from source WKT if available
            source_wkt = filtering.get('source_wkt')
            if source_wkt and TwoPhaseFilter:
                # Use TwoPhaseFilter's bbox extraction
                dummy_props = LayerProperties()
                # We need a connection - return None and let caller handle
                return None
            
            # Try to get from source layer extent
            infos = self.task_params.get('infos', {})
            source_extent = infos.get('source_layer_extent')
            if source_extent:
                if isinstance(source_extent, dict):
                    return (
                        source_extent.get('xmin', 0),
                        source_extent.get('ymin', 0),
                        source_extent.get('xmax', 0),
                        source_extent.get('ymax', 0)
                    )
            
            return None
            
        except Exception as e:
            self.log_debug(f"Could not extract source bounds: {e}")
            return None
    
    def _is_pk_numeric(self, layer: QgsVectorLayer, pk_field: str = None) -> bool:
        """
        Check if the primary key field is numeric.
        
        CRITICAL FIX v2.8.5: UUID fields and other text-based PKs must be quoted in SQL.
        
        Args:
            layer: QgsVectorLayer to check
            pk_field: Primary key field name (optional, auto-detected if None)
            
        Returns:
            bool: True if PK is numeric (int, bigint, etc.), False if text (UUID, varchar, etc.)
        """
        if not layer:
            return True  # Default to numeric
        
        # Auto-detect PK field if not provided
        if not pk_field:
            pk_indices = layer.primaryKeyAttributes()
            if pk_indices:
                pk_field = layer.fields().field(pk_indices[0]).name()
            else:
                pk_field = 'id'  # Default
        
        try:
            field_idx = layer.fields().indexOf(pk_field)
            if field_idx >= 0:
                field = layer.fields().field(field_idx)
                return field.isNumeric()
        except Exception as e:
            self.log_debug(f"Could not determine PK type, assuming numeric: {e}")
        
        return True
    
    def _format_pk_values_for_sql(self, values: list, is_numeric: bool = None, 
                                   layer: QgsVectorLayer = None, pk_field: str = None) -> str:
        """
        Format primary key values for SQL IN clause.
        
        CRITICAL FIX v2.8.5: UUID fields must be quoted with single quotes in SQL.
        Example: 
            - Numeric: IN (1, 2, 3)
            - UUID/Text: IN ('7b2e1a3e-b812-4d51-bf33-7f0cd0271ef3', ...)
        
        Args:
            values: List of primary key values
            is_numeric: Whether PK is numeric (optional, auto-detected if None)
            layer: QgsVectorLayer to check PK type (optional)
            pk_field: Primary key field name (optional)
            
        Returns:
            str: Comma-separated values formatted for SQL IN clause
        """
        if not values:
            return ''
        
        # Auto-detect if not specified
        if is_numeric is None:
            is_numeric = self._is_pk_numeric(layer, pk_field)
        
        if is_numeric:
            # Numeric: simple conversion to string
            return ', '.join(str(v) for v in values)
        else:
            # Text/UUID: quote with single quotes, escape existing quotes
            formatted = []
            for v in values:
                # Convert to string and escape single quotes
                str_val = str(v).replace("'", "''")
                formatted.append(f"'{str_val}'")
            return ', '.join(formatted)
    
    def _build_in_clause_expression(
        self,
        feature_ids: list,
        primary_key: str,
        max_ids_per_clause: int = 10000,
        is_numeric: bool = None,
        layer: QgsVectorLayer = None
    ) -> str:
        """
        Build optimized IN clause expression from feature IDs.
        
        For very large ID lists, uses multiple IN clauses combined with OR
        to avoid PostgreSQL query length limits.
        
        CRITICAL FIX v2.8.5: Now supports UUID/text primary keys with proper quoting.
        
        Args:
            feature_ids: List of feature IDs to include
            primary_key: Primary key column name
            max_ids_per_clause: Maximum IDs per IN clause
            is_numeric: Whether PK is numeric (optional, auto-detected if None)
            layer: QgsVectorLayer to check PK type (optional)
        
        Returns:
            SQL expression string
        """
        if not feature_ids:
            # Return impossible condition for empty results
            return f'"{primary_key}" IS NULL AND "{primary_key}" IS NOT NULL'
        
        # Auto-detect PK type if not specified
        if is_numeric is None:
            is_numeric = self._is_pk_numeric(layer, primary_key)
        
        if len(feature_ids) <= max_ids_per_clause:
            # Simple case - single IN clause
            # CRITICAL FIX v2.8.5: Use _format_pk_values_for_sql for proper quoting
            ids_str = self._format_pk_values_for_sql(feature_ids, is_numeric)
            return f'"{primary_key}" IN ({ids_str})'
        
        # Large ID list - chunk into multiple IN clauses
        clauses = []
        for i in range(0, len(feature_ids), max_ids_per_clause):
            chunk = feature_ids[i:i + max_ids_per_clause]
            # CRITICAL FIX v2.8.5: Use _format_pk_values_for_sql for proper quoting
            ids_str = self._format_pk_values_for_sql(chunk, is_numeric)
            clauses.append(f'"{primary_key}" IN ({ids_str})')
        
        # Combine with OR
        return ' OR '.join(f'({clause})' for clause in clauses)
    
    def _get_fast_feature_count(self, layer: QgsVectorLayer, conn) -> int:
        """
        Get fast feature count estimation using PostgreSQL statistics.
        
        This avoids expensive COUNT(*) queries by using pg_stat_user_tables.
        Falls back to layer.featureCount() if statistics unavailable.
        
        Args:
            layer: PostgreSQL layer
            conn: Database connection
            
        Returns:
            Estimated feature count
        """
        cursor = None
        try:
            cursor = conn.cursor()
            source_uri = QgsDataSourceUri(layer.source())
            schema = source_uri.schema() or "public"
            table = source_uri.table()
            
            # Try to get estimated count from PostgreSQL statistics
            # This is MUCH faster than COUNT(*) for large tables
            cursor.execute(f"""
                SELECT n_live_tup 
                FROM pg_stat_user_tables 
                WHERE schemaname = '{schema}' 
                AND tablename = '{table}'
            """)
            
            result = cursor.fetchone()
            cursor.close()
            
            if result and result[0] is not None:
                estimated_count = result[0]
                self.log_debug(f"Using PostgreSQL statistics: ~{estimated_count:,} features")
                return estimated_count
            else:
                # Fallback: use QGIS feature count (slower but accurate)
                self.log_debug("PostgreSQL statistics unavailable, using layer.featureCount()")
                return layer.featureCount()
                
        except Exception as e:
            self.log_debug(f"Error getting fast count: {e}, falling back to featureCount()")
            # CRITICAL FIX v2.5.21: Rollback the aborted transaction before continuing
            # If cursor.execute() fails, the connection is left in an aborted state
            # and all subsequent commands will fail with "current transaction is aborted"
            try:
                conn.rollback()
                self.log_debug("Transaction rolled back after fast count error")
            except Exception as rollback_err:
                self.log_debug(f"Rollback in fast count failed: {rollback_err}")
            finally:
                if cursor:
                    try:
                        cursor.close()
                    except Exception:
                        pass
            return layer.featureCount()
    
    def _apply_direct(self, layer: QgsVectorLayer, expression: str) -> bool:
        """
        Apply filter directly using setSubsetString (for small datasets).
        
        Simpler and faster for small datasets because it:
        - Avoids creating/dropping materialized views
        - Avoids creating spatial indexes
        - Uses PostgreSQL's query optimizer directly
        
        THREAD SAFETY FIX v2.4.0: Uses queue callback to defer setSubsetString()
        to main thread instead of applying directly from background thread.
        
        Args:
            layer: PostgreSQL layer to filter
            expression: PostGIS SQL expression
        
        Returns:
            True if successful (filter queued for application)
        """
        start_time = time.time()
        
        try:
            self.log_debug(f"Applying direct filter to {layer.name()}")
            self.log_debug(f"Expression: {expression[:200]}...")
            
            # THREAD SAFETY FIX: Use queue callback if available (called from background thread)
            # This defers the setSubsetString() call to the main thread in finished()
            queue_callback = self.task_params.get('_subset_queue_callback')
            
            if queue_callback:
                # Queue for main thread application
                queue_callback(layer, expression)
                self.log_debug(f"Filter queued for main thread application")
                result = True  # We assume success, actual application happens in finished()
            else:
                # Fallback: direct application (for testing or non-task contexts)
                # This should NOT happen during normal filtering from QgsTask
                self.log_warning(f"No queue callback - applying directly (may cause thread issues)")
                result = safe_set_subset_string(layer, expression)
            
            elapsed = time.time() - start_time
            
            if result:
                self.log_info(
                    f"✓ Direct filter {'queued' if queue_callback else 'applied'} in {elapsed:.3f}s."
                )
            else:
                self.log_error(f"Failed to apply direct filter to {layer.name()}")
            
            return result
            
        except Exception as e:
            self.log_error(f"Error applying direct filter: {str(e)}")
            return False
    
    def _apply_with_materialized_view(self, layer: QgsVectorLayer, expression: str) -> bool:
        """
        Apply filter using optimized materialized views (for large datasets).
        
        v2.6.1 OPTIMIZATION: Creates lightweight MV with only ID + geometry.
        This dramatically reduces memory usage and speeds up spatial queries:
        - Old approach: SELECT * (all columns) → large MV, slow index creation
        - New approach: SELECT pk, geom → small MV, fast GIST index
        
        For buffered filters, stores pre-computed buffered geometry in MV
        to avoid recomputing ST_Buffer on each query.
        
        Performance improvements:
        - 3-5x smaller materialized views
        - 2-3x faster index creation
        - 40-60% faster spatial queries (smaller index pages in memory)
        
        Args:
            layer: PostgreSQL layer to filter
            expression: PostGIS SQL expression
        
        Returns:
            True if successful
        """
        start_time = time.time()
        
        try:
            # Get database connection
            conn, source_uri = get_datasource_connexion_from_layer(layer)
            if not conn:
                self.log_error("Cannot get PostgreSQL connection, falling back to direct method")
                return self._apply_direct(layer, expression)
            
            cursor = conn.cursor()
            
            # Get layer properties
            schema = source_uri.schema() or "public"
            table = source_uri.table()
            geom_column = source_uri.geometryColumn()
            key_column = source_uri.keyColumn()
            
            if not key_column:
                # Try to find primary key
                from ..appUtils import get_primary_key_name
                key_column = get_primary_key_name(layer)
            
            # CRITICAL: ctid cannot be used in materialized views
            if not key_column or key_column == 'ctid':
                if key_column == 'ctid':
                    self.log_warning(
                        f"Layer '{layer.name()}' uses 'ctid' (no PRIMARY KEY). "
                        f"Materialized views disabled, using direct filtering."
                    )
                else:
                    self.log_warning("Cannot determine primary key, falling back to direct method")
                conn.close()
                return self._apply_direct(layer, expression)
            
            # Generate unique MV name
            mv_name = f"{self.mv_prefix}{uuid.uuid4().hex[:8]}"
            full_mv_name = f'"{schema}"."{mv_name}"'
            
            self.log_debug(f"Creating optimized materialized view: {full_mv_name}")
            
            # Get estimated row count for optimization decisions
            feature_count = self._get_fast_feature_count(layer, conn)
            
            # v2.6.1: Detect if this is a buffered geometric filter
            # Check task_params for buffer information
            filtering_params = self.task_params.get('filtering', {}) if self.task_params else {}
            has_buffer = filtering_params.get('has_buffer', False)
            buffer_value = filtering_params.get('buffer_value', 0)
            if not has_buffer:
                buffer_value = 0
            
            # Build SQL commands
            commands = []
            command_names = []
            
            # 1. Drop existing MV if any
            sql_drop = f'DROP MATERIALIZED VIEW IF EXISTS {full_mv_name} CASCADE;'
            commands.append(sql_drop)
            command_names.append("DROP MV")
            
            # 2. v2.6.1: Create OPTIMIZED MV with only ID + geometry
            # For buffered filters, also store pre-computed buffered geometry
            # v2.9.1: Add bbox column for ultra-fast pre-filtering with && operator
            unlogged_clause = "UNLOGGED" if self.ENABLE_MV_UNLOGGED else ""
            use_bbox = self.ENABLE_BBOX_COLUMN and feature_count >= 10000
            
            if has_buffer and buffer_value > 0:
                # Store both original geometry AND buffered geometry
                # This allows fast spatial queries without recomputing buffer each time
                endcap_style = self._get_buffer_endcap_style()
                if use_bbox:
                    sql_create = f'''
                        CREATE {unlogged_clause} MATERIALIZED VIEW {full_mv_name} AS
                        SELECT 
                            "{key_column}" as pk,
                            "{geom_column}" as geom,
                            ST_Buffer("{geom_column}", {buffer_value}, '{endcap_style}') as geom_buffered,
                            ST_Envelope(ST_Buffer("{geom_column}", {buffer_value}, '{endcap_style}')) as bbox
                        FROM "{schema}"."{table}"
                        WHERE {expression}
                        WITH DATA;
                    '''
                    self.log_info(f"📦 Creating optimized MV with buffered geometry + bbox (buffer={buffer_value}m)")
                else:
                    sql_create = f'''
                        CREATE {unlogged_clause} MATERIALIZED VIEW {full_mv_name} AS
                        SELECT 
                            "{key_column}" as pk,
                            "{geom_column}" as geom,
                            ST_Buffer("{geom_column}", {buffer_value}, '{endcap_style}') as geom_buffered
                        FROM "{schema}"."{table}"
                        WHERE {expression}
                        WITH DATA;
                    '''
                    self.log_info(f"📦 Creating optimized MV with buffered geometry (buffer={buffer_value}m)")
            else:
                # Standard case: only ID + geometry
                if use_bbox:
                    sql_create = f'''
                        CREATE {unlogged_clause} MATERIALIZED VIEW {full_mv_name} AS
                        SELECT 
                            "{key_column}" as pk,
                            "{geom_column}" as geom,
                            ST_Envelope("{geom_column}") as bbox
                        FROM "{schema}"."{table}"
                        WHERE {expression}
                        WITH DATA;
                    '''
                    self.log_info(f"📦 v2.9.1: Creating optimized MV with bbox pre-filter column ({feature_count:,} features)")
                else:
                    sql_create = f'''
                        CREATE {unlogged_clause} MATERIALIZED VIEW {full_mv_name} AS
                        SELECT 
                            "{key_column}" as pk,
                            "{geom_column}" as geom
                        FROM "{schema}"."{table}"
                        WHERE {expression}
                        WITH DATA;
                    '''
                    self.log_info(f"📦 Creating optimized lightweight MV (ID + geometry only)")
            
            commands.append(sql_create)
            command_names.append("CREATE MV (optimized)")
            
            # 3. Create spatial index with FILLFACTOR optimization
            # v2.9.1: Use INCLUDE clause for covering index (PostgreSQL 11+)
            # This avoids table lookup for pk column, improving query performance
            index_name = f"{mv_name}_gist_idx"
            pg_version = self._get_postgresql_version(conn)
            use_include = self.ENABLE_INDEX_INCLUDE and pg_version >= 11
            
            if use_include:
                sql_create_index = (
                    f'CREATE INDEX "{index_name}" ON {full_mv_name} '
                    f'USING GIST ("geom") '
                    f'INCLUDE ("pk") '
                    f'WITH (FILLFACTOR = {self.MV_INDEX_FILLFACTOR});'
                )
                self.log_info(f"  📊 v2.9.1: Using covering index with INCLUDE (pk) for faster lookups")
            else:
                sql_create_index = (
                    f'CREATE INDEX "{index_name}" ON {full_mv_name} '
                    f'USING GIST ("geom") '
                    f'WITH (FILLFACTOR = {self.MV_INDEX_FILLFACTOR});'
                )
            commands.append(sql_create_index)
            command_names.append("CREATE GIST INDEX")
            
            # 3b. If buffered, also create index on buffered geometry
            if has_buffer and buffer_value > 0:
                buffer_index_name = f"{mv_name}_gist_buf_idx"
                if use_include:
                    sql_create_buffer_index = (
                        f'CREATE INDEX "{buffer_index_name}" ON {full_mv_name} '
                        f'USING GIST ("geom_buffered") '
                        f'INCLUDE ("pk") '
                        f'WITH (FILLFACTOR = {self.MV_INDEX_FILLFACTOR});'
                    )
                else:
                    sql_create_buffer_index = (
                        f'CREATE INDEX "{buffer_index_name}" ON {full_mv_name} '
                        f'USING GIST ("geom_buffered") '
                        f'WITH (FILLFACTOR = {self.MV_INDEX_FILLFACTOR});'
                    )
                commands.append(sql_create_buffer_index)
                command_names.append("CREATE BUFFER GIST INDEX")
            
            # 3c. v2.9.1: Create bbox index for ultra-fast pre-filtering
            # The bbox column uses the && operator which is extremely fast with GIST
            if use_bbox:
                bbox_index_name = f"{mv_name}_bbox_idx"
                sql_create_bbox_index = (
                    f'CREATE INDEX "{bbox_index_name}" ON {full_mv_name} '
                    f'USING GIST ("bbox") '
                    f'WITH (FILLFACTOR = {self.MV_INDEX_FILLFACTOR});'
                )
                commands.append(sql_create_bbox_index)
                command_names.append("CREATE BBOX INDEX")
                self.log_info(f"  📦 v2.9.1: Creating bbox index for fast && pre-filtering")
            
            # 4. Create index on primary key for fast lookups
            pk_index_name = f"{mv_name}_pk_idx"
            sql_create_pk_index = f'CREATE INDEX "{pk_index_name}" ON {full_mv_name} ("pk");'
            commands.append(sql_create_pk_index)
            command_names.append("CREATE PK INDEX")
            
            # 5. CLUSTER - optional, can be slow for large datasets
            # v2.9.1: For large datasets, schedule async CLUSTER instead of skipping
            if self.ENABLE_MV_CLUSTER:
                if feature_count < self.ASYNC_CLUSTER_THRESHOLD:
                    # Small dataset: synchronous CLUSTER
                    sql_cluster = f'CLUSTER {full_mv_name} USING "{index_name}";'
                    commands.append(sql_cluster)
                    command_names.append("CLUSTER")
                elif self.ENABLE_ASYNC_CLUSTER and feature_count < self.LARGE_DATASET_THRESHOLD:
                    # Medium dataset: async CLUSTER in background
                    self.log_info(f"⏳ v2.9.1: Scheduling async CLUSTER for {feature_count:,} features")
                    self._schedule_async_cluster(conn, full_mv_name, index_name, schema, mv_name)
                else:
                    self.log_info(f"⚡ Skipping CLUSTER for very large dataset ({feature_count:,} > {self.LARGE_DATASET_THRESHOLD:,} features)")
            
            # 6. ANALYZE for query optimizer
            if self.ENABLE_MV_ANALYZE:
                sql_analyze = f'ANALYZE {full_mv_name};'
                commands.append(sql_analyze)
                command_names.append("ANALYZE")
            
            # 7. v2.9.1: Create extended statistics for better query plans
            if self.ENABLE_EXTENDED_STATS and pg_version >= 10:
                try:
                    stats_name = f"{mv_name}_stats"
                    # Extended statistics on pk + geom correlation helps optimizer
                    sql_stats = f'CREATE STATISTICS "{stats_name}" ON "pk", "geom" FROM {full_mv_name};'
                    commands.append(sql_stats)
                    command_names.append("CREATE EXTENDED STATS")
                    self.log_debug(f"  📊 v2.9.1: Adding extended statistics for better query plans")
                except Exception:
                    pass  # Extended stats not critical
            
            # Execute commands with timing
            # CRITICAL FIX v2.5.21: Add per-command error handling
            # If any command fails (especially CREATE MV), we need to:
            # 1. Rollback the transaction to clear the aborted state
            # 2. For critical commands (CREATE MV), abort entirely
            # 3. For non-critical commands (INDEX, ANALYZE), log and continue
            total_steps = len(commands)
            step_times = []
            critical_commands = ["CREATE MV (optimized)", "DROP MV"]  # Commands that must succeed
            
            for i, (cmd, cmd_name) in enumerate(zip(commands, command_names)):
                step_start = time.time()
                self.log_debug(f"Executing {cmd_name} ({i+1}/{total_steps})")
                
                try:
                    cursor.execute(cmd)
                    conn.commit()
                    step_time = time.time() - step_start
                    step_times.append((cmd_name, step_time))
                    
                    # Log slow operations
                    if step_time > 1.0:
                        self.log_debug(f"  ⏱️ {cmd_name} took {step_time:.2f}s")
                        
                except Exception as cmd_error:
                    error_str = str(cmd_error).lower()
                    step_time = time.time() - step_start
                    
                    # Rollback to clear the aborted transaction state
                    try:
                        conn.rollback()
                        self.log_debug(f"  Transaction rolled back after {cmd_name} failure")
                    except Exception as rollback_err:
                        self.log_debug(f"  Rollback failed: {rollback_err}")
                    
                    # Check if this is a critical command (must succeed)
                    is_critical = cmd_name in critical_commands
                    
                    if is_critical:
                        # Critical command failed - abort MV creation
                        self.log_error(f"Critical command {cmd_name} failed: {cmd_error}")
                        raise cmd_error  # Re-raise to trigger fallback
                    else:
                        # Non-critical command failed - log and continue
                        # INDEX and ANALYZE failures don't prevent filtering from working
                        self.log_warning(f"  ⚠️ Non-critical command {cmd_name} failed: {cmd_error}")
                        self.log_warning(f"  → Continuing without {cmd_name} (filter will still work)")
                        step_times.append((f"{cmd_name} (FAILED)", step_time))
                        continue
            
            # v2.6.1: Update layer to use materialized view with optimized column reference
            layer_subset = f'"{key_column}" IN (SELECT "pk" FROM {full_mv_name})'
            self.log_debug(f"Setting subset string: {layer_subset[:200]}...")
            
            # THREAD SAFETY FIX: Use queue callback if available
            queue_callback = self.task_params.get('_subset_queue_callback')
            
            if queue_callback:
                queue_callback(layer, layer_subset)
                self.log_debug(f"MV filter queued for main thread application")
                result = True
            else:
                self.log_warning(f"No queue callback - applying directly (may cause thread issues)")
                result = safe_set_subset_string(layer, layer_subset)
            
            # Register MV for cleanup tracking (v2.4.0)
            if MV_REGISTRY_AVAILABLE and result:
                try:
                    registry = get_mv_registry()
                    registry.register(
                        mv_name=mv_name,
                        schema=schema,
                        layer_id=layer.id(),
                        layer_name=layer.name(),
                        feature_count=feature_count
                    )
                    self.log_debug(f"📝 MV registered for cleanup: {mv_name}")
                except Exception as reg_error:
                    self.log_warning(f"Failed to register MV for cleanup: {reg_error}")
            
            cursor.close()
            conn.close()
            
            elapsed = time.time() - start_time
            
            if result:
                new_feature_count = layer.featureCount()
                self.log_info(
                    f"✓ Optimized MV created and filter applied in {elapsed:.2f}s. "
                    f"{new_feature_count} features match."
                )
                
                # Log size benefit for debugging
                if has_buffer and buffer_value > 0:
                    self.log_info(f"  → MV contains: pk + geom + geom_buffered (pre-computed)")
                else:
                    self.log_info(f"  → MV contains: pk + geom only (3-5x smaller than SELECT *)")
                
                # Log performance breakdown for debugging
                if elapsed > 2.0:
                    breakdown = ", ".join([f"{name}: {t:.2f}s" for name, t in step_times])
                    self.log_debug(f"  Performance breakdown: {breakdown}")
            else:
                self.log_error(f"Failed to set subset string on layer")
            
            return result
            
        except Exception as e:
            error_str = str(e).lower()
            
            # CRITICAL FIX v2.5.18: Detect statement timeout and other cancellation errors
            # PostgreSQL raises specific errors when statement_timeout is reached:
            # - "canceling statement due to statement timeout"
            # - "QueryCanceledError"
            is_timeout = (
                'timeout' in error_str or 
                'canceling statement' in error_str or
                'querycanceled' in error_str.replace(' ', '')
            )
            
            if is_timeout:
                self.log_warning(f"⏱️ PostgreSQL query TIMEOUT for {layer.name()}")
                self.log_warning(f"  → Query was too complex or dataset too large for SQL-based filtering")
                self.log_warning(f"  → This typically happens with EXISTS subqueries on large source datasets")
                self.log_warning(f"  → Falling back to OGR backend (QGIS processing)")
                
                # Log to QGIS Message Panel for user visibility
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"⏱️ PostgreSQL timeout for {layer.name()} - switching to OGR backend",
                    "FilterMate", Qgis.Warning
                )
                
                # Store this layer as requiring OGR fallback for future operations
                if 'forced_backends' not in self.task_params:
                    self.task_params['forced_backends'] = {}
                self.task_params['forced_backends'][layer.id()] = 'ogr'
                
                # Return False to trigger OGR fallback in execute_geometric_filtering
                return False
            else:
                self.log_error(f"Error creating materialized view: {str(e)}")
                import traceback
                self.log_debug(f"Traceback: {traceback.format_exc()}")
            
            # Cleanup and fallback
            # CRITICAL FIX v2.5.11: Rollback the aborted transaction before closing
            # This prevents "current transaction is aborted" errors on subsequent operations
            try:
                if 'conn' in locals() and conn:
                    try:
                        conn.rollback()
                        self.log_debug("Transaction rolled back after error")
                    except Exception as rollback_err:
                        self.log_debug(f"Rollback failed (connection may be closed): {rollback_err}")
                if 'cursor' in locals() and cursor:
                    cursor.close()
                if 'conn' in locals() and conn:
                    conn.close()
            except (OSError, AttributeError, Exception) as cleanup_err:
                self.log_debug(f"Cleanup error (non-fatal): {cleanup_err}")
            
            self.log_info("Falling back to direct filter method")
            return self._apply_direct(layer, expression)
    
    def create_source_selection_mv(
        self, 
        layer: QgsVectorLayer, 
        fids: list, 
        pk_field: str,
        geom_field: str
    ) -> Optional[str]:
        """
        Create a temporary materialized view for selected source features.
        
        This optimization is used when the number of selected source features exceeds
        the source_mv_fid_threshold. Instead of including thousands of FIDs in an 
        inline IN(...) clause (which is slow for EXISTS subqueries), we create a 
        small indexed MV and use it in the EXISTS subquery.
        
        Performance benefits:
        - EXISTS subquery uses spatial index on MV instead of scanning IN(...) list
        - PostgreSQL can use hash/merge joins between target and source MV
        - Dramatically faster for large source selections (>500 features)
        
        Args:
            layer: Source QgsVectorLayer (PostgreSQL)
            fids: List of feature IDs to include in MV
            pk_field: Primary key field name
            geom_field: Geometry field name
            
        Returns:
            Full MV reference string (e.g., '"filter_mate_temp"."mv_src_sel_abc123"')
            or None if creation failed
            
        Note:
            The MV is cleaned up automatically by cleanup_materialized_views()
        """
        import uuid
        import time
        
        try:
            conn, source_uri = get_datasource_connexion_from_layer(layer)
            if not conn:
                self.log_warning("Cannot get PostgreSQL connection for source selection MV")
                return None
            
            cursor = conn.cursor()
            source_schema = source_uri.schema() or "public"
            source_table = source_uri.table()
            
            # Generate unique MV name with prefix for identification
            mv_suffix = uuid.uuid4().hex[:8]
            mv_name = f"{self.mv_prefix}src_sel_{mv_suffix}"
            
            # v2.8.8: Use filtermate_temp schema, with fallback to 'public' if creation fails
            mv_schema = self._ensure_mv_schema_exists(conn, DEFAULT_TEMP_SCHEMA)
            full_mv_name = f'"{mv_schema}"."{mv_name}"'
            
            self.log_info(f"🗄️ v2.8.0: Creating source selection MV for {len(fids)} features")
            self.log_info(f"   MV: {full_mv_name}")
            
            # Build FIDs string for IN clause
            # CRITICAL FIX v2.8.5: Use _format_pk_values_for_sql to properly quote UUID/text PKs
            fids_str = self._format_pk_values_for_sql(fids, layer=layer, pk_field=pk_field)
            
            # Drop existing MV if any (unlikely but safe)
            sql_drop = f'DROP MATERIALIZED VIEW IF EXISTS {full_mv_name} CASCADE;'
            
            # Create lightweight MV with only pk + geometry
            # UNLOGGED for better performance (data is transient anyway)
            sql_create = f'''
                CREATE MATERIALIZED VIEW {full_mv_name} AS
                SELECT 
                    "{pk_field}" as pk,
                    "{geom_field}" as geom
                FROM "{source_schema}"."{source_table}"
                WHERE "{pk_field}" IN ({fids_str})
                WITH DATA;
            '''
            
            # Create spatial index for fast spatial joins
            index_name = f"{mv_name}_gist_idx"
            sql_index = f'''
                CREATE INDEX "{index_name}" ON {full_mv_name} 
                USING GIST ("geom");
            '''
            
            # Execute commands
            start_time = time.time()
            
            cursor.execute(sql_drop)
            conn.commit()
            
            cursor.execute(sql_create)
            conn.commit()
            
            cursor.execute(sql_index)
            conn.commit()
            
            # ANALYZE for query optimizer
            cursor.execute(f'ANALYZE {full_mv_name};')
            conn.commit()
            
            elapsed = time.time() - start_time
            
            cursor.close()
            conn.close()
            
            self.log_info(f"   ✓ MV created and indexed in {elapsed:.2f}s")
            
            return full_mv_name
            
        except Exception as e:
            self.log_error(f"Error creating source selection MV: {str(e)}")
            import traceback
            self.log_debug(f"Traceback: {traceback.format_exc()}")
            
            # Cleanup on error
            try:
                if 'conn' in locals() and conn:
                    conn.rollback()
                    conn.close()
            except Exception:
                pass
            
            return None
    
    def cleanup_materialized_views(self, layer: QgsVectorLayer) -> bool:
        """
        Cleanup materialized views created by this backend.
        
        Args:
            layer: PostgreSQL layer
        
        Returns:
            True if cleanup successful
        """
        try:
            conn, source_uri = get_datasource_connexion_from_layer(layer)
            if not conn:
                self.log_warning("Cannot get PostgreSQL connection for cleanup")
                return False
            
            cursor = conn.cursor()
            schema = source_uri.schema() or "public"
            
            # Find all FilterMate materialized views
            cursor.execute(f"""
                SELECT matviewname FROM pg_matviews 
                WHERE schemaname = '{schema}' 
                AND matviewname LIKE '{self.mv_prefix}%'
            """)
            
            views = cursor.fetchall()
            
            for (view_name,) in views:
                try:
                    cursor.execute(f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."{view_name}" CASCADE;')
                    conn.commit()
                    self.log_debug(f"Dropped materialized view: {view_name}")
                except Exception as e:
                    self.log_warning(f"Error dropping view {view_name}: {e}")
            
            cursor.close()
            conn.close()
            
            if views:
                self.log_info(f"Cleaned up {len(views)} materialized view(s)")
            
            return True
            
        except Exception as e:
            self.log_error(f"Error during cleanup: {str(e)}")
            return False
    
    def apply_optimized_buffer_workflow(
        self,
        source_layer: QgsVectorLayer,
        target_layer: QgsVectorLayer,
        buffer_distance: float,
        source_fids: Optional[list] = None,
        source_filter: Optional[str] = None,
        spatial_predicate: str = "ST_Intersects",
        previous_mv: Optional[str] = None
    ) -> Optional[str]:
        """
        Apply optimized buffer workflow using buffer optimizer.
        
        v2.9.0: This method uses pre-computed buffer geometries and
        simplification to dramatically improve performance for large
        buffer + intersection workflows.
        
        Optimizations applied:
        1. ST_SimplifyPreserveTopology before ST_Buffer (10-50x faster buffer)
        2. Pre-computed buffer stored in MV (avoids recalculating per comparison)
        3. Bbox pre-filter in EXISTS (fast spatial index check)
        4. Chained MV for multi-step workflows
        
        Args:
            source_layer: Source PostgreSQL layer (e.g., roads, railways)
            target_layer: Target PostgreSQL layer (e.g., buildings)
            buffer_distance: Buffer distance in layer units
            source_fids: Optional list of source feature IDs
            source_filter: Optional SQL filter for source layer
            spatial_predicate: PostGIS spatial predicate
            previous_mv: Previous step's MV name for chaining
        
        Returns:
            Optimized SQL expression or None if optimization failed
        """
        if not BUFFER_OPTIMIZER_AVAILABLE:
            self.log_info("Buffer optimizer not available, using standard method")
            return None
        
        try:
            # Get connection from source layer
            conn, source_uri = get_datasource_connexion_from_layer(source_layer)
            if not conn:
                self.log_warning("Cannot get PostgreSQL connection for buffer optimizer")
                return None
            
            # Build layer properties dicts
            source_props = {
                'layer_schema': source_uri.schema() or 'public',
                'layer_table_name': source_uri.table(),
                'layer_geometry_field': source_uri.geometryColumn() or 'geom',
                'layer_pk': source_uri.keyColumn() or 'fid',
                'layer_srid': source_layer.crs().postgisSrid() if source_layer.crs() else 2154
            }
            
            target_uri = QgsDataSourceUri(target_layer.dataProvider().dataSourceUri())
            target_props = {
                'layer_schema': target_uri.schema() or 'public',
                'layer_table_name': target_uri.table(),
                'layer_geometry_field': target_uri.geometryColumn() or 'geom',
                'layer_pk': target_uri.keyColumn() or 'fid'
            }
            
            # Load optimization config from ENV_VARS
            config = BufferOptimizationConfig()
            try:
                from ...config.config import ENV_VARS
                auto_opt = ENV_VARS.get('CONFIG_DATA', {}).get('APP', {}).get('OPTIONS', {}).get('AUTO_OPTIMIZATION', {})
                if auto_opt:
                    def get_val(entry, default):
                        if isinstance(entry, dict):
                            return entry.get('value', default)
                        return entry
                    
                    config.simplify_before_buffer = get_val(
                        auto_opt.get('auto_simplify_before_buffer', {}), True
                    )
                    config.simplify_tolerance_factor = get_val(
                        auto_opt.get('buffer_simplify_before_tolerance', {}), 0.1
                    )
            except Exception:
                pass  # Use defaults
            
            # Create optimizer
            optimizer = get_buffer_optimizer(conn, config)
            if not optimizer:
                conn.close()
                return None
            
            # Run optimization
            result = optimizer.optimize_multi_step_buffer_workflow(
                source_layer_props=source_props,
                target_layer_props=target_props,
                buffer_distance=buffer_distance,
                source_filter=source_filter,
                source_fids=source_fids,
                spatial_predicate=spatial_predicate,
                previous_mv=previous_mv
            )
            
            conn.close()
            
            if result.success:
                self.log_info(f"🚀 Buffer Optimizer: {result.estimated_speedup:.1f}x expected speedup")
                for hint in result.hints:
                    self.log_info(f"   {hint}")
                
                # Store buffer MV name for cleanup
                if result.buffer_mv_name and hasattr(self, 'task_params') and self.task_params:
                    buffer_mvs = self.task_params.setdefault('_buffer_mvs', [])
                    buffer_mvs.append(result.buffer_mv_name)
                
                return result.optimized_sql
            else:
                self.log_info("Buffer optimization not applicable, using standard method")
                return None
                
        except Exception as e:
            self.log_error(f"Error in buffer optimizer: {e}")
            import traceback
            self.log_debug(traceback.format_exc())
            return None
    
    def get_backend_name(self) -> str:
        """Get backend name"""
        return "PostgreSQL"

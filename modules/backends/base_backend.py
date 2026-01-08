# -*- coding: utf-8 -*-
"""
Base Backend Interface

Abstract base class defining the interface for geometric filtering backends.
All backend implementations must inherit from this class and implement its abstract methods.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from qgis.core import QgsVectorLayer


class GeometricFilterBackend(ABC):
    """
    Abstract base class for geometric filtering backends.
    
    Each backend is responsible for:
    1. Building filter expressions appropriate for its data source
    2. Applying filters to layers
    3. Verifying compatibility with specific layer types
    """
    
    def __init__(self, task_params: Dict):
        """
        Initialize the backend with task parameters.
        
        Args:
            task_params: Dictionary containing all task configuration parameters
        """
        self.task_params = task_params
        self.logger = None  # Will be set by subclasses
    
    @abstractmethod
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
        Build a filter expression for this backend.
        
        Args:
            layer_props: Layer properties dictionary containing layer metadata
            predicates: Dictionary of spatial predicates to apply
            source_geom: Source geometry for spatial filtering (optional)
            buffer_value: Buffer distance value (optional)
            source_filter: Source layer filter expression (optional, for EXISTS subqueries)
            buffer_expression: Expression for dynamic buffer (optional)
            use_centroids: If True, use centroids instead of full geometries for distant layers (optional)
            **kwargs: Additional backend-specific parameters (e.g., source_wkt, source_srid)
        
        Returns:
            Filter expression as a string suitable for this backend
        
        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement build_expression()")
    
    @abstractmethod
    def apply_filter(
        self, 
        layer: QgsVectorLayer, 
        expression: str,
        old_subset: Optional[str] = None,
        combine_operator: Optional[str] = None
    ) -> bool:
        """
        Apply the filter expression to the layer.
        
        Args:
            layer: QGIS vector layer to filter
            expression: Filter expression to apply
            old_subset: Existing subset string (optional)
            combine_operator: Operator to combine with existing filter (AND/OR)
        
        Returns:
            True if filter was applied successfully, False otherwise
        
        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement apply_filter()")
    
    @abstractmethod
    def supports_layer(self, layer: QgsVectorLayer) -> bool:
        """
        Check if this backend supports the given layer.
        
        Args:
            layer: QGIS vector layer to check
        
        Returns:
            True if this backend can handle the layer, False otherwise
        
        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement supports_layer()")
    
    def get_backend_name(self) -> str:
        """
        Get the human-readable name of this backend.
        
        Returns:
            Backend name as string
        """
        return self.__class__.__name__
    
    def log_info(self, message: str):
        """Helper method for logging info messages"""
        if self.logger:
            self.logger.info(f"[{self.get_backend_name()}] {message}")
    
    def log_warning(self, message: str):
        """Helper method for logging warning messages"""
        if self.logger:
            self.logger.warning(f"[{self.get_backend_name()}] {message}")
    
    def log_error(self, message: str):
        """Helper method for logging error messages"""
        if self.logger:
            self.logger.error(f"[{self.get_backend_name()}] {message}")
    
    def log_debug(self, message: str):
        """Helper method for logging debug messages"""
        if self.logger:
            self.logger.debug(f"[{self.get_backend_name()}] {message}")

    # =========================================================================
    # Shared Filter Combination Methods (v2.8.6 - harmonization)
    # =========================================================================
    
    def _should_clear_old_subset(self, old_subset: Optional[str]) -> bool:
        """
        Check if old_subset contains patterns that indicate it should be cleared.
        
        v2.8.6: Extracted to base class for harmonization across all backends.
        
        This prevents combining with corrupted or incompatible previous filters.
        
        Invalid patterns:
        1. __source alias (PostgreSQL EXISTS subquery internal alias)
        2. EXISTS subquery (would create nested subqueries)
        3. Spatial predicates (likely from previous geometric filter)
        
        Args:
            old_subset: The existing subset string to check
            
        Returns:
            True if old_subset should be cleared (not combined with)
        """
        if not old_subset:
            return False
        
        old_subset_upper = old_subset.upper()
        
        # Pattern 1: __source alias (only valid inside PostgreSQL EXISTS subqueries)
        has_source_alias = '__source' in old_subset.lower()
        
        # Pattern 2: EXISTS subquery (avoid nested EXISTS)
        has_exists = 'EXISTS (' in old_subset_upper or 'EXISTS(' in old_subset_upper
        
        # Pattern 3: Spatial predicates from various backends
        # These indicate a previous geometric filter that should be replaced
        spatial_predicates = [
            # PostGIS/Spatialite predicates
            'ST_INTERSECTS', 'ST_CONTAINS', 'ST_WITHIN', 'ST_TOUCHES',
            'ST_OVERLAPS', 'ST_CROSSES', 'ST_DISJOINT', 'ST_EQUALS',
            'ST_DWITHIN', 'ST_COVERS', 'ST_COVEREDBY',
            # Spatialite-specific (without ST_ prefix)
            'INTERSECTS', 'CONTAINS', 'WITHIN'
        ]
        has_spatial_predicate = any(pred in old_subset_upper for pred in spatial_predicates)
        
        should_clear = has_source_alias or has_exists or has_spatial_predicate
        
        if should_clear:
            reason = []
            if has_source_alias:
                reason.append("contains __source alias")
            if has_exists:
                reason.append("contains EXISTS subquery")
            if has_spatial_predicate:
                reason.append("contains spatial predicate")
            
            self.log_warning(f"⚠️ Invalid old_subset detected - {', '.join(reason)}")
            self.log_debug(f"  → Subset: '{old_subset[:100]}...'")
            self.log_info(f"  → Will replace instead of combine")
        
        return should_clear

    def _is_fid_only_filter(self, subset: Optional[str]) -> bool:
        """
        Check if a subset string is a FID-only filter from previous multi-step.
        
        v2.8.6: Extracted to base class for harmonization.
        
        FID filters from previous steps should be combined with AND,
        not replaced, to maintain multi-step filter chain.
        
        Matches patterns like:
        - fid IN (1, 2, 3)
        - "fid" IN (1, 2, 3)
        - fid = 123
        - fid BETWEEN 1 AND 100
        
        Args:
            subset: Subset string to check
            
        Returns:
            True if subset is a FID-only filter
        """
        if not subset:
            return False
        
        import re
        return bool(re.match(
            r'^\s*\(?\s*(["\']?)fid\1\s+(IN\s*\(|=\s*-?\d+|BETWEEN\s+)',
            subset,
            re.IGNORECASE
        ))

    # =========================================================================
    # Shared Buffer/Geometry Methods (v2.8.6 - extracted from backends)
    # =========================================================================
    
    def _get_buffer_endcap_style(self) -> str:
        """
        Get the buffer endcap style from task_params.
        
        Supports PostGIS/Spatialite ST_Buffer 'endcap' parameter:
        - 'round' (default)
        - 'flat' 
        - 'square'
        
        Returns:
            Endcap style string for SQL buffer functions
        """
        if not self.task_params:
            return 'round'
        
        filtering_params = self.task_params.get("filtering", {})
        if not filtering_params.get("has_buffer_type", False):
            return 'round'
        
        buffer_type_str = filtering_params.get("buffer_type", "Round")
        
        # Map FilterMate buffer types to SQL endcap styles
        buffer_type_mapping = {
            "Round": "round",
            "Flat": "flat", 
            "Square": "square"
        }
        
        endcap_style = buffer_type_mapping.get(buffer_type_str, "round")
        self.log_debug(f"Using buffer endcap style: {endcap_style}")
        return endcap_style
    
    def _get_buffer_segments(self) -> int:
        """
        Get the buffer segments (quad_segs) from task_params.
        
        Controls precision for curved buffer edges:
        - Higher value = smoother curves (more segments per quarter circle)
        - Lower value = faster but rougher curves
        - Default: 5 (if not using buffer_type options)
        
        Returns:
            Number of segments per quarter circle
        """
        if not self.task_params:
            return 5
        
        filtering_params = self.task_params.get("filtering", {})
        if not filtering_params.get("has_buffer_type", False):
            return 5
        
        segments = filtering_params.get("buffer_segments", 5)
        self.log_debug(f"Using buffer segments (quad_segs): {segments}")
        return int(segments)
    
    def _get_simplify_tolerance(self) -> float:
        """
        Get the geometry simplification tolerance from task_params.
        
        When simplify_tolerance > 0, geometries are simplified using
        SimplifyPreserveTopology before applying buffer. This reduces
        vertex count and improves performance for complex geometries.
        
        v2.9.2: Added adaptive tolerance calculation based on buffer distance.
        When no explicit tolerance is set but auto-simplification is enabled,
        calculates optimal tolerance as a fraction of buffer distance.
        
        Notes:
        - Preserves topology (no self-intersections)
        - Tolerance in same units as geometry (meters for projected CRS)
        - Value of 0 means no simplification
        - Adaptive tolerance = buffer_value * 0.1 (clamped to [0.5, 10.0] meters)
        
        Returns:
            Simplification tolerance (0 = disabled)
        """
        if not self.task_params:
            return 0.0
        
        filtering_params = self.task_params.get("filtering", {})
        
        # Check for explicit simplify tolerance from UI
        if filtering_params.get("has_simplify_tolerance", False):
            tolerance = filtering_params.get("simplify_tolerance", 0.0)
            if tolerance and tolerance > 0:
                self.log_debug(f"Using explicit simplification tolerance: {tolerance}")
                return float(tolerance)
        
        # v2.9.2: Adaptive tolerance based on buffer value
        # Only apply if auto_simplify_before_buffer is enabled in config
        has_buffer = filtering_params.get("has_buffer_value", False)
        buffer_value = filtering_params.get("buffer_value", 0.0)
        
        if has_buffer and buffer_value != 0:
            # Check if auto-simplification is enabled in config
            try:
                from ...config.config import ENV_VARS
                config_data = ENV_VARS.get('CONFIG_DATA', {})
                auto_opt = config_data.get('APP', {}).get('OPTIONS', {}).get('AUTO_OPTIMIZATION', {})
                
                # Extract value from nested dict if present
                def get_val(entry, default):
                    if isinstance(entry, dict):
                        return entry.get('value', default)
                    return entry if entry is not None else default
                
                auto_simplify_enabled = get_val(auto_opt.get('auto_simplify_before_buffer', {}), True)
                tolerance_factor = get_val(auto_opt.get('buffer_simplify_before_tolerance', {}), 0.1)
                
                if auto_simplify_enabled:
                    # Calculate adaptive tolerance based on buffer distance
                    abs_buffer = abs(buffer_value)
                    adaptive_tolerance = abs_buffer * tolerance_factor
                    
                    # Clamp to reasonable range [0.5, 10.0] meters
                    MIN_TOLERANCE = 0.5
                    MAX_TOLERANCE = 10.0
                    adaptive_tolerance = max(MIN_TOLERANCE, min(adaptive_tolerance, MAX_TOLERANCE))
                    
                    self.log_debug(f"Using adaptive simplification tolerance: {adaptive_tolerance:.2f}m "
                                   f"(buffer={buffer_value}m, factor={tolerance_factor})")
                    return adaptive_tolerance
                    
            except (ImportError, AttributeError, KeyError) as e:
                self.log_debug(f"Could not load auto-simplify config: {e}")
        
        return 0.0

    def _get_dialect_functions(self, dialect: str) -> dict:
        """
        Get SQL function names and syntax for a specific dialect.

        FIX v3.0.12: Unified function mapping for PostgreSQL and Spatialite backends
        to eliminate 80% code duplication in buffer expression building.

        Args:
            dialect: SQL dialect ('postgresql' or 'spatialite')

        Returns:
            Dictionary with dialect-specific function names and helpers:
            - simplify: Function name for SimplifyPreserveTopology
            - make_valid: Function name for MakeValid
            - is_empty: Function name for IsEmpty check
            - is_empty_check: Lambda to generate empty check condition

        Raises:
            ValueError: If dialect is not supported
        """
        if dialect == 'postgresql':
            return {
                'simplify': 'ST_SimplifyPreserveTopology',
                'make_valid': 'ST_MakeValid',
                'is_empty': 'ST_IsEmpty',
                'is_empty_check': lambda expr: f"ST_IsEmpty({expr})"
            }
        elif dialect == 'spatialite':
            return {
                'simplify': 'SimplifyPreserveTopology',
                'make_valid': 'MakeValid',
                'is_empty': 'ST_IsEmpty',
                'is_empty_check': lambda expr: f"ST_IsEmpty({expr}) = 1"
            }
        else:
            raise ValueError(f"Unsupported SQL dialect: {dialect}. Must be 'postgresql' or 'spatialite'.")

    def _build_buffer_expression(
        self,
        geom_expr: str,
        buffer_value: float,
        dialect: str = 'postgresql'
    ) -> str:
        """
        Build ST_Buffer expression with endcap style, simplification, and validation.

        FIX v3.0.12: Unified buffer expression builder for PostgreSQL and Spatialite backends.
        Eliminates 80% code duplication by providing single source of truth for buffer logic.

        Supports both positive buffers (expansion) and negative buffers (erosion/shrinking).
        Negative buffers only work on polygon geometries - they shrink the polygon inward.

        Features:
        - Optional geometry simplification before buffer (for performance)
        - Configurable endcap style (round/flat/square) and segments
        - Negative buffer validation and empty geometry handling
        - Dialect-specific function names (ST_ prefix differences)

        Args:
            geom_expr: Geometry expression to buffer (e.g., "geom" or "ST_Transform(geom, 3857)")
            buffer_value: Buffer distance (positive=expand, negative=shrink/erode)
            dialect: SQL dialect ('postgresql' or 'spatialite'), default 'postgresql'

        Returns:
            Complete buffer expression with style parameters and validation

        Examples:
            PostgreSQL (positive buffer):
                ST_Buffer(ST_SimplifyPreserveTopology(geom, 2.0), 100, 'quad_segs=5 endcap=round')

            PostgreSQL (negative buffer):
                CASE WHEN ST_IsEmpty(ST_MakeValid(ST_Buffer(geom, -10, 'quad_segs=5')))
                     THEN NULL
                     ELSE ST_MakeValid(ST_Buffer(geom, -10, 'quad_segs=5')) END

            Spatialite (negative buffer):
                CASE WHEN ST_IsEmpty(MakeValid(ST_Buffer(geom, -10, 'quad_segs=5'))) = 1
                     THEN NULL
                     ELSE MakeValid(ST_Buffer(geom, -10, 'quad_segs=5')) END

        Note:
            - Negative buffer on a polygon shrinks it inward
            - Negative buffer on a point or line returns empty geometry
            - Very large negative buffers may collapse the polygon entirely
            - Negative buffers are wrapped in MakeValid() to prevent invalid geometries
            - Returns NULL if buffer produces empty geometry (proper SQL handling)
            - Simplification uses SimplifyPreserveTopology to maintain topology
        """
        # Get buffer configuration parameters
        endcap_style = self._get_buffer_endcap_style()
        quad_segs = self._get_buffer_segments()
        simplify_tolerance = self._get_simplify_tolerance()

        # Get dialect-specific function names
        funcs = self._get_dialect_functions(dialect)

        # Log negative buffer usage for visibility
        if buffer_value < 0:
            self.log_debug(f"📐 Using negative buffer (erosion): {buffer_value}m")

        # Apply geometry simplification before buffer if tolerance is set
        # SimplifyPreserveTopology maintains valid topology (no self-intersections)
        working_geom = geom_expr
        if simplify_tolerance > 0:
            working_geom = f"{funcs['simplify']}({geom_expr}, {simplify_tolerance})"
            self.log_info(f"  📐 Applying {funcs['simplify']}({simplify_tolerance}m) before buffer")

        # Build base buffer expression with quad_segs and endcap style
        # ST_Buffer syntax: ST_Buffer(geom, distance, 'quad_segs=N endcap=style')
        style_params = f"quad_segs={quad_segs}"
        if endcap_style != 'round':
            style_params += f" endcap={endcap_style}"

        buffer_expr = f"ST_Buffer({working_geom}, {buffer_value}, '{style_params}')"
        self.log_debug(f"Buffer expression: {buffer_expr}")

        # CRITICAL FIX: Wrap negative buffers in MakeValid() + empty check
        # Negative buffers (erosion/shrinking) can produce invalid or empty geometries,
        # especially on complex polygons or when buffer is too large.
        # MakeValid() ensures the result is always geometrically valid.
        # Empty check detects ALL empty geometry types (POLYGON EMPTY, MULTIPOLYGON EMPTY, etc.)
        if buffer_value < 0:
            self.log_info(f"  🛡️ Wrapping negative buffer in {funcs['make_valid']}() + {funcs['is_empty']} check")
            # Use CASE WHEN to return NULL if buffer produces empty geometry
            # This ensures empty results from negative buffers don't match spatial predicates
            validated_expr = f"{funcs['make_valid']}({buffer_expr})"
            empty_check = funcs['is_empty_check'](validated_expr)
            return f"CASE WHEN {empty_check} THEN NULL ELSE {validated_expr} END"
        else:
            return buffer_expr

    def _wrap_with_geographic_transform(
        self,
        geom_expr: str,
        source_srid: int,
        target_srid: int,
        buffer_value: float,
        dialect: str = 'postgresql'
    ) -> tuple:
        """
        Wrap geometry expression with EPSG:3857 transformation for geographic CRS buffering.

        FIX v3.0.12: Unified geographic CRS transformation logic for PostgreSQL and Spatialite.
        Eliminates 70% code duplication in CRS handling by providing single transformation strategy.

        Geographic CRS (like EPSG:4326) use degrees, making metric buffers problematic.
        This method transforms to Web Mercator (EPSG:3857) for metric buffer operations,
        then transforms back to the target CRS.

        Args:
            geom_expr: Geometry expression to transform
            source_srid: Source SRID (original geometry CRS)
            target_srid: Target SRID (desired output CRS)
            buffer_value: Buffer distance in meters (0 = no buffer)
            dialect: SQL dialect ('postgresql' or 'spatialite')

        Returns:
            Tuple of (transformed_expr, needs_transform_back):
            - transformed_expr: Expression with transformation to EPSG:3857 if needed
            - needs_transform_back: True if result needs transformation back to target_srid

        Logic:
            - If target is NOT geographic OR buffer is 0: No transformation needed
            - If source is already 3857: Use directly, transform result to target
            - Otherwise: Transform source to 3857 for buffer, then to target

        Examples:
            Geographic CRS with buffer:
                Input: geom, source=4326, target=4326, buffer=100
                Output: ('ST_Transform(geom, 3857)', True)
                Usage: ST_Buffer(ST_Transform(geom, 3857), 100) → transform back to 4326

            Projected CRS:
                Input: geom, source=2154, target=2154, buffer=100
                Output: ('geom', False)
                Usage: ST_Buffer(geom, 100) → no transform back needed

            Already in 3857:
                Input: geom, source=3857, target=4326, buffer=100
                Output: ('geom', True)
                Usage: ST_Buffer(geom, 100) → transform to 4326
        """
        # Get dialect-specific function names
        funcs = self._get_dialect_functions(dialect)

        # Check if target CRS is geographic
        is_target_geographic = target_srid == 4326 or (4000 < target_srid < 5000)

        # No transformation needed if not geographic or no buffer
        if not is_target_geographic or buffer_value == 0:
            return (geom_expr, False)

        # Determine transformation strategy
        if source_srid == 3857:
            # Source already in Web Mercator - use directly
            self.log_debug(f"Source already in EPSG:3857, will transform result to {target_srid}")
            return (geom_expr, True)

        # Transform to EPSG:3857 for metric buffer
        self.log_info(f"🌍 Geographic CRS (source={source_srid}, target={target_srid}) - transforming to EPSG:3857 for buffer")
        transformed_expr = f"ST_Transform({geom_expr}, 3857)"
        return (transformed_expr, True)

    def _apply_geographic_buffer_transform(
        self,
        geom_expr: str,
        source_srid: int,
        target_srid: int,
        buffer_value: float,
        dialect: str = 'postgresql'
    ) -> str:
        """
        Apply complete geographic CRS buffer transformation chain.

        FIX v3.0.12: High-level helper that combines transformation + buffer + transform back.
        Simplifies geographic CRS buffer operations in backends.

        This is the main method backends should use for geographic CRS buffering.
        It handles the complete transformation chain:
        1. Transform geometry to EPSG:3857 if needed
        2. Apply buffer in meters
        3. Transform result back to target CRS if needed

        Args:
            geom_expr: Geometry expression to buffer
            source_srid: Source SRID (original geometry CRS)
            target_srid: Target SRID (desired output CRS)
            buffer_value: Buffer distance in meters
            dialect: SQL dialect ('postgresql' or 'spatialite')

        Returns:
            Complete buffer expression with transformations

        Examples:
            Geographic CRS (EPSG:4326) with 100m buffer:
                ST_Transform(ST_Buffer(ST_Transform(geom, 3857), 100), 4326)

            Projected CRS (EPSG:2154) with 100m buffer:
                ST_Buffer(geom, 100)

        Note:
            This method delegates to _build_buffer_expression() for the actual
            buffer operation, ensuring consistent buffer handling (negative buffers,
            validation, etc.) across all CRS types.
        """
        # Get transformation strategy
        working_geom, needs_transform_back = self._wrap_with_geographic_transform(
            geom_expr, source_srid, target_srid, buffer_value, dialect
        )

        # Apply buffer on (potentially transformed) geometry
        buffered_expr = self._build_buffer_expression(working_geom, buffer_value, dialect)

        # Transform back to target CRS if needed
        if needs_transform_back:
            buffered_expr = f"ST_Transform({buffered_expr}, {target_srid})"
            self.log_debug(f"Transformed buffered result back to SRID {target_srid}")

        return buffered_expr

    def _is_task_canceled(self) -> bool:
        """
        Check if the parent task was canceled.

        Returns:
            True if task was canceled, False otherwise
        """
        if hasattr(self, 'task_params') and self.task_params:
            task = self.task_params.get('_parent_task')
            if task and hasattr(task, 'isCanceled'):
                return task.isCanceled()
        return False


class TemporaryTableManager:
    """
    Context manager for automatic cleanup of temporary database tables.

    FIX v3.0.12: Ensures temporary tables are ALWAYS cleaned up, even if exceptions occur.
    Prevents accumulation of orphaned tables in user databases.

    This addresses the issue where exceptions during table creation/population
    would leave temporary tables in the database indefinitely, causing:
    - Database bloat (tables accumulating over time)
    - Performance degradation (more tables to scan)
    - Eventual resource exhaustion

    Usage:
        with TemporaryTableManager(db_path, table_name, logger) as manager:
            # Create and use table
            cursor.execute(f'CREATE TABLE {table_name} ...')
            # ... populate table ...
            # If exception occurs, table is automatically dropped

    The manager tracks:
    - Table creation state
    - R-tree spatial indexes (need special cleanup)
    - Connection state
    - Cleanup success/failure

    Args:
        db_path: Path to SQLite/GeoPackage database
        table_name: Name of temporary table to manage
        logger: Logger instance for diagnostic messages (optional)
        has_spatial_index: Whether table has R-tree spatial indexes (default True)
    """

    def __init__(self, db_path: str, table_name: str, logger=None, has_spatial_index: bool = True):
        self.db_path = db_path
        self.table_name = table_name
        self.logger = logger
        self.has_spatial_index = has_spatial_index
        self._table_created = False
        self._cleanup_attempted = False

    def __enter__(self):
        """Enter context - table about to be created."""
        return self

    def mark_created(self):
        """
        Mark table as created - enables cleanup on exit.

        Call this immediately after CREATE TABLE succeeds.
        """
        self._table_created = True
        if self.logger:
            self.logger.debug(f"TemporaryTableManager: Table '{self.table_name}' marked for cleanup")

    def keep(self):
        """
        Keep the table - prevent cleanup on exit.

        Call this when table should be preserved (e.g., successful completion).
        Useful for "permanent" temporary tables that are cleaned up later by other mechanisms.
        """
        self._table_created = False  # Disable cleanup
        if self.logger:
            self.logger.debug(f"TemporaryTableManager: Table '{self.table_name}' will be preserved")

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit context - cleanup table if created.

        Runs even if exception occurred (exc_type is not None).
        Returns False to propagate exceptions (normal behavior).
        """
        if self._table_created and not self._cleanup_attempted:
            self._cleanup()

        # Return False to propagate any exception
        return False

    def _cleanup(self):
        """
        Clean up temporary table and spatial indexes.

        Called automatically on context exit.
        Safe to call multiple times (idempotent).
        """
        self._cleanup_attempted = True

        if not self._table_created:
            if self.logger:
                self.logger.debug(f"TemporaryTableManager: No cleanup needed for '{self.table_name}' (not created or already cleaned)")
            return

        conn = None
        cleanup_start = None
        try:
            import sqlite3
            import time

            cleanup_start = time.time()
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()

            # Check if table exists before cleanup
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (self.table_name,))
            table_exists = cursor.fetchone() is not None

            if not table_exists:
                if self.logger:
                    self.logger.debug(f"TemporaryTableManager: Table '{self.table_name}' does not exist (already cleaned up)")
                conn.close()
                return

            # Disable spatial indexes if present
            indexes_disabled = 0
            if self.has_spatial_index:
                for geom_col in ['geom', 'geom_buffered']:
                    try:
                        cursor.execute(f'SELECT DisableSpatialIndex("{self.table_name}", "{geom_col}")')
                        indexes_disabled += 1
                    except Exception:
                        pass  # Index may not exist

            # Drop the table
            cursor.execute(f'DROP TABLE IF EXISTS "{self.table_name}"')
            conn.commit()
            conn.close()

            cleanup_duration = time.time() - cleanup_start
            if self.logger:
                self.logger.info(f"🧹 TemporaryTableManager: Cleaned up table '{self.table_name}' "
                               f"({indexes_disabled} indexes disabled, {cleanup_duration:.3f}s)")

        except Exception as e:
            cleanup_duration = time.time() - cleanup_start if cleanup_start else 0
            if self.logger:
                self.logger.warning(f"TemporaryTableManager: Error cleaning up '{self.table_name}' "
                                  f"after {cleanup_duration:.3f}s: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

# -*- coding: utf-8 -*-
"""
FilterMate Spatialite Backend Implementation - ARCH-043

Main backend class for Spatialite filtering with R-tree optimization.
Implements BackendPort interface.

Part of Phase 4 Backend Refactoring.

Features:
- R-tree spatial index optimization
- Result caching
- Temporary table support
- GeoPackage compatibility

Author: FilterMate Team
Date: January 2026
"""

import logging
import sqlite3
import time
import re
from typing import Optional, List, Dict, Any
from pathlib import Path

from ....core.ports.backend_port import BackendPort, BackendInfo, BackendCapability
from ....core.domain.filter_expression import FilterExpression, ProviderType
from ....core.domain.filter_result import FilterResult
from ....core.domain.layer_info import LayerInfo

from .cache import SpatialiteCache, create_cache
from .index_manager import RTreeIndexManager, create_index_manager

logger = logging.getLogger('FilterMate.Backend.Spatialite')

# v4.0.4: Import centralized spatialite_connect to eliminate duplication
try:
    from ....infrastructure.utils.task_utils import spatialite_connect
except ImportError:
    # Fallback for testing or import issues
    def spatialite_connect(db_path: str) -> sqlite3.Connection:
        """
        Create Spatialite connection with extensions loaded (fallback).

        Args:
            db_path: Path to Spatialite/GeoPackage database

        Returns:
            Connection with mod_spatialite loaded

        Raises:
            RuntimeError: If extension cannot be loaded
        """
        conn = sqlite3.connect(db_path)
        conn.enable_load_extension(True)

        # Try different extension names based on platform
        extensions = [
            'mod_spatialite',
            'mod_spatialite.dll',
            'mod_spatialite.so',
            'mod_spatialite.dylib',
            '/usr/lib/mod_spatialite.so',
            '/usr/lib/x86_64-linux-gnu/mod_spatialite.so',
            '/usr/local/lib/mod_spatialite.dylib'
        ]

        loaded = False
        for ext in extensions:
            try:
                conn.load_extension(ext)
                logger.debug(f"[Spatialite] Extension Loaded - Name: {ext}")
                loaded = True
                break
            except Exception as e:
                logger.debug(f"Ignored in spatialite extension load ({ext}): {e}")
                continue

        if not loaded:
            logger.warning("[Spatialite] Extension Not Loaded - mod_spatialite unavailable - Spatial functions may be limited")

        return conn


class SpatialiteBackend(BackendPort):
    """
    Spatialite backend for filter operations.

    Features:
    - R-tree spatial index optimization
    - Result caching
    - Temporary table support
    - GeoPackage compatibility

    Example:
        backend = SpatialiteBackend("/path/to/db.sqlite")
        result = backend.execute(expression, layer_info)
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        connection: Optional[sqlite3.Connection] = None,
        cache_config: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ):
        """
        Initialize Spatialite backend.

        Args:
            db_path: Path to Spatialite/GeoPackage database
            connection: Existing connection (alternative to db_path)
            cache_config: Optional cache configuration
            use_cache: Enable result caching
        """
        self._db_path = db_path
        self._use_cache = use_cache

        # Initialize connection
        if connection:
            self._conn = connection
            self._owns_connection = False
        elif db_path:
            self._conn = spatialite_connect(db_path)
            self._owns_connection = True
        else:
            self._conn = None
            self._owns_connection = False

        # Initialize components
        cache_config = cache_config or {}
        self._cache = create_cache(
            max_entries=cache_config.get('max_entries', 100),
            ttl_seconds=cache_config.get('ttl_seconds', 300.0),
            max_geometry_cache_mb=cache_config.get('max_geometry_cache_mb', 50.0)
        )

        if self._conn:
            self._index_manager = create_index_manager(self._conn)
        else:
            self._index_manager = None

        # Metrics
        self._metrics = {
            'executions': 0,
            'cache_hits': 0,
            'total_time_ms': 0.0,
            'errors': 0
        }

        if db_path:
            logger.info(f"[Spatialite] Backend Initialized - Database: {Path(db_path).name} - Cache enabled: {self._cache is not None}")

    @property
    def cache(self) -> SpatialiteCache:
        """Access to cache."""
        return self._cache

    @property
    def index_manager(self) -> Optional[RTreeIndexManager]:
        """Access to index manager."""
        return self._index_manager

    @property
    def metrics(self) -> Dict[str, Any]:
        """Get backend metrics."""
        return self._metrics.copy()

    def get_statistics(self) -> Dict[str, Any]:
        """Get backend execution statistics."""
        stats = self.metrics
        # Add cache statistics
        stats['cache_stats'] = self._cache.get_stats()
        return stats

    def reset_statistics(self) -> None:
        """Reset backend execution statistics."""
        self._metrics = {
            'executions': 0,
            'cache_hits': 0,
            'total_time_ms': 0.0,
            'errors': 0
        }

    def set_connection(self, connection: sqlite3.Connection) -> None:
        """
        Set database connection.

        Args:
            connection: Spatialite connection
        """
        if self._owns_connection and self._conn:
            self._conn.close()

        self._conn = connection
        self._owns_connection = False
        self._index_manager = create_index_manager(connection)

    def execute(
        self,
        expression: FilterExpression,
        layer_info: LayerInfo,
        target_layer_infos: Optional[List[LayerInfo]] = None
    ) -> FilterResult:
        """
        Execute filter expression.

        Args:
            expression: Validated filter expression
            layer_info: Source layer information
            target_layer_infos: Optional target layers

        Returns:
            FilterResult with matching feature IDs
        """
        start_time = time.time()
        self._metrics['executions'] += 1

        # Check cache first
        if self._use_cache:
            cached = self._cache.get_result(layer_info.layer_id, expression.raw)
            if cached is not None:
                self._metrics['cache_hits'] += 1
                return FilterResult.from_cache(
                    feature_ids=cached,
                    layer_id=layer_info.layer_id,
                    expression_raw=expression.raw,
                    backend_name=self.name
                )

        if self._conn is None:
            return FilterResult.error(
                layer_id=layer_info.layer_id,
                expression_raw=expression.raw,
                error_message="No database connection available",
                backend_name=self.name
            )

        try:
            # Ensure spatial index exists
            table_name = self._get_table_name(layer_info)
            geom_col = self._get_geometry_column(layer_info)

            if self._index_manager:
                self._index_manager.ensure_index(table_name, geom_col)

            # Execute query
            feature_ids = self._execute_query(expression, layer_info)

            execution_time = (time.time() - start_time) * 1000
            self._metrics['total_time_ms'] += execution_time

            # Cache result
            if self._use_cache:
                self._cache.set_result(
                    layer_info.layer_id,
                    expression.raw,
                    tuple(feature_ids)
                )

            return FilterResult.success(
                feature_ids=feature_ids,
                layer_id=layer_info.layer_id,
                expression_raw=expression.raw,
                execution_time_ms=execution_time,
                backend_name=self.name
            )

        except Exception as e:
            self._metrics['errors'] += 1
            logger.exception(f"Spatialite filter execution failed: {e}")
            return FilterResult.error(
                layer_id=layer_info.layer_id,
                expression_raw=expression.raw,
                error_message=str(e),
                backend_name=self.name
            )

    def supports_layer(self, layer_info: LayerInfo) -> bool:
        """Check if this backend supports the layer."""
        return layer_info.provider_type == ProviderType.SPATIALITE

    def get_info(self) -> BackendInfo:
        """Get backend information."""
        return BackendInfo(
            name="Spatialite",
            version="1.0.0",
            capabilities=(
                BackendCapability.SPATIAL_FILTER |
                BackendCapability.SPATIAL_INDEX |
                BackendCapability.CACHED_RESULTS |
                BackendCapability.BUFFER_OPERATIONS
            ),
            priority=80,  # High priority after PostgreSQL
            max_features=500000,
            description="Spatialite/GeoPackage backend with R-tree indexing"
        )

    def cleanup(self) -> None:
        """Clean up resources."""
        # Clear cache
        cleared = self._cache.clear()
        logger.debug(f"[Spatialite] Spatialite cache cleared: {cleared} entries")

    def estimate_execution_time(
        self,
        expression: FilterExpression,
        layer_info: LayerInfo
    ) -> float:
        """
        Estimate execution time.

        Spatialite is generally slower than PostgreSQL
        but faster than OGR for indexed queries.
        """
        base_time = layer_info.feature_count * 0.05  # 0.05ms per feature

        if expression.is_spatial:
            table_name = self._get_table_name(layer_info)
            geom_col = self._get_geometry_column(layer_info)
            if self._index_manager and self._index_manager.has_index(table_name, geom_col):
                base_time *= 0.2  # 5x faster with index

        return base_time

    def create_temp_table(
        self,
        table_name: str,
        query: str,
        geometry_column: Optional[str] = None
    ) -> bool:
        """
        Create a temporary table from query results.

        This is Spatialite's alternative to PostgreSQL materialized views.

        Args:
            table_name: Name for temp table
            query: SELECT query for table contents
            geometry_column: Geometry column name for spatial index

        Returns:
            True if table created successfully
        """
        if self._conn is None:
            return False

        try:
            cursor = self._conn.cursor()

            # Drop if exists
            cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')  # nosec B608

            # Create table from query
            cursor.execute(f'CREATE TABLE "{table_name}" AS {query}')  # nosec B608

            # Create spatial index if geometry column specified
            if geometry_column and self._index_manager:
                self._index_manager.create_index(table_name, geometry_column)

            self._conn.commit()
            logger.debug(f"[Spatialite] Temp Table Created - Name: {table_name} - Spatial index: {geometry_column is not None}")
            return True

        except Exception as e:
            logger.error(f"[Spatialite] Temp Table Creation Failed - Name: {table_name} - {type(e).__name__}: {str(e)}")
            return False

    def drop_temp_table(self, table_name: str) -> bool:
        """
        Drop a temporary table.

        Args:
            table_name: Table to drop

        Returns:
            True if dropped successfully
        """
        if self._conn is None:
            return False

        try:
            cursor = self._conn.cursor()
            cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')  # nosec B608
            self._conn.commit()
            logger.debug(f"[Spatialite] Temp Table Dropped - Name: {table_name}")
            return True
        except Exception as e:
            logger.error(f"[Spatialite] Temp Table Drop Failed - Name: {table_name} - {type(e).__name__}: {str(e)}")
            return False

    def test_connection(self) -> bool:
        """Test database connection."""
        if self._conn is None:
            return False

        try:
            cursor = self._conn.cursor()
            cursor.execute("SELECT 1")
            return cursor.fetchone() is not None
        except Exception:
            return False

    # === Private Methods ===

    def _execute_query(
        self,
        expression: FilterExpression,
        layer_info: LayerInfo
    ) -> List[int]:
        """Execute filter query and return feature IDs."""
        self._get_table_name(layer_info)
        self._get_pk_column(layer_info)

        # Convert expression to Spatialite SQL if needed
        self._convert_to_spatialite(expression.sql)

        query = """
            SELECT "{pk_column}" FROM "{table_name}"
            WHERE {sql}
        """

        cursor = self._conn.cursor()
        cursor.execute(query)
        return [row[0] for row in cursor.fetchall()]

    def _convert_to_spatialite(self, sql: str) -> str:
        """
        Convert SQL expression to Spatialite dialect.

        Spatialite spatial functions are mostly compatible with PostGIS
        but some differences exist.
        """
        converted = sql

        # ST_Intersects -> Intersects (Spatialite uses Intersects)
        # But recent Spatialite versions also support ST_* prefix
        # We'll keep ST_ prefix as it's more portable

        # Handle any PostGIS-specific functions
        # Most ST_* functions work in Spatialite

        return converted

    def _get_table_name(self, layer_info: LayerInfo) -> str:
        """Extract table name from layer source."""
        source = layer_info.source_path

        # GeoPackage format: "/path/to/file.gpkg|layername=tablename"
        if '|layername=' in source:
            return source.split('|layername=')[1].split('|')[0]

        # Spatialite format: "/path/to/file.sqlite|layername=tablename"
        match = re.search(r'\|layername=([^\|]+)', source)
        if match:
            return match.group(1)

        # Fallback to layer table_name
        if layer_info.table_name:
            return layer_info.table_name

        return "unknown"

    def _get_geometry_column(self, layer_info: LayerInfo) -> str:
        """Get geometry column name."""
        # Common Spatialite/GeoPackage geometry column names
        return "geometry"

    def _get_pk_column(self, layer_info: LayerInfo) -> str:
        """Get primary key column."""
        # GeoPackage uses 'fid', Spatialite may use 'ROWID' or 'id'
        return "fid"

    def __del__(self):
        """Close connection on cleanup."""
        if self._owns_connection and hasattr(self, '_conn') and self._conn:
            try:
                self._conn.close()
            except Exception as e:
                logger.debug(f"Ignored in connection close: {e}")


def create_spatialite_backend(
    db_path: Optional[str] = None,
    connection: Optional[sqlite3.Connection] = None,
    cache_config: Optional[Dict[str, Any]] = None,
    use_cache: bool = True
) -> SpatialiteBackend:
    """
    Factory function for SpatialiteBackend.

    Args:
        db_path: Path to database file
        connection: Existing connection
        cache_config: Cache configuration
        use_cache: Enable caching

    Returns:
        Configured SpatialiteBackend instance
    """
    return SpatialiteBackend(
        db_path=db_path,
        connection=connection,
        cache_config=cache_config,
        use_cache=use_cache
    )

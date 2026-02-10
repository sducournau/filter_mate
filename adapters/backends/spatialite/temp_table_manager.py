# -*- coding: utf-8 -*-
"""
Spatialite Temp Table Manager - FilterMate v4.2

Manages temporary tables for Spatialite filter optimization.
Implements MaterializedViewPort interface.

This is Spatialite's equivalent to PostgreSQL materialized views.
Uses CREATE TABLE AS SELECT with R-tree spatial indexing.

Features:
- Session-scoped temp table management
- R-tree spatial index optimization
- Automatic cleanup on session end
- Statistics tracking

Author: FilterMate Team
Date: January 2026
"""

import logging
import hashlib
import sqlite3
import time
from typing import Optional, List, Dict, Any
from datetime import datetime

from ....core.ports.materialized_view_port import (
    MaterializedViewPort,
    ViewType,
    ViewInfo,
    ViewConfig
)

logger = logging.getLogger('FilterMate.Backend.Spatialite.TempTableManager')


# v4.0.4: Import centralized spatialite_connect
try:
    from ....infrastructure.utils.task_utils import spatialite_connect
except ImportError:
    def spatialite_connect(db_path: str) -> sqlite3.Connection:
        """Fallback spatialite_connect."""
        conn = sqlite3.connect(db_path)
        conn.enable_load_extension(True)
        for ext in ['mod_spatialite', 'mod_spatialite.dll', 'mod_spatialite.so']:
            try:
                conn.load_extension(ext)
                break
            except Exception:
                continue
        return conn


class SpatialiteTempTableManager(MaterializedViewPort):
    """
    Manages temporary tables for Spatialite filter optimization.

    This is Spatialite's alternative to PostgreSQL materialized views.
    Creates temp tables with R-tree spatial indexes for efficient spatial queries.

    Example:
        manager = SpatialiteTempTableManager(db_path="/path/to/db.sqlite")

        # Create temp table for expensive filter
        table_name = manager.create_view(
            query="SELECT * FROM roads WHERE type = 'highway'",
            source_table="roads",
            geometry_column="geom"
        )

        # Query using temp table
        fids = manager.get_feature_ids(table_name, "fid")

        # Cleanup on session end
        manager.cleanup_session_views()
    """

    # Naming conventions
    TABLE_PREFIX = "fm_tmp_"
    SESSION_PREFIX = "s_"

    # Thresholds - v4.2.12: Increased, only use temp tables for large/complex cases
    DEFAULT_FEATURE_THRESHOLD = 50000  # Increased from 5k to 50k

    def __init__(
        self,
        db_path: Optional[str] = None,
        connection: Optional[sqlite3.Connection] = None,
        config: Optional[ViewConfig] = None,
        session_id: Optional[str] = None
    ):
        """
        Initialize SpatialiteTempTableManager.

        Args:
            db_path: Path to Spatialite database
            connection: Existing connection (alternative to db_path)
            config: View configuration settings
            session_id: Unique session ID for session-scoped tables
        """
        self._db_path = db_path
        self._config = config or self._default_config()
        self._session_id = session_id or self._generate_session_id()

        # Connection management
        if connection:
            self._conn = connection
            self._owns_connection = False
        elif db_path:
            self._conn = spatialite_connect(db_path)
            self._owns_connection = True
        else:
            self._conn = None
            self._owns_connection = False

        # Track created tables
        self._created_tables: Dict[str, ViewInfo] = {}

        # Metrics
        self._metrics = {
            'tables_created': 0,
            'tables_refreshed': 0,
            'tables_dropped': 0,
            'cache_hits': 0,
            'total_creation_time_ms': 0.0
        }

        logger.debug(
            "[Spatialite] TempTableManager initialized: "
            f"session={self._session_id[:8]}, db_path={db_path}"
        )

    def _default_config(self) -> ViewConfig:
        """Create default config optimized for Spatialite."""
        return ViewConfig(
            feature_threshold=self.DEFAULT_FEATURE_THRESHOLD,
            complexity_threshold=4,  # v4.2.12: Increased from 2 to 4
            prefix=self.TABLE_PREFIX,
            schema="",  # Spatialite doesn't use schemas
            use_rtree=True,
            register_geometry=True
        )

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        import uuid
        return str(uuid.uuid4())[:12]

    def _generate_table_name(self, query: str, session_scoped: bool) -> str:
        """Generate unique table name from query hash."""
        query_hash = hashlib.md5(query.encode(), usedforsecurity=False).hexdigest()[:8]

        if session_scoped:
            return f"{self.TABLE_PREFIX}{self.SESSION_PREFIX}{self._session_id[:8]}_{query_hash}"
        return f"{self.TABLE_PREFIX}{query_hash}"

    def _get_connection(self) -> Optional[sqlite3.Connection]:
        """Get database connection."""
        if self._conn:
            return self._conn
        if self._db_path:
            self._conn = spatialite_connect(self._db_path)
            self._owns_connection = True
            return self._conn
        return None

    # ==========================================================================
    # MaterializedViewPort Implementation
    # ==========================================================================

    @property
    def view_type(self) -> ViewType:
        """Return the type of view this manager creates."""
        return ViewType.TEMP_TABLE

    @property
    def session_id(self) -> str:
        """Get current session ID."""
        return self._session_id

    @property
    def config(self) -> ViewConfig:
        """Get current configuration."""
        return self._config

    @property
    def metrics(self) -> Dict[str, Any]:
        """Get metrics."""
        return self._metrics.copy()

    def should_use_view(
        self,
        feature_count: int,
        expression_complexity: int = 1,
        is_spatial: bool = False
    ) -> bool:
        """
        Determine if temp table should be used.

        Spatialite benefits from temp tables for:
        - Large datasets (> feature_threshold)
        - Complex expressions
        - Spatial queries on medium+ datasets
        """
        # Large datasets benefit from temp table
        if feature_count >= self._config.feature_threshold:
            return True

        # Complex expressions benefit from temp table
        if expression_complexity >= self._config.complexity_threshold:
            return True

        # Spatial queries on medium datasets benefit
        if is_spatial and feature_count >= self._config.feature_threshold // 2:
            return True

        return False

    def create_view(
        self,
        query: str,
        source_table: str,
        geometry_column: str = "geometry",
        srid: int = 4326,
        indexes: Optional[List[str]] = None,
        session_scoped: bool = True
    ) -> str:
        """
        Create a temporary table from query.

        Args:
            query: SELECT query for table contents
            source_table: Source table name (for naming)
            geometry_column: Geometry column for spatial index
            srid: Spatial reference ID
            indexes: Additional columns to index
            session_scoped: Whether table is session-scoped

        Returns:
            Name of created table
        """
        # Generate unique table name
        table_name = self._generate_table_name(query, session_scoped)

        # Check if already exists
        if self.view_exists(table_name):
            logger.debug(f"[Spatialite] Table {table_name} already exists, reusing")
            self._metrics['cache_hits'] += 1
            return table_name

        conn = self._get_connection()
        if conn is None:
            raise RuntimeError("No database connection available")

        start_time = time.time()

        try:
            cursor = conn.cursor()

            # Drop if exists (for recreation)
            cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')  # nosec B608

            # Create table from query
            create_sql = f'CREATE TABLE "{table_name}" AS {query}'  # nosec B608
            logger.debug(f"[Spatialite] Creating temp table: {create_sql[:100]}...")
            cursor.execute(create_sql)

            # Get row count
            cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')  # nosec B608
            row_count = cursor.fetchone()[0]

            # Create spatial index if geometry column specified
            has_spatial_index = False
            if geometry_column and self._config.use_rtree:
                has_spatial_index = self._create_spatial_index(
                    cursor, table_name, geometry_column, srid
                )

            # Create additional indexes
            if indexes and self._config.create_btree_indexes:
                for col in indexes:
                    self._create_index(cursor, table_name, col)

            conn.commit()

            elapsed_ms = (time.time() - start_time) * 1000

            # Track created table
            self._created_tables[table_name] = ViewInfo(
                name=table_name,
                view_type=ViewType.TEMP_TABLE,
                schema=None,
                created_at=datetime.now(),
                last_refresh=datetime.now(),
                row_count=row_count,
                is_populated=True,
                definition=query,
                session_id=self._session_id if session_scoped else None,
                geometry_column=geometry_column,
                srid=srid,
                has_spatial_index=has_spatial_index
            )

            self._metrics['tables_created'] += 1
            self._metrics['total_creation_time_ms'] += elapsed_ms

            logger.info(
                f"[Spatialite] Created temp table: {table_name} "
                f"({row_count} rows, {elapsed_ms:.1f}ms, spatial_idx={has_spatial_index})"
            )
            return table_name

        except Exception as e:
            logger.error(f"[Spatialite] Failed to create temp table {table_name}: {e}")
            raise

    def _create_spatial_index(
        self,
        cursor: sqlite3.Cursor,
        table_name: str,
        geometry_column: str,
        srid: int
    ) -> bool:
        """Create R-tree spatial index on geometry column."""
        try:
            # First, register geometry column if config says so
            if self._config.register_geometry:
                try:
                    cursor.execute("""
                        SELECT RecoverGeometryColumn(
                            '{table_name}',
                            '{geometry_column}',
                            {srid},
                            'GEOMETRY',
                            'XY'
                        )
                    """)
                except Exception as e:
                    logger.debug(f"[Spatialite] RecoverGeometryColumn skipped: {e}")

            # Create R-tree spatial index
            cursor.execute("""
                SELECT CreateSpatialIndex('{table_name}', '{geometry_column}')
            """)

            logger.debug(
                "[Spatialite] Created R-tree index on "
                f"{table_name}.{geometry_column}"
            )
            return True

        except Exception as e:
            logger.warning(f"[Spatialite] Spatial index creation failed: {e}")
            return False

    def _create_index(
        self,
        cursor: sqlite3.Cursor,
        table_name: str,
        column: str
    ) -> bool:
        """Create B-tree index on column."""
        try:
            index_name = f"idx_{table_name}_{column}"
            cursor.execute(
                f'CREATE INDEX IF NOT EXISTS "{index_name}" '
                f'ON "{table_name}" ("{column}")'
            )
            return True
        except Exception as e:
            logger.warning(f"[Spatialite] Index creation failed: {e}")
            return False

    def refresh_view(self, view_name: str) -> bool:
        """
        Refresh a temp table by recreating it.

        Note: Unlike PostgreSQL REFRESH MATERIALIZED VIEW,
        Spatialite requires dropping and recreating the table.
        """
        if view_name not in self._created_tables:
            logger.warning(f"[Spatialite] Cannot refresh unknown table: {view_name}")
            return False

        view_info = self._created_tables[view_name]

        try:
            # Drop and recreate
            self.drop_view(view_name, if_exists=True)

            # Recreate with original query
            self.create_view(
                query=view_info.definition,
                source_table="",  # Not needed for refresh
                geometry_column=view_info.geometry_column or "geometry",
                srid=view_info.srid or 4326,
                session_scoped=view_info.session_id is not None
            )

            self._metrics['tables_refreshed'] += 1
            logger.debug(f"[Spatialite] Refreshed temp table: {view_name}")
            return True

        except Exception as e:
            logger.error(f"[Spatialite] Failed to refresh temp table {view_name}: {e}")
            return False

    def drop_view(self, view_name: str, if_exists: bool = True) -> bool:
        """Drop a temporary table."""
        conn = self._get_connection()
        if conn is None:
            logger.error("[Spatialite] No connection for drop_view")
            return False

        try:
            cursor = conn.cursor()

            exists_clause = "IF EXISTS" if if_exists else ""
            cursor.execute(f'DROP TABLE {exists_clause} "{view_name}"')  # nosec B608

            # Also drop spatial index if exists
            try:
                cursor.execute(f"SELECT DisableSpatialIndex('{view_name}', 'geometry')")  # nosec B608
            except Exception:
                pass  # Index may not exist

            conn.commit()

            # Remove from tracking
            self._created_tables.pop(view_name, None)

            self._metrics['tables_dropped'] += 1
            logger.debug(f"[Spatialite] Dropped temp table: {view_name}")
            return True

        except Exception as e:
            logger.error(f"[Spatialite] Failed to drop temp table {view_name}: {e}")
            return False

    def view_exists(self, view_name: str) -> bool:
        """Check if temp table exists."""
        conn = self._get_connection()
        if conn is None:
            return False

        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name=?
            """, (view_name,))
            return cursor.fetchone() is not None
        except Exception:
            return False

    def get_view_info(self, view_name: str) -> Optional[ViewInfo]:
        """Get information about a temp table."""
        # Check tracking first
        if view_name in self._created_tables:
            return self._created_tables[view_name]

        # Check database
        if not self.view_exists(view_name):
            return None

        conn = self._get_connection()
        if conn is None:
            return None

        try:
            cursor = conn.cursor()

            # Get row count
            cursor.execute(f'SELECT COUNT(*) FROM "{view_name}"')  # nosec B608
            row_count = cursor.fetchone()[0]

            # Check for spatial index
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name LIKE ?
            """, (f"idx_{view_name}_%",))
            has_spatial_index = cursor.fetchone() is not None

            return ViewInfo(
                name=view_name,
                view_type=ViewType.TEMP_TABLE,
                row_count=row_count,
                is_populated=True,
                has_spatial_index=has_spatial_index
            )

        except Exception as e:
            logger.warning(f"[Spatialite] Failed to get view info: {e}")
            return None

    def list_session_views(self) -> List[ViewInfo]:
        """List all tables created in current session."""
        return [
            info for info in self._created_tables.values()
            if info.session_id == self._session_id
        ]

    def cleanup_session_views(self) -> int:
        """Clean up all session tables."""
        session_tables = [
            name for name, info in self._created_tables.items()
            if info.session_id == self._session_id
        ]

        dropped = 0
        for table_name in session_tables:
            if self.drop_view(table_name):
                dropped += 1

        # Also clean up any orphaned session tables in database
        conn = self._get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                pattern = f"{self.TABLE_PREFIX}{self.SESSION_PREFIX}{self._session_id[:8]}%"
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name LIKE ?
                """, (pattern,))

                for (table_name,) in cursor.fetchall():
                    if table_name not in session_tables:
                        try:
                            cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')  # nosec B608
                            dropped += 1
                        except Exception:
                            pass

                conn.commit()
            except Exception as e:
                logger.warning(f"[Spatialite] Orphan cleanup error: {e}")

        logger.info(f"[Spatialite] Session cleanup: {dropped} tables dropped")
        return dropped

    def query_view(
        self,
        view_name: str,
        columns: Optional[List[str]] = None,
        where_clause: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Any]:
        """Query a temp table."""
        conn = self._get_connection()
        if conn is None:
            return []

        try:
            cursor = conn.cursor()

            # Build query
            cols = ", ".join(f'"{c}"' for c in columns) if columns else "*"
            query = f'SELECT {cols} FROM "{view_name}"'  # nosec B608

            if where_clause:
                query += f" WHERE {where_clause}"

            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query)
            return cursor.fetchall()

        except Exception as e:
            logger.error(f"[Spatialite] Query failed: {e}")
            return []

    def get_feature_ids(
        self,
        view_name: str,
        primary_key: str = "id"
    ) -> List[int]:
        """Get feature IDs from temp table."""
        results = self.query_view(view_name, columns=[primary_key])
        return [row[0] for row in results if row[0] is not None]

    # ==========================================================================
    # Additional Methods
    # ==========================================================================

    def create_filtered_view(
        self,
        source_table: str,
        where_clause: str,
        geometry_column: str = "geometry",
        primary_key: str = "id",
        srid: int = 4326,
        buffer_value: Optional[float] = None,
        buffer_segments: int = 5
    ) -> str:
        """
        Create a filtered temp table with optional buffer.

        This is a convenience method for common filter operations.

        Args:
            source_table: Source table name
            where_clause: SQL WHERE clause (without WHERE keyword)
            geometry_column: Geometry column name
            primary_key: Primary key column name
            srid: Spatial reference ID
            buffer_value: Optional buffer distance
            buffer_segments: Buffer segments (quad_segs)

        Returns:
            Name of created temp table
        """
        # Build SELECT query
        if buffer_value:
            query = """
                SELECT "{primary_key}",
                       ST_Buffer("{geometry_column}", {buffer_value}, {buffer_segments}) AS {geometry_column}
                FROM "{source_table}"
                WHERE {where_clause}
            """
        else:
            query = """
                SELECT * FROM "{source_table}"
                WHERE {where_clause}
            """

        return self.create_view(
            query=query,
            source_table=source_table,
            geometry_column=geometry_column,
            srid=srid,
            indexes=[primary_key]
        )

    def create_spatial_join_view(
        self,
        target_table: str,
        source_table: str,
        target_geom: str = "geometry",
        source_geom: str = "geometry",
        target_pk: str = "id",
        predicate: str = "ST_Intersects",
        source_where: Optional[str] = None
    ) -> str:
        """
        Create a temp table for spatial join results.

        Args:
            target_table: Table to filter
            source_table: Source geometry table
            target_geom: Target geometry column
            source_geom: Source geometry column
            target_pk: Target primary key
            predicate: Spatial predicate (ST_Intersects, ST_Within, etc.)
            source_where: Optional WHERE clause for source

        Returns:
            Name of created temp table
        """
        f"AND {source_where}" if source_where else ""

        query = """
            SELECT DISTINCT t."{target_pk}", t."{target_geom}"
            FROM "{target_table}" t
            WHERE EXISTS (
                SELECT 1 FROM "{source_table}" s
                WHERE {predicate}(t."{target_geom}", s."{source_geom}")
                {source_filter}
            )
        """

        return self.create_view(
            query=query,
            source_table=f"{target_table}_join_{source_table}",
            geometry_column=target_geom,
            indexes=[target_pk]
        )

    def close(self):
        """Close connection if owned."""
        if self._owns_connection and self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup_session_views()
        self.close()


# Factory function
def create_temp_table_manager(
    db_path: Optional[str] = None,
    connection: Optional[sqlite3.Connection] = None,
    session_id: Optional[str] = None
) -> SpatialiteTempTableManager:
    """
    Create a SpatialiteTempTableManager.

    Args:
        db_path: Path to Spatialite database
        connection: Existing connection
        session_id: Session ID for scoping

    Returns:
        Configured SpatialiteTempTableManager
    """
    return SpatialiteTempTableManager(
        db_path=db_path,
        connection=connection,
        session_id=session_id
    )


__all__ = [
    'SpatialiteTempTableManager',
    'create_temp_table_manager',
]

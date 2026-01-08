# -*- coding: utf-8 -*-
"""
FilterMate Materialized View Manager - ARCH-036

Manages materialized views for PostgreSQL filter optimization.
Extracted from monolithic postgresql_backend.py as part of Phase 4.

Features:
- MV creation with proper naming conventions
- MV refresh strategies (full, incremental)
- MV lifecycle management
- Session-scoped MV tracking
- Statistics and monitoring

Author: FilterMate Team
Date: January 2026
"""

import logging
import hashlib
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger('FilterMate.PostgreSQL.MVManager')


@dataclass
class MVInfo:
    """Information about a materialized view."""
    name: str
    schema: str
    created_at: datetime
    last_refresh: Optional[datetime]
    row_count: int
    size_bytes: int
    is_populated: bool
    definition: str
    session_id: Optional[str] = None


@dataclass
class MVConfig:
    """Configuration for materialized view creation."""
    feature_threshold: int = 10000
    complexity_threshold: int = 3
    auto_refresh: bool = True
    refresh_on_change: bool = True
    concurrent_refresh: bool = True
    with_data: bool = True
    create_spatial_index: bool = True
    create_btree_indexes: bool = True


class MaterializedViewManager:
    """
    Manages materialized views for PostgreSQL filter optimization.

    Materialized views are used to pre-compute expensive filter
    results for large datasets or complex expressions.

    Example:
        mv_manager = MaterializedViewManager(connection_pool)

        # Create MV for expensive filter
        mv_name = mv_manager.create_mv(
            query="SELECT * FROM roads WHERE type = 'highway'",
            source_table="roads",
            geometry_column="geom"
        )

        # Query using MV
        results = mv_manager.query_mv(mv_name, additional_filter)

        # Refresh when source data changes
        mv_manager.refresh_mv(mv_name)
    """

    # Naming conventions
    MV_PREFIX = "fm_mv_"
    MV_SCHEMA = "filtermate_temp"
    SESSION_PREFIX = "session_"

    def __init__(
        self,
        connection_pool=None,
        config: Optional[MVConfig] = None,
        session_id: Optional[str] = None
    ):
        """
        Initialize MaterializedViewManager.

        Args:
            connection_pool: Database connection pool
            config: MV configuration settings
            session_id: Unique session ID for session-scoped MVs
        """
        self._pool = connection_pool
        self._config = config or MVConfig()
        self._session_id = session_id or self._generate_session_id()
        self._created_mvs: Dict[str, MVInfo] = {}
        self._metrics = {
            'mvs_created': 0,
            'mvs_refreshed': 0,
            'mvs_dropped': 0,
            'cache_hits': 0
        }

        logger.debug(
            f"MaterializedViewManager initialized: session={self._session_id[:8]}"
        )

    @property
    def session_id(self) -> str:
        """Get current session ID."""
        return self._session_id

    @property
    def config(self) -> MVConfig:
        """Get current configuration."""
        return self._config

    @property
    def metrics(self) -> Dict[str, int]:
        """Get metrics."""
        return self._metrics.copy()

    def should_use_mv(
        self,
        feature_count: int,
        expression_complexity: int,
        is_spatial: bool
    ) -> bool:
        """
        Determine if materialized view should be used.

        Args:
            feature_count: Number of features in source
            expression_complexity: Estimated expression complexity
            is_spatial: Whether expression includes spatial predicates

        Returns:
            True if MV would be beneficial
        """
        # Large datasets benefit from MV
        if feature_count >= self._config.feature_threshold:
            return True

        # Complex expressions benefit from MV
        if expression_complexity >= self._config.complexity_threshold:
            return True

        # Spatial queries on medium datasets benefit
        if is_spatial and feature_count >= self._config.feature_threshold // 2:
            return True

        return False

    def create_mv(
        self,
        query: str,
        source_table: str,
        geometry_column: str = "geometry",
        indexes: Optional[List[str]] = None,
        session_scoped: bool = True,
        connection=None
    ) -> str:
        """
        Create a materialized view.

        Args:
            query: SELECT query for MV definition
            source_table: Source table name
            geometry_column: Geometry column for spatial index
            indexes: Additional columns to index
            session_scoped: Whether MV is session-scoped
            connection: Database connection to use

        Returns:
            Name of created materialized view
        """
        # Generate unique MV name
        mv_name = self._generate_mv_name(query, session_scoped)
        full_name = f'"{self.MV_SCHEMA}"."{mv_name}"'

        # Check if already exists
        if self.mv_exists(mv_name, connection=connection):
            logger.debug(f"MV {mv_name} already exists, reusing")
            self._metrics['cache_hits'] += 1
            return mv_name

        conn = connection or self._get_connection()
        if conn is None:
            raise RuntimeError("No database connection available")

        try:
            cursor = conn.cursor()

            # Ensure schema exists
            cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{self.MV_SCHEMA}"')

            # Create MV
            with_data = "WITH DATA" if self._config.with_data else "WITH NO DATA"
            create_sql = f"""
                CREATE MATERIALIZED VIEW {full_name} AS
                {query}
                {with_data}
            """
            cursor.execute(create_sql)

            # Create spatial index
            if self._config.create_spatial_index and geometry_column:
                self._create_spatial_index(cursor, full_name, geometry_column)

            # Create additional indexes
            if self._config.create_btree_indexes and indexes:
                for col in indexes:
                    self._create_index(cursor, full_name, col)

            if connection is None:
                conn.commit()

            # Track created MV
            self._created_mvs[mv_name] = MVInfo(
                name=mv_name,
                schema=self.MV_SCHEMA,
                created_at=datetime.now(),
                last_refresh=datetime.now() if self._config.with_data else None,
                row_count=-1,
                size_bytes=0,
                is_populated=self._config.with_data,
                definition=query,
                session_id=self._session_id if session_scoped else None
            )

            self._metrics['mvs_created'] += 1
            logger.info(f"Created MV: {mv_name}")
            return mv_name

        except Exception as e:
            logger.error(f"Failed to create MV {mv_name}: {e}")
            raise

    def refresh_mv(
        self,
        mv_name: str,
        concurrent: Optional[bool] = None,
        connection=None
    ) -> bool:
        """
        Refresh a materialized view.

        Args:
            mv_name: Name of MV to refresh
            concurrent: Use CONCURRENTLY (default from config)
            connection: Database connection to use

        Returns:
            True if refresh succeeded
        """
        full_name = f'"{self.MV_SCHEMA}"."{mv_name}"'
        use_concurrent = concurrent if concurrent is not None else self._config.concurrent_refresh

        conn = connection or self._get_connection()
        if conn is None:
            logger.error("No database connection for MV refresh")
            return False

        try:
            cursor = conn.cursor()

            concurrently = "CONCURRENTLY" if use_concurrent else ""
            cursor.execute(f"REFRESH MATERIALIZED VIEW {concurrently} {full_name}")

            if connection is None:
                conn.commit()

            # Update tracking
            if mv_name in self._created_mvs:
                old_info = self._created_mvs[mv_name]
                self._created_mvs[mv_name] = MVInfo(
                    name=old_info.name,
                    schema=old_info.schema,
                    created_at=old_info.created_at,
                    last_refresh=datetime.now(),
                    row_count=old_info.row_count,
                    size_bytes=old_info.size_bytes,
                    is_populated=True,
                    definition=old_info.definition,
                    session_id=old_info.session_id
                )

            self._metrics['mvs_refreshed'] += 1
            logger.debug(f"Refreshed MV: {mv_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to refresh MV {mv_name}: {e}")
            return False

    def drop_mv(
        self,
        mv_name: str,
        if_exists: bool = True,
        connection=None
    ) -> bool:
        """
        Drop a materialized view.

        Args:
            mv_name: Name of MV to drop
            if_exists: Use IF EXISTS clause
            connection: Database connection to use

        Returns:
            True if drop succeeded
        """
        full_name = f'"{self.MV_SCHEMA}"."{mv_name}"'

        conn = connection or self._get_connection()
        if conn is None:
            logger.error("No database connection for MV drop")
            return False

        try:
            cursor = conn.cursor()

            exists_clause = "IF EXISTS" if if_exists else ""
            cursor.execute(f"DROP MATERIALIZED VIEW {exists_clause} {full_name} CASCADE")

            if connection is None:
                conn.commit()

            # Remove from tracking
            self._created_mvs.pop(mv_name, None)

            self._metrics['mvs_dropped'] += 1
            logger.debug(f"Dropped MV: {mv_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to drop MV {mv_name}: {e}")
            return False

    def mv_exists(
        self,
        mv_name: str,
        connection=None
    ) -> bool:
        """Check if materialized view exists."""
        conn = connection or self._get_connection()
        if conn is None:
            return False

        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_matviews
                    WHERE schemaname = %s AND matviewname = %s
                )
            """, (self.MV_SCHEMA, mv_name))
            result = cursor.fetchone()
            return result[0] if result else False
        except Exception:
            return False

    def get_mv_info(
        self,
        mv_name: str,
        connection=None
    ) -> Optional[MVInfo]:
        """Get information about a materialized view."""
        if not self.mv_exists(mv_name, connection=connection):
            return None

        conn = connection or self._get_connection()
        if conn is None:
            return None

        try:
            cursor = conn.cursor()

            # Get MV statistics
            cursor.execute("""
                SELECT
                    pg_relation_size(oid) as size_bytes,
                    reltuples as row_estimate
                FROM pg_class
                WHERE relname = %s AND relnamespace = (
                    SELECT oid FROM pg_namespace WHERE nspname = %s
                )
            """, (mv_name, self.MV_SCHEMA))

            row = cursor.fetchone()
            if row:
                size_bytes, row_count = row

                # Get definition
                cursor.execute("""
                    SELECT definition FROM pg_matviews
                    WHERE schemaname = %s AND matviewname = %s
                """, (self.MV_SCHEMA, mv_name))
                definition_row = cursor.fetchone()
                definition = definition_row[0] if definition_row else ""

                return MVInfo(
                    name=mv_name,
                    schema=self.MV_SCHEMA,
                    created_at=datetime.now(),
                    last_refresh=None,
                    row_count=int(row_count),
                    size_bytes=int(size_bytes),
                    is_populated=True,
                    definition=definition
                )

        except Exception as e:
            logger.error(f"Failed to get MV info for {mv_name}: {e}")

        return None

    def cleanup_session_mvs(self, connection=None) -> int:
        """
        Clean up all session-scoped materialized views.

        Returns:
            Number of MVs dropped
        """
        count = 0
        session_pattern = f"{self.MV_PREFIX}{self.SESSION_PREFIX}{self._session_id}_%"

        conn = connection or self._get_connection()
        if conn is None:
            return 0

        try:
            cursor = conn.cursor()

            # Find all session MVs
            cursor.execute("""
                SELECT matviewname FROM pg_matviews
                WHERE schemaname = %s AND matviewname LIKE %s
            """, (self.MV_SCHEMA, session_pattern))

            mv_names = [row[0] for row in cursor.fetchall()]

            for mv_name in mv_names:
                if self.drop_mv(mv_name, connection=conn):
                    count += 1

            if connection is None:
                conn.commit()

        except Exception as e:
            logger.error(f"Failed to cleanup session MVs: {e}")

        logger.info(f"Cleaned up {count} session MVs")
        return count

    def get_created_mvs(self) -> List[MVInfo]:
        """Get list of MVs created by this manager."""
        return list(self._created_mvs.values())

    def query_mv(
        self,
        mv_name: str,
        columns: str = "*",
        where_clause: Optional[str] = None,
        connection=None
    ) -> List[Tuple]:
        """
        Query a materialized view.

        Args:
            mv_name: Name of MV to query
            columns: Column selection (default "*")
            where_clause: Optional WHERE clause
            connection: Database connection to use

        Returns:
            List of result rows
        """
        full_name = f'"{self.MV_SCHEMA}"."{mv_name}"'

        conn = connection or self._get_connection()
        if conn is None:
            return []

        try:
            cursor = conn.cursor()

            query = f"SELECT {columns} FROM {full_name}"
            if where_clause:
                query += f" WHERE {where_clause}"

            cursor.execute(query)
            return cursor.fetchall()

        except Exception as e:
            logger.error(f"Failed to query MV {mv_name}: {e}")
            return []

    # === Private Methods ===

    def _get_connection(self):
        """Get connection from pool."""
        if self._pool is None:
            return None
        try:
            if hasattr(self._pool, 'get_connection'):
                return self._pool.get_connection()
            elif hasattr(self._pool, 'getconn'):
                return self._pool.getconn()
            else:
                return self._pool
        except Exception:
            return None

    def _generate_mv_name(self, query: str, session_scoped: bool) -> str:
        """Generate unique MV name from query hash."""
        query_hash = hashlib.md5(query.encode()).hexdigest()[:12]

        if session_scoped:
            return f"{self.MV_PREFIX}{self.SESSION_PREFIX}{self._session_id}_{query_hash}"
        else:
            return f"{self.MV_PREFIX}{query_hash}"

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        import uuid
        return uuid.uuid4().hex[:8]

    def _create_spatial_index(
        self,
        cursor,
        table_name: str,
        geometry_column: str
    ) -> None:
        """Create spatial index on MV geometry column."""
        # Clean table name for index naming
        clean_name = table_name.replace('"', '').replace('.', '_')
        index_name = f"idx_{clean_name}_geom"

        try:
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS "{index_name}"
                ON {table_name} USING GIST ("{geometry_column}")
            """)
        except Exception as e:
            logger.warning(f"Failed to create spatial index: {e}")

    def _create_index(
        self,
        cursor,
        table_name: str,
        column: str
    ) -> None:
        """Create btree index on column."""
        clean_name = table_name.replace('"', '').replace('.', '_')
        index_name = f"idx_{clean_name}_{column}"

        try:
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS "{index_name}"
                ON {table_name} ("{column}")
            """)
        except Exception as e:
            logger.warning(f"Failed to create index on {column}: {e}")


def create_mv_manager(
    connection_pool=None,
    session_id: Optional[str] = None,
    config: Optional[MVConfig] = None
) -> MaterializedViewManager:
    """
    Factory function for MaterializedViewManager.

    Args:
        connection_pool: Database connection pool
        session_id: Session ID for tracking
        config: Optional MV configuration

    Returns:
        Configured MaterializedViewManager instance
    """
    return MaterializedViewManager(
        connection_pool=connection_pool,
        config=config,
        session_id=session_id
    )

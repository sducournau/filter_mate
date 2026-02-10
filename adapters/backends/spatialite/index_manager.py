# -*- coding: utf-8 -*-
"""
FilterMate Spatialite R-Tree Index Manager - ARCH-042

Manages R-tree spatial indexes for Spatialite databases.
Essential for efficient spatial queries.

Part of Phase 4 Backend Refactoring.

Features:
- R-tree index creation and management
- Index status checking
- Index rebuild/optimize operations
- Batch index management

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional, List
from dataclasses import dataclass

logger = logging.getLogger('FilterMate.Spatialite.IndexManager')


@dataclass
class IndexInfo:
    """Information about a spatial index."""
    table_name: str
    geometry_column: str
    index_name: str
    row_count: int
    is_valid: bool
    size_bytes: int = 0


class RTreeIndexManager:
    """
    Manages R-tree spatial indexes in Spatialite.

    R-tree indexes are essential for efficient spatial queries
    in Spatialite databases.

    Example:
        manager = RTreeIndexManager(connection)

        # Ensure index exists
        manager.ensure_index("roads", "geometry")

        # Check index status
        if manager.has_index("roads", "geometry"):

    """

    def __init__(self, connection):
        """
        Initialize index manager.

        Args:
            connection: Spatialite database connection (with mod_spatialite loaded)
        """
        self._conn = connection
        self._metrics = {
            'indexes_created': 0,
            'indexes_dropped': 0,
            'indexes_rebuilt': 0
        }

    @property
    def metrics(self) -> dict:
        """Get index manager metrics."""
        return self._metrics.copy()

    def has_index(
        self,
        table_name: str,
        geometry_column: str
    ) -> bool:
        """
        Check if R-tree index exists for table.

        Args:
            table_name: Table name
            geometry_column: Geometry column name

        Returns:
            True if index exists
        """
        index_table = f"idx_{table_name}_{geometry_column}"
        cursor = self._conn.cursor()

        try:
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name=?
            """, (index_table,))
            return cursor.fetchone() is not None
        except Exception as e:
            logger.debug(f"[Spatialite] Error checking index existence: {e}")
            return False

    def create_index(
        self,
        table_name: str,
        geometry_column: str
    ) -> bool:
        """
        Create R-tree spatial index.

        Args:
            table_name: Table to index
            geometry_column: Geometry column

        Returns:
            True if index created successfully
        """
        cursor = self._conn.cursor()

        try:
            # Create the spatial index using Spatialite function
            cursor.execute(
                f"SELECT CreateSpatialIndex('{table_name}', '{geometry_column}')"  # nosec B608
            )
            self._conn.commit()

            self._metrics['indexes_created'] += 1
            logger.info(f"[Spatialite] Created R-tree index on {table_name}.{geometry_column}")
            return True

        except Exception as e:
            logger.error(f"[Spatialite] Failed to create index on {table_name}.{geometry_column}: {e}")
            return False

    def ensure_index(
        self,
        table_name: str,
        geometry_column: str
    ) -> bool:
        """
        Ensure index exists, create if not.

        Args:
            table_name: Table name
            geometry_column: Geometry column

        Returns:
            True if index exists or was created
        """
        if self.has_index(table_name, geometry_column):
            return True
        return self.create_index(table_name, geometry_column)

    def drop_index(
        self,
        table_name: str,
        geometry_column: str
    ) -> bool:
        """
        Drop R-tree spatial index.

        Args:
            table_name: Table name
            geometry_column: Geometry column

        Returns:
            True if index dropped
        """
        cursor = self._conn.cursor()

        try:
            # Disable spatial index using Spatialite function
            cursor.execute(
                f"SELECT DisableSpatialIndex('{table_name}', '{geometry_column}')"  # nosec B608
            )

            # Drop the index table
            index_table = f"idx_{table_name}_{geometry_column}"
            cursor.execute(f"DROP TABLE IF EXISTS \"{index_table}\"")  # nosec B608

            self._conn.commit()

            self._metrics['indexes_dropped'] += 1
            logger.info(f"[Spatialite] Dropped R-tree index on {table_name}.{geometry_column}")
            return True

        except Exception as e:
            logger.error(f"[Spatialite] Failed to drop index on {table_name}.{geometry_column}: {e}")
            return False

    def rebuild_index(
        self,
        table_name: str,
        geometry_column: str
    ) -> bool:
        """
        Rebuild R-tree index (drop and recreate).

        Args:
            table_name: Table name
            geometry_column: Geometry column

        Returns:
            True if rebuild successful
        """
        if self.drop_index(table_name, geometry_column):
            result = self.create_index(table_name, geometry_column)
            if result:
                self._metrics['indexes_rebuilt'] += 1
            return result
        return False

    def get_index_info(
        self,
        table_name: str,
        geometry_column: str
    ) -> Optional[IndexInfo]:
        """
        Get information about a spatial index.

        Args:
            table_name: Table name
            geometry_column: Geometry column

        Returns:
            IndexInfo or None if index doesn't exist
        """
        if not self.has_index(table_name, geometry_column):
            return None

        index_table = f"idx_{table_name}_{geometry_column}"
        cursor = self._conn.cursor()

        try:
            # Get row count
            cursor.execute(f'SELECT COUNT(*) FROM "{index_table}"')  # nosec B608
            row_count = cursor.fetchone()[0]

            # Validate index using Spatialite function
            try:
                cursor.execute(
                    f"SELECT CheckSpatialIndex('{table_name}', '{geometry_column}')"  # nosec B608
                )
                check_result = cursor.fetchone()
                is_valid = check_result[0] == 1 if check_result else False
            except Exception:
                is_valid = True  # Assume valid if check not available

            # Get table size
            try:
                cursor.execute(
                    f"SELECT page_count * page_size FROM pragma_page_count('{index_table}'), pragma_page_size()"  # nosec B608
                )
                size_result = cursor.fetchone()
                size_bytes = size_result[0] if size_result else 0
            except Exception:
                size_bytes = 0

            return IndexInfo(
                table_name=table_name,
                geometry_column=geometry_column,
                index_name=index_table,
                row_count=row_count,
                is_valid=is_valid,
                size_bytes=size_bytes
            )

        except Exception as e:
            logger.error(f"[Spatialite] Failed to get index info for {table_name}.{geometry_column}: {e}")
            return None

    def get_all_indexes(self) -> List[IndexInfo]:
        """
        Get info for all spatial indexes in database.

        Returns:
            List of IndexInfo for all spatial indexes
        """
        cursor = self._conn.cursor()
        indexes: List[IndexInfo] = []

        try:
            # Find all geometry columns registered in Spatialite
            cursor.execute("""
                SELECT f_table_name, f_geometry_column
                FROM geometry_columns
            """)

            for table_name, geom_col in cursor.fetchall():
                info = self.get_index_info(table_name, geom_col)
                if info:
                    indexes.append(info)

        except Exception as e:
            logger.error(f"[Spatialite] Failed to get all indexes: {e}")

        return indexes

    def optimize_all_indexes(self) -> int:
        """
        Optimize all spatial indexes by rebuilding them.

        Returns:
            Number of indexes optimized
        """
        count = 0
        cursor = self._conn.cursor()

        try:
            cursor.execute("""
                SELECT f_table_name, f_geometry_column
                FROM geometry_columns
            """)

            for table_name, geom_col in cursor.fetchall():
                if self.has_index(table_name, geom_col):
                    if self.rebuild_index(table_name, geom_col):
                        count += 1

        except Exception as e:
            logger.error(f"[Spatialite] Failed to optimize indexes: {e}")

        logger.info(f"[Spatialite] Optimized {count} spatial indexes")
        return count

    def vacuum_index_tables(self) -> bool:
        """
        Vacuum all index tables to reclaim space.

        Returns:
            True if vacuum successful
        """
        cursor = self._conn.cursor()

        try:
            # Get all index tables
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name LIKE 'idx_%'
            """)

            index_tables = [row[0] for row in cursor.fetchall()]

            # SQLite doesn't support VACUUM on individual tables
            # So we just run a general VACUUM
            cursor.execute("VACUUM")
            self._conn.commit()

            logger.info(f"[Spatialite] Vacuumed database (includes {len(index_tables)} index tables)")
            return True

        except Exception as e:
            logger.error(f"[Spatialite] Failed to vacuum: {e}")
            return False

    def create_indexes_for_layer(
        self,
        table_name: str,
        geometry_column: str = "geometry",
        attribute_columns: Optional[List[str]] = None
    ) -> int:
        """
        Create spatial and attribute indexes for a layer.

        Args:
            table_name: Table name
            geometry_column: Geometry column name
            attribute_columns: List of attribute columns to index

        Returns:
            Number of indexes created
        """
        count = 0

        # Create spatial index
        if self.create_index(table_name, geometry_column):
            count += 1

        # Create btree indexes for attribute columns
        if attribute_columns:
            cursor = self._conn.cursor()
            for col in attribute_columns:
                try:
                    index_name = f"idx_{table_name}_{col}"
                    cursor.execute(
                        f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{table_name}" ("{col}")'
                    )
                    count += 1
                except Exception as e:
                    logger.warning(f"[Spatialite] Failed to create index on {table_name}.{col}: {e}")

            self._conn.commit()

        return count


def create_index_manager(connection) -> RTreeIndexManager:
    """
    Factory function for RTreeIndexManager.

    Args:
        connection: Spatialite database connection

    Returns:
        Configured RTreeIndexManager instance
    """
    return RTreeIndexManager(connection)

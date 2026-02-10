# -*- coding: utf-8 -*-
"""
Materialized View Port Interface - FilterMate v4.2

Abstract interface for materialized view / temp table operations.
Provides unified API for PostgreSQL materialized views and Spatialite temp tables.

This is the Port in Hexagonal Architecture pattern, defining the contract
that all backends must implement for view/table caching operations.

Author: FilterMate Team
Date: January 2026
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto


class ViewType(Enum):
    """Type of materialized storage."""
    MATERIALIZED_VIEW = auto()    # PostgreSQL MATERIALIZED VIEW
    TEMP_TABLE = auto()           # Spatialite/SQLite temp table
    VIRTUAL_VIEW = auto()         # In-memory view (future)


@dataclass
class ViewInfo:
    """
    Information about a materialized view or temp table.

    Unified representation that works for both PostgreSQL MVs
    and Spatialite temp tables.
    """
    name: str
    view_type: ViewType
    schema: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_refresh: Optional[datetime] = None
    row_count: int = -1
    size_bytes: int = 0
    is_populated: bool = True
    definition: str = ""
    session_id: Optional[str] = None
    geometry_column: Optional[str] = None
    srid: Optional[int] = None
    has_spatial_index: bool = False

    @property
    def full_name(self) -> str:
        """Get fully qualified name (schema.name or just name)."""
        if self.schema:
            return f'"{self.schema}"."{self.name}"'
        return f'"{self.name}"'

    @property
    def is_materialized_view(self) -> bool:
        """Check if this is a PostgreSQL materialized view."""
        return self.view_type == ViewType.MATERIALIZED_VIEW

    @property
    def is_temp_table(self) -> bool:
        """Check if this is a Spatialite temp table."""
        return self.view_type == ViewType.TEMP_TABLE


@dataclass
class ViewConfig:
    """
    Configuration for view/table creation.

    v4.2.12: Conservative defaults - MV only for very large/complex cases.

    Unified config that works for both backends.
    """
    # Thresholds - v4.2.12: Increased significantly
    feature_threshold: int = 100000   # Only use MV for very large datasets
    complexity_threshold: int = 5      # Only for very complex expressions

    # Creation options
    with_data: bool = True
    create_spatial_index: bool = True
    create_btree_indexes: bool = True

    # Refresh options (PostgreSQL only)
    auto_refresh: bool = True
    refresh_on_change: bool = True
    concurrent_refresh: bool = True

    # Naming (unified fm_temp_* prefix v4.4.4+)
    prefix: str = "fm_temp_mv_"
    schema: str = "filtermate_temp"

    # Spatialite specific
    use_rtree: bool = True
    register_geometry: bool = True


class MaterializedViewPort(ABC):
    """
    Abstract interface for materialized view operations.

    Defines the contract for creating, managing, and querying
    materialized views (PostgreSQL) or temp tables (Spatialite).

    Example:
        # PostgreSQL implementation
        class PostgreSQLMVManager(MaterializedViewPort):
            def create_view(self, query, source_table, ...):
                # CREATE MATERIALIZED VIEW ...

        # Spatialite implementation
        class SpatialiteTempTableManager(MaterializedViewPort):
            def create_view(self, query, source_table, ...):
                # CREATE TABLE ... AS SELECT ...
    """

    @property
    @abstractmethod
    def view_type(self) -> ViewType:
        """Return the type of view this manager creates."""

    @property
    @abstractmethod
    def session_id(self) -> str:
        """Get current session ID."""

    @property
    @abstractmethod
    def config(self) -> ViewConfig:
        """Get current configuration."""

    @abstractmethod
    def should_use_view(
        self,
        feature_count: int,
        expression_complexity: int = 1,
        is_spatial: bool = False
    ) -> bool:
        """
        Determine if a materialized view/temp table should be used.

        Args:
            feature_count: Number of features in source
            expression_complexity: Estimated expression complexity
            is_spatial: Whether expression includes spatial predicates

        Returns:
            True if view would be beneficial
        """

    @abstractmethod
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
        Create a materialized view or temp table.

        Args:
            query: SELECT query for view definition
            source_table: Source table name (for naming)
            geometry_column: Geometry column for spatial index
            srid: Spatial reference ID
            indexes: Additional columns to index
            session_scoped: Whether view is session-scoped

        Returns:
            Name of created view/table
        """

    @abstractmethod
    def refresh_view(self, view_name: str) -> bool:
        """
        Refresh a materialized view or recreate temp table.

        Args:
            view_name: Name of view/table to refresh

        Returns:
            True if refresh succeeded
        """

    @abstractmethod
    def drop_view(self, view_name: str, if_exists: bool = True) -> bool:
        """
        Drop a materialized view or temp table.

        Args:
            view_name: Name of view/table to drop
            if_exists: Use IF EXISTS clause

        Returns:
            True if drop succeeded
        """

    @abstractmethod
    def view_exists(self, view_name: str) -> bool:
        """
        Check if view/table exists.

        Args:
            view_name: Name to check

        Returns:
            True if exists
        """

    @abstractmethod
    def get_view_info(self, view_name: str) -> Optional[ViewInfo]:
        """
        Get information about a view/table.

        Args:
            view_name: Name of view/table

        Returns:
            ViewInfo or None if not found
        """

    @abstractmethod
    def list_session_views(self) -> List[ViewInfo]:
        """
        List all views/tables created in current session.

        Returns:
            List of ViewInfo for session views
        """

    @abstractmethod
    def cleanup_session_views(self) -> int:
        """
        Clean up all session views/tables.

        Returns:
            Number of views/tables dropped
        """

    @abstractmethod
    def query_view(
        self,
        view_name: str,
        columns: Optional[List[str]] = None,
        where_clause: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Any]:
        """
        Query a view/table.

        Args:
            view_name: View/table to query
            columns: Columns to select (default: all)
            where_clause: Additional WHERE clause
            limit: Maximum rows to return

        Returns:
            List of result rows
        """

    @abstractmethod
    def get_feature_ids(
        self,
        view_name: str,
        primary_key: str = "id"
    ) -> List[int]:
        """
        Get feature IDs from view/table.

        Args:
            view_name: View/table to query
            primary_key: Primary key column name

        Returns:
            List of feature IDs
        """


__all__ = [
    'ViewType',
    'ViewInfo',
    'ViewConfig',
    'MaterializedViewPort',
]

# -*- coding: utf-8 -*-
"""
Prepared Statements Manager for FilterMate

Provides database-agnostic prepared statement management for optimized query execution.
Supports PostgreSQL (named prepared statements) and Spatialite (parameterized queries).

Location: infrastructure/database/prepared_statements.py (Hexagonal Architecture)

Usage:
    from ...infrastructure.database import create_prepared_statements
    ps_manager = create_prepared_statements(connection, 'postgresql')
    ps_manager.insert_subset_history(...)

Author: FilterMate Team
Date: January 2026
"""
import logging
import sqlite3
from abc import ABC, abstractmethod
from typing import Any

from .postgresql_support import psycopg2

# Conditional exception type for psycopg2 operations
_PsycopgError = psycopg2.Error if psycopg2 else Exception

logger = logging.getLogger('FilterMate.PreparedStatements')


class PreparedStatementManager(ABC):
    """Base class for prepared statement managers."""

    def __init__(self, connection):
        """
        Initialize prepared statement manager.

        Args:
            connection: Database connection (psycopg2 or sqlite3)
        """
        self.connection = connection
        self._prepared = False

    @abstractmethod
    def prepare(self) -> bool:
        """Prepare statements. Returns True if successful."""

    @abstractmethod
    def insert_subset_history(
        self,
        history_id: str,
        project_uuid: str,
        layer_id: str,
        source_layer_id: str,
        seq_order: int,
        subset_string: str
    ) -> bool:
        """Insert subset history record."""

    @abstractmethod
    def delete_subset_history(self, project_uuid: str, layer_id: str) -> bool:
        """
        Delete subset history records for a layer.

        Args:
            project_uuid: Project UUID
            layer_id: Layer ID

        Returns:
            True if successful, False otherwise
        """

    def close(self):
        """Close/deallocate prepared statements."""


class PostgreSQLPreparedStatements(PreparedStatementManager):
    """PostgreSQL prepared statement manager using named prepared statements."""

    def __init__(self, connection):
        super().__init__(connection)
        self._stmt_names = []

    def prepare(self) -> bool:
        """Prepare PostgreSQL named statements."""
        try:
            cursor = self.connection.cursor()
            # Prepare insert statement
            # Column names must match fm_subset_history schema:
            # id, _updated_at, fk_project, layer_id, layer_source_id, seq_order, subset_string
            cursor.execute("""
                PREPARE insert_subset_history_stmt (text, timestamp, text, text, text, int, text) AS
                INSERT INTO fm_subset_history (
                    id, _updated_at, fk_project, layer_id, layer_source_id, seq_order, subset_string
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """)
            self._stmt_names.append('insert_subset_history_stmt')
            self._prepared = True
            return True
        except _PsycopgError as e:
            logger.warning(f"Failed to prepare PostgreSQL statements: {e}")
            return False

    def insert_subset_history(
        self,
        history_id: str,
        project_uuid: str,
        layer_id: str,
        source_layer_id: str,
        seq_order: int,
        subset_string: str
    ) -> bool:
        """Execute prepared insert statement."""
        from datetime import datetime
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "EXECUTE insert_subset_history_stmt (%s, %s, %s, %s, %s, %s, %s)",
                (history_id, datetime.now(), project_uuid, layer_id, source_layer_id, seq_order, subset_string)
            )
            self.connection.commit()
            return True
        except _PsycopgError as e:
            logger.warning(f"PostgreSQL prepared insert failed: {e}")
            return False

    def delete_subset_history(self, project_uuid: str, layer_id: str) -> bool:
        """
        Delete subset history records for a layer.

        Args:
            project_uuid: Project UUID
            layer_id: Layer ID

        Returns:
            True if successful
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "DELETE FROM fm_subset_history WHERE fk_project = %s AND layer_id = %s",
                (project_uuid, layer_id)
            )
            self.connection.commit()
            logger.debug(f"Deleted subset history for layer {layer_id}")
            return True
        except _PsycopgError as e:
            logger.warning(f"PostgreSQL delete_subset_history failed: {e}")
            return False

    def close(self):
        """Deallocate prepared statements."""
        try:
            cursor = self.connection.cursor()
            for stmt_name in self._stmt_names:
                cursor.execute(f"DEALLOCATE {stmt_name}")
            self._stmt_names.clear()
        except _PsycopgError as e:
            logger.debug(f"Error deallocating prepared statements: {e}")


class SpatialitePreparedStatements(PreparedStatementManager):
    """Spatialite prepared statement manager using parameterized queries."""

    def __init__(self, connection):
        super().__init__(connection)
        self._insert_sql = None

    def prepare(self) -> bool:
        """Prepare Spatialite parameterized queries."""
        try:
            # Spatialite/SQLite uses ? placeholders
            # Column names must match fm_subset_history schema:
            # id, _updated_at, fk_project, layer_id, layer_source_id, seq_order, subset_string
            self._insert_sql = """
                INSERT INTO fm_subset_history (
                    id, _updated_at, fk_project, layer_id, layer_source_id, seq_order, subset_string
                ) VALUES (?, datetime('now'), ?, ?, ?, ?, ?)
            """
            self._prepared = True
            return True
        except Exception as e:  # catch-all safety net (string assignment only)
            logger.warning(f"Failed to prepare Spatialite statements: {e}")
            return False

    def insert_subset_history(
        self,
        history_id: str,
        project_uuid: str,
        layer_id: str,
        source_layer_id: str,
        seq_order: int,
        subset_string: str
    ) -> bool:
        """Execute parameterized insert."""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                self._insert_sql,
                (history_id, project_uuid, layer_id, source_layer_id, seq_order, subset_string)
            )
            self.connection.commit()
            return True
        except sqlite3.Error as e:
            logger.warning(f"Spatialite prepared insert failed: {e}")
            return False

    def delete_subset_history(self, project_uuid: str, layer_id: str) -> bool:
        """
        Delete subset history records for a layer.

        Args:
            project_uuid: Project UUID
            layer_id: Layer ID

        Returns:
            True if successful
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "DELETE FROM fm_subset_history WHERE fk_project = ? AND layer_id = ?",
                (project_uuid, layer_id)
            )
            self.connection.commit()
            logger.debug(f"Deleted subset history for layer {layer_id}")
            return True
        except sqlite3.Error as e:
            logger.warning(f"Spatialite delete_subset_history failed: {e}")
            return False


class NullPreparedStatements(PreparedStatementManager):
    """Null object pattern for when prepared statements are not available."""

    def prepare(self) -> bool:
        """No-op prepare."""
        return True

    def insert_subset_history(
        self,
        history_id: str,
        project_uuid: str,
        layer_id: str,
        source_layer_id: str,
        seq_order: int,
        subset_string: str
    ) -> bool:
        """Return False to indicate fallback to direct SQL should be used."""
        return False

    def delete_subset_history(self, project_uuid: str, layer_id: str) -> bool:
        """Return False to indicate fallback to direct SQL should be used."""
        return False


def create_prepared_statements(
    connection: Any,
    provider_type: str
) -> PreparedStatementManager:
    """
    Factory function to create appropriate prepared statement manager.

    Args:
        connection: Database connection (psycopg2 or sqlite3)
        provider_type: 'postgresql' or 'spatialite'

    Returns:
        PreparedStatementManager instance
    """
    if provider_type == 'postgresql':
        manager = PostgreSQLPreparedStatements(connection)
    elif provider_type == 'spatialite':
        manager = SpatialitePreparedStatements(connection)
    else:
        logger.debug(f"Unknown provider type '{provider_type}', using null manager")
        return NullPreparedStatements(connection)

    # Try to prepare statements
    if manager.prepare():
        logger.debug(f"Prepared statements initialized for {provider_type}")
        return manager
    else:
        logger.debug(f"Prepared statements not available for {provider_type}, using null manager")
        return NullPreparedStatements(connection)


__all__ = [
    'PreparedStatementManager',
    'PostgreSQLPreparedStatements',
    'SpatialitePreparedStatements',
    'NullPreparedStatements',
    'create_prepared_statements',
]

"""
FilterMate History Repository

Centralized data access for filter history operations.
Eliminates SQL duplication across backends (PostgreSQL, Spatialite, OGR).

EPIC-1 Phase E4-S9: History Repository Pattern

This module provides a single source of truth for history-related SQL operations:
- Insert/delete/select from fm_subset_history table
- Consistent error handling and logging
- Support for both Spatialite and PostgreSQL connections

Author: FilterMate Team
Created: January 2026
"""

import logging
import uuid
from typing import Optional, Tuple, List, Any
from dataclasses import dataclass

logger = logging.getLogger('FilterMate.Adapters.Repositories.History')


@dataclass
class HistoryEntry:
    """
    Represents a filter history entry.
    
    Attributes:
        id: Unique identifier (UUID)
        timestamp: Creation timestamp
        project_uuid: Project UUID
        layer_id: QGIS layer ID
        source_layer_id: Source layer ID (for filtered layers)
        seq_order: Sequence order for undo/redo
        subset_string: The SQL subset string
    """
    id: str
    timestamp: str
    project_uuid: str
    layer_id: str
    source_layer_id: str
    seq_order: int
    subset_string: str
    
    @classmethod
    def from_row(cls, row: tuple) -> 'HistoryEntry':
        """Create HistoryEntry from database row."""
        return cls(
            id=row[0],
            timestamp=row[1],
            project_uuid=row[2],
            layer_id=row[3],
            source_layer_id=row[4] if len(row) > 4 else '',
            seq_order=row[5] if len(row) > 5 else 0,
            subset_string=row[-1]  # Last column is always subset_string
        )


class HistoryRepository:
    """
    Repository for filter history operations.
    
    Provides centralized data access for fm_subset_history table,
    replacing duplicated SQL across backends.
    
    Usage:
        repo = HistoryRepository(connection, cursor)
        repo.insert(project_uuid, layer_id, subset_string, seq_order)
        last_entry = repo.get_last_entry(project_uuid, layer_id)
        repo.delete_for_layer(project_uuid, layer_id)
    """
    
    def __init__(self, connection, cursor=None):
        """
        Initialize HistoryRepository.
        
        Args:
            connection: Database connection (sqlite3 or psycopg2)
            cursor: Optional database cursor (created if not provided)
        """
        self._conn = connection
        self._cursor = cursor if cursor else connection.cursor()
        self._is_external_cursor = cursor is not None
    
    def insert(
        self,
        project_uuid: str,
        layer_id: str,
        subset_string: str,
        seq_order: int,
        source_layer_id: str = ''
    ) -> Optional[str]:
        """
        Insert a new history entry.
        
        Args:
            project_uuid: Project UUID
            layer_id: QGIS layer ID
            subset_string: SQL subset string
            seq_order: Sequence order
            source_layer_id: Optional source layer ID
            
        Returns:
            str: The generated entry UUID, or None on failure
        """
        entry_id = str(uuid.uuid4())
        
        # Escape single quotes in subset string
        safe_subset = subset_string.replace("'", "''") if subset_string else ''
        
        try:
            self._cursor.execute(
                f"""INSERT INTO fm_subset_history 
                    VALUES('{entry_id}', datetime(), '{project_uuid}', '{layer_id}', 
                           '{source_layer_id}', {seq_order}, '{safe_subset}');"""
            )
            self._conn.commit()
            logger.debug(f"Inserted history entry {entry_id} for layer {layer_id}")
            return entry_id
            
        except Exception as e:
            logger.error(f"Failed to insert history entry: {e}")
            return None
    
    def delete_for_layer(
        self,
        project_uuid: str,
        layer_id: str
    ) -> int:
        """
        Delete all history entries for a layer.
        
        Used by reset action to clear filter history.
        
        Args:
            project_uuid: Project UUID
            layer_id: QGIS layer ID
            
        Returns:
            int: Number of deleted rows
        """
        try:
            self._cursor.execute(
                f"""DELETE FROM fm_subset_history 
                    WHERE fk_project = '{project_uuid}' AND layer_id = '{layer_id}';"""
            )
            self._conn.commit()
            deleted = self._cursor.rowcount
            logger.debug(f"Deleted {deleted} history entries for layer {layer_id}")
            return deleted
            
        except Exception as e:
            logger.error(f"Failed to delete history for layer {layer_id}: {e}")
            return 0
    
    def delete_entry(
        self,
        project_uuid: str,
        layer_id: str,
        entry_id: str
    ) -> bool:
        """
        Delete a specific history entry.
        
        Used by unfilter action to remove the last entry.
        
        Args:
            project_uuid: Project UUID
            layer_id: QGIS layer ID
            entry_id: Specific entry UUID to delete
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            self._cursor.execute(
                f"""DELETE FROM fm_subset_history 
                    WHERE fk_project = '{project_uuid}' 
                      AND layer_id = '{layer_id}' 
                      AND id = '{entry_id}';"""
            )
            self._conn.commit()
            deleted = self._cursor.rowcount > 0
            if deleted:
                logger.debug(f"Deleted history entry {entry_id}")
            return deleted
            
        except Exception as e:
            logger.error(f"Failed to delete history entry {entry_id}: {e}")
            return False
    
    def get_last_entry(
        self,
        project_uuid: str,
        layer_id: str
    ) -> Optional[HistoryEntry]:
        """
        Get the most recent history entry for a layer.
        
        Args:
            project_uuid: Project UUID
            layer_id: QGIS layer ID
            
        Returns:
            HistoryEntry or None if no history exists
        """
        try:
            self._cursor.execute(
                f"""SELECT * FROM fm_subset_history 
                    WHERE fk_project = '{project_uuid}' AND layer_id = '{layer_id}' 
                    ORDER BY seq_order DESC LIMIT 1;"""
            )
            row = self._cursor.fetchone()
            
            if row:
                return HistoryEntry.from_row(row)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get last history entry: {e}")
            return None
    
    def get_last_subset_info(
        self,
        project_uuid: str,
        layer_id: str
    ) -> Tuple[Optional[str], int, Optional[str]]:
        """
        Get the last subset ID, sequence order, and subset string.
        
        Convenience method for common pattern used in filter actions.
        
        Args:
            project_uuid: Project UUID
            layer_id: QGIS layer ID
            
        Returns:
            Tuple of (last_subset_id, last_seq_order, subset_string)
        """
        entry = self.get_last_entry(project_uuid, layer_id)
        
        if entry:
            return entry.id, entry.seq_order, entry.subset_string
        return None, 0, None
    
    def get_history(
        self,
        project_uuid: str,
        layer_id: str,
        limit: int = 100
    ) -> List[HistoryEntry]:
        """
        Get history entries for a layer.
        
        Args:
            project_uuid: Project UUID
            layer_id: QGIS layer ID
            limit: Maximum number of entries to return
            
        Returns:
            List of HistoryEntry, ordered by seq_order DESC
        """
        try:
            self._cursor.execute(
                f"""SELECT * FROM fm_subset_history 
                    WHERE fk_project = '{project_uuid}' AND layer_id = '{layer_id}' 
                    ORDER BY seq_order DESC LIMIT {limit};"""
            )
            rows = self._cursor.fetchall()
            return [HistoryEntry.from_row(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return []
    
    def get_entry_count(
        self,
        project_uuid: str,
        layer_id: str
    ) -> int:
        """
        Get the number of history entries for a layer.
        
        Args:
            project_uuid: Project UUID
            layer_id: QGIS layer ID
            
        Returns:
            int: Number of history entries
        """
        try:
            self._cursor.execute(
                f"""SELECT COUNT(*) FROM fm_subset_history 
                    WHERE fk_project = '{project_uuid}' AND layer_id = '{layer_id}';"""
            )
            result = self._cursor.fetchone()
            return result[0] if result else 0
            
        except Exception as e:
            logger.error(f"Failed to get entry count: {e}")
            return 0
    
    def close(self):
        """Close cursor if it was created internally."""
        if not self._is_external_cursor and self._cursor:
            try:
                self._cursor.close()
            except Exception:
                pass


def create_history_repository(connection, cursor=None) -> HistoryRepository:
    """
    Factory function to create a HistoryRepository.
    
    Args:
        connection: Database connection
        cursor: Optional cursor
        
    Returns:
        HistoryRepository instance
    """
    return HistoryRepository(connection, cursor)

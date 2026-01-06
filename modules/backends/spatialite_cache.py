"""
FilterMate Spatialite Cache Database Module

v2.8.11: New module for persistent filter result caching.

This module provides a Spatialite-based caching system for filter results,
enabling efficient multi-step filtering similar to PostgreSQL's materialized views.

The cache database is stored in the FilterMate plugin directory alongside
config.json and history.db.

Key features:
- Persistent FID cache for each layer's filter results
- Multi-step filtering via FID intersection
- Automatic cleanup of stale cache entries
- Thread-safe operations with proper locking
- Support for both GeoPackage and native Spatialite layers

Architecture:
    filtermate_cache.db (Spatialite)
    └── filter_cache (table)
        ├── id: Auto-increment primary key
        ├── layer_id: QGIS layer ID
        ├── layer_source: Layer source path/connection
        ├── cache_key: Hash of filter parameters
        ├── fids: Comma-separated list of matching FIDs
        ├── fid_count: Number of FIDs in cache
        ├── created_at: Timestamp of cache creation
        ├── expires_at: Timestamp when cache expires
        └── metadata: JSON with additional info

Usage:
    from modules.backends.spatialite_cache import SpatialiteCacheDB
    
    cache = SpatialiteCacheDB()
    cache.store_filter_result(layer_id, source_path, fids, cache_key)
    cached_fids = cache.get_cached_fids(layer_id, cache_key)
"""

import os
import sqlite3
import json
import hashlib
import time
import threading
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Set, Tuple, Any
from contextlib import contextmanager

from qgis.core import QgsMessageLog, Qgis, QgsVectorLayer

# Import config to get plugin directory
try:
    from config.config import ENV_VARS
except ImportError:
    ENV_VARS = {}


# =============================================================================
# Constants
# =============================================================================

CACHE_DB_NAME = "filtermate_cache.db"
CACHE_TABLE_NAME = "filter_cache"
CACHE_DEFAULT_TTL_HOURS = 24  # Default cache time-to-live
CACHE_MAX_ENTRIES = 1000  # Maximum cache entries before cleanup
CACHE_CLEANUP_THRESHOLD = 500  # Cleanup when more than this many expired entries


# =============================================================================
# Utility Functions
# =============================================================================

def _get_cache_db_path() -> str:
    """
    Get the path to the FilterMate cache database.
    
    Returns:
        str: Absolute path to filtermate_cache.db
    """
    if "PLUGIN_CONFIG_DIRECTORY" in ENV_VARS:
        plugin_dir = ENV_VARS["PLUGIN_CONFIG_DIRECTORY"]
    else:
        # Fallback: use QGIS profile directory
        from qgis.core import QgsApplication
        plugin_dir = os.path.join(
            QgsApplication.qgisSettingsDirPath(),
            "FilterMate"
        )
    
    # Ensure directory exists
    if not os.path.exists(plugin_dir):
        os.makedirs(plugin_dir, exist_ok=True)
    
    return os.path.join(plugin_dir, CACHE_DB_NAME)


def _compute_cache_key(
    layer_id: str,
    source_geom_hash: str,
    predicates: List[str],
    buffer_value: float = 0.0,
    use_centroids: bool = False
) -> str:
    """
    Compute a unique cache key for filter parameters.
    
    Args:
        layer_id: QGIS layer ID
        source_geom_hash: Hash of source geometry WKT
        predicates: List of spatial predicates
        buffer_value: Buffer distance in meters
        use_centroids: Whether centroids are used
    
    Returns:
        str: SHA256 hash of filter parameters
    """
    key_data = {
        "layer_id": layer_id,
        "source_geom_hash": source_geom_hash,
        "predicates": sorted(predicates),
        "buffer_value": buffer_value,
        "use_centroids": use_centroids
    }
    key_str = json.dumps(key_data, sort_keys=True)
    return hashlib.sha256(key_str.encode()).hexdigest()[:32]


def _hash_geometry(wkt: str, precision: int = 1) -> str:
    """
    Create a hash of geometry WKT with reduced precision for cache matching.
    
    This allows cache hits even when geometry coordinates have minor differences.
    
    Args:
        wkt: WKT string
        precision: Decimal places to round coordinates
    
    Returns:
        str: SHA256 hash of normalized WKT
    """
    if not wkt:
        return "empty"
    
    # Round coordinates for cache stability
    import re
    
    def round_coord(match):
        num = float(match.group(0))
        return str(round(num, precision))
    
    # Round all numbers in WKT
    normalized = re.sub(r'-?\d+\.?\d*', round_coord, wkt)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


# =============================================================================
# Main Cache Database Class
# =============================================================================

class SpatialiteCacheDB:
    """
    Spatialite-based cache for FilterMate filter results.
    
    This class provides persistent caching of filter FID results,
    enabling efficient multi-step filtering.
    
    Thread-safe with connection pooling and proper locking.
    """
    
    # Class-level lock for thread safety
    _lock = threading.Lock()
    _instance = None
    
    def __new__(cls):
        """Singleton pattern for cache database."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the cache database."""
        if self._initialized:
            return
        
        self.db_path = _get_cache_db_path()
        self._init_database()
        self._initialized = True
        
        QgsMessageLog.logMessage(
            f"SpatialiteCacheDB initialized at: {self.db_path}",
            "FilterMate", Qgis.Info  # DEBUG
        )
    
    def _init_database(self):
        """Create cache database and tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create main cache table
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {CACHE_TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    layer_id TEXT NOT NULL,
                    layer_source TEXT NOT NULL,
                    layer_name TEXT,
                    cache_key TEXT NOT NULL,
                    fids TEXT NOT NULL,
                    fid_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    step_number INTEGER DEFAULT 1,
                    source_geom_hash TEXT,
                    predicates TEXT,
                    buffer_value REAL DEFAULT 0,
                    metadata TEXT,
                    UNIQUE(layer_id, cache_key)
                )
            ''')
            
            # Create index for fast lookups
            cursor.execute(f'''
                CREATE INDEX IF NOT EXISTS idx_cache_layer_key 
                ON {CACHE_TABLE_NAME} (layer_id, cache_key)
            ''')
            
            cursor.execute(f'''
                CREATE INDEX IF NOT EXISTS idx_cache_expires 
                ON {CACHE_TABLE_NAME} (expires_at)
            ''')
            
            # Create multi-step tracking table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS filter_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    layer_id TEXT NOT NULL,
                    step_number INTEGER NOT NULL,
                    cache_key TEXT NOT NULL,
                    previous_fid_count INTEGER,
                    new_fid_count INTEGER,
                    created_at TEXT NOT NULL,
                    UNIQUE(session_id, layer_id, step_number)
                )
            ''')
            
            # Create session table for tracking filter sessions
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS filter_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL UNIQUE,
                    source_layer_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    last_step_at TEXT,
                    step_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1
                )
            ''')
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """
        Get a thread-safe database connection.
        
        Yields:
            sqlite3.Connection: Database connection
        """
        conn = None
        try:
            conn = sqlite3.connect(
                self.db_path,
                timeout=30,
                check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            yield conn
        finally:
            if conn:
                conn.close()
    
    # =========================================================================
    # Cache Operations
    # =========================================================================
    
    def store_filter_result(
        self,
        layer: QgsVectorLayer,
        fids: List[int],
        source_geom_wkt: str,
        predicates: List[str],
        buffer_value: float = 0.0,
        use_centroids: bool = False,
        ttl_hours: int = CACHE_DEFAULT_TTL_HOURS,
        step_number: int = 1,
        session_id: Optional[str] = None
    ) -> str:
        """
        Store filter results in cache.
        
        Args:
            layer: Filtered layer
            fids: List of matching FIDs
            source_geom_wkt: Source geometry WKT
            predicates: Spatial predicates used
            buffer_value: Buffer distance
            use_centroids: Whether centroids were used
            ttl_hours: Cache time-to-live in hours
            step_number: Multi-step filter step number
            session_id: Session ID for multi-step tracking
        
        Returns:
            str: Cache key for this result
        """
        with self._lock:
            layer_id = layer.id()
            layer_source = layer.source()
            layer_name = layer.name()
            
            # Compute cache key
            source_geom_hash = _hash_geometry(source_geom_wkt)
            cache_key = _compute_cache_key(
                layer_id, source_geom_hash, predicates, buffer_value, use_centroids
            )
            
            # Prepare data
            now = datetime.now(timezone.utc)
            expires = now + timedelta(hours=ttl_hours)
            fids_str = ",".join(str(f) for f in sorted(fids))
            predicates_str = json.dumps(predicates)
            
            metadata = {
                "use_centroids": use_centroids,
                "session_id": session_id,
                "created_by": "spatialite_backend"
            }
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Upsert cache entry
                cursor.execute(f'''
                    INSERT OR REPLACE INTO {CACHE_TABLE_NAME} (
                        layer_id, layer_source, layer_name, cache_key,
                        fids, fid_count, created_at, expires_at,
                        step_number, source_geom_hash, predicates,
                        buffer_value, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    layer_id, layer_source, layer_name, cache_key,
                    fids_str, len(fids), now.isoformat(), expires.isoformat(),
                    step_number, source_geom_hash, predicates_str,
                    buffer_value, json.dumps(metadata)
                ))
                
                # Track step if session is provided
                if session_id:
                    cursor.execute('''
                        INSERT OR REPLACE INTO filter_steps (
                            session_id, layer_id, step_number, cache_key,
                            new_fid_count, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        session_id, layer_id, step_number, cache_key,
                        len(fids), now.isoformat()
                    ))
                
                conn.commit()
            
            QgsMessageLog.logMessage(
                f"Cache stored: {layer_name} → {len(fids)} FIDs (step {step_number}, key={cache_key[:8]})",
                "FilterMate", Qgis.Info  # DEBUG
            )
            
            return cache_key
    
    def get_cached_fids(
        self,
        layer: QgsVectorLayer,
        source_geom_wkt: str,
        predicates: List[str],
        buffer_value: float = 0.0,
        use_centroids: bool = False
    ) -> Optional[Set[int]]:
        """
        Get cached FIDs for a layer with given filter parameters.
        
        Args:
            layer: Layer to get cache for
            source_geom_wkt: Source geometry WKT
            predicates: Spatial predicates
            buffer_value: Buffer distance
            use_centroids: Whether centroids are used
        
        Returns:
            Set of FIDs if cache hit, None if cache miss
        """
        layer_id = layer.id()
        source_geom_hash = _hash_geometry(source_geom_wkt)
        cache_key = _compute_cache_key(
            layer_id, source_geom_hash, predicates, buffer_value, use_centroids
        )
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute(f'''
                SELECT fids, fid_count FROM {CACHE_TABLE_NAME}
                WHERE layer_id = ? AND cache_key = ? AND expires_at > ?
            ''', (layer_id, cache_key, now))
            
            row = cursor.fetchone()
            if row:
                fids_str = row['fids']
                fids = set(int(f) for f in fids_str.split(',') if f)
                QgsMessageLog.logMessage(
                    f"Cache HIT: {layer.name()} → {len(fids)} FIDs (key={cache_key[:8]})",
                    "FilterMate", Qgis.Info
                )
                return fids
        
        return None
    
    def get_previous_fids(
        self, 
        layer: QgsVectorLayer,
        current_source_geom_wkt: Optional[str] = None
    ) -> Optional[Set[int]]:
        """
        Get the most recent cached FIDs for a layer (for multi-step filtering).
        
        v2.9.19: FIX - Only return previous FIDs if the source geometry hash matches.
        This prevents incorrect intersection when a new filter uses a different 
        source geometry (e.g., user draws a new polygon).
        
        Args:
            layer: Layer to get previous FIDs for
            current_source_geom_wkt: Current source geometry WKT. If provided,
                only return FIDs if the cached source_geom_hash matches.
                If None, returns FIDs regardless (backward compatible).
        
        Returns:
            Set of FIDs from most recent cache, None if no cache or geometry mismatch
        """
        layer_id = layer.id()
        
        # Compute current geometry hash if WKT provided
        current_geom_hash = None
        if current_source_geom_wkt:
            current_geom_hash = _hash_geometry(current_source_geom_wkt)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute(f'''
                SELECT fids, fid_count, step_number, source_geom_hash FROM {CACHE_TABLE_NAME}
                WHERE layer_id = ? AND expires_at > ?
                ORDER BY created_at DESC
                LIMIT 1
            ''', (layer_id, now))
            
            row = cursor.fetchone()
            if row:
                cached_geom_hash = row['source_geom_hash']
                
                # v2.9.19: If current geometry hash provided, check if it matches
                if current_geom_hash and cached_geom_hash:
                    if current_geom_hash != cached_geom_hash:
                        QgsMessageLog.logMessage(
                            f"Cache SKIP: {layer.name()} → source geometry changed (hash mismatch)",
                            "FilterMate", Qgis.Info
                        )
                        return None  # Different source geometry, don't intersect
                
                fids_str = row['fids']
                fids = set(int(f) for f in fids_str.split(',') if f)
                step = row['step_number']
                QgsMessageLog.logMessage(
                    f"Previous FIDs: {layer.name()} → {len(fids)} FIDs (step {step})",
                    "FilterMate", Qgis.Info
                )
                return fids
        
        return None
    
    def intersect_with_previous(
        self,
        layer: QgsVectorLayer,
        new_fids: Set[int],
        current_source_geom_wkt: Optional[str] = None
    ) -> Tuple[Set[int], int]:
        """
        Intersect new FIDs with previously cached FIDs for multi-step filtering.
        
        v2.9.19: FIX - Only intersect if the source geometry is the same.
        This prevents incorrect intersection when the user applies a new filter
        with a different source geometry.
        
        Args:
            layer: Layer being filtered
            new_fids: New FIDs from current filter operation
            current_source_geom_wkt: Current source geometry WKT for hash comparison
        
        Returns:
            Tuple of (intersected FIDs, previous step number)
        """
        previous_fids = self.get_previous_fids(layer, current_source_geom_wkt)
        
        if previous_fids is not None:
            # Intersect with previous results
            intersected = new_fids & previous_fids
            
            # Get previous step number
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f'''
                    SELECT step_number FROM {CACHE_TABLE_NAME}
                    WHERE layer_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                ''', (layer.id(),))
                row = cursor.fetchone()
                prev_step = row['step_number'] if row else 0
            
            QgsMessageLog.logMessage(
                f"Multi-step intersection: {len(previous_fids)} ∩ {len(new_fids)} = {len(intersected)}",
                "FilterMate", Qgis.Info
            )
            
            return intersected, prev_step + 1
        
        return new_fids, 1
    
    # =========================================================================
    # Session Management
    # =========================================================================
    
    def start_session(self, source_layer_id: str) -> str:
        """
        Start a new filter session for multi-step tracking.
        
        Args:
            source_layer_id: ID of the source layer
        
        Returns:
            str: New session ID
        """
        import uuid
        session_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO filter_sessions (
                    session_id, source_layer_id, started_at, step_count
                ) VALUES (?, ?, ?, 0)
            ''', (session_id, source_layer_id, now))
            conn.commit()
        
        return session_id
    
    def end_session(self, session_id: str):
        """Mark a filter session as inactive."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE filter_sessions SET is_active = 0 WHERE session_id = ?
            ''', (session_id,))
            conn.commit()
    
    # =========================================================================
    # Cleanup Operations
    # =========================================================================
    
    def cleanup_expired(self) -> int:
        """
        Remove expired cache entries.
        
        Returns:
            int: Number of entries removed
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                now = datetime.now(timezone.utc).isoformat()
                cursor.execute(f'''
                    DELETE FROM {CACHE_TABLE_NAME} WHERE expires_at < ?
                ''', (now,))
                
                deleted = cursor.rowcount
                conn.commit()
                
                if deleted > 0:
                    QgsMessageLog.logMessage(
                        f"Cache cleanup: removed {deleted} expired entries",
                        "FilterMate", Qgis.Info
                    )
                
                return deleted
    
    def clear_layer_cache(self, layer_id: str) -> int:
        """
        Clear all cache entries for a specific layer.
        
        Args:
            layer_id: QGIS layer ID
        
        Returns:
            int: Number of entries removed
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f'''
                    DELETE FROM {CACHE_TABLE_NAME} WHERE layer_id = ?
                ''', (layer_id,))
                deleted = cursor.rowcount
                conn.commit()
                return deleted
    
    def clear_all_cache(self) -> int:
        """
        Clear all cache entries.
        
        Returns:
            int: Number of entries removed
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f'DELETE FROM {CACHE_TABLE_NAME}')
                deleted = cursor.rowcount
                cursor.execute('DELETE FROM filter_steps')
                cursor.execute('DELETE FROM filter_sessions')
                conn.commit()
                
                QgsMessageLog.logMessage(
                    f"Cache cleared: removed {deleted} entries",
                    "FilterMate", Qgis.Info
                )
                
                return deleted
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            dict: Cache statistics
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(f'SELECT COUNT(*) as count FROM {CACHE_TABLE_NAME}')
            total_entries = cursor.fetchone()['count']
            
            cursor.execute(f'''
                SELECT SUM(fid_count) as total_fids FROM {CACHE_TABLE_NAME}
            ''')
            total_fids = cursor.fetchone()['total_fids'] or 0
            
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute(f'''
                SELECT COUNT(*) as count FROM {CACHE_TABLE_NAME}
                WHERE expires_at < ?
            ''', (now,))
            expired_entries = cursor.fetchone()['count']
            
            # Get database file size
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            
            return {
                "db_path": self.db_path,
                "total_entries": total_entries,
                "expired_entries": expired_entries,
                "total_fids_cached": total_fids,
                "db_size_bytes": db_size,
                "db_size_mb": round(db_size / (1024 * 1024), 2)
            }


# =============================================================================
# Module-level convenience functions
# =============================================================================

_cache_instance: Optional[SpatialiteCacheDB] = None


def get_cache() -> SpatialiteCacheDB:
    """Get the singleton cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = SpatialiteCacheDB()
    return _cache_instance


def store_filter_fids(
    layer: QgsVectorLayer,
    fids: List[int],
    source_geom_wkt: str,
    predicates: List[str],
    buffer_value: float = 0.0,
    use_centroids: bool = False,
    step_number: int = 1
) -> str:
    """Convenience function to store filter results."""
    return get_cache().store_filter_result(
        layer, fids, source_geom_wkt, predicates,
        buffer_value, use_centroids, step_number=step_number
    )


def get_previous_filter_fids(
    layer: QgsVectorLayer,
    current_source_geom_wkt: Optional[str] = None
) -> Optional[Set[int]]:
    """
    Convenience function to get previous filter FIDs.
    
    v2.9.19: Added current_source_geom_wkt parameter to prevent wrong cache intersection.
    """
    return get_cache().get_previous_fids(layer, current_source_geom_wkt)


def intersect_filter_fids(
    layer: QgsVectorLayer,
    new_fids: Set[int],
    current_source_geom_wkt: Optional[str] = None
) -> Tuple[Set[int], int]:
    """
    Convenience function to intersect with previous FIDs.
    
    v2.9.19: Added current_source_geom_wkt parameter to prevent wrong cache intersection.
    """
    return get_cache().intersect_with_previous(layer, new_fids, current_source_geom_wkt)


def clear_cache():
    """Convenience function to clear all cache."""
    return get_cache().clear_all_cache()


def cleanup_cache():
    """Convenience function to cleanup expired cache."""
    return get_cache().cleanup_expired()

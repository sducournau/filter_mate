# -*- coding: utf-8 -*-
"""
Materialized View Registry for PostgreSQL Backend

Tracks and manages materialized views created by FilterMate.
Provides automatic cleanup of old/orphaned views.

v2.4.0 - Backend Optimization
"""

import threading
import time
from typing import Dict, Optional, Tuple, List, Set
from dataclasses import dataclass, field
from collections import OrderedDict

from ..logging_config import get_tasks_logger
from ..constants import MV_MAX_AGE_SECONDS, MV_CLEANUP_INTERVAL, MV_PREFIX

logger = get_tasks_logger()


@dataclass
class MVEntry:
    """Entry for a tracked materialized view."""
    mv_name: str
    schema: str
    layer_id: str
    layer_name: str
    creation_time: float
    feature_count: int = 0
    last_used: float = field(default_factory=time.time)
    
    @property
    def age_seconds(self) -> float:
        """Age of the MV in seconds."""
        return time.time() - self.creation_time
    
    @property
    def idle_seconds(self) -> float:
        """Time since last use in seconds."""
        return time.time() - self.last_used
    
    @property
    def full_name(self) -> str:
        """Full qualified MV name."""
        return f'"{self.schema}"."{self.mv_name}"'


class MVRegistry:
    """
    Registry for tracking materialized views created by FilterMate.
    
    Features:
    - Thread-safe registration and lookup
    - Automatic cleanup of old MVs
    - Per-layer MV tracking
    - Statistics and monitoring
    
    Usage:
        registry = MVRegistry.get_instance()
        registry.register("mv_abc123", "public", "layer_id_xyz", "My Layer", 5000)
        
        # Later, cleanup old MVs
        registry.cleanup_old()
        
        # Or cleanup for a specific layer
        registry.cleanup_for_layer("layer_id_xyz")
    """
    
    _instance: Optional['MVRegistry'] = None
    _lock = threading.Lock()
    
    def __init__(self):
        """Initialize the registry."""
        self._mvs: OrderedDict[str, MVEntry] = OrderedDict()
        self._layer_mvs: Dict[str, Set[str]] = {}  # layer_id -> set of mv_names
        self._registry_lock = threading.RLock()
        self._last_cleanup: float = 0
        self._total_created: int = 0
        self._total_cleaned: int = 0
    
    @classmethod
    def get_instance(cls) -> 'MVRegistry':
        """Get singleton instance of MVRegistry."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = MVRegistry()
                    logger.info("✓ MVRegistry initialized")
        return cls._instance
    
    def register(
        self,
        mv_name: str,
        schema: str,
        layer_id: str,
        layer_name: str,
        feature_count: int = 0
    ) -> MVEntry:
        """
        Register a new materialized view.
        
        Args:
            mv_name: Name of the materialized view
            schema: Database schema
            layer_id: QGIS layer ID
            layer_name: Human-readable layer name
            feature_count: Number of features in the MV
            
        Returns:
            MVEntry for the registered view
        """
        with self._registry_lock:
            entry = MVEntry(
                mv_name=mv_name,
                schema=schema,
                layer_id=layer_id,
                layer_name=layer_name,
                creation_time=time.time(),
                feature_count=feature_count
            )
            
            self._mvs[mv_name] = entry
            
            # Track by layer
            if layer_id not in self._layer_mvs:
                self._layer_mvs[layer_id] = set()
            self._layer_mvs[layer_id].add(mv_name)
            
            self._total_created += 1
            
            logger.debug(f"📝 MV registered: {entry.full_name} for layer '{layer_name}'")
            
            # Check if cleanup is needed
            self._maybe_cleanup()
            
            return entry
    
    def unregister(self, mv_name: str) -> Optional[MVEntry]:
        """
        Unregister a materialized view.
        
        Args:
            mv_name: Name of the MV to unregister
            
        Returns:
            The removed entry, or None if not found
        """
        with self._registry_lock:
            entry = self._mvs.pop(mv_name, None)
            
            if entry:
                # Remove from layer tracking
                if entry.layer_id in self._layer_mvs:
                    self._layer_mvs[entry.layer_id].discard(mv_name)
                    if not self._layer_mvs[entry.layer_id]:
                        del self._layer_mvs[entry.layer_id]
                
                logger.debug(f"📝 MV unregistered: {entry.full_name}")
            
            return entry
    
    def get(self, mv_name: str) -> Optional[MVEntry]:
        """Get entry for a MV name."""
        with self._registry_lock:
            entry = self._mvs.get(mv_name)
            if entry:
                entry.last_used = time.time()
            return entry
    
    def get_for_layer(self, layer_id: str) -> List[MVEntry]:
        """Get all MVs for a layer."""
        with self._registry_lock:
            mv_names = self._layer_mvs.get(layer_id, set())
            return [self._mvs[name] for name in mv_names if name in self._mvs]
    
    def _maybe_cleanup(self):
        """Check if cleanup should run based on interval."""
        now = time.time()
        if now - self._last_cleanup >= MV_CLEANUP_INTERVAL:
            self._last_cleanup = now
            # Run cleanup in background thread
            cleanup_thread = threading.Thread(
                target=self._background_cleanup,
                daemon=True
            )
            cleanup_thread.start()
    
    def _background_cleanup(self):
        """Background cleanup task."""
        try:
            cleaned = self.cleanup_old(max_age=MV_MAX_AGE_SECONDS)
            if cleaned:
                logger.info(f"🧹 Background cleanup: removed {len(cleaned)} old MV(s)")
        except Exception as e:
            logger.warning(f"Background cleanup error: {e}")
    
    def cleanup_old(self, max_age: int = None) -> List[MVEntry]:
        """
        Cleanup MVs older than max_age seconds.
        
        Args:
            max_age: Maximum age in seconds (default: MV_MAX_AGE_SECONDS)
            
        Returns:
            List of entries that were marked for cleanup
        """
        if max_age is None:
            max_age = MV_MAX_AGE_SECONDS
        
        entries_to_cleanup: List[MVEntry] = []
        
        with self._registry_lock:
            now = time.time()
            
            for mv_name, entry in list(self._mvs.items()):
                if entry.age_seconds > max_age:
                    entries_to_cleanup.append(entry)
                    self.unregister(mv_name)
        
        # Actually drop the MVs from database
        if entries_to_cleanup:
            self._drop_mvs(entries_to_cleanup)
            self._total_cleaned += len(entries_to_cleanup)
        
        return entries_to_cleanup
    
    def cleanup_for_layer(self, layer_id: str) -> List[MVEntry]:
        """
        Cleanup all MVs for a specific layer.
        
        Args:
            layer_id: QGIS layer ID
            
        Returns:
            List of entries that were cleaned up
        """
        entries = self.get_for_layer(layer_id)
        
        for entry in entries:
            self.unregister(entry.mv_name)
        
        if entries:
            self._drop_mvs(entries)
            self._total_cleaned += len(entries)
            logger.info(f"🧹 Cleaned {len(entries)} MV(s) for layer {layer_id}")
        
        return entries
    
    def cleanup_all(self) -> List[MVEntry]:
        """
        Cleanup all registered MVs.
        
        Returns:
            List of all cleaned entries
        """
        with self._registry_lock:
            entries = list(self._mvs.values())
            self._mvs.clear()
            self._layer_mvs.clear()
        
        if entries:
            self._drop_mvs(entries)
            self._total_cleaned += len(entries)
            logger.info(f"🧹 Cleaned all {len(entries)} MV(s)")
        
        return entries
    
    def _drop_mvs(self, entries: List[MVEntry]):
        """
        Drop materialized views from database.
        
        Groups MVs by connection and drops in batch.
        """
        from ..appUtils import POSTGRESQL_AVAILABLE
        
        if not POSTGRESQL_AVAILABLE:
            logger.warning("PostgreSQL not available - cannot drop MVs")
            return
        
        # Group by schema for batch dropping
        by_schema: Dict[str, List[str]] = {}
        for entry in entries:
            if entry.schema not in by_schema:
                by_schema[entry.schema] = []
            by_schema[entry.schema].append(entry.mv_name)
        
        # Try to get a connection and drop
        try:
            from ..appUtils import get_datasource_connexion_from_layer
            from qgis.core import QgsProject
            
            # Find any PostgreSQL layer to get connection
            project = QgsProject.instance()
            pg_layer = None
            for layer_id, layer in project.mapLayers().items():
                if hasattr(layer, 'providerType') and layer.providerType() == 'postgres':
                    pg_layer = layer
                    break
            
            if not pg_layer:
                logger.warning("No PostgreSQL layer found - MVs will be orphaned")
                return
            
            conn, source_uri = get_datasource_connexion_from_layer(pg_layer)
            if not conn:
                logger.warning("Cannot get PostgreSQL connection for MV cleanup")
                return
            
            cursor = conn.cursor()
            
            for schema, mv_names in by_schema.items():
                for mv_name in mv_names:
                    try:
                        cursor.execute(
                            f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."{mv_name}" CASCADE;'
                        )
                        logger.debug(f"✓ Dropped MV: {schema}.{mv_name}")
                    except Exception as e:
                        logger.warning(f"Failed to drop MV {schema}.{mv_name}: {e}")
                
                conn.commit()
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error during MV cleanup: {e}")
    
    def get_stats(self) -> Dict:
        """Get registry statistics."""
        with self._registry_lock:
            return {
                'active_mvs': len(self._mvs),
                'layers_with_mvs': len(self._layer_mvs),
                'total_created': self._total_created,
                'total_cleaned': self._total_cleaned,
                'oldest_mv_age': max(
                    (e.age_seconds for e in self._mvs.values()),
                    default=0
                )
            }
    
    def __len__(self) -> int:
        """Number of registered MVs."""
        return len(self._mvs)
    
    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"MVRegistry(active={stats['active_mvs']}, "
            f"created={stats['total_created']}, "
            f"cleaned={stats['total_cleaned']})"
        )


# Convenience function
def get_mv_registry() -> MVRegistry:
    """Get the global MV registry instance."""
    return MVRegistry.get_instance()

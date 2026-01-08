# -*- coding: utf-8 -*-
"""
Spatial Index Manager for OGR Backend

Provides automatic spatial index creation and management for
file-based formats (Shapefile, GeoPackage, etc.).

v2.4.0 - Backend Optimization
"""

import os
import threading
import time
from typing import Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from qgis.core import QgsVectorLayer
from qgis import processing

from ..logging_config import get_tasks_logger
from ..constants import SPATIAL_INDEX_AUTO_CREATE, SPATIAL_INDEX_MIN_FEATURES

logger = get_tasks_logger()


@dataclass
class IndexInfo:
    """Information about a spatial index."""
    file_path: str
    index_type: str  # 'qix', 'sbn', 'rtree', etc.
    exists: bool
    created_at: Optional[float] = None
    feature_count: int = 0
    
    @property
    def index_path(self) -> Optional[str]:
        """Path to the index file (for file-based indexes)."""
        if self.index_type == 'qix':
            return str(Path(self.file_path).with_suffix('.qix'))
        elif self.index_type == 'sbn':
            return str(Path(self.file_path).with_suffix('.sbn'))
        return None


class SpatialIndexManager:
    """
    Manager for spatial indexes on file-based layers.
    
    Features:
    - Auto-detection of index format by file type
    - Automatic index creation when missing
    - Index status tracking
    - Thread-safe operations
    
    Supported formats:
    - Shapefile: .qix (QGIS QuadTree Index)
    - GeoPackage: SQLite R-tree
    - GeoJSON: Memory-based (via QGIS)
    
    Usage:
        manager = SpatialIndexManager.get_instance()
        
        # Ensure index exists
        manager.ensure_index(layer)
        
        # Check if index exists
        has_index = manager.has_index(layer)
        
        # Get index info
        info = manager.get_index_info(layer)
    """
    
    _instance: Optional['SpatialIndexManager'] = None
    _lock = threading.Lock()
    
    # Supported file extensions and their index types
    INDEX_TYPES = {
        '.shp': 'qix',
        '.gpkg': 'rtree',
        '.sqlite': 'rtree',
        '.geojson': 'memory',
        '.json': 'memory',
    }
    
    def __init__(self):
        """Initialize the spatial index manager."""
        self._index_cache: Dict[str, IndexInfo] = {}
        self._pending_creation: Set[str] = set()
        self._manager_lock = threading.RLock()
        self._creation_errors: Dict[str, str] = {}
        
        # Statistics
        self._indexes_created: int = 0
        self._indexes_checked: int = 0
    
    @classmethod
    def get_instance(cls) -> 'SpatialIndexManager':
        """Get singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = SpatialIndexManager()
                    logger.info("✓ SpatialIndexManager initialized")
        return cls._instance
    
    def _get_source_path(self, layer: QgsVectorLayer) -> Optional[str]:
        """Extract file path from layer source."""
        if not layer or not layer.isValid():
            return None
        
        source = layer.source()
        
        # Handle pipe-separated format (GeoPackage, etc.)
        if '|' in source:
            source = source.split('|')[0]
        
        # Remove any query parameters
        if '?' in source:
            source = source.split('?')[0]
        
        return source if os.path.isfile(source) else None
    
    def _get_index_type(self, file_path: str) -> Optional[str]:
        """Determine index type based on file extension."""
        ext = Path(file_path).suffix.lower()
        return self.INDEX_TYPES.get(ext)
    
    def has_index(self, layer: QgsVectorLayer) -> bool:
        """
        Check if layer has a spatial index.
        
        Args:
            layer: Layer to check
            
        Returns:
            True if spatial index exists
        """
        # First check QGIS built-in method
        if layer.hasSpatialIndex():
            return True
        
        # Check file-based indexes
        file_path = self._get_source_path(layer)
        if not file_path:
            return False
        
        index_type = self._get_index_type(file_path)
        if not index_type:
            return False
        
        # Check for index file
        if index_type == 'qix':
            qix_path = str(Path(file_path).with_suffix('.qix'))
            return os.path.isfile(qix_path)
        elif index_type == 'sbn':
            sbn_path = str(Path(file_path).with_suffix('.sbn'))
            return os.path.isfile(sbn_path)
        elif index_type == 'rtree':
            # For GeoPackage/SQLite, check via SQL
            return self._check_geopackage_rtree(layer)
        
        return False
    
    def _check_geopackage_rtree(self, layer: QgsVectorLayer) -> bool:
        """Check if GeoPackage has R-tree index."""
        try:
            import sqlite3
            
            file_path = self._get_source_path(layer)
            if not file_path:
                return False
            
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            
            # Get table name
            source = layer.source()
            table_name = None
            if '|layername=' in source:
                table_name = source.split('|layername=')[1].split('|')[0]
            
            if not table_name:
                # Try from URI
                from qgis.core import QgsDataSourceUri
                uri = QgsDataSourceUri(source)
                table_name = uri.table()
            
            if not table_name:
                conn.close()
                return False
            
            # Check for rtree table
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ?",
                (f'rtree_{table_name}_%',)
            )
            result = cursor.fetchone()
            conn.close()
            
            return result is not None
            
        except Exception as e:
            logger.debug(f"Error checking GeoPackage rtree: {e}")
            return False
    
    def get_index_info(self, layer: QgsVectorLayer) -> Optional[IndexInfo]:
        """
        Get detailed index information for a layer.
        
        Args:
            layer: Layer to check
            
        Returns:
            IndexInfo or None
        """
        file_path = self._get_source_path(layer)
        if not file_path:
            return None
        
        self._indexes_checked += 1
        
        # Check cache first
        with self._manager_lock:
            if file_path in self._index_cache:
                return self._index_cache[file_path]
        
        index_type = self._get_index_type(file_path)
        if not index_type:
            return None
        
        exists = self.has_index(layer)
        
        # CRITICAL FIX v3.0.18: Protect against None/invalid feature count
        # featureCount() can return None if layer is invalid or -1 if unknown
        feature_count = layer.featureCount()
        if feature_count is None or feature_count < 0:
            feature_count = 0
        
        info = IndexInfo(
            file_path=file_path,
            index_type=index_type,
            exists=exists,
            feature_count=feature_count
        )
        
        # Cache the result
        with self._manager_lock:
            self._index_cache[file_path] = info
        
        return info
    
    def ensure_index(
        self,
        layer: QgsVectorLayer,
        force: bool = False
    ) -> bool:
        """
        Ensure spatial index exists for layer, creating if needed.
        
        Args:
            layer: Layer to index
            force: Force recreation even if exists
            
        Returns:
            True if index exists or was created
        """
        if not SPATIAL_INDEX_AUTO_CREATE and not force:
            return self.has_index(layer)
        
        if not force and self.has_index(layer):
            logger.debug(f"✓ Spatial index already exists for {layer.name()}")
            return True
        
        # Check minimum feature threshold
        # CRITICAL FIX v3.0.18: Protect against None/invalid feature count
        # featureCount() can return None if layer is invalid or -1 if unknown
        feature_count = layer.featureCount()
        if feature_count is None or feature_count < 0:
            feature_count = 0
        if feature_count < SPATIAL_INDEX_MIN_FEATURES and not force:
            logger.debug(
                f"Skipping index creation for {layer.name()} "
                f"({feature_count} < {SPATIAL_INDEX_MIN_FEATURES} features)"
            )
            return True
        
        file_path = self._get_source_path(layer)
        if not file_path:
            # Memory or virtual layer - use QGIS native
            return self._create_qgis_index(layer)
        
        # Check if already creating
        with self._manager_lock:
            if file_path in self._pending_creation:
                logger.debug(f"Index creation already in progress for {file_path}")
                return False
            self._pending_creation.add(file_path)
        
        try:
            index_type = self._get_index_type(file_path)
            
            if index_type == 'qix':
                result = self._create_qix_index(layer, file_path)
            elif index_type == 'rtree':
                result = self._create_rtree_index(layer, file_path)
            else:
                result = self._create_qgis_index(layer)
            
            if result:
                self._indexes_created += 1
                # Update cache
                with self._manager_lock:
                    if file_path in self._index_cache:
                        self._index_cache[file_path].exists = True
                        self._index_cache[file_path].created_at = time.time()
            
            return result
            
        finally:
            with self._manager_lock:
                self._pending_creation.discard(file_path)
    
    def _create_qix_index(self, layer: QgsVectorLayer, file_path: str) -> bool:
        """Create QIX index for Shapefile."""
        try:
            logger.info(f"🔨 Creating QIX spatial index for {layer.name()}...")
            
            result = processing.run("native:createspatialindex", {
                'INPUT': layer
            })
            
            # Verify index was created
            qix_path = str(Path(file_path).with_suffix('.qix'))
            if os.path.isfile(qix_path):
                logger.info(f"✓ QIX index created: {qix_path}")
                return True
            else:
                # Some versions create different format
                logger.info(f"✓ Spatial index created for {layer.name()}")
                return True
                
        except Exception as e:
            logger.warning(f"Failed to create QIX index: {e}")
            self._creation_errors[file_path] = str(e)
            return False
    
    def _create_rtree_index(self, layer: QgsVectorLayer, file_path: str) -> bool:
        """Create R-tree index for GeoPackage/SQLite."""
        try:
            import sqlite3
            
            logger.info(f"🔨 Creating R-tree spatial index for {layer.name()}...")
            
            # Get table and geometry column
            source = layer.source()
            table_name = None
            geom_col = layer.geometryColumn() or 'geom'
            
            if '|layername=' in source:
                table_name = source.split('|layername=')[1].split('|')[0]
            
            if not table_name:
                from qgis.core import QgsDataSourceUri
                uri = QgsDataSourceUri(source)
                table_name = uri.table()
            
            if not table_name:
                logger.warning("Could not determine table name for R-tree creation")
                return self._create_qgis_index(layer)
            
            conn = sqlite3.connect(file_path)
            conn.enable_load_extension(True)
            
            # Try to load spatialite extension
            try:
                conn.load_extension('mod_spatialite')
            except sqlite3.OperationalError:
                try:
                    conn.load_extension('mod_spatialite.dll')
                except sqlite3.OperationalError:
                    logger.debug("Spatialite extension not available, using fallback")
                    conn.close()
                    return self._create_qgis_index(layer)
            
            cursor = conn.cursor()
            
            # Check if it's a GeoPackage
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='gpkg_geometry_columns'"
            )
            is_geopackage = cursor.fetchone() is not None
            
            if is_geopackage:
                # GeoPackage R-tree creation
                cursor.execute(f"""
                    SELECT CreateSpatialIndex('{table_name}', '{geom_col}')
                """)
            else:
                # Spatialite R-tree creation
                cursor.execute(f"""
                    SELECT CreateSpatialIndex('{table_name}', '{geom_col}')
                """)
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"✓ R-tree index created for {table_name}")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to create R-tree index: {e}")
            self._creation_errors[file_path] = str(e)
            return self._create_qgis_index(layer)
    
    def _create_qgis_index(self, layer: QgsVectorLayer) -> bool:
        """Create spatial index using QGIS processing."""
        try:
            logger.info(f"🔨 Creating spatial index for {layer.name()} via QGIS...")
            
            result = processing.run("native:createspatialindex", {
                'INPUT': layer
            })
            
            logger.info(f"✓ Spatial index created for {layer.name()}")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to create spatial index: {e}")
            return False
    
    def invalidate_cache(self, file_path: str = None):
        """
        Invalidate index cache.
        
        Args:
            file_path: Specific file to invalidate, or None for all
        """
        with self._manager_lock:
            if file_path:
                self._index_cache.pop(file_path, None)
            else:
                self._index_cache.clear()
    
    def get_stats(self) -> Dict:
        """Get manager statistics."""
        with self._manager_lock:
            return {
                'cached_entries': len(self._index_cache),
                'indexes_created': self._indexes_created,
                'indexes_checked': self._indexes_checked,
                'pending_creations': len(self._pending_creation),
                'errors': len(self._creation_errors)
            }
    
    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"SpatialIndexManager(cached={stats['cached_entries']}, "
            f"created={stats['indexes_created']})"
        )


# Convenience function
def get_spatial_index_manager() -> SpatialIndexManager:
    """Get the global spatial index manager instance."""
    return SpatialIndexManager.get_instance()

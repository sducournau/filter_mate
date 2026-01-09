"""
BackendService - Backend Management Service.

Centralizes backend detection, selection, forcing, and validation logic.
Extracted from filter_mate_dockwidget.py as part of the God Class migration.

Story: MIG-075
Phase: 6 - God Class DockWidget Migration
Pattern: Strangler Fig - Gradual extraction
"""

import logging
from typing import Dict, List, Optional, Tuple, Any, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum, auto

try:
    from qgis.PyQt.QtCore import pyqtSignal, QObject
except ImportError:
    from PyQt5.QtCore import pyqtSignal, QObject

if TYPE_CHECKING:
    from qgis.core import QgsVectorLayer, QgsProject

logger = logging.getLogger(__name__)


class BackendType(Enum):
    """Available backend types."""
    POSTGRESQL = "postgresql"
    SPATIALITE = "spatialite"
    OGR = "ogr"
    AUTO = "auto"


@dataclass
class BackendInfo:
    """Information about a backend."""
    type: BackendType
    name: str
    icon: str
    is_available: bool = True
    is_compatible: bool = True
    reason: str = ""


@dataclass
class BackendRecommendation:
    """Recommendation for optimal backend."""
    recommended: BackendType
    available_backends: List[BackendInfo]
    reason: str
    feature_count: int = 0
    provider_type: str = ""


class BackendService(QObject):
    """
    Service for backend management.
    
    Provides:
    - Backend detection for layers
    - Backend forcing (per-layer or global)
    - Backend compatibility testing
    - Optimal backend recommendation
    - Backend availability checking
    
    Emits:
    - backend_changed: When a backend is forced/changed
    - backend_detected: When auto-detection occurs
    - backends_available: When available backends change
    """
    
    # Signals
    backend_changed = pyqtSignal(str, str)  # layer_id, backend_type
    backend_detected = pyqtSignal(str, str)  # layer_id, detected_type
    backends_available = pyqtSignal(list)  # list of BackendInfo
    force_all_complete = pyqtSignal(int, int, int)  # forced, warned, skipped
    
    # Backend icons and names
    BACKEND_INFO = {
        BackendType.POSTGRESQL: ("PostgreSQL", "🐘"),
        BackendType.SPATIALITE: ("Spatialite", "💾"),
        BackendType.OGR: ("OGR", "📁"),
        BackendType.AUTO: ("Auto", "🔄"),
    }
    
    # Thresholds for backend recommendations
    LARGE_DATASET_THRESHOLD = 50000
    VERY_LARGE_DATASET_THRESHOLD = 200000
    
    def __init__(self, parent: Optional[QObject] = None):
        """
        Initialize BackendService.
        
        Args:
            parent: Optional parent QObject
        """
        super().__init__(parent)
        
        # Forced backends: layer_id -> BackendType
        self._forced_backends: Dict[str, BackendType] = {}
        
        # Cache for backend availability
        self._postgresql_available: Optional[bool] = None
        
        # Backend instances cache
        self._backend_instances: Dict[BackendType, Any] = {}
    
    # ─────────────────────────────────────────────────────────────────
    # Availability Checks
    # ─────────────────────────────────────────────────────────────────
    
    @property
    def is_postgresql_available(self) -> bool:
        """Check if PostgreSQL backend is available (psycopg2 installed)."""
        if self._postgresql_available is None:
            try:
                from adapters.backends import POSTGRESQL_AVAILABLE
                self._postgresql_available = POSTGRESQL_AVAILABLE
            except ImportError:
                self._postgresql_available = False
        return self._postgresql_available
    
    def get_available_backends(self) -> List[BackendInfo]:
        """
        Get list of all potentially available backends.
        
        Returns:
            List of BackendInfo objects
        """
        backends = []
        
        # PostgreSQL (conditional)
        backends.append(BackendInfo(
            type=BackendType.POSTGRESQL,
            name="PostgreSQL",
            icon="🐘",
            is_available=self.is_postgresql_available,
            reason="" if self.is_postgresql_available else "psycopg2 not installed"
        ))
        
        # Spatialite (always available)
        backends.append(BackendInfo(
            type=BackendType.SPATIALITE,
            name="Spatialite",
            icon="💾",
            is_available=True
        ))
        
        # OGR (always available)
        backends.append(BackendInfo(
            type=BackendType.OGR,
            name="OGR",
            icon="📁",
            is_available=True
        ))
        
        return backends
    
    # ─────────────────────────────────────────────────────────────────
    # Backend Detection
    # ─────────────────────────────────────────────────────────────────
    
    def detect_backend(self, layer: "QgsVectorLayer") -> BackendType:
        """
        Detect which backend should be used for a layer.
        
        Priority:
        1. Forced backend (if set)
        2. Auto-detection based on provider
        
        Args:
            layer: QgsVectorLayer instance
            
        Returns:
            BackendType enum value
        """
        if layer is None or not layer.isValid():
            return BackendType.OGR
        
        layer_id = layer.id()
        
        # Check for forced backend
        if layer_id in self._forced_backends:
            forced = self._forced_backends[layer_id]
            logger.debug(f"Using forced backend {forced.value} for layer {layer.name()}")
            return forced
        
        # Auto-detect based on provider
        detected = self._auto_detect_backend(layer)
        self.backend_detected.emit(layer_id, detected.value)
        return detected
    
    def _auto_detect_backend(self, layer: "QgsVectorLayer") -> BackendType:
        """
        Auto-detect optimal backend based on layer provider.
        
        Args:
            layer: QgsVectorLayer instance
            
        Returns:
            BackendType enum value
        """
        provider_type = layer.providerType()
        
        if provider_type == 'postgres' and self.is_postgresql_available:
            return BackendType.POSTGRESQL
        elif provider_type == 'spatialite':
            return BackendType.SPATIALITE
        else:
            return BackendType.OGR
    
    def get_current_backend_string(self, layer: "QgsVectorLayer") -> str:
        """
        Get current backend as string (for backward compatibility).
        
        Args:
            layer: QgsVectorLayer instance
            
        Returns:
            Backend type string ('postgresql', 'spatialite', 'ogr')
        """
        return self.detect_backend(layer).value
    
    # ─────────────────────────────────────────────────────────────────
    # Backend Forcing
    # ─────────────────────────────────────────────────────────────────
    
    def force_backend(
        self,
        layer_id: str,
        backend_type: Optional[BackendType]
    ) -> None:
        """
        Force a specific backend for a layer.
        
        Args:
            layer_id: Layer ID
            backend_type: Backend to force, or None for auto
        """
        if backend_type is None:
            # Remove forced backend (use auto)
            if layer_id in self._forced_backends:
                del self._forced_backends[layer_id]
                logger.info(f"Removed forced backend for layer {layer_id}")
        else:
            self._forced_backends[layer_id] = backend_type
            logger.info(f"Forced backend {backend_type.value} for layer {layer_id}")
        
        self.backend_changed.emit(layer_id, backend_type.value if backend_type else "auto")
    
    def force_backend_string(
        self,
        layer_id: str,
        backend_type_str: Optional[str]
    ) -> None:
        """
        Force a backend using string type (backward compatibility).
        
        Args:
            layer_id: Layer ID
            backend_type_str: Backend type string or None
        """
        if backend_type_str is None:
            self.force_backend(layer_id, None)
        else:
            backend_type = BackendType(backend_type_str)
            self.force_backend(layer_id, backend_type)
    
    def get_forced_backend(self, layer_id: str) -> Optional[BackendType]:
        """
        Get forced backend for a layer, if any.
        
        Args:
            layer_id: Layer ID
            
        Returns:
            BackendType or None if auto
        """
        return self._forced_backends.get(layer_id)
    
    def get_forced_backend_string(self, layer_id: str) -> Optional[str]:
        """
        Get forced backend as string (backward compatibility).
        
        Args:
            layer_id: Layer ID
            
        Returns:
            Backend type string or None
        """
        forced = self.get_forced_backend(layer_id)
        return forced.value if forced else None
    
    def clear_forced_backend(self, layer_id: str) -> None:
        """
        Clear forced backend for a layer (use auto-detection).
        
        Args:
            layer_id: Layer ID
        """
        self.force_backend(layer_id, None)
    
    def clear_all_forced_backends(self) -> None:
        """Clear all forced backends."""
        layer_ids = list(self._forced_backends.keys())
        self._forced_backends.clear()
        
        for layer_id in layer_ids:
            self.backend_changed.emit(layer_id, "auto")
        
        logger.info(f"Cleared forced backends for {len(layer_ids)} layers")
    
    # ─────────────────────────────────────────────────────────────────
    # Force All Layers
    # ─────────────────────────────────────────────────────────────────
    
    def force_backend_for_all_layers(
        self,
        backend_type: BackendType,
        layers: Optional[List["QgsVectorLayer"]] = None
    ) -> Tuple[int, int, int]:
        """
        Force a specific backend for all layers.
        
        Args:
            backend_type: Backend to force
            layers: List of layers (if None, uses QgsProject)
            
        Returns:
            Tuple of (forced_count, warned_count, skipped_count)
        """
        if layers is None:
            from qgis.core import QgsProject, QgsVectorLayer
            project = QgsProject.instance()
            all_layers = project.mapLayers().values()
            layers = [l for l in all_layers if isinstance(l, QgsVectorLayer)]
        
        logger.info("=" * 60)
        logger.info(f"FORCING {backend_type.value.upper()} BACKEND FOR ALL LAYERS")
        logger.info("=" * 60)
        
        forced_count = 0
        warned_count = 0
        skipped_count = 0
        
        for layer in layers:
            if not layer.isValid():
                skipped_count += 1
                continue
            
            layer_name = layer.name()
            logger.info(f"\nProcessing layer: {layer_name}")
            
            # Check compatibility
            is_compatible, warn = self._check_backend_compatibility(layer, backend_type)
            
            if is_compatible and not warn:
                self.force_backend(layer.id(), backend_type)
                forced_count += 1
                logger.info(f"  ✓ Forced backend to: {backend_type.value.upper()}")
            elif is_compatible and warn:
                # Compatible with warning (e.g., Spatialite on GeoPackage)
                self.force_backend(layer.id(), backend_type)
                warned_count += 1
                logger.warning(f"  ⚠️ Forced {backend_type.value.upper()} with warning")
            else:
                skipped_count += 1
                logger.info(f"  ⚠ Skipped - not compatible")
        
        total = forced_count + warned_count
        logger.info("\n" + "=" * 60)
        logger.info(f"FORCE BACKEND COMPLETE: {total} forced, {skipped_count} skipped")
        logger.info("=" * 60)
        
        self.force_all_complete.emit(forced_count, warned_count, skipped_count)
        return forced_count, warned_count, skipped_count
    
    def _check_backend_compatibility(
        self,
        layer: "QgsVectorLayer",
        backend_type: BackendType
    ) -> Tuple[bool, bool]:
        """
        Check if a backend is compatible with a layer.
        
        Returns:
            Tuple of (is_compatible, has_warning)
        """
        if backend_type == BackendType.POSTGRESQL:
            if not self.is_postgresql_available:
                return False, False
            # PostgreSQL only works with postgres provider
            return layer.providerType() == 'postgres', False
        
        elif backend_type == BackendType.SPATIALITE:
            provider = layer.providerType()
            source = layer.source().lower()
            
            if provider == 'spatialite':
                return True, False
            
            # GeoPackage/SQLite work with Spatialite (with warning)
            if 'gpkg' in source or 'sqlite' in source:
                return True, True
            
            # OGR may work (with warning)
            if provider == 'ogr':
                return True, True
            
            return False, False
        
        elif backend_type == BackendType.OGR:
            # OGR is universal fallback
            return True, False
        
        return False, False
    
    # ─────────────────────────────────────────────────────────────────
    # Backend Compatibility Testing
    # ─────────────────────────────────────────────────────────────────
    
    def verify_backend_supports_layer(
        self,
        layer: "QgsVectorLayer",
        backend_type: BackendType
    ) -> bool:
        """
        Verify that a backend can actually support a layer.
        
        Uses the backend's supports_layer() method.
        
        Args:
            layer: QgsVectorLayer instance
            backend_type: Backend type to test
            
        Returns:
            bool: True if backend supports this layer
        """
        if layer is None or not layer.isValid():
            return False
        
        try:
            backend = self._get_backend_instance(backend_type)
            if backend is None:
                return False
            
            return backend.supports_layer(layer)
            
        except Exception as e:
            logger.warning(
                f"Error testing backend {backend_type.value} for layer {layer.name()}: {e}"
            )
            return False
    
    def _get_backend_instance(self, backend_type: BackendType) -> Any:
        """
        Get or create a backend instance for testing.
        
        Args:
            backend_type: Backend type
            
        Returns:
            Backend instance or None
        """
        if backend_type in self._backend_instances:
            return self._backend_instances[backend_type]
        
        try:
            task_params = {}  # Minimal params for testing
            
            if backend_type == BackendType.POSTGRESQL:
                if not self.is_postgresql_available:
                    return None
                from adapters.backends.postgresql import PostgreSQLGeometricFilter
                backend = PostgreSQLGeometricFilter(task_params)
                
            elif backend_type == BackendType.SPATIALITE:
                from adapters.backends.spatialite import SpatialiteGeometricFilter
                backend = SpatialiteGeometricFilter(task_params)
                
            elif backend_type == BackendType.OGR:
                from adapters.backends.ogr import OGRGeometricFilter
                backend = OGRGeometricFilter(task_params)
                
            else:
                return None
            
            self._backend_instances[backend_type] = backend
            return backend
            
        except Exception as e:
            logger.warning(f"Could not create backend instance for {backend_type.value}: {e}")
            return None
    
    # ─────────────────────────────────────────────────────────────────
    # Available Backends for Layer
    # ─────────────────────────────────────────────────────────────────
    
    def get_available_backends_for_layer(
        self,
        layer: "QgsVectorLayer"
    ) -> List[BackendInfo]:
        """
        Get list of available backends for a specific layer.
        
        Args:
            layer: QgsVectorLayer instance
            
        Returns:
            List of BackendInfo objects (compatible backends)
        """
        if layer is None or not layer.isValid():
            return []
        
        available = []
        provider_type = layer.providerType()
        source = layer.source().lower()
        
        # PostgreSQL
        if provider_type == 'postgres' and self.is_postgresql_available:
            available.append(BackendInfo(
                type=BackendType.POSTGRESQL,
                name="PostgreSQL",
                icon="🐘",
                is_available=True,
                is_compatible=True
            ))
        
        # Spatialite
        if provider_type == 'spatialite':
            available.append(BackendInfo(
                type=BackendType.SPATIALITE,
                name="Spatialite",
                icon="💾",
                is_available=True,
                is_compatible=True
            ))
        elif 'gpkg' in source or 'sqlite' in source:
            available.append(BackendInfo(
                type=BackendType.SPATIALITE,
                name="Spatialite",
                icon="💾",
                is_available=True,
                is_compatible=True,
                reason="GeoPackage/SQLite support"
            ))
        
        # OGR (always available)
        available.append(BackendInfo(
            type=BackendType.OGR,
            name="OGR",
            icon="📁",
            is_available=True,
            is_compatible=True,
            reason="Universal fallback"
        ))
        
        self.backends_available.emit(available)
        return available
    
    # ─────────────────────────────────────────────────────────────────
    # Optimal Backend Recommendation
    # ─────────────────────────────────────────────────────────────────
    
    def recommend_optimal_backend(
        self,
        layer: "QgsVectorLayer"
    ) -> BackendRecommendation:
        """
        Recommend optimal backend for a layer.
        
        Considers:
        - Provider type
        - Feature count
        - PostgreSQL availability
        - Data source type
        
        Args:
            layer: QgsVectorLayer instance
            
        Returns:
            BackendRecommendation object
        """
        if layer is None or not layer.isValid():
            return BackendRecommendation(
                recommended=BackendType.OGR,
                available_backends=[],
                reason="Invalid or null layer"
            )
        
        provider_type = layer.providerType()
        feature_count = layer.featureCount()
        available = self.get_available_backends_for_layer(layer)
        
        # PostgreSQL is optimal for postgres layers
        if provider_type == 'postgres' and self.is_postgresql_available:
            return BackendRecommendation(
                recommended=BackendType.POSTGRESQL,
                available_backends=available,
                reason="Native PostgreSQL layer",
                feature_count=feature_count,
                provider_type=provider_type
            )
        
        # Spatialite for spatialite layers
        if provider_type == 'spatialite':
            return BackendRecommendation(
                recommended=BackendType.SPATIALITE,
                available_backends=available,
                reason="Native Spatialite layer",
                feature_count=feature_count,
                provider_type=provider_type
            )
        
        # For large datasets, recommend Spatialite if available
        source = layer.source().lower()
        if feature_count > self.LARGE_DATASET_THRESHOLD:
            if 'gpkg' in source or 'sqlite' in source:
                return BackendRecommendation(
                    recommended=BackendType.SPATIALITE,
                    available_backends=available,
                    reason=f"Large dataset ({feature_count:,} features) - Spatialite recommended",
                    feature_count=feature_count,
                    provider_type=provider_type
                )
        
        # Default to OGR
        return BackendRecommendation(
            recommended=BackendType.OGR,
            available_backends=available,
            reason="Default OGR backend",
            feature_count=feature_count,
            provider_type=provider_type
        )
    
    # ─────────────────────────────────────────────────────────────────
    # Backend Info Helpers
    # ─────────────────────────────────────────────────────────────────
    
    def get_backend_display_info(
        self,
        backend_type: BackendType
    ) -> Tuple[str, str]:
        """
        Get display name and icon for a backend.
        
        Args:
            backend_type: Backend type
            
        Returns:
            Tuple of (name, icon)
        """
        return self.BACKEND_INFO.get(backend_type, ("Unknown", "❓"))
    
    def get_backend_from_string(self, backend_str: str) -> BackendType:
        """
        Convert string to BackendType enum.
        
        Args:
            backend_str: Backend string
            
        Returns:
            BackendType enum value
        """
        try:
            return BackendType(backend_str.lower())
        except ValueError:
            return BackendType.OGR
    
    # ─────────────────────────────────────────────────────────────────
    # State Management
    # ─────────────────────────────────────────────────────────────────
    
    def get_forced_backends_summary(self) -> Dict[str, str]:
        """
        Get summary of all forced backends.
        
        Returns:
            Dict mapping layer_id to backend_type string
        """
        return {
            layer_id: backend.value
            for layer_id, backend in self._forced_backends.items()
        }
    
    def set_forced_backends_from_dict(self, forced_dict: Dict[str, str]) -> None:
        """
        Restore forced backends from a dictionary.
        
        Args:
            forced_dict: Dict mapping layer_id to backend_type string
        """
        self._forced_backends.clear()
        
        for layer_id, backend_str in forced_dict.items():
            try:
                backend_type = BackendType(backend_str)
                self._forced_backends[layer_id] = backend_type
            except ValueError:
                logger.warning(f"Invalid backend type '{backend_str}' for layer {layer_id}")
    
    def cleanup_removed_layers(self, existing_layer_ids: List[str]) -> int:
        """
        Remove forced backends for layers that no longer exist.
        
        Args:
            existing_layer_ids: List of existing layer IDs
            
        Returns:
            Number of entries removed
        """
        existing_set = set(existing_layer_ids)
        to_remove = [
            layer_id for layer_id in self._forced_backends
            if layer_id not in existing_set
        ]
        
        for layer_id in to_remove:
            del self._forced_backends[layer_id]
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} forced backend entries")
        
        return len(to_remove)

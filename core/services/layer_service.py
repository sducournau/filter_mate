"""
LayerService - Layer Management Business Logic.

Centralizes layer validation, preparation, and state management.
Extracted from filter_mate_dockwidget.py as part of the God Class migration.

Story: MIG-077
Phase: 6 - God Class DockWidget Migration
Pattern: Strangler Fig - Gradual extraction
"""

import logging
import time
from typing import Dict, List, Optional, Tuple, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum, auto

try:
    from qgis.PyQt.QtCore import pyqtSignal, QObject
except ImportError:
    from PyQt5.QtCore import pyqtSignal, QObject

if TYPE_CHECKING:
    from qgis.core import QgsVectorLayer, QgsProject, QgsField

logger = logging.getLogger(__name__)


class LayerValidationStatus(Enum):
    """Layer validation result status."""
    VALID = auto()
    INVALID = auto()
    NOT_VECTOR = auto()
    SOURCE_UNAVAILABLE = auto()
    DELETED = auto()
    NOT_IN_PROJECT = auto()
    PLUGIN_BUSY = auto()


@dataclass
class LayerValidationResult:
    """Result of layer validation."""
    status: LayerValidationStatus
    layer: Optional["QgsVectorLayer"] = None
    layer_id: Optional[str] = None
    layer_name: Optional[str] = None
    error_message: str = ""
    
    @property
    def is_valid(self) -> bool:
        return self.status == LayerValidationStatus.VALID


@dataclass
class LayerInfo:
    """Information about a layer for display."""
    layer_id: str
    name: str
    provider_type: str
    feature_count: int
    geometry_type: str
    crs: str
    primary_key: Optional[str] = None
    has_valid_source: bool = True
    is_editable: bool = False
    fields: List[str] = field(default_factory=list)


@dataclass
class LayerSyncState:
    """State information for layer synchronization."""
    layer_id: str
    layer_name: str
    provider_type: str
    has_subset: bool = False
    subset_string: str = ""
    is_multi_step_filter: bool = False
    primary_key: Optional[str] = None
    forced_backend: Optional[str] = None


class LayerService(QObject):
    """
    Service for layer management operations.
    
    Provides:
    - Layer validation (source, type, availability)
    - Layer information extraction
    - Layer state synchronization
    - Primary key detection
    - Field expression management
    - Multi-step filter detection
    
    Emits:
    - layer_validated: When a layer is validated
    - layer_info_updated: When layer info is extracted
    - layer_sync_started: When sync operation starts
    - layer_sync_completed: When sync operation completes
    - validation_failed: When validation fails
    """
    
    # Signals
    layer_validated = pyqtSignal(str, bool)  # layer_id, is_valid
    layer_info_updated = pyqtSignal(str, object)  # layer_id, LayerInfo
    layer_sync_started = pyqtSignal(str)  # layer_id
    layer_sync_completed = pyqtSignal(str)  # layer_id
    validation_failed = pyqtSignal(str, str)  # layer_id, reason
    
    def __init__(self, parent: Optional[QObject] = None):
        """
        Initialize LayerService.
        
        Args:
            parent: Optional parent QObject
        """
        super().__init__(parent)
        
        # Cache for layer info
        self._layer_info_cache: Dict[str, LayerInfo] = {}
        
        # Protection window tracking
        self._filter_completed_time: float = 0
        self._saved_layer_id_before_filter: Optional[str] = None
        
        # Protection window duration (matches dockwidget)
        self.POST_FILTER_PROTECTION_WINDOW = 5.0  # seconds
    
    # ─────────────────────────────────────────────────────────────────
    # Layer Validation
    # ─────────────────────────────────────────────────────────────────
    
    def validate_layer(
        self,
        layer: Optional["QgsVectorLayer"],
        project_layers: Optional[Dict[str, Any]] = None,
        plugin_busy: bool = False
    ) -> LayerValidationResult:
        """
        Validate a layer for FilterMate operations.
        
        Checks:
        1. Plugin not busy
        2. Layer is not None
        3. Layer is a vector layer
        4. Layer C++ object is valid
        5. Layer source is available
        6. Layer exists in PROJECT_LAYERS
        
        Args:
            layer: Layer to validate
            project_layers: PROJECT_LAYERS dict
            plugin_busy: Whether plugin is busy
            
        Returns:
            LayerValidationResult with status and details
        """
        # Check plugin busy state
        if plugin_busy:
            return LayerValidationResult(
                status=LayerValidationStatus.PLUGIN_BUSY,
                error_message="Plugin is busy with critical operations"
            )
        
        # Check None
        if layer is None:
            return LayerValidationResult(
                status=LayerValidationStatus.INVALID,
                error_message="Layer is None"
            )
        
        # Check vector layer type
        try:
            from qgis.core import QgsVectorLayer
            if not isinstance(layer, QgsVectorLayer):
                return LayerValidationResult(
                    status=LayerValidationStatus.NOT_VECTOR,
                    error_message="Layer is not a vector layer"
                )
        except ImportError:
            pass  # Skip type check if QGIS not available
        
        # Check C++ object validity
        try:
            layer_id = layer.id()
            layer_name = layer.name()
        except RuntimeError:
            return LayerValidationResult(
                status=LayerValidationStatus.DELETED,
                error_message="Layer C++ object was deleted"
            )
        
        # Check source availability
        if not self._is_layer_source_available(layer):
            return LayerValidationResult(
                status=LayerValidationStatus.SOURCE_UNAVAILABLE,
                layer=layer,
                layer_id=layer_id,
                layer_name=layer_name,
                error_message=f"Layer '{layer_name}' source is unavailable"
            )
        
        # Check PROJECT_LAYERS membership
        if project_layers is not None and layer_id not in project_layers:
            return LayerValidationResult(
                status=LayerValidationStatus.NOT_IN_PROJECT,
                layer=layer,
                layer_id=layer_id,
                layer_name=layer_name,
                error_message=f"Layer '{layer_name}' not in PROJECT_LAYERS"
            )
        
        # All checks passed
        self.layer_validated.emit(layer_id, True)
        
        return LayerValidationResult(
            status=LayerValidationStatus.VALID,
            layer=layer,
            layer_id=layer_id,
            layer_name=layer_name
        )
    
    def _is_layer_source_available(self, layer: "QgsVectorLayer") -> bool:
        """
        Check if layer source is available.
        
        Args:
            layer: Layer to check
            
        Returns:
            bool: True if source is available
        """
        try:
            # Try importing helper function
            from core.services.layer_service import is_layer_source_available
            return is_layer_source_available(layer)
        except ImportError:
            # Fallback: check isValid()
            try:
                return layer.isValid()
            except Exception:
                return False
    
    # ─────────────────────────────────────────────────────────────────
    # Layer Information
    # ─────────────────────────────────────────────────────────────────
    
    def get_layer_info(
        self,
        layer: "QgsVectorLayer",
        use_cache: bool = True
    ) -> Optional[LayerInfo]:
        """
        Extract information about a layer.
        
        Args:
            layer: Layer to get info for
            use_cache: Whether to use cached info
            
        Returns:
            LayerInfo object or None
        """
        if layer is None:
            return None
        
        try:
            layer_id = layer.id()
        except RuntimeError:
            return None
        
        # Check cache
        if use_cache and layer_id in self._layer_info_cache:
            return self._layer_info_cache[layer_id]
        
        try:
            from qgis.core import QgsWkbTypes
            
            geometry_type = QgsWkbTypes.displayString(layer.wkbType())
            
            info = LayerInfo(
                layer_id=layer_id,
                name=layer.name(),
                provider_type=layer.providerType(),
                feature_count=layer.featureCount(),
                geometry_type=geometry_type,
                crs=layer.crs().authid(),
                has_valid_source=layer.isValid(),
                is_editable=layer.isEditable(),
                fields=[f.name() for f in layer.fields()],
                primary_key=self._detect_primary_key(layer)
            )
            
            # Cache result
            self._layer_info_cache[layer_id] = info
            
            self.layer_info_updated.emit(layer_id, info)
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting layer info: {e}")
            return None
    
    def clear_cache(self, layer_id: Optional[str] = None) -> None:
        """
        Clear layer info cache.
        
        Args:
            layer_id: Specific layer to clear, or None for all
        """
        if layer_id is not None:
            self._layer_info_cache.pop(layer_id, None)
        else:
            self._layer_info_cache.clear()
    
    # ─────────────────────────────────────────────────────────────────
    # Primary Key Detection
    # ─────────────────────────────────────────────────────────────────
    
    def _detect_primary_key(self, layer: "QgsVectorLayer") -> Optional[str]:
        """
        Detect the primary key field for a layer.
        
        Priority:
        1. Provider-defined primary key
        2. Field named 'id', 'fid', 'pk', etc.
        3. First integer field
        4. First field
        
        Args:
            layer: Layer to detect PK for
            
        Returns:
            Primary key field name or None
        """
        if layer is None:
            return None
        
        try:
            fields = layer.fields()
            
            # Try to get from provider
            pk_indexes = layer.primaryKeyAttributes()
            if pk_indexes:
                return fields[pk_indexes[0]].name()
            
            # Look for common PK names
            pk_names = ['id', 'fid', 'pk', 'gid', 'ogc_fid', 'objectid']
            for field in fields:
                if field.name().lower() in pk_names:
                    return field.name()
            
            # First integer field
            from qgis.core import QVariant
            for field in fields:
                if field.type() in (QVariant.Int, QVariant.LongLong):
                    return field.name()
            
            # First field as fallback
            if fields:
                return fields[0].name()
            
            return None
            
        except Exception as e:
            logger.debug(f"Error detecting primary key: {e}")
            return None
    
    def get_primary_key(
        self,
        layer: "QgsVectorLayer",
        layer_props: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Get primary key for a layer.
        
        First checks layer_props, then auto-detects.
        
        Args:
            layer: Layer to get PK for
            layer_props: Optional cached properties
            
        Returns:
            Primary key field name
        """
        # Check cached props first
        if layer_props:
            infos = layer_props.get('infos', {})
            pk = infos.get('primary_key_name')
            if pk:
                return pk
        
        # Auto-detect
        return self._detect_primary_key(layer)
    
    # ─────────────────────────────────────────────────────────────────
    # Layer Sync State
    # ─────────────────────────────────────────────────────────────────
    
    def get_sync_state(
        self,
        layer: "QgsVectorLayer",
        layer_props: Optional[Dict] = None,
        forced_backends: Optional[Dict[str, str]] = None
    ) -> Optional[LayerSyncState]:
        """
        Get synchronization state for a layer.
        
        Args:
            layer: Layer to get state for
            layer_props: Optional cached properties
            forced_backends: Optional forced backends dict
            
        Returns:
            LayerSyncState object
        """
        if layer is None:
            return None
        
        try:
            layer_id = layer.id()
            subset = layer.subsetString() or ""
            
            state = LayerSyncState(
                layer_id=layer_id,
                layer_name=layer.name(),
                provider_type=layer.providerType(),
                has_subset=bool(subset),
                subset_string=subset,
                is_multi_step_filter=self._detect_multi_step_filter(layer, layer_props),
                primary_key=self.get_primary_key(layer, layer_props)
            )
            
            # Add forced backend if available
            if forced_backends and layer_id in forced_backends:
                state.forced_backend = forced_backends[layer_id]
            
            return state
            
        except Exception as e:
            logger.error(f"Error getting sync state: {e}")
            return None
    
    def _detect_multi_step_filter(
        self,
        layer: "QgsVectorLayer",
        layer_props: Optional[Dict] = None
    ) -> bool:
        """
        Detect if layer has multi-step (additive) filtering.
        
        Args:
            layer: Layer to check
            layer_props: Optional cached properties
            
        Returns:
            bool: True if multi-step filter detected
        """
        if layer is None:
            return False
        
        try:
            # Check for existing subset
            subset = layer.subsetString()
            if not subset:
                return False
            
            # Check layer_props for previous filter history
            if layer_props:
                # Check if has_combine_operator is enabled
                has_combine = layer_props.get('has_combine_operator', {}).get('has_combine_operator', False)
                if has_combine:
                    return True
            
            # Check subset string for multiple conditions
            # Multi-step filters typically use AND/OR combinations
            upper_subset = subset.upper()
            if ' AND ' in upper_subset or ' OR ' in upper_subset:
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Error detecting multi-step filter: {e}")
            return False
    
    # ─────────────────────────────────────────────────────────────────
    # Field Validation
    # ─────────────────────────────────────────────────────────────────
    
    def validate_field_expression(
        self,
        layer: "QgsVectorLayer",
        expression: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a field expression for a layer.
        
        Args:
            layer: Layer to validate against
            expression: Field expression string
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not expression:
            return True, None
        
        if layer is None:
            return False, "No layer provided"
        
        try:
            # Normalize expression (remove quotes)
            normalized = expression.strip().strip('"')
            
            # Get layer fields
            field_names = [f.name() for f in layer.fields()]
            
            # Check if it's a simple field name
            if normalized in field_names or expression in field_names:
                return True, None
            
            # Try to validate as QGIS expression
            from qgis.core import QgsExpression
            expr = QgsExpression(expression)
            
            if expr.hasParserError():
                return False, expr.parserErrorString()
            
            return True, None
            
        except Exception as e:
            return False, str(e)
    
    def get_valid_expression(
        self,
        layer: "QgsVectorLayer",
        expression: str,
        fallback_to_pk: bool = True
    ) -> str:
        """
        Get a valid expression for a layer.
        
        If expression is invalid, returns primary key or first field.
        
        Args:
            layer: Layer to validate against
            expression: Expression to validate
            fallback_to_pk: Use primary key as fallback
            
        Returns:
            Valid expression string
        """
        if layer is None:
            return expression or ""
        
        is_valid, _ = self.validate_field_expression(layer, expression)
        
        if is_valid:
            return expression
        
        # Get fallback
        if fallback_to_pk:
            pk = self._detect_primary_key(layer)
            if pk:
                return pk
        
        # Use first field
        try:
            fields = layer.fields()
            if fields:
                return fields[0].name()
        except Exception:
            pass
        
        return expression or ""
    
    # ─────────────────────────────────────────────────────────────────
    # Protection Window Management
    # ─────────────────────────────────────────────────────────────────
    
    def save_layer_before_filter(self, layer: "QgsVectorLayer") -> None:
        """
        Save layer ID before filter operation for protection.
        
        Args:
            layer: Layer being filtered
        """
        if layer is not None:
            try:
                self._saved_layer_id_before_filter = layer.id()
            except RuntimeError:
                pass
    
    def mark_filter_completed(self) -> None:
        """Mark that a filter operation has completed."""
        self._filter_completed_time = time.time()
    
    def clear_filter_protection(self) -> None:
        """Clear the filter protection state."""
        self._filter_completed_time = 0
        self._saved_layer_id_before_filter = None
    
    def is_within_protection_window(self) -> bool:
        """Check if within post-filter protection window."""
        if self._filter_completed_time == 0:
            return False
        
        elapsed = time.time() - self._filter_completed_time
        return elapsed < self.POST_FILTER_PROTECTION_WINDOW
    
    def should_block_layer_change(
        self,
        new_layer: Optional["QgsVectorLayer"]
    ) -> Tuple[bool, str]:
        """
        Check if a layer change should be blocked.
        
        Args:
            new_layer: Layer being changed to
            
        Returns:
            Tuple of (should_block, reason)
        """
        if not self.is_within_protection_window():
            return False, ""
        
        saved_id = self._saved_layer_id_before_filter
        
        if not saved_id:
            return False, ""
        
        # Block None layer during protection
        if new_layer is None:
            return True, "Layer None during protection window"
        
        # Block different layer during protection
        try:
            if new_layer.id() != saved_id:
                return True, "Layer change during protection window"
        except RuntimeError:
            return True, "Layer deleted during protection window"
        
        return False, ""
    
    # ─────────────────────────────────────────────────────────────────
    # Utility Methods
    # ─────────────────────────────────────────────────────────────────
    
    def get_layer_display_name(
        self,
        layer: "QgsVectorLayer",
        max_length: int = 30
    ) -> str:
        """
        Get display name for a layer.
        
        Args:
            layer: Layer to get name for
            max_length: Maximum name length
            
        Returns:
            Display name string
        """
        if layer is None:
            return "(No layer)"
        
        try:
            name = layer.name()
            if len(name) <= max_length:
                return name
            return name[:max_length - 3] + "..."
        except RuntimeError:
            return "(Deleted)"
    
    def get_provider_display_name(
        self,
        provider_type: str
    ) -> Tuple[str, str]:
        """
        Get display name and icon for provider type.
        
        Args:
            provider_type: Provider type string
            
        Returns:
            Tuple of (display_name, icon)
        """
        providers = {
            'postgres': ('PostgreSQL', '🐘'),
            'spatialite': ('Spatialite', '💾'),
            'ogr': ('OGR', '📁'),
            'memory': ('Memory', '🧠'),
            'wfs': ('WFS', '🌐'),
        }
        
        return providers.get(provider_type, (provider_type, '📄'))
    
    def cleanup_for_removed_layers(
        self,
        existing_layer_ids: List[str]
    ) -> int:
        """
        Remove cached data for layers that no longer exist.
        
        Args:
            existing_layer_ids: List of existing layer IDs
            
        Returns:
            Number of entries removed
        """
        existing_set = set(existing_layer_ids)
        
        to_remove = [
            layer_id for layer_id in self._layer_info_cache
            if layer_id not in existing_set
        ]
        
        for layer_id in to_remove:
            del self._layer_info_cache[layer_id]
        
        # Clear protection if saved layer was removed
        if (self._saved_layer_id_before_filter and 
            self._saved_layer_id_before_filter not in existing_set):
            self.clear_filter_protection()
        
        return len(to_remove)

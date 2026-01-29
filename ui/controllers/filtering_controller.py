"""
FilterMate Filtering Controller.

Manages filtering tab logic including source/target layer selection,
predicate configuration, buffer settings, expression building,
filter execution, and undo/redo functionality.
"""
from typing import TYPE_CHECKING, Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

from qgis.PyQt.QtCore import QTimer
from .base_controller import BaseController
from .mixins.layer_selection_mixin import LayerSelectionMixin

# Module logger
logger = logging.getLogger(__name__)

# Import TaskParameterBuilder for clean parameter construction (v3.0 MIG-024)
try:
    from ...adapters.task_builder import TaskParameterBuilder, TaskParameters
    TASK_BUILDER_AVAILABLE = True
except ImportError:
    TASK_BUILDER_AVAILABLE = False
    TaskParameterBuilder = None
    TaskParameters = None

# EPIC-3: Import RasterFilterService for raster-based filtering
try:
    from ...core.services.raster_filter_service import (
        RasterFilterService,
        RasterFilterContext,
        RasterFilterMode
    )
    from ...core.ports.raster_filter_port import RasterValuePredicate
    from ...adapters.backends.qgis_raster_filter_backend import QGISRasterFilterBackend
    RASTER_FILTER_AVAILABLE = True
except ImportError:
    RASTER_FILTER_AVAILABLE = False
    RasterFilterService = None
    RasterFilterContext = None
    RasterFilterMode = None
    RasterValuePredicate = None
    QGISRasterFilterBackend = None

if TYPE_CHECKING:
    from qgis.core import QgsVectorLayer
    from filter_mate_dockwidget import FilterMateDockWidget
    from ...core.services.filter_service import FilterService
    from ...adapters.qgis.signals.signal_manager import SignalManager


class PredicateType(Enum):
    """Spatial predicate types available for filtering."""
    INTERSECTS = "intersects"
    CONTAINS = "contains"
    WITHIN = "within"
    TOUCHES = "touches"
    CROSSES = "crosses"
    OVERLAPS = "overlaps"
    DISJOINT = "disjoint"
    EQUALS = "equals"
    BBOX = "bbox"


class BufferType(Enum):
    """Buffer type for spatial predicates."""
    NONE = "none"
    SOURCE = "source"
    TARGET = "target"
    BOTH = "both"


class CombineOperator(Enum):
    """
    SQL combine operators for multi-layer filtering.
    
    v3.1 STORY-2.4: Centralized operator management with i18n support.
    """
    AND = "AND"
    AND_NOT = "AND NOT"
    OR = "OR"
    
    @classmethod
    def from_index(cls, index: int) -> 'CombineOperator':
        """
        Convert combobox index to CombineOperator.
        
        Args:
            index: Combobox index (0=AND, 1=AND NOT, 2=OR)
        
        Returns:
            CombineOperator enum value
        """
        mapping = {0: cls.AND, 1: cls.AND_NOT, 2: cls.OR}
        return mapping.get(index, cls.AND)
    
    def to_index(self) -> int:
        """
        Convert CombineOperator to combobox index.
        
        Returns:
            Combobox index (0=AND, 1=AND NOT, 2=OR)
        """
        mapping = {CombineOperator.AND: 0, CombineOperator.AND_NOT: 1, CombineOperator.OR: 2}
        return mapping.get(self, 0)
    
    @classmethod
    def from_string(cls, operator: str) -> 'CombineOperator':
        """
        Convert string (including translations) to CombineOperator.
        
        v3.1 STORY-2.4: Handles translated operator values (ET, OU, etc.)
        from older project files or when QGIS locale is non-English.
        
        Args:
            operator: SQL operator or translated equivalent
        
        Returns:
            CombineOperator enum value
        """
        if not operator:
            return cls.AND
        
        op_upper = operator.upper().strip()
        
        # Map of all possible operator values (including translations) to enum
        operator_map = {
            # English (canonical)
            'AND': cls.AND,
            'AND NOT': cls.AND_NOT,
            'OR': cls.OR,
            # French
            'ET': cls.AND,
            'ET NON': cls.AND_NOT,
            'OU': cls.OR,
            # German
            'UND': cls.AND,
            'UND NICHT': cls.AND_NOT,
            'ODER': cls.OR,
            # Spanish
            'Y': cls.AND,
            'Y NO': cls.AND_NOT,
            'O': cls.OR,
            # Italian
            'E': cls.AND,
            'E NON': cls.AND_NOT,
            # Portuguese
            'E NÃO': cls.AND_NOT,
        }
        
        return operator_map.get(op_upper, cls.AND)


@dataclass
class FilterConfiguration:
    """
    Holds the current filter configuration state.
    
    Immutable representation of a filter setup that can be
    used for execution, saving, or undo/redo.
    """
    source_layer_id: Optional[str] = None
    target_layer_ids: List[str] = field(default_factory=list)
    predicate: PredicateType = PredicateType.INTERSECTS
    buffer_value: float = 0.0
    buffer_type: BufferType = BufferType.NONE
    expression: str = ""
    
    def is_valid(self) -> bool:
        """Check if configuration is valid for execution."""
        return (
            self.source_layer_id is not None and
            len(self.target_layer_ids) > 0
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source_layer_id": self.source_layer_id,
            "target_layer_ids": self.target_layer_ids,
            "predicate": self.predicate.value,
            "buffer_value": self.buffer_value,
            "buffer_type": self.buffer_type.value,
            "expression": self.expression
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FilterConfiguration':
        """Create from dictionary."""
        return cls(
            source_layer_id=data.get("source_layer_id"),
            target_layer_ids=data.get("target_layer_ids", []),
            predicate=PredicateType(data.get("predicate", "intersects")),
            buffer_value=data.get("buffer_value", 0.0),
            buffer_type=BufferType(data.get("buffer_type", "none")),
            expression=data.get("expression", "")
        )


@dataclass
class FilterResult:
    """Result of a filter execution."""
    success: bool
    affected_features: int = 0
    error_message: str = ""
    execution_time_ms: float = 0.0
    configuration: Optional[FilterConfiguration] = None


class FilteringController(BaseController, LayerSelectionMixin):
    """
    Controller for the Filtering tab.
    
    Manages:
    - Source layer selection
    - Target layers selection (multi-select)
    - Predicate configuration
    - Buffer configuration
    - Expression building and preview
    - Filter execution
    - Undo/Redo history
    
    Signals (emitted via dockwidget):
    - filterStarted: Filter execution started
    - filterCompleted: Filter execution completed successfully
    - filterError: Filter execution failed
    - expressionChanged: Filter expression changed
    - configurationChanged: Any configuration changed
    """
    
    def __init__(
        self,
        dockwidget: 'FilterMateDockWidget',
        filter_service: Optional['FilterService'] = None,
        signal_manager: Optional['SignalManager'] = None,
        undo_manager: Optional[Any] = None
    ):
        """
        Initialize the filtering controller.
        
        Args:
            dockwidget: Parent dockwidget for UI access
            filter_service: Filter service for business logic
            signal_manager: Centralized signal manager
            undo_manager: Undo/redo manager for filter history
        """
        super().__init__(dockwidget, filter_service, signal_manager)
        
        # State
        self._source_layer: Optional['QgsVectorLayer'] = None
        self._target_layer_ids: List[str] = []
        self._current_predicate: PredicateType = PredicateType.INTERSECTS
        self._buffer_value: float = 0.0
        self._buffer_type: BufferType = BufferType.NONE
        self._current_expression: str = ""
        
        # v3.1 STORY-2.4: State change handler flags
        self._has_layers_to_filter: bool = False
        self._has_combine_operator: bool = False
        self._has_geometric_predicates: bool = False
        self._has_buffer_type: bool = False
        self._has_buffer_value: bool = False
        self._buffer_property_active: bool = False
        
        # History for undo/redo
        self._undo_manager = undo_manager
        self._undo_stack: List[FilterConfiguration] = []
        self._redo_stack: List[FilterConfiguration] = []
        self._max_history: int = 50
        
        # Callbacks for UI updates
        self._on_expression_changed_callbacks: List[Callable[[str], None]] = []
        self._on_config_changed_callbacks: List[Callable[[FilterConfiguration], None]] = []
        
        # Execution state
        self._is_executing: bool = False
        self._last_result: Optional[FilterResult] = None
        
        # EPIC-3: Raster filter service for raster-based filtering
        self._raster_filter_service: Optional['RasterFilterService'] = None
        if RASTER_FILTER_AVAILABLE:
            try:
                backend = QGISRasterFilterBackend()
                self._raster_filter_service = RasterFilterService(backend)
                self._connect_raster_filter_signals()
                logger.info("EPIC-3: RasterFilterService initialized")
            except Exception as e:
                logger.warning(f"EPIC-3: Failed to initialize RasterFilterService: {e}")

    # === LayerSelectionMixin implementation ===
    
    def get_current_layer(self) -> Optional['QgsVectorLayer']:
        """Get the current source layer (for mixin compatibility)."""
        return self._source_layer
    
    # === Source Layer Management ===
    
    def get_source_layer(self) -> Optional['QgsVectorLayer']:
        """Get the current source layer for filtering."""
        return self._source_layer
    
    def set_source_layer(self, layer: Optional['QgsVectorLayer']) -> None:
        """
        Set the source layer for filtering.
        
        Changing the source layer:
        - Clears target layers selection
        - Resets expression
        - Notifies listeners
        
        Args:
            layer: New source layer or None
        """
        if layer == self._source_layer:
            return
        
        old_layer = self._source_layer
        self._source_layer = layer
        
        # Clear dependent state when source changes
        if layer != old_layer:
            self._clear_target_layers()
            self._current_expression = ""
            self._notify_config_changed()
    
    def on_source_layer_changed(self, layer: Optional['QgsVectorLayer']) -> None:
        """
        Handle source layer change from UI.
        
        Args:
            layer: New layer from combo box
        """
        self.set_source_layer(layer)
    
    # === Target Layers Management ===
    
    def get_target_layers(self) -> List[str]:
        """Get list of target layer IDs."""
        return self._target_layer_ids.copy()
    
    def set_target_layers(self, layer_ids: List[str]) -> None:
        """
        Set target layers for filtering.
        
        Args:
            layer_ids: List of layer IDs to use as targets
        """
        if layer_ids == self._target_layer_ids:
            return
        
        self._target_layer_ids = layer_ids.copy()
        self._rebuild_expression()
        self._notify_config_changed()
    
    def add_target_layer(self, layer_id: str) -> None:
        """Add a layer to targets."""
        if layer_id not in self._target_layer_ids:
            self._target_layer_ids.append(layer_id)
            self._rebuild_expression()
            self._notify_config_changed()
    
    def remove_target_layer(self, layer_id: str) -> None:
        """Remove a layer from targets."""
        if layer_id in self._target_layer_ids:
            self._target_layer_ids.remove(layer_id)
            self._rebuild_expression()
            self._notify_config_changed()
    
    def _clear_target_layers(self) -> None:
        """Clear all target layers."""
        self._target_layer_ids.clear()
    
    def on_target_layers_changed(self, layer_ids: List[str]) -> None:
        """
        Handle target layers change from UI.
        
        Args:
            layer_ids: New list of checked layer IDs
        """
        self.set_target_layers(layer_ids)
    
    def populate_layers_checkable_combobox(self, layer: Optional['QgsVectorLayer'] = None) -> bool:
        """
        Populate the layers-to-filter checkable combobox.
        
        v3.1 Sprint 5: Migrated from dockwidget to controller.
        
        This method:
        - Clears existing items
        - Adds all valid vector layers from PROJECT_LAYERS (except source layer)
        - Sets check state based on saved preferences
        
        Args:
            layer: Source layer (uses current layer if None)
        
        Returns:
            True if population succeeded, False otherwise
        """
        logger.info(f"=== populate_layers_checkable_combobox START (layer={layer.name() if layer else 'None'}) ===")
        try:
            dockwidget = self._dockwidget
            if not dockwidget:
                logger.warning("populate_layers_checkable_combobox: dockwidget not available")
                return False
            if not dockwidget.widgets_initialized:
                logger.warning("populate_layers_checkable_combobox: widgets not initialized")
                return False
            
            # v4.0.5: Log diagnostic info
            logger.info(f"populate_layers_checkable_combobox: has_loaded_layers={getattr(dockwidget, 'has_loaded_layers', False)}, PROJECT_LAYERS count={len(dockwidget.PROJECT_LAYERS) if dockwidget.PROJECT_LAYERS else 0}")
            
            # Imports
            from qgis.core import QgsVectorLayer, QgsProject
            from qgis.PyQt.QtCore import Qt
            from ...infrastructure.utils.validation_utils import is_layer_source_available
            
            # Determine source layer
            if layer is None:
                layer = dockwidget.current_layer
            
            if layer is None or not isinstance(layer, QgsVectorLayer):
                logger.debug("populate_layers_checkable_combobox: No valid source layer")
                return False
            
            # Check layer exists in PROJECT_LAYERS
            if layer.id() not in dockwidget.PROJECT_LAYERS:
                logger.info(f"Layer {layer.name()} not in PROJECT_LAYERS yet, skipping")
                return False
            
            layer_props = dockwidget.PROJECT_LAYERS[layer.id()]
            project = QgsProject.instance()
            
            # DIAGNOSTIC v4.0.5: Log PROJECT_LAYERS state
            logger.info(f"🔍 DIAGNOSTIC: PROJECT_LAYERS has {len(dockwidget.PROJECT_LAYERS)} entries")
            logger.info(f"🔍 DIAGNOSTIC: PROJECT_LAYERS keys: {list(dockwidget.PROJECT_LAYERS.keys())}")
            
            # Clear widget
            layers_widget = dockwidget.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"]
            layers_widget.clear()
            
            # Get saved layers to filter
            has_layers = layer_props.get("filtering", {}).get("has_layers_to_filter", False)
            layers_to_filter = layer_props.get("filtering", {}).get("layers_to_filter", [])
            
            # CRITICAL: Remove current layer from layers_to_filter if present
            # The current layer cannot be a target layer (couche distante)
            source_layer_id = layer.id()
            if source_layer_id in layers_to_filter:
                layers_to_filter = [lid for lid in layers_to_filter if lid != source_layer_id]
                # Update the stored property
                if "filtering" in layer_props:
                    layer_props["filtering"]["layers_to_filter"] = layers_to_filter
                    # Update has_layers_to_filter flag if list is now empty
                    if not layers_to_filter:
                        layer_props["filtering"]["has_layers_to_filter"] = False
                        has_layers = False
                logger.info(f"✓ Removed source layer {layer.name()} (ID: {source_layer_id}) from layers_to_filter")
            else:
                logger.debug(f"✓ Source layer {layer.name()} (ID: {source_layer_id}) not in layers_to_filter (correct)")
            
            # Diagnostic logging
            qgis_vector_layers = [l for l in project.mapLayers().values() 
                                  if isinstance(l, QgsVectorLayer) and l.id() != layer.id()]
            missing = [l for l in qgis_vector_layers if l.id() not in dockwidget.PROJECT_LAYERS]
            if missing:
                logger.warning(f"populate_layers_checkable_combobox: {len(missing)} layer(s) NOT in PROJECT_LAYERS")
                logger.warning(f"Layers in QGIS but NOT in PROJECT_LAYERS: {[l.name() for l in missing]}")
                
                # FIX 2026-01-16 v2: Robust automatic addition with retry
                # BYPASS queue system for critical sync + retry after 1s
                if hasattr(dockwidget, 'app') and dockwidget.app:
                    logger.info("🔄 Triggering automatic add_layers for missing layers...")
                    try:
                        # Reset counter to bypass queue
                        dockwidget.app._pending_add_layers_tasks = 0
                        dockwidget.app.manage_task('add_layers', missing)
                        
                        # Retry after 1s to ensure completion
                        def retry_add_missing():
                            still_missing = [l for l in missing 
                                           if l.id() not in dockwidget.PROJECT_LAYERS]
                            if still_missing:
                                logger.warning(f"⚠️ Retrying add_layers for {len(still_missing)} layers")
                                dockwidget.app._pending_add_layers_tasks = 0
                                dockwidget.app.manage_task('add_layers', still_missing)
                        QTimer.singleShot(1000, retry_add_missing)
                    except Exception as e:
                        logger.error(f"Failed to auto-add missing layers: {e}")
            
            # Populate widget
            item_index = 0
            skipped_reasons = []  # DIAGNOSTIC v4.0.5
            for key in list(dockwidget.PROJECT_LAYERS.keys()):
                # Skip source layer
                if key == layer.id():
                    skipped_reasons.append(f"{key}: is source layer")
                    continue
                
                # Validate layer info
                if key not in dockwidget.PROJECT_LAYERS or "infos" not in dockwidget.PROJECT_LAYERS[key]:
                    skipped_reasons.append(f"{key}: missing infos")
                    continue
                
                layer_info = dockwidget.PROJECT_LAYERS[key]["infos"]
                required_keys = ["layer_id", "layer_name", "layer_crs_authid", "layer_geometry_type"]
                missing_keys = [k for k in required_keys if k not in layer_info or layer_info[k] is None]
                if missing_keys:
                    skipped_reasons.append(f"{key}: missing keys {missing_keys}")
                    continue
                
                # Reset subset history if needed
                if layer_info.get("is_already_subset") is False:
                    layer_info["subset_history"] = []
                
                layer_id = layer_info["layer_id"]
                layer_name = layer_info["layer_name"]
                layer_crs = layer_info["layer_crs_authid"]
                geom_type = layer_info["layer_geometry_type"]
                layer_icon = dockwidget.icon_per_geometry_type(geom_type)
                
                # DIAGNOSTIC: Log geometry type and icon validity
                logger.debug(f"populate_layers_checkable_combobox: layer='{layer_name}', geom_type='{geom_type}', icon_isNull={layer_icon.isNull() if layer_icon else 'None'}")
                
                # Validate layer is usable
                layer_obj = project.mapLayer(layer_id)
                if not layer_obj:
                    skipped_reasons.append(f"{layer_name}: layer_obj is None (not in project)")
                    continue
                if not isinstance(layer_obj, QgsVectorLayer):
                    skipped_reasons.append(f"{layer_name}: not QgsVectorLayer")
                    continue
                # v4.2: Skip non-spatial tables (tables without geometry)
                if not layer_obj.isSpatial():
                    skipped_reasons.append(f"{layer_name}: non-spatial table (no geometry)")
                    continue
                if not is_layer_source_available(layer_obj, require_psycopg2=False):
                    skipped_reasons.append(f"{layer_name}: source not available")
                    continue
                
                # Layer is valid - add to combobox
                display_name = f"{layer_name} [{layer_crs}]"
                item_data = {"layer_id": key, "layer_geometry_type": layer_info["layer_geometry_type"]}
                layers_widget.addItem(layer_icon, display_name, item_data)
                
                item = layers_widget.model().item(item_index)
                if has_layers and layer_id in layers_to_filter:
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
                item_index += 1
            
            # DIAGNOSTIC v4.0.5: Log skipped layers
            if skipped_reasons:
                logger.warning(f"🔍 DIAGNOSTIC: Skipped {len(skipped_reasons)} layers:")
                for reason in skipped_reasons:
                    logger.warning(f"   - {reason}")
            
            # FIX v4.1.3 (2026-01-18): Add missing layers directly to combobox (same as populate_export_combobox)
            # This ensures PostgreSQL and remote layers missing from PROJECT_LAYERS are still filterable
            from ...infrastructure.utils import geometry_type_to_string
            
            for missing_layer in missing:
                # v4.2: Skip non-spatial tables (tables without geometry)
                if missing_layer.isValid() and missing_layer.isSpatial() and is_layer_source_available(missing_layer, require_psycopg2=False):
                    display_name = f"{missing_layer.name()} [{missing_layer.crs().authid()}]"
                    geom_type_str = geometry_type_to_string(missing_layer)
                    layer_icon = dockwidget.icon_per_geometry_type(geom_type_str)
                    logger.debug(f"populate_layers_checkable_combobox [MISSING]: layer='{missing_layer.name()}', geom_type='{geom_type_str}', icon_isNull={layer_icon.isNull() if layer_icon else 'None'}")
                    item_data = {"layer_id": missing_layer.id(), "layer_geometry_type": geom_type_str}
                    layers_widget.addItem(layer_icon, display_name, item_data)
                    item = layers_widget.model().item(item_index)
                    # Check if this layer was previously selected for filtering
                    item.setCheckState(Qt.Checked if missing_layer.id() in layers_to_filter else Qt.Unchecked)
                    item_index += 1
                    logger.info(f"✓ populate_layers_checkable_combobox: Added missing layer '{missing_layer.name()}'")
            
            logger.info(f"✓ populate_layers_checkable_combobox: Added {item_index} layers (source layer '{layer.name()}' excluded)")
            logger.info(f"=== populate_layers_checkable_combobox END ===")
            return True
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"populate_layers_checkable_combobox failed: {e}")
            return False
    
    # === Predicate Configuration ===
    
    def get_predicate(self) -> PredicateType:
        """Get current spatial predicate."""
        return self._current_predicate
    
    def set_predicate(self, predicate: PredicateType) -> None:
        """
        Set spatial predicate.
        
        Args:
            predicate: Predicate type to use
        """
        if predicate == self._current_predicate:
            return
        
        self._current_predicate = predicate
        self._rebuild_expression()
        self._notify_config_changed()
    
    def get_available_predicates(self) -> List[PredicateType]:
        """Get list of available predicates."""
        return list(PredicateType)
    
    def on_predicate_changed(self, predicate_value: str) -> None:
        """
        Handle predicate change from UI.
        
        Args:
            predicate_value: Predicate value string
        """
        try:
            predicate = PredicateType(predicate_value)
            self.set_predicate(predicate)
        except ValueError:
            pass  # Invalid predicate, ignore
    
    # === Buffer Configuration ===
    
    def get_buffer_value(self) -> float:
        """Get current buffer value."""
        return self._buffer_value
    
    def set_buffer_value(self, value: float) -> None:
        """
        Set buffer value.
        
        Args:
            value: Buffer distance value
        """
        if value == self._buffer_value:
            return
        
        self._buffer_value = max(0.0, value)  # No negative buffers
        self._rebuild_expression()
        self._notify_config_changed()
    
    def get_buffer_type(self) -> BufferType:
        """Get current buffer type."""
        return self._buffer_type
    
    def set_buffer_type(self, buffer_type: BufferType) -> None:
        """
        Set buffer type.
        
        Args:
            buffer_type: Which layers to buffer
        """
        if buffer_type == self._buffer_type:
            return
        
        self._buffer_type = buffer_type
        self._rebuild_expression()
        self._notify_config_changed()
    
    def on_buffer_changed(self, value: float, buffer_type: str) -> None:
        """
        Handle buffer configuration change from UI.
        
        Args:
            value: Buffer distance
            buffer_type: Buffer type string
        """
        self._buffer_value = max(0.0, value)
        try:
            self._buffer_type = BufferType(buffer_type)
        except ValueError:
            self._buffer_type = BufferType.NONE
        
        self._rebuild_expression()
        self._notify_config_changed()
    
    # === Expression Management ===
    
    def get_expression(self) -> str:
        """Get current filter expression."""
        return self._current_expression
    
    def set_expression(self, expression: str) -> None:
        """
        Set filter expression directly.
        
        Args:
            expression: Filter expression string
        """
        if expression == self._current_expression:
            return
        
        self._current_expression = expression
        self._notify_expression_changed(expression)
    
    def _rebuild_expression(self) -> None:
        """Rebuild expression from current configuration."""
        expression = self._build_expression_string()
        self.set_expression(expression)
    
    def _build_expression_string(self) -> str:
        """
        Build expression string from current configuration.
        
        Returns:
            Filter expression string
        """
        if not self._source_layer or not self._target_layer_ids:
            return ""
        
        # Basic expression building - actual implementation 
        # would use the filter service
        parts = []
        
        predicate_name = self._current_predicate.value
        
        for target_id in self._target_layer_ids:
            if self._buffer_value > 0:
                part = f"{predicate_name}(buffer($geometry, {self._buffer_value}), layer:='{target_id}')"
            else:
                part = f"{predicate_name}($geometry, layer:='{target_id}')"
            parts.append(part)
        
        return " OR ".join(parts) if parts else ""
    
    def build_configuration(self) -> FilterConfiguration:
        """
        Build current configuration object.
        
        Returns:
            Current filter configuration
        """
        source_id = self._source_layer.id() if self._source_layer else None
        
        return FilterConfiguration(
            source_layer_id=source_id,
            target_layer_ids=self._target_layer_ids.copy(),
            predicate=self._current_predicate,
            buffer_value=self._buffer_value,
            buffer_type=self._buffer_type,
            expression=self._current_expression
        )
    
    def apply_configuration(self, config: FilterConfiguration) -> None:
        """
        Apply a saved configuration.
        
        Args:
            config: Configuration to apply
        """
        # Note: source_layer_id needs to be resolved to actual layer
        # This would be done via layer repository
        self._target_layer_ids = config.target_layer_ids.copy()
        self._current_predicate = config.predicate
        self._buffer_value = config.buffer_value
        self._buffer_type = config.buffer_type
        self._current_expression = config.expression
        
        self._notify_config_changed()
        self._notify_expression_changed(config.expression)
    
    # === Filter Execution ===
    
    def can_execute(self) -> bool:
        """
        Check if filter can be executed.
        
        Returns:
            True if configuration is valid for execution
        """
        if self._is_executing:
            return False
        
        config = self.build_configuration()
        return config.is_valid()
    
    def execute_filter(self) -> bool:
        """
        Execute the current filter.
        
        v3.0 Migration: This method is part of the Strangler Fig pattern.
        Currently it validates the configuration and prepares for execution,
        but returns False to let the legacy code path handle actual filtering.
        
        Future: When FilterService is fully integrated, this will:
        1. Build FilterRequest from configuration
        2. Call FilterService.apply_filter()
        3. Handle async completion
        
        Returns:
            True if execution handled by controller, False to use legacy
        """
        import logging
        logger = logging.getLogger('FilterMate.FilteringController')
        
        if not self.can_execute():
            logger.debug("FilteringController: cannot execute - validation failed")
            return False
        
        # Build configuration for logging/debugging
        config = self.build_configuration()
        
        # Check if FilterService is available
        if self._filter_service:
            logger.info(
                f"FilteringController: FilterService available, config valid. "
                f"source={config.source_layer_id}, targets={len(config.target_layer_ids)}, "
                f"predicate={config.predicate.value}"
            )
            
            # v3.0 MIG-024: Build task parameters using TaskParameterBuilder
            if TASK_BUILDER_AVAILABLE:
                task_params = self.build_task_parameters()
                if task_params:
                    logger.info(
                        f"FilteringController: TaskParameters built successfully. "
                        f"targets={len(task_params.target_layers)}, "
                        f"buffer={task_params.filtering_config.buffer_value if task_params.filtering_config else 0}"
                    )
                else:
                    logger.debug("FilteringController: TaskParameters build returned None")
            
            # v4.0 Note: FilterService integration requires additional work:
            # 1. FilterService.apply_filter() expects FilterRequest with domain objects
            # 2. The async task execution model (QgsTask) is currently in FilterEngineTask
            # 3. Full integration planned for v5.0 when FilterEngineTask is fully refactored
            # For now, delegate to legacy path which uses FilterEngineTask via TaskBuilder
            logger.debug("FilteringController: FilterService available but delegating to legacy (v4.0)")
            return False
        else:
            logger.debug("FilteringController: No FilterService, using legacy path")
            return False
    
    def execute_unfilter(self) -> bool:
        """
        Execute unfilter action - clear all filters on current and target layers.
        
        v4.0: Implements delegate_unfilter() TODO for controller delegation.
        Currently returns False to delegate to legacy code path.
        
        Returns:
            True if handled by controller, False to use legacy path
        """
        if not self._source_layer:
            logger.debug("FilteringController: No source layer for unfilter")
            return False
        
        # Log the unfilter request
        config = self.build_configuration()
        logger.info(
            f"FilteringController: Unfilter requested for source={self._source_layer.name()}, "
            f"targets={len(config.target_layer_ids)}"
        )
        
        # For now, return False to delegate to legacy FilterEngineTask.execute_unfiltering()
        # Future: Implement direct unfilter logic here using layer.setSubsetString('')
        return False
    
    def execute_reset_filters(self) -> bool:
        """
        Execute reset action - restore original filter state on all layers.
        
        v4.0: Implements delegate_reset() TODO for controller delegation.
        Currently returns False to delegate to legacy code path.
        
        Returns:
            True if handled by controller, False to use legacy path
        """
        if not self._source_layer:
            logger.debug("FilteringController: No source layer for reset")
            return False
        
        # Log the reset request
        config = self.build_configuration()
        logger.info(
            f"FilteringController: Reset filters requested for source={self._source_layer.name()}, "
            f"targets={len(config.target_layer_ids)}"
        )
        
        # For now, return False to delegate to legacy FilterEngineTask.execute_reseting()
        # Future: Implement direct reset logic here using history service
        return False
    
    def build_task_parameters(self) -> Optional['TaskParameters']:
        """
        Build TaskParameters using TaskParameterBuilder.
        
        This provides a clean way to construct filter parameters
        without directly accessing PROJECT_LAYERS.
        
        v3.0 MIG-024: Part of God Class reduction strategy.
        
        Returns:
            TaskParameters or None if building failed
        """
        if not TASK_BUILDER_AVAILABLE:
            return None
        
        if not self._dockwidget or not self._source_layer:
            return None
        
        try:
            # Get PROJECT_LAYERS from dockwidget
            project_layers = getattr(self._dockwidget, 'PROJECT_LAYERS', {})
            
            # Create builder
            builder = TaskParameterBuilder(
                dockwidget=self._dockwidget,
                project_layers=project_layers
            )
            
            # Get target layers from QGIS project
            from qgis.core import QgsProject
            project = QgsProject.instance()
            
            target_layers = []
            for layer_id in self._target_layer_ids:
                layer = project.mapLayer(layer_id)
                if layer and layer.isValid():
                    target_layers.append(layer)
            
            # Get current features and expression from dockwidget
            features = []
            expression = ""
            if hasattr(self._dockwidget, 'get_current_features'):
                features_list, expression = self._dockwidget.get_current_features()
                features = [f.id() for f in features_list] if features_list else []
            
            # Build parameters
            params = builder.build_filter_params(
                source_layer=self._source_layer,
                target_layers=target_layers,
                features=features,
                expression=expression
            )
            
            return params
            
        except Exception as e:
            import logging
            logging.getLogger('FilterMate.FilteringController').warning(
                f"Failed to build task parameters: {e}"
            )
            return None
    
    def _on_filter_success(self, config: FilterConfiguration) -> None:
        """Handle successful filter execution."""
        self._is_executing = False
        self._last_result = FilterResult(
            success=True,
            configuration=config
        )
        # Clear redo stack on successful new action
        self._redo_stack.clear()
    
    def _on_filter_error(self, error_message: str) -> None:
        """Handle filter execution error."""
        self._is_executing = False
        self._last_result = FilterResult(
            success=False,
            error_message=error_message
        )
        # Restore state from undo stack on error
        if self._undo_stack:
            self._undo_stack.pop()
    
    def get_last_result(self) -> Optional[FilterResult]:
        """Get result of last filter execution."""
        return self._last_result
    
    # === Undo/Redo ===
    
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return len(self._undo_stack) > 0
    
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return len(self._redo_stack) > 0
    
    def undo(self) -> bool:
        """
        Undo last filter operation.
        
        Returns:
            True if undo was performed
        """
        if not self.can_undo():
            return False
        
        # Save current state to redo stack
        current_config = self.build_configuration()
        self._redo_stack.append(current_config)
        
        # Restore previous state
        previous_config = self._undo_stack.pop()
        self.apply_configuration(previous_config)
        
        return True
    
    def redo(self) -> bool:
        """
        Redo last undone operation.
        
        Returns:
            True if redo was performed
        """
        if not self.can_redo():
            return False
        
        # Save current state to undo stack
        current_config = self.build_configuration()
        self._undo_stack.append(current_config)
        
        # Apply redo state
        redo_config = self._redo_stack.pop()
        self.apply_configuration(redo_config)
        
        return True
    
    def _save_to_undo_stack(self) -> None:
        """Save current state to undo stack."""
        config = self.build_configuration()
        self._undo_stack.append(config)
        
        # Limit stack size
        while len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)
    
    def clear_history(self) -> None:
        """Clear undo/redo history."""
        self._undo_stack.clear()
        self._redo_stack.clear()
    
    def get_undo_count(self) -> int:
        """Get number of undo steps available."""
        return len(self._undo_stack)
    
    def get_redo_count(self) -> int:
        """Get number of redo steps available."""
        return len(self._redo_stack)
    
    # === Callbacks/Notifications ===
    
    def register_expression_callback(self, callback: Callable[[str], None]) -> None:
        """Register callback for expression changes."""
        if callback not in self._on_expression_changed_callbacks:
            self._on_expression_changed_callbacks.append(callback)
    
    def unregister_expression_callback(self, callback: Callable[[str], None]) -> None:
        """Unregister expression change callback."""
        if callback in self._on_expression_changed_callbacks:
            self._on_expression_changed_callbacks.remove(callback)
    
    def register_config_callback(self, callback: Callable[[FilterConfiguration], None]) -> None:
        """Register callback for configuration changes."""
        if callback not in self._on_config_changed_callbacks:
            self._on_config_changed_callbacks.append(callback)
    
    def unregister_config_callback(self, callback: Callable[[FilterConfiguration], None]) -> None:
        """Unregister configuration change callback."""
        if callback in self._on_config_changed_callbacks:
            self._on_config_changed_callbacks.remove(callback)
    
    def _notify_expression_changed(self, expression: str) -> None:
        """Notify listeners of expression change."""
        for callback in self._on_expression_changed_callbacks:
            try:
                callback(expression)
            except Exception:
                pass  # Don't let callback errors break flow
    
    def _notify_config_changed(self) -> None:
        """Notify listeners of configuration change."""
        config = self.build_configuration()
        for callback in self._on_config_changed_callbacks:
            try:
                callback(config)
            except Exception:
                pass
    
    # === Lifecycle ===
    
    def setup(self) -> None:
        """Initialize the controller."""
        # Connect signals would happen here
        # For now, just initialize state
        # EPIC-3: Initialize raster context
        self._raster_exploring_context: Optional[Dict[str, Any]] = None
    
    def teardown(self) -> None:
        """Clean up the controller."""
        self._disconnect_all_signals()
        
        # Clear state
        self._source_layer = None
        self._target_layer_ids.clear()
        self._current_expression = ""
        
        # Clear history
        self.clear_history()
        
        # Clear callbacks
        self._on_expression_changed_callbacks.clear()
        self._on_config_changed_callbacks.clear()
    
    def on_tab_activated(self) -> None:
        """Called when filtering tab becomes active."""
        super().on_tab_activated()
        # Refresh layer lists if needed
    
    def on_tab_deactivated(self) -> None:
        """Called when filtering tab becomes inactive."""
        super().on_tab_deactivated()

    # =========================================================================
    # EPIC-3: Raster-Vector Integration - Exploring Context Handling
    # =========================================================================
    
    def on_exploring_context_changed(self, context: Dict[str, Any]) -> None:
        """
        EPIC-3: Handle context changes from EXPLORING panels (Vector or Raster).
        
        When the user interacts with EXPLORING (selects features, adjusts histogram,
        configures mask operations), the filter context is updated here.
        
        This enables bidirectional filtering:
        - Vector → Vector: Spatial predicates
        - Vector → Raster: Clip/Mask by geometry
        - Raster → Vector: Filter by underlying values
        - Raster → Raster: Value-based masking
        
        Args:
            context: Filter context from EXPLORING panel with keys:
                - source_type: 'vector' or 'raster'
                - mode: 'value_filter', 'spatial_operation', 'info_only', etc.
                - layer_id: Source layer ID
                - layer_name: Source layer name
                - For raster value_filter:
                    - band: Band number
                    - range_min, range_max: Value range
                    - predicate: Value predicate (within_range, etc.)
                    - pixel_count: Pixels in range
                - For raster spatial_operation:
                    - operation: clip, mask_outside, mask_inside, zonal_stats
                    - target_rasters: List of target raster IDs
                - For vector:
                    - feature_count: Number of selected features
                    - selection_mode: single, multiple, custom
        """
        if not context:
            logger.debug("EPIC-3: Empty context received, ignoring")
            return
        
        source_type = context.get('source_type')
        mode = context.get('mode')
        
        logger.info(f"EPIC-3: Exploring context changed - source_type={source_type}, mode={mode}")
        
        # Store context
        if source_type == 'raster':
            self._raster_exploring_context = context
            
            # EPIC-3: Configure RasterFilterService from context
            if self._raster_filter_service and RASTER_FILTER_AVAILABLE:
                self._configure_raster_filter_from_context(context)
        
        # Update UI based on context
        self._update_filtering_source_display(context)
        
        # Notify config changed
        self._notify_config_changed()
    
    def _configure_raster_filter_from_context(self, context: Dict[str, Any]) -> None:
        """
        EPIC-3: Configure RasterFilterService from exploring context.
        
        Args:
            context: Raster exploring context with filter parameters
        """
        if not self._raster_filter_service:
            return
        
        mode = context.get('mode')
        layer_id = context.get('layer_id')
        layer_name = context.get('layer_name', '')
        band = context.get('band', 1)
        band_name = context.get('band_name', f'Band {band}')
        
        # Set raster source
        if layer_id:
            self._raster_filter_service.set_raster_source(
                layer_id=layer_id,
                layer_name=layer_name,
                band=band,
                band_name=band_name
            )
        
        # Configure filter based on mode
        if mode == 'value_filter':
            range_min = context.get('range_min')
            range_max = context.get('range_max')
            predicate_str = context.get('predicate', 'within_range')
            
            if range_min is not None and range_max is not None:
                # Map string predicate to enum
                predicate_map = {
                    'within_range': RasterValuePredicate.WITHIN_RANGE,
                    'outside_range': RasterValuePredicate.OUTSIDE_RANGE,
                    'above_value': RasterValuePredicate.ABOVE_VALUE,
                    'below_value': RasterValuePredicate.BELOW_VALUE,
                    'equals_value': RasterValuePredicate.EQUALS_VALUE,
                    'is_nodata': RasterValuePredicate.IS_NODATA,
                    'is_not_nodata': RasterValuePredicate.IS_NOT_NODATA,
                }
                predicate = predicate_map.get(predicate_str, RasterValuePredicate.WITHIN_RANGE)
                
                self._raster_filter_service.set_value_range(
                    min_value=float(range_min),
                    max_value=float(range_max),
                    predicate=predicate
                )
                
                logger.info(
                    f"EPIC-3: Configured raster filter - "
                    f"range [{range_min}, {range_max}], predicate={predicate_str}"
                )
        
        elif mode == 'single_value':
            value = context.get('value')
            tolerance = context.get('tolerance', 0.01)
            if value is not None:
                self._raster_filter_service.set_single_value(
                    value=float(value),
                    tolerance=float(tolerance)
                )
        
        elif mode == 'nodata_filter':
            include_nodata = context.get('include_nodata', False)
            self._raster_filter_service.set_nodata_filter(include_nodata)
        
        # Set target layers if provided
        target_layers = context.get('target_layers', [])
        if target_layers:
            self._raster_filter_service.set_target_layers(target_layers)
    
    def _update_filtering_source_display(self, context: Dict[str, Any]) -> None:
        """
        EPIC-3: Update the FILTERING SOURCE panel display based on context.
        
        Args:
            context: Filter context from EXPLORING
        """
        try:
            dockwidget = self._dockwidget
            if not dockwidget:
                return
            
            source_type = context.get('source_type', 'unknown')
            mode = context.get('mode', 'unknown')
            layer_name = context.get('layer_name', 'Unknown')
            
            # EPIC-3: Update raster source frame indicator if available
            if hasattr(dockwidget, 'frame_raster_source_info'):
                if source_type == 'raster' and mode in ('value_filter', 'single_value', 'nodata_filter'):
                    band = context.get('band', 1)
                    band_name = context.get('band_name', f'Band {band}')
                    range_min = context.get('range_min')
                    range_max = context.get('range_max')
                    pixel_count = context.get('pixel_count', 0)
                    
                    # Build info text based on mode
                    if mode == 'value_filter' and range_min is not None and range_max is not None:
                        # Format numbers nicely
                        if isinstance(range_min, float):
                            range_min = f"{range_min:.2f}" if range_min != int(range_min) else str(int(range_min))
                        if isinstance(range_max, float):
                            range_max = f"{range_max:.2f}" if range_max != int(range_max) else str(int(range_max))
                        
                        info_text = f"<b>{layer_name}</b> • {band_name} • [{range_min}, {range_max}]"
                        if pixel_count > 0:
                            info_text += f" • {pixel_count:,} px"
                    elif mode == 'single_value':
                        value = context.get('value', '?')
                        info_text = f"<b>{layer_name}</b> • {band_name} • Value: {value}"
                    elif mode == 'nodata_filter':
                        include_nodata = context.get('include_nodata', False)
                        nodata_str = "NoData" if include_nodata else "Valid pixels"
                        info_text = f"<b>{layer_name}</b> • {band_name} • {nodata_str}"
                    else:
                        info_text = f"<b>{layer_name}</b> • {band_name}"
                    
                    dockwidget.lbl_raster_source_info.setText(info_text)
                    dockwidget.frame_raster_source_info.setVisible(True)
                    logger.debug(f"EPIC-3: Raster source display updated: {info_text}")
                else:
                    dockwidget.frame_raster_source_info.setVisible(False)
            
            logger.debug(
                f"EPIC-3: Updating source display - {source_type}/{mode}: {layer_name}"
            )
            
        except Exception as e:
            logger.warning(f"EPIC-3: Error updating source display: {e}")
    
    def get_raster_exploring_context(self) -> Optional[Dict[str, Any]]:
        """
        EPIC-3: Get the current raster exploring context.
        
        Returns:
            Current raster context or None
        """
        return self._raster_exploring_context
    
    def _connect_raster_filter_signals(self) -> None:
        """
        EPIC-3: Connect RasterFilterService signals to handlers.
        """
        if not self._raster_filter_service:
            return
        
        try:
            self._raster_filter_service.context_changed.connect(
                self._on_raster_filter_context_changed
            )
            self._raster_filter_service.filter_completed.connect(
                self._on_raster_filter_completed
            )
            self._raster_filter_service.filter_error.connect(
                self._on_raster_filter_error
            )
            self._raster_filter_service.filter_progress.connect(
                self._on_raster_filter_progress
            )
            # EPIC-3: Connect mask_created for Memory Clips integration
            self._raster_filter_service.mask_created.connect(
                self._on_raster_mask_created
            )
        except Exception as e:
            logger.warning(f"EPIC-3: Failed to connect raster filter signals: {e}")
    
    def _on_raster_filter_context_changed(self, context: Dict[str, Any]) -> None:
        """
        EPIC-3: Handle context changes from RasterFilterService.
        
        Args:
            context: Service context as dictionary
        """
        logger.debug(f"EPIC-3: Raster filter context changed: {context.get('mode')}")
        self._notify_config_changed()
    
    def _on_raster_filter_completed(self, result) -> None:
        """
        EPIC-3: Handle completion of raster filter operation.
        
        Args:
            result: RasterFilterResult from service
        """
        logger.info(
            f"EPIC-3: Raster filter completed - "
            f"{result.matching_count}/{result.total_features} features matched"
        )
        
        # Apply filter to matching features
        if result.matching_feature_ids and result.is_success:
            self._apply_raster_filter_result(result)
            
            # Show success message to user
            try:
                from qgis.utils import iface
                percentage = result.match_percentage
                iface.messageBar().pushSuccess(
                    "FilterMate",
                    f"Raster filter applied: {result.matching_count}/{result.total_features} features ({percentage:.1f}%)"
                )
            except Exception:
                pass  # Message bar optional
        elif not result.matching_feature_ids:
            # No matches found
            try:
                from qgis.utils import iface
                iface.messageBar().pushWarning(
                    "FilterMate",
                    f"No features match the raster value criteria"
                )
            except Exception:
                pass
    
    def _on_raster_filter_error(self, error_msg: str) -> None:
        """
        EPIC-3: Handle raster filter error.
        
        Args:
            error_msg: Error message from service
        """
        logger.error(f"EPIC-3: Raster filter error: {error_msg}")
        
        # Show error to user
        try:
            from qgis.utils import iface
            iface.messageBar().pushCritical(
                "FilterMate",
                f"Raster filter error: {error_msg}"
            )
        except Exception:
            pass
    
    def _on_raster_filter_progress(self, progress: int) -> None:
        """
        EPIC-3: Handle raster filter progress update.
        
        Args:
            progress: Progress percentage (0-100)
        """
        logger.debug(f"EPIC-3: Raster filter progress: {progress}%")
    
    def _on_raster_mask_created(self, result) -> None:
        """
        EPIC-3: Handle mask creation from RasterFilterService.
        
        Notifies the dockwidget to add the mask to Memory Clips.
        
        Args:
            result: RasterMaskResult from service
        """
        logger.info(
            f"EPIC-3: Mask created - {result.layer_name}, "
            f"{result.mask_percentage:.1f}% masked"
        )
        
        # Notify dockwidget to add to Memory Clips
        if hasattr(self._dockwidget, '_on_mask_created_for_memory_clips'):
            self._dockwidget._on_mask_created_for_memory_clips(result)
    
    def _apply_raster_filter_result(self, result) -> None:
        """
        EPIC-3: Apply raster filter result to vector layers.
        
        Creates a subset string expression to show only matching features.
        
        Args:
            result: RasterFilterResult with matching feature IDs
        """
        try:
            from qgis.core import QgsProject
            
            if not result.matching_feature_ids:
                logger.warning("EPIC-3: No matching features to filter")
                return
            
            # Build expression for matching feature IDs
            # Format: $id IN (1, 2, 3, ...)
            id_list = ', '.join(str(fid) for fid in result.matching_feature_ids)
            expression = f"$id IN ({id_list})"
            
            # Get target layers from service context
            if self._raster_filter_service:
                for layer_id in self._raster_filter_service.context.target_layers:
                    layer = QgsProject.instance().mapLayer(layer_id)
                    if layer:
                        layer.setSubsetString(expression)
                        logger.info(f"EPIC-3: Applied filter to {layer.name()}")
            
        except Exception as e:
            logger.error(f"EPIC-3: Failed to apply raster filter result: {e}")
    
    def execute_raster_filter(self, context: Optional[Dict[str, Any]] = None) -> None:
        """
        EPIC-3: Execute raster-based filtering using provided or current context.
        
        Uses RasterFilterService to filter vector features by raster values.
        
        Args:
            context: Optional filter context dictionary. If provided, configures
                     the service before executing. If None, uses current config.
        """
        if not self._raster_filter_service:
            logger.warning("EPIC-3: RasterFilterService not available")
            return
        
        # Configure service from context if provided
        if context:
            self._configure_raster_filter_from_context(context)
            
            # Set target layers from context
            target_layers = context.get('target_layers', [])
            if target_layers:
                self._raster_filter_service.set_target_layers(target_layers)
        
        if not self._raster_filter_service.is_ready():
            logger.warning("EPIC-3: RasterFilterService not ready - configure context first")
            return
        
        try:
            logger.info(f"EPIC-3: Executing raster filter - {self._raster_filter_service.get_status_summary()}")
            self._raster_filter_service.filter_features()
        except Exception as e:
            logger.error(f"EPIC-3: Raster filter execution failed: {e}")
    
    def get_raster_filter_service(self) -> Optional['RasterFilterService']:
        """
        EPIC-3: Get the raster filter service instance.
        
        Returns:
            RasterFilterService or None if not available
        """
        return self._raster_filter_service
    
    def compute_zonal_statistics(
        self,
        raster_layer: 'QgsRasterLayer',
        vector_layer: 'QgsVectorLayer',
        band_index: int = 1,
        statistics: list = None
    ) -> Optional[list]:
        """
        EPIC-3: Compute zonal statistics for vector features over raster.
        
        Calculates statistics (min, max, mean, std, sum, count) for each
        vector feature based on the underlying raster values.
        
        Args:
            raster_layer: Source raster layer
            vector_layer: Vector layer with zone polygons
            band_index: Raster band to analyze (1-based)
            statistics: List of statistics to compute (default: all)
            
        Returns:
            List of dicts with feature ID and computed statistics,
            or None if computation fails
        """
        if not self._raster_filter_service:
            logger.warning("EPIC-3: RasterFilterService not available for zonal stats")
            return None
        
        try:
            logger.info(f"EPIC-3: Computing zonal statistics for {vector_layer.name()} on {raster_layer.name()}")
            
            # Configure the service context with the raster layer
            self._raster_filter_service.update_context(
                raster_layer_id=raster_layer.id(),
                band=band_index
            )
            
            # Default statistics names for backend
            stats_names = statistics or ['min', 'max', 'mean', 'std', 'count', 'sum']
            
            # Use the service to compute - pass vector_layer_id
            results = self._raster_filter_service.compute_zonal_statistics(
                vector_layer_id=vector_layer.id(),
                statistics=stats_names
            )
            
            if results:
                logger.info(f"EPIC-3: Computed zonal stats for {len(results)} features")
                # Convert to list of dicts for dialog
                return [
                    {
                        'feature_id': r.feature_id,
                        'zone_name': r.zone_name,
                        'pixel_count': r.pixel_count,
                        'min': r.min_value,
                        'max': r.max_value,
                        'mean': r.mean_value,
                        'std_dev': r.std_dev,
                        'sum': r.sum_value
                    }
                    for r in results
                ]
            else:
                logger.warning("EPIC-3: No zonal statistics computed")
                return None
            
        except Exception as e:
            logger.error(f"EPIC-3: Error computing zonal statistics: {e}")
            import traceback
            traceback.print_exc()
            return None

    # === Reset ===
    
    def reset(self) -> None:
        """Reset all filter configuration."""
        self._source_layer = None
        self._target_layer_ids.clear()
        self._current_predicate = PredicateType.INTERSECTS
        self._buffer_value = 0.0
        self._buffer_type = BufferType.NONE
        self._current_expression = ""
        self._last_result = None
        
        self._notify_config_changed()
        self._notify_expression_changed("")
    
    # === Combine Operator Utilities (v3.1 STORY-2.4) ===
    
    def index_to_combine_operator(self, index: int) -> str:
        """
        Convert combobox index to SQL combine operator.
        
        v3.1 STORY-2.4: Centralized operator management.
        
        Args:
            index: Combobox index
            
        Returns:
            SQL operator string ('AND', 'AND NOT', 'OR')
        """
        return CombineOperator.from_index(index).value
    
    def combine_operator_to_index(self, operator: str) -> int:
        """
        Convert SQL combine operator to combobox index.
        
        v3.1 STORY-2.4: Handles translated operator values (ET, OU, NON)
        from older project files or when QGIS locale is non-English.
        
        Args:
            operator: SQL operator or translated equivalent
            
        Returns:
            Combobox index (0=AND, 1=AND NOT, 2=OR)
        """
        return CombineOperator.from_string(operator).to_index()
    
    # === State Change Handlers (v3.1 STORY-2.4) ===
    
    def on_layers_to_filter_state_changed(self, is_checked: bool) -> None:
        """
        Handle changes to the has_layers_to_filter checkable button.
        
        v3.1 STORY-2.4: Centralized state management.
        
        Args:
            is_checked: True if layers to filter option is enabled
        """
        import logging
        logger = logging.getLogger('FilterMate.FilteringController')
        logger.debug(f"on_layers_to_filter_state_changed: is_checked={is_checked}")
        
        # Store state for configuration
        self._has_layers_to_filter = is_checked
        self._notify_config_changed()
    
    def on_combine_operator_state_changed(self, is_checked: bool) -> None:
        """
        Handle changes to the has_combine_operator checkable button.
        
        v3.1 STORY-2.4: Centralized state management.
        
        Args:
            is_checked: True if combine operator option is enabled
        """
        import logging
        logger = logging.getLogger('FilterMate.FilteringController')
        logger.debug(f"on_combine_operator_state_changed: is_checked={is_checked}")
        
        self._has_combine_operator = is_checked
        self._notify_config_changed()
    
    def on_geometric_predicates_state_changed(self, is_checked: bool) -> None:
        """
        Handle changes to the has_geometric_predicates checkable button.
        
        v3.1 STORY-2.4: Centralized state management.
        
        Args:
            is_checked: True if geometric predicates option is enabled
        """
        import logging
        logger = logging.getLogger('FilterMate.FilteringController')
        logger.debug(f"on_geometric_predicates_state_changed: is_checked={is_checked}")
        
        self._has_geometric_predicates = is_checked
        self._notify_config_changed()
    
    def on_buffer_type_state_changed(self, is_checked: bool) -> None:
        """
        Handle changes to the has_buffer_type checkable button.
        
        v3.1 STORY-2.4: Centralized state management.
        
        Args:
            is_checked: True if buffer type option is enabled
        """
        import logging
        logger = logging.getLogger('FilterMate.FilteringController')
        logger.debug(f"on_buffer_type_state_changed: is_checked={is_checked}")
        
        self._has_buffer_type = is_checked
        self._notify_config_changed()

    def on_has_buffer_value_state_changed(self, is_checked: bool) -> None:
        """
        Handle changes to the has_buffer_value checkable button.
        
        v3.1 STORY-2.4: Centralized state management for buffer value option.
        
        Args:
            is_checked: True if buffer value option is enabled
        """
        import logging
        logger = logging.getLogger('FilterMate.FilteringController')
        logger.debug(f"on_has_buffer_value_state_changed: is_checked={is_checked}")
        
        self._has_buffer_value = is_checked
        self._notify_config_changed()

    def get_buffer_property_active(self) -> bool:
        """
        Get whether buffer property override is active.
        
        v3.1 STORY-2.4: Returns controller's tracking of buffer property state.
        
        Returns:
            True if buffer property override is active
        """
        return getattr(self, '_buffer_property_active', False)
    
    def set_buffer_property_active(self, is_active: bool) -> None:
        """
        Set buffer property override active state.
        
        v3.1 STORY-2.4: Tracks buffer property state in controller.
        
        Args:
            is_active: Whether buffer property override is active
        """
        import logging
        logger = logging.getLogger('FilterMate.FilteringController')
        logger.debug(f"set_buffer_property_active: is_active={is_active}")
        
        self._buffer_property_active = is_active
        self._notify_config_changed()

    def get_target_layer_ids(self) -> List[str]:
        """
        Get list of target layer IDs for filtering.
        
        v3.1 STORY-2.4: Returns the list of layers selected for filtering.
        
        Returns:
            List of layer IDs selected as filter targets
        """
        return self._target_layer_ids.copy()
    
    def set_target_layer_ids(self, layer_ids: List[str]) -> None:
        """
        Set target layer IDs for filtering.
        
        v3.1 STORY-2.4: Updates the list of layers to filter.
        
        Args:
            layer_ids: List of layer IDs to set as targets
        """
        import logging
        logger = logging.getLogger('FilterMate.FilteringController')
        
        if layer_ids == self._target_layer_ids:
            return
        
        self._target_layer_ids = layer_ids.copy() if layer_ids else []
        logger.debug(f"set_target_layer_ids: {len(self._target_layer_ids)} layers")
        
        self._rebuild_expression()
        self._notify_config_changed()

    # === Populate Data Methods ===
    
    def get_available_predicates(self) -> List[str]:
        """
        Get list of available geometric predicates for UI population.
        
        v3.1 STORY-2.4: Centralized predicate list.
        
        Returns:
            List of predicate display names for combobox
        """
        return ["Intersect", "Contain", "Disjoint", "Equal", "Touch", "Overlap", "Are within", "Cross"]
    
    def get_available_buffer_types(self) -> List[str]:
        """
        Get list of available buffer end cap types for UI population.
        
        v3.1 STORY-2.4: Centralized buffer type list.
        
        Returns:
            List of buffer type display names for combobox
        """
        return ["Round", "Flat", "Square"]
    
    def get_available_combine_operators(self) -> List[str]:
        """
        Get list of available combine operators for UI population.
        
        v3.1 STORY-2.4: Centralized operator list.
        
        Returns:
            List of operator display names for combobox
        """
        return ["AND", "AND NOT", "OR"]

    # === Multi-Step Filter Detection ===
    
    def detect_multi_step_filter(
        self,
        layer: 'QgsVectorLayer',
        layer_props: Dict[str, Any]
    ) -> bool:
        """
        Detect if source or distant layers already have a subsetString (existing filter).
        
        v4.0 Sprint 2: Migrated from dockwidget for centralized filtering logic.
        
        When existing filters are detected, automatically enable additive filter mode.
        Uses existing combinator params if set, otherwise defaults to AND operator.
        
        Args:
            layer: The current source layer
            layer_props: Layer properties dictionary from PROJECT_LAYERS
            
        Returns:
            bool: True if existing filters were detected and additive mode was enabled
        """
        import logging
        logger = logging.getLogger('FilterMate.FilteringController')
        
        try:
            has_existing_filter = False
            
            # Check source layer for existing subset
            if layer and hasattr(layer, 'subsetString'):
                source_subset = layer.subsetString()
                if source_subset and source_subset.strip():
                    has_existing_filter = True
                    logger.debug(
                        f"Multi-step filter detected: source layer '{layer.name()}' "
                        f"has subset: {source_subset[:50]}..."
                    )
            
            # Check distant layers (layers_to_filter) for existing subsets
            if not has_existing_filter:
                filtering_props = layer_props.get("filtering", {})
                if filtering_props.get("has_layers_to_filter", False):
                    layers_to_filter = filtering_props.get("layers_to_filter", [])
                    has_existing_filter = self._check_distant_layers_for_filters(
                        layers_to_filter, logger
                    )
            
            # If existing filters detected, enable additive filter
            if has_existing_filter:
                return self._enable_additive_mode(layer, layer_props, logger)
            
            return False
            
        except Exception as e:
            logger.debug(f"Error detecting multi-step filter: {e}")
            return False
    
    def _check_distant_layers_for_filters(
        self,
        layer_ids: List[str],
        logger: 'logging.Logger'
    ) -> bool:
        """
        Check if any distant layers have existing subsetString filters.
        
        Args:
            layer_ids: List of layer IDs to check
            logger: Logger instance
            
        Returns:
            bool: True if any distant layer has an existing filter
        """
        try:
            from qgis.core import QgsProject
        except ImportError:
            return False
        
        for layer_id in layer_ids:
            distant_layer = QgsProject.instance().mapLayer(layer_id)
            if distant_layer and hasattr(distant_layer, 'subsetString'):
                distant_subset = distant_layer.subsetString()
                if distant_subset and distant_subset.strip():
                    logger.debug(
                        f"Multi-step filter detected: distant layer "
                        f"'{distant_layer.name()}' has subset: {distant_subset[:50]}..."
                    )
                    return True
        return False
    
    def _enable_additive_mode(
        self,
        layer: 'QgsVectorLayer',
        layer_props: Dict[str, Any],
        logger: 'logging.Logger'
    ) -> bool:
        """
        Enable additive filter mode for multi-step filtering.
        
        Args:
            layer: The source layer
            layer_props: Layer properties dictionary
            logger: Logger instance
            
        Returns:
            bool: True if additive mode was enabled
        """
        filtering = layer_props.get("filtering", {})
        
        # Only update if not already enabled (preserve user choice)
        if filtering.get("has_combine_operator", False):
            return False
        
        # Enable additive mode
        layer_props["filtering"]["has_combine_operator"] = True
        
        # Use existing combinator params if set, otherwise default to AND
        if not filtering.get("source_layer_combine_operator"):
            layer_props["filtering"]["source_layer_combine_operator"] = "AND"
        if not filtering.get("other_layers_combine_operator"):
            layer_props["filtering"]["other_layers_combine_operator"] = "AND"
        
        # Update controller state
        self._has_additive_mode = True
        self._source_combine_operator = CombineOperator.AND
        self._distant_combine_operator = CombineOperator.AND
        
        logger.info(
            f"Multi-step filter auto-enabled for layer "
            f"'{layer.name()}' - existing filters detected"
        )
        return True

    # === String Representation ===
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        source = self._source_layer.name() if self._source_layer else "None"
        targets = len(self._target_layer_ids)
        predicate = self._current_predicate.value
        
        return (
            f"FilteringController("
            f"source={source}, "
            f"targets={targets}, "
            f"predicate={predicate}, "
            f"buffer={self._buffer_value}, "
            f"undo={len(self._undo_stack)}, "
            f"redo={len(self._redo_stack)})"
        )
    
    # === FIX 2026-01-16: Methods required by integration.py signal handlers ===
    
    def on_task_started(self, task_type: str) -> None:
        """
        Handle task started notification.
        
        Called by integration._on_launching_task() when a filter task starts.
        Can be used to update UI state (disable buttons, show progress).
        
        Args:
            task_type: Type of task started (e.g., 'filter', 'unfilter', 'reset')
        """
        logger.info(f"FilteringController: Task started: {task_type}")
        # Could disable filter buttons during task execution
        # Could show progress indicator
    
    def on_task_completed(self, task_type: str, success: bool) -> None:
        """
        Handle task completed notification.
        
        Called when a filter task completes.
        
        Args:
            task_type: Type of task that completed
            success: Whether task succeeded
        """
        logger.info(f"FilteringController: Task completed: {task_type}, success={success}")
        # Could re-enable filter buttons
        # Could update undo/redo stacks


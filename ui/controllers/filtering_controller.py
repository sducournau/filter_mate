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
            if not dockwidget or not dockwidget.widgets_initialized:
                logger.warning("populate_layers_checkable_combobox: widgets not initialized")
                return False
            
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
            missing = [l.name() for l in qgis_vector_layers if l.id() not in dockwidget.PROJECT_LAYERS]
            if missing:
                logger.warning(f"Layers in QGIS but NOT in PROJECT_LAYERS: {missing}")
            
            # Populate widget
            item_index = 0
            for key in list(dockwidget.PROJECT_LAYERS.keys()):
                # Skip source layer
                if key == layer.id():
                    continue
                
                # Validate layer info
                if key not in dockwidget.PROJECT_LAYERS or "infos" not in dockwidget.PROJECT_LAYERS[key]:
                    continue
                
                layer_info = dockwidget.PROJECT_LAYERS[key]["infos"]
                required_keys = ["layer_id", "layer_name", "layer_crs_authid", "layer_geometry_type"]
                if any(k not in layer_info or layer_info[k] is None for k in required_keys):
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
                if layer_obj and isinstance(layer_obj, QgsVectorLayer) and is_layer_source_available(layer_obj, require_psycopg2=False):
                    display_name = f"{layer_name} [{layer_crs}]"
                    item_data = {"layer_id": key, "layer_geometry_type": layer_info["layer_geometry_type"]}
                    layers_widget.addItem(layer_icon, display_name, item_data)
                    
                    item = layers_widget.model().item(item_index)
                    if has_layers and layer_id in layers_to_filter:
                        item.setCheckState(Qt.Checked)
                    else:
                        item.setCheckState(Qt.Unchecked)
                    item_index += 1
            
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

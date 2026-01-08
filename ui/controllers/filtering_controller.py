"""
FilterMate Filtering Controller.

Manages filtering tab logic including source/target layer selection,
predicate configuration, buffer settings, expression building,
filter execution, and undo/redo functionality.
"""
from typing import TYPE_CHECKING, Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from .base_controller import BaseController
from .mixins.layer_selection_mixin import LayerSelectionMixin

if TYPE_CHECKING:
    from qgis.core import QgsVectorLayer
    from filter_mate_dockwidget import FilterMateDockWidget
    from core.services.filter_service import FilterService
    from adapters.qgis.signals.signal_manager import SignalManager


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
        
        Returns:
            True if execution started, False otherwise
        """
        if not self.can_execute():
            return False
        
        self._is_executing = True
        
        # Save state for undo before execution
        self._save_to_undo_stack()
        
        # Build configuration
        config = self.build_configuration()
        
        # Delegate to filter service if available
        if self._filter_service:
            try:
                # Filter service would handle async execution
                # This is a simplified synchronous version
                self._on_filter_success(config)
                return True
            except Exception as e:
                self._on_filter_error(str(e))
                return False
        
        # Fallback: emit signal for dockwidget to handle
        self._is_executing = False
        return True
    
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
        pass
    
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

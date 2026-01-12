"""
Undo/Redo Handler
=================

Extracted from filter_mate_app.py (MIG-024) for God Class reduction.

Handles undo/redo operations for filter states with support for:
- Single layer undo/redo
- Global (multi-layer) undo/redo
- Combobox state protection during async operations

Author: FilterMate Team
Version: 2.8.6
"""

import time
import weakref
from typing import Optional, Dict, Callable, List

try:
    from qgis.core import QgsProject, QgsVectorLayer
    from qgis.PyQt.QtCore import QTimer
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False
    QTimer = None

try:
    from ..infrastructure.logging import get_logger
except ImportError:
    import logging
    def get_logger(name):
        return logging.getLogger(name)

try:
    from ..infrastructure.utils.object_safety import (
        safe_set_subset_string,
        is_layer_source_available
    )
except ImportError:
    # Mocks for testing
    def safe_set_subset_string(layer, expr):
        if hasattr(layer, 'setSubsetString'):
            layer.setSubsetString(expr)
        return True
    def is_layer_source_available(layer):
        return layer is not None

logger = get_logger(__name__)


class UndoRedoHandler:
    """
    Handles undo/redo operations for filter states.
    
    Supports both single-layer and global (multi-layer) undo/redo,
    with protection mechanisms for combobox state during async operations.
    
    Extracted from FilterMateApp to reduce God Class complexity.
    """
    
    def __init__(
        self,
        history_manager,
        get_project_layers: Callable[[], Dict],
        get_project: Callable,
        get_iface: Callable,
        refresh_layers_callback: Callable,
        show_warning_callback: Optional[Callable[[str, str], None]] = None
    ):
        """
        Initialize UndoRedoHandler.
        
        Args:
            history_manager: HistoryManager instance for undo/redo state
            get_project_layers: Callback to get PROJECT_LAYERS dict
            get_project: Callback to get QgsProject instance
            get_iface: Callback to get QGIS iface
            refresh_layers_callback: Callback to refresh layers and canvas
            show_warning_callback: Optional callback to show warning messages
        """
        self._history_manager = history_manager
        self._get_project_layers = get_project_layers
        self._get_project = get_project
        self._get_iface = get_iface
        self._refresh_layers = refresh_layers_callback
        self._show_warning = show_warning_callback or self._default_warning
        
    def _default_warning(self, title: str, message: str):
        """Default warning handler using logger."""
        logger.warning(f"{title}: {message}")
    
    def update_button_states(
        self,
        current_layer: Optional['QgsVectorLayer'],
        layers_to_filter: List[str],
        undo_button,
        redo_button
    ) -> None:
        """
        Update undo/redo button states based on history availability.
        
        Args:
            current_layer: Currently selected layer
            layers_to_filter: List of remote layer IDs to filter
            undo_button: QPushButton for undo action
            redo_button: QPushButton for redo action
        """
        if not undo_button or not redo_button:
            return
        
        if not current_layer:
            undo_button.setEnabled(False)
            redo_button.setEnabled(False)
            return
        
        project_layers = self._get_project_layers()
        if current_layer.id() not in project_layers:
            logger.debug(f"update_button_states: layer {current_layer.name()} not in PROJECT_LAYERS")
            undo_button.setEnabled(False)
            redo_button.setEnabled(False)
            return
        
        has_remote_layers = bool(layers_to_filter)
        
        if has_remote_layers:
            # Global history mode - use global undo/redo availability
            can_undo = self._history_manager.can_undo
            can_redo = self._history_manager.can_redo
        else:
            # Source layer only mode - check if any history entries affect this layer
            layer_history = self._history_manager.get_history_for_layer(current_layer.id())
            can_undo = len(layer_history) > 0 and self._history_manager.can_undo
            can_redo = self._history_manager.can_redo
        
        undo_button.setEnabled(can_undo)
        redo_button.setEnabled(can_redo)
        
        logger.debug(f"Updated undo/redo buttons - undo: {can_undo}, redo: {can_redo}")
    
    def handle_undo(
        self,
        source_layer: 'QgsVectorLayer',
        layers_to_filter: List[str],
        use_global: bool,
        dockwidget=None
    ) -> bool:
        """
        Handle undo operation with intelligent layer selection logic.
        
        Args:
            source_layer: The source layer for the undo operation
            layers_to_filter: List of remote layer IDs
            use_global: Whether to use global (multi-layer) undo
            dockwidget: Optional dockwidget for combobox protection
            
        Returns:
            bool: True if undo was successful, False otherwise
        """
        if not source_layer:
            logger.warning("No current layer for undo")
            return False
        
        # Guard: ensure layer is usable
        if not is_layer_source_available(source_layer):
            logger.warning("handle_undo: source layer invalid or source missing")
            self._show_warning(
                "FilterMate",
                "Impossible d'annuler: couche invalide ou source introuvable."
            )
            return False
        
        project_layers = self._get_project_layers()
        if source_layer.id() not in project_layers:
            logger.warning(f"handle_undo: layer {source_layer.name()} not in PROJECT_LAYERS")
            return False
        
        has_remote_layers = bool(layers_to_filter)
        use_global_undo = use_global and has_remote_layers
        
        if use_global_undo:
            result = self._perform_global_undo(source_layer, project_layers)
        else:
            result = self._perform_layer_undo(source_layer, project_layers)
        
        # Set up combobox protection if dockwidget provided
        if dockwidget and result:
            self._setup_combobox_protection(dockwidget, source_layer, "undo")
        
        return result
    
    def handle_redo(
        self,
        source_layer: 'QgsVectorLayer',
        layers_to_filter: List[str],
        use_global: bool,
        dockwidget=None
    ) -> bool:
        """
        Handle redo operation with intelligent layer selection logic.
        
        Args:
            source_layer: The source layer for the redo operation
            layers_to_filter: List of remote layer IDs
            use_global: Whether to use global (multi-layer) redo
            dockwidget: Optional dockwidget for combobox protection
            
        Returns:
            bool: True if redo was successful, False otherwise
        """
        if not source_layer:
            logger.warning("No current layer for redo")
            return False
        
        # Guard: ensure layer is usable
        if not is_layer_source_available(source_layer):
            logger.warning("handle_redo: source layer invalid or source missing")
            self._show_warning(
                "FilterMate",
                "Impossible de rétablir: couche invalide ou source introuvable."
            )
            return False
        
        project_layers = self._get_project_layers()
        if source_layer.id() not in project_layers:
            logger.warning(f"handle_redo: layer {source_layer.name()} not in PROJECT_LAYERS")
            return False
        
        has_remote_layers = bool(layers_to_filter)
        use_global_redo = use_global and has_remote_layers
        
        if use_global_redo and self._history_manager.can_redo:
            result = self._perform_global_redo(source_layer, project_layers)
        else:
            result = self._perform_layer_redo(source_layer, project_layers)
        
        # Set up combobox protection if dockwidget provided
        if dockwidget and result:
            self._setup_combobox_protection(dockwidget, source_layer, "redo")
        
        return result
    
    def _perform_global_undo(
        self,
        source_layer: 'QgsVectorLayer',
        project_layers: Dict
    ) -> bool:
        """Perform global undo affecting all filtered layers."""
        logger.info("Performing global undo (remote layers are filtered)")
        history_entry = self._history_manager.undo()
        
        if not history_entry:
            logger.info("No global undo history available")
            return False
        
        # Restore previous filters for all affected layers
        restored_layers = []
        for layer_id, previous_filter in history_entry.previous_filters:
            if layer_id in project_layers:
                layer = project_layers[layer_id].get("layer")
                if layer:
                    safe_set_subset_string(layer, previous_filter)
                    project_layers[layer_id]["infos"]["is_already_subset"] = bool(previous_filter)
                    restored_layers.append(layer)
                    expr_preview = previous_filter[:60] if previous_filter else 'no filter'
                    logger.info(f"Restored layer {layer.name()}: {expr_preview}")
        
        # Refresh all affected layers
        self._refresh_affected_layers(source_layer, restored_layers)
        
        logger.info(f"Global undo completed - restored {len(restored_layers)} layers")
        return True
    
    def _perform_global_redo(
        self,
        source_layer: 'QgsVectorLayer',
        project_layers: Dict
    ) -> bool:
        """Perform global redo affecting all filtered layers."""
        logger.info("Performing global redo")
        history_entry = self._history_manager.redo()
        
        if not history_entry:
            logger.info("No global redo history available")
            return False
        
        # Apply the filter expression to all affected layers
        restored_layers = []
        for layer_id in history_entry.layer_ids:
            if layer_id in project_layers:
                layer = project_layers[layer_id].get("layer")
                if layer:
                    safe_set_subset_string(layer, history_entry.expression)
                    project_layers[layer_id]["infos"]["is_already_subset"] = bool(history_entry.expression)
                    restored_layers.append(layer)
                    expr_preview = history_entry.expression[:60] if history_entry.expression else 'no filter'
                    logger.info(f"Redone layer {layer.name()}: {expr_preview}")
        
        # Refresh all affected layers
        self._refresh_affected_layers(source_layer, restored_layers)
        
        logger.info(f"Global redo completed - restored {len(restored_layers)} layers")
        return True
        
        logger.info(f"Global redo completed - restored {len(restored_layers) + 1} layers")
        return True
    
    def _perform_layer_undo(
        self,
        source_layer: 'QgsVectorLayer',
        project_layers: Dict
    ) -> bool:
        """Perform undo for source layer only."""
        logger.info("Performing source layer undo only")
        
        # Check if there's any history that affects this layer
        layer_history = self._history_manager.get_history_for_layer(source_layer.id())
        if not layer_history or not self._history_manager.can_undo:
            logger.info("No undo history for source layer")
            return False
        
        previous_state = self._history_manager.undo()
        if not previous_state:
            return False
        
        # Find the previous filter for this specific layer
        previous_expression = ""
        for layer_id, expr in previous_state.previous_filters:
            if layer_id == source_layer.id():
                previous_expression = expr
                break
        
        safe_set_subset_string(source_layer, previous_expression)
        project_layers[source_layer.id()]["infos"]["is_already_subset"] = bool(previous_expression)
        logger.info(f"Undo source layer to: {previous_state.description}")
        
        # Refresh
        self._refresh_layers(source_layer)
        return True
    
    def _perform_layer_redo(
        self,
        source_layer: 'QgsVectorLayer',
        project_layers: Dict
    ) -> bool:
        """Perform redo for source layer only."""
        logger.info("Performing source layer redo only")
        
        if not self._history_manager.can_redo:
            logger.info("No redo history for source layer")
            return False
        
        next_state = self._history_manager.redo()
        if not next_state:
            return False
        
        # Apply the expression from the redo entry
        safe_set_subset_string(source_layer, next_state.expression)
        project_layers[source_layer.id()]["infos"]["is_already_subset"] = bool(next_state.expression)
        logger.info(f"Redo source layer to: {next_state.description}")
        
        # Refresh
        self._refresh_layers(source_layer)
        return True
    
    def _restore_remote_layers(
        self,
        global_state,
        project_layers: Dict
    ) -> List:
        """Restore remote layers from global state."""
        restored_layers = []
        project = self._get_project()
        
        for remote_id, (expression, _) in global_state.remote_layers.items():
            if remote_id not in project_layers:
                logger.warning(f"Remote layer {remote_id} no longer exists, skipping")
                continue
            
            remote_layer = project.mapLayer(remote_id)
            if not remote_layer:
                logger.warning(f"Remote layer {remote_id} not found in project")
                continue
            
            if not is_layer_source_available(remote_layer):
                logger.warning(f"Skipping remote layer '{remote_layer.name()}' (invalid or missing source)")
                continue
            
            safe_set_subset_string(remote_layer, expression)
            project_layers[remote_id]["infos"]["is_already_subset"] = bool(expression)
            expr_preview = expression[:60] if expression else 'no filter'
            logger.info(f"Restored remote layer {remote_layer.name()}: {expr_preview}")
            restored_layers.append(remote_layer)
        
        return restored_layers
    
    def _refresh_affected_layers(
        self,
        source_layer: 'QgsVectorLayer',
        remote_layers: List
    ) -> None:
        """Refresh all affected layers and canvas."""
        source_layer.updateExtents()
        source_layer.triggerRepaint()
        
        for remote_layer in remote_layers:
            remote_layer.updateExtents()
            remote_layer.triggerRepaint()
        
        iface = self._get_iface()
        if iface and hasattr(iface, 'mapCanvas'):
            iface.mapCanvas().refreshAllLayers()
            iface.mapCanvas().refresh()
    
    def _setup_combobox_protection(
        self,
        dockwidget,
        source_layer: 'QgsVectorLayer',
        operation: str
    ) -> None:
        """
        Set up combobox protection to prevent async signal interference.
        
        Args:
            dockwidget: The dockwidget containing the combobox
            source_layer: The layer that should remain selected
            operation: 'undo' or 'redo' for logging
        """
        if not QGIS_AVAILABLE or not QTimer:
            return
        
        dockwidget._filter_completed_time = time.time()
        
        if not source_layer:
            return
        
        dockwidget._saved_layer_id_before_filter = source_layer.id()
        saved_layer_id = source_layer.id()
        
        # Create weak reference to dockwidget
        weak_dockwidget = weakref.ref(dockwidget)
        
        def restore_combobox_if_needed():
            """Check and restore combobox to saved layer if it was changed."""
            try:
                dw = weak_dockwidget()
                if not dw:
                    return
                
                saved_layer = QgsProject.instance().mapLayer(saved_layer_id)
                if not saved_layer or not saved_layer.isValid():
                    return
                
                current_combo = dw.comboBox_filtering_current_layer.currentLayer()
                if not current_combo or current_combo.id() != saved_layer.id():
                    current_name = current_combo.name() if current_combo else "(None)"
                    logger.debug(f"DELAYED CHECK - Restoring from '{current_name}' to '{saved_layer.name()}'")
                    dw.comboBox_filtering_current_layer.blockSignals(True)
                    dw.comboBox_filtering_current_layer.setLayer(saved_layer)
                    dw.comboBox_filtering_current_layer.blockSignals(False)
                    dw.current_layer = saved_layer
            except Exception as e:
                logger.debug(f"Error in delayed {operation} combobox check: {e}")
        
        # Schedule multiple checks to catch async signal-triggered changes
        for delay in [200, 600, 1000, 1500, 2000]:
            QTimer.singleShot(delay, restore_combobox_if_needed)
        
        logger.info(f"handle_{operation} - Scheduled 5 delayed combobox verification checks")
        logger.info(f"handle_{operation} - 2000ms protection window enabled")
    
    def clear_filter_history(
        self,
        source_layer: 'QgsVectorLayer',
        remote_layer_ids: Optional[List[str]] = None
    ) -> None:
        """
        Clear filter history for source and associated layers.
        
        Args:
            source_layer: Source layer whose history to clear
            remote_layer_ids: Optional list of remote layer IDs
        """
        # Clear all history (HistoryService has a single global history)
        cleared_count = self._history_manager.clear()
        logger.info(f"Cleared {cleared_count} filter history entries")
    
    def push_filter_to_history(
        self,
        source_layer: 'QgsVectorLayer',
        task_parameters: Dict,
        feature_count: int,
        provider_type: str,
        layer_count: int
    ) -> None:
        """
        Push filter state to history for source and associated layers.
        
        Extracted from FilterMateApp._push_filter_to_history().
        
        Args:
            source_layer: Source layer being filtered
            task_parameters: Task parameters containing layers info
            feature_count: Number of features in filtered result
            provider_type: Backend provider type
            layer_count: Number of layers affected
        """
        # Save source layer state to history
        history = self._history_manager.get_or_create_history(source_layer.id())
        filter_expression = source_layer.subsetString()
        
        if len(filter_expression) > 60:
            description = f"Filter: {filter_expression[:60]}..."
        else:
            description = f"Filter: {filter_expression}"
        
        history.push_state(
            expression=filter_expression,
            feature_count=feature_count,
            description=description,
            metadata={"backend": provider_type, "operation": "filter", "layer_count": layer_count}
        )
        
        history_pos = history._current_index + 1 if hasattr(history, '_current_index') else '?'
        history_len = len(history._states) if hasattr(history, '_states') else '?'
        logger.info(f"Pushed filter state to history for source layer (position {history_pos}/{history_len})")
        
        # Collect and save remote layers state
        remote_layers_info = self._collect_remote_layers_history(task_parameters, provider_type)
        
        # Push global state if we have remote layers
        if remote_layers_info:
            self._history_manager.push_global_state(
                source_layer_id=source_layer.id(),
                source_expression=filter_expression,
                source_feature_count=feature_count,
                remote_layers=remote_layers_info,
                description=f"Global filter: {len(remote_layers_info) + 1} layers",
                metadata={"backend": provider_type, "operation": "filter"}
            )
            logger.info(f"Pushed global filter state ({len(remote_layers_info) + 1} layers)")
    
    def _collect_remote_layers_history(
        self,
        task_parameters: Dict,
        provider_type: str
    ) -> Dict[str, tuple]:
        """
        Collect and save history for remote layers.
        
        Args:
            task_parameters: Task parameters containing layers info
            provider_type: Default provider type
            
        Returns:
            Dict mapping layer_id to (filter_expression, feature_count) tuple
        """
        remote_layers_info = {}
        project = self._get_project()
        project_layers = self._get_project_layers()
        
        for layer_props in task_parameters.get("task", {}).get("layers", []):
            layer_id = layer_props.get("layer_id")
            layer_name = layer_props.get("layer_name")
            
            if not layer_id or layer_id not in project_layers:
                continue
            
            # Find the layer in the project
            assoc_layer = project.mapLayer(layer_id)
            if not assoc_layer:
                continue
            
            # Push state to layer history
            assoc_history = self._history_manager.get_or_create_history(layer_id)
            assoc_filter = assoc_layer.subsetString()
            assoc_count = assoc_layer.featureCount()
            
            if len(assoc_filter) > 60:
                assoc_desc = f"Filter: {assoc_filter[:60]}..."
            else:
                assoc_desc = f"Filter: {assoc_filter}"
            
            assoc_history.push_state(
                expression=assoc_filter,
                feature_count=assoc_count,
                description=assoc_desc,
                metadata={
                    "backend": layer_props.get("layer_provider_type", provider_type),
                    "operation": "filter"
                }
            )
            logger.info(f"Pushed filter state to history for layer {layer_name}")
            
            # Add to remote layers info for global history
            remote_layers_info[layer_id] = (assoc_filter, assoc_count)
        
        return remote_layers_info

    def initialize_filter_history(
        self,
        current_layer: 'QgsVectorLayer',
        layers_to_filter: List[Dict],
        task_parameters: Dict
    ) -> None:
        """
        Initialize filter history for source and associated layers.
        
        Captures the CURRENT state of all layers BEFORE filtering is applied.
        This ensures that undo will properly restore all layers to their pre-filter state.
        
        Extracted from FilterMateApp._initialize_filter_history() in Sprint 16.
        
        Args:
            current_layer: Source layer
            layers_to_filter: List of layers to be filtered
            task_parameters: Task parameters with layer info
        """
        project_layers = self._get_project_layers()
        project = self._get_project()
        
        # Initialize per-layer history for source layer if needed
        history = self._history_manager.get_or_create_history(current_layer.id())
        if len(history._states) == 0:
            current_filter = current_layer.subsetString()
            current_count = current_layer.featureCount()
            history.push_state(
                expression=current_filter,
                feature_count=current_count,
                description="Initial state (before first filter)",
                metadata={
                    "operation": "initial",
                    "backend": task_parameters["infos"].get("layer_provider_type", "unknown")
                }
            )
            logger.info(f"FilterMate: Initialized history with current state for source layer {current_layer.id()}")
        
        # Initialize per-layer history for associated layers
        remote_layers_info = {}
        for layer_info in layers_to_filter:
            layer_id = layer_info.get("layer_id")
            if layer_id and layer_id in project_layers:
                assoc_layers = [l for l in project.mapLayers().values() if l.id() == layer_id]
                if len(assoc_layers) == 1:
                    assoc_layer = assoc_layers[0]
                    assoc_history = self._history_manager.get_or_create_history(assoc_layer.id())
                    if len(assoc_history._states) == 0:
                        assoc_filter = assoc_layer.subsetString()
                        assoc_count = assoc_layer.featureCount()
                        assoc_history.push_state(
                            expression=assoc_filter,
                            feature_count=assoc_count,
                            description="Initial state (before first filter)",
                            metadata={
                                "operation": "initial",
                                "backend": layer_info.get("layer_provider_type", "unknown")
                            }
                        )
                        logger.info(f"FilterMate: Initialized history for associated layer {assoc_layer.name()}")
                    
                    # Collect CURRENT state for all remote layers (for global state)
                    remote_layers_info[assoc_layer.id()] = (assoc_layer.subsetString(), assoc_layer.featureCount())
        
        # ALWAYS push global state BEFORE filtering if we have remote layers
        if remote_layers_info:
            current_filter = current_layer.subsetString()
            current_count = current_layer.featureCount()
            self._history_manager.push_global_state(
                source_layer_id=current_layer.id(),
                source_expression=current_filter,
                source_feature_count=current_count,
                remote_layers=remote_layers_info,
                description=f"Pre-filter state ({len(remote_layers_info) + 1} layers)",
                metadata={
                    "operation": "pre_filter",
                    "backend": task_parameters["infos"].get("layer_provider_type", "unknown")
                }
            )
            logger.info(f"FilterMate: Captured pre-filter global state ({len(remote_layers_info) + 1} layers)")

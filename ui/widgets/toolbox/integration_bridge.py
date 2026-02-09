# -*- coding: utf-8 -*-
"""
FilterMate - QToolBox Integration Bridge

DEPRECATED (v6.0 Phase 1.5): This module is part of the dual toolbox system
planned for complete removal in Phase 6. Contains 6 hardcoded TODO placeholders
(selection_type, selection_value, predicate, band, data_type) that will not be
resolved since the entire ui/widgets/toolbox/ package will be removed.

This module provides the bridge between the new Dual QToolBox architecture
and the existing FilterMate dockwidget. It handles:
- Signal routing between old and new components
- Auto-switch logic based on current layer type
- Backward compatibility with existing controllers
"""

from qgis.PyQt.QtCore import QObject, pyqtSignal, pyqtSlot, Qt
from qgis.PyQt.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSplitter

from qgis.core import (
    QgsVectorLayer,
    QgsRasterLayer,
    QgsProject,
    QgsMapLayerType
)

from .exploring_toolbox import (
    ExploringToolBox,
    VectorExploringPage,
    RasterExploringPage
)
from .toolset_toolbox import ToolsetToolBox

import logging
logger = logging.getLogger('FilterMate.ToolBoxBridge')


class ToolBoxIntegrationBridge(QObject):
    """Bridge between new QToolBox widgets and existing FilterMate components.
    
    This bridge handles:
    - Routing signals from QToolBox pages to existing handlers
    - Converting selection info to/from old format
    - Managing auto-switch behavior
    - Maintaining backward compatibility
    
    Signals:
        vectorFilterRequested: Emitted when a vector filter is requested
        rasterFilterRequested: Emitted when a raster filter is requested
        exportRequested: Emitted when export is requested
        configChanged: Emitted when configuration changes
        layerSwitched: Emitted when layer type switches (vector/raster)
    """
    
    # Bridge signals (connect to existing handlers)
    vectorFilterRequested = pyqtSignal(dict)  # selection_info
    rasterFilterRequested = pyqtSignal(dict)  # raster_info
    exportRequested = pyqtSignal(dict)  # export_settings
    configChanged = pyqtSignal(str, object)  # key, value
    layerSwitched = pyqtSignal(str)  # 'vector' or 'raster'
    undoRequested = pyqtSignal()
    redoRequested = pyqtSignal()
    resetAllFiltersRequested = pyqtSignal()
    
    def __init__(self, exploring_toolbox: ExploringToolBox, toolset_toolbox: ToolsetToolBox, parent=None):
        """Initialize the integration bridge.
        
        Args:
            exploring_toolbox: The EXPLORING QToolBox instance
            toolset_toolbox: The TOOLSET QToolBox instance
            parent: Parent QObject
        """
        super().__init__(parent)
        
        self._exploring = exploring_toolbox
        self._toolset = toolset_toolbox
        self._current_layer = None
        self._current_layer_type = None  # 'vector' or 'raster'
        self._auto_switch_enabled = True
        
        self._connect_signals()
    
    def _connect_signals(self):
        """Connect all internal signals."""
        # EXPLORING signals
        self._exploring.layerTypeChanged.connect(self._on_layer_type_changed)
        self._exploring.filterRequested.connect(self._on_filter_requested)
        self._exploring.clearRequested.connect(self._on_clear_requested)
        self._exploring.vectorSelectionChanged.connect(self._on_vector_selection_changed)
        self._exploring.rasterRangeChanged.connect(self._on_raster_range_changed)
        
        # TOOLSET signals
        self._toolset.filterRequested.connect(self._on_execute_filter)
        self._toolset.exportRequested.connect(self._on_export_requested)
        self._toolset.configChanged.connect(self._on_config_changed)
        
        # Filtering page specific signals
        filtering_page = self._toolset.get_filtering_page()
        filtering_page.undoRequested.connect(self.undoRequested)
        filtering_page.redoRequested.connect(self.redoRequested)
        filtering_page.resetRequested.connect(self.resetAllFiltersRequested)
        
        # Configuration page signals
        config_page = self._toolset.get_configuration_page()
        config_page.saveRequested.connect(self._on_save_config)
        config_page.resetRequested.connect(self._on_reset_config)
    
    def set_auto_switch(self, enabled: bool):
        """Enable or disable auto-switch behavior.
        
        Args:
            enabled: Whether to auto-switch EXPLORING page based on layer type
        """
        self._auto_switch_enabled = enabled
        self._exploring.set_auto_switch(enabled)
    
    def is_auto_switch_enabled(self) -> bool:
        """Check if auto-switch is enabled."""
        return self._auto_switch_enabled
    
    def set_current_layer(self, layer):
        """Set the current active layer.
        
        This triggers auto-switch if enabled and the layer type changes.
        
        Args:
            layer: The current layer (QgsVectorLayer or QgsRasterLayer)
        """
        self._current_layer = layer
        
        if layer is None:
            return
        
        # Determine layer type
        if isinstance(layer, QgsVectorLayer):
            new_type = 'vector'
        elif isinstance(layer, QgsRasterLayer):
            new_type = 'raster'
        else:
            return
        
        # Auto-switch if type changed
        if new_type != self._current_layer_type:
            self._current_layer_type = new_type
            
            if self._auto_switch_enabled:
                self._exploring.switch_to_layer_type(new_type)
            
            self.layerSwitched.emit(new_type)
        
        # Update toolset source
        self._update_toolset_source()
    
    def _update_toolset_source(self):
        """Update the TOOLSET filtering page with current source info."""
        if not self._current_layer:
            return
        
        selection_info = self._get_current_selection_info()
        self._toolset.set_source(self._current_layer, selection_info)
    
    def _get_current_selection_info(self) -> dict:
        """Get the current selection info from EXPLORING.
        
        Returns:
            Dict with selection information
        """
        if self._current_layer_type == 'vector':
            return self._get_vector_selection_info()
        elif self._current_layer_type == 'raster':
            return self._get_raster_selection_info()
        return {}
    
    def _get_vector_selection_info(self) -> dict:
        """Get vector selection info from EXPLORING page."""
        vector_page = self._exploring.get_vector_page()
        if not vector_page:
            return {}
        
        return {
            'selected_count': vector_page._current_feature_count if hasattr(vector_page, '_current_feature_count') else 0,
            'selection_type': 'Field/Value',  # TODO: Detect actual type
            'selection_value': '',  # TODO: Get from UI
            'geometry_type': self._current_layer.geometryType().name if self._current_layer else 'Unknown',
        }
    
    def _get_raster_selection_info(self) -> dict:
        """Get raster selection info from EXPLORING page."""
        raster_page = self._exploring.get_raster_page()
        if not raster_page:
            return {}
        
        min_val, max_val = raster_page.get_value_range()
        
        return {
            'min_value': min_val,
            'max_value': max_val,
            'predicate': 'Within Range',  # TODO: Get from UI
            'band': 1,  # TODO: Get selected band
            'data_type': 'Float32',  # TODO: Get from layer
        }
    
    # === Signal Handlers ===
    
    @pyqtSlot(str)
    def _on_layer_type_changed(self, layer_type: str):
        """Handle layer type change from EXPLORING."""
        logger.debug(f"Layer type changed to: {layer_type}")
        self._current_layer_type = layer_type
        self._update_toolset_source()
    
    @pyqtSlot()
    def _on_filter_requested(self):
        """Handle filter request from EXPLORING."""
        logger.debug("Filter requested from EXPLORING")
        # Switch to filtering page and trigger
        self._toolset.activate_page(self._toolset.PAGE_FILTERING)
    
    @pyqtSlot()
    def _on_clear_requested(self):
        """Handle clear request from EXPLORING."""
        logger.debug("Clear requested from EXPLORING")
        self.resetAllFiltersRequested.emit()
    
    @pyqtSlot(str, object)
    def _on_vector_selection_changed(self, field: str, value: object):
        """Handle vector selection change."""
        logger.debug(f"Vector selection changed: field={field}, value={value}")
        self._update_toolset_source()
    
    @pyqtSlot(float, float)
    def _on_raster_range_changed(self, min_val: float, max_val: float):
        """Handle raster range change."""
        logger.debug(f"Raster range changed: [{min_val}, {max_val}]")
        self._update_toolset_source()
    
    @pyqtSlot()
    def _on_execute_filter(self):
        """Handle filter execution request from TOOLSET.
        
        v5.0 EPIC-6: Enhanced to support unified multi-target dispatch.
        Now sends all targets with operations in a single signal to the dockwidget,
        which handles the dispatch based on target types.
        
        - Vector source → Filter vector/Clip raster targets
        - Raster source → Filter vector targets / Mask raster targets
        """
        logger.info("EPIC-6: Execute filter requested")
        
        selection_info = self._get_current_selection_info()
        targets = self._toolset.get_selected_targets()  # Returns [(layer_id, operation), ...]
        raster_options = self._toolset.get_raster_options()  # EPIC-6: Raster operation options
        
        logger.debug(f"EPIC-6 targets: {targets}, raster_options: {raster_options}")
        
        if self._current_layer_type == 'vector':
            # Vector source: unified dispatch to dockwidget handler
            self.vectorFilterRequested.emit({
                'source_layer': self._current_layer,
                'selection': selection_info,
                'targets': targets,  # EPIC-6: [(layer_id, operation), ...]
                'raster_options': raster_options  # EPIC-6: Options for raster operations
            })
        
        elif self._current_layer_type == 'raster':
            # Raster source: get raster params and dispatch
            raster_params = self._get_raster_params()
            
            # Separate targets for appropriate handling
            project = QgsProject.instance()
            vector_targets = []
            raster_targets = []
            
            for layer_id, operation in targets:
                layer = project.mapLayer(layer_id)
                if layer:
                    if isinstance(layer, QgsVectorLayer):
                        vector_targets.append({'layer': layer, 'operation': operation})
                    elif isinstance(layer, QgsRasterLayer):
                        raster_targets.append({'layer': layer, 'operation': operation})
            
            # Raster → Vector: Filter by raster values
            if vector_targets:
                self.rasterFilterRequested.emit({
                    'operation': 'raster_to_vector',
                    'source_layer': self._current_layer,
                    'target_layers': [t['layer'] for t in vector_targets],
                    'raster_params': raster_params
                })
            
            # Raster → Raster: Mask by raster values (rare case)
            if raster_targets:
                self.rasterFilterRequested.emit({
                    'operation': 'raster_to_raster',
                    'source_layer': self._current_layer,
                    'target_layers': [t['layer'] for t in raster_targets],
                    'raster_params': raster_params
                })
    
    def _get_raster_params(self) -> dict:
        """Get current raster filter parameters from EXPLORING raster page."""
        raster_page = self._exploring.get_raster_page()
        if not raster_page:
            return {}
        
        return {
            'band': 1,  # TODO: Get from raster page band combo
            'min': raster_page.get_current_range()[0] if hasattr(raster_page, 'get_current_range') else 0.0,
            'max': raster_page.get_current_range()[1] if hasattr(raster_page, 'get_current_range') else 0.0,
            'predicate': raster_page.get_predicate() if hasattr(raster_page, 'get_predicate') else 'within_range',
            'sampling_method': 'centroid'  # Default sampling method
        }
    
    @pyqtSlot()
    def _on_export_requested(self):
        """Handle export request from TOOLSET."""
        logger.info("Export requested")
        settings = self._toolset.get_export_settings()
        self.exportRequested.emit(settings)
    
    @pyqtSlot(str, object)
    def _on_config_changed(self, key: str, value):
        """Handle configuration change."""
        logger.debug(f"Config changed: {key} = {value}")
        
        # Handle auto-switch setting
        if key == 'auto_switch_exploring':
            self.set_auto_switch(value)
        
        self.configChanged.emit(key, value)
    
    @pyqtSlot()
    def _on_save_config(self):
        """Handle save configuration request."""
        logger.info("Save configuration requested")
        config = self._toolset.get_config()
        self.configChanged.emit('__save__', config)
    
    @pyqtSlot()
    def _on_reset_config(self):
        """Handle reset configuration request."""
        logger.info("Reset configuration requested")
        self.configChanged.emit('__reset__', None)
    
    # === Public API for backward compatibility ===
    
    def get_current_expression(self) -> str:
        """Get the current filter expression.
        
        Returns:
            Filter expression string (for backward compatibility)
        """
        if self._current_layer_type == 'vector':
            vector_page = self._exploring.get_vector_page()
            if vector_page:
                return vector_page.get_expression()
        return ""
    
    def set_expression(self, expression: str):
        """Set the filter expression.
        
        Args:
            expression: Filter expression string (for backward compatibility)
        """
        if self._current_layer_type == 'vector':
            vector_page = self._exploring.get_vector_page()
            if vector_page:
                vector_page.set_expression(expression)
    
    def refresh_layers(self):
        """Refresh the layers list."""
        self._toolset.get_filtering_page().refresh_target_layers()


class DualToolBoxContainer(QWidget):
    """Container widget for the Dual QToolBox layout.
    
    Provides a vertical splitter layout with:
    - Top: EXPLORING QToolBox (Vector/Raster selection)
    - Bottom: TOOLSET QToolBox (Filtering/Exporting/Config)
    """
    
    def __init__(self, parent=None):
        """Initialize the dual toolbox container.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._exploring = None
        self._toolset = None
        self._bridge = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the container UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create splitter for resizable sections
        self._splitter = QSplitter(Qt.Vertical)
        
        # Create QToolBox widgets
        self._exploring = ExploringToolBox()
        self._toolset = ToolsetToolBox()
        
        # Add to splitter
        self._splitter.addWidget(self._exploring)
        self._splitter.addWidget(self._toolset)
        
        # Set initial sizes (60% exploring, 40% toolset)
        self._splitter.setSizes([600, 400])
        
        layout.addWidget(self._splitter)
        
        # Create integration bridge
        self._bridge = ToolBoxIntegrationBridge(
            self._exploring,
            self._toolset,
            parent=self
        )
    
    def get_exploring_toolbox(self) -> ExploringToolBox:
        """Get the EXPLORING QToolBox."""
        return self._exploring
    
    def get_toolset_toolbox(self) -> ToolsetToolBox:
        """Get the TOOLSET QToolBox."""
        return self._toolset
    
    def get_bridge(self) -> ToolBoxIntegrationBridge:
        """Get the integration bridge."""
        return self._bridge
    
    def set_current_layer(self, layer):
        """Set the current layer (delegates to bridge).
        
        Args:
            layer: Current active layer
        """
        self._bridge.set_current_layer(layer)
    
    def set_auto_switch(self, enabled: bool):
        """Enable/disable auto-switch (delegates to bridge).
        
        Args:
            enabled: Whether auto-switch is enabled
        """
        self._bridge.set_auto_switch(enabled)


# Export classes
__all__ = [
    'ToolBoxIntegrationBridge',
    'DualToolBoxContainer',
]

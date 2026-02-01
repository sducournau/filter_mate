"""
Raster Filter Controller

MVC Controller for Raster Filter UI section.
Integrates UI widgets with backend tasks and services.

Created for FilterMate v5.0 - EPIC Raster Visibility Controls.

Architecture: Hexagonal - UI Adapter (Primary Port)
Location: ui/controllers/raster_filter_controller.py

Author: Amelia (Developer)
Sprint: Sprint 2, Day 2
Date: 2026-02-06
"""

import logging
import os
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

from qgis.PyQt.QtCore import QObject, QSize, Qt, pyqtSlot
from qgis.PyQt.QtWidgets import QListWidgetItem, QMessageBox
from qgis.core import (
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsTask,
    QgsApplication,
    QgsLayerTreeNode,
    Qgis
)
from qgis.utils import iface

# Import custom widget
from ..widgets import FilteredLayerListItem

# Import tasks
from ...core.tasks import RasterRangeFilterTask, RasterMaskTask

# Import service
from ...core.services.raster_filter_service import get_raster_filter_service

# Import logging
from ...infrastructure.logging import setup_logger
from ...config.config import ENV_VARS

# Setup logger
logger = setup_logger(
    'FilterMate.Controllers.RasterFilter',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_controllers.log'),
    level=logging.INFO
)


@dataclass
class RasterFilterConfig:
    """Configuration for raster filtering."""
    memory_warning_threshold_mb: int = 200
    default_opacity: int = 70
    use_file_based_threshold_mb: int = 50
    cleanup_on_close: bool = True
    skip_cleanup_confirmation: bool = False


class RasterFilterController(QObject):
    """
    Controller for Raster Filter UI section.
    
    Responsibilities:
    - Connect UI widgets to backend tasks
    - Manage active filtered layers list
    - Handle bidirectional sync (UI ↔ QGIS Layer Tree)
    - Coordinate task execution
    - Handle cleanup operations
    
    Signals flow:
    - UI widget signal → Controller slot → Task creation
    - Task signal → Controller slot → UI update
    - QGIS Layer Tree signal → Controller slot → UI sync
    """
    
    def __init__(self, dockwidget, app, parent=None):
        """
        Initialize raster filter controller.
        
        Args:
            dockwidget: FilterMateDockWidget instance (UI)
            app: FilterMateApp instance (application orchestrator)
            parent: QObject parent (optional)
        """
        super().__init__(parent)
        
        self.dockwidget = dockwidget
        self.app = app
        
        # Configuration (loaded from config.json)
        self.config = self._load_config()
        
        # Active filtered layers tracking
        # layer_id → (QListWidgetItem, FilteredLayerListItem widget)
        self.layer_widgets: Dict[str, Tuple[QListWidgetItem, FilteredLayerListItem]] = {}
        
        # Active tasks tracking
        self.active_tasks: Dict[str, QgsTask] = {}  # task_id → task
        
        # Service instance
        self.raster_service = get_raster_filter_service()
        
        # Setup connections
        self._connect_ui_signals()
        self._connect_layer_tree_signals()
        
        logger.info("RasterFilterController initialized")
    
    # =========================================================================
    # INITIALIZATION & CONFIGURATION
    # =========================================================================
    
    def _load_config(self) -> RasterFilterConfig:
        """Load raster filter configuration from config.json."""
        try:
            from ...config.config import get_config_value
            
            return RasterFilterConfig(
                memory_warning_threshold_mb=get_config_value(
                    'RASTER_FILTER', 'memory_warning_threshold_mb', 200
                ),
                default_opacity=get_config_value(
                    'RASTER_FILTER', 'default_opacity', 70
                ),
                use_file_based_threshold_mb=get_config_value(
                    'RASTER_FILTER', 'use_file_based_threshold_mb', 50
                ),
                cleanup_on_close=get_config_value(
                    'RASTER_FILTER', 'cleanup_on_close', True
                ),
                skip_cleanup_confirmation=get_config_value(
                    'RASTER_FILTER', 'skip_cleanup_confirmation', False
                ),
            )
        except Exception as e:
            logger.warning(f"Failed to load config, using defaults: {e}")
            return RasterFilterConfig()
    
    def _connect_ui_signals(self):
        """Connect UI widget signals to controller slots."""
        # Range filter button
        self.dockwidget.pushButton_apply_range_filter.clicked.connect(
            self.on_apply_range_filter_clicked
        )
        
        # Vector mask button
        self.dockwidget.pushButton_apply_vector_mask.clicked.connect(
            self.on_apply_vector_mask_clicked
        )
        
        # Clear all button
        self.dockwidget.pushButton_clear_all_temp_layers.clicked.connect(
            self.on_clear_all_clicked
        )
        
        # Source layer changed (update band selector)
        self.dockwidget.comboBox_raster_source_layer.layerChanged.connect(
            self.on_source_layer_changed
        )
        
        logger.debug("UI signals connected")
    
    def _connect_layer_tree_signals(self):
        """Connect QGIS Layer Tree signals for bidirectional sync."""
        layer_tree_root = QgsProject.instance().layerTreeRoot()
        
        # Visibility changes in QGIS TOC → sync to FilterMate UI
        layer_tree_root.visibilityChanged.connect(
            self.on_layer_tree_visibility_changed
        )
        
        # Layer removed from project → remove from UI list
        QgsProject.instance().layerRemoved.connect(
            self.on_layer_removed_from_project
        )
        
        logger.debug("Layer tree signals connected")
    
    # =========================================================================
    # UI SIGNAL HANDLERS
    # =========================================================================
    
    @pyqtSlot()
    def on_apply_range_filter_clicked(self):
        """Handle 'Apply Range Filter' button click."""
        try:
            # Get source layer
            source_layer = self.dockwidget.comboBox_raster_source_layer.currentLayer()
            if not source_layer or not isinstance(source_layer, QgsRasterLayer):
                iface.messageBar().pushWarning(
                    "FilterMate",
                    "Please select a raster layer"
                )
                return
            
            # Get filter parameters
            min_value = self.dockwidget.doubleSpinBox_raster_min.value()
            max_value = self.dockwidget.doubleSpinBox_raster_max.value()
            
            # Validate range
            if min_value >= max_value:
                iface.messageBar().pushWarning(
                    "FilterMate",
                    "Min value must be less than max value"
                )
                return
            
            # Get band index (1-based)
            band = self.dockwidget.comboBox_raster_band.currentIndex() + 1
            
            logger.info(
                f"Applying range filter: {source_layer.name()}, "
                f"range=[{min_value}, {max_value}], band={band}"
            )
            
            # Create and run task
            task = RasterRangeFilterTask(
                source_layer=source_layer,
                min_value=min_value,
                max_value=max_value,
                band=band,
                default_opacity=self.config.default_opacity,
                use_file_based_threshold_mb=self.config.use_file_based_threshold_mb
            )
            
            # Connect task signals
            task.taskCompleted.connect(self.on_range_filter_completed)
            task.taskTerminated.connect(self.on_task_failed)
            
            # Add to QGIS task manager
            task_id = QgsApplication.taskManager().addTask(task)
            self.active_tasks[str(task_id)] = task
            
            # Show feedback
            iface.messageBar().pushInfo(
                "FilterMate",
                f"Applying range filter to {source_layer.name()}..."
            )
            
        except Exception as e:
            logger.error(f"Failed to apply range filter: {e}", exc_info=True)
            iface.messageBar().pushCritical(
                "FilterMate",
                f"Error: {str(e)}"
            )
    
    @pyqtSlot()
    def on_apply_vector_mask_clicked(self):
        """Handle 'Apply Vector Mask' button click."""
        try:
            # Get source raster layer
            source_layer = self.dockwidget.comboBox_raster_source_layer.currentLayer()
            if not source_layer or not isinstance(source_layer, QgsRasterLayer):
                iface.messageBar().pushWarning(
                    "FilterMate",
                    "Please select a raster layer"
                )
                return
            
            # Get mask vector layer
            mask_layer = self.dockwidget.comboBox_vector_mask_layer.currentLayer()
            if not mask_layer or not isinstance(mask_layer, QgsVectorLayer):
                iface.messageBar().pushWarning(
                    "FilterMate",
                    "Please select a polygon layer for mask"
                )
                return
            
            logger.info(
                f"Applying vector mask: raster={source_layer.name()}, "
                f"mask={mask_layer.name()}"
            )
            
            # Create and run task
            task = RasterMaskTask(
                source_layer=source_layer,
                mask_layer=mask_layer,
                default_opacity=self.config.default_opacity
            )
            
            # Connect task signals
            task.taskCompleted.connect(self.on_mask_filter_completed)
            task.taskTerminated.connect(self.on_task_failed)
            
            # Add to QGIS task manager
            task_id = QgsApplication.taskManager().addTask(task)
            self.active_tasks[str(task_id)] = task
            
            # Show feedback
            iface.messageBar().pushInfo(
                "FilterMate",
                f"Clipping {source_layer.name()} to {mask_layer.name()}..."
            )
            
        except Exception as e:
            logger.error(f"Failed to apply vector mask: {e}", exc_info=True)
            iface.messageBar().pushCritical(
                "FilterMate",
                f"Error: {str(e)}"
            )
    
    @pyqtSlot()
    def on_clear_all_clicked(self):
        """Handle 'Clear All Temp Layers' button click."""
        if not self.layer_widgets:
            iface.messageBar().pushInfo(
                "FilterMate",
                "No temporary layers to clear"
            )
            return
        
        # Confirmation dialog (if not skipped in config)
        if not self.config.skip_cleanup_confirmation:
            reply = QMessageBox.question(
                None,
                "FilterMate",
                f"Remove all {len(self.layer_widgets)} temporary filtered layers?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
        
        # Remove all layers
        layer_ids = list(self.layer_widgets.keys())
        for layer_id in layer_ids:
            self._remove_layer(layer_id)
        
        iface.messageBar().pushSuccess(
            "FilterMate",
            f"Removed {len(layer_ids)} temporary layers"
        )
    
    @pyqtSlot('QgsMapLayer')
    def on_source_layer_changed(self, layer):
        """Handle source raster layer selection change."""
        # Update band selector
        self.dockwidget.comboBox_raster_band.clear()
        
        if layer and isinstance(layer, QgsRasterLayer) and layer.isValid():
            band_count = layer.bandCount()
            for i in range(1, band_count + 1):
                band_name = layer.bandName(i) or f"Band {i}"
                self.dockwidget.comboBox_raster_band.addItem(band_name)
            
            logger.debug(f"Updated band selector: {band_count} bands")
    
    # =========================================================================
    # TASK COMPLETION HANDLERS
    # =========================================================================
    
    @pyqtSlot(QgsRasterLayer, dict)
    def on_range_filter_completed(self, result_layer, metadata):
        """Handle range filter task completion."""
        try:
            logger.info(f"Range filter completed: {result_layer.name()}")
            
            # Set custom properties for identification
            result_layer.setCustomProperty('filtermate_temp', True)
            result_layer.setCustomProperty('filtermate_type', 'raster_range')
            result_layer.setCustomProperty('filtermate_source_id', metadata['source_layer_id'])
            result_layer.setCustomProperty('filtermate_params', {
                'min_value': metadata['min_value'],
                'max_value': metadata['max_value'],
                'band': metadata['band']
            })
            
            # Add to project
            QgsProject.instance().addMapLayer(result_layer)
            
            # Add to UI list
            self.add_filtered_layer_to_list(result_layer)
            
            # Show success
            iface.messageBar().pushSuccess(
                "FilterMate",
                f"Range filter applied: {result_layer.name()}"
            )
            
        except Exception as e:
            logger.error(f"Failed to handle task completion: {e}", exc_info=True)
    
    @pyqtSlot(QgsRasterLayer, dict)
    def on_mask_filter_completed(self, result_layer, metadata):
        """Handle mask filter task completion."""
        try:
            logger.info(f"Mask filter completed: {result_layer.name()}")
            
            # Set custom properties
            result_layer.setCustomProperty('filtermate_temp', True)
            result_layer.setCustomProperty('filtermate_type', 'raster_mask')
            result_layer.setCustomProperty('filtermate_source_id', metadata['source_layer_id'])
            result_layer.setCustomProperty('filtermate_params', {
                'mask_layer_id': metadata['mask_layer_id']
            })
            
            # Add to project
            QgsProject.instance().addMapLayer(result_layer)
            
            # Add to UI list
            self.add_filtered_layer_to_list(result_layer)
            
            # Show success
            iface.messageBar().pushSuccess(
                "FilterMate",
                f"Vector mask applied: {result_layer.name()}"
            )
            
        except Exception as e:
            logger.error(f"Failed to handle task completion: {e}", exc_info=True)
    
    @pyqtSlot(str)
    def on_task_failed(self, error_message):
        """Handle task failure."""
        logger.error(f"Task failed: {error_message}")
        iface.messageBar().pushCritical(
            "FilterMate",
            f"Filter operation failed: {error_message}"
        )
    
    # =========================================================================
    # LAYER MANAGEMENT
    # =========================================================================
    
    def add_filtered_layer_to_list(self, layer: QgsRasterLayer):
        """Add filtered layer to active layers list widget."""
        list_widget = self.dockwidget.listWidget_active_filtered_layers
        
        # Create list item
        item = QListWidgetItem(list_widget)
        item.setSizeHint(QSize(0, 60))  # Fixed height from Sally's design
        
        # Create custom widget
        widget = FilteredLayerListItem(layer)
        
        # Connect widget signals
        widget.visibility_toggled.connect(self.on_visibility_toggled)
        widget.opacity_changed.connect(self.on_opacity_changed)
        widget.delete_clicked.connect(self.on_delete_clicked)
        
        # Set widget in list item
        list_widget.setItemWidget(item, widget)
        
        # Store reference
        self.layer_widgets[layer.id()] = (item, widget)
        
        logger.debug(f"Added layer to list: {layer.name()}")
    
    def remove_layer_from_list(self, layer_id: str):
        """Remove layer from active layers list widget."""
        if layer_id not in self.layer_widgets:
            return
        
        list_widget = self.dockwidget.listWidget_active_filtered_layers
        item, widget = self.layer_widgets[layer_id]
        
        # Find and remove item
        for i in range(list_widget.count()):
            if list_widget.item(i) == item:
                list_widget.takeItem(i)
                break
        
        # Clean up reference
        del self.layer_widgets[layer_id]
        
        logger.debug(f"Removed layer from list: {layer_id}")
    
    def _remove_layer(self, layer_id: str):
        """Remove layer from project and UI."""
        # Remove from project
        QgsProject.instance().removeMapLayer(layer_id)
        
        # Remove from UI list (will be handled by on_layer_removed_from_project)
    
    # =========================================================================
    # BIDIRECTIONAL SYNC (UI ↔ QGIS LAYER TREE)
    # =========================================================================
    
    @pyqtSlot(str, bool)
    def on_visibility_toggled(self, layer_id, is_visible):
        """Handle visibility toggle from custom widget."""
        layer_tree_root = QgsProject.instance().layerTreeRoot()
        layer_tree_layer = layer_tree_root.findLayer(layer_id)
        
        if layer_tree_layer:
            # Update QGIS layer tree (will trigger layer tree signal, but we handle it)
            layer_tree_layer.setItemVisibilityChecked(is_visible)
        
        # Trigger canvas repaint
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer:
            layer.triggerRepaint()
        
        logger.debug(f"Visibility toggled: {layer_id} → {is_visible}")
    
    @pyqtSlot(str, int)
    def on_opacity_changed(self, layer_id, opacity_percent):
        """Handle opacity change from custom widget."""
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer:
            layer.setOpacity(opacity_percent / 100.0)
            layer.triggerRepaint()
        
        logger.debug(f"Opacity changed: {layer_id} → {opacity_percent}%")
    
    @pyqtSlot(str)
    def on_delete_clicked(self, layer_id):
        """Handle delete button click from custom widget."""
        layer = QgsProject.instance().mapLayer(layer_id)
        if not layer:
            return
        
        # Confirmation dialog
        reply = QMessageBox.question(
            None,
            "FilterMate",
            f"Remove filtered layer '{layer.name()}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self._remove_layer(layer_id)
    
    @pyqtSlot('QgsLayerTreeNode')
    def on_layer_tree_visibility_changed(self, node):
        """Sync visibility from QGIS Layer Tree to FilterMate UI."""
        if node.nodeType() != QgsLayerTreeNode.NodeLayer:
            return
        
        layer_id = node.layerId()
        
        # Check if it's one of our filtered layers
        if layer_id not in self.layer_widgets:
            return
        
        # Get new visibility state
        is_visible = node.isVisible()
        
        # Update widget checkbox (without triggering signal loop)
        item, widget = self.layer_widgets[layer_id]
        widget.set_visibility_checked(is_visible)
        
        logger.debug(f"Synced visibility from TOC: {layer_id} → {is_visible}")
    
    @pyqtSlot(str)
    def on_layer_removed_from_project(self, layer_id):
        """Handle layer removal from QGIS project."""
        if layer_id in self.layer_widgets:
            self.remove_layer_from_list(layer_id)
            logger.info(f"Layer removed from project and UI: {layer_id}")
    
    # =========================================================================
    # CLEANUP
    # =========================================================================
    
    def cleanup_on_close(self):
        """Cleanup temporary layers when plugin closes."""
        if not self.config.cleanup_on_close:
            return
        
        if not self.layer_widgets:
            return
        
        # Confirmation (if not skipped)
        if not self.config.skip_cleanup_confirmation:
            reply = QMessageBox.question(
                None,
                "FilterMate",
                f"Remove {len(self.layer_widgets)} temporary filtered layers on close?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
        
        # Remove all layers
        layer_ids = list(self.layer_widgets.keys())
        for layer_id in layer_ids:
            self._remove_layer(layer_id)
        
        logger.info(f"Cleaned up {len(layer_ids)} temporary layers on close")


# Module exports
__all__ = ['RasterFilterController', 'RasterFilterConfig']

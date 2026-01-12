# -*- coding: utf-8 -*-
"""
Custom Widgets for FilterMate

EPIC-1 Migration: Created from orphan modules/custom_widgets.pyc
Date: January 2026

Custom QGIS widgets not available in qgis.gui:
- QgsCheckableComboBoxLayer: Multi-select layer combobox

Usage:
    from ui.widgets.custom_widgets import QgsCheckableComboBoxLayer
    
    combo = QgsCheckableComboBoxLayer(parent)
    combo.setLayers(layer_list)
    selected_layers = combo.checkedLayers()
"""

import logging
from typing import List, Optional

from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsMapLayer
)
from qgis.gui import (
    QgsCheckableComboBox
)
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QWidget

logger = logging.getLogger('FilterMate.UI.Widgets.CustomWidgets')


class QgsCheckableComboBoxLayer(QgsCheckableComboBox):
    """
    A checkable combobox for selecting multiple layers.
    
    Extends QgsCheckableComboBox to provide layer-specific functionality:
    - Filter layers by type (vector, raster, etc.)
    - Track layer lifecycle (removed layers are auto-unchecked)
    - Provide easy access to checked QgsVectorLayer objects
    
    Signals:
        layersChanged: Emitted when the selection changes
    """
    
    layersChanged = pyqtSignal(list)  # List of checked layers
    
    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize the checkable layer combobox.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._layer_filter = None  # Optional filter function
        self._excluded_layer_ids = set()  # Layers to exclude
        self._layer_id_map = {}  # Map item index to layer ID
        
        # Connect to project signals for layer lifecycle
        try:
            QgsProject.instance().layerRemoved.connect(self._on_layer_removed)
        except Exception:
            pass
        
        # Connect internal signal
        self.checkedItemsChanged.connect(self._on_checked_changed)
    
    def setLayers(self, layers: List[QgsVectorLayer], check_all: bool = False):
        """
        Set the available layers in the combobox.
        
        Args:
            layers: List of layers to show
            check_all: If True, check all layers initially
        """
        self.clear()
        self._layer_id_map = {}
        
        for idx, layer in enumerate(layers):
            if layer is None or not layer.isValid():
                continue
            if layer.id() in self._excluded_layer_ids:
                continue
            if self._layer_filter and not self._layer_filter(layer):
                continue
                
            self.addItem(layer.name())
            self._layer_id_map[idx] = layer.id()
            
            if check_all:
                self.setItemCheckState(idx, Qt.Checked)
    
    def refreshFromProject(self, check_all: bool = False):
        """
        Refresh the layer list from the current project.
        
        Args:
            check_all: If True, check all layers initially
        """
        layers = list(QgsProject.instance().mapLayers().values())
        vector_layers = [l for l in layers if isinstance(l, QgsVectorLayer)]
        self.setLayers(vector_layers, check_all)
    
    def setExcludedLayerIds(self, layer_ids: List[str]):
        """
        Set layers to exclude from the combobox.
        
        Args:
            layer_ids: List of layer IDs to exclude
        """
        self._excluded_layer_ids = set(layer_ids)
    
    def setLayerFilter(self, filter_func):
        """
        Set a filter function for layers.
        
        Args:
            filter_func: Callable that takes a layer and returns True if it should be included
        """
        self._layer_filter = filter_func
    
    def checkedLayers(self) -> List[QgsVectorLayer]:
        """
        Get the currently checked layers.
        
        Returns:
            List of checked QgsVectorLayer objects
        """
        checked = []
        project = QgsProject.instance()
        
        for idx in range(self.count()):
            if self.itemCheckState(idx) == Qt.Checked:
                layer_id = self._layer_id_map.get(idx)
                if layer_id:
                    layer = project.mapLayer(layer_id)
                    if layer and isinstance(layer, QgsVectorLayer) and layer.isValid():
                        checked.append(layer)
        
        return checked
    
    def checkedLayerIds(self) -> List[str]:
        """
        Get the IDs of currently checked layers.
        
        Returns:
            List of layer ID strings
        """
        return [layer.id() for layer in self.checkedLayers()]
    
    def setCheckedLayers(self, layers: List[QgsVectorLayer]):
        """
        Set which layers should be checked.
        
        Args:
            layers: List of layers to check
        """
        layer_ids_to_check = {l.id() for l in layers if l is not None}
        
        for idx in range(self.count()):
            layer_id = self._layer_id_map.get(idx)
            if layer_id in layer_ids_to_check:
                self.setItemCheckState(idx, Qt.Checked)
            else:
                self.setItemCheckState(idx, Qt.Unchecked)
    
    def setCheckedLayerIds(self, layer_ids: List[str]):
        """
        Set which layers should be checked by ID.
        
        Args:
            layer_ids: List of layer IDs to check
        """
        layer_ids_set = set(layer_ids)
        
        for idx in range(self.count()):
            layer_id = self._layer_id_map.get(idx)
            if layer_id in layer_ids_set:
                self.setItemCheckState(idx, Qt.Checked)
            else:
                self.setItemCheckState(idx, Qt.Unchecked)
    
    def _on_layer_removed(self, layer_id: str):
        """
        Handle layer removal from project.
        
        Args:
            layer_id: ID of removed layer
        """
        # Find and remove the item for this layer
        for idx, lid in list(self._layer_id_map.items()):
            if lid == layer_id:
                # Uncheck first
                self.setItemCheckState(idx, Qt.Unchecked)
                break
    
    def _on_checked_changed(self, items):
        """
        Handle checked items change.
        
        Args:
            items: List of checked item texts
        """
        checked_layers = self.checkedLayers()
        self.layersChanged.emit(checked_layers)


__all__ = [
    'QgsCheckableComboBoxLayer',
]

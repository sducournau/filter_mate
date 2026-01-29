# -*- coding: utf-8 -*-
"""
Raster Target Layer Widget.

EPIC-3: Raster-Vector Integration
US-R2V-01: Raster as Filter Source

Widget for selecting target vector layers when using raster as filter source.
Each target layer can have:
- Selection checkbox
- Operation selector (filter by value, zonal stats, etc.)
- Sampling method selector (centroid, all vertices, etc.)

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Dict, List, Optional, Any

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QComboBox,
    QFrame,
    QScrollArea,
    QPushButton,
    QSizePolicy
)
from qgis.PyQt.QtGui import QFont, QCursor
from qgis.core import QgsProject, QgsVectorLayer, QgsMapLayerProxyModel

try:
    from qgis.gui import QgsMapLayerComboBox
    HAS_QGIS_GUI = True
except ImportError:
    HAS_QGIS_GUI = False


logger = logging.getLogger("FilterMate.RasterTargetLayerWidget")


class TargetLayerItem(QFrame):
    """
    Single target layer item widget.
    
    Shows:
    - Checkbox with layer name
    - Operation combo (Filter, Zonal Stats)
    - Sampling method combo
    
    Signals:
        selection_changed: Emitted when checkbox state changes (layer_id, is_selected)
        config_changed: Emitted when operation or sampling changes (layer_id, config_dict)
    """
    
    selection_changed = pyqtSignal(str, bool)
    config_changed = pyqtSignal(str, dict)
    
    # Available operations
    OPERATIONS = [
        ('filter_value', "Filter by Value"),
        ('zonal_stats', "Zonal Statistics"),
        ('sample_only', "Sample Values Only"),
    ]
    
    # Sampling methods
    SAMPLING_METHODS = [
        ('centroid', "Centroid"),
        ('all_vertices', "All Vertices"),
        ('intersecting', "Intersecting Cells"),
    ]
    
    def __init__(self, layer: QgsVectorLayer, parent: Optional[QWidget] = None):
        """
        Initialize target layer item.
        
        Args:
            layer: Vector layer for this item
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._layer = layer
        self._layer_id = layer.id()
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self) -> None:
        """Setup the widget UI."""
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setStyleSheet("""
            TargetLayerItem {
                background-color: palette(base);
                border: 1px solid palette(mid);
                border-radius: 4px;
                padding: 4px;
            }
            TargetLayerItem:hover {
                background-color: palette(alternateBase);
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
        
        # Row 1: Checkbox with layer name
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        
        self.chk_selected = QCheckBox(self)
        self.chk_selected.setChecked(False)
        self.chk_selected.setCursor(QCursor(Qt.PointingHandCursor))
        row1.addWidget(self.chk_selected)
        
        self.lbl_layer_name = QLabel(self._layer.name(), self)
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        self.lbl_layer_name.setFont(font)
        self.lbl_layer_name.setToolTip(f"ID: {self._layer_id}")
        row1.addWidget(self.lbl_layer_name, 1)
        
        # Feature count
        feature_count = self._layer.featureCount()
        self.lbl_feature_count = QLabel(f"({feature_count:,})", self)
        self.lbl_feature_count.setStyleSheet("color: gray;")
        row1.addWidget(self.lbl_feature_count)
        
        layout.addLayout(row1)
        
        # Row 2: Operation and sampling selectors (shown when selected)
        self.options_widget = QWidget(self)
        options_layout = QHBoxLayout(self.options_widget)
        options_layout.setContentsMargins(20, 0, 0, 0)
        options_layout.setSpacing(8)
        
        # Operation selector
        self.lbl_operation = QLabel("Op:", self.options_widget)
        self.lbl_operation.setStyleSheet("color: gray; font-size: 8pt;")
        options_layout.addWidget(self.lbl_operation)
        
        self.cmb_operation = QComboBox(self.options_widget)
        self.cmb_operation.setCursor(QCursor(Qt.PointingHandCursor))
        for op_id, op_name in self.OPERATIONS:
            self.cmb_operation.addItem(op_name, op_id)
        self.cmb_operation.setCurrentIndex(0)
        self.cmb_operation.setMinimumWidth(120)
        options_layout.addWidget(self.cmb_operation)
        
        # Sampling method selector
        self.lbl_sampling = QLabel("Sample:", self.options_widget)
        self.lbl_sampling.setStyleSheet("color: gray; font-size: 8pt;")
        options_layout.addWidget(self.lbl_sampling)
        
        self.cmb_sampling = QComboBox(self.options_widget)
        self.cmb_sampling.setCursor(QCursor(Qt.PointingHandCursor))
        for method_id, method_name in self.SAMPLING_METHODS:
            self.cmb_sampling.addItem(method_name, method_id)
        self.cmb_sampling.setCurrentIndex(0)
        self.cmb_sampling.setMinimumWidth(100)
        options_layout.addWidget(self.cmb_sampling)
        
        options_layout.addStretch()
        
        # Hide options by default
        self.options_widget.setVisible(False)
        layout.addWidget(self.options_widget)
    
    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.chk_selected.stateChanged.connect(self._on_selection_changed)
        self.cmb_operation.currentIndexChanged.connect(self._on_config_changed)
        self.cmb_sampling.currentIndexChanged.connect(self._on_config_changed)
    
    def _on_selection_changed(self, state: int) -> None:
        """Handle selection checkbox change."""
        is_selected = state == Qt.Checked
        self.options_widget.setVisible(is_selected)
        self.selection_changed.emit(self._layer_id, is_selected)
        
        if is_selected:
            self._on_config_changed()
    
    def _on_config_changed(self) -> None:
        """Handle operation/sampling change."""
        config = self.get_config()
        self.config_changed.emit(self._layer_id, config)
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get current configuration for this layer.
        
        Returns:
            Dict with operation, sampling_method, layer_id
        """
        return {
            'layer_id': self._layer_id,
            'layer_name': self._layer.name(),
            'is_selected': self.chk_selected.isChecked(),
            'operation': self.cmb_operation.currentData(),
            'sampling_method': self.cmb_sampling.currentData(),
        }
    
    def set_selected(self, selected: bool) -> None:
        """Set selection state."""
        self.chk_selected.setChecked(selected)
    
    def is_selected(self) -> bool:
        """Check if layer is selected."""
        return self.chk_selected.isChecked()
    
    @property
    def layer_id(self) -> str:
        """Get layer ID."""
        return self._layer_id


class RasterTargetLayerWidget(QWidget):
    """
    Widget for selecting and configuring target vector layers.
    
    EPIC-3: Allows users to select which vector layers should be
    filtered by raster values, and configure the operation for each.
    
    Signals:
        targets_changed: Emitted when target selection changes
            List of selected layer configurations
        execute_requested: Emitted when user clicks Execute button
        clear_filters_requested: Emitted when user clicks Clear button
        zonal_stats_requested: Emitted when user clicks Zonal Stats button
    """
    
    targets_changed = pyqtSignal(list)
    execute_requested = pyqtSignal()
    clear_filters_requested = pyqtSignal(list)  # List of layer IDs to clear
    zonal_stats_requested = pyqtSignal(list)  # List of layer IDs for zonal stats
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the widget."""
        super().__init__(parent)
        
        self._layer_items: Dict[str, TargetLayerItem] = {}
        self._setup_ui()
        self._connect_project_signals()
    
    def _setup_ui(self) -> None:
        """Setup the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Header
        header_layout = QHBoxLayout()
        
        self.lbl_header = QLabel("Target Vector Layers", self)
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        self.lbl_header.setFont(font)
        header_layout.addWidget(self.lbl_header)
        
        header_layout.addStretch()
        
        # Select All / None buttons
        self.btn_select_all = QPushButton("All", self)
        self.btn_select_all.setFixedWidth(40)
        self.btn_select_all.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_select_all.clicked.connect(self._select_all)
        header_layout.addWidget(self.btn_select_all)
        
        self.btn_select_none = QPushButton("None", self)
        self.btn_select_none.setFixedWidth(40)
        self.btn_select_none.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_select_none.clicked.connect(self._select_none)
        header_layout.addWidget(self.btn_select_none)
        
        layout.addLayout(header_layout)
        
        # Scroll area for layer items
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setMinimumHeight(100)
        self.scroll_area.setMaximumHeight(200)
        
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(4)
        self.scroll_layout.addStretch()
        
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area)
        
        # Summary and execute
        footer_layout = QHBoxLayout()
        
        self.lbl_summary = QLabel("0 layers selected", self)
        self.lbl_summary.setStyleSheet("color: gray;")
        footer_layout.addWidget(self.lbl_summary)
        
        footer_layout.addStretch()
        
        # Clear Filters button
        self.btn_clear = QPushButton("🗑️ Clear", self)
        self.btn_clear.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_clear.setToolTip("Remove raster-based filters from selected layers")
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        self.btn_clear.clicked.connect(self._on_clear_filters)
        footer_layout.addWidget(self.btn_clear)
        
        # Zonal Statistics button
        self.btn_zonal_stats = QPushButton("📊 Zonal Stats", self)
        self.btn_zonal_stats.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_zonal_stats.setToolTip("Compute raster statistics for selected zone layers")
        self.btn_zonal_stats.setEnabled(False)
        self.btn_zonal_stats.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        self.btn_zonal_stats.clicked.connect(self._on_zonal_stats)
        footer_layout.addWidget(self.btn_zonal_stats)
        
        self.btn_execute = QPushButton("🔍 Filter by Raster", self)
        self.btn_execute.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_execute.setEnabled(False)
        self.btn_execute.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        self.btn_execute.clicked.connect(self.execute_requested.emit)
        footer_layout.addWidget(self.btn_execute)
        
        layout.addLayout(footer_layout)
        
        # Initial population
        self._populate_layers()
    
    def _connect_project_signals(self) -> None:
        """Connect to QGIS project signals."""
        project = QgsProject.instance()
        project.layersAdded.connect(self._on_layers_added)
        project.layersRemoved.connect(self._on_layers_removed)
    
    def _populate_layers(self) -> None:
        """Populate with current project vector layers."""
        project = QgsProject.instance()
        
        for layer in project.mapLayers().values():
            if isinstance(layer, QgsVectorLayer) and layer.isValid():
                self._add_layer_item(layer)
    
    def _add_layer_item(self, layer: QgsVectorLayer) -> None:
        """Add a layer item widget."""
        if layer.id() in self._layer_items:
            return
        
        item = TargetLayerItem(layer, self.scroll_content)
        item.selection_changed.connect(self._on_item_selection_changed)
        item.config_changed.connect(self._on_item_config_changed)
        
        # Insert before stretch
        self.scroll_layout.insertWidget(
            self.scroll_layout.count() - 1,
            item
        )
        
        self._layer_items[layer.id()] = item
    
    def _remove_layer_item(self, layer_id: str) -> None:
        """Remove a layer item widget."""
        if layer_id not in self._layer_items:
            return
        
        item = self._layer_items.pop(layer_id)
        item.deleteLater()
        self._update_summary()
    
    def _on_layers_added(self, layers: List) -> None:
        """Handle layers added to project."""
        for layer in layers:
            if isinstance(layer, QgsVectorLayer) and layer.isValid():
                self._add_layer_item(layer)
    
    def _on_layers_removed(self, layer_ids: List[str]) -> None:
        """Handle layers removed from project."""
        for layer_id in layer_ids:
            self._remove_layer_item(layer_id)
    
    def _on_item_selection_changed(self, layer_id: str, is_selected: bool) -> None:
        """Handle item selection change."""
        self._update_summary()
        self._emit_targets_changed()
    
    def _on_item_config_changed(self, layer_id: str, config: Dict) -> None:
        """Handle item config change."""
        self._emit_targets_changed()
    
    def _on_clear_filters(self) -> None:
        """
        Clear filters from selected vector layers.
        
        Emits clear_filters_requested with list of selected layer IDs.
        """
        selected_ids = self.get_selected_layer_ids()
        if selected_ids:
            self.clear_filters_requested.emit(selected_ids)
    
    def _on_zonal_stats(self) -> None:
        """
        Request zonal statistics for selected vector layers.
        
        Emits zonal_stats_requested with list of selected layer IDs.
        """
        selected_ids = self.get_selected_layer_ids()
        if selected_ids:
            self.zonal_stats_requested.emit(selected_ids)
    
    def _update_summary(self) -> None:
        """Update summary label and execute button state."""
        selected_count = sum(
            1 for item in self._layer_items.values() if item.is_selected()
        )
        
        self.lbl_summary.setText(f"{selected_count} layer(s) selected")
        self.btn_execute.setEnabled(selected_count > 0)
        self.btn_zonal_stats.setEnabled(selected_count > 0)
    
    def _emit_targets_changed(self) -> None:
        """Emit targets_changed signal with current selection."""
        targets = self.get_selected_targets()
        self.targets_changed.emit(targets)
    
    def _select_all(self) -> None:
        """Select all layers."""
        for item in self._layer_items.values():
            item.set_selected(True)
    
    def _select_none(self) -> None:
        """Deselect all layers."""
        for item in self._layer_items.values():
            item.set_selected(False)
    
    def get_selected_targets(self) -> List[Dict[str, Any]]:
        """
        Get configurations for all selected target layers.
        
        Returns:
            List of config dicts for selected layers
        """
        return [
            item.get_config()
            for item in self._layer_items.values()
            if item.is_selected()
        ]
    
    def get_selected_layer_ids(self) -> List[str]:
        """
        Get IDs of selected layers.
        
        Returns:
            List of layer IDs
        """
        return [
            item.layer_id
            for item in self._layer_items.values()
            if item.is_selected()
        ]
    
    def set_selected_layers(self, layer_ids: List[str]) -> None:
        """
        Set which layers are selected.
        
        Args:
            layer_ids: List of layer IDs to select
        """
        for item in self._layer_items.values():
            item.set_selected(item.layer_id in layer_ids)
    
    def refresh(self) -> None:
        """Refresh the layer list."""
        # Clear existing
        for item in list(self._layer_items.values()):
            item.deleteLater()
        self._layer_items.clear()
        
        # Repopulate
        self._populate_layers()
        self._update_summary()

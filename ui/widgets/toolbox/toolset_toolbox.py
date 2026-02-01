# -*- coding: utf-8 -*-
"""
FilterMate - TOOLSET QToolBox

Three-page QToolBox for tools:
- Page 1: Filtering (Multi-target layer list with Vector+Raster operations)
- Page 2: Exporting (Format selection, output options for Vector+Raster)
- Page 3: Configuration (UI settings, backend, raster settings)
"""

from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QCheckBox, QLineEdit, QSpinBox, QDoubleSpinBox,
    QFrame, QSizePolicy, QScrollArea, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QFileDialog, QGroupBox, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QProgressBar
)
from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtGui import QIcon, QFont, QColor

from qgis.core import QgsVectorLayer, QgsRasterLayer, QgsProject
from qgis.gui import QgsCollapsibleGroupBox, QgsFileWidget

from .base_toolbox import BaseToolBox

import logging
logger = logging.getLogger('FilterMate.ToolsetToolBox')


class FilteringPage(QWidget):
    """Page for filtering operations.
    
    Contains:
    - Source context (current selection info)
    - Target layers list with operation selector per layer
    - Action buttons (Filter, Undo, Redo, Reset)
    
    Signals:
        filterRequested: Emitted when filter execution requested
        undoRequested: Emitted when undo requested
        redoRequested: Emitted when redo requested
        resetRequested: Emitted when reset requested
        targetSelectionChanged: Emitted when target layers selection changes
    """
    
    filterRequested = pyqtSignal()
    undoRequested = pyqtSignal()
    redoRequested = pyqtSignal()
    resetRequested = pyqtSignal()
    targetSelectionChanged = pyqtSignal(list)  # list of (layer_id, operation) tuples
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._source_layer = None
        self._source_info = {}
        self._target_layers = []  # list of (layer, operation)
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the filtering UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)
        
        # === SOURCE CONTEXT ===
        self.source_group = QGroupBox(self.tr("Source Context"))
        source_layout = QVBoxLayout(self.source_group)
        source_layout.setContentsMargins(6, 20, 6, 6)  # top margin for title
        source_layout.setSpacing(4)
        
        self.source_type_label = QLabel(self.tr("📍 Vector: -"))
        self.source_type_label.setStyleSheet("font-weight: bold;")
        source_layout.addWidget(self.source_type_label)
        
        self.selection_label = QLabel(self.tr("Selection: -"))
        source_layout.addWidget(self.selection_label)
        
        self.geometry_label = QLabel(self.tr("Geometry: -"))
        self.geometry_label.setStyleSheet("color: gray;")
        source_layout.addWidget(self.geometry_label)
        
        content_layout.addWidget(self.source_group)
        
        # === TARGET LAYERS ===
        self.target_group = QGroupBox(self.tr("Target Layers"))
        self.target_group.setToolTip(self.tr(
            "Target Layers\n\n"
            "Select layers to receive the filtering operation.\n"
            "Check boxes to include layers in batch processing."
        ))
        target_layout = QVBoxLayout(self.target_group)
        target_layout.setContentsMargins(6, 20, 6, 6)  # top margin for title
        target_layout.setSpacing(4)
        
        # Target layers table
        self.target_table = QTableWidget()
        self.target_table.setColumnCount(4)
        self.target_table.setHorizontalHeaderLabels([
            self.tr("✓"), self.tr("Layer"), self.tr("Operation"), self.tr("Status")
        ])
        self.target_table.horizontalHeader().setStretchLastSection(True)
        self.target_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.target_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.target_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.target_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.target_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.target_table.setMinimumHeight(150)
        self.target_table.setToolTip(self.tr(
            "✓: Check layers to include in filtering operation\n"
            "Layer: Target layer name with type icon (📍=Vector, 🏔️=Raster)\n"
            "Operation: Filter operation (Filter for vectors, Clip/Mask for rasters)\n"
            "Status: Current filter status of the layer"
        ))
        target_layout.addWidget(self.target_table)
        
        # Operations info
        ops_label = QLabel(self.tr("Operations:\n• 📍 Vectors: Filter (spatial)\n• 🏔️ Rasters: Clip, Mask Outside, Mask Inside, Zonal Stats"))
        ops_label.setStyleSheet("color: gray; font-size: 9px;")
        target_layout.addWidget(ops_label)
        
        # Selection buttons
        sel_row = QHBoxLayout()
        self.select_all_btn = QPushButton(self.tr("☑ Select All"))
        self.select_all_btn.setToolTip(self.tr(
            "Select All Layers\n\n"
            "Check all layers in the list for filtering.\n"
            "Useful for batch operations on entire project."
        ))
        self.select_all_btn.clicked.connect(self._select_all)
        sel_row.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton(self.tr("☐ Deselect All"))
        self.deselect_all_btn.setToolTip(self.tr(
            "Deselect All Layers\n\n"
            "Uncheck all layers in the list.\n"
            "Use to start fresh with layer selection."
        ))
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        sel_row.addWidget(self.deselect_all_btn)
        
        self.refresh_btn = QPushButton(self.tr("🔄 Refresh List"))
        self.refresh_btn.setToolTip(self.tr(
            "Refresh Layer List\n\n"
            "Reload the layer list from the current project.\n"
            "Use after adding or removing layers in QGIS."
        ))
        self.refresh_btn.clicked.connect(self.refresh_target_layers)
        
        target_layout.addLayout(sel_row)
        
        content_layout.addWidget(self.target_group)
        
        # === RASTER OPTIONS (EPIC-6) ===
        self.raster_options_group = QgsCollapsibleGroupBox(self.tr("Raster Operation Options"))
        self.raster_options_group.setCollapsed(True)
        raster_opts_layout = QVBoxLayout(self.raster_options_group)
        raster_opts_layout.setContentsMargins(6, 20, 6, 6)
        raster_opts_layout.setSpacing(4)
        
        # NoData value
        nodata_row = QHBoxLayout()
        nodata_row.addWidget(QLabel(self.tr("NoData Value:")))
        self.nodata_spin = QDoubleSpinBox()
        self.nodata_spin.setRange(-999999, 999999)
        self.nodata_spin.setValue(-9999)
        self.nodata_spin.setDecimals(2)
        nodata_row.addWidget(self.nodata_spin, 1)
        raster_opts_layout.addLayout(nodata_row)
        
        # Output memory checkbox
        self.memory_output_cb = QCheckBox(self.tr("Output to memory layer"))
        self.memory_output_cb.setChecked(True)
        self.memory_output_cb.setToolTip(self.tr(
            "Output to Memory Layer\n\n"
            "Keep raster result in memory (faster).\n"
            "Uncheck to save to temporary file on disk.\n"
            "Disk output recommended for large rasters."
        ))
        raster_opts_layout.addWidget(self.memory_output_cb)
        
        # Add to project checkbox
        self.add_to_project_cb = QCheckBox(self.tr("Add result to project"))
        self.add_to_project_cb.setChecked(True)
        raster_opts_layout.addWidget(self.add_to_project_cb)
        
        # Compression for output
        compress_row = QHBoxLayout()
        compress_row.addWidget(QLabel(self.tr("Compression:")))
        self.compression_combo = QComboBox()
        self.compression_combo.addItems(["LZW", "DEFLATE", "None", "ZSTD"])
        compress_row.addWidget(self.compression_combo, 1)
        raster_opts_layout.addLayout(compress_row)
        
        content_layout.addWidget(self.raster_options_group)
        
        # === ACTIONS ===
        self.action_group = QGroupBox(self.tr("Actions"))
        action_layout = QVBoxLayout(self.action_group)
        action_layout.setContentsMargins(6, 20, 6, 6)  # top margin for title
        action_layout.setSpacing(4)
        
        # Main action buttons
        action_row1 = QHBoxLayout()
        self.filter_btn = QPushButton(self.tr("▶ EXECUTE FILTER"))
        self.filter_btn.setStyleSheet("background-color: #2a82da; color: white; font-weight: bold; padding: 8px;")
        self.filter_btn.setToolTip(self.tr(
            "Execute the filtering operation on all selected target layers.\n"
            "• Vectors: Apply spatial filter from source layer selection\n"
            "• Rasters: Apply clip/mask operation using vector geometry\n\n"
            "Shortcut: Ctrl+Enter (when focused)"
        ))
        self.filter_btn.clicked.connect(self.filterRequested.emit)
        action_row1.addWidget(self.filter_btn)
        
        self.pause_btn = QPushButton(self.tr("⏸ PAUSE"))
        self.pause_btn.setEnabled(False)
        self.pause_btn.setToolTip(self.tr(
            "Pause Operation (Coming Soon)\n\n"
            "Pause the current filtering operation.\n"
            "Feature not yet implemented."
        ))
        action_row1.addWidget(self.pause_btn)
        action_layout.addLayout(action_row1)
        
        # Undo/Redo/Reset
        action_row2 = QHBoxLayout()
        self.undo_btn = QPushButton(self.tr("↩ UNDO"))
        self.undo_btn.setToolTip(self.tr(
            "Undo the last filter operation.\n"
            "Restores previous filter state for affected layers.\n\n"
            "Shortcut: Ctrl+Z"
        ))
        self.undo_btn.clicked.connect(self.undoRequested.emit)
        action_row2.addWidget(self.undo_btn)
        
        self.redo_btn = QPushButton(self.tr("↪ REDO"))
        self.redo_btn.setToolTip(self.tr(
            "Redo the last undone filter operation.\n\n"
            "Shortcut: Ctrl+Shift+Z"
        ))
        self.redo_btn.clicked.connect(self.redoRequested.emit)
        action_row2.addWidget(self.redo_btn)
        action_layout.addLayout(action_row2)
        
        action_row3 = QHBoxLayout()
        self.reset_btn = QPushButton(self.tr("🔄 RESET ALL FILTERS"))
        self.reset_btn.setToolTip(self.tr(
            "Remove all filters from all layers in the project.\n"
            "This clears all setSubsetString filters on vector layers\n"
            "and restores full visibility."
        ))
        self.reset_btn.clicked.connect(self.resetRequested.emit)
        action_row3.addWidget(self.reset_btn)
        
        self.summary_btn = QPushButton(self.tr("📊 Show Results Summary"))
        self.summary_btn.setToolTip(self.tr(
            "Display a summary of the last filtering operation.\n"
            "Shows: affected layers, feature counts, and timing."
        ))
        action_row3.addWidget(self.summary_btn)
        action_layout.addLayout(action_row3)
        
        content_layout.addWidget(self.action_group)
        
        # Stretch
        content_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
    
    def set_source(self, layer, selection_info: dict = None):
        """Set the source layer and selection info.
        
        Args:
            layer: Source layer (vector or raster)
            selection_info: Dict with selection details
        """
        self._source_layer = layer
        self._source_info = selection_info or {}
        self._update_source_display()
    
    def _update_source_display(self):
        """Update the source context display."""
        if not self._source_layer:
            self.source_type_label.setText(self.tr("📍 No source layer"))
            self.selection_label.setText(self.tr("Selection: -"))
            self.geometry_label.setText(self.tr("Geometry: -"))
            return
        
        if isinstance(self._source_layer, QgsVectorLayer):
            self.source_type_label.setText(f"📍 Vector: {self._source_layer.name()}")
            
            # Selection info
            sel_count = self._source_info.get('selected_count', 0)
            sel_type = self._source_info.get('selection_type', 'Unknown')
            sel_value = self._source_info.get('selection_value', '')
            self.selection_label.setText(
                f"Selection: {sel_count} feature{'s' if sel_count != 1 else ''} ({sel_type}: \"{sel_value}\")"
            )
            
            # Geometry info
            geom_type = self._source_info.get('geometry_type', 'Unknown')
            crs = self._source_layer.crs().authid() if self._source_layer.crs().isValid() else 'Unknown'
            self.geometry_label.setText(f"Geometry: {geom_type}, {crs}")
            
        elif isinstance(self._source_layer, QgsRasterLayer):
            self.source_type_label.setText(f"🏔️ Raster: {self._source_layer.name()}")
            
            # Range info
            min_val = self._source_info.get('min_value', '-')
            max_val = self._source_info.get('max_value', '-')
            predicate = self._source_info.get('predicate', 'Within Range')
            self.selection_label.setText(
                f"Selection: Range [{min_val} - {max_val}] ({predicate})"
            )
            
            # Raster info
            band = self._source_info.get('band', 1)
            data_type = self._source_info.get('data_type', 'Unknown')
            self.geometry_label.setText(f"Band: {band}, Type: {data_type}")
    
    def refresh_target_layers(self):
        """Refresh the target layers list from project."""
        self.target_table.setRowCount(0)
        self._target_layers = []
        
        project = QgsProject.instance()
        if not project:
            return
        
        row = 0
        for layer in project.mapLayers().values():
            # Skip the source layer
            if self._source_layer and layer.id() == self._source_layer.id():
                continue
            
            is_vector = isinstance(layer, QgsVectorLayer)
            is_raster = isinstance(layer, QgsRasterLayer)
            
            if not (is_vector or is_raster):
                continue
            
            self.target_table.insertRow(row)
            
            # Checkbox
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            self.target_table.setCellWidget(row, 0, checkbox)
            
            # Layer name with icon
            icon = "📍" if is_vector else "🏔️"
            name_item = QTableWidgetItem(f"{icon} {layer.name()}")
            name_item.setData(Qt.UserRole, layer.id())
            self.target_table.setItem(row, 1, name_item)
            
            # Operation combo
            op_combo = QComboBox()
            if is_vector:
                op_combo.addItems(["Filter", "Select", "Skip"])
            else:
                op_combo.addItems(["Clip", "Mask Outside", "Mask Inside", "Zonal Stats", "Skip"])
            self.target_table.setCellWidget(row, 2, op_combo)
            
            # Status
            status_item = QTableWidgetItem("-")
            status_item.setForeground(QColor("gray"))
            self.target_table.setItem(row, 3, status_item)
            
            self._target_layers.append((layer, op_combo))
            row += 1
    
    def _select_all(self):
        """Select all target layers."""
        for row in range(self.target_table.rowCount()):
            checkbox = self.target_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(True)
    
    def _deselect_all(self):
        """Deselect all target layers."""
        for row in range(self.target_table.rowCount()):
            checkbox = self.target_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(False)
    
    def get_selected_targets(self) -> list:
        """Get list of selected target layers with operations.
        
        Returns:
            List of (layer_id, operation) tuples
        """
        targets = []
        for row in range(self.target_table.rowCount()):
            checkbox = self.target_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                layer_id = self.target_table.item(row, 1).data(Qt.UserRole)
                op_combo = self.target_table.cellWidget(row, 2)
                operation = op_combo.currentText() if op_combo else "Filter"
                
                if operation != "Skip":
                    targets.append((layer_id, operation))
        
        return targets
    
    def get_raster_options(self) -> dict:
        """EPIC-6: Get raster operation options.
        
        Returns:
            Dict with raster operation settings
        """
        return {
            'nodata_value': self.nodata_spin.value() if hasattr(self, 'nodata_spin') else -9999,
            'output_to_memory': self.memory_output_cb.isChecked() if hasattr(self, 'memory_output_cb') else True,
            'add_to_project': self.add_to_project_cb.isChecked() if hasattr(self, 'add_to_project_cb') else True,
            'compression': self.compression_combo.currentText() if hasattr(self, 'compression_combo') else 'LZW',
        }
    
    def update_target_status(self, layer_id: str, status: str, color: str = "gray"):
        """Update the status for a target layer.
        
        Args:
            layer_id: Layer ID
            status: Status text
            color: Text color
        """
        for row in range(self.target_table.rowCount()):
            item = self.target_table.item(row, 1)
            if item and item.data(Qt.UserRole) == layer_id:
                status_item = self.target_table.item(row, 3)
                if status_item:
                    status_item.setText(status)
                    status_item.setForeground(QColor(color))
                break


class ExportingPage(QWidget):
    """Page for export operations.
    
    Contains:
    - Output settings (format, directory, filename pattern)
    - Vector options
    - Raster options  
    - Layers to export list with batch selection
    - Progress bar for batch export
    - Action buttons
    
    Signals:
        exportRequested: Emitted when export requested
        exportAllRequested: Emitted when export all requested
        openOutputDirRequested: Emitted when open dir requested
        refreshLayersRequested: Emitted when layer list refresh requested
    """
    
    exportRequested = pyqtSignal()
    exportAllRequested = pyqtSignal()
    openOutputDirRequested = pyqtSignal()
    refreshLayersRequested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._export_layers = []
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the exporting UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)
        
        # === OUTPUT SETTINGS ===
        self.output_group = QgsCollapsibleGroupBox(self.tr("Output Settings"))
        self.output_group.setCollapsed(False)
        output_layout = QVBoxLayout(self.output_group)
        output_layout.setContentsMargins(6, 20, 6, 6)  # top margin for title
        output_layout.setSpacing(4)
        
        # Format
        format_row = QHBoxLayout()
        format_row.addWidget(QLabel(self.tr("Format:")))
        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "GeoPackage (.gpkg)",
            "Shapefile (.shp)",
            "GeoJSON (.geojson)",
            "GeoTIFF (.tif)",
            "COG (.tif)",
            "KML (.kml)",
            "CSV (.csv)"
        ])
        format_row.addWidget(self.format_combo, 1)
        output_layout.addLayout(format_row)
        
        # Output directory
        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel(self.tr("Output Dir:")))
        self.output_dir = QgsFileWidget()
        self.output_dir.setStorageMode(QgsFileWidget.GetDirectory)
        dir_row.addWidget(self.output_dir, 1)
        output_layout.addLayout(dir_row)
        
        # Filename pattern
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel(self.tr("Filename:")))
        self.filename_edit = QLineEdit("filtered_{layer_name}_{date}")
        name_row.addWidget(self.filename_edit, 1)
        output_layout.addLayout(name_row)
        
        vars_label = QLabel(self.tr("Variables: {layer_name}, {date}, {time}, {user}"))
        vars_label.setStyleSheet("color: gray; font-size: 9px;")
        output_layout.addWidget(vars_label)
        
        content_layout.addWidget(self.output_group)
        
        # === OPTIONS (Split Vector/Raster) ===
        options_row = QHBoxLayout()
        
        # Vector options
        self.vector_options = QGroupBox(self.tr("Vector Options"))
        vector_layout = QVBoxLayout(self.vector_options)
        vector_layout.setContentsMargins(6, 20, 6, 6)  # top margin for title
        vector_layout.setSpacing(4)
        self.export_filtered_cb = QCheckBox(self.tr("Export filtered features only"))
        self.export_filtered_cb.setChecked(True)
        vector_layout.addWidget(self.export_filtered_cb)
        self.include_styles_cb = QCheckBox(self.tr("Include layer styles (.qml)"))
        self.include_styles_cb.setChecked(True)
        vector_layout.addWidget(self.include_styles_cb)
        self.keep_filters_cb = QCheckBox(self.tr("Keep active subset filters"))
        vector_layout.addWidget(self.keep_filters_cb)
        self.export_visible_cb = QCheckBox(self.tr("Export all visible layers"))
        vector_layout.addWidget(self.export_visible_cb)
        self.include_metadata_cb = QCheckBox(self.tr("Include metadata"))
        vector_layout.addWidget(self.include_metadata_cb)
        
        crs_row = QHBoxLayout()
        crs_row.addWidget(QLabel(self.tr("CRS:")))
        self.crs_combo = QComboBox()
        self.crs_combo.addItems(["Project CRS", "Layer CRS", "Custom..."])
        crs_row.addWidget(self.crs_combo, 1)
        vector_layout.addLayout(crs_row)
        
        options_row.addWidget(self.vector_options)
        
        # Raster options
        self.raster_options = QGroupBox(self.tr("Raster Options"))
        raster_layout = QVBoxLayout(self.raster_options)
        raster_layout.setContentsMargins(6, 20, 6, 6)  # top margin for title
        raster_layout.setSpacing(4)
        self.clip_extent_cb = QCheckBox(self.tr("Clip to source extent"))
        self.clip_extent_cb.setChecked(True)
        raster_layout.addWidget(self.clip_extent_cb)
        self.create_pyramids_cb = QCheckBox(self.tr("Create COG pyramids"))
        raster_layout.addWidget(self.create_pyramids_cb)
        self.include_world_cb = QCheckBox(self.tr("Include world file"))
        raster_layout.addWidget(self.include_world_cb)
        
        compress_row = QHBoxLayout()
        compress_row.addWidget(QLabel(self.tr("Compression:")))
        self.compression_combo = QComboBox()
        self.compression_combo.addItems(["None", "LZW", "DEFLATE", "JPEG"])
        self.compression_combo.setCurrentText("LZW")
        compress_row.addWidget(self.compression_combo, 1)
        raster_layout.addLayout(compress_row)
        
        options_row.addWidget(self.raster_options)
        content_layout.addLayout(options_row)
        
        # === LAYERS TO EXPORT ===
        self.layers_group = QgsCollapsibleGroupBox(self.tr("Layers to Export"))
        self.layers_group.setCollapsed(False)
        layers_layout = QVBoxLayout(self.layers_group)
        layers_layout.setContentsMargins(6, 20, 6, 6)  # top margin for title
        layers_layout.setSpacing(4)
        
        # Selection controls row
        selection_row = QHBoxLayout()
        self.select_all_btn = QPushButton(self.tr("☑ Select All"))
        self.select_all_btn.clicked.connect(self._on_select_all)
        selection_row.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton(self.tr("☐ Deselect All"))
        self.deselect_all_btn.clicked.connect(self._on_deselect_all)
        selection_row.addWidget(self.deselect_all_btn)
        
        self.refresh_layers_btn = QPushButton(self.tr("🔄 Refresh"))
        self.refresh_layers_btn.setToolTip(self.tr(
            "Refresh Layers\n\n"
            "Reload the list of filterable layers from project.\n"
            "Use after adding or removing layers."
        ))
        self.refresh_layers_btn.clicked.connect(self._on_refresh_layers)
        selection_row.addWidget(self.refresh_layers_btn)
        
        selection_row.addStretch()
        
        self.layers_count_label = QLabel(self.tr("0 layers selected"))
        self.layers_count_label.setStyleSheet("color: gray;")
        selection_row.addWidget(self.layers_count_label)
        
        layers_layout.addLayout(selection_row)
        
        self.export_table = QTableWidget()
        self.export_table.setColumnCount(4)
        self.export_table.setHorizontalHeaderLabels(["✓", "Layer", "Output", "Status"])
        self.export_table.horizontalHeader().setStretchLastSection(True)
        self.export_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.export_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.export_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.export_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.export_table.setMinimumHeight(120)
        layers_layout.addWidget(self.export_table)
        
        # Export progress
        self.export_progress = QProgressBar()
        self.export_progress.setMinimum(0)
        self.export_progress.setMaximum(100)
        self.export_progress.setValue(0)
        self.export_progress.setVisible(False)
        self.export_progress.setTextVisible(True)
        layers_layout.addWidget(self.export_progress)
        
        content_layout.addWidget(self.layers_group)
        
        # === ACTIONS ===
        self.action_group = QGroupBox(self.tr("Actions"))
        action_layout = QHBoxLayout(self.action_group)
        action_layout.setContentsMargins(6, 20, 6, 6)  # top margin for title
        action_layout.setSpacing(4)
        
        self.export_btn = QPushButton(self.tr("📤 EXPORT SELECTED"))
        self.export_btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 8px;")
        self.export_btn.clicked.connect(self.exportRequested.emit)
        action_layout.addWidget(self.export_btn)
        
        self.export_all_btn = QPushButton(self.tr("📤 EXPORT ALL"))
        self.export_all_btn.clicked.connect(self.exportAllRequested.emit)
        action_layout.addWidget(self.export_all_btn)
        
        self.open_dir_btn = QPushButton(self.tr("📁 Open Output Dir"))
        self.open_dir_btn.clicked.connect(self.openOutputDirRequested.emit)
        action_layout.addWidget(self.open_dir_btn)
        
        content_layout.addWidget(self.action_group)
        
        # Stretch
        content_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
    
    def set_export_layers(self, layers: list):
        """Set the layers available for export.
        
        Args:
            layers: List of (layer, info_dict) tuples
        """
        self.export_table.setRowCount(0)
        self._export_layers = layers
        
        for row, (layer, info) in enumerate(layers):
            self.export_table.insertRow(row)
            
            # Checkbox
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self._update_selection_count)
            self.export_table.setCellWidget(row, 0, checkbox)
            
            # Layer name with icon and info
            is_vector = isinstance(layer, QgsVectorLayer)
            icon = "📍" if is_vector else "🏔️"
            filter_status = info.get('status', '')
            name_item = QTableWidgetItem(f"{icon} {layer.name()} ({filter_status})")
            name_item.setData(Qt.UserRole, layer.id())
            self.export_table.setItem(row, 1, name_item)
            
            # Output filename
            ext = ".gpkg" if is_vector else ".tif"
            output_item = QTableWidgetItem(f"{layer.name()}{ext}")
            self.export_table.setItem(row, 2, output_item)
            
            # Status column (empty initially)
            status_item = QTableWidgetItem("—")
            status_item.setForeground(QColor("#888888"))
            self.export_table.setItem(row, 3, status_item)
        
        self._update_selection_count()
    
    def get_selected_export_layers(self) -> list:
        """Get list of selected layer IDs for export.
        
        Returns:
            List of layer IDs that are checked for export
        """
        selected = []
        for row in range(self.export_table.rowCount()):
            checkbox = self.export_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                item = self.export_table.item(row, 1)
                if item:
                    layer_id = item.data(Qt.UserRole)
                    if layer_id:
                        selected.append(layer_id)
        return selected
    
    def get_export_settings(self) -> dict:
        """Get current export settings.
        
        Returns:
            Dict with all export settings
        """
        return {
            'format': self.format_combo.currentText(),
            'output_dir': self.output_dir.filePath(),
            'filename_pattern': self.filename_edit.text(),
            'vector': {
                'filtered_only': self.export_filtered_cb.isChecked(),
                'include_styles': self.include_styles_cb.isChecked(),
                'keep_filters': self.keep_filters_cb.isChecked(),
                'export_visible': self.export_visible_cb.isChecked(),
                'include_metadata': self.include_metadata_cb.isChecked(),
                'crs': self.crs_combo.currentText()
            },
            'raster': {
                'clip_extent': self.clip_extent_cb.isChecked(),
                'create_pyramids': self.create_pyramids_cb.isChecked(),
                'include_world': self.include_world_cb.isChecked(),
                'compression': self.compression_combo.currentText()
            }
        }
    
    # === BATCH EXPORT HELPERS ===
    
    def _on_select_all(self):
        """Select all layers for export."""
        for row in range(self.export_table.rowCount()):
            checkbox = self.export_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(True)
        self._update_selection_count()
    
    def _on_deselect_all(self):
        """Deselect all layers."""
        for row in range(self.export_table.rowCount()):
            checkbox = self.export_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(False)
        self._update_selection_count()
    
    def _on_refresh_layers(self):
        """Refresh layer list from project."""
        self.refreshLayersRequested.emit()
    
    def _update_selection_count(self):
        """Update the selection count label."""
        count = len(self.get_selected_export_layers())
        total = self.export_table.rowCount()
        self.layers_count_label.setText(f"{count}/{total} layers selected")
    
    def set_export_progress(self, value: int, message: str = ""):
        """Set the export progress.
        
        Args:
            value: Progress value (0-100), -1 to hide
            message: Optional message to show
        """
        if value < 0:
            self.export_progress.setVisible(False)
        else:
            self.export_progress.setVisible(True)
            self.export_progress.setValue(value)
            if message:
                self.export_progress.setFormat(f"{message} - %p%")
            else:
                self.export_progress.setFormat("%p%")
    
    def set_layer_status(self, row: int, status: str, success: bool = True):
        """Set the export status for a layer.
        
        Args:
            row: Table row index
            status: Status text (e.g., "✓ Exported", "✗ Failed")
            success: Whether operation succeeded (for styling)
        """
        if 0 <= row < self.export_table.rowCount():
            status_item = self.export_table.item(row, 3)
            if not status_item:
                status_item = QTableWidgetItem(status)
                self.export_table.setItem(row, 3, status_item)
            else:
                status_item.setText(status)
            
            # Color based on success
            color = QColor("#28a745") if success else QColor("#dc3545")
            status_item.setForeground(color)


class ConfigurationPage(QWidget):
    """Page for plugin configuration.
    
    Contains:
    - UI Settings (profile, theme)
    - Behavior settings
    - Backend settings
    - Raster settings
    - Action buttons
    
    Signals:
        configChanged: Emitted when configuration changes
        saveRequested: Emitted when save requested
        resetRequested: Emitted when reset to defaults requested
    """
    
    configChanged = pyqtSignal(str, object)  # key, value
    saveRequested = pyqtSignal()
    resetRequested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = {}
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the configuration UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)
        
        # === UI SETTINGS ===
        self.ui_group = QgsCollapsibleGroupBox(self.tr("UI Settings"))
        self.ui_group.setCollapsed(False)
        ui_layout = QVBoxLayout(self.ui_group)
        ui_layout.setContentsMargins(6, 20, 6, 6)  # top margin for title
        ui_layout.setSpacing(4)
        
        # UI Profile
        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel(self.tr("UI Profile:")))
        self.profile_combo = QComboBox()
        self.profile_combo.addItems(["Auto", "Compact", "Normal", "HiDPI"])
        self.profile_combo.setToolTip(self.tr(
            "Select UI density profile:\n"
            "• Auto: Automatically detect based on screen DPI\n"
            "• Compact: Smaller fonts and spacing for more content\n"
            "• Normal: Default balanced layout\n"
            "• HiDPI: Larger elements for high-resolution displays"
        ))
        self.profile_combo.currentTextChanged.connect(lambda v: self._emit_change('ui_profile', v))
        profile_row.addWidget(self.profile_combo, 1)
        ui_layout.addLayout(profile_row)
        
        # Theme
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel(self.tr("Theme:")))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Sync with QGIS", "Light", "Dark", "System"])
        self.theme_combo.setToolTip(self.tr(
            "Select color theme:\n"
            "• Sync with QGIS: Match QGIS application theme\n"
            "• Light: Light colors for bright environments\n"
            "• Dark: Dark colors to reduce eye strain\n"
            "• System: Follow operating system preference"
        ))
        self.theme_combo.currentTextChanged.connect(lambda v: self._emit_change('theme', v))
        theme_row.addWidget(self.theme_combo, 1)
        ui_layout.addLayout(theme_row)
        
        content_layout.addWidget(self.ui_group)
        
        # === BEHAVIOR ===
        self.behavior_group = QgsCollapsibleGroupBox(self.tr("Behavior"))
        self.behavior_group.setCollapsed(False)
        behavior_layout = QVBoxLayout(self.behavior_group)
        behavior_layout.setContentsMargins(6, 20, 6, 6)  # top margin for title
        behavior_layout.setSpacing(4)
        
        self.auto_activate_cb = QCheckBox(self.tr("Auto-activate plugin when project is loaded"))
        self.auto_activate_cb.setToolTip(self.tr(
            "Auto-activate on Project Load\n\n"
            "Automatically open FilterMate dockwidget\n"
            "when a QGIS project is loaded.\n"
            "Useful for frequently used filtering workflows."
        ))
        self.auto_activate_cb.stateChanged.connect(lambda s: self._emit_change('auto_activate', s == Qt.Checked))
        behavior_layout.addWidget(self.auto_activate_cb)
        
        self.remember_filters_cb = QCheckBox(self.tr("Remember last filter expression per layer"))
        self.remember_filters_cb.setToolTip(self.tr(
            "Remember Last Filter\n\n"
            "Store and restore the last used filter expression\n"
            "for each layer between sessions.\n"
            "Helps resume work without re-entering filters."
        ))
        self.remember_filters_cb.stateChanged.connect(lambda s: self._emit_change('remember_filters', s == Qt.Checked))
        behavior_layout.addWidget(self.remember_filters_cb)
        
        self.auto_switch_cb = QCheckBox(self.tr("Auto-switch EXPLORING mode based on current layer type"))
        self.auto_switch_cb.setChecked(True)
        self.auto_switch_cb.setToolTip(self.tr(
            "Auto-switch Exploring Mode\n\n"
            "Automatically switch between Vector and Raster\n"
            "exploring pages when selecting different layer types.\n"
            "Disable to stay on the current page."
        ))
        self.auto_switch_cb.stateChanged.connect(lambda s: self._emit_change('auto_switch_exploring', s == Qt.Checked))
        behavior_layout.addWidget(self.auto_switch_cb)
        
        self.advanced_options_cb = QCheckBox(self.tr("Show advanced filtering options"))
        self.advanced_options_cb.setToolTip(self.tr(
            "Show Advanced Options\n\n"
            "Display additional advanced options\n"
            "in the filtering interface.\n"
            "Includes buffer, centroid, and precision settings."
        ))
        self.advanced_options_cb.stateChanged.connect(lambda s: self._emit_change('show_advanced', s == Qt.Checked))
        behavior_layout.addWidget(self.advanced_options_cb)
        
        self.experimental_cb = QCheckBox(self.tr("Enable experimental features"))
        self.experimental_cb.setToolTip(self.tr(
            "Enable Experimental Features\n\n"
            "Enable features that are still in development.\n"
            "May be unstable or change in future versions.\n"
            "Use at your own risk."
        ))
        self.experimental_cb.stateChanged.connect(lambda s: self._emit_change('experimental', s == Qt.Checked))
        behavior_layout.addWidget(self.experimental_cb)
        
        content_layout.addWidget(self.behavior_group)
        
        # === BACKEND SETTINGS ===
        self.backend_group = QgsCollapsibleGroupBox(self.tr("Backend Settings"))
        self.backend_group.setCollapsed(False)
        backend_layout = QVBoxLayout(self.backend_group)
        backend_layout.setContentsMargins(6, 20, 6, 6)  # top margin for title
        backend_layout.setSpacing(4)
        
        # Default backend
        backend_row = QHBoxLayout()
        backend_row.addWidget(QLabel(self.tr("Default Backend:")))
        self.backend_combo = QComboBox()
        self.backend_combo.addItems(["Auto-detect", "PostgreSQL", "Spatialite", "OGR", "Memory"])
        self.backend_combo.currentTextChanged.connect(lambda v: self._emit_change('default_backend', v))
        backend_row.addWidget(self.backend_combo, 1)
        backend_layout.addLayout(backend_row)
        
        # PostgreSQL status
        self.pg_status_label = QLabel(self.tr("PostgreSQL Status: Checking..."))
        self.pg_status_label.setStyleSheet("color: gray;")
        backend_layout.addWidget(self.pg_status_label)
        
        content_layout.addWidget(self.backend_group)
        
        # === RASTER SETTINGS ===
        self.raster_group = QgsCollapsibleGroupBox(self.tr("Raster Settings"))
        self.raster_group.setCollapsed(True)
        raster_layout = QVBoxLayout(self.raster_group)
        raster_layout.setContentsMargins(6, 20, 6, 6)  # top margin for title
        raster_layout.setSpacing(4)
        
        # Default sampling
        sampling_row = QHBoxLayout()
        sampling_row.addWidget(QLabel(self.tr("Default Sampling:")))
        self.sampling_combo = QComboBox()
        self.sampling_combo.addItems(["Centroid", "All Vertices", "Zonal Mean", "Weighted Average"])
        self.sampling_combo.currentTextChanged.connect(lambda v: self._emit_change('raster_sampling', v))
        sampling_row.addWidget(self.sampling_combo, 1)
        raster_layout.addLayout(sampling_row)
        
        # Default clip operation
        clip_row = QHBoxLayout()
        clip_row.addWidget(QLabel(self.tr("Default Clip Op:")))
        self.clip_combo = QComboBox()
        self.clip_combo.addItems(["Clip to extent", "Mask outside", "Mask inside"])
        self.clip_combo.currentTextChanged.connect(lambda v: self._emit_change('raster_clip_op', v))
        clip_row.addWidget(self.clip_combo, 1)
        raster_layout.addLayout(clip_row)
        
        # Memory clips directory
        clips_row = QHBoxLayout()
        clips_row.addWidget(QLabel(self.tr("Memory Clips Dir:")))
        self.clips_dir = QgsFileWidget()
        self.clips_dir.setStorageMode(QgsFileWidget.GetDirectory)
        clips_row.addWidget(self.clips_dir, 1)
        raster_layout.addLayout(clips_row)
        
        # Raster options
        self.use_pyramids_cb = QCheckBox(self.tr("Use pyramids when available"))
        self.use_pyramids_cb.setChecked(True)
        self.use_pyramids_cb.stateChanged.connect(lambda s: self._emit_change('use_pyramids', s == Qt.Checked))
        raster_layout.addWidget(self.use_pyramids_cb)
        
        self.cache_histogram_cb = QCheckBox(self.tr("Cache histogram computations"))
        self.cache_histogram_cb.setChecked(True)
        self.cache_histogram_cb.stateChanged.connect(lambda s: self._emit_change('cache_histogram', s == Qt.Checked))
        raster_layout.addWidget(self.cache_histogram_cb)
        
        content_layout.addWidget(self.raster_group)
        
        # === ACTIONS ===
        self.action_group = QGroupBox(self.tr("Actions"))
        action_layout = QVBoxLayout(self.action_group)
        action_layout.setContentsMargins(6, 20, 6, 6)  # top margin for title
        action_layout.setSpacing(4)
        
        action_row1 = QHBoxLayout()
        self.open_config_btn = QPushButton(self.tr("📁 Open Config File"))
        action_row1.addWidget(self.open_config_btn)
        
        self.save_btn = QPushButton(self.tr("💾 Save"))
        self.save_btn.clicked.connect(self.saveRequested.emit)
        action_row1.addWidget(self.save_btn)
        
        self.reset_btn = QPushButton(self.tr("↻ Reset to Defaults"))
        self.reset_btn.clicked.connect(self.resetRequested.emit)
        action_row1.addWidget(self.reset_btn)
        action_layout.addLayout(action_row1)
        
        action_row2 = QHBoxLayout()
        self.copy_btn = QPushButton(self.tr("📋 Copy Config"))
        action_row2.addWidget(self.copy_btn)
        
        self.import_btn = QPushButton(self.tr("📥 Import"))
        action_row2.addWidget(self.import_btn)
        
        self.export_btn = QPushButton(self.tr("📤 Export"))
        action_row2.addWidget(self.export_btn)
        action_layout.addLayout(action_row2)
        
        content_layout.addWidget(self.action_group)
        
        # Stretch
        content_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
    
    def _emit_change(self, key: str, value):
        """Emit configuration change signal."""
        self._config[key] = value
        self.configChanged.emit(key, value)
    
    def load_config(self, config: dict):
        """Load configuration values.
        
        Args:
            config: Configuration dictionary
        """
        self._config = config.copy()
        
        # UI Settings
        if 'ui_profile' in config:
            idx = self.profile_combo.findText(config['ui_profile'])
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)
        
        if 'theme' in config:
            idx = self.theme_combo.findText(config['theme'])
            if idx >= 0:
                self.theme_combo.setCurrentIndex(idx)
        
        # Behavior
        self.auto_activate_cb.setChecked(config.get('auto_activate', False))
        self.remember_filters_cb.setChecked(config.get('remember_filters', True))
        self.auto_switch_cb.setChecked(config.get('auto_switch_exploring', True))
        self.advanced_options_cb.setChecked(config.get('show_advanced', False))
        self.experimental_cb.setChecked(config.get('experimental', False))
        
        # Backend
        if 'default_backend' in config:
            idx = self.backend_combo.findText(config['default_backend'])
            if idx >= 0:
                self.backend_combo.setCurrentIndex(idx)
        
        # Raster
        if 'raster_sampling' in config:
            idx = self.sampling_combo.findText(config['raster_sampling'])
            if idx >= 0:
                self.sampling_combo.setCurrentIndex(idx)
        
        self.use_pyramids_cb.setChecked(config.get('use_pyramids', True))
        self.cache_histogram_cb.setChecked(config.get('cache_histogram', True))
    
    def get_config(self) -> dict:
        """Get current configuration.
        
        Returns:
            Configuration dictionary
        """
        return {
            'ui_profile': self.profile_combo.currentText(),
            'theme': self.theme_combo.currentText(),
            'auto_activate': self.auto_activate_cb.isChecked(),
            'remember_filters': self.remember_filters_cb.isChecked(),
            'auto_switch_exploring': self.auto_switch_cb.isChecked(),
            'show_advanced': self.advanced_options_cb.isChecked(),
            'experimental': self.experimental_cb.isChecked(),
            'default_backend': self.backend_combo.currentText(),
            'raster_sampling': self.sampling_combo.currentText(),
            'raster_clip_op': self.clip_combo.currentText(),
            'clips_dir': self.clips_dir.filePath(),
            'use_pyramids': self.use_pyramids_cb.isChecked(),
            'cache_histogram': self.cache_histogram_cb.isChecked()
        }
    
    def set_config_value(self, key: str, value):
        """Set a single configuration value in the UI.
        
        Used to sync UI with config.json on load/reset.
        Blocks signals to avoid emitting configChanged during load.
        
        Args:
            key: Configuration key
            value: Value to set
        """
        # Map keys to widgets with their setter methods
        widget_map = {
            'ui_profile': (self.profile_combo, 'setCurrentText'),
            'theme': (self.theme_combo, 'setCurrentText'),
            'auto_activate': (self.auto_activate_cb, 'setChecked'),
            'remember_filters': (self.remember_filters_cb, 'setChecked'),
            'auto_switch_exploring': (self.auto_switch_cb, 'setChecked'),
            'show_advanced': (self.advanced_options_cb, 'setChecked'),
            'experimental': (self.experimental_cb, 'setChecked'),
            'default_backend': (self.backend_combo, 'setCurrentText'),
            'raster_sampling': (self.sampling_combo, 'setCurrentText'),
            'raster_clip_op': (self.clip_combo, 'setCurrentText'),
            'use_pyramids': (self.use_pyramids_cb, 'setChecked'),
            'cache_histogram': (self.cache_histogram_cb, 'setChecked'),
        }
        
        if key in widget_map:
            widget, method = widget_map[key]
            # Block signals to avoid re-emitting configChanged
            widget.blockSignals(True)
            try:
                getattr(widget, method)(value)
                self._config[key] = value
            finally:
                widget.blockSignals(False)
    
    def update_postgresql_status(self, available: bool):
        """Update PostgreSQL availability status.
        
        Args:
            available: Whether PostgreSQL is available
        """
        if available:
            self.pg_status_label.setText(self.tr("PostgreSQL Status: ✅ Available (psycopg2 installed)"))
            self.pg_status_label.setStyleSheet("color: green;")
        else:
            self.pg_status_label.setText(self.tr("PostgreSQL Status: ❌ Not available"))
            self.pg_status_label.setStyleSheet("color: red;")


class ToolsetToolBox(BaseToolBox):
    """QToolBox for TOOLSET functionality.
    
    Contains three pages:
    - Page 1: Filtering
    - Page 2: Exporting
    - Page 3: Configuration
    
    Signals:
        filterRequested: Emitted when filter execution requested
        exportRequested: Emitted when export requested
        configChanged: Emitted when configuration changes
    """
    
    filterRequested = pyqtSignal()
    exportRequested = pyqtSignal()
    configChanged = pyqtSignal(str, object)  # key, value
    
    # Page name constants
    PAGE_FILTERING = "🔍 FILTERING"
    PAGE_EXPORTING = "📤 EXPORTING"
    PAGE_CONFIGURATION = "⚙️ CONFIGURATION"
    
    def __init__(self, parent=None):
        super().__init__(parent, title="TOOLSET")
        self._setup_pages()
        self._connect_page_signals()
    
    def _setup_pages(self):
        """Setup the three toolset pages."""
        # Filtering page
        self._filtering_page = FilteringPage()
        self.add_page(
            self.PAGE_FILTERING,
            self._filtering_page,
            tooltip="Filter layers based on selection"
        )
        
        # Exporting page
        self._exporting_page = ExportingPage()
        self.add_page(
            self.PAGE_EXPORTING,
            self._exporting_page,
            tooltip="Export filtered layers"
        )
        
        # Configuration page
        self._configuration_page = ConfigurationPage()
        self.add_page(
            self.PAGE_CONFIGURATION,
            self._configuration_page,
            tooltip="Plugin settings and configuration"
        )
        
        # Start with filtering page
        self.activate_page(self.PAGE_FILTERING)
    
    def _connect_page_signals(self):
        """Connect page signals to toolbox signals."""
        # Filtering signals
        self._filtering_page.filterRequested.connect(self.filterRequested)
        
        # Exporting signals
        self._exporting_page.exportRequested.connect(self.exportRequested)
        
        # Configuration signals
        self._configuration_page.configChanged.connect(self.configChanged)
    
    def get_filtering_page(self) -> FilteringPage:
        """Get the filtering page widget."""
        return self._filtering_page
    
    def get_exporting_page(self) -> ExportingPage:
        """Get the exporting page widget."""
        return self._exporting_page
    
    def get_configuration_page(self) -> ConfigurationPage:
        """Get the configuration page widget."""
        return self._configuration_page
    
    def set_source(self, layer, selection_info: dict = None):
        """Set the source layer for filtering.
        
        Args:
            layer: Source layer
            selection_info: Selection information
        """
        self._filtering_page.set_source(layer, selection_info)
        self._filtering_page.refresh_target_layers()
    
    def get_selected_targets(self) -> list:
        """Get selected target layers with operations."""
        return self._filtering_page.get_selected_targets()
    
    def get_export_settings(self) -> dict:
        """Get current export settings."""
        return self._exporting_page.get_export_settings()
    
    def load_config(self, config: dict):
        """Load configuration."""
        self._configuration_page.load_config(config)
    
    def get_config(self) -> dict:
        """Get current configuration."""
        return self._configuration_page.get_config()

# -*- coding: utf-8 -*-
"""
FilterMate - EXPLORING QToolBox

Two-page QToolBox for data exploration:
- Page 1: Vector Exploring (Single Selection, Multiple Selection, Custom Expression)
- Page 2: Raster Exploring (Statistics, Histogram, Value Selection, Mask & Clip)

Auto-switches between pages based on current layer type (Vector/Raster).
"""

from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QSpinBox, QDoubleSpinBox, QCheckBox,
    QFrame, QSizePolicy, QScrollArea, QGroupBox, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from qgis.PyQt.QtCore import pyqtSignal, Qt, QTimer
from qgis.PyQt.QtGui import QIcon, QFont

from qgis.core import QgsVectorLayer, QgsRasterLayer, QgsProject, Qgis
from qgis.gui import QgsCollapsibleGroupBox

from .base_toolbox import BaseToolBox
from ..custom_widgets import QgsCheckableComboBoxFeaturesListPickerWidget

import logging
logger = logging.getLogger('FilterMate.ExploringToolBox')


class VectorExploringPage(QWidget):
    """Page for vector layer exploration.
    
    Contains collapsible sections for:
    - Single Selection (field + value)
    - Multiple Selection (multi-value picker)  
    - Custom Expression (expression builder)
    
    Signals:
        selectionChanged: Emitted when selection changes
        filterRequested: Emitted when filter button clicked
        clearRequested: Emitted when clear button clicked
    """
    
    selectionChanged = pyqtSignal(str, object)  # field_name, value(s)
    filterRequested = pyqtSignal()
    clearRequested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_layer = None
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the vector exploring UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)
        
        # === SINGLE SELECTION ===
        self.single_group = QgsCollapsibleGroupBox("🎯 Single Selection")
        self.single_group.setCollapsed(False)
        single_layout = QVBoxLayout(self.single_group)
        single_layout.setContentsMargins(6, 20, 6, 6)  # top margin for title
        single_layout.setSpacing(4)
        
        # Field selector
        field_row = QHBoxLayout()
        field_row.addWidget(QLabel("Field:"))
        self.field_combo = QComboBox()
        self.field_combo.setMinimumWidth(150)
        self.field_combo.currentTextChanged.connect(self._on_field_changed)
        field_row.addWidget(self.field_combo, 1)
        single_layout.addLayout(field_row)
        
        # Value selector
        value_row = QHBoxLayout()
        value_row.addWidget(QLabel("Value:"))
        self.value_combo = QComboBox()
        self.value_combo.setEditable(True)
        self.value_combo.setMinimumWidth(150)
        self.value_combo.currentTextChanged.connect(self._on_value_changed)
        value_row.addWidget(self.value_combo, 1)
        
        self.filter_btn = QPushButton("🔍")
        self.filter_btn.setFixedWidth(30)
        self.filter_btn.setToolTip("Apply filter")
        self.filter_btn.clicked.connect(self.filterRequested.emit)
        value_row.addWidget(self.filter_btn)
        
        self.clear_btn = QPushButton("✕")
        self.clear_btn.setFixedWidth(30)
        self.clear_btn.setToolTip("Clear selection")
        self.clear_btn.clicked.connect(self.clearRequested.emit)
        value_row.addWidget(self.clear_btn)
        single_layout.addLayout(value_row)
        
        # Options
        options_row = QHBoxLayout()
        self.case_sensitive_cb = QCheckBox("Case sensitive")
        self.exact_match_cb = QCheckBox("Exact match")
        options_row.addWidget(self.case_sensitive_cb)
        options_row.addWidget(self.exact_match_cb)
        options_row.addStretch()
        single_layout.addLayout(options_row)
        
        # Result indicator
        self.result_label = QLabel("Result: - / -")
        self.result_label.setStyleSheet("color: gray; font-style: italic;")
        single_layout.addWidget(self.result_label)
        
        content_layout.addWidget(self.single_group)
        
        # === MULTIPLE SELECTION ===
        self.multiple_group = QgsCollapsibleGroupBox("📋 Multiple Selection")
        self.multiple_group.setCollapsed(True)
        multiple_layout = QVBoxLayout(self.multiple_group)
        multiple_layout.setContentsMargins(6, 20, 6, 6)  # top margin for title
        multiple_layout.setSpacing(4)
        
        # Field selector for multiple
        multi_field_row = QHBoxLayout()
        multi_field_row.addWidget(QLabel("Field:"))
        self.multi_field_combo = QComboBox()
        self.multi_field_combo.currentTextChanged.connect(self._on_multi_field_changed)
        multi_field_row.addWidget(self.multi_field_combo, 1)
        multiple_layout.addLayout(multi_field_row)
        
        # Multi-value picker placeholder
        self.multi_value_label = QLabel("Select multiple values from the field above")
        self.multi_value_label.setStyleSheet("color: gray;")
        multiple_layout.addWidget(self.multi_value_label)
        
        # Will be replaced with actual multi-picker widget
        self.multi_values_placeholder = QWidget()
        self.multi_values_layout = QVBoxLayout(self.multi_values_placeholder)
        self.multi_values_layout.setContentsMargins(0, 0, 0, 0)
        multiple_layout.addWidget(self.multi_values_placeholder)
        
        content_layout.addWidget(self.multiple_group)
        
        # === CUSTOM EXPRESSION ===
        self.expression_group = QgsCollapsibleGroupBox("🔧 Custom Expression")
        self.expression_group.setCollapsed(True)
        expression_layout = QVBoxLayout(self.expression_group)
        expression_layout.setContentsMargins(6, 20, 6, 6)  # top margin for title
        expression_layout.setSpacing(4)
        
        # Expression builder placeholder
        self.expression_label = QLabel("Build advanced filter with expression builder")
        self.expression_label.setStyleSheet("color: gray;")
        expression_layout.addWidget(self.expression_label)
        
        # Will add QgsFieldExpressionWidget here
        self.expression_placeholder = QWidget()
        self.expression_inner_layout = QVBoxLayout(self.expression_placeholder)
        self.expression_inner_layout.setContentsMargins(0, 0, 0, 0)
        expression_layout.addWidget(self.expression_placeholder)
        
        content_layout.addWidget(self.expression_group)
        
        # Stretch to push content to top
        content_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
    
    def set_layer(self, layer: QgsVectorLayer):
        """Set the current layer and populate fields.
        
        Args:
            layer: Vector layer to explore
        """
        self._current_layer = layer
        self._populate_fields()
    
    def _populate_fields(self):
        """Populate field combos from current layer."""
        self.field_combo.clear()
        self.multi_field_combo.clear()
        self.value_combo.clear()
        
        if not self._current_layer:
            return
        
        try:
            fields = self._current_layer.fields()
            for field in fields:
                self.field_combo.addItem(field.name())
                self.multi_field_combo.addItem(field.name())
        except Exception as e:
            logger.error(f"Error populating fields: {e}")
    
    def _on_field_changed(self, field_name: str):
        """Handle field selection change."""
        self._populate_values(field_name)
    
    def _on_multi_field_changed(self, field_name: str):
        """Handle multi-field selection change."""
        # TODO: Populate multi-value picker
        pass
    
    def _populate_values(self, field_name: str):
        """Populate value combo for the selected field."""
        self.value_combo.clear()
        
        if not self._current_layer or not field_name:
            return
        
        try:
            # Get unique values (limited to avoid performance issues)
            idx = self._current_layer.fields().indexOf(field_name)
            if idx >= 0:
                values = self._current_layer.uniqueValues(idx, limit=500)
                for val in sorted(values, key=lambda x: str(x) if x else ""):
                    if val is not None:
                        self.value_combo.addItem(str(val))
        except Exception as e:
            logger.error(f"Error populating values: {e}")
    
    def _on_value_changed(self, value: str):
        """Handle value selection change."""
        field = self.field_combo.currentText()
        if field:
            self.selectionChanged.emit(field, value)
    
    def update_result(self, selected: int, total: int):
        """Update the result indicator.
        
        Args:
            selected: Number of selected features
            total: Total number of features
        """
        pct = (selected / total * 100) if total > 0 else 0
        self.result_label.setText(f"Result: {selected:,} / {total:,} ({pct:.2f}%)")
    
    def get_current_filter(self) -> dict:
        """Get current filter parameters.
        
        Returns:
            Dict with filter parameters
        """
        return {
            'type': 'single',
            'field': self.field_combo.currentText(),
            'value': self.value_combo.currentText(),
            'case_sensitive': self.case_sensitive_cb.isChecked(),
            'exact_match': self.exact_match_cb.isChecked()
        }


class RasterExploringPage(QWidget):
    """Page for raster layer exploration.
    
    Contains collapsible sections for:
    - Statistics (Min, Max, Mean, StdDev, NoData)
    - Value Selection (Interactive histogram with range selection)
    - Mask & Clip Operations
    - Memory Clips Manager
    
    Signals:
        rangeChanged: Emitted when value range changes (min, max)
        statisticsComputed: Emitted when statistics are computed
        clipRequested: Emitted when clip operation requested
    """
    
    rangeChanged = pyqtSignal(float, float)  # min, max
    statisticsComputed = pyqtSignal(dict)  # stats dict
    clipRequested = pyqtSignal(str, dict)  # operation, parameters
    pickFromMapRequested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_layer = None
        self._stats = {}
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the raster exploring UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)
        
        # === RASTER INFO HEADER ===
        info_row = QHBoxLayout()
        info_row.addWidget(QLabel("Band:"))
        self.band_combo = QComboBox()
        self.band_combo.setMinimumWidth(120)
        self.band_combo.currentIndexChanged.connect(self._on_band_changed)
        info_row.addWidget(self.band_combo, 1)
        content_layout.addLayout(info_row)
        
        # === STATISTICS ===
        self.stats_group = QgsCollapsibleGroupBox("📊 Statistics")
        self.stats_group.setCollapsed(False)
        stats_layout = QVBoxLayout(self.stats_group)
        stats_layout.setContentsMargins(6, 20, 6, 6)  # top margin for title
        stats_layout.setSpacing(4)
        
        # Stats grid
        stats_grid = QHBoxLayout()
        
        # Create stat labels
        self.stat_labels = {}
        for stat_name in ['Min', 'Max', 'Mean', 'StdDev', 'NoData']:
            col = QVBoxLayout()
            header = QLabel(stat_name)
            header.setAlignment(Qt.AlignCenter)
            header.setStyleSheet("font-weight: bold; font-size: 9px;")
            col.addWidget(header)
            
            value = QLabel("-")
            value.setAlignment(Qt.AlignCenter)
            value.setStyleSheet("color: #2a82da;")
            col.addWidget(value)
            self.stat_labels[stat_name] = value
            
            stats_grid.addLayout(col)
        
        stats_layout.addLayout(stats_grid)
        
        # Metadata row
        self.metadata_label = QLabel("Data: - | Res: - | Size: -")
        self.metadata_label.setStyleSheet("color: gray; font-size: 9px;")
        
        meta_row = QHBoxLayout()
        meta_row.addWidget(self.metadata_label, 1)
        
        self.refresh_stats_btn = QPushButton("↻")
        self.refresh_stats_btn.setFixedWidth(30)
        self.refresh_stats_btn.setToolTip("Refresh statistics")
        self.refresh_stats_btn.clicked.connect(self._compute_statistics)
        meta_row.addWidget(self.refresh_stats_btn)
        
        stats_layout.addLayout(meta_row)
        content_layout.addWidget(self.stats_group)
        
        # === VALUE SELECTION ===
        self.value_group = QgsCollapsibleGroupBox("📈 Value Selection")
        self.value_group.setCollapsed(False)
        value_layout = QVBoxLayout(self.value_group)
        value_layout.setContentsMargins(6, 20, 6, 6)  # top margin for title
        value_layout.setSpacing(4)
        
        # Histogram placeholder (will be replaced with actual histogram widget)
        self.histogram_frame = QFrame()
        self.histogram_frame.setMinimumHeight(100)
        self.histogram_frame.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        """)
        histogram_inner = QVBoxLayout(self.histogram_frame)
        histogram_label = QLabel("📊 Interactive Histogram\n(Coming in Sprint 2)")
        histogram_label.setAlignment(Qt.AlignCenter)
        histogram_label.setStyleSheet("color: gray;")
        histogram_inner.addWidget(histogram_label)
        value_layout.addWidget(self.histogram_frame)
        
        # Range selection
        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("Range:"))
        
        self.min_spin = QDoubleSpinBox()
        self.min_spin.setDecimals(2)
        self.min_spin.setRange(-999999, 999999)
        self.min_spin.valueChanged.connect(self._on_range_changed)
        range_row.addWidget(QLabel("Min"))
        range_row.addWidget(self.min_spin)
        
        range_row.addWidget(QLabel("◄────►"))
        
        self.max_spin = QDoubleSpinBox()
        self.max_spin.setDecimals(2)
        self.max_spin.setRange(-999999, 999999)
        self.max_spin.valueChanged.connect(self._on_range_changed)
        range_row.addWidget(QLabel("Max"))
        range_row.addWidget(self.max_spin)
        
        value_layout.addLayout(range_row)
        
        # Predicate selection
        predicate_row = QHBoxLayout()
        predicate_row.addWidget(QLabel("Predicate:"))
        self.predicate_combo = QComboBox()
        self.predicate_combo.addItems([
            "Within Range (min ≤ val ≤ max)",
            "Outside Range (val < min OR val > max)",
            "Above Value (val > min)",
            "Below Value (val < max)",
            "Is NoData"
        ])
        predicate_row.addWidget(self.predicate_combo, 1)
        value_layout.addLayout(predicate_row)
        
        # Pixels info and pick button
        pick_row = QHBoxLayout()
        self.pixels_label = QLabel("Pixels: - / - (-)")
        self.pixels_label.setStyleSheet("color: gray;")
        pick_row.addWidget(self.pixels_label, 1)
        
        self.pick_btn = QPushButton("🔬 Pick from Map")
        self.pick_btn.clicked.connect(self.pickFromMapRequested.emit)
        pick_row.addWidget(self.pick_btn)
        
        value_layout.addLayout(pick_row)
        content_layout.addWidget(self.value_group)
        
        # === MASK & CLIP ===
        self.mask_group = QgsCollapsibleGroupBox("🎭 Mask & Clip Operations")
        self.mask_group.setCollapsed(True)
        mask_layout = QVBoxLayout(self.mask_group)
        mask_layout.setContentsMargins(6, 20, 6, 6)  # top margin for title
        mask_layout.setSpacing(4)
        
        self.mask_info_label = QLabel("Clip/Mask raster with vector geometries")
        self.mask_info_label.setStyleSheet("color: gray;")
        mask_layout.addWidget(self.mask_info_label)
        
        # Clip operation selector
        clip_row = QHBoxLayout()
        clip_row.addWidget(QLabel("Operation:"))
        self.clip_operation_combo = QComboBox()
        self.clip_operation_combo.addItems([
            "Clip to extent",
            "Mask outside",
            "Mask inside",
            "Zonal statistics"
        ])
        clip_row.addWidget(self.clip_operation_combo, 1)
        mask_layout.addLayout(clip_row)
        
        # Vector source for clip
        vector_row = QHBoxLayout()
        vector_row.addWidget(QLabel("Vector:"))
        self.clip_vector_combo = QComboBox()
        vector_row.addWidget(self.clip_vector_combo, 1)
        mask_layout.addLayout(vector_row)
        
        # Clip button
        self.clip_btn = QPushButton("Execute Clip/Mask")
        self.clip_btn.clicked.connect(self._on_clip_requested)
        mask_layout.addWidget(self.clip_btn)
        
        content_layout.addWidget(self.mask_group)
        
        # === MEMORY CLIPS MANAGER ===
        self.clips_group = QgsCollapsibleGroupBox("💾 Memory Clips (0)")
        self.clips_group.setCollapsed(True)
        clips_layout = QVBoxLayout(self.clips_group)
        clips_layout.setContentsMargins(6, 20, 6, 6)  # top margin for title
        clips_layout.setSpacing(4)
        
        # Clips list widget
        self.clips_list = QListWidget()
        self.clips_list.setMinimumHeight(80)
        self.clips_list.setMaximumHeight(150)
        self.clips_list.setAlternatingRowColors(True)
        self.clips_list.setSelectionMode(QListWidget.SingleSelection)
        self.clips_list.itemDoubleClicked.connect(self._on_clip_double_clicked)
        self.clips_list.currentRowChanged.connect(lambda _: self._update_clip_actions_state())
        clips_layout.addWidget(self.clips_list)
        
        # Clip actions row
        clip_actions = QHBoxLayout()
        
        self.add_to_project_btn = QPushButton("➕ Add to Project")
        self.add_to_project_btn.setToolTip("Add selected clip as a new layer in the project")
        self.add_to_project_btn.clicked.connect(self._on_add_clip_to_project)
        clip_actions.addWidget(self.add_to_project_btn)
        
        self.delete_clip_btn = QPushButton("🗑️ Delete")
        self.delete_clip_btn.setToolTip("Delete selected memory clip")
        self.delete_clip_btn.clicked.connect(self._on_delete_clip)
        clip_actions.addWidget(self.delete_clip_btn)
        
        clips_layout.addLayout(clip_actions)
        
        clip_actions_row2 = QHBoxLayout()
        
        self.export_clip_btn = QPushButton("💾 Export...")
        self.export_clip_btn.setToolTip("Export selected clip to file")
        self.export_clip_btn.clicked.connect(self._on_export_clip)
        clip_actions_row2.addWidget(self.export_clip_btn)
        
        self.clear_all_clips_btn = QPushButton("🧹 Clear All")
        self.clear_all_clips_btn.setToolTip("Delete all memory clips")
        self.clear_all_clips_btn.clicked.connect(self._on_clear_all_clips)
        clip_actions_row2.addWidget(self.clear_all_clips_btn)
        
        clips_layout.addLayout(clip_actions_row2)
        
        # Initially disable actions (no selection)
        self._update_clip_actions_state()
        
        content_layout.addWidget(self.clips_group)
        
        # === ZONAL STATISTICS RESULTS ===
        self.zonal_group = QgsCollapsibleGroupBox("📊 Zonal Statistics Results")
        self.zonal_group.setCollapsed(True)
        zonal_layout = QVBoxLayout(self.zonal_group)
        zonal_layout.setContentsMargins(6, 20, 6, 6)  # top margin for title
        zonal_layout.setSpacing(4)
        
        # Results table
        self.zonal_table = QTableWidget()
        self.zonal_table.setColumnCount(2)
        self.zonal_table.setHorizontalHeaderLabels(["Statistic", "Value"])
        self.zonal_table.horizontalHeader().setStretchLastSection(True)
        self.zonal_table.setMinimumHeight(120)
        self.zonal_table.setMaximumHeight(200)
        self.zonal_table.setAlternatingRowColors(True)
        zonal_layout.addWidget(self.zonal_table)
        
        # Actions row
        zonal_actions = QHBoxLayout()
        
        self.copy_stats_btn = QPushButton("📋 Copy")
        self.copy_stats_btn.setToolTip("Copy statistics to clipboard")
        self.copy_stats_btn.clicked.connect(self._on_copy_zonal_stats)
        zonal_actions.addWidget(self.copy_stats_btn)
        
        self.export_stats_btn = QPushButton("📤 Export CSV")
        self.export_stats_btn.setToolTip("Export statistics to CSV file")
        self.export_stats_btn.clicked.connect(self._on_export_zonal_stats)
        zonal_actions.addWidget(self.export_stats_btn)
        
        self.add_to_layer_btn = QPushButton("➕ Add to Layer")
        self.add_to_layer_btn.setToolTip("Add statistics as attributes to source vector layer")
        self.add_to_layer_btn.clicked.connect(self._on_add_stats_to_layer)
        zonal_actions.addWidget(self.add_to_layer_btn)
        
        zonal_layout.addLayout(zonal_actions)
        
        # Info label
        self.zonal_info_label = QLabel("Run 'Zonal statistics' operation to compute results")
        self.zonal_info_label.setStyleSheet("color: gray; font-size: 10px;")
        self.zonal_info_label.setWordWrap(True)
        zonal_layout.addWidget(self.zonal_info_label)
        
        content_layout.addWidget(self.zonal_group)
        
        # Stretch to push content to top
        content_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
    
    def set_layer(self, layer: QgsRasterLayer):
        """Set the current raster layer.
        
        Args:
            layer: Raster layer to explore
        """
        self._current_layer = layer
        self._populate_bands()
        self._compute_statistics()
        self._populate_vector_layers()
    
    def _populate_bands(self):
        """Populate band combo from current layer."""
        self.band_combo.clear()
        
        if not self._current_layer:
            return
        
        try:
            band_count = self._current_layer.bandCount()
            for i in range(1, band_count + 1):
                band_name = self._current_layer.bandName(i)
                self.band_combo.addItem(f"{i}-{band_name}", i)
        except Exception as e:
            logger.error(f"Error populating bands: {e}")
    
    def _populate_vector_layers(self):
        """Populate vector layer combo for clip operations."""
        self.clip_vector_combo.clear()
        
        try:
            project = QgsProject.instance()
            for layer in project.mapLayers().values():
                if isinstance(layer, QgsVectorLayer):
                    self.clip_vector_combo.addItem(layer.name(), layer.id())
        except Exception as e:
            logger.error(f"Error populating vector layers: {e}")
    
    def _on_band_changed(self, index: int):
        """Handle band selection change."""
        self._compute_statistics()
    
    def _compute_statistics(self):
        """Compute and display raster statistics."""
        if not self._current_layer:
            return
        
        try:
            band = self.band_combo.currentData() or 1
            provider = self._current_layer.dataProvider()
            
            if provider:
                stats = provider.bandStatistics(band, Qgis.RasterBandStatistic.All)
                
                self._stats = {
                    'min': stats.minimumValue,
                    'max': stats.maximumValue,
                    'mean': stats.mean,
                    'stddev': stats.stdDev
                }
                
                # Update labels
                self.stat_labels['Min'].setText(f"{stats.minimumValue:.2f}")
                self.stat_labels['Max'].setText(f"{stats.maximumValue:.2f}")
                self.stat_labels['Mean'].setText(f"{stats.mean:.2f}")
                self.stat_labels['StdDev'].setText(f"{stats.stdDev:.2f}")
                
                # Get nodata value
                if provider.sourceHasNoDataValue(band):
                    nodata = provider.sourceNoDataValue(band)
                    self.stat_labels['NoData'].setText(f"{nodata:.0f}")
                    self._stats['nodata'] = nodata
                else:
                    self.stat_labels['NoData'].setText("-")
                    self._stats['nodata'] = None
                
                # Update range spinboxes
                self.min_spin.setRange(stats.minimumValue, stats.maximumValue)
                self.max_spin.setRange(stats.minimumValue, stats.maximumValue)
                self.min_spin.setValue(stats.minimumValue)
                self.max_spin.setValue(stats.maximumValue)
                
                # Update metadata
                width = self._current_layer.width()
                height = self._current_layer.height()
                res_x = self._current_layer.rasterUnitsPerPixelX()
                res_y = self._current_layer.rasterUnitsPerPixelY()
                data_type = provider.dataType(band)
                
                type_names = {1: 'Byte', 2: 'UInt16', 3: 'Int16', 4: 'UInt32', 
                             5: 'Int32', 6: 'Float32', 7: 'Float64'}
                type_name = type_names.get(data_type, 'Unknown')
                
                self.metadata_label.setText(
                    f"Data: {type_name} | Res: {res_x:.1f}×{res_y:.1f} | Size: {width}×{height}"
                )
                
                self.statisticsComputed.emit(self._stats)
                
        except Exception as e:
            logger.error(f"Error computing statistics: {e}")
    
    def _on_range_changed(self):
        """Handle range value change."""
        min_val = self.min_spin.value()
        max_val = self.max_spin.value()
        self.rangeChanged.emit(min_val, max_val)
        self._update_pixel_count()
    
    def _update_pixel_count(self):
        """Update the pixel count for current range."""
        # TODO: Implement actual pixel counting based on range
        self.pixels_label.setText("Pixels: calculating...")
    
    def _on_clip_requested(self):
        """Handle clip/mask request."""
        operation = self.clip_operation_combo.currentText()
        vector_id = self.clip_vector_combo.currentData()
        
        params = {
            'operation': operation,
            'vector_layer_id': vector_id,
            'band': self.band_combo.currentData() or 1
        }
        
        self.clipRequested.emit(operation, params)
    
    def get_current_range(self) -> tuple:
        """Get current value range selection.
        
        Returns:
            Tuple of (min, max) values
        """
        return (self.min_spin.value(), self.max_spin.value())
    
    def get_predicate(self) -> str:
        """Get current predicate selection.
        
        Returns:
            Predicate string
        """
        return self.predicate_combo.currentText()
    
    # === MEMORY CLIPS MANAGER METHODS ===
    
    def _update_clip_actions_state(self):
        """Update enabled state of clip action buttons based on selection."""
        has_selection = self.clips_list.currentRow() >= 0
        has_clips = self.clips_list.count() > 0
        
        self.add_to_project_btn.setEnabled(has_selection)
        self.delete_clip_btn.setEnabled(has_selection)
        self.export_clip_btn.setEnabled(has_selection)
        self.clear_all_clips_btn.setEnabled(has_clips)
    
    def add_memory_clip(self, clip_name: str, clip_data: dict):
        """Add a memory clip to the list.
        
        Args:
            clip_name: Display name for the clip
            clip_data: Clip metadata (layer_path, extent, operation, timestamp)
        """
        item = QListWidgetItem(f"🖼️ {clip_name}")
        item.setData(Qt.UserRole, clip_data)
        item.setToolTip(
            f"Source: {clip_data.get('source_layer', 'Unknown')}\n"
            f"Operation: {clip_data.get('operation', 'Unknown')}\n"
            f"Created: {clip_data.get('timestamp', 'Unknown')}"
        )
        self.clips_list.addItem(item)
        
        # Update group title
        count = self.clips_list.count()
        self.clips_group.setTitle(f"💾 Memory Clips ({count})")
        self._update_clip_actions_state()
        
        # Auto-expand when clips exist
        if count == 1:
            self.clips_group.setCollapsed(False)
    
    def get_selected_clip(self) -> dict:
        """Get the currently selected clip data.
        
        Returns:
            Clip data dict or None if no selection
        """
        item = self.clips_list.currentItem()
        if item:
            return item.data(Qt.UserRole)
        return None
    
    def _on_clip_double_clicked(self, item: QListWidgetItem):
        """Handle double-click on clip to add to project."""
        self._on_add_clip_to_project()
    
    def _on_add_clip_to_project(self):
        """Add selected clip as layer to current project."""
        clip_data = self.get_selected_clip()
        if not clip_data:
            return
        
        try:
            layer_path = clip_data.get('layer_path')
            if layer_path:
                clip_name = self.clips_list.currentItem().text().replace("🖼️ ", "")
                layer = QgsRasterLayer(layer_path, clip_name)
                if layer.isValid():
                    QgsProject.instance().addMapLayer(layer)
                    logger.info(f"Added memory clip to project: {clip_name}")
                else:
                    logger.warning(f"Invalid clip layer: {layer_path}")
        except Exception as e:
            logger.error(f"Failed to add clip to project: {e}")
    
    def _on_delete_clip(self):
        """Delete selected memory clip."""
        row = self.clips_list.currentRow()
        if row >= 0:
            item = self.clips_list.takeItem(row)
            clip_data = item.data(Qt.UserRole)
            
            # Optionally delete the file
            layer_path = clip_data.get('layer_path')
            if layer_path:
                try:
                    import os
                    if os.path.exists(layer_path):
                        os.remove(layer_path)
                        logger.debug(f"Deleted clip file: {layer_path}")
                except Exception as e:
                    logger.warning(f"Could not delete clip file: {e}")
            
            # Update UI
            count = self.clips_list.count()
            self.clips_group.setTitle(f"💾 Memory Clips ({count})")
            self._update_clip_actions_state()
    
    def _on_export_clip(self):
        """Export selected clip to file."""
        clip_data = self.get_selected_clip()
        if not clip_data:
            return
        
        from qgis.PyQt.QtWidgets import QFileDialog
        
        clip_name = self.clips_list.currentItem().text().replace("🖼️ ", "")
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Clip",
            f"{clip_name}.tif",
            "GeoTiff (*.tif *.tiff);;All Files (*)"
        )
        
        if file_path:
            try:
                import shutil
                source_path = clip_data.get('layer_path')
                if source_path:
                    shutil.copy2(source_path, file_path)
                    logger.info(f"Exported clip to: {file_path}")
                    from qgis.utils import iface
                    iface.messageBar().pushSuccess("FilterMate", f"Clip exported to {file_path}")
            except Exception as e:
                logger.error(f"Failed to export clip: {e}")
    
    def _on_clear_all_clips(self):
        """Clear all memory clips."""
        from qgis.PyQt.QtWidgets import QMessageBox
        
        result = QMessageBox.question(
            self,
            "Clear All Clips",
            f"Delete all {self.clips_list.count()} memory clips?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if result == QMessageBox.Yes:
            # Delete all clip files
            for i in range(self.clips_list.count()):
                item = self.clips_list.item(i)
                clip_data = item.data(Qt.UserRole)
                layer_path = clip_data.get('layer_path')
                if layer_path:
                    try:
                        import os
                        if os.path.exists(layer_path):
                            os.remove(layer_path)
                    except Exception:
                        pass
            
            self.clips_list.clear()
            self.clips_group.setTitle("💾 Memory Clips (0)")
            self._update_clip_actions_state()
            logger.info("Cleared all memory clips")
    
    # === ZONAL STATISTICS METHODS ===
    
    def set_zonal_stats(self, stats: dict, source_info: str = ""):
        """Set the zonal statistics results.
        
        Args:
            stats: Dictionary of statistic name -> value
            source_info: Optional info about the computation source
        """
        self.zonal_table.setRowCount(0)
        
        for stat_name, stat_value in stats.items():
            row = self.zonal_table.rowCount()
            self.zonal_table.insertRow(row)
            
            # Stat name
            name_item = QTableWidgetItem(stat_name)
            self.zonal_table.setItem(row, 0, name_item)
            
            # Stat value (formatted)
            if isinstance(stat_value, float):
                value_str = f"{stat_value:.4f}"
            else:
                value_str = str(stat_value)
            value_item = QTableWidgetItem(value_str)
            self.zonal_table.setItem(row, 1, value_item)
        
        # Update UI
        self.zonal_group.setCollapsed(False)
        self.zonal_group.setTitle(f"📊 Zonal Statistics ({len(stats)} stats)")
        
        if source_info:
            self.zonal_info_label.setText(source_info)
        else:
            from datetime import datetime
            now = datetime.now().strftime("%H:%M:%S")
            self.zonal_info_label.setText(f"Computed at {now}")
        
        self._zonal_stats_data = stats
    
    def _on_copy_zonal_stats(self):
        """Copy zonal statistics to clipboard."""
        if not hasattr(self, '_zonal_stats_data') or not self._zonal_stats_data:
            return
        
        from qgis.PyQt.QtWidgets import QApplication
        
        lines = ["Statistic\tValue"]
        for stat_name, stat_value in self._zonal_stats_data.items():
            if isinstance(stat_value, float):
                value_str = f"{stat_value:.4f}"
            else:
                value_str = str(stat_value)
            lines.append(f"{stat_name}\t{value_str}")
        
        text = "\n".join(lines)
        QApplication.clipboard().setText(text)
        
        from qgis.utils import iface
        iface.messageBar().pushSuccess("FilterMate", "Zonal statistics copied to clipboard")
    
    def _on_export_zonal_stats(self):
        """Export zonal statistics to CSV file."""
        if not hasattr(self, '_zonal_stats_data') or not self._zonal_stats_data:
            return
        
        from qgis.PyQt.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Zonal Statistics",
            "zonal_stats.csv",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            try:
                import csv
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Statistic", "Value"])
                    for stat_name, stat_value in self._zonal_stats_data.items():
                        writer.writerow([stat_name, stat_value])
                
                from qgis.utils import iface
                iface.messageBar().pushSuccess("FilterMate", f"Statistics exported to {file_path}")
            except Exception as e:
                logger.error(f"Failed to export zonal stats: {e}")
    
    def _on_add_stats_to_layer(self):
        """Add zonal statistics as attributes to source vector layer."""
        # This would require the source vector layer reference
        # For now, just show info
        from qgis.utils import iface
        iface.messageBar().pushInfo(
            "FilterMate", 
            "Feature coming soon: Add stats as layer attributes"
        )


class ExploringToolBox(BaseToolBox):
    """QToolBox for EXPLORING functionality.
    
    Contains two pages:
    - Page 1: Vector Exploring
    - Page 2: Raster Exploring
    
    Auto-switches between pages based on current layer type.
    
    Signals:
        vectorSelectionChanged: Emitted when vector selection changes
        rasterRangeChanged: Emitted when raster range changes
        layerTypeChanged: Emitted when current layer type changes (vector/raster)
    """
    
    vectorSelectionChanged = pyqtSignal(str, object)  # field, value
    rasterRangeChanged = pyqtSignal(float, float)  # min, max
    layerTypeChanged = pyqtSignal(str)  # 'vector' or 'raster'
    filterRequested = pyqtSignal()
    clearRequested = pyqtSignal()
    
    # Page name constants
    PAGE_VECTOR = "📍 EXPLORING VECTOR"
    PAGE_RASTER = "🏔️ EXPLORING RASTER"
    
    def __init__(self, parent=None):
        super().__init__(parent, title="EXPLORING")
        self._current_layer = None
        self._current_layer_type = None  # 'vector' or 'raster'
        self._programmatic_change = False  # Flag to allow programmatic page changes
        self._setup_pages()
        self._connect_page_signals()
    
    def setCurrentIndex(self, index: int):
        """Override to prevent manual page changes by user.
        
        Page changes are ONLY allowed programmatically when layer type changes.
        User clicks on tabs are ignored to ensure sync with current layer type.
        
        Args:
            index: The index to switch to
        """
        if self._programmatic_change:
            # Allow programmatic changes (from set_current_layer)
            super().setCurrentIndex(index)
        else:
            # Block user-initiated changes - log for debugging
            logger.debug(f"ExploringToolBox: Blocked manual page change to index {index}. "
                        f"Page is synced to current layer type ('{self._current_layer_type}').")
    
    def _activate_page_internal(self, name: str) -> bool:
        """Internal method to activate a page programmatically.
        
        This bypasses the user-change protection.
        
        Args:
            name: Page name to activate
            
        Returns:
            True if page was activated, False if not found
        """
        index = self.get_page_index(name)
        if index >= 0:
            self._programmatic_change = True
            try:
                super().setCurrentIndex(index)
            finally:
                self._programmatic_change = False
            return True
        logger.warning(f"Page '{name}' not found in EXPLORING")
        return False
    
    def _setup_pages(self):
        """Setup the two exploring pages."""
        # Vector page
        self._vector_page = VectorExploringPage()
        self.add_page(
            self.PAGE_VECTOR, 
            self._vector_page,
            tooltip="Explore vector layers with field-based selection"
        )
        
        # Raster page
        self._raster_page = RasterExploringPage()
        self.add_page(
            self.PAGE_RASTER,
            self._raster_page,
            tooltip="Explore raster layers with value range selection"
        )
        
        # Start with vector page (use internal method to bypass protection)
        self._activate_page_internal(self.PAGE_VECTOR)
    
    def _connect_page_signals(self):
        """Connect page signals to toolbox signals."""
        # Vector page signals
        self._vector_page.selectionChanged.connect(self.vectorSelectionChanged)
        self._vector_page.filterRequested.connect(self.filterRequested)
        self._vector_page.clearRequested.connect(self.clearRequested)
        
        # Raster page signals
        self._raster_page.rangeChanged.connect(self.rasterRangeChanged)
    
    def set_current_layer(self, layer):
        """Set the current layer and ALWAYS switch page to match layer type.
        
        The page is always synchronized with the current layer type.
        User cannot manually switch between Vector/Raster pages.
        
        Args:
            layer: QgsVectorLayer or QgsRasterLayer
        """
        self._current_layer = layer
        
        if layer is None:
            return
        
        # Determine layer type and ALWAYS switch page to match
        if isinstance(layer, QgsVectorLayer):
            new_type = 'vector'
            self._vector_page.set_layer(layer)
            # Always sync page to layer type (use internal method)
            self._activate_page_internal(self.PAGE_VECTOR)
        elif isinstance(layer, QgsRasterLayer):
            new_type = 'raster'
            self._raster_page.set_layer(layer)
            # Always sync page to layer type (use internal method)
            self._activate_page_internal(self.PAGE_RASTER)
        else:
            logger.warning(f"Unknown layer type: {type(layer)}")
            return
        
        # Emit type change signal if changed
        if new_type != self._current_layer_type:
            self._current_layer_type = new_type
            self.layerTypeChanged.emit(new_type)
            logger.debug(f"ExploringToolBox: Layer type changed to '{new_type}'")
    
    def get_vector_page(self) -> VectorExploringPage:
        """Get the vector exploring page widget."""
        return self._vector_page
    
    def get_raster_page(self) -> RasterExploringPage:
        """Get the raster exploring page widget."""
        return self._raster_page
    
    def get_page_by_name(self, name: str):
        """Get page widget by name.
        
        Args:
            name: 'vector' or 'raster'
            
        Returns:
            Page widget or None
        """
        if name.lower() == 'vector':
            return self._vector_page
        elif name.lower() == 'raster':
            return self._raster_page
        return None
    
    def get_current_layer_type(self) -> str:
        """Get the current layer type.
        
        Returns:
            'vector', 'raster', or None
        """
        return self._current_layer_type
    
    def update_vector_result(self, selected: int, total: int):
        """Update the vector selection result indicator.
        
        Args:
            selected: Number of selected features
            total: Total features
        """
        self._vector_page.update_result(selected, total)
    
    def get_vector_filter(self) -> dict:
        """Get current vector filter parameters."""
        return self._vector_page.get_current_filter()
    
    def get_raster_range(self) -> tuple:
        """Get current raster value range."""
        return self._raster_page.get_current_range()
    
    def get_raster_predicate(self) -> str:
        """Get current raster predicate."""
        return self._raster_page.get_predicate()

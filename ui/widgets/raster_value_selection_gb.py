# -*- coding: utf-8 -*-
"""
FilterMate Raster Value Selection GroupBox Widget.

EPIC-3: Raster-Vector Integration
GroupBox 2: 📈 VALUE SELECTION

Provides interactive histogram-based value selection with a 
"Pick from Map" pipette tool for capturing pixel values from canvas.

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional, Dict, TYPE_CHECKING

from qgis.PyQt.QtCore import Qt, pyqtSignal, QTimer
from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QSizePolicy,
    QComboBox,
    QPushButton,
    QDoubleSpinBox,
    QGroupBox,
)
from qgis.PyQt.QtGui import QFont, QCursor

# Try to import QgsCollapsibleGroupBox
try:
    from qgis.gui import QgsCollapsibleGroupBox
    QGIS_GUI_AVAILABLE = True
except ImportError:
    from qgis.PyQt.QtWidgets import QGroupBox as QgsCollapsibleGroupBox
    QGIS_GUI_AVAILABLE = False

from .histogram_widget import HistogramCanvas

if TYPE_CHECKING:
    from qgis.core import QgsRasterLayer
    from core.ports.raster_port import HistogramData
    from core.services.raster_stats_service import RasterStatsService

logger = logging.getLogger('FilterMate.UI.RasterValueSelectionGB')


# Predicate options for value filtering
VALUE_PREDICATES = [
    ("within_range", "Within Range", "min ≤ value ≤ max"),
    ("outside_range", "Outside Range", "value < min OR value > max"),
    ("above_value", "Above Value", "value > min"),
    ("below_value", "Below Value", "value < max"),
    ("equals_value", "Equals Value", "value = min (uses min only)"),
    ("is_nodata", "Is NoData", "value = NoData"),
    ("is_not_nodata", "Is NOT NoData", "value ≠ NoData"),
]


class RasterValueSelectionGroupBox(QWidget):
    """
    Collapsible GroupBox for raster value selection.
    
    EPIC-3: GroupBox 2 - 📈 VALUE SELECTION
    
    Features:
    - Band selector for multi-band rasters
    - Interactive histogram with drag selection
    - Min/Max spinboxes for range input
    - Predicate selector (within range, outside, etc.)
    - Pick from Map (pipette) tool for value capture
    - Pixel count display for selected range
    - Preview Map button
    
    Signals:
        collapsed_changed: Emitted when collapse state changes
        activated: Emitted when this GroupBox becomes active (expanded)
        band_changed: Emitted when selected band changes
        range_changed: Emitted when value range changes
        predicate_changed: Emitted when predicate changes
        pick_mode_activated: Emitted when pipette mode is toggled
        pixel_value_picked: Emitted when a single pixel value is picked
        pixel_range_picked: Emitted when a range of values is picked
        preview_requested: Emitted when preview is requested
    """
    
    # Signals
    collapsed_changed = pyqtSignal(bool)  # is_collapsed
    activated = pyqtSignal()  # This GroupBox became active
    band_changed = pyqtSignal(int)  # band_number
    range_changed = pyqtSignal(float, float)  # min, max
    predicate_changed = pyqtSignal(str)  # predicate key
    pick_mode_activated = pyqtSignal(bool)  # is_active
    pixel_value_picked = pyqtSignal(float)  # single value
    pixel_range_picked = pyqtSignal(float, float)  # min, max from selection
    preview_requested = pyqtSignal()
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the value selection GroupBox.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._layer: Optional['QgsRasterLayer'] = None
        self._layer_id: Optional[str] = None
        self._stats_service: Optional['RasterStatsService'] = None
        self._current_band: int = 1
        self._data_min: float = 0.0
        self._data_max: float = 100.0
        self._pixel_count: int = 0
        self._total_pixels: int = 0
        self._pick_mode_active: bool = False
        
        # Debounce timer for spinbox changes
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(150)  # 150ms debounce
        self._update_timer.timeout.connect(self._emit_range_changed)
        
        self._setup_ui()
        self._setup_connections()
    
    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # === Collapsible GroupBox ===
        self._groupbox = QgsCollapsibleGroupBox(self)
        self._groupbox.setTitle("📈 VALUE SELECTION")
        self._groupbox.setCheckable(False)
        self._groupbox.setCollapsed(True)
        
        # Style
        font = QFont()
        font.setFamily("Segoe UI")
        font.setPointSize(9)
        font.setBold(True)
        self._groupbox.setFont(font)
        self._groupbox.setCursor(QCursor(Qt.PointingHandCursor))
        
        # Size policy
        self._groupbox.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )
        
        # Content widget
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(8)
        
        # === Band Selector ===
        band_layout = QHBoxLayout()
        band_layout.setSpacing(8)
        
        band_label = QLabel("Band:")
        band_label.setStyleSheet("font-weight: normal; font-size: 9pt;")
        band_layout.addWidget(band_label)
        
        self._band_combo = QComboBox()
        self._band_combo.setObjectName("combo_value_band")
        self._band_combo.setMinimumHeight(24)
        self._band_combo.addItem("Band 1")
        band_layout.addWidget(self._band_combo, 1)
        
        content_layout.addLayout(band_layout)
        
        # === Histogram ===
        self._histogram_frame = QFrame()
        self._histogram_frame.setFrameStyle(QFrame.StyledPanel)
        self._histogram_frame.setStyleSheet("""
            QFrame {
                background-color: palette(base);
                border: 1px solid palette(mid);
                border-radius: 4px;
            }
        """)
        
        hist_layout = QVBoxLayout(self._histogram_frame)
        hist_layout.setContentsMargins(4, 4, 4, 4)
        
        self._histogram_canvas = HistogramCanvas()
        self._histogram_canvas.setMinimumHeight(120)
        hist_layout.addWidget(self._histogram_canvas)
        
        content_layout.addWidget(self._histogram_frame)
        
        # === Range Controls ===
        range_frame = QFrame()
        range_frame.setFrameStyle(QFrame.StyledPanel)
        range_frame.setStyleSheet("""
            QFrame {
                background-color: palette(alternate-base);
                border-radius: 4px;
            }
        """)
        
        range_layout = QHBoxLayout(range_frame)
        range_layout.setContentsMargins(8, 6, 8, 6)
        range_layout.setSpacing(8)
        
        # Range label
        range_label = QLabel("Range:")
        range_label.setStyleSheet("font-weight: normal;")
        range_layout.addWidget(range_label)
        
        # Min spinbox
        self._min_spin = QDoubleSpinBox()
        self._min_spin.setObjectName("spin_range_min")
        self._min_spin.setDecimals(2)
        self._min_spin.setRange(-1e10, 1e10)
        self._min_spin.setMinimumWidth(80)
        self._min_spin.setToolTip("Minimum value of selection range")
        range_layout.addWidget(self._min_spin)
        
        # Arrow
        arrow_label = QLabel("←──→")
        arrow_label.setStyleSheet("color: palette(mid);")
        range_layout.addWidget(arrow_label)
        
        # Max spinbox
        self._max_spin = QDoubleSpinBox()
        self._max_spin.setObjectName("spin_range_max")
        self._max_spin.setDecimals(2)
        self._max_spin.setRange(-1e10, 1e10)
        self._max_spin.setMinimumWidth(80)
        self._max_spin.setToolTip("Maximum value of selection range")
        range_layout.addWidget(self._max_spin)
        
        range_layout.addStretch()
        
        # Pixel count
        self._pixel_label = QLabel("Pixels: —")
        self._pixel_label.setObjectName("label_pixel_count")
        self._pixel_label.setStyleSheet("font-family: monospace; color: palette(mid);")
        range_layout.addWidget(self._pixel_label)
        
        content_layout.addWidget(range_frame)
        
        # === Pick from Map (Pipette) ===
        pick_frame = QFrame()
        pick_frame.setFrameStyle(QFrame.StyledPanel)
        pick_frame.setStyleSheet("""
            QFrame {
                background-color: palette(alternate-base);
                border-radius: 4px;
            }
        """)
        
        pick_layout = QHBoxLayout(pick_frame)
        pick_layout.setContentsMargins(8, 6, 8, 6)
        pick_layout.setSpacing(8)
        
        self._pick_btn = QPushButton("🔬 Pick from Map")
        self._pick_btn.setObjectName("btn_pick_from_map")
        self._pick_btn.setCheckable(True)
        self._pick_btn.setToolTip(
            "Capture pixel values from canvas\n"
            "• Click: single value\n"
            "• Drag: value range\n"
            "• Ctrl+Click: add to selection"
        )
        self._pick_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border: 1px solid palette(mid);
                border-radius: 4px;
                background: palette(button);
                font-weight: bold;
            }
            QPushButton:hover {
                background: palette(light);
                border-color: palette(highlight);
            }
            QPushButton:checked {
                background: #3498db;
                color: white;
                border-color: #2980b9;
            }
            QPushButton:checked:hover {
                background: #2980b9;
            }
        """)
        pick_layout.addWidget(self._pick_btn)
        
        pick_desc = QLabel("Capture pixel values from canvas")
        pick_desc.setStyleSheet("color: palette(mid); font-size: 8pt;")
        pick_layout.addWidget(pick_desc, 1)
        
        content_layout.addWidget(pick_frame)
        
        # === Predicate Selector ===
        pred_layout = QHBoxLayout()
        pred_layout.setSpacing(8)
        
        pred_label = QLabel("Predicate:")
        pred_label.setStyleSheet("font-weight: normal; font-size: 9pt;")
        pred_layout.addWidget(pred_label)
        
        self._predicate_combo = QComboBox()
        self._predicate_combo.setObjectName("combo_predicate")
        self._predicate_combo.setMinimumHeight(24)
        
        for key, name, tooltip in VALUE_PREDICATES:
            self._predicate_combo.addItem(name, key)
            idx = self._predicate_combo.count() - 1
            self._predicate_combo.setItemData(
                idx, tooltip, Qt.ToolTipRole
            )
        
        pred_layout.addWidget(self._predicate_combo, 1)
        
        content_layout.addLayout(pred_layout)
        
        # === Action Buttons ===
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.addStretch()
        
        # Preview button
        self._preview_btn = QPushButton("👁️ Preview Map")
        self._preview_btn.setObjectName("btn_preview_map")
        self._preview_btn.setToolTip("Preview selection on map")
        self._preview_btn.setStyleSheet("""
            QPushButton {
                padding: 4px 12px;
                border: 1px solid palette(mid);
                border-radius: 4px;
                background: palette(button);
            }
            QPushButton:hover {
                background: palette(light);
                border-color: palette(highlight);
            }
            QPushButton:disabled {
                color: palette(mid);
            }
        """)
        btn_layout.addWidget(self._preview_btn)
        
        content_layout.addLayout(btn_layout)
        
        # Set content to groupbox
        self._groupbox.setLayout(QVBoxLayout())
        self._groupbox.layout().setContentsMargins(0, 0, 0, 0)
        self._groupbox.layout().addWidget(content)
        
        main_layout.addWidget(self._groupbox)
    
    def _setup_connections(self) -> None:
        """Set up signal connections."""
        # GroupBox collapse
        if hasattr(self._groupbox, 'collapsedStateChanged'):
            self._groupbox.collapsedStateChanged.connect(
                self._on_collapse_changed
            )
        
        # Band combo
        self._band_combo.currentIndexChanged.connect(
            self._on_band_changed
        )
        
        # Spinboxes
        self._min_spin.valueChanged.connect(self._on_spinbox_changed)
        self._max_spin.valueChanged.connect(self._on_spinbox_changed)
        
        # Histogram
        self._histogram_canvas.range_changed.connect(
            self._on_histogram_range_changed
        )
        
        # Pick button
        self._pick_btn.toggled.connect(self._on_pick_toggled)
        
        # Predicate
        self._predicate_combo.currentIndexChanged.connect(
            self._on_predicate_changed
        )
        
        # Preview
        self._preview_btn.clicked.connect(self._on_preview_clicked)
    
    def _on_collapse_changed(self, collapsed: bool) -> None:
        """Handle collapse state change."""
        self.collapsed_changed.emit(collapsed)
        
        if not collapsed:
            # GroupBox expanded = activated
            self.activated.emit()
            logger.debug("Value Selection GroupBox activated")
    
    def _on_band_changed(self, index: int) -> None:
        """Handle band selection change."""
        band_number = index + 1
        self._current_band = band_number
        self.band_changed.emit(band_number)
        
        # Reload histogram for new band
        self._load_histogram()
    
    def _on_spinbox_changed(self) -> None:
        """Handle spinbox value change (debounced)."""
        # Update histogram selection
        self._histogram_canvas.set_selection_range(
            self._min_spin.value(),
            self._max_spin.value()
        )
        
        # Debounce the signal emission
        self._update_timer.stop()
        self._update_timer.start()
    
    def _emit_range_changed(self) -> None:
        """Emit the range_changed signal after debounce."""
        self.range_changed.emit(
            self._min_spin.value(),
            self._max_spin.value()
        )
        self._update_pixel_count()
    
    def _on_histogram_range_changed(self, min_val: float, max_val: float) -> None:
        """Handle histogram selection change."""
        # Update spinboxes without retriggering
        self._min_spin.blockSignals(True)
        self._max_spin.blockSignals(True)
        
        self._min_spin.setValue(min_val)
        self._max_spin.setValue(max_val)
        
        self._min_spin.blockSignals(False)
        self._max_spin.blockSignals(False)
        
        # Emit range changed
        self.range_changed.emit(min_val, max_val)
        self._update_pixel_count()
    
    def _on_pick_toggled(self, checked: bool) -> None:
        """Handle pick from map button toggle."""
        self._pick_mode_active = checked
        self.pick_mode_activated.emit(checked)
        
        if checked:
            logger.debug("Pick from Map mode ACTIVATED")
        else:
            logger.debug("Pick from Map mode DEACTIVATED")
    
    def _on_predicate_changed(self, index: int) -> None:
        """Handle predicate selection change."""
        predicate_key = self._predicate_combo.currentData()
        self.predicate_changed.emit(predicate_key)
        self._update_pixel_count()
    
    def _on_preview_clicked(self) -> None:
        """Handle preview button click."""
        self.preview_requested.emit()
    
    def _update_pixel_count(self) -> None:
        """Update the pixel count display."""
        # TODO: Calculate actual pixel count from histogram data
        # For now, show placeholder
        if self._total_pixels > 0:
            pct = (self._pixel_count / self._total_pixels) * 100
            self._pixel_label.setText(
                f"Pixels: {self._pixel_count:,} ({pct:.1f}%)"
            )
        else:
            self._pixel_label.setText("Pixels: —")
    
    def set_layer(self, layer: Optional['QgsRasterLayer']) -> None:
        """
        Set the raster layer for value selection.
        
        Args:
            layer: QgsRasterLayer or None to clear
        """
        self._layer = layer
        self._layer_id = layer.id() if layer else None
        
        if layer is not None:
            self._populate_band_combo(layer)
            self._load_histogram()
        else:
            self.clear()
    
    def _populate_band_combo(self, layer: 'QgsRasterLayer') -> None:
        """Populate band combo from layer."""
        self._band_combo.blockSignals(True)
        self._band_combo.clear()
        
        band_count = layer.bandCount()
        for i in range(1, band_count + 1):
            band_name = layer.bandName(i)
            if band_name:
                self._band_combo.addItem(f"Band {i} - {band_name}")
            else:
                self._band_combo.addItem(f"Band {i}")
        
        self._band_combo.blockSignals(False)
        self._current_band = 1
    
    def _load_histogram(self) -> None:
        """Load histogram data for current band."""
        if not self._stats_service or not self._layer_id:
            return
        
        try:
            hist_data = self._stats_service.get_histogram(
                self._layer_id, self._current_band
            )
            if hist_data:
                self._histogram_canvas.set_histogram_data(hist_data)
                
                # Update data range
                self._data_min = hist_data.bin_edges[0]
                self._data_max = hist_data.bin_edges[-1]
                
                # Update spinbox ranges
                self._min_spin.setRange(self._data_min, self._data_max)
                self._max_spin.setRange(self._data_min, self._data_max)
                self._min_spin.setValue(self._data_min)
                self._max_spin.setValue(self._data_max)
                
                # Update total pixels
                self._total_pixels = sum(hist_data.counts)
                self._pixel_count = self._total_pixels
                self._update_pixel_count()
        except Exception as e:
            logger.error(f"Failed to load histogram: {e}")
    
    def clear(self) -> None:
        """Clear all data and reset to default state."""
        self._layer = None
        self._layer_id = None
        
        self._band_combo.clear()
        self._band_combo.addItem("Band 1")
        
        self._histogram_canvas.clear()
        
        self._min_spin.setValue(0)
        self._max_spin.setValue(100)
        self._pixel_label.setText("Pixels: —")
        
        # Deactivate pick mode
        if self._pick_mode_active:
            self._pick_btn.setChecked(False)
    
    def set_stats_service(self, service: 'RasterStatsService') -> None:
        """
        Set the RasterStatsService for histogram data.
        
        Args:
            service: RasterStatsService instance
        """
        self._stats_service = service
    
    def set_collapsed(self, collapsed: bool) -> None:
        """Programmatically set the collapsed state."""
        self._groupbox.setCollapsed(collapsed)
    
    def is_collapsed(self) -> bool:
        """Check if the GroupBox is collapsed."""
        return self._groupbox.isCollapsed()
    
    def expand(self) -> None:
        """Expand the GroupBox."""
        self.set_collapsed(False)
    
    def collapse(self) -> None:
        """Collapse the GroupBox."""
        self.set_collapsed(True)
    
    def set_range(self, min_val: float, max_val: float) -> None:
        """
        Set the selection range programmatically.
        
        Args:
            min_val: Minimum value
            max_val: Maximum value
        """
        self._min_spin.setValue(min_val)
        self._max_spin.setValue(max_val)
        self._histogram_canvas.set_selection_range(min_val, max_val)
    
    def receive_picked_value(self, value: float) -> None:
        """
        Receive a picked pixel value from the map tool.
        
        This method should be called by the PixelPickerMapTool when
        a single pixel value is captured.
        
        Args:
            value: The picked pixel value
        """
        # Set range to single value
        self.set_range(value, value)
        self.pixel_value_picked.emit(value)
        logger.debug(f"Received picked value: {value}")
    
    def receive_picked_range(self, min_val: float, max_val: float) -> None:
        """
        Receive a picked range from the map tool.
        
        This method should be called by the PixelPickerMapTool when
        a range of values is captured via rectangle selection.
        
        Args:
            min_val: Minimum value in the selection
            max_val: Maximum value in the selection
        """
        self.set_range(min_val, max_val)
        self.pixel_range_picked.emit(min_val, max_val)
        logger.debug(f"Received picked range: [{min_val}, {max_val}]")
    
    def extend_range(self, value: float) -> None:
        """
        Extend the current range to include a new value.
        
        Used for Ctrl+Click to add to selection.
        
        Args:
            value: The value to include in the range
        """
        current_min = self._min_spin.value()
        current_max = self._max_spin.value()
        
        new_min = min(current_min, value)
        new_max = max(current_max, value)
        
        self.set_range(new_min, new_max)
        logger.debug(f"Range extended to [{new_min}, {new_max}]")
    
    def deactivate_pick_mode(self) -> None:
        """Deactivate the pick from map mode."""
        if self._pick_btn.isChecked():
            self._pick_btn.setChecked(False)
    
    def is_pick_mode_active(self) -> bool:
        """Check if pick mode is currently active."""
        return self._pick_mode_active
    
    def get_filter_context(self) -> Dict:
        """
        Get the current filter context for FILTERING synchronization.
        
        Returns:
            dict: Filter context with source info and selection
        """
        if self._layer is None:
            return {}
        
        predicate_key = self._predicate_combo.currentData() or "within_range"
        
        return {
            'source_type': 'raster',
            'mode': 'value_filter',
            'layer_id': self._layer_id,
            'layer_name': self._layer.name() if self._layer else None,
            'band': self._current_band,
            'band_name': self._band_combo.currentText(),
            'range_min': self._min_spin.value(),
            'range_max': self._max_spin.value(),
            'predicate': predicate_key,
            'pixel_count': self._pixel_count,
            'pixel_percentage': (
                (self._pixel_count / self._total_pixels * 100)
                if self._total_pixels > 0 else 0
            ),
        }
    
    @property
    def layer(self) -> Optional['QgsRasterLayer']:
        """Get the current raster layer."""
        return self._layer
    
    @property
    def current_band(self) -> int:
        """Get the currently selected band number."""
        return self._current_band
    
    @property
    def current_range(self) -> tuple:
        """Get the current selection range as (min, max) tuple."""
        return (self._min_spin.value(), self._max_spin.value())
    
    @property
    def current_predicate(self) -> str:
        """Get the current predicate key."""
        return self._predicate_combo.currentData() or "within_range"

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
    QStackedWidget,
    QProgressBar,
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

# EPIC-3: Target layer selection widget
try:
    from .raster_target_layer_widget import RasterTargetLayerWidget
    RASTER_TARGET_WIDGET_AVAILABLE = True
except ImportError:
    RasterTargetLayerWidget = None
    RASTER_TARGET_WIDGET_AVAILABLE = False

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
    - Target layer selection widget
    - Execute filter button
    
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
        filter_context_changed: Current filter context (dict)
        execute_filter: User clicked execute filter button
        targets_changed: Target layers selection changed (list)
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
    # EPIC-3: Additional signals for filter execution
    filter_context_changed = pyqtSignal(dict)  # context dict
    execute_filter = pyqtSignal()  # execute requested
    targets_changed = pyqtSignal(list)  # list of target configs
    # EPIC-3: Workflow template signals
    save_as_template_requested = pyqtSignal()  # save current config as template
    load_template_requested = pyqtSignal()  # load and apply a template
    clear_filters = pyqtSignal(list)  # EPIC-3: Clear filters for layer IDs
    zonal_stats_requested = pyqtSignal(list)  # EPIC-3: Zonal stats for layer IDs
    
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
        self._histogram_data: Optional['HistogramData'] = None  # Store histogram for pixel count
        
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
        
        # Stacked widget for histogram/loading switch
        self._histogram_stack = QStackedWidget()
        
        # Page 0: Histogram canvas
        self._histogram_canvas = HistogramCanvas()
        self._histogram_canvas.setMinimumHeight(120)
        self._histogram_stack.addWidget(self._histogram_canvas)
        
        # Page 1: Loading indicator
        loading_widget = QWidget()
        loading_layout = QVBoxLayout(loading_widget)
        loading_layout.setAlignment(Qt.AlignCenter)
        
        self._loading_label = QLabel("⏳ Loading histogram...")
        self._loading_label.setStyleSheet("""
            QLabel {
                color: palette(mid);
                font-style: italic;
                font-size: 10pt;
            }
        """)
        self._loading_label.setAlignment(Qt.AlignCenter)
        loading_layout.addWidget(self._loading_label)
        
        self._loading_progress = QProgressBar()
        self._loading_progress.setRange(0, 0)  # Indeterminate mode
        self._loading_progress.setMaximumWidth(200)
        self._loading_progress.setTextVisible(False)
        self._loading_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid palette(mid);
                border-radius: 4px;
                background: palette(base);
                height: 8px;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3498db, stop:1 #2ecc71
                );
                border-radius: 3px;
            }
        """)
        loading_layout.addWidget(self._loading_progress, 0, Qt.AlignCenter)
        
        loading_widget.setMinimumHeight(120)
        self._histogram_stack.addWidget(loading_widget)
        
        hist_layout.addWidget(self._histogram_stack)
        
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
        
        # Pixel count with visual indicator
        pixel_frame = QFrame()
        pixel_frame.setStyleSheet("""
            QFrame {
                background: transparent;
            }
        """)
        pixel_layout = QHBoxLayout(pixel_frame)
        pixel_layout.setContentsMargins(0, 0, 0, 0)
        pixel_layout.setSpacing(4)
        
        self._pixel_label = QLabel("Pixels: —")
        self._pixel_label.setObjectName("label_pixel_count")
        self._pixel_label.setStyleSheet("font-family: monospace; font-weight: bold;")
        pixel_layout.addWidget(self._pixel_label)
        
        # Percentage bar indicator
        self._pct_bar = QLabel()
        self._pct_bar.setFixedSize(50, 8)
        self._pct_bar.setStyleSheet("""
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 #3498db, stop:1 #ecf0f1
            );
            border-radius: 4px;
        """)
        self._pct_bar.setToolTip("Percentage of selected pixels")
        pixel_layout.addWidget(self._pct_bar)
        
        range_layout.addWidget(pixel_frame)
        
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
        
        # === EPIC-3: Target Layer Selection ===
        self._target_widget = None
        if RASTER_TARGET_WIDGET_AVAILABLE:
            self._target_widget = RasterTargetLayerWidget(content)
            self._target_widget.setObjectName("target_layer_widget")
            content_layout.addWidget(self._target_widget)
        
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
        
        # Save as template button
        self._save_template_btn = QPushButton("📋 Save Template")
        self._save_template_btn.setObjectName("btn_save_template")
        self._save_template_btn.setToolTip("Save current configuration as reusable template")
        self._save_template_btn.setStyleSheet("""
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
        """)
        btn_layout.addWidget(self._save_template_btn)
        
        # Load template button
        self._load_template_btn = QPushButton("📂 Load Template")
        self._load_template_btn.setObjectName("btn_load_template")
        self._load_template_btn.setToolTip("Load and apply a saved workflow template")
        self._load_template_btn.setStyleSheet("""
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
        """)
        btn_layout.addWidget(self._load_template_btn)
        
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
        
        # EPIC-3: Save/Load templates
        self._save_template_btn.clicked.connect(self._on_save_template_clicked)
        self._load_template_btn.clicked.connect(self._on_load_template_clicked)
        
        # EPIC-3: Target layer widget
        if self._target_widget:
            self._target_widget.targets_changed.connect(self._on_targets_changed)
            self._target_widget.execute_requested.connect(self._on_execute_requested)
            self._target_widget.clear_filters_requested.connect(self._on_clear_filters_requested)
            self._target_widget.zonal_stats_requested.connect(self._on_zonal_stats_requested)
    
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
        
        # Update pixel count immediately for better UX
        self._update_pixel_count()
        
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
    
    def _on_save_template_clicked(self) -> None:
        """Handle save as template button click."""
        self.save_as_template_requested.emit()
    
    def _on_load_template_clicked(self) -> None:
        """Handle load template button click."""
        self.load_template_requested.emit()
    
    def _update_pixel_count(self) -> None:
        """
        Update the pixel count display based on histogram data and current selection.
        
        Calculates the number of pixels within the selected value range using
        histogram bin data. Handles predicates like within_range, outside_range, etc.
        """
        # Check if we have histogram data
        if not hasattr(self, '_histogram_data') or self._histogram_data is None:
            self._pixel_label.setText("Pixels: —")
            return
        
        histogram_data = self._histogram_data
        if not histogram_data.counts or not histogram_data.bin_edges:
            self._pixel_label.setText("Pixels: —")
            return
        
        # Get current range and predicate
        range_min = self._min_spin.value()
        range_max = self._max_spin.value()
        predicate = self._predicate_combo.currentData() or "within_range"
        
        # Calculate pixel count based on predicate
        selected_count = self._calculate_pixel_count_for_predicate(
            histogram_data, range_min, range_max, predicate
        )
        
        self._pixel_count = selected_count
        self._total_pixels = histogram_data.total_count
        
        if self._total_pixels > 0:
            pct = (self._pixel_count / self._total_pixels) * 100
            self._pixel_label.setText(
                f"Pixels: {self._pixel_count:,} ({pct:.1f}%)"
            )
            
            # Update percentage bar with gradient color
            # Color: green (0%) -> blue (50%) -> orange (100%)
            self._update_percentage_bar(pct)
        else:
            self._pixel_label.setText("Pixels: —")
            self._update_percentage_bar(0)
    
    def _update_percentage_bar(self, percentage: float) -> None:
        """
        Update the percentage bar visual indicator.
        
        Args:
            percentage: Percentage value (0-100)
        """
        if not hasattr(self, '_pct_bar'):
            return
        
        # Clamp percentage
        pct = max(0, min(100, percentage))
        
        # Determine color based on percentage
        # Low selection (0-30%): Blue
        # Medium selection (30-70%): Green
        # High selection (70-100%): Orange
        if pct < 30:
            color = "#3498db"  # Blue
        elif pct < 70:
            color = "#27ae60"  # Green
        else:
            color = "#e67e22"  # Orange
        
        # Calculate fill width (50px * percentage / 100)
        fill_width = int(50 * pct / 100)
        
        self._pct_bar.setStyleSheet(f"""
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 {color},
                stop:{pct/100:.2f} {color},
                stop:{pct/100 + 0.01:.2f} palette(mid),
                stop:1 palette(mid)
            );
            border-radius: 4px;
            border: 1px solid palette(mid);
        """)
    
    def _calculate_pixel_count_for_predicate(
        self,
        histogram_data: 'HistogramData',
        range_min: float,
        range_max: float,
        predicate: str
    ) -> int:
        """
        Calculate pixel count based on predicate type.
        
        Args:
            histogram_data: Histogram data with counts and bin_edges
            range_min: Minimum value of selection
            range_max: Maximum value of selection
            predicate: Predicate type (within_range, outside_range, etc.)
        
        Returns:
            Number of pixels matching the predicate
        """
        counts = histogram_data.counts
        bin_edges = histogram_data.bin_edges
        total_count = histogram_data.total_count
        
        if predicate == "is_nodata":
            # NoData count would require stats - use 0 as placeholder
            return 0
        
        if predicate == "is_not_nodata":
            # All non-NoData pixels
            return total_count
        
        # Calculate pixels within range
        within_range_count = 0
        for i, count in enumerate(counts):
            if i + 1 >= len(bin_edges):
                break
            
            bin_start = bin_edges[i]
            bin_end = bin_edges[i + 1]
            
            # Check if bin overlaps with selection range
            if bin_end <= range_min or bin_start >= range_max:
                # No overlap
                continue
            
            # Bin overlaps - determine how much
            if bin_start >= range_min and bin_end <= range_max:
                # Bin is fully within range
                within_range_count += count
            else:
                # Partial overlap - estimate fraction
                overlap_start = max(bin_start, range_min)
                overlap_end = min(bin_end, range_max)
                bin_width = bin_end - bin_start
                
                if bin_width > 0:
                    fraction = (overlap_end - overlap_start) / bin_width
                    within_range_count += int(count * fraction)
        
        # Apply predicate
        if predicate == "within_range":
            return within_range_count
        elif predicate == "outside_range":
            return total_count - within_range_count
        elif predicate == "above_value":
            # Count pixels above range_min
            return self._count_pixels_above(histogram_data, range_min)
        elif predicate == "below_value":
            # Count pixels below range_max
            return self._count_pixels_below(histogram_data, range_max)
        elif predicate == "equals_value":
            # Estimate pixels at exact value (use narrow bin around range_min)
            tolerance = histogram_data.bin_width if histogram_data.bin_width > 0 else 0.01
            return self._calculate_pixel_count_for_predicate(
                histogram_data, range_min - tolerance, range_min + tolerance, "within_range"
            )
        
        return within_range_count
    
    def _count_pixels_above(self, histogram_data: 'HistogramData', threshold: float) -> int:
        """Count pixels with values above threshold."""
        count = 0
        for i, bin_count in enumerate(histogram_data.counts):
            if i + 1 >= len(histogram_data.bin_edges):
                break
            
            bin_start = histogram_data.bin_edges[i]
            bin_end = histogram_data.bin_edges[i + 1]
            
            if bin_start >= threshold:
                count += bin_count
            elif bin_end > threshold:
                # Partial bin
                fraction = (bin_end - threshold) / (bin_end - bin_start)
                count += int(bin_count * fraction)
        
        return count
    
    def _count_pixels_below(self, histogram_data: 'HistogramData', threshold: float) -> int:
        """Count pixels with values below threshold."""
        count = 0
        for i, bin_count in enumerate(histogram_data.counts):
            if i + 1 >= len(histogram_data.bin_edges):
                break
            
            bin_start = histogram_data.bin_edges[i]
            bin_end = histogram_data.bin_edges[i + 1]
            
            if bin_end <= threshold:
                count += bin_count
            elif bin_start < threshold:
                # Partial bin
                fraction = (threshold - bin_start) / (bin_end - bin_start)
                count += int(bin_count * fraction)
        
        return count
    
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
    
    def _show_loading(self, message: str = "⏳ Loading histogram...") -> None:
        """Show loading indicator over histogram."""
        self._loading_label.setText(message)
        self._histogram_stack.setCurrentIndex(1)  # Show loading page
    
    def _hide_loading(self) -> None:
        """Hide loading indicator and show histogram."""
        self._histogram_stack.setCurrentIndex(0)  # Show histogram page
    
    def _load_histogram(self) -> None:
        """Load histogram data for current band."""
        if not self._stats_service or not self._layer_id:
            return
        
        # Show loading indicator
        self._show_loading("⏳ Computing histogram...")
        
        # Force UI update
        from qgis.PyQt.QtWidgets import QApplication
        QApplication.processEvents()
        
        try:
            hist_data = self._stats_service.get_histogram(
                self._layer_id, self._current_band
            )
            if hist_data:
                # Store histogram data for pixel count calculation
                self._histogram_data = hist_data
                
                self._histogram_canvas.set_histogram_data(hist_data)
                
                # Update data range
                self._data_min = hist_data.bin_edges[0]
                self._data_max = hist_data.bin_edges[-1]
                
                # Update spinbox ranges
                self._min_spin.setRange(self._data_min, self._data_max)
                self._max_spin.setRange(self._data_min, self._data_max)
                self._min_spin.setValue(self._data_min)
                self._max_spin.setValue(self._data_max)
                
                # Update total pixels from histogram
                self._total_pixels = hist_data.total_count
                self._pixel_count = self._total_pixels
                self._update_pixel_count()
            else:
                self._histogram_data = None
        except Exception as e:
            logger.error(f"Failed to load histogram: {e}")
            self._histogram_data = None
        finally:
            # Always hide loading indicator
            self._hide_loading()
    
    def clear(self) -> None:
        """Clear all data and reset to default state."""
        self._layer = None
        self._layer_id = None
        self._histogram_data = None  # Clear histogram data
        
        self._band_combo.clear()
        self._band_combo.addItem("Band 1")
        
        self._histogram_canvas.clear()
        
        self._min_spin.setValue(0)
        self._max_spin.setValue(100)
        self._pixel_count = 0
        self._total_pixels = 0
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
        
        # Get target layers if widget available
        target_layers = []
        if self._target_widget:
            target_layers = self._target_widget.get_selected_layer_ids()
        
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
            'target_layers': target_layers,
        }
    
    def _on_targets_changed(self, targets: list) -> None:
        """
        EPIC-3: Handle target layers selection change.
        
        Args:
            targets: List of target layer configurations
        """
        self.targets_changed.emit(targets)
        # Also emit updated context
        self._emit_filter_context_changed()
    
    def _on_execute_requested(self) -> None:
        """
        EPIC-3: Handle execute filter button click.
        """
        logger.info("EPIC-3: Execute filter requested from Value Selection")
        self.execute_filter.emit()
    
    def _on_clear_filters_requested(self, layer_ids: list) -> None:
        """
        EPIC-3: Handle clear filters button click.
        
        Args:
            layer_ids: List of layer IDs to clear filters from
        """
        logger.info(f"EPIC-3: Clear filters requested for {len(layer_ids)} layers")
        self.clear_filters.emit(layer_ids)
    
    def _on_zonal_stats_requested(self, layer_ids: list) -> None:
        """
        EPIC-3: Handle zonal stats button click.
        
        Args:
            layer_ids: List of layer IDs for zonal statistics computation
        """
        logger.info(f"EPIC-3: Zonal stats requested for {len(layer_ids)} layers")
        self.zonal_stats_requested.emit(layer_ids)
    
    def _emit_filter_context_changed(self) -> None:
        """Emit the filter_context_changed signal with current context."""
        context = self.get_filter_context()
        if context:
            self.filter_context_changed.emit(context)
    
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

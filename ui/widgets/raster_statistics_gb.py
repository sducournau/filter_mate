# -*- coding: utf-8 -*-
"""
FilterMate Raster Statistics GroupBox Widget.

EPIC-3: Raster-Vector Integration
GroupBox 1: 📊 STATISTICS

Displays comprehensive raster statistics in a collapsible GroupBox.
Part of the accordion pattern for EXPLORING RASTER panel.

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional, Dict, TYPE_CHECKING

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QFrame,
    QSizePolicy,
    QComboBox,
    QPushButton,
    QFileDialog,
    QMessageBox,
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

if TYPE_CHECKING:
    from qgis.core import QgsRasterLayer
    from core.services.raster_stats_service import (
        LayerStatsSnapshot,
        BandSummary,
        RasterStatsService,
    )

logger = logging.getLogger('FilterMate.UI.RasterStatisticsGB')


class StatCell(QFrame):
    """
    A single statistic cell displaying label and value.
    
    Used in the statistics grid for Min, Max, Mean, StdDev, NoData, Null%.
    """
    
    def __init__(
        self,
        label: str,
        value: str = "—",
        tooltip: str = "",
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._setup_ui(label, value, tooltip)
    
    def _setup_ui(self, label: str, value: str, tooltip: str) -> None:
        """Set up the cell UI."""
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Plain)
        self.setStyleSheet("""
            StatCell {
                background-color: palette(base);
                border: 1px solid palette(mid);
                border-radius: 4px;
                padding: 2px;
            }
            StatCell:hover {
                border-color: palette(highlight);
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(1)
        
        # Label (small, top)
        self._label = QLabel(label)
        self._label.setStyleSheet(
            "font-size: 8px; color: palette(mid); font-weight: normal;"
        )
        self._label.setAlignment(Qt.AlignCenter)
        
        # Value (bold, bottom)
        self._value = QLabel(value)
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        self._value.setFont(font)
        self._value.setAlignment(Qt.AlignCenter)
        self._value.setStyleSheet("color: palette(text);")
        
        layout.addWidget(self._label)
        layout.addWidget(self._value)
        
        if tooltip:
            self.setToolTip(tooltip)
        
        # Size policy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumWidth(50)
    
    def set_value(self, value: str) -> None:
        """Update the displayed value."""
        self._value.setText(value)
    
    def get_value(self) -> str:
        """Get the current value text."""
        return self._value.text()


class RasterStatisticsGroupBox(QWidget):
    """
    Collapsible GroupBox displaying raster statistics.
    
    EPIC-3: GroupBox 1 - 📊 STATISTICS
    
    Features:
    - Band selector for multi-band rasters
    - Statistics grid (Min, Max, Mean, StdDev, NoData, Null%)
    - Layer metadata (dimensions, CRS, resolution, extent)
    - Refresh and Export CSV buttons
    
    Signals:
        collapsed_changed: Emitted when collapse state changes
        band_changed: Emitted when selected band changes
        refresh_requested: Emitted when user requests stats refresh
        export_requested: Emitted when user requests CSV export
        activated: Emitted when this GroupBox becomes active (expanded)
    """
    
    # Signals
    collapsed_changed = pyqtSignal(bool)  # is_collapsed
    band_changed = pyqtSignal(int)  # band_number
    refresh_requested = pyqtSignal()
    export_requested = pyqtSignal(str)  # output_path
    activated = pyqtSignal()  # This GroupBox became active
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the statistics GroupBox.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._layer: Optional['QgsRasterLayer'] = None
        self._layer_id: Optional[str] = None
        self._stats_service: Optional['RasterStatsService'] = None
        self._stats_data: Dict[int, Dict] = {}  # band -> stats
        self._current_band: int = 1
        self._setup_ui()
        self._setup_connections()
    
    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # === Collapsible GroupBox ===
        self._groupbox = QgsCollapsibleGroupBox(self)
        self._groupbox.setTitle("📊 STATISTICS")
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
        
        # Content layout
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
        self._band_combo.setObjectName("combo_raster_band")
        self._band_combo.setMinimumHeight(24)
        self._band_combo.addItem("Band 1")
        band_layout.addWidget(self._band_combo, 1)
        
        content_layout.addLayout(band_layout)
        
        # === Statistics Grid with Loading Overlay ===
        self._stats_stack = QStackedWidget()
        
        # Page 0: Statistics display
        self._stats_frame = QFrame()
        self._stats_frame.setFrameStyle(QFrame.StyledPanel)
        self._stats_frame.setStyleSheet("""
            QFrame {
                background-color: palette(alternate-base);
                border-radius: 4px;
            }
        """)
        
        stats_layout = QGridLayout(self._stats_frame)
        stats_layout.setContentsMargins(8, 8, 8, 8)
        stats_layout.setSpacing(4)
        
        # Header label
        header = QLabel("BAND STATISTICS")
        header.setStyleSheet("font-weight: bold; font-size: 9pt; color: palette(text);")
        header.setAlignment(Qt.AlignCenter)
        stats_layout.addWidget(header, 0, 0, 1, 6)
        
        # Statistics cells (row 1)
        self._stat_cells: Dict[str, StatCell] = {}
        
        stat_configs = [
            ("min", "Min", "Minimum pixel value"),
            ("max", "Max", "Maximum pixel value"),
            ("mean", "Mean", "Average pixel value"),
            ("stddev", "StdDev", "Standard deviation"),
            ("nodata", "NoData", "NoData value"),
            ("null_pct", "Null %", "Percentage of null/nodata pixels"),
        ]
        
        for col, (key, label, tooltip) in enumerate(stat_configs):
            cell = StatCell(label, "—", tooltip)
            self._stat_cells[key] = cell
            stats_layout.addWidget(cell, 1, col)
        
        self._stats_stack.addWidget(self._stats_frame)
        
        # Page 1: Loading indicator
        loading_widget = QFrame()
        loading_widget.setFrameStyle(QFrame.StyledPanel)
        loading_widget.setStyleSheet("""
            QFrame {
                background-color: palette(alternate-base);
                border-radius: 4px;
            }
        """)
        loading_layout = QVBoxLayout(loading_widget)
        loading_layout.setAlignment(Qt.AlignCenter)
        
        self._stats_loading_label = QLabel("⏳ Computing statistics...")
        self._stats_loading_label.setStyleSheet("""
            QLabel {
                color: palette(mid);
                font-style: italic;
                font-size: 10pt;
            }
        """)
        self._stats_loading_label.setAlignment(Qt.AlignCenter)
        loading_layout.addWidget(self._stats_loading_label)
        
        self._stats_loading_progress = QProgressBar()
        self._stats_loading_progress.setRange(0, 0)  # Indeterminate
        self._stats_loading_progress.setMaximumWidth(200)
        self._stats_loading_progress.setTextVisible(False)
        self._stats_loading_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid palette(mid);
                border-radius: 4px;
                background: palette(base);
                height: 8px;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #e74c3c, stop:1 #f39c12
                );
                border-radius: 3px;
            }
        """)
        loading_layout.addWidget(self._stats_loading_progress, 0, Qt.AlignCenter)
        
        self._stats_stack.addWidget(loading_widget)
        
        content_layout.addWidget(self._stats_stack)
        
        # === Metadata Info ===
        self._info_frame = QFrame()
        self._info_frame.setFrameStyle(QFrame.StyledPanel)
        self._info_frame.setStyleSheet("""
            QFrame {
                background-color: palette(alternate-base);
                border-radius: 4px;
                padding: 4px;
            }
        """)
        
        info_layout = QGridLayout(self._info_frame)
        info_layout.setContentsMargins(8, 6, 8, 6)
        info_layout.setSpacing(4)
        
        # Row 1: Data Type, Resolution
        info_layout.addWidget(
            QLabel("Data Type:"), 0, 0, alignment=Qt.AlignRight
        )
        self._dtype_label = QLabel("—")
        self._dtype_label.setStyleSheet("font-family: monospace;")
        info_layout.addWidget(self._dtype_label, 0, 1)
        
        info_layout.addWidget(
            QLabel("Resolution:"), 0, 2, alignment=Qt.AlignRight
        )
        self._resolution_label = QLabel("—")
        self._resolution_label.setStyleSheet("font-family: monospace;")
        info_layout.addWidget(self._resolution_label, 0, 3)
        
        # Row 2: Dimensions, Total Pixels
        info_layout.addWidget(
            QLabel("Dimensions:"), 1, 0, alignment=Qt.AlignRight
        )
        self._dimensions_label = QLabel("—")
        self._dimensions_label.setStyleSheet("font-family: monospace;")
        info_layout.addWidget(self._dimensions_label, 1, 1)
        
        info_layout.addWidget(
            QLabel("Total Pixels:"), 1, 2, alignment=Qt.AlignRight
        )
        self._pixels_label = QLabel("—")
        self._pixels_label.setStyleSheet("font-family: monospace;")
        info_layout.addWidget(self._pixels_label, 1, 3)
        
        # Row 3: CRS, Extent
        info_layout.addWidget(
            QLabel("CRS:"), 2, 0, alignment=Qt.AlignRight
        )
        self._crs_label = QLabel("—")
        self._crs_label.setStyleSheet("font-family: monospace;")
        info_layout.addWidget(self._crs_label, 2, 1)
        
        info_layout.addWidget(
            QLabel("Extent:"), 2, 2, alignment=Qt.AlignRight
        )
        self._extent_label = QLabel("—")
        self._extent_label.setStyleSheet("font-family: monospace;")
        info_layout.addWidget(self._extent_label, 2, 3)
        
        content_layout.addWidget(self._info_frame)
        
        # === Action Buttons ===
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.addStretch()
        
        # Refresh button
        self._refresh_btn = QPushButton("↻ Refresh")
        self._refresh_btn.setObjectName("btn_stats_refresh")
        self._refresh_btn.setToolTip("Refresh statistics")
        self._refresh_btn.setStyleSheet("""
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
        btn_layout.addWidget(self._refresh_btn)
        
        # Export button
        self._export_btn = QPushButton("📥 Export")
        self._export_btn.setObjectName("btn_stats_export")
        self._export_btn.setToolTip("Export statistics to CSV")
        self._export_btn.setStyleSheet("""
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
        self._export_btn.setEnabled(False)
        btn_layout.addWidget(self._export_btn)
        
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
        
        # Buttons
        self._refresh_btn.clicked.connect(self._on_refresh_clicked)
        self._export_btn.clicked.connect(self._on_export_clicked)
    
    def _on_collapse_changed(self, collapsed: bool) -> None:
        """Handle collapse state change."""
        self.collapsed_changed.emit(collapsed)
        
        if not collapsed:
            # GroupBox expanded = activated
            self.activated.emit()
            logger.debug("Statistics GroupBox activated")
    
    def _on_band_changed(self, index: int) -> None:
        """Handle band selection change."""
        band_number = index + 1  # Bands are 1-indexed
        self._current_band = band_number
        self.band_changed.emit(band_number)
        
        # Update stats display for new band
        self._update_stats_display()
    
    def _on_refresh_clicked(self) -> None:
        """Handle refresh button click."""
        self.refresh_requested.emit()
        
        # If we have a stats service, refresh
        if self._stats_service and self._layer_id:
            self._load_stats()
    
    def _on_export_clicked(self) -> None:
        """Handle export button click."""
        if self._layer_id is None:
            QMessageBox.warning(
                self,
                "FilterMate",
                "No raster layer selected. Please select a layer first."
            )
            return
        
        # Get suggested filename
        layer_name = self._layer.name() if self._layer else "raster"
        safe_name = "".join(
            c if c.isalnum() or c in ('-', '_') else '_'
            for c in layer_name
        )
        suggested_name = f"{safe_name}_stats.csv"
        
        # Show file dialog
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Raster Statistics",
            suggested_name,
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not output_path:
            return
        
        if not output_path.lower().endswith('.csv'):
            output_path += '.csv'
        
        # Export via service or emit signal
        if self._stats_service:
            try:
                success = self._stats_service.export_stats_to_csv(
                    self._layer_id, output_path
                )
                if success:
                    QMessageBox.information(
                        self,
                        "FilterMate",
                        f"Statistics exported to:\n{output_path}"
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "FilterMate",
                        "Failed to export statistics."
                    )
            except Exception as e:
                logger.error(f"Export error: {e}")
                QMessageBox.critical(
                    self,
                    "FilterMate",
                    f"Export error: {str(e)}"
                )
        else:
            self.export_requested.emit(output_path)
    
    def set_layer(self, layer: Optional['QgsRasterLayer']) -> None:
        """
        Set the raster layer for statistics display.
        
        Args:
            layer: QgsRasterLayer or None to clear
        """
        self._layer = layer
        self._layer_id = layer.id() if layer else None
        
        if layer is not None:
            # Populate band combo
            self._populate_band_combo(layer)
            # Load stats
            self._load_stats()
            self._export_btn.setEnabled(True)
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
    
    def _show_stats_loading(self, message: str = "⏳ Computing statistics...") -> None:
        """Show loading indicator over statistics grid."""
        self._stats_loading_label.setText(message)
        self._stats_stack.setCurrentIndex(1)  # Show loading page
    
    def _hide_stats_loading(self) -> None:
        """Hide loading indicator and show statistics."""
        self._stats_stack.setCurrentIndex(0)  # Show stats page
    
    def _load_stats(self) -> None:
        """Load statistics from service."""
        if not self._stats_service or not self._layer_id:
            return
        
        # Show loading indicator
        self._show_stats_loading("⏳ Computing band statistics...")
        
        # Force UI update
        from qgis.PyQt.QtWidgets import QApplication
        QApplication.processEvents()
        
        try:
            snapshot = self._stats_service.get_layer_snapshot(self._layer_id)
            if snapshot:
                self._apply_snapshot(snapshot)
        except Exception as e:
            logger.error(f"Failed to load stats: {e}")
        finally:
            # Always hide loading indicator
            self._hide_stats_loading()
    
    def _apply_snapshot(self, snapshot: 'LayerStatsSnapshot') -> None:
        """Apply a stats snapshot to the display."""
        # Update metadata
        self._dimensions_label.setText(
            f"{snapshot.width} × {snapshot.height} px"
        )
        self._pixels_label.setText(f"{snapshot.width * snapshot.height:,}")
        self._crs_label.setText(snapshot.crs_auth_id or "—")
        
        # Calculate extent area
        extent = snapshot.extent
        if extent:
            width_km = extent.width() / 1000
            height_km = extent.height() / 1000
            self._extent_label.setText(f"{width_km:.1f} × {height_km:.1f} km")
        
        # Resolution
        if snapshot.pixel_size_x and snapshot.pixel_size_y:
            self._resolution_label.setText(
                f"{snapshot.pixel_size_x:.1f}m × {snapshot.pixel_size_y:.1f}m"
            )
        
        # Store band stats
        self._stats_data.clear()
        for band in snapshot.bands:
            self._stats_data[band.band_number] = {
                'min': band.minimum,
                'max': band.maximum,
                'mean': band.mean,
                'stddev': band.std_dev,
                'nodata': band.no_data_value,
                'null_pct': band.no_data_percentage,
                'data_type': band.data_type,
            }
        
        # Update display
        self._update_stats_display()
    
    def _update_stats_display(self) -> None:
        """Update the statistics display for current band."""
        band_stats = self._stats_data.get(self._current_band)
        
        if band_stats is None:
            self._clear_stats()
            return
        
        # Format values
        def fmt(value, precision=2):
            if value is None:
                return "—"
            if isinstance(value, float):
                return f"{value:.{precision}f}"
            return str(value)
        
        self._stat_cells['min'].set_value(fmt(band_stats.get('min')))
        self._stat_cells['max'].set_value(fmt(band_stats.get('max')))
        self._stat_cells['mean'].set_value(fmt(band_stats.get('mean')))
        self._stat_cells['stddev'].set_value(fmt(band_stats.get('stddev')))
        self._stat_cells['nodata'].set_value(fmt(band_stats.get('nodata'), 0))
        
        null_pct = band_stats.get('null_pct')
        if null_pct is not None:
            self._stat_cells['null_pct'].set_value(f"{null_pct:.1f}%")
        else:
            self._stat_cells['null_pct'].set_value("—")
        
        # Data type
        self._dtype_label.setText(band_stats.get('data_type', '—'))
    
    def _clear_stats(self) -> None:
        """Clear statistics display."""
        for cell in self._stat_cells.values():
            cell.set_value("—")
        self._dtype_label.setText("—")
    
    def clear(self) -> None:
        """Clear all data and reset to default state."""
        self._layer = None
        self._layer_id = None
        self._stats_data.clear()
        
        self._band_combo.clear()
        self._band_combo.addItem("Band 1")
        
        self._clear_stats()
        self._dimensions_label.setText("—")
        self._pixels_label.setText("—")
        self._crs_label.setText("—")
        self._extent_label.setText("—")
        self._resolution_label.setText("—")
        
        self._export_btn.setEnabled(False)
    
    def set_stats_service(self, service: 'RasterStatsService') -> None:
        """
        Set the RasterStatsService for data retrieval.
        
        Args:
            service: RasterStatsService instance
        """
        self._stats_service = service
    
    def set_collapsed(self, collapsed: bool) -> None:
        """
        Programmatically set the collapsed state.
        
        Args:
            collapsed: True to collapse, False to expand
        """
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
    
    def get_filter_context(self) -> Dict:
        """
        Get the current filter context for FILTERING synchronization.
        
        Returns:
            dict: Filter context with source info and stats
        """
        if self._layer is None:
            return {}
        
        band_stats = self._stats_data.get(self._current_band, {})
        
        return {
            'source_type': 'raster',
            'mode': 'info_only',
            'layer_id': self._layer_id,
            'layer_name': self._layer.name() if self._layer else None,
            'band': self._current_band,
            'band_name': self._band_combo.currentText(),
            'stats': {
                'min': band_stats.get('min'),
                'max': band_stats.get('max'),
                'mean': band_stats.get('mean'),
                'stddev': band_stats.get('stddev'),
            }
        }
    
    @property
    def layer(self) -> Optional['QgsRasterLayer']:
        """Get the current raster layer."""
        return self._layer
    
    @property
    def current_band(self) -> int:
        """Get the currently selected band number."""
        return self._current_band

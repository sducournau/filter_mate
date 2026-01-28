# -*- coding: utf-8 -*-
"""
FilterMate Raster Stats Panel Widget.

EPIC-2: Raster Integration
US-05: Stats Panel Widget

Displays comprehensive raster statistics in a clean, organized panel.
Connects to RasterStatsService for data retrieval.

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional, TYPE_CHECKING, Dict

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QFrame,
    QSizePolicy,
    QScrollArea,
    QComboBox,
    QPushButton,
    QFileDialog,
    QMessageBox,
)
from qgis.PyQt.QtGui import QFont

if TYPE_CHECKING:
    from qgis.core import QgsRasterLayer
    from core.services.raster_stats_service import (
        LayerStatsSnapshot,
        BandSummary,
        RasterStatsService,
    )

logger = logging.getLogger('FilterMate.UI.RasterStatsPanel')


class StatCard(QFrame):
    """
    A small card displaying a single statistic.
    
    Shows label on top, value below in a compact format.
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
        """Set up the card UI."""
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Plain)
        self.setStyleSheet("""
            StatCard {
                background-color: palette(base);
                border: 1px solid palette(mid);
                border-radius: 4px;
                padding: 4px;
            }
            StatCard:hover {
                border-color: palette(highlight);
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        
        # Label
        self._label = QLabel(label)
        self._label.setStyleSheet(
            "font-size: 9px; color: palette(mid); font-weight: normal;"
        )
        self._label.setAlignment(Qt.AlignCenter)
        
        # Value
        self._value = QLabel(value)
        font = QFont()
        font.setPointSize(11)
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
        self.setMinimumWidth(60)
    
    def set_value(self, value: str) -> None:
        """Update the displayed value."""
        self._value.setText(value)
    
    def set_label(self, label: str) -> None:
        """Update the label text."""
        self._label.setText(label)


class BandStatsRow(QWidget):
    """
    A row displaying statistics for a single raster band.
    
    Shows: Band name, Min, Max, Mean, StdDev, NoData%, DataType
    """
    
    def __init__(
        self,
        band_number: int,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._band_number = band_number
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the row UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)
        
        # Band label
        self._band_label = QLabel(f"Band {self._band_number}")
        self._band_label.setStyleSheet(
            "font-weight: bold; min-width: 50px;"
        )
        layout.addWidget(self._band_label)
        
        # Stats cards
        self._cards: Dict[str, StatCard] = {}
        
        stats_config = [
            ("min", "Min", "Minimum pixel value"),
            ("max", "Max", "Maximum pixel value"),
            ("mean", "Mean", "Average pixel value"),
            ("stddev", "Std", "Standard deviation"),
            ("null", "Null%", "Percentage of no-data pixels"),
        ]
        
        for key, label, tooltip in stats_config:
            card = StatCard(label, "—", tooltip)
            self._cards[key] = card
            layout.addWidget(card)
        
        # Data type label (smaller, at the end)
        self._dtype_label = QLabel("—")
        self._dtype_label.setStyleSheet(
            "font-size: 9px; color: palette(mid); min-width: 50px;"
        )
        self._dtype_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self._dtype_label)
    
    def update_stats(
        self,
        min_val: str,
        max_val: str,
        mean: str,
        stddev: str,
        null_percent: str,
        data_type: str
    ) -> None:
        """Update all statistics in the row."""
        self._cards["min"].set_value(min_val)
        self._cards["max"].set_value(max_val)
        self._cards["mean"].set_value(mean)
        self._cards["stddev"].set_value(stddev)
        self._cards["null"].set_value(null_percent)
        self._dtype_label.setText(data_type)
    
    def clear(self) -> None:
        """Clear all statistics."""
        for card in self._cards.values():
            card.set_value("—")
        self._dtype_label.setText("—")


class RasterStatsPanel(QWidget):
    """
    Panel displaying comprehensive raster statistics.
    
    EPIC-2 US-05: Stats Panel Widget
    EPIC-2 US-14: Export Stats CSV
    
    Features:
    - Layer metadata (dimensions, CRS, extent)
    - Band selector for multi-band rasters
    - Per-band statistics (min, max, mean, stddev, null%)
    - Data type information
    - Export to CSV functionality
    
    Signals:
        band_changed: Emitted when selected band changes
        refresh_requested: Emitted when user requests stats refresh
        export_requested: Emitted when user requests CSV export
    """
    
    band_changed = pyqtSignal(int)  # band_number
    refresh_requested = pyqtSignal()
    export_requested = pyqtSignal(str)  # output_path
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layer: Optional['QgsRasterLayer'] = None
        self._layer_id: Optional[str] = None
        self._stats_service: Optional['RasterStatsService'] = None
        self._band_rows: Dict[int, BandStatsRow] = {}
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the panel UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)
        
        # === Layer Info Section ===
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
        info_layout.setContentsMargins(8, 8, 8, 8)
        info_layout.setSpacing(4)
        
        # Layer name
        self._layer_name_label = QLabel("No layer selected")
        self._layer_name_label.setStyleSheet(
            "font-weight: bold; font-size: 11px;"
        )
        info_layout.addWidget(self._layer_name_label, 0, 0, 1, 4)
        
        # Dimensions
        info_layout.addWidget(
            QLabel("Size:"), 1, 0, alignment=Qt.AlignRight
        )
        self._size_label = QLabel("— × — px")
        self._size_label.setStyleSheet("font-family: monospace;")
        info_layout.addWidget(self._size_label, 1, 1)
        
        # Bands
        info_layout.addWidget(
            QLabel("Bands:"), 1, 2, alignment=Qt.AlignRight
        )
        self._bands_label = QLabel("—")
        info_layout.addWidget(self._bands_label, 1, 3)
        
        # CRS
        info_layout.addWidget(
            QLabel("CRS:"), 2, 0, alignment=Qt.AlignRight
        )
        self._crs_label = QLabel("—")
        self._crs_label.setStyleSheet("font-family: monospace;")
        info_layout.addWidget(self._crs_label, 2, 1)
        
        # File size
        info_layout.addWidget(
            QLabel("Est. Size:"), 2, 2, alignment=Qt.AlignRight
        )
        self._filesize_label = QLabel("— MB")
        info_layout.addWidget(self._filesize_label, 2, 3)
        
        main_layout.addWidget(self._info_frame)
        
        # === Band Selection (for multi-band) ===
        self._band_selector_frame = QWidget()
        band_selector_layout = QHBoxLayout(self._band_selector_frame)
        band_selector_layout.setContentsMargins(0, 0, 0, 0)
        band_selector_layout.setSpacing(8)
        
        band_selector_layout.addWidget(QLabel("View Band:"))
        self._band_combo = QComboBox()
        self._band_combo.addItem("All Bands")
        self._band_combo.currentIndexChanged.connect(self._on_band_selection_changed)
        band_selector_layout.addWidget(self._band_combo, 1)
        
        self._band_selector_frame.setVisible(False)  # Hidden for single-band
        main_layout.addWidget(self._band_selector_frame)
        
        # === Band Statistics Section ===
        self._stats_scroll = QScrollArea()
        self._stats_scroll.setWidgetResizable(True)
        self._stats_scroll.setFrameStyle(QFrame.NoFrame)
        self._stats_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self._stats_container = QWidget()
        self._stats_layout = QVBoxLayout(self._stats_container)
        self._stats_layout.setContentsMargins(0, 0, 0, 0)
        self._stats_layout.setSpacing(4)
        self._stats_layout.addStretch()
        
        self._stats_scroll.setWidget(self._stats_container)
        main_layout.addWidget(self._stats_scroll, 1)
        
        # === Export Button Section (US-14) ===
        self._export_frame = QWidget()
        export_layout = QHBoxLayout(self._export_frame)
        export_layout.setContentsMargins(0, 4, 0, 0)
        export_layout.setSpacing(8)
        
        export_layout.addStretch()
        
        self._export_btn = QPushButton("📥 Export CSV")
        self._export_btn.setToolTip("Export statistics to CSV file")
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
        self._export_btn.clicked.connect(self._on_export_clicked)
        self._export_btn.setEnabled(False)  # Disabled until layer is set
        export_layout.addWidget(self._export_btn)
        
        main_layout.addWidget(self._export_frame)
        
        # === Placeholder for empty state ===
        self._empty_label = QLabel(
            "Select a raster layer to view statistics"
        )
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet(
            "color: palette(mid); font-style: italic; padding: 20px;"
        )
        main_layout.addWidget(self._empty_label)
        
        # Initial state
        self._show_empty_state()
    
    def _on_export_clicked(self) -> None:
        """
        Handle export button click.
        
        EPIC-2 US-14: Export Stats CSV
        """
        if self._layer_id is None:
            QMessageBox.warning(
                self,
                "FilterMate",
                "No raster layer selected. Please select a layer first."
            )
            return
        
        # Get suggested filename from layer name
        layer_name = self._layer_name_label.text()
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
            return  # User cancelled
        
        # Ensure .csv extension
        if not output_path.lower().endswith('.csv'):
            output_path += '.csv'
        
        # Try to export using service if available
        if self._stats_service is not None:
            try:
                success = self._stats_service.export_stats_to_csv(
                    layer_id=self._layer_id,
                    output_path=output_path,
                    include_histogram_summary=True
                )
                
                if success:
                    QMessageBox.information(
                        self,
                        "FilterMate",
                        f"Statistics exported successfully to:\n{output_path}"
                    )
                    logger.info(f"Stats exported to {output_path}")
                else:
                    QMessageBox.warning(
                        self,
                        "FilterMate",
                        "Failed to export statistics. Check the log for details."
                    )
            except Exception as e:
                logger.error(f"Export failed: {e}")
                QMessageBox.critical(
                    self,
                    "FilterMate",
                    f"Export error: {str(e)}"
                )
        else:
            # Emit signal for controller to handle
            self.export_requested.emit(output_path)
            logger.debug(f"Export requested to {output_path}")
    
    def set_stats_service(self, service: 'RasterStatsService') -> None:
        """
        Set the stats service for direct export.
        
        Args:
            service: RasterStatsService instance
        """
        self._stats_service = service
    
    def _show_empty_state(self) -> None:
        """Show empty state (no layer selected)."""
        self._info_frame.setVisible(False)
        self._band_selector_frame.setVisible(False)
        self._stats_scroll.setVisible(False)
        self._export_frame.setVisible(False)
        self._empty_label.setVisible(True)
        self._export_btn.setEnabled(False)
    
    def _show_stats_state(self) -> None:
        """Show stats state (layer selected)."""
        self._info_frame.setVisible(True)
        self._stats_scroll.setVisible(True)
        self._export_frame.setVisible(True)
        self._empty_label.setVisible(False)
        self._export_btn.setEnabled(True)
    
    def _on_band_selection_changed(self, index: int) -> None:
        """Handle band selection change."""
        if index == 0:
            # Show all bands
            for row in self._band_rows.values():
                row.setVisible(True)
        else:
            # Show only selected band
            band_num = index  # index 1 = band 1, etc.
            for bn, row in self._band_rows.items():
                row.setVisible(bn == band_num)
        
        self.band_changed.emit(index)
    
    def set_layer_snapshot(
        self,
        snapshot: Optional['LayerStatsSnapshot']
    ) -> None:
        """
        Update panel with layer statistics snapshot.
        
        Args:
            snapshot: LayerStatsSnapshot from RasterStatsService, or None to clear
        """
        if snapshot is None:
            self.clear()
            return
        
        self._show_stats_state()
        
        # Store layer_id for export (US-14)
        self._layer_id = snapshot.layer_id
        
        # Update layer info
        self._layer_name_label.setText(snapshot.layer_name)
        self._size_label.setText(f"{snapshot.width} × {snapshot.height} px")
        self._bands_label.setText(str(snapshot.band_count))
        self._crs_label.setText(snapshot.crs or "Unknown")
        self._filesize_label.setText(f"~{snapshot.file_size_mb:.1f} MB")
        
        # Update band selector
        self._band_combo.blockSignals(True)
        self._band_combo.clear()
        self._band_combo.addItem("All Bands")
        for i in range(1, snapshot.band_count + 1):
            self._band_combo.addItem(f"Band {i}")
        self._band_combo.setCurrentIndex(0)
        self._band_combo.blockSignals(False)
        
        # Show band selector only for multi-band
        self._band_selector_frame.setVisible(snapshot.band_count > 1)
        
        # Clear existing band rows
        for row in self._band_rows.values():
            row.setParent(None)
            row.deleteLater()
        self._band_rows.clear()
        
        # Create band rows
        for band_summary in snapshot.band_summaries:
            row = BandStatsRow(band_summary.band_number)
            row.update_stats(
                min_val=band_summary.min_value,
                max_val=band_summary.max_value,
                mean=band_summary.mean,
                stddev=band_summary.std_dev,
                null_percent=band_summary.null_percent,
                data_type=band_summary.data_type
            )
            self._band_rows[band_summary.band_number] = row
            # Insert before stretch
            self._stats_layout.insertWidget(
                self._stats_layout.count() - 1, row
            )
        
        logger.debug(
            f"Stats panel updated: {snapshot.layer_name}, "
            f"{snapshot.band_count} bands"
        )
    
    def clear(self) -> None:
        """Clear the panel and show empty state."""
        self._layer_name_label.setText("No layer selected")
        self._size_label.setText("— × — px")
        self._bands_label.setText("—")
        self._crs_label.setText("—")
        self._filesize_label.setText("— MB")
        
        # Clear layer ID for export (US-14)
        self._layer_id = None
        
        # Clear band rows
        for row in self._band_rows.values():
            row.setParent(None)
            row.deleteLater()
        self._band_rows.clear()
        
        self._band_combo.clear()
        self._band_combo.addItem("All Bands")
        
        self._show_empty_state()
        logger.debug("Stats panel cleared")
    
    def refresh(self) -> None:
        """Request statistics refresh."""
        self.refresh_requested.emit()

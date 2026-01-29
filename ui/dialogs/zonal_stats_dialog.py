# -*- coding: utf-8 -*-
"""
Zonal Statistics Results Dialog.

EPIC-3: Raster-Vector Integration
Displays zonal statistics results in a table format with export options.

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import List, Optional, Dict, Any

try:
    from qgis.PyQt.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
        QPushButton, QLabel, QHeaderView, QFileDialog, QMessageBox,
        QProgressBar, QComboBox, QCheckBox, QGroupBox, QApplication
    )
    from qgis.PyQt.QtCore import Qt, pyqtSignal
    from qgis.PyQt.QtGui import QFont, QColor, QCursor
    HAS_QGIS = True
except ImportError:
    HAS_QGIS = False

from ...core.ports.raster_filter_port import ZonalStatisticsResult

logger = logging.getLogger(__name__)


class ZonalStatsDialog(QDialog):
    """
    Dialog to display zonal statistics results.
    
    EPIC-3: Shows computed statistics per vector zone with options to:
    - Export to CSV
    - Copy to clipboard
    - Add results as layer attributes
    
    Signals:
        export_requested: Emitted when user wants to export results
        add_to_layer_requested: Emitted when user wants to add stats to layer
    """
    
    export_requested = pyqtSignal(str)  # file path
    add_to_layer_requested = pyqtSignal(str)  # layer_id
    
    # Column definitions
    COLUMNS = [
        ('feature_id', 'Feature ID', 80),
        ('zone_name', 'Zone Name', 120),
        ('pixel_count', 'Pixels', 70),
        ('min_value', 'Min', 80),
        ('max_value', 'Max', 80),
        ('mean_value', 'Mean', 90),
        ('std_dev', 'Std Dev', 80),
        ('sum_value', 'Sum', 90),
    ]
    
    def __init__(
        self,
        results: List[ZonalStatisticsResult],
        raster_name: str = "",
        vector_name: str = "",
        band: int = 1,
        parent: Optional['QWidget'] = None
    ):
        """
        Initialize the dialog.
        
        Args:
            results: List of ZonalStatisticsResult objects
            raster_name: Name of source raster layer
            vector_name: Name of zone vector layer  
            band: Band number used for statistics
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._results = results
        self._raster_name = raster_name
        self._vector_name = vector_name
        self._band = band
        
        self._setup_ui()
        self._populate_table()
    
    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        self.setWindowTitle("Zonal Statistics Results")
        self.setMinimumSize(700, 500)
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Header info
        header_layout = QVBoxLayout()
        
        title_label = QLabel(f"📊 Zonal Statistics Results", self)
        title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        header_layout.addWidget(title_label)
        
        info_label = QLabel(
            f"Raster: {self._raster_name} (Band {self._band}) | "
            f"Zones: {self._vector_name} | "
            f"Features: {len(self._results)}",
            self
        )
        info_label.setStyleSheet("color: gray;")
        header_layout.addWidget(info_label)
        
        layout.addLayout(header_layout)
        
        # Results table
        self._table = QTableWidget(self)
        self._table.setColumnCount(len(self.COLUMNS))
        self._table.setHorizontalHeaderLabels([col[1] for col in self.COLUMNS])
        
        # Set column widths
        for i, (_, _, width) in enumerate(self.COLUMNS):
            self._table.setColumnWidth(i, width)
        
        # Table settings
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.ExtendedSelection)
        self._table.setSortingEnabled(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        
        layout.addWidget(self._table)
        
        # Summary statistics
        self._summary_group = QGroupBox("Summary", self)
        summary_layout = QHBoxLayout(self._summary_group)
        
        self._lbl_summary = QLabel("", self)
        summary_layout.addWidget(self._lbl_summary)
        
        layout.addWidget(self._summary_group)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self._btn_copy = QPushButton("📋 Copy to Clipboard", self)
        self._btn_copy.setCursor(QCursor(Qt.PointingHandCursor))
        self._btn_copy.clicked.connect(self._copy_to_clipboard)
        button_layout.addWidget(self._btn_copy)
        
        self._btn_export = QPushButton("💾 Export to CSV", self)
        self._btn_export.setCursor(QCursor(Qt.PointingHandCursor))
        self._btn_export.clicked.connect(self._export_to_csv)
        button_layout.addWidget(self._btn_export)
        
        button_layout.addStretch()
        
        self._btn_close = QPushButton("Close", self)
        self._btn_close.clicked.connect(self.accept)
        button_layout.addWidget(self._btn_close)
        
        layout.addLayout(button_layout)
    
    def _populate_table(self) -> None:
        """Populate the table with results."""
        self._table.setRowCount(len(self._results))
        
        # Track summary stats
        all_means = []
        all_mins = []
        all_maxs = []
        total_pixels = 0
        
        for row, result in enumerate(self._results):
            # Feature ID
            self._set_cell(row, 0, str(result.feature_id))
            
            # Zone Name
            self._set_cell(row, 1, result.zone_name or f"Zone {result.feature_id}")
            
            # Pixel Count
            self._set_cell(row, 2, str(result.valid_pixel_count or result.pixel_count))
            total_pixels += result.valid_pixel_count or result.pixel_count or 0
            
            # Min
            if result.min_value is not None:
                self._set_cell(row, 3, f"{result.min_value:.4f}")
                all_mins.append(result.min_value)
            else:
                self._set_cell(row, 3, "—")
            
            # Max
            if result.max_value is not None:
                self._set_cell(row, 4, f"{result.max_value:.4f}")
                all_maxs.append(result.max_value)
            else:
                self._set_cell(row, 4, "—")
            
            # Mean
            if result.mean_value is not None:
                self._set_cell(row, 5, f"{result.mean_value:.4f}")
                all_means.append(result.mean_value)
            else:
                self._set_cell(row, 5, "—")
            
            # Std Dev
            if result.std_dev is not None:
                self._set_cell(row, 6, f"{result.std_dev:.4f}")
            else:
                self._set_cell(row, 6, "—")
            
            # Sum
            if result.sum_value is not None:
                self._set_cell(row, 7, f"{result.sum_value:.2f}")
            else:
                self._set_cell(row, 7, "—")
        
        # Update summary
        summary_parts = [f"Zones: {len(self._results)}"]
        summary_parts.append(f"Total Pixels: {total_pixels:,}")
        
        if all_mins:
            summary_parts.append(f"Global Min: {min(all_mins):.4f}")
        if all_maxs:
            summary_parts.append(f"Global Max: {max(all_maxs):.4f}")
        if all_means:
            avg_mean = sum(all_means) / len(all_means)
            summary_parts.append(f"Avg Mean: {avg_mean:.4f}")
        
        self._lbl_summary.setText(" | ".join(summary_parts))
    
    def _set_cell(self, row: int, col: int, text: str) -> None:
        """Set a cell value with proper alignment."""
        item = QTableWidgetItem(text)
        
        # Right-align numeric columns
        if col >= 2:
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        else:
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        self._table.setItem(row, col, item)
    
    def _copy_to_clipboard(self) -> None:
        """Copy table contents to clipboard."""
        lines = []
        
        # Header
        headers = [col[1] for col in self.COLUMNS]
        lines.append("\t".join(headers))
        
        # Data rows
        for row in range(self._table.rowCount()):
            row_data = []
            for col in range(self._table.columnCount()):
                item = self._table.item(row, col)
                row_data.append(item.text() if item else "")
            lines.append("\t".join(row_data))
        
        text = "\n".join(lines)
        
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        
        QMessageBox.information(
            self,
            "Copied",
            f"Copied {len(self._results)} rows to clipboard"
        )
    
    def _export_to_csv(self) -> None:
        """Export results to CSV file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Zonal Statistics",
            f"zonal_stats_{self._vector_name}.csv",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                # Header
                headers = [col[1] for col in self.COLUMNS]
                f.write(",".join(headers) + "\n")
                
                # Data
                for row in range(self._table.rowCount()):
                    row_data = []
                    for col in range(self._table.columnCount()):
                        item = self._table.item(row, col)
                        value = item.text() if item else ""
                        # Escape commas
                        if "," in value:
                            value = f'"{value}"'
                        row_data.append(value)
                    f.write(",".join(row_data) + "\n")
            
            self.export_requested.emit(file_path)
            
            QMessageBox.information(
                self,
                "Export Complete",
                f"Exported {len(self._results)} zones to:\n{file_path}"
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export: {str(e)}"
            )
    
    @property
    def results(self) -> List[ZonalStatisticsResult]:
        """Get the results list."""
        return self._results

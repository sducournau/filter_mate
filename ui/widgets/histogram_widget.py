# -*- coding: utf-8 -*-
"""
FilterMate Raster Histogram Widget.

EPIC-2: Raster Integration
US-06: Histogram Visualization

Provides a histogram visualization widget for raster band data,
integrated with theme support for dark/light modes.

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional, List, Tuple, TYPE_CHECKING

from qgis.PyQt.QtCore import Qt, pyqtSignal, QPointF, QRectF
from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QFrame,
)
from qgis.PyQt.QtGui import (
    QPainter,
    QPen,
    QBrush,
    QColor,
    QFontMetrics,
    QPalette,
)

if TYPE_CHECKING:
    from core.ports.raster_port import HistogramData

logger = logging.getLogger('FilterMate.UI.HistogramWidget')


class HistogramCanvas(QWidget):
    """
    Custom canvas widget for drawing the histogram.
    
    Features:
    - Smooth bar rendering
    - Theme-aware colors
    - Selection range highlighting
    - Interactive range selection via mouse
    
    Signals:
        range_changed(float, float): Emitted when selection range changes
        selection_started: Emitted when user starts selecting
        selection_ended: Emitted when user ends selecting
    """
    
    range_changed = pyqtSignal(float, float)
    selection_started = pyqtSignal()
    selection_ended = pyqtSignal()
    
    # Padding constants
    PADDING_LEFT = 50
    PADDING_RIGHT = 10
    PADDING_TOP = 10
    PADDING_BOTTOM = 30
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the histogram canvas."""
        super().__init__(parent)
        
        # Data
        self._histogram_data: Optional['HistogramData'] = None
        self._bin_counts: List[int] = []
        self._bin_edges: List[float] = []
        
        # Selection range
        self._range_min: Optional[float] = None
        self._range_max: Optional[float] = None
        
        # Interaction state
        self._is_selecting = False
        self._selection_start_x: float = 0
        
        # Theme colors (updated dynamically)
        self._bar_color = QColor("#3498db")  # Blue
        self._selected_color = QColor("#2980b9")  # Darker blue
        self._unselected_color = QColor("#95a5a6")  # Gray
        self._axis_color = QColor("#7f8c8d")
        self._text_color = QColor("#2c3e50")
        self._grid_color = QColor("#ecf0f1")
        
        # Widget settings
        self.setMinimumHeight(150)
        self.setMinimumWidth(200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        
        # Update colors from palette
        self._update_colors_from_theme()
    
    def _update_colors_from_theme(self) -> None:
        """Update colors based on current palette/theme."""
        palette = self.palette()
        
        # Check if dark mode by comparing background luminance
        bg_color = palette.color(QPalette.Window)
        
        is_dark = bg_color.lightness() < 128
        
        if is_dark:
            # Dark theme colors
            self._bar_color = QColor("#5dade2")  # Light blue
            self._selected_color = QColor("#3498db")  # Blue
            self._unselected_color = QColor("#5d6d7e")  # Dark gray
            self._axis_color = QColor("#aab7b8")
            self._text_color = palette.color(QPalette.WindowText)
            self._grid_color = QColor("#34495e")
        else:
            # Light theme colors
            self._bar_color = QColor("#3498db")  # Blue
            self._selected_color = QColor("#2980b9")  # Darker blue
            self._unselected_color = QColor("#bdc3c7")  # Light gray
            self._axis_color = QColor("#7f8c8d")
            self._text_color = palette.color(QPalette.WindowText)
            self._grid_color = QColor("#ecf0f1")
    
    def set_histogram_data(self, data: 'HistogramData') -> None:
        """
        Set histogram data to display.
        
        Args:
            data: HistogramData from RasterPort
        """
        self._histogram_data = data
        self._bin_counts = list(data.counts)
        self._bin_edges = list(data.bin_edges)
        
        # Reset selection
        if self._bin_edges:
            self._range_min = self._bin_edges[0]
            self._range_max = self._bin_edges[-1]
        else:
            self._range_min = None
            self._range_max = None
        
        self.update()
        logger.debug(
            f"Histogram data set: {len(self._bin_counts)} bins, "
            f"range [{self._range_min}, {self._range_max}]"
        )
    
    def set_selection_range(
        self,
        min_val: Optional[float],
        max_val: Optional[float]
    ) -> None:
        """
        Set the highlighted selection range.
        
        Args:
            min_val: Minimum value of selection
            max_val: Maximum value of selection
        """
        self._range_min = min_val
        self._range_max = max_val
        self.update()
    
    def reset_selection(self) -> None:
        """Reset selection to full range."""
        if self._bin_edges:
            self._range_min = self._bin_edges[0]
            self._range_max = self._bin_edges[-1]
            self.range_changed.emit(self._range_min, self._range_max)
        self.update()
    
    def clear(self) -> None:
        """Clear histogram data."""
        self._histogram_data = None
        self._bin_counts = []
        self._bin_edges = []
        self._range_min = None
        self._range_max = None
        self.update()
    
    def paintEvent(self, event) -> None:
        """Draw the histogram."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Update colors for current theme
        self._update_colors_from_theme()
        
        # Fill background
        painter.fillRect(
            self.rect(),
            self.palette().color(QPalette.Base)
        )
        
        if not self._bin_counts or not self._bin_edges:
            self._draw_empty_state(painter)
            return
        
        # Calculate drawing area
        draw_rect = self._get_draw_rect()
        
        # Draw grid
        self._draw_grid(painter, draw_rect)
        
        # Draw histogram bars
        self._draw_bars(painter, draw_rect)
        
        # Draw axes
        self._draw_axes(painter, draw_rect)
        
        painter.end()
    
    def _get_draw_rect(self) -> QRectF:
        """Get the rectangle for drawing the histogram."""
        return QRectF(
            self.PADDING_LEFT,
            self.PADDING_TOP,
            self.width() - self.PADDING_LEFT - self.PADDING_RIGHT,
            self.height() - self.PADDING_TOP - self.PADDING_BOTTOM
        )
    
    def _draw_empty_state(self, painter: QPainter) -> None:
        """Draw placeholder when no data."""
        painter.setPen(QPen(self._text_color))
        font = painter.font()
        font.setItalic(True)
        painter.setFont(font)
        painter.drawText(
            self.rect(),
            Qt.AlignCenter,
            "No histogram data"
        )
    
    def _draw_grid(self, painter: QPainter, rect: QRectF) -> None:
        """Draw background grid lines."""
        painter.setPen(QPen(self._grid_color, 1, Qt.DashLine))
        
        # Horizontal grid lines (4 lines)
        for i in range(1, 5):
            y = rect.top() + (rect.height() * i / 5)
            painter.drawLine(
                QPointF(rect.left(), y),
                QPointF(rect.right(), y)
            )
    
    def _draw_bars(self, painter: QPainter, rect: QRectF) -> None:
        """Draw histogram bars."""
        if not self._bin_counts:
            return
        
        n_bins = len(self._bin_counts)
        bar_width = rect.width() / n_bins
        max_count = max(self._bin_counts) if self._bin_counts else 1
        
        if max_count == 0:
            max_count = 1
        
        for i, count in enumerate(self._bin_counts):
            # Calculate bar geometry
            bar_height = (count / max_count) * rect.height()
            x = rect.left() + i * bar_width
            y = rect.bottom() - bar_height
            
            # Determine if this bar is within selection range
            bin_start = self._bin_edges[i]
            next_idx = i + 1
            if next_idx < len(self._bin_edges):
                bin_end = self._bin_edges[next_idx]
            else:
                bin_end = bin_start
            
            is_selected = self._is_bin_selected(bin_start, bin_end)
            
            # Set bar color
            if is_selected:
                color = self._selected_color
            else:
                color = self._unselected_color
            
            # Draw bar
            painter.fillRect(
                QRectF(x, y, bar_width - 1, bar_height),
                QBrush(color)
            )
            
            # Draw bar outline for selected
            if is_selected:
                painter.setPen(QPen(self._bar_color.darker(120), 1))
                painter.drawRect(QRectF(x, y, bar_width - 1, bar_height))
    
    def _is_bin_selected(self, bin_start: float, bin_end: float) -> bool:
        """Check if a bin is within the selection range."""
        if self._range_min is None or self._range_max is None:
            return True  # No selection = all selected
        
        # Bin is selected if it overlaps with selection range
        return not (bin_end <= self._range_min or bin_start >= self._range_max)
    
    def _draw_axes(self, painter: QPainter, rect: QRectF) -> None:
        """Draw axis lines and labels."""
        painter.setPen(QPen(self._axis_color, 2))
        
        # X axis
        painter.drawLine(
            QPointF(rect.left(), rect.bottom()),
            QPointF(rect.right(), rect.bottom())
        )
        
        # Y axis
        painter.drawLine(
            QPointF(rect.left(), rect.top()),
            QPointF(rect.left(), rect.bottom())
        )
        
        # X axis labels (min, max)
        if self._bin_edges:
            painter.setPen(QPen(self._text_color))
            font = painter.font()
            font.setPointSize(8)
            painter.setFont(font)
            
            min_val = self._bin_edges[0]
            max_val = self._bin_edges[-1]
            
            # Format numbers appropriately
            min_str = self._format_value(min_val)
            max_str = self._format_value(max_val)
            
            fm = QFontMetrics(font)
            
            # Min label (left)
            painter.drawText(
                QPointF(rect.left(), rect.bottom() + 15),
                min_str
            )
            
            # Max label (right)
            max_width = fm.horizontalAdvance(max_str)
            painter.drawText(
                QPointF(rect.right() - max_width, rect.bottom() + 15),
                max_str
            )
        
        # Y axis label (count)
        if self._bin_counts:
            max_count = max(self._bin_counts)
            painter.save()
            painter.translate(10, rect.center().y())
            painter.rotate(-90)
            painter.drawText(QPointF(0, 0), f"Count (max: {max_count:,})")
            painter.restore()
    
    def _format_value(self, value: float) -> str:
        """Format a value for display."""
        if abs(value) >= 1000:
            return f"{value:,.0f}"
        elif abs(value) >= 1:
            return f"{value:.1f}"
        else:
            return f"{value:.3f}"
    
    def _value_to_x(self, value: float, rect: QRectF) -> float:
        """Convert a data value to x coordinate."""
        if not self._bin_edges:
            return rect.left()
        
        data_min = self._bin_edges[0]
        data_max = self._bin_edges[-1]
        data_range = data_max - data_min
        
        if data_range == 0:
            return rect.left()
        
        return rect.left() + ((value - data_min) / data_range) * rect.width()
    
    def _x_to_value(self, x: float, rect: QRectF) -> float:
        """Convert an x coordinate to data value."""
        if not self._bin_edges:
            return 0
        
        data_min = self._bin_edges[0]
        data_max = self._bin_edges[-1]
        data_range = data_max - data_min
        
        rel_x = (x - rect.left()) / rect.width()
        return data_min + rel_x * data_range
    
    # === Mouse interaction ===
    
    def mousePressEvent(self, event) -> None:
        """Handle mouse press for range selection."""
        if event.button() == Qt.LeftButton and self._bin_edges:
            self._is_selecting = True
            self._selection_start_x = event.x()
            
            rect = self._get_draw_rect()
            self._range_min = self._x_to_value(event.x(), rect)
            self._range_max = self._range_min
            
            self.selection_started.emit()
            self.update()
    
    def mouseMoveEvent(self, event) -> None:
        """Handle mouse move for range selection."""
        if self._is_selecting and self._bin_edges:
            rect = self._get_draw_rect()
            current_value = self._x_to_value(event.x(), rect)
            start_value = self._x_to_value(self._selection_start_x, rect)
            
            # Ensure min < max
            self._range_min = min(start_value, current_value)
            self._range_max = max(start_value, current_value)
            
            # Clamp to data range
            data_min = self._bin_edges[0]
            data_max = self._bin_edges[-1]
            self._range_min = max(data_min, self._range_min)
            self._range_max = min(data_max, self._range_max)
            
            self.update()
    
    def mouseReleaseEvent(self, event) -> None:
        """Handle mouse release for range selection."""
        if event.button() == Qt.LeftButton and self._is_selecting:
            self._is_selecting = False
            
            if self._range_min is not None and self._range_max is not None:
                # Emit range change only if meaningful selection
                if abs(self._range_max - self._range_min) > 0.001:
                    self.range_changed.emit(self._range_min, self._range_max)
            
            self.selection_ended.emit()
    
    def mouseDoubleClickEvent(self, event) -> None:
        """Handle double-click to reset selection."""
        if event.button() == Qt.LeftButton:
            self.reset_selection()


class HistogramWidget(QWidget):
    """
    Complete histogram widget with canvas and info labels.
    
    EPIC-2 Feature: US-06 Histogram Visualization
    
    Features:
    - Histogram canvas with interactive selection
    - Summary statistics display
    - Sampled indicator for large rasters
    - Theme-aware styling
    
    Signals:
        range_changed(float, float): Emitted when selection range changes
        refresh_requested: Emitted when refresh is requested
    """
    
    range_changed = pyqtSignal(float, float)
    refresh_requested = pyqtSignal()
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the histogram widget."""
        super().__init__(parent)
        self._setup_ui()
        self._setup_connections()
    
    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # === Header with band info ===
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        self._band_label = QLabel("Band: -")
        self._band_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(self._band_label)
        
        header_layout.addStretch()
        
        self._sampled_label = QLabel("⚠ Sampled")
        self._sampled_label.setStyleSheet(
            "color: #e67e22; font-size: 10px; font-style: italic;"
        )
        self._sampled_label.setVisible(False)
        self._sampled_label.setToolTip(
            "Statistics computed from a sample of the raster for performance"
        )
        header_layout.addWidget(self._sampled_label)
        
        layout.addLayout(header_layout)
        
        # === Histogram canvas ===
        self._canvas = HistogramCanvas()
        layout.addWidget(self._canvas, 1)  # Stretch
        
        # === Selection info ===
        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.StyledPanel)
        info_layout = QHBoxLayout(info_frame)
        info_layout.setContentsMargins(8, 4, 8, 4)
        info_layout.setSpacing(16)
        
        # Selection range
        self._selection_label = QLabel("Selection: Full range")
        self._selection_label.setStyleSheet("font-size: 10px;")
        info_layout.addWidget(self._selection_label)
        
        info_layout.addStretch()
        
        # Pixel count in selection
        self._pixel_count_label = QLabel("Pixels: -")
        self._pixel_count_label.setStyleSheet("font-size: 10px;")
        info_layout.addWidget(self._pixel_count_label)
        
        layout.addWidget(info_frame)
        
        # === Hint ===
        hint_label = QLabel(
            "💡 Drag on histogram to select range. Double-click to reset."
        )
        hint_label.setStyleSheet(
            "color: palette(mid); font-size: 9px; font-style: italic;"
        )
        hint_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint_label)
    
    def _setup_connections(self) -> None:
        """Set up signal connections."""
        self._canvas.range_changed.connect(self._on_range_changed)
    
    def _on_range_changed(self, min_val: float, max_val: float) -> None:
        """Handle range change from canvas."""
        # Update selection label
        self._selection_label.setText(
            f"Selection: {self._format_value(min_val)} - {self._format_value(max_val)}"
        )
        
        # Calculate pixel count in selection
        if hasattr(self._canvas, '_histogram_data') and self._canvas._histogram_data:
            count = self._calculate_pixels_in_range(min_val, max_val)
            self._pixel_count_label.setText(f"Pixels: {count:,}")
        
        # Emit signal
        self.range_changed.emit(min_val, max_val)
    
    def _calculate_pixels_in_range(
        self,
        min_val: float,
        max_val: float
    ) -> int:
        """Calculate number of pixels in the selection range."""
        if not self._canvas._bin_counts or not self._canvas._bin_edges:
            return 0
        
        total = 0
        for i, count in enumerate(self._canvas._bin_counts):
            bin_start = self._canvas._bin_edges[i]
            bin_end = self._canvas._bin_edges[i + 1] if i + 1 < len(self._canvas._bin_edges) else bin_start
            
            # Check if bin overlaps with range
            if not (bin_end <= min_val or bin_start >= max_val):
                total += count
        
        return total
    
    def _format_value(self, value: float) -> str:
        """Format a value for display."""
        if abs(value) >= 1000:
            return f"{value:,.0f}"
        elif abs(value) >= 1:
            return f"{value:.2f}"
        else:
            return f"{value:.4f}"
    
    def set_histogram_data(
        self,
        data: 'HistogramData',
        band_name: str = "",
        is_sampled: bool = False
    ) -> None:
        """
        Set histogram data to display.
        
        Args:
            data: HistogramData from RasterPort
            band_name: Name of the band (e.g., "Band 1: Red")
            is_sampled: Whether data is from a sample
        """
        self._canvas.set_histogram_data(data)
        
        # Update labels
        self._band_label.setText(f"Band: {band_name}" if band_name else "Band: -")
        self._sampled_label.setVisible(is_sampled)
        
        # Reset selection info
        if data.bin_edges:
            self._selection_label.setText(
                f"Selection: {self._format_value(data.bin_edges[0])} - "
                f"{self._format_value(data.bin_edges[-1])}"
            )
            total_pixels = sum(data.counts)
            self._pixel_count_label.setText(f"Pixels: {total_pixels:,}")
        else:
            self._selection_label.setText("Selection: -")
            self._pixel_count_label.setText("Pixels: -")
    
    def set_selection_range(
        self,
        min_val: Optional[float],
        max_val: Optional[float]
    ) -> None:
        """
        Set the selection range on the histogram.
        
        Args:
            min_val: Minimum value of selection
            max_val: Maximum value of selection
        """
        self._canvas.set_selection_range(min_val, max_val)
        
        if min_val is not None and max_val is not None:
            self._selection_label.setText(
                f"Selection: {self._format_value(min_val)} - "
                f"{self._format_value(max_val)}"
            )
            count = self._calculate_pixels_in_range(min_val, max_val)
            self._pixel_count_label.setText(f"Pixels: {count:,}")
    
    def reset_selection(self) -> None:
        """Reset selection to full range."""
        self._canvas.reset_selection()
    
    def clear(self) -> None:
        """Clear the histogram display."""
        self._canvas.clear()
        self._band_label.setText("Band: -")
        self._sampled_label.setVisible(False)
        self._selection_label.setText("Selection: -")
        self._pixel_count_label.setText("Pixels: -")
    
    @property
    def selection_range(self) -> Tuple[Optional[float], Optional[float]]:
        """Get the current selection range."""
        return (self._canvas._range_min, self._canvas._range_max)

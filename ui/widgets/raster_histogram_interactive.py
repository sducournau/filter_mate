"""
RasterHistogramInteractiveWidget: Histogramme raster dessiné avec QPainter + sélection interactive.

- Calcule l'histogramme via l'API QGIS raster
- Affiche les barres avec QPainter (100% natif, aucune dépendance)
- Permet la sélection d'une plage min/max par glisser-déposer
- Synchronise la sélection avec les spinbox min/max (et vice-versa)

Auteur: FilterMate Team
Date: Janvier 2026
"""

import numpy as np
from typing import Optional, Tuple

from qgis.PyQt.QtCore import Qt, pyqtSignal, QRectF
from qgis.PyQt.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from qgis.PyQt.QtGui import QPainter, QColor, QPen, QBrush

from qgis.core import QgsRasterLayer, QgsRasterBandStats

from ...infrastructure.logging import get_logger

logger = get_logger(__name__)


class RasterHistogramInteractiveWidget(QWidget):
    """
    Widget histogramme raster interactif dessiné avec QPainter.
    
    Signaux:
        rangeChanged(float, float): Émis lors du drag (temps réel)
        rangeSelectionFinished(float, float): Émis à la fin du drag
    """
    rangeChanged = pyqtSignal(float, float)
    rangeSelectionFinished = pyqtSignal(float, float)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._layer: Optional[QgsRasterLayer] = None
        self._band_index: int = 1
        self._histogram_data: Optional[np.ndarray] = None
        self._bin_edges: Optional[np.ndarray] = None
        self._data_min: float = 0.0
        self._data_max: float = 1.0
        self._selected_min: float = 0.0
        self._selected_max: float = 1.0
        
        # Drag state
        self._dragging = False
        self._drag_start_x: Optional[int] = None
        self._drag_current_x: Optional[int] = None
        
        self._setup_ui()
        self.setMouseTracking(True)

    def _setup_ui(self):
        """Setup the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # Canvas pour l'histogramme
        self._canvas = HistogramCanvas(self)
        self._canvas.setMinimumHeight(60)
        self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self._canvas)
        
        # Info label
        self._info_label = QLabel(self.tr("Select range on histogram"))
        self._info_label.setAlignment(Qt.AlignCenter)
        self._info_label.setStyleSheet("font-size: 9px; color: #666;")
        layout.addWidget(self._info_label)
        
        # Connect canvas signals
        self._canvas.selectionChanged.connect(self._on_canvas_selection_changed)
        self._canvas.selectionFinished.connect(self._on_canvas_selection_finished)
        
        logger.debug("RasterHistogramInteractiveWidget UI setup complete")

    def set_layer(self, layer: QgsRasterLayer, band_index: int = 1):
        """Set the raster layer and band to display histogram for."""
        self._layer = layer
        self._band_index = band_index
        
        if layer is None:
            self._clear_histogram()
            return
        
        self._info_label.setText(self.tr("Computing histogram..."))
        from qgis.PyQt.QtWidgets import QApplication
        QApplication.processEvents()
        
        self._compute_histogram()
        self._update_canvas()
        
    def _compute_histogram(self):
        """Compute histogram data from the raster layer."""
        if not self._layer or not self._layer.isValid():
            self._histogram_data = None
            return
        
        try:
            provider = self._layer.dataProvider()
            if not provider:
                logger.warning("No data provider for histogram")
                return
            
            # Get band statistics
            stats = provider.bandStatistics(
                self._band_index,
                QgsRasterBandStats.Min | QgsRasterBandStats.Max,
                self._layer.extent(),
                250000  # Sample size
            )
            
            self._data_min = stats.minimumValue
            self._data_max = stats.maximumValue
            
            if self._data_min >= self._data_max or not np.isfinite(self._data_min) or not np.isfinite(self._data_max):
                logger.warning(f"Invalid stats: min={self._data_min}, max={self._data_max}")
                self._histogram_data = None
                return
            
            # Get histogram
            histogram = provider.histogram(
                self._band_index,
                256,
                self._data_min,
                self._data_max,
                self._layer.extent(),
                250000
            )
            
            if histogram and hasattr(histogram, 'histogramVector'):
                hist_vector = histogram.histogramVector
                if hist_vector and len(hist_vector) > 0 and sum(hist_vector) > 0:
                    self._histogram_data = np.array(hist_vector, dtype=float)
                    self._bin_edges = np.linspace(self._data_min, self._data_max, len(self._histogram_data) + 1)
                    self._selected_min = self._data_min
                    self._selected_max = self._data_max
                    logger.debug(f"Histogram computed: {len(self._histogram_data)} bins")
                else:
                    logger.warning("Empty histogram from provider")
                    self._histogram_data = None
            else:
                logger.warning("Failed to get histogram")
                self._histogram_data = None
                
        except Exception as e:
            logger.error(f"Error computing histogram: {e}")
            self._histogram_data = None

    def _update_canvas(self):
        """Update the canvas with current histogram data."""
        self._canvas.set_histogram_data(
            self._histogram_data,
            self._data_min,
            self._data_max,
            self._selected_min,
            self._selected_max
        )
        if self._histogram_data is not None:
            self._update_info_label()
        else:
            self._info_label.setText(self.tr("Could not compute histogram"))

    def _clear_histogram(self):
        """Clear the histogram display."""
        self._histogram_data = None
        self._canvas.set_histogram_data(None, 0, 1, 0, 1)
        self._info_label.setText(self.tr("No raster layer selected"))

    def _on_canvas_selection_changed(self, min_val: float, max_val: float):
        """Handle real-time selection changes."""
        self._selected_min = min_val
        self._selected_max = max_val
        self._update_info_label()
        self.rangeChanged.emit(min_val, max_val)

    def _on_canvas_selection_finished(self, min_val: float, max_val: float):
        """Handle selection finished."""
        self._selected_min = min_val
        self._selected_max = max_val
        self._update_info_label()
        self.rangeSelectionFinished.emit(min_val, max_val)

    def _update_info_label(self):
        """Update info label with current selection."""
        if self._histogram_data is not None and self._layer:
            self._info_label.setText(
                f"Range: [{self._selected_min:.1f} - {self._selected_max:.1f}]"
            )

    def showEvent(self, event):
        """v5.11: Force refresh when widget becomes visible."""
        super().showEvent(event)
        # Force canvas update when becoming visible
        if self._canvas:
            self._canvas.update()
        logger.debug("RasterHistogramInteractiveWidget shown, canvas refreshed")

    def set_range(self, min_val: float, max_val: float):
        """Set the selection range programmatically."""
        self._selected_min = max(min_val, self._data_min)
        self._selected_max = min(max_val, self._data_max)
        self._canvas.set_selection(self._selected_min, self._selected_max)
        self._update_info_label()

    def get_range(self) -> Tuple[float, float]:
        """Get the current selection range."""
        return (self._selected_min, self._selected_max)


class HistogramCanvas(QWidget):
    """Canvas widget that draws the histogram and handles mouse interaction."""
    
    selectionChanged = pyqtSignal(float, float)
    selectionFinished = pyqtSignal(float, float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._histogram_data: Optional[np.ndarray] = None
        self._data_min: float = 0.0
        self._data_max: float = 1.0
        self._selected_min: float = 0.0
        self._selected_max: float = 1.0
        
        # Drag state
        self._dragging = False
        self._drag_start_x: Optional[int] = None
        self._drag_current_x: Optional[int] = None
        
        # Margins
        self._margin_left = 5
        self._margin_right = 5
        self._margin_top = 5
        self._margin_bottom = 5
        
        self.setMinimumHeight(60)
        self.setMouseTracking(True)
        
    def set_histogram_data(self, data, data_min, data_max, sel_min, sel_max):
        """Set histogram data and trigger repaint."""
        self._histogram_data = data
        self._data_min = data_min
        self._data_max = data_max
        self._selected_min = sel_min
        self._selected_max = sel_max
        logger.debug(f"HistogramCanvas: set_histogram_data called, data={'None' if data is None else f'{len(data)} bins'}")
        self.update()
        
    def set_selection(self, sel_min, sel_max):
        """Update selection and repaint."""
        self._selected_min = sel_min
        self._selected_max = sel_max
        self.update()

    def paintEvent(self, event):
        """Draw the histogram and selection overlay."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        
        # v5.11: Log paint event for debugging
        logger.debug(f"HistogramCanvas paintEvent: rect={rect.width()}x{rect.height()}, data={'Yes' if self._histogram_data is not None else 'No'}")
        
        plot_rect = QRectF(
            self._margin_left,
            self._margin_top,
            rect.width() - self._margin_left - self._margin_right,
            rect.height() - self._margin_top - self._margin_bottom
        )
        
        # Background - use a visible color for debugging
        painter.fillRect(rect, QColor(245, 245, 250))
        
        # Draw border to see the widget bounds
        painter.setPen(QPen(QColor(200, 200, 210), 1))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
        
        if self._histogram_data is None or len(self._histogram_data) == 0:
            # No data message
            painter.setPen(QColor(120, 120, 130))
            font = painter.font()
            font.setPointSize(9)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignCenter, "Click to compute histogram\nor select a raster layer")
            painter.end()
            return
        
        # Draw histogram bars
        num_bins = len(self._histogram_data)
        bar_width = plot_rect.width() / num_bins
        max_val = np.max(self._histogram_data)
        if max_val == 0:
            max_val = 1
        
        # Histogram color
        bar_color = QColor(100, 149, 237, 200)  # Cornflower blue
        bar_pen = QPen(QColor(70, 130, 180), 0.5)
        painter.setPen(bar_pen)
        painter.setBrush(QBrush(bar_color))
        
        for i, count in enumerate(self._histogram_data):
            bar_height = (count / max_val) * plot_rect.height()
            x = plot_rect.left() + i * bar_width
            y = plot_rect.bottom() - bar_height
            painter.drawRect(QRectF(x, y, bar_width - 0.5, bar_height))
        
        # Draw selection overlay
        sel_x1 = self._value_to_x(self._selected_min, plot_rect)
        sel_x2 = self._value_to_x(self._selected_max, plot_rect)
        
        selection_rect = QRectF(
            min(sel_x1, sel_x2),
            plot_rect.top(),
            abs(sel_x2 - sel_x1),
            plot_rect.height()
        )
        
        # Selection fill
        sel_brush = QBrush(QColor(255, 165, 0, 80))  # Orange transparent
        painter.fillRect(selection_rect, sel_brush)
        
        # Selection borders
        sel_pen = QPen(QColor(255, 140, 0), 2)
        painter.setPen(sel_pen)
        painter.drawLine(int(sel_x1), int(plot_rect.top()), int(sel_x1), int(plot_rect.bottom()))
        painter.drawLine(int(sel_x2), int(plot_rect.top()), int(sel_x2), int(plot_rect.bottom()))
        
        # Draw drag preview if dragging
        if self._dragging and self._drag_start_x is not None and self._drag_current_x is not None:
            drag_rect = QRectF(
                min(self._drag_start_x, self._drag_current_x),
                plot_rect.top(),
                abs(self._drag_current_x - self._drag_start_x),
                plot_rect.height()
            )
            drag_brush = QBrush(QColor(0, 120, 255, 60))
            painter.fillRect(drag_rect, drag_brush)
            drag_pen = QPen(QColor(0, 120, 255), 1, Qt.DashLine)
            painter.setPen(drag_pen)
            painter.drawRect(drag_rect)
        
        painter.end()

    def mousePressEvent(self, event):
        """Start selection drag."""
        if event.button() == Qt.LeftButton and self._histogram_data is not None:
            self._dragging = True
            self._drag_start_x = event.pos().x()
            self._drag_current_x = event.pos().x()
            self.update()

    def mouseMoveEvent(self, event):
        """Update drag preview."""
        if self._dragging:
            self._drag_current_x = event.pos().x()
            self.update()

    def mouseReleaseEvent(self, event):
        """Finish selection and emit signal."""
        if self._dragging:
            self._dragging = False
            self._drag_current_x = event.pos().x()
            
            # Convert to values
            rect = self.rect()
            plot_rect = QRectF(
                self._margin_left,
                self._margin_top,
                rect.width() - self._margin_left - self._margin_right,
                rect.height() - self._margin_top - self._margin_bottom
            )
            
            val1 = self._x_to_value(self._drag_start_x, plot_rect)
            val2 = self._x_to_value(self._drag_current_x, plot_rect)
            
            self._selected_min = min(val1, val2)
            self._selected_max = max(val1, val2)
            
            self._drag_start_x = None
            self._drag_current_x = None
            
            self.update()
            self.selectionChanged.emit(self._selected_min, self._selected_max)
            self.selectionFinished.emit(self._selected_min, self._selected_max)

    def _value_to_x(self, value: float, plot_rect: QRectF) -> float:
        """Convert data value to x pixel coordinate."""
        if self._data_max == self._data_min:
            return plot_rect.left()
        ratio = (value - self._data_min) / (self._data_max - self._data_min)
        ratio = max(0, min(1, ratio))
        return plot_rect.left() + ratio * plot_rect.width()

    def _x_to_value(self, x: float, plot_rect: QRectF) -> float:
        """Convert x pixel coordinate to data value."""
        if plot_rect.width() == 0:
            return self._data_min
        ratio = (x - plot_rect.left()) / plot_rect.width()
        ratio = max(0, min(1, ratio))
        return self._data_min + ratio * (self._data_max - self._data_min)

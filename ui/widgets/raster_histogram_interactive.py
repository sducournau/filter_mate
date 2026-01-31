"""
RasterHistogramInteractiveWidget: Histogramme raster natif QGIS avec sélection interactive de plage (drag & drop).

- Affiche l'histogramme via QgsHistogramWidget
- Permet la sélection d'une plage min/max par glisser-déposer
- Synchronise la sélection avec les spinbox min/max (et vice-versa)
- 100% natif, aucune dépendance externe

Auteur: FilterMate Team
Date: Janvier 2026
"""

from qgis.PyQt.QtCore import Qt, pyqtSignal, QRect, QPoint
from qgis.PyQt.QtWidgets import QWidget, QVBoxLayout, QLabel
from qgis.PyQt.QtGui import QPainter, QColor, QPen, QBrush
from qgis.gui import QgsHistogramWidget
from qgis.core import QgsRasterLayer

class RasterHistogramInteractiveWidget(QWidget):
    """
    Widget histogramme raster natif QGIS avec sélection interactive de plage.
    """
    rangeChanged = pyqtSignal(float, float)
    rangeSelectionFinished = pyqtSignal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layer = None
        self._band_index = 1
        self._histogram_widget = QgsHistogramWidget(self)
        self._histogram_widget.setMinimumHeight(60)
        self._histogram_widget.setSizePolicy(self.sizePolicy())
        self._info_label = QLabel("Histogram (QGIS natif, interactif)")
        self._info_label.setAlignment(Qt.AlignCenter)
        self._info_label.setStyleSheet("font-size: 9px; color: #666;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._histogram_widget)
        layout.addWidget(self._info_label)
        self.setLayout(layout)
        # Sélection interactive
        self._selecting = False
        self._selection_start = None  # QPoint
        self._selection_end = None    # QPoint
        self._selected_min = None
        self._selected_max = None
        self._data_min = None
        self._data_max = None
        self.setMouseTracking(True)

    def set_layer(self, layer: QgsRasterLayer, band_index: int = 1):
        self._layer = layer
        self._band_index = band_index
        if layer is None:
            self._histogram_widget.clear()
            self._info_label.setText("No raster layer selected")
            self._data_min = None
            self._data_max = None
            self._selected_min = None
            self._selected_max = None
            self.update()
            return
        self._histogram_widget.setRasterLayer(layer, band_index)
        # Récupère min/max pour conversion pixel <-> valeur
        provider = layer.dataProvider()
        stats = provider.bandStatistics(band_index)
        self._data_min = stats.minimumValue
        self._data_max = stats.maximumValue
        # Par défaut, sélectionne toute la plage
        self._selected_min = self._data_min
        self._selected_max = self._data_max
        self._info_label.setText(f"Histogram: {layer.name()} (Band {band_index})")
        self.update()

    def set_range(self, min_val: float, max_val: float):
        """Permet de synchroniser la sélection depuis l'extérieur (spinbox)."""
        if self._data_min is None or self._data_max is None:
            return
        self._selected_min = max(min_val, self._data_min)
        self._selected_max = min(max_val, self._data_max)
        self.update()

    def get_range(self):
        return (self._selected_min, self._selected_max)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._data_min is None or self._data_max is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # Calcule la zone de l'histogramme
        hist_rect = self._histogram_widget.geometry()
        if self._selected_min is not None and self._selected_max is not None:
            # Conversion valeur -> pixel
            x1 = self._value_to_pixel(self._selected_min, hist_rect)
            x2 = self._value_to_pixel(self._selected_max, hist_rect)
            sel_rect = QRect(min(x1, x2), hist_rect.top(), abs(x2 - x1), hist_rect.height())
            painter.setBrush(QBrush(QColor(255, 165, 0, 80)))  # Orange transparent
            painter.setPen(QPen(QColor(255, 140, 0), 2))
            painter.drawRect(sel_rect)
        # Si sélection en cours (drag)
        if self._selecting and self._selection_start and self._selection_end:
            x1 = self._selection_start.x()
            x2 = self._selection_end.x()
            sel_rect = QRect(min(x1, x2), hist_rect.top(), abs(x2 - x1), hist_rect.height())
            painter.setBrush(QBrush(QColor(0, 120, 255, 60)))
            painter.setPen(QPen(QColor(0, 120, 255), 1, Qt.DashLine))
            painter.drawRect(sel_rect)
        painter.end()

    def mousePressEvent(self, event):
        hist_rect = self._histogram_widget.geometry()
        if event.button() == Qt.LeftButton and hist_rect.contains(event.pos()):
            self._selecting = True
            self._selection_start = event.pos()
            self._selection_end = event.pos()
            self.update()

    def mouseMoveEvent(self, event):
        if self._selecting:
            self._selection_end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if self._selecting:
            self._selection_end = event.pos()
            self._selecting = False
            # Calcule min/max sélectionnés
            hist_rect = self._histogram_widget.geometry()
            min_val = self._pixel_to_value(self._selection_start.x(), hist_rect)
            max_val = self._pixel_to_value(self._selection_end.x(), hist_rect)
            self._selected_min = min(min_val, max_val)
            self._selected_max = max(min_val, max_val)
            self.rangeChanged.emit(self._selected_min, self._selected_max)
            self.rangeSelectionFinished.emit(self._selected_min, self._selected_max)
            self.update()

    def _value_to_pixel(self, value, hist_rect):
        # Convertit une valeur raster en position X pixel dans l'histogramme
        if self._data_min is None or self._data_max is None:
            return hist_rect.left()
        ratio = (value - self._data_min) / (self._data_max - self._data_min) if self._data_max > self._data_min else 0
        return int(hist_rect.left() + ratio * hist_rect.width())

    def _pixel_to_value(self, x, hist_rect):
        # Convertit une position X pixel en valeur raster
        if self._data_min is None or self._data_max is None or hist_rect.width() == 0:
            return self._data_min or 0
        ratio = (x - hist_rect.left()) / hist_rect.width()
        ratio = min(max(ratio, 0), 1)
        return self._data_min + ratio * (self._data_max - self._data_min)

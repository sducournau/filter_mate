"""
Note: Pixel Picker Map Tool for FilterMate.

A QGIS map tool that allows users to click on a raster layer to pick pixel values
for use in raster filtering. Supports single click (exact value) and rectangle
drag (value range from area).

Author: FilterMate Team
Date: January 2026
"""

from typing import Optional, Tuple, List

from qgis.PyQt.QtCore import Qt, pyqtSignal, QPoint
from qgis.PyQt.QtGui import QCursor, QColor
from qgis.PyQt.QtWidgets import QApplication

from qgis.core import (
    QgsRasterLayer,
    QgsPointXY,
    QgsRectangle,
    QgsCoordinateTransform,
    QgsProject,
    Qgis,
    QgsWkbTypes
)
from qgis.gui import QgsMapTool, QgsMapCanvas, QgsRubberBand

# Compatibility: Qgis.GeometryType.Polygon requires QGIS 3.30+
# Fall back to QgsWkbTypes.PolygonGeometry for older versions.
try:
    _POLYGON_GEOM = Qgis.GeometryType.Polygon
except AttributeError:
    _POLYGON_GEOM = QgsWkbTypes.PolygonGeometry

from ...infrastructure.logging import get_logger

logger = get_logger(__name__)


class RasterPixelPickerTool(QgsMapTool):
    """Map tool for picking pixel values from raster layers.
    
    Features:
    - Single click: Pick value at point → set min = max = value
    - Click + drag: Pick rectangle → set min/max from area statistics
    - Ctrl + click: Extend current range with new value
    - Shift + click: Show all bands values (multi-band info)
    - Escape: Deactivate tool
    
    Signals:
        valuesPicked(float, float): Emitted with (min, max) values
        valuePicked(float): Emitted with single value (click)
        allBandsPicked(list): Emitted with values from all bands
        pickingStarted(): Emitted when tool is activated
        pickingFinished(): Emitted when tool is deactivated
    """
    
    valuesPicked = pyqtSignal(float, float)  # min, max
    valuePicked = pyqtSignal(float)  # single value
    pixelPicked = pyqtSignal(float, float, float)  # value, x, y coordinates
    allBandsPicked = pyqtSignal(list)  # all bands values
    pickingStarted = pyqtSignal()
    pickingFinished = pyqtSignal()
    
    def __init__(self, canvas: QgsMapCanvas, parent=None):
        super().__init__(canvas)
        self._canvas = canvas
        self._parent = parent
        self._layer: Optional[QgsRasterLayer] = None
        self._band_index: int = 1
        self._is_dragging: bool = False
        self._start_point: Optional[QgsPointXY] = None
        self._current_min: float = 0.0
        self._current_max: float = 0.0
        
        # Rubber band for rectangle selection
        self._rubber_band = QgsRubberBand(canvas, _POLYGON_GEOM)
        self._rubber_band.setColor(QColor(255, 165, 0, 100))  # Orange
        self._rubber_band.setStrokeColor(QColor(255, 140, 0))
        self._rubber_band.setWidth(2)
        
        # Custom cursor
        self._setup_cursor()
        
        logger.debug("RasterPixelPickerTool initialized")
    
    def _setup_cursor(self):
        """Setup custom crosshair cursor for the tool."""
        # Use built-in crosshair cursor
        self.setCursor(QCursor(Qt.CrossCursor))
    
    def set_layer(self, layer: QgsRasterLayer, band_index: int = 1):
        """Set the raster layer to pick values from.
        
        Args:
            layer: QgsRasterLayer to sample
            band_index: Band index (1-based)
        """
        self._layer = layer
        self._band_index = band_index
        logger.debug(f"PixelPicker: Layer set to '{layer.name() if layer else 'None'}', band {band_index}")
    
    def set_current_range(self, min_val: float, max_val: float):
        """Set current range for Ctrl+click extend mode.
        
        Args:
            min_val: Current minimum value
            max_val: Current maximum value
        """
        self._current_min = min_val
        self._current_max = max_val
    
    def activate(self):
        """Activate the map tool."""
        super().activate()
        self._rubber_band.reset()
        self.pickingStarted.emit()
        logger.info("PixelPicker: Tool activated")
    
    def deactivate(self):
        """Deactivate the map tool."""
        self._rubber_band.reset()
        self._is_dragging = False
        self._start_point = None
        self.pickingFinished.emit()
        super().deactivate()
        logger.info("PixelPicker: Tool deactivated")
    
    def canvasPressEvent(self, event):
        """Handle mouse press on canvas."""
        if event.button() != Qt.LeftButton:
            return
        
        if not self._layer or not self._layer.isValid():
            logger.warning("PixelPicker: No valid raster layer set")
            return
        
        # Get map point
        self._start_point = self.toMapCoordinates(event.pos())
        self._is_dragging = True
        self._rubber_band.reset(_POLYGON_GEOM)
    
    def canvasMoveEvent(self, event):
        """Handle mouse move on canvas (for drag selection)."""
        if not self._is_dragging or not self._start_point:
            return
        
        # Update rubber band rectangle
        current_point = self.toMapCoordinates(event.pos())
        self._update_rubber_band(self._start_point, current_point)
    
    def canvasReleaseEvent(self, event):
        """Handle mouse release on canvas."""
        if event.button() != Qt.LeftButton:
            return
        
        if not self._layer or not self._layer.isValid():
            return
        
        end_point = self.toMapCoordinates(event.pos())
        modifiers = QApplication.keyboardModifiers()
        
        # Check if it's a click or a drag
        if self._start_point:
            distance = self._start_point.distance(end_point)
            map_units_per_pixel = self._canvas.mapUnitsPerPixel()
            
            if distance < map_units_per_pixel * 5:  # Small movement = click
                # Single click
                self._handle_point_pick(end_point, modifiers)
            else:
                # Rectangle drag
                self._handle_rectangle_pick(self._start_point, end_point, modifiers)
        
        # Reset state
        self._rubber_band.reset()
        self._is_dragging = False
        self._start_point = None
    
    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key_Escape:
            # Deactivate tool
            self._canvas.unsetMapTool(self)
    
    def _handle_point_pick(self, point: QgsPointXY, modifiers):
        """Handle single point pick.
        
        Args:
            point: Map coordinates of click
            modifiers: Keyboard modifiers
        """
        try:
            value = self._sample_raster_at_point(point)
            
            if value is None:
                logger.debug("PixelPicker: No data at click point")
                return
            
            if modifiers & Qt.ShiftModifier:
                # Shift+click: Get all bands
                all_values = self._sample_all_bands_at_point(point)
                self.allBandsPicked.emit(all_values)
                logger.debug(f"PixelPicker: All bands values: {all_values}")
                
            elif modifiers & Qt.ControlModifier:
                # Ctrl+click: Extend range
                new_min = min(self._current_min, value)
                new_max = max(self._current_max, value)
                self.valuesPicked.emit(new_min, new_max)
                logger.debug(f"PixelPicker: Range extended to [{new_min:.2f}, {new_max:.2f}]")
                
            else:
                # Normal click: Set exact value
                self.valuePicked.emit(value)
                self.pixelPicked.emit(value, point.x(), point.y())
                self.valuesPicked.emit(value, value)
                logger.debug(f"PixelPicker: Value picked: {value:.2f} at ({point.x():.2f}, {point.y():.2f})")
                
        except Exception as e:
            logger.error(f"PixelPicker: Error picking point value: {e}")
    
    def _handle_rectangle_pick(self, start_point: QgsPointXY, end_point: QgsPointXY, modifiers):
        """Handle rectangle area pick.
        
        Args:
            start_point: Start corner of rectangle
            end_point: End corner of rectangle
            modifiers: Keyboard modifiers
        """
        try:
            # Create rectangle
            rect = QgsRectangle(start_point, end_point)
            
            # Get statistics for the rectangle
            min_val, max_val = self._get_rectangle_stats(rect)
            
            if min_val is None or max_val is None:
                logger.debug("PixelPicker: No data in selected rectangle")
                return
            
            if modifiers & Qt.ControlModifier:
                # Ctrl+drag: Extend range
                min_val = min(self._current_min, min_val)
                max_val = max(self._current_max, max_val)
            
            self.valuesPicked.emit(min_val, max_val)
            logger.debug(f"PixelPicker: Rectangle range: [{min_val:.2f}, {max_val:.2f}]")
            
        except Exception as e:
            logger.error(f"PixelPicker: Error picking rectangle values: {e}")
    
    def _sample_raster_at_point(self, point: QgsPointXY) -> Optional[float]:
        """Sample raster value at a point.
        
        Args:
            point: Map coordinates
            
        Returns:
            Pixel value or None if no data
        """
        if not self._layer:
            return None
        
        # Transform point to layer CRS if needed
        layer_crs = self._layer.crs()
        canvas_crs = self._canvas.mapSettings().destinationCrs()
        
        if layer_crs != canvas_crs:
            transform = QgsCoordinateTransform(canvas_crs, layer_crs, QgsProject.instance())
            point = transform.transform(point)
        
        # Sample the raster
        provider = self._layer.dataProvider()
        if not provider:
            return None
        
        # Check if point is within layer extent
        if not self._layer.extent().contains(point):
            return None
        
        # Get the value
        result = provider.sample(point, self._band_index)
        
        if result[1]:  # result is (value, isValid)
            return result[0]
        return None
    
    def _sample_all_bands_at_point(self, point: QgsPointXY) -> List[Optional[float]]:
        """Sample all bands at a point.
        
        Args:
            point: Map coordinates
            
        Returns:
            List of values for each band (None for no data)
        """
        if not self._layer:
            return []
        
        # Transform point to layer CRS if needed
        layer_crs = self._layer.crs()
        canvas_crs = self._canvas.mapSettings().destinationCrs()
        
        if layer_crs != canvas_crs:
            transform = QgsCoordinateTransform(canvas_crs, layer_crs, QgsProject.instance())
            point = transform.transform(point)
        
        provider = self._layer.dataProvider()
        if not provider:
            return []
        
        # Check extent
        if not self._layer.extent().contains(point):
            return []
        
        # Sample all bands
        values = []
        for band in range(1, self._layer.bandCount() + 1):
            result = provider.sample(point, band)
            if result[1]:
                values.append(result[0])
            else:
                values.append(None)
        
        return values
    
    def _get_rectangle_stats(self, rect: QgsRectangle) -> Tuple[Optional[float], Optional[float]]:
        """Get min/max statistics for a rectangle area.
        
        Args:
            rect: Rectangle in map coordinates
            
        Returns:
            Tuple of (min, max) values or (None, None) if no data
        """
        if not self._layer:
            return (None, None)
        
        # Transform rectangle to layer CRS if needed
        layer_crs = self._layer.crs()
        canvas_crs = self._canvas.mapSettings().destinationCrs()
        
        if layer_crs != canvas_crs:
            transform = QgsCoordinateTransform(canvas_crs, layer_crs, QgsProject.instance())
            rect = transform.transformBoundingBox(rect)
        
        # Intersect with layer extent
        layer_extent = self._layer.extent()
        rect = rect.intersect(layer_extent)
        
        if rect.isEmpty():
            return (None, None)
        
        # Get statistics for the rectangle
        from qgis.core import QgsRasterBandStats
        try:
            from qgis.core import Qgis
            _stat_min_max = Qgis.RasterBandStatistic.Min | Qgis.RasterBandStatistic.Max
        except AttributeError:
            _stat_min_max = QgsRasterBandStats.Min | QgsRasterBandStats.Max

        provider = self._layer.dataProvider()
        if not provider:
            return (None, None)

        stats = provider.bandStatistics(
            self._band_index,
            _stat_min_max,
            rect,
            0  # Sample size
        )
        
        return (stats.minimumValue, stats.maximumValue)
    
    def _update_rubber_band(self, start_point: QgsPointXY, end_point: QgsPointXY):
        """Update rubber band rectangle display.
        
        Args:
            start_point: Start corner
            end_point: Current corner
        """
        self._rubber_band.reset(_POLYGON_GEOM)
        
        # Create rectangle corners
        self._rubber_band.addPoint(QgsPointXY(start_point.x(), start_point.y()), False)
        self._rubber_band.addPoint(QgsPointXY(end_point.x(), start_point.y()), False)
        self._rubber_band.addPoint(QgsPointXY(end_point.x(), end_point.y()), False)
        self._rubber_band.addPoint(QgsPointXY(start_point.x(), end_point.y()), True)
        
        self._rubber_band.show()

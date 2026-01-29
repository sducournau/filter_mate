# -*- coding: utf-8 -*-
"""
FilterMate Pixel Picker Map Tool.

EPIC-3: Raster-Vector Integration
Feature: Pick from Map (Pipette) 🔬

Provides a QgsMapTool for capturing pixel values from the map canvas
to use as filter criteria. Supports single-click, drag selection,
Ctrl+click to extend range, and Shift+click for multi-band sampling.

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional, List, Dict, TYPE_CHECKING

from qgis.PyQt.QtCore import Qt, pyqtSignal, QRectF, QPointF
from qgis.PyQt.QtWidgets import QApplication
from qgis.PyQt.QtGui import QCursor, QColor, QPixmap

try:
    from qgis.gui import QgsMapTool, QgsMapCanvas, QgsRubberBand
    from qgis.core import (
        QgsPointXY,
        QgsRasterLayer,
        QgsRectangle,
        QgsCoordinateReferenceSystem,
        QgsCoordinateTransform,
        QgsProject,
        QgsRasterDataProvider,
        QgsWkbTypes,
    )
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False
    QgsMapTool = object  # Fallback for type hints

if TYPE_CHECKING:
    pass

logger = logging.getLogger('FilterMate.UI.PixelPickerMapTool')


def create_pipette_cursor() -> QCursor:
    """
    Create a pipette/dropper cursor for the pick mode.
    
    Returns:
        QCursor: Custom pipette cursor
    """
    # Create a simple pipette cursor using built-in crosshair
    # In a real implementation, you might use a custom pixmap
    return QCursor(Qt.CrossCursor)


class PixelPickerMapTool(QgsMapTool):
    """
    Map tool for picking pixel values from raster layers.
    
    EPIC-3: Pick from Map (Pipette) 🔬
    
    Features:
    - Single click: Capture single pixel value
    - Click + drag: Capture min/max from rectangle selection
    - Ctrl + click: Extend existing range with new value
    - Shift + click: Multi-band sampling (shows all band values)
    
    Signals:
        value_picked: Emitted when a single pixel value is picked (value)
        range_picked: Emitted when a value range is picked (min, max)
        extend_requested: Emitted when Ctrl+click requests range extension (value)
        multi_band_picked: Emitted for multi-band sampling (band_values dict)
        pick_finished: Emitted when picking operation completes
        pick_cancelled: Emitted when picking is cancelled (Esc)
    """
    
    # Signals
    value_picked = pyqtSignal(float)  # Single value
    range_picked = pyqtSignal(float, float)  # Min, max from rectangle
    extend_requested = pyqtSignal(float)  # Value to extend range with
    multi_band_picked = pyqtSignal(dict)  # {band_number: value}
    pick_finished = pyqtSignal()
    pick_cancelled = pyqtSignal()
    
    def __init__(
        self,
        canvas: 'QgsMapCanvas',
        layer: Optional['QgsRasterLayer'] = None,
        band: int = 1,
        parent: Optional[object] = None
    ) -> None:
        """
        Initialize the pixel picker map tool.
        
        Args:
            canvas: QgsMapCanvas to operate on
            layer: Target raster layer for value extraction
            band: Band number to sample (1-indexed)
            parent: Optional parent object
        """
        super().__init__(canvas)
        self._canvas = canvas
        self._layer = layer
        self._band = band
        
        # Interaction state
        self._is_dragging = False
        self._drag_start_point: Optional[QgsPointXY] = None
        self._drag_start_pixel: Optional[QPointF] = None
        
        # Rubber band for rectangle selection
        self._rubber_band: Optional['QgsRubberBand'] = None
        self._setup_rubber_band()
        
        # Set custom cursor
        self.setCursor(create_pipette_cursor())
        
        logger.debug(f"PixelPickerMapTool initialized for band {band}")
    
    def _setup_rubber_band(self) -> None:
        """Set up the rubber band for rectangle selection."""
        if not QGIS_AVAILABLE:
            return
        
        self._rubber_band = QgsRubberBand(
            self._canvas, QgsWkbTypes.PolygonGeometry
        )
        self._rubber_band.setColor(QColor(0, 120, 215, 50))  # Semi-transparent blue
        self._rubber_band.setStrokeColor(QColor(0, 120, 215))
        self._rubber_band.setWidth(2)
        self._rubber_band.setLineStyle(Qt.DashLine)
    
    def set_layer(self, layer: Optional['QgsRasterLayer']) -> None:
        """
        Set the target raster layer.
        
        Args:
            layer: QgsRasterLayer to sample values from
        """
        self._layer = layer
        logger.debug(f"Picker layer set to: {layer.name() if layer else 'None'}")
    
    def set_band(self, band: int) -> None:
        """
        Set the band number to sample.
        
        Args:
            band: Band number (1-indexed)
        """
        self._band = band
        logger.debug(f"Picker band set to: {band}")
    
    def canvasPressEvent(self, event) -> None:
        """Handle mouse press event."""
        if event.button() != Qt.LeftButton:
            return
        
        # Start potential drag
        self._is_dragging = True
        self._drag_start_point = self.toMapCoordinates(event.pos())
        self._drag_start_pixel = QPointF(event.pos())
        
        # Clear rubber band
        if self._rubber_band:
            self._rubber_band.reset(QgsWkbTypes.PolygonGeometry)
    
    def canvasMoveEvent(self, event) -> None:
        """Handle mouse move event during drag."""
        if not self._is_dragging or self._drag_start_point is None:
            return
        
        # Check if we've moved enough to consider it a drag
        current_pixel = QPointF(event.pos())
        dx = abs(current_pixel.x() - self._drag_start_pixel.x())
        dy = abs(current_pixel.y() - self._drag_start_pixel.y())
        
        if dx < 5 and dy < 5:
            return  # Not a significant drag yet
        
        # Update rubber band rectangle
        current_point = self.toMapCoordinates(event.pos())
        
        if self._rubber_band:
            self._rubber_band.reset(QgsWkbTypes.PolygonGeometry)
            
            rect = QgsRectangle(self._drag_start_point, current_point)
            self._rubber_band.addPoint(
                QgsPointXY(rect.xMinimum(), rect.yMinimum()), False
            )
            self._rubber_band.addPoint(
                QgsPointXY(rect.xMinimum(), rect.yMaximum()), False
            )
            self._rubber_band.addPoint(
                QgsPointXY(rect.xMaximum(), rect.yMaximum()), False
            )
            self._rubber_band.addPoint(
                QgsPointXY(rect.xMaximum(), rect.yMinimum()), True
            )
            self._rubber_band.show()
    
    def canvasReleaseEvent(self, event) -> None:
        """Handle mouse release event."""
        if event.button() != Qt.LeftButton:
            return
        
        if not self._is_dragging:
            return
        
        release_point = self.toMapCoordinates(event.pos())
        release_pixel = QPointF(event.pos())
        
        # Check if this was a drag or a click
        dx = abs(release_pixel.x() - self._drag_start_pixel.x())
        dy = abs(release_pixel.y() - self._drag_start_pixel.y())
        
        is_drag = dx >= 5 or dy >= 5
        
        # Check modifier keys
        modifiers = QApplication.keyboardModifiers()
        ctrl_pressed = modifiers & Qt.ControlModifier
        shift_pressed = modifiers & Qt.ShiftModifier
        
        if is_drag:
            # Rectangle selection - get min/max values
            self._handle_rectangle_selection(
                self._drag_start_point, release_point
            )
        elif shift_pressed:
            # Multi-band sampling
            self._handle_multi_band_pick(release_point)
        elif ctrl_pressed:
            # Extend range with new value
            self._handle_extend_pick(release_point)
        else:
            # Single value pick
            self._handle_single_pick(release_point)
        
        # Clean up
        self._is_dragging = False
        self._drag_start_point = None
        self._drag_start_pixel = None
        
        if self._rubber_band:
            self._rubber_band.reset(QgsWkbTypes.PolygonGeometry)
            self._rubber_band.hide()
        
        self.pick_finished.emit()
    
    def keyPressEvent(self, event) -> None:
        """Handle key press events."""
        if event.key() == Qt.Key_Escape:
            # Cancel picking
            self._is_dragging = False
            if self._rubber_band:
                self._rubber_band.reset(QgsWkbTypes.PolygonGeometry)
                self._rubber_band.hide()
            self.pick_cancelled.emit()
            logger.debug("Pixel picking cancelled")
    
    def _handle_single_pick(self, point: 'QgsPointXY') -> None:
        """
        Handle single click pixel value pick.
        
        Args:
            point: Map coordinates of click
        """
        value = self._sample_pixel(point, self._band)
        
        if value is not None:
            self.value_picked.emit(value)
            logger.debug(f"Single value picked: {value}")
        else:
            logger.warning("Failed to pick pixel value (NoData or error)")
    
    def _handle_extend_pick(self, point: 'QgsPointXY') -> None:
        """
        Handle Ctrl+click to extend range.
        
        Args:
            point: Map coordinates of click
        """
        value = self._sample_pixel(point, self._band)
        
        if value is not None:
            self.extend_requested.emit(value)
            logger.debug(f"Extend range requested with value: {value}")
    
    def _handle_multi_band_pick(self, point: 'QgsPointXY') -> None:
        """
        Handle Shift+click for multi-band sampling.
        
        Args:
            point: Map coordinates of click
        """
        band_values = self._sample_all_bands(point)
        
        if band_values:
            self.multi_band_picked.emit(band_values)
            logger.debug(f"Multi-band values picked: {band_values}")
    
    def _handle_rectangle_selection(
        self,
        start_point: 'QgsPointXY',
        end_point: 'QgsPointXY'
    ) -> None:
        """
        Handle rectangle drag selection for min/max range.
        
        Args:
            start_point: Start corner of rectangle
            end_point: End corner of rectangle
        """
        # Create rectangle
        rect = QgsRectangle(start_point, end_point)
        
        # Sample values within rectangle
        min_val, max_val = self._sample_rectangle(rect, self._band)
        
        if min_val is not None and max_val is not None:
            self.range_picked.emit(min_val, max_val)
            logger.debug(f"Range picked from rectangle: [{min_val}, {max_val}]")
        else:
            logger.warning("Failed to sample rectangle (no valid pixels)")
    
    def _sample_pixel(
        self,
        point: 'QgsPointXY',
        band: int
    ) -> Optional[float]:
        """
        Sample a single pixel value at the given point.
        
        Args:
            point: Map coordinates
            band: Band number (1-indexed)
        
        Returns:
            Pixel value or None if NoData/error
        """
        if self._layer is None:
            logger.warning("No layer set for pixel sampling")
            return None
        
        if not self._layer.isValid():
            logger.warning("Layer is not valid")
            return None
        
        try:
            provider = self._layer.dataProvider()
            
            # Transform coordinates if necessary
            point_in_layer_crs = self._transform_point(point)
            
            # Sample the pixel
            result = provider.identify(
                point_in_layer_crs,
                1  # QgsRaster.IdentifyFormatValue
            )
            
            if result.isValid():
                values = result.results()
                if band in values:
                    value = values[band]
                    # Check for NoData
                    if value is not None and not self._is_nodata(value, band):
                        return float(value)
            
            return None
            
        except Exception as e:
            logger.error(f"Error sampling pixel: {e}")
            return None
    
    def _sample_all_bands(
        self,
        point: 'QgsPointXY'
    ) -> Dict[int, Optional[float]]:
        """
        Sample all bands at the given point.
        
        Args:
            point: Map coordinates
        
        Returns:
            Dict mapping band number to value
        """
        if self._layer is None:
            return {}
        
        result = {}
        band_count = self._layer.bandCount()
        
        for band in range(1, band_count + 1):
            result[band] = self._sample_pixel(point, band)
        
        return result
    
    def _sample_rectangle(
        self,
        rect: 'QgsRectangle',
        band: int
    ) -> tuple:
        """
        Sample min/max values within a rectangle.
        
        Args:
            rect: Rectangle extent in map coordinates
            band: Band number
        
        Returns:
            Tuple (min_value, max_value) or (None, None)
        """
        if self._layer is None:
            return (None, None)
        
        try:
            provider = self._layer.dataProvider()
            
            # Transform rectangle to layer CRS
            rect_in_layer = self._transform_rectangle(rect)
            
            # Get block of data
            # Calculate pixel extent
            layer_extent = self._layer.extent()
            pixel_width = layer_extent.width() / self._layer.width()
            pixel_height = layer_extent.height() / self._layer.height()
            
            # Calculate column/row range
            col_start = int((rect_in_layer.xMinimum() - layer_extent.xMinimum()) / pixel_width)
            col_end = int((rect_in_layer.xMaximum() - layer_extent.xMinimum()) / pixel_width) + 1
            row_start = int((layer_extent.yMaximum() - rect_in_layer.yMaximum()) / pixel_height)
            row_end = int((layer_extent.yMaximum() - rect_in_layer.yMinimum()) / pixel_height) + 1
            
            # Clamp to valid range
            col_start = max(0, col_start)
            col_end = min(self._layer.width(), col_end)
            row_start = max(0, row_start)
            row_end = min(self._layer.height(), row_end)
            
            width = col_end - col_start
            height = row_end - row_start
            
            if width <= 0 or height <= 0:
                return (None, None)
            
            # Read raster block
            block = provider.block(
                band,
                QgsRectangle(
                    layer_extent.xMinimum() + col_start * pixel_width,
                    layer_extent.yMaximum() - row_end * pixel_height,
                    layer_extent.xMinimum() + col_end * pixel_width,
                    layer_extent.yMaximum() - row_start * pixel_height
                ),
                width,
                height
            )
            
            if block is None:
                return (None, None)
            
            # Find min/max, excluding NoData
            values = []
            nodata = provider.sourceNoDataValue(band)
            
            for row in range(height):
                for col in range(width):
                    value = block.value(row, col)
                    if value is not None and value != nodata:
                        values.append(value)
            
            if values:
                return (min(values), max(values))
            
            return (None, None)
            
        except Exception as e:
            logger.error(f"Error sampling rectangle: {e}")
            return (None, None)
    
    def _transform_point(self, point: 'QgsPointXY') -> 'QgsPointXY':
        """Transform point from canvas CRS to layer CRS."""
        if self._layer is None:
            return point
        
        canvas_crs = self._canvas.mapSettings().destinationCrs()
        layer_crs = self._layer.crs()
        
        if canvas_crs != layer_crs:
            transform = QgsCoordinateTransform(
                canvas_crs, layer_crs, QgsProject.instance()
            )
            return transform.transform(point)
        
        return point
    
    def _transform_rectangle(self, rect: 'QgsRectangle') -> 'QgsRectangle':
        """Transform rectangle from canvas CRS to layer CRS."""
        if self._layer is None:
            return rect
        
        canvas_crs = self._canvas.mapSettings().destinationCrs()
        layer_crs = self._layer.crs()
        
        if canvas_crs != layer_crs:
            transform = QgsCoordinateTransform(
                canvas_crs, layer_crs, QgsProject.instance()
            )
            return transform.transformBoundingBox(rect)
        
        return rect
    
    def _is_nodata(self, value: float, band: int) -> bool:
        """Check if a value is NoData for the given band."""
        if self._layer is None:
            return False
        
        provider = self._layer.dataProvider()
        nodata = provider.sourceNoDataValue(band)
        
        return value == nodata
    
    def deactivate(self) -> None:
        """Clean up when tool is deactivated."""
        if self._rubber_band:
            self._rubber_band.reset(QgsWkbTypes.PolygonGeometry)
            self._rubber_band.hide()
        
        super().deactivate()
        logger.debug("PixelPickerMapTool deactivated")
    
    def activate(self) -> None:
        """Set up when tool is activated."""
        super().activate()
        logger.debug("PixelPickerMapTool activated")

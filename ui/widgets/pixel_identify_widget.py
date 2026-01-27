# -*- coding: utf-8 -*-
"""
FilterMate Pixel Identify Tool and Widget.

EPIC-2: Raster Integration
US-07: Pixel Identify Tool

Provides a map tool for identifying pixel values at clicked locations,
and a widget to display the results.

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional, List, TYPE_CHECKING

from qgis.PyQt.QtCore import Qt, pyqtSignal, QPointF
from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QPushButton,
    QGridLayout,
    QScrollArea,
    QSizePolicy,
)
from qgis.PyQt.QtGui import QCursor, QColor

try:
    from qgis.gui import QgsMapTool, QgsMapCanvas
    from qgis.core import (
        QgsPointXY,
        QgsRasterLayer,
        QgsCoordinateReferenceSystem,
        QgsCoordinateTransform,
        QgsProject,
    )
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False

if TYPE_CHECKING:
    from core.ports.raster_port import PixelIdentifyResult

logger = logging.getLogger('FilterMate.UI.PixelIdentifyTool')


class PixelValueCard(QWidget):
    """
    Card widget displaying a single band's pixel value.
    
    Shows band name, value, and optional color swatch for RGB bands.
    """
    
    def __init__(
        self,
        band_name: str,
        value: Optional[float],
        color: Optional[QColor] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        """
        Initialize the pixel value card.
        
        Args:
            band_name: Name of the band (e.g., "Band 1: Red")
            value: Pixel value (None for NoData)
            color: Optional color swatch for RGB visualization
            parent: Parent widget
        """
        super().__init__(parent)
        self._band_name = band_name
        self._value = value
        self._color = color
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        
        # Color swatch (if provided)
        if self._color is not None:
            self._swatch = QFrame()
            self._swatch.setFixedSize(16, 16)
            self._swatch.setStyleSheet(
                f"background-color: {self._color.name()}; "
                "border: 1px solid palette(mid); "
                "border-radius: 2px;"
            )
            layout.addWidget(self._swatch)
        
        # Band name
        self._name_label = QLabel(self._band_name)
        self._name_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self._name_label)
        
        layout.addStretch()
        
        # Value
        if self._value is not None:
            value_text = self._format_value(self._value)
        else:
            value_text = "NoData"
        
        self._value_label = QLabel(value_text)
        self._value_label.setStyleSheet(
            "font-family: 'Consolas', 'Monaco', monospace; "
            "font-size: 11px;"
        )
        if self._value is None:
            self._value_label.setStyleSheet(
                self._value_label.styleSheet() + "color: #e74c3c;"
            )
        layout.addWidget(self._value_label)
        
        # Frame styling
        self.setStyleSheet("""
            PixelValueCard {
                background: palette(base);
                border: 1px solid palette(mid);
                border-radius: 4px;
            }
        """)
    
    def _format_value(self, value: float) -> str:
        """Format the pixel value for display."""
        if value == int(value):
            return str(int(value))
        elif abs(value) >= 1000:
            return f"{value:,.2f}"
        elif abs(value) >= 1:
            return f"{value:.3f}"
        else:
            return f"{value:.6f}"
    
    def set_value(self, value: Optional[float]) -> None:
        """Update the displayed value."""
        self._value = value
        if value is not None:
            self._value_label.setText(self._format_value(value))
            self._value_label.setStyleSheet(
                "font-family: 'Consolas', 'Monaco', monospace; "
                "font-size: 11px;"
            )
        else:
            self._value_label.setText("NoData")
            self._value_label.setStyleSheet(
                "font-family: 'Consolas', 'Monaco', monospace; "
                "font-size: 11px; color: #e74c3c;"
            )


class PixelIdentifyWidget(QWidget):
    """
    Widget for displaying pixel identification results.
    
    EPIC-2 Feature: US-07 Pixel Identify Tool
    
    Features:
    - Coordinate display (map and pixel coordinates)
    - Band values display with color swatches
    - NoData indication
    - Copy to clipboard functionality
    
    Signals:
        identify_requested: Emitted when user clicks identify button
        clear_requested: Emitted when user clicks clear button
    """
    
    identify_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the pixel identify widget."""
        super().__init__(parent)
        self._result: Optional['PixelIdentifyResult'] = None
        self._value_cards: List[PixelValueCard] = []
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # === Header with identify button ===
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        self._identify_btn = QPushButton("🔍 Identify")
        self._identify_btn.setToolTip(
            "Click to activate pixel identify mode, "
            "then click on the map to see pixel values"
        )
        self._identify_btn.setCheckable(True)
        self._identify_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:checked {
                background: #3498db;
                color: white;
            }
        """)
        self._identify_btn.clicked.connect(self._on_identify_clicked)
        header_layout.addWidget(self._identify_btn)
        
        header_layout.addStretch()
        
        self._clear_btn = QPushButton("✖ Clear")
        self._clear_btn.setToolTip("Clear identification results")
        self._clear_btn.clicked.connect(self._on_clear_clicked)
        header_layout.addWidget(self._clear_btn)
        
        layout.addLayout(header_layout)
        
        # === Coordinate display ===
        coord_frame = QFrame()
        coord_frame.setFrameShape(QFrame.StyledPanel)
        coord_layout = QGridLayout(coord_frame)
        coord_layout.setContentsMargins(8, 4, 8, 4)
        coord_layout.setSpacing(4)
        
        # Map coordinates
        coord_layout.addWidget(QLabel("Map X:"), 0, 0)
        self._map_x_label = QLabel("-")
        self._map_x_label.setStyleSheet(
            "font-family: 'Consolas', 'Monaco', monospace;"
        )
        coord_layout.addWidget(self._map_x_label, 0, 1)
        
        coord_layout.addWidget(QLabel("Map Y:"), 0, 2)
        self._map_y_label = QLabel("-")
        self._map_y_label.setStyleSheet(
            "font-family: 'Consolas', 'Monaco', monospace;"
        )
        coord_layout.addWidget(self._map_y_label, 0, 3)
        
        # Pixel coordinates
        coord_layout.addWidget(QLabel("Pixel:"), 1, 0)
        self._pixel_coord_label = QLabel("-")
        self._pixel_coord_label.setStyleSheet(
            "font-family: 'Consolas', 'Monaco', monospace;"
        )
        coord_layout.addWidget(self._pixel_coord_label, 1, 1, 1, 3)
        
        layout.addWidget(coord_frame)
        
        # === Band values scroll area ===
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self._values_container = QWidget()
        self._values_layout = QVBoxLayout(self._values_container)
        self._values_layout.setContentsMargins(0, 0, 0, 0)
        self._values_layout.setSpacing(4)
        
        # Placeholder
        self._placeholder_label = QLabel(
            "Click 🔍 Identify then click on the map\n"
            "to see pixel values at that location"
        )
        self._placeholder_label.setAlignment(Qt.AlignCenter)
        self._placeholder_label.setStyleSheet(
            "color: palette(mid); font-style: italic; padding: 20px;"
        )
        self._values_layout.addWidget(self._placeholder_label)
        
        self._values_layout.addStretch()
        
        scroll_area.setWidget(self._values_container)
        layout.addWidget(scroll_area, 1)  # Stretch
    
    def _on_identify_clicked(self) -> None:
        """Handle identify button click."""
        if self._identify_btn.isChecked():
            self.identify_requested.emit()
        else:
            # Button unchecked, deactivate tool
            pass
    
    def _on_clear_clicked(self) -> None:
        """Handle clear button click."""
        self.clear()
        self.clear_requested.emit()
    
    def set_identify_active(self, active: bool) -> None:
        """
        Set the identify button state.
        
        Args:
            active: Whether identify mode is active
        """
        self._identify_btn.setChecked(active)
    
    def set_result(self, result: 'PixelIdentifyResult') -> None:
        """
        Display pixel identification result.
        
        Args:
            result: PixelIdentifyResult from RasterPort
        """
        self._result = result
        
        # Update coordinate display
        self._map_x_label.setText(f"{result.map_x:.6f}")
        self._map_y_label.setText(f"{result.map_y:.6f}")
        self._pixel_coord_label.setText(
            f"Row {result.pixel_row}, Col {result.pixel_col}"
        )
        
        # Clear old value cards
        self._clear_value_cards()
        
        # Hide placeholder
        self._placeholder_label.setVisible(False)
        
        # Create value cards for each band
        for i, (band_name, value) in enumerate(
            zip(result.band_names, result.values)
        ):
            # Determine color swatch for RGB bands
            color = None
            if len(result.values) >= 3 and i < 3:
                # RGB interpretation
                if result.values[0] is not None and \
                   result.values[1] is not None and \
                   result.values[2] is not None:
                    r = int(min(255, max(0, result.values[0])))
                    g = int(min(255, max(0, result.values[1])))
                    b = int(min(255, max(0, result.values[2])))
                    if i == 0:
                        color = QColor(r, 0, 0)
                    elif i == 1:
                        color = QColor(0, g, 0)
                    else:
                        color = QColor(0, 0, b)
            
            card = PixelValueCard(band_name, value, color)
            self._value_cards.append(card)
            # Insert before the stretch
            self._values_layout.insertWidget(
                self._values_layout.count() - 1,
                card
            )
        
        # Add combined RGB swatch for multi-band
        if len(result.values) >= 3:
            r_val = result.values[0]
            g_val = result.values[1]
            b_val = result.values[2]
            if r_val is not None and g_val is not None and b_val is not None:
                combined_color = QColor(
                    int(min(255, max(0, r_val))),
                    int(min(255, max(0, g_val))),
                    int(min(255, max(0, b_val)))
                )
                rgb_card = PixelValueCard(
                    "RGB Combined",
                    None,
                    combined_color
                )
                rgb_card._value_label.setText(
                    f"#{combined_color.name()[1:].upper()}"
                )
                self._value_cards.append(rgb_card)
                self._values_layout.insertWidget(
                    self._values_layout.count() - 1,
                    rgb_card
                )
    
    def _clear_value_cards(self) -> None:
        """Clear all value cards."""
        for card in self._value_cards:
            self._values_layout.removeWidget(card)
            card.deleteLater()
        self._value_cards.clear()
    
    def clear(self) -> None:
        """Clear all identification results."""
        self._result = None
        
        # Reset coordinate labels
        self._map_x_label.setText("-")
        self._map_y_label.setText("-")
        self._pixel_coord_label.setText("-")
        
        # Clear value cards
        self._clear_value_cards()
        
        # Show placeholder
        self._placeholder_label.setVisible(True)
        
        # Uncheck identify button
        self._identify_btn.setChecked(False)
    
    @property
    def result(self) -> Optional['PixelIdentifyResult']:
        """Get the current result."""
        return self._result
    
    @property
    def is_identify_active(self) -> bool:
        """Check if identify mode is active."""
        return self._identify_btn.isChecked()


if QGIS_AVAILABLE:
    class RasterIdentifyMapTool(QgsMapTool):
        """
        QGIS Map Tool for raster pixel identification.
        
        Allows clicking on the map canvas to identify pixel values
        at the clicked location.
        
        Signals:
            pixel_identified: Emitted when a pixel is identified
                Args: (x: float, y: float, layer: QgsRasterLayer)
            tool_deactivated: Emitted when tool is deactivated
        """
        
        pixel_identified = pyqtSignal(float, float, object)
        tool_deactivated = pyqtSignal()
        
        def __init__(
            self,
            canvas: 'QgsMapCanvas',
            layer: Optional['QgsRasterLayer'] = None
        ) -> None:
            """
            Initialize the map tool.
            
            Args:
                canvas: QGIS map canvas
                layer: Target raster layer for identification
            """
            super().__init__(canvas)
            self._layer = layer
            self.setCursor(QCursor(Qt.CrossCursor))
        
        def set_layer(self, layer: Optional['QgsRasterLayer']) -> None:
            """
            Set the target raster layer.
            
            Args:
                layer: QgsRasterLayer to identify
            """
            self._layer = layer
        
        def canvasReleaseEvent(self, event) -> None:
            """Handle mouse release on canvas."""
            if self._layer is None:
                logger.warning("No raster layer set for identification")
                return
            
            # Get map coordinates
            point = self.toMapCoordinates(event.pos())
            
            # Transform to layer CRS if needed
            canvas_crs = self.canvas().mapSettings().destinationCrs()
            layer_crs = self._layer.crs()
            
            if canvas_crs != layer_crs:
                transform = QgsCoordinateTransform(
                    canvas_crs,
                    layer_crs,
                    QgsProject.instance()
                )
                point = transform.transform(point)
            
            # Emit signal with coordinates and layer
            self.pixel_identified.emit(
                point.x(),
                point.y(),
                self._layer
            )
            
            logger.debug(
                f"Pixel identified at ({point.x():.4f}, {point.y():.4f})"
            )
        
        def deactivate(self) -> None:
            """Handle tool deactivation."""
            super().deactivate()
            self.tool_deactivated.emit()
            logger.debug("Raster identify tool deactivated")
else:
    # Stub class when QGIS is not available
    class RasterIdentifyMapTool:
        """Stub class when QGIS is not available."""
        
        def __init__(self, *args, **kwargs):
            raise RuntimeError("QGIS not available")

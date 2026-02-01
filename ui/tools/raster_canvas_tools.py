"""
Raster Canvas Tools Controller for FilterMate.

Manages the raster exploring canvas tools (pixel picker, rectangle picker,
all bands info) and provides a unified interface for tool button management.

Author: FilterMate Team
Date: February 2026
"""

from enum import Enum
from typing import Optional, Dict, Any, List

from qgis.PyQt.QtCore import QObject, pyqtSignal, Qt
from qgis.PyQt.QtWidgets import QPushButton, QButtonGroup, QMessageBox

from qgis.core import QgsRasterLayer, QgsProject
from qgis.gui import QgsMapCanvas
from qgis.utils import iface

from infrastructure.logging import get_logger
from .pixel_picker_tool import RasterPixelPickerTool

logger = get_logger(__name__)


class RasterToolMode(Enum):
    """Modes for the raster canvas tools."""
    NONE = "none"
    PIXEL_PICKER = "pixel_picker"
    RECTANGLE_PICKER = "rectangle_picker"
    ALL_BANDS_INFO = "all_bands_info"


class RasterCanvasToolsController(QObject):
    """Controller for managing raster canvas tools and their buttons.
    
    This controller manages:
    - Pixel picker tool (single click)
    - Rectangle picker tool (drag selection)
    - All bands info tool (multi-band values)
    - Sync histogram action
    - Reset range action
    
    Signals:
        valuesPicked(float, float): Emitted when a range is picked (min, max)
        valuePicked(float): Emitted when a single value is picked
        allBandsPicked(list): Emitted when all bands values are picked at a point
        rangeReset(float, float): Emitted when range is reset to data bounds
        histogramSynced(): Emitted when histogram sync is requested
        toolActivated(str): Emitted when a tool is activated (mode name)
        toolDeactivated(): Emitted when all tools are deactivated
    """
    
    # Signals
    valuesPicked = pyqtSignal(float, float)  # min, max
    valuePicked = pyqtSignal(float)
    pixelPicked = pyqtSignal(float, float, float)  # value, x, y
    allBandsPicked = pyqtSignal(list)
    rangeReset = pyqtSignal(float, float)  # data_min, data_max
    histogramSynced = pyqtSignal()
    toolActivated = pyqtSignal(str)  # mode name
    toolDeactivated = pyqtSignal()
    
    def __init__(self, canvas: QgsMapCanvas, parent=None):
        """Initialize the raster canvas tools controller.
        
        Args:
            canvas: QgsMapCanvas instance
            parent: Parent QObject
        """
        super().__init__(parent)
        
        self._canvas = canvas
        self._current_mode = RasterToolMode.NONE
        self._layer: Optional[QgsRasterLayer] = None
        self._band_index: int = 1
        self._current_min: float = 0.0
        self._current_max: float = 0.0
        self._data_min: float = 0.0
        self._data_max: float = 0.0
        
        # Tool buttons (to be set externally)
        self._buttons: Dict[str, QPushButton] = {}
        self._button_group: Optional[QButtonGroup] = None
        
        # Create the pixel picker tool
        self._pixel_picker_tool = RasterPixelPickerTool(canvas, self)
        
        # Connect tool signals
        self._connect_tool_signals()
        
        logger.info("RasterCanvasToolsController initialized")
    
    def _connect_tool_signals(self):
        """Connect signals from the pixel picker tool."""
        self._pixel_picker_tool.valuesPicked.connect(self._on_values_picked)
        self._pixel_picker_tool.valuePicked.connect(self._on_value_picked)
        self._pixel_picker_tool.pixelPicked.connect(self._on_pixel_picked)
        self._pixel_picker_tool.allBandsPicked.connect(self._on_all_bands_picked)
        self._pixel_picker_tool.pickingFinished.connect(self._on_tool_deactivated)
    
    # =========================================================================
    # Button Management
    # =========================================================================
    
    def set_buttons(
        self,
        pixel_picker_btn: Optional[QPushButton] = None,
        rect_picker_btn: Optional[QPushButton] = None,
        sync_histogram_btn: Optional[QPushButton] = None,
        all_bands_btn: Optional[QPushButton] = None,
        reset_range_btn: Optional[QPushButton] = None
    ):
        """Set the tool buttons and connect their signals.
        
        Args:
            pixel_picker_btn: Button for pixel picker tool
            rect_picker_btn: Button for rectangle picker tool
            sync_histogram_btn: Button for histogram sync
            all_bands_btn: Button for all bands info
            reset_range_btn: Button for reset range
        """
        self._buttons = {
            'pixel_picker': pixel_picker_btn,
            'rect_picker': rect_picker_btn,
            'sync_histogram': sync_histogram_btn,
            'all_bands': all_bands_btn,
            'reset_range': reset_range_btn
        }
        
        # Create button group for mutually exclusive checkable buttons
        checkable_buttons = [pixel_picker_btn, rect_picker_btn, all_bands_btn]
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(False)  # We'll manage exclusivity manually
        
        for btn in checkable_buttons:
            if btn:
                self._button_group.addButton(btn)
        
        # Connect button signals
        if pixel_picker_btn:
            pixel_picker_btn.clicked.connect(self._on_pixel_picker_clicked)
        
        if rect_picker_btn:
            rect_picker_btn.clicked.connect(self._on_rect_picker_clicked)
        
        if sync_histogram_btn:
            sync_histogram_btn.clicked.connect(self._on_sync_histogram_clicked)
        
        if all_bands_btn:
            all_bands_btn.clicked.connect(self._on_all_bands_clicked)
        
        if reset_range_btn:
            reset_range_btn.clicked.connect(self._on_reset_range_clicked)
        
        logger.debug("Raster tool buttons connected")
    
    def update_buttons_enabled_state(self, enabled: bool = None):
        """Update enabled state of all buttons based on layer availability.
        
        Args:
            enabled: Force enabled state. If None, checks layer validity.
        """
        if enabled is None:
            enabled = self._layer is not None and self._layer.isValid()
        
        for btn in self._buttons.values():
            if btn:
                btn.setEnabled(enabled)
        
        # If disabled, also uncheck all checkable buttons
        if not enabled:
            self._uncheck_all_tool_buttons()
    
    def _uncheck_all_tool_buttons(self):
        """Uncheck all checkable tool buttons."""
        for key in ['pixel_picker', 'rect_picker', 'all_bands']:
            btn = self._buttons.get(key)
            if btn and btn.isCheckable():
                btn.setChecked(False)
    
    def _set_exclusive_check(self, active_key: str):
        """Set exclusive check state for checkable buttons.
        
        Args:
            active_key: Key of the button to keep checked
        """
        for key in ['pixel_picker', 'rect_picker', 'all_bands']:
            btn = self._buttons.get(key)
            if btn and btn.isCheckable() and key != active_key:
                btn.setChecked(False)
    
    # =========================================================================
    # Layer and Range Management
    # =========================================================================
    
    def set_layer(self, layer: QgsRasterLayer, band_index: int = 1):
        """Set the active raster layer.
        
        Args:
            layer: QgsRasterLayer to work with
            band_index: Band index (1-based)
        """
        self._layer = layer
        self._band_index = band_index
        
        # Update the pixel picker tool
        self._pixel_picker_tool.set_layer(layer, band_index)
        
        # Update data min/max from layer statistics
        self._update_data_bounds()
        
        # Update button states
        self.update_buttons_enabled_state()
        
        logger.debug(f"RasterCanvasTools: Layer set to '{layer.name() if layer else 'None'}'")
    
    def set_band_index(self, band_index: int):
        """Set the active band index.
        
        Args:
            band_index: Band index (1-based)
        """
        self._band_index = band_index
        self._pixel_picker_tool.set_layer(self._layer, band_index)
        self._update_data_bounds()
    
    def set_current_range(self, min_val: float, max_val: float):
        """Set the current value range (for Ctrl+click extend mode).
        
        Args:
            min_val: Current minimum value
            max_val: Current maximum value
        """
        self._current_min = min_val
        self._current_max = max_val
        self._pixel_picker_tool.set_current_range(min_val, max_val)
    
    def _update_data_bounds(self):
        """Update data min/max from layer statistics."""
        if not self._layer or not self._layer.isValid():
            self._data_min = 0.0
            self._data_max = 0.0
            return
        
        provider = self._layer.dataProvider()
        if not provider:
            return
        
        from qgis.core import QgsRasterBandStats
        stats = provider.bandStatistics(
            self._band_index,
            QgsRasterBandStats.Min | QgsRasterBandStats.Max
        )
        
        self._data_min = stats.minimumValue
        self._data_max = stats.maximumValue
        logger.debug(f"Data bounds updated: [{self._data_min}, {self._data_max}]")
    
    # =========================================================================
    # Tool Activation
    # =========================================================================
    
    def activate_pixel_picker(self):
        """Activate pixel picker tool in point mode."""
        if not self._layer or not self._layer.isValid():
            logger.warning("Cannot activate pixel picker: no valid layer")
            return
        
        self._current_mode = RasterToolMode.PIXEL_PICKER
        self._canvas.setMapTool(self._pixel_picker_tool)
        self.toolActivated.emit("pixel_picker")
        logger.info("Pixel picker tool activated (point mode)")
    
    def activate_rectangle_picker(self):
        """Activate pixel picker tool in rectangle mode."""
        if not self._layer or not self._layer.isValid():
            logger.warning("Cannot activate rectangle picker: no valid layer")
            return
        
        self._current_mode = RasterToolMode.RECTANGLE_PICKER
        self._canvas.setMapTool(self._pixel_picker_tool)
        self.toolActivated.emit("rectangle_picker")
        logger.info("Pixel picker tool activated (rectangle mode)")
    
    def activate_all_bands_mode(self):
        """Activate all bands info mode."""
        if not self._layer or not self._layer.isValid():
            logger.warning("Cannot activate all bands mode: no valid layer")
            return
        
        self._current_mode = RasterToolMode.ALL_BANDS_INFO
        self._canvas.setMapTool(self._pixel_picker_tool)
        self.toolActivated.emit("all_bands_info")
        logger.info("All bands info mode activated")
    
    def deactivate_tools(self):
        """Deactivate all canvas tools."""
        self._current_mode = RasterToolMode.NONE
        self._canvas.unsetMapTool(self._pixel_picker_tool)
        self._uncheck_all_tool_buttons()
        self.toolDeactivated.emit()
        logger.info("Raster tools deactivated")
    
    @property
    def current_mode(self) -> RasterToolMode:
        """Get the current tool mode."""
        return self._current_mode
    
    @property
    def is_active(self) -> bool:
        """Check if any tool is currently active."""
        return self._current_mode != RasterToolMode.NONE
    
    # =========================================================================
    # Button Click Handlers
    # =========================================================================
    
    def _on_pixel_picker_clicked(self, checked: bool):
        """Handle pixel picker button click."""
        if checked:
            self._set_exclusive_check('pixel_picker')
            self.activate_pixel_picker()
        else:
            self.deactivate_tools()
    
    def _on_rect_picker_clicked(self, checked: bool):
        """Handle rectangle picker button click."""
        if checked:
            self._set_exclusive_check('rect_picker')
            self.activate_rectangle_picker()
        else:
            self.deactivate_tools()
    
    def _on_all_bands_clicked(self, checked: bool):
        """Handle all bands info button click."""
        if checked:
            self._set_exclusive_check('all_bands')
            self.activate_all_bands_mode()
        else:
            self.deactivate_tools()
    
    def _on_sync_histogram_clicked(self):
        """Handle sync histogram button click."""
        logger.info("Sync histogram requested")
        self.histogramSynced.emit()
    
    def _on_reset_range_clicked(self):
        """Handle reset range button click."""
        if not self._layer or not self._layer.isValid():
            logger.warning("Cannot reset range: no valid layer")
            return
        
        # Update bounds from layer stats
        self._update_data_bounds()
        
        logger.info(f"Range reset to data bounds: [{self._data_min}, {self._data_max}]")
        self.rangeReset.emit(self._data_min, self._data_max)
    
    # =========================================================================
    # Tool Signal Handlers
    # =========================================================================
    
    def _on_values_picked(self, min_val: float, max_val: float):
        """Handle values picked from tool."""
        self.valuesPicked.emit(min_val, max_val)
    
    def _on_value_picked(self, value: float):
        """Handle single value picked from tool."""
        if self._current_mode == RasterToolMode.ALL_BANDS_INFO:
            # In all bands mode, we wait for allBandsPicked signal
            pass
        else:
            self.valuePicked.emit(value)
    
    def _on_pixel_picked(self, value: float, x: float, y: float):
        """Handle pixel picked with coordinates."""
        self.pixelPicked.emit(value, x, y)
    
    def _on_all_bands_picked(self, values: List[Optional[float]]):
        """Handle all bands values picked."""
        if self._current_mode == RasterToolMode.ALL_BANDS_INFO:
            # Display all bands info
            self._display_all_bands_info(values)
        self.allBandsPicked.emit(values)
    
    def _on_tool_deactivated(self):
        """Handle tool deactivation from canvas."""
        self._current_mode = RasterToolMode.NONE
        self._uncheck_all_tool_buttons()
        self.toolDeactivated.emit()
    
    def _display_all_bands_info(self, values: List[Optional[float]]):
        """Display all bands values to the user.
        
        Args:
            values: List of values for each band
        """
        if not values:
            return
        
        # Format the values
        lines = []
        for i, val in enumerate(values, 1):
            if val is not None:
                lines.append(f"Band {i}: {val:.4f}")
            else:
                lines.append(f"Band {i}: NoData")
        
        message = "\n".join(lines)
        
        # Show in message bar
        if iface:
            iface.messageBar().pushInfo(
                "FilterMate - All Bands Info",
                f"Values: {', '.join(f'{v:.2f}' if v else 'NoData' for v in values)}"
            )
        
        logger.info(f"All bands info:\n{message}")
    
    # =========================================================================
    # Cleanup
    # =========================================================================
    
    def cleanup(self):
        """Clean up resources."""
        self.deactivate_tools()
        self._pixel_picker_tool._rubber_band.reset()
        logger.debug("RasterCanvasToolsController cleaned up")


class RasterToolButtonManager:
    """Helper class to create and configure raster tool buttons.
    
    This class provides utilities for creating the standard set of
    raster tool buttons with proper icons, tooltips, and checkable states.
    """
    
    # Button specifications
    BUTTON_SPECS = {
        'pixel_picker': {
            'object_name': 'pushButton_raster_pixel_picker',
            'tooltip': 'Click on raster to pick a single value (Ctrl+click to extend range)',
            'icon': 'raster_pipette.png',
            'checkable': True,
            'size': (32, 32)
        },
        'rect_picker': {
            'object_name': 'pushButton_raster_rect_picker',
            'tooltip': 'Drag rectangle to pick value range from area statistics',
            'icon': 'raster_rectangle_picker.png',
            'checkable': True,
            'size': (32, 32)
        },
        'sync_histogram': {
            'object_name': 'pushButton_raster_sync_histogram',
            'tooltip': 'Synchronize spinbox values with histogram selection',
            'icon': 'raster_sync.png',
            'checkable': False,
            'size': (32, 32)
        },
        'all_bands': {
            'object_name': 'pushButton_raster_all_bands',
            'tooltip': 'Show pixel values for all bands at clicked point',
            'icon': 'raster_all_bands.png',
            'checkable': True,
            'size': (32, 32)
        },
        'reset_range': {
            'object_name': 'pushButton_raster_reset_range',
            'tooltip': 'Reset Min/Max to full data range',
            'icon': 'raster_reset_bands.png',
            'checkable': False,
            'size': (32, 32)
        }
    }
    
    @classmethod
    def create_button(cls, key: str, parent=None, icons_path: str = "") -> Optional[QPushButton]:
        """Create a configured tool button.
        
        Args:
            key: Button key from BUTTON_SPECS
            parent: Parent widget
            icons_path: Path to icons folder
            
        Returns:
            Configured QPushButton or None if key not found
        """
        from qgis.PyQt.QtCore import QSize
        from qgis.PyQt.QtGui import QIcon
        import os
        
        spec = cls.BUTTON_SPECS.get(key)
        if not spec:
            logger.warning(f"Unknown button key: {key}")
            return None
        
        btn = QPushButton(parent)
        btn.setObjectName(spec['object_name'])
        btn.setToolTip(spec['tooltip'])
        btn.setCheckable(spec['checkable'])
        btn.setFlat(True)
        
        # Set size
        width, height = spec['size']
        btn.setMinimumSize(QSize(width, height))
        btn.setMaximumSize(QSize(width, height))
        
        # Set icon
        if icons_path and spec['icon']:
            icon_path = os.path.join(icons_path, spec['icon'])
            if os.path.exists(icon_path):
                btn.setIcon(QIcon(icon_path))
                btn.setIconSize(QSize(width - 4, height - 4))
        
        return btn
    
    @classmethod
    def create_all_buttons(cls, parent=None, icons_path: str = "") -> Dict[str, QPushButton]:
        """Create all raster tool buttons.
        
        Args:
            parent: Parent widget
            icons_path: Path to icons folder
            
        Returns:
            Dictionary mapping button keys to QPushButton instances
        """
        buttons = {}
        for key in cls.BUTTON_SPECS:
            btn = cls.create_button(key, parent, icons_path)
            if btn:
                buttons[key] = btn
        return buttons

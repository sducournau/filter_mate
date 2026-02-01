"""
Raster Tools Keys Widget for FilterMate.

A widget containing the vertical column of raster tool buttons
for the EXPLORING RASTER panel.

Author: FilterMate Team
Date: February 2026
"""

import os
from typing import Dict, Optional

from qgis.PyQt.QtCore import Qt, QSize, pyqtSignal
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QSpacerItem,
    QSizePolicy
)

from ...infrastructure.logging import get_logger

logger = get_logger(__name__)


class RasterToolsKeysWidget(QWidget):
    """Widget containing the raster tool buttons column.
    
    This widget provides a vertical column of tool buttons for the
    EXPLORING RASTER panel, matching the pattern of EXPLORING VECTOR keys.
    
    Buttons:
        1. Pixel Picker (checkable) - Pick single value from raster
        2. Rectangle Picker (checkable) - Pick range from area
        3. Sync Histogram - Sync spinbox with histogram
        4. All Bands Info (checkable) - Show all bands values
        5. Reset Range - Reset to data bounds
    
    Signals:
        pixelPickerClicked(bool): Pixel picker button toggled
        rectPickerClicked(bool): Rectangle picker button toggled
        syncHistogramClicked(): Sync histogram button clicked
        allBandsClicked(bool): All bands button toggled
        resetRangeClicked(): Reset range button clicked
    """
    
    # Signals
    pixelPickerClicked = pyqtSignal(bool)
    rectPickerClicked = pyqtSignal(bool)
    syncHistogramClicked = pyqtSignal()
    allBandsClicked = pyqtSignal(bool)
    resetRangeClicked = pyqtSignal()
    
    # Button size
    BUTTON_SIZE = 32
    WIDGET_WIDTH = 42
    
    def __init__(self, parent=None, icons_path: str = ""):
        """Initialize the raster tools keys widget.
        
        Args:
            parent: Parent widget
            icons_path: Path to icons folder
        """
        super().__init__(parent)
        
        self._icons_path = icons_path
        self._buttons: Dict[str, QPushButton] = {}
        
        self._setup_ui()
        self._connect_signals()
        
        logger.debug("RasterToolsKeysWidget initialized")
    
    def _setup_ui(self):
        """Setup the widget UI."""
        self.setObjectName("widget_raster_keys")
        self.setMinimumWidth(self.WIDGET_WIDTH)
        self.setMaximumWidth(self.WIDGET_WIDTH + 8)
        
        # Main layout
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(2, 4, 2, 4)
        self._layout.setSpacing(4)
        
        # Create buttons
        self._buttons['pixel_picker'] = self._create_button(
            object_name="pushButton_raster_pixel_picker",
            tooltip="Click on raster to pick a single value\n(Ctrl+click to extend range)",
            icon="raster_pipette.png",
            checkable=True
        )
        
        self._buttons['rect_picker'] = self._create_button(
            object_name="pushButton_raster_rect_picker",
            tooltip="Drag rectangle to pick value range\nfrom area statistics",
            icon="raster_rectangle_picker.png",
            checkable=True
        )
        
        self._buttons['sync_histogram'] = self._create_button(
            object_name="pushButton_raster_sync_histogram",
            tooltip="Synchronize spinbox values\nwith histogram selection",
            icon="raster_sync.png",
            checkable=False
        )
        
        self._buttons['all_bands'] = self._create_button(
            object_name="pushButton_raster_all_bands",
            tooltip="Show pixel values for all bands\nat clicked point",
            icon="raster_all_bands.png",
            checkable=True
        )
        
        self._buttons['reset_range'] = self._create_button(
            object_name="pushButton_raster_reset_range",
            tooltip="Reset Min/Max to full data range",
            icon="raster_reset_bands.png",
            checkable=False
        )
        
        # Add buttons to layout
        for key in ['pixel_picker', 'rect_picker', 'sync_histogram', 'all_bands', 'reset_range']:
            self._layout.addWidget(self._buttons[key])
        
        # Add spacer at bottom
        spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self._layout.addItem(spacer)
    
    def _create_button(
        self,
        object_name: str,
        tooltip: str,
        icon: str,
        checkable: bool
    ) -> QPushButton:
        """Create a configured tool button.
        
        Args:
            object_name: Widget object name
            tooltip: Button tooltip
            icon: Icon filename
            checkable: Whether button is checkable
            
        Returns:
            Configured QPushButton
        """
        btn = QPushButton(self)
        btn.setObjectName(object_name)
        btn.setToolTip(tooltip)
        btn.setCheckable(checkable)
        btn.setFlat(True)
        
        # Set size
        btn.setMinimumSize(QSize(self.BUTTON_SIZE, self.BUTTON_SIZE))
        btn.setMaximumSize(QSize(self.BUTTON_SIZE, self.BUTTON_SIZE))
        
        # Set icon
        if self._icons_path and icon:
            icon_path = os.path.join(self._icons_path, icon)
            if os.path.exists(icon_path):
                btn.setIcon(QIcon(icon_path))
                btn.setIconSize(QSize(self.BUTTON_SIZE - 4, self.BUTTON_SIZE - 4))
            else:
                logger.warning(f"Icon not found: {icon_path}")
        
        return btn
    
    def _connect_signals(self):
        """Connect button signals to widget signals."""
        self._buttons['pixel_picker'].clicked.connect(self._on_pixel_picker_clicked)
        self._buttons['rect_picker'].clicked.connect(self._on_rect_picker_clicked)
        self._buttons['sync_histogram'].clicked.connect(self._on_sync_histogram_clicked)
        self._buttons['all_bands'].clicked.connect(self._on_all_bands_clicked)
        self._buttons['reset_range'].clicked.connect(self._on_reset_range_clicked)
    
    # =========================================================================
    # Signal Handlers
    # =========================================================================
    
    def _on_pixel_picker_clicked(self, checked: bool):
        """Handle pixel picker button click."""
        if checked:
            self._set_exclusive_check('pixel_picker')
        self.pixelPickerClicked.emit(checked)
    
    def _on_rect_picker_clicked(self, checked: bool):
        """Handle rectangle picker button click."""
        if checked:
            self._set_exclusive_check('rect_picker')
        self.rectPickerClicked.emit(checked)
    
    def _on_sync_histogram_clicked(self):
        """Handle sync histogram button click."""
        self.syncHistogramClicked.emit()
    
    def _on_all_bands_clicked(self, checked: bool):
        """Handle all bands button click."""
        if checked:
            self._set_exclusive_check('all_bands')
        self.allBandsClicked.emit(checked)
    
    def _on_reset_range_clicked(self):
        """Handle reset range button click."""
        self.resetRangeClicked.emit()
    
    def _set_exclusive_check(self, active_key: str):
        """Ensure checkable buttons are mutually exclusive.
        
        Args:
            active_key: Key of the button that should remain checked
        """
        for key in ['pixel_picker', 'rect_picker', 'all_bands']:
            btn = self._buttons.get(key)
            if btn and btn.isCheckable() and key != active_key:
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
    
    # =========================================================================
    # Public API
    # =========================================================================
    
    def get_button(self, key: str) -> Optional[QPushButton]:
        """Get a button by key.
        
        Args:
            key: Button key ('pixel_picker', 'rect_picker', 'sync_histogram',
                 'all_bands', 'reset_range')
                 
        Returns:
            QPushButton or None if key not found
        """
        return self._buttons.get(key)
    
    def get_all_buttons(self) -> Dict[str, QPushButton]:
        """Get all buttons.
        
        Returns:
            Dictionary mapping keys to buttons
        """
        return self._buttons.copy()
    
    def set_buttons_enabled(self, enabled: bool):
        """Set enabled state for all buttons.
        
        Args:
            enabled: Whether buttons should be enabled
        """
        for btn in self._buttons.values():
            btn.setEnabled(enabled)
        
        # If disabling, also uncheck all checkable buttons
        if not enabled:
            self.uncheck_all()
    
    def uncheck_all(self):
        """Uncheck all checkable buttons."""
        for key in ['pixel_picker', 'rect_picker', 'all_bands']:
            btn = self._buttons.get(key)
            if btn:
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
    
    def set_pixel_picker_checked(self, checked: bool):
        """Set pixel picker button checked state."""
        btn = self._buttons.get('pixel_picker')
        if btn:
            btn.blockSignals(True)
            btn.setChecked(checked)
            btn.blockSignals(False)
    
    def set_rect_picker_checked(self, checked: bool):
        """Set rectangle picker button checked state."""
        btn = self._buttons.get('rect_picker')
        if btn:
            btn.blockSignals(True)
            btn.setChecked(checked)
            btn.blockSignals(False)
    
    def set_all_bands_checked(self, checked: bool):
        """Set all bands button checked state."""
        btn = self._buttons.get('all_bands')
        if btn:
            btn.blockSignals(True)
            btn.setChecked(checked)
            btn.blockSignals(False)
    
    def is_any_tool_active(self) -> bool:
        """Check if any tool button is currently checked."""
        for key in ['pixel_picker', 'rect_picker', 'all_bands']:
            btn = self._buttons.get(key)
            if btn and btn.isChecked():
                return True
        return False
    
    def get_active_tool(self) -> Optional[str]:
        """Get the key of the currently active (checked) tool.
        
        Returns:
            Tool key or None if no tool is active
        """
        for key in ['pixel_picker', 'rect_picker', 'all_bands']:
            btn = self._buttons.get(key)
            if btn and btn.isChecked():
                return key
        return None
    
    # =========================================================================
    # Properties for direct button access
    # =========================================================================
    
    @property
    def pushButton_raster_pixel_picker(self) -> QPushButton:
        """Direct access to pixel picker button."""
        return self._buttons['pixel_picker']
    
    @property
    def pushButton_raster_rect_picker(self) -> QPushButton:
        """Direct access to rectangle picker button."""
        return self._buttons['rect_picker']
    
    @property
    def pushButton_raster_sync_histogram(self) -> QPushButton:
        """Direct access to sync histogram button."""
        return self._buttons['sync_histogram']
    
    @property
    def pushButton_raster_all_bands(self) -> QPushButton:
        """Direct access to all bands button."""
        return self._buttons['all_bands']
    
    @property
    def pushButton_raster_reset_range(self) -> QPushButton:
        """Direct access to reset range button."""
        return self._buttons['reset_range']

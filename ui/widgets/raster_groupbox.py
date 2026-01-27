# -*- coding: utf-8 -*-
"""
FilterMate Raster GroupBox Widget.

EPIC-2: Raster Integration (US-01, US-05+)
Provides a collapsible GroupBox for raster layer exploration.

This is a placeholder widget that will be expanded in US-05 (Histogram Widget)
and subsequent user stories.

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional, TYPE_CHECKING

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
)
from qgis.PyQt.QtGui import QFont, QCursor

# Try to import QgsCollapsibleGroupBox
try:
    from qgis.gui import QgsCollapsibleGroupBox
    QGIS_GUI_AVAILABLE = True
except ImportError:
    from qgis.PyQt.QtWidgets import QGroupBox as QgsCollapsibleGroupBox
    QGIS_GUI_AVAILABLE = False

if TYPE_CHECKING:
    from qgis.core import QgsRasterLayer

logger = logging.getLogger('FilterMate.UI.RasterGroupBox')


class RasterExploringGroupBox(QWidget):
    """
    Collapsible GroupBox for raster layer exploration.
    
    EPIC-2 Feature: Raster Integration
    
    Provides UI controls for exploring raster layers:
    - Histogram visualization (US-05)
    - Range slider (US-07)
    - Statistics display (US-04)
    - Filter controls (US-06)
    
    This is initially a placeholder that will be expanded
    as more user stories are implemented.
    
    Signals:
        visibility_changed: Emitted when widget visibility changes
        layer_set: Emitted when a raster layer is set
    """
    
    visibility_changed = pyqtSignal(bool)
    layer_set = pyqtSignal(object)  # QgsRasterLayer or None
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the raster exploring group box.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._layer: Optional['QgsRasterLayer'] = None
        self._setup_ui()
        
    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(2)
        
        # Create collapsible group box
        self._groupbox = QgsCollapsibleGroupBox(self)
        self._groupbox.setTitle("RASTER ANALYSIS")
        self._groupbox.setCheckable(True)
        self._groupbox.setChecked(False)
        self._groupbox.setCollapsed(True)
        
        # Style the groupbox
        font = QFont()
        font.setFamily("Segoe UI Semibold")
        font.setPointSize(10)
        font.setBold(True)
        self._groupbox.setFont(font)
        self._groupbox.setCursor(QCursor(Qt.PointingHandCursor))
        
        # Size policy
        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._groupbox.setSizePolicy(size_policy)
        self._groupbox.setMinimumSize(100, 0)
        
        # Content layout
        content_layout = QVBoxLayout(self._groupbox)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(4)
        
        # Placeholder content (will be replaced in US-05)
        self._placeholder_label = QLabel(
            "📊 Raster analysis tools\n"
            "(Coming in Sprint 2)"
        )
        self._placeholder_label.setAlignment(Qt.AlignCenter)
        self._placeholder_label.setStyleSheet(
            "color: #888; font-style: italic; padding: 16px;"
        )
        content_layout.addWidget(self._placeholder_label)
        
        # Stats placeholder (inline display - per PRD decision)
        self._stats_container = QWidget()
        stats_layout = QHBoxLayout(self._stats_container)
        stats_layout.setContentsMargins(0, 4, 0, 0)
        stats_layout.setSpacing(8)
        
        self._stats_labels = {}
        for stat_name in ['Min', 'Max', 'Mean', 'StdDev']:
            stat_widget = QWidget()
            stat_layout = QVBoxLayout(stat_widget)
            stat_layout.setContentsMargins(0, 0, 0, 0)
            stat_layout.setSpacing(0)
            
            name_label = QLabel(stat_name)
            name_label.setStyleSheet("font-size: 9px; color: #666;")
            name_label.setAlignment(Qt.AlignCenter)
            
            value_label = QLabel("—")
            value_label.setStyleSheet("font-size: 11px; font-weight: bold;")
            value_label.setAlignment(Qt.AlignCenter)
            
            stat_layout.addWidget(name_label)
            stat_layout.addWidget(value_label)
            stats_layout.addWidget(stat_widget)
            
            self._stats_labels[stat_name] = value_label
        
        self._stats_container.setVisible(False)  # Hidden until layer is set
        content_layout.addWidget(self._stats_container)
        
        # Add groupbox to main layout
        main_layout.addWidget(self._groupbox)
        
        # Initially hidden (shown when raster layer is selected)
        self.setVisible(False)
        
        # Connect signals
        if hasattr(self._groupbox, 'collapsedStateChanged'):
            self._groupbox.collapsedStateChanged.connect(self._on_collapsed_changed)
    
    def _on_collapsed_changed(self, collapsed: bool) -> None:
        """Handle groupbox collapse state change."""
        logger.debug(f"Raster groupbox collapsed state: {collapsed}")
    
    def set_layer(self, layer: Optional['QgsRasterLayer']) -> None:
        """
        Set the raster layer for analysis.
        
        Args:
            layer: QgsRasterLayer or None to clear
        """
        self._layer = layer
        
        if layer is not None:
            logger.debug(f"Raster groupbox: layer set to '{layer.name()}'")
            # TODO US-04: Compute and display statistics
            # TODO US-05: Update histogram
            self._stats_container.setVisible(True)
        else:
            logger.debug("Raster groupbox: layer cleared")
            self._stats_container.setVisible(False)
            self._clear_stats()
        
        self.layer_set.emit(layer)
    
    def _clear_stats(self) -> None:
        """Clear statistics display."""
        for label in self._stats_labels.values():
            label.setText("—")
    
    def update_stats(self, min_val: float, max_val: float, 
                     mean: float, stddev: float) -> None:
        """
        Update statistics display.
        
        Args:
            min_val: Minimum raster value
            max_val: Maximum raster value
            mean: Mean raster value
            stddev: Standard deviation
        """
        self._stats_labels['Min'].setText(f"{min_val:.2f}")
        self._stats_labels['Max'].setText(f"{max_val:.2f}")
        self._stats_labels['Mean'].setText(f"{mean:.2f}")
        self._stats_labels['StdDev'].setText(f"{stddev:.2f}")
        self._stats_container.setVisible(True)
    
    def show_for_raster(self) -> None:
        """Show the groupbox for raster layer exploration."""
        self.setVisible(True)
        self._groupbox.setCollapsed(False)
        self._groupbox.setChecked(True)
        self.visibility_changed.emit(True)
        logger.debug("Raster groupbox shown")
    
    def hide_for_vector(self) -> None:
        """Hide the groupbox when vector layer is selected."""
        self.setVisible(False)
        self._groupbox.setCollapsed(True)
        self._groupbox.setChecked(False)
        self.visibility_changed.emit(False)
        logger.debug("Raster groupbox hidden")
    
    @property
    def layer(self) -> Optional['QgsRasterLayer']:
        """Get the current raster layer."""
        return self._layer
    
    @property
    def is_expanded(self) -> bool:
        """Check if the groupbox is expanded."""
        if hasattr(self._groupbox, 'isCollapsed'):
            return not self._groupbox.isCollapsed()
        return self._groupbox.isChecked()

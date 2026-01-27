# -*- coding: utf-8 -*-
"""
FilterMate Raster GroupBox Widget.

EPIC-2: Raster Integration
US-01: Layer Type Detection (placeholder)
US-05: Stats Panel Integration

Provides a collapsible GroupBox for raster layer exploration,
integrating the RasterStatsPanel and connecting to RasterStatsService.

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional, TYPE_CHECKING

from qgis.PyQt.QtCore import Qt, pyqtSignal, QTimer
from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QTabWidget,
)
from qgis.PyQt.QtGui import QFont, QCursor

# Try to import QgsCollapsibleGroupBox
try:
    from qgis.gui import QgsCollapsibleGroupBox
    QGIS_GUI_AVAILABLE = True
except ImportError:
    from qgis.PyQt.QtWidgets import QGroupBox as QgsCollapsibleGroupBox
    QGIS_GUI_AVAILABLE = False

from .raster_stats_panel import RasterStatsPanel

if TYPE_CHECKING:
    from qgis.core import QgsRasterLayer
    from core.services.raster_stats_service import RasterStatsService

logger = logging.getLogger('FilterMate.UI.RasterGroupBox')


class RasterExploringGroupBox(QWidget):
    """
    Collapsible GroupBox for raster layer exploration.
    
    EPIC-2 Feature: Raster Integration
    
    Integrates:
    - US-05: RasterStatsPanel for statistics display
    - US-06: (Future) Histogram visualization
    - US-07: (Future) Pixel identify tool
    - US-08: (Future) Transparency slider
    
    Signals:
        visibility_changed: Emitted when widget visibility changes
        layer_set: Emitted when a raster layer is set
        stats_refresh_requested: Emitted when stats refresh is requested
    """
    
    visibility_changed = pyqtSignal(bool)
    layer_set = pyqtSignal(object)  # QgsRasterLayer or None
    stats_refresh_requested = pyqtSignal(str)  # layer_id
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the raster exploring group box.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._layer: Optional['QgsRasterLayer'] = None
        self._stats_service: Optional['RasterStatsService'] = None
        self._update_timer: Optional[QTimer] = None
        self._setup_ui()
        self._setup_connections()
        
    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(2)
        
        # Create collapsible group box
        self._groupbox = QgsCollapsibleGroupBox(self)
        self._groupbox.setTitle("🗺️ RASTER ANALYSIS")
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
        content_layout.setSpacing(8)
        
        # === Header with refresh button ===
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        self._status_label = QLabel("Select a raster layer")
        self._status_label.setStyleSheet("color: palette(mid);")
        header_layout.addWidget(self._status_label, 1)
        
        self._refresh_btn = QPushButton("↻")
        self._refresh_btn.setToolTip("Refresh statistics")
        self._refresh_btn.setFixedSize(24, 24)
        self._refresh_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid palette(mid);
                border-radius: 4px;
                background: palette(button);
            }
            QPushButton:hover {
                background: palette(light);
            }
        """)
        self._refresh_btn.clicked.connect(self._on_refresh_clicked)
        header_layout.addWidget(self._refresh_btn)
        
        content_layout.addLayout(header_layout)
        
        # === Tab widget for different tools ===
        self._tab_widget = QTabWidget()
        self._tab_widget.setDocumentMode(True)
        self._tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                padding-top: 4px;
            }
            QTabBar::tab {
                padding: 6px 12px;
            }
        """)
        
        # Stats Panel (US-05)
        self._stats_panel = RasterStatsPanel()
        self._tab_widget.addTab(self._stats_panel, "📊 Stats")
        
        # Histogram tab placeholder (US-06)
        self._histogram_placeholder = QLabel(
            "Histogram visualization\n(Coming soon)"
        )
        self._histogram_placeholder.setAlignment(Qt.AlignCenter)
        self._histogram_placeholder.setStyleSheet(
            "color: palette(mid); font-style: italic; padding: 20px;"
        )
        self._tab_widget.addTab(self._histogram_placeholder, "📈 Histogram")
        
        # Tools tab placeholder (US-07, US-08)
        self._tools_placeholder = QLabel(
            "Pixel identify & transparency tools\n(Coming soon)"
        )
        self._tools_placeholder.setAlignment(Qt.AlignCenter)
        self._tools_placeholder.setStyleSheet(
            "color: palette(mid); font-style: italic; padding: 20px;"
        )
        self._tab_widget.addTab(self._tools_placeholder, "🔧 Tools")
        
        content_layout.addWidget(self._tab_widget)
        
        # Add groupbox to main layout
        main_layout.addWidget(self._groupbox)
        
        # Initially hidden (shown when raster layer is selected)
        self.setVisible(False)
        
        # Setup debounce timer for stats updates
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(200)  # 200ms debounce
        self._update_timer.timeout.connect(self._do_update_stats)
    
    def _setup_connections(self) -> None:
        """Set up internal signal connections."""
        # Connect groupbox signals
        if hasattr(self._groupbox, 'collapsedStateChanged'):
            self._groupbox.collapsedStateChanged.connect(
                self._on_collapsed_changed
            )
        
        # Connect stats panel signals
        self._stats_panel.refresh_requested.connect(self._on_refresh_clicked)
    
    def _on_collapsed_changed(self, collapsed: bool) -> None:
        """Handle groupbox collapse state change."""
        logger.debug(f"Raster groupbox collapsed state: {collapsed}")
        
        # Refresh stats when expanding
        if not collapsed and self._layer is not None:
            self._schedule_stats_update()
    
    def _on_refresh_clicked(self) -> None:
        """Handle refresh button click."""
        if self._layer is not None:
            self._status_label.setText("Refreshing...")
            self.stats_refresh_requested.emit(self._layer.id())
            self._schedule_stats_update(force=True)
    
    def _schedule_stats_update(self, force: bool = False) -> None:
        """Schedule a debounced stats update."""
        if self._update_timer:
            self._update_timer.stop()
            if force:
                self._do_update_stats()
            else:
                self._update_timer.start()
    
    def _do_update_stats(self) -> None:
        """Actually perform the stats update."""
        if self._layer is None:
            return
        
        if self._stats_service is None:
            logger.warning("Stats service not set, cannot update stats")
            return
        
        try:
            # Get snapshot from service
            snapshot = self._stats_service.get_layer_snapshot(self._layer.id())
            
            if snapshot:
                self._stats_panel.set_layer_snapshot(snapshot)
                self._status_label.setText(f"✓ {snapshot.layer_name}")
                self._status_label.setStyleSheet("color: palette(text);")
            else:
                self._status_label.setText("⚠ Stats unavailable")
                self._status_label.setStyleSheet("color: #e67e22;")
                
        except Exception as e:
            logger.error(f"Failed to update raster stats: {e}")
            self._status_label.setText("⚠ Error loading stats")
            self._status_label.setStyleSheet("color: #e74c3c;")
    
    def set_stats_service(
        self,
        service: 'RasterStatsService'
    ) -> None:
        """
        Set the RasterStatsService for data retrieval.
        
        Args:
            service: RasterStatsService instance
        """
        self._stats_service = service
        logger.debug("Stats service set for raster groupbox")
    
    def set_layer(self, layer: Optional['QgsRasterLayer']) -> None:
        """
        Set the raster layer for analysis.
        
        Args:
            layer: QgsRasterLayer or None to clear
        """
        self._layer = layer
        
        if layer is not None:
            logger.debug(f"Raster groupbox: layer set to '{layer.name()}'")
            self._status_label.setText(f"Loading {layer.name()}...")
            self._status_label.setStyleSheet("color: palette(mid);")
            self._schedule_stats_update()
        else:
            logger.debug("Raster groupbox: layer cleared")
            self._stats_panel.clear()
            self._status_label.setText("Select a raster layer")
            self._status_label.setStyleSheet("color: palette(mid);")
        
        self.layer_set.emit(layer)
    
    def _clear_stats(self) -> None:
        """Clear statistics display."""
        self._stats_panel.clear()
    
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
    
    @property
    def stats_panel(self) -> RasterStatsPanel:
        """Get the stats panel widget."""
        return self._stats_panel
    
    # === Legacy compatibility methods ===
    
    def update_stats(
        self,
        min_val: float,
        max_val: float,
        mean: float,
        stddev: float
    ) -> None:
        """
        Legacy method for updating stats display.
        
        Deprecated: Use set_layer() with RasterStatsService instead.
        """
        logger.warning(
            "update_stats() is deprecated. "
            "Use set_stats_service() and set_layer() instead."
        )

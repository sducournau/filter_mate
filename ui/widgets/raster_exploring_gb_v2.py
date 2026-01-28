# -*- coding: utf-8 -*-
"""
FilterMate Raster Exploring GroupBox v2.

EPIC-3: Raster-Vector Integration
Refactored to use accordion pattern with 4 exclusive GroupBoxes.

Replaces the tab-based UI with collapsible GroupBoxes:
1. 📊 STATISTICS
2. 📈 VALUE SELECTION  
3. 🎭 MASK & CLIP
4. 💾 MEMORY CLIPS

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional, Dict, TYPE_CHECKING

from qgis.PyQt.QtCore import Qt, pyqtSignal, QTimer
from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QScrollArea,
    QFrame,
)
from qgis.PyQt.QtGui import QFont, QCursor

# Try to import QgsCollapsibleGroupBox
try:
    from qgis.gui import QgsCollapsibleGroupBox, QgsMapLayerComboBox
    from qgis.core import QgsMapLayerProxyModel
    QGIS_GUI_AVAILABLE = True
except ImportError:
    from qgis.PyQt.QtWidgets import QGroupBox as QgsCollapsibleGroupBox
    QGIS_GUI_AVAILABLE = False

# Import the 4 GroupBox widgets
from .raster_statistics_gb import RasterStatisticsGroupBox
from .raster_value_selection_gb import RasterValueSelectionGroupBox
from .raster_mask_clip_gb import RasterMaskClipGroupBox
from .raster_memory_clips_gb import RasterMemoryClipsGroupBox, MemoryClipItem

if TYPE_CHECKING:
    from qgis.core import QgsRasterLayer
    from qgis.gui import QgsMapCanvas
    from core.services.raster_stats_service import RasterStatsService

logger = logging.getLogger('FilterMate.UI.RasterExploringGroupBoxV2')


class RasterExploringGroupBoxV2(QWidget):
    """
    Main container for raster exploring with accordion pattern.
    
    EPIC-3: Raster-Vector Integration
    
    Uses 4 exclusive collapsible GroupBoxes in accordion pattern:
    - Only one GroupBox can be expanded at a time
    - Active GroupBox determines filter context
    - Automatic sync with FILTERING panel
    
    Signals:
        visibility_changed: Emitted when widget visibility changes
        layer_set: Emitted when a raster layer is set
        stats_refresh_requested: Emitted when stats refresh is requested
        active_groupbox_changed: Emitted when active GroupBox changes
        filter_context_changed: Emitted when filter context changes
        pick_mode_activated: Emitted when pixel picker mode is activated
    """
    
    # Signals
    visibility_changed = pyqtSignal(bool)
    layer_set = pyqtSignal(object)  # QgsRasterLayer or None
    stats_refresh_requested = pyqtSignal(str)  # layer_id
    active_groupbox_changed = pyqtSignal(str)  # groupbox name
    filter_context_changed = pyqtSignal(dict)  # filter context
    pick_mode_activated = pyqtSignal(bool)  # is_active
    
    # GroupBox identifiers
    GB_STATISTICS = "statistics"
    GB_VALUE_SELECTION = "value_selection"
    GB_MASK_CLIP = "mask_clip"
    GB_MEMORY_CLIPS = "memory_clips"
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the raster exploring container.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._layer: Optional['QgsRasterLayer'] = None
        self._stats_service: Optional['RasterStatsService'] = None
        self._canvas: Optional['QgsMapCanvas'] = None
        self._active_groupbox: Optional[str] = None
        
        self._setup_ui()
        self._setup_connections()
    
    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(2)
        
        # === Main Collapsible GroupBox (RASTER section) ===
        self._main_groupbox = QgsCollapsibleGroupBox(self)
        self._main_groupbox.setTitle("🏔️ RASTER")
        self._main_groupbox.setCheckable(True)
        self._main_groupbox.setChecked(False)
        self._main_groupbox.setCollapsed(True)
        
        # Style
        font = QFont()
        font.setFamily("Segoe UI Semibold")
        font.setPointSize(10)
        font.setBold(True)
        self._main_groupbox.setFont(font)
        self._main_groupbox.setCursor(QCursor(Qt.PointingHandCursor))
        
        # Size policy
        self._main_groupbox.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )
        self._main_groupbox.setMinimumSize(100, 0)
        
        # Content layout
        content_layout = QVBoxLayout(self._main_groupbox)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(4)
        
        # === Raster Layer Selector ===
        layer_layout = QHBoxLayout()
        layer_layout.setSpacing(4)
        
        layer_label = QLabel("Raster layer:")
        layer_label.setStyleSheet("font-weight: normal; font-size: 9pt;")
        layer_layout.addWidget(layer_label)
        
        if QGIS_GUI_AVAILABLE:
            self._raster_layer_combo = QgsMapLayerComboBox()
            self._raster_layer_combo.setFilters(QgsMapLayerProxyModel.RasterLayer)
            self._raster_layer_combo.setAllowEmptyLayer(True)
            self._raster_layer_combo.setShowCrs(True)
            self._raster_layer_combo.setMinimumHeight(26)
            layer_layout.addWidget(self._raster_layer_combo, 1)
        else:
            self._raster_layer_combo = None
            layer_layout.addWidget(QLabel("QGIS not available"), 1)
        
        content_layout.addLayout(layer_layout)
        
        # === Status Label ===
        self._status_label = QLabel("Select a raster layer")
        self._status_label.setStyleSheet(
            "color: palette(mid); font-style: italic; font-size: 8pt;"
        )
        content_layout.addWidget(self._status_label)
        
        # === Scroll Area for GroupBoxes ===
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(4)
        
        # === 4 GroupBoxes (Accordion Pattern) ===
        
        # 1. Statistics GroupBox
        self._statistics_gb = RasterStatisticsGroupBox()
        scroll_layout.addWidget(self._statistics_gb)
        
        # 2. Value Selection GroupBox
        self._value_selection_gb = RasterValueSelectionGroupBox()
        scroll_layout.addWidget(self._value_selection_gb)
        
        # 3. Mask & Clip GroupBox
        self._mask_clip_gb = RasterMaskClipGroupBox()
        scroll_layout.addWidget(self._mask_clip_gb)
        
        # 4. Memory Clips GroupBox
        self._memory_clips_gb = RasterMemoryClipsGroupBox()
        scroll_layout.addWidget(self._memory_clips_gb)
        
        scroll_layout.addStretch()
        
        scroll_area.setWidget(scroll_content)
        content_layout.addWidget(scroll_area, 1)
        
        main_layout.addWidget(self._main_groupbox)
        
        # VISIBLE BY DEFAULT
        self.setVisible(True)
    
    def _setup_connections(self) -> None:
        """Set up signal connections."""
        # Main groupbox
        if hasattr(self._main_groupbox, 'collapsedStateChanged'):
            self._main_groupbox.collapsedStateChanged.connect(
                self._on_main_collapsed_changed
            )
        
        # Layer combo
        if self._raster_layer_combo:
            self._raster_layer_combo.layerChanged.connect(
                self._on_raster_layer_changed
            )
        
        # Statistics GroupBox
        self._statistics_gb.activated.connect(
            lambda: self._on_groupbox_activated(self.GB_STATISTICS)
        )
        self._statistics_gb.collapsed_changed.connect(
            lambda c: self._on_groupbox_collapsed(self.GB_STATISTICS, c)
        )
        self._statistics_gb.refresh_requested.connect(
            self._on_stats_refresh_requested
        )
        
        # Value Selection GroupBox
        self._value_selection_gb.activated.connect(
            lambda: self._on_groupbox_activated(self.GB_VALUE_SELECTION)
        )
        self._value_selection_gb.collapsed_changed.connect(
            lambda c: self._on_groupbox_collapsed(self.GB_VALUE_SELECTION, c)
        )
        self._value_selection_gb.pick_mode_activated.connect(
            self._on_pick_mode_activated
        )
        self._value_selection_gb.range_changed.connect(
            self._on_value_range_changed
        )
        
        # Mask & Clip GroupBox
        self._mask_clip_gb.activated.connect(
            lambda: self._on_groupbox_activated(self.GB_MASK_CLIP)
        )
        self._mask_clip_gb.collapsed_changed.connect(
            lambda c: self._on_groupbox_collapsed(self.GB_MASK_CLIP, c)
        )
        
        # Memory Clips GroupBox
        self._memory_clips_gb.activated.connect(
            lambda: self._on_groupbox_activated(self.GB_MEMORY_CLIPS)
        )
        self._memory_clips_gb.collapsed_changed.connect(
            lambda c: self._on_groupbox_collapsed(self.GB_MEMORY_CLIPS, c)
        )
    
    def _on_main_collapsed_changed(self, collapsed: bool) -> None:
        """Handle main groupbox collapse state change."""
        self.visibility_changed.emit(not collapsed)
        
        if not collapsed and self._layer is not None:
            # Expand default GroupBox (Statistics)
            if self._active_groupbox is None:
                self._statistics_gb.expand()
    
    def _on_raster_layer_changed(self, layer) -> None:
        """Handle raster layer selection change."""
        from qgis.core import QgsRasterLayer
        
        if layer is not None and isinstance(layer, QgsRasterLayer):
            self.set_layer(layer)
            # Expand main groupbox
            self._main_groupbox.setCollapsed(False)
            self._main_groupbox.setChecked(True)
        else:
            self.set_layer(None)
    
    def _on_groupbox_activated(self, groupbox_name: str) -> None:
        """
        Handle a GroupBox becoming active (expanded).
        
        Implements accordion behavior: collapse all others.
        
        Args:
            groupbox_name: Name of the activated GroupBox
        """
        logger.debug(f"GroupBox activated: {groupbox_name}")
        
        # Collapse all other GroupBoxes
        groupboxes = {
            self.GB_STATISTICS: self._statistics_gb,
            self.GB_VALUE_SELECTION: self._value_selection_gb,
            self.GB_MASK_CLIP: self._mask_clip_gb,
            self.GB_MEMORY_CLIPS: self._memory_clips_gb,
        }
        
        for name, gb in groupboxes.items():
            if name != groupbox_name:
                gb.collapse()
        
        self._active_groupbox = groupbox_name
        self.active_groupbox_changed.emit(groupbox_name)
        
        # Emit updated filter context
        self._emit_filter_context()
    
    def _on_groupbox_collapsed(self, groupbox_name: str, collapsed: bool) -> None:
        """Handle GroupBox collapse state change."""
        if collapsed and self._active_groupbox == groupbox_name:
            # Active GroupBox was collapsed
            self._active_groupbox = None
    
    def _on_stats_refresh_requested(self) -> None:
        """Handle stats refresh request."""
        if self._layer:
            self.stats_refresh_requested.emit(self._layer.id())
    
    def _on_pick_mode_activated(self, active: bool) -> None:
        """Handle pixel picker mode activation."""
        self.pick_mode_activated.emit(active)
    
    def _on_value_range_changed(self, min_val: float, max_val: float) -> None:
        """Handle value range change in Value Selection GroupBox."""
        self._emit_filter_context()
    
    def _emit_filter_context(self) -> None:
        """Emit the current filter context."""
        context = self.get_filter_context()
        self.filter_context_changed.emit(context)
    
    def set_layer(self, layer: Optional['QgsRasterLayer']) -> None:
        """
        Set the raster layer for all GroupBoxes.
        
        Args:
            layer: QgsRasterLayer or None to clear
        """
        self._layer = layer
        
        # Update all GroupBoxes
        self._statistics_gb.set_layer(layer)
        self._value_selection_gb.set_layer(layer)
        
        if layer is not None:
            self._status_label.setText(f"✓ {layer.name()}")
            self._status_label.setStyleSheet(
                "color: palette(text); font-size: 8pt;"
            )
        else:
            self._status_label.setText("Select a raster layer")
            self._status_label.setStyleSheet(
                "color: palette(mid); font-style: italic; font-size: 8pt;"
            )
        
        self.layer_set.emit(layer)
    
    def set_stats_service(self, service: 'RasterStatsService') -> None:
        """
        Set the RasterStatsService for all GroupBoxes.
        
        Args:
            service: RasterStatsService instance
        """
        self._stats_service = service
        self._statistics_gb.set_stats_service(service)
        self._value_selection_gb.set_stats_service(service)
    
    def set_canvas(self, canvas: 'QgsMapCanvas') -> None:
        """
        Set the map canvas for map tools.
        
        Args:
            canvas: QgsMapCanvas instance
        """
        self._canvas = canvas
    
    def set_vector_source_context(self, context: Optional[Dict]) -> None:
        """
        Update the vector source context for Mask & Clip.
        
        This should be called when the EXPLORING VECTOR selection changes.
        
        Args:
            context: Vector context with layer_name, feature_count, mode
        """
        self._mask_clip_gb.set_vector_source_context(context)
    
    def add_memory_clip(self, clip: MemoryClipItem) -> None:
        """
        Add a memory clip to the Memory Clips GroupBox.
        
        Args:
            clip: MemoryClipItem to add
        """
        self._memory_clips_gb.add_clip(clip)
    
    def remove_memory_clip(self, clip_id: str) -> None:
        """
        Remove a memory clip from the Memory Clips GroupBox.
        
        Args:
            clip_id: ID of clip to remove
        """
        self._memory_clips_gb.remove_clip(clip_id)
    
    def get_filter_context(self) -> Dict:
        """
        Get the current filter context based on active GroupBox.
        
        Returns:
            dict: Filter context for FILTERING synchronization
        """
        if self._active_groupbox is None:
            return {'source_type': 'raster', 'mode': None}
        
        if self._active_groupbox == self.GB_STATISTICS:
            return self._statistics_gb.get_filter_context()
        elif self._active_groupbox == self.GB_VALUE_SELECTION:
            return self._value_selection_gb.get_filter_context()
        elif self._active_groupbox == self.GB_MASK_CLIP:
            return self._mask_clip_gb.get_filter_context()
        elif self._active_groupbox == self.GB_MEMORY_CLIPS:
            return self._memory_clips_gb.get_filter_context()
        
        return {'source_type': 'raster', 'mode': None}
    
    def expand_statistics(self) -> None:
        """Expand the Statistics GroupBox."""
        self._statistics_gb.expand()
    
    def expand_value_selection(self) -> None:
        """Expand the Value Selection GroupBox."""
        self._value_selection_gb.expand()
    
    def expand_mask_clip(self) -> None:
        """Expand the Mask & Clip GroupBox."""
        self._mask_clip_gb.expand()
    
    def expand_memory_clips(self) -> None:
        """Expand the Memory Clips GroupBox."""
        self._memory_clips_gb.expand()
    
    def show_for_raster(self) -> None:
        """Expand the main groupbox for raster analysis."""
        self._main_groupbox.setCollapsed(False)
        self._main_groupbox.setChecked(True)
        self.visibility_changed.emit(True)
    
    def hide_for_vector(self) -> None:
        """Collapse the main groupbox when not in active use."""
        self._main_groupbox.setCollapsed(True)
        self._main_groupbox.setChecked(False)
        self.visibility_changed.emit(False)
    
    def clear(self) -> None:
        """Clear all GroupBoxes."""
        self._statistics_gb.clear()
        self._value_selection_gb.clear()
        self._mask_clip_gb.clear()
        self._memory_clips_gb.clear()
        self._layer = None
        self._active_groupbox = None
    
    # === Property accessors ===
    
    @property
    def layer(self) -> Optional['QgsRasterLayer']:
        """Get the current raster layer."""
        return self._layer
    
    @property
    def raster_layer_combo(self):
        """Get the raster layer combobox widget."""
        return self._raster_layer_combo
    
    @property
    def is_expanded(self) -> bool:
        """Check if the main groupbox is expanded."""
        if hasattr(self._main_groupbox, 'isCollapsed'):
            return not self._main_groupbox.isCollapsed()
        return self._main_groupbox.isChecked()
    
    @property
    def active_groupbox(self) -> Optional[str]:
        """Get the name of the active GroupBox."""
        return self._active_groupbox
    
    @property
    def statistics_groupbox(self) -> RasterStatisticsGroupBox:
        """Get the Statistics GroupBox."""
        return self._statistics_gb
    
    @property
    def value_selection_groupbox(self) -> RasterValueSelectionGroupBox:
        """Get the Value Selection GroupBox."""
        return self._value_selection_gb
    
    @property
    def mask_clip_groupbox(self) -> RasterMaskClipGroupBox:
        """Get the Mask & Clip GroupBox."""
        return self._mask_clip_gb
    
    @property
    def memory_clips_groupbox(self) -> RasterMemoryClipsGroupBox:
        """Get the Memory Clips GroupBox."""
        return self._memory_clips_gb
    
    # === Value Selection shortcuts ===
    
    def receive_picked_value(self, value: float) -> None:
        """Forward picked value to Value Selection GroupBox."""
        self._value_selection_gb.receive_picked_value(value)
    
    def receive_picked_range(self, min_val: float, max_val: float) -> None:
        """Forward picked range to Value Selection GroupBox."""
        self._value_selection_gb.receive_picked_range(min_val, max_val)
    
    def extend_range(self, value: float) -> None:
        """Forward extend range to Value Selection GroupBox."""
        self._value_selection_gb.extend_range(value)
    
    def deactivate_pick_mode(self) -> None:
        """Deactivate pick mode in Value Selection GroupBox."""
        self._value_selection_gb.deactivate_pick_mode()
    
    def is_pick_mode_active(self) -> bool:
        """Check if pick mode is active."""
        return self._value_selection_gb.is_pick_mode_active()

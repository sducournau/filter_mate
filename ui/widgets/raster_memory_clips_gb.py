# -*- coding: utf-8 -*-
"""
FilterMate Raster Memory Clips GroupBox Widget.

EPIC-3: Raster-Vector Integration
GroupBox 4: 💾 MEMORY CLIPS

Manages temporary raster clips stored in memory.
Provides visibility toggle, save to disk, and delete functionality.

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional, Dict, List, TYPE_CHECKING
from datetime import datetime

from qgis.PyQt.QtCore import Qt, pyqtSignal, QSize
from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QSizePolicy,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QMessageBox,
    QFileDialog,
    QAbstractItemView,
)
from qgis.PyQt.QtGui import QFont, QCursor, QIcon, QColor

# Try to import QgsCollapsibleGroupBox
try:
    from qgis.gui import QgsCollapsibleGroupBox
    QGIS_GUI_AVAILABLE = True
except ImportError:
    from qgis.PyQt.QtWidgets import QGroupBox as QgsCollapsibleGroupBox
    QGIS_GUI_AVAILABLE = False

if TYPE_CHECKING:
    from qgis.core import QgsRasterLayer

logger = logging.getLogger('FilterMate.UI.RasterMemoryClipsGB')


class MemoryClipItem:
    """
    Data class representing a memory clip item.
    
    Attributes:
        clip_id: Unique identifier
        name: Display name
        source_name: Name of source raster
        size_mb: Size in megabytes
        created_at: Creation timestamp
        visible: Whether visible in map canvas
        operation: Operation type (clip, mask_outside, etc.)
    """
    
    def __init__(
        self,
        clip_id: str,
        name: str,
        source_name: str,
        size_mb: float,
        operation: str = "clip",
        visible: bool = True
    ) -> None:
        self.clip_id = clip_id
        self.name = name
        self.source_name = source_name
        self.size_mb = size_mb
        self.operation = operation
        self.visible = visible
        self.created_at = datetime.now()
    
    def __repr__(self) -> str:
        return f"MemoryClipItem({self.clip_id}, {self.name}, {self.size_mb}MB)"


class MemoryClipListItem(QWidget):
    """
    Custom widget for displaying a memory clip item in the list.
    
    Layout:
    [👁️] [Icon] Name                    Size [💾][🗑️]
                Source: xxx
                Created: HH:MM:SS
    
    Signals:
        visibility_toggled: Emitted when visibility checkbox is toggled
        save_clicked: Emitted when save button is clicked
        delete_clicked: Emitted when delete button is clicked
    """
    
    visibility_toggled = pyqtSignal(str, bool)  # clip_id, visible
    save_clicked = pyqtSignal(str)  # clip_id
    delete_clicked = pyqtSignal(str)  # clip_id
    
    def __init__(
        self,
        clip_item: MemoryClipItem,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._clip_item = clip_item
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)
        
        # Visibility checkbox
        self._visibility_btn = QPushButton("👁️")
        self._visibility_btn.setCheckable(True)
        self._visibility_btn.setChecked(self._clip_item.visible)
        self._visibility_btn.setFixedSize(28, 28)
        self._visibility_btn.setToolTip("Toggle visibility in map canvas")
        self._visibility_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid palette(mid);
                border-radius: 4px;
                background: palette(button);
            }
            QPushButton:checked {
                background: #3498db;
            }
            QPushButton:hover {
                border-color: palette(highlight);
            }
        """)
        self._visibility_btn.clicked.connect(self._on_visibility_clicked)
        layout.addWidget(self._visibility_btn)
        
        # Icon based on operation type
        icon_label = QLabel()
        if self._clip_item.operation in ("clip", "clip_extent"):
            icon_label.setText("🏔️")
        elif self._clip_item.operation in ("mask_outside", "mask_inside"):
            icon_label.setText("🎭")
        else:
            icon_label.setText("📊")
        icon_label.setFixedWidth(20)
        layout.addWidget(icon_label)
        
        # Info section
        info_layout = QVBoxLayout()
        info_layout.setSpacing(0)
        
        # Name
        name_label = QLabel(self._clip_item.name)
        name_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(name_label)
        
        # Source and created time
        details_label = QLabel(
            f"Source: {self._clip_item.source_name}  •  "
            f"Created: {self._clip_item.created_at.strftime('%H:%M:%S')}"
        )
        details_label.setStyleSheet("font-size: 8pt; color: palette(mid);")
        info_layout.addWidget(details_label)
        
        layout.addLayout(info_layout, 1)
        
        # Size
        size_label = QLabel(f"{self._clip_item.size_mb:.1f} MB")
        size_label.setStyleSheet("font-family: monospace; color: palette(mid);")
        size_label.setFixedWidth(60)
        size_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(size_label)
        
        # Save button
        self._save_btn = QPushButton("💾")
        self._save_btn.setFixedSize(28, 28)
        self._save_btn.setToolTip("Save to disk")
        self._save_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid palette(mid);
                border-radius: 4px;
                background: palette(button);
            }
            QPushButton:hover {
                background: palette(light);
                border-color: palette(highlight);
            }
        """)
        self._save_btn.clicked.connect(self._on_save_clicked)
        layout.addWidget(self._save_btn)
        
        # Delete button
        self._delete_btn = QPushButton("🗑️")
        self._delete_btn.setFixedSize(28, 28)
        self._delete_btn.setToolTip("Delete from memory")
        self._delete_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid palette(mid);
                border-radius: 4px;
                background: palette(button);
            }
            QPushButton:hover {
                background: #e74c3c;
                color: white;
                border-color: #c0392b;
            }
        """)
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        layout.addWidget(self._delete_btn)
        
        # Frame styling
        self.setStyleSheet("""
            MemoryClipListItem {
                background: palette(base);
                border: 1px solid palette(mid);
                border-radius: 4px;
            }
            MemoryClipListItem:hover {
                border-color: palette(highlight);
            }
        """)
    
    def _on_visibility_clicked(self) -> None:
        """Handle visibility button click."""
        visible = self._visibility_btn.isChecked()
        self._clip_item.visible = visible
        self.visibility_toggled.emit(self._clip_item.clip_id, visible)
    
    def _on_save_clicked(self) -> None:
        """Handle save button click."""
        self.save_clicked.emit(self._clip_item.clip_id)
    
    def _on_delete_clicked(self) -> None:
        """Handle delete button click."""
        self.delete_clicked.emit(self._clip_item.clip_id)
    
    @property
    def clip_id(self) -> str:
        """Get the clip ID."""
        return self._clip_item.clip_id
    
    def set_visible(self, visible: bool) -> None:
        """Set visibility state."""
        self._visibility_btn.setChecked(visible)
        self._clip_item.visible = visible


class RasterMemoryClipsGroupBox(QWidget):
    """
    Collapsible GroupBox for managing memory clips.
    
    EPIC-3: GroupBox 4 - 💾 MEMORY CLIPS
    
    Features:
    - List of memory clips with visibility toggle
    - Memory usage progress bar
    - Save individual or all clips to disk
    - Delete clips
    
    Signals:
        collapsed_changed: Emitted when collapse state changes
        activated: Emitted when this GroupBox becomes active (expanded)
        clip_visibility_changed: Emitted when clip visibility changes
        clip_save_requested: Emitted when save is requested for a clip
        clip_delete_requested: Emitted when delete is requested
        save_all_requested: Emitted when save all is requested
        clear_all_requested: Emitted when clear all is requested
    """
    
    # Signals
    collapsed_changed = pyqtSignal(bool)  # is_collapsed
    activated = pyqtSignal()  # This GroupBox became active
    clip_visibility_changed = pyqtSignal(str, bool)  # clip_id, visible
    clip_save_requested = pyqtSignal(str)  # clip_id
    clip_delete_requested = pyqtSignal(str)  # clip_id
    save_all_requested = pyqtSignal()
    clear_all_requested = pyqtSignal()
    
    # Default memory limit
    DEFAULT_MEMORY_LIMIT_MB = 500
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the memory clips GroupBox.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._clips: Dict[str, MemoryClipItem] = {}
        self._memory_used_mb: float = 0.0
        self._memory_limit_mb: float = self.DEFAULT_MEMORY_LIMIT_MB
        self._setup_ui()
        self._setup_connections()
    
    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # === Collapsible GroupBox ===
        self._groupbox = QgsCollapsibleGroupBox(self)
        self._update_title()
        self._groupbox.setCheckable(False)
        self._groupbox.setCollapsed(True)
        
        # Style
        font = QFont()
        font.setFamily("Segoe UI")
        font.setPointSize(9)
        font.setBold(True)
        self._groupbox.setFont(font)
        self._groupbox.setCursor(QCursor(Qt.PointingHandCursor))
        
        # Size policy
        self._groupbox.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )
        
        # Content widget
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(8)
        
        # === Clip List ===
        self._clip_list = QListWidget()
        self._clip_list.setObjectName("list_memory_clips")
        self._clip_list.setMinimumHeight(120)
        self._clip_list.setMaximumHeight(250)
        self._clip_list.setSelectionMode(QAbstractItemView.NoSelection)
        self._clip_list.setStyleSheet("""
            QListWidget {
                background: palette(base);
                border: 1px solid palette(mid);
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 2px;
            }
        """)
        
        # Placeholder for empty list
        self._empty_label = QLabel(
            "No memory clips yet.\n"
            "Use MASK & CLIP to create clips."
        )
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet(
            "color: palette(mid); font-style: italic; padding: 20px;"
        )
        content_layout.addWidget(self._empty_label)
        content_layout.addWidget(self._clip_list)
        
        # Initially hide list, show placeholder
        self._clip_list.setVisible(False)
        
        # === Memory Usage ===
        memory_layout = QHBoxLayout()
        memory_layout.setSpacing(8)
        
        memory_label = QLabel("Memory Usage:")
        memory_label.setStyleSheet("font-size: 9pt;")
        memory_layout.addWidget(memory_label)
        
        self._memory_bar = QProgressBar()
        self._memory_bar.setObjectName("progress_memory")
        self._memory_bar.setMaximum(int(self._memory_limit_mb))
        self._memory_bar.setValue(0)
        self._memory_bar.setTextVisible(True)
        self._memory_bar.setFormat("%p%")
        self._memory_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid palette(mid);
                border-radius: 4px;
                text-align: center;
                height: 16px;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 3px;
            }
        """)
        memory_layout.addWidget(self._memory_bar, 1)
        
        self._memory_text = QLabel("0 / 500 MB")
        self._memory_text.setStyleSheet("font-family: monospace; font-size: 8pt;")
        memory_layout.addWidget(self._memory_text)
        
        content_layout.addLayout(memory_layout)
        
        # === Action Buttons ===
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self._save_all_btn = QPushButton("💾 Save All")
        self._save_all_btn.setObjectName("btn_save_all_clips")
        self._save_all_btn.setToolTip("Save all clips to disk")
        self._save_all_btn.setEnabled(False)
        self._save_all_btn.setStyleSheet("""
            QPushButton {
                padding: 4px 12px;
                border: 1px solid palette(mid);
                border-radius: 4px;
                background: palette(button);
            }
            QPushButton:hover {
                background: palette(light);
                border-color: palette(highlight);
            }
            QPushButton:disabled {
                color: palette(mid);
            }
        """)
        btn_layout.addWidget(self._save_all_btn)
        
        self._clear_btn = QPushButton("🗑️ Clear")
        self._clear_btn.setObjectName("btn_clear_clips")
        self._clear_btn.setToolTip("Clear all memory clips")
        self._clear_btn.setEnabled(False)
        self._clear_btn.setStyleSheet("""
            QPushButton {
                padding: 4px 12px;
                border: 1px solid palette(mid);
                border-radius: 4px;
                background: palette(button);
            }
            QPushButton:hover {
                background: #e74c3c;
                color: white;
                border-color: #c0392b;
            }
            QPushButton:disabled {
                color: palette(mid);
            }
        """)
        btn_layout.addWidget(self._clear_btn)
        
        content_layout.addLayout(btn_layout)
        
        # Set content to groupbox
        self._groupbox.setLayout(QVBoxLayout())
        self._groupbox.layout().setContentsMargins(0, 0, 0, 0)
        self._groupbox.layout().addWidget(content)
        
        main_layout.addWidget(self._groupbox)
    
    def _setup_connections(self) -> None:
        """Set up signal connections."""
        # GroupBox collapse
        if hasattr(self._groupbox, 'collapsedStateChanged'):
            self._groupbox.collapsedStateChanged.connect(
                self._on_collapse_changed
            )
        
        # Buttons
        self._save_all_btn.clicked.connect(self._on_save_all_clicked)
        self._clear_btn.clicked.connect(self._on_clear_clicked)
    
    def _on_collapse_changed(self, collapsed: bool) -> None:
        """Handle collapse state change."""
        self.collapsed_changed.emit(collapsed)
        
        if not collapsed:
            # GroupBox expanded = activated
            self.activated.emit()
            logger.debug("Memory Clips GroupBox activated")
    
    def _on_save_all_clicked(self) -> None:
        """Handle save all button click."""
        self.save_all_requested.emit()
    
    def _on_clear_clicked(self) -> None:
        """Handle clear button click."""
        if not self._clips:
            return
        
        # Confirm
        result = QMessageBox.question(
            self,
            "FilterMate - Clear Memory Clips",
            f"Are you sure you want to delete all {len(self._clips)} memory clips?\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if result == QMessageBox.Yes:
            self.clear_all_requested.emit()
    
    def _update_title(self) -> None:
        """Update the groupbox title with clip count and memory usage."""
        count = len(self._clips)
        if count == 0:
            self._groupbox.setTitle("💾 MEMORY CLIPS (0)")
        else:
            used = int(self._memory_used_mb)
            limit = int(self._memory_limit_mb)
            self._groupbox.setTitle(
                f"💾 MEMORY CLIPS ({count})    {used} MB / {limit} MB"
            )
    
    def _update_memory_display(self) -> None:
        """Update memory usage display."""
        used = self._memory_used_mb
        limit = self._memory_limit_mb
        
        self._memory_bar.setMaximum(int(limit))
        self._memory_bar.setValue(int(used))
        self._memory_text.setText(f"{used:.0f} / {limit:.0f} MB")
        
        # Update progress bar color based on usage
        usage_pct = (used / limit * 100) if limit > 0 else 0
        if usage_pct >= 90:
            color = "#e74c3c"  # Red
        elif usage_pct >= 70:
            color = "#e67e22"  # Orange
        else:
            color = "#3498db"  # Blue
        
        self._memory_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid palette(mid);
                border-radius: 4px;
                text-align: center;
                height: 16px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 3px;
            }}
        """)
        
        self._update_title()
    
    def _refresh_list(self) -> None:
        """Refresh the clip list display."""
        self._clip_list.clear()
        
        if not self._clips:
            self._clip_list.setVisible(False)
            self._empty_label.setVisible(True)
            self._save_all_btn.setEnabled(False)
            self._clear_btn.setEnabled(False)
            return
        
        self._clip_list.setVisible(True)
        self._empty_label.setVisible(False)
        self._save_all_btn.setEnabled(True)
        self._clear_btn.setEnabled(True)
        
        for clip_item in self._clips.values():
            # Create custom widget
            widget = MemoryClipListItem(clip_item)
            widget.visibility_toggled.connect(self._on_clip_visibility_changed)
            widget.save_clicked.connect(self._on_clip_save_clicked)
            widget.delete_clicked.connect(self._on_clip_delete_clicked)
            
            # Create list item
            list_item = QListWidgetItem()
            list_item.setSizeHint(QSize(0, 60))
            
            self._clip_list.addItem(list_item)
            self._clip_list.setItemWidget(list_item, widget)
    
    def _on_clip_visibility_changed(self, clip_id: str, visible: bool) -> None:
        """Handle clip visibility change."""
        if clip_id in self._clips:
            self._clips[clip_id].visible = visible
            self.clip_visibility_changed.emit(clip_id, visible)
    
    def _on_clip_save_clicked(self, clip_id: str) -> None:
        """Handle clip save button click."""
        self.clip_save_requested.emit(clip_id)
    
    def _on_clip_delete_clicked(self, clip_id: str) -> None:
        """Handle clip delete button click."""
        if clip_id not in self._clips:
            return
        
        # Confirm
        clip_name = self._clips[clip_id].name
        result = QMessageBox.question(
            self,
            "FilterMate - Delete Clip",
            f"Delete '{clip_name}' from memory?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if result == QMessageBox.Yes:
            self.clip_delete_requested.emit(clip_id)
    
    def add_clip(self, clip_item: MemoryClipItem) -> None:
        """
        Add a memory clip to the list.
        
        Args:
            clip_item: MemoryClipItem to add
        """
        self._clips[clip_item.clip_id] = clip_item
        self._memory_used_mb += clip_item.size_mb
        
        self._refresh_list()
        self._update_memory_display()
        
        logger.debug(f"Added memory clip: {clip_item}")
    
    def remove_clip(self, clip_id: str) -> None:
        """
        Remove a memory clip from the list.
        
        Args:
            clip_id: ID of clip to remove
        """
        if clip_id in self._clips:
            self._memory_used_mb -= self._clips[clip_id].size_mb
            del self._clips[clip_id]
            
            self._refresh_list()
            self._update_memory_display()
            
            logger.debug(f"Removed memory clip: {clip_id}")
    
    def clear(self) -> None:
        """Clear all memory clips."""
        self._clips.clear()
        self._memory_used_mb = 0.0
        
        self._refresh_list()
        self._update_memory_display()
        
        logger.debug("All memory clips cleared")
    
    def set_memory_limit(self, limit_mb: float) -> None:
        """
        Set the memory limit.
        
        Args:
            limit_mb: Memory limit in megabytes
        """
        self._memory_limit_mb = limit_mb
        self._update_memory_display()
    
    def set_collapsed(self, collapsed: bool) -> None:
        """Programmatically set the collapsed state."""
        self._groupbox.setCollapsed(collapsed)
    
    def is_collapsed(self) -> bool:
        """Check if the GroupBox is collapsed."""
        return self._groupbox.isCollapsed()
    
    def expand(self) -> None:
        """Expand the GroupBox."""
        self.set_collapsed(False)
    
    def collapse(self) -> None:
        """Collapse the GroupBox."""
        self.set_collapsed(True)
    
    def get_filter_context(self) -> Dict:
        """
        Get the current filter context for FILTERING synchronization.
        
        Returns:
            dict: Filter context with memory clips info
        """
        return {
            'source_type': 'raster',
            'mode': 'memory_management',
            'clips': [
                {
                    'id': clip.clip_id,
                    'name': clip.name,
                    'source': clip.source_name,
                    'size_mb': clip.size_mb,
                    'visible': clip.visible
                }
                for clip in self._clips.values()
            ],
            'memory_used_mb': self._memory_used_mb,
            'memory_max_mb': self._memory_limit_mb
        }
    
    @property
    def clip_count(self) -> int:
        """Get the number of memory clips."""
        return len(self._clips)
    
    @property
    def memory_used(self) -> float:
        """Get memory used in MB."""
        return self._memory_used_mb
    
    @property
    def memory_limit(self) -> float:
        """Get memory limit in MB."""
        return self._memory_limit_mb

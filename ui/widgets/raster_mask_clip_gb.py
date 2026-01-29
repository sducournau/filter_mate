# -*- coding: utf-8 -*-
"""
FilterMate Raster Mask & Clip GroupBox Widget.

EPIC-3: Raster-Vector Integration
GroupBox 3: 🎭 MASK & CLIP

Provides clip and mask operations between vector and raster layers.
Supports:
- Clip to Vector Extent
- Mask Outside Vector
- Mask Inside Vector
- Zonal Statistics Only

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional, Dict, List, TYPE_CHECKING

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QSizePolicy,
    QRadioButton,
    QButtonGroup,
    QPushButton,
    QCheckBox,
    QGroupBox,
)
from qgis.PyQt.QtGui import QFont, QCursor

# Try to import QgsCollapsibleGroupBox and QgsCheckableComboBox
try:
    from qgis.gui import QgsCollapsibleGroupBox, QgsCheckableComboBox
    QGIS_GUI_AVAILABLE = True
except ImportError:
    from qgis.PyQt.QtWidgets import QGroupBox as QgsCollapsibleGroupBox
    QgsCheckableComboBox = None
    QGIS_GUI_AVAILABLE = False

if TYPE_CHECKING:
    from qgis.core import QgsRasterLayer, QgsVectorLayer

logger = logging.getLogger('FilterMate.UI.RasterMaskClipGB')


# Operation modes
OPERATION_MODES = [
    (
        "clip_extent",
        "Clip to Vector Extent",
        "Découpe le raster aux limites des géométries vectorielles\n"
        "→ Produit un nouveau raster rectangulaire"
    ),
    (
        "mask_outside",
        "Mask Outside Vector",
        "Rend transparent les pixels en dehors des géométries\n"
        "→ Conserve l'extent original, masque appliqué"
    ),
    (
        "mask_inside",
        "Mask Inside Vector",
        "Rend transparent les pixels à l'intérieur des géométries\n"
        "→ Inverse du mode précédent"
    ),
    (
        "zonal_stats",
        "Zonal Statistics Only",
        "Calcule les statistiques par zone sans modifier le raster\n"
        "→ Produit une table de résultats"
    ),
]


class RasterMaskClipGroupBox(QWidget):
    """
    Collapsible GroupBox for raster mask and clip operations.
    
    EPIC-3: GroupBox 3 - 🎭 MASK & CLIP
    
    Features:
    - Operation mode selector (clip, mask outside, mask inside, zonal stats)
    - Target raster layer multi-select
    - Vector source indicator (from EXPLORING VECTOR)
    - Output options (add to memory, save to disk)
    - Apply button
    
    Signals:
        collapsed_changed: Emitted when collapse state changes
        activated: Emitted when this GroupBox becomes active (expanded)
        operation_requested: Emitted when user requests an operation
        operation_mode_changed: Emitted when operation mode changes
    """
    
    # Signals
    collapsed_changed = pyqtSignal(bool)  # is_collapsed
    activated = pyqtSignal()  # This GroupBox became active
    operation_requested = pyqtSignal(dict)  # Full operation params
    operation_mode_changed = pyqtSignal(str)  # operation key
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the mask & clip GroupBox.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._target_rasters: List[str] = []  # List of layer IDs
        self._vector_source_context: Optional[Dict] = None
        self._current_operation: str = "clip_extent"
        self._setup_ui()
        self._setup_connections()
    
    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # === Collapsible GroupBox ===
        self._groupbox = QgsCollapsibleGroupBox(self)
        self._groupbox.setTitle("🎭 MASK & CLIP")
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
        
        # === Operation Mode ===
        mode_label = QLabel("Operation Mode:")
        mode_label.setStyleSheet("font-weight: bold; font-size: 9pt;")
        content_layout.addWidget(mode_label)
        
        mode_frame = QFrame()
        mode_frame.setFrameStyle(QFrame.StyledPanel)
        mode_frame.setStyleSheet("""
            QFrame {
                background-color: palette(alternate-base);
                border-radius: 4px;
            }
        """)
        
        mode_layout = QVBoxLayout(mode_frame)
        mode_layout.setContentsMargins(8, 8, 8, 8)
        mode_layout.setSpacing(6)
        
        self._mode_group = QButtonGroup(self)
        self._mode_radios: Dict[str, QRadioButton] = {}
        
        for key, label, tooltip in OPERATION_MODES:
            radio = QRadioButton(label)
            radio.setObjectName(f"radio_{key}")
            radio.setToolTip(tooltip)
            self._mode_radios[key] = radio
            self._mode_group.addButton(radio)
            mode_layout.addWidget(radio)
        
        # Default to clip
        self._mode_radios["clip_extent"].setChecked(True)
        
        content_layout.addWidget(mode_frame)
        
        # === Target Rasters ===
        target_label = QLabel("Target Rasters:")
        target_label.setStyleSheet("font-weight: bold; font-size: 9pt;")
        content_layout.addWidget(target_label)
        
        target_frame = QFrame()
        target_frame.setFrameStyle(QFrame.StyledPanel)
        target_frame.setStyleSheet("""
            QFrame {
                background-color: palette(alternate-base);
                border-radius: 4px;
            }
        """)
        
        target_layout = QVBoxLayout(target_frame)
        target_layout.setContentsMargins(8, 8, 8, 8)
        
        # Use QgsCheckableComboBox if available
        if QgsCheckableComboBox is not None:
            self._target_combo = QgsCheckableComboBox()
            self._target_combo.setObjectName("combo_target_rasters")
            self._target_combo.setMinimumHeight(26)
            target_layout.addWidget(self._target_combo)
        else:
            # Fallback: simple label
            self._target_combo = None
            self._target_fallback_label = QLabel("No raster layers available")
            self._target_fallback_label.setStyleSheet("color: palette(mid);")
            target_layout.addWidget(self._target_fallback_label)
        
        content_layout.addWidget(target_frame)
        
        # === Vector Source ===
        source_label = QLabel("Vector Source:")
        source_label.setStyleSheet("font-weight: bold; font-size: 9pt;")
        content_layout.addWidget(source_label)
        
        source_frame = QFrame()
        source_frame.setFrameStyle(QFrame.StyledPanel)
        source_frame.setStyleSheet("""
            QFrame {
                background-color: palette(alternate-base);
                border-radius: 4px;
            }
        """)
        
        source_layout = QHBoxLayout(source_frame)
        source_layout.setContentsMargins(8, 8, 8, 8)
        
        self._vector_source_label = QLabel(
            "⚠️ Select features in EXPLORING VECTOR first"
        )
        self._vector_source_label.setObjectName("label_vector_source")
        self._vector_source_label.setStyleSheet("color: #e67e22;")
        self._vector_source_label.setWordWrap(True)
        source_layout.addWidget(self._vector_source_label)
        
        content_layout.addWidget(source_frame)
        
        # === Output Options ===
        output_label = QLabel("Output:")
        output_label.setStyleSheet("font-weight: bold; font-size: 9pt;")
        content_layout.addWidget(output_label)
        
        output_layout = QVBoxLayout()
        output_layout.setSpacing(4)
        
        self._add_to_memory_check = QCheckBox("Add results to Memory Clips")
        self._add_to_memory_check.setObjectName("check_add_memory")
        self._add_to_memory_check.setChecked(True)
        output_layout.addWidget(self._add_to_memory_check)
        
        self._save_to_disk_check = QCheckBox("Save directly to disk")
        self._save_to_disk_check.setObjectName("check_save_disk")
        self._save_to_disk_check.setChecked(False)
        output_layout.addWidget(self._save_to_disk_check)
        
        content_layout.addLayout(output_layout)
        
        # === Apply Button ===
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self._apply_btn = QPushButton("▶ Apply")
        self._apply_btn.setObjectName("btn_apply_operation")
        self._apply_btn.setToolTip("Execute the selected operation")
        self._apply_btn.setEnabled(False)  # Disabled until valid source
        self._apply_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 16px;
                border: 1px solid #27ae60;
                border-radius: 4px;
                background: #27ae60;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #2ecc71;
            }
            QPushButton:disabled {
                background: palette(mid);
                border-color: palette(mid);
                color: palette(base);
            }
        """)
        btn_layout.addWidget(self._apply_btn)
        
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
        
        # Mode buttons
        self._mode_group.buttonClicked.connect(self._on_mode_changed)
        
        # Apply button
        self._apply_btn.clicked.connect(self._on_apply_clicked)
    
    def _on_collapse_changed(self, collapsed: bool) -> None:
        """Handle collapse state change."""
        self.collapsed_changed.emit(collapsed)
        
        if not collapsed:
            # GroupBox expanded = activated
            self.activated.emit()
            logger.debug("Mask & Clip GroupBox activated")
    
    def _on_mode_changed(self, button: QRadioButton) -> None:
        """Handle operation mode change."""
        for key, radio in self._mode_radios.items():
            if radio == button:
                self._current_operation = key
                self.operation_mode_changed.emit(key)
                logger.debug(f"Operation mode changed to: {key}")
                break
    
    def _on_apply_clicked(self) -> None:
        """Handle apply button click."""
        # Build operation parameters
        params = {
            'operation': self._current_operation,
            'target_rasters': self._get_selected_targets(),
            'vector_source': self._vector_source_context,
            'output': {
                'add_to_memory': self._add_to_memory_check.isChecked(),
                'save_to_disk': self._save_to_disk_check.isChecked(),
                'disk_path': None  # Will be set if save_to_disk is True
            }
        }
        
        self.operation_requested.emit(params)
        logger.debug(f"Operation requested: {params}")
    
    def _get_selected_targets(self) -> List[str]:
        """Get list of selected target raster layer IDs."""
        if self._target_combo is None:
            return self._target_rasters
        
        # Get checked items from QgsCheckableComboBox
        selected = []
        for i in range(self._target_combo.count()):
            if self._target_combo.itemCheckState(i) == Qt.Checked:
                layer_id = self._target_combo.itemData(i)
                if layer_id:
                    selected.append(layer_id)
        
        return selected
    
    def set_vector_source_context(self, context: Optional[Dict]) -> None:
        """
        Update the vector source context from EXPLORING VECTOR.
        
        Args:
            context: Vector context dict with layer_name, feature_count, mode
        """
        self._vector_source_context = context
        self._update_vector_source_label()
    
    def _update_vector_source_label(self) -> None:
        """Update the vector source label based on current context."""
        if not self._vector_source_context:
            self._vector_source_label.setText(
                "⚠️ Select features in EXPLORING VECTOR first"
            )
            self._vector_source_label.setStyleSheet("color: #e67e22;")
            self._apply_btn.setEnabled(False)
            return
        
        layer_name = self._vector_source_context.get('layer_name', 'Unknown')
        feature_count = self._vector_source_context.get('feature_count', 0)
        mode = self._vector_source_context.get('mode', 'unknown')
        
        if feature_count == 0:
            self._vector_source_label.setText(
                f"⚠️ {layer_name} - No features selected"
            )
            self._vector_source_label.setStyleSheet("color: #e67e22;")
            self._apply_btn.setEnabled(False)
        else:
            self._vector_source_label.setText(
                f"✓ {layer_name} ({feature_count} features, {mode})"
            )
            self._vector_source_label.setStyleSheet("color: #27ae60;")
            self._apply_btn.setEnabled(True)
    
    def populate_target_rasters(
        self,
        raster_layers: List['QgsRasterLayer']
    ) -> None:
        """
        Populate the target rasters combo with available layers.
        
        Args:
            raster_layers: List of raster layers to show
        """
        if self._target_combo is None:
            # Fallback mode
            if raster_layers:
                self._target_fallback_label.setText(
                    f"{len(raster_layers)} raster layers available"
                )
                self._target_rasters = [layer.id() for layer in raster_layers]
            return
        
        self._target_combo.clear()
        
        for layer in raster_layers:
            # Get layer info
            name = layer.name()
            band_count = layer.bandCount()
            
            # Get data type from first band
            provider = layer.dataProvider()
            data_type = ""
            if provider and band_count > 0:
                data_type = str(provider.dataType(1))
            
            display_text = f"{name} ({data_type}, {band_count} band{'s' if band_count > 1 else ''})"
            
            self._target_combo.addItem(display_text, layer.id())
            
            # Default all to checked
            idx = self._target_combo.count() - 1
            self._target_combo.setItemCheckState(idx, Qt.Checked)
    
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
    
    def clear(self) -> None:
        """Clear all selections and reset to default state."""
        self._target_rasters = []
        self._vector_source_context = None
        
        if self._target_combo:
            self._target_combo.clear()
        
        self._mode_radios["clip_extent"].setChecked(True)
        self._current_operation = "clip_extent"
        
        self._add_to_memory_check.setChecked(True)
        self._save_to_disk_check.setChecked(False)
        
        self._update_vector_source_label()
    
    def get_filter_context(self) -> Dict:
        """
        Get the current filter context for FILTERING synchronization.
        
        Returns:
            dict: Filter context with operation info
        """
        return {
            'source_type': 'raster',
            'mode': 'spatial_operation',
            'operation': self._current_operation,
            'target_rasters': [
                {'id': rid} for rid in self._get_selected_targets()
            ],
            'vector_source': {
                'layer_name': self._vector_source_context.get('layer_name')
                if self._vector_source_context else None,
                'feature_count': self._vector_source_context.get('feature_count', 0)
                if self._vector_source_context else 0,
            },
            'ready': self._vector_source_context is not None and
                     self._vector_source_context.get('feature_count', 0) > 0
        }
    
    @property
    def current_operation(self) -> str:
        """Get the currently selected operation mode."""
        return self._current_operation

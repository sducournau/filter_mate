"""
FilteredLayerListItem - Custom widget for raster filtered layer list items

This widget is used in the Active Filtered Layers list to display:
- Visibility checkbox
- Eye icon (visual indicator)
- Layer name
- Delete button
- Opacity slider with label

Author: Sally (UX Designer)
Created: 2026-02-03 (Sprint 1, Day 3)
"""

from qgis.PyQt.QtCore import Qt, pyqtSignal, QSize
from qgis.PyQt.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QCheckBox,
    QLabel,
    QSlider,
    QPushButton,
    QSizePolicy
)
from qgis.PyQt.QtGui import QFont


class FilteredLayerListItem(QWidget):
    """
    Custom widget for displaying a filtered raster layer in the list.
    
    Signals:
        visibility_toggled(str, bool): Emitted when visibility checkbox toggled
                                       Args: layer_id, is_visible
        opacity_changed(str, int): Emitted when opacity slider moved
                                   Args: layer_id, opacity_percent (0-100)
        delete_clicked(str): Emitted when delete button clicked
                            Args: layer_id
    """
    
    # Define signals
    visibility_toggled = pyqtSignal(str, bool)
    opacity_changed = pyqtSignal(str, int)
    delete_clicked = pyqtSignal(str)
    
    def __init__(self, layer, parent=None):
        """
        Initialize the list item widget.
        
        Args:
            layer: QgsMapLayer - The raster layer this item represents
            parent: QWidget - Parent widget
        """
        super().__init__(parent)
        
        self.layer = layer
        self.layer_id = layer.id()
        self.layer_name = layer.name()
        
        # Setup UI
        self.setup_ui()
        self.setup_connections()
        
        # Set initial state from layer
        self.update_from_layer()
    
    def setup_ui(self):
        """Create and layout all UI components."""
        # Main vertical layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(3)
        
        # --- ROW 1: Checkbox + Eye Icon + Name + Delete Button ---
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(5)
        
        # Visibility checkbox
        self.checkbox_visible = QCheckBox()
        self.checkbox_visible.setToolTip("Toggle layer visibility")
        self.checkbox_visible.setChecked(True)
        row1_layout.addWidget(self.checkbox_visible)
        
        # Eye icon (visual indicator)
        self.label_eye_icon = QLabel("👁")
        self.label_eye_icon.setFixedSize(20, 20)
        self.label_eye_icon.setToolTip("Visibility indicator")
        row1_layout.addWidget(self.label_eye_icon)
        
        # Layer name label
        self.label_name = QLabel(self.layer_name)
        self.label_name.setToolTip(self.layer_name)  # Full name on hover
        
        # Truncate long names
        if len(self.layer_name) > 30:
            display_name = self.layer_name[:27] + "..."
            self.label_name.setText(display_name)
        
        # Make name label expand to fill space
        self.label_name.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred
        )
        row1_layout.addWidget(self.label_name)
        
        # Delete button
        self.button_delete = QPushButton("×")
        self.button_delete.setFixedSize(20, 20)
        self.button_delete.setToolTip(f"Remove layer '{self.layer_name}'")
        self.button_delete.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                font-size: 16px;
                font-weight: bold;
                color: #666;
            }
            QPushButton:hover {
                color: #d32f2f;
                background-color: #ffebee;
            }
        """)
        row1_layout.addWidget(self.button_delete)
        
        main_layout.addLayout(row1_layout)
        
        # --- ROW 2: Opacity Slider + Label ---
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(5)
        row2_layout.setContentsMargins(45, 0, 0, 0)  # Indent to align with name
        
        # Opacity label
        self.label_opacity_text = QLabel("Opacity:")
        row2_layout.addWidget(self.label_opacity_text)
        
        # Opacity slider
        self.slider_opacity = QSlider(Qt.Horizontal)
        self.slider_opacity.setMinimum(0)
        self.slider_opacity.setMaximum(100)
        self.slider_opacity.setValue(70)  # Default 70%
        self.slider_opacity.setTickPosition(QSlider.TicksBelow)
        self.slider_opacity.setTickInterval(10)
        self.slider_opacity.setToolTip("Adjust layer transparency (0% = transparent, 100% = opaque)")
        
        # Make slider expand
        self.slider_opacity.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )
        row2_layout.addWidget(self.slider_opacity)
        
        # Opacity value label
        self.label_opacity_value = QLabel("70%")
        self.label_opacity_value.setMinimumWidth(40)
        self.label_opacity_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        # Make value label bold
        font = QFont()
        font.setBold(True)
        self.label_opacity_value.setFont(font)
        
        row2_layout.addWidget(self.label_opacity_value)
        
        main_layout.addLayout(row2_layout)
        
        # Set size policy for entire widget
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(60)
        self.setMaximumHeight(60)
    
    def setup_connections(self):
        """Connect widget signals to internal handlers."""
        # Checkbox toggled → update eye icon + emit signal
        self.checkbox_visible.toggled.connect(self.on_visibility_toggled)
        
        # Slider moved → update label + emit signal
        self.slider_opacity.valueChanged.connect(self.on_opacity_changed)
        
        # Delete button clicked → emit signal
        self.button_delete.clicked.connect(self.on_delete_clicked)
    
    def on_visibility_toggled(self, checked):
        """
        Handle visibility checkbox toggle.
        
        Args:
            checked: bool - New checkbox state
        """
        # Update eye icon
        if checked:
            self.label_eye_icon.setText("👁")
            self.label_eye_icon.setStyleSheet("color: #1976d2;")  # Blue when visible
        else:
            self.label_eye_icon.setText("👁")
            self.label_eye_icon.setStyleSheet("color: #bdbdbd;")  # Gray when hidden
        
        # Emit signal
        self.visibility_toggled.emit(self.layer_id, checked)
    
    def on_opacity_changed(self, value):
        """
        Handle opacity slider change.
        
        Args:
            value: int - New opacity value (0-100)
        """
        # Update label
        self.label_opacity_value.setText(f"{value}%")
        
        # Emit signal
        self.opacity_changed.emit(self.layer_id, value)
    
    def on_delete_clicked(self):
        """Handle delete button click."""
        # Emit signal
        self.delete_clicked.emit(self.layer_id)
    
    def update_from_layer(self):
        """
        Update widget state from the actual QGIS layer.
        Called when layer properties change externally.
        """
        if not self.layer:
            return
        
        # Update opacity slider from layer
        layer_opacity = int(self.layer.opacity() * 100)
        
        # Block signals to prevent triggering change events
        self.slider_opacity.blockSignals(True)
        self.slider_opacity.setValue(layer_opacity)
        self.label_opacity_value.setText(f"{layer_opacity}%")
        self.slider_opacity.blockSignals(False)
    
    def set_visibility_checked(self, checked):
        """
        Set visibility checkbox state programmatically.
        Used for external sync (e.g., from QGIS layer tree).
        
        Args:
            checked: bool - New checkbox state
        """
        # Block signals to prevent infinite loop
        self.checkbox_visible.blockSignals(True)
        self.checkbox_visible.setChecked(checked)
        self.checkbox_visible.blockSignals(False)
        
        # Update eye icon manually since signal was blocked
        if checked:
            self.label_eye_icon.setText("👁")
            self.label_eye_icon.setStyleSheet("color: #1976d2;")
        else:
            self.label_eye_icon.setText("👁")
            self.label_eye_icon.setStyleSheet("color: #bdbdbd;")
    
    def set_opacity_value(self, value):
        """
        Set opacity slider value programmatically.
        Used for external sync.
        
        Args:
            value: int - Opacity value (0-100)
        """
        # Block signals to prevent infinite loop
        self.slider_opacity.blockSignals(True)
        self.slider_opacity.setValue(value)
        self.label_opacity_value.setText(f"{value}%")
        self.slider_opacity.blockSignals(False)
    
    def sizeHint(self):
        """
        Return recommended size for this widget.
        
        Returns:
            QSize: Recommended size (width=-1 for expand, height=60)
        """
        return QSize(-1, 60)

# -*- coding: utf-8 -*-
"""
FilterMate Raster Transparency/Opacity Slider Widget.

EPIC-2: Raster Integration
US-08: Transparency Slider

Provides a slider widget to control raster layer opacity/transparency,
with optional range-based transparency (hide pixels outside value range).

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional, Tuple, TYPE_CHECKING

from qgis.PyQt.QtCore import Qt, pyqtSignal, QTimer
from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QDoubleSpinBox,
    QGroupBox,
    QCheckBox,
    QPushButton,
    QFrame,
)

if TYPE_CHECKING:
    from qgis.core import QgsRasterLayer

logger = logging.getLogger('FilterMate.UI.TransparencySlider')


class OpacitySlider(QWidget):
    """
    Simple opacity slider with label and spinbox.
    
    Features:
    - Slider from 0% to 100%
    - Synchronized spinbox for precise input
    - Debounced value change signal
    
    Signals:
        opacity_changed(float): Emitted when opacity changes (0.0 to 1.0)
    """
    
    opacity_changed = pyqtSignal(float)
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        initial_value: float = 1.0
    ) -> None:
        """
        Initialize the opacity slider.
        
        Args:
            parent: Parent widget
            initial_value: Initial opacity value (0.0 to 1.0)
        """
        super().__init__(parent)
        self._current_opacity = initial_value
        self._debounce_timer: Optional[QTimer] = None
        self._setup_ui()
        self._setup_connections()
        self._set_value_no_signal(initial_value)
    
    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Label
        self._label = QLabel("Opacity:")
        layout.addWidget(self._label)
        
        # Slider
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(100)
        self._slider.setValue(100)
        self._slider.setTickPosition(QSlider.TicksBelow)
        self._slider.setTickInterval(25)
        layout.addWidget(self._slider, 1)  # Stretch
        
        # Spinbox
        self._spinbox = QSpinBox()
        self._spinbox.setMinimum(0)
        self._spinbox.setMaximum(100)
        self._spinbox.setValue(100)
        self._spinbox.setSuffix("%")
        self._spinbox.setFixedWidth(70)
        layout.addWidget(self._spinbox)
        
        # Debounce timer
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(100)  # 100ms debounce
        self._debounce_timer.timeout.connect(self._emit_opacity_changed)
    
    def _setup_connections(self) -> None:
        """Set up signal connections."""
        self._slider.valueChanged.connect(self._on_slider_changed)
        self._spinbox.valueChanged.connect(self._on_spinbox_changed)
    
    def _on_slider_changed(self, value: int) -> None:
        """Handle slider value change."""
        # Block spinbox signals to avoid loops
        self._spinbox.blockSignals(True)
        self._spinbox.setValue(value)
        self._spinbox.blockSignals(False)
        
        self._current_opacity = value / 100.0
        self._debounce_timer.start()
    
    def _on_spinbox_changed(self, value: int) -> None:
        """Handle spinbox value change."""
        # Block slider signals to avoid loops
        self._slider.blockSignals(True)
        self._slider.setValue(value)
        self._slider.blockSignals(False)
        
        self._current_opacity = value / 100.0
        self._debounce_timer.start()
    
    def _emit_opacity_changed(self) -> None:
        """Emit the opacity changed signal after debounce."""
        self.opacity_changed.emit(self._current_opacity)
        logger.debug(f"Opacity changed: {self._current_opacity:.2f}")
    
    def _set_value_no_signal(self, opacity: float) -> None:
        """Set value without emitting signal."""
        value = int(opacity * 100)
        
        self._slider.blockSignals(True)
        self._spinbox.blockSignals(True)
        
        self._slider.setValue(value)
        self._spinbox.setValue(value)
        self._current_opacity = opacity
        
        self._slider.blockSignals(False)
        self._spinbox.blockSignals(False)
    
    def set_opacity(self, opacity: float) -> None:
        """
        Set the opacity value.
        
        Args:
            opacity: Opacity value from 0.0 to 1.0
        """
        opacity = max(0.0, min(1.0, opacity))
        self._set_value_no_signal(opacity)
    
    @property
    def opacity(self) -> float:
        """Get the current opacity value (0.0 to 1.0)."""
        return self._current_opacity


class RangeTransparencyWidget(QWidget):
    """
    Widget for setting value-based transparency.
    
    Allows hiding pixels outside a specified value range
    by making them transparent.
    
    Signals:
        range_changed(float, float): Emitted when range changes
        enabled_changed(bool): Emitted when enabled state changes
    """
    
    range_changed = pyqtSignal(float, float)
    enabled_changed = pyqtSignal(bool)
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        min_value: float = 0.0,
        max_value: float = 255.0
    ) -> None:
        """
        Initialize the range transparency widget.
        
        Args:
            parent: Parent widget
            min_value: Minimum possible value
            max_value: Maximum possible value
        """
        super().__init__(parent)
        self._data_min = min_value
        self._data_max = max_value
        self._range_min = min_value
        self._range_max = max_value
        self._debounce_timer: Optional[QTimer] = None
        self._setup_ui()
        self._setup_connections()
    
    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Enable checkbox
        self._enable_check = QCheckBox("Hide pixels outside range")
        self._enable_check.setChecked(False)
        layout.addWidget(self._enable_check)
        
        # Range inputs container
        self._range_container = QWidget()
        range_layout = QHBoxLayout(self._range_container)
        range_layout.setContentsMargins(20, 0, 0, 0)  # Indent
        range_layout.setSpacing(8)
        
        # Min value
        range_layout.addWidget(QLabel("Min:"))
        self._min_spinbox = QDoubleSpinBox()
        self._min_spinbox.setDecimals(2)
        self._min_spinbox.setMinimum(-1e10)
        self._min_spinbox.setMaximum(1e10)
        self._min_spinbox.setValue(self._data_min)
        range_layout.addWidget(self._min_spinbox)
        
        range_layout.addWidget(QLabel("Max:"))
        self._max_spinbox = QDoubleSpinBox()
        self._max_spinbox.setDecimals(2)
        self._max_spinbox.setMinimum(-1e10)
        self._max_spinbox.setMaximum(1e10)
        self._max_spinbox.setValue(self._data_max)
        range_layout.addWidget(self._max_spinbox)
        
        # Reset button
        self._reset_btn = QPushButton("↺")
        self._reset_btn.setToolTip("Reset to data range")
        self._reset_btn.setFixedSize(24, 24)
        range_layout.addWidget(self._reset_btn)
        
        range_layout.addStretch()
        
        self._range_container.setEnabled(False)
        layout.addWidget(self._range_container)
        
        # Debounce timer
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(200)  # 200ms debounce
        self._debounce_timer.timeout.connect(self._emit_range_changed)
    
    def _setup_connections(self) -> None:
        """Set up signal connections."""
        self._enable_check.toggled.connect(self._on_enabled_changed)
        self._min_spinbox.valueChanged.connect(self._on_range_value_changed)
        self._max_spinbox.valueChanged.connect(self._on_range_value_changed)
        self._reset_btn.clicked.connect(self.reset_range)
    
    def _on_enabled_changed(self, enabled: bool) -> None:
        """Handle enable checkbox change."""
        self._range_container.setEnabled(enabled)
        self.enabled_changed.emit(enabled)
        
        if enabled:
            self._debounce_timer.start()
        
        logger.debug(f"Range transparency enabled: {enabled}")
    
    def _on_range_value_changed(self) -> None:
        """Handle range value change."""
        if self._enable_check.isChecked():
            self._debounce_timer.start()
    
    def _emit_range_changed(self) -> None:
        """Emit range changed signal after debounce."""
        self._range_min = self._min_spinbox.value()
        self._range_max = self._max_spinbox.value()
        
        # Ensure min <= max
        if self._range_min > self._range_max:
            self._range_min, self._range_max = self._range_max, self._range_min
            self._min_spinbox.blockSignals(True)
            self._max_spinbox.blockSignals(True)
            self._min_spinbox.setValue(self._range_min)
            self._max_spinbox.setValue(self._range_max)
            self._min_spinbox.blockSignals(False)
            self._max_spinbox.blockSignals(False)
        
        self.range_changed.emit(self._range_min, self._range_max)
        logger.debug(f"Range changed: [{self._range_min}, {self._range_max}]")
    
    def set_data_range(self, min_value: float, max_value: float) -> None:
        """
        Set the data range for the spinboxes.
        
        Args:
            min_value: Minimum data value
            max_value: Maximum data value
        """
        self._data_min = min_value
        self._data_max = max_value
        
        # Update spinbox ranges
        self._min_spinbox.blockSignals(True)
        self._max_spinbox.blockSignals(True)
        
        self._min_spinbox.setMinimum(min_value - abs(max_value - min_value))
        self._min_spinbox.setMaximum(max_value + abs(max_value - min_value))
        self._max_spinbox.setMinimum(min_value - abs(max_value - min_value))
        self._max_spinbox.setMaximum(max_value + abs(max_value - min_value))
        
        self._min_spinbox.blockSignals(False)
        self._max_spinbox.blockSignals(False)
    
    def set_range(self, min_value: float, max_value: float) -> None:
        """
        Set the current range values.
        
        Args:
            min_value: Minimum value
            max_value: Maximum value
        """
        self._min_spinbox.blockSignals(True)
        self._max_spinbox.blockSignals(True)
        
        self._min_spinbox.setValue(min_value)
        self._max_spinbox.setValue(max_value)
        self._range_min = min_value
        self._range_max = max_value
        
        self._min_spinbox.blockSignals(False)
        self._max_spinbox.blockSignals(False)
    
    def reset_range(self) -> None:
        """Reset range to data min/max."""
        self.set_range(self._data_min, self._data_max)
        
        if self._enable_check.isChecked():
            self.range_changed.emit(self._data_min, self._data_max)
    
    @property
    def is_enabled(self) -> bool:
        """Check if range transparency is enabled."""
        return self._enable_check.isChecked()
    
    @property
    def range(self) -> Tuple[float, float]:
        """Get the current range."""
        return (self._range_min, self._range_max)


class TransparencyWidget(QWidget):
    """
    Combined transparency control widget.
    
    EPIC-2 Feature: US-08 Transparency Slider
    
    Features:
    - Layer opacity slider (0-100%)
    - Optional range-based transparency
    - Sync with histogram selection
    - Apply to layer button
    
    Signals:
        opacity_changed(float): Emitted when opacity changes
        range_transparency_changed(float, float): Emitted when range changes
        apply_requested: Emitted when apply button clicked
    """
    
    opacity_changed = pyqtSignal(float)
    range_transparency_changed = pyqtSignal(float, float)
    apply_requested = pyqtSignal()
    
    def __init__(
        self,
        parent: Optional[QWidget] = None
    ) -> None:
        """Initialize the transparency widget."""
        super().__init__(parent)
        self._layer: Optional['QgsRasterLayer'] = None
        self._setup_ui()
        self._setup_connections()
    
    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # === Opacity section ===
        opacity_group = QGroupBox("Layer Opacity")
        opacity_layout = QVBoxLayout(opacity_group)
        opacity_layout.setContentsMargins(8, 8, 8, 8)
        
        self._opacity_slider = OpacitySlider()
        opacity_layout.addWidget(self._opacity_slider)
        
        layout.addWidget(opacity_group)
        
        # === Range transparency section ===
        range_group = QGroupBox("Value-Based Transparency")
        range_layout = QVBoxLayout(range_group)
        range_layout.setContentsMargins(8, 8, 8, 8)
        
        self._range_widget = RangeTransparencyWidget()
        range_layout.addWidget(self._range_widget)
        
        # Info label
        info_label = QLabel(
            "💡 Tip: Select a range on the histogram to sync here"
        )
        info_label.setStyleSheet(
            "color: palette(mid); font-size: 9px; font-style: italic;"
        )
        info_label.setWordWrap(True)
        range_layout.addWidget(info_label)
        
        layout.addWidget(range_group)
        
        # === Apply button ===
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self._apply_btn = QPushButton("Apply to Layer")
        self._apply_btn.setToolTip(
            "Apply transparency settings to the current raster layer"
        )
        self._apply_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                font-weight: bold;
                background: #27ae60;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #2ecc71;
            }
            QPushButton:pressed {
                background: #1e8449;
            }
        """)
        self._apply_btn.clicked.connect(self._on_apply_clicked)
        button_layout.addWidget(self._apply_btn)
        
        layout.addLayout(button_layout)
        
        layout.addStretch()
    
    def _setup_connections(self) -> None:
        """Set up signal connections."""
        self._opacity_slider.opacity_changed.connect(self._on_opacity_changed)
        self._range_widget.range_changed.connect(self._on_range_changed)
        self._range_widget.enabled_changed.connect(self._on_range_enabled_changed)
    
    def _on_opacity_changed(self, opacity: float) -> None:
        """Handle opacity change."""
        self.opacity_changed.emit(opacity)
    
    def _on_range_changed(self, min_val: float, max_val: float) -> None:
        """Handle range change."""
        self.range_transparency_changed.emit(min_val, max_val)
    
    def _on_range_enabled_changed(self, enabled: bool) -> None:
        """Handle range enabled state change."""
        logger.debug(f"Range transparency enabled: {enabled}")
    
    def _on_apply_clicked(self) -> None:
        """Handle apply button click."""
        self.apply_requested.emit()
        logger.debug("Apply transparency requested")
    
    def set_layer(self, layer: Optional['QgsRasterLayer']) -> None:
        """
        Set the target raster layer.
        
        Args:
            layer: QgsRasterLayer or None
        """
        self._layer = layer
        
        if layer is not None:
            # Update opacity from layer
            opacity = layer.opacity()
            self._opacity_slider.set_opacity(opacity)
            
            logger.debug(f"Transparency widget: layer set to '{layer.name()}'")
        else:
            self._opacity_slider.set_opacity(1.0)
    
    def set_data_range(self, min_value: float, max_value: float) -> None:
        """
        Set the data range for range transparency.
        
        Args:
            min_value: Minimum data value
            max_value: Maximum data value
        """
        self._range_widget.set_data_range(min_value, max_value)
        self._range_widget.reset_range()
    
    def set_range_from_histogram(
        self,
        min_value: float,
        max_value: float
    ) -> None:
        """
        Set range from histogram selection.
        
        Args:
            min_value: Histogram selection minimum
            max_value: Histogram selection maximum
        """
        self._range_widget.set_range(min_value, max_value)
    
    @property
    def opacity(self) -> float:
        """Get current opacity value."""
        return self._opacity_slider.opacity
    
    @property
    def range_enabled(self) -> bool:
        """Check if range transparency is enabled."""
        return self._range_widget.is_enabled
    
    @property
    def transparency_range(self) -> Tuple[float, float]:
        """Get current transparency range."""
        return self._range_widget.range

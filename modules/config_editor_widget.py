"""
Configuration Editor Widget for FilterMate

Automatically generates user-friendly configuration forms based on metadata.
Supports various widget types: checkbox, combobox, textbox, spinbox, colorpicker.

Usage:
    from modules.config_editor_widget import ConfigEditorWidget
    
    editor = ConfigEditorWidget(config_data)
    editor.show()
    
    # Or embed in existing dialog:
    config_widget = ConfigEditorWidget(config_data)
    layout.addWidget(config_widget)

Author: FilterMate Team
Date: December 2025
"""

from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QPushButton, QGroupBox,
    QScrollArea, QColorDialog, QFormLayout, QFrame
)
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor
from typing import Dict, Any, Optional
import json
import os

try:
    from .config_metadata import get_config_metadata
    from .config_helpers import (
        get_config_value,
        set_config_value,
        validate_config_value_with_metadata
    )
    from .feedback_utils import show_success, show_error as show_error_msg
    IMPORTS_OK = True
except ImportError:
    IMPORTS_OK = False


class ConfigEditorWidget(QWidget):
    """
    Widget that automatically generates configuration UI from metadata.
    """
    
    # Signal emitted when configuration changes
    config_changed = pyqtSignal(str, object)  # (config_path, new_value)
    
    def __init__(self, config_data: Dict[str, Any], parent: Optional[QWidget] = None):
        """
        Initialize configuration editor widget.
        
        Args:
            config_data: Configuration dictionary
            parent: Parent widget
        """
        super().__init__(parent)
        
        if not IMPORTS_OK:
            self.show_error("Required modules not available")
            return
        
        self.config_data = config_data
        self.metadata = get_config_metadata()
        self.widgets = {}  # Store widget references: {config_path: widget}
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create scroll area for many config options
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        # Container widget for scroll area
        container = QWidget()
        container_layout = QVBoxLayout(container)
        
        # Get configuration groups
        groups = self.metadata.get_config_groups()
        
        # Create a group box for each category
        for category, paths in sorted(groups.items()):
            group_box = self.create_group_box(category, paths)
            container_layout.addWidget(group_box)
        
        container_layout.addStretch()
        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)
        
        # Add action buttons at bottom
        self.add_action_buttons(main_layout)
    
    def create_group_box(self, category: str, paths: list) -> QGroupBox:
        """
        Create a group box for a category of configuration options.
        
        Args:
            category: Category name
            paths: List of configuration paths in this category
        
        Returns:
            QGroupBox containing the configuration widgets
        """
        group_box = QGroupBox(category)
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight)
        
        for path in paths:
            widget = self.create_config_widget(path)
            if widget:
                label_text = self.metadata.get_user_friendly_label(path)
                description = self.metadata.get_description(path)
                
                # Create label with tooltip
                label = QLabel(f"{label_text}:")
                if description:
                    label.setToolTip(description)
                
                # Store widget reference
                self.widgets[path] = widget
                
                # Add to form
                form_layout.addRow(label, widget)
        
        group_box.setLayout(form_layout)
        return group_box
    
    def create_config_widget(self, config_path: str) -> Optional[QWidget]:
        """
        Create appropriate widget for a configuration parameter.
        
        Args:
            config_path: Dot-separated configuration path
        
        Returns:
            QWidget for editing the configuration value
        """
        meta = self.metadata.get_metadata(config_path)
        if not meta:
            return None
        
        widget_type = meta.get('widget_type', 'textbox')
        current_value = self.get_current_value(config_path)
        
        if widget_type == 'checkbox':
            return self.create_checkbox(config_path, current_value)
        
        elif widget_type == 'combobox':
            allowed_values = meta['validation'].get('allowed_values', [])
            return self.create_combobox(config_path, current_value, allowed_values)
        
        elif widget_type == 'spinbox':
            validation = meta.get('validation', {})
            min_val = validation.get('min', 0)
            max_val = validation.get('max', 999999)
            return self.create_spinbox(config_path, current_value, min_val, max_val)
        
        elif widget_type == 'doublespinbox':
            validation = meta.get('validation', {})
            min_val = validation.get('min', 0.0)
            max_val = validation.get('max', 999999.0)
            return self.create_doublespinbox(config_path, current_value, min_val, max_val)
        
        elif widget_type == 'colorpicker':
            return self.create_colorpicker(config_path, current_value)
        
        elif widget_type == 'textbox':
            return self.create_textbox(config_path, current_value)
        
        else:
            # Fallback to textbox
            return self.create_textbox(config_path, current_value)
    
    def get_current_value(self, config_path: str) -> Any:
        """
        Get current value from config_data for given path.
        
        Args:
            config_path: Dot-separated path
        
        Returns:
            Current value or default
        """
        keys = config_path.split('.')
        try:
            return get_config_value(self.config_data, *keys)
        except Exception:
            # Try to get default from metadata
            meta = self.metadata.get_metadata(config_path)
            if meta:
                return meta.get('default')
            return None
    
    def create_checkbox(self, config_path: str, current_value: bool) -> QCheckBox:
        """Create checkbox widget."""
        checkbox = QCheckBox()
        checkbox.setChecked(bool(current_value))
        checkbox.stateChanged.connect(
            lambda state: self.on_value_changed(config_path, state == Qt.Checked)
        )
        return checkbox
    
    def create_combobox(self, config_path: str, current_value: Any, 
                        allowed_values: list) -> QComboBox:
        """Create combobox widget."""
        combobox = QComboBox()
        
        for value in allowed_values:
            combobox.addItem(str(value), value)
        
        # Set current value
        index = combobox.findData(current_value)
        if index >= 0:
            combobox.setCurrentIndex(index)
        
        combobox.currentIndexChanged.connect(
            lambda: self.on_value_changed(config_path, combobox.currentData())
        )
        
        return combobox
    
    def create_spinbox(self, config_path: str, current_value: int,
                      min_val: int, max_val: int) -> QSpinBox:
        """Create spinbox widget."""
        spinbox = QSpinBox()
        spinbox.setMinimum(min_val)
        spinbox.setMaximum(max_val)
        spinbox.setValue(int(current_value or 0))
        
        spinbox.valueChanged.connect(
            lambda value: self.on_value_changed(config_path, value)
        )
        
        return spinbox
    
    def create_doublespinbox(self, config_path: str, current_value: float,
                             min_val: float, max_val: float) -> QDoubleSpinBox:
        """Create double spinbox widget for float values."""
        spinbox = QDoubleSpinBox()
        spinbox.setMinimum(float(min_val))
        spinbox.setMaximum(float(max_val))
        spinbox.setDecimals(2)
        spinbox.setSingleStep(0.1)
        spinbox.setValue(float(current_value or 0.0))
        
        spinbox.valueChanged.connect(
            lambda value: self.on_value_changed(config_path, value)
        )
        
        return spinbox
    
    def create_textbox(self, config_path: str, current_value: str) -> QLineEdit:
        """Create textbox widget."""
        textbox = QLineEdit()
        textbox.setText(str(current_value or ''))
        
        textbox.textChanged.connect(
            lambda text: self.on_value_changed(config_path, text)
        )
        
        return textbox
    
    def create_colorpicker(self, config_path: str, current_value: str) -> QWidget:
        """Create color picker widget."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Color display label
        color_label = QLabel()
        color_label.setFixedSize(50, 25)
        color_label.setStyleSheet(f"background-color: {current_value}; border: 1px solid #ccc;")
        
        # Color text field
        color_text = QLineEdit(current_value)
        color_text.setMaximumWidth(100)
        
        # Pick color button
        pick_btn = QPushButton("Pick")
        pick_btn.setMaximumWidth(60)
        
        def pick_color():
            color = QColorDialog.getColor(QColor(current_value), self)
            if color.isValid():
                hex_color = color.name()
                color_text.setText(hex_color)
                color_label.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #ccc;")
                self.on_value_changed(config_path, hex_color)
        
        def text_changed(text):
            if text.startswith('#') and len(text) == 7:
                color_label.setStyleSheet(f"background-color: {text}; border: 1px solid #ccc;")
                self.on_value_changed(config_path, text)
        
        pick_btn.clicked.connect(pick_color)
        color_text.textChanged.connect(text_changed)
        
        layout.addWidget(color_label)
        layout.addWidget(color_text)
        layout.addWidget(pick_btn)
        layout.addStretch()
        
        return container
    
    def on_value_changed(self, config_path: str, new_value: Any):
        """
        Handle value change in a configuration widget.
        
        Args:
            config_path: Configuration path that changed
            new_value: New value
        """
        # Validate the new value
        valid, error = validate_config_value_with_metadata(config_path, new_value)
        
        if not valid:
            # Show error message to user
            show_error_msg(
                "FilterMate - Configuration",
                f"Invalid value for {config_path}: {error}"
            )
            return
        
        # Update config_data
        keys = config_path.split('.')
        try:
            set_config_value(self.config_data, new_value, *keys)
            self.config_changed.emit(config_path, new_value)
        except Exception:
            pass  # Error already shown to user via validation
    
    def add_action_buttons(self, layout: QVBoxLayout):
        """Add action buttons (Save, Reset, etc.)."""
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Reset to defaults button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self.reset_to_defaults)
        button_layout.addWidget(reset_btn)
        
        # Save button
        save_btn = QPushButton("Save Configuration")
        save_btn.clicked.connect(self.save_configuration)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
    
    def reset_to_defaults(self):
        """Reset all configuration values to defaults."""
        for config_path, widget in self.widgets.items():
            meta = self.metadata.get_metadata(config_path)
            if meta and 'default' in meta:
                default = meta['default']
                
                # Update widget
                if isinstance(widget, QCheckBox):
                    widget.setChecked(bool(default))
                elif isinstance(widget, QComboBox):
                    index = widget.findData(default)
                    if index >= 0:
                        widget.setCurrentIndex(index)
                elif isinstance(widget, QSpinBox):
                    widget.setValue(int(default))
                elif isinstance(widget, QLineEdit):
                    widget.setText(str(default))
                
                # Update config_data
                keys = config_path.split('.')
                set_config_value(self.config_data, default, *keys)
    
    def save_configuration(self):
        """Save configuration to config.json."""
        try:
            # Get config path from ENV_VARS
            from config.config import ENV_VARS
            config_path = ENV_VARS.get('CONFIG_JSON_PATH')
            
            if not config_path:
                raise ValueError("CONFIG_JSON_PATH not found in ENV_VARS")
            
            # Save configuration to file
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            
            # Show success message
            show_success(
                "FilterMate",
                f"Configuration saved to {os.path.basename(config_path)}"
            )
            
        except Exception as e:
            error_msg = f"Failed to save configuration: {str(e)}"
            # Show error message
            show_error_msg("FilterMate", error_msg)
        
    def show_error(self, message: str):
        """Show error message when widget cannot be initialized."""
        layout = QVBoxLayout(self)
        error_label = QLabel(f"Error: {message}")
        error_label.setStyleSheet("color: red; padding: 20px;")
        layout.addWidget(error_label)


class SimpleConfigDialog(QWidget):
    """
    Simple standalone dialog for configuration editing.
    """
    
    def __init__(self, config_data: Dict[str, Any], parent: Optional[QWidget] = None):
        """
        Initialize simple config dialog.
        
        Args:
            config_data: Configuration dictionary
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.setWindowTitle("FilterMate Configuration")
        self.resize(600, 500)
        
        layout = QVBoxLayout(self)
        
        # Add title
        title = QLabel("FilterMate Configuration")
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(title)
        
        # Add config editor
        self.editor = ConfigEditorWidget(config_data)
        layout.addWidget(self.editor)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

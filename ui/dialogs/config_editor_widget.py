# -*- coding: utf-8 -*-
"""
Configuration Editor Widget for FilterMate

This module provides UI widgets for editing FilterMate configuration.
It auto-generates appropriate widgets based on configuration metadata.

Migrated from: before_migration/modules/config_editor_widget.py (447 lines)
Location: ui/dialogs/config_editor_widget.py

Usage:
    from ui.dialogs.config_editor_widget import ConfigEditorWidget, SimpleConfigDialog
    
    # Create standalone editor widget
    editor = ConfigEditorWidget(config_data, metadata)
    
    # Create dialog
    dialog = SimpleConfigDialog(config_data, parent_widget)
    if dialog.exec_():
        updated_config = dialog.get_config()

Author: FilterMate Team
Date: December 2025 (migrated January 2026)
"""

from typing import Any, Dict, Optional, Callable

from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QCheckBox, QComboBox, QSpinBox, QDoubleSpinBox,
    QLineEdit, QPushButton, QGroupBox, QScrollArea,
    QDialog, QDialogButtonBox, QColorDialog, QMessageBox,
    QTabWidget
)
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor


class ColorPickerWidget(QWidget):
    """
    Simple color picker widget with preview and button.
    """
    
    colorChanged = pyqtSignal(str)
    
    def __init__(self, initial_color: str = "#ffffff", parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Color preview label
        self._preview = QLabel()
        self._preview.setFixedSize(24, 24)
        self._preview.setStyleSheet(f"background-color: {initial_color}; border: 1px solid #888;")
        layout.addWidget(self._preview)
        
        # Color code display
        self._color_edit = QLineEdit(initial_color)
        self._color_edit.setMaximumWidth(80)
        self._color_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._color_edit)
        
        # Pick button
        self._pick_button = QPushButton("...")
        self._pick_button.setFixedWidth(30)
        self._pick_button.clicked.connect(self._pick_color)
        layout.addWidget(self._pick_button)
        
        layout.addStretch()
        
        self._color = initial_color
        
    def _pick_color(self):
        """Open color dialog."""
        current = QColor(self._color)
        color = QColorDialog.getColor(current, self, "Select Color")
        if color.isValid():
            self._color = color.name()
            self._color_edit.setText(self._color)
            self._preview.setStyleSheet(f"background-color: {self._color}; border: 1px solid #888;")
            self.colorChanged.emit(self._color)
            
    def _on_text_changed(self, text: str):
        """Handle manual color code entry."""
        if QColor(text).isValid():
            self._color = text
            self._preview.setStyleSheet(f"background-color: {self._color}; border: 1px solid #888;")
            self.colorChanged.emit(self._color)
            
    def get_value(self) -> str:
        """Get current color value."""
        return self._color
        
    def set_value(self, color: str):
        """Set color value."""
        if QColor(color).isValid():
            self._color = color
            self._color_edit.setText(color)
            self._preview.setStyleSheet(f"background-color: {color}; border: 1px solid #888;")


class ConfigEditorWidget(QWidget):
    """
    Auto-generated configuration editor widget.
    
    Creates appropriate UI widgets based on configuration metadata:
    - boolean -> QCheckBox
    - combobox -> QComboBox
    - spinbox -> QSpinBox/QDoubleSpinBox
    - colorpicker -> ColorPickerWidget
    - textbox (default) -> QLineEdit
    
    Signals:
        configChanged: Emitted when any configuration value changes
    """
    
    configChanged = pyqtSignal()
    
    def __init__(
        self,
        config_data: Dict[str, Any],
        metadata: Optional[Any] = None,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the configuration editor.
        
        Args:
            config_data: Dictionary of config_path -> value
            metadata: Optional ConfigMetadata instance for widget hints
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._config_data = config_data.copy()
        self._metadata = metadata
        self._widgets: Dict[str, QWidget] = {}
        self._on_change_callbacks: list = []
        
        self._init_ui()
        
    def _init_ui(self):
        """Build the configuration UI."""
        main_layout = QVBoxLayout(self)
        
        # Create scroll area for many options
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        container = QWidget()
        self._content_layout = QVBoxLayout(container)
        
        if self._metadata:
            # Group by category
            self._build_grouped_ui()
        else:
            # Simple list
            self._build_flat_ui()
            
        self._content_layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)
        
    def _build_grouped_ui(self):
        """Build UI with grouped sections."""
        groups = self._metadata.get_config_groups()
        
        for group_name in sorted(groups.keys()):
            paths = groups[group_name]
            
            # Create group box
            group_box = QGroupBox(group_name)
            group_layout = QGridLayout(group_box)
            
            row = 0
            for config_path in paths:
                if config_path in self._config_data:
                    value = self._config_data[config_path]
                    self._add_config_row(group_layout, row, config_path, value)
                    row += 1
                    
            if row > 0:  # Only add group if it has content
                self._content_layout.addWidget(group_box)
                
    def _build_flat_ui(self):
        """Build UI without grouping."""
        grid = QGridLayout()
        
        row = 0
        for config_path, value in sorted(self._config_data.items()):
            self._add_config_row(grid, row, config_path, value)
            row += 1
            
        self._content_layout.addLayout(grid)
        
    def _add_config_row(
        self, 
        layout: QGridLayout, 
        row: int, 
        config_path: str, 
        value: Any
    ):
        """
        Add a configuration row to the layout.
        
        Args:
            layout: Grid layout to add to
            row: Row index
            config_path: Configuration path
            value: Current value
        """
        # Create label
        if self._metadata:
            label_text = self._metadata.get_user_friendly_label(config_path)
            tooltip = self._metadata.get_description(config_path)
        else:
            label_text = config_path.split('.')[-1].replace('_', ' ').title()
            tooltip = config_path
            
        label = QLabel(f"{label_text}:")
        label.setToolTip(tooltip)
        layout.addWidget(label, row, 0)
        
        # Create appropriate widget
        widget = self._create_widget_for_value(config_path, value)
        widget.setToolTip(tooltip)
        layout.addWidget(widget, row, 1)
        
        self._widgets[config_path] = widget
        
    def _create_widget_for_value(self, config_path: str, value: Any) -> QWidget:
        """
        Create appropriate widget based on value type and metadata.
        
        Args:
            config_path: Configuration path
            value: Current value
            
        Returns:
            Created widget
        """
        widget_type = 'textbox'
        
        if self._metadata:
            widget_type = self._metadata.get_widget_type(config_path)
        elif isinstance(value, bool):
            widget_type = 'checkbox'
        elif isinstance(value, int):
            widget_type = 'spinbox'
        elif isinstance(value, float):
            widget_type = 'spinbox'
            
        # Create widget based on type
        if widget_type == 'checkbox':
            return self._create_checkbox(config_path, value)
        elif widget_type == 'combobox':
            return self._create_combobox(config_path, value)
        elif widget_type == 'spinbox':
            return self._create_spinbox(config_path, value)
        elif widget_type == 'colorpicker':
            return self._create_colorpicker(config_path, value)
        else:
            return self._create_textbox(config_path, value)
            
    def _create_checkbox(self, config_path: str, value: Any) -> QCheckBox:
        """Create checkbox widget."""
        checkbox = QCheckBox()
        checkbox.setChecked(bool(value))
        checkbox.stateChanged.connect(
            lambda state: self._on_value_changed(config_path, state == Qt.Checked)
        )
        return checkbox
        
    def _create_combobox(self, config_path: str, value: Any) -> QComboBox:
        """Create combobox widget."""
        combobox = QComboBox()
        
        # Get allowed values from metadata
        if self._metadata:
            allowed = self._metadata.get_allowed_values(config_path)
            if allowed:
                combobox.addItems([str(v) for v in allowed])
                
        # Set current value
        index = combobox.findText(str(value))
        if index >= 0:
            combobox.setCurrentIndex(index)
        elif combobox.count() == 0:
            combobox.addItem(str(value))
            
        combobox.currentTextChanged.connect(
            lambda text: self._on_value_changed(config_path, text)
        )
        return combobox
        
    def _create_spinbox(self, config_path: str, value: Any) -> QWidget:
        """Create spinbox widget."""
        if isinstance(value, float):
            spinbox = QDoubleSpinBox()
            spinbox.setDecimals(2)
        else:
            spinbox = QSpinBox()
            
        # Set range from metadata
        if self._metadata:
            meta = self._metadata.get_metadata(config_path)
            if meta and 'validation' in meta:
                val = meta['validation']
                if 'min' in val:
                    spinbox.setMinimum(val['min'])
                if 'max' in val:
                    spinbox.setMaximum(val['max'])
        else:
            spinbox.setMinimum(-999999)
            spinbox.setMaximum(999999)
            
        spinbox.setValue(value if value is not None else 0)
        spinbox.valueChanged.connect(
            lambda v: self._on_value_changed(config_path, v)
        )
        return spinbox
        
    def _create_colorpicker(self, config_path: str, value: Any) -> ColorPickerWidget:
        """Create color picker widget."""
        color_str = str(value) if value else "#ffffff"
        picker = ColorPickerWidget(color_str)
        picker.colorChanged.connect(
            lambda color: self._on_value_changed(config_path, color)
        )
        return picker
        
    def _create_textbox(self, config_path: str, value: Any) -> QLineEdit:
        """Create textbox widget."""
        textbox = QLineEdit(str(value) if value is not None else "")
        textbox.textChanged.connect(
            lambda text: self._on_value_changed(config_path, text)
        )
        return textbox
        
    def _on_value_changed(self, config_path: str, value: Any):
        """Handle value change."""
        self._config_data[config_path] = value
        self.configChanged.emit()
        
        # Call registered callbacks
        for callback in self._on_change_callbacks:
            try:
                callback(config_path, value)
            except Exception:
                pass
                
    def get_config(self) -> Dict[str, Any]:
        """
        Get current configuration values.
        
        Returns:
            Dictionary of config_path -> value
        """
        return self._config_data.copy()
        
    def set_config(self, config_data: Dict[str, Any]):
        """
        Set configuration values.
        
        Args:
            config_data: Dictionary of config_path -> value
        """
        for config_path, value in config_data.items():
            if config_path in self._widgets:
                widget = self._widgets[config_path]
                self._set_widget_value(widget, value)
                self._config_data[config_path] = value
                
    def _set_widget_value(self, widget: QWidget, value: Any):
        """Set value on a widget."""
        if isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QComboBox):
            index = widget.findText(str(value))
            if index >= 0:
                widget.setCurrentIndex(index)
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            widget.setValue(value if value is not None else 0)
        elif isinstance(widget, ColorPickerWidget):
            widget.set_value(str(value))
        elif isinstance(widget, QLineEdit):
            widget.setText(str(value) if value is not None else "")
            
    def reset_to_defaults(self):
        """Reset all values to defaults from metadata."""
        if not self._metadata:
            return
            
        for config_path in self._widgets.keys():
            default = self._metadata.get_default_value(config_path)
            if default is not None:
                self._set_widget_value(self._widgets[config_path], default)
                self._config_data[config_path] = default
                
        self.configChanged.emit()
        
    def on_change(self, callback: Callable[[str, Any], None]):
        """
        Register callback for value changes.
        
        Args:
            callback: Function(config_path, new_value) to call on changes
        """
        self._on_change_callbacks.append(callback)
        
    def set_metadata(self, metadata):
        """
        Set or update metadata instance.
        
        Args:
            metadata: ConfigMetadata instance
        """
        self._metadata = metadata
        # Update tooltips
        for config_path, widget in self._widgets.items():
            tooltip = self._metadata.get_description(config_path)
            widget.setToolTip(tooltip)


class SimpleConfigDialog(QDialog):
    """
    Simple configuration dialog with save/cancel buttons.
    
    Usage:
        dialog = SimpleConfigDialog(config_data, parent)
        if dialog.exec_():
            new_config = dialog.get_config()
    """
    
    def __init__(
        self,
        config_data: Dict[str, Any],
        parent: Optional[QWidget] = None,
        metadata: Optional[Any] = None,
        title: str = "Configuration"
    ):
        """
        Initialize the configuration dialog.
        
        Args:
            config_data: Dictionary of config_path -> value
            parent: Parent widget
            metadata: Optional ConfigMetadata instance
            title: Dialog title
        """
        super().__init__(parent)
        
        self.setWindowTitle(title)
        self.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # Create editor widget
        self._editor = ConfigEditorWidget(config_data, metadata)
        layout.addWidget(self._editor)
        
        # Button box
        button_layout = QHBoxLayout()
        
        # Reset button
        self._reset_btn = QPushButton(self.tr("Reset to Defaults"))
        self._reset_btn.clicked.connect(self._on_reset)
        button_layout.addWidget(self._reset_btn)
        
        button_layout.addStretch()
        
        # Standard buttons
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        self._button_box.accepted.connect(self._on_save)
        self._button_box.rejected.connect(self.reject)
        button_layout.addWidget(self._button_box)
        
        layout.addLayout(button_layout)
        
        self._original_config = config_data.copy()
        
    def _on_save(self):
        """Handle save button."""
        # Validate all values
        config = self._editor.get_config()
        metadata = self._editor._metadata
        
        if metadata:
            errors = []
            for path, value in config.items():
                valid, error = metadata.validate_value(path, value)
                if not valid:
                    errors.append(f"{path}: {error}")
                    
            if errors:
                QMessageBox.warning(
                    self,
                    self.tr("Validation Error"),
                    self.tr("Please fix the following errors:") + "\n\n" + "\n".join(errors)
                )
                return
                
        self.accept()
        
    def _on_reset(self):
        """Handle reset button."""
        reply = QMessageBox.question(
            self,
            self.tr("Reset Configuration"),
            self.tr("Reset all values to defaults?"),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._editor.reset_to_defaults()
            
    def get_config(self) -> Dict[str, Any]:
        """Get the current configuration."""
        return self._editor.get_config()


class TabbedConfigDialog(QDialog):
    """
    Configuration dialog with tabbed groups.
    
    Each configuration group becomes a separate tab for better organization.
    """
    
    def __init__(
        self,
        config_data: Dict[str, Any],
        parent: Optional[QWidget] = None,
        metadata: Optional[Any] = None,
        title: str = "Configuration"
    ):
        """
        Initialize the tabbed configuration dialog.
        
        Args:
            config_data: Dictionary of config_path -> value
            parent: Parent widget
            metadata: Optional ConfigMetadata instance
            title: Dialog title
        """
        super().__init__(parent)
        
        self.setWindowTitle(title)
        self.setMinimumSize(600, 500)
        
        self._config_data = config_data.copy()
        self._metadata = metadata
        self._widgets: Dict[str, QWidget] = {}
        
        layout = QVBoxLayout(self)
        
        # Tab widget
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)
        
        self._build_tabs()
        
        # Button box
        button_layout = QHBoxLayout()
        
        self._reset_btn = QPushButton(self.tr("Reset to Defaults"))
        self._reset_btn.clicked.connect(self._on_reset)
        button_layout.addWidget(self._reset_btn)
        
        button_layout.addStretch()
        
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)
        button_layout.addWidget(self._button_box)
        
        layout.addLayout(button_layout)
        
    def _build_tabs(self):
        """Build tabs from configuration groups."""
        if not self._metadata:
            # Single tab for all
            editor = ConfigEditorWidget(self._config_data, None)
            self._tabs.addTab(editor, self.tr("General"))
            return
            
        groups = self._metadata.get_config_groups()
        
        for group_name in sorted(groups.keys()):
            paths = groups[group_name]
            
            # Filter config data for this group
            group_data = {
                path: self._config_data[path]
                for path in paths
                if path in self._config_data
            }
            
            if group_data:
                editor = ConfigEditorWidget(group_data, self._metadata)
                self._tabs.addTab(editor, group_name)
                
    def _on_reset(self):
        """Reset all tabs to defaults."""
        for i in range(self._tabs.count()):
            editor = self._tabs.widget(i)
            if hasattr(editor, 'reset_to_defaults'):
                editor.reset_to_defaults()
                
    def get_config(self) -> Dict[str, Any]:
        """Get configuration from all tabs."""
        result = {}
        for i in range(self._tabs.count()):
            editor = self._tabs.widget(i)
            if hasattr(editor, 'get_config'):
                result.update(editor.get_config())
        return result

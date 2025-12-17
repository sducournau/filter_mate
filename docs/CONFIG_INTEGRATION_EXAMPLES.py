"""
Example integration of the new configuration system into FilterMate UI

This file shows how to integrate the ConfigEditorWidget into the main plugin interface.
Add these snippets to filter_mate_app.py or filter_mate_dockwidget.py
"""

# ============================================================================
# Example 1: Add Settings Button to Action Bar
# ============================================================================

def setup_action_bar_with_settings(self):
    """
    Add a settings button to the action bar.
    
    Add this method to FilterMateApp or FilterMateDockWidget class.
    """
    from qgis.PyQt.QtWidgets import QPushButton
    from modules.config_editor_widget import SimpleConfigDialog
    
    # Create settings button
    settings_btn = QPushButton()
    settings_btn.setIcon(QIcon(os.path.join(self.plugin_dir, "icons", "settings.png")))
    settings_btn.setToolTip("Open Configuration Settings")
    settings_btn.setFixedSize(30, 30)
    
    # Connect to open config dialog
    settings_btn.clicked.connect(lambda: self.open_config_dialog())
    
    # Add to action bar layout
    self.action_bar_layout.addWidget(settings_btn)


def open_config_dialog(self):
    """
    Open the configuration dialog.
    
    Add this method to FilterMateApp or FilterMateDockWidget class.
    """
    from modules.config_editor_widget import SimpleConfigDialog
    
    # Create and show dialog
    dialog = SimpleConfigDialog(self.config_data, parent=self)
    
    # Listen for changes
    dialog.editor.config_changed.connect(self.on_config_changed)
    
    dialog.show()


def on_config_changed(self, config_path: str, new_value):
    """
    Handle configuration changes.
    
    Args:
        config_path: Dot-separated path (e.g., 'app.ui.theme.active')
        new_value: New value
    """
    print(f"Config changed: {config_path} = {new_value}")
    
    # Apply changes based on what was modified
    if config_path.startswith('app.ui.theme'):
        self.apply_theme()
    elif config_path == 'app.ui.profile':
        self.apply_ui_profile()
    elif config_path.startswith('app.buttons'):
        self.refresh_buttons()
    
    # Save configuration to file
    self.save_config()


# ============================================================================
# Example 2: Add Settings to Menu
# ============================================================================

def create_menu_with_settings(self):
    """
    Add settings option to plugin menu.
    
    Add this in filter_mate.py (main plugin file).
    """
    from qgis.PyQt.QtWidgets import QMenu, QAction
    
    # Create menu
    menu = QMenu("FilterMate")
    
    # Add actions
    open_action = QAction("Open FilterMate", self.iface.mainWindow())
    open_action.triggered.connect(self.show_dockwidget)
    menu.addAction(open_action)
    
    menu.addSeparator()
    
    # Settings action
    settings_action = QAction("Settings...", self.iface.mainWindow())
    settings_action.triggered.connect(self.open_settings)
    menu.addAction(settings_action)
    
    # Add to QGIS menu bar
    self.iface.addPluginToMenu("FilterMate", menu)


def open_settings(self):
    """Open settings dialog from menu."""
    from modules.config_editor_widget import SimpleConfigDialog
    from config.config import ENV_VARS
    
    dialog = SimpleConfigDialog(ENV_VARS["CONFIG_DATA"], parent=self.iface.mainWindow())
    dialog.show()


# ============================================================================
# Example 3: Embedded Config Panel in Dockwidget
# ============================================================================

def add_config_tab_to_dockwidget(self):
    """
    Add a configuration tab to the main dockwidget.
    
    Add this to FilterMateDockWidget class in filter_mate_dockwidget.py
    """
    from qgis.PyQt.QtWidgets import QTabWidget
    from modules.config_editor_widget import ConfigEditorWidget
    
    # Get or create tab widget
    if not hasattr(self, 'tab_widget'):
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)
    
    # Create config widget
    config_widget = ConfigEditorWidget(self.config_data)
    config_widget.config_changed.connect(self.on_config_changed)
    
    # Add as tab
    self.tab_widget.addTab(config_widget, "Settings")


# ============================================================================
# Example 4: Programmatic Config Access with Metadata
# ============================================================================

def example_using_metadata_in_code(self):
    """
    Examples of using metadata in application code.
    """
    from modules.config_helpers import (
        get_widget_type_for_config,
        get_config_description,
        get_config_allowed_values,
        validate_config_value_with_metadata
    )
    
    # Example 1: Show help tooltip for a parameter
    param_path = 'app.ui.theme.active'
    description = get_config_description(param_path)
    some_widget.setToolTip(description)
    
    # Example 2: Populate a combobox from metadata
    allowed_values = get_config_allowed_values('app.ui.profile')
    combo_box.clear()
    for value in allowed_values:
        combo_box.addItem(value)
    
    # Example 3: Validate user input before applying
    user_input = '999999'  # From some input field
    valid, error = validate_config_value_with_metadata(
        'app.buttons.icon_sizes.action',
        int(user_input)
    )
    
    if not valid:
        QMessageBox.warning(self, "Invalid Input", error)
        return
    
    # Apply the valid value
    self.apply_icon_size(int(user_input))


# ============================================================================
# Example 5: Create Custom Config Section
# ============================================================================

def create_custom_config_section(self):
    """
    Create a custom configuration section for specific features.
    
    This shows how to create a focused config UI for just certain parameters.
    """
    from qgis.PyQt.QtWidgets import QGroupBox, QFormLayout, QLabel
    from modules.config_metadata import get_config_metadata
    
    metadata = get_config_metadata()
    
    # Create group box for export settings
    export_group = QGroupBox("Export Configuration")
    layout = QFormLayout()
    
    # Get all export-related parameters
    export_params = [
        'app.export.style.format',
        'app.export.data.format',
        'app.export.layers_enabled',
        'app.export.projection_enabled'
    ]
    
    for param in export_params:
        meta = metadata.get_metadata(param)
        if not meta:
            continue
        
        label = QLabel(meta['user_friendly_label'])
        label.setToolTip(meta['description'])
        
        # Create appropriate widget
        widget = self.create_widget_for_param(param, meta)
        
        layout.addRow(label, widget)
    
    export_group.setLayout(layout)
    return export_group


def create_widget_for_param(self, param_path, meta):
    """
    Helper to create widget for a parameter.
    
    Args:
        param_path: Configuration path
        meta: Metadata dictionary
    
    Returns:
        QWidget appropriate for the parameter
    """
    from qgis.PyQt.QtWidgets import QCheckBox, QComboBox
    from modules.config_helpers import get_config_value
    
    widget_type = meta['widget_type']
    current_value = get_config_value(self.config_data, *param_path.split('.'))
    
    if widget_type == 'checkbox':
        widget = QCheckBox()
        widget.setChecked(bool(current_value))
        widget.stateChanged.connect(
            lambda state: self.on_param_changed(param_path, state == Qt.Checked)
        )
        return widget
    
    elif widget_type == 'combobox':
        widget = QComboBox()
        allowed = meta['validation'].get('allowed_values', [])
        for value in allowed:
            widget.addItem(str(value), value)
        index = widget.findData(current_value)
        if index >= 0:
            widget.setCurrentIndex(index)
        widget.currentIndexChanged.connect(
            lambda: self.on_param_changed(param_path, widget.currentData())
        )
        return widget
    
    # Add more widget types as needed
    return QLabel("Unsupported widget type")


def on_param_changed(self, param_path, new_value):
    """Handle parameter change."""
    from modules.config_helpers import set_config_value
    
    keys = param_path.split('.')
    set_config_value(self.config_data, new_value, *keys)
    
    # Trigger refresh if needed
    if param_path.startswith('app.export'):
        self.refresh_export_options()


# ============================================================================
# Example 6: Display Config Info in About Dialog
# ============================================================================

def add_config_info_to_about_dialog(self):
    """
    Show configuration information in About dialog.
    """
    from modules.config_helpers import get_all_configurable_paths
    
    about_text = "<h2>FilterMate Configuration</h2>"
    
    # Count parameters
    all_params = get_all_configurable_paths()
    about_text += f"<p>Total configurable parameters: <b>{len(all_params)}</b></p>"
    
    # Show current important settings
    from modules.config_helpers import (
        get_ui_profile,
        get_active_theme,
        get_feedback_level
    )
    
    about_text += "<h3>Current Settings:</h3>"
    about_text += "<ul>"
    about_text += f"<li>UI Profile: <b>{get_ui_profile(self.config_data)}</b></li>"
    about_text += f"<li>Theme: <b>{get_active_theme(self.config_data)}</b></li>"
    about_text += f"<li>Feedback Level: <b>{get_feedback_level(self.config_data)}</b></li>"
    about_text += "</ul>"
    
    about_text += "<p><i>Use Settings menu to configure FilterMate</i></p>"
    
    return about_text


# ============================================================================
# Example 7: Export/Import Configuration
# ============================================================================

def export_configuration(self):
    """Export current configuration to JSON file."""
    from qgis.PyQt.QtWidgets import QFileDialog
    import json
    
    filename, _ = QFileDialog.getSaveFileName(
        self,
        "Export Configuration",
        "",
        "JSON Files (*.json)"
    )
    
    if filename:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.config_data, f, indent=2)
        
        QMessageBox.information(
            self,
            "Export Successful",
            f"Configuration exported to:\n{filename}"
        )


def import_configuration(self):
    """Import configuration from JSON file."""
    from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox
    import json
    from modules.config_helpers import validate_config_value_with_metadata
    
    filename, _ = QFileDialog.getOpenFileName(
        self,
        "Import Configuration",
        "",
        "JSON Files (*.json)"
    )
    
    if not filename:
        return
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            imported_config = json.load(f)
        
        # Validate imported config
        # (Add validation logic here)
        
        # Apply imported config
        self.config_data.update(imported_config)
        self.apply_all_config()
        
        QMessageBox.information(
            self,
            "Import Successful",
            "Configuration imported and applied successfully!"
        )
        
    except Exception as e:
        QMessageBox.critical(
            self,
            "Import Failed",
            f"Error importing configuration:\n{str(e)}"
        )


# ============================================================================
# USAGE SUMMARY
# ============================================================================

"""
To integrate the new configuration system into FilterMate:

1. ADD SETTINGS BUTTON
   - Copy setup_action_bar_with_settings() method
   - Call it during UI initialization
   - Add settings icon to icons/ folder

2. IMPLEMENT HANDLERS
   - Copy open_config_dialog() method
   - Copy on_config_changed() method
   - Customize to refresh your specific UI elements

3. ADD MENU ITEM (Optional)
   - Copy create_menu_with_settings() to main plugin file
   - Call during plugin initialization

4. USE METADATA IN CODE
   - Import config_helpers functions
   - Replace direct config access with helpers
   - Use validation before applying user input

5. TEST
   - Open settings dialog
   - Change various parameters
   - Verify UI updates correctly
   - Check validation works

Example minimal integration:

    # In FilterMateApp.__init__ or similar:
    
    from modules.config_editor_widget import SimpleConfigDialog
    
    # Add settings button
    settings_btn = QPushButton("⚙")
    settings_btn.clicked.connect(self.open_settings)
    self.toolbar.addWidget(settings_btn)
    
    # Handler
    def open_settings(self):
        dialog = SimpleConfigDialog(self.config_data, self)
        dialog.editor.config_changed.connect(
            lambda path, val: print(f"Changed: {path} = {val}")
        )
        dialog.show()

That's it! The system handles the rest automatically.
"""

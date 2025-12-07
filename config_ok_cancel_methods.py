# Temporary file with the new methods to integrate into filter_mate_dockwidget.py
# 
# INTEGRATION NOTES:
# 1. These methods should be added to the FilterMateDockWidget class
# 2. The existing code in data_changed_configuration_model() lines ~970-1180 should be removed
# 3. Connect signals in connect_widgets_signals():
#    self.widgets["DOCK"]["CONFIGURATION_BUTTONBOX"]["WIDGET"].accepted.connect(self.on_config_buttonbox_accepted)
#    self.widgets["DOCK"]["CONFIGURATION_BUTTONBOX"]["WIDGET"].rejected.connect(self.on_config_buttonbox_rejected)
# 4. Ensure these imports are present at the top of filter_mate_dockwidget.py:
#    - from qgis.utils import iface
#    - from .modules.logging_config import logger
#    - import json
#    - from .modules.qt_json_view.model import JsonModel
#
# BUTTON STATE LOGIC:
# - Buttons are DISABLED by default (manage_configuration_model)
# - Buttons are ENABLED when user edits a value (data_changed_configuration_model)
# - Buttons are DISABLED after OK (apply_pending_config_changes)
# - Buttons are DISABLED after Cancel (cancel_pending_config_changes)

def apply_pending_config_changes(self):
    """Apply all pending configuration changes when OK button is clicked"""
    
    if not self.config_changes_pending or not self.pending_config_changes:
        logger.info("No pending configuration changes to apply")
        return
    
    logger.info(f"Applying {len(self.pending_config_changes)} pending configuration change(s)")
    
    changes_summary = []
    
    for change in self.pending_config_changes:
        items_keys_values_path = change['path']
        index = change['index']
        item = change['item']
        
        # Handle ICONS changes
        if 'ICONS' in items_keys_values_path:
            try:
                self.set_widget_icon(items_keys_values_path)
                changes_summary.append(f"Icon: {' → '.join(items_keys_values_path[-2:])}")
            except Exception as e:
                logger.error(f"Error applying ICONS change: {e}")
        
        # Handle ACTIVE_THEME changes
        if 'ACTIVE_THEME' in items_keys_values_path:
            try:
                value_item = self.config_view.model.itemFromIndex(index.siblingAtColumn(1))
                value_data = value_item.data(QtCore.Qt.UserRole)
                
                if isinstance(value_data, dict) and 'value' in value_data:
                    new_theme_value = value_data['value']
                else:
                    new_theme_value = value_item.data(QtCore.Qt.DisplayRole) if value_item else None
                
                if new_theme_value:
                    from .modules.ui_styles import StyleLoader
                    
                    if new_theme_value == 'auto':
                        detected_theme = StyleLoader.detect_qgis_theme()
                        StyleLoader.set_theme_from_config(self.dockWidgetContents, self.CONFIG_DATA, detected_theme)
                    else:
                        StyleLoader.set_theme_from_config(self.dockWidgetContents, self.CONFIG_DATA, new_theme_value)
                    
                    changes_summary.append(f"Theme: {new_theme_value}")
            except Exception as e:
                logger.error(f"Error applying ACTIVE_THEME change: {e}")
        
        # Handle UI_PROFILE changes
        if 'UI_PROFILE' in items_keys_values_path:
            try:
                value_item = self.config_view.model.itemFromIndex(index.siblingAtColumn(1))
                value_data = value_item.data(QtCore.Qt.UserRole)
                
                if isinstance(value_data, dict) and 'value' in value_data:
                    new_profile_value = value_data['value']
                else:
                    new_profile_value = value_item.data(QtCore.Qt.DisplayRole) if value_item else None
                
                if new_profile_value and UI_CONFIG_AVAILABLE:
                    from .modules.ui_config import UIConfig, DisplayProfile
                    
                    if new_profile_value == 'compact':
                        UIConfig.set_profile(DisplayProfile.COMPACT)
                    elif new_profile_value == 'normal':
                        UIConfig.set_profile(DisplayProfile.NORMAL)
                    elif new_profile_value == 'auto':
                        detected_profile = UIConfig.detect_optimal_profile()
                        UIConfig.set_profile(detected_profile)
                    
                    self.apply_dynamic_dimensions()
                    changes_summary.append(f"UI Profile: {new_profile_value}")
            except Exception as e:
                logger.error(f"Error applying UI_PROFILE change: {e}")
        
        # Handle STYLES_TO_EXPORT changes
        if 'STYLES_TO_EXPORT' in items_keys_values_path:
            try:
                value_item = self.config_view.model.itemFromIndex(index.siblingAtColumn(1))
                value_data = value_item.data(QtCore.Qt.UserRole)
                
                if isinstance(value_data, dict) and 'value' in value_data:
                    new_style_value = value_data['value']
                else:
                    new_style_value = value_item.data(QtCore.Qt.DisplayRole) if value_item else None
                
                if new_style_value and 'STYLE_TO_EXPORT' in self.widgets.get('EXPORTING', {}):
                    style_combo = self.widgets["EXPORTING"]["STYLE_TO_EXPORT"]["WIDGET"]
                    index_to_set = style_combo.findText(new_style_value)
                    if index_to_set >= 0:
                        style_combo.setCurrentIndex(index_to_set)
                        changes_summary.append(f"Export Style: {new_style_value}")
            except Exception as e:
                logger.error(f"Error applying STYLES_TO_EXPORT change: {e}")
        
        # Handle DATATYPE_TO_EXPORT changes
        if 'DATATYPE_TO_EXPORT' in items_keys_values_path:
            try:
                value_item = self.config_view.model.itemFromIndex(index.siblingAtColumn(1))
                value_data = value_item.data(QtCore.Qt.UserRole)
                
                if isinstance(value_data, dict) and 'value' in value_data:
                    new_format_value = value_data['value']
                else:
                    new_format_value = value_item.data(QtCore.Qt.DisplayRole) if value_item else None
                
                if new_format_value and 'DATATYPE_TO_EXPORT' in self.widgets.get('EXPORTING', {}):
                    format_combo = self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"]
                    index_to_set = format_combo.findText(new_format_value)
                    if index_to_set >= 0:
                        format_combo.setCurrentIndex(index_to_set)
                        changes_summary.append(f"Export Format: {new_format_value}")
            except Exception as e:
                logger.error(f"Error applying DATATYPE_TO_EXPORT change: {e}")
    
    # Save configuration to file
    self.save_configuration_model()
    
    # Clear pending changes
    self.pending_config_changes = []
    self.config_changes_pending = False
    
    # Disable buttons after applying changes
    if hasattr(self, 'buttonBox'):
        self.buttonBox.setEnabled(False)
        logger.info("Configuration buttons disabled (changes applied)")
    
    # Show summary message
    if changes_summary:
        summary_text = ", ".join(changes_summary)
        iface.messageBar().pushSuccess(
            "FilterMate",
            f"Configuration applied: {summary_text}",
            5
        )
        logger.info(f"Configuration changes applied successfully: {summary_text}")
    else:
        iface.messageBar().pushInfo(
            "FilterMate",
            "Configuration saved",
            3
        )


def cancel_pending_config_changes(self):
    """Cancel pending configuration changes when Cancel button is clicked"""
    
    if not self.config_changes_pending or not self.pending_config_changes:
        logger.info("No pending configuration changes to cancel")
        return
    
    logger.info(f"Cancelling {len(self.pending_config_changes)} pending configuration change(s)")
    
    # Reload configuration from file to revert changes in tree view
    try:
        with open(self.plugin_dir + '/config/config.json', 'r') as infile:
            self.CONFIG_DATA = json.load(infile)
        
        # Recreate model with original data
        self.config_model = JsonModel(
            data=self.CONFIG_DATA, 
            editable_keys=True, 
            editable_values=True, 
            plugin_dir=self.plugin_dir
        )
        
        # Update view
        if hasattr(self, 'config_view') and self.config_view is not None:
            self.config_view.setModel(self.config_model)
            self.config_view.model = self.config_model
        
        # Clear pending changes
        self.pending_config_changes = []
        self.config_changes_pending = False
        
        # Disable buttons after cancelling changes
        if hasattr(self, 'buttonBox'):
            self.buttonBox.setEnabled(False)
            logger.info("Configuration buttons disabled (changes cancelled)")
        
        iface.messageBar().pushInfo(
            "FilterMate",
            "Configuration changes cancelled and reverted",
            3
        )
        logger.info("Configuration changes cancelled successfully")
        
    except Exception as e:
        logger.error(f"Error cancelling configuration changes: {e}")
        import traceback
        logger.error(traceback.format_exc())
        iface.messageBar().pushCritical(
            "FilterMate",
            f"Error cancelling changes: {str(e)}",
            5
        )


def on_config_buttonbox_accepted(self):
    """Called when OK button is clicked"""
    logger.info("Configuration OK button clicked")
    self.apply_pending_config_changes()


def on_config_buttonbox_rejected(self):
    """Called when Cancel button is clicked"""
    logger.info("Configuration Cancel button clicked")
    self.cancel_pending_config_changes()

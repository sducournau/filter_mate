from qgis.PyQt import QtGui, QtCore, QtWidgets
import sys
from . import delegate
from . import themes
from .datatypes import match_type, TypeRole, StrType


# Default settings for JsonView
DEFAULT_JSON_VIEW_SETTINGS = {
    'theme': 'auto',
    'font_size': 9,
    'alternating_rows': True,
    'editable_keys': True,
    'editable_values': True,
    'column_width_key': 180,
    'column_width_value': 240,
    'min_column_width': 120,
}


class JsonView(QtWidgets.QTreeView):
    """
    Tree to display the JsonModel.
    
    Supports configuration via settings dictionary for integration
    with FilterMate's configuration system.
    
    Args:
        model: The JsonModel to display
        plugin_dir: Path to the plugin directory (optional)
        settings: Dictionary of view settings (optional)
        parent: Parent widget (optional)
    
    Settings dictionary keys:
        - theme (str): Color theme name or 'auto'
        - font_size (int): Font size in points (8-16)
        - alternating_rows (bool): Show alternating row colors
        - editable_keys (bool): Allow editing keys
        - editable_values (bool): Allow editing values
        - column_width_key (int): Width of key column
        - column_width_value (int): Width of value column
    """
    onLeaveEvent = QtCore.pyqtSignal()
    settingsChanged = QtCore.pyqtSignal(dict)  # Emitted when settings change

    def __init__(self, model, plugin_dir=None, settings=None, parent=None):
        super(JsonView, self).__init__(parent)
        self.model = model
        self.plugin_dir = plugin_dir
        
        # Merge provided settings with defaults
        self._settings = DEFAULT_JSON_VIEW_SETTINGS.copy()
        if settings:
            self._settings.update(settings)
        
        # CRITICAL: Set model IMMEDIATELY to avoid Qt crashes
        if model is not None:
            self.setModel(model)
        
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self.setItemDelegate(delegate.JsonDelegate())
        
        # Apply settings
        self._apply_settings()
    
    def _apply_settings(self):
        """Apply all settings from the settings dictionary."""
        # Apply theme
        theme_name = self._settings.get('theme', 'auto')
        if theme_name == 'auto':
            self._apply_theme_stylesheet()
        else:
            self.set_theme(theme_name)
            self._apply_theme_stylesheet()
        
        # Apply font size
        font_size = self._settings.get('font_size', 9)
        font = self.font()
        font.setPointSize(font_size)
        self.setFont(font)
        
        # Apply alternating rows
        self.setAlternatingRowColors(self._settings.get('alternating_rows', True))
        self.setUniformRowHeights(False)
        
        # Configure columns
        header = self.header()
        header.setStretchLastSection(False)
        header.setVisible(True)
        header.setDefaultAlignment(QtCore.Qt.AlignLeft)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Interactive)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Interactive)
        
        # Apply column widths from settings
        header.resizeSection(0, self._settings.get('column_width_key', 180))
        header.resizeSection(1, self._settings.get('column_width_value', 240))
        header.setMinimumSectionSize(self._settings.get('min_column_width', 120))
    
    def get_settings(self):
        """
        Get current view settings.
        
        Returns:
            dict: Current settings dictionary
        """
        return self._settings.copy()
    
    def update_settings(self, settings):
        """
        Update view settings.
        
        Args:
            settings (dict): Settings to update
        """
        self._settings.update(settings)
        self._apply_settings()
        self.settingsChanged.emit(self._settings)
    
    def set_setting(self, key, value):
        """
        Set a single setting value.
        
        Args:
            key (str): Setting key
            value: Setting value
        """
        self._settings[key] = value
        self._apply_settings()

    def _apply_theme_stylesheet(self):
        """Apply stylesheet based on detected theme (dark/light)."""
        # Détection simple du thème basée sur la palette
        try:
            from qgis.core import QgsApplication
            palette = QgsApplication.palette()
            bg_color = palette.color(QtGui.QPalette.Window)
            is_dark = bg_color.lightness() < 128
        except (ImportError, AttributeError):
            is_dark = False
        
        if is_dark:
            # Thème sombre optimisé
            self.setStyleSheet("""
                QTreeView {
                    font-size: 9pt;
                    background-color: #1E1E1E;
                    alternate-background-color: #252526;
                    selection-background-color: #264F78;
                    selection-color: #FFFFFF;
                    border: 1px solid #3E3E42;
                    gridline-color: #3E3E42;
                    color: #D4D4D4;
                }
                QTreeView::item {
                    padding: 3px;
                    min-height: 22px;
                    border-bottom: 1px solid #2D2D30;
                }
                QTreeView::item:hover {
                    background-color: #2A2D2E;
                }
                QTreeView::item:selected {
                    background-color: #264F78;
                    color: #FFFFFF;
                }
                QTreeView::item:selected:hover {
                    background-color: #094771;
                }
                QTreeView::branch {
                    background-color: transparent;
                }
                QHeaderView::section {
                    background-color: #252526;
                    padding: 4px;
                    border: 1px solid #3E3E42;
                    border-left: none;
                    font-weight: bold;
                    font-size: 9pt;
                    min-height: 24px;
                    color: #CCCCCC;
                }
                QHeaderView::section:first {
                    border-left: 1px solid #3E3E42;
                }
            """)
        else:
            # Thème clair
            self.setStyleSheet("""
                QTreeView {
                    font-size: 9pt;
                    background-color: #ffffff;
                    alternate-background-color: #f5f5f5;
                    selection-background-color: #0078d4;
                    selection-color: white;
                    border: 2px solid #999999;
                    gridline-color: #d0d0d0;
                }
                QTreeView::item {
                    padding: 3px;
                    min-height: 22px;
                    border-bottom: 1px solid #e0e0e0;
                }
                QTreeView::item:hover {
                    background-color: #e5f3ff;
                }
                QTreeView::item:selected {
                    background-color: #0078d4;
                    color: white;
                }
                QTreeView::branch {
                    background-color: transparent;
                }
                QHeaderView::section {
                    background-color: #f0f0f0;
                    padding: 4px;
                    border: 1px solid #c0c0c0;
                    border-left: none;
                    font-weight: bold;
                    font-size: 9pt;
                    min-height: 24px;
                }
                QHeaderView::section:first {
                    border-left: 1px solid #c0c0c0;
                }
            """)

    # def leaveEvent(self, QEvent):
    #     self.onLeaveEvent.emit()

    
    def _menu(self, position):
        """Show the actions of the DataType (if any)."""
        menu = QtWidgets.QMenu()
        index = self.indexAt(position)
        data = index.data(TypeRole)
        if data is None:
            return
        actions = data.actions(index)
        if actions is not None and len(actions) > 0:
            menu.addActions(actions)
        action = menu.exec_(self.viewport().mapToGlobal(position))
        if action:
            action_data = action.data()
            item = self.model.itemFromIndex(index)

            if action_data is not None:
                if action.text() == "Change":
                    if len(action_data) == 2:
                        item.setData(action_data[0], QtCore.Qt.DisplayRole)
                    elif len(action_data) == 3:
                        item.setData(action_data[0], QtCore.Qt.DisplayRole)
                        item.setData(action_data[1], QtCore.Qt.UserRole)

            if action.text() == "Rename":
                self.edit(index)

            if action.text() == "Add child":

                self.model.addData(item)

            if action.text() == "Insert sibling up":
                self.model.addData(item,'up')


            if action.text() == "Insert sibling down":
                self.model.addData(item,'down')


            if action.text() == "Remove":

                self.model.removeData(item)

    def set_theme(self, theme_name):
        """
        Change the color theme for the JSON view.
        
        Args:
            theme_name (str): Name of the theme to apply (e.g., 'monokai', 'nord')
        
        Returns:
            bool: True if theme was changed successfully
        """
        if themes.set_theme(theme_name):
            # Refresh the view to apply new colors
            self.refresh_colors()
            return True
        return False
    
    def get_current_theme_name(self):
        """
        Get the name of the currently active theme.
        
        Returns:
            str: Name of the current theme
        """
        return themes.get_current_theme().name
    
    def get_available_themes(self):
        """
        Get list of available theme names.
        
        Returns:
            dict: Dictionary mapping theme keys to display names
        """
        return themes.get_theme_display_names()
    
    def refresh_colors(self):
        """
        Refresh all item colors in the view based on the current theme.
        """
        if not self.model:
            return
        
        # Recursively update colors for all items
        def update_item_colors(item):
            if item is None:
                return
            
            # Update the item's color if it has a DataType
            data_type = item.data(TypeRole)
            if data_type is not None:
                item.setData(QtGui.QBrush(data_type.get_color()), QtCore.Qt.ForegroundRole)
            
            # Update children
            for row in range(item.rowCount()):
                for col in range(item.columnCount()):
                    child = item.child(row, col)
                    if child:
                        update_item_colors(child)
        
        # Update all root items
        for row in range(self.model.rowCount()):
            for col in range(self.model.columnCount()):
                item = self.model.item(row, col)
                if item:
                    update_item_colors(item)
        
        # Force view update
        self.viewport().update()
    
    def is_dark_theme(self):
        """
        Detect if the current system/QGIS theme is dark.
        
        Returns:
            bool: True if dark theme is detected
        """
        try:
            from qgis.core import QgsApplication
            palette = QgsApplication.palette()
            bg_color = palette.color(QtGui.QPalette.Window)
            return bg_color.lightness() < 128
        except (ImportError, AttributeError):
            return False
    
    def get_recommended_theme_for_ui(self, ui_theme=None):
        """
        Get recommended JSON View theme based on UI theme.
        
        Args:
            ui_theme (str): UI theme name ('auto', 'dark', 'light', 'default')
        
        Returns:
            str: Recommended JSON View theme name
        """
        # Theme mapping
        mapping = {
            'auto': 'dracula' if self.is_dark_theme() else 'default',
            'dark': 'dracula',
            'light': 'solarized_light',
            'default': 'default',
        }
        
        if ui_theme is None:
            ui_theme = 'auto'
        
        return mapping.get(ui_theme, 'default')
    
    def apply_config_settings(self, config_manager):
        """
        Apply settings from a ConfigManager instance.
        
        Args:
            config_manager: FilterMate ConfigManager instance
        
        This method bridges the plugin's configuration system with
        the JSON View settings.
        """
        try:
            json_view_settings = config_manager.get_json_view_settings()
            self.update_settings(json_view_settings)
        except AttributeError:
            # ConfigManager doesn't have this method (old version)
            pass
    
    def save_column_widths(self):
        """
        Get current column widths for saving to config.
        
        Returns:
            dict: Dictionary with column_width_key and column_width_value
        """
        header = self.header()
        return {
            'column_width_key': header.sectionSize(0),
            'column_width_value': header.sectionSize(1),
        }


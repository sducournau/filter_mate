from qgis.PyQt import QtGui, QtCore, QtWidgets
import sys
from . import delegate
from . import themes
from .datatypes import match_type, TypeRole, StrType



class JsonView(QtWidgets.QTreeView):
    """Tree to display the JsonModel."""
    onLeaveEvent = QtCore.pyqtSignal()

    def __init__(self, model, plugin_dir=None, parent=None):
        super(JsonView, self).__init__(parent)
        self.model = model
        self.plugin_dir = plugin_dir
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self.setItemDelegate(delegate.JsonDelegate())


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
        if actions != None and len(actions) > 0:
            menu.addActions(actions)
        action = menu.exec_(self.viewport().mapToGlobal(position))
        if action:
            action_data = action.data()
            item = self.model.itemFromIndex(index)

            if action_data != None:
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

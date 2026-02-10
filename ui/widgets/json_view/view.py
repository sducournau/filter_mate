from qgis.PyQt import QtGui, QtCore, QtWidgets
from . import delegate
from . import themes
from .datatypes import TypeRole


class JsonView(QtWidgets.QTreeView):
    """Tree to display the JsonModel."""
    onLeaveEvent = QtCore.pyqtSignal()

    def __init__(self, model, plugin_dir=None, parent=None):
        super(JsonView, self).__init__(parent)
        self.model = model
        self.plugin_dir = plugin_dir

        # CRITICAL: Set model IMMEDIATELY to avoid Qt crashes
        if model is not None:
            self.setModel(model)

        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self.setItemDelegate(delegate.JsonDelegate())

        # Amélioration de la visibilité avec support du thème dark
        self._apply_theme_stylesheet()

        # Configuration additionnelle pour la lisibilité
        self.setAlternatingRowColors(True)
        self.setUniformRowHeights(False)
        font = self.font()
        font.setPointSize(9)
        self.setFont(font)

        # Configuration des colonnes pour meilleure visibilité
        header = self.header()
        header.setStretchLastSection(False)
        header.setVisible(True)
        header.setDefaultAlignment(QtCore.Qt.AlignLeft)
        # Colonne Property (clé): largeur interactive avec minimum
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Interactive)
        # Colonne Value: largeur interactive
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Interactive)
        # Définir des largeurs initiales optimales
        header.resizeSection(0, 180)
        header.resizeSection(1, 240)
        header.setMinimumSectionSize(120)

    def _apply_theme_stylesheet(self):
        """Apply stylesheet based on detected theme (dark/light)."""
        # Check if theme was forced externally
        if hasattr(self, '_forced_dark') and self._forced_dark is not None:
            is_dark = self._forced_dark
        else:
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
            # Convert string actions to QAction objects if needed
            qactions = []
            for action in actions:
                if isinstance(action, str):
                    qaction = QtWidgets.QAction(action, None)
                    qactions.append(qaction)
                else:
                    qactions.append(action)
            menu.addActions(qactions)
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
                self.model.addData(item, 'up')

            if action.text() == "Insert sibling down":
                self.model.addData(item, 'down')

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

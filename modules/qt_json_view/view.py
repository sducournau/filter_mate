from qgis.PyQt import QtGui, QtCore, QtWidgets
import sys
from . import delegate
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

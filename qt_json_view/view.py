from qgis.PyQt import QtGui, QtCore, QtWidgets
import sys
from ..config import *
from . import delegate
from .datatypes import match_type, TypeRole, StrType




class JsonView(QtWidgets.QTreeView):
    """Tree to display the JsonModel."""
    onLeaveEvent = QtCore.pyqtSignal()

    def __init__(self, model,  parent=None):
        super(JsonView, self).__init__(parent=parent)
        self.model = model

        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self.setItemDelegate(delegate.JsonDelegate())
        self.setMouseTracking(True)



    def leaveEvent(self, QEvent):
        self.onLeaveEvent.emit()



    def _menu(self, position):
        """Show the actions of the DataType (if any)."""
        menu = QtWidgets.QMenu()
        index = self.indexAt(position)
        data = index.data(TypeRole)
        if data is None:
            return
        for action in data.actions(index):
            menu.addAction(action)
        action = menu.exec_(self.viewport().mapToGlobal(position))
        if action:
            indexes = self.selectedIndexes()
            item = self.model.itemFromIndex(index)


            if action.text() == "Rename":
                self.edit(index)

            if action.text() == "Add child":
                print(item.data(), item, data, index)


                if item.data(0) == 'WIDGETS':
                    self.model.addData(item,widgets=True)
                    print("widget added !")

                else:
                    self.model.addData(item)

            if action.text() == "Insert sibling up":
                self.model.addData(item,'up')


            if action.text() == "Insert sibling down":
                self.model.addData(item,'down')


            if action.text() == "Remove":
                if item.parent().data(0) == 'WIDGETS':
                    self.model.removeData(item,widgets=True)

                    print("widget removed !")

                else:
                    self.model.removeData(item)

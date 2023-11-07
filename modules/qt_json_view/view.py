from qgis.PyQt import QtGui, QtCore, QtWidgets
import sys
import os
from shutil import copyfile
from . import delegate
from .datatypes import match_type, TypeRole, StrType
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *



class JsonView(QtWidgets.QTreeView):
    """Tree to display the JsonModel."""
    onLeaveEvent = QtCore.pyqtSignal()

    def __init__(self, model, plugin_dir=None, parent=None):
        super(JsonView, self).__init__(parent=parent)
        self.model = model
        self.plugin_dir = plugin_dir
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self.setItemDelegate(delegate.JsonDelegate())
        self.setMouseTracking(True)


    def leaveEvent(self, QEvent):
        self.onLeaveEvent.emit()

    # def checkDrag(self):
    #     pos = QCursor.pos()
    #     # slightly move the mouse to trigger dragMoveEvent
    #     QCursor.setPos(pos + QPoint(1, 1))
    #     # restore the previous position
    #     QCursor.setPos(pos)


    # def mouseMoveEvent(self, event):
    #     if event.buttons() != Qt.RightButton:
    #         return
    #     if ((event.pos() - self.dragStartPosition).manhattanLength() < QApplication.startDragDistance()):
    #         return

    #     # a local timer, it will be deleted when the function returns
    #     dragTimer = QTimer(interval=100, timeout=self.checkDrag)
    #     dragTimer.start()
    #     self.startDrag(Qt.CopyAction)

    # def dragMoveEvent(self, event):
    #     print(event)
    #     print(event.mimeData())
    #     print(event.mimeData().urls())
    #     if not event.mimeData().hasUrls():
    #         event.ignore()
    #         return
    #     event.setDropAction(Qt.CopyAction)
        
    #     for url in event.mimeData().urls():
    #         if os.path.isfile(url):
    #             copyfile(url, self.plugin_dir + '/icons/' + os.path.basename(url))
    #     event.accept()


    
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

from qgis.PyQt import QtGui, QtWidgets, QtCore
import json
from .datatypes import set_plugin_dir, match_type, TypeRole, ListType, DictType

class InputWindow(QtWidgets.QDialog):
    """Main Window."""
    def __init__(self):
        """Initializer."""
        super().__init__()
        self.setWindowTitle("Python Menus & Toolbars")
        self.resize(400, 200)



        self.layout = QtWidgets.QGridLayout(self)

        QBtn = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        self.buttonBox = QtWidgets.QDialogButtonBox(QBtn)

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.key = QtWidgets.QLineEdit()
        self.value = QtWidgets.QTextEdit()
        self.keyLabel = QtWidgets.QLabel("Propriété")
        self.valueLabel = QtWidgets.QLabel("Valeur")

        self.layout.addWidget(self.keyLabel, 0, 0)
        self.layout.addWidget(self.key, 0, 1)
        self.layout.addWidget(self.valueLabel, 1, 0)
        self.layout.addWidget(self.value, 1, 1)
        self.layout.addWidget(self.buttonBox, 2, 1)


class JsonModel(QtGui.QStandardItemModel):
    """Represent JSON-serializable data."""

    def __init__(
            self,
            data=None,
            editable_keys=False,
            editable_values=False,
            plugin_dir=None,
            parent=None
            ):
        super(JsonModel, self).__init__(parent=parent)
        self.plugin_dir = plugin_dir
        set_plugin_dir(self.plugin_dir)
        if data is not None:
            self.init(data, editable_keys, editable_values)

    def init(self, data, editable_keys=False, editable_values=False):
        """Convert the data to items and populate the model."""
        self.clear()
        self.setHorizontalHeaderLabels(['Property', 'Value'])
        self.editable_keys = editable_keys
        self.editable_values = editable_values
        parent = self.invisibleRootItem()
        type_ = match_type(data)
        parent.setData(type_, TypeRole)
        type_.next(model=self, data=data, parent=parent)

    def serialize(self):
        """Assemble the model back into a dict or list."""
        parent = self.invisibleRootItem()
        type_ = parent.data(TypeRole)
        if isinstance(type_, ListType):
            data = []
        elif isinstance(type_, DictType):
            data = {}
        type_.serialize(model=self, item=parent, data=data, parent=parent)
        return data

    def addData(self, item, direction='insert', widgets=False):
        self.input = InputWindow()

        if self.input.exec_() == QtWidgets.QDialog.Accepted:

            key = self.input.key.text()
            try:
                value = json.loads(self.input.value.toPlainText())
            except (json.JSONDecodeError, ValueError):
                # If JSON parsing fails, treat as plain text
                value = self.input.value.toPlainText()

            type_ = match_type(value)
            key_item = type_.key_item(key, datatype=type_, model=self)
            value_item = type_.value_item(value, self, key)
            if item.parent() is None:
                parent = self.invisibleRootItem()
            else:
                parent = item.parent()

            if direction == 'insert':
                item.appendRow([key_item, value_item])
            elif direction == 'up':
                parent.insertRow(item.row(), [key_item, value_item])
            elif direction == 'down':
                parent.insertRow(item.row() + 1, [key_item, value_item])

    def removeData(self, item, widgets=False):

        if item.parent() is None:
            parent = self.invisibleRootItem()
        else:
            parent = item.parent()
        parent.removeRow(item.row())


class JsonSortFilterProxyModel(QtCore.QSortFilterProxyModel):
    """Show ALL occurences by keeping the parents of each occurence visible."""

    def filterAcceptsRow(self, sourceRow, sourceParent):
        """Accept the row if the parent has been accepted."""
        index = self.sourceModel().index(sourceRow, self.filterKeyColumn(), sourceParent)
        return self.accept_index(index)

    def accept_index(self, index):
        if index.isValid():
            text = str(index.data(self.filterRole()))
            if self.filterRegExp().indexIn(text) >= 0:
                return True
            for row in range(index.model().rowCount(index)):
                if self.accept_index(index.model().index(row, self.filterKeyColumn(), index)):
                    return True
        return False

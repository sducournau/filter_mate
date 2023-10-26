from qgis.PyQt import QtGui, QtWidgets, QtCore
import json
from ..config import *
from .datatypes import match_type, TypeRole, ListType, DictType

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

class InputWindowWidgets(QtWidgets.QDialog):
    """Main Window."""
    def __init__(self):
        """Initializer."""
        super().__init__()
        self.setWindowTitle("Add property and value")
        self.resize(400, 200)



        self.layout = QtWidgets.QGridLayout(self)

        QBtn = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        self.buttonBox = QtWidgets.QDialogButtonBox(QBtn)

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.key =  QtWidgets.QComboBox()


        list = ["checkableComboBox", "searchComboBox","expressionWidget"]
        self.key.clear()
        self.key.addItems(list)

        #self.value = QtWidgets.QgsCheckableTextEdit()
        self.keyLabel = QtWidgets.QLabel("Select a widget")
        #self.valueLabel = QtWidgets.QLabel("Value")

        self.layout.addWidget(self.keyLabel, 0, 0)
        self.layout.addWidget(self.key, 0, 1)
        #self.layout.addWidget(self.valueLabel, 1, 0)
        #self.layout.addWidget(self.value, 1, 1)
        self.layout.addWidget(self.buttonBox, 1, 1)






class JsonModel(QtGui.QStandardItemModel):
    """Represent JSON-serializable data."""

    def __init__(
            self, parent=None,
            data=None,
            editable_keys=False,
            editable_values=False):
        super(JsonModel, self).__init__(parent=parent)
        if data is not None:
            self.init(data, editable_keys, editable_values)

    def init(self, data, editable_keys=False, editable_values=False):
        """Convert the data to items and populate the model."""
        self.clear()
        self.setHorizontalHeaderLabels(['Propriété', 'Valeur'])
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
        global CONFIG_SCOPE
        CONFIG_SCOPE = True
        print(item.data(0))
        if widgets:
            self.input = InputWindowWidgets()
            if self.input.exec_() == QtWidgets.QDialog.Accepted:

                value = self.input.key.currentText()
                type = {"searchComboBox":{
                        "Name":"MySearchComboBox",
                         "Type":"searchComboBox",
                         "Parameters":{
                            "layer":"zone_de_nro",
                            "field":"za_nro",
                            "id":"code_id"
                         }
                      },"checkableComboBox":{
                        "Name":"MyCheckableComboBox",
                         "Type":"checkableComboBox",
                         "Parameters":{
                            "layer":"zone_de_nro",
                            "field":"za_nro"
                         }
                      },"expressionWidget":{
                        "Name":"MyExpressionWidget",
                         "Type":"expressionWidget",
                         "Parameters":{
                            "layer":"zone_de_nro"
                         }
                      }}
                if item.hasChildren():
                    type_ = item.data(TypeRole)
                    data = []
                    type_.serialize(model=self, item=item, data=data, parent=self.invisibleRootItem())
                    data = data[0]
                    for i in range(0,item.rowCount()):
                        item.removeRow(0)

                else:
                    data = []

                data.append(type[value])
                print(data)
                type_ = match_type(data)
                print(type_)
                item.setData(type_, TypeRole)
                type_.next(model=self, data=data, parent=item)






        else:

            self.input = InputWindow()

            if self.input.exec_() == QtWidgets.QDialog.Accepted:

                key = self.input.key.text()
                try:
                    value = json.loads(self.input.value.toPlainText())
                except:
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



                print(key_item, value_item)

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

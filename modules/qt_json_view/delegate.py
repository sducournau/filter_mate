from qgis.PyQt import QtWidgets, QtCore

from .datatypes import DataType, TypeRole


class JsonDelegate(QtWidgets.QStyledItemDelegate):
    """Display the data based on the definitions on the DataTypes."""

    def sizeHint(self, option, index):
        # Larger size hint for better QgsColorButton visibility
        return QtCore.QSize(option.rect.width(), 28)

    def paint(self, painter, option, index):
        """Use method from the data type or fall back to the default."""
        if index.column() == 0:
            return super(JsonDelegate, self).paint(painter, option, index)
        type_ = index.data(TypeRole)
        if isinstance(type_, DataType):
            try:
                # For ColorType, only call type_.paint() to avoid double rendering
                return type_.paint(painter, option, index)
            except NotImplementedError:
                # Fallback to default painting if paint() not implemented
                pass
        return super(JsonDelegate, self).paint(painter, option, index)

    def createEditor(self, parent, option, index):
        """Use method from the data type or fall back to the default."""
        if index.column() == 0:
            return super(JsonDelegate, self).createEditor(
                parent, option, index)
        try:
            return index.data(TypeRole).createEditor(parent, option, index)
        except NotImplementedError:
            return super(JsonDelegate, self).createEditor(
                parent, option, index)

    def setEditorData(self, editor, index):
        """Use method from the data type or fall back to the default."""
        if index.column() == 0:
            return super(JsonDelegate, self).setEditorData(editor, index)
        try:
            type_ = index.data(TypeRole)
            if hasattr(type_, 'setEditorData'):
                return type_.setEditorData(editor, index)
        except (NotImplementedError, AttributeError):
            pass
        return super(JsonDelegate, self).setEditorData(editor, index)
    
    def setModelData(self, editor, model, index):
        """Use method from the data type or fall back to the default."""
        if index.column() == 0:
            return super(JsonDelegate, self).setModelData(editor, model, index)
        try:
            type_ = index.data(TypeRole)
            if hasattr(type_, 'setModelData'):
                result = type_.setModelData(editor, model, index)
                # Emit dataChanged to notify listeners
                model.dataChanged.emit(index, index)
                return result
        except (NotImplementedError, AttributeError):
            pass
        result = super(JsonDelegate, self).setModelData(editor, model, index)
        # Emit dataChanged for standard edits too
        model.dataChanged.emit(index, index)
        return result

from functools import partial
import re
import webbrowser
import os
from shutil import copyfile

from qgis.PyQt import QtCore, QtGui, QtWidgets
from qgis.gui import QgsColorButton
from . import themes


TypeRole = QtCore.Qt.UserRole + 1
PLUGIN_DIR = ''

class DataType(object):
    """Base class for data types."""
    COLOR = QtCore.Qt.black
    THEME_COLOR_KEY = 'string'  # Default theme color key

    def get_color(self):
        """Get the color for this data type from the current theme."""
        return themes.get_current_theme().get_color(self.THEME_COLOR_KEY)

    def matches(self, data):
        """Logic to define whether the given data matches this type."""
        raise NotImplementedError

    def next(self, model, data, parent):
        """Implement if this data type has to add child items to itself."""
        pass

    def actions(self, index):
        """Re-implement to return custom QActions."""

        return ["Rename","Add child","Insert sibling up","Insert sibling down", "Remove"]

    def paint(self, painter, option, index):
        """Optionally re-implement for use by the delegate."""
        raise NotImplementedError

    def createEditor(self, parent, option, index):
        """Optionally re-implement for use by the delegate."""
        raise NotImplementedError

    def setModelData(self, editor, model, index):
        """Optionally re-implement for use by the delegate."""
        raise NotImplementedError

    def serialize(self, model, item, data, parent):
        """Serialize this data type."""
        value_item = parent.child(item.row(), 1)
        value = value_item.data(QtCore.Qt.DisplayRole)
        if isinstance(data, dict):
            key_item = parent.child(item.row(), 0)
            key = key_item.data(QtCore.Qt.DisplayRole)
            data[key] = value
        elif isinstance(data, list):
            data.append(value)

    def key_item(self, key, model, datatype=None, editable=True):
        """Create an item for the key column for this data type."""
        key_item = QtGui.QStandardItem(key)
        key_item.setData(datatype, TypeRole)
        key_item.setData(datatype.__class__.__name__, QtCore.Qt.ToolTipRole)
        key_item.setData(
            QtGui.QBrush(self.get_color()), QtCore.Qt.ForegroundRole)
        key_item.setFlags(
            QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        if editable and model.editable_keys:
            key_item.setFlags(key_item.flags() | QtCore.Qt.ItemIsEditable)
        return key_item

    def value_item(self, value, model, key=None):
        """Create an item for the value column for this data type."""
        display_value = value
        item = QtGui.QStandardItem(display_value)
        item.setData(display_value, QtCore.Qt.DisplayRole)
        item.setData(value, QtCore.Qt.UserRole)
        item.setData(self, TypeRole)
        item.setData(QtGui.QBrush(self.get_color()), QtCore.Qt.ForegroundRole)
        item.setFlags(
            QtCore.Qt.ItemIsSelectable |
            QtCore.Qt.ItemIsEnabled)
        if model.editable_values:
            item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
        return item


# -----------------------------------------------------------------------------
# Default Types
# -----------------------------------------------------------------------------


class NoneType(DataType):
    """None"""
    THEME_COLOR_KEY = 'none'

    def matches(self, data):
        return data is None

    def value_item(self, value, model, key=None):
        item = super(NoneType, self).value_item(value, model, key)
        item.setData('None', QtCore.Qt.DisplayRole)
        return item

    def serialize(self, model, item, data, parent):
        value_item = parent.child(item.row(), 1)
        value = value_item.data(QtCore.Qt.DisplayRole)
        value = value if value != 'None' else None
        if isinstance(data, dict):
            key_item = parent.child(item.row(), 0)
            key = key_item.data(QtCore.Qt.DisplayRole)
            data[key] = value
        elif isinstance(data, list):
            data.append(value)


class StrType(DataType):
    """Strings and unicodes"""

    def matches(self, data):
        return isinstance(data, str) or isinstance(data, unicode)


class ColorType(DataType):
    """Hex color strings displayed with QgsColorButton."""
    THEME_COLOR_KEY = 'string'
    
    # Pattern to match hex colors: #RGB, #RRGGBB, #RRGGBBAA
    HEX_COLOR_PATTERN = re.compile(r'^#[0-9A-Fa-f]{3}([0-9A-Fa-f]{3})?([0-9A-Fa-f]{2})?$')

    def matches(self, data):
        """Check if data is a hex color string."""
        if not isinstance(data, str):
            return False
        return bool(self.HEX_COLOR_PATTERN.match(data))

    def createEditor(self, parent, option, index):
        """Create a QgsColorButton editor for color selection."""
        color_button = QgsColorButton(parent)
        color_button.setAllowOpacity(True)
        color_button.setShowNoColor(False)
        color_button.setMinimumSize(30, 22)
        color_button.setMaximumHeight(30)
        
        # Set initial color from current value
        current_color = index.data(QtCore.Qt.DisplayRole)
        if current_color:
            qcolor = QtGui.QColor(current_color)
            if qcolor.isValid():
                color_button.setColor(qcolor)
        
        # Connect signal to update immediately on color change
        color_button.colorChanged.connect(
            lambda: self.setModelData(color_button, index.model(), index)
        )
        
        return color_button
    
    def setEditorData(self, editor, index):
        """Set the editor data from the model."""
        if isinstance(editor, QgsColorButton):
            color_str = index.data(QtCore.Qt.DisplayRole)
            if color_str:
                qcolor = QtGui.QColor(color_str)
                if qcolor.isValid():
                    editor.setColor(qcolor)

    def setModelData(self, editor, model, index):
        """Update model with selected color from QgsColorButton."""
        if isinstance(editor, QgsColorButton):
            color = editor.color()
            # Format color as hex string with alpha if present
            if color.alpha() < 255:
                hex_color = color.name(QtGui.QColor.HexArgb)
            else:
                hex_color = color.name(QtGui.QColor.HexRgb)
            
            model.setData(index, hex_color, QtCore.Qt.EditRole)

    def paint(self, painter, option, index):
        """Paint a color preview rectangle next to the color value."""
        painter.save()
        
        # Get color value
        color_str = index.data(QtCore.Qt.DisplayRole)
        qcolor = QtGui.QColor(color_str)
        
        if qcolor.isValid():
            # Draw color rectangle
            rect = option.rect
            color_rect = QtCore.QRect(
                rect.left() + 2,
                rect.top() + 2,
                20,
                rect.height() - 4
            )
            painter.fillRect(color_rect, qcolor)
            painter.setPen(QtGui.QPen(QtCore.Qt.black, 1))
            painter.drawRect(color_rect)
            
            # Draw text after color rectangle
            text_rect = QtCore.QRect(
                color_rect.right() + 5,
                rect.top(),
                rect.width() - color_rect.width() - 7,
                rect.height()
            )
            painter.setPen(self.get_color())
            painter.drawText(
                text_rect,
                QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft,
                color_str
            )
        else:
            # Fallback to default painting if color is invalid
            painter.setPen(self.get_color())
            painter.drawText(
                option.rect,
                QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft,
                " " + color_str
            )
        
        painter.restore()


class IntType(DataType):
    """Integers"""
    THEME_COLOR_KEY = 'integer'

    def matches(self, data):
        return isinstance(data, int) and not isinstance(data, bool)


class FloatType(DataType):
    """Floats"""
    THEME_COLOR_KEY = 'float'

    def matches(self, data):
        return isinstance(data, float)


class BoolType(DataType):
    """Bools are displayed as checkable items with a check box."""
    THEME_COLOR_KEY = 'boolean'

    def matches(self, data):
        return isinstance(data, bool)

    def value_item(self, value, model, key=None):
        item = super(BoolType, self).value_item(value, model, key)
        item.setCheckState(QtCore.Qt.Checked if value else QtCore.Qt.Unchecked)
        item.setData('', QtCore.Qt.DisplayRole)
        if model.editable_values:
            item.setFlags(
                item.flags() | QtCore.Qt.ItemIsEditable |
                QtCore.Qt.ItemIsUserCheckable)
        return item

    def serialize(self, model, item, data, parent):
        value_item = parent.child(item.row(), 1)
        value = value_item.checkState() == QtCore.Qt.Checked
        if isinstance(data, dict):
            key_item = parent.child(item.row(), 0)
            key = key_item.data(QtCore.Qt.DisplayRole)
            data[key] = value
        elif isinstance(data, list):
            data.append(value)


class ListType(DataType):
    """Lists"""
    THEME_COLOR_KEY = 'list'

    def matches(self, data):
        return isinstance(data, list)

    def next(self, model, data, parent):
        for i, value in enumerate(data):
            type_ = match_type(value)
            key_item = self.key_item(
                str(i), datatype=type_, editable=False, model=model)
            value_item = type_.value_item(value, model=model, key=str(i))
            parent.appendRow([key_item, value_item])
            type_.next(model, data=value, parent=key_item)

    def value_item(self, value, model, key):
        item = QtGui.QStandardItem()
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        return item

    def serialize(self, model, item, data, parent):
        key_item = parent.child(item.row(), 0)
        if key_item:
            if isinstance(data, dict):
                key = key_item.data(QtCore.Qt.DisplayRole)
                data[key] = []
                data = data[key]
            elif isinstance(data, list):
                new_data = []
                data.append(new_data)
                data = new_data
        for row in range(item.rowCount()):
            child_item = item.child(row, 0)
            type_ = child_item.data(TypeRole)
            type_.serialize(
                model=self, item=child_item, data=data, parent=item)


class DictType(DataType):
    """Dictionaries"""
    THEME_COLOR_KEY = 'dict'

    def matches(self, data):
        return isinstance(data, dict)

    def next(self, model, data, parent):
        for key, value in data.items():
            type_ = match_type(value)
            key_item = self.key_item(key, datatype=type_, model=model)
            value_item = type_.value_item(value, model, key)
            parent.appendRow([key_item, value_item])
            type_.next(model, data=value, parent=key_item)

    def value_item(self, value, model, key):
        item = QtGui.QStandardItem()
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        return item

    def serialize(self, model, item, data, parent):
        key_item = parent.child(item.row(), 0)
        if key_item:
            if isinstance(data, dict):
                key = key_item.data(QtCore.Qt.DisplayRole)
                data[key] = {}
                data = data[key]
            elif isinstance(data, list):
                new_data = {}
                data.append(new_data)
                data = new_data
        for row in range(item.rowCount()):
            child_item = item.child(row, 0)
            type_ = child_item.data(TypeRole)
            type_.serialize(model=self, item=child_item, data=data, parent=item)


# -----------------------------------------------------------------------------
# Derived Types
# -----------------------------------------------------------------------------


class RangeType(DataType):
    """A range, shown as three spinboxes next to each other.

    A range is defined as a dict with start, end and step keys.
    It supports both floats and ints.
    """
    THEME_COLOR_KEY = 'range'
    KEYS = ['start', 'end', 'step']

    def matches(self, data):
        if isinstance(data, dict) and len(data) == 3:
            if all([True if k in self.KEYS else False for k in data.keys()]):
                return True
        return False

    def paint(self, painter, option, index):
        data = index.data(QtCore.Qt.UserRole)

        painter.save()

        painter.setPen(QtGui.QPen(index.data(QtCore.Qt.ForegroundRole).color()))
        metrics = painter.fontMetrics()
        spinbox_option = QtWidgets.QStyleOptionSpinBox()
        start_rect = QtCore.QRect(option.rect)
        start_rect.setWidth(start_rect.width() / 3.0)
        spinbox_option.rect = start_rect
        spinbox_option.frame = True
        spinbox_option.state = option.state
        spinbox_option.buttonSymbols = QtWidgets.QAbstractSpinBox.NoButtons
        for i, key in enumerate(self.KEYS):
            if i > 0:
                spinbox_option.rect.adjust(
                    spinbox_option.rect.width(), 0,
                    spinbox_option.rect.width(), 0)
            QtWidgets.QApplication.style().drawComplexControl(
                QtWidgets.QStyle.CC_SpinBox, spinbox_option, painter)
            value = str(data[key])
            value_rect = QtCore.QRectF(
                spinbox_option.rect.adjusted(6, 1, -2, -2))
            value = metrics.elidedText(
                value, QtCore.Qt.ElideRight, value_rect.width() - 20)
            painter.drawText(value_rect, value)

        painter.restore()

    def createEditor(self, parent, option, index):
        data = index.data(QtCore.Qt.UserRole)
        wid = QtWidgets.QWidget(parent)
        wid.setLayout(QtWidgets.QHBoxLayout(parent))
        wid.layout().setContentsMargins(0, 0, 0, 0)
        wid.layout().setSpacing(0)

        start = data['start']
        end = data['end']
        step = data['step']

        if isinstance(start, float):
            start_spinbox = QtWidgets.QDoubleSpinBox(wid)
        else:
            start_spinbox = QtWidgets.QSpinBox(wid)

        if isinstance(end, float):
            end_spinbox = QtWidgets.QDoubleSpinBox(wid)
        else:
            end_spinbox = QtWidgets.QSpinBox(wid)

        if isinstance(step, float):
            step_spinbox = QtWidgets.QDoubleSpinBox(wid)
        else:
            step_spinbox = QtWidgets.QSpinBox(wid)

        start_spinbox.setRange(-16777215, 16777215)
        end_spinbox.setRange(-16777215, 16777215)
        step_spinbox.setRange(-16777215, 16777215)
        start_spinbox.setValue(start)
        end_spinbox.setValue(end)
        step_spinbox.setValue(step)
        wid.layout().addWidget(start_spinbox)
        wid.layout().addWidget(end_spinbox)
        wid.layout().addWidget(step_spinbox)
        return wid

    def setModelData(self, editor, model, index):
        #if isinstance(model, QtWidgets.QAbstractProxyModel):
        #    index = model.mapToSource(index)
        #    model = model.sourceModel()
        data = index.data(QtCore.Qt.UserRole)
        data['start'] = editor.layout().itemAt(0).widget().value()
        data['end'] = editor.layout().itemAt(1).widget().value()
        data['step'] = editor.layout().itemAt(2).widget().value()
        model.itemFromIndex(index).setData(data, QtCore.Qt.UserRole)

    def value_item(self, value, model, key=None):
        """Item representing a value."""
        value_item = super(RangeType, self).value_item(None, model, key)
        value_item.setData(value, QtCore.Qt.UserRole)
        return value_item

    def serialize(self, model, item, data, parent):
        value_item = parent.child(item.row(), 1)
        value = value_item.data(QtCore.Qt.UserRole)
        if isinstance(data, dict):
            key_item = parent.child(item.row(), 0)
            key = key_item.data(QtCore.Qt.DisplayRole)
            data[key] = value
        elif isinstance(data, list):
            data.append(value)


class UrlType(DataType):
    """Provide a link to urls."""
    THEME_COLOR_KEY = 'url'
    REGEX = re.compile(r'(?:https?):\/\/|(?:file):\/\\/')

    def matches(self, data):
        if isinstance(data, str) or isinstance(data, unicode):
            if self.REGEX.match(data) is not None:
                return True
        return False

    def actions(self, index):
        explore = QtWidgets.QAction('Explore ...', None)
        explore.triggered.connect(
            partial(webbrowser.open, index.data(QtCore.Qt.DisplayRole)))
        return [explore]


class FilepathType(DataType):
    """Files and paths can be opened."""
    THEME_COLOR_KEY = 'filepath'
    POSITIVE_REGEX = re.compile(r'(\/.*)|([A-Za-z]:\\.*)')
    NEGATIVE_REGEX = re.compile(r'(\.png)|(\.jpg)|(\.jpeg)|(\.gif)$')

    def matches(self, data):
        if isinstance(data, str) or isinstance(data, unicode):
            if self.POSITIVE_REGEX.search(data) is not None:
                if self.NEGATIVE_REGEX.search(data) is None:
                    return True
        return False

    def value_item(self, value, model, key):
        """Item representing a value."""
        value_item = super(FilepathType, self).value_item(value, model, key)
        if os.path.exists(value):
            if os.path.isdir(value):
                value_item.setData(value, QtCore.Qt.DisplayRole)
            elif os.path.isfile(value):
                value_item.setData(os.path.basename(value), QtCore.Qt.DisplayRole)
                value_item.setData(os.path.normcase(value), QtCore.Qt.UserRole)
        return value_item


    def actions(self, index):
        view = QtWidgets.QAction('View', None)
        self.change = QtWidgets.QAction('Change', None)
        path = index.data(QtCore.Qt.DisplayRole)
        view.triggered.connect(partial(webbrowser.open, path))
        self.change.triggered.connect(partial(self.change_path, path, index))
        return [view, self.change]
    
    def change_path(self, input_path, index):
        new_path = None
        filename = None
        if os.path.isdir(input_path):
            new_path = os.path.normcase(str(QtWidgets.QFileDialog.getExistingDirectory(None, 'Select a folder', input_path)))
        else:
            if os.path.exists(input_path):
                extension = os.path.basename(input_path).split('.')[-1]
                new_path = os.path.normcase(str(QtWidgets.QFileDialog.getOpenFileName(None, 'Select a file', input_path, '*.{extension}'.format(extension=extension))[0]))   
                filename = os.path.basename(new_path)
            else:
                extension = os.path.basename(input_path).split('.')[-1]
                new_path = os.path.normcase(str(QtWidgets.QFileDialog.getSaveFileName(None, 'Save to a file', input_path, '*.{extension}'.format(extension=extension))[0]))   
                filename = os.path.basename(new_path)
        if new_path is not None:
            if filename is not None:
                self.change.setData([filename, new_path])
            else:
                self.change.setData([new_path])


class FilepathTypeImages(DataType):
    """Files and paths can be opened."""
    THEME_COLOR_KEY = 'filepath'
    REGEX = re.compile(r'(\.png)|(\.jpg)|(\.jpeg)|(\.gif)$')

    def matches(self, data):
        if isinstance(data, str) or isinstance(data, unicode):
            if self.REGEX.search(data) is not None:
                return True
        return False

    def value_item(self, value, model, key):
        """Item representing a value."""
        value_item = super(FilepathTypeImages, self).value_item(value, model, key)
        value_item.setData(value, QtCore.Qt.DisplayRole)
        value_item.setData(os.path.normcase(os.path.join(PLUGIN_DIR, "icons", value)), QtCore.Qt.UserRole)
        return value_item

    def actions(self, index):
        view = QtWidgets.QAction('View', None)
        self.change = QtWidgets.QAction('Change', None)
        path_view = index.data(QtCore.Qt.UserRole)
        path_change = os.path.normcase(os.path.join(PLUGIN_DIR, "icons"))
        view.triggered.connect(partial(webbrowser.open, path_view))
        self.change.triggered.connect(partial(self.change_icon, path_change, index))
        return [view, self.change]
        

    def change_icon(self, folder_path, index):
        filepath = os.path.normcase(str(QtWidgets.QFileDialog.getOpenFileName(None, 'Select an icon', folder_path, 'Images (*.png *.jpg *.jpeg *.gif)')[0]))
        if filepath:
            new_filepath = filepath
            filename = os.path.basename(filepath)
            if filepath.find(folder_path) < 0:
                new_filepath = os.path.join(folder_path, filename)
                copyfile(filepath, new_filepath)
            self.change.setData([filename, new_filepath])




class ChoicesType(DataType):
    """A combobox that allows for a number of choices.

    The data has to be a dict with at least 'value' and 'choices' keys.
    Supports extended format with optional 'description' and other metadata.
    
    Basic format:
    {
        "value": "A",
        "choices": ["A", "B", "C"]
    }
    
    Extended format (v2.0 config):
    {
        "value": "auto",
        "choices": ["auto", "compact", "normal"],
        "description": "UI display profile setting",
        "additional_metadata": "any value"
    }
    """
    THEME_COLOR_KEY = 'choices'
    REQUIRED_KEYS = ['value', 'choices']

    def matches(self, data):
        """Match dict with 'value' and 'choices' keys (and optionally more)."""
        if isinstance(data, dict):
            # Must have both 'value' and 'choices' keys
            if all(k in data for k in self.REQUIRED_KEYS):
                # 'choices' must be a list
                if isinstance(data.get('choices'), list):
                    return True
        return False

    def createEditor(self, parent, option, index):
        data = index.data(QtCore.Qt.UserRole)
        cbx = QtWidgets.QComboBox(parent)
        cbx.addItems([str(d) for d in data['choices']])
        cbx.setCurrentIndex(cbx.findText(str(data['value'])))
        # Add description as tooltip if available
        if 'description' in data:
            cbx.setToolTip(str(data['description']))
        return cbx

    def setModelData(self, editor, model, index):
        data = index.data(QtCore.Qt.UserRole)
        data['value'] = data['choices'][editor.currentIndex()]
        model.itemFromIndex(index).setData(data['value'], QtCore.Qt.DisplayRole)
        model.itemFromIndex(index).setData(data, QtCore.Qt.UserRole)

    def value_item(self, value, model, key=None):
        """Item representing a value with optional tooltip from description."""
        value_item = super(ChoicesType, self).value_item(value['value'], model, key)
        value_item.setData(value, QtCore.Qt.UserRole)
        # Set tooltip from description if available
        if 'description' in value:
            value_item.setData(str(value['description']), QtCore.Qt.ToolTipRole)
        return value_item

    def serialize(self, model, item, data, parent):
        value_item = parent.child(item.row(), 1)
        value = value_item.data(QtCore.Qt.UserRole)
        if isinstance(data, dict):
            key_item = parent.child(item.row(), 0)
            key = key_item.data(QtCore.Qt.DisplayRole)
            data[key] = value
        elif isinstance(data, list):
            data.append(value)


class ConfigValueType(DataType):
    """A simple config value with description metadata.

    The data has to be a dict with 'value' key and optionally 'description'.
    This type handles config values that have metadata but no choices.
    
    Format:
    {
        "value": true,
        "description": "Auto-activate plugin when project loaded"
    }
    
    Or with additional metadata:
    {
        "value": "path/to/file",
        "description": "Database file path",
        "applies_to": "Plugin initialization"
    }
    
    NOTE: This type must NOT match if 'choices' key is present - 
    those should be handled by ChoicesType.
    """
    THEME_COLOR_KEY = 'string'

    def matches(self, data):
        """Match dict with 'value' key but WITHOUT 'choices' key."""
        if isinstance(data, dict):
            # Must have 'value' key
            if 'value' in data:
                # Must NOT have 'choices' key (that's for ChoicesType)
                if 'choices' not in data:
                    # Should have at least description or other metadata
                    # (otherwise it's just a plain value in a dict)
                    return len(data) >= 2
        return False

    def createEditor(self, parent, option, index):
        """Create appropriate editor based on value type."""
        data = index.data(QtCore.Qt.UserRole)
        value = data.get('value')
        
        if isinstance(value, bool):
            # Use checkbox for boolean
            cbx = QtWidgets.QCheckBox(parent)
            cbx.setChecked(value)
            if 'description' in data:
                cbx.setToolTip(str(data['description']))
            return cbx
        elif isinstance(value, int) and not isinstance(value, bool):
            # Use spinbox for integers
            spinbox = QtWidgets.QSpinBox(parent)
            spinbox.setMinimum(-2147483648)
            spinbox.setMaximum(2147483647)
            spinbox.setValue(value)
            if 'description' in data:
                spinbox.setToolTip(str(data['description']))
            return spinbox
        elif isinstance(value, float):
            # Use double spinbox for floats
            spinbox = QtWidgets.QDoubleSpinBox(parent)
            spinbox.setDecimals(6)
            spinbox.setMinimum(-1e10)
            spinbox.setMaximum(1e10)
            spinbox.setValue(value)
            if 'description' in data:
                spinbox.setToolTip(str(data['description']))
            return spinbox
        else:
            # Use line edit for strings and other types
            line_edit = QtWidgets.QLineEdit(parent)
            line_edit.setText(str(value) if value is not None else '')
            if 'description' in data:
                line_edit.setToolTip(str(data['description']))
            return line_edit

    def setModelData(self, editor, model, index):
        """Set model data based on editor type."""
        data = index.data(QtCore.Qt.UserRole)
        original_value = data.get('value')
        
        if isinstance(editor, QtWidgets.QCheckBox):
            new_value = editor.isChecked()
        elif isinstance(editor, QtWidgets.QSpinBox):
            new_value = editor.value()
        elif isinstance(editor, QtWidgets.QDoubleSpinBox):
            new_value = editor.value()
        else:
            # Line edit - try to preserve type
            text = editor.text()
            if isinstance(original_value, bool):
                new_value = text.lower() in ('true', '1', 'yes', 'on')
            elif isinstance(original_value, int) and not isinstance(original_value, bool):
                try:
                    new_value = int(text)
                except ValueError:
                    new_value = text
            elif isinstance(original_value, float):
                try:
                    new_value = float(text)
                except ValueError:
                    new_value = text
            else:
                new_value = text
        
        data['value'] = new_value
        # Display the value, not the full dict
        display_text = str(new_value)
        if isinstance(new_value, bool):
            display_text = 'true' if new_value else 'false'
        model.itemFromIndex(index).setData(display_text, QtCore.Qt.DisplayRole)
        model.itemFromIndex(index).setData(data, QtCore.Qt.UserRole)

    def value_item(self, value, model, key=None):
        """Item representing a value with optional tooltip from description."""
        actual_value = value.get('value', value)
        # Convert bool to string for display
        if isinstance(actual_value, bool):
            display_text = 'true' if actual_value else 'false'
        else:
            display_text = str(actual_value) if actual_value is not None else ''
        
        value_item = QtGui.QStandardItem(display_text)
        value_item.setData(display_text, QtCore.Qt.DisplayRole)
        value_item.setData(value, QtCore.Qt.UserRole)
        value_item.setData(self, TypeRole)
        value_item.setData(QtGui.QBrush(self.get_color()), QtCore.Qt.ForegroundRole)
        value_item.setFlags(
            QtCore.Qt.ItemIsSelectable |
            QtCore.Qt.ItemIsEnabled)
        if model.editable_values:
            value_item.setFlags(value_item.flags() | QtCore.Qt.ItemIsEditable)
        
        # Set tooltip from description if available
        if isinstance(value, dict) and 'description' in value:
            value_item.setData(str(value['description']), QtCore.Qt.ToolTipRole)
        
        return value_item

    def serialize(self, model, item, data, parent):
        """Serialize the full dict structure back."""
        value_item = parent.child(item.row(), 1)
        value = value_item.data(QtCore.Qt.UserRole)
        if isinstance(data, dict):
            key_item = parent.child(item.row(), 0)
            key = key_item.data(QtCore.Qt.DisplayRole)
            data[key] = value
        elif isinstance(data, list):
            data.append(value)


# Add any custom DataType to this list
# NOTE: Order matters! More specific types must come before generic ones.
# - ChoicesType must match before ConfigValueType (has 'choices' key)
# - ConfigValueType must match before DictType (has 'value' key with metadata)
# - DictType is the fallback for all other dicts
#
DATA_TYPES = [
    NoneType(),
    UrlType(),
    FilepathTypeImages(),
    FilepathType(),
    ColorType(),  # Must be before StrType to match color strings first
    StrType(),
    IntType(),
    FloatType(),
    BoolType(),
    ListType(),
    RangeType(),
    ChoicesType(),      # Match {value, choices, ...} - dropdown editor
    ConfigValueType(),  # Match {value, description, ...} without choices - typed editor
    DictType()          # Fallback for all other dicts
]


def match_type(data):
    """Try to match the given data object to a DataType"""
    for type_ in DATA_TYPES:
        if type_.matches(data):
            return type_

def set_plugin_dir(plugin_dir):
    """Set the global PLUGIN_DIR variable used by FilepathTypeImages."""
    global PLUGIN_DIR
    PLUGIN_DIR = plugin_dir
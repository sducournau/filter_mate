# -*- coding: utf-8 -*-
"""
Custom Widgets for FilterMate

EPIC-1 Migration: Restored from before_migration/modules/widgets.py
Date: January 2026 - Updated with full functionality restoration

Custom QGIS widgets not available in qgis.gui:
- QgsCheckableComboBoxLayer: Multi-select layer combobox with context menu and geometry filtering
- QgsCheckableComboBoxFeaturesListPickerWidget: Multi-select feature picker with async loading
- ListWidgetWrapper: Feature list storage with sorting capabilities
- ItemDelegate: Custom delegate for checkable items with icons

Usage:
    from ui.widgets.custom_widgets import QgsCheckableComboBoxLayer, QgsCheckableComboBoxFeaturesListPickerWidget
    
    combo = QgsCheckableComboBoxLayer(parent)
    combo.addItem(icon, "Layer Name", {"layer_geometry_type": "GeometryType.Point"})
    selected_layers = combo.checkedItems()
    
    feature_picker = QgsCheckableComboBoxFeaturesListPickerWidget(config, parent)
    feature_picker.setLayer(layer, layer_props)
    selected_features = feature_picker.checkedItems()
"""

import logging
from typing import List, Optional, Any, Dict
from functools import partial

from qgis.PyQt import QtGui, QtWidgets, QtCore
from qgis.PyQt.QtCore import (
    QEvent,
    QRect,
    QSize,
    Qt,
    QTimer,
    pyqtSignal
)
from qgis.PyQt.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QIcon,
    QPalette,
    QPixmap,
    QStandardItem
)
from qgis.PyQt.QtWidgets import (
    QAction,
    QApplication,
    QComboBox,
    QDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QSizePolicy,
    QStyle,
    QStyleOptionComboBox,
    QStyleOptionViewItem,
    QStylePainter,
    QStyledItemDelegate,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QPushButton
)
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsMapLayer,
    QgsFeature,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextScope,
    QgsExpressionContextUtils,
    QgsFeatureRequest,
    QgsTask,
    QgsApplication,
    QgsMessageLog,
    Qgis
)
from qgis.gui import (
    QgsCheckableComboBox
)
from qgis.utils import iface

# Import safe iteration utilities for OGR/GeoPackage error handling
from ...infrastructure.utils import safe_iterate_features, get_feature_attribute

logger = logging.getLogger('FilterMate.UI.Widgets.CustomWidgets')


class ItemDelegate(QStyledItemDelegate):
    """
    Custom item delegate for checkable combobox items with icons.
    
    Restored from before_migration/modules/widgets.py for full functionality.
    Provides custom painting for checkbox + icon + text layout.
    """

    def __init__(self, parent=None, *args):
        QStyledItemDelegate.__init__(self, parent, *args)
        self.parent = parent

    def sizeHint(self, option, index):
        # BUGFIX: Return fixed size hint for consistent row height
        # Match QGIS standard layer item height
        return QSize(200, 20)  # Width ignored by view, height = 20px

    def getCheckboxRect(self, option):
        return QRect(4, 4, 18, 18).translated(option.rect.topLeft())
    
    def getItemRect(self, item):
        size_hint = item.sizeHint()
        return QRect(0, 0, size_hint.width(), size_hint.height())

    def paint(self, painter, option, index):
        painter.save()

        # BUGFIX: Use fixed icon size instead of option.decorationSize which can be (0,0)
        # Standard QGIS icon size for layer items
        ICON_SIZE = 16
        CHECKBOX_WIDTH = 22  # Space for checkbox (18px + 4px margin)
        
        x, y, dx, dy = option.rect.x(), option.rect.y(), option.rect.width(), option.rect.height()

        # Decoration - Draw icon FIRST, positioned after checkbox
        # v4.0.2: Simplified - icon is now properly stored via setData(icon, Qt.DecorationRole)
        pic = index.data(Qt.DecorationRole)
        
        icon_drawn = False
        if pic:
            if isinstance(pic, QIcon):
                if not pic.isNull():
                    # Draw icon with fixed size, positioned after checkbox
                    icon_x = x + CHECKBOX_WIDTH
                    icon_y = y + (dy - ICON_SIZE) // 2  # Center vertically
                    pixmap = pic.pixmap(ICON_SIZE, ICON_SIZE)
                    painter.drawPixmap(icon_x, icon_y, pixmap)
                    icon_drawn = True
            elif isinstance(pic, QPixmap):
                icon_x = x + CHECKBOX_WIDTH
                icon_y = y + (dy - ICON_SIZE) // 2
                painter.drawPixmap(icon_x, icon_y, pic.scaled(ICON_SIZE, ICON_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                icon_drawn = True
        
        # Draw text AFTER icon
        text = index.data(Qt.DisplayRole)
        if text:
            # Position text after checkbox + icon + margins
            text_x = x + CHECKBOX_WIDTH + (ICON_SIZE + 4 if icon_drawn else 0)
            text_y = y + dy // 2 + 4  # Center vertically with offset
            painter.drawText(text_x, text_y, text)

        # Indicate Selected
        painter.setPen(QtGui.QPen(Qt.NoPen))
        if option.state & QStyle.State_Selected:
            painter.setBrush(QBrush(QColor(0, 70, 240, 128)))
        else:
            painter.setBrush(QBrush(Qt.NoBrush))
        painter.drawRect(QRect(x, y, dx, dy))

        # Checkstate
        value = index.data(Qt.CheckStateRole)
        if value is not None:
            opt = QStyleOptionViewItem()
            opt.rect = self.getCheckboxRect(option)
            opt.state = opt.state & ~QStyle.State_HasFocus
            if value == Qt.Unchecked:
                opt.state |= QStyle.State_Off
            elif value == Qt.PartiallyChecked:
                opt.state |= QStyle.State_NoChange
            elif value == Qt.Checked:
                opt.state = QStyle.State_On
            style = QApplication.style()
            style.drawPrimitive(
                QStyle.PE_IndicatorViewItemCheck, opt, painter, None
            )

        painter.restore()


class QgsCheckableComboBoxLayer(QComboBox):
    """
    A checkable combobox for selecting multiple layers with context menu.
    
    Restored from before_migration/modules/widgets.py with full functionality:
    - Custom ItemDelegate for checkbox + icon + text
    - Context menu with Select All, Deselect All, filter by geometry type
    - Custom paintEvent showing selected items as CSV
    - Event filter for left/right click handling
    
    Signals:
        checkedItemsChanged: Emitted when the selection changes (list of layer names)
    """

    checkedItemsChanged = pyqtSignal(list)

    def __init__(self, parent=None):
        super(QgsCheckableComboBoxLayer, self).__init__(parent)

        self.parent = parent
        
        # Dimensions managed by QSS (20px standard height from resources/styles/default.qss)
        # Width and size policy still configured in Python for layout flexibility
        self.setMinimumWidth(30)
        self.setMaximumWidth(16777215)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)

        font = QFont("Segoe UI Semibold", 8)
        font.setBold(True)
        self.setFont(font)

        self.setModel(QtGui.QStandardItemModel(self))
        self.setItemDelegate(ItemDelegate(self))
        self.createMenuContext()

        self.view().setModel(self.model())
        
        self.installEventFilter(self)
        self.view().viewport().installEventFilter(self)

    def createMenuContext(self):
        """Create the context menu with selection actions."""
        self.context_menu = QMenu(self)
        
        self.action_check_all = QAction('Select All', self)
        self.action_check_all.triggered.connect(self.select_all)
        self.action_uncheck_all = QAction('De-select All', self)
        self.action_uncheck_all.triggered.connect(self.deselect_all)
        self.action_check_all_geometry_line = QAction('Select all layers by geometry type (Lines)', self)
        self.action_check_all_geometry_line.triggered.connect(partial(self.select_by_geometry, 'GeometryType.Line', Qt.Checked))
        self.action_uncheck_all_geometry_line = QAction('De-Select all layers by geometry type (Lines)', self)
        self.action_uncheck_all_geometry_line.triggered.connect(partial(self.select_by_geometry, 'GeometryType.Line', Qt.Unchecked))
        self.action_check_all_geometry_point = QAction('Select all layers by geometry type (Points)', self)
        self.action_check_all_geometry_point.triggered.connect(partial(self.select_by_geometry, 'GeometryType.Point', Qt.Checked))
        self.action_uncheck_all_geometry_point = QAction('De-Select all layers by geometry type (Points)', self)
        self.action_uncheck_all_geometry_point.triggered.connect(partial(self.select_by_geometry, 'GeometryType.Point', Qt.Unchecked))
        self.action_check_all_geometry_polygon = QAction('Select all layers by geometry type (Polygons)', self)
        self.action_check_all_geometry_polygon.triggered.connect(partial(self.select_by_geometry, 'GeometryType.Polygon', Qt.Checked))
        self.action_uncheck_all_geometry_polygon = QAction('De-Select all layers by geometry type (Polygon)', self)
        self.action_uncheck_all_geometry_polygon.triggered.connect(partial(self.select_by_geometry, 'GeometryType.Polygon', Qt.Unchecked))

        self.context_menu.addAction(self.action_check_all)
        self.context_menu.addAction(self.action_uncheck_all)
        self.context_menu.addSeparator()    
        self.context_menu.addAction(self.action_check_all_geometry_line)
        self.context_menu.addAction(self.action_uncheck_all_geometry_line)
        self.context_menu.addSeparator()    
        self.context_menu.addAction(self.action_check_all_geometry_point)
        self.context_menu.addAction(self.action_uncheck_all_geometry_point)
        self.context_menu.addSeparator()        
        self.context_menu.addAction(self.action_check_all_geometry_polygon)
        self.context_menu.addAction(self.action_uncheck_all_geometry_polygon)

    def addItem(self, icon, text, data=None):
        """
        Add an item to the combobox with icon and optional data.
        
        Args:
            icon: QIcon for the layer
            text: Display text (layer name)
            data: Optional user data (dict with layer_geometry_type, etc.)
            
        v4.0.2 BUGFIX: Use setData(icon, Qt.DecorationRole) instead of setIcon()
        This ensures the ItemDelegate can retrieve the icon via index.data(Qt.DecorationRole)
        """
        item = QStandardItem()
        item.setCheckable(True)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
        item.setData(Qt.Unchecked, Qt.CheckStateRole)
        
        # Set text first
        item.setText(text)
        item.setData(text, role=Qt.DisplayRole)
        
        # CRITICAL: Use setData() with DecorationRole, NOT setIcon()
        # setIcon() doesn't properly expose the icon to ItemDelegate.paint()
        if icon and not icon.isNull():
            item.setData(icon, role=Qt.DecorationRole)
            geom_type = data.get('layer_geometry_type', 'Unknown') if data else 'Unknown'
            logger.debug(f"QgsCheckableComboBoxLayer.addItem: '{text}' with icon (geom_type={geom_type})")
        else:
            logger.warning(f"QgsCheckableComboBoxLayer.addItem: '{text}' has NULL or missing icon!")
        
        if data is not None:
            item.setData(data, role=Qt.UserRole)

        self.model().appendRow(item)

    def setItemCheckState(self, i, state=None):
        """Set or toggle the check state of an item."""
        item = self.model().item(i)
        if item is None:
            return
        if state is not None:
            item.setCheckState(state)
        else:
            state = item.data(Qt.CheckStateRole)
            if state == Qt.Checked:
                item.setCheckState(Qt.Unchecked)
            elif state == Qt.Unchecked:
                item.setCheckState(Qt.Checked)

    def setItemsCheckState(self, input_list, state):
        """Set check state for multiple items by index."""
        assert isinstance(input_list, list)
        for i in input_list:
            item = self.model().item(i)
            if item:
                item.setCheckState(state)
        self.checkedItemsChangedEvent()

    def setCheckedItems(self, input_list):
        """Set checked items by text matching."""
        assert isinstance(input_list, list)
        for text in input_list:
            items = self.model().findItems(text)
            for item in items:
                item.setCheckState(Qt.Checked)

    def select_all(self):
        """Select all items."""
        for i in range(self.count()):
            item = self.model().item(i)
            if item:
                item.setCheckState(Qt.Checked)
        self.checkedItemsChangedEvent()

    def deselect_all(self):
        """Deselect all items."""
        for i in range(self.count()):
            item = self.model().item(i)
            if item:
                item.setCheckState(Qt.Unchecked)       
        self.checkedItemsChangedEvent()

    def select_by_geometry(self, geometry_type, state):
        """Select/deselect items by geometry type."""
        items_to_be_checked = []
        for i in range(self.count()):
            item = self.model().item(i)
            if item:
                data = item.data(Qt.UserRole)
                if data and isinstance(data, dict) and "layer_geometry_type" in data:
                    if data["layer_geometry_type"] == geometry_type:
                        items_to_be_checked.append(i)
        self.setItemsCheckState(items_to_be_checked, state)

    def eventFilter(self, obj, event):
        """Handle mouse events for item selection and context menu."""
        if event.type() == QEvent.MouseButtonRelease and obj == self.view().viewport() and event.button() == Qt.LeftButton:
            index = self.view().currentIndex()
            item = self.model().itemFromIndex(index)
            if item:
                state = index.data(Qt.CheckStateRole)
                if state == Qt.Checked:
                    item.setCheckState(Qt.Unchecked)
                elif state == Qt.Unchecked:
                    item.setCheckState(Qt.Checked)
            return True
        elif event.type() == QEvent.MouseButtonRelease and obj in [self.view().viewport(), self] and event.button() == Qt.RightButton:
            action = self.context_menu.exec_(QCursor.pos())
            if action:
                return True
            else:
                return False
        return False

    def itemCheckState(self, i):
        """Get the check state of an item by index."""
        item = self.model().item(i)
        if item:
            return item.checkState()
        return None

    def checkedItems(self):
        """Get list of checked item texts (layer names)."""
        checked_items = []
        for i in range(self.count()):
            item = self.model().item(i)
            if item and item.checkState() == Qt.Checked:
                checked_items.append(item.text())
        checked_items.sort()
        return checked_items

    def checkedItemsChangedEvent(self):
        """Emit the checkedItemsChanged signal."""
        event = self.checkedItems()
        self.checkedItemsChanged.emit(event)

    def paintEvent(self, event):
        """Custom paint to show checked items as CSV in the display."""
        painter = QStylePainter(self)
        painter.setPen(self.palette().color(QPalette.Text))
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        opt.currentText = ",".join(self.checkedItems())
        painter.drawComplexControl(QStyle.CC_ComboBox, opt)
        painter.drawControl(QStyle.CE_ComboBoxLabel, opt)


class ListWidgetWrapper(QListWidget):
    """
    Wrapper for QListWidget that stores feature list metadata.
    
    Restored from before_migration/modules/widgets.py for full functionality.
    Stores display expression, filter state, and feature lists for the picker widget.
    """
  
    def __init__(self, identifier_field_name, primary_key_is_numeric, parent=None):
        super(ListWidgetWrapper, self).__init__(parent)

        # Dynamic sizing based on config - match before_migration/UIConfig compact profile
        # before_migration: list.min_height = 225px (ratio 1.5x for 5-6 items display)
        try:
            from ...config.config import ENV_VARS
            # Try to get from config, fallback to before_migration compact profile default
            ui_config = ENV_VARS.get('CONFIG_DATA', {}).get('APP', {}).get('DOCKWIDGET', {})
            list_min_height = ui_config.get('list_min_height', 225)
        except (ImportError, AttributeError, KeyError, TypeError):
            list_min_height = 225  # Match before_migration compact profile
        
        self.setMinimumHeight(list_min_height)
        self.identifier_field_name = identifier_field_name
        self.identifier_field_type_numeric = primary_key_is_numeric
        self.filter_expression = ''
        self.filter_text = ''
        self.display_expression = ''
        self.field_flag = False
        self.subset_string = ''
        self.features_list = []
        self.filter_expression_features_id_list = []
        self.visible_features_list = []
        self.selected_features_list = []
        self.limit = 1000
        self.total_features_list_count = 0

    def setFilterExpression(self, filter_expression):
        self.filter_expression = filter_expression

    def setIdentifierFieldName(self, identifier_field_name):
        self.identifier_field_name = identifier_field_name

    def setFilterText(self, filter_text):
        self.filter_text = filter_text

    def setDisplayExpression(self, display_expression):
        self.display_expression = display_expression

    def setExpressionFieldFlag(self, field_flag):
        self.field_flag = field_flag    
    
    def setSubsetString(self, subset_string):
        self.subset_string = subset_string

    def setTotalFeaturesListCount(self, total_features_list_count):
        self.total_features_list_count = total_features_list_count

    def setFeaturesList(self, features_list):
        self.features_list = features_list

    def setFilterExpressionFeaturesIdList(self, filter_expression_features_id_list):
        self.filter_expression_features_id_list = filter_expression_features_id_list

    def setVisibleFeaturesList(self, visible_features_list):
        self.visible_features_list = visible_features_list

    def setSelectedFeaturesList(self, selected_features_list):
        self.selected_features_list = selected_features_list

    def setCheckedByFeatureIds(self, feature_ids, parent_widget=None):
        """
        Check items in the list widget by matching feature IDs.
        
        This method updates the visual checkbox state (unlike setSelectedFeaturesList
        which only stores data). The feature ID is stored in item.data(3).
        
        Args:
            feature_ids: List of feature IDs to check
            parent_widget: Optional parent QgsCheckableComboBoxFeaturesListPickerWidget
                          for accessing font_by_state styling
        
        Returns:
            int: Number of items that were successfully checked
        """
        if not feature_ids:
            return 0
        
        # Convert to set for O(1) lookup
        feature_ids_set = set(feature_ids)
        checked_count = 0
        
        for i in range(self.count()):
            item = self.item(i)
            if item:
                item_fid = item.data(3)  # Feature ID is stored in data(3)
                
                if item_fid in feature_ids_set:
                    item.setCheckState(Qt.Checked)
                    # Update font styling if parent_widget provided
                    if parent_widget and hasattr(parent_widget, 'font_by_state'):
                        # Check if item is in subset (data(4) == "True")
                        is_in_subset = item.data(4) == "True"
                        if is_in_subset:
                            item.setData(6, parent_widget.font_by_state['checked'][0])
                            item.setData(9, QBrush(parent_widget.font_by_state['checked'][1]))
                        else:
                            item.setData(6, parent_widget.font_by_state['checkedFiltered'][0])
                            item.setData(9, QBrush(parent_widget.font_by_state['checkedFiltered'][1]))
                    checked_count += 1
                else:
                    # Uncheck items not in the selection
                    if item.checkState() == Qt.Checked:
                        item.setCheckState(Qt.Unchecked)
                        if parent_widget and hasattr(parent_widget, 'font_by_state'):
                            is_in_subset = item.data(4) == "True"
                            if is_in_subset:
                                item.setData(6, parent_widget.font_by_state['unChecked'][0])
                                item.setData(9, QBrush(parent_widget.font_by_state['unChecked'][1]))
                            else:
                                item.setData(6, parent_widget.font_by_state['unCheckedFiltered'][0])
                                item.setData(9, QBrush(parent_widget.font_by_state['unCheckedFiltered'][1]))
        
        # Also update the stored selected_features_list
        self.selected_features_list = [[str(fid), fid, True] for fid in feature_ids]
        
        return checked_count
    
    def setLimit(self, limit):
        self.limit = limit

    def getFilterExpression(self):
        return self.filter_expression

    def getIdentifierFieldName(self):
        return self.identifier_field_name
    
    def getFilterText(self):
        return self.filter_text

    def getDisplayExpression(self):
        return self.display_expression
    
    def getExpressionFieldFlag(self):
        return self.field_flag
    
    def getSubsetString(self):
        return self.subset_string
    
    def getTotalFeaturesListCount(self):
        return self.total_features_list_count
      
    def getFilterExpressionFeaturesIdList(self):
        return self.filter_expression_features_id_list

    def getFeaturesList(self):
        return self.features_list
    
    def getVisibleFeaturesList(self):
        return self.visible_features_list
    
    def getSelectedFeaturesList(self):
        return self.selected_features_list

    def getLimit(self):
        return self.limit
    
    def sortFeaturesListByDisplayExpression(self, nonSubset_features_list=[], reverse=False):
        """
        Sort features list by display expression.
        
        Args:
            nonSubset_features_list: List of feature IDs that are not in the current subset
            reverse: If True, sort in descending order (DESC)
        """
        def safe_sort_key(k):
            # k[0] is the display expression value, k[1] is the feature id
            # Handle None values by converting to empty string for comparison
            display_value = k[0] if k[0] is not None else ""
            is_in_subset = k[1] not in nonSubset_features_list
            return (is_in_subset, display_value)
        
        self.features_list.sort(key=safe_sort_key, reverse=reverse)


class QgsCheckableComboBoxFeaturesListPickerWidget(QWidget):
    """
    A widget for selecting multiple features from a layer with async loading.
    
    Restored from before_migration/modules/widgets.py with full functionality:
    - Asynchronous population using QgsTask (PopulateListEngineTask)
    - Live search/filter with debouncing (300ms)
    - Multi-select with checkboxes and font styling by state
    - Context menu (Select All, Deselect All, subset filtering)
    - ListWidgetWrapper for each layer with feature caching
    - Sort order support (ASC/DESC)
    
    Signals:
        updatingCheckedItemList: Emitted when checked items list is updated (list, flag)
        filteringCheckedItemList: Emitted when filtering checked items
    """
    
    updatingCheckedItemList = pyqtSignal(list, bool)
    filteringCheckedItemList = pyqtSignal()
    
    def __init__(self, config_data, parent=None):
        QWidget.__init__(self, parent)

        self.config_data = config_data
        
        # Dynamic sizing based on config matching before_migration/UIConfig compact profile
        # before_migration: combobox.height = 36px, list.min_height = 225px
        # New v4.0: combobox.height = 26px (from QSS), list.min_height = 225px (ratio 1.5x)
        try:
            from ...config.config import ENV_VARS
            # Try to get from config, fallback to hardcoded defaults
            ui_config = ENV_VARS.get('CONFIG_DATA', {}).get('APP', {}).get('DOCKWIDGET', {})
            combobox_height = ui_config.get('combobox_height', 26)  # From QSS standard
            list_min_height = ui_config.get('list_min_height', 225)  # From before_migration compact
        except (AttributeError, TypeError, ValueError, ImportError, KeyError):
            combobox_height = 26  # Match QSS standard height
            list_min_height = 225  # Match before_migration compact profile (ratio 1.5x for 5-6 items)
        
        # Calculate total height: 2 QLineEdit + spacing + list
        # Match before_migration formula: lineedit_height + list_min_height + 4
        lineedit_height = combobox_height * 2 + 2  # 2 lineEdit (26px each) + 2px spacing = 54px
        total_min_height = lineedit_height + list_min_height + 4  # 54 + 225 + 4 = 283px
        
        self.setMinimumWidth(30)
        self.setMaximumWidth(16777215)
        self.setMinimumHeight(total_min_height)
        # Remove setMaximumHeight to allow expansion (before_migration pattern)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.PointingHandCursor)

        font = QFont("Segoe UI", 8)
        self.setFont(font)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)
        self.filter_le = QLineEdit(self)
        self.filter_le.setPlaceholderText('Type to filter...')
        self.items_le = QLineEdit(self)
        self.items_le.setReadOnly(True)

        self.layout.addWidget(self.filter_le)
        self.layout.addWidget(self.items_le)

        # Context menu
        self.context_menu = QMenu(self)
        self.action_check_all = QAction('Select All', self)
        self.action_check_all.triggered.connect(lambda state, x='Select All': self.select_all(x))
        self.action_check_all_non_subset = QAction('Select All (non subset)', self)
        self.action_check_all_non_subset.triggered.connect(lambda state, x='Select All (non subset)': self.select_all(x))
        self.action_check_all_subset = QAction('Select All (subset)', self)
        self.action_check_all_subset.triggered.connect(lambda state, x='Select All (subset)': self.select_all(x))
        self.action_uncheck_all = QAction('De-select All', self)
        self.action_uncheck_all.triggered.connect(lambda state, x='De-select All': self.deselect_all(x))
        self.action_uncheck_all_non_subset = QAction('De-select All (non subset)', self)
        self.action_uncheck_all_non_subset.triggered.connect(lambda state, x='De-select All (non subset)': self.deselect_all(x))
        self.action_uncheck_all_subset = QAction('De-select All (subset)', self)
        self.action_uncheck_all_subset.triggered.connect(lambda state, x='De-select All (subset)': self.deselect_all(x))

        self.context_menu.addAction(self.action_check_all)
        self.context_menu.addAction(self.action_check_all_non_subset)
        self.context_menu.addAction(self.action_check_all_subset)
        self.context_menu.addSeparator()
        self.context_menu.addAction(self.action_uncheck_all)
        self.context_menu.addAction(self.action_uncheck_all_non_subset)
        self.context_menu.addAction(self.action_uncheck_all_subset)

        # Font colors for different states
        try:
            from ...config.config import ENV_VARS
            font_colors = ENV_VARS.get('FONTS', {}).get('colors', ['#000000', '#808080', '#0000FF'])
            if len(font_colors) < 3:
                font_colors = ['#000000', '#808080', '#0000FF']
        except (ImportError, AttributeError, KeyError):
            font_colors = ['#000000', '#808080', '#0000FF']
            
        self.font_by_state = {
            'unChecked': (QFont("Segoe UI", 8, QFont.Medium), QColor(font_colors[0])),
            'checked': (QFont("Segoe UI", 8, QFont.Bold), QColor(font_colors[0])),
            'unCheckedFiltered': (QFont("Segoe UI", 8, QFont.Medium), QColor(font_colors[2])),
            'checkedFiltered': (QFont("Segoe UI", 8, QFont.Bold), QColor(font_colors[2]))
        }

        self.list_widgets = {}
        self.tasks = {}

        self.tasks['buildFeaturesList'] = {}
        self.tasks['updateFeaturesList'] = {}
        self.tasks['loadFeaturesList'] = {}
        self.tasks['selectAllFeatures'] = {}
        self.tasks['deselectAllFeatures'] = {}
        self.tasks['filterFeatures'] = {}
        self.tasks['updateFeatures'] = {}

        self.last_layer = None
        self.layer = None
        self.is_field_flag = None
        self._cached_layer_name = None
        
        # Sort order settings (ASC/DESC)
        self._sort_order = 'ASC'
        self._sort_field = None
        
        # Debounce timer for filter text input
        self._filter_debounce_timer = QTimer(self)
        self._filter_debounce_timer.setSingleShot(True)
        self._filter_debounce_timer.setInterval(300)  # 300ms debounce delay
        self._filter_debounce_timer.timeout.connect(self._execute_filter)

    def setSortOrder(self, order='ASC', field=None):
        """Set the sort order for the features list."""
        self._sort_order = order
        self._sort_field = field
        logger.debug(f"QgsCheckableComboBoxFeaturesListPickerWidget.setSortOrder: order={order}, field={field}")
        
        if self.layer is not None and self.layer.id() in self.list_widgets:
            expression = self.list_widgets[self.layer.id()].getDisplayExpression()
            if expression:
                self.setDisplayExpression(expression)
    
    def getSortOrder(self):
        """Get the current sort order settings."""
        return (self._sort_order, self._sort_field)

    def checkedItems(self):
        """Get list of checked items with their data."""
        selection = []
        if self.layer is None or self.layer.id() not in self.list_widgets:
            return selection
            
        for i in range(self.list_widgets[self.layer.id()].count()):
            item = self.list_widgets[self.layer.id()].item(i)
            if item and item.checkState() == Qt.Checked:
                selection.append([item.data(0), item.data(3), item.data(6), item.data(9)])
        selection.sort(key=lambda k: k[0])
        return selection

    def displayExpression(self):
        """Get current display expression."""
        if self.layer is not None and self.layer.id() in self.list_widgets:
            return self.list_widgets[self.layer.id()].getDisplayExpression()
        return False
      
    def currentLayer(self):
        """Get current layer or False if none."""
        if self.layer is not None:
            return self.layer
        return False
    
    def currentSelectedFeatures(self):
        """Get currently selected features list or False if none."""
        if self.layer is not None:
            if self.layer.id() not in self.list_widgets:
                return False
            current_selected_features = self.list_widgets[self.layer.id()].getSelectedFeaturesList()
            return current_selected_features if len(current_selected_features) > 0 else False
        return False
        
    def currentVisibleFeatures(self):
        """Get currently visible features list or False if none."""
        if self.layer is not None:
            if self.layer.id() not in self.list_widgets:
                return False
            visible_features_list = self.list_widgets[self.layer.id()].getVisibleFeaturesList()
            return visible_features_list if len(visible_features_list) > 0 else False
        return False

    def setLayer(self, layer, layer_props, skip_task=False):
        """
        Set the current layer and initialize its list widget.
        
        Args:
            layer: QgsVectorLayer to display features from
            layer_props: Dictionary with layer properties including:
                - infos.primary_key_name: Primary key field name
                - infos.primary_key_is_numeric: Whether PK is numeric
                - exploring.multiple_selection_expression: Display expression
            skip_task: If True, skip launching the feature loading task (useful during
                widget reload to avoid redundant task execution)
        """
        try:
            if layer is not None:
                # Cancel all tasks for the OLD layer BEFORE changing to new layer
                if self.layer is not None:
                    old_layer_id = self.layer.id()
                    self._filter_debounce_timer.stop()
                    for task_type in self.tasks:
                        if old_layer_id in self.tasks[task_type]:
                            try:
                                task = self.tasks[task_type][old_layer_id]
                                if isinstance(task, QgsTask):
                                    task.cancel()
                                    logger.debug(f"Cancelled task {task_type} for old layer {old_layer_id}")
                            except (RuntimeError, KeyError):
                                pass
                    
                    self.filter_le.clear()
                    self.items_le.clear()
                    
                self.layer = layer
                self._cached_layer_name = layer.name()

                # Ensure the widget exists for the new layer
                if self.layer.id() not in self.list_widgets:
                    self.manage_list_widgets(layer_props)

                # Validate required keys exist
                pk_name = layer_props.get("infos", {}).get("primary_key_name")
                if pk_name is not None and self.layer.id() in self.list_widgets:
                    if self.list_widgets[self.layer.id()].getIdentifierFieldName() != pk_name:
                        logger.debug(f"Updating identifier field from '{self.list_widgets[self.layer.id()].getIdentifierFieldName()}' to '{pk_name}'")
                        self.list_widgets[self.layer.id()].setIdentifierFieldName(pk_name)
                    
                    # Reset stale display expression when reusing widget
                    current_expr = self.list_widgets[self.layer.id()].getDisplayExpression()
                    if current_expr and current_expr != pk_name:
                        logger.debug(f"Resetting stale display expression '{current_expr}'")
                        self.list_widgets[self.layer.id()].setDisplayExpression("")

                # Refresh widgets
                self.manage_list_widgets(layer_props)

                if self.layer.id() in self.list_widgets:
                    self.filter_le.setText(self.list_widgets[self.layer.id()].getFilterText())

                    # Update display expression
                    expected_expression = layer_props.get("exploring", {}).get("multiple_selection_expression", "")
                    current_expression = self.list_widgets[self.layer.id()].getDisplayExpression()
                    
                    if current_expression != expected_expression or not current_expression:
                        logger.debug(f"Updating display expression to '{expected_expression}'")
                        self.setDisplayExpression(expected_expression, skip_task=skip_task)
                    elif not skip_task:
                        # Only launch task if not skipped and expression already correct
                        self._populate_features_sync(expected_expression)
                else:
                    logger.error(f"Failed to create list widget for layer {self.layer.id()}")

        except (AttributeError, RuntimeError) as e:
            try:
                self.filter_le.clear()
                self.items_le.clear()
            except (AttributeError, RuntimeError):
                pass

    def setFilterExpression(self, filter_expression, layer_props):
        """Set the filter expression for the current layer."""
        if self.layer is not None:
            if self.layer.id() not in self.list_widgets:
                self.manage_list_widgets(layer_props)
            if self.layer.id() in self.list_widgets:  
                if filter_expression != self.list_widgets[self.layer.id()].getFilterExpression():
                    if QgsExpression(filter_expression).isField() is False:
                        self.list_widgets[self.layer.id()].setFilterExpression(filter_expression)
                        expression = self.list_widgets[self.layer.id()].getDisplayExpression()
                        self.setDisplayExpression(expression)

    def setDisplayExpression(self, expression, skip_task=False):
        """Set the display expression and rebuild the features list.
        
        Args:
            expression: The display expression to use
            skip_task: If True, skip the feature population task
        """
        logger.debug(f"QgsCheckableComboBoxFeaturesListPickerWidget.setDisplayExpression: {expression}, skip_task={skip_task}")
        
        if self.layer is not None:
            if self.layer.id() not in self.list_widgets:
                logger.warning(f"No list widget found for layer {self.layer.id()}")
                return
            
            self.filter_le.clear()
            self.items_le.clear()
            
            # Handle empty or invalid expression
            working_expression = expression
            if not expression or expression.strip() == '':
                identifier_field = self.list_widgets[self.layer.id()].getIdentifierFieldName()
                if identifier_field:
                    logger.debug(f"Empty expression, using identifier field '{identifier_field}'")
                    working_expression = identifier_field
                    self.list_widgets[self.layer.id()].setExpressionFieldFlag(True)
                else:
                    field_names = [field.name() for field in self.layer.fields()]
                    if field_names:
                        working_expression = field_names[0]
                        logger.debug(f"No identifier field, using first field '{working_expression}'")
                        self.list_widgets[self.layer.id()].setExpressionFieldFlag(True)
                    else:
                        logger.warning(f"No fields available for layer")
                        return
            elif QgsExpression(expression).isField():
                working_expression = expression.replace('"', '')
                self.list_widgets[self.layer.id()].setExpressionFieldFlag(True)
            else:
                expr = QgsExpression(expression)
                if not expr.isValid():
                    identifier_field = self.list_widgets[self.layer.id()].getIdentifierFieldName()
                    if identifier_field:
                        logger.debug(f"Invalid expression '{expression}', using identifier field")
                        working_expression = identifier_field
                        self.list_widgets[self.layer.id()].setExpressionFieldFlag(True)
                    else:
                        logger.warning(f"Invalid expression and no identifier field")
                        return
                else:
                    working_expression = expression
                    self.list_widgets[self.layer.id()].setExpressionFieldFlag(False)

            self.list_widgets[self.layer.id()].setDisplayExpression(working_expression)

            # Clear widget before rebuilding
            try:
                self.list_widgets[self.layer.id()].clear()
                self.list_widgets[self.layer.id()].viewport().update()
                from qgis.PyQt.QtCore import QCoreApplication
                QCoreApplication.processEvents()
            except Exception as clear_err:
                logger.debug(f"Could not clear widget: {clear_err}")

            # Build features list synchronously (unless skipped)
            if not skip_task:
                self._populate_features_sync(working_expression)

    def _populate_features_sync(self, expression):
        """Populate features list synchronously."""
        if self.layer is None or self.layer.id() not in self.list_widgets:
            return
            
        list_widget = self.list_widgets[self.layer.id()]
        list_widget.clear()
        
        # Build expression
        expr = QgsExpression(expression) if expression and not QgsExpression(expression).isField() else None
        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.layer))
        
        identifier_field = list_widget.getIdentifierFieldName()
        
        # Request features
        request = QgsFeatureRequest()
        request.setFlags(QgsFeatureRequest.NoGeometry)
        
        features_data = []
        for feature in safe_iterate_features(self.layer, request):
            try:
                fid = feature[identifier_field] if identifier_field else feature.id()
                
                if expr:
                    context.setFeature(feature)
                    display_value = str(expr.evaluate(context))
                else:
                    # Simple field access
                    display_value = str(feature[expression]) if expression else str(fid)
                
                # UUID FIX v4.0: Ensure fid is converted to string for UUID/text PKs
                # This ensures proper handling when building SQL expressions later
                fid_value = str(fid) if not isinstance(fid, (int, float)) else fid
                features_data.append((display_value, fid_value))
            except Exception as e:
                logger.debug(f"Error processing feature: {e}")
                continue
        
        # Sort features
        reverse = self._sort_order == 'DESC'
        features_data.sort(key=lambda x: (x[0] if x[0] is not None else ""), reverse=reverse)
        
        # Populate list widget
        for display_value, fid in features_data:
            item = QListWidgetItem(display_value)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setData(0, display_value)
            item.setData(3, fid)
            item.setData(4, "True")
            item.setData(6, self.font_by_state['unChecked'][0])
            item.setData(9, QBrush(self.font_by_state['unChecked'][1]))
            list_widget.addItem(item)
        
        list_widget.setFeaturesList(features_data)
        list_widget.setTotalFeaturesListCount(len(features_data))
        
        self.connect_filter_lineEdit()
        logger.debug(f"Populated {len(features_data)} features")

    def eventFilter(self, obj, event):
        """Handle mouse events for feature selection and context menu."""
        if self.layer is None or self.layer.id() not in self.list_widgets:
            return False
        
        if event.type() == QEvent.MouseButtonPress and obj == self.list_widgets[self.layer.id()].viewport():
            identifier_field_name = self.list_widgets[self.layer.id()].getIdentifierFieldName()
            
            try:
                nonSubset_features_list = [feature[identifier_field_name] for feature in safe_iterate_features(self.layer)]
            except Exception:
                nonSubset_features_list = []
            
            if event.button() == Qt.LeftButton:
                clicked_item = self.list_widgets[self.layer.id()].itemAt(event.pos())
                if clicked_item is not None:
                    id_item = clicked_item.data(3)
                    if clicked_item.checkState() == Qt.Checked:
                        clicked_item.setCheckState(Qt.Unchecked)
                        if id_item in nonSubset_features_list:
                            clicked_item.setData(6, self.font_by_state['unChecked'][0])
                            clicked_item.setData(9, QBrush(self.font_by_state['unChecked'][1]))
                            clicked_item.setData(4, "True")
                        else:
                            clicked_item.setData(6, self.font_by_state['unCheckedFiltered'][0])
                            clicked_item.setData(9, QBrush(self.font_by_state['unCheckedFiltered'][1]))
                            clicked_item.setData(4, "False")
                    else:
                        clicked_item.setCheckState(Qt.Checked)
                        if id_item in nonSubset_features_list:
                            clicked_item.setData(6, self.font_by_state['checked'][0])
                            clicked_item.setData(9, QBrush(self.font_by_state['checked'][1]))
                            clicked_item.setData(4, "True")
                        else:   
                            clicked_item.setData(6, self.font_by_state['checkedFiltered'][0])
                            clicked_item.setData(9, QBrush(self.font_by_state['checkedFiltered'][1]))
                            clicked_item.setData(4, "False")
                    
                    # Emit update signal
                    self._emit_checked_items_update()
                return True

            elif event.button() == Qt.RightButton:
                self.context_menu.exec(QCursor.pos())
                return True
        return False

    def _emit_checked_items_update(self):
        """Emit update signal with current checked items."""
        checked = self.checkedItems()
        self.updatingCheckedItemList.emit(checked, True)

    def connect_filter_lineEdit(self):
        """Connect filter line edit to appropriate signal."""
        if self.layer is not None and self.layer.id() in self.list_widgets:
            if self.list_widgets[self.layer.id()].getTotalFeaturesListCount() == self.list_widgets[self.layer.id()].count():
                try:
                    self.filter_le.editingFinished.disconnect()
                except TypeError:
                    pass
                self.filter_le.textChanged.connect(self._on_filter_text_changed)
            else:
                try:
                    self.filter_le.textChanged.disconnect()
                except TypeError:
                    pass
                self.filter_le.editingFinished.connect(self.filter_items)
    
    def _on_filter_text_changed(self, text):
        """Handle filter text changes with debouncing."""
        self._pending_filter_text = text
        self._filter_debounce_timer.start()
    
    def _execute_filter(self):
        """Execute the filter after debounce delay."""
        if hasattr(self, '_pending_filter_text'):
            self.filter_items(self._pending_filter_text)

    def manage_list_widgets(self, layer_props):
        """Manage visibility and creation of list widgets."""
        for key in self.list_widgets.keys():
            self.list_widgets[key].setVisible(False)

        if self.layer.id() in self.list_widgets:
            self.list_widgets[self.layer.id()].setVisible(True)
        else:
            self.add_list_widget(layer_props)

    def remove_list_widget(self, layer_id):
        """Remove list widget for a layer."""
        if layer_id in self.list_widgets:
            for task in self.tasks:
                try:
                    del self.tasks[task][layer_id]
                except KeyError:
                    pass
            try:
                del self.list_widgets[layer_id]
            except KeyError:
                pass

    def reset(self):
        """Reset the widget to initial state."""
        self._filter_debounce_timer.stop()
        self.layer = None
        self.tasks = {
            'buildFeaturesList': {},
            'updateFeaturesList': {},
            'loadFeaturesList': {},
            'selectAllFeatures': {},
            'deselectAllFeatures': {},
            'filterFeatures': {},
            'updateFeatures': {}
        }
        for i in range(self.layout.count()):
            item = self.layout.itemAt(i)
            widget = item.widget()       
            if widget:
                try:
                    widget.close()
                except RuntimeError:
                    pass

        self.list_widgets = {}

    def add_list_widget(self, layer_props):
        """Add a new list widget for the current layer."""
        if "infos" not in layer_props:
            logger.warning("layer_props missing 'infos' dictionary")
            return
        
        infos = layer_props["infos"]
        pk_name = infos.get("primary_key_name")
        pk_is_numeric = infos.get("primary_key_is_numeric", True)
        
        if pk_name is None:
            logger.warning("primary_key_name is None, attempting fallback")
            
            if self.layer is not None:
                fields = self.layer.fields()
                fallback_names = ['fid', 'id', 'ID', 'FID', 'ogc_fid', 'gid']
                for fallback_name in fallback_names:
                    if fields.indexFromName(fallback_name) >= 0:
                        pk_name = fallback_name
                        field = fields.field(fallback_name)
                        pk_is_numeric = field.isNumeric() if field else True
                        logger.info(f"Using fallback identifier field: {pk_name}")
                        break
                
                if pk_name is None and fields.count() > 0:
                    pk_name = fields.field(0).name()
                    pk_is_numeric = fields.field(0).isNumeric()
                    logger.info(f"Using first field as fallback: {pk_name}")
        
        if pk_name is None:
            logger.error("Could not determine identifier field")
            return
        
        self.list_widgets[self.layer.id()] = ListWidgetWrapper(pk_name, pk_is_numeric, self)
        self.list_widgets[self.layer.id()].viewport().installEventFilter(self)
        self.layout.addWidget(self.list_widgets[self.layer.id()])

    def select_all(self, x):
        """Select all items based on action type."""
        if self.layer is None or self.layer.id() not in self.list_widgets:
            return
        
        list_widget = self.list_widgets[self.layer.id()]
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item:
                if x == 'Select All':
                    item.setCheckState(Qt.Checked)
                elif x == 'Select All (subset)' and item.data(4) == "True":
                    item.setCheckState(Qt.Checked)
                elif x == 'Select All (non subset)' and item.data(4) == "False":
                    item.setCheckState(Qt.Checked)
        
        self._emit_checked_items_update()

    def deselect_all(self, x):
        """Deselect all items based on action type."""
        if self.layer is None or self.layer.id() not in self.list_widgets:
            return
        
        list_widget = self.list_widgets[self.layer.id()]
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item:
                if x == 'De-select All':
                    item.setCheckState(Qt.Unchecked)
                elif x == 'De-select All (subset)' and item.data(4) == "True":
                    item.setCheckState(Qt.Unchecked)
                elif x == 'De-select All (non subset)' and item.data(4) == "False":
                    item.setCheckState(Qt.Unchecked)
        
        self._emit_checked_items_update()
        
    def filter_items(self, filter_txt=None):
        """Filter items based on text."""
        if filter_txt is None:
            self.filter_txt = self.filter_le.text()
        else:
            self.filter_txt = filter_txt
        
        if self.layer is None or self.layer.id() not in self.list_widgets:
            return
            
        list_widget = self.list_widgets[self.layer.id()]
        list_widget.setFilterText(self.filter_txt)
        
        filter_lower = self.filter_txt.lower()
        visible_count = 0
        
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item:
                if not filter_lower or filter_lower in item.text().lower():
                    item.setHidden(False)
                    visible_count += 1
                else:
                    item.setHidden(True)
        
        # Update visible features list
        visible_features = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item and not item.isHidden():
                visible_features.append([item.data(0), item.data(3)])
        
        list_widget.setVisibleFeaturesList(visible_features)
        self.filteringCheckedItemList.emit()


    def setCheckedFeatureIds(self, feature_ids):
        """
        Set checked items by feature IDs.
        
        This method synchronizes the widget's checked items with the given feature IDs,
        updating the visual checkbox state and emitting the update signal.
        
        Args:
            feature_ids: List of feature IDs to check. Can be integers or strings.
        
        Returns:
            int: Number of items that were successfully checked
        """
        if self.layer is None or self.layer.id() not in self.list_widgets:
            logger.warning("setCheckedFeatureIds: No layer or list_widget available")
            return 0
        
        if not feature_ids:
            # Clear all selections
            self.deselect_all('De-select All')
            return 0
        
        list_widget = self.list_widgets[self.layer.id()]
        
        # Normalize feature IDs for comparison (handle both int and str types)
        normalized_fids = set()
        for fid in feature_ids:
            normalized_fids.add(fid)
            # Also add string version for text-based PKs
            if not isinstance(fid, str):
                normalized_fids.add(str(fid))
        
        checked_count = list_widget.setCheckedByFeatureIds(normalized_fids, self)
        
        logger.debug(f"setCheckedFeatureIds: Checked {checked_count}/{len(feature_ids)} items")
        
        # Update display text
        checked = self.checkedItems()
        if checked:
            display_text = ", ".join([str(item[0]) for item in checked[:5]])
            if len(checked) > 5:
                display_text += f"... (+{len(checked) - 5})"
            self.items_le.setText(display_text)
        else:
            self.items_le.clear()
        
        # Emit update signal
        self._emit_checked_items_update()
        
        return checked_count

    def getCheckedFeatureIds(self):
        """
        Get list of currently checked feature IDs.
        
        Returns:
            list: List of feature IDs (from item.data(3)) for checked items
        """
        if self.layer is None or self.layer.id() not in self.list_widgets:
            return []
        
        feature_ids = []
        list_widget = self.list_widgets[self.layer.id()]
        
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item and item.checkState() == Qt.Checked:
                feature_ids.append(item.data(3))
        
        return feature_ids


__all__ = [
    'ItemDelegate',
    'ListWidgetWrapper',
    'QgsCheckableComboBoxLayer',
    'QgsCheckableComboBoxFeaturesListPickerWidget',
]

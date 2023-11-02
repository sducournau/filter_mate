# -*- coding: utf-8 -*-
"""
/***************************************************************************
 FilterMateDockWidget
                                 A QGIS plugin
 FilterMate is a Qgis plugin, an everyday companion that allows you to easily filter your vector layers
                             -------------------
        begin                : 2023-10-26
        git sha              : $Format:%H$
        copyright            : (C) 2023 by imagodata
        email                : imagodata+filter_mate@skiff.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from .widgets.config import *
import os
from functools import partial
from qgis.PyQt import QtGui, QtWidgets, uic
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *
from qgis.utils import iface
from qgis.PyQt.QtWidgets import QApplication, QVBoxLayout

from .widgets.qgsCustomCheckableListWidget import QgsCustomCheckableListWidget
from .widgets.qt_json_view.model import JsonModel, JsonSortFilterProxyModel
from .widgets.qt_json_view.view import JsonView

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'filter_mate_dockwidget_base.ui'))


class FilterMateDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()
    launchingTask = pyqtSignal(str)

    gettingProjectLayers = pyqtSignal()
    settingProjectLayers = pyqtSignal(dict)

    def __init__(self, project_layers, plugin_dir, parent=None):
        """Constructor."""
        super(FilterMateDockWidget, self).__init__(parent)
        
        self.iface = iface
        self.PROJECT_LAYERS = project_layers
        self.plugin_dir = plugin_dir

        self.tabTools_current_index = 0
        self.tabWidgets_current_index = 0

        self.current_layer = self.iface.activeLayer()
        self.current_exploring_groupbox = None
        self.auto_change_current_layer_flag = False
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://doc.qt.io/qt-5/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.setupUiCustom()
        self.manage_ui_icons()
        self.manage_ui_style()
        self.manage_interactions()
        self.manage_output_name()

    def setupUiCustom(self):
        self.customCheckableComboBox_exploring_multiple_selection = QgsCustomCheckableListWidget(self)
        self.layout = self.verticalLayout_exploring_multiple_selection
        self.layout.insertWidget(0, self.customCheckableComboBox_exploring_multiple_selection)
        self.manage_configuration_model()

        self.exploring_groupbox_init()

    def manage_configuration_model(self):
        """Manage the qtreeview model configuration"""
        #self.proxy = JsonSortFilterProxyModel()
        self.model = JsonModel(data=CONFIG_DATA, editable_keys=True, editable_values=True)

        #self.proxy.setSourceModel(self.model)
        self.view = JsonView(self.model)
        self.CONFIGURATION.layout().addWidget(self.view)
        #self.view.setModel(self.model)
        self.view.setModel(self.model)


        self.view.setAnimated(True)
        self.view.setDragDropMode(QAbstractItemView.InternalMove)
        self.view.show()
        self.view.setStyleSheet("""padding:0px;
                                    color:black;""")
        
    def manage_output_name(self):
        self.output_name = 'export'
        self.current_project_title = PROJECT.fileName().split('.')[0]
        self.current_project_path = PROJECT.homePath()
        if self.current_project_title is not None:
            self.output_name = 'export' + '_' + str(self.current_project_title)


    def manage_ui_icons(self):

        """SET PUSHBUTTONS' ICONS"""

        """ACTION"""
        icon = QtGui.QIcon(os.path.join(self.plugin_dir,  "icons/filter.png"))
        self.pushButton_action_filter.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(self.plugin_dir,  "icons/unfilter.png"))
        self.pushButton_action_unfilter.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(self.plugin_dir,  "icons/export.png"))
        self.pushButton_action_export.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(self.plugin_dir,  "icons/logo.png"))
        self.pushButton_action_help.setIcon(icon)


        """EXPLORING"""
        icon = QtGui.QIcon(os.path.join(self.plugin_dir,  "icons/selection_7.png"))
        self.pushButton_exploring_identify.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(self.plugin_dir,  "icons/zoom_2.png"))
        self.pushButton_exploring_zoom.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(self.plugin_dir,  "icons/selection_3.png"))
        self.pushButton_checkable_exploring_selecting.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(self.plugin_dir,  "icons/zoom_1.png"))
        self.pushButton_checkable_exploring_tracking.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(self.plugin_dir,  "icons/link.png"))
        self.pushButton_checkable_exploring_linking_widgets.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(self.plugin_dir,  "icons/auto_save.png"))
        self.pushButton_checkable_exploring_saving_parameters.setIcon(icon)



        """FILTERING"""
        icon = QtGui.QIcon(os.path.join(self.plugin_dir,  "icons/change_2.png"))
        self.pushButton_checkable_filtering_auto_current_layer.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(self.plugin_dir,  "icons/layers.png"))
        self.pushButton_checkable_filtering_layers_to_filter.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(self.plugin_dir,  "icons/add.png"))
        self.pushButton_checkable_filtering_current_layer_add.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(self.plugin_dir,  "icons/geo_1.png"))
        self.pushButton_checkable_filtering_geometric_predicates.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(self.plugin_dir,  "icons/geo_tampon.png"))
        self.pushButton_checkable_filtering_buffer.setIcon(icon)


        """EXPORTING"""
        icon = QtGui.QIcon(os.path.join(self.plugin_dir,  "icons/layers.png"))
        self.pushButton_checkable_exporting_layers.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(self.plugin_dir,  "icons/projection_1.png"))
        self.pushButton_checkable_exporting_projection.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(self.plugin_dir,  "icons/styles_1.png"))
        self.pushButton_checkable_exporting_styles.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(self.plugin_dir,  "icons/datatype.png"))
        self.pushButton_checkable_exporting_datatype.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(self.plugin_dir,  "icons/folder_white.png"))
        self.pushButton_checkable_exporting_output_folder.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(self.plugin_dir,  "icons/zip.png"))
        self.pushButton_checkable_exporting_zip.setIcon(icon)







    def manage_ui_style(self):

        """Manage the plugin style"""

        combobox_style = """
                        QgsFeaturePickerWidget
                        {
                        background-color:{color_1};
                        border: 1px solid {color_1};
                        border-radius: 3px;
                        padding: 3px 3px 3px 3px;
                        color:{color_3};
                        }
                        QgsFeaturePickerWidget:hover
                        {
                        border: 2px solid {color_3};
                        }
                        QgsFeaturePickerWidget QAbstractItemView 
                        {
                        background: {color_1};
                        selection-background-color:{color_3};
                        color:{color_3};
                        border: 2px solid {color_3};
                        }
                        QgsProjectionSelectionWidget
                        {
                        background-color:{color_1};
                        border: 1px solid {color_1};
                        border-radius: 3px;
                        padding: 3px 3px 3px 3px;
                        color:{color_3};
                        }
                        QgsProjectionSelectionWidget:hover
                        {
                        border: 2px solid {color_3};
                        }
                        QgsProjectionSelectionWidget QAbstractItemView 
                        {
                        background: {color_1};
                        selection-background-color:{color_3};
                        color:{color_3};
                        border: 2px solid {color_3};
                        }
                        QgsMapLayerComboBox
                        {
                        background-color:{color_1};
                        border: 1px solid {color_1};
                        border-radius: 3px;
                        padding: 3px 3px 3px 3px;
                        color:{color_3};
                        }
                        QgsMapLayerComboBox:hover
                        {
                        border: 2px solid {color_3};
                        }
                        QgsMapLayerComboBox QAbstractItemView 
                        {
                        background: {color_1};
                        selection-background-color:{color_3};
                        color:{color_3};
                        border: 2px solid {color_3};
                        }
                        QgsFieldComboBox
                        {
                        background-color:{color_1};
                        border: 1px solid {color_1};
                        border-radius: 3px;
                        padding: 3px 3px 3px 3px;
                        color:{color_3};
                        }
                        QgsFieldComboBox:hover
                        {
                        border: 2px solid {color_3};
                        }
                        QgsFieldComboBox QAbstractItemView {

                        background: {color_1};
                        selection-background-color:{color_3};
                        color:{color_3};
                        border: 2px solid {color_3};
                        }
                        QgsFieldComboBox
                        {
                        background-color:{color_1};
                        border: 1px solid {color_1};
                        border-radius: 3px;
                        padding: 3px 3px 3px 3px;
                        color:{color_3};
                        }
                        QgsFieldComboBox:hover
                        {
                        border: 2px solid {color_3};
                        }
                        QgsFieldComboBox QAbstractItemView {

                        background: {color_1};
                        selection-background-color:{color_3};
                        color:{color_3};
                        border: 2px solid {color_3};
                        }
                        QgsFieldExpressionWidget
                        {
                        background-color:{color_1};
                        border: 1px solid {color_1};
                        border-radius: 3px;
                        padding: 3px 3px 3px 3px;
                        color:{color_3};
                        }
                        QgsFieldExpressionWidget:hover
                        {
                        border: 2px solid {color_3};
                        }
                        QgsFieldExpressionWidget QAbstractItemView {

                        background: {color_1};
                        selection-background-color:{color_3};
                        color:{color_3};
                        border: 2px solid {color_3};
                        }
                        QgsCheckableComboBox
                        {
                         background-color:{color_1};
                        border: 1px solid {color_1};
                        border-radius: 3px;
                        padding: 3px 3px 3px 3px;
                        color:{color_3};

                        }

                        QgsCheckableComboBox:hover
                        {

                        border: 2px solid {color_3};

                        }

                        QgsCheckableComboBox QAbstractItemView {

                          background: {color_1};
                          selection-background-color: {color_2};
                            color:{color_3};
                            border: 2px solid {color_3};
                        }
                        QComboBox
                        {
                         background-color:{color_1};
                        border: 1px solid {color_1};
                        border-radius: 3px;
                        padding: 3px 3px 3px 3px;
                        color:{color_3};

                        }

                        QComboBox:hover
                        {

                        border: 2px solid {color_3};

                        }

                        QComboBox QAbstractItemView {

                          background: {color_1};
                          selection-background-color: {color_2};
                          color:{color_3};
                          border: 2px solid {color_3};
                        }
                        """




        checkbox_style = """QCheckBox:hover
                            {
                            background-color: {color};
                            }
                            QCheckBox:pressed
                            {
                            background-color: {color};
                            border: 2px solid black;
                            }
                            QCheckBox:checked
                            {
                            background-color:{color};
                            border: 2px solid black;
                            }
                            QCheckBox::indicator
                            {
                            border: none;
                            background: none;
                            }
                            QCheckBox::indicator:checked
                            {
                            background: none;
                            }"""

        pushbutton_style = """QPushButton
                            {
                            border-radius: 10px;
                            padding: 10px 10px 10px 10px;
                            }
                            QPushButton:hover
                            {
                            background-color: {color};
                            }
                            QPushButton:pressed
                            {
                            background-color: {color};
                            border: 2px solid black;
                            }
                            QPushButton:checked
                            {
                            background-color: {color};
                            border: 2px solid black;
                            }
                            """
        dock_style = ("""QWidget
                        {
                        background: {color};
                        }""")
        
        groupbox_style = """QGroupBox
                            {
                            background-color: {color_1};
                            border-color: rgb(0, 0, 0);
                            border-radius:6px;
                            padding: 10px 10px 10px 10px;
                            color:{color_3}
                            }"""

        expression_style = """
                                background-color: {color_2};
                                color:{color_1};
                                border-radius: 3px;
                                padding: 3px 3px 3px 3px;"""

        combobox_style = combobox_style.replace("{color_1}",COLORS["BACKGROUND"][1]).replace("{color_2}",COLORS["BACKGROUND"][2]).replace("{color_3}",COLORS["FONT"][1])

        checkbox_style = checkbox_style.replace("{color}",COLORS["BACKGROUND"][1])

        pushbutton_style = pushbutton_style.replace("{color}",COLORS["BACKGROUND"][1])

        dock_style = dock_style.replace("{color}",COLORS["BACKGROUND"][2])

        groupbox_style = groupbox_style.replace("{color_1}",COLORS["BACKGROUND"][0]).replace("{color_3}",COLORS["FONT"][1])

        expression_style = expression_style.replace("{color_1}",COLORS["FONT"][1]).replace("{color_2}",COLORS["BACKGROUND"][1])


        # self.toolBox_tabWidgets.setStyleSheet("""background-color: {};
        #                                                 border-color: rgb(0, 0, 0);
        #                                                 border-radius:6px;
        #                                                 padding: 10px 10px 10px 10px;
        #                                                 color:{};""".format(COLORS["BACKGROUND"][0],COLORS["FONT"][0]))



        # selfS.setStyleSheet("""background-color: {};
        #                                                 border-color: rgb(0, 0, 0);
        #                                                 border-radius:6px;
        #                                                 marging: 25px 10px 10px 10px;
        #                                                 color:{};""".format(COLORS["BACKGROUND"][0],COLORS["FONT"][0]))









        """SET STYLES"""
        
        """DOCK"""
        self.dockWidgetContents.setStyleSheet(dock_style)

        self.toolBox_tabTools.setStyleSheet("""background-color: {};
                                                        border-color: rgb(0, 0, 0);
                                                        border-radius:6px;
                                                        padding: 10px 10px 10px 10px;
                                                        color:{};""".format(COLORS["BACKGROUND"][0],COLORS["FONT"][0]))
        
        self.group_exploring.setStyleSheet(groupbox_style)

        self.CONFIGURATION.setStyleSheet("""background-color: {};
                                                        border-color: rgb(0, 0, 0);
                                                        border-radius:6px;
                                                        marging: 25px 10px 10px 10px;
                                                        color:{};""".format(COLORS["BACKGROUND"][0],COLORS["FONT"][0]))



        """ACTION"""
        self.pushButton_action_filter.setStyleSheet(pushbutton_style)
        self.pushButton_action_unfilter.setStyleSheet(pushbutton_style)
        self.pushButton_action_export.setStyleSheet(pushbutton_style)
        self.pushButton_action_help.setStyleSheet(pushbutton_style)

        

        """EXPLORING"""
        self.pushButton_exploring_identify.setStyleSheet(pushbutton_style)
        self.pushButton_exploring_zoom.setStyleSheet(pushbutton_style)

        self.pushButton_checkable_exploring_selecting.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_exploring_tracking.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_exploring_linking_widgets.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_exploring_saving_parameters.setStyleSheet(pushbutton_style)

        """SINGLE SELECTION"""
        #self.mGroupBox_exploring_single_selection.setStyleSheet(groupbox_style)
        self.mFeaturePickerWidget_exploring_single_selection.setStyleSheet(combobox_style)
        self.mFieldExpressionWidget_exploring_single_selection.setStyleSheet(combobox_style)

        """MULTIPLE SELECTION"""
        #self.mGroupBox_exploring_multiple_selection.setStyleSheet(groupbox_style)
        #self.mFeatureListComboBox_exploring_multiple_selection.setStyleSheet(combobox_style)
        self.mFieldExpressionWidget_exploring_multiple_selection.setStyleSheet(combobox_style)

        """CUSTOM SELECTION"""
        #self.mGroupBox_exploring_custom_selection.setStyleSheet(groupbox_style)
        self.mFieldExpressionWidget_exploring_custom_selection.setStyleSheet(combobox_style)


        """FILTERING"""
        self.pushButton_checkable_filtering_auto_current_layer.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_filtering_layers_to_filter.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_filtering_current_layer_add.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_filtering_geometric_predicates.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_filtering_buffer.setStyleSheet(pushbutton_style)


        self.mMapLayerComboBox_filtering_current_layer.setStyleSheet(combobox_style)
        self.comboBox_filtering_layers_to_filter.setStyleSheet(combobox_style)
        self.comboBox_filtering_current_layer_add.setStyleSheet(combobox_style)
        self.mComboBox_filtering_geometric_predicates.setStyleSheet(combobox_style)
        #lineedit
        #self.mQgsDoubleSpinBox_filtering_buffer.setStyleSheet()
        

        """EXPORTING"""
        self.pushButton_checkable_exporting_layers.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_exporting_projection.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_exporting_styles.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_exporting_datatype.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_exporting_output_folder.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_exporting_zip.setStyleSheet(pushbutton_style)


        self.comboBox_exporting_layers.setStyleSheet(combobox_style)
        self.mQgsProjectionSelectionWidget_exporting_projection.setStyleSheet(combobox_style)
        self.comboBox_exporting_styles.setStyleSheet(combobox_style)
        self.comboBox_exporting_datatype.setStyleSheet(combobox_style)

        #lineedit
        #self.lineEdit_exporting_output_folder.setStyleSheet()
        #self.lineEdit_exporting_zip.setStyleSheet()


        print("Colors changed!")

    def manage_interactions(self):

        """SET INTERACTIONS"""

        self.custom_identify_tool = CustomIdentifyTool(self.iface)
        """DOCK"""

        """INIT"""
        self.select_tabTools_index(self.toolBox_tabTools.currentIndex())

        """SLOTS"""
        self.toolBox_tabTools.currentChanged.connect(self.select_tabTools_index)



        """ACTION"""

        """SLOTS"""
        self.pushButton_action_filter.clicked.connect(partial(self.launchTaskEvent, 'filter'))
        self.pushButton_action_unfilter.clicked.connect(partial(self.launchTaskEvent, 'unfilter'))
        self.pushButton_action_export.clicked.connect(partial(self.launchTaskEvent, 'export'))


        """EXPLORING"""

        """SLOTS"""
        self.pushButton_checkable_exploring_selecting.clicked.connect(partial(self.layer_property_changed, 'is_selecting'))
        self.pushButton_checkable_exploring_tracking.clicked.connect(partial(self.layer_property_changed, 'is_tracking'))
        self.pushButton_checkable_exploring_linking_widgets.clicked.connect(partial(self.layer_property_changed, 'is_linked'))
        self.pushButton_checkable_exploring_saving_parameters.clicked.connect(partial(self.layer_property_changed, 'is_saving'))
        
        self.pushButton_exploring_zoom.clicked.connect(self.exploring_zoom_clicked)
        self.pushButton_exploring_identify.clicked.connect(self.exploring_identify_clicked)


        """SINGLE SELECTION"""

        """SLOTS"""
        self.mGroupBox_exploring_single_selection.clicked.connect(partial(self.exploring_groupbox_changed, 'single_selection'))

        

        self.mFeaturePickerWidget_exploring_single_selection.featureChanged.connect(self.exploring_features_changed)
        self.mFieldExpressionWidget_exploring_single_selection.fieldChanged.connect(self.exploring_source_params_changed)

        

        """MULTIPLE SELECTION"""
        self.mGroupBox_exploring_multiple_selection.clicked.connect(partial(self.exploring_groupbox_changed, 'multiple_selection'))

        self.customCheckableComboBox_exploring_multiple_selection.updatingCheckedItemList.connect(self.exploring_features_changed)
        self.customCheckableComboBox_exploring_multiple_selection.filteringCheckedItemList.connect(self.exploring_link_widgets)

        self.mFieldExpressionWidget_exploring_multiple_selection.fieldChanged.connect(self.exploring_source_params_changed)
        

        """CUSTOM SELECTION"""
        self.mGroupBox_exploring_custom_selection.clicked.connect(partial(self.exploring_groupbox_changed, 'custom_selection'))

        self.mFieldExpressionWidget_exploring_custom_selection.fieldChanged.connect(self.exploring_source_params_changed)


        """FILTERING"""

        """INIT"""
        self.mQgsDoubleSpinBox_filtering_buffer.setExpressionsEnabled(True)


        """SLOTS"""
        self.mMapLayerComboBox_filtering_current_layer.layerChanged.connect(self.current_layer_changed)
        self.comboBox_filtering_layers_to_filter.checkedItemsChanged.connect(partial(self.layer_property_changed, 'layers_to_filter'))
        self.comboBox_filtering_current_layer_add.currentTextChanged.connect(partial(self.layer_property_changed, 'combined_filter_logic'))
        self.mComboBox_filtering_geometric_predicates.checkedItemsChanged.connect(partial(self.layer_property_changed, 'geometric_predicates'))
        self.mQgsDoubleSpinBox_filtering_buffer.textChanged.connect(partial(self.layer_property_changed, 'buffer'))
        

        self.pushButton_checkable_filtering_layers_to_filter.clicked.connect(partial(self.layer_property_changed, 'has_layers_to_filter'))
        self.pushButton_checkable_filtering_current_layer_add.clicked.connect(partial(self.layer_property_changed, 'has_combined_filter_logic'))
        self.pushButton_checkable_filtering_geometric_predicates.clicked.connect(partial(self.layer_property_changed, 'has_geometric_predicates'))
        self.pushButton_checkable_filtering_buffer.clicked.connect(partial(self.layer_property_changed, 'has_buffer'))



        self.pushButton_checkable_filtering_auto_current_layer.clicked.connect(self.filtering_auto_current_layer_changed)



        """EXPORTING"""
        
        """INIT"""
        self.mQgsProjectionSelectionWidget_exporting_projection.setCrs(PROJECT.crs())

        """SLOTS"""
        self.pushButton_checkable_exporting_output_folder.clicked.connect(self.dialog_export_folder)
        self.lineEdit_exporting_output_folder.textEdited.connect(self.reset_export_folder)

        self.pushButton_checkable_exporting_zip.clicked.connect(self.dialog_export_zip)
        self.lineEdit_exporting_zip.textEdited.connect(self.reset_export_zip)


        """QGIS"""

        """SLOTS"""
        if self.auto_change_current_layer_flag is True:
            self.iface.layerTreeView().currentLayerChanged.connect(self.current_layer_changed)

        """INIT"""
        
        self.current_layer = self.iface.activeLayer()

        self.populate_predicats_chekableCombobox()

        if self.current_layer != None:
            self.exporting_populate_layers_chekableCombobox()
            self.filtering_populate_layers_chekableCombobox()
            self.current_layer_changed(self.current_layer)

    def icon_per_geometry_type(self, geometry_type):
        """Return the icon for a geometry type.

        If not found, it will return the default icon.

        :param geometry_type: The geometry as a string.
        :type geometry_type: basestring

        :return: The icon.
        :rtype: QIcon
        """

        if geometry_type == 'GeometryType.Polygon':
            return QgsLayerItem.iconPolygon()
        elif geometry_type == 'GeometryType.Point':
            return QgsLayerItem.iconPoint()
        elif geometry_type == 'GeometryType.Line':
            return QgsLayerItem.iconLine()
        elif geometry_type == 'GeometryType.UnknownGeometry':
            return QgsLayerItem.iconTable()
        else:
            return QgsLayerItem.iconDefault()
        
    
    def populate_predicats_chekableCombobox(self):

        self.predicats = ["Intersect","Contain","Disjoint","Equal","Touch","Overlap","Are within","Cross"]
        self.mComboBox_filtering_geometric_predicates.clear()
        self.mComboBox_filtering_geometric_predicates.addItems(self.predicats)

    def filtering_populate_layers_chekableCombobox(self):

        self.comboBox_filtering_layers_to_filter.clear()
        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]

        if layer_props["filtering"]["has_layers_to_filter"] == True:
            i = 0
            for key in self.PROJECT_LAYERS:
                layer_id = self.PROJECT_LAYERS[key]["infos"]["layer_id"]
                layer_name = self.PROJECT_LAYERS[key]["infos"]["layer_name"]
                layer_crs = self.PROJECT_LAYERS[key]["infos"]["layer_crs"]
                layer_icon = self.icon_per_geometry_type(self.PROJECT_LAYERS[key]["infos"]["layer_geometry_type"])

                if key != self.current_layer.id():
                    self.comboBox_filtering_layers_to_filter.addItem(layer_icon, layer_name + ' [%s]' % (layer_crs))
                    self.comboBox_filtering_layers_to_filter.setItemData(i, json.dumps(self.PROJECT_LAYERS[key]["infos"]), Qt.UserRole)
                    if len(layer_props["filtering"]["layers_to_filter"]) > 0:
                        if layer_id in [layer_info["layer_id"] for layer_info in layer_props["filtering"]["layers_to_filter"]]:
                            self.comboBox_filtering_layers_to_filter.setItemCheckState(i, Qt.Checked)
                        else:
                            self.comboBox_filtering_layers_to_filter.setItemCheckState(i, Qt.Unchecked)   
                    else:
                        self.comboBox_filtering_layers_to_filter.setItemCheckState(i, Qt.Unchecked)
                    i += 1    
        else:
            i = 0
            for key in self.PROJECT_LAYERS:
                layer_name = self.PROJECT_LAYERS[key]["infos"]["layer_name"]
                layer_crs = self.PROJECT_LAYERS[key]["infos"]["layer_crs"]
                layer_icon = self.icon_per_geometry_type(self.PROJECT_LAYERS[key]["infos"]["layer_geometry_type"])
                
                if key != self.current_layer.id():
                    self.comboBox_filtering_layers_to_filter.addItem(layer_icon, layer_name + ' [%s]' % (layer_crs), self.PROJECT_LAYERS[key]["infos"])                 
                    self.comboBox_filtering_layers_to_filter.setItemCheckState(i, Qt.Unchecked)
                    i += 1    


    def exporting_populate_layers_chekableCombobox(self):

        self.comboBox_exporting_layers.clear()

        for key in self.PROJECT_LAYERS:
            layer_name = self.PROJECT_LAYERS[key]["infos"]["layer_name"]
            layer_crs = self.PROJECT_LAYERS[key]["infos"]["layer_crs"]
            layer_icon = self.icon_per_geometry_type(self.PROJECT_LAYERS[key]["infos"]["layer_geometry_type"])
            self.comboBox_exporting_layers.addItem(layer_icon, layer_name + ' [%s]' % (layer_crs), self.PROJECT_LAYERS[key]["infos"])
        
        self.comboBox_exporting_layers.selectAllOptions()
            




    def layer_property_changed(self, property):

        if self.current_layer == None:
            return
        
        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]

        
        
        

        flag_value_changed = False

        if property == "is_selecting":
            if layer_props["exploring"]["is_selecting"] is False and self.pushButton_checkable_exploring_selecting.isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["is_selecting"] = True
                flag_value_changed = True
                self.exploring_groupbox_changed(self.current_exploring_groupbox)

            elif layer_props["exploring"]["is_selecting"] is True and self.pushButton_checkable_exploring_selecting.isChecked() is False:
                self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["is_selecting"] = False
                flag_value_changed = True

        elif property == "is_tracking":
            if layer_props["exploring"]["is_tracking"] is False and self.pushButton_checkable_exploring_tracking.isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["is_tracking"] = True
                flag_value_changed = True
                self.exploring_groupbox_changed(self.current_exploring_groupbox)

            elif layer_props["exploring"]["is_tracking"] is True and self.pushButton_checkable_exploring_tracking.isChecked() is False:
                self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["is_tracking"] = False
                flag_value_changed = True

        elif property == "is_linked":
            if layer_props["exploring"]["is_linked"] is False and self.pushButton_checkable_exploring_linking_widgets.isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["is_linked"] = True
                flag_value_changed = True

            elif layer_props["exploring"]["is_linked"] is True and self.pushButton_checkable_exploring_linking_widgets.isChecked() is False:
                self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["is_linked"] = False
                flag_value_changed = True
            self.exploring_link_widgets()

        elif property == "is_saving":
            if layer_props["exploring"]["is_saving"] is False and self.pushButton_checkable_exploring_saving_parameters.isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["is_saving"] = True
                flag_value_changed = True
            elif layer_props["exploring"]["is_saving"] is True and self.pushButton_checkable_exploring_saving_parameters.isChecked() is False:
                self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["is_saving"] = False
                flag_value_changed = True

        elif property == "has_layers_to_filter":
            if layer_props["filtering"]["has_layers_to_filter"] is False and self.pushButton_checkable_filtering_layers_to_filter.isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["has_layers_to_filter"] = True
                checked_list_data = []
                for i in range(self.comboBox_filtering_layers_to_filter.count()):
                   if self.comboBox_filtering_layers_to_filter.itemCheckState(i) == Qt.Checked:
                        checked_list_data.append(self.comboBox_filtering_layers_to_filter.itemData(i, Qt.UserRole))
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["layers_to_filter"] = checked_list_data
                flag_value_changed = True
            elif layer_props["filtering"]["has_layers_to_filter"] is True and self.pushButton_checkable_filtering_layers_to_filter.isChecked() is False:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["has_layers_to_filter"] = False
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["layers_to_filter"] = []
                self.comboBox_filtering_layers_to_filter.checkedItemsChanged.disconnect()
                self.comboBox_filtering_layers_to_filter.deselectAllOptions()
                self.comboBox_filtering_layers_to_filter.checkedItemsChanged.connect(partial(self.layer_property_changed, 'layers_to_filter'))
                flag_value_changed = True
            
        elif property == "layers_to_filter":
            if layer_props["filtering"]["has_layers_to_filter"] is True and self.pushButton_checkable_filtering_layers_to_filter.isChecked() is True:
                checked_list_data = []
                for i in range(self.comboBox_filtering_layers_to_filter.count()):
                   if self.comboBox_filtering_layers_to_filter.itemCheckState(i) == Qt.Checked:
                        checked_list_data.append(self.comboBox_filtering_layers_to_filter.itemData(i, Qt.UserRole))
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["layers_to_filter"] = checked_list_data
                flag_value_changed = True
            else:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["layers_to_filter"] = []
                self.comboBox_filtering_layers_to_filter.checkedItemsChanged.disconnect()
                self.comboBox_filtering_layers_to_filter.deselectAllOptions()
                self.comboBox_filtering_layers_to_filter.checkedItemsChanged.connect(partial(self.layer_property_changed, 'layers_to_filter'))
                flag_value_changed = True

        elif property == "has_combined_filter_logic":
            if layer_props["filtering"]["has_combined_filter_logic"] is False and self.pushButton_checkable_filtering_current_layer_add.isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["has_combined_filter_logic"] = True
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["combined_filter_logic"] = self.comboBox_filtering_current_layer_add.currentText()
                flag_value_changed = True
            elif layer_props["filtering"]["has_combined_filter_logic"] is True and self.pushButton_checkable_filtering_current_layer_add.isChecked() is False:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["has_combined_filter_logic"] = False
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["combined_filter_logic"] = ''
                self.comboBox_filtering_current_layer_add.currentTextChanged.disconnect()
                self.comboBox_filtering_current_layer_add.setCurrentIndex(0)
                self.comboBox_filtering_current_layer_add.currentTextChanged.connect(partial(self.layer_property_changed, 'combined_filter_logic'))
                flag_value_changed = True
            
        elif property == "combined_filter_logic":
            if layer_props["filtering"]["has_combined_filter_logic"] is True and self.pushButton_checkable_filtering_layers_to_filter.isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["combined_filter_logic"] = self.comboBox_filtering_current_layer_add.currentText()
                flag_value_changed = True
            else:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["combined_filter_logic"] = ''
                self.comboBox_filtering_current_layer_add.currentTextChanged.disconnect()
                self.comboBox_filtering_current_layer_add.setCurrentIndex(0)
                self.comboBox_filtering_current_layer_add.currentTextChanged.connect(partial(self.layer_property_changed, 'combined_filter_logic'))
                flag_value_changed = True

        elif property == "has_geometric_predicates":
            self.filtering_geometric_predicates_state_changed()
            if layer_props["filtering"]["has_geometric_predicates"] is False and self.pushButton_checkable_filtering_geometric_predicates.isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["has_geometric_predicates"] = True
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["geometric_predicates"] = self.mComboBox_filtering_geometric_predicates.checkedItems()
                flag_value_changed = True
            elif layer_props["filtering"]["has_geometric_predicates"] is True and self.pushButton_checkable_filtering_geometric_predicates.isChecked() is False:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["has_geometric_predicates"] = False
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["geometric_predicates"] = []
                self.mComboBox_filtering_geometric_predicates.checkedItemsChanged.disconnect()
                self.mComboBox_filtering_geometric_predicates.deselectAllOptions()
                self.mComboBox_filtering_geometric_predicates.checkedItemsChanged.connect(partial(self.layer_property_changed, 'geometric_predicates'))
                flag_value_changed = True

        elif property == "geometric_predicates":
            if layer_props["filtering"]["has_geometric_predicates"] is True and self.pushButton_checkable_filtering_geometric_predicates.isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["geometric_predicates"] = self.mComboBox_filtering_geometric_predicates.checkedItems()
                flag_value_changed = True
            else:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["geometric_predicates"] = []
                self.mComboBox_filtering_geometric_predicates.checkedItemsChanged.disconnect()
                self.mComboBox_filtering_geometric_predicates.deselectAllOptions()
                self.mComboBox_filtering_geometric_predicates.checkedItemsChanged.connect(partial(self.layer_property_changed, 'geometric_predicates'))
                flag_value_changed = True

        elif property == "has_buffer":
            self.filtering_buffer_state_changed()
            if layer_props["filtering"]["has_buffer"] is False and self.pushButton_checkable_filtering_buffer.isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["has_buffer"] = True
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer"] = self.mQgsDoubleSpinBox_filtering_buffer.value()
                flag_value_changed = True
            elif layer_props["filtering"]["has_buffer"] is True and self.pushButton_checkable_filtering_buffer.isChecked() is False:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["has_buffer"] = False
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer"] = 0.0
                self.mQgsDoubleSpinBox_filtering_buffer.textChanged.disconnect()
                self.mQgsDoubleSpinBox_filtering_buffer.setValue(0.0)
                self.mQgsDoubleSpinBox_filtering_buffer.textChanged.connect(partial(self.layer_property_changed, 'buffer'))
                flag_value_changed = True

        elif property == "buffer":
            if layer_props["filtering"]["has_buffer"] is True and self.pushButton_checkable_filtering_buffer.isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer"] = self.mQgsDoubleSpinBox_filtering_buffer.value()
                flag_value_changed = True
            else:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer"] = 0.0
                self.mQgsDoubleSpinBox_filtering_buffer.textChanged.disconnect()
                self.mQgsDoubleSpinBox_filtering_buffer.setValue(0.0)
                self.mQgsDoubleSpinBox_filtering_buffer.textChanged.connect(partial(self.layer_property_changed, 'buffer'))
                flag_value_changed = True


        if flag_value_changed is True:
            self.setProjectLayersEvent(self.PROJECT_LAYERS)



    def dialog_export_folder(self):

        if self.pushButton_checkable_exporting_output_folder.isChecked() == True:
            
            folderpath = str(QtWidgets.QFileDialog.getExistingDirectory(self, 'Select a folder where to export your layers', self.current_project_path))

            if folderpath:
                self.lineEdit_exporting_output_folder.setText(folderpath)
                print(folderpath)
            else:
                self.pushButton_checkable_exporting_output_folder.setChecked(False)
        else:
            self.lineEdit_exporting_output_folder.clear()

    def reset_export_folder(self):

        if str(self.lineEdit_exporting_output_folder.text()) == '':
            self.lineEdit_exporting_output_folder.clear()
            self.pushButton_checkable_exporting_output_folder.setChecked(False)


    def dialog_export_zip(self):

        if self.pushButton_checkable_exporting_zip.isChecked() == True:

            
            filepath = str(QtWidgets.QFileDialog.getSaveFileName(self, 'Save your exported data to a zip file', os.path.join(self.current_project_path, self.output_name) ,'*.zip')[0])

            if filepath:
                self.lineEdit_exporting_zip.setText(filepath)
                print(filepath)
            else:
                self.pushButton_checkable_exporting_zip.setChecked(False)
        else:
            self.lineEdit_exporting_zip.clear()


    def reset_export_zip(self):

        if str(self.lineEdit_exporting_zip.text()) == '':
            self.lineEdit_exporting_zip.clear()
            self.pushButton_checkable_exporting_zip.setChecked(False)


    def select_tabTools_index(self, i):
        """Keep the current tab index updated"""
        self.tabTools_current_index = i
        if self.tabTools_current_index == 1:
            self.pushButton_action_export.setEnabled(True)
        else:
            self.pushButton_action_export.setEnabled(False)

    def filtering_auto_current_layer_changed(self):
        if self.pushButton_checkable_filtering_auto_current_layer.isChecked() is True:
            self.auto_change_current_layer_flag = True
            self.iface.layerTreeView().currentLayerChanged.connect(self.current_layer_changed)
        else:
            self.auto_change_current_layer_flag = False
            self.iface.layerTreeView().currentLayerChanged.disconnect()


    def filtering_geometric_predicates_state_changed(self):
        """Manage the geo filter state checkbox"""
        if self.pushButton_checkable_filtering_geometric_predicates.isChecked() is True:
            self.pushButton_checkable_filtering_buffer.setEnabled(True)

            self.mComboBox_filtering_geometric_predicates.setEnabled(True)
            self.mComboBox_filtering_geometric_predicates.setFrame(True)
        else:
            self.pushButton_checkable_filtering_buffer.setEnabled(False)
            self.pushButton_checkable_filtering_buffer.setChecked(False)

            self.mQgsDoubleSpinBox_filtering_buffer.setDisabled(True)

            self.mComboBox_filtering_geometric_predicates.setFrame(False)
            self.mComboBox_filtering_geometric_predicates.setDisabled(True)
            
      
    def filtering_buffer_state_changed(self):
        """Manage the buffer state checkbox"""
        if self.pushButton_checkable_filtering_buffer.isChecked() is True:
            self.mQgsDoubleSpinBox_filtering_buffer.setEnabled(True)
        else:
            self.mQgsDoubleSpinBox_filtering_buffer.setEnabled(False)

    def exploring_identify_clicked(self):
        
        self.custom_identify_tool.setLayer(self.current_layer)

        if self.current_exploring_groupbox == "single_selection":
            input = self.mFeaturePickerWidget_exploring_single_selection.feature()
            features, expr = self.getExploringFeatures(input)

        elif self.current_exploring_groupbox == "multiple_selection":
            input = self.customCheckableComboBox_exploring_multiple_selection.checkedItems()
            features, expr = self.getExploringFeatures(input, True)

        elif self.current_exploring_groupbox == "custom_selection":
            features = self.exploring_custom_selection()
        
        if len(features) == 0:
            return
        else:
            self.custom_identify_tool.setFeatures(features)
        #iface.mapCanvas().setMapTool(self.custom_identify_tool)


    def get_current_features(self):

        if self.current_exploring_groupbox == "single_selection":
            input = self.mFeaturePickerWidget_exploring_single_selection.feature()
            features, expression = self.getExploringFeatures(input)

        elif self.current_exploring_groupbox == "multiple_selection":
            input = self.customCheckableComboBox_exploring_multiple_selection.checkedItems()
            features, expression = self.getExploringFeatures(input, True)

        elif self.current_exploring_groupbox == "custom_selection":
            features, expression = self.exploring_custom_selection()
            
        return features, expression
    

    def exploring_zoom_clicked(self):

        features, expr = self.get_current_features()
        
        if len(features) == 0:
            return
        else:
            self.zooming_to_features(features)


    def exploring_features_changed(self, input, identify_by_primary_key_name=False, custom_expression=None):


        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
        features, expression = self.getExploringFeatures(input, identify_by_primary_key_name, custom_expression)

        
        self.exploring_link_widgets(expression)
        
        self.current_layer.removeSelection()

        if len(features) == 0:
            return features
    
    
        if layer_props["exploring"]["is_selecting"] == True:
            self.current_layer.removeSelection()
            self.current_layer.select([feature.id() for feature in features])

        if layer_props["exploring"]["is_tracking"] == True:
            self.zooming_to_features(features)  


        return features

    def exploring_source_params_changed(self, expression):


        layer_props = self.PROJECT_LAYERS[self.current_layer.id()] 
        flag_value_changed = False

        if self.current_exploring_groupbox == "single_selection":
            
            if expression != self.mFeaturePickerWidget_exploring_single_selection.displayExpression():
                self.mFeaturePickerWidget_exploring_single_selection.setDisplayExpression(expression)


                self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["single_selection_expression"] = expression
                flag_value_changed = True

        elif self.current_exploring_groupbox == "multiple_selection":

            if expression != self.customCheckableComboBox_exploring_multiple_selection.displayExpression():
                self.customCheckableComboBox_exploring_multiple_selection.setDisplayExpression(expression)


                self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["multiple_selection_expression"] = expression
                flag_value_changed = True


        elif self.current_exploring_groupbox == "custom_selection":

            self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["custom_selection_expression"] = expression
            if QgsExpression(expression).isField() is False:
                self.exploring_custom_selection()

            flag_value_changed = True
        
        if flag_value_changed == True:
            self.setProjectLayersEvent(self.PROJECT_LAYERS)
 



    def exploring_custom_selection(self):
        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
        expression = layer_props["exploring"]["custom_selection_expression"]
        features = []
        if QgsExpression(expression).isField() is False:
            features = self.exploring_features_changed([], False, expression)
        return features, expression



    def exploring_groupbox_init(self):

        if self.mGroupBox_exploring_single_selection.isChecked() is True or self.mGroupBox_exploring_single_selection.isCollapsed() is False:
            self.current_exploring_groupbox = "single_selection"

        elif self.mGroupBox_exploring_multiple_selection.isChecked() is True or self.mGroupBox_exploring_multiple_selection.isCollapsed() is False:
            self.current_exploring_groupbox = "multiple_selection"  

        elif self.mGroupBox_exploring_custom_selection.isChecked() is True or self.mGroupBox_exploring_custom_selection.isCollapsed() is False:
            self.current_exploring_groupbox = "custom_selection"

        self.exploring_groupbox_changed(self.current_exploring_groupbox)




    def exploring_groupbox_changed(self, groupbox):



        if groupbox == "single_selection":
  
            if self.mGroupBox_exploring_single_selection.isChecked() is True or self.mGroupBox_exploring_single_selection.isCollapsed() is False:


                try:
                    self.mFeaturePickerWidget_exploring_single_selection.featureChanged.connect(self.exploring_features_changed)
                except:
                    pass

                self.mGroupBox_exploring_single_selection.setChecked(True)
                self.mGroupBox_exploring_single_selection.setCollapsed(False)

                self.mFeaturePickerWidget_exploring_single_selection.setEnabled(True)
                self.mFieldExpressionWidget_exploring_single_selection.setEnabled(True)

                self.mGroupBox_exploring_multiple_selection.setChecked(False)
                self.mGroupBox_exploring_multiple_selection.setCollapsed(True)

                self.mGroupBox_exploring_custom_selection.setChecked(False)
                self.mGroupBox_exploring_custom_selection.setCollapsed(True)

                self.current_exploring_groupbox = "single_selection"

                if self.current_layer != None:
                    self.exploring_features_changed(self.mFeaturePickerWidget_exploring_single_selection.feature())
            # else:
            #     self.mGroupBox_exploring_single_selection.setChecked(False)
            #     self.mGroupBox_exploring_single_selection.setCollapsed(True)

            #     self.current_exploring_groupbox = None


        elif groupbox == "multiple_selection":

            if self.mGroupBox_exploring_multiple_selection.isChecked() is True or self.mGroupBox_exploring_multiple_selection.isCollapsed() is False:
                
                try:
                    self.mFeaturePickerWidget_exploring_single_selection.featureChanged.disconnect()
                except:
                    pass


                self.mGroupBox_exploring_multiple_selection.setChecked(True)
                self.mGroupBox_exploring_multiple_selection.setCollapsed(False)

                self.customCheckableComboBox_exploring_multiple_selection.setEnabled(True)
                self.mFieldExpressionWidget_exploring_multiple_selection.setEnabled(True)

                self.mGroupBox_exploring_single_selection.setChecked(False)
                self.mGroupBox_exploring_single_selection.setCollapsed(True)

                self.mGroupBox_exploring_custom_selection.setChecked(False)
                self.mGroupBox_exploring_custom_selection.setCollapsed(True)

                self.current_exploring_groupbox = "multiple_selection"

                if self.current_layer != None:
                    self.exploring_features_changed(self.customCheckableComboBox_exploring_multiple_selection.currentSelectedFeatures(), True)
            # else:
            #     self.mGroupBox_exploring_multiple_selection.setChecked(False)
            #     self.mGroupBox_exploring_multiple_selection.setCollapsed(True)

        elif groupbox == "custom_selection":

            if self.mGroupBox_exploring_custom_selection.isChecked() is True or self.mGroupBox_exploring_custom_selection.isCollapsed() is False:

                try:
                    self.mFeaturePickerWidget_exploring_single_selection.featureChanged.disconnect()
                except:
                    pass

                self.mGroupBox_exploring_custom_selection.setChecked(True)
                self.mGroupBox_exploring_custom_selection.setCollapsed(False)

                self.mFieldExpressionWidget_exploring_custom_selection.setEnabled(True)

                self.mGroupBox_exploring_multiple_selection.setChecked(False)
                self.mGroupBox_exploring_multiple_selection.setCollapsed(True)

                self.mGroupBox_exploring_single_selection.setChecked(False)
                self.mGroupBox_exploring_single_selection.setCollapsed(True)

                self.current_exploring_groupbox = "custom_selection"

                if self.current_layer != None:
                    self.exploring_custom_selection()

            # else:
            #     self.mGroupBox_exploring_custom_selection.setChecked(False)
            #     self.mGroupBox_exploring_custom_selection.setCollapsed(True)



    def current_layer_changed(self, layer):

        self.current_layer = layer  

        if self.current_layer == None:
            return
        
        

        self.mFieldExpressionWidget_exploring_single_selection.fieldChanged.disconnect()
        self.mFieldExpressionWidget_exploring_multiple_selection.fieldChanged.disconnect()
        self.mFieldExpressionWidget_exploring_custom_selection.fieldChanged.disconnect()
        self.mMapLayerComboBox_filtering_current_layer.layerChanged.disconnect()
        

        if self.auto_change_current_layer_flag == True:
            self.iface.layerTreeView().currentLayerChanged.disconnect()

        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]

        currentLayer = self.mMapLayerComboBox_filtering_current_layer.currentLayer()
        if currentLayer != None and currentLayer.id() != self.current_layer.id():
            self.mMapLayerComboBox_filtering_current_layer.setLayer(self.current_layer)

        """EXPLORING"""
        
        """SINGLE SELECTION"""

        self.mFieldExpressionWidget_exploring_single_selection.setLayer(self.current_layer)
        self.mFieldExpressionWidget_exploring_single_selection.setExpression(layer_props["exploring"]["single_selection_expression"])

        self.mFeaturePickerWidget_exploring_single_selection.setLayer(self.current_layer)
        self.mFeaturePickerWidget_exploring_single_selection.setDisplayExpression(layer_props["exploring"]["single_selection_expression"])
        self.mFeaturePickerWidget_exploring_single_selection.setFetchGeometry(True)
        self.mFeaturePickerWidget_exploring_single_selection.setShowBrowserButtons(True)



        """MULTIPLE SELECTION"""
        
        self.mFieldExpressionWidget_exploring_multiple_selection.setLayer(self.current_layer)
        self.mFieldExpressionWidget_exploring_multiple_selection.setExpression(layer_props["exploring"]["multiple_selection_expression"])

        self.customCheckableComboBox_exploring_multiple_selection.setLayer(self.current_layer, layer_props)

        """CUSTOM SELECTION"""

        self.mFieldExpressionWidget_exploring_custom_selection.setLayer(self.current_layer)
        self.mFieldExpressionWidget_exploring_custom_selection.setExpression(layer_props["exploring"]["custom_selection_expression"])

        


        if layer_props["exploring"]["is_selecting"] == True:
            self.pushButton_checkable_exploring_selecting.setChecked(True)
        elif layer_props["exploring"]["is_selecting"] == False:
            self.pushButton_checkable_exploring_selecting.setChecked(False)

        if layer_props["exploring"]["is_tracking"] == True:
            self.pushButton_checkable_exploring_tracking.setChecked(True)
        elif layer_props["exploring"]["is_tracking"] == False:
            self.pushButton_checkable_exploring_tracking.setChecked(False)

        if layer_props["exploring"]["is_linked"] == True:
            self.pushButton_checkable_exploring_linking_widgets.setChecked(True)
        elif layer_props["exploring"]["is_linked"] == False:
            self.pushButton_checkable_exploring_linking_widgets.setChecked(False)

        if layer_props["exploring"]["is_saving"] == True:
            self.pushButton_checkable_exploring_saving_parameters.setChecked(True)
        elif layer_props["exploring"]["is_saving"] == False:
            self.pushButton_checkable_exploring_saving_parameters.setChecked(False)



        self.comboBox_filtering_layers_to_filter.checkedItemsChanged.disconnect()

        if layer_props["filtering"]["has_layers_to_filter"] == True:
            self.pushButton_checkable_filtering_layers_to_filter.setChecked(True)
            self.filtering_populate_layers_chekableCombobox()
        elif layer_props["filtering"]["has_layers_to_filter"] == False:
            self.pushButton_checkable_filtering_layers_to_filter.setChecked(False)
            self.filtering_populate_layers_chekableCombobox()

        self.comboBox_filtering_layers_to_filter.checkedItemsChanged.connect(partial(self.layer_property_changed, 'layers_to_filter'))



        self.comboBox_filtering_current_layer_add.currentTextChanged.disconnect()

        if layer_props["filtering"]["has_combined_filter_logic"] == True:
            self.pushButton_checkable_filtering_current_layer_add.setChecked(True)
            self.comboBox_filtering_current_layer_add.setCurrentText(layer_props["filtering"]["combined_filter_logic"])
        elif layer_props["filtering"]["has_combined_filter_logic"] == False:
            self.pushButton_checkable_filtering_current_layer_add.setChecked(False)
            self.comboBox_filtering_current_layer_add.setCurrentIndex(0)

        self.comboBox_filtering_current_layer_add.currentTextChanged.connect(partial(self.layer_property_changed, 'combined_filter_logic'))



        self.mComboBox_filtering_geometric_predicates.checkedItemsChanged.disconnect()

        if layer_props["filtering"]["has_geometric_predicates"] == True:
            self.pushButton_checkable_filtering_geometric_predicates.setChecked(True)
            self.mComboBox_filtering_geometric_predicates.setCheckedItems(layer_props["filtering"]["geometric_predicates"])
        elif layer_props["filtering"]["has_geometric_predicates"] == False:
            self.pushButton_checkable_filtering_geometric_predicates.setChecked(False)
            self.mComboBox_filtering_geometric_predicates.deselectAllOptions()

        self.mComboBox_filtering_geometric_predicates.checkedItemsChanged.connect(partial(self.layer_property_changed, 'geometric_predicates'))



        self.mQgsDoubleSpinBox_filtering_buffer.textChanged.disconnect()

        if layer_props["filtering"]["has_buffer"] == True:
            self.pushButton_checkable_filtering_buffer.setChecked(True)
            self.mQgsDoubleSpinBox_filtering_buffer.setValue(self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer"])
        elif layer_props["filtering"]["has_buffer"] == False:
            self.pushButton_checkable_filtering_buffer.setChecked(False)
            self.mQgsDoubleSpinBox_filtering_buffer.setValue(0.0)

        self.filtering_geometric_predicates_state_changed()
        self.filtering_buffer_state_changed()

        self.mQgsDoubleSpinBox_filtering_buffer.textChanged.connect(partial(self.layer_property_changed, 'buffer'))

        
        

        if self.auto_change_current_layer_flag == True:
            if self.iface.activeLayer().id() != self.current_layer.id():
                self.iface.layerTreeView().setCurrentLayer(self.current_layer)
            self.iface.layerTreeView().currentLayerChanged.connect(self.current_layer_changed)

        self.exploring_link_widgets()

        self.mFieldExpressionWidget_exploring_single_selection.fieldChanged.connect(self.exploring_source_params_changed)
        self.mFieldExpressionWidget_exploring_multiple_selection.fieldChanged.connect(self.exploring_source_params_changed)
        self.mFieldExpressionWidget_exploring_custom_selection.fieldChanged.connect(self.exploring_source_params_changed)
        self.mMapLayerComboBox_filtering_current_layer.layerChanged.connect(self.current_layer_changed)

        
            

    def exploring_link_widgets(self, expression=None):

        if self.current_layer == None:
            return
        
        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
        custom_filter = None

        if layer_props["exploring"]["is_linked"] == True:
            if QgsExpression(layer_props["exploring"]["custom_selection_expression"]).isValid() is True:
                if QgsExpression(layer_props["exploring"]["custom_selection_expression"]).isField() is False:
                    custom_filter = layer_props["exploring"]["custom_selection_expression"]
                    self.customCheckableComboBox_exploring_multiple_selection.setFilterExpression(custom_filter)
            if expression != None:
                self.mFeaturePickerWidget_exploring_single_selection.setFilterExpression(expression)
            elif self.customCheckableComboBox_exploring_multiple_selection.currentSelectedFeatures() != False:
                features, expression = self.getExploringFeatures(self.customCheckableComboBox_exploring_multiple_selection.currentSelectedFeatures(), True)
                if len(features) > 0 and expression != None:
                    self.mFeaturePickerWidget_exploring_single_selection.setFilterExpression(expression)
            elif self.customCheckableComboBox_exploring_multiple_selection.currentVisibleFeatures() != False:
                features, expression = self.getExploringFeatures(self.customCheckableComboBox_exploring_multiple_selection.currentVisibleFeatures(), True)
                if len(features) > 0 and expression != None:
                    self.mFeaturePickerWidget_exploring_single_selection.setFilterExpression(expression)
            elif custom_filter != None:
                self.mFeaturePickerWidget_exploring_single_selection.setFilterExpression(custom_filter)
           
        else:
            self.mFeaturePickerWidget_exploring_single_selection.setFilterExpression('')
            self.customCheckableComboBox_exploring_multiple_selection.setFilterExpression('')



    def zooming_to_features(self, features):
        raw_geometries = [feature.geometry() for feature in features if feature.hasGeometry()]
        geometries = []

        for geometry in raw_geometries:
            if geometry.isEmpty() is False:
                if geometry.isMultipart():
                    geometry.convertToSingleType()
                geometries.append(geometry)

        collected_geometry = QgsGeometry().collectGeometry(geometries)

        box = collected_geometry.boundingBox()
        self.iface.mapCanvas().setExtent(box)
        self.iface.mapCanvas().refresh()


    def getExploringFeatures(self, input, identify_by_primary_key_name=False, custom_expression=None):

        if self.current_layer == None:
            return
        
        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
        features = []
        expression = None

        if isinstance(input, QgsFeature):
            features = [input]
        elif isinstance(input, list):
            if len(input) == 0 and custom_expression == None:
                return features, expression
            
            if identify_by_primary_key_name is True:
                if layer_props["infos"]["primary_key_is_numeric"] is True:
                    input_ids = [str(feat[1]) for feat in input]  
                    expression = layer_props["infos"]["primary_key_name"] + " in (" + ", ".join(input_ids) + ")"
                else:
                    input_ids = [str(feat[1]) for feat in input]
                    expression = layer_props["infos"]["primary_key_name"] + " in (\'" + "\', \'".join(input_ids) + "\')"
            
            if custom_expression != None:
                 expression = custom_expression

            if QgsExpression(expression).isValid():

                features_iterator = self.current_layer.getFeatures(QgsFeatureRequest(QgsExpression(expression)))
                done_looping = False
                
                while not done_looping:
                    try:
                        feature = next(features_iterator)
                        features.append(feature)
                    except StopIteration:
                        done_looping = True
            else:
                expression = None

        return features, expression



    def get_project_layers_from_app(self, project_layers):
        if isinstance(project_layers, dict) and len(project_layers) > 0:
            self.PROJECT_LAYERS = project_layers
        else:
            return
        
        layers = [layer for layer in PROJECT.mapLayersByName(self.PROJECT_LAYERS[self.current_layer.id()]["infos"]["layer_name"]) if layer.id() == self.current_layer.id()]
        if len(layers) == 0:
            self.current_layer = self.iface.activeLayer()
            
            if self.current_layer == None:
                return
            
            self.exporting_populate_layers_chekableCombobox()
            self.current_layer_changed(self.current_layer)

    def setProjectLayersEvent(self, event):
        self.settingProjectLayers.emit(event)
    
    def getProjectLayersEvent(self, event):
        self.gettingProjectLayers.emit()


    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def launchTaskEvent(self, event):
        self.launchingTask.emit(event)

class CustomIdentifyTool(QgsIdentifyMenu):
    
    def __init__(self, iface):
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.layer = self.iface.activeLayer()
        self.features = []
        self.features_result = []
        QgsIdentifyMenu.__init__(self, self.canvas)
        self.map_tool_identify = QgsMapToolIdentify(self.canvas)
        self.iface.currentLayerChanged.connect(self.active_changed)
        
    def active_changed(self, layer):
        if isinstance(layer, QgsVectorLayer) and layer.isSpatial():
            self.layer = layer
            self.features = []
            self.features_result = []

    def setLayer(self, layer):
        if isinstance(layer, QgsVectorLayer) and layer.isSpatial():
            self.layer = layer
            self.features = []
            self.features_result = []

    def setFeatures(self, features):
        self.features = features
        self.features_result = []

        if len(self.features) > 0:
            for feature in self.features:
                feature_point_XY = self.features[0].geometry().centroid().asPoint()    
                self.features_result.append(self.map_tool_identify.IdentifyResult(self.layer, feature, self.map_tool_identify.derivedAttributesForPoint(QgsPoint(feature_point_XY))))

            self.exec(self.features_result, feature_point_XY.toQPointF().toPoint())

            
    def canvasPressEvent(self, event):
        results = self.identify(event.x(), event.y(), [self.layer], QgsMapToolIdentify.TopDownAll)
        for i in range(len(results)):
            print(results[i].mDerivedAttributes)
        
    def deactivate(self):
        self.iface.currentLayerChanged.disconnect(self.active_changed)



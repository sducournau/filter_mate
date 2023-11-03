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
from .config.config import *
import os
import json
from functools import partial
from qgis.PyQt import QtGui, QtWidgets, uic
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *
from qgis.utils import iface
from qgis.PyQt.QtWidgets import QApplication, QVBoxLayout

from .modules.qgsCustomCheckableListWidget import QgsCustomCheckableListWidget
from .modules.qt_json_view.model import JsonModel, JsonSortFilterProxyModel
from .modules.qt_json_view.view import JsonView
from .modules.customExceptions import *

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'filter_mate_dockwidget_base.ui'))


class FilterMateDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()
    launchingTask = pyqtSignal(str)

    gettingProjectLayers = pyqtSignal()
    settingProjectLayers = pyqtSignal(dict)

    reinitializingLayerOnError = pyqtSignal(str)

    def __init__(self, project_layers, plugin_dir, parent=None):
        """Constructor."""
        super(FilterMateDockWidget, self).__init__(parent)
        
        self.exception = None

        self.plugin_dir = plugin_dir
        self.iface = iface
        self.PROJECT_LAYERS = project_layers
        
        self.tabTools_current_index = 0

        self.auto_change_current_layer_flag = False

        self.widgets = None
        self.current_exploring_groupbox = None
        self.current_layer = None

        self.setupUi(self)
        self.setupUiCustom()
        self.dockwidget_widgets_configuration()
        self.manage_ui_style()
        self.manage_interactions()
        self.manage_output_name()

    def getSignal(self, oObject : QObject, strSignalName : str):
        oMetaObj = oObject.metaObject()
        for i in range (oMetaObj.methodCount()):
            oMetaMethod = oMetaObj.method(i)
            if not oMetaMethod.isValid():
                continue
            if oMetaMethod.methodType () == QMetaMethod.Signal and \
                oMetaMethod.name() == strSignalName:
                return oMetaMethod

        return None

    def manageSignal(self, widget_path, custom_action=None, custom_signal_name=None):
        current_signal_name = None
        current_triggered_function = None
        state = None
        widget_object = None


        if isinstance(widget_path, list) and len(widget_path) == 2:
            widget_object = self.widgets[widget_path[0]][widget_path[1]]
        else:
            raise SignalStateChangeError(state, widget_path, 'Incorrect input parameters')

        if custom_signal_name != None:
           for signal in widget_object["SIGNALS"]:
               if signal[0] == custom_signal_name:
                    current_signal_name = custom_signal_name
                    current_triggered_function = signal[1]

        else:
            current_signal_name = widget_object["SIGNALS"][0][0]
            current_triggered_function = widget_object["SIGNALS"][0][1]
            

        if hasattr(widget_object["WIDGET"], current_signal_name):
            state = widget_object["WIDGET"].isSignalConnected(self.getSignal(widget_object["WIDGET"], current_signal_name))
            if custom_action != None:
                if custom_action == 'disconnect' and state == True:
                    getattr(widget_object["WIDGET"], current_signal_name).disconnect()
                elif custom_action == 'connect' and state == False:
                    getattr(widget_object["WIDGET"], current_signal_name).connect(current_triggered_function)
            else:
                if state == True:
                    getattr(widget_object["WIDGET"], current_signal_name).disconnect()
                else:
                    getattr(widget_object["WIDGET"], current_signal_name).connect(current_triggered_function)

            state = widget_object["WIDGET"].isSignalConnected(self.getSignal(widget_object["WIDGET"], current_signal_name))   
            return state
        
        if state == None:
            raise SignalStateChangeError(state, widget_path)



    def setupUiCustom(self):
        self.customCheckableComboBox_exploring_multiple_selection = QgsCustomCheckableListWidget(self)
        self.layout = self.verticalLayout_exploring_multiple_selection
        self.layout.insertWidget(0, self.customCheckableComboBox_exploring_multiple_selection)

        #self.custom_identify_tool = CustomIdentifyTool(self.iface)
        self.iface.mapCanvas().setSelectionColor(QColor(237, 97, 62, 75))
        self.manage_configuration_model()



    def dockwidget_widgets_configuration(self):

        self.widgets = {"DOCK":{}, "ACTION":{}, "EXPLORING":{}, "SINGLE_SELECTION":{}, "MULTIPLE_SELECTION":{}, "CUSTOM_SELECTION":{}, "FILTERING":{}, "EXPORTING":{}, "QGIS":{}}
            
        self.widgets["DOCK"] = {
                                "GroupBox_SINGLE_SELECTION":{"WIDGET":self.mGroupBox_exploring_single_selection, "SIGNALS":[("clicked", partial(self.exploring_groupbox_changed, 'single_selection'))]},
                                "GroupBox_MULTIPLE_SELECTION":{"WIDGET":self.mGroupBox_exploring_multiple_selection, "SIGNALS":[("clicked", partial(self.exploring_groupbox_changed, 'multiple_selection'))]},
                                "GroupBox_CUSTOM_SELECTION":{"WIDGET":self.mGroupBox_exploring_custom_selection, "SIGNALS":[("clicked", partial(self.exploring_groupbox_changed, 'custom_selection'))]},
                                "ToolBox_tabTools":{"WIDGET":self.toolBox_tabTools, "SIGNALS":[("currentChanged", self.select_tabTools_index)]}
                                }   

        self.widgets["ACTION"] = {
                                "PushButton_FILTER":{"WIDGET":self.pushButton_action_filter, "SIGNALS":[("clicked", partial(self.launchTaskEvent, 'filter'))], "ICON":None},
                                "PushButton_UNFILTER":{"WIDGET":self.pushButton_action_unfilter, "SIGNALS":[("clicked", partial(self.launchTaskEvent, 'unfilter'))], "ICON":None},
                                "PushButton_EXPORT":{"WIDGET":self.pushButton_action_export, "SIGNALS":[("clicked", partial(self.launchTaskEvent, 'export'))], "ICON":None}
                                }        
        
        self.widgets["EXPLORING"] = {
                                    "PushButton_IDENTIFY":{"WIDGET":self.pushButton_exploring_identify, "SIGNALS":[("clicked", self.exploring_identify_clicked)], "ICON":None},
                                    "PushButton_ZOOM":{"WIDGET":self.pushButton_exploring_zoom, "SIGNALS":[("clicked", self.exploring_zoom_clicked)], "ICON":None},
                                    "PushButton_SELECTING":{"WIDGET":self.pushButton_checkable_exploring_selecting, "SIGNALS":[("clicked", partial(self.layer_property_changed, 'is_selecting'))], "ICON":None},
                                    "PushButton_TRACKING":{"WIDGET":self.pushButton_checkable_exploring_tracking, "SIGNALS":[("clicked", partial(self.layer_property_changed, 'is_tracking'))], "ICON":None},
                                    "PushButton_LINKING":{"WIDGET":self.pushButton_checkable_exploring_linking_widgets, "SIGNALS":[("clicked", partial(self.layer_property_changed, 'is_linked'))], "ICON":None},
                                    "PushButton_SAVING":{"WIDGET":self.pushButton_checkable_exploring_saving_parameters, "SIGNALS":[("clicked", partial(self.layer_property_changed, 'is_saving'))], "ICON":None}
                                    }
        
        self.widgets["SINGLE_SELECTION"] = {
                                            "ComboBox_FeaturePickerWidget":{"WIDGET":self.mFeaturePickerWidget_exploring_single_selection, "SIGNALS":[("featureChanged", self.exploring_features_changed)]},
                                            "ComboBox_FieldExpressionWidget":{"WIDGET":self.mFieldExpressionWidget_exploring_single_selection, "SIGNALS":[("fieldChanged", self.exploring_source_params_changed)]}
                                            }
        
        self.widgets["MULTIPLE_SELECTION"] = {
                                            "ComboBox_CustomCheckableComboBox":{"WIDGET":self.customCheckableComboBox_exploring_multiple_selection, "SIGNALS":[("updatingCheckedItemList", self.exploring_features_changed),("filteringCheckedItemList", self.exploring_link_widgets)]},
                                            "ComboBox_FieldExpressionWidget":{"WIDGET":self.mFieldExpressionWidget_exploring_multiple_selection, "SIGNALS":[("fieldChanged", self.exploring_source_params_changed)]}
                                            }
        
        self.widgets["CUSTOM_SELECTION"] = {
                                            "ComboBox_FieldExpressionWidget":{"WIDGET":self.mFieldExpressionWidget_exploring_custom_selection, "SIGNALS":[("fieldChanged", self.exploring_source_params_changed)]}
                                            }
        
        self.widgets["FILTERING"] = {
                                    "PushButton_AUTO_CURRENT_LAYER":{"WIDGET":self.pushButton_checkable_filtering_auto_current_layer, "SIGNALS":[("clicked", self.filtering_auto_current_layer_changed)], "ICON":None},
                                    "PushButton_LAYERS_TO_FILTER":{"WIDGET":self.pushButton_checkable_filtering_layers_to_filter, "SIGNALS":[("clicked", partial(self.layer_property_changed, 'has_layers_to_filter'))], "ICON":None},
                                    "PushButton_COMBINE_OPERATOR":{"WIDGET":self.pushButton_checkable_filtering_current_layer_combine_operator, "SIGNALS":[("clicked", partial(self.layer_property_changed, 'has_combined_filter_logic'))], "ICON":None},
                                    "PushButton_GEOMETRIC_PREDICATES":{"WIDGET":self.pushButton_checkable_filtering_geometric_predicates, "SIGNALS":[("clicked", partial(self.layer_property_changed, 'has_geometric_predicates'))], "ICON":None},
                                    "PushButton_BUFFER":{"WIDGET":self.pushButton_checkable_filtering_buffer, "SIGNALS":[("clicked", partial(self.layer_property_changed, 'has_buffer'))], "ICON":None},
                                    "ComboBox_CURRENT_LAYER":{"WIDGET":self.comboBox_filtering_current_layer, "SIGNALS":[("layerChanged", self.current_layer_changed)]},
                                    "ComboBox_LAYERS_TO_FILTER":{"WIDGET":self.comboBox_filtering_layers_to_filter, "SIGNALS":[("checkedItemsChanged", partial(self.layer_property_changed, 'layers_to_filter'))]},
                                    "ComboBox_COMBINE_OPERATOR":{"WIDGET":self.comboBox_filtering_current_layer_combine_operator, "SIGNALS":[("currentTextChanged", partial(self.layer_property_changed, 'combined_filter_logic'))]},
                                    "ComboBox_GEOMETRIC_PREDICATES":{"WIDGET":self.comboBox_filtering_geometric_predicates, "SIGNALS":[("checkedItemsChanged", partial(self.layer_property_changed, 'geometric_predicates'))]},
                                    "ComboBox_PREDICATES_OPERATOR":{"WIDGET":self.comboBox_filtering_geometric_predicates_operator, "SIGNALS":[("currentTextChanged", partial(self.layer_property_changed, 'geometric_predicates_operator'))]},
                                    "QgsDoubleSpinBox_BUFFER":{"WIDGET":self.mQgsDoubleSpinBox_filtering_buffer, "SIGNALS":[("textChanged", partial(self.layer_property_changed, 'buffer'))]}
                                    }
        
        self.widgets["EXPORTING"] = {
                                    "PushButton_LAYERS":{"WIDGET":self.pushButton_checkable_exporting_layers, "SIGNALS":[("clicked", None)], "ICON":None},
                                    "PushButton_PROJECTION":{"WIDGET":self.pushButton_checkable_exporting_projection, "SIGNALS":[("clicked", None)], "ICON":None},
                                    "PushButton_STYLES":{"WIDGET":self.pushButton_checkable_exporting_styles, "SIGNALS":[("clicked", None)], "ICON":None},
                                    "PushButton_DATATYPE":{"WIDGET":self.pushButton_checkable_exporting_datatype, "SIGNALS":[("clicked", None)], "ICON":None},
                                    "PushButton_OUTPUT_FOLDER":{"WIDGET":self.pushButton_checkable_exporting_output_folder, "SIGNALS":[("clicked", self.dialog_export_folder)], "ICON":None},
                                    "PushButton_ZIP":{"WIDGET":self.pushButton_checkable_exporting_zip, "SIGNALS":[("clicked", self.dialog_export_zip)], "ICON":None},
                                    "ComboBox_LAYERS":{"WIDGET":self.comboBox_exporting_layers, "SIGNALS":[("checkedItemsChanged", None)]},
                                    "ComboBox_PROJECTION":{"WIDGET":self.mQgsProjectionSelectionWidget_exporting_projection, "SIGNALS":[("crsChanged", None)]},
                                    "ComboBox_STYLES":{"WIDGET":self.comboBox_exporting_styles, "SIGNALS":[("currentTextChanged", None)]},
                                    "ComboBox_DATATYPE":{"WIDGET":self.comboBox_exporting_datatype, "SIGNALS":[("currentTextChanged", None)]},
                                    "LineEdit_OUTPUT_FOLDER":{"WIDGET":self.lineEdit_exporting_output_folder, "SIGNALS":[("textEdited", self.reset_export_folder)]},
                                    "LineEdit_ZIP":{"WIDGET":self.lineEdit_exporting_zip, "SIGNALS":[("textEdited", self.reset_export_zip)]}
                                    }
    
        self.widgets["QGIS"] = {
                                "LayerTreeView":{"WIDGET":self.iface.layerTreeView(), "SIGNALS":[("currentLayerChanged", self.current_layer_changed)]}
                                }
        




    def manage_configuration_model(self):
        """Manage the qtreeview model configuration"""

        self.model = JsonModel(data=CONFIG_DATA, editable_keys=False, editable_values=True)


        self.view = JsonView(self.model, self.plugin_dir)
        self.CONFIGURATION.layout().addWidget(self.view)

        self.view.setModel(self.model)

        self.view.setStyleSheet("""padding:0px;
                                    color:black;""")

        self.view.setAnimated(True)
        self.view.viewport().setAcceptDrops(True)
        self.view.setDragDropMode(QAbstractItemView.DropOnly)
        self.view.setDropIndicatorShown(True)
        self.view.show()


        
    def manage_output_name(self):
        self.output_name = 'export'
        self.current_project_title = PROJECT.fileName().split('.')[0]
        self.current_project_path = PROJECT.homePath()
        if self.current_project_title is not None:
            self.output_name = 'export' + '_' + str(self.current_project_title)


    def set_widget_icon(self, widget_path, widget_type):

        file = CONFIG_DATA["DOCKWIDGET"][widget_type]["ICONS"][widget_path[0]][widget_path[1]]
        file_path = os.path.join(self.plugin_dir, "icons", file)
        icon = QtGui.QIcon(file_path)
        self.widgets[widget_path[0]][widget_path[1]]["ICON"] = file_path
        self.widgets[widget_path[0]][widget_path[1]]["WIDGET"].setIcon(icon)



    def manage_ui_style(self):

        """Manage the plugin style"""

        comboBox_style = """
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

        lineEdit_style = """
                                background-color: {color_2};
                                color:{color_1};
                                border-radius: 3px;
                                padding: 3px 3px 3px 3px;"""

        comboBox_style = comboBox_style.replace("{color_1}",COLORS["BACKGROUND"][1]).replace("{color_2}",COLORS["BACKGROUND"][2]).replace("{color_3}",COLORS["FONT"][1])

        dock_style = dock_style.replace("{color}",COLORS["BACKGROUND"][2])

        groupbox_style = groupbox_style.replace("{color_1}",COLORS["BACKGROUND"][0]).replace("{color_3}",COLORS["FONT"][1])

        lineEdit_style = lineEdit_style.replace("{color_1}",COLORS["FONT"][1]).replace("{color_2}",COLORS["BACKGROUND"][1])


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

        self.widgets["DOCK"]["ToolBox_tabTools"]["WIDGET"].setStyleSheet("""background-color: {};
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
        
        pushButton_style = json.dumps(CONFIG_DATA["DOCKWIDGET"]["PushButton"]["STYLE"])[1:-1].replace(': {', ' {').replace('\"', '').replace(',', '')
        print(pushButton_style)

        for widget_group in self.widgets:
            for widget_name in self.widgets[widget_group]:
                if widget_name.find("PushButton") >= 0:
                    self.set_widget_icon([widget_group, widget_name], "PushButton")
                    self.widgets[widget_group][widget_name]["WIDGET"].setStyleSheet(pushButton_style)
                elif widget_name.find("ComboBox") >= 0:
                    self.widgets[widget_group][widget_name]["WIDGET"].setStyleSheet(comboBox_style)
                elif widget_name.find("LineEdit") >= 0:
                    self.widgets[widget_group][widget_name]["WIDGET"].setStyleSheet(lineEdit_style)



    def manage_interactions(self):

        



        """INIT"""
        self.current_layer = self.iface.activeLayer()
        

        self.select_tabTools_index(self.widgets["DOCK"]["ToolBox_tabTools"]["WIDGET"].currentIndex())
        self.widgets["FILTERING"]["QgsDoubleSpinBox_BUFFER"]["WIDGET"].setExpressionsEnabled(True)
        self.widgets["EXPORTING"]["ComboBox_PROJECTION"]["WIDGET"].setCrs(PROJECT.crs())

        """SET INTERACTIONS"""
        for widget_group in self.widgets:
            for widget in self.widgets[widget_group]:
                for signal in self.widgets[widget_group][widget]["SIGNALS"]:
                    if signal[1] != None:
                        self.manageSignal([widget_group, widget], 'connect', signal[0])




        if self.current_layer != None:
            self.populate_predicats_chekableCombobox()
            self.exporting_populate_layers_chekableCombobox()
            self.filtering_populate_layers_chekableCombobox()
            self.filtering_auto_current_layer_changed()
            #self.exploring_groupbox_changed('single_selection')
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
        self.widgets["FILTERING"]["ComboBox_GEOMETRIC_PREDICATES"]["WIDGET"].clear()
        self.widgets["FILTERING"]["ComboBox_GEOMETRIC_PREDICATES"]["WIDGET"].addItems(self.predicats)

    def filtering_populate_layers_chekableCombobox(self):
        try:    
            self.widgets["FILTERING"]["ComboBox_LAYERS_TO_FILTER"]["WIDGET"].clear()
            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]

            if layer_props["filtering"]["has_layers_to_filter"] == True:
                i = 0
                for key in self.PROJECT_LAYERS:
                    layer_id = self.PROJECT_LAYERS[key]["infos"]["layer_id"]
                    layer_name = self.PROJECT_LAYERS[key]["infos"]["layer_name"]
                    layer_crs = self.PROJECT_LAYERS[key]["infos"]["layer_crs"]
                    layer_icon = self.icon_per_geometry_type(self.PROJECT_LAYERS[key]["infos"]["layer_geometry_type"])

                    if key != self.current_layer.id():
                        self.widgets["FILTERING"]["ComboBox_LAYERS_TO_FILTER"]["WIDGET"].addItem(layer_icon, layer_name + ' [%s]' % (layer_crs))
                        self.widgets["FILTERING"]["ComboBox_LAYERS_TO_FILTER"]["WIDGET"].setItemData(i, json.dumps(self.PROJECT_LAYERS[key]["infos"]), Qt.UserRole)
                        if len(layer_props["filtering"]["layers_to_filter"]) > 0:
                            if layer_id in list(layer_info["layer_id"] for layer_info in list(layer_props["filtering"]["layers_to_filter"])):
                                self.widgets["FILTERING"]["ComboBox_LAYERS_TO_FILTER"]["WIDGET"].setItemCheckState(i, Qt.Checked)
                            else:
                                self.widgets["FILTERING"]["ComboBox_LAYERS_TO_FILTER"]["WIDGET"].setItemCheckState(i, Qt.Unchecked)   
                        else:
                            self.widgets["FILTERING"]["ComboBox_LAYERS_TO_FILTER"]["WIDGET"].setItemCheckState(i, Qt.Unchecked)
                        i += 1    
            else:
                i = 0
                for key in self.PROJECT_LAYERS:
                    layer_name = self.PROJECT_LAYERS[key]["infos"]["layer_name"]
                    layer_crs = self.PROJECT_LAYERS[key]["infos"]["layer_crs"]
                    layer_icon = self.icon_per_geometry_type(self.PROJECT_LAYERS[key]["infos"]["layer_geometry_type"])
                    
                    if key != self.current_layer.id():
                        self.widgets["FILTERING"]["ComboBox_LAYERS_TO_FILTER"]["WIDGET"].addItem(layer_icon, layer_name + ' [%s]' % (layer_crs), self.PROJECT_LAYERS[key]["infos"])                 
                        self.widgets["FILTERING"]["ComboBox_LAYERS_TO_FILTER"]["WIDGET"].setItemCheckState(i, Qt.Unchecked)
                        i += 1    
        
        except Exception as e:
            self.exception = e
            print(self.exception)
            self.reinitializeLayerOnErrorEvent(self.current_layer.id())

    def exporting_populate_layers_chekableCombobox(self):

        self.widgets["EXPORTING"]["ComboBox_LAYERS"]["WIDGET"].clear()

        for key in self.PROJECT_LAYERS:
            layer_name = self.PROJECT_LAYERS[key]["infos"]["layer_name"]
            layer_crs = self.PROJECT_LAYERS[key]["infos"]["layer_crs"]
            layer_icon = self.icon_per_geometry_type(self.PROJECT_LAYERS[key]["infos"]["layer_geometry_type"])
            self.widgets["EXPORTING"]["ComboBox_LAYERS"]["WIDGET"].addItem(layer_icon, layer_name + ' [%s]' % (layer_crs), self.PROJECT_LAYERS[key]["infos"])
        
        self.widgets["EXPORTING"]["ComboBox_LAYERS"]["WIDGET"].selectAllOptions()
            




    def layer_property_changed(self, property):

        if self.current_layer == None:
            return
        
        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]

        
        
        

        flag_value_changed = False

        if property == "is_selecting":
            if layer_props["exploring"]["is_selecting"] is False and self.widgets["EXPLORING"]["PushButton_SELECTING"]["WIDGET"].isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["is_selecting"] = True
                flag_value_changed = True
                #self.exploring_groupbox_changed(self.current_exploring_groupbox)

            elif layer_props["exploring"]["is_selecting"] is True and self.widgets["EXPLORING"]["PushButton_SELECTING"]["WIDGET"].isChecked() is False:
                self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["is_selecting"] = False
                flag_value_changed = True

        elif property == "is_tracking":
            if layer_props["exploring"]["is_tracking"] is False and self.widgets["EXPLORING"]["PushButton_TRACKING"]["WIDGET"].isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["is_tracking"] = True
                flag_value_changed = True
                #self.exploring_groupbox_changed(self.current_exploring_groupbox)

            elif layer_props["exploring"]["is_tracking"] is True and self.widgets["EXPLORING"]["PushButton_TRACKING"]["WIDGET"].isChecked() is False:
                self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["is_tracking"] = False
                flag_value_changed = True

        elif property == "is_linked":
            if layer_props["exploring"]["is_linked"] is False and self.widgets["EXPLORING"]["PushButton_LINKING"]["WIDGET"].isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["is_linked"] = True
                flag_value_changed = True

            elif layer_props["exploring"]["is_linked"] is True and self.widgets["EXPLORING"]["PushButton_LINKING"]["WIDGET"].isChecked() is False:
                self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["is_linked"] = False
                flag_value_changed = True
            self.exploring_link_widgets()

        elif property == "is_saving":
            if layer_props["exploring"]["is_saving"] is False and self.widgets["EXPLORING"]["PushButton_SAVING"]["WIDGET"].isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["is_saving"] = True
                flag_value_changed = True
            elif layer_props["exploring"]["is_saving"] is True and self.widgets["EXPLORING"]["PushButton_SAVING"]["WIDGET"].isChecked() is False:
                self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["is_saving"] = False
                flag_value_changed = True
                self.reinitializeLayerOnErrorEvent(self.current_layer.id())

        elif property == "has_layers_to_filter":
            if layer_props["filtering"]["has_layers_to_filter"] is False and self.widgets["FILTERING"]["PushButton_LAYERS_TO_FILTER"]["WIDGET"].isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["has_layers_to_filter"] = True
                checked_list_data = []
                for i in range(self.widgets["FILTERING"]["ComboBox_LAYERS_TO_FILTER"]["WIDGET"].count()):
                   if self.widgets["FILTERING"]["ComboBox_LAYERS_TO_FILTER"]["WIDGET"].itemCheckState(i) == Qt.Checked:
                        data = self.widgets["FILTERING"]["ComboBox_LAYERS_TO_FILTER"]["WIDGET"].itemData(i, Qt.UserRole)
                        if isinstance(data, dict):
                            checked_list_data.append(data)
                        else:
                            checked_list_data.append(json.loads(data))
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["layers_to_filter"] = checked_list_data
                flag_value_changed = True
            elif layer_props["filtering"]["has_layers_to_filter"] is True and self.widgets["FILTERING"]["PushButton_LAYERS_TO_FILTER"]["WIDGET"].isChecked() is False:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["has_layers_to_filter"] = False
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["layers_to_filter"] = []

                state = self.manageSignal(["FILTERING","ComboBox_LAYERS_TO_FILTER"])
                if state == False:
                    self.widgets["FILTERING"]["ComboBox_LAYERS_TO_FILTER"]["WIDGET"].deselectAllOptions()
                    self.manageSignal(["FILTERING","ComboBox_LAYERS_TO_FILTER"])
                flag_value_changed = True
            
        elif property == "layers_to_filter":
            if layer_props["filtering"]["has_layers_to_filter"] is True and self.widgets["FILTERING"]["PushButton_LAYERS_TO_FILTER"]["WIDGET"].isChecked() is True:
                checked_list_data = []
                for i in range(self.widgets["FILTERING"]["ComboBox_LAYERS_TO_FILTER"]["WIDGET"].count()):
                   if self.widgets["FILTERING"]["ComboBox_LAYERS_TO_FILTER"]["WIDGET"].itemCheckState(i) == Qt.Checked:
                        data = self.widgets["FILTERING"]["ComboBox_LAYERS_TO_FILTER"]["WIDGET"].itemData(i, Qt.UserRole)
                        if isinstance(data, dict):
                            checked_list_data.append(data)
                        else:
                            checked_list_data.append(json.loads(data))
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["layers_to_filter"] = checked_list_data
                flag_value_changed = True
            else:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["layers_to_filter"] = []
                state = self.manageSignal(["FILTERING","ComboBox_LAYERS_TO_FILTER"])
                if state == False:
                    self.widgets["FILTERING"]["ComboBox_LAYERS_TO_FILTER"]["WIDGET"].deselectAllOptions()
                    self.manageSignal(["FILTERING","ComboBox_LAYERS_TO_FILTER"])
                flag_value_changed = True

        elif property == "has_combined_filter_logic":
            if layer_props["infos"]["has_combined_filter_logic"] is False and self.widgets["FILTERING"]["PushButton_COMBINE_OPERATOR"]["WIDGET"].isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["infos"]["has_combined_filter_logic"] = True
                self.PROJECT_LAYERS[self.current_layer.id()]["infos"]["combined_filter_logic"] = self.widgets["FILTERING"]["ComboBox_COMBINE_OPERATOR"]["WIDGET"].currentText()
                flag_value_changed = True
            elif layer_props["infos"]["has_combined_filter_logic"] is True and self.widgets["FILTERING"]["PushButton_COMBINE_OPERATOR"]["WIDGET"].isChecked() is False:
                self.PROJECT_LAYERS[self.current_layer.id()]["infos"]["has_combined_filter_logic"] = False
                self.PROJECT_LAYERS[self.current_layer.id()]["infos"]["combined_filter_logic"] = ''
                state = self.manageSignal(["FILTERING","ComboBox_COMBINE_OPERATOR"])
                if state == False:
                    self.widgets["FILTERING"]["ComboBox_COMBINE_OPERATOR"]["WIDGET"].setCurrentIndex(0)
                    self.manageSignal(["FILTERING","ComboBox_COMBINE_OPERATOR"])
                flag_value_changed = True
            
        elif property == "combined_filter_logic":
            if layer_props["infos"]["has_combined_filter_logic"] is True and self.widgets["FILTERING"]["PushButton_LAYERS_TO_FILTER"]["WIDGET"].isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["infos"]["combined_filter_logic"] = self.widgets["FILTERING"]["ComboBox_COMBINE_OPERATOR"]["WIDGET"].currentText()
                flag_value_changed = True
            else:
                self.PROJECT_LAYERS[self.current_layer.id()]["infos"]["combined_filter_logic"] = ''
                state = self.manageSignal(["FILTERING","ComboBox_COMBINE_OPERATOR"])
                if state == False:
                    self.widgets["FILTERING"]["ComboBox_COMBINE_OPERATOR"]["WIDGET"].setCurrentIndex(0)
                    self.manageSignal(["FILTERING","ComboBox_COMBINE_OPERATOR"])
                flag_value_changed = True

        elif property == "has_geometric_predicates":
            self.filtering_geometric_predicates_state_changed()
            if layer_props["filtering"]["has_geometric_predicates"] is False and self.widgets["FILTERING"]["PushButton_GEOMETRIC_PREDICATES"]["WIDGET"].isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["has_geometric_predicates"] = True
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["geometric_predicates"] = self.widgets["FILTERING"]["ComboBox_GEOMETRIC_PREDICATES"]["WIDGET"].checkedItems()
                flag_value_changed = True
            elif layer_props["filtering"]["has_geometric_predicates"] is True and self.widgets["FILTERING"]["PushButton_GEOMETRIC_PREDICATES"]["WIDGET"].isChecked() is False:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["has_geometric_predicates"] = False
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["geometric_predicates"] = []
                state = self.manageSignal(["FILTERING","ComboBox_GEOMETRIC_PREDICATES"])
                if state == False:
                    self.widgets["FILTERING"]["ComboBox_GEOMETRIC_PREDICATES"]["WIDGET"].deselectAllOptions()
                    self.manageSignal(["FILTERING","ComboBox_GEOMETRIC_PREDICATES"])
                flag_value_changed = True

        elif property == "geometric_predicates":
            if layer_props["filtering"]["has_geometric_predicates"] is True and self.widgets["FILTERING"]["PushButton_GEOMETRIC_PREDICATES"]["WIDGET"].isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["geometric_predicates"] = self.widgets["FILTERING"]["ComboBox_GEOMETRIC_PREDICATES"]["WIDGET"].checkedItems()
                flag_value_changed = True
            else:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["geometric_predicates"] = []
                state = self.manageSignal(["FILTERING","ComboBox_GEOMETRIC_PREDICATES"])
                if state == False:
                    self.widgets["FILTERING"]["ComboBox_GEOMETRIC_PREDICATES"]["WIDGET"].deselectAllOptions()
                    self.manageSignal(["FILTERING","ComboBox_GEOMETRIC_PREDICATES"])
                flag_value_changed = True

        
        elif property == "geometric_predicates_operator":
            if layer_props["filtering"]["has_geometric_predicates"] is True and self.widgets["FILTERING"]["PushButton_GEOMETRIC_PREDICATES"]["WIDGET"].isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["geometric_predicates_operator"] = self.widgets["FILTERING"]["ComboBox_PREDICATES_OPERATOR"]["WIDGET"].currentText()
                flag_value_changed = True
            else:
                state = self.manageSignal(self.widgets["FILTERING"]["ComboBox_PREDICATES_OPERATOR"])
                if state == False:
                    self.widgets["FILTERING"]["ComboBox_PREDICATES_OPERATOR"]["WIDGET"].setCurrentIndex(0)
                    self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["geometric_predicates_operator"] = self.widgets["FILTERING"]["ComboBox_PREDICATES_OPERATOR"]["WIDGET"].currentText()
                    self.manageSignal(self.widgets["FILTERING"]["ComboBox_PREDICATES_OPERATOR"])
                flag_value_changed = True

        elif property == "has_buffer":
            self.filtering_buffer_state_changed()
            if layer_props["filtering"]["has_buffer"] is False and self.widgets["FILTERING"]["PushButton_BUFFER"]["WIDGET"].isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["has_buffer"] = True
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer"] = self.widgets["FILTERING"]["QgsDoubleSpinBox_BUFFER"]["WIDGET"].value()
                flag_value_changed = True
            elif layer_props["filtering"]["has_buffer"] is True and self.widgets["FILTERING"]["PushButton_BUFFER"]["WIDGET"].isChecked() is False:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["has_buffer"] = False
                state = self.manageSignal(["FILTERING","QgsDoubleSpinBox_BUFFER"])
                if state == False:
                    self.widgets["FILTERING"]["QgsDoubleSpinBox_BUFFER"]["WIDGET"].setValue(0.0)
                    self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer"] = self.widgets["FILTERING"]["QgsDoubleSpinBox_BUFFER"]["WIDGET"].value()
                    self.manageSignal(["FILTERING","QgsDoubleSpinBox_BUFFER"])
                flag_value_changed = True

        elif property == "buffer":
            if layer_props["filtering"]["has_buffer"] is True and self.widgets["FILTERING"]["PushButton_BUFFER"]["WIDGET"].isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer"] = self.widgets["FILTERING"]["QgsDoubleSpinBox_BUFFER"]["WIDGET"].value()
                flag_value_changed = True
            else:
                state = self.manageSignal(["FILTERING","QgsDoubleSpinBox_BUFFER"])
                if state == False:
                    self.widgets["FILTERING"]["QgsDoubleSpinBox_BUFFER"]["WIDGET"].setValue(0.0)
                    self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer"] = self.widgets["FILTERING"]["QgsDoubleSpinBox_BUFFER"]["WIDGET"].value()
                    self.manageSignal(["FILTERING","QgsDoubleSpinBox_BUFFER"])
                flag_value_changed = True


        if flag_value_changed is True:
            self.setProjectLayersEvent(self.PROJECT_LAYERS)



    def dialog_export_folder(self):

        if self.widgets["EXPORTING"]["PushButton_OUTPUT_FOLDER"]["WIDGET"].isChecked() == True:
            
            folderpath = str(QtWidgets.QFileDialog.getExistingDirectory(self, 'Select a folder where to export your layers', self.current_project_path))

            if folderpath:
                self.widgets["EXPORTING"]["LineEdit_OUTPUT_FOLDER"]["WIDGET"].setText(folderpath)
                print(folderpath)
            else:
                self.widgets["EXPORTING"]["PushButton_OUTPUT_FOLDER"]["WIDGET"].setChecked(False)
        else:
            self.widgets["EXPORTING"]["LineEdit_OUTPUT_FOLDER"]["WIDGET"].clear()

    def reset_export_folder(self):

        if str(self.widgets["EXPORTING"]["LineEdit_OUTPUT_FOLDER"]["WIDGET"].text()) == '':
            self.widgets["EXPORTING"]["LineEdit_OUTPUT_FOLDER"]["WIDGET"].clear()
            self.widgets["EXPORTING"]["PushButton_OUTPUT_FOLDER"]["WIDGET"].setChecked(False)


    def dialog_export_zip(self):

        if self.widgets["EXPORTING"]["PushButton_ZIP"]["WIDGET"].isChecked() == True:

            
            filepath = str(QtWidgets.QFileDialog.getSaveFileName(self, 'Save your exported data to a zip file', os.path.join(self.current_project_path, self.output_name) ,'*.zip')[0])

            if filepath:
                self.widgets["EXPORTING"]["LineEdit_ZIP"]["WIDGET"].setText(filepath)
                print(filepath)
            else:
                self.widgets["EXPORTING"]["PushButton_ZIP"]["WIDGET"].setChecked(False)
        else:
            self.widgets["EXPORTING"]["LineEdit_ZIP"]["WIDGET"].clear()


    def reset_export_zip(self):

        if str(self.widgets["EXPORTING"]["LineEdit_ZIP"]["WIDGET"].text()) == '':
            self.widgets["EXPORTING"]["LineEdit_ZIP"]["WIDGET"].clear()
            self.widgets["EXPORTING"]["PushButton_ZIP"]["WIDGET"].setChecked(False)


    def select_tabTools_index(self, i):
        """Keep the current tab index updated"""
        self.tabTools_current_index = i
        if self.tabTools_current_index == 1:
            self.widgets["ACTION"]["PushButton_EXPORT"]["WIDGET"].setEnabled(True)
        else:
            self.widgets["ACTION"]["PushButton_EXPORT"]["WIDGET"].setEnabled(False)

    def filtering_auto_current_layer_changed(self):
        if self.widgets["FILTERING"]["PushButton_AUTO_CURRENT_LAYER"]["WIDGET"].isChecked() is True:
            self.auto_change_current_layer_flag = True
            state = self.manageSignal(["QGIS","LayerTreeView"], 'connect')
            if state == False:
                raise SignalStateChangeError(state, self.widgets, ["QGIS","LayerTreeView"], 'connect')
        else:
            self.auto_change_current_layer_flag = False
            state = self.manageSignal(["QGIS","LayerTreeView"], 'disconnect')
            if state == True:
                raise SignalStateChangeError(state, self.widgets, ["QGIS","LayerTreeView"], 'disconnect')


    def filtering_geometric_predicates_state_changed(self):
        """Manage the geo filter state checkbox"""
        if self.widgets["FILTERING"]["PushButton_GEOMETRIC_PREDICATES"]["WIDGET"].isChecked() is True:
            self.widgets["FILTERING"]["PushButton_BUFFER"]["WIDGET"].setEnabled(True)

            self.widgets["FILTERING"]["ComboBox_PREDICATES_OPERATOR"]["WIDGET"].setEnabled(True)
            self.widgets["FILTERING"]["ComboBox_PREDICATES_OPERATOR"]["WIDGET"].setFrame(True)
            self.widgets["FILTERING"]["ComboBox_GEOMETRIC_PREDICATES"]["WIDGET"].setEnabled(True)
            self.widgets["FILTERING"]["ComboBox_GEOMETRIC_PREDICATES"]["WIDGET"].setFrame(True)
        else:
            self.widgets["FILTERING"]["PushButton_BUFFER"]["WIDGET"].setEnabled(False)
            self.widgets["FILTERING"]["PushButton_BUFFER"]["WIDGET"].setChecked(False)

            self.widgets["FILTERING"]["ComboBox_GEOMETRIC_PREDICATES"]["WIDGET"].setFrame(False)
            self.widgets["FILTERING"]["ComboBox_GEOMETRIC_PREDICATES"]["WIDGET"].setDisabled(True)
            self.widgets["FILTERING"]["ComboBox_PREDICATES_OPERATOR"]["WIDGET"].setDisabled(True)
            self.widgets["FILTERING"]["ComboBox_PREDICATES_OPERATOR"]["WIDGET"].setFrame(True)
            self.widgets["FILTERING"]["QgsDoubleSpinBox_BUFFER"]["WIDGET"].setDisabled(True)
            
      
    def filtering_buffer_state_changed(self):
        """Manage the buffer state checkbox"""
        if self.widgets["FILTERING"]["PushButton_BUFFER"]["WIDGET"].isChecked() is True:
            self.widgets["FILTERING"]["QgsDoubleSpinBox_BUFFER"]["WIDGET"].setEnabled(True)
        else:
            self.widgets["FILTERING"]["QgsDoubleSpinBox_BUFFER"]["WIDGET"].setEnabled(False)

    def exploring_identify_clicked(self):
        

        if self.current_exploring_groupbox == "single_selection":
            input = self.widgets["SINGLE_SELECTION"]["ComboBox_FeaturePickerWidget"]["WIDGET"].feature()
            features, expr = self.getExploringFeatures(input)

        elif self.current_exploring_groupbox == "multiple_selection":
            input = self.widgets["MULTIPLE_SELECTION"]["ComboBox_CustomCheckableComboBox"]["WIDGET"].checkedItems()
            features, expr = self.getExploringFeatures(input, True)

        elif self.current_exploring_groupbox == "custom_selection":
            features = self.exploring_custom_selection()
        
        if len(features) == 0:
            return
        else:
            self.iface.mapCanvas().flashFeatureIds(self.current_layer, [feature.id() for feature in features], startColor=QColor(235, 49, 42, 255), endColor=QColor(237, 97, 62, 25), flashes=6, duration=400)
        


    def get_current_features(self):

        if self.current_exploring_groupbox == "single_selection":
            input = self.widgets["SINGLE_SELECTION"]["ComboBox_FeaturePickerWidget"]["WIDGET"].feature()
            features, expression = self.getExploringFeatures(input)

        elif self.current_exploring_groupbox == "multiple_selection":
            input = self.widgets["MULTIPLE_SELECTION"]["ComboBox_CustomCheckableComboBox"]["WIDGET"].checkedItems()
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
            
            if expression != self.widgets["SINGLE_SELECTION"]["ComboBox_FeaturePickerWidget"]["WIDGET"].displayExpression():
                self.widgets["SINGLE_SELECTION"]["ComboBox_FeaturePickerWidget"]["WIDGET"].setDisplayExpression(expression)


                self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["single_selection_expression"] = expression
                flag_value_changed = True

        elif self.current_exploring_groupbox == "multiple_selection":

            if expression != self.widgets["MULTIPLE_SELECTION"]["ComboBox_CustomCheckableComboBox"]["WIDGET"].displayExpression():
                self.widgets["MULTIPLE_SELECTION"]["ComboBox_CustomCheckableComboBox"]["WIDGET"].setDisplayExpression(expression)


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

        if self.widgets["DOCK"]["GroupBox_SINGLE_SELECTION"]["WIDGET"].isChecked() is True or self.widgets["DOCK"]["GroupBox_SINGLE_SELECTION"]["WIDGET"].isCollapsed() is False:
            exploring_groupbox = "single_selection"

        elif self.widgets["DOCK"]["GroupBox_MULTIPLE_SELECTION"]["WIDGET"].isChecked() is True or self.widgets["DOCK"]["GroupBox_MULTIPLE_SELECTION"]["WIDGET"].isCollapsed() is False:
            exploring_groupbox = "multiple_selection"  

        elif self.widgets["DOCK"]["GroupBox_CUSTOM_SELECTION"]["WIDGET"].isChecked() is True or self.widgets["DOCK"]["GroupBox_CUSTOM_SELECTION"]["WIDGET"].isCollapsed() is False:
            exploring_groupbox = "custom_selection"

        self.exploring_groupbox_changed(exploring_groupbox)




    def exploring_groupbox_changed(self, groupbox):


        state = self.manageSignal(["SINGLE_SELECTION","ComboBox_FeaturePickerWidget"], 'disconnect')
        state = self.manageSignal(["DOCK","GroupBox_SINGLE_SELECTION"], 'disconnect')
        state = self.manageSignal(["DOCK","GroupBox_MULTIPLE_SELECTION"], 'disconnect')
        state = self.manageSignal(["DOCK","GroupBox_CUSTOM_SELECTION"], 'disconnect')
        print(state)
        # if state == True:
        #     raise SignalStateChangeError(state, self.widgets, ["SINGLE_SELECTION","ComboBox_FeaturePickerWidget"])

        if groupbox == "single_selection":
  
            if self.widgets["DOCK"]["GroupBox_SINGLE_SELECTION"]["WIDGET"].isChecked() is True or self.widgets["DOCK"]["GroupBox_SINGLE_SELECTION"]["WIDGET"].isCollapsed() is False:


                self.widgets["DOCK"]["GroupBox_SINGLE_SELECTION"]["WIDGET"].setChecked(True)
                self.widgets["DOCK"]["GroupBox_SINGLE_SELECTION"]["WIDGET"].setCollapsed(False)

                self.widgets["DOCK"]["GroupBox_MULTIPLE_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["GroupBox_MULTIPLE_SELECTION"]["WIDGET"].setCollapsed(True)

                self.widgets["DOCK"]["GroupBox_CUSTOM_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["GroupBox_CUSTOM_SELECTION"]["WIDGET"].setCollapsed(True)

                self.current_exploring_groupbox = "single_selection"

                self.widgets["SINGLE_SELECTION"]["ComboBox_FeaturePickerWidget"]["WIDGET"].setEnabled(True)
                self.widgets["SINGLE_SELECTION"]["ComboBox_FieldExpressionWidget"]["WIDGET"].setEnabled(True)

                if self.current_layer != None:
                    self.exploring_features_changed(self.widgets["SINGLE_SELECTION"]["ComboBox_FeaturePickerWidget"]["WIDGET"].feature())



        elif groupbox == "multiple_selection":

            if self.widgets["DOCK"]["GroupBox_MULTIPLE_SELECTION"]["WIDGET"].isChecked() is True or self.widgets["DOCK"]["GroupBox_MULTIPLE_SELECTION"]["WIDGET"].isCollapsed() is False:
                

                self.widgets["DOCK"]["GroupBox_MULTIPLE_SELECTION"]["WIDGET"].setChecked(True)
                self.widgets["DOCK"]["GroupBox_MULTIPLE_SELECTION"]["WIDGET"].setCollapsed(False)

                self.widgets["DOCK"]["GroupBox_SINGLE_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["GroupBox_SINGLE_SELECTION"]["WIDGET"].setCollapsed(True)

                self.widgets["DOCK"]["GroupBox_CUSTOM_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["GroupBox_CUSTOM_SELECTION"]["WIDGET"].setCollapsed(True)

                self.current_exploring_groupbox = "multiple_selection"

                self.widgets["MULTIPLE_SELECTION"]["ComboBox_CustomCheckableComboBox"]["WIDGET"].setEnabled(True)
                self.widgets["MULTIPLE_SELECTION"]["ComboBox_FieldExpressionWidget"]["WIDGET"].setEnabled(True)



                if self.current_layer != None:
                    self.exploring_features_changed(self.widgets["MULTIPLE_SELECTION"]["ComboBox_CustomCheckableComboBox"]["WIDGET"].currentSelectedFeatures(), True)


        elif groupbox == "custom_selection":

            if self.widgets["DOCK"]["GroupBox_CUSTOM_SELECTION"]["WIDGET"].isChecked() is True or self.widgets["DOCK"]["GroupBox_CUSTOM_SELECTION"]["WIDGET"].isCollapsed() is False:
                

                self.widgets["DOCK"]["GroupBox_CUSTOM_SELECTION"]["WIDGET"].setChecked(True)
                self.widgets["DOCK"]["GroupBox_CUSTOM_SELECTION"]["WIDGET"].setCollapsed(False)

                self.widgets["DOCK"]["GroupBox_MULTIPLE_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["GroupBox_MULTIPLE_SELECTION"]["WIDGET"].setCollapsed(True)

                self.widgets["DOCK"]["GroupBox_SINGLE_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["GroupBox_SINGLE_SELECTION"]["WIDGET"].setCollapsed(True)

                self.current_exploring_groupbox = "custom_selection"

                self.widgets["CUSTOM_SELECTION"]["ComboBox_FieldExpressionWidget"]["WIDGET"].setEnabled(True)

                if self.current_layer != None:
                    self.exploring_custom_selection()


        state = self.manageSignal(["SINGLE_SELECTION","ComboBox_FeaturePickerWidget"], 'connect')
        state = self.manageSignal(["DOCK","GroupBox_SINGLE_SELECTION"], 'connect')
        state = self.manageSignal(["DOCK","GroupBox_MULTIPLE_SELECTION"], 'connect')
        state = self.manageSignal(["DOCK","GroupBox_CUSTOM_SELECTION"], 'connect')
        print(state)
        # if state == False:
        #     raise SignalStateChangeError(state, self.widgets, ["SINGLE_SELECTION","ComboBox_FeaturePickerWidget"])
        

    def current_layer_changed(self, layer):

        self.current_layer = layer  

        if self.current_layer == None:
            return
        
        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]

        widgets_to_stop =   [
                                ["SINGLE_SELECTION","ComboBox_FeaturePickerWidget"],
                                ["SINGLE_SELECTION","ComboBox_FieldExpressionWidget"],
                                ["MULTIPLE_SELECTION","ComboBox_CustomCheckableComboBox"],
                                ["MULTIPLE_SELECTION","ComboBox_FieldExpressionWidget"],
                                ["CUSTOM_SELECTION","ComboBox_FieldExpressionWidget"],
                                ["FILTERING","QgsDoubleSpinBox_BUFFER"],
                                ["FILTERING","ComboBox_GEOMETRIC_PREDICATES"],
                                ["FILTERING","ComboBox_PREDICATES_OPERATOR"],
                                ["FILTERING","ComboBox_COMBINE_OPERATOR"],
                                ["FILTERING","ComboBox_LAYERS_TO_FILTER"],
                                ["FILTERING","ComboBox_CURRENT_LAYER"]
                            ]
        
        for widget_path in widgets_to_stop:
            state = self.manageSignal(widget_path)
            if state == True:
                raise SignalStateChangeError(state, self.widgets, widget_path)

        if self.auto_change_current_layer_flag == True:
            widget_path = ["QGIS","LayerTreeView"]
            state = self.manageSignal(widget_path)
            if state == True:
                raise SignalStateChangeError(state, self.widgets, widget_path)




        currentLayer = self.widgets["FILTERING"]["ComboBox_CURRENT_LAYER"]["WIDGET"].currentLayer()
        if currentLayer != None and currentLayer.id() != self.current_layer.id():
            self.widgets["FILTERING"]["ComboBox_CURRENT_LAYER"]["WIDGET"].setLayer(self.current_layer)


        """SINGLE SELECTION"""

        self.widgets["SINGLE_SELECTION"]["ComboBox_FieldExpressionWidget"]["WIDGET"].setLayer(self.current_layer)
        self.widgets["SINGLE_SELECTION"]["ComboBox_FieldExpressionWidget"]["WIDGET"].setExpression(layer_props["exploring"]["single_selection_expression"])

        self.widgets["SINGLE_SELECTION"]["ComboBox_FeaturePickerWidget"]["WIDGET"].setLayer(self.current_layer)
        self.widgets["SINGLE_SELECTION"]["ComboBox_FeaturePickerWidget"]["WIDGET"].setDisplayExpression(layer_props["exploring"]["single_selection_expression"])
        self.widgets["SINGLE_SELECTION"]["ComboBox_FeaturePickerWidget"]["WIDGET"].setFetchGeometry(True)
        self.widgets["SINGLE_SELECTION"]["ComboBox_FeaturePickerWidget"]["WIDGET"].setShowBrowserButtons(True)


        """MULTIPLE SELECTION"""
        
        self.widgets["MULTIPLE_SELECTION"]["ComboBox_FieldExpressionWidget"]["WIDGET"].setLayer(self.current_layer)
        self.widgets["MULTIPLE_SELECTION"]["ComboBox_FieldExpressionWidget"]["WIDGET"].setExpression(layer_props["exploring"]["multiple_selection_expression"])

        self.widgets["MULTIPLE_SELECTION"]["ComboBox_CustomCheckableComboBox"]["WIDGET"].setLayer(self.current_layer, layer_props)


        """CUSTOM SELECTION"""

        self.widgets["CUSTOM_SELECTION"]["ComboBox_FieldExpressionWidget"]["WIDGET"].setLayer(self.current_layer)
        self.widgets["CUSTOM_SELECTION"]["ComboBox_FieldExpressionWidget"]["WIDGET"].setExpression(layer_props["exploring"]["custom_selection_expression"])


        """EXPLORING"""

        if layer_props["exploring"]["is_selecting"] == True:
            self.widgets["EXPLORING"]["PushButton_SELECTING"]["WIDGET"].setChecked(True)
        elif layer_props["exploring"]["is_selecting"] == False:
            self.widgets["EXPLORING"]["PushButton_SELECTING"]["WIDGET"].setChecked(False)


        if layer_props["exploring"]["is_tracking"] == True:
            self.widgets["EXPLORING"]["PushButton_TRACKING"]["WIDGET"].setChecked(True)
        elif layer_props["exploring"]["is_tracking"] == False:
            self.widgets["EXPLORING"]["PushButton_TRACKING"]["WIDGET"].setChecked(False)


        if layer_props["exploring"]["is_linked"] == True:
            self.widgets["EXPLORING"]["PushButton_LINKING"]["WIDGET"].setChecked(True)
        elif layer_props["exploring"]["is_linked"] == False:
            self.widgets["EXPLORING"]["PushButton_LINKING"]["WIDGET"].setChecked(False)


        if layer_props["exploring"]["is_saving"] == True:
            self.widgets["EXPLORING"]["PushButton_SAVING"]["WIDGET"].setChecked(True)
        elif layer_props["exploring"]["is_saving"] == False:
            self.widgets["EXPLORING"]["PushButton_SAVING"]["WIDGET"].setChecked(False)


        """FILTERING"""

        if layer_props["filtering"]["has_layers_to_filter"] == True:
            self.widgets["FILTERING"]["PushButton_LAYERS_TO_FILTER"]["WIDGET"].setChecked(True)
            self.filtering_populate_layers_chekableCombobox()
        elif layer_props["filtering"]["has_layers_to_filter"] == False:
            self.widgets["FILTERING"]["PushButton_LAYERS_TO_FILTER"]["WIDGET"].setChecked(False)
            self.filtering_populate_layers_chekableCombobox()


        if layer_props["infos"]["has_combined_filter_logic"] == True:
            self.widgets["FILTERING"]["PushButton_COMBINE_OPERATOR"]["WIDGET"].setChecked(True)
            self.widgets["FILTERING"]["ComboBox_COMBINE_OPERATOR"]["WIDGET"].setCurrentText(layer_props["infos"]["combined_filter_logic"])
        elif layer_props["infos"]["has_combined_filter_logic"] == False:
            self.widgets["FILTERING"]["PushButton_COMBINE_OPERATOR"]["WIDGET"].setChecked(False)
            self.widgets["FILTERING"]["ComboBox_COMBINE_OPERATOR"]["WIDGET"].setCurrentIndex(0)


        if layer_props["filtering"]["has_geometric_predicates"] == True:
            self.widgets["FILTERING"]["PushButton_GEOMETRIC_PREDICATES"]["WIDGET"].setChecked(True)
            self.widgets["FILTERING"]["ComboBox_GEOMETRIC_PREDICATES"]["WIDGET"].setCheckedItems(layer_props["filtering"]["geometric_predicates"])
            self.widgets["FILTERING"]["ComboBox_PREDICATES_OPERATOR"]["WIDGET"].setCurrentText(layer_props["filtering"]["geometric_predicates_operator"])
        elif layer_props["filtering"]["has_geometric_predicates"] == False:
            self.widgets["FILTERING"]["PushButton_GEOMETRIC_PREDICATES"]["WIDGET"].setChecked(False)
            self.widgets["FILTERING"]["ComboBox_GEOMETRIC_PREDICATES"]["WIDGET"].deselectAllOptions()
            self.widgets["FILTERING"]["ComboBox_PREDICATES_OPERATOR"]["WIDGET"].setCurrentIndex(0)
            self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["geometric_predicates_operator"] = self.widgets["FILTERING"]["ComboBox_PREDICATES_OPERATOR"]["WIDGET"].currentText()
                

        if layer_props["filtering"]["has_buffer"] == True:
            self.widgets["FILTERING"]["PushButton_BUFFER"]["WIDGET"].setChecked(True)
            self.widgets["FILTERING"]["QgsDoubleSpinBox_BUFFER"]["WIDGET"].setValue(layer_props["filtering"]["buffer"])
        elif layer_props["filtering"]["has_buffer"] == False:
            self.widgets["FILTERING"]["PushButton_BUFFER"]["WIDGET"].setChecked(False)
            self.widgets["FILTERING"]["QgsDoubleSpinBox_BUFFER"]["WIDGET"].setValue(0.0)


        self.filtering_geometric_predicates_state_changed()
        self.filtering_buffer_state_changed()
        self.exploring_link_widgets()

        for widget_path in widgets_to_stop:
            state = self.manageSignal(widget_path)
            if state == False:
                raise SignalStateChangeError(state, self.widgets, widget_path)

        if self.auto_change_current_layer_flag == True:
            if self.iface.activeLayer().id() != self.current_layer.id():
                self.widgets["QGIS"]["LayerTreeView"]["WIDGET"].setCurrentLayer(self.current_layer)

            widget_path = ["QGIS","LayerTreeView"]
            state = self.manageSignal(widget_path)
            if state == False:
                raise SignalStateChangeError(state, self.widgets, widget_path)
        
            

    def exploring_link_widgets(self, expression=None):

        if self.current_layer == None:
            return
        
        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
        custom_filter = None

        if layer_props["exploring"]["is_linked"] == True:
            if QgsExpression(layer_props["exploring"]["custom_selection_expression"]).isValid() is True:
                if QgsExpression(layer_props["exploring"]["custom_selection_expression"]).isField() is False:
                    custom_filter = layer_props["exploring"]["custom_selection_expression"]
                    self.widgets["MULTIPLE_SELECTION"]["ComboBox_CustomCheckableComboBox"]["WIDGET"].setFilterExpression(custom_filter)
            if expression != None:
                self.widgets["SINGLE_SELECTION"]["ComboBox_FeaturePickerWidget"]["WIDGET"].setFilterExpression(expression)
            elif self.widgets["MULTIPLE_SELECTION"]["ComboBox_CustomCheckableComboBox"]["WIDGET"].currentSelectedFeatures() != False:
                features, expression = self.getExploringFeatures(self.widgets["MULTIPLE_SELECTION"]["ComboBox_CustomCheckableComboBox"]["WIDGET"].currentSelectedFeatures(), True)
                if len(features) > 0 and expression != None:
                    self.widgets["SINGLE_SELECTION"]["ComboBox_FeaturePickerWidget"]["WIDGET"].setFilterExpression(expression)
            elif self.widgets["MULTIPLE_SELECTION"]["ComboBox_CustomCheckableComboBox"]["WIDGET"].currentVisibleFeatures() != False:
                features, expression = self.getExploringFeatures(self.widgets["MULTIPLE_SELECTION"]["ComboBox_CustomCheckableComboBox"]["WIDGET"].currentVisibleFeatures(), True)
                if len(features) > 0 and expression != None:
                    self.widgets["SINGLE_SELECTION"]["ComboBox_FeaturePickerWidget"]["WIDGET"].setFilterExpression(expression)
            elif custom_filter != None:
                self.widgets["SINGLE_SELECTION"]["ComboBox_FeaturePickerWidget"]["WIDGET"].setFilterExpression(custom_filter)
           
        else:
            self.widgets["SINGLE_SELECTION"]["ComboBox_FeaturePickerWidget"]["WIDGET"].setFilterExpression('')
            self.widgets["MULTIPLE_SELECTION"]["ComboBox_CustomCheckableComboBox"]["WIDGET"].setFilterExpression('')



    def zooming_to_features(self, features):
        features_with_geometry = [feature for feature in features if feature.hasGeometry()]

        if len(features_with_geometry) == 1:
            feature = features_with_geometry[0]

            if str(feature.geometry().type()) == 'GeometryType.Point':
                box = feature.geometry().buffer(50,5).boundingBox()
            else:
                box = feature.geometry().boundingBox()

            self.iface.mapCanvas().zoomToFeatureExtent(box)
        else:
            self.iface.mapCanvas().zoomToFeatureIds(self.current_layer, [feature.id() for feature in features_with_geometry])

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
                    expression = layer_props["infos"]["primary_key_name"] + " IN (" + ", ".join(input_ids) + ")"
                else:
                    input_ids = [str(feat[1]) for feat in input]
                    expression = layer_props["infos"]["primary_key_name"] + " IN (\'" + "\', \'".join(input_ids) + "\')"
            
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
        
        layers = [layer for layer in PROJECT.mapLayersByName(self.PROJECT_LAYERS[self.current_layer.id()]["infos"]["layer_name"]) if layer.id() == self.current_layer.id()]
        if len(layers) == 0:
            self.current_layer = self.iface.activeLayer()
            
        self.exporting_populate_layers_chekableCombobox()
        self.current_layer_changed(self.current_layer)
        self.layer_property_changed('layers_to_filter')

    def setProjectLayersEvent(self, event):
        self.settingProjectLayers.emit(event)
    
    def getProjectLayersEvent(self, event):
        self.gettingProjectLayers.emit()

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def launchTaskEvent(self, event):
        self.launchingTask.emit(event)
    
    def reinitializeLayerOnErrorEvent(self, event):
        self.reinitializingLayerOnError.emit(event)

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



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
import re
from functools import partial
from osgeo import ogr
from qgis.PyQt import QtGui, QtWidgets, uic
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *
from qgis.utils import iface
from qgis.PyQt.QtWidgets import QApplication, QVBoxLayout

from .modules.widgets import QgsCheckableComboBoxFeaturesListPickerWidget, QgsCheckableComboBoxLayer
from .modules.qt_json_view.model import JsonModel, JsonSortFilterProxyModel
from .modules.qt_json_view.view import JsonView
from .modules.customExceptions import *

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'filter_mate_dockwidget_base.ui'))


class FilterMateDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()
    launchingTask = pyqtSignal(str)

    gettingProjectLayers = pyqtSignal()
    settingLayerVariable = pyqtSignal(str, tuple)

    reinitializingLayerOnError = pyqtSignal(str)

    def __init__(self, project_layers, plugin_dir, config_data, parent=None):
        """Constructor."""
        super(FilterMateDockWidget, self).__init__(parent)
        
        self.exception = None
        self.iface = iface

        self.plugin_dir = plugin_dir
        self.CONFIG_DATA = config_data
        self.PROJECT_LAYERS = project_layers

        self.current_layer = None
        self.link_legend_layers_and_current_layer_flag = False
        if len(list(self.PROJECT_LAYERS)) > 0:
            self.init_layer = self.iface.activeLayer() if self.iface.activeLayer() != None else list(PROJECT.mapLayers().values())[0]
            self.has_loaded_layers = True
        else:
            self.init_layer = None
            self.has_loaded_layers = False
        self.current_layer_all_features = None

        self.widgets = None
        self.widgets_initialized = False
        self.current_exploring_groupbox = None
        self.tabTools_current_index = 0

        self.predicates = None
        self.buffer_property_has_been_init = False
        self.current_buffer_property_has_been_init = False
        self.project_props = {"exporting":{}}
        self.layer_properties_tuples_dict = None
        self.export_properties_tuples_dict = None
        self.json_template_layer_exporting = '{"has_layers_to_export":false,"layers_to_export":[],"has_projection_to_export":false,"projection_to_export":"","has_styles_to_export":false,"styles_to_export":"","has_datatype_to_export":false,"datatype_to_export":"","datatype_to_export":"","has_output_folder_to_export":false,"output_folder_to_export":"","has_zip_to_export":false,"zip_to_export":"" }'
        self.json_template_layer_filtering = '{"feature_limit": 10000}'

        self.setupUi(self)
        self.manage_configuration_model()
        self.setupUiCustom()
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
               if signal[0] == custom_signal_name and signal[1] != None:
                    current_signal_name = custom_signal_name
                    current_triggered_function = signal[1]
                    state = self.changeSignalState(widget_path, current_signal_name, current_triggered_function, custom_action)

        else:
            for signal in widget_object["SIGNALS"]:
                if signal[1] != None:
                    current_signal_name = str(signal[0])
                    current_triggered_function = signal[1]
                    state = self.changeSignalState(widget_path, current_signal_name, current_triggered_function, custom_action)
        
        if state == None:
            raise SignalStateChangeError(state, widget_path)

        return state
        

        

    def changeSignalState(self, widget_path, current_signal_name, current_triggered_function, custom_action=None):
        state = None

        if isinstance(widget_path, list) and len(widget_path) == 2:
            if hasattr(self.widgets[widget_path[0]][widget_path[1]]["WIDGET"], current_signal_name):
                state = self.widgets[widget_path[0]][widget_path[1]]["WIDGET"].isSignalConnected(self.getSignal(self.widgets[widget_path[0]][widget_path[1]]["WIDGET"], current_signal_name))
                if custom_action != None:
                    if custom_action == 'disconnect' and state == True:
                        getattr(self.widgets[widget_path[0]][widget_path[1]]["WIDGET"], current_signal_name).disconnect()
                    elif custom_action == 'connect' and state == False:
                        getattr(self.widgets[widget_path[0]][widget_path[1]]["WIDGET"], current_signal_name).connect(current_triggered_function)
                else:
                    if state == True:
                        getattr(self.widgets[widget_path[0]][widget_path[1]]["WIDGET"], current_signal_name).disconnect()
                    else:
                        getattr(self.widgets[widget_path[0]][widget_path[1]]["WIDGET"], current_signal_name).connect(current_triggered_function)

                state = self.widgets[widget_path[0]][widget_path[1]]["WIDGET"].isSignalConnected(self.getSignal(self.widgets[widget_path[0]][widget_path[1]]["WIDGET"], current_signal_name))   
                return state
        
        if state == None:
            raise SignalStateChangeError(state, widget_path)




    def setupUiCustom(self):
        self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection = QgsCheckableComboBoxFeaturesListPickerWidget(self)
        self.layout = self.verticalLayout_exploring_multiple_selection
        self.layout.insertWidget(0, self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection)

        self.checkableComboBoxLayer_filtering_layers_to_filter = QgsCheckableComboBoxLayer(self)

        #self.checkableComboBoxLayer_filtering_layers_to_filter.contextMenuEvent()

        self.checkableComboBoxLayer_exporting_layers = QgsCheckableComboBoxLayer(self)

        #self.checkableComboBoxLayer_exporting_layers.contextMenuEvent()

        self.dockwidget_widgets_configuration()


        if 'EXPORT' in self.CONFIG_DATA:
            if len(list(self.CONFIG_DATA["EXPORT"])) > 0 and isinstance(self.CONFIG_DATA["EXPORT"], dict):
                self.project_props['exporting'] = self.CONFIG_DATA["EXPORT"]
            else:
                self.project_props['exporting'] = json.loads(self.json_template_layer_exporting)
        else:
            self.project_props['exporting'] = json.loads(self.json_template_layer_exporting)

        if 'FILTER' in self.CONFIG_DATA:
            if len(list(self.CONFIG_DATA["FILTER"])) > 0 and isinstance(self.CONFIG_DATA["FILTER"], dict):
                self.project_props['filtering'] = self.CONFIG_DATA["FILTER"]
            else:
                self.project_props['filtering'] = json.loads(self.json_template_layer_filtering)
        else:
            self.project_props['filtering'] = json.loads(self.json_template_layer_filtering)

        if 'APP' in self.CONFIG_DATA:
            if len(list(self.CONFIG_DATA["APP"])) > 0 and isinstance(self.CONFIG_DATA["APP"], dict):
                if "LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG" in self.CONFIG_DATA["APP"] and isinstance(self.CONFIG_DATA["APP"]["LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"], bool):
                    self.link_legend_layers_and_current_layer_flag = self.CONFIG_DATA["APP"]["LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"]


        self.layout = self.verticalLayout_filtering_values
        self.layout.insertWidget(3, self.checkableComboBoxLayer_filtering_layers_to_filter)

        self.layout = self.verticalLayout_exporting_values
        self.layout.insertWidget(1, self.checkableComboBoxLayer_exporting_layers)

        #self.custom_identify_tool = CustomIdentifyTool(self.iface)
        self.iface.mapCanvas().setSelectionColor(QColor(237, 97, 62, 75))
        
        


    def dockwidget_widgets_configuration(self):

        self.layer_properties_tuples_dict =   {
                                                "is":(("exploring","is_selecting"),("exploring","is_tracking"),("exploring","is_linking"),("exploring","is_saving")),
                                                "layers_to_filter":(("filtering","has_layers_to_filter"),("filtering","layers_to_filter")),
                                                "combine_operator":(("filtering","has_combine_operator"),("filtering","combine_operator")),
                                                "geometric_predicates":(("filtering","has_geometric_predicates"),("filtering","has_buffer"),("filtering","geometric_predicates"),("filtering","geometric_predicates_operator")),
                                                "buffer":(("filtering","has_buffer"),("filtering","buffer"),("filtering","buffer_property"),("filtering","buffer_expression"))
                                                }
        
        self.export_properties_tuples_dict =   {
                                                "layers_to_export":(("exporting","has_layers_to_export"),("exporting","layers_to_export")),
                                                "projection_to_export":(("exporting","has_projection_to_export"),("exporting","projection_to_export")),
                                                "styles_to_export":(("exporting","has_styles_to_export"),("exporting","styles_to_export")),
                                                "datatype_to_export":(("exporting","has_datatype_to_export"),("exporting","datatype_to_export")),
                                                "output_folder_to_export":(("exporting","has_output_folder_to_export"),("exporting","output_folder_to_export")),
                                                "zip_to_export":(("exporting","has_zip_to_export"),("exporting","zip_to_export"))
                                                }

        self.widgets = {"DOCK":{}, "ACTION":{}, "EXPLORING":{}, "SINGLE_SELECTION":{}, "MULTIPLE_SELECTION":{}, "CUSTOM_SELECTION":{}, "FILTERING":{}, "EXPORTING":{}, "QGIS":{}}
            
        self.widgets["DOCK"] = {
                                "SINGLE_SELECTION":{"TYPE":"GroupBox", "WIDGET":self.mGroupBox_exploring_single_selection, "SIGNALS":[("stateChanged", lambda state, x='single_selection': self.exploring_groupbox_changed(x))]},
                                "MULTIPLE_SELECTION":{"TYPE":"GroupBox","WIDGET":self.mGroupBox_exploring_multiple_selection, "SIGNALS":[("stateChanged", lambda state, x='multiple_selection': self.exploring_groupbox_changed(x))]},
                                "CUSTOM_SELECTION":{"TYPE":"GroupBox","WIDGET":self.mGroupBox_exploring_custom_selection, "SIGNALS":[("stateChanged", lambda state, x='custom_selection': self.exploring_groupbox_changed(x))]},
                                "CONFIGURATION_TREE_VIEW":{"TYPE":"TreeView","WIDGET":self.config_view, "SIGNALS":[("collapsed", None),("expanded", None)]},
                                "CONFIGURATION_MODEL":{"TYPE":"QStandardItemModel","WIDGET":self.config_model, "SIGNALS":[("itemChanged", self.data_changed_configuration_model)]},
                                "TOOLS":{"TYPE":"ToolBox","WIDGET":self.toolBox_tabTools, "SIGNALS":[("currentChanged", self.select_tabTools_index)]}
                                }   

        self.widgets["ACTION"] = {
                                "FILTER":{"TYPE":"PushButton", "WIDGET":self.pushButton_action_filter, "SIGNALS":[("clicked", lambda state, x='filter': self.launchTaskEvent(x))], "ICON":None},
                                "UNFILTER":{"TYPE":"PushButton", "WIDGET":self.pushButton_action_unfilter, "SIGNALS":[("clicked", lambda state, x='unfilter': self.launchTaskEvent(x))], "ICON":None},
                                "RESET":{"TYPE":"PushButton", "WIDGET":self.pushButton_action_reset, "SIGNALS":[("clicked", lambda state, x='reset': self.launchTaskEvent(x))], "ICON":None},
                                "EXPORT":{"TYPE":"PushButton", "WIDGET":self.pushButton_action_export, "SIGNALS":[("clicked", lambda state, x='export': self.launchTaskEvent(x))], "ICON":None}
                                }        

        self.widgets["SINGLE_SELECTION"] = {
                                            "FEATURES":{"TYPE":"FeatureComboBox", "WIDGET":self.mFeaturePickerWidget_exploring_single_selection, "SIGNALS":[("featureChanged", self.exploring_features_changed),("filterExpressionChanged", self.exploring_source_params_changed)]},
                                            "EXPRESSION":{"TYPE":"ComboBox", "WIDGET":self.mFieldExpressionWidget_exploring_single_selection, "SIGNALS":[("fieldChanged", self.exploring_source_params_changed)]}
                                            }
        
        self.widgets["MULTIPLE_SELECTION"] = {
                                            "FEATURES":{"TYPE":"CustomCheckableFeatureComboBox", "WIDGET":self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection, "SIGNALS":[("updatingCheckedItemList", self.exploring_features_changed),("filteringCheckedItemList", self.exploring_source_params_changed)]},
                                            "EXPRESSION":{"TYPE":"ComboBox", "WIDGET":self.mFieldExpressionWidget_exploring_multiple_selection, "SIGNALS":[("fieldChanged", self.exploring_source_params_changed)]}
                                            }
        
        self.widgets["CUSTOM_SELECTION"] = {
                                            "EXPRESSION":{"TYPE":"ComboBox", "WIDGET":self.mFieldExpressionWidget_exploring_custom_selection, "SIGNALS":[("fieldChanged", self.exploring_source_params_changed)]}
                                            }


        self.widgets["EXPLORING"] = {
                                    "IDENTIFY":{"TYPE":"PushButton", "WIDGET":self.pushButton_exploring_identify, "SIGNALS":[("clicked", self.exploring_identify_clicked)], "ICON":None},
                                    "ZOOM":{"TYPE":"PushButton", "WIDGET":self.pushButton_exploring_zoom, "SIGNALS":[("clicked", self.exploring_zoom_clicked)], "ICON":None},
                                    "IS_SELECTING":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exploring_selecting, "SIGNALS":[("clicked", lambda state, x='is_selecting', custom_functions={"ON_TRUE": lambda x: self.exploring_source_params_changed(), "ON_FALSE": lambda x: self.exploring_deselect_features()}: self.layer_property_changed(x, state, custom_functions))], "ICON":None},
                                    "IS_TRACKING":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exploring_tracking, "SIGNALS":[("clicked", lambda state, x='is_tracking', custom_functions={"ON_TRUE": lambda x: self.exploring_source_params_changed()}: self.layer_property_changed(x, state, custom_functions))], "ICON":None},
                                    "IS_LINKING":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exploring_linking_widgets, "SIGNALS":[("clicked", lambda state, x='is_linking', custom_functions={"ON_CHANGE": lambda x: self.exploring_source_params_changed()}: self.layer_property_changed(x, state, custom_functions))], "ICON":None},
                                    "IS_SAVING":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exploring_saving_parameters, "SIGNALS":[("clicked", lambda state, x='is_saving', custom_functions={"ON_TRUE": lambda x: self.exploring_source_params_changed(), "ON_FALSE": lambda x : self.reinitializeLayerOnErrorEvent()}: self.layer_property_changed(x, state, custom_functions))], "ICON":None}
                                    }


        self.widgets["FILTERING"] = {
                                    "AUTO_CURRENT_LAYER":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_filtering_auto_current_layer, "SIGNALS":[("clicked", lambda state: self.filtering_auto_current_layer_changed(state))], "ICON":None},
                                    "HAS_LAYERS_TO_FILTER":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_filtering_layers_to_filter, "SIGNALS":[("clicked", lambda state, x='has_layers_to_filter': self.layer_property_changed(x, state))], "ICON":None},
                                    "HAS_COMBINE_OPERATOR":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_filtering_current_layer_combine_operator, "SIGNALS":[("clicked", lambda state, x='has_combine_operator': self.layer_property_changed(x, state))], "ICON":None},
                                    "HAS_GEOMETRIC_PREDICATES":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_filtering_geometric_predicates, "SIGNALS":[("clicked", lambda state, x='has_geometric_predicates': self.layer_property_changed(x, state))], "ICON":None},
                                    "HAS_BUFFER":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_filtering_buffer, "SIGNALS":[("clicked", lambda state, x='has_buffer': self.layer_property_changed(x, state))], "ICON":None},
                                    "CURRENT_LAYER":{"TYPE":"ComboBox", "WIDGET":self.comboBox_filtering_current_layer, "SIGNALS":[("layerChanged", self.current_layer_changed)]},
                                    "LAYERS_TO_FILTER":{"TYPE":"CustomCheckableLayerComboBox", "WIDGET":self.checkableComboBoxLayer_filtering_layers_to_filter, "CUSTOM_LOAD_FUNCTION": lambda x: self.get_layers_to_filter(), "SIGNALS":[("checkedItemsChanged", lambda state, custom_functions={"CUSTOM_DATA": lambda x: self.get_layers_to_filter()}, x='layers_to_filter': self.layer_property_changed(x, state, custom_functions))]},
                                    "COMBINE_OPERATOR":{"TYPE":"ComboBox", "WIDGET":self.comboBox_filtering_current_layer_combine_operator, "SIGNALS":[("currentTextChanged", lambda state, x='combine_operator': self.layer_property_changed(x, state))]},
                                    "GEOMETRIC_PREDICATES":{"TYPE":"CheckableComboBox", "WIDGET":self.comboBox_filtering_geometric_predicates, "SIGNALS":[("checkedItemsChanged", lambda state, x='geometric_predicates': self.layer_property_changed(x, state))]},
                                    "GEOMETRIC_PREDICATES_OPERATOR":{"TYPE":"ComboBox", "WIDGET":self.comboBox_filtering_geometric_predicates_operator, "SIGNALS":[("currentTextChanged", lambda state, x='geometric_predicates_operator': self.layer_property_changed(x, state))]},
                                    "BUFFER":{"TYPE":"QgsDoubleSpinBox", "WIDGET":self.mQgsDoubleSpinBox_filtering_buffer, "SIGNALS":[("valueChanged", lambda state, x='buffer': self.layer_property_changed(x, state))]},
                                    "BUFFER_PROPERTY":{"TYPE":"PropertyOverrideButton", "WIDGET":self.mPropertyOverrideButton_filtering_buffer_property, "SIGNALS":[("activated", lambda state, x='buffer_property', custom_functions={"ON_CHANGE": lambda x: self.filtering_buffer_property_changed()}: self.layer_property_changed(x, state, custom_functions))]},
                                    "BUFFER_EXPRESSION":{"TYPE":"LineEdit", "WIDGET":self.lineEdit_filtering_buffer_expression, "SIGNALS":[("textEdited", lambda state, x='buffer_expression', custom_functions={"ON_CHANGE": lambda x: self.filtering_buffer_expression_edited()}: self.layer_property_changed(x, state, custom_functions)),("textChanged", lambda state, x='buffer_expression': self.layer_property_changed(x, state))]}
                                    }
        
        self.widgets["EXPORTING"] = {
                                    "HAS_LAYERS_TO_EXPORT":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_layers, "SIGNALS":[("clicked", lambda state, x='has_layers_to_export': self.project_property_changed(x, state))], "ICON":None},
                                    "HAS_PROJECTION_TO_EXPORT":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_projection, "SIGNALS":[("clicked", lambda state, x='has_projection_to_export': self.project_property_changed(x, state))], "ICON":None},
                                    "HAS_STYLES_TO_EXPORT":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_styles, "SIGNALS":[("clicked", lambda state, x='has_styles_to_export': self.project_property_changed(x, state))], "ICON":None},
                                    "HAS_DATATYPE_TO_EXPORT":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_datatype, "SIGNALS":[("clicked", lambda state, x='has_datatype_to_export': self.project_property_changed(x, state))], "ICON":None},
                                    "HAS_OUTPUT_FOLDER_TO_EXPORT":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_output_folder, "SIGNALS":[("clicked", lambda state, x='has_output_folder_to_export', custom_functions={"ON_CHANGE": lambda x: self.dialog_export_output_path()}: self.project_property_changed(x, state, custom_functions))], "ICON":None},
                                    "HAS_ZIP_TO_EXPORT":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_zip, "SIGNALS":[("clicked", lambda state, x='has_zip_to_export', custom_functions={"ON_CHANGE": lambda x: self.dialog_export_output_pathzip()}: self.project_property_changed(x, state, custom_functions))], "ICON":None},
                                    "LAYERS_TO_EXPORT":{"TYPE":"CustomCheckableLayerComboBox", "WIDGET":self.checkableComboBoxLayer_exporting_layers, "SIGNALS":[("checkedItemsChanged", lambda state, x='layers_to_export': self.project_property_changed(x, state))]},
                                    "PROJECTION_TO_EXPORT":{"TYPE":"QgsProjectionSelectionWidget", "WIDGET":self.mQgsProjectionSelectionWidget_exporting_projection, "SIGNALS":[("crsChanged", lambda state, x='projection_to_export', custom_functions={"CUSTOM_DATA": lambda x: self.get_current_crs_authid()}: self.project_property_changed(x, state, custom_functions))]},
                                    "STYLES_TO_EXPORT":{"TYPE":"ComboBox", "WIDGET":self.comboBox_exporting_styles, "SIGNALS":[("currentTextChanged", lambda state, x='styles_to_export': self.project_property_changed(x, state))]},
                                    "DATATYPE_TO_EXPORT":{"TYPE":"ComboBox", "WIDGET":self.comboBox_exporting_datatype, "SIGNALS":[("currentTextChanged", lambda state, x='datatype_to_export': self.project_property_changed(x, state))]},
                                    "OUTPUT_FOLDER_TO_EXPORT":{"TYPE":"LineEdit", "WIDGET":self.lineEdit_exporting_output_folder, "SIGNALS":[("textEdited", lambda state, x='output_folder_to_export', custom_functions={"ON_CHANGE": lambda x: self.reset_export_output_path()}: self.project_property_changed(x, state, custom_functions))]},
                                    "ZIP_TO_EXPORT":{"TYPE":"LineEdit", "WIDGET":self.lineEdit_exporting_zip, "SIGNALS":[("textEdited", lambda state, x='zip_to_export', custom_functions={"ON_CHANGE": lambda x: self.reset_export_output_pathzip()}: self.project_property_changed(x, state, custom_functions))]}
                                    }
            

    
        self.widgets["QGIS"] = {
                                "LAYER_TREE_VIEW":{"TYPE":"TreeView", "WIDGET":self.iface.layerTreeView(), "SIGNALS":[("currentLayerChanged", self.current_layer_changed)]}
                                }
        
        self.widgets_initialized = True

    def data_changed_configuration_model(self, input_data=None):

        if self.widgets_initialized is True:

            print('data_changed_configuration_model', input_data)
            index = input_data.index()
            item = input_data

            item_key = self.config_view.model.itemFromIndex(index.siblingAtColumn(0))

            items_keys_values_path = []

            while item_key != None:
                items_keys_values_path.append(item_key.data(QtCore.Qt.DisplayRole))
                item_key = item_key.parent()

            items_keys_values_path.reverse()

            if 'ICONS' in items_keys_values_path:
                self.set_widget_icon(items_keys_values_path)

            self.save_configuration_model()



    def reload_configuration_model(self):

        if self.widgets_initialized is True:

            self.config_model = JsonModel(data=self.CONFIG_DATA, editable_keys=True, editable_values=True, plugin_dir=self.plugin_dir)
            self.config_view.setModel(self.config_model)
            json_object = json.dumps(self.CONFIG_DATA, indent=4)

            with open(self.plugin_dir + '/config/config.json', 'w') as outfile:
                outfile.write(json_object)


    def save_configuration_model(self):

        if self.widgets_initialized is True:

            self.CONFIG_DATA = self.config_model.serialize()
            json_object = json.dumps(self.CONFIG_DATA, indent=4)

            print('save_configuration_model')

            with open(self.plugin_dir + '/config/config.json', 'w') as outfile:
                outfile.write(json_object)


    def manage_configuration_model(self):
        """Manage the qtreeview model configuration"""

        self.config_model = JsonModel(data=self.CONFIG_DATA, editable_keys=True, editable_values=True, plugin_dir=self.plugin_dir)


        self.config_view = JsonView(self.config_model, self.plugin_dir)
        self.CONFIGURATION.layout().addWidget(self.config_view)

        self.config_view.setModel(self.config_model)

        self.config_view.setStyleSheet("""padding:0px;
                                    color:black;""")

        self.config_view.setAnimated(True)
        self.config_view.viewport().setAcceptDrops(True)
        self.config_view.setDragDropMode(QAbstractItemView.DropOnly)
        self.config_view.setDropIndicatorShown(True)
        self.config_view.show()


        
    def manage_output_name(self):
        self.output_name = 'export'
        self.current_project_title = PROJECT.fileName().split('.')[0]
        self.current_project_path = PROJECT.homePath()
        if self.current_project_title is not None:
            self.output_name = 'export' + '_' + str(self.current_project_title)


    def set_widget_icon(self, config_widget_path):

        if self.widgets_initialized is True:

            if len(config_widget_path) == 5:
                file = self.CONFIG_DATA[config_widget_path[0]][config_widget_path[1]][config_widget_path[2]][config_widget_path[3]][config_widget_path[4]]
                file_path = os.path.join(self.plugin_dir, "icons", file)
                icon = QtGui.QIcon(file_path)
                self.widgets[config_widget_path[3]][config_widget_path[4]]["ICON"] = file_path
                self.widgets[config_widget_path[3]][config_widget_path[4]]["WIDGET"].setIcon(icon)


    def icon_per_geometry_type(self, geometry_type):

        if geometry_type == 'GeometryType.Line':
            return QgsLayerItem.iconLine()
        elif geometry_type == 'GeometryType.Point':
            return QgsLayerItem.iconPoint()
        elif geometry_type == 'GeometryType.Polygon':
            return QgsLayerItem.iconPolygon()
        elif geometry_type == 'GeometryType.UnknownGeometry':
            return QgsLayerItem.iconTable()
        else:
            return QgsLayerItem.iconDefault()
        
    def filtering_populate_predicates_chekableCombobox(self):

        self.predicates = ["Intersect","Contain","Disjoint","Equal","Touch","Overlap","Are within","Cross"]
        self.widgets["FILTERING"]["GEOMETRIC_PREDICATES"]["WIDGET"].clear()
        self.widgets["FILTERING"]["GEOMETRIC_PREDICATES"]["WIDGET"].addItems(self.predicates)


    def filtering_populate_layers_chekableCombobox(self, layer=None):


        if self.widgets_initialized is True:

            if layer == None:
                layer = self.current_layer
            else:
                assert isinstance(layer, QgsVectorLayer)
            try:    
                self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].clear()
                layer_props = self.PROJECT_LAYERS[layer.id()]

                if layer_props["filtering"]["has_layers_to_filter"] == True:
                    i = 0
                    
                    for key in self.PROJECT_LAYERS:
                        if self.PROJECT_LAYERS[key]["infos"]["is_already_subset"] is False:
                            self.PROJECT_LAYERS[key]["infos"]["subset_history"] = []

                        layer_id = self.PROJECT_LAYERS[key]["infos"]["layer_id"]
                        layer_name = self.PROJECT_LAYERS[key]["infos"]["layer_name"]
                        layer_crs_authid = self.PROJECT_LAYERS[key]["infos"]["layer_crs_authid"]
                        layer_icon = self.icon_per_geometry_type(self.PROJECT_LAYERS[key]["infos"]["layer_geometry_type"])

                        if key != layer.id():
                            self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].addItem(layer_icon, layer_name + ' [%s]' % (layer_crs_authid), json.dumps(self.PROJECT_LAYERS[key]["infos"]))
                            item = self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].model().item(i)
                            if len(layer_props["filtering"]["layers_to_filter"]) > 0:
                                if layer_id in list(layer_info["layer_id"] for layer_info in list(layer_props["filtering"]["layers_to_filter"])):
                                    item.setCheckState(Qt.Checked)
                                else:
                                    item.setCheckState(Qt.Unchecked) 
                            else:
                                item.setCheckState(Qt.Unchecked)
                            i += 1    
                else:
                    i = 0
                    for key in self.PROJECT_LAYERS:
                        layer_id = self.PROJECT_LAYERS[key]["infos"]["layer_id"]
                        layer_name = self.PROJECT_LAYERS[key]["infos"]["layer_name"]
                        layer_crs_authid = self.PROJECT_LAYERS[key]["infos"]["layer_crs_authid"]
                        layer_icon = self.icon_per_geometry_type(self.PROJECT_LAYERS[key]["infos"]["layer_geometry_type"])
                        
                        if key != layer.id():
                            self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].addItem(layer_icon, layer_name + ' [%s]' % (layer_crs_authid), self.PROJECT_LAYERS[key]["infos"])
                            item = self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].model().item(i)
                            item.setCheckState(Qt.Unchecked)
                            i += 1    
            
            except Exception as e:
                self.exception = e
                print(self.exception)
                self.reinitializeLayerOnErrorEvent()

    def exporting_populate_combobox(self):

        if self.widgets_initialized is True and self.has_loaded_layers is True:

            layers_to_export = []
            datatype_to_export = ''

            if self.project_props['exporting']['has_layers_to_export'] is True:
                layers_to_export = self.project_props['exporting']['layers_to_export']

            if self.project_props['exporting']['has_layers_to_export'] is True:
                datatype_to_export = self.project_props['exporting']['datatype_to_export']


            self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].clear()
            for i, key in enumerate(self.PROJECT_LAYERS):
                layer_name = self.PROJECT_LAYERS[key]["infos"]["layer_name"]
                layer_crs_authid = self.PROJECT_LAYERS[key]["infos"]["layer_crs_authid"]
                layer_icon = self.icon_per_geometry_type(self.PROJECT_LAYERS[key]["infos"]["layer_geometry_type"])
                layer_name = layer_name + ' [%s]' % (layer_crs_authid)
                self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].addItem(layer_icon, layer_name, json.dumps(self.PROJECT_LAYERS[key]["infos"]))
                item = self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].model().item(i)
                if layer_name in layers_to_export:
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
            
            ogr_driver_list = [ogr.GetDriver(i).GetDescription() for i in range(ogr.GetDriverCount())]
            ogr_driver_list.sort()
            self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"].clear()
            self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"].addItems(ogr_driver_list)

            if datatype_to_export != '':
                self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"].setCurrentIndex(self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"].findText(datatype_to_export))
            else:
                self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"].setCurrentIndex(self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"].findText('GPKG'))


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
                        QgsCheckableComboBoxLayer
                        {
                        background-color:{color_1};
                        border: 1px solid {color_1};
                        border-radius: 3px;
                        padding: 3px 3px 3px 3px;
                        color:{color_3};
                        }
                        QgsCheckableComboBoxLayer:hover
                        {
                        border: 2px solid {color_3};
                        }
                        QgsCheckableComboBoxLayer QAbstractItemView {
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
        
        expressionBuilder_style = """QgsExpressionBuilderWidget
                            {
                            background-color: {color_1};
                            border-color: rgb(0, 0, 0);
                            border-radius:6px;
                            padding: 10px 10px 10px 10px;
                            color:{color_3}
                            }"""

        
        frame_style =    """QFrame
                            {
                            background-color: {color_1};
                            border-color: rgb(0, 0, 0);
                            border-radius:6px;
                            padding: 5px 5px 5px 5px;
                            marging: 5px 5px 5px 5px;
                            color:{color_3}
                            }
                            QgsExpressionBuilderWidget
                            {
                            background-color: {color_1};
                            border-color: rgb(0, 0, 0);
                            border-radius:6px;
                            padding: 10px 10px 10px 10px;
                            color:{color_3}
                            }"""

        collapsibleGroupBox_style =  """QgsCollapsibleGroupBox
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
        
        pushBarMessage_style =  """QFrame QFrame {
                                    min-height: 70px;
                                    margin:0px;
                                    padding:0px;
                                    }
                                    QLineEdit {
                                    border: 1px solid gray;
                                    border-radius: 1px;
                                    padding: 0 8px;
                                        selection-background-color: darkgray;
                                        border-color: darkgray
                                    }
                                    QTextEdit, QListView {
                                        border: 1px solid gray;
                                        height:40px;
                                    }"""

        splitter_style = """QSplitter::handle {
                            background: {color_1};
                            }
                            QSplitter::handle:hover {
                            background: {color_2};
                            }"""

        comboBox_style = comboBox_style.replace("{color_1}",self.CONFIG_DATA['DOCKWIDGET']['COLORS']["BACKGROUND"][1]).replace("{color_2}",self.CONFIG_DATA['DOCKWIDGET']['COLORS']["BACKGROUND"][2]).replace("{color_3}",self.CONFIG_DATA['DOCKWIDGET']['COLORS']["FONT"][1])

        dock_style = dock_style.replace("{color}",self.CONFIG_DATA['DOCKWIDGET']['COLORS']["BACKGROUND"][1])

        frame_actions_style = frame_style.replace("{color_1}",self.CONFIG_DATA['DOCKWIDGET']['COLORS']["BACKGROUND"][0]).replace("{color_3}",self.CONFIG_DATA['DOCKWIDGET']['COLORS']["FONT"][1])

        frame_style = frame_style.replace("{color_1}",self.CONFIG_DATA['DOCKWIDGET']['COLORS']["BACKGROUND"][0]).replace("{color_3}",self.CONFIG_DATA['DOCKWIDGET']['COLORS']["FONT"][1])
        
        collapsibleGroupBox_style = collapsibleGroupBox_style.replace("{color_1}",self.CONFIG_DATA['DOCKWIDGET']['COLORS']["BACKGROUND"][0]).replace("{color_3}",self.CONFIG_DATA['DOCKWIDGET']['COLORS']["FONT"][1])

        lineEdit_style = lineEdit_style.replace("{color_1}",self.CONFIG_DATA['DOCKWIDGET']['COLORS']["FONT"][1]).replace("{color_2}",self.CONFIG_DATA['DOCKWIDGET']['COLORS']["BACKGROUND"][1])

        splitter_style = splitter_style.replace("{color_1}", self.CONFIG_DATA['DOCKWIDGET']['COLORS']["BACKGROUND"][1]).replace("{color_2}", self.CONFIG_DATA['DOCKWIDGET']['COLORS']["BACKGROUND"][3])

        
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

        self.widgets["DOCK"]["TOOLS"]["WIDGET"].setStyleSheet("""background-color: {};
                                                        border-color: rgb(0, 0, 0);
                                                        border-radius:6px;
                                                        padding: 10px 10px 10px 10px;
                                                        color:{};""".format(self.CONFIG_DATA['DOCKWIDGET']['COLORS']["BACKGROUND"][0],self.CONFIG_DATA['DOCKWIDGET']['COLORS']["FONT"][0]))
        
        self.splitter.setStyleSheet(splitter_style)
        self.frame_actions.setStyleSheet(frame_actions_style)
        self.frame_exploring.setStyleSheet(frame_style)
        self.frame_toolset.setStyleSheet(frame_style)

        self.mGroupBox_exploring_single_selection.setStyleSheet(collapsibleGroupBox_style)
        self.mGroupBox_exploring_multiple_selection.setStyleSheet(collapsibleGroupBox_style)
        self.mGroupBox_exploring_custom_selection.setStyleSheet(collapsibleGroupBox_style)


        self.CONFIGURATION.setStyleSheet("""background-color: {};
                                            border-color: rgb(0, 0, 0);
                                            border-radius:6px;
                                            marging: 25px 10px 10px 10px;
                                            color:{};""".format(self.CONFIG_DATA['DOCKWIDGET']['COLORS']["BACKGROUND"][0],self.CONFIG_DATA['DOCKWIDGET']['COLORS']["FONT"][0]))
        
        

        pushButton_config_path = ['DOCKWIDGET', 'PushButton']
        pushButton_style = json.dumps(self.CONFIG_DATA[pushButton_config_path[0]][pushButton_config_path[1]]["STYLE"])[1:-1].replace(': {', ' {').replace('\"', '').replace(',', '')
        

        for widget_group in self.widgets:
            for widget_name in self.widgets[widget_group]:
                if self.widgets[widget_group][widget_name]["TYPE"] == "PushButton":
                    self.set_widget_icon(pushButton_config_path + ["ICONS", widget_group, widget_name])
                    self.widgets[widget_group][widget_name]["WIDGET"].setStyleSheet(pushButton_style)
                elif self.widgets[widget_group][widget_name]["TYPE"].find("ComboBox") >= 0:
                    self.widgets[widget_group][widget_name]["WIDGET"].setStyleSheet(comboBox_style)
                elif self.widgets[widget_group][widget_name]["TYPE"].find("LineEdit") >= 0:
                    self.widgets[widget_group][widget_name]["WIDGET"].setStyleSheet(lineEdit_style)
                elif self.widgets[widget_group][widget_name]["TYPE"].find("PropertyOverrideButton") >= 0:
                    self.widgets[widget_group][widget_name]["WIDGET"].setStyleSheet(lineEdit_style)
                elif self.widgets[widget_group][widget_name]["TYPE"].find("QgsProjectionSelectionWidget") >= 0:
                    self.widgets[widget_group][widget_name]["WIDGET"].setStyleSheet(comboBox_style)
                

    def set_widgets_enabled_state(self, state):
        for widget_group in self.widgets:
            for widget_name in self.widgets[widget_group]:
                if self.widgets[widget_group][widget_name]["TYPE"] in ("PushButton","ComboBox","CheckableComboBox","CustomCheckableLayerComboBox","CustomCheckableFeatureComboBox","FeatureComboBox","LineEdit","QgsProjectionSelectionWidget","QgsDoubleSpinBox"):
                    self.widgets[widget_group][widget_name]["WIDGET"].setEnabled(state)


    def connect_widgets_signals(self):
        """SET INTERACTIONS"""
        for widget_group in self.widgets:
            if widget_group != 'QGIS':
                for widget in self.widgets[widget_group]:
                    if widget_group != 'DOCK':
                        self.manageSignal([widget_group, widget], 'connect')


    def disconnect_widgets_signals(self):
        """SET INTERACTIONS"""
        for widget_group in self.widgets:
            if widget_group != 'QGIS':
                for widget in self.widgets[widget_group]:
                    if widget_group != 'DOCK':
                        self.manageSignal([widget_group, widget], 'disconnect')


    def manage_interactions(self):



        """INIT"""

        self.coordinateReferenceSystem = QgsCoordinateReferenceSystem()
        self.widgets["FILTERING"]["BUFFER"]["WIDGET"].setExpressionsEnabled(True)
        self.widgets["FILTERING"]["BUFFER"]["WIDGET"].setClearValue(0.0)
        self.widgets["EXPORTING"]["PROJECTION_TO_EXPORT"]["WIDGET"].setCrs(PROJECT.crs())
        self.set_widgets_enabled_state(self.has_loaded_layers)
        self.filtering_populate_predicates_chekableCombobox()    

        if self.has_loaded_layers is True:
            self.connect_widgets_signals()


        self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].clicked.connect(lambda state, x='single_selection': self.exploring_groupbox_changed(x))
        self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].clicked.connect(lambda state, x='multiple_selection': self.exploring_groupbox_changed(x))
        self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].clicked.connect(lambda state, x='custom_selection': self.exploring_groupbox_changed(x))
        self.widgets["DOCK"]["TOOLS"]["WIDGET"].currentChanged.connect(self.select_tabTools_index)
        self.widgets["DOCK"]["CONFIGURATION_MODEL"]["WIDGET"].itemChanged.connect(self.data_changed_configuration_model)
        self.widgets["DOCK"]["CONFIGURATION_MODEL"]["WIDGET"].dataChanged.connect(self.save_configuration_model)
        self.widgets["DOCK"]["CONFIGURATION_MODEL"]["WIDGET"].rowsInserted.connect(self.save_configuration_model)
        self.widgets["DOCK"]["CONFIGURATION_MODEL"]["WIDGET"].rowsRemoved.connect(self.save_configuration_model)
        
        # self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].contextMenuEvent
        # self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].contextMenuEvent


        if self.init_layer != None and isinstance(self.init_layer, QgsVectorLayer):
            self.exporting_populate_combobox()
            self.set_exporting_properties()
            self.current_layer_changed(self.init_layer)
            self.filtering_auto_current_layer_changed()

            
    def select_tabTools_index(self, i):
        
        if self.widgets_initialized is True:

            self.tabTools_current_index = i
            if self.tabTools_current_index == 1:
                self.widgets["ACTION"]["EXPORT"]["WIDGET"].setEnabled(True)
            else:
                self.widgets["ACTION"]["EXPORT"]["WIDGET"].setEnabled(False)

            self.set_exporting_properties()


    def exploring_groupbox_init(self):

        if self.widgets_initialized is True:

            if self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].isChecked() is True or self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].isCollapsed() is False:
                exploring_groupbox = "single_selection"

            elif self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].isChecked() is True or self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].isCollapsed() is False:
                exploring_groupbox = "multiple_selection"  

            elif self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].isChecked() is True or self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].isCollapsed() is False:
                exploring_groupbox = "custom_selection"

            self.exploring_groupbox_changed(exploring_groupbox)

    def exploring_groupbox_changed(self, groupbox):
        
        if self.widgets_initialized is True:

            if groupbox == "single_selection":
    
                if self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].isChecked() is True or self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].isCollapsed() is False:

                    self.current_exploring_groupbox = "single_selection"

                    self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setChecked(True)
                    self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setCollapsed(False)

                    self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setChecked(False)
                    self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setCollapsed(True)

                    self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setChecked(False)
                    self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setCollapsed(True)
                    

                    if self.current_layer != None:
                        self.manageSignal(["SINGLE_SELECTION","FEATURES"], 'connect', 'featureChanged')
                        self.manageSignal(["MULTIPLE_SELECTION","FEATURES"], 'disconnect', 'updatingCheckedItemList')

                        self.widgets["SINGLE_SELECTION"]["FEATURES"]["WIDGET"].setEnabled(True)
                        self.widgets["SINGLE_SELECTION"]["EXPRESSION"]["WIDGET"].setEnabled(True)

                        self.exploring_features_changed(self.widgets["SINGLE_SELECTION"]["FEATURES"]["WIDGET"].feature())



            elif groupbox == "multiple_selection":

                if self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].isChecked() is True or self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].isCollapsed() is False:
                    
                    self.current_exploring_groupbox = "multiple_selection"



                    self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setChecked(True)
                    self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setCollapsed(False)

                    self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setChecked(False)
                    self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setCollapsed(True)

                    self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setChecked(False)
                    self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setCollapsed(True)



                    if self.current_layer != None:
                        self.manageSignal(["SINGLE_SELECTION","FEATURES"], 'disconnect', 'featureChanged')
                        self.manageSignal(["MULTIPLE_SELECTION","FEATURES"], 'connect', 'updatingCheckedItemList')

                        self.widgets["MULTIPLE_SELECTION"]["FEATURES"]["WIDGET"].setEnabled(True)
                        self.widgets["MULTIPLE_SELECTION"]["EXPRESSION"]["WIDGET"].setEnabled(True)

                        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
                        self.widgets["MULTIPLE_SELECTION"]["FEATURES"]["WIDGET"].setLayer(self.current_layer, layer_props)

                        self.exploring_features_changed(self.widgets["MULTIPLE_SELECTION"]["FEATURES"]["WIDGET"].currentSelectedFeatures(), True)


            elif groupbox == "custom_selection":

                if self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].isChecked() is True or self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].isCollapsed() is False:
                    
                    self.current_exploring_groupbox = "custom_selection"
                    
                    self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setChecked(True)
                    self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setCollapsed(False)

                    self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setChecked(False)
                    self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setCollapsed(True)

                    self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setChecked(False)
                    self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setCollapsed(True)



                    if self.current_layer != None:
                        self.manageSignal(["SINGLE_SELECTION","FEATURES"], 'disconnect', 'featureChanged')
                        self.manageSignal(["MULTIPLE_SELECTION","FEATURES"], 'disconnect', 'updatingCheckedItemList')

                        self.widgets["CUSTOM_SELECTION"]["EXPRESSION"]["WIDGET"].setEnabled(True)
                        self.exploring_custom_selection()


    def exploring_identify_clicked(self):

        features = []
        expression = None

        if self.widgets_initialized is True and self.current_layer != None:

            if self.current_exploring_groupbox == "single_selection":
                input = self.widgets["SINGLE_SELECTION"]["FEATURES"]["WIDGET"].feature()
                features, expression = self.get_exploring_features(input, True)

            elif self.current_exploring_groupbox == "multiple_selection":
                input = self.widgets["MULTIPLE_SELECTION"]["FEATURES"]["WIDGET"].checkedItems()
                features, expression = self.get_exploring_features(input, True)

            elif self.current_exploring_groupbox == "custom_selection":
                features, expression = self.exploring_custom_selection()
            
            if len(features) == 0:
                return
            else:
                self.iface.mapCanvas().flashFeatureIds(self.current_layer, [feature.id() for feature in features], startColor=QColor(235, 49, 42, 255), endColor=QColor(237, 97, 62, 25), flashes=6, duration=400)


    def exploring_zoom_clicked(self):

        if self.widgets_initialized is True and self.current_layer != None:

            features, expression = self.get_current_features()
            
            if len(features) == 0:
                return
            else:
                self.zooming_to_features(features)


    def zooming_to_features(self, features):
        
        if self.widgets_initialized is True and self.current_layer != None:

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



    def exploring_source_params_changed(self, expression=None):

        if self.widgets_initialized is True and self.current_layer != None:

            layer_props = self.PROJECT_LAYERS[self.current_layer.id()] 
            flag_value_changed = False

            if self.current_exploring_groupbox == "single_selection":

                if expression != None:
                    layer_props["exploring"]["single_selection_expression"] = expression
                    self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["single_selection_expression"] = layer_props["exploring"]["single_selection_expression"]
                    self.widgets["SINGLE_SELECTION"]["FEATURES"]["WIDGET"].setDisplayExpression(expression)

            elif self.current_exploring_groupbox == "multiple_selection":

                if expression != None:  
                    layer_props["exploring"]["multiple_selection_expression"] = expression   
                    self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["multiple_selection_expression"] = layer_props["exploring"]["multiple_selection_expression"]
                
                self.widgets["MULTIPLE_SELECTION"]["FEATURES"]["WIDGET"].setLayer(self.current_layer, layer_props)
                self.exploring_link_widgets()

            elif self.current_exploring_groupbox == "custom_selection":

                if expression != None:
                    layer_props["exploring"]["custom_selection_expression"] = expression 
                    self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["custom_selection_expression"] = layer_props["exploring"]["custom_selection_expression"]
                    self.exploring_link_widgets(expression)

            self.get_current_features()

 


    def exploring_custom_selection(self):

        if self.widgets_initialized is True and self.current_layer != None:

            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
            expression = layer_props["exploring"]["custom_selection_expression"]
            features = []
            if QgsExpression(expression).isField() is False:
                features = self.exploring_features_changed([], False, expression)
            elif self.current_layer_all_features == None:
                features_iterator = self.current_layer.getFeatures()
                done_looping = False
                
                while not done_looping:
                    try:
                        feature = next(features_iterator)
                        features.append(feature)
                    except StopIteration:
                        done_looping = True
                self.current_layer_all_features = features
            else:
                features = self.current_layer_all_features

            return features, expression
    

    def exploring_deselect_features(self):

        if self.widgets_initialized is True and self.current_layer != None:

            if self.current_layer == None:
                return
            
            self.current_layer.removeSelection()
        

    def get_current_features(self):

        if self.widgets_initialized is True and self.current_layer != None:

            features = []    
            expression = ''

            if self.current_exploring_groupbox == "single_selection":
                input = self.widgets["SINGLE_SELECTION"]["FEATURES"]["WIDGET"].feature()
                features, expression = self.get_exploring_features(input, True)

            elif self.current_exploring_groupbox == "multiple_selection":
                input = self.widgets["MULTIPLE_SELECTION"]["FEATURES"]["WIDGET"].checkedItems()
                features, expression = self.get_exploring_features(input, True)

            elif self.current_exploring_groupbox == "custom_selection":
                features, expression = self.exploring_custom_selection()
                
            return features, expression
    
    def exploring_features_changed(self, input, identify_by_primary_key_name=False, custom_expression=None):

        if self.widgets_initialized is True and self.current_layer != None:
            
            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
            features, expression = self.get_exploring_features(input, identify_by_primary_key_name, custom_expression)

            if self.current_exploring_groupbox == 'multiple_selection':
                self.exploring_link_widgets()

            self.current_layer.removeSelection()

            if len(features) == 0:
                return features
        
            if layer_props["exploring"]["is_selecting"] == True:
                self.current_layer.removeSelection()
                self.current_layer.select([feature.id() for feature in features])

            if layer_props["exploring"]["is_tracking"] == True:
                self.zooming_to_features(features)  

            return features


    def get_exploring_features(self, input, identify_by_primary_key_name=False, custom_expression=None):

        if self.widgets_initialized is True and self.current_layer != None:

            if self.current_layer == None:
                return
            
            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
            features = []
            expression = None

            if isinstance(input, QgsFeature):
                if identify_by_primary_key_name is True:
                    if layer_props["infos"]["primary_key_is_numeric"] is True: 
                        expression = layer_props["infos"]["primary_key_name"] + " = {}".format(input[layer_props["infos"]["primary_key_name"]])
                    else:
                        expression = layer_props["infos"]["primary_key_name"] + " = '{}'".format(input[layer_props["infos"]["primary_key_name"]])
                else:
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
        
    
    def exploring_link_widgets(self, expression=None):

        if self.widgets_initialized is True and self.current_layer != None:

            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
            custom_filter = None

            if layer_props["exploring"]["is_linking"] == True:
                if QgsExpression(layer_props["exploring"]["custom_selection_expression"]).isValid() is True:
                    if QgsExpression(layer_props["exploring"]["custom_selection_expression"]).isField() is False:
                        custom_filter = layer_props["exploring"]["custom_selection_expression"]
                        self.widgets["MULTIPLE_SELECTION"]["FEATURES"]["WIDGET"].setFilterExpression(custom_filter)
                if expression != None:
                    self.widgets["SINGLE_SELECTION"]["FEATURES"]["WIDGET"].setFilterExpression(expression)
                elif self.widgets["MULTIPLE_SELECTION"]["FEATURES"]["WIDGET"].currentSelectedFeatures() != False:
                    features, expression = self.get_exploring_features(self.widgets["MULTIPLE_SELECTION"]["FEATURES"]["WIDGET"].currentSelectedFeatures(), True)
                    if len(features) > 0 and expression != None:
                        self.widgets["SINGLE_SELECTION"]["FEATURES"]["WIDGET"].setFilterExpression(expression)
                elif self.widgets["MULTIPLE_SELECTION"]["FEATURES"]["WIDGET"].currentVisibleFeatures() != False:
                    features, expression = self.get_exploring_features(self.widgets["MULTIPLE_SELECTION"]["FEATURES"]["WIDGET"].currentVisibleFeatures(), True)
                    if len(features) > 0 and expression != None:
                        self.widgets["SINGLE_SELECTION"]["FEATURES"]["WIDGET"].setFilterExpression(expression)
                elif custom_filter != None:
                    self.widgets["SINGLE_SELECTION"]["FEATURES"]["WIDGET"].setFilterExpression(custom_filter)
            
            else:
                self.widgets["SINGLE_SELECTION"]["FEATURES"]["WIDGET"].setFilterExpression('')
                self.widgets["MULTIPLE_SELECTION"]["FEATURES"]["WIDGET"].setFilterExpression('')


    def get_layers_to_filter(self):

        if self.widgets_initialized is True and self.current_layer != None:

            checked_list_data = []
            for i in range(self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].count()):
                if self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].itemCheckState(i) == Qt.Checked:
                    data = self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].itemData(i, Qt.UserRole)
                    if isinstance(data, dict):
                        checked_list_data.append(data)
                    else:
                        checked_list_data.append(json.loads(data))
            return checked_list_data


    def get_current_crs_authid(self):
        
        if self.widgets_initialized is True and self.has_loaded_layers is True:

            return self.widgets["EXPORTING"]["PROJECTION_TO_EXPORT"]["WIDGET"].crs().authid()


    def current_layer_changed(self, layer):

        if self.widgets_initialized is True:

            if self.current_layer != None:
                self.PROJECT_LAYERS[self.current_layer.id()]["infos"]["is_current_layer"] = False

            if layer != None: 
                self.PROJECT_LAYERS[layer.id()]["infos"]["is_current_layer"] = True    
                self.current_layer = layer
            else:
                return

            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
        

            widgets_to_stop =   [
                                    ["SINGLE_SELECTION","EXPRESSION"],
                                    ["MULTIPLE_SELECTION","FEATURES"],
                                    ["MULTIPLE_SELECTION","EXPRESSION"],
                                    ["CUSTOM_SELECTION","EXPRESSION"],
                                    ["FILTERING","BUFFER"],
                                    ["FILTERING","BUFFER_PROPERTY"],
                                    ["FILTERING","BUFFER_EXPRESSION"],
                                    ["FILTERING","GEOMETRIC_PREDICATES"],
                                    ["FILTERING","GEOMETRIC_PREDICATES_OPERATOR"],
                                    ["FILTERING","COMBINE_OPERATOR"],
                                    ["FILTERING","LAYERS_TO_FILTER"],
                                    ["FILTERING","CURRENT_LAYER"]
                                ]
            
            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'disconnect')

            if self.link_legend_layers_and_current_layer_flag is True:
                widget_path = ["QGIS","LAYER_TREE_VIEW"]
                self.manageSignal(widget_path, 'disconnect')



            self.current_buffer_property_has_been_init = False
            self.current_layer_all_features = None

            lastLayer = self.widgets["FILTERING"]["CURRENT_LAYER"]["WIDGET"].currentLayer()
            if lastLayer != None and lastLayer.id() != self.current_layer.id():
                self.widgets["FILTERING"]["CURRENT_LAYER"]["WIDGET"].setLayer(self.current_layer)


            """SINGLE SELECTION"""

            self.widgets["SINGLE_SELECTION"]["EXPRESSION"]["WIDGET"].setLayer(self.current_layer)
            self.widgets["SINGLE_SELECTION"]["EXPRESSION"]["WIDGET"].setExpression(layer_props["exploring"]["single_selection_expression"])

            self.widgets["SINGLE_SELECTION"]["FEATURES"]["WIDGET"].setLayer(self.current_layer)
            self.widgets["SINGLE_SELECTION"]["FEATURES"]["WIDGET"].setDisplayExpression(layer_props["exploring"]["single_selection_expression"])
            self.widgets["SINGLE_SELECTION"]["FEATURES"]["WIDGET"].setFetchGeometry(True)
            self.widgets["SINGLE_SELECTION"]["FEATURES"]["WIDGET"].setShowBrowserButtons(True)


            """MULTIPLE SELECTION"""
            
            self.widgets["MULTIPLE_SELECTION"]["EXPRESSION"]["WIDGET"].setLayer(self.current_layer)
            self.widgets["MULTIPLE_SELECTION"]["EXPRESSION"]["WIDGET"].setExpression(layer_props["exploring"]["multiple_selection_expression"])

            self.widgets["MULTIPLE_SELECTION"]["FEATURES"]["WIDGET"].setLayer(self.current_layer, layer_props)


            """CUSTOM SELECTION"""

            self.widgets["CUSTOM_SELECTION"]["EXPRESSION"]["WIDGET"].setLayer(self.current_layer)
            self.widgets["CUSTOM_SELECTION"]["EXPRESSION"]["WIDGET"].setExpression(layer_props["exploring"]["custom_selection_expression"])


            for properties_tuples_key in self.layer_properties_tuples_dict:
                properties_tuples = self.layer_properties_tuples_dict[properties_tuples_key]
                for i, property_tuple in enumerate(properties_tuples):
                    widget_type = self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["TYPE"]
                    if widget_type == 'PushButton':
                        self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setChecked(layer_props[property_tuple[0]][property_tuple[1]])
                    elif widget_type == 'CheckableComboBox':
                        self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setCheckedItems(layer_props[property_tuple[0]][property_tuple[1]])
                    elif widget_type == 'CustomCheckableComboBox':
                        self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["CUSTOM_LOAD_FUNCTION"]
                    elif widget_type == 'ComboBox':
                        self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setCurrentIndex(self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].findText(layer_props[property_tuple[0]][property_tuple[1]]))
                    elif widget_type == 'QgsDoubleSpinBox':
                        self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setValue(layer_props[property_tuple[0]][property_tuple[1]])
                    elif widget_type == 'LineEdit':
                        self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setText(layer_props[property_tuple[0]][property_tuple[1]])
                    elif widget_type == 'QgsProjectionSelectionWidget':
                        crs = QgsCoordinateReferenceSystem(layer_props[property_tuple[0]][property_tuple[1]])
                        if crs.isValid():
                            self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setCrs(crs)
                    elif widget_type == 'PropertyOverrideButton':
                        self.filtering_init_buffer_property()
                        if layer_props[property_tuple[0]][property_tuple[1]] is False:
                            self.widgets["FILTERING"]["BUFFER_PROPERTY"]["WIDGET"].setActive(False)
                            if self.widgets["FILTERING"]["BUFFER_EXPRESSION"]["WIDGET"].isVisible() is True:
                                self.widgets["FILTERING"]["BUFFER_EXPRESSION"]["WIDGET"].hide()
                        elif layer_props[property_tuple[0]][property_tuple[1]] is True:
                            self.widgets["FILTERING"]["BUFFER_PROPERTY"]["WIDGET"].setActive(True)
                            if self.widgets["FILTERING"]["BUFFER_EXPRESSION"]["WIDGET"].isHidden() is True:
                                self.widgets["FILTERING"]["BUFFER_EXPRESSION"]["WIDGET"].show()
                        
                        
                            

                                


            for properties_group in self.layer_properties_tuples_dict:
                if properties_group != 'is':
                    self.properties_group_state_changed(self.layer_properties_tuples_dict[properties_group], properties_group)

            self.filtering_populate_layers_chekableCombobox()

            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'connect')

            if self.link_legend_layers_and_current_layer_flag is True:
                if self.iface.activeLayer() != None and self.iface.activeLayer().id() != self.current_layer.id():
                    self.widgets["QGIS"]["LAYER_TREE_VIEW"]["WIDGET"].setCurrentLayer(self.current_layer)

                widget_path = ["QGIS","LAYER_TREE_VIEW"]
                self.manageSignal(widget_path, 'connect')
                
            self.exploring_link_widgets()
        


    def project_property_changed(self, input_property, input_data=None, custom_functions={}):

        if self.widgets_initialized is True and self.has_loaded_layers is True:

            properties_group_key = None
            property_path = None
            index = None
            state = None
            flag_value_changed = False

            if isinstance(input_data, dict) or isinstance(input_data, list) or isinstance(input_data, str):
                if len(input_data) >= 0:
                    state = True
                else:
                    state = False
            elif isinstance(input_data, int) or isinstance(input_data, float):
                if int(input_data) >= 0:
                    state = True
                else:
                    state = False
            elif isinstance(input_data, bool):
                state = input_data
            

            for properties_tuples_key in self.export_properties_tuples_dict:
                if input_property.find(properties_tuples_key) >= 0:
                    properties_group_key = properties_tuples_key
                    properties_tuples = self.export_properties_tuples_dict[properties_tuples_key]
                    for i, property_tuple in enumerate(properties_tuples):
                        if property_tuple[1] == input_property:
                            property_path = property_tuple
                            index = i
                            break
                    break
            
            widget_type = self.widgets[property_path[0].upper()][property_path[1].upper()]["TYPE"]
            if widget_type == 'PushButton':
                if self.project_props[property_path[0]][property_path[1]] is not input_data and input_data is True:
                    self.project_props[property_path[0]][property_path[1]] = input_data
                    flag_value_changed = True
                    if "ON_TRUE" in custom_functions:
                        custom_functions["ON_TRUE"](0)

                elif self.project_props[property_path[0]][property_path[1]] is not input_data and input_data is False:
                    self.project_props[property_path[0]][property_path[1]] = input_data
                    flag_value_changed = True
                    if "ON_FALSE" in custom_functions:
                        custom_functions["ON_FALSE"](0)

                
                if flag_value_changed is True:
                    self.properties_group_state_changed(properties_tuples, properties_group_key)

            else:    
                
                if self.project_props[properties_tuples[0][0]][properties_tuples[0][1]] is state and state is True:
                    self.project_props[property_path[0]][property_path[1]] = custom_functions["CUSTOM_DATA"](0) if "CUSTOM_DATA" in custom_functions else input_data
                    flag_value_changed = True
                    if "ON_TRUE" in custom_functions:
                        custom_functions["ON_TRUE"](0)

            if flag_value_changed is True:
                if "ON_CHANGE" in custom_functions:
                    custom_functions["ON_CHANGE"](0)
                self.CONFIG_DATA['EXPORT'] = self.project_props['exporting']
                self.reload_configuration_model()


    def layer_property_changed(self, input_property, input_data=None, custom_functions={}):
        
        if self.widgets_initialized is True and self.current_layer != None:


            if self.current_layer == None:
                return
            
            print(input_property, input_data)
            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
            properties_group_key = None
            property_path = None
            index = None
            state = None
            flag_value_changed = False

            if isinstance(input_data, dict) or isinstance(input_data, list) or isinstance(input_data, str):
                if len(input_data) >= 0:
                    state = True
                else:
                    state = False
            elif isinstance(input_data, int) or isinstance(input_data, float):
                if int(input_data) >= 0:
                    state = True
                else:
                    state = False
            elif isinstance(input_data, bool):
                state = input_data
            

            for properties_tuples_key in self.layer_properties_tuples_dict:
                if input_property.find(properties_tuples_key) >= 0:
                    properties_group_key = properties_tuples_key
                    properties_tuples = self.layer_properties_tuples_dict[properties_tuples_key]
                    for i, property_tuple in enumerate(properties_tuples):
                        if property_tuple[1] == input_property:
                            property_path = property_tuple
                            index = i
                            break
                    break

            if properties_group_key == 'is':

                if layer_props[property_path[0]][property_path[1]] is not input_data and input_data is True:
                    self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = input_data
                    flag_value_changed = True
                    if "ON_TRUE" in custom_functions:
                        custom_functions["ON_TRUE"](0)

                elif layer_props[property_path[0]][property_path[1]] is not input_data and input_data is False:
                    self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = input_data
                    flag_value_changed = True
                    if "ON_FALSE" in custom_functions:
                        custom_functions["ON_FALSE"](0) 

            else:
                widget_type = self.widgets[property_path[0].upper()][property_path[1].upper()]["TYPE"]
                if widget_type == 'PushButton':
                    if layer_props[property_path[0]][property_path[1]] is not input_data and input_data is True:
                        self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = input_data
                        flag_value_changed = True
                        if "ON_TRUE" in custom_functions:
                            custom_functions["ON_TRUE"](0)

                    elif layer_props[property_path[0]][property_path[1]] is not input_data and input_data is False:
                        self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = input_data
                        flag_value_changed = True
                        if "ON_FALSE" in custom_functions:
                            custom_functions["ON_FALSE"](0)

                    if flag_value_changed is True:
                        self.properties_group_state_changed(properties_tuples, properties_group_key)

                else:    
                    if layer_props[properties_tuples[0][0]][properties_tuples[0][1]] is state and state is True:
                        self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = custom_functions["CUSTOM_DATA"](0) if "CUSTOM_DATA" in custom_functions else input_data
                        flag_value_changed = True
                        if "ON_TRUE" in custom_functions:
                            custom_functions["ON_TRUE"](0)




            if flag_value_changed is True:
                if "ON_CHANGE" in custom_functions:
                    custom_functions["ON_CHANGE"](0)

                self.setLayerVariableEvent(self.current_layer.id(), tuple(property_path))


    def set_exporting_properties(self):

        if self.widgets_initialized is True and self.has_loaded_layers is True:

            widgets_to_stop =   [
                                    ["EXPORTING","HAS_LAYERS_TO_EXPORT"],
                                    ["EXPORTING","HAS_PROJECTION_TO_EXPORT"],
                                    ["EXPORTING","HAS_STYLES_TO_EXPORT"],
                                    ["EXPORTING","HAS_DATATYPE_TO_EXPORT"],
                                    ["EXPORTING","LAYERS_TO_EXPORT"],
                                    ["EXPORTING","PROJECTION_TO_EXPORT"],
                                    ["EXPORTING","STYLES_TO_EXPORT"],
                                    ["EXPORTING","DATATYPE_TO_EXPORT"]
                                ]
            
            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'disconnect')

            for properties_tuples_key in self.export_properties_tuples_dict:
                properties_tuples = self.export_properties_tuples_dict[properties_tuples_key]    
                for i, property_tuple in enumerate(properties_tuples):
                    widget_type = self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["TYPE"]
                    if widget_type == 'PushButton':
                        self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setChecked(self.project_props[property_tuple[0]][property_tuple[1]])
                    elif widget_type == 'CheckableComboBox':
                        self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setCheckedItems(self.project_props[property_tuple[0]][property_tuple[1]])
                    elif widget_type == 'CustomCheckableComboBox':
                        self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["CUSTOM_LOAD_FUNCTION"]
                    elif widget_type == 'ComboBox':
                        self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setCurrentIndex(self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].findText(self.project_props[property_tuple[0]][property_tuple[1]]))
                    elif widget_type == 'QgsDoubleSpinBox':
                        self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setValue(self.project_props[property_tuple[0]][property_tuple[1]])
                    elif widget_type == 'LineEdit':
                        self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setText(self.project_props[property_tuple[0]][property_tuple[1]])
                    elif widget_type == 'QgsProjectionSelectionWidget':
                        crs = QgsCoordinateReferenceSystem(self.project_props[property_tuple[0]][property_tuple[1]])
                        if crs.isValid():
                            self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setCrs(crs)

            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'connect')

            self.CONFIG_DATA['EXPORT'] = self.project_props['exporting']
            self.reload_configuration_model()



    def properties_group_state_changed(self, tuple_group, group_name):

        if self.widgets_initialized is True and self.has_loaded_layers is True:

            group_enabled_property = tuple_group[0]
            state = self.widgets[group_enabled_property[0].upper()][group_enabled_property[1].upper()]["WIDGET"].isChecked()

            for tuple in tuple_group[1:]:
                if state is False:
                    widget_type = self.widgets[tuple[0].upper()][tuple[1].upper()]["TYPE"]
                    self.manageSignal([tuple[0].upper(),tuple[1].upper()], 'disconnect')

                    if group_name in self.layer_properties_tuples_dict:
                        if widget_type == 'PushButton':
                            self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].setChecked(state)
                            self.PROJECT_LAYERS[self.current_layer.id()][tuple[0]][tuple[1]] = self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].isChecked()
                        elif widget_type == 'CheckableComboBox':
                            self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].deselectAllOptions()
                            self.PROJECT_LAYERS[self.current_layer.id()][tuple[0]][tuple[1]] = self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].checkedItems()
                        elif widget_type == 'ComboBox':
                            self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].setCurrentIndex(0)
                            self.PROJECT_LAYERS[self.current_layer.id()][tuple[0]][tuple[1]] = self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].currentText()
                        elif widget_type == 'QgsDoubleSpinBox':
                            self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].clearValue()
                            self.PROJECT_LAYERS[self.current_layer.id()][tuple[0]][tuple[1]] = self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].value()
                        elif widget_type == 'LineEdit':
                            self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].setText('')
                            self.PROJECT_LAYERS[self.current_layer.id()][tuple[0]][tuple[1]] = self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].text()
                        elif widget_type == 'QgsProjectionSelectionWidget':
                            self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].setCrs(PROJECT.crs())
                            self.PROJECT_LAYERS[self.current_layer.id()][tuple[0]][tuple[1]] = self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].crs().authid()
                        elif widget_type == 'PropertyOverrideButton':
                            self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].setActive(False)
                            self.PROJECT_LAYERS[self.current_layer.id()][tuple[0]][tuple[1]] = False


                    elif group_name in self.export_properties_tuples_dict:
                        if widget_type == 'PushButton':
                            self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].setChecked(state)
                            self.project_props[tuple[0]][tuple[1]] = self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].isChecked()
                        elif widget_type == 'CheckableComboBox':
                            self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].deselectAllOptions()
                            self.project_props[tuple[0]][tuple[1]] = self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].checkedItems()
                        elif widget_type == 'ComboBox':
                            index = self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].findText('GPKG')
                            if index < 0:
                                index = 0
                            self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].setCurrentIndex(index)
                            self.project_props[tuple[0]][tuple[1]] = self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].currentText()
                        elif widget_type == 'QgsDoubleSpinBox':
                            self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].clearValue()
                            self.project_props[tuple[0]][tuple[1]] = self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].value()
                        elif widget_type == 'LineEdit':
                            self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].setText('')
                            self.project_props[tuple[0]][tuple[1]] = self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].text()
                        elif widget_type == 'QgsProjectionSelectionWidget':
                            self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].setCrs(PROJECT.crs())
                            self.project_props[tuple[0]][tuple[1]] = self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].crs().authid()
                        elif widget_type == 'PropertyOverrideButton':
                            self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].setActive(False)
                            self.project_props[tuple[0]][tuple[1]] = False
                            
 



                    self.manageSignal([tuple[0].upper(),tuple[1].upper()], 'connect')

                self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].setEnabled(state)

    def filtering_init_buffer_property(self):

        if self.widgets_initialized is True and self.has_loaded_layers is True:
                        


            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]   
            layer_scope = QgsExpressionContextUtils.layerScope(self.current_layer)

            property = QgsProperty()
            name = str("{}_buffer_property_definition".format(self.current_layer.id()))
            description = str("Replace unique buffer value with values based on expression for {}".format(self.current_layer.id()))
           
            property_definition = QgsPropertyDefinition(name, QgsPropertyDefinition.DataTypeNumeric, description, 'Expression must returns numeric values (unit is in meters)')
            
            buffer_expression = layer_props["filtering"]["buffer_expression"]
            if buffer_expression != '':
                expression_context = QgsExpressionContext([layer_scope])
                expression = QgsExpression(buffer_expression)
                expression.prepare(expression_context)
                if expression.isField() is False and expression.isValid() is True:
                    results = expression.evaluate()
                    print(results)
                    if isinstance(results, list):
                        for result in results:
                            print(result)
                        property = QgsProperty.fromExpression(layer_props["filtering"]["buffer_expression"])


            self.widgets["FILTERING"]["BUFFER_PROPERTY"]["WIDGET"].init(0, property, property_definition, self.current_layer)
            
            if self.buffer_property_has_been_init is False:
                self.widgets["FILTERING"]["BUFFER_PROPERTY"]["WIDGET"].registerEnabledWidget(self.widgets["FILTERING"]["BUFFER"]["WIDGET"], False)
                self.widgets["FILTERING"]["BUFFER_PROPERTY"]["WIDGET"].registerVisibleWidget(self.widgets["FILTERING"]["BUFFER"]["WIDGET"], False)
                self.widgets["FILTERING"]["BUFFER_PROPERTY"]["WIDGET"].registerEnabledWidget(self.widgets["FILTERING"]["BUFFER_EXPRESSION"]["WIDGET"], True)
                self.widgets["FILTERING"]["BUFFER_PROPERTY"]["WIDGET"].registerVisibleWidget(self.widgets["FILTERING"]["BUFFER_EXPRESSION"]["WIDGET"], True)
                self.widgets["FILTERING"]["BUFFER_PROPERTY"]["WIDGET"].registerExpressionWidget(self.widgets["FILTERING"]["BUFFER_EXPRESSION"]["WIDGET"])
                self.buffer_property_has_been_init = True

            self.current_buffer_property_has_been_init = True

    def filtering_buffer_expression_edited(self):

        if self.widgets_initialized is True and self.has_loaded_layers is True:

            widgets_to_stop =   [
                                    ["FILTERING","BUFFER_PROPERTY"],
                                     ["FILTERING","BUFFER_EXPRESSION"]
                                ]
            
            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'disconnect')


            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]

            if layer_props["filtering"]["buffer_expression"] in ('','NULL'):
                if layer_props["filtering"]["buffer_property"] is True:
                    self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer_expression"] = ''
                    self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer_property"] = False
                    self.widgets["FILTERING"]["BUFFER_PROPERTY"]["WIDGET"].setToProperty(QgsProperty())
                    self.widgets["FILTERING"]["BUFFER_PROPERTY"]["WIDGET"].setActive(False)

            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'connect')

    def filtering_buffer_property_changed(self):

        if self.widgets_initialized is True and self.has_loaded_layers is True:
            
            widgets_to_stop =   [
                                    ["FILTERING","BUFFER_EXPRESSION"]
                                ]
            
            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'disconnect')

            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]

            if layer_props["filtering"]["buffer_property"] is True:
                if self.current_buffer_property_has_been_init is False:
                    self.filtering_init_buffer_property()
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer_expression"] = self.widgets["FILTERING"]["BUFFER_PROPERTY"]["WIDGET"].toProperty().asExpression()

            if layer_props["filtering"]["buffer_property"] is False:
                print(layer_props["filtering"])
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer_expression"] = ''
                self.widgets["FILTERING"]["BUFFER_PROPERTY"]["WIDGET"].setToProperty(QgsProperty())
                self.widgets["FILTERING"]["BUFFER_PROPERTY"]["WIDGET"].setActive(False)

            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'connect')

              
    def dialog_export_output_path(self):

        if self.widgets_initialized is True and self.has_loaded_layers is True:

            path = ''
            datatype = ''

            state = self.widgets["EXPORTING"]["HAS_OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].isChecked()

            if self.widgets["EXPORTING"]["HAS_DATATYPE_TO_EXPORT"]["WIDGET"].isChecked() == True:  
                datatype = self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"].currentText()

            if state == True:

                if self.widgets["EXPORTING"]["HAS_LAYERS_TO_EXPORT"]["WIDGET"].isChecked() == True:

                    layers = self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].checkedItems()
                    if len(layers) == 1 and datatype != '':

                        layer = layers[0]
                        regexp_layer = re.search('.* ', layer)
                        if regexp_layer != None:
                            layer = regexp_layer.group()
                        path = str(QtWidgets.QFileDialog.getSaveFileName(self, 'Save your layer to a file', os.path.join(self.current_project_path, self.output_name + '_' + layer.strip()) ,'*.{}'.format(datatype))[0])

                    elif datatype.upper() == 'GPKG':

                        path = str(QtWidgets.QFileDialog.getSaveFileName(self, 'Save your layer to a file', os.path.join(self.current_project_path, self.output_name + '.gpkg') ,'*.gpkg')[0])
                    
                    else:
                    
                        path = str(QtWidgets.QFileDialog.getExistingDirectory(self, 'Select a folder where to export your layers', self.current_project_path))

                else:
                
                    path = str(QtWidgets.QFileDialog.getExistingDirectory(self, 'Select a folder where to export your layers', self.current_project_path))

                if path != None and path != '':
                    path = os.path.normcase(path)
                    self.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].setText(path)
                else:
                    state = False
                    self.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].clear()
            else:
                self.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].clear()

            self.project_property_changed('has_output_folder_to_export', state)
            self.project_property_changed('output_folder_to_export', path)


    def reset_export_output_path(self):

        if self.widgets_initialized is True and self.has_loaded_layers is True:

            if str(self.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].text()) == '':
                self.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].clear()
                self.widgets["EXPORTING"]["HAS_OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].setChecked(False)
                self.project_property_changed('has_output_folder_to_export', False)
                self.project_property_changed('output_folder_to_export', '')

    def dialog_export_output_pathzip(self):

        if self.widgets_initialized is True and self.has_loaded_layers is True:
            
            path = ''
            state = self.widgets["EXPORTING"]["HAS_ZIP_TO_EXPORT"]["WIDGET"].isChecked()

            if state == True:

                path = str(QtWidgets.QFileDialog.getSaveFileName(self, 'Save your exported data to a zip file', os.path.join(self.current_project_path, self.output_name) ,'*.zip')[0])

                if path != None and path != '':
                    path = os.path.normcase(path)
                    self.widgets["EXPORTING"]["ZIP_TO_EXPORT"]["WIDGET"].setText(path)
                else:
                    state = False
                    self.widgets["EXPORTING"]["ZIP_TO_EXPORT"]["WIDGET"].clear()
            else:
                self.widgets["EXPORTING"]["ZIP_TO_EXPORT"]["WIDGET"].clear()
                
            self.project_property_changed('has_zip_to_export', state)
            self.project_property_changed('zip_to_export', path)


    def reset_export_output_pathzip(self):

        if self.widgets_initialized is True and self.has_loaded_layers is True:
                
            if str(self.widgets["EXPORTING"]["ZIP_TO_EXPORT"]["WIDGET"].text()) == '':
                self.widgets["EXPORTING"]["ZIP_TO_EXPORT"]["WIDGET"].clear()
                self.widgets["EXPORTING"]["HAS_ZIP_TO_EXPORT"]["WIDGET"].setChecked(False)
                self.project_property_changed('has_zip_to_export', False)
                self.project_property_changed('zip_to_export', '')

    def filtering_auto_current_layer_changed(self, state=None):

        if self.widgets_initialized is True and self.has_loaded_layers is True:

            if state == None:
                state = self.link_legend_layers_and_current_layer_flag
            # else:
            #     state = self.widgets["FILTERING"]["AUTO_CURRENT_LAYER"]["WIDGET"].isChecked()

            self.widgets["FILTERING"]["AUTO_CURRENT_LAYER"]["WIDGET"].setChecked(state)

            if state is True:
                self.link_legend_layers_and_current_layer_flag = state
                self.manageSignal(["QGIS","LAYER_TREE_VIEW"], 'connect')

            elif state is False:
                self.link_legend_layers_and_current_layer_flag = state
                self.manageSignal(["QGIS","LAYER_TREE_VIEW"], 'disconnect')


    def get_project_layers_from_app(self, project_layers):

        layer = None

        if self.widgets_initialized is True:

            self.PROJECT_LAYERS = project_layers

            if len(list(self.PROJECT_LAYERS)) > 0:

                if self.current_layer != None:
                    layers = [layer for layer in PROJECT.mapLayersByName(self.PROJECT_LAYERS[self.current_layer.id()]["infos"]["layer_name"]) if layer.id() == self.current_layer.id()]
                    if len(layers) == 0:
                        layer = self.iface.activeLayer()
                else:
                    layer = self.iface.activeLayer()

                if self.has_loaded_layers is False:
                    self.has_loaded_layers = True
                    self.connect_widgets_signals()
                    self.set_widgets_enabled_state(self.has_loaded_layers)
        
            else:
                self.has_loaded_layers = False
                self.disconnect_widgets_signals()
                self.set_widgets_enabled_state(self.has_loaded_layers)

            
            if layer != None and isinstance(layer, QgsVectorLayer):
                print("get_project_layers_from_app", self.PROJECT_LAYERS)
                self.exporting_populate_combobox()
                self.set_exporting_properties()
                self.current_layer_changed(layer)
                self.filtering_auto_current_layer_changed()
                self.exploring_source_params_changed()


    def setLayerVariableEvent(self, layer_id, path):

        if self.widgets_initialized is True:

            self.settingLayerVariable.emit(layer_id, path)
    
    def getProjectLayersEvent(self, event):

        if self.widgets_initialized is True:

            self.gettingProjectLayers.emit()

    def closeEvent(self, event):

        if self.widgets_initialized is True:

            self.closingPlugin.emit()
            event.accept()

    def launchTaskEvent(self, event):

        if self.widgets_initialized is True:

            self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["layers_to_filter"] = self.get_layers_to_filter()
            self.launchingTask.emit(event)
    
    def reinitializeLayerOnErrorEvent(self, event=None):

        if self.widgets_initialized is True:

            data = self.current_layer.id()    
            self.reinitializingLayerOnError.emit(data)

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



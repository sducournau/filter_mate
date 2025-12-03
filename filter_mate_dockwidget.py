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
from qgis.PyQt import QtGui, QtWidgets, QtCore, uic
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *
from qgis.utils import iface
from qgis.PyQt.QtWidgets import QApplication, QVBoxLayout

import webbrowser
from .modules.widgets import QgsCheckableComboBoxFeaturesListPickerWidget, QgsCheckableComboBoxLayer
from .modules.qt_json_view.model import JsonModel
from .modules.qt_json_view.view import JsonView
from .modules.customExceptions import *
from .modules.appUtils import *

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'filter_mate_dockwidget_base.ui'))

class FilterMateDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()
    launchingTask = pyqtSignal(str)

    gettingProjectLayers = pyqtSignal()

    settingLayerVariable = pyqtSignal(QgsVectorLayer, list)
    resettingLayerVariable = pyqtSignal(QgsVectorLayer, list)
    resettingLayerVariableOnError = pyqtSignal(QgsVectorLayer, list)

    settingProjectVariables = pyqtSignal()
    
    # Static cache for geometry icons to avoid repeated calculations
    _icon_cache = {}

    def __init__(self, project_layers, plugin_dir, config_data, project, parent=None):
        """Constructor."""
        super(FilterMateDockWidget, self).__init__(parent)
        
        self.exception = None
        self.iface = iface

        self.plugin_dir = plugin_dir
        self.CONFIG_DATA = config_data
        self.PROJECT_LAYERS = project_layers
        self.PROJECT = project
        self.current_layer = None
        if self.PROJECT:
            if len(list(self.PROJECT_LAYERS)) > 0:
                self.init_layer = self.iface.activeLayer() if self.iface.activeLayer() != None else list(self.PROJECT.mapLayers().values())[0]
                self.has_loaded_layers = True
            else:
                self.init_layer = None
                self.has_loaded_layers = False
        else:
            self.init_layer = None
            self.has_loaded_layers = False


        self.widgets = None
        self.widgets_initialized = False
        self.current_exploring_groupbox = None
        self.tabTools_current_index = 0
        self.backend_indicator_label = None

        self.predicates = None
        self.buffer_property_has_been_init = False
        self.project_props = None
        self.layer_properties_tuples_dict = None
        self.export_properties_tuples_dict = None
        self.json_template_project_exporting = '{"has_layers_to_export":false,"layers_to_export":[],"has_projection_to_export":false,"projection_to_export":"","has_styles_to_export":false,"styles_to_export":"","has_datatype_to_export":false,"datatype_to_export":"","datatype_to_export":"","has_output_folder_to_export":false,"output_folder_to_export":"","has_zip_to_export":false,"zip_to_export":"" }'

        self.setupUi(self)
        self.setupUiCustom()
        self.manage_ui_style()
        self.manage_interactions()
        

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
               if signal[0] == custom_signal_name and signal[-1] != None:
                    current_signal_name = custom_signal_name
                    current_triggered_function = signal[-1]
                    state = self.changeSignalState(widget_path, current_signal_name, current_triggered_function, custom_action)

        else:
            for signal in widget_object["SIGNALS"]:
                if signal[-1] != None:
                    current_signal_name = str(signal[0])
                    current_triggered_function = signal[-1]
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

    def reset_multiple_checkable_combobox(self):
       


        layout = self.verticalLayout_exploring_multiple_selection
        item = layout.itemAt(0)
        layout.removeItem(item)
        self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.reset()
        self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.close()
        
        self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection = None

        self.set_multiple_checkable_combobox()

        layout.insertWidget(0, self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection)
        layout.update()

        self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"] = {"TYPE":"CustomCheckableFeatureComboBox", "WIDGET":self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection, "SIGNALS":[("updatingCheckedItemList", self.exploring_features_changed),("filteringCheckedItemList", self.exploring_source_params_changed)]}
        #self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setEnabled(True)

    def set_multiple_checkable_combobox(self):
        self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection = QgsCheckableComboBoxFeaturesListPickerWidget(self.CONFIG_DATA, self)


    def setupUiCustom(self):
        self.set_multiple_checkable_combobox()

        # Create backend indicator label
        self.backend_indicator_label = QtWidgets.QLabel(self)
        self.backend_indicator_label.setObjectName("label_backend_indicator")
        self.backend_indicator_label.setText("Backend: Detecting...")
        self.backend_indicator_label.setStyleSheet("color: gray; font-size: 10px; padding: 2px;")
        self.backend_indicator_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        # Add to the main layout (top of the widget)
        if hasattr(self, 'verticalLayout'):
            self.verticalLayout.insertWidget(0, self.backend_indicator_label)

        layout = self.verticalLayout_exploring_multiple_selection
        layout.insertWidget(0, self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection)

        self.checkableComboBoxLayer_filtering_layers_to_filter = QgsCheckableComboBoxLayer(self)
        #self.checkableComboBoxLayer_filtering_layers_to_filter.contextMenuEvent()

        self.checkableComboBoxLayer_exporting_layers = QgsCheckableComboBoxLayer(self)

        #self.checkableComboBoxLayer_exporting_layers.contextMenuEvent()




        if 'CURRENT_PROJECT' in self.CONFIG_DATA:
            self.project_props = self.CONFIG_DATA["CURRENT_PROJECT"]

        
        self.manage_configuration_model()
        self.dockwidget_widgets_configuration()

        layout = self.verticalLayout_filtering_values
        layout.insertWidget(3, self.checkableComboBoxLayer_filtering_layers_to_filter)

        layout = self.verticalLayout_exporting_values
        layout.insertWidget(1, self.checkableComboBoxLayer_exporting_layers)

        #self.custom_identify_tool = CustomIdentifyTool(self.iface)
        self.iface.mapCanvas().setSelectionColor(QColor(237, 97, 62, 75))
        
        


    def dockwidget_widgets_configuration(self):

        self.layer_properties_tuples_dict =   {
                                                "is":(("exploring","is_selecting"),("exploring","is_tracking"),("exploring","is_linking")),
                                                "selection_expression":(("exploring","single_selection_expression"),("exploring","multiple_selection_expression"),("exploring","custom_selection_expression")),
                                                "layers_to_filter":(("filtering","has_layers_to_filter"),("filtering","layers_to_filter")),
                                                "combine_operator":(("filtering", "has_combine_operator"), ("filtering", "source_layer_combine_operator"),("filtering", "other_layers_combine_operator")),
                                                "buffer_type":(("filtering","has_buffer_type"),("filtering","buffer_type")),
                                                "buffer_value":(("filtering", "has_buffer_value"),("filtering","has_buffer_type"),("filtering", "buffer_value"),("filtering", "buffer_value_expression"),("filtering", "buffer_value_property")),
                                                "geometric_predicates":(("filtering","has_geometric_predicates"),("filtering","has_buffer_value"),("filtering","has_buffer_type"),("filtering","geometric_predicates"))
                                                }
        
        self.export_properties_tuples_dict =   {
                                                "layers_to_export":(("exporting","has_layers_to_export"),("exporting","layers_to_export")),
                                                "projection_to_export":(("exporting","has_projection_to_export"),("exporting","projection_to_export")),
                                                "styles_to_export":(("exporting","has_styles_to_export"),("exporting","styles_to_export")),
                                                "datatype_to_export":(("exporting","has_datatype_to_export"),("exporting","datatype_to_export")),
                                                "output_folder_to_export":(("exporting","has_output_folder_to_export"),("exporting","output_folder_to_export")),
                                                "zip_to_export":(("exporting", "has_zip_to_export"), ("exporting", "zip_to_export"))
                                                }

        self.widgets = {"DOCK":{}, "ACTION":{}, "EXPLORING":{}, "SINGLE_SELECTION":{}, "MULTIPLE_SELECTION":{}, "CUSTOM_SELECTION":{}, "FILTERING":{}, "EXPORTING":{}, "QGIS":{}}
            
        self.widgets["DOCK"] = {
                                "SINGLE_SELECTION":{"TYPE":"GroupBox", "WIDGET":self.mGroupBox_exploring_single_selection, "SIGNALS":[("stateChanged", lambda state, x='single_selection': self.exploring_groupbox_changed(x))]},
                                "MULTIPLE_SELECTION":{"TYPE":"GroupBox","WIDGET":self.mGroupBox_exploring_multiple_selection, "SIGNALS":[("stateChanged", lambda state, x='multiple_selection': self.exploring_groupbox_changed(x))]},
                                "CUSTOM_SELECTION":{"TYPE":"GroupBox","WIDGET":self.mGroupBox_exploring_custom_selection, "SIGNALS":[("stateChanged", lambda state, x='custom_selection': self.exploring_groupbox_changed(x))]},
                                "CONFIGURATION_TREE_VIEW":{"TYPE":"JsonTreeView","WIDGET":self.config_view, "SIGNALS":[("collapsed", None),("expanded", None)]},
                                "CONFIGURATION_MODEL":{"TYPE":"JsonModel","WIDGET":self.config_model, "SIGNALS":[("itemChanged", None)]},
                                "TOOLS":{"TYPE":"ToolBox","WIDGET":self.toolBox_tabTools, "SIGNALS":[("currentChanged", self.select_tabTools_index)]}
                                }   

        self.widgets["ACTION"] = {
                                "FILTER":{"TYPE":"PushButton", "WIDGET":self.pushButton_action_filter, "SIGNALS":[("clicked", lambda state, x='filter': self.launchTaskEvent(state, x))], "ICON":None},
                                "UNFILTER":{"TYPE":"PushButton", "WIDGET":self.pushButton_action_unfilter, "SIGNALS":[("clicked", lambda state, x='unfilter': self.launchTaskEvent(state, x))], "ICON":None},
                                "RESET":{"TYPE":"PushButton", "WIDGET":self.pushButton_action_reset, "SIGNALS":[("clicked", lambda state, x='reset': self.launchTaskEvent(state, x))], "ICON":None},
                                "EXPORT":{"TYPE":"PushButton", "WIDGET":self.pushButton_action_export, "SIGNALS":[("clicked", lambda state, x='export': self.launchTaskEvent(state, x))], "ICON":None},
                                "ABOUT":{"TYPE":"PushButton", "WIDGET":self.pushButton_action_about, "SIGNALS":[("clicked", self.open_project_page)], "ICON":None}
                                }        


        self.widgets["EXPLORING"] = {
                                    "IDENTIFY":{"TYPE":"PushButton", "WIDGET":self.pushButton_exploring_identify, "SIGNALS":[("clicked", self.exploring_identify_clicked)], "ICON":None},
                                    "ZOOM":{"TYPE":"PushButton", "WIDGET":self.pushButton_exploring_zoom, "SIGNALS":[("clicked", self.exploring_zoom_clicked)], "ICON":None},
                                    "IS_SELECTING":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exploring_selecting, "SIGNALS":[("clicked", lambda state, x='is_selecting', custom_functions={"ON_TRUE": lambda x: self.get_current_features(), "ON_FALSE": lambda x: self.exploring_deselect_features()}: self.layer_property_changed(x, state, custom_functions))], "ICON":None},
                                    "IS_TRACKING":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exploring_tracking, "SIGNALS":[("clicked", lambda state, x='is_tracking', custom_functions={"ON_TRUE": lambda x: self.get_current_features()}: self.layer_property_changed(x, state, custom_functions))], "ICON":None},
                                    "IS_LINKING":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exploring_linking_widgets, "SIGNALS":[("clicked", lambda state, x='is_linking', custom_functions={"ON_CHANGE": lambda x: self.exploring_link_widgets()}: self.layer_property_changed(x, state, custom_functions))], "ICON":None},
                                    "RESET_ALL_LAYER_PROPERTIES":{"TYPE":"PushButton", "WIDGET":self.pushButton_exploring_reset_layer_properties, "SIGNALS":[("clicked", self.resetLayerVariableEvent)], "ICON":None},
                                    
                                    "SINGLE_SELECTION_FEATURES":{"TYPE":"FeatureComboBox", "WIDGET":self.mFeaturePickerWidget_exploring_single_selection, "SIGNALS":[("featureChanged", self.exploring_features_changed)]},
                                    "SINGLE_SELECTION_EXPRESSION":{"TYPE":"QgsFieldExpressionWidget", "WIDGET":self.mFieldExpressionWidget_exploring_single_selection, "SIGNALS":[("fieldChanged", lambda state, x='single_selection_expression', custom_functions={"ON_CHANGE": lambda x: self.exploring_source_params_changed()}: self.layer_property_changed(x, state, custom_functions))]},
                                    
                                    "MULTIPLE_SELECTION_FEATURES":{"TYPE":"CustomCheckableFeatureComboBox", "WIDGET":self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection, "SIGNALS":[("updatingCheckedItemList", self.exploring_features_changed),("filteringCheckedItemList", self.exploring_source_params_changed)]},
                                    "MULTIPLE_SELECTION_EXPRESSION":{"TYPE":"QgsFieldExpressionWidget", "WIDGET":self.mFieldExpressionWidget_exploring_multiple_selection, "SIGNALS":[("fieldChanged", lambda state, x='multiple_selection_expression', custom_functions={"ON_CHANGE": lambda x: self.exploring_source_params_changed()}: self.layer_property_changed(x, state, custom_functions))]},
                                    
                                    "CUSTOM_SELECTION_EXPRESSION":{"TYPE":"QgsFieldExpressionWidget", "WIDGET":self.mFieldExpressionWidget_exploring_custom_selection, "SIGNALS":[("fieldChanged", lambda state, x='custom_selection_expression', custom_functions={"ON_CHANGE": lambda x: self.exploring_source_params_changed()}: self.layer_property_changed(x, state, custom_functions))]}
                                    }


        self.widgets["FILTERING"] = {
                                    "AUTO_CURRENT_LAYER":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_filtering_auto_current_layer, "SIGNALS":[("clicked", lambda state : self.filtering_auto_current_layer_changed(state))], "ICON":None},
                                    "HAS_LAYERS_TO_FILTER":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_filtering_layers_to_filter, "SIGNALS":[("clicked", lambda state, x='has_layers_to_filter': self.layer_property_changed(x, state))], "ICON":None},
                                    "HAS_COMBINE_OPERATOR":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_filtering_current_layer_combine_operator, "SIGNALS":[("clicked", lambda state, x='has_combine_operator': self.layer_property_changed(x, state))], "ICON":None},
                                    "HAS_GEOMETRIC_PREDICATES":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_filtering_geometric_predicates, "SIGNALS":[("clicked", lambda state, x='has_geometric_predicates': self.layer_property_changed(x, state))], "ICON":None},
                                    "HAS_BUFFER_VALUE":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_filtering_buffer_value, "SIGNALS":[("clicked", lambda state, x='has_buffer_value', custom_functions={"ON_CHANGE": lambda x: self.filtering_buffer_property_changed()}: self.layer_property_changed(x, state, custom_functions))], "ICON":None},
                                    "HAS_BUFFER_TYPE":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_filtering_buffer_type, "SIGNALS":[("clicked", lambda state, x='has_buffer_type', custom_functions={"ON_CHANGE": lambda x: self.filtering_buffer_property_changed()}: self.layer_property_changed(x, state, custom_functions))], "ICON":None},
                                    "CURRENT_LAYER":{"TYPE":"ComboBox", "WIDGET":self.comboBox_filtering_current_layer, "SIGNALS":[("layerChanged", self.current_layer_changed)]},
                                    "LAYERS_TO_FILTER":{"TYPE":"CustomCheckableLayerComboBox", "WIDGET":self.checkableComboBoxLayer_filtering_layers_to_filter, "CUSTOM_LOAD_FUNCTION": lambda x: self.get_layers_to_filter(), "SIGNALS":[("checkedItemsChanged", lambda state, custom_functions={"CUSTOM_DATA": lambda x: self.get_layers_to_filter()}, x='layers_to_filter': self.layer_property_changed(x, state, custom_functions))]},
                                    "SOURCE_LAYER_COMBINE_OPERATOR":{"TYPE":"ComboBox", "WIDGET":self.comboBox_filtering_source_layer_combine_operator, "SIGNALS":[("currentTextChanged", lambda state, x='source_layer_combine_operator': self.layer_property_changed(x, state))]},
                                    "OTHER_LAYERS_COMBINE_OPERATOR":{"TYPE":"ComboBox", "WIDGET":self.comboBox_filtering_other_layers_combine_operator, "SIGNALS":[("currentTextChanged", lambda state, x='other_layers_combine_operator': self.layer_property_changed(x, state))]},
                                    "GEOMETRIC_PREDICATES":{"TYPE":"CheckableComboBox", "WIDGET":self.comboBox_filtering_geometric_predicates, "SIGNALS":[("checkedItemsChanged", lambda state, x='geometric_predicates': self.layer_property_changed(x, state))]},
                                    "BUFFER_VALUE":{"TYPE":"QgsDoubleSpinBox", "WIDGET":self.mQgsDoubleSpinBox_filtering_buffer_value, "SIGNALS":[("valueChanged", lambda state, x='buffer_value': self.layer_property_changed(x, state))]},
                                    "BUFFER_VALUE_PROPERTY":{"TYPE":"PropertyOverrideButton", "WIDGET":self.mPropertyOverrideButton_filtering_buffer_value_property, "SIGNALS":[("activated", lambda state, x='buffer_value_property', custom_functions={"ON_CHANGE": lambda x: self.filtering_buffer_property_changed(), "CUSTOM_DATA": lambda x: self.get_buffer_property_state()}: self.layer_property_changed(x, state, custom_functions))]},
                                    "BUFFER_VALUE_EXPRESSION":{"TYPE":"LineEdit", "WIDGET":self.lineEdit_filtering_buffer_value_expression, "SIGNALS":[("textEdited", lambda state, x='buffer_value_expression', custom_functions={"ON_CHANGE": lambda x: self.filtering_buffer_expression_edited()}: self.layer_property_changed(x, state, custom_functions)), ("textChanged", lambda state, x='buffer_value_expression', custom_functions={"ON_CHANGE": lambda x: self.filtering_buffer_expression_edited()}: self.layer_property_changed(x, state, custom_functions))]},
                                    "BUFFER_TYPE":{"TYPE":"ComboBox", "WIDGET":self.comboBox_filtering_buffer_type, "SIGNALS":[("currentTextChanged", lambda state, x='buffer_type': self.layer_property_changed(x, state))]},
                                    }
        
        self.widgets["EXPORTING"] = {
                                    "HAS_LAYERS_TO_EXPORT":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_layers, "SIGNALS":[("clicked", lambda state, x='has_layers_to_export': self.project_property_changed(x, state))], "ICON":None},
                                    "HAS_PROJECTION_TO_EXPORT":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_projection, "SIGNALS":[("clicked", lambda state, x='has_projection_to_export': self.project_property_changed(x, state))], "ICON":None},
                                    "HAS_STYLES_TO_EXPORT":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_styles, "SIGNALS":[("clicked", lambda state, x='has_styles_to_export': self.project_property_changed(x, state))], "ICON":None},
                                    "HAS_DATATYPE_TO_EXPORT":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_datatype, "SIGNALS":[("clicked", lambda state, x='has_datatype_to_export': self.project_property_changed(x, state))], "ICON":None},
                                    "HAS_OUTPUT_FOLDER_TO_EXPORT":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_output_folder, "SIGNALS":[("clicked", lambda state, x='has_output_folder_to_export', custom_functions={"ON_CHANGE": lambda x: self.dialog_export_output_path()}: self.project_property_changed(x, state, custom_functions))], "ICON":None},
                                    "HAS_ZIP_TO_EXPORT":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_zip, "SIGNALS":[("clicked", lambda state, x='has_zip_to_export', custom_functions={"ON_CHANGE": lambda x: self.dialog_export_output_pathzip()}: self.project_property_changed(x, state, custom_functions))], "ICON":None},
                                    "LAYERS_TO_EXPORT":{"TYPE":"CustomCheckableLayerComboBox", "WIDGET":self.checkableComboBoxLayer_exporting_layers, "CUSTOM_LOAD_FUNCTION": lambda x: self.get_layers_to_export(), "SIGNALS":[("checkedItemsChanged", lambda state, custom_functions={"CUSTOM_DATA": lambda x: self.get_layers_to_export()}, x='layers_to_export': self.project_property_changed(x, state, custom_functions))]},
                                    "PROJECTION_TO_EXPORT":{"TYPE":"QgsProjectionSelectionWidget", "WIDGET":self.mQgsProjectionSelectionWidget_exporting_projection, "SIGNALS":[("crsChanged", lambda state, x='projection_to_export', custom_functions={"CUSTOM_DATA": lambda x: self.get_current_crs_authid()}: self.project_property_changed(x, state, custom_functions))]},
                                    "STYLES_TO_EXPORT":{"TYPE":"ComboBox", "WIDGET":self.comboBox_exporting_styles, "SIGNALS":[("currentTextChanged", lambda state, x='styles_to_export': self.project_property_changed(x, state))]},
                                    "DATATYPE_TO_EXPORT":{"TYPE":"ComboBox", "WIDGET":self.comboBox_exporting_datatype, "SIGNALS":[("currentTextChanged", lambda state, x='datatype_to_export': self.project_property_changed(x, state))]},
                                    "OUTPUT_FOLDER_TO_EXPORT":{"TYPE":"LineEdit", "WIDGET":self.lineEdit_exporting_output_folder, "SIGNALS":[("textEdited", lambda state, x='output_folder_to_export', custom_functions={"ON_CHANGE": lambda x: self.reset_export_output_path()}: self.project_property_changed(x, state, custom_functions))]},
                                    "ZIP_TO_EXPORT":{"TYPE":"LineEdit", "WIDGET":self.lineEdit_exporting_zip, "SIGNALS":[("textEdited", lambda state, x='zip_to_export', custom_functions={"ON_CHANGE": lambda x: self.reset_export_output_pathzip()}: self.project_property_changed(x, state, custom_functions))]}
                                    }
            

    
        self.widgets["QGIS"] = {
                                "LAYER_TREE_VIEW":{"TYPE":"LayerTreeView", "WIDGET":self.iface.layerTreeView(), "SIGNALS":[("currentLayerChanged", self.current_layer_changed)]}
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
        
        self.CONFIGURATION.layout().insertWidget(0, self.config_view)

        self.config_view.setModel(self.config_model)

        self.config_view.setStyleSheet("""padding:0px;
                                    color:black;""")

        self.config_view.setAnimated(True)
        self.config_view.setEnabled(True)
        self.config_view.show()


        
    def manage_output_name(self):
        self.output_name = 'export'
        self.current_project_title = self.PROJECT.fileName().split('.')[0]
        self.current_project_path = self.PROJECT.homePath()
        if self.current_project_title is not None:
            self.output_name = 'export' + '_' + str(self.current_project_title)


    def set_widget_icon(self, config_widget_path):

        if self.widgets_initialized is True:

            if len(config_widget_path) == 6:

                config_path = self.CONFIG_DATA[config_widget_path[0]][config_widget_path[1]][config_widget_path[2]][config_widget_path[3]][config_widget_path[4]][config_widget_path[5]]

                if isinstance(config_path, dict):
                    if "ICON_ON_FALSE" in config_path:    
                        file = config_path["ICON_ON_FALSE"]
                        file_path = os.path.join(self.plugin_dir, "icons", file)
                        self.widgets[config_widget_path[4]][config_widget_path[5]]["ICON_ON_FALSE"] = file_path

                    if "ICON_ON_TRUE" in config_path:
                        file = config_path["ICON_ON_TRUE"]
                        file_path = os.path.join(self.plugin_dir, "icons", file)
                        self.widgets[config_widget_path[4]][config_widget_path[5]]["ICON_ON_TRUE"] = file_path

                elif isinstance(config_path, str):
                    file_path = os.path.join(self.plugin_dir, "icons", config_path)
                    self.widgets[config_widget_path[4]][config_widget_path[5]]["ICON"] = file_path

                icon = QtGui.QIcon(file_path)
                self.widgets[config_widget_path[4]][config_widget_path[5]]["WIDGET"].setIcon(icon)


    def switch_widget_icon(self, widget_path, state):
        if state is True:
            icon = QtGui.QIcon(self.widgets[widget_path[0].upper()][widget_path[1].upper()]["ICON_ON_TRUE"])
        else:
            icon = QtGui.QIcon(self.widgets[widget_path[0].upper()][widget_path[1].upper()]["ICON_ON_FALSE"])
        self.widgets[widget_path[0].upper()][widget_path[1].upper()]["WIDGET"].setIcon(icon)


    def icon_per_geometry_type(self, geometry_type):
        """
        Get icon for geometry type with caching.
        
        Icons are cached statically to avoid repeated QgsLayerItem calls,
        improving performance when displaying multiple layers.
        
        Args:
            geometry_type (str): Geometry type string (e.g., 'GeometryType.Point')
        
        Returns:
            QIcon: Icon for the geometry type
        """
        # Check cache first
        if geometry_type in self._icon_cache:
            return self._icon_cache[geometry_type]
        
        # Calculate and cache the icon
        if geometry_type == 'GeometryType.Line':
            icon = QgsLayerItem.iconLine()
        elif geometry_type == 'GeometryType.Point':
            icon = QgsLayerItem.iconPoint()
        elif geometry_type == 'GeometryType.Polygon':
            icon = QgsLayerItem.iconPolygon()
        elif geometry_type == 'GeometryType.UnknownGeometry':
            icon = QgsLayerItem.iconTable()
        else:
            icon = QgsLayerItem.iconDefault()
        
        # Cache for future use
        self._icon_cache[geometry_type] = icon
        return icon
        
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
                            self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].addItem(layer_icon, layer_name + ' [%s]' % (layer_crs_authid), key)
                            item = self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].model().item(i)
                            if len(layer_props["filtering"]["layers_to_filter"]) > 0:
                                if layer_id in list(layer_id for layer_id in list(layer_props["filtering"]["layers_to_filter"])):
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
                            self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].addItem(layer_icon, layer_name + ' [%s]' % (layer_crs_authid), key)
                            item = self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].model().item(i)
                            item.setCheckState(Qt.Unchecked)
                            i += 1    
            
            except Exception as e:
                self.exception = e
                print(self.exception)
                self.resetLayerVariableOnErrorEvent(layer, self.exception)

    def exporting_populate_combobox(self):

        if self.widgets_initialized is True and self.has_loaded_layers is True:

            layers_to_export = []
            datatype_to_export = ''

            if self.project_props['EXPORTING']['HAS_LAYERS_TO_EXPORT'] is True:
                layers_to_export = self.project_props['EXPORTING']['LAYERS_TO_EXPORT']
            
            if self.project_props['EXPORTING']['HAS_DATATYPE_TO_EXPORT'] is True:
                datatype_to_export = self.project_props['EXPORTING']['DATATYPE_TO_EXPORT']


            self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].clear()
            for i, key in enumerate(self.PROJECT_LAYERS):
                layer_name = self.PROJECT_LAYERS[key]["infos"]["layer_name"]
                layer_crs_authid = self.PROJECT_LAYERS[key]["infos"]["layer_crs_authid"]
                layer_icon = self.icon_per_geometry_type(self.PROJECT_LAYERS[key]["infos"]["layer_geometry_type"])
                layer_name = layer_name + ' [%s]' % (layer_crs_authid)
                self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].addItem(layer_icon, layer_name, key)
                item = self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].model().item(i)
                if key in layers_to_export:
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
        
        toolBox_tabTools =  """QWidget
                                {
                                background: {color_1};
                                }
                                QScrollBar:vertical 
                                {
                                border: none;
                                background: transparent;
                                width:5px;
                                }
                                QScrollBar::handle:vertical {
                                border: none;
                                background: {color_2};
                                width:3px;
                                }
                                QScrollBar::add-line:vertical {
                                background: transparent;
                                height: 3px;
                                subcontrol-position: bottom;
                                subcontrol-origin: margin;
                                }
                                QScrollBar::sub-line:vertical {
                                background: transparent;
                                height: 3px;
                                subcontrol-position: top;
                                subcontrol-origin: margin;
                                }
                                QScrollBar:horizontal {
                                border: none;
                                background: transparent;
                                height:5px;
                                }
                                QScrollBar::handle:horizontal {
                                border: none;
                                background: {color_2};
                                height:3px;
                                }
                                QScrollBar::add-line:horizontal {
                                background: transparent;
                                width: 3px;
                                subcontrol-position: right;
                                subcontrol-origin: margin;
                                }
                                QScrollBar::sub-line:horizontal {
                                background: transparent;
                                width: 3px;
                                subcontrol-position: left;
                                subcontrol-origin: margin;
                                }"""

        dock_style = """
                        QDockWidget
                        {
                        background: {color_1};
                        }
                        QWidget
                        {
                        background: {color_1};
                        }"""
        
        expressionBuilder_style = """QgsExpressionBuilderWidget
                            {
                            background-color: {color_1};
                            border-color: rgb(0, 0, 0);
                            border-radius:6px;
                            padding: 10px 10px 10px 10px;
                            color:{color_3}
                            }"""
        
        scroll_area_style =  """QScrollArea
                            {
                            background-color: {color_1};
                            color:{color_3}
                            }
                            QWidget
                            {
                            background: {color_1};
                            }
                            QScrollBar:vertical 
                            {
                            border: none;
                            background: transparent;
                            width:5px;
                            }
                            QScrollBar::handle:vertical {
                            border: none;
                            background: {color_2};
                            width:3px;
                            }
                            QScrollBar::add-line:vertical {
                            background: transparent;
                            height: 3px;
                            subcontrol-position: bottom;
                            subcontrol-origin: margin;
                            }
                            QScrollBar::sub-line:vertical {
                            background: transparent;
                            height: 3px;
                            subcontrol-position: top;
                            subcontrol-origin: margin;
                            }
                            QScrollBar:horizontal {
                            border: none;
                            background: transparent;
                            height:5px;
                            }
                            QScrollBar::handle:horizontal {
                            border: none;
                            background: {color_2};
                            height:3px;
                            }
                            QScrollBar::add-line:horizontal {
                            background: transparent;
                            width: 3px;
                            subcontrol-position: right;
                            subcontrol-origin: margin;
                            }
                            QScrollBar::sub-line:horizontal {
                            background: transparent;
                            width: 3px;
                            subcontrol-position: left;
                            subcontrol-origin: margin;
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
        
        lineEdit_style = """QLineEdit 
                            {
                            background-color: {color_2};
                            color:{color_1};
                            border-radius: 3px;
                            padding: 3px 3px 3px 3px;
                            }
                            QLineEdit:hover
                            {
                            border: 2px solid black;
                            }
                            """
        
        qgsDoubleSpinBox_style = """QgsDoubleSpinBox {
                                    background-color: {color_2};
                                    color:{color_1};
                                    border-radius: 3px;
                                    padding: 3px 3px 3px 3px;
                                    }
                                    QgsDoubleSpinBox:hover
                                    {
                                    border: 2px solid black;
                                    }
                                    """
        
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

        propertyOverrideButton_style =  """QgsPropertyOverrideButton 
                                        {
                                        background-color: {color_1};
                                        color:{color_3};
                                        border-radius: 3px;
                                        padding: 3px 3px 3px 3px;
                                        }
                                        QgsPropertyOverrideButton:hover
                                        {
                                        border: 2px solid black;
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
                                        }"""


        splitter_style = """QSplitter::handle {
                            background: {color_1};
                            }
                            QSplitter::handle:hover {
                            background: {color_2};
                            }"""

        comboBox_style = comboBox_style.replace("{color_1}",self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["BACKGROUND"][1]).replace("{color_2}",self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["BACKGROUND"][2]).replace("{color_3}",self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["FONT"][1])

        propertyOverrideButton_style = propertyOverrideButton_style.replace("{color_1}",self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["BACKGROUND"][1]).replace("{color_2}",self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["BACKGROUND"][2]).replace("{color_3}",self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["FONT"][1])

        dock_style = dock_style.replace("{color_1}",self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["BACKGROUND"][1])

        frame_actions_style = frame_style.replace("{color_1}",self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["BACKGROUND"][0]).replace("{color_3}",self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["FONT"][1])

        frame_style = frame_style.replace("{color_1}",self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["BACKGROUND"][0]).replace("{color_3}",self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["FONT"][1])
        
        toolBox_tabTools = toolBox_tabTools.replace("{color_1}",self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["BACKGROUND"][0]).replace("{color_2}",self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["BACKGROUND"][1])

        scroll_area_style = scroll_area_style.replace("{color_1}",self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["BACKGROUND"][0]).replace("{color_3}",self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["FONT"][1]).replace("{color_2}",self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["BACKGROUND"][1])

        collapsibleGroupBox_style = collapsibleGroupBox_style.replace("{color_1}",self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["BACKGROUND"][0]).replace("{color_3}",self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["FONT"][1])

        lineEdit_style = lineEdit_style.replace("{color_1}",self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["FONT"][1]).replace("{color_2}",self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["BACKGROUND"][1])

        qgsDoubleSpinBox_style = qgsDoubleSpinBox_style.replace("{color_1}",self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["FONT"][1]).replace("{color_2}",self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["BACKGROUND"][1])

        splitter_style = splitter_style.replace("{color_1}", self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["BACKGROUND"][1]).replace("{color_2}", self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["BACKGROUND"][3])

        
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
        #self.FilterMateDockWidgetBase.setStyleSheet(dock_style)
        self.dockWidgetContents.setStyleSheet(dock_style)

        self.widgets["DOCK"]["TOOLS"]["WIDGET"].setStyleSheet("""background-color: {};
                                                        border-color: rgb(0, 0, 0);
                                                        border-radius:6px;
                                                        padding: 10px 10px 10px 10px;
                                                        color:{};""".format(self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["BACKGROUND"][0],self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["FONT"][0]))
        
        self.splitter.setStyleSheet(splitter_style)
        self.frame_actions.setStyleSheet(frame_actions_style)
        self.frame_exploring.setStyleSheet(frame_style)
        self.frame_toolset.setStyleSheet(frame_style)

        self.toolBox_tabTools.setStyleSheet(toolBox_tabTools)
        self.scrollArea_frame_exploring.setStyleSheet(scroll_area_style)

        self.mGroupBox_exploring_single_selection.setStyleSheet(collapsibleGroupBox_style)
        self.mGroupBox_exploring_multiple_selection.setStyleSheet(collapsibleGroupBox_style)
        self.mGroupBox_exploring_custom_selection.setStyleSheet(collapsibleGroupBox_style)
        

        # self.CONFIGURATION.setStyleSheet("""background-color: {};
        #                                     border-color: rgb(0, 0, 0);
        #                                     border-radius:6px;
        #                                     marging: 25px 10px 10px 10px;
        #                                     color:{};""".format(self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["BACKGROUND"][0],self.CONFIG_DATA["APP"]["DOCKWIDGET"]['COLORS']["FONT"][0]))
        
        

        pushButton_config_path = ['APP','DOCKWIDGET','PushButton']
        pushButton_config = self.CONFIG_DATA[pushButton_config_path[0]][pushButton_config_path[1]][pushButton_config_path[2]]
        pushButton_style = json.dumps(pushButton_config["STYLE"])[1:-1].replace(': {', ' {').replace('\"', '').replace(',', '')
        icons_sizes = {}
        icon_size = 20
        if "ICONS_SIZES" in pushButton_config:
            if "ACTION" in pushButton_config["ICONS_SIZES"]:
                icons_sizes["ACTION"] = pushButton_config["ICONS_SIZES"]["ACTION"]
            if "OTHERS" in pushButton_config["ICONS_SIZES"]:
                icons_sizes["OTHERS"] = pushButton_config["ICONS_SIZES"]["OTHERS"]


        font = QFont("Segoe UI Semibold", 8)
        font.setBold(True)

        for widget_group in self.widgets:
            for widget_name in self.widgets[widget_group]:
                if self.widgets[widget_group][widget_name]["TYPE"] == "PushButton":
                    self.set_widget_icon(pushButton_config_path + ["ICONS", widget_group, widget_name])
                    self.widgets[widget_group][widget_name]["WIDGET"].setStyleSheet(pushButton_style)
                    self.widgets[widget_group][widget_name]["WIDGET"].setCursor(Qt.PointingHandCursor)
                    if widget_group in icons_sizes:
                        icon_size = icons_sizes[widget_group]    
                    else:
                        icon_size = icons_sizes["OTHERS"]

                    self.widgets[widget_group][widget_name]["WIDGET"].setIconSize(QtCore.QSize(icon_size, icon_size))
                    self.widgets[widget_group][widget_name]["WIDGET"].setMinimumHeight(icon_size*2)
                    self.widgets[widget_group][widget_name]["WIDGET"].setMaximumHeight(icon_size*2)
                    self.widgets[widget_group][widget_name]["WIDGET"].setMinimumWidth(icon_size*2)
                    self.widgets[widget_group][widget_name]["WIDGET"].setMaximumWidth(icon_size*2)
                    self.widgets[widget_group][widget_name]["WIDGET"].setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
                    self.widgets[widget_group][widget_name]["WIDGET"].setFont(font)
                elif self.widgets[widget_group][widget_name]["TYPE"].find("ComboBox") >= 0:
                    self.widgets[widget_group][widget_name]["WIDGET"].setStyleSheet(comboBox_style)
                    self.widgets[widget_group][widget_name]["WIDGET"].setCursor(Qt.PointingHandCursor)
                    self.widgets[widget_group][widget_name]["WIDGET"].setFont(font)
                elif self.widgets[widget_group][widget_name]["TYPE"].find("QgsFieldExpressionWidget") >= 0:
                    self.widgets[widget_group][widget_name]["WIDGET"].setStyleSheet(comboBox_style)
                    self.widgets[widget_group][widget_name]["WIDGET"].setCursor(Qt.PointingHandCursor)
                    self.widgets[widget_group][widget_name]["WIDGET"].setFont(font)
                elif self.widgets[widget_group][widget_name]["TYPE"].find("LineEdit") >= 0:
                    self.widgets[widget_group][widget_name]["WIDGET"].setStyleSheet(lineEdit_style)
                    self.widgets[widget_group][widget_name]["WIDGET"].setCursor(Qt.IBeamCursor)
                    self.widgets[widget_group][widget_name]["WIDGET"].setFont(font)
                elif self.widgets[widget_group][widget_name]["TYPE"].find("QgsDoubleSpinBox") >= 0:
                    self.widgets[widget_group][widget_name]["WIDGET"].setStyleSheet(qgsDoubleSpinBox_style)
                    self.widgets[widget_group][widget_name]["WIDGET"].setCursor(Qt.IBeamCursor)
                    self.widgets[widget_group][widget_name]["WIDGET"].setFont(font)
                elif self.widgets[widget_group][widget_name]["TYPE"].find("PropertyOverrideButton") >= 0:
                    self.widgets[widget_group][widget_name]["WIDGET"].setStyleSheet(propertyOverrideButton_style)
                    self.widgets[widget_group][widget_name]["WIDGET"].setCursor(Qt.PointingHandCursor)
                    self.widgets[widget_group][widget_name]["WIDGET"].setFont(font)
                elif self.widgets[widget_group][widget_name]["TYPE"].find("QgsProjectionSelectionWidget") >= 0:
                    self.widgets[widget_group][widget_name]["WIDGET"].setStyleSheet(comboBox_style)
                    self.widgets[widget_group][widget_name]["WIDGET"].setCursor(Qt.PointingHandCursor)
                    self.widgets[widget_group][widget_name]["WIDGET"].setFont(font)
                _
        icon_size = icons_sizes["OTHERS"]
        for widget in [self.widget_exploring_keys, self.widget_filtering_keys, self.widget_exporting_keys]:
            # widget.setMinimumHeight(icon_size*2)
            # widget.setMaximumHeight(icon_size*2)
            widget.setMinimumWidth(icon_size*3)
            widget.setMaximumWidth(icon_size*3)
            widget.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        
        icon_size = icons_sizes["ACTION"]
        self.frame_actions.setMinimumHeight(icon_size*3)
        self.frame_actions.setMaximumHeight(icon_size*3)
        self.frame_actions.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        
        
        

    def set_widgets_enabled_state(self, state):
        for widget_group in self.widgets:
            for widget_name in self.widgets[widget_group]:
                if self.widgets[widget_group][widget_name]["TYPE"] not in ("JsonTreeView","LayerTreeView","JsonModel","ToolBox"):
                    if self.widgets[widget_group][widget_name]["TYPE"] in ("PushButton", "GroupBox"):
                        if self.widgets[widget_group][widget_name]["WIDGET"].isCheckable():
                            if state is False:
                                self.widgets[widget_group][widget_name]["WIDGET"].setChecked(state)
                                if self.widgets[widget_group][widget_name]["TYPE"] == "GroupBox":
                                    self.widgets[widget_group][widget_name]["WIDGET"].setCollapsed(True)
                    self.widgets[widget_group][widget_name]["WIDGET"].setEnabled(state)



    def connect_widgets_signals(self):
        """SET INTERACTIONS"""
        for widget_group in self.widgets:
            if widget_group != 'QGIS':
                for widget in self.widgets[widget_group]:
                    try:
                        self.manageSignal([widget_group, widget], 'connect')
                    except (AttributeError, RuntimeError, TypeError) as e:
                        # Widget may not exist or signal not available
                        pass

    def disconnect_widgets_signals(self):
        """SET INTERACTIONS"""
        for widget_group in self.widgets:
            if widget_group != 'QGIS':
                for widget in self.widgets[widget_group]:
                    try:
                        self.manageSignal([widget_group, widget], 'disconnect')
                    except (AttributeError, RuntimeError, TypeError) as e:
                        # Widget may not exist or signal not connected
                        pass


    def manage_interactions(self):



        """INIT"""

        self.coordinateReferenceSystem = QgsCoordinateReferenceSystem()
        self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"].setExpressionsEnabled(True)
        self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"].setClearValue(0.0)
        if self.PROJECT:
            self.widgets["EXPORTING"]["PROJECTION_TO_EXPORT"]["WIDGET"].setCrs(self.PROJECT.crs())
        self.set_widgets_enabled_state(self.has_loaded_layers)
        self.filtering_populate_predicates_chekableCombobox()    

        if self.has_loaded_layers is True:
            self.connect_widgets_signals()


        self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].clicked.connect(lambda state, x='single_selection': self.exploring_groupbox_changed(x))
        self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].clicked.connect(lambda state, x='multiple_selection': self.exploring_groupbox_changed(x))
        self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].clicked.connect(lambda state, x='custom_selection': self.exploring_groupbox_changed(x))
        self.widgets["DOCK"]["TOOLS"]["WIDGET"].currentChanged.connect(self.select_tabTools_index)
        #self.widgets["DOCK"]["CONFIGURATION_MODEL"]["WIDGET"].itemChanged.connect(self.data_changed_configuration_model)
        # self.widgets["DOCK"]["CONFIGURATION_MODEL"]["WIDGET"].dataChanged.connect(self.save_configuration_model)
        # self.widgets["DOCK"]["CONFIGURATION_MODEL"]["WIDGET"].rowsInserted.connect(self.save_configuration_model)
        # self.widgets["DOCK"]["CONFIGURATION_MODEL"]["WIDGET"].rowsRemoved.connect(self.save_configuration_model)
        # self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].filterExpressionChanged()
        
        # self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].contextMenuEvent
        # self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].contextMenuEvent

        if self.init_layer != None and isinstance(self.init_layer, QgsVectorLayer):
            self.manage_output_name()
            self.exporting_populate_combobox()
            self.set_exporting_properties()
            self.exploring_groupbox_init()
            self.current_layer_changed(self.init_layer)
            self.filtering_auto_current_layer_changed()

            
    def select_tabTools_index(self):
        
        if self.widgets_initialized is True:

            self.tabTools_current_index = self.widgets["DOCK"]["TOOLS"]["WIDGET"].currentIndex()
            if self.tabTools_current_index == 1:
                self.widgets["ACTION"]["EXPORT"]["WIDGET"].setEnabled(True)
            else:
                self.widgets["ACTION"]["EXPORT"]["WIDGET"].setEnabled(False)

            self.set_exporting_properties()


    def exploring_groupbox_init(self):

        if self.widgets_initialized is True:
            self.properties_group_state_enabler(self.layer_properties_tuples_dict["selection_expression"]) 

            exploring_groupbox = "custom_selection"

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
    
  

                self.current_exploring_groupbox = "single_selection"

                self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setChecked(True)
                self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setCollapsed(False)

                self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setCollapsed(True)

                self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setCollapsed(True)
                

                if self.current_layer != None:
                    self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'connect', 'featureChanged')
                    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'filteringCheckedItemList')
                    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'updatingCheckedItemList')

                    self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setEnabled(True)
                    self.widgets["EXPLORING"]["SINGLE_SELECTION_EXPRESSION"]["WIDGET"].setEnabled(True)

                    self.exploring_features_changed(self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].feature())
                else:
                    self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
                    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')



            elif groupbox == "multiple_selection":

     
                    
                self.current_exploring_groupbox = "multiple_selection"



                self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setChecked(True)
                self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setCollapsed(False)

                self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setCollapsed(True)

                self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setCollapsed(True)



                if self.current_layer != None:
                    self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect', 'featureChanged')
                    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect')

                    self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setEnabled(True)
                    self.widgets["EXPLORING"]["MULTIPLE_SELECTION_EXPRESSION"]["WIDGET"].setEnabled(True)

                    layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
                    self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setLayer(self.current_layer, layer_props)

                    self.exploring_features_changed(self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentSelectedFeatures(), True)
                else:
                    self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
                    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')

            elif groupbox == "custom_selection":


                    
                self.current_exploring_groupbox = "custom_selection"
                
                self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setChecked(True)
                self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setCollapsed(False)

                self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setCollapsed(True)

                self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setCollapsed(True)



                if self.current_layer != None:
                    self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect', 'featureChanged')
                    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'filteringCheckedItemList')
                    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'updatingCheckedItemList')

                    self.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"].setEnabled(True)
                    self.exploring_custom_selection()
                else:
                    self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
                    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')


    def exploring_identify_clicked(self):

        features = []
        expression = None

        if self.widgets_initialized is True and self.current_layer != None:

            features, expression = self.get_current_features()
            
            if len(features) == 0:
                return
            else:
                self.iface.mapCanvas().flashFeatureIds(self.current_layer, [feature.id() for feature in features], startColor=QColor(235, 49, 42, 255), endColor=QColor(237, 97, 62, 25), flashes=6, duration=400)


    def get_current_features(self):

        if self.widgets_initialized is True and self.current_layer != None:

            features = []    
            expression = ''

            if self.current_exploring_groupbox == "single_selection":
                input = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].feature()
                features, expression = self.get_exploring_features(input, True)

            elif self.current_exploring_groupbox == "multiple_selection":
                input = self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].checkedItems()
                features, expression = self.get_exploring_features(input, True)

            elif self.current_exploring_groupbox == "custom_selection":
                expression = self.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"].expression()
                if QgsExpression(expression).isField() is False:
                    features, expression = self.exploring_custom_selection()


                
            return features, expression
        
        return [], ''
        

    def exploring_zoom_clicked(self, features=[]):

        if self.widgets_initialized is True and self.current_layer != None:

            if not features or len(features) == 0:   
                features, expression = self.get_current_features()
            

            self.zooming_to_features(features)


    def zooming_to_features(self, features):
        
        if self.widgets_initialized is True and self.current_layer != None:

            # Safety check: ensure features is a list
            if not features or not isinstance(features, list) or len(features) == 0:        
                extent = self.current_layer.extent()
                self.iface.mapCanvas().zoomToFeatureExtent(extent) 

            else: 
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


            if self.current_exploring_groupbox == "single_selection":

                expression = self.widgets["EXPLORING"]["SINGLE_SELECTION_EXPRESSION"]["WIDGET"].expression()
                if expression != None and layer_props["exploring"]["single_selection_expression"] != expression:
                    self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["single_selection_expression"] = expression
                    self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression(expression)

            elif self.current_exploring_groupbox == "multiple_selection":

                expression = self.widgets["EXPLORING"]["MULTIPLE_SELECTION_EXPRESSION"]["WIDGET"].expression()
                if expression != None and layer_props["exploring"]["multiple_selection_expression"] != expression:
                    self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["multiple_selection_expression"] = expression

                layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
                self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setLayer(self.current_layer, layer_props)
                self.exploring_link_widgets()

            elif self.current_exploring_groupbox == "custom_selection":

                expression = self.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"].expression()
                if expression != None and layer_props["exploring"]["custom_selection_expression"] != expression:
                    self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["custom_selection_expression"] = expression
                    self.exploring_link_widgets(expression)

            self.get_current_features()

 


    def exploring_custom_selection(self):

        if self.widgets_initialized is True and self.current_layer != None:

            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
            expression = layer_props["exploring"]["custom_selection_expression"]
            features = []
            if QgsExpression(expression).isField() is False:
                features = self.exploring_features_changed([], False, expression)

            return features, expression
        
        return [], ''
    

    def exploring_deselect_features(self):

        if self.widgets_initialized is True and self.current_layer != None:

            if self.current_layer == None:
                return
            
            self.current_layer.removeSelection()
        


    
    def exploring_features_changed(self, input=[], identify_by_primary_key_name=False, custom_expression=None):

        if self.widgets_initialized is True and self.current_layer != None and isinstance(self.current_layer, QgsVectorLayer):
            
            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
            features, expression = self.get_exploring_features(input, identify_by_primary_key_name, custom_expression)

     
            self.exploring_link_widgets()

            self.current_layer.removeSelection()

            if len(features) == 0:
                return []
        
            if layer_props["exploring"]["is_selecting"] == True:
                self.current_layer.removeSelection()
                self.current_layer.select([feature.id() for feature in features])

            if layer_props["exploring"]["is_tracking"] == True:
                self.zooming_to_features(features)  

            return features
        
        return []


    def get_exploring_features(self, input, identify_by_primary_key_name=False, custom_expression=None):

        if self.widgets_initialized is True and self.current_layer != None:

            if self.current_layer == None:
                return [], None
            
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
            layer_features_source = self.current_layer.dataProvider().featureSource() 
            
            if layer_props["exploring"]["is_linking"] == True:
                   

                if QgsExpression(layer_props["exploring"]["custom_selection_expression"]).isValid() is True:
                    if QgsExpression(layer_props["exploring"]["custom_selection_expression"]).isField() is False:
                        custom_filter = layer_props["exploring"]["custom_selection_expression"]
                        self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setFilterExpression(custom_filter, layer_props)
                if expression != None:
                    self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setFilterExpression(expression)
                elif self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentSelectedFeatures() != False:
                    features, expression = self.get_exploring_features(self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentSelectedFeatures(), True)
                    if len(features) > 0 and expression != None:
                        self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setFilterExpression(expression)
                elif self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentVisibleFeatures() != False:
                    features, expression = self.get_exploring_features(self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentVisibleFeatures(), True)
                    if len(features) > 0 and expression != None:
                        self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setFilterExpression(expression)
                elif custom_filter != None:
                    self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setFilterExpression(custom_filter)
                
                multiple_display_expression = layer_props["exploring"]["multiple_selection_expression"]
                if QgsExpression(multiple_display_expression).isField():
                    multiple_display_expression = multiple_display_expression.replace('"','')

                single_display_expression = layer_props["exploring"]["single_selection_expression"]
                if QgsExpression(single_display_expression).isField():
                    single_display_expression = single_display_expression.replace('"','')

                if QgsExpression(single_display_expression).isValid() and single_display_expression == layer_props["infos"]["primary_key_name"]:
                    if QgsExpression(multiple_display_expression).isValid() and multiple_display_expression != layer_props["infos"]["primary_key_name"]:
                        self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["single_selection_expression"] = multiple_display_expression
                        self.widgets["EXPLORING"]["SINGLE_SELECTION_EXPRESSION"]["WIDGET"].setExpression(multiple_display_expression)
                        self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression(multiple_display_expression)

                if QgsExpression(multiple_display_expression).isValid() and multiple_display_expression == layer_props["infos"]["primary_key_name"]:
                    if QgsExpression(single_display_expression).isValid() and single_display_expression != layer_props["infos"]["primary_key_name"]:
                        self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["multiple_selection_expression"] = single_display_expression
                        self.widgets["EXPLORING"]["MULTIPLE_SELECTION_EXPRESSION"]["WIDGET"].setExpression(single_display_expression)
                        self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression(single_display_expression)

            
            else:
                self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setFilterExpression('')
                self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setFilterExpression('', layer_props)


    def get_layers_to_filter(self):

        if self.widgets_initialized is True and self.current_layer != None:

            checked_list_data = []
            for i in range(self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].count()):
                if self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].itemCheckState(i) == Qt.Checked:
                    data = self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].itemData(i, Qt.UserRole)
                    if isinstance(data, str):
                        checked_list_data.append(data)
            return checked_list_data


    def get_layers_to_export(self):

        if self.widgets_initialized is True and self.current_layer != None:

            checked_list_data = []
            for i in range(self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].count()):
                if self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].itemCheckState(i) == Qt.Checked:
                    data = self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].itemData(i, Qt.UserRole)
                    if isinstance(data, str):
                        checked_list_data.append(data)
            return checked_list_data


    def get_current_crs_authid(self):
        
        if self.widgets_initialized is True and self.has_loaded_layers is True:

            return self.widgets["EXPORTING"]["PROJECTION_TO_EXPORT"]["WIDGET"].crs().authid()


    def current_layer_changed(self, layer):

        try:
            if self.widgets_initialized is True:


                if layer != None:  
                    self.current_layer = layer
                else:
                    return

                layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
            

                widgets_to_stop =   [
                                        ["EXPLORING","SINGLE_SELECTION_FEATURES"],
                                        ["EXPLORING","SINGLE_SELECTION_EXPRESSION"],
                                        ["EXPLORING","MULTIPLE_SELECTION_FEATURES"],
                                        ["EXPLORING","MULTIPLE_SELECTION_EXPRESSION"],
                                        ["EXPLORING", "CUSTOM_SELECTION_EXPRESSION"],
                                        ["EXPLORING", "IS_SELECTING"],
                                        ["EXPLORING", "IS_TRACKING"],
                                        ["EXPLORING", "IS_LINKING"],
                                        ["EXPLORING", "RESET_ALL_LAYER_PROPERTIES"],
                                        ["FILTERING","CURRENT_LAYER"],
                                        ["FILTERING","HAS_LAYERS_TO_FILTER"],
                                        ["FILTERING", "LAYERS_TO_FILTER"],
                                        ["FILTERING","HAS_COMBINE_OPERATOR"],
                                        ["FILTERING","SOURCE_LAYER_COMBINE_OPERATOR"],
                                        ["FILTERING", "OTHER_LAYERS_COMBINE_OPERATOR"],
                                        ["FILTERING","HAS_GEOMETRIC_PREDICATES"],
                                        ["FILTERING", "GEOMETRIC_PREDICATES"],
                                        ["FILTERING","HAS_BUFFER_VALUE"],
                                        ["FILTERING","BUFFER_VALUE"],
                                        ["FILTERING","BUFFER_VALUE_PROPERTY"],
                                        ["FILTERING", "BUFFER_VALUE_EXPRESSION"],
                                        ["FILTERING","HAS_BUFFER_TYPE"],
                                        ["FILTERING","BUFFER_TYPE"]
                                    ]
                
                for widget_path in widgets_to_stop:
                    self.manageSignal(widget_path, 'disconnect')

                if self.project_props["OPTIONS"]["LAYERS"]["LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"] is True:
                    widget_path = ["QGIS","LAYER_TREE_VIEW"]
                    self.manageSignal(widget_path, 'disconnect')

            


                lastLayer = self.widgets["FILTERING"]["CURRENT_LAYER"]["WIDGET"].currentLayer()
                if lastLayer != None and lastLayer.id() != self.current_layer.id():
                    self.widgets["FILTERING"]["CURRENT_LAYER"]["WIDGET"].setLayer(self.current_layer)

                # Update backend indicator
                if 'provider_type' in layer_props.get('infos', {}):
                    self._update_backend_indicator(layer_props['infos']['provider_type'])

                """SINGLE SELECTION"""
                self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setLayer(self.current_layer)
                self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression(layer_props["exploring"]["single_selection_expression"])
                self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setFetchGeometry(True)
                self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setShowBrowserButtons(True)


                """MULTIPLE SELECTION"""
                self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setLayer(self.current_layer, layer_props)

                self.filtering_init_buffer_property()

                for group_name in self.layer_properties_tuples_dict:
                    tuple_group = self.layer_properties_tuples_dict[group_name]
                    group_state = True
                    if group_name not in ('is','selection_expression'):
                        group_enabled_property = tuple_group[0]
                        group_state = layer_props[group_enabled_property[0]][group_enabled_property[1]]
                        if group_state is False:
                            self.properties_group_state_reset_to_default(tuple_group, group_name, group_state)
                        else:
                            self.properties_group_state_enabler(tuple_group)

                    if group_state is True:
                        for i, property_tuple in enumerate(tuple_group):
                            widget_type = self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["TYPE"]
                            if widget_type == 'PushButton':

                                if all(key in self.widgets[property_tuple[0].upper()][property_tuple[1].upper()] for key in ["ICON_ON_TRUE", "ICON_ON_FALSE"]):
                                    self.switch_widget_icon(property_tuple, layer_props[property_tuple[0]][property_tuple[1]])

                                if self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].isCheckable():
                                    self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setChecked(layer_props[property_tuple[0]][property_tuple[1]])
                            elif widget_type == 'CheckableComboBox':
                                self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setCheckedItems(layer_props[property_tuple[0]][property_tuple[1]])
                            elif widget_type == 'CustomCheckableComboBox':
                                self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["CUSTOM_LOAD_FUNCTION"]
                            elif widget_type == 'ComboBox':
                                self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setCurrentIndex(self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].findText(layer_props[property_tuple[0]][property_tuple[1]]))
                            elif widget_type == 'QgsFieldExpressionWidget':
                                print(property_tuple[0].upper(),property_tuple[1].upper())
                                self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setLayer(self.current_layer)
                                self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setExpression(layer_props[property_tuple[0]][property_tuple[1]])
                            elif widget_type == 'QgsDoubleSpinBox':
                                self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setValue(layer_props[property_tuple[0]][property_tuple[1]])
                            elif widget_type == 'LineEdit':
                                self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setText(layer_props[property_tuple[0]][property_tuple[1]])
                            elif widget_type == 'QgsProjectionSelectionWidget':
                                crs = QgsCoordinateReferenceSystem(layer_props[property_tuple[0]][property_tuple[1]])
                                if crs.isValid():
                                    self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setCrs(crs)
                            elif widget_type == 'PropertyOverrideButton':
                                if layer_props[property_tuple[0]][property_tuple[1]] is False:
                                    self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].setActive(False)
                                elif layer_props[property_tuple[0]][property_tuple[1]] is True:
                                    self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].setActive(True)
                            
                self.filtering_populate_layers_chekableCombobox()

                for widget_path in widgets_to_stop:
                    self.manageSignal(widget_path, 'connect')

                if self.project_props["OPTIONS"]["LAYERS"]["LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"] is True:
                    if self.iface.activeLayer() != None and self.iface.activeLayer().id() != self.current_layer.id():
                        self.widgets["QGIS"]["LAYER_TREE_VIEW"]["WIDGET"].setCurrentLayer(self.current_layer)

                    widget_path = ["QGIS","LAYER_TREE_VIEW"]
                    self.manageSignal(widget_path, 'connect')
                    
                self.exploring_link_widgets()
                
        except (AttributeError, KeyError, RuntimeError) as e:
            # Widget initialization may not be complete
            pass


    def project_property_changed(self, input_property, input_data=None, custom_functions={}):

        if self.widgets_initialized is True and self.has_loaded_layers is True:

            properties_group_key = None
            property_path = None
            index = None
            state = None
            group_state = True
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
                if isinstance(input_data, float):
                    input_data = truncate(input_data, 2)
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
            
            group_enabled_property = properties_tuples[0]
            group_state = self.widgets[group_enabled_property[0].upper()][group_enabled_property[1].upper()]["WIDGET"].isChecked()

            if group_state is False:
                self.properties_group_state_reset_to_default(properties_tuples, properties_group_key, group_state)            

            else:
                self.properties_group_state_enabler(properties_tuples)
                widget_type = self.widgets[property_path[0].upper()][property_path[1].upper()]["TYPE"]
                if widget_type == 'PushButton':
                    if self.project_props[property_path[0].upper()][property_path[1].upper()] is not input_data and input_data is True:
                        self.project_props[property_path[0].upper()][property_path[1].upper()] = input_data
                        flag_value_changed = True
                        if "ON_TRUE" in custom_functions:
                            custom_functions["ON_TRUE"](0)

                    elif self.project_props[property_path[0].upper()][property_path[1].upper()] is not input_data and input_data is False:
                        self.project_props[property_path[0].upper()][property_path[1].upper()] = input_data
                        flag_value_changed = True
                        if "ON_FALSE" in custom_functions:
                            custom_functions["ON_FALSE"](0)
                else:    
                    
                    if self.project_props[properties_tuples[0][0].upper()][properties_tuples[0][1].upper()] is state and state is True:
                        self.project_props[property_path[0].upper()][property_path[1].upper()] = custom_functions["CUSTOM_DATA"](0) if "CUSTOM_DATA" in custom_functions else input_data
                        flag_value_changed = True
                        if "ON_TRUE" in custom_functions:
                            custom_functions["ON_TRUE"](0)

            if flag_value_changed is True:
                if "ON_CHANGE" in custom_functions:
                    custom_functions["ON_CHANGE"](0)
                self.CONFIG_DATA['CURRENT_PROJECT']['EXPORT'] = self.project_props['EXPORTING']
                self.setProjectVariablesEvent()


    def layer_property_changed(self, input_property, input_data=None, custom_functions={}):
        
        if self.widgets_initialized is True and self.current_layer != None:


            if self.current_layer == None:
                return
            
            widgets_to_stop =   [
                        ["EXPLORING","SINGLE_SELECTION_FEATURES"],
                        ["EXPLORING","SINGLE_SELECTION_EXPRESSION"],
                        ["EXPLORING","MULTIPLE_SELECTION_FEATURES"],
                        ["EXPLORING","MULTIPLE_SELECTION_EXPRESSION"],
                        ["EXPLORING","CUSTOM_SELECTION_EXPRESSION"]
                    ]
        
            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'disconnect')

            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
            properties_group_key = None
            property_path = None
            index = None
            state = None
            group_state = True
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
                if isinstance(input_data, float):
                    input_data = truncate(input_data, 2)
            elif isinstance(input_data, bool):
                state = input_data
            elif input_data is None:
                state = False
            

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

            print(property_path, input_data)            


            if properties_group_key == 'is':

                if property_path[1] == "is_changing_all_layer_properties":

                    if layer_props[property_path[0]][property_path[1]] is True:
                        self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = False
                        flag_value_changed = True
                        if "ON_TRUE" in custom_functions:
                            custom_functions["ON_TRUE"](0)
                        self.switch_widget_icon(property_path, False)

                    elif layer_props[property_path[0]][property_path[1]] is False:
                        self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = True
                        flag_value_changed = True
                        if "ON_FALSE" in custom_functions:
                            custom_functions["ON_FALSE"](0)
                        self.switch_widget_icon(property_path, True)

                else:

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


            elif properties_group_key == 'selection_expression':
                
                if str(layer_props[property_path[0]][property_path[1]]) != input_data:
                    self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = input_data
                    flag_value_changed = True
                    if "ON_TRUE" in custom_functions:
                        custom_functions["ON_TRUE"](0)

            else:
                group_enabled_property = properties_tuples[0]
                group_state = self.widgets[group_enabled_property[0].upper()][group_enabled_property[1].upper()]["WIDGET"].isChecked()

                if group_state is False:
                    self.properties_group_state_reset_to_default(properties_tuples, properties_group_key, group_state)
                    flag_value_changed = True

                else:
                    self.properties_group_state_enabler(properties_tuples)
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

                    else:
                        print(input_data)
                        self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = input_data
                        flag_value_changed = True
                        if "ON_TRUE" in custom_functions:
                            custom_functions["ON_TRUE"](0)


            if flag_value_changed is True:
                if "ON_CHANGE" in custom_functions:
                    custom_functions["ON_CHANGE"](0)

                print('setLayerVariableEvent', input_data)
                self.setLayerVariableEvent(self.current_layer, [property_path])

            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'connect')

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

            group_state = True

            for properties_group_key in self.export_properties_tuples_dict:
                properties_tuples = self.export_properties_tuples_dict[properties_group_key]
                
                group_enabled_property = properties_tuples[0]
                group_state = self.widgets[group_enabled_property[0].upper()][group_enabled_property[1].upper()]["WIDGET"].isChecked()

                if group_state is False:
                    self.properties_group_state_reset_to_default(properties_tuples, properties_group_key, group_state)

                else:
                    self.properties_group_state_enabler(properties_tuples)
                    for i, property_path in enumerate(properties_tuples):
                        widget_type = self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["TYPE"]
                        if widget_type == 'PushButton':
                            self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setChecked(self.project_props[property_path[0].upper()][property_path[1].upper()])
                        elif widget_type == 'CheckableComboBox':
                            self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setCheckedItems(self.project_props[property_path[0].upper()][property_path[1].upper()])
                        elif widget_type == 'CustomCheckableComboBox':
                            self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["CUSTOM_LOAD_FUNCTION"]
                        elif widget_type == 'ComboBox':
                            self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setCurrentIndex(self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].findText(self.project_props[property_path[0].upper()][property_path[1].upper()]))
                        elif widget_type == 'QgsDoubleSpinBox':
                            self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setValue(self.project_props[property_path[0].upper()][property_path[1].upper()])
                        elif widget_type == 'LineEdit':
                            if self.project_props[property_path[0].upper()][property_path[1].upper()] == '':
                                if property_tuple[1] == 'output_folder_to_export':
                                    self.reset_export_output_path()
                                if property_tuple[1] == 'zip_to_export':
                                    self.reset_export_output_pathzip()
                            else:
                                self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setText(self.project_props[property_path[0].upper()][property_path[1].upper()])
                        elif widget_type == 'QgsProjectionSelectionWidget':
                            crs = QgsCoordinateReferenceSystem(self.project_props[property_path[0].upper()][property_path[1].upper()])
                            if crs.isValid():
                                self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setCrs(crs)

            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'connect')

            self.CONFIG_DATA["CURRENT_PROJECT"]['EXPORTING'] = self.project_props['EXPORTING']
            # self.reload_configuration_model()


    def properties_group_state_enabler(self, tuple_group):

        if self.widgets_initialized is True and self.has_loaded_layers is True:
            for tuple in tuple_group:
                self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].setEnabled(True)


    def properties_group_state_reset_to_default(self, tuple_group, group_name, state):

        if self.widgets_initialized is True and self.has_loaded_layers is True:
            for i, property_path in enumerate(tuple_group):
                if state is False:
                    widget_type = self.widgets[property_path[0].upper()][property_path[1].upper()]["TYPE"]
                    self.manageSignal([property_path[0].upper(),property_path[1].upper()], 'disconnect')

                    if group_name in self.layer_properties_tuples_dict:
                        if widget_type == 'PushButton':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setChecked(state)
                            self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].isChecked()
                        elif widget_type == 'CheckableComboBox':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].deselectAllOptions()
                            self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].checkedItems()
                        elif widget_type == 'ComboBox':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setCurrentIndex(0)
                            self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].currentText()
                        elif widget_type == 'QgsFieldExpressionWidget':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setField(self.PROJECT_LAYERS[self.current_layer.id()]["infos"]["primary_key_name"])
                            self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].expression()
                        elif widget_type == 'QgsDoubleSpinBox':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].clearValue()
                            self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].value()
                        elif widget_type == 'LineEdit':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setText('')
                            self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].text()
                        elif widget_type == 'QgsProjectionSelectionWidget':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setCrs(self.PROJECT.crs())
                            self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].crs().authid()
                        elif widget_type == 'PropertyOverrideButton':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setActive(False)
                            self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = False


                    elif group_name in self.export_properties_tuples_dict:
                        if widget_type == 'PushButton':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setChecked(state)
                            self.project_props[property_path[0].upper()][property_path[1].upper()] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].isChecked()
                        elif widget_type == 'CheckableComboBox':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].deselectAllOptions()
                            self.project_props[property_path[0].upper()][property_path[1].upper()] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].checkedItems()
                        elif widget_type == 'ComboBox':
                            index = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].findText('GPKG')
                            if index < 0:
                                index = 0
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setCurrentIndex(index)
                            self.project_props[property_path[0].upper()][property_path[1].upper()] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].currentText()
                        elif widget_type == 'QgsFieldExpressionWidget':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setField(self.PROJECT_LAYERS[self.current_layer.id()]["infos"]["primary_key_name"])
                            self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].expression()    
                        elif widget_type == 'QgsDoubleSpinBox':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].clearValue()
                            self.project_props[property_path[0].upper()][property_path[1].upper()] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].value()
                        elif widget_type == 'LineEdit':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setText('')
                            self.project_props[property_path[0].upper()][property_path[1].upper()] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].text()
                        elif widget_type == 'QgsProjectionSelectionWidget':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setCrs(self.PROJECT.crs())
                            self.project_props[property_path[0].upper()][property_path[1].upper()] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].crs().authid()
                        elif widget_type == 'PropertyOverrideButton':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setActive(False)
                            self.project_props[property_path[0].upper()][property_path[1].upper()] = False

                    self.manageSignal([property_path[0].upper(), property_path[1].upper()], 'connect')
                    
                if i == 0 and property_path[1].upper().find('HAS') >= 0:
                    self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setEnabled(True)
                else:
                    self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setEnabled(state)

    def filtering_init_buffer_property(self):

        if self.widgets_initialized is True and self.has_loaded_layers is True:
                        




            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]   

            name = str("{}_buffer_property_definition".format(self.current_layer.id()))
            description = str("Replace unique buffer value with values based on expression for {}".format(self.current_layer.id()))
            property_definition = QgsPropertyDefinition(name, QgsPropertyDefinition.DataTypeNumeric, description, 'Expression must returns numeric values (unit is in meters)')
            
            
            buffer_expression = layer_props["filtering"]["buffer_value_expression"]
            if buffer_expression != '':
                property = QgsProperty.fromExpression(layer_props["filtering"]["buffer_value_expression"])
            else:
                property = QgsProperty()

            print(property, property.propertyType(), self.current_layer)
            
            # if self.buffer_property_has_been_init is False:
                
            self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].init(0, property, property_definition, self.current_layer)

            if property.propertyType() == 0:
                print(property.propertyType())
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].registerEnabledWidget(self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"], True)
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].registerVisibleWidget(self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"], True)
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].registerEnabledWidget(self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"], False)
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].registerVisibleWidget(self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"], False)
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].registerExpressionWidget(self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"])
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].setText('')
                #self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].setActive(False)
                #self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["SIGNALS"][0][1](False)

            else:
                print(property.propertyType())
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].registerEnabledWidget(self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"], False)
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].registerVisibleWidget(self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"], False)
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].registerEnabledWidget(self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"], True)
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].registerVisibleWidget(self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"], True)
                self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"].setClearButtonEnabled(True)
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].registerExpressionWidget(self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"])
                #self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["SIGNALS"][0][1](True)

                

                
                # self.buffer_property_has_been_init = True


                


    def filtering_buffer_expression_edited(self):

        if self.widgets_initialized is True and self.has_loaded_layers is True:


            widgets_to_stop =   [
                                    ["FILTERING","BUFFER_VALUE_EXPRESSION"]
                                ]
            
            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'disconnect')



            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]

            if self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"].text().strip() in ('', 'NULL') or len(self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"].text().strip()) == 0:

                print("filtering_buffer_expression_edited", layer_props["filtering"]["buffer_value_expression"].strip())

                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer_value_expression"] = ''
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].setActive(False)
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["SIGNALS"][0][1](False)

            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'connect')
 

    def filtering_buffer_property_changed(self):

        if self.widgets_initialized is True and self.has_loaded_layers is True:


            widgets_to_stop =   [
                                    ["FILTERING","BUFFER_VALUE_PROPERTY"]
                                ]
            
            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'disconnect')


            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
            
            print(layer_props["filtering"]["buffer_value_expression"].strip())
            print(layer_props["filtering"]["buffer_value_property"])

            if layer_props["filtering"]["buffer_value_property"] is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer_value_expression"] = self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].toProperty().asExpression()
                self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"].setClearButtonEnabled(True)


            if layer_props["filtering"]["buffer_value_property"] is False:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer_value_expression"] = ''
                if self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"].text().strip() != '':
                    self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"].setText('')
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].setToProperty(QgsProperty())


            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'connect')


    def get_buffer_property_state(self):
        return self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].isActive()

              
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
                state = self.project_props["OPTIONS"]["LAYERS"]["LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"]


            self.widgets["FILTERING"]["AUTO_CURRENT_LAYER"]["WIDGET"].setChecked(state)

            if state is True:
                self.project_props["OPTIONS"]["LAYERS"]["LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"] = state
                self.manageSignal(["QGIS","LAYER_TREE_VIEW"], 'connect')

            elif state is False:
                self.project_props["OPTIONS"]["LAYERS"]["LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"] = state
                self.manageSignal(["QGIS", "LAYER_TREE_VIEW"], 'disconnect')
                
            self.setProjectVariablesEvent()

    def get_project_layers_from_app(self, project_layers, project=None):

        layer = None

        if self.widgets_initialized is True:

            if project != None:    
                self.PROJECT = project

            self.PROJECT_LAYERS = project_layers


            if self.PROJECT != None and len(list(self.PROJECT_LAYERS)) > 0:

                try:
                    if self.current_layer != None:
                        layers = [layer for layer in self.PROJECT.mapLayersByName(self.PROJECT_LAYERS[self.current_layer.id()]["infos"]["layer_name"]) if layer.id() == self.current_layer.id()]
                        if len(layers) == 0:
                            if self.iface.activeLayer():
                                layer = self.iface.activeLayer()
                        elif len(layers) > 0:
                            layer = layers[0]
                    else:
                        if self.iface.activeLayer():
                            layer = self.iface.activeLayer()
                except:
                    if self.iface.activeLayer():
                        layer = self.iface.activeLayer()


                if self.has_loaded_layers is False:
                    self.has_loaded_layers = True
                    
                self.set_widgets_enabled_state(True)
                
                if layer != None and isinstance(layer, QgsVectorLayer):
                    self.manage_output_name()
                    self.exporting_populate_combobox()
                    self.set_exporting_properties()
                    self.select_tabTools_index()
                    self.current_layer_changed(layer)
                    self.connect_widgets_signals()
                    self.exploring_groupbox_init()
                    self.filtering_auto_current_layer_changed()
                    return

                    
            else:
                self.has_loaded_layers = False
                self.disconnect_widgets_signals()
                self.set_widgets_enabled_state(False)
                return


    def open_project_page(self):
        if "APP" in self.CONFIG_DATA:
            if "GITHUB_PAGE" in self.CONFIG_DATA["APP"] and self.CONFIG_DATA["APP"]["GITHUB_PAGE"].find("http") >= 0:
                webbrowser.open(self.CONFIG_DATA["APP"]["GITHUB_PAGE"])


    def setLayerVariableEvent(self, layer=None, properties=[]):

        if self.widgets_initialized is True:
            if layer == None:
                layer = self.current_layer

            self.settingLayerVariable.emit(layer, properties)


    def resetLayerVariableOnErrorEvent(self, layer, properties=[]):


        if self.widgets_initialized is True:
            if layer == None:
                layer = self.current_layer
           
            self.resettingLayerVariableOnError.emit(layer, properties)


    def resetLayerVariableEvent(self, layer=None, properties=[]):

        if self.widgets_initialized is True:
            if layer == None:
                layer = self.current_layer
           
            self.resettingLayerVariable.emit(layer, properties)

    def setProjectVariablesEvent(self):
        if self.widgets_initialized is True:

            self.settingProjectVariables.emit()

    def getProjectLayersEvent(self, event):

        if self.widgets_initialized is True:

            self.gettingProjectLayers.emit()

    def closeEvent(self, event):

        if self.widgets_initialized is True:

            self.closingPlugin.emit()
            event.accept()

    def launchTaskEvent(self, state, task_name):

        if self.widgets_initialized is True:

            self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["layers_to_filter"] = self.get_layers_to_filter()
            self.launchingTask.emit(task_name)
    



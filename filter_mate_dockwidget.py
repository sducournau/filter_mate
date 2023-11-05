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

        self.properties_tuples_dict = None
        self.widgets = None
        self.widgets_initialized = False
        self.current_exploring_groupbox = None
        self.current_layer = self.iface.activeLayer()
        self.CONFIG_DATA = CONFIG_DATA
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
        
        return state
        
        if state == None:
            raise SignalStateChangeError(state, widget_path)
        

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
        self.customCheckableComboBox_exploring_multiple_selection = QgsCustomCheckableListWidget(self)
        self.layout = self.verticalLayout_exploring_multiple_selection
        self.layout.insertWidget(0, self.customCheckableComboBox_exploring_multiple_selection)

        #self.custom_identify_tool = CustomIdentifyTool(self.iface)
        self.iface.mapCanvas().setSelectionColor(QColor(237, 97, 62, 75))
        self.manage_configuration_model()



    def dockwidget_widgets_configuration(self):

        self.properties_tuples_dict =   {
                                        "is":(("exploring","is_selecting"),("exploring","is_tracking"),("exploring","is_linking"),("exploring","is_saving")),
                                        "layers_to_filter":(("filtering","has_layers_to_filter"),("filtering","layers_to_filter")),
                                        "combine_operator":(("filtering","has_combine_operator"),("filtering","combine_operator")),
                                        "geometric_predicates":(("filtering","has_geometric_predicates"),("filtering","geometric_predicates"),("filtering","geometric_predicates_operator")),
                                        "buffer":(("filtering","has_buffer"),("filtering","buffer"))
                                        }


        self.widgets = {"DOCK":{}, "ACTION":{}, "EXPLORING":{}, "SINGLE_SELECTION":{}, "MULTIPLE_SELECTION":{}, "CUSTOM_SELECTION":{}, "FILTERING":{}, "EXPORTING":{}, "QGIS":{}}
            
        self.widgets["DOCK"] = {
                                "SINGLE_SELECTION":{"TYPE":"GroupBox", "WIDGET":self.mGroupBox_exploring_single_selection, "SIGNALS":[("stateChanged", lambda state, x='single_selection': self.exploring_groupbox_changed(x, state))]},
                                "MULTIPLE_SELECTION":{"TYPE":"GroupBox","WIDGET":self.mGroupBox_exploring_multiple_selection, "SIGNALS":[("stateChanged", lambda state, x='multiple_selection': self.exploring_groupbox_changed(x, state))]},
                                "CUSTOM_SELECTION":{"TYPE":"GroupBox","WIDGET":self.mGroupBox_exploring_custom_selection, "SIGNALS":[("stateChanged", lambda state, x='custom_selection': self.exploring_groupbox_changed(x, state))]},
                                "CONFIGURATION_TREE_VIEW":{"TYPE":"TreeView","WIDGET":self.config_view, "SIGNALS":[("currentChanged", None)]},
                                "TOOLS":{"TYPE":"ToolBox","WIDGET":self.toolBox_tabTools, "SIGNALS":[("currentChanged", self.select_tabTools_index)]}
                                }   

        self.widgets["ACTION"] = {
                                "FILTER":{"TYPE":"PushButton", "WIDGET":self.pushButton_action_filter, "SIGNALS":[("clicked", lambda state, x='filter': self.launchTaskEvent(x))], "ICON":None},
                                "UNFILTER":{"TYPE":"PushButton", "WIDGET":self.pushButton_action_unfilter, "SIGNALS":[("clicked", lambda state, x='unfilter': self.launchTaskEvent(x))], "ICON":None},
                                "EXPORT":{"TYPE":"PushButton", "WIDGET":self.pushButton_action_export, "SIGNALS":[("clicked", lambda state, x='export': self.launchTaskEvent(x))], "ICON":None}
                                }        

        self.widgets["SINGLE_SELECTION"] = {
                                            "FEATURES":{"TYPE":"FeatureComboBox", "WIDGET":self.mFeaturePickerWidget_exploring_single_selection, "SIGNALS":[("featureChanged", self.exploring_features_changed)]},
                                            "EXPRESSION":{"TYPE":"ComboBox", "WIDGET":self.mFieldExpressionWidget_exploring_single_selection, "SIGNALS":[("fieldChanged", self.exploring_source_params_changed)]}
                                            }
        
        self.widgets["MULTIPLE_SELECTION"] = {
                                            "FEATURES":{"TYPE":"CustomCheckableComboBox", "WIDGET":self.customCheckableComboBox_exploring_multiple_selection, "SIGNALS":[("updatingCheckedItemList", self.exploring_features_changed),("filteringCheckedItemList", self.exploring_link_widgets)]},
                                            "EXPRESSION":{"TYPE":"ComboBox", "WIDGET":self.mFieldExpressionWidget_exploring_multiple_selection, "SIGNALS":[("fieldChanged", self.exploring_source_params_changed)]}
                                            }
        
        self.widgets["CUSTOM_SELECTION"] = {
                                            "EXPRESSION":{"TYPE":"ComboBox", "WIDGET":self.mFieldExpressionWidget_exploring_custom_selection, "SIGNALS":[("fieldChanged", self.exploring_source_params_changed)]}
                                            }


        self.widgets["EXPLORING"] = {
                                    "IDENTIFY":{"TYPE":"PushButton", "WIDGET":self.pushButton_exploring_identify, "SIGNALS":[("clicked", self.exploring_identify_clicked)], "ICON":None},
                                    "ZOOM":{"TYPE":"PushButton", "WIDGET":self.pushButton_exploring_zoom, "SIGNALS":[("clicked", self.exploring_zoom_clicked)], "ICON":None},
                                    "IS_SELECTING":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exploring_selecting, "SIGNALS":[("clicked", lambda state, x='is_selecting': self.layer_property_changed(x, state))], "ICON":None},
                                    "IS_TRACKING":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exploring_tracking, "SIGNALS":[("clicked", lambda state, x='is_tracking': self.layer_property_changed(x, state))], "ICON":None},
                                    "IS_LINKING":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exploring_linking_widgets, "SIGNALS":[("clicked", lambda state, x='is_linking', custom_function={"ON_CHANGE": lambda x: self.exploring_link_widgets()}: self.layer_property_changed(x, state, custom_function))], "ICON":None},
                                    "IS_SAVING":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exploring_saving_parameters, "SIGNALS":[("clicked", lambda state, x='is_saving', custom_function={"ON_FALSE": lambda x=self.current_layer.id(): self.reinitializeLayerOnErrorEvent(x)}: self.layer_property_changed(x, state, custom_function))], "ICON":None}
                                    }


        self.widgets["FILTERING"] = {
                                    "AUTO_CURRENT_LAYER":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_filtering_auto_current_layer, "SIGNALS":[("clicked", self.filtering_auto_current_layer_changed)], "ICON":None},
                                    "HAS_LAYERS_TO_FILTER":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_filtering_layers_to_filter, "SIGNALS":[("clicked", lambda state, x='has_layers_to_filter': self.layer_property_changed(x, state))], "ICON":None},
                                    "HAS_COMBINE_OPERATOR":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_filtering_current_layer_combine_operator, "SIGNALS":[("clicked", lambda state, x='has_combine_operator': self.layer_property_changed(x, state))], "ICON":None},
                                    "HAS_GEOMETRIC_PREDICATES":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_filtering_geometric_predicates, "SIGNALS":[("clicked", lambda state, x='has_geometric_predicates': self.layer_property_changed(x, state))], "ICON":None},
                                    "HAS_BUFFER":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_filtering_buffer, "SIGNALS":[("clicked", lambda state, x='has_buffer': self.layer_property_changed(x, state))], "ICON":None},
                                    "CURRENT_LAYER":{"TYPE":"ComboBox", "WIDGET":self.comboBox_filtering_current_layer, "SIGNALS":[("layerChanged", self.current_layer_changed)]},
                                    "LAYERS_TO_FILTER":{"TYPE":"CustomCheckableComboBox", "WIDGET":self.comboBox_filtering_layers_to_filter, "CUSTOM_LOAD_FUNCTION": lambda x: self.get_layers_to_filter(), "SIGNALS":[("checkedItemsChanged", lambda state, custom_function={"CUSTOM_DATA": lambda x: self.get_layers_to_filter()}, x='layers_to_filter': self.layer_property_changed(x, state, custom_function))]},
                                    "COMBINE_OPERATOR":{"TYPE":"ComboBox", "WIDGET":self.comboBox_filtering_current_layer_combine_operator, "SIGNALS":[("currentTextChanged", lambda state, x='combine_operator': self.layer_property_changed(x, state))]},
                                    "GEOMETRIC_PREDICATES":{"TYPE":"CheckableComboBox", "WIDGET":self.comboBox_filtering_geometric_predicates, "SIGNALS":[("checkedItemsChanged", lambda state, x='geometric_predicates': self.layer_property_changed(x, state))]},
                                    "GEOMETRIC_PREDICATES_OPERATOR":{"TYPE":"ComboBox", "WIDGET":self.comboBox_filtering_geometric_predicates_operator, "SIGNALS":[("currentTextChanged", lambda state, x='geometric_predicates_operator': self.layer_property_changed(x, state))]},
                                    "BUFFER":{"TYPE":"QgsDoubleSpinBox", "WIDGET":self.mQgsDoubleSpinBox_filtering_buffer, "SIGNALS":[("textChanged", lambda state, x='buffer': self.layer_property_changed(x, state))]}
                                    }
        
        self.widgets["EXPORTING"] = {
                                    "HAS_LAYERS":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_layers, "SIGNALS":[("clicked", None)], "ICON":None},
                                    "HAS_PROJECTION":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_projection, "SIGNALS":[("clicked", None)], "ICON":None},
                                    "HAS_STYLES":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_styles, "SIGNALS":[("clicked", None)], "ICON":None},
                                    "HAS_DATATYPE":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_datatype, "SIGNALS":[("clicked", None)], "ICON":None},
                                    "HAS_OUTPUT_FOLDER":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_output_folder, "SIGNALS":[("clicked", self.dialog_export_folder)], "ICON":None},
                                    "HAS_ZIP":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_zip, "SIGNALS":[("clicked", self.dialog_export_zip)], "ICON":None},
                                    "LAYERS":{"TYPE":"CheckableComboBox", "WIDGET":self.comboBox_exporting_layers, "SIGNALS":[("checkedItemsChanged", None)]},
                                    "PROJECTION":{"TYPE":"ComboBox", "WIDGET":self.mQgsProjectionSelectionWidget_exporting_projection, "SIGNALS":[("crsChanged", None)]},
                                    "STYLES":{"TYPE":"ComboBox", "WIDGET":self.comboBox_exporting_styles, "SIGNALS":[("currentTextChanged", None)]},
                                    "DATATYPE":{"TYPE":"ComboBox", "WIDGET":self.comboBox_exporting_datatype, "SIGNALS":[("currentTextChanged", None)]},
                                    "OUTPUT_FOLDER":{"TYPE":"LineEdit", "WIDGET":self.lineEdit_exporting_output_folder, "SIGNALS":[("textEdited", self.reset_export_folder)]},
                                    "ZIP":{"TYPE":"LineEdit", "WIDGET":self.lineEdit_exporting_zip, "SIGNALS":[("textEdited", self.reset_export_zip)]}
                                    }
            

    
        self.widgets["QGIS"] = {
                                "LAYER_TREE_VIEW":{"TYPE":"TreeView", "WIDGET":self.iface.layerTreeView(), "SIGNALS":[("currentLayerChanged", self.current_layer_changed)]}
                                }
        
        self.widgets_initialized = True

    def reload_configuration_model(self):
        try:
            self.config_model = JsonModel(data=self.CONFIG_DATA, editable_keys=True, editable_values=True)
            self.config_view.setModel(self.config_model)
            self.save_configuration_model()
        except:
            pass


    def save_configuration_model(self):
        # CONFIG_DATA = self.widgets["DOCK"]["CONFIGURATION_TREE_VIEW"]["WIDGET"].model.serialize()
        # COLORS = CONFIG_DATA['DOCKWIDGET']['COLORS']

        with open(self.plugin_dir + '/config/config.json', 'w') as outfile:
            json.dump(self.CONFIG_DATA, outfile)


    def manage_configuration_model(self):
        """Manage the qtreeview model configuration"""

        self.config_model = JsonModel(data=self.CONFIG_DATA, editable_keys=True, editable_values=True)


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


    def set_widget_icon(self, widget_path, widget_type):

        file = self.CONFIG_DATA["DOCKWIDGET"][widget_type]["ICONS"][widget_path[0]][widget_path[1]]
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

        self.widgets["DOCK"]["TOOLS"]["WIDGET"].setStyleSheet("""background-color: {};
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
        
        pushButton_style = json.dumps(self.CONFIG_DATA["DOCKWIDGET"]["PushButton"]["STYLE"])[1:-1].replace(': {', ' {').replace('\"', '').replace(',', '')

        for widget_group in self.widgets:
            for widget_name in self.widgets[widget_group]:
                if self.widgets[widget_group][widget_name]["TYPE"] == "PushButton":
                    self.set_widget_icon([widget_group, widget_name], "PushButton")
                    self.widgets[widget_group][widget_name]["WIDGET"].setStyleSheet(pushButton_style)
                elif self.widgets[widget_group][widget_name]["TYPE"].find("ComboBox") >= 0:
                    self.widgets[widget_group][widget_name]["WIDGET"].setStyleSheet(comboBox_style)
                elif self.widgets[widget_group][widget_name]["TYPE"].find("LineEdit") >= 0:
                    self.widgets[widget_group][widget_name]["WIDGET"].setStyleSheet(lineEdit_style)



    def manage_interactions(self):


        """INIT"""


        self.select_tabTools_index(self.widgets["DOCK"]["TOOLS"]["WIDGET"].currentIndex())
        self.widgets["FILTERING"]["BUFFER"]["WIDGET"].setExpressionsEnabled(True)
        self.widgets["FILTERING"]["BUFFER"]["WIDGET"].setClearValue(0.0)
        self.widgets["EXPORTING"]["PROJECTION"]["WIDGET"].setCrs(PROJECT.crs())


        """SET INTERACTIONS"""
        for widget_group in self.widgets:
            if widget_group != 'QGIS':
                for widget in self.widgets[widget_group]:
                    if widget_group != 'DOCK' and self.widgets[widget_group][widget]["TYPE"] != "GroupBox":
                        self.manageSignal([widget_group, widget], 'connect')


        self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].clicked.connect(lambda state, x='single_selection': self.exploring_groupbox_changed(x, state))
        self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].clicked.connect(lambda state, x='multiple_selection': self.exploring_groupbox_changed(x, state))
        self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].clicked.connect(lambda state, x='custom_selection': self.exploring_groupbox_changed(x, state))
        

        if self.current_layer != None:
            self.populate_predicats_chekableCombobox()
            self.exporting_populate_layers_chekableCombobox()
            self.filtering_populate_layers_chekableCombobox()
            self.filtering_auto_current_layer_changed()
            self.exploring_groupbox_changed('multiple_selection')
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
        self.widgets["FILTERING"]["GEOMETRIC_PREDICATES"]["WIDGET"].clear()
        self.widgets["FILTERING"]["GEOMETRIC_PREDICATES"]["WIDGET"].addItems(self.predicats)

    def filtering_populate_layers_chekableCombobox(self):
        try:    
            self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].clear()
            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]

            if layer_props["filtering"]["has_layers_to_filter"] == True:
                i = 0
                for key in self.PROJECT_LAYERS:
                    layer_id = self.PROJECT_LAYERS[key]["infos"]["layer_id"]
                    layer_name = self.PROJECT_LAYERS[key]["infos"]["layer_name"]
                    layer_crs = self.PROJECT_LAYERS[key]["infos"]["layer_crs"]
                    layer_icon = self.icon_per_geometry_type(self.PROJECT_LAYERS[key]["infos"]["layer_geometry_type"])

                    if key != self.current_layer.id():
                        self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].addItem(layer_icon, layer_name + ' [%s]' % (layer_crs))
                        self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].setItemData(i, json.dumps(self.PROJECT_LAYERS[key]["infos"]), Qt.UserRole)
                        if len(layer_props["filtering"]["layers_to_filter"]) > 0:
                            if layer_id in list(layer_info["layer_id"] for layer_info in list(layer_props["filtering"]["layers_to_filter"])):
                                self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].setItemCheckState(i, Qt.Checked)
                            else:
                                self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].setItemCheckState(i, Qt.Unchecked)   
                        else:
                            self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].setItemCheckState(i, Qt.Unchecked)
                        i += 1    
            else:
                i = 0
                for key in self.PROJECT_LAYERS:
                    layer_id = self.PROJECT_LAYERS[key]["infos"]["layer_id"]
                    layer_name = self.PROJECT_LAYERS[key]["infos"]["layer_name"]
                    layer_crs = self.PROJECT_LAYERS[key]["infos"]["layer_crs"]
                    layer_icon = self.icon_per_geometry_type(self.PROJECT_LAYERS[key]["infos"]["layer_geometry_type"])
                    
                    if key != self.current_layer.id():
                        self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].addItem(layer_icon, layer_name + ' [%s]' % (layer_crs), self.PROJECT_LAYERS[key]["infos"])
                        self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].setItemData(i, json.dumps(self.PROJECT_LAYERS[key]["infos"]), Qt.UserRole)             
                        self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].setItemCheckState(i, Qt.Unchecked)
                        i += 1    
        
        except Exception as e:
            self.exception = e
            print(self.exception)
            self.reinitializeLayerOnErrorEvent(self.current_layer.id())

    def exporting_populate_layers_chekableCombobox(self):

        self.widgets["EXPORTING"]["LAYERS"]["WIDGET"].clear()

        for key in self.PROJECT_LAYERS:
            layer_name = self.PROJECT_LAYERS[key]["infos"]["layer_name"]
            layer_crs = self.PROJECT_LAYERS[key]["infos"]["layer_crs"]
            layer_icon = self.icon_per_geometry_type(self.PROJECT_LAYERS[key]["infos"]["layer_geometry_type"])
            self.widgets["EXPORTING"]["LAYERS"]["WIDGET"].addItem(layer_icon, layer_name + ' [%s]' % (layer_crs), self.PROJECT_LAYERS[key]["infos"])
        
        self.widgets["EXPORTING"]["LAYERS"]["WIDGET"].selectAllOptions()
            




    def layer_property_changed(self, input_property, input_data=None, custom_function={}):

        if self.current_layer == None:
            return
        
        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
        properties_group_key = None
        property_path = None
        index = None
        state = None
        flag_value_changed = False

        if isinstance(input_data, dict) or isinstance(input_data, list):
            if len(input_data) >= 0:
                state = True
            else:
                state = False
        elif isinstance(input_data, bool):
            state = input_data
        

        for properties_tuples_key in self.properties_tuples_dict:
            if input_property.find(properties_tuples_key) >= 0:
                properties_group_key = properties_tuples_key
                properties_tuples = self.properties_tuples_dict[properties_tuples_key]
                for i, property_tuple in enumerate(properties_tuples):
                    if property_tuple[1] == input_property:
                        property_path = property_tuple
                        index = i
                        break
                break

        if properties_group_key == 'is':

            if layer_props[property_path[0]][property_path[1]] is not state and state is True:
                self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = state
                flag_value_changed = True
                if "ON_TRUE" in custom_function:
                    custom_function["ON_TRUE"]

            elif layer_props[property_path[0]][property_path[1]] is not state and state is False:
                self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = state
                flag_value_changed = True
                if "ON_FALSE" in custom_function:
                    custom_function["ON_FALSE"]

        else:
            if index == 0:
                if layer_props[property_path[0]][property_path[1]] is not state and state is True:
                    self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = state
                    flag_value_changed = True
                    if "ON_TRUE" in custom_function:
                        custom_function["ON_TRUE"]

                elif layer_props[property_path[0]][property_path[1]] is not state and state is False:
                    self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = state
                    flag_value_changed = True
                    if "ON_FALSE" in custom_function:
                        custom_function["ON_FALSE"]

                if flag_value_changed is True:
                    self.properties_group_state_changed(properties_tuples)

            else:    
                if layer_props[properties_tuples[0][0]][properties_tuples[0][1]] is state and state is True:
                    self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = custom_function["CUSTOM_DATA"](0) if "CUSTOM_DATA" in custom_function else input_data
                    flag_value_changed = True
                    if "ON_TRUE" in custom_function:
                        custom_function["ON_TRUE"]

        if flag_value_changed is True:
            if "ON_CHANGE" in custom_function:
                custom_function["ON_CHANGE"]
            self.setProjectLayersEvent(self.PROJECT_LAYERS)



    def get_layers_to_filter(self):
        if self.widgets_initialized is True:
            checked_list_data = []
            for i in range(self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].count()):
                if self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].itemCheckState(i) == Qt.Checked:
                    data = self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].itemData(i, Qt.UserRole)
                    if isinstance(data, dict):
                        checked_list_data.append(data)
                    else:
                        checked_list_data.append(json.loads(data))
            return checked_list_data





    def select_tabTools_index(self, i):
        """Keep the current tab index updated"""
        self.tabTools_current_index = i
        if self.tabTools_current_index == 1:
            self.widgets["ACTION"]["EXPORT"]["WIDGET"].setEnabled(True)
        else:
            self.widgets["ACTION"]["EXPORT"]["WIDGET"].setEnabled(False)

    def filtering_auto_current_layer_changed(self):
        if self.widgets["FILTERING"]["AUTO_CURRENT_LAYER"]["WIDGET"].isChecked() is True:
            self.auto_change_current_layer_flag = True
            state = self.manageSignal(["QGIS","LAYER_TREE_VIEW"], 'connect')
            if state == False:
                raise SignalStateChangeError(state, ["QGIS","LAYER_TREE_VIEW"], 'connect')
        else:
            self.auto_change_current_layer_flag = False
            state = self.manageSignal(["QGIS","LAYER_TREE_VIEW"], 'disconnect')
            if state == True:
                raise SignalStateChangeError(state, ["QGIS","LAYER_TREE_VIEW"], 'disconnect')


    def properties_group_state_changed(self, tuple_group):
        
        group_enabled_property = tuple_group[0]
        state = self.widgets[group_enabled_property[0].upper()][group_enabled_property[1].upper()]["WIDGET"].isChecked()
        for tuple in tuple_group[1:]:
            if state is False:
                widget_type = self.widgets[tuple[0].upper()][tuple[1].upper()]["TYPE"]
                signal_status = self.manageSignal([tuple[0].upper(),tuple[1].upper()])
                if widget_type == 'CheckableComboBox':
                    self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].deselectAllOptions()
                    self.PROJECT_LAYERS[self.current_layer.id()][tuple[0]][tuple[1]] = self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].checkedItems()
                elif widget_type == 'ComboBox':
                    self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].setCurrentIndex(0)
                    self.PROJECT_LAYERS[self.current_layer.id()][tuple[0]][tuple[1]] = self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].currentText()
                elif widget_type == 'QgsDoubleSpinBox':
                    self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].clearValue()
                    self.PROJECT_LAYERS[self.current_layer.id()][tuple[0]][tuple[1]] = self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].value()
                signal_status = self.manageSignal([tuple[0].upper(),tuple[1].upper()])

            self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].setEnabled(state)


            #     else:
            #         raise SignalStateChangeError(state, [tuple[0].upper(),tuple[1].upper()], 'connect')
            # else:
            #     raise SignalStateChangeError(state, [tuple[0].upper(),tuple[1].upper()], 'disconnect')

                    

    def exploring_identify_clicked(self):
        

        if self.current_exploring_groupbox == "single_selection":
            input = self.widgets["SINGLE_SELECTION"]["FEATURES"]["WIDGET"].feature()
            features, expr = self.getExploringFeatures(input)

        elif self.current_exploring_groupbox == "multiple_selection":
            input = self.widgets["MULTIPLE_SELECTION"]["FEATURES"]["WIDGET"].checkedItems()
            features, expr = self.getExploringFeatures(input, True)

        elif self.current_exploring_groupbox == "custom_selection":
            features = self.exploring_custom_selection()
        
        if len(features) == 0:
            return
        else:
            self.iface.mapCanvas().flashFeatureIds(self.current_layer, [feature.id() for feature in features], startColor=QColor(235, 49, 42, 255), endColor=QColor(237, 97, 62, 25), flashes=6, duration=400)
        


    def get_current_features(self):

        if self.current_exploring_groupbox == "single_selection":
            input = self.widgets["SINGLE_SELECTION"]["FEATURES"]["WIDGET"].feature()
            features, expression = self.getExploringFeatures(input)

        elif self.current_exploring_groupbox == "multiple_selection":
            input = self.widgets["MULTIPLE_SELECTION"]["FEATURES"]["WIDGET"].checkedItems()
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
            
            self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["single_selection_expression"] = expression
            self.widgets["SINGLE_SELECTION"]["FEATURES"]["WIDGET"].setDisplayExpression(expression)

        elif self.current_exploring_groupbox == "multiple_selection":

            self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["multiple_selection_expression"] = expression
            self.widgets["MULTIPLE_SELECTION"]["FEATURES"]["WIDGET"].setLayer(self.current_layer, layer_props)

        elif self.current_exploring_groupbox == "custom_selection":

            self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["custom_selection_expression"] = expression
            self.exploring_custom_selection()

        self.setProjectLayersEvent(self.PROJECT_LAYERS)
 



    def exploring_custom_selection(self):
        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
        expression = layer_props["exploring"]["custom_selection_expression"]
        features = []
        if QgsExpression(expression).isField() is False:
            features = self.exploring_features_changed([], False, expression)
        return features, expression



    def exploring_groupbox_init(self):

        if self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].isChecked() is True or self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].isCollapsed() is False:
            exploring_groupbox = "single_selection"

        elif self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].isChecked() is True or self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].isCollapsed() is False:
            exploring_groupbox = "multiple_selection"  

        elif self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].isChecked() is True or self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].isCollapsed() is False:
            exploring_groupbox = "custom_selection"

        self.exploring_groupbox_changed(exploring_groupbox)




    def exploring_groupbox_changed(self, groupbox, state=None):


        state = self.manageSignal(["SINGLE_SELECTION","FEATURES"], 'disconnect')
        if state == True:
            raise SignalStateChangeError(state, ["SINGLE_SELECTION","FEATURES"])

        if groupbox == "single_selection":
  
            if self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].isChecked() is True or self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].isCollapsed() is False:


                self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setChecked(True)
                self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setCollapsed(False)

                self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setCollapsed(True)

                self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setCollapsed(True)

                self.current_exploring_groupbox = "single_selection"

                self.widgets["SINGLE_SELECTION"]["FEATURES"]["WIDGET"].setEnabled(True)
                self.widgets["SINGLE_SELECTION"]["EXPRESSION"]["WIDGET"].setEnabled(True)

                if self.current_layer != None:
                    self.exploring_features_changed(self.widgets["SINGLE_SELECTION"]["FEATURES"]["WIDGET"].feature())



        elif groupbox == "multiple_selection":

            if self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].isChecked() is True or self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].isCollapsed() is False:
                

                self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setChecked(True)
                self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setCollapsed(False)

                self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setCollapsed(True)

                self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setCollapsed(True)

                self.current_exploring_groupbox = "multiple_selection"

                self.widgets["MULTIPLE_SELECTION"]["FEATURES"]["WIDGET"].setEnabled(True)
                self.widgets["MULTIPLE_SELECTION"]["EXPRESSION"]["WIDGET"].setEnabled(True)



                if self.current_layer != None:
                    self.exploring_features_changed(self.widgets["MULTIPLE_SELECTION"]["FEATURES"]["WIDGET"].currentSelectedFeatures(), True)


        elif groupbox == "custom_selection":

            if self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].isChecked() is True or self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].isCollapsed() is False:
                

                self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setChecked(True)
                self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setCollapsed(False)

                self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setCollapsed(True)

                self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setCollapsed(True)

                self.current_exploring_groupbox = "custom_selection"

                self.widgets["CUSTOM_SELECTION"]["EXPRESSION"]["WIDGET"].setEnabled(True)

                if self.current_layer != None:
                    self.exploring_custom_selection()


        state = self.manageSignal(["SINGLE_SELECTION","FEATURES"], 'connect')
        if state == False:
            raise SignalStateChangeError(state, ["SINGLE_SELECTION","FEATURES"])

        

    def current_layer_changed(self, layer):
        if self.widgets_initialized is False:
            return

        self.current_layer = layer  

        if self.current_layer == None:
            return
        
        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
    

        widgets_to_stop =   [
                                ["SINGLE_SELECTION","FEATURES"],
                                ["SINGLE_SELECTION","EXPRESSION"],
                                ["MULTIPLE_SELECTION","FEATURES"],
                                ["MULTIPLE_SELECTION","EXPRESSION"],
                                ["CUSTOM_SELECTION","EXPRESSION"],
                                ["FILTERING","BUFFER"],
                                ["FILTERING","GEOMETRIC_PREDICATES"],
                                ["FILTERING","GEOMETRIC_PREDICATES_OPERATOR"],
                                ["FILTERING","COMBINE_OPERATOR"],
                                ["FILTERING","LAYERS_TO_FILTER"],
                                ["FILTERING","CURRENT_LAYER"]
                            ]
        
        for widget_path in widgets_to_stop:
            state = self.manageSignal(widget_path)
            if state == True:
                raise SignalStateChangeError(state, widget_path)

        if self.auto_change_current_layer_flag == True:
            widget_path = ["QGIS","LAYER_TREE_VIEW"]
            state = self.manageSignal(widget_path)
            if state == True:
                raise SignalStateChangeError(state, widget_path)





        currentLayer = self.widgets["FILTERING"]["CURRENT_LAYER"]["WIDGET"].currentLayer()
        if currentLayer != None and currentLayer.id() != self.current_layer.id():
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


        for properties_tuples_key in self.properties_tuples_dict:
            properties_tuples = self.properties_tuples_dict[properties_tuples_key]
            for i, property_tuple in enumerate(properties_tuples):
                widget_type = self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["TYPE"]
                if widget_type == 'PushButton':
                    self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setChecked(layer_props[property_tuple[0]][property_tuple[1]])
                elif widget_type == 'CheckableComboBox':
                    self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setCheckedItems(layer_props[property_tuple[0]][property_tuple[1]])
                elif widget_type == 'CustomCheckableComboBox':
                    self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["CUSTOM_LOAD_FUNCTION"]
                elif widget_type == 'ComboBox':
                     self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setCurrentText(layer_props[property_tuple[0]][property_tuple[1]])
                elif widget_type == 'QgsDoubleSpinBox':
                    self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setValue(layer_props[property_tuple[0]][property_tuple[1]])

        for properties_group in self.properties_tuples_dict:
            if properties_group != 'is':
                self.properties_group_state_changed(self.properties_tuples_dict[properties_group])

        self.filtering_populate_layers_chekableCombobox()

        for widget_path in widgets_to_stop:
            state = self.manageSignal(widget_path)
            if state == False:
                raise SignalStateChangeError(state, widget_path)

        if self.auto_change_current_layer_flag == True:
            if self.iface.activeLayer().id() != self.current_layer.id():
                self.widgets["QGIS"]["LAYER_TREE_VIEW"]["WIDGET"].setCurrentLayer(self.current_layer)

            widget_path = ["QGIS","LAYER_TREE_VIEW"]
            state = self.manageSignal(widget_path)
            if state == False:
                raise SignalStateChangeError(state, widget_path)
    
        self.exploring_link_widgets()   


    def exploring_link_widgets(self, expression=None):

        if self.current_layer == None:
            return
        
        state = self.manageSignal(["SINGLE_SELECTION","FEATURES"], 'disconnect')
        if state == True:
            raise SignalStateChangeError(state, ["SINGLE_SELECTION","FEATURES"])
        

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
                features, expression = self.getExploringFeatures(self.widgets["MULTIPLE_SELECTION"]["FEATURES"]["WIDGET"].currentSelectedFeatures(), True)
                if len(features) > 0 and expression != None:
                    self.widgets["SINGLE_SELECTION"]["FEATURES"]["WIDGET"].setFilterExpression(expression)
            elif self.widgets["MULTIPLE_SELECTION"]["FEATURES"]["WIDGET"].currentVisibleFeatures() != False:
                features, expression = self.getExploringFeatures(self.widgets["MULTIPLE_SELECTION"]["FEATURES"]["WIDGET"].currentVisibleFeatures(), True)
                if len(features) > 0 and expression != None:
                    self.widgets["SINGLE_SELECTION"]["FEATURES"]["WIDGET"].setFilterExpression(expression)
            elif custom_filter != None:
                self.widgets["SINGLE_SELECTION"]["FEATURES"]["WIDGET"].setFilterExpression(custom_filter)
           
        else:
            self.widgets["SINGLE_SELECTION"]["FEATURES"]["WIDGET"].setFilterExpression('')
            self.widgets["MULTIPLE_SELECTION"]["FEATURES"]["WIDGET"].setFilterExpression('')

        state = self.manageSignal(["SINGLE_SELECTION","FEATURES"], 'connect')
        if state == False:
            raise SignalStateChangeError(state, ["SINGLE_SELECTION","FEATURES"])
        

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


    def dialog_export_folder(self):

        if self.widgets["EXPORTING"]["HAS_OUTPUT_FOLDER"]["WIDGET"].isChecked() == True:
            
            folderpath = str(QtWidgets.QFileDialog.getExistingDirectory(self, 'Select a folder where to export your layers', self.current_project_path))

            if folderpath:
                self.widgets["EXPORTING"]["OUTPUT_FOLDER"]["WIDGET"].setText(folderpath)
                print(folderpath)
            else:
                self.widgets["EXPORTING"]["HAS_OUTPUT_FOLDER"]["WIDGET"].setChecked(False)
        else:
            self.widgets["EXPORTING"]["OUTPUT_FOLDER"]["WIDGET"].clear()

    def reset_export_folder(self):

        if str(self.widgets["EXPORTING"]["OUTPUT_FOLDER"]["WIDGET"].text()) == '':
            self.widgets["EXPORTING"]["OUTPUT_FOLDER"]["WIDGET"].clear()
            self.widgets["EXPORTING"]["HAS_OUTPUT_FOLDER"]["WIDGET"].setChecked(False)


    def dialog_export_zip(self):

        if self.widgets["EXPORTING"]["HAS_ZIP"]["WIDGET"].isChecked() == True:

            
            filepath = str(QtWidgets.QFileDialog.getSaveFileName(self, 'Save your exported data to a zip file', os.path.join(self.current_project_path, self.output_name) ,'*.zip')[0])

            if filepath:
                self.widgets["EXPORTING"]["ZIP"]["WIDGET"].setText(filepath)
                print(filepath)
            else:
                self.widgets["EXPORTING"]["HAS_ZIP"]["WIDGET"].setChecked(False)
        else:
            self.widgets["EXPORTING"]["ZIP"]["WIDGET"].clear()


    def reset_export_zip(self):

        if str(self.widgets["EXPORTING"]["ZIP"]["WIDGET"].text()) == '':
            self.widgets["EXPORTING"]["ZIP"]["WIDGET"].clear()
            self.widgets["EXPORTING"]["HAS_ZIP"]["WIDGET"].setChecked(False)


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



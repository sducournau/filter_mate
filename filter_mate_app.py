from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import QgsCheckableComboBox, QgsFeatureListComboBox, QgsFieldExpressionWidget
from qgis.utils import *
from qgis import processing

from collections import OrderedDict
from operator import getitem
import zipfile
import os.path
from pathlib import Path
import re
from .config.config import *
from functools import partial
import json
from .modules.customExceptions import *
from .modules.appTasks import *
from .resources import *

# Import the code for the DockWidget
from .filter_mate_dockwidget import FilterMateDockWidget

MESSAGE_TASKS_CATEGORIES = {
                            'filter':'FilterLayers',
                            'unfilter':'FilterLayers',
                            'reset':'FilterLayers',
                            'export':'ExportLayers',
                            'add_layers':'ManageLayers',
                            'remove_layers':'ManageLayers',
                            'remove_all_layers':'ManageLayers',
                            'new_project':'ManageLayers',
                            'project_read':'ManageLayers'
                            }

class FilterMateApp:

    PROJECT_LAYERS = {} 


    def __init__(self, plugin_dir):
        self.iface = iface
        self.MapLayerStore = QgsMapLayerStore()
        self.dockwidget = None
        self.flags = {}
        self.CONFIG_DATA = CONFIG_DATA

        self.plugin_dir = plugin_dir
        self.appTasks = {"filter":None,"unfilter":None,"reset":None,"export":None,"add_layers":None,"remove_layers":None,"remove_all_layers":None,"new_project":None,"project_read":None}
        self.tasks_descriptions = {
                                    'filter':'Filtering data',
                                    'unfilter':'Unfiltering data',
                                    'reset':'Reseting data',
                                    'export':'Exporting data',
                                    'add_layers':'Adding layers',
                                    'remove_layers':'Removing layers',
                                    'remove_all_layers':'Removing all layers',
                                    'new_project':'New project',
                                    'project_read':'Existing project loaded'
                                    }
        
        self.PROJECT = QgsProject.instance()
        self.run()


    def run(self):
        if self.dockwidget == None:
            


            init_layers = list(self.PROJECT.mapLayers().values())

            self.dockwidget = FilterMateDockWidget(self.PROJECT_LAYERS, self.plugin_dir, self.CONFIG_DATA, self.PROJECT)

            if init_layers != None and len(init_layers) > 0:
                self.manage_task('add_layers', init_layers)

            # show the dockwidget
            # TODO: fix to allow choice of dock location
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
            self.dockwidget.show()


        """Keep the advanced filter combobox updated on adding or removing layers"""
        self.iface.projectRead.connect(lambda x='project_read': self.manage_task(x))
        self.iface.newProjectCreated.connect(lambda x='new_project': self.manage_task(x))
        self.MapLayerStore.layersAdded.connect(lambda layers, x='add_layers': self.manage_task(x, layers))
        self.MapLayerStore.layersWillBeRemoved.connect(lambda layers, x='remove_layers': self.manage_task(x, layers))
        self.MapLayerStore.allLayersRemoved.connect(lambda layers, x='remove_all_layers': self.manage_task(x))
        
        self.dockwidget.launchingTask.connect(lambda x: self.manage_task(x))

        self.dockwidget.resettingLayerVariableOnError.connect(lambda layer, properties: self.remove_variables_from_layer(layer, properties))
        self.dockwidget.settingLayerVariable.connect(lambda layer, properties: self.save_variables_from_layer(layer, properties))
        self.dockwidget.resettingLayerVariable.connect(lambda layer, properties: self.remove_variables_from_layer(layer, properties))



        
        """Overload configuration qtreeview model to keep configuration file up to date"""
        # 
        # self.managerWidgets.model.rowsInserted.connect(self.qtree_signal)
        # self.managerWidgets.model.rowsRemoved.connect(self.qtree_signal)


    def manage_task(self, task_name, data=None):
        """Manage the different tasks"""

        assert task_name in list(self.tasks_descriptions.keys())

        if self.dockwidget != None:
            self.PROJECT_LAYERS = self.dockwidget.PROJECT_LAYERS

        if task_name == 'remove_all_layers':
           QgsApplication.taskManager().cancelAll()
           self.dockwidget.disconnect_widgets_signals()
           self.dockwidget.reset_multiple_checkable_combobox()
           self.layer_management_engine_task_completed({}, task_name)
           return
        
        if task_name in ('project_read', 'new_project'):
            QgsApplication.taskManager().cancelAll()
            self.PROJECT = QgsProject.instance()
            init_layers = list(self.PROJECT.mapLayers().values())
            if len(init_layers) > 0:
                self.manage_task('add_layers', init_layers)
            else:
                self.dockwidget.disconnect_widgets_signals()
                self.dockwidget.reset_multiple_checkable_combobox()
                self.layer_management_engine_task_completed({}, 'remove_all_layers')
            return

        task_parameters = self.get_task_parameters(task_name, data)

        if task_name in [name for name in self.tasks_descriptions.keys() if "layer" not in name]:

            if self.dockwidget == None or self.dockwidget.current_layer == None:
                return
            else:
                current_layer = self.dockwidget.current_layer 


                
            layers = []
            self.appTasks[task_name] = FilterEngineTask(self.tasks_descriptions[task_name], task_name, task_parameters)
            layers_props = [layer_infos for layer_infos in self.PROJECT_LAYERS[current_layer.id()]["filtering"]["layers_to_filter"]]
            layers_ids = [layer_props["layer_id"] for layer_props in layers_props]
            for layer_props in layers_props:
                temp_layers = self.PROJECT.mapLayersByName(layer_props["layer_name"])
                for temp_layer in temp_layers:
                    if temp_layer.id() in layers_ids: 
                        layers.append(temp_layer)

            self.appTasks[task_name].setDependentLayers(layers + [current_layer])
            self.appTasks[task_name].taskCompleted.connect(lambda task_name=task_name, current_layer=current_layer, task_parameters=task_parameters: self.filter_engine_task_completed(task_name, current_layer, task_parameters))
            
        else:
            self.appTasks[task_name] = LayersManagementEngineTask(self.tasks_descriptions[task_name], task_name, task_parameters)

            if task_name == "add_layers":
                self.appTasks[task_name].setDependentLayers(task_parameters["task"]["layers"])
                self.appTasks[task_name].begun.connect(self.dockwidget.disconnect_widgets_signals)
            elif task_name == "remove_layers":
                self.appTasks[task_name].begun.connect(self.dockwidget.on_remove_layer_task_begun)
            
            # self.appTasks[task_name].taskCompleted.connect(lambda state='connect': self.dockwidget_change_widgets_signal(state))

            self.appTasks[task_name].resultingLayers.connect(lambda result_project_layers, task_name=task_name: self.layer_management_engine_task_completed(result_project_layers, task_name))
            self.appTasks[task_name].savingLayerVariable.connect(lambda layer, variable_key, value_typped, type_returned: self.saving_layer_variable(layer, variable_key, value_typped, type_returned))
            self.appTasks[task_name].removingLayerVariable.connect(lambda layer, variable_key: self.removing_layer_variable(layer, variable_key))

        
    
        QgsApplication.taskManager().addTask(self.appTasks[task_name])

    def on_remove_layer_task_begun(self):
        self.dockwidget.disconnect_widgets_signals()
        self.dockwidget.reset_multiple_checkable_combobox()
    

    def get_task_parameters(self, task_name, data=None):

        

        if task_name in [name for name in self.tasks_descriptions.keys() if "layer" not in name]:

            if self.dockwidget == None or self.dockwidget.current_layer == None:
                return
            else:
                current_layer = self.dockwidget.current_layer 

            if current_layer.id() in self.PROJECT_LAYERS.keys():
                task_parameters = self.PROJECT_LAYERS[current_layer.id()]

            if current_layer.subsetString() != '':
                self.PROJECT_LAYERS[current_layer.id()]["infos"]["is_already_subset"] = True
            else:
                self.PROJECT_LAYERS[current_layer.id()]["infos"]["is_already_subset"] = False

            features, expression = self.dockwidget.get_current_features()

            if task_name == 'filter':

                task_parameters["task"] = {"features": features, "expression": expression, "filtering": self.dockwidget.project_props["filtering"]}
                return task_parameters

            elif task_name == 'unfilter':

                task_parameters["task"] = {"features": features, "expression": expression, "filtering": self.dockwidget.project_props["filtering"]}
                return task_parameters
            
            elif task_name == 'reset':

                task_parameters["task"] = {"features": features, "expression": expression}
                return task_parameters

            elif task_name == 'export':
                
                task_parameters["task"] = self.dockwidget.project_props
                return task_parameters
            
        else:
            if data != None:
                reset_all_layers_variables_flag = False
                task_parameters = {}

                if task_name == 'add_layers':
                    if isinstance(data, list):
                        layers = data
                    else:
                        layers = [data]

                    if self.CONFIG_DATA["APP"]["FRESH_RELOAD_FLAG"] is True and self.dockwidget.has_loaded_layers is False:
                        reset_all_layers_variables_flag = True

                    task_parameters["task"] = {"layers": layers, "project_layers": self.PROJECT_LAYERS, "reset_all_layers_variables_flag":reset_all_layers_variables_flag }
                    return task_parameters

                elif task_name == 'remove_layers':
                    if isinstance(data, list):
                        layers = data
                    else:
                        layers = [data]

                    if self.CONFIG_DATA["APP"]["FRESH_RELOAD_FLAG"] is True and self.dockwidget.has_loaded_layers is False:
                        reset_all_layers_variables_flag = True

                    task_parameters["task"] = {"layers": layers, "project_layers": self.PROJECT_LAYERS, "reset_all_layers_variables_flag": reset_all_layers_variables_flag }
                    return task_parameters




    def filter_engine_task_completed(self, task_name, current_layer, task_parameters):
        
        # if self.PROJECT_LAYERS.
        #     first_launch = bool(QgsExpressionContextUtils.projectScope(self.PROJECT).variable('first_launch'))
        #     history_table_exists = bool(QgsExpressionContextUtils.projectScope(self.PROJECT).variable('history_table_exists'))

        # if history_table_exists is False:
        #     vl = QgsVectorLayer("Point", "temp", "memory")
        
        #     QgsExpressionContextUtils.setProjectVariable(self.PROJECT, 'history_table_exists','True')

        if current_layer.subsetString() != '':
            self.PROJECT_LAYERS[current_layer.id()]["infos"]["is_already_subset"] = True
            if task_name == 'filter':

                if isinstance(self.PROJECT_LAYERS[current_layer.id()]["infos"]["subset_history"], list):
                    pass
                else:
                    self.PROJECT_LAYERS[current_layer.id()]["infos"]["subset_history"] = []

                self.PROJECT_LAYERS[current_layer.id()]["infos"]["subset_history"].append({"source_layer":current_layer.id(), "subset_string":current_layer.subsetString()})

            elif task_name == 'unfilter':

                if isinstance(self.PROJECT_LAYERS[current_layer.id()]["infos"]["subset_history"], list) is False:
                    self.PROJECT_LAYERS[current_layer.id()]["infos"]["subset_history"] = list(self.PROJECT_LAYERS[current_layer.id()]["infos"]["subset_history"])

                if len(self.PROJECT_LAYERS[current_layer.id()]["infos"]["subset_history"]) > 0:
                    self.PROJECT_LAYERS[current_layer.id()]["infos"]["subset_history"].pop()
                else:
                    self.PROJECT_LAYERS[current_layer.id()]["infos"]["subset_history"] = []
                    
        else:
            self.PROJECT_LAYERS[current_layer.id()]["infos"]["is_already_subset"] = False
            self.PROJECT_LAYERS[current_layer.id()]["infos"]["subset_history"] = []

        if self.PROJECT_LAYERS[current_layer.id()]["infos"]["layer_provider_type"] != 'postgresql':
            self.create_spatial_index_for_layer(current_layer)

        self.save_variables_from_layer(current_layer,[("infos","is_already_subset"),("infos","subset_history")])

        if task_parameters["filtering"]["has_layers_to_filter"] == True:
            for layer_props in task_parameters["filtering"]["layers_to_filter"]:
                if layer_props["layer_id"] in self.PROJECT_LAYERS:
                    layers = [layer for layer in self.PROJECT.mapLayersByName(layer_props["layer_name"]) if layer.id() == layer_props["layer_id"]]
                    if len(layers) == 1:

                        layer = layers[0]

                        if layer.subsetString() != '':
                            self.PROJECT_LAYERS[layer.id()]["infos"]["is_already_subset"] = True
                            if task_name == 'filter':

                                if isinstance(self.PROJECT_LAYERS[layer.id()]["infos"]["subset_history"], list) is False:
                                    self.PROJECT_LAYERS[layer.id()]["infos"]["subset_history"] = list(self.PROJECT_LAYERS[layer.id()]["infos"]["subset_history"])

                                self.PROJECT_LAYERS[layer.id()]["infos"]["subset_history"].append({"source_layer":current_layer.id(), "subset_string":layer.subsetString()})

                            elif task_name == 'unfilter':

                                if isinstance(self.PROJECT_LAYERS[layer.id()]["infos"]["subset_history"], list) is False:
                                    self.PROJECT_LAYERS[layer.id()]["infos"]["subset_history"] = list(self.PROJECT_LAYERS[layer.id()]["infos"]["subset_history"])

                                if len(self.PROJECT_LAYERS[layer.id()]["infos"]["subset_history"]) > 0:
                                    self.PROJECT_LAYERS[layer.id()]["infos"]["subset_history"].pop()
                                else:
                                    self.PROJECT_LAYERS[current_layer.id()]["infos"]["subset_history"] = []

                        else:
                            self.PROJECT_LAYERS[layer.id()]["infos"]["is_already_subset"] = False
                            self.PROJECT_LAYERS[layer.id()]["infos"]["subset_history"] = []

                        

                        if self.PROJECT_LAYERS[layer.id()]["infos"]["layer_provider_type"] != 'postgresql':
                            self.create_spatial_index_for_layer(layer)


                        self.save_variables_from_layer(layer,[("infos","is_already_subset"),("infos","subset_history")])

        self.iface.mapCanvas().refreshAllLayers()
        self.iface.mapCanvas().refresh()
         
        self.dockwidget.get_project_layers_from_app(self.PROJECT_LAYERS, self.PROJECT)


        if task_name == 'filter' or task_name == 'unfilter':
            features_iterator = current_layer.getFeatures()
            done_looping = False
            features = []

            while not done_looping:
                try:
                    feature = next(features_iterator)
                    features.append(feature)
                except StopIteration:
                    done_looping = True
            self.dockwidget.exploring_zoom_clicked(features if len(features) > 0 else None)
        


    def save_variables_from_layer(self, layer, layer_properties=[]):

        layer_all_properties_flag = False

        assert isinstance(layer, QgsVectorLayer)

        if len(layer_properties) == 0:
            layer_all_properties_flag = True

        if layer.id() in self.PROJECT_LAYERS.keys():

            if layer_all_properties_flag is True:
                for key_group in ("infos", "exploring", "filtering"):
                    for key, value in self.PROJECT_LAYERS[layer.id()][key_group].items():
                        variable_key = "filterMate_{key_group}_{key}".format(key_group=key_group, key=key)
                        value_typped, type_returned = self.return_typped_value(value, 'save')
                        if type_returned in (list, dict):
                            QgsExpressionContextUtils.setLayerVariable(layer, variable_key, json.dumps(value_typped))
                        else:
                            QgsExpressionContextUtils.setLayerVariable(layer, variable_key, value_typped)
            
            else:
                for layer_property in layer_properties:
                    if layer_property[0] in ("infos", "exploring", "filtering"):
                        if layer_property[0] in self.PROJECT_LAYERS[layer.id()] and layer_property[1] in self.PROJECT_LAYERS[layer.id()][layer_property[0]]:
                            variable_key = "filterMate_{key_group}_{key}".format(key_group=layer_property[0], key=layer_property[1])
                            value = self.PROJECT_LAYERS[layer.id()][layer_property[0]][layer_property[1]]
                            value_typped, type_returned = self.return_typped_value(value, 'save')
                            if type_returned in (list, dict):
                                QgsExpressionContextUtils.setLayerVariable(layer, variable_key, json.dumps(value_typped))
                            else:
                                QgsExpressionContextUtils.setLayerVariable(layer, variable_key, value_typped)

    

    def remove_variables_from_layer(self, layer, layer_properties=[]):
        
        layer_all_properties_flag = False

        assert isinstance(layer, QgsVectorLayer)

        if len(layer_properties) == 0:
            layer_all_properties_flag = True

        if layer.id() in self.PROJECT_LAYERS.keys():

            layer_scope = QgsExpressionContextUtils.layerScope(layer)

            if layer_all_properties_flag is True:
                QgsExpressionContextUtils.setLayerVariables(layer, {})

            else:
                for layer_property in layer_properties:
                    if layer_property[0] in ("infos", "exploring", "filtering"):
                        if layer_property[0] in self.PROJECT_LAYERS[layer.id()] and layer_property[1] in self.PROJECT_LAYERS[layer.id()][layer_property[0]]:
                            variable_key = "filterMate_{key_group}_{key}".format(key_group=layer_property[0], key=layer_property[1])
                            layer_scope.removeVariable(variable_key)
            

      

    def create_spatial_index_for_layer(self, layer):    

        alg_params_createspatialindex = {
            "INPUT": layer
        }
        processing.run('qgis:createspatialindex', alg_params_createspatialindex)
    

    def layer_management_engine_task_completed(self, result_project_layers, task_name):

        self.PROJECT_LAYERS = result_project_layers
        self.PROJECT = QgsProject.instance()

        if self.dockwidget != None:

            if task_name in ("add_layers","remove_layers","remove_all_layers"):
                if task_name == 'remove_layers':
                    for layer_key in self.PROJECT_LAYERS.keys():
                        if layer_key not in self.dockwidget.PROJECT_LAYERS.keys():
                            try:
                                self.dockwidget.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].remove_list_widget(layer_key)
                            except:
                                pass

                self.dockwidget.get_project_layers_from_app(self.PROJECT_LAYERS, self.PROJECT)
        

    def can_cast(self, dest_type, source_value):
        try:
            dest_type(source_value)
            return True
        except:
            return False


    def return_typped_value(self, value_as_string, action=None):
        value_typped= None
        type_returned = None

        if value_as_string == None or value_as_string == '':   
            value_typped = str('')
            type_returned = str
        elif str(value_as_string).find('{') == 0 and self.can_cast(dict, value_as_string) is True:
            if action == 'save':
                value_typped = json.dumps(dict(value_as_string))
            elif action == 'load':
                value_typped = dict(json.loads(value_as_string))
            type_returned = dict
        elif str(value_as_string).find('[') == 0 and self.can_cast(list, value_as_string) is True:
            if action == 'save':
                value_typped = list(value_as_string)
            elif action == 'load':
                value_typped = list(json.loads(value_as_string))
            type_returned = list
        elif self.can_cast(bool, value_as_string) is True and str(value_as_string).upper() in ('FALSE','TRUE'):
            value_typped = bool(value_as_string)
            type_returned = bool
        elif self.can_cast(float, value_as_string) is True and len(str(value_as_string).split('.')) > 1:
            value_typped = float(value_as_string)
            type_returned = float
        elif self.can_cast(int, value_as_string) is True:
            value_typped = int(value_as_string)
            type_returned = int
        else:
            value_typped = str(value_as_string)
            type_returned = str

        return value_typped, type_returned       

# class barProgress:

#     def __init__(self):
#         self.prog = 0
#         self.bar = None
#         self.type = type
#         iface.messageBar().clearWidgets()
#         self.init()
#         self.bar.show()

#     def init(self):
#         self.bar = QProgressBar()
#         self.bar.setMaximum(100)
#         self.bar.setValue(self.prog)
#         iface.mainWindow().statusBar().addWidget(self.bar)

#     def show(self):
#         self.bar.show()


#     def update(self, prog):
#         self.bar.setValue(prog)

#     def hide(self):
#         self.bar.hide()

# class msgProgress:

#     def __init__(self):
#         self.messageBar = iface.messageBar().createMessage('Doing something time consuming...')
#         self.progressBar = QProgressBar()
#         self.progressBar.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
#         self.cancelButton = QPushButton()
#         self.cancelButton.setText('Cancel')
#         self.messageBar.layout().addWidget(self.progressBar)
#         self.messageBar.layout().addWidget(self.cancelButton)
#         iface.messageBar().pushWidget(self.messageBar, Qgis.Info)


#     def update(self, prog):
#         self.progressBar.setValue(prog)

#     def reset(self):
#         self.progressBar.setValue(0)

#     def setText(self, text):
#         self.messageBar.setText(text)




def zoom_to_features(layer, t0):
    end = time.time() - t0
    print("DONE" + " IN " + str(end) + " s.")
    canvas = iface.mapCanvas()
    canvas.setExtent(layer.extent())
    canvas.refresh()

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
from shutil import copyfile
import re
from .config.config import *
from functools import partial
import json
from .modules.customExceptions import *
from .modules.appTasks import *
from .resources import *
import uuid


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
        self.PLUGIN_CONFIG_DIRECTORY = PLUGIN_CONFIG_DIRECTORY
        self.db_name = 'filterMate_db.sqlite'
        self.db_file_path = os.path.normpath(self.PLUGIN_CONFIG_DIRECTORY + os.sep + self.db_name)
        self.project_file_name = os.path.basename(self.PROJECT.absoluteFilePath())
        self.project_file_path = self.PROJECT.absolutePath()
        self.project_uuid = ''
        self.run()


    def run(self):
        if self.dockwidget == None:
            
            QgsExpressionContextUtils.setProjectVariable(self.PROJECT, 'filterMate_db_project_uuid', '')    

            init_layers = list(self.PROJECT.mapLayers().values())

            self.init_filterMate_db()
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
            self.CONFIG_DATA = self.dockwidget.CONFIG_DATA

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
            self.init_filterMate_db()
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
                self.appTasks[task_name].setDependentLayers([layer_tuple[0] for layer_tuple in task_parameters["task"]["layers"]])
                self.appTasks[task_name].begun.connect(self.dockwidget.disconnect_widgets_signals)
            elif task_name == "remove_layers":
                self.appTasks[task_name].begun.connect(self.dockwidget.on_remove_layer_task_begun)
            
            # self.appTasks[task_name].taskCompleted.connect(lambda state='connect': self.dockwidget_change_widgets_signal(state))

            self.appTasks[task_name].resultingLayers.connect(lambda result_project_layers, task_name=task_name: self.layer_management_engine_task_completed(result_project_layers, task_name))
            self.appTasks[task_name].savingLayerVariable.connect(lambda layer, variable_key, value_typped, type_returned: self.saving_layer_variable(layer, variable_key, value_typped, type_returned))
            self.appTasks[task_name].removingLayerVariable.connect(lambda layer, variable_key: self.removing_layer_variable(layer, variable_key))

        try:
            active_tasks = QgsApplication.taskManager().activeTasks()
            if len(active_tasks) > 0:
                for active_task in active_tasks:
                    key_active_task = [k for k, v in self.tasks_descriptions.items() if v == active_task.description()][0]
                    if key_active_task in ('filter','reset','unfilter'):
                        active_task.cancel()
        except:
            pass
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

                task_parameters["task"] = {"features": features, "expression": expression, "filtering": self.dockwidget.project_props["filtering"], 
                                           "db_file_path": self.db_file_path, "project_uuid": self.project_uuid }
                return task_parameters

            elif task_name == 'unfilter':

                task_parameters["task"] = {"features": features, "expression": expression, "filtering": self.dockwidget.project_props["filtering"], 
                                           "db_file_path": self.db_file_path, "project_uuid": self.project_uuid }
                return task_parameters
            
            elif task_name == 'reset':

                task_parameters["task"] = {"features": features, "expression": expression, 
                                           "db_file_path": self.db_file_path, "project_uuid": self.project_uuid }
                return task_parameters

            elif task_name == 'export':
                
                task_parameters["task"] = self.dockwidget.project_props
                return task_parameters
            
        else:
            if data != None:
                reset_all_layers_variables_flag = False
                task_parameters = {}

                if task_name == 'add_layers':

                    new_layers = []

                    if isinstance(data, list):
                        layers = data
                    else:
                        layers = [data]

                    if self.CONFIG_DATA["APP"]["FRESH_RELOAD_FLAG"] is True and self.dockwidget.has_loaded_layers is False:
                        reset_all_layers_variables_flag = True

                    for layer in layers:
                        layer_total_features_count = None
                        layer_features_source = 0

                        subset_string_init = layer.subsetString()
                        if subset_string_init != '':
                            layer.setSubsetString('')

                        data_provider_layer = layer.dataProvider()
                        if data_provider_layer:
                            layer_total_features_count = data_provider_layer.featureCount()
                            layer_features_source = data_provider_layer.featureSource()

                        if subset_string_init != '':
                            layer.setSubsetString(subset_string_init)
                        
                        new_layers.append((layer, layer_features_source, layer_total_features_count))

                    task_parameters["task"] = {"layers": new_layers, "project_layers": self.PROJECT_LAYERS, "reset_all_layers_variables_flag":reset_all_layers_variables_flag }
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


    def filter_engine_task_completed(self, task_name, source_layer, task_parameters):

        if task_name in ('filter','unfilter','reset'):


            self.apply_subset_filter(task_name, source_layer)


            source_layer.reload()
            source_layer.updateExtents()
            source_layer.triggerRepaint()

            if self.PROJECT_LAYERS[source_layer.id()]["infos"]["layer_provider_type"] != 'postgresql':
                self.create_spatial_index_for_layer(source_layer)

            # self.save_variables_from_layer(source_layer,[("infos","is_already_subset")])
            
            
            if task_parameters["filtering"]["has_layers_to_filter"] == True:
                for layer_props in task_parameters["filtering"]["layers_to_filter"]:
                    if layer_props["layer_id"] in self.PROJECT_LAYERS:
                        layers = [layer for layer in self.PROJECT.mapLayersByName(layer_props["layer_name"]) if layer.id() == layer_props["layer_id"]]
                        if len(layers) == 1:
                            layer = layers[0]

                            self.apply_subset_filter(task_name, layer)

                            layer.reload()
                            layer.updateExtents()
                            layer.triggerRepaint()

                            

                            if self.PROJECT_LAYERS[layer.id()]["infos"]["layer_provider_type"] != 'postgresql':
                                self.create_spatial_index_for_layer(layer)

                            # self.save_variables_from_layer(layer,[("infos","is_already_subset")])

            self.iface.mapCanvas().refreshAllLayers()
            self.iface.mapCanvas().refresh()
         
        self.dockwidget.get_project_layers_from_app(self.PROJECT_LAYERS, self.PROJECT)


        if task_name == 'filter' or task_name == 'unfilter':
            features_iterator = source_layer.getFeatures()
            done_looping = False
            features = []

            while not done_looping:
                try:
                    feature = next(features_iterator)
                    features.append(feature)
                except StopIteration:
                    done_looping = True
            self.dockwidget.exploring_zoom_clicked(features if len(features) > 0 else None)
        

    def apply_subset_filter(self, task_name, layer):

        conn = spatialite_connect(self.db_file_path)
        cur = conn.cursor()

        last_subset_string = ''

        cur.execute("""SELECT * FROM fm_subset_history WHERE fk_project = '{fk_project}' AND layer_id = '{layer_id}' ORDER BY seq_order DESC LIMIT 1;""".format(
                                                                                                                                                        fk_project=self.project_uuid,
                                                                                                                                                        layer_id=layer.id()
                                                                                                                                                        )
        )

        results = cur.fetchall()

        if len(results) == 1:
            result = results[0]
            last_subset_string = result[6].replace("\'\'", "\'")

        if task_name in ('filter', 'unfilter'):

            layer.setSubsetString(last_subset_string)

            if layer.subsetString() != '':
                self.PROJECT_LAYERS[layer.id()]["infos"]["is_already_subset"] = True
            else:
                self.PROJECT_LAYERS[layer.id()]["infos"]["is_already_subset"] = False

        elif task_name == 'reset':
            layer.setSubsetString('')
            self.PROJECT_LAYERS[layer.id()]["infos"]["is_already_subset"] = False

        cur.close()
        conn.close()


    def save_variables_from_layer(self, layer, layer_properties=[]):

        layer_all_properties_flag = False

        assert isinstance(layer, QgsVectorLayer)

        if len(layer_properties) == 0:
            layer_all_properties_flag = True

        if layer.id() in self.PROJECT_LAYERS.keys():

            conn = spatialite_connect(self.db_file_path)
            cur = conn.cursor()

            if layer_all_properties_flag is True:
                for key_group in ("infos", "exploring", "filtering"):
                    for key, value in self.PROJECT_LAYERS[layer.id()][key_group].items():
                        value_typped, type_returned = self.return_typped_value(value, 'save')
                        if type_returned in (list, dict):
                            value_typped = json.dumps(value_typped)
                        QgsExpressionContextUtils.setLayerVariable(layer, key_group + '_' +  key, value_typped)
                        cur.execute("""INSERT INTO fm_project_layers_properties 
                                        VALUES('{id}', datetime(), datetime(), '{project_id}', '{layer_id}', '{meta_type}', '{meta_key}', '{meta_value}');""".format(
                                                                            id=uuid.uuid4(),
                                                                            project_id=self.project_uuid,
                                                                            layer_id=layer.id(),
                                                                            meta_type=key_group,
                                                                            meta_key=key,
                                                                            meta_value=value_typped.replace("\'","\'\'") if type_returned in (str, dict, list) else value_typped
                                                                            )
                        )
                        conn.commit()



            else:
                for layer_property in layer_properties:
                    if layer_property[0] in ("infos", "exploring", "filtering"):
                        if layer_property[0] in self.PROJECT_LAYERS[layer.id()] and layer_property[1] in self.PROJECT_LAYERS[layer.id()][layer_property[0]]:
                            value = self.PROJECT_LAYERS[layer.id()][layer_property[0]][layer_property[1]]
                            value_typped, type_returned = self.return_typped_value(value, 'save')
                            if type_returned in (list, dict):
                                value_typped = json.dumps(value_typped)
                            QgsExpressionContextUtils.setLayerVariable(layer, layer_property[0] + '_' +  layer_property[1], value_typped)
                            cur.execute("""INSERT INTO fm_project_layers_properties 
                                            VALUES('{id}', datetime(), datetime(), '{project_id}', '{layer_id}', '{meta_type}', '{meta_key}', '{meta_value}');""".format(
                                                                                id=uuid.uuid4(),
                                                                                project_id=self.project_uuid,
                                                                                layer_id=layer.id(),
                                                                                meta_type=layer_property[0],
                                                                                meta_key=layer_property[1],
                                                                                meta_value=value_typped.replace("\'","\'\'") if type_returned in (str, dict, list) else value_typped
                                                                                )
                            )
                            conn.commit()

            cur.close()
            conn.close()

    def remove_variables_from_layer(self, layer, layer_properties=[]):
        
        layer_all_properties_flag = False

        assert isinstance(layer, QgsVectorLayer)

        if len(layer_properties) == 0:
            layer_all_properties_flag = True

        if layer.id() in self.PROJECT_LAYERS.keys():

            conn = spatialite_connect(self.db_file_path)
            cur = conn.cursor()

            if layer_all_properties_flag is True:
                cur.execute("""DELETE FROM fm_project_layers_properties 
                                WHERE fk_project = '{project_id}' and layer_id = '{layer_id}';""".format(
                                                                                                    project_id=self.project_uuid,
                                                                                                    layer_id=layer.id()
                                                                                                    )
                )
                conn.commit()
                QgsExpressionContextUtils.setLayerVariables(layer, {})

            else:
                for layer_property in layer_properties:
                    if layer_property[0] in ("infos", "exploring", "filtering"):
                        if layer_property[0] in self.PROJECT_LAYERS[layer.id()] and layer_property[1] in self.PROJECT_LAYERS[layer.id()][layer_property[0]]:
                            cur.execute("""DELETE FROM fm_project_layers_properties  
                                            WHERE fk_project = '{project_id}' and layer_id = '{layer_id}' and meta_type = '{meta_type}' and meta_key = '{meta_key}');""".format(
                                                                                                                                                                            project_id=self.project_uuid,
                                                                                                                                                                            layer_id=layer.id(),
                                                                                                                                                                            meta_type=layer_property[0],
                                                                                                                                                                            meta_key=layer_property[1]                           
                                                                                                                                                                            )
                            )
                            conn.commit()
                            QgsExpressionContextUtils.setLayerVariable(layer, layer_property[0] + '_' + layer_property[1], '')

      

    def create_spatial_index_for_layer(self, layer):    

        alg_params_createspatialindex = {
            "INPUT": layer
        }
        processing.run('qgis:createspatialindex', alg_params_createspatialindex)
    

    def init_filterMate_db(self):

        if self.PROJECT != None and len(list(self.PROJECT.mapLayers().values())) > 0:

            self.project_file_name = os.path.basename(self.PROJECT.absoluteFilePath())
            self.project_file_path = self.PROJECT.absolutePath()
            project_settings = json.dumps(self.CONFIG_DATA["CURRENT_PROJECT"])

            print(self.db_file_path)

            if self.CONFIG_DATA["APP"]["FRESH_RELOAD_FLAG"] is True:
                os.remove(self.db_file_path)
                self.CONFIG_DATA["APP"]["FRESH_RELOAD_FLAG"] = False
                with open(DIR_CONFIG +  os.sep + 'config.json', 'w') as outfile:
                    outfile.write(json.dumps(self.CONFIG_DATA, indent=4))
                    
            if not os.path.exists(self.db_file_path):
                memory_uri = 'NoGeometry?field=plugin_name:string(255,0)&field=_created_at:date(0,0)&field=_updated_at:date(0,0)&field=_version:string(255,0)'
                layer_name = 'filterMate_db'
                layer = QgsVectorLayer(memory_uri, layer_name, "memory")

                crs = QgsCoordinateReferenceSystem("epsg:4326")
                QgsVectorFileWriter.writeAsVectorFormat(layer, self.db_file_path, "utf-8", crs, driverName="SQLite", datasourceOptions=["SPATIALITE=YES","SQLITE_MAX_LENGTH=100000000",])
            
                conn = spatialite_connect(self.db_file_path)
                cur = conn.cursor()

                cur.execute("""PRAGMA foreign_keys = ON;""")
                cur.execute("""INSERT INTO filterMate_db VALUES(1, '{plugin_name}', datetime(), datetime(), '{version}');""".format(
                                                                                                                                plugin_name='FilterMate',
                                                                                                                                version='1.4'
                                                                                                                                )
                )

                cur.execute("""CREATE TABLE fm_projects (
                                project_id VARYING CHARACTER(255) NOT NULL PRIMARY KEY,
                                _created_at DATETIME NOT NULL,
                                _updated_at DATETIME NOT NULL,
                                project_name VARYING CHARACTER(255) NOT NULL,
                                project_path VARYING CHARACTER(255) NOT NULL,
                                project_settings TEXT NOT NULL);
                                """)

                cur.execute("""CREATE TABLE fm_subset_history (
                                id VARYING CHARACTER(255) NOT NULL PRIMARY KEY,
                                _updated_at DATETIME NOT NULL,
                                fk_project VARYING CHARACTER(255) NOT NULL,
                                layer_id VARYING CHARACTER(255) NOT NULL,
                                layer_source_id VARYING CHARACTER(255) NOT NULL,
                                seq_order INTEGER NOT NULL,
                                subset_string TEXT NOT NULL,
                                FOREIGN KEY (fk_project)  
                                REFERENCES fm_projects(project_id));
                                """)
                
                cur.execute("""CREATE TABLE fm_project_layers_properties (
                                id VARYING CHARACTER(255) NOT NULL PRIMARY KEY,
                                _updated_at DATETIME NOT NULL,
                                fk_project VARYING CHARACTER(255) NOT NULL,
                                layer_id VARYING CHARACTER(255) NOT NULL,
                                meta_type VARYING CHARACTER(255) NOT NULL,
                                meta_key VARYING CHARACTER(255) NOT NULL,
                                meta_value TEXT NOT NULL,
                                FOREIGN KEY (fk_project)  
                                REFERENCES fm_projects(project_id),
                                CONSTRAINT property_unicity
                                UNIQUE(fk_project, layer_id, meta_type, meta_key) ON CONFLICT REPLACE);
                                """)
                
                self.project_uuid = uuid.uuid4()
            
                cur.execute("""INSERT INTO fm_projects VALUES('{project_id}', datetime(), datetime(), '{project_name}', '{project_path}', '{project_settings}');""".format(
                                                                                                                                                                    project_id=self.project_uuid,
                                                                                                                                                                    project_name=self.project_file_name,
                                                                                                                                                                    project_path=self.project_file_path,
                                                                                                                                                                    project_settings=project_settings.replace("\'","\'\'")
                                                                                                                                                                    )
                )

                conn.commit()

                QgsExpressionContextUtils.setProjectVariable(self.PROJECT, 'filterMate_db_project_uuid', self.project_uuid)



            else:
                conn = spatialite_connect(self.db_file_path)
                cur = conn.cursor()
                cur.execute("""SELECT * FROM fm_projects WHERE project_name = '{project_name}' AND project_path = '{project_path}' LIMIT 1;""".format(
                                                                                                                                                project_name=self.project_file_name,
                                                                                                                                                project_path=self.project_file_path
                                                                                                                                                )
                )

                results = cur.fetchall()

                if len(results) == 1:
                    result = results[0]
                    project_settings = result[-1]
                    self.project_uuid = result[0].replace("\'\'", "\'")
                    self.CONFIG_DATA["CURRENT_PROJECT"] = json.loads(project_settings)
                    QgsExpressionContextUtils.setProjectVariable(self.PROJECT, 'filterMate_db_project_uuid', self.project_uuid)

                    # cur.execute("""UPDATE fm_projects 
                    #                 SET _updated_at = datetime(),
                    #                     project_settings = '{project_settings}' 
                    #                 WHERE project_id = '{project_id}'""".format(
                    #                                                             project_settings=project_settings,
                    #                                                             project_id=project_id
                    #                                                             )
                    # )

                else:
                    self.project_uuid = uuid.uuid4()
                    cur.execute("""INSERT INTO fm_projects VALUES('{project_id}', datetime(), datetime(), '{project_name}', '{project_path}', '{projects_settings}');""".format(
                                                                                                                                                                        project_id=self.project_uuid,
                                                                                                                                                                        project_name=self.project_file_name,
                                                                                                                                                                        project_path=self.project_file_path,
                                                                                                                                                                        projects_settings=project_settings.replace("\'","\'\'")
                                                                                                                                                                        )
                    )
                    QgsExpressionContextUtils.setProjectVariable(self.PROJECT, 'filterMate_db_project_uuid', self.project_uuid)

                conn.commit()

            cur.close()
            conn.close()

            




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

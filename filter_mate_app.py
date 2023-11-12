from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import QgsCheckableComboBox, QgsFeatureListComboBox, QgsFieldExpressionWidget
from qgis.utils import *
from qgis.utils import iface
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


# Import the code for the DockWidget
from .filter_mate_dockwidget import FilterMateDockWidget

class FilterMateApp:

    PROJECT_LAYERS = {} 


    def __init__(self, plugin_dir):
        self.iface = iface
        self.dockwidget = None
        self.flags = {}
        self.CONFIG_DATA = CONFIG_DATA
        self.plugin_dir = plugin_dir
        self.appTasks = {"filter":None,"unfilter":None,"export":None}
        self.tasks_descriptions = {'filter':'Filtering data',
                                    'unfilter':'Unfiltering data',
                                    'reset':'Reseting data',
                                    'export':'Exporting data'}
        
        self.json_template_layer_infos = '{"layer_geometry_type":"%s","layer_name":"%s","layer_id":"%s","layer_schema":"%s","subset_history":[],"is_already_subset":false,"layer_provider_type":"%s","layer_crs_authid":"%s","primary_key_name":"%s","primary_key_idx":%s,"primary_key_type":"%s","geometry_field":"%s","primary_key_is_numeric":%s,"is_current_layer":false }'
        self.json_template_layer_exploring = '{"is_saving":false,"is_tracking":false,"is_selecting":false,"is_linking":false,"single_selection_expression":"%s","multiple_selection_expression":"%s","custom_selection_expression":"%s" }'
        self.json_template_layer_filtering = '{"has_layers_to_filter":false,"layers_to_filter":[],"has_combine_operator":false,"combine_operator":"","has_geometric_predicates":false,"geometric_predicates":[],"geometric_predicates_operator":"AND","has_buffer":false,"buffer":0.0,"buffer_property":false,"buffer_expression":"" }'
        self.run()


    def run(self):
        if self.dockwidget == None:
            
            

            init_layers = list(PROJECT.mapLayers().values())

            if self.CONFIG_DATA["APP"]["FRESH_RELOAD_FLAG"] is True:
                self.remove_variables_from_all_layers()

            self.manage_project_layers(init_layers, 'add')



            self.dockwidget = FilterMateDockWidget(self.PROJECT_LAYERS, self.plugin_dir, self.CONFIG_DATA)

            # show the dockwidget
            # TODO: fix to allow choice of dock location
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
            self.dockwidget.show()


        """Keep the advanced filter combobox updated on adding or removing layers"""

        PROJECT.layersAdded.connect(lambda layers, x='add': self.manage_project_layers(layers, x))
        PROJECT.layersWillBeRemoved.connect(lambda layers, x='remove': self.manage_project_layers(layers, x))

        
        self.dockwidget.launchingTask.connect(self.manage_task)
        self.dockwidget.reinitializingLayerOnError.connect(self.remove_variables_from_layer_id)
        self.dockwidget.settingLayerVariable.connect(self.save_variables_from_layer_id)



        
        """Overload configuration qtreeview model to keep configuration file up to date"""
        # 
        # self.managerWidgets.model.rowsInserted.connect(self.qtree_signal)
        # self.managerWidgets.model.rowsRemoved.connect(self.qtree_signal)

    def can_cast(self, dest_type, source_value):
        try:
            dest_type(source_value)
            return True
        except:
            return False



    def return_typped_value(self, value_as_string):
        value_typped= None

        if value_as_string == None or value_as_string == '':   
            value_typped = str('')
        elif str(value_as_string).find('{') == 0 and self.can_cast(dict, value_as_string) is True:
            value_typped = dict(value_as_string)
        elif str(value_as_string).find('[') == 0 and self.can_cast(list, value_as_string) is True:
            value_typped = list(value_as_string)
        elif self.can_cast(bool, value_as_string) is True and str(value_as_string).upper() in ('FALSE','TRUE'):
            value_typped = bool(value_as_string)
        elif self.can_cast(float, value_as_string) is True and len(str(value_as_string).split('.')) > 1:
            value_typped = float(value_as_string)
        elif self.can_cast(int, value_as_string) is True:
            value_typped = int(value_as_string)
        else:
            value_typped = str(value_as_string)

        return value_typped



    def save_variables_from_layer_id(self, layer_id, custom_variable=None):

        if self.dockwidget != None:    
            self.PROJECT_LAYERS = self.dockwidget.PROJECT_LAYERS

        if layer_id in self.PROJECT_LAYERS.keys():
            layers = [layer for layer in PROJECT.mapLayersByName(self.PROJECT_LAYERS[layer_id]["infos"]["layer_name"]) if layer.id() == layer_id]
            
            if len(layers) > 0:
                layer = layers[0]
                 

                if custom_variable == None or (isinstance(custom_variable, tuple) and len(custom_variable) == 0):
                    for key_group in ("infos", "exploring", "filtering"):
                        for key, value in self.PROJECT_LAYERS[layer_id][key_group].items():
                            variable_key = "filterMate_{key_group}_{key}".format(key_group=key_group, key=key)
                            QgsExpressionContextUtils.setLayerVariable(layer, variable_key, str(value))
                            #layer_scope.setVariable(variable_key, value, True)
                
                elif isinstance(custom_variable, tuple) and len(custom_variable) == 2:
                    if custom_variable[0] in ("infos", "exploring", "filtering"):
                        if custom_variable[0] in self.PROJECT_LAYERS[layer_id] and custom_variable[1] in self.PROJECT_LAYERS[layer_id][custom_variable[0]]:
                            variable_key = "filterMate_{key_group}_{key}".format(key_group=custom_variable[0], key=custom_variable[1])
                            value = self.PROJECT_LAYERS[layer_id][custom_variable[0]][custom_variable[1]]
                            QgsExpressionContextUtils.setLayerVariable(layer, variable_key, str(value))
                            #layer_scope.setVariable(variable_key, value, True)


    def save_style_from_layer_id(self, layer_id):

        if self.dockwidget != None:    
            self.PROJECT_LAYERS = self.dockwidget.PROJECT_LAYERS

        if layer_id in self.PROJECT_LAYERS.keys():
            if self.PROJECT_LAYERS[layer_id]["exploring"]["is_saving"] is True:
                layers = [layer for layer in PROJECT.mapLayersByName(self.PROJECT_LAYERS[layer_id]["infos"]["layer_name"]) if layer.id() == layer_id]
                print("save_projectCustomProperties_from_layer_id", layers)
                if len(layers) > 0:
                    layer = layers[0]

                    try:
                        layer.deleteStyleFromDatabase(name="FilterMate_style_{}".format(layer.name()))
                        result = layer.saveStyleToDatabase(name="FilterMate_style_{}".format(layer.name()),description="FilterMate style for {}".format(layer.name()), useAsDefault=True, uiFileContent="") 
                        print("save_projectCustomProperties_from_layer_id", result)
                    except:
                        layer_path = layer.source().split('|')[0]
                        layer.saveNamedStyle(os.path.normcase(os.path.join(os.path.split(layer_path)[0], 'FilterMate_style_{}.qml'.format(layer.name()))))



    def remove_variables_from_layer_id(self, layer_id, action='reset'):

        if self.dockwidget != None:    
            self.PROJECT_LAYERS = self.dockwidget.PROJECT_LAYERS

        if layer_id in self.PROJECT_LAYERS:
            layers = [layer for layer in PROJECT.mapLayersByName(self.PROJECT_LAYERS[layer_id]["infos"]["layer_name"]) if layer.id() == layer_id]
            if len(layers) > 0:
                layer = layers[0]
                layer_scope = QgsExpressionContextUtils.layerScope(layer)    

                for key_group in ("infos", "exploring", "filtering"):
                    for key in self.PROJECT_LAYERS[layer_id][key_group]:
                        variable_key = "filterMate_{key_group}_{key}".format(key_group=key_group, key=key)
                        layer_scope.removeVariable(variable_key)
                QgsExpressionContextUtils.setLayerVariables(layer, {})
                if action == 'reset':
                    self.add_project_layer(layer)


        if self.dockwidget != None and action == 'reset':
            self.dockwidget.get_project_layers_from_app(self.PROJECT_LAYERS)
                    

    def remove_variables_from_all_layers(self):
        init_layers = list(PROJECT.mapLayers().values())
    
        for layer in init_layers:
            try:
                QgsExpressionContextUtils.setLayerVariables(layer, {})
            except:
                pass


    def manage_project_layers(self, layers, action):

        if self.dockwidget != None:

            self.PROJECT_LAYERS = self.dockwidget.PROJECT_LAYERS

            widgets_to_stop =   [
                                    ["QGIS","LAYER_TREE_VIEW"],
                                    ["SINGLE_SELECTION","FEATURES"],
                                    ["SINGLE_SELECTION","EXPRESSION"],
                                    ["MULTIPLE_SELECTION","FEATURES"],
                                    ["MULTIPLE_SELECTION","EXPRESSION"],
                                    ["CUSTOM_SELECTION","EXPRESSION"],
                                    ["FILTERING","CURRENT_LAYER"],
                                    ["FILTERING","LAYERS_TO_FILTER"],
                                    ["FILTERING","COMBINE_OPERATOR"],
                                    ["FILTERING","GEOMETRIC_PREDICATES"],
                                    ["FILTERING","GEOMETRIC_PREDICATES_OPERATOR"],
                                    ["FILTERING","BUFFER"],
                                    ["FILTERING","BUFFER_PROPERTY"],
                                    ["FILTERING","BUFFER_EXPRESSION"]
                                ]
        
            for widget_path in widgets_to_stop:
                self.dockwidget.manageSignal(widget_path, 'disconnect')


        for layer in layers:
            if action == 'add':     
                self.add_project_layer(layer)
            elif action == 'remove':
                self.remove_project_layer(layer)

        self.PROJECT_LAYERS = dict(OrderedDict(sorted(self.PROJECT_LAYERS.items(), key = lambda layer: (getitem(layer[1]['infos'], 'layer_geometry_type'), getitem(layer[1]['infos'], 'layer_name')))))

        if self.dockwidget != None:
            for widget_path in widgets_to_stop:
                self.dockwidget.manageSignal(widget_path, 'connect')

            self.dockwidget.get_project_layers_from_app(self.PROJECT_LAYERS)
            
            # self.dockwidget.CONFIG_DATA["LAYERS"] = self.PROJECT_LAYERS
            # self.dockwidget.reload_configuration_model()


    def check_dict_structure(self, input, reference):
        
        if isinstance(reference, dict):
            for key in reference:
                if isinstance(input, dict) is False:
                    input = {}
                if key not in input:
                    if isinstance(reference[key], dict):
                        input[key] = self.check_dict_structure(input[key], reference[key])
                    else:
                        input[key] = reference[key]
        else:
            input = reference
        
        return input

    



    def add_project_layer(self, layer):


        if layer.id() not in self.PROJECT_LAYERS.keys():

            if isinstance(layer, QgsVectorLayer) and layer.isSpatial():

                primary_key_name, primary_key_idx, primary_key_type, primary_key_is_numeric = self.search_primary_key_from_layer(layer)
                source_schema = 'NULL'
                geometry_field = 'NULL'
                init = True
                new_layer_variables = {}
                existing_layer_variables = {}
                layer_variables = {}

                if layer.providerType() == 'ogr':

                    capabilities = layer.capabilitiesString().split(', ')
                    if 'Transactions' in capabilities:
                        layer_provider_type = 'spatialite'
                    else:
                        layer_provider_type = 'ogr'

                elif layer.providerType() == 'postgres':
                    layer_provider_type = 'postgresql'
                    
                    layer_source = layer.source()
                    regexp_match_source_schema = re.search('(?<=table=\\")[a-zA-Z0-9_-]*(?=\\".)',layer_source)
                    if regexp_match_source_schema != None:
                        source_schema = regexp_match_source_schema.group()

                    regexp_match_geometry_field = re.search('(?<=\\()[a-zA-Z0-9_-]*(?=\\))',layer_source)
                    if regexp_match_geometry_field != None:
                        geometry_field = regexp_match_geometry_field.group()

      

                else:
                    capabilities = layer.capabilitiesString().split(', ')
                    if 'Transactions' in capabilities:
                        layer_provider_type = 'spatialite'
                    else:
                        layer_provider_type = 'ogr'

                layer_geometry_type = layer.geometryType()
                if layer_provider_type == 'spatialite':
                    geometry_field = 'GEOMETRY'
                elif layer_provider_type == 'ogr':
                    geometry_field = '_ogr_geometry_'

                new_layer_variables["infos"] = json.loads(self.json_template_layer_infos % (layer_geometry_type, layer.name(), layer.id(), source_schema, layer_provider_type, layer.sourceCrs().authid(), primary_key_name, primary_key_idx, primary_key_type, geometry_field, str(primary_key_is_numeric).lower()))
                new_layer_variables["exploring"] = json.loads(self.json_template_layer_exploring % (str(primary_key_name),str(primary_key_name),str(primary_key_name)))
                new_layer_variables["filtering"] = json.loads(self.json_template_layer_filtering)
        
                layer_scope = QgsExpressionContextUtils.layerScope(layer)

                for key_group in ("infos", "exploring", "filtering"):
                    existing_layer_variables[key_group] = {}
                    for key in new_layer_variables[key_group]:
                        variable_key = "filterMate_{key_group}_{key}".format(key_group=key_group, key=key)

                        if layer_scope.hasVariable(variable_key) is True:
                            value = layer_scope.variable(variable_key)
                            typped_value = self.return_typped_value(value)
                            existing_layer_variables[key_group][key] = typped_value
                        else:
                            if key in new_layer_variables[key_group]:
                                value = new_layer_variables[key_group][key]
                                existing_layer_variables[key_group][key] = value
                
                layer_variables["infos"] = existing_layer_variables["infos"]
                layer_variables["exploring"] = existing_layer_variables["exploring"]
                layer_variables["filtering"] = existing_layer_variables["filtering"]    

                if (layer_provider_type != layer_variables["infos"]["layer_provider_type"]) or (layer.name() != layer_variables["infos"]["layer_name"]) or (source_schema != layer_variables["infos"]["layer_schema"]) or (primary_key_name != layer_variables["infos"]["primary_key_name"]):
                    layer_variables["infos"] = new_layer_variables["infos"]

                self.PROJECT_LAYERS[str(layer.id())] = {"infos": layer_variables["infos"], "exploring": layer_variables["exploring"], "filtering": layer_variables["filtering"]}
                self.PROJECT_LAYERS[str(layer.id())]["infos"]["layer_id"] = layer.id()

                if layer_provider_type == 'postgresql':
                    self.create_spatial_index_for_postgresql_layer(layer)
                else:
                    self.create_spatial_index_for_layer(layer)

                self.save_variables_from_layer_id(layer.id())

    def remove_project_layer(self, layer_to_remove_id):

        if isinstance(layer_to_remove_id, str):

            self.save_variables_from_layer_id(layer_to_remove_id)    
            self.save_style_from_layer_id(layer_to_remove_id)

            if layer_to_remove_id in self.PROJECT_LAYERS:
                self.dockwidget.widgets["MULTIPLE_SELECTION"]["FEATURES"]["WIDGET"].remove_list_widget(layer_to_remove_id)
                del self.PROJECT_LAYERS[layer_to_remove_id]

        

    def search_primary_key_from_layer(self, layer):
        """For each layer we search the primary key"""

        primary_key_index = layer.primaryKeyAttributes()
        if len(primary_key_index) > 0:
            for field_id in primary_key_index:
                if len(layer.uniqueValues(field_id)) == layer.featureCount():
                    field = layer.fields()[field_id]
                    return field.name(), field_id, field.typeName(), field.isNumeric()
        else:
            for field in layer.fields():
                if 'ID' in str(field.name()).upper():
                    if len(layer.uniqueValues(layer.fields().indexOf(field.name()))) == layer.featureCount():
                        return field.name(), layer.fields().indexFromName(field.name()), field.typeName(), field.isNumeric()
                    
            for field in layer.fields():
                if len(layer.uniqueValues(layer.fields().indexOf(field.name()))) == layer.featureCount():
                    return field.name(), layer.fields().indexFromName(field.name()), field.typeName(), field.isNumeric()
                
        new_field = QgsField('ID', QVariant.LongLong)
        layer.addExpressionField('@row_number', new_field)

        return 'ID', layer.fields().indexFromName('ID'), new_field.typeName(), True


    def create_spatial_index_for_postgresql_layer(self, layer):       

        layer_props = self.PROJECT_LAYERS[layer.id()]
        schema = layer_props["infos"]["layer_schema"]
        table = layer_props["infos"]["layer_name"]
        geometry_field = layer_props["infos"]["geometry_field"]
        primary_key_name = layer_props["infos"]["primary_key_name"]

        layer_source_uri = QgsDataSourceUri(layer.source())


        md = QgsProviderRegistry.instance().providerMetadata('postgres')
        database = md.createConnection('LOCAL')
        postgresql_named_connection = self.CONFIG_DATA["APP"]["POSTGRESQL_CONNECTION_NAME"]

        sql_statement = 'CREATE INDEX IF NOT EXISTS {schema}_{table}_{geometry_field}_idx ON "{schema}"."{table}" USING GIST ({geometry_field});\r\n'.format(schema=schema,
                                                                                                                                                        table=table,
                                                                                                                                                        geometry_field=geometry_field)
        sql_statement = sql_statement + 'CREATE UNIQUE INDEX IF NOT EXISTS {schema}_{table}_{primary_key_name}_idx ON "{schema}"."{table}" ({primary_key_name});'.format(schema=schema,
                                                                                                                                                                            table=table,
                                                                                                                                                                            primary_key_name=primary_key_name)

        alg_params_postgisexecutesql = {
            "DATABASE": postgresql_named_connection,
            "SQL": sql_statement
        }
        processing.run('qgis:postgisexecutesql', alg_params_postgisexecutesql)



    def create_spatial_index_for_layer(self, layer):    

        alg_params_createspatialindex = {
            "INPUT": layer
        }
        output = processing.run('qgis:createspatialindex', alg_params_createspatialindex)


    def manage_task(self, task_name):
        """Manage the different tasks"""

        assert task_name in list(self.tasks_descriptions.keys())

        if self.dockwidget.current_layer == None:
            return
        
        task_parameters, current_layer = self.get_task_parameters(task_name)

        if task_name == 'filter':
            if len(task_parameters["task"]['features']) == 0 or task_parameters["task"]['expression'] == None:
                return

        self.appTasks[task_name] = FilterEngineTask(self.tasks_descriptions[task_name], task_name, task_parameters)

        self.appTasks[task_name].taskCompleted.connect(partial(self.task_postprocessing, task_name, current_layer, task_parameters))

        QgsApplication.taskManager().addTask(self.appTasks[task_name])


    def get_task_parameters(self, task_name):

        self.PROJECT_LAYERS = self.dockwidget.PROJECT_LAYERS
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
            return task_parameters, current_layer

        elif task_name == 'unfilter':

            task_parameters["task"] = {"features": features, "expression": expression, "filtering": self.dockwidget.project_props["filtering"]}
            return task_parameters, current_layer
        
        elif task_name == 'reset':

            task_parameters["task"] = {"features": features, "expression": expression}
            return task_parameters, current_layer

        elif task_name == 'export':
            
            task_parameters["task"] = self.dockwidget.project_props
            return task_parameters, current_layer




    def task_postprocessing(self, task_name, current_layer, task_parameters):
         
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

        if task_parameters["filtering"]["has_layers_to_filter"] == True:
            for layer_props in task_parameters["filtering"]["layers_to_filter"]:
                if layer_props["layer_id"] in self.PROJECT_LAYERS:
                    layers = [layer for layer in PROJECT.mapLayersByName(layer_props["layer_name"]) if layer.id() == layer_props["layer_id"]]
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

           
        self.iface.mapCanvas().refreshAllLayers()
        self.iface.mapCanvas().refresh()
         
        self.dockwidget.get_project_layers_from_app(self.PROJECT_LAYERS)

        if task_name == 'filter' or task_name == 'unfilter':
            self.dockwidget.exploring_zoom_clicked()



class FilterEngineTask(QgsTask):
    """Main QgsTask class which filter and unfilter data"""

    def __init__(self, description, task_action, task_parameters):

        QgsTask.__init__(self, description, QgsTask.CanCancel)


        self.exception = None
        self.task_action = task_action
        self.task_parameters = task_parameters
        self.layers_count = None

        self.expression = None
        self.is_field_expression = None

        self.has_feature_count_limit = True
        self.feature_count_limit = None
        self.param_source_provider_type = None
        self.has_combine_operator = None
        self.param_combine_operator = None
        self.param_buffer_expression = None
        self.param_buffer_value = None
        self.param_source_schema = None
        self.param_source_table = None
        self.param_source_geom = None
        self.param_source_geom_operator = None
        self.param_source_subset = None

        self.has_to_reproject_source_layer = False
        self.source_crs = None
        self.source_layer_crs_authid = None

        self.postgresql_source_geom = None
        self.spatialite_source_geom = None
        self.ogr_source_geom = None

        self.current_predicates = {}
        self.outputs = {}
        self.message = None
        self.predicates = {"Intersect":"ST_Intersects","Contain":"ST_Contains","Disjoint":"ST_Disjoint","Equal":"ST_Equals","Touch":"ST_Touches","Overlap":"ST_Overlaps","Are within":"ST_Within","Cross":"ST_Crosses"}

    def run(self):
        """Main function that run the right method from init parameters"""

        try:
            self.layers_count = 1    
            layers = [layer for layer in PROJECT.mapLayersByName(self.task_parameters["infos"]["layer_name"]) if layer.id() == self.task_parameters["infos"]["layer_id"]]
            if len(layers) > 0:
                self.source_layer = layers[0]
                self.source_crs = self.source_layer.sourceCrs()
                source_crs_distance_unit = self.source_crs.mapUnits()
                self.source_layer_crs_authid = self.task_parameters["infos"]["layer_crs_authid"]
                
                if source_crs_distance_unit in ['DistanceUnit.Degrees','DistanceUnit.Unknown'] or self.source_crs.isGeographic() is True:
                    self.has_to_reproject_source_layer = True
                    self.source_layer_crs_authid = "EPSG:3857"



                if "filtering" in self.task_parameters["task"] and "feature_count_limit" in self.task_parameters["task"]["filtering"]:
                    if isinstance(self.task_parameters["task"]["filtering"]["feature_count_limit"], int) and self.task_parameters["task"]["filtering"]["feature_count_limit"] > 0:
                        self.feature_count_limit = self.task_parameters["task"]["filtering"]["feature_count_limit"]

            """We split the selected layers to be filtered in two categories sql and others"""
            self.layers = {}

            if self.task_parameters["filtering"]["has_layers_to_filter"] == True:
                for layer_props in self.task_parameters["filtering"]["layers_to_filter"]:
                    if layer_props["layer_provider_type"] not in self.layers:
                        self.layers[layer_props["layer_provider_type"]] = []

                    layers = [layer for layer in PROJECT.mapLayersByName(layer_props["layer_name"]) if layer.id() == layer_props["layer_id"]]
                    if len(layers) > 0:
                        self.layers[layer_props["layer_provider_type"]].append([layers[0], layer_props])
                        self.layers_count += 1
    
                self.provider_list = list(self.layers)
        

            if self.task_action == 'filter':
                """We will filter layers"""

                self.execute_filtering()
                    

            elif self.task_action == 'unfilter':
                """We will unfilter the layers"""

                self.execute_unfiltering()

            elif self.task_action == 'reset':
                """We will reset the layers"""

                self.execute_reseting()

            elif self.task_action == 'export':
                """We will export layers"""
                if self.task_parameters["task"]["exporting"]["has_layers_to_export"] == True:
                    self.execute_exporting()
                else:
                    return False
                
            return True
    
        except Exception as e:
            self.exception = e
            print(self.exception)
            return False



    def prepare_postgresql_source_geom(self):

        self.postgresql_source_geom = '"{source_table}"."{source_geom}"'.format(source_table=self.param_source_table,
                                                                                source_geom=self.param_source_geom)

        if self.has_to_reproject_source_layer is True:
            self.postgresql_source_geom = 'ST_Transform({postgresql_source_geom}, {source_layer_srid})'.format(postgresql_source_geom=self.postgresql_source_geom,
                                                                                                                source_layer_srid=self.source_layer_crs_authid.split(':')[1])
            

        if self.param_buffer_value != None:
            self.postgresql_source_geom = 'ST_Buffer({postgresql_source_geom}, {buffer_value})'.format(postgresql_source_geom=self.postgresql_source_geom,
                                                                                                        buffer_value=self.param_buffer_value)

        print("prepare_postgresql_source_geom", self.postgresql_source_geom)     

    def prepare_spatialite_source_geom(self):

        raw_geometries = [feature.geometry() for feature in self.task_parameters["task"]["features"] if feature.hasGeometry()]
        geometries = []

        if self.has_to_reproject_source_layer is True:
            transform = QgsCoordinateTransform(QgsCoordinateReferenceSystem(self.source_crs.authid()), QgsCoordinateReferenceSystem( self.source_layer_crs_authid), PROJECT)

        for geometry in raw_geometries:
            if geometry.isEmpty() is False:
                if geometry.isMultipart():
                    geometry.convertToSingleType()
                if self.has_to_reproject_source_layer is True:
                    geometry.transform(transform)
                if self.param_buffer_value != None:
                    geometry = geometry.buffer(self.param_buffer_value, 5)
                geometries.append(geometry)

        collected_geometry = QgsGeometry().collectGeometry(geometries)
        self.spatialite_source_geom = collected_geometry.asWkt().strip()

        print("prepare_spatialite_source_geom", self.spatialite_source_geom) 


    def prepare_ogr_source_geom(self):

        layer = self.source_layer

        if self.has_to_reproject_source_layer is True:
        
            alg_source_layer_params_reprojectlayer = {
                'INPUT': layer,
                'TARGET_CRS': self.source_layer_crs_authid,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            self.outputs['alg_source_layer_params_reprojectlayer'] = processing.run('qgis:reprojectlayer', alg_source_layer_params_reprojectlayer)
            layer = self.outputs['alg_source_layer_params_reprojectlayer']['OUTPUT']

            alg_params_createspatialindex = {
                "INPUT": layer
            }
            processing.run('qgis:createspatialindex', alg_params_createspatialindex)


        if self.param_buffer_value != None:

            alg_source_layer_params_buffer = {
                'DISSOLVE': False,
                'DISTANCE': QgsProperty.fromExpression(self.param_buffer_expression) if self.param_buffer_expression != '' else float(self.param_buffer_value),
                'END_CAP_STYLE': 0,
                'INPUT': layer,
                'JOIN_STYLE': 0,
                'MITER_LIMIT': 2,
                'SEGMENTS': 5,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }

            self.outputs['alg_source_layer_params_buffer'] = processing.run('qgis:buffer', alg_source_layer_params_buffer)
            layer = self.outputs['alg_source_layer_params_buffer']['OUTPUT']   

            alg_params_createspatialindex = {
                "INPUT": layer
            }
            processing.run('qgis:createspatialindex', alg_params_createspatialindex)


        self.ogr_source_geom = layer

        print("prepare_ogr_source_geom", self.ogr_source_geom) 


    def execute_geometric_filtering(self, layer_provider_type, layer, layer_props):

        result = False
        postgis_predicates = list(self.current_predicates.values())

        param_old_subset = ''
        if self.param_combine_operator != '':
            if layer_props["is_already_subset"] == True:
                param_old_subset = layer.subsetString()

        param_distant_schema = layer_props["layer_schema"]
        param_distant_table = layer_props["layer_name"]
        param_distant_primary_key_name = layer_props["primary_key_name"]
        param_distant_primary_key_is_numeric = layer_props["primary_key_is_numeric"]
        param_distant_geometry_field = layer_props["geometry_field"]
        param_layer_crs_authid = layer_props["layer_crs_authid"]
        
        param_layer_feature_count = 0
        param_has_to_reproject_layer = False
        param_layer_crs = layer.sourceCrs()
        param_layer_crs_distance_unit = param_layer_crs.mapUnits()
        if param_layer_crs_distance_unit not in ['DistanceUnit.Degrees','DistanceUnit.Unknown'] and param_layer_crs.isGeographic() is False:

            if param_layer_crs_authid != self.source_layer_crs_authid:
                param_has_to_reproject_layer = True
                param_layer_crs_authid = self.source_layer_crs_authid

        else:
            param_has_to_reproject_layer = True
            param_layer_crs_authid = self.source_layer_crs_authid



        if self.param_source_provider_type == 'postgresql' and layer_provider_type == 'postgresql' and self.has_combine_operator is False and self.param_buffer_expression == None:

            postgis_sub_expression_array = []
            for postgis_predicate in postgis_predicates:
                
                param_distant_geom_expression = '"{distant_table}"."{distant_geometry_field}"'.format(distant_table=param_distant_table,
                                                                                                        distant_geometry_field=param_distant_geometry_field)
                if param_has_to_reproject_layer:

                    param_distant_geom_expression = 'ST_Transform({param_distant_geom_expression}, {param_layer_srid})'.format(param_distant_geom_expression=param_distant_geom_expression,
                                                                                                                              param_layer_srid=param_layer_crs_authid.split(':')[1])
                    
                    

                postgis_sub_expression_array.append(postgis_predicate + '({source_sub_expression_geom},{param_distant_geom_expression})'.format(source_sub_expression_geom=self.postgresql_source_geom,
                                                                                                                                                    param_distant_geom_expression=param_distant_geom_expression)
                                                                                                                                                    )
            
            if len(postgis_sub_expression_array) > 1:
                param_postgis_sub_expression = self.param_source_geom_operator.join(postgis_sub_expression_array)
            else:
                param_postgis_sub_expression = postgis_sub_expression_array[0]

            param_expression = '"{distant_primary_key_name}" IN (SELECT "{distant_table}"."{distant_primary_key_name}" FROM "{distant_schema}"."{distant_table}" LEFT JOIN "{source_schema}"."{source_table}" ON {postgis_sub_expression} WHERE {source_subset})'.format(distant_primary_key_name=param_distant_primary_key_name,
                                                                                                                                                                                                                                                                            distant_schema=param_distant_schema,    
                                                                                                                                                                                                                                                                            distant_table=param_distant_table,
                                                                                                                                                                                                                                                                            source_schema=self.param_source_schema,    
                                                                                                                                                                                                                                                                            source_table=self.param_source_table,
                                                                                                                                                                                                                                                                            postgis_sub_expression=param_postgis_sub_expression,
                                                                                                                                                                                                                                                                            source_subset=self.expression)

            
            result = layer.setSubsetString(param_expression)

            if result is False:
                print(param_expression)

            param_layer_feature_count = layer.featureCount()

            if param_has_to_reproject_layer or (self.has_feature_count_limit is True and param_layer_feature_count > self.feature_count_limit):

                features_ids = []
                for feature in layer.getFeatures():
                    features_ids.append(str(feature[param_distant_primary_key_name]))

                if len(features_ids) > 0:
                    if param_distant_primary_key_is_numeric == True:
                        param_expression = '"{distant_primary_key_name}" IN '.format(distant_primary_key_name=param_distant_primary_key_name) + "(" + ", ".join(features_ids) + ")"
                    else:
                        param_expression = '"{distant_primary_key_name}" IN '.format(distant_primary_key_name=param_distant_primary_key_name) + "(\'" + "\', \'".join(features_ids) + "\')"

                    if QgsExpression(param_expression).isValid():

                        result = layer.setSubsetString(param_expression)
    
                        if result is False:
                            print(param_expression)

        if result is False:

            current_layer = layer

            if param_has_to_reproject_layer:

                alg_layer_params_reprojectlayer = {
                    'INPUT': current_layer,
                    'TARGET_CRS': param_layer_crs_authid,
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                }
                self.outputs['alg_layer_params_reprojectlayer'] = processing.run('qgis:reprojectlayer', alg_layer_params_reprojectlayer)
                current_layer = self.outputs['alg_layer_params_reprojectlayer']['OUTPUT']

                alg_params_createspatialindex = {
                    "INPUT": current_layer
                }
                processing.run('qgis:createspatialindex', alg_params_createspatialindex)


            features_list = []
            alg_params_select = {
                'INPUT': current_layer,
                'INTERSECT': self.ogr_source_geom,
                'METHOD': 0,
                'PREDICATE': [int(predicate) for predicate in self.current_predicates.keys()]
            }
            processing.run("qgis:selectbylocation", alg_params_select)

            features_ids = []
            for feature in current_layer.selectedFeatures():
                features_ids.append(str(feature[param_distant_primary_key_name]))



            current_layer.removeSelection()
            layer.removeSelection()


            if len(features_ids) > 0:
                if param_distant_primary_key_is_numeric == True:
                    param_expression = '"{distant_primary_key_name}" IN '.format(distant_primary_key_name=param_distant_primary_key_name) + "(" + ", ".join(features_ids) + ")"
                else:
                    param_expression = '"{distant_primary_key_name}" IN '.format(distant_primary_key_name=param_distant_primary_key_name) + "(\'" + "\', \'".join(features_ids) + "\')"
                


                if QgsExpression(param_expression).isValid():

                    result = layer.setSubsetString(param_expression)
    
                    if result is False:
                        print(param_expression)
                        
        return result
    
    def manage_distant_layers_geometric_filtering(self):
        """Filter layers from a prefiltered layer"""

        result = False
        self.param_source_geom = self.task_parameters["infos"]["geometry_field"]
        self.param_source_geom_operator = ' ' + self.task_parameters["filtering"]["geometric_predicates_operator"] + ' '
        self.param_source_subset = self.expression



        if self.task_parameters["filtering"]["has_buffer"] is True:
            if self.task_parameters["filtering"]["buffer_property"] is True:
                if self.task_parameters["filtering"]["buffer_expression"] != '':
                    self.param_buffer_expression = self.task_parameters["filtering"]["buffer_expression"]
                else:
                    self.param_buffer_value = self.task_parameters["filtering"]["buffer"]
            else:
                self.param_buffer_value = self.task_parameters["filtering"]["buffer"]  

        
        provider_list = self.provider_list + [self.param_source_provider_type]
        provider_list = list(dict.fromkeys(provider_list))

        print(provider_list)

        if 'postgresql' in provider_list and self.param_buffer_expression == None:
            self.prepare_postgresql_source_geom()

        if 'spatialite' in provider_list:
            self.prepare_ogr_source_geom()

        if 'ogr' in provider_list or self.param_buffer_expression != None:
            self.prepare_ogr_source_geom()

        i = 1
        for layer_provider_type in self.layers:
            for layer, layer_props in self.layers[layer_provider_type]:
                result = self.execute_geometric_filtering(layer_provider_type, layer, layer_props)
                if result == True:
                    print(layer.name(), 'has been filtered')
                else:
                    print(layer.name(), 'errors occured')
                i += 1
                self.setProgress((i/self.layers_count)*100)

                
        return True

    def execute_source_layer_filtering(self):
        """Manage the creation of the origin filtering expression"""
        result = False
        param_old_subset = ''

        self.param_source_provider_type = self.task_parameters["infos"]["layer_provider_type"]
        self.param_source_schema = self.task_parameters["infos"]["layer_schema"]
        self.param_source_table = self.task_parameters["infos"]["layer_name"]
        self.primary_key_name = self.task_parameters["infos"]["primary_key_name"]
        self.has_combine_operator = self.task_parameters["filtering"]["has_combine_operator"]
        self.source_layer_fields_names = [field.name() for field in self.source_layer.fields() if field.name() != self.primary_key_name]

        if self.has_combine_operator == True:
            if self.task_parameters["filtering"]["combine_operator"] != '':
                self.param_combine_operator = self.task_parameters["filtering"]["combine_operator"]
                if self.task_parameters["infos"]["is_already_subset"] == True:
                    param_old_subset = self.source_layer.subsetString()

        if self.task_parameters["task"]["expression"] != None:
            self.expression = " " + self.task_parameters["task"]["expression"]
            if QgsExpression(self.expression).isValid() is True:
                
                is_field_expression =  QgsExpression().isFieldEqualityExpression(self.task_parameters["task"]["expression"])

                if is_field_expression[0] == True:
                    self.is_field_expression = is_field_expression

                if QgsExpression(self.expression).isField() is False:
                    
                    fields_similar_to_primary_key_name = [x for x in self.source_layer_fields_names if self.primary_key_name.find(x) > -1]
                    fields_similar_to_primary_key_name_in_expression = [x for x in fields_similar_to_primary_key_name if self.expression.find(x) > -1]
                    existing_fields = [x for x in self.source_layer_fields_names if self.expression.find(x) > -1]
                    if self.expression.find(self.primary_key_name) > -1:
                        if self.expression.find(self.param_source_table) < 0:
                            if self.expression.find(' "' + self.primary_key_name + '" ') > -1:
                                if self.param_source_provider_type == 'postgresql':
                                    self.expression = self.expression.replace('"' + self.primary_key_name + '"', '"{source_table}"."{field_name}"'.format(source_table=self.param_source_table, field_name=self.primary_key_name))
                            elif self.expression.find(" " + self.primary_key_name + " ") > -1:
                                if self.param_source_provider_type == 'postgresql':
                                    self.expression = self.expression.replace(self.primary_key_name, '"{source_table}"."{field_name}"'.format(source_table=self.param_source_table, field_name=self.primary_key_name))
                                else:
                                    self.expression = self.expression.replace(self.primary_key_name,  '"{field_name}"'.format(field_name=self.primary_key_name))
                    elif len(existing_fields) >= 1:
                        if self.expression.find(self.param_source_table) < 0:
                            for field_name in existing_fields:
                                if self.expression.find(' "' + field_name + '" ') > -1:
                                    if self.param_source_provider_type == 'postgresql':
                                        self.expression = self.expression.replace('"' + field_name + '"', '"{source_table}"."{field_name}"'.format(source_table=self.param_source_table, field_name=field_name))
                                elif self.expression.find(" " + field_name + " ") > -1:
                                    if self.param_source_provider_type == 'postgresql':
                                        self.expression = self.expression.replace(field_name, '"{source_table}"."{field_name}"'.format(source_table=self.param_source_table, field_name=field_name))
                                    else:
                                        self.expression = self.expression.replace(self.primary_key_name,  '"{field_name}"'.format(field_name=field_name))    



                    result = self.source_layer.setSubsetString(self.expression)

        if result is False:
            self.is_field_expression = None    
            features_list = self.task_parameters["task"]["features"]

            features_ids = [str(feature[self.primary_key_name]) for feature in features_list]

            if len(features_ids) > 0:
                if self.task_parameters["infos"]["primary_key_is_numeric"] is True:
                    self.expression = '"{source_table}"."{primary_key_name}" IN '.format(source_table=self.param_source_table, primary_key_name=self.primary_key_name) + "(" + ", ".join(features_ids) + ")"
                else:
                    self.expression = '"{source_table}"."{primary_key_name}" IN '.format(source_table=self.param_source_table, primary_key_name=self.primary_key_name) + "(\'" + "\', \'".join(features_ids) + "\')"
                
                result = self.source_layer.setSubsetString(self.expression)
 
        return result
    

      
    def execute_filtering(self):
        """Manage the advanced filtering"""

       
        result = self.execute_source_layer_filtering()

        
        if result is True:
            result = self.setProgress((1/self.layers_count)*100)

        

        if self.task_parameters["filtering"]["has_geometric_predicates"] == True:

            if len(self.task_parameters["filtering"]["geometric_predicates"]) > 0:
                
                source_predicates = self.task_parameters["filtering"]["geometric_predicates"]
                
                for key in source_predicates:
                    index = None
                    if key in self.predicates:
                        index = list(self.predicates).index(key)
                        if index >= 0:
                            self.current_predicates[str(index)] = self.predicates[key]

                self.geometric_predicates_operator = self.task_parameters["filtering"]["geometric_predicates_operator"]
                self.manage_distant_layers_geometric_filtering()

        elif self.is_field_expression != None:
            field_idx = -1
            for layer_provider_type in self.layers:
                for layer, layer_prop in self.layers[layer_provider_type]:
                    field_idx = layer.fields().indexOf(self.is_field_expression[1])
                    if field_idx >= 0:
                        param_old_subset = ''
                        if self.param_combine_operator != '':
                            if layer_prop["is_already_subset"] == True:
                                param_old_subset = layer.subsetString()

                        if param_old_subset != '' and self.param_combine_operator != '':

                            result = self.source_layer.setSubsetString('( {old_subset} ) {combine_operator} {expression}'.format(old_subset=param_old_subset,
                                                                                                                                combine_operator=self.param_combine_operator,
                                                                                                                                expression=self.expression))
                        else:
                            result = self.source_layer.setSubsetString(self.expression)

        return result  


    def execute_unfiltering(self):

        print(self.task_parameters)
        i = 1
        if len(self.task_parameters["infos"]["subset_history"]) > 1:
            self.source_layer.setSubsetString(self.task_parameters["infos"]["subset_history"][-2]["subset_string"])
        else:
            self.source_layer.setSubsetString('')
        self.setProgress((i/self.layers_count)*100)

        
        for layer_provider_type in self.layers:
            for layer, layer_props in self.layers[layer_provider_type]:
                if len(layer_props["subset_history"]) > 1:
                    layer.setSubsetString(layer_props["subset_history"][-2]["subset_string"])
                else:
                    layer.setSubsetString('')
                i += 1
                self.setProgress((i/self.layers_count)*100)


        return True


    def execute_reseting(self):

        self.source_layer.setSubsetString('')

        for layer_provider_type in self.layers:
            for layer, layer_props in self.layers[layer_provider_type]:
                layer.setSubsetString('')


        return True


    def execute_exporting(self):
        """Main function to export the selected layers to the right format with their associated styles"""
        self.coordinateReferenceSystem = QgsCoordinateReferenceSystem()
        layers_to_export = None
        projection_to_export = None
        styles_to_export = None
        datatype_to_export = None
        output_folder_to_export = PATH_ABSOLUTE_PROJECT
        zip_to_export = None
        result = None
        zip_result = None

        if self.task_parameters["task"]["exporting"]["has_layers_to_export"] is True:
            if self.task_parameters["task"]["exporting"]["layers_to_export"] != None and len(self.task_parameters["task"]["exporting"]["layers_to_export"]) > 0:
                layers_to_export = [re.search('.* ', layer).group().strip() for layer in self.task_parameters["task"]["exporting"]["layers_to_export"] if re.search('.* ', layer) != None]
            else:
                return False
        else:
            return False

        if self.task_parameters["task"]["exporting"]["has_projection_to_export"] is True:
            if self.task_parameters["task"]["exporting"]["projection_to_export"] != None and self.task_parameters["task"]["exporting"]["projection_to_export"] != '':
                self.coordinateReferenceSystem.createFromWkt(self.task_parameters["task"]["exporting"]["projection_to_export"])
                projection_to_export = self.coordinateReferenceSystem
     
        if self.task_parameters["task"]["exporting"]["has_styles_to_export"] is True:
            if self.task_parameters["task"]["exporting"]["styles_to_export"] != None and self.task_parameters["task"]["exporting"]["styles_to_export"] != '':
                styles_to_export = self.task_parameters["task"]["exporting"]["styles_to_export"].lower()

        if self.task_parameters["task"]["exporting"]["has_datatype_to_export"] is True:
            if self.task_parameters["task"]["exporting"]["datatype_to_export"] != None and self.task_parameters["task"]["exporting"]["datatype_to_export"] != '':
                datatype_to_export = self.task_parameters["task"]["exporting"]["datatype_to_export"]
            else:
                return False
        else:
            return False

        if self.task_parameters["task"]["exporting"]["has_output_folder_to_export"] is True:
            if self.task_parameters["task"]["exporting"]["output_folder_to_export"] != None and self.task_parameters["task"]["exporting"]["output_folder_to_export"] != '':
                output_folder_to_export = self.task_parameters["task"]["exporting"]["output_folder_to_export"]

        if self.task_parameters["task"]["exporting"]["has_zip_to_export"] is True:
            if self.task_parameters["task"]["exporting"]["zip_to_export"] != None and self.task_parameters["task"]["exporting"]["zip_to_export"] != '':
                zip_to_export = self.task_parameters["task"]["exporting"]["zip_to_export"]

        if layers_to_export != None:
            if datatype_to_export == 'GPKG':
                alg_parameters_export = {
                    'LAYERS': [PROJECT.mapLayersByName(layer)[0] for layer in layers_to_export],
                    'OVERWRITE':True,
                    'SAVE_STYLES':self.task_parameters["task"]["exporting"]["has_styles_to_export"],
                    'OUTPUT':output_folder_to_export

                    }
                output = processing.run("qgis:package", alg_parameters_export)

            else:
                if os.path.exists(output_folder_to_export):
                    if os.path.isdir(output_folder_to_export) and len(layers_to_export) > 1:
            
                        for layer_name in layers_to_export:
                            layer = PROJECT.mapLayersByName(layer_name)[0]
                            if projection_to_export == None:
                                current_projection_to_export = layer.sourceCrs()
                            else:
                                current_projection_to_export = projection_to_export
                            result = QgsVectorFileWriter.writeAsVectorFormat(layer, os.path.normcase(os.path.join(output_folder_to_export , layer_name)), "UTF-8", current_projection_to_export, datatype_to_export)
                            if datatype_to_export != 'XLSX':
                                if self.task_parameters["task"]["exporting"]["has_styles_to_export"] is True:
                                    layer.saveNamedStyle(os.path.normcase(os.path.join(output_folder_to_export , layer_name + '.{}'.format(styles_to_export))))

                elif len(layers_to_export) == 1:
                    layer_name = layers_to_export[0]
                    layer = PROJECT.mapLayersByName(layer_name)[0]
                    if projection_to_export == None:
                        current_projection_to_export = layer.sourceCrs()
                    else:
                        current_projection_to_export = projection_to_export
                    result = QgsVectorFileWriter.writeAsVectorFormat(layer, os.path.normcase(output_folder_to_export), "UTF-8", current_projection_to_export, datatype_to_export)
                    if datatype_to_export != 'XLSX':
                        if self.task_parameters["task"]["exporting"]["has_styles_to_export"] is True:
                            layer.saveNamedStyle(os.path.normcase(os.path.join(output_folder_to_export + '.{}'.format(styles_to_export))))

            


            if zip_to_export != None:
                directory, zipfile = os.path.split(output_folder_to_export)
                if os.path.exists(directory) and os.path.isdir(directory):
                    zip_result = self.zipfolder(zip_to_export, output_folder_to_export)

            if list(result)[0] == 0:
                self.message = 'Layer(s) has been exported to <a href="file:///{}">{}</a>'.format(output_folder_to_export, output_folder_to_export)
            if zip_result is True:
                self.message = self.message + ' and ' + 'Zip file has been exported to <a href="file:///{}">{}</a>'.format(zip_to_export, zip_to_export)

            

        return True
    
    def zipfolder(self, zip_file, target_dir):   

        if os.path.exists(target_dir):
            zip_file = zip_file + '.zip' if '.zip' not in os.path.basename(zip_file) else zip_file
            directory = Path(target_dir)

            with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zipobj:
        
                if os.path.isfile(target_dir):
                    zipobj.write(target_dir, arcname=Path(target_dir).relative_to(directory))
                elif os.path.isdir(target_dir):
                    for base, dirs, files in os.walk(target_dir):
                        for file in files:
                            if '.zip' not in file:
                                fn = os.path.join(base, file)
                                zipobj.write(fn, arcname=Path(fn).relative_to(directory))
                return True

    def cancel(self):
        QgsMessageLog.logMessage(
            '"{name}" was canceled'.format(name=self.description()))
        super().cancel()


    def finished(self, result):
        """This function is called automatically when the task is completed and is
        called from the main thread so it is safe to interact with the GUI etc here"""
        if result is False:
            if self.exception is None:
                iface.messageBar().pushMessage('Task was cancelled')
            else:
                iface.messageBar().pushMessage('Errors occured')
                print(self.exception)
        else:
            if self.message != None:
                iface.messageBar().pushMessage(self.message, Qgis.Success, 50)


class barProgress:

    def __init__(self):
        self.prog = 0
        self.bar = None
        self.type = type
        iface.messageBar().clearWidgets()
        self.init()
        self.bar.show()

    def init(self):
        self.bar = QProgressBar()
        self.bar.setMaximum(100)
        self.bar.setValue(self.prog)
        iface.mainWindow().statusBar().addWidget(self.bar)

    def show(self):
        self.bar.show()


    def update(self, prog):
        self.bar.setValue(prog)

    def hide(self):
        self.bar.hide()

class msgProgress:

    def __init__(self):
        self.messageBar = iface.messageBar().createMessage('Doing something time consuming...')
        self.progressBar = QProgressBar()
        self.progressBar.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.cancelButton = QPushButton()
        self.cancelButton.setText('Cancel')
        self.messageBar.layout().addWidget(self.progressBar)
        self.messageBar.layout().addWidget(self.cancelButton)
        iface.messageBar().pushWidget(self.messageBar, Qgis.Info)


    def update(self, prog):
        self.progressBar.setValue(prog)

    def reset(self):
        self.progressBar.setValue(0)

    def setText(self, text):
        self.messageBar.setText(text)




def zoom_to_features(layer, t0):
    end = time.time() - t0
    print("DONE" + " IN " + str(end) + " s.")
    canvas = iface.mapCanvas()
    canvas.setExtent(layer.extent())
    canvas.refresh()

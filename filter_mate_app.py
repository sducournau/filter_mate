from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import QgsCheckableComboBox, QgsFeatureListComboBox, QgsFieldExpressionWidget
from qgis.utils import *
from qgis.utils import iface

import os.path
from pathlib import Path
import re
from .config.config import *
from qgis import processing
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
        self.appTasks = {"filter":None,"unfilter":None,"export":None}
        self.tasks_descriptions = {'filter':'Filtering data',
                                    'unfilter':'Unfiltering data',
                                    'export':'Exporting data'}
        self.plugin_dir = plugin_dir
        self.run()


    def run(self):
        if self.dockwidget == None:
            
            

            init_layers = list(PROJECT.mapLayers().values())
            #self.remove_projectCustomProperties_layers_all()

            self.manage_project_layers(init_layers, 'add')

            self.dockwidget = FilterMateDockWidget(self.PROJECT_LAYERS, self.plugin_dir)

            # show the dockwidget
            # TODO: fix to allow choice of dock location
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
            self.dockwidget.show()


        """Keep the advanced filter combobox updated on adding or removing layers"""

        PROJECT.layersAdded.connect(partial(self.manage_project_layers, 'add'))
        PROJECT.layersWillBeRemoved.connect(partial(self.manage_project_layers, 'remove'))

        
        self.dockwidget.launchingTask.connect(self.manage_task)
        self.dockwidget.reinitializingLayerOnError.connect(self.remove_layer_projectCustomProperties)
        self.dockwidget.settingProjectLayers.connect(self.save_projectCustomProperties_layers)



        
        """Overload configuration qtreeview model to keep configuration file up to date"""
        # self.managerWidgets.model.dataChanged.connect(self.qtree_signal)
        # self.managerWidgets.model.rowsInserted.connect(self.qtree_signal)
        # self.managerWidgets.model.rowsRemoved.connect(self.qtree_signal)



    def save_projectCustomProperties_layers(self, project_layers):
        if isinstance(project_layers, dict):
            self.PROJECT_LAYERS = project_layers
        
        for layer_id in self.PROJECT_LAYERS.keys():
            if self.PROJECT_LAYERS[layer_id]["exploring"]["is_saving"] == True:
                layers = [layer for layer in PROJECT.mapLayersByName(self.PROJECT_LAYERS[layer_id]["infos"]["layer_name"]) if layer.id() == layer_id]
                if len(layers) == 1:
                    layer = layers[0]
                    layer.setCustomProperty("filterMate/infos", json.dumps(self.PROJECT_LAYERS[layer_id]["infos"]))
                    layer.setCustomProperty("filterMate/exploring", json.dumps(self.PROJECT_LAYERS[layer_id]["exploring"]))
                    layer.setCustomProperty("filterMate/filtering", json.dumps(self.PROJECT_LAYERS[layer_id]["filtering"]))
                    
                    if layer.listStylesInDatabase()[0] > -1:
                       layer.saveStyleToDatabase(name="FilterMate_style_{}".format(layer.name()),description="FilterMate style for {}".format(layer.name()), useAsDefault=True, uiFileContent="") 
                    else:
                        layer.saveNamedStyle(os.path.dirname(layer.styleURI())  + 'FilterMate_style_{}.qml'.format(layer.name()))


    def remove_layer_projectCustomProperties(self, layer_id):
        
        if layer_id in self.PROJECT_LAYERS:
            layers = [layer for layer in PROJECT.mapLayersByName(self.PROJECT_LAYERS[layer_id]["infos"]["layer_name"]) if layer.id() == layer_id]
            if len(layers) == 1:
                layer = layers[0]
                layer.removeCustomProperty("filterMate/infos")
                layer.removeCustomProperty("filterMate/exploring")
                layer.removeCustomProperty("filterMate/filtering")
                self.remove_project_layer(layer_id)
                self.add_project_layer(layer)


        if self.dockwidget != None:
            self.dockwidget.get_project_layers_from_app(self.PROJECT_LAYERS) 
                    

    def remove_projectCustomProperties_layers_all(self):
        init_layers = list(PROJECT.mapLayers().values())
    
        for layer in init_layers:
            try:
                layer.removeCustomProperty("filterMate/infos")
                layer.removeCustomProperty("filterMate/exploring")
                layer.removeCustomProperty("filterMate/filtering")
            except:
                pass


    def manage_project_layers(self, layers, action):

        if self.dockwidget != None:

            widgets_to_stop =   [
                                    ["SINGLE_SELECTION","ComboBox_FeaturePickerWidget"],
                                    ["SINGLE_SELECTION","ComboBox_FieldExpressionWidget"],
                                    ["MULTIPLE_SELECTION","ComboBox_CustomCheckableComboBox"],
                                    ["MULTIPLE_SELECTION","ComboBox_FieldExpressionWidget"],
                                    ["CUSTOM_SELECTION","ComboBox_FieldExpressionWidget"],
                                    ["FILTERING","QgsDoubleSpinBox_BUFFER"],
                                    ["FILTERING","ComboBox_LAYERS_TO_FILTER"],
                                    ["FILTERING","ComboBox_CURRENT_LAYER"]
                                ]
        
            for widget_path in widgets_to_stop:
                state = self.dockwidget.manageSignal(widget_path)
                if state == True:
                    raise SignalStateChangeError(state, self.widgets, widget_path)



        self.flags['is_managing_project_layers'] = True

        self.json_template_layer_infos = '{"has_combined_filter_logic":false,"combined_filter_logic":"","subset_history":[],"is_already_subset":false,"layer_geometry_type":"%s","layer_provider_type":"%s","layer_crs":"%s","layer_id":"%s","layer_schema":"%s","layer_name":"%s","primary_key_name":"%s","primary_key_idx":%s,"primary_key_type":"%s","geometry_field":"%s","primary_key_is_numeric":%s }'
        self.json_template_layer_exploring = '{"is_saving":false,"is_tracking":false,"is_selecting":false,"is_linked":false,"single_selection_expression":"%s","multiple_selection_expression":"%s","custom_selection_expression":"%s" }'
        self.json_template_layer_filtering = '{"has_layers_to_filter":false,"layers_to_filter":[],"has_geometric_predicates":false,"geometric_predicates":[],"geometric_predicates_operator":"AND","has_buffer":false,"buffer":0.0 }'

        for layer in layers:
            if action == 'add':     
                self.add_project_layer(layer)
            elif action == 'remove':
                self.remove_project_layer(layer)

        if self.dockwidget != None:
            for widget_path in widgets_to_stop:
                state = self.dockwidget.manageSignal(widget_path)
                if state == False:
                    raise SignalStateChangeError(state, self.widgets, widget_path)

            self.dockwidget.get_project_layers_from_app(self.PROJECT_LAYERS)
            


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

                new_layer_infos = json.loads(self.json_template_layer_infos % (layer_geometry_type, layer_provider_type, layer.sourceCrs().authid(), layer.id(), source_schema, layer.name(), primary_key_name, primary_key_idx, primary_key_type, geometry_field, str(primary_key_is_numeric).lower()))
                new_layer_exploring = json.loads(self.json_template_layer_exploring % (str(primary_key_name),str(primary_key_name),str(primary_key_name)))
                new_layer_filtering = json.loads(self.json_template_layer_filtering)


                if "filterMate/infos" in layer.customPropertyKeys() and "filterMate/exploring" in layer.customPropertyKeys() and "filterMate/filtering" in layer.customPropertyKeys():
                    existing_layer_infos = json.loads(layer.customProperty("filterMate/infos"))
                    layer_infos = self.check_dict_structure(existing_layer_infos, new_layer_infos)
                    existing_layer_exploring = json.loads(layer.customProperty("filterMate/exploring"))
                    layer_exploring = self.check_dict_structure(existing_layer_exploring, new_layer_exploring)
                    existing_layer_filtering = json.loads(layer.customProperty("filterMate/filtering"))
                    layer_filtering = self.check_dict_structure(existing_layer_filtering, new_layer_filtering)

                else:
                    layer_infos = new_layer_infos
                    layer_exploring = new_layer_exploring
                    layer_filtering = new_layer_filtering

                self.PROJECT_LAYERS[str(layer.id())] = {"infos": layer_infos, "exploring": layer_exploring, "filtering": layer_filtering}

    def remove_project_layer(self, layer_id):
        try:
            if self.dockwidget.current_layer.id() == layer_id:
                self.dockwidget.mFieldExpressionWidget_exploring_single_selection.setLayer(None)
                self.dockwidget.mFeaturePickerWidget_exploring_single_selection.setLayer(None)
                self.dockwidget.mFieldExpressionWidget_exploring_multiple_selection.setLayer(None)
                self.dockwidget.customCheckableComboBox_exploring_multiple_selection.setLayer(None)
                self.dockwidget.mFieldExpressionWidget_exploring_custom_selection.setLayer(None)

            del self.PROJECT_LAYERS[layer_id]


            
        except:
            print("Layer id not found")

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

        return 'ID', new_field.id(), new_field.typeName(), True


    def manage_task(self, task_name):
        """Manage the different tasks"""

        assert task_name in list(self.tasks_descriptions.keys())
        
        task_parameters, current_layer = self.get_task_parameters(task_name)

        self.appTasks[task_name] = FilterEngineTask(self.tasks_descriptions[task_name], task_name, task_parameters)

        self.appTasks[task_name].taskCompleted.connect(partial(self.task_postprocessing, task_name, current_layer, task_parameters))

        QgsApplication.taskManager().addTask(self.appTasks[task_name])


    def get_task_parameters(self, task_name):

        current_layer = self.dockwidget.current_layer
        
        if current_layer.id() in self.PROJECT_LAYERS.keys():
            task_parameters = self.PROJECT_LAYERS[current_layer.id()]

        if current_layer.subsetString() != '':
            self.PROJECT_LAYERS[current_layer.id()]["infos"]["is_already_subset"] = True
        else:
            self.PROJECT_LAYERS[current_layer.id()]["infos"]["is_already_subset"] = False

        features, expression = self.dockwidget.get_current_features()

        if task_name == 'filter':

            task_parameters["task"] = {"features": features, "expression": expression}
            return task_parameters, current_layer

        elif task_name == 'unfilter':

            task_parameters["task"] = {"features": features, "expression": expression}
            return task_parameters, current_layer

        elif task_name == 'export':
            return task_parameters, current_layer
            

    def task_postprocessing(self, task_name, current_layer, task_parameters):
         
        if current_layer.subsetString() != '':
            self.PROJECT_LAYERS[current_layer.id()]["infos"]["is_already_subset"] = True
            if task_name == 'filter':
                self.PROJECT_LAYERS[current_layer.id()]["infos"]["subset_history"].append({"source_layer":current_layer.id(), "subset_string":current_layer.subsetString()})
            elif task_name == 'unfilter':
                if len(self.PROJECT_LAYERS[current_layer.id()]["infos"]["subset_history"]) > 0:
                    self.PROJECT_LAYERS[current_layer.id()]["infos"]["subset_history"] = [subset_history for subset_history in self.PROJECT_LAYERS[current_layer.id()]["infos"]["subset_history"] if subset_history["source_layer"] != current_layer.id()]
        else:
            self.PROJECT_LAYERS[current_layer.id()]["infos"]["is_already_subset"] = False
            self.PROJECT_LAYERS[current_layer.id()]["infos"]["subset_history"] = []
    
        if task_parameters["filtering"]["has_layers_to_filter"] == True:
            for layer_props in task_parameters["filtering"]["layers_to_filter"]:
                if layer_props["layer_id"] in self.PROJECT_LAYERS:
                    layers = [layer for layer in PROJECT.mapLayersByName(layer_props["layer_name"]) if layer.id() == layer_props["layer_id"]]
                    if len(layers) == 1:
                        layer = layers[0]
                        if layer.subsetString() != '':
                            self.PROJECT_LAYERS[layer.id()]["infos"]["is_already_subset"] = True
                            if task_name == 'filter':
                                self.PROJECT_LAYERS[layer.id()]["infos"]["subset_history"].append({"source_layer":current_layer.id(), "subset_string":layer.subsetString()})
                                print(layer, self.PROJECT_LAYERS[layer.id()]["infos"]["subset_history"])
                            elif task_name == 'unfilter':
                                if len(self.PROJECT_LAYERS[layer.id()]["infos"]["subset_history"]) > 0:
                                    self.PROJECT_LAYERS[layer.id()]["infos"]["subset_history"] = [subset_history for subset_history in self.PROJECT_LAYERS[layer.id()]["infos"]["subset_history"] if subset_history["source_layer"] != current_layer.id()]
                        else:
                            self.PROJECT_LAYERS[layer.id()]["infos"]["is_already_subset"] = False
                            self.PROJECT_LAYERS[layer.id()]["infos"]["subset_history"] = []
           
        self.iface.mapCanvas().refreshAllLayers()
        self.iface.mapCanvas().refresh()
        self.dockwidget.get_project_layers_from_app(self.PROJECT_LAYERS)

        if task_name == 'filter':
            self.dockwidget.exploring_zoom_clicked()



class FilterEngineTask(QgsTask):
    """Main QgsTask class which filter and unfilter data"""

    def __init__(self, description, task_action, task_parameters):

        QgsTask.__init__(self, description, QgsTask.CanCancel)


        self.exception = None
        self.task_action = task_action
        self.task_parameters = task_parameters
        
        self.expression = None
        self.is_field_expression = None

        self.param_source_provider_type = None
        self.param_buffer_value = None
        self.param_source_schema = None
        self.param_source_table = None
        self.param_source_geom = None
        self.param_source_geom_operator = None
        self.param_source_subset = None

        self.postgresql_source_geom = None
        self.spatialite_source_geom = None
        self.ogr_source_geom = None

        self.current_predicates = {}
        self.outputs = {}

        self.predicates = {"Intersect":"ST_Intersects","Contain":"ST_Contains","Disjoint":"ST_Disjoint","Equal":"ST_Equals","Touch":"ST_Touches","Overlap":"ST_Overlaps","Are within":"ST_Within","Cross":"ST_Crosses"}

    def run(self):
        """Main function that run the right method from init parameters"""

        try:

            layers = [layer for layer in PROJECT.mapLayersByName(self.task_parameters["infos"]["layer_name"]) if layer.id() == self.task_parameters["infos"]["layer_id"]]
            if len(layers) == 1:
                self.source_layer = layers[0]


            """We split the selected layers to be filtered in two categories sql and others"""
            self.layers = {}

            if self.task_parameters["filtering"]["has_layers_to_filter"] == True:
                for layer_props in self.task_parameters["filtering"]["layers_to_filter"]:
                    if layer_props["layer_provider_type"] not in self.layers:
                        self.layers[layer_props["layer_provider_type"]] = []

                    layers = [layer for layer in PROJECT.mapLayersByName(layer_props["layer_name"]) if layer.id() == layer_props["layer_id"]]
                    if len(layers) == 1:
                        self.layers[layer_props["layer_provider_type"]].append([layers[0], layer_props])
    
                self.provider_list = list(self.layers)

            if self.task_action == 'filter':
                """We will filter layers"""

                self.execute_filtering()
                    

            elif self.task_action == 'unfilter':
                """We will unfilter the layers"""

                self.execute_unfiltering()


            elif self.task_action == 'export':
                """We will export layers"""

                self.execute_exporting()
                
            return True
    
        except Exception as e:
            self.exception = e
            print(self.exception)
            return False


    def execute_filtering(self):
        """Manage the advanced filtering"""

       
        result = self.execute_source_layer_filtering()


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
                        param_combine_operator = ''
                        if layer_prop["has_combined_filter_logic"] == True:
                            if layer_prop["combined_filter_logic"] != '':
                                param_combine_operator = layer_prop["combined_filter_logic"]
                                if layer_prop["is_already_subset"] == True:
                                    param_old_subset = layer.subsetString()

                        if param_old_subset != '' and param_combine_operator != '':

                            result = self.source_layer.setSubsetString('( {old_subset} ) {combine_operator} {expression}'.format(old_subset=param_old_subset,
                                                                                                                                combine_operator=param_combine_operator,
                                                                                                                                expression=self.expression))
                        else:
                            result = self.source_layer.setSubsetString(self.expression)

        return result
    

    def execute_source_layer_filtering(self):
        """Manage the creation of the origin filtering expression"""
        result = False
        param_combine_operator = ''
        param_old_subset = ''

        self.param_source_provider_type = self.task_parameters["infos"]["layer_provider_type"]
        self.param_source_schema = self.task_parameters["infos"]["layer_schema"]
        self.param_source_table = self.task_parameters["infos"]["layer_name"]
        self.primary_key_name = self.task_parameters["infos"]["primary_key_name"]
        self.source_layer_fields_names = [field.name() for field in self.source_layer.fields() if field.name() != self.primary_key_name]

        if self.task_parameters["infos"]["has_combined_filter_logic"] == True:
            if self.task_parameters["infos"]["combined_filter_logic"] != '':
                param_combine_operator = self.task_parameters["infos"]["combined_filter_logic"]
                if self.task_parameters["infos"]["is_already_subset"] == True:
                    param_old_subset = self.source_layer.subsetString()

        if self.task_parameters["task"]["expression"] != None:
            self.expression = " " + self.task_parameters["task"]["expression"]
            if QgsExpression(self.expression).isValid() is True:
                
                is_field_expression =  QgsExpression().isFieldEqualityExpression(self.task_parameters["task"]["expression"])

                if is_field_expression[0] == True:
                    self.is_field_expression = is_field_expression

                if QgsExpression(self.expression).isField() is False:
                    
                    print(self.expression)
                    existing_fields = [x for x in self.source_layer_fields_names if self.expression.find(x) > -1]
                    if len(existing_fields) == 0 and self.expression.find(self.primary_key_name) > -1:
                        if self.expression.find(self.param_source_table) < 0:
                            if self.expression.find(' "' + self.primary_key_name + '" ') > -1:
                                self.expression = self.expression.replace('"' + self.primary_key_name + '"', '"{source_table}"."{field_name}"'.format(source_table=self.param_source_table, field_name=self.primary_key_name))
                            elif self.expression.find(" " + self.primary_key_name + " ") > -1:
                                self.expression = self.expression.replace(self.primary_key_name, '"{source_table}"."{field_name}"'.format(source_table=self.param_source_table, field_name=self.primary_key_name))
                    elif len(existing_fields) >= 1:
                        if self.expression.find(self.param_source_table) < 0:
                            for field_name in existing_fields:
                                if self.expression.find(' "' + field_name + '" ') > -1:
                                    self.expression = self.expression.replace('"' + field_name + '"', '"{source_table}"."{field_name}"'.format(source_table=self.param_source_table, field_name=field_name))
                                elif self.expression.find(" " + field_name + " ") > -1:
                                    self.expression = self.expression.replace(field_name, '"{source_table}"."{field_name}"'.format(source_table=self.param_source_table, field_name=field_name))


                    if param_old_subset != '' and param_combine_operator != '':

                        result = self.source_layer.setSubsetString('( {old_subset} ) {combine_operator} {expression}'.format(old_subset=param_old_subset,
                                                                                                                            combine_operator=param_combine_operator,
                                                                                                                            expression=self.expression))
                    else:
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


                if param_old_subset != '' and param_combine_operator != '':

                    result = self.source_layer.setSubsetString('( {old_subset} ) {combine_operator} {expression}'.format(old_subset=param_old_subset,
                                                                                                                        combine_operator=param_combine_operator,
                                                                                                                        expression=self.expression))
                else:
                    result = self.source_layer.setSubsetString(self.expression)

 
        return result
        

    def manage_distant_layers_geometric_filtering(self):
        """Filter layers from a prefiltered layer"""

        result = False
        self.param_source_geom = self.task_parameters["infos"]["geometry_field"]
        self.param_source_geom_operator = ' ' + self.task_parameters["filtering"]["geometric_predicates_operator"] + ' '
        self.param_source_subset = self.expression

        if self.task_parameters["filtering"]["has_buffer"]:
            self.param_buffer_value = float(self.task_parameters["filtering"]["buffer"]) 
        
        provider_list = self.provider_list + [self.param_source_provider_type]

        if 'postgresql' in provider_list:
            self.prepare_postgresql_source_geom()

        if 'spatialite' in provider_list:
            self.prepare_spatialite_source_geom()

        if 'ogr' in provider_list:
            self.prepare_ogr_source_geom()

        for layer_provider_type in self.layers:
            for layer, layer_props in self.layers[layer_provider_type]:
                result = self.execute_geometric_filtering(layer_provider_type, layer, layer_props)
                if result == True:
                    print(layer.name(), 'has been filtered')
                else:
                    print(layer.name(), 'errors occured')


    def prepare_postgresql_source_geom(self):

        if self.param_buffer_value != None:
            self.postgresql_source_geom = 'ST_Buffer("{source_table}"."{source_geom}", {buffer_value})'.format(source_table=self.param_source_table,
                                                                                                               source_geom=self.param_source_geom,
                                                                                                               buffer_value=self.param_buffer_value)
        else:
            self.postgresql_source_geom = '"{source_table}"."{source_geom}"'.format(source_table=self.param_source_table,
                                                                                    source_geom=self.param_source_geom)


    def prepare_spatialite_source_geom(self):

        raw_geometries = [feature.geometry() for feature in self.task_parameters["task"]["features"] if feature.hasGeometry()]
        geometries = []

        for geometry in raw_geometries:
            if geometry.isEmpty() is False:
                if geometry.isMultipart():
                    geometry.convertToSingleType()
                if self.param_buffer_value != None:
                    geometry = geometry.buffer(self.param_buffer_value, 5)
                geometries.append(geometry)

        collected_geometry = QgsGeometry().collectGeometry(geometries)
        self.spatialite_source_geom = collected_geometry.asWkt().strip()


    def prepare_ogr_source_geom(self):

        if self.param_buffer_value != None:

            alg_params_buffer = {
                'DISSOLVE': True,
                'DISTANCE': self.param_buffer_value,
                'END_CAP_STYLE': 2,
                'INPUT': self.source_layer,
                'JOIN_STYLE': 2,
                'MITER_LIMIT': 2,
                'SEGMENTS': 5,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }

            self.outputs['alg_params_buffer'] = processing.run('qgis:buffer', alg_params_buffer)
            self.ogr_source_geom = self.outputs['alg_params_buffer']['OUTPUT']


    def execute_geometric_filtering(self, layer_provider_type, layer, layer_props):

        result = False
        postgis_predicates = list(self.current_predicates.values())

        param_old_subset = ''
        param_combine_operator = ''
        if layer_props["has_combined_filter_logic"] == True:
            if layer_props["combined_filter_logic"] != '':
                param_combine_operator = layer_props["combined_filter_logic"]
                if layer_props["is_already_subset"] == True:
                    param_old_subset = layer.subsetString()

        param_distant_schema = layer_props["layer_schema"]
        param_distant_table = layer_props["layer_name"]
        param_distant_primary_key_name = layer_props["primary_key_name"]
        param_distant_primary_key_is_numeric = layer_props["primary_key_is_numeric"]
        param_distant_geometry_field = layer_props["geometry_field"]


        if self.param_source_provider_type == 'postgresql' and layer_provider_type == 'postgresql':

            postgis_sub_expression_array = []
            for postgis_predicate in postgis_predicates:
                postgis_sub_expression_array.append(postgis_predicate + '({source_sub_expression_geom},"{distant_table}"."{distant_geometry_field}")'.format(source_sub_expression_geom=self.postgresql_source_geom,
                                                                                                                                                                distant_table=param_distant_table,
                                                                                                                                                                distant_geometry_field=param_distant_geometry_field))
            
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
            print(param_expression)
            if param_old_subset != '' and param_combine_operator != '':
                result = layer.setSubsetString('({old_subset}) {combine_operator} {expression}'.format(old_subset=param_old_subset,
                                                                                              combine_operator=param_combine_operator,
                                                                                              expression=param_expression))
            else:
                result = layer.setSubsetString(param_expression)
    

        elif self.param_source_provider_type == 'spatialite' or layer_provider_type == 'spatialite':

            spatialite_sub_expression_array = []
            for postgis_predicate in postgis_predicates:
                spatialite_sub_expression_array.append(postgis_predicate + '(ST_GeomFromText(\'{source_sub_expression_geom}\'),"{distant_geometry_field}")'.format(source_sub_expression_geom=self.spatialite_source_geom,
                                                                                                                                                    distant_geometry_field=param_distant_geometry_field))
            if len(spatialite_sub_expression_array) > 1:
                param_spatialite_sub_expression = self.param_source_geom_operator.join(spatialite_sub_expression_array)
            else:
                param_spatialite_sub_expression = spatialite_sub_expression_array[0]

            param_expression = 'SELECT {postgis_sub_expression}'.format(postgis_sub_expression=param_spatialite_sub_expression)

            print(param_expression)
            if param_old_subset != '' and param_combine_operator != '':
                result = layer.setSubsetString('({old_subset}) {combine_operator} {expression}'.format(old_subset=param_old_subset,
                                                                                              combine_operator=param_combine_operator,
                                                                                              expression=param_expression))
            else:
                result = layer.setSubsetString(param_expression)              


        elif self.param_source_provider_type == 'ogr' or layer_provider_type == 'ogr':

            features_list = []
            alg_params_select = {
                'INPUT': layer,
                'INTERSECT': self.ogr_source_geom if self.ogr_source_geom != None else self.source_layer,
                'METHOD': 0,
                'PREDICATE': [int(predicate) for predicate in self.current_predicates]
            }
            processing.run("qgis:selectbylocation", alg_params_select)

            for feature in layer.selectedFeatures():
                features_list.append(feature)

            layer.removeSelection()
            features_ids = [str(feature[param_distant_primary_key_name]) for feature in features_list]

            if len(features_ids) > 0:
                if param_distant_primary_key_is_numeric == True:
                    param_expression = '"{distant_table}"."{distant_primary_key_name}" IN '.format(distant_table=param_distant_table, distant_primary_key_name=param_distant_primary_key_name) + "(" + ", ".join(features_ids) + ")"
                else:
                    param_expression = '"{distant_table}"."{distant_primary_key_name}" IN '.format(distant_table=param_distant_table, distant_primary_key_name=param_distant_primary_key_name) + "(\'" + "\', \'".join(features_ids) + "\')"

                if QgsExpression(param_expression).isValid():

                    if param_old_subset != '' and param_combine_operator != '':

                        result = self.source_layer.setSubsetString('( {old_subset} ) {combine_operator} {expression}'.format(old_subset=param_old_subset,
                                                                                                                            combine_operator=param_combine_operator,
                                                                                                                            expression=param_expression))
                    else:
                        result = self.source_layer.setSubsetString(param_expression)

        return result    


    def execute_unfiltering(self):

        if len(self.task_parameters["infos"]["subset_history"]) > 1:
            if self.task_parameters["infos"]["subset_history"][-1]["source_layer"] == self.source_layer.id():
                self.source_layer.setSubsetString(self.task_parameters["infos"]["subset_history"][-2]["subset_string"])
            else:
                self.source_layer.setSubsetString('')
        else:
            self.source_layer.setSubsetString('')
        
        for layer_provider_type in self.layers:
            for layer, layer_props in self.layers[layer_provider_type]:
                if len(layer_props["subset_history"]) > 1:
                    print(self.source_layer.id())
                    print(layer, layer_props["subset_history"])
                    if layer_props["subset_history"][-1]["source_layer"] == self.source_layer.id():
                        print(layer_props["subset_history"][-2]["subset_string"])
                        layer.setSubsetString(layer_props["subset_history"][-2]["subset_string"])
                    else:
                        layer.setSubsetString('')
                else:
                    layer.setSubsetString('')

        return True


    def execute_exporting(self):
        """Main function to export the selected layers to the right format with their associated styles"""

        format = self.dockwidget.comboBox_export_type.currentText()
        output = {}
        name = str(self.dockwidget.lineEdit_export.text()) if self.dockwidget.lineEdit_export.text() != '' else 'output'
        crs = self.dockwidget.mQgsProjectionSelectionWidget.crs()
        if format == 'GeoPackage':
            alg_parameters_export = {
                'LAYERS': [PROJECT.mapLayersByName(layer)[0] for layer in self.dockwidget.comboBox_select_layers.checkedItems()],
                'OVERWRITE':True,
                'SAVE_STYLES':True,
                'OUTPUT':PATH_ABSOLUTE_PROJECT + '\{name}.{format}'.format(name=name,format='gpkg')

                }
            print(PATH_ABSOLUTE_PROJECT + '\{name}.{format}'.format(name=name,format='gpkg'))
            output = processing.run("qgis:package", alg_parameters_export)

        else:
            if not os.path.isdir(PATH_ABSOLUTE_PROJECT + os.sep + name):
                os.mkdir(PATH_ABSOLUTE_PROJECT + os.sep + name)

            for layer in self.dockwidget.comboBox_select_layers.checkedItems():
                if self.isCanceled():
                    print('Cancel')
                    return False
                QgsVectorFileWriter.writeAsVectorFormat(PROJECT.mapLayersByName(layer)[0], PATH_ABSOLUTE_PROJECT + os.sep + name + os.sep + PROJECT.mapLayersByName(layer)[0].name(), "UTF-8", crs, format)
                if format != 'XLSX':
                    PROJECT.mapLayersByName(layer)[0].saveNamedStyle(PATH_ABSOLUTE_PROJECT + os.sep + name + os.sep + PROJECT.mapLayersByName(layer)[0].name() + '.qml')

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

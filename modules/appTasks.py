from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.utils import *
from qgis.utils import iface
from qgis import processing

import psycopg2
import uuid
from collections import OrderedDict
from operator import getitem
import zipfile
import os
import os.path
from pathlib import Path
import re
from functools import partial
import json
from ..config.config import *
from .appUtils import *
from qgis.utils import iface

MESSAGE_TASKS_CATEGORIES = {
                            'filter':'FilterLayers',
                            'unfilter':'FilterLayers',
                            'reset':'FilterLayers',
                            'export':'ExportLayers',
                            'add_layers':'ManageLayers',
                            'remove_layers':'ManageLayers',
                            'save_layer_variable':'ManageLayersProperties',
                            'remove_layer_variable':'ManageLayersProperties'
                            }



class FilterEngineTask(QgsTask):
    """Main QgsTask class which filter and unfilter data"""

    def __init__(self, description, task_action, task_parameters):

        QgsTask.__init__(self, description, QgsTask.CanCancel)

        self.exception = None
        self.task_action = task_action
        self.task_parameters = task_parameters

        self.db_file_path = None
        self.project_uuid = None

        self.layers_count = None
        self.layers = {}
        self.expression = None
        self.is_field_expression = None

        self.has_feature_count_limit = True
        self.feature_count_limit = None
        self.param_source_provider_type = None
        self.has_combine_operator = None
        self.param_source_layer_combine_operator = None
        self.param_other_layers_combine_operator = None
        self.param_buffer_expression = None
        self.param_buffer_value = None
        self.param_source_schema = None
        self.param_source_table = None
        self.param_source_layer_id = None
        self.param_source_geom = None
        self.param_source_new_subset = None
        self.param_source_old_subset = None

        self.current_materialized_view_schema = None
        self.current_materialized_view_name = None

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
        global ENV_VARS
        self.PROJECT = ENV_VARS["PROJECT"]
        self.current_materialized_view_schema = 'filter_mate_temp'

    def run(self):
        """Main function that run the right method from init parameters"""


        try:
            self.layers_count = 1    
            layers = [layer for layer in self.PROJECT.mapLayersByName(self.task_parameters["infos"]["layer_name"]) if layer.id() == self.task_parameters["infos"]["layer_id"]]
            if len(layers) > 0:
                self.source_layer = layers[0]
                self.source_crs = self.source_layer.sourceCrs()
                source_crs_distance_unit = self.source_crs.mapUnits()
                self.source_layer_crs_authid = self.task_parameters["infos"]["layer_crs_authid"]
                
                if source_crs_distance_unit in ['DistanceUnit.Degrees','DistanceUnit.Unknown'] or self.source_crs.isGeographic() is True:
                    self.has_to_reproject_source_layer = True
                    self.source_layer_crs_authid = "EPSG:3857"



                if "options" in self.task_parameters["task"] and "LAYERS" in self.task_parameters["task"]["options"] and "FEATURE_COUNT_LIMIT" in self.task_parameters["task"]["options"]["LAYERS"]:
                    if isinstance(self.task_parameters["task"]["options"]["LAYERS"]["FEATURE_COUNT_LIMIT"], int) and self.task_parameters["task"]["options"]["LAYERS"]["FEATURE_COUNT_LIMIT"] > 0:
                        self.feature_count_limit = self.task_parameters["task"]["options"]["LAYERS"]["FEATURE_COUNT_LIMIT"]

            """We split the selected layers to be filtered in two categories sql and others"""

            if self.task_parameters["filtering"]["has_layers_to_filter"] == True:
                for layer_props in self.task_parameters["task"]["layers"]:
                    if layer_props["layer_provider_type"] not in self.layers:
                        self.layers[layer_props["layer_provider_type"]] = []

                    layers = [layer for layer in self.PROJECT.mapLayersByName(layer_props["layer_name"]) if layer.id() == layer_props["layer_id"]]
                    if len(layers) > 0:
                        self.layers[layer_props["layer_provider_type"]].append([layers[0], layer_props])
                        self.layers_count += 1
    
                self.provider_list = list(self.layers)

            if 'db_file_path' in self.task_parameters["task"] and self.task_parameters["task"]['db_file_path'] not in (None, ''):
                self.db_file_path = self.task_parameters["task"]['db_file_path']
        
            if 'project_uuid' in self.task_parameters["task"] and self.task_parameters["task"]['project_uuid'] not in (None, ''):
                self.project_uuid = self.task_parameters["task"]['project_uuid']


            if self.task_action == 'filter':
                """We will filter layers"""

                result = self.execute_filtering()
                if self.isCanceled() or result is False:
                    return False
                    

            elif self.task_action == 'unfilter':
                """We will unfilter the layers"""

                result = self.execute_unfiltering()
                if self.isCanceled() or result is False:
                    return False

            elif self.task_action == 'reset':
                """We will reset the layers"""

                result = self.execute_reseting()
                if self.isCanceled() or result is False:
                    return False                

            elif self.task_action == 'export':
                """We will export layers"""
                if self.task_parameters["task"]["EXPORTING"]["HAS_LAYERS_TO_EXPORT"] == True:
                    result = self.execute_exporting()
                    if self.isCanceled() or result is False:
                        return False
                else:
                    return False
            
            return True
    
        except Exception as e:
            self.exception = e
            print(self.exception)
            return False


    def execute_source_layer_filtering(self):
        """Manage the creation of the origin filtering expression"""
        result = False
        self.param_source_old_subset = ''

        self.param_source_provider_type = self.task_parameters["infos"]["layer_provider_type"]
        self.param_source_schema = self.task_parameters["infos"]["layer_schema"]
        self.param_source_table = self.task_parameters["infos"]["layer_name"]
        self.param_source_layer_id = self.task_parameters["infos"]["layer_id"]
        self.param_source_geom = self.task_parameters["infos"]["geometry_field"]
        self.primary_key_name = self.task_parameters["infos"]["primary_key_name"]
        self.has_combine_operator = self.task_parameters["filtering"]["has_combine_operator"]
        self.source_layer_fields_names = [field.name() for field in self.source_layer.fields() if field.name() != self.primary_key_name]

        if self.has_combine_operator == True:
            self.param_source_layer_combine_operator = self.task_parameters["filtering"]["source_layer_combine_operator"]
            self.param_other_layers_combine_operator = self.task_parameters["filtering"]["other_layers_combine_operator"]
            if self.source_layer.subsetString() != '':
                self.param_source_old_subset = self.source_layer.subsetString()

                

        print(self.task_parameters["task"]["expression"])
        if self.task_parameters["task"]["expression"] != None:
            
            self.expression = self.task_parameters["task"]["expression"]
            if QgsExpression(self.expression).isField() is False:

                if QgsExpression(self.expression).isValid() is True:

                    self.expression = " " + self.expression
                    is_field_expression =  QgsExpression().isFieldEqualityExpression(self.task_parameters["task"]["expression"])

                    if is_field_expression[0] == True:
                        self.is_field_expression = is_field_expression
                    
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

                    self.expression = self.qgis_expression_to_postgis(self.expression)
                    self.expression = self.expression.strip()
                    if self.expression.find("CASE") == 0:
                        self.expression = 'SELECT ' + self.expression

                    param_old_subset_where_clause = ''
                    param_source_old_subset = ''
                    if self.param_source_old_subset != '' and self.param_source_layer_combine_operator != '':
                        index_where_clause = self.param_source_old_subset.find('WHERE')
                        if index_where_clause > -1:
                            param_old_subset_where_clause = self.param_source_old_subset[index_where_clause:]
                            if param_old_subset_where_clause[-2:] == '))':
                                param_old_subset_where_clause = param_old_subset_where_clause[:-1]
                                param_source_old_subset = self.param_source_old_subset[:index_where_clause]

                        self.expression = '{source_old_subset} {old_subset_where_clause} {param_combine_operator} {expression} )'.format(source_old_subset=param_source_old_subset,
                                                                                                                                            old_subset_where_clause=param_old_subset_where_clause,   
                                                                                                                                            param_combine_operator=self.param_source_layer_combine_operator, 
                                                                                                                                            expression=self.expression)

                    # sql_expression = QgsSQLStatement('SELECT * FROM  "{source_schema}"."{source_table}" WHERE {expression}'.format(source_schema=self.param_source_schema,
                    #                                                                                                                 source_table=self.param_source_table,
                    #                                                                                                                 expression=self.expression),
                    #                                                                                                                 True)
                    # validation_check = sql_expression.doBasicValidationChecks()
                    # print(sql_expression)
                    # print(sql_expression.dump())
                    # print(validation_check)
                    
                    # if validation_check[0] is True:

                    result = self.source_layer.setSubsetString(self.expression)
                    if result is True:
                        expression = 'SELECT "{param_source_table}"."{primary_key_name}", "{param_source_table}"."{param_source_geom}" FROM "{param_source_schema}"."{param_source_table}" WHERE {expression}'.format(
                                                                                                                                                                                                                        primary_key_name=self.primary_key_name,
                                                                                                                                                                                                                        param_source_geom=self.param_source_geom,
                                                                                                                                                                                                                        param_source_schema=self.param_source_schema,
                                                                                                                                                                                                                        param_source_table=self.param_source_table,
                                                                                                                                                                                                                        expression=self.expression
                                                                                                                                                                                                                        )  
                        self.manage_layer_subset_strings(self.source_layer, expression, self.primary_key_name)


        if result is False:
            self.is_field_expression = None    
            features_list = self.task_parameters["task"]["features"]

            features_ids = [str(feature[self.primary_key_name]) for feature in features_list]

            if len(features_ids) > 0:
                if self.task_parameters["infos"]["primary_key_is_numeric"] is True:
                    self.expression = '"{source_table}"."{primary_key_name}" IN '.format(source_table=self.param_source_table, primary_key_name=self.primary_key_name) + "(" + ", ".join(features_ids) + ")"
                else:
                    self.expression = '"{source_table}"."{primary_key_name}" IN '.format(source_table=self.param_source_table, primary_key_name=self.primary_key_name) + "(\'" + "\', \'".join(features_ids) + "\')"
                
                if self.param_source_old_subset != '' and self.param_source_layer_combine_operator != '':
                    self.expression = '( {param_old_subset} ) {param_combine_operator} {expression}'.format(param_old_subset=self.param_source_old_subset, param_combine_operator=self.param_source_layer_combine_operator, expression=self.expression)

                # sql_expression = QgsSQLStatement('SELECT * FROM  "{source_schema}"."{source_table}" WHERE {expression}'.format(source_schema=self.param_source_schema,
                #                                                                                                                 source_table=self.param_source_table,
                #                                                                                                                 expression=self.expression),
                #                                                                                                                 True)
                # validation_check = sql_expression.doBasicValidationChecks()
                # print(validation_check)
                # if validation_check[0] is True:

                result = self.source_layer.setSubsetString(self.expression)
                if result is True:
                    expression = 'SELECT "{param_source_table}"."{primary_key_name}", "{param_source_table}"."{param_source_geom}" FROM "{param_source_schema}"."{param_source_table}" WHERE {expression}'.format(
                                                                                                                                                                                                                    primary_key_name=self.primary_key_name,
                                                                                                                                                                                                                    param_source_geom=self.param_source_geom,
                                                                                                                                                                                                                    param_source_schema=self.param_source_schema,
                                                                                                                                                                                                                    param_source_table=self.param_source_table,
                                                                                                                                                                                                                    expression=self.expression
                                                                                                                                                                                                                    )  
                    self.manage_layer_subset_strings(self.source_layer, expression, self.primary_key_name)



        return result
    
    def manage_distant_layers_geometric_filtering(self):
        """Filter layers from a prefiltered layer"""

        result = False
        
        if QgsExpression(self.expression).isField() is False:
            self.param_source_new_subset = self.expression
        else:
            self.param_source_new_subset = self.param_source_old_subset


        if self.task_parameters["filtering"]["has_buffer_value"] is True:
            if self.task_parameters["filtering"]["buffer_value_property"] is True:
                if self.task_parameters["filtering"]["buffer_value_expression"] != '':
                    self.param_buffer_expression = self.task_parameters["filtering"]["buffer_value_expression"]
                else:
                    self.param_buffer_value = self.task_parameters["filtering"]["buffer_value"]
            else:
                self.param_buffer_value = self.task_parameters["filtering"]["buffer_value"]  

        
        provider_list = self.provider_list + [self.param_source_provider_type]
        provider_list = list(dict.fromkeys(provider_list))

        if 'postgresql' in provider_list:
            self.prepare_postgresql_source_geom()

        if 'ogr' in provider_list or 'spatialite' in provider_list or self.param_buffer_expression != '':
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
                if self.isCanceled():
                    return False
                
        return True
    
    def qgis_expression_to_postgis(self, expression):

        if expression.find('if') >= 0:
            expression = re.sub('if\((.*,.*,.*)\))', '(if(.* then .* else .*))', expression)
            print(expression)


        expression = expression.replace('" >', '"::numeric >').replace('">', '"::numeric >')
        expression = expression.replace('" <', '"::numeric <').replace('"<', '"::numeric <')
        expression = expression.replace('" +', '"::numeric +').replace('"+', '"::numeric +')
        expression = expression.replace('" -', '"::numeric -').replace('"-', '"::numeric -')

        expression = re.sub('case', ' CASE ', expression)
        expression = re.sub('when', ' WHEN ', expression)
        expression = re.sub(' is ', ' IS ', expression)
        expression = re.sub('then', ' THEN ', expression)
        expression = re.sub('else', ' ELSE ', expression)
        expression = re.sub('ilike', ' ILIKE ', expression)
        expression = re.sub('like', ' LIKE ', expression)
        expression = re.sub('not', ' NOT ', expression)

        expression = expression.replace('" NOT ILIKE', '"::text NOT ILIKE').replace('" ILIKE', '"::text ILIKE')
        expression = expression.replace('" NOT LIKE', '"::text NOT LIKE').replace('" LIKE', '"::text LIKE')

        return expression


    def prepare_postgresql_source_geom(self):
        

        source_table = self.param_source_table
        self.postgresql_source_geom = '"{source_table}"."{source_geom}"'.format(source_table=source_table,
                                                                source_geom=self.param_source_geom)

        if self.param_buffer_expression != None and self.param_buffer_expression != '':


            if self.param_buffer_expression.find('"') == 0 and self.param_buffer_expression.find(source_table) != 1:
                self.param_buffer_expression = '"{source_table}".'.format(source_table=source_table) + self.param_buffer_expression

            self.param_buffer_expression = re.sub(' "', ' "mv_{source_table}"."'.format(source_table=source_table), self.param_buffer_expression)

            self.param_buffer_expression = self.qgis_expression_to_postgis(self.param_buffer_expression)    

            
            result = self.manage_layer_subset_strings(self.source_layer, None, self.primary_key_name, True)


            layer_name = self.source_layer.name()
            self.current_materialized_view_name = self.source_layer.id().replace(layer_name, '').replace('-', '_')    
            self.postgresql_source_geom = '"mv_{source_table}"."{source_geom}"'.format(source_table=self.current_materialized_view_name,
                                                                                        source_geom=self.param_source_geom)


            if self.has_to_reproject_source_layer is True:
                self.postgresql_source_geom = 'ST_Transform({postgresql_source_geom}, {source_layer_srid})'.format(postgresql_source_geom=self.postgresql_source_geom,
                                                                                                                    source_layer_srid=self.source_layer_crs_authid.split(':')[1])
                
            self.postgresql_source_geom = 'ST_Buffer({postgresql_source_geom}, "mv_{current_materialized_view_name}"."buffer_value")'.format(postgresql_source_geom=self.postgresql_source_geom,
                                                                                                                                        current_materialized_view_name=self.current_materialized_view_name)
            

        elif self.param_buffer_value != None:

            if self.has_to_reproject_source_layer is True:
                self.postgresql_source_geom = 'ST_Transform({postgresql_source_geom}, {source_layer_srid})'.format(postgresql_source_geom=self.postgresql_source_geom,
                                                                                                                    source_layer_srid=self.source_layer_crs_authid.split(':')[1])
                
            self.postgresql_source_geom = 'ST_Buffer({postgresql_source_geom}, {buffer_value})'.format(postgresql_source_geom=self.postgresql_source_geom,
                                                                                                        buffer_value=self.param_buffer_value)

        

        print("prepare_postgresql_source_geom", self.postgresql_source_geom)     



    def prepare_spatialite_source_geom(self):

        raw_geometries = [feature.geometry() for feature in self.task_parameters["task"]["features"] if feature.hasGeometry()]
        geometries = []

        if self.has_to_reproject_source_layer is True:
            transform = QgsCoordinateTransform(QgsCoordinateReferenceSystem(self.source_crs.authid()), QgsCoordinateReferenceSystem( self.source_layer_crs_authid), self.PROJECT)

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
        param_buffer_distance = None 

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


        if self.param_buffer_value != None or self.param_buffer_expression != None:

            if self.param_buffer_expression != None and self.param_buffer_expression != '':    
                param_buffer_distance = QgsProperty.fromExpression(self.param_buffer_expression)
            else:
                param_buffer_distance = float(self.param_buffer_value)   

            alg_source_layer_params_buffer = {
                'DISSOLVE': True,
                'DISTANCE': param_buffer_distance,
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
        param_combine_operator = ''
        param_old_subset = ''

        if layer.subsetString() != '':
            param_old_subset = layer.subsetString()

        if self.has_combine_operator is True:
            if self.param_other_layers_combine_operator == 'AND':
                param_combine_operator = 'INTERSECT'
            elif self.param_other_layers_combine_operator == 'AND NOT': 
                param_combine_operator = 'EXCEPT'
            elif self.param_other_layers_combine_operator == 'OR':
                param_combine_operator = 'UNION'


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



        if self.param_source_provider_type == 'postgresql' and layer_provider_type == 'postgresql':
            # and (self.param_buffer_expression == None or self.param_buffer_expression == '')    
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
                param_postgis_sub_expression = ' OR '.join(postgis_sub_expression_array)
            else:
                param_postgis_sub_expression = postgis_sub_expression_array[0]

            if QgsExpression(self.expression).isField() is True and self.param_source_old_subset != '':
                sub_expression = self.param_source_old_subset
            else:
                sub_expression = self.expression

            if self.has_combine_operator is True:
                
                
                index = sub_expression.find('FROM "{source_schema}"."{source_table}"'.format(source_schema=self.param_source_schema,
                                                                                            source_table=self.param_source_table
                                                                                            ))
                
                
                results_fields = []
                sub_expression_results_fields = []
                buffer_expression_results_fields = []

                sub_expression_results_fields = re.findall(r'\"{source_table}\"\.[\"a-zA-Z_0_9-]*'.format(source_table=self.param_source_table), sub_expression[index:])

                if self.param_buffer_expression != None and self.param_buffer_expression != '':
                    buffer_expression_results_fields = re.findall(r'\"{source_table}\"\.[\"a-zA-Z_0_9-]*'.format(source_table='sub'), self.postgresql_source_geom)
                    buffer_expression_results_fields = [item.replace('sub',self.param_source_table) for item in buffer_expression_results_fields]

                results_fields = list(set(sub_expression_results_fields + buffer_expression_results_fields))

                geom_column = '"{source_table}"."{source_geom}"'.format(source_table=self.param_source_table,source_geom=self.param_source_geom)
                
                if geom_column not in results_fields:
                    results_fields.append(geom_column)

                if len(results_fields) >= 1:
                    if index > -1:
                        sub_expression = '(SELECT ' + ' , '.join(results_fields) + ' {sub_expression}'.format(sub_expression=sub_expression[index:])
                    else:
                        sub_expression = '(SELECT ' + ' , '.join(results_fields) + ' FROM "{source_schema}"."{source_table}")'.format(source_schema=self.param_source_schema,
                                                                                                                                        source_table=self.param_source_table
                                                                                                                                        )

                index = param_old_subset.find('(SELECT')
                if index > -1:
                    param_old_subset = param_old_subset[index:]
                else:
                    index = param_old_subset.find('(')
                    if index > -1:
                        param_old_subset[index:]



            if QgsExpression(self.expression).isField() is False:
                
                if self.has_combine_operator is True:

                    if self.current_materialized_view_name is not None:
                        param_expression = '(SELECT "{distant_table}"."{distant_primary_key_name}" FROM "{distant_schema}"."{distant_table}" INNER JOIN "{source_subset_schema_name}"."mv_{source_subset_table_name}" ON {postgis_sub_expression})'.format(
                                                                                                                                                                                                                                                distant_primary_key_name=param_distant_primary_key_name,
                                                                                                                                                                                                                                                distant_schema=param_distant_schema,    
                                                                                                                                                                                                                                                distant_table=param_distant_table,
                                                                                                                                                                                                                                                source_subset_schema_name=self.current_materialized_view_schema,
                                                                                                                                                                                                                                                source_subset_table_name=self.current_materialized_view_name,
                                                                                                                                                                                                                                                postgis_sub_expression=param_postgis_sub_expression
                                                                                                                                                                                                                                                )
                    else:
                        param_expression = '(SELECT "{distant_table}"."{distant_primary_key_name}" FROM "{distant_schema}"."{distant_table}" INNER JOIN {source_subset} ON {postgis_sub_expression})'.format(
                                                                                                                                                                                                            distant_primary_key_name=param_distant_primary_key_name,
                                                                                                                                                                                                            distant_schema=param_distant_schema,    
                                                                                                                                                                                                            distant_table=param_distant_table,
                                                                                                                                                                                                            postgis_sub_expression=param_postgis_sub_expression,
                                                                                                                                                                                                            source_subset=sub_expression
                                                                                                                                                                                                            )
                else:
                    if self.current_materialized_view_name is not None:
                        param_expression = '(SELECT "{distant_table}"."{distant_primary_key_name}" FROM "{distant_schema}"."{distant_table}" INNER JOIN "{source_subset_schema_name}"."mv_{source_subset_table_name}" ON {postgis_sub_expression} WHERE {source_subset})'.format(
                                                                                                                                                                                                                                                                            distant_primary_key_name=param_distant_primary_key_name,
                                                                                                                                                                                                                                                                            distant_schema=param_distant_schema,    
                                                                                                                                                                                                                                                                            distant_table=param_distant_table,
                                                                                                                                                                                                                                                                            source_subset_schema_name=self.current_materialized_view_schema,
                                                                                                                                                                                                                                                                            source_subset_table_name=self.current_materialized_view_name,
                                                                                                                                                                                                                                                                            postgis_sub_expression=param_postgis_sub_expression
                                                                                                                                                                                                                                                                            )
                    else:
                        param_expression = '(SELECT "{distant_table}"."{distant_primary_key_name}" FROM "{distant_schema}"."{distant_table}" INNER JOIN "{source_schema}"."{source_table}" ON {postgis_sub_expression} WHERE {source_subset})'.format(
                                                                                                                                                                                                                                                    distant_primary_key_name=param_distant_primary_key_name,
                                                                                                                                                                                                                                                    distant_schema=param_distant_schema,    
                                                                                                                                                                                                                                                    distant_table=param_distant_table,
                                                                                                                                                                                                                                                    source_schema=self.param_source_schema,    
                                                                                                                                                                                                                                                    source_table=self.param_source_table,
                                                                                                                                                                                                                                                    postgis_sub_expression=param_postgis_sub_expression,
                                                                                                                                                                                                                                                    source_subset=sub_expression
                                                                                                                                                                                                                                                    )
            elif QgsExpression(self.expression).isField() is True:

                if self.has_combine_operator is True:
                    if self.current_materialized_view_name is not None:    
                        param_expression = '(SELECT "{distant_table}"."{distant_primary_key_name}" FROM "{distant_schema}"."{distant_table}" INNER JOIN "{source_subset_schema_name}"."mv_{source_subset_table_name}" ON {postgis_sub_expression})'.format(
                                                                                                                                                                                                                                                    distant_primary_key_name=param_distant_primary_key_name,
                                                                                                                                                                                                                                                    distant_schema=param_distant_schema,    
                                                                                                                                                                                                                                                    distant_table=param_distant_table,  
                                                                                                                                                                                                                                                    source_subset_schema_name=self.current_materialized_view_schema,
                                                                                                                                                                                                                                                    source_subset_table_name=self.current_materialized_view_name,
                                                                                                                                                                                                                                                    postgis_sub_expression=param_postgis_sub_expression
                                                                                                                                                                                                                                                    )
                                    
                    else:        
                        param_expression = '(SELECT "{distant_table}"."{distant_primary_key_name}" FROM "{distant_schema}"."{distant_table}" INNER JOIN {source_subset} ON {postgis_sub_expression})'.format(
                                                                                                                                                                                                            distant_primary_key_name=param_distant_primary_key_name,
                                                                                                                                                                                                            distant_schema=param_distant_schema,    
                                                                                                                                                                                                            distant_table=param_distant_table,  
                                                                                                                                                                                                            source_subset=sub_expression,
                                                                                                                                                                                                            postgis_sub_expression=param_postgis_sub_expression
                                                                                                                                                                                                            )
        

                else:
                    if self.current_materialized_view_name is not None:
                        param_expression = '(SELECT "{distant_table}"."{distant_primary_key_name}" FROM "{distant_schema}"."{distant_table}" INNER JOIN "{source_subset_schema_name}"."mv_{source_subset_table_name}" ON {postgis_sub_expression})'.format(
                                                                                                                                                                                                                                                    distant_primary_key_name=param_distant_primary_key_name,
                                                                                                                                                                                                                                                    distant_schema=param_distant_schema,    
                                                                                                                                                                                                                                                    distant_table=param_distant_table,
                                                                                                                                                                                                                                                    source_subset_schema_name=self.current_materialized_view_schema,
                                                                                                                                                                                                                                                    source_subset_table_name=self.current_materialized_view_name,
                                                                                                                                                                                                                                                    postgis_sub_expression=param_postgis_sub_expression
                                                                                                                                                                                                                                                    )
                        
                    else:
                        param_expression = '(SELECT "{distant_table}"."{distant_primary_key_name}" FROM "{distant_schema}"."{distant_table}" INNER JOIN {source_subset} ON {postgis_sub_expression})'.format(
                                                                                                                                                                                                            distant_primary_key_name=param_distant_primary_key_name,
                                                                                                                                                                                                            distant_schema=param_distant_schema,    
                                                                                                                                                                                                            distant_table=param_distant_table,
                                                                                                                                                                                                            source_subset=self.param_source_table,
                                                                                                                                                                                                            postgis_sub_expression=param_postgis_sub_expression
                                                                                                                                                                                                            )
                    
            if param_old_subset != '' and param_combine_operator != '':
                
                expression = '"{distant_primary_key_name}" IN ( {param_old_subset} {param_combine_operator} {expression} )'.format(
                                                                                                                                    distant_primary_key_name=param_distant_primary_key_name,    
                                                                                                                                    param_old_subset=param_old_subset, 
                                                                                                                                    param_combine_operator=param_combine_operator, 
                                                                                                                                    expression=param_expression
                                                                                                                                    )
            else:
                expression = '"{distant_primary_key_name}" IN {expression}'.format(
                                                                                    distant_primary_key_name=param_distant_primary_key_name,                
                                                                                    expression=param_expression
                                                                                    )

            param_expression = param_expression.replace(' " ', ' ')
            expression = expression.replace(' " ', ' ')
            print(param_expression)

            global ENV_VARS
            with open(ENV_VARS["PATH_ABSOLUTE_PROJECT"] + os.sep + 'logs.txt', 'a') as f:
                f.write(param_expression)

            # sql_expression = QgsSQLStatement('SELECT * FROM  "{distant_schema}"."{distant_table}" WHERE {expression}'.format(distant_schema=param_distant_schema,
            #                                                                                                                 distant_table=param_distant_table,
            #                                                                                                                 expression=param_expression),
            #                                                                                                                 True)
            # validation_check = sql_expression.doBasicValidationChecks()
            # print(validation_check)
            # if validation_check[0] is True:

            result = layer.setSubsetString(expression)
            if result is True:
                string_to_replace = 'SELECT "{distant_table}"."{distant_primary_key_name}" FROM'.format(
                                                                                                    distant_table=param_distant_table,
                                                                                                    distant_primary_key_name=param_distant_primary_key_name
                                                                                                    )

                string_replacement = 'SELECT "{distant_table}"."{distant_primary_key_name}", {param_distant_geom_expression} FROM'.format(
                                                                                                                                    distant_table=param_distant_table,
                                                                                                                                    distant_primary_key_name=param_distant_primary_key_name,
                                                                                                                                    param_distant_geom_expression=param_distant_geom_expression
                                                                                                                                    )
                print(string_to_replace)
                print(string_replacement)
                
                param_expression = param_expression.replace(string_to_replace, string_replacement)

                self.manage_layer_subset_strings(layer, param_expression, param_distant_primary_key_name, False)


        if result is False or (self.param_source_provider_type != 'postgresql' or layer_provider_type != 'postgresql'):
            
            layer.removeSelection()
                
            if self.has_combine_operator is False or (self.has_combine_operator is True and self.param_other_layers_combine_operator == 'OR'):
                layer.setSubsetString('')

            if param_has_to_reproject_layer:

                alg_layer_params_reprojectlayer = {
                    'INPUT': layer,
                    'TARGET_CRS': param_layer_crs_authid,
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                }
                self.outputs['alg_layer_params_reprojectlayer'] = processing.run('qgis:reprojectlayer', alg_layer_params_reprojectlayer)
                current_layer = self.outputs['alg_layer_params_reprojectlayer']['OUTPUT']

                alg_params_createspatialindex = {
                    "INPUT": current_layer
                }
                processing.run('qgis:createspatialindex', alg_params_createspatialindex)
            else:
                current_layer = layer
                

            if self.has_combine_operator is True:
                current_layer.selectAll()

                if self.param_other_layers_combine_operator == 'OR':
                    current_layer.setSubsetString(param_old_subset)
                    current_layer.selectAll()
                    current_layer.setSubsetString('')

                    alg_params_select = {
                        'INPUT': current_layer,
                        'INTERSECT': self.ogr_source_geom,
                        'METHOD': 1,
                        'PREDICATE': [int(predicate) for predicate in self.current_predicates.keys()]
                    }
                    processing.run("qgis:selectbylocation", alg_params_select)

                elif self.param_other_layers_combine_operator == 'AND':

                    alg_params_select = {
                        'INPUT': current_layer,
                        'INTERSECT': self.ogr_source_geom,
                        'METHOD': 2,
                        'PREDICATE': [int(predicate) for predicate in self.current_predicates.keys()]
                    }
                    processing.run("qgis:selectbylocation", alg_params_select)
                
                elif self.param_other_layers_combine_operator == 'NOT AND':

                    alg_params_select = {
                        'INPUT': current_layer,
                        'INTERSECT': self.ogr_source_geom,
                        'METHOD': 3,
                        'PREDICATE': [int(predicate) for predicate in self.current_predicates.keys()]
                    }
                    processing.run("qgis:selectbylocation", alg_params_select)

                else:

                    alg_params_select = {
                        'INPUT': current_layer,
                        'INTERSECT': self.ogr_source_geom,
                        'METHOD': 0,
                        'PREDICATE': [int(predicate) for predicate in self.current_predicates.keys()]
                    }
                    processing.run("qgis:selectbylocation", alg_params_select)

            else:

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
            current_layer = None

            if len(features_ids) > 0:
                if param_distant_primary_key_is_numeric == True:
                    param_expression = '"{distant_primary_key_name}" IN '.format(distant_primary_key_name=param_distant_primary_key_name) + "(" + ", ".join(features_ids) + ")"
                else:
                    param_expression = '"{distant_primary_key_name}" IN '.format(distant_primary_key_name=param_distant_primary_key_name) + "(\'" + "\', \'".join(features_ids) + "\')"

                # sql_expression = QgsSQLStatement('SELECT * FROM  "{distant_schema}"."{distant_table}" WHERE {expression}'.format(distant_schema=param_distant_schema,
                #                                                                                                                 distant_table=param_distant_table,
                #                                                                                                                 expression=param_expression),
                #                                                                                                                 True)
                # validation_check = sql_expression.doBasicValidationChecks()
                # print(validation_check)
                # if validation_check[0] is True:

                result = layer.setSubsetString(param_expression)
                if result is True:
                    expression = 'SELECT "{param_distant_table}"."{param_distant_primary_key_name}", {param_distant_geom_expression} FROM "{param_distant_schema}"."{param_distant_table}" WHERE {expression}'.format(
                                                                                                                                                                                                                        param_distant_primary_key_name=param_distant_primary_key_name,
                                                                                                                                                                                                                        param_distant_geom_expression=param_distant_geom_expression,
                                                                                                                                                                                                                        param_distant_schema=param_distant_schema,
                                                                                                                                                                                                                        param_distant_table=param_distant_table,
                                                                                                                                                                                                                        expression=param_expression
                                                                                                                                                                                                                        )  
                    self.manage_layer_subset_strings(layer, expression, param_distant_primary_key_name, False)
                        
        return result



    def execute_filtering(self):
        """Manage the advanced filtering"""
       
        result = self.execute_source_layer_filtering()

        if self.isCanceled():
            return False

        self.setProgress((1 / self.layers_count) * 100)

        if self.task_parameters["filtering"]["has_geometric_predicates"] == True:

            if len(self.task_parameters["filtering"]["geometric_predicates"]) > 0:
                
                source_predicates = self.task_parameters["filtering"]["geometric_predicates"]
                
                for key in source_predicates:
                    index = None
                    if key in self.predicates:
                        index = list(self.predicates).index(key)
                        if index >= 0:
                            self.current_predicates[str(index)] = self.predicates[key]

                
                result = self.manage_distant_layers_geometric_filtering()

                if self.isCanceled() or result is False:
                    return False

        # elif self.is_field_expression != None:
        #     field_idx = -1

        #     for layer_provider_type in self.layers:
        #         for layer, layer_prop in self.layers[layer_provider_type]:
        #             field_idx = layer.fields().indexOf(self.is_field_expression[1])
        #             if field_idx >= 0:
        #                 param_old_subset = ''
        #                 if self.source_layer.subsetString() != '':
        #                     if self.param_other_layers_combine_operator != '':
        #                         if layer.subsetString() != '':
        #                             param_old_subset = layer.subsetString()

        #                 if param_old_subset != '' and self.param_other_layers_combine_operator != '':

        #                     result = self.source_layer.setSubsetString('( {old_subset} ) {combine_operator} {expression}'.format(old_subset=param_old_subset,
        #                                                                                                                         combine_operator=self.param_other_layers_combine_operator,
        #                                                                                                                         expression=self.expression))
        #                 else:
        #                     result = self.source_layer.setSubsetString(self.expression)

        return result 
     

    def execute_unfiltering(self):

        i = 1

        self.manage_layer_subset_strings(self.source_layer, None, self.primary_key_name)
        self.setProgress((i/self.layers_count)*100)

        for layer_provider_type in self.layers:
            for layer, layer_props in self.layers[layer_provider_type]:
                self.manage_layer_subset_strings(layer, None, layer_props["primary_key_name"])
                i += 1
                self.setProgress((i/self.layers_count)*100)
                if self.isCanceled():
                    return False

        return True
    
    def execute_reseting(self):

        i = 1

        self.manage_layer_subset_strings(self.source_layer)
        self.setProgress((i/self.layers_count)*100)

        
        for layer_provider_type in self.layers:
            for layer, layer_props in self.layers[layer_provider_type]:
                self.manage_layer_subset_strings(layer)
                i += 1
                self.setProgress((i/self.layers_count)*100)
                if self.isCanceled():
                    return False


        return True




    def execute_exporting(self):
        """Main function to export the selected layers to the right format with their associated styles"""
        self.coordinateReferenceSystem = QgsCoordinateReferenceSystem()
        layers_to_export = None
        projection_to_export = None
        styles_to_export = None
        datatype_to_export = None
        zip_to_export = None
        result = None
        zip_result = None

        global ENV_VARS
        output_folder_to_export = ENV_VARS["PATH_ABSOLUTE_PROJECT"]

        if self.task_parameters["task"]['EXPORTING']["HAS_LAYERS_TO_EXPORT"] is True:
            if self.task_parameters["task"]["layers"] != None and len(self.task_parameters["task"]["layers"]) > 0:
                layers_to_export = self.task_parameters["task"]["layers"]
            else:
                return False
        else:
            return False

        if self.task_parameters["task"]['EXPORTING']["HAS_PROJECTION_TO_EXPORT"] is True:
            if self.task_parameters["task"]['EXPORTING']["PROJECTION_TO_EXPORT"] != None and self.task_parameters["task"]['EXPORTING']["PROJECTION_TO_EXPORT"] != '':
                self.coordinateReferenceSystem.createFromWkt(self.task_parameters["task"]['EXPORTING']["PROJECTION_TO_EXPORT"])
                projection_to_export = self.coordinateReferenceSystem
     
        if self.task_parameters["task"]['EXPORTING']["HAS_STYLES_TO_EXPORT"] is True:
            if self.task_parameters["task"]['EXPORTING']["STYLES_TO_EXPORT"] != None and self.task_parameters["task"]['EXPORTING']["STYLES_TO_EXPORT"] != '':
                styles_to_export = self.task_parameters["task"]['EXPORTING']["STYLES_TO_EXPORT"].lower()

        if self.task_parameters["task"]['EXPORTING']["HAS_DATATYPE_TO_EXPORT"] is True:
            if self.task_parameters["task"]['EXPORTING']["DATATYPE_TO_EXPORT"] != None and self.task_parameters["task"]['EXPORTING']["DATATYPE_TO_EXPORT"] != '':
                datatype_to_export = self.task_parameters["task"]['EXPORTING']["DATATYPE_TO_EXPORT"]
            else:
                return False
        else:
            return False

        if self.task_parameters["task"]['EXPORTING']["HAS_OUTPUT_FOLDER_TO_EXPORT"] is True:
            if self.task_parameters["task"]['EXPORTING']["OUTPUT_FOLDER_TO_EXPORT"] != None and self.task_parameters["task"]['EXPORTING']["OUTPUT_FOLDER_TO_EXPORT"] != '':
                output_folder_to_export = self.task_parameters["task"]['EXPORTING']["OUTPUT_FOLDER_TO_EXPORT"]

        if self.task_parameters["task"]['EXPORTING']["HAS_ZIP_TO_EXPORT"] is True:
            if self.task_parameters["task"]['EXPORTING']["ZIP_TO_EXPORT"] != None and self.task_parameters["task"]['EXPORTING']["ZIP_TO_EXPORT"] != '':
                zip_to_export = self.task_parameters["task"]['EXPORTING']["ZIP_TO_EXPORT"]

        if layers_to_export != None:
            if datatype_to_export == 'GPKG':
                alg_parameters_export = {
                    'LAYERS': [self.PROJECT.mapLayersByName(layer)[0] for layer in layers_to_export],
                    'OVERWRITE':True,
                    'SAVE_STYLES':self.task_parameters["task"]['EXPORTING']["HAS_STYLES_TO_EXPORT"],
                    'OUTPUT':output_folder_to_export

                    }
                output = processing.run("qgis:package", alg_parameters_export)

            else:
                if os.path.exists(output_folder_to_export):
                    if os.path.isdir(output_folder_to_export) and len(layers_to_export) > 1:
            
                        for layer_name in layers_to_export:
                            layer = self.PROJECT.mapLayersByName(layer_name)[0]
                            if projection_to_export == None:
                                current_projection_to_export = layer.sourceCrs()
                            else:
                                current_projection_to_export = projection_to_export
                            result = QgsVectorFileWriter.writeAsVectorFormat(layer, os.path.normcase(os.path.join(output_folder_to_export , layer_name)), "UTF-8", current_projection_to_export, datatype_to_export)
                            if datatype_to_export != 'XLSX':
                                if self.task_parameters["task"]['EXPORTING']["HAS_STYLES_TO_EXPORT"] is True:
                                    layer.saveNamedStyle(os.path.normcase(os.path.join(output_folder_to_export , layer_name + '.{}'.format(styles_to_export))))
                            if self.isCanceled() or list(result)[0] != 0:
                                return False

                elif len(layers_to_export) == 1:
                    layer_name = layers_to_export[0]
                    layer = self.PROJECT.mapLayersByName(layer_name)[0]
                    if projection_to_export == None:
                        current_projection_to_export = layer.sourceCrs()
                    else:
                        current_projection_to_export = projection_to_export
                    result = QgsVectorFileWriter.writeAsVectorFormat(layer, os.path.normcase(output_folder_to_export), "UTF-8", current_projection_to_export, datatype_to_export)
                    if datatype_to_export != 'XLSX':
                        if self.task_parameters["task"]['EXPORTING']["HAS_STYLES_TO_EXPORT"] is True:
                            layer.saveNamedStyle(os.path.normcase(os.path.join(output_folder_to_export + '.{}'.format(styles_to_export))))

            
            if self.isCanceled():
                return False

            if zip_to_export != None:
                directory, zipfile = os.path.split(output_folder_to_export)
                if os.path.exists(directory) and os.path.isdir(directory):
                    zip_result = self.zipfolder(zip_to_export, output_folder_to_export)
                    if self.isCanceled() or zip_result is False:
                        return False

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


    def manage_layer_subset_strings(self, layer, sql_subset_string=None, distant_primary_key_name=None, custom=False):

        conn = spatialite_connect(self.db_file_path)
        cur = conn.cursor()

        current_seq_order = 0
        last_seq_order = 0
        last_subset_id = None
        layer_name = layer.name()
        name = layer.id().replace(layer_name, '').replace('-', '_')

        cur.execute("""SELECT * FROM fm_subset_history WHERE fk_project = '{fk_project}' AND layer_id = '{layer_id}' ORDER BY seq_order DESC LIMIT 1;""".format(
                                                                                                                                                        fk_project=self.project_uuid,
                                                                                                                                                        layer_id=layer.id()
                                                                                                                                                        )
        )

        results = cur.fetchall()

        if len(results) == 1:
            result = results[0]
            last_subset_id = result[0]
            last_seq_order = result[5]

        if self.task_action == 'filter':
            current_seq_order = last_seq_order + 1

            if custom is False:

                sql_drop_request = 'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."mv_{name}";'.format(schema=self.current_materialized_view_schema,
                                                                                                    name=name)

                sql_create_request = 'CREATE MATERIALIZED VIEW IF NOT EXISTS "{schema}"."mv_{name}" TABLESPACE pg_default AS {sql_subset_string} WITH DATA;'.format(schema=self.current_materialized_view_schema,
                                                                                                                                                                name=name,
                                                                                                                                                                sql_subset_string=sql_subset_string
                                                                                                                                                                )
                



            
            elif custom is True:

                cur.execute("""SELECT * FROM fm_subset_history WHERE fk_project = '{fk_project}' AND layer_id = '{layer_id}' ORDER BY seq_order DESC LIMIT 1;""".format(
                                                                                                                                                    fk_project=self.project_uuid,
                                                                                                                                                    layer_id=layer.id()
                                                                                                                                                    )
                )

                results = cur.fetchall()
                if len(results) == 1:
                    result = results[0]
                    sql_subset_string = result[-1]
                    last_subset_id = result[0]
                    
                self.where_clause = self.param_buffer_expression.replace('CASE', '').replace('END', '').replace('IF', '').replace('ELSE', '').replace('\r', ' ').replace('\n', ' ')
                where_clauses_in_arr = self.where_clause.split('WHEN')

                where_clause_out_arr = []
                where_clause_fields_arr = []
                
                for where_then_clause in where_clauses_in_arr:
                    if len(where_then_clause.split('THEN')) >= 1:
                        where_clause = where_then_clause.split('THEN')[0]
                        where_clause = where_clause.replace('WHEN', ' ')
                        if where_clause.strip() != '':
                            where_clause = where_clause.strip()
                            where_clause_out_arr.append(where_clause)
                            where_clause_fields_arr.append(where_clause.split(' ')[0])


                sql_drop_request = 'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."mv_{name}";'.format(schema=self.current_materialized_view_schema,
                                                                                                    name=name)


                if last_subset_id != None:
                    sql_create_request = 'CREATE MATERIALIZED VIEW IF NOT EXISTS "{schema}"."mv_{name}" TABLESPACE pg_default AS SELECT "{table_source}".geom, "{table_source}"."{primary_key_name}", {where_clause_fields}, {param_buffer_expression} as buffer_value FROM "{schema_source}"."{table_source}" WHERE "{table_source}"."{primary_key_name}" IN (SELECT sub."{primary_key_name}" FROM {source_new_subset} sub ) AND {where_expression} WITH DATA;'.format(
                                                                                                                                                                                                                                                                                                                                                                                                                            schema=self.current_materialized_view_schema,
                                                                                                                                                                                                                                                                                                                                                                                                                            name=name,
                                                                                                                                                                                                                                                                                                                                                                                                                            schema_source=self.param_source_schema,
                                                                                                                                                                                                                                                                                                                                                                                                                            primary_key_name=self.primary_key_name,
                                                                                                                                                                                                                                                                                                                                                                                                                            table_source=self.param_source_table,
                                                                                                                                                                                                                                                                                                                                                                                                                            where_clause_fields= ','.join(where_clause_fields_arr).replace('mv_',''),
                                                                                                                                                                                                                                                                                                                                                                                                                            param_buffer_expression=self.param_buffer_expression.replace('mv_',''),
                                                                                                                                                                                                                                                                                                                                                                                                                            source_new_subset=sql_subset_string,
                                                                                                                                                                                                                                                                                                                                                                                                                            where_expression=' OR '.join(where_clause_out_arr).replace('mv_','')
                                                                                                                                                                                                                                                                                                                                                                                                                        )
                else:
                    sql_create_request = 'CREATE MATERIALIZED VIEW IF NOT EXISTS "{schema}"."mv_{name}" TABLESPACE pg_default AS SELECT "{table_source}".geom, "{table_source}"."{primary_key_name}", {where_clause_fields}, {param_buffer_expression} as buffer_value FROM "{schema_source}"."{table_source}" WHERE "{table_source}"."{primary_key_name}" IN (SELECT sub."{primary_key_name}" FROM {source_new_subset} sub ) AND {where_expression} WITH DATA;'.format(
                                                                                                                                                                                                                                                                                                                                                                                                                schema=self.current_materialized_view_schema,
                                                                                                                                                                                                                                                                                                                                                                                                                name=name,
                                                                                                                                                                                                                                                                                                                                                                                                                schema_source=self.param_source_schema,
                                                                                                                                                                                                                                                                                                                                                                                                                primary_key_name=self.primary_key_name,
                                                                                                                                                                                                                                                                                                                                                                                                                table_source=self.param_source_table,
                                                                                                                                                                                                                                                                                                                                                                                                                where_clause_fields= ','.join(where_clause_fields_arr).replace('mv_',''),
                                                                                                                                                                                                                                                                                                                                                                                                                param_buffer_expression=self.param_buffer_expression.replace('mv_',''),
                                                                                                                                                                                                                                                                                                                                                                                                                source_new_subset=sql_subset_string,
                                                                                                                                                                                                                                                                                                                                                                                                                where_expression=' OR '.join(where_clause_out_arr).replace('mv_','')
                                                                                                                                                                                                                                                                                                                                                                                                            )


            sql_create_request = sql_create_request.replace('\n','').replace('\t','').replace('  ', ' ').strip()                                                        
            print("sql_drop_request", sql_drop_request)
            print("sql_create_request", sql_create_request)

            connexion = self.task_parameters["task"]["options"]["ACTIVE_POSTGRESQL"]

            try:
                with connexion.cursor() as cursor:
                    cursor.execute("SELECT 1")
            except:
                connexion, source_uri = get_datasource_connexion_from_layer(self.source_layer)

            with connexion.cursor() as cursor:
                cursor.execute(sql_drop_request)
                connexion.commit()
                cursor.execute(sql_create_request)
                connexion.commit()

            cur.execute("""INSERT INTO fm_subset_history VALUES('{id}', datetime(), '{fk_project}', '{layer_id}', '{layer_source_id}', {seq_order}, '{subset_string}');""".format(
                                                                                                                                                                                    id=uuid.uuid4(),
                                                                                                                                                                                    fk_project=self.project_uuid,
                                                                                                                                                                                    layer_id=layer.id(),
                                                                                                                                                                                    layer_source_id=self.source_layer.id(),
                                                                                                                                                                                    seq_order=current_seq_order,
                                                                                                                                                                                    subset_string=sql_subset_string.replace("\'","\'\'")
                                                                                                                                                                                    )
            )
            conn.commit()

            layer_subsetString = '"{distant_primary_key_name}" IN (SELECT "mv_{name}"."{distant_primary_key_name}" FROM "{schema}"."mv_{name}")'.format(
                                                                                                                                                        schema=self.current_materialized_view_schema,
                                                                                                                                                        name=name,
                                                                                                                                                        distant_primary_key_name=distant_primary_key_name
                                                                                                                                                        )
            print("layer_subsetString", layer_subsetString)
            layer.setSubsetString(layer_subsetString)


        elif self.task_action == 'reset':
            
                cur.execute("""DELETE FROM fm_subset_history WHERE fk_project = '{fk_project}' AND layer_id = '{layer_id}';""".format(
                                                                                                                                    fk_project=self.project_uuid,
                                                                                                                                    layer_id=layer.id()
                                                                                                                                    )
                )

                conn.commit()

                sql_drop_request = 'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."mv_{name}";'.format(schema=self.current_materialized_view_schema,
                                                                                                    name=name)
                connexion = self.task_parameters["task"]["options"]["ACTIVE_POSTGRESQL"]

                try:
                    with connexion.cursor() as cursor:
                        cursor.execute("SELECT 1")
                except:
                    connexion, source_uri = get_datasource_connexion_from_layer(self.source_layer)

                with connexion.cursor() as cursor:
                    cursor.execute(sql_drop_request)
                    connexion.commit()

                layer.setSubsetString('')

        elif self.task_action == 'unfilter':
            if last_subset_id != None:
                cur.execute("""DELETE FROM fm_subset_history WHERE fk_project = '{fk_project}' AND layer_id = '{layer_id}' AND id = '{last_subset_id}';""".format(
                                                                                                                                                                fk_project=self.project_uuid,
                                                                                                                                                                layer_id=layer.id(),
                                                                                                                                                                last_subset_id=last_subset_id
                                                                                                                                                                )
                )
                conn.commit()

            cur.execute("""SELECT * FROM fm_subset_history WHERE fk_project = '{fk_project}' AND layer_id = '{layer_id}' ORDER BY seq_order DESC LIMIT 1;""".format(
                                                                                                                                                fk_project=self.project_uuid,
                                                                                                                                                layer_id=layer.id()
                                                                                                                                                )
            )

            results = cur.fetchall()
            if len(results) == 1:
                result = results[0]
                sql_subset_string = result[-1]
            

                sql_drop_request = 'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."mv_{name}";'.format(schema=self.current_materialized_view_schema,
                                                                                                name=name)

                sql_create_request = 'CREATE MATERIALIZED VIEW IF NOT EXISTS "{schema}"."mv_{name}" TABLESPACE pg_default AS {sql_subset_string} WITH DATA;'.format(schema=self.current_materialized_view_schema,
                                                                                                                                                                   name=name,
                                                                                                                                                                   sql_subset_string=sql_subset_string
                                                                                                                                                                   )
                 


                sql_create_request = sql_create_request.replace('\n','').replace('\t','').replace('  ', ' ').strip()

                print(sql_create_request)
                connexion = self.task_parameters["task"]["options"]["ACTIVE_POSTGRESQL"]

                try:
                    with connexion.cursor() as cursor:
                        cursor.execute("SELECT 1")
                except:
                    connexion, source_uri = get_datasource_connexion_from_layer(self.source_layer)

                with connexion.cursor() as cursor:
                    cursor.execute(sql_drop_request)
                    connexion.commit()
                    cursor.execute(sql_create_request)
                    connexion.commit()

                layer_subsetString = '"{distant_primary_key_name}" IN (SELECT "mv_{name}"."{distant_primary_key_name}" FROM "{schema}"."mv_{name}")'.format(
                                                                                                                                                            schema=self.current_materialized_view_schema,
                                                                                                                                                            name=name,
                                                                                                                                                            distant_primary_key_name=distant_primary_key_name
                                                                                                                                                            )
                layer.setSubsetString(layer_subsetString)    

            else:
                layer.setSubsetString('')

        cur.close()
        conn.close()
        return True


    def cancel(self):
        QgsMessageLog.logMessage(
            '"{name}" task was canceled'.format(name=self.description()),
            MESSAGE_TASKS_CATEGORIES[self.task_action], Qgis.Info)
        super().cancel()


    def finished(self, result):
        result_action = None
        message_category = MESSAGE_TASKS_CATEGORIES[self.task_action]

        if self.exception is None:
            if result is None:
                iface.messageBar().pushMessage(
                    'Completed with no exception and no result (probably manually canceled by the user).',
                    MESSAGE_TASKS_CATEGORIES[self.task_action], Qgis.Warning)
            else:
                if message_category == 'FilterLayers':

                    if self.task_action == 'filter':
                        result_action = 'Layer(s) filtered'
                    elif self.task_action == 'unfilter':
                        result_action = 'Layer(s) filtered to precedent state'
                    elif self.task_action == 'reset':
                        result_action = 'Layer(s) unfiltered'
                    
                    iface.messageBar().pushMessage(
                        'Filter task : {}'.format(result_action),
                        MESSAGE_TASKS_CATEGORIES[self.task_action], Qgis.Success)

                elif message_category == 'ExportLayers':

                    if self.task_action == 'export':
                        iface.messageBar().pushMessage(
                            'Export task : {}'.format(self.message),
                            MESSAGE_TASKS_CATEGORIES[self.task_action], Qgis.Success)
                        
        else:
            iface.messageBar().pushMessage(
                "Exception: {}".format(self.exception),
                MESSAGE_TASKS_CATEGORIES[self.task_action], Qgis.Critical)
            raise self.exception





class LayersManagementEngineTask(QgsTask):
    """Main QgsTask class which filter and unfilter data"""

    resultingLayers = pyqtSignal(dict)
    savingLayerVariable = pyqtSignal(QgsVectorLayer, str, object, type)
    removingLayerVariable = pyqtSignal(QgsVectorLayer, str)

    def __init__(self, description, task_action, task_parameters):

        QgsTask.__init__(self, description, QgsTask.CanCancel)


        self.exception = None
        self.task_action = task_action
        self.task_parameters = task_parameters
        self.CONFIG_DATA = None
        self.db_file_path = None
        self.project_uuid = None

        self.layers = None
        self.project_layers = None
        self.layer_properties = None
        self.layer_all_properties_flag = False
        self.outputs = {}
        self.message = None

        self.json_template_layer_infos = '{"layer_geometry_type":"%s","layer_name":"%s","layer_id":"%s","layer_schema":"%s","is_already_subset":false,"layer_provider_type":"%s","layer_crs_authid":"%s","primary_key_name":"%s","primary_key_idx":%s,"primary_key_type":"%s","geometry_field":"%s","primary_key_is_numeric":%s,"is_current_layer":false }'
        self.json_template_layer_exploring = '{"is_changing_all_layer_properties":true,"is_tracking":false,"is_selecting":false,"is_linking":false,"single_selection_expression":"%s","multiple_selection_expression":"%s","custom_selection_expression":"%s" }'
        self.json_template_layer_filtering = '{"has_layers_to_filter":false,"layers_to_filter":[],"has_combine_operator":false,"source_layer_combine_operator":"","other_layers_combine_operator":"","has_geometric_predicates":false,"geometric_predicates":[],"has_buffer_value":false,"buffer_value":0.0,"buffer_value_property":false,"buffer_value_expression":"","has_buffer_type":false,"buffer_type":"" }'
        
        global ENV_VARS
        self.PROJECT = ENV_VARS["PROJECT"]


    def run(self):
        try:    
            result = False

            self.CONFIG_DATA = self.task_parameters["task"]["config_data"]
            self.db_file_path = self.task_parameters["task"]["db_file_path"]
            self.project_uuid = self.task_parameters["task"]["project_uuid"]

            if self.task_action == 'add_layers':

                self.layers = self.task_parameters["task"]["layers"]
                self.project_layers = self.task_parameters["task"]["project_layers"]
                self.reset_all = self.task_parameters["task"]["reset_all_layers_variables_flag"]
                result = self.manage_project_layers()
                if self.isCanceled() or result is False:
                    return False

            elif self.task_action == 'remove_layers':

                self.layers = self.task_parameters["task"]["layers"]
                self.project_layers = self.task_parameters["task"]["project_layers"]
                self.reset_all = self.task_parameters["task"]["reset_all_layers_variables_flag"]
                result = self.manage_project_layers()
                if self.isCanceled() or result is False:
                    return False


            return True
    
        except Exception as e:
            self.exception = e
            print(self.exception)
            return False




    def manage_project_layers(self):
        result = False

        if self.reset_all is True:
            result = self.remove_variables_from_all_layers()

            if self.isCanceled() or result is False:
                return False
            
        for layer in self.layers:
            if self.task_action == 'add_layers':
                if isinstance(layer, QgsVectorLayer):
                    if layer.id() not in self.project_layers.keys():
                        result = self.add_project_layer(layer)
            elif self.task_action == 'remove_layers':
                if isinstance(layer, QgsVectorLayer):
                    if layer.id() in self.project_layers.keys():
                        result = self.remove_project_layer(layer)

            if self.isCanceled() or result is False:
                return False

        self.project_layers = dict(OrderedDict(sorted(self.project_layers.items(), key = lambda layer: (getitem(layer[1]['infos'], 'layer_geometry_type'), getitem(layer[1]['infos'], 'layer_name')))))

        return True
    

    def add_project_layer(self, layer):

        result = False
        layer_variables = {}

        if isinstance(layer, QgsVectorLayer) and layer.isSpatial():

            spatialite_results = self.select_properties_from_spatialite(layer.id())
            if len(spatialite_results) > 0 and len(spatialite_results) == self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["LAYERS"]["LAYER_PROPERTIES_COUNT"]:
                existing_layer_variables = {}
                for key in ("infos", "exploring", "filtering"):
                    existing_layer_variables[key] = {}
                for property in spatialite_results:

                    if property[0] in existing_layer_variables:
                        value_typped, type_returned = self.return_typped_value(property[2].replace("\'\'", "\'"), 'load')
                        existing_layer_variables[property[0]][property[1]] = value_typped
                        variable_key = "filterMate_{key_group}_{key}".format(key_group=property[0], key=property[1])
                        QgsExpressionContextUtils.setLayerVariable(layer, variable_key, value_typped)

                layer_variables["infos"] = existing_layer_variables["infos"]
                layer_variables["exploring"] = existing_layer_variables["exploring"]
                layer_variables["filtering"] = existing_layer_variables["filtering"]

            else:
                new_layer_variables = {}
                result = self.search_primary_key_from_layer(layer)
                if self.isCanceled() or result is False:
                    return False
                
                if isinstance(result, tuple) and len(list(result)) == 4:
                    primary_key_name = result[0]
                    primary_key_idx = result[1]
                    primary_key_type = result[2]
                    primary_key_is_numeric = result[3]
                else:
                    return False

                source_schema = 'NULL'
                geometry_field = 'NULL'

                layer_variables = {}
                layer_props = {}

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
    
                
                for key_group in ("infos", "exploring", "filtering"):
                    for key in new_layer_variables[key_group]:
                        variable_key = "filterMate_{key_group}_{key}".format(key_group=key_group, key=key)
                        value_typped, type_returned = self.return_typped_value(new_layer_variables[key_group][key], 'save')
                        if type_returned in (list, dict):
                            value_typped = json.dumps(value_typped)
                        QgsExpressionContextUtils.setLayerVariable(layer, variable_key, value_typped)

                layer_variables["infos"] = new_layer_variables["infos"]
                layer_variables["exploring"] = new_layer_variables["exploring"]
                layer_variables["filtering"] = new_layer_variables["filtering"]  

            
            if self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["LAYERS"]["LAYER_PROPERTIES_COUNT"] == 0:
                properties_count = len(layer_variables["infos"]) + len(layer_variables["exploring"]) + len(layer_variables["filtering"])
                self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["LAYERS"]["LAYER_PROPERTIES_COUNT"] = properties_count


            layer_props = {"infos": layer_variables["infos"], "exploring": layer_variables["exploring"], "filtering": layer_variables["filtering"]}
            layer_props["infos"]["layer_id"] = layer.id()

            self.insert_properties_to_spatialite(layer.id(), layer_props)

            if layer_props["infos"]["layer_provider_type"] == 'postgresql':
                try:
                    self.create_spatial_index_for_postgresql_layer(layer, layer_props)
                except:
                    pass
                
            else:
                self.create_spatial_index_for_layer(layer)
                
            self.project_layers[layer.id()] = layer_props
            return True


    def remove_project_layer(self, layer_id):

        if isinstance(layer_id, str):

            self.save_variables_from_layer(layer_id)    
            self.save_style_from_layer_id(layer_id)

            del self.project_layers[layer_id]

            return True

        

    def search_primary_key_from_layer(self, layer):
        """For each layer we search the primary key"""

        primary_key_index = layer.primaryKeyAttributes()
        if len(primary_key_index) > 0:
            for field_id in primary_key_index:
                if self.isCanceled():
                    return False
                if len(layer.uniqueValues(field_id)) == layer.featureCount():
                    field = layer.fields()[field_id]
                    return (field.name(), field_id, field.typeName(), field.isNumeric())
        else:
            for field in layer.fields():
                if self.isCanceled():
                    return False
                if 'id' in str(field.name()).lower():
                    if len(layer.uniqueValues(layer.fields().indexOf(field.name()))) == layer.featureCount():
                        return (field.name(), layer.fields().indexFromName(field.name()), field.typeName(), field.isNumeric())
                    
            for field in layer.fields():
                if self.isCanceled():
                    return False
                if len(layer.uniqueValues(layer.fields().indexOf(field.name()))) == layer.featureCount():
                    return (field.name(), layer.fields().indexFromName(field.name()), field.typeName(), field.isNumeric())
                
        new_field = QgsField('virtual_id', QVariant.LongLong)
        layer.addExpressionField('@row_number', new_field)

        return ('virtual_id', layer.fields().indexFromName('virtual_id'), new_field.typeName(), True)


    def create_spatial_index_for_postgresql_layer(self, layer, layer_props):       


        if layer != None or layer_props != None:

            schema = layer_props["infos"]["layer_schema"]
            table = layer_props["infos"]["layer_name"]
            geometry_field = layer_props["infos"]["geometry_field"]
            primary_key_name = layer_props["infos"]["primary_key_name"]

            connexion, source_uri = get_datasource_connexion_from_layer(layer)

            sql_statement = 'CREATE INDEX IF NOT EXISTS {schema}_{table}_{geometry_field}_idx ON "{schema}"."{table}" USING GIST ({geometry_field});'.format(schema=schema,
                                                                                                                                                            table=table,
                                                                                                                                                            geometry_field=geometry_field)
            sql_statement = sql_statement + 'CREATE UNIQUE INDEX IF NOT EXISTS {schema}_{table}_{primary_key_name}_idx ON "{schema}"."{table}" ({primary_key_name});'.format(schema=schema,
                                                                                                                                                                                table=table,
                                                                                                                                                                                primary_key_name=primary_key_name)
            sql_statement = sql_statement + 'ALTER TABLE "{schema}"."{table}" CLUSTER ON {schema}_{table}_{geometry_field}_idx;'.format(schema=schema,
                                                                                                                                table=table,
                                                                                                                                geometry_field=geometry_field)
            
            sql_statement = sql_statement + 'ANALYZE "{schema}"."{table}";'.format(schema=schema,
                                                                                    table=table)


            with connexion.cursor() as cursor:
                cursor.execute(sql_statement)

            if self.isCanceled():
                return False
            
            return True

        else:
            return False



    def create_spatial_index_for_layer(self, layer):    

        alg_params_createspatialindex = {
            "INPUT": layer
        }
        processing.run('qgis:createspatialindex', alg_params_createspatialindex)
        if self.isCanceled():
            return False
    
        return True


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
                        variable_key = "filterMate_{key_group}_{key}".format(key_group=key_group, key=key)
                        QgsExpressionContextUtils.setLayerVariable(layer, key_group + '_' +  key, value_typped)
                        cur.execute("""INSERT INTO fm_project_layers_properties 
                                        VALUES('{id}', datetime(), '{project_id}', '{layer_id}', '{meta_type}', '{meta_key}', '{meta_value}');""".format(
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
                            variable_key = "filterMate_{key_group}_{key}".format(key_group=layer_property[0], key=layer_property[1])
                            QgsExpressionContextUtils.setLayerVariable(layer, variable_key, value_typped)
                            cur.execute("""INSERT INTO fm_project_layers_properties 
                                            VALUES('{id}', datetime(), '{project_id}', '{layer_id}', '{meta_type}', '{meta_key}', '{meta_value}');""".format(
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
                            variable_key = "filterMate_{key_group}_{key}".format(key_group=layer_property[0], key=layer_property[1])
                            QgsExpressionContextUtils.setLayerVariable(layer, variable_key, '')

            cur.close()
            conn.close()



    def save_style_from_layer_id(self, layer_id):


        if layer_id in self.project_layers.keys():

            layers = [layer for layer in self.PROJECT.mapLayersByName(self.project_layers[layer_id]["infos"]["layer_name"]) if layer.id() == layer_id]
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

        return True


    def remove_variables_from_all_layers(self):

        if len(self.project_layers) == 0:
            if len(self.layers) > 0:

                for layer_obj in self.layers:

                    if isinstance(layer_obj, tuple) and len(list(layer_obj)) == 3:
                        layer = layer_obj[0]
                    elif isinstance(layer_obj, QgsVectorLayer):
                        layer = layer_obj

                    result_layers = [result_layer for result_layer in self.PROJECT.mapLayersByName(layer.name())]
                    if len(result_layers) > 0:
                        for result_layer in result_layers:
                            QgsExpressionContextUtils.setLayerVariables(result_layer, {})
                            if self.isCanceled():
                                return False
                            
                    if self.isCanceled():
                        return False
            else:
                return False


        else:
            for layer_id in self.project_layers:

                result_layers = [layer for layer in self.PROJECT.mapLayersByName(self.project_layers[layer_id]["infos"]["layer_name"]) if layer.id() == layer_id]
                if len(result_layers) > 0:

                    result_layer = result_layers[0]
                    QgsExpressionContextUtils.setLayerVariables(result_layer, {})

                if self.isCanceled():
                    return False

        return True

    def select_properties_from_spatialite(self, layer_id):

        results = []
        
        conn = spatialite_connect(self.db_file_path)
        cur = conn.cursor()

        cur.execute("""SELECT meta_type, meta_key, meta_value FROM fm_project_layers_properties  
                        WHERE fk_project = '{project_id}' and layer_id = '{layer_id}';""".format(
                                                                                            project_id=self.project_uuid,
                                                                                            layer_id=layer_id                    
                                                                                            )
        )
        results = cur.fetchall()   

        conn.commit()
        cur.close()
        conn.close()

        return results
    

    def insert_properties_to_spatialite(self, layer_id, layer_props):

        conn = spatialite_connect(self.db_file_path)
        cur = conn.cursor()

        for key_group in layer_props:
            for key in layer_props[key_group]:

                value_typped, type_returned = self.return_typped_value(layer_props[key_group][key], 'save')
                if type_returned in (list, dict):
                    value_typped = json.dumps(value_typped)
        
                cur.execute("""INSERT INTO fm_project_layers_properties 
                                VALUES('{id}', datetime(), '{project_id}', '{layer_id}', '{meta_type}', '{meta_key}', '{meta_value}');""".format(
                                                                                                                                        id=uuid.uuid4(),
                                                                                                                                        project_id=self.project_uuid,
                                                                                                                                        layer_id=layer_id,
                                                                                                                                        meta_type=key_group,
                                                                                                                                        meta_key=key,
                                                                                                                                        meta_value=value_typped.replace("\'","\'\'") if type_returned in (str, dict, list) else value_typped
                                                                                                                                        )
                )
                conn.commit()
  
        cur.close()
        conn.close()



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
            if str(value_as_string).upper() == 'FALSE':
                value_typped = False
            elif str(value_as_string).upper() == 'TRUE':
                value_typped = True
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


    def cancel(self):
        QgsMessageLog.logMessage(
            '"{name}" task was canceled'.format(name=self.description()),
            MESSAGE_TASKS_CATEGORIES[self.task_action], Qgis.Info)
        super().cancel()


    def finished(self, result):
        result_action = None
        message_category = MESSAGE_TASKS_CATEGORIES[self.task_action]

        if self.exception is None:
            if result is None:
                iface.messageBar().pushMessage(
                    'Completed with no exception and no result (probably manually canceled by the user).',
                    MESSAGE_TASKS_CATEGORIES[self.task_action], Qgis.Warning)
            else:
                if message_category == 'ManageLayers':
                    
                    
                    if self.task_action == 'add_layers':
                        if len(self.layers) == len(list(self.project_layers.keys())):
                            result_action = '{} layer(s) added'.format(str(len(list(self.project_layers.keys()))))
                        else:
                            result_action = '{} layer(s) added'.format(str(len(self.layers) - len(list(self.project_layers.keys()))))

                    elif self.task_action == 'remove_layers':
                        result_action = '{} layer(s) removed'.format(str(len(list(self.project_layers.keys())) - len(self.layers)))

                    iface.messageBar().pushMessage(
                        'Layers list has been updated : {}'.format(result_action),
                        MESSAGE_TASKS_CATEGORIES[self.task_action], Qgis.Success)
                        

                elif message_category == 'ManageLayersProperties':

                    if self.layer_all_properties_flag is True:    

                        if self.task_action == 'save_layer_variable':
                            result_action = 'All properties saved for {} layer'.format(self.layer_id)
                        elif self.task_action == 'remove_layer_variable':
                            result_action = 'All properties removed for {} layer'.format(self.layer_id)

                        iface.messageBar().pushMessage(
                            'Layers list has been updated : {}'.format(result_action),
                            MESSAGE_TASKS_CATEGORIES[self.task_action], Qgis.Success)
                    
                self.resultingLayers.emit(self.project_layers)
        else:
            iface.messageBar().pushMessage(
                "Exception: {}".format(self.exception),
                MESSAGE_TASKS_CATEGORIES[self.task_action], Qgis.Critical)
            raise self.exception

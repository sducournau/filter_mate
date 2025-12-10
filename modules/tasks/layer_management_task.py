"""
Layer Management Task

Extracted from appTasks.py during Phase 3b (Dec 2025).

This module contains the LayersManagementEngineTask class which handles:
- Adding and removing layers from FilterMate project tracking
- Managing layer properties and variables in Spatialite database
- Creating spatial indexes for layers
- Detecting and migrating legacy layer metadata
- Saving/removing layer styles

Dependencies:
- QgsTask for asynchronous execution
- Spatialite database for persistent layer properties
- QGIS layer variables for runtime property access
"""

from qgis.core import (
    Qgis,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsFeatureSource,
    QgsField,
    QgsMessageLog,
    QgsProject,
    QgsTask,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import pyqtSignal, QMetaType
from qgis.utils import iface
from qgis import processing
import logging
import os
import json
import uuid
from collections import OrderedDict
import re

# Import logging configuration
from ..logging_config import setup_logger, safe_log
from ...config.config import ENV_VARS

# Setup logger
logger = setup_logger(
    'FilterMate.LayerManagementTask',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_tasks.log'),
    level=logging.INFO
)

# Import constants
from ..constants import (
    PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR
)

# Import utilities
from ..appUtils import (
    get_source_table_name,
    get_datasource_connexion_from_layer,
    detect_layer_provider_type,
    geometry_type_to_string
)

# Import task utilities
from .task_utils import spatialite_connect, sqlite_execute_with_retry, MESSAGE_TASKS_CATEGORIES

# Conditional import for PostgreSQL support
try:
    import psycopg2
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False
    psycopg2 = None


class LayersManagementEngineTask(QgsTask):
    """
    QgsTask for managing layer tracking, properties, and spatial indexes.
    
    This task handles the asynchronous addition and removal of layers from
    FilterMate's tracking system, including:
    
    - Detecting layer metadata (provider type, geometry field, primary key)
    - Storing layer properties in Spatialite database
    - Setting QGIS layer variables for runtime access
    - Creating spatial indexes (PostgreSQL GIST, QGIS spatial index)
    - Migrating legacy property formats
    - Saving/removing layer styles
    
    Signals:
        resultingLayers (dict): Emitted on completion with updated project layers
        savingLayerVariable (QgsVectorLayer, str, object, type): Emitted when saving a variable
        removingLayerVariable (QgsVectorLayer, str): Emitted when removing a variable
    """
    
    resultingLayers = pyqtSignal(dict)
    savingLayerVariable = pyqtSignal(QgsVectorLayer, str, object, type)
    removingLayerVariable = pyqtSignal(QgsVectorLayer, str)

    def __init__(self, description, task_action, task_parameters):
        """
        Initialize layer management task.
        
        Args:
            description (str): Task description for UI
            task_action (str): Action to perform ('add_layers', 'remove_layers')
            task_parameters (dict): Task configuration with keys:
                - task['config_data']: Configuration data
                - task['db_file_path']: Path to Spatialite database
                - task['project_uuid']: Project UUID
                - task['layers']: List of layers to process
                - task['project_layers']: Current project layers dict
                - task['reset_all_layers_variables_flag']: Whether to reset all variables
        """
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

        # JSON templates for layer properties
        self.json_template_layer_infos = '{"layer_geometry_type":"%s","layer_name":"%s","layer_table_name":"%s","layer_id":"%s","layer_schema":"%s","is_already_subset":false,"layer_provider_type":"%s","layer_crs_authid":"%s","primary_key_name":"%s","primary_key_idx":%s,"primary_key_type":"%s","layer_geometry_field":"%s","primary_key_is_numeric":%s,"is_current_layer":false }'
        self.json_template_layer_exploring = '{"is_changing_all_layer_properties":true,"is_tracking":false,"is_selecting":false,"is_linking":false,"current_exploring_groupbox":"single_selection","single_selection_expression":"%s","multiple_selection_expression":"%s","custom_selection_expression":"%s" }'
        self.json_template_layer_filtering = '{"has_layers_to_filter":false,"layers_to_filter":[],"has_combine_operator":false,"source_layer_combine_operator":"","other_layers_combine_operator":"","has_geometric_predicates":false,"geometric_predicates":[],"has_buffer_value":false,"buffer_value":0.0,"buffer_value_property":false,"buffer_value_expression":"","has_buffer_type":false,"buffer_type":"Round" }'
        
        global ENV_VARS
        self.PROJECT = ENV_VARS["PROJECT"]

    
    def _ensure_db_directory_exists(self):
        """
        Ensure the database directory exists before connecting.
        
        Raises:
            OSError: If directory cannot be created
            ValueError: If db_file_path is invalid
        """
        if not self.db_file_path:
            raise ValueError("db_file_path is not set")
        
        # Normalize path to handle any separator inconsistencies
        normalized_path = os.path.normpath(self.db_file_path)
        db_dir = os.path.dirname(normalized_path)
        
        if not db_dir:
            raise ValueError(f"Invalid database path: {self.db_file_path}")
        
        if os.path.exists(db_dir):
            # Directory already exists, check if it's writable
            if not os.access(db_dir, os.W_OK):
                raise OSError(f"Database directory exists but is not writable: {db_dir}")
            logger.debug(f"Database directory exists: {db_dir}")
        else:
            # Validate parent directories before attempting creation
            parent_dir = os.path.dirname(db_dir)
            
            if not parent_dir or not os.path.exists(parent_dir):
                error_msg = (
                    f"Cannot create database directory '{db_dir}': "
                    f"parent directory '{parent_dir}' does not exist. "
                    f"Original path: {self.db_file_path}"
                )
                logger.error(error_msg)
                raise OSError(error_msg)
            
            if not os.access(parent_dir, os.W_OK):
                error_msg = (
                    f"Cannot create database directory '{db_dir}': "
                    f"parent directory '{parent_dir}' is not writable. "
                    f"Original path: {self.db_file_path}"
                )
                logger.error(error_msg)
                raise OSError(error_msg)
            
            # Create directory with all intermediate directories
            try:
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"Created database directory: {db_dir}")
            except OSError as e:
                error_msg = (
                    f"Failed to create database directory '{db_dir}': {e}. "
                    f"Original path: {self.db_file_path}, "
                    f"Normalized: {normalized_path}"
                )
                logger.error(error_msg)
                raise OSError(error_msg) from e
    
    
    def _safe_spatialite_connect(self):
        """
        Safely connect to Spatialite database, ensuring directory exists.
        
        Returns:
            sqlite3.Connection: Database connection
            
        Raises:
            OSError: If directory cannot be created
            sqlite3.OperationalError: If database cannot be opened
        """
        self._ensure_db_directory_exists()
        
        try:
            conn = spatialite_connect(self.db_file_path)
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to Spatialite database at {self.db_file_path}: {e}")
            raise


    def run(self):
        """
        Execute the layer management task.
        
        Returns:
            bool: True if successful, False otherwise
        """
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
            # Provide detailed error information for database issues
            error_msg = f'LayerManagementEngineTask run() failed: {e}'
            if 'unable to open database file' in str(e):
                error_msg += f'\nDatabase path: {self.db_file_path}'
                if self.db_file_path:
                    db_dir = os.path.dirname(self.db_file_path)
                    error_msg += f'\nDatabase directory: {db_dir}'
                    error_msg += f'\nDirectory exists: {os.path.exists(db_dir) if db_dir else "N/A"}'
            safe_log(logger, logging.ERROR, error_msg, exc_info=True)
            return False


    def manage_project_layers(self):
        """
        Manage addition/removal of layers to/from project tracking.
        
        Returns:
            bool: True if successful, False otherwise
        """
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

        # Sort layers once after all operations (performance optimization)
        self.project_layers = dict(OrderedDict(sorted(
            self.project_layers.items(), 
            key=lambda layer: (
                layer[1]['infos'].get('layer_geometry_type', 'Unknown'),
                layer[1]['infos'].get('layer_name', '')
            )
        )))
        
        logger.info(f"manage_project_layers completed successfully: {len(self.project_layers)} layers in project_layers")
        return True
    
    def _load_existing_layer_properties(self, layer):
        """
        Load existing layer properties from Spatialite database.
        
        Args:
            layer (QgsVectorLayer): Layer to load properties for
            
        Returns:
            dict: Dictionary with 'infos', 'exploring', 'filtering' keys, or empty dict if not found
        """
        spatialite_results = self.select_properties_from_spatialite(layer.id())
        expected_count = self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["LAYERS"]["LAYER_PROPERTIES_COUNT"]
        
        if not spatialite_results:
            return {}
        
        existing_layer_variables = {
            "infos": {},
            "exploring": {},
            "filtering": {}
        }
        
        for property in spatialite_results:
            if property[0] in existing_layer_variables:
                value_typped, type_returned = self.return_typped_value(
                    property[2].replace("\'\'", "\'"), 
                    'load'
                )
                existing_layer_variables[property[0]][property[1]] = value_typped
                
                # Set as QGIS layer variable
                variable_key = f"filterMate_{property[0]}_{property[1]}"
                QgsExpressionContextUtils.setLayerVariable(layer, variable_key, value_typped)
        
        # If property count has changed, update it
        actual_count = (
            len(existing_layer_variables.get("infos", {})) +
            len(existing_layer_variables.get("exploring", {})) +
            len(existing_layer_variables.get("filtering", {}))
        )
        if actual_count > 0 and actual_count != expected_count:
            logger.debug(f"Property count changed from {expected_count} to {actual_count} for layer {layer.id()}")
            self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["LAYERS"]["LAYER_PROPERTIES_COUNT"] = actual_count
        
        return existing_layer_variables

    def _migrate_legacy_geometry_field(self, layer_variables, layer):
        """
        Migrate old 'geometry_field' key to 'layer_geometry_field' and add missing properties.
        
        Args:
            layer_variables (dict): Dictionary with layer properties
            layer (QgsVectorLayer): Layer being processed
        """
        infos = layer_variables.get("infos", {})
        
        # Migrate geometry_field to layer_geometry_field
        if "geometry_field" in infos and "layer_geometry_field" not in infos:
            infos["layer_geometry_field"] = infos["geometry_field"]
            del infos["geometry_field"]
            logger.info(f"Migrated geometry_field to layer_geometry_field for layer {layer.id()}")
            
            # Update database with new key name
            try:
                conn = self._safe_spatialite_connect()
                cur = conn.cursor()
                cur.execute(
                    """UPDATE fm_project_layers_properties 
                       SET meta_key = 'layer_geometry_field'
                       WHERE fk_project = ? AND layer_id = ? 
                       AND meta_type = 'infos' AND meta_key = 'geometry_field'""",
                    (str(self.project_uuid), layer.id())
                )
                conn.commit()
                cur.close()
                conn.close()
                logger.debug(f"Updated database for layer {layer.id()}")
            except Exception as e:
                logger.warning(f"Could not update database for migration: {e}")
        
        # Add layer_table_name if missing
        if "layer_table_name" not in infos:
            source_table_name = get_source_table_name(layer)
            infos["layer_table_name"] = source_table_name
            logger.info(f"Added layer_table_name='{source_table_name}' for layer {layer.id()}")
            
            try:
                conn = self._safe_spatialite_connect()
                cur = conn.cursor()
                cur.execute(
                    """INSERT INTO fm_project_layers_properties 
                       (fk_project, layer_id, meta_type, meta_key, meta_value)
                       VALUES (?, ?, 'infos', 'layer_table_name', ?)""",
                    (str(self.project_uuid), layer.id(), source_table_name)
                )
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                logger.warning(f"Could not add layer_table_name to database: {e}")
        
        # Add layer_provider_type if missing
        if "layer_provider_type" not in infos:
            layer_provider_type = detect_layer_provider_type(layer)
            infos["layer_provider_type"] = layer_provider_type
            logger.info(f"Added layer_provider_type='{layer_provider_type}' for layer {layer.id()}")
            
            try:
                conn = self._safe_spatialite_connect()
                cur = conn.cursor()
                cur.execute(
                    """INSERT INTO fm_project_layers_properties 
                       (fk_project, layer_id, meta_type, meta_key, meta_value)
                       VALUES (?, ?, 'infos', 'layer_provider_type', ?)""",
                    (str(self.project_uuid), layer.id(), layer_provider_type)
                )
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                logger.warning(f"Could not add layer_provider_type to database: {e}")
            
            # Set as QGIS layer variable
            QgsExpressionContextUtils.setLayerVariable(layer, "filterMate_infos_layer_table_name", infos.get("layer_table_name", ""))
        
        # Add layer_geometry_type if missing
        if "layer_geometry_type" not in infos:
            layer_geometry_type = geometry_type_to_string(layer)
            infos["layer_geometry_type"] = layer_geometry_type
            logger.info(f"Added layer_geometry_type='{layer_geometry_type}' for layer {layer.id()}")
            
            try:
                conn = self._safe_spatialite_connect()
                cur = conn.cursor()
                cur.execute(
                    """INSERT INTO fm_project_layers_properties 
                       (fk_project, layer_id, meta_type, meta_key, meta_value)
                       VALUES (?, ?, 'infos', 'layer_geometry_type', ?)""",
                    (str(self.project_uuid), layer.id(), layer_geometry_type)
                )
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                logger.warning(f"Could not add layer_geometry_type to database: {e}")

    def _detect_layer_metadata(self, layer, layer_provider_type):
        """
        Detect layer-specific metadata based on provider.
        
        Args:
            layer (QgsVectorLayer): Layer to analyze
            layer_provider_type (str): Provider type constant
            
        Returns:
            tuple: (source_schema, geometry_field)
        """
        source_schema = 'NULL'
        geometry_field = 'NULL'
        
        if layer_provider_type == PROVIDER_POSTGRES:
            layer_source = layer.source()
            
            # Extract schema from connection string
            regexp_match_schema = re.search('(?<=table=\\")[a-zA-Z0-9_-]*(?=\\".)', layer_source)
            if regexp_match_schema:
                source_schema = regexp_match_schema.group()
            
            # Extract geometry field from connection string
            regexp_match_geom = re.search('(?<=\\()[a-zA-Z0-9_-]*(?=\\))', layer_source)
            if regexp_match_geom:
                geometry_field = regexp_match_geom.group()
        
        elif layer_provider_type in [PROVIDER_SPATIALITE, PROVIDER_OGR]:
            try:
                geom_col = layer.dataProvider().geometryColumn()
                if geom_col:
                    geometry_field = geom_col
                else:
                    geometry_field = 'geom' if layer_provider_type == PROVIDER_OGR else 'geometry'
            except AttributeError:
                geometry_field = 'geom' if layer_provider_type == PROVIDER_OGR else 'geometry'
        
        return source_schema, geometry_field

    def _build_new_layer_properties(self, layer, primary_key_result):
        """
        Build property dictionaries for a new layer.
        
        Args:
            layer (QgsVectorLayer): Layer to build properties for
            primary_key_result (tuple): Tuple from search_primary_key_from_layer
            
        Returns:
            dict: Dictionary with 'infos', 'exploring', 'filtering' keys
        """
        primary_key_name, primary_key_idx, primary_key_type, primary_key_is_numeric = primary_key_result
        
        # Detect provider type and metadata
        layer_provider_type = detect_layer_provider_type(layer)
        source_schema, geometry_field = self._detect_layer_metadata(layer, layer_provider_type)
        
        # Convert geometry type
        layer_geometry_type = geometry_type_to_string(layer)
        
        # Get actual source table name
        source_table_name = get_source_table_name(layer)
        
        # Build properties from JSON templates
        new_layer_variables = {}
        new_layer_variables["infos"] = json.loads(
            self.json_template_layer_infos % (
                layer_geometry_type, 
                layer.name(),
                source_table_name,
                layer.id(), 
                source_schema, 
                layer_provider_type, 
                layer.sourceCrs().authid(), 
                primary_key_name, 
                primary_key_idx, 
                primary_key_type, 
                geometry_field, 
                str(primary_key_is_numeric).lower()
            )
        )
        new_layer_variables["exploring"] = json.loads(
            self.json_template_layer_exploring % (
                str(primary_key_name),
                str(primary_key_name),
                str(primary_key_name)
            )
        )
        new_layer_variables["filtering"] = json.loads(self.json_template_layer_filtering)
        
        return new_layer_variables

    def _set_layer_variables(self, layer, layer_variables):
        """
        Set QGIS layer variables from property dictionary.
        
        Args:
            layer (QgsVectorLayer): Layer to set variables on
            layer_variables (dict): Dictionary with 'infos', 'exploring', 'filtering' keys
        """
        for key_group in ("infos", "exploring", "filtering"):
            for key in layer_variables[key_group]:
                variable_key = f"filterMate_{key_group}_{key}"
                value_typped, type_returned = self.return_typped_value(
                    layer_variables[key_group][key], 
                    'save'
                )
                if type_returned in (list, dict):
                    value_typped = json.dumps(value_typped)
                QgsExpressionContextUtils.setLayerVariable(layer, variable_key, value_typped)

    def _create_spatial_index(self, layer, layer_props):
        """
        Create spatial index for layer based on provider type.
        
        Args:
            layer (QgsVectorLayer): Layer to index
            layer_props (dict): Layer properties dictionary
        """
        layer_provider_type = layer_props.get("infos", {}).get("layer_provider_type")
        
        if not layer_provider_type:
            layer_provider_type = detect_layer_provider_type(layer)
        
        if layer_provider_type == PROVIDER_POSTGRES:
            try:
                self.create_spatial_index_for_postgresql_layer(layer, layer_props)
            except (AttributeError, KeyError) as e:
                logger.debug(f"Could not create spatial index for PostgreSQL layer {layer.id()}: {e}")
            except Exception as e:
                if POSTGRESQL_AVAILABLE and psycopg2 and isinstance(e, psycopg2.Error):
                    logger.debug(f"PostgreSQL error creating spatial index: {e}")
                else:
                    logger.debug(f"Error creating spatial index: {e}")
        else:
            self.create_spatial_index_for_layer(layer)

    def add_project_layer(self, layer):
        """
        Add a spatial layer to the project with all necessary metadata and indexes.
        
        Args:
            layer (QgsVectorLayer): Layer to add
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not isinstance(layer, QgsVectorLayer) or not layer.isSpatial():
            return False
        
        # Try to load existing properties from database
        layer_variables = self._load_existing_layer_properties(layer)
        
        if layer_variables:
            # Layer exists - apply migration if needed
            self._migrate_legacy_geometry_field(layer_variables, layer)
        else:
            # New layer - search for primary key and build properties
            result = self.search_primary_key_from_layer(layer)
            if self.isCanceled() or result is False:
                return False
            
            if not isinstance(result, tuple) or len(list(result)) != 4:
                return False
            
            layer_variables = self._build_new_layer_properties(layer, result)
            self._set_layer_variables(layer, layer_variables)
        
        # Update properties count if first layer
        if self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["LAYERS"]["LAYER_PROPERTIES_COUNT"] == 0:
            properties_count = (
                len(layer_variables["infos"]) + 
                len(layer_variables["exploring"]) + 
                len(layer_variables["filtering"])
            )
            self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["LAYERS"]["LAYER_PROPERTIES_COUNT"] = properties_count
        
        # Prepare layer properties dict
        layer_props = {
            "infos": layer_variables["infos"],
            "exploring": layer_variables["exploring"],
            "filtering": layer_variables["filtering"]
        }
        layer_props["infos"]["layer_id"] = layer.id()
        
        # Save to database
        self.insert_properties_to_spatialite(layer.id(), layer_props)
        
        # Create spatial index
        self._create_spatial_index(layer, layer_props)
        
        # Add to project layers dictionary
        self.project_layers[layer.id()] = layer_props
        
        return True

    def remove_project_layer(self, layer_id):
        """
        Remove a layer from project tracking.
        
        Args:
            layer_id (str): Layer ID to remove
            
        Returns:
            bool: True if successful, False otherwise
        """
        if isinstance(layer_id, str):
            self.save_variables_from_layer(layer_id)    
            self.save_style_from_layer_id(layer_id)
            del self.project_layers[layer_id]
            return True
        return False

    def search_primary_key_from_layer(self, layer):
        """
        Search for a primary key field in the layer.
        
        Tries in order:
        1. Layer's declared primary key attributes
        2. Fields with 'id' in name that have unique values
        3. Any field with unique values
        4. Creates a virtual 'virtual_id' field
        
        Args:
            layer (QgsVectorLayer): Layer to search
            
        Returns:
            tuple: (field_name, field_index, field_type, is_numeric) or False if canceled
        """
        feature_count = layer.featureCount()
        
        primary_key_index = layer.primaryKeyAttributes()
        if len(primary_key_index) > 0:
            for field_id in primary_key_index:
                if self.isCanceled():
                    return False
                if len(layer.uniqueValues(field_id)) == feature_count:
                    field = layer.fields()[field_id]
                    return (field.name(), field_id, field.typeName(), field.isNumeric())
        else:
            for field in layer.fields():
                if self.isCanceled():
                    return False
                if 'id' in str(field.name()).lower():
                    if len(layer.uniqueValues(layer.fields().indexOf(field.name()))) == feature_count:
                        return (field.name(), layer.fields().indexFromName(field.name()), field.typeName(), field.isNumeric())
                    
            for field in layer.fields():
                if self.isCanceled():
                    return False
                if len(layer.uniqueValues(layer.fields().indexOf(field.name()))) == feature_count:
                    return (field.name(), layer.fields().indexFromName(field.name()), field.typeName(), field.isNumeric())
                
        # No unique field found - create virtual ID
        new_field = QgsField('virtual_id', QMetaType.Type.LongLong)
        layer.addExpressionField('@row_number', new_field)
        return ('virtual_id', layer.fields().indexFromName('virtual_id'), new_field.typeName(), True)

    def create_spatial_index_for_postgresql_layer(self, layer, layer_props):
        """
        Create PostgreSQL spatial indexes (GIST + primary key).
        
        Args:
            layer (QgsVectorLayer): PostgreSQL layer
            layer_props (dict): Layer properties with schema, table, geometry field, primary key
            
        Returns:
            bool: True if successful, False otherwise
        """
        if layer is None or layer_props is None:
            return False
        
        if "infos" not in layer_props:
            logger.warning(f"layer_props missing 'infos' dictionary, skipping spatial index creation")
            return False
        
        required_keys = ["layer_schema", "layer_name", "layer_geometry_field", "primary_key_name"]
        infos = layer_props["infos"]
        missing_keys = [k for k in required_keys if k not in infos or infos[k] is None]
        
        if missing_keys:
            logger.warning(f"layer_props['infos'] missing required keys: {missing_keys}, skipping spatial index creation")
            return False

        schema = infos["layer_schema"]
        table = infos["layer_name"]
        geometry_field = infos["layer_geometry_field"]
        primary_key_name = infos["primary_key_name"]

        connexion, source_uri = get_datasource_connexion_from_layer(layer)

        sql_statement = (
            f'CREATE INDEX IF NOT EXISTS {schema}_{table}_{geometry_field}_idx '
            f'ON "{schema}"."{table}" USING GIST ({geometry_field});'
            f'CREATE UNIQUE INDEX IF NOT EXISTS {schema}_{table}_{primary_key_name}_idx '
            f'ON "{schema}"."{table}" ({primary_key_name});'
            f'ALTER TABLE "{schema}"."{table}" CLUSTER ON {schema}_{table}_{geometry_field}_idx;'
            f'ANALYZE VERBOSE "{schema}"."{table}";'
        )

        with connexion.cursor() as cursor:
            cursor.execute(sql_statement)

        if self.isCanceled():
            return False
        
        return True

    def create_spatial_index_for_layer(self, layer):
        """
        Create QGIS spatial index for a layer.
        
        Args:
            layer (QgsVectorLayer): Layer to index
            
        Returns:
            bool: True if successful or index already exists, False if canceled
        """
        try:
            if not layer.isSpatial():
                return True
            
            if layer.hasSpatialIndex() != QgsFeatureSource.SpatialIndexNotPresent:
                return True
            
            if layer.featureCount() == 0:
                return True
            
            # Check for at least one valid geometry
            has_valid_geom = False
            for feature in layer.getFeatures():
                if feature.hasGeometry() and not feature.geometry().isNull():
                    has_valid_geom = True
                    break
                if self.isCanceled():
                    return False
            
            if not has_valid_geom:
                return True
            
            # Create spatial index
            alg_params_createspatialindex = {"INPUT": layer}
            processing.run('qgis:createspatialindex', alg_params_createspatialindex)
            
            if self.isCanceled():
                return False
        
        except Exception as e:
            safe_log(logger, logging.WARNING, 
                    f"Failed to create spatial index for layer {layer.name()}: {str(e)}")
    
        return True

    def save_variables_from_layer(self, layer, layer_properties=[]):
        """
        Save layer variables to Spatialite database.
        
        Args:
            layer (QgsVectorLayer): Layer to save variables for
            layer_properties (list): List of (key_group, key) tuples, or empty for all properties
        """
        layer_all_properties_flag = False
        assert isinstance(layer, QgsVectorLayer)

        if len(layer_properties) == 0:
            layer_all_properties_flag = True

        if layer.id() in self.PROJECT_LAYERS.keys():
            conn = self._safe_spatialite_connect()
            cur = conn.cursor()

            if layer_all_properties_flag is True:
                for key_group in ("infos", "exploring", "filtering"):
                    for key, value in self.PROJECT_LAYERS[layer.id()][key_group].items():
                        value_typped, type_returned = self.return_typped_value(value, 'save')
                        if type_returned in (list, dict):
                            value_typped = json.dumps(value_typped)
                        variable_key = f"filterMate_{key_group}_{key}"
                        QgsExpressionContextUtils.setLayerVariable(layer, key_group + '_' + key, value_typped)
                        self.savingLayerVariable.emit(layer, variable_key, value_typped, type_returned)
                        cur.execute(
                            """INSERT INTO fm_project_layers_properties 
                               VALUES(?, datetime(), ?, ?, ?, ?, ?)""",
                            (
                                str(uuid.uuid4()),
                                str(self.project_uuid),
                                layer.id(),
                                key_group,
                                key,
                                value_typped.replace("\'", "\'\'") if type_returned in (str, dict, list) else value_typped
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
                            variable_key = f"filterMate_{key_group}_{key}"
                            QgsExpressionContextUtils.setLayerVariable(layer, variable_key, value_typped)
                            self.savingLayerVariable.emit(layer, variable_key, value_typped, type_returned)
                            cur.execute(
                                """INSERT INTO fm_project_layers_properties 
                                   VALUES(?, datetime(), ?, ?, ?, ?, ?)""",
                                (
                                    str(uuid.uuid4()),
                                    str(self.project_uuid),
                                    layer.id(),
                                    layer_property[0],
                                    layer_property[1],
                                    value_typped.replace("\'", "\'\'") if type_returned in (str, dict, list) else value_typped
                                )
                            )
                            conn.commit()

            cur.close()
            conn.close()

    def remove_variables_from_layer(self, layer, layer_properties=[]):
        """
        Remove layer variables from Spatialite database.
        
        Args:
            layer (QgsVectorLayer): Layer to remove variables from
            layer_properties (list): List of (key_group, key) tuples, or empty for all properties
        """
        layer_all_properties_flag = False
        assert isinstance(layer, QgsVectorLayer)

        if len(layer_properties) == 0:
            layer_all_properties_flag = True

        if layer.id() in self.PROJECT_LAYERS.keys():
            conn = self._safe_spatialite_connect()
            cur = conn.cursor()

            if layer_all_properties_flag is True:
                cur.execute(
                    """DELETE FROM fm_project_layers_properties 
                       WHERE fk_project = ? AND layer_id = ?""",
                    (str(self.project_uuid), layer.id())
                )
                conn.commit()
                QgsExpressionContextUtils.setLayerVariables(layer, {})
            else:
                for layer_property in layer_properties:
                    if layer_property[0] in ("infos", "exploring", "filtering"):
                        if layer_property[0] in self.PROJECT_LAYERS[layer.id()] and layer_property[1] in self.PROJECT_LAYERS[layer.id()][layer_property[0]]:
                            cur.execute(
                                """DELETE FROM fm_project_layers_properties  
                                   WHERE fk_project = ? AND layer_id = ? AND meta_type = ? AND meta_key = ?""",
                                (str(self.project_uuid), layer.id(), layer_property[0], layer_property[1])
                            )
                            conn.commit()
                            variable_key = f"filterMate_{layer_property[0]}_{layer_property[1]}"
                            QgsExpressionContextUtils.setLayerVariable(layer, variable_key, '')
                            self.removingLayerVariable.emit(layer, variable_key)

            cur.close()
            conn.close()

    def save_style_from_layer_id(self, layer_id):
        """
        Save layer style to database or file.
        
        Args:
            layer_id (str): Layer ID to save style for
            
        Returns:
            bool: True (always, errors are logged but not propagated)
        """
        if layer_id in self.project_layers.keys():
            if "infos" not in self.project_layers[layer_id]:
                logger.warning(f"Layer {layer_id} missing 'infos' dictionary, skipping style save")
                return True
            
            if "layer_name" not in self.project_layers[layer_id]["infos"]:
                logger.warning(f"Layer {layer_id} missing 'layer_name' in infos, skipping style save")
                return True

            layers = [layer for layer in self.PROJECT.mapLayersByName(self.project_layers[layer_id]["infos"]["layer_name"]) if layer.id() == layer_id]
            if len(layers) > 0:
                layer = layers[0]
                try:
                    layer.deleteStyleFromDatabase(name=f"FilterMate_style_{layer.name()}")
                    result = layer.saveStyleToDatabase(name=f"FilterMate_style_{layer.name()}", description=f"FilterMate style for {layer.name()}", useAsDefault=True, uiFileContent="") 
                except (RuntimeError, AttributeError) as e:
                    logger.debug(f"Could not save style to database for layer {layer.name()}, falling back to file: {e}")
                    layer_path = layer.source().split('|')[0]
                    layer.saveNamedStyle(os.path.normcase(os.path.join(os.path.split(layer_path)[0], f'FilterMate_style_{layer.name()}.qml')))

        return True

    def remove_variables_from_all_layers(self):
        """
        Remove variables from all layers in the project.
        
        Returns:
            bool: True if successful, False if canceled or failed
        """
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
                if "infos" not in self.project_layers[layer_id]:
                    continue
                if "layer_name" not in self.project_layers[layer_id]["infos"]:
                    continue

                result_layers = [layer for layer in self.PROJECT.mapLayersByName(self.project_layers[layer_id]["infos"]["layer_name"]) if layer.id() == layer_id]
                if len(result_layers) > 0:
                    result_layer = result_layers[0]
                    QgsExpressionContextUtils.setLayerVariables(result_layer, {})

                if self.isCanceled():
                    return False

        return True

    def select_properties_from_spatialite(self, layer_id):
        """
        Select layer properties from Spatialite database.
        
        Args:
            layer_id (str): Layer ID to select properties for
            
        Returns:
            list: List of (meta_type, meta_key, meta_value) tuples
        """
        results = []
        conn = self._safe_spatialite_connect()
        cur = conn.cursor()
        cur.execute(
            """SELECT meta_type, meta_key, meta_value FROM fm_project_layers_properties  
               WHERE fk_project = ? and layer_id = ?""",
            (str(self.project_uuid), layer_id)
        )
        results = cur.fetchall()   
        conn.commit()
        cur.close()
        conn.close()
        return results
    
    def insert_properties_to_spatialite(self, layer_id, layer_props):
        """
        Insert layer properties into Spatialite database.
        
        Args:
            layer_id (str): Layer ID
            layer_props (dict): Dictionary of layer properties to insert
        """
        def do_insert():
            conn = self._safe_spatialite_connect()
            try:
                cur = conn.cursor()
                for key_group in layer_props:
                    for key in layer_props[key_group]:
                        value_typped, type_returned = self.return_typped_value(layer_props[key_group][key], 'save')
                        if type_returned in (list, dict):
                            value_typped = json.dumps(value_typped)
                        cur.execute(
                            """INSERT INTO fm_project_layers_properties 
                               VALUES(?, datetime(), ?, ?, ?, ?, ?)""",
                            (
                                str(uuid.uuid4()),
                                str(self.project_uuid),
                                layer_id,
                                key_group,
                                key,
                                value_typped.replace("\'", "\'\'") if type_returned in (str, dict, list) else value_typped
                            )
                        )
                conn.commit()
                cur.close()
                return True
            except Exception:
                if conn:
                    try:
                        conn.rollback()
                    except (AttributeError, OSError):
                        pass
                raise
            finally:
                if conn:
                    conn.close()
        
        sqlite_execute_with_retry(
            do_insert, 
            operation_name=f"insert properties for layer {layer_id}"
        )

    def can_cast(self, dest_type, source_value):
        """
        Check if a value can be cast to a destination type.
        
        Args:
            dest_type (type): Target type
            source_value: Value to cast
            
        Returns:
            bool: True if castable, False otherwise
        """
        try:
            dest_type(source_value)
            return True
        except (ValueError, TypeError, OverflowError):
            return False

    def return_typped_value(self, value_as_string, action=None):
        """
        Convert string value to typed value with type detection.
        
        Args:
            value_as_string: String value to convert
            action (str): 'save' or 'load' to handle JSON serialization
            
        Returns:
            tuple: (typed_value, type_returned)
        """
        value_typped = None
        type_returned = None

        if value_as_string is None or value_as_string == '':   
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
        elif self.can_cast(bool, value_as_string) is True and str(value_as_string).upper() in ('FALSE', 'TRUE'):
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
        """Handle task cancellation."""
        QgsMessageLog.logMessage(
            f'"{self.description()}" task was canceled',
            MESSAGE_TASKS_CATEGORIES[self.task_action], Qgis.Info
        )
        super().cancel()

    def finished(self, result):
        """
        Handle task completion and emit results.
        
        CRITICAL: Signals must be emitted and disconnected BEFORE displaying messages
        to avoid "wrapped C/C++ object has been deleted" errors.
        
        Args:
            result (bool): Task result
        """
        logger.info(f"LayersManagementEngineTask.finished(): task_action={self.task_action}, result={result}, project_layers count={len(self.project_layers) if self.project_layers else 0}")
        result_action = None
        message_category = MESSAGE_TASKS_CATEGORIES[self.task_action]

        if self.exception is None:
            if result is None:
                # Emit signal before UI operations
                try:
                    if self.project_layers is not None:
                        self.resultingLayers.emit(self.project_layers)
                except RuntimeError:
                    pass
                finally:
                    try:
                        self.resultingLayers.disconnect()
                    except (RuntimeError, TypeError):
                        pass
                
                iface.messageBar().pushMessage(
                    'Completed with no exception and no result (probably manually canceled by the user).',
                    MESSAGE_TASKS_CATEGORIES[self.task_action], Qgis.Warning
                )
            else:
                # CRITICAL: Emit signal BEFORE showing message
                try:
                    if self.project_layers is not None:
                        logger.info(f"Emitting resultingLayers signal with {len(self.project_layers)} layers")
                        self.resultingLayers.emit(self.project_layers)
                        logger.info("resultingLayers signal emitted successfully")
                except RuntimeError as e:
                    logger.warning(f"RuntimeError when emitting resultingLayers signal: {e}")
                
                if message_category == 'ManageLayers':
                    if self.task_action == 'add_layers':
                        result_action = f'{len(self.layers)} layer(s) added'
                    elif self.task_action == 'remove_layers':
                        result_action = f'{len(list(self.project_layers.keys())) - len(self.layers)} layer(s) removed'

                    iface.messageBar().pushMessage(
                        f'Layers list has been updated : {result_action}',
                        MESSAGE_TASKS_CATEGORIES[self.task_action], Qgis.Success
                    )
                elif message_category == 'ManageLayersProperties':
                    if self.layer_all_properties_flag is True:    
                        if self.task_action == 'save_layer_variable':
                            result_action = f'All properties saved for {self.layer_id} layer'
                        elif self.task_action == 'remove_layer_variable':
                            result_action = f'All properties removed for {self.layer_id} layer'

                        iface.messageBar().pushMessage(
                            f'Layers list has been updated : {result_action}',
                            MESSAGE_TASKS_CATEGORIES[self.task_action], Qgis.Success
                        )
                
                # Disconnect signals
                try:
                    self.resultingLayers.disconnect()
                except (RuntimeError, TypeError):
                    pass
        else:
            try:
                self.resultingLayers.disconnect()
            except (RuntimeError, TypeError):
                pass
            
            iface.messageBar().pushMessage(
                f"Exception: {self.exception}",
                MESSAGE_TASKS_CATEGORIES[self.task_action], Qgis.Critical
            )
            raise self.exception

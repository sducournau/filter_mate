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
import sqlite3
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
    geometry_type_to_string,
    escape_json_string,
    get_best_display_field
)

# Import task utilities
from .task_utils import (
    spatialite_connect,
    safe_spatialite_connect,
    sqlite_execute_with_retry, 
    ensure_db_directory_exists,
    MESSAGE_TASKS_CATEGORIES
)

# Import type utilities
from ..type_utils import can_cast, return_typed_value

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
        
        Delegates to the centralized ensure_db_directory_exists function
        in task_utils.py for consistent behavior across all tasks.
        
        Raises:
            OSError: If directory cannot be created
            ValueError: If db_file_path is invalid
        """
        ensure_db_directory_exists(self.db_file_path)
    
    
    def _safe_spatialite_connect(self):
        """
        Safely connect to Spatialite database, ensuring directory exists.
        
        Delegates to centralized safe_spatialite_connect() in task_utils.py.
        
        Returns:
            sqlite3.Connection: Database connection
            
        Raises:
            OSError: If directory cannot be created
            sqlite3.OperationalError: If database cannot be opened
        """
        return safe_spatialite_connect(self.db_file_path)


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
        Migrate legacy properties and ensure all required properties exist.
        
        This function handles backward compatibility for layers created with older versions
        of the plugin. It ensures that:
        1. Old property names are migrated to new names
        2. All required properties exist with sensible defaults
        3. Expression properties use the layer's primary key
        
        Args:
            layer_variables (dict): Dictionary with layer properties
            layer (QgsVectorLayer): Layer being processed
        """
        infos = layer_variables.get("infos", {})
        exploring = layer_variables.get("exploring", {})
        primary_key = infos.get("primary_key_name", "id")
        
        # Migrate old geometry_field to layer_geometry_field
        if "geometry_field" in infos and "layer_geometry_field" not in infos:
            infos["layer_geometry_field"] = infos["geometry_field"]
            del infos["geometry_field"]
            logger.info(f"Migrated geometry_field to layer_geometry_field for layer {layer.id()}")
        
        # Ensure all required exploring boolean flags exist
        exploring_booleans = {
            "is_linking": False,
            "is_selecting": False,
            "is_tracking": False,
            "is_changing_all_layer_properties": True
        }
        for prop_name, default_value in exploring_booleans.items():
            if prop_name not in exploring:
                exploring[prop_name] = default_value
                logger.info(f"Added missing '{prop_name}' property for layer {layer.id()}")
        
        # Ensure exploring groupbox property exists
        if "current_exploring_groupbox" not in exploring:
            exploring["current_exploring_groupbox"] = "single_selection"
            logger.info(f"Added missing 'current_exploring_groupbox' property for layer {layer.id()}")
        
        # Ensure all expression properties exist with primary key as default
        expression_properties = [
            "single_selection_expression",
            "multiple_selection_expression",
            "custom_selection_expression"
        ]
        for prop_name in expression_properties:
            if prop_name not in exploring:
                exploring[prop_name] = str(primary_key)
                logger.info(f"Added missing '{prop_name}' property for layer {layer.id()}")
            
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
            # IMPROVED: Use QgsDataSourceUri for reliable parsing instead of fragile regex
            try:
                from qgis.core import QgsDataSourceUri
                source_uri = QgsDataSourceUri(layer.source())
                
                # Extract schema
                schema = source_uri.schema()
                if schema:
                    source_schema = schema
                else:
                    # Fallback to 'public' if no schema specified
                    source_schema = 'public'
                
                # Extract geometry field
                geom_col = source_uri.geometryColumn()
                if geom_col:
                    geometry_field = geom_col
                else:
                    # Try from data provider
                    try:
                        geom_col = layer.dataProvider().geometryColumn()
                        if geom_col:
                            geometry_field = geom_col
                        else:
                            geometry_field = 'geom'
                    except AttributeError:
                        geometry_field = 'geom'
                
                logger.debug(f"PostgreSQL layer metadata: schema={source_schema}, geometry_field={geometry_field}")
                
            except Exception as e:
                logger.warning(f"Error parsing PostgreSQL layer source: {e}, falling back to regex")
                # Fallback to regex if QgsDataSourceUri fails
                layer_source = layer.source()
                regexp_match_schema = re.search(r'(?<=table=")[a-zA-Z0-9_-]*(?="\.)', layer_source)
                if regexp_match_schema:
                    source_schema = regexp_match_schema.group()
                regexp_match_geom = re.search(r'(?<=\()[a-zA-Z0-9_-]*(?=\))', layer_source)
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
        
        # Check PostgreSQL connection availability for PostgreSQL layers
        # This determines if we can use native PostgreSQL backend or need OGR fallback
        postgresql_connection_available = False
        if layer_provider_type == PROVIDER_POSTGRES and POSTGRESQL_AVAILABLE:
            try:
                conn, _ = get_datasource_connexion_from_layer(layer)
                if conn is not None:
                    postgresql_connection_available = True
                    conn.close()
                else:
                    logger.warning(f"PostgreSQL layer {layer.name()} will use OGR fallback (no connection)")
            except Exception as e:
                logger.warning(f"PostgreSQL connection test failed for {layer.name()}: {e}, will use OGR fallback")
        
        # Build properties from JSON templates
        # CRITICAL: Escape all string values to prevent JSON parsing errors
        # with special characters like em-dash (—), quotes, backslashes
        new_layer_variables = {}
        new_layer_variables["infos"] = json.loads(
            self.json_template_layer_infos % (
                escape_json_string(layer_geometry_type), 
                escape_json_string(layer.name()),
                escape_json_string(source_table_name) if source_table_name else "",
                escape_json_string(layer.id()), 
                escape_json_string(source_schema) if source_schema else "", 
                escape_json_string(layer_provider_type), 
                escape_json_string(layer.sourceCrs().authid()), 
                escape_json_string(primary_key_name) if primary_key_name else "", 
                primary_key_idx, 
                escape_json_string(primary_key_type) if primary_key_type else "", 
                escape_json_string(geometry_field) if geometry_field else "", 
                str(primary_key_is_numeric).lower()
            )
        )
        
        # Add PostgreSQL connection availability flag
        new_layer_variables["infos"]["postgresql_connection_available"] = postgresql_connection_available
        
        # Determine the best display field for exploring expressions
        # Use descriptive text fields when available instead of just primary key
        best_display_field = get_best_display_field(layer)
        display_expression = best_display_field if best_display_field else (primary_key_name if primary_key_name else "")
        
        new_layer_variables["exploring"] = json.loads(
            self.json_template_layer_exploring % (
                escape_json_string(display_expression),
                escape_json_string(display_expression),
                escape_json_string(display_expression)
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
        
        For PostgreSQL layers without connection, falls back to QGIS spatial index.
        
        Args:
            layer (QgsVectorLayer): Layer to index
            layer_props (dict): Layer properties dictionary
        """
        layer_provider_type = layer_props.get("infos", {}).get("layer_provider_type")
        
        if not layer_provider_type:
            layer_provider_type = detect_layer_provider_type(layer)
        
        if layer_provider_type == PROVIDER_POSTGRES:
            # Check if PostgreSQL connection is available
            postgresql_connection_available = layer_props.get("infos", {}).get("postgresql_connection_available", False)
            
            if postgresql_connection_available:
                try:
                    self.create_spatial_index_for_postgresql_layer(layer, layer_props)
                except (AttributeError, KeyError) as e:
                    logger.debug(f"Could not create spatial index for PostgreSQL layer {layer.id()}: {e}")
                    # Fallback to QGIS spatial index
                    self.create_spatial_index_for_layer(layer)
                except Exception as e:
                    if POSTGRESQL_AVAILABLE and psycopg2 and isinstance(e, psycopg2.Error):
                        logger.debug(f"PostgreSQL error creating spatial index: {e}")
                    else:
                        logger.debug(f"Error creating spatial index: {e}")
                    # Fallback to QGIS spatial index
                    self.create_spatial_index_for_layer(layer)
            else:
                # PostgreSQL layer but no connection - use QGIS spatial index (OGR fallback)
                logger.info(f"Using QGIS spatial index for PostgreSQL layer {layer.name()} (no DB connection)")
                self.create_spatial_index_for_layer(layer)
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
            # CRITICAL: Validate PostgreSQL layers don't have virtual_id (legacy bug)
            if layer.providerType() == 'postgres':
                primary_key = layer_variables.get("infos", {}).get("primary_key_name")
                if primary_key == "virtual_id":
                    error_msg = (
                        f"Couche PostgreSQL '{layer.name()}' : Données corrompues détectées.\n\n"
                        f"Cette couche utilise 'virtual_id' qui n'existe pas dans PostgreSQL.\n"
                        f"Cette erreur provient d'une version précédente de FilterMate.\n\n"
                        f"Solution : Supprimez cette couche du projet FilterMate, puis rajoutez-la.\n"
                        f"Assurez-vous que la table PostgreSQL a une PRIMARY KEY définie."
                    )
                    logger.error(error_msg)
                    raise ValueError(error_msg)
            
            # Layer exists - apply migration if needed
            self._migrate_legacy_geometry_field(layer_variables, layer)
        else:
            # New layer - search for primary key and build properties
            result = self.search_primary_key_from_layer(layer)
            if self.isCanceled() or result is False:
                return False
            
            if not isinstance(result, tuple) or len(list(result)) != 4:
                return False
            
            # Check if PostgreSQL layer using ctid (no PRIMARY KEY)
            primary_key = result[0]
            if layer.providerType() == 'postgres' and primary_key == 'ctid':
                # Show warning to user about limitations
                from qgis.core import Qgis
                from qgis.utils import iface
                iface.messageBar().pushMessage(
                    "FilterMate - PostgreSQL sans clé primaire",
                    f"La couche '{layer.name()}' n'a pas de PRIMARY KEY. "
                    f"Fonctionnalités limitées : vues matérialisées désactivées. "
                    f"Recommandation : ajoutez une PRIMARY KEY pour performances optimales.",
                    Qgis.Warning,
                    duration=10
                )
            
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

    def cleanup_postgresql_virtual_id_layers(self):
        """
        Clean up PostgreSQL layers that incorrectly use virtual_id.
        
        This is a migration function to fix layers affected by the virtual_id bug
        where PostgreSQL layers were allowed to use virtual fields that don't exist
        in the actual database.
        
        Returns:
            list: List of layer IDs that were cleaned up
        """
        cleaned_layer_ids = []
        
        try:
            conn = self._safe_spatialite_connect()
            cur = conn.cursor()
            
            # Find all layers with virtual_id as primary key
            cur.execute("""
                SELECT DISTINCT layer_id, meta_value 
                FROM fm_project_layers_properties 
                WHERE fk_project = ? 
                  AND meta_key = 'primary_key_name' 
                  AND meta_value = 'virtual_id'
            """, (str(self.project_uuid),))
            
            problematic_layers = cur.fetchall()
            
            for layer_id, _ in problematic_layers:
                # Check if this is a PostgreSQL layer
                cur.execute("""
                    SELECT meta_value 
                    FROM fm_project_layers_properties 
                    WHERE fk_project = ? 
                      AND layer_id = ? 
                      AND meta_key = 'layer_provider'
                """, (str(self.project_uuid), layer_id))
                
                provider_result = cur.fetchone()
                if provider_result and provider_result[0] == 'postgresql':
                    logger.warning(f"Removing corrupted PostgreSQL layer {layer_id} with virtual_id")
                    
                    # Delete all properties for this layer
                    cur.execute("""
                        DELETE FROM fm_project_layers_properties 
                        WHERE fk_project = ? AND layer_id = ?
                    """, (str(self.project_uuid), layer_id))
                    
                    cleaned_layer_ids.append(layer_id)
            
            conn.commit()
            cur.close()
            conn.close()
            
            if cleaned_layer_ids:
                logger.info(f"Cleaned up {len(cleaned_layer_ids)} PostgreSQL layers with virtual_id: {cleaned_layer_ids}")
            
        except Exception as e:
            logger.error(f"Error during PostgreSQL virtual_id cleanup: {e}")
        
        return cleaned_layer_ids

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
        layer_provider = layer.providerType()
        
        # CRITICAL FIX: For PostgreSQL layers, ALWAYS trust declared primary key
        # without checking uniqueness to avoid freeze on large tables.
        # uniqueValues() loads ALL values in memory = freeze on 100k+ rows
        is_postgresql = (layer_provider == 'postgres')
        
        # For PostgreSQL or unknown feature count, trust primary key attributes
        if feature_count == -1:
            logger.debug(f"Layer {layer.name()} has unknown feature count (-1), using primary key attributes directly")
        
        primary_key_index = layer.primaryKeyAttributes()
        if len(primary_key_index) > 0:
            for field_id in primary_key_index:
                if self.isCanceled():
                    return False
                field = layer.fields()[field_id]
                
                # CRITICAL: For PostgreSQL, ALWAYS trust declared PK (no uniqueValues check)
                # PostgreSQL enforces PRIMARY KEY constraint at database level
                if is_postgresql:
                    logger.debug(f"PostgreSQL layer: trusting declared primary key '{field.name()}' (no uniqueness check)")
                    return (field.name(), field_id, field.typeName(), field.isNumeric())
                
                # For unknown feature count, trust the declared primary key
                if feature_count == -1:
                    logger.debug(f"Using declared primary key: {field.name()}")
                    return (field.name(), field_id, field.typeName(), field.isNumeric())
                
                # For other providers with known count, verify uniqueness (safe for small datasets)
                if len(layer.uniqueValues(field_id)) == feature_count:
                    return (field.name(), field_id, field.typeName(), field.isNumeric())
        
        # If no declared primary key, try to find one
        # For PostgreSQL or unknown feature count, use first 'id' field without verification
        logger.debug(f"PostgreSQL layer '{layer.name()}': No declared PRIMARY KEY, searching for ID field manually")
        logger.debug(f"Available fields: {[f.name() for f in layer.fields()]}")
        
        for field in layer.fields():
            if self.isCanceled():
                return False
            field_name_lower = str(field.name()).lower()
            logger.debug(f"Checking field '{field.name()}' (lowercase: '{field_name_lower}')")
            
            # Check if field name contains 'id' or matches common ID patterns
            if 'id' in field_name_lower:
                # For PostgreSQL, assume 'id' field is unique (avoid freeze)
                if is_postgresql:
                    logger.info(f"PostgreSQL layer '{layer.name()}': Found field with 'id': '{field.name()}', using as primary key")
                    return (field.name(), layer.fields().indexFromName(field.name()), field.typeName(), field.isNumeric())
                
                if feature_count == -1:
                    logger.debug(f"Using field with 'id' in name: {field.name()}")
                    return (field.name(), layer.fields().indexFromName(field.name()), field.typeName(), field.isNumeric())
                
                # Only verify uniqueness for non-PostgreSQL layers
                if len(layer.uniqueValues(layer.fields().indexOf(field.name()))) == feature_count:
                    return (field.name(), layer.fields().indexFromName(field.name()), field.typeName(), field.isNumeric())
                
        # For PostgreSQL without declared PK or 'id' field, use ctid immediately
        # Don't iterate all fields (would freeze on large tables)
        if is_postgresql:
            logger.warning(
                f"⚠️ Couche PostgreSQL '{layer.name()}' : Aucune clé primaire ou champ 'id' trouvé.\n"
                f"   FilterMate utilisera 'ctid' (identifiant interne PostgreSQL) avec limitations :\n"
                f"   - ✅ Filtrage attributaire possible\n"
                f"   - ✅ Filtrage géométrique basique possible\n"
                f"   - ❌ Vues matérialisées désactivées (performance réduite)\n"
                f"   - ❌ Historique de filtres limité\n"
                f"   Recommandation : Ajoutez une PRIMARY KEY pour performances optimales."
            )
            return ('ctid', -1, 'tid', False)
        
        # For unknown feature count, use first field
        if feature_count == -1 and layer.fields().count() > 0:
            field = layer.fields()[0]
            logger.debug(f"Using first field as fallback: {field.name()}")
            return (field.name(), 0, field.typeName(), field.isNumeric())
        
        # For non-PostgreSQL layers, check uniqueness (safe for small datasets)
        for field in layer.fields():
            if self.isCanceled():
                return False
            if len(layer.uniqueValues(layer.fields().indexOf(field.name()))) == feature_count:
                return (field.name(), layer.fields().indexFromName(field.name()), field.typeName(), field.isNumeric())
        
        # Should not reach here for PostgreSQL (already handled above)
        # But keep as safety fallback
        if is_postgresql:
            logger.error(f"Unexpected: PostgreSQL layer '{layer.name()}' reached end of search_primary_key_from_layer")
            return ('ctid', -1, 'tid', False)
                
        # For non-PostgreSQL layers (memory, shapefile, etc.), create virtual ID
        new_field = QgsField('virtual_id', QMetaType.Type.LongLong)
        layer.addExpressionField('@row_number', new_field)
        logger.warning(f"Layer {layer.name()}: No unique field found, created virtual_id (only works for non-database layers)")
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
        
        # CRITICAL FIX: Check if connexion is None (PostgreSQL unavailable or connection failed)
        if connexion is None:
            logger.warning(f"Cannot create spatial index for PostgreSQL layer {layer.name()}: no database connection")
            return False

        try:
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
            connexion.commit()
        except Exception as e:
            logger.warning(f"Error creating spatial index for PostgreSQL layer {layer.name()}: {e}")
            return False
        finally:
            try:
                connexion.close()
            except (OSError, AttributeError) as e:
                logger.debug(f"Could not close connection: {e}")

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
        if not isinstance(layer, QgsVectorLayer):
            logger.error(f"save_variables_from_layer: Expected QgsVectorLayer, got {type(layer).__name__}")
            return

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
        if not isinstance(layer, QgsVectorLayer):
            logger.error(f"remove_variables_from_layer: Expected QgsVectorLayer, got {type(layer).__name__}")
            return

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
        
        Uses retry logic to handle database lock contention from concurrent access.
        
        Args:
            layer_id (str): Layer ID to select properties for
            
        Returns:
            list: List of (meta_type, meta_key, meta_value) tuples
        """
        def do_select():
            conn = None
            try:
                conn = self._safe_spatialite_connect()
                cur = conn.cursor()
                cur.execute(
                    """SELECT meta_type, meta_key, meta_value FROM fm_project_layers_properties  
                       WHERE fk_project = ? and layer_id = ?""",
                    (str(self.project_uuid), layer_id)
                )
                results = cur.fetchall()   
                cur.close()
                return results
            finally:
                if conn:
                    try:
                        conn.close()
                    except (AttributeError, OSError, sqlite3.Error):
                        pass
        
        return sqlite_execute_with_retry(
            do_select, 
            operation_name=f"select properties for layer {layer_id}"
        )
    
    def insert_properties_to_spatialite(self, layer_id, layer_props):
        """
        Insert layer properties into Spatialite database.
        
        Uses retry logic to handle database lock contention from concurrent access.
        
        Args:
            layer_id (str): Layer ID
            layer_props (dict): Dictionary of layer properties to insert
        """
        def do_insert():
            conn = None
            try:
                conn = self._safe_spatialite_connect()
                # Begin explicit transaction for better lock management
                conn.execute('BEGIN IMMEDIATE')
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
            except (sqlite3.Error, OSError, ValueError) as e:
                logger.debug(f"Error inserting properties to Spatialite: {e}")
                if conn:
                    try:
                        conn.rollback()
                    except (AttributeError, OSError, sqlite3.Error):
                        pass
                raise
            finally:
                if conn:
                    try:
                        conn.close()
                    except (AttributeError, OSError, sqlite3.Error):
                        pass
        
        sqlite_execute_with_retry(
            do_insert, 
            operation_name=f"insert properties for layer {layer_id}"
        )

    def can_cast(self, dest_type, source_value):
        """
        Check if a value can be cast to a destination type.
        Delegates to centralized type_utils.can_cast().
        
        Args:
            dest_type (type): Target type
            source_value: Value to cast
            
        Returns:
            bool: True if castable, False otherwise
        """
        return can_cast(dest_type, source_value)

    def return_typped_value(self, value_as_string, action=None):
        """
        Convert string value to typed value with type detection.
        Delegates to centralized type_utils.return_typed_value().
        
        Args:
            value_as_string: String value to convert
            action (str): 'save' or 'load' to handle JSON serialization
            
        Returns:
            tuple: (typed_value, type_returned)
        """
        return return_typed_value(value_as_string, action)

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
                
                # Task was likely canceled by user - log only, no message bar notification
                logger.info('Task completed with no result (likely canceled by user)')
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
                    # Message bar notification removed - internal operation, too verbose for UX
                    logger.info(f'Layers list has been updated: {result_action}')
                elif message_category == 'ManageLayersProperties':
                    if self.layer_all_properties_flag is True:    
                        if self.task_action == 'save_layer_variable':
                            result_action = f'All properties saved for {self.layer_id} layer'
                        elif self.task_action == 'remove_layer_variable':
                            result_action = f'All properties removed for {self.layer_id} layer'
                        # Message bar notification removed - internal operation, too verbose for UX
                        logger.info(f'Layers properties updated: {result_action}')
                
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

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.utils import *
from qgis.utils import iface
from qgis import processing
import logging
import os

# Import logging configuration
from .logging_config import setup_logger, safe_log
from ..config.config import ENV_VARS

# Setup logger with rotation
logger = setup_logger(
    'FilterMate.Tasks',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_tasks.log'),
    level=logging.INFO
)

# Import conditionnel de psycopg2 pour support PostgreSQL optionnel
try:
    import psycopg2
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False
    psycopg2 = None
    logger.warning("PostgreSQL support disabled (psycopg2 not found)")

# Import constants
from .constants import (
    PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR, PROVIDER_MEMORY,
    PREDICATE_INTERSECTS, PREDICATE_WITHIN, PREDICATE_CONTAINS,
    PREDICATE_OVERLAPS, PREDICATE_CROSSES, PREDICATE_TOUCHES,
    PREDICATE_DISJOINT, PREDICATE_EQUALS,
    get_provider_name, should_warn_performance
)

# Import backend architecture
from .backends import BackendFactory

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

def get_best_metric_crs(project, source_crs):
    """
    Détermine le meilleur CRS métrique à utiliser pour les calculs.
    Priorité:
    1. CRS du projet s'il est métrique
    2. CRS suggéré par QGIS basé sur l'emprise
    3. EPSG:3857 (Web Mercator) par défaut
    
    Args:
        project: QgsProject instance
        source_crs: QgsCoordinateReferenceSystem du layer source
    
    Returns:
        str: authid du CRS métrique optimal (ex: 'EPSG:3857')
    """
    # 1. Vérifier le CRS du projet
    project_crs = project.crs()
    if project_crs and not project_crs.isGeographic():
        # Le CRS du projet est métrique, l'utiliser
        map_units = project_crs.mapUnits()
        if map_units not in [QgsUnitTypes.DistanceUnit.Degrees, QgsUnitTypes.DistanceUnit.Unknown]:
            logger.info(f"Using project CRS for metric calculations: {project_crs.authid()}")
            return project_crs.authid()
    
    # 2. Essayer d'obtenir un CRS suggéré basé sur l'emprise
    if source_crs and hasattr(QgsCoordinateReferenceSystem, 'createFromWkt'):
        try:
            # Obtenir les limites du layer
            extent = None
            if hasattr(source_crs, 'bounds'):
                extent = source_crs.bounds()
            
            # Si possible, obtenir un CRS UTM approprié basé sur la longitude centrale
            if extent and extent.isFinite():
                center_lon = (extent.xMinimum() + extent.xMaximum()) / 2
                center_lat = (extent.yMinimum() + extent.yMaximum()) / 2
                
                # Calculer la zone UTM
                utm_zone = int((center_lon + 180) / 6) + 1
                
                # Déterminer si hémisphère nord ou sud
                if center_lat >= 0:
                    # Hémisphère nord
                    utm_epsg = 32600 + utm_zone
                else:
                    # Hémisphère sud
                    utm_epsg = 32700 + utm_zone
                
                utm_crs = QgsCoordinateReferenceSystem(f"EPSG:{utm_epsg}")
                if utm_crs.isValid():
                    logger.info(f"Using calculated UTM CRS for metric calculations: EPSG:{utm_epsg}")
                    return f"EPSG:{utm_epsg}"
        except Exception as e:
            logger.debug(f"Could not calculate optimal UTM CRS: {e}")
    
    # 3. Par défaut, utiliser Web Mercator (EPSG:3857)
    logger.info("Using default Web Mercator (EPSG:3857) for metric calculations")
    return "EPSG:3857"


def should_reproject_layer(layer, target_crs_authid):
    """
    Détermine si un layer doit être reprojeté vers le CRS cible.
    
    Args:
        layer: QgsVectorLayer à vérifier
        target_crs_authid: CRS cible (ex: 'EPSG:3857')
    
    Returns:
        bool: True si reprojection nécessaire
    """
    if not layer or not target_crs_authid:
        return False
    
    layer_crs = layer.sourceCrs()
    
    # Vérifier si les CRS sont différents
    if layer_crs.authid() == target_crs_authid:
        logger.debug(f"Layer {layer.name()} already in target CRS {target_crs_authid}")
        return False
    
    # Vérifier si le CRS du layer est géographique
    if layer_crs.isGeographic():
        logger.info(f"Layer {layer.name()} has geographic CRS {layer_crs.authid()}, will reproject to {target_crs_authid}")
        return True
    
    # Vérifier les unités de distance
    map_units = layer_crs.mapUnits()
    if map_units in [QgsUnitTypes.DistanceUnit.Degrees, QgsUnitTypes.DistanceUnit.Unknown]:
        logger.info(f"Layer {layer.name()} has non-metric units, will reproject to {target_crs_authid}")
        return True
    
    # Le layer est déjà dans un CRS métrique mais différent
    # Pour la cohérence, reprojetons quand même vers le CRS cible commun
    logger.info(f"Layer {layer.name()} will be reprojected from {layer_crs.authid()} to {target_crs_authid} for consistency")
    return True


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
        self.primary_key_name = None
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
        # Initialize with standard spatial predicates mapping user-friendly names to SQL functions
        # FIXED: Updated to include standard predicate names used in UI
        self.predicates = {
            "Intersect": "ST_Intersects",
            "intersects": "ST_Intersects",
            "Contain": "ST_Contains",
            "contains": "ST_Contains",
            "Disjoint": "ST_Disjoint",
            "disjoint": "ST_Disjoint",
            "Equal": "ST_Equals",
            "equals": "ST_Equals",
            "Touch": "ST_Touches",
            "touches": "ST_Touches",
            "Overlap": "ST_Overlaps",
            "overlaps": "ST_Overlaps",
            "Are within": "ST_Within",
            "within": "ST_Within",
            "Cross": "ST_Crosses",
            "crosses": "ST_Crosses",
            "covers": "ST_Covers",
            "coveredby": "ST_CoveredBy"
        }
        global ENV_VARS
        self.PROJECT = ENV_VARS["PROJECT"]
        self.current_materialized_view_schema = 'filter_mate_temp'
        
        # Track active database connections for cleanup on cancellation
        self.active_connections = []

    
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

    def _initialize_source_layer(self):
        """
        Initialize source layer and basic layer count.
        
        Returns:
            bool: True if source layer found, False otherwise
        """
        self.layers_count = 1
        layers = [
            layer for layer in self.PROJECT.mapLayersByName(
                self.task_parameters["infos"]["layer_name"]
            ) 
            if layer.id() == self.task_parameters["infos"]["layer_id"]
        ]
        
        if not layers:
            return False
        
        self.source_layer = layers[0]
        self.source_crs = self.source_layer.sourceCrs()
        self.source_layer_crs_authid = self.task_parameters["infos"]["layer_crs_authid"]
        
        # Extract feature count limit if provided
        task_options = self.task_parameters.get("task", {}).get("options", {})
        if "LAYERS" in task_options and "FEATURE_COUNT_LIMIT" in task_options["LAYERS"]:
            limit = task_options["LAYERS"]["FEATURE_COUNT_LIMIT"]
            if isinstance(limit, int) and limit > 0:
                self.feature_count_limit = limit
        
        return True

    def _configure_metric_crs(self):
        """
        Configure CRS for metric calculations, reprojecting if necessary.
        
        Sets has_to_reproject_source_layer flag and updates source_layer_crs_authid
        if the source CRS is geographic or non-metric.
        """
        source_crs_distance_unit = self.source_crs.mapUnits()
        
        # Check if CRS is geographic or non-metric
        is_non_metric = (
            source_crs_distance_unit in ['DistanceUnit.Degrees', 'DistanceUnit.Unknown'] 
            or self.source_crs.isGeographic()
        )
        
        if is_non_metric:
            self.has_to_reproject_source_layer = True
            # Get optimal metric CRS for layer extent
            self.source_layer_crs_authid = get_best_metric_crs(self.PROJECT, self.source_crs)
            logger.info(
                f"Source layer will be reprojected to {self.source_layer_crs_authid} "
                "for metric calculations"
            )
        else:
            logger.info(f"Source layer CRS is already metric: {self.source_layer_crs_authid}")

    def _organize_layers_to_filter(self):
        """
        Organize layers to be filtered by provider type.
        
        Populates self.layers dictionary with layers grouped by provider,
        and updates layers_count.
        """
        if not self.task_parameters["filtering"]["has_layers_to_filter"]:
            return
        
        for layer_props in self.task_parameters["task"]["layers"]:
            provider_type = layer_props["layer_provider_type"]
            
            # Initialize provider list if needed
            if provider_type not in self.layers:
                self.layers[provider_type] = []
            
            # Find layer by name and ID
            layers = [
                layer for layer in self.PROJECT.mapLayersByName(layer_props["layer_name"])
                if layer.id() == layer_props["layer_id"]
            ]
            
            if layers:
                self.layers[provider_type].append([layers[0], layer_props])
                self.layers_count += 1
        
        self.provider_list = list(self.layers.keys())

    def _log_backend_info(self):
        """
        Log backend information and performance warnings for filtering tasks.
        
        Only logs if task_action is 'filter'.
        """
        if self.task_action != 'filter':
            return
        
        # Determine active backend
        backend_name = "Memory/QGIS"
        if POSTGRESQL_AVAILABLE and self.param_source_provider_type == PROVIDER_POSTGRES:
            backend_name = "PostgreSQL/PostGIS"
        elif self.param_source_provider_type == PROVIDER_SPATIALITE:
            backend_name = "Spatialite"
        elif self.param_source_provider_type == PROVIDER_OGR:
            backend_name = "OGR"
        
        logger.info(f"Using {backend_name} backend for filtering")
        
        # Performance warning for large datasets without PostgreSQL
        feature_count = self.source_layer.featureCount()
        if feature_count > 50000 and not (
            POSTGRESQL_AVAILABLE and self.param_source_provider_type == PROVIDER_POSTGRES
        ):
            logger.warning(
                f"Large dataset detected ({feature_count:,} features) without PostgreSQL backend. "
                "Performance may be reduced. Consider using PostgreSQL/PostGIS for optimal performance."
            )

    def _execute_task_action(self):
        """
        Execute the appropriate action based on task_action parameter.
        
        Returns:
            bool: True if action succeeded, False otherwise
        """
        if self.task_action == 'filter':
            return self.execute_filtering()
        
        elif self.task_action == 'unfilter':
            return self.execute_unfiltering()
        
        elif self.task_action == 'reset':
            return self.execute_reseting()
        
        elif self.task_action == 'export':
            if self.task_parameters["task"]["EXPORTING"]["HAS_LAYERS_TO_EXPORT"]:
                return self.execute_exporting()
            else:
                return False
        
        return False

    def run(self):
        """
        Main task orchestration method.
        
        Initializes layers, configures CRS, organizes filtering layers,
        and executes the appropriate action based on task_action.
        
        Returns:
            bool: True if task completed successfully, False otherwise
        """
        try:
            # Initialize source layer
            if not self._initialize_source_layer():
                return False
            
            # Configure metric CRS if needed
            self._configure_metric_crs()
            
            # Organize layers to filter by provider
            self._organize_layers_to_filter()
            
            # Extract database and project configuration
            if 'db_file_path' in self.task_parameters["task"]:
                db_path = self.task_parameters["task"]['db_file_path']
                if db_path not in (None, ''):
                    self.db_file_path = db_path
            
            if 'project_uuid' in self.task_parameters["task"]:
                proj_uuid = self.task_parameters["task"]['project_uuid']
                if proj_uuid not in (None, ''):
                    self.project_uuid = proj_uuid
            
            # Initialize progress and logging
            self.setProgress(0)
            logger.info(f"Starting {self.task_action} task for {self.layers_count} layer(s)")
            
            # Log backend info and performance warnings
            self._log_backend_info()
            
            # Execute the appropriate action
            result = self._execute_task_action()
            if self.isCanceled() or result is False:
                return False
            
            # Task completed successfully
            self.setProgress(100)
            logger.info(f"{self.task_action.capitalize()} task completed successfully")
            return True
        
        except Exception as e:
            self.exception = e
            safe_log(logger, logging.ERROR, f'FilterEngineTask run() failed: {e}', exc_info=True)
            return False


    def _initialize_source_filtering_parameters(self):
        """Extract and initialize all parameters needed for source layer filtering"""
        self.param_source_old_subset = ''
        
        # Extract basic layer information
        self.param_source_provider_type = self.task_parameters["infos"]["layer_provider_type"]
        self.param_source_schema = self.task_parameters["infos"]["layer_schema"]
        self.param_source_table = self.task_parameters["infos"]["layer_name"]
        self.param_source_layer_id = self.task_parameters["infos"]["layer_id"]
        self.param_source_geom = self.task_parameters["infos"]["layer_geometry_field"]
        self.primary_key_name = self.task_parameters["infos"]["primary_key_name"]
        
        logger.debug(f"Filtering layer: {self.param_source_table} (Provider: {self.param_source_provider_type})")
        
        # Extract filtering configuration
        self.has_combine_operator = self.task_parameters["filtering"]["has_combine_operator"]
        self.source_layer_fields_names = [
            field.name() for field in self.source_layer.fields() 
            if field.name() != self.primary_key_name
        ]
        
        if self.has_combine_operator:
            self.param_source_layer_combine_operator = self.task_parameters["filtering"]["source_layer_combine_operator"]
            self.param_other_layers_combine_operator = self.task_parameters["filtering"]["other_layers_combine_operator"]
            if self.source_layer.subsetString():
                self.param_source_old_subset = self.source_layer.subsetString()

    def _qualify_field_names_in_expression(self, expression):
        """
        Add proper table qualifiers to field names in the expression.
        
        For PostgreSQL, converts field references to "table"."field" format.
        For other providers, ensures proper quoting.
        """
        # Find fields that might be primary key or similar
        fields_similar_to_pk = [
            x for x in self.source_layer_fields_names 
            if self.primary_key_name.find(x) > -1
        ]
        existing_fields = [
            x for x in self.source_layer_fields_names 
            if expression.find(x) > -1
        ]
        
        # Qualify primary key field
        if self.primary_key_name in expression:
            if self.param_source_table not in expression:
                if f' "{self.primary_key_name}" ' in expression:
                    if self.param_source_provider_type == PROVIDER_POSTGRES:
                        expression = expression.replace(
                            f'"{self.primary_key_name}"',
                            f'"{self.param_source_table}"."{self.primary_key_name}"'
                        )
                elif f" {self.primary_key_name} " in expression:
                    if self.param_source_provider_type == PROVIDER_POSTGRES:
                        expression = expression.replace(
                            self.primary_key_name,
                            f'"{self.param_source_table}"."{self.primary_key_name}"'
                        )
                    else:
                        expression = expression.replace(
                            self.primary_key_name,
                            f'"{self.primary_key_name}"'
                        )
        
        # Qualify other existing fields
        elif existing_fields:
            if self.param_source_table not in expression:
                for field_name in existing_fields:
                    if f' "{field_name}" ' in expression:
                        if self.param_source_provider_type == PROVIDER_POSTGRES:
                            expression = expression.replace(
                                f'"{field_name}"',
                                f'"{self.param_source_table}"."{field_name}"'
                            )
                    elif f" {field_name} " in expression:
                        if self.param_source_provider_type == PROVIDER_POSTGRES:
                            expression = expression.replace(
                                field_name,
                                f'"{self.param_source_table}"."{field_name}"'
                            )
                        else:
                            expression = expression.replace(
                                field_name,
                                f'"{field_name}"'
                            )
        
        return expression

    def _process_qgis_expression(self, expression):
        """
        Process and validate a QGIS expression, converting it to appropriate SQL.
        
        Returns:
            tuple: (processed_expression, is_field_expression) or (None, None) if invalid
        """
        if QgsExpression(expression).isField():
            return None, None
        
        if not QgsExpression(expression).isValid():
            return None, None
        
        # Add leading space and check for field equality
        expression = " " + expression
        is_field_expression = QgsExpression().isFieldEqualityExpression(
            self.task_parameters["task"]["expression"]
        )
        
        if is_field_expression[0]:
            self.is_field_expression = is_field_expression
        
        # Qualify field names
        expression = self._qualify_field_names_in_expression(expression)
        
        # Convert to PostGIS SQL
        expression = self.qgis_expression_to_postgis(expression)
        expression = expression.strip()
        
        # Handle CASE statements
        if expression.startswith("CASE"):
            expression = 'SELECT ' + expression
        
        return expression, is_field_expression

    def _combine_with_old_subset(self, expression):
        """
        Combine new expression with existing subset string using combine operator.
        
        Returns:
            str: Combined expression
        """
        if not self.param_source_old_subset or not self.param_source_layer_combine_operator:
            return expression
        
        # Extract WHERE clause from old subset
        index_where = self.param_source_old_subset.find('WHERE')
        if index_where == -1:
            return expression
        
        param_old_subset_where = self.param_source_old_subset[index_where:]
        param_source_old_subset = self.param_source_old_subset[:index_where]
        
        # Remove trailing )) if present
        if param_old_subset_where.endswith('))'):
            param_old_subset_where = param_old_subset_where[:-1]
        
        combined = (
            f'{param_source_old_subset} {param_old_subset_where} '
            f'{self.param_source_layer_combine_operator} {expression} )'
        )
        
        return combined

    def _build_feature_id_expression(self, features_list):
        """
        Build SQL IN expression from list of feature IDs.
        
        Returns:
            str: SQL expression like "table"."pk" IN (1,2,3) or "table"."pk" IN ('a','b','c')
        """
        features_ids = [str(feature[self.primary_key_name]) for feature in features_list]
        
        if not features_ids:
            return None
        
        # Build IN clause based on primary key type
        if self.task_parameters["infos"]["primary_key_is_numeric"]:
            expression = (
                f'"{self.param_source_table}"."{self.primary_key_name}" IN '
                f'({", ".join(features_ids)})'
            )
        else:
            expression = (
                f'"{self.param_source_table}"."{self.primary_key_name}" IN '
                f"({', '.join(repr(fid) for fid in features_ids)})"
            )
        
        # Combine with old subset if needed
        if self.param_source_old_subset and self.param_source_layer_combine_operator:
            expression = (
                f'( {self.param_source_old_subset} ) '
                f'{self.param_source_layer_combine_operator} {expression}'
            )
        
        return expression

    def _apply_filter_and_update_subset(self, expression):
        """
        Apply filter expression to source layer and update subset strings.
        
        Returns:
            bool: True if successful, False otherwise
        """
        # CRITICAL: setSubsetString must be called from main thread
        result = self._safe_set_subset_string(self.source_layer, expression)
        
        if result:
            # Build full SELECT expression for subset management
            full_expression = (
                f'SELECT "{self.param_source_table}"."{self.primary_key_name}", '
                f'"{self.param_source_table}"."{self.param_source_geom}" '
                f'FROM "{self.param_source_schema}"."{self.param_source_table}" '
                f'WHERE {expression}'
            )
            self.manage_layer_subset_strings(
                self.source_layer,
                full_expression,
                self.primary_key_name,
                self.param_source_geom,
                False
            )
        
        return result

    def execute_source_layer_filtering(self):
        """Manage the creation of the origin filtering expression"""
        # Initialize all parameters and configuration
        self._initialize_source_filtering_parameters()
        
        result = False
        task_expression = self.task_parameters["task"]["expression"]
        logger.debug(f"Task expression: {task_expression}")
        
        # Process QGIS expression if provided
        if task_expression:
            processed_expr, is_field_expr = self._process_qgis_expression(task_expression)
            
            if processed_expr:
                # Combine with existing subset if needed
                self.expression = self._combine_with_old_subset(processed_expr)
                
                # Apply filter and update subset
                result = self._apply_filter_and_update_subset(self.expression)
        
        # Fallback to feature ID list if expression processing failed
        if not result:
            self.is_field_expression = None
            features_list = self.task_parameters["task"]["features"]
            
            if features_list:
                self.expression = self._build_feature_id_expression(features_list)
                
                if self.expression:
                    result = self._apply_filter_and_update_subset(self.expression)
        
        return result
    
    def _safe_set_subset_string(self, layer, expression):
        """
        Thread-safe wrapper for layer.setSubsetString().
        
        CRITICAL: setSubsetString() MUST be called from the main Qt thread.
        Calling it from QgsTask thread causes QGIS crashes (access violation).
        
        Args:
            layer: QgsVectorLayer to filter
            expression: Filter expression string
        
        Returns:
            bool: True if filter applied successfully
        """
        from qgis.PyQt.QtCore import QMetaObject, Qt, Q_ARG, Q_RETURN_ARG, QThread
        from qgis.core import QgsApplication
        
        # If already in main thread, execute directly
        if QThread.currentThread() == QgsApplication.instance().thread():
            try:
                return layer.setSubsetString(expression)
            except Exception as e:
                logger.error(f"Failed to apply subset string: {e}")
                return False
        
        # Store result for thread-safe return
        result_container = {'result': None, 'error': None}
        
        def apply_subset():
            """Inner function executed in main thread"""
            try:
                result_container['result'] = layer.setSubsetString(expression)
            except Exception as e:
                logger.error(f"Failed to apply subset string: {e}")
                result_container['error'] = str(e)
                result_container['result'] = False
        
        # Execute in main thread using BlockingQueuedConnection
        # This properly waits for the main thread to finish
        QMetaObject.invokeMethod(
            QgsApplication.instance(),
            apply_subset,
            Qt.BlockingQueuedConnection
        )
        
        return result_container.get('result', False)
    
    def _initialize_source_subset_and_buffer(self):
        """
        Initialize source subset expression and buffer parameters.
        
        Sets param_source_new_subset based on expression type and
        extracts buffer value/expression from task parameters.
        """
        # Set source subset based on expression type
        if QgsExpression(self.expression).isField() is False:
            self.param_source_new_subset = self.expression
        else:
            self.param_source_new_subset = self.param_source_old_subset

        # Extract buffer parameters if configured
        if self.task_parameters["filtering"]["has_buffer_value"] is True:
            if self.task_parameters["filtering"]["buffer_value_property"] is True:
                if self.task_parameters["filtering"]["buffer_value_expression"] != '':
                    self.param_buffer_expression = self.task_parameters["filtering"]["buffer_value_expression"]
                else:
                    self.param_buffer_value = self.task_parameters["filtering"]["buffer_value"]
            else:
                self.param_buffer_value = self.task_parameters["filtering"]["buffer_value"]

    def _prepare_geometries_by_provider(self, provider_list):
        """
        Prepare source geometries for each provider type.
        
        Args:
            provider_list: List of unique provider types to prepare
            
        Returns:
            bool: True if all required geometries prepared successfully
        """
        # Prepare PostgreSQL source geometry
        if 'postgresql' in provider_list and POSTGRESQL_AVAILABLE:
            logger.info("Preparing PostgreSQL source geometry...")
            self.prepare_postgresql_source_geom()
        
        # Prepare Spatialite source geometry (WKT string) with fallback to OGR
        if 'spatialite' in provider_list:
            logger.info("Preparing Spatialite source geometry...")
            spatialite_success = False
            try:
                self.prepare_spatialite_source_geom()
                if hasattr(self, 'spatialite_source_geom') and self.spatialite_source_geom is not None:
                    spatialite_success = True
                    logger.info("✓ Spatialite source geometry prepared successfully")
                else:
                    logger.warning("Spatialite geometry preparation returned None")
            except Exception as e:
                logger.warning(f"Spatialite geometry preparation failed: {e}")
                import traceback
                logger.debug(f"Traceback: {traceback.format_exc()}")
            
            # Fallback to OGR if Spatialite failed
            if not spatialite_success:
                logger.info("Falling back to OGR geometry preparation...")
                try:
                    self.prepare_ogr_source_geom()
                    if hasattr(self, 'ogr_source_geom') and self.ogr_source_geom is not None:
                        # Use OGR geometry as Spatialite geometry
                        self.spatialite_source_geom = self.ogr_source_geom
                        logger.info("✓ Successfully used OGR geometry as fallback")
                    else:
                        logger.error("OGR fallback also failed - no geometry available")
                        return False
                except Exception as e2:
                    logger.error(f"OGR fallback failed: {e2}")
                    return False

        # Prepare OGR geometry if needed for OGR layers or buffer expressions
        if 'ogr' in provider_list or self.param_buffer_expression != '':
            logger.info("Preparing OGR/Spatialite source geometry...")
            self.prepare_ogr_source_geom()

        return True

    def _filter_all_layers_with_progress(self):
        """
        Iterate through all layers and apply filtering with progress tracking.
        
        Updates task description to show current layer being processed.
        Progress is visible in QGIS task manager panel.
        
        Returns:
            bool: True if all layers processed (some may fail), False if canceled
        """
        i = 1
        for layer_provider_type in self.layers:
            for layer, layer_props in self.layers[layer_provider_type]:
                # Update task description with current progress
                self.setDescription(f"Filtering layer {i}/{self.layers_count}: {layer.name()}")
                
                logger.info(f"Filtering layer {i}/{self.layers_count}: {layer.name()} ({layer_provider_type})")
                result = self.execute_geometric_filtering(layer_provider_type, layer, layer_props)
                
                if result == True:
                    logger.info(f"{layer.name()} has been filtered")
                else:
                    logger.error(f"{layer.name()} - errors occurred during filtering")
                
                i += 1
                progress_percent = int((i / self.layers_count) * 100)
                self.setProgress(progress_percent)
                
                if self.isCanceled():
                    return False
        
        return True

    def manage_distant_layers_geometric_filtering(self):
        """
        Filter layers from a prefiltered layer.
        
        Orchestrates the complete workflow: initialize parameters, prepare geometries,
        and filter all layers with progress tracking.
        
        Returns:
            bool: True if all layers processed successfully, False on error or cancellation
        """
        # Initialize source subset and buffer parameters
        self._initialize_source_subset_and_buffer()
        
        # Build unique provider list including source layer provider
        provider_list = self.provider_list + [self.param_source_provider_type]
        provider_list = list(dict.fromkeys(provider_list))
        
        # Prepare geometries for all provider types
        if not self._prepare_geometries_by_provider(provider_list):
            return False
        
        # Filter all layers with progress tracking
        return self._filter_all_layers_with_progress()
    
    def qgis_expression_to_postgis(self, expression):

        if expression.find('if') >= 0:
            expression = re.sub('if\((.*,.*,.*)\))', '(if(.* then .* else .*))', expression)
            logger.debug(f"Expression: {expression}")


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


    def qgis_expression_to_spatialite(self, expression):
        """
        Convert QGIS expression to Spatialite SQL.
        
        Spatialite spatial functions are ~90% compatible with PostGIS, but there are some differences:
        - Type casting: PostgreSQL uses :: operator, Spatialite uses CAST() function
        - String comparison is case-sensitive by default
        - Some function names differ slightly
        
        Args:
            expression (str): QGIS expression string
        
        Returns:
            str: Spatialite SQL expression
        
        Note:
            This function adapts QGIS expressions to Spatialite SQL syntax.
            Most PostGIS spatial functions work in Spatialite with the same name.
        """
        
        # Handle CASE expressions
        expression = re.sub('case', ' CASE ', expression, flags=re.IGNORECASE)
        expression = re.sub('when', ' WHEN ', expression, flags=re.IGNORECASE)
        expression = re.sub(' is ', ' IS ', expression, flags=re.IGNORECASE)
        expression = re.sub('then', ' THEN ', expression, flags=re.IGNORECASE)
        expression = re.sub('else', ' ELSE ', expression, flags=re.IGNORECASE)
        
        # Handle LIKE/ILIKE - Spatialite doesn't have ILIKE, use LIKE with LOWER()
        # For case-insensitive matching in Spatialite
        expression = re.sub(r'(\w+)\s+ILIKE\s+', r'LOWER(\1) LIKE LOWER(', expression, flags=re.IGNORECASE)
        expression = re.sub('not', ' NOT ', expression, flags=re.IGNORECASE)
        expression = re.sub('like', ' LIKE ', expression, flags=re.IGNORECASE)
        
        # Convert PostgreSQL :: type casting to Spatialite CAST() function
        # PostgreSQL: "field"::numeric -> Spatialite: CAST("field" AS REAL)
        expression = re.sub(r'(["\w]+)::numeric', r'CAST(\1 AS REAL)', expression)
        expression = re.sub(r'(["\w]+)::integer', r'CAST(\1 AS INTEGER)', expression)
        expression = re.sub(r'(["\w]+)::text', r'CAST(\1 AS TEXT)', expression)
        expression = re.sub(r'(["\w]+)::double', r'CAST(\1 AS REAL)', expression)
        
        # Handle numeric comparisons - ensure fields are cast properly
        expression = expression.replace('" >', ' ').replace('">', ' ')
        expression = expression.replace('" <', ' ').replace('"<', ' ')
        expression = expression.replace('" +', ' ').replace('"+', ' ')
        expression = expression.replace('" -', ' ').replace('"-', ' ')
        
        # Spatial functions compatibility (most are identical, but document them)
        # ST_Buffer, ST_Intersects, ST_Contains, ST_Distance, ST_Union, ST_Transform
        # all work the same in Spatialite as in PostGIS
        
        return expression


    def prepare_postgresql_source_geom(self):
        

        source_table = self.param_source_table
        self.postgresql_source_geom = '"{source_table}"."{source_geom}"'.format(
                                                                                source_table=source_table,
                                                                                source_geom=self.param_source_geom
                                                                                )

        if self.param_buffer_expression != None and self.param_buffer_expression != '':


            if self.param_buffer_expression.find('"') == 0 and self.param_buffer_expression.find(source_table) != 1:
                self.param_buffer_expression = '"{source_table}".'.format(source_table=source_table) + self.param_buffer_expression

            self.param_buffer_expression = re.sub(' "', ' "mv_{source_table}"."'.format(source_table=source_table), self.param_buffer_expression)

            self.param_buffer_expression = self.qgis_expression_to_postgis(self.param_buffer_expression)    

            
            self.param_buffer = self.param_buffer_expression

            result = self.manage_layer_subset_strings(self.source_layer, None, self.primary_key_name, self.param_source_geom, True)


            layer_name = self.source_layer.name()
            self.current_materialized_view_name = self.source_layer.id().replace(layer_name, '').replace('-', '_')
                
            self.postgresql_source_geom = '"mv_{current_materialized_view_name}_dump"."{source_geom}"'.format(
                                                                                                        source_geom=self.param_source_geom,
                                                                                                        current_materialized_view_name=self.current_materialized_view_name
                                                                                                        )
            
        


        elif self.param_buffer_value != None:

            self.param_buffer = self.param_buffer_value

            result = self.manage_layer_subset_strings(self.source_layer, None, self.primary_key_name, self.param_source_geom, True)
                
            self.postgresql_source_geom = '"mv_{current_materialized_view_name}_dump"."{source_geom}"'.format(
                                                                                                        source_geom=self.param_source_geom,
                                                                                                        current_materialized_view_name=self.current_materialized_view_name
                                                                                                        )     

        

        logger.debug(f"prepare_postgresql_source_geom: {self.postgresql_source_geom}")     



    def prepare_spatialite_source_geom(self):
        """
        Prepare source geometry for Spatialite filtering.
        
        Converts selected features to WKT format for use in Spatialite spatial queries.
        Handles reprojection and buffering if needed.
        """
        # Get features from task parameters
        features = self.task_parameters["task"]["features"]
        logger.debug(f"prepare_spatialite_source_geom: Processing {len(features)} features")
        
        raw_geometries = [feature.geometry() for feature in features if feature.hasGeometry()]
        logger.debug(f"prepare_spatialite_source_geom: {len(raw_geometries)} geometries with geometry")
        
        if len(raw_geometries) == 0:
            logger.error("prepare_spatialite_source_geom: No geometries found in source features")
            self.spatialite_source_geom = None
            return
        
        geometries = []

        if self.has_to_reproject_source_layer is True:
            transform = QgsCoordinateTransform(
                QgsCoordinateReferenceSystem(self.source_crs.authid()), 
                QgsCoordinateReferenceSystem(self.source_layer_crs_authid), 
                self.PROJECT
            )
            logger.debug(f"Will reproject from {self.source_crs.authid()} to {self.source_layer_crs_authid}")

        for geometry in raw_geometries:
            if geometry.isEmpty() is False:
                # Make a copy to avoid modifying original
                geom_copy = QgsGeometry(geometry)
                
                if geom_copy.isMultipart():
                    geom_copy.convertToSingleType()
                    
                if self.has_to_reproject_source_layer is True:
                    geom_copy.transform(transform)
                    
                if self.param_buffer_value is not None and self.param_buffer_value > 0:
                    geom_copy = geom_copy.buffer(self.param_buffer_value, 5)
                    logger.debug(f"Applied buffer of {self.param_buffer_value}")
                    
                geometries.append(geom_copy)

        if len(geometries) == 0:
            logger.error("prepare_spatialite_source_geom: No valid geometries after processing")
            self.spatialite_source_geom = None
            return

        # Collect all geometries into one
        collected_geometry = QgsGeometry.collectGeometry(geometries)
        wkt = collected_geometry.asWkt()
        
        # Escape single quotes for SQL
        self.spatialite_source_geom = wkt.replace("'", "''")

        logger.debug(f"prepare_spatialite_source_geom: WKT length = {len(self.spatialite_source_geom)} chars")
        logger.debug(f"prepare_spatialite_source_geom WKT preview: {self.spatialite_source_geom[:200]}...") 


    def _fix_invalid_geometries(self, layer, output_key):
        """
        Fix invalid geometries in layer using QGIS processing.
        
        Args:
            layer: Input layer
            output_key: Key to store output in self.outputs dict
            
        Returns:
            QgsVectorLayer: Layer with fixed geometries
        """
        alg_params = {
            'INPUT': layer,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        self.outputs[output_key] = processing.run('qgis:fixgeometries', alg_params)
        return self.outputs[output_key]['OUTPUT']


    def _reproject_layer(self, layer, target_crs):
        """
        Reproject layer to target CRS and fix resulting geometries.
        
        Args:
            layer: Input layer
            target_crs: Target CRS authority ID (e.g., 'EPSG:3857')
            
        Returns:
            QgsVectorLayer: Reprojected layer with fixed geometries
        """
        # Reproject
        alg_params = {
            'INPUT': layer,
            'TARGET_CRS': target_crs,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        self.outputs['alg_source_layer_params_reprojectlayer'] = processing.run('qgis:reprojectlayer', alg_params)
        layer = self.outputs['alg_source_layer_params_reprojectlayer']['OUTPUT']
        
        # Fix geometries after reprojection
        layer = self._fix_invalid_geometries(layer, 'alg_source_layer_params_fixgeometries_reproject')
        
        # Create spatial index
        processing.run('qgis:createspatialindex', {"INPUT": layer})
        
        return layer


    def _get_buffer_distance_parameter(self):
        """
        Get buffer distance parameter from task configuration.
        
        Returns:
            QgsProperty or float or None: Buffer distance
        """
        if self.param_buffer_expression:
            return QgsProperty.fromExpression(self.param_buffer_expression)
        elif self.param_buffer_value is not None:
            return float(self.param_buffer_value)
        return None


    def _apply_qgis_buffer(self, layer, buffer_distance):
        """
        Apply buffer using QGIS processing algorithm.
        
        Args:
            layer: Input layer
            buffer_distance: QgsProperty or float
            
        Returns:
            QgsVectorLayer: Buffered layer
            
        Raises:
            Exception: If buffer operation fails
        """
        # Fix geometries before buffer
        layer = self._fix_invalid_geometries(layer, 'alg_source_layer_params_fixgeometries_buffer')
        
        # Log layer info
        logger.debug(f"Layer before buffer: {layer.featureCount()} features, "
                   f"CRS: {layer.crs().authid()}, "
                   f"Geometry type: {layer.geometryType()}")
        
        # Apply buffer with dissolve
        alg_params = {
            'DISSOLVE': True,
            'DISTANCE': buffer_distance,
            'END_CAP_STYLE': 0,
            'INPUT': layer,
            'JOIN_STYLE': 0,
            'MITER_LIMIT': 2,
            'SEGMENTS': 5,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        
        self.outputs['alg_source_layer_params_buffer'] = processing.run('qgis:buffer', alg_params)
        layer = self.outputs['alg_source_layer_params_buffer']['OUTPUT']
        
        # Create spatial index
        processing.run('qgis:createspatialindex', {"INPUT": layer})
        
        return layer


    def _evaluate_buffer_distance(self, layer, buffer_param):
        """
        Evaluate buffer distance from parameter (handles expressions).
        
        Args:
            layer: Layer to use for expression evaluation
            buffer_param: QgsProperty or float
            
        Returns:
            float: Evaluated buffer distance
        """
        if isinstance(buffer_param, QgsProperty):
            # Expression-based buffer: use first feature to evaluate
            features = list(layer.getFeatures())
            if features:
                context = QgsExpressionContext()
                context.setFeature(features[0])
                return buffer_param.value(context, 0)
            return 0
        return buffer_param

    def _create_memory_layer_for_buffer(self, layer):
        """
        Create empty memory layer for buffered features.
        
        Args:
            layer: Source layer for CRS and geometry type
            
        Returns:
            QgsVectorLayer: Empty memory layer configured for buffered geometries
        """
        geom_type = "Polygon" if layer.geometryType() in [0, 1] else "MultiPolygon"
        buffered_layer = QgsVectorLayer(
            f"{geom_type}?crs={layer.crs().authid()}",
            "buffered_temp",
            "memory"
        )
        return buffered_layer

    def _buffer_all_features(self, layer, buffer_dist):
        """
        Buffer all features from layer.
        
        Args:
            layer: Source layer
            buffer_dist: Buffer distance
            
        Returns:
            tuple: (list of geometries, valid_count, invalid_count)
        """
        geometries = []
        valid_features = 0
        invalid_features = 0
        
        for feature in layer.getFeatures():
            geom = feature.geometry()
            if geom and not geom.isEmpty():
                try:
                    # Make valid before buffer
                    if not geom.isGeosValid():
                        geom = geom.makeValid()
                    
                    # Apply buffer
                    buffered_geom = geom.buffer(float(buffer_dist), 5)
                    
                    if buffered_geom and not buffered_geom.isEmpty():
                        geometries.append(buffered_geom)
                        valid_features += 1
                    else:
                        invalid_features += 1
                except Exception as feat_error:
                    logger.debug(f"Skipping invalid feature during manual buffer: {feat_error}")
                    invalid_features += 1
            else:
                invalid_features += 1
        
        logger.debug(f"Manual buffer results: {valid_features} valid, {invalid_features} invalid features")
        return geometries, valid_features, invalid_features

    def _dissolve_and_add_to_layer(self, geometries, buffered_layer):
        """
        Dissolve geometries and add to memory layer.
        
        Args:
            geometries: List of buffered geometries
            buffered_layer: Target memory layer
            
        Returns:
            QgsVectorLayer: Layer with dissolved geometry added
        """
        # Dissolve all geometries into one
        dissolved_geom = QgsGeometry.unaryUnion(geometries)
        
        # Create feature with dissolved geometry
        feat = QgsFeature()
        feat.setGeometry(dissolved_geom)
        
        provider = buffered_layer.dataProvider()
        provider.addFeatures([feat])
        buffered_layer.updateExtents()
        
        # Create spatial index
        processing.run('qgis:createspatialindex', {"INPUT": buffered_layer})
        
        return buffered_layer

    def _create_buffered_memory_layer(self, layer, buffer_distance):
        """
        Manually buffer layer features and create memory layer (fallback method).
        
        Args:
            layer: Input layer
            buffer_distance: QgsProperty or float
            
        Returns:
            QgsVectorLayer: Memory layer with buffered geometries
            
        Raises:
            Exception: If no valid geometries could be buffered
        """
        feature_count = layer.featureCount()
        logger.debug(f"Layer has {feature_count} features before manual buffer")
        
        if feature_count == 0:
            raise Exception("Cannot buffer layer: source layer has no features")
        
        # Evaluate buffer distance
        buffer_dist = self._evaluate_buffer_distance(layer, buffer_distance)
        logger.debug(f"Manual buffer distance: {buffer_dist}")
        
        # Create memory layer
        buffered_layer = self._create_memory_layer_for_buffer(layer)
        
        # Buffer all features
        geometries, valid_features, invalid_features = self._buffer_all_features(layer, buffer_dist)
        
        # Dissolve and add to layer if we have valid geometries
        if geometries:
            return self._dissolve_and_add_to_layer(geometries, buffered_layer)
        else:
            error_msg = (f"No valid geometries could be buffered. "
                        f"Total features: {feature_count}, "
                        f"Valid after buffer: {valid_features}, "
                        f"Invalid: {invalid_features}")
            raise Exception(error_msg)


    def _apply_buffer_with_fallback(self, layer, buffer_distance):
        """
        Apply buffer to layer with automatic fallback to manual method.
        
        Args:
            layer: Input layer
            buffer_distance: QgsProperty or float
            
        Returns:
            QgsVectorLayer: Buffered layer
            
        Raises:
            Exception: If both QGIS and manual buffer methods fail
        """
        try:
            # Try QGIS buffer algorithm first
            return self._apply_qgis_buffer(layer, buffer_distance)
        except Exception as e:
            # Fallback to manual buffer
            logger.warning(f"QGIS buffer algorithm failed: {str(e)}, using manual buffer approach")
            try:
                return self._create_buffered_memory_layer(layer, buffer_distance)
            except Exception as manual_error:
                raise Exception(f"Both buffer methods failed. QGIS: {str(e)}, Manual: {str(manual_error)}")


    def prepare_ogr_source_geom(self):
        """
        Prepare OGR source geometry with optional reprojection and buffering.
        
        REFACTORED: Decomposed from 173 lines to ~35 lines using helper methods.
        Main method now orchestrates geometry preparation workflow.
        
        Process:
        1. Fix invalid geometries in source layer
        2. Reproject if needed
        3. Apply buffer if specified
        4. Store result in self.ogr_source_geom
        """
        layer = self.source_layer
        
        # Step 1: Fix invalid geometries
        layer = self._fix_invalid_geometries(layer, 'alg_source_layer_params_fixgeometries_source')
        
        # Step 2: Reproject if needed
        if self.has_to_reproject_source_layer:
            layer = self._reproject_layer(layer, self.source_layer_crs_authid)
        
        # Step 3: Apply buffer if specified
        buffer_distance = self._get_buffer_distance_parameter()
        if buffer_distance is not None:
            layer = self._apply_buffer_with_fallback(layer, buffer_distance)
        
        # Store result
        self.ogr_source_geom = layer
        logger.debug(f"prepare_ogr_source_geom: {self.ogr_source_geom}")



    def _verify_and_create_spatial_index(self, layer, layer_name=None):
        """
        Verify that spatial index exists on layer, create if missing.
        
        This method checks if a layer has a spatial index and creates one automatically
        if it's missing. Spatial indexes dramatically improve performance of spatial
        operations (intersect, contains, etc.).
        
        Args:
            layer: QgsVectorLayer to check
            layer_name: Optional display name for user messages
            
        Returns:
            bool: True if index exists or was created successfully, False otherwise
        """
        if not layer or not layer.isValid():
            logger.warning("Cannot verify spatial index: invalid layer")
            return False
        
        display_name = layer_name or layer.name()
        
        # Check if layer already has spatial index
        if layer.hasSpatialIndex():
            logger.debug(f"Spatial index already exists for layer: {display_name}")
            return True
        
        # No spatial index - create one
        logger.info(f"Creating spatial index for layer: {display_name}")
        
        # NOTE: Cannot display message bar from worker thread - would cause crash
        # Message bar operations MUST run in main thread
        # Spatial index creation is logged instead
        
        # Create spatial index
        try:
            processing.run('qgis:createspatialindex', {
                'INPUT': layer
            })
            logger.info(f"Successfully created spatial index for: {display_name}")
            return True
            
        except Exception as e:
            logger.warning(f"Could not create spatial index for {display_name}: {e}")
            logger.info(f"Proceeding without spatial index - performance may be reduced")
            return False


    def _build_postgis_predicates(self, postgis_predicates, layer_props, param_has_to_reproject_layer, param_layer_crs_authid):
        """
        Build PostGIS spatial predicates array for geometric filtering.
        
        Args:
            postgis_predicates: List of PostGIS predicate functions (ST_Intersects, etc.)
            layer_props: Layer properties dict with schema, table, geometry field
            param_has_to_reproject_layer: Whether layer needs reprojection
            param_layer_crs_authid: Target CRS authority ID
            
        Returns:
            tuple: (postgis_sub_expression_array, param_distant_geom_expression)
        """
        param_distant_table = layer_props["layer_name"]
        param_distant_geometry_field = layer_props["layer_geometry_field"]
        
        postgis_sub_expression_array = []
        param_distant_geom_expression = '"{distant_table}"."{distant_geometry_field}"'.format(
            distant_table=param_distant_table,
            distant_geometry_field=param_distant_geometry_field
        )
        
        # Utiliser le CRS métrique du source layer pour tous les calculs
        target_crs_srid = self.source_layer_crs_authid.split(':')[1] if hasattr(self, 'source_layer_crs_authid') else '3857'
        
        for postgis_predicate in postgis_predicates:
            current_geom_expr = param_distant_geom_expression
            
            if param_has_to_reproject_layer:
                # Reprojeter le layer distant dans le même CRS métrique que le source
                current_geom_expr = 'ST_Transform({param_distant_geom_expression}, {target_crs_srid})'.format(
                    param_distant_geom_expression=param_distant_geom_expression,
                    target_crs_srid=target_crs_srid
                )
                logger.debug(f"Layer will be reprojected to {self.source_layer_crs_authid} for comparison")
            
            postgis_sub_expression_array.append(
                postgis_predicate + '({source_sub_expression_geom},{param_distant_geom_expression})'.format(
                    source_sub_expression_geom=self.postgresql_source_geom,
                    param_distant_geom_expression=current_geom_expr
                )
            )
        
        return postgis_sub_expression_array, param_distant_geom_expression

    def _get_source_reference(self, sub_expression):
        """
        Determine the source reference for spatial joins.
        
        Returns either materialized view reference or the sub_expression/table.
        
        Args:
            sub_expression: Source layer subset expression or table reference
            
        Returns:
            str: Source reference for JOIN clause
        """
        if self.current_materialized_view_name:
            return f'"{self.current_materialized_view_schema}"."mv_{self.current_materialized_view_name}_dump"'
        return sub_expression

    def _build_spatial_join_query(self, layer_props, param_postgis_sub_expression, sub_expression):
        """
        Build SELECT query with spatial JOIN for filtering.
        
        Args:
            layer_props: Layer properties dict
            param_postgis_sub_expression: PostGIS spatial predicate
            sub_expression: Source layer subset expression
            
        Returns:
            str: SELECT query with INNER JOIN
        """
        param_distant_primary_key_name = layer_props["primary_key_name"]
        param_distant_schema = layer_props["layer_schema"]
        param_distant_table = layer_props["layer_name"]
        
        source_ref = self._get_source_reference(sub_expression)
        
        # Check if expression is a field or complex query
        is_field = QgsExpression(self.expression).isField()
        
        # Build query based on combine operator and expression type
        if self.has_combine_operator:
            # With combine operator - no WHERE clause needed
            query = (
                f'(SELECT "{param_distant_table}"."{param_distant_primary_key_name}" '
                f'FROM "{param_distant_schema}"."{param_distant_table}" '
                f'INNER JOIN {source_ref} ON {param_postgis_sub_expression})'
            )
        else:
            # Without combine operator - add WHERE clause if not a field
            if is_field:
                # For field expressions, use simple JOIN
                query = (
                    f'(SELECT "{param_distant_table}"."{param_distant_primary_key_name}" '
                    f'FROM "{param_distant_schema}"."{param_distant_table}" '
                    f'INNER JOIN {source_ref} ON {param_postgis_sub_expression})'
                )
            else:
                # For complex expressions, add WHERE clause
                if self.current_materialized_view_name:
                    # Materialized view has WHERE embedded
                    query = (
                        f'(SELECT "{param_distant_table}"."{param_distant_primary_key_name}" '
                        f'FROM "{param_distant_schema}"."{param_distant_table}" '
                        f'INNER JOIN {source_ref} ON {param_postgis_sub_expression} '
                        f'WHERE {sub_expression})'
                    )
                else:
                    # Direct table JOIN with WHERE
                    query = (
                        f'(SELECT "{param_distant_table}"."{param_distant_primary_key_name}" '
                        f'FROM "{param_distant_schema}"."{param_distant_table}" '
                        f'INNER JOIN "{self.param_source_schema}"."{self.param_source_table}" '
                        f'ON {param_postgis_sub_expression} WHERE {sub_expression})'
                    )
        
        return query

    def _apply_combine_operator(self, primary_key_name, param_expression, param_old_subset, param_combine_operator):
        """
        Apply SQL set operator to combine with existing subset.
        
        Args:
            primary_key_name: Primary key field name
            param_expression: The subquery expression
            param_old_subset: Existing subset to combine with
            param_combine_operator: SQL set operator (UNION, INTERSECT, EXCEPT)
            
        Returns:
            str: Complete IN expression with optional combine operator
        """
        if param_old_subset and param_combine_operator:
            return (
                f'"{primary_key_name}" IN ( {param_old_subset} '
                f'{param_combine_operator} {param_expression} )'
            )
        else:
            return f'"{primary_key_name}" IN {param_expression}'

    def _build_postgis_filter_expression(self, layer_props, param_postgis_sub_expression, sub_expression, param_old_subset, param_combine_operator):
        """
        Build complete PostGIS filter expression for subset string.
        
        Args:
            layer_props: Layer properties dict
            param_postgis_sub_expression: PostGIS spatial predicate expression
            sub_expression: Source layer subset expression
            param_old_subset: Existing subset string from layer
            param_combine_operator: SQL set operator (UNION, INTERSECT, EXCEPT)
            
        Returns:
            tuple: (expression, param_expression) - Complete filter and subquery
        """
        param_distant_primary_key_name = layer_props["primary_key_name"]
        
        # Build spatial join subquery
        param_expression = self._build_spatial_join_query(
            layer_props, 
            param_postgis_sub_expression, 
            sub_expression
        )
        
        # Apply combine operator if specified
        expression = self._apply_combine_operator(
            param_distant_primary_key_name,
            param_expression,
            param_old_subset,
            param_combine_operator
        )
        
        return expression, param_expression


    def _execute_ogr_spatial_selection(self, layer, current_layer, param_old_subset):
        """
        Execute spatial selection using QGIS processing for OGR/non-PostgreSQL layers.
        
        Args:
            layer: Original layer
            current_layer: Potentially reprojected working layer
            param_old_subset: Existing subset string
            
        Returns:
            None (modifies current_layer selection)
        """
        if self.has_combine_operator is True:
            current_layer.selectAll()
            
            if self.param_other_layers_combine_operator == 'OR':
                self._verify_and_create_spatial_index(current_layer)
                # CRITICAL FIX: Thread-safe subset string application
                self._safe_set_subset_string(current_layer, param_old_subset)
                current_layer.selectAll()
                self._safe_set_subset_string(current_layer, '')
                
                alg_params_select = {
                    'INPUT': current_layer,
                    'INTERSECT': self.ogr_source_geom,
                    'METHOD': 1,
                    'PREDICATE': [int(predicate) for predicate in self.current_predicates.keys()]
                }
                processing.run("qgis:selectbylocation", alg_params_select)
                
            elif self.param_other_layers_combine_operator == 'AND':
                self._verify_and_create_spatial_index(current_layer)
                alg_params_select = {
                    'INPUT': current_layer,
                    'INTERSECT': self.ogr_source_geom,
                    'METHOD': 2,
                    'PREDICATE': [int(predicate) for predicate in self.current_predicates.keys()]
                }
                processing.run("qgis:selectbylocation", alg_params_select)
                
            elif self.param_other_layers_combine_operator == 'NOT AND':
                self._verify_and_create_spatial_index(current_layer)
                alg_params_select = {
                    'INPUT': current_layer,
                    'INTERSECT': self.ogr_source_geom,
                    'METHOD': 3,
                    'PREDICATE': [int(predicate) for predicate in self.current_predicates.keys()]
                }
                processing.run("qgis:selectbylocation", alg_params_select)
                
            else:
                self._verify_and_create_spatial_index(current_layer)
                alg_params_select = {
                    'INPUT': current_layer,
                    'INTERSECT': self.ogr_source_geom,
                    'METHOD': 0,
                    'PREDICATE': [int(predicate) for predicate in self.current_predicates.keys()]
                }
                processing.run("qgis:selectbylocation", alg_params_select)
        else:
            self._verify_and_create_spatial_index(current_layer)
            alg_params_select = {
                'INPUT': current_layer,
                'INTERSECT': self.ogr_source_geom,
                'METHOD': 0,
                'PREDICATE': [int(predicate) for predicate in self.current_predicates.keys()]
            }
            processing.run("qgis:selectbylocation", alg_params_select)


    def _build_ogr_filter_from_selection(self, current_layer, layer_props, param_distant_geom_expression):
        """
        Build filter expression from selected features for OGR layers.
        
        Args:
            current_layer: Layer with selected features
            layer_props: Layer properties dict
            param_distant_geom_expression: Geometry field expression
            
        Returns:
            tuple: (success_bool, filter_expression or None)
        """
        param_distant_primary_key_name = layer_props["primary_key_name"]
        param_distant_primary_key_is_numeric = layer_props["primary_key_is_numeric"]
        param_distant_schema = layer_props["layer_schema"]
        param_distant_table = layer_props["layer_name"]
        param_distant_geometry_field = layer_props["layer_geometry_field"]
        
        # Extract feature IDs from selection
        features_ids = []
        for feature in current_layer.selectedFeatures():
            features_ids.append(str(feature[param_distant_primary_key_name]))
        
        if len(features_ids) == 0:
            return False, None
        
        # Build IN clause based on key type
        if param_distant_primary_key_is_numeric:
            param_expression = '"{distant_primary_key_name}" IN '.format(
                distant_primary_key_name=param_distant_primary_key_name
            ) + "(" + ", ".join(features_ids) + ")"
        else:
            param_expression = '"{distant_primary_key_name}" IN '.format(
                distant_primary_key_name=param_distant_primary_key_name
            ) + "('" + "', '".join(features_ids) + "')"
        
        # Build full SELECT expression for manage_layer_subset_strings
        expression = 'SELECT "{param_distant_table}"."{param_distant_primary_key_name}", {param_distant_geom_expression} FROM "{param_distant_schema}"."{param_distant_table}" WHERE {expression}'.format(
            param_distant_primary_key_name=param_distant_primary_key_name,
            param_distant_geom_expression=param_distant_geom_expression,
            param_distant_schema=param_distant_schema,
            param_distant_table=param_distant_table,
            expression=param_expression
        )
        
        return param_expression, expression


    def _qualify_field_names_in_expression(self, expression, field_names, primary_key_name, table_name, is_postgresql):
        """
        Qualify field names with table prefix for PostgreSQL expressions.
        
        This helper adds table qualifiers to field names in QGIS expressions to make them
        compatible with PostgreSQL queries (e.g., "field" becomes "table"."field").
        
        Args:
            expression: Raw QGIS expression string
            field_names: List of field names to qualify
            primary_key_name: Primary key field name
            table_name: Source table name
            is_postgresql: Whether target is PostgreSQL (True) or other provider (False)
            
        Returns:
            str: Expression with qualified field names
        """
        result_expression = expression
        
        # Handle primary key
        if primary_key_name in result_expression:
            if table_name not in result_expression:
                if f' "{primary_key_name}" ' in result_expression:
                    if is_postgresql:
                        result_expression = result_expression.replace(
                            f'"{primary_key_name}"',
                            f'"{table_name}"."{primary_key_name}"'
                        )
                elif f" {primary_key_name} " in result_expression:
                    if is_postgresql:
                        result_expression = result_expression.replace(
                            primary_key_name,
                            f'"{table_name}"."{primary_key_name}"'
                        )
                    else:
                        result_expression = result_expression.replace(
                            primary_key_name,
                            f'"{primary_key_name}"'
                        )
        
        # Handle other fields
        existing_fields = [x for x in field_names if x in result_expression]
        if existing_fields and table_name not in result_expression:
            for field_name in existing_fields:
                if f' "{field_name}" ' in result_expression:
                    if is_postgresql:
                        result_expression = result_expression.replace(
                            f'"{field_name}"',
                            f'"{table_name}"."{field_name}"'
                        )
                elif f" {field_name} " in result_expression:
                    if is_postgresql:
                        result_expression = result_expression.replace(
                            field_name,
                            f'"{table_name}"."{field_name}"'
                        )
                    else:
                        result_expression = result_expression.replace(
                            field_name,
                            f'"{field_name}"'
                        )
        
        return result_expression


    def _build_combined_filter_expression(self, new_expression, old_subset, combine_operator):
        """
        Combine new filter expression with existing subset using specified operator.
        
        Args:
            new_expression: New filter expression to apply
            old_subset: Existing subset string from layer
            combine_operator: SQL operator ('AND', 'OR', 'NOT')
            
        Returns:
            str: Combined filter expression
        """
        if not old_subset or not combine_operator:
            return new_expression
        
        # Extract WHERE clause from old subset if present
        param_old_subset_where_clause = ''
        param_source_old_subset = old_subset
        
        index_where_clause = old_subset.find('WHERE')
        if index_where_clause > -1:
            param_old_subset_where_clause = old_subset[index_where_clause:]
            if param_old_subset_where_clause.endswith('))'):
                param_old_subset_where_clause = param_old_subset_where_clause[:-1]
            param_source_old_subset = old_subset[:index_where_clause]
        
        # Combine expressions
        combined = f'{param_source_old_subset} {param_old_subset_where_clause} {combine_operator} {new_expression} )'
        return combined 

    def _validate_layer_properties(self, layer_props, layer_name):
        """
        Validate required fields in layer properties.
        
        Args:
            layer_props: Dict containing layer information
            layer_name: Layer name for error messages
            
        Returns:
            tuple: (layer_name, primary_key, geom_field, layer_schema) or (None, None, None, None) on error
        """
        layer_table = layer_props.get('layer_name')
        primary_key = layer_props.get('primary_key_name')
        geom_field = layer_props.get('layer_geometry_field')
        layer_schema = layer_props.get('layer_schema')
        
        # Validate required fields
        if not all([layer_table, primary_key, geom_field]):
            logger.error(f"Missing required fields in layer_props for {layer_name}: "
                       f"name={layer_table}, pk={primary_key}, geom={geom_field}")
            return None, None, None, None
        
        return layer_table, primary_key, geom_field, layer_schema

    def _build_backend_expression(self, backend, layer_props, source_geom):
        """
        Build filter expression using backend.
        
        Args:
            backend: Backend instance
            layer_props: Layer properties dict
            source_geom: Prepared source geometry
            
        Returns:
            str: Filter expression or None on error
        """
        expression = backend.build_expression(
            layer_props=layer_props,
            predicates=self.current_predicates,
            source_geom=source_geom,
            buffer_value=self.param_buffer_value if hasattr(self, 'param_buffer_value') else None,
            buffer_expression=self.param_buffer_expression if hasattr(self, 'param_buffer_expression') else None
        )
        
        if not expression:
            logger.warning(f"No expression generated by backend")
            return None
        
        return expression

    def _combine_with_old_filter(self, expression, layer):
        """
        Combine new expression with existing subset if needed.
        
        Args:
            expression: New filter expression
            layer: QGIS vector layer
            
        Returns:
            str: Final combined expression
        """
        old_subset = layer.subsetString() if layer.subsetString() != '' else None
        combine_operator = self._get_combine_operator()
        
        if old_subset and combine_operator:
            return f"({old_subset}) {combine_operator} ({expression})"
        
        return expression

    def execute_geometric_filtering(self, layer_provider_type, layer, layer_props):
        """
        Execute geometric filtering on layer using spatial predicates.
        
        FIXED: Corrected layer_props access pattern - layer_props IS the infos dict,
        not a wrapper containing it. Uses correct key names and proper validation.
        
        Args:
            layer_provider_type: Provider type ('postgresql', 'spatialite', 'ogr')
            layer: QgsVectorLayer to filter
            layer_props: Dict containing layer info (IS the infos dict directly)
            
        Returns:
            bool: True if filtering succeeded, False otherwise
        """
        try:
            logger.info(f"Executing geometric filtering for {layer.name()} ({layer_provider_type})")
            
            # Validate layer properties
            layer_name, primary_key, geom_field, layer_schema = self._validate_layer_properties(
                layer_props, 
                layer.name()
            )
            if not layer_name:
                return False
            
            # Verify spatial index exists before filtering - critical for performance
            self._verify_and_create_spatial_index(layer, layer_name)
            
            # Get appropriate backend for this layer
            backend = BackendFactory.get_backend(layer_provider_type, layer, self.task_parameters)
            
            # Prepare source geometry based on backend type
            source_geom = self._prepare_source_geometry(layer_provider_type)
            if not source_geom:
                logger.error(f"Failed to prepare source geometry for {layer.name()}")
                return False
            
            # Build filter expression using backend
            expression = self._build_backend_expression(backend, layer_props, source_geom)
            if not expression:
                logger.warning(f"No expression generated for {layer.name()}")
                return False
            
            # Combine with old subset if needed
            final_expression = self._combine_with_old_filter(expression, layer)
            logger.debug(f"Final filter expression for {layer.name()}: {final_expression}")
            
            # Apply filter using thread-safe method
            result = self._safe_set_subset_string(layer, final_expression)
            
            if result:
                # Store subset string for history/undo functionality
                self.manage_layer_subset_strings(
                    layer,
                    final_expression,
                    primary_key,
                    geom_field,
                    False
                )
                feature_count = layer.featureCount()
                logger.info(f"✓ Successfully filtered {layer.name()}: {feature_count:,} features match")
            else:
                logger.error(f"✗ Failed to apply filter to {layer.name()}")
            
            return result
            
        except Exception as e:
            safe_log(logger, logging.ERROR, f"Error in execute_geometric_filtering for {layer.name()}: {e}", exc_info=True)
            return False
    
    def _get_combine_operator(self):
        """
        Get SQL operator for combining with existing filters.
        
        Returns:
            str: 'AND', 'OR', 'INTERSECT', 'UNION', 'EXCEPT', or None
        """
        if not hasattr(self, 'has_combine_operator') or not self.has_combine_operator:
            return None
        
        operator_map = {
            'AND': 'INTERSECT',
            'AND NOT': 'EXCEPT',
            'OR': 'UNION'
        }
        
        other_op = getattr(self, 'param_other_layers_combine_operator', None)
        return operator_map.get(other_op, other_op)
    
    def _prepare_source_geometry(self, layer_provider_type):
        """
        Prepare source geometry expression based on provider type.
        
        Args:
            layer_provider_type: Target layer provider type
        
        Returns:
            Source geometry (type depends on provider):
            - PostgreSQL: SQL expression string
            - Spatialite: WKT string  
            - OGR: QgsVectorLayer
        """
        if layer_provider_type == PROVIDER_POSTGRES and POSTGRESQL_AVAILABLE:
            if hasattr(self, 'postgresql_source_geom'):
                return self.postgresql_source_geom
        
        # For Spatialite, return WKT string
        if layer_provider_type == PROVIDER_SPATIALITE:
            if hasattr(self, 'spatialite_source_geom'):
                return self.spatialite_source_geom
        
        # For OGR, return the source layer
        if hasattr(self, 'ogr_source_geom'):
            return self.ogr_source_geom
        
        # Fallback: return source layer
        if hasattr(self, 'source_layer'):
            return self.source_layer
        
        return None

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

        self.manage_layer_subset_strings(self.source_layer, None, self.primary_key_name, self.param_source_geom, False)
        self.setProgress((i/self.layers_count)*100)

        for layer_provider_type in self.layers:
            for layer, layer_props in self.layers[layer_provider_type]:
                self.manage_layer_subset_strings(layer, None, layer_props["primary_key_name"], layer_props["layer_geometry_field"], False)
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




    def _validate_export_parameters(self):
        """
        Validate and extract export parameters from task configuration.
        
        Returns:
            dict: Export configuration or None if validation fails
                {
                    'layers': list of layer names,
                    'projection': QgsCoordinateReferenceSystem or None,
                    'styles': style format (e.g., 'qml', 'sld') or None,
                    'datatype': export format (e.g., 'GPKG', 'ESRI Shapefile'),
                    'output_folder': output directory path,
                    'zip_path': zip file path or None
                }
        """
        config = self.task_parameters["task"]['EXPORTING']
        
        # Validate layers
        if not config.get("HAS_LAYERS_TO_EXPORT", False):
            logger.error("No layers selected for export")
            return None
        
        layers = self.task_parameters["task"].get("layers")
        if not layers or len(layers) == 0:
            logger.error("Empty layers list for export")
            return None
        
        # Validate datatype
        if not config.get("HAS_DATATYPE_TO_EXPORT", False):
            logger.error("No export datatype specified")
            return None
        
        datatype = config.get("DATATYPE_TO_EXPORT")
        if not datatype:
            logger.error("Export datatype is empty")
            return None
        
        # Extract optional parameters
        projection = None
        if config.get("HAS_PROJECTION_TO_EXPORT", False):
            proj_wkt = config.get("PROJECTION_TO_EXPORT")
            if proj_wkt:
                crs = QgsCoordinateReferenceSystem()
                crs.createFromWkt(proj_wkt)
                projection = crs
        
        styles = None
        if config.get("HAS_STYLES_TO_EXPORT", False):
            styles_raw = config.get("STYLES_TO_EXPORT")
            if styles_raw:
                styles = styles_raw.lower()
        
        output_folder = ENV_VARS["PATH_ABSOLUTE_PROJECT"]
        if config.get("HAS_OUTPUT_FOLDER_TO_EXPORT", False):
            folder = config.get("OUTPUT_FOLDER_TO_EXPORT")
            if folder:
                output_folder = folder
        
        zip_path = None
        if config.get("HAS_ZIP_TO_EXPORT", False):
            zip_path = config.get("ZIP_TO_EXPORT")
        
        return {
            'layers': layers,
            'projection': projection,
            'styles': styles,
            'datatype': datatype,
            'output_folder': output_folder,
            'zip_path': zip_path
        }


    def _get_layer_by_name(self, layer_name):
        """
        Get layer object from project by name.
        
        Args:
            layer_name: Layer name to search for
            
        Returns:
            QgsVectorLayer or None if not found
        """
        layers_found = self.PROJECT.mapLayersByName(layer_name)
        if layers_found:
            return layers_found[0]
        logger.warning(f"Layer '{layer_name}' not found in project")
        return None


    def _save_layer_style(self, layer, output_path, style_format, datatype):
        """
        Save layer style to file if format supports it.
        
        Args:
            layer: QgsVectorLayer
            output_path: Base path for export (without extension)
            style_format: Style file format (e.g., 'qml', 'sld')
            datatype: Export datatype (to check if styles are supported)
        """
        if datatype == 'XLSX' or not style_format:
            return
        
        style_path = os.path.normcase(f"{output_path}.{style_format}")
        try:
            layer.saveNamedStyle(style_path)
            logger.debug(f"Style saved: {style_path}")
        except Exception as e:
            logger.warning(f"Could not save style for '{layer.name()}': {e}")


    def _export_single_layer(self, layer, output_path, projection, datatype, style_format, save_styles):
        """
        Export a single layer to file.
        
        Args:
            layer: QgsVectorLayer to export
            output_path: Output file path (without extension for some formats)
            projection: Target CRS or None to use layer's CRS
            datatype: Export format (e.g., 'ESRI Shapefile', 'GeoJSON')
            style_format: Style file format or None
            save_styles: Whether to save layer styles
            
        Returns:
            bool: True if successful
        """
        current_projection = projection if projection else layer.sourceCrs()
        
        logger.debug(f"Exporting layer '{layer.name()}' to {output_path}")
        
        try:
            result = QgsVectorFileWriter.writeAsVectorFormat(
                layer,
                os.path.normcase(output_path),
                "UTF-8",
                current_projection,
                datatype
            )
            
            if result[0] != QgsVectorFileWriter.NoError:
                logger.error(f"Export failed for layer '{layer.name()}': {result[1]}")
                return False
            
            # Save style if requested
            if save_styles:
                self._save_layer_style(layer, output_path, style_format, datatype)
            
            return True
            
        except Exception as e:
            logger.error(f"Export exception for layer '{layer.name()}': {e}")
            return False


    def _export_to_gpkg(self, layer_names, output_path, save_styles):
        """
        Export layers to GeoPackage format using QGIS processing.
        
        Args:
            layer_names: List of layer names to export
            output_path: Output GPKG file path
            save_styles: Whether to include layer styles
            
        Returns:
            bool: True if successful
        """
        logger.info(f"Exporting {len(layer_names)} layer(s) to GPKG: {output_path}")
        
        # Collect layer objects
        layer_objects = []
        for layer_name in layer_names:
            layer = self._get_layer_by_name(layer_name)
            if layer:
                layer_objects.append(layer)
        
        if not layer_objects:
            logger.error("No valid layers found for GPKG export")
            return False
        
        alg_parameters = {
            'LAYERS': layer_objects,
            'OVERWRITE': True,
            'SAVE_STYLES': save_styles,
            'OUTPUT': output_path
        }
        
        try:
            # processing.run() is thread-safe for file operations
            output = processing.run("qgis:package", alg_parameters)
            
            if not output or 'OUTPUT' not in output:
                logger.error("GPKG export failed: no output returned")
                return False
            
            logger.info(f"GPKG export successful: {output['OUTPUT']}")
            return True
            
        except Exception as e:
            logger.error(f"GPKG export failed with exception: {e}")
            return False


    def _export_multiple_layers_to_directory(self, layer_names, output_folder, projection, datatype, style_format, save_styles):
        """
        Export multiple layers to a directory (one file per layer).
        
        Updates task description to show export progress.
        
        Args:
            layer_names: List of layer names to export
            output_folder: Output directory path
            projection: Target CRS or None
            datatype: Export format
            style_format: Style file format or None
            save_styles: Whether to save layer styles
            
        Returns:
            bool: True if all exports successful
        """
        logger.info(f"Exporting {len(layer_names)} layer(s) to {datatype} in directory {output_folder}")
        
        total_layers = len(layer_names)
        for idx, layer_name in enumerate(layer_names, 1):
            # Update task description with current progress
            self.setDescription(f"Exporting layer {idx}/{total_layers}: {layer_name}")
            self.setProgress(int((idx / total_layers) * 90))  # Reserve 90% for export, 10% for zip
            
            layer = self._get_layer_by_name(layer_name)
            if not layer:
                continue
            
            output_path = os.path.join(output_folder, layer_name)
            success = self._export_single_layer(
                layer, output_path, projection, datatype, style_format, save_styles
            )
            
            if not success:
                return False
            
            if self.isCanceled():
                logger.info("Export cancelled by user")
                return False
        
        return True


    def _create_zip_archive(self, zip_path, folder_to_zip):
        """
        Create a zip archive of the exported folder.
        
        Updates task description to show compression progress.
        
        Args:
            zip_path: Output zip file path
            folder_to_zip: Folder to compress
            
        Returns:
            bool: True if successful
        """
        directory, zipfile = os.path.split(folder_to_zip)
        if not os.path.exists(directory) or not os.path.isdir(directory):
            logger.error(f"Directory does not exist: {directory}")
            return False
        
        self.setDescription(f"Creating zip archive...")
        self.setProgress(95)
        
        logger.info(f"Creating zip archive: {zip_path}")
        try:
            result = self.zipfolder(zip_path, folder_to_zip)
            if self.isCanceled() or result is False:
                logger.warning("Zip creation failed or cancelled")
                return False
            
            self.setProgress(100)
            logger.info("Zip archive created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Zip creation failed: {e}")
            return False

    def execute_exporting(self):
        """
        Export selected layers to specified format with optional styles.
        
        REFACTORED: Decomposed from 235 lines to ~65 lines using helper methods.
        Main method now validates parameters and orchestrates export workflow.
        
        Returns:
            bool: True if export successful
        """
        # Validate and extract export parameters
        export_config = self._validate_export_parameters()
        if not export_config:
            return False
        
        layers = export_config['layers']
        projection = export_config['projection']
        datatype = export_config['datatype']
        output_folder = export_config['output_folder']
        style_format = export_config['styles']
        zip_path = export_config['zip_path']
        save_styles = self.task_parameters["task"]['EXPORTING'].get("HAS_STYLES_TO_EXPORT", False)
        
        # Execute export based on format
        export_success = False
        
        if datatype == 'GPKG':
            # GeoPackage export using processing
            export_success = self._export_to_gpkg(layers, output_folder, save_styles)
        else:
            # Other formats (Shapefile, GeoJSON, etc.)
            if not os.path.exists(output_folder):
                logger.error(f"Output path does not exist: {output_folder}")
                return False
            
            if os.path.isdir(output_folder) and len(layers) > 1:
                # Multiple layers to directory
                export_success = self._export_multiple_layers_to_directory(
                    layers, output_folder, projection, datatype, style_format, save_styles
                )
            elif len(layers) == 1:
                # Single layer export
                layer = self._get_layer_by_name(layers[0])
                if not layer:
                    return False
                
                export_success = self._export_single_layer(
                    layer, output_folder, projection, datatype, style_format, save_styles
                )
            else:
                logger.error(f"Invalid export configuration: {len(layers)} layers but output is not a directory")
                return False
        
        if not export_success:
            return False
        
        if self.isCanceled():
            logger.info("Export cancelled by user before zip")
            return False
        
        # Create zip archive if requested
        zip_created = False
        if zip_path:
            zip_created = self._create_zip_archive(zip_path, output_folder)
            if not zip_created:
                return False
        
        # Build success message
        self.message = f'Layer(s) has been exported to <a href="file:///{output_folder}">{output_folder}</a>'
        if zip_created:
            self.message += f' and Zip file has been exported to <a href="file:///{zip_path}">{zip_path}</a>'
        
        logger.info("Export completed successfully")
        return True

    def _get_spatialite_datasource(self, layer):
        """
        Get Spatialite datasource information from layer.
        
        Falls back to filterMate database for non-Spatialite layers.
        
        Args:
            layer: QGIS vector layer
            
        Returns:
            tuple: (db_path, table_name, layer_srid, is_native_spatialite)
        """
        from .appUtils import get_spatialite_datasource_from_layer
        
        # Get Spatialite datasource
        db_path, table_name = get_spatialite_datasource_from_layer(layer)
        layer_srid = layer.crs().postgisSrid()
        
        # Check if native Spatialite or OGR/Shapefile
        is_native_spatialite = db_path is not None
        
        if not is_native_spatialite:
            # Use filterMate_db for temp storage
            db_path = self.db_file_path
            logger.info("Non-Spatialite layer detected, will use QGIS subset string")
        
        return db_path, table_name, layer_srid, is_native_spatialite

    def _build_spatialite_query(self, sql_subset_string, table_name, geom_key_name, 
                                primary_key_name, custom):
        """
        Build Spatialite query for simple or complex (buffered) subsets.
        
        Args:
            sql_subset_string: SQL query for subset
            table_name: Source table name
            geom_key_name: Geometry field name
            primary_key_name: Primary key field name
            custom: Whether custom buffer expression is used
            
        Returns:
            str: Spatialite SELECT query
        """
        if custom is False:
            # Simple subset - use query as-is
            return sql_subset_string
        
        # Complex subset with buffer (adapt from PostgreSQL logic)
        buffer_expr = (
            self.qgis_expression_to_spatialite(self.param_buffer_expression) 
            if self.param_buffer_expression 
            else str(self.param_buffer_value)
        )
        
        # Build Spatialite SELECT (similar to PostgreSQL CREATE MATERIALIZED VIEW)
        # Note: Spatialite uses same ST_Buffer syntax as PostGIS
        query = f"""
            SELECT 
                ST_Buffer({geom_key_name}, {buffer_expr}) as {geom_key_name},
                {primary_key_name},
                {buffer_expr} as buffer_value
            FROM {table_name}
            WHERE {primary_key_name} IN ({sql_subset_string})
        """
        
        return query

    def _apply_spatialite_subset(self, layer, name, primary_key_name, sql_subset_string, 
                                 cur, conn, current_seq_order):
        """
        Apply subset string to layer and update history.
        
        Args:
            layer: QGIS vector layer
            name: Temp table name
            primary_key_name: Primary key field name
            sql_subset_string: Original SQL subset string for history
            cur: Spatialite cursor for history
            conn: Spatialite connection for history
            current_seq_order: Sequence order for history
            
        Returns:
            bool: True if successful
        """
        # Apply subset string to layer (reference temp table)
        layer_subsetString = f'"{primary_key_name}" IN (SELECT "{primary_key_name}" FROM mv_{name})'
        logger.debug(f"Applying Spatialite subset string: {layer_subsetString}")
        
        # CRITICAL FIX: Thread-safe subset string application
        result = self._safe_set_subset_string(layer, layer_subsetString)
        
        if not result:
            logger.error("Failed to apply Spatialite subset string")
            return False
        
        # Update history
        if cur and conn:
            cur.execute("""INSERT INTO fm_subset_history VALUES('{id}', datetime(), '{fk_project}', '{layer_id}', '{layer_source_id}', {seq_order}, '{subset_string}');""".format(
                id=uuid.uuid4(),
                fk_project=self.project_uuid,
                layer_id=layer.id(),
                layer_source_id=self.source_layer.id(),
                seq_order=current_seq_order,
                subset_string=sql_subset_string.replace("\'","\'\'")
            ))
            conn.commit()
        
        return True

    def _manage_spatialite_subset(self, layer, sql_subset_string, primary_key_name, geom_key_name, 
                                   name, custom=False, cur=None, conn=None, current_seq_order=0):
        """
        Handle Spatialite temporary tables for filtering (Phase 2 implementation).
        
        Alternative to PostgreSQL materialized views using create_temp_spatialite_table().
        
        Args:
            layer: QGIS vector layer
            sql_subset_string: SQL query for subset
            primary_key_name: Primary key field name
            geom_key_name: Geometry field name
            name: Unique name for temp table
            custom: Whether custom buffer expression is used
            cur: Spatialite cursor for history
            conn: Spatialite connection for history
            current_seq_order: Sequence order for history
            
        Returns:
            bool: True if successful
        """
        from .appUtils import create_temp_spatialite_table
        
        # Get datasource information
        db_path, table_name, layer_srid, is_native_spatialite = self._get_spatialite_datasource(layer)
        
        # For non-Spatialite layers, use QGIS subset string directly
        if not is_native_spatialite:
            return self._safe_set_subset_string(layer, sql_subset_string)
        
        # Build Spatialite query (simple or buffered)
        spatialite_query = self._build_spatialite_query(
            sql_subset_string, 
            table_name, 
            geom_key_name, 
            primary_key_name, 
            custom
        )
        
        # Create temporary table
        logger.info(f"Creating Spatialite temp table 'mv_{name}'")
        success = create_temp_spatialite_table(
            db_path=db_path,
            table_name=name,
            sql_query=spatialite_query,
            geom_field=geom_key_name,
            srid=layer_srid
        )
        
        if not success:
            logger.error("Failed to create Spatialite temp table")
            # NOTE: Cannot call iface.messageBar() from worker thread - would cause crash
            # Error is logged and will be handled in finished() method
            return False
        
        # Apply subset and update history
        return self._apply_spatialite_subset(
            layer, 
            name, 
            primary_key_name, 
            sql_subset_string, 
            cur, 
            conn, 
            current_seq_order
        )


    def _get_last_subset_info(self, cur, layer):
        """
        Get the last subset information for a layer from history.
        
        Args:
            cur: Database cursor
            layer: QgsVectorLayer
            
        Returns:
            tuple: (last_subset_id, last_seq_order, layer_name, name)
        """
        layer_name = layer.name()
        name = layer.id().replace(layer_name, '').replace('-', '_')
        
        cur.execute(
            """SELECT * FROM fm_subset_history 
               WHERE fk_project = '{fk_project}' AND layer_id = '{layer_id}' 
               ORDER BY seq_order DESC LIMIT 1;""".format(
                fk_project=self.project_uuid,
                layer_id=layer.id()
            )
        )
        
        results = cur.fetchall()
        if len(results) == 1:
            result = results[0]
            return result[0], result[5], layer_name, name
        else:
            return None, 0, layer_name, name


    def _determine_backend(self, layer):
        """
        Determine which backend to use for layer operations.
        
        Args:
            layer: QgsVectorLayer
            
        Returns:
            tuple: (provider_type, use_postgresql, use_spatialite)
        """
        provider_type = detect_layer_provider_type(layer)
        use_postgresql = (provider_type == PROVIDER_POSTGRES and POSTGRESQL_AVAILABLE)
        use_spatialite = (provider_type in [PROVIDER_SPATIALITE, PROVIDER_OGR] or not use_postgresql)
        
        logger.debug(f"Provider={provider_type}, PostgreSQL={use_postgresql}, Spatialite={use_spatialite}")
        return provider_type, use_postgresql, use_spatialite


    def _log_performance_warning_if_needed(self, use_spatialite, layer):
        """
        Log performance warning for large Spatialite datasets.
        
        Note: Cannot call iface.messageBar() from worker thread - would cause crash.
        
        Args:
            use_spatialite: Whether Spatialite backend is used
            layer: QgsVectorLayer
        """
        if use_spatialite and layer.featureCount() > 50000:
            logger.warning(
                f"Large dataset ({layer.featureCount():,} features) using Spatialite backend. "
                f"Filtering may take longer. For optimal performance with large datasets, consider using PostgreSQL."
            )


    def _create_simple_materialized_view_sql(self, schema, name, sql_subset_string):
        """
        Create SQL for simple materialized view (non-custom buffer).
        
        Args:
            schema: PostgreSQL schema name
            name: Layer identifier
            sql_subset_string: SQL SELECT statement
            
        Returns:
            str: SQL CREATE MATERIALIZED VIEW statement
        """
        return 'CREATE MATERIALIZED VIEW IF NOT EXISTS "{schema}"."mv_{name}" TABLESPACE pg_default AS {sql_subset_string} WITH DATA;'.format(
            schema=schema,
            name=name,
            sql_subset_string=sql_subset_string
        )


    def _create_custom_buffer_view_sql(self, schema, name, geom_key_name, where_clause_fields_arr, last_subset_id, sql_subset_string):
        """
        Create SQL for custom buffer materialized view.
        
        Args:
            schema: PostgreSQL schema name
            name: Layer identifier
            geom_key_name: Geometry field name
            where_clause_fields_arr: List of WHERE clause fields
            last_subset_id: Previous subset ID (None if first)
            sql_subset_string: SQL SELECT statement for source
            
        Returns:
            str: SQL CREATE MATERIALIZED VIEW statement
        """
        # Common parts
        postgresql_source_geom = self.postgresql_source_geom
        if self.has_to_reproject_source_layer:
            postgresql_source_geom = f'ST_Transform({postgresql_source_geom}, {self.source_layer_crs_authid.split(":")[1]})'
        
        template = '''CREATE MATERIALIZED VIEW IF NOT EXISTS "{schema}"."mv_{name}" TABLESPACE pg_default AS 
            SELECT ST_Buffer({postgresql_source_geom}, {param_buffer_expression}) as {geometry_field}, 
                   "{table_source}"."{primary_key_name}", 
                   {where_clause_fields}, 
                   {param_buffer_expression} as buffer_value 
            FROM "{schema_source}"."{table_source}" 
            WHERE "{table_source}"."{primary_key_name}" IN (SELECT sub."{primary_key_name}" FROM {source_new_subset} sub) 
              AND {where_expression} 
            WITH DATA;'''
        
        return template.format(
            schema=schema,
            name=name,
            postgresql_source_geom=postgresql_source_geom,
            geometry_field=geom_key_name,
            schema_source=self.param_source_schema,
            primary_key_name=self.primary_key_name,
            table_source=self.param_source_table,
            where_clause_fields=','.join(where_clause_fields_arr).replace('mv_', ''),
            param_buffer_expression=self.param_buffer.replace('mv_', ''),
            source_new_subset=sql_subset_string,
            where_expression=' OR '.join(self._parse_where_clauses()).replace('mv_', '')
        )


    def _parse_where_clauses(self):
        """
        Parse CASE statement into WHERE clause array.
        
        Returns:
            list: List of WHERE clause strings
        """
        where_clause = self.where_clause.replace('CASE', '').replace('END', '').replace('IF', '').replace('ELSE', '').replace('\r', ' ').replace('\n', ' ')
        where_clauses_in_arr = where_clause.split('WHEN')
        
        where_clause_out_arr = []
        for where_then_clause in where_clauses_in_arr:
            if len(where_then_clause.split('THEN')) >= 1:
                clause = where_then_clause.split('THEN')[0].replace('WHEN', ' ').strip()
                if clause:
                    where_clause_out_arr.append(clause)
        
        return where_clause_out_arr


    def _execute_postgresql_commands(self, connexion, commands):
        """
        Execute PostgreSQL commands with automatic reconnection on failure.
        
        Args:
            connexion: psycopg2 connection
            commands: List of SQL commands to execute
            
        Returns:
            bool: True if all commands succeeded
        """
        # Test connection
        try:
            with connexion.cursor() as cursor:
                cursor.execute("SELECT 1")
        except (psycopg2.OperationalError, psycopg2.InterfaceError, AttributeError) as e:
            logger.debug(f"PostgreSQL connection test failed, reconnecting: {e}")
            connexion, _ = get_datasource_connexion_from_layer(self.source_layer)
        
        # Execute commands
        with connexion.cursor() as cursor:
            for command in commands:
                cursor.execute(command)
                connexion.commit()
        
        return True


    def _insert_subset_history(self, cur, conn, layer, sql_subset_string, seq_order):
        """
        Insert subset history record into database.
        
        Args:
            cur: Database cursor
            conn: Database connection
            layer: QgsVectorLayer
            sql_subset_string: SQL subset string
            seq_order: Sequence order number
        """
        cur.execute(
            """INSERT INTO fm_subset_history 
               VALUES('{id}', datetime(), '{fk_project}', '{layer_id}', '{layer_source_id}', {seq_order}, '{subset_string}');""".format(
                id=uuid.uuid4(),
                fk_project=self.project_uuid,
                layer_id=layer.id(),
                layer_source_id=self.source_layer.id(),
                seq_order=seq_order,
                subset_string=sql_subset_string.replace("'", "''")
            )
        )
        conn.commit()


    def _filter_action_postgresql(self, layer, sql_subset_string, primary_key_name, geom_key_name, name, custom, cur, conn, seq_order):
        """
        Execute filter action using PostgreSQL backend.
        
        Args:
            layer: QgsVectorLayer to filter
            sql_subset_string: SQL SELECT statement
            primary_key_name: Primary key field name
            geom_key_name: Geometry field name
            name: Layer identifier
            custom: Whether this is a custom buffer filter
            cur: Database cursor
            conn: Database connection
            seq_order: Sequence order number
            
        Returns:
            bool: True if successful
        """
        schema = self.current_materialized_view_schema
        
        # Build SQL commands
        sql_drop = f'DROP INDEX IF EXISTS {schema}_{name}_cluster CASCADE; DROP MATERIALIZED VIEW IF EXISTS "{schema}"."mv_{name}" CASCADE;'
        
        if custom:
            # Parse custom buffer expression
            sql_drop += f' DROP MATERIALIZED VIEW IF EXISTS "{schema}"."mv_{name}_dump" CASCADE;'
            
            # Get previous subset if exists
            cur.execute(
                f"""SELECT * FROM fm_subset_history 
                    WHERE fk_project = '{self.project_uuid}' AND layer_id = '{layer.id()}' 
                    ORDER BY seq_order DESC LIMIT 1;"""
            )
            results = cur.fetchall()
            last_subset_id = results[0][0] if len(results) == 1 else None
            
            # Parse WHERE clauses
            self.where_clause = self.param_buffer_expression.replace('CASE', '').replace('END', '').replace('IF', '').replace('ELSE', '').replace('\r', ' ').replace('\n', ' ')
            where_clauses = self._parse_where_clauses()
            where_clause_fields_arr = [clause.split(' ')[0] for clause in where_clauses]
            
            sql_create = self._create_custom_buffer_view_sql(schema, name, geom_key_name, where_clause_fields_arr, last_subset_id, sql_subset_string)
        else:
            sql_create = self._create_simple_materialized_view_sql(schema, name, sql_subset_string)
        
        sql_create_index = f'CREATE INDEX IF NOT EXISTS {schema}_{name}_cluster ON "{schema}"."mv_{name}" USING GIST ({geom_key_name});'
        sql_cluster = f'ALTER MATERIALIZED VIEW IF EXISTS  "{schema}"."mv_{name}" CLUSTER ON {schema}_{name}_cluster;'
        sql_analyze = f'ANALYZE VERBOSE "{schema}"."mv_{name}";'
        
        sql_create = sql_create.replace('\n', '').replace('\t', '').replace('  ', ' ').strip()
        logger.debug(f"SQL drop request: {sql_drop}")
        logger.debug(f"SQL create request: {sql_create}")
        
        # Execute PostgreSQL commands
        connexion = self.task_parameters["task"]["options"]["ACTIVE_POSTGRESQL"]
        commands = [sql_drop, sql_create, sql_create_index, sql_cluster, sql_analyze]
        
        if custom:
            sql_dump = f'CREATE MATERIALIZED VIEW IF NOT EXISTS "{schema}"."mv_{name}_dump" as SELECT ST_Union("{geom_key_name}") as {geom_key_name} from "{schema}"."mv_{name}";'
            commands.append(sql_dump)
        
        self._execute_postgresql_commands(connexion, commands)
        
        # Insert history
        self._insert_subset_history(cur, conn, layer, sql_subset_string, seq_order)
        
        # Set subset string on layer
        layer_subset_string = f'"{primary_key_name}" IN (SELECT "mv_{name}"."{primary_key_name}" FROM "{schema}"."mv_{name}")'
        logger.debug(f"Layer subset string: {layer_subset_string}")
        self._safe_set_subset_string(layer, layer_subset_string)
        
        return True


    def _reset_action_postgresql(self, layer, name, cur, conn):
        """
        Execute reset action using PostgreSQL backend.
        
        Args:
            layer: QgsVectorLayer to reset
            name: Layer identifier
            cur: Database cursor
            conn: Database connection
            
        Returns:
            bool: True if successful
        """
        # Delete history
        cur.execute(
            f"""DELETE FROM fm_subset_history 
                WHERE fk_project = '{self.project_uuid}' AND layer_id = '{layer.id()}';"""
        )
        conn.commit()
        
        # Drop materialized view
        schema = self.current_materialized_view_schema
        sql_drop = f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."mv_{name}" CASCADE;'
        
        connexion = self.task_parameters["task"]["options"]["ACTIVE_POSTGRESQL"]
        self._execute_postgresql_commands(connexion, [sql_drop])
        
        # Clear subset string
        self._safe_set_subset_string(layer, '')
        return True


    def _reset_action_spatialite(self, layer, name, cur, conn):
        """
        Execute reset action using Spatialite backend.
        
        Args:
            layer: QgsVectorLayer to reset
            name: Layer identifier
            cur: Database cursor
            conn: Database connection
            
        Returns:
            bool: True if successful
        """
        logger.info("Reset - Spatialite backend - dropping temp table")
        
        # Delete history
        cur.execute(
            f"""DELETE FROM fm_subset_history 
                WHERE fk_project = '{self.project_uuid}' AND layer_id = '{layer.id()}';"""
        )
        conn.commit()
        
        # Drop temp table from filterMate_db
        import sqlite3
        try:
            temp_conn = sqlite3.connect(self.db_file_path)
            temp_cur = temp_conn.cursor()
            temp_cur.execute(f"DROP TABLE IF EXISTS mv_{name}")
            temp_conn.commit()
            temp_cur.close()
            temp_conn.close()
        except Exception as e:
            logger.error(f"Error dropping Spatialite temp table: {e}")
        
        # Clear subset string
        self._safe_set_subset_string(layer, '')
        return True


    def _unfilter_action(self, layer, primary_key_name, geom_key_name, name, custom, cur, conn, last_subset_id, use_postgresql, use_spatialite):
        """
        Execute unfilter action (restore previous filter state).
        
        Args:
            layer: QgsVectorLayer to unfilter
            primary_key_name: Primary key field name
            geom_key_name: Geometry field name
            name: Layer identifier
            custom: Whether this is a custom buffer filter
            cur: Database cursor
            conn: Database connection
            last_subset_id: Last subset ID to remove
            use_postgresql: Whether to use PostgreSQL backend
            use_spatialite: Whether to use Spatialite backend
            
        Returns:
            bool: True if successful
        """
        # Delete last subset from history
        if last_subset_id:
            cur.execute(
                f"""DELETE FROM fm_subset_history 
                    WHERE fk_project = '{self.project_uuid}' 
                      AND layer_id = '{layer.id()}' 
                      AND id = '{last_subset_id}';"""
            )
            conn.commit()
        
        # Get previous subset
        cur.execute(
            f"""SELECT * FROM fm_subset_history 
                WHERE fk_project = '{self.project_uuid}' AND layer_id = '{layer.id()}' 
                ORDER BY seq_order DESC LIMIT 1;"""
        )
        
        results = cur.fetchall()
        if len(results) == 1:
            sql_subset_string = results[0][-1]
            
            if use_spatialite:
                logger.info("Unfilter - Spatialite backend - recreating previous subset")
                success = self._manage_spatialite_subset(
                    layer, sql_subset_string, primary_key_name, geom_key_name,
                    name, custom=False, cur=None, conn=None, current_seq_order=0
                )
                if not success:
                    self._safe_set_subset_string(layer, '')
            
            elif use_postgresql:
                schema = self.current_materialized_view_schema
                sql_drop = f'DROP INDEX IF EXISTS {schema}_{name}_cluster CASCADE; DROP MATERIALIZED VIEW IF EXISTS "{schema}"."mv_{name}" CASCADE;'
                sql_create = self._create_simple_materialized_view_sql(schema, name, sql_subset_string)
                sql_create_index = f'CREATE INDEX IF NOT EXISTS {schema}_{name}_cluster ON "{schema}"."mv_{name}" USING GIST ({geom_key_name});'
                sql_cluster = f'ALTER MATERIALIZED VIEW IF EXISTS  "{schema}"."mv_{name}" CLUSTER ON {schema}_{name}_cluster;'
                sql_analyze = f'ANALYZE VERBOSE "{schema}"."mv_{name}";'
                
                sql_create = sql_create.replace('\n', '').replace('\t', '').replace('  ', ' ').strip()
                
                connexion = self.task_parameters["task"]["options"]["ACTIVE_POSTGRESQL"]
                self._execute_postgresql_commands(connexion, [sql_drop, sql_create, sql_create_index, sql_cluster, sql_analyze])
                
                layer_subset_string = f'"{primary_key_name}" IN (SELECT "mv_{name}"."{primary_key_name}" FROM "{schema}"."mv_{name}")'
                self._safe_set_subset_string(layer, layer_subset_string)
        else:
            self._safe_set_subset_string(layer, '')
        
        return True


    def manage_layer_subset_strings(self, layer, sql_subset_string=None, primary_key_name=None, geom_key_name=None, custom=False):
        """
        Manage layer subset strings using materialized views or temp tables.
        
        REFACTORED: Decomposed from 384 lines to ~60 lines using helper methods.
        Main method now orchestrates the process, delegates to specialized methods.
        
        Args:
            layer: QgsVectorLayer to manage
            sql_subset_string: SQL SELECT statement for filtering
            primary_key_name: Primary key field name
            geom_key_name: Geometry field name
            custom: Whether this is a custom buffer filter
            
        Returns:
            bool: True if successful
        """
        conn = None
        cur = None
        
        try:
            # Initialize database connection
            conn = self._safe_spatialite_connect()
            self.active_connections.append(conn)
            cur = conn.cursor()
            
            # Get layer info and history
            last_subset_id, last_seq_order, layer_name, name = self._get_last_subset_info(cur, layer)
            
            # Determine backend to use
            provider_type, use_postgresql, use_spatialite = self._determine_backend(layer)
            
            # Log performance warning if needed
            self._log_performance_warning_if_needed(use_spatialite, layer)
            
            # Execute appropriate action based on task_action
            if self.task_action == 'filter':
                current_seq_order = last_seq_order + 1
                
                # Use Spatialite backend for local layers
                if use_spatialite:
                    backend_name = "Spatialite" if provider_type == PROVIDER_SPATIALITE else "Local (OGR)"
                    logger.info(f"Using {backend_name} backend")
                    success = self._manage_spatialite_subset(
                        layer, sql_subset_string, primary_key_name, geom_key_name,
                        name, custom, cur, conn, current_seq_order
                    )
                    return success
                
                # Use PostgreSQL backend for remote layers
                return self._filter_action_postgresql(
                    layer, sql_subset_string, primary_key_name, geom_key_name,
                    name, custom, cur, conn, current_seq_order
                )
            
            elif self.task_action == 'reset':
                if use_spatialite:
                    return self._reset_action_spatialite(layer, name, cur, conn)
                elif use_postgresql:
                    return self._reset_action_postgresql(layer, name, cur, conn)
            
            elif self.task_action == 'unfilter':
                return self._unfilter_action(
                    layer, primary_key_name, geom_key_name, name, custom,
                    cur, conn, last_subset_id, use_postgresql, use_spatialite
                )
            
            return True
            
        finally:
            # Always cleanup connections
            if cur:
                try:
                    cur.close()
                except Exception as e:
                    logger.debug(f"Could not close database cursor: {e}")
            if conn:
                try:
                    conn.close()
                except Exception as e:
                    logger.debug(f"Could not close database connection: {e}")
                if conn in self.active_connections:
                    self.active_connections.remove(conn)



    def cancel(self):
        """Cancel task and cleanup all active database connections"""
        # Cleanup all active database connections
        for conn in self.active_connections[:]:
            try:
                conn.close()
            except Exception as e:
                # Log but don't fail - connection may already be closed
                logger.debug(f"Connection cleanup failed (may already be closed): {e}")
        self.active_connections.clear()
        
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

        self.json_template_layer_infos = '{"layer_geometry_type":"%s","layer_name":"%s","layer_id":"%s","layer_schema":"%s","is_already_subset":false,"layer_provider_type":"%s","layer_crs_authid":"%s","primary_key_name":"%s","primary_key_idx":%s,"primary_key_type":"%s","layer_geometry_field":"%s","primary_key_is_numeric":%s,"is_current_layer":false }'
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
                logger.error(f"Normalized path: {normalized_path}")
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
        self.project_layers = dict(OrderedDict(sorted(self.project_layers.items(), key = lambda layer: (getitem(layer[1]['infos'], 'layer_geometry_type'), getitem(layer[1]['infos'], 'layer_name')))))

        return True
    
    def _load_existing_layer_properties(self, layer):
        """
        Load existing layer properties from Spatialite database.
        
        Args:
            layer: QgsVectorLayer to load properties for
            
        Returns:
            dict: Dictionary with 'infos', 'exploring', 'filtering' keys, or empty dict if not found
        """
        spatialite_results = self.select_properties_from_spatialite(layer.id())
        expected_count = self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["LAYERS"]["LAYER_PROPERTIES_COUNT"]
        
        if not spatialite_results or len(spatialite_results) != expected_count:
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
        
        return existing_layer_variables

    def _migrate_legacy_geometry_field(self, layer_variables, layer):
        """
        Migrate old 'geometry_field' key to 'layer_geometry_field'.
        
        Args:
            layer_variables: Dictionary with layer properties
            layer: QgsVectorLayer being processed
        """
        infos = layer_variables.get("infos", {})
        
        if "geometry_field" in infos and "layer_geometry_field" not in infos:
            # Perform migration
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

    def _detect_layer_metadata(self, layer, layer_provider_type):
        """
        Detect layer-specific metadata (schema, geometry field) based on provider.
        
        Args:
            layer: QgsVectorLayer to analyze
            layer_provider_type: Provider type constant
            
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
        
        elif layer_provider_type == PROVIDER_SPATIALITE:
            geometry_field = 'GEOMETRY'
        
        elif layer_provider_type == PROVIDER_OGR:
            geometry_field = '_ogr_geometry_'
        
        return source_schema, geometry_field

    def _build_new_layer_properties(self, layer, primary_key_result):
        """
        Build property dictionaries for a new layer (not yet in database).
        
        Args:
            layer: QgsVectorLayer to build properties for
            primary_key_result: Tuple from search_primary_key_from_layer
            
        Returns:
            dict: Dictionary with 'infos', 'exploring', 'filtering' keys
        """
        primary_key_name, primary_key_idx, primary_key_type, primary_key_is_numeric = primary_key_result
        
        # Detect provider type and metadata
        layer_provider_type = detect_layer_provider_type(layer)
        source_schema, geometry_field = self._detect_layer_metadata(layer, layer_provider_type)
        
        # Convert geometry type using utility function
        layer_geometry_type = geometry_type_to_string(layer)
        
        # Build properties from JSON templates
        new_layer_variables = {}
        new_layer_variables["infos"] = json.loads(
            self.json_template_layer_infos % (
                layer_geometry_type, 
                layer.name(), 
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
            layer: QgsVectorLayer to set variables on
            layer_variables: Dictionary with 'infos', 'exploring', 'filtering' keys
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
            layer: QgsVectorLayer to index
            layer_props: Layer properties dictionary
        """
        if layer_props["infos"]["layer_provider_type"] == PROVIDER_POSTGRES:
            try:
                self.create_spatial_index_for_postgresql_layer(layer, layer_props)
            except (psycopg2.Error, AttributeError, KeyError) as e:
                logger.debug(f"Could not create spatial index for PostgreSQL layer {layer.id()}: {e}")
        else:
            self.create_spatial_index_for_layer(layer)

    def add_project_layer(self, layer):
        """
        Add a spatial layer to the project with all necessary metadata and indexes.
        
        Args:
            layer: QgsVectorLayer to add
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not isinstance(layer, QgsVectorLayer) or not layer.isSpatial():
            return False
        
        # Try to load existing properties from database
        layer_variables = self._load_existing_layer_properties(layer)
        
        if layer_variables:
            # Layer exists in database - apply migration if needed
            self._migrate_legacy_geometry_field(layer_variables, layer)
        else:
            # New layer - search for primary key and build properties
            result = self.search_primary_key_from_layer(layer)
            if self.isCanceled() or result is False:
                return False
            
            if not isinstance(result, tuple) or len(list(result)) != 4:
                return False
            
            # Build properties for new layer
            layer_variables = self._build_new_layer_properties(layer, result)
            
            # Set QGIS layer variables
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

        if isinstance(layer_id, str):

            self.save_variables_from_layer(layer_id)    
            self.save_style_from_layer_id(layer_id)

            del self.project_layers[layer_id]

            return True

        

    def search_primary_key_from_layer(self, layer):
        """For each layer we search the primary key"""

        # Cache feature count - expensive operation that was being called repeatedly
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
                
        new_field = QgsField('virtual_id', QVariant.LongLong)
        layer.addExpressionField('@row_number', new_field)

        return ('virtual_id', layer.fields().indexFromName('virtual_id'), new_field.typeName(), True)


    def create_spatial_index_for_postgresql_layer(self, layer, layer_props):       


        if layer != None or layer_props != None:

            schema = layer_props["infos"]["layer_schema"]
            table = layer_props["infos"]["layer_name"]
            geometry_field = layer_props["infos"]["layer_geometry_field"]
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
            
            sql_statement = sql_statement + 'ANALYZE VERBOSE "{schema}"."{table}";'.format(schema=schema,
                                                                                    table=table)


            with connexion.cursor() as cursor:
                cursor.execute(sql_statement)

            if self.isCanceled():
                return False
            
            return True

        else:
            return False



    def create_spatial_index_for_layer(self, layer):    
        """
        Create spatial index for a layer with proper validation and error handling.
        
        Args:
            layer: QgsVectorLayer to create spatial index for
            
        Returns:
            bool: True if successful or index already exists, False if canceled
        """
        try:
            # Skip if layer has no geometry or is already indexed
            if not layer.isSpatial():
                return True
            
            # Check if spatial index already exists
            if layer.hasSpatialIndex() != QgsFeatureSource.SpatialIndexNotPresent:
                return True
            
            # Validate layer has features with valid geometry
            if layer.featureCount() == 0:
                return True
            
            # Check for at least one valid geometry before attempting index creation
            has_valid_geom = False
            for feature in layer.getFeatures():
                if feature.hasGeometry() and not feature.geometry().isNull():
                    has_valid_geom = True
                    break
                if self.isCanceled():
                    return False
            
            if not has_valid_geom:
                # No valid geometries, skip spatial index creation
                return True
            
            # Create spatial index
            alg_params_createspatialindex = {
                "INPUT": layer
            }
            processing.run('qgis:createspatialindex', alg_params_createspatialindex)
            
            if self.isCanceled():
                return False
        
        except Exception as e:
            # Log error but don't fail the entire operation
            safe_log(logger, logging.WARNING, 
                    f"Failed to create spatial index for layer {layer.name()}: {str(e)}")
            # Continue without spatial index - layer will still be usable
            pass
    
        return True


    def save_variables_from_layer(self, layer, layer_properties=[]):

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
                        variable_key = "filterMate_{key_group}_{key}".format(key_group=key_group, key=key)
                        QgsExpressionContextUtils.setLayerVariable(layer, key_group + '_' +  key, value_typped)
                        # Emit signal to notify variable was saved
                        self.savingLayerVariable.emit(layer, variable_key, value_typped, type_returned)
                        # Use parameterized query to prevent SQL injection
                        cur.execute(
                            """INSERT INTO fm_project_layers_properties 
                               VALUES(?, datetime(), ?, ?, ?, ?, ?)""",
                            (
                                str(uuid.uuid4()),
                                str(self.project_uuid),
                                layer.id(),
                                key_group,
                                key,
                                value_typped.replace("\'","\'\'") if type_returned in (str, dict, list) else value_typped
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
                            # Emit signal to notify variable was saved
                            self.savingLayerVariable.emit(layer, variable_key, value_typped, type_returned)
                            # Use parameterized query to prevent SQL injection
                            cur.execute(
                                """INSERT INTO fm_project_layers_properties 
                                   VALUES(?, datetime(), ?, ?, ?, ?, ?)""",
                                (
                                    str(uuid.uuid4()),
                                    str(self.project_uuid),
                                    layer.id(),
                                    layer_property[0],
                                    layer_property[1],
                                    value_typped.replace("\'","\'\'") if type_returned in (str, dict, list) else value_typped
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

            conn = self._safe_spatialite_connect()
            cur = conn.cursor()

            if layer_all_properties_flag is True:
                # Use parameterized query to prevent SQL injection
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
                            # Use parameterized query to prevent SQL injection
                            cur.execute(
                                """DELETE FROM fm_project_layers_properties  
                                   WHERE fk_project = ? AND layer_id = ? AND meta_type = ? AND meta_key = ?""",
                                (str(self.project_uuid), layer.id(), layer_property[0], layer_property[1])
                            )
                            conn.commit()
                            variable_key = "filterMate_{key_group}_{key}".format(key_group=layer_property[0], key=layer_property[1])
                            QgsExpressionContextUtils.setLayerVariable(layer, variable_key, '')
                            # Emit signal to notify variable was removed
                            self.removingLayerVariable.emit(layer, variable_key)

            cur.close()
            conn.close()



    def save_style_from_layer_id(self, layer_id):


        if layer_id in self.project_layers.keys():

            layers = [layer for layer in self.PROJECT.mapLayersByName(self.project_layers[layer_id]["infos"]["layer_name"]) if layer.id() == layer_id]
            logger.debug(f"save_style_from_layer_id - layers found: {layers}")
            if len(layers) > 0:
                layer = layers[0]

                try:
                    layer.deleteStyleFromDatabase(name="FilterMate_style_{}".format(layer.name()))
                    result = layer.saveStyleToDatabase(name="FilterMate_style_{}".format(layer.name()),description="FilterMate style for {}".format(layer.name()), useAsDefault=True, uiFileContent="") 
                    logger.debug(f"save_style_from_layer_id - style saved: {result}")
                except (RuntimeError, AttributeError) as e:
                    logger.debug(f"Could not save style to database for layer {layer.name()}, falling back to file: {e}")
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
        
        conn = self._safe_spatialite_connect()
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

        conn = self._safe_spatialite_connect()
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
        except (ValueError, TypeError, OverflowError):
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
                        # Count how many layers were actually added (present in self.layers)
                        # self.layers contains the layers being added
                        # self.project_layers contains all layers after adding
                        result_action = '{} layer(s) added'.format(str(len(self.layers)))

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

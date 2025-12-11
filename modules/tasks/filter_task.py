"""
FilterEngine Task Module

Main filtering task for FilterMate QGIS Plugin.
Extracted from appTasks.py during Phase 3 refactoring (Dec 2025).

This module contains FilterEngineTask, the core QgsTask that handles:
- Source layer filtering (attribute and geometry)
- Multi-layer geometric filtering with spatial predicates
- Export operations
- Filter history management (undo/redo/reset)

Supports multiple backends:
- PostgreSQL/PostGIS (optimal performance for large datasets)
- Spatialite (good performance for medium datasets)
- OGR (fallback for shapefiles, GeoPackage, etc.)

Performance: Uses geometry caching and backend-specific optimizations.
"""

import logging
import os
import uuid
import re
import sqlite3
import zipfile
from collections import OrderedDict
from pathlib import Path
from functools import partial

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsFeatureRequest,
    QgsFeatureSource,
    QgsField,
    QgsGeometry,
    QgsMessageLog,
    QgsProcessing,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProject,
    QgsProperty,
    QgsTask,
    QgsUnitTypes,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes
)
from qgis.PyQt.QtCore import pyqtSignal
from qgis.utils import iface
from qgis import processing

# Import logging configuration
from ..logging_config import setup_logger, safe_log
from ...config.config import ENV_VARS

# Setup logger with rotation
logger = setup_logger(
    'FilterMate.Tasks.Filter',
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
from ..constants import (
    PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR, PROVIDER_MEMORY,
    PREDICATE_INTERSECTS, PREDICATE_WITHIN, PREDICATE_CONTAINS,
    PREDICATE_OVERLAPS, PREDICATE_CROSSES, PREDICATE_TOUCHES,
    PREDICATE_DISJOINT, PREDICATE_EQUALS,
    get_provider_name, should_warn_performance
)

# Import backend architecture
from ..backends import BackendFactory

# Import utilities
from ..appUtils import (
    safe_set_subset_string,
    get_source_table_name,
    get_datasource_connexion_from_layer,
    get_primary_key_name,
    detect_layer_provider_type,
    geometry_type_to_string
)

# Import prepared statements manager
from ..prepared_statements import create_prepared_statements

# Import task utilities (Phase 3a extractions)
from .task_utils import (
    spatialite_connect,
    sqlite_execute_with_retry,
    ensure_db_directory_exists,
    get_best_metric_crs,
    should_reproject_layer,
    SQLITE_TIMEOUT,
    SQLITE_MAX_RETRIES,
    MESSAGE_TASKS_CATEGORIES
)

# Import geometry cache (Phase 3a extraction)
from .geometry_cache import SourceGeometryCache

class FilterEngineTask(QgsTask):
    """Main QgsTask class which filter and unfilter data"""
    
    # Cache de classe (partagé entre toutes les instances de FilterEngineTask)
    _geometry_cache = SourceGeometryCache()

    def __init__(self, description, task_action, task_parameters):

        QgsTask.__init__(self, description, QgsTask.CanCancel)

        self.exception = None
        self.task_action = task_action
        self.task_parameters = task_parameters
        
        # Référence au cache partagé
        self.geom_cache = FilterEngineTask._geometry_cache

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
        self.param_buffer_type = 0  # Default: Round (0), Flat (1), Square (2)
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
        
        # Prepared statements manager (initialized when DB connection is established)
        self._ps_manager = None

    
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
        # Validate required keys in task_parameters["infos"]
        if "infos" not in self.task_parameters:
            logger.error("task_parameters missing 'infos' dictionary")
            self.exception = KeyError("task_parameters missing 'infos' dictionary")
            return False
        
        required_keys = ["layer_name", "layer_id", "layer_crs_authid"]
        infos = self.task_parameters["infos"]
        missing_keys = [k for k in required_keys if k not in infos or infos[k] is None]
        
        if missing_keys:
            error_msg = f"task_parameters['infos'] missing required keys: {missing_keys}"
            logger.error(error_msg)
            self.exception = KeyError(error_msg)
            return False
        
        self.layers_count = 1
        layers = [
            layer for layer in self.PROJECT.mapLayersByName(
                infos["layer_name"]
            ) 
            if layer.id() == infos["layer_id"]
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
        
        # Validate required keys exist
        required_keys = [
            "layer_provider_type", "layer_schema", "layer_name", 
            "layer_id", "layer_geometry_field", "primary_key_name"
        ]
        infos = self.task_parameters.get("infos", {})
        missing_keys = [k for k in required_keys if k not in infos or infos[k] is None]
        
        if missing_keys:
            error_msg = f"task_parameters['infos'] missing required keys for filtering: {missing_keys}"
            logger.error(error_msg)
            raise KeyError(error_msg)
        
        # Extract basic layer information
        self.param_source_provider_type = infos["layer_provider_type"]
        self.param_source_schema = infos["layer_schema"]
        self.param_source_table = infos["layer_name"]
        self.param_source_layer_id = infos["layer_id"]
        self.param_source_geom = infos["layer_geometry_field"]
        self.primary_key_name = infos["primary_key_name"]
        
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

    def _process_qgis_expression(self, expression):
        """
        Process and validate a QGIS expression, converting it to appropriate SQL.
        
        Returns:
            tuple: (processed_expression, is_field_expression) or (None, None) if invalid
        """
        # FIXED: Only reject if expression is JUST a field name (no operators)
        # Allow expressions like "HOMECOUNT = 10" or "field > 5"
        qgs_expr = QgsExpression(expression)
        if qgs_expr.isField() and not any(op in expression for op in ['=', '>', '<', '!', 'IN', 'LIKE', 'AND', 'OR']):
            logger.debug(f"Rejecting expression '{expression}' - it's just a field name without comparison")
            return None, None
        
        if not qgs_expr.isValid():
            logger.warning(f"Invalid QGIS expression: '{expression}'")
            return None, None
        
        # Add leading space and check for field equality
        expression = " " + expression
        is_field_expression = QgsExpression().isFieldEqualityExpression(
            self.task_parameters["task"]["expression"]
        )
        
        if is_field_expression[0]:
            self.is_field_expression = is_field_expression
        
        # Qualify field names
        expression = self._qualify_field_names_in_expression(
            expression,
            self.source_layer_fields_names,
            self.primary_key_name,
            self.param_source_table,
            self.param_source_provider_type == PROVIDER_POSTGRES
        )
        
        # Convert to provider-specific SQL
        # CRITICAL: Don't apply PostgreSQL conversions to OGR layers!
        if self.param_source_provider_type == PROVIDER_POSTGRES:
            expression = self.qgis_expression_to_postgis(expression)
        elif self.param_source_provider_type == PROVIDER_SPATIALITE:
            expression = self.qgis_expression_to_spatialite(expression)
        # else: OGR providers - keep QGIS expression as-is
        
        expression = expression.strip()
        
        # Handle CASE statements
        if expression.startswith("CASE"):
            expression = 'SELECT ' + expression
        
        return expression, is_field_expression

    def _combine_with_old_subset(self, expression):
        """
        Combine new expression with existing subset string using combine operator.
        
        Uses logical operators (AND, AND NOT, OR) for source layer filtering.
        
        Returns:
            str: Combined expression
        """
        combine_operator = self._get_source_combine_operator()
        if not self.param_source_old_subset or not combine_operator:
            return expression
        
        # Extract WHERE clause from old subset
        index_where = self.param_source_old_subset.find('WHERE')
        if index_where == -1:
            # If no WHERE clause, simple combination
            return f'( {self.param_source_old_subset} ) {combine_operator} ( {expression} )'
        
        param_old_subset_where = self.param_source_old_subset[index_where:]
        param_source_old_subset = self.param_source_old_subset[:index_where]
        
        # Remove trailing )) if present
        if param_old_subset_where.endswith('))'):
            param_old_subset_where = param_old_subset_where[:-1]
        
        combined = (
            f'{param_source_old_subset} {param_old_subset_where} '
            f'{combine_operator} ( {expression} ) )'
        )
        
        return combined

    def _build_feature_id_expression(self, features_list):
        """
        Build SQL IN expression from list of feature IDs.
        
        Returns:
            str: SQL expression like "table"."pk" IN (1,2,3) or "pk" IN (1,2,3) for OGR
        """
        features_ids = [str(feature[self.primary_key_name]) for feature in features_list]
        
        if not features_ids:
            return None
        
        # Build IN clause based on provider type and primary key type
        is_numeric = self.task_parameters["infos"]["primary_key_is_numeric"]
        
        if self.param_source_provider_type == PROVIDER_OGR:
            # OGR: Simple syntax without table qualification
            # Use "fid" for numeric keys, quoted field name for string keys
            if is_numeric:
                expression = f'"fid" IN ({", ".join(features_ids)})'
            else:
                expression = f'"{self.primary_key_name}" IN ({", ".join(repr(fid) for fid in features_ids)})'
        else:
            # PostgreSQL/Spatialite: Qualified syntax
            if is_numeric:
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
        combine_operator = self._get_source_combine_operator()
        if self.param_source_old_subset and combine_operator:
            expression = (
                f'( {self.param_source_old_subset} ) '
                f'{combine_operator} ( {expression} )'
            )
        
        return expression

    def _apply_filter_and_update_subset(self, expression):
        """
        Apply filter expression to source layer and update subset strings.
        
        Returns:
            bool: True if successful, False otherwise
        """
        # CRITICAL: setSubsetString must be called from main thread
        result = safe_set_subset_string(self.source_layer, expression)
        
        if result:
            # Only build PostgreSQL SELECT for PostgreSQL providers
            # OGR and Spatialite use subset strings directly
            provider_type = self.source_layer.providerType()
            if provider_type == 'postgres':
                # Build full SELECT expression for subset management (PostgreSQL only)
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
            else:
                pass
        
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
    
    def _initialize_source_subset_and_buffer(self):
        """
        Initialize source subset expression and buffer parameters.
        
        Sets param_source_new_subset based on expression type and
        extracts buffer value/expression from task parameters.
        """
        logger.info("🔧 _initialize_source_subset_and_buffer() START")
        
        # Set source subset based on expression type
        if QgsExpression(self.expression).isField() is False:
            self.param_source_new_subset = self.expression
        else:
            self.param_source_new_subset = self.param_source_old_subset

        # Extract buffer parameters if configured
        has_buffer = self.task_parameters["filtering"]["has_buffer_value"]
        logger.info(f"  has_buffer_value: {has_buffer}")
        
        # Extract buffer_type configuration
        has_buffer_type = self.task_parameters["filtering"].get("has_buffer_type", False)
        buffer_type_str = self.task_parameters["filtering"].get("buffer_type", "Round")
        logger.info(f"  has_buffer_type: {has_buffer_type}")
        logger.info(f"  buffer_type: {buffer_type_str}")
        
        # Map buffer_type string to QGIS END_CAP_STYLE integer
        # Round = 0 (default), Flat = 1, Square = 2
        buffer_type_mapping = {
            "Round": 0,
            "Flat": 1,
            "Square": 2
        }
        
        if has_buffer_type:
            self.param_buffer_type = buffer_type_mapping.get(buffer_type_str, 0)
            logger.info(f"  ✓ Buffer type set: {buffer_type_str} (END_CAP_STYLE={self.param_buffer_type})")
        else:
            self.param_buffer_type = 0  # Default to Round
            logger.info(f"  ℹ️  Buffer type not configured, using default: Round (END_CAP_STYLE=0)")
        
        if has_buffer is True:
            buffer_property = self.task_parameters["filtering"]["buffer_value_property"]
            buffer_expr = self.task_parameters["filtering"]["buffer_value_expression"]
            buffer_val = self.task_parameters["filtering"]["buffer_value"]
            
            logger.info(f"  buffer_value_property: {buffer_property}")
            logger.info(f"  buffer_value_expression: '{buffer_expr}'")
            logger.info(f"  buffer_value: {buffer_val}")
            
            # CRITICAL FIX: Check buffer_value_expression FIRST, regardless of buffer_property
            # UI sometimes sets buffer_property=False but still provides buffer_value_expression
            if buffer_expr != '' and buffer_expr is not None:
                # Try to convert to float - if successful, it's a static value
                try:
                    numeric_value = float(buffer_expr)
                    self.param_buffer_value = numeric_value
                    logger.info(f"  ✓ Buffer expression is static value: {self.param_buffer_value}m")
                    logger.info(f"  ℹ️  Converted from expression '{buffer_expr}' to numeric value")
                except (ValueError, TypeError):
                    # It's a real dynamic expression (e.g., field reference)
                    self.param_buffer_expression = buffer_expr
                    logger.info(f"  ✓ Buffer DYNAMIC EXPRESSION set: {self.param_buffer_expression}")
                    logger.warning(f"  ⚠️  Dynamic buffer expressions may not work with all backends")
            elif buffer_val is not None and buffer_val != 0:
                # Fallback to buffer_value
                self.param_buffer_value = buffer_val
                logger.info(f"  ✓ Buffer VALUE set: {self.param_buffer_value}m")
            else:
                # No valid buffer specified
                self.param_buffer_value = 0
                logger.warning(f"  ⚠️  No valid buffer value found, defaulting to 0m")
        else:
            logger.warning(f"  ⚠️  NO BUFFER configured (has_buffer_value=False)")
            logger.warning(f"  ⚠️  param_buffer_value will remain: {getattr(self, 'param_buffer_value', 'NOT SET')}")
        
        logger.info("✓ _initialize_source_subset_and_buffer() END")

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
                
                if result:
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
        
        CRITICAL: Buffer parameters MUST be initialized BEFORE preparing geometries,
        otherwise buffer will not be applied to source geometries!
        
        Returns:
            bool: True if all layers processed successfully, False on error or cancellation
        """
        # CRITICAL: Initialize source subset and buffer parameters FIRST
        # This sets self.param_buffer_value which is needed by prepare_*_source_geom()
        self._initialize_source_subset_and_buffer()
        
        # Build unique provider list including source layer provider
        provider_list = self.provider_list + [self.param_source_provider_type]
        provider_list = list(dict.fromkeys(provider_list))
        
        # Prepare geometries for all provider types
        # NOTE: This will use self.param_buffer_value set above
        if not self._prepare_geometries_by_provider(provider_list):
            return False
        
        # Filter all layers with progress tracking
        result = self._filter_all_layers_with_progress()
        return result
    
    def qgis_expression_to_postgis(self, expression):

        if expression.find('if') >= 0:
            expression = re.sub(r'if\((.*,.*,.*)\))', r'(if(.* then .* else .*))', expression)
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
        # IMPORTANT: Process ILIKE first, before processing LIKE, to avoid double-replacement
        expression = re.sub(r'(\w+)\s+ILIKE\s+', r'LOWER(\1) LIKE LOWER(', expression, flags=re.IGNORECASE)
        expression = re.sub(r'\bNOT\b', ' NOT ', expression, flags=re.IGNORECASE)
        expression = re.sub(r'\bLIKE\b', ' LIKE ', expression, flags=re.IGNORECASE)
        
        # Convert PostgreSQL :: type casting to Spatialite CAST() function
        # PostgreSQL: "field"::numeric -> Spatialite: CAST("field" AS REAL)
        expression = re.sub(r'(["\w]+)::numeric', r'CAST(\1 AS REAL)', expression)
        expression = re.sub(r'(["\w]+)::integer', r'CAST(\1 AS INTEGER)', expression)
        expression = re.sub(r'(["\w]+)::text', r'CAST(\1 AS TEXT)', expression)
        expression = re.sub(r'(["\w]+)::double', r'CAST(\1 AS REAL)', expression)
        
        # CRITICAL FIX: Do NOT remove quotes from field names!
        # Spatialite needs quotes for case-sensitive field names, just like PostgreSQL.
        # Unlike the PostgreSQL version that adds ::numeric for type casting,
        # Spatialite will do implicit type conversion when needed.
        # The quotes MUST be preserved for field names like "HOMECOUNT".
        #
        # Note: The old code had these lines which REMOVED quotes:
        #   expression = expression.replace('" >', ' ').replace('">', ' ')
        # This was WRONG and caused "HOMECOUNT" > 100 to become HOMECOUNT > 100
        
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

        if self.param_buffer_expression is not None and self.param_buffer_expression != '':


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
            
        


        elif self.param_buffer_value is not None:

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
        
        Supports all geometry types including non-linear geometries:
        - CIRCULARSTRING
        - COMPOUNDCURVE
        - CURVEPOLYGON
        - MULTICURVE
        - MULTISURFACE
        
        Note: Uses QGIS asWkt() which handles extended WKT format.
        GeoPackage and Spatialite both support these geometry types via standard WKB encoding.
        
        Performance: Uses cache to avoid recalculating for multiple layers.
        """
        # Get features from task parameters
        features = self.task_parameters["task"]["features"]
        logger.info(f"=== prepare_spatialite_source_geom START ===")
        logger.info(f"  Features: {len(features)} features")
        logger.info(f"  Buffer value: {self.param_buffer_value}")
        logger.info(f"  Target CRS: {self.source_layer_crs_authid}")
        logger.debug(f"prepare_spatialite_source_geom: Processing {len(features)} features")
        
        # Check cache first
        cached_geom = self.geom_cache.get(
            features, 
            self.param_buffer_value,
            self.source_layer_crs_authid
        )
        
        if cached_geom is not None:
            # CRITICAL: Verify cache BEFORE using it
            cached_wkt = cached_geom.get('wkt')
            wkt_type = cached_wkt.split('(')[0].strip() if cached_wkt else 'Unknown'
            
            # Check if buffer expected but cached geometry is LineString
            cache_is_valid = True
            if self.param_buffer_value and self.param_buffer_value > 0:
                if 'LineString' in wkt_type or 'Line' in wkt_type:
                    logger.error("❌ CACHE BUG DETECTED!")
                    logger.error(f"  Expected: Polygon/MultiPolygon (with {self.param_buffer_value}m buffer)")
                    logger.error(f"  Got: {wkt_type} (no buffer applied!)")
                    logger.error("  → Cache has stale geometry without buffer")
                    logger.error("  → Clearing cache and recomputing...")
                    
                    # Clear cache and mark as invalid
                    self.geom_cache.clear()
                    cached_geom = None
                    cache_is_valid = False
                    logger.info("✓ Cache cleared, will recompute geometry with buffer")
            
            # Only use cache if valid
            if cache_is_valid and cached_geom is not None:
                self.spatialite_source_geom = cached_wkt
                logger.info("✓ Using CACHED source geometry for Spatialite")
                logger.debug(f"  Cache was computed with buffer: {self.param_buffer_value}")
                logger.debug(f"  Cached geometry type: {wkt_type}")
                return
        
        # Cache miss - compute geometry
        logger.debug("Cache miss - computing source geometry")
        
        raw_geometries = [feature.geometry() for feature in features if feature.hasGeometry()]
        logger.debug(f"prepare_spatialite_source_geom: {len(raw_geometries)} geometries with geometry")
        
        if len(raw_geometries) == 0:
            logger.error("prepare_spatialite_source_geom: No geometries found in source features")
            self.spatialite_source_geom = None
            return
        
        geometries = []

        # Determine target CRS for buffer operations
        target_crs = QgsCoordinateReferenceSystem(self.source_layer_crs_authid)
        is_geographic = target_crs.isGeographic()
        
        # CRITICAL: For geographic coordinates, switch to EPSG:3857 for metric calculations
        # This ensures accurate buffer distances in meters instead of imprecise degrees
        use_metric_crs = False
        if is_geographic and self.param_buffer_value is not None and self.param_buffer_value > 0:
            logger.info(f"🌍 Geographic CRS detected: {target_crs.authid()}")
            logger.info(f"   → Switching to EPSG:3857 for metric-based buffer calculations")
            target_crs = QgsCoordinateReferenceSystem("EPSG:3857")
            use_metric_crs = True
        
        # Setup reprojection transforms
        if self.has_to_reproject_source_layer is True or use_metric_crs:
            source_crs_obj = QgsCoordinateReferenceSystem(self.source_crs.authid())
            transform = QgsCoordinateTransform(source_crs_obj, target_crs, self.PROJECT)
            
            if use_metric_crs:
                logger.debug(f"Will reproject from {self.source_crs.authid()} → EPSG:3857 (metric) for buffer")
            else:
                logger.debug(f"Will reproject from {self.source_crs.authid()} to {self.source_layer_crs_authid}")

        # Log buffer settings for debugging
        logger.debug(f"Buffer settings: param_buffer_value={self.param_buffer_value}")
        
        for geometry in raw_geometries:
            if geometry.isEmpty() is False:
                # Make a copy to avoid modifying original
                geom_copy = QgsGeometry(geometry)
                
                logger.debug(f"Processing geometry: type={geom_copy.wkbType()}, multipart={geom_copy.isMultipart()}")
                
                if geom_copy.isMultipart():
                    geom_copy.convertToSingleType()
                    
                if self.has_to_reproject_source_layer is True or use_metric_crs:
                    geom_copy.transform(transform)
                    
                # Apply buffer if configured (now always in meters)
                if self.param_buffer_value is not None and self.param_buffer_value > 0:
                    logger.info(f"Applying buffer of {self.param_buffer_value}m to geometry (CRS: {target_crs.authid()})")
                    original_wkt_type = geom_copy.asWkt().split('(')[0].strip()
                    geom_copy = geom_copy.buffer(self.param_buffer_value, 5)
                    buffered_wkt_type = geom_copy.asWkt().split('(')[0].strip()
                    logger.debug(f"  Geometry type: {original_wkt_type} → {buffered_wkt_type}")
                else:
                    logger.warning(f"No buffer applied! param_buffer_value={self.param_buffer_value}")
                    
                geometries.append(geom_copy)

        if len(geometries) == 0:
            logger.error("prepare_spatialite_source_geom: No valid geometries after processing")
            self.spatialite_source_geom = None
            return

        # Collect all geometries into one
        collected_geometry = QgsGeometry.collectGeometry(geometries)
        
        # CRITICAL: If we used metric CRS for buffer, transform back to target layer CRS
        if use_metric_crs:
            final_crs = QgsCoordinateReferenceSystem(self.source_layer_crs_authid)
            back_transform = QgsCoordinateTransform(target_crs, final_crs, self.PROJECT)
            collected_geometry.transform(back_transform)
            logger.info(f"✓ Transformed buffered geometry from EPSG:3857 back to {final_crs.authid()}")
        
        wkt = collected_geometry.asWkt()
        
        # Log the final geometry type
        geom_type = wkt.split('(')[0].strip() if '(' in wkt else 'Unknown'
        logger.info(f"  Final collected geometry type: {geom_type}")
        logger.info(f"  Number of geometries collected: {len(geometries)}")
        if use_metric_crs:
            logger.info(f"  ✓ Buffer calculated in EPSG:3857 (metric), result in {self.source_layer_crs_authid}")
        
        # Escape single quotes for SQL
        wkt_escaped = wkt.replace("'", "''")
        self.spatialite_source_geom = wkt_escaped

        logger.info(f"  WKT length: {len(self.spatialite_source_geom)} chars")
        logger.debug(f"prepare_spatialite_source_geom WKT preview: {self.spatialite_source_geom[:200]}...")
        logger.info(f"=== prepare_spatialite_source_geom END ===") 
        
        # Store in cache for future use
        self.geom_cache.put(
            features,
            self.param_buffer_value,
            self.source_layer_crs_authid,
            {'wkt': wkt_escaped}
        )
        logger.info("✓ Source geometry computed and CACHED") 

    def _copy_filtered_layer_to_memory(self, layer, layer_name="filtered_copy"):
        """
        Copy filtered layer (with subset string) to memory layer.
        
        This is crucial for OGR layers with subset strings, as some QGIS
        algorithms don't handle subset strings correctly.
        
        Args:
            layer: Source layer (may have subset string active)
            layer_name: Name for memory layer
            
        Returns:
            QgsVectorLayer: Memory layer with only filtered features
        """
        # Check if layer has active filter
        subset_string = layer.subsetString()
        feature_count = layer.featureCount()
        
        logger.debug(f"_copy_filtered_layer_to_memory: {layer.name()}, features={feature_count}, subset='{subset_string[:50] if subset_string else 'None'}'")
        
        # If no filter and reasonable feature count, return original
        if not subset_string and feature_count < 10000:
            logger.debug("  → No subset string, returning original layer")
            return layer
        
        # Create memory layer with same structure
        geom_type = QgsWkbTypes.displayString(layer.wkbType())
        crs = layer.crs().authid()
        memory_layer = QgsVectorLayer(f"{geom_type}?crs={crs}", layer_name, "memory")
        
        # Copy fields
        memory_layer.dataProvider().addAttributes(layer.fields())
        memory_layer.updateFields()
        
        # Copy filtered features
        features_to_copy = []
        for feature in layer.getFeatures():
            new_feature = QgsFeature(feature)
            features_to_copy.append(new_feature)
        
        if not features_to_copy:
            logger.warning(f"  ⚠️ No features to copy from {layer.name()}")
            return memory_layer
        
        memory_layer.dataProvider().addFeatures(features_to_copy)
        memory_layer.updateExtents()
        
        logger.debug(f"  ✓ Copied {len(features_to_copy)} features to memory layer")
        return memory_layer

    def _fix_invalid_geometries(self, layer, output_key):
        """
        Fix invalid geometries in layer using QGIS processing.
        DISABLED: Returns input layer unchanged.
        
        Args:
            layer: Input layer
            output_key: Key to store output in self.outputs dict
            
        Returns:
            QgsVectorLayer: Original layer (unmodified)
        """
        logger.debug(f"_fix_invalid_geometries: DISABLED, returning layer as-is")
        return layer
        # DISABLED CODE:
        # alg_params = {
        #     'INPUT': layer,
        #     'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        # }
        # self.outputs[output_key] = processing.run('qgis:fixgeometries', alg_params)
        # return self.outputs[output_key]['OUTPUT']


    def _reproject_layer(self, layer, target_crs):
        """
        Reproject layer to target CRS without geometry validation.
        
        Args:
            layer: Input layer
            target_crs: Target CRS authority ID (e.g., 'EPSG:3857')
            
        Returns:
            QgsVectorLayer: Reprojected layer (no geometry validation)
        """
        # Reproject with GeometryNoCheck
        alg_params = {
            'INPUT': layer,
            'TARGET_CRS': target_crs,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        
        context = QgsProcessingContext()
        context.setInvalidGeometryCheck(QgsFeatureRequest.GeometryNoCheck)
        feedback = QgsProcessingFeedback()
        
        self.outputs['alg_source_layer_params_reprojectlayer'] = processing.run(
            'qgis:reprojectlayer', 
            alg_params,
            context=context,
            feedback=feedback
        )
        layer = self.outputs['alg_source_layer_params_reprojectlayer']['OUTPUT']
        
        # DISABLED: Skip geometry fix after reprojection
        # layer = self._fix_invalid_geometries(layer, 'alg_source_layer_params_fixgeometries_reproject')
        
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
        # DISABLED: Geometry repair - let invalid geometries pass through
        # layer = self._repair_invalid_geometries(layer)
        # layer = self._fix_invalid_geometries(layer, 'alg_source_layer_params_fixgeometries_buffer')
        
        # CRITICAL DIAGNOSTIC: Check CRS type
        crs = layer.crs()
        is_geographic = crs.isGeographic()
        crs_units = crs.mapUnits()
        
        # Log layer info with enhanced CRS diagnostics
        logger.info(f"QGIS buffer: {layer.featureCount()} features, "
                   f"CRS: {crs.authid()}, "
                   f"Geometry type: {layer.geometryType()}, "
                   f"wkbType: {layer.wkbType()}, "
                   f"buffer_distance: {buffer_distance}")
        logger.info(f"CRS diagnostics: isGeographic={is_geographic}, mapUnits={crs_units}")
        
        # CRITICAL: Check if CRS is geographic with large buffer value
        if is_geographic:
            # Evaluate buffer distance to get actual value
            eval_distance = buffer_distance
            if isinstance(buffer_distance, QgsProperty):
                features = list(layer.getFeatures())
                if features:
                    context = QgsExpressionContext()
                    context.setFeature(features[0])
                    eval_distance = buffer_distance.value(context, 0)
            
            if eval_distance and float(eval_distance) > 1:
                logger.warning(
                    f"⚠️ GEOGRAPHIC CRS DETECTED with large buffer value!\n"
                    f"  CRS: {crs.authid()} (units: degrees)\n"
                    f"  Buffer: {eval_distance} DEGREES (this is likely wrong!)\n"
                    f"  → A buffer of {eval_distance}° = ~{float(eval_distance) * 111}km at equator\n"
                    f"  → This will likely fail or create invalid geometries\n"
                    f"  SOLUTION: Reproject layer to a projected CRS (e.g., EPSG:3857, EPSG:2154) first"
                )
                raise Exception(
                    f"Cannot apply buffer: Geographic CRS detected ({crs.authid()}) with buffer value {eval_distance}. "
                    f"Buffer units would be DEGREES, not meters. "
                    f"Please reproject your layer to a projected coordinate system (e.g., EPSG:3857 Web Mercator, "
                    f"or EPSG:2154 Lambert 93 for France) before applying buffer."
                )
        
        # Apply buffer with dissolve
        # CRITICAL: Configure to skip invalid geometries instead of failing
        alg_params = {
            'DISSOLVE': True,
            'DISTANCE': buffer_distance,
            'END_CAP_STYLE': int(self.param_buffer_type),  # Use configured buffer type (0=Round, 1=Flat, 2=Square)
            'INPUT': layer,
            'JOIN_STYLE': int(0),
            'MITER_LIMIT': float(2),
            'SEGMENTS': int(5),
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        
        logger.debug(f"Calling processing.run('qgis:buffer') with params: {alg_params}")
        
        # CRITICAL: Configure processing context to skip invalid geometries
        context = QgsProcessingContext()
        context.setInvalidGeometryCheck(QgsFeatureRequest.GeometryNoCheck)
        feedback = QgsProcessingFeedback()
        
        self.outputs['alg_source_layer_params_buffer'] = processing.run(
            'qgis:buffer', 
            alg_params, 
            context=context, 
            feedback=feedback
        )
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
        
        logger.debug(f"Buffering features: layer type={layer.geometryType()}, wkb type={layer.wkbType()}, buffer_dist={buffer_dist}")
        
        for idx, feature in enumerate(layer.getFeatures()):
            geom = feature.geometry()
            if geom and not geom.isEmpty():
                try:
                    logger.debug(f"Feature {idx}: wkbType={geom.wkbType()}, isEmpty={geom.isEmpty()}")
                    
                    # DISABLED: Skip all validation, accept geometry as-is
                    # Only check for null/empty
                    if geom.isNull() or geom.isEmpty():
                        logger.warning(f"Feature {idx}: Geometry is null or empty, skipping")
                        invalid_features += 1
                        continue
                    
                    # Apply buffer WITHOUT pre-validation
                    try:
                        buffered_geom = geom.buffer(float(buffer_dist), 5)
                        logger.debug(f"Feature {idx}: Buffer applied, isEmpty={buffered_geom.isEmpty() if buffered_geom else 'None'}")
                        
                        # Accept any non-empty result, even if invalid
                        if buffered_geom and not buffered_geom.isEmpty():
                            geometries.append(buffered_geom)
                            valid_features += 1
                            logger.debug(f"Feature {idx}: Buffered geometry accepted (validation skipped)")
                        else:
                            logger.warning(f"Feature {idx}: Buffer resulted in empty geometry")
                            invalid_features += 1
                    except Exception as buffer_error:
                        logger.warning(f"Feature {idx}: Buffer operation failed: {buffer_error}")
                        invalid_features += 1
                except Exception as feat_error:
                    logger.warning(f"Feature {idx}: Error during buffer: {feat_error}")
                    invalid_features += 1
            else:
                logger.debug(f"Feature {idx}: Geometry is None or empty")
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
        # DISABLED: Skip pre-validation, accept geometries as-is
        logger.info("Manual buffer: geometry validation DISABLED")
        # layer = self._repair_invalid_geometries(layer)
        
        feature_count = layer.featureCount()
        logger.info(f"Manual buffer: Layer has {feature_count} features, geomType={layer.geometryType()}, wkbType={layer.wkbType()}")
        
        # CRS diagnostic
        crs = layer.crs()
        is_geographic = crs.isGeographic()
        logger.info(f"Manual buffer CRS: {crs.authid()}, isGeographic={is_geographic}")
        
        if feature_count == 0:
            raise Exception("Cannot buffer layer: source layer has no features")
        
        # Evaluate buffer distance
        buffer_dist = self._evaluate_buffer_distance(layer, buffer_distance)
        logger.debug(f"Manual buffer distance: {buffer_dist}")
        
        # Warn about geographic CRS
        if is_geographic and buffer_dist > 1:
            logger.warning(
                f"⚠️ Manual buffer with geographic CRS ({crs.authid()}) and distance {buffer_dist}°\n"
                f"   This is {buffer_dist * 111:.1f}km at equator - likely too large!"
            )
        
        # Create memory layer
        buffered_layer = self._create_memory_layer_for_buffer(layer)
        
        # Buffer all features
        geometries, valid_features, invalid_features = self._buffer_all_features(layer, buffer_dist)
        
        # MODIFIED: Accept result even with 0 valid geometries (return empty layer instead of error)
        if not geometries:
            logger.warning(
                f"⚠️ Manual buffer produced no geometries. "
                f"Total: {feature_count}, Valid: {valid_features}, Invalid: {invalid_features}"
            )
            # Return empty layer instead of raising exception
            return buffered_layer
        
        # Dissolve and add to layer if we have geometries
        return self._dissolve_and_add_to_layer(geometries, buffered_layer)

    def _aggressive_geometry_repair(self, geom):
        """
        Try multiple repair strategies for a geometry.
        
        Args:
            geom: QgsGeometry to repair
            
        Returns:
            QgsGeometry or None: Repaired geometry if successful, None otherwise
        """
        # Log initial state
        logger.debug(f"🔧 Attempting geometry repair: wkbType={geom.wkbType()}, isEmpty={geom.isEmpty()}, isValid={geom.isGeosValid()}")
        
        # Strategy 1: Standard makeValid()
        try:
            repaired = geom.makeValid()
            if repaired and not repaired.isNull() and not repaired.isEmpty() and repaired.isGeosValid():
                logger.info("✓ Repaired with makeValid()")
                return repaired
            else:
                status = f"null={repaired.isNull() if repaired else 'None'}, empty={repaired.isEmpty() if repaired and not repaired.isNull() else 'N/A'}, valid={repaired.isGeosValid() if repaired and not repaired.isNull() else 'N/A'}"
                logger.debug(f"makeValid() produced unusable geometry: {status}")
        except Exception as e:
            logger.debug(f"makeValid() failed with exception: {e}")
        
        # Strategy 2: Buffer(0) trick - often fixes self-intersections
        try:
            buffered = geom.buffer(0, 5)
            if buffered and not buffered.isNull() and not buffered.isEmpty() and buffered.isGeosValid():
                logger.info("✓ Repaired with buffer(0) trick")
                return buffered
            else:
                status = f"null={buffered.isNull() if buffered else 'None'}, empty={buffered.isEmpty() if buffered and not buffered.isNull() else 'N/A'}"
                logger.debug(f"buffer(0) produced unusable geometry: {status}")
        except Exception as e:
            logger.debug(f"buffer(0) failed with exception: {e}")
        
        # Strategy 3: Simplify then makeValid
        try:
            simplified = geom.simplify(0.0001)  # Very small tolerance
            if simplified and not simplified.isNull():
                repaired = simplified.makeValid()
                if repaired and not repaired.isNull() and not repaired.isEmpty() and repaired.isGeosValid():
                    logger.info("✓ Repaired with simplify + makeValid")
                    return repaired
        except Exception as e:
            logger.debug(f"simplify + makeValid failed: {e}")
        
        # Strategy 4: ConvexHull as last resort (preserves area but simplifies shape)
        try:
            hull = geom.convexHull()
            if hull and not hull.isNull() and not hull.isEmpty() and hull.isGeosValid():
                logger.info("✓ Using convex hull as last resort")
                return hull
        except Exception as e:
            logger.debug(f"convexHull failed: {e}")
        
        # Strategy 5: Bounding box (very last resort for filtering purposes)
        try:
            bbox = geom.boundingBox()
            if bbox and not bbox.isEmpty():
                bbox_geom = QgsGeometry.fromRect(bbox)
                if bbox_geom and not bbox_geom.isNull() and bbox_geom.isGeosValid():
                    logger.warning("⚠️ Using bounding box as absolute last resort - geometry severely corrupted")
                    return bbox_geom
        except Exception as e:
            logger.debug(f"boundingBox failed: {e}")
        
        logger.error("✗ All repair strategies failed - geometry is irreparably corrupted")
        return None

    def _repair_invalid_geometries(self, layer):
        """
        Validate and repair invalid geometries in a layer.
        Creates a new memory layer with repaired geometries if needed.
        
        Args:
            layer: Input layer to check and repair
            
        Returns:
            QgsVectorLayer: Original layer if all valid, or new layer with repaired geometries
        """
        total_features = layer.featureCount()
        invalid_count = 0
        repaired_count = 0
        
        # First pass: check for invalid geometries
        for feature in layer.getFeatures():
            geom = feature.geometry()
            if geom and not geom.isNull():
                if not geom.isGeosValid():
                    invalid_count += 1
        
        if invalid_count == 0:
            logger.debug(f"✓ All {total_features} geometries are valid")
            return layer
        
        logger.warning(f"⚠️ Found {invalid_count}/{total_features} invalid geometries, attempting repair...")
        
        # Create memory layer for repaired geometries
        geom_type = QgsWkbTypes.displayString(layer.wkbType())
        crs = layer.crs().authid()
        repaired_layer = QgsVectorLayer(f"{geom_type}?crs={crs}", "repaired_geometries", "memory")
        
        # Copy fields
        repaired_layer.dataProvider().addAttributes(layer.fields())
        repaired_layer.updateFields()
        
        # Repair and copy features
        features_to_add = []
        for feature in layer.getFeatures():
            new_feature = QgsFeature(feature)
            geom = feature.geometry()
            
            if geom and not geom.isNull():
                # Log geometry details for diagnosis
                logger.debug(f"Feature {feature.id()}: wkbType={geom.wkbType()}, isEmpty={geom.isEmpty()}, isValid={geom.isGeosValid()}")
                
                if not geom.isGeosValid():
                    # Get validation error details
                    try:
                        errors = geom.validateGeometry()
                        if errors:
                            logger.debug(f"  Validation errors: {[str(e.what()) for e in errors[:3]]}")  # First 3 errors
                    except (AttributeError, RuntimeError):
                        pass
                    
                    # Try aggressive repair with multiple strategies
                    repaired_geom = self._aggressive_geometry_repair(geom)
                    
                    if repaired_geom and not repaired_geom.isEmpty():
                        new_feature.setGeometry(repaired_geom)
                        repaired_count += 1
                        logger.debug(f"  ✓ Repaired geometry for feature {feature.id()}")
                    else:
                        logger.warning(f"  ✗ Could not repair geometry for feature {feature.id()} - all strategies failed")
                        continue
            
            features_to_add.append(new_feature)
        
        # Add repaired features
        repaired_layer.dataProvider().addFeatures(features_to_add)
        repaired_layer.updateExtents()
        
        # Check if we have at least some valid features
        if len(features_to_add) == 0:
            logger.error(f"✗ Geometry repair failed: No valid features remaining after repair (0/{total_features})")
            raise Exception(f"All geometries are invalid and cannot be repaired. Total: {total_features}, Invalid: {invalid_count}")
        
        logger.info(f"✓ Geometry repair complete: {repaired_count}/{invalid_count} successfully repaired, {len(features_to_add)}/{total_features} features kept")
        return repaired_layer

    def _apply_buffer_with_fallback(self, layer, buffer_distance):
        """
        Apply buffer to layer with automatic fallback to manual method.
        Validates and repairs geometries before buffering.
        
        Args:
            layer: Input layer
            buffer_distance: QgsProperty or float
            
        Returns:
            QgsVectorLayer: Buffered layer (may be empty on failure)
        """
        logger.info(f"Applying buffer: distance={buffer_distance}")
        
        # DISABLED: Skip geometry repair
        # layer = self._repair_invalid_geometries(layer)
        
        try:
            # Try QGIS buffer algorithm first
            return self._apply_qgis_buffer(layer, buffer_distance)
        except Exception as e:
            # Fallback to manual buffer
            logger.warning(f"QGIS buffer algorithm failed: {str(e)}, using manual buffer approach")
            try:
                return self._create_buffered_memory_layer(layer, buffer_distance)
            except Exception as manual_error:
                logger.error(f"Both buffer methods failed. QGIS: {str(e)}, Manual: {str(manual_error)}")
                logger.warning("Returning empty buffer layer - continuing with empty geometry")
                
                # Return empty layer instead of raising exception
                geom_type = "Polygon" if layer.geometryType() in [0, 1] else "MultiPolygon"
                empty_layer = QgsVectorLayer(
                    f"{geom_type}?crs={layer.crs().authid()}",
                    "empty_buffer",
                    "memory"
                )
                return empty_layer


    def prepare_ogr_source_geom(self):
        """
        Prepare OGR source geometry with optional reprojection and buffering.
        
        REFACTORED: Decomposed from 173 lines to ~35 lines using helper methods.
        Main method now orchestrates geometry preparation workflow.
        
        Process:
        1. Copy filtered layer to memory (if subset string active)
        2. Fix invalid geometries in source layer
        3. Reproject if needed
        4. Apply buffer if specified
        5. Store result in self.ogr_source_geom
        """
        layer = self.source_layer
        
        # Step 0: CRITICAL - Copy to memory if layer has subset string
        # This prevents issues with QGIS algorithms not handling subset strings correctly
        if layer.subsetString():
            logger.debug(f"Source layer has subset string, copying to memory first...")
            layer = self._copy_filtered_layer_to_memory(layer, "source_filtered")
        
        # Step 1: DISABLED - Skip geometry validation/repair, let invalid geometries pass
        logger.info("Geometry validation DISABLED - allowing invalid geometries to pass through")
        # layer = self._repair_invalid_geometries(layer)
        # layer = self._fix_invalid_geometries(layer, 'alg_source_layer_params_fixgeometries_source')
        
        # Step 2: Check if buffer is requested and validate CRS BEFORE reprojection
        buffer_distance = self._get_buffer_distance_parameter()
        if buffer_distance is not None:
            # Check CRS compatibility with buffer
            crs = layer.crs()
            is_geographic = crs.isGeographic()
            
            # Evaluate buffer distance
            eval_distance = buffer_distance
            if isinstance(buffer_distance, QgsProperty):
                features = list(layer.getFeatures())
                if features:
                    context = QgsExpressionContext()
                    context.setFeature(features[0])
                    eval_distance = buffer_distance.value(context, 0)
            
            if is_geographic and eval_distance and float(eval_distance) > 1:
                logger.warning(
                    f"⚠️ Geographic CRS detected ({crs.authid()}) with buffer value {eval_distance}.\n"
                    f"   Buffer units would be DEGREES. Auto-reprojecting to EPSG:3857 (Web Mercator)."
                )
                # Force reprojection to Web Mercator for buffering
                self.has_to_reproject_source_layer = True
                self.source_layer_crs_authid = 'EPSG:3857'
        
        # Step 3: Reproject if needed (either requested by user or forced for buffer)
        if self.has_to_reproject_source_layer:
            layer = self._reproject_layer(layer, self.source_layer_crs_authid)
        
        # Step 4: Apply buffer if specified
        if buffer_distance is not None:
            layer = self._apply_buffer_with_fallback(layer, buffer_distance)
            # Check if buffer resulted in empty layer
            if layer.featureCount() == 0:
                logger.warning("⚠️ Buffer operation produced empty layer - using unbuffered geometry")
                # Fallback: use original geometry without buffer
                layer = self.source_layer
                if layer.subsetString():
                    layer = self._copy_filtered_layer_to_memory(layer, "source_filtered_no_buffer")
        
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
                safe_set_subset_string(current_layer, param_old_subset)
                current_layer.selectAll()
                safe_set_subset_string(current_layer, '')
                
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
        Qualify field names with table prefix for PostgreSQL/Spatialite expressions.
        
        This helper adds table qualifiers to field names in QGIS expressions to make them
        compatible with PostgreSQL/Spatialite queries (e.g., "field" becomes "table"."field").
        
        For OGR providers, field names are NOT qualified (just wrapped in quotes if needed).
        
        Args:
            expression: Raw QGIS expression string
            field_names: List of field names to qualify
            primary_key_name: Primary key field name
            table_name: Source table name
            is_postgresql: Whether target is PostgreSQL (True) or other provider (False)
            
        Returns:
            str: Expression with qualified field names (PostgreSQL/Spatialite) or simple quoted names (OGR)
        """
        result_expression = expression
        
        # For OGR, just ensure field names are quoted, no table qualification
        if self.param_source_provider_type == PROVIDER_OGR:
            # Handle primary key
            if primary_key_name in result_expression and f'"{primary_key_name}"' not in result_expression:
                result_expression = result_expression.replace(
                    f' {primary_key_name} ',
                    f' "{primary_key_name}" '
                )
            
            # Handle other fields
            for field_name in field_names:
                if field_name in result_expression and f'"{field_name}"' not in result_expression:
                    result_expression = result_expression.replace(
                        f' {field_name} ',
                        f' "{field_name}" '
                    )
            
            return result_expression
        
        # PostgreSQL/Spatialite: Add table qualification
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
            
            # Ensure layer object is in layer_props for backend use
            if 'layer' not in layer_props:
                layer_props['layer'] = layer
            
            # Build filter expression using backend
            expression = self._build_backend_expression(backend, layer_props, source_geom)
            if not expression:
                logger.warning(f"No expression generated for {layer.name()}")
                return False
            
            # Get old subset and combine operator for backend to handle
            old_subset = layer.subsetString() if layer.subsetString() != '' else None
            combine_operator = self._get_combine_operator()
            
            logger.debug(f"Filter expression for {layer.name()}: {expression[:200] if len(expression) < 500 else expression[:200] + '...'}")
            if old_subset:
                logger.debug(f"Will combine with existing filter using operator: {combine_operator}")
            
            # Apply filter using backend (delegates to appropriate method for each provider type)
            result = backend.apply_filter(layer, expression, old_subset, combine_operator)
            
            if result:
                # For backends that use setSubsetString, get the actual applied expression
                final_expression = layer.subsetString()
                feature_count = layer.featureCount()
                
                # CRITICAL DIAGNOSTIC: Verify filter was actually applied
                logger.info(f"✓ Filter operation completed for {layer.name()}")
                logger.info(f"  - Backend returned: SUCCESS")
                logger.info(f"  - Features after filter: {feature_count:,}")
                logger.info(f"  - Subset string applied: '{final_expression[:200] if final_expression else '(empty)'}'")
                
                # Additional layer state verification
                logger.info(f"  - Layer is valid: {layer.isValid()}")
                logger.info(f"  - Provider: {layer.providerType()}")
                logger.info(f"  - CRS: {layer.crs().authid()}")
                
                # Try to trigger layer refresh to ensure UI updates
                try:
                    layer.triggerRepaint()
                    logger.debug(f"  - Triggered layer repaint")
                except Exception as repaint_error:
                    logger.warning(f"  - Could not trigger repaint: {repaint_error}")
                
                # Warning if no features after filtering
                if feature_count == 0:
                    logger.warning(
                        f"⚠️ WARNING: {layer.name()} has ZERO features after filtering!\n"
                        f"   This could mean:\n"
                        f"   1. The filter is correct but no features match\n"
                        f"   2. The subset string syntax is invalid for this provider\n"
                        f"   3. The filter was not actually applied\n"
                        f"   Provider: {layer_provider_type}, Expression length: {len(final_expression) if final_expression else 0}"
                    )
                
                # Store subset string for history/undo functionality
                self.manage_layer_subset_strings(
                    layer,
                    final_expression,
                    primary_key,
                    geom_field,
                    False
                )
                
                logger.info(f"✓ Successfully filtered {layer.name()}: {feature_count:,} features match")
            else:
                logger.error(f"✗ Backend returned FAILURE for {layer.name()}")
                logger.error(f"  - Check backend logs for details")
            
            return result
            
        except Exception as e:
            safe_log(logger, logging.ERROR, f"Error in execute_geometric_filtering for {layer.name()}: {e}", exc_info=True)
            return False
    
    def _get_source_combine_operator(self):
        """
        Get logical operator for combining with source layer's existing filter.
        
        Returns logical operators (AND, AND NOT, OR) directly from UI.
        These are used in simple SQL WHERE clause combinations.
        
        Returns:
            str: 'AND', 'AND NOT', 'OR', or None
        """
        if not hasattr(self, 'has_combine_operator') or not self.has_combine_operator:
            return None
        
        # Return source layer operator directly (no conversion needed)
        return getattr(self, 'param_source_layer_combine_operator', None)
    
    def _get_combine_operator(self):
        """
        Get operator for combining with distant layers' existing filters.
        
        Returns the operator directly from UI for use in WHERE clauses:
        - 'AND': Logical AND (intersection)
        - 'AND NOT': Logical AND NOT (exclusion)
        - 'OR': Logical OR (union)
        
        Note: These operators are used directly in SQL WHERE clauses for all backends
        (PostgreSQL, Spatialite, OGR). For PostgreSQL set operations (UNION, INTERSECT, EXCEPT),
        use a different method when combining subqueries.
        
        Returns:
            str: 'AND', 'OR', 'AND NOT', or None
        """
        if not hasattr(self, 'has_combine_operator') or not self.has_combine_operator:
            return None
        
        # Return operator directly - no conversion needed for WHERE clause combinations
        other_op = getattr(self, 'param_other_layers_combine_operator', None)
        return other_op
    
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
        """
        Manage the advanced filtering.
        
        OPTIMISÉ: Filtre la couche source D'ABORD avec validation des modes,
        puis les couches distantes SEULEMENT si succès.
        """
        # ═══════════════════════════════════════════════════════════════
        # ÉTAPE 1: FILTRER LA COUCHE SOURCE (PRIORITÉ)
        # ═══════════════════════════════════════════════════════════════
        
        logger.info("=" * 60)
        logger.info("STEP 1/2: Filtering SOURCE LAYER")
        logger.info("=" * 60)
        
        # Déterminer le mode de sélection actif
        features_list = self.task_parameters["task"]["features"]
        qgis_expression = self.task_parameters["task"]["expression"]
        
        if len(features_list) > 0 and features_list[0] != "":
            if len(features_list) == 1:
                logger.info("✓ Selection Mode: SINGLE SELECTION")
                logger.info(f"  → 1 feature selected")
            else:
                logger.info("✓ Selection Mode: MULTIPLE SELECTION")
                logger.info(f"  → {len(features_list)} features selected")
        elif qgis_expression and qgis_expression.strip():
            logger.info("✓ Selection Mode: CUSTOM EXPRESSION")
            logger.info(f"  → Expression: '{qgis_expression}'")
        else:
            logger.error("✗ No valid selection mode detected!")
            logger.error("  → features_list is empty AND expression is empty")
            return False
        
        # Exécuter le filtrage de la couche source
        result = self.execute_source_layer_filtering()

        if self.isCanceled():
            logger.warning("⚠ Task canceled by user")
            return False
        
        # ✅ VALIDATION: Vérifier que le filtre source a réussi
        if not result:
            logger.error("=" * 60)
            logger.error("✗ FAILED: Source layer filtering FAILED")
            logger.error("=" * 60)
            logger.error("⛔ ABORTING: Distant layers will NOT be filtered")
            logger.error("   Reason: Source filter must succeed before filtering distant layers")
            return False
        
        # Vérifier le nombre de features après filtrage
        source_feature_count = self.source_layer.featureCount()
        logger.info("=" * 60)
        logger.info(f"✓ SUCCESS: Source layer filtered")
        logger.info(f"  → {source_feature_count} feature(s) remaining")
        logger.info("=" * 60)
        
        if source_feature_count == 0:
            logger.warning("⚠ WARNING: Source layer has ZERO features after filter!")
            logger.warning("  → Distant layers may return no results")
            logger.warning("  → Consider adjusting filter criteria")

        self.setProgress((1 / self.layers_count) * 100)

        # ═══════════════════════════════════════════════════════════════
        # ÉTAPE 2: FILTRER LES COUCHES DISTANTES (si prédicats géométriques)
        # ═══════════════════════════════════════════════════════════════
        
        has_geom_predicates = self.task_parameters["filtering"]["has_geometric_predicates"]
        logger.info(f"\n🔍 Checking if distant layers should be filtered...")
        logger.info(f"  has_geometric_predicates: {has_geom_predicates}")
        
        if has_geom_predicates:
            geom_predicates_list = self.task_parameters["filtering"]["geometric_predicates"]
            logger.info(f"  geometric_predicates list: {geom_predicates_list}")
            logger.info(f"  geometric_predicates count: {len(geom_predicates_list)}")

            if len(geom_predicates_list) > 0:
                
                logger.info("")
                logger.info("=" * 60)
                logger.info("STEP 2/2: Filtering DISTANT LAYERS")
                logger.info("=" * 60)
                logger.info(f"  → {len(self.task_parameters['task']['layers'])} layer(s) to filter")
                
                source_predicates = self.task_parameters["filtering"]["geometric_predicates"]
                # source_predicates is a list, not a dict
                logger.info(f"  → Geometric predicates: {source_predicates}")
                
                for key in source_predicates:
                    index = None
                    if key in self.predicates:
                        index = list(self.predicates).index(key)
                        if index >= 0:
                            self.current_predicates[str(index)] = self.predicates[key]

                logger.info(f"  → Current predicates configured: {self.current_predicates}")
                logger.info(f"\n🚀 Calling manage_distant_layers_geometric_filtering()...")
                
                result = self.manage_distant_layers_geometric_filtering()

                if self.isCanceled():
                    logger.warning("⚠ Task canceled during distant layers filtering")
                    return False
                
                if result is False:
                    logger.error("=" * 60)
                    logger.error("✗ PARTIAL SUCCESS: Source OK, but distant layers FAILED")
                    logger.error("=" * 60)
                    logger.warning("  → Source layer remains filtered")
                    logger.warning("  → Check logs for distant layer errors")
                    return False
                
                logger.info("=" * 60)
                logger.info("✓ COMPLETE SUCCESS: All layers filtered")
                logger.info("=" * 60)
            else:
                logger.info("  → No geometric predicates configured")
                logger.info("  → Only source layer filtered")
        else:
            logger.info("  → Geometric filtering disabled")
            logger.info("  → Only source layer filtered")

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
        """
        Execute undo operation using the new HistoryManager system.
        
        This method now uses the in-memory history manager to restore the previous
        filter state instead of manipulating the database history table directly.
        
        IMPORTANT: This bypasses manage_layer_subset_strings to avoid triggering
        the old _unfilter_action that would delete database history entries.
        """
        # Get history manager from task parameters (passed from filter_mate_app)
        history_manager = self.task_parameters["task"].get("history_manager")
        
        if not history_manager:
            logger.error("FilterMate: No history_manager in task parameters, cannot undo")
            return False
        
        # Get history for source layer
        history = history_manager.get_history(self.source_layer.id())
        
        if not history or not history.can_undo():
            logger.info("FilterMate: No undo history available, clearing filters")
            # No history available - clear filters as fallback
            safe_set_subset_string(self.source_layer, '')
            
            # Clear filters on associated layers too
            i = 1
            self.setProgress((i/self.layers_count)*100)
            
            for layer_provider_type in self.layers:
                for layer, layer_props in self.layers[layer_provider_type]:
                    safe_set_subset_string(layer, '')
                    i += 1
                    self.setProgress((i/self.layers_count)*100)
                    if self.isCanceled():
                        return False
            return True
        
        # Use history manager to get previous state
        previous_state = history.undo()
        
        if previous_state:
            logger.info(f"FilterMate: Restoring previous filter: {previous_state.description}")
            # Apply previous filter expression to source layer directly
            safe_set_subset_string(self.source_layer, previous_state.expression)
            
            # Restore associated layers filters from their history
            i = 1
            self.setProgress((i/self.layers_count)*100)
            
            for layer_provider_type in self.layers:
                for layer, layer_props in self.layers[layer_provider_type]:
                    # Get history for this associated layer
                    layer_history = history_manager.get_history(layer.id())
                    
                    if layer_history and layer_history.can_undo():
                        # Restore previous filter for this layer
                        layer_previous_state = layer_history.undo()
                        if layer_previous_state:
                            safe_set_subset_string(layer, layer_previous_state.expression)
                            logger.info(f"FilterMate: Restored filter for layer {layer.name()}: {layer_previous_state.description}")
                        else:
                            # No previous state available, clear the filter
                            safe_set_subset_string(layer, '')
                            logger.debug(f"FilterMate: No previous state for layer {layer.name()}, clearing filter")
                    else:
                        # No history available for this layer, clear the filter
                        safe_set_subset_string(layer, '')
                        logger.debug(f"FilterMate: No history for layer {layer.name()}, clearing filter")
                    
                    i += 1
                    self.setProgress((i/self.layers_count)*100)
                    if self.isCanceled():
                        return False
        else:
            logger.warning("FilterMate: History undo returned None, clearing filters")
            safe_set_subset_string(self.source_layer, '')
            
            i = 1
            for layer_provider_type in self.layers:
                for layer, layer_props in self.layers[layer_provider_type]:
                    safe_set_subset_string(layer, '')
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
        
        # Batch export flags
        batch_output_folder = config.get("BATCH_OUTPUT_FOLDER", False)
        batch_zip = config.get("BATCH_ZIP", False)
        
        # Debug logging
        logger.debug(f"Export config keys: {list(config.keys())}")
        logger.debug(f"BATCH_OUTPUT_FOLDER value: {batch_output_folder} (type: {type(batch_output_folder)})")
        logger.debug(f"BATCH_ZIP value: {batch_zip} (type: {type(batch_zip)})")
        
        return {
            'layers': layers,
            'projection': projection,
            'styles': styles,
            'datatype': datatype,
            'output_folder': output_folder,
            'zip_path': zip_path,
            'batch_output_folder': batch_output_folder,
            'batch_zip': batch_zip
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
            layer_names: List of layer names (str) or layer info dicts to export
            output_path: Output GPKG file path
            save_styles: Whether to include layer styles
            
        Returns:
            bool: True if successful
        """
        logger.info(f"Exporting {len(layer_names)} layer(s) to GPKG: {output_path}")
        
        # Collect layer objects
        layer_objects = []
        for layer_item in layer_names:
            # Handle both dict (layer info) and string (layer name) formats
            layer_name = layer_item['layer_name'] if isinstance(layer_item, dict) else layer_item
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
            layer_names: List of layer names (str) or layer info dicts to export
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
        for idx, layer_item in enumerate(layer_names, 1):
            # Handle both dict (layer info) and string (layer name) formats
            layer_name = layer_item['layer_name'] if isinstance(layer_item, dict) else layer_item
            
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


    def _export_batch_to_folder(self, layer_names, output_folder, projection, datatype, style_format, save_styles):
        """
        Export multiple layers to a directory with one file per layer.
        Each layer is exported separately to the specified directory.
        
        Args:
            layer_names: List of layer names (str) or layer info dicts to export
            output_folder: Output directory path
            projection: Target CRS or None
            datatype: Export format
            style_format: Style file format or None
            save_styles: Whether to save layer styles
            
        Returns:
            bool: True if all exports successful
        """
        logger.info(f"Batch export: {len(layer_names)} layer(s) to {datatype} in {output_folder}")
        
        # Ensure output directory exists
        if not os.path.exists(output_folder):
            try:
                os.makedirs(output_folder)
                logger.info(f"Created output directory: {output_folder}")
            except Exception as e:
                logger.error(f"Failed to create output directory: {e}")
                return False
        
        total_layers = len(layer_names)
        exported_files = []
        
        for idx, layer_item in enumerate(layer_names, 1):
            # Handle both dict (layer info) and string (layer name) formats
            layer_name = layer_item['layer_name'] if isinstance(layer_item, dict) else layer_item
            
            # Update task description with current progress
            self.setDescription(f"Batch export: layer {idx}/{total_layers}: {layer_name}")
            self.setProgress(int((idx / total_layers) * 100))
            
            layer = self._get_layer_by_name(layer_name)
            if not layer:
                logger.warning(f"Skipping layer '{layer_name}' (not found)")
                continue
            
            # Build output path for this layer
            output_path = os.path.join(output_folder, layer_name)
            logger.info(f"Exporting layer '{layer_name}' to: {output_path}")
            logger.debug(f"Export params - datatype: {datatype}, projection: {projection}, style_format: {style_format}")
            
            try:
                success = self._export_single_layer(
                    layer, output_path, projection, datatype, style_format, save_styles
                )
                
                if success:
                    exported_files.append(output_path)
                    logger.info(f"Successfully exported: {layer_name}")
                else:
                    logger.error(f"Failed to export layer '{layer_name}' (see logs for details)")
                    return False
                    
            except Exception as e:
                import traceback
                logger.error(f"Exception during export of '{layer_name}': {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                return False
            
            if self.isCanceled():
                logger.info("Batch export cancelled by user")
                return False
        
        logger.info(f"Batch export completed: {len(exported_files)} file(s) in {output_folder}")
        return True

    def _export_batch_to_zip(self, layer_names, output_folder, projection, datatype, style_format, save_styles):
        """
        Export multiple layers with one ZIP file per layer.
        Each layer is exported to its own ZIP archive in the specified directory.
        
        Args:
            layer_names: List of layer names (str) or layer info dicts to export
            output_folder: Output directory path for ZIP files
            projection: Target CRS or None
            datatype: Export format
            style_format: Style file format or None
            save_styles: Whether to save layer styles
            
        Returns:
            bool: True if all exports successful
        """
        logger.info(f"Batch ZIP export: {len(layer_names)} layer(s) to {datatype} ZIPs in {output_folder}")
        
        # Ensure output directory exists
        if not os.path.exists(output_folder):
            try:
                os.makedirs(output_folder)
                logger.info(f"Created output directory: {output_folder}")
            except Exception as e:
                logger.error(f"Failed to create output directory: {e}")
                return False
        
        total_layers = len(layer_names)
        exported_zips = []
        
        for idx, layer_item in enumerate(layer_names, 1):
            # Handle both dict (layer info) and string (layer name) formats
            layer_name = layer_item['layer_name'] if isinstance(layer_item, dict) else layer_item
            
            # Update task description with current progress
            self.setDescription(f"Batch ZIP export: layer {idx}/{total_layers}: {layer_name}")
            self.setProgress(int((idx / total_layers) * 100))
            
            layer = self._get_layer_by_name(layer_name)
            if not layer:
                logger.warning(f"Skipping layer '{layer_name}' (not found)")
                continue
            
            # Create temporary directory for this layer's export
            import tempfile
            temp_dir = tempfile.mkdtemp(prefix=f"fm_batch_{layer_name}_")
            
            try:
                # Export layer to temporary directory
                temp_output = os.path.join(temp_dir, layer_name)
                logger.info(f"Exporting layer '{layer_name}' to temp: {temp_output}")
                logger.debug(f"Export params - datatype: {datatype}, projection: {projection}, style_format: {style_format}")
                
                success = self._export_single_layer(
                    layer, temp_output, projection, datatype, style_format, save_styles
                )
                
                if not success:
                    logger.error(f"Failed to export layer '{layer_name}' (see logs for details)")
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return False
                
                # Create ZIP for this layer
                zip_path = os.path.join(output_folder, f"{layer_name}.zip")
                logger.info(f"Creating ZIP archive: {zip_path} from {temp_dir}")
                
                # List files in temp_dir for debugging
                try:
                    files_in_temp = os.listdir(temp_dir)
                    logger.debug(f"Files in temp_dir: {files_in_temp}")
                except Exception as list_err:
                    logger.warning(f"Could not list temp_dir: {list_err}")
                
                zip_success = self._create_zip_archive(zip_path, temp_dir)
                
                if zip_success:
                    exported_zips.append(zip_path)
                    logger.info(f"Successfully created ZIP: {zip_path}")
                else:
                    logger.error(f"Failed to create ZIP for '{layer_name}' at {zip_path}")
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return False
                
                # Clean up temporary directory
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
                
            except Exception as e:
                import traceback
                logger.error(f"Error during batch ZIP export of '{layer_name}': {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
                return False
            
            if self.isCanceled():
                logger.info("Batch ZIP export cancelled by user")
                return False
        
        logger.info(f"Batch ZIP export completed: {len(exported_zips)} ZIP file(s) in {output_folder}")
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
        import zipfile as zipfile_module
        
        # Validate folder exists
        if not os.path.exists(folder_to_zip) or not os.path.isdir(folder_to_zip):
            logger.error(f"Folder to zip does not exist or is not a directory: {folder_to_zip}")
            return False
        
        self.setDescription(f"Creating zip archive...")
        self.setProgress(95)
        
        logger.info(f"Creating zip archive: {zip_path} from {folder_to_zip}")
        
        try:
            # Create ZIP file
            with zipfile_module.ZipFile(zip_path, 'w', zipfile_module.ZIP_DEFLATED) as zipf:
                # Walk through all files in the folder
                for root, dirs, files in os.walk(folder_to_zip):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Calculate relative path for archive
                        arcname = os.path.relpath(file_path, os.path.dirname(folder_to_zip))
                        zipf.write(file_path, arcname)
                        logger.debug(f"Added to ZIP: {arcname}")
                        
                        # Check for cancellation
                        if self.isCanceled():
                            logger.info("ZIP creation cancelled by user")
                            # Remove incomplete ZIP file
                            try:
                                os.remove(zip_path)
                            except (OSError, PermissionError):
                                pass
                            return False
            
            # Verify ZIP was created
            if not os.path.exists(zip_path):
                logger.error(f"ZIP file was not created: {zip_path}")
                return False
            
            self.setProgress(100)
            logger.info(f"ZIP archive created successfully: {zip_path} ({os.path.getsize(zip_path)} bytes)")
            return True
            
        except Exception as e:
            import traceback
            logger.error(f"Failed to create ZIP archive: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Clean up incomplete ZIP file
            try:
                if os.path.exists(zip_path):
                    os.remove(zip_path)
            except (OSError, PermissionError):
                pass
            return False

    def execute_exporting(self):
        """
        Export selected layers to specified format with optional styles.
        
        REFACTORED: Decomposed from 235 lines to ~65 lines using helper methods.
        Main method now validates parameters and orchestrates export workflow.
        
        Supports:
        - Standard export (single file or directory)
        - Batch output folder mode (one file per layer)
        - Batch ZIP mode (one ZIP per layer)
        
        Returns:
            bool: True if export successful
        """
        # Validate and extract export parameters
        export_config = self._validate_export_parameters()
        if not export_config:
            self.message = 'Export configuration validation failed'
            return False
        
        layers = export_config['layers']
        projection = export_config['projection']
        datatype = export_config['datatype']
        output_folder = export_config['output_folder']
        style_format = export_config['styles']
        zip_path = export_config['zip_path']
        batch_output_folder = export_config.get('batch_output_folder', False)
        batch_zip = export_config.get('batch_zip', False)
        save_styles = self.task_parameters["task"]['EXPORTING'].get("HAS_STYLES_TO_EXPORT", False)
        
        # Execute export based on mode and format
        export_success = False
        
        # BATCH MODE: One file per layer in folder
        if batch_output_folder:
            logger.info("Batch output folder mode enabled")
            export_success = self._export_batch_to_folder(
                layers, output_folder, projection, datatype, style_format, save_styles
            )
            if export_success:
                self.message = f'Batch export: {len(layers)} layer(s) exported to <a href="file:///{output_folder}">{output_folder}</a>'
            else:
                self.message = f'Batch export failed for {len(layers)} layer(s)'
            return export_success
        
        # BATCH MODE: One ZIP per layer
        if batch_zip:
            logger.info("Batch ZIP mode enabled")
            export_success = self._export_batch_to_zip(
                layers, output_folder, projection, datatype, style_format, save_styles
            )
            if export_success:
                self.message = f'Batch ZIP export: {len(layers)} ZIP file(s) created in <a href="file:///{output_folder}">{output_folder}</a>'
            else:
                self.message = f'Batch ZIP export failed for {len(layers)} layer(s)'
            return export_success
        
        # STANDARD MODE: Original behavior
        if datatype == 'GPKG':
            # GeoPackage export using processing
            export_success = self._export_to_gpkg(layers, output_folder, save_styles)
        else:
            # Other formats (Shapefile, GeoJSON, etc.)
            if not os.path.exists(output_folder):
                logger.error(f"Output path does not exist: {output_folder}")
                self.message = f'Output path does not exist: {output_folder}'
                return False
            
            if os.path.isdir(output_folder) and len(layers) > 1:
                # Multiple layers to directory
                export_success = self._export_multiple_layers_to_directory(
                    layers, output_folder, projection, datatype, style_format, save_styles
                )
            elif len(layers) == 1:
                # Single layer export
                # Handle both dict (layer info) and string (layer name) formats
                layer_name = layers[0]['layer_name'] if isinstance(layers[0], dict) else layers[0]
                layer = self._get_layer_by_name(layer_name)
                if not layer:
                    return False
                
                export_success = self._export_single_layer(
                    layer, output_folder, projection, datatype, style_format, save_styles
                )
            else:
                logger.error(f"Invalid export configuration: {len(layers)} layers but output is not a directory")
                self.message = f'Invalid export configuration: {len(layers)} layers but output is not a directory'
                return False
        
        if not export_success:
            self.message = 'Export failed'
            return False
        
        if self.isCanceled():
            logger.info("Export cancelled by user before zip")
            self.message = 'Export cancelled by user'
            return False
        
        # Create zip archive if requested (standard mode only)
        zip_created = False
        if zip_path:
            zip_created = self._create_zip_archive(zip_path, output_folder)
            if not zip_created:
                self.message = 'Failed to create ZIP archive'
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
        result = safe_set_subset_string(layer, layer_subsetString)
        
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
        Handle Spatialite temporary tables for filtering.
        
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
            return safe_set_subset_string(layer, sql_subset_string)
        
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
        # Initialize prepared statements manager if needed
        if not self._ps_manager:
            # Detect provider type from connection
            provider_type = 'spatialite'  # Default to spatialite for filtermate_db
            if hasattr(conn, 'get_backend_pid'):  # psycopg2 connection
                provider_type = 'postgresql'
            self._ps_manager = create_prepared_statements(conn, provider_type)
        
        # Use prepared statement if available
        if self._ps_manager:
            try:
                return self._ps_manager.insert_subset_history(
                    history_id=str(uuid.uuid4()),
                    project_uuid=self.project_uuid,
                    layer_id=layer.id(),
                    source_layer_id=self.source_layer.id(),
                    seq_order=seq_order,
                    subset_string=sql_subset_string
                )
            except Exception as e:
                logger.warning(f"Prepared statement failed, falling back to direct SQL: {e}")
        
        # Fallback to direct SQL if prepared statements unavailable
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
        safe_set_subset_string(layer, layer_subset_string)
        
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
        # Delete history using prepared statement
        if self._ps_manager:
            try:
                self._ps_manager.delete_subset_history(self.project_uuid, layer.id())
            except Exception as e:
                logger.warning(f"Prepared statement failed, falling back to direct SQL: {e}")
                # Fallback
                cur.execute(
                    f"""DELETE FROM fm_subset_history 
                        WHERE fk_project = '{self.project_uuid}' AND layer_id = '{layer.id()}';""" 
                )
                conn.commit()
        else:
            # Direct SQL if no prepared statements
            cur.execute(
                f"""DELETE FROM fm_subset_history 
                    WHERE fk_project = '{self.project_uuid}' AND layer_id = '{layer.id()}';""" 
            )
            conn.commit()        # Drop materialized view
        schema = self.current_materialized_view_schema
        sql_drop = f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."mv_{name}" CASCADE;'
        
        connexion = self.task_parameters["task"]["options"]["ACTIVE_POSTGRESQL"]
        self._execute_postgresql_commands(connexion, [sql_drop])
        
        # Clear subset string
        safe_set_subset_string(layer, '')
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
        
        # Delete history using prepared statement
        if self._ps_manager:
            try:
                self._ps_manager.delete_subset_history(self.project_uuid, layer.id())
            except Exception as e:
                logger.warning(f"Prepared statement failed, falling back to direct SQL: {e}")
                # Fallback
                cur.execute(
                    f"""DELETE FROM fm_subset_history 
                        WHERE fk_project = '{self.project_uuid}' AND layer_id = '{layer.id()}';"""
                )
                conn.commit()
        else:
            # Direct SQL if no prepared statements
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
        safe_set_subset_string(layer, '')
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
                    safe_set_subset_string(layer, '')
            
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
                safe_set_subset_string(layer, layer_subset_string)
        else:
            safe_set_subset_string(layer, '')
        
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
            # Exception occurred during task execution
            error_msg = f"Exception: {self.exception}"
            logger.error(f"Task finished with exception: {error_msg}")
            
            # Display error to user
            iface.messageBar().pushMessage(
                error_msg,
                MESSAGE_TASKS_CATEGORIES[self.task_action], Qgis.Critical)
            
            # Only raise exception if task completely failed (result is False)
            # If result is True, some layers may have been processed successfully
            if result is False:
                raise self.exception
            else:
                # Partial success - log but don't raise
                logger.warning(
                    f"Task completed with partial success. "
                    f"Some operations succeeded but an exception occurred: {self.exception}"
                )






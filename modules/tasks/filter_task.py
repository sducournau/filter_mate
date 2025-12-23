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
    QgsMemoryProviderUtils,
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
from ..backends.spatialite_backend import SpatialiteGeometricFilter

# Import utilities
from ..appUtils import (
    safe_set_subset_string,
    get_source_table_name,
    get_datasource_connexion_from_layer,
    get_primary_key_name,
    detect_layer_provider_type,
    geometry_type_to_string,
    sanitize_sql_identifier,
    sanitize_filename
)

# Import object safety utilities (v2.3.9 - stability fix)
from ..object_safety import (
    is_sip_deleted, is_valid_layer, safe_disconnect
)

# Import prepared statements manager
from ..prepared_statements import create_prepared_statements

# Import task utilities (Phase 3a extractions)
from .task_utils import (
    spatialite_connect,
    safe_spatialite_connect,
    sqlite_execute_with_retry,
    ensure_db_directory_exists,
    get_best_metric_crs,
    should_reproject_layer,
    SQLITE_TIMEOUT,
    SQLITE_MAX_RETRIES,
    MESSAGE_TASKS_CATEGORIES
)

# Import geometry safety module (v2.3.9 - stability fix)
from ..geometry_safety import (
    validate_geometry,
    validate_geometry_for_geos,
    safe_as_geometry_collection,
    safe_as_polygon,
    safe_buffer,
    safe_unary_union,
    safe_collect_geometry,
    safe_convert_to_multi_polygon,
    extract_polygons_from_collection,
    repair_geometry,
    get_geometry_type_name,
    create_geos_safe_layer
)

# Import geometry cache (Phase 3a extraction)
from .geometry_cache import SourceGeometryCache

# Import query expression cache (Phase 4 optimization)
from .query_cache import QueryExpressionCache, get_query_cache

# Import parallel executor (Phase 4 optimization)
from .parallel_executor import ParallelFilterExecutor, ParallelConfig

# Import streaming exporter (Phase 4 optimization)
from .result_streaming import StreamingExporter, StreamingConfig

class FilterEngineTask(QgsTask):
    """Main QgsTask class which filter and unfilter data"""
    
    # Cache de classe (partagé entre toutes les instances de FilterEngineTask)
    _geometry_cache = SourceGeometryCache()
    
    # Cache d'expressions (partagé entre toutes les instances)
    _expression_cache = None  # Initialized lazily via get_query_cache()

    def __init__(self, description, task_action, task_parameters):

        QgsTask.__init__(self, description, QgsTask.CanCancel)

        self.exception = None
        self.task_action = task_action
        self.task_parameters = task_parameters
        
        # Référence au cache partagé
        self.geom_cache = FilterEngineTask._geometry_cache
        
        # Référence au cache d'expressions (lazy init)
        self.expr_cache = get_query_cache()

        self.db_file_path = None
        self.project_uuid = None

        self.layers_count = None
        self.layers = {}
        self.provider_list = []
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
        
        Delegates to centralized safe_spatialite_connect() in task_utils.py.
        
        Returns:
            sqlite3.Connection: Database connection
            
        Raises:
            OSError: If directory cannot be created
            sqlite3.OperationalError: If database cannot be opened
        """
        return safe_spatialite_connect(self.db_file_path)

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
        
        infos = self.task_parameters["infos"]
        
        # First, we need layer_id to find the layer (cannot be auto-filled)
        if "layer_id" not in infos or infos["layer_id"] is None:
            error_msg = "task_parameters['infos'] missing required key: ['layer_id']"
            logger.error(error_msg)
            self.exception = KeyError(error_msg)
            return False
        
        # Try to find the layer by ID first (more reliable than name)
        layer_id = infos["layer_id"]
        layer_obj = self.PROJECT.mapLayer(layer_id)
        
        # Fallback: try by name if available
        if layer_obj is None and infos.get("layer_name"):
            layers = [
                layer for layer in self.PROJECT.mapLayersByName(infos["layer_name"]) 
                if layer.id() == layer_id
            ]
            if layers:
                layer_obj = layers[0]
        
        if layer_obj is None:
            error_msg = f"Layer with id '{layer_id}' not found in project"
            logger.error(error_msg)
            self.exception = KeyError(error_msg)
            return False
        
        # Auto-fill missing required keys from the QGIS layer object
        if "layer_name" not in infos or infos["layer_name"] is None:
            infos["layer_name"] = layer_obj.name()
            logger.info(f"Auto-filled layer_name='{infos['layer_name']}' for source layer")
        
        if "layer_crs_authid" not in infos or infos["layer_crs_authid"] is None:
            infos["layer_crs_authid"] = layer_obj.sourceCrs().authid()
            logger.info(f"Auto-filled layer_crs_authid='{infos['layer_crs_authid']}' for source layer")
        
        self.layers_count = 1
        self.source_layer = layer_obj
        self.source_crs = self.source_layer.sourceCrs()
        self.source_layer_crs_authid = infos["layer_crs_authid"]
        
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
        
        For 'filter' action: respects has_layers_to_filter flag OR processes if layers exist
        For 'unfilter' and 'reset': processes all layers in the list regardless of flag
        (to clean up filters that were applied previously)
        """
        logger.info(f"🔍 _organize_layers_to_filter() called for action: {self.task_action}")
        logger.info(f"  has_layers_to_filter: {self.task_parameters['filtering']['has_layers_to_filter']}")
        logger.info(f"  task['layers'] count: {len(self.task_parameters['task'].get('layers', []))}")
        
        # For 'filter' action, process layers if:
        # - has_layers_to_filter is True, OR
        # - There are layers in the task parameters (user selected layers)
        # For 'unfilter' and 'reset', always process layers to clean up previous filters
        has_layers_to_filter = self.task_parameters["filtering"]["has_layers_to_filter"]
        has_layers_in_params = len(self.task_parameters['task'].get('layers', [])) > 0
        
        # FIX CRITIQUE: Ne retourner que si vraiment aucune couche n'est disponible
        # La vérification has_layers_to_filter peut être False même si des couches sont présentes
        if self.task_action == 'filter' and not has_layers_in_params:
            logger.info("  ℹ️ No layers in task params - skipping distant layers organization")
            return
        
        # Get forced backends from task parameters (set by user in UI)
        forced_backends = self.task_parameters.get('forced_backends', {})
        
        # Process all layers in the list
        for layer_props in self.task_parameters["task"]["layers"]:
            provider_type = layer_props["layer_provider_type"]
            layer_name = layer_props.get("layer_name", "unknown")
            layer_id = layer_props.get("layer_id", "unknown")
            
            # PRIORITY 1: Check if backend is forced by user for this layer
            forced_backend = forced_backends.get(layer_id)
            if forced_backend:
                logger.info(f"  🔒 Using FORCED backend '{forced_backend}' for layer '{layer_name}'")
                provider_type = forced_backend
                # Mark in layer_props for later reference
                layer_props["_effective_provider_type"] = forced_backend
                layer_props["_forced_backend"] = True
            else:
                # PRIORITY 2: Check if PostgreSQL connection is available
                # If not, use OGR fallback which works with all layer types via QGIS processing
                if provider_type == PROVIDER_POSTGRES:
                    postgresql_connection_available = layer_props.get("postgresql_connection_available", False)
                    if not postgresql_connection_available or not POSTGRESQL_AVAILABLE:
                        logger.warning(f"  PostgreSQL layer '{layer_name}' has no connection available - using OGR fallback")
                        provider_type = PROVIDER_OGR
                        # Mark in layer_props for later reference
                        layer_props["_effective_provider_type"] = PROVIDER_OGR
                        layer_props["_postgresql_fallback"] = True
                
                # PRIORITY 3: Verify provider_type is correct by detecting it from actual layer
                # This ensures GeoPackage layers are correctly identified as 'spatialite'
                # even if layer_props had incorrect provider_type from previous operations
                # STABILITY FIX v2.3.9: Validate layer before access to prevent access violations
                from ..appUtils import detect_layer_provider_type
                layer_by_id = self.PROJECT.mapLayer(layer_id)
                if layer_by_id and is_valid_layer(layer_by_id):
                    detected_provider = detect_layer_provider_type(layer_by_id)
                    if detected_provider != provider_type and detected_provider != 'unknown':
                        logger.warning(
                            f"  ⚠️ Provider type mismatch for '{layer_name}': "
                            f"stored='{provider_type}', detected='{detected_provider}'. "
                            f"Using detected type."
                        )
                        provider_type = detected_provider
                        # Update layer_props with correct provider type
                        layer_props["layer_provider_type"] = provider_type
            
            logger.info(f"  Processing layer: {layer_name} ({provider_type}), id={layer_id}")
            
            # Initialize provider list if needed
            if provider_type not in self.layers:
                self.layers[provider_type] = []
            
            # STABILITY FIX v2.3.9: Validate layers before adding to prevent access violations
            # Find layer by name and ID (preferred method)
            layers = []
            for layer in self.PROJECT.mapLayersByName(layer_props["layer_name"]):
                if is_sip_deleted(layer):
                    continue
                if layer.id() == layer_props["layer_id"] and is_valid_layer(layer):
                    layers.append(layer)
            
            # Fallback: If not found by name, try by ID only (layer may have been renamed)
            if not layers:
                logger.debug(f"    Layer not found by name '{layer_name}', trying by ID...")
                layer_by_id = self.PROJECT.mapLayer(layer_id)
                if layer_by_id and is_valid_layer(layer_by_id):
                    layers = [layer_by_id]
                    try:
                        logger.info(f"    Found layer by ID (name may have changed to '{layer_by_id.name()}')")
                        # Update layer_props with current name
                        layer_props["layer_name"] = layer_by_id.name()
                    except RuntimeError:
                        logger.warning(f"    Layer {layer_id} became invalid during access")
                        layers = []
            
            if layers:
                self.layers[provider_type].append([layers[0], layer_props])
                self.layers_count += 1
                logger.info(f"    ✓ Added to filter list (total: {self.layers_count})")
            else:
                logger.warning(f"    ⚠️ Layer not found in project: {layer_name} (id: {layer_id})")
                # Log all layer IDs in project for debugging
                all_layer_ids = list(self.PROJECT.mapLayers().keys())
                logger.debug(f"    Available layer IDs in project: {all_layer_ids[:10]}{'...' if len(all_layer_ids) > 10 else ''}")
        
        self.provider_list = list(self.layers.keys())
        logger.info(f"  📊 Final organized layers count: {self.layers_count}, providers: {self.provider_list}")
        
        # DIAGNOSTIC: Afficher les couches organisées pour debug
        if self.layers_count > 1:
            logger.info(f"  ✓ Remote layers organized successfully:")
            for provider, layers_list in self.layers.items():
                for layer, props in layers_list:
                    logger.info(f"    - {layer.name()} ({provider})")
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
        
        infos = self.task_parameters.get("infos", {})
        
        # Auto-fill missing keys from source_layer if available
        if self.source_layer:
            # Auto-fill layer_name
            if "layer_name" not in infos or infos["layer_name"] is None:
                infos["layer_name"] = self.source_layer.name()
                logger.info(f"Auto-filled layer_name='{infos['layer_name']}' from source layer")
            
            # Auto-fill layer_id  
            if "layer_id" not in infos or infos["layer_id"] is None:
                infos["layer_id"] = self.source_layer.id()
                logger.info(f"Auto-filled layer_id='{infos['layer_id']}' from source layer")
            
            # Auto-fill layer_provider_type
            # Use detect_layer_provider_type to get correct provider for backend selection
            if "layer_provider_type" not in infos or infos["layer_provider_type"] is None:
                detected_type = detect_layer_provider_type(self.source_layer)
                infos["layer_provider_type"] = detected_type
                logger.info(f"Auto-filled layer_provider_type='{detected_type}' from source layer")
            
            # Auto-fill layer_geometry_field
            if "layer_geometry_field" not in infos or infos["layer_geometry_field"] is None:
                try:
                    geom_col = self.source_layer.dataProvider().geometryColumn()
                    if geom_col:
                        infos["layer_geometry_field"] = geom_col
                    else:
                        # Default based on provider
                        if infos.get("layer_provider_type") == 'postgresql':
                            infos["layer_geometry_field"] = 'geom'
                        else:
                            infos["layer_geometry_field"] = 'geometry'
                    logger.info(f"Auto-filled layer_geometry_field='{infos['layer_geometry_field']}' from source layer")
                except Exception as e:
                    infos["layer_geometry_field"] = 'geom'
                    logger.warning(f"Could not detect geometry column, using 'geom': {e}")
            
            # Auto-fill primary_key_name
            if "primary_key_name" not in infos or infos["primary_key_name"] is None:
                pk_indices = self.source_layer.primaryKeyAttributes()
                if pk_indices:
                    infos["primary_key_name"] = self.source_layer.fields()[pk_indices[0]].name()
                else:
                    # Fallback to first field
                    if self.source_layer.fields():
                        infos["primary_key_name"] = self.source_layer.fields()[0].name()
                    else:
                        infos["primary_key_name"] = 'id'
                logger.info(f"Auto-filled primary_key_name='{infos['primary_key_name']}' from source layer")
            
            # Auto-fill layer_schema (empty for non-PostgreSQL)
            if "layer_schema" not in infos or infos["layer_schema"] is None:
                if infos.get("layer_provider_type") == 'postgresql':
                    import re
                    source = self.source_layer.source()
                    match = re.search(r'table="([^"]+)"\.', source)
                    if match:
                        infos["layer_schema"] = match.group(1)
                    else:
                        infos["layer_schema"] = 'public'
                else:
                    infos["layer_schema"] = ''
                logger.info(f"Auto-filled layer_schema='{infos['layer_schema']}' from source layer")
        
        # Validate required keys exist after auto-fill
        required_keys = [
            "layer_provider_type", "layer_name", 
            "layer_id", "layer_geometry_field", "primary_key_name"
        ]
        missing_keys = [k for k in required_keys if k not in infos or infos[k] is None]
        
        if missing_keys:
            error_msg = f"task_parameters['infos'] missing required keys for filtering: {missing_keys}"
            logger.error(error_msg)
            raise KeyError(error_msg)
        
        # Extract basic layer information
        self.param_source_provider_type = infos["layer_provider_type"]
        
        # PRIORITY 1: Check if backend is forced by user for source layer
        forced_backends = self.task_parameters.get('forced_backends', {})
        source_layer_id = infos.get("layer_id")
        forced_backend = forced_backends.get(source_layer_id) if source_layer_id else None
        
        if forced_backend:
            logger.info(f"🔒 Source layer: Using FORCED backend '{forced_backend}'")
            self.param_source_provider_type = forced_backend
            self._source_forced_backend = True
            self._source_postgresql_fallback = False
        else:
            self._source_forced_backend = False
            # PRIORITY 2: Check PostgreSQL connection availability for source layer
            # If PostgreSQL layer but no connection, use OGR fallback which works with all layer types
            if self.param_source_provider_type == PROVIDER_POSTGRES:
                postgresql_connection_available = infos.get("postgresql_connection_available", False)
                if not postgresql_connection_available or not POSTGRESQL_AVAILABLE:
                    logger.warning(f"Source layer is PostgreSQL but connection unavailable - using OGR fallback")
                    self.param_source_provider_type = PROVIDER_OGR
                    self._source_postgresql_fallback = True
                else:
                    self._source_postgresql_fallback = False
            else:
                self._source_postgresql_fallback = False
        
        self.param_source_schema = infos["layer_schema"]
        # CRITICAL FIX: Use layer_table_name (actual DB table name) for PostgreSQL, not layer_name (display name)
        # layer_name is the QGIS layer name which can differ from the actual database table name
        # e.g., layer_name="Distribution Cluster" but layer_table_name="distribution_clusters"
        # This is essential for building correct SQL queries in EXISTS subqueries
        self.param_source_table = infos.get("layer_table_name") or infos["layer_name"]
        self.param_source_layer_name = infos["layer_name"]  # Keep display name for logging
        self.param_source_layer_id = infos["layer_id"]
        self.param_source_geom = infos["layer_geometry_field"]
        self.primary_key_name = infos["primary_key_name"]
        
        logger.debug(f"Filtering layer: {self.param_source_layer_name} (table: {self.param_source_table}, Provider: {self.param_source_provider_type})")
        
        # Extract filtering configuration
        self.has_combine_operator = self.task_parameters["filtering"]["has_combine_operator"]
        self.source_layer_fields_names = [
            field.name() for field in self.source_layer.fields() 
            if field.name() != self.primary_key_name
        ]
        
        # TOUJOURS capturer le filtre existant si présent
        # Cela garantit que les filtres ne sont jamais perdus lors du changement de couche
        if self.source_layer.subsetString():
            self.param_source_old_subset = self.source_layer.subsetString()
            logger.info(f"FilterMate: Filtre existant détecté sur {self.param_source_table}: {self.param_source_old_subset[:100]}...")
        
        if self.has_combine_operator:
            self.param_source_layer_combine_operator = self.task_parameters["filtering"]["source_layer_combine_operator"]
            self.param_other_layers_combine_operator = self.task_parameters["filtering"]["other_layers_combine_operator"]

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
        
        COMPORTEMENT PAR DÉFAUT:
        - Si un filtre existant est présent, il est TOUJOURS préservé
        - Si aucun opérateur n'est spécifié, utilise AND par défaut
        - Cela garantit que les filtres ne sont jamais perdus lors du changement de couche
        
        Returns:
            str: Combined expression
        """
        # Si aucun filtre existant, retourner la nouvelle expression
        if not self.param_source_old_subset:
            return expression
        
        # CRITICAL FIX: Avoid duplicating identical expressions
        # Normalize both expressions for comparison (strip whitespace and outer parentheses)
        def normalize_expr(expr):
            if not expr:
                return ""
            import re
            expr = expr.strip()
            # Normalize whitespace: replace multiple spaces with single space
            expr = re.sub(r'\s+', ' ', expr)
            # Remove outer parentheses if present
            while expr.startswith('(') and expr.endswith(')'):
                # Check if these are matching outer parentheses
                depth = 0
                is_outer = True
                for i, char in enumerate(expr):
                    if char == '(':
                        depth += 1
                    elif char == ')':
                        depth -= 1
                        if depth == 0 and i < len(expr) - 1:
                            is_outer = False
                            break
                if is_outer and depth == 0:
                    expr = expr[1:-1].strip()
                    # Normalize whitespace again after stripping parentheses
                    expr = re.sub(r'\s+', ' ', expr)
                else:
                    break
            return expr
        
        normalized_new = normalize_expr(expression)
        normalized_old = normalize_expr(self.param_source_old_subset)
        
        logger.debug(f"FilterMate: Comparing expressions:")
        logger.debug(f"  → normalized_new: '{normalized_new}'")
        logger.debug(f"  → normalized_old: '{normalized_old}'")
        
        # If expressions are identical, don't duplicate
        if normalized_new == normalized_old:
            logger.info(f"FilterMate: New expression identical to old subset - skipping duplication")
            logger.debug(f"  → Expression: '{expression[:80]}...'")
            return expression
        
        # If new expression is already contained in old subset, don't duplicate
        if normalized_new in normalized_old:
            logger.info(f"FilterMate: New expression already in old subset - skipping duplication")
            logger.debug(f"  → New: '{normalized_new[:60]}...'")
            logger.debug(f"  → Old: '{normalized_old[:60]}...'")
            return self.param_source_old_subset
        
        # CRITICAL FIX: Also check if old subset is contained in new expression
        # This handles the case where the new expression is a superset of the old
        if normalized_old in normalized_new:
            logger.info(f"FilterMate: Old subset already in new expression - returning new expression only")
            logger.debug(f"  → New: '{normalized_new[:60]}...'")
            logger.debug(f"  → Old: '{normalized_old[:60]}...'")
            return expression
        
        # Récupérer l'opérateur de combinaison (ou utiliser AND par défaut)
        combine_operator = self._get_source_combine_operator()
        if not combine_operator:
            # NOUVEAU: Si un filtre existe mais pas d'opérateur, utiliser AND par défaut
            # Cela préserve les filtres existants lors du changement de couche
            combine_operator = 'AND'
            logger.info(f"FilterMate: Aucun opérateur de combinaison défini, utilisation de AND par défaut pour préserver le filtre existant")
        
        # Extract WHERE clause from old subset
        index_where = self.param_source_old_subset.find('WHERE')
        if index_where == -1:
            # If no WHERE clause, simple combination
            return f'( {self.param_source_old_subset} ) {combine_operator} ( {expression} )'
        
        param_old_subset_where = self.param_source_old_subset[index_where:]
        param_source_old_subset = self.param_source_old_subset[:index_where]
        
        # Remove trailing )) if present (legacy handling for malformed expressions)
        if param_old_subset_where.endswith('))'):
            param_old_subset_where = param_old_subset_where[:-1]
        
        # CRITICAL FIX: Removed extra closing parenthesis that was causing SQL syntax errors
        # The bug was: f'... ( {expression} ) )' - two closing parens with only one opening
        # This caused "syntax error at or near ')'" in EXISTS subqueries
        combined = (
            f'{param_source_old_subset} {param_old_subset_where} '
            f'{combine_operator} ( {expression} )'
        )
        
        return combined

    def _build_feature_id_expression(self, features_list):
        """
        Build SQL IN expression from list of feature IDs.
        
        Returns:
            str: SQL expression like "table"."pk" IN (1,2,3) or "pk" IN (1,2,3) for OGR
        """
        # CRITICAL FIX: Handle ctid (PostgreSQL internal identifier)
        # ctid is not accessible via feature[field_name], use feature.id() instead
        if self.primary_key_name == 'ctid':
            features_ids = [str(feature.id()) for feature in features_list]
        else:
            features_ids = [str(feature[self.primary_key_name]) for feature in features_list]
        
        if not features_ids:
            return None
        
        # Build IN clause based on provider type and primary key type
        is_numeric = self.task_parameters["infos"]["primary_key_is_numeric"]
        
        if self.param_source_provider_type == PROVIDER_OGR:
            # OGR: Simple syntax with quoted field name
            # CRITICAL FIX: Use actual primary_key_name, not hardcoded "fid"
            if is_numeric:
                expression = f'"{self.primary_key_name}" IN ({", ".join(features_ids)})'
            else:
                expression = f'"{self.primary_key_name}" IN ({", ".join(repr(fid) for fid in features_ids)})'
        elif self.param_source_provider_type == PROVIDER_SPATIALITE:
            # Spatialite: Simple syntax with quoted field name (no table qualification needed)
            if is_numeric:
                expression = f'"{self.primary_key_name}" IN ({", ".join(features_ids)})'
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
        # COMPORTEMENT PAR DÉFAUT: Si un filtre existe, il est TOUJOURS préservé
        if self.param_source_old_subset:
            combine_operator = self._get_source_combine_operator()
            if not combine_operator:
                # Si aucun opérateur n'est spécifié, utiliser AND par défaut
                # Cela garantit que les filtres existants sont préservés
                combine_operator = 'AND'
                logger.info(f"FilterMate: Aucun opérateur de combinaison défini, utilisation de AND par défaut pour préserver le filtre existant (feature ID list)")
            
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
        task_features = self.task_parameters["task"]["features"]
        
        # DIAGNOSTIC: Log incoming parameters
        logger.info("=" * 60)
        logger.info("🔧 execute_source_layer_filtering DIAGNOSTIC")
        logger.info("=" * 60)
        logger.info(f"   task_expression = '{task_expression}'")
        logger.info(f"   task_features count = {len(task_features) if task_features else 0}")
        if task_features and len(task_features) > 0:
            for i, f in enumerate(task_features[:3]):  # Show first 3
                logger.info(f"      feature[{i}]: id={f.id()}, isValid={f.isValid()}")
        logger.info(f"   source_layer = '{self.source_layer.name() if self.source_layer else 'None'}'")
        logger.info(f"   primary_key_name = '{self.primary_key_name}'")
        logger.info("=" * 60)
        
        logger.debug(f"Task expression: {task_expression}")
        
        # Check if expression is just a field name (no comparison operators)
        is_simple_field = False
        if task_expression:
            qgs_expr = QgsExpression(task_expression)
            is_simple_field = qgs_expr.isField() and not any(
                op in task_expression for op in ['=', '>', '<', '!', 'IN', 'LIKE', 'AND', 'OR']
            )
        
        # Check if geometric filtering is enabled
        has_geom_predicates = self.task_parameters["filtering"]["has_geometric_predicates"]
        geom_predicates_list = self.task_parameters["filtering"].get("geometric_predicates", [])
        has_geometric_filtering = has_geom_predicates and len(geom_predicates_list) > 0
        
        # ================================================================
        # MODE FIELD-BASED: Custom Selection avec champ simple + prédicats géométriques
        # ================================================================
        # COMPORTEMENT ATTENDU:
        #   1. COUCHE SOURCE: Garder le subset existant (PAS de modification)
        #   2. COUCHES DISTANTES: Appliquer filtre géométrique en intersection
        #                         avec les géométries de la couche source déjà filtrée
        #
        # EXEMPLE:
        #   - Couche source avec subset: "homecount > 5" (affiche 100 features)
        #   - Custom selection active avec champ: "drop_ID"
        #   - Prédicats géométriques: "intersects" vers couche distante
        #   → Résultat: Source garde "homecount > 5", distant filtré par intersection avec ces 100 features
        # ================================================================
        if is_simple_field and has_geometric_filtering:
            logger.info("=" * 60)
            logger.info("🔄 FIELD-BASED GEOMETRIC FILTER MODE")
            logger.info("=" * 60)
            logger.info(f"  Expression is simple field: '{task_expression}'")
            logger.info(f"  Geometric filtering enabled: {has_geometric_filtering}")
            logger.info("  → Source layer will NOT be filtered (keeps existing subset)")
            
            # Store the field expression for later use in geometric filtering
            self.is_field_expression = (True, task_expression)
            
            # Keep existing subset - don't modify source layer filter
            self.expression = self.param_source_old_subset if self.param_source_old_subset else ""
            
            # Log detailed information about source layer state
            current_subset = self.source_layer.subsetString()
            feature_count = self.source_layer.featureCount()
            
            if current_subset:
                logger.info(f"  ✓ Source layer has active subset: '{current_subset[:80]}...'")
                logger.info(f"  ✓ {feature_count} filtered features will be used for geometric intersection")
            else:
                logger.info(f"  ℹ Source layer has NO subset - all {feature_count} features will be used")
            
            # Mark as successful - source layer remains with current filter
            result = True
            logger.info("=" * 60)
            return result
        
        # Process QGIS expression if provided
        if task_expression:
            logger.info(f"   → Processing task_expression: '{task_expression}'")
            processed_expr, is_field_expr = self._process_qgis_expression(task_expression)
            logger.info(f"   → processed_expr: '{processed_expr}', is_field_expr: {is_field_expr}")
            
            if processed_expr:
                # Combine with existing subset if needed
                self.expression = self._combine_with_old_subset(processed_expr)
                logger.info(f"   → combined expression: '{self.expression}'")
                
                # Apply filter and update subset
                result = self._apply_filter_and_update_subset(self.expression)
                logger.info(f"   → filter applied result: {result}")
        else:
            logger.info(f"   → No task_expression provided, will try fallback to feature IDs")
        
        # Fallback to feature ID list if expression processing failed
        if not result:
            logger.info(f"   → Fallback: trying feature ID list...")
            self.is_field_expression = None
            features_list = self.task_parameters["task"]["features"]
            logger.info(f"   → features_list count: {len(features_list) if features_list else 0}")
            
            if features_list:
                self.expression = self._build_feature_id_expression(features_list)
                logger.info(f"   → built expression from features: '{self.expression}'")
                
                if self.expression:
                    result = self._apply_filter_and_update_subset(self.expression)
                    logger.info(f"   → fallback filter applied result: {result}")
            else:
                logger.warning(f"   ⚠️ No features in list - cannot apply filter!")
        
        logger.info(f"🔧 execute_source_layer_filtering RESULT: {result}")
        return result
    
    def _initialize_source_subset_and_buffer(self):
        """
        Initialize source subset expression and buffer parameters.
        
        Sets param_source_new_subset based on expression type and
        extracts buffer value/expression from task parameters.
        
        CRITICAL MODE FIELD-BASED:
        - Quand is_field_expression est activé (Custom Selection avec champ simple),
          on PRESERVE TOUJOURS le subset existant de la couche source
        - Le subset existant sera utilisé pour déterminer quelles géométries
          sources utiliser pour l'intersection géométrique avec les couches distantes
        - La couche source elle-même ne sera PAS modifiée
        
        Exemple:
          Source avec subset "homecount > 5" (100 features)
          + Custom selection "drop_ID" (champ)
          + Prédicats géom vers distant
          → Source garde "homecount > 5"
          → Distant filtré par intersection avec ces 100 features
        """
        logger.info("🔧 _initialize_source_subset_and_buffer() START")
        
        # Check if we're in field-based geometric filter mode
        # In this mode, is_field_expression = (True, field_name) and expression = old_subset
        is_field_based_mode = (
            hasattr(self, 'is_field_expression') and 
            self.is_field_expression is not None and
            isinstance(self.is_field_expression, tuple) and
            len(self.is_field_expression) >= 2 and
            self.is_field_expression[0] is True
        )
        
        if is_field_based_mode:
            # CRITICAL: In field-based mode, ALWAYS keep existing subset
            # The source layer stays filtered by its current subset (or no filter)
            # Only distant layers get filtered by geometric intersection
            field_name = self.is_field_expression[1]
            
            logger.info(f"  🔄 FIELD-BASED MODE: Preserving source layer filter")
            logger.info(f"  → Field name: '{field_name}'")
            logger.info(f"  → Source layer keeps its current state (subset preserved)")
            
            # ALWAYS use existing subset - do NOT build from selected features
            self.param_source_new_subset = self.param_source_old_subset
            
            if self.param_source_old_subset:
                logger.info(f"  ✓ Existing subset preserved: '{self.param_source_old_subset[:80]}...'")
                logger.info(f"  ✓ Source geometries from filtered layer will be used for intersection")
            else:
                logger.info(f"  ℹ No existing subset - all features from source layer will be used")
        else:
            # Standard mode: Set source subset based on expression type
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
            
            logger.info(f"  buffer_value_property (override active): {buffer_property}")
            logger.info(f"  buffer_value_expression: '{buffer_expr}'")
            logger.info(f"  buffer_value (spinbox): {buffer_val}")
            
            # CRITICAL: Check buffer_value_expression FIRST
            # When mPropertyOverrideButton_filtering_buffer_value_property is active with valid expression,
            # it takes precedence over the spinbox value
            if buffer_expr != '' and buffer_expr is not None:
                # Try to convert to float - if successful, it's a static value
                try:
                    numeric_value = float(buffer_expr)
                    self.param_buffer_value = numeric_value
                    logger.info(f"  ✓ Buffer from property override (numeric): {self.param_buffer_value}m")
                    logger.info(f"  ℹ️  Expression '{buffer_expr}' converted to static value")
                except (ValueError, TypeError):
                    # It's a real dynamic expression (e.g., field reference or complex expression)
                    self.param_buffer_expression = buffer_expr
                    logger.info(f"  ✓ Buffer from property override (DYNAMIC EXPRESSION): {self.param_buffer_expression}")
                    logger.info(f"  ℹ️  Will evaluate expression per feature (e.g., field reference)")
                    if buffer_property:
                        logger.info(f"  ✓ Property override button confirmed ACTIVE")
                    else:
                        logger.warning(f"  ⚠️  Expression found but buffer_value_property=False (UI state mismatch?)")
            elif buffer_val is not None and buffer_val != 0:
                # Fallback to buffer_value from spinbox
                self.param_buffer_value = buffer_val
                logger.info(f"  ✓ Buffer from spinbox VALUE: {self.param_buffer_value}m")
            else:
                # No valid buffer specified
                self.param_buffer_value = 0
                logger.warning(f"  ⚠️  No valid buffer value found, defaulting to 0m")
        else:
            # CRITICAL FIX: Reset buffer parameters when no buffer is configured
            # This prevents using buffer values from previous filtering operations
            old_buffer = getattr(self, 'param_buffer_value', None)
            old_expr = getattr(self, 'param_buffer_expression', None)
            
            self.param_buffer_value = 0
            self.param_buffer_expression = None
            
            logger.info(f"  ℹ️  NO BUFFER configured (has_buffer_value=False)")
            if old_buffer is not None and old_buffer != 0:
                logger.info(f"  ✓ Reset buffer_value: {old_buffer}m → 0m")
            if old_expr is not None:
                logger.info(f"  ✓ Reset buffer_expression: '{old_expr}' → None")
            if old_buffer is None or old_buffer == 0:
                logger.info(f"  ✓ Buffer already at 0m (no reset needed)")
        
        logger.info("✓ _initialize_source_subset_and_buffer() END")

    def _prepare_geometries_by_provider(self, provider_list):
        """
        Prepare source geometries for each provider type.
        
        Args:
            provider_list: List of unique provider types to prepare
            
        Returns:
            bool: True if all required geometries prepared successfully
        """
        # Check if we need WKT for PostgreSQL simplified mode (few source features)
        source_feature_count = self.source_layer.featureCount()
        postgresql_needs_wkt = (
            'postgresql' in provider_list and 
            POSTGRESQL_AVAILABLE and
            source_feature_count <= 50  # SIMPLE_WKT_THRESHOLD from PostgreSQL backend
        )
        
        if postgresql_needs_wkt:
            logger.info(f"PostgreSQL simplified mode: {source_feature_count} features ≤ 50")
            logger.info("  → Will prepare WKT geometry for direct ST_GeomFromText()")
        
        # Check if any OGR layer needs Spatialite geometry
        ogr_needs_spatialite_geom = False
        if 'ogr' in provider_list and hasattr(self, 'layers') and 'ogr' in self.layers:
            spatialite_backend = SpatialiteGeometricFilter(self.task_parameters)
            for layer, layer_props in self.layers['ogr']:
                if spatialite_backend.supports_layer(layer):
                    ogr_needs_spatialite_geom = True
                    logger.info(f"  OGR layer '{layer.name()}' will use Spatialite backend - need WKT geometry")
                    break
        
        # Prepare PostgreSQL source geometry
        # CRITICAL FIX: Check BOTH source layer AND distant layers for PostgreSQL
        # If source layer is PostgreSQL with connection, we MUST prepare postgresql_source_geom
        # for EXISTS subqueries to work correctly
        has_postgresql_fallback_layers = False  # Track if any PostgreSQL layer uses OGR fallback
        
        if 'postgresql' in provider_list and POSTGRESQL_AVAILABLE:
            # Check if SOURCE layer is PostgreSQL with connection
            source_is_postgresql_with_connection = (
                self.param_source_provider_type == PROVIDER_POSTGRES and
                self.task_parameters.get("infos", {}).get("postgresql_connection_available", False)
            )
            
            # Check if any DISTANT PostgreSQL layer has connection available
            has_distant_postgresql_with_connection = False
            if hasattr(self, 'layers') and 'postgresql' in self.layers:
                for layer, layer_props in self.layers['postgresql']:
                    if layer_props.get('postgresql_connection_available', False):
                        has_distant_postgresql_with_connection = True
                    # CRITICAL FIX: Check if this layer uses OGR fallback
                    if layer_props.get('_postgresql_fallback', False):
                        has_postgresql_fallback_layers = True
                        logger.info(f"  → Layer '{layer.name()}' is PostgreSQL with OGR fallback")
            
            if source_is_postgresql_with_connection or has_distant_postgresql_with_connection:
                logger.info("Preparing PostgreSQL source geometry...")
                if source_is_postgresql_with_connection:
                    logger.info("  → Source layer is PostgreSQL with connection")
                if has_distant_postgresql_with_connection:
                    logger.info("  → Distant PostgreSQL layers with connection found")
                self.prepare_postgresql_source_geom()
            else:
                logger.warning("PostgreSQL in provider list but no layers have connection - will use OGR fallback")
                # Ensure OGR geometry is prepared for PostgreSQL fallback
                if 'ogr' not in provider_list:
                    logger.info("Adding OGR to provider list for PostgreSQL fallback...")
                    provider_list.append('ogr')
        
        # CRITICAL FIX: If any PostgreSQL layer uses OGR fallback, we MUST prepare ogr_source_geom
        # This happens when source layer has PostgreSQL connection but distant layers don't
        if has_postgresql_fallback_layers and 'ogr' not in provider_list:
            logger.info("PostgreSQL fallback layers detected - adding OGR to provider list")
            provider_list.append('ogr')
        
        # Prepare Spatialite source geometry (WKT string) with fallback to OGR
        # Also needed for PostgreSQL simplified mode (few source features)
        # CRITICAL FIX: Also prepare for OGR layers that will use Spatialite backend (GeoPackage/SQLite)
        if 'spatialite' in provider_list or postgresql_needs_wkt or ogr_needs_spatialite_geom:
            logger.info("Preparing Spatialite source geometry...")
            logger.info(f"  → Reason: spatialite={'spatialite' in provider_list}, "
                       f"postgresql_wkt={postgresql_needs_wkt}, ogr_spatialite={ogr_needs_spatialite_geom}")
            logger.info(f"  → Features in task: {len(self.task_parameters['task'].get('features', []))}")
            
            spatialite_success = False
            try:
                self.prepare_spatialite_source_geom()
                if hasattr(self, 'spatialite_source_geom') and self.spatialite_source_geom is not None:
                    spatialite_success = True
                    wkt_preview = self.spatialite_source_geom[:150] if len(self.spatialite_source_geom) > 150 else self.spatialite_source_geom
                    logger.info(f"✓ Spatialite source geometry prepared: {len(self.spatialite_source_geom)} chars")
                    logger.info(f"  → WKT preview: {wkt_preview}...")
                else:
                    logger.warning("Spatialite geometry preparation returned None")
            except Exception as e:
                logger.warning(f"Spatialite geometry preparation failed: {e}")
                import traceback
                logger.debug(f"Traceback: {traceback.format_exc()}")
            
            # Fallback to OGR if Spatialite failed
            if not spatialite_success:
                logger.info("Falling back to OGR geometry preparation...")
                # Set flag to prevent buffer application in OGR fallback
                # Buffer will be applied via ST_Buffer() in SQL when we convert to WKT
                self._spatialite_fallback_mode = True
                try:
                    self.prepare_ogr_source_geom()
                    if hasattr(self, 'ogr_source_geom') and self.ogr_source_geom is not None:
                        # CRITICAL FIX: Convert OGR layer geometry to WKT for Spatialite
                        # ogr_source_geom is a QgsVectorLayer, spatialite_source_geom expects WKT string
                        if isinstance(self.ogr_source_geom, QgsVectorLayer):
                            # Extract geometries from the layer and convert to WKT
                            all_geoms = []
                            for feature in self.ogr_source_geom.getFeatures():
                                geom = feature.geometry()
                                if geom and not geom.isEmpty():
                                    all_geoms.append(geom)
                            
                            if all_geoms:
                                # Combine all geometries and convert to WKT
                                combined = QgsGeometry.collectGeometry(all_geoms)
                                
                                # CRITICAL FIX: Prevent GeometryCollection from causing issues
                                # Same protection as in prepare_spatialite_source_geom
                                combined_type = QgsWkbTypes.displayString(combined.wkbType())
                                if 'GeometryCollection' in combined_type:
                                    logger.warning(f"OGR fallback: collectGeometry produced {combined_type} - converting")
                                    
                                    # Determine dominant geometry type
                                    has_polygons = any('Polygon' in QgsWkbTypes.displayString(g.wkbType()) for g in all_geoms)
                                    has_lines = any('Line' in QgsWkbTypes.displayString(g.wkbType()) for g in all_geoms)
                                    has_points = any('Point' in QgsWkbTypes.displayString(g.wkbType()) for g in all_geoms)
                                    
                                    if has_polygons:
                                        converted = combined.convertToType(QgsWkbTypes.PolygonGeometry, True)
                                    elif has_lines:
                                        converted = combined.convertToType(QgsWkbTypes.LineGeometry, True)
                                    elif has_points:
                                        converted = combined.convertToType(QgsWkbTypes.PointGeometry, True)
                                    else:
                                        converted = None
                                    
                                    if converted and not converted.isEmpty():
                                        combined = converted
                                        logger.info(f"OGR fallback: Converted to {QgsWkbTypes.displayString(combined.wkbType())}")
                                    else:
                                        logger.warning("OGR fallback: Conversion failed, keeping GeometryCollection")
                                
                                wkt = combined.asWkt()
                                # Escape single quotes for SQL
                                self.spatialite_source_geom = wkt.replace("'", "''")
                                logger.info(f"✓ Converted OGR layer to WKT ({len(self.spatialite_source_geom)} chars)")
                            else:
                                logger.warning("OGR layer has no valid geometries for Spatialite fallback")
                                self.spatialite_source_geom = None
                        else:
                            # If it's already a string (WKT), use it directly
                            self.spatialite_source_geom = self.ogr_source_geom
                            logger.info("✓ Successfully used OGR geometry as fallback")
                    else:
                        logger.error("OGR fallback also failed - no geometry available")
                        self.message = "Failed to prepare source geometry: OGR fallback also failed - no geometry available"
                        return False
                except Exception as e2:
                    logger.error(f"OGR fallback failed: {e2}")
                    self.message = f"Failed to prepare source geometry: OGR fallback failed - {e2}"
                    return False
                finally:
                    # Reset fallback flag
                    self._spatialite_fallback_mode = False

        # Prepare OGR geometry if needed for OGR layers, buffer expressions, OR PostgreSQL layers
        # CRITICAL: Always prepare OGR geometry for PostgreSQL because BackendFactory may
        # fall back to OGR at runtime if PostgreSQL connection fails or for small datasets
        # ALSO: Prepare for Spatialite layers because Spatialite backend may fall back to OGR
        # if Spatialite functions are not available (e.g., GDAL without Spatialite support)
        needs_ogr_geom = (
            'ogr' in provider_list or 
            'spatialite' in provider_list or  # Spatialite may fall back to OGR
            self.param_buffer_expression != '' or
            'postgresql' in provider_list  # PostgreSQL may use OGR fallback at runtime
        )
        if needs_ogr_geom:
            logger.info("Preparing OGR/Spatialite source geometry...")
            self.prepare_ogr_source_geom()

        return True

    def _filter_all_layers_with_progress(self):
        """
        Iterate through all layers and apply filtering with progress tracking.
        
        Supports parallel execution when enabled in configuration.
        Updates task description to show current layer being processed.
        Progress is visible in QGIS task manager panel.
        
        Returns:
            bool: True if all layers processed (some may fail), False if canceled
        """
        # DIAGNOSTIC: Log all layers that will be filtered
        logger.info("=" * 70)
        logger.info("📋 LISTE DES COUCHES À FILTRER GÉOMÉTRIQUEMENT")
        logger.info("=" * 70)
        total_layers = 0
        for provider_type in self.layers:
            layer_list = self.layers[provider_type]
            logger.info(f"  Provider: {provider_type} → {len(layer_list)} couche(s)")
            for idx, (layer, layer_props) in enumerate(layer_list, 1):
                logger.info(f"    {idx}. {layer.name()} (id={layer.id()[:8]}...)")
            total_layers += len(layer_list)
        logger.info(f"  TOTAL: {total_layers} couches à filtrer")
        logger.info("=" * 70)
        
        # Check if parallel filtering is enabled
        parallel_config = self.task_parameters.get('config', {}).get('APP', {}).get('OPTIONS', {}).get('PARALLEL_FILTERING', {})
        parallel_enabled = parallel_config.get('enabled', {}).get('value', True)
        min_layers_for_parallel = parallel_config.get('min_layers', {}).get('value', 2)
        max_workers = parallel_config.get('max_workers', {}).get('value', 0)
        
        # Use parallel execution if enabled and enough layers
        if parallel_enabled and total_layers >= min_layers_for_parallel:
            return self._filter_all_layers_parallel(max_workers)
        else:
            return self._filter_all_layers_sequential()
    
    def _filter_all_layers_parallel(self, max_workers: int = 0):
        """
        Filter all layers using parallel execution.
        
        Args:
            max_workers: Maximum worker threads (0 = auto-detect)
        
        Returns:
            bool: True if all layers processed successfully
        """
        logger.info("🚀 Using PARALLEL filtering mode")
        
        # Prepare flat list of (layer, layer_props) tuples with provider_type stored in layer_props
        all_layers = []
        for provider_type in self.layers:
            for layer, layer_props in self.layers[provider_type]:
                # Store provider_type in layer_props for the filter function
                layer_props_with_provider = layer_props.copy()
                layer_props_with_provider['_effective_provider_type'] = provider_type
                all_layers.append((layer, layer_props_with_provider))
        
        # Create executor with config
        config = ParallelConfig(
            max_workers=max_workers if max_workers > 0 else None,
            min_layers_for_parallel=1  # Already checked threshold
        )
        executor = ParallelFilterExecutor(config.max_workers)
        
        # Execute parallel filtering with required task_parameters
        task_parameters = {
            'task': self,
            'filter_type': getattr(self, 'filter_type', 'geometric')
        }
        results = executor.filter_layers_parallel(
            all_layers, 
            self.execute_geometric_filtering,
            task_parameters
        )
        
        # Process results and update progress
        successful_filters = 0
        failed_filters = 0
        
        for i, (layer_tuple, result) in enumerate(zip(all_layers, results), 1):
            layer, layer_props = layer_tuple
            self.setDescription(f"Filtering layer {i}/{self.layers_count}: {layer.name()}")
            
            if result.success:
                successful_filters += 1
                logger.info(f"✅ {layer.name()} has been filtered → {layer.featureCount()} features")
            else:
                failed_filters += 1
                error_msg = result.error_message if hasattr(result, 'error_message') else getattr(result, 'error', 'Unknown error')
                logger.error(f"❌ {layer.name()} - errors occurred during filtering: {error_msg}")
            
            progress_percent = int((i / self.layers_count) * 100)
            self.setProgress(progress_percent)
            
            if self.isCanceled():
                logger.warning(f"⚠️ Filtering canceled at layer {i}/{self.layers_count}")
                return False
        
        # DIAGNOSTIC: Summary of filtering results
        self._log_filtering_summary(successful_filters, failed_filters)
        return True
    
    def _filter_all_layers_sequential(self):
        """
        Filter all layers sequentially (original behavior).
        
        Returns:
            bool: True if all layers processed successfully
        """
        logger.info("🔄 Using SEQUENTIAL filtering mode")
        
        i = 1
        successful_filters = 0
        failed_filters = 0
        
        for layer_provider_type in self.layers:
            for layer, layer_props in self.layers[layer_provider_type]:
                # STABILITY FIX v2.3.9: Validate layer before any operations
                # This prevents crashes when layer becomes invalid during sequential filtering
                try:
                    if not is_valid_layer(layer):
                        logger.warning(f"⚠️ Layer {i}/{self.layers_count} is invalid - skipping")
                        failed_filters += 1
                        i += 1
                        continue
                    
                    layer_name = layer.name()
                    layer_feature_count = layer.featureCount()
                except (RuntimeError, AttributeError) as access_error:
                    logger.error(f"❌ Layer {i}/{self.layers_count} access error (C++ object deleted): {access_error}")
                    failed_filters += 1
                    i += 1
                    continue
                
                # Update task description with current progress
                self.setDescription(f"Filtering layer {i}/{self.layers_count}: {layer_name}")
                
                logger.info("")
                logger.info(f"🔄 FILTRAGE {i}/{self.layers_count}: {layer_name} ({layer_provider_type})")
                logger.info(f"   Features avant filtre: {layer_feature_count}")
                
                result = self.execute_geometric_filtering(layer_provider_type, layer, layer_props)
                
                if result:
                    successful_filters += 1
                    try:
                        final_count = layer.featureCount()
                        logger.info(f"✅ {layer_name} has been filtered → {final_count} features")
                    except (RuntimeError, AttributeError):
                        logger.info(f"✅ {layer_name} has been filtered (count unavailable)")
                else:
                    failed_filters += 1
                    logger.error(f"❌ {layer_name} - errors occurred during filtering")
                
                i += 1
                progress_percent = int((i / self.layers_count) * 100)
                self.setProgress(progress_percent)
                
                if self.isCanceled():
                    logger.warning(f"⚠️ Filtering canceled at layer {i}/{self.layers_count}")
                    return False
        
        # DIAGNOSTIC: Summary of filtering results
        self._log_filtering_summary(successful_filters, failed_filters)
        return True
    
    def _log_filtering_summary(self, successful_filters: int, failed_filters: int):
        """Log summary of filtering results."""
        logger.info("")
        logger.info("=" * 70)
        logger.info("📊 RÉSUMÉ DU FILTRAGE GÉOMÉTRIQUE")
        logger.info("=" * 70)
        logger.info(f"  Total couches: {self.layers_count}")
        logger.info(f"  ✅ Succès: {successful_filters}")
        logger.info(f"  ❌ Échecs: {failed_filters}")
        logger.info("=" * 70)

    def manage_distant_layers_geometric_filtering(self):
        """
        Filter layers from a prefiltered layer.
        
        MODE FIELD-BASED BEHAVIOR:
        - En mode field-based (Custom Selection avec champ simple),
          la couche source conserve son subset existant
        - Les géométries sources pour l'intersection proviennent de
          TOUTES les features VISIBLES de la couche source (respect du subset)
        - Seules les couches distantes reçoivent un nouveau filtre géométrique
        
        Orchestrates the complete workflow: initialize parameters, prepare geometries,
        and filter all layers with progress tracking.
        
        CRITICAL: Buffer parameters MUST be initialized BEFORE preparing geometries,
        otherwise buffer will not be applied to source geometries!
        
        Returns:
            bool: True if all layers processed successfully, False on error or cancellation
        """
        # Log source layer state for debugging
        logger.info("=" * 60)
        logger.info("🔍 manage_distant_layers_geometric_filtering() - SOURCE LAYER STATE")
        logger.info("=" * 60)
        logger.info(f"  Source layer name: {self.source_layer.name()}")
        logger.info(f"  Source layer subset: '{self.source_layer.subsetString()[:100] if self.source_layer.subsetString() else ''}'...")
        logger.info(f"  Source layer feature count: {self.source_layer.featureCount()}")
        logger.info(f"  is_field_expression: {getattr(self, 'is_field_expression', None)}")
        logger.info("=" * 60)
        
        # CRITICAL: Initialize source subset and buffer parameters FIRST
        # This sets self.param_buffer_value which is needed by prepare_*_source_geom()
        self._initialize_source_subset_and_buffer()
        
        # Build unique provider list including source layer provider
        provider_list = self.provider_list + [self.param_source_provider_type]
        provider_list = list(dict.fromkeys(provider_list))
        
        # Prepare geometries for all provider types
        # NOTE: This will use self.param_buffer_value set above
        if not self._prepare_geometries_by_provider(provider_list):
            # If self.message wasn't set by _prepare_geometries_by_provider, set a generic one
            if not hasattr(self, 'message') or not self.message:
                self.message = "Failed to prepare source geometries for distant layers filtering"
            logger.error(f"_prepare_geometries_by_provider failed: {self.message}")
            return False
        
        # Filter all layers with progress tracking
        result = self._filter_all_layers_with_progress()
        return result
    
    def qgis_expression_to_postgis(self, expression):
        """
        Convert QGIS expression to PostGIS SQL.
        
        Enhanced conversion with:
        - Spatial function mapping ($area, $length, etc.)
        - Type casting for numeric/text operations
        - CASE WHEN support
        - Pattern matching operators
        
        Args:
            expression: QGIS expression string
        
        Returns:
            PostGIS SQL expression string
        """
        if not expression:
            return expression
        
        # 1. Convert QGIS spatial functions to PostGIS
        spatial_conversions = {
            '$area': 'ST_Area(geometry)',
            '$length': 'ST_Length(geometry)',
            '$perimeter': 'ST_Perimeter(geometry)',
            '$x': 'ST_X(geometry)',
            '$y': 'ST_Y(geometry)',
            '$geometry': 'geometry',
            'buffer': 'ST_Buffer',
            'area': 'ST_Area',
            'length': 'ST_Length',
            'perimeter': 'ST_Perimeter',
        }
        
        for qgis_func, postgis_func in spatial_conversions.items():
            expression = expression.replace(qgis_func, postgis_func)
        
        # 2. Convert IF statements to CASE WHEN
        if expression.find('if') >= 0:
            expression = re.sub(r'if\((.*,.*,.*)\))', r'(if(.* then .* else .*))', expression)
            logger.debug(f"Expression after IF conversion: {expression}")

        # 3. Add type casting for numeric operations
        expression = expression.replace('" >', '"::numeric >').replace('">', '"::numeric >')
        expression = expression.replace('" <', '"::numeric <').replace('"<', '"::numeric <')
        expression = expression.replace('" +', '"::numeric +').replace('"+', '"::numeric +')
        expression = expression.replace('" -', '"::numeric -').replace('"-', '"::numeric -')

        # 4. Normalize SQL keywords (case-insensitive replacements)
        expression = re.sub(r'\bcase\b', ' CASE ', expression, flags=re.IGNORECASE)
        expression = re.sub(r'\bwhen\b', ' WHEN ', expression, flags=re.IGNORECASE)
        expression = re.sub(r'\bis\b', ' IS ', expression, flags=re.IGNORECASE)
        expression = re.sub(r'\bthen\b', ' THEN ', expression, flags=re.IGNORECASE)
        expression = re.sub(r'\belse\b', ' ELSE ', expression, flags=re.IGNORECASE)
        expression = re.sub(r'\bilike\b', ' ILIKE ', expression, flags=re.IGNORECASE)
        expression = re.sub(r'\blike\b', ' LIKE ', expression, flags=re.IGNORECASE)
        expression = re.sub(r'\bnot\b', ' NOT ', expression, flags=re.IGNORECASE)

        # 5. Add type casting for text operations
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
        source_schema = self.param_source_schema
        
        # CRITICAL FIX: Include schema in geometry reference for PostgreSQL
        # Format: "schema"."table"."geom" to avoid "missing FROM-clause entry" errors
        self.postgresql_source_geom = '"{source_schema}"."{source_table}"."{source_geom}"'.format(
                                                                                source_schema=source_schema,
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
            # Use sanitize_sql_identifier to handle all special chars (em-dash, etc.)
            self.current_materialized_view_name = sanitize_sql_identifier(
                self.source_layer.id().replace(layer_name, '')
            )
                
            self.postgresql_source_geom = '"mv_{current_materialized_view_name}_dump"."{source_geom}"'.format(
                                                                                                        source_geom=self.param_source_geom,
                                                                                                        current_materialized_view_name=self.current_materialized_view_name
                                                                                                        )
            
        


        elif self.param_buffer_value is not None and self.param_buffer_value != 0:

            self.param_buffer = self.param_buffer_value
            
            # CRITICAL FIX: For simple numeric buffer values, apply buffer directly in SQL
            # Don't create materialized views - just wrap geometry in ST_Buffer()
            # This is simpler and more efficient than creating a _dump view
            source_table = self.param_source_table
            source_schema = self.param_source_schema
            self.postgresql_source_geom = 'ST_Buffer("{source_schema}"."{source_table}"."{source_geom}", {buffer_value})'.format(
                source_schema=source_schema,
                source_table=source_table,
                source_geom=self.param_source_geom,
                buffer_value=self.param_buffer_value
            )
            logger.debug(f"Using simple buffer: ST_Buffer with {self.param_buffer_value}m")     

        

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
        # CRITICAL FIX: Respect active subset filter on source layer
        # When source layer has a subsetString (e.g., "homecount > 5"), we must use ONLY filtered features
        # for geometric operations, not all features in the layer.
        has_subset = bool(self.source_layer.subsetString())
        has_selection = self.source_layer.selectedFeatureCount() > 0
        
        # Check if we're in field-based mode (Custom Selection with a simple field name)
        is_field_based_mode = (
            hasattr(self, 'is_field_expression') and 
            self.is_field_expression is not None and
            isinstance(self.is_field_expression, tuple) and
            len(self.is_field_expression) >= 2 and
            self.is_field_expression[0] is True
        )
        
        logger.info(f"=== prepare_spatialite_source_geom DEBUG ===")
        logger.info(f"  has_subset: {has_subset}")
        logger.info(f"  has_selection: {has_selection}")
        logger.info(f"  is_field_based_mode: {is_field_based_mode}")
        if has_subset:
            logger.info(f"  Current subset: '{self.source_layer.subsetString()[:100]}'")
        
        if has_subset:
            # Source layer is filtered (e.g., from custom expression) - use getFeatures() which respects subsetString
            logger.info(f"=== prepare_spatialite_source_geom (FILTERED MODE) ===")
            logger.info(f"  Source layer has active filter: {self.source_layer.subsetString()[:100]}")
            logger.info(f"  Using {self.source_layer.featureCount()} filtered features from source layer")
            features = list(self.source_layer.getFeatures())
            logger.debug(f"  Retrieved {len(features)} features from getFeatures()")
        elif has_selection:
            # Multi-selection mode - use selected features
            logger.info(f"=== prepare_spatialite_source_geom (MULTI-SELECTION MODE) ===")
            logger.info(f"  Using {self.source_layer.selectedFeatureCount()} selected features from source layer")
            features = list(self.source_layer.selectedFeatures())
        elif is_field_based_mode:
            # FIELD-BASED MODE: Use ALL features from filtered source layer
            # The source layer keeps its current filter (subset string)
            # We use ALL filtered features for geometric intersection with distant layers
            logger.info(f"=== prepare_spatialite_source_geom (FIELD-BASED MODE) ===")
            logger.info(f"  Field name: '{self.is_field_expression[1]}'")
            logger.info(f"  Source subset: '{self.source_layer.subsetString()[:80] if self.source_layer.subsetString() else '(none)'}...'")
            logger.info(f"  Using ALL {self.source_layer.featureCount()} filtered features for geometric intersection")
            features = list(self.source_layer.getFeatures())
        else:
            # Get features from task parameters (single selection or expression mode)
            features = self.task_parameters["task"]["features"]
            logger.debug(f"=== prepare_spatialite_source_geom START ===")
            logger.debug(f"  Features: {len(features)} features")
        
        # FALLBACK: If features list is empty, use all visible features from source layer
        if not features or len(features) == 0:
            logger.warning(f"  ⚠️ No features provided! Falling back to source layer's visible features")
            features = list(self.source_layer.getFeatures())
            logger.info(f"  → Fallback: Using {len(features)} features from source layer")
        
        logger.debug(f"  Buffer value: {self.param_buffer_value}")
        logger.debug(f"  Target CRS: {self.source_layer_crs_authid}")
        logger.debug(f"prepare_spatialite_source_geom: Processing {len(features)} features")
        
        # Get current subset string for cache key (critical for field-based mode)
        current_subset = self.source_layer.subsetString() or ''
        layer_id = self.source_layer.id()
        
        # Check cache first (includes layer_id and subset_string to avoid stale cache)
        cached_geom = self.geom_cache.get(
            features, 
            self.param_buffer_value,
            self.source_layer_crs_authid,
            layer_id=layer_id,
            subset_string=current_subset
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

        # Determine target CRS
        target_crs = QgsCoordinateReferenceSystem(self.source_layer_crs_authid)
        
        # Setup reprojection transforms (only if explicitly requested)
        # SPATIALITE OPTIMIZATION: Buffer is now applied via ST_Buffer() in SQL expression
        # No need to reproject to metric CRS here - ST_Buffer handles it with ST_Transform
        if self.has_to_reproject_source_layer is True:
            source_crs_obj = QgsCoordinateReferenceSystem(self.source_crs.authid())
            transform = QgsCoordinateTransform(source_crs_obj, target_crs, self.PROJECT)
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
                    
                if self.has_to_reproject_source_layer is True:
                    geom_copy.transform(transform)
                    
                # SPATIALITE OPTIMIZATION: Buffer is now applied via ST_Buffer() in SQL expression
                # This avoids GeometryCollection issues from QGIS buffer and uses native Spatialite functions
                # The buffer value is passed to build_expression() which adds ST_Buffer() to the SQL
                if self.param_buffer_value is not None and self.param_buffer_value > 0:
                    logger.info(f"Buffer of {self.param_buffer_value}m will be applied via ST_Buffer() in SQL")
                    # NOTE: Do NOT apply buffer here - it's done in Spatialite SQL expression
                    
                geometries.append(geom_copy)

        if len(geometries) == 0:
            logger.error("prepare_spatialite_source_geom: No valid geometries after processing")
            self.spatialite_source_geom = None
            return

        # STABILITY FIX v2.3.9: Use safe_collect_geometry wrapper
        # This prevents access violations on certain machines
        collected_geometry = safe_collect_geometry(geometries)
        
        if collected_geometry is None:
            logger.error("prepare_spatialite_source_geom: safe_collect_geometry returned None")
            self.spatialite_source_geom = None
            return
        
        # CRITICAL FIX: Prevent GeometryCollection from causing issues with typed layers
        # GeoPackage and other backends require homogeneous geometry types
        collected_type = get_geometry_type_name(collected_geometry)
        logger.debug(f"Initial collected geometry type: {collected_type}")
        
        if 'GeometryCollection' in collected_type:
            logger.warning(f"collectGeometry produced {collected_type} - converting to homogeneous type")
            
            # Determine the dominant geometry type from input geometries using safe wrapper
            has_polygons = any('Polygon' in get_geometry_type_name(g) for g in geometries if validate_geometry(g))
            has_lines = any('Line' in get_geometry_type_name(g) for g in geometries if validate_geometry(g))
            has_points = any('Point' in get_geometry_type_name(g) for g in geometries if validate_geometry(g))
            
            logger.debug(f"Geometry analysis - Polygons: {has_polygons}, Lines: {has_lines}, Points: {has_points}")
            
            # Priority: Polygon > Line > Point (spatial filtering typically uses areas/zones)
            if has_polygons:
                # STABILITY FIX: Use safe wrapper for extraction
                polygon_parts = extract_polygons_from_collection(collected_geometry)
                
                if polygon_parts:
                    collected_geometry = safe_collect_geometry(polygon_parts)
                    if collected_geometry is None:
                        logger.error("Failed to collect polygon parts")
                    # Force conversion to MultiPolygon if still GeometryCollection
                    elif 'GeometryCollection' in get_geometry_type_name(collected_geometry):
                        converted = collected_geometry.convertToType(QgsWkbTypes.PolygonGeometry, True)
                        if converted and not converted.isEmpty():
                            collected_geometry = converted
                            logger.info(f"Converted to {get_geometry_type_name(collected_geometry)}")
                        else:
                            logger.error("Polygon conversion failed - keeping original")
                    else:
                        logger.info(f"Successfully converted to {get_geometry_type_name(collected_geometry)}")
                else:
                    logger.warning("No polygon parts found in GeometryCollection")
                    
            elif has_lines:
                # Extract and collect only line parts using safe wrapper
                line_parts = []
                for part in safe_as_geometry_collection(collected_geometry):
                    part_type = get_geometry_type_name(part)
                    if 'Line' in part_type:
                        if 'Multi' in part_type:
                            for sub_part in safe_as_geometry_collection(part):
                                line_parts.append(sub_part)
                        else:
                            line_parts.append(part)
                
                if line_parts:
                    collected_geometry = safe_collect_geometry(line_parts)
                    if collected_geometry and 'GeometryCollection' in get_geometry_type_name(collected_geometry):
                        converted = collected_geometry.convertToType(QgsWkbTypes.LineGeometry, True)
                        if converted and not converted.isEmpty():
                            collected_geometry = converted
                            logger.info(f"Converted to {get_geometry_type_name(collected_geometry)}")
                        else:
                            logger.error("Line conversion failed - keeping original")
                    else:
                        logger.info(f"Successfully converted to {get_geometry_type_name(collected_geometry)}")
                else:
                    logger.warning("No line parts found in GeometryCollection")
                    
            elif has_points:
                # Extract and collect only point parts using safe wrapper
                point_parts = []
                for part in safe_as_geometry_collection(collected_geometry):
                    part_type = get_geometry_type_name(part)
                    if 'Point' in part_type:
                        if 'Multi' in part_type:
                            for sub_part in safe_as_geometry_collection(part):
                                point_parts.append(sub_part)
                        else:
                            point_parts.append(part)
                
                if point_parts:
                    collected_geometry = safe_collect_geometry(point_parts)
                    if collected_geometry and 'GeometryCollection' in get_geometry_type_name(collected_geometry):
                        converted = collected_geometry.convertToType(QgsWkbTypes.PointGeometry, True)
                        if converted and not converted.isEmpty():
                            collected_geometry = converted
                            logger.info(f"Converted to {get_geometry_type_name(collected_geometry)}")
                        else:
                            logger.error("Point conversion failed - keeping original")
                    else:
                        logger.info(f"Successfully converted to {get_geometry_type_name(collected_geometry)}")
                else:
                    logger.warning("No point parts found in GeometryCollection")
        
        wkt = collected_geometry.asWkt()
        
        # Log the final geometry type
        geom_type = wkt.split('(')[0].strip() if '(' in wkt else 'Unknown'
        logger.info(f"  Final collected geometry type: {geom_type}")
        logger.info(f"  Number of geometries collected: {len(geometries)}")
        
        # Escape single quotes for SQL
        wkt_escaped = wkt.replace("'", "''")
        self.spatialite_source_geom = wkt_escaped

        logger.info(f"  WKT length: {len(self.spatialite_source_geom)} chars")
        logger.debug(f"prepare_spatialite_source_geom WKT preview: {self.spatialite_source_geom[:200]}...")
        logger.info(f"=== prepare_spatialite_source_geom END ===") 
        
        # Store in cache for future use (includes layer_id and subset_string)
        self.geom_cache.put(
            features,
            self.param_buffer_value,
            self.source_layer_crs_authid,
            {'wkt': wkt_escaped},
            layer_id=layer_id,
            subset_string=current_subset
        )
        logger.info("✓ Source geometry computed and CACHED") 

    def _copy_filtered_layer_to_memory(self, layer, layer_name="filtered_copy"):
        """
        Copy filtered layer (with subset string) to memory layer.
        
        STABILITY FIX v2.3.9: Added geometry validation AND repair during copy to prevent
        access violations when processing corrupted geometries from virtual layers.
        
        This is crucial for OGR layers with subset strings, as some QGIS
        algorithms don't handle subset strings correctly.
        
        Args:
            layer: Source layer (may have subset string active)
            layer_name: Name for memory layer
            
        Returns:
            QgsVectorLayer: Memory layer with only filtered features and valid geometries
        """
        # Check if layer has active filter
        subset_string = layer.subsetString()
        feature_count = layer.featureCount()
        
        logger.debug(f"_copy_filtered_layer_to_memory: {layer.name()}, features={feature_count}, "
                    f"subset='{subset_string[:50] if subset_string else 'None'}', provider={layer.providerType()}")
        
        # If no filter and reasonable feature count, return original
        # EXCEPTION: Always copy virtual layers to memory - they may have unstable geometries
        is_virtual_layer = layer.providerType() == 'virtual'
        if not subset_string and feature_count < 10000 and not is_virtual_layer:
            logger.debug("  → No subset string, returning original layer")
            return layer
        
        if is_virtual_layer:
            logger.debug("  → Virtual layer detected, copying to memory for stability")
        
        # Create memory layer with same structure
        geom_type = QgsWkbTypes.displayString(layer.wkbType())
        crs = layer.crs().authid()
        memory_layer = QgsVectorLayer(f"{geom_type}?crs={crs}", layer_name, "memory")
        
        # Copy fields
        memory_layer.dataProvider().addAttributes(layer.fields())
        memory_layer.updateFields()
        
        # STABILITY FIX v2.3.9: Validate AND REPAIR geometries during copy
        # Virtual layers and some OGR sources may have corrupted geometries
        # that pass validation but crash GEOS
        features_to_copy = []
        skipped_invalid = 0
        repaired_count = 0
        
        for feature in layer.getFeatures():
            geom = feature.geometry()
            
            # CRITICAL: First check if geometry exists
            if geom is None or geom.isNull() or geom.isEmpty():
                skipped_invalid += 1
                continue
            
            # STABILITY FIX: Try to repair ALL geometries with makeValid()
            try:
                repaired_geom = geom.makeValid()
                if repaired_geom and not repaired_geom.isNull() and not repaired_geom.isEmpty():
                    new_feature = QgsFeature(feature)
                    new_feature.setGeometry(repaired_geom)
                    features_to_copy.append(new_feature)
                    if geom.wkbType() != repaired_geom.wkbType():
                        repaired_count += 1
                elif validate_geometry(geom):
                    new_feature = QgsFeature(feature)
                    features_to_copy.append(new_feature)
                else:
                    skipped_invalid += 1
            except Exception as e:
                logger.debug(f"  Exception repairing feature {feature.id()}: {e}")
                skipped_invalid += 1
        
        if repaired_count > 0:
            logger.info(f"  🔧 Repaired {repaired_count} geometries during copy")
        if skipped_invalid > 0:
            logger.warning(f"  ⚠️ Skipped {skipped_invalid} features with invalid geometries")
        
        if not features_to_copy:
            logger.warning(f"  ⚠️ No valid features to copy from {layer.name()}")
            return memory_layer
        
        memory_layer.dataProvider().addFeatures(features_to_copy)
        memory_layer.updateExtents()
        
        logger.debug(f"  ✓ Copied {len(features_to_copy)} features to memory layer (skipped {skipped_invalid} invalid, repaired {repaired_count})")
        
        # Create spatial index for improved performance
        self._verify_and_create_spatial_index(memory_layer, layer_name)
        
        return memory_layer

    def _copy_selected_features_to_memory(self, layer, layer_name="selected_copy"):
        """
        Copy only selected features from layer to memory layer.
        
        STABILITY FIX v2.3.9: Added geometry validation AND repair during copy to prevent
        access violations when processing corrupted geometries from virtual layers.
        
        This method extracts only the currently selected features from the source
        layer and copies them to a new memory layer. Essential for multi-selection
        mode where only selected features should be used for spatial operations.
        
        Args:
            layer: Source layer with selected features
            layer_name: Name for the memory layer
            
        Returns:
            QgsVectorLayer: Memory layer containing only selected features with valid geometries
        """
        selected_count = layer.selectedFeatureCount()
        logger.debug(f"_copy_selected_features_to_memory: {layer.name()}, "
                    f"selected={selected_count}, provider={layer.providerType()}")
        
        if selected_count == 0:
            logger.warning(f"  ⚠️ No features selected in {layer.name()}")
            # Return empty memory layer with same structure
            geom_type = QgsWkbTypes.displayString(layer.wkbType())
            crs = layer.crs().authid()
            empty_layer = QgsVectorLayer(f"{geom_type}?crs={crs}", layer_name, "memory")
            empty_layer.dataProvider().addAttributes(layer.fields())
            empty_layer.updateFields()
            return empty_layer
        
        # Create memory layer with same structure
        geom_type = QgsWkbTypes.displayString(layer.wkbType())
        crs = layer.crs().authid()
        memory_layer = QgsVectorLayer(f"{geom_type}?crs={crs}", layer_name, "memory")
        
        # Copy fields
        memory_layer.dataProvider().addAttributes(layer.fields())
        memory_layer.updateFields()
        
        # STABILITY FIX v2.3.9: Validate AND REPAIR geometries during copy
        # Virtual layers and some OGR sources may have corrupted geometries
        # that pass validation but crash GEOS
        features_to_copy = []
        skipped_invalid = 0
        repaired_count = 0
        
        for feature in layer.selectedFeatures():
            geom = feature.geometry()
            
            # CRITICAL: First check if geometry exists
            if geom is None or geom.isNull() or geom.isEmpty():
                skipped_invalid += 1
                logger.debug(f"  Skipped feature {feature.id()} with null/empty geometry")
                continue
            
            # STABILITY FIX: Try to repair ALL geometries with makeValid()
            # This prevents crashes even on geometries that "look" valid
            try:
                repaired_geom = geom.makeValid()
                if repaired_geom and not repaired_geom.isNull() and not repaired_geom.isEmpty():
                    # Use repaired geometry
                    new_feature = QgsFeature(feature)
                    new_feature.setGeometry(repaired_geom)
                    features_to_copy.append(new_feature)
                    if geom.wkbType() != repaired_geom.wkbType():
                        repaired_count += 1
                elif validate_geometry(geom):
                    # Fallback to original if makeValid failed but geometry seems OK
                    new_feature = QgsFeature(feature)
                    features_to_copy.append(new_feature)
                else:
                    skipped_invalid += 1
                    logger.debug(f"  Skipped feature {feature.id()} - makeValid failed and geometry invalid")
            except Exception as e:
                logger.warning(f"  Exception repairing feature {feature.id()}: {e}")
                skipped_invalid += 1
        
        if repaired_count > 0:
            logger.info(f"  🔧 Repaired {repaired_count} geometries during copy")
        if skipped_invalid > 0:
            logger.warning(f"  ⚠️ Skipped {skipped_invalid} features with invalid geometries")
        
        if features_to_copy:
            memory_layer.dataProvider().addFeatures(features_to_copy)
            memory_layer.updateExtents()
            
            # Create spatial index for improved performance
            self._verify_and_create_spatial_index(memory_layer, layer_name)
        else:
            logger.warning(f"  ⚠️ No valid features to copy from selection (all {selected_count} had invalid geometries)")
        
        logger.debug(f"  ✓ Copied {len(features_to_copy)} selected features to memory layer (skipped {skipped_invalid} invalid)")
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
        
        # CRITICAL FIX: Convert GeometryCollection to MultiPolygon
        # This prevents "Impossible d'ajouter l'objet avec une géométrie de type 
        # GeometryCollection à une couche de type MultiPolygon" errors when using
        # the buffer result for spatial operations on typed GPKG layers
        layer = self._convert_geometry_collection_to_multipolygon(layer)
        
        # Create spatial index
        processing.run('qgis:createspatialindex', {"INPUT": layer})
        
        return layer

    def _convert_geometry_collection_to_multipolygon(self, layer):
        """
        Convert GeometryCollection geometries in a layer to MultiPolygon.
        
        STABILITY FIX v2.3.9: Uses geometry_safety module to prevent
        access violations when handling GeometryCollections.
        
        CRITICAL FIX for GeoPackage/OGR layers:
        When qgis:buffer processes features with DISSOLVE=True, the result
        can contain GeometryCollection type instead of MultiPolygon.
        This causes errors when the buffer layer is used for spatial operations
        on typed layers (e.g., GeoPackage MultiPolygon layers).
        
        Error fixed: "Impossible d'ajouter l'objet avec une géométrie de type 
        GeometryCollection à une couche de type MultiPolygon"
        
        Args:
            layer: QgsVectorLayer from buffer operation
            
        Returns:
            QgsVectorLayer: Layer with geometries converted to MultiPolygon
        """
        try:
            # Check if any features have GeometryCollection type
            has_geometry_collection = False
            for feature in layer.getFeatures():
                geom = feature.geometry()
                if validate_geometry(geom):
                    geom_type = get_geometry_type_name(geom)
                    if 'GeometryCollection' in geom_type:
                        has_geometry_collection = True
                        break
            
            if not has_geometry_collection:
                logger.debug("No GeometryCollection found in buffer result - no conversion needed")
                return layer
            
            logger.info("🔄 GeometryCollection detected in buffer result - converting to MultiPolygon")
            
            # Create new memory layer with MultiPolygon type
            crs = layer.crs()
            fields = layer.fields()
            
            # Create MultiPolygon memory layer
            converted_layer = QgsMemoryProviderUtils.createMemoryLayer(
                f"{layer.name()}_converted",
                fields,
                QgsWkbTypes.MultiPolygon,
                crs
            )
            
            if not converted_layer or not converted_layer.isValid():
                logger.error("Failed to create converted memory layer")
                return layer
            
            converted_dp = converted_layer.dataProvider()
            converted_features = []
            conversion_count = 0
            
            for feature in layer.getFeatures():
                geom = feature.geometry()
                if not validate_geometry(geom):
                    continue
                
                geom_type = get_geometry_type_name(geom)
                new_geom = geom
                
                if 'GeometryCollection' in geom_type:
                    # STABILITY FIX: Use safe wrapper for conversion
                    converted = safe_convert_to_multi_polygon(geom)
                    if converted:
                        new_geom = converted
                        conversion_count += 1
                        logger.debug(f"Converted GeometryCollection to {get_geometry_type_name(new_geom)}")
                    else:
                        # Fallback: try extracting polygons using safe wrapper
                        polygon_parts = extract_polygons_from_collection(geom)
                        if polygon_parts:
                            # Create MultiPolygon from extracted parts
                            if len(polygon_parts) == 1:
                                poly_data = safe_as_polygon(polygon_parts[0])
                                if poly_data:
                                    new_geom = QgsGeometry.fromMultiPolygonXY([poly_data])
                            else:
                                multi_poly_parts = [safe_as_polygon(p) for p in polygon_parts]
                                multi_poly_parts = [p for p in multi_poly_parts if p]
                                if multi_poly_parts:
                                    new_geom = QgsGeometry.fromMultiPolygonXY(multi_poly_parts)
                            conversion_count += 1
                        else:
                            logger.warning("GeometryCollection contained no polygon parts - skipping feature")
                            continue
                
                elif 'Polygon' in geom_type and 'Multi' not in geom_type:
                    # Convert single Polygon to MultiPolygon for consistency
                    poly_data = safe_as_polygon(geom)
                    if poly_data:
                        new_geom = QgsGeometry.fromMultiPolygonXY([poly_data])
                
                # Create new feature with converted geometry
                new_feature = QgsFeature(fields)
                new_feature.setGeometry(new_geom)
                new_feature.setAttributes(feature.attributes())
                converted_features.append(new_feature)
            
            # Add converted features
            if converted_features:
                success, _ = converted_dp.addFeatures(converted_features)
                if success:
                    converted_layer.updateExtents()
                    logger.info(f"✓ Converted {conversion_count} GeometryCollection(s) to MultiPolygon")
                    return converted_layer
                else:
                    logger.error("Failed to add converted features to layer")
                    return layer
            else:
                logger.warning("No features to convert")
                return layer
                
        except Exception as e:
            logger.error(f"Error converting GeometryCollection: {str(e)}")
            import traceback
            logger.debug(f"Conversion traceback: {traceback.format_exc()}")
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
        # ALWAYS use MultiPolygon for buffer results - buffers always produce polygons
        # regardless of source geometry type (Point, Line, Polygon)
        # Using MultiPolygon handles both single and multi-part results
        geom_type = "MultiPolygon"
        buffered_layer = QgsVectorLayer(
            f"{geom_type}?crs={layer.crs().authid()}",
            "buffered_temp",
            "memory"
        )
        return buffered_layer

    def _buffer_all_features(self, layer, buffer_dist):
        """
        Buffer all features from layer.
        
        STABILITY FIX v2.3.9: Uses safe_buffer wrapper to prevent
        access violations on certain machines.
        
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
            
            # STABILITY FIX: Use validate_geometry for proper checking
            if not validate_geometry(geom):
                logger.debug(f"Feature {idx}: Invalid or empty geometry, skipping")
                invalid_features += 1
                continue
            
            try:
                # STABILITY FIX: Use safe_buffer wrapper instead of direct buffer()
                # This handles invalid geometries gracefully and prevents GEOS crashes
                buffered_geom = safe_buffer(geom, buffer_dist, 5)
                
                if buffered_geom is not None:
                    geometries.append(buffered_geom)
                    valid_features += 1
                    logger.debug(f"Feature {idx}: Buffered geometry accepted")
                else:
                    logger.warning(f"Feature {idx}: safe_buffer returned None")
                    invalid_features += 1
                    
            except Exception as buffer_error:
                logger.warning(f"Feature {idx}: Buffer operation failed: {buffer_error}")
                invalid_features += 1
        
        logger.debug(f"Manual buffer results: {valid_features} valid, {invalid_features} invalid features")
        return geometries, valid_features, invalid_features

    def _dissolve_and_add_to_layer(self, geometries, buffered_layer):
        """
        Dissolve geometries and add to memory layer.
        
        STABILITY FIX v2.3.9: Uses geometry_safety module to prevent
        access violations when handling GeometryCollections.
        
        Args:
            geometries: List of buffered geometries
            buffered_layer: Target memory layer
            
        Returns:
            QgsVectorLayer: Layer with dissolved geometry added
        """
        # Filter out invalid geometries first (STABILITY FIX)
        valid_geometries = [g for g in geometries if validate_geometry(g)]
        
        if not valid_geometries:
            logger.warning("_dissolve_and_add_to_layer: No valid geometries to dissolve")
            return buffered_layer
        
        # Dissolve all geometries into one using safe wrapper
        dissolved_geom = safe_unary_union(valid_geometries)
        
        if dissolved_geom is None:
            logger.error("_dissolve_and_add_to_layer: safe_unary_union returned None")
            return buffered_layer
        
        # STABILITY FIX: Use safe conversion to MultiPolygon
        final_type = get_geometry_type_name(dissolved_geom)
        logger.debug(f"Dissolved geometry type: {final_type}")
        
        if 'GeometryCollection' in final_type or 'Polygon' not in final_type:
            logger.info(f"Converting {final_type} to MultiPolygon using safe wrapper")
            converted = safe_convert_to_multi_polygon(dissolved_geom)
            if converted:
                dissolved_geom = converted
                logger.info(f"Converted to {get_geometry_type_name(dissolved_geom)}")
            else:
                # Last resort: extract polygons manually using safe function
                logger.warning("safe_convert_to_multi_polygon failed, extracting polygons")
                polygon_parts = extract_polygons_from_collection(dissolved_geom)
                if polygon_parts:
                    collected = safe_collect_geometry(polygon_parts)
                    if collected:
                        dissolved_geom = collected
                        # Force conversion if still not polygon
                        if 'Polygon' not in get_geometry_type_name(dissolved_geom):
                            converted = dissolved_geom.convertToType(QgsWkbTypes.PolygonGeometry, True)
                            if converted and not converted.isEmpty():
                                dissolved_geom = converted
                else:
                    logger.error("Could not extract any polygons from geometry")
                    return buffered_layer
        
        # FINAL SAFETY CHECK: Ensure geometry is MultiPolygon before adding to layer
        if validate_geometry(dissolved_geom):
            final_type = get_geometry_type_name(dissolved_geom)
            logger.info(f"Final geometry type before adding: {final_type}")
            
            # Ensure it's MultiPolygon (not single Polygon)
            if dissolved_geom.wkbType() == QgsWkbTypes.Polygon:
                # Convert single Polygon to MultiPolygon using safe wrapper
                poly_data = safe_as_polygon(dissolved_geom)
                if poly_data:
                    dissolved_geom = QgsGeometry.fromMultiPolygonXY([poly_data])
                    logger.debug("Converted single Polygon to MultiPolygon")
        else:
            logger.error("Final dissolved geometry is invalid")
            return buffered_layer
        
        # Create feature with dissolved geometry
        feat = QgsFeature()
        feat.setGeometry(dissolved_geom)
        
        provider = buffered_layer.dataProvider()
        success, _ = provider.addFeatures([feat])
        if not success:
            logger.error(f"Failed to add feature to buffer layer. Geometry type: {get_geometry_type_name(dissolved_geom)}")
        buffered_layer.updateExtents()
        
        # Create spatial index for improved performance
        self._verify_and_create_spatial_index(buffered_layer, "buffered_temp")
        
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
        
        # Create spatial index for improved performance
        self._verify_and_create_spatial_index(repaired_layer, "repaired_geometries")
        
        logger.info(f"✓ Geometry repair complete: {repaired_count}/{invalid_count} successfully repaired, {len(features_to_add)}/{total_features} features kept")
        return repaired_layer

    def _apply_buffer_with_fallback(self, layer, buffer_distance):
        """
        Apply buffer to layer with automatic fallback to manual method.
        Validates and repairs geometries before buffering.
        
        STABILITY FIX v2.3.9: Added input layer validation to prevent access violations.
        
        Args:
            layer: Input layer
            buffer_distance: QgsProperty or float
            
        Returns:
            QgsVectorLayer: Buffered layer, or None on failure
        """
        logger.info(f"Applying buffer: distance={buffer_distance}")
        
        # STABILITY FIX v2.3.9: Validate input layer before any operations
        if layer is None:
            logger.error("_apply_buffer_with_fallback: Input layer is None")
            return None
        
        if not layer.isValid():
            logger.error(f"_apply_buffer_with_fallback: Input layer is not valid")
            return None
        
        if layer.featureCount() == 0:
            logger.warning(f"_apply_buffer_with_fallback: Input layer has no features")
            return None
        
        # DISABLED: Skip geometry repair
        # layer = self._repair_invalid_geometries(layer)
        
        try:
            # Try QGIS buffer algorithm first
            result = self._apply_qgis_buffer(layer, buffer_distance)
            
            # STABILITY FIX v2.3.9: Validate result before returning
            if result is None or not result.isValid() or result.featureCount() == 0:
                logger.warning("_apply_qgis_buffer returned invalid/empty result, trying manual buffer")
                raise Exception("QGIS buffer returned invalid result")
            
            return result
            
        except Exception as e:
            # Fallback to manual buffer
            logger.warning(f"QGIS buffer algorithm failed: {str(e)}, using manual buffer approach")
            try:
                result = self._create_buffered_memory_layer(layer, buffer_distance)
                
                # STABILITY FIX v2.3.9: Validate result before returning
                if result is None or not result.isValid() or result.featureCount() == 0:
                    logger.error("Manual buffer also returned invalid/empty result")
                    return None
                
                return result
                
            except Exception as manual_error:
                logger.error(f"Both buffer methods failed. QGIS: {str(e)}, Manual: {str(manual_error)}")
                logger.error("Returning None - buffer operation failed completely")
                return None


    def prepare_ogr_source_geom(self):
        """
        Prepare OGR source geometry with optional reprojection and buffering.
        
        REFACTORED: Decomposed from 173 lines to ~35 lines using helper methods.
        Main method now orchestrates geometry preparation workflow.
        
        Process:
        1. Copy filtered layer to memory (if subset string active OR features selected OR field-based mode)
        2. Fix invalid geometries in source layer
        3. Reproject if needed
        4. Apply buffer if specified
        5. Store result in self.ogr_source_geom
        """
        layer = self.source_layer
        
        # Step 0: CRITICAL - Copy to memory if layer has subset string OR selected features
        # This prevents issues with QGIS algorithms not handling subset strings/selections correctly
        has_subset = bool(layer.subsetString())
        has_selection = layer.selectedFeatureCount() > 0
        
        # Check if we're in field-based mode (Custom Selection with a simple field name)
        is_field_based_mode = (
            hasattr(self, 'is_field_expression') and 
            self.is_field_expression is not None and
            isinstance(self.is_field_expression, tuple) and
            len(self.is_field_expression) >= 2 and
            self.is_field_expression[0] is True
        )
        
        logger.info(f"=== prepare_ogr_source_geom DEBUG ===")
        logger.info(f"  has_subset: {has_subset}")
        logger.info(f"  has_selection: {has_selection}")
        logger.info(f"  is_field_based_mode: {is_field_based_mode}")
        if has_subset:
            logger.info(f"  Current subset: '{layer.subsetString()[:100]}'")
        
        if has_subset or has_selection:
            if has_subset:
                logger.debug(f"Source layer has subset string, copying to memory first...")
            if has_selection:
                logger.debug(f"Source layer has {layer.selectedFeatureCount()} selected features, copying selection to memory...")
            
            # For multi-selection, copy only selected features
            if has_selection and not has_subset:
                layer = self._copy_selected_features_to_memory(layer, "source_selection")
            else:
                layer = self._copy_filtered_layer_to_memory(layer, "source_filtered")
        elif is_field_based_mode:
            # FIELD-BASED MODE: Use all visible features from filtered source layer
            # The source layer keeps its current filter (subset string)
            # We copy ALL filtered features to use for geometric intersection with distant layers
            logger.info(f"=== prepare_ogr_source_geom (FIELD-BASED MODE) ===")
            logger.info(f"  Field name: '{self.is_field_expression[1]}'")
            logger.info(f"  Source subset: '{layer.subsetString()[:80] if layer.subsetString() else '(none)'}...'")
            logger.info(f"  Using ALL {layer.featureCount()} filtered features for geometric intersection")
            # Copy all visible features to memory for consistent processing
            layer = self._copy_filtered_layer_to_memory(layer, "source_field_based")
        
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
        # SPATIALITE OPTIMIZATION: If spatialite_source_geom is prepared OR we're in fallback mode,
        # buffer will be applied via ST_Buffer() in SQL expression, so skip buffer here
        has_spatialite_geom = hasattr(self, 'spatialite_source_geom') and self.spatialite_source_geom is not None
        is_spatialite_fallback = hasattr(self, '_spatialite_fallback_mode') and self._spatialite_fallback_mode
        skip_buffer = has_spatialite_geom or is_spatialite_fallback
        
        if buffer_distance is not None and not skip_buffer:
            # Only apply buffer via processing if Spatialite WKT is NOT available
            # (Spatialite backend will use ST_Buffer() in SQL instead)
            logger.info("Applying buffer via QGIS processing (Spatialite WKT not available)")
            buffered_layer = self._apply_buffer_with_fallback(layer, buffer_distance)
            
            # STABILITY FIX v2.3.9: Check if buffer failed (returns None) or produced empty layer
            if buffered_layer is None or not buffered_layer.isValid() or buffered_layer.featureCount() == 0:
                logger.warning("⚠️ Buffer operation failed or produced empty layer - using unbuffered geometry")
                # Fallback: use original geometry without buffer
                layer = self.source_layer
                if layer.subsetString():
                    layer = self._copy_filtered_layer_to_memory(layer, "source_filtered_no_buffer")
            else:
                layer = buffered_layer
        elif buffer_distance is not None and skip_buffer:
            logger.info(f"Buffer of {buffer_distance}m will be applied via ST_Buffer() in Spatialite SQL")
        
        # STABILITY FIX v2.3.9: Validate the final layer before storing
        if layer is None:
            logger.error("prepare_ogr_source_geom: Final layer is None")
            self.ogr_source_geom = None
            return
        
        if not layer.isValid():
            logger.error(f"prepare_ogr_source_geom: Final layer is not valid")
            self.ogr_source_geom = None
            return
        
        if layer.featureCount() == 0:
            logger.warning("prepare_ogr_source_geom: Final layer has no features")
            self.ogr_source_geom = None
            return
        
        # Validate at least one geometry is valid
        has_valid_geom = False
        for feature in layer.getFeatures():
            geom = feature.geometry()
            if validate_geometry(geom):
                has_valid_geom = True
                break
        
        if not has_valid_geom:
            logger.error("prepare_ogr_source_geom: Final layer has no valid geometries")
            self.ogr_source_geom = None
            return
        
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
        
        # Build source table reference for subquery
        source_schema = self.param_source_schema
        source_table = self.param_source_table
        source_geom_field = self.param_source_geom
        
        for postgis_predicate in postgis_predicates:
            current_geom_expr = param_distant_geom_expression
            
            if param_has_to_reproject_layer:
                # Reprojeter le layer distant dans le même CRS métrique que le source
                current_geom_expr = 'ST_Transform({param_distant_geom_expression}, {target_crs_srid})'.format(
                    param_distant_geom_expression=param_distant_geom_expression,
                    target_crs_srid=target_crs_srid
                )
                logger.debug(f"Layer will be reprojected to {self.source_layer_crs_authid} for comparison")
            
            # CRITICAL FIX: Use subquery with EXISTS to avoid "missing FROM-clause" error
            # setSubsetString cannot reference other tables directly, need subquery
            postgis_sub_expression_array.append(
                'EXISTS (SELECT 1 FROM "{source_schema}"."{source_table}" AS __source WHERE {predicate}({distant_geom},{source_geom}))'.format(
                    source_schema=source_schema,
                    source_table=source_table,
                    predicate=postgis_predicate,
                    distant_geom=current_geom_expr,
                    source_geom='__source."{}"'.format(source_geom_field)
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
        
        STABILITY FIX v2.3.9: Added comprehensive validation before calling selectbylocation
        to prevent access violations from invalid geometries.
        
        Args:
            layer: Original layer
            current_layer: Potentially reprojected working layer
            param_old_subset: Existing subset string
            
        Returns:
            None (modifies current_layer selection)
        """
        # CRITICAL FIX: Validate ogr_source_geom before using it
        if not self.ogr_source_geom:
            logger.error("ogr_source_geom is None - cannot execute spatial selection")
            raise Exception("Source geometry layer is not available for spatial selection")
        
        if not isinstance(self.ogr_source_geom, QgsVectorLayer):
            logger.error(f"ogr_source_geom is not a QgsVectorLayer: {type(self.ogr_source_geom)}")
            raise Exception(f"Source geometry must be a QgsVectorLayer, got {type(self.ogr_source_geom)}")
        
        if not self.ogr_source_geom.isValid():
            logger.error(f"ogr_source_geom is not valid: {self.ogr_source_geom.name()}")
            raise Exception("Source geometry layer is not valid")
        
        if self.ogr_source_geom.featureCount() == 0:
            logger.warning("ogr_source_geom has no features - spatial selection will return no results")
            return
        
        # STABILITY FIX v2.3.9: Validate that at least one geometry is valid before calling selectbylocation
        # This prevents access violations from corrupted or invalid geometries
        has_valid_geom = False
        for feature in self.ogr_source_geom.getFeatures():
            geom = feature.geometry()
            if validate_geometry(geom):
                has_valid_geom = True
                break
        
        if not has_valid_geom:
            logger.error("ogr_source_geom has no valid geometries - spatial selection would fail")
            raise Exception("Source geometry layer has no valid geometries")
        
        logger.info(f"Using ogr_source_geom: {self.ogr_source_geom.name()}, "
                   f"features={self.ogr_source_geom.featureCount()}, "
                   f"geomType={QgsWkbTypes.displayString(self.ogr_source_geom.wkbType())}")
        
        # STABILITY FIX v2.3.9: Configure processing context to skip invalid geometries
        # This prevents access violations when selectbylocation encounters corrupted geometries
        context = QgsProcessingContext()
        context.setInvalidGeometryCheck(QgsFeatureRequest.GeometrySkipInvalid)
        feedback = QgsProcessingFeedback()
        
        # CRITICAL FIX v2.3.9.2: Use create_geos_safe_layer for geometry validation
        # The function now handles fallbacks gracefully and returns original layer as last resort
        logger.info("🛡️ Creating GEOS-safe source layer (geometry validation)...")
        safe_source_geom = create_geos_safe_layer(self.ogr_source_geom, "_safe_source")
        
        # create_geos_safe_layer now returns the original layer as fallback, never None for valid input
        if safe_source_geom is None:
            logger.warning("create_geos_safe_layer returned None, using original")
            safe_source_geom = self.ogr_source_geom
        
        if not safe_source_geom.isValid() or safe_source_geom.featureCount() == 0:
            logger.error("No valid source geometries available")
            raise Exception("Source geometry layer has no valid geometries")
        
        logger.info(f"✓ Safe source layer: {safe_source_geom.featureCount()} features")
        
        # Also process current_layer if not too large (to avoid performance issues)
        safe_current_layer = current_layer
        use_safe_current = False
        if current_layer.featureCount() <= 50000:  # Only process smaller layers for performance
            logger.debug("🛡️ Creating GEOS-safe target layer...")
            temp_safe_layer = create_geos_safe_layer(current_layer, "_safe_target")
            if temp_safe_layer and temp_safe_layer.isValid() and temp_safe_layer.featureCount() > 0:
                safe_current_layer = temp_safe_layer
                use_safe_current = True
                logger.info(f"✓ Safe target layer: {safe_current_layer.featureCount()} features")
        
        predicate_list = [int(predicate) for predicate in self.current_predicates.keys()]
        
        # Helper function to map selection back to original layer if we used safe layer
        def map_selection_to_original():
            if use_safe_current and safe_current_layer is not current_layer:
                selected_fids = [f.id() for f in safe_current_layer.selectedFeatures()]
                if selected_fids:
                    current_layer.selectByIds(selected_fids)
                    logger.debug(f"Mapped {len(selected_fids)} features back to original layer")
        
        # Use safe layers for spatial operations
        work_layer = safe_current_layer if use_safe_current else current_layer
        
        if self.has_combine_operator is True:
            work_layer.selectAll()
            
            if self.param_other_layers_combine_operator == 'OR':
                self._verify_and_create_spatial_index(work_layer)
                # CRITICAL FIX: Thread-safe subset string application
                safe_set_subset_string(work_layer, param_old_subset)
                work_layer.selectAll()
                safe_set_subset_string(work_layer, '')
                
                alg_params_select = {
                    'INPUT': work_layer,
                    'INTERSECT': safe_source_geom,
                    'METHOD': 1,
                    'PREDICATE': predicate_list
                }
                processing.run("qgis:selectbylocation", alg_params_select, context=context, feedback=feedback)
                map_selection_to_original()
                
            elif self.param_other_layers_combine_operator == 'AND':
                self._verify_and_create_spatial_index(work_layer)
                alg_params_select = {
                    'INPUT': work_layer,
                    'INTERSECT': safe_source_geom,
                    'METHOD': 2,
                    'PREDICATE': predicate_list
                }
                processing.run("qgis:selectbylocation", alg_params_select, context=context, feedback=feedback)
                map_selection_to_original()
                
            elif self.param_other_layers_combine_operator == 'NOT AND':
                self._verify_and_create_spatial_index(work_layer)
                alg_params_select = {
                    'INPUT': work_layer,
                    'INTERSECT': safe_source_geom,
                    'METHOD': 3,
                    'PREDICATE': predicate_list
                }
                processing.run("qgis:selectbylocation", alg_params_select, context=context, feedback=feedback)
                map_selection_to_original()
                
            else:
                self._verify_and_create_spatial_index(work_layer)
                alg_params_select = {
                    'INPUT': work_layer,
                    'INTERSECT': safe_source_geom,
                    'METHOD': 0,
                    'PREDICATE': predicate_list
                }
                processing.run("qgis:selectbylocation", alg_params_select, context=context, feedback=feedback)
                map_selection_to_original()
        else:
            self._verify_and_create_spatial_index(work_layer)
            alg_params_select = {
                'INPUT': work_layer,
                'INTERSECT': safe_source_geom,
                'METHOD': 0,
                'PREDICATE': predicate_list
            }
            processing.run("qgis:selectbylocation", alg_params_select, context=context, feedback=feedback)
            map_selection_to_original()


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
        # CRITICAL FIX: Handle ctid (PostgreSQL internal identifier)
        # ctid is not accessible via feature[field_name], use feature.id() instead
        features_ids = []
        for feature in current_layer.selectedFeatures():
            if param_distant_primary_key_name == 'ctid':
                features_ids.append(str(feature.id()))
            else:
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


    def _normalize_column_names_for_postgresql(self, expression, field_names):
        """
        Normalize column names in expression to match actual PostgreSQL column names.
        
        PostgreSQL is case-sensitive for quoted identifiers. If columns were created
        without quotes, they are stored in lowercase. This function corrects column
        names in filter expressions to match the actual column names.
        
        For example: "SUB_TYPE" → "sub_type" if the column exists as "sub_type"
        
        Args:
            expression: SQL expression string
            field_names: List of actual field names from the layer
            
        Returns:
            str: Expression with corrected column names
        """
        if not expression or not field_names:
            return expression
        
        result_expression = expression
        
        # Build case-insensitive lookup map: lowercase → actual name
        field_lookup = {name.lower(): name for name in field_names}
        
        # Find all quoted column names in expression (e.g., "SUB_TYPE")
        quoted_cols = re.findall(r'"([^"]+)"', result_expression)
        
        corrections_made = []
        for col_name in quoted_cols:
            # Skip if column exists with exact case (no correction needed)
            if col_name in field_names:
                continue
            
            # Check for case-insensitive match
            col_lower = col_name.lower()
            if col_lower in field_lookup:
                correct_name = field_lookup[col_lower]
                # Replace the incorrectly cased column name with correct one
                result_expression = result_expression.replace(
                    f'"{col_name}"',
                    f'"{correct_name}"'
                )
                corrections_made.append(f'"{col_name}" → "{correct_name}"')
        
        if corrections_made:
            logger.info(f"PostgreSQL column case normalization: {', '.join(corrections_made)}")
        
        return result_expression

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
        
        # CRITICAL FIX: For PostgreSQL, first normalize column names to match actual database column case
        # This fixes "column X does not exist" errors caused by case mismatch
        # (e.g., "SUB_TYPE" in expression but "sub_type" in database)
        if is_postgresql:
            # Include primary key in field names for case normalization
            all_fields = list(field_names) + ([primary_key_name] if primary_key_name else [])
            result_expression = self._normalize_column_names_for_postgresql(result_expression, all_fields)
        
        # For OGR and Spatialite, just ensure field names are quoted, no table qualification
        if self.param_source_provider_type in (PROVIDER_OGR, PROVIDER_SPATIALITE):
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
        
        # CRITICAL FIX: Removed extra closing parenthesis that was causing SQL syntax errors
        # When there's no WHERE clause, we should wrap in parentheses; when there is, just combine
        if index_where_clause > -1:
            # Has WHERE clause - combine with existing structure
            combined = f'{param_source_old_subset} {param_old_subset_where_clause} {combine_operator} {new_expression}'
        else:
            # No WHERE clause - wrap both in parentheses for safety
            combined = f'( {old_subset} ) {combine_operator} ( {new_expression} )'
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
        
        For PostgreSQL with few source features, passes WKT for simplified expressions.
        Uses expression cache for repeated operations (Phase 4 optimization).
        
        Args:
            backend: Backend instance
            layer_props: Layer properties dict
            source_geom: Prepared source geometry
            
        Returns:
            str: Filter expression or None on error
        """
        # Get source layer filter for EXISTS subqueries
        # CRITICAL: Use param_source_new_subset instead of subsetString() to avoid recursive filters
        # param_source_new_subset contains the clean filter before combination with old subset
        source_filter = None
        if hasattr(self, 'param_source_new_subset') and self.param_source_new_subset:
            source_filter = self.param_source_new_subset
            logger.debug(f"Using source filter for EXISTS subquery: {source_filter}")
        elif hasattr(self, 'expression') and self.expression:
            # Fallback to current expression if param_source_new_subset not set
            source_filter = self.expression
            logger.debug(f"Using expression as source filter for EXISTS: {source_filter}")
        
        # CRITICAL FIX: Validate source_filter before passing to backend
        # If source_filter contains spatial predicates or __source alias, it's invalid
        # and would cause SQL duplication errors in EXISTS subqueries
        if source_filter:
            source_filter_upper = source_filter.upper()
            is_invalid_filter = any(pattern in source_filter_upper for pattern in [
                'ST_INTERSECTS', 'ST_CONTAINS', 'ST_WITHIN', 'ST_TOUCHES',
                'ST_OVERLAPS', 'ST_CROSSES', 'ST_DISJOINT', 'ST_EQUALS',
                '__SOURCE', 'EXISTS (', 'EXISTS('
            ])
            
            if is_invalid_filter:
                logger.warning(f"⚠️ Source filter contains spatial predicates or EXISTS - clearing to prevent SQL errors")
                logger.warning(f"  → Invalid filter: '{source_filter[:100]}...'")
                logger.warning(f"  → This is likely from a previous geometric filter operation")
                source_filter = None
        
        # Get source feature count and WKT for simplified PostgreSQL expressions
        source_wkt = None
        source_srid = None
        source_feature_count = None
        
        # For PostgreSQL, provide WKT for small datasets (simpler expression)
        if backend.get_backend_name() == 'PostgreSQL':
            source_feature_count = self.source_layer.featureCount()
            
            # If Spatialite WKT is available, use it for PostgreSQL too (same format)
            if hasattr(self, 'spatialite_source_geom') and self.spatialite_source_geom:
                source_wkt = self.spatialite_source_geom
                # Extract SRID from source layer CRS
                if hasattr(self, 'source_layer_crs_authid') and self.source_layer_crs_authid:
                    try:
                        source_srid = int(self.source_layer_crs_authid.split(':')[1])
                    except (ValueError, IndexError):
                        source_srid = 4326  # Default to WGS84
                else:
                    source_srid = 4326
                
                logger.debug(f"PostgreSQL simple mode: {source_feature_count} features, SRID={source_srid}")
        
        # Phase 4: Check expression cache before building
        layer = layer_props.get('layer')
        layer_id = layer.id() if layer and hasattr(layer, 'id') else None
        
        if layer_id and self.expr_cache:
            # Compute cache key
            source_hash = self.expr_cache.compute_source_hash(source_geom)
            buffer_value = self.param_buffer_value if hasattr(self, 'param_buffer_value') else None
            provider_type = backend.get_backend_name().lower()
            
            cache_key = self.expr_cache.get_cache_key(
                layer_id=layer_id,
                predicates=self.current_predicates,
                buffer_value=buffer_value,
                source_geometry_hash=source_hash,
                provider_type=provider_type
            )
            
            # Try to get cached expression
            cached_expression = self.expr_cache.get(cache_key)
            if cached_expression:
                logger.info(f"✓ Expression cache HIT for {layer.name() if layer else 'unknown'}")
                return cached_expression
        else:
            cache_key = None
        
        expression = backend.build_expression(
            layer_props=layer_props,
            predicates=self.current_predicates,
            source_geom=source_geom,
            buffer_value=self.param_buffer_value if hasattr(self, 'param_buffer_value') else None,
            buffer_expression=self.param_buffer_expression if hasattr(self, 'param_buffer_expression') else None,
            source_filter=source_filter,
            source_wkt=source_wkt,
            source_srid=source_srid,
            source_feature_count=source_feature_count
        )
        
        if not expression:
            logger.warning(f"No expression generated by backend")
            return None
        
        # Phase 4: Store in cache for future use
        if cache_key and self.expr_cache:
            self.expr_cache.put(cache_key, expression)
            logger.debug(f"Expression cached for {layer.name() if layer else 'unknown'}")
        
        return expression

    def _combine_with_old_filter(self, expression, layer):
        """
        Combine new expression with existing subset if needed.
        
        COMPORTEMENT PAR DÉFAUT:
        - Si un filtre existant est présent, il est TOUJOURS préservé
        - Si aucun opérateur n'est spécifié, utilise AND par défaut
        - Garantit que les filtres multi-couches ne sont jamais perdus
        - EXCEPTION: Les filtres géométriques (EXISTS, ST_*) sont REMPLACÉS, pas combinés
        
        Args:
            expression: New filter expression
            layer: QGIS vector layer
            
        Returns:
            str: Final combined expression
        """
        old_subset = layer.subsetString() if layer.subsetString() != '' else None
        
        # Si aucun filtre existant, retourner la nouvelle expression
        if not old_subset:
            return expression
        
        # CRITICAL FIX: Check for invalid old_subset patterns that should NOT be combined
        # These patterns indicate a previous geometric filter that should be replaced
        old_subset_upper = old_subset.upper()
        
        # Pattern 1: __source alias (only valid inside EXISTS subqueries)
        has_source_alias = '__source' in old_subset.lower()
        
        # Pattern 2: EXISTS subquery (avoid nested EXISTS)
        has_exists = 'EXISTS (' in old_subset_upper or 'EXISTS(' in old_subset_upper
        
        # Pattern 3: Spatial predicates (likely from previous geometric filter)
        spatial_predicates = [
            'ST_INTERSECTS', 'ST_CONTAINS', 'ST_WITHIN', 'ST_TOUCHES',
            'ST_OVERLAPS', 'ST_CROSSES', 'ST_DISJOINT', 'ST_EQUALS',
            'ST_DWITHIN', 'ST_COVERS', 'ST_COVEREDBY'
        ]
        has_spatial_predicate = any(pred in old_subset_upper for pred in spatial_predicates)
        
        # If old_subset contains geometric filter patterns, replace instead of combine
        if has_source_alias or has_exists or has_spatial_predicate:
            reason = []
            if has_source_alias:
                reason.append("__source alias")
            if has_exists:
                reason.append("EXISTS subquery")
            if has_spatial_predicate:
                reason.append("spatial predicate")
            
            logger.info(f"FilterMate: Old subset contains {', '.join(reason)} - replacing instead of combining")
            return expression
        
        # Récupérer l'opérateur (ou AND par défaut)
        combine_operator = self._get_combine_operator()
        if not combine_operator:
            # NOUVEAU: Utiliser AND par défaut pour préserver les filtres existants
            combine_operator = 'AND'
            logger.info(f"FilterMate: Préservation du filtre existant sur {layer.name()} avec AND par défaut")
        
        return f"({old_subset}) {combine_operator} ({expression})"

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
            # STABILITY FIX v2.3.9: Validate layer before any operations
            # This prevents access violations on deleted/invalid layers
            if not is_valid_layer(layer):
                logger.error(f"Cannot filter layer: layer is invalid or has been deleted")
                return False
            
            # Additional safety check - verify layer exists in project
            try:
                layer_id = layer.id()
                layer_name_check = layer.name()
                if not layer.isValid():
                    logger.error(f"Layer {layer_name_check} is not valid - skipping filtering")
                    return False
            except (RuntimeError, AttributeError) as e:
                logger.error(f"Layer access error (C++ object may be deleted): {e}")
                return False
            
            # CRITICAL FIX: Use effective provider type if PostgreSQL fallback is active
            effective_provider_type = layer_props.get("_effective_provider_type", layer_provider_type)
            is_postgresql_fallback = layer_props.get("_postgresql_fallback", False)
            
            if is_postgresql_fallback:
                logger.info(f"Executing geometric filtering for {layer.name()} (PostgreSQL → OGR fallback)")
            else:
                logger.info(f"Executing geometric filtering for {layer.name()} ({effective_provider_type})")
            
            # Validate layer properties
            layer_name, primary_key, geom_field, layer_schema = self._validate_layer_properties(
                layer_props, 
                layer.name()
            )
            if not layer_name:
                return False
            
            # Verify spatial index exists before filtering - critical for performance
            self._verify_and_create_spatial_index(layer, layer_name)
            
            # Check if backend is forced for this layer
            forced_backends = self.task_parameters.get('forced_backends', {})
            forced_backend = forced_backends.get(layer.id())
            
            if forced_backend:
                logger.info(f"  ⚡ Using FORCED backend '{forced_backend}' for layer '{layer_name}'")
                # Force the provider type to match the forced backend
                effective_provider_type = forced_backend
            
            # Get appropriate backend for this layer - use effective provider type
            backend = BackendFactory.get_backend(effective_provider_type, layer, self.task_parameters)
            
            # CRITICAL FIX: Use backend type to determine geometry format, not provider type
            # The factory may return different backends than expected:
            # 1. SpatialiteGeometricFilter for OGR layers (GeoPackage/SQLite) - needs WKT string
            # 2. OGRGeometricFilter for PostgreSQL layers (small dataset / fallback) - needs QgsVectorLayer
            # 3. PostgreSQLGeometricFilter for PostgreSQL layers - needs SQL expression
            backend_name = backend.get_backend_name().lower()
            
            # Log actual backend being used
            if forced_backend and backend_name != forced_backend:
                logger.warning(f"  ⚠️ Forced backend '{forced_backend}' but got '{backend_name}' (backend may not support layer)")
            else:
                logger.info(f"  ✓ Using backend: {backend_name}")
            
            # Store actual backend used for this layer (for UI indicator)
            if 'actual_backends' not in self.task_parameters:
                self.task_parameters['actual_backends'] = {}
            self.task_parameters['actual_backends'][layer.id()] = backend_name
            
            # Determine geometry provider based on backend type, not layer provider
            if backend_name == 'spatialite':
                # Spatialite backend ALWAYS needs WKT string, regardless of layer provider type
                geometry_provider = PROVIDER_SPATIALITE
                logger.info(f"  → Backend is Spatialite - using WKT geometry format")
            elif backend_name == 'ogr':
                # OGR backend needs QgsVectorLayer
                geometry_provider = PROVIDER_OGR
                if effective_provider_type == PROVIDER_POSTGRES:
                    logger.info(f"  → Backend is OGR but provider is PostgreSQL - using OGR geometry format (fallback/optimization)")
                else:
                    logger.info(f"  → Backend is OGR - using QgsVectorLayer geometry format")
            elif backend_name == 'postgresql':
                # PostgreSQL backend needs SQL expression
                geometry_provider = PROVIDER_POSTGRES
                logger.info(f"  → Backend is PostgreSQL - using SQL expression geometry format")
            else:
                # Fallback: use effective provider type
                geometry_provider = effective_provider_type
                logger.warning(f"  → Unknown backend '{backend_name}' - using provider type {effective_provider_type}")
            
            # Prepare source geometry based on backend requirements - use geometry_provider
            logger.info(f"  → Preparing source geometry for provider: {geometry_provider}")
            logger.info(f"  → spatialite_source_geom exists: {hasattr(self, 'spatialite_source_geom')}")
            if hasattr(self, 'spatialite_source_geom'):
                logger.info(f"  → spatialite_source_geom length: {len(self.spatialite_source_geom) if self.spatialite_source_geom else 'None'}")
            source_geom = self._prepare_source_geometry(geometry_provider)
            if not source_geom:
                logger.error(f"Failed to prepare source geometry for {layer.name()}")
                logger.error(f"  → backend_name: {backend_name}")
                logger.error(f"  → geometry_provider: {geometry_provider}")
                logger.error(f"  → effective_provider_type: {effective_provider_type}")
                logger.error(f"  → spatialite_source_geom: {getattr(self, 'spatialite_source_geom', 'NOT SET')}")
                logger.error(f"  → ogr_source_geom: {getattr(self, 'ogr_source_geom', 'NOT SET')}")
                return False
            logger.info(f"  ✓ Source geometry ready: {type(source_geom).__name__}")
            
            # Ensure layer object is in layer_props for backend use
            if 'layer' not in layer_props:
                layer_props['layer'] = layer
            
            # CRITICAL FIX: Clean corrupted subset strings BEFORE any processing
            # Proactively clear any subset containing __source alias (invalid from previous failed ops)
            current_subset = layer.subsetString()
            if current_subset and '__source' in current_subset.lower():
                logger.warning(f"🧹 CLEANING corrupted subset on {layer.name()} BEFORE filtering")
                logger.warning(f"  → Corrupted subset found: '{current_subset[:100]}'...")
                logger.warning(f"  → Clearing it to prevent SQL errors")
                # Use thread-safe method to clear the subset
                from .signal_utils import safe_set_subset_string
                safe_set_subset_string(layer, "")
                logger.info(f"  ✓ Layer {layer.name()} subset cleared - ready for fresh filter")
            
            # Build filter expression using backend
            logger.info(f"  → Building backend expression with predicates: {self.current_predicates}")
            expression = self._build_backend_expression(backend, layer_props, source_geom)
            if not expression:
                logger.warning(f"No expression generated for {layer.name()}")
                logger.warning(f"  → backend type: {type(backend).__name__}")
                logger.warning(f"  → current_predicates: {self.current_predicates}")
                logger.warning(f"  → source_geom type: {type(source_geom).__name__}")
                return False
            logger.info(f"  ✓ Expression built: {len(expression)} chars")
            logger.info(f"  → Expression preview: {expression[:200]}...")
            
            # Get old subset and combine operator for backend to handle
            old_subset = layer.subsetString() if layer.subsetString() != '' else None
            combine_operator = self._get_combine_operator()
            
            # CRITICAL FIX: Clean invalid old_subset from previous geometric filtering operations
            # Invalid old_subset patterns that MUST be cleared:
            # 1. Contains __source alias (only valid inside EXISTS subqueries)
            # 2. Contains EXISTS subquery (would create nested EXISTS = complex/slow)
            # 3. Contains spatial predicates (ST_Intersects, etc.) - likely cross-table filter
            #
            # When these patterns are detected, the new filter should completely replace the old one
            if old_subset:
                old_subset_upper = old_subset.upper()
                
                # Pattern 1: __source alias (invalid outside EXISTS)
                has_source_alias = '__source' in old_subset.lower()
                
                # Pattern 2: EXISTS subquery (avoid nested EXISTS)
                has_exists = 'EXISTS (' in old_subset_upper or 'EXISTS(' in old_subset_upper
                
                # Pattern 3: Spatial predicates (likely from previous geometric filter)
                spatial_predicates = [
                    'ST_INTERSECTS', 'ST_CONTAINS', 'ST_WITHIN', 'ST_TOUCHES',
                    'ST_OVERLAPS', 'ST_CROSSES', 'ST_DISJOINT', 'ST_EQUALS',
                    'ST_DWITHIN', 'ST_COVERS', 'ST_COVEREDBY'
                ]
                has_spatial_predicate = any(pred in old_subset_upper for pred in spatial_predicates)
                
                # Determine if old_subset should be cleared
                should_clear = has_source_alias or has_exists or has_spatial_predicate
                
                if should_clear:
                    reason = []
                    if has_source_alias:
                        reason.append("__source alias")
                    if has_exists:
                        reason.append("EXISTS subquery")
                    if has_spatial_predicate:
                        reason.append("spatial predicate")
                    
                    logger.warning(f"⚠️ Invalid old subset detected - contains: {', '.join(reason)}")
                    logger.warning(f"  → Invalid subset: '{old_subset[:100]}...'")
                    logger.warning(f"  → This is from a previous geometric filtering operation")
                    old_subset = None  # Clear invalid subset
                    logger.info(f"  → Subset cleared, will apply new filter without combination")
            
            logger.info(f"📋 Préparation du filtre pour {layer.name()}")
            logger.info(f"  → Nouvelle expression: '{expression[:100]}...' ({len(expression)} chars)")
            if old_subset:
                logger.info(f"  → ✓ Subset existant détecté: '{old_subset[:80]}...'")
                logger.info(f"  → Opérateur de combinaison: {combine_operator if combine_operator else 'AND (par défaut)'}")
            else:
                logger.info(f"  → Pas de subset existant (filtre simple)")
            
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
                logger.info(f"  - Subset string applied: {final_expression[:200] if final_expression else '(empty)'}")
                
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
            self.message = "No valid selection mode: no features selected and no expression provided"
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
            # Set error message for user
            source_name = self.source_layer.name() if self.source_layer else 'Unknown'
            self.message = f"Failed to filter source layer '{source_name}'. Check Python console for details."
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
        has_layers_to_filter = self.task_parameters["filtering"]["has_layers_to_filter"]
        has_layers_in_params = len(self.task_parameters['task'].get('layers', [])) > 0
        
        logger.info(f"\n🔍 Checking if distant layers should be filtered...")
        logger.info(f"  has_geometric_predicates: {has_geom_predicates}")
        logger.info(f"  has_layers_to_filter: {has_layers_to_filter}")
        logger.info(f"  has_layers_in_params: {has_layers_in_params}")
        logger.info(f"  self.layers_count: {self.layers_count}")
        logger.info(f"  task['layers'] content: {[l.get('layer_name', 'unknown') for l in self.task_parameters['task'].get('layers', [])]}")
        logger.info(f"  self.layers content: {list(self.layers.keys())} with {sum(len(v) for v in self.layers.values())} total layers")
        
        # Process if geometric predicates enabled AND (has_layers_to_filter OR layers in params) AND layers were organized
        if has_geom_predicates and (has_layers_to_filter or has_layers_in_params) and self.layers_count > 0:
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
                    self.message = "Filter task was canceled by user"
                    return False
                
                if result is False:
                    logger.error("=" * 60)
                    logger.error("✗ PARTIAL SUCCESS: Source OK, but distant layers FAILED")
                    logger.error("=" * 60)
                    logger.warning("  → Source layer remains filtered")
                    logger.warning("  → Check logs for distant layer errors")
                    self.message = "Source layer filtered, but some distant layers failed. Check Python console for details."
                    return False
                
                logger.info("=" * 60)
                logger.info("✓ COMPLETE SUCCESS: All layers filtered")
                logger.info("=" * 60)
            else:
                logger.info("  → No geometric predicates configured")
                logger.info("  → Only source layer filtered")
        else:
            # Log detailed reason why geometric filtering is skipped
            if not has_geom_predicates:
                logger.info("  → Geometric predicates not enabled (has_geometric_predicates=False)")
            if not has_layers_to_filter and not has_layers_in_params:
                logger.info("  → No layers to filter (has_layers_to_filter=False AND no layers in params)")
            if self.layers_count == 0:
                logger.info("  → No layers organized for filtering (layers_count=0)")
            logger.info("  → Only source layer filtered")

        return result 
     

    def execute_unfiltering(self):
        """
        Remove all filters from source layer and selected remote layers.
        
        This clears filters completely (sets subsetString to empty) for:
        - The current/source layer
        - All selected remote layers (layers_to_filter)
        
        NOTE: This is different from undo - it removes filters entirely rather than
        restoring previous filter state. Use undo button for history navigation.
        """
        logger.info("FilterMate: Clearing all filters on source and selected layers")
        
        # Clear filter on source layer
        safe_set_subset_string(self.source_layer, '')
        logger.info(f"FilterMate: Cleared filter on source layer {self.source_layer.name()}")
        
        # Clear filters on all selected associated layers
        i = 1
        self.setProgress((i/self.layers_count)*100)
        
        for layer_provider_type in self.layers:
            for layer, layer_props in self.layers[layer_provider_type]:
                safe_set_subset_string(layer, '')
                logger.info(f"FilterMate: Cleared filter on layer {layer.name()}")
                i += 1
                self.setProgress((i/self.layers_count)*100)
                if self.isCanceled():
                    return False
        
        logger.info(f"FilterMate: Successfully cleared filters on {self.layers_count} layer(s)")
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
            datatype: Export format (e.g., 'SHP', 'GPKG', 'GEOJSON')
            style_format: Style file format or None
            save_styles: Whether to save layer styles
            
        Returns:
            bool: True if successful
        """
        current_projection = projection if projection else layer.sourceCrs()
        
        # Map short datatype names to QGIS driver names
        driver_map = {
            'GPKG': 'GPKG',
            'SHP': 'ESRI Shapefile',
            'SHAPEFILE': 'ESRI Shapefile',
            'ESRI SHAPEFILE': 'ESRI Shapefile',
            'GEOJSON': 'GeoJSON',
            'JSON': 'GeoJSON',
            'GML': 'GML',
            'KML': 'KML',
            'CSV': 'CSV',
            'XLSX': 'XLSX',
            'TAB': 'MapInfo File',
            'MAPINFO': 'MapInfo File',
            'DXF': 'DXF',
            'SQLITE': 'SQLite',
            'SPATIALITE': 'SpatiaLite'
        }
        driver_name = driver_map.get(datatype.upper(), datatype)
        
        logger.debug(f"Exporting layer '{layer.name()}' to {output_path} (driver: {driver_name})")
        
        try:
            result = QgsVectorFileWriter.writeAsVectorFormat(
                layer,
                os.path.normcase(output_path),
                "UTF-8",
                current_projection,
                driver_name
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
            
            # Determine file extension based on datatype
            extension_map = {
                'GPKG': '.gpkg',
                'SHP': '.shp',
                'SHAPEFILE': '.shp',
                'ESRI SHAPEFILE': '.shp',
                'GEOJSON': '.geojson',
                'JSON': '.geojson',
                'GML': '.gml',
                'KML': '.kml',
                'CSV': '.csv',
                'XLSX': '.xlsx',
                'TAB': '.tab',
                'MAPINFO': '.tab',
                'DXF': '.dxf',
                'SQLITE': '.sqlite',
                'SPATIALITE': '.sqlite'
            }
            file_extension = extension_map.get(datatype.upper(), f'.{datatype.lower()}')
            
            # Sanitize filename to handle special characters like em-dash (—)
            safe_filename = sanitize_filename(layer_name)
            output_path = os.path.join(output_folder, f"{safe_filename}{file_extension}")
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
            
            # Determine file extension based on datatype
            extension_map = {
                'GPKG': '.gpkg',
                'SHP': '.shp',
                'SHAPEFILE': '.shp',
                'ESRI SHAPEFILE': '.shp',
                'GEOJSON': '.geojson',
                'JSON': '.geojson',
                'GML': '.gml',
                'KML': '.kml',
                'CSV': '.csv',
                'XLSX': '.xlsx',
                'TAB': '.tab',
                'MAPINFO': '.tab',
                'DXF': '.dxf',
                'SQLITE': '.sqlite',
                'SPATIALITE': '.sqlite'
            }
            file_extension = extension_map.get(datatype.upper(), f'.{datatype.lower()}')
            
            # Build output path for this layer
            # Sanitize filename to handle special characters like em-dash (—)
            safe_filename = sanitize_filename(layer_name)
            output_path = os.path.join(output_folder, f"{safe_filename}{file_extension}")
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
            
            # Sanitize filename to handle special characters like em-dash (—)
            safe_filename = sanitize_filename(layer_name)
            
            # Determine file extension based on datatype
            extension_map = {
                'GPKG': '.gpkg',
                'SHP': '.shp',
                'SHAPEFILE': '.shp',
                'ESRI SHAPEFILE': '.shp',
                'GEOJSON': '.geojson',
                'JSON': '.geojson',
                'GML': '.gml',
                'KML': '.kml',
                'CSV': '.csv',
                'XLSX': '.xlsx',
                'TAB': '.tab',
                'MAPINFO': '.tab',
                'DXF': '.dxf',
                'SQLITE': '.sqlite',
                'SPATIALITE': '.sqlite'
            }
            file_extension = extension_map.get(datatype.upper(), f'.{datatype.lower()}')
            
            # Create temporary directory for this layer's export
            import tempfile
            temp_dir = tempfile.mkdtemp(prefix=f"fm_batch_{safe_filename}_")
            
            try:
                # Export layer to temporary directory
                temp_output = os.path.join(temp_dir, f"{safe_filename}{file_extension}")
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
                zip_path = os.path.join(output_folder, f"{safe_filename}.zip")
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
        - Streaming export for large datasets (Phase 4 optimization)
        
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
        
        # Check streaming export configuration
        streaming_config = self.task_parameters.get('config', {}).get('APP', {}).get('OPTIONS', {}).get('STREAMING_EXPORT', {})
        streaming_enabled = streaming_config.get('enabled', {}).get('value', True)
        feature_threshold = streaming_config.get('feature_threshold', {}).get('value', 10000)
        chunk_size = streaming_config.get('chunk_size', {}).get('value', 5000)
        
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
        
        # GPKG STANDARD MODE: Always use qgis:package for single file with all layers and styles
        # This takes priority over streaming to ensure proper GeoPackage structure
        if datatype == 'GPKG':
            # GeoPackage export using processing - create single file with all layers and styles
            # Determine GPKG output path
            if output_folder.lower().endswith('.gpkg'):
                # User selected a file path (via save dialog)
                gpkg_output_path = output_folder
                # Ensure parent directory exists
                gpkg_dir = os.path.dirname(gpkg_output_path)
                if gpkg_dir and not os.path.exists(gpkg_dir):
                    try:
                        os.makedirs(gpkg_dir)
                        logger.info(f"Created output directory: {gpkg_dir}")
                    except Exception as e:
                        logger.error(f"Failed to create output directory: {e}")
                        self.message = f'Failed to create output directory: {gpkg_dir}'
                        return False
            else:
                # output_folder is a directory - construct default GPKG filename
                if not os.path.exists(output_folder):
                    try:
                        os.makedirs(output_folder)
                        logger.info(f"Created output directory: {output_folder}")
                    except Exception as e:
                        logger.error(f"Failed to create output directory: {e}")
                        self.message = f'Failed to create output directory: {output_folder}'
                        return False
                # Default filename: use project name or "export"
                project_title = self.PROJECT.title() if self.PROJECT.title() else None
                project_basename = self.PROJECT.baseName() if self.PROJECT.baseName() else None
                default_name = project_title or project_basename or 'export'
                # Sanitize filename
                default_name = sanitize_filename(default_name)
                gpkg_output_path = os.path.join(output_folder, f"{default_name}.gpkg")
                logger.info(f"GPKG output path constructed: {gpkg_output_path}")
            
            export_success = self._export_to_gpkg(layers, gpkg_output_path, save_styles)
            
            if not export_success:
                self.message = 'GPKG export failed'
                return False
            
            # Build success message with file path
            self.message = f'Layer(s) exported to <a href="file:///{gpkg_output_path}">{gpkg_output_path}</a>'
            
            # Create zip archive if requested
            if zip_path:
                # For GPKG, zip the single file
                gpkg_dir = os.path.dirname(gpkg_output_path)
                zip_created = self._create_zip_archive(zip_path, gpkg_dir)
                if zip_created:
                    self.message += f' and Zip file has been exported to <a href="file:///{zip_path}">{zip_path}</a>'
            
            return True
        
        # STANDARD MODE: Check if streaming should be used for large layers (non-GPKG formats only)
        if streaming_enabled:
            # Check total feature count across all layers
            total_features = self._calculate_total_features(layers)
            if total_features >= feature_threshold:
                logger.info(f"🚀 Using STREAMING export mode ({total_features} features >= {feature_threshold} threshold)")
                export_success = self._export_with_streaming(
                    layers, output_folder, projection, datatype, style_format, save_styles, chunk_size
                )
                if export_success:
                    self.message = f'Streaming export: {len(layers)} layer(s) ({total_features} features) exported to <a href="file:///{output_folder}">{output_folder}</a>'
                elif not self.message:
                    # Only set generic message if _export_with_streaming didn't set a detailed one
                    self.message = f'Streaming export failed for {len(layers)} layer(s)'
                
                # Create zip if requested
                if export_success and zip_path:
                    zip_created = self._create_zip_archive(zip_path, output_folder)
                    if zip_created:
                        self.message += f' and Zip file has been exported to <a href="file:///{zip_path}">{zip_path}</a>'
                
                return export_success
        
        # STANDARD MODE: Other formats (Shapefile, GeoJSON, etc.)
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

    def _calculate_total_features(self, layers) -> int:
        """
        Calculate total feature count across all layers.
        
        Args:
            layers: List of layer info dicts or layer names
        
        Returns:
            int: Total feature count
        """
        total = 0
        for layer_info in layers:
            layer_name = layer_info['layer_name'] if isinstance(layer_info, dict) else layer_info
            layer = self._get_layer_by_name(layer_name)
            if layer:
                total += layer.featureCount()
        return total
    
    def _export_with_streaming(self, layers, output_folder, projection, datatype, style_format, save_styles, chunk_size):
        """
        Export layers using streaming for large datasets.
        
        Args:
            layers: List of layer info dicts or layer names
            output_folder: Output directory path
            projection: Target CRS
            datatype: Output format (GPKG, SHP, etc.)
            style_format: Style format (QML, SLD, etc.)
            save_styles: Whether to save styles
            chunk_size: Number of features per batch
        
        Returns:
            bool: True if export successful
        """
        try:
            # Note: StreamingConfig uses batch_size, not chunk_size
            config = StreamingConfig(batch_size=chunk_size)
            exporter = StreamingExporter(config)
            
            # Map datatype to format string expected by StreamingExporter
            format_map = {
                'GPKG': 'gpkg',
                'SHP': 'shp',
                'GEOJSON': 'geojson',
                'GML': 'gml',
                'KML': 'kml',
                'CSV': 'csv'
            }
            export_format = format_map.get(datatype.upper(), datatype.lower())
            
            # Ensure output folder exists
            if not os.path.exists(output_folder):
                try:
                    os.makedirs(output_folder)
                    logger.info(f"Created output folder: {output_folder}")
                except OSError as e:
                    error_msg = f"Cannot create output folder '{output_folder}': {e}"
                    logger.error(error_msg)
                    self.message = error_msg
                    return False
            
            # Progress callback - ExportProgress uses percent_complete, not percentage
            def progress_callback(progress):
                self.setProgress(int(progress.percent_complete))
                self.setDescription(f"Streaming export: {progress.features_processed}/{progress.total_features} features")
            
            exported_count = 0
            failed_layers = []
            
            for layer_info in layers:
                layer_name = layer_info['layer_name'] if isinstance(layer_info, dict) else layer_info
                layer = self._get_layer_by_name(layer_name)
                
                if not layer:
                    logger.warning(f"Layer not found: {layer_name}")
                    failed_layers.append(f"{layer_name} (not found)")
                    continue
                
                # Determine output path
                if datatype == 'GPKG':
                    output_path = os.path.join(output_folder, f"{layer_name}.gpkg")
                elif datatype == 'SHP':
                    output_path = os.path.join(output_folder, f"{layer_name}.shp")
                elif datatype == 'GEOJSON':
                    output_path = os.path.join(output_folder, f"{layer_name}.geojson")
                else:
                    output_path = os.path.join(output_folder, f"{layer_name}.{datatype.lower()}")
                
                logger.info(f"Streaming export: {layer_name} → {output_path}")
                
                # StreamingExporter.export_layer_streaming expects:
                # source_layer (not layer), format (not target_crs)
                # and returns a dict with 'success' key
                result = exporter.export_layer_streaming(
                    source_layer=layer,
                    output_path=output_path,
                    format=export_format,
                    progress_callback=progress_callback,
                    cancel_check=self.isCanceled
                )
                
                # Check the 'success' key in the returned dict
                if not result.get('success', False):
                    error_msg = result.get('error', 'Unknown error')
                    logger.error(f"Streaming export failed for {layer_name}: {error_msg}")
                    failed_layers.append(f"{layer_name} ({error_msg})")
                    continue
                
                exported_count += 1
                
                # Save styles if requested
                if save_styles and style_format:
                    self._save_layer_style(layer, output_path, style_format, datatype)
                
                if self.isCanceled():
                    logger.info("Export cancelled by user")
                    self.message = "Export cancelled by user"
                    return False
            
            # Check results
            if failed_layers:
                if exported_count > 0:
                    self.message = f"Partial export: {exported_count}/{len(layers)} layers exported. Failed: {', '.join(failed_layers[:3])}"
                    if len(failed_layers) > 3:
                        self.message += f" and {len(failed_layers) - 3} more"
                    logger.warning(self.message)
                    return True  # Partial success
                else:
                    self.message = f"Export failed for all {len(layers)} layers. Errors: {', '.join(failed_layers[:3])}"
                    if len(failed_layers) > 3:
                        self.message += f" and {len(failed_layers) - 3} more"
                    logger.error(self.message)
                    return False
            
            return True
            
        except Exception as e:
            error_msg = f"Streaming export error: {e}"
            logger.error(error_msg)
            self.message = error_msg
            return False

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
        # Use sanitize_sql_identifier to handle all special chars (em-dash, etc.)
        name = sanitize_sql_identifier(layer.id().replace(layer_name, ''))
        
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


    def _ensure_source_table_stats(self, connexion, schema, table, geom_field):
        """
        Ensure PostgreSQL statistics exist for source table geometry column.
        
        Checks pg_stats for geometry column statistics and runs ANALYZE if missing.
        This prevents "stats for X.geom do not exist" warnings from PostgreSQL
        query planner.
        
        Args:
            connexion: psycopg2 connection
            schema: Table schema name
            table: Table name
            geom_field: Geometry column name
            
        Returns:
            bool: True if stats exist or were created, False on error
        """
        try:
            with connexion.cursor() as cursor:
                # Check if stats exist for geometry column
                cursor.execute("""
                    SELECT COUNT(*) FROM pg_stats 
                    WHERE schemaname = %s 
                    AND tablename = %s 
                    AND attname = %s;
                """, (schema, table, geom_field))
                
                result = cursor.fetchone()
                has_stats = result[0] > 0 if result else False
                
                if not has_stats:
                    logger.info(f"Running ANALYZE on source table \"{schema}\".\"{table}\" (missing stats for {geom_field})")
                    cursor.execute(f'ANALYZE "{schema}"."{table}";')
                    connexion.commit()
                    logger.debug(f"ANALYZE completed for \"{schema}\".\"{table}\"")
                
                return True
                
        except Exception as e:
            logger.warning(f"Could not check/create stats for \"{schema}\".\"{table}\": {e}")
            return False


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
        
        Adapts filtering strategy based on dataset size:
        - Small datasets (< 10k features): Uses direct setSubsetString for simplicity
        - Large datasets (≥ 10k features): Uses materialized views for performance
        - Custom buffer expressions: Always uses materialized views
        
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
        # Get feature count to determine strategy
        feature_count = layer.featureCount()
        
        # Threshold for using materialized views (10,000 features)
        MATERIALIZED_VIEW_THRESHOLD = 10000
        
        # Decide on strategy based on dataset size and filter type
        # Custom buffer filters always need materialized views for geometry operations
        use_materialized_view = custom or feature_count >= MATERIALIZED_VIEW_THRESHOLD
        
        if use_materialized_view:
            # Log strategy decision
            if custom:
                logger.info(f"PostgreSQL: Using materialized views for custom buffer expression")
            elif feature_count >= 100000:
                logger.info(
                    f"PostgreSQL: Very large dataset ({feature_count:,} features). "
                    f"Using materialized views with spatial index for optimal performance."
                )
            else:
                logger.info(
                    f"PostgreSQL: Large dataset ({feature_count:,} features ≥ {MATERIALIZED_VIEW_THRESHOLD:,}). "
                    f"Using materialized views for better performance."
                )
            
            return self._filter_action_postgresql_materialized(
                layer, sql_subset_string, primary_key_name, geom_key_name, 
                name, custom, cur, conn, seq_order
            )
        else:
            # Small dataset - use direct setSubsetString
            logger.info(
                f"PostgreSQL: Small dataset ({feature_count:,} features < {MATERIALIZED_VIEW_THRESHOLD:,}). "
                f"Using direct setSubsetString for simplicity."
            )
            
            return self._filter_action_postgresql_direct(
                layer, sql_subset_string, primary_key_name, cur, conn, seq_order
            )
    
    
    def _filter_action_postgresql_direct(self, layer, sql_subset_string, primary_key_name, cur, conn, seq_order):
        """
        Execute PostgreSQL filter using direct setSubsetString (for small datasets).
        
        This method is simpler and faster for small datasets because it:
        - Avoids creating/dropping materialized views
        - Avoids creating spatial indexes
        - Uses PostgreSQL's query optimizer directly
        
        Args:
            layer: QgsVectorLayer to filter
            sql_subset_string: SQL SELECT statement
            primary_key_name: Primary key field name
            cur: Database cursor
            conn: Database connection
            seq_order: Sequence order number
            
        Returns:
            bool: True if successful
        """
        import time
        start_time = time.time()
        
        # Ensure source table has statistics for query optimization
        connexion = self.task_parameters["task"]["options"]["ACTIVE_POSTGRESQL"]
        self._ensure_source_table_stats(
            connexion, 
            self.param_source_schema, 
            self.param_source_table, 
            self.param_source_geom
        )
        
        try:
            # Extract WHERE clause from SELECT statement
            # sql_subset_string format: SELECT * FROM "schema"."table" WHERE condition
            where_clause = self._extract_where_clause_from_select(sql_subset_string)
            
            if where_clause:
                # Get existing subset to preserve filter chain
                old_subset = layer.subsetString()
                
                if old_subset:
                    # CRITICAL FIX: Check for invalid old_subset patterns that should NOT be combined
                    # These patterns indicate a previous geometric filter that should be replaced
                    old_subset_upper = old_subset.upper()
                    
                    # Pattern 1: __source alias (only valid inside EXISTS subqueries)
                    has_source_alias = '__source' in old_subset.lower()
                    
                    # Pattern 2: EXISTS subquery (avoid nested EXISTS)
                    has_exists = 'EXISTS (' in old_subset_upper or 'EXISTS(' in old_subset_upper
                    
                    # Pattern 3: Spatial predicates (likely from previous geometric filter)
                    spatial_predicates = [
                        'ST_INTERSECTS', 'ST_CONTAINS', 'ST_WITHIN', 'ST_TOUCHES',
                        'ST_OVERLAPS', 'ST_CROSSES', 'ST_DISJOINT', 'ST_EQUALS',
                        'ST_DWITHIN', 'ST_COVERS', 'ST_COVEREDBY'
                    ]
                    has_spatial_predicate = any(pred in old_subset_upper for pred in spatial_predicates)
                    
                    # If old_subset contains geometric filter patterns, replace instead of combine
                    if has_source_alias or has_exists or has_spatial_predicate:
                        final_expression = where_clause
                        logger.info(f"Old subset contains geometric filter patterns - replacing instead of combining")
                    else:
                        # Check if the new filter is identical to the old one to avoid duplication
                        # Normalize both expressions for comparison (remove extra spaces/parentheses)
                        normalized_old = old_subset.strip().strip('()')
                        normalized_new = where_clause.strip().strip('()')
                        
                        if normalized_old == normalized_new:
                            # Identical filter - no need to combine, just use the new one
                            final_expression = where_clause
                            logger.debug(f"New filter identical to existing - replacing instead of combining")
                        else:
                            # Different filters - combine with existing filter using AND
                            final_expression = f"({old_subset}) AND ({where_clause})"
                            logger.debug(f"Combining with existing filter: {old_subset[:50]}...")
                else:
                    final_expression = where_clause
                
                logger.debug(f"Direct filter expression: {final_expression[:200]}...")
                
                # Apply filter directly
                result = safe_set_subset_string(layer, final_expression)
                
                if result:
                    elapsed = time.time() - start_time
                    feature_count = layer.featureCount()
                    logger.info(
                        f"Direct PostgreSQL filter applied in {elapsed:.3f}s. "
                        f"{feature_count} features match."
                    )
                    
                    # Insert history
                    self._insert_subset_history(cur, conn, layer, sql_subset_string, seq_order)
                    return True
                else:
                    logger.error(f"Failed to apply direct filter to {layer.name()}")
                    return False
            else:
                logger.warning(f"Could not extract WHERE clause from: {sql_subset_string[:100]}...")
                # Fallback to materialized view approach
                logger.info("Falling back to materialized view approach")
                return self._filter_action_postgresql_materialized(
                    layer, sql_subset_string, primary_key_name, None, 
                    layer.name(), False, cur, conn, seq_order
                )
                
        except Exception as e:
            logger.error(f"Error applying direct PostgreSQL filter: {str(e)}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return False
    
    
    def _extract_where_clause_from_select(self, sql_select):
        """
        Extract WHERE clause from a SQL SELECT statement.
        
        Args:
            sql_select: SQL SELECT statement (e.g., 'SELECT * FROM "schema"."table" WHERE condition')
            
        Returns:
            str: WHERE clause condition, or None if not found
        """
        import re
        
        # Find WHERE clause (case-insensitive)
        match = re.search(r'\bWHERE\b\s+(.+?)(?:\s+ORDER\s+BY|\s+LIMIT|\s+GROUP\s+BY|\s*$)', 
                         sql_select, re.IGNORECASE | re.DOTALL)
        
        if match:
            where_clause = match.group(1).strip()
            # Remove trailing semicolon if present
            where_clause = where_clause.rstrip(';').strip()
            return where_clause
        
        return None
    
    
    def _filter_action_postgresql_materialized(self, layer, sql_subset_string, primary_key_name, geom_key_name, name, custom, cur, conn, seq_order):
        """
        Execute PostgreSQL filter using materialized views (for large datasets or custom buffers).
        
        This method provides optimal performance for large datasets by:
        - Creating indexed materialized views on the server
        - Using GIST spatial indexes for fast spatial queries
        - Clustering data for sequential read optimization
        
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
        import time
        start_time = time.time()
        
        schema = self.current_materialized_view_schema
        
        # Ensure source table has statistics for query optimization
        connexion = self.task_parameters["task"]["options"]["ACTIVE_POSTGRESQL"]
        self._ensure_source_table_stats(
            connexion, 
            self.param_source_schema, 
            self.param_source_table, 
            geom_key_name
        )
        
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
            # CRITICAL FIX: Handle None buffer expression
            if self.param_buffer_expression:
                self.where_clause = self.param_buffer_expression.replace('CASE', '').replace('END', '').replace('IF', '').replace('ELSE', '').replace('\r', ' ').replace('\n', ' ')
                where_clauses = self._parse_where_clauses()
                where_clause_fields_arr = [clause.split(' ')[0] for clause in where_clauses]
            else:
                logger.warning("Custom buffer requested but param_buffer_expression is None, using simple view")
                self.where_clause = ""
                where_clause_fields_arr = []
            
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
        
        elapsed = time.time() - start_time
        feature_count = layer.featureCount()
        logger.info(
            f"Materialized view created and filter applied in {elapsed:.2f}s. "
            f"{feature_count} features match."
        )
        
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



    def _cleanup_postgresql_materialized_views(self):
        """
        Cleanup PostgreSQL materialized views created during filtering.
        This prevents accumulation of temporary MVs in the database.
        """
        if not POSTGRESQL_AVAILABLE:
            return
        
        try:
            # Only cleanup if source layer is PostgreSQL
            if self.param_source_provider_type != 'postgresql':
                return
            
            # Get source layer from task parameters
            source_layer = None
            if 'source_layer' in self.task_parameters:
                source_layer = self.task_parameters['source_layer']
            elif hasattr(self, 'source_layer') and self.source_layer:
                source_layer = self.source_layer
            
            if not source_layer:
                logger.debug("No source layer available for PostgreSQL MV cleanup")
                return
            
            # Import backend and perform cleanup
            from ..backends.postgresql_backend import PostgreSQLGeometricFilter
            
            backend = PostgreSQLGeometricFilter(self.task_parameters)
            success = backend.cleanup_materialized_views(source_layer)
            
            if success:
                logger.debug("PostgreSQL materialized views cleaned up successfully")
            else:
                logger.debug("PostgreSQL MV cleanup completed with warnings")
                
        except Exception as e:
            # Non-critical error - log but don't fail the task
            logger.debug(f"Error during PostgreSQL MV cleanup: {e}")
    
    def cancel(self):
        """Cancel task and cleanup all active database connections"""
        # Cleanup PostgreSQL materialized views before closing connections
        self._cleanup_postgresql_materialized_views()
        
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
        
        # Cleanup PostgreSQL materialized views (critical for preventing accumulation)
        self._cleanup_postgresql_materialized_views()

        if self.exception is None:
            if result is None:
                # Task was likely canceled by user - log only, no message bar notification
                logger.info('Task completed with no result (likely canceled by user)')
            elif result is False:
                # Task failed without exception - display error message
                error_msg = self.message if hasattr(self, 'message') and self.message else 'Task failed'
                logger.error(f"Task finished with failure: {error_msg}")
                iface.messageBar().pushMessage(
                    message_category,
                    error_msg,
                    Qgis.Critical)
            else:
                # Task succeeded
                if message_category == 'FilterLayers':

                    if self.task_action == 'filter':
                        result_action = 'Layer(s) filtered'
                    elif self.task_action == 'unfilter':
                        result_action = 'Layer(s) filtered to precedent state'
                    elif self.task_action == 'reset':
                        result_action = 'Layer(s) unfiltered'
                    
                    iface.messageBar().pushMessage(
                        message_category,
                        f'Filter task : {result_action}',
                        Qgis.Success)

                elif message_category == 'ExportLayers':

                    if self.task_action == 'export':
                        iface.messageBar().pushMessage(
                            message_category,
                            f'Export task : {self.message}',
                            Qgis.Success)
                        
        else:
            # Exception occurred during task execution
            error_msg = f"Exception: {self.exception}"
            logger.error(f"Task finished with exception: {error_msg}")
            
            # Display error to user
            iface.messageBar().pushMessage(
                message_category,
                error_msg,
                Qgis.Critical)
            
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






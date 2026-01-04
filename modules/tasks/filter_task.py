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

# Import PostgreSQL availability flags from centralized appUtils
# POSTGRESQL_AVAILABLE = True (always, QGIS native support)
# PSYCOPG2_AVAILABLE = depends on psycopg2 import (for advanced features)
from ..appUtils import POSTGRESQL_AVAILABLE, PSYCOPG2_AVAILABLE
try:
    import psycopg2
except ImportError:
    psycopg2 = None

# Import constants
from ..constants import (
    PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR, PROVIDER_MEMORY,
    PREDICATE_INTERSECTS, PREDICATE_WITHIN, PREDICATE_CONTAINS,
    PREDICATE_OVERLAPS, PREDICATE_CROSSES, PREDICATE_TOUCHES,
    PREDICATE_DISJOINT, PREDICATE_EQUALS,
    get_provider_name, should_warn_performance,
    LONG_QUERY_WARNING_THRESHOLD, VERY_LONG_QUERY_WARNING_THRESHOLD
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
    needs_metric_conversion,
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
    safe_buffer_metric,
    safe_buffer_with_crs_check,
    safe_unary_union,
    safe_collect_geometry,
    safe_convert_to_multi_polygon,
    extract_polygons_from_collection,
    repair_geometry,
    get_geometry_type_name,
    create_geos_safe_layer
)

# Import CRS utilities (v2.5.7 - improved CRS compatibility)
try:
    from ..crs_utils import (
        is_geographic_crs,
        is_metric_crs,
        get_optimal_metric_crs,
        CRSTransformer,
        create_metric_buffer,
        get_crs_units,
        get_layer_crs_info
    )
    CRS_UTILS_AVAILABLE = True
except ImportError:
    CRS_UTILS_AVAILABLE = False
    logger.warning("crs_utils module not available - using legacy CRS handling")

# Import geometry cache (Phase 3a extraction)
from .geometry_cache import SourceGeometryCache

# Import query expression cache (Phase 4 optimization)
from .query_cache import QueryExpressionCache, get_query_cache

# Import parallel executor (Phase 4 optimization)
from .parallel_executor import ParallelFilterExecutor, ParallelConfig

# Import streaming exporter (Phase 4 optimization)
from .result_streaming import StreamingExporter, StreamingConfig

# Import combined query optimizer (Phase 5 optimization - v2.8.0)
from .combined_query_optimizer import get_combined_query_optimizer, optimize_combined_filter

class FilterEngineTask(QgsTask):
    """Main QgsTask class which filter and unfilter data"""
    
    # Signal to apply subset string on main thread (THREAD SAFETY FIX v2.3.21)
    # setSubsetString is NOT thread-safe and MUST be called from the main Qt thread.
    # This signal allows background tasks to request filter application on the main thread.
    applySubsetRequest = pyqtSignal(QgsVectorLayer, str)
    
    # Cache de classe (partagé entre toutes les instances de FilterEngineTask)
    # Lazy initialization to avoid import-time errors with logging
    _geometry_cache = None
    
    # Cache d'expressions (partagé entre toutes les instances)
    _expression_cache = None  # Initialized lazily via get_query_cache()
    
    @classmethod
    def get_geometry_cache(cls):
        """Get or create the geometry cache (lazy initialization)."""
        if cls._geometry_cache is None:
            cls._geometry_cache = SourceGeometryCache()
        return cls._geometry_cache

    def __init__(self, description, task_action, task_parameters):

        QgsTask.__init__(self, description, QgsTask.CanCancel)

        self.exception = None
        self.task_action = task_action
        self.task_parameters = task_parameters
        
        # THREAD SAFETY FIX v2.5.6: Store warnings from worker thread for display in finished()
        # Cannot call iface.messageBar() from worker thread - would cause crash
        self.warning_messages = []
        
        # Référence au cache partagé (lazy initialization)
        self.geom_cache = FilterEngineTask.get_geometry_cache()
        
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
        self.param_buffer_segments = 5  # Default: 5 segments for buffer precision
        self.param_use_centroids_source_layer = False  # Use centroids for source layer geometries
        self.param_use_centroids_distant_layers = False  # Use centroids for distant layer geometries
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
        
        # Session ID for multi-client materialized view isolation
        # Retrieved from task_parameters, defaults to 'default' for backward compatibility
        self.session_id = None  # Will be set in run() from task_parameters
        
        # Track active database connections for cleanup on cancellation
        self.active_connections = []
        
        # THREAD SAFETY FIX v2.3.21: Store subset string requests to apply on main thread
        # Instead of calling setSubsetString directly from background thread (which causes
        # access violations), we store the requests and emit applySubsetRequest signal
        # after the task completes. The signal is connected with Qt.QueuedConnection
        # to ensure setSubsetString is called on the main thread.
        self._pending_subset_requests = []
        
        # Prepared statements manager (initialized when DB connection is established)
        self._ps_manager = None

    def queue_subset_request(self, layer, expression):
        """
        Queue a subset string request to be applied on the main thread.
        
        THREAD SAFETY FIX v2.3.21:
        setSubsetString() is NOT thread-safe and MUST be called from the main Qt thread.
        Instead of calling it directly from run() (background thread), we store the
        request and apply it in finished() which runs on the main thread.
        
        Args:
            layer: QgsVectorLayer to apply the filter to
            expression: Subset string expression to apply
            
        Note:
            The actual application happens in finished() after run() completes.
            This ensures all filters are applied atomically from the main thread.
        """
        if layer and expression is not None:
            self._pending_subset_requests.append((layer, expression))
            expr_preview = (expression[:60] + '...') if len(expression) > 60 else expression
            logger.debug(f"📥 Queued subset request for {layer.name()}: {expr_preview}")
        else:
            logger.warning(f"⚠️ queue_subset_request called with invalid params: layer={layer}, expression={expression is not None}")
        return True  # Return True to indicate success (actual application is deferred)
    
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

    def _get_valid_postgresql_connection(self):
        """
        Get a valid PostgreSQL connection for the current task.
        
        Checks if ACTIVE_POSTGRESQL in task_parameters contains a valid psycopg2 
        connection object. If not (e.g., it's a string or None), attempts to 
        obtain a fresh connection from the source layer.
        
        Returns:
            psycopg2.connection: Valid PostgreSQL connection object
            
        Raises:
            Exception: If no valid connection can be established
        """
        # Try to get connection from task parameters
        connexion = self.task_parameters.get("task", {}).get("options", {}).get("ACTIVE_POSTGRESQL")
        
        # Validate that it's actually a connection object, not a string or None
        if connexion is not None and not isinstance(connexion, str):
            try:
                # Check if connection has cursor method (duck typing for psycopg2 connection)
                if hasattr(connexion, 'cursor') and callable(getattr(connexion, 'cursor')):
                    # Also check if connection is not closed
                    if not getattr(connexion, 'closed', True):
                        return connexion
                    else:
                        logger.warning("ACTIVE_POSTGRESQL connection is closed, will obtain new connection")
            except Exception as e:
                logger.warning(f"Error checking ACTIVE_POSTGRESQL connection: {e}")
        
        # Connection is invalid (string, None, or closed) - try to get fresh connection from source layer
        logger.info("ACTIVE_POSTGRESQL is not a valid connection object, obtaining fresh connection from source layer")
        
        if hasattr(self, 'source_layer') and self.source_layer is not None:
            try:
                connexion, source_uri = get_datasource_connexion_from_layer(self.source_layer)
                if connexion is not None:
                    # Track this connection for cleanup
                    self.active_connections.append(connexion)
                    return connexion
            except Exception as e:
                logger.error(f"Failed to get connection from source layer: {e}")
        
        # Last resort: try from infos layer_id
        try:
            layer_id = self.task_parameters.get("infos", {}).get("layer_id")
            if layer_id:
                layer = self.PROJECT.mapLayer(layer_id)
                if layer and layer.providerType() == 'postgres':
                    connexion, source_uri = get_datasource_connexion_from_layer(layer)
                    if connexion is not None:
                        self.active_connections.append(connexion)
                        return connexion
        except Exception as e:
            logger.error(f"Failed to get connection from layer by ID: {e}")
        
        raise Exception(
            "No valid PostgreSQL connection available. "
            "ACTIVE_POSTGRESQL was not a valid connection object and could not obtain fresh connection from layer."
        )

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
        
        IMPROVED v2.5.7: Uses crs_utils module for better CRS detection and
        optimal metric CRS selection (including UTM zones).
        
        Sets has_to_reproject_source_layer flag and updates source_layer_crs_authid
        if the source CRS is geographic or non-metric.
        """
        # Use crs_utils if available for better CRS handling
        if CRS_UTILS_AVAILABLE:
            is_non_metric = is_geographic_crs(self.source_crs) or not is_metric_crs(self.source_crs)
            
            if is_non_metric:
                self.has_to_reproject_source_layer = True
                
                # Get optimal metric CRS using layer extent for better accuracy
                layer_extent = self.source_layer.extent() if self.source_layer else None
                self.source_layer_crs_authid = get_optimal_metric_crs(
                    project=self.PROJECT,
                    source_crs=self.source_crs,
                    extent=layer_extent,
                    prefer_utm=True
                )
                
                # Log CRS conversion info
                crs_info = get_layer_crs_info(self.source_layer)
                logger.info(
                    f"Source layer CRS: {crs_info.get('authid', 'unknown')} "
                    f"(units: {crs_info.get('units', 'unknown')}, "
                    f"geographic: {crs_info.get('is_geographic', False)})"
                )
                logger.info(
                    f"Source layer will be reprojected to {self.source_layer_crs_authid} "
                    "for metric calculations"
                )
            else:
                logger.info(f"Source layer CRS is already metric: {self.source_layer_crs_authid}")
        else:
            # Legacy CRS handling (fallback)
            source_crs_distance_unit = self.source_crs.mapUnits()
            
            is_non_metric = (
                source_crs_distance_unit in ['DistanceUnit.Degrees', 'DistanceUnit.Unknown'] 
                or self.source_crs.isGeographic()
            )
            
            if is_non_metric:
                self.has_to_reproject_source_layer = True
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
        for layer_props_original in self.task_parameters["task"]["layers"]:
            # CRITICAL FIX v2.7.8: Create a COPY of layer_props to avoid modifying
            # the original dict in self.PROJECT_LAYERS. Without this, modifications
            # like _effective_provider_type and _postgresql_fallback persist between
            # filter executions, causing PostgreSQL layers to incorrectly use OGR backend.
            layer_props = layer_props_original.copy()
            
            # Remove stale runtime keys from previous executions that may have been
            # copied from PROJECT_LAYERS (in case copy() was added after some runs)
            for stale_key in ['_effective_provider_type', '_postgresql_fallback', '_forced_backend']:
                layer_props.pop(stale_key, None)
            
            provider_type = layer_props["layer_provider_type"]
            layer_name = layer_props.get("layer_name", "unknown")
            layer_id = layer_props.get("layer_id", "unknown")
            
            # DIAGNOSTIC: Log initial provider type
            logger.debug(f"  📋 Layer '{layer_name}' initial provider_type='{provider_type}'")
            
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
                # CRITICAL FIX v2.5.14: PostgreSQL layers loaded in QGIS are ALWAYS filterable
                # via QGIS native API (setSubsetString). Default to True for PostgreSQL layers.
                if provider_type == PROVIDER_POSTGRES:
                    postgresql_connection_available = layer_props.get("postgresql_connection_available", True)
                    if not postgresql_connection_available or not POSTGRESQL_AVAILABLE:
                        logger.warning(f"  PostgreSQL layer '{layer_name}' has no connection available - using OGR fallback")
                        provider_type = PROVIDER_OGR
                        # Mark in layer_props for later reference
                        layer_props["_effective_provider_type"] = PROVIDER_OGR
                        layer_props["_postgresql_fallback"] = True
                    else:
                        logger.debug(f"  PostgreSQL layer '{layer_name}': using native PostgreSQL backend")
                
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

    def _queue_subset_string(self, layer, expression):
        """
        Queue a subset string request for thread-safe application in finished().
        
        CRITICAL: setSubsetString must be called from the main Qt thread.
        This method queues the request for processing in finished() which
        runs on the main thread, avoiding access violation crashes.
        
        Args:
            layer: QgsVectorLayer to apply filter to
            expression: Filter expression string (or empty string to clear)
            
        Returns:
            bool: True if queued successfully
        """
        if not hasattr(self, '_pending_subset_requests'):
            self._pending_subset_requests = []
        
        if layer is not None:
            self._pending_subset_requests.append((layer, expression))
            logger.debug(f"Queued subset request for {layer.name()}: {len(expression) if expression else 0} chars")
            return True
        return False

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
        thresholds = self._get_optimization_thresholds()
        large_dataset_threshold = thresholds['large_dataset_warning']
        
        if large_dataset_threshold > 0 and feature_count > large_dataset_threshold and not (
            POSTGRESQL_AVAILABLE and self.param_source_provider_type == PROVIDER_POSTGRES
        ):
            logger.warning(
                f"Large dataset detected ({feature_count:,} features > {large_dataset_threshold:,} threshold) without PostgreSQL backend. "
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
        import time
        run_start_time = time.time()
        
        try:
            # v2.4.13: Clear Spatialite support cache at the start of each filter task
            # This ensures fresh detection of Spatialite support for GeoPackage layers
            # and helps diagnose issues when GDAL/Spatialite configuration changes
            if self.task_action == 'filter':
                try:
                    from ..backends.spatialite_backend import SpatialiteGeometricFilter
                    SpatialiteGeometricFilter.clear_support_cache()
                    logger.debug("Spatialite support cache cleared for fresh detection")
                except Exception as e:
                    logger.debug(f"Could not clear Spatialite cache: {e}")
            
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
            
            # Extract session_id for multi-client materialized view isolation
            if 'session_id' in self.task_parameters["task"]:
                self.session_id = self.task_parameters["task"]['session_id']
            elif 'options' in self.task_parameters["task"] and 'session_id' in self.task_parameters["task"]["options"]:
                self.session_id = self.task_parameters["task"]["options"]['session_id']
            else:
                # Fallback: generate a short session id if not provided
                import hashlib
                import time
                self.session_id = hashlib.md5(f"{time.time()}".encode()).hexdigest()[:8]
                logger.debug(f"Generated fallback session_id: {self.session_id}")
            
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
            
            # v2.5.11: Check for long query duration and add warning if needed
            run_elapsed = time.time() - run_start_time
            if run_elapsed >= VERY_LONG_QUERY_WARNING_THRESHOLD:
                # Very long query (>30s): Critical warning
                warning_msg = (
                    f"La requête de filtrage a pris {run_elapsed:.1f}s. "
                    f"Pour de meilleures performances, considérez d'utiliser PostgreSQL/PostGIS "
                    f"ou de réduire la complexité du filtre (buffer plus petit, moins de couches)."
                )
                self.warning_messages.append(warning_msg)
                logger.warning(f"⚠️ Very long query: {run_elapsed:.1f}s")
            elif run_elapsed >= LONG_QUERY_WARNING_THRESHOLD:
                # Long query (>10s): Standard warning
                warning_msg = (
                    f"La requête de filtrage a pris {run_elapsed:.1f}s. "
                    f"Pour les jeux de données volumineux, PostgreSQL offre de meilleures performances."
                )
                self.warning_messages.append(warning_msg)
                logger.warning(f"⚠️ Long query: {run_elapsed:.1f}s")
            
            logger.info(f"{self.task_action.capitalize()} task completed successfully in {run_elapsed:.2f}s")
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
            # CRITICAL FIX v2.5.14: PostgreSQL layers loaded in QGIS are ALWAYS filterable
            # via QGIS native API (setSubsetString). The postgresql_connection_available flag
            # should default to True for PostgreSQL layers, not False.
            # 
            # The flag was intended to detect if psycopg2 connection works, but basic filtering
            # NEVER requires psycopg2 - it works via QGIS native PostgreSQL provider.
            # Only advanced features (materialized views) need psycopg2.
            if self.param_source_provider_type == PROVIDER_POSTGRES:
                # Default to True for PostgreSQL layers - they're always filterable via QGIS API
                postgresql_connection_available = infos.get("postgresql_connection_available", True)
                if not postgresql_connection_available or not POSTGRESQL_AVAILABLE:
                    logger.warning(f"Source layer is PostgreSQL but connection unavailable - using OGR fallback")
                    self.param_source_provider_type = PROVIDER_OGR
                    self._source_postgresql_fallback = True
                else:
                    self._source_postgresql_fallback = False
                    logger.debug(f"Source layer PostgreSQL: using native PostgreSQL backend (postgresql_connection_available={postgresql_connection_available})")
            else:
                self._source_postgresql_fallback = False
        
        # CRITICAL FIX v2.3.15: Re-validate schema from actual layer source for PostgreSQL
        # The stored layer_schema can be corrupted or incorrect (e.g., literal "schema" string)
        # This causes "relation schema.table does not exist" errors
        stored_schema = infos.get("layer_schema", "")
        if self.param_source_provider_type == PROVIDER_POSTGRES and self.source_layer:
            try:
                from qgis.core import QgsDataSourceUri
                source_uri = QgsDataSourceUri(self.source_layer.source())
                detected_schema = source_uri.schema()
                
                if detected_schema:
                    if stored_schema != detected_schema:
                        logger.info(f"Schema mismatch detected: stored='{stored_schema}', actual='{detected_schema}'")
                        logger.info(f"Using actual schema from layer source: '{detected_schema}'")
                    self.param_source_schema = detected_schema
                elif stored_schema and stored_schema != 'NULL':
                    # Use stored value if valid and no schema detected
                    self.param_source_schema = stored_schema
                else:
                    # Default to 'public' for PostgreSQL
                    self.param_source_schema = 'public'
                    logger.info(f"No schema detected, using default: 'public'")
            except Exception as e:
                logger.warning(f"Could not detect schema from layer source: {e}")
                self.param_source_schema = stored_schema if stored_schema and stored_schema != 'NULL' else 'public'
        else:
            self.param_source_schema = stored_schema
        
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
            self.param_source_old_subset = self._sanitize_subset_string(self.source_layer.subsetString())
            logger.info(f"FilterMate: Filtre existant détecté sur {self.param_source_table}: {self.param_source_old_subset[:100]}...")
        
        if self.has_combine_operator:
            # Combine operators are now always SQL keywords (AND, AND NOT, OR)
            # thanks to index-based conversion in dockwidget._index_to_combine_operator()
            self.param_source_layer_combine_operator = self.task_parameters["filtering"].get(
                "source_layer_combine_operator", "AND"
            )
            self.param_other_layers_combine_operator = self.task_parameters["filtering"].get(
                "other_layers_combine_operator", "AND"
            )
            # Ensure valid operator (fallback to AND if empty/invalid)
            if not self.param_source_layer_combine_operator:
                self.param_source_layer_combine_operator = "AND"
            if not self.param_other_layers_combine_operator:
                self.param_other_layers_combine_operator = "AND"

    def _sanitize_subset_string(self, subset_string):
        """
        Remove non-boolean display expressions and fix type casting issues in subset string.
        
        Display expressions like 'coalesce("field",'<NULL>')' or CASE expressions that
        return true/false are valid QGIS expressions but cause issues in SQL WHERE clauses.
        This function removes such expressions and fixes common type casting issues.
        
        Args:
            subset_string (str): The original subset string
            
        Returns:
            str: Sanitized subset string with non-boolean expressions removed
        """
        if not subset_string:
            return subset_string
        
        import re
        
        sanitized = subset_string
        
        # ========================================================================
        # PHASE 0: Normalize French SQL operators to English
        # ========================================================================
        # QGIS expressions support French operators (ET, OU, NON) but PostgreSQL
        # only understands English operators (AND, OR, NOT). This normalization
        # ensures compatibility with all SQL backends.
        # 
        # FIX v2.5.12: Handle French operators that cause SQL syntax errors like:
        # "syntax error at or near 'ET'" 
        
        french_operators = [
            (r'\)\s+ET\s+\(', ') AND ('),      # ) ET ( -> ) AND (
            (r'\)\s+OU\s+\(', ') OR ('),       # ) OU ( -> ) OR (
            (r'\s+ET\s+', ' AND '),            # ... ET ... -> ... AND ...
            (r'\s+OU\s+', ' OR '),             # ... OU ... -> ... OR ...
            (r'\s+ET\s+NON\s+', ' AND NOT '),  # ET NON -> AND NOT
            (r'\s+NON\s+', ' NOT '),           # NON ... -> NOT ...
        ]
        
        for pattern, replacement in french_operators:
            if re.search(pattern, sanitized, re.IGNORECASE):
                logger.info(f"FilterMate: Normalizing French operator '{pattern}' to '{replacement}'")
                sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        
        # ========================================================================
        # PHASE 1: Remove non-boolean display expressions
        # ========================================================================
        
        # Pattern to match AND/OR followed by coalesce display expressions
        # CRITICAL: These patterns must match display expressions that return values, not booleans
        # Example: AND (coalesce("cleabs",'<NULL>')) - returns text, not boolean
        # Note: The outer ( ) wraps coalesce(...) so we have )) at the end
        coalesce_patterns = [
            # Match coalesce with quoted string containing special chars like '<NULL>'
            # Pattern: AND (coalesce("field",'<NULL>'))  - note TWO closing parens
            r'(?:^|\s+)AND\s+\(coalesce\("[^"]+"\s*,\s*\'[^\']*\'\s*\)\)',
            r'(?:^|\s+)OR\s+\(coalesce\("[^"]+"\s*,\s*\'[^\']*\'\s*\)\)',
            # Match AND/OR followed by coalesce expression with nested content
            r'(?:^|\s+)AND\s+\(coalesce\([^)]*(?:\([^)]*\)[^)]*)*\)\)',
            r'(?:^|\s+)OR\s+\(coalesce\([^)]*(?:\([^)]*\)[^)]*)*\)\)',
            # Simpler patterns for common cases (TWO closing parens)
            r'(?:^|\s+)AND\s+\(coalesce\([^)]+\)\)',
            r'(?:^|\s+)OR\s+\(coalesce\([^)]+\)\)',
            # Match table.field syntax
            r'(?:^|\s+)AND\s+\(coalesce\("[^"]+"\s*\.\s*"[^"]+"\s*,\s*\'[^\']*\'\s*\)\)',
            r'(?:^|\s+)OR\s+\(coalesce\("[^"]+"\s*\.\s*"[^"]+"\s*,\s*\'[^\']*\'\s*\)\)',
        ]
        
        for pattern in coalesce_patterns:
            match = re.search(pattern, sanitized, re.IGNORECASE)
            if match:
                logger.info(f"FilterMate: Removing invalid coalesce expression: '{match.group()[:60]}...'")
                sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
        
        # Pattern to match AND/OR followed by CASE expressions that just return true/false
        # These are style/display expressions, not filter conditions
        # Match: AND ( case when ... end ) OR AND ( SELECT CASE when ... end )
        # with multiple closing parentheses (malformed)
        #
        # CRITICAL FIX v2.5.10: Improved patterns to handle multi-line CASE expressions
        # like those from rule-based symbology:
        #   AND ( SELECT CASE 
        #     WHEN 'AV' = left("table"."field", 2) THEN true
        #     WHEN 'PL' = left("table"."field", 2) THEN true
        #     ...
        #   end )
        
        # IMPROVED PATTERN: Match AND ( SELECT CASE ... WHEN ... THEN true/false ... end )
        # This pattern is more robust for multi-line expressions from QGIS rule-based symbology
        select_case_pattern = r'\s*AND\s+\(\s*SELECT\s+CASE\s+(?:WHEN\s+.+?THEN\s+(?:true|false)\s*)+\s*(?:ELSE\s+.+?)?\s*end\s*\)'
        
        match = re.search(select_case_pattern, sanitized, re.IGNORECASE | re.DOTALL)
        if match:
            logger.info(f"FilterMate: Removing SELECT CASE style expression: '{match.group()[:80]}...'")
            sanitized = re.sub(select_case_pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        
        # Also check for simpler CASE patterns without SELECT
        case_patterns = [
            # Standard CASE expression with true/false returns  
            r'\s*AND\s+\(\s*CASE\s+(?:WHEN\s+.+?THEN\s+(?:true|false)\s*)+(?:ELSE\s+.+?)?\s*END\s*\)+',
            r'\s*OR\s+\(\s*CASE\s+(?:WHEN\s+.+?THEN\s+(?:true|false)\s*)+(?:ELSE\s+.+?)?\s*END\s*\)+',
            # SELECT CASE expression (from rule-based styles) - backup pattern
            r'\s*AND\s+\(\s*SELECT\s+CASE\s+.+?\s+END\s*\)+',
            r'\s*OR\s+\(\s*SELECT\s+CASE\s+.+?\s+END\s*\)+',
        ]
        
        for pattern in case_patterns:
            match = re.search(pattern, sanitized, re.IGNORECASE | re.DOTALL)
            if match:
                # Verify this is a display/style expression (returns true/false, not a comparison)
                matched_text = match.group()
                # Check if it's just "then true/false" without external comparison
                if re.search(r'\bTHEN\s+(true|false)\b', matched_text, re.IGNORECASE):
                    logger.info(f"FilterMate: Removing invalid CASE/style expression: '{matched_text[:60]}...'")
                    sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove standalone coalesce expressions at start
        standalone_coalesce = r'^\s*\(coalesce\([^)]*(?:\([^)]*\)[^)]*)*\)\)\s*(?:AND|OR)?'
        if re.match(standalone_coalesce, sanitized, re.IGNORECASE):
            match = re.match(standalone_coalesce, sanitized, re.IGNORECASE)
            logger.info(f"FilterMate: Removing standalone coalesce: '{match.group()[:60]}...'")
            sanitized = re.sub(standalone_coalesce, '', sanitized, flags=re.IGNORECASE)
        
        # ========================================================================
        # PHASE 2: Fix unbalanced parentheses
        # ========================================================================
        
        # Count parentheses and fix if unbalanced
        open_count = sanitized.count('(')
        close_count = sanitized.count(')')
        
        if close_count > open_count:
            # Remove excess closing parentheses from the end
            excess = close_count - open_count
            # Remove trailing )))) patterns
            trailing_parens = re.search(r'\)+\s*$', sanitized)
            if trailing_parens:
                parens_at_end = len(trailing_parens.group().strip())
                if parens_at_end >= excess:
                    sanitized = re.sub(r'\){' + str(excess) + r'}\s*$', '', sanitized)
                    logger.info(f"FilterMate: Removed {excess} excess closing parentheses")
        
        # ========================================================================
        # PHASE 3: Clean up whitespace and orphaned operators
        # ========================================================================
        
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        sanitized = re.sub(r'\s+(AND|OR)\s*$', '', sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r'^\s*(AND|OR)\s+', '', sanitized, flags=re.IGNORECASE)
        
        # Remove duplicate AND/OR operators
        sanitized = re.sub(r'\s+AND\s+AND\s+', ' AND ', sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r'\s+OR\s+OR\s+', ' OR ', sanitized, flags=re.IGNORECASE)
        
        if sanitized != subset_string:
            logger.info(f"FilterMate: Subset sanitized from '{subset_string[:80]}...' to '{sanitized[:80]}...'")
        
        return sanitized
    
    def _extract_spatial_clauses_for_exists(self, filter_expr, source_table=None):
        """
        Extract only spatial clauses (ST_Intersects, etc.) from a filter expression.
        
        CRITICAL FIX v2.5.11: For EXISTS subqueries in PostgreSQL, we must include
        the source layer's spatial filter to ensure we only consider filtered features.
        However, we must EXCLUDE:
        - Style-based rules (SELECT CASE ... THEN true/false)
        - Attribute-only filters (without spatial predicates)
        - coalesce display expressions
        
        This ensures the EXISTS query sees the same filtered source as QGIS.
        
        Args:
            filter_expr: The source layer's current subsetString
            source_table: Source table name for reference replacement
            
        Returns:
            str: Extracted spatial clauses only, or None if no spatial predicates found
        """
        if not filter_expr:
            return None
        
        import re
        
        # List of spatial predicates to extract
        SPATIAL_PREDICATES = [
            'ST_Intersects', 'ST_Contains', 'ST_Within', 'ST_Touches',
            'ST_Overlaps', 'ST_Crosses', 'ST_Disjoint', 'ST_Equals',
            'ST_DWithin', 'ST_Covers', 'ST_CoveredBy'
        ]
        
        # Check if filter contains any spatial predicates
        filter_upper = filter_expr.upper()
        has_spatial = any(pred.upper() in filter_upper for pred in SPATIAL_PREDICATES)
        
        if not has_spatial:
            logger.debug(f"_extract_spatial_clauses: No spatial predicates in filter")
            return None
        
        # First, remove style-based expressions (SELECT CASE ... THEN true/false)
        cleaned = filter_expr
        
        # Pattern for SELECT CASE style rules (multi-line support)
        select_case_pattern = r'\s*AND\s+\(\s*SELECT\s+CASE\s+(?:WHEN\s+.+?THEN\s+(?:true|false)\s*)+\s*(?:ELSE\s+.+?)?\s*end\s*\)'
        cleaned = re.sub(select_case_pattern, '', cleaned, flags=re.IGNORECASE | re.DOTALL)
        
        # Pattern for simple CASE style rules
        case_pattern = r'\s*AND\s+\(\s*CASE\s+(?:WHEN\s+.+?THEN\s+(?:true|false)\s*)+(?:ELSE\s+.+?)?\s*END\s*\)+'
        cleaned = re.sub(case_pattern, '', cleaned, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove coalesce display expressions
        coalesce_pattern = r'\s*(?:AND|OR)\s+\(coalesce\([^)]*(?:\([^)]*\)[^)]*)*\)\)'
        cleaned = re.sub(coalesce_pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Clean up whitespace and operators
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        cleaned = re.sub(r'\s+(AND|OR)\s*$', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'^\s*(AND|OR)\s+', '', cleaned, flags=re.IGNORECASE)
        
        # Remove outer parentheses if present
        while cleaned.startswith('(') and cleaned.endswith(')'):
            # Check if these are matching outer parens
            depth = 0
            is_outer = True
            for i, char in enumerate(cleaned):
                if char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1
                    if depth == 0 and i < len(cleaned) - 1:
                        is_outer = False
                        break
            if is_outer and depth == 0:
                cleaned = cleaned[1:-1].strip()
            else:
                break
        
        # Verify cleaned expression still contains spatial predicates
        cleaned_upper = cleaned.upper()
        has_spatial_after_clean = any(pred.upper() in cleaned_upper for pred in SPATIAL_PREDICATES)
        
        if not has_spatial_after_clean:
            logger.debug(f"_extract_spatial_clauses: Spatial predicates removed during cleaning")
            return None
        
        # Validate parentheses are balanced
        if cleaned.count('(') != cleaned.count(')'):
            logger.warning(f"_extract_spatial_clauses: Unbalanced parentheses after extraction")
            return None
        
        logger.info(f"_extract_spatial_clauses: Extracted spatial filter: '{cleaned[:100]}...'")
        return cleaned
    
    def _apply_postgresql_type_casting(self, expression, layer=None):
        """
        Apply PostgreSQL type casting to fix common type mismatch errors.
        
        Handles cases like "importance" < 4 where importance is varchar.
        
        Args:
            expression: SQL expression
            layer: Optional layer to get field type information
            
        Returns:
            str: Expression with type casting applied
        """
        if not expression:
            return expression
        
        import re
        
        # Add ::numeric type casting for numeric comparisons if not already present
        # This handles cases like "importance" < 4 → "importance"::numeric < 4
        # Pattern: "field" followed by comparison operator and number
        # Only apply if not already cast (no :: before the operator)
        
        numeric_comparison_pattern = r'"([^"]+)"(\s*)(<|>|<=|>=)(\s*)(\d+(?:\.\d+)?)'
        
        def add_numeric_cast(match):
            field = match.group(1)
            space1 = match.group(2)
            operator = match.group(3)
            space2 = match.group(4)
            number = match.group(5)
            # Check if already has type casting
            return f'"{field}"::numeric{space1}{operator}{space2}{number}'
        
        # Only apply if not already cast (check for :: before operator)
        if '::numeric' not in expression:
            expression = re.sub(numeric_comparison_pattern, add_numeric_cast, expression)
        
        return expression

    def _process_qgis_expression(self, expression):
        """
        Process and validate a QGIS expression, converting it to appropriate SQL.
        
        Returns:
            tuple: (processed_expression, is_field_expression) or (None, None) if invalid
        """
        # FIXED: Only reject if expression is JUST a field name (no operators)
        # Allow expressions like "HOMECOUNT = 10" or "field > 5"
        qgs_expr = QgsExpression(expression)
        # FIX v2.3.9: Use case-insensitive check for operators (e.g., 'in' vs 'IN')
        expr_upper = expression.upper()
        if qgs_expr.isField() and not any(op in expr_upper for op in ['=', '>', '<', '!', 'IN', 'LIKE', 'AND', 'OR']):
            logger.debug(f"Rejecting expression '{expression}' - it's just a field name without comparison")
            return None, None
        
        if not qgs_expr.isValid():
            logger.warning(f"Invalid QGIS expression: '{expression}'")
            return None, None
        
        # CRITICAL FIX: Reject "display expressions" that don't return boolean values
        # Display expressions like coalesce("field",'<NULL>') are valid QGIS expressions
        # but they return string/value types, not boolean - they cannot be used as SQL WHERE filters
        # Filter expressions must contain comparison/logical operators
        comparison_operators = ['=', '>', '<', '!=', '<>', 'IN', 'LIKE', 'ILIKE', 'IS NULL', 'IS NOT NULL', 
                               'BETWEEN', 'NOT', 'AND', 'OR', '~', 'SIMILAR TO', '@', '&&']
        has_comparison = any(op in expression.upper() for op in comparison_operators)
        
        if not has_comparison:
            # Expression doesn't contain comparison operators - likely a display expression
            logger.debug(f"Rejecting expression '{expression}' - no comparison operators found (display expression, not filter)")
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
        
        OPTIMIZATION v2.5.13: Detects and removes duplicate IN clauses
        - Multi-step filtering can generate duplicate "fid IN (...)" clauses
        - These duplicates are detected and merged for optimal query performance
        
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
        
        def extract_in_clauses(expr):
            """
            Extract all IN clauses from expression for deduplication.
            Returns dict mapping field names to sets of IDs.
            
            OPTIMIZATION v2.5.13: Detect duplicate IN clauses for same field
            """
            in_clauses = {}
            # Pattern to match "field" IN (id1, id2, ...) or "table"."field" IN (...)
            pattern = r'"([^"]+)"(?:\."([^"]+)")?\s+IN\s*\(([^)]+)\)'
            matches = re.finditer(pattern, expr, re.IGNORECASE)
            
            for match in matches:
                if match.group(2):
                    # Qualified name: "table"."field"
                    field_key = f'"{match.group(1)}"."{match.group(2)}"'
                else:
                    # Simple name: "field"
                    field_key = f'"{match.group(1)}"'
                
                # Parse IDs from the IN clause
                ids_str = match.group(3)
                ids = set()
                for id_part in ids_str.split(','):
                    id_part = id_part.strip().strip("'\"")
                    if id_part:
                        ids.add(id_part)
                
                if field_key not in in_clauses:
                    in_clauses[field_key] = ids
                else:
                    # Check if this is a duplicate IN clause for same field
                    existing_ids = in_clauses[field_key]
                    if ids == existing_ids:
                        # Identical IN clause - flag as duplicate
                        logger.debug(f"FilterMate: Detected duplicate IN clause for {field_key} with {len(ids)} IDs")
                    else:
                        # Different IDs - intersection for AND, union for OR
                        in_clauses[field_key] = existing_ids & ids  # AND = intersection
            
            return in_clauses
        
        def optimize_expression(expr):
            """
            Remove duplicate IN clauses from expression.
            
            OPTIMIZATION v2.5.13: Multi-step filtering generates duplicate clauses like:
            (A AND fid IN (1,2,3)) AND (fid IN (1,2,3)) AND (fid IN (1,2,3))
            
            This function detects and removes the duplicates, keeping only ONE IN clause.
            """
            # Count IN clauses for same field
            pattern = r'"([^"]+)"(?:\."([^"]+)")?\s+IN\s*\([^)]+\)'
            matches = list(re.finditer(pattern, expr, re.IGNORECASE))
            
            if len(matches) <= 1:
                return expr  # No duplicates possible
            
            # Group matches by field name
            field_matches = {}
            for match in matches:
                if match.group(2):
                    field_key = f'"{match.group(1)}"."{match.group(2)}"'
                else:
                    field_key = f'"{match.group(1)}"'
                
                if field_key not in field_matches:
                    field_matches[field_key] = []
                field_matches[field_key].append(match)
            
            # Check for duplicates (more than one IN clause for same field)
            for field_key, field_match_list in field_matches.items():
                if len(field_match_list) > 1:
                    logger.info(f"FilterMate: OPTIMIZATION - Found {len(field_match_list)} duplicate IN clauses for {field_key}")
                    
                    # Keep only the first occurrence, remove the rest
                    # We need to remove from end to start to preserve indices
                    for match in reversed(field_match_list[1:]):
                        start, end = match.span()
                        # Find the surrounding AND/OR operator to remove
                        before_context = expr[max(0, start-10):start]
                        
                        # Remove " AND (" before the duplicate clause
                        if ' AND (' in before_context or ' AND(' in before_context:
                            # Find the actual start of " AND ("
                            and_pos = expr.rfind(' AND (', 0, start)
                            if and_pos != -1:
                                # Find matching closing paren
                                depth = 0
                                close_pos = end
                                for i in range(and_pos, len(expr)):
                                    if expr[i] == '(':
                                        depth += 1
                                    elif expr[i] == ')':
                                        depth -= 1
                                        if depth == 0:
                                            close_pos = i + 1
                                            break
                                # Remove " AND ( ... IN (...) )"
                                expr = expr[:and_pos] + expr[close_pos:]
                                logger.debug(f"FilterMate: Removed duplicate AND clause at positions {and_pos}-{close_pos}")
            
            # Clean up any resulting double spaces or orphaned operators
            expr = re.sub(r'\s+', ' ', expr)
            expr = re.sub(r'\(\s*\)', '', expr)  # Remove empty parens
            expr = re.sub(r'AND\s+AND', 'AND', expr)  # Fix double ANDs
            expr = re.sub(r'\(\s*AND\s*', '(', expr)  # Remove leading AND in parens
            expr = re.sub(r'\s*AND\s*\)', ')', expr)  # Remove trailing AND in parens
            
            return expr.strip()
        
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
        
        # CRITICAL FIX v2.5.12: Handle OGR fallback for PostgreSQL layers
        # When using OGR fallback, the old subset might contain PostgreSQL-specific syntax
        # (SELECT ... FROM ... WHERE ...) that OGR can't parse. In this case, only use
        # the WHERE clause portion, or skip combination if the old subset is too complex.
        if hasattr(self, 'param_source_provider_type') and self.param_source_provider_type == PROVIDER_OGR:
            # For OGR, check if old subset contains PostgreSQL-specific syntax
            old_subset_upper = self.param_source_old_subset.upper()
            if 'SELECT' in old_subset_upper or 'FROM' in old_subset_upper:
                logger.warning(f"FilterMate: Old subset contains PostgreSQL syntax but using OGR fallback")
                # Try to extract just the WHERE clause
                index_where = self.param_source_old_subset.upper().find('WHERE')
                if index_where != -1:
                    where_clause = self.param_source_old_subset[index_where + 5:].strip()  # Skip 'WHERE'
                    # Remove trailing SELECT part if this was a subquery
                    if where_clause:
                        logger.info(f"FilterMate: Extracted WHERE clause for OGR: {where_clause[:80]}...")
                        return f'( {where_clause} ) {combine_operator} ( {expression} )'
                # Can't extract WHERE clause - skip combination, use new expression only
                logger.warning(f"FilterMate: Cannot combine with PostgreSQL subset in OGR mode - using new expression only")
                return expression
        
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
        
        # OPTIMIZATION v2.5.13: Remove duplicate IN clauses from multi-step filtering
        # This prevents expressions like: (A AND fid IN (...)) AND (fid IN (...)) AND (fid IN (...))
        optimized = optimize_expression(combined)
        if optimized != combined:
            original_len = len(combined)
            optimized_len = len(optimized)
            savings = original_len - optimized_len
            logger.info(f"FilterMate: OPTIMIZATION - Reduced expression size from {original_len} to {optimized_len} bytes ({savings} bytes saved, {100*savings/original_len:.1f}% reduction)")
            return optimized
        
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
            
            # CRITICAL FIX v2.5.12: Handle OGR fallback for PostgreSQL layers
            # When using OGR fallback, the old subset might contain PostgreSQL-specific syntax
            old_subset_to_combine = self.param_source_old_subset
            if self.param_source_provider_type == PROVIDER_OGR:
                old_subset_upper = self.param_source_old_subset.upper()
                if 'SELECT' in old_subset_upper or 'FROM' in old_subset_upper:
                    logger.warning(f"FilterMate: Old subset contains PostgreSQL syntax but using OGR fallback (feature ID list)")
                    # Try to extract just the WHERE clause
                    index_where = self.param_source_old_subset.upper().find('WHERE')
                    if index_where != -1:
                        where_clause = self.param_source_old_subset[index_where + 5:].strip()
                        if where_clause:
                            old_subset_to_combine = where_clause
                            logger.info(f"FilterMate: Extracted WHERE clause for OGR: {where_clause[:80]}...")
                        else:
                            # Can't extract WHERE clause - skip combination
                            logger.warning(f"FilterMate: Cannot combine with PostgreSQL subset in OGR mode - using new expression only")
                            return expression
                    else:
                        # No WHERE clause found - skip combination
                        logger.warning(f"FilterMate: Cannot combine with PostgreSQL subset in OGR mode - using new expression only")
                        return expression
            
            expression = (
                f'( {old_subset_to_combine} ) '
                f'{combine_operator} ( {expression} )'
            )
            
            # OPTIMIZATION v2.5.13: Check for duplicate IN clauses
            # Multi-step filtering can create redundant: (old AND fid IN(...)) AND (fid IN(...))
            expression = self._optimize_duplicate_in_clauses(expression)
        
        return expression
    
    def _optimize_duplicate_in_clauses(self, expression):
        """
        Remove duplicate IN clauses from an expression.
        
        OPTIMIZATION v2.5.13: Multi-step filtering generates duplicate clauses like:
        (A AND fid IN (1,2,3)) AND (fid IN (1,2,3)) AND (fid IN (1,2,3))
        
        This function detects and removes the duplicates, keeping only ONE IN clause per field.
        
        Args:
            expression: SQL expression potentially containing duplicate IN clauses
            
        Returns:
            str: Optimized expression with duplicate IN clauses removed
        """
        if not expression:
            return expression
        
        # Pattern to match "field" IN (...) or "table"."field" IN (...)
        pattern = r'"([^"]+)"(?:\."([^"]+)")?\s+IN\s*\([^)]+\)'
        matches = list(re.finditer(pattern, expression, re.IGNORECASE))
        
        if len(matches) <= 1:
            return expression  # No duplicates possible
        
        # Group matches by field name
        field_matches = {}
        for match in matches:
            if match.group(2):
                field_key = f'"{match.group(1)}"."{match.group(2)}"'
            else:
                field_key = f'"{match.group(1)}"'
            
            if field_key not in field_matches:
                field_matches[field_key] = []
            field_matches[field_key].append(match)
        
        # Check for duplicates (more than one IN clause for same field)
        has_duplicates = False
        for field_key, field_match_list in field_matches.items():
            if len(field_match_list) > 1:
                has_duplicates = True
                logger.info(f"FilterMate: OPTIMIZATION - Found {len(field_match_list)} duplicate IN clauses for {field_key}")
        
        if not has_duplicates:
            return expression
        
        # Remove duplicates - keep first occurrence, remove subsequent ones
        result = expression
        for field_key, field_match_list in field_matches.items():
            if len(field_match_list) <= 1:
                continue
                
            # Process from end to start to preserve indices
            for match in reversed(field_match_list[1:]):
                start, end = match.span()
                
                # Find the surrounding AND operator and parentheses
                # Look for " AND (" before the match
                search_start = max(0, start - 20)
                before = result[search_start:start]
                
                # Pattern: " AND (" or " AND " before the IN clause
                and_pattern = r'\s+AND\s+\(\s*$'
                and_match = re.search(and_pattern, before, re.IGNORECASE)
                
                if and_match:
                    # Find corresponding closing paren after the IN clause
                    actual_start = search_start + and_match.start()
                    depth = 0
                    close_pos = end
                    
                    for i, char in enumerate(result[actual_start:], actual_start):
                        if char == '(':
                            depth += 1
                        elif char == ')':
                            depth -= 1
                            if depth == 0:
                                close_pos = i + 1
                                break
                    
                    # Remove " AND ( ... IN (...) )"
                    result = result[:actual_start] + result[close_pos:]
                    logger.debug(f"FilterMate: Removed duplicate clause for {field_key}")
        
        # Clean up any double spaces or malformed syntax
        result = re.sub(r'\s+', ' ', result)
        result = re.sub(r'\(\s*\)', '', result)  # Remove empty parens
        result = re.sub(r'AND\s+AND', 'AND', result, flags=re.IGNORECASE)
        result = re.sub(r'\(\s*AND', '(', result, flags=re.IGNORECASE)
        result = re.sub(r'AND\s*\)', ')', result, flags=re.IGNORECASE)
        
        # Log optimization results
        if len(result) < len(expression):
            savings = len(expression) - len(result)
            pct = 100 * savings / len(expression)
            logger.info(f"FilterMate: OPTIMIZATION - Reduced expression by {savings} bytes ({pct:.1f}% reduction)")
        
        return result.strip()

    def _apply_filter_and_update_subset(self, expression):
        """
        Queue filter expression for application on main thread.
        
        CRITICAL: setSubsetString must be called from main thread to avoid
        access violation crashes. This method now only queues the expression
        for application in finished() which runs on the main thread.
        
        Returns:
            bool: True if expression was queued successfully
        """
        # Apply type casting for PostgreSQL to fix varchar/numeric comparison issues
        # CRITICAL FIX v2.5.12: Use param_source_provider_type instead of providerType()
        # providerType() returns 'postgres' even when using OGR fallback (psycopg2 unavailable)
        # param_source_provider_type correctly accounts for OGR fallback
        if self.param_source_provider_type == PROVIDER_POSTGRES:
            expression = self._apply_postgresql_type_casting(expression, self.source_layer)
        
        # CRITICAL FIX v2.6.6: Do NOT call setSubsetString from worker thread!
        # This causes "access violation" crashes on Windows because QGIS layer
        # operations are not thread-safe.
        # Instead, queue the expression for application in finished() which
        # runs on the main Qt thread.
        
        # Queue source layer for filter application in finished()
        if hasattr(self, '_pending_subset_requests'):
            self._pending_subset_requests.append((self.source_layer, expression))
            logger.info(f"Queued source layer {self.source_layer.name()} for filter application in finished()")
        
        # Only build PostgreSQL SELECT for PostgreSQL providers
        # OGR and Spatialite use subset strings directly
        # CRITICAL FIX v2.5.12: Use param_source_provider_type instead of providerType()
        # providerType() returns 'postgres' even when using OGR fallback
        if self.param_source_provider_type == PROVIDER_POSTGRES:
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
        
        # Return True to indicate expression was queued successfully
        return True

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
            # FIX v2.3.9: Use case-insensitive check for operators (e.g., 'in' vs 'IN')
            task_expr_upper = task_expression.upper()
            is_simple_field = qgs_expr.isField() and not any(
                op in task_expr_upper for op in ['=', '>', '<', '!', 'IN', 'LIKE', 'AND', 'OR']
            )
        
        # Check if skip_source_filter is enabled (custom selection with non-filter expression)
        skip_source_filter = self.task_parameters["task"].get("skip_source_filter", False)
        
        # Check if geometric filtering is enabled (for logging purposes)
        has_geom_predicates = self.task_parameters["filtering"]["has_geometric_predicates"]
        geom_predicates_list = self.task_parameters["filtering"].get("geometric_predicates", [])
        has_geometric_filtering = has_geom_predicates and len(geom_predicates_list) > 0
        
        # ================================================================
        # MODE ALL-FEATURES: Custom Selection sans filtre valide
        # ================================================================
        # Quand skip_source_filter=True, utiliser TOUTES les features de la couche source
        # sans modifier son subset (garder l'existant)
        # ================================================================
        if skip_source_filter:
            logger.info("=" * 60)
            logger.info("🔄 ALL-FEATURES MODE (skip_source_filter=True)")
            logger.info("=" * 60)
            logger.info("  Custom selection active with non-filter expression")
            logger.info("  → Source layer will NOT be filtered (keeps existing subset)")
            logger.info("  → All features from source layer will be used for geometric predicates")
            
            # Store that we're using all features
            self.is_field_expression = (True, "__all_features__")
            
            # Keep existing subset - don't modify source layer filter
            self.expression = self.param_source_old_subset if self.param_source_old_subset else ""
            
            # Log detailed information about source layer state
            current_subset = self.source_layer.subsetString()
            feature_count = self.source_layer.featureCount()
            
            if current_subset:
                logger.info(f"  ✓ Source layer has active subset: '{current_subset[:80]}...'")
                logger.info(f"  ✓ {feature_count} filtered features will be used for geometric intersection")
            else:
                logger.info(f"  ✓ Source layer has NO subset - all {feature_count} features will be used")
            
            # Mark as successful - source layer remains with current filter
            result = True
            logger.info("=" * 60)
            return result
        
        # ================================================================
        # MODE FIELD-BASED: Custom Selection avec champ simple
        # ================================================================
        # COMPORTEMENT ATTENDU:
        #   1. COUCHE SOURCE: Garder le subset existant (PAS de modification)
        #   2. COUCHES DISTANTES: Appliquer filtre géométrique en intersection
        #                         avec TOUTES les géométries de la couche source (avec son filtre existant)
        #
        # Ce mode s'active dès que l'expression est un simple champ, peu importe
        # si des prédicats géométriques explicites sont configurés. Cela permet
        # aux filtres distants d'utiliser l'ensemble de la couche source.
        #
        # EXEMPLE:
        #   - Couche source avec subset: "homecount > 5" (affiche 100 features)
        #   - Custom selection active avec champ: "drop_ID"
        #   - Prédicats géométriques: "intersects" vers couche distante (ou filtrage implicite)
        #   → Résultat: Source garde "homecount > 5", distant filtré par intersection avec ces 100 features
        # ================================================================
        if is_simple_field:
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

        # Extract use_centroids parameters
        self.param_use_centroids_source_layer = self.task_parameters["filtering"].get("use_centroids_source_layer", False)
        self.param_use_centroids_distant_layers = self.task_parameters["filtering"].get("use_centroids_distant_layers", False)
        logger.info(f"  use_centroids_source_layer: {self.param_use_centroids_source_layer}")
        logger.info(f"  use_centroids_distant_layers: {self.param_use_centroids_distant_layers}")
        
        # v2.7.0: Extract pre-approved optimizations from UI confirmation dialog
        # These are set in filter_mate_app._check_and_confirm_optimizations()
        self.approved_optimizations = self.task_parameters.get("task", {}).get("approved_optimizations", {})
        self.auto_apply_optimizations = self.task_parameters.get("task", {}).get("auto_apply_optimizations", False)
        if self.approved_optimizations:
            logger.info(f"  ✓ User-approved optimizations loaded: {len(self.approved_optimizations)} layer(s)")
            for layer_id, opts in self.approved_optimizations.items():
                logger.info(f"    - {layer_id[:8]}...: {opts}")
        elif self.auto_apply_optimizations:
            logger.info(f"  ✓ Auto-apply optimizations enabled (no confirmation required)")
        
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
            # Extract buffer_segments configuration
            self.param_buffer_segments = self.task_parameters["filtering"].get("buffer_segments", 5)
            logger.info(f"  ✓ Buffer segments set: {self.param_buffer_segments}")
        else:
            self.param_buffer_type = 0  # Default to Round
            self.param_buffer_segments = 5  # Default segments
            logger.info(f"  ℹ️  Buffer type not configured, using default: Round (END_CAP_STYLE=0), segments=5")
        
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
        # CRITICAL FIX v2.7.3: Use SELECTED/FILTERED feature count, not total table count!
        # When user selects 1 commune out of 930, we should use WKT mode (1 feature ≤ 50)
        # NOT EXISTS subquery (which would require filtering 930 communes).
        #
        # Priority for source feature count:
        # 1. task_features from task_parameters (selected features passed from main thread)
        # 2. source_layer.featureCount() (respects subsetString but NOT manual selection)
        task_features = self.task_parameters.get("task", {}).get("features", [])
        if task_features and len(task_features) > 0:
            source_feature_count = len(task_features)
            logger.info(f"Using task_features count for WKT decision: {source_feature_count} selected features")
            # DIAGNOSTIC: Also log to QGIS Message Panel
            logger.debug(
                f"v2.7.3 FIX: Using {source_feature_count} SELECTED features for WKT decision (not {self.source_layer.featureCount()} total)"
            )
        else:
            source_feature_count = self.source_layer.featureCount()
            logger.info(f"Using source_layer featureCount for WKT decision: {source_feature_count} total features")
        
        # CRITICAL FIX v2.7.15: Check if source is PostgreSQL with connection
        # If source IS PostgreSQL, we should prefer EXISTS subquery over WKT mode
        # because WKT simplification can produce Bounding Box fallback which returns too many features
        source_is_postgresql = (
            self.param_source_provider_type == PROVIDER_POSTGRES and
            self.task_parameters.get("infos", {}).get("postgresql_connection_available", True)
        )
        
        postgresql_needs_wkt = (
            'postgresql' in provider_list and 
            POSTGRESQL_AVAILABLE and
            source_feature_count <= 50 and  # SIMPLE_WKT_THRESHOLD from PostgreSQL backend
            not source_is_postgresql  # v2.7.15: Don't use WKT mode if source is PostgreSQL (use EXISTS instead)
        )
        
        # DIAGNOSTIC: Log WKT decision
        logger.debug(
            f"v2.7.15: postgresql_needs_wkt={postgresql_needs_wkt} (count={source_feature_count}, source_is_pg={source_is_postgresql})"
        )
        if postgresql_needs_wkt:
            logger.info(f"PostgreSQL simplified mode: {source_feature_count} features ≤ 50, source is NOT PostgreSQL")
            logger.info("  → Will prepare WKT geometry for direct ST_GeomFromText()")
        elif source_is_postgresql and 'postgresql' in provider_list:
            logger.info(f"PostgreSQL EXISTS mode: source IS PostgreSQL with {source_feature_count} features")
            logger.info("  → Will use EXISTS subquery with table reference (no WKT simplification)")
        
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
        # CRITICAL FIX v2.7.2: Only prepare postgresql_source_geom if SOURCE layer is PostgreSQL
        # Previously, this was also called when source layer is OGR but distant layers are PostgreSQL.
        # This created invalid table references like "public"."commune"."geometrie" where
        # "commune" is an OGR layer (GeoPackage/Shapefile) that doesn't exist in PostgreSQL!
        # The result was that EXISTS subqueries referenced non-existent tables, causing
        # filters to silently fail and return all features instead of filtered results.
        #
        # NEW BEHAVIOR:
        # - Source is PostgreSQL + distant is PostgreSQL: Use postgresql_source_geom (EXISTS subquery)
        # - Source is OGR + distant is PostgreSQL: Use WKT (spatialite_source_geom) with ST_GeomFromText
        has_postgresql_fallback_layers = False  # Track if any PostgreSQL layer uses OGR fallback
        
        if 'postgresql' in provider_list and POSTGRESQL_AVAILABLE:
            # Check if SOURCE layer is PostgreSQL with connection
            # CRITICAL FIX v2.5.14: Default to True for PostgreSQL layers
            source_is_postgresql_with_connection = (
                self.param_source_provider_type == PROVIDER_POSTGRES and
                self.task_parameters.get("infos", {}).get("postgresql_connection_available", True)
            )
            
            # Check if any DISTANT PostgreSQL layer has connection available
            has_distant_postgresql_with_connection = False
            if hasattr(self, 'layers') and 'postgresql' in self.layers:
                for layer, layer_props in self.layers['postgresql']:
                    # CRITICAL FIX v2.5.14: Default to True for PostgreSQL layers
                    if layer_props.get('postgresql_connection_available', True):
                        has_distant_postgresql_with_connection = True
                    # CRITICAL FIX: Check if this layer uses OGR fallback
                    if layer_props.get('_postgresql_fallback', False):
                        has_postgresql_fallback_layers = True
                        logger.info(f"  → Layer '{layer.name()}' is PostgreSQL with OGR fallback")
            
            # CRITICAL FIX v2.7.2: ONLY prepare postgresql_source_geom if SOURCE is PostgreSQL
            # For OGR source + PostgreSQL distant, we will use WKT mode (spatialite_source_geom)
            if source_is_postgresql_with_connection:
                logger.info("Preparing PostgreSQL source geometry...")
                logger.info("  → Source layer is PostgreSQL with connection")
                self.prepare_postgresql_source_geom()
            elif has_distant_postgresql_with_connection:
                # Source is NOT PostgreSQL but distant layers ARE PostgreSQL
                # Use WKT mode (ST_GeomFromText) instead of EXISTS subquery
                logger.info("PostgreSQL distant layers detected but source is NOT PostgreSQL")
                logger.info("  → Source layer provider: %s", self.param_source_provider_type)
                logger.info("  → Will use WKT mode (ST_GeomFromText) for PostgreSQL filtering")
                logger.info("  → Skipping prepare_postgresql_source_geom() to avoid invalid table references")
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
            logger.debug(f"v2.7.3: Preparing Spatialite/WKT geometry (postgresql_wkt={postgresql_needs_wkt})")
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
                    logger.debug(f"v2.7.3: WKT prepared OK ({len(self.spatialite_source_geom)} chars)")
                    logger.info(f"  → WKT preview: {wkt_preview}...")
                else:
                    logger.warning("Spatialite geometry preparation returned None")
                    QgsMessageLog.logMessage(
                        "v2.7.3: WARNING - Spatialite geometry preparation returned None!",
                        "FilterMate", Qgis.Warning
                    )
            except Exception as e:
                logger.warning(f"Spatialite geometry preparation failed: {e}")
                QgsMessageLog.logMessage(
                    f"v2.7.3: ERROR - Spatialite geometry preparation failed: {e}",
                    "FilterMate", Qgis.Critical
                )
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
            
            # DIAGNOSTIC v2.4.11: Log status of all source geometries after preparation
            logger.info("=" * 60)
            logger.info("📊 SOURCE GEOMETRY STATUS AFTER PREPARATION")
            logger.info("=" * 60)
            
            spatialite_status = "✓ READY" if (hasattr(self, 'spatialite_source_geom') and self.spatialite_source_geom) else "✗ NOT AVAILABLE"
            spatialite_len = len(self.spatialite_source_geom) if (hasattr(self, 'spatialite_source_geom') and self.spatialite_source_geom) else 0
            logger.info(f"  Spatialite (WKT): {spatialite_status} ({spatialite_len} chars)")
            
            ogr_status = "✓ READY" if (hasattr(self, 'ogr_source_geom') and self.ogr_source_geom) else "✗ NOT AVAILABLE"
            ogr_features = self.ogr_source_geom.featureCount() if (hasattr(self, 'ogr_source_geom') and self.ogr_source_geom and isinstance(self.ogr_source_geom, QgsVectorLayer)) else 0
            logger.info(f"  OGR (Layer):      {ogr_status} ({ogr_features} features)")
            
            postgresql_status = "✓ READY" if (hasattr(self, 'postgresql_source_geom') and self.postgresql_source_geom) else "✗ NOT AVAILABLE"
            logger.info(f"  PostgreSQL (SQL): {postgresql_status}")
            
            # CRITICAL: If both Spatialite and OGR are not available, filtering will fail
            if not (hasattr(self, 'spatialite_source_geom') and self.spatialite_source_geom) and \
               not (hasattr(self, 'ogr_source_geom') and self.ogr_source_geom):
                logger.error("=" * 60)
                logger.error("❌ CRITICAL: NO SOURCE GEOMETRY AVAILABLE!")
                logger.error("=" * 60)
                logger.error("  → Both Spatialite (WKT) and OGR (Layer) geometries are None")
                logger.error("  → This will cause ALL layer filtering to FAIL")
                logger.error("  → Possible causes:")
                logger.error("    1. Source layer has no features")
                logger.error("    2. Source layer has no valid geometries")
                logger.error("    3. No features selected/filtered in source layer")
                logger.error("    4. Geometry preparation failed")
                logger.error("=" * 60)
            
            logger.info("=" * 60)

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
        # THREAD SAFETY FIX v2.3.9: Include filtering params for OGR detection
        task_parameters = {
            'task': self,
            'filter_type': getattr(self, 'filter_type', 'geometric'),
            'filtering': {
                'filter_type': getattr(self, 'filter_type', 'geometric')
            }
        }
        # CANCELLATION FIX v2.3.22: Pass cancel_check callback to executor
        # This allows parallel workers to check if task was canceled and stop immediately
        results = executor.filter_layers_parallel(
            all_layers, 
            self.execute_geometric_filtering,
            task_parameters,
            cancel_check=self.isCanceled
        )
        
        # Process results and update progress
        successful_filters = 0
        failed_filters = 0
        failed_layer_names = []  # Track names of failed layers for error message
        
        # DIAGNOSTIC: Log results for debugging
        logger.debug(f"_filter_all_layers_parallel: all_layers count={len(all_layers)}, results count={len(results)}")
        for idx, res in enumerate(results):
            logger.debug(f"  Result[{idx}]: {res.layer_name} → success={res.success}, error={res.error_message}")
        
        for i, (layer_tuple, result) in enumerate(zip(all_layers, results), 1):
            layer, layer_props = layer_tuple
            self.setDescription(f"Filtering layer {i}/{self.layers_count}: {layer.name()}")
            
            if result.success:
                successful_filters += 1
                logger.info(f"✅ {layer.name()} has been filtered → {layer.featureCount()} features")
            else:
                failed_filters += 1
                failed_layer_names.append(layer.name())
                error_msg = result.error_message if hasattr(result, 'error_message') else getattr(result, 'error', 'Unknown error')
                logger.error(f"❌ {layer.name()} - errors occurred during filtering: {error_msg}")
            
            progress_percent = int((i / self.layers_count) * 100)
            self.setProgress(progress_percent)
            
            if self.isCanceled():
                logger.warning(f"⚠️ Filtering canceled at layer {i}/{self.layers_count}")
                return False
        
        # DIAGNOSTIC: Summary of filtering results
        self._log_filtering_summary(successful_filters, failed_filters, failed_layer_names)
        
        # CRITICAL FIX: Return False if ANY filter failed to alert user
        # Store failed layer names for error message in finished()
        if failed_filters > 0:
            self._failed_layer_names = failed_layer_names
            logger.warning(f"⚠️ {failed_filters} layer(s) failed to filter (parallel mode) - returning False")
            logger.warning(f"   Failed layers: {', '.join(failed_layer_names[:5])}{'...' if len(failed_layer_names) > 5 else ''}")
            return False
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
        failed_layer_names = []  # Track names of failed layers for error message
        
        for layer_provider_type in self.layers:
            for layer, layer_props in self.layers[layer_provider_type]:
                # STABILITY FIX v2.3.9: Validate layer before any operations
                # This prevents crashes when layer becomes invalid during sequential filtering
                try:
                    if not is_valid_layer(layer):
                        logger.warning(f"⚠️ Layer {i}/{self.layers_count} is invalid - skipping")
                        failed_filters += 1
                        failed_layer_names.append(f"Layer_{i} (invalid)")
                        i += 1
                        continue
                    
                    layer_name = layer.name()
                    layer_feature_count = layer.featureCount()
                except (RuntimeError, AttributeError) as access_error:
                    logger.error(f"❌ Layer {i}/{self.layers_count} access error (C++ object deleted): {access_error}")
                    failed_filters += 1
                    failed_layer_names.append(f"Layer_{i} (deleted)")
                    i += 1
                    continue
                
                # Update task description with current progress
                self.setDescription(f"Filtering layer {i}/{self.layers_count}: {layer_name}")
                
                logger.info("")
                logger.info(f"🔄 FILTRAGE {i}/{self.layers_count}: {layer_name} ({layer_provider_type})")
                logger.info(f"   Features avant filtre: {layer_feature_count}")
                
                result = self.execute_geometric_filtering(layer_provider_type, layer, layer_props)
                
                # DIAGNOSTIC: Log result for debugging
                logger.debug(f"_filter_all_layers_sequential: {layer_name} → result={result}")
                
                if result:
                    successful_filters += 1
                    try:
                        final_count = layer.featureCount()
                        logger.info(f"✅ {layer_name} has been filtered → {final_count} features")
                    except (RuntimeError, AttributeError):
                        logger.info(f"✅ {layer_name} has been filtered (count unavailable)")
                else:
                    failed_filters += 1
                    failed_layer_names.append(layer_name)
                    logger.error(f"❌ {layer_name} - errors occurred during filtering")
                
                i += 1
                progress_percent = int((i / self.layers_count) * 100)
                self.setProgress(progress_percent)
                
                if self.isCanceled():
                    logger.warning(f"⚠️ Filtering canceled at layer {i}/{self.layers_count}")
                    return False
        
        # DIAGNOSTIC: Summary of filtering results
        self._log_filtering_summary(successful_filters, failed_filters, failed_layer_names)
        
        # CRITICAL FIX: Return False if ANY filter failed to alert user
        # Store failed layer names for error message in finished()
        if failed_filters > 0:
            self._failed_layer_names = failed_layer_names
            logger.warning(f"⚠️ {failed_filters} layer(s) failed to filter - returning False")
            logger.warning(f"   Failed layers: {', '.join(failed_layer_names[:5])}{'...' if len(failed_layer_names) > 5 else ''}")
            return False
        return True
    
    def _log_filtering_summary(self, successful_filters: int, failed_filters: int, failed_layer_names=None):
        """Log summary of filtering results.
        
        Args:
            successful_filters: Number of layers that filtered successfully
            failed_filters: Number of layers that failed to filter
            failed_layer_names: Optional list of names of layers that failed
        """
        if failed_layer_names is None:
            failed_layer_names = []
        logger.info("")
        logger.info("=" * 70)
        logger.info("📊 RÉSUMÉ DU FILTRAGE GÉOMÉTRIQUE")
        logger.info("=" * 70)
        logger.info(f"  Total couches: {self.layers_count}")
        logger.info(f"  ✅ Succès: {successful_filters}")
        logger.info(f"  ❌ Échecs: {failed_filters}")
        if failed_filters > 0:
            logger.info("")
            if failed_layer_names:
                logger.info("  ❌ COUCHES EN ÉCHEC:")
                for name in failed_layer_names[:10]:  # Show first 10
                    logger.info(f"     • {name}")
                if len(failed_layer_names) > 10:
                    logger.info(f"     ... et {len(failed_layer_names) - 10} autre(s)")
            logger.info("")
            logger.info("  💡 CONSEIL: Si des couches échouent avec le backend Spatialite:")
            logger.info("     → Vérifiez que les couches sont des GeoPackage/SQLite")
            logger.info("     → Les Shapefiles ne supportent pas les fonctions Spatialite")
            logger.info("     → Essayez le backend OGR (QGIS processing) pour ces couches")
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
        
        # Build unique provider list including source layer provider AND forced backends
        # CRITICAL FIX v2.4.1: Include forced backends in provider_list
        # Without this, forced backends won't have their source geometry prepared
        provider_list = self.provider_list + [self.param_source_provider_type]
        
        # Add any forced backends to ensure their geometry is prepared
        forced_backends = self.task_parameters.get('forced_backends', {})
        for layer_id, forced_backend in forced_backends.items():
            if forced_backend and forced_backend not in provider_list:
                logger.info(f"  → Adding forced backend '{forced_backend}' to provider_list")
                provider_list.append(forced_backend)
        
        provider_list = list(dict.fromkeys(provider_list))
        logger.info(f"  → Provider list for geometry preparation: {provider_list}")
        
        # Prepare geometries for all provider types
        # NOTE: This will use self.param_buffer_value set above
        if not self._prepare_geometries_by_provider(provider_list):
            # If self.message wasn't set by _prepare_geometries_by_provider, set a generic one
            if not hasattr(self, 'message') or not self.message:
                self.message = "Failed to prepare source geometries for distant layers filtering"
            logger.error(f"_prepare_geometries_by_provider failed: {self.message}")
            return False
        
        # Filter all layers with progress tracking
        logger.info("🚀 Starting _filter_all_layers_with_progress()...")
        result = self._filter_all_layers_with_progress()
        logger.info(f"📊 _filter_all_layers_with_progress() returned: {result}")
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
        
        # Get the actual geometry column name from the layer (default to 'geometry' if not set)
        geom_col = getattr(self, 'param_source_geom', None) or 'geometry'
        
        # 1. Convert QGIS spatial functions to PostGIS
        # Use the actual geometry column name from the layer
        spatial_conversions = {
            '$area': f'ST_Area("{geom_col}")',
            '$length': f'ST_Length("{geom_col}")',
            '$perimeter': f'ST_Perimeter("{geom_col}")',
            '$x': f'ST_X("{geom_col}")',
            '$y': f'ST_Y("{geom_col}")',
            '$geometry': f'"{geom_col}"',
            'buffer': 'ST_Buffer',
            'area': 'ST_Area',
            'length': 'ST_Length',
            'perimeter': 'ST_Perimeter',
        }
        
        for qgis_func, postgis_func in spatial_conversions.items():
            expression = expression.replace(qgis_func, postgis_func)
        
        # 2. Convert IF statements to CASE WHEN
        if expression.find('if') >= 0:
            expression = re.sub(r'if\s*\(\s*([^,]+),\s*([^,]+),\s*([^)]+)\)', r'CASE WHEN \1 THEN \2 ELSE \3 END', expression, flags=re.IGNORECASE)
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
        base_geom = '"{source_schema}"."{source_table}"."{source_geom}"'.format(
                                                                                source_schema=source_schema,
                                                                                source_table=source_table,
                                                                                source_geom=self.param_source_geom
                                                                                )
        
        # CENTROID OPTIMIZATION: Wrap geometry in ST_Centroid if enabled for source layer
        # This significantly speeds up queries for complex polygons (e.g., buildings)
        # CENTROID + BUFFER OPTIMIZATION v2.5.13: Combine centroid and buffer when both are enabled
        # Order: ST_Buffer(ST_Centroid(geom)) - buffer is applied to the centroid point
        # This allows filtering distant layers using a buffered zone around source layer centroids
        
        if self.param_buffer_expression is not None and self.param_buffer_expression != '':
            # Buffer expression mode (dynamic buffer from field/expression)

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
            # NOTE: Centroids are not supported with buffer expressions (materialized views)
            # because the view already contains buffered geometries
            if self.param_use_centroids_source_layer:
                logger.warning("⚠️ PostgreSQL: Centroid option ignored when using buffer expression (materialized view)")
            
        elif self.param_buffer_value is not None and self.param_buffer_value != 0:
            # Static buffer value mode

            self.param_buffer = self.param_buffer_value
            
            # CRITICAL FIX: For simple numeric buffer values, apply buffer directly in SQL
            # Don't create materialized views - just wrap geometry in ST_Buffer()
            # This is simpler and more efficient than creating a _dump view
            source_table = self.param_source_table
            source_schema = self.param_source_schema
            
            # Build ST_Buffer style parameters (quad_segs for segments, endcap for buffer type)
            buffer_type_mapping = {"Round": "round", "Flat": "flat", "Square": "square"}
            buffer_type_str = self.task_parameters["filtering"].get("buffer_type", "Round")
            endcap_style = buffer_type_mapping.get(buffer_type_str, "round")
            quad_segs = self.param_buffer_segments
            
            # Build style string for PostGIS ST_Buffer
            style_params = f"quad_segs={quad_segs}"
            if endcap_style != 'round':
                style_params += f" endcap={endcap_style}"
            
            # CENTROID + BUFFER: Determine the geometry to buffer
            # If centroid is enabled, buffer the centroid point instead of the full geometry
            if self.param_use_centroids_source_layer:
                geom_to_buffer = f'ST_Centroid("{source_schema}"."{source_table}"."{self.param_source_geom}")'
                logger.info(f"✓ PostgreSQL: Using ST_Centroid + ST_Buffer for source layer")
            else:
                geom_to_buffer = '"{source_schema}"."{source_table}"."{source_geom}"'.format(
                    source_schema=source_schema,
                    source_table=source_table,
                    source_geom=self.param_source_geom
                )
            
            # Build base ST_Buffer expression with style parameters
            base_buffer_expr = f"ST_Buffer({geom_to_buffer}, {self.param_buffer_value}, '{style_params}')"
            
            # CRITICAL FIX v2.5.6: Handle negative buffers (erosion) properly
            # Negative buffers can produce empty geometries which must be handled
            # with ST_MakeValid() and ST_IsEmpty() to prevent matching issues
            if self.param_buffer_value < 0:
                logger.info(f"📐 Applying NEGATIVE buffer (erosion): {self.param_buffer_value}m")
                logger.info(f"  🛡️ Wrapping in ST_MakeValid() + ST_IsEmpty check for empty geometry handling")
                validated_expr = f"ST_MakeValid({base_buffer_expr})"
                self.postgresql_source_geom = f"CASE WHEN ST_IsEmpty({validated_expr}) THEN NULL ELSE {validated_expr} END"
                logger.info(f"  📝 Generated expression: {self.postgresql_source_geom[:150]}...")
            else:
                self.postgresql_source_geom = base_buffer_expr
            
            buffer_type_desc = "expansion" if self.param_buffer_value > 0 else "erosion"
            centroid_desc = " (on centroids)" if self.param_use_centroids_source_layer else ""
            logger.info(f"✓ PostgreSQL source geom prepared with {self.param_buffer_value}m buffer ({buffer_type_desc}, endcap={endcap_style}, segments={quad_segs}){centroid_desc}")
            logger.debug(f"Using simple buffer: ST_Buffer with {self.param_buffer_value}m ({buffer_type_desc}){centroid_desc}")
        
        else:
            # No buffer - just apply centroid if enabled
            if self.param_use_centroids_source_layer:
                self.postgresql_source_geom = f"ST_Centroid({base_geom})"
                logger.info(f"✓ PostgreSQL: Using ST_Centroid for source layer geometry simplification")
            else:
                self.postgresql_source_geom = base_geom     

        

        logger.debug(f"prepare_postgresql_source_geom: {self.postgresql_source_geom}")     



    def _get_optimization_thresholds(self):
        """
        Get optimization thresholds configuration from task parameters or defaults.
        
        Returns:
            dict: Optimization thresholds with keys:
                - large_dataset_warning: int (feature count for performance warnings)
                - async_expression_threshold: int (feature count for async expressions)
                - update_extents_threshold: int (feature count for auto extent update)
                - centroid_optimization_threshold: int (feature count for centroid opt)
                - exists_subquery_threshold: int (WKT length for EXISTS mode)
                - parallel_processing_threshold: int (feature count for parallel)
                - progress_update_batch_size: int (features per progress update)
                - source_mv_fid_threshold: int (max FIDs for inline IN clause, above creates MV)
        """
        # Default values
        defaults = {
            'large_dataset_warning': 50000,
            'async_expression_threshold': 10000,
            'update_extents_threshold': 50000,
            'centroid_optimization_threshold': 5000,
            'exists_subquery_threshold': 100000,
            'parallel_processing_threshold': 100000,
            'progress_update_batch_size': 100,
            'source_mv_fid_threshold': 500  # v2.8.0: Create MV when source FIDs > 500
        }
        
        # Try to get from task_parameters
        if hasattr(self, 'task_parameters') and self.task_parameters:
            config = self.task_parameters.get('config', {})
            app_config = config.get('APP', {})
            settings = app_config.get('SETTINGS', {})
            opt_config = settings.get('OPTIMIZATION_THRESHOLDS', {})
            
            if opt_config:
                return {
                    'large_dataset_warning': opt_config.get('large_dataset_warning', {}).get('value', defaults['large_dataset_warning']),
                    'async_expression_threshold': opt_config.get('async_expression_threshold', {}).get('value', defaults['async_expression_threshold']),
                    'update_extents_threshold': opt_config.get('update_extents_threshold', {}).get('value', defaults['update_extents_threshold']),
                    'centroid_optimization_threshold': opt_config.get('centroid_optimization_threshold', {}).get('value', defaults['centroid_optimization_threshold']),
                    'exists_subquery_threshold': opt_config.get('exists_subquery_threshold', {}).get('value', defaults['exists_subquery_threshold']),
                    'parallel_processing_threshold': opt_config.get('parallel_processing_threshold', {}).get('value', defaults['parallel_processing_threshold']),
                    'progress_update_batch_size': opt_config.get('progress_update_batch_size', {}).get('value', defaults['progress_update_batch_size']),
                    'source_mv_fid_threshold': opt_config.get('source_mv_fid_threshold', {}).get('value', defaults['source_mv_fid_threshold'])
                }
        
        return defaults

    def _get_simplification_config(self):
        """
        Get geometry simplification configuration from task parameters or defaults.
        
        Returns:
            dict: Simplification configuration with keys:
                - enabled: bool
                - max_wkt_length: int
                - preserve_topology: bool
                - min_tolerance_meters: float
                - max_tolerance_meters: float
                - show_warnings: bool
        """
        # Default values
        defaults = {
            'enabled': True,
            'max_wkt_length': 100000,
            'preserve_topology': True,
            'min_tolerance_meters': 1.0,
            'max_tolerance_meters': 100.0,
            'show_warnings': True
        }
        
        # Try to get from task_parameters
        if hasattr(self, 'task_parameters') and self.task_parameters:
            config = self.task_parameters.get('config', {})
            app_config = config.get('APP', {})
            settings = app_config.get('SETTINGS', {})
            simp_config = settings.get('GEOMETRY_SIMPLIFICATION', {})
            
            if simp_config:
                return {
                    'enabled': simp_config.get('enabled', {}).get('value', defaults['enabled']),
                    'max_wkt_length': simp_config.get('max_wkt_length', {}).get('value', defaults['max_wkt_length']),
                    'preserve_topology': simp_config.get('preserve_topology', {}).get('value', defaults['preserve_topology']),
                    'min_tolerance_meters': simp_config.get('min_tolerance_meters', {}).get('value', defaults['min_tolerance_meters']),
                    'max_tolerance_meters': simp_config.get('max_tolerance_meters', {}).get('value', defaults['max_tolerance_meters']),
                    'show_warnings': simp_config.get('show_simplification_warnings', {}).get('value', defaults['show_warnings'])
                }
        
        return defaults

    def _get_wkt_precision(self, crs_authid: str = None) -> int:
        """
        Get appropriate WKT precision based on CRS units.
        
        v2.7.14: New method to optimize WKT size by reducing coordinate precision.
        
        For metric CRS (e.g., EPSG:2154 Lambert 93):
        - 2 decimal places = centimeter precision (sufficient for spatial filtering)
        - Reduces WKT size by ~60-70% vs default 17 decimals
        
        For geographic CRS (e.g., EPSG:4326 WGS84):
        - 8 decimal places = ~1mm precision at equator
        - Reduces WKT size by ~50% vs default 17 decimals
        
        Args:
            crs_authid: CRS authority ID (e.g., 'EPSG:2154', 'EPSG:4326')
                       If None, uses source_layer_crs_authid if available
        
        Returns:
            int: Number of decimal places for WKT coordinates
        """
        # Use instance CRS if not specified
        if crs_authid is None:
            crs_authid = getattr(self, 'source_layer_crs_authid', None)
        
        if not crs_authid:
            # Default to conservative precision for unknown CRS
            return 6
        
        # Check if geographic CRS
        try:
            srid = int(crs_authid.split(':')[1]) if ':' in crs_authid else int(crs_authid)
            # Geographic CRS: EPSG:4326, EPSG:4267, etc.
            is_geographic = srid == 4326 or (4000 <= srid < 5000)
        except (ValueError, IndexError):
            is_geographic = False
        
        if is_geographic:
            # Geographic: 8 decimals ≈ 1mm at equator
            return 8
        else:
            # Projected/metric: 2 decimals = 1cm precision
            return 2

    def _geometry_to_wkt(self, geometry, crs_authid: str = None) -> str:
        """
        Convert geometry to WKT with optimized precision based on CRS.
        
        v2.7.14: New method to generate compact WKT by using appropriate precision.
        
        Example: For EPSG:2154 (Lambert 93, meters), this reduces:
        - Input: 508746.09999999997671694 → Output: 508746.10
        - WKT size reduction: ~60-70%
        
        Args:
            geometry: QgsGeometry to convert
            crs_authid: CRS authority ID for precision selection
        
        Returns:
            str: WKT string with optimized precision
        """
        if geometry is None or geometry.isEmpty():
            return ""
        
        precision = self._get_wkt_precision(crs_authid)
        wkt = geometry.asWkt(precision)
        
        logger.debug(f"  📏 WKT precision: {precision} decimals (CRS: {crs_authid})")
        
        return wkt

    def _get_buffer_aware_tolerance(self, buffer_value, buffer_segments, buffer_type, extent_size, is_geographic=False):
        """
        Calculate optimal simplification tolerance based on buffer parameters.
        
        v2.7.11: New method to compute tolerance that respects buffer precision.
        
        The idea is that when a buffer is applied with specific segments/type parameters,
        the resulting geometry has a known precision. We can safely simplify up to that
        precision level without losing meaningful detail.
        
        For a buffer with N segments per quarter-circle:
        - Arc length per segment ≈ (π/2) * radius / N
        - Maximum error from simplification ≈ radius * (1 - cos(π/(2*N)))
        
        Args:
            buffer_value: Buffer distance in map units
            buffer_segments: Number of segments per quarter-circle (quad_segs)
            buffer_type: Buffer end cap type (0=round, 1=flat, 2=square)
            extent_size: Maximum extent dimension
            is_geographic: Whether CRS is geographic (degrees)
            
        Returns:
            float: Recommended simplification tolerance
        """
        import math
        
        abs_buffer = abs(buffer_value) if buffer_value else 0
        
        # Default tolerance if no buffer
        if abs_buffer == 0:
            base_tolerance = extent_size * 0.001
        else:
            # Calculate maximum angular error per segment
            # For N segments per quarter circle, each segment covers π/(2*N) radians
            angle_per_segment = math.pi / (2 * buffer_segments)
            
            # Maximum chord-to-arc error is: r * (1 - cos(θ/2))
            # where θ is the angle per segment
            max_arc_error = abs_buffer * (1 - math.cos(angle_per_segment / 2))
            
            # For flat/square endcaps, tolerance can be more aggressive
            # since the buffer edges are straight lines
            if buffer_type in [1, 2]:  # Flat or Square
                # Flat endcaps have no curves at ends, can simplify more
                tolerance_factor = 2.0
            else:  # Round
                # Round endcaps have curves, be more conservative
                tolerance_factor = 1.0
            
            # Base tolerance is the arc error (this is the inherent precision of the buffer)
            base_tolerance = max_arc_error * tolerance_factor
            
            # Log the calculation
            logger.info(f"  📐 Buffer-aware tolerance calculation:")
            logger.info(f"     buffer={buffer_value}m, segments={buffer_segments}, type={buffer_type}")
            logger.info(f"     angle_per_segment={math.degrees(angle_per_segment):.2f}°")
            logger.info(f"     max_arc_error={max_arc_error:.4f}m")
            logger.info(f"     base_tolerance={base_tolerance:.4f} ({'degrees' if is_geographic else 'map units'})")
        
        # Convert to degrees if geographic CRS
        if is_geographic:
            # 1 degree ≈ 111km at equator
            base_tolerance = base_tolerance / 111000.0
        
        return base_tolerance

    def _simplify_geometry_adaptive(self, geometry, max_wkt_length=None, crs_authid=None):
        """
        Simplify geometry adaptively to fit within WKT size limit while preserving topology.
        
        v2.7.6: New adaptive simplification algorithm that:
        1. Estimates optimal tolerance based on geometry extent and target size
        2. Uses topology-preserving simplification
        3. Progressively increases tolerance until target size is reached
        4. Never produces empty or invalid geometries
        5. Respects configuration parameters for tolerance limits
        
        v2.7.11: Enhanced to use buffer parameters (segments, type) for smarter tolerance.
        
        Args:
            geometry: QgsGeometry to simplify
            max_wkt_length: Maximum WKT string length (default from config, fallback 100KB)
            crs_authid: CRS authority ID for unit-aware simplification (e.g., 'EPSG:2154')
            
        Returns:
            QgsGeometry: Simplified geometry, or original if simplification fails/disabled
        """
        from qgis.core import QgsGeometry, QgsWkbTypes
        
        if not geometry or geometry.isEmpty():
            return geometry
        
        # Get configuration
        config = self._get_simplification_config()
        
        # Check if simplification is enabled
        if not config['enabled']:
            logger.debug(f"  Geometry simplification disabled in config")
            return geometry
        
        # Use configured max_wkt_length if not specified
        if max_wkt_length is None:
            max_wkt_length = config['max_wkt_length']
        
        # v2.7.14: Use optimized WKT precision for size calculation
        wkt_precision = self._get_wkt_precision(crs_authid)
        original_wkt = geometry.asWkt(wkt_precision)
        original_length = len(original_wkt)
        
        if original_length <= max_wkt_length:
            logger.debug(f"  Geometry already within limit ({original_length} chars)")
            return geometry
        
        if config['show_warnings']:
            logger.info(f"  🔧 Simplifying geometry: {original_length} chars → target {max_wkt_length} chars")
        
        # Calculate reduction ratio needed
        reduction_ratio = max_wkt_length / original_length
        logger.debug(f"  Reduction ratio needed: {reduction_ratio:.4f} ({(1-reduction_ratio)*100:.1f}% reduction)")
        
        # Get geometry extent to estimate appropriate tolerance
        extent = geometry.boundingBox()
        extent_size = max(extent.width(), extent.height())
        
        # Determine if CRS is geographic (degrees) or metric
        is_geographic = False
        if crs_authid:
            try:
                srid = int(crs_authid.split(':')[1]) if ':' in crs_authid else int(crs_authid)
                # EPSG:4326 and similar geographic CRS have small SRID numbers
                is_geographic = srid == 4326 or (srid < 5000 and srid > 4000)
            except (ValueError, IndexError):
                pass
        
        # Get tolerance limits from config
        min_tolerance = config['min_tolerance_meters']
        max_tolerance = config['max_tolerance_meters']
        
        # v2.7.13: For extremely large WKT, increase max_tolerance dynamically
        # If we need >99% reduction, we need to be more aggressive
        if reduction_ratio < 0.01:  # Need >99% reduction (e.g., 4.6M → 100K chars)
            # Scale max_tolerance based on how extreme the reduction is
            # For 4.6M → 100K, ratio = 0.022, so multiplier ≈ 45
            extreme_multiplier = 1.0 / reduction_ratio if reduction_ratio > 0 else 100
            max_tolerance = max_tolerance * min(extreme_multiplier, 100)  # Cap at 100x
            logger.info(f"  🔧 Extreme WKT size - increasing max_tolerance to {max_tolerance:.1f}m")
        
        # v2.7.11: Use buffer-aware tolerance if buffer parameters are available
        buffer_value = getattr(self, 'param_buffer_value', None)
        buffer_segments = getattr(self, 'param_buffer_segments', 5)
        buffer_type = getattr(self, 'param_buffer_type', 0)
        
        if buffer_value is not None and buffer_value != 0:
            # Calculate tolerance based on buffer precision
            buffer_tolerance = self._get_buffer_aware_tolerance(
                buffer_value=buffer_value,
                buffer_segments=buffer_segments,
                buffer_type=buffer_type,
                extent_size=extent_size,
                is_geographic=is_geographic
            )
            
            # Use buffer-aware tolerance as base, but scale based on reduction needed
            if reduction_ratio < 0.01:  # Need >99% reduction
                initial_tolerance = buffer_tolerance * 10
            elif reduction_ratio < 0.05:  # Need >95% reduction
                initial_tolerance = buffer_tolerance * 5
            elif reduction_ratio < 0.1:  # Need >90% reduction
                initial_tolerance = buffer_tolerance * 3
            elif reduction_ratio < 0.5:  # Need >50% reduction
                initial_tolerance = buffer_tolerance * 2
            else:
                initial_tolerance = buffer_tolerance
            
            logger.info(f"  🎯 Using buffer-aware tolerance: {buffer_tolerance:.6f} → scaled to {initial_tolerance:.6f}")
        else:
            # Fallback: Calculate initial tolerance based on extent and reduction needed
            if is_geographic:
                # Geographic CRS: convert meters to degrees (approximate)
                # 1 degree ≈ 111km at equator
                min_tolerance = min_tolerance / 111000.0
                max_tolerance = max_tolerance / 111000.0
                base_tolerance = extent_size * 0.0001  # Start with 0.01% of extent
            else:
                # Projected CRS: tolerance in map units (usually meters)
                base_tolerance = extent_size * 0.001  # Start with 0.1% of extent
            
            # Scale initial tolerance based on how much reduction is needed
            if reduction_ratio < 0.01:  # Need >99% reduction
                initial_tolerance = base_tolerance * 50
            elif reduction_ratio < 0.05:  # Need >95% reduction
                initial_tolerance = base_tolerance * 20
            elif reduction_ratio < 0.1:  # Need >90% reduction
                initial_tolerance = base_tolerance * 10
            elif reduction_ratio < 0.5:  # Need >50% reduction
                initial_tolerance = base_tolerance * 5
            else:
                initial_tolerance = base_tolerance
        
        # Convert tolerance limits if geographic
        if is_geographic:
            min_tolerance = config['min_tolerance_meters'] / 111000.0
            max_tolerance = config['max_tolerance_meters'] / 111000.0
        
        # Clamp to configured limits
        initial_tolerance = max(min_tolerance, min(initial_tolerance, max_tolerance))
        
        logger.info(f"  Initial tolerance: {initial_tolerance:.6f} ({'degrees' if is_geographic else 'map units'})")
        logger.info(f"  Tolerance limits: [{min_tolerance:.6f}, {max_tolerance:.6f}]")
        logger.info(f"  Extent size: {extent_size:.2f}")
        
        # Progressive simplification with topology preservation
        tolerance = initial_tolerance
        best_simplified = geometry
        best_wkt_length = original_length
        max_attempts = 15
        tolerance_multiplier = 2.0
        
        for attempt in range(max_attempts):
            # Check if we've exceeded max tolerance
            if tolerance > max_tolerance:
                logger.warning(f"  Reached max tolerance ({max_tolerance:.6f}) - stopping")
                break
            
            # Use QGIS simplify which is topology-aware for polygons
            simplified = geometry.simplify(tolerance)
            
            if simplified is None or simplified.isEmpty():
                logger.warning(f"  Attempt {attempt+1}: Simplification produced empty geometry at tolerance {tolerance:.6f}")
                # Try a smaller tolerance step
                tolerance *= 1.5
                continue
            
            # Validate geometry type is preserved
            if QgsWkbTypes.geometryType(simplified.wkbType()) != QgsWkbTypes.geometryType(geometry.wkbType()):
                logger.warning(f"  Attempt {attempt+1}: Geometry type changed, skipping")
                tolerance *= tolerance_multiplier
                continue
            
            # v2.7.14: Use optimized WKT precision
            simplified_wkt = simplified.asWkt(wkt_precision)
            wkt_length = len(simplified_wkt)
            reduction_pct = (1 - wkt_length / original_length) * 100
            
            logger.debug(f"  Attempt {attempt+1}: tolerance={tolerance:.6f}, {wkt_length} chars ({reduction_pct:.1f}% reduction)")
            
            # Track best result
            if wkt_length < best_wkt_length:
                best_simplified = simplified
                best_wkt_length = wkt_length
            
            if wkt_length <= max_wkt_length:
                if config['show_warnings']:
                    logger.info(f"  ✓ Simplified: {original_length} → {wkt_length} chars ({reduction_pct:.1f}% reduction)")
                    logger.info(f"  ✓ Final tolerance: {tolerance:.6f}")
                return simplified
            
            # Increase tolerance for next attempt
            tolerance *= tolerance_multiplier
        
        # Use best result even if not under limit
        final_reduction = (1 - best_wkt_length / original_length) * 100
        if best_wkt_length < original_length:
            if config['show_warnings']:
                logger.warning(f"  ⚠️ Could not reach target, using best result: {original_length} → {best_wkt_length} chars ({final_reduction:.1f}% reduction)")
            
            # v2.7.13: If still too large, try more aggressive fallbacks
            if best_wkt_length > max_wkt_length:
                logger.warning(f"  🔄 Trying aggressive fallbacks...")
                
                # FALLBACK 1: Convex Hull - fast and compact but loses concave details
                try:
                    convex_hull = geometry.convexHull()
                    if convex_hull and not convex_hull.isEmpty():
                        # v2.7.14: Use optimized WKT precision
                        hull_wkt = convex_hull.asWkt(wkt_precision)
                        if len(hull_wkt) <= max_wkt_length:
                            hull_reduction = (1 - len(hull_wkt) / original_length) * 100
                            logger.info(f"  ✓ Convex Hull fallback: {original_length} → {len(hull_wkt)} chars ({hull_reduction:.1f}% reduction)")
                            logger.warning(f"  ⚠️ Using Convex Hull - some precision lost for concave boundaries")
                            return convex_hull
                except Exception as e:
                    logger.debug(f"  Convex Hull fallback failed: {e}")
                
                # FALLBACK 2: Oriented Minimum Bounding Rectangle - even more compact
                try:
                    oriented_bbox = geometry.orientedMinimumBoundingBox()[0]
                    if oriented_bbox and not oriented_bbox.isEmpty():
                        # v2.7.14: Use optimized WKT precision
                        bbox_wkt = oriented_bbox.asWkt(wkt_precision)
                        if len(bbox_wkt) <= max_wkt_length:
                            bbox_reduction = (1 - len(bbox_wkt) / original_length) * 100
                            logger.info(f"  ✓ Oriented BBox fallback: {original_length} → {len(bbox_wkt)} chars ({bbox_reduction:.1f}% reduction)")
                            logger.warning(f"  ⚠️ Using Oriented Bounding Box - significant precision lost")
                            return oriented_bbox
                except Exception as e:
                    logger.debug(f"  Oriented BBox fallback failed: {e}")
                
                # FALLBACK 3: Simple Bounding Box as polygon - minimal but always works
                try:
                    bbox = geometry.boundingBox()
                    if not bbox.isEmpty():
                        from qgis.core import QgsGeometry, QgsRectangle
                        bbox_geom = QgsGeometry.fromRect(bbox)
                        if bbox_geom and not bbox_geom.isEmpty():
                            # v2.7.14: Use optimized WKT precision
                            bbox_wkt = bbox_geom.asWkt(wkt_precision)
                            bbox_reduction = (1 - len(bbox_wkt) / original_length) * 100
                            logger.info(f"  ✓ Bounding Box fallback: {original_length} → {len(bbox_wkt)} chars ({bbox_reduction:.1f}% reduction)")
                            logger.warning(f"  ⚠️ Using Bounding Box - maximum precision lost")
                            return bbox_geom
                except Exception as e:
                    logger.debug(f"  Bounding Box fallback failed: {e}")
            
            return best_simplified
        else:
            if config['show_warnings']:
                logger.warning(f"  ⚠️ Simplification failed, using original geometry")
            return geometry

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
        # CRITICAL FIX v2.4.10: Respect active subset filter on source layer
        # When source layer has a subsetString (e.g., "homecount > 5"), we must use ONLY filtered features
        # for geometric operations, not all features in the layer.
        
        # THREAD-SAFETY FIX v2.4.10: In background threads, subsetString() may return empty
        # even when the layer is filtered. Check task_parameters FIRST for reliable feature access.
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
        
        # Check task_features FIRST (passed from main thread, reliable across threads)
        task_features = self.task_parameters.get("task", {}).get("features", [])
        has_task_features = task_features and len(task_features) > 0
        
        logger.info(f"=== prepare_spatialite_source_geom DEBUG ===")
        logger.info(f"  has_task_features: {has_task_features} ({len(task_features) if task_features else 0} features)")
        logger.info(f"  has_subset: {has_subset}")
        logger.info(f"  has_selection: {has_selection}")
        logger.info(f"  is_field_based_mode: {is_field_based_mode}")
        if has_subset:
            logger.info(f"  Current subset: '{self.source_layer.subsetString()[:100]}'")
        
        # PRIORITY ORDER (v2.4.10):
        # 1. task_features from task_parameters (most reliable, thread-safe)
        # 2. getFeatures() with subset (if has_subset is True)
        # 3. selectedFeatures() (if has_selection)
        # 4. is_field_based_mode
        # 5. FALLBACK: getFeatures() (all features)
        
        if has_task_features and not is_field_based_mode:
            # PRIORITY MODE v2.4.10: Use task_features passed from main thread (thread-safe)
            logger.info(f"=== prepare_spatialite_source_geom (TASK PARAMS PRIORITY MODE) ===")
            logger.info(f"  Using {len(task_features)} features from task_parameters (thread-safe)")
            
            # Validate features (filter out invalid/empty ones)
            # v2.7.4: Improved thread-safety - copy geometry to local QgsGeometry object
            # to prevent access violations when original feature becomes invalid
            valid_features = []
            validation_errors = 0
            skipped_no_geometry = 0  # v2.7.16: Track features skipped due to no/empty geometry
            for i, f in enumerate(task_features):
                try:
                    if f is None or f == "":
                        continue
                    if hasattr(f, 'hasGeometry') and hasattr(f, 'geometry'):
                        if f.hasGeometry() and not f.geometry().isEmpty():
                            valid_features.append(f)
                            # Log first few features for diagnostic (DEBUG level)
                            if i < 3 and logger.isEnabledFor(logging.DEBUG):
                                geom = f.geometry()
                                bbox = geom.boundingBox()
                                logger.debug(f"  Feature[{i}]: type={geom.wkbType()}, bbox=({bbox.xMinimum():.1f},{bbox.yMinimum():.1f})-({bbox.xMaximum():.1f},{bbox.yMaximum():.1f})")
                        else:
                            # v2.7.16: Count as validation failure - feature has no valid geometry
                            skipped_no_geometry += 1
                            logger.debug(f"  Skipping feature[{i}] without valid geometry")
                    elif f:
                        valid_features.append(f)
                except Exception as e:
                    validation_errors += 1
                    logger.warning(f"  Feature[{i}] validation error (thread-safety): {e}")
                    continue
            
            # v2.7.16: Consider both types of failures for recovery logic
            total_failures = validation_errors + skipped_no_geometry
            
            features = valid_features
            logger.info(f"  Valid features after filtering: {len(features)}")
            if skipped_no_geometry > 0:
                logger.warning(f"  Skipped {skipped_no_geometry} features with no/empty geometry (thread-safety issue?)")
            
            # v2.7.4: CRITICAL FIX - If ALL task_features failed validation but we had features,
            # this is likely a thread-safety issue. DO NOT fall back to all features!
            # Instead, use feature_fids to refetch, or source selection as fallback.
            # v2.7.16: Use total_failures which includes both exceptions AND empty geometries
            recovery_attempted = False  # v2.7.16: Flag to prevent fallback to all features
            if len(features) == 0 and len(task_features) > 0 and total_failures > 0:
                recovery_attempted = True  # Mark that we tried recovery - don't use all features as fallback!
                logger.error(f"  ❌ ALL {len(task_features)} task_features failed validation ({validation_errors} errors, {skipped_no_geometry} no geometry)")
                logger.error(f"  This is likely a thread-safety issue - features became invalid")
                
                # v2.7.16: PRIORITY 1 - Use feature_fids to refetch features from source layer
                # This is more reliable than selection which may have changed
                feature_fids = self.task_parameters.get("task", {}).get("feature_fids", [])
                logger.info(f"  → Looking for feature_fids in task_parameters['task']: found {len(feature_fids) if feature_fids else 0}")
                if not feature_fids:
                    # Also check root level of task_parameters
                    feature_fids = self.task_parameters.get("feature_fids", [])
                    logger.info(f"  → Looking for feature_fids at root level: found {len(feature_fids) if feature_fids else 0}")
                
                if feature_fids and len(feature_fids) > 0 and self.source_layer:
                    logger.info(f"  → Attempting recovery using {len(feature_fids)} feature_fids")
                    try:
                        from qgis.core import QgsFeatureRequest
                        request = QgsFeatureRequest().setFilterFids(feature_fids)
                        features = list(self.source_layer.getFeatures(request))
                        if len(features) > 0:
                            logger.debug(f"  ✓ v2.7.15: Recovered {len(features)} features using FIDs (thread-safety fix)")
                        else:
                            logger.warning(f"  ⚠️ FID recovery returned 0 features")
                    except Exception as e:
                        logger.error(f"  ❌ FID recovery failed: {e}")
                
                # v2.7.15: PRIORITY 2 - Try source layer selection as fallback
                if len(features) == 0 and self.source_layer and self.source_layer.selectedFeatureCount() > 0:
                    logger.info(f"  → Attempting recovery from source layer selection")
                    try:
                        features = list(self.source_layer.selectedFeatures())
                        logger.info(f"  ✓ Recovered {len(features)} features from source layer selection")
                    except Exception as e:
                        logger.error(f"  ❌ Could not recover selection: {e}")
                
                # v2.7.16: If still no features, DON'T fall back to all features!
                if len(features) == 0:
                    logger.error(f"  ❌ Could not recover any features - filter will fail")
                    logger.error(f"  This prevents incorrect filtering with all {self.source_layer.featureCount()} features")
                    from qgis.core import QgsMessageLog, Qgis
                    QgsMessageLog.logMessage(
                        f"v2.7.16: BLOCKING fallback to all {self.source_layer.featureCount()} features - would cause incorrect filter!",
                        "FilterMate", Qgis.Warning
                    )
            elif len(features) == 0 and len(task_features) > 0:
                # Features were provided but ALL failed validation without errors
                # This shouldn't happen, but if it does, mark as recovery attempted
                recovery_attempted = True
                logger.warning(f"  ⚠️ All {len(task_features)} task_features failed validation without errors")
        elif has_subset and not has_task_features:
            # Fallback: use getFeatures() which respects subsetString
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
            # FINAL FALLBACK: No task_features, no subset, no selection, no field mode
            # Use all features from source layer (this should be rare)
            logger.info(f"=== prepare_spatialite_source_geom (FALLBACK MODE) ===")
            logger.info(f"  No specific mode matched - using all source features")
            features = list(self.source_layer.getFeatures())
            logger.info(f"  Retrieved {len(features)} features from source layer")
        
        # FALLBACK: If features list is empty, use all visible features from source layer
        # FIX v2.4.22: Also check for expression/subset that should be applied
        # v2.7.16: BUT NOT if we already tried recovery from FIDs - that means task_features were provided
        # but became invalid, and using all features would give WRONG results!
        if not features or len(features) == 0:
            # v2.7.16: Check if recovery was already attempted - don't fallback to all features!
            if 'recovery_attempted' in dir() and recovery_attempted:
                logger.error(f"  ❌ BLOCKING fallback to all features - recovery was attempted")
                logger.error(f"  task_features were provided but became invalid")
                logger.error(f"  Using all {self.source_layer.featureCount()} features would give WRONG results!")
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"v2.7.16: Filter aborted - cannot recover source features. Verify selection before filtering.",
                    "FilterMate", Qgis.Critical
                )
                self.spatialite_source_geom = None
                return
            logger.warning(f"  ⚠️ No features provided! Checking for expression fallback...")
            
            # Check if we have an expression that should filter the source layer
            filter_expression = getattr(self, 'expression', None)
            new_subset = getattr(self, 'param_source_new_subset', None)
            
            filter_to_use = None
            if filter_expression and filter_expression.strip():
                filter_to_use = filter_expression
                logger.info(f"  → Found expression: '{filter_expression[:80]}...'")
            elif new_subset and new_subset.strip():
                filter_to_use = new_subset
                logger.info(f"  → Found new_subset: '{new_subset[:80]}...'")
            
            if filter_to_use:
                # Use a feature request with expression to filter features
                from qgis.core import QgsFeatureRequest, QgsExpression
                
                try:
                    expr = QgsExpression(filter_to_use)
                    if not expr.hasParserError():
                        request = QgsFeatureRequest(expr)
                        features = list(self.source_layer.getFeatures(request))
                        logger.info(f"  → Expression fallback: {len(features)} features")
                    else:
                        logger.warning(f"  → Expression parse error: {expr.parserErrorString()}")
                        features = list(self.source_layer.getFeatures())
                except Exception as e:
                    logger.warning(f"  → Expression fallback failed: {e}")
                    features = list(self.source_layer.getFeatures())
            else:
                logger.info(f"  → Source layer: {self.source_layer.name()}")
                logger.info(f"  → Source layer feature count: {self.source_layer.featureCount()}")
                logger.info(f"  → Source layer subset: '{self.source_layer.subsetString()[:100] if self.source_layer.subsetString() else ''}'")
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
            if self.param_buffer_value and self.param_buffer_value != 0:
                if 'LineString' in wkt_type or 'Line' in wkt_type:
                    logger.error("❌ CACHE BUG DETECTED!")
                    buffer_type_str = "expansion" if self.param_buffer_value > 0 else "erosion"
                    logger.error(f"  Expected: Polygon/MultiPolygon (with {self.param_buffer_value}m {buffer_type_str} buffer)")
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
                
                # CENTROID OPTIMIZATION: Convert source layer geometry to centroid if enabled
                # This significantly speeds up queries for complex polygons (e.g., buildings)
                if self.param_use_centroids_source_layer:
                    centroid = geom_copy.centroid()
                    if centroid and not centroid.isEmpty():
                        geom_copy = centroid
                        logger.debug(f"Converted source layer geometry to centroid")
                
                if geom_copy.isMultipart():
                    geom_copy.convertToSingleType()
                    
                if self.has_to_reproject_source_layer is True:
                    geom_copy.transform(transform)
                    
                # SPATIALITE OPTIMIZATION: Buffer is now applied via ST_Buffer() in SQL expression
                # This avoids GeometryCollection issues from QGIS buffer and uses native Spatialite functions
                # The buffer value is passed to build_expression() which adds ST_Buffer() to the SQL
                # Supports both positive (expand) and negative (shrink/erode) buffers
                if self.param_buffer_value is not None and self.param_buffer_value != 0:
                    buffer_type_str = "expansion" if self.param_buffer_value > 0 else "erosion (shrink)"
                    logger.info(f"Buffer of {self.param_buffer_value}m ({buffer_type_str}) will be applied via ST_Buffer() in SQL")
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
        
        # v2.6.3: Force 2D geometry by dropping Z/M values for Spatialite compatibility
        # Spatialite's GeomFromText() may have issues with very large WKT containing Z coordinates
        # (e.g., "MultiLineString Z (...)" format from QGIS asWkt())
        # This ensures consistent behavior and avoids "parse error" from GeomFromText
        from qgis.core import QgsWkbTypes
        if QgsWkbTypes.hasZ(collected_geometry.wkbType()) or QgsWkbTypes.hasM(collected_geometry.wkbType()):
            original_type = get_geometry_type_name(collected_geometry)
            # Create a new 2D geometry from WKB
            # First, get the 2D variant of the WKB type
            wkb_2d = QgsWkbTypes.flatType(collected_geometry.wkbType())
            
            # Use constGet() to access the underlying abstract geometry
            abstract_geom = collected_geometry.constGet()
            if abstract_geom:
                # Clone and drop Z/M values
                cloned = abstract_geom.clone()
                cloned.dropZValue()
                cloned.dropMValue()
                collected_geometry = QgsGeometry(cloned)
                logger.info(f"  ✓ Dropped Z/M values: {original_type} → {get_geometry_type_name(collected_geometry)}")
            else:
                logger.warning(f"  Could not access geometry internals to drop Z/M, keeping {original_type}")
        
        # v2.7.14: Use optimized WKT precision based on CRS units
        # This reduces WKT size by 60-70% for metric CRS (e.g., EPSG:2154)
        crs_authid = self.source_layer_crs_authid if hasattr(self, 'source_layer_crs_authid') else None
        wkt = self._geometry_to_wkt(collected_geometry, crs_authid)
        
        # Log the final geometry type
        geom_type = wkt.split('(')[0].strip() if '(' in wkt else 'Unknown'
        logger.info(f"  Final collected geometry type: {geom_type}")
        logger.info(f"  Number of geometries collected: {len(geometries)}")
        logger.info(f"  📏 WKT with optimized precision: {len(wkt):,} chars")
        
        # v2.7.6: Use adaptive simplification for very large geometries
        # This preserves topology while achieving the target WKT size
        # Get threshold from configuration
        thresholds = self._get_optimization_thresholds()
        MAX_WKT_LENGTH = thresholds['exists_subquery_threshold']
        
        if len(wkt) > MAX_WKT_LENGTH:
            logger.warning(f"  ⚠️ WKT too long ({len(wkt)} chars > {MAX_WKT_LENGTH} max)")
            logger.debug(f"  v2.7.13 WKT: Simplifying {len(wkt):,} chars → target {MAX_WKT_LENGTH:,}")
            
            # Use new adaptive simplification that estimates optimal tolerance
            simplified = self._simplify_geometry_adaptive(
                collected_geometry,
                max_wkt_length=MAX_WKT_LENGTH,
                crs_authid=self.source_layer_crs_authid if hasattr(self, 'source_layer_crs_authid') else None
            )
            
            if simplified and not simplified.isEmpty():
                # v2.7.14: Use optimized WKT precision for simplified geometry too
                simplified_wkt = self._geometry_to_wkt(simplified, crs_authid)
                reduction_pct = (1 - len(simplified_wkt) / len(wkt)) * 100
                
                logger.debug(f"v2.7.14 WKT: Simplified to {len(simplified_wkt):,} chars ({reduction_pct:.1f}% reduction)")
                
                if len(simplified_wkt) <= MAX_WKT_LENGTH:
                    logger.info(f"  ✓ Adaptive simplification succeeded: {len(wkt)} → {len(simplified_wkt)} chars ({reduction_pct:.1f}% reduction)")
                    wkt = simplified_wkt
                    collected_geometry = simplified
                else:
                    logger.warning(f"  ⚠️ Adaptive simplification reduced but not enough: {len(wkt)} → {len(simplified_wkt)} chars")
                    # v2.7.13: Still use the simplified geometry - better than nothing
                    wkt = simplified_wkt
                    collected_geometry = simplified
                    QgsMessageLog.logMessage(
                        f"v2.7.14 WKT: Still large ({len(simplified_wkt):,} chars) - may impact performance",
                        "FilterMate", Qgis.Warning
                    )
            else:
                logger.warning(f"  ⚠️ Simplification failed, using original ({len(wkt)} chars)")
                logger.warning(f"  Consider using PostgreSQL backend for better handling of complex geometries")
                QgsMessageLog.logMessage(
                    f"v2.7.13 WKT: Simplification failed - using original ({len(wkt):,} chars)",
                    "FilterMate", Qgis.Warning
                )
        
        # Escape single quotes for SQL
        wkt_escaped = wkt.replace("'", "''")
        self.spatialite_source_geom = wkt_escaped

        logger.info(f"  WKT length: {len(self.spatialite_source_geom)} chars")
        logger.debug(f"prepare_spatialite_source_geom WKT preview: {self.spatialite_source_geom[:200]}...")
        logger.info(f"=== prepare_spatialite_source_geom END ===") 
        
        # v2.6.5: Store WKT in task_parameters for backend R-tree optimization
        # This allows the Spatialite backend to use permanent source tables with R-tree indexes
        # for large WKT geometries (>50KB), dramatically improving performance
        if hasattr(self, 'task_parameters') and self.task_parameters:
            if 'infos' not in self.task_parameters:
                self.task_parameters['infos'] = {}
            self.task_parameters['infos']['source_geom_wkt'] = wkt_escaped
            logger.info(f"  ✓ WKT stored in task_parameters for backend optimization ({len(wkt_escaped)} chars)")
        
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

    def _create_memory_layer_from_features(self, features, crs, layer_name="from_features"):
        """
        Create memory layer from a list of QgsFeature objects.
        
        This is used when task_parameters contains features but the source layer
        has no visible features (e.g., after filtering).
        
        Args:
            features: List of QgsFeature objects
            crs: QgsCoordinateReferenceSystem for the memory layer
            layer_name: Name for the memory layer
            
        Returns:
            QgsVectorLayer: Memory layer containing the features, or None on failure
        """
        if not features or len(features) == 0:
            logger.warning(f"_create_memory_layer_from_features: No features provided")
            return None
        
        # Find first feature with valid geometry to determine type
        geom_type = None
        for feat in features:
            if feat.hasGeometry() and not feat.geometry().isEmpty():
                geom_type = QgsWkbTypes.displayString(feat.geometry().wkbType())
                break
        
        if not geom_type:
            logger.error(f"_create_memory_layer_from_features: No features with valid geometry")
            return None
        
        # Get CRS auth ID
        crs_authid = crs.authid() if hasattr(crs, 'authid') else str(crs)
        
        logger.info(f"_create_memory_layer_from_features: Creating {geom_type} layer with {len(features)} features")
        
        # Create memory layer
        memory_layer = QgsVectorLayer(f"{geom_type}?crs={crs_authid}", layer_name, "memory")
        
        if not memory_layer.isValid():
            logger.error(f"_create_memory_layer_from_features: Failed to create memory layer")
            return None
        
        # Copy fields from first feature if available
        first_valid = features[0]
        if first_valid.fields().count() > 0:
            memory_layer.dataProvider().addAttributes(first_valid.fields())
            memory_layer.updateFields()
        
        # Add features with geometry validation
        features_to_add = []
        skipped = 0
        
        for feat in features:
            if not feat.hasGeometry() or feat.geometry().isEmpty():
                skipped += 1
                continue
            
            geom = feat.geometry()
            
            # Try to repair geometry
            try:
                repaired = geom.makeValid()
                if repaired and not repaired.isEmpty():
                    new_feat = QgsFeature(feat)
                    new_feat.setGeometry(repaired)
                    features_to_add.append(new_feat)
                elif validate_geometry(geom):
                    features_to_add.append(QgsFeature(feat))
                else:
                    skipped += 1
            except Exception:
                if validate_geometry(geom):
                    features_to_add.append(QgsFeature(feat))
                else:
                    skipped += 1
        
        if not features_to_add:
            logger.error(f"_create_memory_layer_from_features: All {len(features)} features had invalid geometries")
            return None
        
        memory_layer.dataProvider().addFeatures(features_to_add)
        memory_layer.updateExtents()
        
        if skipped > 0:
            logger.warning(f"  ⚠️ Skipped {skipped} features with invalid geometries")
        
        logger.info(f"  ✓ Created memory layer with {memory_layer.featureCount()} features")
        
        # Create spatial index
        self._verify_and_create_spatial_index(memory_layer, layer_name)
        
        return memory_layer

    def _convert_layer_to_centroids(self, layer):
        """
        Convert a layer's geometries to their centroids.
        
        This optimization significantly speeds up spatial queries for complex
        polygons (e.g., buildings with many vertices) by using simple point
        geometries instead.
        
        Args:
            layer: QgsVectorLayer with polygon/line geometries
            
        Returns:
            QgsVectorLayer: Memory layer with point geometries (centroids),
                           or None on failure
        """
        if not layer or not layer.isValid():
            logger.warning("_convert_layer_to_centroids: Invalid input layer")
            return None
        
        # Create point memory layer
        crs_authid = layer.crs().authid()
        centroid_layer = QgsVectorLayer(f"Point?crs={crs_authid}", "centroids", "memory")
        
        if not centroid_layer.isValid():
            logger.error("_convert_layer_to_centroids: Failed to create memory layer")
            return None
        
        # Copy fields
        if layer.fields().count() > 0:
            centroid_layer.dataProvider().addAttributes(layer.fields())
            centroid_layer.updateFields()
        
        # Convert geometries to centroids
        features_to_add = []
        skipped = 0
        
        for feature in layer.getFeatures():
            if not feature.hasGeometry() or feature.geometry().isEmpty():
                skipped += 1
                continue
            
            geom = feature.geometry()
            centroid = geom.centroid()
            
            if centroid and not centroid.isEmpty():
                new_feat = QgsFeature(feature)
                new_feat.setGeometry(centroid)
                features_to_add.append(new_feat)
            else:
                skipped += 1
        
        if not features_to_add:
            logger.error("_convert_layer_to_centroids: No valid centroids created")
            return None
        
        centroid_layer.dataProvider().addFeatures(features_to_add)
        centroid_layer.updateExtents()
        
        if skipped > 0:
            logger.warning(f"  ⚠️ Skipped {skipped} features during centroid conversion")
        
        logger.debug(f"_convert_layer_to_centroids: Created {centroid_layer.featureCount()} centroid features")
        
        return centroid_layer

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
            'SEGMENTS': int(self.param_buffer_segments),  # Use configured buffer segments (default: 5)
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
        
        NOTE: Negative buffers (erosion) may produce empty geometries if the buffer
        distance is larger than the feature width. This is expected behavior.
        
        Args:
            layer: Source layer
            buffer_dist: Buffer distance (can be negative for erosion)
            
        Returns:
            tuple: (list of geometries, valid_count, invalid_count, eroded_count)
        """
        geometries = []
        valid_features = 0
        invalid_features = 0
        eroded_features = 0  # Count features that eroded completely
        
        is_negative_buffer = buffer_dist < 0
        logger.debug(f"Buffering features: layer type={layer.geometryType()}, wkb type={layer.wkbType()}, buffer_dist={buffer_dist}")
        
        if is_negative_buffer:
            logger.info(f"⚠️ Applying NEGATIVE BUFFER (erosion) of {buffer_dist}m - some features may disappear completely")
        
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
                # Use param_buffer_segments for precision (default: 5)
                segments = getattr(self, 'param_buffer_segments', 5)
                buffered_geom = safe_buffer(geom, buffer_dist, segments)
                
                if buffered_geom is not None:
                    geometries.append(buffered_geom)
                    valid_features += 1
                    logger.debug(f"Feature {idx}: Buffered geometry accepted")
                else:
                    # Check if this is complete erosion (expected for negative buffers)
                    if is_negative_buffer:
                        logger.debug(f"Feature {idx}: Completely eroded (negative buffer)")
                        eroded_features += 1
                    else:
                        logger.warning(f"Feature {idx}: safe_buffer returned None")
                        invalid_features += 1
                    
            except Exception as buffer_error:
                logger.warning(f"Feature {idx}: Buffer operation failed: {buffer_error}")
                invalid_features += 1
        
        # Enhanced logging for negative buffers
        if is_negative_buffer and eroded_features > 0:
            logger.info(f"📊 Buffer négatif résultats: {valid_features} features conservées, {eroded_features} complètement érodées, {invalid_features} invalides")
            if valid_features == 0:
                logger.warning(f"⚠️ TOUTES les features ont été érodées par le buffer de {buffer_dist}m! Réduisez la distance du buffer.")
        else:
            logger.debug(f"Manual buffer results: {valid_features} valid, {invalid_features} invalid features")
        
        return geometries, valid_features, invalid_features, eroded_features

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
        geometries, valid_features, invalid_features, eroded_features = self._buffer_all_features(layer, buffer_dist)
        
        # MODIFIED: Accept result even with 0 valid geometries (return empty layer instead of error)
        if not geometries:
            # Enhanced warning message for negative buffers
            if buffer_dist < 0:
                logger.warning(
                    f"⚠️ Buffer négatif ({buffer_dist}m) a complètement érodé toutes les géométries. "
                    f"Total: {feature_count}, Valides: {valid_features}, Érodées: {eroded_features}, Invalides: {invalid_features}"
                )
                # THREAD SAFETY FIX v2.5.6: Store warning for display in finished()
                # Cannot call iface.messageBar() from worker thread - would cause crash
                self.warning_messages.append(
                    f"Le buffer négatif de {buffer_dist}m a complètement érodé toutes les géométries. Réduisez la distance du buffer."
                )
            else:
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
        
        # Also check task_features early for diagnostic
        task_features_early = self.task_parameters.get("task", {}).get("features", [])
        # CRITICAL FIX v2.4.16: Properly validate QgsFeature objects
        # Old filter: [f for f in task_features_early if f and f != ""]
        # This missed invalid features that are truthy but don't have geometry
        #
        # FIX v2.4.22: More robust validation with detailed logging
        # Thread safety issue: QgsFeature objects may become invalid when passed
        # between threads. We need to catch exceptions during validation.
        valid_task_features_early = []
        invalid_count = 0
        for f in task_features_early:
            if f is None or f == "":
                continue
            # Check if it's a QgsFeature with geometry
            try:
                if hasattr(f, 'hasGeometry') and hasattr(f, 'geometry'):
                    if f.hasGeometry():
                        geom = f.geometry()
                        if geom is not None and not geom.isEmpty():
                            valid_task_features_early.append(f)
                        else:
                            invalid_count += 1
                            logger.debug(f"  Skipping feature with empty geometry: id={f.id() if hasattr(f, 'id') else 'unknown'}")
                    else:
                        invalid_count += 1
                        logger.debug(f"  Skipping feature without geometry: id={f.id() if hasattr(f, 'id') else 'unknown'}")
                elif f:
                    # Non-QgsFeature truthy value (e.g., feature ID)
                    valid_task_features_early.append(f)
            except (RuntimeError, AttributeError) as e:
                invalid_count += 1
                logger.warning(f"  ⚠️ Feature access error (thread-safety issue?): {e}")
        
        if invalid_count > 0:
            logger.warning(f"  ⚠️ {invalid_count} task features were invalid or had no geometry")
        
        # v2.7.15: If ALL task_features failed validation, try to recover using feature_fids
        if len(valid_task_features_early) == 0 and len(task_features_early) > 0 and invalid_count > 0:
            logger.warning(f"  ⚠️ ALL {len(task_features_early)} task_features failed validation (thread-safety issue)")
            
            # Try to recover using feature_fids
            feature_fids = self.task_parameters.get("task", {}).get("feature_fids", [])
            if not feature_fids:
                feature_fids = self.task_parameters.get("feature_fids", [])
            
            if feature_fids and len(feature_fids) > 0 and layer:
                logger.info(f"  → v2.7.15: Attempting FID recovery with {len(feature_fids)} FIDs")
                try:
                    from qgis.core import QgsFeatureRequest, QgsMessageLog, Qgis
                    request = QgsFeatureRequest().setFilterFids(feature_fids)
                    recovered_features = list(layer.getFeatures(request))
                    if len(recovered_features) > 0:
                        valid_task_features_early = recovered_features
                        logger.debug(f"  ✓ v2.7.15 OGR: Recovered {len(recovered_features)} features using FIDs")
                except Exception as e:
                    logger.error(f"  ❌ FID recovery failed: {e}")
        
        logger.info(f"=== prepare_ogr_source_geom DEBUG ===")
        logger.info(f"  Source layer name: {layer.name() if layer else 'None'}")
        logger.info(f"  Source layer valid: {layer.isValid() if layer else False}")
        logger.info(f"  Source layer feature count: {layer.featureCount() if layer else 0}")
        logger.info(f"  has_subset: {has_subset}")
        logger.info(f"  has_selection: {has_selection}")
        logger.info(f"  is_field_based_mode: {is_field_based_mode}")
        logger.info(f"  valid_task_features count: {len(valid_task_features_early)}")
        if has_subset:
            logger.info(f"  Current subset: '{layer.subsetString()[:100]}'")
        
        # DIAGNOSTIC: Log for debugging
        logger.debug(
            f"prepare_ogr_source_geom: layer={layer.name() if layer else 'None'}, "
            f"features={layer.featureCount() if layer else 0}, "
            f"has_subset={has_subset}, has_selection={has_selection}, "
            f"task_features={len(valid_task_features_early)}"
        )
        
        # CRITICAL: If task_features are provided, they should take precedence!
        # This handles single selection by FID mode
        if valid_task_features_early and len(valid_task_features_early) > 0:
            logger.info(f"=== prepare_ogr_source_geom (TASK PARAMS MODE - PRIORITY) ===")
            logger.info(f"  PRIORITY: Using {len(valid_task_features_early)} features from task_parameters")
            
            # DIAGNOSTIC: Log for debugging
            logger.debug(
                f"OGR TASK PARAMS MODE (PRIORITY): {len(valid_task_features_early)} features from task_parameters"
            )
            
            # DIAGNOSTIC v2.4.17: Log geometry details of task features before creating memory layer
            logger.debug(f"OGR TASK PARAMS: {len(valid_task_features_early)} features to use")
            # Only log first 3 features at DEBUG level to reduce verbosity
            if logger.isEnabledFor(logging.DEBUG):
                for idx, feat in enumerate(valid_task_features_early[:3]):
                    if hasattr(feat, 'geometry') and feat.hasGeometry():
                        geom = feat.geometry()
                        geom_type = geom.type()
                        bbox = geom.boundingBox()
                        logger.debug(
                            f"  Feature[{idx}]: type={geom_type}, bbox=({bbox.xMinimum():.1f},{bbox.yMinimum():.1f})-({bbox.xMaximum():.1f},{bbox.yMaximum():.1f})"
                        )
                    else:
                        logger.debug(f"  Feature[{idx}]: NO GEOMETRY or type={type(feat).__name__}")
                if len(valid_task_features_early) > 3:
                    logger.debug(f"  ... and {len(valid_task_features_early) - 3} more features")
            
            # Create memory layer from task features
            layer = self._create_memory_layer_from_features(valid_task_features_early, layer.crs(), "source_from_task")
            if layer:
                logger.info(f"  ✓ Memory layer created with {layer.featureCount()} features")
                # Log extent at DEBUG level
                extent = layer.extent()
                logger.debug(
                    f"  Memory layer extent: ({extent.xMinimum():.1f},{extent.yMinimum():.1f})-({extent.xMaximum():.1f},{extent.yMaximum():.1f})"
                )
            else:
                logger.error(f"  ✗ Failed to create memory layer from task features, using original layer")
                layer = self.source_layer
        elif has_subset or has_selection:
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
        else:
            # DIRECT MODE: No task_features, no subset, no selection, no field-based mode
            #
            # FIX v2.4.22: Check if we have an expression that should filter the source layer
            # This handles the case where setSubsetString() from a background thread didn't
            # take effect immediately (thread-safety issue).
            #
            # Try multiple fallback strategies:
            # 1. Check if self.expression was set during execute_source_layer_filtering()
            # 2. Check if param_source_new_subset was set
            # 3. Use all features as last resort
            
            filter_expression = getattr(self, 'expression', None)
            new_subset = getattr(self, 'param_source_new_subset', None)
            
            # Determine if we should filter
            should_filter = False
            filter_to_use = None
            
            if filter_expression and filter_expression.strip():
                should_filter = True
                filter_to_use = filter_expression
                logger.info(f"=== prepare_ogr_source_geom (EXPRESSION FALLBACK MODE) ===")
                logger.info(f"  ⚠️ No subset detected but self.expression exists")
                logger.info(f"  Expression: '{filter_expression[:80]}...'")
            elif new_subset and new_subset.strip():
                should_filter = True
                filter_to_use = new_subset
                logger.info(f"=== prepare_ogr_source_geom (SUBSET FALLBACK MODE) ===")
                logger.info(f"  ⚠️ No subset detected but param_source_new_subset exists")
                logger.info(f"  New subset: '{new_subset[:80]}...'")
            
            if should_filter and filter_to_use:
                # Use a feature request with expression to filter features
                from qgis.core import QgsFeatureRequest, QgsExpression
                
                try:
                    expr = QgsExpression(filter_to_use)
                    if expr.hasParserError():
                        logger.warning(f"  Expression parse error: {expr.parserErrorString()}")
                        logger.warning(f"  Falling back to all features")
                    else:
                        request = QgsFeatureRequest(expr)
                        filtered_features = list(layer.getFeatures(request))
                        
                        if len(filtered_features) > 0:
                            logger.info(f"  ✓ Filtered to {len(filtered_features)} features using expression")
                            
                            # Create memory layer from filtered features
                            layer = self._create_memory_layer_from_features(
                                filtered_features, layer.crs(), "source_expr_filtered"
                            )
                            if layer:
                                logger.info(f"  ✓ Memory layer created with {layer.featureCount()} features")
                                logger.debug(f"OGR EXPRESSION FALLBACK: Using {layer.featureCount()} features (filtered from expression)")
                            else:
                                logger.error(f"  ✗ Failed to create memory layer, using original layer")
                                layer = self.source_layer
                        else:
                            logger.warning(f"  ⚠️ Expression returned 0 features, using original layer")
                            layer = self.source_layer
                except Exception as e:
                    logger.error(f"  Expression filtering failed: {e}")
                    layer = self.source_layer
            else:
                logger.info(f"=== prepare_ogr_source_geom (DIRECT MODE) ===")
                logger.info(f"  No task features, subset, selection, or field-based mode detected")
                logger.info(f"  Source layer: {layer.name()}")
                logger.info(f"  Source layer feature count: {layer.featureCount()}")
                
                # DIAGNOSTIC: Log to QGIS Message Panel
                QgsMessageLog.logMessage(
                    f"OGR DIRECT MODE: Using {layer.featureCount()} features from source layer",
                    "FilterMate", Qgis.Warning
                )
        
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
        # CRITICAL FIX v2.5.2: Only skip buffer when using Spatialite backend for SQL-based buffer
        # Do NOT skip if using OGR backend directly (even if spatialite_source_geom exists for other layers)
        #
        # IMPORTANT: Buffer must be applied in ONE place only to avoid double-buffering:
        # - Spatialite backend: Buffer via ST_Buffer() in SQL (backend.build_expression applies it)
        # - OGR backend: Buffer via QGIS Processing (here OR in apply_filter)
        # - PostgreSQL backend: Buffer via ST_Buffer() in SQL
        #
        # The ogr_source_geom layer is used by OGR backend's apply_filter method
        # Buffer is applied there via _apply_buffer() using the buffer_value param from build_expression
        # So we should NOT apply buffer here for OGR layers - let apply_filter handle it
        #
        # Skip buffer in prepare_ogr only if it will be applied via SQL (Spatialite fallback mode)
        is_spatialite_fallback = hasattr(self, '_spatialite_fallback_mode') and self._spatialite_fallback_mode
        
        if buffer_distance is not None and not is_spatialite_fallback:
            # Buffer will be applied in OGR backend's apply_filter via _apply_buffer()
            # This is the correct place because OGR uses QGIS Processing algorithms
            logger.info(f"Buffer of {buffer_distance}m will be applied in OGR backend's apply_filter")
        elif buffer_distance is not None and is_spatialite_fallback:
            logger.info(f"Buffer of {buffer_distance}m will be applied via ST_Buffer() in Spatialite SQL")
        
        # REMOVED: Don't apply buffer here, let OGR apply_filter handle it via _apply_buffer()
        # This ensures buffer is applied with correct parameters and error handling
        
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
        
        # CENTROID OPTIMIZATION: Convert source layer geometries to centroids if enabled
        # This significantly speeds up queries for complex polygons (e.g., buildings)
        if self.param_use_centroids_source_layer:
            logger.info("OGR: Applying centroid transformation for source layer geometry simplification")
            centroid_layer = self._convert_layer_to_centroids(layer)
            if centroid_layer and centroid_layer.isValid() and centroid_layer.featureCount() > 0:
                layer = centroid_layer
                logger.info(f"  ✓ Converted source layer to centroids: {layer.featureCount()} point features")
            else:
                logger.warning("  ⚠️ Source layer centroid conversion failed, using original geometries")
        
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


    # DEPRECATED v2.3.13: This method is no longer called - expression building
    # is now handled by postgresql_backend.build_expression().
    # Keeping for reference but should be removed in a future version.
    def _build_postgis_predicates(self, postgis_predicates, layer_props, param_has_to_reproject_layer, param_layer_crs_authid):
        """
        Build PostGIS spatial predicates array for geometric filtering.
        
        DEPRECATED: Not currently used. Expression building is now handled by
        postgresql_backend.build_expression() which properly wraps table references
        in EXISTS subqueries.
        
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


    def _build_combined_filter_expression(self, new_expression, old_subset, combine_operator, layer_props=None):
        """
        Combine new filter expression with existing subset using specified operator.
        
        OPTIMIZATION v2.8.0: Uses CombinedQueryOptimizer to detect and reuse
        materialized views from previous filter operations, providing 10-50x
        speedup for successive filters on large datasets.
        
        Args:
            new_expression: New filter expression to apply
            old_subset: Existing subset string from layer
            combine_operator: SQL operator ('AND', 'OR', 'NOT')
            layer_props: Optional layer properties for optimization context
            
        Returns:
            str: Combined filter expression (optimized when possible)
        """
        if not old_subset or not combine_operator:
            return new_expression
        
        # CRITICAL: Sanitize old_subset to remove non-boolean display expressions
        # Display expressions like coalesce("field",'<NULL>') cause PostgreSQL type errors
        old_subset = self._sanitize_subset_string(old_subset)
        if not old_subset:
            return new_expression
        
        # OPTIMIZATION v2.8.0: Try to optimize combined expression
        # This is especially effective when old_subset contains a materialized view reference
        # and new_expression is a spatial predicate (EXISTS with ST_Intersects, etc.)
        try:
            optimizer = get_combined_query_optimizer()
            result = optimizer.optimize_combined_expression(
                old_subset=old_subset,
                new_expression=new_expression,
                combine_operator=combine_operator,
                layer_props=layer_props
            )
            
            if result.success:
                logger.info(
                    f"✓ Combined expression optimized ({result.optimization_type.name}): "
                    f"~{result.estimated_speedup:.1f}x speedup expected"
                )
                return result.optimized_expression
        except Exception as e:
            # Log but don't fail - fall back to original logic
            logger.warning(f"Combined query optimization failed, using fallback: {e}")
        
        # FALLBACK: Original combination logic
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
        # CRITICAL FIX v2.5.11: For PostgreSQL EXISTS mode, we MUST include the source
        # layer's filter to ensure the EXISTS query only considers the filtered
        # source features. Without this, EXISTS queries the ENTIRE source table!
        #
        # The previous fix (v2.3.15) set source_filter=None thinking "featureCount reflects
        # the subset" - but that's WRONG for EXISTS because PostgreSQL doesn't know about
        # QGIS's subsetString. The EXISTS query goes directly to PostgreSQL.
        #
        # v2.5.12 FIX: Pass the ENTIRE source subsetString to EXISTS, not just spatial
        # clauses. The subsetString contains ALL legitimate filter conditions:
        # - Spatial filters (ST_Intersects with emprise)
        # - Attribute filters from exploring (SELECT CASE for custom expressions)
        # - Any other user-defined filters
        #
        # Note: Style rules from renderers are NOT in subsetString - they're handled
        # separately by QGIS rendering engine. So we can safely use the full filter.
        source_filter = None
        
        # For PostgreSQL EXISTS mode, use entire source layer subsetString
        if backend.get_backend_name() == 'PostgreSQL':
            source_subset = self.source_layer.subsetString() if self.source_layer else None
            
            # CRITICAL FIX v2.7.10: Check if source_subset contains patterns that would be SKIPPED
            # in postgresql_backend.build_expression(). If so, we should NOT use it as source_filter
            # because it would be skipped anyway, leaving no filter and matching ALL features.
            # Instead, fall through to generate filter from task_features.
            #
            # Patterns that get skipped:
            # - EXISTS( or EXISTS ( - geometric filter from previous FilterMate operation
            # - __source - already adapted filter
            # - "filter_mate_temp"."mv_" - materialized view reference (except mv_src_sel_)
            skip_source_subset = False
            if source_subset:
                source_subset_upper = source_subset.upper()
                skip_source_subset = any(pattern in source_subset_upper for pattern in [
                    '__SOURCE',
                    'EXISTS(',
                    'EXISTS ('
                ])
                if not skip_source_subset:
                    # Also check for MV references (except source selection MVs which are allowed)
                    import re
                    # v2.8.0: Use negative lookahead to exclude mv_src_sel_ (source selection MVs)
                    skip_source_subset = bool(re.search(
                        r'IN\s*\(\s*SELECT.*FROM\s+["\']?filter_mate_temp["\']?\s*\.\s*["\']?.*mv_(?!.*src_sel_)',
                        source_subset,
                        re.IGNORECASE | re.DOTALL
                    ))
                
                if skip_source_subset:
                    logger.info(f"⚠️ PostgreSQL EXISTS: Source subset contains patterns that would be skipped")
                    logger.info(f"   Subset preview: '{source_subset[:100]}...'")
                    logger.info(f"   → Falling through to generate filter from task_features instead")
            
            # CRITICAL FIX v2.8.1: Check for task_features FIRST before using source_subset!
            # When user selects specific features (e.g., 9 roads out of 161), task_features
            # contains those 9 features. We MUST use those, not the source_subset which
            # contains the filter from previous operation (e.g., 161 roads from first filter).
            #
            # Priority order:
            # 1. task_features (user's current selection) - ALWAYS takes priority
            # 2. source_subset (existing layer filter) - only if no selection
            task_features = self.task_parameters.get("task", {}).get("features", [])
            use_task_features = task_features and len(task_features) > 0
            
            if use_task_features:
                # PRIORITY: Generate filter from task_features (user's selected features)
                # This ensures the second filter uses the 9 selected features, not the 161 from previous filter
                logger.debug(f"🎯 PostgreSQL EXISTS: Using {len(task_features)} task_features (selection priority)")
                
                # Get the primary key field name (usually 'fid', 'id', or 'gid')
                pk_field = None
                if self.source_layer:
                    try:
                        # Try to get primary key from provider
                        pk_attrs = self.source_layer.primaryKeyAttributes()
                        if pk_attrs:
                            fields = self.source_layer.fields()
                            pk_field = fields[pk_attrs[0]].name()
                    except Exception:
                        pass
                
                # Fallback: try common PK names
                if not pk_field:
                    for common_pk in ['fid', 'id', 'gid', 'ogc_fid']:
                        if self.source_layer and self.source_layer.fields().indexOf(common_pk) >= 0:
                            pk_field = common_pk
                            break
                
                if pk_field:
                    # Extract feature IDs from task_features
                    fids = []
                    for f in task_features:
                        try:
                            # task_features are QgsFeature objects
                            # CRITICAL: Use attribute(pk_field) NOT id()!
                            # f.id() returns QGIS internal FID which may differ from DB primary key
                            if hasattr(f, 'attribute'):
                                fid_val = f.attribute(pk_field)
                                if fid_val is not None:
                                    fids.append(fid_val)
                                else:
                                    # Fallback to QGIS FID if attribute is null
                                    # This shouldn't happen but provides safety
                                    if hasattr(f, 'id'):
                                        fids.append(f.id())
                            elif hasattr(f, 'id'):
                                # Legacy fallback for non-QgsFeature objects
                                fids.append(f.id())
                            elif isinstance(f, dict) and pk_field in f:
                                fids.append(f[pk_field])
                        except Exception as e:
                            logger.debug(f"  Could not extract ID from feature: {e}")
                    
                    if fids:
                        # Get source table name for qualification
                        # CRITICAL: Use param_source_table (actual DB table name), not layer.name() (display name)
                        # e.g., layer.name()="Distribution Cluster" but param_source_table="distribution_clusters"
                        source_table_name = getattr(self, 'param_source_table', None)
                        if not source_table_name and self.source_layer:
                            # Fallback: try to get from layer URI
                            try:
                                from qgis.core import QgsDataSourceUri
                                uri = QgsDataSourceUri(self.source_layer.source())
                                source_table_name = uri.table()
                            except Exception:
                                source_table_name = self.source_layer.name()
                        
                        # v2.8.0: Check if we should create a MV for large source selections
                        # This optimizes EXISTS subqueries by avoiding inline IN(...) with thousands of FIDs
                        thresholds = self._get_optimization_thresholds()
                        source_mv_fid_threshold = thresholds.get('source_mv_fid_threshold', 500)
                        
                        if len(fids) > source_mv_fid_threshold:
                            # Large source selection: create MV for better performance
                            logger.info(f"🗄️ v2.8.0: Source selection ({len(fids)} FIDs) > threshold ({source_mv_fid_threshold})")
                            logger.info(f"   → Creating temporary MV for optimized EXISTS query")
                            
                            # Get geometry field name
                            source_geom_field = getattr(self, 'param_source_geom', None)
                            if not source_geom_field and self.source_layer:
                                try:
                                    uri = QgsDataSourceUri(self.source_layer.source())
                                    source_geom_field = uri.geometryColumn() or 'geom'
                                except Exception:
                                    source_geom_field = 'geom'
                            
                            # Create MV using backend method
                            from ..backends.postgresql_backend import PostgreSQLGeometricFilter
                            pg_backend = PostgreSQLGeometricFilter(self.task_parameters)
                            
                            mv_ref = pg_backend.create_source_selection_mv(
                                layer=self.source_layer,
                                fids=fids,
                                pk_field=pk_field,
                                geom_field=source_geom_field
                            )
                            
                            if mv_ref:
                                # Use MV reference in source_filter
                                # The EXISTS subquery will use: __source."pk" IN (SELECT pk FROM mv_ref)
                                # This is MUCH faster than inline IN(...) with thousands of values
                                source_filter = f'"{source_table_name}"."{pk_field}" IN (SELECT pk FROM {mv_ref})'
                                
                                # Store MV reference for cleanup
                                if not hasattr(self, '_source_selection_mvs'):
                                    self._source_selection_mvs = []
                                self._source_selection_mvs.append(mv_ref)
                                
                                logger.debug(f"   ✓ MV created: {mv_ref}")
                                logger.debug(f"   → v2.8.0: Using source selection MV ({len(fids)} features) for EXISTS optimization")
                            else:
                                # MV creation failed, fall back to inline IN clause
                                logger.warning(f"   ⚠️ MV creation failed, using inline IN clause (may be slow)")
                                fids_str = ', '.join(str(fid) for fid in fids)
                                if source_table_name:
                                    source_filter = f'"{source_table_name}"."{pk_field}" IN ({fids_str})'
                                else:
                                    source_filter = f'"{pk_field}" IN ({fids_str})'
                        else:
                            # Small source selection: use inline IN clause (fast enough)
                            # CRITICAL FIX v2.7.9: Prefix with source table name for _adapt_filter_for_subquery
                            # Without table prefix, the filter "fid" IN (135) is ambiguous in EXISTS subquery
                            # because both source and target tables may have a "fid" column.
                            fids_str = ', '.join(str(fid) for fid in fids)
                            
                            if source_table_name:
                                # Use qualified column name: "table"."column"
                                source_filter = f'"{source_table_name}"."{pk_field}" IN ({fids_str})'
                            else:
                                # Fallback: unqualified (may still be ambiguous)
                                source_filter = f'"{pk_field}" IN ({fids_str})'
                        
                        logger.debug(f"🎯 PostgreSQL EXISTS: Generated selection filter from {len(fids)} features")
                        logger.debug(f"   v2.7.9: Generated qualified source filter: {source_filter[:80]}...")
                    else:
                        logger.warning(f"⚠️ PostgreSQL EXISTS: Could not extract feature IDs from task_features")
                else:
                    logger.warning(f"⚠️ PostgreSQL EXISTS: Could not determine primary key field for source layer")
            
            elif source_subset and not skip_source_subset:
                # No task_features selection - use the existing source subset filter
                source_filter = source_subset
                logger.info(f"🎯 PostgreSQL EXISTS: Using full source filter ({len(source_filter)} chars)")
                logger.debug(f"   Source filter preview: '{source_filter[:100]}...'")
            elif skip_source_subset and source_subset and self.source_layer:
                # CRITICAL FIX v2.8.3: Handle cascading geometric filters
                # When source_subset contains EXISTS/MV patterns from a previous filter,
                # we can't use it directly. But the source layer IS filtered - we just need
                # to generate a new filter from the currently visible features.
                #
                # Example scenario:
                # 1. First filter: commune -> routes (sets EXISTS filter on routes)
                # 2. Second filter: routes with buffer -> other layers
                #    - source_subset = "EXISTS (...)" from step 1 -> skip_source_subset = True
                #    - task_features = empty (user didn't manually select routes)
                #    - Without this fix: source_filter = None -> all routes used!
                #    - With this fix: generate filter from currently visible routes (411 in this case)
                logger.info(f"🔄 PostgreSQL EXISTS: Generating filter from currently visible source features")
                logger.info(f"   → Source layer has filtered subset but it contains unadaptable patterns")
                logger.info(f"   → Fetching visible feature IDs to create new source_filter")
                
                try:
                    # Get primary key field
                    pk_field = None
                    try:
                        pk_attrs = self.source_layer.primaryKeyAttributes()
                        if pk_attrs:
                            fields = self.source_layer.fields()
                            pk_field = fields[pk_attrs[0]].name()
                    except Exception:
                        pass
                    
                    if not pk_field:
                        for common_pk in ['fid', 'id', 'gid', 'ogc_fid']:
                            if self.source_layer.fields().indexOf(common_pk) >= 0:
                                pk_field = common_pk
                                break
                    
                    if pk_field:
                        # Fetch all visible features (respects the active subset)
                        visible_fids = []
                        for feature in self.source_layer.getFeatures():
                            try:
                                fid_val = feature.attribute(pk_field)
                                if fid_val is not None:
                                    visible_fids.append(fid_val)
                            except Exception:
                                pass
                        
                        if visible_fids:
                            # Get source table name
                            source_table_name = getattr(self, 'param_source_table', None)
                            if not source_table_name:
                                try:
                                    from qgis.core import QgsDataSourceUri
                                    uri = QgsDataSourceUri(self.source_layer.source())
                                    source_table_name = uri.table()
                                except Exception:
                                    source_table_name = self.source_layer.name()
                            
                            # Check if we should use MV for large selections
                            thresholds = self._get_optimization_thresholds()
                            source_mv_fid_threshold = thresholds.get('source_mv_fid_threshold', 500)
                            
                            if len(visible_fids) > source_mv_fid_threshold:
                                # Large selection: create MV for performance
                                logger.info(f"   → {len(visible_fids)} visible features > threshold ({source_mv_fid_threshold})")
                                logger.info(f"   → Creating temporary MV for optimized EXISTS query")
                                
                                source_geom_field = getattr(self, 'param_source_geom', None)
                                if not source_geom_field:
                                    try:
                                        uri = QgsDataSourceUri(self.source_layer.source())
                                        source_geom_field = uri.geometryColumn() or 'geom'
                                    except Exception:
                                        source_geom_field = 'geom'
                                
                                from ..backends.postgresql_backend import PostgreSQLGeometricFilter
                                pg_backend = PostgreSQLGeometricFilter(self.task_parameters)
                                mv_ref = pg_backend.create_source_selection_mv(
                                    layer=self.source_layer,
                                    fids=visible_fids,
                                    pk_field=pk_field,
                                    geom_field=source_geom_field
                                )
                                
                                if mv_ref:
                                    source_filter = f'"{source_table_name}"."{pk_field}" IN (SELECT pk FROM {mv_ref})'
                                    if not hasattr(self, '_source_selection_mvs'):
                                        self._source_selection_mvs = []
                                    self._source_selection_mvs.append(mv_ref)
                                    logger.info(f"   ✓ Created MV for {len(visible_fids)} visible features")
                                else:
                                    # MV failed, use inline IN clause
                                    fids_str = ', '.join(str(fid) for fid in visible_fids)
                                    source_filter = f'"{source_table_name}"."{pk_field}" IN ({fids_str})'
                                    logger.warning(f"   ⚠️ MV creation failed, using inline IN clause")
                            else:
                                # Small selection: use inline IN clause
                                fids_str = ', '.join(str(fid) for fid in visible_fids)
                                if source_table_name:
                                    source_filter = f'"{source_table_name}"."{pk_field}" IN ({fids_str})'
                                else:
                                    source_filter = f'"{pk_field}" IN ({fids_str})'
                            
                            logger.info(f"   ✓ Generated source_filter from {len(visible_fids)} visible features")
                            logger.debug(f"   → Filter preview: '{source_filter[:100]}...'")
                        else:
                            logger.warning(f"   ⚠️ No visible features found in source layer!")
                    else:
                        logger.warning(f"   ⚠️ Could not determine primary key field for source layer")
                except Exception as e:
                    logger.error(f"   ❌ Failed to generate filter from visible features: {e}")
                    import traceback
                    logger.debug(f"   Traceback: {traceback.format_exc()}")
            else:
                logger.debug(f"Geometric filtering: Source layer has no subsetString and no selection")
        else:
            logger.debug(f"Geometric filtering: Non-PostgreSQL backend, source_filter=None")
        
        # REMOVED: Old logic that picked up source layer filter including style rules
        # if hasattr(self, 'param_source_new_subset') and self.param_source_new_subset:
        #     source_filter = self.param_source_new_subset
        # elif hasattr(self, 'expression') and self.expression:
        #     source_filter = self.expression
        
        # Get source feature count and WKT for simplified PostgreSQL expressions
        source_wkt = None
        source_srid = None
        source_feature_count = None
        
        # For PostgreSQL, provide WKT for small datasets (simpler expression)
        if backend.get_backend_name() == 'PostgreSQL':
            # CRITICAL FIX v2.7.3: Use SELECTED/FILTERED feature count, not total table count!
            # Priority order:
            # 1. task_features from task_parameters (selected features from main thread)
            # 2. ogr_source_geom feature count (if available, contains filtered features)
            # 3. source_layer.featureCount() (fallback - respects subset but NOT manual selection)
            #
            # This ensures use_simple_wkt is True for small selections (e.g., 1 commune out of 930)
            task_features = self.task_parameters.get("task", {}).get("features", [])
            if task_features and len(task_features) > 0:
                source_feature_count = len(task_features)
                logger.info(f"PostgreSQL: Using task_features count: {source_feature_count} selected features")
            elif hasattr(self, 'ogr_source_geom') and self.ogr_source_geom:
                if isinstance(self.ogr_source_geom, QgsVectorLayer):
                    source_feature_count = self.ogr_source_geom.featureCount()
                    logger.debug(f"PostgreSQL: Using ogr_source_geom feature count: {source_feature_count}")
                else:
                    # ogr_source_geom exists but is not a layer (might be a geometry)
                    source_feature_count = 1  # Assume single geometry
                    logger.debug(f"PostgreSQL: ogr_source_geom is {type(self.ogr_source_geom).__name__}, assuming 1 feature")
            else:
                # Fallback to original source layer count
                source_feature_count = self.source_layer.featureCount()
                logger.debug(f"PostgreSQL: Using source_layer feature count (fallback): {source_feature_count}")
            
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
                # DIAGNOSTIC v2.7.3
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"v2.7.3: PostgreSQL will use WKT mode (count={source_feature_count}, wkt_len={len(source_wkt)}, srid={source_srid})",
                    "FilterMate", Qgis.Info
                )
            else:
                # DIAGNOSTIC v2.7.3: WKT not available - this is expected for PostgreSQL EXISTS mode
                # PostgreSQL uses source_filter with EXISTS subquery instead of WKT, so this is informational only
                logger.debug(
                    f"PostgreSQL: spatialite_source_geom not available (expected for EXISTS mode with source_filter)"
                )
        
        # Phase 4: Check expression cache before building
        layer = layer_props.get('layer')
        layer_id = layer.id() if layer and hasattr(layer, 'id') else None
        
        if layer_id and self.expr_cache:
            # Compute cache key
            source_hash = self.expr_cache.compute_source_hash(source_geom)
            buffer_value = self.param_buffer_value if hasattr(self, 'param_buffer_value') else None
            provider_type = backend.get_backend_name().lower()
            
            # v2.5.19: Include source_filter hash in cache key for PostgreSQL EXISTS mode
            # This ensures cache invalidation when source filter changes (e.g., refiltering)
            # Without this, cached expressions would use stale source filters in EXISTS queries
            source_filter_hash = None
            if source_filter:
                import hashlib
                source_filter_hash = hashlib.md5(source_filter.encode()).hexdigest()[:16]
                logger.debug(f"  Cache: source_filter_hash={source_filter_hash} (filter length: {len(source_filter)})")
            
            # v2.5.14: Include use_centroids in cache key to invalidate when centroid option changes
            use_centroids_distant = self.param_use_centroids_distant_layers if hasattr(self, 'param_use_centroids_distant_layers') else False
            use_centroids_source = self.param_use_centroids_source_layer if hasattr(self, 'param_use_centroids_source_layer') else False
            cache_key = self.expr_cache.get_cache_key(
                layer_id=layer_id,
                predicates=self.current_predicates,
                buffer_value=buffer_value,
                source_geometry_hash=source_hash,
                provider_type=provider_type,
                source_filter_hash=source_filter_hash,  # v2.5.19: Include for refilter cache invalidation
                use_centroids=use_centroids_distant,  # v2.5.14: Include centroid flag for distant layers
                use_centroids_source=use_centroids_source  # v2.5.15: Include centroid flag for source layer
            )
            
            # Try to get cached expression
            cached_expression = self.expr_cache.get(cache_key)
            if cached_expression:
                logger.info(f"✓ Expression cache HIT for {layer.name() if layer else 'unknown'}")
                return cached_expression
        else:
            cache_key = None
        
        # Log buffer values being passed to backend
        passed_buffer_value = self.param_buffer_value if hasattr(self, 'param_buffer_value') else None
        passed_buffer_expression = self.param_buffer_expression if hasattr(self, 'param_buffer_expression') else None
        passed_use_centroids_distant = self.param_use_centroids_distant_layers if hasattr(self, 'param_use_centroids_distant_layers') else False
        
        # v2.7.0: OPTIMIZATION - Check for pre-approved optimizations from UI
        # Optimizations are now handled BEFORE task launch via user confirmation dialog
        # This ensures user consent is always obtained before applying optimizations
        if not passed_use_centroids_distant:
            # Check if optimization was pre-approved for this layer
            approved_optimizations = getattr(self, 'approved_optimizations', {})
            layer_id = layer.id() if layer else None
            
            if layer_id and layer_id in approved_optimizations:
                layer_opts = approved_optimizations[layer_id]
                if layer_opts.get('use_centroid', False):
                    passed_use_centroids_distant = True
                    logger.info(f"🎯 USER-APPROVED OPTIMIZATION: Centroid mode for {layer.name()}")
            
            # Fallback: Auto-detection (only if auto_apply is enabled)
            # This only triggers if user has disabled "ask before apply" in settings
            if not passed_use_centroids_distant and getattr(self, 'auto_apply_optimizations', False):
                try:
                    from ..backends.factory import get_optimization_plan, AUTO_OPTIMIZER_AVAILABLE
                    if AUTO_OPTIMIZER_AVAILABLE and layer:
                        # Get optimization recommendations
                        source_wkt_len = len(source_wkt) if source_wkt else 0
                        # v2.7.x: Pass buffer parameters to optimizer
                        has_buffer = passed_buffer_value is not None and passed_buffer_value != 0
                        optimization_plan = get_optimization_plan(
                            target_layer=layer,
                            source_layer=self.source_layer if hasattr(self, 'source_layer') else None,
                            source_wkt_length=source_wkt_len,
                            predicates=self.current_predicates,
                            user_requested_centroids=None,  # None = auto-detect
                            has_buffer=has_buffer,
                            buffer_value=passed_buffer_value if passed_buffer_value else 0.0
                        )
                        
                        if optimization_plan:
                            if optimization_plan.final_use_centroids:
                                passed_use_centroids_distant = True
                                logger.info(f"🎯 AUTO-OPTIMIZATION: Centroid mode enabled for {layer.name()}")
                                logger.info(f"   Reason: {optimization_plan.recommendations[0].reason if optimization_plan.recommendations else 'auto-detected'}")
                                logger.info(f"   Expected speedup: ~{optimization_plan.estimated_total_speedup:.1f}x")
                            
                            # v2.7.x: Apply buffer simplification optimization if recommended
                            if optimization_plan.final_simplify_tolerance and optimization_plan.final_simplify_tolerance > 0:
                                # Update task_parameters to enable simplification
                                if hasattr(self, 'task_parameters') and self.task_parameters:
                                    filtering_params = self.task_parameters.get("filtering", {})
                                    # Only apply if not already set by user
                                    if not filtering_params.get("has_simplify_tolerance", False):
                                        filtering_params["has_simplify_tolerance"] = True
                                        filtering_params["simplify_tolerance"] = optimization_plan.final_simplify_tolerance
                                        self.task_parameters["filtering"] = filtering_params
                                        logger.info(f"🎯 AUTO-OPTIMIZATION: Buffer simplification enabled")
                                        logger.info(f"   Tolerance: {optimization_plan.final_simplify_tolerance:.2f}m")
                except Exception as e:
                    logger.debug(f"Auto-optimization check failed: {e}")
        
        logger.info(f"📐 _build_backend_expression - Buffer being passed to backend:")
        logger.info(f"  - param_buffer_value: {passed_buffer_value}")
        logger.info(f"  - param_buffer_expression: {passed_buffer_expression}")
        logger.info(f"  - use_centroids_distant_layers: {passed_use_centroids_distant}")
        if passed_buffer_value is not None and passed_buffer_value < 0:
            logger.info(f"  ⚠️ NEGATIVE BUFFER (erosion) will be passed: {passed_buffer_value}m")
        
        expression = backend.build_expression(
            layer_props=layer_props,
            predicates=self.current_predicates,
            source_geom=source_geom,
            buffer_value=passed_buffer_value,
            buffer_expression=passed_buffer_expression,
            source_filter=source_filter,
            source_wkt=source_wkt,
            source_srid=source_srid,
            source_feature_count=source_feature_count,
            use_centroids=passed_use_centroids_distant
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
        - EXCEPTION: Les expressions display (coalesce) sont SUPPRIMÉES
        
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
        
        # CRITICAL FIX v2.5.6: Sanitize old_subset to remove non-boolean display expressions
        # Display expressions like coalesce("field",'<NULL>') cause PostgreSQL type errors
        old_subset = self._sanitize_subset_string(old_subset)
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
        
        # Pattern 4: FilterMate materialized view reference (fid IN SELECT from mv_...)
        # CRITICAL FIX v2.5.11: Detect previous FilterMate geometric filters using materialized views
        # Format: "fid" IN (SELECT ... FROM "filter_mate_temp"."mv_...")
        # These should be REPLACED, not combined, when re-filtering geometrically
        import re
        has_mv_filter = bool(re.search(
            r'IN\s*\(\s*SELECT.*FROM\s+["\']?filter_mate_temp["\']?\s*\.\s*["\']?mv_',
            old_subset,
            re.IGNORECASE | re.DOTALL
        ))
        
        # If old_subset contains geometric filter patterns, replace instead of combine
        if has_source_alias or has_exists or has_spatial_predicate or has_mv_filter:
            reason = []
            if has_source_alias:
                reason.append("__source alias")
            if has_exists:
                reason.append("EXISTS subquery")
            if has_spatial_predicate:
                reason.append("spatial predicate")
            if has_mv_filter:
                reason.append("FilterMate materialized view (mv_)")
            
            logger.info(f"FilterMate: Old subset contains {', '.join(reason)} - replacing instead of combining")
            return expression
        
        # CRITICAL FIX v2.4.15: Detect QGIS style/symbology expressions
        # These patterns indicate rule-based symbology filters that should NOT
        # be combined with geometric filters as they cause type mismatch errors
        import re
        style_patterns = [
            r'AND\s+TRUE\s*\)',           # Pattern: AND TRUE) - common in rule-based styles
            r'THEN\s+true',               # CASE WHEN ... THEN true - style expression
            r'THEN\s+false',              # CASE WHEN ... THEN false
            r'SELECT\s+CASE',             # SELECT CASE in subquery
            r'\)\s*AND\s+TRUE\s*\)',      # (...) AND TRUE) pattern
        ]
        has_style_pattern = any(
            re.search(pattern, old_subset, re.IGNORECASE) 
            for pattern in style_patterns
        )
        
        if has_style_pattern:
            logger.info(f"FilterMate: Old subset contains QGIS style patterns - replacing instead of combining")
            logger.info(f"  → Detected style-based filter: '{old_subset[:80]}...'")
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
        # CANCELLATION FIX v2.3.22: Check if task was canceled before processing layer
        # This prevents continuing to filter layers after user cancels the task
        if self.isCanceled():
            logger.info(f"⚠️ Skipping layer {layer.name() if hasattr(layer, 'name') else 'unknown'} - task was canceled")
            return False
        
        # THREAD SAFETY FIX: Pass queue_subset_request callback to backends
        # This allows backends to defer setSubsetString() calls to the main thread
        self.task_parameters['_subset_queue_callback'] = self.queue_subset_request
        
        # v2.6.2: Pass parent task reference to backends for cancellation checks
        # This allows backends to check isCanceled() during long operations
        self.task_parameters['_parent_task'] = self
        
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
            
            logger.debug(f"execute_geometric_filtering: {layer.name()} → backend={backend_name.upper()}")
            
            # Log actual backend being used
            if forced_backend and backend_name != forced_backend:
                logger.warning(f"  ⚠️ Forced backend '{forced_backend}' but got '{backend_name}' (backend may not support layer)")
            else:
                logger.info(f"  ✓ Using backend: {backend_name.upper()}")
            
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
            elif backend_name == 'memory':
                # Memory backend uses OGR-style geometry (QgsVectorLayer)
                # v2.5.11: Added explicit memory backend handling
                geometry_provider = PROVIDER_OGR
                logger.info(f"  → Backend is Memory - using OGR geometry format (QgsVectorLayer)")
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
                # THREAD SAFETY: Queue subset clear for application in finished()
                self._queue_subset_string(layer, "")
                logger.info(f"  ✓ Queued subset clear for {layer.name()} - ready for fresh filter")
            
            # Build filter expression using backend
            logger.info(f"  → Building backend expression with predicates: {self.current_predicates}")
            expression = self._build_backend_expression(backend, layer_props, source_geom)
            if not expression:
                logger.warning(f"No expression generated for {layer.name()}")
                logger.warning(f"  → backend type: {type(backend).__name__}")
                logger.warning(f"  → current_predicates: {self.current_predicates}")
                logger.warning(f"  → source_geom type: {type(source_geom).__name__}")
                
                # DIAGNOSTIC v2.4.11: Log all available source geometries
                logger.warning("  → Available source geometries:")
                logger.warning(f"     - spatialite_source_geom: {'YES' if (hasattr(self, 'spatialite_source_geom') and self.spatialite_source_geom) else 'NO'}")
                logger.warning(f"     - ogr_source_geom: {'YES' if (hasattr(self, 'ogr_source_geom') and self.ogr_source_geom) else 'NO'}")
                logger.warning(f"     - postgresql_source_geom: {'YES' if (hasattr(self, 'postgresql_source_geom') and self.postgresql_source_geom) else 'NO'}")
                
                # FALLBACK v2.4.10: Try OGR backend when Spatialite expression building fails
                # This happens when Spatialite source geometry is not available (e.g., GDAL without Spatialite)
                # CRITICAL FIX v2.7.6: Also try OGR fallback for PostgreSQL when WKT is too large
                # This handles cases where complex geometries exceed PostgreSQL's WKT embedding limits
                if backend_name in ('spatialite', 'postgresql'):
                    if backend_name == 'postgresql':
                        logger.warning(f"⚠️ PostgreSQL expression building failed for {layer.name()}")
                        logger.warning(f"  → This typically means WKT geometry is too large for PostgreSQL embedding")
                        logger.warning(f"  → Attempting OGR fallback (QGIS processing)...")
                    else:
                        logger.warning(f"⚠️ Spatialite expression building failed for {layer.name()}")
                        logger.warning(f"  → Attempting OGR fallback (QGIS processing)...")
                    
                    try:
                        ogr_backend = BackendFactory.get_backend('ogr', layer, self.task_parameters)
                        
                        # Prepare OGR source geometry if not already done
                        if not hasattr(self, 'ogr_source_geom') or self.ogr_source_geom is None:
                            logger.info(f"  → Preparing OGR source geometry for fallback...")
                            self.prepare_ogr_source_geom()
                            
                            # Check if preparation succeeded
                            if not hasattr(self, 'ogr_source_geom') or self.ogr_source_geom is None:
                                logger.error(f"  ✗ OGR source geometry preparation FAILED")
                                logger.error(f"    → Source layer: {self.source_layer.name() if self.source_layer else 'None'}")
                                logger.error(f"    → Source features: {self.source_layer.featureCount() if self.source_layer else 0}")
                                return False
                        
                        ogr_source_geom = self._prepare_source_geometry(PROVIDER_OGR)
                        
                        if ogr_source_geom:
                            if isinstance(ogr_source_geom, QgsVectorLayer):
                                logger.info(f"  → OGR source geometry: {ogr_source_geom.name()} ({ogr_source_geom.featureCount()} features)")
                            
                            ogr_expression = self._build_backend_expression(ogr_backend, layer_props, ogr_source_geom)
                            
                            if ogr_expression:
                                logger.info(f"  → OGR expression built: {ogr_expression[:100]}...")
                                
                                # CRITICAL FIX v2.5.10: Handle old_subset intelligently for OGR fallback
                                # Get the current layer's old_subset for OGR fallback
                                fallback_old_subset = layer.subsetString() if layer.subsetString() else None
                                fallback_combine_op = self._get_combine_operator()
                                
                                # Apply same logic as main path - preserve attribute filters, replace geometric
                                if fallback_old_subset:
                                    upper = fallback_old_subset.upper()
                                    is_geo = ('__source' in fallback_old_subset.lower() or 
                                              'EXISTS' in upper or 
                                              any(p in upper for p in ['ST_INTERSECTS', 'ST_CONTAINS', 'ST_WITHIN']))
                                    if is_geo:
                                        logger.info(f"  → OGR fallback: Replacing geometric filter")
                                        fallback_old_subset = None
                                        fallback_combine_op = None
                                    else:
                                        logger.info(f"  → OGR fallback: Preserving attribute filter")
                                
                                result = ogr_backend.apply_filter(layer, ogr_expression, fallback_old_subset, fallback_combine_op)
                                
                                if result:
                                    logger.info(f"✓ OGR fallback SUCCEEDED for {layer.name()}")
                                    if 'actual_backends' not in self.task_parameters:
                                        self.task_parameters['actual_backends'] = {}
                                    self.task_parameters['actual_backends'][layer.id()] = 'ogr'
                                    return True
                                else:
                                    logger.error(f"✗ OGR fallback also FAILED for {layer.name()}")
                            else:
                                logger.error(f"✗ Could not build OGR expression for fallback")
                        else:
                            logger.error(f"✗ Could not prepare OGR source geometry for fallback")
                    except Exception as fallback_error:
                        logger.error(f"✗ OGR fallback exception: {fallback_error}")
                        import traceback
                        logger.error(f"Fallback traceback: {traceback.format_exc()}")
                
                return False
            logger.info(f"  ✓ Expression built: {len(expression)} chars")
            logger.info(f"  → Expression preview: {expression[:200]}...")
            
            # Get old subset and combine operator for backend to handle
            old_subset = layer.subsetString() if layer.subsetString() != '' else None
            combine_operator = self._get_combine_operator()
            
            # CRITICAL FIX v2.5.10: Intelligently handle existing subset during geometric filtering
            # - REPLACE if it contains geometric patterns (EXISTS, ST_*, __source)
            # - COMBINE if it's a simple attribute filter
            # 
            # This preserves user's attribute filters (like "importance > 5") while avoiding
            # nested geometric filters which cause SQL errors.
            if old_subset:
                old_subset_upper = old_subset.upper()
                
                # Check if old_subset contains geometric filter patterns that cannot be nested
                is_geometric_filter = (
                    '__source' in old_subset.lower() or
                    'EXISTS (' in old_subset_upper or
                    'EXISTS(' in old_subset_upper or
                    any(pred in old_subset_upper for pred in [
                        'ST_INTERSECTS', 'ST_CONTAINS', 'ST_WITHIN', 'ST_TOUCHES',
                        'ST_OVERLAPS', 'ST_CROSSES', 'ST_DISJOINT', 'ST_EQUALS',
                        'ST_DWITHIN', 'ST_COVERS', 'ST_COVEREDBY', 'ST_BUFFER'
                    ])
                )
                
                # Check for style/display expression patterns
                # CRITICAL FIX v2.5.10: Enhanced detection for SELECT CASE expressions
                import re
                is_style_expression = any(re.search(pattern, old_subset, re.IGNORECASE | re.DOTALL) for pattern in [
                    r'AND\s+TRUE\s*\)',              # Rule-based style
                    r'THEN\s+true\b',                # CASE THEN true
                    r'THEN\s+false\b',               # CASE THEN false
                    r'coalesce\s*\([^)]+,\s*\'',     # Display expression
                    r'SELECT\s+CASE\s+',             # SELECT CASE expression from rule-based styles
                    r'\(\s*CASE\s+WHEN\s+.+THEN\s+true',  # CASE WHEN ... THEN true
                ])
                
                if is_geometric_filter:
                    logger.info(f"🔄 Existing subset on {layer.name()} contains GEOMETRIC filter - will be REPLACED")
                    logger.info(f"  → Existing: '{old_subset[:100]}...'")
                    logger.info(f"  → Reason: Cannot nest geometric filters (EXISTS, ST_*, __source)")
                    old_subset = None
                elif is_style_expression:
                    logger.info(f"🔄 Existing subset on {layer.name()} contains STYLE expression - will be REPLACED")
                    logger.info(f"  → Existing: '{old_subset[:100]}...'")
                    logger.info(f"  → Reason: Style expressions cause type mismatch errors")
                    old_subset = None
                else:
                    # Simple attribute filter - will be COMBINED by backend
                    logger.info(f"✅ Existing subset on {layer.name()} is ATTRIBUTE filter - will be COMBINED")
                    logger.info(f"  → Existing: '{old_subset[:100]}...'")
                    logger.info(f"  → Reason: Preserving user's attribute filter with geometric filter")
            
            logger.info(f"📋 Préparation du filtre pour {layer.name()}")
            logger.info(f"  → Nouvelle expression: '{expression[:100]}...' ({len(expression)} chars)")
            if old_subset:
                logger.info(f"  → ✓ Subset existant détecté: '{old_subset[:80]}...'")
                logger.info(f"  → Opérateur de combinaison: {combine_operator if combine_operator else 'AND (par défaut)'}")
            else:
                logger.info(f"  → Pas de subset existant (filtre simple)")
            
            # Apply filter using backend (delegates to appropriate method for each provider type)
            result = backend.apply_filter(layer, expression, old_subset, combine_operator)
            
            # FALLBACK MECHANISM v2.4.1: If Spatialite or PostgreSQL backend fails on a forced layer,
            # try OGR backend as fallback. This handles cases where user forces a backend
            # on layers that don't support that backend (e.g., Shapefiles with Spatialite).
            # Also trigger fallback when Spatialite functions are not available (e.g., GDAL without Spatialite)
            # 
            # CRITICAL FIX v2.5.18: Also trigger OGR fallback for PostgreSQL failures
            # This handles:
            # - statement_timeout on complex EXISTS queries with large source datasets
            # - Connection failures
            # - SQL syntax errors on edge cases
            # v2.6.10: Also handles suspicious 0 results on large Spatialite datasets
            if not result and backend_name in ('spatialite', 'postgresql'):
                forced_backends = self.task_parameters.get('forced_backends', {})
                was_forced = layer.id() in forced_backends
                
                # v2.6.10: Check if this is a suspicious zero result fallback
                zero_result_fallback = getattr(backend, '_spatialite_zero_result_fallback', False)
                
                # CRITICAL FIX v2.5.18: Always try OGR fallback for PostgreSQL failures too
                # PostgreSQL backend may fail due to timeout (complex spatial queries),
                # connection issues, or SQL errors. OGR uses QGIS processing which is
                # slower but more reliable.
                # v2.8.2: BUT skip OGR fallback for very large PostgreSQL tables (>100k features)
                # OGR fallback downloads ALL features from PostgreSQL which is impractical
                # for tables with millions of rows.
                layer_feature_count = layer.featureCount()
                is_large_pg_table = (backend_name == 'postgresql' and 
                                     layer.providerType() == 'postgres' and 
                                     layer_feature_count > 100000)
                
                if is_large_pg_table:
                    logger.error(f"⚠️ PostgreSQL query FAILED for large table {layer.name()} ({layer_feature_count:,} features)")
                    logger.error(f"  → OGR fallback is NOT available for tables > 100k features")
                    logger.error(f"  → PostgreSQL timeout may be too short for complex spatial queries")
                    logger.error(f"  → Solutions:")
                    logger.error(f"     1. Reduce source selection count (fewer features to intersect)")
                    logger.error(f"     2. Increase PostgreSQL statement_timeout on server")
                    logger.error(f"     3. Add spatial index (GiST) on geometry column")
                    logger.error(f"     4. Use simpler predicates (e.g., intersects instead of contains)")
                    from qgis.core import QgsMessageLog, Qgis
                    QgsMessageLog.logMessage(
                        f"⚠️ {layer.name()}: PostgreSQL timeout on {layer_feature_count:,} features - "
                        f"reduce source count or increase server timeout",
                        "FilterMate", Qgis.Critical
                    )
                    # Skip fallback, return failure
                    return False
                
                should_fallback = was_forced or (backend_name in ('spatialite', 'postgresql'))
                
                if should_fallback:
                    if zero_result_fallback:
                        # v2.6.10: Special handling for suspicious 0 results
                        logger.warning(f"⚠️ SPATIALITE returned 0 features on large dataset {layer.name()}")
                        logger.warning(f"  → This suggests geometry processing issue (ST_Simplify may have corrupted geometry)")
                        logger.warning(f"  → Falling back to OGR for reliable feature-by-feature filtering")
                        from qgis.core import QgsMessageLog, Qgis
                        QgsMessageLog.logMessage(
                            f"🔄 {layer.name()}: OGR fallback (Spatialite 0 results on {layer.featureCount():,} features)",
                            "FilterMate", Qgis.Warning
                        )
                    elif was_forced:
                        logger.warning(f"⚠️ {backend_name.upper()} backend FAILED for forced layer {layer.name()}")
                        logger.warning(f"  → Layer may not support {backend_name.upper()} SQL functions")
                    elif backend_name == 'postgresql':
                        logger.warning(f"⚠️ PostgreSQL backend FAILED for {layer.name()}")
                        logger.warning(f"  → Query may have timed out or connection failed")
                        logger.warning(f"  → Consider reducing source feature count or using simpler predicates")
                    else:
                        logger.warning(f"⚠️ {backend_name.upper()} backend FAILED for {layer.name()}")
                        logger.warning(f"  → Spatialite functions may not be available (GDAL without Spatialite)")
                    logger.warning(f"  → Attempting OGR fallback (QGIS processing)...")
                    
                    # v2.6.11: Log OGR fallback attempt to QGIS MessageLog
                    QgsMessageLog.logMessage(
                        f"🔄 {layer.name()}: Attempting OGR fallback...",
                        "FilterMate", Qgis.Info
                    )
                    
                    # Try OGR backend as fallback
                    try:
                        # v2.6.12: Use force_ogr=True to bypass backend auto-selection
                        # Without this, BackendFactory.get_backend() would test Spatialite again
                        # and return Spatialite backend (which just timed out!) instead of OGR
                        ogr_backend = BackendFactory.get_backend('ogr', layer, self.task_parameters, force_ogr=True)
                        
                        # v2.6.11: Ensure OGR source geometry is prepared
                        # This is critical for the fallback to work
                        if not hasattr(self, 'ogr_source_geom') or self.ogr_source_geom is None:
                            logger.info(f"  → Preparing OGR source geometry for fallback...")
                            QgsMessageLog.logMessage(
                                f"OGR fallback: preparing source geometry...",
                                "FilterMate", Qgis.Info
                            )
                            self.prepare_ogr_source_geom()
                        
                        # v2.6.11: Use ogr_source_geom directly after preparation
                        ogr_source_geom = getattr(self, 'ogr_source_geom', None)
                        
                        # If still None, try _prepare_source_geometry as fallback
                        if ogr_source_geom is None:
                            logger.warning(f"  → ogr_source_geom still None, trying _prepare_source_geometry...")
                            ogr_source_geom = self._prepare_source_geometry(PROVIDER_OGR)
                        
                        # Enhanced diagnostic logging for OGR fallback
                        if ogr_source_geom:
                            if isinstance(ogr_source_geom, QgsVectorLayer):
                                logger.info(f"  → OGR source geometry: {ogr_source_geom.name()} ({ogr_source_geom.featureCount()} features)")
                                QgsMessageLog.logMessage(
                                    f"OGR fallback: source geometry = {ogr_source_geom.name()} ({ogr_source_geom.featureCount()} features)",
                                    "FilterMate", Qgis.Info
                                )
                            else:
                                logger.info(f"  → OGR source geometry type: {type(ogr_source_geom).__name__}")
                                QgsMessageLog.logMessage(
                                    f"OGR fallback: source geometry type = {type(ogr_source_geom).__name__}",
                                    "FilterMate", Qgis.Info
                                )
                            
                            # Build OGR expression
                            ogr_expression = self._build_backend_expression(ogr_backend, layer_props, ogr_source_geom)
                            
                            if ogr_expression:
                                logger.info(f"  → OGR expression built: {ogr_expression[:100]}...")
                                
                                # Apply OGR filter
                                result = ogr_backend.apply_filter(layer, ogr_expression, old_subset, combine_operator)
                                
                                if result:
                                    logger.info(f"✓ OGR fallback SUCCEEDED for {layer.name()}")
                                    # v2.6.11: Log OGR success to QGIS MessageLog
                                    QgsMessageLog.logMessage(
                                        f"✓ OGR fallback SUCCEEDED for {layer.name()} → {layer.featureCount()} features",
                                        "FilterMate", Qgis.Info
                                    )
                                    # Update actual backend used
                                    self.task_parameters['actual_backends'][layer.id()] = 'ogr'
                                    # Return success since fallback worked
                                    return True
                                else:
                                    logger.error(f"✗ OGR fallback also FAILED for {layer.name()}")
                                    logger.error(f"  → Check Python console for detailed errors")
                                    QgsMessageLog.logMessage(
                                        f"⚠️ OGR fallback FAILED for {layer.name()} - check Python console",
                                        "FilterMate", Qgis.Warning
                                    )
                            else:
                                logger.error(f"✗ Could not build OGR expression for fallback")
                                logger.error(f"  → predicates: {self.current_predicates}")
                                QgsMessageLog.logMessage(
                                    f"⚠️ OGR fallback: could not build expression for {layer.name()}",
                                    "FilterMate", Qgis.Warning
                                )
                        else:
                            logger.error(f"✗ Could not prepare OGR source geometry for fallback")
                            logger.error(f"  → ogr_source_geom is None")
                            QgsMessageLog.logMessage(
                                f"⚠️ OGR fallback: source geometry is None for {layer.name()}",
                                "FilterMate", Qgis.Warning
                            )
                            if hasattr(self, 'ogr_source_geom'):
                                logger.error(f"  → self.ogr_source_geom exists but is {self.ogr_source_geom}")
                            else:
                                logger.error(f"  → self.ogr_source_geom was never set")
                    except Exception as fallback_error:
                        logger.error(f"✗ OGR fallback exception: {fallback_error}")
                        import traceback
                        logger.error(f"Fallback traceback: {traceback.format_exc()}")
                        # v2.6.11: Log OGR fallback exception to QGIS MessageLog
                        QgsMessageLog.logMessage(
                            f"⚠️ OGR fallback exception for {layer.name()}: {str(fallback_error)[:100]}",
                            "FilterMate", Qgis.Warning
                        )
            
            if result:
                # For backends that use setSubsetString, get the actual applied expression
                final_expression = layer.subsetString()
                feature_count = layer.featureCount()
                
                # CRITICAL DIAGNOSTIC: Verify filter was actually applied
                logger.debug(f"✓ execute_geometric_filtering: {layer.name()} → backend returned SUCCESS")
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
                # CRITICAL FIX: For PostgreSQL layers, build a full SELECT statement
                # because manage_layer_subset_strings expects a complete SQL SELECT
                # for materialized view creation, not just a WHERE clause expression
                if layer.providerType() == 'postgres' and final_expression:
                    # Build full SELECT statement from WHERE clause
                    sql_subset_string = (
                        f'SELECT "{layer_name}"."{primary_key}", '
                        f'"{layer_name}"."{geom_field}" '
                        f'FROM "{layer_schema}"."{layer_name}" '
                        f'WHERE {final_expression}'
                    )
                    logger.debug(f"Built full SELECT for PostgreSQL history: {sql_subset_string[:200]}...")
                else:
                    # Non-PostgreSQL layers use the expression directly
                    sql_subset_string = final_expression
                
                # CRITICAL FIX v2.8.1: Skip manage_layer_subset_strings for distant layers
                # when backend has already queued the filter via queue_callback.
                # manage_layer_subset_strings would add a DUPLICATE filter to the queue,
                # causing the old filter to overwrite the new one in finished().
                # 
                # For PostgreSQL layers using geometric filtering, the backend's apply_filter()
                # has already queued the filter. We only need manage_layer_subset_strings for:
                # 1. Saving filter history (but not re-applying the filter!)
                # 2. Creating materialized views (which is handled separately)
                #
                # SKIP: The filter was already queued by backend.apply_filter()
                logger.info(
                    f"Skipping manage_layer_subset_strings for {layer.name()}: "
                    f"filter already queued by backend.apply_filter() via queue_callback"
                )
                
                logger.info(f"✓ Successfully filtered {layer.name()}: {feature_count:,} features match")
            else:
                logger.error(f"✗ Backend returned FAILURE for {layer.name()}")
                logger.error(f"  - Check backend logs for details")
                
                # Log to QGIS Message Panel for visibility
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"execute_geometric_filtering ✗ {layer.name()} → backend returned FAILURE",
                    "FilterMate", Qgis.Warning
                )
            
            # DIAGNOSTIC: Log final return value
            logger.debug(f"execute_geometric_filtering → returning result={result} for {layer.name()}")
            return result
            
        except Exception as e:
            # DIAGNOSTIC: Log exception being caught
            from qgis.core import QgsMessageLog, Qgis
            QgsMessageLog.logMessage(
                f"execute_geometric_filtering EXCEPTION for {layer.name()}: {e}",
                "FilterMate", Qgis.Critical
            )
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
        
        # Return source layer operator, normalized to English SQL keyword
        source_op = getattr(self, 'param_source_layer_combine_operator', None)
        return self._normalize_sql_operator(source_op)
    
    def _normalize_sql_operator(self, operator):
        """
        Normalize translated SQL operators to English SQL keywords.
        
        FIX v2.5.12: Handle cases where translated operator values (ET, OU, NON)
        are stored in layer properties or project files from older versions.
        
        Args:
            operator: The operator string (possibly translated)
            
        Returns:
            str: Normalized SQL operator ('AND', 'OR', 'AND NOT', 'NOT') or None
        """
        if not operator:
            return None
        
        op_upper = operator.upper().strip()
        
        # Mapping of translated operators to SQL keywords
        translations = {
            # French
            'ET': 'AND',
            'OU': 'OR',
            'ET NON': 'AND NOT',
            'NON': 'NOT',
            # German
            'UND': 'AND',
            'ODER': 'OR',
            'UND NICHT': 'AND NOT',
            'NICHT': 'NOT',
            # Spanish
            'Y': 'AND',
            'O': 'OR',
            'Y NO': 'AND NOT',
            'NO': 'NOT',
            # Italian
            'E': 'AND',
            'E NON': 'AND NOT',
            # Portuguese
            'E NÃO': 'AND NOT',
            'NÃO': 'NOT',
            # Already English - just return as-is
            'AND': 'AND',
            'OR': 'OR',
            'AND NOT': 'AND NOT',
            'NOT': 'NOT',
        }
        
        normalized = translations.get(op_upper, operator)
        
        if normalized != operator:
            logger.debug(f"Normalized operator '{operator}' to '{normalized}'")
        
        return normalized
    
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
        
        # Get operator and normalize to English SQL keyword
        other_op = getattr(self, 'param_other_layers_combine_operator', None)
        return self._normalize_sql_operator(other_op)
    
    def _prepare_source_geometry(self, layer_provider_type):
        """
        Prepare source geometry expression based on provider type.
        
        CRITICAL FIX v2.4.1: Added fallback logic to handle cases where
        the requested geometry type is not available. This commonly happens
        when a backend is forced but the corresponding geometry wasn't prepared.
        
        CRITICAL FIX v2.7.2: For PostgreSQL target layers, only use postgresql_source_geom
        if the SOURCE layer is also PostgreSQL. When source is OGR (GeoPackage/Shapefile),
        always use WKT (spatialite_source_geom) which works via ST_GeomFromText().
        
        Args:
            layer_provider_type: Target layer provider type
        
        Returns:
            Source geometry (type depends on provider):
            - PostgreSQL: SQL expression string (table ref if source is PG, WKT otherwise)
            - Spatialite: WKT string  
            - OGR: QgsVectorLayer
        """
        # PostgreSQL backend needs SQL expression
        if layer_provider_type == PROVIDER_POSTGRES and POSTGRESQL_AVAILABLE:
            # v2.7.11 DIAGNOSTIC: Log which path is taken
            logger.info(f"🔍 _prepare_source_geometry(PROVIDER_POSTGRES)")
            logger.info(f"   postgresql_source_geom exists: {hasattr(self, 'postgresql_source_geom')}")
            if hasattr(self, 'postgresql_source_geom'):
                logger.info(f"   postgresql_source_geom truthy: {bool(self.postgresql_source_geom)}")
                if self.postgresql_source_geom:
                    logger.info(f"   postgresql_source_geom preview: '{str(self.postgresql_source_geom)[:100]}...'")
            
            # CRITICAL FIX v2.7.2: Only use postgresql_source_geom if source is also PostgreSQL
            # When source is OGR and postgresql_source_geom was NOT prepared (per fix in
            # _prepare_geometries_by_provider), we should use WKT mode.
            # However, if postgresql_source_geom was somehow prepared with invalid data,
            # we need to validate it first.
            source_is_postgresql = (
                hasattr(self, 'param_source_provider_type') and 
                self.param_source_provider_type == PROVIDER_POSTGRES
            )
            logger.info(f"   source_is_postgresql: {source_is_postgresql}")
            
            if source_is_postgresql:
                # Source is PostgreSQL - use postgresql_source_geom (table reference for EXISTS)
                if hasattr(self, 'postgresql_source_geom') and self.postgresql_source_geom:
                    logger.info(f"   → Returning postgresql_source_geom (table reference)")
                    return self.postgresql_source_geom
                else:
                    logger.warning(f"   → postgresql_source_geom NOT available, will use WKT fallback!")
            else:
                # Source is NOT PostgreSQL (OGR, Spatialite, etc.)
                # Must use WKT mode - DO NOT use postgresql_source_geom even if set
                # because it would contain invalid table references
                logger.info(f"PostgreSQL target but source is {self.param_source_provider_type} - using WKT mode")
            
            # Fallback: try WKT for PostgreSQL (works with ST_GeomFromText)
            if hasattr(self, 'spatialite_source_geom') and self.spatialite_source_geom:
                if not source_is_postgresql:
                    logger.info(f"Using WKT (spatialite_source_geom) for PostgreSQL filtering")
                else:
                    logger.warning(f"PostgreSQL source geom not available, using WKT fallback")
                return self.spatialite_source_geom
        
        # Spatialite backend needs WKT string
        if layer_provider_type == PROVIDER_SPATIALITE:
            if hasattr(self, 'spatialite_source_geom') and self.spatialite_source_geom:
                return self.spatialite_source_geom
            # CRITICAL FIX v2.4.1: Generate WKT from OGR source if available
            if hasattr(self, 'ogr_source_geom') and self.ogr_source_geom:
                logger.warning(f"Spatialite source geom not available, generating WKT from OGR layer")
                try:
                    if isinstance(self.ogr_source_geom, QgsVectorLayer):
                        all_geoms = []
                        for feature in self.ogr_source_geom.getFeatures():
                            geom = feature.geometry()
                            if geom and not geom.isEmpty():
                                all_geoms.append(geom)
                        if all_geoms:
                            combined = QgsGeometry.collectGeometry(all_geoms)
                            wkt = combined.asWkt()
                            self.spatialite_source_geom = wkt.replace("'", "''")
                            logger.info(f"✓ Generated WKT from OGR layer ({len(self.spatialite_source_geom)} chars)")
                            return self.spatialite_source_geom
                except Exception as e:
                    logger.error(f"Failed to generate WKT from OGR layer: {e}")
        
        # OGR backend needs QgsVectorLayer
        if layer_provider_type == PROVIDER_OGR:
            if hasattr(self, 'ogr_source_geom') and self.ogr_source_geom:
                return self.ogr_source_geom
        
        # Generic fallback for any provider: try OGR geometry
        if hasattr(self, 'ogr_source_geom') and self.ogr_source_geom:
            logger.warning(f"Using OGR source geom as fallback for provider '{layer_provider_type}'")
            return self.ogr_source_geom
        
        # Last resort: return source layer
        if hasattr(self, 'source_layer') and self.source_layer:
            logger.warning(f"Using source layer as last resort fallback")
            return self.source_layer
        
        logger.error(f"No source geometry available for provider '{layer_provider_type}'")
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
        skip_source_filter = self.task_parameters["task"].get("skip_source_filter", False)
        
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
        elif skip_source_filter:
            # Custom selection mode avec expression non-filtre (ex: nom de champ seul)
            # → Utiliser toutes les features de la couche source
            logger.info("✓ Selection Mode: ALL FEATURES (custom selection with field-only expression)")
            logger.info(f"  → No source filter will be applied")
            logger.info(f"  → All features from source layer will be used for geometric predicates")
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
                
                # FIX v2.7.1: Use function name as key instead of indices
                # Previously, using list(self.predicates).index(key) produced incorrect indices
                # (0, 2, 4, 6...) because the predicates dict has both capitalized and lowercase
                # entries (16 total). This caused Spatialite backend's index_to_name mapping to fail.
                # Now we use the SQL function name directly as the key, which both backends handle correctly.
                for key in source_predicates:
                    if key in self.predicates:
                        func_name = self.predicates[key]
                        self.current_predicates[func_name] = func_name

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
                    logger.warning("  → Common causes:")
                    logger.warning("     1. Forced Spatialite backend on non-Spatialite layers (e.g., Shapefiles)")
                    logger.warning("     2. GDAL not compiled with Spatialite extension")
                    logger.warning("     3. CRS mismatch between source and distant layers")
                    
                    # Build informative error message with failed layer names
                    failed_names = getattr(self, '_failed_layer_names', [])
                    if failed_names:
                        if len(failed_names) <= 3:
                            layers_str = ', '.join(failed_names)
                        else:
                            layers_str = f"{', '.join(failed_names[:3])} (+{len(failed_names)-3} others)"
                        self.message = f"Failed layers: {layers_str}. Try OGR backend or check Python console."
                    else:
                        self.message = "Source layer filtered, but some distant layers failed. Try using OGR backend for failing layers or check Python console."
                    return False
                
                logger.info("=" * 60)
                logger.info("✓ COMPLETE SUCCESS: All layers filtered")
                logger.info("=" * 60)
            else:
                logger.info("  → No geometric predicates configured")
                logger.info("  → Only source layer filtered")
        else:
            # Log detailed reason why geometric filtering is skipped
            logger.warning("=" * 60)
            logger.warning("⚠️ DISTANT LAYERS FILTERING SKIPPED - DIAGNOSTIC")
            logger.warning("=" * 60)
            if not has_geom_predicates:
                logger.warning("  ❌ has_geometric_predicates = FALSE")
                logger.warning("     → Enable 'Geometric predicates' button in UI")
            else:
                logger.info("  ✓ has_geometric_predicates = True")
            
            if not has_layers_to_filter and not has_layers_in_params:
                logger.warning("  ❌ No layers to filter:")
                logger.warning(f"     - has_layers_to_filter = {has_layers_to_filter}")
                logger.warning(f"     - has_layers_in_params = {has_layers_in_params}")
                logger.warning("     → Select layers to filter in UI")
            else:
                logger.info(f"  ✓ has_layers_to_filter = {has_layers_to_filter}")
                logger.info(f"  ✓ has_layers_in_params = {has_layers_in_params}")
            
            if self.layers_count == 0:
                logger.warning("  ❌ layers_count = 0 (no layers organized)")
                logger.warning("     → Check if selected layers exist in project")
            else:
                logger.info(f"  ✓ layers_count = {self.layers_count}")
            
            # Log filtering parameters for debugging
            filtering_params = self.task_parameters.get("filtering", {})
            logger.warning("  📋 Filtering parameters:")
            logger.warning(f"     - has_geometric_predicates: {filtering_params.get('has_geometric_predicates', 'NOT SET')}")
            logger.warning(f"     - geometric_predicates: {filtering_params.get('geometric_predicates', 'NOT SET')}")
            logger.warning(f"     - has_layers_to_filter: {filtering_params.get('has_layers_to_filter', 'NOT SET')}")
            logger.warning(f"     - layers_to_filter: {filtering_params.get('layers_to_filter', 'NOT SET')}")
            
            logger.warning("=" * 60)
            logger.warning("  → Only source layer filtered")

        return result 
     

    def execute_unfiltering(self):
        """
        Remove all filters from source layer and selected remote layers.
        
        This clears filters completely (sets subsetString to empty) for:
        - The current/source layer
        - All selected remote layers (layers_to_filter)
        
        NOTE: This is different from undo - it removes filters entirely rather than
        restoring previous filter state. Use undo button for history navigation.
        
        THREAD SAFETY: All subset string operations are queued for application
        in finished() which runs on the main Qt thread.
        """
        logger.info("FilterMate: Clearing all filters on source and selected layers")
        
        # Queue filter clear on source layer (will be applied in finished())
        self._queue_subset_string(self.source_layer, '')
        logger.info(f"FilterMate: Queued filter clear on source layer {self.source_layer.name()}")
        
        # Queue filter clear on all selected associated layers
        i = 1
        self.setProgress((i/self.layers_count)*100)
        
        for layer_provider_type in self.layers:
            for layer, layer_props in self.layers[layer_provider_type]:
                self._queue_subset_string(layer, '')
                logger.info(f"FilterMate: Queued filter clear on layer {layer.name()}")
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
            style_format: Style file format (e.g., 'qml', 'sld', 'lyrx')
            datatype: Export datatype (to check if styles are supported)
        """
        if datatype == 'XLSX' or not style_format:
            return
        
        # Normalize format name
        format_lower = style_format.lower().replace('arcgis (lyrx)', 'lyrx').strip()
        
        # Handle ArcGIS LYRX format
        if format_lower == 'lyrx' or 'arcgis' in format_lower:
            self._save_layer_style_lyrx(layer, output_path)
            return
        
        style_path = os.path.normcase(f"{output_path}.{format_lower}")
        try:
            layer.saveNamedStyle(style_path)
            logger.debug(f"Style saved: {style_path}")
        except Exception as e:
            logger.warning(f"Could not save style for '{layer.name()}': {e}")

    def _save_layer_style_lyrx(self, layer, output_path):
        """
        Export layer style to ArcGIS-compatible LYRX format.
        
        Creates a JSON-based style file that can be imported into ArcGIS Pro.
        Note: This is a basic conversion that includes symbology metadata.
        Full ArcGIS style support requires ArcPy (not available in QGIS).
        
        Args:
            layer: QgsVectorLayer
            output_path: Base path for export (without extension)
        """
        import json
        from datetime import datetime
        
        style_path = os.path.normcase(f"{output_path}.lyrx")
        
        try:
            # Build ArcGIS-compatible layer definition
            renderer = layer.renderer()
            geometry_type_map = {
                0: "esriGeometryPoint",
                1: "esriGeometryPolyline", 
                2: "esriGeometryPolygon",
                3: "esriGeometryMultipoint",
                4: "esriGeometryNull"
            }
            
            lyrx_content = {
                "type": "CIMLayerDocument",
                "version": "2.9.0",
                "build": 32739,
                "layers": [
                    f"CIMPATH=map/{layer.name().replace(' ', '_')}.json"
                ],
                "layerDefinitions": [
                    {
                        "type": "CIMFeatureLayer",
                        "name": layer.name(),
                        "uRI": f"CIMPATH=map/{layer.name().replace(' ', '_')}.json",
                        "sourceModifiedTime": {
                            "type": "TimeInstant",
                            "start": datetime.now().timestamp() * 1000
                        },
                        "description": f"Exported from QGIS FilterMate - {layer.name()}",
                        "layerType": "Operational",
                        "showLegends": True,
                        "visibility": True,
                        "displayCacheType": "Permanent",
                        "maxDisplayCacheAge": 5,
                        "showPopups": True,
                        "serviceLayerID": -1,
                        "refreshRate": -1,
                        "refreshRateUnit": "esriTimeUnitsSeconds",
                        "autoGenerateFeatureTemplates": True,
                        "featureTable": {
                            "type": "CIMFeatureTable",
                            "displayField": layer.displayField() or "",
                            "editable": True,
                            "dataConnection": {
                                "type": "CIMStandardDataConnection",
                                "workspaceFactory": "FileGDB" if ".gdb" in layer.source() else "Shapefile"
                            },
                            "studyAreaSpatialRel": "esriSpatialRelUndefined",
                            "searchOrder": "esriSearchOrderSpatial"
                        },
                        "htmlPopupEnabled": True,
                        "selectable": True,
                        "featureCacheType": "Session",
                        "geometryType": geometry_type_map.get(layer.geometryType(), "esriGeometryNull"),
                        "_qgis_renderer_type": renderer.type() if renderer else "unknown",
                        "_qgis_crs": layer.crs().authid(),
                        "_qgis_feature_count": layer.featureCount(),
                        "_filtermate_export": {
                            "version": "2.5.0",
                            "timestamp": datetime.now().isoformat(),
                            "note": "Basic LYRX export. For full symbology, use ArcGIS Pro import."
                        }
                    }
                ]
            }
            
            # Add symbology info if available
            if renderer:
                if renderer.type() == 'singleSymbol':
                    symbol = renderer.symbol()
                    if symbol:
                        lyrx_content["layerDefinitions"][0]["renderer"] = {
                            "type": "CIMSimpleRenderer",
                            "symbol": {
                                "type": "CIMSymbolReference",
                                "symbol": self._convert_symbol_to_arcgis(symbol)
                            }
                        }
            
            with open(style_path, 'w', encoding='utf-8') as f:
                json.dump(lyrx_content, f, indent=2, ensure_ascii=False)
            
            logger.info(f"ArcGIS LYRX style saved: {style_path}")
            
        except Exception as e:
            logger.warning(f"Could not save ArcGIS LYRX style for '{layer.name()}': {e}")

    def _convert_symbol_to_arcgis(self, symbol):
        """
        Convert QGIS symbol to basic ArcGIS CIM symbol format.
        
        Args:
            symbol: QGIS symbol object
            
        Returns:
            dict: ArcGIS CIM symbol definition
        """
        try:
            # Get basic color from first symbol layer
            if symbol.symbolLayerCount() > 0:
                symbol_layer = symbol.symbolLayer(0)
                color = symbol_layer.color()
                rgb = [color.red(), color.green(), color.blue(), color.alpha()]
            else:
                rgb = [128, 128, 128, 255]
            
            symbol_type = symbol.type()
            
            if symbol_type == 0:  # Marker (Point)
                return {
                    "type": "CIMPointSymbol",
                    "symbolLayers": [{
                        "type": "CIMVectorMarker",
                        "enable": True,
                        "size": symbol.size() if hasattr(symbol, 'size') else 6,
                        "colorLocked": True,
                        "markerGraphics": [{
                            "type": "CIMMarkerGraphic",
                            "geometry": {"rings": [[[-1, -1], [-1, 1], [1, 1], [1, -1], [-1, -1]]]},
                            "symbol": {
                                "type": "CIMPolygonSymbol",
                                "symbolLayers": [{
                                    "type": "CIMSolidFill",
                                    "enable": True,
                                    "color": {"type": "CIMRGBColor", "values": rgb}
                                }]
                            }
                        }]
                    }]
                }
            elif symbol_type == 1:  # Line
                return {
                    "type": "CIMLineSymbol",
                    "symbolLayers": [{
                        "type": "CIMSolidStroke",
                        "enable": True,
                        "width": symbol.width() if hasattr(symbol, 'width') else 1,
                        "color": {"type": "CIMRGBColor", "values": rgb}
                    }]
                }
            else:  # Polygon
                return {
                    "type": "CIMPolygonSymbol",
                    "symbolLayers": [{
                        "type": "CIMSolidFill",
                        "enable": True,
                        "color": {"type": "CIMRGBColor", "values": rgb}
                    }]
                }
        except Exception as e:
            logger.debug(f"Symbol conversion fallback: {e}")
            return {"type": "CIMSymbolReference", "note": "Fallback symbol"}


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
            tuple: (success: bool, error_message: str or None)
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
                error_msg = result[1] if len(result) > 1 else "Unknown error"
                logger.error(f"Export failed for layer '{layer.name()}': {error_msg}")
                return False, error_msg
            
            # Save style if requested
            if save_styles:
                self._save_layer_style(layer, output_path, style_format, datatype)
            
            return True, None
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Export exception for layer '{layer.name()}': {error_msg}")
            return False, error_msg


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
            success, error_msg = self._export_single_layer(
                layer, output_path, projection, datatype, style_format, save_styles
            )
            
            if not success:
                logger.error(f"Failed to export layer '{layer_name}': {error_msg}")
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
                self.error_details = f"Failed to create output directory: {str(e)}"
                return False
        
        total_layers = len(layer_names)
        exported_files = []
        failed_layers = []  # Track failed layers with reasons
        skipped_layers = []  # Track skipped layers (not found)
        
        for idx, layer_item in enumerate(layer_names, 1):
            # Handle both dict (layer info) and string (layer name) formats
            layer_name = layer_item['layer_name'] if isinstance(layer_item, dict) else layer_item
            
            # Update task description with current progress
            self.setDescription(f"Batch export: layer {idx}/{total_layers}: {layer_name}")
            self.setProgress(int((idx / total_layers) * 100))
            
            layer = self._get_layer_by_name(layer_name)
            if not layer:
                logger.warning(f"Skipping layer '{layer_name}' (not found)")
                skipped_layers.append(layer_name)
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
                success, error_msg = self._export_single_layer(
                    layer, output_path, projection, datatype, style_format, save_styles
                )
                
                if success:
                    exported_files.append(output_path)
                    logger.info(f"Successfully exported: {layer_name}")
                else:
                    error_detail = f"{layer_name}: {error_msg}" if error_msg else layer_name
                    failed_layers.append(error_detail)
                    logger.error(f"Failed to export layer '{layer_name}': {error_msg}")
                    
            except Exception as e:
                import traceback
                error_detail = f"{layer_name}: {str(e)}"
                failed_layers.append(error_detail)
                logger.error(f"Exception during export of '{layer_name}': {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
            
            if self.isCanceled():
                logger.info("Batch export cancelled by user")
                self.error_details = f"Export cancelled by user. Exported {len(exported_files)}/{total_layers} layers."
                return False
        
        # Build detailed summary
        success_count = len(exported_files)
        total_attempted = len(layer_names)
        
        if failed_layers or skipped_layers:
            # Some failures occurred
            details = []
            if success_count > 0:
                details.append(f"✓ {success_count} layer(s) exported successfully")
            if failed_layers:
                details.append(f"✗ {len(failed_layers)} layer(s) failed:")
                for failed in failed_layers[:5]:  # Limit to first 5 to avoid too long messages
                    details.append(f"  - {failed}")
                if len(failed_layers) > 5:
                    details.append(f"  ... and {len(failed_layers) - 5} more (see logs)")
            if skipped_layers:
                details.append(f"⚠ {len(skipped_layers)} layer(s) not found: {', '.join(skipped_layers[:3])}")
                if len(skipped_layers) > 3:
                    details.append(f"  ... and {len(skipped_layers) - 3} more")
            
            self.error_details = "\n".join(details)
            logger.warning(f"Batch export completed with errors: {success_count}/{total_attempted} successful")
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
                self.error_details = f"Failed to create output directory: {str(e)}"
                return False
        
        total_layers = len(layer_names)
        exported_zips = []
        failed_layers = []  # Track failed layers with reasons
        skipped_layers = []  # Track skipped layers (not found)
        
        for idx, layer_item in enumerate(layer_names, 1):
            # Handle both dict (layer info) and string (layer name) formats
            layer_name = layer_item['layer_name'] if isinstance(layer_item, dict) else layer_item
            
            # Update task description with current progress
            self.setDescription(f"Batch ZIP export: layer {idx}/{total_layers}: {layer_name}")
            self.setProgress(int((idx / total_layers) * 100))
            
            layer = self._get_layer_by_name(layer_name)
            if not layer:
                logger.warning(f"Skipping layer '{layer_name}' (not found)")
                skipped_layers.append(layer_name)
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
                
                success, error_msg = self._export_single_layer(
                    layer, temp_output, projection, datatype, style_format, save_styles
                )
                
                if not success:
                    error_detail = f"{layer_name}: {error_msg}" if error_msg else layer_name
                    failed_layers.append(error_detail)
                    logger.error(f"Failed to export layer '{layer_name}': {error_msg}")
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    continue  # Continue with next layer instead of failing entire batch
                
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
                    error_detail = f"{layer_name}: Failed to create ZIP archive"
                    failed_layers.append(error_detail)
                    logger.error(f"Failed to create ZIP for '{layer_name}' at {zip_path}")
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    continue  # Continue with next layer instead of failing entire batch
                
                # Clean up temporary directory
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
                
            except Exception as e:
                import traceback
                error_detail = f"{layer_name}: {str(e)}"
                failed_layers.append(error_detail)
                logger.error(f"Error during batch ZIP export of '{layer_name}': {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            
            if self.isCanceled():
                logger.info("Batch ZIP export cancelled by user")
                self.error_details = f"Export cancelled by user. Created {len(exported_zips)}/{total_layers} ZIP files."
                return False
        
        # Build detailed summary
        success_count = len(exported_zips)
        total_attempted = len(layer_names)
        
        if failed_layers or skipped_layers:
            # Some failures occurred
            details = []
            if success_count > 0:
                details.append(f"✓ {success_count} ZIP file(s) created successfully")
            if failed_layers:
                details.append(f"✗ {len(failed_layers)} layer(s) failed:")
                for failed in failed_layers[:5]:  # Limit to first 5 to avoid too long messages
                    details.append(f"  - {failed}")
                if len(failed_layers) > 5:
                    details.append(f"  ... and {len(failed_layers) - 5} more (see logs)")
            if skipped_layers:
                details.append(f"⚠ {len(skipped_layers)} layer(s) not found: {', '.join(skipped_layers[:3])}")
                if len(skipped_layers) > 3:
                    details.append(f"  ... and {len(skipped_layers) - 3} more")
            
            self.error_details = "\n".join(details)
            logger.warning(f"Batch ZIP export completed with errors: {success_count}/{total_attempted} successful")
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
                # Use detailed error info if available
                if hasattr(self, 'error_details') and self.error_details:
                    self.message = f'Batch export completed with errors:\n{self.error_details}'
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
                # Use detailed error info if available
                if hasattr(self, 'error_details') and self.error_details:
                    self.message = f'Batch ZIP export completed with errors:\n{self.error_details}'
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
        from ..appUtils import get_spatialite_datasource_from_layer
        
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
        
        # Build ST_Buffer style parameters (quad_segs for segments, endcap for buffer type)
        buffer_type_mapping = {"Round": "round", "Flat": "flat", "Square": "square"}
        buffer_type_str = self.task_parameters["filtering"].get("buffer_type", "Round")
        endcap_style = buffer_type_mapping.get(buffer_type_str, "round")
        quad_segs = self.param_buffer_segments
        
        # Build style string for Spatialite ST_Buffer
        style_params = f"quad_segs={quad_segs}"
        if endcap_style != 'round':
            style_params += f" endcap={endcap_style}"
        
        # Build Spatialite SELECT (similar to PostgreSQL CREATE MATERIALIZED VIEW)
        # Note: Spatialite uses same ST_Buffer syntax as PostGIS
        query = f"""
            SELECT 
                ST_Buffer({geom_key_name}, {buffer_expr}, '{style_params}') as {geom_key_name},
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
        # Use session-prefixed name for multi-client isolation
        session_name = self._get_session_prefixed_name(name)
        
        # Apply subset string to layer (reference temp table)
        layer_subsetString = f'"{primary_key_name}" IN (SELECT "{primary_key_name}" FROM mv_{session_name})'
        logger.debug(f"Applying Spatialite subset string: {layer_subsetString}")
        
        # THREAD SAFETY: Queue subset string for application in finished()
        self._queue_subset_string(layer, layer_subsetString)
        
        # Note: We assume success since the actual application happens in finished()
        # The history update proceeds with the assumption that the filter will be applied
        
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
        from ..appUtils import create_temp_spatialite_table
        
        # Get datasource information
        db_path, table_name, layer_srid, is_native_spatialite = self._get_spatialite_datasource(layer)
        
        # For non-Spatialite layers, use QGIS subset string directly (queued for main thread)
        if not is_native_spatialite:
            self._queue_subset_string(layer, sql_subset_string)
            return True
        
        # Build Spatialite query (simple or buffered)
        spatialite_query = self._build_spatialite_query(
            sql_subset_string, 
            table_name, 
            geom_key_name, 
            primary_key_name, 
            custom
        )
        
        # Create temporary table with session-prefixed name
        session_name = self._get_session_prefixed_name(name)
        logger.info(f"Creating Spatialite temp table 'mv_{session_name}' (session: {self.session_id})")
        success = create_temp_spatialite_table(
            db_path=db_path,
            table_name=session_name,
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
            
        Raises:
            ValueError: If sql_subset_string is empty or None
        """
        # CRITICAL FIX: Validate sql_subset_string is not empty
        # Empty sql_subset_string causes SQL syntax error: "AS WITH DATA;" without SELECT
        if not sql_subset_string or not sql_subset_string.strip():
            raise ValueError(
                f"Cannot create materialized view 'mv_{name}': sql_subset_string is empty. "
                f"This usually means the filter expression was not properly built."
            )
        
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
        
        # Build ST_Buffer style parameters (quad_segs for segments, endcap for buffer type)
        buffer_type_mapping = {"Round": "round", "Flat": "flat", "Square": "square"}
        buffer_type_str = self.task_parameters["filtering"].get("buffer_type", "Round")
        endcap_style = buffer_type_mapping.get(buffer_type_str, "round")
        quad_segs = self.param_buffer_segments
        
        # Build style string for PostGIS ST_Buffer
        style_params = f"quad_segs={quad_segs}"
        if endcap_style != 'round':
            style_params += f" endcap={endcap_style}"
        
        template = '''CREATE MATERIALIZED VIEW IF NOT EXISTS "{schema}"."mv_{name}" TABLESPACE pg_default AS 
            SELECT ST_Buffer({postgresql_source_geom}, {param_buffer_expression}, '{style_params}') as {geometry_field}, 
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
            where_expression=' OR '.join(self._parse_where_clauses()).replace('mv_', ''),
            style_params=style_params
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


    def _ensure_temp_schema_exists(self, connexion, schema_name):
        """
        Ensure the temporary schema exists in PostgreSQL database.
        
        Creates the schema if it doesn't exist. This is required before
        creating materialized views in the schema.
        
        Args:
            connexion: psycopg2 connection
            schema_name: Name of the schema to create
            
        Returns:
            bool: True if schema exists or was created successfully
            
        Raises:
            Exception: If connection is invalid or schema creation fails
        """
        # Validate connection before use
        if connexion is None:
            logger.error("Cannot ensure temp schema: connection is None")
            raise Exception(f"Cannot create schema '{schema_name}': PostgreSQL connection is None")
        
        # Check if connexion is a string (connection string) instead of a connection object
        if isinstance(connexion, str):
            logger.error(f"Cannot ensure temp schema: connexion is a string ('{connexion[:50]}...'), not a connection object")
            raise Exception(f"Cannot create schema '{schema_name}': PostgreSQL connexion is a string, not a connection object. This indicates ACTIVE_POSTGRESQL was not properly initialized.")
        
        # Check if connection has cursor method (duck typing validation)
        if not hasattr(connexion, 'cursor') or not callable(getattr(connexion, 'cursor', None)):
            logger.error(f"Cannot ensure temp schema: connexion object has no cursor() method (type: {type(connexion).__name__})")
            raise Exception(f"Cannot create schema '{schema_name}': PostgreSQL connexion is not a valid connection object (type: {type(connexion).__name__})")
        
        # Check if connection is closed
        try:
            if connexion.closed:
                logger.error("Cannot ensure temp schema: connection is closed")
                raise Exception(f"Cannot create schema '{schema_name}': PostgreSQL connection is closed")
        except AttributeError:
            # Connection object doesn't have 'closed' attribute - proceed anyway
            pass
        
        # First check if schema already exists
        try:
            with connexion.cursor() as cursor:
                cursor.execute("""
                    SELECT schema_name FROM information_schema.schemata 
                    WHERE schema_name = %s
                """, (schema_name,))
                result = cursor.fetchone()
                if result:
                    logger.debug(f"Schema '{schema_name}' already exists")
                    return True
        except Exception as check_e:
            logger.debug(f"Could not check if schema exists: {check_e}")
            # Continue to try creating it
        
        # Try creating schema without explicit authorization (uses current user)
        try:
            with connexion.cursor() as cursor:
                cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}";')
                connexion.commit()
            logger.debug(f"Ensured schema '{schema_name}' exists")
            return True
        except Exception as e:
            logger.warning(f"Error creating schema '{schema_name}' (no auth): {e}")
            # Rollback failed transaction
            try:
                connexion.rollback()
            except:
                pass
            
            # Try with explicit AUTHORIZATION CURRENT_USER as fallback
            try:
                with connexion.cursor() as cursor:
                    cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}" AUTHORIZATION CURRENT_USER;')
                    connexion.commit()
                logger.debug(f"Created schema '{schema_name}' with CURRENT_USER authorization")
                return True
            except Exception as e2:
                logger.warning(f"Error creating schema with CURRENT_USER: {e2}")
                try:
                    connexion.rollback()
                except:
                    pass
                
                # Final fallback: try with postgres authorization
                try:
                    with connexion.cursor() as cursor:
                        cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}" AUTHORIZATION postgres;')
                        connexion.commit()
                    logger.debug(f"Created schema '{schema_name}' with postgres authorization")
                    return True
                except Exception as e3:
                    try:
                        connexion.rollback()
                    except:
                        pass
                    error_msg = f"Failed to create temp schema '{schema_name}': No auth error: {e}, CURRENT_USER error: {e2}, postgres auth error: {e3}"
                    logger.error(error_msg)
                    # Store the error for the calling code
                    self._last_schema_error = error_msg
                    return False


    def _get_session_prefixed_name(self, base_name):
        """
        Generate a session-unique materialized view name.
        
        Prefixes the base name with the session_id to ensure different
        QGIS clients don't conflict when using the same PostgreSQL database.
        
        Args:
            base_name: Original layer-based name
            
        Returns:
            str: Session-prefixed name (e.g., "a1b2c3d4_layername")
        """
        if self.session_id:
            return f"{self.session_id}_{base_name}"
        return base_name


    def _cleanup_session_materialized_views(self, connexion, schema_name):
        """
        Clean up all materialized views for the current session.
        
        Drops all materialized views and indexes prefixed with the session_id.
        Should be called when closing the plugin or resetting.
        
        Args:
            connexion: psycopg2 connection
            schema_name: Schema containing the materialized views
            
        Returns:
            int: Number of views cleaned up
        """
        if not self.session_id:
            return 0
        
        try:
            with connexion.cursor() as cursor:
                # Find all materialized views for this session
                cursor.execute("""
                    SELECT matviewname FROM pg_matviews 
                    WHERE schemaname = %s AND matviewname LIKE %s
                """, (schema_name, f"mv_{self.session_id}_%"))
                views = cursor.fetchall()
                
                count = 0
                for (view_name,) in views:
                    try:
                        # Drop associated index first
                        index_name = view_name.replace('mv_', f'{schema_name}_').replace('_dump', '') + '_cluster'
                        cursor.execute(f'DROP INDEX IF EXISTS "{schema_name}"."{index_name}" CASCADE;')
                        # Drop the view
                        cursor.execute(f'DROP MATERIALIZED VIEW IF EXISTS "{schema_name}"."{view_name}" CASCADE;')
                        count += 1
                    except Exception as e:
                        logger.warning(f"Error dropping view {view_name}: {e}")
                
                connexion.commit()
                if count > 0:
                    logger.info(f"Cleaned up {count} materialized view(s) for session {self.session_id}")
                return count
        except Exception as e:
            logger.error(f"Error cleaning up session views: {e}")
            return 0


    def _cleanup_orphaned_materialized_views(self, connexion, schema_name, max_age_hours=24):
        """
        Clean up orphaned materialized views older than max_age_hours.
        
        This is a maintenance function to clean up views from crashed sessions
        or sessions that didn't clean up properly.
        
        Args:
            connexion: psycopg2 connection
            schema_name: Schema containing the materialized views
            max_age_hours: Maximum age in hours before a view is considered orphaned
            
        Returns:
            int: Number of views cleaned up
        """
        try:
            with connexion.cursor() as cursor:
                # Find all materialized views in the schema
                # Note: PostgreSQL doesn't track matview creation time directly,
                # so we rely on naming convention and periodic cleanup
                cursor.execute("""
                    SELECT matviewname FROM pg_matviews 
                    WHERE schemaname = %s AND matviewname LIKE 'mv_%'
                """, (schema_name,))
                views = cursor.fetchall()
                
                count = 0
                for (view_name,) in views:
                    try:
                        # Try to drop views that start with an 8-char hex session prefix
                        # Format: mv_<session_id>_<layer_id>
                        parts = view_name[3:].split('_', 1)  # Remove 'mv_' prefix
                        if len(parts) >= 2 and len(parts[0]) == 8:
                            # This looks like a session-prefixed view
                            # In a real scenario, you might check if the session is still active
                            # For now, we just log and skip active session views
                            if parts[0] == self.session_id:
                                continue  # Skip our own session's views
                        
                        # For non-session views or very old ones, we could drop them
                        # But to be safe, we only log here
                        logger.debug(f"Found potentially orphaned view: {view_name}")
                    except Exception as e:
                        logger.debug(f"Error processing view {view_name}: {e}")
                
                return count
        except Exception as e:
            logger.error(f"Error checking orphaned views: {e}")
            return 0


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
        connexion = self._get_valid_postgresql_connection()
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
                    
                    # Pattern 4: FilterMate materialized view reference (fid IN SELECT from mv_...)
                    # CRITICAL FIX v2.5.11: Detect previous FilterMate geometric filters using materialized views
                    import re
                    has_mv_filter = bool(re.search(
                        r'IN\s*\(\s*SELECT.*FROM\s+["\']?filter_mate_temp["\']?\s*\.\s*["\']?mv_',
                        old_subset,
                        re.IGNORECASE | re.DOTALL
                    ))
                    
                    # If old_subset contains geometric filter patterns, replace instead of combine
                    if has_source_alias or has_exists or has_spatial_predicate or has_mv_filter:
                        final_expression = where_clause
                        reason = []
                        if has_source_alias:
                            reason.append("__source alias")
                        if has_exists:
                            reason.append("EXISTS subquery")
                        if has_spatial_predicate:
                            reason.append("spatial predicate")
                        if has_mv_filter:
                            reason.append("FilterMate materialized view (mv_)")
                        logger.info(f"Old subset contains {', '.join(reason)} - replacing instead of combining")
                    else:
                        # CRITICAL FIX v2.4.15: Detect QGIS style/symbology expressions
                        # These patterns indicate rule-based symbology filters that should NOT
                        # be combined with geometric filters as they cause type mismatch errors
                        import re
                        style_patterns = [
                            r'AND\s+TRUE\s*\)',           # Pattern: AND TRUE) - common in rule-based styles
                            r'THEN\s+true',               # CASE WHEN ... THEN true - style expression
                            r'THEN\s+false',              # CASE WHEN ... THEN false
                            r'SELECT\s+CASE',             # SELECT CASE in subquery
                            r'\)\s*AND\s+TRUE\s*\)',      # (...) AND TRUE) pattern
                        ]
                        has_style_pattern = any(
                            re.search(pattern, old_subset, re.IGNORECASE) 
                            for pattern in style_patterns
                        )
                        
                        if has_style_pattern:
                            final_expression = where_clause
                            logger.info(f"Old subset contains QGIS style patterns - replacing instead of combining")
                            logger.info(f"  → Detected style-based filter: '{old_subset[:80]}...'")
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
                
                # THREAD SAFETY: Queue filter for application in finished()
                self._queue_subset_string(layer, final_expression)
                
                # Log intent (actual application happens in finished())
                elapsed = time.time() - start_time
                logger.info(
                    f"Direct PostgreSQL filter queued in {elapsed:.3f}s. "
                    f"Will be applied on main thread."
                )
                
                # Insert history
                self._insert_subset_history(cur, conn, layer, sql_subset_string, seq_order)
                return True
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
        
        # Generate session-unique view name for multi-client isolation
        session_name = self._get_session_prefixed_name(name)
        logger.debug(f"Using session-prefixed view name: {session_name} (session_id: {self.session_id})")
        
        # Ensure temp schema exists before creating materialized views
        connexion = self._get_valid_postgresql_connection()
        if not self._ensure_temp_schema_exists(connexion, schema):
            error_detail = getattr(self, '_last_schema_error', 'Unknown error')
            raise Exception(f"Failed to ensure temp schema '{schema}' exists: {error_detail}")
        
        # Ensure source table has statistics for query optimization
        self._ensure_source_table_stats(
            connexion, 
            self.param_source_schema, 
            self.param_source_table, 
            geom_key_name
        )
        
        # Build SQL commands using session-prefixed name
        sql_drop = f'DROP INDEX IF EXISTS {schema}_{session_name}_cluster CASCADE; DROP MATERIALIZED VIEW IF EXISTS "{schema}"."mv_{session_name}" CASCADE;'
        
        if custom:
            # Parse custom buffer expression
            sql_drop += f' DROP MATERIALIZED VIEW IF EXISTS "{schema}"."mv_{session_name}_dump" CASCADE;'
            
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
            
            sql_create = self._create_custom_buffer_view_sql(schema, session_name, geom_key_name, where_clause_fields_arr, last_subset_id, sql_subset_string)
        else:
            sql_create = self._create_simple_materialized_view_sql(schema, session_name, sql_subset_string)
        
        sql_create_index = f'CREATE INDEX IF NOT EXISTS {schema}_{session_name}_cluster ON "{schema}"."mv_{session_name}" USING GIST ({geom_key_name});'
        sql_cluster = f'ALTER MATERIALIZED VIEW IF EXISTS  "{schema}"."mv_{session_name}" CLUSTER ON {schema}_{session_name}_cluster;'
        sql_analyze = f'ANALYZE VERBOSE "{schema}"."mv_{session_name}";'
        
        sql_create = sql_create.replace('\n', '').replace('\t', '').replace('  ', ' ').strip()
        logger.debug(f"SQL drop request: {sql_drop}")
        logger.debug(f"SQL create request: {sql_create}")
        
        # Execute PostgreSQL commands
        connexion = self._get_valid_postgresql_connection()
        commands = [sql_drop, sql_create, sql_create_index, sql_cluster, sql_analyze]
        
        if custom:
            sql_dump = f'CREATE MATERIALIZED VIEW IF NOT EXISTS "{schema}"."mv_{session_name}_dump" as SELECT ST_Union("{geom_key_name}") as {geom_key_name} from "{schema}"."mv_{session_name}";'
            commands.append(sql_dump)
        
        self._execute_postgresql_commands(connexion, commands)
        
        # Insert history
        self._insert_subset_history(cur, conn, layer, sql_subset_string, seq_order)
        
        # Set subset string on layer using session-prefixed view name
        # THREAD SAFETY: Queue for application in finished()
        layer_subset_string = f'"{primary_key_name}" IN (SELECT "mv_{session_name}"."{primary_key_name}" FROM "{schema}"."mv_{session_name}")'
        logger.debug(f"Layer subset string: {layer_subset_string}")
        self._queue_subset_string(layer, layer_subset_string)
        
        elapsed = time.time() - start_time
        logger.info(
            f"Materialized view created in {elapsed:.2f}s. "
            f"Filter queued for application on main thread."
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
        
        # Use session-prefixed name for multi-client isolation
        session_name = self._get_session_prefixed_name(name)
        sql_drop = f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."mv_{session_name}" CASCADE;'
        sql_drop += f' DROP MATERIALIZED VIEW IF EXISTS "{schema}"."mv_{session_name}_dump" CASCADE;'
        sql_drop += f' DROP INDEX IF EXISTS {schema}_{session_name}_cluster CASCADE;'
        
        connexion = self._get_valid_postgresql_connection()
        self._execute_postgresql_commands(connexion, [sql_drop])
        
        # THREAD SAFETY: Queue subset clear for application in finished()
        self._queue_subset_string(layer, '')
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
        
        # Drop temp table from filterMate_db using session-prefixed name
        import sqlite3
        session_name = self._get_session_prefixed_name(name)
        try:
            temp_conn = sqlite3.connect(self.db_file_path)
            temp_cur = temp_conn.cursor()
            temp_cur.execute(f"DROP TABLE IF EXISTS mv_{session_name}")
            temp_conn.commit()
            temp_cur.close()
            temp_conn.close()
        except Exception as e:
            logger.error(f"Error dropping Spatialite temp table: {e}")
        
        # THREAD SAFETY: Queue subset clear for application in finished()
        self._queue_subset_string(layer, '')
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
            
            # CRITICAL FIX: Validate sql_subset_string from history before using
            if not sql_subset_string or not sql_subset_string.strip():
                logger.warning(
                    f"Unfilter: Previous subset string from history is empty for {layer.name()}. "
                    f"Clearing layer filter."
                )
                # THREAD SAFETY: Queue subset clear for application in finished()
                self._queue_subset_string(layer, '')
                return True
            
            if use_spatialite:
                logger.info("Unfilter - Spatialite backend - recreating previous subset")
                success = self._manage_spatialite_subset(
                    layer, sql_subset_string, primary_key_name, geom_key_name,
                    name, custom=False, cur=None, conn=None, current_seq_order=0
                )
                if not success:
                    # THREAD SAFETY: Queue subset clear for application in finished()
                    self._queue_subset_string(layer, '')
            
            elif use_postgresql:
                schema = self.current_materialized_view_schema
                
                # Use session-prefixed name for multi-client isolation
                session_name = self._get_session_prefixed_name(name)
                
                sql_drop = f'DROP INDEX IF EXISTS {schema}_{session_name}_cluster CASCADE; DROP MATERIALIZED VIEW IF EXISTS "{schema}"."mv_{session_name}" CASCADE;'
                sql_create = self._create_simple_materialized_view_sql(schema, session_name, sql_subset_string)
                sql_create_index = f'CREATE INDEX IF NOT EXISTS {schema}_{session_name}_cluster ON "{schema}"."mv_{session_name}" USING GIST ({geom_key_name});'
                sql_cluster = f'ALTER MATERIALIZED VIEW IF EXISTS  "{schema}"."mv_{session_name}" CLUSTER ON {schema}_{session_name}_cluster;'
                sql_analyze = f'ANALYZE VERBOSE "{schema}"."mv_{session_name}";'
                
                sql_create = sql_create.replace('\n', '').replace('\t', '').replace('  ', ' ').strip()
                
                connexion = self._get_valid_postgresql_connection()
                self._execute_postgresql_commands(connexion, [sql_drop, sql_create, sql_create_index, sql_cluster, sql_analyze])
                
                layer_subset_string = f'"{primary_key_name}" IN (SELECT "mv_{session_name}"."{primary_key_name}" FROM "{schema}"."mv_{session_name}")'
                # THREAD SAFETY: Queue subset for application in finished()
                self._queue_subset_string(layer, layer_subset_string)
        else:
            # THREAD SAFETY: Queue subset clear for application in finished()
            self._queue_subset_string(layer, '')
        
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
                
                # CRITICAL FIX: Skip materialized view creation if sql_subset_string is empty
                # Empty sql_subset_string causes SQL syntax error in materialized view creation
                if not sql_subset_string or not sql_subset_string.strip():
                    logger.warning(
                        f"Skipping subset management for {layer.name()}: "
                        f"sql_subset_string is empty. Filter was applied via setSubsetString but "
                        f"history/materialized view creation is skipped."
                    )
                    return True
                
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
                # FIX v2.3.9: Reset prepared statements manager when connection closes
                # to avoid "Cannot operate on a closed database" errors
                self._ps_manager = None

    def _is_complex_filter(self, subset: str, provider_type: str) -> bool:
        """
        Check if a filter expression is complex (requires longer refresh delay).
        
        FIX v2.5.21: Used to determine appropriate refresh timing after filter application.
        Complex filters include:
        - PostgreSQL: EXISTS, ST_Buffer, ST_Intersects, __source, large IN clauses
        - Spatialite: ST_*, Intersects, Contains, Within functions
        - OGR: Large IN clauses (>50 IDs) or expressions > 1000 chars
        
        Args:
            subset: The filter expression string
            provider_type: Layer provider type (postgres, spatialite, ogr)
            
        Returns:
            True if filter is complex, False otherwise
        """
        if not subset:
            return False
            
        subset_upper = subset.upper()
        
        if provider_type == 'postgres':
            return (
                'EXISTS' in subset_upper or
                'ST_BUFFER' in subset_upper or
                'ST_INTERSECTS' in subset_upper or
                'ST_CONTAINS' in subset_upper or
                'ST_WITHIN' in subset_upper or
                '__source' in subset.lower() or
                (subset_upper.count(',') > 100 and ' IN (' in subset_upper)
            )
        elif provider_type == 'spatialite':
            return (
                'ST_BUFFER' in subset_upper or
                'ST_INTERSECTS' in subset_upper or
                'ST_CONTAINS' in subset_upper or
                'ST_WITHIN' in subset_upper or
                'INTERSECTS(' in subset_upper or
                'CONTAINS(' in subset_upper or
                'WITHIN(' in subset_upper or
                (subset_upper.count(',') > 100 and ' IN (' in subset_upper)
            )
        elif provider_type == 'ogr':
            return (
                (subset_upper.count(',') > 50 and ' IN (' in subset_upper) or
                len(subset) > 1000
            )
        return False

    def _single_canvas_refresh(self):
        """
        Perform a single comprehensive canvas refresh after filter application.
        
        FIX v2.5.21: Replaces the previous multi-refresh approach that caused
        overlapping refreshes to cancel each other, leaving the canvas white.
        
        FIX v2.6.5: PERFORMANCE - Only refresh layers involved in filtering,
        not ALL project layers. Skip updateExtents() for large layers.
        
        This method:
        1. Stops any ongoing rendering to avoid conflicts
        2. Forces reload for layers with complex filters
        3. Triggers repaint for filtered layers (skip expensive updateExtents for large layers)
        4. Performs a single final canvas refresh
        """
        try:
            from qgis.core import QgsProject
            
            canvas = iface.mapCanvas()
            
            # Step 1: Stop any ongoing rendering to get a clean slate
            canvas.stopRendering()
            
            layers_reloaded = 0
            layers_repainted = 0
            
            # v2.6.5: Limit expensive operations to prevent UI freeze
            MAX_FEATURES_FOR_UPDATE_EXTENTS = 50000  # Skip updateExtents for large layers
            
            # Step 2: Process only filtered vector layers (not ALL layers)
            for layer_id, layer in QgsProject.instance().mapLayers().items():
                try:
                    if layer.type() != 0:  # Not a vector layer
                        continue
                    
                    subset = layer.subsetString() or ''
                    if not subset:
                        continue  # Skip unfiltered layers - MAJOR OPTIMIZATION
                    
                    provider_type = layer.providerType()
                    
                    # v2.6.6: FREEZE FIX - Only use reloadData() for PostgreSQL
                    # For OGR/Spatialite, reloadData() can block for a long time
                    # on large FID IN (...) filters, causing QGIS to freeze.
                    # triggerRepaint() is sufficient for file-based providers.
                    if provider_type == 'postgres':
                        # PostgreSQL: Force reload for complex filters (MV-based)
                        if self._is_complex_filter(subset, provider_type):
                            try:
                                layer.dataProvider().reloadData()
                                layers_reloaded += 1
                            except Exception as reload_err:
                                logger.debug(f"reloadData() failed for {layer.name()}: {reload_err}")
                                try:
                                    layer.reload()
                                except Exception:
                                    pass
                        else:
                            try:
                                layer.reload()
                            except Exception:
                                pass
                    # v2.6.6: For OGR/Spatialite, just triggerRepaint() - NO reloadData()
                    # This prevents the freeze caused by re-evaluating large FID IN filters
                    
                    # v2.6.5: Skip updateExtents for large layers to prevent freeze
                    feature_count = layer.featureCount()
                    if feature_count >= 0 and feature_count < MAX_FEATURES_FOR_UPDATE_EXTENTS:
                        layer.updateExtents()
                    # else: skip expensive updateExtents for very large layers
                    
                    layer.triggerRepaint()
                    layers_repainted += 1
                    
                except Exception as layer_err:
                    logger.debug(f"Layer refresh failed: {layer_err}")
            
            # Step 3: Single final canvas refresh
            canvas.refresh()
            
            logger.debug(f"Single canvas refresh: reloaded {layers_reloaded}, repainted {layers_repainted} layers")
            
        except Exception as e:
            logger.debug(f"Single canvas refresh failed: {e}")
            # Last resort fallback
            try:
                iface.mapCanvas().refresh()
            except Exception:
                pass

    def _delayed_canvas_refresh(self):
        """
        Perform a delayed canvas refresh for all filtered layers.
        
        FIX v2.5.15: This is called via QTimer.singleShot after the initial
        refresh to allow providers to complete their data fetch.
        Using a timer avoids blocking the main thread while still ensuring
        the canvas is properly updated.
        
        FIX v2.5.11: Also force updateExtents for all visible layers to fix
        display issues with complex spatial queries (e.g., buffered EXISTS).
        
        FIX v2.5.19: Force aggressive reload for layers with complex filters
        (EXISTS, ST_Buffer, IN clauses, etc.) to ensure data provider cache is cleared.
        This fixes display issues after multi-step filtering with spatial predicates.
        
        FIX v2.5.20: Extended support for Spatialite and OGR layers with complex filters.
        - Spatialite: ST_*, Intersects, Contains, Within functions
        - OGR: IN clause with many IDs (typical for selectbylocation results)
        """
        try:
            from qgis.core import QgsProject
            
            layers_refreshed = {
                'postgres': 0,
                'spatialite': 0,
                'ogr': 0,
                'other': 0
            }
            
            # v2.6.6: Skip updateExtents for large layers to prevent freeze
            MAX_FEATURES_FOR_UPDATE_EXTENTS = 50000
            
            for layer_id, layer in QgsProject.instance().mapLayers().items():
                try:
                    if layer.type() == 0:  # Vector layer
                        provider_type = layer.providerType()
                        subset = layer.subsetString() or ''
                        if not subset:
                            continue  # Skip unfiltered layers
                        
                        subset_upper = subset.upper()
                        
                        # v2.6.6: FREEZE FIX - Only use reloadData() for PostgreSQL
                        # For OGR/Spatialite, reloadData() blocks on large FID IN filters
                        if provider_type == 'postgres':
                            # PostgreSQL: EXISTS, ST_*, __source
                            has_complex_filter = (
                                'EXISTS' in subset_upper or
                                'ST_BUFFER' in subset_upper or
                                'ST_INTERSECTS' in subset_upper or
                                'ST_CONTAINS' in subset_upper or
                                'ST_WITHIN' in subset_upper or
                                '__source' in subset.lower() or
                                # Large IN clause (> 100 IDs)
                                (subset_upper.count(',') > 100 and ' IN (' in subset_upper)
                            )
                            
                            if has_complex_filter:
                                try:
                                    layer.dataProvider().reloadData()
                                    logger.debug(f"  → Forced reloadData() for {layer.name()} (postgres, complex filter)")
                                except Exception as reload_err:
                                    logger.debug(f"  → reloadData() failed for {layer.name()}: {reload_err}")
                                    try:
                                        layer.reload()
                                    except Exception:
                                        pass
                                layers_refreshed['postgres'] += 1
                            else:
                                try:
                                    layer.reload()
                                except Exception:
                                    pass
                        # v2.6.6: For OGR/Spatialite, just triggerRepaint - NO reloadData()
                        # This prevents freeze on large FID IN filters
                        
                        # v2.6.6: Skip updateExtents for large layers to prevent freeze
                        feature_count = layer.featureCount()
                        if feature_count >= 0 and feature_count < MAX_FEATURES_FOR_UPDATE_EXTENTS:
                            layer.updateExtents()
                        layer.triggerRepaint()
                        
                except Exception as layer_err:
                    logger.debug(f"  → Layer refresh failed: {layer_err}")
            
            # Final canvas refresh
            iface.mapCanvas().refresh()
            
            # Log summary
            total_refreshed = sum(layers_refreshed.values())
            if total_refreshed > 0:
                refresh_summary = ", ".join(
                    f"{count} {ptype}" for ptype, count in layers_refreshed.items() if count > 0
                )
                logger.debug(f"Delayed canvas refresh: reloaded {refresh_summary} layer(s)")
            else:
                logger.debug("Delayed canvas refresh completed")
                
        except Exception as e:
            logger.debug(f"Delayed canvas refresh skipped: {e}")

    def _final_canvas_refresh(self):
        """
        Perform a final canvas refresh after all filter queries have completed.
        
        FIX v2.5.19: This is the last refresh pass, scheduled 2 seconds after filtering
        to ensure even slow queries with complex EXISTS, ST_Buffer, and large IN clauses
        have completed.
        
        FIX v2.5.20: Extended to all provider types (PostgreSQL, Spatialite, OGR).
        This method:
        1. Triggers repaint for all filtered vector layers
        2. Forces canvas full refresh
        
        This fixes display issues where complex multi-step filters don't show
        all filtered features immediately after the filter task completes.
        """
        try:
            from qgis.core import QgsProject
            
            # Final refresh for all vector layers with filters
            layers_repainted = 0
            for layer_id, layer in QgsProject.instance().mapLayers().items():
                try:
                    if layer.type() == 0:  # Vector layer
                        # Check if layer has any filter applied
                        subset = layer.subsetString()
                        if subset:
                            layer.triggerRepaint()
                            layers_repainted += 1
                except Exception:
                    pass
            
            # Final canvas refresh
            iface.mapCanvas().refresh()
            
            if layers_repainted > 0:
                logger.debug(f"Final canvas refresh: repainted {layers_repainted} filtered layer(s)")
            else:
                logger.debug("Final canvas refresh completed (2s delay)")
            logger.debug("Final canvas refresh completed (2s delay)")
            
        except Exception as e:
            logger.debug(f"Final canvas refresh skipped: {e}")

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
        # FIX v2.3.9: Reset prepared statements manager when connections close
        self._ps_manager = None
        
        QgsMessageLog.logMessage(
            '"{name}" task was canceled'.format(name=self.description()),
            MESSAGE_TASKS_CATEGORIES[self.task_action], Qgis.Info)
        super().cancel()


    def finished(self, result):
        result_action = None
        message_category = MESSAGE_TASKS_CATEGORIES[self.task_action]
        
        # THREAD SAFETY FIX v2.5.6: Display any warnings stored during worker thread execution
        # These warnings (like negative buffer erosion) could not be displayed from worker thread
        if hasattr(self, 'warning_messages') and self.warning_messages:
            for warning_msg in self.warning_messages:
                iface.messageBar().pushWarning("FilterMate", warning_msg)
            self.warning_messages = []  # Clear after display
        
        # CANCELLATION FIX v2.3.22: Don't apply pending subset requests if task was canceled
        # This prevents duplicate filter applications when user cancels during parallel execution
        if self.isCanceled():
            logger.info("Task was canceled - skipping pending subset requests to prevent partial filter application")
            if hasattr(self, '_pending_subset_requests'):
                self._pending_subset_requests = []  # Clear to prevent any application
        
        # THREAD SAFETY FIX v2.3.21: Apply pending subset strings on main thread
        # This is called from the main Qt thread (unlike run() which is on a worker thread).
        # Process all pending subset requests stored during run()
        if hasattr(self, '_pending_subset_requests') and self._pending_subset_requests:
            logger.debug(f"finished(): Applying {len(self._pending_subset_requests)} pending subset requests on main thread")
            
            # v2.7.9: Log all pending requests details
            for idx, (lyr, expr) in enumerate(self._pending_subset_requests):
                lyr_name = lyr.name() if lyr and is_valid_layer(lyr) else "INVALID"
                expr_preview = (expr[:80] + '...') if expr and len(expr) > 80 else (expr or 'EMPTY')
                logger.debug(f"  [{idx+1}] {lyr_name}: {expr_preview}")
            
            # v2.6.5: PERFORMANCE - Skip updateExtents for large layers to prevent freeze
            MAX_FEATURES_FOR_UPDATE_EXTENTS = 50000
            # v2.6.5: Maximum expression length before using deferred application
            MAX_EXPRESSION_FOR_DIRECT_APPLY = 100000  # 100KB
            
            # v2.6.5: Collect large expressions for deferred/chunked application
            large_expressions = []
            
            for layer, expression in self._pending_subset_requests:
                try:
                    if layer and is_valid_layer(layer):
                        # FIX v2.5.11: Check if filter is already applied to avoid redundant application
                        # This happens for source layer which is filtered during run()
                        current_subset = layer.subsetString() or ''
                        expression_str = expression or ''
                        
                        # v2.6.5: Check if expression is too large for direct application
                        if expression_str and len(expression_str) > MAX_EXPRESSION_FOR_DIRECT_APPLY:
                            logger.warning(f"  ⚠️ Large expression ({len(expression_str)} chars) for {layer.name()} - deferring")
                            large_expressions.append((layer, expression_str))
                            continue
                        
                        if current_subset.strip() == expression_str.strip():
                            # Filter already applied - force reload for PostgreSQL layers
                            # FIX v2.5.16: Use layer.reload() for PostgreSQL to force data refresh
                            # This is less aggressive than dataProvider().reloadData() but more
                            # effective than just triggerRepaint()
                            if layer.providerType() == 'postgres':
                                layer.reload()
                            # v2.6.5: Skip updateExtents for large layers
                            feature_count = layer.featureCount()
                            if feature_count >= 0 and feature_count < MAX_FEATURES_FOR_UPDATE_EXTENTS:
                                layer.updateExtents()
                            layer.triggerRepaint()
                            
                            logger.debug(f"  ✓ Filter already applied to {layer.name()}, triggered reload+repaint")
                            
                            count_str = f"{feature_count} features" if feature_count >= 0 else "(count pending)"
                            logger.debug(f"finished() ✓ Repaint: {layer.name()} → {count_str} (filter already applied)")
                        else:
                            # FIX v2.4.13: Use safe_set_subset_string to apply PostgreSQL type casting
                            # This fixes "operator does not exist: character varying < integer" errors
                            success = safe_set_subset_string(layer, expression)
                            if success:
                                # FIX v2.5.16: Force layer reload for PostgreSQL after setSubsetString
                                # For PostgreSQL layers with MV-based filters (IN SELECT queries),
                                # the provider cache may not refresh automatically
                                if layer.providerType() == 'postgres':
                                    layer.reload()
                                # v2.6.5: Skip updateExtents for large layers
                                feature_count = layer.featureCount()
                                if feature_count >= 0 and feature_count < MAX_FEATURES_FOR_UPDATE_EXTENTS:
                                    layer.updateExtents()
                                layer.triggerRepaint()
                                
                                logger.debug(f"  ✓ Applied filter to {layer.name()}: {len(expression) if expression else 0} chars")
                                
                                # v2.4.13: Handle -1 feature count (unknown count for OGR/GeoPackage)
                                feature_count = layer.featureCount()
                                if feature_count >= 0:
                                    count_str = f"{feature_count} features"
                                    # v2.5.11: Additional diagnostic for layers with 0 features
                                    if feature_count == 0:
                                        logger.warning(f"  ⚠️ Layer {layer.name()} has 0 features after filtering!")
                                        logger.warning(f"    → Expression length: {len(expression)} chars")
                                        logger.warning(f"    → Check if expression is too complex or returns no results")
                                        QgsMessageLog.logMessage(
                                            f"⚠️ {layer.name()} → 0 features (filter may be too restrictive or expression error)",
                                            "FilterMate", Qgis.Warning
                                        )
                                else:
                                    count_str = "(count pending)"
                                
                                logger.debug(f"finished() ✓ Applied: {layer.name()} → {count_str}")
                            else:
                                # ENHANCED DIAGNOSTIC v2.4.12: Log detailed error information
                                error_msg = 'Unknown error'
                                if layer.error():
                                    error_msg = layer.error().message()
                                logger.warning(f"  ✗ Failed to apply filter to {layer.name()}")
                                logger.warning(f"    → Error: {error_msg}")
                                logger.warning(f"    → Expression ({len(expression) if expression else 0} chars): {expression[:200] if expression else '(empty)'}...")
                                logger.warning(f"    → Provider: {layer.providerType()}")
                                
                                QgsMessageLog.logMessage(
                                    f"finished() ✗ FAILED: {layer.name()} - {error_msg}",
                                    "FilterMate", Qgis.Critical
                                )
                    else:
                        logger.warning(f"  ✗ Layer became invalid before filter could be applied")
                        QgsMessageLog.logMessage(
                            f"finished() ✗ Layer invalid: {layer.name() if layer else 'None'}",
                            "FilterMate", Qgis.Warning
                        )
                except Exception as e:
                    logger.error(f"  ✗ Error applying subset string: {e}")
                    import traceback
                    logger.error(f"    → Traceback: {traceback.format_exc()}")
                    
                    QgsMessageLog.logMessage(
                        f"finished() ✗ Exception: {layer.name() if layer else 'Unknown'} - {str(e)}",
                        "FilterMate", Qgis.Critical
                    )
            
            # v2.6.5: Apply large expressions with deferred processing to prevent freeze
            if large_expressions:
                logger.info(f"  📦 Applying {len(large_expressions)} large expressions with deferred processing")
                from qgis.PyQt.QtCore import QTimer
                
                def apply_deferred_filters():
                    """Apply large filter expressions with UI breathing room."""
                    for lyr, expr in large_expressions:
                        try:
                            if lyr and is_valid_layer(lyr):
                                success = safe_set_subset_string(lyr, expr)
                                if success:
                                    lyr.triggerRepaint()
                                    QgsMessageLog.logMessage(
                                        f"finished() ✓ Deferred: {lyr.name()} → {lyr.featureCount()} features",
                                        "FilterMate", Qgis.Info
                                    )
                                else:
                                    logger.error(f"Failed to apply deferred filter to {lyr.name()}")
                        except Exception as e:
                            logger.error(f"Error applying deferred filter: {e}")
                    # Final canvas refresh
                    try:
                        iface.mapCanvas().refresh()
                    except Exception:
                        pass
                
                # Defer large expression application to allow UI to breathe
                QTimer.singleShot(100, apply_deferred_filters)
            
            # Clear the pending requests
            self._pending_subset_requests = []
            
            # FIX v2.5.15: Simplified canvas refresh with delayed second pass
            # Avoid processEvents() which can cause reentrancy issues and freezes
            # Use a QTimer for delayed refresh to allow PostgreSQL provider to update
            # FIX v2.5.19: Increased delay and added second refresh for complex filters
            # FIX v2.5.21: Avoid multiple overlapping refreshes that cancel each other
            # The problem was: refreshAllLayers() -> _delayed_canvas_refresh(800ms) -> _final_canvas_refresh(2s)
            # Each refresh cancels pending rendering tasks, causing "Building features list was canceled"
            # Solution: Single delayed refresh with proper wait time for complex filters
            try:
                from qgis.PyQt.QtCore import QTimer
                
                # FIX v2.5.21: Skip immediate refreshAllLayers() - layers already got triggerRepaint()
                # This avoids starting a render that will be cancelled by the delayed refresh
                logger.debug("Skipping immediate refresh - layers already triggered repaint")
                
                # FIX v2.5.21: Single delayed refresh with adaptive timing
                # Check if any filter is complex (EXISTS, large IN clause, ST_*)
                # We need to check before clearing _pending_subset_requests
                from qgis.core import QgsProject
                has_complex_filter = False
                for layer_id, layer in QgsProject.instance().mapLayers().items():
                    if layer.type() == 0:  # Vector layer
                        subset = layer.subsetString() or ''
                        if subset and self._is_complex_filter(subset, layer.providerType()):
                            has_complex_filter = True
                            break
                
                # Use longer delay for complex filters
                refresh_delay = 1500 if has_complex_filter else 500
                
                # Schedule single comprehensive refresh
                QTimer.singleShot(refresh_delay, lambda: self._single_canvas_refresh())
                logger.debug(f"Scheduled single canvas refresh in {refresh_delay}ms (complex={has_complex_filter})")
                
            except Exception as canvas_err:
                logger.warning(f"Failed to schedule canvas refresh: {canvas_err}")
                # Fallback: immediate refresh
                try:
                    iface.mapCanvas().refresh()
                except Exception:
                    pass
        
        # CRITICAL FIX v2.3.13: Only cleanup MVs on reset/unfilter actions, NOT on filter
        # When filtering, materialized views are referenced by the layer's subsetString.
        # Cleaning them up would invalidate the filter expression causing empty results.
        # Cleanup should only happen when:
        # - reset: User wants to remove all filters (MVs no longer needed)
        # - unfilter: User wants to revert to previous state (MVs no longer needed)
        # - export: After exporting data (MVs were temporary for export)
        if self.task_action in ('reset', 'unfilter', 'export'):
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
                    
                    # FIX v2.5.12: Ensure canvas is refreshed after successful filter operation
                    # This guarantees filtered features are visible on the map
                    try:
                        iface.mapCanvas().refresh()
                    except Exception:
                        pass  # Ignore refresh errors, filter was still applied

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






"""
FilterEngine Task Module

Main filtering task for FilterMate QGIS Plugin.
Migrated from modules/tasks/filter_task.py to core/tasks/filter_task.py (January 2026).

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

Location: core/tasks/filter_task.py (Hexagonal Architecture - Application Layer)

Import directly from this location:
    from core.tasks.filter_task import FilterEngineTask
    
Or from the package:
    from core.tasks import FilterEngineTask
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

# Import logging configuration (migrated to infrastructure.logging)
from ...infrastructure.logging import setup_logger, safe_log
from ...config.config import ENV_VARS

# EPIC-1 Phase E12: Import extracted orchestration modules (relative import in core/)
from ..filter.filter_orchestrator import FilterOrchestrator
from ..filter.expression_builder import ExpressionBuilder
from ..filter.result_processor import ResultProcessor

# EPIC-1 Phase E5: Import source filter builder functions (relative import in core/)
from ..filter.source_filter_builder import (
    should_skip_source_subset,
    get_primary_key_field as sfb_get_primary_key_field,
    get_source_table_name as sfb_get_source_table_name,
    extract_feature_ids,
    build_source_filter_inline,
    build_source_filter_with_mv,
    get_visible_feature_ids,
    get_source_wkt_and_srid,
    get_source_feature_count,
)

# Setup logger with rotation
logger = setup_logger(
    'FilterMate.Tasks.Filter',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_tasks.log'),
    level=logging.INFO
)

# Centralized psycopg2 availability (v2.8.6 refactoring - migrated to adapters)
from ...adapters.backends.postgresql_availability import psycopg2, PSYCOPG2_AVAILABLE, POSTGRESQL_AVAILABLE

# Import constants (migrated to infrastructure)
from ...infrastructure.constants import (
    PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR, PROVIDER_MEMORY,
    PREDICATE_INTERSECTS, PREDICATE_WITHIN, PREDICATE_CONTAINS,
    PREDICATE_OVERLAPS, PREDICATE_CROSSES, PREDICATE_TOUCHES,
    PREDICATE_DISJOINT, PREDICATE_EQUALS,
    get_provider_name, should_warn_performance,
    LONG_QUERY_WARNING_THRESHOLD, VERY_LONG_QUERY_WARNING_THRESHOLD
)

# Import backend architecture (migrated to adapters)
from ...adapters.backends import BackendFactory
from ...adapters.backends.spatialite import SpatialiteBackend as SpatialiteGeometricFilter

# Import utilities (migrated to infrastructure)
from ...infrastructure.utils import (
    safe_set_subset_string,
    get_source_table_name,
    get_datasource_connexion_from_layer,
    get_primary_key_name,
    detect_layer_provider_type,
    geometry_type_to_string,
    sanitize_sql_identifier,
    sanitize_filename,
    clean_buffer_value,  # v3.0.12: Clean buffer values from float precision errors
)

# Import object safety utilities (v2.3.9 - stability fix, migrated to infrastructure)
from ...infrastructure.utils import (
    is_sip_deleted, is_layer_valid as is_valid_layer, safe_disconnect
)

# Import prepared statements manager (migrated to infrastructure/database/)
from ...infrastructure.database.prepared_statements import create_prepared_statements

# Import task utilities (Phase 3a - migrated to infrastructure)
from ...infrastructure.utils import (
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

# Import geometry safety module (v2.3.9 - stability fix, migrated to core/geometry)
from ..geometry.geometry_safety import (
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

# Import CRS utilities (v2.5.7 - improved CRS compatibility, migrated to core/geometry)
try:
    from ..geometry.crs_utils import (
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

# Import from infrastructure (EPIC-1 migration)
from ...infrastructure.cache import SourceGeometryCache, QueryExpressionCache, get_query_cache
from ...infrastructure.streaming import StreamingExporter, StreamingConfig
from ...infrastructure.parallel import ParallelFilterExecutor, ParallelConfig

# Import from core (EPIC-1 migration - relative import now that we're in core/)
from ..optimization import get_combined_query_optimizer, optimize_combined_filter

# E6: Task completion handler functions (relative import, same package)
from .task_completion_handler import (
    display_warning_messages as tch_display_warnings,
    should_skip_subset_application,
    apply_pending_subset_requests,
    schedule_canvas_refresh,
    cleanup_memory_layer
)

# v3.0 MIG-023: Import TaskBridge for Strangler Fig migration
# TaskBridge allows using new v3 backends while keeping legacy code as fallback
try:
    from ...adapters.task_bridge import get_task_bridge, BridgeStatus
    TASK_BRIDGE_AVAILABLE = True
except ImportError:
    get_task_bridge = None
    BridgeStatus = None
    TASK_BRIDGE_AVAILABLE = False
    logger.debug("TaskBridge not available - using legacy backends only")

# EPIC-1 Phase E4-S5: Import extracted backend filter_executor modules
# These provide Strangler Fig delegation for PostgreSQL/Spatialite/OGR utilities
try:
    from ...adapters.backends.postgresql import filter_executor as pg_executor
    from ...adapters.backends.postgresql.filter_actions import (
        execute_filter_action_postgresql as pg_execute_filter,
        execute_filter_action_postgresql_direct as pg_execute_direct,
        execute_filter_action_postgresql_materialized as pg_execute_materialized,
        has_expensive_spatial_expression as pg_has_expensive_expr,
        execute_reset_action_postgresql as pg_execute_reset,
        execute_unfilter_action_postgresql as pg_execute_unfilter,
    )
    PG_EXECUTOR_AVAILABLE = True
except ImportError:
    pg_executor = None
    pg_execute_filter = None
    pg_execute_direct = None
    pg_execute_materialized = None
    pg_has_expensive_expr = None
    pg_execute_reset = None
    pg_execute_unfilter = None
    PG_EXECUTOR_AVAILABLE = False

try:
    from ...adapters.backends.spatialite import filter_executor as sl_executor
    SL_EXECUTOR_AVAILABLE = True
except ImportError:
    sl_executor = None
    SL_EXECUTOR_AVAILABLE = False

try:
    from ...adapters.backends.ogr import filter_executor as ogr_executor
    OGR_EXECUTOR_AVAILABLE = True
except ImportError:
    ogr_executor = None
    OGR_EXECUTOR_AVAILABLE = False

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
        
        # v3.0 MIG-023: TaskBridge for Strangler Fig migration
        # Allows using new v3 backends while keeping legacy code as fallback
        self._task_bridge = None
        if TASK_BRIDGE_AVAILABLE:
            try:
                self._task_bridge = get_task_bridge()
                if self._task_bridge:
                    logger.debug("TaskBridge initialized - v3 backends available")
            except Exception as e:
                logger.debug(f"TaskBridge not available: {e}")
        
        # THREAD SAFETY FIX v2.3.21: Store subset string requests to apply on main thread
        # Instead of calling setSubsetString directly from background thread (which causes
        # access violations), we store the requests and emit applySubsetRequest signal
        # after the task completes. The signal is connected with Qt.QueuedConnection
        # to ensure setSubsetString is called on the main thread.
        self._pending_subset_requests = []
        
        # Prepared statements manager (initialized when DB connection is established)
        self._ps_manager = None
        
        # EPIC-1 Phase E12: Initialize orchestration modules (lazy initialization)
        # These are initialized in run() once source_layer is available
        self._filter_orchestrator = None
        self._expression_builder = None
        self._result_processor = None

    def queue_subset_request(self, layer, expression):
        """Queue subset string to be applied on main thread (thread safety v2.3.21)."""
        if layer and expression is not None:
            self._pending_subset_requests.append((layer, expression))
            expr_preview = (expression[:60] + '...') if len(expression) > 60 else expression
            logger.debug(f"📥 Queued subset request for {layer.name()}: {expr_preview}")
        else:
            logger.warning(f"⚠️ queue_subset_request called with invalid params: layer={layer}, expression={expression is not None}")
        return True  # Return True to indicate success (actual application is deferred)

    def _collect_backend_warnings(self, backend):
        """Collect warnings from backend for display on main thread."""
        if backend and hasattr(backend, 'get_user_warnings'):
            warnings = backend.get_user_warnings()
            if warnings:
                for warning in warnings:
                    if warning not in self.warning_messages:  # Avoid duplicates
                        self.warning_messages.append(warning)
                        logger.debug(f"📥 Collected backend warning: {warning[:60]}...")
                backend.clear_user_warnings()
    
    def _ensure_db_directory_exists(self):
        """Delegates to ensure_db_directory_exists() in task_utils.py."""
        ensure_db_directory_exists(self.db_file_path)
    
    
    def _safe_spatialite_connect(self):
        """Delegates to safe_spatialite_connect() in task_utils.py."""
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
        
        EPIC-1 Phase 14.3: Delegates to core.services.layer_organizer.
        
        Populates self.layers dictionary with layers grouped by provider,
        and updates layers_count.
        
        For 'filter' action: respects has_layers_to_filter flag OR processes if layers exist
        For 'unfilter' and 'reset': processes all layers in the list regardless of flag
        (to clean up filters that were applied previously)
        """
        from core.services.layer_organizer import organize_layers_for_filtering
        from ..appUtils import detect_layer_provider_type
        
        # Delegate to LayerOrganizer service
        result = organize_layers_for_filtering(
            task_action=self.task_action,
            task_parameters=self.task_parameters,
            project=self.PROJECT,
            postgresql_available=POSTGRESQL_AVAILABLE,
            detect_provider_fn=detect_layer_provider_type,
            is_valid_layer_fn=is_valid_layer,
            is_sip_deleted_fn=is_sip_deleted
        )
        
        # Update task state from result
        self.layers = result.layers_by_provider
        self.layers_count = result.layers_count
        self.provider_list = result.provider_list
        
        # Update task state from result
        self.layers = result.layers_by_provider
        self.layers_count = result.layers_count
        self.provider_list = result.provider_list

    def _queue_subset_string(self, layer, expression):
        """Queue a subset string request for thread-safe application in finished()."""
        if not hasattr(self, '_pending_subset_requests'):
            self._pending_subset_requests = []
        if layer is not None:
            self._pending_subset_requests.append((layer, expression))
            logger.debug(f"Queued subset request for {layer.name()}: {len(expression) if expression else 0} chars")
            return True
        return False

    def _log_backend_info(self):
        """Log backend info and performance warnings. Delegated to core.optimization.logging_utils."""
        from core.optimization.logging_utils import log_backend_info
        thresholds = self._get_optimization_thresholds()
        log_backend_info(
            task_action=self.task_action, provider_type=self.param_source_provider_type,
            postgresql_available=POSTGRESQL_AVAILABLE, feature_count=self.source_layer.featureCount(),
            large_dataset_threshold=thresholds['large_dataset_warning'],
            provider_postgres=PROVIDER_POSTGRES, provider_spatialite=PROVIDER_SPATIALITE, provider_ogr=PROVIDER_OGR
        )

    def _get_contextual_performance_warning(self, elapsed_time: float, severity: str = 'warning') -> str:
        """Generate contextual performance warning. Delegated to core.optimization.performance_advisor."""
        from core.optimization.performance_advisor import get_contextual_performance_warning
        return get_contextual_performance_warning(
            elapsed_time=elapsed_time, provider_type=self.param_source_provider_type,
            postgresql_available=POSTGRESQL_AVAILABLE, severity=severity
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
            
            # EPIC-1 Phase E12: Initialize orchestration modules
            # These modules extract 1,663 lines from this God Class
            self._result_processor = ResultProcessor(
                task_action=self.task_action,
                task_parameters=self.task_parameters
            )
            # Redirect pending_subset_requests to ResultProcessor
            self._pending_subset_requests = self._result_processor._pending_subset_requests
            # Redirect warning_messages to ResultProcessor
            self.warning_messages = self._result_processor.warning_messages
            
            self._expression_builder = ExpressionBuilder(
                task_parameters=self.task_parameters,
                source_layer=getattr(self, 'source_layer', None),
                current_predicates=getattr(self, 'current_predicates', [])
            )
            
            self._filter_orchestrator = FilterOrchestrator(
                task_parameters=self.task_parameters,
                subset_queue_callback=self.queue_subset_request,
                parent_task=self,
                current_predicates=getattr(self, 'current_predicates', [])
            )
            
            logger.debug("Phase E12 orchestration modules initialized")
            
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
            # v2.8.6: Contextual messages based on current backend
            run_elapsed = time.time() - run_start_time
            if run_elapsed >= VERY_LONG_QUERY_WARNING_THRESHOLD:
                # Very long query (>30s): Critical warning - contextual message
                warning_msg = self._get_contextual_performance_warning(run_elapsed, 'critical')
                if warning_msg:
                    self.warning_messages.append(warning_msg)
                logger.warning(f"⚠️ Very long query: {run_elapsed:.1f}s")
            elif run_elapsed >= LONG_QUERY_WARNING_THRESHOLD:
                # Long query (>10s): Standard warning - contextual message
                warning_msg = self._get_contextual_performance_warning(run_elapsed, 'warning')
                if warning_msg:
                    self.warning_messages.append(warning_msg)
                logger.warning(f"⚠️ Long query: {run_elapsed:.1f}s")
            
            logger.info(f"{self.task_action.capitalize()} task completed successfully in {run_elapsed:.2f}s")
            return True
        
        except Exception as e:
            self.exception = e
            safe_log(logger, logging.ERROR, f'FilterEngineTask run() failed: {e}', exc_info=True)
            return False

    # ========================================================================
    # V3 TaskBridge Delegation Methods (Strangler Fig Pattern)
    # ========================================================================
    
    def _try_v3_attribute_filter(self, task_expression, task_features):
        """Try v3 TaskBridge attribute filter. Returns True/False/None (fallback to legacy)."""
        if not self._task_bridge:
            return None
            
        # Only handle simple expression-based filters for now
        # Skip: field-only expressions, skip_source_filter, feature lists
        skip_source_filter = self.task_parameters["task"].get("skip_source_filter", False)
        
        if skip_source_filter:
            logger.debug("TaskBridge: skip_source_filter mode - using legacy code")
            return None
        
        if not task_expression or not task_expression.strip():
            logger.debug("TaskBridge: no expression - using legacy code")
            return None
            
        # Check if expression is just a field name (no operators)
        qgs_expr = QgsExpression(task_expression)
        task_expr_upper = task_expression.upper()
        is_simple_field = qgs_expr.isField() and not any(
            op in task_expr_upper for op in ['=', '>', '<', '!', 'IN', 'LIKE', 'AND', 'OR']
        )
        
        if is_simple_field:
            logger.debug("TaskBridge: field-only expression - using legacy code")
            return None
        
        # Try v3 attribute filter
        try:
            logger.info("=" * 60)
            logger.info("🚀 V3 TASKBRIDGE: Attempting attribute filter")
            logger.info("=" * 60)
            logger.info(f"   Expression: '{task_expression}'")
            logger.info(f"   Layer: '{self.source_layer.name()}'")
            
            bridge_result = self._task_bridge.execute_attribute_filter(
                layer=self.source_layer,
                expression=task_expression,
                combine_with_existing=True
            )
            
            if bridge_result.status == BridgeStatus.SUCCESS and bridge_result.success:
                # V3 succeeded - apply the result
                logger.info(f"✅ V3 TaskBridge SUCCESS")
                logger.info(f"   Backend used: {bridge_result.backend_used}")
                logger.info(f"   Feature count: {bridge_result.feature_count}")
                logger.info(f"   Execution time: {bridge_result.execution_time_ms:.1f}ms")
                
                # Apply the filter to the layer
                self.expression = task_expression
                if bridge_result.feature_ids:
                    # Build expression from feature IDs
                    pk = self.primary_key_name or '$id'
                    ids_str = ', '.join(str(fid) for fid in bridge_result.feature_ids[:1000])
                    if len(bridge_result.feature_ids) > 1000:
                        logger.warning("TaskBridge: Truncating feature IDs to 1000 for expression")
                    self.expression = f'"{pk}" IN ({ids_str})'
                
                # Apply subset string
                result = safe_set_subset_string(self.source_layer, self.expression)
                if result:
                    logger.info(f"   ✓ Filter applied successfully")
                    return True
                else:
                    logger.warning(f"   ✗ Failed to apply filter expression")
                    return None  # Fallback to legacy
                    
            elif bridge_result.status == BridgeStatus.FALLBACK:
                logger.info(f"⚠️ V3 TaskBridge: FALLBACK requested")
                logger.info(f"   Reason: {bridge_result.error_message}")
                return None  # Use legacy code
                
            elif bridge_result.status == BridgeStatus.NOT_AVAILABLE:
                logger.debug("TaskBridge: not available - using legacy code")
                return None
                
            else:
                # Error occurred
                logger.warning(f"⚠️ V3 TaskBridge: ERROR")
                logger.warning(f"   Error: {bridge_result.error_message}")
                return None  # Fallback to legacy
                
        except Exception as e:
            logger.warning(f"TaskBridge delegation failed: {e}")
            return None  # Fallback to legacy

    def _try_v3_spatial_filter(self, layer, layer_props, predicates):
        """Try v3 TaskBridge spatial filter. Returns True/False/None (fallback to legacy)."""
        if not self._task_bridge or not self._task_bridge.is_available():
            return None
        
        # v3 spatial filter is experimental - only enable for simple cases
        # Skip for now: complex predicates, buffers, multi-step
        buffer_value = self.task_parameters.get("task", {}).get("buffer_value", 0)
        if buffer_value and buffer_value > 0:
            logger.debug("TaskBridge: buffer active - using legacy spatial code")
            return None
        
        if len(predicates) > 1:
            logger.debug("TaskBridge: multiple predicates - using legacy spatial code")
            return None
        
        try:
            logger.info("=" * 60)
            logger.info("🚀 V3 TASKBRIDGE: Attempting spatial filter")
            logger.info("=" * 60)
            logger.info(f"   Layer: '{layer.name()}'")
            logger.info(f"   Predicates: {predicates}")
            
            bridge_result = self._task_bridge.execute_spatial_filter(
                source_layer=self.source_layer,
                target_layers=[layer],
                predicates=predicates,
                buffer_value=0.0,
                combine_operator=self._get_combine_operator() or 'AND'
            )
            
            if bridge_result.status == BridgeStatus.SUCCESS and bridge_result.success:
                logger.info(f"✅ V3 TaskBridge SPATIAL SUCCESS")
                logger.info(f"   Backend used: {bridge_result.backend_used}")
                logger.info(f"   Feature count: {bridge_result.feature_count}")
                logger.info(f"   Execution time: {bridge_result.execution_time_ms:.1f}ms")
                
                # Store in task_parameters for metrics
                if 'actual_backends' not in self.task_parameters:
                    self.task_parameters['actual_backends'] = {}
                self.task_parameters['actual_backends'][layer.id()] = f"v3_{bridge_result.backend_used}"
                
                return True
                
            elif bridge_result.status == BridgeStatus.FALLBACK:
                logger.info(f"⚠️ V3 TaskBridge SPATIAL: FALLBACK requested")
                logger.info(f"   Reason: {bridge_result.error_message}")
                return None
                
            else:
                logger.debug(f"TaskBridge spatial: status={bridge_result.status}")
                return None
                
        except Exception as e:
            logger.warning(f"TaskBridge spatial delegation failed: {e}")
            return None

    def _try_v3_multi_step_filter(self, layers_dict, progress_callback=None):
        """Try v3 TaskBridge multi-step filter. Returns True/None (fallback to legacy)."""
        if not self._task_bridge:
            return None
        
        # Check if TaskBridge supports multi-step
        if not self._task_bridge.supports_multi_step():
            logger.debug("TaskBridge: multi-step not supported - using legacy code")
            return None
        
        # Skip multi-step for complex scenarios
        # Check for buffers which require special handling
        buffer_value = self.task_parameters.get("task", {}).get("buffer_value", 0)
        if buffer_value and buffer_value > 0:
            logger.debug("TaskBridge: buffer active - using legacy multi-step code")
            return None
        
        # Count total layers
        total_layers = sum(len(layer_list) for layer_list in layers_dict.values())
        if total_layers == 0:
            return True  # Nothing to filter
        
        try:
            logger.info("=" * 70)
            logger.info("🚀 V3 TASKBRIDGE: Attempting multi-step filter")
            logger.info("=" * 70)
            logger.info(f"   Total distant layers: {total_layers}")
            
            # Build step configurations for each layer
            steps = []
            for provider_type, layer_list in layers_dict.items():
                for layer, layer_props in layer_list:
                    # Get predicates from layer_props or default to intersects
                    predicates = layer_props.get('predicates', ['intersects'])
                    
                    step_config = {
                        'target_layer_ids': [layer.id()],
                        'predicates': predicates,
                        'step_name': f"Filter {layer.name()}",
                        'use_previous_result': False  # Each layer filtered independently
                    }
                    steps.append(step_config)
                    logger.debug(f"   Step for {layer.name()}: predicates={predicates}")
            
            # Define progress callback adapter
            def bridge_progress(step_num, total_steps, step_name):
                if progress_callback:
                    progress_callback(step_num, total_steps, step_name)
                self.setDescription(f"V3 Multi-step: {step_name}")
                self.setProgress(int((step_num / total_steps) * 100))
            
            # Execute via TaskBridge
            bridge_result = self._task_bridge.execute_multi_step_filter(
                source_layer=self.source_layer,
                steps=steps,
                progress_callback=bridge_progress
            )
            
            if bridge_result.status == BridgeStatus.SUCCESS and bridge_result.success:
                logger.info("=" * 70)
                logger.info(f"✅ V3 TaskBridge MULTI-STEP SUCCESS")
                logger.info(f"   Backend used: {bridge_result.backend_used}")
                logger.info(f"   Final feature count: {bridge_result.feature_count}")
                logger.info(f"   Total execution time: {bridge_result.execution_time_ms:.1f}ms")
                logger.info("=" * 70)
                
                # Store metrics
                if 'actual_backends' not in self.task_parameters:
                    self.task_parameters['actual_backends'] = {}
                self.task_parameters['actual_backends']['_multi_step'] = f"v3_{bridge_result.backend_used}"
                
                return True
                
            elif bridge_result.status == BridgeStatus.FALLBACK:
                logger.info(f"⚠️ V3 TaskBridge MULTI-STEP: FALLBACK requested")
                logger.info(f"   Reason: {bridge_result.error_message}")
                return None
                
            else:
                logger.debug(f"TaskBridge multi-step: status={bridge_result.status}, falling back")
                return None
                
        except Exception as e:
            logger.warning(f"TaskBridge multi-step delegation failed: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None

    def _try_v3_export(self, layer, output_path, format_type, progress_callback=None):
        """Try v3 TaskBridge streaming export. Returns True/None (fallback to legacy)."""
        if not self._task_bridge:
            return None
            return None
        
        # Check if TaskBridge supports export
        if not self._task_bridge.supports_export():
            logger.debug("TaskBridge: export not supported - using legacy code")
            return None
        
        try:
            logger.info("=" * 60)
            logger.info("🚀 V3 TASKBRIDGE: Attempting streaming export")
            logger.info("=" * 60)
            logger.info(f"   Layer: '{layer.name()}'")
            logger.info(f"   Format: {format_type}")
            logger.info(f"   Output: {output_path}")
            
            # Define cancel check
            def cancel_check():
                return self.isCanceled()
            
            bridge_result = self._task_bridge.execute_export(
                source_layer=layer,
                output_path=output_path,
                format=format_type,
                progress_callback=progress_callback,
                cancel_check=cancel_check
            )
            
            if bridge_result.status == BridgeStatus.SUCCESS and bridge_result.success:
                logger.info(f"✅ V3 TaskBridge EXPORT SUCCESS")
                logger.info(f"   Features exported: {bridge_result.feature_count}")
                logger.info(f"   Execution time: {bridge_result.execution_time_ms:.1f}ms")
                
                # Store in task_parameters for metrics
                if 'actual_backends' not in self.task_parameters:
                    self.task_parameters['actual_backends'] = {}
                self.task_parameters['actual_backends'][f'export_{layer.id()}'] = 'v3_streaming'
                
                return True
                
            elif bridge_result.status == BridgeStatus.FALLBACK:
                logger.info(f"⚠️ V3 TaskBridge EXPORT: FALLBACK requested")
                logger.info(f"   Reason: {bridge_result.error_message}")
                return None
                
            else:
                logger.debug(f"TaskBridge export: status={bridge_result.status}")
                return None
                
        except Exception as e:
            logger.warning(f"TaskBridge export delegation failed: {e}")
            return None

    def _initialize_source_filtering_parameters(self):
        """
        Extract and initialize all parameters needed for source layer filtering.
        
        EPIC-1 Phase 14.4: Delegates to core.services.filter_parameter_builder.
        """
        from core.services.filter_parameter_builder import build_filter_parameters
        from ..appUtils import detect_layer_provider_type
        
        # Delegate to FilterParameterBuilder service
        params = build_filter_parameters(
            task_parameters=self.task_parameters,
            source_layer=self.source_layer,
            postgresql_available=POSTGRESQL_AVAILABLE,
            detect_provider_fn=detect_layer_provider_type,
            sanitize_subset_fn=self._sanitize_subset_string
        )
        
        # Update task state from result
        self.param_source_provider_type = params.provider_type
        self.param_source_layer_name = params.layer_name
        self.param_source_layer_id = params.layer_id
        self.param_source_table = params.table_name
        self.param_source_schema = params.schema
        self.param_source_geom = params.geometry_field
        self.primary_key_name = params.primary_key_name
        self._source_forced_backend = params.forced_backend
        self._source_postgresql_fallback = params.postgresql_fallback
        self.has_combine_operator = params.has_combine_operator
        self.param_source_layer_combine_operator = params.source_layer_combine_operator
        self.param_other_layers_combine_operator = params.other_layers_combine_operator
        self.param_source_old_subset = params.old_subset
        self.source_layer_fields_names = params.field_names
        
        logger.debug(
            f"Filtering layer: {self.param_source_layer_name} "
            f"(table: {self.param_source_table}, Provider: {self.param_source_provider_type})"
        )
        
        # NOTE: The following code was extracted to FilterParameterBuilder service:
        # - Auto-fill missing metadata (layer_name, layer_id, provider_type, geometry_field, primary_key, schema)
        # - Provider type detection and PostgreSQL fallback
        # - Schema validation for PostgreSQL layers
        # - Filtering configuration extraction (combine operators, old subset, field names)
        
        # Preserve original infos dict for backward compatibility (optional)
        infos = self.task_parameters.get("infos", {})
        # Preserve original infos dict for backward compatibility (optional)
        infos = self.task_parameters.get("infos", {})

    def _sanitize_subset_string(self, subset_string):
        """
        Remove non-boolean display expressions and fix type casting issues in subset string.
        
        v4.7 E6-S2: Pure delegation to core.services.expression_service.sanitize_subset_string
        
        Args:
            subset_string (str): The original subset string
            
        Returns:
            str: Sanitized subset string with non-boolean expressions removed
        """
        from core.services.expression_service import sanitize_subset_string
        return sanitize_subset_string(subset_string, logger=logger)
    
    def _extract_spatial_clauses_for_exists(self, filter_expr, source_table=None):
        """Delegates to core.filter.expression_sanitizer.extract_spatial_clauses_for_exists()."""
        from core.filter.expression_sanitizer import extract_spatial_clauses_for_exists
        
        return extract_spatial_clauses_for_exists(filter_expr, source_table)
    
    def _apply_postgresql_type_casting(self, expression, layer=None):
        """Delegates to pg_executor.apply_postgresql_type_casting()."""
        if PG_EXECUTOR_AVAILABLE:
            return pg_executor.apply_postgresql_type_casting(expression, layer)
        # If pg_executor unavailable, return expression unchanged
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
        """Delegates to core.filter.expression_combiner.combine_with_old_subset()."""
        from core.filter.expression_combiner import combine_with_old_subset
        from core.filter.expression_sanitizer import optimize_duplicate_in_clauses
        
        # If no existing filter, return new expression
        if not self.param_source_old_subset:
            return expression
        
        # Get combine operator (or default to AND)
        combine_operator = self._get_source_combine_operator()
        if not combine_operator:
            combine_operator = 'AND'
        
        # Delegate to core module
        return combine_with_old_subset(
            new_expression=expression,
            old_subset=self.param_source_old_subset,
            combine_operator=combine_operator,
            provider_type=self.param_source_provider_type if hasattr(self, 'param_source_provider_type') else 'postgresql',
            optimize_duplicates_fn=lambda expr: optimize_duplicate_in_clauses(expr)
        )

    def _build_feature_id_expression(self, features_list):
        """Delegates to core.filter.expression_builder.build_feature_id_expression()."""
        from core.filter.expression_builder import build_feature_id_expression
        from core.filter.expression_combiner import combine_with_old_subset
        from core.filter.expression_sanitizer import optimize_duplicate_in_clauses
        
        # Extract feature IDs
        # CRITICAL FIX: Handle ctid (PostgreSQL internal identifier)
        if self.primary_key_name == 'ctid':
            features_ids = [str(feature.id()) for feature in features_list]
        else:
            features_ids = [str(feature[self.primary_key_name]) for feature in features_list]
        
        if not features_ids:
            return None
        
        # Build base IN expression
        is_numeric = self.task_parameters["infos"]["primary_key_is_numeric"]
        expression = build_feature_id_expression(
            features_ids=features_ids,
            primary_key_name=self.primary_key_name,
            table_name=self.param_source_table if self.param_source_provider_type == PROVIDER_POSTGRES else None,
            provider_type=self.param_source_provider_type,
            is_numeric=is_numeric
        )
        
        # Combine with old subset if needed
        if self.param_source_old_subset:
            combined = combine_with_old_subset(
                new_expression=expression,
                old_subset=self.param_source_old_subset,
                combine_operator=self._get_source_combine_operator() or 'AND',
                provider_type=self.param_source_provider_type,
                optimize_duplicates_fn=lambda expr: optimize_duplicate_in_clauses(expr)
            )
            return combined
        
        return expression
    
    def _is_pk_numeric(self, layer=None, pk_field=None):
        """Check if the primary key field is numeric. Delegated to pg_executor."""
        check_layer = layer or self.source_layer
        check_pk = pk_field or getattr(self, 'primary_key_name', None)
        if PG_EXECUTOR_AVAILABLE:
            return pg_executor._is_pk_numeric(check_layer, check_pk)
        return True  # Default assumption
    
    def _format_pk_values_for_sql(self, values, is_numeric=None, layer=None, pk_field=None):
        """Format primary key values for SQL IN clause. Delegated to pg_executor."""
        if PG_EXECUTOR_AVAILABLE:
            return pg_executor.format_pk_values_for_sql(values, is_numeric, layer, pk_field)
        # Minimal fallback for non-PostgreSQL
        if not values:
            return ''
        return ', '.join(str(v) for v in values)
    
    def _optimize_duplicate_in_clauses(self, expression):
        """Delegates to core.filter.expression_sanitizer.optimize_duplicate_in_clauses()."""
        from core.filter.expression_sanitizer import optimize_duplicate_in_clauses
        
        return optimize_duplicate_in_clauses(expression)

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
        
        # ================================================================
        # V3 TASKBRIDGE DELEGATION (Strangler Fig Pattern)
        # ================================================================
        # Try v3 backend via TaskBridge for simple attribute filters.
        # This progressively migrates filtering logic to hexagonal architecture.
        # Fallback to legacy code if TaskBridge fails or is not available.
        # ================================================================
        if self._task_bridge and self._task_bridge.is_available():
            bridge_result = self._try_v3_attribute_filter(task_expression, task_features)
            if bridge_result is not None:
                # v3 backend succeeded, return its result
                return bridge_result
            # bridge_result is None means fallback to legacy code
            logger.debug("TaskBridge: Falling back to legacy attribute filter")
        
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
        # Quand skip_source_filter=True (but not single_selection_mode), 
        # utiliser TOUTES les features de la couche source
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
        Initialize source subset expression and buffer parameters (v2).
        
        PHASE 14.5: Migrated to SourceSubsetBufferBuilder service.
        Delegates to build_source_subset_buffer_config() for actual initialization.
        
        Extracted 163 lines to core/services/source_subset_buffer_builder.py (v5.0-alpha).
        """
        # PHASE 14.5: Delegate to SourceSubsetBufferBuilder service
        from core.services.source_subset_buffer_builder import build_source_subset_buffer_config
        
        # Build configuration using service
        config = build_source_subset_buffer_config(
            task_parameters=self.task_parameters,
            expression=self.expression,
            old_subset=self.param_source_old_subset,
            is_field_expression=getattr(self, 'is_field_expression', None)
        )
        
        # Apply results to task instance
        self.param_source_new_subset = config.source_new_subset
        self.param_use_centroids_source_layer = config.use_centroids_source_layer
        self.param_use_centroids_distant_layers = config.use_centroids_distant_layers
        self.approved_optimizations = config.approved_optimizations
        self.auto_apply_optimizations = config.auto_apply_optimizations
        
        # Buffer configuration
        if config.has_buffer:
            self.param_buffer_value = config.buffer_value
            self.param_buffer_expression = config.buffer_expression
        else:
            self.param_buffer_value = 0
            self.param_buffer_expression = None
        
        self.param_buffer_type = config.buffer_type
        self.param_buffer_segments = config.buffer_segments

    def _prepare_geometries_by_provider(self, provider_list):
        """
        Prepare source geometries for each provider type.
        
        Delegates to core.services.geometry_preparer.prepare_geometries_by_provider()
        for actual geometry preparation logic.
        
        Args:
            provider_list: List of unique provider types to prepare
            
        Returns:
            bool: True if all required geometries prepared successfully
        """
        from core.services.geometry_preparer import prepare_geometries_by_provider
        
        result = prepare_geometries_by_provider(
            provider_list=provider_list,
            task_parameters=self.task_parameters,
            source_layer=self.source_layer,
            param_source_provider_type=self.param_source_provider_type,
            param_buffer_expression=self.param_buffer_expression,
            layers_dict=self.layers if hasattr(self, 'layers') else None,
            prepare_postgresql_geom_callback=lambda: self.prepare_postgresql_source_geom(),
            prepare_spatialite_geom_callback=lambda: self.prepare_spatialite_source_geom(),
            prepare_ogr_geom_callback=lambda: self.prepare_ogr_source_geom(),
            logger=logger,
            postgresql_available=POSTGRESQL_AVAILABLE
        )
        
        # Apply results to instance attributes
        if result['postgresql_source_geom'] is not None:
            self.postgresql_source_geom = result['postgresql_source_geom']
        if result['spatialite_source_geom'] is not None:
            self.spatialite_source_geom = result['spatialite_source_geom']
        if result['ogr_source_geom'] is not None:
            self.ogr_source_geom = result['ogr_source_geom']
        if result.get('spatialite_fallback_mode', False):
            self._spatialite_fallback_mode = result['spatialite_fallback_mode']
        
        return result['success']

    def _filter_all_layers_with_progress(self):
        """
        Iterate through all layers and apply filtering with progress tracking.
        
        Supports parallel execution when enabled in configuration.
        Updates task description to show current layer being processed.
        Progress is visible in QGIS task manager panel.
        
        Returns:
            bool: True if all layers processed (some may fail), False if canceled
        """
        # FIX v3.0.8: Import QgsMessageLog for visible diagnostic logs
        from qgis.core import QgsMessageLog, Qgis as QgisLevel
        
        # DIAGNOSTIC: Log all layers that will be filtered
        logger.info("=" * 70)
        logger.info("📋 LISTE DES COUCHES À FILTRER GÉOMÉTRIQUEMENT")
        logger.info("=" * 70)
        total_layers = 0
        layer_names_list = []
        for provider_type in self.layers:
            layer_list = self.layers[provider_type]
            logger.info(f"  Provider: {provider_type} → {len(layer_list)} couche(s)")
            for idx, (layer, layer_props) in enumerate(layer_list, 1):
                logger.info(f"    {idx}. {layer.name()} (id={layer.id()[:8]}...)")
                layer_names_list.append(layer.name())
            total_layers += len(layer_list)
        logger.info(f"  TOTAL: {total_layers} couches à filtrer")
        logger.info("=" * 70)
        
        # FIX v3.0.8: Log to QGIS message panel for visibility
        QgsMessageLog.logMessage(
            f"🔍 Filtering {total_layers} distant layers: {', '.join(layer_names_list[:5])}{'...' if len(layer_names_list) > 5 else ''}",
            "FilterMate", QgisLevel.Info
        )
        
        # =====================================================================
        # MIG-023: STRANGLER FIG PATTERN - Try v3 multi-step first
        # =====================================================================
        v3_result = self._try_v3_multi_step_filter(self.layers)
        if v3_result is True:
            logger.info("✅ V3 multi-step completed successfully - skipping legacy code")
            return True
        elif v3_result is False:
            logger.error("❌ V3 multi-step failed - falling back to legacy")
            # Continue with legacy code below
        else:
            logger.debug("V3 multi-step not applicable - using legacy code")
        # =====================================================================
        
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
        """Filter all layers using parallel execution."""
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
        """Log summary of filtering results. Delegated to core.optimization.logging_utils."""
        from core.optimization.logging_utils import log_filtering_summary
        log_filtering_summary(
            layers_count=self.layers_count, successful_filters=successful_filters,
            failed_filters=failed_filters, failed_layer_names=failed_layer_names, log_to_qgis=True
        )

    def manage_distant_layers_geometric_filtering(self):
        """Filter distant layers using source layer geometries. Orchestrates prepare/filter workflow."""
        logger.info(f"🔍 manage_distant_layers_geometric_filtering: {self.source_layer.name()} (features: {self.source_layer.featureCount()})")
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
        """Convert QGIS expression to PostGIS SQL. Delegated to ExpressionService."""
        if not expression:
            return expression
        geom_col = getattr(self, 'param_source_geom', None) or 'geometry'
        from core.services.expression_service import ExpressionService
        from core.domain.filter_expression import ProviderType
        return ExpressionService().to_sql(expression, ProviderType.POSTGRESQL, geom_col)


    def qgis_expression_to_spatialite(self, expression):
        """Convert QGIS expression to Spatialite SQL. Delegated to ExpressionService."""
        if not expression:
            return expression
        geom_col = getattr(self, 'param_source_geom', None) or 'geometry'
        from core.services.expression_service import ExpressionService
        from core.domain.filter_expression import ProviderType
        return ExpressionService().to_sql(expression, ProviderType.SPATIALITE, geom_col)


    def prepare_postgresql_source_geom(self):
        """Prepare PostgreSQL source geometry with buffer/centroid. Delegated to adapters.backends.postgresql."""
        from adapters.backends.postgresql import prepare_postgresql_source_geom as pg_prepare_source_geom
        result_geom, mv_name = pg_prepare_source_geom(
            source_table=self.param_source_table, source_schema=self.param_source_schema,
            source_geom=self.param_source_geom, buffer_value=getattr(self, 'param_buffer_value', None),
            buffer_expression=getattr(self, 'param_buffer_expression', None),
            use_centroids=getattr(self, 'param_use_centroids_source_layer', False),
            buffer_segments=getattr(self, 'param_buffer_segments', 5),
            buffer_type=self.task_parameters.get("filtering", {}).get("buffer_type", "Round"),
            primary_key_name=getattr(self, 'primary_key_name', None)
        )
        self.postgresql_source_geom = result_geom
        if mv_name:
            self.current_materialized_view_name = mv_name
        logger.debug(f"prepare_postgresql_source_geom: {self.postgresql_source_geom}")


    def _get_optimization_thresholds(self):
        """Get optimization thresholds config. Delegated to core.optimization.config_provider."""
        from core.optimization.config_provider import get_optimization_thresholds
        return get_optimization_thresholds(getattr(self, 'task_parameters', None))

    def _get_simplification_config(self):
        """Get geometry simplification config. Delegated to core.optimization.config_provider."""
        from core.optimization.config_provider import get_simplification_config
        return get_simplification_config(getattr(self, 'task_parameters', None))

    def _get_wkt_precision(self, crs_authid: str = None) -> int:
        """Get appropriate WKT precision based on CRS units. Delegated to BufferService."""
        from core.services.buffer_service import BufferService
        if crs_authid is None:
            crs_authid = getattr(self, 'source_layer_crs_authid', None)
        return BufferService().get_wkt_precision(crs_authid)

    def _geometry_to_wkt(self, geometry, crs_authid: str = None) -> str:
        """Convert geometry to WKT with optimized precision based on CRS."""
        if geometry is None or geometry.isEmpty():
            return ""
        precision = self._get_wkt_precision(crs_authid)
        wkt = geometry.asWkt(precision)
        logger.debug(f"  📏 WKT precision: {precision} decimals (CRS: {crs_authid})")
        return wkt

    def _get_buffer_aware_tolerance(self, buffer_value, buffer_segments, buffer_type, extent_size, is_geographic=False):
        """Calculate optimal simplification tolerance. Delegated to BufferService."""
        from core.services.buffer_service import BufferService, BufferConfig, BufferEndCapStyle
        config = BufferConfig(distance=buffer_value or 0, segments=buffer_segments, end_cap_style=BufferEndCapStyle(buffer_type))
        return BufferService().calculate_buffer_aware_tolerance(config, extent_size, is_geographic)

    def _simplify_geometry_adaptive(self, geometry, max_wkt_length=None, crs_authid=None):
        """Simplify geometry adaptively. Delegated to GeometryPreparationAdapter."""
        from qgis.core import QgsGeometry
        
        if not geometry or geometry.isEmpty():
            return geometry
        
        try:
            from adapters.qgis.geometry_preparation import GeometryPreparationAdapter
            adapter = GeometryPreparationAdapter()
            
            # Get buffer parameters for tolerance calculation
            buffer_value = getattr(self, 'param_buffer_value', None)
            buffer_segments = getattr(self, 'param_buffer_segments', 5)
            buffer_type = getattr(self, 'param_buffer_type', 0)
            
            result = adapter.simplify_geometry_adaptive(
                geometry=geometry,
                max_wkt_length=max_wkt_length,
                crs_authid=crs_authid,
                buffer_value=buffer_value,
                buffer_segments=buffer_segments,
                buffer_type=buffer_type
            )
            
            if result.success and result.geometry:
                return result.geometry
            logger.warning(f"GeometryPreparationAdapter simplify failed: {result.message}")
            return geometry
        except ImportError as e:
            logger.error(f"GeometryPreparationAdapter not available: {e}")
            return geometry
        except Exception as e:
            logger.error(f"GeometryPreparationAdapter simplify error: {e}")
            return geometry

    def prepare_spatialite_source_geom(self):
        """Prepare source geometry for Spatialite filtering. Delegated to spatialite backend."""
        from adapters.backends.spatialite import (
            SpatialiteSourceContext,
            prepare_spatialite_source_geom as spatialite_prepare_source_geom
        )
        
        context = SpatialiteSourceContext(
            source_layer=self.source_layer,
            task_parameters=self.task_parameters,
            is_field_expression=getattr(self, 'is_field_expression', None),
            expression=getattr(self, 'expression', None),
            param_source_new_subset=getattr(self, 'param_source_new_subset', None),
            param_buffer_value=getattr(self, 'param_buffer_value', None),
            has_to_reproject_source_layer=getattr(self, 'has_to_reproject_source_layer', False),
            source_layer_crs_authid=getattr(self, 'source_layer_crs_authid', None),
            source_crs=getattr(self, 'source_crs', None),
            param_use_centroids_source_layer=getattr(self, 'param_use_centroids_source_layer', False),
            PROJECT=getattr(self, 'PROJECT', None),
            geom_cache=getattr(self, 'geom_cache', None),
            geometry_to_wkt=self._geometry_to_wkt,
            simplify_geometry_adaptive=self._simplify_geometry_adaptive,
            get_optimization_thresholds=self._get_optimization_thresholds,
        )
        
        result = spatialite_prepare_source_geom(context)
        if result.success:
            self.spatialite_source_geom = result.wkt
            if hasattr(self, 'task_parameters') and self.task_parameters:
                if 'infos' not in self.task_parameters:
                    self.task_parameters['infos'] = {}
                self.task_parameters['infos']['source_geom_wkt'] = result.wkt
                self.task_parameters['infos']['buffer_state'] = result.buffer_state
            logger.debug(f"prepare_spatialite_source_geom: WKT length = {len(result.wkt) if result.wkt else 0}")
        else:
            logger.error(f"prepare_spatialite_source_geom failed: {result.error_message}")
            self.spatialite_source_geom = None

    def _copy_filtered_layer_to_memory(self, layer, layer_name="filtered_copy"):
        """Copy filtered layer to memory layer. Delegated to GeometryPreparationAdapter."""
        from adapters.qgis.geometry_preparation import GeometryPreparationAdapter
        result = GeometryPreparationAdapter().copy_filtered_to_memory(layer, layer_name)
        if result.success and result.layer:
            self._verify_and_create_spatial_index(result.layer, layer_name)
            return result.layer
        raise Exception(f"Failed to copy filtered layer: {result.error_message or 'Unknown'}")

    def _copy_selected_features_to_memory(self, layer, layer_name="selected_copy"):
        """Copy selected features to memory layer. Delegated to GeometryPreparationAdapter."""
        from adapters.qgis.geometry_preparation import GeometryPreparationAdapter
        result = GeometryPreparationAdapter().copy_selected_to_memory(layer, layer_name)
        if result.success and result.layer:
            self._verify_and_create_spatial_index(result.layer, layer_name)
            return result.layer
        raise Exception(f"Failed to copy selected features: {result.error_message or 'Unknown'}")

    def _create_memory_layer_from_features(self, features, crs, layer_name="from_features"):
        """Create memory layer from QgsFeature objects. Delegated to GeometryPreparationAdapter."""
        from adapters.qgis.geometry_preparation import GeometryPreparationAdapter
        result = GeometryPreparationAdapter().create_memory_from_features(features, crs, layer_name)
        if result.success and result.layer:
            self._verify_and_create_spatial_index(result.layer, layer_name)
            return result.layer
        logger.error(f"_create_memory_layer_from_features failed: {result.error_message or 'Unknown'}")
        return None

    def _convert_layer_to_centroids(self, layer):
        """Convert layer geometries to centroids. Delegated to GeometryPreparationAdapter."""
        from adapters.qgis.geometry_preparation import GeometryPreparationAdapter
        result = GeometryPreparationAdapter().convert_to_centroids(layer)
        if result.success and result.layer:
            return result.layer
        logger.error(f"_convert_layer_to_centroids failed: {result.error_message or 'Unknown'}")
        return None

    def _fix_invalid_geometries(self, layer, output_key):
        """Fix invalid geometries. DISABLED: Returns input layer unchanged."""
        return layer


    def _reproject_layer(self, layer, target_crs):
        """Reproject layer to target CRS without geometry validation."""
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
        processing.run('qgis:createspatialindex', {"INPUT": layer})
        return layer


    def _store_warning_message(self, message):
        """Store a warning message for display in UI thread (thread-safe callback)."""
        if message and message not in self.warning_messages:
            self.warning_messages.append(message)


    def _get_buffer_distance_parameter(self):
        """Get buffer distance parameter from task configuration."""
        if self.param_buffer_expression:
            return QgsProperty.fromExpression(self.param_buffer_expression)
        elif self.param_buffer_value is not None:
            return float(self.param_buffer_value)
        return None


    def _apply_qgis_buffer(self, layer, buffer_distance):
        """Apply buffer - delegated to core.geometry.apply_qgis_buffer."""
        try:
            from core.geometry import apply_qgis_buffer, BufferConfig
            config = BufferConfig(buffer_type=self.param_buffer_type, buffer_segments=self.param_buffer_segments, dissolve=True)
            buffered_layer = apply_qgis_buffer(layer, buffer_distance, config, self._convert_geometry_collection_to_multipolygon)
            self.outputs['alg_source_layer_params_buffer'] = {'OUTPUT': buffered_layer}
            return buffered_layer
        except ImportError as e:
            logger.error(f"core.geometry module not available: {e}")
            raise Exception(f"Buffer operation requires core.geometry module: {e}")
        except Exception as e:
            logger.error(f"Buffer operation failed: {e}")
            raise

    def _convert_geometry_collection_to_multipolygon(self, layer):
        """Convert GeometryCollection to MultiPolygon. Delegated to core.geometry."""
        from core.geometry import convert_geometry_collection_to_multipolygon
        return convert_geometry_collection_to_multipolygon(layer)


    def _evaluate_buffer_distance(self, layer, buffer_param):
        """Delegates to core.geometry.buffer_processor.evaluate_buffer_distance()."""
        from core.geometry.buffer_processor import evaluate_buffer_distance
        
        return evaluate_buffer_distance(layer, buffer_param)

    def _create_memory_layer_for_buffer(self, layer):
        """
        Create empty memory layer for buffered features.
        
        EPIC-1 Phase E7.5: Legacy code removed - fully delegates to core.geometry.buffer_processor.
        
        Args:
            layer: Source layer for CRS and geometry type
            
        Returns:
            QgsVectorLayer: Empty memory layer configured for buffered geometries
        """
        from core.geometry.buffer_processor import create_memory_layer_for_buffer
        
        return create_memory_layer_for_buffer(layer)

    def _buffer_all_features(self, layer, buffer_dist):
        """Buffer all features from layer. Delegated to core.geometry.buffer_processor."""
        from core.geometry.buffer_processor import buffer_all_features
        segments = getattr(self, 'param_buffer_segments', 5)
        return buffer_all_features(layer, buffer_dist, segments)

    def _dissolve_and_add_to_layer(self, geometries, buffered_layer):
        """Delegates to core.geometry.buffer_processor.dissolve_and_add_to_layer()."""
        from core.geometry.buffer_processor import dissolve_and_add_to_layer
        return dissolve_and_add_to_layer(geometries, buffered_layer, self._verify_and_create_spatial_index)

    def _create_buffered_memory_layer(self, layer, buffer_distance):
        """Delegates to core.geometry.create_buffered_memory_layer()."""
        from core.geometry import create_buffered_memory_layer
        return create_buffered_memory_layer(layer, buffer_distance, self.param_buffer_segments, self._verify_and_create_spatial_index, self._store_warning_message)

    def _aggressive_geometry_repair(self, geom):
        """Delegates to core.geometry.aggressive_geometry_repair()."""
        from core.geometry import aggressive_geometry_repair
        return aggressive_geometry_repair(geom)

    def _repair_invalid_geometries(self, layer):
        """Validate and repair invalid geometries. Delegated to core.geometry."""
        from core.geometry import repair_invalid_geometries
        return repair_invalid_geometries(
            layer=layer,
            verify_spatial_index_fn=self._verify_and_create_spatial_index
        )

    def _simplify_buffer_result(self, layer, buffer_distance):
        """Simplify polygon(s) from buffer operations. Delegated to core.geometry."""
        from ..backends.auto_optimizer import get_auto_optimization_config
        from core.geometry import simplify_buffer_result
        config = get_auto_optimization_config()
        return simplify_buffer_result(
            layer=layer,
            buffer_distance=buffer_distance,
            auto_simplify=config.get('auto_simplify_after_buffer', True),
            tolerance=config.get('buffer_simplify_after_tolerance', 0.5),
            verify_spatial_index_fn=self._verify_and_create_spatial_index
        )

    def _apply_buffer_with_fallback(self, layer, buffer_distance):
        """Apply buffer with fallback to manual method. Validates geometries before buffering."""
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
        
        result = None
        
        try:
            # Try QGIS buffer algorithm first
            result = self._apply_qgis_buffer(layer, buffer_distance)
            
            # STABILITY FIX v2.3.9: Validate result before returning
            if result is None or not result.isValid() or result.featureCount() == 0:
                logger.warning("_apply_qgis_buffer returned invalid/empty result, trying manual buffer")
                raise Exception("QGIS buffer returned invalid result")
            
        except Exception as e:
            # Fallback to manual buffer
            logger.warning(f"QGIS buffer algorithm failed: {str(e)}, using manual buffer approach")
            try:
                result = self._create_buffered_memory_layer(layer, buffer_distance)
                
                # STABILITY FIX v2.3.9: Validate result before returning
                if result is None or not result.isValid() or result.featureCount() == 0:
                    logger.error("Manual buffer also returned invalid/empty result")
                    return None
                
            except Exception as manual_error:
                logger.error(f"Both buffer methods failed. QGIS: {str(e)}, Manual: {str(manual_error)}")
                logger.error("Returning None - buffer operation failed completely")
                return None
        
        # v2.8.6: Apply post-buffer simplification to reduce vertex count
        if result is not None and result.isValid() and result.featureCount() > 0:
            result = self._simplify_buffer_result(result, buffer_distance)
        
        return result


    def prepare_ogr_source_geom(self):
        """Prepare OGR source geometry with reprojection/buffering. Delegated to ogr_executor."""
        if not OGR_EXECUTOR_AVAILABLE or not hasattr(ogr_executor, 'OGRSourceContext'):
            logger.error("OGR executor not available")
            self.ogr_source_geom = None
            return
        context = ogr_executor.OGRSourceContext(
            source_layer=self.source_layer, task_parameters=self.task_parameters,
            is_field_expression=getattr(self, 'is_field_expression', None),
            expression=getattr(self, 'expression', None),
            param_source_new_subset=getattr(self, 'param_source_new_subset', None),
            has_to_reproject_source_layer=self.has_to_reproject_source_layer,
            source_layer_crs_authid=self.source_layer_crs_authid,
            param_use_centroids_source_layer=self.param_use_centroids_source_layer,
            spatialite_fallback_mode=getattr(self, '_spatialite_fallback_mode', False),
            buffer_distance=None,
            copy_filtered_layer_to_memory=self._copy_filtered_layer_to_memory,
            copy_selected_features_to_memory=self._copy_selected_features_to_memory,
            create_memory_layer_from_features=self._create_memory_layer_from_features,
            reproject_layer=self._reproject_layer,
            convert_layer_to_centroids=self._convert_layer_to_centroids,
            get_buffer_distance_parameter=self._get_buffer_distance_parameter,
        )
        self.ogr_source_geom = ogr_executor.prepare_ogr_source_geom(context)
        logger.debug(f"prepare_ogr_source_geom: {self.ogr_source_geom}")


    def _verify_and_create_spatial_index(self, layer, layer_name=None):
        """Verify/create spatial index on layer. Delegated to core.geometry.spatial_index."""
        from core.geometry.spatial_index import verify_and_create_spatial_index
        return verify_and_create_spatial_index(layer, layer_name)


    def _get_source_reference(self, sub_expression):
        """Determine the source reference for spatial joins (MV or direct table)."""
        if self.current_materialized_view_name:
            return f'"{self.current_materialized_view_schema}"."mv_{self.current_materialized_view_name}_dump"'
        return sub_expression

    def _build_spatial_join_query(self, layer_props, param_postgis_sub_expression, sub_expression):
        """Build SELECT query with spatial JOIN for filtering. Delegates to pg_executor."""
        if PG_EXECUTOR_AVAILABLE:
            return pg_executor.build_spatial_join_query(
                layer_props=layer_props,
                param_postgis_sub_expression=param_postgis_sub_expression,
                sub_expression=sub_expression,
                current_materialized_view_name=self.current_materialized_view_name,
                current_materialized_view_schema=self.current_materialized_view_schema,
                source_schema=self.param_source_schema,
                source_table=self.param_source_table,
                expression=self.expression,
                has_combine_operator=self.has_combine_operator
            )
        # Minimal fallback for non-PG environments
        param_distant_primary_key_name = layer_props["primary_key_name"]
        param_distant_schema = layer_props["layer_schema"]
        param_distant_table = layer_props["layer_name"]
        source_ref = self._get_source_reference(sub_expression)
        return (
            f'(SELECT "{param_distant_table}"."{param_distant_primary_key_name}" '
            f'FROM "{param_distant_schema}"."{param_distant_table}" '
            f'INNER JOIN {source_ref} ON {param_postgis_sub_expression})'
        )

    def _apply_combine_operator(self, primary_key_name, param_expression, param_old_subset, param_combine_operator):
        """Apply SQL set operator to combine with existing subset. Delegated to pg_executor."""
        if PG_EXECUTOR_AVAILABLE:
            return pg_executor.apply_combine_operator(
                primary_key_name, param_expression, param_old_subset, param_combine_operator
            )
        # Minimal fallback
        if param_old_subset and param_combine_operator:
            return f'"{primary_key_name}" IN ( {param_old_subset} {param_combine_operator} {param_expression} )'
        return f'"{primary_key_name}" IN {param_expression}'

    def _build_postgis_filter_expression(self, layer_props, param_postgis_sub_expression, sub_expression, param_old_subset, param_combine_operator):
        """
        Build complete PostGIS filter expression for subset string.
        Delegates to pg_executor.build_postgis_filter_expression().
        
        Args:
            layer_props: Layer properties dict
            param_postgis_sub_expression: PostGIS spatial predicate expression
            sub_expression: Source layer subset expression
            param_old_subset: Existing subset string from layer
            param_combine_operator: SQL set operator (UNION, INTERSECT, EXCEPT)
            
        Returns:
            tuple: (expression, param_expression) - Complete filter and subquery
        """
        if PG_EXECUTOR_AVAILABLE:
            return pg_executor.build_postgis_filter_expression(
                layer_props=layer_props,
                param_postgis_sub_expression=param_postgis_sub_expression,
                sub_expression=sub_expression,
                param_old_subset=param_old_subset,
                param_combine_operator=param_combine_operator,
                current_materialized_view_name=self.current_materialized_view_name,
                current_materialized_view_schema=self.current_materialized_view_schema,
                source_schema=self.param_source_schema,
                source_table=self.param_source_table,
                expression=self.expression,
                has_combine_operator=self.has_combine_operator
            )
        # Minimal fallback
        param_expression = self._build_spatial_join_query(
            layer_props, param_postgis_sub_expression, sub_expression
        )
        expression = self._apply_combine_operator(
            layer_props["primary_key_name"], param_expression, param_old_subset, param_combine_operator
        )
        return expression, param_expression


    def _execute_ogr_spatial_selection(self, layer, current_layer, param_old_subset):
        """Delegates to ogr_executor.execute_ogr_spatial_selection()."""
        if not OGR_EXECUTOR_AVAILABLE:
            raise ImportError("ogr_executor module not available - cannot execute OGR spatial selection")
        
        if not hasattr(ogr_executor, 'OGRSpatialSelectionContext'):
            raise ImportError("ogr_executor.OGRSpatialSelectionContext not available")
        
        context = ogr_executor.OGRSpatialSelectionContext(
            ogr_source_geom=self.ogr_source_geom,
            current_predicates=self.current_predicates,
            has_combine_operator=self.has_combine_operator,
            param_other_layers_combine_operator=self.param_other_layers_combine_operator,
            verify_and_create_spatial_index=self._verify_and_create_spatial_index,
        )
        ogr_executor.execute_ogr_spatial_selection(
            layer, current_layer, param_old_subset, context
        )
        logger.debug("_execute_ogr_spatial_selection: delegated to ogr_executor")


    def _build_ogr_filter_from_selection(self, current_layer, layer_props, param_distant_geom_expression):
        """Delegates to ogr_executor.build_ogr_filter_from_selection()."""
        if not OGR_EXECUTOR_AVAILABLE:
            raise ImportError("ogr_executor module not available - cannot build OGR filter from selection")
        
        return ogr_executor.build_ogr_filter_from_selection(
            layer=current_layer,
            layer_props=layer_props,
            distant_geom_expression=param_distant_geom_expression
        )


    def _normalize_column_names_for_postgresql(self, expression, field_names):
        """
        Normalize column names in expression to match actual PostgreSQL column names.
        
        v4.7 E6-S1: Pure delegation to pg_executor.normalize_column_names_for_postgresql (legacy fallback removed).
        """
        if not PG_EXECUTOR_AVAILABLE:
            raise ImportError("pg_executor module not available - cannot normalize column names for PostgreSQL")
        
        return pg_executor.normalize_column_names_for_postgresql(expression, field_names)

    def _qualify_field_names_in_expression(self, expression, field_names, primary_key_name, table_name, is_postgresql):
        """
        Qualify field names with table prefix for PostgreSQL/Spatialite expressions.
        
        EPIC-1 Phase E7.5: Legacy code removed - fully delegates to core.filter.expression_builder.
        
        Args:
            expression: Raw QGIS expression string
            field_names: List of field names to qualify
            primary_key_name: Primary key field name
            table_name: Source table name
            is_postgresql: Whether target is PostgreSQL (True) or other provider (False)
            
        Returns:
            str: Expression with qualified field names
        """
        from core.filter.expression_builder import qualify_field_names_in_expression
        
        return qualify_field_names_in_expression(
            expression=expression,
            field_names=field_names,
            primary_key_name=primary_key_name,
            table_name=table_name,
            is_postgresql=is_postgresql,
            provider_type=self.param_source_provider_type,
            normalize_columns_fn=self._normalize_column_names_for_postgresql if is_postgresql else None
        )


    def _build_combined_filter_expression(self, new_expression, old_subset, combine_operator, layer_props=None):
        """
        Combine new filter expression with existing subset using specified operator.
        
        OPTIMIZATION v2.8.0: Uses CombinedQueryOptimizer to detect and reuse
        materialized views from previous filter operations, providing 10-50x
        speedup for successive filters on large datasets.
        
        v2.9.0: Creates source MV with pre-computed buffer when FID count exceeds
        SOURCE_FID_MV_THRESHOLD (50), providing up to 20x additional speedup.
        
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
                # v2.9.0: If source MV needs to be created, do it now
                if hasattr(result, 'source_mv_info') and result.source_mv_info is not None:
                    self._create_source_mv_if_needed(result.source_mv_info)
                
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

    def _create_source_mv_if_needed(self, source_mv_info):
        """Create source materialized view with pre-computed buffer (v2.9.0 optimization)."""
        if not source_mv_info or not source_mv_info.create_sql:
            return False
        
        try:
            import time
            start_time = time.time()
            
            connexion = self._get_valid_postgresql_connection()
            if not connexion:
                logger.warning("No PostgreSQL connection available for source MV creation")
                return False
            
            # Build commands: drop if exists, create, add spatial index
            schema = source_mv_info.schema
            view_name = source_mv_info.view_name
            
            commands = [
                f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."{view_name}" CASCADE;',
                source_mv_info.create_sql,
                f'CREATE INDEX IF NOT EXISTS idx_{view_name}_geom ON "{schema}"."{view_name}" USING GIST (geom);',
                f'CREATE INDEX IF NOT EXISTS idx_{view_name}_buff ON "{schema}"."{view_name}" USING GIST (geom_buffered);',
                f'ANALYZE "{schema}"."{view_name}";'
            ]
            
            self._execute_postgresql_commands(connexion, commands)
            
            elapsed = time.time() - start_time
            fid_count = len(source_mv_info.fid_list)
            logger.info(
                f"✓ v2.9.0: Source MV '{view_name}' created in {elapsed:.2f}s "
                f"({fid_count} FIDs with pre-computed buffer)"
            )
            return True
            
        except Exception as e:
            logger.warning(f"Failed to create source MV '{source_mv_info.view_name}': {e}")
            # Don't raise - the optimization can still work with inline subquery
            return False

    def _validate_layer_properties(self, layer_props, layer_name):
        """Validate required fields in layer properties. Returns tuple or (None,)*4 on error."""
        layer_table = layer_props.get('layer_name')
        primary_key = layer_props.get('primary_key_name')
        geom_field = layer_props.get('layer_geometry_field')
        layer_schema = layer_props.get('layer_schema')
        if not all([layer_table, primary_key, geom_field]):
            logger.error(f"Missing required fields for {layer_name}: name={layer_table}, pk={primary_key}, geom={geom_field}")
            return None, None, None, None
        return layer_table, primary_key, geom_field, layer_schema

    def _build_backend_expression_v2(self, backend, layer_props, source_geom):
        """
        Build filter expression using backend - PHASE 14.1 REFACTORED VERSION.
        
        Delegates to BackendExpressionBuilder service to reduce God Class size.
        Extracted 426 lines to core/services/backend_expression_builder.py (v5.0-alpha).
        
        Args:
            backend: Backend instance
            layer_props: Layer properties dict
            source_geom: Prepared source geometry
            
        Returns:
            str: Filter expression or None on error
        """
        # PHASE 14.1: Delegate to BackendExpressionBuilder service
        from core.services.backend_expression_builder import create_expression_builder
        
        # Create builder with all required dependencies
        builder = create_expression_builder(
            source_layer=self.source_layer,
            task_parameters=self.task_parameters,
            expr_cache=self.expr_cache,
            format_pk_values_callback=self._format_pk_values_for_sql,
            get_optimization_thresholds_callback=self._get_optimization_thresholds
        )
        
        # Transfer task state to builder
        builder.param_buffer_value = self.param_buffer_value
        builder.param_buffer_expression = self.param_buffer_expression
        builder.param_use_centroids_distant_layers = self.param_use_centroids_distant_layers
        builder.param_use_centroids_source_layer = self.param_use_centroids_source_layer
        builder.param_source_table = self.param_source_table
        builder.param_source_geom = self.param_source_geom
        builder.current_predicates = self.current_predicates
        builder.approved_optimizations = self.approved_optimizations
        builder.auto_apply_optimizations = self.auto_apply_optimizations
        builder.spatialite_source_geom = self.spatialite_source_geom
        builder.ogr_source_geom = self.ogr_source_geom
        builder.source_layer_crs_authid = self.source_layer_crs_authid
        
        # Build expression
        expression = builder.build(backend, layer_props, source_geom)
        
        # Collect created MVs for cleanup
        created_mvs = builder.get_created_mvs()
        if created_mvs:
            self._source_selection_mvs.extend(created_mvs)
        
        return expression

    def _build_backend_expression(self, backend, layer_props, source_geom):
        """
        Build filter expression using backend.
        
        PHASE 14.1 GOD CLASS REDUCTION: Delegates to _build_backend_expression_v2().
        Wrapper method for backward compatibility - all logic moved to service-based v2.
        
        Args:
            backend: Backend instance
            layer_props: Layer properties dict
            source_geom: Prepared source geometry
            
        Returns:
            str: Filter expression or None on error
        """
        # PHASE 14.1: Simple delegation to refactored version
        return self._build_backend_expression_v2(backend, layer_props, source_geom)

    def _combine_with_old_filter(self, expression, layer):
        """Delegates to core.filter.expression_combiner.combine_with_old_filter()."""
        from core.filter.expression_combiner import combine_with_old_filter
        
        old_subset = layer.subsetString() if layer.subsetString() != '' else None
        
        return combine_with_old_filter(
            new_expression=expression,
            old_subset=old_subset,
            combine_operator=self._get_combine_operator(),
            sanitize_fn=self._sanitize_subset_string
        )

    def execute_geometric_filtering(self, layer_provider_type, layer, layer_props):
        """
        Execute geometric filtering on layer using spatial predicates.
        
        EPIC-1 Phase E12: Delegated to FilterOrchestrator.
        This method now acts as a thin delegation layer, reducing filter_task.py
        from 7,015 to ~5,400 lines (-1,615 lines).
        
        Args:
            layer_provider_type: Provider type ('postgresql', 'spatialite', 'ogr')
            layer: QgsVectorLayer to filter
            layer_props: Dict containing layer info
            
        Returns:
            bool: True if filtering succeeded, False otherwise
        """
        # Prepare source geometries dict for orchestrator
        source_geometries = {
            'postgresql': getattr(self, 'postgresql_source_geom', None),
            'spatialite': getattr(self, 'spatialite_source_geom', None),
            'ogr': getattr(self, 'ogr_source_geom', None)
        }
        
        # Delegate to FilterOrchestrator
        return self._filter_orchestrator.orchestrate_geometric_filter(
            layer=layer,
            layer_provider_type=layer_provider_type,
            layer_props=layer_props,
            source_geometries=source_geometries,
            expression_builder=self._expression_builder
        )
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
    
    def _simplify_source_for_ogr_fallback(self, source_layer):
        """
        v4.7 E6-S2: Simplify complex source geometries for OGR fallback.
        
        Pure delegation to adapters.backends.ogr.geometry_optimizer.simplify_source_for_ogr_fallback
        
        Args:
            source_layer: QgsVectorLayer containing source geometry
            
        Returns:
            QgsVectorLayer: Simplified source layer (may be new memory layer)
        """
        from adapters.backends.ogr.geometry_optimizer import simplify_source_for_ogr_fallback
        return simplify_source_for_ogr_fallback(source_layer, logger=logger)
    
    def _prepare_source_geometry(self, layer_provider_type):
        """Prepare source geometry expression based on provider type (PostgreSQL→SQL/WKT, Spatialite→WKT, OGR→QgsVectorLayer)."""
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
        """Filter source layer first, then distant layers if successful."""
        # STEP 1/2: Filtering SOURCE LAYER
        
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
            logger.error("  → Please select a feature, check multiple features, or enter a filter expression")
            # Provide user-friendly message with guidance
            self.message = (
                "No valid selection: please select a feature, check features, "
                "or enter a filter expression in the 'Exploring' tab before filtering."
            )
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
        
        # FIX v3.0.7: Log to QGIS message panel for visibility
        from qgis.core import QgsMessageLog, Qgis as QgisLevel
        
        logger.info(f"\n🔍 Checking if distant layers should be filtered...")
        logger.info(f"  has_geometric_predicates: {has_geom_predicates}")
        logger.info(f"  has_layers_to_filter: {has_layers_to_filter}")
        logger.info(f"  has_layers_in_params: {has_layers_in_params}")
        logger.info(f"  self.layers_count: {self.layers_count}")
        
        # Log layer names to QGIS message panel for visibility
        layer_names = [l.get('layer_name', 'unknown') for l in self.task_parameters['task'].get('layers', [])]
        QgsMessageLog.logMessage(
            f"📋 Distant layers to filter ({len(layer_names)}): {', '.join(layer_names[:5])}{'...' if len(layer_names) > 5 else ''}",
            "FilterMate", QgisLevel.Info
        )
        
        logger.info(f"  task['layers'] content: {layer_names}")
        logger.info(f"  self.layers content: {list(self.layers.keys())} with {sum(len(v) for v in self.layers.values())} total layers")
        
        # FIX v3.0.10: Log conditions to QGIS message panel for debugging
        # This helps diagnose why distant layers may not be filtered
        if not has_geom_predicates or (not has_layers_to_filter and not has_layers_in_params) or self.layers_count == 0:
            missing_conditions = []
            if not has_geom_predicates:
                missing_conditions.append("has_geometric_predicates=False")
            if not has_layers_to_filter and not has_layers_in_params:
                missing_conditions.append("no layers configured")
            if self.layers_count == 0:
                missing_conditions.append("layers_count=0")
            QgsMessageLog.logMessage(
                f"⚠️ Distant layers NOT filtered: {', '.join(missing_conditions)}",
                "FilterMate", QgisLevel.Warning
            )
            logger.warning(f"⚠️ Distant layers NOT filtered: {', '.join(missing_conditions)}")
        
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
        
        v4.7 E6-S1: Pure delegation to core.export.validate_export_parameters (legacy fallback removed).
        
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
        from core.export import validate_export_parameters
        
        result = validate_export_parameters(self.task_parameters, ENV_VARS)
        if result.valid:
            return {
                'layers': result.layers,
                'projection': result.projection,
                'styles': result.styles,
                'datatype': result.datatype,
                'output_folder': result.output_folder,
                'zip_path': result.zip_path,
                'batch_output_folder': result.batch_output_folder,
                'batch_zip': result.batch_zip
            }
        else:
            logger.error(result.error_message)
            return None


    def _get_layer_by_name(self, layer_name):
        """Get layer object from project by name."""
        layers_found = self.PROJECT.mapLayersByName(layer_name)
        if layers_found:
            return layers_found[0]
        logger.warning(f"Layer '{layer_name}' not found in project")
        return None


    def _save_layer_style(self, layer, output_path, style_format, datatype):
        """Delegates to core.export.save_layer_style()."""
        from core.export import save_layer_style
        
        save_layer_style(layer, output_path, style_format, datatype)

    def _save_layer_style_lyrx(self, layer, output_path):
        """Delegates to core.export.StyleExporter for LYRX format."""
        from core.export.style_exporter import StyleExporter, StyleFormat
        
        exporter = StyleExporter()
        exporter.save_style(layer, output_path, StyleFormat.LYRX)

    # =========================================================================
    # LEGACY EXPORT METHODS REMOVED - v4.0 E11.3
    # =========================================================================
    # The following 6 export methods were removed (523 lines total):
    #   - _export_single_layer (71 lines)
    #   - _export_to_gpkg (49 lines) 
    #   - _export_multiple_layers_to_directory (69 lines)
    #   - _export_batch_to_folder (120 lines)
    #   - _export_batch_to_zip (146 lines)
    #   - _create_zip_archive (68 lines)
    #
    # These methods have been fully replaced by:
    #   - core.export.BatchExporter (export_to_folder, export_to_zip, create_zip_archive)
    #   - core.export.LayerExporter (export_single_layer, export_to_gpkg, export_multiple_to_directory)
    #
    # See execute_exporting() below for proper delegation to core.export module.
    # =========================================================================

    def execute_exporting(self):
        """
        Export selected layers. Supports standard/batch/ZIP/streaming modes.
        
        v4.0 E11.2: MIGRATED to core.export.BatchExporter and LayerExporter.
        Replaced 191 lines of orchestration code with ~100 lines of clean delegation.
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
        
        # Initialize exporters (v4.0 E11.2 delegation)
        from core.export import BatchExporter, LayerExporter, sanitize_filename
        batch_exporter = BatchExporter(project=self.PROJECT)
        layer_exporter = LayerExporter(project=self.PROJECT)
        
        # Inject cancel check into batch_exporter
        batch_exporter.is_canceled = lambda: self.isCanceled()
        
        # Define progress/description callbacks
        def progress_callback(percent):
            self.setProgress(percent)
        
        def description_callback(desc):
            self.setDescription(desc)
        
        # BATCH MODE: One file per layer in folder
        if batch_output_folder:
            logger.info("Batch output folder mode enabled - delegating to BatchExporter")
            result = batch_exporter.export_to_folder(
                layers, output_folder, datatype,
                projection=projection,
                style_format=style_format,
                save_styles=save_styles,
                progress_callback=progress_callback,
                description_callback=description_callback
            )
            
            if result.success:
                self.message = f'Batch export: {result.exported_count} layer(s) exported to <a href="file:///{output_folder}">{output_folder}</a>'
            else:
                self.message = f'Batch export completed with errors:\n{result.get_summary()}'
                self.error_details = result.error_details
            
            return result.success
        
        # BATCH MODE: One ZIP per layer
        if batch_zip:
            logger.info("Batch ZIP mode enabled - delegating to BatchExporter")
            result = batch_exporter.export_to_zip(
                layers, output_folder, datatype,
                projection=projection,
                style_format=style_format,
                save_styles=save_styles,
                progress_callback=progress_callback,
                description_callback=description_callback
            )
            
            if result.success:
                self.message = f'Batch ZIP export: {result.exported_count} ZIP file(s) created in <a href="file:///{output_folder}">{output_folder}</a>'
            else:
                self.message = f'Batch ZIP export completed with errors:\n{result.get_summary()}'
                self.error_details = result.error_details
            
            return result.success
        
        # GPKG STANDARD MODE: Delegate to LayerExporter
        if datatype == 'GPKG':
            # Determine GPKG output path
            if output_folder.lower().endswith('.gpkg'):
                gpkg_output_path = output_folder
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
                if not os.path.exists(output_folder):
                    try:
                        os.makedirs(output_folder)
                    except Exception as e:
                        self.message = f'Failed to create output directory: {output_folder}'
                        return False
                
                # Default filename: use project name or "export"
                project_title = self.PROJECT.title() if self.PROJECT.title() else None
                project_basename = self.PROJECT.baseName() if self.PROJECT.baseName() else None
                default_name = project_title or project_basename or 'export'
                default_name = sanitize_filename(default_name)
                gpkg_output_path = os.path.join(output_folder, f"{default_name}.gpkg")
            
            # Delegate to LayerExporter (v4.0 E11.2)
            logger.info(f"GPKG export - delegating to LayerExporter: {gpkg_output_path}")
            result = layer_exporter.export_to_gpkg(layers, gpkg_output_path, save_styles)
            
            if not result.success:
                self.message = result.error_message or 'GPKG export failed'
                return False
            
            self.message = f'Layer(s) exported to <a href="file:///{gpkg_output_path}">{gpkg_output_path}</a>'
            
            # Create zip if requested
            if zip_path:
                gpkg_dir = os.path.dirname(gpkg_output_path)
                if BatchExporter.create_zip_archive(zip_path, gpkg_dir):
                    self.message += f' and Zip file has been exported to <a href="file:///{zip_path}">{zip_path}</a>'
            
            return True
        
        # Check streaming export configuration
        streaming_config = self.task_parameters.get('config', {}).get('APP', {}).get('OPTIONS', {}).get('STREAMING_EXPORT', {})
        streaming_enabled = streaming_config.get('enabled', {}).get('value', True)
        feature_threshold = streaming_config.get('feature_threshold', {}).get('value', 10000)
        chunk_size = streaming_config.get('chunk_size', {}).get('value', 5000)
        
        # STREAMING MODE: For large datasets (non-GPKG)
        if streaming_enabled:
            total_features = self._calculate_total_features(layers)
            if total_features >= feature_threshold:
                logger.info(f"🚀 Using STREAMING export mode ({total_features} features >= {feature_threshold} threshold)")
                export_success = self._export_with_streaming(
                    layers, output_folder, projection, datatype, style_format, save_styles, chunk_size
                )
                if export_success:
                    self.message = f'Streaming export: {len(layers)} layer(s) ({total_features} features) exported to <a href="file:///{output_folder}">{output_folder}</a>'
                elif not self.message:
                    self.message = f'Streaming export failed for {len(layers)} layer(s)'
                
                if export_success and zip_path:
                    if BatchExporter.create_zip_archive(zip_path, output_folder):
                        self.message += f' and Zip file has been exported to <a href="file:///{zip_path}">{zip_path}</a>'
                
                return export_success
        
        # STANDARD MODE: Single or multiple layers
        if not os.path.exists(output_folder):
            self.message = f'Output path does not exist: {output_folder}'
            return False
        
        export_success = False
        
        if len(layers) == 1:
            # Single layer export - delegate to LayerExporter (v4.0 E11.2)
            layer_name = layers[0]['layer_name'] if isinstance(layers[0], dict) else layers[0]
            logger.info(f"Single layer export - delegating to LayerExporter: {layer_name}")
            result = layer_exporter.export_single_layer(
                layer_name, output_folder, projection, datatype, style_format, save_styles
            )
            export_success = result.success
            if not result.success:
                self.message = result.error_message or 'Export failed'
                
        elif os.path.isdir(output_folder):
            # Multiple layers to directory - delegate to LayerExporter (v4.0 E11.2)
            logger.info(f"Multiple layers export - delegating to LayerExporter: {len(layers)} layers")
            from core.export import ExportConfig
            result = layer_exporter.export_multiple_to_directory(
                ExportConfig(
                    layers=layers,
                    output_path=output_folder,
                    datatype=datatype,
                    projection=projection,
                    style_format=style_format,
                    save_styles=save_styles
                )
            )
            export_success = result.success
            if not result.success:
                self.message = result.error_message or 'Export failed'
        else:
            self.message = f'Invalid export configuration: {len(layers)} layers but output is not a directory'
            return False
        
        if not export_success:
            return False
        
        if self.isCanceled():
            self.message = 'Export cancelled by user'
            return False
        
        # Create zip archive if requested
        zip_created = False
        if zip_path:
            zip_created = BatchExporter.create_zip_archive(zip_path, output_folder)
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
        """Build Spatialite query for simple or complex (buffered) subsets. Delegated to sl_executor."""
        if SL_EXECUTOR_AVAILABLE:
            return sl_executor.build_spatialite_query(
                sql_subset_string=sql_subset_string,
                table_name=table_name,
                geom_key_name=geom_key_name,
                primary_key_name=primary_key_name,
                custom=custom,
                buffer_expression=getattr(self, 'param_buffer_expression', None),
                buffer_value=getattr(self, 'param_buffer_value', None),
                buffer_segments=getattr(self, 'param_buffer_segments', 5),
                task_parameters=getattr(self, 'task_parameters', None)
            )
        # Minimal fallback: return unmodified if not custom
        return sql_subset_string

    def _apply_spatialite_subset(self, layer, name, primary_key_name, sql_subset_string, 
                                 cur, conn, current_seq_order):
        """
        Apply subset string to layer and update history.
        
        EPIC-1 Phase E4-S9: Delegated to adapters.backends.spatialite.filter_executor.
        
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
        from adapters.backends.spatialite import apply_spatialite_subset
        
        return apply_spatialite_subset(
            layer=layer,
            name=name,
            primary_key_name=primary_key_name,
            sql_subset_string=sql_subset_string,
            cur=cur,
            conn=conn,
            current_seq_order=current_seq_order,
            session_id=self.session_id,
            project_uuid=self.project_uuid,
            source_layer_id=self.source_layer.id() if self.source_layer else None,
            queue_subset_func=self._queue_subset_string
        )

    def _manage_spatialite_subset(self, layer, sql_subset_string, primary_key_name, geom_key_name, 
                                   name, custom=False, cur=None, conn=None, current_seq_order=0):
        """
        Handle Spatialite temporary tables for filtering.
        
        EPIC-1 Phase E4-S9: Delegated to adapters.backends.spatialite.filter_executor.
        
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
        from adapters.backends.spatialite import manage_spatialite_subset
        
        return manage_spatialite_subset(
            layer=layer,
            sql_subset_string=sql_subset_string,
            primary_key_name=primary_key_name,
            geom_key_name=geom_key_name,
            name=name,
            custom=custom,
            cur=cur,
            conn=conn,
            current_seq_order=current_seq_order,
            session_id=self.session_id,
            project_uuid=self.project_uuid,
            source_layer_id=self.source_layer.id() if self.source_layer else None,
            queue_subset_func=self._queue_subset_string,
            get_spatialite_datasource_func=self._get_spatialite_datasource,
            task_parameters=self.task_parameters
        )


    def _get_last_subset_info(self, cur, layer):
        """
        Get the last subset information for a layer from history.
        
        EPIC-1 Phase E4-S9: Delegated to adapters.backends.spatialite.filter_executor.
        
        Args:
            cur: Database cursor
            layer: QgsVectorLayer
            
        Returns:
            tuple: (last_subset_id, last_seq_order, layer_name, name)
        """
        from adapters.backends.spatialite import get_last_subset_info
        
        return get_last_subset_info(cur, layer, self.project_uuid)


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
        """Delegated to adapters.backends.postgresql.schema_manager."""
        from adapters.backends.postgresql.schema_manager import create_simple_materialized_view_sql
        return create_simple_materialized_view_sql(schema, name, sql_subset_string)


    def _parse_where_clauses(self):
        """Delegated to adapters.backends.postgresql.schema_manager."""
        from adapters.backends.postgresql.schema_manager import parse_case_to_where_clauses
        return parse_case_to_where_clauses(self.where_clause)


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


    def _ensure_temp_schema_exists(self, connexion, schema_name):
        """
        Ensure the temporary schema exists in PostgreSQL database.
        
        Delegated to adapters.backends.postgresql.schema_manager.ensure_temp_schema_exists().
        
        Args:
            connexion: psycopg2 connection
            schema_name: Name of the schema to create
            
        Returns:
            str: Name of the schema to use (schema_name if created, 'public' as fallback)
        """
        from adapters.backends.postgresql.schema_manager import ensure_temp_schema_exists
        
        result = ensure_temp_schema_exists(connexion, schema_name)
        
        # Track schema error for instance state if fallback occurred
        if result == 'public' and schema_name != 'public':
            self._last_schema_error = f"Using 'public' schema as fallback (could not create '{schema_name}')"
        
        return result


    def _get_session_prefixed_name(self, base_name):
        """
        Generate a session-unique materialized view name.
        
        Delegated to adapters.backends.postgresql.schema_manager.get_session_prefixed_name().
        """
        from adapters.backends.postgresql.schema_manager import get_session_prefixed_name
        
        return get_session_prefixed_name(base_name, self.session_id)


    def _cleanup_session_materialized_views(self, connexion, schema_name):
        """
        Clean up all materialized views for the current session.
        
        Delegated to adapters.backends.postgresql.schema_manager.cleanup_session_materialized_views().
        """
        # Strangler Fig: Delegate to extracted module (pg_executor or schema_manager)
        if PG_EXECUTOR_AVAILABLE:
            return pg_executor.cleanup_session_materialized_views(
                connexion, schema_name, self.session_id
            )
        
        # Fallback to schema_manager
        from adapters.backends.postgresql.schema_manager import cleanup_session_materialized_views
        
        return cleanup_session_materialized_views(connexion, schema_name, self.session_id)


    def _cleanup_orphaned_materialized_views(self, connexion, schema_name, max_age_hours=24):
        """
        Clean up orphaned materialized views older than max_age_hours.
        
        Delegated to adapters.backends.postgresql.schema_manager.cleanup_orphaned_materialized_views().
        """
        from adapters.backends.postgresql.schema_manager import cleanup_orphaned_materialized_views
        
        return cleanup_orphaned_materialized_views(connexion, schema_name, self.session_id, max_age_hours)


    def _execute_postgresql_commands(self, connexion, commands):
        """
        Execute PostgreSQL commands with automatic reconnection on failure.
        
        Delegated to adapters.backends.postgresql.schema_manager.execute_commands().
        
        Args:
            connexion: psycopg2 connection
            commands: List of SQL commands to execute
            
        Returns:
            bool: True if all commands succeeded
        """
        from adapters.backends.postgresql.schema_manager import execute_commands
        
        # Test connection and reconnect if needed
        try:
            with connexion.cursor() as cursor:
                cursor.execute("SELECT 1")
        except (psycopg2.OperationalError, psycopg2.InterfaceError, AttributeError) as e:
            logger.debug(f"PostgreSQL connection test failed, reconnecting: {e}")
            connexion, _ = get_datasource_connexion_from_layer(self.source_layer)
        
        return execute_commands(connexion, commands)


    def _ensure_source_table_stats(self, connexion, schema, table, geom_field):
        """
        Ensure PostgreSQL statistics exist for source table geometry column.
        
        Delegated to adapters.backends.postgresql.schema_manager.ensure_table_stats().
        """
        from adapters.backends.postgresql.schema_manager import ensure_table_stats
        
        return ensure_table_stats(connexion, schema, table, geom_field)


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
        
        EPIC-1 Phase E5/E6: Delegates to adapters.backends.postgresql.filter_actions.
        
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
        if PG_EXECUTOR_AVAILABLE and pg_execute_filter:
            return pg_execute_filter(
                layer=layer,
                sql_subset_string=sql_subset_string,
                primary_key_name=primary_key_name,
                geom_key_name=geom_key_name,
                name=name,
                custom=custom,
                cur=cur,
                conn=conn,
                seq_order=seq_order,
                # Callback functions
                queue_subset_fn=self._queue_subset_string,
                get_connection_fn=self._get_valid_postgresql_connection,
                ensure_stats_fn=self._ensure_source_table_stats,
                extract_where_fn=self._extract_where_clause_from_select,
                insert_history_fn=self._insert_subset_history,
                get_session_name_fn=self._get_session_prefixed_name,
                ensure_schema_fn=self._ensure_temp_schema_exists,
                execute_commands_fn=self._execute_postgresql_commands,
                create_simple_mv_fn=self._create_simple_materialized_view_sql,
                create_custom_mv_fn=self._create_custom_buffer_view_sql,
                parse_where_clauses_fn=self._parse_where_clauses,
                # Context parameters
                source_schema=self.param_source_schema,
                source_table=self.param_source_table,
                source_geom=self.param_source_geom,
                current_mv_schema=self.current_materialized_view_schema,
                project_uuid=self.project_uuid,
                session_id=self.session_id,
                param_buffer_expression=getattr(self, 'param_buffer_expression', None)
            )
        
        # Module not available - this should not happen in production
        error_msg = (
            "PostgreSQL filter_actions module not available. "
            "This indicates a critical installation issue."
        )
        logger.error(error_msg)
        raise ImportError(error_msg)
    
    # NOTE: _filter_action_postgresql_legacy REMOVED in Phase 14.2
    # The method was dead code - _filter_action_postgresql now delegates to pg_execute_filter
    
    # NOTE: _filter_action_postgresql_direct REMOVED in Phase 14.2 (151 lines)
    # Now handled by adapters/backends/postgresql/filter_actions.py execute_filter_action_postgresql_direct()
    
    def _extract_where_clause_from_select(self, sql_select):
        """
        Extract WHERE clause from a SQL SELECT statement.
        
        Delegated to core.filter.expression_builder.extract_where_clause_from_select().
        """
        from core.filter.expression_builder import extract_where_clause_from_select
        
        return extract_where_clause_from_select(sql_select)
    
    
    # NOTE: _filter_action_postgresql_materialized REMOVED in Phase 14.2 (113 lines)
    # Now handled by adapters/backends/postgresql/filter_actions.py execute_filter_action_postgresql_materialized()


    def _reset_action_postgresql(self, layer, name, cur, conn):
        """
        Execute reset action using PostgreSQL backend.
        
        EPIC-1 Phase E5/E6: Delegates to adapters.backends.postgresql.filter_actions.
        
        Args:
            layer: QgsVectorLayer to reset
            name: Layer identifier
            cur: Database cursor
            conn: Database connection
            
        Returns:
            bool: True if successful
        """
        if PG_EXECUTOR_AVAILABLE and pg_execute_reset:
            delete_history_fn = None
            if self._ps_manager:
                delete_history_fn = self._ps_manager.delete_subset_history
            
            return pg_execute_reset(
                layer=layer,
                name=name,
                cur=cur,
                conn=conn,
                queue_subset_fn=self._queue_subset_string,
                get_connection_fn=self._get_valid_postgresql_connection,
                execute_commands_fn=self._execute_postgresql_commands,
                get_session_name_fn=self._get_session_prefixed_name,
                delete_history_fn=delete_history_fn,
                project_uuid=self.project_uuid,
                current_mv_schema=self.current_materialized_view_schema
            )
        
        error_msg = "PostgreSQL filter_actions module not available"
        logger.error(error_msg)
        raise ImportError(error_msg)
    
    def _reset_action_postgresql_legacy(self, layer, name, cur, conn):
        """Legacy implementation - kept for fallback."""
        if self._ps_manager:
            try:
                self._ps_manager.delete_subset_history(self.project_uuid, layer.id())
            except Exception as e:
                logger.warning(f"Prepared statement failed, falling back to direct SQL: {e}")
                cur.execute(
                    f"""DELETE FROM fm_subset_history 
                        WHERE fk_project = '{self.project_uuid}' AND layer_id = '{layer.id()}';"""
                )
                conn.commit()
        else:
            cur.execute(
                f"""DELETE FROM fm_subset_history 
                    WHERE fk_project = '{self.project_uuid}' AND layer_id = '{layer.id()}';"""
            )
            conn.commit()
        
        schema = self.current_materialized_view_schema
        session_name = self._get_session_prefixed_name(name)
        sql_drop = f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."mv_{session_name}" CASCADE;'
        sql_drop += f' DROP MATERIALIZED VIEW IF EXISTS "{schema}"."mv_{session_name}_dump" CASCADE;'
        sql_drop += f' DROP INDEX IF EXISTS {schema}_{session_name}_cluster CASCADE;'
        
        connexion = self._get_valid_postgresql_connection()
        self._execute_postgresql_commands(connexion, [sql_drop])
        
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
        
        EPIC-1 Phase E5/E6: PostgreSQL logic delegates to filter_actions module.
        
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
        if use_postgresql and PG_EXECUTOR_AVAILABLE and pg_execute_unfilter:
            return pg_execute_unfilter(
                layer=layer,
                primary_key_name=primary_key_name,
                geom_key_name=geom_key_name,
                name=name,
                cur=cur,
                conn=conn,
                last_subset_id=last_subset_id,
                queue_subset_fn=self._queue_subset_string,
                get_connection_fn=self._get_valid_postgresql_connection,
                execute_commands_fn=self._execute_postgresql_commands,
                get_session_name_fn=self._get_session_prefixed_name,
                create_simple_mv_fn=self._create_simple_materialized_view_sql,
                project_uuid=self.project_uuid,
                current_mv_schema=self.current_materialized_view_schema
            )
        elif use_postgresql:
            # PostgreSQL but module not available
            error_msg = "PostgreSQL filter_actions module not available"
            logger.error(error_msg)
            raise ImportError(error_msg)
        
        # Spatialite path
        return self._unfilter_action_spatialite(
            layer, primary_key_name, geom_key_name, name, custom,
            cur, conn, last_subset_id
        )
    
    def _unfilter_action_spatialite(self, layer, primary_key_name, geom_key_name, name, custom, cur, conn, last_subset_id):
        """Unfilter implementation for Spatialite backend."""
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
            
            logger.info("Unfilter - Spatialite backend - recreating previous subset")
            success = self._manage_spatialite_subset(
                layer, sql_subset_string, primary_key_name, geom_key_name,
                name, custom=False, cur=None, conn=None, current_seq_order=0
            )
            if not success:
                # THREAD SAFETY: Queue subset clear for application in finished()
                self._queue_subset_string(layer, '')
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

    def _has_expensive_spatial_expression(self, sql_string: str) -> bool:
        """
        Detect if a SQL expression contains expensive spatial predicates.
        
        EPIC-1 Phase E7.5: Legacy code removed - fully delegates to core.optimization.query_analyzer.
        """
        from core.optimization.query_analyzer import has_expensive_spatial_expression
        return has_expensive_spatial_expression(sql_string)

    def _is_complex_filter(self, subset: str, provider_type: str) -> bool:
        """
        Check if a filter expression is complex (requires longer refresh delay).
        
        EPIC-1 Phase E7.5: Legacy code removed - fully delegates to core.optimization.query_analyzer.
        """
        from core.optimization.query_analyzer import is_complex_filter
        return is_complex_filter(subset, provider_type)

    def _single_canvas_refresh(self):
        """
        Perform a single comprehensive canvas refresh after filter application.
        
        FIX v2.5.21: Replaces the previous multi-refresh approach that caused
        overlapping refreshes to cancel each other, leaving the canvas white.
        
        FIX v2.6.5: PERFORMANCE - Only refresh layers involved in filtering,
        not ALL project layers. Skip updateExtents() for large layers.
        
        FIX v2.9.11: REMOVED stopRendering() for Spatialite/OGR layers
        For large FID filters (100k+ FIDs), rendering can take 30+ seconds.
        Calling stopRendering() after the 1500ms delay cancels in-progress
        rendering, causing "Building features list was canceled" messages
        and empty/incomplete layer display.
        
        This method:
        1. Checks if only file-based layers are filtered (skip stopRendering)
        2. Forces reload for layers with complex filters (PostgreSQL only)
        3. Triggers repaint for filtered layers (skip expensive updateExtents for large layers)
        4. Performs a single final canvas refresh
        """
        try:
            from qgis.core import QgsProject
            
            canvas = iface.mapCanvas()
            
            # v2.9.11: Only stop rendering for PostgreSQL layers
            # For OGR/Spatialite with large FID filters, stopRendering() cancels
            # in-progress feature loading, causing incomplete display
            has_postgres_filtered = False
            for layer_id, layer in QgsProject.instance().mapLayers().items():
                try:
                    if layer.type() == 0 and layer.providerType() == 'postgres':
                        subset = layer.subsetString() or ''
                        if subset:
                            has_postgres_filtered = True
                            break
                except Exception:
                    pass
            
            if has_postgres_filtered:
                # PostgreSQL layers benefit from stopRendering() to clear stale cache
                canvas.stopRendering()
                logger.debug("stopRendering() called for PostgreSQL layers")
            else:
                # Skip stopRendering() for OGR/Spatialite to avoid canceling feature loading
                logger.debug("Skipping stopRendering() for file-based layers")
            
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
                    # 
                    # v3.0.10: CRITICAL FIX - Block signals during reload() to prevent
                    # currentLayerChanged signals from triggering combobox changes
                    if provider_type == 'postgres':
                        # PostgreSQL: Force reload for complex filters (MV-based)
                        if self._is_complex_filter(subset, provider_type):
                            try:
                                layer.blockSignals(True)  # v3.0.10: Block async signals
                                layer.dataProvider().reloadData()
                                layers_reloaded += 1
                            except Exception as reload_err:
                                logger.debug(f"reloadData() failed for {layer.name()}: {reload_err}")
                                try:
                                    layer.reload()
                                except Exception:
                                    pass
                            finally:
                                layer.blockSignals(False)  # v3.0.10: Always unblock
                        else:
                            try:
                                layer.blockSignals(True)  # v3.0.10: Block async signals
                                layer.reload()
                            except Exception:
                                pass
                            finally:
                                layer.blockSignals(False)  # v3.0.10: Always unblock
                    # v2.9.24: For Spatialite, use reload() to ensure features display correctly on second filter
                    # For OGR without FID filters, just triggerRepaint() is enough
                    elif provider_type == 'spatialite':
                        try:
                            layer.blockSignals(True)  # v3.0.10: Block async signals
                            layer.reload()
                            layers_reloaded += 1
                            logger.debug(f"Forced reload() for Spatialite layer {layer.name()}")
                        except Exception as reload_err:
                            logger.debug(f"reload() failed for {layer.name()}: {reload_err}")
                        finally:
                            layer.blockSignals(False)  # v3.0.10: Always unblock
                    # v2.6.6: For OGR, just triggerRepaint() - NO reloadData()
                    # This prevents the freeze caused by re-evaluating large FID IN filters
                    
                    # v2.6.5: Skip updateExtents for large layers to prevent freeze
                    # v3.0.10: Also protect against None feature_count
                    feature_count = layer.featureCount()
                    if feature_count is not None and feature_count >= 0 and feature_count < MAX_FEATURES_FOR_UPDATE_EXTENTS:
                        layer.updateExtents()
                    # else: skip expensive updateExtents for very large layers or unknown count
                    
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
                                    # CRIT-005 FIX: Block signals during reload to prevent
                                    # currentLayerChanged emissions that cause combobox reset
                                    layer.blockSignals(True)
                                    layer.dataProvider().reloadData()
                                    logger.debug(f"  → Forced reloadData() for {layer.name()} (postgres, complex filter)")
                                except Exception as reload_err:
                                    logger.debug(f"  → reloadData() failed for {layer.name()}: {reload_err}")
                                    try:
                                        layer.reload()
                                    except Exception:
                                        pass
                                finally:
                                    layer.blockSignals(False)
                                layers_refreshed['postgres'] += 1
                            else:
                                try:
                                    # CRIT-005 FIX: Block signals during reload
                                    layer.blockSignals(True)
                                    layer.reload()
                                except Exception:
                                    pass
                                finally:
                                    layer.blockSignals(False)
                        # v2.6.6: For OGR/Spatialite, just triggerRepaint - NO reloadData()
                        # This prevents freeze on large FID IN filters
                        
                        # v2.6.6: Skip updateExtents for large layers to prevent freeze
                        # v3.0.10: Protect against None feature_count
                        feature_count = layer.featureCount()
                        if feature_count is not None and feature_count >= 0 and feature_count < MAX_FEATURES_FOR_UPDATE_EXTENTS:
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
        """Cancel task and cleanup all active database connections.
        
        CRASH FIX (v2.8.7): Removed QgsMessageLog call to prevent Windows fatal
        exception (access violation) during QGIS shutdown. When QgsTaskManager::cancelAll()
        is called during QgsApplication destruction, QgsMessageLog may already be
        destroyed even if QApplication.instance() is still valid. Use Python logger only.
        """
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
        
        # CRASH FIX (v2.8.7): Use Python logger only, NOT QgsMessageLog
        # QgsMessageLog may be destroyed during QGIS shutdown, causing access violation
        try:
            logger.info(f'"{self.description()}" task was canceled')
        except Exception:
            pass
        
        super().cancel()

    def _restore_source_layer_selection(self):
        """
        v2.9.23: Restore the source layer selection after filter/unfilter.
        
        This ensures the selected features remain visually highlighted on the map
        after the filtering operation completes.
        """
        if not self.source_layer or not is_valid_layer(self.source_layer):
            return
        
        # Get feature FIDs from task parameters
        feature_fids = self.task_parameters.get("task", {}).get("feature_fids", [])
        
        # Fallback: extract FIDs from features list if feature_fids not available
        if not feature_fids:
            task_features = self.task_parameters.get("task", {}).get("features", [])
            if task_features:
                feature_fids = [f.id() for f in task_features if hasattr(f, 'id') and f.id() is not None]
        
        if feature_fids:
            try:
                # Select features by their IDs
                self.source_layer.selectByIds(feature_fids)
                logger.info(f"✓ Restored source layer selection: {len(feature_fids)} feature(s) selected")
            except Exception as e:
                logger.debug(f"Could not restore selection: {e}")

    def finished(self, result):
        result_action = None
        message_category = MESSAGE_TASKS_CATEGORIES[self.task_action]
        
        # E6: Delegate warning display to task_completion_handler
        if hasattr(self, 'warning_messages') and self.warning_messages:
            tch_display_warnings(self.warning_messages)
            self.warning_messages = []  # Clear after display
        
        # E6: Check if subset application should be skipped
        has_pending = hasattr(self, '_pending_subset_requests')
        pending_list = self._pending_subset_requests if has_pending else []
        truly_canceled = should_skip_subset_application(
            self.isCanceled(), has_pending, pending_list, result
        )
        
        if truly_canceled and hasattr(self, '_pending_subset_requests') and not self._pending_subset_requests:
            logger.info("Task was canceled - skipping pending subset requests to prevent partial filter application")
            if hasattr(self, '_pending_subset_requests'):
                self._pending_subset_requests = []  # Clear to prevent any application
        
        # THREAD SAFETY FIX v2.3.21: Apply pending subset strings on main thread
        # E6: Delegated to task_completion_handler.apply_pending_subset_requests()
        if hasattr(self, '_pending_subset_requests') and self._pending_subset_requests:
            apply_pending_subset_requests(
                self._pending_subset_requests,
                safe_set_subset_string
            )
            # Clear the pending requests
            self._pending_subset_requests = []
            
            # E6: Delegated canvas refresh to task_completion_handler
            schedule_canvas_refresh(
                self._is_complex_filter,
                self._single_canvas_refresh
            )
        
        # CRITICAL FIX v2.3.13: Only cleanup MVs on reset/unfilter actions, NOT on filter
        # When filtering, materialized views are referenced by the layer's subsetString.
        # Cleaning them up would invalidate the filter expression causing empty results.
        # Cleanup should only happen when:
        # - reset: User wants to remove all filters (MVs no longer needed)
        # - unfilter: User wants to revert to previous state (MVs no longer needed)
        # - export: After exporting data (MVs were temporary for export)
        if self.task_action in ('reset', 'unfilter', 'export'):
            self._cleanup_postgresql_materialized_views()
        
        # E6: Delegate memory layer cleanup to task_completion_handler
        if hasattr(self, 'ogr_source_geom'):
            cleanup_memory_layer(self.ogr_source_geom)
            self.ogr_source_geom = None

        if self.exception is None:
            # v3.0.8: CRITICAL FIX - Only show error message if task was TRULY canceled by user
            # When a new filter task starts, it cancels previous tasks. Those tasks call finished()
            # with result=False and message="Filter task was canceled by user". We should NOT
            # display this as a critical error since it's expected behavior when starting a new filter.
            # However, we must NOT return early here as it would skip cleanup and signal reconnection.
            task_was_canceled = self.isCanceled()
            
            if result is None:
                # Task was likely canceled by user - log only, no message bar notification
                logger.info('Task completed with no result (likely canceled by user)')
            elif result is False:
                # Task failed without exception - only display error if NOT canceled
                if task_was_canceled:
                    # Task was canceled - don't show error message
                    logger.info('Task was canceled - no error message displayed')
                else:
                    # Task really failed - display error message
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
                    
                    # v2.9.23: Restore source layer selection after filter/unfilter
                    # This keeps the selected features visually highlighted on the map
                    try:
                        self._restore_source_layer_selection()
                    except Exception as sel_err:
                        logger.debug(f"Could not restore source layer selection: {sel_err}")
                    
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
        
        # FIX v2.9.24: Clean up OGR backend temporary GEOS-safe layers
        # These accumulate during multi-layer filtering and must be released after task completes
        try:
            # Import cleanup function from OGR backend
            from ..backends.ogr_backend import cleanup_ogr_temp_layers
            
            # Get OGR backend instances from task_parameters if they exist
            # These may have been created during fallback from Spatialite
            if hasattr(self, 'task_parameters'):
                # Check for OGR backend instances stored in task params
                ogr_backends = []
                
                # Look for backend instances in different places
                if '_backend_instances' in self.task_parameters:
                    ogr_backends.extend(self.task_parameters['_backend_instances'])
                
                # Clean up each backend instance
                for backend in ogr_backends:
                    if backend and hasattr(backend, '_temp_layers_keep_alive'):
                        cleanup_ogr_temp_layers(backend)
                        logger.debug(f"Cleaned up temp layers for backend: {type(backend).__name__}")
        except Exception as cleanup_err:
            logger.debug(f"OGR temp layer cleanup failed (non-critical): {cleanup_err}")
        
        # MIG-023: Log TaskBridge metrics for migration validation
        if hasattr(self, '_task_bridge') and self._task_bridge:
            try:
                metrics_report = self._task_bridge.get_metrics_report()
                logger.info(metrics_report)
            except Exception as metrics_err:
                logger.debug(f"TaskBridge metrics logging failed: {metrics_err}")

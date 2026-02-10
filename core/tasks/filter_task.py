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
    from ...core.tasks.filter_task import FilterEngineTask
Or from the package:
    from ...core.tasks import FilterEngineTask"""

import logging
import os
import uuid
from typing import Any, Dict, List, Optional

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsProcessing,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProject,
    QgsProperty,
    QgsTask,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import pyqtSignal
from qgis import processing

# Import logging configuration (migrated to infrastructure.logging)
from ...infrastructure.logging import setup_logger
from ...infrastructure.utils.thread_utils import main_thread_only
from ...config.config import ENV_VARS

# EPIC-1 Phase E12: Import extracted orchestration modules (relative import in core/)
from ..filter.filter_orchestrator import FilterOrchestrator
from ..filter.expression_builder import ExpressionBuilder

# EPIC-1 Phase E5: Import source filter builder functions (relative import in core/)

# Setup logger with rotation
logger = setup_logger(
    'FilterMate.Tasks.Filter',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_tasks.log'),
    level=logging.INFO
)

# PostgreSQL availability check - EPIC-1 E13: Use BackendServices facade
from ..ports.backend_services import get_backend_services

# Lazy load psycopg2 and availability flags via facade
_backend_services = get_backend_services()
_pg_availability = _backend_services.get_postgresql_availability()
psycopg2 = _pg_availability.psycopg2
PSYCOPG2_AVAILABLE = _pg_availability.psycopg2_available
POSTGRESQL_AVAILABLE = _pg_availability.postgresql_available

# Import constants (migrated to infrastructure)
from ...infrastructure.constants import (
    PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR
)

# Backend architecture (migrated to adapters.backends)

# Import utilities (migrated to infrastructure)
from ...infrastructure.utils import (
    safe_set_subset_string,
    get_datasource_connexion_from_layer,
    detect_layer_provider_type,
)

# Import object safety utilities (v2.3.9 - stability fix, migrated to infrastructure)
from ...infrastructure.utils import (
    is_layer_valid as is_valid_layer
)

# Import prepared statements manager (migrated to infrastructure/database/)
from ...infrastructure.database.prepared_statements import create_prepared_statements

# Import task utilities (Phase 3a - migrated to infrastructure)
from ...infrastructure.utils import (
    spatialite_connect,
    ensure_db_directory_exists,
    get_best_metric_crs,
    MESSAGE_TASKS_CATEGORIES
)

# Import geometry safety module (v2.3.9 - stability fix, migrated to core/geometry)

# Import CRS utilities (v2.5.7 - improved CRS compatibility, migrated to core/geometry)
try:
    from ..geometry.crs_utils import (
        is_geographic_crs,
        is_metric_crs,
        get_optimal_metric_crs,
        get_layer_crs_info
    )
    CRS_UTILS_AVAILABLE = True
except ImportError:
    CRS_UTILS_AVAILABLE = False
    logger.warning("crs_utils module not available - using legacy CRS handling")

# Import from infrastructure (EPIC-1 migration)
from ...infrastructure.cache import SourceGeometryCache
from ...infrastructure.streaming import StreamingExporter, StreamingConfig
from ...infrastructure.parallel import ParallelFilterExecutor, ParallelConfig

# Import from core (EPIC-1 migration - relative import now that we're in core/)
from ..optimization import get_combined_query_optimizer

# Phase E13: Import extracted classes (January 2026)
from .executors.attribute_filter_executor import AttributeFilterExecutor
from .executors.spatial_filter_executor import SpatialFilterExecutor
from .cache.geometry_cache import GeometryCache
from .cache.expression_cache import ExpressionCache
from .connectors.backend_connector import BackendConnector
from .builders.subset_string_builder import SubsetStringBuilder
from .collectors.feature_collector import FeatureCollector
from .dispatchers.action_dispatcher import (
    create_dispatcher_for_task, create_action_context_from_task
)

# E6: Task completion handler functions (relative import, same package)
from .task_completion_handler import (
    display_warning_messages as tch_display_warnings,
    should_skip_subset_application,
    apply_pending_subset_requests,
    schedule_canvas_refresh,
    cleanup_memory_layer
)

# EPIC-1 Phase E4-S9: Centralized history repository
from ...adapters.repositories.history_repository import HistoryRepository

# EPIC-1 E13: Use BackendServices facade for all adapter imports
# This maintains hexagonal architecture by routing through core/ports

# v3.0 MIG-023: TaskBridge for Strangler Fig migration
get_task_bridge, BridgeStatus = _backend_services.get_task_bridge()
TASK_BRIDGE_AVAILABLE = get_task_bridge is not None

# PostgreSQL filter executor - lazy loaded via facade
pg_executor = _backend_services.get_postgresql_executor()
PG_EXECUTOR_AVAILABLE = pg_executor is not None

# Get individual PostgreSQL actions via facade
_pg_actions = _backend_services.get_postgresql_filter_actions()
if _pg_actions:
    pg_execute_filter = _pg_actions.get('filter')
    pg_execute_reset = _pg_actions.get('reset')
    pg_execute_unfilter = _pg_actions.get('unfilter')
    # These functions are not in the facade yet - use None for now
    pg_execute_direct = None
    pg_execute_materialized = None
    pg_has_expensive_expr = None
else:
    pg_execute_filter = None
    pg_execute_direct = None
    pg_execute_materialized = None
    pg_has_expensive_expr = None
    pg_execute_reset = None
    pg_execute_unfilter = None

# Spatialite filter executor - lazy loaded via facade
sl_executor = _backend_services.get_spatialite_executor()
SL_EXECUTOR_AVAILABLE = sl_executor is not None

# OGR filter executor - lazy loaded via facade
ogr_executor = _backend_services.get_ogr_executor()
OGR_EXECUTOR_AVAILABLE = ogr_executor is not None

# OGR filter actions - EPIC-1 Phase E4-S8
_ogr_actions = _backend_services.get_ogr_filter_actions()
if _ogr_actions:
    ogr_execute_reset = _ogr_actions.get('reset')
    ogr_execute_unfilter = _ogr_actions.get('unfilter')
    ogr_apply_subset = _ogr_actions.get('apply_subset')
    ogr_cleanup_temp_layers = _ogr_actions.get('cleanup')
else:
    ogr_execute_reset = None
    ogr_execute_unfilter = None
    ogr_apply_subset = None
    ogr_cleanup_temp_layers = None


class FilterEngineTask(QgsTask):
    """Main QgsTask for filtering and unfiltering vector data.

    This task orchestrates all filtering operations in FilterMate, supporting:
    - Source layer filtering (attribute and geometry)
    - Multi-layer geometric filtering with spatial predicates
    - Export operations (standard, batch, ZIP, streaming)
    - Filter history management (undo/redo/reset)

    Supports multiple backends:
    - PostgreSQL/PostGIS (optimal for large datasets >100k features)
    - Spatialite (good for medium datasets <100k features)
    - OGR (fallback for shapefiles, GeoPackage, etc.)

    Thread Safety:
        All setSubsetString operations are queued via applySubsetRequest signal
        and applied in finished() on the main Qt thread.

    Attributes:
        task_action: Action to perform ('filter', 'unfilter', 'reset', 'export').
        task_parameters: Dict containing task configuration and layer info.
        warning_messages: List of warnings to display after task completion.
        layers: Dict of layers organized by provider type.
        source_layer: The primary layer being filtered.

    Example:
        >>> task = FilterEngineTask(
        ...     description="Filter parcels",
        ...     task_action="filter",
        ...     task_parameters={"task": {...}, "filtering": {...}}
        ... )
        >>> QgsApplication.taskManager().addTask(task)
    """

    # Signal to apply subset string on main thread
    # setSubsetString is NOT thread-safe and MUST be called from the main Qt thread.
    # This signal allows background tasks to request filter application on the main thread.
    applySubsetRequest = pyqtSignal(QgsVectorLayer, str)

    # Cache de classe (partagé entre toutes les instances de FilterEngineTask)
    # Lazy initialization to avoid import-time errors with logging
    _geometry_cache = None

    # Cache d'expressions (partagé entre toutes les instances)
    _expression_cache = None  # Initialized lazily via get_query_cache()

    @classmethod
    def get_geometry_cache(cls) -> 'SourceGeometryCache':
        """Get or create the shared geometry cache.

        Implements lazy initialization of the class-level geometry cache.
        The cache is shared between all FilterEngineTask instances to avoid
        redundant geometry preparation across multiple filter operations.

        Returns:
            SourceGeometryCache: The shared geometry cache instance.
        """
        if cls._geometry_cache is None:
            cls._geometry_cache = SourceGeometryCache()
        return cls._geometry_cache

    def __init__(
        self,
        description: str,
        task_action: str,
        task_parameters: Dict[str, Any],
        backend_registry: Optional[Any] = None
    ) -> None:
        """
        Initialize FilterEngineTask.

        Args:
            description: Task description for QGIS task manager
            task_action: Action to perform ('filter', 'unfilter', 'reset', 'export')
            task_parameters: Dict with task configuration
            backend_registry: Optional BackendRegistry for hexagonal architecture.
                             If None, falls back to legacy direct imports.
                             (v4.0.1 - Strangler Fig pattern)
        """
        QgsTask.__init__(self, description, QgsTask.CanCancel)

        self.exception = None
        self.task_action = task_action
        self.task_parameters = task_parameters

        # Backend registry for hexagonal architecture compliance
        # If provided, use registry for backend selection instead of direct imports
        self._backend_registry = backend_registry

        # Store warnings from worker thread for display in finished()
        # Cannot call iface.messageBar() from worker thread - would cause crash
        self.warning_messages = []

        # Phase E13: Initialize extracted helper classes
        self.geom_cache = GeometryCache()
        self.expr_cache = ExpressionCache()
        self._attribute_executor = None  # Lazy init
        self._spatial_executor = None  # Lazy init
        self._backend_connector = None  # Lazy init
        self._subset_builder = None  # Lazy init (Phase E13 Step 4)
        self._feature_collector = None  # Lazy init (Phase E13 Step 5)

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
        # Use QgsProject.instance() directly - always available in QGIS
        self.PROJECT = QgsProject.instance()
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

        # Store subset string requests to apply on main thread
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

        # Phase E13 Step 6: ActionDispatcher for clean action routing
        self._action_dispatcher = None

    # ========================================================================
    # FIX 2026-01-16: Early Predicate Initialization
    # ========================================================================

    def _initialize_current_predicates(self):
        """
        Initialize current_predicates from task parameters EARLY in the filtering process.

        FIX 2026-01-16: This method MUST be called at the start of execute_filtering(),
        BEFORE execute_source_layer_filtering(). Previously, predicates were only
        initialized in STEP 2/2 (distant layers), but ExpressionBuilder and
        FilterOrchestrator are lazy-initialized during STEP 1/2 and need predicates.

        Without early initialization:
        - ExpressionBuilder received EMPTY predicates
        - FilterOrchestrator received EMPTY predicates
        - Geometric filtering failed silently

        With early initialization:
        - All components receive correct predicates from the start
        - OGR backend gets both SQL names AND numeric QGIS codes
        """
        # Get geometric predicates from filtering parameters
        filtering_params = self.task_parameters.get("filtering", {})
        geom_predicates = filtering_params.get("geometric_predicates", [])

        # Log FULL filtering params for diagnosis
        from qgis.core import QgsMessageLog, Qgis as QgisLevel

        logger.info("=" * 70)
        logger.info("🔍 FILTERING PARAMETERS RECEIVED:")
        logger.info(f"   has_geometric_predicates: {filtering_params.get('has_geometric_predicates', 'NOT SET')}")
        logger.info(f"   geometric_predicates: {geom_predicates}")
        logger.info(f"   has_layers_to_filter: {filtering_params.get('has_layers_to_filter', 'NOT SET')}")
        logger.info(f"   layers_to_filter count: {len(filtering_params.get('layers_to_filter', []))}")
        logger.info("=" * 70)

        if not geom_predicates:
            # CRITICAL: Log to QGIS panel - this explains why distant layers won't be filtered!
            logger.warning("⚠️ No geometric predicates in task_parameters - distant layers will NOT be filtered!")
            QgsMessageLog.logMessage(
                "⚠️ No geometric predicates configured - check 'Intersect' checkbox in Filtering panel",
                "FilterMate", QgisLevel.Warning
            )
            self.current_predicates = {}
            return

        logger.info("🔧 EARLY PREDICATE INITIALIZATION")
        logger.info(f"   Input geometric_predicates: {geom_predicates}")
        QgsMessageLog.logMessage(
            f"🔧 Predicates: {geom_predicates}",
            "FilterMate", QgisLevel.Info
        )

        # Mapping SQL function → QGIS predicate code (pour OGR/processing)
        sql_to_qgis_code = {
            'ST_Intersects': 0,
            'ST_Contains': 1,
            'ST_Disjoint': 2,
            'ST_Equals': 3,
            'ST_Touches': 4,
            'ST_Overlaps': 5,
            'ST_Within': 6,
            'ST_Crosses': 7,
            'ST_Covers': 1,     # maps to Contains
            'ST_CoveredBy': 6,  # maps to Within
        }

        # Reset current_predicates
        self.current_predicates = {}
        # Separate numeric predicates for OGR (prevent duplicates in PostgreSQL)
        self.numeric_predicates = {}

        for key in geom_predicates:
            if key in self.predicates:
                func_name = self.predicates[key]
                # Store SQL name (for PostgreSQL/Spatialite)
                # Only store string key to prevent duplicate EXISTS generation
                # Previously, storing BOTH string and numeric keys caused build_expression()
                # to iterate twice with same predicate → duplicate EXISTS clauses
                self.current_predicates[func_name] = func_name

                # Store numeric code separately for OGR/processing
                qgis_code = sql_to_qgis_code.get(func_name)
                if qgis_code is not None:
                    self.numeric_predicates[qgis_code] = func_name
                    logger.debug(f"   Mapped: {key} → {func_name} → QGIS code {qgis_code}")
                else:
                    logger.warning(f"   ⚠️ No QGIS code for: {key} → {func_name}")
            else:
                logger.warning(f"   ⚠️ Unknown predicate key: {key}")

        # Log final state
        # Current_predicates only has string keys, numeric_predicates has numeric keys
        logger.info(f"   current_predicates (SQL): {self.current_predicates}")
        logger.info(f"   numeric_predicates (OGR): {self.numeric_predicates}")
        logger.info("   v2.10.0: Predicates now stored separately to prevent duplicate EXISTS")
        logger.info("=" * 70)

        # FIX 2026-01-16: Propagate predicates to EXISTING instances
        # TaskRunOrchestrator may have already created expression_builder and filter_orchestrator
        # with current_predicates=[], so we must update them here.
        if self._expression_builder is not None:
            self._expression_builder.current_predicates = self.current_predicates
            logger.debug("Propagated predicates to existing ExpressionBuilder")

        if self._filter_orchestrator is not None:
            self._filter_orchestrator.current_predicates = self.current_predicates
            logger.debug("Propagated predicates to existing FilterOrchestrator")

    # ========================================================================
    # Phase E13: Lazy Initialization for Extracted Classes
    # ========================================================================

    def _get_attribute_executor(self):
        """Get or create AttributeFilterExecutor (lazy initialization)."""
        if self._attribute_executor is None:
            self._attribute_executor = AttributeFilterExecutor(
                layer=self.source_layer,
                provider_type=self.param_source_provider_type,
                primary_key=self.primary_key_name,
                table_name=self.param_source_table,
                old_subset=self.param_source_old_subset,
                combine_operator=self.param_source_layer_combine_operator or 'AND',
                task_bridge=self._task_bridge
            )
        return self._attribute_executor

    def _get_spatial_executor(self):
        """Get or create SpatialFilterExecutor (lazy initialization)."""
        if self._spatial_executor is None:
            self._spatial_executor = SpatialFilterExecutor(
                source_layer=self.source_layer,
                project=self.PROJECT,
                backend_registry=None,  # Not used in current implementation
                task_bridge=self._task_bridge,
                postgresql_available=POSTGRESQL_AVAILABLE,
                geometry_cache=self.geom_cache
            )
        return self._spatial_executor

    def _get_backend_connector(self):
        """Get or create BackendConnector (lazy initialization)."""
        if self._backend_connector is None:
            self._backend_connector = BackendConnector(
                layer=self.source_layer,
                backend_registry=self._backend_registry
            )
        return self._backend_connector

    def _get_subset_builder(self):
        """
        Get or create SubsetStringBuilder (lazy initialization).

        Phase E13 Step 4: Extracted subset string building logic.
        """
        if self._subset_builder is None:
            self._subset_builder = SubsetStringBuilder(
                sanitize_fn=self._sanitize_subset_string,
                use_optimizer=True
            )
        return self._subset_builder

    def _get_feature_collector(self):
        """
        Get or create FeatureCollector (lazy initialization).

        Phase E13 Step 5: Centralized feature ID collection.
        """
        if self._feature_collector is None:
            self._feature_collector = FeatureCollector(
                layer=self.source_layer,
                primary_key_field=getattr(self, 'primary_key_name', None),
                is_pk_numeric=self.task_parameters.get("infos", {}).get("primary_key_is_numeric", True),
                cache_enabled=True
            )
        return self._feature_collector

    def _get_action_dispatcher(self):
        """
        Get or create ActionDispatcher (lazy initialization).

        Phase E13 Step 6: Clean action routing via dispatcher pattern.
        """
        if self._action_dispatcher is None:
            self._action_dispatcher = create_dispatcher_for_task(self)
            logger.debug("ActionDispatcher initialized for FilterEngineTask")
        return self._action_dispatcher

    def _get_filter_orchestrator(self):
        """
        Get or create FilterOrchestrator (lazy initialization).

        ARCHITECTURE FIX 2026-01-16 (Winston): Callback Pattern Implementation
        Instead of passing current_predicates by value (which may be empty at creation time),
        we pass a lambda callback that fetches predicates dynamically at execution time.

        This eliminates the race condition where TaskRunOrchestrator creates
        FilterOrchestrator BEFORE _initialize_current_predicates() runs.

        The callback ensures predicates are ALWAYS fresh when orchestrate_geometric_filter()
        is called, regardless of when FilterOrchestrator was instantiated.
        """
        if self._filter_orchestrator is None:
            logger.debug("FilterOrchestrator: Creating new instance with callback pattern")

            self._filter_orchestrator = FilterOrchestrator(
                task_parameters=self.task_parameters,
                subset_queue_callback=self.queue_subset_request,
                parent_task=self,
                get_predicates_callback=lambda: getattr(self, 'current_predicates', {})
            )
            logger.debug("FilterOrchestrator lazy-initialized with predicate callback")
            # FIX 2026-01-17: Use self.current_predicates directly instead of undefined predicates_to_pass
            current_preds = getattr(self, 'current_predicates', None) or {}
            logger.debug(f"FilterOrchestrator: ALWAYS propagating predicates: {list(current_preds.keys()) if current_preds else 'EMPTY'}")

        return self._filter_orchestrator

    def _get_expression_builder(self):
        """
        Get or create ExpressionBuilder (lazy initialization).

        FIX 2026-01-15: ExpressionBuilder may not be set from context.
        This lazy initialization ensures it's always available.

        FIX 2026-01-16: Pass critical PostgreSQL parameters for EXISTS/ST_Intersects
        expressions. Without these, backend falls back to "id" IN (...) expressions.
        Always update parameters in case source geometries were prepared after initial creation.
        """
        # Get source WKT and SRID from prepared Spatialite geometry
        source_wkt = getattr(self, 'spatialite_source_geom', None)
        source_srid = None
        if hasattr(self, 'source_layer_crs_authid') and self.source_layer_crs_authid:
            try:
                source_srid = int(self.source_layer_crs_authid.split(':')[1])
            except (ValueError, IndexError):
                source_srid = 4326  # Default to WGS84

        # Get source feature count (priority: task_features > ogr_source_geom > source_layer)
        source_feature_count = None
        task_features = self.task_parameters.get("task", {}).get("features", [])
        if task_features and len(task_features) > 0:
            source_feature_count = len(task_features)
        elif hasattr(self, 'ogr_source_geom') and self.ogr_source_geom:
            from qgis.core import QgsVectorLayer
            if isinstance(self.ogr_source_geom, QgsVectorLayer):
                source_feature_count = self.ogr_source_geom.featureCount()
            else:
                source_feature_count = 1
        elif hasattr(self, 'source_layer') and self.source_layer:
            source_feature_count = self.source_layer.featureCount()

        # ALWAYS get fresh predicates (race condition fix)
        predicates_to_pass = getattr(self, 'current_predicates', None) or {}

        # Validate predicates are populated
        if not predicates_to_pass:
            logger.error("❌ _get_expression_builder called with EMPTY current_predicates!")
            logger.error("   Expression building may fail or produce incorrect filters.")

        if self._expression_builder is None:
            logger.debug(f"ExpressionBuilder: Creating new instance with predicates: {list(predicates_to_pass.keys()) if predicates_to_pass else 'EMPTY'}")

            self._expression_builder = ExpressionBuilder(
                task_parameters=self.task_parameters,
                source_layer=getattr(self, 'source_layer', None),
                current_predicates=predicates_to_pass,
                source_wkt=source_wkt,
                source_srid=source_srid,
                source_feature_count=source_feature_count,
                buffer_value=getattr(self, 'param_buffer_value', None),
                buffer_expression=getattr(self, 'param_buffer_expression', None),
                use_centroids_distant=getattr(self, 'param_use_centroids_distant_layers', False)
            )
            logger.debug("ExpressionBuilder lazy-initialized with PostgreSQL parameters")
        else:
            # CRITICAL: ALWAYS update parameters AND predicates to fix race condition
            # TaskRunOrchestrator may have created instance before source geom prep or predicate init
            self._expression_builder.source_wkt = source_wkt
            self._expression_builder.source_srid = source_srid
            self._expression_builder.source_feature_count = source_feature_count
            self._expression_builder.buffer_value = getattr(self, 'param_buffer_value', None)
            self._expression_builder.buffer_expression = getattr(self, 'param_buffer_expression', None)
            self._expression_builder.use_centroids_distant = getattr(self, 'param_use_centroids_distant_layers', False)
            self._expression_builder.current_predicates = predicates_to_pass
            logger.debug(f"ExpressionBuilder: ALWAYS propagating predicates: {list(predicates_to_pass.keys()) if predicates_to_pass else 'EMPTY'}")

        logger.debug(f"   source_wkt available: {source_wkt is not None}")
        logger.debug(f"   source_srid: {source_srid}")
        logger.debug(f"   source_feature_count: {source_feature_count}")
        logger.debug(f"   buffer_value: {getattr(self, 'param_buffer_value', None)}")
        return self._expression_builder

    # ========================================================================
    # Hexagonal Architecture - Backend Access Methods
    # ========================================================================

    def _get_backend_executor(self, layer_info: dict):
        """
        Get appropriate backend executor for a layer.

        v4.0.1: Uses BackendRegistry if available (hexagonal pattern),
        otherwise falls back to legacy direct imports (Strangler Fig).

        Phase E13: Delegates to BackendConnector.

        Args:
            layer_info: Dict with 'layer_provider_type' key

        Returns:
            FilterExecutorPort implementation or None
        """
        connector = self._get_backend_connector()
        return connector.get_backend_executor(layer_info)

    def _has_backend_registry(self) -> bool:
        """
        Check if backend registry is available.

        Phase E13: Delegates to BackendConnector.
        """
        connector = self._get_backend_connector()
        return connector.has_backend_registry()

    def _is_postgresql_available(self) -> bool:
        """
        Check if PostgreSQL backend is available.

        v4.0.1: Uses registry if available, otherwise legacy import.
        Phase E13: Delegates to BackendConnector.
        """
        connector = self._get_backend_connector()
        return connector.is_postgresql_available()

        # Fallback to legacy import
        return POSTGRESQL_AVAILABLE

    def _prepare_source_geometry_via_executor(self, layer_info: dict, feature_ids=None,
                                  buffer_value: float = 0.0, use_centroids: bool = False):
        """
        Prepare source geometry using backend executor.

        Phase E13: Delegates to SpatialFilterExecutor.

        Args:
            layer_info: Dict with layer metadata
            feature_ids: Optional list of feature IDs
            buffer_value: Buffer distance
            use_centroids: Use centroids instead of full geometries

        Returns:
            Tuple of (geometry_data, error_message)
        """
        executor = self._get_spatial_executor()

        return executor.prepare_source_geometry_via_executor(
            layer_info=layer_info,
            backend_registry=self._backend_registry,
            feature_ids=feature_ids,
            buffer_value=buffer_value,
            use_centroids=use_centroids
        )

    def _apply_subset_via_executor(self, layer, expression: str) -> bool:
        """
        Apply subset string using backend executor.

        v4.0.1: Uses BackendRegistry if available, otherwise falls back to legacy.

        Args:
            layer: QgsVectorLayer
            expression: Filter expression

        Returns:
            True if applied successfully, False if fallback required
        """
        if not self._backend_registry:
            return False

        try:
            layer_info = {'layer': layer, 'layer_provider_type': detect_layer_provider_type(layer)}
            executor = self._get_backend_executor(layer_info)
            if executor:
                return executor.apply_subset_string(layer, expression)
        except Exception as e:
            logger.debug(f"Executor.apply_subset_string failed: {e}")

        return False

    def _cleanup_backend_resources(self):
        """
        Cleanup backend resources using registry.

        v4.0.1: Delegates to BackendRegistry.cleanup_all() if available.
        Phase E13: Delegates to BackendConnector.
        v4.1.1: Also cleans up temporary OGR layers.
        """
        connector = self._get_backend_connector()
        connector.cleanup_backend_resources()

        # Cleanup temporary OGR layers via BackendServices facade
        _backend_services.cleanup_ogr_temp_layers()

    def queue_subset_request(self, layer: QgsVectorLayer, expression: str) -> bool:
        """Queue a subset string request for thread-safe application.

        Subset strings (filter expressions) cannot be applied directly from background
        threads due to Qt thread safety constraints. This method queues requests to be
        applied in finished() on the main Qt thread.

        Args:
            layer: The QgsVectorLayer to apply the filter to.
            expression: SQL WHERE clause or empty string to clear filter.

        Returns:
            True if the request was queued successfully.

        Note:
            The actual setSubsetString call is deferred until finished().
            Use empty string to clear the layer's filter.
        """
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
        """
        Get a Spatialite connection for the current task.

        FIX 2026-01-16: Previously delegated to safe_spatialite_connect() which is a
        @contextmanager, causing "'_GeneratorContextManager' object has no attribute 'cursor'"
        error. Now uses spatialite_connect() directly which returns a connection object.

        Ensures the database directory exists before connecting.

        Returns:
            sqlite3.Connection: Spatialite database connection
        """
        # Ensure directory exists first
        ensure_db_directory_exists(self.db_file_path)
        # Use spatialite_connect directly (NOT the context manager version)
        return spatialite_connect(self.db_file_path)

    def _get_valid_postgresql_connection(self):
        """
        Get a valid PostgreSQL connection for the current task.

        Checks if ACTIVE_POSTGRESQL in task_parameters contains a valid psycopg2
        connection object. If not (e.g., it's a string, dict, or None), attempts to
        obtain a fresh connection from the source layer.

        Returns:
            psycopg2.connection: Valid PostgreSQL connection object

        Raises:
            Exception: If no valid connection can be established
        """
        # Try to get connection from task parameters
        connexion = self.task_parameters.get("task", {}).get("options", {}).get("ACTIVE_POSTGRESQL")

        # Explicitly reject dict objects - they are NOT valid connections
        # This fixes "'dict' object has no attribute 'cursor'" errors
        if isinstance(connexion, dict):
            logger.warning("ACTIVE_POSTGRESQL is a dict (connection params), not a connection object - obtaining fresh connection")
            connexion = None

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

        Phase E13: Delegates to SpatialFilterExecutor.
        """
        executor = self._get_spatial_executor()

        result = executor.organize_layers_to_filter(
            task_action=self.task_action,
            task_parameters=self.task_parameters
        )

        # Update task state from result
        self.layers = result.layers_by_provider
        self.layers_count = result.layers_count
        self.provider_list = result.provider_list

    def _queue_subset_string(self, layer, expression):
        """
        Queue a subset string request for thread-safe application in finished().

        Phase E13 Step 4: Delegates to SubsetStringBuilder AND adds to task's
        _pending_subset_requests for backward compatibility with finished().

        CRITICAL FIX 2026-01-15: finished() reads self._pending_subset_requests,
        but SubsetStringBuilder stores in its own _pending_requests list.
        We must add to BOTH to ensure proper application.
        """
        # Add to task's _pending_subset_requests (used by finished())
        if layer and expression is not None:
            self._pending_subset_requests.append((layer, expression))
            logger.debug(f"📥 _queue_subset_string: Queued for {layer.name()}: {len(expression)} chars")

        # Also delegate to builder for consistency
        builder = self._get_subset_builder()
        return builder.queue_subset_request(layer, expression)

    def _get_pending_subset_requests(self):
        """
        Get pending subset requests for main thread processing.

        Phase E13 Step 4: Delegates to SubsetStringBuilder.
        """
        builder = self._get_subset_builder()
        return builder.get_pending_requests()

    def _log_backend_info(self):
        """Log backend info and performance warnings. Delegated to core.optimization.logging_utils."""
        from ..optimization.logging_utils import log_backend_info
        thresholds = self._get_optimization_thresholds()
        log_backend_info(
            task_action=self.task_action, provider_type=self.param_source_provider_type,
            postgresql_available=POSTGRESQL_AVAILABLE, feature_count=self.source_layer.featureCount(),
            large_dataset_threshold=thresholds['large_dataset_warning'],
            provider_postgres=PROVIDER_POSTGRES, provider_spatialite=PROVIDER_SPATIALITE, provider_ogr=PROVIDER_OGR
        )

    def _get_contextual_performance_warning(self, elapsed_time: float, severity: str = 'warning') -> str:
        """Generate contextual performance warning. Delegated to core.optimization.performance_advisor."""
        from ..optimization.performance_advisor import get_contextual_performance_warning
        return get_contextual_performance_warning(
            elapsed_time=elapsed_time, provider_type=self.param_source_provider_type,
            postgresql_available=POSTGRESQL_AVAILABLE, severity=severity
        )

    def _execute_task_action(self):
        """
        Execute the appropriate action based on task_action parameter.

        Phase E13 Step 6: Uses ActionDispatcher for clean action routing.
        Falls back to legacy if/elif for backward compatibility during migration.

        Returns:
            bool: True if action succeeded, False otherwise
        """
        # Phase E13: Try dispatcher-based routing first
        try:
            dispatcher = self._get_action_dispatcher()
            context = create_action_context_from_task(self)
            result = dispatcher.dispatch(self.task_action, context)

            # Log dispatch result
            if result.success:
                logger.info(f"Action '{self.task_action}' completed via dispatcher: {result.message}")
            else:
                logger.warning(f"Action '{self.task_action}' failed via dispatcher: {result.message}")

            return result.success

        except Exception as e:
            # Fallback to legacy routing if dispatcher fails
            logger.warning(f"ActionDispatcher failed, using legacy routing: {e}")
            return self._execute_task_action_legacy()

    def _execute_task_action_legacy(self):
        """
        Legacy action routing (pre-Phase E13).

        Kept as fallback during Strangler Fig migration.
        v4.1.0: Enhanced logging for debugging.
        """
        logger.info(f"📋 _execute_task_action_legacy: action={self.task_action}")

        try:
            if self.task_action == 'filter':
                logger.info("  → Executing filtering...")
                result = self.execute_filtering()
                logger.info(f"  ✓ execute_filtering returned: {result}")
                return result

            elif self.task_action == 'unfilter':
                logger.info("  → Executing unfiltering...")
                result = self.execute_unfiltering()
                logger.info(f"  ✓ execute_unfiltering returned: {result}")
                return result

            elif self.task_action == 'reset':
                logger.info("  → Executing reset...")
                result = self.execute_reseting()
                logger.info(f"  ✓ execute_reseting returned: {result}")
                return result

            elif self.task_action == 'export':
                if self.task_parameters["task"]["EXPORTING"]["HAS_LAYERS_TO_EXPORT"]:
                    logger.info("  → Executing export...")
                    result = self.execute_exporting()
                    logger.info(f"  ✓ execute_exporting returned: {result}")
                    return result
                else:
                    logger.warning("  ⚠️ Export requested but no layers to export")
                    return False

            logger.warning(f"  ⚠️ Unknown task_action: {self.task_action}")
            return False
        except Exception as e:
            logger.error(f"  ❌ _execute_task_action_legacy FAILED: {e}", exc_info=True)
            self.exception = e
            return False

    def run(self) -> bool:
        """
        Main task orchestration method (v2).

        PHASE 14.7: Migrated to TaskRunOrchestrator service.
        Delegates to execute_task_run() for main orchestration flow.

        Extracted 129 lines to core/services/task_run_orchestrator.py (v5.0-alpha).
        v4.1.0: Enhanced logging for debugging.

        Returns:
            bool: True if task completed successfully, False otherwise
        """
        import time
        import traceback
        run_start_time = time.time()

        # Log PostgreSQL availability at task start
        from qgis.core import QgsMessageLog, Qgis as QgisLevel

        logger.info(f"{'=' * 60}")
        logger.info(f"🔍 POSTGRESQL_AVAILABLE = {POSTGRESQL_AVAILABLE}")
        logger.info(f"🔍 PSYCOPG2_AVAILABLE = {PSYCOPG2_AVAILABLE}")
        logger.info(f"{'=' * 60}")

        # Also log to QGIS message panel for visibility
        QgsMessageLog.logMessage(
            "🔍 FilterMate PostgreSQL Status:\n"
            f"   POSTGRESQL_AVAILABLE = {POSTGRESQL_AVAILABLE}\n"
            f"   PSYCOPG2_AVAILABLE = {PSYCOPG2_AVAILABLE}",
            "FilterMate", QgisLevel.Info
        )

        logger.info("🏃 FilterEngineTask.run() STARTED")
        logger.info(f"   action={self.task_action}")
        logger.info(f"   layers_count={self.layers_count}")
        source_layer = getattr(self, 'source_layer', None)
        logger.info(f"   source_layer={source_layer.name() if source_layer else 'None (will be initialized)'}")
        logger.info(f"{'=' * 60}")

        # FIX 2026-01-16: Extract critical configuration values IMMEDIATELY
        # These must be available BEFORE execute_task_run() because they are used
        # during source layer filtering (e.g., _safe_spatialite_connect needs db_file_path)
        task_params = self.task_parameters.get("task", {})
        if task_params.get("db_file_path"):
            self.db_file_path = task_params["db_file_path"]
            logger.info(f"   db_file_path extracted: {self.db_file_path}")
        else:
            logger.warning("   ⚠️ db_file_path NOT in task_parameters['task'] - Spatialite operations may fail!")

        if task_params.get("project_uuid"):
            self.project_uuid = task_params["project_uuid"]
            logger.debug(f"   project_uuid extracted: {self.project_uuid}")

        if task_params.get("session_id"):
            self.session_id = task_params["session_id"]
            logger.debug(f"   session_id extracted: {self.session_id}")

        try:
            # PHASE 14.7: Delegate to TaskRunOrchestrator service
            from ..services.task_run_orchestrator import execute_task_run

            # Execute main orchestration
            result = execute_task_run(
                task_action=self.task_action,
                task_parameters=self.task_parameters,
                layers_count=self.layers_count,
                source_layer=getattr(self, 'source_layer', None),
                initialize_source_layer_callback=self._initialize_source_layer,
                configure_metric_crs_callback=self._configure_metric_crs,
                organize_layers_to_filter_callback=self._organize_layers_to_filter,
                log_backend_info_callback=self._log_backend_info,
                execute_task_action_callback=self._execute_task_action,
                get_contextual_performance_warning_callback=self._get_contextual_performance_warning,
                is_canceled_callback=self.isCanceled,
                set_progress_callback=self.setProgress
            )

            # Apply orchestration modules to task instance
            if result.success and hasattr(result, 'context'):
                if hasattr(result.context, 'result_processor'):
                    self._result_processor = result.context.result_processor
                    # Merge pending subset requests instead of overwriting
                    # For 'unfilter' and 'reset' actions, requests are added directly to
                    # self._pending_subset_requests in execute_unfiltering()/execute_reseting().
                    # We must extend the existing list, not replace it.
                    if result.context.result_processor._pending_subset_requests:
                        self._pending_subset_requests.extend(
                            result.context.result_processor._pending_subset_requests
                        )
                    self.warning_messages = result.context.result_processor.warning_messages

                if hasattr(result.context, 'expression_builder'):
                    self._expression_builder = result.context.expression_builder

                # ARCHITECTURE FIX 2026-01-16 (Winston): filter_orchestrator is now None from context
                # It will be lazy-initialized by _get_filter_orchestrator() with proper callback pattern
                if hasattr(result.context, 'filter_orchestrator') and result.context.filter_orchestrator is not None:
                    self._filter_orchestrator = result.context.filter_orchestrator
                # Else: lazy-init will handle it with callback pattern

            # Retrieve critical configuration values from context
            # These are REQUIRED for Spatialite connections and filter history
            if hasattr(result, 'context') and result.context:
                if result.context.db_file_path is not None:
                    self.db_file_path = result.context.db_file_path
                if result.context.project_uuid is not None:
                    self.project_uuid = result.context.project_uuid
                if result.context.session_id is not None:
                    self.session_id = result.context.session_id

            # Store exception if any
            if result.exception:
                self.exception = result.exception
                logger.error(f"❌ FilterEngineTask.run() EXCEPTION: {result.exception}")
                logger.error(f"   Traceback: {traceback.format_exc()}")

            # Merge warning messages
            if result.warning_messages:
                if not hasattr(self, 'warning_messages'):
                    self.warning_messages = []
                self.warning_messages.extend(result.warning_messages)

            # Enhanced completion logging
            run_elapsed = time.time() - run_start_time
            logger.info(f"{'=' * 60}")
            logger.info("🏁 FilterEngineTask.run() FINISHED")
            logger.info(f"   success={result.success}")
            logger.info(f"   elapsed={run_elapsed:.2f}s")
            logger.info(f"   exception={result.exception is not None}")
            logger.info(f"   warnings={len(result.warning_messages) if result.warning_messages else 0}")
            logger.info(f"{'=' * 60}")

            if not result.success and not result.exception:
                logger.warning("⚠️ Task returned False without exception - check task logic")
                # If self.exception was set by a callback but not propagated to result,
                # convert it to a message for user display
                if self.exception and not self.message:
                    self.message = f"Initialization error: {self.exception}"
                    logger.error(f"   Propagating callback exception to message: {self.exception}")

            return result.success

        except Exception as e:
            # Catch-all exception handler with full traceback
            run_elapsed = time.time() - run_start_time
            self.exception = e
            logger.error(f"{'=' * 60}")
            logger.error(f"❌ FilterEngineTask.run() CRASHED after {run_elapsed:.2f}s")
            logger.error(f"   action={self.task_action}")
            logger.error(f"   exception={type(e).__name__}: {e}")
            logger.error(f"   traceback:\n{traceback.format_exc()}")
            logger.error(f"{'=' * 60}")
            return False

    # ========================================================================
    # V3 TaskBridge Delegation Methods (Strangler Fig Pattern)
    # ========================================================================

    def _try_v3_attribute_filter(self, task_expression, task_features):
        """
        Try v3 TaskBridge attribute filter.

        Phase E13: Delegates to AttributeFilterExecutor.

        Returns:
            True/False/None (fallback to legacy)
        """
        executor = self._get_attribute_executor()

        result = executor.try_v3_attribute_filter(
            task_expression=task_expression,
            task_features=task_features,
            task_bridge=self._task_bridge,
            source_layer=self.source_layer,
            primary_key_name=self.primary_key_name,
            task_parameters=self.task_parameters
        )

        # Update task state from executor result
        if result is True and hasattr(executor, '_last_expression'):
            self.expression = executor._last_expression

        return result

    def _try_v3_spatial_filter(self, layer, layer_props, predicates):
        """
        Try v3 TaskBridge spatial filter.

        Phase E13: Delegates to SpatialFilterExecutor.

        Returns:
            True/False/None (fallback to legacy)
        """
        executor = self._get_spatial_executor()

        result = executor.try_v3_spatial_filter(
            layer=layer,
            layer_props=layer_props,
            predicates=predicates,
            task_bridge=self._task_bridge,
            source_layer=self.source_layer,
            task_parameters=self.task_parameters,
            combine_operator=self._get_combine_operator() or 'AND'
        )

        return result

    def _try_v3_multi_step_filter(self, layers_dict, progress_callback=None):
        """Try v3 TaskBridge multi-step filter. Returns True/None (fallback to legacy)."""
        if not self._task_bridge:
            return None

        # Check if TaskBridge supports multi-step
        if not self._task_bridge.supports_multi_step():
            logger.debug("TaskBridge: multi-step not supported - using legacy code")
            return None

        # CRITICAL v4.1.1 (2026-01-17): Disable V3 for PostgreSQL spatial filtering
        # The V3 PostgreSQLBackend does not generate proper EXISTS subqueries.
        # It sends raw SQL placeholders like "SPATIAL_FILTER(intersects)" which fail.
        # Use legacy PostgreSQLGeometricFilter which properly generates EXISTS clauses.
        if 'postgresql' in layers_dict and len(layers_dict.get('postgresql', [])) > 0:
            logger.debug("TaskBridge: PostgreSQL spatial filtering - using legacy code (V3 not ready)")
            return None

        # CRITICAL v4.1.2 (2026-01-19): Disable V3 for OGR spatial filtering
        # Same issue as PostgreSQL: V3 sends "SPATIAL_FILTER(intersects)" placeholder
        # which is not a valid QGIS expression function, causing:
        # "La fonction SPATIAL_FILTER est inconnue" error
        # Use legacy OGRExpressionBuilder.apply_filter() which uses QGIS processing
        if 'ogr' in layers_dict and len(layers_dict.get('ogr', [])) > 0:
            logger.debug("TaskBridge: OGR spatial filtering - using legacy code (V3 not ready)")
            return None

        # Skip multi-step for complex scenarios
        # Check for buffers which require special handling (both positive and negative)
        # Handle negative buffers (erosion) as well as positive buffers
        buffer_value = self.task_parameters.get("task", {}).get("buffer_value", 0)
        if buffer_value and buffer_value != 0:
            buffer_type = "expansion" if buffer_value > 0 else "erosion"
            logger.debug(f"TaskBridge: buffer active ({buffer_value}m {buffer_type}) - using legacy multi-step code")
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

                    # Build spatial expression from predicates
                    # Format: SPATIAL_FILTER(predicate1, predicate2, ...)
                    predicate_str = ', '.join(predicates) if predicates else 'intersects'
                    spatial_expression = f"SPATIAL_FILTER({predicate_str})"

                    step_config = {
                        'expression': spatial_expression,  # Required by TaskBridge
                        'target_layer_ids': [layer.id()],
                        'predicates': predicates,
                        'step_name': f"Filter {layer.name()}",
                        'use_previous_result': False  # Each layer filtered independently
                    }
                    steps.append(step_config)
                    logger.debug(f"   Step for {layer.name()}: predicates={predicates}, expression={spatial_expression}")

            # FIX 2026-01-16: Log source geometry diagnostic
            logger.info("=" * 70)
            logger.info("🔍 MULTI-STEP SOURCE GEOMETRY DIAGNOSTIC")
            logger.debug(f"   Source layer: {self.source_layer.name()} (provider: {self.param_source_provider_type})")
            logger.info(f"   Source feature count: {self.source_layer.featureCount()}")
            logger.info(f"   Source CRS: {self.source_layer.crs().authid() if self.source_layer.crs() else 'UNKNOWN'}")
            logger.info(f"   Target layers: {len(steps)}")
            for idx, (provider_type, layer_list) in enumerate(layers_dict.items(), 1):
                for layer, layer_props in layer_list:
                    logger.info(f"   {idx}. {layer.name()}:")
                    logger.info(f"      - Provider: {layer.providerType()}")
                    logger.info(f"      - CRS: {layer.crs().authid() if layer.crs() else 'UNKNOWN'}")
                    logger.info(f"      - Geometry column: {layer_props.get('layer_geometry_field', 'UNKNOWN')}")
                    logger.info(f"      - Primary key: {layer_props.get('layer_key_column_name', 'UNKNOWN')}")
            logger.info("=" * 70)

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
                logger.info("✅ V3 TaskBridge MULTI-STEP SUCCESS")
                logger.info(f"   Backend used: {bridge_result.backend_used}")
                logger.info(f"   Final feature count: {bridge_result.feature_count}")
                logger.debug(f"   Total execution time: {bridge_result.execution_time_ms:.1f}ms")
                logger.info("=" * 70)

                # Store metrics
                if 'actual_backends' not in self.task_parameters:
                    self.task_parameters['actual_backends'] = {}
                self.task_parameters['actual_backends']['_multi_step'] = f"v3_{bridge_result.backend_used}"

                return True

            elif bridge_result.status == BridgeStatus.FALLBACK:
                logger.info("⚠️ V3 TaskBridge MULTI-STEP: FALLBACK requested")
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
                logger.info("✅ V3 TaskBridge EXPORT SUCCESS")
                logger.info(f"   Features exported: {bridge_result.feature_count}")
                logger.debug(f"   Execution time: {bridge_result.execution_time_ms:.1f}ms")

                # Store in task_parameters for metrics
                if 'actual_backends' not in self.task_parameters:
                    self.task_parameters['actual_backends'] = {}
                self.task_parameters['actual_backends'][f'export_{layer.id()}'] = 'v3_streaming'

                return True

            elif bridge_result.status == BridgeStatus.FALLBACK:
                logger.info("⚠️ V3 TaskBridge EXPORT: FALLBACK requested")
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
        from ..services.filter_parameter_builder import build_filter_parameters
        from ...infrastructure.utils import detect_layer_provider_type

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

        # Update task_parameters with source table info
        # This is critical for ExpressionBuilder to access param_source_table
        # which is needed for adapting EXISTS clauses when filtering distant layers
        self.task_parameters['param_source_table'] = params.table_name
        self.task_parameters['param_source_schema'] = params.schema

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
        self.task_parameters.get("infos", {})
        # Preserve original infos dict for backward compatibility (optional)
        self.task_parameters.get("infos", {})

    def _sanitize_subset_string(self, subset_string):
        """
        Remove non-boolean display expressions and fix type casting issues in subset string.

        v4.7 E6-S2: Pure delegation to core.services.expression_service.sanitize_subset_string

        Args:
            subset_string (str): The original subset string

        Returns:
            str: Sanitized subset string with non-boolean expressions removed
        """
        from ..services.expression_service import sanitize_subset_string
        return sanitize_subset_string(subset_string, logger=logger)

    def _extract_spatial_clauses_for_exists(self, filter_expr, source_table=None):
        """Delegates to core.filter.expression_sanitizer.extract_spatial_clauses_for_exists()."""
        from ..filter.expression_sanitizer import extract_spatial_clauses_for_exists

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

        Phase E13: Delegates to AttributeFilterExecutor.

        Returns:
            tuple: (processed_expression, is_field_expression) or (None, None) if invalid
        """
        executor = self._get_attribute_executor()

        # FIX 2026-01-18: AttributeFilterExecutor.process_qgis_expression only accepts expression
        # Other context is already available in the executor instance
        result = executor.process_qgis_expression(expression=expression)

        # Update task state if field expression detected
        if result[1] and isinstance(result[1], tuple) and result[1][0]:
            self.is_field_expression = result[1]
        elif result[1]:
            self.is_field_expression = result[1]

        return result

    def _combine_with_old_subset(self, expression):
        """
        Combine new expression with old subset.

        Phase E13: Delegates to AttributeFilterExecutor.
        The executor already has old_subset, combine_operator, and provider_type
        set during initialization, so we only pass the expression.
        """
        executor = self._get_attribute_executor()

        # FIX 2026-01-18: AttributeFilterExecutor.combine_with_old_subset() only takes
        # the expression parameter - other values are stored in the executor instance
        return executor.combine_with_old_subset(expression)

    def _build_feature_id_expression(self, features_list):
        """
        Build expression from feature IDs.

        Phase E13: Delegates to AttributeFilterExecutor.

        FIX 2026-01-15: AttributeFilterExecutor.build_feature_id_expression()
        only accepts features_list and is_numeric. Other parameters come from
        the executor's constructor (stored in self).
        """
        executor = self._get_attribute_executor()

        result = executor.build_feature_id_expression(
            features_list=features_list,
            is_numeric=self.task_parameters["infos"]["primary_key_is_numeric"]
        )

        # FIX 2026-01-16: Log expression to diagnose WHERE prefix
        logger.info(f"🔍 _build_feature_id_expression result: '{result[:100] if result else None}...'")
        if result and result.strip().startswith('WHERE'):
            logger.error("❌ BUG: Expression starts with WHERE! Should NOT have WHERE prefix for setSubsetString")

        return result

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
        from ..filter.expression_sanitizer import optimize_duplicate_in_clauses

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
        # Use param_source_provider_type instead of providerType()
        # providerType() returns 'postgres' even when using OGR fallback (psycopg2 unavailable)
        # param_source_provider_type correctly accounts for OGR fallback
        if self.param_source_provider_type == PROVIDER_POSTGRES:
            expression = self._apply_postgresql_type_casting(expression, self.source_layer)

        # Do NOT call setSubsetString from worker thread!
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
        # Use param_source_provider_type instead of providerType()
        # providerType() returns 'postgres' even when using OGR fallback
        if self.param_source_provider_type == PROVIDER_POSTGRES:
            # FIX 2026-01-16: Strip leading "WHERE " from expression to prevent "WHERE WHERE" syntax error
            clean_expression = expression.lstrip()
            if clean_expression.upper().startswith('WHERE '):
                clean_expression = clean_expression[6:].lstrip()
                logger.debug("Stripped WHERE prefix from expression in _apply_filter_and_update_subset")

            # Build full SELECT expression for subset management (PostgreSQL only)
            full_expression = (
                f'SELECT "{self.param_source_table}"."{self.primary_key_name}", '  # nosec B608 - identifiers from QGIS layer metadata (task parameters)
                f'"{self.param_source_table}"."{self.param_source_geom}" '
                f'FROM "{self.param_source_schema}"."{self.param_source_table}" '
                f'WHERE {clean_expression}'
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

    def execute_source_layer_filtering(self) -> bool:
        """
        Manage the creation of the origin filtering expression (v2).

        PHASE 14.6: Migrated to SourceLayerFilterExecutor service.
        Delegates to execute_source_layer_filtering() for actual execution.

        Extracted 220 lines to core/services/source_layer_filter_executor.py (v5.0-alpha).
        """
        # Initialize all parameters and configuration
        self._initialize_source_filtering_parameters()

        # PHASE 14.6: Delegate to SourceLayerFilterExecutor service
        from ..services.source_layer_filter_executor import execute_source_layer_filtering

        # Execute filtering with service
        result_obj = execute_source_layer_filtering(
            task_parameters=self.task_parameters,
            source_layer=self.source_layer,
            param_source_old_subset=self.param_source_old_subset,
            primary_key_name=self.primary_key_name,
            task_bridge=getattr(self, '_task_bridge', None),
            process_qgis_expression_callback=self._process_qgis_expression,
            combine_with_old_subset_callback=self._combine_with_old_subset,
            apply_filter_and_update_subset_callback=self._apply_filter_and_update_subset,
            build_feature_id_expression_callback=self._build_feature_id_expression
        )

        # Apply results to task instance
        self.expression = result_obj.expression
        if result_obj.is_field_expression:
            self.is_field_expression = result_obj.is_field_expression

        return result_obj.success

    def _initialize_source_subset_and_buffer(self):
        """
        Initialize source subset expression and buffer parameters (v2).

        PHASE 14.5: Migrated to SourceSubsetBufferBuilder service.
        Delegates to build_source_subset_buffer_config() for actual initialization.

        Extracted 163 lines to core/services/source_subset_buffer_builder.py (v5.0-alpha).
        """
        # PHASE 14.5: Delegate to SourceSubsetBufferBuilder service
        from ..services.source_subset_buffer_builder import build_source_subset_buffer_config

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
        from ..services.geometry_preparer import prepare_geometries_by_provider

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
        # Import QgsMessageLog for visible diagnostic logs
        from qgis.core import QgsMessageLog, Qgis as QgisLevel

        # DIAGNOSTIC: Log all layers that will be filtered
        logger.info("=" * 70)
        logger.info("📋 LISTE DES COUCHES À FILTRER GÉOMÉTRIQUEMENT")
        logger.info("=" * 70)
        total_layers = 0
        layer_names_list = []
        for provider_type in self.layers:
            layer_list = self.layers[provider_type]
            logger.debug(f"  Provider: {provider_type} → {len(layer_list)} couche(s)")
            for idx, (layer, layer_props) in enumerate(layer_list, 1):
                logger.info(f"    {idx}. {layer.name()} (id={layer.id()[:8]}...)")
                layer_names_list.append(layer.name())
            total_layers += len(layer_list)
        logger.info(f"  TOTAL: {total_layers} couches à filtrer")
        logger.info("=" * 70)

        # Log to QGIS message panel for visibility
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
            result = self._filter_all_layers_parallel(max_workers)
            return result
        else:
            result = self._filter_all_layers_sequential()
            return result

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

        logger.debug(f"Prepared {len(all_layers)} layers for parallel filtering")

        # Create executor with config
        config = ParallelConfig(
            max_workers=max_workers if max_workers > 0 else None,
            min_layers_for_parallel=1  # Already checked threshold
        )
        executor = ParallelFilterExecutor(config.max_workers)

        # Execute parallel filtering with required task_parameters
        # Include filtering params for OGR detection (thread safety)
        task_parameters = {
            'task': self,
            'filter_type': getattr(self, 'filter_type', 'geometric'),
            'filtering': {
                'filter_type': getattr(self, 'filter_type', 'geometric')
            }
        }
        # Pass cancel_check callback to executor
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
            # Set self.message for proper error display in finished()
            layer_list = ', '.join(failed_layer_names[:3])
            suffix = f' (+{len(failed_layer_names) - 3} more)' if len(failed_layer_names) > 3 else ''
            self.message = f"{failed_filters} layer(s) failed to filter: {layer_list}{suffix}"
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

        logger.debug(f"Processing providers: {list(self.layers.keys())}")
        for provider_type in self.layers:
            logger.debug(f"Provider '{provider_type}' has {len(self.layers[provider_type])} layers")

        for layer_provider_type in self.layers:
            for layer, layer_props in self.layers[layer_provider_type]:
                # Validate layer before any operations
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
                logger.debug(f"🔄 FILTRAGE {i}/{self.layers_count}: {layer_name} ({layer_provider_type})")
                logger.info(f"   Features avant filtre: {layer_feature_count}")

                result = self.execute_geometric_filtering(layer_provider_type, layer, layer_props)

                # Log result VISIBLY for debugging
                logger.info(f"   → execute_geometric_filtering RESULT: {result}")

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
            # Set self.message for proper error display in finished()
            layer_list = ', '.join(failed_layer_names[:3])
            suffix = f' (+{len(failed_layer_names) - 3} more)' if len(failed_layer_names) > 3 else ''
            self.message = f"{failed_filters} layer(s) failed to filter: {layer_list}{suffix}"
            logger.warning(f"⚠️ {failed_filters} layer(s) failed to filter - returning False")
            logger.warning(f"   Failed layers: {', '.join(failed_layer_names[:5])}{'...' if len(failed_layer_names) > 5 else ''}")
            return False
        return True

    def _log_filtering_summary(self, successful_filters: int, failed_filters: int, failed_layer_names=None):
        """Log summary of filtering results. Delegated to core.optimization.logging_utils."""
        from ..optimization.logging_utils import log_filtering_summary
        log_filtering_summary(
            layers_count=self.layers_count, successful_filters=successful_filters,
            failed_filters=failed_filters, failed_layer_names=failed_layer_names, log_to_qgis=True
        )

    def manage_distant_layers_geometric_filtering(self) -> bool:
        """Filter distant layers using source layer geometries.

        Orchestrates the geometric filtering workflow:
        1. Initialize buffer parameters and source subset
        2. Create optimized filter chain MV for PostgreSQL (if applicable)
        3. Prepare source geometries for each backend type
        4. Execute filtering on all distant layers with progress tracking

        Returns:
            True if all distant layers were filtered successfully.

        Note:
            - Supports buffer expressions with MV optimization for large datasets
            - Creates filter chain MV when multiple spatial filters are chained
            - Handles provider-specific geometry preparation (PostgreSQL, Spatialite, OGR)
        """
        logger.info(f"🔍 manage_distant_layers_geometric_filtering: {self.source_layer.name()} (features: {self.source_layer.featureCount()})")
        logger.info(f"  is_field_expression: {getattr(self, 'is_field_expression', None)}")
        logger.info("=" * 60)

        # DIAGNOSTIC COMPLET - ARCHITECTURE FIX 2026-01-16
        logger.info("=" * 80)
        logger.info("🔍 DIAGNOSTIC manage_distant_layers_geometric_filtering")
        logger.info(f"  current_predicates available: {bool(getattr(self, 'current_predicates', None))}")
        if hasattr(self, 'current_predicates') and self.current_predicates:
            logger.info(f"  Active predicates: {list(self.current_predicates.keys())}")
        else:
            logger.warning("  ⚠️ current_predicates NOT yet initialized (may be set later)")
        logger.info("=" * 80)

        # CRITICAL: Initialize source subset and buffer parameters FIRST
        # This sets self.param_buffer_value which is needed by prepare_*_source_geom()
        self._initialize_source_subset_and_buffer()

        # Calculate source_feature_count ONCE and store it for consistent threshold decisions
        # This ensures _ensure_buffer_expression_mv_exists() and prepare_postgresql_source_geom()
        # use the same value (featureCount can vary if subsetString changes between calls)
        self._cached_source_feature_count = self.source_layer.featureCount() if self.source_layer else None
        logger.info(f"  📊 Cached source_feature_count: {self._cached_source_feature_count}")

        # Ensure buffer expression MV exists BEFORE prepare_geometries
        # CRITICAL - Only call MV creation if feature count exceeds threshold
        # When using custom buffer expression with PostgreSQL, the MV must be created BEFORE
        # prepare_postgresql_source_geom() generates the reference to it. Otherwise, the
        # MV won't exist when distant layers try to use it for filtering.
        # HOWEVER: For small datasets (<= 10000), inline buffer is used, so MV creation is skipped.
        # This prevents freeze on 2nd filter when source layer is already filtered.
        from ...adapters.backends.postgresql.filter_executor import BUFFER_EXPR_MV_THRESHOLD
        if (self.param_buffer_expression and
            self.param_source_provider_type == 'postgresql' and
            self._cached_source_feature_count is not None and
                self._cached_source_feature_count > BUFFER_EXPR_MV_THRESHOLD):
            logger.info(f"  🔧 Feature count ({self._cached_source_feature_count}) > threshold ({BUFFER_EXPR_MV_THRESHOLD})")
            logger.info("  → Calling _ensure_buffer_expression_mv_exists()...")
            self._ensure_buffer_expression_mv_exists()
        elif self.param_buffer_expression and self.param_source_provider_type == 'postgresql':
            logger.info(f"  ✓ SKIP MV creation: {self._cached_source_feature_count} features <= {BUFFER_EXPR_MV_THRESHOLD} threshold")
            logger.info("  → Buffer expression will be applied INLINE by prepare_postgresql_source_geom()")

        # Try to create optimized filter chain MV for PostgreSQL
        # When multiple spatial filters are chained (zone_pop AND demand_points etc.),
        # creating a single MV reduces N×M EXISTS queries to 1 EXISTS per distant layer
        if self.param_source_provider_type == 'postgresql':
            self._try_create_filter_chain_mv()

        # Build unique provider list including source layer provider AND forced backends
        # Include forced backends in provider_list
        # Without this, forced backends won't have their source geometry prepared
        provider_list = self.provider_list + [self.param_source_provider_type]

        # Add any forced backends to ensure their geometry is prepared
        forced_backends = self.task_parameters.get('forced_backends', {})
        for layer_id, forced_backend in forced_backends.items():
            if forced_backend and forced_backend not in provider_list:
                logger.debug(f"  → Adding forced backend '{forced_backend}' to provider_list")
                provider_list.append(forced_backend)

        provider_list = list(dict.fromkeys(provider_list))
        logger.info(f"  → Provider list for geometry preparation: {provider_list}")

        # Prepare geometries for all provider types
        # NOTE: This will use self.param_buffer_value set above
        geom_prep_result = self._prepare_geometries_by_provider(provider_list)

        if not geom_prep_result:
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

    def qgis_expression_to_postgis(self, expression: str) -> str:
        """Convert a QGIS expression to PostGIS-compatible SQL.

        Transforms QGIS expression syntax to PostgreSQL/PostGIS SQL, handling:
        - Function name mapping (e.g., $area → ST_Area)
        - Operator conversions
        - Geometry column references

        Args:
            expression: QGIS expression string to convert.

        Returns:
            PostGIS-compatible SQL expression, or original if empty.

        Example:
            >>> task.qgis_expression_to_postgis('$area > 1000')
            'ST_Area("geometry") > 1000'
        """
        if not expression:
            return expression
        geom_col = getattr(self, 'param_source_geom', None) or 'geometry'
        from ..services.expression_service import ExpressionService
        from ..domain.filter_expression import ProviderType
        return ExpressionService().to_sql(expression, ProviderType.POSTGRESQL, geom_col)

    def qgis_expression_to_spatialite(self, expression: str) -> str:
        """Convert a QGIS expression to Spatialite-compatible SQL.

        Transforms QGIS expression syntax to Spatialite SQL, handling:
        - Function name mapping (e.g., $area → ST_Area)
        - Operator conversions
        - Geometry column references

        Args:
            expression: QGIS expression string to convert.

        Returns:
            Spatialite-compatible SQL expression, or original if empty.

        Note:
            Spatialite spatial functions are ~90% compatible with PostGIS.
        """
        if not expression:
            return expression
        geom_col = getattr(self, 'param_source_geom', None) or 'geometry'
        from ..services.expression_service import ExpressionService
        from ..domain.filter_expression import ProviderType
        return ExpressionService().to_sql(expression, ProviderType.SPATIALITE, geom_col)

    def prepare_postgresql_source_geom(self) -> str:
        """Prepare PostgreSQL source geometry with buffer/centroid. Delegated to BackendServices facade.

        Returns:
            str: PostgreSQL geometry expression (e.g., '"schema"."table"."geom"' or buffered variant)
        """
        # Add diagnostic logging to trace PostgreSQL geometry preparation
        logger.info("=" * 60)
        logger.info("🐘 PREPARING PostgreSQL SOURCE GEOMETRY")
        logger.info("=" * 60)
        logger.info(f"   source_schema: {self.param_source_schema}")
        logger.info(f"   source_table: {self.param_source_table}")
        logger.info(f"   source_geom: {self.param_source_geom}")
        logger.info(f"   buffer_value: {getattr(self, 'param_buffer_value', None)}")
        logger.info(f"   buffer_expression: {getattr(self, 'param_buffer_expression', None)}")
        logger.info(f"   use_centroids: {getattr(self, 'param_use_centroids_source_layer', False)}")
        logger.info(f"   session_id: {getattr(self, 'session_id', None)}")
        logger.info(f"   mv_schema: {getattr(self, 'current_materialized_view_schema', 'filter_mate_temp')}")

        # Use cached feature count for consistent threshold decisions
        source_fc = getattr(self, '_cached_source_feature_count', None)
        if source_fc is None:
            # Fallback if not cached (e.g., called from different code path)
            source_fc = self.source_layer.featureCount() if self.source_layer else None
            logger.warning(f"   ⚠️ Using fresh featureCount (not cached): {source_fc}")
        logger.info(f"   source_feature_count: {source_fc} (threshold=10000)")

        result_geom, mv_name = _backend_services.prepare_postgresql_source_geom(
            source_table=self.param_source_table, source_schema=self.param_source_schema,
            source_geom=self.param_source_geom, buffer_value=getattr(self, 'param_buffer_value', None),
            buffer_expression=getattr(self, 'param_buffer_expression', None),
            use_centroids=getattr(self, 'param_use_centroids_source_layer', False),
            buffer_segments=getattr(self, 'param_buffer_segments', 5),
            buffer_type=self.task_parameters.get("filtering", {}).get("buffer_type", "Round"),
            primary_key_name=getattr(self, 'primary_key_name', None),
            session_id=getattr(self, 'session_id', None),  # Pass session_id for MV name prefix
            mv_schema=getattr(self, 'current_materialized_view_schema', 'filter_mate_temp'),  # Pass MV schema
            source_feature_count=source_fc  # Use cached value for consistent threshold
        )
        self.postgresql_source_geom = result_geom
        if mv_name:
            self.current_materialized_view_name = mv_name

        # Log result for debugging
        logger.info(f"   ✓ postgresql_source_geom = '{str(result_geom)[:100]}...'")
        logger.info("=" * 60)

        # CRITICAL - Return the geometry expression!
        # The callback in geometry_preparer.py expects a return value.
        return result_geom

    def _get_optimization_thresholds(self):
        """Get optimization thresholds config. Delegated to core.optimization.config_provider."""
        from ..optimization.config_provider import get_optimization_thresholds
        return get_optimization_thresholds(getattr(self, 'task_parameters', None))

    def _get_simplification_config(self):
        """Get geometry simplification config. Delegated to core.optimization.config_provider."""
        from ..optimization.config_provider import get_simplification_config
        return get_simplification_config(getattr(self, 'task_parameters', None))

    def _get_wkt_precision(self, crs_authid: str = None) -> int:
        """Get appropriate WKT precision based on CRS units. Delegated to BufferService."""
        from ..services.buffer_service import BufferService
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
        from ..services.buffer_service import BufferService, BufferConfig, BufferEndCapStyle
        config = BufferConfig(distance=buffer_value or 0, segments=buffer_segments, end_cap_style=BufferEndCapStyle(buffer_type))
        return BufferService().calculate_buffer_aware_tolerance(config, extent_size, is_geographic)

    def _simplify_geometry_adaptive(self, geometry: Any, max_wkt_length: Optional[int] = None, crs_authid: Optional[str] = None) -> Any:
        """Simplify geometry adaptively. Delegated to BackendServices facade."""

        if not geometry or geometry.isEmpty():
            return geometry

        try:
            adapter = _backend_services.get_geometry_preparation_adapter()
            if adapter is None:
                logger.warning("GeometryPreparationAdapter not available, returning original geometry")
                return geometry

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

    def prepare_spatialite_source_geom(self) -> Optional[str]:
        """Prepare source geometry for Spatialite filtering. Delegated to BackendServices facade.

        Returns:
            str: WKT geometry string, or None if preparation failed
        """
        SpatialiteSourceContext = _backend_services.get_spatialite_source_context_class()
        if SpatialiteSourceContext is None:
            raise ImportError("SpatialiteSourceContext not available")

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

        result = _backend_services.prepare_spatialite_source_geom(context)
        if result.success:
            self.spatialite_source_geom = result.wkt
            if hasattr(self, 'task_parameters') and self.task_parameters:
                if 'infos' not in self.task_parameters:
                    self.task_parameters['infos'] = {}
                self.task_parameters['infos']['source_geom_wkt'] = result.wkt
                self.task_parameters['infos']['buffer_state'] = result.buffer_state
            logger.debug(f"prepare_spatialite_source_geom: WKT length = {len(result.wkt) if result.wkt else 0}")
            logger.info(f"✓ Spatialite source geom prepared: {len(result.wkt)} chars")
            return result.wkt  # FIX: Return WKT string for lambda callback
        else:
            error_msg = result.error_message or "Unknown error"
            logger.error(f"prepare_spatialite_source_geom failed: {error_msg}")
            # FIX 2026-01-16: Also log to QGIS message panel for visibility
            from qgis.core import QgsMessageLog, Qgis
            QgsMessageLog.logMessage(
                f"❌ Spatialite geometry preparation FAILED: {error_msg}",
                "FilterMate", Qgis.Critical
            )
            logger.error("  → This will cause distant layer filtering to fail!")
            logger.error("  → Check if source layer has valid geometry")
            logger.error("  → Check if source layer has features selected or filtered")
            self.spatialite_source_geom = None
            return None  # FIX: Return None to signal failure

    def _copy_filtered_layer_to_memory(self, layer: QgsVectorLayer, layer_name: str = "filtered_copy") -> QgsVectorLayer:
        """Copy filtered layer to memory layer. Delegated to GeometryPreparationAdapter."""
        GeometryPreparationAdapter = _backend_services.get_geometry_preparation_adapter()
        if GeometryPreparationAdapter is None:
            raise Exception("GeometryPreparationAdapter not available")
        result = GeometryPreparationAdapter().copy_filtered_to_memory(layer, layer_name)
        if result.success and result.layer:
            self._verify_and_create_spatial_index(result.layer, layer_name)
            return result.layer
        raise Exception(f"Failed to copy filtered layer: {result.error_message or 'Unknown'}")

    def _copy_selected_features_to_memory(self, layer: QgsVectorLayer, layer_name: str = "selected_copy") -> QgsVectorLayer:
        """Copy selected features to memory layer. Delegated to GeometryPreparationAdapter."""
        GeometryPreparationAdapter = _backend_services.get_geometry_preparation_adapter()
        if GeometryPreparationAdapter is None:
            raise Exception("GeometryPreparationAdapter not available")
        result = GeometryPreparationAdapter().copy_selected_to_memory(layer, layer_name)
        if result.success and result.layer:
            self._verify_and_create_spatial_index(result.layer, layer_name)
            return result.layer
        raise Exception(f"Failed to copy selected features: {result.error_message or 'Unknown'}")

    def _create_memory_layer_from_features(self, features: List[QgsFeature], crs: QgsCoordinateReferenceSystem, layer_name: str = "from_features") -> Optional[QgsVectorLayer]:
        """Create memory layer from QgsFeature objects. Delegated to GeometryPreparationAdapter."""
        GeometryPreparationAdapter = _backend_services.get_geometry_preparation_adapter()
        if GeometryPreparationAdapter is None:
            logger.error("GeometryPreparationAdapter not available")
            return None
        result = GeometryPreparationAdapter().create_memory_from_features(features, crs, layer_name)
        if result.success and result.layer:
            self._verify_and_create_spatial_index(result.layer, layer_name)
            return result.layer
        logger.error(f"_create_memory_layer_from_features failed: {result.error_message or 'Unknown'}")
        return None

    def _convert_layer_to_centroids(self, layer: QgsVectorLayer) -> Optional[QgsVectorLayer]:
        """Convert layer geometries to centroids. Delegated to GeometryPreparationAdapter."""
        GeometryPreparationAdapter = _backend_services.get_geometry_preparation_adapter()
        if GeometryPreparationAdapter is None:
            logger.error("GeometryPreparationAdapter not available")
            return None
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
            from ..geometry import apply_qgis_buffer, BufferConfig
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
        from ..geometry import convert_geometry_collection_to_multipolygon
        return convert_geometry_collection_to_multipolygon(layer)

    def _evaluate_buffer_distance(self, layer, buffer_param):
        """Delegates to core.geometry.buffer_processor.evaluate_buffer_distance()."""
        from ..geometry.buffer_processor import evaluate_buffer_distance

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
        from ..geometry.buffer_processor import create_memory_layer_for_buffer

        return create_memory_layer_for_buffer(layer)

    def _buffer_all_features(self, layer, buffer_dist):
        """Buffer all features from layer. Delegated to core.geometry.buffer_processor."""
        from ..geometry.buffer_processor import buffer_all_features
        segments = getattr(self, 'param_buffer_segments', 5)
        return buffer_all_features(layer, buffer_dist, segments)

    def _dissolve_and_add_to_layer(self, geometries, buffered_layer):
        """Delegates to core.geometry.buffer_processor.dissolve_and_add_to_layer()."""
        from ..geometry.buffer_processor import dissolve_and_add_to_layer
        return dissolve_and_add_to_layer(geometries, buffered_layer, self._verify_and_create_spatial_index)

    def _create_buffered_memory_layer(self, layer, buffer_distance):
        """Delegates to core.geometry.create_buffered_memory_layer()."""
        from ..geometry import create_buffered_memory_layer
        return create_buffered_memory_layer(layer, buffer_distance, self.param_buffer_segments, self._verify_and_create_spatial_index, self._store_warning_message)

    def _aggressive_geometry_repair(self, geom):
        """Delegates to core.geometry.aggressive_geometry_repair()."""
        from ..geometry import aggressive_geometry_repair
        return aggressive_geometry_repair(geom)

    def _repair_invalid_geometries(self, layer):
        """Validate and repair invalid geometries. Delegated to core.geometry."""
        from ..geometry import repair_invalid_geometries
        return repair_invalid_geometries(
            layer=layer,
            verify_spatial_index_fn=self._verify_and_create_spatial_index
        )

    def _simplify_buffer_result(self, layer, buffer_distance):
        """Simplify polygon(s) from buffer operations. Delegated to core.geometry."""
        from ..backends.auto_optimizer import get_auto_optimization_config
        from ..geometry import simplify_buffer_result
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

        # Validate input layer before any operations
        if layer is None:
            logger.error("_apply_buffer_with_fallback: Input layer is None")
            return None

        if not layer.isValid():
            logger.error("_apply_buffer_with_fallback: Input layer is not valid")
            return None

        if layer.featureCount() == 0:
            logger.warning("_apply_buffer_with_fallback: Input layer has no features")
            return None

        result = None

        try:
            # Try QGIS buffer algorithm first
            result = self._apply_qgis_buffer(layer, buffer_distance)

            # Validate result before returning
            if result is None or not result.isValid() or result.featureCount() == 0:
                logger.warning("_apply_qgis_buffer returned invalid/empty result, trying manual buffer")
                raise Exception("QGIS buffer returned invalid result")

        except Exception as e:
            # Fallback to manual buffer
            logger.warning(f"QGIS buffer algorithm failed: {str(e)}, using manual buffer approach")
            try:
                result = self._create_buffered_memory_layer(layer, buffer_distance)

                # Validate result before returning
                if result is None or not result.isValid() or result.featureCount() == 0:
                    logger.error("Manual buffer also returned invalid/empty result")
                    return None

            except Exception as manual_error:
                logger.error(f"Both buffer methods failed. QGIS: {str(e)}, Manual: {str(manual_error)}")
                logger.error("Returning None - buffer operation failed completely")
                return None

        # Apply post-buffer simplification to reduce vertex count
        if result is not None and result.isValid() and result.featureCount() > 0:
            result = self._simplify_buffer_result(result, buffer_distance)

        return result

    def prepare_ogr_source_geom(self):
        """Prepare OGR source geometry with reprojection/buffering. Delegated to ogr_executor."""
        if not OGR_EXECUTOR_AVAILABLE or not hasattr(ogr_executor, 'OGRSourceContext'):
            logger.error("OGR executor not available")
            self.ogr_source_geom = None
            return None
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

        # FIX 2026-01-17: Return the prepared geometry so the callback gets a value
        return self.ogr_source_geom

    def _verify_and_create_spatial_index(self, layer, layer_name=None):
        """Verify/create spatial index on layer. Delegated to core.geometry.spatial_index."""
        from ..geometry.spatial_index import verify_and_create_spatial_index
        return verify_and_create_spatial_index(layer, layer_name)

    def _get_source_reference(self, sub_expression):
        """Determine the source reference for spatial joins (MV or direct table)."""
        if self.current_materialized_view_name:
            # Fm_temp_mv_ prefix for new MVs
            return f'"{self.current_materialized_view_schema}"."fm_temp_mv_{self.current_materialized_view_name}_dump"'
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
            f'(SELECT "{param_distant_table}"."{param_distant_primary_key_name}" '  # nosec B608 - identifiers from QGIS layer metadata (task parameters)
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
        from ..filter.expression_builder import qualify_field_names_in_expression

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

        Phase E13 Step 4: Delegates to SubsetStringBuilder.combine_expressions().

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
        builder = self._get_subset_builder()
        result = builder.combine_expressions(
            new_expression=new_expression,
            old_subset=old_subset,
            combine_operator=combine_operator,
            layer_props=layer_props
        )

        # Handle source MV creation (kept here as it's task-specific)
        # The builder returns optimization info but doesn't create MVs
        if result.optimization_applied:
            try:
                optimizer = get_combined_query_optimizer()
                opt_result = optimizer.optimize_combined_expression(
                    old_subset=self._sanitize_subset_string(old_subset) if old_subset else "",
                    new_expression=new_expression,
                    combine_operator=combine_operator,
                    layer_props=layer_props
                )
                if opt_result.success and hasattr(opt_result, 'source_mv_info') and opt_result.source_mv_info is not None:
                    self._create_source_mv_if_needed(opt_result.source_mv_info)
            except Exception as e:
                logger.debug(f"MV creation skipped: {e}")

        return result.expression

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

            # Register MV references to prevent premature cleanup
            from ...adapters.backends.postgresql.mv_reference_tracker import get_mv_reference_tracker
            tracker = get_mv_reference_tracker()

            # Register references for source layer and all distant layers
            if hasattr(self, 'source_layer') and self.source_layer:
                tracker.add_reference(view_name, self.source_layer.id())

            # Register for all distant layers that will use this source MV
            if hasattr(self, 'param_all_layers'):
                for layer in self.param_all_layers:
                    if layer and hasattr(layer, 'id'):
                        if not self.source_layer or layer.id() != self.source_layer.id():
                            tracker.add_reference(view_name, layer.id())

            elapsed = time.time() - start_time
            fid_count = len(source_mv_info.fid_list)
            logger.info(
                f"✓ v2.9.0: Source MV '{view_name}' created in {elapsed:.2f}s "
                f"({fid_count} FIDs with pre-computed buffer)"
            )
            logger.info("   FIX v4.2.8: Registered references for multiple layers")
            return True

        except Exception as e:
            logger.warning(f"Failed to create source MV '{source_mv_info.view_name}': {e}")
            # Don't raise - the optimization can still work with inline subquery
            return False

    def _ensure_buffer_expression_mv_exists(self):
        """
        FIX v4.2.1 (2026-01-21): Ensure buffer expression MVs exist BEFORE distant layer filtering.
        FIX v4.2.7 (2026-01-22): Only create MVs if feature count exceeds threshold.

        When using custom buffer expression (set to field), this function creates the
        materialized views (mv_<session>_<table>_buffer_expr and mv_<session>_<table>_buffer_expr_dump)
        BEFORE prepare_postgresql_source_geom() generates references to them.

        The problem was:
        - prepare_postgresql_source_geom() generates postgresql_source_geom pointing to MV _dump
        - But the MV was only created when filtering the source layer itself
        - If the source layer was already filtered (re-filtering), the MV didn't exist
        - Distant layers failed with "relation does not exist" error

        The fix:
        - Create the MVs upfront in manage_distant_layers_geometric_filtering()
        - This ensures the MV exists before any reference to it is generated

        FIX v4.2.7: Only create MVs if feature count > BUFFER_EXPR_MV_THRESHOLD (100).
        For small datasets, prepare_postgresql_source_geom() uses inline ST_Buffer() instead
        of referencing MVs, so creating MVs is unnecessary overhead.
        """
        import time
        from ...infrastructure.database.sql_utils import sanitize_sql_identifier
        from ...adapters.backends.postgresql.filter_executor import BUFFER_EXPR_MV_THRESHOLD

        logger.info("=" * 60)
        logger.info("🔧 FIX v4.2.1/v4.2.7: Checking buffer expression MV requirements...")
        logger.info(f"   param_buffer_expression: {self.param_buffer_expression}")
        logger.info(f"   session_id: {self.session_id}")
        logger.info(f"   source_table: {self.param_source_table}")

        # Use cached feature count for consistent threshold decisions
        source_feature_count = getattr(self, '_cached_source_feature_count', None)
        if source_feature_count is None:
            # Fallback if not cached (should not happen in normal flow)
            source_feature_count = self.source_layer.featureCount() if self.source_layer else 0
            logger.warning(f"   ⚠️ Using fresh featureCount (not cached): {source_feature_count}")
        logger.info(f"   source_feature_count: {source_feature_count}")
        logger.info(f"   BUFFER_EXPR_MV_THRESHOLD: {BUFFER_EXPR_MV_THRESHOLD}")

        if source_feature_count is not None and source_feature_count <= BUFFER_EXPR_MV_THRESHOLD:
            logger.info(f"   ✓ SKIP MV creation: {source_feature_count} features <= {BUFFER_EXPR_MV_THRESHOLD} threshold")
            logger.info("   → prepare_postgresql_source_geom() will use INLINE ST_Buffer() instead")
            logger.info("=" * 60)
            return True  # Success - no MV needed

        logger.info(f"   → Creating MV: {source_feature_count} features > {BUFFER_EXPR_MV_THRESHOLD} threshold")
        logger.info("=" * 60)

        start_time = time.time()

        try:
            # Get PostgreSQL connection
            connexion = self._get_valid_postgresql_connection()
            if not connexion:
                logger.warning("No PostgreSQL connection available for buffer expression MV creation")
                return False

            # Generate MV name (must match prepare_postgresql_source_geom logic)
            base_mv_name = sanitize_sql_identifier(self.param_source_table + '_buffer_expr')
            if self.session_id:
                mv_name = f"{self.session_id}_{base_mv_name}"
            else:
                mv_name = base_mv_name
                logger.warning("No session_id - using base MV name (may conflict with other sessions)")

            schema = self.current_materialized_view_schema
            geom_field = self.param_source_geom

            # Get source layer's current subset (the features to include in MV)
            source_subset = self.source_layer.subsetString() if self.source_layer else ""

            # Build the buffer expression for PostGIS
            buffer_expr = self.param_buffer_expression
            if buffer_expr:
                # Convert QGIS expression to PostGIS
                buffer_expr = self.qgis_expression_to_postgis(buffer_expr)
                # Adjust field references to include table name
                if buffer_expr.find('"') == 0 and self.param_source_table not in buffer_expr[:50]:
                    buffer_expr = f'"{self.param_source_table}".' + buffer_expr

            # Build ST_Buffer style parameters
            buffer_type_mapping = {"Round": "round", "Flat": "flat", "Square": "square"}
            buffer_type_str = self.task_parameters.get("filtering", {}).get("buffer_type", "Round")
            endcap_style = buffer_type_mapping.get(buffer_type_str, "round")
            quad_segs = getattr(self, 'param_buffer_segments', 5)
            style_params = f"quad_segs={quad_segs}"
            if endcap_style != 'round':
                style_params += f" endcap={endcap_style}"

            # Build source geometry reference
            f'"{self.param_source_schema}"."{self.param_source_table}"."{geom_field}"'

            # Build WHERE clause for source features
            if source_subset:
                f" WHERE {source_subset}"

            # SQL commands (fm_temp_mv_ prefix)
            sql_drop = f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."fm_temp_mv_{mv_name}_dump" CASCADE;'
            sql_drop_main = f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."fm_temp_mv_{mv_name}" CASCADE;'

            # Create main MV with buffered geometries
            sql_create_main = '''
                CREATE MATERIALIZED VIEW IF NOT EXISTS "{schema}"."fm_temp_mv_{mv_name}" AS
                SELECT
                    "{self.param_source_table}"."{self.primary_key_name}",
                    ST_Buffer({source_geom_ref}, {buffer_expr}, '{style_params}') as {geom_field}
                FROM "{self.param_source_schema}"."{self.param_source_table}"
                {where_clause}
                WITH DATA;
            '''

            # Create dump MV (union of all buffered geometries)
            sql_create_dump = '''
                CREATE MATERIALIZED VIEW IF NOT EXISTS "{schema}"."fm_temp_mv_{mv_name}_dump" AS
                SELECT ST_Union("{geom_field}") as {geom_field}
                FROM "{schema}"."fm_temp_mv_{mv_name}"
                WITH DATA;
            '''

            # Index for main MV
            sql_index = f'CREATE INDEX IF NOT EXISTS idx_{mv_name}_geom ON "{schema}"."fm_temp_mv_{mv_name}" USING GIST ({geom_field});'

            # Ensure temp schema exists
            schema = self._ensure_temp_schema_exists(connexion, schema)

            # Execute commands
            commands = [sql_drop, sql_drop_main, sql_create_main, sql_index, sql_create_dump]
            self._execute_postgresql_commands(connexion, commands)

            # Register MV references to prevent premature cleanup
            from ...adapters.backends.postgresql.mv_reference_tracker import get_mv_reference_tracker
            tracker = get_mv_reference_tracker()

            # Register references for source layer and all distant layers (fm_temp_mv_ prefix)
            if self.source_layer:
                tracker.add_reference(f"fm_temp_mv_{mv_name}", self.source_layer.id())
                tracker.add_reference(f"fm_temp_mv_{mv_name}_dump", self.source_layer.id())

            # Register for all distant layers that will use this MV
            if hasattr(self, 'param_all_layers'):
                for layer in self.param_all_layers:
                    if layer and hasattr(layer, 'id') and layer.id() != (self.source_layer.id() if self.source_layer else None):
                        tracker.add_reference(f"fm_temp_mv_{mv_name}", layer.id())
                        tracker.add_reference(f"fm_temp_mv_{mv_name}_dump", layer.id())

            elapsed = time.time() - start_time
            logger.info(f"✓ FIX v4.2.1: Buffer expression MVs created in {elapsed:.2f}s")
            logger.info(f"   fm_temp_mv_{mv_name} and fm_temp_mv_{mv_name}_dump ready for distant layer filtering")
            logger.info(f"   FIX v4.2.8: Registered references for {len(self.param_all_layers) if hasattr(self, 'param_all_layers') else 1} layer(s)")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to create buffer expression MV: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            # Don't raise - let the original code path try
            return False

    def _try_create_filter_chain_mv(self):
        """
        v4.2.10: Try to create optimized MV for filter chaining.

        When multiple spatial filters are chained (e.g., zone_pop AND demand_points with buffer),
        this creates a single MV containing pre-filtered source features. This reduces
        N×M EXISTS queries to a single EXISTS per distant layer.

        Optimization triggers when:
        - Source layer has an existing subsetString containing EXISTS clause(s)
        - Current filter adds another spatial constraint (buffer or additional EXISTS)
        - At least 2 spatial filters are being combined

        The MV is stored in self._filter_chain_mv_name and used by expression builders.

        v4.2.10b: DISABLED - Feature causes blocking on large datasets.
        Will be re-enabled after adding:
        - Query timeout protection
        - Feature count threshold for spatial_filters tables
        - Configuration option to enable/disable
        """
        # DISABLED - Causes task blocking at 14%
        # The MV creation with complex EXISTS subqueries can take very long on large tables
        # without proper indexes. Need to add timeout and better threshold checks.
        logger.info("=" * 60)
        logger.info("🚀 v4.2.10b: Filter chain MV optimization DISABLED")
        logger.info("   → Feature temporarily disabled to prevent blocking")
        logger.info("   → Will be re-enabled with timeout protection")
        logger.info("=" * 60)
        return False

        # Original code below - keep for reference
        """
        import time

        logger.info("=" * 60)
        logger.info("🚀 v4.2.10: Checking filter chain MV optimization...")

        # Check prerequisites
        source_subset = self.source_layer.subsetString() if self.source_layer else ""
        if not source_subset:
            logger.info("   ✗ No source subset - skipping filter chain optimization")
            logger.info("=" * 60)
            return False

        # Check if source_subset contains EXISTS clauses
        if 'EXISTS' not in source_subset.upper():
            logger.info("   ✗ No EXISTS in source subset - skipping filter chain optimization")
            logger.info("=" * 60)
            return False

        # Check if we're adding another spatial filter
        has_buffer = bool(self.param_buffer_expression or self.param_buffer_value)
        if not has_buffer:
            logger.info("   ✗ No buffer expression - filter chain MV not needed")
            logger.info("=" * 60)
            return False

        logger.info("   ✓ Prerequisites met for filter chain optimization:")
        logger.info("      - source_subset contains EXISTS")
        logger.info(f"      - buffer_expression/value: {self.param_buffer_expression or self.param_buffer_value}")

        start_time = time.time()

        try:
            # Import filter chain optimizer
            from ...adapters.backends.postgresql.filter_chain_optimizer import (
                FilterChainOptimizer,
                FilterChainContext,
                OptimizationStrategy
            )
            from ..filter.expression_combiner import extract_exists_clauses

            # Extract spatial filters from source_subset
            exists_clauses = extract_exists_clauses(source_subset)
            if len(exists_clauses) < 1:
                logger.info("   ✗ Could not extract EXISTS clauses from source subset")
                logger.info("=" * 60)
                return False

            # Build spatial_filters list from extracted EXISTS
            spatial_filters = []
            for clause in exists_clauses:
                spatial_filters.append({
                    'table': clause.get('table', 'unknown'),
                    'schema': clause.get('schema', 'public'),
                    'geom_column': 'geom',  # Default
                    'predicate': 'ST_Intersects',
                    'sql': clause.get('sql')  # Original SQL for reference
                })

            # Add current source layer as another filter (with buffer)
            buffer_val = self.param_buffer_value
            if self.param_buffer_expression:
                # For expression buffers, use average estimate
                buffer_val = 10.0  # Placeholder, actual value from expression

            spatial_filters.append({
                'table': self.param_source_table,
                'schema': self.param_source_schema,
                'geom_column': self.param_source_geom,
                'predicate': 'ST_Intersects',
                'buffer': buffer_val
            })

            logger.info(f"   → Detected {len(spatial_filters)} spatial filters to chain:")
            for i, f in enumerate(spatial_filters):
                buf_str = f" (buffer={f.get('buffer')})" if f.get('buffer') else ""
                logger.info(f"      {i+1}. {f.get('schema')}.{f.get('table')}{buf_str}")

            # Get PostgreSQL connection
            connexion = self._get_valid_postgresql_connection()
            if not connexion:
                logger.warning("   ✗ No PostgreSQL connection for filter chain MV")
                logger.info("=" * 60)
                return False

            # Create filter chain context
            context = FilterChainContext(
                source_schema=self.param_source_schema,
                source_table=self.param_source_table,
                source_geom_column=self.param_source_geom,
                spatial_filters=spatial_filters,
                buffer_value=self.param_buffer_value,
                buffer_expression=self.param_buffer_expression,  # Include dynamic expression
                feature_count_estimate=getattr(self, '_cached_source_feature_count', 0),
                session_id=self.session_id
            )

            # Create optimizer and analyze
            optimizer = FilterChainOptimizer(connexion, self.session_id)
            strategy = optimizer.analyze_chain(context)

            if strategy == OptimizationStrategy.NONE:
                logger.info("   ✗ Optimizer recommends no MV (strategy=NONE)")
                logger.info("=" * 60)
                return False

            # Create chain MV
            mv_name = optimizer.create_chain_mv(context, strategy)

            if mv_name:
                elapsed = time.time() - start_time
                logger.info(f"   ✓ Filter chain MV created: {mv_name}")
                logger.info(f"   ✓ Strategy: {strategy.value}")
                logger.info(f"   ✓ Time: {elapsed:.2f}s")

                # Store for use by expression builders
                self._filter_chain_mv_name = mv_name
                self._filter_chain_optimizer = optimizer
                self._filter_chain_context = context

                # Inject MV name into task_parameters for ExpressionBuilder access
                self.task_parameters['_filter_chain_mv_name'] = mv_name
                logger.info("   ✓ Injected _filter_chain_mv_name into task_parameters")

                logger.info("=" * 60)
                return True
            else:
                logger.warning("   ✗ MV creation failed")
                logger.info("=" * 60)
                return False

        except ImportError as e:
            logger.debug(f"   ✗ Filter chain optimizer not available: {e}")
            logger.info("=" * 60)
            return False
        except Exception as e:
            logger.warning(f"   ✗ Filter chain optimization failed: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            logger.info("=" * 60)
            return False
        """  # End of disabled code block

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
        from ..services.backend_expression_builder import create_expression_builder

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
        from ..filter.expression_combiner import combine_with_old_filter

        old_subset = layer.subsetString() if layer.subsetString() != '' else None

        return combine_with_old_filter(
            new_expression=expression,
            old_subset=old_subset,
            combine_operator=self._get_combine_operator(),
            sanitize_fn=self._sanitize_subset_string
        )

    def execute_geometric_filtering(self, layer_provider_type: str, layer: QgsVectorLayer, layer_props: Dict[str, Any]) -> bool:
        """Execute geometric filtering on a single layer using spatial predicates.

        Applies spatial predicates (intersects, contains, within, etc.) to filter
        features based on their geometric relationship with source layer features.

        Args:
            layer_provider_type: Backend type ('postgresql', 'spatialite', 'ogr').
            layer: The QgsVectorLayer to filter.
            layer_props: Layer properties dict with keys:
                - schema: Database schema (PostgreSQL only)
                - table: Table/layer name
                - primary_key: Primary key field name
                - geometry: Geometry column name

        Returns:
            True if filtering succeeded, False otherwise.

        Raises:
            Logs detailed error to both Python logger and QGIS message panel on failure.

        Note:
            Delegates to FilterOrchestrator for the actual filtering logic.
            Uses lazy initialization to ensure orchestrator is available.
        """
        # DIAGNOSTIC DÉTAILLÉ - ARCHITECTURE FIX 2026-01-16
        logger.info("=" * 70)
        logger.info(f"🎯 execute_geometric_filtering: {layer.name()}")
        logger.debug(f"   Provider: {layer_provider_type}")
        logger.info(f"   Predicates in task: {bool(getattr(self, 'current_predicates', None))}")

        if hasattr(self, 'current_predicates') and self.current_predicates:
            logger.info(f"   Available predicates: {list(self.current_predicates.keys())}")
        else:
            logger.error("❌ current_predicates NOT initialized in task!")
            logger.error("   This should have been set by _initialize_current_predicates()")

        logger.info("=" * 70)

        # Prepare source geometries dict for orchestrator
        source_geometries = {
            'postgresql': getattr(self, 'postgresql_source_geom', None),
            'spatialite': getattr(self, 'spatialite_source_geom', None),
            'ogr': getattr(self, 'ogr_source_geom', None)
        }

        # DIAGNOSTIC: Log source geometries availability
        logger.info("📦 Source geometries prepared:")
        for provider, geom in source_geometries.items():
            if geom is not None:
                geom_type = type(geom).__name__
                if hasattr(geom, 'name'):
                    logger.info(f"   {provider}: {geom_type} - {geom.name()}")
                elif hasattr(geom, '__len__'):
                    logger.info(f"   {provider}: {geom_type} - len={len(geom)}")
                else:
                    logger.info(f"   {provider}: {geom_type}")
            else:
                logger.info(f"   {provider}: None (not prepared)")

        # FIX 2026-01-15: Capture ALL exceptions pour diagnostic
        try:
            # FIX 2026-01-15: Use lazy initialization to ensure orchestrator is always available
            # When filtering distant layers via ParallelFilterExecutor._filter_sequential,
            # the context from TaskRunOrchestrator may not have been processed.
            filter_orchestrator = self._get_filter_orchestrator()
            expression_builder = self._get_expression_builder()

            # Delegate to FilterOrchestrator
            result = filter_orchestrator.orchestrate_geometric_filter(
                layer=layer,
                layer_provider_type=layer_provider_type,
                layer_props=layer_props,
                source_geometries=source_geometries,
                expression_builder=expression_builder
            )
            logger.info(f"✅ orchestrate_geometric_filter returned: {result}")
            return result
        except Exception as e:
            logger.error("=" * 70)
            logger.error("❌ EXCEPTION in execute_geometric_filtering:")
            logger.error(f"   Layer: {layer.name()}")
            logger.error(f"   Provider: {layer_provider_type}")
            logger.error(f"   Exception type: {type(e).__name__}")
            logger.error(f"   Exception message: {str(e)}")
            logger.error("=" * 70)
            import traceback
            full_tb = traceback.format_exc()
            logger.error(f"Full traceback:\n{full_tb}")
            # Afficher AUSSI dans la console QGIS
            from qgis.core import QgsMessageLog, Qgis as QgisLevel
            QgsMessageLog.logMessage(
                f"FilterMate ERROR: {type(e).__name__}: {str(e)}",
                "FilterMate", QgisLevel.Critical
            )
            raise  # Re-raise pour que finished() puisse le capturer

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

        Delegated to BackendServices facade.

        Args:
            source_layer: QgsVectorLayer containing source geometry

        Returns:
            QgsVectorLayer: Simplified source layer (may be new memory layer)
        """
        return _backend_services.simplify_source_for_ogr_fallback(source_layer, logger=logger)

    def _prepare_source_geometry(self, layer_provider_type):
        """Prepare source geometry expression based on provider type (PostgreSQL→SQL/WKT, Spatialite→WKT, OGR→QgsVectorLayer)."""
        # PostgreSQL backend needs SQL expression
        if layer_provider_type == PROVIDER_POSTGRES and POSTGRESQL_AVAILABLE:
            # Log which path is taken
            logger.info("🔍 _prepare_source_geometry(PROVIDER_POSTGRES)")
            logger.info(f"   postgresql_source_geom exists: {hasattr(self, 'postgresql_source_geom')}")
            if hasattr(self, 'postgresql_source_geom'):
                logger.info(f"   postgresql_source_geom truthy: {bool(self.postgresql_source_geom)}")
                if self.postgresql_source_geom:
                    logger.info(f"   postgresql_source_geom preview: '{str(self.postgresql_source_geom)[:100]}...'")

            # Only use postgresql_source_geom if source is also PostgreSQL
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
                    logger.info("   → Returning postgresql_source_geom (table reference)")
                    return self.postgresql_source_geom
                else:
                    logger.warning("   → postgresql_source_geom NOT available, will use WKT fallback!")
            else:
                # Source is NOT PostgreSQL (OGR, Spatialite, etc.)
                # Must use WKT mode - DO NOT use postgresql_source_geom even if set
                # because it would contain invalid table references
                logger.debug(f"PostgreSQL target but source is {self.param_source_provider_type} - using WKT mode")

            # Fallback: try WKT for PostgreSQL (works with ST_GeomFromText)
            if hasattr(self, 'spatialite_source_geom') and self.spatialite_source_geom:
                if not source_is_postgresql:
                    logger.info("Using WKT (spatialite_source_geom) for PostgreSQL filtering")
                else:
                    logger.warning("PostgreSQL source geom not available, using WKT fallback")
                return self.spatialite_source_geom

        # Spatialite backend needs WKT string
        if layer_provider_type == PROVIDER_SPATIALITE:
            if hasattr(self, 'spatialite_source_geom') and self.spatialite_source_geom:
                return self.spatialite_source_geom
            # Generate WKT from OGR source if available
            if hasattr(self, 'ogr_source_geom') and self.ogr_source_geom:
                logger.warning("Spatialite source geom not available, generating WKT from OGR layer")
                try:
                    if isinstance(self.ogr_source_geom, QgsVectorLayer):
                        all_geoms = []
                        # Add cancellation check during feature iteration
                        cancel_check_interval = 100
                        for i, feature in enumerate(self.ogr_source_geom.getFeatures()):
                            # Periodic cancellation check
                            if i > 0 and i % cancel_check_interval == 0:
                                if self.isCanceled():
                                    logger.info(f"WKT generation canceled at {i} features")
                                    return None
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
            logger.warning("Using source layer as last resort fallback")
            return self.source_layer

        logger.error(f"No source geometry available for provider '{layer_provider_type}'")
        return None

    def execute_filtering(self) -> bool:
        """Execute the complete filtering workflow.

        Orchestrates filtering in two steps:
        1. Filter the source layer using attribute/expression criteria
        2. Filter distant layers using geometric predicates (intersects, within, etc.)

        The source layer filter must succeed before distant layers are processed.
        If no geometric predicates are configured, only the source layer is filtered.

        Returns:
            True if filtering completed successfully, False otherwise.

        Raises:
            Sets self.message with user-friendly error description on failure.

        Note:
            - Initializes current_predicates early for ExpressionBuilder
            - Supports selection modes: single, multiple, expression, all features
            - Progress is reported via setProgress()
        """
        # FIX 2026-01-16: Initialize current_predicates EARLY
        # current_predicates must be populated BEFORE execute_source_layer_filtering()
        # because ExpressionBuilder and FilterOrchestrator need them during lazy init.
        # Previously, predicates were only set in STEP 2/2 (distant layers), causing
        # EMPTY predicates warnings during source layer filtering.
        self._initialize_current_predicates()

        # STEP 1/2: Filtering SOURCE LAYER

        logger.info("=" * 60)
        logger.info("STEP 1/2: Filtering SOURCE LAYER")
        logger.info("=" * 60)

        # Déterminer le mode de sélection actif
        features_list = self.task_parameters["task"]["features"]
        qgis_expression = self.task_parameters["task"]["expression"]
        skip_source_filter = self.task_parameters["task"].get("skip_source_filter", False)

        # DIAGNOSTIC 2026-01-28: Log features details
        logger.info(f"  features_list count: {len(features_list) if features_list else 0}")
        logger.info(f"  features_list type: {type(features_list)}")
        if features_list and len(features_list) > 0:
            logger.info(f"  features_list[0] type: {type(features_list[0])}")
            logger.info(f"  features_list[0]: {features_list[0]}")
        logger.info(f"  qgis_expression: '{qgis_expression}'")
        logger.info(f"  skip_source_filter: {skip_source_filter}")

        if len(features_list) > 0 and features_list[0] != "":
            if len(features_list) == 1:
                logger.info("✓ Selection Mode: SINGLE SELECTION")
                logger.info("  → 1 feature selected")
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
            logger.info("  → No source filter will be applied")
            logger.info("  → All features from source layer will be used for geometric predicates")
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
        logger.info("✓ SUCCESS: Source layer filtered")
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

        # FIX 2026-01-17: Enhanced console diagnostic for distant layers filtering

        has_geom_predicates = self.task_parameters["filtering"]["has_geometric_predicates"]
        has_layers_to_filter = self.task_parameters["filtering"]["has_layers_to_filter"]
        has_layers_in_params = len(self.task_parameters['task'].get('layers', [])) > 0
        for prov_type, layer_list in (self.layers or {}).items():
            pass  # print statements removed

        # Log to QGIS message panel for visibility
        from qgis.core import QgsMessageLog, Qgis as QgisLevel

        logger.info("\n🔍 Checking if distant layers should be filtered...")
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

        # Log conditions to QGIS message panel for debugging
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

                # FIX 2026-01-16: current_predicates is already initialized at start of execute_filtering()
                # Just log for confirmation
                logger.info(f"  → Using pre-initialized predicates: {self.current_predicates}")

                logger.info("\n🚀 Calling manage_distant_layers_geometric_filtering()...")

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
                            layers_str = f"{', '.join(failed_names[:3])} (+{len(failed_names) - 3} others)"
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

    def execute_unfiltering(self) -> bool:
        """Remove all filters from source and selected remote layers.

        Clears filters completely by setting subsetString to empty for:
        - The source/current layer
        - All selected remote layers (layers_to_filter)

        Returns:
            True if all filter clears were queued successfully.

        Note:
            - This is NOT the same as undo - it removes filters entirely
            - Use the undo button to restore previous filter state
            - All setSubsetString calls are queued for main thread execution
            - Progress is reported via setProgress()
        """
        logger.info("=" * 60)
        logger.info("FilterMate: UNFILTERING - Clearing all filters")
        logger.info("=" * 60)

        # Queue filter clear on source layer (will be applied in finished())
        self._queue_subset_string(self.source_layer, '')
        logger.info(f"  → Queued clear on source: {self.source_layer.name()}")

        # Queue filter clear on all selected associated layers
        # FIX 2026-01-15: Protect against division by zero when no layers selected
        i = 1
        if self.layers_count > 0:
            self.setProgress((i / self.layers_count) * 100)

        for layer_provider_type in self.layers:
            logger.debug(f"  → Processing {len(self.layers[layer_provider_type])} {layer_provider_type} layer(s)")
            for layer, layer_props in self.layers[layer_provider_type]:
                self._queue_subset_string(layer, '')
                logger.info(f"    → Queued clear on: {layer.name()}")
                i += 1
                if self.layers_count > 0:
                    self.setProgress((i / self.layers_count) * 100)
                if self.isCanceled():
                    logger.warning("FilterMate: Unfilter canceled by user")
                    return False

        logger.info("=" * 60)
        logger.info(f"✓ FilterMate: Unfilter queued for {i} layer(s)")
        logger.info("=" * 60)

        return True

    def execute_reseting(self) -> bool:
        """Reset all layers to their original/saved subset state.

        Restores the initial filter state for all configured layers by:
        - Looking up saved subset strings in the filter history database
        - Applying the original subset to each layer via manage_layer_subset_strings()

        Returns:
            True if reset completed successfully, False if canceled.

        Note:
            - Progress is reported via setProgress()
            - Can be canceled by user (isCanceled() check)
        """
        logger.info("=" * 60)
        logger.info("FilterMate: RESETTING all layers to saved state")
        logger.info("=" * 60)

        i = 1

        logger.info(f"  → Resetting source layer: {self.source_layer.name()}")
        self.manage_layer_subset_strings(self.source_layer)
        # FIX 2026-01-15: Protect against division by zero when no layers selected
        if self.layers_count > 0:
            self.setProgress((i / self.layers_count) * 100)

        for layer_provider_type in self.layers:
            logger.debug(f"  → Processing {len(self.layers[layer_provider_type])} {layer_provider_type} layer(s)")
            for layer, layer_props in self.layers[layer_provider_type]:
                logger.info(f"    → Resetting: {layer.name()}")
                self.manage_layer_subset_strings(layer)
                i += 1
                self.setProgress((i / self.layers_count) * 100)
                if self.isCanceled():
                    logger.warning("FilterMate: Reset canceled by user")
                    return False

        logger.info("=" * 60)
        logger.info(f"✓ FilterMate: Reset completed for {i} layer(s)")
        logger.info("=" * 60)
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
        from ..export import validate_export_parameters

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
        from ..export import save_layer_style

        save_layer_style(layer, output_path, style_format, datatype)

    def _save_layer_style_lyrx(self, layer, output_path):
        """Delegates to core.export.StyleExporter for LYRX format."""
        from ..export.style_exporter import StyleExporter, StyleFormat

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

    def execute_exporting(self) -> bool:
        """Export selected layers to various formats.

        Supports multiple export modes:
        - Standard: Single file with all layers (GPKG, GeoJSON)
        - Batch folder: One file per layer in output folder
        - Batch ZIP: One ZIP archive per layer
        - Streaming: Memory-efficient export for large datasets

        Returns:
            True if export completed successfully, False otherwise.

        Note:
            - Delegates to BatchExporter and LayerExporter (v4.0 E11.2)
            - Supports style export in QML/SLD formats
            - Sets self.message with result summary or error details
            - Progress is reported via setProgress()
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
        from ..export import BatchExporter, LayerExporter, sanitize_filename
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
                        logger.debug(f"Ignored in makedirs for export output: {e}")
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
            from ..export import ExportConfig
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
        from ...infrastructure.utils import get_spatialite_datasource_from_layer

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
        return _backend_services.apply_spatialite_subset(
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
        return _backend_services.manage_spatialite_subset(
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
        return _backend_services.get_last_subset_info(cur, layer, self.project_uuid)

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
                "Filtering may take longer. For optimal performance with large datasets, consider using PostgreSQL."
            )

    def _create_simple_materialized_view_sql(self, schema: str, name: str, sql_subset_string: str) -> str:
        """Delegated to BackendServices facade."""
        return _backend_services.create_simple_materialized_view_sql(schema, name, sql_subset_string)

    def _parse_where_clauses(self) -> Any:
        """Delegated to BackendServices facade."""
        return _backend_services.parse_case_to_where_clauses(self.where_clause)

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

        # Use source layer subset for buffer MV filtering
        #
        # Problem: When creating buffer MV, sql_subset_string contains the SELECT for
        #          the DISTANT layer filter, not the SOURCE layer filter.
        #          This causes buffer MV to ignore existing source layer filters (e.g., zone_pop selection).
        #
        # Solution: Use source_layer.subsetString() to filter the buffer MV instead.
        #           This ensures the buffer MV respects existing source layer filtering.
        #
        # Example scenario:
        #   1. User filters ducts by zone_pop (5 UUIDs selected)
        #   2. User launches new filter with buffer_expression from ducts (already filtered)
        #   3. Buffer MV should use zone_pop filter, not ducts filter
        #
        source_filter_for_mv = sql_subset_string
        if self.source_layer and self.source_layer.subsetString():
            source_subset = self.source_layer.subsetString()
            logger.info("🎯 Buffer MV: Using source layer subset for filtering")
            logger.info(f"   Source subset preview: {source_subset[:200]}...")

            # FIX: Use source subset as-is if it's a valid SELECT statement
            if 'SELECT' in source_subset.upper():
                source_filter_for_mv = source_subset
                logger.info("   Using source layer SELECT statement for buffer MV")  # nosec B608 - false positive: logger statement, no SQL execution
            else:
                # Fallback: source_subset is a WHERE clause, wrap it in SELECT
                source_filter_for_mv = (
                    f'(SELECT "{self.param_source_table}"."{self.primary_key_name}" '  # nosec B608 - identifiers from QGIS layer metadata (task parameters)
                    f'FROM "{self.param_source_schema}"."{self.param_source_table}" '
                    f'WHERE {source_subset})'
                )
                logger.info("   Wrapped source WHERE clause in SELECT for buffer MV")  # nosec B608 - false positive: logger statement, no SQL execution
        else:
            logger.debug("   Buffer MV: No source layer subset, using sql_subset_string")

        template = '''CREATE MATERIALIZED VIEW IF NOT EXISTS "{schema}"."fm_temp_mv_{name}" TABLESPACE pg_default AS
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
            source_new_subset=source_filter_for_mv,
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
        result = _backend_services.ensure_temp_schema_exists(connexion, schema_name)

        # Track schema error for instance state if fallback occurred
        if result == 'public' and schema_name != 'public':
            self._last_schema_error = f"Using 'public' schema as fallback (could not create '{schema_name}')"

        return result

    def _get_session_prefixed_name(self, base_name: str) -> str:
        """
        Generate a session-unique materialized view name.

        Delegated to BackendServices facade.
        """
        return _backend_services.get_session_prefixed_name(base_name, self.session_id)

    def _cleanup_session_materialized_views(self, connexion: Any, schema_name: str) -> Any:
        """
        Clean up all materialized views for the current session.

        Delegated to BackendServices facade.
        """
        # Strangler Fig: Delegate to extracted module (pg_executor or facade)
        if PG_EXECUTOR_AVAILABLE and pg_executor:
            return pg_executor.cleanup_session_materialized_views(
                connexion, schema_name, self.session_id
            )

        # Fallback to facade
        return _backend_services.cleanup_session_materialized_views(connexion, schema_name, self.session_id)

    def _cleanup_orphaned_materialized_views(self, connexion: Any, schema_name: str, max_age_hours: int = 24) -> Any:
        """
        Clean up orphaned materialized views older than max_age_hours.

        Delegated to BackendServices facade.
        """
        return _backend_services.cleanup_orphaned_materialized_views(connexion, schema_name, self.session_id, max_age_hours)

    def _execute_postgresql_commands(self, connexion: Any, commands: List[str]) -> bool:
        """
        Execute PostgreSQL commands with automatic reconnection on failure.

        Delegated to BackendServices facade.

        Args:
            connexion: psycopg2 connection
            commands: List of SQL commands to execute

        Returns:
            bool: True if all commands succeeded
        """
        # Test connection and reconnect if needed
        try:
            with connexion.cursor() as cursor:
                cursor.execute("SELECT 1")
        except (psycopg2.OperationalError, psycopg2.InterfaceError, AttributeError) as e:
            logger.debug(f"PostgreSQL connection test failed, reconnecting: {e}")
            connexion, _ = get_datasource_connexion_from_layer(self.source_layer)

        return _backend_services.execute_commands(connexion, commands)

    def _ensure_source_table_stats(self, connexion: Any, schema: str, table: str, geom_field: str) -> bool:
        """
        Ensure PostgreSQL statistics exist for source table geometry column.

        Delegated to BackendServices facade.

        Args:
            connexion: psycopg2 connection
            schema: Schema name
            table: Table name
            geom_field: Geometry column name

        Returns:
            bool: True if stats were verified/created
        """
        return _backend_services.ensure_table_stats(connexion, schema, table, geom_field)

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

        # Use prepared statement if available (best performance)
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
                logger.warning(f"Prepared statement failed, falling back to repository: {e}")

        # EPIC-1 E4-S9: Use centralized HistoryRepository instead of direct SQL
        history_repo = HistoryRepository(conn, cur)
        try:
            source_layer_id = self.source_layer.id() if self.source_layer else ''
            return history_repo.insert(
                project_uuid=self.project_uuid,
                layer_id=layer.id(),
                subset_string=sql_subset_string,
                seq_order=seq_order,
                source_layer_id=source_layer_id
            )
        finally:
            history_repo.close()

    def _filter_action_postgresql(self, layer, sql_subset_string, primary_key_name, geom_key_name, name, custom, cur, conn, seq_order):
        """
        Execute filter action using PostgreSQL backend.

        EPIC-1 Phase E5/E6: Delegates to adapters.backends.postgresql.filter_actions.

        TODO v5.0: Refactor to use self._get_backend_executor() with FilterExecutorPort
                   instead of direct pg_execute_filter import. This will complete the
                   hexagonal architecture compliance for filter execution.

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

        Delegated to core.tasks.builders.subset_string_builder.SubsetStringBuilder.extract_where_clause().
        """
        from .builders.subset_string_builder import SubsetStringBuilder

        # extract_where_clause is a static method that returns (sql_before_where, where_clause)
        _, where_clause = SubsetStringBuilder.extract_where_clause(sql_select)
        return where_clause

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

        # EPIC-1 E4-S9: Use centralized HistoryRepository instead of duplicated SQL
        history_repo = HistoryRepository(conn, cur)
        try:
            if self._ps_manager:
                try:
                    self._ps_manager.delete_subset_history(self.project_uuid, layer.id())
                except Exception as e:
                    logger.warning(f"Prepared statement failed, falling back to repository: {e}")
                    history_repo.delete_for_layer(self.project_uuid, layer.id())
            else:
                # Use repository instead of direct SQL
                history_repo.delete_for_layer(self.project_uuid, layer.id())
        finally:
            history_repo.close()

        # Drop temp table from filterMate_db using session-prefixed name (fm_temp_ prefix)
        import sqlite3
        session_name = self._get_session_prefixed_name(name)
        try:
            temp_conn = sqlite3.connect(self.db_file_path)
            temp_cur = temp_conn.cursor()
            # Try to drop both new (fm_temp_) and legacy (mv_) tables
            temp_cur.execute(f"DROP TABLE IF EXISTS fm_temp_{session_name}")  # nosec B608 - session_name from _get_session_prefixed_name() (internal hash-based generation, SpatiaLite: no sql.Identifier equivalent)
            temp_cur.execute(f"DROP TABLE IF EXISTS mv_{session_name}")  # nosec B608 - session_name from _get_session_prefixed_name() (internal hash-based generation, SpatiaLite: no sql.Identifier equivalent)
            temp_conn.commit()
            temp_cur.close()
            temp_conn.close()
        except Exception as e:
            logger.error(f"Error dropping Spatialite temp table: {e}")

        # THREAD SAFETY: Queue subset clear for application in finished()
        self._queue_subset_string(layer, '')
        return True

    def _reset_action_ogr(self, layer, name, cur, conn):
        """
        Execute reset action using OGR backend.

        EPIC-1 Phase E4-S8: OGR-specific reset with temp layer cleanup.

        Args:
            layer: QgsVectorLayer to reset
            name: Layer identifier
            cur: Database cursor (for history)
            conn: Database connection (for history)

        Returns:
            bool: True if successful
        """
        logger.info("Reset - OGR backend")

        # EPIC-1 E4-S9: Use centralized HistoryRepository instead of duplicated SQL
        history_repo = HistoryRepository(conn, cur)
        try:
            if self._ps_manager:
                try:
                    self._ps_manager.delete_subset_history(self.project_uuid, layer.id())
                except Exception as e:
                    logger.warning(f"Prepared statement failed, falling back to repository: {e}")
                    history_repo.delete_for_layer(self.project_uuid, layer.id())
            else:
                # Use repository instead of direct SQL
                history_repo.delete_for_layer(self.project_uuid, layer.id())
        finally:
            history_repo.close()

        # Use OGR-specific reset function if available
        if ogr_execute_reset:
            return ogr_execute_reset(
                layer=layer,
                queue_subset_func=self._queue_subset_string,
                cleanup_temp_layers=True
            )

        # Fallback: simple subset clear
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

        # Determine if this is OGR or Spatialite
        provider_type = detect_layer_provider_type(layer)
        if provider_type == PROVIDER_OGR and ogr_execute_unfilter:
            return self._unfilter_action_ogr(
                layer, cur, conn, last_subset_id
            )

        # Spatialite path (also used as fallback for OGR without ogr_execute_unfilter)
        return self._unfilter_action_spatialite(
            layer, primary_key_name, geom_key_name, name, custom,
            cur, conn, last_subset_id
        )

    def _unfilter_action_ogr(self, layer, cur, conn, last_subset_id):
        """
        Unfilter implementation for OGR backend.

        EPIC-1 Phase E4-S8: OGR-specific unfilter.

        Args:
            layer: QgsVectorLayer to unfilter
            cur: Database cursor (for history)
            conn: Database connection (for history)
            last_subset_id: Last subset ID to remove

        Returns:
            bool: True if successful
        """
        # EPIC-1 E4-S9: Use centralized HistoryRepository instead of duplicated SQL
        history_repo = HistoryRepository(conn, cur)
        try:
            # Delete last subset from history
            if last_subset_id:
                history_repo.delete_entry(self.project_uuid, layer.id(), last_subset_id)

            # Get previous subset using repository
            last_entry = history_repo.get_last_entry(self.project_uuid, layer.id())
        finally:
            history_repo.close()

        previous_subset = None

        if last_entry:
            previous_subset = last_entry.subset_string

            # Validate previous subset
            if not previous_subset or not previous_subset.strip():
                logger.warning(
                    f"Unfilter OGR: Previous subset from history is empty for {layer.name()}. "
                    "Clearing layer filter."
                )
                previous_subset = None

        # Use OGR-specific unfilter function
        if ogr_execute_unfilter:
            return ogr_execute_unfilter(
                layer=layer,
                previous_subset=previous_subset,
                queue_subset_func=self._queue_subset_string
            )

        # Fallback: direct subset application
        self._queue_subset_string(layer, previous_subset or '')
        return True

    def _unfilter_action_spatialite(self, layer, primary_key_name, geom_key_name, name, custom, cur, conn, last_subset_id):
        """Unfilter implementation for Spatialite backend."""
        # EPIC-1 E4-S9: Use centralized HistoryRepository instead of duplicated SQL
        history_repo = HistoryRepository(conn, cur)
        try:
            # Delete last subset from history
            if last_subset_id:
                history_repo.delete_entry(self.project_uuid, layer.id(), last_subset_id)

            # Get previous subset using repository
            last_entry = history_repo.get_last_entry(self.project_uuid, layer.id())
        finally:
            history_repo.close()

        if last_entry:
            sql_subset_string = last_entry.subset_string

            # CRITICAL FIX: Validate sql_subset_string from history before using
            if not sql_subset_string or not sql_subset_string.strip():
                logger.warning(
                    f"Unfilter: Previous subset string from history is empty for {layer.name()}. "
                    "Clearing layer filter."
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
        with self._safe_spatialite_connect() as conn:
            self.active_connections.append(conn)
            cur = conn.cursor()

            try:
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
                            "sql_subset_string is empty. Filter was applied via setSubsetString but "
                            "history/materialized view creation is skipped."
                        )
                        return True

                    # Use Spatialite backend for local layers
                    if use_spatialite:
                        backend_name = "Spatialite" if provider_type == PROVIDER_SPATIALITE else "Local (OGR)"
                        logger.debug(f"Using {backend_name} backend")
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
                    # EPIC-1 Phase E4-S8: Distinguish OGR from Spatialite
                    if use_postgresql:
                        return self._reset_action_postgresql(layer, name, cur, conn)
                    elif provider_type == PROVIDER_OGR:
                        return self._reset_action_ogr(layer, name, cur, conn)
                    elif use_spatialite:
                        return self._reset_action_spatialite(layer, name, cur, conn)

                elif self.task_action == 'unfilter':
                    return self._unfilter_action(
                        layer, primary_key_name, geom_key_name, name, custom,
                        cur, conn, last_subset_id, use_postgresql, use_spatialite
                    )

                return True

            finally:
                # Always cleanup cursor and bookkeeping
                try:
                    cur.close()
                except Exception as e:
                    logger.debug(f"Could not close database cursor: {e}")
                if conn in self.active_connections:
                    self.active_connections.remove(conn)
                # Reset prepared statements manager when connection closes
                # to avoid "Cannot operate on a closed database" errors
                self._ps_manager = None

    def _has_expensive_spatial_expression(self, sql_string: str) -> bool:
        """
        Detect if a SQL expression contains expensive spatial predicates.

        EPIC-1 Phase E7.5: Legacy code removed - fully delegates to core.optimization.query_analyzer.
        """
        from ..optimization.query_analyzer import has_expensive_spatial_expression
        return has_expensive_spatial_expression(sql_string)

    def _is_complex_filter(self, subset: str, provider_type: str) -> bool:
        """
        Check if a filter expression is complex (requires longer refresh delay).

        EPIC-1 Phase E7.5: Legacy code removed - fully delegates to core.optimization.query_analyzer.
        """
        from ..optimization.query_analyzer import is_complex_filter
        return is_complex_filter(subset, provider_type)

    def _single_canvas_refresh(self):
        """
        Perform a single comprehensive canvas refresh (v2).

        PHASE 14.8: Migrated to CanvasRefreshService.
        Delegates to single_canvas_refresh() for actual refresh logic.

        Extracted 138 lines to core/services/canvas_refresh_service.py (v5.0-alpha).
        """
        from ..services.canvas_refresh_service import single_canvas_refresh
        single_canvas_refresh()

    def _delayed_canvas_refresh(self):
        """
        Perform a delayed canvas refresh (v2).

        PHASE 14.8: Migrated to CanvasRefreshService.
        Delegates to delayed_canvas_refresh() for actual refresh logic.

        Extracted 112 lines to core/services/canvas_refresh_service.py (v5.0-alpha).
        """
        from ..services.canvas_refresh_service import delayed_canvas_refresh
        delayed_canvas_refresh()

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

        Note: iface imported locally to prevent accidental use from worker thread.
        """
        from qgis.utils import iface
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
                except Exception as e:
                    logger.debug(f"Ignored in final canvas repaint loop: {e}")

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

        FIX v4.2.8 (2026-01-21): Use reference tracker to prevent premature MV cleanup.
        When filtering multiple layers, a shared MV (e.g., temp_buffered_demand_points_xxx)
        may be referenced by multiple layers. Only drop MVs when no layers reference them.
        """
        if not POSTGRESQL_AVAILABLE:
            return

        try:
            # Only cleanup if source layer is PostgreSQL
            if self.param_source_provider_type != 'postgresql':
                return

            # Import reference tracker
            from ...adapters.backends.postgresql.mv_reference_tracker import get_mv_reference_tracker

            # Get layer IDs from task (layers being filtered)
            layer_ids = []

            # Add source layer ID
            if hasattr(self, 'source_layer') and self.source_layer:
                layer_ids.append(self.source_layer.id())
            elif 'source_layer' in self.task_parameters:
                source_layer = self.task_parameters['source_layer']
                if source_layer:
                    layer_ids.append(source_layer.id())

            # Add distant layer IDs
            if hasattr(self, 'param_all_layers'):
                for layer in self.param_all_layers:
                    if layer and hasattr(layer, 'id'):
                        layer_ids.append(layer.id())

            if not layer_ids:
                logger.debug("No layer IDs available for PostgreSQL MV cleanup")
                return

            # Remove references for these layers and get MVs that can be dropped
            tracker = get_mv_reference_tracker()
            mvs_to_drop = set()

            for layer_id in layer_ids:
                can_drop = tracker.remove_all_references_for_layer(layer_id)
                mvs_to_drop.update(can_drop)

            if not mvs_to_drop:
                logger.debug(
                    "PostgreSQL MV cleanup: All MVs still referenced by other layers "
                    f"(removed references for {len(layer_ids)} layer(s))"
                )
                return

            # Actually drop MVs that have no more references
            logger.info(
                f"PostgreSQL MV cleanup: Dropping {len(mvs_to_drop)} MV(s) "
                "with no remaining references"
            )

            # Get PostgreSQL connection and drop MVs
            connexion = self._get_valid_postgresql_connection()
            if not connexion:
                logger.warning("No PostgreSQL connection for MV cleanup")
                return

            cursor = connexion.cursor()
            schema = getattr(self, 'current_materialized_view_schema', 'filtermate_temp')

            for mv_name in mvs_to_drop:
                try:
                    # Extract just the view name if it's fully qualified
                    if '.' in mv_name:
                        mv_name = mv_name.split('.')[-1].strip('"')

                    drop_sql = f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."{mv_name}" CASCADE;'
                    cursor.execute(drop_sql)
                    logger.debug(f"Dropped MV: {schema}.{mv_name}")
                except Exception as e:
                    logger.warning(f"Failed to drop MV {mv_name}: {e}")

            connexion.commit()
            logger.debug(f"PostgreSQL MV cleanup completed: dropped {len(mvs_to_drop)} MV(s)")

        except Exception as e:
            # Non-critical error - log but don't fail the task
            logger.debug(f"Error during PostgreSQL MV cleanup: {e}")

    def cancel(self) -> None:
        """Cancel the task and cleanup all resources.

        Performs cleanup in the following order:
        1. Cleanup PostgreSQL materialized views created during filtering
        2. Close all active database connections
        3. Reset prepared statements manager
        4. Log cancellation (Python logger only, not QgsMessageLog)
        5. Call parent cancel()

        Note:
            Uses Python logger instead of QgsMessageLog to prevent Windows
            access violation during QGIS shutdown (v2.8.7 crash fix).
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
        # Reset prepared statements manager when connections close
        self._ps_manager = None

        # Use Python logger only, NOT QgsMessageLog
        # QgsMessageLog may be destroyed during QGIS shutdown, causing access violation
        try:
            logger.info(f'"{self.description()}" task was canceled')
        except Exception:
            pass  # Logger may be destroyed during QGIS shutdown - intentional silent catch

        super().cancel()

    def _restore_source_layer_selection(self):
        """
        v2.9.23: Restore the source layer selection after filter/unfilter.

        This ensures the selected features remain visually highlighted on the map
        after the filtering operation completes.

        Phase E13 Step 5: Uses FeatureCollector.restore_layer_selection().
        """
        if not self.source_layer or not is_valid_layer(self.source_layer):
            return

        # Phase E13: Use FeatureCollector for centralized feature management
        collector = self._get_feature_collector()

        # Get feature FIDs from task parameters
        feature_fids = self.task_parameters.get("task", {}).get("feature_fids", [])

        # Fallback: extract FIDs from features list if feature_fids not available
        if not feature_fids:
            task_features = self.task_parameters.get("task", {}).get("features", [])
            if task_features:
                # Use collector to extract IDs
                result = collector.collect_from_features(task_features)
                feature_fids = result.feature_ids

        if feature_fids:
            # Delegate selection restoration to FeatureCollector
            collector.restore_layer_selection(feature_fids)
            logger.info(f"✓ Restored source layer selection via FeatureCollector: {len(feature_fids)} feature(s)")

    @main_thread_only
    def finished(self, result: Optional[bool]) -> None:
        """Handle task completion with cleanup and user notifications.

        Called by QGIS task manager when task completes. Performs:
        1. Display warning messages collected during task execution
        2. Apply pending subset string requests on main Qt thread
        3. Cleanup PostgreSQL materialized views (for reset/unfilter/export only)
        4. Show success/error message in QGIS message bar
        5. Restore source layer selection

        Args:
            result: True if task succeeded, False if failed, None if canceled.

        Note:
            - Subset strings are applied here for thread safety
            - MVs are NOT cleaned on 'filter' action as they're still referenced
            - Warning messages are displayed before being cleared
        """
        from qgis.utils import iface
        result_action: Optional[str] = None
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

        # Apply pending subset strings on main thread
        # E6: Delegated to task_completion_handler.apply_pending_subset_requests()
        if hasattr(self, '_pending_subset_requests') and self._pending_subset_requests:
            applied_count = apply_pending_subset_requests(
                self._pending_subset_requests,
                safe_set_subset_string
            )
            logger.info(f"Applied {applied_count} pending subset requests")
            # Clear the pending requests
            self._pending_subset_requests = []

            # E6: Delegated canvas refresh to task_completion_handler
            schedule_canvas_refresh(
                self._is_complex_filter,
                self._single_canvas_refresh
            )

        # Only cleanup MVs on reset/unfilter actions, NOT on filter
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
            # Only show error message if task was TRULY canceled by user
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
                    # Enhanced error message with failed layer names
                    error_msg = self.message if hasattr(self, 'message') and self.message else 'Task failed'

                    # Include failed layer names if available
                    failed_layers = getattr(self, '_failed_layer_names', [])
                    if failed_layers and error_msg == 'Task failed':
                        error_msg = f"Filter failed for: {', '.join(failed_layers[:3])}"
                        if len(failed_layers) > 3:
                            error_msg += f" (+{len(failed_layers) - 3} more)"

                    logger.error(f"Task finished with failure: {error_msg}")
                    logger.error(f"   Task action: {self.task_action}")
                    logger.error(f"   Source layer: {self.source_layer.name() if self.source_layer else 'None'}")
                    logger.error(f"   Layers count: {getattr(self, 'layers_count', 'N/A')}")

                    # Log to QGIS message log for visibility
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage(
                        f"❌ Task failed: {error_msg}",
                        "FilterMate", Qgis.Critical
                    )

                    # Log additional diagnostic info to Python console
                    if error_msg == 'Task failed':
                        logger.error("   💡 TIP: Check the Python console for detailed error messages")
                        logger.error("   💡 Common causes: no features selected, invalid layer, database connection issue")

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

                    # Restore source layer selection after filter/unfilter
                    # This keeps the selected features visually highlighted on the map
                    try:
                        self._restore_source_layer_selection()
                    except Exception as sel_err:
                        logger.debug(f"Could not restore source layer selection: {sel_err}")

                    # Ensure canvas is refreshed after successful filter operation
                    # This guarantees filtered features are visible on the map
                    try:
                        iface.mapCanvas().refresh()
                    except Exception as e:
                        logger.debug(f"Ignored in post-filter canvas refresh: {e}")

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
                    "Task completed with partial success. "
                    f"Some operations succeeded but an exception occurred: {self.exception}"
                )

        # Clean up OGR backend temporary GEOS-safe layers
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

        # FIX 2026-01-17: Clean up orphaned safe_intersect layers from project
        # These temporary layers should be removed after task completion
        self._cleanup_safe_intersect_layers()

    def _cleanup_safe_intersect_layers(self):
        """
        Clean up orphaned safe_intersect temporary layers from the project.

        These layers are created during OGR/Spatialite filtering as GEOS-safe wrappers
        and should be removed after task completion to prevent project pollution.
        """
        try:
            import re
            from qgis.core import QgsProject

            project = QgsProject.instance()
            layers_to_remove = []

            # Patterns for temp layers created by FilterMate
            temp_patterns = [
                r'_safe_intersect_\d+',
                r'_safe_source$',
                r'_safe_target$',
                r'_geos_safe$',
                r'^source_from_task$',
                r'^source_selection$',
                r'^source_filtered$',
                r'^source_field_based$',
                r'^source_expr_filtered$',
            ]

            for layer_id, layer in project.mapLayers().items():
                layer_name = layer.name()
                for pattern in temp_patterns:
                    if re.search(pattern, layer_name):
                        layers_to_remove.append(layer_id)
                        logger.debug(f"Marking for removal: {layer_name}")
                        break

            if layers_to_remove:
                # Remove layers from project (not from legend - they were never added to legend)
                project.removeMapLayers(layers_to_remove)
                logger.debug(f"Cleaned up {len(layers_to_remove)} temporary safe_intersect layers")
        except Exception as e:
            logger.debug(f"safe_intersect cleanup failed (non-critical): {e}")

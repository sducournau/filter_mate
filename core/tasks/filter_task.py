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
    PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR,
    QGIS_PROVIDER_POSTGRES,
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

# Import CRS utilities (migrated to core/geometry)
from ..geometry.crs_utils import (
    is_geographic_crs,
    is_metric_crs,
    get_optimal_metric_crs,
    get_layer_crs_info
)

# Import from infrastructure (EPIC-1 migration)
from ...infrastructure.cache import SourceGeometryCache
from ...infrastructure.streaming import StreamingExporter, StreamingConfig
from ...infrastructure.parallel import ParallelFilterExecutor, ParallelConfig

# Import from core (EPIC-1 migration - relative import now that we're in core/)
from ..optimization import get_combined_query_optimizer

# Phase 3 C1: Import extracted handlers (February 2026)
from .cleanup_handler import CleanupHandler
from .export_handler import ExportHandler
from .geometry_handler import GeometryHandler
from .initialization_handler import InitializationHandler
from .source_geometry_preparer import SourceGeometryPreparer
from .subset_management_handler import SubsetManagementHandler
from .filtering_orchestrator import FilteringOrchestrator
from .finished_handler import FinishedHandler
from .materialized_view_handler import MaterializedViewHandler
from .expression_facade_handler import ExpressionFacadeHandler

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
            except (ImportError, RuntimeError, AttributeError) as e:
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

        # Phase 3 C1: Initialize extracted handlers (February 2026)
        # These handlers encapsulate cohesive groups of methods to reduce
        # FilterEngineTask complexity from ~5890 to ~4000 lines.
        self._cleanup_handler = CleanupHandler()
        self._export_handler = ExportHandler()
        self._geometry_handler = GeometryHandler()

        # Phase 3 C1 Pass 2: Additional extracted handlers
        self._init_handler = InitializationHandler()
        self._source_geom_preparer = SourceGeometryPreparer()
        self._subset_handler = SubsetManagementHandler()

        # Phase 3 C1 US-C1.3.2: Filtering orchestration handler
        self._filtering_orchestrator = FilteringOrchestrator()

        # Phase 3 C1 US-C1.3.3: Task completion handler
        self._finished_handler = FinishedHandler()

        # Pass 3: Materialized view handler
        self._mv_handler = MaterializedViewHandler(self)

        # Pass 3: Expression facade handler
        self._expr_facade = ExpressionFacadeHandler(self)

    # ========================================================================
    # FIX 2026-01-16: Early Predicate Initialization
    # ========================================================================

    def _initialize_current_predicates(self):
        """Initialize current_predicates from task parameters. Delegates to InitializationHandler."""
        result = self._init_handler.initialize_current_predicates(
            task_parameters=self.task_parameters,
            predicates_map=self.predicates,
            expression_builder=self._expression_builder,
            filter_orchestrator=self._filter_orchestrator,
        )
        self.current_predicates = result['current_predicates']
        self.numeric_predicates = result['numeric_predicates']

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
        except (RuntimeError, AttributeError, ValueError) as e:
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
            except (AttributeError, TypeError, RuntimeError) as e:
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
            except (RuntimeError, OSError, AttributeError) as e:
                logger.error(f"Failed to get connection from source layer: {e}")

        # Last resort: try from infos layer_id
        try:
            layer_id = self.task_parameters.get("infos", {}).get("layer_id")
            if layer_id:
                layer = self.PROJECT.mapLayer(layer_id)
                if layer and layer.providerType() == QGIS_PROVIDER_POSTGRES:
                    connexion, source_uri = get_datasource_connexion_from_layer(layer)
                    if connexion is not None:
                        self.active_connections.append(connexion)
                        return connexion
        except (RuntimeError, OSError, AttributeError, KeyError) as e:
            logger.error(f"Failed to get connection from layer by ID: {e}")

        raise Exception(
            "No valid PostgreSQL connection available. "
            "ACTIVE_POSTGRESQL was not a valid connection object and could not obtain fresh connection from layer."
        )

    def _initialize_source_layer(self):
        """Initialize source layer and basic layer count. Delegates to InitializationHandler."""
        result = self._init_handler.initialize_source_layer(self.task_parameters, self.PROJECT)
        if not result['success']:
            self.exception = result['exception']
            return False
        self.layers_count = 1
        self.source_layer = result['source_layer']
        self.source_crs = result['source_crs']
        self.source_layer_crs_authid = result['source_layer_crs_authid']
        if result['feature_count_limit'] is not None:
            self.feature_count_limit = result['feature_count_limit']
        return True

    def _configure_metric_crs(self):
        """Configure CRS for metric calculations. Delegates to InitializationHandler."""
        result = self._init_handler.configure_metric_crs(
            source_crs=self.source_crs,
            source_layer=self.source_layer,
            project=self.PROJECT,
            source_layer_crs_authid=self.source_layer_crs_authid,
        )
        self.has_to_reproject_source_layer = result['has_to_reproject']
        self.source_layer_crs_authid = result['crs_authid']

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

        except Exception as e:  # catch-all safety net: fallback to legacy routing
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
        except Exception as e:  # catch-all safety net: captures any action failure
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

        except Exception as e:  # catch-all safety net: QgsTask.run() must not propagate exceptions
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

        except Exception as e:  # catch-all safety net: v3 bridge failure falls back to legacy
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

        except Exception as e:  # catch-all safety net: v3 bridge failure falls back to legacy
            logger.warning(f"TaskBridge export delegation failed: {e}")
            return None

    def _initialize_source_filtering_parameters(self):
        """Extract and initialize all parameters. Delegates to InitializationHandler."""
        result = self._init_handler.initialize_source_filtering_parameters(
            task_parameters=self.task_parameters,
            source_layer=self.source_layer,
            postgresql_available=POSTGRESQL_AVAILABLE,
            sanitize_subset_fn=self._sanitize_subset_string,
        )
        self.param_source_provider_type = result['provider_type']
        self.param_source_layer_name = result['layer_name']
        self.param_source_layer_id = result['layer_id']
        self.param_source_table = result['table_name']
        self.param_source_schema = result['schema']
        self.param_source_geom = result['geometry_field']
        self.primary_key_name = result['primary_key_name']
        self._source_forced_backend = result['forced_backend']
        self._source_postgresql_fallback = result['postgresql_fallback']
        self.has_combine_operator = result['has_combine_operator']
        self.param_source_layer_combine_operator = result['source_layer_combine_operator']
        self.param_other_layers_combine_operator = result['other_layers_combine_operator']
        self.param_source_old_subset = result['old_subset']
        self.source_layer_fields_names = result['field_names']
        # Critical for ExpressionBuilder to access source table info
        self.task_parameters['param_source_table'] = result['table_name']
        self.task_parameters['param_source_schema'] = result['schema']

    def _sanitize_subset_string(self, subset_string):
        """Sanitize subset string. Delegates to ExpressionFacadeHandler."""
        return self._expr_facade.sanitize_subset_string(subset_string)

    def _extract_spatial_clauses_for_exists(self, filter_expr, source_table=None):
        """Extract spatial clauses. Delegates to ExpressionFacadeHandler."""
        return self._expr_facade.extract_spatial_clauses_for_exists(filter_expr, source_table)

    def _apply_postgresql_type_casting(self, expression, layer=None):
        """Apply PostgreSQL type casting. Delegates to ExpressionFacadeHandler."""
        return self._expr_facade.apply_postgresql_type_casting(expression, layer)

    def _process_qgis_expression(self, expression):
        """Process QGIS expression. Delegates to ExpressionFacadeHandler."""
        return self._expr_facade.process_qgis_expression(expression)

    def _combine_with_old_subset(self, expression):
        """Combine with old subset. Delegates to ExpressionFacadeHandler."""
        return self._expr_facade.combine_with_old_subset(expression)

    def _build_feature_id_expression(self, features_list):
        """Build feature ID expression. Delegates to ExpressionFacadeHandler."""
        return self._expr_facade.build_feature_id_expression(features_list)

    def _is_pk_numeric(self, layer=None, pk_field=None):
        """Check if PK is numeric. Delegates to ExpressionFacadeHandler."""
        return self._expr_facade.is_pk_numeric(layer, pk_field)

    def _format_pk_values_for_sql(self, values, is_numeric=None, layer=None, pk_field=None):
        """Format PK values for SQL. Delegates to ExpressionFacadeHandler."""
        return self._expr_facade.format_pk_values_for_sql(values, is_numeric, layer, pk_field)

    def _optimize_duplicate_in_clauses(self, expression):
        """Optimize duplicate IN clauses. Delegates to ExpressionFacadeHandler."""
        return self._expr_facade.optimize_duplicate_in_clauses(expression)

    def _apply_filter_and_update_subset(self, expression):
        """Queue filter expression for main thread. Delegates to ExpressionFacadeHandler."""
        return self._expr_facade.apply_filter_and_update_subset(expression)

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
        """Initialize source subset and buffer parameters. Delegates to InitializationHandler."""
        result = self._init_handler.initialize_source_subset_and_buffer(
            task_parameters=self.task_parameters,
            expression=self.expression,
            old_subset=self.param_source_old_subset,
            is_field_expression=getattr(self, 'is_field_expression', None),
        )
        self.param_source_new_subset = result['source_new_subset']
        self.param_use_centroids_source_layer = result['use_centroids_source_layer']
        self.param_use_centroids_distant_layers = result['use_centroids_distant_layers']
        self.approved_optimizations = result['approved_optimizations']
        self.auto_apply_optimizations = result['auto_apply_optimizations']
        self.param_buffer_value = result['buffer_value']
        self.param_buffer_expression = result['buffer_expression']
        self.param_buffer_type = result['buffer_type']
        self.param_buffer_segments = result['buffer_segments']

    def _prepare_geometries_by_provider(self, provider_list):
        """Prepare source geometries for each provider. Delegates to SourceGeometryPreparer."""
        result = self._source_geom_preparer.prepare_geometries_by_provider(
            provider_list=provider_list,
            task_parameters=self.task_parameters,
            source_layer=self.source_layer,
            param_source_provider_type=self.param_source_provider_type,
            param_buffer_expression=self.param_buffer_expression,
            layers_dict=self.layers if hasattr(self, 'layers') else None,
            prepare_postgresql_callback=lambda: self.prepare_postgresql_source_geom(),
            prepare_spatialite_callback=lambda: self.prepare_spatialite_source_geom(),
            prepare_ogr_callback=lambda: self.prepare_ogr_source_geom(),
            postgresql_available=POSTGRESQL_AVAILABLE,
        )
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
        """Iterate through all layers with progress tracking. Delegates to FilteringOrchestrator."""
        result = self._filtering_orchestrator.filter_all_layers_with_progress(
            layers=self.layers,
            layers_count=self.layers_count,
            task_parameters=self.task_parameters,
            execute_geometric_filtering_callback=self.execute_geometric_filtering,
            try_v3_multi_step_filter_callback=self._try_v3_multi_step_filter,
            is_canceled_callback=self.isCanceled,
            set_progress_callback=self.setProgress,
            set_description_callback=self.setDescription,
        )
        if result.get('message'):
            self.message = result['message']
        if result.get('failed_layer_names'):
            self._failed_layer_names = result['failed_layer_names']
        return result.get('success', True)

    def _log_filtering_summary(self, successful_filters: int, failed_filters: int, failed_layer_names=None):
        """Log summary of filtering results. Delegates to FilteringOrchestrator."""
        self._filtering_orchestrator._log_filtering_summary(
            layers_count=self.layers_count, successful_filters=successful_filters,
            failed_filters=failed_filters, failed_layer_names=failed_layer_names
        )

    def manage_distant_layers_geometric_filtering(self) -> bool:
        """Filter distant layers using source layer geometries. Delegates to FilteringOrchestrator."""
        def _set_cached_feature_count(count):
            self._cached_source_feature_count = count

        return self._filtering_orchestrator.manage_distant_layers_geometric_filtering(
            source_layer=self.source_layer,
            layers=self.layers,
            task_parameters=self.task_parameters,
            param_buffer_expression=self.param_buffer_expression,
            param_source_provider_type=self.param_source_provider_type,
            provider_list=self.provider_list,
            initialize_source_subset_and_buffer_callback=self._initialize_source_subset_and_buffer,
            ensure_buffer_expression_mv_exists_callback=self._ensure_buffer_expression_mv_exists,
            try_create_filter_chain_mv_callback=self._try_create_filter_chain_mv,
            prepare_geometries_by_provider_callback=self._prepare_geometries_by_provider,
            filter_all_layers_with_progress_callback=self._filter_all_layers_with_progress,
            cached_source_feature_count_setter=_set_cached_feature_count,
        )

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
        """Prepare PostgreSQL source geometry. Delegates to SourceGeometryPreparer."""
        source_fc = getattr(self, '_cached_source_feature_count', None)
        result = self._source_geom_preparer.prepare_postgresql_source_geom(
            source_table=self.param_source_table, source_schema=self.param_source_schema,
            source_geom=self.param_source_geom,
            buffer_value=getattr(self, 'param_buffer_value', None),
            buffer_expression=getattr(self, 'param_buffer_expression', None),
            use_centroids=getattr(self, 'param_use_centroids_source_layer', False),
            buffer_segments=getattr(self, 'param_buffer_segments', 5),
            buffer_type=self.task_parameters.get("filtering", {}).get("buffer_type", "Round"),
            primary_key_name=getattr(self, 'primary_key_name', None),
            session_id=getattr(self, 'session_id', None),
            mv_schema=getattr(self, 'current_materialized_view_schema', 'filter_mate_temp'),
            source_feature_count=source_fc,
            source_layer=self.source_layer,
        )
        self.postgresql_source_geom = result['geom']
        if result['mv_name']:
            self.current_materialized_view_name = result['mv_name']
        return result['geom']

    def _get_optimization_thresholds(self):
        """Get optimization thresholds. Delegates to GeometryHandler."""
        return self._geometry_handler.get_optimization_thresholds(getattr(self, 'task_parameters', None))

    def _get_simplification_config(self):
        """Get simplification config. Delegates to GeometryHandler."""
        return self._geometry_handler.get_simplification_config(getattr(self, 'task_parameters', None))

    def _get_wkt_precision(self, crs_authid: str = None) -> int:
        """Get WKT precision. Delegates to GeometryHandler."""
        if crs_authid is None:
            crs_authid = getattr(self, 'source_layer_crs_authid', None)
        return self._geometry_handler.get_wkt_precision(crs_authid)

    def _geometry_to_wkt(self, geometry, crs_authid: str = None) -> str:
        """Convert geometry to WKT. Delegates to GeometryHandler."""
        return self._geometry_handler.geometry_to_wkt(geometry, crs_authid)

    def _get_buffer_aware_tolerance(self, buffer_value, buffer_segments, buffer_type, extent_size, is_geographic=False):
        """Calculate simplification tolerance. Delegates to GeometryHandler."""
        return self._geometry_handler.get_buffer_aware_tolerance(
            buffer_value, buffer_segments, buffer_type, extent_size, is_geographic
        )

    def _simplify_geometry_adaptive(self, geometry: Any, max_wkt_length: Optional[int] = None, crs_authid: Optional[str] = None) -> Any:
        """Simplify geometry adaptively. Delegates to GeometryHandler."""
        return self._geometry_handler.simplify_geometry_adaptive(
            geometry, max_wkt_length, crs_authid,
            buffer_value=getattr(self, 'param_buffer_value', None),
            buffer_segments=getattr(self, 'param_buffer_segments', 5),
            buffer_type=getattr(self, 'param_buffer_type', 0),
        )

    def prepare_spatialite_source_geom(self) -> Optional[str]:
        """Prepare Spatialite source geometry. Delegates to SourceGeometryPreparer."""
        result = self._source_geom_preparer.prepare_spatialite_source_geom(
            source_layer=self.source_layer, task_parameters=self.task_parameters,
            is_field_expression=getattr(self, 'is_field_expression', None),
            expression=getattr(self, 'expression', None),
            param_source_new_subset=getattr(self, 'param_source_new_subset', None),
            param_buffer_value=getattr(self, 'param_buffer_value', None),
            has_to_reproject_source_layer=getattr(self, 'has_to_reproject_source_layer', False),
            source_layer_crs_authid=getattr(self, 'source_layer_crs_authid', None),
            source_crs=getattr(self, 'source_crs', None),
            param_use_centroids_source_layer=getattr(self, 'param_use_centroids_source_layer', False),
            project=getattr(self, 'PROJECT', None),
            geom_cache=getattr(self, 'geom_cache', None),
            geometry_to_wkt_fn=self._geometry_to_wkt,
            simplify_geometry_adaptive_fn=self._simplify_geometry_adaptive,
            get_optimization_thresholds_fn=self._get_optimization_thresholds,
        )
        if result['success']:
            self.spatialite_source_geom = result['wkt']
            if hasattr(self, 'task_parameters') and self.task_parameters:
                if 'infos' not in self.task_parameters:
                    self.task_parameters['infos'] = {}
                self.task_parameters['infos']['source_geom_wkt'] = result['wkt']
                self.task_parameters['infos']['buffer_state'] = result['buffer_state']
            return result['wkt']
        else:
            self.spatialite_source_geom = None
            return None

    def _copy_filtered_layer_to_memory(self, layer: QgsVectorLayer, layer_name: str = "filtered_copy") -> QgsVectorLayer:
        """Copy filtered layer to memory. Delegates to GeometryHandler."""
        return self._geometry_handler.copy_filtered_layer_to_memory(
            layer, layer_name, self._verify_and_create_spatial_index
        )

    def _copy_selected_features_to_memory(self, layer: QgsVectorLayer, layer_name: str = "selected_copy") -> QgsVectorLayer:
        """Copy selected features to memory. Delegates to GeometryHandler."""
        return self._geometry_handler.copy_selected_features_to_memory(
            layer, layer_name, self._verify_and_create_spatial_index
        )

    def _create_memory_layer_from_features(self, features: List[QgsFeature], crs: QgsCoordinateReferenceSystem, layer_name: str = "from_features") -> Optional[QgsVectorLayer]:
        """Create memory layer from features. Delegates to GeometryHandler."""
        return self._geometry_handler.create_memory_layer_from_features(
            features, crs, layer_name, self._verify_and_create_spatial_index
        )

    def _convert_layer_to_centroids(self, layer: QgsVectorLayer) -> Optional[QgsVectorLayer]:
        """Convert to centroids. Delegates to GeometryHandler."""
        return self._geometry_handler.convert_layer_to_centroids(layer)

    def _fix_invalid_geometries(self, layer, output_key):
        """Fix invalid geometries. Delegates to GeometryHandler."""
        return self._geometry_handler.fix_invalid_geometries(layer, output_key)

    def _reproject_layer(self, layer, target_crs):
        """Reproject layer. Delegates to GeometryHandler."""
        return self._geometry_handler.reproject_layer(layer, target_crs, self.outputs)

    def _store_warning_message(self, message):
        """Store a warning message for display in UI thread (thread-safe callback)."""
        self._geometry_handler.store_warning_message(message, self.warning_messages)

    def _get_buffer_distance_parameter(self):
        """Get buffer distance parameter. Delegates to GeometryHandler."""
        return self._geometry_handler.get_buffer_distance_parameter(
            self.param_buffer_expression, self.param_buffer_value
        )

    def _apply_qgis_buffer(self, layer, buffer_distance):
        """Apply QGIS buffer. Delegates to GeometryHandler."""
        return self._geometry_handler.apply_qgis_buffer(
            layer, buffer_distance, self.param_buffer_type, self.param_buffer_segments, self.outputs
        )

    def _convert_geometry_collection_to_multipolygon(self, layer):
        """Convert GeometryCollection to MultiPolygon. Delegates to GeometryHandler."""
        return self._geometry_handler.convert_geometry_collection_to_multipolygon(layer)

    def _evaluate_buffer_distance(self, layer, buffer_param):
        """Evaluate buffer distance. Delegates to GeometryHandler."""
        return self._geometry_handler.evaluate_buffer_distance(layer, buffer_param)

    def _create_memory_layer_for_buffer(self, layer):
        """Create memory layer for buffer. Delegates to GeometryHandler."""
        return self._geometry_handler.create_memory_layer_for_buffer(layer)

    def _buffer_all_features(self, layer, buffer_dist):
        """Buffer all features. Delegates to GeometryHandler."""
        return self._geometry_handler.buffer_all_features(
            layer, buffer_dist, getattr(self, 'param_buffer_segments', 5)
        )

    def _dissolve_and_add_to_layer(self, geometries, buffered_layer):
        """Dissolve and add to layer. Delegates to GeometryHandler."""
        return self._geometry_handler.dissolve_and_add_to_layer(
            geometries, buffered_layer, self._verify_and_create_spatial_index
        )

    def _create_buffered_memory_layer(self, layer, buffer_distance):
        """Create buffered memory layer. Delegates to GeometryHandler."""
        return self._geometry_handler.create_buffered_memory_layer(
            layer, buffer_distance, self.param_buffer_segments,
            self._verify_and_create_spatial_index, self._store_warning_message
        )

    def _aggressive_geometry_repair(self, geom):
        """Aggressive geometry repair. Delegates to GeometryHandler."""
        return self._geometry_handler.aggressive_geometry_repair(geom)

    def _repair_invalid_geometries(self, layer):
        """Repair invalid geometries. Delegates to GeometryHandler."""
        return self._geometry_handler.repair_invalid_geometries(
            layer, self._verify_and_create_spatial_index
        )

    def _simplify_buffer_result(self, layer, buffer_distance):
        """Simplify buffer result. Delegates to GeometryHandler."""
        return self._geometry_handler.simplify_buffer_result(
            layer, buffer_distance, self._verify_and_create_spatial_index
        )

    def _apply_buffer_with_fallback(self, layer, buffer_distance):
        """Apply buffer with fallback. Delegates to GeometryHandler."""
        return self._geometry_handler.apply_buffer_with_fallback(
            layer, buffer_distance, self.param_buffer_type, self.param_buffer_segments,
            self.outputs, self._verify_and_create_spatial_index, self._store_warning_message,
        )

    def prepare_ogr_source_geom(self):
        """Prepare OGR source geometry. Delegates to SourceGeometryPreparer."""
        result = self._source_geom_preparer.prepare_ogr_source_geom(
            source_layer=self.source_layer, task_parameters=self.task_parameters,
            is_field_expression=getattr(self, 'is_field_expression', None),
            expression=getattr(self, 'expression', None),
            param_source_new_subset=getattr(self, 'param_source_new_subset', None),
            has_to_reproject_source_layer=self.has_to_reproject_source_layer,
            source_layer_crs_authid=self.source_layer_crs_authid,
            param_use_centroids_source_layer=self.param_use_centroids_source_layer,
            spatialite_fallback_mode=getattr(self, '_spatialite_fallback_mode', False),
            copy_filtered_layer_to_memory_fn=self._copy_filtered_layer_to_memory,
            copy_selected_features_to_memory_fn=self._copy_selected_features_to_memory,
            create_memory_layer_from_features_fn=self._create_memory_layer_from_features,
            reproject_layer_fn=self._reproject_layer,
            convert_layer_to_centroids_fn=self._convert_layer_to_centroids,
            get_buffer_distance_parameter_fn=self._get_buffer_distance_parameter,
            ogr_executor=ogr_executor,
            ogr_executor_available=OGR_EXECUTOR_AVAILABLE,
        )
        self.ogr_source_geom = result
        return self.ogr_source_geom

    def _verify_and_create_spatial_index(self, layer, layer_name=None):
        """Verify/create spatial index. Delegates to GeometryHandler."""
        return self._geometry_handler.verify_and_create_spatial_index(layer, layer_name)

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
        """Normalize column names for PostgreSQL. Delegates to ExpressionFacadeHandler."""
        return self._expr_facade.normalize_column_names_for_postgresql(expression, field_names)

    def _qualify_field_names_in_expression(self, expression, field_names, primary_key_name, table_name, is_postgresql):
        """Qualify field names in expression. Delegates to ExpressionFacadeHandler."""
        return self._expr_facade.qualify_field_names_in_expression(
            expression, field_names, primary_key_name, table_name, is_postgresql
        )

    def _build_combined_filter_expression(self, new_expression, old_subset, combine_operator, layer_props=None):
        """Build combined filter expression. Delegates to ExpressionFacadeHandler."""
        return self._expr_facade.build_combined_filter_expression(
            new_expression, old_subset, combine_operator, layer_props
        )

    def _create_source_mv_if_needed(self, source_mv_info):
        """Create source materialized view with pre-computed buffer. Delegates to MaterializedViewHandler."""
        return self._mv_handler.create_source_mv_if_needed(source_mv_info)

    def _ensure_buffer_expression_mv_exists(self):
        """Ensure buffer expression MVs exist. Delegates to MaterializedViewHandler."""
        return self._mv_handler.ensure_buffer_expression_mv_exists()

    def _try_create_filter_chain_mv(self):
        """Try to create filter chain MV optimization. Delegates to MaterializedViewHandler."""
        return self._mv_handler.try_create_filter_chain_mv()

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
        except Exception as e:  # catch-all safety net: geometric filtering must not crash the task
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
                except (RuntimeError, AttributeError, ValueError) as e:
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
        """Execute the complete filtering workflow. Delegates to FilteringOrchestrator."""
        result = self._filtering_orchestrator.execute_filtering(
            task_parameters=self.task_parameters,
            source_layer=self.source_layer,
            layers=self.layers,
            layers_count=self.layers_count,
            current_predicates=self.current_predicates,
            initialize_current_predicates_callback=self._initialize_current_predicates,
            execute_source_layer_filtering_callback=self.execute_source_layer_filtering,
            manage_distant_layers_callback=self.manage_distant_layers_geometric_filtering,
            is_canceled_callback=self.isCanceled,
            set_progress_callback=self.setProgress,
        )
        if result.get('message'):
            self.message = result['message']
        if result.get('failed_layer_names'):
            self._failed_layer_names = result['failed_layer_names']
        return result.get('success', False)

    def execute_unfiltering(self) -> bool:
        """Remove all filters from source and selected remote layers. Delegates to FilteringOrchestrator."""
        return self._filtering_orchestrator.execute_unfiltering(
            source_layer=self.source_layer,
            layers=self.layers,
            layers_count=self.layers_count,
            queue_subset_string_callback=self._queue_subset_string,
            is_canceled_callback=self.isCanceled,
            set_progress_callback=self.setProgress,
        )

    def execute_reseting(self) -> bool:
        """Reset all layers to their original/saved subset state. Delegates to FilteringOrchestrator."""
        return self._filtering_orchestrator.execute_reseting(
            source_layer=self.source_layer,
            layers=self.layers,
            layers_count=self.layers_count,
            manage_layer_subset_strings_callback=self.manage_layer_subset_strings,
            is_canceled_callback=self.isCanceled,
            set_progress_callback=self.setProgress,
        )

    def _validate_export_parameters(self):
        """Validate export parameters. Delegates to ExportHandler."""
        return self._export_handler.validate_export_parameters(self.task_parameters)

    def _get_layer_by_name(self, layer_name):
        """Get layer by name. Delegates to ExportHandler."""
        return self._export_handler.get_layer_by_name(self.PROJECT, layer_name)

    def _save_layer_style(self, layer, output_path, style_format, datatype):
        """Save layer style. Delegates to ExportHandler."""
        self._export_handler.save_layer_style(layer, output_path, style_format, datatype)

    def _save_layer_style_lyrx(self, layer, output_path):
        """Save layer style LYRX. Delegates to ExportHandler."""
        self._export_handler.save_layer_style_lyrx(layer, output_path)

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
        """Export selected layers. Delegates to ExportHandler."""
        success, message, error_details = self._export_handler.execute_exporting(
            task_parameters=self.task_parameters,
            project=self.PROJECT,
            set_progress=self.setProgress,
            set_description=self.setDescription,
            is_canceled=self.isCanceled,
        )
        self.message = message
        if error_details:
            self.error_details = error_details
        return success

    def _calculate_total_features(self, layers) -> int:
        """Calculate total features. Delegates to ExportHandler."""
        return self._export_handler.calculate_total_features(layers, self.PROJECT)

    def _export_with_streaming(self, layers, output_folder, projection, datatype, style_format, save_styles, chunk_size):
        """Export with streaming. Delegates to ExportHandler."""
        success, message = self._export_handler._export_with_streaming(
            layers, output_folder, projection, datatype,
            style_format, save_styles, chunk_size,
            self.PROJECT, self.setProgress, self.setDescription, self.isCanceled,
        )
        self.message = message
        return success

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
        """Create simple MV SQL. Delegates to MaterializedViewHandler."""
        return self._mv_handler.create_simple_materialized_view_sql(schema, name, sql_subset_string)

    def _parse_where_clauses(self) -> Any:
        """Parse WHERE clauses. Delegates to MaterializedViewHandler."""
        return self._mv_handler.parse_where_clauses()

    def _create_custom_buffer_view_sql(self, schema, name, geom_key_name, where_clause_fields_arr, last_subset_id, sql_subset_string):
        """Create SQL for custom buffer MV. Delegates to MaterializedViewHandler."""
        return self._mv_handler.create_custom_buffer_view_sql(
            schema, name, geom_key_name, where_clause_fields_arr, last_subset_id, sql_subset_string
        )

    def _ensure_temp_schema_exists(self, connexion, schema_name):
        """Ensure temp schema exists. Delegates to MaterializedViewHandler."""
        return self._mv_handler.ensure_temp_schema_exists(connexion, schema_name)

    def _get_session_prefixed_name(self, base_name: str) -> str:
        """Generate session-unique MV name. Delegates to MaterializedViewHandler."""
        return self._mv_handler.get_session_prefixed_name(base_name)

    def _cleanup_session_materialized_views(self, connexion: Any, schema_name: str) -> Any:
        """Clean up session MVs. Delegates to MaterializedViewHandler."""
        return self._mv_handler.cleanup_session_materialized_views(connexion, schema_name)

    def _cleanup_orphaned_materialized_views(self, connexion: Any, schema_name: str, max_age_hours: int = 24) -> Any:
        """Clean up orphaned MVs. Delegates to MaterializedViewHandler."""
        return self._mv_handler.cleanup_orphaned_materialized_views(connexion, schema_name, max_age_hours)

    def _execute_postgresql_commands(self, connexion: Any, commands: List[str]) -> bool:
        """Execute PostgreSQL commands. Delegates to MaterializedViewHandler."""
        return self._mv_handler.execute_postgresql_commands(connexion, commands)

    def _ensure_source_table_stats(self, connexion: Any, schema: str, table: str, geom_field: str) -> bool:
        """Ensure PostgreSQL statistics exist. Delegates to MaterializedViewHandler."""
        return self._mv_handler.ensure_source_table_stats(connexion, schema, table, geom_field)

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
            except (RuntimeError, OSError, AttributeError) as e:
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
                except (RuntimeError, OSError, AttributeError) as e:
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
        except sqlite3.Error as e:
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
                except (RuntimeError, OSError, AttributeError) as e:
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
        """Manage layer subset strings. Delegates to SubsetManagementHandler."""
        result = self._subset_handler.manage_layer_subset_strings(
            layer=layer, task_action=self.task_action,
            safe_connect_fn=self._safe_spatialite_connect,
            active_connections=self.active_connections,
            project_uuid=self.project_uuid, session_id=self.session_id,
            source_layer=self.source_layer, db_file_path=self.db_file_path,
            ps_manager=self._ps_manager, postgresql_available=POSTGRESQL_AVAILABLE,
            queue_subset_fn=self._queue_subset_string,
            get_session_name_fn=self._get_session_prefixed_name,
            get_connection_fn=self._get_valid_postgresql_connection,
            ensure_stats_fn=self._ensure_source_table_stats,
            extract_where_fn=self._extract_where_clause_from_select,
            insert_history_fn=self._insert_subset_history,
            ensure_schema_fn=self._ensure_temp_schema_exists,
            execute_commands_fn=self._execute_postgresql_commands,
            create_simple_mv_fn=self._create_simple_materialized_view_sql,
            create_custom_mv_fn=self._create_custom_buffer_view_sql,
            parse_where_clauses_fn=self._parse_where_clauses,
            manage_spatialite_subset_fn=self._manage_spatialite_subset,
            get_spatialite_datasource_fn=self._get_spatialite_datasource,
            pg_execute_filter_fn=pg_execute_filter, pg_execute_reset_fn=pg_execute_reset,
            pg_execute_unfilter_fn=pg_execute_unfilter, pg_executor_available=PG_EXECUTOR_AVAILABLE,
            ogr_execute_reset_fn=ogr_execute_reset, ogr_execute_unfilter_fn=ogr_execute_unfilter,
            current_mv_schema=self.current_materialized_view_schema,
            param_source_schema=self.param_source_schema,
            param_source_table=self.param_source_table,
            param_source_geom=self.param_source_geom,
            param_buffer_expression=getattr(self, 'param_buffer_expression', None),
            task_parameters=self.task_parameters,
            sql_subset_string=sql_subset_string, primary_key_name=primary_key_name,
            geom_key_name=geom_key_name, custom=custom,
        )
        # Reset prepared statements manager when connection closes
        self._ps_manager = None
        return result

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
                except (RuntimeError, AttributeError) as e:
                    logger.debug(f"Ignored in final canvas repaint loop: {e}")

            # Final canvas refresh
            iface.mapCanvas().refresh()

            if layers_repainted > 0:
                logger.debug(f"Final canvas refresh: repainted {layers_repainted} filtered layer(s)")
            else:
                logger.debug("Final canvas refresh completed (2s delay)")
            logger.debug("Final canvas refresh completed (2s delay)")

        except Exception as e:  # catch-all safety net: canvas refresh must not crash finished()
            logger.debug(f"Final canvas refresh skipped: {e}")

    def _cleanup_postgresql_materialized_views(self):
        """Cleanup PostgreSQL materialized views. Delegates to MaterializedViewHandler."""
        self._mv_handler.cleanup_postgresql_materialized_views()

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
            except (RuntimeError, OSError, AttributeError) as e:
                # Log but don't fail - connection may already be closed
                logger.debug(f"Connection cleanup failed (may already be closed): {e}")
        self.active_connections.clear()
        # Reset prepared statements manager when connections close
        self._ps_manager = None

        # Use Python logger only, NOT QgsMessageLog
        # QgsMessageLog may be destroyed during QGIS shutdown, causing access violation
        try:
            logger.info(f'"{self.description()}" task was canceled')
        except Exception:  # catch-all safety net: logger may be destroyed during QGIS shutdown
            pass  # Intentional silent catch

        super().cancel()

    def _restore_source_layer_selection(self):
        """Restore source layer selection after filter/unfilter. Delegates to FeatureCollector."""
        if not self.source_layer or not is_valid_layer(self.source_layer):
            return

        collector = self._get_feature_collector()
        feature_fids = self.task_parameters.get("task", {}).get("feature_fids", [])

        if not feature_fids:
            task_features = self.task_parameters.get("task", {}).get("features", [])
            if task_features:
                result = collector.collect_from_features(task_features)
                feature_fids = result.feature_ids

        if feature_fids:
            collector.restore_layer_selection(self.source_layer, feature_fids)
            logger.info(f"Restored source layer selection via FeatureCollector: {len(feature_fids)} feature(s)")

    @main_thread_only
    def finished(self, result: Optional[bool]) -> None:
        """Handle task completion. Delegates to FinishedHandler."""
        message_category = MESSAGE_TASKS_CATEGORIES[self.task_action]

        cleared_warnings, cleared_pending, cleared_ogr = self._finished_handler.handle_finished(
            result=result,
            task_action=self.task_action,
            message_category=message_category,
            is_canceled_fn=self.isCanceled,
            warning_messages=getattr(self, 'warning_messages', []),
            pending_subset_requests=getattr(self, '_pending_subset_requests', []),
            safe_set_subset_fn=safe_set_subset_string,
            is_complex_filter_fn=self._is_complex_filter,
            single_canvas_refresh_fn=self._single_canvas_refresh,
            cleanup_mv_fn=self._cleanup_postgresql_materialized_views,
            ogr_source_geom=getattr(self, 'ogr_source_geom', None),
            exception=self.exception,
            task_message=getattr(self, 'message', None),
            source_layer=getattr(self, 'source_layer', None),
            task_parameters=getattr(self, 'task_parameters', {}),
            failed_layer_names=getattr(self, '_failed_layer_names', []),
            layers_count=getattr(self, 'layers_count', None),
            task_description=self.description(),
            restore_selection_fn=self._restore_source_layer_selection,
            task_bridge=getattr(self, '_task_bridge', None),
            cleanup_safe_intersect_fn=self._cleanup_safe_intersect_layers,
        )

        # Update state from handler return values
        self.warning_messages = cleared_warnings
        self._pending_subset_requests = cleared_pending
        self.ogr_source_geom = cleared_ogr

    def _cleanup_safe_intersect_layers(self):
        """Cleanup orphaned safe_intersect layers. Delegates to FinishedHandler."""
        self._finished_handler.cleanup_safe_intersect_layers()

"""
FilterMate Application Orchestrator

.. deprecated:: 3.0.0
    This module is a legacy God Class (5,900+ lines) and will be progressively
    refactored in future versions. New code should use the hexagonal architecture:
    
    - For filtering logic: core/services/filter_service.py
    - For task management: adapters/qgis/tasks/
    - For backend operations: adapters/backends/
    
    This module is kept for backward compatibility. See docs/architecture.md.
"""

from qgis.PyQt.QtCore import Qt, QTimer
import weakref
import sip
from qgis.PyQt.QtWidgets import QApplication
from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransformContext,
    QgsExpressionContextUtils,
    QgsMapLayerProxyModel,
    QgsProject,
    QgsTask,
    QgsVectorFileWriter,
    QgsVectorLayer
)
from qgis.utils import iface
from qgis import processing
from osgeo import ogr

import os.path
import logging
from .config.config import init_env_vars, ENV_VARS
import json

# Core tasks (migrated from modules/tasks/)
from .core.tasks import (
    FilterEngineTask,
    LayersManagementEngineTask,
)
from .infrastructure.utils import spatialite_connect

# Infrastructure utilities (migrated from modules/appUtils)
from .infrastructure.utils import (
    POSTGRESQL_AVAILABLE,
    get_data_source_uri,
    get_datasource_connexion_from_layer,
    is_layer_source_available,
    detect_layer_provider_type,
    validate_and_cleanup_postgres_layers,  # v2.8.1: Orphaned MV cleanup on project load
)
from .infrastructure.database.sql_utils import sanitize_sql_identifier, safe_set_subset_string
from .infrastructure.field_utils import clean_buffer_value, cleanup_corrupted_layer_filters
from .utils.type_utils import return_typed_value
from .infrastructure.feedback import (
    show_backend_info, show_success_with_backend,
    show_info, show_warning, show_error
)
from .core.services.history_service import HistoryService
from .core.services.favorites_service import FavoritesService
from .ui.config import UIConfig, DisplayProfile

# Config helpers (migrated to config/)
from .config.config import get_optimization_thresholds

# Object safety utilities (migrated to infrastructure/utils/)
from .infrastructure.utils import (
    is_sip_deleted, is_layer_valid as is_valid_layer, is_qgis_alive,
    GdalErrorHandler
)
from .infrastructure.logging import get_app_logger
from .resources import *  # Qt resources must be imported with wildcard

# Get FilterMate logger BEFORE importing hexagonal services
logger = get_app_logger()

# v3.0: Hexagonal architecture services bridge
# Provides access to new architecture while maintaining backward compatibility
HEXAGONAL_AVAILABLE = False
try:
    logger.debug("Loading hexagonal services...")
    from .adapters.app_bridge import (
        initialize_services as _init_hexagonal_services,
        cleanup_services as _cleanup_hexagonal_services,
        is_initialized as _hexagonal_initialized,
        get_filter_service,
        get_history_service,
        get_expression_service,
        validate_expression,
        parse_expression,
    )
    logger.debug("✓ app_bridge")
    from .adapters.task_builder import TaskParameterBuilder  # v4.0: Task parameter extraction
    logger.debug("✓ task_builder")
    from .core.services.layer_lifecycle_service import (  # v4.0: Layer lifecycle extraction
        LayerLifecycleService,
        LayerLifecycleConfig
    )
    logger.debug("✓ layer_lifecycle_service")
    from .core.services.task_management_service import (  # v4.0: Task management extraction
        TaskManagementService,
        TaskManagementConfig
    )
    logger.debug("✓ task_management_service")
    from .adapters.undo_redo_handler import UndoRedoHandler  # v4.0: Undo/Redo extraction
    logger.debug("✓ undo_redo_handler")
    from .adapters.database_manager import DatabaseManager  # v4.0: Database operations extraction
    logger.debug("✓ database_manager")
    from .adapters.variables_manager import VariablesPersistenceManager  # v4.0: Variables persistence extraction
    logger.debug("✓ variables_manager")
    from .core.services.task_orchestrator import TaskOrchestrator  # v4.1: Task orchestration extraction
    logger.debug("✓ task_orchestrator")
    from .core.services.optimization_manager import OptimizationManager  # v4.2: Optimization management extraction
    logger.debug("✓ optimization_manager")
    from .adapters.filter_result_handler import FilterResultHandler  # v4.3: Filter result handling extraction
    logger.debug("✓ filter_result_handler")
    from .core.services.app_initializer import AppInitializer  # v4.4: App initialization extraction
    logger.debug("✓ app_initializer")
    from .core.services.datasource_manager import DatasourceManager
    logger.debug("✓ datasource_manager")
    from .core.services.layer_filter_builder import LayerFilterBuilder
    logger.debug("✓ layer_filter_builder")
    from .adapters.layer_refresh_manager import LayerRefreshManager
    logger.debug("✓ layer_refresh_manager")
    from .adapters.layer_task_completion_handler import LayerTaskCompletionHandler
    logger.debug("✓ layer_task_completion_handler")
    from .adapters.layer_validator import LayerValidator
    logger.debug("✓ layer_validator")
    from .core.services.filter_application_service import FilterApplicationService
    logger.debug("✓ filter_application_service")
    HEXAGONAL_AVAILABLE = True
    logger.info("All hexagonal services loaded successfully")
except ImportError as e:
    import traceback
    logger.error(f"Failed to import hexagonal services: {e}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    HEXAGONAL_AVAILABLE = False
    TaskParameterBuilder = LayerRefreshManager = LayerTaskCompletionHandler = None
    LayerLifecycleService = LayerLifecycleConfig = TaskManagementService = TaskManagementConfig = None
    UndoRedoHandler = DatabaseManager = VariablesPersistenceManager = TaskOrchestrator = None
    OptimizationManager = FilterResultHandler = AppInitializer = DatasourceManager = LayerFilterBuilder = None
    LayerValidator = FilterApplicationService = None
    def _init_hexagonal_services(config=None): pass
    def _cleanup_hexagonal_services(): pass
    def _hexagonal_initialized(): return False
    get_filter_service = get_history_service = get_expression_service = validate_expression = parse_expression = None

# Logger already initialized before hexagonal imports (line 78)


def safe_show_message(level, title, message):
    """Safely show a message in QGIS interface, catching RuntimeError if interface is destroyed."""
    try:
        mb = iface.messageBar()
        {'success': mb.pushSuccess, 'info': mb.pushInfo, 'warning': mb.pushWarning, 'critical': mb.pushCritical}.get(level, mb.pushInfo)(title, message)
        return True
    except (RuntimeError, AttributeError): return False


from .filter_mate_dockwidget import FilterMateDockWidget

MESSAGE_TASKS_CATEGORIES = {'filter':'FilterLayers', 'unfilter':'FilterLayers', 'reset':'FilterLayers', 'export':'ExportLayers',
    'add_layers':'ManageLayers', 'remove_layers':'ManageLayers', 'remove_all_layers':'ManageLayers',
    'new_project':'ManageLayers', 'project_read':'ManageLayers', 'reload_layers':'ManageLayers'}

STABILITY_CONSTANTS = {
    'MAX_ADD_LAYERS_QUEUE': 50, 'FLAG_TIMEOUT_MS': 30000, 'LAYER_RETRY_DELAY_MS': 500,
    'UI_REFRESH_DELAY_MS': 300, 'PROJECT_LOAD_DELAY_MS': 2500, 'PROJECT_CHANGE_CLEANUP_DELAY_MS': 300,
    'PROJECT_CHANGE_REINIT_DELAY_MS': 500, 'MAX_RETRIES': 10, 'SIGNAL_DEBOUNCE_MS': 150,
    'POSTGRESQL_EXTRA_DELAY_MS': 1000, 'SPATIALITE_STABILIZATION_MS': 200}

class FilterMateApp:

    PROJECT_LAYERS = {} 

    def _get_layer_lifecycle_service(self):
        """Get or create LayerLifecycleService instance (lazy initialization)."""
        if not hasattr(self, '_lifecycle_service') or self._lifecycle_service is None:
            if LayerLifecycleService:
                config = LayerLifecycleConfig(
                    postgresql_temp_schema=self.app_postgresql_temp_schema if hasattr(self, 'app_postgresql_temp_schema') else 'public',
                    auto_cleanup_enabled=True
                )
                self._lifecycle_service = LayerLifecycleService(config)
            else:
                self._lifecycle_service = None
        return self._lifecycle_service
    
    def _get_task_management_service(self):
        """Get or create TaskManagementService instance (lazy initialization)."""
        if not hasattr(self, '_task_mgmt_service') or self._task_mgmt_service is None:
            if TaskManagementService:
                config = TaskManagementConfig()
                self._task_mgmt_service = TaskManagementService(config)
            else:
                self._task_mgmt_service = None
        return self._task_mgmt_service

    def _get_task_builder(self):
        """Get TaskParameterBuilder instance if available."""
        if TaskParameterBuilder and self.dockwidget:
            return TaskParameterBuilder(dockwidget=self.dockwidget, project_layers=self.PROJECT_LAYERS, config_data=self.CONFIG_DATA)
        return None

    def _filter_usable_layers(self, layers):
        """Return only valid vector layers with available sources."""
        service = self._get_layer_lifecycle_service()
        if service: return service.filter_usable_layers(layers, POSTGRESQL_AVAILABLE)
        # Fallback: minimal validation
        return [l for l in layers if isinstance(l, QgsVectorLayer) and l.isValid() and is_layer_source_available(l)]

    def _on_layers_added(self, layers):
        """Signal handler for layersAdded: ignore broken/invalid layers."""
        import time
        
        # Debounce rapid layer additions
        current_time = time.time() * 1000
        if current_time - self._last_layer_change_timestamp < STABILITY_CONSTANTS['SIGNAL_DEBOUNCE_MS']:
            logger.debug("Debouncing layersAdded signal")
            weak_self = weakref.ref(self)
            QTimer.singleShot(STABILITY_CONSTANTS['SIGNAL_DEBOUNCE_MS'], 
                            lambda: (s := weak_self()) and s._on_layers_added(layers))
            return
        self._last_layer_change_timestamp = current_time
        self._check_and_reset_stale_flags()
        
        # Identify PostgreSQL layers
        all_postgres = [l for l in layers if isinstance(l, QgsVectorLayer) and l.providerType() == 'postgres']
        if all_postgres and not POSTGRESQL_AVAILABLE:
            names = ', '.join([l.name() for l in all_postgres[:3]]) + (f" (+{len(all_postgres) - 3} autres)" if len(all_postgres) > 3 else "")
            show_warning(f"Couches PostgreSQL détectées ({names}) mais psycopg2 n'est pas installé.")
            logger.warning(f"FilterMate: Cannot use {len(all_postgres)} PostgreSQL layer(s) - psycopg2 not available")
        
        filtered = self._filter_usable_layers(layers)
        postgres_pending = [l for l in all_postgres if l.id() not in [f.id() for f in filtered] and not is_sip_deleted(l)]
        
        if not filtered and not postgres_pending:
            logger.info("FilterMate: Ignoring layersAdded (no usable layers)"); return
        
        # Delegate PostgreSQL cleanup/retry to LayerLifecycleService
        service = self._get_layer_lifecycle_service()
        if service and (postgres_to_validate := [l for l in filtered if l.providerType() == 'postgres']):
            service.validate_and_cleanup_postgres_layers_on_add(postgres_to_validate)
        
        if filtered: self.manage_task('add_layers', filtered)
        
        if postgres_pending and service:
            service.schedule_postgres_layer_retry(postgres_pending, self.PROJECT_LAYERS,
                                                 lambda layers: self.manage_task('add_layers', layers),
                                                 STABILITY_CONSTANTS)

    def cleanup(self):
        """Clean up plugin resources on unload or reload. Delegates to LayerLifecycleService."""
        service = self._get_layer_lifecycle_service()
        if service:
            auto_cleanup_enabled = getattr(self.dockwidget, '_pg_auto_cleanup_enabled', True) if self.dockwidget else True
            service.cleanup(session_id=self.session_id, temp_schema=self.app_postgresql_temp_schema, 
                          project_layers=self.PROJECT_LAYERS, dockwidget=self.dockwidget,
                          auto_cleanup_enabled=auto_cleanup_enabled, postgresql_available=POSTGRESQL_AVAILABLE)
        self.PROJECT_LAYERS.clear(); self.project_datasources.clear()
        if HEXAGONAL_AVAILABLE:
            try: _cleanup_hexagonal_services()
            except Exception as e: logger.debug(f"Hexagonal services cleanup (expected during shutdown): {e}")
    
    def get_all_cache_stats(self):
        """
        Get statistics for all registered caches.
        
        Returns dictionary mapping cache names to their statistics.
        Useful for monitoring cache performance and debugging.
        
        Returns:
            dict: Cache name -> CacheStats mapping
            
        Example:
            >>> stats = app.get_all_cache_stats()
            >>> for cache_name, cache_stats in stats.items():
            ...     print(f"{cache_name}: {cache_stats.hits} hits, {cache_stats.misses} misses")
        """
        try:
            from .infrastructure.cache.cache_manager import CacheManager
            
            manager = CacheManager.get_instance()
            all_stats = manager.get_stats()
            
            logger.debug(f"Retrieved stats for {len(all_stats)} caches")
            return all_stats
            
        except Exception as e:
            logger.warning(f"Failed to get cache stats: {e}")
            return {}
    
    def clear_all_caches(self):
        """
        Clear all registered caches.
        
        Useful for debugging or when memory needs to be freed.
        All caches registered in CacheManager will be cleared.
        
        Returns:
            int: Number of caches cleared
            
        Example:
            >>> cleared_count = app.clear_all_caches()
            >>> print(f"Cleared {cleared_count} caches")
        """
        try:
            from .infrastructure.cache.cache_manager import CacheManager
            
            manager = CacheManager.get_instance()
            cleared_count = manager.clear_all_caches()
            
            logger.info(f"✅ Cleared {cleared_count} caches via CacheManager")
            
            # Also push feedback to user
            from qgis.utils import iface
            if iface:
                iface.messageBar().pushSuccess(
                    "FilterMate",
                    f"Cleared {cleared_count} caches"
                )
            
            return cleared_count
            
        except Exception as e:
            logger.error(f"Failed to clear caches: {e}")
            return 0

    def _cleanup_postgresql_session_views(self):
        """Clean up all PostgreSQL materialized views created by this session."""
        service = self._get_layer_lifecycle_service()
        if service: service.cleanup_postgresql_session_views(session_id=self.session_id, temp_schema=self.app_postgresql_temp_schema, project_layers=self.PROJECT_LAYERS, postgresql_available=POSTGRESQL_AVAILABLE)

    def __init__(self, plugin_dir):
        """v4.0 Sprint 16: Initialize FilterMate app with managers, services, and state."""
        self.iface, self.dockwidget, self.flags, self.plugin_dir = iface, None, {}, plugin_dir
        self.appTasks = {"filter":None,"unfilter":None,"reset":None,"export":None,"add_layers":None,"remove_layers":None,"remove_all_layers":None,"new_project":None,"project_read":None}
        self.tasks_descriptions = {'filter':'Filtering data','unfilter':'Unfiltering data','reset':'Reseting data','export':'Exporting data',
                                    'undo':'Undo filter','redo':'Redo filter','add_layers':'Adding layers','remove_layers':'Removing layers',
                                    'remove_all_layers':'Removing all layers','new_project':'New project','project_read':'Existing project loaded','reload_layers':'Reloading layers'}
        
        # History & Favorites
        history_max_size = self._get_history_max_size_from_config()
        self.history_manager = HistoryService(max_depth=history_max_size)
        logger.info(f"FilterMate: HistoryService initialized for undo/redo functionality (max_depth={history_max_size})")
        self._undo_redo_handler = UndoRedoHandler(self.history_manager, lambda: self.PROJECT_LAYERS, lambda: self.PROJECT, lambda: self.iface,
                                                   self._refresh_layers_and_canvas, lambda t, m: iface.messageBar().pushWarning(t, m)) if HEXAGONAL_AVAILABLE and UndoRedoHandler else None
        if self._undo_redo_handler:
            logger.info("FilterMate: UndoRedoHandler initialized (v4.0 migration)")
        self.favorites_manager = FavoritesService()
        logger.info(f"FilterMate: FavoritesService initialized ({self.favorites_manager.get_favorites_count()} favorites)")
        
        # Spatialite cache
        try:
            from .infrastructure.cache import get_cache, cleanup_cache
            self._spatialite_cache = get_cache()
            expired_count = cleanup_cache()
            if expired_count > 0:
                logger.info(f"FilterMate: Cleaned up {expired_count} expired cache entries")
            cache_stats = self._spatialite_cache.get_cache_stats()
            logger.info(f"FilterMate: Spatialite cache initialized ({cache_stats['total_entries']} entries, {cache_stats['db_size_mb']} MB)")
        except Exception as e:
            logger.debug(f"FilterMate: Spatialite cache not available: {e}")
            self._spatialite_cache = None
        
        # PostgreSQL & Hexagonal services
        if POSTGRESQL_AVAILABLE:
            logger.info("FilterMate: PostgreSQL support enabled (psycopg2 available)")
        else:
            logger.warning("FilterMate: PostgreSQL support DISABLED - psycopg2 not installed. Plugin will work with local files (Shapefile, GeoPackage, Spatialite) only. For PostgreSQL layers, install psycopg2.")
        
        # v3.0: Initialize hexagonal architecture services
        if HEXAGONAL_AVAILABLE:
            try:
                _init_hexagonal_services({
                    'history': {'max_depth': history_max_size},
                    'backends': {'postgresql_available': POSTGRESQL_AVAILABLE}
                })
                logger.info("FilterMate: Hexagonal architecture services initialized")
            except Exception as e:
                logger.warning(f"FilterMate: Hexagonal services initialization failed: {e}")
        
        # v4.0.1: Initialize BackendRegistry for hexagonal architecture compliance
        self._backend_registry = None
        try:
            from .adapters.backend_registry import BackendRegistry
            self._backend_registry = BackendRegistry()
            logger.info(f"FilterMate: BackendRegistry initialized (postgresql_available: {self._backend_registry.postgresql_available})")
        except Exception as e:
            logger.warning(f"FilterMate: BackendRegistry not available: {e}")
        
        init_env_vars()
        
        global ENV_VARS
        self.CONFIG_DATA = ENV_VARS["CONFIG_DATA"]
        self._init_feedback_level()
        self.PROJECT = ENV_VARS["PROJECT"]
        self.MapLayerStore, self.db_name = self.PROJECT.layerStore(), 'filterMate_db.sqlite'
        self.db_file_path = os.path.normpath(ENV_VARS["PLUGIN_CONFIG_DIRECTORY"] + os.sep + self.db_name)
        self.project_file_name, self.project_file_path, self.project_uuid = os.path.basename(self.PROJECT.absoluteFilePath()), self.PROJECT.absolutePath(), ''
        
        # DatabaseManager & VariablesPersistenceManager
        self._database_manager = DatabaseManager(ENV_VARS["PLUGIN_CONFIG_DIRECTORY"], self.PROJECT) if HEXAGONAL_AVAILABLE and DatabaseManager else None
        if self._database_manager:
            logger.info("FilterMate: DatabaseManager initialized (v4.0 migration)")
        self._variables_manager = VariablesPersistenceManager(self.get_spatialite_connection, lambda: str(self.project_uuid), lambda: self.PROJECT_LAYERS, return_typed_value,
                                                               lambda layer_id: self._cancel_layer_tasks(layer_id) if hasattr(self, 'dockwidget') and self.dockwidget else None,
                                                               lambda: hasattr(self, 'dockwidget') and self.dockwidget and getattr(self.dockwidget, '_updating_current_layer', False)) if HEXAGONAL_AVAILABLE and VariablesPersistenceManager else None
        if self._variables_manager:
            logger.info("FilterMate: VariablesPersistenceManager initialized (v4.0 migration)")
        
        # Session & Flags
        self.project_datasources, self.app_postgresql_temp_schema, self.app_postgresql_temp_schema_setted = {}, 'filter_mate_temp', False
        import time, hashlib
        self.session_id = hashlib.md5(f"{time.time()}_{os.getpid()}_{id(self)}".encode()).hexdigest()[:8]
        self._signals_connected = self._dockwidget_signals_connected = self._loading_new_project = self._initializing_project = self._processing_queue = self._widgets_ready = False
        self._loading_new_project_timestamp = self._initializing_project_timestamp = self._last_layer_change_timestamp = self._pending_add_layers_tasks = 0
        self._add_layers_queue = []
        self.PROJECT_LAYERS = {}
        
        # Managers v4.1-4.7
        self._task_orchestrator = TaskOrchestrator(lambda: self.dockwidget, lambda: self.PROJECT_LAYERS, lambda: self.CONFIG_DATA, lambda: self.PROJECT,
                                                    self._check_and_reset_stale_flags, self._set_loading_flag, self._set_initializing_flag, self.get_task_parameters,
                                                    self._execute_filter_task, self._execute_layer_task, self.handle_undo, self.handle_redo, self.force_reload_layers,
                                                    self._handle_remove_all_layers, self._handle_project_initialization) if HEXAGONAL_AVAILABLE and TaskOrchestrator else None
        if self._task_orchestrator:
            logger.info("FilterMate: TaskOrchestrator initialized (v4.1 migration)")
        self._optimization_manager = OptimizationManager(lambda: self.dockwidget, lambda: self.PROJECT, lambda: self.PROJECT_LAYERS) if HEXAGONAL_AVAILABLE and OptimizationManager else None
        if self._optimization_manager:
            logger.info("FilterMate: OptimizationManager initialized (v4.2 migration)")
        self._filter_result_handler = FilterResultHandler(self._refresh_layers_and_canvas, self._push_filter_to_history, self._clear_filter_history, self.update_undo_redo_buttons,
                                                           lambda: self.PROJECT_LAYERS, lambda: self.dockwidget, lambda: self.iface) if HEXAGONAL_AVAILABLE and FilterResultHandler else None
        if self._filter_result_handler:
            logger.info("FilterMate: FilterResultHandler initialized (v4.3 migration)")
        self._app_initializer = AppInitializer(self.init_filterMate_db, self.get_spatialite_connection, cleanup_corrupted_layer_filters, self._filter_usable_layers, self.manage_task,
                                                lambda: self.PROJECT_LAYERS, lambda: self.CONFIG_DATA, lambda: self.PROJECT, lambda: self.plugin_dir, self._get_dock_position, lambda: self.iface,
                                                lambda: self.dockwidget, lambda dw: setattr(self, 'dockwidget', dw), lambda: self._task_orchestrator, lambda: self.favorites_manager,
                                                lambda: self._signals_connected, lambda val: setattr(self, '_signals_connected', val), lambda: self._dockwidget_signals_connected,
                                                lambda val: setattr(self, '_dockwidget_signals_connected', val), lambda: self.MapLayerStore, lambda mls: setattr(self, 'MapLayerStore', mls),
                                                self._on_widgets_initialized, self._on_layers_added, self.update_undo_redo_buttons, self.save_variables_from_layer,
                                                self.remove_variables_from_layer, self.save_project_variables) if HEXAGONAL_AVAILABLE and AppInitializer else None
        if self._app_initializer:
            logger.info("FilterMate: AppInitializer initialized (v4.4 migration)")
        
        # v4.5: Initialize DatasourceManager (extracted from FilterMateApp datasource methods)
        if HEXAGONAL_AVAILABLE and DatasourceManager:
            self._datasource_manager = DatasourceManager(
                get_project_callback=lambda: self.PROJECT,
                get_iface_callback=lambda: self.iface,
                get_config_data_callback=lambda: self.CONFIG_DATA,
                set_config_data_callback=lambda cd: setattr(self, 'CONFIG_DATA', cd),
                get_db_file_path_callback=lambda: self.db_file_path,
                get_temp_schema_callback=lambda: self.app_postgresql_temp_schema,
                show_error_callback=lambda msg: show_error(msg),
                show_warning_callback=lambda msg: show_warning(msg)
            )
            logger.info("FilterMate: DatasourceManager initialized (v4.5 migration)")
        else:
            self._datasource_manager = None
        
        # v4.7: Initialize LayerRefreshManager (extracted from _refresh_layers_and_canvas)
        if HEXAGONAL_AVAILABLE and LayerRefreshManager:
            self._layer_refresh_manager = LayerRefreshManager(
                get_iface=lambda: self.iface,
                stabilization_ms=STABILITY_CONSTANTS.get('SPATIALITE_STABILIZATION_MS', 200),
                update_extents_threshold=get_optimization_thresholds(ENV_VARS).get('update_extents_threshold', 50000)
            )
            logger.info("FilterMate: LayerRefreshManager initialized (v4.7 migration)")
        else:
            self._layer_refresh_manager = None
        
        # v4.7: Initialize LayerTaskCompletionHandler (extracted from layer_management_engine_task_completed)
        if HEXAGONAL_AVAILABLE and LayerTaskCompletionHandler:
            self._layer_task_completion_handler = LayerTaskCompletionHandler(
                get_spatialite_connection=self.get_spatialite_connection,
                get_project_uuid=lambda: self.project_uuid,
                get_project=lambda: self.PROJECT,
                get_dockwidget=lambda: self.dockwidget,
                get_project_layers=lambda: self.PROJECT_LAYERS,
                set_project_layers=lambda pl: setattr(self, 'PROJECT_LAYERS', pl),
                get_history_manager=lambda: self.history_manager,
                save_project_variables_callback=self.save_project_variables,
                update_datasource_callback=self.update_datasource,
                get_env_vars=lambda: ENV_VARS,
                warm_query_cache_callback=self._warm_query_cache_for_layers if hasattr(self, '_warm_query_cache_for_layers') else None,
                process_add_layers_queue_callback=self._process_add_layers_queue if hasattr(self, '_process_add_layers_queue') else None,
                refresh_ui_after_project_load_callback=self._refresh_ui_after_project_load if hasattr(self, '_refresh_ui_after_project_load') else None,
                set_loading_flag_callback=self._set_loading_flag if hasattr(self, '_set_loading_flag') else None,
                validate_layer_info_callback=self._validate_layer_info if hasattr(self, '_validate_layer_info') else None,
                update_datasource_for_layer_callback=self._update_datasource_for_layer if hasattr(self, '_update_datasource_for_layer') else None,
                remove_datasource_for_layer_callback=self._remove_datasource_for_layer if hasattr(self, '_remove_datasource_for_layer') else None,
                pending_tasks_counter_callbacks={
                    'get': lambda: self._pending_add_layers_tasks,
                    'decrement': lambda: setattr(self, '_pending_add_layers_tasks', self._pending_add_layers_tasks - 1),
                    'get_queue': lambda: self._add_layers_queue
                },
                stability_constants=STABILITY_CONSTANTS
            )
            logger.info("FilterMate: LayerTaskCompletionHandler initialized (v4.7 migration)")
        else:
            self._layer_task_completion_handler = None
        
        # Sprint 17: Initialize LayerValidator
        if HEXAGONAL_AVAILABLE and LayerValidator:
            self._layer_validator = LayerValidator(postgresql_available=POSTGRESQL_AVAILABLE)
            logger.info("FilterMate: LayerValidator initialized (Sprint 17)")
        else:
            self._layer_validator = None
        
        # Sprint 17: Initialize FilterApplicationService
        if HEXAGONAL_AVAILABLE and FilterApplicationService:
            self._filter_application_service = FilterApplicationService(
                history_manager=self.history_manager,
                get_spatialite_connection=self.get_spatialite_connection,
                get_project_uuid=lambda: self.project_uuid,
                get_project_layers=lambda: self.PROJECT_LAYERS,
                show_warning=lambda t, m: iface.messageBar().pushWarning(t, m)
            )
            logger.info("FilterMate: FilterApplicationService initialized (Sprint 17)")
        else:
            self._filter_application_service = None
        
        # Note: Do NOT call self.run() here - it will be called from filter_mate.py
        # when the user actually activates the plugin to avoid QGIS initialization race conditions

    def _get_history_max_size_from_config(self):
        """Get history.max_history_size from config (default: 100)."""
        try:
            from .config.config import ENV_VARS
            config_data = ENV_VARS.get("CONFIG_DATA", {})
            history_config = config_data.get("APP", {}).get("OPTIONS", {}).get("HISTORY", {})
            max_size = history_config.get("max_history_size", {}).get("value", 100)
            return int(max_size)
        except Exception as e:
            logger.warning(f"FilterMate: Could not get history max_size from config: {e}. Using default 100.")
            return 100

    def _init_feedback_level(self):
        """Initialize feedback verbosity level from config.json."""
        try:
            from .config.feedback_config import set_feedback_level_from_string
            
            feedback_level = self.CONFIG_DATA.get("APP", {}).get("DOCKWIDGET", {}).get("FEEDBACK_LEVEL", {}).get("value", "normal")
            
            set_feedback_level_from_string(feedback_level)
            logger.info(f"FilterMate: Feedback level set to '{feedback_level}'")
            
        except Exception as e:
            logger.warning(f"FilterMate: Could not set feedback level: {e}. Using default 'normal'.")

    def _get_dock_position(self):
        """Get Qt.DockWidgetArea from config.DOCK_POSITION (default: right)."""
        try:
            dock_position_str = self.CONFIG_DATA.get("APP", {}).get("DOCKWIDGET", {}).get("DOCK_POSITION", {}).get("value", "right")
            
            position_mapping = {
                "left": Qt.LeftDockWidgetArea,
                "right": Qt.RightDockWidgetArea,
                "top": Qt.TopDockWidgetArea,
                "bottom": Qt.BottomDockWidgetArea,
            }
            
            dock_position = position_mapping.get(dock_position_str.lower(), Qt.RightDockWidgetArea)
            logger.debug(f"FilterMate: Dock position configured as '{dock_position_str}'")
            return dock_position
            
        except Exception as e:
            logger.warning(f"FilterMate: Could not get dock position: {e}. Using default 'right'.")
            return Qt.RightDockWidgetArea

    def _check_and_reset_stale_flags(self):
        """Check for stale flags that might block operations and reset them. Returns True if any flags were reset."""
        import time; current_time = time.time() * 1000; timeout = STABILITY_CONSTANTS['FLAG_TIMEOUT_MS']; flags_reset = False
        # Check _loading_new_project flag timeout
        if self._loading_new_project:
            if self._loading_new_project_timestamp > 0 and (elapsed := current_time - self._loading_new_project_timestamp) > timeout:
                logger.warning(f"🔧 STABILITY: Resetting stale _loading_new_project flag (elapsed: {elapsed:.0f}ms > {timeout}ms)")
                self._loading_new_project = False; self._loading_new_project_timestamp = 0; flags_reset = True
            elif self._loading_new_project_timestamp <= 0: self._loading_new_project_timestamp = current_time
        # Check _initializing_project flag timeout
        if self._initializing_project:
            if self._initializing_project_timestamp > 0 and (elapsed := current_time - self._initializing_project_timestamp) > timeout:
                logger.warning(f"🔧 STABILITY: Resetting stale _initializing_project flag (elapsed: {elapsed:.0f}ms > {timeout}ms)")
                self._initializing_project = False; self._initializing_project_timestamp = 0; flags_reset = True
            elif self._initializing_project_timestamp <= 0: self._initializing_project_timestamp = current_time
        # Check queue sizes
        max_queue = STABILITY_CONSTANTS['MAX_ADD_LAYERS_QUEUE']
        if len(self._add_layers_queue) > max_queue: self._add_layers_queue = self._add_layers_queue[-max_queue:]; flags_reset = True
        if self._pending_add_layers_tasks < 0 or self._pending_add_layers_tasks > 10: self._pending_add_layers_tasks = 0; flags_reset = True
        return flags_reset

    def _set_flag_with_timestamp(self, flag_name: str, value: bool):
        """Set flag with timestamp tracking (loading/initializing)."""
        import time
        setattr(self, flag_name, value)
        setattr(self, f"{flag_name}_timestamp", time.time() * 1000 if value else 0)

    def _set_loading_flag(self, loading: bool):
        """Set _loading_new_project flag with timestamp tracking."""
        self._set_flag_with_timestamp('_loading_new_project', loading)

    def _set_initializing_flag(self, initializing: bool):
        """Set _initializing_project flag with timestamp tracking."""
        self._set_flag_with_timestamp('_initializing_project', initializing)

    def force_reload_layers(self):
        """Force a complete reload of all layers. Delegates to LayerLifecycleService."""
        global ENV_VARS
        
        service = self._get_layer_lifecycle_service()
        if not service:
            logger.error("LayerLifecycleService not available, cannot force reload layers")
            return
        
        # Update project reference
        init_env_vars()
        self.PROJECT = ENV_VARS["PROJECT"]
        self.MapLayerStore = self.PROJECT.layerStore()
        
        service.force_reload_layers(
            cancel_tasks_callback=self._safe_cancel_all_tasks,
            reset_flags_callback=lambda: (
                self._check_and_reset_stale_flags(),
                self._set_loading_flag(False),
                self._set_initializing_flag(False),
                setattr(self, '_add_layers_queue', []),
                setattr(self, '_pending_add_layers_tasks', 0)
            ),
            init_db_callback=self.init_filterMate_db,
            manage_task_callback=lambda layers: self.manage_task('add_layers', layers),
            project_layers=self.PROJECT_LAYERS,
            dockwidget=self.dockwidget,
            stability_constants=STABILITY_CONSTANTS
        )

    def run(self):
        """Initialize and display the FilterMate dockwidget. Delegates to AppInitializer."""
        print(f"DEBUG: FilterMateApp.run() called")
        print(f"DEBUG: HEXAGONAL_AVAILABLE = {HEXAGONAL_AVAILABLE}")
        print(f"DEBUG: self._app_initializer = {self._app_initializer}")
        
        USE_APP_INITIALIZER = True
        if USE_APP_INITIALIZER and self._app_initializer is not None:
            logger.info(f"v4.4: Delegating application initialization to AppInitializer")
            print(f"DEBUG: Calling AppInitializer.initialize_application()")
            try:
                is_first_run = (self.dockwidget is None)
                success = self._app_initializer.initialize_application(is_first_run)
                print(f"DEBUG: AppInitializer returned {success}")
                if success:
                    # v4.5: Ensure signal connections even after AppInitializer success
                    # This is the simplified direct connection system
                    self._connect_layer_store_signals()
                    self._connect_dockwidget_signals()
                    return
                else:
                    logger.error(f"AppInitializer returned False - falling back to legacy initialization")
            except Exception as e:
                logger.error(f"AppInitializer raised exception: {e}")
                print(f"DEBUG: AppInitializer exception: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                traceback.print_exc()
        
        # Fallback: Legacy initialization when AppInitializer not available or fails
        print(f"DEBUG: Using legacy fallback initialization")
        logger.warning("Using legacy initialization - AppInitializer not available")
        
        # Basic initialization: create and show dockwidget
        if self.dockwidget is None:
            try:
                # Initialize database first
                self.init_filterMate_db()
                
                from .filter_mate_dockwidget import FilterMateDockWidget
                self.dockwidget = FilterMateDockWidget(
                    project_layers=self.PROJECT_LAYERS,
                    plugin_dir=self.plugin_dir,
                    config_data=self.CONFIG_DATA,
                    project=self.PROJECT
                )
                
                # CRITICAL: Initialize UI from .ui file
                self.dockwidget.setupUi(self.dockwidget)
                
                logger.info("Created FilterMateDockWidget (legacy mode)")
            except Exception as e:
                logger.error(f"Failed to create dockwidget: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                traceback.print_exc()
                show_error("FilterMate", f"Failed to create dockwidget: {e}")
                return
        
        # Show the dockwidget
        try:
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
            self.dockwidget.show()
            logger.info("Dockwidget displayed (legacy mode)")
        except Exception as e:
            logger.error(f"Failed to show dockwidget: {e}")
            show_error("FilterMate", f"Failed to display dockwidget: {e}")
        
        # CRITICAL: Ensure signal connections are established
        # This is the simplified direct connection system (v4.5)
        self._connect_layer_store_signals()
        self._connect_dockwidget_signals()

    # ========================================
    # SIGNAL CONNECTION SYSTEM (v4.5 Simplified)
    # ========================================
    # 
    # FilterMate uses a layered signal connection architecture:
    # 
    # 1. LAYER STORE SIGNALS (MapLayerStore):
    #    - layersAdded -> _on_layers_added() -> manage_task('add_layers')
    #    - layersWillBeRemoved -> manage_task('remove_layers')
    #    - allLayersRemoved -> manage_task('remove_all_layers')
    #    Connected via: _connect_layer_store_signals()
    # 
    # 2. DOCKWIDGET SIGNALS:
    #    - launchingTask -> manage_task(task_name)
    #    - currentLayerChanged -> update_undo_redo_buttons()
    #    - settingLayerVariable -> save_variables_from_layer()
    #    - resettingLayerVariable -> remove_variables_from_layer()
    #    - settingProjectVariables -> save_project_variables()
    #    - widgetsInitialized -> _on_widgets_initialized()
    #    Connected via: _connect_dockwidget_signals()
    # 
    # 3. WIDGET SIGNALS (in dockwidget):
    #    Managed by ConfigurationManager.configure_widgets()
    #    Connected/disconnected via manageSignal()
    # 
    # Connection is done directly here (not via AppInitializer callbacks)
    # to ensure reliability and simplify debugging.
    # ========================================

    def _connect_layer_store_signals(self):
        """
        Connect layer store signals for layer management.
        
        Called once during initialization and after project changes.
        Uses flag to prevent duplicate connections.
        """
        if self._signals_connected:
            return
        
        if not self.MapLayerStore:
            logger.warning("Cannot connect layer store signals: MapLayerStore is None")
            return
        
        logger.debug("Connecting layer store signals (layersAdded, layersWillBeRemoved...)")
        
        self.MapLayerStore.layersAdded.connect(self._on_layers_added)
        self.MapLayerStore.layersWillBeRemoved.connect(
            lambda layers: self.manage_task('remove_layers', layers)
        )
        self.MapLayerStore.allLayersRemoved.connect(
            lambda: self.manage_task('remove_all_layers')
        )
        
        self._signals_connected = True
        logger.info("✓ Layer store signals connected")

    def _connect_dockwidget_signals(self):
        """
        Connect dockwidget signals for task management and variable persistence.
        
        CRITICAL: These connections enable:
        - Task launching (filter, unfilter, export)
        - Undo/redo button state updates
        - Layer variable persistence
        - Project variable persistence
        
        Called once after dockwidget creation.
        """
        if self._dockwidget_signals_connected:
            return
        
        if not self.dockwidget:
            logger.warning("Cannot connect dockwidget signals: dockwidget is None")
            return
        
        logger.debug("Connecting dockwidget signals...")
        
        # Task launching signal - triggers filter/unfilter/export tasks
        self.dockwidget.launchingTask.connect(
            lambda task_name: self.manage_task(task_name)
        )
        # FIX 2026-01-15: Log signal connection confirmation
        logger.info(f"✓ Connected launchingTask signal")
        
        # Current layer changed - update undo/redo buttons
        self.dockwidget.currentLayerChanged.connect(
            self.update_undo_redo_buttons
        )
        
        # Layer variable signals - persist layer properties
        self.dockwidget.settingLayerVariable.connect(
            lambda layer, properties: self._safe_layer_operation(
                layer, properties, self.save_variables_from_layer
            )
        )
        self.dockwidget.resettingLayerVariable.connect(
            lambda layer, properties: self._safe_layer_operation(
                layer, properties, self.remove_variables_from_layer
            )
        )
        self.dockwidget.resettingLayerVariableOnError.connect(
            lambda layer, properties: self._safe_layer_operation(
                layer, properties, self.remove_variables_from_layer
            )
        )
        
        # Project variable signals - persist project-level settings
        self.dockwidget.settingProjectVariables.connect(
            self.save_project_variables
        )
        self.PROJECT.fileNameChanged.connect(
            lambda: self.save_project_variables()
        )
        
        # Widget initialization signal - sync state when widgets ready
        self.dockwidget.widgetsInitialized.connect(
            self._on_widgets_initialized
        )
        
        self._dockwidget_signals_connected = True
        logger.info("✓ Dockwidget signals connected")

    def _disconnect_all_signals(self):
        """
        Disconnect all signals during cleanup or project change.
        
        Called before plugin unload or project change to prevent
        access violations from stale signal connections.
        """
        # Disconnect layer store signals
        if self._signals_connected and self.MapLayerStore:
            try:
                self.MapLayerStore.layersAdded.disconnect()
                self.MapLayerStore.layersWillBeRemoved.disconnect()
                self.MapLayerStore.allLayersRemoved.disconnect()
                self._signals_connected = False
                logger.debug("Layer store signals disconnected")
            except (TypeError, RuntimeError) as e:
                logger.debug(f"Could not disconnect layer store signals: {e}")
        
        # Disconnect dockwidget signals
        if self._dockwidget_signals_connected and self.dockwidget:
            try:
                self.dockwidget.launchingTask.disconnect()
                self.dockwidget.currentLayerChanged.disconnect()
                self.dockwidget.settingLayerVariable.disconnect()
                self.dockwidget.resettingLayerVariable.disconnect()
                self.dockwidget.resettingLayerVariableOnError.disconnect()
                self.dockwidget.settingProjectVariables.disconnect()
                self.dockwidget.widgetsInitialized.disconnect()
                self._dockwidget_signals_connected = False
                logger.debug("Dockwidget signals disconnected")
            except (TypeError, RuntimeError) as e:
                logger.debug(f"Could not disconnect dockwidget signals: {e}")

    def _safe_layer_operation(self, layer, properties, operation):
        """Safely execute a layer operation by deferring to Qt event loop and re-fetching layer."""
        from qgis.PyQt.QtCore import QTimer
        try:
            if layer is None or sip.isdeleted(layer): return
            layer_id = layer.id()
            if not layer_id: return
        except (RuntimeError, OSError, SystemError): return
        # This ensures Qt internal state is stable and layer deletion is complete
        # (if it was going to be deleted). Using singleShot(0, ...) queues the
        # callback to run as soon as control returns to the event loop.
        def deferred_operation():
            # CRASH FIX (v2.3.18): Check if QGIS is still alive before any operations
            if not is_qgis_alive():
                logger.debug(f"_safe_layer_operation: QGIS is shutting down, skipping")
                return
            
            # CRASH FIX (v2.4.13): Check if dockwidget is in the middle of a layer change
            # This prevents access violations when setLayerVariable is called during
            # _reconnect_layer_signals which can process Qt events and cause instability.
            if hasattr(self, 'dockwidget') and self.dockwidget is not None:
                if getattr(self.dockwidget, '_updating_current_layer', False):
                    logger.debug(f"_safe_layer_operation: layer change in progress, re-deferring operation for {layer_id}")
                    # Re-schedule with a small delay to allow layer change to complete
                    QTimer.singleShot(50, deferred_operation)
                    return
            
            # Re-fetch fresh layer reference from project in the deferred context
            fresh_layer = QgsProject.instance().mapLayer(layer_id)
            if fresh_layer is None:
                logger.debug(f"_safe_layer_operation: layer {layer_id} no longer in project, skipping")
                return
            
            # CRASH FIX (v2.4.13): Additional sip check before validation
            if sip.isdeleted(fresh_layer):
                logger.debug(f"_safe_layer_operation: fresh layer is sip deleted, skipping")
                return
            
            # Final validation before calling operation
            if not is_valid_layer(fresh_layer):
                logger.debug(f"_safe_layer_operation: fresh layer is invalid, skipping")
                return
            
            # Execute the operation with the fresh layer reference
            try:
                operation(fresh_layer, properties)
            except (RuntimeError, OSError, SystemError) as e:
                logger.warning(f"_safe_layer_operation: operation failed: {e}")
        
        QTimer.singleShot(0, deferred_operation)

    def get_spatialite_connection(self):
        """Get a Spatialite connection via DatasourceManager or fallback."""
        if self._datasource_manager:
            try:
                return self._datasource_manager.get_spatialite_connection()
            except Exception as e:
                logger.error(f"DatasourceManager connection failed: {e}, using fallback")
        
        # Fallback: direct connection
        try:
            from .infrastructure.utils import spatialite_connect
            return spatialite_connect(self.db_file_path)
        except Exception as e:
            logger.error(f"Spatialite connection fallback failed: {e}")
            return None
    
    def _handle_remove_all_layers(self):
        """Delegates to LayerLifecycleService.handle_remove_all_layers()."""
        service = self._get_layer_lifecycle_service()
        if not service:
            logger.error("LayerLifecycleService not available, cannot handle remove all layers")
            return
        
        service.handle_remove_all_layers(
            cancel_tasks_callback=self._safe_cancel_all_tasks,
            dockwidget=self.dockwidget
        )
    
    def _handle_project_initialization(self, task_name):
        """Handle project read/new project initialization. Delegates to LayerLifecycleService."""
        global ENV_VARS
        
        service = self._get_layer_lifecycle_service()
        if not service:
            logger.error("LayerLifecycleService not available, cannot handle project initialization")
            return
        
        # Handle signal reconnection logic (app-specific, not in service)
        old_layer_store = self.MapLayerStore
        new_layer_store = self.PROJECT.layerStore() if hasattr(self, 'PROJECT') and self.PROJECT else None
        
        if new_layer_store and self._signals_connected:
            logger.info(f"FilterMate: Disconnecting old layer store signals for {task_name}")
            try:
                old_layer_store.layersAdded.disconnect()
                old_layer_store.layersWillBeRemoved.disconnect()
                old_layer_store.allLayersRemoved.disconnect()
                logger.info("FilterMate: Old layer store signals disconnected")
            except (TypeError, RuntimeError) as e:
                logger.debug(f"Could not disconnect old signals (expected): {e}")
            
            self.MapLayerStore = new_layer_store
            self.MapLayerStore.layersAdded.connect(self._on_layers_added)
            self.MapLayerStore.layersWillBeRemoved.connect(lambda layers: self.manage_task('remove_layers', layers))
            self.MapLayerStore.allLayersRemoved.connect(lambda: self.manage_task('remove_all_layers'))
            logger.info("FilterMate: Layer store signals reconnected to new project")
        elif new_layer_store:
            logger.debug("FilterMate: Updating MapLayerStore reference (signals not yet connected)")
            self.MapLayerStore = new_layer_store
        
        # Clear old PROJECT_LAYERS and reset datasources
        self.PROJECT_LAYERS = {}
        self.project_datasources = {'postgresql': {}, 'spatialite': {}, 'ogr': {}}
        self.app_postgresql_temp_schema_setted = False
        
        # v4.5: Sync project_datasources with DatasourceManager
        if self._datasource_manager:
            self._datasource_manager.set_project_datasources(self.project_datasources)
        
        # Load favorites from new project
        if hasattr(self, 'favorites_manager'):
            self.favorites_manager.load_from_project()
            logger.info(f"FilterMate: Favorites loaded for {task_name} ({self.favorites_manager.count} favorites)")
        
        service.handle_project_initialization(
            task_name=task_name,
            is_initializing=self._initializing_project,
            is_loading=self._loading_new_project,
            dockwidget=self.dockwidget,
            check_reset_flags_callback=self._check_and_reset_stale_flags,
            set_initializing_flag_callback=self._set_initializing_flag,
            set_loading_flag_callback=self._set_loading_flag,
            cancel_tasks_callback=self._safe_cancel_all_tasks,
            init_env_vars_callback=lambda: (init_env_vars(), setattr(self, 'PROJECT', ENV_VARS["PROJECT"])),
            get_project_callback=lambda: self.PROJECT,
            init_db_callback=self.init_filterMate_db,
            manage_task_callback=lambda layers: self.manage_task('add_layers', layers),
            temp_schema=self.app_postgresql_temp_schema,
            stability_constants=STABILITY_CONSTANTS
        )

    # ========================================
    # TASK EXECUTION METHODS (v4.1)
    # ========================================
    
    def _execute_filter_task(self, task_name: str, task_parameters: dict):
        """Execute filter/unfilter/reset task (callback for TaskOrchestrator)."""
        from .core.tasks import FilterEngineTask
        
        logger.info(f"⚙️ _execute_filter_task CALLED: task_name={task_name}")
        
        if self.dockwidget is None or self.dockwidget.current_layer is None:
            logger.error(f"❌ Cannot execute filter task: dockwidget={self.dockwidget is not None}, current_layer={self.dockwidget.current_layer is not None if self.dockwidget else False}")
            return
        
        current_layer = self.dockwidget.current_layer
        
        # Create task with backend registry for hexagonal architecture (v4.0.1)
        logger.info(f"📦 Creating FilterEngineTask with {len(task_parameters.get('task', {}).get('layers', []))} layers")
        self.appTasks[task_name] = FilterEngineTask(
            self.tasks_descriptions[task_name], 
            task_name, 
            task_parameters,
            backend_registry=self._backend_registry  # v4.0.1: Hexagonal DI
        )
        logger.info(f"✓ FilterEngineTask created: {self.appTasks[task_name].description()}")
        
        # Get layers from task parameters
        layers = []
        layers_props = [layer_infos for layer_infos in task_parameters["task"]["layers"]]
        layers_ids = [layer_props["layer_id"] for layer_props in layers_props]
        for layer_props in layers_props:
            temp_layers = self.PROJECT.mapLayersByName(layer_props["layer_name"])
            for temp_layer in temp_layers:
                if temp_layer.id() in layers_ids:
                    layers.append(temp_layer)
        
        # Save current layer before filtering
        self._save_current_layer_before_filter()
        
        # Set filtering protection flags
        self._set_filter_protection_flags(current_layer)
        
        # Show backend info message
        self._show_filter_start_message(task_name, task_parameters, layers_props, layers, current_layer)
        
        # Connect completion handler
        self.appTasks[task_name].taskCompleted.connect(
            lambda tn=task_name, cl=current_layer, tp=task_parameters: 
                self.filter_engine_task_completed(tn, cl, tp)
        )
        
        # Cancel conflicting tasks and add to task manager
        self._cancel_conflicting_tasks()
        QgsApplication.taskManager().addTask(self.appTasks[task_name])
    
    def _execute_layer_task(self, task_name: str, task_parameters: dict):
        """Execute layer management task (callback for TaskOrchestrator)."""
        from .core.tasks import LayersManagementEngineTask
        
        self.appTasks[task_name] = LayersManagementEngineTask(
            self.tasks_descriptions[task_name], 
            task_name, 
            task_parameters
        )
        
        # Configure task based on type
        if task_name == "add_layers":
            self.appTasks[task_name].setDependentLayers([
                layer for layer in task_parameters["task"]["layers"]
            ])
            if self.dockwidget is not None:
                self.appTasks[task_name].begun.connect(
                    self.dockwidget.disconnect_widgets_signals
                )
        elif task_name == "remove_layers":
            self.appTasks[task_name].begun.connect(self.on_remove_layer_task_begun)
        
        # Connect signals with Qt.QueuedConnection
        self.appTasks[task_name].resultingLayers.connect(
            lambda result_project_layers, tn=task_name: 
                self.layer_management_engine_task_completed(result_project_layers, tn),
            Qt.QueuedConnection
        )
        self.appTasks[task_name].savingLayerVariable.connect(
            lambda layer, variable_key, value_typped, type_returned: 
                self.saving_layer_variable(layer, variable_key, value_typped, type_returned),
            Qt.QueuedConnection
        )
        self.appTasks[task_name].removingLayerVariable.connect(
            lambda layer, variable_key: 
                self.removing_layer_variable(layer, variable_key),
            Qt.QueuedConnection
        )
        self.appTasks[task_name].taskTerminated.connect(
            lambda tn=task_name: self._handle_layer_task_terminated(tn),
            Qt.QueuedConnection
        )
        
        # Add to task manager
        QgsApplication.taskManager().addTask(self.appTasks[task_name])
    
    def _legacy_dispatch_task(self, task_name: str, data=None):
        """Legacy task dispatcher fallback when TaskOrchestrator unavailable."""
        logger.debug(f"_legacy_dispatch_task: {task_name}")
        
        # Get task parameters
        logger.info(f"🔧 Building task parameters for {task_name}...")
        task_parameters = self.get_task_parameters(task_name, data)
        if task_parameters is None:
            logger.error(f"❌ Cannot execute task {task_name}: parameters are None")
            logger.error(f"   current_layer={self.dockwidget.current_layer if self.dockwidget else None}")
            logger.error(f"   widgets_ready={self._widgets_ready}")
            logger.error(f"   dockwidget_ready={self._is_dockwidget_ready_for_filtering()}")
            return
        logger.info(f"✓ Task parameters built successfully")
        
        # Dispatch based on task type
        # E7-S1: Wrap all dispatches in try/except to prevent total failure
        try:
            if task_name in ('filter', 'unfilter', 'reset'):
                # Filter operations
                self._execute_filter_task(task_name, task_parameters)
            elif task_name in ('add_layers', 'remove_layers'):
                # Layer management operations
                self._execute_layer_task(task_name, task_parameters)
            elif task_name == 'remove_all_layers':
                self._handle_remove_all_layers()
            elif task_name in ('new_project', 'project_read'):
                self._handle_project_initialization(task_name)
            elif task_name == 'undo':
                self.handle_undo()
            elif task_name == 'redo':
                self.handle_redo()
            else:
                logger.warning(f"_legacy_dispatch_task: Unknown task {task_name}")
        except Exception as e:
            logger.error(f"_legacy_dispatch_task failed for {task_name}: {e}", exc_info=True)
            iface.messageBar().pushCritical("FilterMate", f"Erreur lors de l'exécution de {task_name}: {str(e)}")
    
    def _show_degraded_mode_warning(self):
        """Show one-time warning that plugin is running in degraded mode."""
        if hasattr(self, '_degraded_mode_warning_shown'):
            return  # Already shown
        
        # Mark as shown
        self._degraded_mode_warning_shown = True
        
        # Show non-blocking warning message
        try:
            iface.messageBar().pushWarning(
                "FilterMate",
                "Plugin fonctionne en mode dégradé (services hexagonaux indisponibles). "
                "Performance réduite possible."
            )
            logger.warning("FilterMate running in DEGRADED MODE - hexagonal services unavailable")
        except Exception as e:
            logger.debug(f"Could not show degraded mode warning: {e}")
    
    def _save_current_layer_before_filter(self):
        """Save current layer reference before filtering to restore after."""
        self._current_layer_before_filter = self.dockwidget.current_layer if self.dockwidget else None
        if self._current_layer_before_filter:
            try:
                self._current_layer_id_before_filter = self._current_layer_before_filter.id()
                logger.info(f"v4.1: 💾 Saved current_layer before filtering")
            except (RuntimeError, AttributeError):
                self._current_layer_id_before_filter = None
        else:
            self._current_layer_id_before_filter = None
    
    def _set_filter_protection_flags(self, current_layer):
        """Set protection flags and disconnect signals during filtering."""
        if not self.dockwidget: return
        if self._current_layer_id_before_filter: self.dockwidget._saved_layer_id_before_filter = self._current_layer_id_before_filter
        self.dockwidget._filtering_in_progress = True
        try:
            self.dockwidget.manageSignal(["FILTERING", "CURRENT_LAYER"], 'disconnect')
            self.dockwidget.comboBox_filtering_current_layer.blockSignals(True)
            self.dockwidget.manageSignal(["QGIS", "LAYER_TREE_VIEW"], 'disconnect')
        except Exception:  # Signal may already be disconnected - expected during filtering protection
            pass
    
    def _show_filter_start_message(self, task_name, task_parameters, layers_props, layers, current_layer):
        """Show informational message about filtering operation starting."""
        # Determine dominant backend from distant layers
        distant_types = [lp.get("layer_provider_type", "unknown") for lp in layers_props]
        provider_type = ('spatialite' if 'spatialite' in distant_types else
                        'postgresql' if 'postgresql' in distant_types else
                        distant_types[0] if distant_types else
                        task_parameters["infos"].get("layer_provider_type", "unknown"))
        
        # Check for forced backends
        is_fallback = False
        if forced := (getattr(self.dockwidget, 'forced_backends', {}) if self.dockwidget else {}):
            all_ids = [current_layer.id()] + [l.id() for l in layers]
            forced_types = set(forced.get(lid) for lid in all_ids if lid in forced)
            if len(forced_types) == 1 and None not in forced_types:
                provider_type = list(forced_types)[0]
                is_fallback = (provider_type == 'ogr')
        
        # Check PostgreSQL fallback
        if not is_fallback and provider_type == 'postgresql':
            is_fallback = task_parameters["infos"].get("postgresql_connection_available", True) is False
        
        show_backend_info(provider_type, len(layers) + 1, operation=task_name, is_fallback=is_fallback)
    
    def _cancel_conflicting_tasks(self):
        """Cancel any conflicting filter tasks that are currently running."""
        try:
            active_tasks = QgsApplication.taskManager().activeTasks()
            for active_task in active_tasks:
                key_active_task = [k for k, v in self.tasks_descriptions.items() 
                                   if v == active_task.description()]
                if key_active_task and key_active_task[0] in ('filter', 'reset', 'unfilter'):
                    active_task.cancel()
        except (IndexError, KeyError, AttributeError):
            pass

    def manage_task(self, task_name, data=None):
        """
        Orchestrate FilterMate tasks via TaskOrchestrator.
        
        v4.1.0: Restored from before_migration with full guards and protections.
        """
        # FIX 2026-01-17: CRITICAL - Use print() for visibility (logger.info not visible in console)
        print(f"🚀 manage_task RECEIVED: task_name={task_name}, data={data is not None}")
        print(f"   STEP 1: Checking task_name validity...")
        
        assert task_name in list(self.tasks_descriptions.keys()), f"Unknown task: {task_name}"
        print(f"   ✓ STEP 1 PASSED: task_name '{task_name}' is valid")
        
        # v4.1.0: STABILITY FIX - Check and reset stale flags before processing
        print(f"   STEP 2: Checking and resetting stale flags...")
        self._check_and_reset_stale_flags()
        print(f"   ✓ STEP 2 PASSED: stale flags checked")
        
        # v4.1.0: CRITICAL - Skip layersAdded signals during project initialization
        print(f"   STEP 3: Checking if add_layers during init...")
        if task_name == 'add_layers' and self._initializing_project:
            logger.debug("Skipping add_layers - project initialization in progress")
            print(f"   ❌ STEP 3 BLOCKED: add_layers during init - RETURNING")
            return
        print(f"   ✓ STEP 3 PASSED: not add_layers during init")
        
        # v4.1.0: STABILITY FIX - Queue concurrent add_layers tasks
        print(f"   STEP 4: Checking add_layers queueing...")
        if task_name == 'add_layers':
            max_queue_size = STABILITY_CONSTANTS.get('MAX_ADD_LAYERS_QUEUE', 5)
            if self._pending_add_layers_tasks > 0:
                if len(self._add_layers_queue) >= max_queue_size:
                    logger.warning(f"⚠️ STABILITY: add_layers queue full ({max_queue_size}), dropping oldest")
                    self._add_layers_queue.pop(0)
                logger.info(f"Queueing add_layers - {self._pending_add_layers_tasks} task(s) in progress")
                self._add_layers_queue.append(data)
                return
            self._pending_add_layers_tasks += 1
            logger.debug(f"Starting add_layers (pending: {self._pending_add_layers_tasks})")
        print(f"   ✓ STEP 4 PASSED: add_layers queue handled")
        
        # v4.1.0: Guard - Ensure dockwidget is initialized for most tasks
        print(f"   STEP 5: Checking dockwidget initialization...")
        print(f"      task_name={task_name}, dockwidget={self.dockwidget is not None}")
        if self.dockwidget:
            print(f"      widgets_initialized={hasattr(self.dockwidget, 'widgets_initialized') and self.dockwidget.widgets_initialized}")
        if task_name not in ('remove_all_layers', 'project_read', 'new_project', 'add_layers'):
            if self.dockwidget is None or not hasattr(self.dockwidget, 'widgets_initialized') or not self.dockwidget.widgets_initialized:
                logger.warning(f"Task '{task_name}' called before dockwidget initialization, deferring by 500ms...")
                print(f"   ❌ STEP 5 BLOCKED: dockwidget not initialized - DEFERRING")
                weak_self = weakref.ref(self)
                captured_task_name, captured_data = task_name, data
                def safe_deferred_task():
                    strong_self = weak_self()
                    if strong_self is not None:
                        strong_self.manage_task(captured_task_name, captured_data)
                QTimer.singleShot(500, safe_deferred_task)
                return
        print(f"   ✓ STEP 5 PASSED: dockwidget initialized")
        
        # v4.1.0: CRITICAL - For filtering tasks, ensure widgets are ready with retry logic
        print(f"   STEP 6: Checking if filtering task needs widget readiness check...")
        if task_name in ('filter', 'unfilter', 'reset'):
            print(f"      YES - This is a filtering task, checking readiness...")
            if not hasattr(self, '_filter_retry_count'):
                self._filter_retry_count = {}
            
            retry_key = f"{task_name}_{id(data)}"
            retry_count = self._filter_retry_count.get(retry_key, 0)
            
            print(f"      Calling _is_dockwidget_ready_for_filtering()...")
            is_ready = self._is_dockwidget_ready_for_filtering()
            print(f"      Result: is_ready={is_ready}, retry_count={retry_count}")
            
            if not is_ready:
                if retry_count >= 10:  # Max 10 retries = 5 seconds
                    logger.error(f"❌ GIVING UP: Task '{task_name}' not ready after {retry_count} retries")
                    print(f"   ❌ STEP 6 BLOCKED: Max retries reached - GIVING UP")
                    iface.messageBar().pushCritical(
                        "FilterMate ERROR",
                        f"Impossible d'exécuter {task_name}: initialisation des widgets échouée."
                    )
                    self._filter_retry_count[retry_key] = 0
                    # EMERGENCY FALLBACK
                    if hasattr(self.dockwidget, 'widgets_initialized') and self.dockwidget.widgets_initialized:
                        logger.warning("⚠️ EMERGENCY: Forcing _widgets_ready = True")
                        self._widgets_ready = True
                        weak_self = weakref.ref(self)
                        captured_tn, captured_d = task_name, data
                        def safe_emergency_retry():
                            strong_self = weak_self()
                            if strong_self is not None:
                                strong_self.manage_task(captured_tn, captured_d)
                        QTimer.singleShot(100, safe_emergency_retry)
                    return
                
                self._filter_retry_count[retry_key] = retry_count + 1
                logger.warning(f"Task '{task_name}' deferring 500ms (attempt {retry_count + 1}/10)")
                print(f"   ❌ STEP 6 BLOCKED: Not ready - DEFERRING (attempt {retry_count + 1}/10)")
                weak_self = weakref.ref(self)
                captured_tn, captured_d = task_name, data
                def safe_filter_retry():
                    strong_self = weak_self()
                    if strong_self is not None:
                        strong_self.manage_task(captured_tn, captured_d)
                QTimer.singleShot(500, safe_filter_retry)
                return
            else:
                # Success! Reset counter
                self._filter_retry_count[retry_key] = 0
                print(f"      ✓ Widgets ready! Proceeding...")
        print(f"   ✓ STEP 6 PASSED: filtering readiness check complete")
        
        # Sync PROJECT_LAYERS from dockwidget
        print(f"   STEP 7: Syncing PROJECT_LAYERS from dockwidget...")
        if self.dockwidget is not None:
            self.PROJECT_LAYERS = self.dockwidget.PROJECT_LAYERS
            self.CONFIG_DATA = self.dockwidget.CONFIG_DATA
        print(f"   ✓ STEP 7 PASSED: PROJECT_LAYERS synced")
        
        # Dispatch via TaskOrchestrator or fallback
        print(f"   STEP 8: Dispatching task...")
        print(f"      _task_orchestrator={self._task_orchestrator is not None}")
        if self._task_orchestrator:
            try:
                logger.info(f"   Using TaskOrchestrator to dispatch {task_name}")
                print(f"      → Calling TaskOrchestrator.dispatch_task('{task_name}', data={data is not None})")
                self._task_orchestrator.dispatch_task(task_name, data)
                print(f"   ✓ STEP 8 COMPLETE: TaskOrchestrator dispatched successfully")
                return
            except Exception as e:
                logger.error(f"TaskOrchestrator failed: {e}, using fallback")
                print(f"   ⚠️ STEP 8 FALLBACK: TaskOrchestrator failed - {e}")
        
        # Fallback: legacy dispatch
        logger.info(f"   Using legacy dispatch for {task_name}")
        print(f"      → Calling _legacy_dispatch_task('{task_name}', data={data is not None})")
        self._legacy_dispatch_task(task_name, data)
        print(f"   ✓ STEP 8 COMPLETE: Legacy dispatch finished")


    def _safe_cancel_all_tasks(self):
        """Safely cancel all tasks via TaskManagementService."""
        service = self._get_task_management_service()
        if service:
            service.safe_cancel_all_tasks()
        else:
            logger.warning("TaskManagementService unavailable - cannot cancel tasks safely")

    def _cancel_layer_tasks(self, layer_id):
        """Cancel all tasks for layer_id via TaskManagementService."""
        service = self._get_task_management_service()
        if service:
            service.cancel_layer_tasks(layer_id, self.dockwidget)
        else:
            logger.warning("TaskManagementService not available, cannot cancel layer tasks")

    def _handle_layer_task_terminated(self, task_name):
        """Handle layer management task termination (failure or cancellation) to prevent stuck UI."""
        logger.warning(f"Layer management task '{task_name}' was terminated")
        
        # STABILITY FIX: Reset counters and flags on task failure using tracked flags
        if task_name == 'add_layers':
            if self._pending_add_layers_tasks > 0:
                self._pending_add_layers_tasks -= 1
                logger.debug(f"Reset add_layers counter after termination (remaining: {self._pending_add_layers_tasks})")
            if self._loading_new_project:
                logger.warning("Resetting _loading_new_project flag after task termination")
                self._set_loading_flag(False)
            if self._initializing_project:
                logger.warning("Resetting _initializing_project flag after task termination")
                self._set_initializing_flag(False)
        
        # Check if we still need to initialize the UI
        if self.dockwidget is None:
            return
        
        # STABILITY FIX: Release dockwidget busy flag
        if hasattr(self.dockwidget, '_plugin_busy'):
            self.dockwidget._plugin_busy = False
        
        # If PROJECT_LAYERS is still empty, try to recover
        if len(self.PROJECT_LAYERS) == 0:
            logger.info("Task terminated with empty PROJECT_LAYERS, attempting recovery")
            
            # Get current vector layers from project
            current_layers = self._filter_usable_layers(list(self.PROJECT.mapLayers().values()))
            
            if len(current_layers) > 0:
                # Retry add_layers with a delay
                logger.info(f"Recovery: Retrying add_layers with {len(current_layers)} layers")
                # STABILITY FIX: Use weakref to prevent access violations
                weak_self = weakref.ref(self)
                captured_layers = current_layers
                def safe_layer_retry():
                    strong_self = weak_self()
                    if strong_self is not None:
                        strong_self.manage_task('add_layers', captured_layers)
                QTimer.singleShot(STABILITY_CONSTANTS['LAYER_RETRY_DELAY_MS'], safe_layer_retry)
            else:
                logger.info("No layers available after task termination")
                if hasattr(self.dockwidget, 'backend_indicator_label') and self.dockwidget.backend_indicator_label:
                    self.dockwidget.backend_indicator_label.setText("...")
                    self.dockwidget.backend_indicator_label.setStyleSheet("QLabel#label_backend_indicator{color:#7f8c8d;font-size:9pt;font-weight:600;padding:3px 10px;border-radius:12px;border:none;background-color:#ecf0f1;}")
        else:
            logger.info("Task terminated but PROJECT_LAYERS has data, refreshing UI")
            self.dockwidget.get_project_layers_from_app(self.PROJECT_LAYERS, self.PROJECT)

    def _process_add_layers_queue(self):
        """
        Process queued add_layers operations.
        
        .. deprecated:: 4.0.0
            Delegates to TaskManagementService.process_add_layers_queue()
        
        Processes the first queued add_layers operation from self._add_layers_queue.
        Called after a previous add_layers task completes or from safety timer.
        """
        service = self._get_task_management_service()
        if service:
            service.process_add_layers_queue(self.manage_task)
        else:
            logger.warning("TaskManagementService not available, cannot process queue")
    
    def _warm_query_cache_for_layers(self):
        """Pre-warm query cache for loaded layers to reduce cold-start latency."""
        if not self.PROJECT_LAYERS: return
        try:
            from .infrastructure.cache import warm_cache_for_project
            layers_info = [{'id': lid, 'provider_type': linfo.get('layer_provider_type', 'unknown')}
                          for lid, linfo in self.PROJECT_LAYERS.items()
                          if linfo.get('layer') and is_valid_layer(linfo.get('layer'))]
            if layers_info:
                warmed = warm_cache_for_project(layers_info, ['equals', 'intersects', 'contains', 'within'])
                if warmed > 0: logger.debug(f"Pre-warmed {warmed} cache entries for {len(layers_info)} layers")
        except Exception as e: logger.debug(f"Cache warmup skipped (optional): {e}")

    def _is_dockwidget_ready_for_filtering(self):
        """Check if dockwidget is fully ready for filtering."""
        if not self.dockwidget:
            logger.debug("Dockwidget not ready: dockwidget is None"); return False
        
        # Sync _widgets_ready flag if dockwidget.widgets_initialized is True
        if not self._widgets_ready and hasattr(self.dockwidget, 'widgets_initialized') and self.dockwidget.widgets_initialized:
            logger.warning("⚠️ FALLBACK: Syncing _widgets_ready flag")
            self._widgets_ready = True
        
        # Check readiness conditions
        if not self._widgets_ready or not getattr(self.dockwidget, 'widgets_initialized', False):
            logger.debug("Dockwidget not ready: widgets not initialized"); return False
        if hasattr(self.dockwidget, 'cbb_layers') and self.dockwidget.cbb_layers and self.dockwidget.cbb_layers.count() == 0:
            logger.debug("Dockwidget not ready: layer combobox empty"); return False
        if not self.dockwidget.current_layer:
            logger.debug("Dockwidget not ready: no current layer"); return False
        
        logger.debug("✓ Dockwidget ready for filtering")
        return True

    def _on_widgets_initialized(self):
        """Callback when dockwidget widgets are initialized (via widgetsInitialized signal)."""
        logger.info("✓ Received widgetsInitialized signal - dockwidget ready for operations")
        self._widgets_ready = True
        logger.debug(f"_widgets_ready set to: {self._widgets_ready}")
        
        # If we have PROJECT_LAYERS but UI wasn't refreshed yet, do it now
        if len(self.PROJECT_LAYERS) > 0:
            logger.debug(f"Refreshing UI with {len(self.PROJECT_LAYERS)} existing layers")
            self.dockwidget.get_project_layers_from_app(self.PROJECT_LAYERS, self.PROJECT)
        
        # Process any queued add_layers operations now that widgets are ready
        if self._add_layers_queue and self._pending_add_layers_tasks == 0:
            logger.info(f"Widgets ready - processing {len(self._add_layers_queue)} queued add_layers operations")
            # STABILITY FIX: Use weakref to prevent access violations
            weak_self = weakref.ref(self)
            def safe_process_queue():
                strong_self = weak_self()
                if strong_self is not None:
                    strong_self._process_add_layers_queue()
            QTimer.singleShot(100, safe_process_queue)

    def on_remove_layer_task_begun(self):
        """Called when layer removal task begins. Cleanup UI before layers are removed."""
        # CRITICAL: Clear layer combo box before layers are removed to prevent access violations
        if self.dockwidget and hasattr(self.dockwidget, 'comboBox_filtering_current_layer'):
            try:
                # Check if current layer is about to be removed
                current_layer = self.dockwidget.current_layer
                if current_layer:
                    # Clear if it's the current layer being removed
                    self.dockwidget.comboBox_filtering_current_layer.setLayer(None)
                    logger.debug("FilterMate: Cleared layer combo during remove_layers task")
            except Exception as e:
                logger.debug(f"FilterMate: Error clearing layer combo in on_remove_layer_task_begun: {e}")
        
        # CRITICAL: Clear QgsFeaturePickerWidget before layers are removed
        # The widget has an internal timer that can cause access violation if layer is destroyed
        if self.dockwidget and hasattr(self.dockwidget, 'mFeaturePickerWidget_exploring_single_selection'):
            try:
                self.dockwidget.mFeaturePickerWidget_exploring_single_selection.setLayer(None)
                logger.debug("FilterMate: Cleared FeaturePickerWidget during remove_layers task")
            except Exception as e:
                logger.debug(f"FilterMate: Error clearing FeaturePickerWidget in on_remove_layer_task_begun: {e}")
        
        self.dockwidget.disconnect_widgets_signals()
        self.dockwidget.reset_multiple_checkable_combobox()
    
    # ========================================
    # CONTROLLER DELEGATION (v3.0 MIG-025)
    # ========================================
    
    def _try_delegate_to_controller(self, task_name: str, data=None) -> bool:
        """
        Try to delegate task to hexagonal architecture controllers (Strangler Fig pattern).
        
        This method implements the progressive migration strategy:
        1. Check if hexagonal architecture is available
        2. Verify controller integration is setup
        3. Attempt delegation to appropriate controller
        4. Automatic fallback to legacy code if delegation fails
        
        Args:
            task_name: Name of the task ('filter', 'unfilter', 'reset')
            data: Optional task-specific data
            
        Returns:
            True if delegation succeeded (use hexagonal path)
            False to use legacy code path
        """
        # Check prerequisites
        if not HEXAGONAL_AVAILABLE:
            logger.debug(f"Delegation skipped for '{task_name}': hexagonal architecture not available")
            return False
        
        if self.dockwidget is None:
            logger.debug(f"Delegation skipped for '{task_name}': dockwidget not available")
            return False
        
        # Get controller integration from dockwidget
        integration = getattr(self.dockwidget, '_controller_integration', None)
        if integration is None:
            logger.debug(f"Delegation skipped for '{task_name}': controller integration is None")
            return False
            
        if not integration.enabled:
            logger.debug(f"Delegation skipped for '{task_name}': controller integration disabled")
            return False
        
        # Verify controllers are setup
        if not hasattr(integration, '_is_setup') or not integration._is_setup:
            logger.debug(f"Delegation skipped for '{task_name}': controllers not yet setup")
            return False
        
        try:
            # Always sync state before delegation
            integration.sync_from_dockwidget()
            
            # Delegate based on task type
            if task_name == 'filter':
                success = integration.delegate_execute_filter()
                if success:
                    logger.info("✓ Filter executed via FilteringController (hexagonal)")
                    return True
                else:
                    logger.debug("FilteringController returned False, falling back to legacy")
                    return False
            
            elif task_name == 'unfilter':
                success = integration.delegate_execute_unfilter()
                if success:
                    logger.info("✓ Unfilter executed via FilteringController (hexagonal)")
                    return True
                else:
                    logger.debug("Unfilter delegation returned False, falling back to legacy")
                    return False
            
            elif task_name == 'reset':
                success = integration.delegate_execute_reset()
                if success:
                    logger.info("✓ Reset executed via FilteringController (hexagonal)")
                    return True
                else:
                    logger.debug("Reset delegation returned False, falling back to legacy")
                    return False
            
            else:
                logger.debug(f"No controller delegation available for task: {task_name}")
                return False
            
        except Exception as e:
            logger.warning(f"Controller delegation failed for '{task_name}': {e}", exc_info=True)
            logger.info("Falling back to legacy code path")
            return False
    
    # ========================================
    # AUTO-OPTIMIZATION METHODS
    # ========================================
    
    def _check_and_confirm_optimizations(self, current_layer, task_parameters):
        """Check for optimization opportunities and ask user for confirmation. Delegates to OptimizationManager."""
        if self._optimization_manager is not None:
            try:
                return self._optimization_manager.check_and_confirm_optimizations(
                    current_layer, task_parameters
                )
            except Exception as e:
                logger.warning(f"v4.2: OptimizationManager failed: {e}")
        
        # v4.7: Minimal fallback - return safe defaults (no optimizations)
        # Full logic is now in OptimizationManager
        logger.debug("Optimization check skipped (manager unavailable)")
        return {}, False
    
    def _apply_optimization_to_ui_widgets(self, selected_optimizations: dict):
        """Apply accepted optimization choices to UI widgets. Delegates to OptimizationManager."""
        if self._optimization_manager is not None:
            try:
                self._optimization_manager.apply_optimization_to_ui_widgets(selected_optimizations)
                return
            except Exception as e:
                logger.warning(f"v4.2: OptimizationManager UI update failed: {e}")
        
        # v4.7: Minimal fallback - full logic is in OptimizationManager
        logger.debug("UI widget optimization skipped (manager unavailable)")
    
    def _build_layers_to_filter(self, current_layer):
        """Build list of layers to filter with validation. Delegates to LayerFilterBuilder."""
        if LayerFilterBuilder is not None:
            builder = LayerFilterBuilder(self.PROJECT_LAYERS, self.PROJECT)
            return builder.build_layers_to_filter(current_layer)
        
        # Minimal fallback (should not happen in normal operation)
        logger.warning("LayerFilterBuilder not available, using minimal fallback")
        layers_to_filter = []
        if current_layer.id() in self.PROJECT_LAYERS:
            raw_layers = self.PROJECT_LAYERS[current_layer.id()]["filtering"].get("layers_to_filter", [])
            for key in raw_layers:
                if key in self.PROJECT_LAYERS:
                    layers_to_filter.append(self.PROJECT_LAYERS[key]["infos"].copy())
        return layers_to_filter
    
    def _build_all_filtered_layers(self, current_layer):
        """
        Build list of ALL layers that have an active subsetString filter.
        
        v4.8 FIX: Used for unfilter/reset operations when no layers are checked
        in the combobox. This ensures all previously filtered layers get unfiltered.
        
        Args:
            current_layer: Current source layer (excluded from result)
            
        Returns:
            List of layer info dicts for layers with active filters
        """
        filtered_layers = []
        current_layer_id = current_layer.id() if current_layer else None
        
        for layer_id, layer_props in self.PROJECT_LAYERS.items():
            # Skip current layer (handled separately)
            if layer_id == current_layer_id:
                continue
            
            # Get the actual layer object
            layer = layer_props.get("layer")
            if not layer or not is_valid_layer(layer):
                continue
            
            # Check if layer has an active filter
            subset_string = layer.subsetString()
            if subset_string and subset_string.strip():
                # Layer has active filter - include it for unfiltering
                layer_info = layer_props.get("infos", {}).copy()
                if layer_info:
                    filtered_layers.append(layer_info)
                    logger.debug(f"v4.8: Including filtered layer for unfilter: {layer.name()}")
        
        return filtered_layers

    def _initialize_filter_history(self, current_layer, layers_to_filter, task_parameters):
        """Initialize filter history for source and associated layers.
        
        .. deprecated:: 4.0.0
            Delegates to UndoRedoHandler.initialize_filter_history()
        """
        if self._undo_redo_handler:
            self._undo_redo_handler.initialize_filter_history(
                current_layer, layers_to_filter, task_parameters
            )
    
    def _build_common_task_params(self, features, expression, layers_to_filter, include_history=False):
        """Build common task parameters for filter/unfilter/reset operations."""
        builder = self._get_task_builder()
        if builder:
            return builder.build_common_task_params(
                features=features, expression=expression, layers_to_filter=layers_to_filter,
                include_history=include_history, session_id=self.session_id,
                db_file_path=self.db_file_path, project_uuid=self.project_uuid,
                history_manager=self.history_manager if include_history else None
            )
        logger.error("TaskParameterBuilder not available - cannot build task parameters")
        return None
    
    def _build_layer_management_params(self, layers, reset_flag):
        """Build parameters for layer management tasks (add/remove layers)."""
        builder = self._get_task_builder()
        if builder:
            return builder.build_layer_management_params(
                layers=layers, reset_flag=reset_flag, project_layers=self.PROJECT_LAYERS,
                config_data=self.CONFIG_DATA, db_file_path=self.db_file_path,
                project_uuid=self.project_uuid, session_id=self.session_id
            )
        logger.error("TaskParameterBuilder not available - cannot build layer management parameters")
        return None

    def get_task_parameters(self, task_name, data=None):
        """Build parameter dictionary for task execution (filter/layer management)."""
        # DIAGNOSTIC 2026-01-16: ULTRA-DETAILED TRACE
        logger.info("=" * 80)
        logger.info("🔧 get_task_parameters() CALLED")
        logger.info("=" * 80)
        logger.info(f"   task_name: {task_name}")
        logger.info(f"   data: {data}")

        if task_name in [name for name in self.tasks_descriptions.keys() if "layer" not in name]:
            if self.dockwidget is None or self.dockwidget.current_layer is None:
                logger.warning("   → Returning None (dockwidget or current_layer is None)")
                return None
            
            current_layer = self.dockwidget.current_layer
            logger.info(f"   current_layer: {current_layer.name()}")
            builder = self._get_task_builder()
            logger.info(f"   builder: {builder is not None}")
            
            # v4.7: Delegate layer validation
            if builder:
                error = builder.validate_current_layer_for_task(current_layer, self.PROJECT_LAYERS)
                if error:
                    logger.warning(f"   → Returning None (layer validation error: {error})")
                    return None
            else:
                # Minimal fallback validation
                if not is_layer_source_available(current_layer):
                    return None
                if current_layer.id() not in self.PROJECT_LAYERS.keys():
                    return None
            
            # v4.4: Delegate UI→PROJECT_LAYERS synchronization
            if builder:
                task_parameters = builder.sync_ui_to_project_layers(current_layer)
                if task_parameters is None:
                    logger.error("sync_ui_to_project_layers returned None")
                    return None
            else:
                task_parameters = self.PROJECT_LAYERS[current_layer.id()]

            # v4.7: Delegate feature extraction and validation
            logger.info("   → Calling builder.get_and_validate_features()...")
            try:
                if builder:
                    features, expression = builder.get_and_validate_features(task_name)
                    logger.info(f"   → get_and_validate_features returned: {len(features)} features, expression='{expression}'")
                else:
                    features, expression = [], ""
                    logger.warning("   → No builder - using empty features!")
            except ValueError:
                logger.warning("   → ValueError from get_and_validate_features - returning None")
                return None  # single_selection mode with no features
            if task_name in ('filter', 'unfilter', 'reset'):
                # Build validated list of layers to filter
                layers_to_filter = self._build_layers_to_filter(current_layer)
                
                # v4.8 FIX: For unfilter/reset, include ALL layers with active subsetString
                # This ensures layers that were filtered are unfiltered even if unchecked
                if task_name in ('unfilter', 'reset') and len(layers_to_filter) == 0:
                    layers_to_filter = self._build_all_filtered_layers(current_layer)
                    logger.info(f"v4.8: unfilter/reset - found {len(layers_to_filter)} layers with active filters")
                
                # v4.7: Delegate diagnostic logging
                if builder:
                    builder.log_filtering_diagnostic(current_layer, layers_to_filter)
                
                # Build common task parameters
                include_history = False
                task_parameters["task"] = self._build_common_task_params(
                    features, expression, layers_to_filter, include_history
                )
                
                # v4.7: Delegate skip_source_filter logic
                skip_source_filter = builder.determine_skip_source_filter(
                    task_name, task_parameters, expression
                ) if builder else False
                
                task_parameters["task"]["skip_source_filter"] = skip_source_filter
                
                # Initialize filter history for 'filter' operation
                if task_name == 'filter':
                    self._initialize_filter_history(current_layer, layers_to_filter, task_parameters)
                
                # CRITICAL: Add forced_backends at root level for factory.py and filter_task.py access
                # They expect task_parameters.get('forced_backends', {}) at root level
                if self.dockwidget and hasattr(self.dockwidget, 'forced_backends'):
                    task_parameters["forced_backends"] = self.dockwidget.forced_backends
                
                return task_parameters

            elif task_name == 'export':
                # v4.7: Delegate export params building
                if builder:
                    export_params = builder.build_export_params(self.PROJECT_LAYERS, self.PROJECT)
                    if export_params:
                        export_params["task"]["session_id"] = self.session_id
                        return {**task_parameters, **export_params}
                
                # Fallback if TaskParameterBuilder unavailable
                logger.warning("TaskParameterBuilder unavailable for export")
                return None
            
        else:
            # Layer management tasks
            if data is None:
                return None
            
            if task_name in ('add_layers', 'remove_layers'):
                layers = data if isinstance(data, list) else [data]
                # Safely check has_loaded_layers - default to False if dockwidget not available
                has_loaded = self.dockwidget.has_loaded_layers if self.dockwidget else False
                reset_flag = (self.CONFIG_DATA["APP"]["OPTIONS"]["FRESH_RELOAD_FLAG"] and 
                             not has_loaded)
                return self._build_layer_management_params(layers, reset_flag)

    def _refresh_layers_and_canvas(self, source_layer):
        """Refresh source layer and canvas via LayerRefreshManager."""
        if self._layer_refresh_manager is not None:
            self._layer_refresh_manager.refresh_layer_and_canvas(source_layer)
        else:
            logger.warning("LayerRefreshManager unavailable - canvas refresh skipped")
    
    def _push_filter_to_history(self, source_layer, task_parameters, feature_count, provider_type, layer_count):
        """Push filter state to history via UndoRedoHandler."""
        if self._undo_redo_handler:
            self._undo_redo_handler.push_filter_to_history(
                source_layer=source_layer,
                task_parameters=task_parameters,
                feature_count=feature_count,
                provider_type=provider_type,
                layer_count=layer_count
            )
        else:
            logger.warning("UndoRedoHandler not available, history not updated")
    
    def update_undo_redo_buttons(self):
        """Update undo/redo button states via UndoRedoHandler."""
        if not self.dockwidget: return
        undo_btn = getattr(self.dockwidget, 'pushButton_action_undo_filter', None)
        redo_btn = getattr(self.dockwidget, 'pushButton_action_redo_filter', None)
        if not undo_btn or not redo_btn: return
        if self._undo_redo_handler:
            current_layer = self.dockwidget.current_layer
            layers_to_filter = self.dockwidget.PROJECT_LAYERS.get(current_layer.id(), {}).get("filtering", {}).get("layers_to_filter", []) if current_layer and current_layer.id() in self.dockwidget.PROJECT_LAYERS else []
            self._undo_redo_handler.update_button_states(current_layer=current_layer, layers_to_filter=layers_to_filter, undo_button=undo_btn, redo_button=redo_btn)
        else:
            undo_btn.setEnabled(False); redo_btn.setEnabled(False)
    
    def _handle_undo_redo(self, is_undo: bool):
        """Handle undo/redo operation (delegates to UndoRedoHandler, with legacy fallback)."""
        action_name = "undo" if is_undo else "redo"
        if not self.dockwidget or not self.dockwidget.current_layer:
            logger.warning(f"FilterMate: No current layer for {action_name}")
            return
        
        source_layer = self.dockwidget.current_layer
        
        # Guard: ensure layer is usable
        if not is_layer_source_available(source_layer):
            logger.warning(f"handle_{action_name}: source layer invalid or source missing; aborting.")
            show_warning(f"Impossible de {action_name}: couche invalide ou source introuvable.")
            return
        
        # STABILITY FIX: Verify layer exists in PROJECT_LAYERS before access
        if source_layer.id() not in self.dockwidget.PROJECT_LAYERS:
            logger.warning(f"handle_{action_name}: layer {source_layer.name()} not in PROJECT_LAYERS; aborting.")
            return
        
        layers_to_filter = self.dockwidget.PROJECT_LAYERS.get(source_layer.id(), {}).get("filtering", {}).get("layers_to_filter", [])
        button_is_checked = self.dockwidget.pushButton_checkable_filtering_layers_to_filter.isChecked()
        
        # v4.1: Set filtering protection to prevent layer change signals
        self.dockwidget._filtering_in_progress = True
        logger.info(f"v4.1: 🔒 handle_{action_name} - Filtering protection enabled")
        
        try:
            # Try UndoRedoHandler first (v4.0 hexagonal architecture)
            if self._undo_redo_handler:
                handler_method = self._undo_redo_handler.handle_undo if is_undo else self._undo_redo_handler.handle_redo
                result = handler_method(source_layer=source_layer, layers_to_filter=layers_to_filter, use_global=button_is_checked, dockwidget=self.dockwidget)
                if result: self.update_undo_redo_buttons()
            else:
                # LEGACY FALLBACK: Direct history_manager access (v2.x behavior)
                logger.warning(f"UndoRedoHandler unavailable - using legacy {action_name}")
                self._legacy_handle_undo_redo(is_undo, source_layer, layers_to_filter, button_is_checked)
        finally:
            if self.dockwidget:
                self.dockwidget._filtering_in_progress = False
                logger.info(f"v4.1: 🔓 handle_{action_name} - Filtering protection disabled")
    
    def _legacy_handle_undo_redo(self, is_undo: bool, source_layer, layers_to_filter: list, button_is_checked: bool):
        """
        Legacy undo/redo fallback when UndoRedoHandler is unavailable.
        
        Extracted from before_migration/filter_mate_app.py v2.9.29 for stability.
        """
        action_name = "undo" if is_undo else "redo"
        has_remote_layers = bool(layers_to_filter)
        use_global = button_is_checked and has_remote_layers
        
        if use_global:
            # Global undo/redo
            logger.info(f"FilterMate: Performing global {action_name} (legacy fallback)")
            global_state = self.history_manager.undo_global() if is_undo else self.history_manager.redo_global()
            
            if global_state:
                # Apply state to source layer
                safe_set_subset_string(source_layer, global_state.source_expression)
                self.PROJECT_LAYERS[source_layer.id()]["infos"]["is_already_subset"] = bool(global_state.source_expression)
                logger.info(f"FilterMate: Restored source layer: {global_state.source_expression[:60] if global_state.source_expression else 'no filter'}")
                
                # Apply state to ALL remote layers from the saved state
                restored_count = 0
                restored_layers = []
                for remote_id, (expression, _) in global_state.remote_layers.items():
                    if remote_id not in self.PROJECT_LAYERS:
                        logger.warning(f"FilterMate: Remote layer {remote_id} no longer exists, skipping")
                        continue
                    
                    remote_layers = [l for l in self.PROJECT.mapLayers().values() if l.id() == remote_id]
                    if remote_layers:
                        remote_layer = remote_layers[0]
                        if not is_layer_source_available(remote_layer):
                            logger.warning(f"Global {action_name}: skipping remote layer '{remote_layer.name()}' (invalid or missing source)")
                            continue
                        safe_set_subset_string(remote_layer, expression)
                        self.PROJECT_LAYERS[remote_id]["infos"]["is_already_subset"] = bool(expression)
                        logger.info(f"FilterMate: Restored remote layer {remote_layer.name()}: {expression[:60] if expression else 'no filter'}")
                        restored_count += 1
                        restored_layers.append(remote_layer)
                    else:
                        logger.warning(f"FilterMate: Remote layer {remote_id} not found in project")
                
                # Refresh ALL affected layers
                source_layer.updateExtents()
                source_layer.triggerRepaint()
                for remote_layer in restored_layers:
                    remote_layer.updateExtents()
                    remote_layer.triggerRepaint()
                self.iface.mapCanvas().refreshAllLayers()
                self.iface.mapCanvas().refresh()
                
                logger.info(f"FilterMate: Global {action_name} completed - restored {restored_count + 1} layers (legacy)")
            else:
                logger.info(f"FilterMate: No global {action_name} history available")
        else:
            # Source layer only undo/redo
            logger.info(f"FilterMate: Performing source layer {action_name} only (legacy fallback)")
            history = self.history_manager.get_history(source_layer.id())
            
            can_action = history.can_undo() if is_undo else history.can_redo() if history else False
            if history and can_action:
                state = history.undo() if is_undo else history.redo()
                if state:
                    safe_set_subset_string(source_layer, state.expression)
                    self.PROJECT_LAYERS[source_layer.id()]["infos"]["is_already_subset"] = bool(state.expression)
                    logger.info(f"FilterMate: {action_name.capitalize()} source layer to: {state.description}")
                    self._refresh_layers_and_canvas(source_layer)
            else:
                logger.info(f"FilterMate: No {action_name} history for source layer")
        
        # Update button states
        self.update_undo_redo_buttons()
    
    def handle_undo(self):
        """Handle undo (delegates to UndoRedoHandler, global mode if checkbox checked)."""
        self._handle_undo_redo(is_undo=True)
    
    def handle_redo(self):
        """Handle redo (delegates to UndoRedoHandler, global mode if checkbox checked)."""
        self._handle_undo_redo(is_undo=False)
    
    def _clear_filter_history(self, source_layer, task_parameters):
        """Clear filter history via UndoRedoHandler."""
        if self._undo_redo_handler:
            remote_layer_ids = [
                lp.get("layer_id") 
                for lp in task_parameters.get("task", {}).get("layers", [])
                if lp.get("layer_id")
            ]
            self._undo_redo_handler.clear_filter_history(source_layer, remote_layer_ids)
        else:
            logger.warning("UndoRedoHandler unavailable - history not cleared")
    
    def _show_task_completion_message(self, task_name, source_layer, provider_type, layer_count, is_fallback=False):
        """Show success message with backend info and feature counts."""
        from .config.feedback_config import should_show_message
        feature_count = source_layer.featureCount()
        show_success_with_backend(provider_type, task_name, layer_count, is_fallback=is_fallback)
        if should_show_message('filter_count'):
            prefix = "All filters cleared - " if task_name == 'unfilter' else ""
            show_info(f"{prefix}{feature_count:,} features visible in main layer")

    def filter_engine_task_completed(self, task_name, source_layer, task_parameters):
        """Handle completion of filtering operations via FilterResultHandler."""
        if not self._filter_result_handler:
            logger.error("FilterResultHandler not available")
            iface.messageBar().pushCritical("FilterMate", "Erreur: handler de résultats manquant")
            return
        
        try:
            current_layer_id = getattr(self, '_current_layer_id_before_filter', None)
            self._filter_result_handler.handle_task_completion(
                task_name=task_name,
                source_layer=source_layer,
                task_parameters=task_parameters,
                current_layer_id_before_filter=current_layer_id
            )
        except Exception as e:
            logger.error(f"FilterResultHandler failed: {e}")
            iface.messageBar().pushCritical("FilterMate", f"Erreur lors du filtrage: {str(e)}")

    def apply_subset_filter(self, task_name, layer):
        """Apply or remove subset filter expression on a layer. Delegates to FilterApplicationService."""
        if self._filter_application_service:
            self._filter_application_service.apply_subset_filter(task_name, layer)
        else:
            logger.warning("FilterApplicationService not available, cannot apply subset filter")

    def save_variables_from_layer(self, layer, layer_properties=None):
        """Save layer filtering properties to QGIS variables and Spatialite database."""
        if self._variables_manager:
            self._variables_manager.save_variables_from_layer(layer, layer_properties)
        else:
            logger.warning("VariablesPersistenceManager not available, cannot save layer variables")

    def remove_variables_from_layer(self, layer, layer_properties=None):
        """Remove layer filtering properties from QGIS variables and Spatialite database."""
        if self._variables_manager:
            self._variables_manager.remove_variables_from_layer(layer, layer_properties)
        else:
            logger.warning("VariablesPersistenceManager not available, cannot remove layer variables")

    def create_spatial_index_for_layer(self, layer):
        """Create spatial index for a layer via DatasourceManager."""
        if self._datasource_manager:
            self._datasource_manager.create_spatial_index_for_layer(layer)

    def init_filterMate_db(self):
        """Initialize FilterMate Spatialite database with required schema. Delegates to DatabaseManager."""
        if self.PROJECT is None:
            return
        
        self.project_file_name = os.path.basename(self.PROJECT.absoluteFilePath())
        self.project_file_path = self.PROJECT.absolutePath()
        
        if not self._database_manager:
            logger.error("DatabaseManager not available, cannot initialize database")
            return
        
        fresh_reload = self.CONFIG_DATA.get("APP", {}).get("OPTIONS", {}).get("FRESH_RELOAD_FLAG", False)
        success, self.CONFIG_DATA = self._database_manager.initialize_database(
            config_data=self.CONFIG_DATA,
            fresh_reload=fresh_reload,
            config_json_path=ENV_VARS["CONFIG_JSON_PATH"]
        )
        
        if success:
            # Sync db_file_path and project_uuid from DatabaseManager
            self.db_file_path = self._database_manager.db_file_path
            self.project_uuid = self._database_manager.project_uuid
            
            # Configure FavoritesService with SQLite database
            if hasattr(self, 'favorites_manager') and self.db_file_path and self.project_uuid:
                self.favorites_manager.set_database(self.db_file_path, str(self.project_uuid))
                self.favorites_manager.load_from_project()
                logger.info(f"FavoritesService configured with SQLite database ({self.favorites_manager.count} favorites loaded)")

    def add_project_datasource(self, layer):
        """Add PostgreSQL datasource and create temp schema via DatasourceManager."""
        if self._datasource_manager:
            self._datasource_manager.add_project_datasource(layer)

    def save_project_variables(self, name=None):
        """Save project variables to database. Delegates to DatabaseManager."""
        global ENV_VARS

        if self.dockwidget is None:
            return
        
        self.CONFIG_DATA = self.dockwidget.CONFIG_DATA
        
        if not self._database_manager:
            logger.warning("DatabaseManager not available, cannot save project variables")
            return
        
        if name is not None:
            self.project_file_name = name
            self.project_file_path = self.PROJECT.absolutePath()
        
        success = self._database_manager.save_project_variables(
            config_data=self.CONFIG_DATA,
            project_name=name
        )
        
        if success:
            # Also save to config file - use cleaned data to avoid non-serializable objects
            # (e.g., psycopg2 connections that may be stored in CONFIG_DATA)
            config_data_clean = self._database_manager._clean_for_json(self.CONFIG_DATA)
            with open(ENV_VARS["CONFIG_JSON_PATH"], 'w') as outfile:
                outfile.write(json.dumps(config_data_clean, indent=4))
            
            # Save favorites to project
            if hasattr(self, 'favorites_manager') and self.favorites_manager is not None:
                self.favorites_manager.save()
                count = getattr(self.favorites_manager, 'count', 0)
                logger.debug(f"Saved {count} favorites to project")

    def layer_management_engine_task_completed(self, result_project_layers, task_name):
        """Handle layer management task completion. Delegates to LayerTaskCompletionHandler."""
        if self._layer_task_completion_handler is not None:
            try:
                # Initialize ENV_VARS before delegation
                init_env_vars()
                global ENV_VARS
                self.PROJECT = ENV_VARS["PROJECT"]
                
                # Delegate to handler
                self._layer_task_completion_handler.handle_task_completion(
                    result_project_layers=result_project_layers,
                    task_name=task_name,
                    loading_new_project=self._loading_new_project
                )
                return
            except Exception as e:
                import traceback
                logger.warning(f"v4.7: LayerTaskCompletionHandler failed: {e}")
                logger.debug(f"v4.7: Traceback: {traceback.format_exc()}")
        
        # v4.7: Minimal fallback
        logger.debug("Layer task completion skipped (handler unavailable)")
    
    def _validate_layer_info(self, layer_key):
        """Validate layer structure and return layer info if valid, else None."""
        if layer_key not in self.PROJECT_LAYERS:
            logger.warning(f"Layer {layer_key} not found in PROJECT_LAYERS")
            return None
        
        if "infos" not in self.PROJECT_LAYERS[layer_key]:
            logger.warning(f"Layer {layer_key} missing required 'infos' in PROJECT_LAYERS")
            return None
        
        layer_info = self.PROJECT_LAYERS[layer_key]["infos"]
        required_keys = ["layer_provider_type", "layer_name", "layer_id"]
        missing_keys = [k for k in required_keys if k not in layer_info or layer_info[k] is None]
        
        if missing_keys:
            logger.warning(f"Layer {layer_key} missing required keys in infos: {missing_keys}")
            return None
        
        return layer_info
    
    def _update_datasource_for_layer(self, layer_info):
        """Update datasources via DatasourceManager."""
        if self._datasource_manager:
            self._datasource_manager.update_datasource_for_layer(layer_info)

    def _remove_datasource_for_layer(self, layer_info):
        """Remove project datasources via DatasourceManager."""
        if self._datasource_manager:
            self._datasource_manager.remove_datasource_for_layer(layer_info)

    def _refresh_ui_with_layers(self, validate_postgres=False, show_success=False, allow_retry=False):
        """Refresh UI after layer operations (reload/project load). Consolidates 2 similar methods."""
        from qgis.PyQt.QtCore import QTimer
        
        if not self.dockwidget or not self.dockwidget.widgets_initialized:
            logger.debug("Cannot refresh UI: dockwidget not initialized"); return
        
        # Reset loading flag
        self._set_loading_flag(False)
        
        # Handle retry logic for reload operations
        if allow_retry and len(self.PROJECT_LAYERS) == 0:
            if not hasattr(self, '_reload_retry_count'): self._reload_retry_count = 0
            self._reload_retry_count += 1
            if self._reload_retry_count < 3:
                logger.warning(f"PROJECT_LAYERS empty, retry {self._reload_retry_count}/3")
                weak_self = weakref.ref(self)
                QTimer.singleShot(1000, lambda: (s := weak_self()) and s._refresh_ui_with_layers(validate_postgres, show_success, allow_retry))
                return
            logger.error("PROJECT_LAYERS still empty after 3 retries")
            self._reload_retry_count = 0
            if hasattr(self.dockwidget, 'backend_indicator_label') and self.dockwidget.backend_indicator_label:
                self.dockwidget.backend_indicator_label.setText("!")
                self.dockwidget.backend_indicator_label.setStyleSheet("QLabel#label_backend_indicator{color:#e74c3c;font-size:9pt;font-weight:600;padding:3px 10px;border-radius:12px;border:none;background-color:#fadbd8;}")
                self.dockwidget.backend_indicator_label.setToolTip("Layer loading failed - click to retry")
            return
        
        if len(self.PROJECT_LAYERS) == 0:
            logger.warning("Cannot refresh UI: PROJECT_LAYERS still empty"); return
        
        if allow_retry: self._reload_retry_count = 0
        logger.info(f"Refreshing UI with {len(self.PROJECT_LAYERS)} layers (validate_postgres={validate_postgres})")
        
        # Validate PostgreSQL layers if requested
        if validate_postgres: self._validate_postgres_layers_on_project_load()
        
        # Reconnect PROJECT signals for project load
        if validate_postgres:
            try:
                try: self.PROJECT.fileNameChanged.disconnect()
                except TypeError:  # Signal not connected - expected on first project load
                    pass
                self.PROJECT.fileNameChanged.connect(lambda: self.save_project_variables())
                logger.info("PROJECT signals reconnected")
            except Exception as e: logger.warning(f"Error reconnecting signals: {e}")
        
        # Update dockwidget with layers
        self.dockwidget.get_project_layers_from_app(self.PROJECT_LAYERS, self.PROJECT)
        self.dockwidget.has_loaded_layers = True
        if hasattr(self.dockwidget, 'set_widgets_enabled_state'): self.dockwidget.set_widgets_enabled_state(True)
        try:
            if hasattr(self.dockwidget, 'comboBox_filtering_current_layer'):
                self.dockwidget.comboBox_filtering_current_layer.setFilters(QgsMapLayerProxyModel.VectorLayer)
        except Exception as e: logger.debug(f"ComboBox filter setup (non-critical): {e}")
        
        # Trigger layer change with active or first layer
        active = self.iface.activeLayer()
        if active and isinstance(active, QgsVectorLayer) and active.id() in self.PROJECT_LAYERS:
            self.dockwidget.current_layer_changed(active)
            logger.info(f"UI refreshed with active layer: {active.name()}")
        elif self.PROJECT_LAYERS:
            first_layer = self.PROJECT.mapLayer(list(self.PROJECT_LAYERS.keys())[0])
            if first_layer:
                self.dockwidget.current_layer_changed(first_layer)
                logger.info(f"UI refreshed with first layer: {first_layer.name()}")
        
        # Show success notification if requested
        if show_success:
            from qgis.utils import iface
            iface.messageBar().pushSuccess("FilterMate", f"{len(self.PROJECT_LAYERS)} couche(s) chargée(s) avec succès")

    def _force_ui_refresh_after_reload(self):
        """Force UI refresh after force_reload_layers."""
        self._refresh_ui_with_layers(validate_postgres=False, show_success=True, allow_retry=True)
    
    def _refresh_ui_after_project_load(self):
        """Force UI refresh after project load."""
        self._refresh_ui_with_layers(validate_postgres=True, show_success=False, allow_retry=False)
    
    def _validate_postgres_layers_on_project_load(self):
        """
        Validate PostgreSQL layers for orphaned materialized view references.
        
        Sprint 17: Delegates to LayerValidator.validate_postgres_layers_on_project_load()
        """
        if self._layer_validator:
            self._layer_validator.validate_postgres_layers_on_project_load(
                project=self.PROJECT,
                show_warning_callback=lambda t, m: iface.messageBar().pushWarning(t, m)
            )
        else:
            logger.debug("LayerValidator not available, skipping PostgreSQL validation")
            
    def update_datasource(self):
        """Update CONFIG_DATA with active datasource connections via DatasourceManager."""
        if self._datasource_manager:
            self.project_datasources = self._datasource_manager.get_project_datasources()
            self._datasource_manager.update_datasource()

    def create_foreign_data_wrapper(self, project_datasource, datasource, format):
        """Create PostgreSQL foreign data wrapper via DatasourceManager."""
        if self._datasource_manager:
            self._datasource_manager.create_foreign_data_wrapper(project_datasource, datasource, format)

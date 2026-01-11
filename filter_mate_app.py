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
from .modules.tasks import (
    FilterEngineTask,
    LayersManagementEngineTask,
    spatialite_connect
)
from .modules.appUtils import (
    POSTGRESQL_AVAILABLE,
    sanitize_sql_identifier,
    get_data_source_uri,
    get_datasource_connexion_from_layer,
    is_layer_source_available,
    safe_set_subset_string,
    detect_layer_provider_type,
    cleanup_corrupted_layer_filters,
    validate_and_cleanup_postgres_layers,  # v2.8.1: Orphaned MV cleanup on project load
    clean_buffer_value,  # v3.0.12: Clean buffer values from float precision errors
)
from .modules.type_utils import return_typed_value
from .infrastructure.feedback import (
    show_backend_info, show_success_with_backend,
    show_info, show_warning, show_error
)
from .core.services.history_service import HistoryManager
from .core.services.favorites_service import FavoritesManager
from .ui.config import UIConfig, DisplayProfile
from .modules.config_helpers import get_optimization_thresholds
from .modules.object_safety import (
    is_sip_deleted, is_valid_layer, is_qgis_alive,
    GdalErrorHandler
)
from .infrastructure.logging import get_app_logger
from .resources import *  # Qt resources must be imported with wildcard

# v3.0: Hexagonal architecture services bridge
# Provides access to new architecture while maintaining backward compatibility
try:
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
    from .adapters.task_builder import TaskParameterBuilder  # v4.0: Task parameter extraction
    from .core.services.layer_lifecycle_service import (  # v4.0: Layer lifecycle extraction
        LayerLifecycleService,
        LayerLifecycleConfig
    )
    from .core.services.task_management_service import (  # v4.0: Task management extraction
        TaskManagementService,
        TaskManagementConfig
    )
    from .adapters.undo_redo_handler import UndoRedoHandler  # v4.0: Undo/Redo extraction
    from .adapters.database_manager import DatabaseManager  # v4.0: Database operations extraction
    from .adapters.variables_manager import VariablesPersistenceManager  # v4.0: Variables persistence extraction
    from .core.services.task_orchestrator import TaskOrchestrator  # v4.1: Task orchestration extraction
    from .core.services.optimization_manager import OptimizationManager  # v4.2: Optimization management extraction
    from .adapters.filter_result_handler import FilterResultHandler  # v4.3: Filter result handling extraction
    from .core.services.app_initializer import AppInitializer  # v4.4: App initialization extraction
    from .core.services.datasource_manager import DatasourceManager  # v4.5: Datasource management extraction
    from .core.services.layer_filter_builder import LayerFilterBuilder  # v4.6: Layer filter building extraction
    from .adapters.layer_refresh_manager import LayerRefreshManager  # v4.7: Layer refresh extraction
    from .adapters.layer_task_completion_handler import LayerTaskCompletionHandler  # v4.7: Layer task completion extraction
    HEXAGONAL_AVAILABLE = True
except ImportError:
    HEXAGONAL_AVAILABLE = False
    TaskParameterBuilder = None  # v4.0: Fallback
    LayerRefreshManager = None  # v4.7: Fallback
    LayerTaskCompletionHandler = None  # v4.7: Fallback
    LayerLifecycleService = None  # v4.0: Fallback
    LayerLifecycleConfig = None  # v4.0: Fallback
    TaskManagementService = None  # v4.0: Fallback
    TaskManagementConfig = None  # v4.0: Fallback
    UndoRedoHandler = None  # v4.0: Fallback
    DatabaseManager = None  # v4.0: Fallback
    VariablesPersistenceManager = None  # v4.0: Fallback
    TaskOrchestrator = None  # v4.1: Fallback
    OptimizationManager = None  # v4.2: Fallback
    FilterResultHandler = None  # v4.3: Fallback
    AppInitializer = None  # v4.4: Fallback
    DatasourceManager = None  # v4.5: Fallback
    LayerFilterBuilder = None  # v4.6: Fallback
    LayerRefreshManager = None  # v4.7: Fallback

    def _init_hexagonal_services(config=None):
        """Fallback when hexagonal services unavailable."""

    def _cleanup_hexagonal_services():
        """Fallback cleanup."""

    def _hexagonal_initialized():
        """Fallback initialization check."""
        return False

    # Fallback stubs for optional services
    get_filter_service = None
    get_history_service = None
    get_expression_service = None
    validate_expression = None
    parse_expression = None

# Get FilterMate logger with SafeStreamHandler to prevent "--- Logging error ---" on shutdown
logger = get_app_logger()


def safe_show_message(level, title, message):
    """
    Safely show a message in QGIS interface, catching RuntimeError if interface is destroyed.
    
    This prevents access violations when showing messages after plugin unload or QGIS shutdown.
    
    Args:
        level (str): Message level - 'success', 'info', 'warning', or 'critical'
        title (str): Message title
        message (str): Message content
    
    Returns:
        bool: True if message was shown, False if interface unavailable
    """
    try:
        message_bar = iface.messageBar()
        if level == 'success':
            message_bar.pushSuccess(title, message)
        elif level == 'info':
            message_bar.pushInfo(title, message)
        elif level == 'warning':
            message_bar.pushWarning(title, message)
        elif level == 'critical':
            message_bar.pushCritical(title, message)
        return True
    except (RuntimeError, AttributeError) as e:
        logger.warning(f"Cannot show {level} message '{title}': interface may be destroyed ({e})")
        return False


# Import the code for the DockWidget
from .filter_mate_dockwidget import FilterMateDockWidget

MESSAGE_TASKS_CATEGORIES = {
                            'filter':'FilterLayers',
                            'unfilter':'FilterLayers',
                            'reset':'FilterLayers',
                            'export':'ExportLayers',
                            'add_layers':'ManageLayers',
                            'remove_layers':'ManageLayers',
                            'remove_all_layers':'ManageLayers',
                            'new_project':'ManageLayers',
                            'project_read':'ManageLayers',
                            'reload_layers':'ManageLayers'
                            }

# STABILITY CONSTANTS - Centralized timing configuration
STABILITY_CONSTANTS = {
    'MAX_ADD_LAYERS_QUEUE': 50,           # Maximum queued add_layers operations
    'FLAG_TIMEOUT_MS': 30000,              # Timeout for flags (30 seconds)
    'LAYER_RETRY_DELAY_MS': 500,           # Delay between layer operation retries
    'UI_REFRESH_DELAY_MS': 300,            # Delay for UI refresh after operations (increased from 200)
    'PROJECT_LOAD_DELAY_MS': 2500,         # Delay after project load for layer processing (increased from 1500)
    'PROJECT_CHANGE_CLEANUP_DELAY_MS': 300, # Delay before cleanup on project change
    'PROJECT_CHANGE_REINIT_DELAY_MS': 500,  # Delay before reinitializing after project change
    'MAX_RETRIES': 10,                     # Maximum retry count for deferred operations
    'SIGNAL_DEBOUNCE_MS': 150,             # Debounce delay for rapid signal calls (increased from 100)
    'POSTGRESQL_EXTRA_DELAY_MS': 1000,     # Extra delay for PostgreSQL layers
    'SPATIALITE_STABILIZATION_MS': 200,    # Delay before refreshing Spatialite layers (v2.3.12)
}

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

    def _filter_usable_layers(self, layers):
        """
        Return only layers that are valid vector layers with available sources.
        
        Delegates to LayerLifecycleService.filter_usable_layers().
        
        v4.7 E7-S1: Functional fallback when service unavailable.
        """
        service = self._get_layer_lifecycle_service()
        if service:
            return service.filter_usable_layers(layers, POSTGRESQL_AVAILABLE)
        
        # E7-S1 FALLBACK: Minimal working implementation
        logger.warning("LayerLifecycleService unavailable, using minimal fallback validation")
        
        usable = []
        for layer in layers:
            try:
                # Validate layer is a valid QgsVectorLayer with available source
                if (isinstance(layer, QgsVectorLayer) and 
                    layer.isValid() and 
                    is_layer_source_available(layer)):
                    usable.append(layer)
            except Exception as e:
                # E7-S1: Catch all exceptions to prevent fallback from crashing
                logger.debug(f"Skipping invalid layer in fallback: {e}")
                continue
        
        logger.info(f"Fallback validation: {len(usable)}/{len(layers)} layers usable")
        return usable

    def _on_layers_added(self, layers):
        """Signal handler for layersAdded: ignore broken/invalid layers.
        
        STABILITY: Debounces rapid layer additions and validates all layers.
        PostgreSQL FIX: Retries layers that may not be immediately valid due to connection timing.
        """
        import time
        
        # STABILITY FIX: Debounce rapid layer additions
        current_time = time.time() * 1000
        debounce_ms = STABILITY_CONSTANTS['SIGNAL_DEBOUNCE_MS']
        if current_time - self._last_layer_change_timestamp < debounce_ms:
            logger.debug(f"Debouncing layersAdded signal (elapsed: {current_time - self._last_layer_change_timestamp:.0f}ms < {debounce_ms}ms)")
            # Queue for later processing - use weakref to prevent access violations
            weak_self = weakref.ref(self)
            def safe_callback():
                strong_self = weak_self()
                if strong_self is not None:
                    strong_self._on_layers_added(layers)
            QTimer.singleShot(debounce_ms, safe_callback)
            return
        self._last_layer_change_timestamp = current_time
        
        # STABILITY FIX: Check and reset stale flags
        self._check_and_reset_stale_flags()
        
        # Identify PostgreSQL layers (even if not yet valid - for retry mechanism)
        all_postgres = [l for l in layers if isinstance(l, QgsVectorLayer) and l.providerType() == 'postgres']
        
        # Check if any PostgreSQL layers are being added without psycopg2
        if all_postgres and not POSTGRESQL_AVAILABLE:
            layer_names = ', '.join([l.name() for l in all_postgres[:3]])  # Show first 3
            if len(all_postgres) > 3:
                layer_names += f" (+{len(all_postgres) - 3} autres)"
            
            show_warning(
                f"Couches PostgreSQL détectées ({layer_names}) mais psycopg2 n'est pas installé. "
                "Le plugin ne peut pas utiliser ces couches. "
                "Installez psycopg2 pour activer le support PostgreSQL."
            )
            logger.warning(
                f"FilterMate: Cannot use {len(all_postgres)} PostgreSQL layer(s) - psycopg2 not available"
            )
        
        filtered = self._filter_usable_layers(layers)
        
        # FIX: Identify PostgreSQL layers that failed validation (may be initializing)
        postgres_pending = [l for l in all_postgres 
                          if l.id() not in [f.id() for f in filtered] 
                          and not is_sip_deleted(l)]
        
        if not filtered and not postgres_pending:
            logger.info("FilterMate: Ignoring layersAdded (no usable layers)")
            return
        
        # v2.8.1: Validate PostgreSQL layers for orphaned MV references BEFORE adding them
        # This fixes "relation does not exist" errors when layers with stale filters are added
        postgres_to_validate = [l for l in filtered if l.providerType() == 'postgres']
        if postgres_to_validate:
            try:
                cleaned = validate_and_cleanup_postgres_layers(postgres_to_validate)
                if cleaned:
                    logger.info(f"Cleared orphaned MV references from {len(cleaned)} layer(s) during add")
            except Exception as e:
                logger.debug(f"Error validating PostgreSQL layers during add: {e}")
        
        if filtered:
            self.manage_task('add_layers', filtered)
        
        # FIX: Schedule retry for PostgreSQL layers that may become valid after connection is established
        if postgres_pending:
            logger.info(f"FilterMate: {len(postgres_pending)} PostgreSQL layers pending - scheduling retry")
            weak_self = weakref.ref(self)
            captured_pending = postgres_pending
            
            def retry_postgres(retry_attempt=1):
                strong_self = weak_self()
                if strong_self is None:
                    return
                
                now_valid = []
                still_pending = []
                for layer in captured_pending:
                    try:
                        if is_sip_deleted(layer):
                            continue
                        if layer.isValid() and layer.id() not in strong_self.PROJECT_LAYERS:
                            now_valid.append(layer)
                            logger.info(f"PostgreSQL layer '{layer.name()}' is now valid (retry #{retry_attempt})")
                        elif not layer.isValid():
                            still_pending.append(layer)
                    except (RuntimeError, AttributeError):
                        pass
                
                if now_valid:
                    logger.info(f"FilterMate: Adding {len(now_valid)} PostgreSQL layers after retry #{retry_attempt}")
                    strong_self.manage_task('add_layers', now_valid)
                
                # FIX v2.8.6: Schedule a second retry if layers are still pending
                if still_pending and retry_attempt < 3:
                    logger.info(f"FilterMate: {len(still_pending)} PostgreSQL layers still not valid - scheduling retry #{retry_attempt + 1}")
                    QTimer.singleShot(
                        STABILITY_CONSTANTS['POSTGRESQL_EXTRA_DELAY_MS'] * retry_attempt,
                        lambda: retry_postgres(retry_attempt + 1)
                    )
            
            # Retry after PostgreSQL connection establishment delay
            QTimer.singleShot(STABILITY_CONSTANTS['POSTGRESQL_EXTRA_DELAY_MS'], retry_postgres)

    def cleanup(self):
        """
        Clean up plugin resources on unload or reload.
        
        .. deprecated:: 4.0.2
            Delegates to LayerLifecycleService.cleanup()
        
        Safely removes widgets, clears data structures, and prevents memory leaks.
        Called when plugin is disabled or QGIS is closing.
        
        Cleanup steps:
        1. Clean up PostgreSQL materialized views for this session
        2. Clear list_widgets from multiple selection widget
        3. Reset async tasks
        4. Clear PROJECT_LAYERS dictionary
        5. Clear datasource connections
        
        Notes:
            - Uses try/except to handle already-deleted widgets
            - Safe to call multiple times
            - Prevents KeyError on plugin reload
        """
        # v4.0.2: Delegate to LayerLifecycleService
        service = self._get_layer_lifecycle_service()
        if service:
            # Get auto-cleanup setting
            auto_cleanup_enabled = True  # Default to enabled
            if self.dockwidget and hasattr(self.dockwidget, '_pg_auto_cleanup_enabled'):
                auto_cleanup_enabled = self.dockwidget._pg_auto_cleanup_enabled
            
            service.cleanup(
                session_id=self.session_id,
                temp_schema=self.app_postgresql_temp_schema,
                project_layers=self.PROJECT_LAYERS,
                dockwidget=self.dockwidget,
                auto_cleanup_enabled=auto_cleanup_enabled,
                postgresql_available=POSTGRESQL_AVAILABLE
            )
            
            # Clear app-level structures
            self.PROJECT_LAYERS.clear()
            self.project_datasources.clear()
            
            # v3.0: Cleanup hexagonal architecture services
            if HEXAGONAL_AVAILABLE:
                try:
                    _cleanup_hexagonal_services()
                    logger.debug("FilterMate: Hexagonal services cleaned up")
                except Exception as e:
                    logger.debug(f"FilterMate: Hexagonal services cleanup error: {e}")
            return
        
        # Service not available - minimal cleanup
        logger.warning("LayerLifecycleService not available - performing minimal cleanup")
        self.PROJECT_LAYERS.clear()
        self.project_datasources.clear()
        
        if HEXAGONAL_AVAILABLE:
            try:
                _cleanup_hexagonal_services()
            except Exception as e:
                logger.debug(f"FilterMate: Hexagonal services cleanup error: {e}")


    def _cleanup_postgresql_session_views(self):
        """
        Clean up all PostgreSQL materialized views created by this session.
        
        Delegates to LayerLifecycleService.cleanup_postgresql_session_views().
        """
        service = self._get_layer_lifecycle_service()
        if service:
            service.cleanup_postgresql_session_views(
                session_id=self.session_id,
                temp_schema=self.app_postgresql_temp_schema,
                project_layers=self.PROJECT_LAYERS,
                postgresql_available=POSTGRESQL_AVAILABLE
            )
        else:
            logger.debug("LayerLifecycleService not available - skipping PostgreSQL cleanup")


    def __init__(self, plugin_dir):
        """v4.0 Sprint 16: Initialize FilterMate app with managers, services, and state."""
        self.iface, self.dockwidget, self.flags, self.plugin_dir = iface, None, {}, plugin_dir
        self.appTasks = {"filter":None,"unfilter":None,"reset":None,"export":None,"add_layers":None,"remove_layers":None,"remove_all_layers":None,"new_project":None,"project_read":None}
        self.tasks_descriptions = {'filter':'Filtering data','unfilter':'Unfiltering data','reset':'Reseting data','export':'Exporting data',
                                    'undo':'Undo filter','redo':'Redo filter','add_layers':'Adding layers','remove_layers':'Removing layers',
                                    'remove_all_layers':'Removing all layers','new_project':'New project','project_read':'Existing project loaded','reload_layers':'Reloading layers'}
        
        # History & Favorites
        history_max_size = self._get_history_max_size_from_config()
        self.history_manager = HistoryManager(max_size=history_max_size)
        logger.info(f"FilterMate: HistoryManager initialized for undo/redo functionality (max_size={history_max_size})")
        self._undo_redo_handler = UndoRedoHandler(self.history_manager, lambda: self.PROJECT_LAYERS, lambda: self.PROJECT, lambda: self.iface,
                                                   self._refresh_layers_and_canvas, lambda t, m: iface.messageBar().pushWarning(t, m)) if HEXAGONAL_AVAILABLE and UndoRedoHandler else None
        if self._undo_redo_handler:
            logger.info("FilterMate: UndoRedoHandler initialized (v4.0 migration)")
        self.favorites_manager = FavoritesManager(max_favorites=50)
        self.favorites_manager.load_from_project()
        logger.info(f"FilterMate: FavoritesManager initialized ({self.favorites_manager.count} favorites loaded)")
        
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
        
        # Note: Do NOT call self.run() here - it will be called from filter_mate.py
        # when the user actually activates the plugin to avoid QGIS initialization race conditions

    def _get_history_max_size_from_config(self):
        """
        Get the maximum history size from configuration.
        
        Reads the HISTORY.max_history_size setting from config.json
        to control how many filter operations are kept in the undo/redo stack.
        
        Returns:
            int: Maximum history size (default: 100)
        """
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
        """
        Initialize user feedback verbosity level from configuration.
        
        Loads the FEEDBACK_LEVEL setting from config.json and applies it
        to the feedback_config module to control message display.
        """
        try:
            from .config.feedback_config import set_feedback_level_from_string
            
            feedback_level = self.CONFIG_DATA.get("APP", {}).get("DOCKWIDGET", {}).get("FEEDBACK_LEVEL", {}).get("value", "normal")
            
            set_feedback_level_from_string(feedback_level)
            logger.info(f"FilterMate: Feedback level set to '{feedback_level}'")
            
        except Exception as e:
            logger.warning(f"FilterMate: Could not set feedback level: {e}. Using default 'normal'.")

    def _get_dock_position(self):
        """
        Get the dock widget position from configuration.
        
        Returns the Qt.DockWidgetArea corresponding to the configured
        DOCK_POSITION value in config.json.
        
        Returns:
            Qt.DockWidgetArea: The dock position (Left, Right, Top, or Bottom)
        
        Default:
            Qt.RightDockWidgetArea if configuration is missing or invalid
        """
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
        """
        Check for stale flags that might block operations and reset them.
        
        This is a STABILITY method to prevent deadlocks when flags get stuck due to
        errors or exceptions that bypass the normal finally blocks.
        
        Checks:
        - _loading_new_project: Should not be set for more than FLAG_TIMEOUT_MS
        - _initializing_project: Should not be set for more than FLAG_TIMEOUT_MS
        - _pending_add_layers_tasks: Should not exceed MAX_ADD_LAYERS_QUEUE
        
        Returns:
            bool: True if any flags were reset, False otherwise
        """
        import time
        current_time = time.time() * 1000  # Convert to milliseconds
        timeout = STABILITY_CONSTANTS['FLAG_TIMEOUT_MS']
        flags_reset = False
        
        # Check _loading_new_project flag timeout
        if self._loading_new_project:
            if self._loading_new_project_timestamp > 0:
                elapsed = current_time - self._loading_new_project_timestamp
                if elapsed > timeout:
                    logger.warning(f"🔧 STABILITY: Resetting stale _loading_new_project flag (elapsed: {elapsed:.0f}ms > {timeout}ms)")
                    self._loading_new_project = False
                    self._loading_new_project_timestamp = 0
                    flags_reset = True
            else:
                # Timestamp not set but flag is True - set timestamp now
                self._loading_new_project_timestamp = current_time
        
        # Check _initializing_project flag timeout
        if self._initializing_project:
            if self._initializing_project_timestamp > 0:
                elapsed = current_time - self._initializing_project_timestamp
                if elapsed > timeout:
                    logger.warning(f"🔧 STABILITY: Resetting stale _initializing_project flag (elapsed: {elapsed:.0f}ms > {timeout}ms)")
                    self._initializing_project = False
                    self._initializing_project_timestamp = 0
                    flags_reset = True
            else:
                # Timestamp not set but flag is True - set timestamp now
                self._initializing_project_timestamp = current_time
        
        # Check add_layers queue size
        max_queue = STABILITY_CONSTANTS['MAX_ADD_LAYERS_QUEUE']
        if len(self._add_layers_queue) > max_queue:
            logger.warning(f"🔧 STABILITY: Trimming add_layers queue from {len(self._add_layers_queue)} to {max_queue}")
            # Keep only the most recent items
            self._add_layers_queue = self._add_layers_queue[-max_queue:]
            flags_reset = True
        
        # Check pending tasks counter sanity
        if self._pending_add_layers_tasks < 0:
            logger.warning(f"🔧 STABILITY: Resetting negative _pending_add_layers_tasks counter: {self._pending_add_layers_tasks}")
            self._pending_add_layers_tasks = 0
            flags_reset = True
        elif self._pending_add_layers_tasks > 10:
            logger.warning(f"🔧 STABILITY: Resetting unreasonably high _pending_add_layers_tasks counter: {self._pending_add_layers_tasks}")
            self._pending_add_layers_tasks = 0
            flags_reset = True
        
        return flags_reset

    def _set_loading_flag(self, loading: bool):
        """
        Set _loading_new_project flag with timestamp tracking.
        
        Args:
            loading: True to set loading state, False to clear it
        """
        import time
        self._loading_new_project = loading
        if loading:
            self._loading_new_project_timestamp = time.time() * 1000
        else:
            self._loading_new_project_timestamp = 0

    def _set_initializing_flag(self, initializing: bool):
        """
        Set _initializing_project flag with timestamp tracking.
        
        Args:
            initializing: True to set initializing state, False to clear it
        """
        import time
        self._initializing_project = initializing
        if initializing:
            self._initializing_project_timestamp = time.time() * 1000
        else:
            self._initializing_project_timestamp = 0

    def force_reload_layers(self):
        """
        Force a complete reload of all layers in the current project.
        
        v4.0.2: Delegates to LayerLifecycleService.force_reload_layers()
        
        This method is useful when the dockwidget gets out of sync with the
        current project, or when switching projects does not properly reload layers.
        """
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
        """
        Initialize and display the FilterMate dockwidget.
        
        v4.4: Feature flag for AppInitializer delegation.
        Set USE_APP_INITIALIZER = True to enable new architecture.
        Keep False during testing period for safe rollback.
        
        Creates the dockwidget if it doesn't exist, initializes the database,
        connects signals for layer management, and displays the UI.
        Also processes any existing layers in the project on first run.
        
        DIAGNOSTIC LOGGING ENABLED: Logging startup phases to identify freeze point.
        
        This method can be called multiple times:
        - First call: creates dockwidget and initializes everything
        - Subsequent calls: shows existing dockwidget and refreshes layers if needed
        """
        
        # v4.4: Feature flag for AppInitializer delegation
        USE_APP_INITIALIZER = True  # Phase 4.6: ENABLED
        
        if USE_APP_INITIALIZER and self._app_initializer is not None:
            logger.info(f"v4.4: Delegating application initialization to AppInitializer")
            try:
                is_first_run = (self.dockwidget is None)
                success = self._app_initializer.initialize_application(is_first_run)
                if success:
                    return
                else:
                    logger.error(f"AppInitializer returned False - initialization failed")
            except Exception as e:
                logger.error(f"AppInitializer raised exception: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
        else:
            logger.error("AppInitializer not available - cannot initialize plugin")


    def _safe_layer_operation(self, layer, properties, operation):
        """
        Safely execute a layer operation by deferring to Qt event loop and re-fetching layer.
        
        CRASH FIX (v2.3.18): Signal handlers receive layer objects that may become
        invalid (C++ deleted) between signal emission and handling. This wrapper:
        1. Extracts the layer ID immediately (before it becomes invalid)
        2. Defers execution with QTimer.singleShot(0, ...) to let Qt stabilize
        3. Re-fetches fresh layer reference from QgsProject in the deferred callback
        
        This approach prevents Windows access violations that cannot be caught by try/except.
        
        Args:
            layer: Layer object from signal (may be stale)
            properties: Properties to pass to operation
            operation: Function to call with (fresh_layer, properties)
        """
        from qgis.PyQt.QtCore import QTimer
        
        # Extract layer ID before it potentially becomes invalid
        try:
            if layer is None:
                logger.debug("_safe_layer_operation: layer is None, skipping")
                return
            if sip.isdeleted(layer):
                logger.debug("_safe_layer_operation: layer already sip deleted, skipping")
                return
            layer_id = layer.id()
            if not layer_id:
                logger.debug("_safe_layer_operation: layer has no ID, skipping")
                return
        except (RuntimeError, OSError, SystemError) as e:
            logger.debug(f"_safe_layer_operation: failed to get layer ID: {e}")
            return
        
        # CRASH FIX (v2.3.18): Defer the operation to next Qt event loop iteration
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
        """
        Get a Spatialite connection with proper error handling.
        
        v4.5 DELEGATION: Uses DatasourceManager.get_spatialite_connection()
        v4.7 E7-S1: Functional fallback when manager unavailable.
        
        Returns:
            Connection object or None if connection fails
        """
        # v4.5: Feature flag for DatasourceManager delegation
        USE_DATASOURCE_MANAGER = True  # Phase 4.6: ENABLED
        
        if USE_DATASOURCE_MANAGER and self._datasource_manager:
            try:
                return self._datasource_manager.get_spatialite_connection()
            except Exception as e:
                logger.error(f"DatasourceManager.get_spatialite_connection failed: {e}, using fallback")
                # E7-S1 FALLBACK: Continue to legacy implementation below
        else:
            logger.warning("DatasourceManager not available, using fallback")
        
        # E7-S1 FALLBACK: Direct spatialite_connect() call
        try:
            from .modules.tasks import spatialite_connect
            conn = spatialite_connect(self.db_file_path)
            if conn:
                logger.debug("Spatialite connection created via fallback")
                return conn
            else:
                logger.error("Spatialite connection fallback returned None")
                return None
        except Exception as e:
            logger.error(f"Spatialite connection fallback failed: {e}")
            return None
    
    def _handle_remove_all_layers(self):
        """Handle remove all layers task.
        
        v4.0.2: Delegates to LayerLifecycleService.handle_remove_all_layers()
        
        Safely cleans up all layer state when all layers are removed from project.
        """
        service = self._get_layer_lifecycle_service()
        if not service:
            logger.error("LayerLifecycleService not available, cannot handle remove all layers")
            return
        
        service.handle_remove_all_layers(
            cancel_tasks_callback=self._safe_cancel_all_tasks,
            dockwidget=self.dockwidget
        )
    
    def _handle_project_initialization(self, task_name):
        """Handle project read/new project initialization.
        
        v4.0.2: Delegates to LayerLifecycleService.handle_project_initialization()
        
        Args:
            task_name: 'project_read' or 'new_project'
        """
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
        """
        Execute a filter/unfilter/reset task.
        
        v4.1: Extracted as callback for TaskOrchestrator.
        Contains the actual task creation and execution logic for filtering operations.
        
        Args:
            task_name: Name of the task ('filter', 'unfilter', 'reset')
            task_parameters: Parameters for task execution
        """
        from .modules.tasks import FilterEngineTask
        
        if self.dockwidget is None or self.dockwidget.current_layer is None:
            return
        
        current_layer = self.dockwidget.current_layer
        
        # Create task
        self.appTasks[task_name] = FilterEngineTask(
            self.tasks_descriptions[task_name], 
            task_name, 
            task_parameters
        )
        
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
        """
        Execute a layer management task.
        
        v4.1: Extracted as callback for TaskOrchestrator.
        Contains the actual task creation and execution logic for layer operations.
        
        Args:
            task_name: Name of the task ('add_layers', 'remove_layers')
            task_parameters: Parameters for task execution
        """
        from .modules.tasks import LayersManagementEngineTask
        
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
        """
        Legacy task dispatcher used as fallback when TaskOrchestrator unavailable.
        
        E7-S1: Minimal implementation for core operations only.
        Does NOT implement all features - just enough to keep plugin functional.
        
        Args:
            task_name: Task to execute ('filter', 'unfilter', 'reset', 'add_layers', etc.)
            data: Task-specific data
        """
        logger.debug(f"_legacy_dispatch_task: {task_name}")
        
        # Get task parameters
        task_parameters = self.get_task_parameters(task_name, data)
        if task_parameters is None:
            logger.warning(f"Cannot execute task {task_name}: parameters are None")
            return
        
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
        """
        Show one-time warning that plugin is running in degraded mode.
        
        E7-S1: Uses QSettings to track if warning already shown this session.
        """
        # Check if we've already shown the warning this session
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
        if not self.dockwidget:
            return
        
        # Set saved layer ID for protection
        if self._current_layer_id_before_filter:
            self.dockwidget._saved_layer_id_before_filter = self._current_layer_id_before_filter
        
        # Set filtering in progress flag
        self.dockwidget._filtering_in_progress = True
        logger.info("v4.1: 🔒 Filtering protection enabled")
        
        # Disconnect signals and block Qt signals on combobox
        try:
            self.dockwidget.manageSignal(["FILTERING", "CURRENT_LAYER"], 'disconnect')
            self.dockwidget.comboBox_filtering_current_layer.blockSignals(True)
            self.dockwidget.manageSignal(["QGIS", "LAYER_TREE_VIEW"], 'disconnect')
        except Exception as e:
            logger.debug(f"Could not disconnect signals: {e}")
    
    def _show_filter_start_message(self, task_name, task_parameters, layers_props, layers, current_layer):
        """Show informational message about filtering operation starting."""
        layer_count = len(layers) + 1
        source_provider_type = task_parameters["infos"].get("layer_provider_type", "unknown")
        
        # Determine dominant backend
        distant_provider_types = [lp.get("layer_provider_type", "unknown") for lp in layers_props]
        
        if 'spatialite' in distant_provider_types:
            provider_type = 'spatialite'
        elif 'postgresql' in distant_provider_types:
            provider_type = 'postgresql'
        elif distant_provider_types:
            provider_type = distant_provider_types[0]
        else:
            provider_type = source_provider_type
        
        # Check for forced backends
        is_fallback = False
        forced_backends = getattr(self.dockwidget, 'forced_backends', {}) if self.dockwidget else {}
        if forced_backends:
            all_layer_ids = [current_layer.id()] + [l.id() for l in layers]
            forced_types = set(forced_backends.get(lid) for lid in all_layer_ids if lid in forced_backends)
            if len(forced_types) == 1 and None not in forced_types:
                provider_type = list(forced_types)[0]
                is_fallback = (provider_type == 'ogr')
        
        # Check PostgreSQL fallback
        if not is_fallback and provider_type == 'postgresql':
            is_fallback = task_parameters["infos"].get("postgresql_connection_available", True) is False
        
        show_backend_info(provider_type, layer_count, operation=task_name, is_fallback=is_fallback)
    
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
        Orchestrate execution of FilterMate tasks.
        
        Central dispatcher for all plugin operations including filtering, layer management,
        and project operations. Creates appropriate task objects and manages their execution
        through QGIS task manager.
        
        .. deprecated:: 4.1.0
            This method delegates to TaskOrchestrator when available.
            Direct task execution logic is being migrated to _execute_filter_task() 
            and _execute_layer_task() methods.
        
        Args:
            task_name (str): Name of task to execute. Must be one of:
                - 'filter': Apply filters to layers
                - 'unfilter': Remove filters from layers
                - 'reset': Reset layer state
                - 'add_layers': Process newly added layers
                - 'remove_layers': Clean up removed layers
                - 'remove_all_layers': Clear all layer data
                - 'project_read': Handle project load
                - 'new_project': Initialize new project
            data: Task-specific data (layers list, parameters, etc.)
                
        Raises:
            AssertionError: If task_name is not recognized
            
        Notes:
            - Cancels conflicting active tasks before starting new ones
            - Shows progress messages in QGIS message bar
            - Automatically connects task completion signals
        """

        assert task_name in list(self.tasks_descriptions.keys())
        
        # v4.1: Feature flag for TaskOrchestrator delegation
        # Set USE_TASK_ORCHESTRATOR = True to enable new architecture
        # Keep False during testing period for safe rollback
        USE_TASK_ORCHESTRATOR = True  # Phase 4.6: ENABLED
        
        if USE_TASK_ORCHESTRATOR and self._task_orchestrator is not None:
            logger.info(f"v4.1: Delegating task '{task_name}' to TaskOrchestrator")
            try:
                self._task_orchestrator.dispatch_task(task_name, data)
                return
            except Exception as e:
                logger.error(f"TaskOrchestrator failed: {e}, using fallback")
                # E7-S1 FALLBACK: Continue to legacy implementation below
        else:
            logger.warning("TaskOrchestrator not available, using fallback")
        
        # E7-S1 FALLBACK: Legacy task dispatch
        logger.info(f"Executing task fallback for: {task_name}")
        self._legacy_dispatch_task(task_name, data)


    def _safe_cancel_all_tasks(self):
        """
        Safely cancel all tasks in the task manager to avoid access violations.
        
        .. deprecated:: 4.0.0
            Delegates to TaskManagementService.safe_cancel_all_tasks()
        
        Note: We cancel tasks individually instead of using cancelAll() to avoid
        Windows access violations that occur when cancelAll() is called from Qt signals
        during project transitions.
        """
        # v4.0: Delegate to TaskManagementService
        service = self._get_task_management_service()
        if service:
            service.safe_cancel_all_tasks()
            return
        
        # Fallback to legacy implementation
        try:
            task_manager = QgsApplication.taskManager()
            if not task_manager:
                return
            
            # Get all active tasks and cancel them
            # Note: QgsTask doesn't have taskId() method, we iterate by index
            count = task_manager.count()
            for i in range(count - 1, -1, -1):  # Iterate backwards to avoid index issues
                task = task_manager.task(i)
                if task and task.canCancel():
                    task.cancel()
                    
        except Exception as e:
            logger.warning(f"Could not cancel tasks: {e}")

    def _cancel_layer_tasks(self, layer_id):
        """
        Cancel all running tasks for a specific layer to prevent access violations.
        
        Delegates to TaskManagementService.cancel_layer_tasks().
        
        Args:
            layer_id: The ID of the layer whose tasks should be cancelled
        """
        service = self._get_task_management_service()
        if service:
            service.cancel_layer_tasks(layer_id, self.dockwidget)
        else:
            logger.warning("TaskManagementService not available, cannot cancel layer tasks")

    def _handle_layer_task_terminated(self, task_name):
        """Handle layer management task termination (failure or cancellation).
        
        This method is called when a LayersManagementEngineTask is terminated
        (cancelled or failed) without emitting resultingLayers signal. It ensures
        the UI is not left in a disabled/grey state.
        
        Args:
            task_name (str): Name of the task that was terminated ('add_layers', 'remove_layers')
        """
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
                # No layers - update UI to show waiting state
                logger.info("No layers available after task termination")
                if hasattr(self.dockwidget, 'backend_indicator_label') and self.dockwidget.backend_indicator_label:
                    self.dockwidget.backend_indicator_label.setText("...")
                    self.dockwidget.backend_indicator_label.setStyleSheet("""
                        QLabel#label_backend_indicator {
                            color: #7f8c8d;
                            font-size: 9pt;
                            font-weight: 600;
                            padding: 3px 10px;
                            border-radius: 12px;
                            border: none;
                            background-color: #ecf0f1;
                        }
                    """)
        else:
            # PROJECT_LAYERS has data - just refresh UI
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
        """Pre-warm query cache for loaded layers to reduce cold-start latency.
        
        PERFORMANCE v2.6.0: After layers are added, pre-compute cache keys for
        common filter predicates (equals, intersects, contains, within).
        This reduces latency on first filter operations.
        
        Called automatically after successful add_layers completion.
        """
        try:
            # Only warm cache if we have layers
            if not self.PROJECT_LAYERS:
                return
            
            from infrastructure.cache import warm_cache_for_project
            
            # Collect layer info for cache warming
            layers_info = []
            for layer_id, layer_info in self.PROJECT_LAYERS.items():
                layer = layer_info.get('layer')
                if layer and is_valid_layer(layer):
                    provider_type = layer_info.get('layer_provider_type', 'unknown')
                    layers_info.append({
                        'id': layer_id,
                        'provider_type': provider_type
                    })
            
            if layers_info:
                # Warm cache for common predicates
                common_predicates = ['equals', 'intersects', 'contains', 'within']
                warmed_count = warm_cache_for_project(layers_info, common_predicates)
                if warmed_count > 0:
                    logger.debug(f"PERFORMANCE: Pre-warmed {warmed_count} cache entries for {len(layers_info)} layers")
        except ImportError:
            # query_cache module not available - skip warming
            pass
        except Exception as e:
            # Don't fail on cache warming errors
            logger.debug(f"Cache warming skipped: {e}")

    def _is_dockwidget_ready_for_filtering(self):
        """Check if dockwidget is fully ready for filtering operations.
        
        Verifies that:
        - Dockwidget exists
        - Widgets are initialized (via widgetsInitialized signal)
        - Layer combobox has items
        - Current layer is set
        - Widgets are ready flag is set
        
        Returns:
            bool: True if ready for filtering, False otherwise
        """
        if self.dockwidget is None:
            logger.debug("Dockwidget not ready: dockwidget is None")
            return False
        
        # Primary check: use the signal-based flag
        # FALLBACK: If signal wasn't received but dockwidget.widgets_initialized is True, sync the flags
        if not self._widgets_ready:
            # Check if dockwidget has widgets_initialized=True despite signal not received
            if hasattr(self.dockwidget, 'widgets_initialized') and self.dockwidget.widgets_initialized:
                logger.warning("⚠️ FALLBACK: Signal not received but dockwidget.widgets_initialized=True, syncing flags")
                self._widgets_ready = True
                # Continue to other checks
            else:
                logger.debug(f"Dockwidget not ready: widgetsInitialized signal not yet received (_widgets_ready={self._widgets_ready})")
                return False
        
        # Secondary check: verify widgets_initialized attribute (redundant after fallback but kept for safety)
        if not hasattr(self.dockwidget, 'widgets_initialized') or not self.dockwidget.widgets_initialized:
            logger.debug("Dockwidget not ready: widgets_initialized attribute is False")
            return False
        
        # Check if layer combobox has items
        if hasattr(self.dockwidget, 'cbb_layers') and self.dockwidget.cbb_layers:
            if self.dockwidget.cbb_layers.count() == 0:
                logger.debug("Dockwidget not ready: layer combobox is empty")
                return False
        
        # Check if current layer is set
        if self.dockwidget.current_layer is None:
            logger.debug("Dockwidget not ready: no current layer")
            return False
        
        logger.debug("✓ Dockwidget is fully ready for filtering")
        return True

    def _on_widgets_initialized(self):
        """Callback when dockwidget widgets are fully initialized.
        
        This is called via widgetsInitialized signal when the dockwidget
        has finished creating and connecting all its widgets. It's a safe
        point to perform operations that require fully functional UI.
        """
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
        Try to delegate filter task to hexagonal architecture controllers.
        
        Implements the Strangler Fig pattern: new code path via controllers
        with automatic fallback to legacy if delegation fails.
        
        Args:
            task_name: Name of the task ('filter', 'unfilter', 'reset')
            data: Optional task data
            
        Returns:
            True if delegation succeeded, False to use legacy path
        """
        # Check prerequisites
        if not HEXAGONAL_AVAILABLE:
            logger.debug("Controller delegation skipped: hexagonal architecture not available")
            return False
        
        if self.dockwidget is None:
            logger.debug("Controller delegation skipped: dockwidget not available")
            return False
        
        # Get controller integration from dockwidget
        integration = getattr(self.dockwidget, '_controller_integration', None)
        if integration is None or not integration.enabled:
            logger.debug("Controller delegation skipped: controller integration not enabled")
            return False
        
        try:
            # Delegate based on task type
            if task_name == 'filter':
                # Sync controller state from current UI before execution
                integration.sync_from_dockwidget()
                
                # Execute through controller
                success = integration.delegate_execute_filter()
                if success:
                    logger.info("v3.0: Filter executed via FilteringController")
                    return True
                else:
                    logger.debug("v3.0: FilteringController.execute_filter() returned False")
                    return False
            
            elif task_name == 'unfilter':
                # Unfilter is currently handled by legacy code
                # TODO: Implement delegate_unfilter() in controllers
                logger.debug("Controller delegation for 'unfilter' not yet implemented")
                return False
            
            elif task_name == 'reset':
                # Reset is currently handled by legacy code
                # TODO: Implement delegate_reset() in controllers
                logger.debug("Controller delegation for 'reset' not yet implemented")
                return False
            
            else:
                logger.debug(f"Controller delegation not available for task: {task_name}")
                return False
            
        except Exception as e:
            logger.warning(f"v3.0: Controller delegation failed, falling back to legacy: {e}")
            return False
    
    # ========================================
    # AUTO-OPTIMIZATION METHODS
    # ========================================
    
    def _check_and_confirm_optimizations(self, current_layer, task_parameters):
        """
        Check for optimization opportunities and ask user for confirmation.
        
        .. deprecated:: 4.2.0
            Delegates to OptimizationManager.check_and_confirm_optimizations().
        
        This method analyzes the layers being filtered and determines if any
        optimizations (like centroid usage) would benefit the operation.
        If optimizations are available and the "ask before apply" setting is
        enabled, it shows a confirmation dialog to the user.
        
        Args:
            current_layer: The source layer for filtering
            task_parameters: The task parameters dictionary
            
        Returns:
            tuple: (approved_optimizations dict, auto_apply_optimizations bool)
                - approved_optimizations: {layer_id: {optimization_type: bool}}
                - auto_apply_optimizations: True if auto-apply is enabled
        """
        # v4.2: Delegate to OptimizationManager
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
        """
        Apply accepted optimization choices to UI widgets.
        
        .. deprecated:: 4.2.0
            Delegates to OptimizationManager.apply_optimization_to_ui_widgets().
        
        When user accepts optimizations in the confirmation dialog, this method
        updates the corresponding checkboxes and other UI controls to reflect
        their choices. This ensures visual consistency between the dialog
        selections and the main UI state.
        
        Args:
            selected_optimizations: Dict of {optimization_type: bool} choices
                e.g., {'use_centroid_distant': True, 'simplify_geometry': False}
        
        v2.7.1: New method for UI synchronization after optimization acceptance
        v2.8.7: Added support for use_centroid_distant optimization type
        v4.2.0: Delegates to OptimizationManager
        """
        # v4.2: Delegate to OptimizationManager
        if self._optimization_manager is not None:
            try:
                self._optimization_manager.apply_optimization_to_ui_widgets(selected_optimizations)
                return
            except Exception as e:
                logger.warning(f"v4.2: OptimizationManager UI update failed: {e}")
        
        # v4.7: Minimal fallback - full logic is in OptimizationManager
        logger.debug("UI widget optimization skipped (manager unavailable)")
    
    def _build_layers_to_filter(self, current_layer):
        """Build list of layers to filter with validation.
        
        v4.6: Delegates to LayerFilterBuilder for God Class reduction.
        
        Args:
            current_layer: Source layer for filtering
            
        Returns:
            list: List of validated layer info dictionaries
        """
        # v4.6: Delegate to LayerFilterBuilder
        if LayerFilterBuilder is not None:
            try:
                builder = LayerFilterBuilder(self.PROJECT_LAYERS, self.PROJECT)
                return builder.build_layers_to_filter(current_layer)
            except Exception as e:
                logger.error(f"LayerFilterBuilder failed: {e}. Falling back to minimal logic.")
        
        # Minimal fallback (should not happen in normal operation)
        layers_to_filter = []
        if current_layer.id() not in self.PROJECT_LAYERS:
            logger.warning(f"_build_layers_to_filter: layer {current_layer.name()} not in PROJECT_LAYERS")
            return layers_to_filter
        
        raw_layers_list = self.PROJECT_LAYERS[current_layer.id()]["filtering"].get("layers_to_filter", [])
        for key in raw_layers_list:
            if key in self.PROJECT_LAYERS:
                layers_to_filter.append(self.PROJECT_LAYERS[key]["infos"].copy())
        
        logger.info(f"Built layers_to_filter (fallback) with {len(layers_to_filter)} layers")
        return layers_to_filter
    
    def _initialize_filter_history(self, current_layer, layers_to_filter, task_parameters):
        """Initialize filter history for source and associated layers.
        
        Captures the CURRENT state of all layers BEFORE filtering is applied.
        This ensures that undo will properly restore all layers to their pre-filter state.
        
        Args:
            current_layer: Source layer
            layers_to_filter: List of layers to be filtered
            task_parameters: Task parameters with layer info
        """
        # Initialize per-layer history for source layer if needed
        history = self.history_manager.get_or_create_history(current_layer.id())
        if len(history._states) == 0:
            # Push initial unfiltered state for source layer
            current_filter = current_layer.subsetString()
            current_count = current_layer.featureCount()
            history.push_state(
                expression=current_filter,
                feature_count=current_count,
                description="Initial state (before first filter)",
                metadata={"operation": "initial", "backend": task_parameters["infos"].get("layer_provider_type", "unknown")}
            )
            logger.info(f"FilterMate: Initialized history with current state for source layer {current_layer.id()}")
        
        # Initialize per-layer history for associated layers
        remote_layers_info = {}
        for layer_info in layers_to_filter:
            layer_id = layer_info.get("layer_id")
            if layer_id and layer_id in self.PROJECT_LAYERS:
                assoc_layers = [l for l in self.PROJECT.mapLayers().values() if l.id() == layer_id]
                if len(assoc_layers) == 1:
                    assoc_layer = assoc_layers[0]
                    assoc_history = self.history_manager.get_or_create_history(assoc_layer.id())
                    if len(assoc_history._states) == 0:
                        assoc_filter = assoc_layer.subsetString()
                        assoc_count = assoc_layer.featureCount()
                        assoc_history.push_state(
                            expression=assoc_filter,
                            feature_count=assoc_count,
                            description="Initial state (before first filter)",
                            metadata={"operation": "initial", "backend": layer_info.get("layer_provider_type", "unknown")}
                        )
                        logger.info(f"FilterMate: Initialized history for associated layer {assoc_layer.name()}")
                    
                    # Collect CURRENT state for all remote layers (for global state)
                    remote_layers_info[assoc_layer.id()] = (assoc_layer.subsetString(), assoc_layer.featureCount())
        
        # ALWAYS push global state BEFORE filtering if we have remote layers
        # This captures the pre-filter state of ALL currently selected remote layers
        # Critical fix: we must capture the state before EACH filter operation, not just the first one
        if remote_layers_info:
            current_filter = current_layer.subsetString()
            current_count = current_layer.featureCount()
            self.history_manager.push_global_state(
                source_layer_id=current_layer.id(),
                source_expression=current_filter,
                source_feature_count=current_count,
                remote_layers=remote_layers_info,
                description=f"Pre-filter state ({len(remote_layers_info) + 1} layers)",
                metadata={"operation": "pre_filter", "backend": task_parameters["infos"].get("layer_provider_type", "unknown")}
            )
            logger.info(f"FilterMate: Captured pre-filter global state ({len(remote_layers_info) + 1} layers)")
    
    def _build_common_task_params(self, features, expression, layers_to_filter, include_history=False):
        """
        Build common task parameters for filter/unfilter/reset operations.
        
        Delegates to TaskParameterBuilder.build_common_task_params().
        """
        if TaskParameterBuilder and self.dockwidget:
            builder = TaskParameterBuilder(
                dockwidget=self.dockwidget,
                project_layers=self.PROJECT_LAYERS,
                config_data=self.CONFIG_DATA
            )
            return builder.build_common_task_params(
                features=features,
                expression=expression,
                layers_to_filter=layers_to_filter,
                include_history=include_history,
                session_id=self.session_id,
                db_file_path=self.db_file_path,
                project_uuid=self.project_uuid,
                history_manager=self.history_manager if include_history else None
            )
        
        # TaskParameterBuilder required
        logger.error("TaskParameterBuilder not available - cannot build task parameters")
        return None
    
    def _build_layer_management_params(self, layers, reset_flag):
        """
        Build parameters for layer management tasks (add/remove layers).
        
        Delegates to TaskParameterBuilder.build_layer_management_params().
        """
        if TaskParameterBuilder and self.dockwidget:
            builder = TaskParameterBuilder(
                dockwidget=self.dockwidget,
                project_layers=self.PROJECT_LAYERS,
                config_data=self.CONFIG_DATA
            )
            return builder.build_layer_management_params(
                layers=layers,
                reset_flag=reset_flag,
                project_layers=self.PROJECT_LAYERS,
                config_data=self.CONFIG_DATA,
                db_file_path=self.db_file_path,
                project_uuid=self.project_uuid,
                session_id=self.session_id
            )
        
        # TaskParameterBuilder required
        logger.error("TaskParameterBuilder not available - cannot build layer management parameters")
        return None

    def get_task_parameters(self, task_name, data=None):
        """
        Build parameter dictionary for task execution.
        
        Constructs the complete parameter set needed by FilterEngineTask or
        LayersManagementEngineTask, including layer properties, configuration,
        and backend-specific settings.
        
        Args:
            task_name (str): Name of the task requiring parameters
            data: Task-specific input data (typically layers or properties)
            
        Returns:
            dict: Complete task parameter dictionary with structure:
                {
                    'plugin_dir': str,
                    'config_data': dict,
                    'project': QgsProject,
                    'project_layers': dict,
                    'task': dict  # Task-specific parameters
                }
                
        Notes:
            - For filtering tasks: includes current layer and layers to filter
            - For layer management: includes layers being added/removed
            - Automatically detects PostgreSQL availability
        """

        if task_name in [name for name in self.tasks_descriptions.keys() if "layer" not in name]:

            if self.dockwidget is None or self.dockwidget.current_layer is None:
                return None
            
            current_layer = self.dockwidget.current_layer
            
            # v4.7: Create TaskParameterBuilder once for all delegations
            builder = None
            if TaskParameterBuilder and self.dockwidget:
                builder = TaskParameterBuilder(
                    dockwidget=self.dockwidget,
                    project_layers=self.PROJECT_LAYERS,
                    config_data=self.CONFIG_DATA
                )
            
            # v4.7: Delegate layer validation
            if builder:
                error = builder.validate_current_layer_for_task(current_layer, self.PROJECT_LAYERS)
                if error:
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
            try:
                if builder:
                    features, expression = builder.get_and_validate_features(task_name)
                else:
                    features, expression = [], ""
            except ValueError:
                return None  # single_selection mode with no features

            if task_name in ('filter', 'unfilter', 'reset'):
                # Build validated list of layers to filter
                layers_to_filter = self._build_layers_to_filter(current_layer)
                
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
        """
        Refresh source layer and map canvas with stabilization for Spatialite.
        
        v4.7: Delegates to LayerRefreshManager.refresh_layer_and_canvas().
        Legacy fallback for backward compatibility.
        
        Args:
            source_layer (QgsVectorLayer): Layer to refresh
        """
        # v4.7: Delegate to LayerRefreshManager when available
        if self._layer_refresh_manager is not None:
            self._layer_refresh_manager.refresh_layer_and_canvas(source_layer)
            return
        
        # Legacy fallback (for when hexagonal services unavailable)
        from qgis.PyQt.QtCore import QTimer
        
        provider_type = source_layer.providerType() if source_layer else None
        needs_stabilization = provider_type in ('spatialite', 'ogr')
        
        def do_refresh():
            try:
                with GdalErrorHandler():
                    thresholds = get_optimization_thresholds(ENV_VARS)
                    MAX_FEATURES = thresholds['update_extents_threshold']
                    feature_count = source_layer.featureCount() if source_layer else 0
                    if feature_count >= 0 and feature_count < MAX_FEATURES:
                        source_layer.updateExtents()
                    source_layer.triggerRepaint()
                    self.iface.mapCanvas().refresh()
            except Exception as e:
                logger.warning(f"_refresh_layers_and_canvas: refresh failed: {e}")
        
        if needs_stabilization:
            stabilization_ms = STABILITY_CONSTANTS.get('SPATIALITE_STABILIZATION_MS', 200)
            QTimer.singleShot(stabilization_ms, do_refresh)
        else:
            # No delay needed for PostgreSQL and other providers
            do_refresh()
    
    def _push_filter_to_history(self, source_layer, task_parameters, feature_count, provider_type, layer_count):
        """
        Push filter state to history for source and associated layers.
        
        v4.0: Delegated to UndoRedoHandler.
        
        Args:
            source_layer (QgsVectorLayer): Source layer being filtered
            task_parameters (dict): Task parameters containing layers info
            feature_count (int): Number of features in filtered result
            provider_type (str): Backend provider type
            layer_count (int): Number of layers affected
        """
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
        """
        Update undo/redo button states based on history availability.
        
        v4.0: Delegates to UndoRedoHandler.
        """
        if not self.dockwidget:
            return
        
        undo_btn = getattr(self.dockwidget, 'pushButton_action_undo_filter', None)
        redo_btn = getattr(self.dockwidget, 'pushButton_action_redo_filter', None)
        
        if not undo_btn or not redo_btn:
            return
        
        if self._undo_redo_handler:
            current_layer = self.dockwidget.current_layer
            layers_to_filter = []
            if current_layer and current_layer.id() in self.dockwidget.PROJECT_LAYERS:
                layers_to_filter = self.dockwidget.PROJECT_LAYERS[current_layer.id()]["filtering"].get("layers_to_filter", [])
            
            self._undo_redo_handler.update_button_states(
                current_layer=current_layer,
                layers_to_filter=layers_to_filter,
                undo_button=undo_btn,
                redo_button=redo_btn
            )
        else:
            # Fallback: disable both buttons
            undo_btn.setEnabled(False)
            redo_btn.setEnabled(False)
    
    def handle_undo(self):
        """
        Handle undo operation with intelligent layer selection logic.
        
        v4.0: Delegated to UndoRedoHandler for God Class reduction.
        v4.7 E7-S1: Functional fallback when handler unavailable.
        
        Logic:
        - If pushButton_checkable_filtering_layers_to_filter is checked AND has remote layers: undo all layers globally
        - If pushButton_checkable_filtering_layers_to_filter is unchecked: undo only source layer
        """
        if not self.dockwidget or not self.dockwidget.current_layer:
            logger.warning("FilterMate: No current layer for undo")
            return
        
        # v4.0: Delegate to handler if available
        if self._undo_redo_handler:
            source_layer = self.dockwidget.current_layer
            layers_to_filter = self.dockwidget.PROJECT_LAYERS.get(
                source_layer.id(), {}
            ).get("filtering", {}).get("layers_to_filter", [])
            
            button_is_checked = self.dockwidget.pushButton_checkable_filtering_layers_to_filter.isChecked()
            
            # Set filtering protection
            self.dockwidget._filtering_in_progress = True
            logger.info("v4.0: 🔒 handle_undo - Filtering protection enabled (delegated)")
            
            try:
                result = self._undo_redo_handler.handle_undo(
                    source_layer=source_layer,
                    layers_to_filter=layers_to_filter,
                    use_global=button_is_checked,
                    dockwidget=self.dockwidget
                )
                if result:
                    self.update_undo_redo_buttons()
            finally:
                self.dockwidget._filtering_in_progress = False
                logger.info("v4.0: 🔓 handle_undo - Filtering protection disabled")
        else:
            # E7-S1 FALLBACK: Use HistoryManager directly
            logger.warning("UndoRedoHandler not available, using fallback")
            
            source_layer = self.dockwidget.current_layer
            layers_to_filter = self.dockwidget.PROJECT_LAYERS.get(
                source_layer.id(), {}
            ).get("filtering", {}).get("layers_to_filter", [])
            button_is_checked = self.dockwidget.pushButton_checkable_filtering_layers_to_filter.isChecked()
            
            history = self.history_manager.get_history(source_layer.id())
            
            if history and history.can_undo():
                # Set filtering protection
                self.dockwidget._filtering_in_progress = True
                
                try:
                    previous_state = history.undo()
                    if previous_state:
                        # Apply to source layer
                        safe_set_subset_string(source_layer, previous_state.expression)
                        
                        # Apply to remote layers if global mode
                        if button_is_checked and layers_to_filter:
                            for layer_id in layers_to_filter:
                                remote_layer = self.PROJECT.mapLayer(layer_id)
                                if remote_layer:
                                    remote_history = self.history_manager.get_history(layer_id)
                                    if remote_history and remote_history.can_undo():
                                        remote_state = remote_history.undo()
                                        if remote_state:
                                            safe_set_subset_string(remote_layer, remote_state.expression)
                        
                        self._refresh_layers_and_canvas(source_layer)
                        logger.info(f"Undo fallback: restored filter '{previous_state.description}'")
                        show_info(f"Filtre annulé: {previous_state.description}")
                finally:
                    self.dockwidget._filtering_in_progress = False
                
                # Update button states
                self.update_undo_redo_buttons()
            else:
                show_warning("Aucune opération à annuler")
    
    def handle_redo(self):
        """
        Handle redo operation with intelligent layer selection logic.
        
        v4.0: Delegated to UndoRedoHandler for God Class reduction.
        v4.7 E7-S1: Functional fallback when handler unavailable.
        
        Logic:
        - If pushButton_checkable_filtering_layers_to_filter is checked AND has remote layers: redo all layers globally
        - If pushButton_checkable_filtering_layers_to_filter is unchecked: redo only source layer
        """
        if not self.dockwidget or not self.dockwidget.current_layer:
            logger.warning("FilterMate: No current layer for redo")
            return
        
        # v4.0: Delegate to handler if available
        if self._undo_redo_handler:
            source_layer = self.dockwidget.current_layer
            layers_to_filter = self.dockwidget.PROJECT_LAYERS.get(
                source_layer.id(), {}
            ).get("filtering", {}).get("layers_to_filter", [])
            
            button_is_checked = self.dockwidget.pushButton_checkable_filtering_layers_to_filter.isChecked()
            
            # Set filtering protection
            self.dockwidget._filtering_in_progress = True
            logger.info("v4.0: 🔒 handle_redo - Filtering protection enabled (delegated)")
            
            try:
                result = self._undo_redo_handler.handle_redo(
                    source_layer=source_layer,
                    layers_to_filter=layers_to_filter,
                    use_global=button_is_checked,
                    dockwidget=self.dockwidget
                )
                if result:
                    self.update_undo_redo_buttons()
            finally:
                self.dockwidget._filtering_in_progress = False
                logger.info("v4.0: 🔓 handle_redo - Filtering protection disabled")
        else:
            # E7-S1 FALLBACK: Use HistoryManager directly
            logger.warning("UndoRedoHandler not available, using fallback")
            
            source_layer = self.dockwidget.current_layer
            layers_to_filter = self.dockwidget.PROJECT_LAYERS.get(
                source_layer.id(), {}
            ).get("filtering", {}).get("layers_to_filter", [])
            button_is_checked = self.dockwidget.pushButton_checkable_filtering_layers_to_filter.isChecked()
            
            history = self.history_manager.get_history(source_layer.id())
            
            if history and history.can_redo():
                # Set filtering protection
                self.dockwidget._filtering_in_progress = True
                
                try:
                    next_state = history.redo()
                    if next_state:
                        # Apply to source layer
                        safe_set_subset_string(source_layer, next_state.expression)
                        
                        # Apply to remote layers if global mode
                        if button_is_checked and layers_to_filter:
                            for layer_id in layers_to_filter:
                                remote_layer = self.PROJECT.mapLayer(layer_id)
                                if remote_layer:
                                    remote_history = self.history_manager.get_history(layer_id)
                                    if remote_history and remote_history.can_redo():
                                        remote_state = remote_history.redo()
                                        if remote_state:
                                            safe_set_subset_string(remote_layer, remote_state.expression)
                        
                        self._refresh_layers_and_canvas(source_layer)
                        logger.info(f"Redo fallback: reapplied filter '{next_state.description}'")
                        show_info(f"Filtre réappliqué: {next_state.description}")
                finally:
                    self.dockwidget._filtering_in_progress = False
                
                # Update button states
                self.update_undo_redo_buttons()
            else:
                show_warning("Aucune opération à refaire")
    
    def _clear_filter_history(self, source_layer, task_parameters):
        """
        Clear filter history for source and associated layers.
        
        v4.0: Delegated to UndoRedoHandler for God Class reduction.
        
        Args:
            source_layer (QgsVectorLayer): Source layer whose history to clear
            task_parameters (dict): Task parameters containing layers info
        """
        if self._undo_redo_handler:
            remote_layer_ids = [
                lp.get("layer_id") 
                for lp in task_parameters.get("task", {}).get("layers", [])
                if lp.get("layer_id")
            ]
            self._undo_redo_handler.clear_filter_history(source_layer, remote_layer_ids)
        else:
            # Legacy fallback
            history = self.history_manager.get_history(source_layer.id())
            if history:
                history.clear()
            self.history_manager.clear_global_history()
    
    def _show_task_completion_message(self, task_name, source_layer, provider_type, layer_count, is_fallback=False):
        """
        Show success message with backend info and feature counts.
        
        Args:
            task_name (str): Name of completed task ('filter', 'unfilter', 'reset')
            source_layer (QgsVectorLayer): Source layer with results
            provider_type (str): Backend provider type
            layer_count (int): Number of layers affected
            is_fallback (bool): True if OGR was used as fallback
        """
        from .config.feedback_config import should_show_message
        
        feature_count = source_layer.featureCount()
        show_success_with_backend(provider_type, task_name, layer_count, is_fallback=is_fallback)
        
        # Only show feature count if configured to do so
        if should_show_message('filter_count'):
            if task_name == 'filter':
                show_info(
                    f"{feature_count:,} features visible in main layer"
                )
            elif task_name == 'unfilter':
                show_info(
                    f"All filters cleared - {feature_count:,} features visible in main layer"
                )
            elif task_name == 'reset':
                show_info(
                    f"{feature_count:,} features visible in main layer"
                )

    def filter_engine_task_completed(self, task_name, source_layer, task_parameters):
        """
        Handle completion of filtering operations.
        
        v4.3: Feature flag for FilterResultHandler delegation.
        Set USE_FILTER_RESULT_HANDLER = True to enable new architecture.
        Keep False during testing period for safe rollback.
        
        Called when FilterEngineTask completes successfully. Applies results to layers,
        updates UI, saves layer variables, and shows success messages.
        
        Args:
            task_name (str): Name of completed task ('filter', 'unfilter', 'reset')
            source_layer (QgsVectorLayer): Primary layer that was filtered
            task_parameters (dict): Original task parameters including results
            
        Notes:
            - Applies subset filters to all affected layers
            - Updates layer variables in Spatialite database
            - Refreshes dockwidget UI state
            - Shows success message with feature counts
            - Handles both single and multi-layer filtering
        """
        
        # v4.3: Feature flag for FilterResultHandler delegation
        USE_FILTER_RESULT_HANDLER = True  # Phase 4.6: ENABLED
        
        if USE_FILTER_RESULT_HANDLER and self._filter_result_handler is not None:
            logger.info(f"v4.3: Delegating filter completion to FilterResultHandler")
            try:
                # Get current_layer_id_before_filter from instance variable if available
                current_layer_id = getattr(self, '_current_layer_id_before_filter', None)
                self._filter_result_handler.handle_task_completion(
                    task_name=task_name,
                    source_layer=source_layer,
                    task_parameters=task_parameters,
                    current_layer_id_before_filter=current_layer_id
                )
                return
            except Exception as e:
                logger.error(f"FilterResultHandler failed: {e}, using fallback")
                iface.messageBar().pushWarning("FilterMate", "Opération en mode dégradé")
                # E7-S1 FALLBACK: Continue to legacy implementation below
        else:
            logger.warning("FilterResultHandler not available, using fallback")
        
        # E7-S1 FALLBACK: Legacy filter result handling
        logger.info(f"Executing filter completion fallback for task: {task_name}")
        
        try:
            # Apply subset filter to source layer
            self.apply_subset_filter(task_name, source_layer)
            
            # Apply filters to remote layers
            if "task" in task_parameters and "layers" in task_parameters["task"]:
                for layer_info in task_parameters["task"]["layers"]:
                    layer_id = layer_info.get("layer_id")
                    if layer_id:
                        remote_layers = [l for l in self.PROJECT.mapLayers().values() if l.id() == layer_id]
                        if len(remote_layers) == 1:
                            self.apply_subset_filter(task_name, remote_layers[0])
            
            # Refresh layers and canvas
            self._refresh_layers_and_canvas(source_layer)
            
            # Show success message
            feature_count = source_layer.featureCount()
            provider_type = task_parameters.get("infos", {}).get("layer_provider_type", "unknown")
            layer_count = len(task_parameters.get("task", {}).get("layers", [])) + 1
            
            show_success_with_backend(provider_type, task_name, layer_count)
            if task_name == 'filter':
                show_info(f"{feature_count:,} features visible in main layer")
            
            # Update UI if dockwidget available
            if self.dockwidget:
                try:
                    self.dockwidget._filtering_in_progress = False
                    self.dockwidget.comboBox_filtering_current_layer.blockSignals(False)
                    self.dockwidget.manageSignal(["FILTERING", "CURRENT_LAYER"], 'connect')
                    self.dockwidget.manageSignal(["QGIS", "LAYER_TREE_VIEW"], 'connect')
                    # E7-S1 MEDIUM-1 FIX: Reconnect filtering protection signals
                    self.dockwidget.reconnect_filtering_protection_signals()
                except Exception as e:
                    logger.debug(f"Could not reconnect signals: {e}")
            
            logger.info("Filter completion fallback executed successfully")
            
        except Exception as e:
            logger.error(f"Filter completion fallback failed: {e}")
            iface.messageBar().pushCritical("FilterMate", f"Erreur lors du filtrage: {str(e)}")


    def apply_subset_filter(self, task_name, layer):
        """
        Apply or remove subset filter expression on a layer.
        
        Uses FilterHistory module for proper undo/redo functionality.
        
        Args:
            task_name (str): Type of operation ('filter', 'unfilter', 'reset')
            layer (QgsVectorLayer): Layer to apply filter to
            
        Notes:
            - For 'unfilter': Uses history.undo() to return to previous state
            - For 'reset': Clears subset string and history
            - For 'filter': Applies expression from Spatialite database
            - Changes trigger layer refresh automatically
        """
        # Guard: ensure layer is usable
        if not is_layer_source_available(layer):
            logger.warning("apply_subset_filter called on invalid/missing-source layer; skipping.")
            iface.messageBar().pushWarning(
                "FilterMate",
                "La couche est invalide ou sa source est introuvable. Opération annulée."
            )
            return

        if task_name == 'unfilter':
            # v2.8.11: Clear Spatialite cache for this layer when unfiltering
            try:
                from infrastructure.cache import get_cache
                cache = get_cache()
                cache.clear_layer_cache(layer.id())
                logger.debug(f"FilterMate: Cleared Spatialite cache for {layer.name()}")
            except Exception as e:
                logger.debug(f"Could not clear Spatialite cache: {e}")
            
            # Use history manager for proper undo
            history = self.history_manager.get_history(layer.id())
            
            if history and history.can_undo():
                previous_state = history.undo()
                if previous_state:
                    safe_set_subset_string(layer, previous_state.expression)
                    logger.info(f"FilterMate: Undo applied - restored filter: {previous_state.description}")
                    
                    if layer.subsetString() != '':
                        self.PROJECT_LAYERS[layer.id()]["infos"]["is_already_subset"] = True
                    else:
                        self.PROJECT_LAYERS[layer.id()]["infos"]["is_already_subset"] = False
                    return
            else:
                # No history available - clear filter
                logger.info(f"FilterMate: No undo history available, clearing filter")
                safe_set_subset_string(layer, '')
                self.PROJECT_LAYERS[layer.id()]["infos"]["is_already_subset"] = False
                return
        
        # For 'filter' and 'reset' operations, use database history
        conn = self.get_spatialite_connection()
        if conn is None:
            return
        
        with conn:
            cur = conn.cursor()

            last_subset_string = ''

            # Use parameterized query to prevent SQL injection
            cur.execute(
                """SELECT * FROM fm_subset_history 
                   WHERE fk_project = ? AND layer_id = ? 
                   ORDER BY seq_order DESC LIMIT 1""",
                (str(self.project_uuid), layer.id())
            )

            results = cur.fetchall()

            if len(results) == 1:
                result = results[0]
                last_subset_string = result[6].replace("\'\'", "\'")

            if task_name == 'filter':
                safe_set_subset_string(layer, last_subset_string)

                if layer.subsetString() != '':
                    self.PROJECT_LAYERS[layer.id()]["infos"]["is_already_subset"] = True
                else:
                    self.PROJECT_LAYERS[layer.id()]["infos"]["is_already_subset"] = False

            elif task_name == 'reset':
                safe_set_subset_string(layer, '')
                self.PROJECT_LAYERS[layer.id()]["infos"]["is_already_subset"] = False

    def save_variables_from_layer(self, layer, layer_properties=None):
        """
        Save layer filtering properties to both QGIS variables and Spatialite database.
        
        v4.0: Delegates to VariablesPersistenceManager.
        
        Args:
            layer (QgsVectorLayer): Layer to save properties for
            layer_properties (list): List of tuples (key_group, key, value, type)
                If None or empty, saves all properties
        """
        if self._variables_manager:
            self._variables_manager.save_variables_from_layer(layer, layer_properties)
        else:
            logger.warning("VariablesPersistenceManager not available, cannot save layer variables")

    def remove_variables_from_layer(self, layer, layer_properties=None):
        """
        Remove layer filtering properties from QGIS variables and Spatialite database.
        
        v4.0: Delegates to VariablesPersistenceManager.
        
        Args:
            layer (QgsVectorLayer): Layer to remove properties from
            layer_properties (list): List of tuples (key_group, key)
                If None or empty, removes ALL filterMate variables for the layer
        """
        if self._variables_manager:
            self._variables_manager.remove_variables_from_layer(layer, layer_properties)
        else:
            logger.warning("VariablesPersistenceManager not available, cannot remove layer variables")


      

    def create_spatial_index_for_layer(self, layer):
        """
        Create spatial index for a layer.
        
        v4.5 DELEGATION: Uses DatasourceManager.create_spatial_index_for_layer()
        """
        # v4.5: Feature flag for DatasourceManager delegation
        USE_DATASOURCE_MANAGER = True  # Phase 4.6: ENABLED
        
        if USE_DATASOURCE_MANAGER and self._datasource_manager:
            try:
                self._datasource_manager.create_spatial_index_for_layer(layer)
                return
            except Exception as e:
                logger.error(f"DatasourceManager.create_spatial_index_for_layer failed: {e}. Falling back to legacy.")
        

    def init_filterMate_db(self):
        """
        Initialize FilterMate Spatialite database with required schema.
        
        v4.0: Delegates to DatabaseManager.
        
        Creates database file and tables if they do not exist. Sets up schema for
        storing project configurations, layer properties, and datasource information.
        
        Tables created:
        - fm_projects: Project metadata and UUIDs
        - fm_project_layers_properties: Layer filtering/export settings
        - fm_project_datasources: Data source connection info
        """
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
            
            # Configure FavoritesManager with SQLite database
            if hasattr(self, 'favorites_manager') and self.db_file_path and self.project_uuid:
                self.favorites_manager.set_database(self.db_file_path, str(self.project_uuid))
                self.favorites_manager.load_from_project()
                logger.info(f"FavoritesManager configured with SQLite database ({self.favorites_manager.count} favorites loaded)")

    def add_project_datasource(self, layer):
        """
        Add PostgreSQL datasource and create temp schema if needed.
        
        v4.5 DELEGATION: Uses DatasourceManager.add_project_datasource()
        
        Args:
            layer: PostgreSQL layer to get connection from
        """
        # v4.5: Feature flag for DatasourceManager delegation
        USE_DATASOURCE_MANAGER = True  # Phase 4.6: ENABLED
        
        if USE_DATASOURCE_MANAGER and self._datasource_manager:
            try:
                self._datasource_manager.add_project_datasource(layer)
                return
            except Exception as e:
                logger.error(f"DatasourceManager.add_project_datasource failed: {e}. Falling back to legacy.")
        

    def save_project_variables(self, name=None):
        """
        Save project variables to database.
        
        v4.0: Delegates to DatabaseManager.
        """
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
            # Also save to config file
            with open(ENV_VARS["CONFIG_JSON_PATH"], 'w') as outfile:
                outfile.write(json.dumps(self.CONFIG_DATA, indent=4))
            
            # Save favorites to project
            if hasattr(self, 'favorites_manager'):
                self.favorites_manager.save_to_project()
                logger.debug(f"Saved {self.favorites_manager.count} favorites to project")


    def layer_management_engine_task_completed(self, result_project_layers, task_name):
        """
        Handle completion of layer management tasks.
        
        v4.7: Delegates to LayerTaskCompletionHandler for God Class reduction.
        
        Called when LayersManagementEngineTask completes. Updates internal layer registry,
        refreshes UI, and handles layer addition/removal cleanup.
        
        Args:
            result_project_layers (dict): Updated PROJECT_LAYERS dictionary with all layer metadata
            task_name (str): Type of task completed (add_layers, remove_layers, etc.)
        """
        # v4.7: Delegate to LayerTaskCompletionHandler
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
                logger.warning(f"v4.7: LayerTaskCompletionHandler failed: {e}")
        
        # v4.7: Minimal fallback
        logger.debug("Layer task completion skipped (handler unavailable)")
    
    def _validate_layer_info(self, layer_key):
        """Validate layer structure and return layer info if valid.
        
        Args:
            layer_key: Layer ID to validate
            
        Returns:
            dict: Layer info or None if invalid
        """
        # STABILITY FIX: Guard against KeyError if layer_key not in PROJECT_LAYERS
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
        """
        Update project datasources for a given layer.
        
        v4.5 DELEGATION: Uses DatasourceManager.update_datasource_for_layer()
        
        Args:
            layer_info: Layer info dictionary
        """
        # v4.5: Feature flag for DatasourceManager delegation
        USE_DATASOURCE_MANAGER = True  # Phase 4.6: ENABLED
        
        if USE_DATASOURCE_MANAGER and self._datasource_manager:
            try:
                self._datasource_manager.update_datasource_for_layer(layer_info)
                return
            except Exception as e:
                logger.error(f"DatasourceManager.update_datasource_for_layer failed: {e}. Falling back to legacy.")
        

    def _remove_datasource_for_layer(self, layer_info):
        """
        Remove project datasources for a given layer.
        
        v4.5 DELEGATION: Uses DatasourceManager.remove_datasource_for_layer()
        
        Args:
            layer_info: Layer info dictionary
        """
        # v4.5: Feature flag for DatasourceManager delegation
        USE_DATASOURCE_MANAGER = True  # Phase 4.6: ENABLED
        
        if USE_DATASOURCE_MANAGER and self._datasource_manager:
            try:
                self._datasource_manager.remove_datasource_for_layer(layer_info)
                return
            except Exception as e:
                logger.error(f"DatasourceManager.remove_datasource_for_layer failed: {e}. Falling back to legacy.")
        

    def _force_ui_refresh_after_reload(self):
        """
        Force complete UI refresh after force_reload_layers.
        
        This method ensures the UI is updated even if PROJECT_LAYERS was empty initially.
        It retries a few times with increasing delays if layers are not ready yet.
        """
        from qgis.PyQt.QtCore import QTimer
        
        logger.info(f"Force UI refresh after reload - PROJECT_LAYERS count: {len(self.PROJECT_LAYERS)}")
        
        # Reset loading flag
        self._set_loading_flag(False)
        
        if self.dockwidget is None or not self.dockwidget.widgets_initialized:
            logger.debug("Cannot refresh UI: dockwidget not initialized")
            return
        
        # If PROJECT_LAYERS is still empty, retry after a delay (max 3 retries)
        if not hasattr(self, '_reload_retry_count'):
            self._reload_retry_count = 0
        
        if len(self.PROJECT_LAYERS) == 0:
            self._reload_retry_count += 1
            if self._reload_retry_count < 3:
                logger.warning(f"PROJECT_LAYERS still empty, retry {self._reload_retry_count}/3")
                # STABILITY FIX: Use weakref to prevent access violations
                weak_self = weakref.ref(self)
                def safe_force_refresh_retry():
                    strong_self = weak_self()
                    if strong_self is not None:
                        strong_self._force_ui_refresh_after_reload()
                QTimer.singleShot(1000, safe_force_refresh_retry)
                return
            else:
                logger.error("PROJECT_LAYERS still empty after 3 retries - layer loading may have failed")
                self._reload_retry_count = 0
                # Update indicator to show error state
                if hasattr(self.dockwidget, 'backend_indicator_label') and self.dockwidget.backend_indicator_label:
                    self.dockwidget.backend_indicator_label.setText("!")
                    self.dockwidget.backend_indicator_label.setStyleSheet("""
                        QLabel#label_backend_indicator {
                            color: #e74c3c;
                            font-size: 9pt;
                            font-weight: 600;
                            padding: 3px 10px;
                            border-radius: 12px;
                            border: none;
                            background-color: #fadbd8;
                        }
                    """)
                    self.dockwidget.backend_indicator_label.setToolTip("Layer loading failed - click to retry")
                return
        
        # Reset retry counter on success
        self._reload_retry_count = 0
        
        # CRITICAL: Sync PROJECT_LAYERS to dockwidget
        self.dockwidget.get_project_layers_from_app(self.PROJECT_LAYERS, self.PROJECT)
        self.dockwidget.has_loaded_layers = True
        
        # Enable UI widgets
        if hasattr(self.dockwidget, 'set_widgets_enabled_state'):
            self.dockwidget.set_widgets_enabled_state(True)
        
        # FIX v2.8.10: Force QgsMapLayerComboBox to re-sync with project layers
        # The combobox uses QgsMapLayerProxyModel which should auto-sync, but sometimes
        # needs a nudge after major state changes. We re-apply the filter to trigger refresh.
        try:
            if hasattr(self.dockwidget, 'comboBox_filtering_current_layer'):
                # Re-apply filter to force model refresh
                self.dockwidget.comboBox_filtering_current_layer.setFilters(QgsMapLayerProxyModel.VectorLayer)
                logger.debug("Force refreshed QgsMapLayerComboBox filters after reload")
        except Exception as e:
            logger.debug(f"Error refreshing layer combobox after reload: {e}")
        
        # If there's an active layer, trigger current_layer_changed
        if self.iface.activeLayer() is not None:
            active_layer = self.iface.activeLayer()
            if isinstance(active_layer, QgsVectorLayer) and active_layer.id() in self.PROJECT_LAYERS:
                self.dockwidget.current_layer_changed(active_layer)
                logger.info(f"UI refreshed with active layer: {active_layer.name()}")
        else:
            # Select first layer if no active layer
            if self.PROJECT_LAYERS:
                first_layer_id = list(self.PROJECT_LAYERS.keys())[0]
                first_layer = self.PROJECT.mapLayer(first_layer_id)
                if first_layer:
                    self.dockwidget.current_layer_changed(first_layer)
                    logger.info(f"UI refreshed with first layer: {first_layer.name()}")
        
        logger.info(f"UI refresh completed with {len(self.PROJECT_LAYERS)} layers")
        
        # Show success notification
        from qgis.utils import iface
        iface.messageBar().pushSuccess(
            "FilterMate",
            f"{len(self.PROJECT_LAYERS)} couche(s) chargée(s) avec succès"
        )
    
    def _refresh_ui_after_project_load(self):
        """
        Force complete UI refresh after project load.
        
        Called when a new project is loaded while the plugin was already active.
        Ensures all widgets, comboboxes, and signals are properly updated with new project layers.
        Also validates PostgreSQL layers for orphaned materialized view references.
        """
        if self.dockwidget is None or not self.dockwidget.widgets_initialized:
            logger.debug("Cannot refresh UI: dockwidget not initialized")
            return
        
        # CRITICAL: Verify PROJECT_LAYERS has layers before attempting refresh
        if len(self.PROJECT_LAYERS) == 0:
            logger.warning("Cannot refresh UI: PROJECT_LAYERS is still empty - layer tasks not yet completed")
            return
            
        logger.info(f"Forcing complete UI refresh after project load with {len(self.PROJECT_LAYERS)} layers")
        
        # v2.8.1: Validate PostgreSQL layers for orphaned MV references
        # This fixes "relation does not exist" errors when QGIS is restarted
        # and materialized views created by FilterMate no longer exist
        self._validate_postgres_layers_on_project_load()
        
        # CRITICAL: Reconnect dockwidget signals that depend on PROJECT
        # The PROJECT reference has changed and signals need to be refreshed
        try:
            # Disconnect old PROJECT signal
            try:
                # Find and disconnect old fileNameChanged signal
                self.PROJECT.fileNameChanged.disconnect()
            except (TypeError, RuntimeError):
                pass  # Signal may not be connected yet
            
            # Reconnect with new PROJECT
            self.PROJECT.fileNameChanged.connect(lambda: self.save_project_variables())
            logger.info("Dockwidget signals reconnected to new PROJECT")
        except Exception as e:
            logger.warning(f"Error reconnecting dockwidget signals: {e}")
        
        # Ensure PROJECT_LAYERS is up to date
        self.dockwidget.get_project_layers_from_app(self.PROJECT_LAYERS, self.PROJECT)
        
        # If there's an active layer, trigger current_layer_changed to refresh everything
        if self.iface.activeLayer() is not None:
            active_layer = self.iface.activeLayer()
            if isinstance(active_layer, QgsVectorLayer) and active_layer.id() in self.PROJECT_LAYERS:
                self.dockwidget.current_layer_changed(active_layer)
                logger.info(f"UI refreshed with active layer: {active_layer.name()}")
        else:
            logger.info("No active layer after project load, UI refreshed without layer selection")
    
    def _validate_postgres_layers_on_project_load(self):
        """
        Validate PostgreSQL layers for orphaned materialized view references.
        
        v2.8.1: When QGIS/FilterMate is closed and reopened, materialized views
        created for filtering are no longer present in the database. However, 
        the layer's subset string may still reference them, causing 
        "relation does not exist" errors.
        
        This method detects such orphaned references and clears them,
        restoring the layer to its unfiltered state.
        """
        try:
            # Get all PostgreSQL layers from the project
            postgres_layers = []
            for layer in self.PROJECT.mapLayers().values():
                if isinstance(layer, QgsVectorLayer) and layer.providerType() == 'postgres':
                    postgres_layers.append(layer)
            
            if not postgres_layers:
                logger.debug("No PostgreSQL layers to validate for orphaned MVs")
                return
            
            logger.debug(f"Validating {len(postgres_layers)} PostgreSQL layer(s) for orphaned MV references")
            
            # Validate and cleanup orphaned MV references
            cleaned_layers = validate_and_cleanup_postgres_layers(postgres_layers)
            
            if cleaned_layers:
                # Show warning to user about cleared filters
                layer_list = ", ".join(cleaned_layers[:3])
                if len(cleaned_layers) > 3:
                    layer_list += f" (+{len(cleaned_layers) - 3} other(s))"
                
                iface.messageBar().pushWarning(
                    "FilterMate",
                    f"Cleared orphaned filter(s) from {len(cleaned_layers)} layer(s): {layer_list}. "
                    f"Previous filters referenced temporary views that no longer exist."
                )
                logger.warning(
                    f"Cleared orphaned MV references from {len(cleaned_layers)} PostgreSQL layer(s) on project load"
                )
            else:
                logger.debug("No orphaned MV references found in PostgreSQL layers")
                
        except Exception as e:
            # Non-critical - don't fail project load
            logger.debug(f"Error validating PostgreSQL layers for orphaned MVs: {e}")
            
    def update_datasource(self):
        """
        Update CONFIG_DATA with active datasource connections.
        
        v4.5 DELEGATION: Uses DatasourceManager.update_datasource()
        """
        # v4.5: Feature flag for DatasourceManager delegation
        USE_DATASOURCE_MANAGER = True  # Phase 4.6: ENABLED
        
        if USE_DATASOURCE_MANAGER and self._datasource_manager:
            try:
                # Sync project_datasources from DatasourceManager
                self.project_datasources = self._datasource_manager.get_project_datasources()
                # Delegate to DatasourceManager
                self._datasource_manager.update_datasource()
                return
            except Exception as e:
                logger.error(f"DatasourceManager.update_datasource failed: {e}. Falling back to legacy.")
        

    def create_foreign_data_wrapper(self, project_datasource, datasource, format):
        """
        Create PostgreSQL foreign data wrapper for external datasource.
        
        v4.5 DELEGATION: Uses DatasourceManager.create_foreign_data_wrapper()
        
        Args:
            project_datasource: Full path to datasource file
            datasource: Basename of datasource (for server naming)
            format: OGR format name (e.g., 'GPKG', 'ESRI Shapefile')
        """
        # v4.5: Feature flag for DatasourceManager delegation
        USE_DATASOURCE_MANAGER = True  # Phase 4.6: ENABLED
        
        if USE_DATASOURCE_MANAGER and self._datasource_manager:
            try:
                self._datasource_manager.create_foreign_data_wrapper(project_datasource, datasource, format)
                return
            except Exception as e:
                logger.error(f"DatasourceManager.create_foreign_data_wrapper failed: {e}. Falling back to legacy.")
        

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
    HEXAGONAL_AVAILABLE = True
except ImportError:
    HEXAGONAL_AVAILABLE = False
    TaskParameterBuilder = None  # v4.0: Fallback
    LayerLifecycleService = None  # v4.0: Fallback
    LayerLifecycleConfig = None  # v4.0: Fallback
    TaskManagementService = None  # v4.0: Fallback
    TaskManagementConfig = None  # v4.0: Fallback
    UndoRedoHandler = None  # v4.0: Fallback
    DatabaseManager = None  # v4.0: Fallback
    VariablesPersistenceManager = None  # v4.0: Fallback
    TaskOrchestrator = None  # v4.1: Fallback

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
        """
        service = self._get_layer_lifecycle_service()
        if service:
            return service.filter_usable_layers(layers, POSTGRESQL_AVAILABLE)
        
        # Service not available - return empty (should not happen in normal operation)
        logger.error("LayerLifecycleService not available - returning empty layer list")
        return []

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
        """
        Initialize FilterMate application controller.
        
        Sets up the main application state, task registry, and environment variables.
        Does not create UI - that happens in run() when plugin is activated.
        
        Args:
            plugin_dir (str): Absolute path to plugin directory
            
        Attributes:
            PROJECT_LAYERS (dict): Registry of all managed layers with metadata
            appTasks (dict): Active QgsTask instances for async operations
            tasks_descriptions (dict): Human-readable task names for UI
            project_datasources (dict): Data source connection information
            db_file_path (str): Path to Spatialite database for project
            
        Notes:
            - Initializes environment variables via init_env_vars()
            - Sets up QGIS project and layer store references
            - Prepares task manager for PostgreSQL/Spatialite operations
        """
        self.iface = iface
        
        self.dockwidget = None
        self.flags = {}


        self.plugin_dir = plugin_dir
        self.appTasks = {"filter":None,"unfilter":None,"reset":None,"export":None,"add_layers":None,"remove_layers":None,"remove_all_layers":None,"new_project":None,"project_read":None}
        self.tasks_descriptions = {
                                    'filter':'Filtering data',
                                    'unfilter':'Unfiltering data',
                                    'reset':'Reseting data',
                                    'export':'Exporting data',
                                    'undo':'Undo filter',
                                    'redo':'Redo filter',
                                    'add_layers':'Adding layers',
                                    'remove_layers':'Removing layers',
                                    'remove_all_layers':'Removing all layers',
                                    'new_project':'New project',
                                    'project_read':'Existing project loaded',
                                    'reload_layers':'Reloading layers'
                                    }
        
        # Initialize filter history manager for undo/redo functionality
        # Get max_history_size from configuration (default: 100)
        history_max_size = self._get_history_max_size_from_config()
        self.history_manager = HistoryManager(max_size=history_max_size)
        logger.info(f"FilterMate: HistoryManager initialized for undo/redo functionality (max_size={history_max_size})")
        
        # v4.0: Initialize UndoRedoHandler (extracted from FilterMateApp)
        if HEXAGONAL_AVAILABLE and UndoRedoHandler:
            self._undo_redo_handler = UndoRedoHandler(
                history_manager=self.history_manager,
                get_project_layers=lambda: self.PROJECT_LAYERS,
                get_project=lambda: self.PROJECT,
                get_iface=lambda: self.iface,
                refresh_layers_callback=self._refresh_layers_and_canvas,
                show_warning_callback=lambda t, m: iface.messageBar().pushWarning(t, m)
            )
            logger.info("FilterMate: UndoRedoHandler initialized (v4.0 migration)")
        else:
            self._undo_redo_handler = None
        
        # Initialize filter favorites manager for saving/loading favorites
        self.favorites_manager = FavoritesManager(max_favorites=50)
        self.favorites_manager.load_from_project()
        logger.info(f"FilterMate: FavoritesManager initialized ({self.favorites_manager.count} favorites loaded)")
        
        # v2.8.11: Initialize Spatialite cache for multi-step filtering
        try:
            from .infrastructure.cache import get_cache, cleanup_cache
            self._spatialite_cache = get_cache()
            # Cleanup expired entries on startup
            expired_count = cleanup_cache()
            if expired_count > 0:
                logger.info(f"FilterMate: Cleaned up {expired_count} expired cache entries")
            cache_stats = self._spatialite_cache.get_cache_stats()
            logger.info(f"FilterMate: Spatialite cache initialized ({cache_stats['total_entries']} entries, {cache_stats['db_size_mb']} MB)")
        except Exception as e:
            import traceback
            logger.debug(f"FilterMate: Spatialite cache not available: {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            self._spatialite_cache = None
        
        # Log PostgreSQL availability status
        if POSTGRESQL_AVAILABLE:
            logger.info("FilterMate: PostgreSQL support enabled (psycopg2 available)")
        else:
            logger.warning(
                "FilterMate: PostgreSQL support DISABLED - psycopg2 not installed. "
                "Plugin will work with local files (Shapefile, GeoPackage, Spatialite) only. "
                "For PostgreSQL layers, install psycopg2."
            )
        
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
        
        # Initialize feedback level from configuration
        self._init_feedback_level()
        self.PROJECT = ENV_VARS["PROJECT"]

        self.MapLayerStore = self.PROJECT.layerStore()
        self.db_name = 'filterMate_db.sqlite'
        self.db_file_path = os.path.normpath(ENV_VARS["PLUGIN_CONFIG_DIRECTORY"] + os.sep + self.db_name)
        self.project_file_name = os.path.basename(self.PROJECT.absoluteFilePath())
        self.project_file_path = self.PROJECT.absolutePath()
        self.project_uuid = ''
        
        # v4.0: Initialize DatabaseManager (extracted from FilterMateApp)
        if HEXAGONAL_AVAILABLE and DatabaseManager:
            self._database_manager = DatabaseManager(
                config_directory=ENV_VARS["PLUGIN_CONFIG_DIRECTORY"],
                project=self.PROJECT
            )
            logger.info("FilterMate: DatabaseManager initialized (v4.0 migration)")
        else:
            self._database_manager = None
        
        # v4.0: Initialize VariablesPersistenceManager (extracted from FilterMateApp)
        if HEXAGONAL_AVAILABLE and VariablesPersistenceManager:
            self._variables_manager = VariablesPersistenceManager(
                get_spatialite_connection=self.get_spatialite_connection,
                get_project_uuid=lambda: str(self.project_uuid),
                get_project_layers=lambda: self.PROJECT_LAYERS,
                return_typped_value=return_typed_value,  # Use module function directly
                cancel_layer_tasks=lambda layer_id: self._cancel_layer_tasks(layer_id) if hasattr(self, 'dockwidget') and self.dockwidget else None,
                is_layer_change_in_progress=lambda: hasattr(self, 'dockwidget') and self.dockwidget and getattr(self.dockwidget, '_updating_current_layer', False)
            )
            logger.info("FilterMate: VariablesPersistenceManager initialized (v4.0 migration)")
        else:
            self._variables_manager = None

        self.project_datasources = {}
        self.app_postgresql_temp_schema = 'filter_mate_temp'  # PostgreSQL temp schema name
        self.app_postgresql_temp_schema_setted = False
        
        # Session ID for multi-client materialized view isolation
        # Format: short hex string (8 chars) unique per QGIS session
        import time
        import hashlib
        session_seed = f"{time.time()}_{os.getpid()}_{id(self)}"
        self.session_id = hashlib.md5(session_seed.encode()).hexdigest()[:8]
        self._signals_connected = False
        self._dockwidget_signals_connected = False  # Flag for dockwidget signal connections
        self._loading_new_project = False  # Flag to track when loading a new project
        self._loading_new_project_timestamp = 0  # Timestamp when flag was set
        self._initializing_project = False  # Flag to prevent recursive project initialization
        self._initializing_project_timestamp = 0  # Timestamp when flag was set
        self._pending_add_layers_tasks = 0  # Counter for concurrent add_layers tasks prevention
        self._add_layers_queue = []  # Queue for deferred add_layers operations
        self._processing_queue = False  # Flag to prevent concurrent queue processing
        self._widgets_ready = False  # Flag to track when widgets are fully initialized and ready
        self._last_layer_change_timestamp = 0  # Debounce for layer change signals
        
        # Initialize PROJECT_LAYERS as instance attribute (shadows class attribute for isolation)
        self.PROJECT_LAYERS = {}
        
        # v4.1: Initialize TaskOrchestrator (extracted from FilterMateApp.manage_task)
        if HEXAGONAL_AVAILABLE and TaskOrchestrator:
            self._task_orchestrator = TaskOrchestrator(
                get_dockwidget=lambda: self.dockwidget,
                get_project_layers=lambda: self.PROJECT_LAYERS,
                get_config_data=lambda: self.CONFIG_DATA,
                get_project=lambda: self.PROJECT,
                check_reset_stale_flags=self._check_and_reset_stale_flags,
                set_loading_flag=self._set_loading_flag,
                set_initializing_flag=self._set_initializing_flag,
                get_task_parameters=self.get_task_parameters,
                handle_filter_task=self._execute_filter_task,
                handle_layer_task=self._execute_layer_task,
                handle_undo=self.handle_undo,
                handle_redo=self.handle_redo,
                force_reload_layers=self.force_reload_layers,
                handle_remove_all_layers=self._handle_remove_all_layers,
                handle_project_initialization=self._handle_project_initialization,
            )
            logger.info("FilterMate: TaskOrchestrator initialized (v4.1 migration)")
        else:
            self._task_orchestrator = None
        
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
        
        Creates the dockwidget if it doesn't exist, initializes the database,
        connects signals for layer management, and displays the UI.
        Also processes any existing layers in the project on first run.
        
        DIAGNOSTIC LOGGING ENABLED: Logging startup phases to identify freeze point.
        
        This method can be called multiple times:
        - First call: creates dockwidget and initializes everything
        - Subsequent calls: shows existing dockwidget and refreshes layers if needed
        """
        if self.dockwidget is None:

            
        
            global ENV_VARS

            self.CONFIG_DATA = ENV_VARS["CONFIG_DATA"]
            self.PROJECT = ENV_VARS["PROJECT"]

            QgsExpressionContextUtils.setProjectVariable(self.PROJECT, 'filterMate_db_project_uuid', '')
            
            # CRITICAL FIX v2.3.13: Clean up any corrupted filters saved in project
            # This prevents SQL errors from filters containing __source without EXISTS wrapper
            # or with unbalanced parentheses that were incorrectly persisted
            cleared_layers = cleanup_corrupted_layer_filters(self.PROJECT)
            if cleared_layers:
                show_warning(
                    self.tr(f"Cleared corrupted filters from {len(cleared_layers)} layer(s). Please re-apply your filters.")
                )

            init_layers = self._filter_usable_layers(list(self.PROJECT.mapLayers().values()))
            logger.info(f"FilterMate App.run(): Found {len(init_layers)} layers in project")

            logger.info("FilterMate App.run(): Starting init_filterMate_db()")
            self.init_filterMate_db()
            logger.info("FilterMate App.run(): init_filterMate_db() complete")
            
            # HEALTH CHECK: Verify database is accessible
            try:
                db_conn = self.get_spatialite_connection()
                if db_conn is None:
                    logger.error("Database health check failed: Cannot connect to Spatialite database")
                    iface.messageBar().pushCritical(
                        "FilterMate - Erreur base de données",
                        "Impossible d'accéder à la base de données FilterMate. Vérifiez les permissions du répertoire du projet."
                    )
                    return
                else:
                    logger.info("Database health check: OK")
                    db_conn.close()
            except Exception as db_err:
                logger.error(f"Database health check failed with exception: {db_err}", exc_info=True)
                iface.messageBar().pushCritical(
                    "FilterMate - Erreur base de données",
                    f"Erreur lors de la vérification de la base de données: {str(db_err)}"
                )
                return
            
            # Initialize UI profile based on screen resolution
            try:
                screen = QApplication.primaryScreen()
                if screen:
                    screen_geometry = screen.geometry()
                    screen_width = screen_geometry.width()
                    screen_height = screen_geometry.height()
                    
                    # Use compact mode for resolutions < 1920x1080
                    if screen_width < 1920 or screen_height < 1080:
                        UIConfig.set_profile(DisplayProfile.COMPACT)
                        logger.info(f"FilterMate: Using COMPACT profile for resolution {screen_width}x{screen_height}")
                    else:
                        UIConfig.set_profile(DisplayProfile.NORMAL)
                        logger.info(f"FilterMate: Using NORMAL profile for resolution {screen_width}x{screen_height}")
                else:
                    # Fallback to normal if screen detection fails
                    UIConfig.set_profile(DisplayProfile.NORMAL)
                    logger.warning("FilterMate: Could not detect screen, using NORMAL profile")
            except Exception as e:
                logger.error(f"FilterMate: Error detecting screen resolution: {e}")
                UIConfig.set_profile(DisplayProfile.NORMAL)
            
            logger.info("FilterMate App.run(): Creating FilterMateDockWidget")
            self.dockwidget = FilterMateDockWidget(self.PROJECT_LAYERS, self.plugin_dir, self.CONFIG_DATA, self.PROJECT)
            logger.info("FilterMate App.run(): FilterMateDockWidget created")
            
            # Store reference to app in dockwidget for session management
            self.dockwidget._app_ref = self
            
            # Pass favorites manager to dockwidget for indicator updates
            self.dockwidget._favorites_manager = self.favorites_manager
            self.dockwidget._update_favorite_indicator()
            logger.debug("FavoritesManager attached to DockWidget")
            
            # Connect to widgetsInitialized signal for synchronization
            self.dockwidget.widgetsInitialized.connect(self._on_widgets_initialized)
            logger.debug("widgetsInitialized signal connected to _on_widgets_initialized")
            
            # v4.1: Also connect to TaskOrchestrator if available
            if self._task_orchestrator is not None:
                self.dockwidget.widgetsInitialized.connect(self._task_orchestrator.on_widgets_initialized)
                logger.debug("widgetsInitialized signal connected to TaskOrchestrator")
            
            # CRITICAL FIX: Signal may have been emitted BEFORE connection (in dockwidget __init__)
            # Check if widgets are already initialized and manually sync if needed
            if hasattr(self.dockwidget, 'widgets_initialized') and self.dockwidget.widgets_initialized:
                logger.info("Widgets already initialized before signal connection - syncing state")
                # Call the handler directly since signal was already emitted
                self._on_widgets_initialized()
                # v4.1: Also sync TaskOrchestrator
                if self._task_orchestrator is not None:
                    self._task_orchestrator.on_widgets_initialized()

            # Force retranslation to ensure tooltips/text use current translator
            try:
                if hasattr(self.dockwidget, 'retranslateUi'):
                    self.dockwidget.retranslateUi(self.dockwidget)
                    logger.info("FilterMate: DockWidget UI retranslated with active locale")
                if hasattr(self.dockwidget, 'retranslate_dynamic_tooltips'):
                    self.dockwidget.retranslate_dynamic_tooltips()
                    logger.info("FilterMate: Dynamic tooltips refreshed with active locale")
            except Exception as e:
                logger.warning(f"FilterMate: Failed to retranslate DockWidget UI: {e}")

            # Get dock position from configuration
            dock_position = self._get_dock_position()
            self.iface.addDockWidget(dock_position, self.dockwidget)
            self.dockwidget.show()
            logger.info(f"FilterMate App.run(): DockWidget shown at position {dock_position}")
            
            # Process existing layers AFTER dockwidget is shown and fully initialized
            # Use QTimer to ensure widgets_initialized is True and event loop has processed show()
            if init_layers is not None and len(init_layers) > 0:
                # STABILITY FIX: Increased delay to 600ms to ensure complete initialization
                # Wait for widgets_initialized callback before processing layers
                # Use explicit lambda capture to prevent variable mutation issues
                def wait_for_widget_initialization(layers_to_add):
                    """Wait for widgets to be fully initialized before adding layers."""
                    max_retries = 10  # Max 3 seconds (10 * 300ms)
                    retry_count = 0
                    
                    def check_and_add():
                        nonlocal retry_count
                        if self.dockwidget and self.dockwidget.widgets_initialized:
                            logger.info(f"Widgets initialized, adding {len(layers_to_add)} layers")
                            self.manage_task('add_layers', layers_to_add)
                        elif retry_count < max_retries:
                            retry_count += 1
                            logger.debug(f"Waiting for widget initialization (attempt {retry_count}/{max_retries})")
                            QTimer.singleShot(300, check_and_add)
                        else:
                            logger.warning("Widget initialization timeout, forcing add_layers anyway")
                            self.manage_task('add_layers', layers_to_add)
                    
                    check_and_add()
                
                # Use weakref to prevent access violations
                weak_self = weakref.ref(self)
                def safe_wait_init():
                    strong_self = weak_self()
                    if strong_self is not None:
                        wait_for_widget_initialization(init_layers)
                QTimer.singleShot(600, safe_wait_init)
                
                # SAFETY: Force UI update after 5 seconds if task hasn't completed
                # This ensures UI is never left in disabled/grey state on startup
                # TIMEOUT INCREASED: 3s -> 5s to allow more time for large projects
                def ensure_ui_enabled():
                    # CRITICAL: Check if self still exists (plugin not unloaded)
                    try:
                        if not hasattr(self, 'dockwidget'):
                            logger.warning("Safety timer: self.dockwidget attribute missing, plugin may be unloaded")
                            return
                    except RuntimeError:
                        logger.warning("Safety timer: self object destroyed, plugin unloaded")
                        return
                    
                    if not self.dockwidget:
                        logger.warning("Safety timer: Dockwidget is None, cannot check UI state")
                        return
                    
                    # Check if layers were successfully loaded
                    if len(self.PROJECT_LAYERS) > 0:
                        logger.info(f"Safety timer: Task completed successfully with {len(self.PROJECT_LAYERS)} layers, forcing UI refresh")
                        self.dockwidget.get_project_layers_from_app(self.PROJECT_LAYERS, self.PROJECT)
                    else:
                        # Task may have failed or not completed - try to reload layers
                        all_layers = list(self.PROJECT.mapLayers().values())
                        logger.warning(f"Safety timer: PROJECT_LAYERS still empty after 5s, attempting recovery (total layers in project: {len(all_layers)})")
                        
                        # FIX v2.8.14: Be VERY permissive during recovery - include ALL valid vector layers
                        # This is critical for layers loaded by external scripts (like qgis_snap_zones.py)
                        # where the timing of layer addition may not align with FilterMate's initialization
                        
                        # First, try normal filtering
                        current_layers = self._filter_usable_layers(all_layers)
                        
                        # FIX v2.8.6 + v2.8.14: Enhanced recovery for PostgreSQL AND other providers
                        # Include ALL valid QgsVectorLayer instances that were missed
                        all_valid_vector_layers = [
                            l for l in all_layers 
                            if isinstance(l, QgsVectorLayer) 
                            and l.isValid()
                            and not is_sip_deleted(l)
                        ]
                        missed_layers = [l for l in all_valid_vector_layers if l not in current_layers]
                        
                        if missed_layers:
                            logger.warning(f"Recovery: Found {len(missed_layers)} valid vector layers that were filtered - forcing inclusion")
                            for layer in missed_layers:
                                provider = layer.providerType()
                                logger.info(f"  Force-adding missed layer: {layer.name()} (provider={provider}, id={layer.id()})")
                            current_layers.extend(missed_layers)
                        
                        # Detailed diagnostic
                        postgres_count = sum(1 for l in all_layers if isinstance(l, QgsVectorLayer) and l.providerType() == 'postgres')
                        spatialite_count = sum(1 for l in all_layers if isinstance(l, QgsVectorLayer) and l.providerType() == 'spatialite')
                        ogr_count = sum(1 for l in all_layers if isinstance(l, QgsVectorLayer) and l.providerType() == 'ogr')
                        logger.info(f"Recovery diagnostic: total_layers={len(all_layers)}, usable_layers={len(current_layers)}, missed={len(missed_layers)}")
                        logger.info(f"  Provider breakdown: postgres={postgres_count}, spatialite={spatialite_count}, ogr={ogr_count}")
                        logger.info(f"  Pending tasks: {self._pending_add_layers_tasks}")
                        
                        if len(current_layers) > 0:
                            logger.info(f"Recovery: Found {len(current_layers)} usable layers, retrying add_layers")
                            # Use QTimer to defer to avoid recursion issues - use weakref for safety
                            weak_self = weakref.ref(self)
                            def safe_retry_add():
                                strong_self = weak_self()
                                if strong_self is not None:
                                    strong_self.manage_task('add_layers', current_layers)
                            QTimer.singleShot(100, safe_retry_add)
                            # Set another safety timer (TIMEOUT: increased 3s -> 5s for large projects)
                            QTimer.singleShot(5000, ensure_ui_enabled_final)
                        else:
                            # No layers found - update indicator to show waiting state
                            logger.warning(f"Recovery: No usable layers found from {len(all_layers)} total layers, plugin waiting for layers")
                            logger.debug(f"Layer types in project: {[type(l).__name__ for l in all_layers][:5]}...")  # Show first 5
                            if self.dockwidget and hasattr(self.dockwidget, 'backend_indicator_label') and self.dockwidget.backend_indicator_label:
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
                                # Show info message that plugin is loading
                                try:
                                    iface.messageBar().pushInfo(
                                        "FilterMate",
                                        "Chargement des couches en cours... Veuillez patienter."
                                    )
                                except RuntimeError:
                                    logger.warning("Cannot show message: iface may be destroyed")
                
                def ensure_ui_enabled_final(retry_count=0):
                    """Final safety check after recovery attempt.
                    
                    Args:
                        retry_count: Number of retries already attempted (max 5 = 15s additional wait)
                    """
                    MAX_RETRIES = 5  # Maximum 5 retries of 3s each = 15s additional wait
                    
                    # CRITICAL: Check if self still exists
                    try:
                        if not hasattr(self, 'dockwidget'):
                            logger.warning("Final safety timer: plugin may be unloaded")
                            return
                    except RuntimeError:
                        logger.warning("Final safety timer: self object destroyed")
                        return
                    
                    if not self.dockwidget:
                        return
                    if len(self.PROJECT_LAYERS) > 0:
                        logger.info("Final safety timer: Layers loaded, refreshing UI")
                        self.dockwidget.get_project_layers_from_app(self.PROJECT_LAYERS, self.PROJECT)
                    else:
                        # Check if tasks are still running - if so, don't show error yet
                        if self._pending_add_layers_tasks > 0 and retry_count < MAX_RETRIES:
                            logger.info(f"Final safety timer: {self._pending_add_layers_tasks} task(s) still running, deferring check (retry {retry_count + 1}/{MAX_RETRIES})")
                            # Reschedule check for later with incremented retry count
                            QTimer.singleShot(3000, lambda: ensure_ui_enabled_final(retry_count + 1))
                            return
                        
                        logger.error("Final safety timer: Failed to load layers after recovery attempt")
                        
                        # DIAGNOSTIC: Gather detailed information about the failure
                        current_layers = self._filter_usable_layers(list(self.PROJECT.mapLayers().values()))
                        all_layers = list(self.PROJECT.mapLayers().values())
                        
                        diagnostic_msg = (
                            f"Échec du chargement des couches.\n\n"
                            f"Diagnostic:\n"
                            f"- Couches totales dans le projet: {len(all_layers)}\n"
                            f"- Couches utilisables détectées: {len(current_layers)}\n"
                            f"- Tâches en attente (add_layers): {self._pending_add_layers_tasks}\n\n"
                            f"Solution: Utilisez F5 pour forcer le rechargement des couches."
                        )
                        
                        logger.error(f"Layer loading failure diagnostic: total={len(all_layers)}, usable={len(current_layers)}, pending_tasks={self._pending_add_layers_tasks}")
                        
                        # Check for database issues
                        try:
                            conn = self.get_spatialite_connection()
                            if conn is None:
                                diagnostic_msg += "\n\n⚠️ La base de données FilterMate n'est pas accessible."
                                logger.error("Database connection failed in final safety check")
                            else:
                                conn.close()
                        except Exception as db_err:
                            diagnostic_msg += f"\n\n⚠️ Erreur base de données: {str(db_err)}"
                            logger.error(f"Database error in final safety check: {db_err}")
                        
                        self.iface.messageBar().pushWarning(
                            "FilterMate",
                            diagnostic_msg
                        )
                
                # TIMEOUT INCREASED: 3s -> 5s to allow more time for loading large projects
                # Use weakref to prevent access violations on plugin unload
                weak_self = weakref.ref(self)
                def safe_ensure_ui():
                    strong_self = weak_self()
                    if strong_self is not None:
                        ensure_ui_enabled()
                QTimer.singleShot(5000, safe_ensure_ui)
            else:
                # No layers in project - inform user that plugin is waiting for layers
                logger.info("FilterMate: Plugin started with empty project - waiting for layers to be added")
                show_info(
                    "Projet vide détecté. Ajoutez des couches vectorielles pour activer le plugin."
                )
        else:
            # Dockwidget already exists - show it and refresh layers if needed
            logger.info("FilterMate: Dockwidget already exists, showing and refreshing layers")
            
            # Update project reference
            init_env_vars()
            self.PROJECT = ENV_VARS["PROJECT"]
            self.MapLayerStore = self.PROJECT.layerStore()

            try:
                if hasattr(self.dockwidget, 'retranslateUi'):
                    self.dockwidget.retranslateUi(self.dockwidget)
                if hasattr(self.dockwidget, 'retranslate_dynamic_tooltips'):
                    self.dockwidget.retranslate_dynamic_tooltips()
            except Exception as e:
                logger.debug(f"FilterMate: Retranslation skipped for existing dockwidget: {e}")
            
            # Make sure the dockwidget is visible
            if not self.dockwidget.isVisible():
                self.dockwidget.show()
            
            # Check if there are new layers in the project that need to be loaded
            current_project_layers = list(self.PROJECT.mapLayers().values())
            if current_project_layers:
                # Filter to get only layers not already in PROJECT_LAYERS
                new_layers = [layer for layer in current_project_layers 
                             if layer.id() not in self.PROJECT_LAYERS]
                
                if new_layers:
                    logger.info(f"FilterMate: Found {len(new_layers)} new layers to add")
                    # STABILITY FIX: Use explicit lambda capture to prevent variable mutation issues
                    # Use weakref to prevent access violations
                    usable = self._filter_usable_layers(new_layers)
                    weak_self = weakref.ref(self)
                    def safe_add_new_layers():
                        strong_self = weak_self()
                        if strong_self is not None:
                            # v2.9.19: CRASH FIX - Re-filter to remove layers deleted during the delay
                            still_valid = [l for l in usable if l is not None and not sip.isdeleted(l)]
                            if still_valid:
                                strong_self.manage_task('add_layers', still_valid)
                    QTimer.singleShot(300, safe_add_new_layers)
                else:
                    # No new layers, but update UI if it's empty
                    if len(self.PROJECT_LAYERS) == 0 and len(current_project_layers) > 0:
                        logger.info("FilterMate: PROJECT_LAYERS is empty but project has layers, refreshing")
                        # STABILITY FIX: Use weakref to prevent access violations
                        usable_layers = self._filter_usable_layers(current_project_layers)
                        weak_self = weakref.ref(self)
                        def safe_add_layers_refresh():
                            strong_self = weak_self()
                            if strong_self is not None:
                                # v2.9.19: CRASH FIX - Re-filter to remove layers deleted during the delay
                                still_valid = [l for l in usable_layers if l is not None and not sip.isdeleted(l)]
                                if still_valid:
                                    strong_self.manage_task('add_layers', still_valid)
                        QTimer.singleShot(300, safe_add_layers_refresh)


        """Keep the advanced filter combobox updated on adding or removing layers"""
        # Use QTimer.singleShot to defer project signal handling until QGIS is in stable state
        # This prevents access violations during project transitions
        # Only connect signals once to avoid multiple connections on plugin reload
        if not self._signals_connected:
            logger.debug("Connecting layer store signals (layersAdded, layersWillBeRemoved...)")
            # NOTE: projectRead and newProjectCreated signals are handled by filter_mate.py
            # via _auto_activate_plugin() which calls run(). We don't connect them here
            # to avoid double processing which causes freezes during project load.
            
            # Use layersAdded (batch) instead of layerWasAdded (per layer) to avoid duplicate calls
            self.MapLayerStore.layersAdded.connect(self._on_layers_added)
            self.MapLayerStore.layersWillBeRemoved.connect(lambda layers: self.manage_task('remove_layers', layers))
            self.MapLayerStore.allLayersRemoved.connect(lambda: self.manage_task('remove_all_layers'))
            self._signals_connected = True
            logger.debug("Layer store signals connected successfully")
        
        # Only connect dockwidget signals once to avoid multiple connections
        if not self._dockwidget_signals_connected:
            self.dockwidget.launchingTask.connect(lambda x: self.manage_task(x))
            self.dockwidget.currentLayerChanged.connect(self.update_undo_redo_buttons)

            self.dockwidget.resettingLayerVariableOnError.connect(lambda layer, properties: self._safe_layer_operation(layer, properties, self.remove_variables_from_layer))
            self.dockwidget.settingLayerVariable.connect(lambda layer, properties: self._safe_layer_operation(layer, properties, self.save_variables_from_layer))
            self.dockwidget.resettingLayerVariable.connect(lambda layer, properties: self._safe_layer_operation(layer, properties, self.remove_variables_from_layer))

            self.dockwidget.settingProjectVariables.connect(self.save_project_variables)
            self.PROJECT.fileNameChanged.connect(lambda: self.save_project_variables())
            self._dockwidget_signals_connected = True
        

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
        
        Returns:
            Connection object or None if connection fails
        """
        if not os.path.exists(self.db_file_path):
            error_msg = f"Database file does not exist: {self.db_file_path}"
            logger.error(error_msg)
            show_error(error_msg)
            return None
            
        try:
            conn = spatialite_connect(self.db_file_path)
            return conn
        except Exception as error:
            error_msg = f"Failed to connect to database {self.db_file_path}: {error}"
            logger.error(error_msg)
            show_error(error_msg)
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
        USE_TASK_ORCHESTRATOR = False  # TODO: Enable after testing
        
        if USE_TASK_ORCHESTRATOR and self._task_orchestrator is not None:
            logger.info(f"v4.1: Delegating task '{task_name}' to TaskOrchestrator")
            try:
                self._task_orchestrator.dispatch_task(task_name, data)
                return
            except Exception as e:
                logger.warning(f"v4.1: TaskOrchestrator failed, falling back to legacy: {e}")
                # Fall through to legacy code
        
        # v2.7.17: Enhanced logging for task reception
        logger.info(f"=" * 60)
        logger.info(f"manage_task: RECEIVED task_name='{task_name}'")
        # v2.9.19: CRASH FIX - Check if current_layer is deleted before accessing it
        if self.dockwidget and hasattr(self.dockwidget, 'current_layer'):
            try:
                current_layer = self.dockwidget.current_layer
                if current_layer and not sip.isdeleted(current_layer):
                    logger.info(f"  current_layer: {current_layer.name()}")
                    logger.info(f"  current_exploring_groupbox: {getattr(self.dockwidget, 'current_exploring_groupbox', 'unknown')}")
            except RuntimeError:
                # Layer was deleted between check and access
                logger.debug("  current_layer: <deleted>")
        logger.info(f"=" * 60)
        
        # STABILITY FIX: Check and reset stale flags before processing
        self._check_and_reset_stale_flags()
        
        # CRITICAL: Skip layersAdded signals during project initialization
        # These will be handled by _handle_project_initialization which calls add_layers explicitly
        # Only check _initializing_project - _loading_new_project is used for the deferred call itself
        if task_name == 'add_layers' and self._initializing_project:
            logger.debug(f"Skipping add_layers - project initialization in progress (will be handled by _handle_project_initialization)")
            return
        
        # STABILITY FIX: Queue concurrent add_layers tasks instead of rejecting them
        # Multiple signals (projectRead, layersAdded, timers) can trigger add_layers simultaneously
        # STABILITY FIX: Limit queue size to prevent memory issues
        max_queue_size = STABILITY_CONSTANTS['MAX_ADD_LAYERS_QUEUE']
        if task_name == 'add_layers':
            if self._pending_add_layers_tasks > 0:
                if len(self._add_layers_queue) >= max_queue_size:
                    logger.warning(f"⚠️ STABILITY: add_layers queue full ({max_queue_size}), dropping oldest entry")
                    self._add_layers_queue.pop(0)  # Remove oldest entry
                logger.info(f"Queueing add_layers - already {self._pending_add_layers_tasks} task(s) in progress (queue size: {len(self._add_layers_queue)})")
                self._add_layers_queue.append(data)
                return
            self._pending_add_layers_tasks += 1
            logger.debug(f"Starting add_layers task (pending count: {self._pending_add_layers_tasks}, queue size: {len(self._add_layers_queue)})")
        
        # Guard: Ensure dockwidget is fully initialized before processing tasks
        # Exception: remove_all_layers, project_read, new_project, add_layers can run without full initialization
        # add_layers is allowed to run early to handle existing layers at startup
        if task_name not in ('remove_all_layers', 'project_read', 'new_project', 'add_layers'):
            if self.dockwidget is None or not hasattr(self.dockwidget, 'widgets_initialized') or not self.dockwidget.widgets_initialized:
                logger.warning(f"Task '{task_name}' called before dockwidget initialization, deferring by 500ms...")
                # STABILITY FIX: Use weakref to prevent access violations
                weak_self = weakref.ref(self)
                captured_task_name = task_name
                captured_data = data
                def safe_deferred_task():
                    strong_self = weak_self()
                    if strong_self is not None:
                        strong_self.manage_task(captured_task_name, captured_data)
                QTimer.singleShot(500, safe_deferred_task)
                return
        
        # CRITICAL: For filtering tasks, ensure widgets are fully initialized AND connected
        if task_name in ('filter', 'unfilter', 'reset'):
            # Track retry count to prevent infinite loop
            if not hasattr(self, '_filter_retry_count'):
                self._filter_retry_count = {}
            
            retry_key = f"{task_name}_{id(data)}"
            retry_count = self._filter_retry_count.get(retry_key, 0)
            
            if not self._is_dockwidget_ready_for_filtering():
                if retry_count >= 10:  # Max 10 retries = 5 seconds
                    logger.error(f"❌ GIVING UP: Task '{task_name}' still not ready after {retry_count} retries (5 seconds)")
                    iface.messageBar().pushCritical(
                        "FilterMate ERROR",
                        f"Cannot execute {task_name}: Widgets initialization failed. Try closing and reopening FilterMate."
                    )
                    # Reset counter
                    self._filter_retry_count[retry_key] = 0
                    
                    # EMERGENCY FALLBACK: Force sync if dockwidget.widgets_initialized is True
                    if hasattr(self.dockwidget, 'widgets_initialized') and self.dockwidget.widgets_initialized:
                        logger.warning("⚠️ EMERGENCY: Forcing _widgets_ready = True based on dockwidget.widgets_initialized")
                        show_warning("Emergency fallback: forcing widgets ready flag")
                        self._widgets_ready = True
                        # Retry immediately - use weakref for safety
                        weak_self = weakref.ref(self)
                        captured_tn = task_name
                        captured_d = data
                        def safe_emergency_retry():
                            strong_self = weak_self()
                            if strong_self is not None:
                                strong_self.manage_task(captured_tn, captured_d)
                        QTimer.singleShot(100, safe_emergency_retry)
                    return
                
                # Increment retry count
                self._filter_retry_count[retry_key] = retry_count + 1
                logger.warning(f"Task '{task_name}' called before dockwidget is ready for filtering, deferring by 500ms (attempt {retry_count + 1}/10)...")
                # STABILITY FIX: Use weakref to prevent access violations
                weak_self = weakref.ref(self)
                captured_tn = task_name
                captured_d = data
                def safe_filter_retry():
                    strong_self = weak_self()
                    if strong_self is not None:
                        strong_self.manage_task(captured_tn, captured_d)
                QTimer.singleShot(500, safe_filter_retry)
                return
            else:
                # Success! Reset counter for this task
                self._filter_retry_count[retry_key] = 0

        if self.dockwidget is not None:
            self.PROJECT_LAYERS = self.dockwidget.PROJECT_LAYERS
            self.CONFIG_DATA = self.dockwidget.CONFIG_DATA

        if task_name == 'remove_all_layers':
            self._handle_remove_all_layers()
            return
        
        if task_name in ('project_read', 'new_project'):
            self._handle_project_initialization(task_name)
            return
        
        # Handle undo/redo operations
        if task_name == 'undo':
            self.handle_undo()
            return
        
        if task_name == 'redo':
            self.handle_redo()
            return
        
        # Handle reload_layers - force complete reload of all layers
        if task_name == 'reload_layers':
            self.force_reload_layers()
            return

        # v3.0: MIG-025 - Try delegating to hexagonal controllers (Strangler Fig pattern)
        # If delegation succeeds, skip legacy code path
        if task_name in ('filter', 'unfilter', 'reset'):
            if self._try_delegate_to_controller(task_name, data):
                logger.info(f"v3.0: Task '{task_name}' delegated to controller successfully")
                return
            # Fallback to legacy code path if delegation fails
            logger.debug(f"v3.0: Task '{task_name}' using legacy code path")

        task_parameters = self.get_task_parameters(task_name, data)
        
        # Guard: task_parameters can be None if layer is not in PROJECT_LAYERS
        if task_parameters is None:
            logger.warning(f"FilterMate: Task '{task_name}' aborted - no valid task parameters")
            return

        if task_name in [name for name in self.tasks_descriptions.keys() if "layer" not in name]:

            if self.dockwidget is None or self.dockwidget.current_layer is None:
                return
            else:
                current_layer = self.dockwidget.current_layer 

            # v2.6.7: Cancel any pending async expression evaluation before starting filter task
            # This prevents race conditions where the expression task uses stale feature sources
            if hasattr(self.dockwidget, 'cancel_async_expression_evaluation'):
                try:
                    self.dockwidget.cancel_async_expression_evaluation()
                    logger.debug("Cancelled pending async expression evaluation before filter task")
                except Exception as e:
                    logger.debug(f"Could not cancel async expression evaluation: {e}")
            
            # v2.7.0: AUTO-OPTIMIZATION - Check for optimization recommendations before filtering
            # Only show confirmation if task is 'filter' and ask_before is enabled
            approved_optimizations = {}
            auto_apply_optimizations = False
            if task_name == 'filter':
                try:
                    approved_optimizations, auto_apply_optimizations = self._check_and_confirm_optimizations(
                        current_layer, task_parameters
                    )
                except Exception as e:
                    logger.warning(f"Optimization check failed: {e}")
            
            # Pass approved optimizations to task parameters
            if approved_optimizations:
                if "task" not in task_parameters:
                    task_parameters["task"] = {}
                task_parameters["task"]["approved_optimizations"] = approved_optimizations
                task_parameters["task"]["auto_apply_optimizations"] = auto_apply_optimizations
                logger.info(f"Passing approved optimizations to task: {approved_optimizations}")
                
                # v2.8.6: Apply enable_buffer_type optimization to task_parameters
                # When user accepts this optimization, update buffer params for the task
                for layer_id, opts in approved_optimizations.items():
                    if opts.get('enable_buffer_type', False):
                        if "filtering" not in task_parameters:
                            task_parameters["filtering"] = {}
                        task_parameters["filtering"]["has_buffer_type"] = True
                        task_parameters["filtering"]["buffer_type"] = "Flat"
                        task_parameters["filtering"]["buffer_segments"] = 1
                        logger.info("AUTO-OPTIMIZATION: Applied buffer_type=Flat, buffer_segments=1 to task_parameters")
                        break  # Only need to apply once
                
            layers = []
            self.appTasks[task_name] = FilterEngineTask(self.tasks_descriptions[task_name], task_name, task_parameters)
            layers_props = [layer_infos for layer_infos in task_parameters["task"]["layers"]]
            layers_ids = [layer_props["layer_id"] for layer_props in layers_props]
            for layer_props in layers_props:
                temp_layers = self.PROJECT.mapLayersByName(layer_props["layer_name"])
                for temp_layer in temp_layers:
                    if temp_layer.id() in layers_ids:
                        layers.append(temp_layer)
            
            # v2.9.19: CRITICAL - Save current_layer BEFORE filtering to restore it after
            # The combobox must NEVER change during filtering, regardless of what happens
            self._current_layer_before_filter = self.dockwidget.current_layer if self.dockwidget else None
            if self._current_layer_before_filter:
                try:
                    self._current_layer_id_before_filter = self._current_layer_before_filter.id()
                    logger.info(f"v3.0.13: 💾 Saved current_layer '{self._current_layer_before_filter.name()}' (ID: {self._current_layer_id_before_filter[:8]}...) before filtering")
                    # v3.0.13: Log to QGIS message panel for visibility
                    from qgis.core import QgsMessageLog, Qgis
                    QgsMessageLog.logMessage(
                        f"🔒 Filter protection ACTIVE - Layer '{self._current_layer_before_filter.name()}' will be preserved",
                        "FilterMate", Qgis.Info
                    )
                except (RuntimeError, AttributeError):
                    self._current_layer_id_before_filter = None
                    logger.warning("v2.9.19: ⚠️ Could not save current_layer ID (layer invalid)")
            else:
                self._current_layer_id_before_filter = None
                logger.warning("v2.9.19: ⚠️ No current_layer to save before filtering")
            
            # v3.0.18: CRITICAL FIX - Set _saved_layer_id_before_filter IMMEDIATELY at start of filtering
            # Previously, this was only set in filter_engine_task_completed's finally block.
            # BUT: canvas.refresh() and layer.reload() calls in FilterEngineTask.finished() can trigger
            # currentLayerChanged signals BEFORE filter_engine_task_completed runs.
            # This caused comboBox to lose its value for OGR (after first filter) and 
            # Spatialite (during multistep step2) because the protection in current_layer_changed
            # was checking _saved_layer_id_before_filter which wasn't set yet.
            if self.dockwidget and self._current_layer_id_before_filter:
                self.dockwidget._saved_layer_id_before_filter = self._current_layer_id_before_filter
                logger.info(f"v3.0.18: 💾 Set _saved_layer_id_before_filter at START of filtering")
            
            # v2.9.25: CRITICAL - Set filtering flag to prevent current_layer reset during filtering
            if self.dockwidget:
                self.dockwidget._filtering_in_progress = True
                logger.info("v2.9.25: 🔒 Filtering in progress flag SET")
            
            # v2.8.16: CRITICAL - Disconnect current_layer combobox during filtering
            # This prevents the combobox from automatically changing when layers are modified
            # The combobox will be restored to the correct layer after filtering completes
            if self.dockwidget:
                try:
                    self.dockwidget.manageSignal(["FILTERING", "CURRENT_LAYER"], 'disconnect')
                    logger.debug("v2.8.16: Disconnected current_layer combobox signal during filtering")
                except Exception as e:
                    logger.debug(f"Could not disconnect current_layer combobox: {e}")
                
                # v3.0.19: CRITICAL FIX - Also BLOCK Qt internal signals on combobox
                # Disconnecting our handler is NOT enough - Qt's internal signal handling
                # can still trigger combobox value changes when canvas.refresh() completes.
                # By blocking signals, we prevent Qt from internally resetting the combobox.
                try:
                    self.dockwidget.comboBox_filtering_current_layer.blockSignals(True)
                    logger.info("v3.0.19: 🔒 BLOCKED Qt signals on current_layer combobox during filtering")
                    from qgis.core import QgsMessageLog, Qgis
                    QgsMessageLog.logMessage(
                        "v3.0.19: 🔒 Combobox signals BLOCKED for entire filtering + 5s protection",
                        "FilterMate", Qgis.Info
                    )
                except Exception as e:
                    logger.error(f"v3.0.19: Failed to block combobox signals: {e}")
                
                # v2.9.27: CRITICAL - Also disconnect LAYER_TREE_VIEW signal during filtering
                # Canvas refresh in FilterEngineTask.finished() can trigger currentLayerChanged on the
                # layer tree view. Without disconnecting, this can call current_layer_changed() after
                # _filtering_in_progress is reset to False, causing current_layer to become None.
                try:
                    self.dockwidget.manageSignal(["QGIS", "LAYER_TREE_VIEW"], 'disconnect')
                    logger.debug("v2.9.27: Disconnected LAYER_TREE_VIEW signal during filtering")
                except Exception as e:
                    logger.debug(f"Could not disconnect LAYER_TREE_VIEW signal: {e}")
            
            # Show informational message with backend awareness
            layer_count = len(layers) + 1  # +1 for current layer
            source_provider_type = task_parameters["infos"].get("layer_provider_type", "unknown")
            
            # Determine the dominant backend for distant layers (what will actually be used)
            # The distant layers determine filtering backend, not the source layer
            distant_provider_types = []
            for layer_props in layers_props:
                layer_type = layer_props.get("layer_provider_type", "unknown")
                distant_provider_types.append(layer_type)
            
            # DEBUG: Log what we found
            logger.info(f"Backend detection: source={source_provider_type}, distant_types={distant_provider_types}")
            
            # Use the most common distant layer type for the message
            # Priority: spatialite > postgresql > ogr (since spatialite includes GPKG)
            if 'spatialite' in distant_provider_types:
                provider_type = 'spatialite'
            elif 'postgresql' in distant_provider_types:
                provider_type = 'postgresql'
            elif distant_provider_types:
                provider_type = distant_provider_types[0]
            else:
                provider_type = source_provider_type
            
            logger.info(f"Backend detection: selected provider_type={provider_type}")
            
            # v2.8.8: Check if backend is forced for all layers - override provider_type for UI message
            forced_backends = {}
            is_fallback = False  # Initialize here
            if self.dockwidget and hasattr(self.dockwidget, 'forced_backends'):
                forced_backends = self.dockwidget.forced_backends
            
            # Check if ALL layers have the same forced backend
            backend_was_forced = False
            if forced_backends:
                all_layer_ids = [current_layer.id()] + [layer.id() for layer in layers]
                forced_types = set(forced_backends.get(lid) for lid in all_layer_ids if lid in forced_backends)
                
                if len(forced_types) == 1 and None not in forced_types:
                    forced_type = list(forced_types)[0]
                    logger.info(f"Backend detection: ALL layers forced to {forced_type.upper()}")
                    provider_type = forced_type
                    is_fallback = (forced_type == 'ogr')
                    backend_was_forced = True
                elif forced_types:
                    # Mixed forced backends - use 'ogr' as indicator since it's the fallback
                    logger.info(f"Backend detection: Mixed forced backends: {forced_types}")
            
            # Check if PostgreSQL layer is using OGR fallback (no connection available)
            # CRITICAL FIX v2.5.14: Default to True for PostgreSQL layers - they're always
            # filterable via QGIS native API (setSubsetString). Only explicitly False means fallback.
            if not backend_was_forced:
                is_fallback = (
                    provider_type == 'postgresql' and 
                    task_parameters["infos"].get("postgresql_connection_available", True) is False
                )
            
            # Check if Spatialite functions are available for the distant layers
            # If not, OGR fallback will be used
            spatialite_fallback = False
            if provider_type == 'spatialite' and layers and not backend_was_forced:
                from .adapters.backends.spatialite import SpatialiteGeometricFilter
                spatialite_backend = SpatialiteGeometricFilter({})
                # Test first layer to see if Spatialite functions work
                test_layer = layers[0] if layers else current_layer
                if test_layer and not spatialite_backend.supports_layer(test_layer):
                    spatialite_fallback = True
                    is_fallback = True
                    provider_type = 'ogr'  # Update to show actual backend
                    logger.warning(f"Spatialite functions not available - using OGR fallback")
            
            if task_name == 'filter':
                show_backend_info(provider_type, layer_count, operation='filter', is_fallback=is_fallback)
            elif task_name == 'unfilter':
                show_backend_info(provider_type, layer_count, operation='unfilter', is_fallback=is_fallback)
            elif task_name == 'reset':
                show_backend_info(provider_type, layer_count, operation='reset', is_fallback=is_fallback)

            # v3.0.8: CRITICAL FIX - Do NOT set any dependent layers for filter tasks
            # PROBLEM: QGIS QgsTaskManager automatically cancels tasks when dependent layers are modified.
            # Even with only source_layer as dependent, when OGR fallback uses processing.run
            # ('native:selectbylocation'), the processing modifies layer selection state in the main thread.
            # If source and target layers are from the same GeoPackage file, modifications to ANY layer
            # in that file can trigger signals that make QGIS think the source changed.
            # This causes "Filter task was canceled by user" errors without user action.
            # SOLUTION: Don't set ANY dependent layers. The filter task manages its own data access
            # and doesn't need QGIS to cancel it when layers change.
            # self.appTasks[task_name].setDependentLayers([current_layer])  # DISABLED - causes auto-cancel
            self.appTasks[task_name].taskCompleted.connect(lambda task_name=task_name, current_layer=current_layer, task_parameters=task_parameters: self.filter_engine_task_completed(task_name, current_layer, task_parameters))
            
        else:
            self.appTasks[task_name] = LayersManagementEngineTask(self.tasks_descriptions[task_name], task_name, task_parameters)

            if task_name == "add_layers":
                self.appTasks[task_name].setDependentLayers([layer for layer in task_parameters["task"]["layers"]])
                # Only connect to dockwidget signal if dockwidget exists
                if self.dockwidget is not None:
                    self.appTasks[task_name].begun.connect(self.dockwidget.disconnect_widgets_signals)
            elif task_name == "remove_layers":
                self.appTasks[task_name].begun.connect(self.on_remove_layer_task_begun)

            # CRITICAL: Use Qt.QueuedConnection to defer signal handling and avoid accessing deleted C++ objects
            # The QgsTask object is destroyed by Qt immediately after finished() returns, so direct connections
            # could try to access the deleted object. Queued connections process after event loop returns,
            # by which time the signal has already been emitted and disconnected.
            self.appTasks[task_name].resultingLayers.connect(
                lambda result_project_layers, task_name=task_name: self.layer_management_engine_task_completed(result_project_layers, task_name),
                Qt.QueuedConnection
            )
            self.appTasks[task_name].savingLayerVariable.connect(
                lambda layer, variable_key, value_typped, type_returned: self.saving_layer_variable(layer, variable_key, value_typped, type_returned),
                Qt.QueuedConnection
            )
            self.appTasks[task_name].removingLayerVariable.connect(
                lambda layer, variable_key: self.removing_layer_variable(layer, variable_key),
                Qt.QueuedConnection
            )
            
            # CRITICAL FIX: Handle task termination (failure/cancellation)
            # This ensures the UI is not left in a disabled state if the task fails
            self.appTasks[task_name].taskTerminated.connect(
                lambda tn=task_name: self._handle_layer_task_terminated(tn),
                Qt.QueuedConnection
            )

        try:
            active_tasks = QgsApplication.taskManager().activeTasks()
            if len(active_tasks) > 0:
                for active_task in active_tasks:
                    key_active_task = [k for k, v in self.tasks_descriptions.items() if v == active_task.description()][0]
                    if key_active_task in ('filter','reset','unfilter'):
                        active_task.cancel()
        except (IndexError, KeyError, AttributeError) as e:
            # Ignore errors in task cancellation - task may have completed already
            pass
        QgsApplication.taskManager().addTask(self.appTasks[task_name])

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
        approved_optimizations = {}
        auto_apply = False
        
        # Check if optimization system is enabled
        optimization_enabled = getattr(self.dockwidget, '_optimization_enabled', True) if self.dockwidget else True
        if not optimization_enabled:
            logger.debug("Auto-optimization disabled by user setting")
            return approved_optimizations, auto_apply
        
        # Check if we should ask before applying
        ask_before = getattr(self.dockwidget, '_optimization_ask_before', True) if self.dockwidget else True
        centroid_auto = getattr(self.dockwidget, '_centroid_auto_enabled', True) if self.dockwidget else True
        
        if not centroid_auto:
            logger.debug("Auto-centroid disabled by user setting")
            return approved_optimizations, auto_apply
        
        # If not asking, return auto_apply = True (will be handled in task)
        if not ask_before:
            auto_apply = True
            logger.info("Auto-apply optimizations enabled (no confirmation dialog)")
            return approved_optimizations, auto_apply
        
        # Analyze layers for optimization opportunities
        try:
            from .core.services.auto_optimizer import (
                LayerAnalyzer, AutoOptimizer, AUTO_OPTIMIZER_AVAILABLE, OptimizationType
            )
            
            if not AUTO_OPTIMIZER_AVAILABLE:
                return approved_optimizations, auto_apply
            
            analyzer = LayerAnalyzer()
            optimizer = AutoOptimizer()
            
            # Collect all layers that need optimization
            layers_needing_optimization = []
            
            # Get layers to filter from task parameters
            task_layers = task_parameters.get("task", {}).get("layers", [])
            
            # v2.8.6: Get buffer parameters for optimization recommendations
            filtering_params = task_parameters.get("filtering", {})
            has_buffer = filtering_params.get("has_buffer_value", False)
            has_buffer_type = filtering_params.get("has_buffer_type", False)
            
            # v2.8.7: Get distant layers (layers_to_filter) for centroid optimization
            has_layers_to_filter = filtering_params.get("has_layers_to_filter", False)
            layers_to_filter_ids = filtering_params.get("layers_to_filter", [])
            
            # v2.8.7: Check if distant layers centroid is already enabled
            # v2.9.31 FIX: checkBox_filtering_use_centroids_distant_layers doesn't exist!
            # Use checkBox_filtering_use_centroids_source_layer instead (controls both)
            distant_centroid_enabled = False
            if self.dockwidget and hasattr(self.dockwidget, 'checkBox_filtering_use_centroids_distant_layers'):
                distant_centroid_enabled = self.dockwidget.checkBox_filtering_use_centroids_distant_layers.isChecked()
            elif self.dockwidget and hasattr(self.dockwidget, 'checkBox_filtering_use_centroids_source_layer'):
                # v2.9.31 FIX: Fallback to source checkbox (controls both source and distant layers)
                distant_centroid_enabled = self.dockwidget.checkBox_filtering_use_centroids_source_layer.isChecked()
            
            # v2.8.7: Collect and analyze distant layers for centroid optimization
            distant_layers_recommendations = []
            distant_layers_analyses = []  # Initialize outside the if block
            if has_layers_to_filter and layers_to_filter_ids and not distant_centroid_enabled:
                for distant_layer_id in layers_to_filter_ids:
                    distant_layer = self.PROJECT.mapLayer(distant_layer_id)
                    if distant_layer and distant_layer.isValid():
                        distant_analysis = analyzer.analyze_layer(distant_layer)
                        if distant_analysis:
                            distant_layers_analyses.append(distant_analysis)
                
                # Evaluate centroid optimization for distant layers
                if distant_layers_analyses:
                    distant_centroid_rec = optimizer.evaluate_distant_layers_centroid(
                        distant_layers_analyses,
                        user_already_enabled=distant_centroid_enabled
                    )
                    if distant_centroid_rec:
                        distant_layers_recommendations.append(distant_centroid_rec)
                        logger.debug(f"Distant layers centroid optimization recommended: {distant_centroid_rec.reason}")
            
            for layer_props in task_layers:
                layer_id = layer_props.get("layer_id")
                if not layer_id:
                    continue
                
                # Get actual layer object
                layer = self.PROJECT.mapLayer(layer_id)
                if not layer or not layer.isValid():
                    continue
                
                # Analyze the layer
                analysis = analyzer.analyze_layer(layer)
                if not analysis:
                    continue
                
                # v2.7.15: Check if centroid is already enabled for this layer
                # Don't recommend if user already has centroids enabled via checkbox or override
                user_centroid_enabled = False
                if self.dockwidget:
                    user_centroid_enabled = self.dockwidget._is_centroid_already_enabled(layer) if hasattr(self.dockwidget, '_is_centroid_already_enabled') else False
                
                # Get recommendations - skip centroid if already enabled
                # v2.8.6: Pass buffer parameters for buffer type optimization
                # v2.8.9: is_source_layer=False because these are target layers being filtered
                recommendations = optimizer.get_recommendations(
                    analysis, 
                    user_centroid_enabled=user_centroid_enabled,
                    has_buffer=has_buffer,
                    has_buffer_type=has_buffer_type,
                    is_source_layer=False
                )
                
                # Check if any significant optimization is recommended
                # v2.8.6: Include ENABLE_BUFFER_TYPE in addition to USE_CENTROID_DISTANT
                has_significant_recommendation = False
                for rec in recommendations:
                    if rec.auto_applicable and rec.optimization_type in (
                        OptimizationType.USE_CENTROID_DISTANT,
                        OptimizationType.ENABLE_BUFFER_TYPE
                    ):
                        has_significant_recommendation = True
                        break
                
                if has_significant_recommendation:
                    layers_needing_optimization.append({
                        'layer': layer,
                        'layer_id': layer_id,
                        'analysis': analysis,
                        'recommendations': recommendations
                    })
            
            # v2.8.7: Check if we have distant layer recommendations OR target layer recommendations
            has_any_recommendations = bool(layers_needing_optimization) or bool(distant_layers_recommendations)
            
            if not has_any_recommendations:
                logger.debug("No optimization recommendations for current filtering operation")
                return approved_optimizations, auto_apply
            
            # Show confirmation dialog
            total_recommendations = len(layers_needing_optimization)
            if distant_layers_recommendations:
                total_recommendations += 1
            logger.info(f"Found {total_recommendations} optimization recommendation(s) (including distant layers)")
            
            from .modules.optimization_dialogs import OptimizationRecommendationDialog
            
            # v2.8.7: Combine recommendations from target layer and distant layers
            # Determine what to display in the dialog based on recommendation types
            recommendations = []
            dialog_layer_name = ""
            dialog_feature_count = 0
            dialog_location_type = "local_file"
            
            if layers_needing_optimization:
                # Use first target layer info for recommendations
                first_layer_info = layers_needing_optimization[0]
                layer = first_layer_info['layer']
                analysis = first_layer_info['analysis']
                recommendations = list(first_layer_info['recommendations'])
                # v2.8.8: Always use source layer name in dialog title for context
                dialog_layer_name = current_layer.name()
                dialog_feature_count = analysis.feature_count
                dialog_location_type = analysis.location_type.value
            
            # v2.8.7: If we have distant layer recommendations, adjust dialog info
            if distant_layers_recommendations:
                recommendations.extend(distant_layers_recommendations)
                
                # If ONLY distant layer recommendations (no target layer recs),
                # display info about the distant layers instead
                if not layers_needing_optimization:
                    # Calculate total features from all distant layers
                    total_distant_features = 0
                    distant_layer_names = []
                    for distant_layer_id in layers_to_filter_ids:
                        distant_layer = self.PROJECT.mapLayer(distant_layer_id)
                        if distant_layer and distant_layer.isValid():
                            total_distant_features += distant_layer.featureCount()
                            distant_layer_names.append(distant_layer.name())
                    
                    # Use source layer name but indicate it's about distant layers
                    dialog_layer_name = current_layer.name()
                    dialog_feature_count = total_distant_features
                    # Get location type from first distant layer analysis
                    if distant_layers_analyses:
                        dialog_location_type = distant_layers_analyses[0].location_type.value
            
            # v2.8.10: Deduplicate recommendations by optimization_type
            # Keep the recommendation with the highest speedup for each type
            deduped_recommendations = {}
            for rec in recommendations:
                opt_type = rec.optimization_type.value if hasattr(rec.optimization_type, 'value') else str(rec.optimization_type)
                if opt_type not in deduped_recommendations:
                    deduped_recommendations[opt_type] = rec
                elif rec.estimated_speedup > deduped_recommendations[opt_type].estimated_speedup:
                    deduped_recommendations[opt_type] = rec
            recommendations = list(deduped_recommendations.values())
            
            dialog = OptimizationRecommendationDialog(
                layer_name=dialog_layer_name,
                recommendations=[r.to_dict() for r in recommendations],
                feature_count=dialog_feature_count,
                location_type=dialog_location_type,
                parent=self.dockwidget
            )
            
            result = dialog.exec_()
            
            if result:
                selected = dialog.get_selected_optimizations()
                
                # Apply to all similar layers
                for layer_info in layers_needing_optimization:
                    approved_optimizations[layer_info['layer_id']] = selected
                
                # v2.7.1: Update UI widgets when user accepts optimizations
                # This ensures checkboxes reflect the user's optimization choices
                self._apply_optimization_to_ui_widgets(selected)
                
                # Check if user wants to remember
                if dialog.should_remember():
                    # Store in dockwidget for session persistence
                    if not hasattr(self.dockwidget, '_session_optimization_choices'):
                        self.dockwidget._session_optimization_choices = {}
                    
                    for layer_info in layers_needing_optimization:
                        self.dockwidget._session_optimization_choices[layer_info['layer_id']] = selected
                
                logger.info(f"User approved optimizations: {approved_optimizations}")
            else:
                logger.info("User skipped optimizations")
            
        except ImportError as e:
            logger.debug(f"Auto-optimizer not available: {e}")
        except Exception as e:
            logger.warning(f"Error in optimization check: {e}")
        
        return approved_optimizations, auto_apply
    
    def _apply_optimization_to_ui_widgets(self, selected_optimizations: dict):
        """
        Apply accepted optimization choices to UI widgets.
        
        When user accepts optimizations in the confirmation dialog, this method
        updates the corresponding checkboxes and other UI controls to reflect
        their choices. This ensures visual consistency between the dialog
        selections and the main UI state.
        
        Args:
            selected_optimizations: Dict of {optimization_type: bool} choices
                e.g., {'use_centroid_distant': True, 'simplify_geometry': False}
        
        v2.7.1: New method for UI synchronization after optimization acceptance
        v2.8.7: Added support for use_centroid_distant optimization type
        """
        if not self.dockwidget or not selected_optimizations:
            return
        
        try:
            # Handle centroid optimization for distant layers only
            # IMPORTANT v2.7.2: Do NOT enable centroids for source layer when it's a polygon
            # used for spatial intersection - this would give geometrically incorrect results.
            # Centroid optimization should only apply to distant layers being filtered.
            use_distant_centroids = selected_optimizations.get('use_centroid_distant', False)
            
            if use_distant_centroids:
                # Update distant layers centroid checkbox (primary target for remote layers)
                if hasattr(self.dockwidget, 'checkBox_filtering_use_centroids_distant_layers'):
                    if not self.dockwidget.checkBox_filtering_use_centroids_distant_layers.isChecked():
                        self.dockwidget.checkBox_filtering_use_centroids_distant_layers.setChecked(True)
                        logger.info("AUTO-OPTIMIZATION: Enabled 'use_centroids_distant_layers' checkbox")
                
                # v2.7.2: Do NOT automatically enable centroids for source layer
                # The source layer geometry must be preserved for accurate spatial intersection.
                # Users can still manually enable this if they understand the implications.
                # if hasattr(self.dockwidget, 'checkBox_filtering_use_centroids_source_layer'):
                #     if not self.dockwidget.checkBox_filtering_use_centroids_source_layer.isChecked():
                #         self.dockwidget.checkBox_filtering_use_centroids_source_layer.setChecked(True)
                #         logger.info("AUTO-OPTIMIZATION: Enabled 'use_centroids_source_layer' checkbox")
                
                # Also update the current layer's stored parameters (distant layers only)
                if hasattr(self.dockwidget, 'current_layer') and self.dockwidget.current_layer:
                    layer_id = self.dockwidget.current_layer.id()
                    if layer_id in self.PROJECT_LAYERS:
                        if "filtering" not in self.PROJECT_LAYERS[layer_id]:
                            self.PROJECT_LAYERS[layer_id]["filtering"] = {}
                        # v2.7.2: Only set distant layers centroids, NOT source layer
                        self.PROJECT_LAYERS[layer_id]["filtering"]["use_centroids_distant_layers"] = True
                        logger.debug(f"AUTO-OPTIMIZATION: Updated PROJECT_LAYERS for {layer_id} (distant layers only)")
            
            # Handle other optimization types (future expansion)
            # if selected_optimizations.get('simplify_geometry', False):
            #     # Update simplification UI if it exists
            #     pass
            
            # if selected_optimizations.get('bbox_prefilter', False):
            #     # Update bbox prefilter UI if it exists
            #     pass
            
            # v2.8.6: Handle enable_buffer_type optimization
            # When user accepts, enable buffer type with Flat type and 1 segment
            if selected_optimizations.get('enable_buffer_type', False):
                # Enable the buffer type toggle button
                if hasattr(self.dockwidget, 'pushButton_checkable_filtering_buffer_type'):
                    if not self.dockwidget.pushButton_checkable_filtering_buffer_type.isChecked():
                        self.dockwidget.pushButton_checkable_filtering_buffer_type.setChecked(True)
                        logger.info("AUTO-OPTIMIZATION: Enabled 'buffer_type' toggle button")
                
                # Set buffer type to "Flat" (index 1) for performance
                if hasattr(self.dockwidget, 'comboBox_filtering_buffer_type'):
                    # Find "Flat" option in combobox
                    flat_index = self.dockwidget.comboBox_filtering_buffer_type.findText("Flat")
                    if flat_index >= 0:
                        self.dockwidget.comboBox_filtering_buffer_type.setCurrentIndex(flat_index)
                        logger.info("AUTO-OPTIMIZATION: Set buffer type to 'Flat'")
                
                # Set buffer segments to 1 for maximum performance
                if hasattr(self.dockwidget, 'mQgsSpinBox_filtering_buffer_segments'):
                    self.dockwidget.mQgsSpinBox_filtering_buffer_segments.setValue(1)
                    logger.info("AUTO-OPTIMIZATION: Set buffer segments to 1")
                
                # Update the current layer's stored parameters
                if hasattr(self.dockwidget, 'current_layer') and self.dockwidget.current_layer:
                    layer_id = self.dockwidget.current_layer.id()
                    if layer_id in self.PROJECT_LAYERS:
                        if "filtering" not in self.PROJECT_LAYERS[layer_id]:
                            self.PROJECT_LAYERS[layer_id]["filtering"] = {}
                        self.PROJECT_LAYERS[layer_id]["filtering"]["has_buffer_type"] = True
                        self.PROJECT_LAYERS[layer_id]["filtering"]["buffer_type"] = "Flat"
                        self.PROJECT_LAYERS[layer_id]["filtering"]["buffer_segments"] = 1
                        logger.debug(f"AUTO-OPTIMIZATION: Updated PROJECT_LAYERS buffer params for {layer_id}")
            
            logger.debug(f"Applied optimization choices to UI: {selected_optimizations}")
            
        except Exception as e:
            logger.warning(f"Error applying optimizations to UI widgets: {e}")
    
    def _build_layers_to_filter(self, current_layer):
        """Build list of layers to filter with validation.
        
        AUTO-DETECTION: If source layer is from a GeoPackage, automatically includes
        all other layers from the same GeoPackage file for geometric filtering.
        This ensures consistent filtering across all layers in the same data source.
        
        Args:
            current_layer: Source layer for filtering
            
        Returns:
            list: List of validated layer info dictionaries
        """
        layers_to_filter = []
        
        # STABILITY FIX: Verify layer exists in PROJECT_LAYERS before access
        if current_layer.id() not in self.PROJECT_LAYERS:
            logger.warning(f"_build_layers_to_filter: layer {current_layer.name()} not in PROJECT_LAYERS")
            return layers_to_filter
        
        # DIAGNOSTIC: Log the raw layers_to_filter list from PROJECT_LAYERS
        raw_layers_list = self.PROJECT_LAYERS[current_layer.id()]["filtering"].get("layers_to_filter", [])
        logger.info(f"=== _build_layers_to_filter DIAGNOSTIC ===")
        logger.info(f"  Source layer: {current_layer.name()} (id={current_layer.id()[:8]}...)")
        logger.info(f"  Raw layers_to_filter list (user-selected): {raw_layers_list}")
        logger.info(f"  Number of user-selected layers: {len(raw_layers_list)}")
        
        # DIAGNOSTIC v2.7.4: List ALL available layers vs selected ones to identify missing layers
        all_available_layers = []
        for key in list(self.PROJECT_LAYERS.keys()):
            if key != current_layer.id():  # Exclude source layer
                layer_obj = self.PROJECT.mapLayer(key)
                if layer_obj:
                    all_available_layers.append((layer_obj.name(), key[:8], key))
        
        logger.info(f"  All available layers in PROJECT_LAYERS for filtering ({len(all_available_layers)}):")
        for name, key_prefix, full_key in all_available_layers:
            is_selected = full_key in raw_layers_list
            status = "✓ SELECTED" if is_selected else "✗ NOT SELECTED"
            logger.info(f"    - {name} ({key_prefix}...) → {status}")
        
        # FIX v2.7.5: Detect layers in QGIS project but NOT in PROJECT_LAYERS (registration issue)
        qgis_layers = [l for l in self.PROJECT.mapLayers().values() if isinstance(l, QgsVectorLayer)]
        missing_from_project_layers = []
        for qgis_layer in qgis_layers:
            if qgis_layer.id() not in self.PROJECT_LAYERS and qgis_layer.id() != current_layer.id():
                missing_from_project_layers.append(qgis_layer.name())
        
        if missing_from_project_layers:
            logger.warning(f"  ⚠️ QGIS layers NOT in PROJECT_LAYERS (may need re-add): {missing_from_project_layers}")
        
        # FIX v2.5.15: Disabled auto-inclusion of GeoPackage layers
        # User selection is now strictly respected - only explicitly checked layers are filtered
        # Previously, all layers from the same GeoPackage were auto-included, ignoring user selection
        logger.info(f"  Final layers to process: {len(raw_layers_list)} (user selection only)")
        
        for key in raw_layers_list:
            # FIX v2.7.5: Log when layer is not in PROJECT_LAYERS (was silently ignored)
            if key not in self.PROJECT_LAYERS:
                # Try to find layer name for better error message
                layer_obj = self.PROJECT.mapLayer(key)
                layer_name = layer_obj.name() if layer_obj else "unknown"
                logger.warning(
                    f"  ⚠️ Layer '{layer_name}' (id={key[:16]}...) in user selection but NOT in PROJECT_LAYERS - SKIPPED!"
                )
                logger.warning(f"     Available PROJECT_LAYERS keys count: {len(self.PROJECT_LAYERS)}")
                continue
            
            layer_info = self.PROJECT_LAYERS[key]["infos"].copy()
            
            # CRITICAL FIX v2.7.8: Remove stale runtime keys from previous filter executions
            # These keys should NOT be part of the persistent layer configuration
            for stale_key in ['_effective_provider_type', '_postgresql_fallback', '_forced_backend']:
                layer_info.pop(stale_key, None)

            # Resolve actual QgsVectorLayer by id
            layer_obj = [l for l in self.PROJECT.mapLayers().values() if l.id() == key]
            if not layer_obj:
                logger.error(f"Cannot filter layer {key}: layer not found in project")
                continue
            layer = layer_obj[0]

            # Skip invalid or unavailable layers (broken source)
            if not is_layer_source_available(layer):
                logger.warning(
                    f"Skipping layer '{layer.name()}' (id={key}) - invalid or source missing"
                )
                continue
            
            # Validate required keys exist for geometric filtering
            required_keys = [
                'layer_name', 'layer_id', 'layer_provider_type',
                'primary_key_name', 'layer_geometry_field', 'layer_schema'
            ]
            
            missing_keys = [k for k in required_keys if k not in layer_info or layer_info[k] is None]
            if missing_keys:
                logger.warning(f"Layer {key} missing required keys: {missing_keys}")
                # Try to fill in missing keys from QGIS layer object
                if layer_obj:
                    layer = layer_obj[0]
                    # Fill basic info
                    if 'layer_name' not in layer_info or layer_info['layer_name'] is None:
                        layer_info['layer_name'] = layer.name()
                    if 'layer_id' not in layer_info or layer_info['layer_id'] is None:
                        layer_info['layer_id'] = layer.id()
                    
                    # Fill layer_geometry_field from data provider
                    if 'layer_geometry_field' not in layer_info or layer_info['layer_geometry_field'] is None:
                        try:
                            geom_col = layer.dataProvider().geometryColumn()
                            if geom_col:
                                layer_info['layer_geometry_field'] = geom_col
                                logger.info(f"Auto-filled layer_geometry_field='{geom_col}' for layer {layer.name()}")
                            else:
                                # Default geometry field names by provider
                                provider = layer.providerType()
                                if provider == 'postgres':
                                    layer_info['layer_geometry_field'] = 'geom'
                                elif provider == 'spatialite':
                                    layer_info['layer_geometry_field'] = 'geometry'
                                else:
                                    layer_info['layer_geometry_field'] = 'geom'
                                logger.info(f"Using default layer_geometry_field='{layer_info['layer_geometry_field']}' for layer {layer.name()}")
                        except Exception as e:
                            layer_info['layer_geometry_field'] = 'geom'
                            logger.warning(f"Could not detect geometry column for {layer.name()}, using 'geom': {e}")
                    
                    # Fill layer_provider_type
                    # Use detect_layer_provider_type to get correct provider for backend selection
                    if 'layer_provider_type' not in layer_info or layer_info['layer_provider_type'] is None:
                        detected_type = detect_layer_provider_type(layer)
                        layer_info['layer_provider_type'] = detected_type
                        logger.info(f"Auto-filled layer_provider_type='{detected_type}' for layer {layer.name()}")
                    
                    # Fill/validate layer_schema (NULL for non-PostgreSQL layers)
                    # CRITICAL FIX v2.3.15: Always re-validate schema from layer source for PostgreSQL
                    # The stored layer_schema can be corrupted or incorrect (e.g., literal "schema" string)
                    if layer_info.get('layer_provider_type') == 'postgresql':
                        try:
                            from qgis.core import QgsDataSourceUri
                            source_uri = QgsDataSourceUri(layer.source())
                            detected_schema = source_uri.schema()
                            stored_schema = layer_info.get('layer_schema')
                            
                            if detected_schema:
                                if stored_schema and stored_schema != detected_schema and stored_schema != 'NULL':
                                    logger.warning(f"Schema mismatch for {layer.name()}: stored='{stored_schema}', actual='{detected_schema}'")
                                layer_info['layer_schema'] = detected_schema
                                logger.debug(f"Validated layer_schema='{detected_schema}' for layer {layer.name()}")
                            elif not stored_schema or stored_schema == 'NULL':
                                layer_info['layer_schema'] = 'public'
                                logger.info(f"Auto-filled layer_schema='public' (default) for layer {layer.name()}")
                        except Exception as e:
                            logger.warning(f"Could not detect schema for {layer.name()}: {e}")
                            if 'layer_schema' not in layer_info or layer_info['layer_schema'] is None:
                                # Fallback to regex if QgsDataSourceUri fails
                                import re
                                source = layer.source()
                                match = re.search(r'table="([^"]+)"\.', source)
                                if match:
                                    layer_info['layer_schema'] = match.group(1)
                                else:
                                    layer_info['layer_schema'] = 'public'
                                logger.info(f"Auto-filled layer_schema='{layer_info['layer_schema']}' (regex fallback) for layer {layer.name()}")
                    elif 'layer_schema' not in layer_info or layer_info['layer_schema'] is None:
                        layer_info['layer_schema'] = 'NULL'
                    
                    # Fill primary_key_name by searching for a unique field
                    if 'primary_key_name' not in layer_info or layer_info['primary_key_name'] is None:
                        pk_found = False
                        # Check declared primary key
                        pk_attrs = layer.primaryKeyAttributes()
                        if pk_attrs:
                            field = layer.fields()[pk_attrs[0]]
                            layer_info['primary_key_name'] = field.name()
                            pk_found = True
                            logger.info(f"Auto-filled primary_key_name='{field.name()}' from primary key for layer {layer.name()}")
                        
                        # Fallback: look for 'id' field
                        if not pk_found:
                            for field in layer.fields():
                                if 'id' in field.name().lower():
                                    layer_info['primary_key_name'] = field.name()
                                    pk_found = True
                                    logger.info(f"Auto-filled primary_key_name='{field.name()}' (contains 'id') for layer {layer.name()}")
                                    break
                        
                        # Last resort: use first numeric field
                        if not pk_found:
                            for field in layer.fields():
                                if field.isNumeric():
                                    layer_info['primary_key_name'] = field.name()
                                    logger.info(f"Auto-filled primary_key_name='{field.name()}' (first numeric) for layer {layer.name()}")
                                    break
                    
                    # Log what still couldn't be filled
                    still_missing = [k for k in required_keys if k not in layer_info or layer_info[k] is None]
                    if still_missing:
                        logger.error(f"Cannot filter layer {layer.name()} (id={key}): still missing {still_missing}")
                        continue
                    else:
                        logger.info(f"Successfully auto-filled missing properties for layer {layer.name()}")
                        # Update PROJECT_LAYERS with auto-filled values
                        # CRITICAL FIX v2.7.8: Remove runtime keys before updating persistent storage
                        # These keys should only exist during filter execution, not in saved config
                        update_info = {k: v for k, v in layer_info.items() 
                                       if k not in ['_effective_provider_type', '_postgresql_fallback', '_forced_backend']}
                        self.PROJECT_LAYERS[key]["infos"].update(update_info)
                else:
                    logger.error(f"Cannot filter layer {key}: layer not found in project")
                    continue
            
            layers_to_filter.append(layer_info)
            logger.info(f"  ✓ Added layer to filter list: {layer_info.get('layer_name', key)}")
        
        logger.info(f"=== Built layers_to_filter list with {len(layers_to_filter)} layers ===")
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
            else:
                current_layer = self.dockwidget.current_layer 

            # Guard: current layer must be valid and source available
            if not is_layer_source_available(current_layer):
                logger.warning(
                    f"FilterMate: Layer '{current_layer.name() if current_layer else 'Unknown'}' is invalid or source missing."
                )
                iface.messageBar().pushWarning(
                    "FilterMate",
                    "La couche sélectionnée est invalide ou sa source est introuvable. Opération annulée."
                )
                return None

            # CRITICAL: Verify layer is in PROJECT_LAYERS before proceeding
            if current_layer.id() not in self.PROJECT_LAYERS.keys():
                logger.warning(f"FilterMate: Layer '{current_layer.name()}' (id: {current_layer.id()}) not found in PROJECT_LAYERS. "
                              "The layer may not have been processed yet. Try selecting another layer and then back.")
                iface.messageBar().pushWarning(
                    "FilterMate", 
                    f"La couche '{current_layer.name()}' n'est pas encore initialisée. "
                    "Essayez de sélectionner une autre couche puis revenez à celle-ci."
                )
                return None
            
            task_parameters = self.PROJECT_LAYERS[current_layer.id()]
            
            # CRITICAL FIX v2.5.x: Synchronize buffer spinbox value to PROJECT_LAYERS
            # The spinbox valueChanged signal may not have updated PROJECT_LAYERS yet
            # Read the current spinbox value directly and sync it before creating task params
            # FIX v3.0.12: Clean buffer value from float precision errors (0.9999999 → 1.0)
            if self.dockwidget and hasattr(self.dockwidget, 'mQgsDoubleSpinBox_filtering_buffer_value'):
                current_spinbox_buffer = clean_buffer_value(self.dockwidget.mQgsDoubleSpinBox_filtering_buffer_value.value())
                stored_buffer = task_parameters.get("filtering", {}).get("buffer_value", 0.0)
                if current_spinbox_buffer != stored_buffer:
                    logger.info(f"SYNC buffer_value: spinbox={current_spinbox_buffer}, stored={stored_buffer} → updating")
                    if "filtering" not in task_parameters:
                        task_parameters["filtering"] = {}
                    task_parameters["filtering"]["buffer_value"] = current_spinbox_buffer
                    self.PROJECT_LAYERS[current_layer.id()]["filtering"]["buffer_value"] = current_spinbox_buffer

            # CRITICAL FIX v2.5.11: Synchronize buffer_segments spinbox value to PROJECT_LAYERS
            # Same issue as buffer_value - the spinbox valueChanged signal may not have updated PROJECT_LAYERS yet
            if self.dockwidget and hasattr(self.dockwidget, 'mQgsSpinBox_filtering_buffer_segments'):
                current_spinbox_segments = self.dockwidget.mQgsSpinBox_filtering_buffer_segments.value()
                stored_segments = task_parameters.get("filtering", {}).get("buffer_segments", 5)
                if current_spinbox_segments != stored_segments:
                    logger.info(f"SYNC buffer_segments: spinbox={current_spinbox_segments}, stored={stored_segments} → updating")
                    if "filtering" not in task_parameters:
                        task_parameters["filtering"] = {}
                    task_parameters["filtering"]["buffer_segments"] = current_spinbox_segments
                    self.PROJECT_LAYERS[current_layer.id()]["filtering"]["buffer_segments"] = current_spinbox_segments

            # CRITICAL FIX v2.5.11: Synchronize buffer_type combobox value to PROJECT_LAYERS
            # Same issue - the combobox currentTextChanged signal may not have updated PROJECT_LAYERS yet
            if self.dockwidget and hasattr(self.dockwidget, 'comboBox_filtering_buffer_type'):
                current_buffer_type = self.dockwidget.comboBox_filtering_buffer_type.currentText()
                stored_buffer_type = task_parameters.get("filtering", {}).get("buffer_type", "Round")
                if current_buffer_type != stored_buffer_type:
                    logger.info(f"SYNC buffer_type: combobox={current_buffer_type}, stored={stored_buffer_type} → updating")
                    if "filtering" not in task_parameters:
                        task_parameters["filtering"] = {}
                    task_parameters["filtering"]["buffer_type"] = current_buffer_type
                    self.PROJECT_LAYERS[current_layer.id()]["filtering"]["buffer_type"] = current_buffer_type

            # CENTROID OPTIMIZATION v2.5.12: Synchronize use_centroids checkboxes (source and distant layers)
            if self.dockwidget and hasattr(self.dockwidget, 'checkBox_filtering_use_centroids_source_layer'):
                current_use_centroids_source = self.dockwidget.checkBox_filtering_use_centroids_source_layer.isChecked()
                stored_use_centroids_source = task_parameters.get("filtering", {}).get("use_centroids_source_layer", False)
                if current_use_centroids_source != stored_use_centroids_source:
                    logger.info(f"SYNC use_centroids_source_layer: checkbox={current_use_centroids_source}, stored={stored_use_centroids_source} → updating")
                    if "filtering" not in task_parameters:
                        task_parameters["filtering"] = {}
                    task_parameters["filtering"]["use_centroids_source_layer"] = current_use_centroids_source
                    self.PROJECT_LAYERS[current_layer.id()]["filtering"]["use_centroids_source_layer"] = current_use_centroids_source
            
            if self.dockwidget and hasattr(self.dockwidget, 'checkBox_filtering_use_centroids_distant_layers'):
                current_use_centroids_distant = self.dockwidget.checkBox_filtering_use_centroids_distant_layers.isChecked()
                stored_use_centroids_distant = task_parameters.get("filtering", {}).get("use_centroids_distant_layers", False)
                if current_use_centroids_distant != stored_use_centroids_distant:
                    logger.info(f"SYNC use_centroids_distant_layers: checkbox={current_use_centroids_distant}, stored={stored_use_centroids_distant} → updating")
                    if "filtering" not in task_parameters:
                        task_parameters["filtering"] = {}
                    task_parameters["filtering"]["use_centroids_distant_layers"] = current_use_centroids_distant
                    self.PROJECT_LAYERS[current_layer.id()]["filtering"]["use_centroids_distant_layers"] = current_use_centroids_distant

            if current_layer.subsetString() != '':
                self.PROJECT_LAYERS[current_layer.id()]["infos"]["is_already_subset"] = True
            else:
                self.PROJECT_LAYERS[current_layer.id()]["infos"]["is_already_subset"] = False

            # CRITICAL FIX v2.5.x: Synchronize has_geometric_predicates button state
            # The button clicked signal may not have updated PROJECT_LAYERS yet
            if self.dockwidget and hasattr(self.dockwidget, 'pushButton_checkable_filtering_geometric_predicates'):
                current_has_geom_predicates = self.dockwidget.pushButton_checkable_filtering_geometric_predicates.isChecked()
                stored_has_geom_predicates = task_parameters.get("filtering", {}).get("has_geometric_predicates", False)
                if current_has_geom_predicates != stored_has_geom_predicates:
                    logger.info(f"SYNC has_geometric_predicates: button={current_has_geom_predicates}, stored={stored_has_geom_predicates} → updating")
                    if "filtering" not in task_parameters:
                        task_parameters["filtering"] = {}
                    task_parameters["filtering"]["has_geometric_predicates"] = current_has_geom_predicates
                    self.PROJECT_LAYERS[current_layer.id()]["filtering"]["has_geometric_predicates"] = current_has_geom_predicates

            # CRITICAL FIX v2.5.x: Synchronize geometric_predicates list from UI
            # The listWidget selection may not have updated PROJECT_LAYERS yet
            if self.dockwidget and hasattr(self.dockwidget, 'listWidget_filtering_geometric_predicate'):
                # Get selected predicates from list widget
                selected_items = self.dockwidget.listWidget_filtering_geometric_predicate.selectedItems()
                current_predicates = [item.text() for item in selected_items]
                stored_predicates = task_parameters.get("filtering", {}).get("geometric_predicates", [])
                if set(current_predicates) != set(stored_predicates):
                    logger.info(f"SYNC geometric_predicates: listWidget={current_predicates}, stored={stored_predicates} → updating")
                    if "filtering" not in task_parameters:
                        task_parameters["filtering"] = {}
                    task_parameters["filtering"]["geometric_predicates"] = current_predicates
                    self.PROJECT_LAYERS[current_layer.id()]["filtering"]["geometric_predicates"] = current_predicates

            # CRITICAL FIX v2.5.x: Synchronize has_layers_to_filter button state
            if self.dockwidget and hasattr(self.dockwidget, 'pushButton_checkable_filtering_layers_to_filter'):
                current_has_layers = self.dockwidget.pushButton_checkable_filtering_layers_to_filter.isChecked()
                stored_has_layers = task_parameters.get("filtering", {}).get("has_layers_to_filter", False)
                if current_has_layers != stored_has_layers:
                    logger.info(f"SYNC has_layers_to_filter: button={current_has_layers}, stored={stored_has_layers} → updating")
                    if "filtering" not in task_parameters:
                        task_parameters["filtering"] = {}
                    task_parameters["filtering"]["has_layers_to_filter"] = current_has_layers
                    self.PROJECT_LAYERS[current_layer.id()]["filtering"]["has_layers_to_filter"] = current_has_layers

            # CRITICAL FIX v2.5.x: Synchronize layers_to_filter list from UI
            # The combobox checked items may not have updated PROJECT_LAYERS yet
            if self.dockwidget and hasattr(self.dockwidget, 'get_layers_to_filter'):
                current_layers_to_filter = self.dockwidget.get_layers_to_filter()
                stored_layers_to_filter = task_parameters.get("filtering", {}).get("layers_to_filter", [])
                if set(current_layers_to_filter) != set(stored_layers_to_filter):
                    logger.info(f"SYNC layers_to_filter: combobox={len(current_layers_to_filter)} layers, stored={len(stored_layers_to_filter)} layers → updating")
                    if "filtering" not in task_parameters:
                        task_parameters["filtering"] = {}
                    task_parameters["filtering"]["layers_to_filter"] = current_layers_to_filter
                    self.PROJECT_LAYERS[current_layer.id()]["filtering"]["layers_to_filter"] = current_layers_to_filter

            # v2.7.17: Enhanced logging before getting features
            # v2.9.28: FIX - reset and unfilter do NOT require features to be selected
            # Only filter operation requires features - reset/unfilter just need source layer and distant layers
            if task_name == 'filter':
                logger.info(f"get_task_parameters: Calling get_current_features()...")
                features, expression = self.dockwidget.get_current_features()
                logger.info(f"get_task_parameters: get_current_features() returned {len(features)} features, expression='{expression}'")
                
                # v2.7.17: CRITICAL CHECK - Warn if no features and no expression
                # v2.9.20: Enhanced warning with QGIS MessageLog for visibility
                # v2.9.21: FIX - Abort filter in single_selection mode to prevent FALLBACK MODE
                if len(features) == 0 and not expression:
                    logger.warning(f"⚠️ get_task_parameters: NO FEATURES and NO EXPRESSION!")
                    logger.warning(f"   current_exploring_groupbox: {self.dockwidget.current_exploring_groupbox}")
                    logger.warning(f"   This may cause the filter task to abort or filter incorrectly")
                    from qgis.core import QgsMessageLog, Qgis
                    QgsMessageLog.logMessage(
                        f"⚠️ CRITICAL: No source features selected! Groupbox: {self.dockwidget.current_exploring_groupbox}",
                        "FilterMate", Qgis.Warning
                    )
                    
                    # v2.9.21: ABORT filter in single_selection mode instead of continuing with ALL features
                    if self.dockwidget.current_exploring_groupbox == "single_selection":
                        QgsMessageLog.logMessage(
                            f"   Aborting filter - single_selection mode requires a selected feature!",
                            "FilterMate", Qgis.Warning
                        )
                        iface.messageBar().pushWarning(
                            "FilterMate",
                            "Aucune entité sélectionnée! Le widget de sélection a perdu la feature. Re-sélectionnez une entité."
                        )
                        logger.warning(f"⚠️ ABORTING filter task - single_selection mode with no selection!")
                        return None  # v2.9.21: Abort filter instead of using FALLBACK MODE
                    else:
                        QgsMessageLog.logMessage(
                            f"   The filter will use ALL features from source layer - this is probably NOT what you want!",
                            "FilterMate", Qgis.Warning
                        )
            else:
                # v2.9.28: For reset and unfilter, we don't need features - just initialize empty values
                # These operations just clear filters on source and distant layers
                logger.info(f"get_task_parameters: task_name='{task_name}' - no features needed (reset/unfilter)")
                features = []
                expression = ""

            if task_name in ('filter', 'unfilter', 'reset'):
                # Build validated list of layers to filter
                layers_to_filter = self._build_layers_to_filter(current_layer)
                
                # Log filtering state - ENHANCED DIAGNOSTIC
                filtering_props = self.PROJECT_LAYERS[current_layer.id()]["filtering"]
                logger.info(f"=" * 60)
                logger.info(f"🔍 GEOMETRIC FILTERING DIAGNOSTIC - get_task_parameters")
                logger.info(f"=" * 60)
                logger.info(f"  Source layer: {current_layer.name()}")
                logger.info(f"  has_geometric_predicates: {filtering_props.get('has_geometric_predicates', 'NOT SET')}")
                logger.info(f"  geometric_predicates: {filtering_props.get('geometric_predicates', [])}")
                logger.info(f"  has_layers_to_filter: {filtering_props.get('has_layers_to_filter', 'NOT SET')}")
                logger.info(f"  layers_to_filter (from filtering): {filtering_props.get('layers_to_filter', [])}")
                logger.info(f"  layers_to_filter (validated): {len(layers_to_filter)} layers")
                for i, l in enumerate(layers_to_filter[:5]):  # Show first 5
                    logger.info(f"    {i+1}. {l.get('layer_name', 'unknown')}")
                if len(layers_to_filter) > 5:
                    logger.info(f"    ... and {len(layers_to_filter) - 5} more")
                logger.info(f"=" * 60)
                
                # Build common task parameters
                # Note: unfilter no longer needs history_manager (just clears filters)
                include_history = False
                task_parameters["task"] = self._build_common_task_params(
                    features, expression, layers_to_filter, include_history
                )
                
                # NOUVEAU: Détecter si le filtre source doit être ignoré
                # Cas: custom_selection active ET expression n'est pas un filtre valide
                # (pas d'opérateurs de comparaison - ex: juste un nom de champ ou expression display)
                # 
                # NOTE v2.9.23: single_selection et multiple_selection filtrent TOUJOURS la couche source
                # Le filtre est appliqué selon la logique du groupbox actif
                skip_source_filter = False
                current_groupbox = self.dockwidget.current_exploring_groupbox
                
                if task_name == 'filter':
                    if current_groupbox == "custom_selection":
                        # L'expression validée est vide si l'expression originale n'était pas un filtre
                        # (car _build_common_task_params la vide si pas d'opérateurs de comparaison)
                        validated_expr = task_parameters["task"].get("expression", "")
                        if not validated_expr or not validated_expr.strip():
                            skip_source_filter = True
                            logger.info(f"FilterMate: Custom selection with non-filter expression '{expression}' - will use ALL features from source layer")
                    # single_selection et multiple_selection: la couche source EST filtrée
                    # en utilisant l'expression construite à partir des features sélectionnées
                
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
                layers_to_export = []
                for key in self.dockwidget.project_props["EXPORTING"]["LAYERS_TO_EXPORT"]:
                    if key in self.PROJECT_LAYERS:
                        layers_to_export.append(self.PROJECT_LAYERS[key]["infos"])
                    else:
                        # FIX: Handle layers not in PROJECT_LAYERS but still in QGIS project
                        # This can happen for PostgreSQL layers that weren't added to FilterMate
                        layer = self.PROJECT.mapLayer(key)
                        if layer and isinstance(layer, QgsVectorLayer) and layer.isValid():
                            # Convert geometry type to string
                            geom_type_map = {0: 'GeometryType.Point', 1: 'GeometryType.Line', 
                                           2: 'GeometryType.Polygon', 3: 'GeometryType.Unknown', 4: 'GeometryType.Null'}
                            geom_type_str = geom_type_map.get(layer.geometryType(), 'GeometryType.Unknown')
                            
                            # Build minimal layer info for export
                            layer_info = {
                                "layer_id": layer.id(),
                                "layer_name": layer.name(),
                                "layer_crs_authid": layer.crs().authid(),
                                "layer_geometry_type": geom_type_str,
                                "layer_provider_type": detect_layer_provider_type(layer),
                                "layer_table_name": layer.name(),  # Fallback
                                "layer_schema": "",
                                "layer_geometry_field": layer.dataProvider().geometryColumn() if hasattr(layer.dataProvider(), 'geometryColumn') else "geometry"
                            }
                            layers_to_export.append(layer_info)
                            logger.info(f"Export: Added layer '{layer.name()}' not in PROJECT_LAYERS")
                
                task_parameters["task"] = self.dockwidget.project_props
                task_parameters["task"]["layers"] = layers_to_export
                task_parameters["task"]["session_id"] = self.session_id  # For multi-client isolation
                return task_parameters
            
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
        
        For Spatialite/OGR layers, adds a brief stabilization delay before refresh
        to allow SQLite connections to fully close. This prevents transient 
        "unable to open database file" errors during concurrent access.
        
        Uses GdalErrorHandler to suppress transient GDAL warnings during refresh.
        
        v2.6.5: PERFORMANCE FIX - Skip updateExtents() for large layers to prevent freeze.
        v2.6.7: FREEZE FIX - Replace blocking time.sleep() with non-blocking QTimer.
        
        Args:
            source_layer (QgsVectorLayer): Layer to refresh
        """
        from qgis.PyQt.QtCore import QTimer
        
        # Check if layer is Spatialite or OGR (local file-based SQLite)
        provider_type = source_layer.providerType() if source_layer else None
        needs_stabilization = provider_type in ('spatialite', 'ogr')
        
        def do_refresh():
            """Perform the actual layer refresh (called immediately or after delay)."""
            try:
                # Use GDAL error handler to suppress transient SQLite warnings during refresh
                with GdalErrorHandler():
                    # v2.6.5: Skip updateExtents for large layers to prevent freeze
                    # v2.7.6: Use configurable threshold
                    thresholds = get_optimization_thresholds(ENV_VARS)
                    MAX_FEATURES_FOR_UPDATE_EXTENTS = thresholds['update_extents_threshold']
                    feature_count = source_layer.featureCount() if source_layer else 0
                    if feature_count >= 0 and feature_count < MAX_FEATURES_FOR_UPDATE_EXTENTS:
                        source_layer.updateExtents()
                    # else: skip expensive updateExtents for very large layers
                    source_layer.triggerRepaint()
                    # v2.6.7: Skip refreshAllLayers() - individual layer repaint is sufficient
                    # This avoids redundant refresh when finished() already handles canvas refresh
                    self.iface.mapCanvas().refresh()
            except Exception as e:
                logger.warning(f"_refresh_layers_and_canvas: refresh failed: {e}")
        
        if needs_stabilization:
            # v2.6.7: NON-BLOCKING stabilization delay using QTimer
            # This prevents UI freeze while allowing SQLite connections to settle
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
            # Legacy fallback - should not happen in normal operation
            logger.warning("FilterMate: UndoRedoHandler not available, undo skipped")
    
    def handle_redo(self):
        """
        Handle redo operation with intelligent layer selection logic.
        
        v4.0: Delegated to UndoRedoHandler for God Class reduction.
        
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
            # Legacy fallback - should not happen in normal operation
            logger.warning("FilterMate: UndoRedoHandler not available, redo skipped")
    
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

        if task_name not in ('filter', 'unfilter', 'reset'):
            return
        
        # v2.9.19: Clear Spatialite cache for all affected layers when unfiltering/resetting
        # This ensures the multi-step cache doesn't interfere with subsequent filter operations
        if task_name in ('unfilter', 'reset'):
            try:
                from infrastructure.cache import get_cache
                cache = get_cache()
                # Clear cache for source layer
                cache.clear_layer_cache(source_layer.id())
                logger.info(f"FilterMate: Cleared Spatialite cache for source layer {source_layer.name()}")
                
                # Clear cache for all associated layers
                # FIX v2.9.24: layers_list contains dicts with 'layer_id', not layer objects
                layers_list = task_parameters.get("task", {}).get("layers", [])
                for lyr_info in layers_list:
                    if isinstance(lyr_info, dict) and 'layer_id' in lyr_info:
                        layer_id = lyr_info['layer_id']
                        layer_name = lyr_info.get('layer_name', layer_id[:8])
                        cache.clear_layer_cache(layer_id)
                        logger.info(f"FilterMate: Cleared Spatialite cache for layer {layer_name}")
            except Exception as e:
                logger.debug(f"Could not clear Spatialite cache: {e}")
        
        # Refresh layers and map canvas
        self._refresh_layers_and_canvas(source_layer)
        
        # Get task metadata
        feature_count = source_layer.featureCount()
        provider_type = task_parameters["infos"].get("layer_provider_type", "unknown")
        layer_count = len(task_parameters.get("task", {}).get("layers", [])) + 1
        
        # v2.4.13: Use actual backend for success message (not just requested provider type)
        # This ensures the message reflects what backend was really used (e.g., OGR fallback)
        actual_backends = task_parameters.get('actual_backends', {})
        
        # Determine display_backend from actual_backends dictionary
        # Priority: if any layer used 'ogr', show 'ogr' (it means fallback was used)
        if actual_backends:
            backends_used = set(actual_backends.values())
            if 'ogr' in backends_used:
                # OGR fallback was used for at least one layer
                display_backend = 'ogr'
            else:
                # Use the first backend found (they should all be the same)
                display_backend = next(iter(actual_backends.values()))
        else:
            # No actual_backends recorded, fallback to requested provider_type
            display_backend = provider_type
        
        # Handle filter history based on task type
        if task_name == 'filter':
            self._push_filter_to_history(source_layer, task_parameters, feature_count, provider_type, layer_count)
        elif task_name == 'reset':
            self._clear_filter_history(source_layer, task_parameters)
        
        # Update undo/redo button states
        self.update_undo_redo_buttons()
        
        # Show success message with actual backend used
        # Check if OGR was used as fallback (provider requested spatialite/postgresql but got ogr)
        is_fallback = (display_backend == 'ogr' and provider_type != 'ogr')
        self._show_task_completion_message(task_name, source_layer, display_backend, layer_count, is_fallback=is_fallback)
        
        # Update backend indicator with actual backend used
        # v2.9.25: Pass is_fallback flag to show "Spatialite*" when OGR fallback was used
        if hasattr(self.dockwidget, '_update_backend_indicator'):
            if actual_backends:
                # Get PostgreSQL connection status
                postgresql_conn = task_parameters.get('infos', {}).get('postgresql_connection_available')
                # v2.9.25: If fallback was used, show the original provider with fallback indicator
                if is_fallback:
                    # Show original provider type with fallback flag
                    self.dockwidget._update_backend_indicator(
                        provider_type, postgresql_conn, 
                        actual_backend=f"{provider_type}_fallback"
                    )
                else:
                    self.dockwidget._update_backend_indicator(provider_type, postgresql_conn, display_backend)
        
        # Zoom to filtered extent only if is_tracking (auto extent) is enabled in exploring
        # Check if is_tracking is enabled for this layer
        is_tracking_enabled = False
        if source_layer.id() in self.PROJECT_LAYERS:
            layer_props = self.PROJECT_LAYERS[source_layer.id()]
            is_tracking_enabled = layer_props.get("exploring", {}).get("is_tracking", False)
        
        if is_tracking_enabled:
            # IMPROVED: Use actual filtered extent instead of cached layer extent
            source_layer.updateExtents()  # Force recalculation after filter
            
            # Use dockwidget helper if available, otherwise calculate directly
            if hasattr(self.dockwidget, 'get_filtered_layer_extent'):
                extent = self.dockwidget.get_filtered_layer_extent(source_layer)
            else:
                extent = source_layer.extent()
                
            if extent and not extent.isEmpty():
                self.iface.mapCanvas().zoomToFeatureExtent(extent)
                logger.debug(f"Auto-zoom to filtered extent enabled (is_tracking=True)")
            else:
                self.iface.mapCanvas().refresh()
        else:
            # Just refresh the canvas without zooming
            self.iface.mapCanvas().refresh()
            
        self.dockwidget.PROJECT_LAYERS = self.PROJECT_LAYERS
        
        # v2.9.19: CRITICAL - Restore EXACT same current_layer that was active BEFORE filtering
        # The combobox must show the SAME layer before and after filtering - NEVER change
        restored_layer = None
        if hasattr(self, '_current_layer_id_before_filter') and self._current_layer_id_before_filter:
            from qgis.core import QgsProject
            restored_layer = QgsProject.instance().mapLayer(self._current_layer_id_before_filter)
            if restored_layer and restored_layer.isValid():
                self.dockwidget.current_layer = restored_layer
                logger.info(f"v2.9.19: ✅ Restored current_layer to '{restored_layer.name()}' (same as before filtering)")
            else:
                logger.warning(f"v2.9.19: ⚠️ Could not restore layer ID {self._current_layer_id_before_filter} - layer no longer exists")
                # Fallback: try to find ANY valid layer
                self.dockwidget.current_layer = self.dockwidget._ensure_valid_current_layer(None)
                if self.dockwidget.current_layer:
                    logger.info(f"v2.9.19: ⚠️ Fallback: selected '{self.dockwidget.current_layer.name()}' as current_layer")
        else:
            logger.warning("v2.9.19: ⚠️ No saved current_layer to restore - searching for valid layer")
            # Fallback: ensure we have SOME valid layer if layers exist
            if not self.dockwidget.current_layer and len(self.PROJECT_LAYERS) > 0:
                self.dockwidget.current_layer = self.dockwidget._ensure_valid_current_layer(None)
                if self.dockwidget.current_layer:
                    logger.info(f"v2.9.19: ⚠️ Auto-selected '{self.dockwidget.current_layer.name()}' as current_layer")
        
        # v2.8.15: CRITICAL FIX - Ensure current_layer combo and exploring panel stay synchronized after filtering
        # v2.8.16: Extended to ALL backends (not just OGR) - Spatialite/PostgreSQL can also cause combobox reset
        # Any backend can cause the combobox to reset to None and exploring widgets to not refresh properly
        # This is because layers may reload their data provider after filtering, invalidating widget references
        # v2.9.19: CRITICAL - finally block MUST be outside the if to guarantee execution
        # v3.0.10: Use restored_layer directly to avoid issues if current_layer is modified by async signals
        target_layer = restored_layer if restored_layer and restored_layer.isValid() else self.dockwidget.current_layer
        try:
            if target_layer:
                # 1. Ensure combobox still shows the current layer (CRITICAL for UX)
                # v2.9.19: This should now be the EXACT same layer as before filtering
                current_combo_layer = self.dockwidget.comboBox_filtering_current_layer.currentLayer()
                if not current_combo_layer or current_combo_layer.id() != target_layer.id():
                    logger.info(f"v2.9.19: 🔄 Combobox reset detected - restoring to '{target_layer.name()}'")
                    # Temporarily disconnect to prevent signal during setLayer
                    self.dockwidget.manageSignal(["FILTERING", "CURRENT_LAYER"], 'disconnect')
                    self.dockwidget.comboBox_filtering_current_layer.setLayer(target_layer)
                    # Note: Don't reconnect here - let the finally block handle it for consistency
                else:
                    logger.info(f"v2.9.19: ✅ Combobox already shows correct layer '{target_layer.name()}'")
                
                # 2. Force reload of exploring widgets to refresh feature lists after filtering
                # This ensures the multiple selection widget displays the filtered features
                # v2.9.20: CRITICAL - ALWAYS reload exploring widgets, even if current_layer didn't change
                # The features have changed due to filtering, so widgets MUST be refreshed
                # v3.0.10: Use target_layer to ensure we use the saved layer, not a potentially modified current_layer
                try:
                    if target_layer.id() in self.PROJECT_LAYERS:
                        layer_props = self.PROJECT_LAYERS[target_layer.id()]
                        logger.info(f"v2.9.20: 🔄 Reloading exploring widgets for '{target_layer.name()}' after {display_backend} filter")
                        
                        # FORCE complete reload of exploring widgets with the saved layer
                        self.dockwidget._reload_exploration_widgets(target_layer, layer_props)
                        
                        # v2.9.28: CRITICAL FIX - Always restore groupbox UI state after filtering
                        # Use saved groupbox from layer_props if available, fallback to current or default
                        groupbox_to_restore = None
                        if "current_exploring_groupbox" in layer_props.get("exploring", {}):
                            groupbox_to_restore = layer_props["exploring"]["current_exploring_groupbox"]
                        if not groupbox_to_restore and hasattr(self.dockwidget, 'current_exploring_groupbox'):
                            groupbox_to_restore = self.dockwidget.current_exploring_groupbox
                        if not groupbox_to_restore:
                            groupbox_to_restore = "single_selection"  # Default fallback
                        
                        self.dockwidget._restore_groupbox_ui_state(groupbox_to_restore)
                        logger.info(f"v2.9.28: ✅ Restored groupbox UI state for '{groupbox_to_restore}'")
                        
                        # v2.9.41: CRITICAL - Update button states after filtering completes
                        # Ensures zoom/identify buttons are enabled/disabled based on current selection
                        # This is especially important for Spatialite multi-step filters where the
                        # exploring widgets have been reloaded with filtered features
                        self.dockwidget._update_exploring_buttons_state()
                        logger.info(f"v2.9.41: ✅ Updated exploring button states after {display_backend} filter")
                        
                        logger.info(f"v2.9.20: ✅ Exploring widgets reloaded successfully")
                    else:
                        logger.warning(f"v2.9.20: ⚠️ target_layer ID {target_layer.id()} not in PROJECT_LAYERS - cannot reload exploring widgets")
                except Exception as exploring_error:
                    logger.error(f"v2.9.20: ❌ Error reloading exploring widgets: {exploring_error}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                
                # 3. v2.8.16: Force explicit layer repaint to ensure canvas displays filtered features
                # All backends may require explicit triggerRepaint() on BOTH source and current layer
                # v2.9.20: Isolated try-catch to ensure this always attempts to run
                # v3.0.10: Use target_layer to ensure we repaint the correct layer
                try:
                    logger.debug(f"v2.9.20: {display_backend} filter completed - triggering layer repaint")
                    if source_layer and source_layer.isValid():
                        source_layer.triggerRepaint()
                    if target_layer.isValid():
                        target_layer.triggerRepaint()
                    # Force canvas refresh with stopRendering first to prevent conflicts
                    canvas = self.iface.mapCanvas()
                    canvas.stopRendering()
                    canvas.refresh()
                    logger.info(f"v2.9.20: ✅ Canvas repaint completed")
                except Exception as repaint_error:
                    logger.error(f"v2.9.20: ❌ Error triggering layer repaint: {repaint_error}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
            else:
                logger.warning(f"v2.9.19: ⚠️ target_layer is None after filtering - skipping UI refresh")
                    
        except (AttributeError, RuntimeError) as e:
            logger.error(f"v2.9.19: ❌ Error refreshing UI after {display_backend} filter: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
        finally:
            # v2.9.20: CRITICAL FIX - finally OUTSIDE if block to guarantee execution
            # This ensures signal reconnection happens even if current_layer is None
            if self.dockwidget:
                try:
                    # v3.0.12: CRITICAL FIX - Set time-based protection BEFORE reconnecting signals
                    # Reconnecting signals can trigger pending events that would change the combobox.
                    # The protection must be active BEFORE any signals are reconnected.
                    # This protection will be REFRESHED after the combobox is restored to ensure
                    # the 2-second window covers delayed canvas refresh timers (up to 1500ms).
                    import time
                    self.dockwidget._filter_completed_time = time.time()
                    if hasattr(self, '_current_layer_id_before_filter') and self._current_layer_id_before_filter:
                        self.dockwidget._saved_layer_id_before_filter = self._current_layer_id_before_filter
                        logger.info(f"v3.0.12: ⏱️ Initial protection set for layer '{self._current_layer_id_before_filter[:8]}...'")
                    
                    # v2.9.26: CRITICAL - Ensure combobox shows correct layer BEFORE reconnecting signal
                    # and BEFORE resetting the filtering flag
                    if hasattr(self, '_current_layer_id_before_filter') and self._current_layer_id_before_filter:
                        restored_layer = QgsProject.instance().mapLayer(self._current_layer_id_before_filter)
                        # v3.0.16: DEBUG - Log current combobox state to QGIS MessageLog
                        current_combo_layer = self.dockwidget.comboBox_filtering_current_layer.currentLayer()
                        combo_name = current_combo_layer.name() if current_combo_layer else "(None)"
                        restored_name = restored_layer.name() if restored_layer else "(None)"
                        from qgis.core import QgsMessageLog, Qgis
                        QgsMessageLog.logMessage(
                            f"v3.0.16: 🔍 Combobox state: current='{combo_name}', should_be='{restored_name}'",
                            "FilterMate", Qgis.Info
                        )
                        
                        if restored_layer and restored_layer.isValid():
                            if not current_combo_layer or current_combo_layer.id() != restored_layer.id():
                                # KEEP SIGNALS BLOCKED - don't unblock yet!
                                # We'll unblock in delayed timer after protection window
                                self.dockwidget.comboBox_filtering_current_layer.setLayer(restored_layer)
                                QgsMessageLog.logMessage(
                                    f"v3.0.19: ✅ FORCED combobox to '{restored_layer.name()}' (signals STAY BLOCKED)",
                                    "FilterMate", Qgis.Info
                                )
                                logger.info(f"v3.0.19: ✅ FINALLY - Forced combobox to '{restored_layer.name()}' (signals blocked)")
                            # v3.0.10: Also ensure current_layer is set correctly BEFORE signal reconnection
                            if self.dockwidget.current_layer is None or self.dockwidget.current_layer.id() != restored_layer.id():
                                self.dockwidget.current_layer = restored_layer
                                logger.info(f"v3.0.10: ✅ FINALLY - Ensured current_layer is '{restored_layer.name()}'")
                    
                    # v3.0.19: CRITICAL FIX - Don't reconnect signal yet!
                    # Keep it disconnected during the entire protection window (5s)
                    # We'll reconnect it in a delayed timer AFTER protection expires
                    logger.info("v3.0.19: ⏳ Keeping current_layer signal DISCONNECTED during 5s protection")
                    
                    # v2.9.27: Reconnect LAYER_TREE_VIEW signal (disconnected in manage_task)
                    # Only if the legend link option is enabled (otherwise signal was never connected)
                    if self.dockwidget.project_props.get("OPTIONS", {}).get("LAYERS", {}).get("LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG", False):
                        try:
                            self.dockwidget.manageSignal(["QGIS", "LAYER_TREE_VIEW"], 'connect')
                            logger.info("v2.9.27: ✅ FINALLY - Reconnected LAYER_TREE_VIEW signal after filtering")
                        except Exception as e:
                            logger.debug(f"Could not reconnect LAYER_TREE_VIEW signal: {e}")
                    
                    # v2.9.24: CRITICAL FIX - Force reconnect ACTION signals after filtering
                    # The signal cache can become desynchronized, causing buttons to stop working.
                    # This bypasses the cache and forces direct reconnection of ACTION signals.
                    if hasattr(self.dockwidget, 'force_reconnect_action_signals'):
                        self.dockwidget.force_reconnect_action_signals()
                    
                    # v3.0.11: CRITICAL FIX - Force reconnect EXPLORING signals after filtering
                    # The signal cache can become desynchronized, causing exploring widgets 
                    # (single selection, distant layers, etc.) to not reload on layer change.
                    # This bypasses the cache and forces direct reconnection of EXPLORING signals.
                    if hasattr(self.dockwidget, 'force_reconnect_exploring_signals'):
                        self.dockwidget.force_reconnect_exploring_signals()
                    
                    # v2.9.20: FORCE invalidation of exploring cache after filtering
                    # This ensures the panel shows fresh, filtered features
                    if hasattr(self.dockwidget, 'invalidate_exploring_cache') and self.dockwidget.current_layer:
                        self.dockwidget.invalidate_exploring_cache(self.dockwidget.current_layer.id())
                        logger.info(f"v2.9.20: ✅ Invalidated exploring cache for '{self.dockwidget.current_layer.name()}'")
                    
                    # v3.0.12: CRITICAL - Final combobox protection BEFORE resetting filtering flag
                    # The reconnected signals can trigger currentLayerChanged which may change the combobox.
                    # We MUST ensure the combobox shows the saved layer BEFORE allowing signals through.
                    if hasattr(self, '_current_layer_id_before_filter') and self._current_layer_id_before_filter:
                        final_layer = QgsProject.instance().mapLayer(self._current_layer_id_before_filter)
                        if final_layer and final_layer.isValid():
                            current_combo = self.dockwidget.comboBox_filtering_current_layer.currentLayer()
                            if not current_combo or current_combo.id() != final_layer.id():
                                # Block and restore combobox to correct layer
                                self.dockwidget.comboBox_filtering_current_layer.blockSignals(True)
                                self.dockwidget.comboBox_filtering_current_layer.setLayer(final_layer)
                                self.dockwidget.comboBox_filtering_current_layer.blockSignals(False)
                                # Also update current_layer reference in dockwidget
                                self.dockwidget.current_layer = final_layer
                                logger.info(f"v3.0.12: ✅ FINAL - Restored combobox to '{final_layer.name()}' BEFORE signal unlock")
                    
                    # v3.0.12: CRITICAL - Update protection time AFTER restoring combobox
                    # This ensures the 2-second protection window starts AFTER the combobox is correctly set.
                    # The delayed canvas refresh timers (up to 1500ms) will be blocked by this protection.
                    import time
                    self.dockwidget._filter_completed_time = time.time()
                    if hasattr(self, '_current_layer_id_before_filter') and self._current_layer_id_before_filter:
                        self.dockwidget._saved_layer_id_before_filter = self._current_layer_id_before_filter
                    logger.info(f"v3.0.12: ⏱️ Updated 2000ms protection window AFTER combobox restoration")
                    
                    # v3.0.19: CRITICAL - Schedule combobox signal reconnection AFTER protection expires
                    # Keep combobox signals BLOCKED during entire 5s protection window
                    # This prevents Qt from internally resetting the combobox when async refreshes complete
                    if hasattr(self, '_current_layer_id_before_filter') and self._current_layer_id_before_filter:
                        saved_layer_id = self._current_layer_id_before_filter
                        
                        def restore_combobox_if_needed():
                            """Check and restore combobox to saved layer if it was changed."""
                            try:
                                if not self.dockwidget:
                                    return
                                saved_layer = QgsProject.instance().mapLayer(saved_layer_id)
                                if saved_layer and saved_layer.isValid():
                                    current_combo = self.dockwidget.comboBox_filtering_current_layer.currentLayer()
                                    current_name = current_combo.name() if current_combo else "(None)"
                                    # v3.0.16: Log every check to QGIS MessageLog
                                    from qgis.core import QgsMessageLog, Qgis
                                    QgsMessageLog.logMessage(
                                        f"v3.0.19: 🔄 DELAYED CHECK - combobox='{current_name}', expected='{saved_layer.name()}'",
                                        "FilterMate", Qgis.Info
                                    )
                                    if not current_combo or current_combo.id() != saved_layer.id():
                                        logger.info(f"v3.0.19: 🔧 DELAYED CHECK - Combobox was changed, restoring to '{saved_layer.name()}'")
                                        QgsMessageLog.logMessage(
                                            f"v3.0.19: 🔧 RESTORING combobox from '{current_name}' to '{saved_layer.name()}'",
                                            "FilterMate", Qgis.Warning
                                        )
                                        # Keep signals blocked during restore
                                        self.dockwidget.comboBox_filtering_current_layer.setLayer(saved_layer)
                                        self.dockwidget.current_layer = saved_layer
                            except Exception as e:
                                logger.debug(f"v3.0.19: Error in delayed combobox check: {e}")
                        
                        def unblock_and_reconnect_combobox():
                            """Unblock combobox signals and reconnect handler AFTER protection window."""
                            try:
                                if not self.dockwidget:
                                    return
                                # Unblock Qt internal signals
                                self.dockwidget.comboBox_filtering_current_layer.blockSignals(False)
                                # Reconnect our handler
                                self.dockwidget.manageSignal(["FILTERING", "CURRENT_LAYER"], 'connect', 'layerChanged')
                                
                                # v3.0.19: CRITICAL FIX - Reset _filtering_in_progress HERE, not earlier
                                # This flag must stay True during the ENTIRE 5s protection window
                                # Otherwise current_layer_changed() will process signals during protection
                                self.dockwidget._filtering_in_progress = False
                                
                                logger.info("v3.0.19: ✅ Unblocked combobox, reconnected handler, and reset filtering flag after 5s protection")
                                from qgis.core import QgsMessageLog, Qgis
                                QgsMessageLog.logMessage(
                                    "v3.0.19: ✅ Combobox protection ENDED - signals reconnected, filtering flag reset",
                                    "FilterMate", Qgis.Info
                                )
                            except Exception as e:
                                logger.error(f"v3.0.19: Error reconnecting combobox: {e}")
                        
                        # Schedule checks during protection window (signals still blocked)
                        from qgis.PyQt.QtCore import QTimer
                        for delay in [200, 600, 1000, 1500, 2000, 2500, 3000, 4000]:
                            QTimer.singleShot(delay, restore_combobox_if_needed)
                        
                        # Unblock and reconnect AFTER 5s protection window
                        QTimer.singleShot(5100, unblock_and_reconnect_combobox)  # 5.1s to ensure protection has expired
                        
                        logger.info(f"v3.0.19: 📋 Scheduled 8 delayed checks + signal reconnection at 5.1s")
                    
                    # v3.0.19: REMOVED - Don't reset _filtering_in_progress here!
                    # It must stay True during the entire 5s protection window.
                    # It will be reset in unblock_and_reconnect_combobox() at 5.1s
                    
                except Exception as reconnect_error:
                    logger.error(f"v2.9.20: ❌ Failed to reconnect layerChanged signal: {reconnect_error}")
                    
                except Exception as reconnect_error:
                    logger.error(f"v2.9.20: ❌ Failed to reconnect layerChanged signal: {reconnect_error}")
                    # v2.9.25: Reset flag even on error
                    self.dockwidget._filtering_in_progress = False
        
        # v2.8.13: CRITICAL - Invalidate expression cache after filtering
        # When a layer's subsetString changes, cached expression results become stale.
        # This is essential for multi-step filtering: Step 2 must re-evaluate expressions
        # on the filtered features from Step 1, not use cached results from before filtering.
        if hasattr(self.dockwidget, 'invalidate_expression_cache'):
            # Invalidate cache for all layers that were filtered (their subsetString changed)
            affected_layer_ids = []
            if source_layer:
                affected_layer_ids.append(source_layer.id())
            # Also include all distant layers from task_parameters
            # FIX v2.9.24: distant_layers contains dicts with 'layer_id', not layer objects
            distant_layers = task_parameters.get("task", {}).get("layers", [])
            for dl in distant_layers:
                if isinstance(dl, dict) and 'layer_id' in dl:
                    affected_layer_ids.append(dl['layer_id'])
            
            for layer_id in affected_layer_ids:
                self.dockwidget.invalidate_expression_cache(layer_id)
                logger.debug(f"v2.8.13: Invalidated expression cache for layer {layer_id}")


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
        # Guard invalid/missing-source layers
        if not is_layer_source_available(layer):
            logger.warning("create_spatial_index_for_layer: layer invalid or source missing; skipping.")
            iface.messageBar().pushWarning(
                "FilterMate",
                "Impossible de créer un index spatial: couche invalide ou source introuvable."
            )
            return

        alg_params_createspatialindex = {
            "INPUT": layer
        }
        processing.run('qgis:createspatialindex', alg_params_createspatialindex)
    
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
        
        Args:
            layer: PostgreSQL layer to get connection from
        """
        connexion, source_uri = get_datasource_connexion_from_layer(layer)
        
        # CRITICAL FIX: Check if connexion is None (PostgreSQL unavailable or connection failed)
        if connexion is None:
            logger.warning(f"Cannot add project datasource for layer {layer.name()}: no database connection")
            return

        try:
            sql_statement = 'CREATE SCHEMA IF NOT EXISTS {app_temp_schema} AUTHORIZATION postgres;'.format(app_temp_schema=self.app_postgresql_temp_schema)
            logger.debug(f"SQL statement: {sql_statement}")

            with connexion.cursor() as cursor:
                cursor.execute(sql_statement)
            connexion.commit()
        except Exception as e:
            logger.warning(f"Error creating temp schema for layer {layer.name()}: {e}")
        finally:
            try:
                connexion.close()
            except (OSError, AttributeError) as e:
                logger.debug(f"Could not close connection: {e}")



            
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
        
        Called when LayersManagementEngineTask completes. Updates internal layer registry,
        refreshes UI, and handles layer addition/removal cleanup.
        
        Args:
            result_project_layers (dict): Updated PROJECT_LAYERS dictionary with all layer metadata
            task_name (str): Type of task completed (add_layers, remove_layers, etc.)
            
        Notes:
            - Updates dockwidget PROJECT_LAYERS reference
            - Calls get_project_layers_from_app() to refresh UI
            - Handles special cases for layer removal and project reset
            - Updates layer comboboxes and enables/disables controls
            - Reconnects widget signals after changes
        """
        logger.info(f"layer_management_engine_task_completed called: task_name={task_name}, result_project_layers count={len(result_project_layers) if result_project_layers else 0}")
        
        init_env_vars()

        global ENV_VARS

        # CRITICAL: Validate and update PROJECT_LAYERS before UI refresh
        # This ensures layer IDs are synchronized before dockwidget accesses them
        if result_project_layers is None:
            logger.error("layer_management_engine_task_completed received None for result_project_layers")
            return
        
        self.PROJECT_LAYERS = result_project_layers
        self.PROJECT = ENV_VARS["PROJECT"]
        
        logger.debug(f"Updated PROJECT_LAYERS with {len(self.PROJECT_LAYERS)} layers after {task_name}")
        
        ENV_VARS["PATH_ABSOLUTE_PROJECT"] = os.path.normpath(self.PROJECT.readPath("./"))
        if ENV_VARS["PATH_ABSOLUTE_PROJECT"] =='./':
            if ENV_VARS["PLATFORM"].startswith('win'):
                ENV_VARS["PATH_ABSOLUTE_PROJECT"] =  os.path.normpath(os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop'))
            else:
                ENV_VARS["PATH_ABSOLUTE_PROJECT"] =  os.path.normpath(os.environ['HOME'])

        if self.dockwidget is not None:

            conn = self.get_spatialite_connection()
            if conn is None:
                # Even if DB connection fails, we must update the UI
                self.dockwidget.get_project_layers_from_app(self.PROJECT_LAYERS, self.PROJECT)
                return
            cur = conn.cursor()

            try:
                if task_name in ("add_layers","remove_layers","remove_all_layers"):
                    if task_name == 'add_layers':
                        for layer_key in self.PROJECT_LAYERS.keys():
                            if layer_key not in self.dockwidget.PROJECT_LAYERS.keys():
                                try:
                                    self.dockwidget.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].remove_list_widget(layer_key)
                                except (KeyError, AttributeError, RuntimeError):
                                    pass

                            # Validate and update datasource
                            layer_info = self._validate_layer_info(layer_key)
                            if layer_info:
                                self._update_datasource_for_layer(layer_info)
                                

                    else:
                        # Handle layer removal
                        for layer_key in self.dockwidget.PROJECT_LAYERS.keys():
                            if layer_key not in self.PROJECT_LAYERS.keys():
                                # Layer removed - clean up database
                                cur.execute("""DELETE FROM fm_project_layers_properties 
                                                WHERE fk_project = '{project_id}' and layer_id = '{layer_id}';""".format(
                                                    project_id=self.project_uuid,
                                                    layer_id=layer_key
                                                ))
                                conn.commit()
                                
                                # Clean up history for removed layer
                                self.history_manager.remove_history(layer_key)
                                logger.info(f"FilterMate: Removed history for deleted layer {layer_key}")
                                
                                try:
                                    self.dockwidget.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].remove_list_widget(layer_key)
                                except (KeyError, AttributeError, RuntimeError):
                                    pass
                            else:
                                # Update datasource for remaining layers
                                layer_info = self._validate_layer_info(layer_key)
                                if layer_info:
                                    self._remove_datasource_for_layer(layer_info)
                    
                    
                    self.save_project_variables()                    
                    self.dockwidget.get_project_layers_from_app(self.PROJECT_LAYERS, self.PROJECT)

                self.MapLayerStore = self.PROJECT.layerStore()
                self.update_datasource()
                logger.debug(f"Project datasources: {self.project_datasources}")
            finally:
                # STABILITY FIX: Ensure DB connection is always closed
                try:
                    cur.close()
                except Exception:
                    pass
                try:
                    conn.close()
                except Exception:
                    pass
            
            # STABILITY FIX: Decrement add_layers task counter and process queue
            if task_name == 'add_layers':
                if self._pending_add_layers_tasks > 0:
                    self._pending_add_layers_tasks -= 1
                    logger.debug(f"Completed add_layers task (remaining: {self._pending_add_layers_tasks})")
                
                # PERFORMANCE v2.6.0: Warm query cache for loaded layers
                self._warm_query_cache_for_layers()
                
                # Process next queued operation if any
                if self._add_layers_queue and self._pending_add_layers_tasks == 0:
                    logger.info(f"Processing {len(self._add_layers_queue)} queued add_layers operations")
                    # STABILITY FIX: Use weakref to prevent access violations
                    weak_self = weakref.ref(self)
                    def safe_process_queue_on_complete():
                        strong_self = weak_self()
                        if strong_self is not None:
                            strong_self._process_add_layers_queue()
                    QTimer.singleShot(STABILITY_CONSTANTS['SIGNAL_DEBOUNCE_MS'], safe_process_queue_on_complete)
            
            # If we're loading a new project, force UI refresh after add_layers completes
            if task_name == 'add_layers' and self._loading_new_project:
                logger.info("New project loaded - forcing UI refresh")
                self._set_loading_flag(False)  # Use timestamp-tracked flag
                if self.dockwidget is not None and self.dockwidget.widgets_initialized:
                    # STABILITY FIX: Use weakref to prevent access violations
                    weak_self = weakref.ref(self)
                    def safe_ui_refresh():
                        strong_self = weak_self()
                        if strong_self is not None:
                            strong_self._refresh_ui_after_project_load()
                    QTimer.singleShot(STABILITY_CONSTANTS['UI_REFRESH_DELAY_MS'], safe_ui_refresh)
    
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
        """Update project datasources for a given layer.
        
        Args:
            layer_info: Layer info dictionary
        """
        layer_source_type = layer_info["layer_provider_type"]
        if layer_source_type not in self.project_datasources:
            self.project_datasources[layer_source_type] = {}
        
        layers = [layer for layer in self.PROJECT.mapLayersByName(layer_info["layer_name"]) 
                 if layer.id() == layer_info["layer_id"]]
        
        if len(layers) != 1:
            return
        
        layer = layers[0]
        source_uri, authcfg_id = get_data_source_uri(layer)
        
        if authcfg_id is not None:
            if authcfg_id not in self.project_datasources[layer_source_type].keys():
                connexion, source_uri = get_datasource_connexion_from_layer(layer)
                self.project_datasources[layer_source_type][authcfg_id] = connexion
        else:
            uri = source_uri.uri().strip()
            relative_path = uri.split('|')[0] if len(uri.split('|')) == 2 else uri
            layer_name = uri.split('|')[1] if len(uri.split('|')) == 2 else None
            absolute_path = os.path.join(os.path.normpath(ENV_VARS["PATH_ABSOLUTE_PROJECT"]), 
                                        os.path.normpath(relative_path))
            
            if absolute_path not in self.project_datasources[layer_source_type].keys():
                self.project_datasources[layer_source_type][absolute_path] = []
            
            if uri not in self.project_datasources[layer_source_type][absolute_path]:
                full_uri = absolute_path + ('|' + layer_name if layer_name is not None else '')
                self.project_datasources[layer_source_type][absolute_path].append(full_uri)
    
    def _remove_datasource_for_layer(self, layer_info):
        """Remove project datasources for a given layer.
        
        Args:
            layer_info: Layer info dictionary
        """
        layer_source_type = layer_info["layer_provider_type"]
        if layer_source_type not in self.project_datasources:
            self.project_datasources[layer_source_type] = {}
        
        layers = [layer for layer in self.PROJECT.mapLayersByName(layer_info["layer_name"]) 
                 if layer.id() == layer_info["layer_id"]]
        
        if len(layers) != 1:
            return
        
        layer = layers[0]
        source_uri, authcfg_id = get_data_source_uri(layer)
        
        if authcfg_id is not None:
            if authcfg_id not in self.project_datasources[layer_source_type].keys():
                connexion, source_uri = get_datasource_connexion_from_layer(layer)
                self.project_datasources[layer_source_type][authcfg_id] = connexion
        else:
            uri = source_uri.uri().strip()
            relative_path = uri.split('|')[0] if len(uri.split('|')) == 2 else uri
            absolute_path = os.path.normpath(os.path.join(ENV_VARS["PATH_ABSOLUTE_PROJECT"], relative_path))
            
            if absolute_path in self.project_datasources[layer_source_type].keys():
                if uri in self.project_datasources[layer_source_type][absolute_path]:
                    self.project_datasources[layer_source_type][absolute_path].remove(uri)
    
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
        # POSTGRESQL_AVAILABLE est maintenant importé au niveau du module
        ogr_driver_list = [ogr.GetDriver(i).GetDescription() for i in range(ogr.GetDriverCount())]
        ogr_driver_list.sort()
        logger.debug(f"OGR drivers available: {ogr_driver_list}")

        # Vérifier si PostgreSQL est disponible et s'il y a des connexions PostgreSQL
        if 'postgresql' in self.project_datasources and POSTGRESQL_AVAILABLE:
            list(self.project_datasources['postgresql'].keys())
            if len(self.project_datasources['postgresql']) >= 1:
                postgresql_connexions = list(self.project_datasources['postgresql'].keys())
                # FIXED: Check if ACTIVE_POSTGRESQL is a valid connection object, not just empty string
                # The config may have been loaded from JSON with a string value (connection info)
                # We need to ensure ACTIVE_POSTGRESQL is an actual psycopg2 connection object
                current_connection = self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"]
                is_valid_connection = (
                    current_connection is not None 
                    and not isinstance(current_connection, str)
                    and hasattr(current_connection, 'cursor')
                    and callable(getattr(current_connection, 'cursor', None))
                    and not getattr(current_connection, 'closed', True)
                )
                if not is_valid_connection:
                    # Assign fresh connection object from project_datasources
                    self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"] = self.project_datasources['postgresql'][postgresql_connexions[0]]
                    self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["IS_ACTIVE_POSTGRESQL"] = True
                    logger.debug("Assigned fresh PostgreSQL connection object to ACTIVE_POSTGRESQL")
            else:
                self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"] = ""
                self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["IS_ACTIVE_POSTGRESQL"] = False
        elif 'postgresql' in self.project_datasources and not POSTGRESQL_AVAILABLE:
            # PostgreSQL layers detected but psycopg2 not available
            self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"] = ""
            self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["IS_ACTIVE_POSTGRESQL"] = False
            self.iface.messageBar().pushWarning(
                "FilterMate",
                "PostgreSQL layers detected but psycopg2 is not installed. "
                "Using local Spatialite backend. "
                "For better performance with large datasets, install psycopg2."
            )
        else:
            self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"] = ""
            self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["IS_ACTIVE_POSTGRESQL"] = False

        for current_datasource in list(self.project_datasources.keys()):
            if current_datasource != "postgresql":
                for project_datasource in self.project_datasources[current_datasource].keys():
                    datasources = self.project_datasources[current_datasource][project_datasource]
                    for datasource in datasources:
                        # Extract file extension safely
                        datasource_path = datasource.split('|')[0]
                        path_parts = datasource_path.split('.')
                        # Check if there's an extension (at least 2 parts after split)
                        datasource_ext = path_parts[-1] if len(path_parts) >= 2 else datasource_path
                        datasource_type_name = [ogr_name for ogr_name in ogr_driver_list if ogr_name.upper() == datasource_ext.upper()]

                    if self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["IS_ACTIVE_POSTGRESQL"] is True:
                        self.create_foreign_data_wrapper(project_datasource, os.path.basename(project_datasource), datasource_type_name[0])
                        




    def create_foreign_data_wrapper(self, project_datasource, datasource, format):

        sql_request = """CREATE EXTENSION IF NOT EXISTS ogr_fdw;
                        CREATE SCHEMA IF NOT EXISTS filter_mate_temp AUTHORIZATION postgres; 
                        DROP SERVER IF exists server_{datasource_name}  CASCADE;
                        CREATE SERVER server_{datasource_name} 
                        FOREIGN DATA WRAPPER ogr_fdw OPTIONS (
                            datasource '{datasource}', 
                            format '{format}');
                        IMPORT FOREIGN SCHEMA ogr_all
                        FROM SERVER server_{datasource_name} INTO filter_mate_temp;""".format(datasource_name=sanitize_sql_identifier(datasource),
                                                                                        datasource=project_datasource.replace('\\\\', '\\'),
                                                                                        format=format)

        if self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["IS_ACTIVE_POSTGRESQL"] is True:
            connexion = self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"]
            # Validate that connexion is actually a connection object, not a string
            if connexion is None or isinstance(connexion, str):
                logger.warning("ACTIVE_POSTGRESQL is not a valid connection object, skipping foreign data wrapper creation")
                return
            try:
                with connexion.cursor() as cursor:
                    cursor.execute(sql_request)
            except Exception as e:
                logger.error(f"Failed to create foreign data wrapper: {e}")


def zoom_to_features(layer, t0):
    canvas = iface.mapCanvas()
    canvas.setExtent(layer.extent())
    canvas.refresh()

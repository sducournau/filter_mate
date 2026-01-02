from qgis.PyQt.QtCore import Qt, QTimer
import weakref
import sip
from qgis.PyQt.QtWidgets import QApplication, QPushButton, QProgressBar
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsAuthMethodConfig,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransformContext,
    QgsDataSourceUri,
    QgsExpression,
    QgsExpressionContextUtils,
    QgsProject,
    QgsTask,
    QgsVectorFileWriter,
    QgsVectorLayer
)
from qgis.gui import QgsCheckableComboBox, QgsFeatureListComboBox, QgsFieldExpressionWidget
from qgis.utils import iface
from qgis import processing
from osgeo import ogr

from collections import OrderedDict
from operator import getitem
import zipfile
import os.path
from pathlib import Path
from shutil import copyfile
import re
import logging
from .config.config import ENV_VARS, init_env_vars
from functools import partial
import json
from .modules.customExceptions import (
    FilterMateException,
    LayerNotFoundError,
    InvalidExpressionError
)
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
)
from .modules.type_utils import can_cast, return_typed_value
from .modules.feedback_utils import (
    show_backend_info, show_progress_message, show_success_with_backend,
    show_performance_warning, show_error_with_context
)
from .modules.filter_history import HistoryManager
from .modules.filter_favorites import FavoritesManager
from .modules.ui_config import UIConfig, DisplayProfile
from .modules.object_safety import (
    is_sip_deleted, is_valid_layer, is_valid_qobject, is_qgis_alive,
    safe_disconnect, safe_emit, make_safe_callback,
    safe_set_layer_variable,  # CRASH FIX v2.4.14: Use safe wrapper instead of direct call
    GdalErrorHandler,  # v2.3.12: Suppress transient GDAL warnings during refresh
    require_valid_layer  # STABILITY v2.6.0: Decorator for layer validation
)
# STABILITY v2.6.0: Circuit breaker for PostgreSQL connection protection
from .modules.circuit_breaker import (
    get_postgresql_breaker,
    CircuitOpenError
)
from .modules.logging_config import get_app_logger
from .resources import *  # Qt resources must be imported with wildcard
import uuid

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

    def _filter_usable_layers(self, layers):
        """
        Return only layers that are valid vector layers with available sources.
        
        STABILITY FIX v2.3.9: Uses is_valid_layer() from object_safety module
        to prevent access violations from deleted C++ objects.
        """
        try:
            input_count = len(layers or [])
            usable = []
            filtered_reasons = []
            
            logger.info(f"_filter_usable_layers: Processing {input_count} layers (POSTGRESQL_AVAILABLE={POSTGRESQL_AVAILABLE})")
            
            for l in (layers or []):
                # CRITICAL: Check if C++ object was deleted before any access
                if is_sip_deleted(l):
                    filtered_reasons.append("unknown: C++ object deleted")
                    continue
                    
                if not isinstance(l, QgsVectorLayer):
                    try:
                        name = l.name() if hasattr(l, 'name') else 'unknown'
                    except RuntimeError:
                        name = 'unknown'
                    filtered_reasons.append(f"{name}: not a vector layer")
                    continue
                
                # Use object_safety module for comprehensive validation
                if not is_valid_layer(l):
                    try:
                        name = l.name()
                    except RuntimeError:
                        name = 'unknown'
                    filtered_reasons.append(f"{name}: invalid layer (C++ object may be deleted)")
                    continue
                
                # IMPORTANT: For layer loading, we don't require psycopg2 to be available
                # because the layer list should include all layers, even if some features
                # (like filtering with PostgreSQL backend) won't work.
                # Export uses QGIS API, not psycopg2 directly.
                if not is_layer_source_available(l, require_psycopg2=False):
                    filtered_reasons.append(f"{l.name()}: source not available (provider={l.providerType()})")
                    continue
                usable.append(l)
            
            if filtered_reasons and input_count != len(usable):
                logger.info(f"_filter_usable_layers: {input_count} input layers -> {len(usable)} usable layers. Filtered: {len(filtered_reasons)}")
                for reason in filtered_reasons:
                    logger.info(f"  Filtered: {reason}")
            else:
                logger.info(f"_filter_usable_layers: All {input_count} layers are usable")
            
            return usable
        except Exception as e:
            logger.error(f"_filter_usable_layers error: {e}", exc_info=True)
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
            
            iface.messageBar().pushWarning(
                "FilterMate",
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
        
        if filtered:
            self.manage_task('add_layers', filtered)
        
        # FIX: Schedule retry for PostgreSQL layers that may become valid after connection is established
        if postgres_pending:
            logger.info(f"FilterMate: {len(postgres_pending)} PostgreSQL layers pending - scheduling retry")
            weak_self = weakref.ref(self)
            captured_pending = postgres_pending
            
            def retry_postgres():
                strong_self = weak_self()
                if strong_self is None:
                    return
                
                now_valid = []
                for layer in captured_pending:
                    try:
                        if not is_sip_deleted(layer) and layer.isValid() and layer.id() not in strong_self.PROJECT_LAYERS:
                            now_valid.append(layer)
                            logger.info(f"PostgreSQL layer '{layer.name()}' is now valid (retry)")
                    except (RuntimeError, AttributeError):
                        pass
                
                if now_valid:
                    logger.info(f"FilterMate: Adding {len(now_valid)} PostgreSQL layers after retry")
                    strong_self.manage_task('add_layers', now_valid)
            
            # Retry after PostgreSQL connection establishment delay
            QTimer.singleShot(STABILITY_CONSTANTS['POSTGRESQL_EXTRA_DELAY_MS'], retry_postgres)

    def cleanup(self):
        """
        Clean up plugin resources on unload or reload.
        
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
        # Clean up PostgreSQL materialized views for this session (if auto-cleanup is enabled)
        auto_cleanup_enabled = True  # Default to enabled
        if self.dockwidget and hasattr(self.dockwidget, '_pg_auto_cleanup_enabled'):
            auto_cleanup_enabled = self.dockwidget._pg_auto_cleanup_enabled
        
        if auto_cleanup_enabled:
            self._cleanup_postgresql_session_views()
        else:
            logger.info("PostgreSQL auto-cleanup disabled - session views not cleaned")
        
        if self.dockwidget is not None:
            # Nettoyer tous les widgets list_widgets pour éviter les KeyError
            if hasattr(self.dockwidget, 'widgets'):
                try:
                    multiple_selection_widget = self.dockwidget.widgets.get("EXPLORING", {}).get("MULTIPLE_SELECTION_FEATURES", {}).get("WIDGET")
                    if multiple_selection_widget and hasattr(multiple_selection_widget, 'list_widgets'):
                        # Nettoyer tous les list_widgets
                        multiple_selection_widget.list_widgets.clear()
                        # Réinitialiser les tasks
                        if hasattr(multiple_selection_widget, 'tasks'):
                            multiple_selection_widget.tasks.clear()
                except (KeyError, AttributeError, RuntimeError) as e:
                    # Les widgets peuvent déjà être supprimés
                    pass
            
            # Nettoyer PROJECT_LAYERS
            if hasattr(self.dockwidget, 'PROJECT_LAYERS'):
                self.dockwidget.PROJECT_LAYERS.clear()
        
        # Réinitialiser les structures de données de l'app
        self.PROJECT_LAYERS.clear()
        self.project_datasources.clear()


    def _cleanup_postgresql_session_views(self):
        """
        Clean up all PostgreSQL materialized views created by this session.
        
        Drops all materialized views and indexes prefixed with the session_id
        to prevent accumulation of orphaned views in the database.
        
        This is called during cleanup() when the plugin is unloaded.
        
        Uses circuit breaker pattern to prevent cascading failures if
        PostgreSQL connection is unstable.
        """
        if not POSTGRESQL_AVAILABLE:
            return
        
        if not hasattr(self, 'session_id') or not self.session_id:
            return
        
        # STABILITY v2.6.0: Check circuit breaker before attempting PostgreSQL operations
        pg_breaker = get_postgresql_breaker()
        if pg_breaker.is_open:
            logger.debug("Skipping PostgreSQL cleanup - circuit breaker is OPEN")
            return
        
        schema = self.app_postgresql_temp_schema
        
        # Try to get a PostgreSQL connection from any loaded layer
        try:
            from .modules.appUtils import get_datasource_connexion_from_layer
            
            # Find a PostgreSQL layer to get connection
            connexion = None
            for layer_id, layer_info in self.PROJECT_LAYERS.items():
                layer = layer_info.get('layer')
                if layer and layer.isValid() and layer.providerType() == 'postgres':
                    connexion, _ = get_datasource_connexion_from_layer(layer)
                    if connexion:
                        break
            
            if not connexion:
                logger.debug("No PostgreSQL connection available for session cleanup")
                return
            
            try:
                with connexion.cursor() as cursor:
                    # Find all materialized views for this session
                    cursor.execute("""
                        SELECT matviewname FROM pg_matviews 
                        WHERE schemaname = %s AND matviewname LIKE %s
                    """, (schema, f"mv_{self.session_id}_%"))
                    views = cursor.fetchall()
                    
                    if views:
                        count = 0
                        for (view_name,) in views:
                            try:
                                # Drop associated index first
                                index_name = f"{schema}_{view_name[3:]}_cluster"  # Remove 'mv_' prefix
                                cursor.execute(f'DROP INDEX IF EXISTS "{index_name}" CASCADE;')
                                # Drop the view
                                cursor.execute(f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."{view_name}" CASCADE;')
                                count += 1
                            except Exception as e:
                                logger.debug(f"Error dropping view {view_name}: {e}")
                        
                        connexion.commit()
                        if count > 0:
                            logger.info(f"Cleaned up {count} materialized view(s) for session {self.session_id}")
                
                # STABILITY v2.6.0: Record success for circuit breaker
                pg_breaker.record_success()
            finally:
                try:
                    connexion.close()
                except:
                    pass
                    
        except CircuitOpenError:
            logger.debug("PostgreSQL cleanup skipped - circuit breaker tripped")
        except Exception as e:
            # STABILITY v2.6.0: Record failure for circuit breaker
            pg_breaker.record_failure()
            logger.debug(f"Error during PostgreSQL session cleanup: {e}")


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
        
        # Initialize filter favorites manager for saving/loading favorites
        self.favorites_manager = FavoritesManager(max_favorites=50)
        self.favorites_manager.load_from_project()
        logger.info(f"FilterMate: FavoritesManager initialized ({self.favorites_manager.count} favorites loaded)")
        
        # Log PostgreSQL availability status
        if POSTGRESQL_AVAILABLE:
            logger.info("FilterMate: PostgreSQL support enabled (psycopg2 available)")
        else:
            logger.warning(
                "FilterMate: PostgreSQL support DISABLED - psycopg2 not installed. "
                "Plugin will work with local files (Shapefile, GeoPackage, Spatialite) only. "
                "For PostgreSQL layers, install psycopg2."
            )
        
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
        
        This method is useful when the dockwidget gets out of sync with the
        current project, or when switching projects doesn't properly reload layers.
        
        Workflow:
        1. Cancel all pending tasks
        2. Reset all state flags
        3. Clear PROJECT_LAYERS
        4. Reinitialize the database
        5. Reload all vector layers from current project
        
        Can be called from UI (refresh button) or programmatically.
        """
        import time
        from qgis.PyQt.QtCore import QTimer
        from qgis.utils import iface
        
        logger.info("FilterMate: Force reload layers requested")
        
        # 1. Reset all protection flags immediately
        self._check_and_reset_stale_flags()
        self._set_loading_flag(False)
        self._set_initializing_flag(False)
        
        # 2. Cancel all pending tasks
        self._safe_cancel_all_tasks()
        
        # 3. Clear the add_layers queue
        self._add_layers_queue.clear()
        self._pending_add_layers_tasks = 0
        
        # 4. Clear PROJECT_LAYERS
        self.PROJECT_LAYERS = {}
        
        # 5. Reset dockwidget state
        if self.dockwidget:
            self.dockwidget.current_layer = None
            self.dockwidget.has_loaded_layers = False
            self.dockwidget.PROJECT_LAYERS = {}
            self.dockwidget._plugin_busy = False
            self.dockwidget._updating_layers = False
            
            # Clear combobox safely
            try:
                if hasattr(self.dockwidget, 'comboBox_filtering_current_layer'):
                    self.dockwidget.comboBox_filtering_current_layer.setLayer(None)
                    self.dockwidget.comboBox_filtering_current_layer.clear()
            except Exception as e:
                logger.debug(f"Error clearing layer combobox during reload: {e}")
            
            # Update indicator to show reloading state
            if hasattr(self.dockwidget, 'backend_indicator_label') and self.dockwidget.backend_indicator_label:
                self.dockwidget.backend_indicator_label.setText("⟳")
                self.dockwidget.backend_indicator_label.setStyleSheet("""
                    QLabel#label_backend_indicator {
                        color: #3498db;
                        font-size: 9pt;
                        font-weight: 600;
                        padding: 3px 10px;
                        border-radius: 12px;
                        border: none;
                        background-color: #e8f4fc;
                    }
                """)
        
        # 6. Update project reference
        init_env_vars()
        global ENV_VARS
        self.PROJECT = ENV_VARS["PROJECT"]
        self.MapLayerStore = self.PROJECT.layerStore()
        
        # 7. Reinitialize database
        try:
            self.init_filterMate_db()
        except Exception as e:
            logger.error(f"Error reinitializing database during reload: {e}")
        
        # 8. Get all current vector layers and add them
        current_layers = self._filter_usable_layers(list(self.PROJECT.mapLayers().values()))
        
        if current_layers:
            logger.info(f"FilterMate: Reloading {len(current_layers)} layers")
            
            # Check if any PostgreSQL layers - need longer delay
            has_postgres = any(
                layer.providerType() == 'postgres' 
                for layer in current_layers
            )
            delay = STABILITY_CONSTANTS['UI_REFRESH_DELAY_MS']
            if has_postgres:
                delay += STABILITY_CONSTANTS['POSTGRESQL_EXTRA_DELAY_MS']
            
            # Set loading flag so the UI refresh is triggered after add_layers completes
            self._set_loading_flag(True)
            
            # Use weakref to prevent access violations on plugin unload
            weak_self = weakref.ref(self)
            def safe_add_layers():
                strong_self = weak_self()
                if strong_self is not None:
                    strong_self.manage_task('add_layers', current_layers)
            QTimer.singleShot(delay, safe_add_layers)
            
            # CRITICAL: Force UI refresh after layers are loaded
            # Schedule refresh with enough time for add_layers to complete
            refresh_delay = delay + 2000  # add_layers + 2s safety margin
            def safe_ui_refresh():
                strong_self = weak_self()
                if strong_self is not None:
                    strong_self._force_ui_refresh_after_reload()
            QTimer.singleShot(refresh_delay, safe_ui_refresh)
            
            # Show success message
            iface.messageBar().pushInfo(
                "FilterMate",
                f"Rechargement de {len(current_layers)} couche(s) en cours..."
            )
        else:
            logger.info("FilterMate: No layers to reload")
            iface.messageBar().pushInfo(
                "FilterMate",
                "Aucune couche vectorielle à recharger."
            )
            
            # Update indicator to show waiting state
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

    def _is_layer_valid(self, layer) -> bool:
        """
        Check if a layer object is still valid (C++ object not deleted).
        
        Args:
            layer: QgsVectorLayer to check
            
        Returns:
            bool: True if layer is valid and accessible, False otherwise
        """
        if layer is None:
            return False
        try:
            # Try to access basic properties - will raise if C++ object is deleted
            _ = layer.name()
            _ = layer.id()
            return layer.isValid()
        except (RuntimeError, AttributeError):
            return False

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
                from qgis.utils import iface
                iface.messageBar().pushWarning(
                    "FilterMate",
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
            
            # CRITICAL FIX: Signal may have been emitted BEFORE connection (in dockwidget __init__)
            # Check if widgets are already initialized and manually sync if needed
            if hasattr(self.dockwidget, 'widgets_initialized') and self.dockwidget.widgets_initialized:
                logger.info("Widgets already initialized before signal connection - syncing state")
                # Call the handler directly since signal was already emitted
                self._on_widgets_initialized()

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
                        current_layers = self._filter_usable_layers(all_layers)
                        
                        logger.info(f"Recovery diagnostic: total_layers={len(all_layers)}, usable_layers={len(current_layers)}, pending_tasks={self._pending_add_layers_tasks}")
                        
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
                iface.messageBar().pushInfo(
                    "FilterMate",
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
                            strong_self.manage_task('add_layers', usable)
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
                                strong_self.manage_task('add_layers', usable_layers)
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
            iface.messageBar().pushCritical("FilterMate", error_msg)
            return None
            
        try:
            conn = spatialite_connect(self.db_file_path)
            return conn
        except Exception as error:
            error_msg = f"Failed to connect to database {self.db_file_path}: {error}"
            logger.error(error_msg)
            iface.messageBar().pushCritical("FilterMate", error_msg)
            return None
    
    def _handle_remove_all_layers(self):
        """Handle remove all layers task.
        
        Safely cleans up all layer state when all layers are removed from project.
        STABILITY FIX: Properly resets current_layer and has_loaded_layers to prevent
        crashes when accessing invalid layer references.
        """
        self._safe_cancel_all_tasks()
        
        # CRITICAL: Check if dockwidget exists before accessing its methods
        if self.dockwidget is not None:
            # CRITICAL: Clear layer combo box to prevent access violations
            try:
                if hasattr(self.dockwidget, 'comboBox_filtering_current_layer'):
                    self.dockwidget.comboBox_filtering_current_layer.setLayer(None)
                    self.dockwidget.comboBox_filtering_current_layer.clear()
                    logger.debug("FilterMate: Layer combo cleared during remove_all_layers")
            except Exception as e:
                logger.debug(f"FilterMate: Error clearing layer combo during remove_all_layers: {e}")
            
            # STABILITY FIX: Disconnect LAYER_TREE_VIEW signal to prevent callbacks to invalid layers
            try:
                self.dockwidget.manageSignal(["QGIS", "LAYER_TREE_VIEW"], 'disconnect')
            except Exception as e:
                logger.debug(f"Could not disconnect LAYER_TREE_VIEW signal: {e}")
            
            self.dockwidget.disconnect_widgets_signals()
            self.dockwidget.reset_multiple_checkable_combobox()
            
            # STABILITY FIX: Reset current_layer to prevent access to deleted objects
            self.dockwidget.current_layer = None
            self.dockwidget.has_loaded_layers = False
            self.dockwidget._plugin_busy = False  # Ensure not stuck in busy state
            
            # Update backend indicator to show waiting state (badge style)
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
        
        self.layer_management_engine_task_completed({}, 'remove_all_layers')
        
        # Inform user that plugin is waiting for layers
        iface.messageBar().pushInfo(
            "FilterMate",
            "Toutes les couches ont été supprimées. Ajoutez des couches vectorielles pour réactiver le plugin."
        )
    
    def _handle_project_initialization(self, task_name):
        """Handle project read/new project initialization.
        
        Args:
            task_name: 'project_read' or 'new_project'
        """
        logger.debug(f"_handle_project_initialization called with task_name={task_name}")
        
        # STABILITY FIX: Check and reset stale flags that might block operations
        self._check_and_reset_stale_flags()
        
        # CRITICAL: Skip if already initializing to prevent recursive calls
        if self._initializing_project:
            logger.debug(f"Skipping {task_name} - already initializing project")
            return
        
        # CRITICAL: Skip if currently loading a new project (add_layers in progress)
        if self._loading_new_project:
            logger.debug(f"Skipping {task_name} - already loading new project")
            return
        
        # CRITICAL: Skip if dockwidget doesn't exist yet - run() handles initial setup
        if self.dockwidget is None:
            logger.debug(f"Skipping {task_name} - dockwidget not created yet (run() will handle)")
            return
        
        # Use timestamp-tracked flag setter
        self._set_initializing_flag(True)
        
        # CRITICAL: Clear layer combo box before project change to prevent access violations
        if self.dockwidget is not None:
            try:
                if hasattr(self.dockwidget, 'comboBox_filtering_current_layer'):
                    self.dockwidget.comboBox_filtering_current_layer.setLayer(None)
                    self.dockwidget.comboBox_filtering_current_layer.clear()
                    logger.debug(f"FilterMate: Layer combo cleared before {task_name}")
            except Exception as e:
                logger.debug(f"FilterMate: Error clearing layer combo before {task_name}: {e}")
        
        # STABILITY FIX: Set dockwidget busy flag to prevent concurrent layer changes
        if self.dockwidget is not None:
            self.dockwidget._plugin_busy = True
        
        try:
            # Verify project is valid
            project = QgsProject.instance()
            if not project:
                logger.warning(f"Project not available for {task_name}, skipping")
                return
            
            self.app_postgresql_temp_schema_setted = False
            self._safe_cancel_all_tasks()
            
            # Reset project datasources
            self.project_datasources = {'postgresql': {}, 'spatialite': {}, 'ogr': {}}
            # Use timestamp-tracked flag setter for loading
            self._set_loading_flag(True)
            
            init_env_vars()
            global ENV_VARS
            self.PROJECT = ENV_VARS["PROJECT"]

            # Verify project is still valid after init
            if not self.PROJECT:
                logger.warning(f"Project became invalid during {task_name}, skipping")
                self._set_loading_flag(False)
                return

            # CRITICAL: Disconnect old layer store signals before updating reference
            # The old MapLayerStore may be invalid after project change
            old_layer_store = self.MapLayerStore
            new_layer_store = self.PROJECT.layerStore()

            # ALWAYS reconnect signals on project change - even if layer_store is same object,
            # the project context has changed and signals may be stale
            if self._signals_connected:
                logger.info(f"FilterMate: Disconnecting old layer store signals for {task_name}")
                try:
                    # Disconnect ALL old signals using disconnect() without arguments
                    # This ensures all connections are removed
                    old_layer_store.layersAdded.disconnect()
                    old_layer_store.layersWillBeRemoved.disconnect()
                    old_layer_store.allLayersRemoved.disconnect()
                    logger.info("FilterMate: Old layer store signals disconnected")
                except (TypeError, RuntimeError) as e:
                    # Signals may already be invalid after project change
                    logger.debug(f"Could not disconnect old signals (expected): {e}")
                
                # Update to new layer store
                self.MapLayerStore = new_layer_store
                
                # Reconnect signals to new layer store
                self.MapLayerStore.layersAdded.connect(self._on_layers_added)
                self.MapLayerStore.layersWillBeRemoved.connect(lambda layers: self.manage_task('remove_layers', layers))
                self.MapLayerStore.allLayersRemoved.connect(lambda: self.manage_task('remove_all_layers'))
                logger.info("FilterMate: Layer store signals reconnected to new project")
            else:
                # First time - just update reference, signals will be connected in run()
                logger.debug("FilterMate: Updating MapLayerStore reference (signals not yet connected)")
                self.MapLayerStore = new_layer_store
            
            all_project_layers = list(self.PROJECT.mapLayers().values())
            init_layers = self._filter_usable_layers(all_project_layers)
            
            # FIX: Track PostgreSQL layers that failed initial validation (might not be ready yet)
            postgres_pending = [l for l in all_project_layers 
                               if isinstance(l, QgsVectorLayer) 
                               and l.providerType() == 'postgres' 
                               and l.id() not in [layer.id() for layer in init_layers]]
            if postgres_pending:
                logger.info(f"FilterMate: {len(postgres_pending)} PostgreSQL layers pending validation (connection may be initializing)")
            
            # Clear old PROJECT_LAYERS when switching projects
            self.PROJECT_LAYERS = {}
            
            self.init_filterMate_db()
            
            # Load favorites from the new project
            if hasattr(self, 'favorites_manager'):
                self.favorites_manager.load_from_project()
                logger.info(f"FilterMate: Favorites loaded for {task_name} ({self.favorites_manager.count} favorites)")
            
            # CRITICAL FIX v2.3.7: When switching projects, the layersAdded signal has ALREADY
            # been emitted by QGIS BEFORE we reach this point (it's emitted with projectRead).
            # Since we just reconnected signals, we missed it. We MUST manually trigger add_layers.
            # 
            # Previous comment was WRONG: "waiting for layersAdded signal" - the signal already passed!
            
            # Determine delay based on PostgreSQL presence
            has_postgres = any(l.providerType() == 'postgres' for l in all_project_layers if isinstance(l, QgsVectorLayer))
            base_delay = STABILITY_CONSTANTS['UI_REFRESH_DELAY_MS']
            if has_postgres:
                base_delay += STABILITY_CONSTANTS['POSTGRESQL_EXTRA_DELAY_MS']
                logger.info(f"PostgreSQL project detected - using extended delay ({base_delay}ms)")
            
            if len(init_layers) > 0 or postgres_pending:
                logger.info(f"FilterMate: {len(init_layers)} layers detected in {task_name} - manually triggering add_layers (signal already passed)")
                
                # CRITICAL: Manually call add_layers since we missed the signal
                # Use a short delay to allow flag resets to complete
                weak_self = weakref.ref(self)
                captured_init_layers = init_layers
                captured_postgres_pending = postgres_pending
                
                def trigger_add_layers():
                    strong_self = weak_self()
                    if strong_self is None:
                        return
                    # Reset flags before calling add_layers to prevent blocking
                    strong_self._set_initializing_flag(False)
                    strong_self._set_loading_flag(False)
                    
                    # Now trigger the add_layers task
                    logger.info(f"FilterMate: Triggering add_layers for {len(captured_init_layers)} layers")
                    strong_self.manage_task('add_layers', captured_init_layers)
                    
                    # FIX: Schedule retry for PostgreSQL layers that might be valid now
                    if captured_postgres_pending:
                        def retry_postgres_layers():
                            strong_self2 = weak_self()
                            if strong_self2 is None:
                                return
                            # Re-check PostgreSQL layers that were pending
                            now_valid = []
                            for layer in captured_postgres_pending:
                                try:
                                    if layer.isValid() and layer.id() not in strong_self2.PROJECT_LAYERS:
                                        now_valid.append(layer)
                                        logger.info(f"PostgreSQL layer '{layer.name()}' is now valid")
                                except (RuntimeError, AttributeError):
                                    pass
                            if now_valid:
                                logger.info(f"FilterMate: Retrying {len(now_valid)} PostgreSQL layers that are now valid")
                                strong_self2.manage_task('add_layers', now_valid)
                        
                        # Retry PostgreSQL layers after additional delay
                        QTimer.singleShot(STABILITY_CONSTANTS['POSTGRESQL_EXTRA_DELAY_MS'] * 2, retry_postgres_layers)
                
                # Use delay to ensure QGIS is stable (longer for PostgreSQL)
                QTimer.singleShot(base_delay, trigger_add_layers)
                
                # CRITICAL: Force UI refresh after layers are loaded
                # This ensures all widgets and signals are properly updated
                # Use longer delay and verify PROJECT_LAYERS is populated
                # For PostgreSQL projects, use even longer delay to account for retry mechanism
                refresh_delay = 3000 if not has_postgres else 5000
                
                def refresh_after_load():
                    if not self.dockwidget or not self.dockwidget.widgets_initialized:
                        return
                    
                    # CRITICAL: Verify PROJECT_LAYERS has been populated before refreshing
                    if len(self.PROJECT_LAYERS) == 0:
                        logger.debug(f"PROJECT_LAYERS still empty, deferring UI refresh by 1000ms")
                        # Layers not yet processed - try again in 1 second
                        QTimer.singleShot(1000, refresh_after_load)
                        return
                    
                    logger.info(f"Forcing UI refresh after {task_name} layer load with {len(self.PROJECT_LAYERS)} layers")
                    self._refresh_ui_after_project_load()
                
                # Start with appropriate delay based on project type
                QTimer.singleShot(refresh_delay, refresh_after_load)
            else:
                logger.info(f"FilterMate: No layers in {task_name}, resetting UI")
                # CRITICAL: Check dockwidget exists before accessing (should be true due to check at start)
                if self.dockwidget is not None:
                    self.dockwidget.disconnect_widgets_signals()
                    self.dockwidget.reset_multiple_checkable_combobox()
                    self.layer_management_engine_task_completed({}, 'remove_all_layers')
                    self._loading_new_project = False
                    # Inform user that plugin is waiting for layers
                    iface.messageBar().pushInfo(
                        "FilterMate",
                        "Projet sans couches vectorielles. Ajoutez des couches pour activer le plugin."
                    )
        finally:
            # STABILITY FIX: Use timestamp-tracked flag resetters
            self._set_initializing_flag(False)
            # STABILITY FIX: Always reset _loading_new_project flag, even on error
            if self._loading_new_project:
                logger.debug(f"Resetting _loading_new_project flag in finally block")
                self._set_loading_flag(False)
            # STABILITY FIX: Release dockwidget busy flag
            if self.dockwidget is not None:
                self.dockwidget._plugin_busy = False

    def manage_task(self, task_name, data=None):
        """
        Orchestrate execution of FilterMate tasks.
        
        Central dispatcher for all plugin operations including filtering, layer management,
        and project operations. Creates appropriate task objects and manages their execution
        through QGIS task manager.
        
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
        
        logger.debug(f"manage_task called with task_name={task_name}, data={type(data)}")
        
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
                        iface.messageBar().pushWarning("FilterMate", "Emergency fallback: forcing widgets ready flag")
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


                
            layers = []
            self.appTasks[task_name] = FilterEngineTask(self.tasks_descriptions[task_name], task_name, task_parameters)
            layers_props = [layer_infos for layer_infos in task_parameters["task"]["layers"]]
            layers_ids = [layer_props["layer_id"] for layer_props in layers_props]
            for layer_props in layers_props:
                temp_layers = self.PROJECT.mapLayersByName(layer_props["layer_name"])
                for temp_layer in temp_layers:
                    if temp_layer.id() in layers_ids:
                        layers.append(temp_layer)
            
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
            
            # Check if PostgreSQL layer is using OGR fallback (no connection available)
            # CRITICAL FIX v2.5.14: Default to True for PostgreSQL layers - they're always
            # filterable via QGIS native API (setSubsetString). Only explicitly False means fallback.
            is_fallback = (
                provider_type == 'postgresql' and 
                task_parameters["infos"].get("postgresql_connection_available", True) is False
            )
            
            # Check if Spatialite functions are available for the distant layers
            # If not, OGR fallback will be used
            spatialite_fallback = False
            if provider_type == 'spatialite' and layers:
                from .modules.backends.spatialite_backend import SpatialiteGeometricFilter
                spatialite_backend = SpatialiteGeometricFilter({})
                # Test first layer to see if Spatialite functions work
                test_layer = layers[0] if layers else current_layer
                if test_layer and not spatialite_backend.supports_layer(test_layer):
                    spatialite_fallback = True
                    is_fallback = True
                    provider_type = 'ogr'  # Update to show actual backend
                    logger.warning(f"Spatialite functions not available - using OGR fallback")
            
            if task_name == 'filter':
                show_backend_info(iface, provider_type, layer_count, operation='filter', is_fallback=is_fallback)
            elif task_name == 'unfilter':
                show_backend_info(iface, provider_type, layer_count, operation='unfilter', is_fallback=is_fallback)
            elif task_name == 'reset':
                show_backend_info(iface, provider_type, layer_count, operation='reset', is_fallback=is_fallback)

            self.appTasks[task_name].setDependentLayers(layers + [current_layer])
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
        """Safely cancel all tasks in the task manager to avoid access violations.
        
        Note: We cancel tasks individually instead of using cancelAll() to avoid
        Windows access violations that occur when cancelAll() is called from Qt signals
        during project transitions.
        """
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
        """Cancel all running tasks for a specific layer to prevent access violations.
        
        CRASH FIX (v2.3.20): This method must be called before modifying layer variables
        (setLayerVariable) to prevent the race condition where background tasks are
        iterating features while the main thread modifies layer state.
        
        Args:
            layer_id: The ID of the layer whose tasks should be cancelled
        """
        try:
            # Cancel tasks in exploring widgets
            if hasattr(self, 'dockwidget') and self.dockwidget:
                exploring_widget = self.dockwidget.widgets.get("EXPLORING", {})
                for widget_key in ["SINGLE_SELECTION_FEATURES", "MULTIPLE_SELECTION_FEATURES"]:
                    widget_data = exploring_widget.get(widget_key, {})
                    widget = widget_data.get("WIDGET")
                    if widget and hasattr(widget, 'tasks'):
                        for task_type in widget.tasks:
                            if layer_id in widget.tasks[task_type]:
                                task = widget.tasks[task_type][layer_id]
                                if isinstance(task, QgsTask) and not sip.isdeleted(task):
                                    if task.status() in [QgsTask.Running, QgsTask.Queued]:
                                        logger.debug(f"Cancelling {task_type} task for layer {layer_id} before variable update")
                                        task.cancel()
        except Exception as e:
            logger.debug(f"_cancel_layer_tasks: Error cancelling tasks: {e}")

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
        """Process queued add_layers operations.
        
        Processes the first queued add_layers operation from self._add_layers_queue.
        Called after a previous add_layers task completes or from safety timer.
        
        Thread-safe: Uses _processing_queue flag to prevent concurrent processing.
        """
        # Prevent concurrent queue processing
        if self._processing_queue:
            logger.debug("Queue already being processed, skipping")
            return
        
        if not self._add_layers_queue:
            logger.debug("Queue is empty, nothing to process")
            return
        
        self._processing_queue = True
        
        try:
            # Get first queued operation
            queued_layers = self._add_layers_queue.pop(0)
            logger.info(f"Processing queued add_layers operation with {len(queued_layers) if queued_layers else 0} layers (queue size: {len(self._add_layers_queue)})")
            
            # Process the queued operation
            # Note: manage_task will increment _pending_add_layers_tasks
            self.manage_task('add_layers', queued_layers)
            
        except Exception as e:
            logger.error(f"Error processing add_layers queue: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        finally:
            self._processing_queue = False
    
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
            
            from .modules.tasks.query_cache import warm_cache_for_project
            
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
        
        self.dockwidget.disconnect_widgets_signals()
        self.dockwidget.reset_multiple_checkable_combobox()
    
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
        
        # AUTO-INCLUDE: Add layers from same GeoPackage if source is GeoPackage
        from .modules.appUtils import get_geopackage_related_layers
        related_gpkg_layers = get_geopackage_related_layers(current_layer, self.PROJECT_LAYERS)
        
        if related_gpkg_layers:
            logger.info(f"🔗 Auto-including {len(related_gpkg_layers)} layer(s) from same GeoPackage")
            # Merge with user-selected layers, avoiding duplicates
            combined_list = list(set(raw_layers_list + related_gpkg_layers))
            logger.info(f"  Combined list size: {len(combined_list)} layers (user + auto)")
            raw_layers_list = combined_list
        else:
            logger.debug(f"  No related GeoPackage layers found (source is not GeoPackage or is single-layer)")
        
        logger.info(f"  Final layers to process: {len(raw_layers_list)}")
        
        for key in raw_layers_list:
            if key in self.PROJECT_LAYERS:
                layer_info = self.PROJECT_LAYERS[key]["infos"].copy()

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
                            self.PROJECT_LAYERS[key]["infos"].update(layer_info)
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
        
        Args:
            features: Selected features for filtering
            expression (str): Filter expression
            layers_to_filter (list): List of layers to apply filter to
            include_history (bool): Whether to include history_manager (for unfilter)
            
        Returns:
            dict: Common task parameters
        """
        from qgis.core import QgsMessageLog, Qgis
        
        # DIAGNOSTIC v2.4.17: Log incoming features at DEBUG level
        feat_count = len(features) if features else 0
        logger.debug(f"_build_common_task_params: {feat_count} features received, expression='{expression}'")
        
        # FIX v2.4.19: Deduplicate features by ID to prevent processing same feature twice
        # This can happen when features are passed from multiple sources (e.g., selection + expression)
        deduplicated_features = []
        seen_ids = set()
        if features:
            for feat in features:
                if hasattr(feat, 'id'):
                    feat_id = feat.id()
                    if feat_id not in seen_ids:
                        seen_ids.add(feat_id)
                        deduplicated_features.append(feat)
                    else:
                        logger.debug(f"  Removing duplicate feature id={feat_id}")
                else:
                    # Non-QgsFeature item, keep as is
                    deduplicated_features.append(feat)
        
        if len(deduplicated_features) != feat_count:
            # Log at WARNING only if significant deduplication (>10% difference)
            if feat_count - len(deduplicated_features) > max(1, feat_count * 0.1):
                logger.warning(f"  ⚠️ Deduplicated features: {feat_count} → {len(deduplicated_features)}")
            else:
                logger.debug(f"  Deduplicated features: {feat_count} → {len(deduplicated_features)}")
            features = deduplicated_features
        
        logger.debug(f"=== _build_common_task_params DIAGNOSTIC ===")
        logger.debug(f"  features count: {len(features) if features else 0}")
        if features and logger.isEnabledFor(logging.DEBUG):
            # Only log first 3 features to reduce verbosity
            for idx, feat in enumerate(features[:3]):
                if hasattr(feat, 'id') and hasattr(feat, 'geometry'):
                    feat_id = feat.id()
                    if feat.hasGeometry():
                        bbox = feat.geometry().boundingBox()
                        logger.debug(f"  feature[{idx}]: id={feat_id}, bbox=({bbox.xMinimum():.1f},{bbox.yMinimum():.1f})-({bbox.xMaximum():.1f},{bbox.yMaximum():.1f})")
                    else:
                        logger.debug(f"  feature[{idx}]: id={feat_id}, NO GEOMETRY")
                else:
                    logger.debug(f"  feature[{idx}]: type={type(feat).__name__}")
            if len(features) > 3:
                logger.debug(f"  ... and {len(features) - 3} more features")
        logger.debug(f"  expression: '{expression}'")
        logger.debug(f"  layers_to_filter count: {len(layers_to_filter)}")
        
        # CRITICAL FIX: Validate that expression is a boolean filter expression, not a display expression
        # Display expressions like coalesce("field",'<NULL>') return values, not boolean
        # They cannot be used in SQL WHERE clauses
        validated_expression = expression
        if expression:
            # Check if expression contains comparison operators (required for boolean filter)
            comparison_operators = ['=', '>', '<', '!=', '<>', ' IN ', ' LIKE ', ' ILIKE ', 
                                   ' IS NULL', ' IS NOT NULL', ' BETWEEN ', ' NOT ', '~']
            has_comparison = any(op in expression.upper() for op in comparison_operators)
            
            if not has_comparison:
                # Expression doesn't contain comparison operators - likely a display expression
                # Don't use it as a filter expression
                logger.debug(f"_build_common_task_params: Rejecting display expression '{expression}' - no comparison operators")
                validated_expression = ''
        
        params = {
            "features": features,
            "expression": validated_expression,
            "options": self.dockwidget.project_props["OPTIONS"],
            "layers": layers_to_filter,
            "db_file_path": self.db_file_path,
            "project_uuid": self.project_uuid,
            "session_id": self.session_id  # For multi-client materialized view isolation
        }
        if include_history:
            params["history_manager"] = self.history_manager
        
        # Add forced backends information from dockwidget
        if self.dockwidget and hasattr(self.dockwidget, 'forced_backends'):
            params["forced_backends"] = self.dockwidget.forced_backends
        
        return params
    
    def _build_layer_management_params(self, layers, reset_flag):
        """
        Build parameters for layer management tasks (add/remove layers).
        
        Args:
            layers (list): List of layers to manage
            reset_flag (bool): Whether to reset all layer variables
            
        Returns:
            dict: Layer management task parameters
        """
        return {
            "task": {
                "layers": layers,
                "project_layers": self.PROJECT_LAYERS,
                "reset_all_layers_variables_flag": reset_flag,
                "config_data": self.CONFIG_DATA,
                "db_file_path": self.db_file_path,
                "project_uuid": self.project_uuid,
                "session_id": self.session_id  # For multi-client materialized view isolation
            }
        }

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
            if self.dockwidget and hasattr(self.dockwidget, 'mQgsDoubleSpinBox_filtering_buffer_value'):
                current_spinbox_buffer = self.dockwidget.mQgsDoubleSpinBox_filtering_buffer_value.value()
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

            if current_layer.subsetString() != '':
                self.PROJECT_LAYERS[current_layer.id()]["infos"]["is_already_subset"] = True
            else:
                self.PROJECT_LAYERS[current_layer.id()]["infos"]["is_already_subset"] = False

            features, expression = self.dockwidget.get_current_features()

            if task_name in ('filter', 'unfilter', 'reset'):
                # Build validated list of layers to filter
                layers_to_filter = self._build_layers_to_filter(current_layer)
                
                # Log filtering state
                filtering_props = self.PROJECT_LAYERS[current_layer.id()]["filtering"]
                logger.debug(f"get_task_parameters - Filtering state for {current_layer.name()}: "
                           f"has_layers_to_filter={filtering_props.get('has_layers_to_filter')}, "
                           f"layers_count={len(layers_to_filter)}")
                
                # Build common task parameters
                # Note: unfilter no longer needs history_manager (just clears filters)
                include_history = False
                task_parameters["task"] = self._build_common_task_params(
                    features, expression, layers_to_filter, include_history
                )
                
                # NOUVEAU: Détecter si le filtre source doit être ignoré
                # Cas: custom_selection active ET expression est juste un champ (pas complexe)
                skip_source_filter = False
                if (task_name == 'filter' and 
                    self.dockwidget.current_exploring_groupbox == "custom_selection" and
                    expression):
                    qgs_expr = QgsExpression(expression)
                    if qgs_expr.isValid() and qgs_expr.isField():
                        skip_source_filter = True
                        logger.info(f"FilterMate: Custom selection with field-only expression '{expression}' - will skip source layer filter")
                
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
        
        Args:
            source_layer (QgsVectorLayer): Layer to refresh
        """
        # Check if layer is Spatialite or OGR (local file-based SQLite)
        provider_type = source_layer.providerType() if source_layer else None
        needs_stabilization = provider_type in ('spatialite', 'ogr')
        
        if needs_stabilization:
            # Brief stabilization delay to let SQLite connections settle
            # This helps prevent "unable to open database file" errors
            import time
            stabilization_ms = STABILITY_CONSTANTS.get('SPATIALITE_STABILIZATION_MS', 200)
            time.sleep(stabilization_ms / 1000.0)
        
        # Use GDAL error handler to suppress transient SQLite warnings during refresh
        with GdalErrorHandler():
            source_layer.updateExtents()
            source_layer.triggerRepaint()
            self.iface.mapCanvas().refreshAllLayers()
            self.iface.mapCanvas().refresh()
    
    def _push_filter_to_history(self, source_layer, task_parameters, feature_count, provider_type, layer_count):
        """
        Push filter state to history for source and associated layers.
        
        Args:
            source_layer (QgsVectorLayer): Source layer being filtered
            task_parameters (dict): Task parameters containing layers info
            feature_count (int): Number of features in filtered result
            provider_type (str): Backend provider type
            layer_count (int): Number of layers affected
        """
        # Save source layer state to history
        history = self.history_manager.get_or_create_history(source_layer.id())
        filter_expression = source_layer.subsetString()
        description = f"Filter: {filter_expression[:60]}..." if len(filter_expression) > 60 else f"Filter: {filter_expression}"
        history.push_state(
            expression=filter_expression,
            feature_count=feature_count,
            description=description,
            metadata={"backend": provider_type, "operation": "filter", "layer_count": layer_count}
        )
        logger.info(f"FilterMate: Pushed filter state to history for source layer (position {history._current_index + 1}/{len(history._states)})")
        
        # Collect remote layers info for global history
        remote_layers_info = {}
        
        # Save associated layers state to history
        for layer_props in task_parameters.get("task", {}).get("layers", []):
            if layer_props["layer_id"] in self.PROJECT_LAYERS:
                layers = [layer for layer in self.PROJECT.mapLayersByName(layer_props["layer_name"]) 
                         if layer.id() == layer_props["layer_id"]]
                if len(layers) == 1:
                    assoc_layer = layers[0]
                    assoc_history = self.history_manager.get_or_create_history(assoc_layer.id())
                    assoc_filter = assoc_layer.subsetString()
                    assoc_count = assoc_layer.featureCount()
                    assoc_desc = f"Filter: {assoc_filter[:60]}..." if len(assoc_filter) > 60 else f"Filter: {assoc_filter}"
                    assoc_history.push_state(
                        expression=assoc_filter,
                        feature_count=assoc_count,
                        description=assoc_desc,
                        metadata={"backend": layer_props.get("layer_provider_type", "unknown"), "operation": "filter"}
                    )
                    logger.info(f"FilterMate: Pushed filter state to history for layer {assoc_layer.name()}")
                    
                    # Add to global history info
                    remote_layers_info[assoc_layer.id()] = (assoc_filter, assoc_count)
        
        # Push global state if we have remote layers
        if remote_layers_info:
            self.history_manager.push_global_state(
                source_layer_id=source_layer.id(),
                source_expression=filter_expression,
                source_feature_count=feature_count,
                remote_layers=remote_layers_info,
                description=f"Global filter: {len(remote_layers_info) + 1} layers",
                metadata={"backend": provider_type, "operation": "filter"}
            )
            logger.info(f"FilterMate: Pushed global filter state ({len(remote_layers_info) + 1} layers)")
    
    def update_undo_redo_buttons(self):
        """
        Update undo/redo button states based on history availability.
        """
        if not self.dockwidget or not hasattr(self.dockwidget, 'pushButton_action_undo_filter') or not hasattr(self.dockwidget, 'pushButton_action_redo_filter'):
            return
        
        if not self.dockwidget.current_layer:
            self.dockwidget.pushButton_action_undo_filter.setEnabled(False)
            self.dockwidget.pushButton_action_redo_filter.setEnabled(False)
            return
        
        source_layer = self.dockwidget.current_layer
        
        # STABILITY FIX: Guard against KeyError if layer not in PROJECT_LAYERS
        if source_layer.id() not in self.dockwidget.PROJECT_LAYERS:
            logger.debug(f"update_undo_redo_buttons: layer {source_layer.name()} not in PROJECT_LAYERS")
            self.dockwidget.pushButton_action_undo_filter.setEnabled(False)
            self.dockwidget.pushButton_action_redo_filter.setEnabled(False)
            return
        
        layers_to_filter = self.dockwidget.PROJECT_LAYERS[source_layer.id()]["filtering"].get("layers_to_filter", [])
        
        # Check if remote layers are selected
        has_remote_layers = bool(layers_to_filter)
        
        # Determine undo/redo availability
        if has_remote_layers:
            # Global history mode
            can_undo = self.history_manager.can_undo_global()
            can_redo = self.history_manager.can_redo_global()
        else:
            # Source layer only mode
            history = self.history_manager.get_history(source_layer.id())
            can_undo = history.can_undo() if history else False
            can_redo = history.can_redo() if history else False
        
        self.dockwidget.pushButton_action_undo_filter.setEnabled(can_undo)
        self.dockwidget.pushButton_action_redo_filter.setEnabled(can_redo)
        
        logger.debug(f"FilterMate: Updated undo/redo buttons - undo: {can_undo}, redo: {can_redo}")
    
    def handle_undo(self):
        """
        Handle undo operation with intelligent layer selection logic.
        
        Logic:
        - If pushButton_checkable_filtering_layers_to_filter is checked AND has remote layers: undo all layers globally
        - If pushButton_checkable_filtering_layers_to_filter is unchecked: undo only source layer
        """
        if not self.dockwidget or not self.dockwidget.current_layer:
            logger.warning("FilterMate: No current layer for undo")
            return
        
        source_layer = self.dockwidget.current_layer

        # Guard: ensure layer is usable
        if not is_layer_source_available(source_layer):
            logger.warning("handle_undo: source layer invalid or source missing; aborting.")
            iface.messageBar().pushWarning(
                "FilterMate",
                "Impossible d'annuler: couche invalide ou source introuvable."
            )
            return
        
        # STABILITY FIX: Verify layer exists in PROJECT_LAYERS before access
        if source_layer.id() not in self.dockwidget.PROJECT_LAYERS:
            logger.warning(f"handle_undo: layer {source_layer.name()} not in PROJECT_LAYERS; aborting.")
            return
        
        layers_to_filter = self.dockwidget.PROJECT_LAYERS[source_layer.id()]["filtering"].get("layers_to_filter", [])
        
        # Check if the "Layers to filter" button is checked and has remote layers selected
        button_is_checked = self.dockwidget.pushButton_checkable_filtering_layers_to_filter.isChecked()
        has_remote_layers = bool(layers_to_filter)
        
        # Use global undo if button is checked and remote layers are selected
        use_global_undo = button_is_checked and has_remote_layers
        
        if use_global_undo:
            # Global undo
            logger.info("FilterMate: Performing global undo (remote layers are filtered)")
            global_state = self.history_manager.undo_global()
            
            if global_state:
                # Apply state to source layer
                safe_set_subset_string(source_layer, global_state.source_expression)
                self.PROJECT_LAYERS[source_layer.id()]["infos"]["is_already_subset"] = bool(global_state.source_expression)
                logger.info(f"FilterMate: Restored source layer: {global_state.source_expression[:60] if global_state.source_expression else 'no filter'}")
                
                # Apply state to ALL remote layers from the saved state
                restored_count = 0
                restored_layers = []
                for remote_id, (expression, _) in global_state.remote_layers.items():
                    # Check if layer still exists in project
                    if remote_id not in self.PROJECT_LAYERS:
                        logger.warning(f"FilterMate: Remote layer {remote_id} no longer exists, skipping")
                        continue
                    
                    remote_layers = [l for l in self.PROJECT.mapLayers().values() if l.id() == remote_id]
                    if remote_layers:
                        remote_layer = remote_layers[0]
                        if not is_layer_source_available(remote_layer):
                            logger.warning(
                                f"Global undo: skipping remote layer '{remote_layer.name()}' (invalid or missing source)"
                            )
                            continue
                        safe_set_subset_string(remote_layer, expression)
                        self.PROJECT_LAYERS[remote_id]["infos"]["is_already_subset"] = bool(expression)
                        logger.info(f"FilterMate: Restored remote layer {remote_layer.name()}: {expression[:60] if expression else 'no filter'}")
                        restored_count += 1
                        restored_layers.append(remote_layer)
                    else:
                        logger.warning(f"FilterMate: Remote layer {remote_id} not found in project")
                
                # Refresh ALL affected layers (source + remotes), not just source
                source_layer.updateExtents()
                source_layer.triggerRepaint()
                for remote_layer in restored_layers:
                    remote_layer.updateExtents()
                    remote_layer.triggerRepaint()
                self.iface.mapCanvas().refreshAllLayers()
                self.iface.mapCanvas().refresh()
                
                logger.info(f"FilterMate: Global undo completed - restored {restored_count + 1} layers")
            else:
                logger.info("FilterMate: No global undo history available")
        else:
            # Source layer only undo
            logger.info("FilterMate: Performing source layer undo only")
            history = self.history_manager.get_history(source_layer.id())
            
            if history and history.can_undo():
                previous_state = history.undo()
                if previous_state:
                    safe_set_subset_string(source_layer, previous_state.expression)
                    self.PROJECT_LAYERS[source_layer.id()]["infos"]["is_already_subset"] = bool(previous_state.expression)
                    logger.info(f"FilterMate: Undo source layer to: {previous_state.description}")
                    
                    # Refresh
                    self._refresh_layers_and_canvas(source_layer)
            else:
                logger.info("FilterMate: No undo history for source layer")
        
        # Update button states after undo
        self.update_undo_redo_buttons()
    
    def handle_redo(self):
        """
        Handle redo operation with intelligent layer selection logic.
        
        Logic:
        - If pushButton_checkable_filtering_layers_to_filter is checked AND has remote layers: redo all layers globally
        - If pushButton_checkable_filtering_layers_to_filter is unchecked: redo only source layer
        """
        if not self.dockwidget or not self.dockwidget.current_layer:
            logger.warning("FilterMate: No current layer for redo")
            return
        
        source_layer = self.dockwidget.current_layer

        # Guard: ensure layer is usable
        if not is_layer_source_available(source_layer):
            logger.warning("handle_redo: source layer invalid or source missing; aborting.")
            iface.messageBar().pushWarning(
                "FilterMate",
                "Impossible de rétablir: couche invalide ou source introuvable."
            )
            return
        
        # STABILITY FIX: Verify layer exists in PROJECT_LAYERS before access
        if source_layer.id() not in self.dockwidget.PROJECT_LAYERS:
            logger.warning(f"handle_redo: layer {source_layer.name()} not in PROJECT_LAYERS; aborting.")
            return
        
        layers_to_filter = self.dockwidget.PROJECT_LAYERS[source_layer.id()]["filtering"].get("layers_to_filter", [])
        
        # Check if the "Layers to filter" button is checked and has remote layers selected
        button_is_checked = self.dockwidget.pushButton_checkable_filtering_layers_to_filter.isChecked()
        has_remote_layers = bool(layers_to_filter)
        
        # Use global redo if button is checked and remote layers are selected
        use_global_redo = button_is_checked and has_remote_layers
        
        if use_global_redo and self.history_manager.can_redo_global():
            # Global redo
            logger.info("FilterMate: Performing global redo")
            global_state = self.history_manager.redo_global()
            
            if global_state:
                # Apply state to source layer
                safe_set_subset_string(source_layer, global_state.source_expression)
                self.PROJECT_LAYERS[source_layer.id()]["infos"]["is_already_subset"] = bool(global_state.source_expression)
                logger.info(f"FilterMate: Restored source layer: {global_state.source_expression[:60] if global_state.source_expression else 'no filter'}")
                
                # Apply state to ALL remote layers from the saved state
                restored_count = 0
                restored_layers = []
                for remote_id, (expression, _) in global_state.remote_layers.items():
                    # Check if layer still exists in project
                    if remote_id not in self.PROJECT_LAYERS:
                        logger.warning(f"FilterMate: Remote layer {remote_id} no longer exists, skipping")
                        continue
                    
                    remote_layers = [l for l in self.PROJECT.mapLayers().values() if l.id() == remote_id]
                    if remote_layers:
                        remote_layer = remote_layers[0]
                        if not is_layer_source_available(remote_layer):
                            logger.warning(
                                f"Global redo: skipping remote layer '{remote_layer.name()}' (invalid or missing source)"
                            )
                            continue
                        safe_set_subset_string(remote_layer, expression)
                        self.PROJECT_LAYERS[remote_id]["infos"]["is_already_subset"] = bool(expression)
                        logger.info(f"FilterMate: Restored remote layer {remote_layer.name()}: {expression[:60] if expression else 'no filter'}")
                        restored_count += 1
                        restored_layers.append(remote_layer)
                    else:
                        logger.warning(f"FilterMate: Remote layer {remote_id} not found in project")
                
                # Refresh ALL affected layers (source + remotes), not just source
                source_layer.updateExtents()
                source_layer.triggerRepaint()
                for remote_layer in restored_layers:
                    remote_layer.updateExtents()
                    remote_layer.triggerRepaint()
                self.iface.mapCanvas().refreshAllLayers()
                self.iface.mapCanvas().refresh()
                
                logger.info(f"FilterMate: Global redo completed - restored {restored_count + 1} layers")
            else:
                logger.info("FilterMate: No global redo history available")
        else:
            # Source layer only redo
            logger.info("FilterMate: Performing source layer redo only")
            history = self.history_manager.get_history(source_layer.id())
            
            if history and history.can_redo():
                next_state = history.redo()
                if next_state:
                    safe_set_subset_string(source_layer, next_state.expression)
                    self.PROJECT_LAYERS[source_layer.id()]["infos"]["is_already_subset"] = bool(next_state.expression)
                    logger.info(f"FilterMate: Redo source layer to: {next_state.description}")
                    
                    # Refresh
                    self._refresh_layers_and_canvas(source_layer)
            else:
                logger.info("FilterMate: No redo history for source layer")
        
        # Update button states after redo
        self.update_undo_redo_buttons()
    
    def _clear_filter_history(self, source_layer, task_parameters):
        """
        Clear filter history for source and associated layers.
        
        Args:
            source_layer (QgsVectorLayer): Source layer whose history to clear
            task_parameters (dict): Task parameters containing layers info
        """
        # Clear history for source layer
        history = self.history_manager.get_history(source_layer.id())
        if history:
            history.clear()
            logger.info(f"FilterMate: Cleared filter history for source layer {source_layer.id()}")
        
        # Clear global history
        self.history_manager.clear_global_history()
        
        # Clear history for associated layers
        for layer_props in task_parameters.get("task", {}).get("layers", []):
            if layer_props["layer_id"] in self.PROJECT_LAYERS:
                layers = [layer for layer in self.PROJECT.mapLayersByName(layer_props["layer_name"]) 
                         if layer.id() == layer_props["layer_id"]]
                if len(layers) == 1:
                    assoc_layer = layers[0]
                    assoc_history = self.history_manager.get_history(assoc_layer.id())
                    if assoc_history:
                        assoc_history.clear()
                        logger.info(f"FilterMate: Cleared filter history for layer {assoc_layer.name()}")
    
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
        show_success_with_backend(iface, provider_type, task_name, layer_count, is_fallback=is_fallback)
        
        # Only show feature count if configured to do so
        if should_show_message('filter_count'):
            if task_name == 'filter':
                iface.messageBar().pushInfo(
                    "FilterMate",
                    f"{feature_count:,} features visible in main layer"
                )
            elif task_name == 'unfilter':
                iface.messageBar().pushInfo(
                    "FilterMate",
                    f"All filters cleared - {feature_count:,} features visible in main layer"
                )
            elif task_name == 'reset':
                iface.messageBar().pushInfo(
                    "FilterMate",
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
        if hasattr(self.dockwidget, '_update_backend_indicator'):
            if actual_backends:
                # Get PostgreSQL connection status
                postgresql_conn = task_parameters.get('infos', {}).get('postgresql_connection_available')
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

    def _save_single_property(self, layer, cursor, key_group, key, value):
        """
        Save a single property to QGIS variable and Spatialite database.
        
        Helper method to eliminate code duplication in save_variables_from_layer.
        
        Args:
            layer (QgsVectorLayer): Layer to save property for
            cursor: SQLite cursor for database operations
            key_group (str): Property group ('infos', 'exploring', 'filtering')
            key (str): Property key name
            value: Property value to save
        """
        # CRASH FIX (v2.3.18): Check if QGIS is still alive before any operations
        if not is_qgis_alive():
            logger.debug(f"_save_single_property: QGIS is shutting down, skipping save for {key_group}.{key}")
            return
        
        # CRASH FIX (v2.4.11): Check if dockwidget is in the middle of a layer change
        # When setCollapsed() processes Qt events, deferred operations run during
        # _reconnect_layer_signals which can cause access violations if we try to
        # call setLayerVariable during this unstable state.
        skip_qgis_variable = False
        if hasattr(self, 'dockwidget') and self.dockwidget is not None:
            if getattr(self.dockwidget, '_updating_current_layer', False):
                logger.debug(f"_save_single_property: layer change in progress, deferring QGIS variable for {key_group}.{key}")
                skip_qgis_variable = True
        
        # CRASH FIX (v2.3.15): Use is_valid_layer() for robust validation
        # This prevents Windows access violations when layer's C++ object is deleted
        # during signal processing (e.g., backend change, layer switch, project unload)
        if not is_valid_layer(layer):
            logger.debug(f"_save_single_property: layer is invalid or deleted, skipping save for {key_group}.{key}")
            return
        
        # Double-check layer ID is accessible (defensive programming)
        try:
            layer_id = layer.id()
            if not layer_id:
                return
        except (RuntimeError, OSError, SystemError):
            logger.debug(f"_save_single_property: layer.id() failed, C++ object likely deleted")
            return
        
        # CRASH FIX (v2.3.16): Re-fetch fresh layer reference from QGIS project
        # This is CRITICAL for preventing Windows access violations. The original layer
        # reference may be stale (C++ object deleted) even if previous checks passed.
        # Windows access violations CANNOT be caught by try/except - they crash the app.
        # By re-fetching from QgsProject, we get a valid reference or None.
        fresh_layer = QgsProject.instance().mapLayer(layer_id)
        if fresh_layer is None:
            logger.debug(f"_save_single_property: layer {layer_id} no longer in project, skipping {key_group}.{key}")
            return
        
        # Final validation of the fresh layer reference
        if not is_valid_layer(fresh_layer):
            logger.debug(f"_save_single_property: fresh layer reference is invalid, skipping {key_group}.{key}")
            return
        
        value_typped, type_returned = self.return_typped_value(value, 'save')
        if type_returned in (list, dict):
            value_typped = json.dumps(value_typped)
        
        variable_key = f"filterMate_{key_group}_{key}"
        
        # CRASH FIX (v2.3.18): Check if layer is still in project - most reliable check
        # If layer was removed from project, QgsProject.mapLayer() returns None.
        # This is more reliable than sip.isdeleted() for detecting deleted layers.
        project_layer = QgsProject.instance().mapLayer(layer_id)
        if project_layer is None:
            logger.debug(f"_save_single_property: layer {layer_id} removed from project, skipping QGIS variable for {key_group}.{key}")
            # Still save to database below (layer_id is valid even if layer is gone)
        elif skip_qgis_variable:
            # CRASH FIX (v2.4.11): Layer change is in progress, skip QGIS variable update
            # but still save to database below
            pass
        else:
            # CRASH FIX (v2.3.18): Triple-check with sip.isdeleted() IMMEDIATELY before Qt call
            # This is the last line of defense against Windows access violations.
            if sip.isdeleted(project_layer):
                logger.debug(f"_save_single_property: project_layer sip deleted just before setLayerVariable, skipping {key_group}.{key}")
                # Still save to database below
            else:
                # CRASH FIX (v2.3.20): Cancel running tasks for this layer before modifying variables
                # This prevents the race condition where background tasks iterate features
                # while setLayerVariable modifies the layer state, causing access violations.
                self._cancel_layer_tasks(layer_id)
                
                # CRASH FIX (v2.4.14): Use safe_set_layer_variable from object_safety module
                # This function handles ALL the complexity of Windows access violation prevention:
                # - Re-fetches layer from project registry
                # - Checks sip deletion status multiple times
                # - Flushes pending Qt events on Windows before C++ call
                # - Uses setCustomProperty instead of setLayerVariable (safer)
                # - Returns False on failure instead of crashing
                variable_name = f"{key_group}_{key}"
                if not safe_set_layer_variable(layer_id, variable_name, value_typped):
                    logger.debug(f"_save_single_property: safe_set_layer_variable returned False for {layer_id}.{variable_name}")
                    # Continue to database save - don't return
        
        # CRASH FIX (v2.3.16): Use layer_id instead of layer.id() to avoid accessing stale reference
        cursor.execute(
            """INSERT INTO fm_project_layers_properties 
               VALUES(?, datetime(), ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), str(self.project_uuid), layer_id, 
             key_group, key, str(value_typped))
        )

    def save_variables_from_layer(self, layer, layer_properties=None):
        """
        Save layer filtering properties to both QGIS variables and Spatialite database.
        
        Stores layer properties in two locations:
        1. QGIS layer variables (for runtime access)
        2. Spatialite database (for persistence across sessions)
        
        CRASH FIX (v2.3.15): Added is_valid_layer() check to prevent Windows access
        violations when layer's C++ object is deleted during signal processing.
        
        Args:
            layer (QgsVectorLayer): Layer to save properties for
            layer_properties (list): List of tuples (key_group, key, value, type)
                Example: [('filtering', 'layer_filter_expression', 'population > 1000', 'str')]
                If None or empty, saves all properties
                
        Notes:
            - Uses parameterized SQL queries to prevent injection
            - Converts string values to proper types before storing
            - Creates filterMate_{key_group}_{key} variable names
            - Stores in fm_project_layers_properties table
            - Uses context manager for automatic connection cleanup
        """

        if layer_properties is None:
            layer_properties = []
        
        layer_all_properties_flag = False

        # CRASH FIX (v2.3.15): Use is_valid_layer() for robust validation
        # This catches deleted C++ objects that would cause access violations
        if not is_valid_layer(layer):
            logger.debug(f"save_variables_from_layer: layer is invalid or deleted, skipping save")
            return

        if len(layer_properties) == 0:
            layer_all_properties_flag = True
        
        # Debug logging for persistence tracking
        # CRASH FIX (v2.3.15): Wrap layer access in try/except for extra safety
        try:
            if layer_all_properties_flag:
                logger.debug(f"💾 Saving ALL properties for layer '{layer.name()}' ({layer.id()})")
            else:
                logger.debug(f"💾 Saving {len(layer_properties)} specific properties for layer '{layer.name()}' ({layer.id()})")
                for prop in layer_properties[:3]:  # Log first 3 properties
                    # Handle both tuple formats: (key_group, key) or (key_group, key, value, type)
                    if len(prop) >= 3:
                        value_str = str(prop[2])[:50] + "..." if len(str(prop[2])) > 50 else str(prop[2])
                        logger.debug(f"  - {prop[0]}.{prop[1]} = {value_str}")
                    else:
                        logger.debug(f"  - {prop[0]}.{prop[1]}")
        except (RuntimeError, OSError, SystemError) as e:
            logger.debug(f"save_variables_from_layer: layer access failed during logging: {e}")
            return

        if layer.id() not in self.PROJECT_LAYERS.keys():
            logger.warning(f"Layer {layer.name()} not in PROJECT_LAYERS, cannot save properties")
            return
        
        conn = self.get_spatialite_connection()
        if conn is None:
            return
        
        with conn:
            cur = conn.cursor()
            
            if layer_all_properties_flag:
                # Save all properties from all groups
                for key_group in ("infos", "exploring", "filtering"):
                    for key, value in self.PROJECT_LAYERS[layer.id()][key_group].items():
                        self._save_single_property(layer, cur, key_group, key, value)
            else:
                # Save specific properties
                for layer_property in layer_properties:
                    key_group, key = layer_property[0], layer_property[1]
                    if key_group not in ("infos", "exploring", "filtering"):
                        continue
                    
                    if (key_group in self.PROJECT_LAYERS[layer.id()] and 
                        key in self.PROJECT_LAYERS[layer.id()][key_group]):
                        value = self.PROJECT_LAYERS[layer.id()][key_group][key]
                        self._save_single_property(layer, cur, key_group, key, value)

    def remove_variables_from_layer(self, layer, layer_properties=None):
        """
        Remove layer filtering properties from QGIS variables and Spatialite database.
        
        Clears stored properties from both runtime variables and persistent storage.
        Used when resetting filters or cleaning up removed layers.
        
        CRASH FIX (v2.3.17): Added sip.isdeleted() and is_valid_layer() checks
        to prevent Windows access violations when layer C++ object is deleted.
        
        Args:
            layer (QgsVectorLayer): Layer to remove properties from
            layer_properties (list): List of tuples (key_group, key, value, type)
                If None or empty, removes ALL filterMate variables for the layer
                
        Notes:
            - Sets QGIS variables to empty string (effectively removes them)
            - Deletes corresponding rows from Spatialite database
            - Uses parameterized queries for SQL injection protection
            - Handles both selective and bulk removal
            - Uses context manager for safe database operations
        """
        
        if layer_properties is None:
            layer_properties = []
        
        layer_all_properties_flag = False

        # CRASH FIX (v2.3.17): Use is_valid_layer() for robust validation
        if not is_valid_layer(layer):
            logger.debug("remove_variables_from_layer: layer is invalid or deleted, skipping")
            return
        
        # Extract layer_id early and re-fetch layer for safety
        try:
            layer_id = layer.id()
            if not layer_id:
                return
        except (RuntimeError, OSError, SystemError):
            logger.debug("remove_variables_from_layer: layer.id() failed, C++ object likely deleted")
            return
        
        # Re-fetch fresh layer reference from project
        fresh_layer = QgsProject.instance().mapLayer(layer_id)
        if fresh_layer is None:
            logger.debug(f"remove_variables_from_layer: layer {layer_id} no longer in project, skipping")
            return
        
        # Final validation of fresh layer
        if not is_valid_layer(fresh_layer):
            logger.debug("remove_variables_from_layer: fresh layer reference is invalid, skipping")
            return
        
        # Debug logging for deletion tracking
        try:
            layer_name = fresh_layer.name()
            if len(layer_properties) == 0:
                layer_all_properties_flag = True
                logger.debug(f"🗑️ Removing ALL properties for layer '{layer_name}' ({layer_id})")
            else:
                logger.debug(f"🗑️ Removing {len(layer_properties)} specific properties for layer '{layer_name}' ({layer_id})")
        except (RuntimeError, OSError, SystemError) as e:
            logger.debug(f"remove_variables_from_layer: layer access failed during logging: {e}")
            return
        
        if layer_id not in self.PROJECT_LAYERS.keys():
            logger.warning(f"Layer {layer_id} not in PROJECT_LAYERS, cannot remove properties")
            return
        
        conn = self.get_spatialite_connection()
        if conn is None:
            return
        
        with conn:
            cur = conn.cursor()
            
            if layer_all_properties_flag:
                # Remove all properties for layer
                cur.execute(
                    """DELETE FROM fm_project_layers_properties 
                       WHERE fk_project = ? and layer_id = ?""",
                    (str(self.project_uuid), layer_id)
                )
                # CRASH FIX (v2.3.17): Final sip check before Qt call
                if not sip.isdeleted(fresh_layer):
                    try:
                        QgsExpressionContextUtils.setLayerVariables(fresh_layer, {})
                    except (RuntimeError, OSError, SystemError) as e:
                        logger.warning(f"remove_variables_from_layer: setLayerVariables failed: {e}")
            else:
                # Remove specific properties
                for layer_property in layer_properties:
                    key_group, key = layer_property[0], layer_property[1]
                    if key_group not in ("infos", "exploring", "filtering"):
                        continue
                    
                    if (key_group in self.PROJECT_LAYERS[layer_id] and 
                        key in self.PROJECT_LAYERS[layer_id][key_group]):
                        cur.execute(
                            """DELETE FROM fm_project_layers_properties  
                               WHERE fk_project = ? and layer_id = ? 
                               and meta_type = ? and meta_key = ?""",
                            (str(self.project_uuid), layer_id, key_group, key)
                        )
                        variable_key = f"filterMate_{key_group}_{key}"
                        # CRASH FIX (v2.3.17): Final sip check before Qt call
                        if not sip.isdeleted(fresh_layer):
                            try:
                                QgsExpressionContextUtils.setLayerVariable(fresh_layer, variable_key, '')
                            except (RuntimeError, OSError, SystemError) as e:
                                logger.warning(f"remove_variables_from_layer: setLayerVariable failed for {key}: {e}")


      

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
    
    def _ensure_db_directory(self):
        """
        Ensure database directory exists, create if missing.
        
        Returns:
            bool: True if directory exists or was created, False on error
        """
        db_dir = os.path.dirname(self.db_file_path)
        if not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"Created database directory: {db_dir}")
                return True
            except OSError as error:
                error_msg = f"Could not create database directory {db_dir}: {error}"
                logger.error(error_msg)
                iface.messageBar().pushCritical("FilterMate", error_msg)
                return False
        return True
    
    def _create_db_file(self, crs):
        """
        Create Spatialite database file if it doesn't exist.
        
        Args:
            crs: QgsCoordinateReferenceSystem for database creation
            
        Returns:
            bool: True if file exists or was created, False on error
        """
        if os.path.exists(self.db_file_path):
            return True
            
        memory_uri = 'NoGeometry?field=plugin_name:string(255,0)&field=_created_at:date(0,0)&field=_updated_at:date(0,0)&field=_version:string(255,0)'
        layer_name = 'filterMate_db'
        layer = QgsVectorLayer(memory_uri, layer_name, "memory")
        
        try:
            # Use modern QgsVectorFileWriter.create() instead of deprecated writeAsVectorFormat()
            save_options = QgsVectorFileWriter.SaveVectorOptions()
            save_options.driverName = "SQLite"
            save_options.fileEncoding = "utf-8"
            save_options.datasourceOptions = ["SPATIALITE=YES", "SQLITE_MAX_LENGTH=100000000"]
            
            writer = QgsVectorFileWriter.create(
                self.db_file_path,
                layer.fields(),
                layer.wkbType(),
                crs,
                QgsCoordinateTransformContext(),
                save_options
            )
            
            if writer.hasError() != QgsVectorFileWriter.NoError:
                logger.error(f"Error creating database file: {writer.errorMessage()}")
                return False
            
            del writer  # Ensure file is closed
            return True
        except Exception as error:
            error_msg = f"Failed to create database file {self.db_file_path}: {error}"
            logger.error(error_msg)
            iface.messageBar().pushCritical("FilterMate", error_msg)
            return False
    
    def _initialize_schema(self, cursor, project_settings):
        """
        Initialize database schema with fresh tables and project entry.
        
        Args:
            cursor: Database cursor
            project_settings: Project configuration dictionary
        """
        cursor.execute("""INSERT INTO filterMate_db VALUES(1, '{plugin_name}', datetime(), datetime(), '{version}');""".format(
            plugin_name='FilterMate',
            version='1.6'
        ))

        cursor.execute("""CREATE TABLE fm_projects (
                        project_id VARYING CHARACTER(255) NOT NULL PRIMARY KEY,
                        _created_at DATETIME NOT NULL,
                        _updated_at DATETIME NOT NULL,
                        project_name VARYING CHARACTER(255) NOT NULL,
                        project_path VARYING CHARACTER(255) NOT NULL,
                        project_settings TEXT NOT NULL);
                        """)

        cursor.execute("""CREATE TABLE fm_subset_history (
                        id VARYING CHARACTER(255) NOT NULL PRIMARY KEY,
                        _updated_at DATETIME NOT NULL,
                        fk_project VARYING CHARACTER(255) NOT NULL,
                        layer_id VARYING CHARACTER(255) NOT NULL,
                        layer_source_id VARYING CHARACTER(255) NOT NULL,
                        seq_order INTEGER NOT NULL,
                        subset_string TEXT NOT NULL,
                        FOREIGN KEY (fk_project)  
                        REFERENCES fm_projects(project_id));
                        """)
        
        cursor.execute("""CREATE TABLE fm_project_layers_properties (
                        id VARYING CHARACTER(255) NOT NULL PRIMARY KEY,
                        _updated_at DATETIME NOT NULL,
                        fk_project VARYING CHARACTER(255) NOT NULL,
                        layer_id VARYING CHARACTER(255) NOT NULL,
                        meta_type VARYING CHARACTER(255) NOT NULL,
                        meta_key VARYING CHARACTER(255) NOT NULL,
                        meta_value TEXT NOT NULL,
                        FOREIGN KEY (fk_project)  
                        REFERENCES fm_projects(project_id),
                        CONSTRAINT property_unicity
                        UNIQUE(fk_project, layer_id, meta_type, meta_key) ON CONFLICT REPLACE);
                        """)
        
        # Create indexes for better query performance
        cursor.execute("""CREATE INDEX IF NOT EXISTS idx_layer_properties_lookup 
                        ON fm_project_layers_properties(fk_project, layer_id, meta_type);""")
        
        cursor.execute("""CREATE INDEX IF NOT EXISTS idx_layer_properties_by_project 
                        ON fm_project_layers_properties(fk_project);""")
        
        cursor.execute("""CREATE INDEX IF NOT EXISTS idx_subset_history_by_project 
                        ON fm_subset_history(fk_project, layer_id);""")
        
        logger.info("✓ Created database indexes for optimized queries")
        
        self.project_uuid = uuid.uuid4()
    
        cursor.execute("""INSERT INTO fm_projects VALUES('{project_id}', datetime(), datetime(), '{project_name}', '{project_path}', '{project_settings}');""".format(
            project_id=self.project_uuid,
            project_name=self.project_file_name,
            project_path=self.project_file_path,
            project_settings=json.dumps(project_settings).replace("'", "''")
        ))

        # Set the project UUID for newly initialized database
        QgsExpressionContextUtils.setProjectVariable(self.PROJECT, 'filterMate_db_project_uuid', self.project_uuid)
    
    def _migrate_schema_if_needed(self, cursor):
        """
        Migrate database schema if needed (add fm_subset_history table for v1.6+).
        
        Args:
            cursor: Database cursor
            
        Returns:
            bool: True if subset history table exists
        """
        cursor.execute("""SELECT count(*) FROM sqlite_master WHERE type='table' AND name='fm_subset_history';""")
        subset_history_exists = cursor.fetchone()[0] > 0
        
        if not subset_history_exists:
            logger.info("Migrating database: creating fm_subset_history table")
            cursor.execute("""CREATE TABLE fm_subset_history (
                            id VARYING CHARACTER(255) NOT NULL PRIMARY KEY,
                            _updated_at DATETIME NOT NULL,
                            fk_project VARYING CHARACTER(255) NOT NULL,
                            layer_id VARYING CHARACTER(255) NOT NULL,
                            layer_source_id VARYING CHARACTER(255) NOT NULL,
                            seq_order INTEGER NOT NULL,
                            subset_string TEXT NOT NULL,
                            FOREIGN KEY (fk_project)  
                            REFERENCES fm_projects(project_id));
                            """)
            logger.info("Migration completed: fm_subset_history table created")
            
        return subset_history_exists
    
    def _load_or_create_project(self, cursor, project_settings):
        """
        Load existing project from database or create new entry.
        
        Args:
            cursor: Database cursor
            project_settings: Project configuration dictionary
        """
        # Check if this project exists
        cursor.execute("""SELECT * FROM fm_projects WHERE project_name = '{project_name}' AND project_path = '{project_path}' LIMIT 1;""".format(
            project_name=self.project_file_name,
            project_path=self.project_file_path
        ))

        results = cursor.fetchall()

        if len(results) == 1:
            result = results[0]
            project_settings_str = result[-1].replace("''", "'")
            self.project_uuid = result[0]
            self.CONFIG_DATA["CURRENT_PROJECT"] = json.loads(project_settings_str)
            QgsExpressionContextUtils.setProjectVariable(self.PROJECT, 'filterMate_db_project_uuid', self.project_uuid)
        else:
            self.project_uuid = uuid.uuid4()
            cursor.execute("""INSERT INTO fm_projects VALUES('{project_id}', datetime(), datetime(), '{project_name}', '{project_path}', '{project_settings}');""".format(
                project_id=self.project_uuid,
                project_name=self.project_file_name,
                project_path=self.project_file_path,
                project_settings=json.dumps(project_settings).replace("'", "''")
            ))
            QgsExpressionContextUtils.setProjectVariable(self.PROJECT, 'filterMate_db_project_uuid', self.project_uuid)

    def init_filterMate_db(self):
        """
        Initialize FilterMate Spatialite database with required schema.
        
        Creates database file and tables if they don't exist. Sets up schema for
        storing project configurations, layer properties, and datasource information.
        
        Tables created:
        - fm_projects: Project metadata and UUIDs
        - fm_project_layers_properties: Layer filtering/export settings
        - fm_project_datasources: Data source connection info
        
        Notes:
            - Database location: <project_dir>/.filterMate/<project_name>.db
            - Enables Spatialite extension for spatial operations
            - Idempotent: safe to call multiple times
            - Sets up project UUID in QGIS variables
            - Creates directory structure if missing
        """

        if self.PROJECT is not None:

            self.project_file_name = os.path.basename(self.PROJECT.absoluteFilePath())
            self.project_file_path = self.PROJECT.absolutePath()
            
            # Ensure database directory exists
            if not self._ensure_db_directory():
                return

            logger.debug(f"Database file path: {self.db_file_path}")

            if self.CONFIG_DATA["APP"]["OPTIONS"]["FRESH_RELOAD_FLAG"] is True:
                try: 
                    os.remove(self.db_file_path)
                    self.CONFIG_DATA["APP"]["OPTIONS"]["FRESH_RELOAD_FLAG"] = False
                    with open(ENV_VARS["CONFIG_JSON_PATH"], 'w') as outfile:
                        outfile.write(json.dumps(self.CONFIG_DATA, indent=4))  
                except OSError as error: 
                    logger.error(f"Failed to remove database file: {error}")
            
            project_settings = self.CONFIG_DATA["CURRENT_PROJECT"]
            logger.debug(f"Project settings: {project_settings}")

            # Create database file if missing
            crs = QgsCoordinateReferenceSystem("epsg:4326")
            if not self._create_db_file(crs):
                return
            
            try:
                conn = self.get_spatialite_connection()
                if conn is None:
                    error_msg = "Cannot initialize FilterMate database: connection failed"
                    logger.error(error_msg)
                    iface.messageBar().pushCritical("FilterMate", error_msg)
                    return
            except Exception as e:
                error_msg = f"Critical error connecting to database: {str(e)}"
                logger.error(error_msg)
                iface.messageBar().pushCritical("FilterMate", error_msg)
                return

            try:
                with conn:
                    cur = conn.cursor()
                    cur.execute("""PRAGMA foreign_keys = ON;""")
                    
                    # Check if database is already initialized
                    cur.execute("""SELECT count(*) FROM sqlite_master WHERE type='table' AND name='fm_projects';""")
                    tables_exist = cur.fetchone()[0] > 0
                    
                    if not tables_exist:
                        # Initialize fresh schema
                        self._initialize_schema(cur, project_settings)
                        conn.commit()
                    else:
                        # Database already initialized - migrate if needed
                        self._migrate_schema_if_needed(cur)
                        
                        # Load or create project entry
                        self._load_or_create_project(cur, project_settings)
                        conn.commit()

            except Exception as e:
                error_msg = f"Error during database initialization: {str(e)}"
                logger.error(error_msg)
                iface.messageBar().pushCritical("FilterMate", error_msg)
                return
            finally:
                if conn:
                    try:
                        cur.close()
                        conn.close()
                    except (OSError, AttributeError, sqlite3.Error) as e:
                        logger.debug(f"Error closing database connection: {e}")
            
            # Configure FavoritesManager to use SQLite database
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
        
        global ENV_VARS

        if self.dockwidget is not None:
            self.CONFIG_DATA = self.dockwidget.CONFIG_DATA
            conn = None
            cur = None
            try:
                conn = self.get_spatialite_connection()
                if conn is None:
                    return
                cur = conn.cursor()

                if name is not None:
                    self.project_file_name = name
                    self.project_file_path = self.PROJECT.absolutePath()    

                project_settings = self.CONFIG_DATA["CURRENT_PROJECT"]    

                # Use parameterized query
                cur.execute(
                    """UPDATE fm_projects SET 
                       _updated_at = datetime(),
                       project_name = ?,
                       project_path = ?,
                       project_settings = ?
                       WHERE project_id = ?""",
                    (self.project_file_name, self.project_file_path, 
                     json.dumps(project_settings), str(self.project_uuid))
                )
                conn.commit()
            finally:
                if cur:
                    cur.close()
                if conn:
                    conn.close()

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
            task_name (str): Type of task completed ('add_layers', 'remove_layers', etc.)
            
        Notes:
            - Updates dockwidget's PROJECT_LAYERS reference
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
        It retries a few times with increasing delays if layers aren't ready yet.
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
        """
        if self.dockwidget is None or not self.dockwidget.widgets_initialized:
            logger.debug("Cannot refresh UI: dockwidget not initialized")
            return
        
        # CRITICAL: Verify PROJECT_LAYERS has layers before attempting refresh
        if len(self.PROJECT_LAYERS) == 0:
            logger.warning("Cannot refresh UI: PROJECT_LAYERS is still empty - layer tasks not yet completed")
            return
            
        logger.info(f"Forcing complete UI refresh after project load with {len(self.PROJECT_LAYERS)} layers")
        
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

            
        



    def can_cast(self, dest_type, source_value):
        """
        Check if a value can be cast to a destination type.
        Delegates to centralized type_utils.can_cast().
        """
        return can_cast(dest_type, source_value)


    def return_typped_value(self, value_as_string, action=None):
        """
        Convert string value to typed value with type detection.
        Delegates to centralized type_utils.return_typed_value().
        """
        return return_typed_value(value_as_string, action)


def zoom_to_features(layer, t0):
    canvas = iface.mapCanvas()
    canvas.setExtent(layer.extent())
    canvas.refresh()

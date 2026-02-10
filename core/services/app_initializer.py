"""
Application Initializer - Phase 4.4 God Class Reduction

Handles FilterMate application initialization and startup logic.
Extracted from FilterMateApp.run() (~430 lines).

This service is responsible for:
1. Database initialization and health checks
2. UI profile detection based on screen resolution
3. Dockwidget creation and configuration
4. Widget initialization synchronization
5. Layer loading on startup
6. Signal connections (layer store, dockwidget)
7. Recovery mechanisms for failed layer loading

v4.4: Strangler Fig Pattern - New service with fallback to FilterMateApp legacy code.
"""

from typing import Callable, List, Any
from qgis.PyQt.QtCore import QTimer
from qgis.PyQt.QtWidgets import QApplication
from qgis.core import QgsVectorLayer, QgsProject
from qgis.utils import iface
import sip

from ..ports.qgis_port import get_qgis_factory
from ...infrastructure.logging import get_app_logger
from ...infrastructure.feedback import show_warning, show_info
from ...ui.config import UIConfig, DisplayProfile

logger = get_app_logger()


class AppInitializer:
    """
    Manages FilterMate application initialization.

    Responsibilities:
    - Database setup and health checks
    - UI profile selection (normal/compact)
    - Dockwidget creation and display
    - Widget initialization synchronization
    - Initial layer loading with retry mechanisms
    - Signal connection management
    - Recovery for failed initialization

    Uses dependency injection callbacks to avoid circular dependencies
    and enable testing without QGIS UI dependencies.
    """

    def __init__(
        self,
        # Callbacks for database operations
        init_filtermate_db_callback=None,
        get_spatialite_connection_callback=None,
        cleanup_corrupted_layer_filters_callback=None,
        # Callbacks for layer management
        filter_usable_layers_callback=None,
        manage_task_callback=None,
        # Callbacks for accessing state
        get_project_layers_callback=None,
        get_config_data_callback=None,
        get_project_callback=None,
        get_plugin_dir_callback=None,
        get_dock_position_callback=None,
        get_iface_callback=None,
        # Callbacks for component access
        get_dockwidget_callback=None,
        set_dockwidget_callback=None,
        get_task_orchestrator_callback=None,
        get_favorites_manager_callback=None,
        # Callbacks for signal state
        get_signals_connected_callback=None,
        set_signals_connected_callback=None,
        get_dockwidget_signals_connected_callback=None,
        set_dockwidget_signals_connected_callback=None,
        get_map_layer_store_callback=None,
        set_map_layer_store_callback=None,
        # Callbacks for other operations
        on_widgets_initialized_callback=None,
        on_layers_added_callback=None,
        update_undo_redo_buttons_callback=None,
        save_variables_from_layer_callback=None,
        remove_variables_from_layer_callback=None,
        save_project_variables_callback=None,
    ):
        """
        Initialize AppInitializer with dependency injection.

        Args:
            init_filtermate_db_callback: Callback to initialize database
            get_spatialite_connection_callback: Callback to get database connection
            cleanup_corrupted_layer_filters_callback: Callback to clean corrupted filters
            filter_usable_layers_callback: Callback to filter usable layers
            manage_task_callback: Callback to manage tasks
            get_project_layers_callback: Callback to get PROJECT_LAYERS dict
            get_config_data_callback: Callback to get CONFIG_DATA dict
            get_project_callback: Callback to get QgsProject instance
            get_plugin_dir_callback: Callback to get plugin directory path
            get_dock_position_callback: Callback to get dock position
            get_iface_callback: Callback to get iface instance
            get_dockwidget_callback: Callback to get dockwidget instance
            set_dockwidget_callback: Callback to set dockwidget instance
            get_task_orchestrator_callback: Callback to get TaskOrchestrator
            get_favorites_manager_callback: Callback to get FavoritesManager
            get_signals_connected_callback: Callback to get _signals_connected flag
            set_signals_connected_callback: Callback to set _signals_connected flag
            get_dockwidget_signals_connected_callback: Callback to get _dockwidget_signals_connected flag
            set_dockwidget_signals_connected_callback: Callback to set _dockwidget_signals_connected flag
            get_map_layer_store_callback: Callback to get MapLayerStore
            set_map_layer_store_callback: Callback to set MapLayerStore
            on_widgets_initialized_callback: Callback when widgets are initialized
            on_layers_added_callback: Callback when layers are added
            update_undo_redo_buttons_callback: Callback to update undo/redo buttons
            save_variables_from_layer_callback: Callback to save layer variables
            remove_variables_from_layer_callback: Callback to remove layer variables
            save_project_variables_callback: Callback to save project variables
        """
        self._init_filtermate_db = init_filtermate_db_callback
        self._get_spatialite_connection = get_spatialite_connection_callback
        self._cleanup_corrupted_layer_filters = cleanup_corrupted_layer_filters_callback
        self._filter_usable_layers = filter_usable_layers_callback
        self._manage_task = manage_task_callback
        self._get_project_layers = get_project_layers_callback
        self._get_config_data = get_config_data_callback
        self._get_project = get_project_callback
        self._get_plugin_dir = get_plugin_dir_callback
        self._get_dock_position = get_dock_position_callback
        self._get_iface = get_iface_callback or (lambda: iface)
        self._get_dockwidget = get_dockwidget_callback
        self._set_dockwidget = set_dockwidget_callback
        self._get_task_orchestrator = get_task_orchestrator_callback
        self._get_favorites_manager = get_favorites_manager_callback
        self._get_signals_connected = get_signals_connected_callback
        self._set_signals_connected = set_signals_connected_callback
        self._get_dockwidget_signals_connected = get_dockwidget_signals_connected_callback
        self._set_dockwidget_signals_connected = set_dockwidget_signals_connected_callback
        self._get_map_layer_store = get_map_layer_store_callback
        self._set_map_layer_store = set_map_layer_store_callback
        self._on_widgets_initialized = on_widgets_initialized_callback
        self._on_layers_added = on_layers_added_callback
        self._update_undo_redo_buttons = update_undo_redo_buttons_callback
        self._save_variables_from_layer = save_variables_from_layer_callback
        self._remove_variables_from_layer = remove_variables_from_layer_callback
        self._save_project_variables = save_project_variables_callback

    def initialize_application(self, is_first_run: bool = True) -> bool:
        """
        Initialize and display the FilterMate dockwidget.

        Args:
            is_first_run: True if this is the first call to run(), False for subsequent calls

        Returns:
            bool: True if initialization succeeded, False otherwise
        """
        if is_first_run:
            return self._initialize_first_run()
        else:
            return self._reinitialize_existing()

    def _initialize_first_run(self) -> bool:
        """
        First-time initialization: create dockwidget and set up everything.

        Returns:
            bool: True if initialization succeeded
        """
        # Get project reference
        factory = get_qgis_factory()
        project = self._get_project() if self._get_project else factory.get_project()

        # Cleanup corrupted filters
        if self._cleanup_corrupted_layer_filters:
            from ...infrastructure.field_utils import cleanup_corrupted_layer_filters
            cleared_layers = cleanup_corrupted_layer_filters()  # Pass None to use all project layers
            if cleared_layers:
                show_warning(
                    f"Cleared corrupted filters from {len(cleared_layers)} layer(s). Please re-apply your filters."
                )

        # Get initial layers
        init_layers = None
        if self._filter_usable_layers:
            all_layers = list(project.mapLayers().values())
            init_layers = self._filter_usable_layers(all_layers)
            logger.info(f"FilterMate App.run(): Found {len(init_layers)} layers in project")

        # Initialize database
        logger.info("FilterMate App.run(): Starting init_filterMate_db()")
        if self._init_filtermate_db:
            self._init_filtermate_db()
        logger.info("FilterMate App.run(): init_filterMate_db() complete")

        # Database health check
        if not self._perform_database_health_check():
            return False

        # Initialize UI profile based on screen resolution
        self._initialize_ui_profile()

        # Create dockwidget
        if not self._create_dockwidget():
            return False

        # Connect dockwidget to widget initialization signals
        self._connect_widget_initialization_signals()

        # Force retranslation
        self._retranslate_ui()

        # Get dock position and show dockwidget
        dock_position = self._get_dock_position() if self._get_dock_position else 2  # Qt.LeftDockWidgetArea
        iface_obj = self._get_iface()
        dockwidget = self._get_dockwidget() if self._get_dockwidget else None

        if dockwidget:
            iface_obj.addDockWidget(dock_position, dockwidget)
            dockwidget.show()
            logger.info(f"FilterMate App.run(): DockWidget shown at position {dock_position}")

        # Process existing layers with retry mechanism
        if init_layers is not None and len(init_layers) > 0:
            self._process_initial_layers(init_layers)
        else:
            logger.info("FilterMate: Plugin started with empty project - waiting for layers to be added")
            show_info("Projet vide détecté. Ajoutez des couches vectorielles pour activer le plugin.")

        # Connect layer store signals
        self._connect_layer_store_signals()

        # Connect dockwidget signals
        self._connect_dockwidget_signals()

        return True

    def _reinitialize_existing(self) -> bool:
        """
        Reinitialize existing dockwidget: show it and refresh layers.

        Returns:
            bool: True if reinitialization succeeded
        """
        dockwidget = self._get_dockwidget() if self._get_dockwidget else None
        if not dockwidget:
            logger.warning("FilterMate: Dockwidget is None during reinit")
            return False

        logger.info("FilterMate: Dockwidget already exists, showing and refreshing layers")

        # Update project reference
        from ...config.config import init_env_vars, ENV_VARS
        init_env_vars()
        factory = get_qgis_factory()
        project = ENV_VARS.get("PROJECT") or factory.get_project()
        map_layer_store = project.layerStore()
        if self._set_map_layer_store:
            self._set_map_layer_store(map_layer_store)

        # Retranslate UI
        self._retranslate_ui()

        # Make sure the dockwidget is visible
        if not dockwidget.isVisible():
            dockwidget.show()

        # Check for new layers
        self._refresh_layers_if_needed(project)

        # Reconnect signals if needed
        self._connect_layer_store_signals()
        self._connect_dockwidget_signals()

        return True

    def _perform_database_health_check(self) -> bool:
        """
        Verify database is accessible.

        Returns:
            bool: True if database is healthy
        """
        try:
            if not self._get_spatialite_connection:
                logger.warning("No database connection callback available")
                return True  # Continue anyway

            db_conn = self._get_spatialite_connection()
            if db_conn is None:
                logger.error("Database health check failed: Cannot connect to Spatialite database")
                iface.messageBar().pushCritical(
                    "FilterMate - Erreur base de données",
                    "Impossible d'accéder à la base de données FilterMate. Vérifiez les permissions du répertoire du projet."
                )
                return False
            else:
                logger.info("Database health check: OK")
                db_conn.close()
                return True
        except Exception as db_err:
            logger.error(f"Database health check failed with exception: {db_err}", exc_info=True)
            iface.messageBar().pushCritical(
                "FilterMate - Erreur base de données",
                f"Erreur lors de la vérification de la base de données: {str(db_err)}"
            )
            return False

    def _initialize_ui_profile(self):
        """Initialize UI profile based on screen resolution."""
        try:
            screen = QApplication.primaryScreen()
            if screen:
                screen_geometry = screen.geometry()
                screen_width = screen_geometry.width()
                screen_height = screen_geometry.height()

                # Activate NORMAL mode for 1080p and above
                # COMPACT: Small screens (< 1920x1080) - laptops, tablets
                # NORMAL: Standard screens (≥ 1920x1080) - desktops, large laptops
                # Small screens (below 1080p) → COMPACT
                if screen_width < 1920 or screen_height < 1080:
                    UIConfig.set_profile(DisplayProfile.COMPACT)
                    logger.info(f"FilterMate: Using COMPACT profile for small screen {screen_width}x{screen_height}")
                # Standard and large screens (1080p+) → NORMAL
                else:
                    UIConfig.set_profile(DisplayProfile.NORMAL)
                    logger.info(f"FilterMate: Using NORMAL profile for resolution {screen_width}x{screen_height}")
            else:
                # Fallback to NORMAL (better for desktop QGIS)
                UIConfig.set_profile(DisplayProfile.NORMAL)
                logger.warning("FilterMate: Could not detect screen, using NORMAL profile (desktop default)")
        except Exception as e:
            logger.error(f"FilterMate: Error detecting screen resolution: {e}")
            UIConfig.set_profile(DisplayProfile.NORMAL)  # Fail-safe: NORMAL for desktop QGIS

    def _create_dockwidget(self) -> bool:
        """
        Create the FilterMateDockWidget.

        Returns:
            bool: True if creation succeeded
        """
        try:
            from ...filter_mate_dockwidget import FilterMateDockWidget

            project_layers = self._get_project_layers() if self._get_project_layers else {}
            plugin_dir = self._get_plugin_dir() if self._get_plugin_dir else ""
            config_data = self._get_config_data() if self._get_config_data else {}
            project = self._get_project() if self._get_project else QgsProject.instance()

            logger.info("FilterMate App.run(): Creating FilterMateDockWidget")
            dockwidget = FilterMateDockWidget(project_layers, plugin_dir, config_data, project)
            logger.info("FilterMate App.run(): FilterMateDockWidget created")

            if self._set_dockwidget:
                self._set_dockwidget(dockwidget)

            # Store reference to app in dockwidget for session management
            # Note: This creates a weak circular reference but is necessary for some features
            # dockwidget._app_ref = self (cannot do here since this is a service, not the app)

            # Pass favorites manager to dockwidget and update FavoritesController
            favorites_manager = self._get_favorites_manager() if self._get_favorites_manager else None
            if favorites_manager:
                dockwidget._favorites_manager = favorites_manager

                # Update FavoritesController with the correctly initialized manager
                # The controller was setup in dockwidget_widgets_configuration() BEFORE we could
                # attach the favorites_manager, so it may have created its own uninitialized instance
                if hasattr(dockwidget, 'favorites_controller') and dockwidget.favorites_controller:
                    controller = dockwidget.favorites_controller
                    # Use the dedicated sync method for clean signal handling
                    if hasattr(controller, 'sync_with_dockwidget_manager'):
                        controller.sync_with_dockwidget_manager()
                        logger.info(f"✓ FavoritesController synced via sync_with_dockwidget_manager() ({favorites_manager.count} favorites)")
                    else:
                        # Fallback for older controller versions
                        controller._favorites_manager = favorites_manager
                        # Connect to favorites_changed signal for UI updates
                        if hasattr(favorites_manager, 'favorites_changed'):
                            try:
                                favorites_manager.favorites_changed.disconnect(controller._on_favorites_loaded)
                            except (TypeError, RuntimeError):
                                pass  # Signal wasn't connected
                            favorites_manager.favorites_changed.connect(controller._on_favorites_loaded)
                        # Trigger initial UI update with loaded favorites
                        controller.update_indicator()
                        logger.info(f"✓ FavoritesController synchronized (fallback) ({favorites_manager.count} favorites)")

                if hasattr(dockwidget, '_update_favorite_indicator'):
                    dockwidget._update_favorite_indicator()
                logger.debug("FavoritesManager attached to DockWidget")

            return True
        except Exception as e:
            logger.error(f"Failed to create dockwidget: {e}", exc_info=True)
            return False

    def _connect_widget_initialization_signals(self):
        """Connect signals for widget initialization synchronization."""
        dockwidget = self._get_dockwidget() if self._get_dockwidget else None
        if not dockwidget:
            return

        # Connect to widgetsInitialized signal
        if self._on_widgets_initialized:
            dockwidget.widgetsInitialized.connect(self._on_widgets_initialized)
            logger.debug("widgetsInitialized signal connected to _on_widgets_initialized")

        # Also connect to TaskOrchestrator if available
        task_orchestrator = self._get_task_orchestrator() if self._get_task_orchestrator else None
        if task_orchestrator is not None:
            dockwidget.widgetsInitialized.connect(task_orchestrator.on_widgets_initialized)
            logger.debug("widgetsInitialized signal connected to TaskOrchestrator")

        # REMOVED - projectLayersReady signal is now connected ONLY in
        # ui/controllers/integration.py to avoid duplicate handler execution.
        # The ControllerIntegration._on_project_layers_ready() method properly
        # delegates to ExportingController.refresh_layers() and LayerSyncController.on_layers_ready()
        # See: integration.py line 406 and line 719 for the unified handler.

        # CRITICAL FIX: Signal may have been emitted BEFORE connection
        if hasattr(dockwidget, 'widgets_initialized') and dockwidget.widgets_initialized:
            logger.info("Widgets already initialized before signal connection - syncing state")
            if self._on_widgets_initialized:
                self._on_widgets_initialized()
            if task_orchestrator is not None:
                task_orchestrator.on_widgets_initialized()

    def _retranslate_ui(self):
        """Force retranslation to ensure tooltips/text use current translator."""
        dockwidget = self._get_dockwidget() if self._get_dockwidget else None
        if not dockwidget:
            return

        try:
            if hasattr(dockwidget, 'retranslateUi'):
                dockwidget.retranslateUi(dockwidget)
                logger.info("FilterMate: DockWidget UI retranslated with active locale")
            if hasattr(dockwidget, 'retranslate_dynamic_tooltips'):
                dockwidget.retranslate_dynamic_tooltips()
                logger.info("FilterMate: Dynamic tooltips refreshed with active locale")
        except Exception as e:
            logger.warning(f"FilterMate: Failed to retranslate DockWidget UI: {e}")

    def _process_initial_layers(self, init_layers: List[QgsVectorLayer]):
        """
        Process existing layers with retry mechanism.

        Args:
            init_layers: List of layers to process
        """
        # Wait for widget initialization before adding layers
        def wait_for_widget_initialization(layers_to_add):
            """Wait for widgets to be fully initialized before adding layers."""
            max_retries = 10  # Max 3 seconds (10 * 300ms)
            retry_count = 0

            dockwidget = self._get_dockwidget() if self._get_dockwidget else None

            def check_and_add():
                nonlocal retry_count
                if dockwidget and dockwidget.widgets_initialized:
                    logger.info(f"Widgets initialized, adding {len(layers_to_add)} layers")
                    if self._manage_task:
                        self._manage_task('add_layers', layers_to_add)
                elif retry_count < max_retries:
                    retry_count += 1
                    logger.debug(f"Waiting for widget initialization (attempt {retry_count}/{max_retries})")
                    QTimer.singleShot(300, check_and_add)
                else:
                    logger.warning("Widget initialization timeout, forcing add_layers anyway")
                    if self._manage_task:
                        self._manage_task('add_layers', layers_to_add)

            check_and_add()

        # Use weakref to prevent access violations
        QTimer.singleShot(600, lambda: wait_for_widget_initialization(init_layers))

        # Safety timer to ensure UI is enabled
        QTimer.singleShot(5000, self._ensure_ui_enabled_after_startup)

    def _ensure_ui_enabled_after_startup(self):
        """
        Safety check to ensure UI is enabled after startup.

        This prevents UI from being left in disabled/grey state on startup.
        """
        dockwidget = self._get_dockwidget() if self._get_dockwidget else None
        project_layers = self._get_project_layers() if self._get_project_layers else {}
        project = self._get_project() if self._get_project else QgsProject.instance()

        if not dockwidget:
            logger.warning("Safety timer: Dockwidget is None, cannot check UI state")
            return

        # Check if layers were successfully loaded
        if len(project_layers) > 0:
            logger.info(f"Safety timer: Task completed successfully with {len(project_layers)} layers, forcing UI refresh")
            if hasattr(dockwidget, 'get_project_layers_from_app'):
                dockwidget.get_project_layers_from_app(project_layers, project)
        else:
            # Task may have failed - try recovery
            logger.warning("Safety timer: PROJECT_LAYERS still empty after 5s, attempting recovery")
            self._attempt_layer_recovery()

    def _attempt_layer_recovery(self):
        """Attempt to recover from failed layer loading."""
        project = self._get_project() if self._get_project else QgsProject.instance()
        all_layers = list(project.mapLayers().values())

        logger.warning(f"Recovery: Total layers in project: {len(all_layers)}")

        if not self._filter_usable_layers:
            logger.error("Recovery: No filter_usable_layers callback available")
            return

        current_layers = self._filter_usable_layers(all_layers)

        # Include ALL valid vector layers
        all_valid_vector_layers = [
            l for l in all_layers
            if isinstance(l, QgsVectorLayer)
            and l.isValid()
            and not sip.isdeleted(l)
        ]
        missed_layers = [l for l in all_valid_vector_layers if l not in current_layers]

        if missed_layers:
            logger.warning(f"Recovery: Found {len(missed_layers)} valid vector layers that were filtered - forcing inclusion")
            for layer in missed_layers:
                provider = layer.providerType()
                logger.info(f"  Force-adding missed layer: {layer.name()} (provider={provider})")
            current_layers.extend(missed_layers)

        if len(current_layers) > 0:
            logger.info(f"Recovery: Found {len(current_layers)} usable layers, retrying add_layers")
            if self._manage_task:
                QTimer.singleShot(100, lambda: self._manage_task('add_layers', current_layers))
            # Set another safety timer
            QTimer.singleShot(5000, lambda: self._ensure_ui_enabled_final(0))
        else:
            logger.warning(f"Recovery: No usable layers found from {len(all_layers)} total layers")
            # Update indicator to show waiting state
            dockwidget = self._get_dockwidget() if self._get_dockwidget else None
            if dockwidget and hasattr(dockwidget, 'backend_indicator_label') and dockwidget.backend_indicator_label:
                dockwidget.backend_indicator_label.setText("...")

    def _ensure_ui_enabled_final(self, retry_count=0):
        """
        Final safety check after recovery attempt.

        Args:
            retry_count: Number of retries already attempted (max 5)
        """
        MAX_RETRIES = 5

        dockwidget = self._get_dockwidget() if self._get_dockwidget else None
        project_layers = self._get_project_layers() if self._get_project_layers else {}
        project = self._get_project() if self._get_project else QgsProject.instance()

        if not dockwidget:
            return

        if len(project_layers) > 0:
            logger.info("Final safety timer: Layers loaded, refreshing UI")
            if hasattr(dockwidget, 'get_project_layers_from_app'):
                dockwidget.get_project_layers_from_app(project_layers, project)
        elif retry_count < MAX_RETRIES:
            logger.info(f"Final safety timer: Deferring check (retry {retry_count + 1}/{MAX_RETRIES})")
            QTimer.singleShot(3000, lambda: self._ensure_ui_enabled_final(retry_count + 1))
        else:
            logger.error("Final safety timer: Failed to load layers after recovery")
            iface.messageBar().pushWarning(
                "FilterMate",
                "Échec du chargement des couches. Utilisez F5 pour forcer le rechargement."
            )

    def _refresh_layers_if_needed(self, project: QgsProject):
        """
        Check for new layers and refresh if needed.

        Args:
            project: QgsProject instance
        """
        project_layers = self._get_project_layers() if self._get_project_layers else {}
        current_project_layers = list(project.mapLayers().values())

        if not current_project_layers:
            return

        # Filter to get only layers not already in PROJECT_LAYERS
        new_layers = [layer for layer in current_project_layers
                     if layer.id() not in project_layers]

        if new_layers:
            logger.info(f"FilterMate: Found {len(new_layers)} new layers to add")
            if self._filter_usable_layers and self._manage_task:
                usable = self._filter_usable_layers(new_layers)
                QTimer.singleShot(300, lambda: self._safe_add_layers(usable))
        else:
            # No new layers, but update UI if it's empty
            if len(project_layers) == 0 and len(current_project_layers) > 0:
                logger.info("FilterMate: PROJECT_LAYERS is empty but project has layers, refreshing")
                if self._filter_usable_layers and self._manage_task:
                    usable_layers = self._filter_usable_layers(current_project_layers)
                    QTimer.singleShot(300, lambda: self._safe_add_layers(usable_layers))

    def _safe_add_layers(self, usable_layers: List[QgsVectorLayer]):
        """
        Safely add layers, filtering out deleted ones.

        Args:
            usable_layers: List of layers to add
        """
        # Re-filter to remove layers deleted during the delay
        still_valid = [l for l in usable_layers if l is not None and not sip.isdeleted(l)]
        if still_valid and self._manage_task:
            self._manage_task('add_layers', still_valid)

    def _connect_layer_store_signals(self):
        """Connect layer store signals for layer management."""
        signals_connected = self._get_signals_connected() if self._get_signals_connected else False

        if signals_connected:
            return  # Already connected

        map_layer_store = self._get_map_layer_store() if self._get_map_layer_store else None
        if not map_layer_store:
            logger.warning("Cannot connect layer store signals: MapLayerStore is None")
            return

        logger.debug("Connecting layer store signals (layersAdded, layersWillBeRemoved...)")

        # Use layersAdded (batch) instead of layerWasAdded (per layer)
        if self._on_layers_added and self._manage_task:
            map_layer_store.layersAdded.connect(self._on_layers_added)
            map_layer_store.layersWillBeRemoved.connect(lambda layers: self._manage_task('remove_layers', layers))
            map_layer_store.allLayersRemoved.connect(lambda: self._manage_task('remove_all_layers'))

        if self._set_signals_connected:
            self._set_signals_connected(True)
        logger.debug("Layer store signals connected successfully")

    def _connect_dockwidget_signals(self):
        """Connect dockwidget signals for task management."""
        dockwidget_signals_connected = self._get_dockwidget_signals_connected() if self._get_dockwidget_signals_connected else False

        if dockwidget_signals_connected:
            return  # Already connected

        dockwidget = self._get_dockwidget() if self._get_dockwidget else None
        project = self._get_project() if self._get_project else QgsProject.instance()

        if not dockwidget:
            logger.warning("Cannot connect dockwidget signals: dockwidget is None")
            return

        # Connect task launching signal
        if self._manage_task:
            dockwidget.launchingTask.connect(lambda x: self._manage_task(x))

        # Connect current layer changed signal
        if self._update_undo_redo_buttons:
            dockwidget.currentLayerChanged.connect(self._update_undo_redo_buttons)

        # Connect variable management signals
        if self._save_variables_from_layer and self._remove_variables_from_layer:
            dockwidget.resettingLayerVariableOnError.connect(
                lambda layer, properties: self._safe_layer_operation(layer, properties, self._remove_variables_from_layer)
            )
            dockwidget.settingLayerVariable.connect(
                lambda layer, properties: self._safe_layer_operation(layer, properties, self._save_variables_from_layer)
            )
            dockwidget.resettingLayerVariable.connect(
                lambda layer, properties: self._safe_layer_operation(layer, properties, self._remove_variables_from_layer)
            )

        # Connect project variables signal
        if self._save_project_variables:
            dockwidget.settingProjectVariables.connect(self._save_project_variables)
            project.fileNameChanged.connect(lambda: self._save_project_variables())

        if self._set_dockwidget_signals_connected:
            self._set_dockwidget_signals_connected(True)

        logger.debug("Dockwidget signals connected successfully")

    def _safe_layer_operation(self, layer: QgsVectorLayer, properties: Any, operation: Callable):
        """
        Safely execute a layer operation by deferring to Qt event loop.

        CRASH FIX: Signal handlers receive layer objects that may become invalid.
        This wrapper defers execution to let Qt stabilize.

        Args:
            layer: Layer object from signal (may be stale)
            properties: Properties to pass to operation
            operation: Function to call with (fresh_layer, properties)
        """
        if not layer:
            return

        # Extract layer ID immediately
        layer_id = layer.id()

        def deferred_operation():
            # Re-fetch fresh layer reference
            project = self._get_project() if self._get_project else QgsProject.instance()
            fresh_layer = project.mapLayer(layer_id)

            if fresh_layer and fresh_layer.isValid() and not sip.isdeleted(fresh_layer):
                operation(fresh_layer, properties)
            else:
                logger.warning(f"Layer {layer_id} no longer valid in deferred operation")

        # Defer to event loop
        QTimer.singleShot(0, deferred_operation)

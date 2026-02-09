"""
FilterMate DockWidget Orchestrator.

DEPRECATED (v6.0 Phase 1.4): Not used at runtime. Marked for removal in Phase 6.
Kept only for test backward compatibility until Phase 6 completes.

Minimal orchestrator that coordinates between extracted components.
This is the target structure after Phase 6 refactoring.

Story: MIG-087
Phase: 6 - God Class DockWidget Migration
Target: ~500 lines (from ~13,000)

Components coordinated:
- Layout managers (splitter, dimensions, spacing, action bar)
- Styling managers (theme, icons, buttons)
- Controllers (filtering, exploring, exporting, config, etc.)
- Signal management (signal manager, layer handler)
- Services (via controllers and dependency injection)
"""

from typing import TYPE_CHECKING, Dict, Any, List
import logging
import warnings

try:
    from qgis.PyQt.QtWidgets import QDockWidget, QWidget
    from qgis.PyQt.QtCore import Qt, pyqtSignal, QTimer
    HAS_QGIS = True
except ImportError:
    from unittest.mock import MagicMock
    QDockWidget = MagicMock
    QWidget = MagicMock
    Qt = MagicMock()
    pyqtSignal = lambda *args: MagicMock()
    QTimer = MagicMock
    HAS_QGIS = False

if TYPE_CHECKING:
    from filter_mate_app import FilterMateApp

logger = logging.getLogger(__name__)


class DockWidgetOrchestrator:
    """
    Orchestrator for the FilterMate DockWidget.
    
    Acts as a coordination layer between:
    - UI components (via dockwidget)
    - Layout managers
    - Style managers
    - Controllers
    - Services
    
    This class should contain:
    - Initialization and dependency injection
    - Component lifecycle management
    - Public API for external access
    - Deprecated façades for backward compatibility
    
    The orchestrator DOES NOT contain business logic - all logic
    is delegated to the appropriate controller or service.
    """
    
    # =========================================================================
    # Signals
    # =========================================================================
    
    # These are defined at class level but connected via signal manager
    # filter_applied = pyqtSignal(str, str)  # layer_id, expression
    # export_completed = pyqtSignal(str)  # output_path
    
    def __init__(
        self,
        dockwidget: QDockWidget,
        app: 'FilterMateApp',
        iface,
    ) -> None:
        """
        Initialize the orchestrator.
        
        Args:
            dockwidget: The actual QDockWidget instance (with UI setup)
            app: Main FilterMate application
            iface: QGIS interface
        """
        self._dockwidget = dockwidget
        self._app = app
        self._iface = iface
        
        # Component references (initialized lazily)
        self._layout_managers: Dict[str, Any] = {}
        self._style_managers: Dict[str, Any] = {}
        self._controllers: Dict[str, Any] = {}
        self._services: Dict[str, Any] = {}
        
        # Signal management
        self._signal_manager = None
        self._layer_signal_handler = None
        
        # State
        self._initialized = False
        self._setup_complete = False
        
        logger.debug("DockWidgetOrchestrator created")
    
    def __repr__(self) -> str:
        return (
            f"DockWidgetOrchestrator("
            f"initialized={self._initialized}, "
            f"controllers={len(self._controllers)}, "
            f"managers={len(self._layout_managers) + len(self._style_managers)})"
        )
    
    # =========================================================================
    # Initialization
    # =========================================================================
    
    def initialize(self) -> bool:
        """
        Initialize all components.
        
        Returns:
            bool: True if initialization successful
        """
        if self._initialized:
            logger.warning("Orchestrator already initialized")
            return True
        
        try:
            self._init_signal_management()
            self._init_layout_managers()
            self._init_style_managers()
            self._init_services()
            self._init_controllers()
            
            self._initialized = True
            logger.debug("DockWidgetOrchestrator initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Orchestrator initialization failed: {e}")
            return False
    
    def setup(self) -> bool:
        """
        Perform setup after initialization.
        
        Returns:
            bool: True if setup successful
        """
        if not self._initialized:
            logger.error("Cannot setup: orchestrator not initialized")
            return False
        
        if self._setup_complete:
            logger.warning("Setup already complete")
            return True
        
        try:
            # Setup layout managers
            for manager in self._layout_managers.values():
                if hasattr(manager, 'setup'):
                    manager.setup()
            
            # Setup style managers
            for manager in self._style_managers.values():
                if hasattr(manager, 'setup'):
                    manager.setup()
            
            # Setup controllers
            for controller in self._controllers.values():
                if hasattr(controller, 'setup'):
                    controller.setup()
            
            # Connect signals
            if self._signal_manager:
                self._signal_manager.connect_widgets_signals()
            
            self._setup_complete = True
            logger.info("DockWidgetOrchestrator setup complete")
            return True
            
        except Exception as e:
            logger.error(f"Orchestrator setup failed: {e}")
            return False
    
    def _init_signal_management(self) -> None:
        """Initialize signal manager and handlers."""
        from ..adapters.qgis.signals import SignalManager, LayerSignalHandler        
        self._signal_manager = SignalManager(self._dockwidget)
        self._layer_signal_handler = LayerSignalHandler(
            self._dockwidget,
            self._signal_manager
        )
        logger.debug("Signal management initialized")
    
    def _init_layout_managers(self) -> None:
        """Initialize layout managers."""
        from ui.layout import (
            SplitterManager,
            DimensionsManager,
            SpacingManager,
            ActionBarManager,
        )
        
        self._layout_managers = {
            'splitter': SplitterManager(self._dockwidget),
            'dimensions': DimensionsManager(self._dockwidget),
            'spacing': SpacingManager(self._dockwidget),
            'action_bar': ActionBarManager(self._dockwidget),
        }
        logger.debug(f"Layout managers initialized: {list(self._layout_managers.keys())}")
    
    def _init_style_managers(self) -> None:
        """Initialize styling managers."""
        from ui.styles import ThemeManager, IconManager, ButtonStyler
        
        self._style_managers = {
            'theme': ThemeManager(self._dockwidget),
            'icon': IconManager(self._dockwidget),
            'button': ButtonStyler(self._dockwidget),
        }
        logger.debug(f"Style managers initialized: {list(self._style_managers.keys())}")
    
    def _init_services(self) -> None:
        """Initialize business services."""
        from ..core.services import (
            BackendService,
            FilterService,
            FavoritesService,
            LayerService,
            PostgresSessionManager,
        )
        
        # These are the primary services used by controllers
        self._services = {
            'backend': BackendService(self._dockwidget),
            'filter': FilterService(self._dockwidget),
            'favorites': FavoritesService(self._dockwidget),
            'layer': LayerService(self._dockwidget),
            'postgres_session': PostgresSessionManager(self._dockwidget),
        }
        logger.debug(f"Services initialized: {list(self._services.keys())}")
    
    def _init_controllers(self) -> None:
        """Initialize UI controllers."""
        from .controllers import (
            FilteringController,
            ExploringController,
            ExportingController,
            ConfigController,
            BackendController,
            FavoritesController,
            LayerSyncController,
            PropertyController,
        )
        
        self._controllers = {
            'filtering': FilteringController(
                self._dockwidget,
                self._services.get('filter'),
            ),
            'exploring': ExploringController(self._dockwidget),
            'exporting': ExportingController(self._dockwidget),
            'config': ConfigController(self._dockwidget),
            'backend': BackendController(
                self._dockwidget,
                self._services.get('backend'),
            ),
            'favorites': FavoritesController(
                self._dockwidget,
                self._services.get('favorites'),
            ),
            'layer_sync': LayerSyncController(
                self._dockwidget,
                self._services.get('layer'),
            ),
            'property': PropertyController(self._dockwidget),
        }
        logger.debug(f"Controllers initialized: {list(self._controllers.keys())}")
    
    # =========================================================================
    # Public Properties
    # =========================================================================
    
    @property
    def dockwidget(self) -> QDockWidget:
        """Get the underlying dockwidget."""
        return self._dockwidget
    
    @property
    def app(self) -> 'FilterMateApp':
        """Get the main application."""
        return self._app
    
    @property
    def iface(self):
        """Get the QGIS interface."""
        return self._iface
    
    @property
    def signal_manager(self):
        """Get the signal manager."""
        return self._signal_manager
    
    @property
    def current_layer(self):
        """Get the currently selected layer."""
        controller = self._controllers.get('layer_sync')
        return controller.current_layer if controller else None
    
    @property
    def current_backend(self) -> str:
        """Get the current backend name."""
        controller = self._controllers.get('backend')
        return controller.current_backend if controller else 'unknown'
    
    @property
    def is_filtering_in_progress(self) -> bool:
        """Check if a filter operation is in progress."""
        controller = self._controllers.get('filtering')
        return controller.is_in_progress if controller else False
    
    @property
    def is_initialized(self) -> bool:
        """Check if orchestrator is initialized."""
        return self._initialized
    
    @property
    def is_setup_complete(self) -> bool:
        """Check if setup is complete."""
        return self._setup_complete
    
    # =========================================================================
    # Component Access
    # =========================================================================
    
    def get_controller(self, name: str):
        """
        Get a controller by name.
        
        Args:
            name: Controller name ('filtering', 'exploring', etc.)
            
        Returns:
            The controller instance or None
        """
        return self._controllers.get(name)
    
    def get_layout_manager(self, name: str):
        """
        Get a layout manager by name.
        
        Args:
            name: Manager name ('splitter', 'dimensions', etc.)
            
        Returns:
            The manager instance or None
        """
        return self._layout_managers.get(name)
    
    def get_style_manager(self, name: str):
        """
        Get a style manager by name.
        
        Args:
            name: Manager name ('theme', 'icon', 'button')
            
        Returns:
            The manager instance or None
        """
        return self._style_managers.get(name)
    
    def get_service(self, name: str):
        """
        Get a service by name.
        
        Args:
            name: Service name ('backend', 'filter', etc.)
            
        Returns:
            The service instance or None
        """
        return self._services.get(name)
    
    def get_all_controllers(self) -> List:
        """Get all controllers."""
        return list(self._controllers.values())
    
    def get_all_managers(self) -> List:
        """Get all managers (layout + style)."""
        return list(self._layout_managers.values()) + list(self._style_managers.values())
    
    # =========================================================================
    # Public API - Delegated Methods
    # =========================================================================
    
    def apply_filter(self, expression: str = None) -> bool:
        """
        Apply a filter to the current layer.
        
        Args:
            expression: Optional filter expression
            
        Returns:
            bool: True if successful
        """
        controller = self._controllers.get('filtering')
        if controller:
            return controller.apply_filter(expression)
        return False
    
    def clear_filter(self) -> bool:
        """
        Clear the current filter.
        
        Returns:
            bool: True if successful
        """
        controller = self._controllers.get('filtering')
        if controller:
            return controller.clear_filter()
        return False
    
    def reset_all(self) -> bool:
        """
        Reset all filters on all layers.
        
        Returns:
            bool: True if successful
        """
        controller = self._controllers.get('filtering')
        if controller:
            return controller.reset_all()
        return False
    
    def export_layer(self, format_type: str = 'gpkg', **kwargs) -> bool:
        """
        Export the current layer.
        
        Args:
            format_type: Export format ('gpkg', 'shp', etc.)
            **kwargs: Additional export options
            
        Returns:
            bool: True if successful
        """
        controller = self._controllers.get('exporting')
        if controller:
            return controller.export(format_type, **kwargs)
        return False
    
    def refresh_layer_list(self) -> None:
        """Refresh the layer list in all combo boxes."""
        controller = self._controllers.get('layer_sync')
        if controller:
            controller.refresh_layers()
    
    def switch_backend(self, backend_name: str) -> bool:
        """
        Switch to a different backend.
        
        Args:
            backend_name: Name of backend to switch to
            
        Returns:
            bool: True if successful
        """
        controller = self._controllers.get('backend')
        if controller:
            return controller.switch_backend(backend_name)
        return False
    
    # =========================================================================
    # Cleanup
    # =========================================================================
    
    def teardown(self) -> None:
        """
        Cleanup all components.
        
        Call this before destroying the dockwidget.
        """
        logger.info("DockWidgetOrchestrator teardown starting")
        
        # Disconnect signals first
        if self._signal_manager:
            try:
                self._signal_manager.teardown()
            except Exception as e:
                logger.warning(f"Signal manager teardown error: {e}")
        
        if self._layer_signal_handler:
            try:
                self._layer_signal_handler.disconnect_all_layers()
            except Exception as e:
                logger.warning(f"Layer signal handler teardown error: {e}")
        
        # Cleanup layout managers
        for name, manager in self._layout_managers.items():
            try:
                if hasattr(manager, 'teardown'):
                    manager.teardown()
            except Exception as e:
                logger.warning(f"Layout manager {name} teardown error: {e}")
        
        # Cleanup style managers
        for name, manager in self._style_managers.items():
            try:
                if hasattr(manager, 'teardown'):
                    manager.teardown()
            except Exception as e:
                logger.warning(f"Style manager {name} teardown error: {e}")
        
        # Cleanup services
        for name, service in self._services.items():
            try:
                if hasattr(service, 'cleanup'):
                    service.cleanup()
                elif hasattr(service, 'teardown'):
                    service.teardown()
            except Exception as e:
                logger.warning(f"Service {name} cleanup error: {e}")
        
        # Clear references
        self._layout_managers.clear()
        self._style_managers.clear()
        self._controllers.clear()
        self._services.clear()
        
        self._initialized = False
        self._setup_complete = False
        
        logger.info("DockWidgetOrchestrator teardown complete")
    
    def close_event_handler(self, event) -> None:
        """
        Handle close event from dockwidget.
        
        Call this from DockWidget.closeEvent().
        
        Args:
            event: The close event
        """
        logger.debug("Close event received")
        self.teardown()
    
    # =========================================================================
    # Deprecated Façades (Backward Compatibility)
    # =========================================================================
    
    def _deprecated_warning(self, old_method: str, new_method: str) -> None:
        """Issue a deprecation warning."""
        warnings.warn(
            f"{old_method}() is deprecated. Use {new_method} instead. "
            "Will be removed in v4.0.",
            DeprecationWarning,
            stacklevel=3
        )
    
    # These façades maintain backward compatibility with code that
    # directly calls methods on the dockwidget. They delegate to
    # the appropriate controller and emit deprecation warnings.
    
    def manage_filter(self, *args, **kwargs):
        """@deprecated Use filtering controller."""
        self._deprecated_warning('manage_filter', '_controllers["filtering"]')
        return self._controllers.get('filtering')
    
    def manage_export(self, *args, **kwargs):
        """@deprecated Use exporting controller."""
        self._deprecated_warning('manage_export', '_controllers["exporting"]')
        return self._controllers.get('exporting')
    
    def get_splitter_manager(self):
        """@deprecated Use get_layout_manager('splitter')."""
        self._deprecated_warning('get_splitter_manager', "get_layout_manager('splitter')")
        return self._layout_managers.get('splitter')
    
    def get_theme_manager(self):
        """@deprecated Use get_style_manager('theme')."""
        self._deprecated_warning('get_theme_manager', "get_style_manager('theme')")
        return self._style_managers.get('theme')


# =========================================================================
# Factory Function
# =========================================================================

def create_orchestrator(
    dockwidget: QDockWidget,
    app: 'FilterMateApp',
    iface,
    auto_init: bool = True,
    auto_setup: bool = True,
) -> DockWidgetOrchestrator:
    """
    Factory function to create and optionally initialize an orchestrator.
    
    Args:
        dockwidget: The QDockWidget instance
        app: FilterMate application
        iface: QGIS interface
        auto_init: Whether to auto-initialize
        auto_setup: Whether to auto-setup (requires auto_init)
        
    Returns:
        DockWidgetOrchestrator: The configured orchestrator
    """
    orchestrator = DockWidgetOrchestrator(dockwidget, app, iface)
    
    if auto_init:
        orchestrator.initialize()
        
        if auto_setup:
            orchestrator.setup()
    
    return orchestrator

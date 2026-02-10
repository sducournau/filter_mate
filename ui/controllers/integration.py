"""
FilterMate DockWidget Controller Integration.

This module provides the integration layer between the legacy dockwidget
and the new MVC controllers. It acts as a bridge allowing gradual migration
without breaking existing functionality.

Usage:
    In filter_mate_dockwidget.py __init__:
        from ui.controllers.integration import ControllerIntegration
        self._controller_integration = ControllerIntegration(self)
        self._controller_integration.setup()
    
    In closeEvent:
        self._controller_integration.teardown()
"""
from typing import TYPE_CHECKING, Optional, Dict, Any, Tuple
import logging

from .registry import ControllerRegistry, TabIndex
from .exploring_controller import ExploringController
from .filtering_controller import FilteringController
from .exporting_controller import ExportingController
from .backend_controller import BackendController
from .layer_sync_controller import LayerSyncController
from .config_controller import ConfigController
from .favorites_controller import FavoritesController
from .property_controller import PropertyController
from .ui_layout_controller import UILayoutController

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget
    from ...adapters.qgis.signals.signal_manager import SignalManager
    from ...core.services.filter_service import FilterService

logger = logging.getLogger(__name__)


class ControllerIntegration:
    """
    Integration layer between legacy dockwidget and new controllers.
    
    This class:
    - Creates and registers all controllers
    - Wires up signals between dockwidget and controllers
    - Provides backward-compatible property access
    - Handles lifecycle management
    
    The integration is designed to be non-invasive:
    - Controllers can be disabled without breaking the dockwidget
    - Legacy code paths still work when controllers are not active
    - Gradual migration is possible
    """
    
    def __init__(
        self,
        dockwidget: 'FilterMateDockWidget',
        signal_manager: Optional['SignalManager'] = None,
        filter_service: Optional['FilterService'] = None,
        enabled: bool = True
    ):
        """
        Initialize the integration layer.
        
        Args:
            dockwidget: Parent dockwidget
            signal_manager: Signal manager for connection tracking
            filter_service: Filter service for business logic
            enabled: Whether controllers are enabled
        """
        self._dockwidget = dockwidget
        self._signal_manager = signal_manager
        self._filter_service = filter_service
        self._enabled = enabled
        
        # Registry for all controllers
        self._registry: Optional[ControllerRegistry] = None
        
        # Individual controller references
        self._exploring_controller: Optional[ExploringController] = None
        self._filtering_controller: Optional[FilteringController] = None
        self._exporting_controller: Optional[ExportingController] = None
        self._backend_controller: Optional[BackendController] = None
        self._layer_sync_controller: Optional[LayerSyncController] = None
        self._config_controller: Optional[ConfigController] = None
        self._favorites_controller: Optional[FavoritesController] = None
        self._property_controller: Optional[PropertyController] = None
        self._ui_layout_controller: Optional[UILayoutController] = None
        
        # Connection tracking
        self._connections: list = []
        self._is_setup: bool = False
    
    @property
    def enabled(self) -> bool:
        """Check if controllers are enabled."""
        return self._enabled
    
    @property
    def registry(self) -> Optional[ControllerRegistry]:
        """Get the controller registry."""
        return self._registry
    
    @property
    def exploring_controller(self) -> Optional[ExploringController]:
        """Get the exploring controller."""
        return self._exploring_controller
    
    @property
    def filtering_controller(self) -> Optional[FilteringController]:
        """Get the filtering controller."""
        return self._filtering_controller
    
    @property
    def exporting_controller(self) -> Optional[ExportingController]:
        """Get the exporting controller."""
        return self._exporting_controller
    
    @property
    def backend_controller(self) -> Optional[BackendController]:
        """Get the backend controller."""
        return self._backend_controller
    
    @property
    def layer_sync_controller(self) -> Optional[LayerSyncController]:
        """Get the layer sync controller."""
        return self._layer_sync_controller

    @property
    def config_controller(self) -> Optional[ConfigController]:
        """Get the config controller."""
        return self._config_controller

    @property
    def favorites_controller(self) -> Optional[FavoritesController]:
        """Get the favorites controller."""
        return self._favorites_controller

    @property
    def property_controller(self) -> Optional[PropertyController]:
        """Get the property controller."""
        return self._property_controller
    
    @property
    def ui_layout_controller(self) -> Optional[UILayoutController]:
        """Get the UI layout controller."""
        return self._ui_layout_controller
    
    def setup(self) -> bool:
        """
        Setup all controllers and wire up signals.
        
        This is the main initialization point for the controller integration.
        It follows these steps:
        1. Create controller registry
        2. Instantiate all controller objects
        3. Register them in the registry
        4. Wire up signal connections
        5. Call setup() on each controller
        
        Returns:
            True if setup succeeded, False otherwise
        """
        if not self._enabled:
            logger.info("Controller integration is disabled")
            return False
        
        if self._is_setup:
            logger.debug("Controller integration already setup (idempotent call)")
            return True
        
        try:
            logger.debug("Creating controller registry...")
            self._registry = ControllerRegistry()
            
            logger.debug("Creating controller instances...")
            self._create_controllers()
            
            logger.debug("Registering controllers...")
            self._register_controllers()
            
            logger.debug("Wiring up signals...")
            self._connect_signals()
            
            logger.debug("Setting up all controllers...")
            setup_count = self._registry.setup_all()
            logger.debug(f"✓ {setup_count} controllers initialized successfully")
            
            self._is_setup = True
            logger.info("✓ Controller integration setup complete")
            return True
            
        except Exception as e:
            import traceback
            logger.error(f"Failed to setup controller integration: {e}", exc_info=True)
            self._cleanup_on_error()
            return False
    
    def teardown(self) -> None:
        """Teardown all controllers and cleanup."""
        if not self._is_setup:
            return
        
        try:
            # Disconnect signals
            self._disconnect_signals()
            
            # Teardown all controllers
            if self._registry:
                self._registry.teardown_all()
            
        except Exception as e:
            logger.error(f"Error during controller teardown: {e}")
        
        finally:
            # Clear references
            self._exploring_controller = None
            self._filtering_controller = None
            self._exporting_controller = None
            self._backend_controller = None
            self._layer_sync_controller = None
            self._config_controller = None
            self._favorites_controller = None
            self._property_controller = None
            self._ui_layout_controller = None
            self._registry = None
            self._is_setup = False
            
            logger.info("Controller integration teardown complete")
    
    def _create_controllers(self) -> None:
        """Create all controller instances."""
        # Get cache from dockwidget if available
        features_cache = getattr(self._dockwidget, '_exploring_cache', None)
        
        # Create ExploringController
        self._exploring_controller = ExploringController(
            dockwidget=self._dockwidget,
            filter_service=self._filter_service,
            signal_manager=self._signal_manager,
            features_cache=features_cache
        )
        
        # Create FilteringController
        self._filtering_controller = FilteringController(
            dockwidget=self._dockwidget,
            filter_service=self._filter_service,
            signal_manager=self._signal_manager
        )
        
        # Create ExportingController
        self._exporting_controller = ExportingController(
            dockwidget=self._dockwidget,
            filter_service=self._filter_service,
            signal_manager=self._signal_manager
        )
        
        # Create BackendController
        self._backend_controller = BackendController(
            dockwidget=self._dockwidget
        )
        
        # Create LayerSyncController
        self._layer_sync_controller = LayerSyncController(
            dockwidget=self._dockwidget
        )
        
        # v3.1 STORY-2.5: Create ConfigController
        self._config_controller = ConfigController(
            dockwidget=self._dockwidget,
            signal_manager=self._signal_manager
        )
        
        # v4.0: Create FavoritesController
        self._favorites_controller = FavoritesController(
            dockwidget=self._dockwidget
        )
        
        # v4.0 Sprint 1: Create PropertyController
        self._property_controller = PropertyController(
            dockwidget=self._dockwidget
        )
        
        # v4.0 Sprint 4: Create UILayoutController
        self._ui_layout_controller = UILayoutController(
            dockwidget=self._dockwidget
        )
        
        logger.debug("All controllers created")
    
    def _register_controllers(self) -> None:
        """Register all controllers with the registry."""
        if not self._registry:
            return
        
        # Register with tab indices
        # Note: TabIndex.FILTERING = 0, but exploring is typically first
        # We register by name, tab index is for tab switching
        
        
        def safe_register(name, controller, tab_index):
            """Helper to register with error handling."""
            try:
                if controller is None:
                    return False
                self._registry.register(name, controller, tab_index=tab_index)
                return True
            except Exception as e:
                import traceback
                return False
        
        safe_register(
            'exploring',
            self._exploring_controller,
            TabIndex.FILTERING  # Tab 0 - Exploring/Filtering combined?
        )
        
        safe_register(
            'filtering',
            self._filtering_controller,
            TabIndex.FILTERING  # Tab 0
        )
        
        safe_register(
            'exporting',
            self._exporting_controller,
            TabIndex.EXPORTING  # Tab 1
        )
        
        safe_register(
            'backend',
            self._backend_controller,
            TabIndex.FILTERING  # Backend indicator visible on all tabs
        )
        
        safe_register(
            'layer_sync',
            self._layer_sync_controller,
            TabIndex.FILTERING  # Layer sync active on all tabs
        )
        
        # v3.1 STORY-2.5: Register ConfigController
        safe_register(
            'config',
            self._config_controller,
            TabIndex.CONFIGURATION  # Tab for configuration
        )
        
        # v4.0: Register FavoritesController
        safe_register(
            'favorites',
            self._favorites_controller,
            TabIndex.FILTERING  # Favorites indicator visible on filtering tabs
        )
        
        # v4.0 Sprint 1: Register PropertyController
        safe_register(
            'property',
            self._property_controller,
            TabIndex.FILTERING  # Property controller active on filtering tab
        )
        
        # v4.0 Sprint 4: Register UILayoutController
        safe_register(
            'ui_layout',
            self._ui_layout_controller,
            TabIndex.FILTERING  # UI layout controller active on all tabs
        )
        
        logger.debug("All controllers registered")
    
    def _connect_signals(self) -> None:
        """Connect dockwidget signals to controllers and controller signals to handlers."""
        dw = self._dockwidget
        
        # Connect tab changed signal
        if hasattr(dw, 'tabTools') and dw.tabTools:
            try:
                dw.tabTools.currentChanged.connect(self._on_tab_changed)
                self._connections.append(('tabTools.currentChanged', self._on_tab_changed))
            except Exception as e:
                logger.warning(f"Could not connect tabTools signal: {e}")
        
        # Connect layer changed signal
        if hasattr(dw, 'currentLayerChanged'):
            try:
                dw.currentLayerChanged.connect(self._on_current_layer_changed)
                self._connections.append(('currentLayerChanged', self._on_current_layer_changed))
            except Exception as e:
                logger.warning(f"Could not connect currentLayerChanged signal: {e}")
        
        # === FIX 2026-01-16: Connect critical dockwidget signals (regression fix) ===
        # These signals were not connected during hexagonal migration, causing:
        # - Controllers unaware when widgets are ready
        # - Task launches not tracked
        # - Export combobox not populated
        
        # FIX-1: widgetsInitialized - Controllers need to know when UI is ready
        if hasattr(dw, 'widgetsInitialized'):
            try:
                dw.widgetsInitialized.connect(self._on_widgets_initialized)
                self._connections.append(('widgetsInitialized', self._on_widgets_initialized))
                logger.debug("✓ Connected widgetsInitialized signal")
            except Exception as e:
                logger.warning(f"Could not connect widgetsInitialized signal: {e}")
        
        # FIX-2: launchingTask - Track task launches for filtering/export operations
        if hasattr(dw, 'launchingTask'):
            try:
                dw.launchingTask.connect(self._on_launching_task)
                self._connections.append(('launchingTask', self._on_launching_task))
                logger.debug("✓ Connected launchingTask signal")
            except Exception as e:
                logger.warning(f"Could not connect launchingTask signal: {e}")
        
        # FIX-4: projectLayersReady - Populate export combobox when layers are ready
        if hasattr(dw, 'projectLayersReady'):
            try:
                dw.projectLayersReady.connect(self._on_project_layers_ready)
                self._connections.append(('projectLayersReady', self._on_project_layers_ready))
                logger.debug("✓ Connected projectLayersReady signal")
            except Exception as e:
                logger.warning(f"Could not connect projectLayersReady signal: {e}")
        
        # FIX-4b: gettingProjectLayers - Show loading feedback
        if hasattr(dw, 'gettingProjectLayers'):
            try:
                dw.gettingProjectLayers.connect(self._on_getting_project_layers)
                self._connections.append(('gettingProjectLayers', self._on_getting_project_layers))
                logger.debug("✓ Connected gettingProjectLayers signal")
            except Exception as e:
                logger.warning(f"Could not connect gettingProjectLayers signal: {e}")
        
        # === v4.0.5: Connect controller signals to integration handlers ===
        # This enables proper event-driven communication between controllers and UI
        
        # LayerSyncController signals
        if self._layer_sync_controller:
            try:
                self._layer_sync_controller.layer_synchronized.connect(self._on_layer_synchronized)
                self._connections.append(('layer_sync.layer_synchronized', self._on_layer_synchronized))
                self._layer_sync_controller.sync_blocked.connect(self._on_sync_blocked)
                self._connections.append(('layer_sync.sync_blocked', self._on_sync_blocked))
                self._layer_sync_controller.layer_changed.connect(self._on_layer_changed_from_controller)
                self._connections.append(('layer_sync.layer_changed', self._on_layer_changed_from_controller))
            except Exception as e:
                logger.warning(f"Could not connect LayerSyncController signals: {e}")
        
        # PropertyController signals
        if self._property_controller:
            try:
                self._property_controller.property_changed.connect(self._on_property_changed)
                self._connections.append(('property.property_changed', self._on_property_changed))
                self._property_controller.property_error.connect(self._on_property_error)
                self._connections.append(('property.property_error', self._on_property_error))
                self._property_controller.buffer_style_changed.connect(self._on_buffer_style_changed)
                self._connections.append(('property.buffer_style_changed', self._on_buffer_style_changed))
            except Exception as e:
                logger.warning(f"Could not connect PropertyController signals: {e}")
        
        # BackendController signals
        if self._backend_controller:
            try:
                self._backend_controller.backend_changed.connect(self._on_backend_changed)
                self._connections.append(('backend.backend_changed', self._on_backend_changed))
                self._backend_controller.reload_requested.connect(self._on_reload_requested)
                self._connections.append(('backend.reload_requested', self._on_reload_requested))
            except Exception as e:
                logger.warning(f"Could not connect BackendController signals: {e}")
        
        # FavoritesController signals
        if self._favorites_controller:
            try:
                self._favorites_controller.favorites_changed.connect(self._on_favorites_changed)
                self._connections.append(('favorites.favorites_changed', self._on_favorites_changed))
                self._favorites_controller.favorite_applied.connect(self._on_favorite_applied)
                self._connections.append(('favorites.favorite_applied', self._on_favorite_applied))
            except Exception as e:
                logger.warning(f"Could not connect FavoritesController signals: {e}")
        
        # ConfigController signals
        if self._config_controller:
            try:
                self._config_controller.theme_changed.connect(self._on_theme_changed)
                self._connections.append(('config.theme_changed', self._on_theme_changed))
                self._config_controller.config_changed.connect(self._on_config_changed)
                self._connections.append(('config.config_changed', self._on_config_changed))
            except Exception as e:
                logger.warning(f"Could not connect ConfigController signals: {e}")
        
        logger.debug(f"Connected {len(self._connections)} signals")
    
    def _disconnect_signals(self) -> None:
        """Disconnect all signals."""
        dw = self._dockwidget
        
        for signal_name, handler in self._connections:
            try:
                # Dockwidget signals
                if signal_name == 'tabTools.currentChanged' and hasattr(dw, 'tabTools'):
                    dw.tabTools.currentChanged.disconnect(handler)
                elif signal_name == 'currentLayerChanged' and hasattr(dw, 'currentLayerChanged'):
                    dw.currentLayerChanged.disconnect(handler)
                # FIX 2026-01-16: Disconnect critical dockwidget signals
                elif signal_name == 'widgetsInitialized' and hasattr(dw, 'widgetsInitialized'):
                    dw.widgetsInitialized.disconnect(handler)
                elif signal_name == 'launchingTask' and hasattr(dw, 'launchingTask'):
                    dw.launchingTask.disconnect(handler)
                elif signal_name == 'projectLayersReady' and hasattr(dw, 'projectLayersReady'):
                    dw.projectLayersReady.disconnect(handler)
                elif signal_name == 'gettingProjectLayers' and hasattr(dw, 'gettingProjectLayers'):
                    dw.gettingProjectLayers.disconnect(handler)
                # v4.0.5: Controller signals
                elif signal_name.startswith('layer_sync.') and self._layer_sync_controller:
                    if 'layer_synchronized' in signal_name:
                        self._layer_sync_controller.layer_synchronized.disconnect(handler)
                    elif 'sync_blocked' in signal_name:
                        self._layer_sync_controller.sync_blocked.disconnect(handler)
                    elif 'layer_changed' in signal_name:
                        self._layer_sync_controller.layer_changed.disconnect(handler)
                elif signal_name.startswith('property.') and self._property_controller:
                    if 'property_changed' in signal_name:
                        self._property_controller.property_changed.disconnect(handler)
                    elif 'property_error' in signal_name:
                        self._property_controller.property_error.disconnect(handler)
                    elif 'buffer_style_changed' in signal_name:
                        self._property_controller.buffer_style_changed.disconnect(handler)
                elif signal_name.startswith('backend.') and self._backend_controller:
                    if 'backend_changed' in signal_name:
                        self._backend_controller.backend_changed.disconnect(handler)
                    elif 'reload_requested' in signal_name:
                        self._backend_controller.reload_requested.disconnect(handler)
                elif signal_name.startswith('favorites.') and self._favorites_controller:
                    if 'favorites_changed' in signal_name:
                        self._favorites_controller.favorites_changed.disconnect(handler)
                    elif 'favorite_applied' in signal_name:
                        self._favorites_controller.favorite_applied.disconnect(handler)
                elif signal_name.startswith('config.') and self._config_controller:
                    if 'theme_changed' in signal_name:
                        self._config_controller.theme_changed.disconnect(handler)
                    elif 'config_changed' in signal_name:
                        self._config_controller.config_changed.disconnect(handler)
            except Exception as e:
                logger.debug(f"Could not disconnect {signal_name}: {e}")
        
        self._connections.clear()
    
    def _on_tab_changed(self, index: int) -> None:
        """
        Handle tab change event.
        
        Args:
            index: New tab index
        """
        if self._registry:
            try:
                tab_index = TabIndex(index)
                self._registry.notify_tab_changed(tab_index)
            except ValueError:
                # Invalid tab index, ignore
                pass
    
    def _on_current_layer_changed(self) -> None:
        """Handle current layer change event.
        
        Note: This is triggered by the currentLayerChanged signal which is emitted
        DURING current_layer_changed() execution. The actual widget updates are
        handled by current_layer_changed() in dockwidget after this signal.
        This method is kept for controller state synchronization only.
        """
        layer = getattr(self._dockwidget, 'current_layer', None)
        
        # Update exploring controller internal state
        if self._exploring_controller:
            self._exploring_controller.set_layer(layer)
        
        # Update filtering controller internal state
        if self._filtering_controller:
            self._filtering_controller.set_source_layer(layer)
    
    # === v4.0.5: Controller Signal Handlers ===
    # These handlers respond to signals emitted by controllers
    
    def _on_layer_synchronized(self, layer) -> None:
        """Handle layer synchronized event from LayerSyncController."""
        layer_name = layer.name() if layer and hasattr(layer, 'name') else 'None'
        logger.debug(f"Layer synchronized: {layer_name}")
        # Could trigger UI refresh here if needed
    
    def _on_sync_blocked(self, reason: str) -> None:
        """Handle sync blocked event from LayerSyncController."""
        logger.debug(f"Layer sync blocked: {reason}")
        # Could show user notification for certain block reasons
    
    def _on_layer_changed_from_controller(self, layer) -> None:
        """Handle layer changed event from LayerSyncController."""
        layer_name = layer.name() if layer and hasattr(layer, 'name') else 'None'
        logger.debug(f"Layer changed (from controller): {layer_name}")
    
    def _on_property_changed(self, prop_name: str, new_val, old_val) -> None:
        """Handle property change event from PropertyController."""
        logger.debug(f"Property '{prop_name}' changed: {old_val} -> {new_val}")
        # Could propagate to other components that need to know about property changes
    
    def _on_property_error(self, prop_name: str, error_msg: str) -> None:
        """Handle property error event from PropertyController."""
        logger.warning(f"Property error on '{prop_name}': {error_msg}")
        # Could show error message to user via message bar
        try:
            from qgis.utils import iface
            if iface and hasattr(iface, 'messageBar'):
                iface.messageBar().pushWarning("FilterMate", f"Property error: {error_msg}")
        except Exception:
            pass
    
    def _on_buffer_style_changed(self, buffer_value: float) -> None:
        """Handle buffer style change event from PropertyController."""
        logger.debug(f"Buffer style changed: {buffer_value}")
        # Could update buffer visualization or related UI elements
    
    def _on_backend_changed(self, layer_id: str, backend_name: str) -> None:
        """Handle backend change event from BackendController."""
        logger.debug(f"Backend changed for layer {layer_id}: {backend_name}")
        # Update backend indicator display for current layer
        if self._dockwidget and self._backend_controller:
            current_layer = self._dockwidget.current_layer
            if current_layer and current_layer.id() == layer_id:
                # Ensure indicator is updated for the current layer
                self._backend_controller.update_for_layer(current_layer, actual_backend=backend_name if backend_name != 'auto' else None)
    
    def _on_reload_requested(self) -> None:
        """Handle reload request event from BackendController."""
        logger.info("Reload requested from BackendController")
        if self._dockwidget and hasattr(self._dockwidget, 'get_project_layers'):
            try:
                self._dockwidget.get_project_layers()
            except Exception as e:
                logger.error(f"Failed to reload layers: {e}")
    
    def _on_favorites_changed(self) -> None:
        """Handle favorites changed event from FavoritesController."""
        logger.debug("Favorites list changed")
        # Could trigger refresh of favorites UI widget
    
    def _on_favorite_applied(self, favorite_name: str) -> None:
        """Handle favorite applied event from FavoritesController."""
        logger.info(f"Favorite applied: {favorite_name}")
        # Could show success notification
    
    def _on_theme_changed(self, theme_name: str) -> None:
        """Handle theme change event from ConfigController."""
        logger.info(f"Theme changed to: {theme_name}")
        # Trigger theme application across the UI
        if self._dockwidget:
            try:
                # Try to apply theme via style manager
                from ..styles import ThemeManager
                if ThemeManager:
                    ThemeManager.apply_theme(theme_name)
            except Exception as e:
                logger.debug(f"Could not apply theme automatically: {e}")
    
    def _on_config_changed(self, key: str, value) -> None:
        """Handle config change event from ConfigController."""
        logger.debug(f"Config changed: {key} = {value}")
        # Could propagate config changes to components that need them
    
    # === FIX 2026-01-16: Handlers for critical dockwidget signals ===
    
    def _on_widgets_initialized(self) -> None:
        """
        FIX-1: Handle widgets initialized event from dockwidget.
        
        This signal is emitted when all dockwidget widgets are configured.
        Controllers can now safely access widgets.
        """
        logger.info("✓ Widgets initialized - controllers can now access UI")
        
        # Sync all controllers with current dockwidget state
        self.sync_from_dockwidget()
        
        # Notify exploring controller to refresh if layer exists
        if self._exploring_controller and self._dockwidget:
            layer = getattr(self._dockwidget, 'current_layer', None)
            if layer:
                try:
                    self._exploring_controller.set_layer(layer)
                    logger.debug(f"ExploringController synced with layer: {layer.name()}")
                except Exception as e:
                    logger.debug(f"Could not sync exploring controller: {e}")
        
        # Notify exporting controller to populate layers
        if self._exporting_controller and self._dockwidget:
            try:
                if hasattr(self._exporting_controller, 'refresh_layers'):
                    self._exporting_controller.refresh_layers()
                    logger.debug("ExportingController layers refreshed")
            except Exception as e:
                logger.debug(f"Could not refresh exporting layers: {e}")
    
    def _on_launching_task(self, task_type: str) -> None:
        """
        FIX-2: Handle task launch event from dockwidget.
        
        This signal is emitted when a filtering/export task is launched.
        Controllers can track task state and show progress.
        
        Args:
            task_type: Type of task being launched (e.g., 'filter', 'export')
        """
        logger.info(f"📋 Task launched: {task_type}")
        
        # Could show progress indicator or disable UI during task
        # For now, just log and let the task complete
        
        # Notify filtering controller if it's a filter task
        if task_type in ('filter', 'unfilter', 'reset') and self._filtering_controller:
            try:
                if hasattr(self._filtering_controller, 'on_task_started'):
                    self._filtering_controller.on_task_started(task_type)
            except Exception as e:
                logger.debug(f"FilteringController task notification failed: {e}")
        
        # Notify exporting controller if it's an export task
        if task_type == 'export' and self._exporting_controller:
            try:
                if hasattr(self._exporting_controller, 'on_task_started'):
                    self._exporting_controller.on_task_started(task_type)
            except Exception as e:
                logger.debug(f"ExportingController task notification failed: {e}")
    
    def _on_project_layers_ready(self) -> None:
        """
        v4.1.4: Unified handler for project layers ready event.
        
        This is the SINGLE handler for projectLayersReady signal.
        Previously, both app_initializer.py and integration.py connected to this signal,
        causing duplicate operations. Now only integration.py handles this signal.
        
        This handler:
        1. Sets has_loaded_layers flag on dockwidget
        2. Populates export combobox via ExportingController
        3. Populates filtering layers combobox via FilteringController
        4. Notifies LayerSyncController
        """
        logger.info("✓ Project layers ready - populating comboboxes (unified handler)")
        
        dw = self._dockwidget
        if not dw:
            logger.warning("_on_project_layers_ready: No dockwidget available")
            return
        
        # Step 1: Set loaded flag (previously done in dockwidget._on_project_layers_ready)
        dw.has_loaded_layers = True
        
        # Step 2: Populate export layers combobox
        if self._exporting_controller:
            try:
                dw.manageSignal(["EXPORTING", "LAYERS_TO_EXPORT"], 'disconnect')
                if hasattr(self._exporting_controller, 'populate_export_combobox'):
                    self._exporting_controller.populate_export_combobox()
                    logger.debug("Export layers combobox populated via controller")
                elif hasattr(self._exporting_controller, 'refresh_layers'):
                    self._exporting_controller.refresh_layers()
                    logger.debug("Export layers combobox populated via refresh_layers")
                dw.manageSignal(["EXPORTING", "LAYERS_TO_EXPORT"], 'connect', 'checkedItemsChanged')
            except Exception as e:
                logger.debug(f"Could not populate export layers: {e}")
        
        # Step 3: Populate filtering layers combobox
        if self._filtering_controller:
            try:
                layer = dw.current_layer
                if layer:
                    dw.manageSignal(["FILTERING", "LAYERS_TO_FILTER"], 'disconnect')
                    self._filtering_controller.populate_layers_checkable_combobox(layer)
                    dw.manageSignal(["FILTERING", "LAYERS_TO_FILTER"], 'connect', 'checkedItemsChanged')
                    logger.debug("Filtering layers combobox populated via controller")
            except Exception as e:
                logger.debug(f"Could not populate filtering layers: {e}")
        
        # Step 4: Notify layer sync controller
        if self._layer_sync_controller:
            try:
                if hasattr(self._layer_sync_controller, 'on_layers_ready'):
                    self._layer_sync_controller.on_layers_ready()
            except Exception as e:
                logger.debug(f"LayerSyncController layers ready notification failed: {e}")
    
    def _on_getting_project_layers(self) -> None:
        """
        FIX-4b: Handle getting project layers event from dockwidget.
        
        This signal is emitted when layer loading starts.
        Could show loading indicator.
        """
        logger.debug("⏳ Loading project layers...")

    def _cleanup_on_error(self) -> None:
        """Cleanup after setup error."""
        self._exploring_controller = None
        self._filtering_controller = None
        self._exporting_controller = None
        self._backend_controller = None
        self._layer_sync_controller = None
        self._config_controller = None
        self._favorites_controller = None
        self._property_controller = None
        self._ui_layout_controller = None
        self._registry = None
        self._connections.clear()
        self._is_setup = False
    
    # === Validation Methods ===
    
    def validate_controllers(self) -> dict:
        """
        Validate that all expected controllers are properly initialized.
        
        This method performs comprehensive validation of the controller architecture:
        - Checks if setup has been completed
        - Verifies each controller is instantiated
        - Confirms registry contains all controllers
        - Reports on connection status
        
        Returns:
            Dictionary with validation results:
            {
                'is_setup': bool,
                'controllers': {name: bool},
                'registry_count': int,
                'connections_count': int,
                'all_valid': bool
            }
        
        Example:
            >>> integration.validate_controllers()
            {
                'is_setup': True,
                'controllers': {
                    'exploring': True,
                    'filtering': True,
                    ...
                },
                'registry_count': 9,
                'connections_count': 12,
                'all_valid': True
            }
        """
        result = {
            'is_setup': self._is_setup,
            'controllers': {},
            'registry_count': 0,
            'connections_count': len(self._connections),
            'all_valid': False
        }
        
        # Check individual controllers
        expected_controllers = [
            ('exploring', self._exploring_controller),
            ('filtering', self._filtering_controller),
            ('exporting', self._exporting_controller),
            ('backend', self._backend_controller),
            ('layer_sync', self._layer_sync_controller),
            ('config', self._config_controller),
            ('favorites', self._favorites_controller),
            ('property', self._property_controller),
            ('ui_layout', self._ui_layout_controller),
        ]
        
        for name, controller in expected_controllers:
            result['controllers'][name] = controller is not None
        
        # Check registry
        if self._registry:
            result['registry_count'] = len(self._registry)
        
        # Determine overall validity
        all_controllers_valid = all(result['controllers'].values())
        registry_valid = result['registry_count'] == len(expected_controllers)
        result['all_valid'] = (
            result['is_setup'] and 
            all_controllers_valid and 
            registry_valid
        )
        
        return result
    
    def get_controller_status(self) -> str:
        """
        Get a human-readable status summary of all controllers.
        
        Returns:
            Formatted string with controller status
        
        Example:
            >>> print(integration.get_controller_status())
            Controller Integration Status:
            ✓ Setup completed
            ✓ 9/9 controllers initialized
            ✓ Registry contains 9 controllers
            ✓ 12 signal connections active
        """
        validation = self.validate_controllers()
        
        lines = ["Controller Integration Status:"]
        
        # Setup status
        if validation['is_setup']:
            lines.append("✓ Setup completed")
        else:
            lines.append("✗ Setup not completed")
        
        # Controllers status
        controller_count = sum(validation['controllers'].values())
        total_count = len(validation['controllers'])
        if controller_count == total_count:
            lines.append(f"✓ {controller_count}/{total_count} controllers initialized")
        else:
            lines.append(f"⚠ {controller_count}/{total_count} controllers initialized")
            for name, status in validation['controllers'].items():
                if not status:
                    lines.append(f"  ✗ {name} controller missing")
        
        # Registry status
        if validation['registry_count'] == total_count:
            lines.append(f"✓ Registry contains {validation['registry_count']} controllers")
        else:
            lines.append(f"⚠ Registry contains {validation['registry_count']} controllers (expected {total_count})")
        
        # Connections status
        lines.append(f"ℹ {validation['connections_count']} signal connections active")
        
        # Overall status
        if validation['all_valid']:
            lines.append("✓ All systems operational")
        else:
            lines.append("⚠ Some issues detected")
        
        return "\n".join(lines)
    
    # === Delegation Methods ===
    # These methods allow the dockwidget to delegate to controllers
    
    def delegate_flash_feature(self, feature_id: int) -> bool:
        """Delegate flash feature to exploring controller."""
        if self._exploring_controller:
            return self._exploring_controller.flash_feature(feature_id)
        return False
    
    def delegate_zoom_to_feature(self, feature_id: int) -> bool:
        """Delegate zoom to feature to exploring controller."""
        if self._exploring_controller:
            return self._exploring_controller.zoom_to_feature(feature_id)
        return False
    
    def delegate_identify_feature(self, feature_id: int) -> bool:
        """Delegate identify feature to exploring controller."""
        if self._exploring_controller:
            return self._exploring_controller.identify_feature(feature_id)
        return False
    
    def delegate_flash_features_by_ids(
        self,
        layer,
        feature_ids: list,
        start_color=None,
        end_color=None,
        flashes: int = 6,
        duration: int = 400
    ) -> bool:
        """
        Delegate flash features by IDs using exploring controller.
        
        This is a higher-level delegation that takes parameters matching
        the dockwidget's exploring_identify_clicked pattern.
        
        Args:
            layer: The QgsVectorLayer containing the features
            feature_ids: List of feature IDs to flash
            start_color: Start color for flash animation
            end_color: End color for flash animation
            flashes: Number of flash cycles
            duration: Duration of flash in milliseconds
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if not self._exploring_controller or not feature_ids:
            return False
        
        try:
            # Set layer on controller
            self._exploring_controller.set_layer(layer)
            
            # Flash each feature (controller handles the animation)
            for fid in feature_ids[:10]:  # Limit for performance
                self._exploring_controller.flash_feature(fid, duration // flashes)
            
            return True
        except Exception as e:
            logger.warning(f"delegate_flash_features_by_ids failed: {e}")
            return False
    
    def delegate_zoom_to_extent(self, extent, layer=None) -> bool:
        """
        Delegate zoom to extent operation.
        
        Args:
            extent: QgsRectangle to zoom to
            layer: Optional layer for CRS transform
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._exploring_controller:
            # Controller doesn't have direct extent zoom, use zoom_to_selected
            # after setting selection
            return self._exploring_controller.zoom_to_selected()
        return False
    
    def delegate_zoom_to_features(self, features: list, expression: str = None, layer=None) -> bool:
        """
        Delegate zoom to features operation.
        
        v3.1 Phase 6 (STORY-2.3): Enhanced with layer sync for robust delegation.
        
        Args:
            features: List of QgsFeature objects to zoom to
            expression: Optional expression string (for logging)
            layer: Optional layer to sync before zoom (if None, uses dockwidget.current_layer)
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._exploring_controller and features:
            try:
                # v3.1 STORY-2.3: Sync layer before zoom to ensure controller has correct layer
                target_layer = layer
                if target_layer is None and self._dockwidget:
                    target_layer = getattr(self._dockwidget, 'current_layer', None)
                
                if target_layer:
                    self._exploring_controller.set_layer(target_layer)
                
                return self._exploring_controller.zoom_to_features(features)
            except Exception as e:
                logger.warning(f"delegate_zoom_to_features failed: {e}")
                return False
        return False
    
    def delegate_flash_features(self, feature_ids: list, layer=None) -> bool:
        """
        Delegate flash features operation to ExploringController.
        
        v3.1 Vague 2: Supports dockwidget exploring_identify_clicked delegation.
        v3.1 Phase 6 (STORY-2.3): Enhanced with layer sync for robust delegation.
        
        Args:
            feature_ids: List of feature IDs to flash
            layer: Optional layer to sync before flash (if None, uses dockwidget.current_layer)
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._exploring_controller and feature_ids:
            try:
                # v3.1 STORY-2.3: Sync layer before flash to ensure controller has correct layer
                target_layer = layer
                if target_layer is None and self._dockwidget:
                    target_layer = getattr(self._dockwidget, 'current_layer', None)
                
                if target_layer:
                    self._exploring_controller.set_layer(target_layer)
                
                return self._exploring_controller.flash_features(feature_ids)
            except Exception as e:
                logger.warning(f"delegate_flash_features failed: {e}")
                return False
        return False
    
    # === Exploring Controller Delegation (v3.1 Phase 6 - STORY-2.3) ===
    
    def delegate_exploring_setup(self) -> bool:
        """
        Delegate exploring controller setup.
        
        v3.1 Phase 6 (STORY-2.3): Full delegation to ExploringController.
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._exploring_controller:
            try:
                self._exploring_controller.setup()
                return True
            except Exception as e:
                logger.warning(f"delegate_exploring_setup failed: {e}")
                return False
        return False
    
    def delegate_handle_layer_selection_changed(self, selected, deselected, clear_and_select) -> bool:
        """
        Delegate layer selection change handling to ExploringController.
        
        v3.1 Sprint 7: Full migration of on_layer_selection_changed logic.
        
        Args:
            selected: List of added feature IDs
            deselected: List of removed feature IDs
            clear_and_select: Boolean indicating if selection was cleared
        
        Returns:
            True if handled successfully, False otherwise
        """
        if self._exploring_controller:
            try:
                return self._exploring_controller.handle_layer_selection_changed(
                    selected, deselected, clear_and_select
                )
            except Exception as e:
                logger.warning(f"delegate_handle_layer_selection_changed failed: {e}")
                return False
        return False
    
    def delegate_get_current_features(self, use_cache: bool = True) -> tuple:
        """
        Delegate getting current selected features to ExploringController.
        
        v3.1 Sprint 6: Full migration of get_current_features logic.
        
        Args:
            use_cache: If True, return cached features if available
        
        Returns:
            tuple: (features, expression) or ([], '') on failure
        """
        if self._exploring_controller:
            try:
                return self._exploring_controller.get_current_features(use_cache)
            except Exception as e:
                logger.warning(f"delegate_get_current_features failed: {e}")
                return [], ''
        return [], ''
    
    def delegate_exploring_get_current_features(self) -> list:
        """
        Delegate getting current selected features.
        
        Returns:
            List of selected feature values, empty list on failure
        """
        if self._exploring_controller:
            try:
                return self._exploring_controller.get_selected_features()
            except Exception as e:
                logger.warning(f"delegate_exploring_get_current_features failed: {e}")
                return []
        return []
    
    def delegate_exploring_set_layer(self, layer) -> bool:
        """
        Delegate layer change to exploring controller.
        
        Args:
            layer: The new layer to set
            
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._exploring_controller:
            try:
                self._exploring_controller.set_layer(layer)
                return True
            except Exception as e:
                logger.warning(f"delegate_exploring_set_layer failed: {e}")
                return False
        return False
    
    def delegate_exploring_clear_cache(self) -> bool:
        """
        Delegate cache clearing to exploring controller.
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._exploring_controller:
            try:
                self._exploring_controller.clear_cache()
                return True
            except Exception as e:
                logger.warning(f"delegate_exploring_clear_cache failed: {e}")
                return False
        return False
    
    def delegate_exploring_get_cache_stats(self) -> dict:
        """
        Delegate cache stats retrieval.
        
        Returns:
            Cache stats dictionary, empty dict on failure
        """
        if self._exploring_controller:
            try:
                return self._exploring_controller.get_cache_stats()
            except Exception as e:
                logger.warning(f"delegate_exploring_get_cache_stats failed: {e}")
                return {}
        return {}
    
    def delegate_exploring_clear_selection(self) -> bool:
        """
        Delegate clearing feature selection.
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._exploring_controller:
            try:
                self._exploring_controller.clear_selection()
                return True
            except Exception as e:
                logger.warning(f"delegate_exploring_clear_selection failed: {e}")
                return False
        return False

    def delegate_exploring_set_groupbox_mode(self, mode: str) -> bool:
        """
        Delegate groupbox mode change to ExploringController.
        
        v3.1 STORY-2.3: Tracks groupbox state in controller for cache invalidation.
        
        Args:
            mode: 'single_selection', 'multiple_selection', or 'custom_selection'
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._exploring_controller:
            try:
                return self._exploring_controller.set_groupbox_mode(mode)
            except Exception as e:
                logger.warning(f"delegate_exploring_set_groupbox_mode failed: {e}")
                return False
        return False

    def delegate_exploring_get_groupbox_mode(self) -> str:
        """
        Get current groupbox mode from ExploringController.
        
        Returns:
            Current mode or 'single_selection' as default
        """
        if self._exploring_controller:
            try:
                return self._exploring_controller.get_groupbox_mode()
            except Exception as e:
                logger.warning(f"delegate_exploring_get_groupbox_mode failed: {e}")
                return 'single_selection'
        return 'single_selection'

    def delegate_exploring_configure_groupbox(self, mode: str, layer=None, 
                                               layer_props: dict = None) -> bool:
        """
        Delegate groupbox configuration to ExploringController.
        
        v4.0 Sprint 5: Full groupbox configuration delegation.
        
        Args:
            mode: 'single_selection', 'multiple_selection', or 'custom_selection'
            layer: Optional layer to configure widgets for
            layer_props: Optional layer properties dict
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._exploring_controller:
            try:
                return self._exploring_controller.configure_groupbox(mode, layer, layer_props)
            except Exception as e:
                logger.warning(f"delegate_exploring_configure_groupbox failed: {e}")
                return False
        return False
    
    def delegate_exploring_zoom_to_selected(self) -> bool:
        """
        Delegate zoom to selected features.
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._exploring_controller:
            try:
                return self._exploring_controller.zoom_to_selected()
            except Exception as e:
                logger.warning(f"delegate_exploring_zoom_to_selected failed: {e}")
                return False
        return False

    def delegate_exploring_activate_selection_tool(self, layer=None) -> bool:
        """
        Delegate activation of QGIS selection tool.
        
        Args:
            layer: Optional layer to set as active
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._exploring_controller:
            try:
                return self._exploring_controller.activate_selection_tool(layer)
            except Exception as e:
                logger.warning(f"delegate_exploring_activate_selection_tool failed: {e}")
                return False
        return False

    def delegate_exploring_select_layer_features(self, feature_ids: list = None, layer=None) -> bool:
        """
        Delegate feature selection on layer.
        
        Args:
            feature_ids: List of feature IDs to select
            layer: Optional layer to use
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._exploring_controller:
            try:
                return self._exploring_controller.select_layer_features(feature_ids, layer)
            except Exception as e:
                logger.warning(f"delegate_exploring_select_layer_features failed: {e}")
                return False
        return False

    def delegate_execute_filter(self) -> bool:
        """Delegate filter execution to filtering controller."""
        if self._filtering_controller:
            return self._filtering_controller.execute_filter()
        return False
    
    def delegate_execute_unfilter(self) -> bool:
        """
        Delegate unfilter execution to filtering controller.
        
        v4.0: Implements controller delegation for unfilter action.
        """
        if self._filtering_controller:
            return self._filtering_controller.execute_unfilter()
        return False
    
    def delegate_execute_reset(self) -> bool:
        """
        Delegate reset execution to filtering controller.
        
        v4.0: Implements controller delegation for reset action.
        """
        if self._filtering_controller:
            return self._filtering_controller.execute_reset_filters()
        return False
    
    def delegate_undo_filter(self) -> bool:
        """Delegate undo to filtering controller."""
        if self._filtering_controller:
            return self._filtering_controller.undo()
        return False
    
    def delegate_redo_filter(self) -> bool:
        """Delegate redo to filtering controller."""
        if self._filtering_controller:
            return self._filtering_controller.redo()
        return False
    
    # === Filtering Controller Delegation (v3.1 Phase 7 - STORY-2.4) ===
    
    def delegate_filtering_index_to_combine_operator(self, index: int) -> str:
        """
        Delegate index to combine operator conversion.
        
        v3.1 STORY-2.4: Centralized operator management.
        
        Args:
            index: Combobox index
        
        Returns:
            SQL operator string ('AND', 'AND NOT', 'OR')
        """
        if self._filtering_controller:
            try:
                return self._filtering_controller.index_to_combine_operator(index)
            except Exception as e:
                logger.warning(f"delegate_filtering_index_to_combine_operator failed: {e}")
        # Fallback
        return {0: 'AND', 1: 'AND NOT', 2: 'OR'}.get(index, 'AND')
    
    def delegate_filtering_combine_operator_to_index(self, operator: str) -> int:
        """
        Delegate combine operator to index conversion.
        
        v3.1 STORY-2.4: Handles translated operator values.
        
        Args:
            operator: SQL operator or translated equivalent
        
        Returns:
            Combobox index (0=AND, 1=AND NOT, 2=OR)
        """
        if self._filtering_controller:
            try:
                return self._filtering_controller.combine_operator_to_index(operator)
            except Exception as e:
                logger.warning(f"delegate_filtering_combine_operator_to_index failed: {e}")
        return 0
    
    def delegate_filtering_layers_to_filter_state_changed(self, is_checked: bool) -> bool:
        """
        Delegate layers_to_filter state change.
        
        v3.1 STORY-2.4: Centralized state change handling.
        
        Args:
            is_checked: True if layers to filter option is enabled
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._filtering_controller:
            try:
                self._filtering_controller.on_layers_to_filter_state_changed(is_checked)
                return True
            except Exception as e:
                logger.warning(f"delegate_filtering_layers_to_filter_state_changed failed: {e}")
                return False
        return False
    
    def delegate_filtering_combine_operator_state_changed(self, is_checked: bool) -> bool:
        """
        Delegate combine_operator state change.
        
        v3.1 STORY-2.4: Centralized state change handling.
        
        Args:
            is_checked: True if combine operator option is enabled
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._filtering_controller:
            try:
                self._filtering_controller.on_combine_operator_state_changed(is_checked)
                return True
            except Exception as e:
                logger.warning(f"delegate_filtering_combine_operator_state_changed failed: {e}")
                return False
        return False
    
    def delegate_filtering_geometric_predicates_state_changed(self, is_checked: bool) -> bool:
        """
        Delegate geometric_predicates state change.
        
        v3.1 STORY-2.4: Centralized state change handling.
        
        Args:
            is_checked: True if geometric predicates option is enabled
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._filtering_controller:
            try:
                self._filtering_controller.on_geometric_predicates_state_changed(is_checked)
                return True
            except Exception as e:
                logger.warning(f"delegate_filtering_geometric_predicates_state_changed failed: {e}")
                return False
        return False
    
    def delegate_filtering_buffer_type_state_changed(self, is_checked: bool) -> bool:
        """
        Delegate buffer_type state change.
        
        v3.1 STORY-2.4: Centralized state change handling.
        
        Args:
            is_checked: True if buffer type option is enabled
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._filtering_controller:
            try:
                self._filtering_controller.on_buffer_type_state_changed(is_checked)
                return True
            except Exception as e:
                logger.warning(f"delegate_filtering_buffer_type_state_changed failed: {e}")
                return False
        return False

    def delegate_filtering_has_buffer_value_state_changed(self, is_checked: bool) -> bool:
        """
        Delegate has_buffer_value state change.
        
        v3.1 STORY-2.4: Centralized state change handling.
        
        Args:
            is_checked: True if buffer value option is enabled
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._filtering_controller:
            try:
                self._filtering_controller.on_has_buffer_value_state_changed(is_checked)
                return True
            except Exception as e:
                logger.warning(f"delegate_filtering_has_buffer_value_state_changed failed: {e}")
                return False
        return False

    def delegate_filtering_get_buffer_property_active(self) -> Optional[bool]:
        """
        Delegate getting buffer property active state.
        
        v3.1 STORY-2.4: Returns buffer property override state from controller.
        
        Returns:
            True if buffer property override is active, None if delegation failed
        """
        if self._filtering_controller:
            try:
                return self._filtering_controller.get_buffer_property_active()
            except Exception as e:
                logger.warning(f"delegate_filtering_get_buffer_property_active failed: {e}")
                return None
        return None

    def delegate_filtering_set_buffer_property_active(self, is_active: bool) -> bool:
        """
        Delegate setting buffer property active state.
        
        v3.1 STORY-2.4: Sets buffer property override state in controller.
        
        Args:
            is_active: Whether buffer property override should be active
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._filtering_controller:
            try:
                self._filtering_controller.set_buffer_property_active(is_active)
                return True
            except Exception as e:
                logger.warning(f"delegate_filtering_set_buffer_property_active failed: {e}")
                return False
        return False

    def delegate_filtering_get_target_layer_ids(self) -> Optional[list]:
        """
        Delegate getting target layer IDs.
        
        v3.1 STORY-2.4: Returns list of layer IDs selected for filtering.
        
        Returns:
            List of layer IDs or None if delegation failed
        """
        if self._filtering_controller:
            try:
                return self._filtering_controller.get_target_layer_ids()
            except Exception as e:
                logger.warning(f"delegate_filtering_get_target_layer_ids failed: {e}")
                return None
        return None

    def delegate_filtering_set_target_layer_ids(self, layer_ids: list) -> bool:
        """
        Delegate setting target layer IDs.
        
        v3.1 STORY-2.4: Updates list of layers selected for filtering.
        
        Args:
            layer_ids: List of layer IDs to set as filter targets
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._filtering_controller:
            try:
                self._filtering_controller.set_target_layer_ids(layer_ids)
                return True
            except Exception as e:
                logger.warning(f"delegate_filtering_set_target_layer_ids failed: {e}")
                return False
        return False

    def delegate_populate_layers_checkable_combobox(self, layer=None) -> bool:
        """
        Delegate populating the layers-to-filter checkable combobox.
        
        v3.1 Sprint 5: Migrated from dockwidget.
        
        Args:
            layer: Source layer (optional, uses current if None)
        
        Returns:
            True if population succeeded, False otherwise
        """
        if self._filtering_controller:
            try:
                return self._filtering_controller.populate_layers_checkable_combobox(layer)
            except Exception as e:
                logger.warning(f"delegate_populate_layers_checkable_combobox failed: {e}")
                return False
        return False

    def delegate_filtering_get_available_predicates(self) -> Optional[list]:
        """
        Delegate getting available predicates list.
        
        v3.1 STORY-2.4: Centralized predicate list from controller.
        
        Returns:
            List of predicate display names or None if delegation failed
        """
        if self._filtering_controller:
            try:
                return self._filtering_controller.get_available_predicates()
            except Exception as e:
                logger.warning(f"delegate_filtering_get_available_predicates failed: {e}")
                return None
        return None

    def delegate_filtering_get_available_buffer_types(self) -> Optional[list]:
        """
        Delegate getting available buffer types list.
        
        v3.1 STORY-2.4: Centralized buffer type list from controller.
        
        Returns:
            List of buffer type display names or None if delegation failed
        """
        if self._filtering_controller:
            try:
                return self._filtering_controller.get_available_buffer_types()
            except Exception as e:
                logger.warning(f"delegate_filtering_get_available_buffer_types failed: {e}")
                return None
        return None

    def delegate_filtering_get_available_combine_operators(self) -> Optional[list]:
        """
        Delegate getting available combine operators list.
        
        v3.1 STORY-2.4: Centralized operator list from controller.
        
        Returns:
            List of operator display names or None if delegation failed
        """
        if self._filtering_controller:
            try:
                return self._filtering_controller.get_available_combine_operators()
            except Exception as e:
                logger.warning(f"delegate_filtering_get_available_combine_operators failed: {e}")
                return None
        return None
    
    def delegate_execute_export(self) -> bool:
        """Delegate export execution to exporting controller."""
        if self._exporting_controller:
            return self._exporting_controller.execute_export()
        return False

    # === Exporting Controller Delegation Methods ===
    
    def delegate_export_get_layers_to_export(self) -> Optional[list]:
        """
        Delegate getting layers to export.
        
        v3.1 STORY-2.5: Returns list of layer IDs selected for export.
        
        Returns:
            List of layer IDs or None if delegation failed
        """
        if self._exporting_controller:
            try:
                return self._exporting_controller.get_layers_to_export()
            except Exception as e:
                logger.warning(f"delegate_export_get_layers_to_export failed: {e}")
                return None
        return None
    
    def delegate_export_set_layers_to_export(self, layer_ids: list) -> bool:
        """
        Delegate setting layers to export.
        
        v3.1 STORY-2.5: Updates list of layers selected for export.
        
        Args:
            layer_ids: List of layer IDs to export
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._exporting_controller:
            try:
                self._exporting_controller.set_layers_to_export(layer_ids)
                return True
            except Exception as e:
                logger.warning(f"delegate_export_set_layers_to_export failed: {e}")
                return False
        return False
    
    def delegate_export_get_output_path(self) -> Optional[str]:
        """
        Delegate getting export output path.
        
        v3.1 STORY-2.5: Returns current output path.
        
        Returns:
            Output path string or None if delegation failed
        """
        if self._exporting_controller:
            try:
                return self._exporting_controller.get_output_path()
            except Exception as e:
                logger.warning(f"delegate_export_get_output_path failed: {e}")
                return None
        return None
    
    def delegate_populate_export_combobox(self) -> bool:
        """
        Delegate populating the export layers combobox.
        
        v3.1 Sprint 5: Migrated from dockwidget.
        
        Returns:
            True if population succeeded, False otherwise
        """
        if self._exporting_controller:
            try:
                return self._exporting_controller.populate_export_combobox()
            except Exception as e:
                logger.warning(f"delegate_populate_export_combobox failed: {e}")
                return False
        return False
    
    def delegate_export_set_output_path(self, path: str) -> bool:
        """
        Delegate setting export output path.
        
        v3.1 STORY-2.5: Sets output path for export.
        
        Args:
            path: Output path to set
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._exporting_controller:
            try:
                self._exporting_controller.set_output_path(path)
                return True
            except Exception as e:
                logger.warning(f"delegate_export_set_output_path failed: {e}")
                return False
        return False
    
    def delegate_export_get_output_format(self) -> Optional[str]:
        """
        Delegate getting export output format.
        
        v3.1 STORY-2.5: Returns current output format.
        
        Returns:
            Format value string or None if delegation failed
        """
        if self._exporting_controller:
            try:
                return self._exporting_controller.get_output_format().value
            except Exception as e:
                logger.warning(f"delegate_export_get_output_format failed: {e}")
                return None
        return None
    
    def delegate_export_on_format_changed(self, format_value: str) -> bool:
        """
        Delegate format change handling.
        
        v3.1 STORY-2.5: Handles export format change.
        
        Args:
            format_value: New format value
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._exporting_controller:
            try:
                self._exporting_controller.on_format_changed(format_value)
                return True
            except Exception as e:
                logger.warning(f"delegate_export_on_format_changed failed: {e}")
                return False
        return False
    
    def delegate_export_get_available_formats(self) -> Optional[list]:
        """
        Delegate getting available export formats.
        
        v3.1 STORY-2.5: Returns list of available formats.
        
        Returns:
            List of format values or None if delegation failed
        """
        if self._exporting_controller:
            try:
                formats = self._exporting_controller.get_available_formats()
                return [f.value for f in formats]
            except Exception as e:
                logger.warning(f"delegate_export_get_available_formats failed: {e}")
                return None
        return None
    
    def delegate_update_backend_indicator(
        self,
        layer,
        postgresql_connection_available=None,
        actual_backend=None
    ) -> bool:
        """
        Delegate backend indicator update to backend controller.
        
        Args:
            layer: Current QgsVectorLayer
            postgresql_connection_available: Whether PostgreSQL connection is available
            actual_backend: Forced backend name, if any
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._backend_controller and layer:
            try:
                self._backend_controller.update_for_layer(
                    layer,
                    postgresql_connection_available,
                    actual_backend
                )
                return True
            except Exception as e:
                logger.warning(f"delegate_update_backend_indicator failed: {e}")
                return False
        return False
    
    def delegate_handle_backend_click(self) -> bool:
        """Delegate backend indicator click to backend controller."""
        if self._backend_controller:
            try:
                self._backend_controller.handle_indicator_clicked()
                return True
            except Exception as e:
                logger.warning(f"delegate_handle_backend_click failed: {e}")
                return False
        return False
    
    def delegate_current_layer_changed(self, layer, manual_change=False) -> bool:
        """
        Delegate current layer change to layer sync controller.
        
        Args:
            layer: The new current layer (or None)
            manual_change: True if user manually selected layer (bypasses protection windows)
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._layer_sync_controller:
            try:
                return self._layer_sync_controller.on_current_layer_changed(layer, manual_change=manual_change)
            except Exception as e:
                logger.warning(f"delegate_current_layer_changed failed: {e}")
                return False
        return False
    
    def delegate_set_filtering_in_progress(self, in_progress: bool) -> bool:
        """Delegate filtering state to layer sync controller."""
        if self._layer_sync_controller:
            try:
                self._layer_sync_controller.set_filtering_in_progress(in_progress)
                return True
            except Exception as e:
                logger.warning(f"delegate_set_filtering_in_progress failed: {e}")
                return False
        return False
    
    def delegate_update_buffer_validation(self) -> bool:
        """
        Delegate buffer validation to property controller.
        
        v4.0 Sprint 1: Migrated from dockwidget._update_buffer_validation.
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._property_controller:
            try:
                self._property_controller.update_buffer_validation()
                return True
            except Exception as e:
                logger.warning(f"delegate_update_buffer_validation failed: {e}")
                return False
        return False
    
    def delegate_auto_select_optimal_backends(self) -> bool:
        """
        Delegate auto-select optimal backends to backend controller.
        
        v4.0 Sprint 1: Migrated from dockwidget.auto_select_optimal_backends.
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._backend_controller:
            try:
                self._backend_controller.auto_select_optimal_backends()
                return True
            except Exception as e:
                logger.warning(f"delegate_auto_select_optimal_backends failed: {e}")
                return False
        return False
    
    def delegate_ensure_valid_current_layer(self, layer) -> 'Optional[QgsVectorLayer]':
        """
        Delegate layer validation to layer sync controller.
        
        v4.0 Sprint 1: Migrated from dockwidget._ensure_valid_current_layer.
        
        Args:
            layer: Proposed layer (can be None)
            
        Returns:
            Valid layer or None
        """
        if self._layer_sync_controller:
            try:
                return self._layer_sync_controller._ensure_valid_current_layer(layer)
            except Exception as e:
                logger.warning(f"delegate_ensure_valid_current_layer failed: {e}")
                return None
        return None
    
    def delegate_is_layer_truly_deleted(self, layer: 'Optional[QgsVectorLayer]') -> bool:
        """
        Delegate layer deletion check to layer sync controller.
        
        v4.0 Sprint 2: Centralized layer deletion check with filtering protection.
        
        Args:
            layer: Layer to check (can be None)
            
        Returns:
            True if layer is truly deleted
        """
        if self._layer_sync_controller:
            try:
                return self._layer_sync_controller.is_layer_truly_deleted(layer)
            except Exception as e:
                logger.warning(f"delegate_is_layer_truly_deleted failed: {e}")
                # On error, assume deleted (safe fallback)
                return True
        # No controller: use simple None check
        return layer is None
    
    def delegate_reset_layer_expressions(self, layer_props: dict) -> bool:
        """
        Delegate expression reset to exploring controller.
        
        v4.0 Sprint 1: Migrated from dockwidget._reset_layer_expressions.
        
        Args:
            layer_props: Layer properties dict
            
        Returns:
            True if delegation succeeded
        """
        if self._exploring_controller:
            try:
                self._exploring_controller.reset_layer_expressions(layer_props)
                return True
            except Exception as e:
                logger.warning(f"delegate_reset_layer_expressions failed: {e}")
                return False
        return False
    
    def delegate_detect_multi_step_filter(
        self,
        layer: 'QgsVectorLayer',
        layer_props: dict
    ) -> Tuple[bool, bool]:
        """
        Delegate multi-step filter detection to filtering controller.
        
        v4.0 Sprint 2: Migrated from dockwidget._detect_multi_step_filter.
        
        Args:
            layer: The source layer
            layer_props: Layer properties dict from PROJECT_LAYERS
            
        Returns:
            Tuple[bool, bool]: (delegation_succeeded, filter_detected)
        """
        if self._filtering_controller:
            try:
                result = self._filtering_controller.detect_multi_step_filter(
                    layer, layer_props
                )
                return (True, result)
            except Exception as e:
                logger.warning(f"delegate_detect_multi_step_filter failed: {e}")
                return (False, False)
        return (False, False)
    
    # === State Synchronization ===
    
    def sync_from_dockwidget(self) -> None:
        """
        Synchronize controller state from dockwidget widgets.
        
        Call this after dockwidget widgets are initialized
        to set initial controller state.
        """
        if not self._is_setup:
            return
        
        dw = self._dockwidget
        
        # Sync current layer
        if hasattr(dw, 'current_layer') and dw.current_layer:
            if self._exploring_controller:
                self._exploring_controller.set_layer(dw.current_layer)
            if self._filtering_controller:
                self._filtering_controller.set_source_layer(dw.current_layer)
        
        logger.debug("Controller state synchronized from dockwidget")
    
    def sync_to_dockwidget(self) -> None:
        """
        Synchronize dockwidget widgets from controller state.
        
        Call this to update UI from controller state,
        for example after loading a configuration.
        
        v5.0: Full implementation of widget synchronization.
        """
        if not self._is_setup:
            return
        
        dw = self._dockwidget
        
        # Sync exploring controller state to widgets
        if self._exploring_controller and hasattr(self._exploring_controller, 'current_layer'):
            layer = self._exploring_controller.current_layer
            if layer and hasattr(dw, 'mMapLayerComboBox_exploring_layer'):
                dw.mMapLayerComboBox_exploring_layer.setLayer(layer)
        
        # Sync filtering controller state to widgets
        if self._filtering_controller:
            # Sync source layer
            if hasattr(self._filtering_controller, 'source_layer'):
                layer = self._filtering_controller.source_layer
                if layer and hasattr(dw, 'mMapLayerComboBox_filtering_source_layer'):
                    dw.mMapLayerComboBox_filtering_source_layer.setLayer(layer)
            
            # Sync active expression
            if hasattr(self._filtering_controller, 'active_expression'):
                expr = self._filtering_controller.active_expression
                if expr and hasattr(dw, 'mQgsFieldExpressionWidget_filtering_active_expression'):
                    widget = dw.mQgsFieldExpressionWidget_filtering_active_expression
                    if hasattr(widget, 'setExpression'):
                        widget.setExpression(expr)
        
        # Sync exporting controller state to widgets
        if self._exporting_controller:
            if hasattr(self._exporting_controller, 'export_format'):
                fmt = self._exporting_controller.export_format
                if fmt and hasattr(dw, 'mComboBox_exporting_format'):
                    index = dw.mComboBox_exporting_format.findText(fmt)
                    if index >= 0:
                        dw.mComboBox_exporting_format.setCurrentIndex(index)
        
        logger.debug("Dockwidget synchronized from controller state")
    
    # === Status ===
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get integration status for debugging.
        
        Returns:
            Status dictionary
        """
        return {
            'enabled': self._enabled,
            'is_setup': self._is_setup,
            'registry_count': len(self._registry) if self._registry else 0,
            'connections_count': len(self._connections),
            'controllers': {
                'exploring': self._exploring_controller is not None,
                'filtering': self._filtering_controller is not None,
                'exporting': self._exporting_controller is not None,
                'config': self._config_controller is not None
            }
        }

    # === Config Controller Delegation Methods ===
    
    def delegate_config_data_changed(self, input_data: Any = None) -> bool:
        """
        Delegate configuration data change handling.
        
        v3.1 STORY-2.5: Centralized config change handling.
        
        Args:
            input_data: Data that changed
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._config_controller:
            try:
                self._config_controller.data_changed_configuration_model(input_data)
                return True
            except Exception as e:
                logger.warning(f"delegate_config_data_changed failed: {e}")
                return False
        return False
    
    def delegate_config_apply_pending_changes(self) -> bool:
        """
        Delegate applying pending config changes.
        
        v3.1 STORY-2.5: Applies all pending configuration changes.
        
        Returns:
            True if all changes applied successfully, False otherwise
        """
        if self._config_controller:
            try:
                return self._config_controller.apply_pending_config_changes()
            except Exception as e:
                logger.warning(f"delegate_config_apply_pending_changes failed: {e}")
                return False
        return False
    
    def delegate_config_cancel_pending_changes(self) -> bool:
        """
        Delegate canceling pending config changes.
        
        v3.1 STORY-2.5: Cancels all pending changes and reverts to saved state.
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._config_controller:
            try:
                self._config_controller.cancel_pending_config_changes()
                return True
            except Exception as e:
                logger.warning(f"delegate_config_cancel_pending_changes failed: {e}")
                return False
        return False
    
    def delegate_config_has_pending_changes(self) -> Optional[bool]:
        """
        Delegate checking if there are pending config changes.
        
        v3.1 STORY-2.5: Returns pending changes status.
        
        Returns:
            True if pending changes exist, None if delegation failed
        """
        if self._config_controller:
            try:
                return self._config_controller.has_pending_changes
            except Exception as e:
                logger.warning(f"delegate_config_has_pending_changes failed: {e}")
                return None
        return None
    
    def delegate_config_save(self) -> bool:
        """
        Delegate saving configuration.
        
        v3.1 STORY-2.5: Saves current configuration to file.
        
        Returns:
            True if save succeeded, False otherwise
        """
        if self._config_controller:
            try:
                return self._config_controller._save_configuration()
            except Exception as e:
                logger.warning(f"delegate_config_save failed: {e}")
                return False
        return False
    
    def delegate_config_reload(self) -> bool:
        """
        Delegate reloading configuration.
        
        v3.1 STORY-2.5: Reloads configuration from file.
        
        Returns:
            True if reload succeeded, False otherwise
        """
        if self._config_controller:
            try:
                return self._config_controller._reload_configuration()
            except Exception as e:
                logger.warning(f"delegate_config_reload failed: {e}")
                return False
        return False
    
    def delegate_config_get_current(self) -> Optional[Dict[str, Any]]:
        """
        Delegate getting current configuration.
        
        v3.1 STORY-2.5: Returns current config dictionary.
        
        Returns:
            Configuration dictionary or None if delegation failed
        """
        if self._config_controller:
            try:
                return self._config_controller.get_current_config()
            except Exception as e:
                logger.warning(f"delegate_config_get_current failed: {e}")
                return None
        return None
    
    def delegate_config_set_value(self, key: str, value: Any) -> bool:
        """
        Delegate setting a config value.
        
        v3.1 STORY-2.5: Sets a configuration value.
        
        Args:
            key: Configuration key
            value: Value to set
        
        Returns:
            True if value was set, False otherwise
        """
        if self._config_controller:
            try:
                return self._config_controller.set_config_value(key, value)
            except Exception as e:
                logger.warning(f"delegate_config_set_value failed: {e}")
                return False
        return False
    
    # ========================================
    # EXPORT DIALOG DELEGATION METHODS
    # v3.1 STORY-2.5 Phase 2
    # ========================================
    
    def delegate_export_can_export(self) -> Optional[bool]:
        """
        Delegate checking if export is possible.
        
        v3.1 STORY-2.5: Checks export preconditions.
        
        Returns:
            True if export possible, False if not, None if delegation failed
        """
        if self._exporting_controller:
            try:
                return self._exporting_controller.can_export()
            except Exception as e:
                logger.warning(f"delegate_export_can_export failed: {e}")
                return None
        return None
    
    def delegate_export_execute(self) -> bool:
        """
        Delegate export execution.
        
        v3.1 STORY-2.5: Executes the export operation.
        
        Returns:
            True if export succeeded, False otherwise
        """
        if self._exporting_controller:
            try:
                return self._exporting_controller.execute_export()
            except Exception as e:
                logger.warning(f"delegate_export_execute failed: {e}")
                return False
        return False
    
    def delegate_export_get_output_crs(self) -> Optional[str]:
        """
        Delegate getting output CRS.
        
        v3.1 STORY-2.5: Returns the output CRS authid.
        
        Returns:
            CRS authid string or None
        """
        if self._exporting_controller:
            try:
                return self._exporting_controller.get_output_crs()
            except Exception as e:
                logger.warning(f"delegate_export_get_output_crs failed: {e}")
                return None
        return None
    
    def delegate_export_set_output_crs(self, crs: str) -> bool:
        """
        Delegate setting output CRS.
        
        v3.1 STORY-2.5: Sets the output CRS.
        
        Args:
            crs: CRS authid string (e.g. 'EPSG:4326')
        
        Returns:
            True if set, False otherwise
        """
        if self._exporting_controller:
            try:
                self._exporting_controller.set_output_crs(crs)
                return True
            except Exception as e:
                logger.warning(f"delegate_export_set_output_crs failed: {e}")
                return False
        return False
    
    def delegate_export_get_zip_output(self) -> Optional[bool]:
        """
        Delegate getting zip output flag.
        
        v3.1 STORY-2.5: Returns whether output should be zipped.
        
        Returns:
            True if zip enabled, False if disabled, None if failed
        """
        if self._exporting_controller:
            try:
                return self._exporting_controller.get_zip_output()
            except Exception as e:
                logger.warning(f"delegate_export_get_zip_output failed: {e}")
                return None
        return None
    
    def delegate_export_set_zip_output(self, zip_it: bool) -> bool:
        """
        Delegate setting zip output flag.
        
        v3.1 STORY-2.5: Sets the zip output flag.
        
        Args:
            zip_it: True to zip output, False otherwise
        
        Returns:
            True if set, False otherwise
        """
        if self._exporting_controller:
            try:
                self._exporting_controller.set_zip_output(zip_it)
                return True
            except Exception as e:
                logger.warning(f"delegate_export_set_zip_output failed: {e}")
                return False
        return False
    
    def delegate_export_get_include_styles(self) -> Optional[bool]:
        """
        Delegate getting include styles flag.
        
        v3.1 STORY-2.5: Returns whether styles should be included.
        
        Returns:
            True if styles included, False if not, None if failed
        """
        if self._exporting_controller:
            try:
                return self._exporting_controller.get_include_styles()
            except Exception as e:
                logger.warning(f"delegate_export_get_include_styles failed: {e}")
                return None
        return None
    
    def delegate_export_set_include_styles(self, include: bool) -> bool:
        """
        Delegate setting include styles flag.
        
        v3.1 STORY-2.5: Sets whether styles should be included.
        
        Args:
            include: True to include styles, False otherwise
        
        Returns:
            True if set, False otherwise
        """
        if self._exporting_controller:
            try:
                self._exporting_controller.set_include_styles(include)
                return True
            except Exception as e:
                logger.warning(f"delegate_export_set_include_styles failed: {e}")
                return False
        return False
    
    def delegate_export_is_exporting(self) -> Optional[bool]:
        """
        Delegate checking if export is in progress.
        
        v3.1 STORY-2.5: Returns whether an export is currently running.
        
        Returns:
            True if exporting, False if not, None if failed
        """
        if self._exporting_controller:
            try:
                return self._exporting_controller.is_exporting()
            except Exception as e:
                logger.warning(f"delegate_export_is_exporting failed: {e}")
                return None
        return None
    
    def delegate_export_get_progress(self) -> Optional[float]:
        """
        Delegate getting export progress.
        
        v3.1 STORY-2.5: Returns current export progress.
        
        Returns:
            Progress as float 0.0-1.0, or None if failed
        """
        if self._exporting_controller:
            try:
                return self._exporting_controller.get_progress()
            except Exception as e:
                logger.warning(f"delegate_export_get_progress failed: {e}")
                return None
        return None
    
    def delegate_export_get_mode(self) -> Optional[str]:
        """
        Delegate getting export mode.
        
        v3.1 STORY-2.5 Phase 3: Returns the current export mode.
        
        Returns:
            Export mode string ('single', 'batch', etc.) or None if failed
        """
        if self._exporting_controller:
            try:
                mode = self._exporting_controller.get_export_mode()
                return mode.value if mode else None
            except Exception as e:
                logger.warning(f"delegate_export_get_mode failed: {e}")
                return None
        return None
    
    def delegate_export_set_mode(self, mode: str) -> bool:
        """
        Delegate setting export mode.
        
        v3.1 STORY-2.5 Phase 3: Sets the export mode.
        
        Args:
            mode: Export mode string ('single', 'batch', etc.)
        
        Returns:
            True if set, False otherwise
        """
        if self._exporting_controller:
            try:
                # Import ExportMode enum
                from .exporting_controller import ExportMode
                export_mode = ExportMode(mode) if mode else ExportMode.SINGLE
                self._exporting_controller.set_export_mode(export_mode)
                return True
            except Exception as e:
                logger.warning(f"delegate_export_set_mode failed: {e}")
                return False
        return False
    
    def delegate_export_add_layer(self, layer_id: str) -> bool:
        """
        Delegate adding a layer to export list.
        
        v3.1 STORY-2.5 Phase 3: Adds a layer to the export selection.
        
        Args:
            layer_id: Layer ID to add
        
        Returns:
            True if added, False otherwise
        """
        if self._exporting_controller:
            try:
                self._exporting_controller.add_layer(layer_id)
                return True
            except Exception as e:
                logger.warning(f"delegate_export_add_layer failed: {e}")
                return False
        return False
    
    def delegate_export_remove_layer(self, layer_id: str) -> bool:
        """
        Delegate removing a layer from export list.
        
        v3.1 STORY-2.5 Phase 3: Removes a layer from the export selection.
        
        Args:
            layer_id: Layer ID to remove
        
        Returns:
            True if removed, False otherwise
        """
        if self._exporting_controller:
            try:
                self._exporting_controller.remove_layer(layer_id)
                return True
            except Exception as e:
                logger.warning(f"delegate_export_remove_layer failed: {e}")
                return False
        return False
    
    def delegate_export_clear_layers(self) -> bool:
        """
        Delegate clearing all layers from export list.
        
        v3.1 STORY-2.5 Phase 3: Clears all layers from export selection.
        
        Returns:
            True if cleared, False otherwise
        """
        if self._exporting_controller:
            try:
                self._exporting_controller.clear_layers()
                return True
            except Exception as e:
                logger.warning(f"delegate_export_clear_layers failed: {e}")
                return False
        return False
    
    def delegate_export_on_layer_selection_changed(self, layer_ids: list) -> bool:
        """
        Delegate layer selection change notification.
        
        v3.1 STORY-2.5 Phase 3: Notifies controller of layer selection change.
        
        Args:
            layer_ids: List of selected layer IDs
        
        Returns:
            True if processed, False otherwise
        """
        if self._exporting_controller:
            try:
                self._exporting_controller.on_layer_selection_changed(layer_ids)
                return True
            except Exception as e:
                logger.warning(f"delegate_export_on_layer_selection_changed failed: {e}")
                return False
        return False
    
    def delegate_export_on_crs_changed(self, crs_string: str) -> bool:
        """
        Delegate CRS change notification.
        
        v3.1 STORY-2.5 Phase 3: Notifies controller of CRS change.
        
        Args:
            crs_string: CRS authid string (e.g. 'EPSG:4326')
        
        Returns:
            True if processed, False otherwise
        """
        if self._exporting_controller:
            try:
                self._exporting_controller.on_crs_changed(crs_string)
                return True
            except Exception as e:
                logger.warning(f"delegate_export_on_crs_changed failed: {e}")
                return False
        return False
    
    def delegate_export_on_output_path_changed(self, path: str) -> bool:
        """
        Delegate output path change notification.
        
        v3.1 STORY-2.5 Phase 3: Notifies controller of path change.
        
        Args:
            path: New output path
        
        Returns:
            True if processed, False otherwise
        """
        if self._exporting_controller:
            try:
                self._exporting_controller.on_output_path_changed(path)
                return True
            except Exception as e:
                logger.warning(f"delegate_export_on_output_path_changed failed: {e}")
                return False
        return False
    
    def delegate_export_get_last_result(self) -> Optional[dict]:
        """
        Delegate getting last export result.
        
        v3.1 STORY-2.5 Phase 3: Returns the last export result.
        
        Returns:
            Export result dictionary or None
        """
        if self._exporting_controller:
            try:
                result = self._exporting_controller.get_last_result()
                if result:
                    return {
                        'success': result.success,
                        'exported_count': result.exported_count,
                        'failed_count': result.failed_count,
                        'output_paths': result.output_paths,
                        'error_message': result.error_message
                    }
                return None
            except Exception as e:
                logger.warning(f"delegate_export_get_last_result failed: {e}")
                return None
        return None

    # === Favorites Controller Delegation (v4.0) ===
    
    def delegate_favorites_show_manager_dialog(self) -> bool:
        """
        Delegate favorites manager dialog display to FavoritesController.
        
        v4.0: Removes 376 lines of dialog code from dockwidget.
        
        Returns:
            bool: True if delegated successfully, False otherwise
        """
        if self._favorites_controller:
            try:
                self._favorites_controller.show_manager_dialog()
                return True
            except Exception as e:
                logger.warning(f"delegate_favorites_show_manager_dialog failed: {e}")
                return False
        return False
    
    def delegate_favorites_add_current(self) -> bool:
        """
        Delegate adding current filter to favorites.
        
        Returns:
            bool: True if delegated successfully, False otherwise
        """
        if self._favorites_controller:
            try:
                return self._favorites_controller.add_current_to_favorites()
            except Exception as e:
                logger.warning(f"delegate_favorites_add_current failed: {e}")
                return False
        return False
    
    def delegate_favorites_apply(self, favorite_id: str) -> bool:
        """
        Delegate applying a favorite filter.
        
        Args:
            favorite_id: The favorite ID to apply
            
        Returns:
            bool: True if delegated successfully, False otherwise
        """
        if self._favorites_controller:
            try:
                return self._favorites_controller.apply_favorite(favorite_id)
            except Exception as e:
                logger.warning(f"delegate_favorites_apply failed: {e}")
                return False
        return False
    
    def delegate_favorites_update_indicator(self) -> bool:
        """
        Delegate favorites indicator update.
        
        Returns:
            bool: True if delegated successfully, False otherwise
        """
        if self._favorites_controller:
            try:
                self._favorites_controller.update_indicator()
                return True
            except Exception as e:
                logger.warning(f"delegate_favorites_update_indicator failed: {e}")
                return False
        return False
    
    def delegate_favorites_on_indicator_clicked(self, event) -> bool:
        """
        Delegate favorites indicator click handling.
        
        Args:
            event: The mouse event
            
        Returns:
            bool: True if delegated successfully, False otherwise
        """
        if self._favorites_controller:
            try:
                self._favorites_controller.on_indicator_clicked(event)
                return True
            except Exception as e:
                logger.warning(f"delegate_favorites_on_indicator_clicked failed: {e}")
                return False
        return False

    # =========================================================================
    # Sprint 3: Layer Sync Controller Delegation Methods
    # =========================================================================

    def delegate_synchronize_layer_widgets(
        self,
        layer,
        layer_props: dict,
        manual_change: bool = False
    ) -> bool:
        """
        Delegate layer widget synchronization to LayerSyncController.
        
        v4.0 Sprint 3: Migrated from dockwidget._synchronize_layer_widgets.
        FIX 2026-01-14: Added manual_change parameter.
        
        Args:
            layer: The current layer to sync widgets to
            layer_props: Layer properties from PROJECT_LAYERS
            manual_change: True if user manually selected layer (bypasses protection)
            
        Returns:
            True if delegated successfully, False otherwise
        """
        if self._layer_sync_controller:
            try:
                return self._layer_sync_controller.synchronize_layer_widgets(
                    layer, layer_props, manual_change=manual_change
                )
            except Exception as e:
                logger.warning(f"delegate_synchronize_layer_widgets failed: {e}")
                return False
        return False

    def delegate_reconnect_layer_signals(
        self,
        widgets_to_reconnect: list,
        layer_props: dict
    ) -> bool:
        """
        Delegate layer signal reconnection to LayerSyncController.
        
        v4.0 Sprint 3: Migrated from dockwidget._reconnect_layer_signals.
        
        Args:
            widgets_to_reconnect: List of widget paths to reconnect
            layer_props: Layer properties from PROJECT_LAYERS
            
        Returns:
            True if delegated successfully, False otherwise
        """
        if self._layer_sync_controller:
            try:
                self._layer_sync_controller.reconnect_layer_signals(
                    widgets_to_reconnect, layer_props
                )
                return True
            except Exception as e:
                logger.warning(f"delegate_reconnect_layer_signals failed: {e}")
                return False
        return False

    def delegate_get_project_layers_data(
        self,
        project_layers: dict,
        project = None
    ) -> Optional[dict]:
        """
        Delegate project layers data processing to LayerSyncController.
        
        v4.0 Sprint 3: Migrated from dockwidget.get_project_layers_from_app.
        
        Args:
            project_layers: Updated PROJECT_LAYERS dictionary from app
            project: QGIS project instance
            
        Returns:
            dict with status info or None if delegation failed
        """
        if self._layer_sync_controller:
            try:
                return self._layer_sync_controller.get_project_layers_data(
                    project_layers, project
                )
            except Exception as e:
                logger.warning(f"delegate_get_project_layers_data failed: {e}")
                return None
        return None

    def delegate_is_layer_truly_deleted(self, layer) -> Optional[bool]:
        """
        Delegate layer deletion check to LayerSyncController.
        
        v4.0 Sprint 3: Centralized layer deletion check with protection.
        
        Args:
            layer: The layer to check
            
        Returns:
            True if truly deleted, False if not, None if delegation failed
        """
        if self._layer_sync_controller:
            try:
                return self._layer_sync_controller.is_layer_truly_deleted(layer)
            except Exception as e:
                logger.warning(f"delegate_is_layer_truly_deleted failed: {e}")
                return None
        return None

    # =========================================================================
    # Sprint 3: Property Controller Delegation Methods
    # =========================================================================

    def delegate_reset_property_group(
        self,
        tuple_group: list,
        group_name: str,
        state: bool
    ) -> bool:
        """
        Delegate property group reset to PropertyController.
        
        v4.0 Sprint 3: Migrated from dockwidget.properties_group_state_reset_to_default.
        
        Args:
            tuple_group: List of property tuples in the group
            group_name: Name of the property group
            state: Target state (usually False for reset)
            
        Returns:
            True if delegated successfully, False otherwise
        """
        if self._property_controller:
            try:
                return self._property_controller.reset_property_group_to_default(
                    tuple_group, group_name, state
                )
            except Exception as e:
                logger.warning(f"delegate_reset_property_group failed: {e}")
                return False
        return False

    def delegate_change_project_property(
        self,
        input_property: str,
        input_data = None,
        custom_functions: dict = None
    ) -> bool:
        """
        Delegate project property change to PropertyController.
        
        v4.0 Sprint 3: Migrated from dockwidget.project_property_changed.
        
        Args:
            input_property: Property identifier string
            input_data: New value
            custom_functions: Optional callbacks dict
            
        Returns:
            True if delegated successfully, False otherwise
        """
        if self._property_controller:
            try:
                return self._property_controller.change_project_property(
                    input_property, input_data, custom_functions
                )
            except Exception as e:
                logger.warning(f"delegate_change_project_property failed: {e}")
                return False
        return False

    def delegate_change_layer_property(
        self,
        input_property: str,
        input_data = None,
        custom_functions: dict = None
    ) -> bool:
        """
        Delegate layer property change to PropertyController.
        
        v4.0 Sprint 3: Alternative to dockwidget.layer_property_changed.
        
        Args:
            input_property: Property identifier string
            input_data: New value
            custom_functions: Optional callbacks dict
            
        Returns:
            True if delegated successfully, False otherwise
        """
        if self._property_controller:
            try:
                return self._property_controller.change_property(
                    input_property, input_data, custom_functions
                )
            except Exception as e:
                logger.warning(f"delegate_change_layer_property failed: {e}")
                return False
        return False

    def delegate_update_buffer_validation(self) -> bool:
        """
        Delegate buffer validation update to PropertyController.
        
        v4.0 Sprint 3: Migrated from dockwidget._update_buffer_validation.
        
        Returns:
            True if delegated successfully, False otherwise
        """
        if self._property_controller:
            try:
                self._property_controller.update_buffer_validation()
                return True
            except Exception as e:
                logger.warning(f"delegate_update_buffer_validation failed: {e}")
                return False
        return False

    # ============================================================================
    # DELEGATION - UILayoutController
    # v4.0 Sprint 4: UI Layout Management delegation methods
    # ============================================================================

    def delegate_sync_multiple_selection_from_qgis(self) -> bool:
        """
        Delegate synchronization of multiple selection from QGIS to UILayoutController.
        
        v4.0 Sprint 4: Migrated from dockwidget._sync_multiple_selection_from_qgis.
        
        Returns:
            True if delegated successfully, False otherwise
        """
        if self._ui_layout_controller:
            try:
                self._ui_layout_controller.sync_multiple_selection_from_qgis()
                return True
            except Exception as e:
                logger.warning(f"delegate_sync_multiple_selection_from_qgis failed: {e}")
                return False
        return False

    def delegate_align_key_layouts(self) -> bool:
        """
        Delegate alignment of key layouts to UILayoutController.
        
        v4.0 Sprint 4: Migrated from dockwidget._align_key_layouts.
        
        Returns:
            True if delegated successfully, False otherwise
        """
        if self._ui_layout_controller:
            try:
                self._ui_layout_controller.align_key_layouts()
                return True
            except Exception as e:
                logger.warning(f"delegate_align_key_layouts failed: {e}")
                return False
        return False

    def delegate_create_horizontal_wrapper_for_side_action_bar(self) -> bool:
        """
        Delegate creation of horizontal wrapper for side action bar to UILayoutController.
        
        v4.0 Sprint 4: Migrated from dockwidget._create_horizontal_wrapper_for_side_action_bar.
        
        Returns:
            True if delegated successfully, False otherwise
        """
        if self._ui_layout_controller:
            try:
                self._ui_layout_controller.create_horizontal_wrapper_for_side_action_bar()
                return True
            except Exception as e:
                logger.warning(f"delegate_create_horizontal_wrapper_for_side_action_bar failed: {e}")
                return False
        return False

    def delegate_harmonize_checkable_pushbuttons(self) -> bool:
        """
        Delegate harmonization of checkable pushbuttons to UILayoutController.
        
        v4.0 Sprint 4: Migrated from dockwidget._harmonize_checkable_pushbuttons.
        
        Returns:
            True if delegated successfully, False otherwise
        """
        if self._ui_layout_controller:
            try:
                self._ui_layout_controller.harmonize_checkable_pushbuttons()
                return True
            except Exception as e:
                logger.warning(f"delegate_harmonize_checkable_pushbuttons failed: {e}")
                return False
        return False

    def delegate_apply_layout_spacing(self) -> bool:
        """
        Delegate application of layout spacing to UILayoutController.
        
        v4.0 Sprint 4: Migrated from dockwidget._apply_layout_spacing.
        
        Returns:
            True if delegated successfully, False otherwise
        """
        if self._ui_layout_controller:
            try:
                self._ui_layout_controller.apply_layout_spacing()
                return True
            except Exception as e:
                logger.warning(f"delegate_apply_layout_spacing failed: {e}")
                return False
        return False

    def __repr__(self) -> str:
        """String representation."""
        status = "active" if self._is_setup else "inactive"
        return f"ControllerIntegration({status}, controllers={len(self._registry) if self._registry else 0})"

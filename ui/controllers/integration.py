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
from typing import TYPE_CHECKING, Optional, Dict, Any
import logging

from .registry import ControllerRegistry, TabIndex
from .exploring_controller import ExploringController
from .filtering_controller import FilteringController
from .exporting_controller import ExportingController
from .backend_controller import BackendController
from .layer_sync_controller import LayerSyncController

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget
    from adapters.qgis.signals.signal_manager import SignalManager
    from core.services.filter_service import FilterService

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
    
    def setup(self) -> bool:
        """
        Setup all controllers and wire up signals.
        
        Returns:
            True if setup succeeded, False otherwise
        """
        if not self._enabled:
            logger.info("Controller integration is disabled")
            return False
        
        if self._is_setup:
            logger.warning("Controller integration already setup")
            return True
        
        try:
            # Create registry
            self._registry = ControllerRegistry()
            
            # Create controllers
            self._create_controllers()
            
            # Register controllers
            self._register_controllers()
            
            # Wire up signals
            self._connect_signals()
            
            # Setup all controllers
            self._registry.setup_all()
            
            self._is_setup = True
            logger.info("Controller integration setup complete")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup controller integration: {e}")
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
        
        logger.debug("All controllers created")
    
    def _register_controllers(self) -> None:
        """Register all controllers with the registry."""
        if not self._registry:
            return
        
        # Register with tab indices
        # Note: TabIndex.FILTERING = 0, but exploring is typically first
        # We register by name, tab index is for tab switching
        
        self._registry.register(
            'exploring',
            self._exploring_controller,
            tab_index=TabIndex.FILTERING  # Tab 0 - Exploring/Filtering combined?
        )
        
        self._registry.register(
            'filtering',
            self._filtering_controller,
            tab_index=TabIndex.FILTERING  # Tab 0
        )
        
        self._registry.register(
            'exporting',
            self._exporting_controller,
            tab_index=TabIndex.EXPORTING  # Tab 1
        )
        
        self._registry.register(
            'backend',
            self._backend_controller,
            tab_index=TabIndex.FILTERING  # Backend indicator visible on all tabs
        )
        
        self._registry.register(
            'layer_sync',
            self._layer_sync_controller,
            tab_index=TabIndex.FILTERING  # Layer sync active on all tabs
        )
        
        logger.debug("All controllers registered")
    
    def _connect_signals(self) -> None:
        """Connect dockwidget signals to controllers."""
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
        
        logger.debug(f"Connected {len(self._connections)} signals")
    
    def _disconnect_signals(self) -> None:
        """Disconnect all signals."""
        dw = self._dockwidget
        
        for signal_name, handler in self._connections:
            try:
                if signal_name == 'tabTools.currentChanged' and hasattr(dw, 'tabTools'):
                    dw.tabTools.currentChanged.disconnect(handler)
                elif signal_name == 'currentLayerChanged' and hasattr(dw, 'currentLayerChanged'):
                    dw.currentLayerChanged.disconnect(handler)
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
        """Handle current layer change event."""
        layer = getattr(self._dockwidget, 'current_layer', None)
        
        # Update exploring controller
        if self._exploring_controller:
            self._exploring_controller.set_layer(layer)
        
        # Update filtering controller
        if self._filtering_controller:
            self._filtering_controller.set_source_layer(layer)
    
    def _cleanup_on_error(self) -> None:
        """Cleanup after setup error."""
        self._exploring_controller = None
        self._filtering_controller = None
        self._exporting_controller = None
        self._registry = None
        self._connections.clear()
        self._is_setup = False
    
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
    
    def delegate_zoom_to_features(self, features: list, expression: str = None) -> bool:
        """
        Delegate zoom to features operation.
        
        Args:
            features: List of QgsFeature objects to zoom to
            expression: Optional expression string (for logging)
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._exploring_controller and features:
            try:
                return self._exploring_controller.zoom_to_features(features)
            except Exception as e:
                logger.warning(f"delegate_zoom_to_features failed: {e}")
                return False
        return False
    
    def delegate_flash_features(self, feature_ids: list) -> bool:
        """
        Delegate flash features operation to ExploringController.
        
        v3.1 Vague 2: Supports dockwidget exploring_identify_clicked delegation.
        
        Args:
            feature_ids: List of feature IDs to flash
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._exploring_controller and feature_ids:
            try:
                return self._exploring_controller.flash_features(feature_ids)
            except Exception as e:
                logger.warning(f"delegate_flash_features failed: {e}")
                return False
        return False
    
    def delegate_execute_filter(self) -> bool:
        """Delegate filter execution to filtering controller."""
        if self._filtering_controller:
            return self._filtering_controller.execute_filter()
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
    
    def delegate_execute_export(self) -> bool:
        """Delegate export execution to exporting controller."""
        if self._exporting_controller:
            return self._exporting_controller.execute_export()
        return False
    
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
    
    def delegate_current_layer_changed(self, layer) -> bool:
        """
        Delegate current layer change to layer sync controller.
        
        Args:
            layer: The new current layer (or None)
        
        Returns:
            True if delegation succeeded, False otherwise
        """
        if self._layer_sync_controller:
            try:
                self._layer_sync_controller.on_current_layer_changed(layer)
                return True
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
        """
        if not self._is_setup:
            return
        
        # TODO: Implement widget updates based on controller state
        # This would update combo boxes, text fields, etc.
        
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
                'exporting': self._exporting_controller is not None
            }
        }
    
    def __repr__(self) -> str:
        """String representation."""
        status = "active" if self._is_setup else "inactive"
        return f"ControllerIntegration({status}, controllers={len(self._registry) if self._registry else 0})"

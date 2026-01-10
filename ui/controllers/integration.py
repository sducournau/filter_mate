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
from .config_controller import ConfigController
from .favorites_controller import FavoritesController
from .property_controller import PropertyController

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
        self._config_controller: Optional[ConfigController] = None
        self._favorites_controller: Optional[FavoritesController] = None
        self._property_controller: Optional[PropertyController] = None
        
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
            self._config_controller = None
            self._favorites_controller = None
            self._property_controller = None
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
            dockwidget=self._dockwidget,
            signal_manager=self._signal_manager
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
        
        # v3.1 STORY-2.5: Register ConfigController
        self._registry.register(
            'config',
            self._config_controller,
            tab_index=TabIndex.CONFIGURATION  # Tab for configuration
        )
        
        # v4.0: Register FavoritesController
        self._registry.register(
            'favorites',
            self._favorites_controller,
            tab_index=TabIndex.FILTERING  # Favorites indicator visible on filtering tabs
        )
        
        # v4.0 Sprint 1: Register PropertyController
        self._registry.register(
            'property',
            self._property_controller,
            tab_index=TabIndex.FILTERING  # Property controller active on filtering tab
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

    def __repr__(self) -> str:
        """String representation."""
        status = "active" if self._is_setup else "inactive"
        return f"ControllerIntegration({status}, controllers={len(self._registry) if self._registry else 0})"

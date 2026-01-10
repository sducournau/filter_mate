"""
Layer Sync Controller for FilterMate.

Manages layer change synchronization and widget updates.
Extracted from filter_mate_dockwidget.py (lines 9826-10796).

CRITICAL: This controller handles the post-filter protection
to prevent CRIT-005 (layer loss after filter).

Story: MIG-073
Phase: 6 - God Class DockWidget Migration
"""

from typing import TYPE_CHECKING, Optional, List
import logging
import time

from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import QgsVectorLayer, QgsProject

from .base_controller import BaseController

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)

# Protection window after filter completes (seconds)
# Must cover refresh_delay (1500ms) + layer.reload() + margin
POST_FILTER_PROTECTION_WINDOW = 5.0


class LayerSyncController(BaseController):
    """
    Controller for layer synchronization.

    Handles:
    - Layer change events
    - Widget synchronization on layer change
    - Post-filter protection (CRIT-005 fix)
    - Layer add/remove events

    CRITICAL FIX (CRIT-005): This controller implements a 5-second protection
    window after filtering to prevent unwanted layer changes from async signals.

    Signals:
        layer_synchronized: Emitted when layer sync completes
        sync_blocked: Emitted when sync is blocked (protection)
        layer_changed: Emitted when current layer changes

    Example:
        controller = LayerSyncController(dockwidget)
        controller.setup()

        # React to sync events
        controller.layer_synchronized.connect(on_layer_synced)
        controller.sync_blocked.connect(on_sync_blocked)
    """

    layer_synchronized = pyqtSignal(object)  # QgsVectorLayer
    sync_blocked = pyqtSignal(str)  # reason
    layer_changed = pyqtSignal(object)  # QgsVectorLayer or None

    def __init__(self, dockwidget: 'FilterMateDockWidget') -> None:
        """
        Initialize the layer sync controller.

        Args:
            dockwidget: Main dockwidget reference
        """
        super().__init__(dockwidget)
        # Post-filter protection state
        self._filter_completed_time: float = 0
        self._saved_layer_id_before_filter: Optional[str] = None
        self._current_layer_id: Optional[str] = None
        # Lock to prevent reentrant calls
        self._updating_current_layer: bool = False
        # Filtering state
        self._filtering_in_progress: bool = False

    @property
    def current_layer_id(self) -> Optional[str]:
        """Get the current layer ID."""
        return self._current_layer_id

    @property
    def is_within_protection_window(self) -> bool:
        """Check if we're within the post-filter protection window."""
        return self._is_within_post_filter_protection()

    @property
    def protection_remaining(self) -> float:
        """Get remaining protection window time in seconds."""
        if self._filter_completed_time <= 0:
            return 0.0
        elapsed = time.time() - self._filter_completed_time
        remaining = POST_FILTER_PROTECTION_WINDOW - elapsed
        return max(0.0, remaining)

    def setup(self) -> None:
        """
        Connect to layer change signals.

        Connects to the QGIS layer change events to track layer selection.
        """
        self._sync_with_dockwidget()
        self._initialized = True
        logger.debug("LayerSyncController setup complete")

    def teardown(self) -> None:
        """Clean up resources."""
        self.clear_protection()
        super().teardown()

    def on_tab_activated(self) -> None:
        """Handle tab activation."""
        super().on_tab_activated()

    def on_tab_deactivated(self) -> None:
        """Handle tab deactivation."""
        super().on_tab_deactivated()

    # === Public API ===

    def on_current_layer_changed(
        self,
        layer: Optional[QgsVectorLayer]
    ) -> bool:
        """
        Handle current layer change event.

        Orchestrates layer change by validating, checking protection window,
        and synchronizing widgets.

        CRITICAL: This method implements CRIT-005 fix to prevent layer loss.

        Args:
            layer: New current layer (can be None)

        Returns:
            True if layer change was accepted, False if blocked
        """
        layer_name = layer.name() if layer else "(None)"
        logger.debug(f"on_current_layer_changed called with layer='{layer_name}'")

        # Check lock for reentrant calls
        if self._updating_current_layer:
            logger.debug("on_current_layer_changed BLOCKED - already updating")
            return False

        # Block during active filtering
        if self._filtering_in_progress:
            logger.debug("🛡️ on_current_layer_changed BLOCKED - filtering in progress")
            self.sync_blocked.emit("filtering_in_progress")
            return False

        # CRITICAL: Check post-filter protection window
        if self._is_within_post_filter_protection():
            elapsed = time.time() - self._filter_completed_time
            
            # Case 1: layer=None - BLOCK to prevent auto-selection of wrong layer
            if layer is None:
                logger.info(
                    f"🛡️ on_current_layer_changed BLOCKED - layer=None during "
                    f"protection window (elapsed={elapsed:.3f}s)"
                )
                self._restore_protected_layer()
                self.sync_blocked.emit("layer_none_during_protection")
                return False

            # Case 2: Different layer than saved - BLOCK
            if (self._saved_layer_id_before_filter and 
                layer.id() != self._saved_layer_id_before_filter):
                logger.info(
                    f"🛡️ on_current_layer_changed BLOCKED - layer '{layer_name}' "
                    f"!= saved during protection (elapsed={elapsed:.3f}s)"
                )
                self._restore_protected_layer()
                self.sync_blocked.emit("layer_change_during_protection")
                return False

            # Case 3: Same layer as saved - ALLOW
            logger.debug(
                f"✓ on_current_layer_changed ALLOWED - same layer during "
                f"protection (elapsed={elapsed:.3f}s)"
            )

        # Validate layer
        layer = self._ensure_valid_current_layer(layer)
        if layer is None:
            if self._has_project_layers():
                logger.error(
                    "❌ CRITICAL - Could not find valid layer despite having layers!"
                )
            else:
                logger.debug("No layers in project - current_layer remains None")
            return False

        # Accept the layer change
        self._updating_current_layer = True
        try:
            self._current_layer_id = layer.id()
            self.layer_changed.emit(layer)
            self.layer_synchronized.emit(layer)
            logger.debug(f"Layer synchronized: {layer.name()}")
            return True
        finally:
            self._updating_current_layer = False

    def set_filtering_in_progress(self, in_progress: bool) -> None:
        """
        Set filtering state for protection.

        Args:
            in_progress: True when filtering starts, False when complete
        """
        self._filtering_in_progress = in_progress
        
        # Sync with dockwidget if exists
        if hasattr(self.dockwidget, '_filtering_in_progress'):
            self.dockwidget._filtering_in_progress = in_progress

        if in_progress:
            logger.debug("Filtering started - layer changes will be blocked")
        else:
            logger.debug("Filtering completed - layer changes allowed")

    def save_layer_before_filter(self, layer: Optional[QgsVectorLayer] = None) -> None:
        """
        Save current layer before filtering starts.

        Called at the beginning of filter operation to preserve layer selection.

        Args:
            layer: Layer to save (uses current_layer if not provided)
        """
        if layer is None:
            layer = self._get_current_layer()

        if layer:
            self._saved_layer_id_before_filter = layer.id()
            logger.debug(f"Saved layer before filter: {layer.name()}")
        else:
            self._saved_layer_id_before_filter = None

    def mark_filter_completed(self) -> None:
        """
        Mark filter as completed, starting protection window.

        Called when filter task completes to start the 5-second protection.
        """
        self._filter_completed_time = time.time()
        self._filtering_in_progress = False
        
        # Sync with dockwidget
        if hasattr(self.dockwidget, '_filter_completed_time'):
            self.dockwidget._filter_completed_time = self._filter_completed_time
        if hasattr(self.dockwidget, '_filtering_in_progress'):
            self.dockwidget._filtering_in_progress = False

        logger.info(
            f"Filter completed - protection window started "
            f"({POST_FILTER_PROTECTION_WINDOW}s)"
        )

    def clear_protection(self) -> None:
        """
        Clear the post-filter protection state.

        Can be called to manually clear protection before timeout.
        """
        self._filter_completed_time = 0
        self._saved_layer_id_before_filter = None
        self._filtering_in_progress = False
        
        # Sync with dockwidget
        if hasattr(self.dockwidget, '_filter_completed_time'):
            self.dockwidget._filter_completed_time = 0
        if hasattr(self.dockwidget, '_saved_layer_id_before_filter'):
            self.dockwidget._saved_layer_id_before_filter = None
        if hasattr(self.dockwidget, '_filtering_in_progress'):
            self.dockwidget._filtering_in_progress = False

        logger.debug("Post-filter protection cleared")

    def restore_layer_after_filter(self) -> Optional[QgsVectorLayer]:
        """
        Restore the saved layer after filtering.

        Returns:
            The restored layer, or None if restoration failed
        """
        if not self._saved_layer_id_before_filter:
            return None

        project = QgsProject.instance()
        layer = project.mapLayer(self._saved_layer_id_before_filter)

        if layer and layer.isValid():
            self._set_current_layer(layer)
            logger.info(f"Restored layer after filter: {layer.name()}")
            return layer
        else:
            logger.warning(
                f"Could not restore layer {self._saved_layer_id_before_filter}"
            )
            return None

    def validate_layer(self, layer: QgsVectorLayer) -> bool:
        """
        Validate that a layer is usable.

        Args:
            layer: Layer to validate

        Returns:
            True if layer is valid and usable
        """
        if layer is None:
            return False

        try:
            # Check if C++ object is valid
            _ = layer.name()
            _ = layer.id()
            return layer.isValid()
        except (RuntimeError, AttributeError):
            return False

    def is_layer_truly_deleted(self, layer: Optional[QgsVectorLayer]) -> bool:
        """
        Check if a layer is truly deleted, accounting for filtering operations.
        
        v4.0 Sprint 2: Centralized layer deletion check with filtering protection.
        
        During and immediately after filtering, layers can temporarily appear as
        "deleted" to sip.isdeleted() even though they're still valid. This method
        provides a centralized check that respects:
        1. Active filtering operations (_filtering_in_progress flag)
        2. Post-filtering protection window (configured in POST_FILTER_PROTECTION_WINDOW)
        3. Actual C++ object deletion status via sip
        
        Args:
            layer: The layer to check (can be None)
            
        Returns:
            True if layer is truly deleted and should be cleared, False otherwise
        """
        # If layer is None, it's already "deleted" in a sense
        if layer is None:
            return True
        
        # During filtering, NEVER consider layer as deleted
        if self._filtering_in_progress:
            layer_name = layer.name() if hasattr(layer, 'name') else 'unknown'
            logger.debug(
                f"🛡️ is_layer_truly_deleted BLOCKED - filtering in progress "
                f"(layer={layer_name})"
            )
            return False
        
        # Within protection window after filtering, NEVER consider layer as deleted
        if self._is_within_post_filter_protection():
            elapsed = time.time() - self._filter_completed_time
            layer_name = layer.name() if hasattr(layer, 'name') else 'unknown'
            logger.debug(
                f"🛡️ is_layer_truly_deleted BLOCKED - within protection window "
                f"(elapsed={elapsed:.3f}s, layer={layer_name})"
            )
            return False
        
        # Perform the actual deletion check via sip
        try:
            import sip
            if sip.isdeleted(layer):
                logger.debug("✅ Layer C++ object is truly deleted")
                return True
            else:
                return False
        except (RuntimeError, TypeError, AttributeError) as e:
            # If we can't check, assume it's deleted
            logger.debug(f"Layer deletion check failed with {type(e).__name__}: {e}")
            return True

    # === Private Methods ===

    def _sync_with_dockwidget(self) -> None:
        """Sync state from dockwidget."""
        # Get protection state
        if hasattr(self.dockwidget, '_filter_completed_time'):
            self._filter_completed_time = self.dockwidget._filter_completed_time or 0
        if hasattr(self.dockwidget, '_saved_layer_id_before_filter'):
            self._saved_layer_id_before_filter = self.dockwidget._saved_layer_id_before_filter
        if hasattr(self.dockwidget, '_filtering_in_progress'):
            self._filtering_in_progress = self.dockwidget._filtering_in_progress or False
        if hasattr(self.dockwidget, '_updating_current_layer'):
            self._updating_current_layer = self.dockwidget._updating_current_layer or False

    def _is_within_post_filter_protection(self) -> bool:
        """Check if we're within the post-filter protection window."""
        if self._filter_completed_time <= 0:
            return False
        elapsed = time.time() - self._filter_completed_time
        return elapsed < POST_FILTER_PROTECTION_WINDOW

    def _restore_protected_layer(self) -> None:
        """Restore the protected layer to dockwidget."""
        restore_layer = None

        # Try saved_layer_id first
        if self._saved_layer_id_before_filter:
            project = QgsProject.instance()
            restore_layer = project.mapLayer(self._saved_layer_id_before_filter)

        # Fallback to current_layer
        if not restore_layer:
            restore_layer = self._get_current_layer()

        # Last resort: combobox layer
        if not restore_layer:
            if hasattr(self.dockwidget, 'comboBox_filtering_current_layer'):
                combo_layer = self.dockwidget.comboBox_filtering_current_layer.currentLayer()
                if combo_layer and combo_layer.isValid():
                    restore_layer = combo_layer

        if restore_layer and restore_layer.isValid():
            self._set_current_layer(restore_layer)
            logger.info(f"Restored protected layer: {restore_layer.name()}")
        else:
            logger.warning("No valid layer to restore during protection")

    def _ensure_valid_current_layer(
        self,
        layer: Optional[QgsVectorLayer]
    ) -> Optional[QgsVectorLayer]:
        """
        Ensure we have a valid layer, selecting first available if needed.

        Never allows current_layer to be None if layers exist in project.

        Args:
            layer: Proposed layer (can be None)

        Returns:
            A valid layer, or None if no layers available
        """
        # If layer is valid, return it
        if layer and self.validate_layer(layer):
            return layer

        # Try to find a fallback layer
        return self._find_fallback_layer()

    def _find_fallback_layer(self) -> Optional[QgsVectorLayer]:
        """Find a fallback layer from project."""
        # Try PROJECT_LAYERS first
        if hasattr(self.dockwidget, 'PROJECT_LAYERS'):
            for layer_id in self.dockwidget.PROJECT_LAYERS:
                project = QgsProject.instance()
                layer = project.mapLayer(layer_id)
                if layer and self.validate_layer(layer):
                    logger.debug(f"Using fallback layer from PROJECT_LAYERS: {layer.name()}")
                    return layer

        # Try all project layers
        project = QgsProject.instance()
        for layer in project.mapLayers().values():
            if isinstance(layer, QgsVectorLayer) and self.validate_layer(layer):
                logger.debug(f"Using fallback layer from project: {layer.name()}")
                return layer

        return None

    def _get_current_layer(self) -> Optional[QgsVectorLayer]:
        """Get current layer from dockwidget."""
        if hasattr(self.dockwidget, 'current_layer'):
            layer = self.dockwidget.current_layer
            if layer and self.validate_layer(layer):
                return layer
        return None

    def _set_current_layer(self, layer: QgsVectorLayer) -> None:
        """Set current layer on dockwidget."""
        if hasattr(self.dockwidget, 'current_layer'):
            self.dockwidget.current_layer = layer
        
        # Update combobox
        if hasattr(self.dockwidget, 'comboBox_filtering_current_layer'):
            combo = self.dockwidget.comboBox_filtering_current_layer
            combo.blockSignals(True)
            combo.setLayer(layer)
            combo.blockSignals(False)

        self._current_layer_id = layer.id()

    def _has_project_layers(self) -> bool:
        """Check if project has layers."""
        if hasattr(self.dockwidget, 'PROJECT_LAYERS'):
            return len(self.dockwidget.PROJECT_LAYERS) > 0
        return False

    # === Layer Events ===

    def on_layer_added(self, layer: QgsVectorLayer) -> None:
        """
        Handle layer added event.

        Args:
            layer: Layer that was added
        """
        if not isinstance(layer, QgsVectorLayer):
            return

        if not self.validate_layer(layer):
            return

        logger.debug(f"Layer added: {layer.name()}")

        # If no current layer, set this as current
        if self._get_current_layer() is None:
            self._set_current_layer(layer)

    def on_layers_will_be_removed(self, layer_ids: List[str]) -> None:
        """
        Handle layers about to be removed.

        Args:
            layer_ids: IDs of layers being removed
        """
        current_layer = self._get_current_layer()
        if current_layer is None:
            return

        # If current layer is being removed, find a replacement
        if current_layer.id() in layer_ids:
            logger.debug(f"Current layer {current_layer.name()} being removed")
            
            # Clear saved layer if it's being removed
            if self._saved_layer_id_before_filter in layer_ids:
                self._saved_layer_id_before_filter = None

            # Find replacement
            replacement = None
            project = QgsProject.instance()
            for layer in project.mapLayers().values():
                if (isinstance(layer, QgsVectorLayer) and 
                    layer.id() not in layer_ids and
                    self.validate_layer(layer)):
                    replacement = layer
                    break

            if replacement:
                self._set_current_layer(replacement)
                logger.info(f"Replaced current layer with: {replacement.name()}")
            else:
                logger.warning("No replacement layer available")

    def on_layer_removed(self, layer_id: str) -> None:
        """
        Handle layer removed event.

        Args:
            layer_id: ID of removed layer
        """
        # Clear saved layer if it was removed
        if self._saved_layer_id_before_filter == layer_id:
            self._saved_layer_id_before_filter = None
            logger.debug("Cleared saved layer (was removed)")

        # Clear current layer ID if it was removed
        if self._current_layer_id == layer_id:
            self._current_layer_id = None

    # =========================================================================
    # Sprint 3: Widget Synchronization Methods (migrated from dockwidget)
    # =========================================================================

    def synchronize_layer_widgets(
        self,
        layer: QgsVectorLayer,
        layer_props: dict
    ) -> bool:
        """
        Synchronize all widgets with the new current layer.
        
        Updates comboboxes, field expression widgets, and backend indicator.
        Migrated from filter_mate_dockwidget._synchronize_layer_widgets.
        
        v4.0 Sprint 3: Full migration from dockwidget.
        
        CRITICAL: Respects post-filter protection window to prevent CRIT-005.
        
        Args:
            layer: The current layer to sync widgets to
            layer_props: Layer properties from PROJECT_LAYERS
            
        Returns:
            True if synchronization completed, False if blocked
        """
        dw = self.dockwidget
        
        # Check if widgets are initialized
        if not getattr(dw, 'widgets_initialized', False):
            logger.debug("synchronize_layer_widgets: widgets not initialized")
            return False
        
        # Check protection window for combobox sync
        skip_combobox_sync = self._should_skip_combobox_sync(layer)
        
        # Detect multi-step filter
        if hasattr(dw, '_detect_multi_step_filter'):
            dw._detect_multi_step_filter(layer, layer_props)
        
        # Sync current layer combobox (unless protected)
        if not skip_combobox_sync:
            self._sync_current_layer_combobox(layer)
        
        # Update backend indicator
        self._update_backend_indicator(layer, layer_props)
        
        # Initialize buffer property
        if hasattr(dw, 'filtering_init_buffer_property'):
            dw.filtering_init_buffer_property()
        
        # Synchronize all layer property widgets
        self._sync_layer_property_widgets(layer, layer_props)
        
        # Populate layers combobox
        self._sync_layers_to_filter_combobox()
        
        # Synchronize state-dependent widgets
        self._sync_state_dependent_widgets()
        
        # Update centroids source checkbox
        if hasattr(dw, '_update_centroids_source_checkbox_state'):
            dw._update_centroids_source_checkbox_state()
        
        logger.debug(f"synchronize_layer_widgets completed for {layer.name()}")
        self.layer_synchronized.emit(layer)
        return True

    def reconnect_layer_signals(
        self,
        widgets_to_reconnect: List[List[str]],
        layer_props: dict
    ) -> None:
        """
        Reconnect all layer-related widget signals after updates.
        
        Also restores exploring groupbox UI state and connects layer selection signal.
        Migrated from filter_mate_dockwidget._reconnect_layer_signals.
        
        v4.0 Sprint 3: Full migration from dockwidget.
        
        Args:
            widgets_to_reconnect: List of widget paths to reconnect
            layer_props: Layer properties from PROJECT_LAYERS
        """
        dw = self.dockwidget
        
        # Exploring widget signals - already reconnected in _reload_exploration_widgets
        exploring_signal_prefixes = [
            ["EXPLORING", "SINGLE_SELECTION_FEATURES"],
            ["EXPLORING", "SINGLE_SELECTION_EXPRESSION"],
            ["EXPLORING", "MULTIPLE_SELECTION_FEATURES"],
            ["EXPLORING", "MULTIPLE_SELECTION_EXPRESSION"],
            ["EXPLORING", "CUSTOM_SELECTION_EXPRESSION"],
            ["EXPLORING", "IDENTIFY"],
            ["EXPLORING", "ZOOM"]
        ]
        
        # Reconnect only non-exploring signals
        for widget_path in widgets_to_reconnect:
            if widget_path not in exploring_signal_prefixes:
                if hasattr(dw, 'manageSignal'):
                    dw.manageSignal(widget_path, 'connect')
        
        # Reconnect legend link if enabled
        self._reconnect_legend_link()
        
        # Connect selectionChanged signal
        self._connect_layer_selection_signal()
        
        # Restore exploring groupbox UI state
        self._restore_exploring_groupbox_state(layer_props)
        
        # Link widgets and restore feature selection
        self._restore_feature_selection_state(layer_props)
        
        logger.debug("reconnect_layer_signals completed")

    def get_project_layers_data(
        self,
        project_layers: dict,
        project = None
    ) -> dict:
        """
        Update dockwidget with latest layer information from FilterMateApp.
        
        Called when layer management tasks complete. Orchestrates UI refresh.
        Migrated from filter_mate_dockwidget.get_project_layers_from_app.
        
        v4.0 Sprint 3: Partial migration - data handling only.
        UI updates still handled by dockwidget.
        
        Args:
            project_layers: Updated PROJECT_LAYERS dictionary from app
            project: QGIS project instance
            
        Returns:
            dict with status: {'updated': bool, 'layer_count': int, 'reason': str}
        """
        dw = self.dockwidget
        
        # Check if filtering is in progress
        if getattr(dw, '_filtering_in_progress', False) or self._filtering_in_progress:
            logger.info("get_project_layers_data: skipped - filtering in progress")
            
            # Only update data, don't touch UI
            if project_layers is not None:
                dw.PROJECT_LAYERS = project_layers
            if project is not None:
                dw.PROJECT = project
            
            return {
                'updated': False,
                'layer_count': len(project_layers) if project_layers else 0,
                'reason': 'filtering_in_progress'
            }
        
        # Update data
        if project_layers is not None:
            dw.PROJECT_LAYERS = project_layers
        if project is not None:
            dw.PROJECT = project
        
        return {
            'updated': True,
            'layer_count': len(project_layers) if project_layers else 0,
            'reason': 'success'
        }

    # =========================================================================
    # Private Helper Methods for Widget Synchronization
    # =========================================================================

    def _should_skip_combobox_sync(self, layer: Optional[QgsVectorLayer]) -> bool:
        """
        Check if combobox synchronization should be skipped.
        
        Skips during post-filter protection window to prevent CRIT-005.
        
        Args:
            layer: Layer being synced
            
        Returns:
            True if combobox sync should be skipped
        """
        if not self._is_within_post_filter_protection():
            return False
        
        elapsed = time.time() - self._filter_completed_time
        saved_layer_id = self._saved_layer_id_before_filter
        
        if saved_layer_id:
            if layer is None or layer.id() != saved_layer_id:
                layer_name = layer.name() if layer else "(None)"
                logger.info(
                    f"🛡️ synchronize_layer_widgets BLOCKED combobox sync - "
                    f"layer={layer_name} during protection (elapsed={elapsed:.3f}s)"
                )
                return True
        
        return False

    def _sync_current_layer_combobox(self, layer: QgsVectorLayer) -> None:
        """
        Sync the current layer combobox with the layer.
        
        Args:
            layer: Layer to set in combobox
        """
        dw = self.dockwidget
        widgets = getattr(dw, 'widgets', {})
        
        if "FILTERING" not in widgets or "CURRENT_LAYER" not in widgets.get("FILTERING", {}):
            return
        
        current_layer_widget = widgets["FILTERING"]["CURRENT_LAYER"].get("WIDGET")
        if current_layer_widget is None:
            return
        
        last_layer = current_layer_widget.currentLayer()
        current_layer = getattr(dw, 'current_layer', None)
        
        if last_layer is None or current_layer is None:
            return
        
        if last_layer.id() != current_layer.id():
            if hasattr(dw, 'manageSignal'):
                dw.manageSignal(["FILTERING", "CURRENT_LAYER"], 'disconnect')
            current_layer_widget.setLayer(current_layer)
            if hasattr(dw, 'manageSignal'):
                dw.manageSignal(["FILTERING", "CURRENT_LAYER"], 'connect', 'layerChanged')

    def _update_backend_indicator(
        self,
        layer: QgsVectorLayer,
        layer_props: dict
    ) -> None:
        """
        Update the backend indicator for the layer.
        
        Args:
            layer: Current layer
            layer_props: Layer properties
        """
        dw = self.dockwidget
        
        # Get forced backend if set
        forced_backend = None
        forced_backends = getattr(dw, 'forced_backends', {})
        if layer.id() in forced_backends:
            forced_backend = forced_backends[layer.id()]
        
        project_layers = getattr(dw, 'PROJECT_LAYERS', {})
        
        if layer.id() in project_layers:
            infos = layer_props.get('infos', {})
            if 'layer_provider_type' in infos:
                provider_type = infos['layer_provider_type']
                postgresql_conn = infos.get('postgresql_connection_available', None)
                if hasattr(dw, '_update_backend_indicator'):
                    dw._update_backend_indicator(
                        provider_type, postgresql_conn, actual_backend=forced_backend
                    )
        else:
            provider_type = layer.providerType()
            if hasattr(dw, '_update_backend_indicator'):
                dw._update_backend_indicator(provider_type, actual_backend=forced_backend)

    def _sync_layer_property_widgets(
        self,
        layer: QgsVectorLayer,
        layer_props: dict
    ) -> None:
        """
        Synchronize all layer property widgets with stored values.
        
        Args:
            layer: Current layer
            layer_props: Layer properties from PROJECT_LAYERS
        """
        dw = self.dockwidget
        widgets = getattr(dw, 'widgets', {})
        layer_properties_tuples_dict = getattr(dw, 'layer_properties_tuples_dict', {})
        
        for group_name, tuple_group in layer_properties_tuples_dict.items():
            group_state = True
            
            # Skip groups that are always enabled
            if group_name not in ('is', 'selection_expression', 'source_layer'):
                if len(tuple_group) > 0:
                    group_enabled_property = tuple_group[0]
                    group_state = layer_props.get(
                        group_enabled_property[0], {}
                    ).get(group_enabled_property[1], True)
                    
                    if group_state is False:
                        if hasattr(dw, 'properties_group_state_reset_to_default'):
                            dw.properties_group_state_reset_to_default(
                                tuple_group, group_name, group_state
                            )
                    else:
                        if hasattr(dw, 'properties_group_state_enabler'):
                            dw.properties_group_state_enabler(tuple_group)
            
            if group_state is True:
                self._sync_group_widgets(tuple_group, layer_props, layer)

    def _sync_group_widgets(
        self,
        tuple_group: list,
        layer_props: dict,
        layer: QgsVectorLayer
    ) -> None:
        """
        Sync widgets for a property group.
        
        Args:
            tuple_group: List of property tuples
            layer_props: Layer properties
            layer: Current layer
        """
        dw = self.dockwidget
        widgets = getattr(dw, 'widgets', {})
        
        for property_tuple in tuple_group:
            # Skip data-only properties
            if property_tuple[0].upper() not in widgets:
                continue
            if property_tuple[1].upper() not in widgets.get(property_tuple[0].upper(), {}):
                continue
            
            widget_info = widgets[property_tuple[0].upper()][property_tuple[1].upper()]
            widget_type = widget_info.get("TYPE")
            widget = widget_info.get("WIDGET")
            
            if widget is None:
                continue
            
            # Get stored value
            stored_value = layer_props.get(
                property_tuple[0], {}
            ).get(property_tuple[1])
            
            # Sync based on widget type
            self._sync_widget_by_type(
                widget, widget_type, widget_info, property_tuple,
                stored_value, layer, dw
            )

    def _sync_widget_by_type(
        self,
        widget,
        widget_type: str,
        widget_info: dict,
        property_tuple: tuple,
        stored_value,
        layer: QgsVectorLayer,
        dw
    ) -> None:
        """
        Sync a widget based on its type.
        
        Args:
            widget: The widget to sync
            widget_type: Type of widget
            widget_info: Widget info dict
            property_tuple: Property path tuple
            stored_value: Stored value from layer props
            layer: Current layer
            dw: Dockwidget reference
        """
        try:
            if widget_type == 'PushButton':
                # Handle icon switching
                if all(k in widget_info for k in ["ICON_ON_TRUE", "ICON_ON_FALSE"]):
                    if hasattr(dw, 'switch_widget_icon'):
                        dw.switch_widget_icon(property_tuple, stored_value)
                
                if widget.isCheckable():
                    widget.blockSignals(True)
                    widget.setChecked(stored_value)
                    widget.blockSignals(False)
                    
            elif widget_type == 'CheckableComboBox':
                widget.setCheckedItems(stored_value if stored_value else [])
                
            elif widget_type == 'ComboBox':
                if property_tuple[1] in ('source_layer_combine_operator', 'other_layers_combine_operator'):
                    if hasattr(dw, '_combine_operator_to_index'):
                        index = dw._combine_operator_to_index(stored_value)
                    else:
                        index = 0
                else:
                    index = widget.findText(str(stored_value) if stored_value else '')
                    if index == -1:
                        index = 0
                widget.setCurrentIndex(index)
                
            elif widget_type == 'QgsFieldExpressionWidget':
                widget.blockSignals(True)
                widget.setLayer(layer)
                widget.setExpression(str(stored_value) if stored_value else '')
                widget.blockSignals(False)
                
            elif widget_type in ('QgsDoubleSpinBox', 'QgsSpinBox'):
                widget.setValue(stored_value if stored_value is not None else 0)
                
            elif widget_type == 'CheckBox':
                widget.blockSignals(True)
                widget.setChecked(stored_value if stored_value else False)
                widget.blockSignals(False)
                
            elif widget_type == 'LineEdit':
                widget.setText(str(stored_value) if stored_value else '')
                
            elif widget_type == 'QgsProjectionSelectionWidget':
                from qgis.core import QgsCoordinateReferenceSystem
                if stored_value:
                    crs = QgsCoordinateReferenceSystem(stored_value)
                    if crs.isValid():
                        widget.setCrs(crs)
                        
            elif widget_type == 'PropertyOverrideButton':
                widget.setActive(stored_value if stored_value else False)
                
        except Exception as e:
            logger.warning(f"Error syncing widget {property_tuple}: {e}")

    def _sync_layers_to_filter_combobox(self) -> None:
        """Populate the layers_to_filter combobox."""
        dw = self.dockwidget
        
        if hasattr(dw, 'manageSignal'):
            dw.manageSignal(["FILTERING", "LAYERS_TO_FILTER"], 'disconnect')
        
        if hasattr(dw, 'filtering_populate_layers_chekableCombobox'):
            dw.filtering_populate_layers_chekableCombobox()
        
        if hasattr(dw, 'manageSignal'):
            dw.manageSignal(
                ["FILTERING", "LAYERS_TO_FILTER"],
                'connect',
                'checkedItemsChanged'
            )

    def _sync_state_dependent_widgets(self) -> None:
        """Synchronize state-dependent widgets."""
        dw = self.dockwidget
        
        method_names = [
            'filtering_layers_to_filter_state_changed',
            'filtering_combine_operator_state_changed',
            'filtering_geometric_predicates_state_changed',
            'filtering_buffer_property_changed',
            'filtering_buffer_type_state_changed'
        ]
        
        for method_name in method_names:
            if hasattr(dw, method_name):
                try:
                    getattr(dw, method_name)()
                except Exception as e:
                    logger.debug(f"Error calling {method_name}: {e}")

    def _reconnect_legend_link(self) -> None:
        """Reconnect legend link signal if enabled."""
        dw = self.dockwidget
        project_props = getattr(dw, 'project_props', {})
        
        legend_link_enabled = project_props.get(
            "OPTIONS", {}
        ).get("LAYERS", {}).get("LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG", False)
        
        if not legend_link_enabled:
            return
        
        # Reconnect signal
        if hasattr(dw, 'manageSignal'):
            dw.manageSignal(["QGIS", "LAYER_TREE_VIEW"], 'connect')
        
        # Sync Layer Tree View with current_layer
        current_layer = getattr(dw, 'current_layer', None)
        if current_layer is None:
            return
        
        iface = getattr(dw, 'iface', None)
        if iface is None:
            return
        
        active_layer = iface.activeLayer()
        if active_layer is None or active_layer.id() != current_layer.id():
            widgets = getattr(dw, 'widgets', {})
            layer_tree_widget = widgets.get("QGIS", {}).get("LAYER_TREE_VIEW", {}).get("WIDGET")
            
            if layer_tree_widget:
                if hasattr(dw, 'manageSignal'):
                    dw.manageSignal(["QGIS", "LAYER_TREE_VIEW"], 'disconnect')
                layer_tree_widget.setCurrentLayer(current_layer)
                if hasattr(dw, 'manageSignal'):
                    dw.manageSignal(["QGIS", "LAYER_TREE_VIEW"], 'connect')

    def _connect_layer_selection_signal(self) -> None:
        """Connect selectionChanged signal for current layer."""
        dw = self.dockwidget
        current_layer = getattr(dw, 'current_layer', None)
        
        if current_layer is None:
            return
        
        try:
            if hasattr(dw, 'on_layer_selection_changed'):
                current_layer.selectionChanged.connect(dw.on_layer_selection_changed)
                dw.current_layer_selection_connection = True
        except (TypeError, RuntimeError) as e:
            logger.warning(f"Could not connect selectionChanged signal: {e}")
            if hasattr(dw, 'current_layer_selection_connection'):
                dw.current_layer_selection_connection = None

    def _restore_exploring_groupbox_state(self, layer_props: dict) -> None:
        """
        Restore exploring groupbox UI state.
        
        Args:
            layer_props: Layer properties
        """
        dw = self.dockwidget
        
        saved_groupbox = layer_props.get("exploring", {}).get("current_exploring_groupbox")
        current_groupbox = getattr(dw, 'current_exploring_groupbox', None)
        
        if saved_groupbox:
            target_groupbox = saved_groupbox
        elif current_groupbox:
            target_groupbox = current_groupbox
        else:
            target_groupbox = "single_selection"
        
        if hasattr(dw, '_restore_groupbox_ui_state'):
            dw._restore_groupbox_ui_state(target_groupbox)

    def _restore_feature_selection_state(self, layer_props: dict) -> None:
        """
        Restore feature selection state after layer change.
        
        Args:
            layer_props: Layer properties
        """
        dw = self.dockwidget
        current_layer = getattr(dw, 'current_layer', None)
        
        if current_layer is None:
            return
        
        # Link widgets
        if hasattr(dw, 'exploring_link_widgets'):
            dw.exploring_link_widgets()
        
        # Trigger feature update based on groupbox mode
        current_groupbox = getattr(dw, 'current_exploring_groupbox', 'single_selection')
        widgets = getattr(dw, 'widgets', {})
        
        if current_groupbox == "single_selection":
            picker = widgets.get("EXPLORING", {}).get(
                "SINGLE_SELECTION_FEATURES", {}
            ).get("WIDGET")
            
            if picker:
                feature = picker.feature()
                if feature is not None and feature.isValid():
                    if hasattr(dw, 'exploring_features_changed'):
                        dw.exploring_features_changed(feature)
                        
        elif current_groupbox == "multiple_selection":
            multi_picker = widgets.get("EXPLORING", {}).get(
                "MULTIPLE_SELECTION_FEATURES", {}
            ).get("WIDGET")
            
            if multi_picker and hasattr(multi_picker, 'currentSelectedFeatures'):
                features = multi_picker.currentSelectedFeatures()
                if features:
                    if hasattr(dw, 'exploring_features_changed'):
                        dw.exploring_features_changed(features, True)
                        
        elif current_groupbox == "custom_selection":
            custom_expression = layer_props.get("exploring", {}).get(
                "custom_selection_expression", ""
            )
            if custom_expression:
                if hasattr(dw, 'exploring_custom_selection'):
                    dw.exploring_custom_selection()
        
        # Initialize selection sync if is_selecting is enabled
        is_selecting = layer_props.get("exploring", {}).get("is_selecting", False)
        if is_selecting:
            logger.debug("reconnect_layer_signals: is_selecting=True, initializing selection sync")
            if hasattr(dw, 'exploring_select_features'):
                dw.exploring_select_features()

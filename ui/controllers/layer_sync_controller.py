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

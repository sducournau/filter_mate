"""
Filter Result Handler - Phase 4.3 God Class Reduction

Handles filter task completion, result application, and UI synchronization.
Extracted from FilterMateApp.filter_engine_task_completed (~445 lines).

This handler is responsible for:
1. Post-filtering cache management and cleanup
2. Layer refresh and UI synchronization
3. Filter history management (push/clear)
4. Success message display with backend info
5. Undo/redo button state updates
6. Current layer protection and restoration
7. Combobox stability with delayed timers
8. Exploring widgets reload and state restoration

v4.3: Strangler Fig Pattern - New service with fallback to FilterMateApp legacy code.
"""

import time
from typing import Optional, Dict, Any
from qgis.PyQt.QtCore import QTimer
from qgis.core import QgsVectorLayer, QgsProject, QgsMessageLog, Qgis
from qgis.utils import iface

from ..infrastructure.logging import get_app_logger
from ..infrastructure.signal_utils import SignalBlocker
from ..config.feedback_config import should_show_message
from ..infrastructure.feedback import show_success_with_backend, show_info

logger = get_app_logger()


class FilterResultHandler:
    """
    Handles filter operation completion and result application.

    Responsibilities:
    - Cache management (Spatialite multi-step cache clearing)
    - Layer and canvas refresh
    - Filter history updates (push new state, clear on reset)
    - Success message display with backend information
    - Undo/redo button state synchronization
    - Auto-zoom to filtered extent (if tracking enabled)
    - Current layer protection and restoration
    - Combobox stability with delayed signal protection
    - Exploring widgets reload after filtering

    Uses dependency injection callbacks to avoid circular dependencies
    and enable testing without QGIS UI dependencies.
    """

    def __init__(
        self,
        # Callbacks for FilterMateApp methods
        refresh_layers_and_canvas_callback=None,
        push_filter_to_history_callback=None,
        clear_filter_history_callback=None,
        update_undo_redo_buttons_callback=None,
        # Callbacks for accessing state
        get_project_layers_callback=None,
        get_dockwidget_callback=None,
        get_iface_callback=None,
    ):
        """
        Initialize FilterResultHandler with dependency injection.

        Args:
            refresh_layers_and_canvas_callback: Callback to refresh layers and canvas
            push_filter_to_history_callback: Callback to push filter state to history
            clear_filter_history_callback: Callback to clear filter history
            update_undo_redo_buttons_callback: Callback to update undo/redo button states
            get_project_layers_callback: Callback to get PROJECT_LAYERS dict
            get_dockwidget_callback: Callback to get dockwidget instance
            get_iface_callback: Callback to get iface instance (default: qgis.utils.iface)
        """
        self._refresh_layers_and_canvas = refresh_layers_and_canvas_callback
        self._push_filter_to_history = push_filter_to_history_callback
        self._clear_filter_history = clear_filter_history_callback
        self._update_undo_redo_buttons = update_undo_redo_buttons_callback
        self._get_project_layers = get_project_layers_callback
        self._get_dockwidget = get_dockwidget_callback
        self._get_iface = get_iface_callback or (lambda: iface)

    def handle_task_completion(
        self,
        task_name: str,
        source_layer: QgsVectorLayer,
        task_parameters: Dict[str, Any],
        current_layer_id_before_filter: Optional[str] = None
    ) -> None:
        """
        Handle completion of filtering operations.

        Called when FilterEngineTask completes successfully. Applies results to layers,
        updates UI, saves layer variables, and shows success messages.

        Args:
            task_name: Name of completed task ('filter', 'unfilter', 'reset')
            source_layer: Primary layer that was filtered
            task_parameters: Original task parameters including results
            current_layer_id_before_filter: Layer ID that was active before filtering
                (for restoration after completion)

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
            self._clear_spatialite_cache(source_layer, task_parameters)

        # Refresh layers and map canvas
        if self._refresh_layers_and_canvas:
            self._refresh_layers_and_canvas(source_layer)

        # Get task metadata
        feature_count = source_layer.featureCount()
        provider_type = task_parameters["infos"].get("layer_provider_type", "unknown")
        layer_count = len(task_parameters.get("task", {}).get("layers", [])) + 1

        # v2.4.13: Use actual backend for success message (not just requested provider type)
        # This ensures the message reflects what backend was really used (e.g., OGR fallback)
        display_backend, is_fallback = self._determine_backend(task_parameters, provider_type)

        # Handle filter history based on task type
        if task_name == 'filter':
            if self._push_filter_to_history:
                self._push_filter_to_history(source_layer, task_parameters, feature_count, provider_type, layer_count)
        elif task_name == 'reset':
            if self._clear_filter_history:
                self._clear_filter_history(source_layer, task_parameters)

        # Update undo/redo button states
        if self._update_undo_redo_buttons:
            self._update_undo_redo_buttons()

        # Show success message with actual backend used
        self._show_task_completion_message(task_name, source_layer, display_backend, layer_count, is_fallback)

        # Update backend indicator with actual backend used
        self._update_backend_indicator(task_parameters, provider_type, display_backend, is_fallback)

        # Zoom to filtered extent only if is_tracking (auto extent) is enabled
        self._handle_auto_zoom(source_layer)

        # Sync PROJECT_LAYERS between app and dockwidget
        self._sync_project_layers()

        # v2.9.19: CRITICAL - Restore EXACT same current_layer that was active BEFORE filtering
        restored_layer = self._restore_current_layer(current_layer_id_before_filter)

        # v2.8.15: CRITICAL FIX - Ensure current_layer combo and exploring panel stay synchronized
        # v3.0.10: Use restored_layer directly to avoid issues if current_layer is modified by async signals
        self._refresh_ui_after_filtering(restored_layer, display_backend, current_layer_id_before_filter)

        # v2.8.13: CRITICAL - Invalidate expression cache after filtering
        self._invalidate_expression_cache(source_layer, task_parameters)

    def _clear_spatialite_cache(self, source_layer: QgsVectorLayer, task_parameters: Dict[str, Any]) -> None:
        """
        Clear Spatialite cache for all affected layers.

        Args:
            source_layer: Source layer being unfiltered/reset
            task_parameters: Task parameters containing affected layers list
        """
        try:
            from ..infrastructure.cache import get_cache
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

    def _determine_backend(
        self,
        task_parameters: Dict[str, Any],
        provider_type: str
    ) -> tuple[str, bool]:
        """
        Determine actual backend used and whether it was a fallback.

        Args:
            task_parameters: Task parameters containing actual_backends dict
            provider_type: Requested provider type

        Returns:
            Tuple of (display_backend, is_fallback)
        """
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

        # Check if OGR was used as fallback (provider requested spatialite/postgresql but got ogr)
        is_fallback = (display_backend == 'ogr' and provider_type != 'ogr')

        return display_backend, is_fallback

    def _show_task_completion_message(
        self,
        task_name: str,
        source_layer: QgsVectorLayer,
        provider_type: str,
        layer_count: int,
        is_fallback: bool
    ) -> None:
        """
        Show success message with backend info and feature counts.

        Args:
            task_name: Name of completed task ('filter', 'unfilter', 'reset')
            source_layer: Source layer with results
            provider_type: Backend provider type
            layer_count: Number of layers affected
            is_fallback: True if OGR was used as fallback
        """
        feature_count = source_layer.featureCount()
        show_success_with_backend(provider_type, task_name, layer_count, is_fallback=is_fallback)

        # Only show feature count if configured to do so
        if should_show_message('filter_count'):
            if task_name == 'filter':
                show_info(f"{feature_count:,} features visible in main layer")
            elif task_name == 'unfilter':
                show_info(f"All filters cleared - {feature_count:,} features visible in main layer")
            elif task_name == 'reset':
                show_info(f"{feature_count:,} features visible in main layer")

    def _update_backend_indicator(
        self,
        task_parameters: Dict[str, Any],
        provider_type: str,
        display_backend: str,
        is_fallback: bool
    ) -> None:
        """
        Update backend indicator with actual backend used.

        v2.9.25: Pass is_fallback flag to show "Spatialite*" when OGR fallback was used.

        Args:
            task_parameters: Task parameters containing PostgreSQL connection info
            provider_type: Requested provider type
            display_backend: Actual backend used
            is_fallback: Whether OGR fallback was used
        """
        dockwidget = self._get_dockwidget() if self._get_dockwidget else None
        if not dockwidget:
            return

        if hasattr(dockwidget, '_update_backend_indicator'):
            actual_backends = task_parameters.get('actual_backends', {})
            if actual_backends:
                # Get PostgreSQL connection status
                postgresql_conn = task_parameters.get('infos', {}).get('postgresql_connection_available')
                # v2.9.25: If fallback was used, show the original provider with fallback indicator
                if is_fallback:
                    # Show original provider type with fallback flag
                    dockwidget._update_backend_indicator(
                        provider_type, postgresql_conn,
                        actual_backend=f"{provider_type}_fallback"
                    )
                else:
                    dockwidget._update_backend_indicator(provider_type, postgresql_conn, display_backend)

    def _handle_auto_zoom(self, source_layer: QgsVectorLayer) -> None:
        """
        Zoom to filtered extent if auto-zoom is enabled for this layer.

        Args:
            source_layer: Source layer to zoom to
        """
        project_layers = self._get_project_layers() if self._get_project_layers else {}

        # Check if is_tracking is enabled for this layer
        is_tracking_enabled = False
        if source_layer.id() in project_layers:
            layer_props = project_layers[source_layer.id()]
            is_tracking_enabled = layer_props.get("exploring", {}).get("is_tracking", False)

        if not is_tracking_enabled:
            # Just refresh the canvas without zooming
            iface_obj = self._get_iface()
            iface_obj.mapCanvas().refresh()
            return

        # IMPROVED: Use actual filtered extent instead of cached layer extent
        source_layer.updateExtents()  # Force recalculation after filter

        # Use dockwidget helper if available, otherwise calculate directly
        dockwidget = self._get_dockwidget() if self._get_dockwidget else None
        if dockwidget and hasattr(dockwidget, 'get_filtered_layer_extent'):
            extent = dockwidget.get_filtered_layer_extent(source_layer)
        else:
            extent = source_layer.extent()

        iface_obj = self._get_iface()
        if extent and not extent.isEmpty():
            iface_obj.mapCanvas().zoomToFeatureExtent(extent)
            logger.debug("Auto-zoom to filtered extent enabled (is_tracking=True)")
        else:
            iface_obj.mapCanvas().refresh()

    def _sync_project_layers(self) -> None:
        """Sync PROJECT_LAYERS between FilterMateApp and dockwidget."""
        dockwidget = self._get_dockwidget() if self._get_dockwidget else None
        project_layers = self._get_project_layers() if self._get_project_layers else {}

        if dockwidget and project_layers:
            dockwidget.PROJECT_LAYERS = project_layers

    def _restore_current_layer(self, current_layer_id_before_filter: Optional[str]) -> Optional[QgsVectorLayer]:
        """
        Restore the current layer that was active before filtering.

        v2.9.19: CRITICAL - The combobox must show the SAME layer before and after filtering - NEVER change

        Args:
            current_layer_id_before_filter: Layer ID that was active before filtering

        Returns:
            Restored layer or None if restoration failed
        """
        dockwidget = self._get_dockwidget() if self._get_dockwidget else None
        if not dockwidget:
            return None

        restored_layer = None
        if current_layer_id_before_filter:
            restored_layer = QgsProject.instance().mapLayer(current_layer_id_before_filter)
            if restored_layer and restored_layer.isValid():
                dockwidget.current_layer = restored_layer
                logger.info(f"v2.9.19: ✅ Restored current_layer to '{restored_layer.name()}' (same as before filtering)")
            else:
                logger.warning(f"v2.9.19: ⚠️ Could not restore layer ID {current_layer_id_before_filter} - layer no longer exists")
                # Fallback: try to find ANY valid layer
                if hasattr(dockwidget, '_ensure_valid_current_layer'):
                    dockwidget.current_layer = dockwidget._ensure_valid_current_layer(None)
                    if dockwidget.current_layer:
                        logger.info(f"v2.9.19: ⚠️ Fallback: selected '{dockwidget.current_layer.name()}' as current_layer")
        else:
            logger.warning("v2.9.19: ⚠️ No saved current_layer to restore - searching for valid layer")
            # Fallback: ensure we have SOME valid layer if layers exist
            project_layers = self._get_project_layers() if self._get_project_layers else {}
            if not dockwidget.current_layer and len(project_layers) > 0:
                if hasattr(dockwidget, '_ensure_valid_current_layer'):
                    dockwidget.current_layer = dockwidget._ensure_valid_current_layer(None)
                    if dockwidget.current_layer:
                        logger.info(f"v2.9.19: ⚠️ Auto-selected '{dockwidget.current_layer.name()}' as current_layer")

        return restored_layer

    def _refresh_ui_after_filtering(
        self,
        restored_layer: Optional[QgsVectorLayer],
        display_backend: str,
        current_layer_id_before_filter: Optional[str]
    ) -> None:
        """
        Refresh UI components after filtering completes.

        v2.8.15: CRITICAL FIX - Ensure current_layer combo and exploring panel stay synchronized after filtering
        v2.8.16: Extended to ALL backends (not just OGR) - Spatialite/PostgreSQL can also cause combobox reset

        Args:
            restored_layer: The layer restored from before filtering
            display_backend: Backend used for the operation
            current_layer_id_before_filter: Layer ID that was active before filtering
        """
        dockwidget = self._get_dockwidget() if self._get_dockwidget else None
        if not dockwidget:
            return

        # v3.0.10: Use restored_layer directly to avoid issues if current_layer is modified by async signals
        target_layer = restored_layer if restored_layer and restored_layer.isValid() else dockwidget.current_layer

        try:
            if not target_layer:
                logger.warning("v2.9.19: ⚠️ target_layer is None after filtering - skipping UI refresh")
                return

            # 1. Ensure combobox still shows the current layer (CRITICAL for UX)
            self._ensure_combobox_shows_correct_layer(target_layer)

            # 2. Force reload of exploring widgets to refresh feature lists after filtering
            self._reload_exploring_widgets(target_layer, display_backend)

            # 3. v2.8.16: Force explicit layer repaint to ensure canvas displays filtered features
            self._trigger_layer_repaint(target_layer, display_backend)

        except (AttributeError, RuntimeError) as e:
            logger.error(f"v2.9.19: ❌ Error refreshing UI after {display_backend} filter: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
        finally:
            # v2.9.20: CRITICAL FIX - finally OUTSIDE if block to guarantee execution
            # This ensures signal reconnection happens even if current_layer is None
            self._finalize_filtering(current_layer_id_before_filter)

    def _ensure_combobox_shows_correct_layer(self, target_layer: QgsVectorLayer) -> None:
        """
        Ensure combobox still shows the current layer after filtering.

        v2.9.19: This should now be the EXACT same layer as before filtering

        Args:
            target_layer: Layer that should be shown in combobox
        """
        dockwidget = self._get_dockwidget() if self._get_dockwidget else None
        if not dockwidget:
            return

        current_combo_layer = dockwidget.comboBox_filtering_current_layer.currentLayer()
        if not current_combo_layer or current_combo_layer.id() != target_layer.id():
            logger.info(f"v2.9.19: 🔄 Combobox reset detected - restoring to '{target_layer.name()}'")
            # Temporarily disconnect to prevent signal during setLayer
            if hasattr(dockwidget, 'manageSignal'):
                dockwidget.manageSignal(["FILTERING", "CURRENT_LAYER"], 'disconnect')
            dockwidget.comboBox_filtering_current_layer.setLayer(target_layer)
            # Note: Don't reconnect here - let the finally block handle it for consistency
        else:
            logger.info(f"v2.9.19: ✅ Combobox already shows correct layer '{target_layer.name()}'")

    def _reload_exploring_widgets(self, target_layer: QgsVectorLayer, display_backend: str) -> None:
        """
        Force reload of exploring widgets to refresh feature lists after filtering.

        v2.9.20: CRITICAL - ALWAYS reload exploring widgets, even if current_layer didn't change

        Args:
            target_layer: Layer to reload widgets for
            display_backend: Backend used for the operation
        """
        dockwidget = self._get_dockwidget() if self._get_dockwidget else None
        project_layers = self._get_project_layers() if self._get_project_layers else {}
        if not dockwidget or not project_layers:
            return

        try:
            if target_layer.id() not in project_layers:
                logger.warning(f"v2.9.20: ⚠️ target_layer ID {target_layer.id()} not in PROJECT_LAYERS - cannot reload exploring widgets")
                return

            layer_props = project_layers[target_layer.id()]
            logger.info(f"v2.9.20: 🔄 Reloading exploring widgets for '{target_layer.name()}' after {display_backend} filter")

            # FORCE complete reload of exploring widgets with the saved layer
            if hasattr(dockwidget, '_reload_exploration_widgets'):
                dockwidget._reload_exploration_widgets(target_layer, layer_props)

            # v2.9.28: CRITICAL FIX - Always restore groupbox UI state after filtering
            self._restore_groupbox_ui_state(layer_props)

            # v2.9.41: CRITICAL - Update button states after filtering completes
            if hasattr(dockwidget, '_update_exploring_buttons_state'):
                dockwidget._update_exploring_buttons_state()
                logger.info(f"v2.9.41: ✅ Updated exploring button states after {display_backend} filter")

            logger.info("v2.9.20: ✅ Exploring widgets reloaded successfully")
        except Exception as exploring_error:
            logger.error(f"v2.9.20: ❌ Error reloading exploring widgets: {exploring_error}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    def _restore_groupbox_ui_state(self, layer_props: Dict[str, Any]) -> None:
        """
        Restore groupbox UI state after filtering.

        v2.9.28: Use saved groupbox from layer_props if available, fallback to current or default

        Args:
            layer_props: Layer properties containing groupbox state
        """
        dockwidget = self._get_dockwidget() if self._get_dockwidget else None
        if not dockwidget or not hasattr(dockwidget, '_restore_groupbox_ui_state'):
            return

        groupbox_to_restore = None
        if "current_exploring_groupbox" in layer_props.get("exploring", {}):
            groupbox_to_restore = layer_props["exploring"]["current_exploring_groupbox"]
        if not groupbox_to_restore and hasattr(dockwidget, 'current_exploring_groupbox'):
            groupbox_to_restore = dockwidget.current_exploring_groupbox
        if not groupbox_to_restore:
            groupbox_to_restore = "single_selection"  # Default fallback

        dockwidget._restore_groupbox_ui_state(groupbox_to_restore)
        logger.info(f"v2.9.28: ✅ Restored groupbox UI state for '{groupbox_to_restore}'")

    def _trigger_layer_repaint(self, target_layer: QgsVectorLayer, display_backend: str) -> None:
        """
        Force explicit layer repaint to ensure canvas displays filtered features.

        All backends may require explicit triggerRepaint() on BOTH source and current layer

        Args:
            target_layer: Layer to repaint
            display_backend: Backend used for the operation
        """
        try:
            logger.debug(f"v2.9.20: {display_backend} filter completed - triggering layer repaint")
            if target_layer.isValid():
                target_layer.triggerRepaint()
            # Force canvas refresh with stopRendering first to prevent conflicts
            iface_obj = self._get_iface()
            canvas = iface_obj.mapCanvas()
            canvas.stopRendering()
            canvas.refresh()
            logger.info("v2.9.20: ✅ Canvas repaint completed")
        except Exception as repaint_error:
            logger.error(f"v2.9.20: ❌ Error triggering layer repaint: {repaint_error}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    def _finalize_filtering(self, current_layer_id_before_filter: Optional[str]) -> None:
        """
        Finalize filtering operation with signal reconnection and protection.

        v3.0.12: CRITICAL - Set time-based protection BEFORE reconnecting signals
        v3.0.19: CRITICAL FIX - Keep combobox signals BLOCKED during entire 5s protection window

        Args:
            current_layer_id_before_filter: Layer ID that was active before filtering
        """
        logger.info("🔄 _finalize_filtering CALLED")
        dockwidget = self._get_dockwidget() if self._get_dockwidget else None
        if not dockwidget:
            logger.warning("❌ _finalize_filtering: dockwidget is None")
            return

        try:
            # v3.0.12: Set time-based protection BEFORE reconnecting signals
            dockwidget._filter_completed_time = time.time()
            if current_layer_id_before_filter:
                dockwidget._saved_layer_id_before_filter = current_layer_id_before_filter
                logger.info(f"v3.0.12: ⏱️ Initial protection set for layer '{current_layer_id_before_filter[:8]}...'")

            # v2.9.26: CRITICAL - Ensure combobox shows correct layer BEFORE reconnecting signal
            self._force_combobox_restoration(current_layer_id_before_filter)

            # v3.0.19: CRITICAL - Keep combobox signals BLOCKED during 5s protection
            logger.debug("v3.0.19: ⏳ Keeping current_layer signal DISCONNECTED during 5s protection")

            # v2.9.27: Reconnect LAYER_TREE_VIEW signal (if legend link enabled)
            self._reconnect_layer_tree_view_signal()

            # v2.9.24: CRITICAL FIX - Force reconnect ACTION signals
            logger.info("📡 About to call _force_reconnect_action_signals()")
            self._force_reconnect_action_signals()

            # v3.0.11: CRITICAL FIX - Force reconnect EXPLORING signals
            self._force_reconnect_exploring_signals()

            # v2.9.20: FORCE invalidation of exploring cache after filtering
            self._invalidate_exploring_cache()

            # v3.0.12: Final combobox protection BEFORE resetting filtering flag
            self._final_combobox_protection(current_layer_id_before_filter)

            # v3.0.12: Update protection time AFTER restoring combobox
            dockwidget._filter_completed_time = time.time()
            if current_layer_id_before_filter:
                dockwidget._saved_layer_id_before_filter = current_layer_id_before_filter
            logger.info("v3.0.12: ⏱️ Updated 2000ms protection window AFTER combobox restoration")

            # v3.0.19: Schedule combobox signal reconnection AFTER protection expires
            self._schedule_delayed_reconnection(current_layer_id_before_filter)

        except Exception as reconnect_error:
            logger.error(f"v2.9.20: ❌ Failed to reconnect signals: {reconnect_error}")
            # v2.9.25: Reset flag even on error
            if dockwidget:
                dockwidget._filtering_in_progress = False

    def _force_combobox_restoration(self, current_layer_id_before_filter: Optional[str]) -> None:
        """
        Force combobox to show correct layer before reconnecting signals.

        Args:
            current_layer_id_before_filter: Layer ID to restore
        """
        dockwidget = self._get_dockwidget() if self._get_dockwidget else None
        if not dockwidget or not current_layer_id_before_filter:
            return

        restored_layer = QgsProject.instance().mapLayer(current_layer_id_before_filter)
        current_combo_layer = dockwidget.comboBox_filtering_current_layer.currentLayer()
        combo_name = current_combo_layer.name() if current_combo_layer else "(None)"
        restored_name = restored_layer.name() if restored_layer else "(None)"

        # v3.0.16: DEBUG - Log current combobox state
        QgsMessageLog.logMessage(
            f"v3.0.16: 🔍 Combobox state: current='{combo_name}', should_be='{restored_name}'",
            "FilterMate", Qgis.Info
        )

        if restored_layer and restored_layer.isValid():
            if not current_combo_layer or current_combo_layer.id() != restored_layer.id():
                # KEEP SIGNALS BLOCKED - don't unblock yet!
                dockwidget.comboBox_filtering_current_layer.setLayer(restored_layer)
                QgsMessageLog.logMessage(
                    f"v3.0.19: ✅ FORCED combobox to '{restored_layer.name()}' (signals STAY BLOCKED)",
                    "FilterMate", Qgis.Info
                )
                logger.info(f"v3.0.19: ✅ FINALLY - Forced combobox to '{restored_layer.name()}' (signals blocked)")

            # v3.0.10: Also ensure current_layer is set correctly
            if dockwidget.current_layer is None or dockwidget.current_layer.id() != restored_layer.id():
                dockwidget.current_layer = restored_layer
                logger.info(f"v3.0.10: ✅ FINALLY - Ensured current_layer is '{restored_layer.name()}'")

    def _reconnect_layer_tree_view_signal(self) -> None:
        """Reconnect LAYER_TREE_VIEW signal if legend link option is enabled."""
        dockwidget = self._get_dockwidget() if self._get_dockwidget else None
        if not dockwidget:
            return

        if hasattr(dockwidget, 'project_props'):
            link_enabled = dockwidget.project_props.get("OPTIONS", {}).get("LAYERS", {}).get(
                "LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG", False
            )
            if link_enabled and hasattr(dockwidget, 'manageSignal'):
                try:
                    dockwidget.manageSignal(["QGIS", "LAYER_TREE_VIEW"], 'connect')
                    logger.debug("v2.9.27: ✅ FINALLY - Reconnected LAYER_TREE_VIEW signal after filtering")
                except Exception as e:
                    logger.debug(f"Could not reconnect LAYER_TREE_VIEW signal: {e}")

    def _force_reconnect_action_signals(self) -> None:
        """Force reconnect ACTION signals after filtering."""
        logger.info("🔄 _force_reconnect_action_signals CALLED in filter_result_handler")
        dockwidget = self._get_dockwidget() if self._get_dockwidget else None
        if dockwidget and hasattr(dockwidget, 'force_reconnect_action_signals'):
            logger.info("   -> Delegating to dockwidget.force_reconnect_action_signals()")
            dockwidget.force_reconnect_action_signals()
        else:
            logger.warning(f"   -> FAILED: dockwidget={dockwidget}, has_method={hasattr(dockwidget, 'force_reconnect_action_signals') if dockwidget else False}")

    def _force_reconnect_exploring_signals(self) -> None:
        """Force reconnect EXPLORING signals after filtering."""
        dockwidget = self._get_dockwidget() if self._get_dockwidget else None
        if dockwidget and hasattr(dockwidget, 'force_reconnect_exploring_signals'):
            dockwidget.force_reconnect_exploring_signals()

    def _invalidate_exploring_cache(self) -> None:
        """Invalidate exploring cache after filtering to show fresh features."""
        dockwidget = self._get_dockwidget() if self._get_dockwidget else None
        if dockwidget and hasattr(dockwidget, 'invalidate_exploring_cache') and dockwidget.current_layer:
            dockwidget.invalidate_exploring_cache(dockwidget.current_layer.id())
            logger.info(f"v2.9.20: ✅ Invalidated exploring cache for '{dockwidget.current_layer.name()}'")

    def _final_combobox_protection(self, current_layer_id_before_filter: Optional[str]) -> None:
        """
        Final combobox protection before resetting filtering flag.

        v3.0.12: Ensures combobox shows saved layer BEFORE allowing signals through

        Args:
            current_layer_id_before_filter: Layer ID to restore
        """
        dockwidget = self._get_dockwidget() if self._get_dockwidget else None
        if not dockwidget or not current_layer_id_before_filter:
            return

        final_layer = QgsProject.instance().mapLayer(current_layer_id_before_filter)
        if final_layer and final_layer.isValid():
            current_combo = dockwidget.comboBox_filtering_current_layer.currentLayer()
            if not current_combo or current_combo.id() != final_layer.id():
                # Block and restore combobox to correct layer
                with SignalBlocker(dockwidget.comboBox_filtering_current_layer):
                    dockwidget.comboBox_filtering_current_layer.setLayer(final_layer)
                # Also update current_layer reference in dockwidget
                dockwidget.current_layer = final_layer
                logger.info(f"v3.0.12: ✅ FINAL - Restored combobox to '{final_layer.name()}' BEFORE signal unlock")

    def _schedule_delayed_reconnection(self, current_layer_id_before_filter: Optional[str]) -> None:
        """
        Schedule delayed combobox checks and signal reconnection.

        v3.0.19: Keep signals BLOCKED during entire 5s protection window
        v4.1.4 FIX 2026-01-17: ALWAYS reset _filtering_in_progress, even if layer ID is None

        Args:
            current_layer_id_before_filter: Layer ID to monitor and restore
        """
        dockwidget = self._get_dockwidget() if self._get_dockwidget else None
        if not dockwidget:
            return

        # FIX 2026-01-17: If no layer ID to restore, still schedule the flag reset
        # This ensures undo/redo/unfilter buttons work after filtering
        if not current_layer_id_before_filter:
            logger.warning("v4.1.4: ⚠️ No layer ID to restore, scheduling immediate flag reset")

            def reset_flag_only():
                try:
                    if dockwidget:
                        dockwidget._filtering_in_progress = False
                        logger.info("v4.1.4: ✅ Reset _filtering_in_progress (no layer restoration needed)")
                except Exception as e:
                    logger.error(f"v4.1.4: Error resetting flag: {e}")
            QTimer.singleShot(100, reset_flag_only)
            return

        saved_layer_id = current_layer_id_before_filter

        def restore_combobox_if_needed():
            """Check and restore combobox to saved layer if it was changed."""
            try:
                if not dockwidget:
                    return
                saved_layer = QgsProject.instance().mapLayer(saved_layer_id)
                if saved_layer and saved_layer.isValid():
                    current_combo = dockwidget.comboBox_filtering_current_layer.currentLayer()
                    current_name = current_combo.name() if current_combo else "(None)"
                    # v3.0.16: Log every check to QGIS MessageLog
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
                        dockwidget.comboBox_filtering_current_layer.setLayer(saved_layer)
                        dockwidget.current_layer = saved_layer
            except Exception as e:
                logger.debug(f"v3.0.19: Error in delayed combobox check: {e}")

        def unblock_and_reconnect_combobox():
            """Unblock combobox signals and reconnect handler AFTER protection window."""
            try:
                if not dockwidget:
                    return
                # Unblock Qt internal signals
                dockwidget.comboBox_filtering_current_layer.blockSignals(False)
                # Reconnect our handler
                if hasattr(dockwidget, 'manageSignal'):
                    dockwidget.manageSignal(["FILTERING", "CURRENT_LAYER"], 'connect', 'layerChanged')

                # v3.0.19: CRITICAL FIX - Reset _filtering_in_progress HERE, not earlier
                dockwidget._filtering_in_progress = False

                logger.debug("v3.0.19: ✅ Unblocked combobox, reconnected handler, and reset filtering flag after protection")
                QgsMessageLog.logMessage(
                    "v3.0.19: ✅ Combobox protection ENDED - signals reconnected, filtering flag reset",
                    "FilterMate", Qgis.Info
                )
            except Exception as e:
                logger.error(f"v3.0.19: Error reconnecting combobox: {e}")

        # Schedule checks during protection window (signals still blocked)
        # v4.1.3: Reduced delays for faster response time
        for delay in [100, 300, 500, 800, 1000]:
            QTimer.singleShot(delay, restore_combobox_if_needed)

        # v4.1.3: Reduced protection window from 5s to 1.5s for faster user interaction
        # Unblock and reconnect AFTER protection window
        QTimer.singleShot(1500, unblock_and_reconnect_combobox)

        logger.info("v4.1.3: 📋 Scheduled 5 delayed checks + signal reconnection at 1.5s")

    def _invalidate_expression_cache(self, source_layer: QgsVectorLayer, task_parameters: Dict[str, Any]) -> None:
        """
        Invalidate expression cache after filtering.

        v2.8.13: CRITICAL - When a layer's subsetString changes, cached expression results become stale.

        Args:
            source_layer: Source layer whose cache to invalidate
            task_parameters: Task parameters containing affected layers list
        """
        dockwidget = self._get_dockwidget() if self._get_dockwidget else None
        if not dockwidget or not hasattr(dockwidget, 'invalidate_expression_cache'):
            return

        # Invalidate cache for all layers that were filtered
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
            dockwidget.invalidate_expression_cache(layer_id)
            logger.debug(f"v2.8.13: Invalidated expression cache for layer {layer_id}")
